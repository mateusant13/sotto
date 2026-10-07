"""Sotto ASR -- the int8 ONNX Parakeet-TDT engine (`specs/02-asr.md`).

Layout:
  constants.py  every MEASURED constant, each with its provenance (`path:line`)
  audio.py      16 kHz mono PCM16 in; anything else is refused, never converted
  segment.py    cut on SILENCE (a fixed grid is a CONTROL, ratio 0.229)
  level.py      the 10 Hz windowed level event -- the panel's only honest wave
  engine.py     the loaded artefact + the pinned thread knee (intra=4, inter=1)
  runner.py     the loop; every metric is produced by the process that did the work
  transcribe.py `python -m asr.transcribe --wav FILE [--json]`
  parity.py     the harness: ternary oracle arms + the same-engine regression lock

This module deliberately imports nothing heavy: `asr.engine.pin_thread_env()` must run
BEFORE numpy and onnxruntime load their thread pools, so the CLI pins first and imports after.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
