"""Is `use_vad` LIVE in onnxruntime-genai 0.17.1, or an inert option?

The VAD-on/VAD-off selftest arms produced byte-identical transcripts, which has
TWO possible causes and they are not the same claim:
  (a) VAD ran and simply never met its own trigger on this clip (silence 3360 ms
      inside a 13.4 s continuous read has nowhere to fire), or
  (b) the option is not consumed at all by this genai build.

`get_option` is the instrument: it reads back what the processor holds. Then the
discriminator is a DIGITAL-SILENCE chunk (0.0 everywhere), which (a) predicts is
gated/dropped by a live VAD and (b) predicts is passed through unchanged by an
inert one.

usage: py -3 _main/vad-option-probe.py
"""
import json
import os

import numpy as np
import onnxruntime_genai as og

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
cfg = json.load(open(os.path.join(ROOT, "worker", "config.json"), encoding="utf-8"))
model_dir = os.path.join(ROOT, "worker", cfg["model"]["dir"])
chunk_samples = json.load(
    open(os.path.join(model_dir, "genai_config.json"), encoding="utf-8")
)["model"]["chunk_samples"]
print("model_dir      :", os.path.basename(model_dir))
print("chunk_samples  :", chunk_samples)

CHUNK = chunk_samples
silence = np.zeros(CHUNK, dtype=np.float32)
# Speech-like: a 440 Hz tone at full scale, the same shape the inject probe used.
t = np.arange(CHUNK, dtype=np.float32) / 16000.0
tone = (0.98 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


def drain(proc, x):
    out = proc.process(x)
    if out is None:
        return None
    af = out["audio_features"]
    af = af.as_numpy() if hasattr(af, "as_numpy") else np.asarray(af)
    return af


def run(use_vad: bool, label: str):
    model = og.Model(model_dir)
    proc = model.create_streaming_processor()
    proc.set_option("use_vad", "1" if use_vad else "0")
    print(f"--- arm {label}: requested use_vad={'1' if use_vad else '0'} ---")
    for key in ("use_vad", "vad", "silence_duration_ms", "prefix_padding_ms", "threshold"):
        try:
            print(f"    get_option({key!r}) = {proc.get_option(key)!r}")
        except Exception as exc:
            print(f"    get_option({key!r}) raised {type(exc).__name__}: {exc}")
    # warm with one speech chunk so the VAD has a "speech" context, then silence
    warm = [drain(proc, tone) for _ in range(3)]
    sil = [drain(proc, silence) for _ in range(12)]
    shape = lambda a: None if a is None else tuple(a.shape)
    zero = lambda a: None if a is None else float(np.abs(a).max())
    print("    warm tone   ->", [shape(a) for a in warm], "peaks", [zero(a) for a in warm])
    print("    silence x12 ->", [(shape(a), None if a is None else round(zero(a), 6)) for a in sil])
    return sil


a = run(False, "off")
b = run(True, "on")

same_shapes = [None if x is None else tuple(x.shape) for x in a] == [
    None if x is None else tuple(x.shape) for x in b
]
none_counts = {"off": sum(1 for x in a if x is None), "on": sum(1 for x in b if x is None)}
print("silence SHAPES identical off vs on :", same_shapes)
print("silence None counts                :", none_counts)
if all(x is not None for x in a + b):
    print(
        "silence max-abs identical off vs on:",
        all(np.array_equal(np.nan_to_num(x), np.nan_to_num(y)) for x, y in zip(a, b)),
    )
