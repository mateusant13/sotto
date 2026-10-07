#!/usr/bin/env python3
"""MEASUREMENT INSTRUMENT — onnx-asr against the istupakov v3-onnx int8 export.

This is the only instrument this lane owns. It answers four questions in ONE process,
because they must come from the same run to be comparable:

  1. PEAK RSS of the whole process (the number that decides whether the int8 ONNX
     export can replace the 3.90 GB ternary/Photon runner).
  2. RTFx = seconds of audio / second of wall clock, per pass.
  3. parity: the transcript of the two reference clips, printed verbatim.
  4. the RSS CURVE over a long continuous decode loop — a leak only shows as a slope.

Design notes
------------
* It writes its OWN result file. It is launched as ``pythonw.exe`` (no console, ever),
  whose stdout is None, so nothing may be printed to stdout for the report to survive.
  Human-readable progress still goes to stderr (harmless) and to the timeline file.
* The RSS timeline is sampled by a DAEMON THREAD every ``--sample-ms``, using
  ``GetProcessMemoryInfo`` on our own process: no WMI, no external poller, and the
  samples exist even while the main thread is inside a long onnxruntime call.
* Two RSS numbers are reported and they are different claims:
  ``peak_working_set`` (what the OS charged to the process) and
  ``peak_private`` (commit charge). The ternary receipt quoted working set; working set
  is what this receipt compares against, and private is reported next to it.

Usage
-----
    pythonw onnx_asr_probe.py --out R.json --timeline T.jsonl
        --parity-clips A.wav,B.wav
        --loop-wav C.wav --loop-passes N
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------- RSS sampling

PROCESS_QUERY_INFORMATION = 0x0400


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)
_GetCurrentProcess = _kernel32.GetCurrentProcess
_GetCurrentProcess.restype = ctypes.c_void_p
_GetProcessMemoryInfo = _psapi.GetProcessMemoryInfo
_GetProcessMemoryInfo.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
    wt.DWORD,
]
_GetProcessMemoryInfo.restype = wt.BOOL


def rss_bytes() -> tuple[int, int, int]:
    """(working_set, peak_working_set, private) for THIS process, in bytes."""
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    if not _GetProcessMemoryInfo(_GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise OSError(f"GetProcessMemoryInfo failed: {ctypes.get_last_error()}")
    return counters.WorkingSetSize, counters.PeakWorkingSetSize, counters.PagefileUsage


class Sampler:
    """Own-RSS sampler on a daemon thread; writes one JSONL line per sample."""

    def __init__(self, timeline: Path, sample_ms: int) -> None:
        self.timeline = timeline
        self.sample_ms = sample_ms
        self.t0 = time.perf_counter()
        self._lock = threading.Lock()
        self._phase = "startup"
        self._stop = threading.Event()
        self.samples: list[dict] = []
        self._fh = timeline.open("w", encoding="utf-8", buffering=1)
        self._thread = threading.Thread(target=self._run, name="rss-sampler", daemon=True)

    def phase(self, name: str) -> None:
        with self._lock:
            self._phase = name
        self._record(marker=f"phase={name}")

    def _record(self, marker: str | None = None) -> None:
        ws, peak, priv = rss_bytes()
        with self._lock:
            row = {
                "t": round(time.perf_counter() - self.t0, 3),
                "phase": self._phase,
                "ws_mb": round(ws / 2**20, 1),
                "peak_ws_mb": round(peak / 2**20, 1),
                "private_mb": round(priv / 2**20, 1),
            }
        if marker:
            row["marker"] = marker
        self.samples.append(row)
        self._fh.write(json.dumps(row) + "\n")

    def _run(self) -> None:
        while not self._stop.wait(self.sample_ms / 1000.0):
            try:
                self._record()
            except OSError:
                return

    def start(self) -> None:
        self._record(marker="sampler-start")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._record(marker="sampler-stop")
        self._fh.close()

    def peak(self) -> dict:
        return {
            "peak_working_set_mb": max(s["ws_mb"] for s in self.samples),
            "peak_working_set_os_mb": max(s["peak_ws_mb"] for s in self.samples),
            "peak_private_mb": max(s["private_mb"] for s in self.samples),
            "samples": len(self.samples),
        }

    def phase_peaks(self) -> dict:
        out: dict[str, float] = {}
        for s in self.samples:
            out[s["phase"]] = max(out.get(s["phase"], 0.0), s["ws_mb"])
        return out


# ---------------------------------------------------------------- profiling

def _profile_summary(model, out_dir: str) -> dict:
    """Aggregate ORT's per-node profile: which op types actually spend the time.

    This is what turns "it is slow" into a cause. A pure-Python or a fallback kernel
    shows up as one op_type dominating, and that is observable, unlike a hunch.
    """
    import collections

    summary: dict = {}
    sessions = {}
    for attr in ("_encoder", "_decoder_joint"):
        sess = getattr(getattr(model, "asr", None), attr, None)
        if sess is not None:
            sessions[attr] = sess
    for attr, sess in sessions.items():
        try:
            raw = sess.end_profiling()
            events = json.loads(Path(raw).read_text(encoding="utf-8"))
        except BaseException as exc:  # noqa: BLE001
            summary[attr] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        by_type: dict[str, float] = collections.defaultdict(float)
        by_type_n: dict[str, int] = collections.defaultdict(int)
        by_node: dict[str, float] = collections.defaultdict(float)
        for ev in events:
            if ev.get("cat") != "Node" or "dur" not in ev:
                continue
            t = ev.get("args", {}).get("op_type", ev.get("name", "?"))
            by_type[t] += ev["dur"]
            by_type_n[t] += 1
            by_node[f"{ev.get('name')}|{t}"] += ev["dur"]
        total = sum(by_type.values())
        summary[attr] = {
            "profile_file": str(raw),
            "node_events": sum(by_type_n.values()),
            "total_node_us": round(total, 1),
            "by_op_type_ms": {
                k: round(v / 1000.0, 1)
                for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])[:12]
            },
            "top_nodes_ms": {
                k: round(v / 1000.0, 1)
                for k, v in sorted(by_node.items(), key=lambda kv: -kv[1])[:8]
            },
        }
    return summary


# ---------------------------------------------------------------- the run

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="nemo-parakeet-tdt-0.6b-v3")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--quantization", default="int8")
    ap.add_argument("--parity-clips", default="", help="comma-separated wav paths")
    ap.add_argument("--loop-wav", default="", help="wav fed repeatedly for the RSS curve")
    ap.add_argument("--loop-passes", type=int, default=0)
    ap.add_argument("--loop-wav-seconds", type=float, default=0.0, help="duration of --loop-wav, for RTFx")
    ap.add_argument("--warmup-clip", default="")
    ap.add_argument("--sample-ms", type=int, default=500)
    ap.add_argument("--providers", default="", help="comma-separated ORT providers; empty = ORT default")
    ap.add_argument("--intra-threads", type=int, default=0, help="0 = ORT default")
    ap.add_argument("--profile", default="", help="directory for ORT node profiles; empty = off")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeline", required=True)
    args = ap.parse_args(argv)

    out_path = Path(args.out)
    result: dict = {
        "instrument": "onnx_asr_probe.py",
        "pid": os.getpid(),
        "python": sys.version,
        "argv": sys.argv,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    sampler = Sampler(Path(args.timeline), args.sample_ms)
    sampler.start()

    def write_result() -> None:
        result["total_wall_s"] = round(time.perf_counter() - sampler.t0, 3)
        result["rss"] = sampler.peak()
        result["rss_phase_peaks_mb"] = sampler.phase_peaks()
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        import numpy as np
        import onnxruntime as ort

        result["onnxruntime"] = ort.__version__
        result["available_providers"] = ort.get_available_providers()
        # The provider list above is what ORT *offers*; on this box the CUDA EP is
        # offered and then fails to load (missing cublasLt64_13.dll), which costs ~1.5 s
        # of the load time and is recorded in the receipt. Quiet the ORT info spam so the
        # probe's own files stay readable; the failure is captured in `sessions` below.
        ort.set_default_logger_severity(3)

        import onnx_asr

        result["onnx_asr"] = getattr(onnx_asr, "__version__", "unknown")

        sampler.phase("import-done")
        sess_options = ort.SessionOptions()
        if args.intra_threads:
            sess_options.intra_op_num_threads = args.intra_threads
        if args.profile:
            Path(args.profile).mkdir(parents=True, exist_ok=True)
            sess_options.enable_profiling = True
            sess_options.profile_file_prefix = str(Path(args.profile) / "ort")
        providers = [p for p in args.providers.split(",") if p.strip()] or None
        result["providers_requested"] = providers
        t_load = time.perf_counter()
        model = onnx_asr.load_model(
            args.model,
            path=args.model_dir,
            quantization=args.quantization or None,
            sess_options=sess_options,
            providers=providers,
        )
        result["load_seconds"] = round(time.perf_counter() - t_load, 3)
        result["model_dir"] = str(args.model_dir)
        result["quantization"] = args.quantization
        sampler.phase("loaded")

        # Which execution provider did the sessions actually get?
        sessions = []
        for attr in ("_encoder", "_decoder_joint", "_model", "_decoder"):
            sess = getattr(getattr(model, "asr", None), attr, None)
            if sess is not None:
                inp = {i.name: i.shape for i in sess.get_inputs()}
                sessions.append({
                    "attr": attr,
                    "providers": sess.get_providers(),
                    "inputs": inp,
                })
        result["sessions"] = sessions
        so = None
        for attr in ("_encoder", "_decoder_joint"):
            sess = getattr(getattr(model, "asr", None), attr, None)
            if sess is not None:
                so = sess.get_session_options()
                break
        if so is not None:
            result["sess_intra_op_threads"] = so.intra_op_num_threads
        result["cpu_count"] = os.cpu_count()

        # ---- warm-up ------------------------------------------------------
        if args.warmup_clip:
            sampler.phase("warmup")
            t = time.perf_counter()
            list(model.recognize([args.warmup_clip]))
            result["warmup_seconds"] = round(time.perf_counter() - t, 3)
            sampler.phase("warm-done")

        # ---- parity -------------------------------------------------------
        clips = [c for c in args.parity_clips.split(",") if c.strip()]
        if clips:
            result["parity"] = []
            for clip in clips:
                sampler.phase(f"parity:{Path(clip).name}")
                t = time.perf_counter()
                texts = list(model.recognize([clip]))
                el = time.perf_counter() - t
                row = {
                    "wav": clip,
                    "wall_seconds": round(el, 3),
                    "text": "\n".join(texts),
                }
                result["parity"].append(row)
            sampler.phase("parity-done")

        # ---- the RSS curve ------------------------------------------------
        if args.loop_wav and args.loop_passes:
            sampler.phase("curve")
            passes = []
            t_curve = time.perf_counter()
            for i in range(args.loop_passes):
                t = time.perf_counter()
                list(model.recognize([args.loop_wav]))
                el = time.perf_counter() - t
                ws, _, priv = rss_bytes()
                row = {
                    "pass": i + 1,
                    "wall_s": round(el, 3),
                    "ws_mb": round(ws / 2**20, 1),
                    "private_mb": round(priv / 2**20, 1),
                    "t_rel_s": round(time.perf_counter() - t_curve, 3),
                }
                if args.loop_wav_seconds:
                    row["rtfx"] = round(args.loop_wav_seconds / el, 3)
                passes.append(row)
                self_marker = f"pass={i + 1}"
                sampler._record(marker=self_marker)  # noqa: SLF001 - same object
            curve_wall = time.perf_counter() - t_curve
            result["curve"] = {
                "wav": args.loop_wav,
                "elapsed_note": "wav file; onnx-asr reports no duration, --loop-wav-seconds is a probe argument",
                "passes": len(passes),
                "curve_wall_seconds": round(curve_wall, 3),
                "audio_seconds_total": round(args.loop_wav_seconds * len(passes), 3),
                "rtfx_mean": round(
                    args.loop_wav_seconds * len(passes) / curve_wall, 3
                ) if curve_wall else None,
                "per_pass": passes,
            }
            sampler.phase("curve-done")

        sampler.phase("done")
        if args.profile:
            result["profile"] = _profile_summary(model, args.profile)
        write_result()
    except BaseException as exc:  # noqa: BLE001 - the report must survive any failure
        import traceback

        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        sampler.phase("error")
        write_result()
        sampler.stop()
        return 1

    sampler.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
