#!/usr/bin/env python3
"""Sotto batch transcriber for the Parakeet Redux ternary checkpoint.

``worker/models/parakeet-redux-ternary/`` is ``moondream/parakeet-redux``, a 1.58-bit
ternary re-quantisation of ``nvidia/parakeet-tdt-0.6b-v3`` (both CC-BY-4.0), and it is run
here by **Photon**, moondream's own runtime, through its Python surface ``kestrel`` — the
vendor runtime that reads the packed ``thrush-ternary-v2`` weights directly. This file is a
thin, batch-shaped wrapper around it: it decodes a WAV file, transcribes it, and prints one
JSON caption line per segment.

Usage
-----
    python worker/redux_batch.py --wav PATH [--json] [--model-dir DIR]

Contract (fixed — another lane parses this): one JSON object per segment on **stdout**,

    {"type": "caption", "text": "...", "start": <seconds>, "end": <seconds>, "producer": "redux"}

Everything else - progress, timings, warnings - goes to **stderr**, so stdout stays a clean
JSON-lines stream. ``--json`` appends one final ``{"type": "result", ...}`` line with the
whole transcript (the caption lines above are printed either way).

It never opens an audio device (the WAV path is decoded from disk by ``kestrel_native``) and
it never spawns a process, so it shows no console window of its own.

Attribution: model ``moondream/parakeet-redux``, license CC-BY-4.0, based on
``nvidia/parakeet-tdt-0.6b-v3`` by NVIDIA. Runtime: Photon / kestrel (moondream).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL_DIR = HERE / "models" / "parakeet-redux-ternary"
PRODUCER = "redux"


def _utf8_streams() -> None:
    """Pin stdout/stderr to UTF-8, whatever the console code page is.

    Same convention as ``sotto_worker.py`` (``sys.stdout.reconfigure(encoding="utf-8",
    errors="replace", line_buffering=True)``): a caption's text is UTF-8 JSON, so a redirect to
    a file must not silently re-encode it into the host locale - on this pt-BR box that writes
    ``á`` as ``0xE1`` and the line stops being valid UTF-8.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (ValueError, OSError):
                pass


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _weight_form(model_dir: Path) -> str:
    """Pick the resident form of the ternary weights, and say what was picked.

    Photon keeps ternary weights packed and runs them through a compiled int8 GEMM ("gemm8")
    whenever the machine has one of avx512vnni / avxvnni / avx2 (x86) or neon-i8mm /
    neon-dotprod / neon-mull (aarch64). ``kestrel_kernels`` ships that kernel in its protected
    ``kestrel_cpu.kstlc`` payload, and on this Windows x86-64 wheel the payload exposes only
    the **scalar** reference - ``ternary_gemm_isa() == "scalar"`` on an AVX2-capable CPU - so
    ``resident_form("cpu")`` raises ``NotImplementedError`` from inside the loader.

    When that happens we fall back to the form Kestrel documents as its own oracle (module
    docstring of ``kestrel_kernels.ternary``): the codes are dequantized once, at load, to
    dense weights in the activation dtype, and the projections run as ordinary float GEMMs.
    Same weights, same graph, same decode loop - only the residency differs - which is why the
    transcript is unchanged. Measured cost on this box: 1.9 GB more resident memory and 193
    weight matrices held dense instead of packed.
    """
    import torch
    import kestrel_kernels.ternary as ternary

    if ternary.ternary_gemm_ready():
        return "gemm8"

    original = ternary.resident_form

    def resident_form(device):
        if torch.device(device).type == "cpu":
            return "dense"
        return original(device)

    ternary.resident_form = resident_form
    return "dense"


class _RuntimeConfig:
    """The slice of Photon's ``RuntimeConfig`` this batch runner needs, and no more."""

    def __init__(self, model_dir: Path, device: str, capacity: int) -> None:
        self.model = str(model_dir)
        self.model_path = str(model_dir)
        self.device = device
        self.decode_path = "auto"
        self.enable_cuda_graphs = device != "cpu"
        self.single_pass_batch_capacity = capacity
        self.cpu_threads = None  # let the runtime size its own pool


