#!/usr/bin/env python3
"""What each Redux engine COSTS on this box: RSS, load time, latency, text.

WHY THIS FILE EXISTS
--------------------
``worker/redux_batch.py`` runs the ternary checkpoint through Photon/kestrel and
was measured at **3.90 GB peak RSS**, because ``_main/redux-gemm8-probe.py`` proved
the packed int8 ("gemm8") CPU path does not exist in the published wheel: the
weights are dequantized 193/193 at load (the documented ``dense`` form).  The owner
had a ~2 s PC stall, so the number that decides whether this is usable for LIVE
captions is memory, and it has to be measured, not inferred.

This probe measures the SAME question for each engine that can actually run here,
in a FRESH PROCESS per arm (peak RSS is a per-process high-water mark; two arms in
one process would report only the larger):

    ternary-cpu   the shipped ternary path, CPU, dense form   (the 3.90 GB one)
    ternary-cuda  the SAME weights and graph, weights on the GPU
    onnx-cpu      the ONNX int4 export (``hf download eschmidbauer/parakeet-redux-onnx``),
                  onnxruntime + numpy only, no torch

WHY ``ternary-cuda`` IS AN ARM: ``resident_form`` returns ``dense`` for CUDA by
design, so the graph is identical -- but the resident weights live in VRAM instead
of host RAM.  That answers "is there a light path on THIS machine", separately from
"is there a distributable path" (which CUDA is not: it needs an NVIDIA GPU).

WHAT IT REPORTS, and why each number is here
--------------------------------------------
  rss_after_imports_mb   the framework's own floor (torch is not free) -- without
                         it, "3.9 GB for the model" and "3.9 GB for torch+model"
                         are the same sentence, and they are not the same fact
  rss_after_load_mb      the model resident, before any inference
  rss_peak_mb            the OS's PeakWorkingSetSize for THIS process: never
                         estimated, read from psapi
  load_s                 time to first inference-ready state
  compute_s / rtf        the transcribe itself, and audio-seconds per wall-second
  text                   compared against ``_main/redux-ptbr.txt`` (the parity
                         oracle) -- a fast engine that transcribes differently is
                         not the same engine

HOUSE BUDGET: probes get <= 2 threads.  ``--threads 2`` is the default and every
number printed carries the cap.  ``--threads 0`` asks the runtime for its own pool
and is labelled NOT-BUDGET when used.

Usage:
    py -3 _main/redux-engine-cost-probe.py --arm ternary-cpu
    py -3 _main/redux-engine-cost-probe.py --arm ternary-cuda
    py -3 _main/redux-engine-cost-probe.py --arm onnx-cpu
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WORKER = REPO / "worker"
WAV = HERE / "pt-br-sample.wav"
ORACLE = HERE / "redux-ptbr.txt"
TERNARY_DIR = WORKER / "models" / "parakeet-redux-ternary"
ONNX_DIR = WORKER / "models" / "parakeet-redux-onnx-int4"
ONNX_REF = WORKER / "models" / "parakeet-redux-reference"

sys.path.insert(0, str(WORKER))
sys.path.insert(0, str(ONNX_REF))


def _log(msg: str) -> None:
    print(msg, flush=True)


def _utf8_streams() -> None:
    """Pin stdout/stderr to UTF-8, whatever the console code page is.

    MEASURED on this pt-BR box: a transcript carrying ``á``/``ã`` raised
    ``UnicodeEncodeError: 'charmap' codec ... character maps to <undefined>`` from
    ``print`` itself (cp1252), so the probe died AFTER doing the measurement and
    printed no verdict. Same convention as ``sotto_worker.py``/``redux_batch.py``.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (ValueError, OSError):
                pass


