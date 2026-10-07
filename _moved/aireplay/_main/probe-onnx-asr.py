#!/usr/bin/env python
"""probe-onnx-asr.py -- measure the istupakov int8 ONNX export through `onnx-asr`.

Answers ONE question: does `onnx-asr` + `parakeet-tdt-0.6b-v3-onnx` (int8, 670.6 MB on
disk) replace the 3.90 GB-RSS ternary/Redux runner?

Measures, all from inside the process that does the work:
  * model load time
  * RSS before load / after load / peak (1 Hz process-poll) AND the OS `peak_wset`
  * RTFx (audio seconds per wall second), inference-only and wall-including-load
  * the RSS curve over minutes of continuous audio, sampled every --sample-every s,
    each point stamped with BOTH wall seconds and audio seconds processed
  * the transcript, per chunk, so a parity step can diff it

Never opens an audio device: it reads a wav file. No network: the model dir is local
and onnx-asr goes offline when `path` exists (resolver.py:69-72).

Usage:
  py -3 probe-onnx-asr.py --wav F --model-dir D --quant int8 --provider cpu \
      [--chunk-s 30] [--offset-s 900] [--max-s 1800] [--sample-every 1.0] \
      --json OUT.json [--text OUT.txt] [--label NAME]
"""

import argparse
import gc
import json
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np
import psutil

MB = 1024.0 * 1024.0


def now_mb(proc: psutil.Process) -> float:
    return proc.memory_info().rss / MB


class RssSampler(threading.Thread):
    """Polls RSS at a fixed cadence and stamps each point with the audio clock."""

    def __init__(self, proc: psutil.Process, every: float, clock: dict):
        super().__init__(daemon=True)
        self.proc, self.every, self.clock = proc, every, clock
        self.points = []
        self._evt = threading.Event()
        self.t0 = time.perf_counter()
        self.cpu0 = None

    def run(self) -> None:
        self.proc.cpu_percent(None)  # prime the delta
        while not self._evt.is_set():
            t = time.perf_counter() - self.t0
            cpu = self.proc.cpu_percent(None)
            self.points.append(
                [round(t, 3), round(self.clock["audio_s"], 3), round(now_mb(self.proc), 2), round(cpu, 1)]
            )
            self._evt.wait(self.every)

    def stop(self) -> None:
        self._evt.set()
        self.join(timeout=5.0)


