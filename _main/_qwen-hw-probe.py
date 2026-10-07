#!/usr/bin/env python3
"""_qwen-hw-probe.py -- capability probe + gate for the hourly Qwen title/summary feature.

DESIGN PRINCIPLE, stated because a wrong answer here is a failed delivery:
    A CAPABILITY QUERY IS NOT EVIDENCE. ONLY PERFORMING THE CAPABILITY IS.
Every verdict below is produced by DOING the thing on this box and recording what
happened. A library's own claim (`torch.cuda.is_available()`,
`ort.get_available_providers()`, `_cpu.ternary_gemm_isa()`, WMI `AdapterRAM`) is
recorded as a HINT with its source, and is NEVER the verdict on its own.

Why that rule is not paranoia -- all three measured on this one machine:
  * `onnxruntime.get_available_providers()` lists CUDAExecutionProvider and
    `ort.get_device()` says `GPU`, yet a real InferenceSession requesting CUDA
    silently binds CPUExecutionProvider (missing `cublasLt64_13.dll`).
  * `torch.cuda.is_available()` is True with torch 2.7.0+cu128 on the SAME GPU.
  * kestrel's `_cpu.ternary_gemm_isa()` returns 'scalar' on an i5-13600K that
    has AVX2, because its kernel sits in a protected payload.
Same box, three different answers, one of them produced by a vendor probe that
had every reason to work.

Output: one structured record per capability --
    {capability, verdict, confidence, method, evidence, reason, timestamp}
`verdict` is one of: "ok" | "unavailable" | "degraded" | "unknown".
Nothing here is ever a bare boolean.

READ-ONLY AND INERT: no downloads, no installs, no audio device, no window.
The only allocation it performs is a small tensor followed by a deliberate OOM
probe, both of which are released immediately.

Usage:
    python _main\\_qwen-hw-probe.py [out.log] [--no-smi-on-path]
    --no-smi-on-path   simulate a machine where `nvidia-smi` is not on PATH
                       (robustness self-test; every other method must still work)
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

CREATE_NO_WINDOW = 0x08000000

# Capabilities whose verdict is allowed to gate a download.
VERDICT_OK = "ok"
VERDICT_UNAVAILABLE = "unavailable"
VERDICT_DEGRADED = "degraded"
VERDICT_UNKNOWN = "unknown"


class Report:
    """Tee the report to stdout AND a UTF-8 file we own.

    We open the file ourselves rather than relying on shell redirection: creating
    an ORT InferenceSession flips the Windows CRT stdout handle to UTF-16
    (`_O_U16TEXT`), which turns `> log 2>&1` into a UTF-16LE file that ordinary
    tools cannot read. MEASURED on this box.
    """

    def __init__(self, path: str | None) -> None:
        self.fh = open(path, "w", encoding="utf-8", errors="replace") if path else None
        self._orig = sys.__stdout__

    def write(self, text: str) -> int:
        try:
            self._orig.write(text)
        except Exception:
            pass
        if self.fh:
            self.fh.write(text)
            self.fh.flush()
        return len(text)

    def flush(self) -> None:
        try:
            self._orig.flush()
        except Exception:
            pass
        if self.fh:
            self.fh.flush()

    def close(self) -> None:
        if self.fh:
            self.fh.close()
            self.fh = None


def force_utf8_stdout() -> None:
    """Best-effort recovery of fd 1 after ONNX Runtime's CRT mode flip."""
    try:
        ctypes.windll.msvcrt._setmode(1, os.O_TEXT)
    except Exception:
        try:
            ctypes.windll.ucrtbase._setmode(1, os.O_TEXT)
        except Exception:
            pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# verdict records
# ---------------------------------------------------------------------------

