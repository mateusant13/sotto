"""VRAM RESIDENCY - what is on the GPU right now, measured in-process.

This module launches nothing. It reads the two sources that answer who is using
the GPU and how much, both from inside this process:

  * NVML (pynvml)  - device totals (total/used/free), driver, and the pids that
                     hold a CUDA context.
  * PDH (win32pdh) - PER-PROCESS dedicated/shared GPU memory.

WHY PDH AND NOT nvidia-smi OR nvmlDeviceGetComputeRunningProcesses (measured
here, 2026-10-12, RTX 5080, driver 617.14):

  * "nvidia-smi --query-compute-apps=pid,used_memory" -> "Failed to initialize
    NVML: Unknown Error" from this box shells, and "[N/A]" for used_memory in
    the Lead session. Unusable.
  * nvmlDeviceGetComputeRunningProcesses_v2 LISTS the pids (it sees 28 of them)
    but reports usedGpuMemory == 0 for every one. On Windows/WDDM the driver
    does not publish per-process bytes through NVML. Measured, not assumed.
  * The Windows performance-counter object "GPU Process Memory" DOES answer it:
    win32pdh + a wildcard query + GetFormattedCounterArray returns
    {instance_name: bytes}, the instance name carries the pid, and the numbers
    agree with PowerShell Get-Counter on the same object (cross-checked
    2026-10-12: pid 10056 -> 81485824 B in both).

CAVEAT, stated rather than hidden: PDH "Dedicated Usage" is the driver
per-process DEDICATED allocation; NVML "used" is a device-wide counter, and the
two do NOT sum to the same total (measured 2026-10-12: PDH ded sum 8531.6 MiB
vs NVML used 5513 MiB). Both are reported; neither is described as the other.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import time

try:  # evidence of the import path, not a dependency claim
    import pynvml as _nvml
except Exception:  # the box HAS pynvml 11.4.1 (measured)
    _nvml = None

try:
    import win32pdh as _pdh
except Exception:  # the box HAS pywin32 (measured)
    _pdh = None

try:
    import psutil as _psutil
except Exception:
    _psutil = None

MIB = 1048576.0
BS = chr(92)          # one backslash, built so this source has none literal
APOS = chr(39)        # one apostrophe, ditto
_PDH_GPU_OBJECT = "GPU Process Memory"
_PDH_COUNTERS = {
    "ded": "Dedicated Usage",      # VRAM the process owns exclusively
    "shr": "Shared Usage",         # VRAM shared with other processes
    "tot": "Total Committed",       # the process total GPU commit
}
_SOTTO_WORKER = "sotto_worker.py"


# --------------------------------------------------------------------------
# the two measurement sources
# --------------------------------------------------------------------------
def pdh_counter(counter_name):
    """{instance_name: bytes} for one GPU Process Memory counter.

    In-process, no subprocess. The wildcard path form is the ONLY one that works
    on this box: addressing the object by computer name returns
    PDH_CSTATUS_NO_OBJECT (O objeto especificado nao foi encontrado no computador)
    and a per-instance multi-counter query dies with Nao ha dados a serem
    retornados. Both measured 2026-10-12.
    """
    if _pdh is None:
        raise RuntimeError("win32pdh (pywin32) is not importable on this box")
    path = BS + _PDH_GPU_OBJECT + "(*)" + BS + counter_name
    q = _pdh.OpenQuery(None, 0)
    try:
        h = _pdh.AddCounter(q, path, None)
        # TWO collects with a settle between: on this box one collect answers
        # "Nao ha dados a serem retornados" (measured 2026-10-12) and the second,
        # a second later, returns the instances.
        last = None
        for i in range(3):
            try:
                _pdh.CollectQueryData(q)
                if i >= 1:
                    break
                time.sleep(1.0)
            except Exception as exc:
                last = exc
                time.sleep(1.0)
        else:
            raise RuntimeError("CollectQueryData never yielded data for "
                               + counter_name + ": " + str(last))
        return dict(_pdh.GetFormattedCounterArray(h, _pdh.PDH_FMT_LARGE))
    finally:
        try:
            _pdh.CloseQuery(q)
        except Exception:
            pass


def pdh_snapshot():
    """{pid: {ded_MiB, shr_MiB, tot_MiB, instances}}.

    Sums EVERY instance of a pid: one process can appear under several luid
    values (measured: pid 11504 twice, pid 13176 twice, pid 18840 twice).
    Instance names look like pid_123_luid_0x00000000_0x000140D8_phys_0, so the
    pid and the physical adapter are split out by underscore, no regex needed.
    """
    out = {}
    for key, cname in _PDH_COUNTERS.items():
        try:
            vals = pdh_counter(cname)
        except Exception as exc:
            out["err_" + key] = str(exc)
            continue
        for inst, nbytes in vals.items():
            parts = inst.split("_")
            # pid_<n>_luid_0x..._0x..._phys_<m>
            if len(parts) < 6 or parts[0] != "pid" or parts[-2] != "phys":
                continue
            try:
                pid = int(parts[1])
                phys = int(parts[-1])
            except ValueError:
                continue
            rec = out.setdefault(pid, {"ded_MiB": 0.0, "shr_MiB": 0.0,
                                      "tot_MiB": 0.0, "instances": 0})
            rec[key + "_MiB"] = rec.get(key + "_MiB", 0.0) + (nbytes or 0) / MIB
            rec["instances"] += 1
            rec["phys"] = phys
    return out


def device_totals():
    """NVML device memory totals + the pids that hold a CUDA context."""
    if _nvml is None:
        raise RuntimeError("pynvml is not importable on this box")
    _nvml.nvmlInit()
    try:
        devs = []
        for i in range(_nvml.nvmlDeviceGetCount()):
            h = _nvml.nvmlDeviceGetHandleByIndex(i)
            m = _nvml.nvmlDeviceGetMemoryInfo(h)
            try:
                comp = [p.pid for p in _nvml.nvmlDeviceGetComputeRunningProcesses_v2(h)]
            except Exception:
                comp = []
            devs.append({
                "index": i,
                "name": _nvml.nvmlDeviceGetName(h).decode(errors="replace"),
                "total_MiB": m.total // MIB,
                "used_MiB": m.used // MIB,
                "free_MiB": m.free // MIB,
                "compute_pids": comp,
            })
        return {
            "driver": _nvml.nvmlSystemGetDriverVersion().decode(errors="replace"),
            "devices": devs,
        }
    finally:
        try:
            _nvml.nvmlShutdown()
        except Exception:
            pass


def process_label(pid):
    """(name, cmdline) for a pid, or (None, None) when it is gone/private."""
    if _psutil is not None:
        try:
            p = _psutil.Process(pid)
            return p.name(), " ".join(p.cmdline() or [])
        except Exception:
            return None, None
    return None, None


def per_process_vram(min_mib=0.0):
    """Per-process GPU memory, biggest first. Pure measurement."""
    snap = pdh_snapshot()
    rows = []
    for pid, rec in snap.items():
        if not isinstance(pid, int):
            continue
        name, cmdline = process_label(pid)
        rows.append({
            "pid": pid,
            "name": name,
            "cmdline": cmdline,
            "ded_MiB": round(rec.get("ded_MiB", 0.0), 1),
            "shr_MiB": round(rec.get("shr_MiB", 0.0), 1),
            "tot_MiB": round(rec.get("tot_MiB", 0.0), 1),
            "instances": rec.get("instances", 0),
        })
    rows = [r for r in rows if r["ded_MiB"] >= min_mib or r["shr_MiB"] >= min_mib]
    rows.sort(key=lambda r: (-r["ded_MiB"], -r["tot_MiB"]))
    return rows


# --------------------------------------------------------------------------
# model identity + foreign-holder detection
# --------------------------------------------------------------------------
#: Weight files that ARE the model. Everything else in an export dir is a
#: header, a config or a tokenizer and is not what costs VRAM.
WEIGHT_SUFFIXES = (".onnx.data", ".onnx", ".safetensors", ".pt", ".bin", ".gguf")


def weight_files(model_dir):
    """([(filename, bytes)], error-or-None) for the weight files present, sorted."""
    out = []
    try:
        names = sorted(os.listdir(model_dir))
    except OSError as exc:
        return out, str(exc)
    for n in names:
        p = os.path.join(model_dir, n)
        try:
            if os.path.isfile(p) and n.endswith(WEIGHT_SUFFIXES):
                out.append((n, os.path.getsize(p)))
        except OSError:
            continue
    return out, None


def _sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def model_identity(model_dir, hash_weights=True):
    """What makes THIS model THIS model.

    Identity is the set of weight files and their digests. Two directories with
    the same weights are the same model no matter what either is called; two
    directories with the same name and different bytes are not. Measured by
    hashing, never by name.
    """
    model_dir = os.path.abspath(os.path.normpath(model_dir))
    weights, err = weight_files(model_dir)
    ident = {
        "dir": model_dir,
        "weights": [{"file": n, "bytes": b} for n, b in weights],
        "total_bytes": sum(b for _, b in weights),
    }
    if err:
        ident["error"] = err
        return ident
    if hash_weights:
        for rec in ident["weights"]:
            try:
                rec["sha256"] = _sha256(os.path.join(model_dir, rec["file"]))
            except OSError as exc:
                rec["sha256"] = "ERR:" + str(exc)
        digests = [r.get("sha256") for r in ident["weights"] if r.get("sha256")]
        if len(digests) == len(ident["weights"]):
            ident["digest"] = hashlib.sha256(
                "|".join(r["file"] + ":" + r["sha256"] for r in ident["weights"]
                         ).encode("utf-8")).hexdigest()
    return ident


def same_model(a, b):
    """True when two identities describe the same weights."""
    da, db = a.get("digest"), b.get("digest")
    if da and db:
        return da == db
    wa = sorted((r["file"], r["bytes"]) for r in a.get("weights", []))
    wb = sorted((r["file"], r["bytes"]) for r in b.get("weights", []))
    return wa == wb and bool(wa)


def find_foreign_holders(identity, procs, own_pid=None, min_mib=None):
    """Processes OUTSIDE this one that plausibly hold the SAME model.

    A cross-process VRAM copy can only be INFERRED, never read: CUDA allocations
    are not nameable from outside, and NVML reports 0 bytes per pid here. What IS
    observable, and is used: (a) a process running the same Sotto worker, and
    (b) a process whose dedicated VRAM is at least the size of this model.

    The two are NOT the same claim, so they are carried in two tiers:
      tier "same-worker"     - runs sotto_worker.py. The strongest signal there is:
                               a Sotto worker that IS loaded. It cannot be
                               disproved from outside, but it is a fact about the
                               process, not a guess about its VRAM.
      tier "size-plausible"  - holds enough VRAM to contain the model. A browser
                               or the NVIDIA overlay trips this with no ASR in
                               sight, so it is reported as a candidate only, never
                               as a second copy of the model.
    """
    total_mib = (identity.get("total_bytes") or 0) / MIB
    floor = min_mib if min_mib is not None else max(256.0, total_mib)
    out = []
    for r in procs:
        pid = r.get("pid")
        if pid == own_pid:
            continue
        why = []
        tier = None
        cmd = r.get("cmdline") or ""
        if _SOTTO_WORKER in cmd.lower():
            why.append("runs sotto_worker.py")
            tier = "same-worker"
        if (r.get("ded_MiB") or 0) >= floor:
            why.append("dedicated VRAM %.1f MiB >= %.1f MiB (model on disk)"
                       % (r["ded_MiB"], floor))
            if tier is None:
                tier = "size-plausible"
        if why:
            out.append(dict(r, why=why, tier=tier))
    out.sort(key=lambda r: -r.get("ded_MiB", 0.0))
    return out


def residency_verdict(model_dir=None, own_pid=None):
    """The loud answer to "is this model already resident somewhere?"."""
    verdict = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="milliseconds"),
               "device": None, "per_process": [], "model": None,
               "foreign_holders": [], "duplicate_risk": False}
    try:
        verdict["device"] = device_totals()
    except Exception as exc:
        verdict["device_error"] = "%s: %s" % (type(exc).__name__, exc)
    procs = per_process_vram(min_mib=0.5)
    verdict["per_process"] = procs
    if model_dir:
        try:
            ident = model_identity(model_dir, hash_weights=True)
        except Exception as exc:
            ident = {"dir": model_dir, "error": "%s: %s" % (type(exc).__name__, exc),
                     "total_bytes": 0}
        verdict["model"] = ident
        total_mib = (ident.get("total_bytes") or 0) / MIB
        verdict["model_MiB_on_disk"] = round(total_mib, 1)
        holders = find_foreign_holders(ident, procs, own_pid=own_pid)
        verdict["foreign_holders"] = holders
        verdict["duplicate_risk"] = bool(holders)
    return verdict

def find_model_holders(identity, procs, own_pid=None):
    """Only the STRONG tier: processes that run a Sotto worker.

    This is the answer to "is OUR model already resident elsewhere" - the one case
    where reuse could actually have been possible. A browser or the NVIDIA overlay
    holding a similar amount of VRAM is not that case.
    """
    out = []
    for r in procs:
        pid = r.get("pid")
        if pid == own_pid:
            continue
        cmd = r.get("cmdline") or ""
        if _SOTTO_WORKER in cmd.lower():
            out.append(dict(r, why=["runs sotto_worker.py"], tier="same-worker"))
    out.sort(key=lambda r: -r.get("ded_MiB", 0.0))
    return out


def vram_brief(model_dir=None, own_pid=None, top_n=10):
    """A compact, printable brief of who holds GPU memory right now."""
    lines = []
    try:
        d = device_totals()
        for dev in d["devices"]:
            lines.append("GPU: %s driver=%s total=%.0f used=%.0f free=%.0f MiB compute_pids=%d"
                         % (dev["name"], d["driver"], dev["total_MiB"], dev["used_MiB"],
                            dev["free_MiB"], len(dev["compute_pids"])))
    except Exception as exc:
        lines.append("GPU: unmeasurable (%s: %s)" % (type(exc).__name__, exc))
    rows = per_process_vram(min_mib=50.0)
    lines.append("top GPU holders (>=50 MiB dedicated):")
    for r in rows[:top_n]:
        lines.append("  pid=%-7s ded=%8.1f MiB  %s" % (r["pid"], r["ded_MiB"], r["name"] or "?"))
    if model_dir:
        ident = model_identity(model_dir, hash_weights=False)
        total_mib = (ident.get("total_bytes") or 0) / MIB
        lines.append("model on disk: %.1f MiB in %d weight files (%s)"
                     % (total_mib, len(ident.get("weights") or []), ident.get("dir")))
        holders = find_model_holders(ident, rows, own_pid=own_pid)
        if holders:
            lines.append("VERDICT: a Sotto worker (the same model) is already resident:")
            for h in holders:
                lines.append("  pid=%s %s ded=%.1f MiB" % (h.get("pid"), h.get("name"),
                                                           h.get("ded_MiB")))
            lines.append("VERDICT: loading a second copy in a new process would be a DUPLICATE.")
        else:
            lines.append("VERDICT: no other Sotto worker is resident; nothing to reuse.")
    return lines