def load_runtime(model_dir: Path, device: str = "cpu", capacity: int = 1):
    if not (model_dir / "config.json").is_file():
        raise SystemExit(f"redux_batch: no checkpoint in {model_dir}")
    if not (model_dir / "model.safetensors").is_file():
        raise SystemExit(f"redux_batch: no weights in {model_dir}")
    if not (model_dir / "ternary.json").is_file():
        raise SystemExit(
            f"redux_batch: {model_dir} has no ternary.json manifest; the loader needs it to "
            "recognise the packed export"
        )

    import torch

    form = _weight_form(model_dir)
    _log(f"redux_batch: resident weight form = {form}")

    from kestrel.models.parakeet_tdt.runtime import ParakeetTdtRuntime

    started = time.perf_counter()
    runtime = ParakeetTdtRuntime(_RuntimeConfig(model_dir, device, capacity))
    _log(f"redux_batch: loaded in {time.perf_counter() - started:.2f}s from {model_dir}")
    return runtime


def transcribe(runtime, wav: Path, timestamps: str = "segment"):
    result = runtime.forward("transcribe", [{"audio": str(wav), "timestamps": timestamps}])[0]
    if isinstance(result, BaseException):
        raise result
    return result


def main(argv=None) -> int:
    _utf8_streams()
    parser = argparse.ArgumentParser(
        prog="redux_batch",
        description="Batch-transcribe a WAV file with the Parakeet Redux ternary checkpoint "
                    "(Photon / kestrel).",
    )
    parser.add_argument("--wav", required=True, type=Path, help="16 kHz mono WAV (any WAV the native decoder reads)")
    parser.add_argument("--json", action="store_true", help="also print one final result line")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR,
                        help=f"checkpoint directory (default: {DEFAULT_MODEL_DIR})")
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda", "mps"),
                        help="Photon device (default: cpu)")
    parser.add_argument("--timestamps", default="segment", choices=("none", "segment", "word", "character"),
                        help="caption granularity (default: segment)")
    args = parser.parse_args(argv)

    wav = args.wav.expanduser().resolve()
    if not wav.is_file():
        print(f"redux_batch: no such file: {wav}", file=sys.stderr, flush=True)
        return 2
    model_dir = args.model_dir.expanduser().resolve()

    runtime = load_runtime(model_dir, device=args.device)
    started = time.perf_counter()
    result = transcribe(runtime, wav, timestamps=args.timestamps)
    elapsed = time.perf_counter() - started

    duration = float(result.get("duration_seconds") or 0.0)
    _log(f"redux_batch: {wav.name}: {duration:.1f}s of audio in {elapsed:.2f}s, "
         f"{duration / elapsed if elapsed else 0:.0f}x real time")

    text = str(result.get("text") or "").strip()
    segments = result.get("segments") or ()
    if not segments and text:
        segments = ({"text": text, "start": 0.0, "end": duration},)

    wrote = 0
    for segment in segments:
        caption = str(segment.get("text") or "").strip()
        if not caption:
            continue
        line = {
            "type": "caption",
            "text": caption,
            "start": round(float(segment.get("start") or 0.0), 3),
            "end": round(float(segment.get("end") or 0.0), 3),
            "producer": PRODUCER,
        }
        print(json.dumps(line, ensure_ascii=False), flush=True)
        wrote += 1

    if args.json:
        print(json.dumps({
            "type": "result",
            "text": text,
            "segments": wrote,
            "duration": round(duration, 3),
            "compute_seconds": round(elapsed, 3),
            "real_time_factor": round(duration / elapsed, 2) if elapsed else None,
            "producer": PRODUCER,
            "wav": str(wav),
            "model_dir": str(model_dir),
        }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