def rec(capability: str, verdict: str, method: str, evidence,
        confidence: str = "measured", reason: str = "") -> dict:
    """Build one capability record. Never returns a bare boolean."""
    return {
        "capability": capability,
        "verdict": verdict,
        "confidence": confidence,
        "method": method,
        "evidence": evidence,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def hr(title: str) -> None:
    print()
    print("=" * 76)
    print(title)
    print("=" * 76)


def show(r: dict) -> None:
    mark = {"ok": "OK  ", "unavailable": "UNAV", "degraded": "DEGR", "unknown": "UNKN"}
    print(f"  [{mark.get(r['verdict'], '??')}] {r['capability']}")
    print(f"         confidence : {r['confidence']}")
    print(f"         method     : {r['method']}")
    ev = r["evidence"]
    if isinstance(ev, (dict, list)):
        for line in json.dumps(ev, indent=2, default=str).splitlines():
            print(f"         evidence   : {line}")
    else:
        print(f"         evidence   : {ev}")
    if r["reason"]:
        print(f"         reason     : {r['reason']}")


def run_capture(cmd: list[str], timeout: int = 25) -> tuple[int, str]:
    """Run a console program with NO window (the owner's app is LIVE)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW, errors="replace")
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except FileNotFoundError:
        return 127, "NOT FOUND on PATH"
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


# ===========================================================================
# METHOD 1 -- nvidia-smi.  Note: absence from PATH is NOT evidence of no GPU.
# ===========================================================================

SMI_CANDIDATES = [
    "nvidia-smi",                                                    # PATH
    r"C:\Windows\System32\nvidia-smi.exe",                           # usual Windows home
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",     # legacy home
]


def find_and_run_smi(simulate_absent: bool = False) -> tuple[str | None, str, str]:
    """Return (exe_used, raw_stdout, note). Absence is reported, not assumed."""
    if simulate_absent:
        return None, "", "SIMULATED: nvidia-smi treated as absent (--no-smi-on-path)"
    for cand in SMI_CANDIDATES:
        if cand != "nvidia-smi" and not os.path.isfile(cand):
            continue
        rc, out = run_capture([cand, "--query-gpu=name,memory.total,memory.free",
                               "--format=csv,noheader,nounits"])
        if rc == 0 and out and "not found" not in out.lower():
            return cand, out, f"rc=0 via {cand}"
        if rc == 127:
            continue  # try the next location
    return None, "", "no working nvidia-smi at any known location"


def probe_cuda_gpu(simulate_absent: bool) -> dict:
    """Capability: is there a usable NVIDIA CUDA GPU, and how much VRAM is free?

    The verdict is built by CROSS-CHECKING independent methods and then
    PERFORMING an allocation. Disagreement between methods is reported as
    disagreement, never silently averaged.
    """
    hr("CAPABILITY: CUDA / NVIDIA GPU")
    hints: dict = {}
    methods_ok: list[str] = []
    discrepancies: list[str] = []

    # --- method A: nvidia-smi (subprocess) ---
    exe, smi_out, smi_note = find_and_run_smi(simulate_absent)
    hints["nvidia_smi"] = {"exe": exe, "note": smi_note, "raw": smi_out}
    if exe and smi_out:
        methods_ok.append("nvidia-smi")
        print(f"  nvidia-smi  : {exe}")
        for line in smi_out.splitlines():
            print(f"    | {line}")
    else:
        print(f"  nvidia-smi  : NOT USABLE -- {smi_note}")
        print("    (NOT treated as 'no GPU': the device may still be present)")

    # --- method B: NVML via pynvml -- the same source nvidia-smi reads ---
    nvml_total = nvml_free = None
    try:
        import pynvml  # type: ignore

        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        devs = []
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode("utf-8", "replace")
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            devs.append({"index": i, "name": name,
                         "total_mib": round(mem.total / 2**20, 1),
                         "free_mib": round(mem.free / 2**20, 1)})
            if i == 0:
                nvml_total, nvml_free = mem.total, mem.free
        hints["pynvml"] = devs
        if devs:
            methods_ok.append("pynvml(NVML)")
            print(f"  pynvml/NVML : {len(devs)} device(s)")
            for d in devs:
                print(f"    | #{d['index']} {d['name']} total={d['total_mib']} MiB "
                      f"free={d['free_mib']} MiB")
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        hints["pynvml"] = f"{type(exc).__name__}: {exc}"
        print(f"  pynvml/NVML : unavailable ({type(exc).__name__})")

    # --- method C: torch.cuda -- a DIFFERENT runtime, so a real cross-check ---
    torch_info = None
    try:
        import torch  # type: ignore

        av = torch.cuda.is_available()
        print(f"  torch       : version={torch.__version__} is_available()={av}  [HINT]")
        if av:
            free_b, total_b = torch.cuda.mem_get_info(0)
            torch_info = {"is_available": True,
                          "free_mib": round(free_b / 2**20, 1),
                          "total_mib": round(total_b / 2**20, 1),
                          "device_name": torch.cuda.get_device_name(0),
                          "torch_version": torch.__version__}
            methods_ok.append("torch.cuda")
            print(f"    | mem_get_info #0 free={torch_info['free_mib']} MiB "
                  f"total={torch_info['total_mib']} MiB")
            # PERFORM the capability -- a query is not evidence.
            try:
                t = torch.zeros(1, device="cuda")
                allocated = torch.cuda.memory_allocated()
                del t
                torch_info["allocation_ok"] = True
                torch_info["memory_allocated_bytes"] = int(allocated)
                print(f"    | ALLOCATION PERFORMED: torch.zeros(1, device='cuda') OK, "
                      f"memory_allocated={allocated} B")
            except Exception as exc:  # noqa: BLE001
                torch_info["allocation_ok"] = False
                torch_info["allocation_error"] = f"{type(exc).__name__}: {exc}"
                discrepancies.append(f"torch says CUDA available but allocation FAILED: {exc}")
                print(f"    | ALLOCATION FAILED: {type(exc).__name__}: {exc}")
            if os.environ.get("SOTTO_PROBE_SIMULATE_TORCH_OOM") == "1":
                # Robustness self-test: the query says YES, the allocation says NO.
                # This is the documented disagreement (WDDM/TDR, MIG, fragmentation):
                # the right answer is to report it and fall back, never to crash.
                torch_info["allocation_ok"] = False
                torch_info["allocation_error"] = (
                    "SIMULATED OutOfMemoryError (SOTTO_PROBE_SIMULATE_TORCH_OOM=1): "
                    "the query said CUDA was available and the allocation refused")
                torch_info["simulated"] = True
                discrepancies.append(
                    "SIMULATED: torch.cuda.is_available()=True but the allocation was refused")
                print("    | ALLOCATION SIMULATED-FAILED (robustness self-test armed)")
        else:
            torch_info = {"is_available": False, "torch_version": torch.__version__}
    except Exception as exc:  # noqa: BLE001
        torch_info = {"error": f"{type(exc).__name__}: {exc}"}
        print(f"  torch       : unavailable ({type(exc).__name__})")
    hints["torch"] = torch_info

    # --- method D: DXGI AdapterRAM trap -- the classic FALSE reading ---
    vram_trap = probe_wmi_adapterram()
    hints["wmi_adapterram_trap"] = vram_trap

    # --- the OOM honesty test: does allocation FAIL loudly, or crash? ---
    oom = probe_oom_honesty()
    hints["oom_probe"] = oom

    # ---- reconcile ----
    # Compare TOTAL capacity as the authoritative cross-check. TOTAL is a stable
    # property of the device; "free" is a live value that different runtimes
    # snapshot at different moments and account for differently (measured here:
    # nvidia-smi 16303 MiB total vs torch 16275 MiB, a 0.17% gap from CUDA's own
    # reservation, while free differed by 2.1 GiB partly because NVML and the
    # CUDA context sample at different instants).
    #
    # A free-memory gap is therefore NOT a discrepancy and must not raise a
    # false alarm -- but free is the number the feature's budget depends on, so
    # it is reported and the MOST CONSERVATIVE reading is what the gate uses.
    free_mib = None
    source = None
    note_free = []
    for cand, val in (("nvidia-smi", _free_from_smi(smi_out)),
                      ("pynvml", nvml_free / 2**20 if nvml_free else None),
                      ("torch", torch_info.get("free_mib") if torch_info else None)):
        if val:
            note_free.append((cand, val))
            if free_mib is None or val < free_mib:
                free_mib, source = val, cand  # conservative = smallest claim

    totals = []
    tot_smi = _total_from_smi(smi_out)
    if tot_smi:
        totals.append(("nvidia-smi", tot_smi))
    if nvml_total:
        totals.append(("pynvml", nvml_total / 2**20))
    if torch_info and torch_info.get("total_mib"):
        totals.append(("torch", torch_info["total_mib"]))
    if len(totals) >= 2:
        vals = [v for _n, v in totals]
        spread = (max(vals) - min(vals)) / max(vals) * 100.0
        if spread > 2.0:
            discrepancies.append(
                "VRAM TOTAL disagrees by "
                f"{spread:.1f}%: " + ", ".join(f"{n}={v:.0f} MiB" for n, v in totals))

    free_note = ""
    if len(note_free) >= 2:
        vals = [v for _n, v in note_free]
        if (max(vals) - min(vals)) > 512:
            free_note = ("free VRAM varies by method (live value, not a defect): "
                         + ", ".join(f"{n}={v:.0f} MiB" for n, v in note_free)
                         + f" -- gate uses the most conservative: {free_mib:.0f} MiB from {source}")
            print(f"  NOTE: {free_note}")

    if not methods_ok:
        return rec("cuda_gpu", VERDICT_UNAVAILABLE, "nvidia-smi|pynvml|torch (all methods)",
                   hints, "measured",
                   "no CUDA detection method produced a device: "
                   f"nvidia-smi {smi_note}; pynvml and torch also reported nothing")

    if discrepancies:
        return rec("cuda_gpu", VERDICT_DEGRADED,
                   "+".join(methods_ok) + " (methods DISAGREE)",
                   dict(hints, discrepancies=discrepancies,
                        vram_free_mib=round(free_mib, 1) if free_mib else None,
                        vram_free_source=source,
                        vram_free_is_conservative=True,
                        vram_total_mib=totals,
                        free_memory_note=free_note), "measured",
                   "; ".join(discrepancies))
    return rec("cuda_gpu", VERDICT_OK, "+".join(methods_ok) + " (cross-checked)",
               dict(hints, vram_free_mib=round(free_mib, 1) if free_mib else None,
                    vram_free_source=source,
                    vram_free_is_conservative=True,
                    vram_total_mib=totals,
                    free_memory_note=free_note), "measured", "")


def _total_from_smi(raw: str):
    for line in (raw or "").splitlines():
        cells = [c.strip() for c in line.split(",")]
        if len(cells) >= 2:
            try:
                return float(cells[1])
            except ValueError:
                continue
    return None


def _free_from_smi(raw: str):
    for line in (raw or "").splitlines():
        cells = [c.strip() for c in line.split(",")]
        if len(cells) >= 3:
            try:
                return float(cells[2])
            except ValueError:
                continue
    return None


def probe_wmi_adapterram() -> dict:
    """Win32_VideoController.AdapterRAM is a uint32 and WRAPS above 4 GB.

    It is recorded here ONLY to demonstrate the trap, never to decide anything:
    a 16 GB RTX 5080 can report 4096 MiB, and an 8 GB card can report less than
    a 4 GB one. Sources:
      https://github.com/Mesh-LLM/mesh-llm/issues/1811
      https://github.com/AlexsJones/llmfit/pull/831
    """
    rc, out = run_capture([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Get-CimInstance Win32_VideoController | ForEach-Object "
        "{ \"$($_.Name)|$($_.AdapterRAM)|$($_.PNPDeviceID)\" }",
    ])
    rows = []
    if rc == 0 and out:
        for line in out.splitlines():
            if line.strip():
                parts = line.split("|")
                name = parts[0] if parts else "?"
                ram = parts[1] if len(parts) > 1 else ""
                rows.append({"name": name, "AdapterRAM_raw": ram})
    wrapped = [r for r in rows if r["AdapterRAM_raw"].isdigit()
               and int(r["AdapterRAM_raw"]) >= 4293918720]
    return {"method": "Win32_VideoController.AdapterRAM",
            "trust": "FORBIDDEN as a VRAM reading -- uint32 wraps above 4 GB",
            "rows": rows,
            "rows_showing_the_wrap": [r["name"] for r in wrapped]}


def probe_oom_honesty() -> dict:
    """Does the capability fail CLEANLY when the request does not fit?

    "Query says yes" and "allocation succeeds" are different claims, and the gap
    between them is one of the documented failure modes (WDDM lets a CUDA context
    over-commit into shared system memory, so a small overshoot can appear to
    succeed and then thrash the whole box). The honest test must therefore be
    bounded and must not touch the driver's over-commit path.

    Method: cap the torch caching allocator to a known fraction
    (`set_per_process_memory_fraction`) and then ask for MORE than the cap. That
    forces the OOM inside the allocator, deterministically, with no driver
    over-commit, no pagefile thrash and no unbounded wait.

    MEASURED LESSON: the first version of this probe asked the driver for a flat
    64 GiB and had to be killed -- it thrashed the machine instead of failing.
    A probe that can take down the box it measures is not a probe. Hence the cap.
    """
    out: dict = {"method": "oversized request inside a capped caching allocator"}
    try:
        import torch  # type: ignore

        if not torch.cuda.is_available():
            out["result"] = "skipped: torch.cuda not available"
            return out

        free_b, total_b = torch.cuda.mem_get_info(0)
        cap_fraction = 0.10
        torch.cuda.set_per_process_memory_fraction(cap_fraction, 0)
        cap_b = total_b * cap_fraction
        # Ask for 4x the cap: guaranteed to fail inside the allocator, and the
        # requested size (≈6.4 GiB on a 16 GiB card) is far below the ~64 GiB
        # that caused driver over-commit.
        ask_b = int(cap_b * 4)
        out.update({"cap_fraction": cap_fraction, "cap_gib": round(cap_b / 2**30, 2),
                    "asked_gib": round(ask_b / 2**30, 2),
                    "free_gib_before": round(free_b / 2**30, 2)})
        t0 = time.perf_counter()
        try:
            t = torch.zeros(ask_b // 4, dtype=torch.float32, device="cuda")
            out["result"] = ("UNEXPECTED: the oversized request SUCCEEDED inside a "
                             "capped allocator -- the cap was not honoured")
            del t
        except Exception as exc:  # noqa: BLE001
            dt = time.perf_counter() - t0
            out["result"] = "OOM raised cleanly (this is the CORRECT behaviour)"
            out["exception_type"] = type(exc).__name__
            out["exception_text"] = str(exc)[:220]
            out["failed_after_seconds"] = round(dt, 3)
            try:
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                free_after, _ = torch.cuda.mem_get_info(0)
                out["recovered"] = True
                out["free_gib_after"] = round(free_after / 2**30, 2)
            except Exception as exc2:  # noqa: BLE001
                out["recovered"] = False
                out["recovery_error"] = str(exc2)[:200]
        finally:
            try:
                torch.cuda.set_per_process_memory_fraction(1.0, 0)
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001
        out["result"] = f"probe itself failed: {type(exc).__name__}: {exc}"
    print()
    print("  OOM honesty probe (bounded, does not touch driver over-commit):")
    for k, v in out.items():
        print(f"    {k}: {v}")
    return out


# ===========================================================================
# ORT execution providers -- the runtime the live ASR model already uses
# ===========================================================================

def probe_ort_providers() -> dict:
    hr("CAPABILITY: ONNX Runtime execution providers (what the stack ALREADY uses)")
    hints: dict = {}
    try:
        import onnxruntime as ort
    except Exception as exc:  # noqa: BLE001
        print(f"  onnxruntime import FAILED: {exc}")
        return rec("ort_runtime", VERDICT_UNAVAILABLE, "import onnxruntime",
                   {"error": f"{type(exc).__name__}: {exc}"}, "measured", str(exc))

    hints["version"] = ort.__version__
    advertised = list(ort.get_available_providers())
    try:
        hints["get_device_hint"] = ort.get_device()
    except Exception:
        hints["get_device_hint"] = None
    print(f"  onnxruntime {ort.__version__}")
    print(f"    get_available_providers() = {advertised}   [HINT, not a verdict]")
    print(f"    get_device()              = {hints['get_device_hint']}   [HINT]")

    # PERFORM the capability for each provider: ask for it, then read back which
    # provider the SESSION actually bound.
    per_provider: dict = {}
    for prov in ("CUDAExecutionProvider", "TensorrtExecutionProvider",
                 "DmlExecutionProvider", "CPUExecutionProvider"):
        if prov not in advertised:
            per_provider[prov] = {"advertised": False, "bound": False,
                                  "note": "not advertised by this wheel"}
            continue
        bound, err = _try_session_on(ort, prov)
        per_provider[prov] = {"advertised": True, "bound": bound, "error": err}
        print(f"    {prov:<28} advertised=YES  SESSION BOUND={'YES' if bound else 'NO '}"
              + (f"  ({err[:90]})" if err and not bound else ""))
    force_utf8_stdout()

    hints["providers"] = per_provider
    cuda_bound = per_provider.get("CUDAExecutionProvider", {}).get("bound", False)
    cpu_bound = per_provider.get("CPUExecutionProvider", {}).get("bound", False)

    if cuda_bound:
        return rec("ort_runtime", VERDICT_OK, "request provider + read back session's bound providers",
                   hints, "measured", "")
    err = per_provider.get("CUDAExecutionProvider", {}).get("error", "")
    return rec("ort_runtime",
               VERDICT_DEGRADED if cpu_bound else VERDICT_UNAVAILABLE,
               "request provider + read back session's bound providers", hints, "measured",
               f"CUDAExecutionProvider is ADVERTISED but does not bind; session fell back to CPU. "
               f"Root cause: {err[:400]}")


def _try_session_on(ort, provider: str) -> tuple[bool, str]:
    """Build a tiny graph, force one provider, return what the session really got."""
    try:
        import numpy as np
        from onnx import TensorProto, helper

        node = helper.make_node("Add", ["x", "y"], ["z"])
        graph = helper.make_graph(
            [node], "probe",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [2]),
             helper.make_tensor_value_info("y", TensorProto.FLOAT, [2])],
            [helper.make_tensor_value_info("z", TensorProto.FLOAT, [2])],
        )
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
        sess = ort.InferenceSession(model.SerializeToString(), providers=[provider])
        bound = list(sess.get_providers())
        sess.run(None, {"x": np.array([1.0, 2.0], np.float32),
                        "y": np.array([3.0, 4.0], np.float32)})
        ok = bound[:1] == [provider]
        return ok, "" if ok else f"session bound {bound} instead"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


# ===========================================================================
# CPU + SIMD, verified by PERFORMING a vectorised op
# ===========================================================================

def probe_cpu() -> dict:
    hr("CAPABILITY: CPU (cores, SIMD)")
    import platform

    name = platform.processor() or "UNKNOWN"
    rc, out = run_capture([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name",
    ])
    if rc == 0 and out.strip():
        name = out.strip()
    rc2, cores = run_capture([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "$c = Get-CimInstance Win32_Processor | Select-Object -First 1; "
        "\"$($c.NumberOfCores);$($c.NumberOfLogicalProcessors)\"",
    ])
    phys = logi = 0
    if rc2 == 0 and cores:
        parts = cores.strip().split(";")
        if len(parts) >= 2:
            try:
                phys, logi = int(parts[0]), int(parts[1])
            except ValueError:
                phys = logi = 0
    if not logi:
        # os.cpu_count() is the LOGICAL count and is always available; degrade to
        # it rather than reporting zero, because a zero core count would flip the
        # gate to "unavailable" on a perfectly capable machine.
        logi = os.cpu_count() or 0
    if not phys:
        # No WMI physical count: assume SMT-2, the overwhelmingly common case.
        phys = max(1, logi // 2) if logi else 0
        phys_source = "DERIVED as logical/2 (WMI unavailable)"
    else:
        phys_source = "WMI Win32_Processor.NumberOfCores"

    # SIMD: a feature FLAG, then a PERFORMED op whose timing proves a wide path.
    flags = {}
    try:
        PF_AVX2_INSTRUCTION_AVAILABLE = 40  # IsProcessorFeaturePresent(PF_AVX2...)
        k32 = ctypes.windll.kernel32
        flags["IsProcessorFeaturePresent(40)=AVX2"] = bool(
            k32.IsProcessorFeaturePresent(PF_AVX2_INSTRUCTION_AVAILABLE))
    except Exception as exc:  # noqa: BLE001
        flags["IsProcessorFeaturePresent(40)=AVX2"] = f"error: {exc}"

    simd_perf = None
    try:
        import numpy as np

        # Build numpy from source in a way that reports its SIMD baseline, then
        # PERFORM a float32 matmul -- a scalar-only build is dramatically slower.
        try:
            show = np.show_config  # noqa: F841
        except Exception:
            pass
        a = np.random.rand(512, 512).astype(np.float32)
        b = np.random.rand(512, 512).astype(np.float32)
        a @ b  # warm up
        t0 = time.perf_counter()
        for _ in range(3):
            a @ b
        dt = (time.perf_counter() - t0) / 3.0
        gflops = (2 * 512**3) / dt / 1e9
        simd_perf = {"matmul_512x512_float32_ms": round(dt * 1000, 3),
                     "derived_gflops": round(gflops, 2)}
    except Exception as exc:  # noqa: BLE001
        simd_perf = {"error": f"{type(exc).__name__}: {exc}"}

    print(f"  CPU model        : {name}")
    print(f"  physical/logical : {phys} / {logi}  ({phys_source})")
    print(f"  AVX2 feature flag: {flags.get('IsProcessorFeaturePresent(40)=AVX2')}  [HINT]")
    print(f"  PERFORMED matmul : {simd_perf}")

    # The PERFORMED op is the evidence; the flag is only a hint. Calibrate PER
    # CORE, because absolute GFLOPS depends on core count and on what else is
    # running (the owner's ASR worker holds a core while this probe runs).
    #
    # DELIBERATELY CONSERVATIVE FLOORS: a false NEGATIVE denies the feature to a
    # capable machine, so "unavailable" is set at scalar-only performance
    # (well under 1 GFLOPS/core) -- NOT at "slower than I hoped".
    per_core = None
    if simd_perf and simd_perf.get("derived_gflops") and phys:
        per_core = simd_perf["derived_gflops"] / phys

    verdict = VERDICT_OK
    reason = ""
    if not phys or not logi:
        verdict = VERDICT_UNKNOWN
        reason = "core counts not obtainable from WMI or the OS"
    elif per_core is None:
        verdict = VERDICT_UNKNOWN
        reason = "the performed matmul did not produce a usable throughput number"
    elif per_core < 0.5:
        verdict = VERDICT_UNAVAILABLE
        reason = (f"measured {per_core:.2f} GFLOPS/physical-core: scalar-only performance, "
                  "i.e. the vectorised path is NOT being used")
    elif per_core < 2.0:
        verdict = VERDICT_DEGRADED
        reason = (f"measured {per_core:.2f} GFLOPS/physical-core -- usable for a small model, "
                  "but CPU-only latency will be slow")

    if per_core:
        print(f"  GFLOPS/physical-core: {per_core:.2f}")
    return rec("cpu", verdict,
               "WMI core counts + PERFORMED float32 matmul, calibrated per physical core",
               {"model": name, "physical_cores": phys, "logical_cores": logi,
                "core_source": phys_source,
                "os_cpu_count": os.cpu_count(),
                "simd_flags_hint": flags, "simd_performance": simd_perf,
                "gflops_per_physical_core": round(per_core, 2) if per_core else None,
                "floors": {"unavailable_below": 0.5, "degraded_below": 2.0,
                           "units": "GFLOPS per physical core"}},
               "measured", reason)


def probe_ram() -> dict:
    hr("CAPABILITY: system RAM")
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.wintypes.DWORD),
                    ("dwMemoryLoad", ctypes.wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ok = bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)))
    if not ok:
        return rec("ram", VERDICT_UNKNOWN, "GlobalMemoryStatusEx",
                   {"error": "GlobalMemoryStatusEx failed"}, "measured",
                   "the RAM API refused")
    ev = {"total_gib": round(st.ullTotalPhys / 2**30, 2),
          "available_gib": round(st.ullAvailPhys / 2**30, 2),
          "load_percent": st.dwMemoryLoad,
          "commit_limit_gib": round(st.ullTotalPageFile / 2**30, 2)}
    print(f"  total {ev['total_gib']} GiB  available {ev['available_gib']} GiB  "
          f"load {ev['load_percent']}%")
    verdict = VERDICT_OK
    reason = ""
    if ev["available_gib"] < 4:
        verdict = VERDICT_UNAVAILABLE
        reason = f"only {ev['available_gib']} GiB free right now: a 4B int4 model needs ~3 GiB"
    elif ev["available_gib"] < 8:
        verdict = VERDICT_DEGRADED
        reason = f"{ev['available_gib']} GiB free: room for a small model only, no headroom"
    return rec("ram", verdict, "GlobalMemoryStatusEx (Win32)", ev, "measured", reason)


# ===========================================================================
# THE GATE -- tiering table + the weak-PC path
# ===========================================================================

# Measured/derived model footprints (GiB of WEIGHTS, at load time).
TIERS = [
    # (min_free_vram_gib, model, why)
    (10.0, "Qwen3.5-9B (int4, ~5.5 GiB) or Qwen3.5-4B (int4, ~2.5 GiB)", "comfortable headroom; 9B fits fully on device"),
    (4.0,  "Qwen3.5-4B (int4, ~2.5 GiB)", "one quantised 4B model fits with room for KV cache"),
    (2.0,  "Qwen3.5-2B (int4, ~1.3 GiB)", "small model only; short summaries"),
    (0.0,  "Qwen3.5-0.8B (int4, ~0.6 GiB)", "last GPU-resident option"),
]


def decide_gate(records: dict) -> dict:
    """Turn the capability records into ONE gate verdict + a human reason.

    TWO DIFFERENT QUESTIONS, kept apart on purpose because conflating them
    produced a false NEGATIVE on this very box:

      Q1 "Is there a GPU we could compute on?"   -> torch.cuda / nvidia-smi
      Q2 "Will the feature's own runtime use it?" -> an ORT provider BINDS

    On this machine Q1=yes and Q2=no (ORT 1.30 wants CUDA 13 DLLs, the box has
    CUDA 12.8). The feature is an ONNX Runtime GenAI job, so Q2 decides the TIER
    -- but Q1 still decides whether a GPU exists at all, and a CPU path remains
    available, so the correct answer is "available on CPU now, GPU after a
    one-line DLL install", never "unavailable".

    Fail-closed on the DOWNLOAD question: `unavailable` permits nothing.
    """
    gpu = records.get("cuda_gpu", {})
    ort = records.get("ort_runtime", {})
    cpu = records.get("cpu", {})
    ram = records.get("ram", {})

    ev_gpu = gpu.get("evidence") or {}
    # Read the VRAM figure REGARDLESS of the gpu verdict: a `degraded` verdict
    # can be caused by an allocation disagreement while the device and its free
    # memory are perfectly real. Gating this on verdict=="ok" made the reason
    # string say "vram_free=0.0 GiB" on a box with 11 GiB free -- a misleading
    # zero that could tip a borderline machine to a false "unavailable".
    free_mib = float(ev_gpu.get("vram_free_mib") or 0.0)
    free_gib = free_mib / 1024.0
    ev_ram = ram.get("evidence") or {}
    ram_free = float(ev_ram.get("available_gib") or 0.0)
    ev_cpu = cpu.get("evidence") or {}
    cores = int(ev_cpu.get("physical_cores") or 0)

    providers = (ort.get("evidence") or {}).get("providers", {})
    ort_gpu_bound = any(providers.get(p, {}).get("bound")
                        for p in ("CUDAExecutionProvider", "TensorrtExecutionProvider",
                                  "DmlExecutionProvider"))
    torch_cuda = bool((ev_gpu.get("torch") or {}).get("allocation_ok"))

    # Which tier can actually RUN, using the runtime the feature really uses.
    if ort_gpu_bound and free_gib >= 10.0:
        path, compute = "gpu-high", "ort-gpu"
    elif ort_gpu_bound and free_gib >= 4.0:
        path, compute = "gpu-mid", "ort-gpu"
    elif ort_gpu_bound and free_gib >= 2.0:
        path, compute = "gpu-low", "ort-gpu"
    elif ram_free >= 12.0 and cores >= 8:
        path, compute = "cpu-only-adequate", "ort-cpu"
    elif ram_free >= 6.0 and cores >= 4:
        path, compute = "cpu-only-marginal", "ort-cpu"
    else:
        path, compute = "unavailable", "none"

    available = path != "unavailable"
    # The honest tier: a GPU EXISTS but the feature's runtime cannot use it yet.
    gpu_exists_but_unusable = bool(torch_cuda) and not ort_gpu_bound

    if available:
        model = ("Qwen3.5-9B int4" if path == "gpu-high"
                 else "Qwen3.5-4B int4" if path.startswith("gpu")
                 else "Qwen3.5-2B int4 (CPU)" if path == "cpu-only-adequate"
                 else "Qwen3.5-0.8B int4 (CPU)")
        reason = (f"{path} via {compute}: ort_gpu_provider_bound={ort_gpu_bound}, "
                  f"torch_cuda_usable={torch_cuda}, vram_free={free_gib:.1f} GiB, "
                  f"ram_free={ram_free:.1f} GiB, physical_cores={cores}")
        if gpu_exists_but_unusable:
            reason += ("; NOTE: a usable CUDA GPU EXISTS (torch allocated on it) but ONNX "
                       "Runtime cannot bind it, so the GPU tier is withheld until the ORT "
                       "CUDA 13 / cuDNN 9 dependency is installed")
    else:
        model = None
        reason = ("no usable ONNX Runtime provider and free RAM/cores below the floor: "
                  f"vram_free={free_gib:.1f} GiB, ram_free={ram_free:.1f} GiB, "
                  f"physical_cores={cores}")

    return {"path": path, "available": available, "compute": compute,
            "recommended_model": model, "reason": reason,
            "downloads_permitted": bool(available),
            "gpu_exists_but_runtime_cannot_use_it": gpu_exists_but_unusable,
            "questions": {
                "q1_gpu_exists": bool(torch_cuda or free_mib > 0),
                "q2_feature_runtime_uses_gpu": bool(ort_gpu_bound),
            },
            "tiers_considered": [{"min_free_vram_gib": t[0], "model": t[1], "why": t[2]}
                                 for t in TIERS],
            "inputs": {"vram_free_gib": round(free_gib, 2),
                       "ram_free_gib": round(ram_free, 2),
                       "physical_cores": cores,
                       "ort_gpu_provider_bound": ort_gpu_bound,
                       "torch_cuda_allocation_ok": torch_cuda}}


def main() -> int:
    simulate_absent = "--no-smi-on-path" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    default_log = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "_qwen-hw-probe.log")
    tee = Report(args[0] if args else default_log)
    sys.stdout = tee  # type: ignore[assignment]

    print("SOTTO -- QWEN HOURLY FEATURE: CAPABILITY GATE PROBE")
    print(f"python {sys.version.split()[0]}  ({sys.executable})")
    print(f"host {os.environ.get('COMPUTERNAME', '?')}  "
          f"at {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    if simulate_absent:
        print("MODE: --no-smi-on-path (robustness self-test: nvidia-smi simulated ABSENT)")
    print("read-only: no downloads, no installs, no audio device, no window")
    print()
    print("RULE: a capability QUERY is not evidence; only PERFORMING it is. "
          "Queries are labelled [HINT].")

    records: dict = {}
    for fn in (lambda: probe_cuda_gpu(simulate_absent),
               probe_ort_providers, probe_cpu, probe_ram):
        try:
            r = fn()
        except Exception as exc:  # noqa: BLE001
            r = rec(getattr(fn, "__name__", "unknown"), VERDICT_UNKNOWN, "probe crashed",
                    {"error": f"{type(exc).__name__}: {exc}"}, "measured", str(exc))
        records[r["capability"]] = r
        print()
        show(r)

    hr("GATE DECISION")
    gate = decide_gate(records)
    print(f"  path                 : {gate['path']}")
    print(f"  available            : {gate['available']}")
    print(f"  recommended model    : {gate['recommended_model']}")
    print(f"  DOWNLOADS PERMITTED  : {gate['downloads_permitted']}")
    print(f"  reason               : {gate['reason']}")
    print()
    print("  tiering table (min free VRAM -> allowed model):")
    for t in gate["tiers_considered"]:
        print(f"    >= {t['min_free_vram_gib']:>4} GiB  {t['model']:<52} {t['why']}")

    payload = {"probe": "sotto-qwen-capability-gate",
               "simulated": {"no_smi_on_path": simulate_absent},
               "records": records, "gate": gate}
    print()
    print("  ---- JSON ----")
    print(json.dumps(payload, indent=2, default=str))
    force_utf8_stdout()
    tee.close()
    sys.stdout = tee._orig  # type: ignore[assignment]
    return 0


if __name__ == "__main__":
    sys.exit(main())
