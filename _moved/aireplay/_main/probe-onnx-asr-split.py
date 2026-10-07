#!/usr/bin/env python
"""probe-onnx-asr-split.py -- same measurement as probe-onnx-asr.py, but the audio is cut
into segments the way a BACKGROUND PASS would cut it, not on a fixed grid.

Why: the fixed-10 s run over the sibling's plain-3600s.wav slice produced garbage at the
seams ("The radio announce. that the bridge", "anunció que la bridge", "TECA. Video
announced") because a fixed grid cuts mid-word and hands the model half a word. That is a
CHUNKING-POLICY effect, and the sibling's Redux pass does NOT have it (its own segmenter
cuts on silence). This probe isolates the two.

`--mode fixed` is the CONTROL arm: it must reproduce probe-onnx-asr.py's text for the same
window byte for byte, or the instrument is wrong.

Splitter is energy-only (no model, no download): 20 ms RMS frames, silence = frames below
max(4x the 10th-percentile floor, 0.005), runs >= 300 ms are cut at their midpoint,
segments longer than --max-seg are split at their quietest frame, silence-only segments are
dropped, 100 ms of pad is kept either side.
"""

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np
import psutil

MB = 1024.0 * 1024.0
SR = 16000


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / MB


def read_slice(path: str, offset_s: float, audio_s: float) -> np.ndarray:
    with wave.open(path, "rb") as f:
        assert f.getframerate() == SR and f.getnchannels() == 1 and f.getsampwidth() == 2, "expect 16k mono PCM16"
        f.setpos(int(round(offset_s * SR)))
        raw = f.readframes(int(round(audio_s * SR)))
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def segments_silence(x: np.ndarray, min_sil: float = 0.30, max_seg: float = 15.0, min_seg: float = 0.6):
    fl = 320  # 20 ms
    n = len(x) // fl
    frames = x[: n * fl].reshape(n, fl)
    rms = np.sqrt((frames**2).mean(axis=1) + 1e-12)
    floor = float(np.percentile(rms, 10))
    thr = max(floor * 4.0, 0.005)
    silent = rms < thr
    min_run = int(round(min_sil / 0.02))
    cuts = []
    i = 0
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            if j - i >= min_run:
                cuts.append((i + j) // 2)
            i = j
        else:
            i += 1
    bounds = [0, *cuts, n]
    segs = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = (a, b)
        while (seg[1] - seg[0]) * 0.02 > max_seg:
            lim_lo = seg[0] + int(round(min_seg / 0.02))
            lim_hi = seg[0] + int(round(max_seg / 0.02))
            k = int(np.argmin(rms[lim_lo:lim_hi])) + lim_lo
            segs.append((seg[0], k))
            seg = (k, seg[1])
        segs.append(seg)
    pad = int(round(0.10 / 0.02))
    out = []
    for a, b in segs:
        if (b - a) * 0.02 < min_seg:
            continue
        if silent[a:b].all():
            continue
        out.append((max(0, (a - pad) * fl), min(len(x), (b + pad) * fl)))
    return [(a / SR, b / SR) for a, b in out]


def segments_fixed(total_s: float, chunk_s: float):
    out = []
    t = 0.0
    while t < total_s - 1e-6:
        b = min(t + chunk_s, total_s)
        out.append((t, b))
        t = b
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--quant", default="int8")
    ap.add_argument("--provider", default="cpu")
    ap.add_argument("--mode", choices=["fixed", "silence"], required=True)
    ap.add_argument("--chunk-s", type=float, default=10.0)
    ap.add_argument("--max-seg", type=float, default=15.0)
    ap.add_argument("--offset-s", type=float, default=0.0)
    ap.add_argument("--max-s", type=float, default=180.0)
    ap.add_argument(
        "--threads",
        type=int,
        default=2,
        help="ORT intra_op_num_threads (inter_op fixed at 1); 0 = ORT default (NOT the product number)",
    )
    ap.add_argument("--json", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    import onnx_asr  # noqa: PLC0415

    rss0 = rss_mb()
    providers = ["CPUExecutionProvider"] if args.provider == "cpu" else ["CUDAExecutionProvider", "CPUExecutionProvider"]
    sess_options = None
    if args.threads:
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = args.threads
        sess_options.inter_op_num_threads = 1
    t0 = time.perf_counter()
    model = onnx_asr.load_model(
        "nemo-parakeet-tdt-0.6b-v3",
        path=Path(args.model_dir),
        quantization=args.quant,
        providers=providers,
        sess_options=sess_options,
    )
    load_s = time.perf_counter() - t0
    rss_load = rss_mb()

    x = read_slice(args.wav, args.offset_s, args.max_s)
    total_s = len(x) / SR
    segs = segments_fixed(total_s, args.chunk_s) if args.mode == "fixed" else segments_silence(x, max_seg=args.max_seg)

    texts, rows, peak = [], [], rss_load
    t1 = time.perf_counter()
    for a, b in segs:
        audio = x[int(round(a * SR)) : int(round(b * SR))]
        c0 = time.perf_counter()
        txt = model.recognize(audio, sample_rate=SR)
        cw = time.perf_counter() - c0
        peak = max(peak, rss_mb())
        texts.append(txt)
        rows.append(
            {
                "start": round(args.offset_s + a, 3),
                "end": round(args.offset_s + b, 3),
                "audio_s": round(b - a, 3),
                "wall_s": round(cw, 3),
                "chars": len(txt),
                "text": txt,
            }
        )
        print(f"  {args.offset_s + a:8.2f}-{args.offset_s + b:8.2f}s wall={cw:6.2f}s rss={rss_mb():7.2f}MB chars={len(txt)}", flush=True)
    inf_s = time.perf_counter() - t1
    text = " ".join(t.strip() for t in texts if t and t.strip())
    Path(args.text).write_text(text, encoding="utf-8")

    mem = psutil.Process().memory_info()
    durs = [b - a for a, b in segs]
    out = {
        "label": args.label,
        "mode": args.mode,
        "wav": args.wav,
        "offset_s": args.offset_s,
        "audio_s": round(total_s, 3),
        "n_segments": len(segs),
        "threads_intra_op": args.threads,
        "threads_inter_op": 1 if args.threads else None,
        "seg_median_s": round(float(np.median(durs)), 3) if durs else 0,
        "seg_max_s": round(float(np.max(durs)), 3) if durs else 0,
        "load_s": round(load_s, 3),
        "infer_s": round(inf_s, 3),
        "rtfx_infer": round(total_s / inf_s, 2) if inf_s else None,
        "rss_start_mb": round(rss0, 1),
        "rss_after_load_mb": round(rss_load, 1),
        "rss_peak_mb": round(peak, 1),
        "rss_peak_wset_mb": round(mem.peak_wset / MB, 1),
        "segments": rows,
        "text": text,
    }
    Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"RESULT {args.label}: mode={args.mode} audio={out['audio_s']}s segs={len(segs)} "
        f"(med={out['seg_median_s']}s max={out['seg_max_s']}s) load={load_s:.2f}s infer={inf_s:.2f}s "
        f"rtfx={out['rtfx_infer']} rss(load/peak/peak_wset)={out['rss_after_load_mb']}/{out['rss_peak_mb']}/"
        f"{out['rss_peak_wset_mb']}MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
