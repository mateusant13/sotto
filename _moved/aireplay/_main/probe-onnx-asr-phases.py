#!/usr/bin/env python
"""probe-onnx-asr-phases.py -- where do the seconds go inside onnx-asr?

`onnx-asr` reached only 2.7-4.0x real time on this box while the sibling's ternary Redux
runner reached 5-14x on the SAME clips. This probe splits one chunk into the three phases
onnx-asr itself runs (asr.py:156 `self._encode(*self._preprocessor(...))` then
`self._decoding(...)`) and counts decoder_joint session.run calls, so the blame is a
number and not a guess.

  py -3 probe-onnx-asr-phases.py --model-dir D --wav F --offset-s 900 --audio-s 10 [--repeat 3]
"""

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np

import onnx_asr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--quant", default="int8")
    ap.add_argument("--provider", default="cpu")
    ap.add_argument("--offset-s", type=float, default=0.0)
    ap.add_argument("--audio-s", type=float, default=10.0)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--threads", type=int, default=0, help="ORT intra_op_num_threads (0 = ORT default)")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    providers = ["CPUExecutionProvider"] if args.provider == "cpu" else ["CUDAExecutionProvider", "CPUExecutionProvider"]
    sess_options = None
    if args.threads:
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = args.threads
    model = onnx_asr.load_model(
        "nemo-parakeet-tdt-0.6b-v3",
        path=Path(args.model_dir),
        quantization=args.quant,
        providers=providers,
        sess_options=sess_options,
    )
    asr = model.asr

    joint = asr._decoder_joint
    calls = {"n": 0}
    real_run = joint.run

    def counting_run(*a, **kw):
        calls["n"] += 1
        return real_run(*a, **kw)

    joint.run = counting_run

    with wave.open(args.wav, "rb") as f:
        sr = f.getframerate()
        f.setpos(int(round(args.offset_s * sr)))
        raw = f.readframes(int(round(args.audio_s * sr)))
    audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    wav_batch = audio[None, :]
    lens = np.array([audio.shape[0]], dtype=np.int64)

    out = {"audio_s": len(audio) / sr, "repeat": args.repeat, "phases": [], "provider": args.provider}
    for i in range(args.repeat):
        calls["n"] = 0
        t0 = time.perf_counter()
        feats, flens = asr._preprocessor(wav_batch, lens)
        t1 = time.perf_counter()
        enc, encl = asr._encode(feats, flens)
        t2 = time.perf_counter()
        toks, stamps, _ = next(iter(asr._decoding(enc, encl)))
        t3 = time.perf_counter()
        row = {
            "i": i,
            "preprocess_s": round(t1 - t0, 4),
            "encode_s": round(t2 - t1, 4),
            "decode_s": round(t3 - t2, 4),
            "total_s": round(t3 - t0, 4),
            "encoder_frames": int(enc.shape[1]) if enc.ndim == 3 else int(enc.shape[0]),
            "tokens": len(toks),
            "joint_calls": calls["n"],
            "rtfx_total": round((len(audio) / sr) / (t3 - t0), 2),
        }
        out["phases"].append(row)
        print(
            f"  run{i}: preprocess={row['preprocess_s']:.3f}s encode={row['encode_s']:.3f}s "
            f"decode={row['decode_s']:.3f}s total={row['total_s']:.3f}s frames={row['encoder_frames']} "
            f"tokens={row['tokens']} joint_calls={row['joint_calls']} rtfx={row['rtfx_total']}",
            flush=True,
        )

    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