# ── RSS, read from the OS (the same instrument sotto_worker.py uses) ───────────
class _PMC(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _pmc():
    c = _PMC()
    c.cb = ctypes.sizeof(_PMC)
    psapi = ctypes.WinDLL("psapi")
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    ok = psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return ok, c


def rss_mb() -> float:
    ok, c = _pmc()
    return c.WorkingSetSize / (1024.0 * 1024.0) if ok else -1.0


def peak_rss_mb() -> float:
    ok, c = _pmc()
    return c.PeakWorkingSetSize / (1024.0 * 1024.0) if ok else -1.0


# ── the two engines ───────────────────────────────────────────────────────────
def arm_ternary(device: str, threads: int) -> dict:
    """The shipped ternary path, via ``redux_batch`` (the parity-proven runner)."""
    import redux_batch

    out = {"arm": f"ternary-{device}", "threads": threads,
           "rss_after_imports_mb": round(rss_mb(), 1)}
    _log(f"  rss after imports        : {out['rss_after_imports_mb']:.1f} MB")

    # The SAME loader the shipped runner uses, so the form it picks is the form
    # being measured -- including redux_batch's own `resident_form` patch.
    import torch

    original_load = redux_batch.load_runtime

    def load_with_threads(model_dir, device="cpu", capacity=1):
        import kestrel_kernels.ternary as ternary
        form = redux_batch._weight_form(model_dir)
        _log(f"  resident weight form     : {form}")
        out["weight_form"] = form

        from kestrel.models.parakeet_tdt.runtime import ParakeetTdtRuntime

        cfg = redux_batch._RuntimeConfig(model_dir, device, capacity)
        cfg.cpu_threads = None if threads == 0 else int(threads)
        started = time.perf_counter()
        runtime = ParakeetTdtRuntime(cfg)
        out["load_s"] = round(time.perf_counter() - started, 2)
        _log(f"  loaded in                : {out['load_s']:.2f} s")
        _log(f"  torch.get_num_threads()  : {torch.get_num_threads()}"
             + ("   <-- NOT the house budget" if threads == 0 else ""))
        out["torch_threads"] = torch.get_num_threads()
        _ = ternary
        return runtime

    redux_batch.load_runtime = load_with_threads

    out["rss_after_load_mb"] = None
    started = time.perf_counter()
    runtime = load_with_threads(TERNARY_DIR, device=device)
    out["load_s"] = round(time.perf_counter() - started, 2)
    out["rss_after_load_mb"] = round(rss_mb(), 1)
    _log(f"  rss after load           : {out['rss_after_load_mb']:.1f} MB")

    started = time.perf_counter()
    result = redux_batch.transcribe(runtime, WAV, timestamps="segment")
    out["compute_s"] = round(time.perf_counter() - started, 2)
    duration = float(result.get("duration_seconds") or 0.0)
    out["audio_s"] = round(duration, 2)
    out["rtf"] = round(duration / out["compute_s"], 2) if out["compute_s"] else None

    out["rss_after_infer_mb"] = round(rss_mb(), 1)
    out["rss_peak_mb"] = round(peak_rss_mb(), 1)
    _log(f"  {duration:.1f} s of audio in {out['compute_s']:.2f} s = "
         f"{out['rtf']}x real time")
    _log(f"  rss after inference      : {out['rss_after_infer_mb']:.1f} MB")
    _log(f"  rss PEAK (psapi)         : {out['rss_peak_mb']:.1f} MB")

    out["text"] = str(result.get("text") or "").strip()
    out["segments"] = len(result.get("segments") or ())
    if device == "cuda":
        out["cuda"] = {
            "allocated_mb": round(torch.cuda.memory_allocated() / 1048576.0, 1),
            "max_allocated_mb": round(torch.cuda.max_memory_allocated() / 1048576.0, 1),
            "reserved_mb": round(torch.cuda.memory_reserved() / 1048576.0, 1),
            "device_name": torch.cuda.get_device_name(0),
        }
        _log(f"  CUDA {out['cuda']['device_name']}: "
             f"allocated={out['cuda']['allocated_mb']} MB, "
             f"peak={out['cuda']['max_allocated_mb']} MB, "
             f"reserved={out['cuda']['reserved_mb']} MB")
    return out


def arm_onnx(threads: int) -> dict:
    """The ONNX int4 export, through the export's OWN reference implementation."""
    import numpy as np
    import transcribe as onnx_ref

    out = {"arm": "onnx-cpu", "threads": threads,
           "rss_after_imports_mb": round(rss_mb(), 1)}
    _log(f"  rss after imports        : {out['rss_after_imports_mb']:.1f} MB")
    if not (ONNX_DIR / "encoder-model.onnx").is_file():
        raise SystemExit(f"no ONNX export in {ONNX_DIR}; "
                         f"`hf download eschmidbauer/parakeet-redux-onnx "
                         f"--local-dir {ONNX_DIR}`")

    started = time.perf_counter()
    model = onnx_ref.OnnxParakeet(ONNX_DIR, threads=(None if threads == 0 else int(threads)))
    out["load_s"] = round(time.perf_counter() - started, 2)
    out["rss_after_load_mb"] = round(rss_mb(), 1)
    _log(f"  loaded in                : {out['load_s']:.2f} s")
    _log(f"  rss after load           : {out['rss_after_load_mb']:.1f} MB")

    pcm = onnx_ref.read_audio(WAV)
    out["audio_s"] = round(pcm.size / onnx_ref.SAMPLE_RATE, 2)
    started = time.perf_counter()
    result = model.transcribe(pcm, "segment")
    out["compute_s"] = round(time.perf_counter() - started, 2)
    out["rtf"] = round(out["audio_s"] / out["compute_s"], 2) if out["compute_s"] else None

    out["rss_after_infer_mb"] = round(rss_mb(), 1)
    out["rss_peak_mb"] = round(peak_rss_mb(), 1)
    _log(f"  {out['audio_s']:.1f} s of audio in {out['compute_s']:.2f} s = "
         f"{out['rtf']}x real time")
    _log(f"  rss after inference      : {out['rss_after_infer_mb']:.1f} MB")
    _log(f"  rss PEAK (psapi)         : {out['rss_peak_mb']:.1f} MB")

    out["text"] = str(result.get("text") or "").strip()
    out["segments"] = len(result.get("segments") or ())
    out["providers"] = list(model.encoder.get_providers())
    _log(f"  onnxruntime providers    : {out['providers']}")
    _ = np
    return out


def _oracle_text() -> str:
    """The parity oracle's transcript line, decoded HONESTLY.

    MEASURED: ``_main/redux-ptbr.txt`` is **cp1252**, not UTF-8 -- it holds
    ``b'O r\\xe1dio ... pr\\xf3xima'`` and fails a strict UTF-8 decode.  Reading it
    as UTF-8 produced ``'O r\\ufffdio ... pr\\ufffdx'``, so the comparison against a
    correct UTF-8 transcript reported ``TEXT MATCHES ORACLE: False`` for a reason
    that had nothing to do with either engine -- a comparison that cannot succeed
    is not a gate.  Decode by trying UTF-8 first and falling back to cp1252, and
    say which one was used.
    """
    if not ORACLE.is_file():
        return ""
    raw = ORACLE.read_bytes()
    for encoding in ("utf-8", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", "replace")
        encoding = "utf-8/replace"
    globals()["_ORACLE_ENCODING"] = encoding
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("model loaded") or line.endswith("real time"):
            continue
        return line
    return ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="redux-engine-cost-probe",
        description="Measure RSS / load / latency / text for each Redux engine on this box.")
    parser.add_argument("--arm", required=True,
                        choices=("ternary-cpu", "ternary-cuda", "onnx-cpu"))
    parser.add_argument("--threads", type=int, default=2,
                        help="2 = the house budget for a probe (default); 0 = the "
                             "runtime's own pool, labelled NOT-BUDGET")
    parser.add_argument("--json", action="store_true", help="also print one JSON line")
    args = parser.parse_args(argv)
    _utf8_streams()

    _log(f"ARM {args.arm}  (fresh process, pid={os.getpid()})")
    _log(f"  wav                      : {WAV}")
    _log(f"  threads                  : {args.threads}"
         + ("  <-- NOT the house budget (runtime's own pool)" if args.threads == 0 else ""))

    if args.arm == "ternary-cpu":
        out = arm_ternary("cpu", args.threads)
    elif args.arm == "ternary-cuda":
        out = arm_ternary("cuda", args.threads)
    else:
        out = arm_onnx(args.threads)

    oracle = _oracle_text()
    out["oracle_text"] = oracle
    out["oracle_encoding"] = globals().get("_ORACLE_ENCODING")
    out["text_matches_oracle"] = bool(oracle) and out.get("text", "").strip() == oracle.strip()
    _log(f"  text                     : {out.get('text','')!r}")
    _log(f"  oracle (_main/redux-ptbr): {oracle!r}  [{out['oracle_encoding']}]")
    _log(f"  TEXT MATCHES ORACLE      : {out['text_matches_oracle']}")
    out["type"] = "result"
    if args.json:
        print(json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