def read_block(path: Path, offset_s: float, max_s: float | None):
    """Yield (start_s, float32 mono array) blocks straight off disk; no whole-file copy."""
    with wave.open(str(path), "rb") as f:
        sr, ch, width, frames = f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getnframes()
        if width != 2:
            raise SystemExit(f"probe: expected PCM_16, got sampwidth={width}")
        start = int(round(offset_s * sr))
        f.setpos(min(start, frames))
        remaining = frames - start if max_s is None else min(frames - start, int(round(max_s * sr)))
        return sr, ch, remaining


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--quant", default="int8", help="onnx-asr quantization suffix (int8 -> encoder-model.int8.onnx)")
    ap.add_argument("--provider", default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--chunk-s", type=float, default=0.0, help="0 = one shot over the whole slice")
    ap.add_argument("--offset-s", type=float, default=0.0)
    ap.add_argument("--max-s", type=float, default=0.0, help="0 = to the end of the file")
    ap.add_argument("--sample-every", type=float, default=1.0)
    ap.add_argument("--repeat", type=int, default=1, help="run the SAME slice again, serially (long-run curve on a small slice)")
    ap.add_argument(
        "--threads",
        type=int,
        default=2,
        help="ORT intra_op_num_threads (inter_op fixed at 1); 0 = ORT default (NOT the product number)",
    )
    ap.add_argument("--json", required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    proc = psutil.Process()
    rss_start = now_mb(proc)

    import onnxruntime as ort  # noqa: PLC0415
    import onnx_asr  # noqa: PLC0415

    rss_after_imports = now_mb(proc)

    providers = ["CPUExecutionProvider"]
    if args.provider == "cuda":
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    sess_options = None
    if args.threads:
        ort.SessionOptions  # touch, keeps the import meaningful in the type checker's eyes
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = args.threads
        sess_options.inter_op_num_threads = 1

    wav = Path(args.wav)
    model_dir = Path(args.model_dir)
    sr, ch, remaining = read_block(wav, args.offset_s, args.max_s or None)
    audio_total = remaining / sr * args.repeat

    clock = {"audio_s": 0.0}
    sampler = RssSampler(proc, args.sample_every, clock)
    sampler.start()

    load_t0 = time.perf_counter()
    model = onnx_asr.load_model(
        "nemo-parakeet-tdt-0.6b-v3",
        path=model_dir,
        quantization=args.quant,
        providers=providers,
        sess_options=sess_options,
    )
    load_s = time.perf_counter() - load_t0
    rss_after_load = now_mb(proc)

    asr = model.asr
    sess_providers = [s.get_providers() for s in (getattr(asr, "_encoder", None), getattr(asr, "_decoder_joint", None)) if s]

    chunks = []
    texts = []
    inf_t0 = time.perf_counter()

    for p in range(args.repeat):
        with wave.open(str(wav), "rb") as f:
            start = int(round(args.offset_s * sr))
            f.setpos(min(start, f.getnframes()))
            left = remaining
            step = int(round(args.chunk_s * sr)) if args.chunk_s > 0 else left
            pos = 0
            while left > 0:
                n = min(step, left)
                raw = f.readframes(n)
                got = len(raw) // 2
                if got == 0:
                    break
                audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
                c0 = time.perf_counter()
                text = model.recognize(audio, sample_rate=sr)
                cw = time.perf_counter() - c0
                a0 = pos / sr
                pos += got
                left -= got
                clock["audio_s"] = (p * (remaining / sr)) + pos / sr
                chunks.append(
                    {
                        "pass": p,
                        "start": round(args.offset_s + a0, 3),
                        "end": round(args.offset_s + pos / sr, 3),
                        "audio_s": round(got / sr, 3),
                        "wall_s": round(cw, 3),
                        "chars": len(text),
                        "text": text,
                    }
                )
                texts.append(text)
                print(
                    f"[{time.perf_counter() - inf_t0:7.2f}s] pass{p} {args.offset_s + a0:8.2f}-{args.offset_s + pos / sr:8.2f}s "
                    f"wall={cw:6.2f}s rss={now_mb(proc):8.2f}MB chars={len(text)}",
                    flush=True,
                )
                del audio
                gc.collect()

    inf_s = time.perf_counter() - inf_t0
    sampler.stop()
    mem = proc.memory_info()
    rss_end = mem.rss / MB

    out = {
        "label": args.label or wav.name,
        "wav": str(wav),
        "model_dir": str(model_dir),
        "quant": args.quant,
        "provider_requested": args.provider,
        "onnx_asr": onnx_asr.__version__,
        "onnxruntime": ort.__version__,
        "ort_available_providers": ort.get_available_providers(),
        "session_providers": sess_providers,
        "wav_sample_rate": sr,
        "offset_s": args.offset_s,
        "audio_s": round(audio_total, 3),
        "chunk_s": args.chunk_s,
        "n_chunks": len(chunks),
        "threads_intra_op": args.threads,
        "threads_inter_op": 1 if args.threads else None,
        "omp_num_threads_env": __import__("os").environ.get("OMP_NUM_THREADS"),
        "openblas_num_threads_env": __import__("os").environ.get("OPENBLAS_NUM_THREADS"),
        "load_s": round(load_s, 3),
        "infer_s": round(inf_s, 3),
        "wall_s": round(load_s + inf_s, 3),
        "rtfx_infer": round(audio_total / inf_s, 2) if inf_s > 0 else None,
        "rtfx_wall": round(audio_total / (load_s + inf_s), 2) if (load_s + inf_s) > 0 else None,
        "rss_start_mb": round(rss_start, 1),
        "rss_after_imports_mb": round(rss_after_imports, 1),
        "rss_after_load_mb": round(rss_after_load, 1),
        "rss_end_mb": round(rss_end, 1),
        "rss_peak_poll_mb": round(max([p[2] for p in sampler.points], default=0.0), 1),
        "cpu_median_pct": round(
            sorted([p[3] for p in sampler.points if len(p) > 3])[
                len([p for p in sampler.points if len(p) > 3]) // 2
            ],
            1,
        )
        if sampler.points
        else None,
        "cpu_max_pct": round(max([p[3] for p in sampler.points if len(p) > 3], default=0.0), 1),
        "rss_peak_wset_mb": round(mem.peak_wset / MB, 1),
        "rss_curve_n": len(sampler.points),
        "rss_curve": sampler.points,
        "chunks": chunks,
        "text": " ".join(t.strip() for t in texts if t and t.strip()),
    }
    Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.text:
        Path(args.text).write_text(out["text"], encoding="utf-8")

    print(
        f"RESULT {out['label']}: audio={out['audio_s']}s load={out['load_s']}s infer={out['infer_s']}s "
        f"rtfx_infer={out['rtfx_infer']} rtfx_wall={out['rtfx_wall']} "
        f"threads(intra={out['threads_intra_op']},inter={out['threads_inter_op']}) "
        f"cpu_median={out['cpu_median_pct']}% cpu_max={out['cpu_max_pct']}% "
        f"rss(start/imports/load/peak/end)={out['rss_start_mb']}/{out['rss_after_imports_mb']}/"
        f"{out['rss_after_load_mb']}/{out['rss_peak_poll_mb']}/{out['rss_end_mb']}MB "
        f"peak_wset={out['rss_peak_wset_mb']}MB",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
