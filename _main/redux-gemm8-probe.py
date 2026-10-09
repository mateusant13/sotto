#!/usr/bin/env python3
"""Does the Photon/kestrel ``gemm8`` int8 CPU path run on THIS box? (measurement)

WHY THIS FILE EXISTS
--------------------
``worker/models/parakeet-redux-ternary/`` is a 1.58-bit ternary re-quantisation of
``nvidia/parakeet-tdt-0.6b-v3``.  Photon (moondream's engine) keeps those weights
PACKED and multiplies them with a compiled int8 kernel ("gemm8") whenever the
machine has one of ``avx512vnni`` / ``avxvnni`` / ``avx2`` (x86) or the three neon
variants.  When it does not, ``resident_form("cpu")`` raises ``NotImplementedError``
-- and ``worker/redux_batch.py`` catches that by patching ``resident_form`` to
return ``"dense"``, which dequantizes 193/193 layers to float ONCE, at load.  That
is where the documented **3.90 GB peak RSS** comes from.

So the whole cost question is one question: **can gemm8 run here?**

``kestrel_kernels.ternary.ternary_gemm_ready()`` says no, because the payload's own
probe reports ``ternary_gemm_isa() == 'scalar'``.  This file does not take that on
trust.  It asks the payload DIRECTLY, and it separates three very different
explanations that all look identical from the outside:

  (i)   **no code**: the compiled payload has no x86 SIMD path at all;
  (ii)  **no CPU**: this CPU genuinely lacks AVX2;
  (iii) **locked**: the path exists but a licence / key gate refuses it.

Only (i) and (iii) are actionable, and they are actionable in opposite directions,
so the probe reports which one it found, with the payload's own words.

ARMS (one command)
------------------
  ARM 1  the payload's capability census next to TWO INDEPENDENT opinions about
         the CPU (torch's own dispatch capability, numpy's dispatched-feature
         census).  This is what separates (i) from (ii).
  ARM 2  a small SELF-CHECKING GEMM: reference (the documented scalar oracle) vs
         each named ISA, compared BYTE FOR BYTE.  A path that runs and computes
         something else is worse than one that refuses, so the comparison is the
         point -- and the refusal, when it comes, is quoted verbatim.
  ARM 3  the loader question: what ``resident_form('cpu')`` picks, and what
         happens when ``set_gemm_isa()`` is used to FORCE the packed path anyway.
         That force is a trap worth documenting: ``ternary_gemm_isa()`` reads the
         override, so ``resident_form`` returns ``'gemm8'`` on a machine where the
         kernel does not exist -- the load then succeeds and the FIRST projection
         dies.  ``redux_batch.py`` patches ``resident_form`` instead, which is the
         right shape.
  ARM 4  the payload's own NOTICE block, and the wheel identity (is there another
         published wheel with a different payload?).  A missing kernel that is
         missing from the only published artifact is a different fact from one
         that is merely not installed here.

CONTROL (the arm that MUST go red)
----------------------------------
``--neg-arm`` compares the reference against a deliberately corrupted copy, so a
harness that prints GREEN unconditionally is visible as such.

BUDGET: this probe is capped at 2 threads (``--threads``, default 2), per the
house rule for measurement probes.  It opens no audio device, spawns nothing, and
loads no model (that is ``redux-engine-cost-probe.py``).

Usage:
    py -3 _main/redux-gemm8-probe.py [--threads 2] [--neg-arm] [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time

ISA_NAMES = ("scalar", "avx2", "avxvnni", "avx512vnni",
             "neon-i8mm", "neon-dotprod", "neon-mull")


def _log(msg: str) -> None:
    print(msg, flush=True)


# ── ARM 1 ─────────────────────────────────────────────────────────────────────
def arm1_capability() -> dict:
    """The payload's census, next to two INDEPENDENT CPU opinions."""
    import kestrel_kernels._cpu as cpu

    available = {}
    for name in ISA_NAMES:
        try:
            available[name] = bool(cpu.gemm_isa_available(name))
        except Exception as exc:
            available[name] = f"{type(exc).__name__}: {exc}"

    conformer = {}
    for name in (None, "scalar", "avx2", "avx512", "neon"):
        try:
            conformer[str(name)] = cpu.conformer_isa(name)
        except Exception as exc:
            conformer[str(name)] = f"{type(exc).__name__}: {exc}"

    _log("ARM 1 -- what the compiled payload says it can do")
    _log(f"  platform                  : {platform.processor()!r} ({platform.machine()})")
    _log(f"  ternary_gemm_isa()        : {cpu.ternary_gemm_isa()!r}")
    _log(f"  conformer_isa()           : {cpu.conformer_isa()!r}")
    _log(f"  gemm_isa_available        : {available}")
    _log(f"  conformer_isa(by name)    : {conformer}")
    _log(f"  pool_threads()            : {cpu.pool_threads()}")
    _log(f"  pool_cpus()               : {cpu.pool_cpus()}")
    try:
        _log(f"  pool_placement()          : {cpu.pool_placement()!r}")
    except Exception as exc:
        _log(f"  pool_placement()          : {type(exc).__name__}: {exc}")

    # INDEPENDENT INSTRUMENT 1 -- torch's own dispatcher, a different vendor's
    # code, compiled with PERF_WITH_AVX2=1.  ``show()`` PRINTS its report, so it
    # is captured rather than dumped into this probe's own output.
    import contextlib
    import io

    import torch
    torch_cap = torch.backends.cpu.get_cpu_capability()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        torch.__config__.show()
    torch_cfg = buf.getvalue()
    if not torch_cfg:
        # Some builds RETURN the report instead of printing it; take it either way.
        with contextlib.redirect_stdout(buf):
            returned = torch.__config__.show()
        torch_cfg = buf.getvalue() or str(returned or "")
    torch_avx2 = "PERF_WITH_AVX2=1" in torch_cfg

    # INDEPENDENT INSTRUMENT 2 -- numpy's dispatched-feature census.  Read the
    # feature dict when the build exposes it, and fall back to capturing the
    # human-readable dump (``show_config`` PRINTS; it does not return).
    import contextlib
    import io

    import numpy as np
    found = []
    try:
        features = np.core._multiarray_umath.__cpu_features__  # numpy < 2
        found = sorted(name for name, on in features.items() if on)
    except Exception:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            np.show_config(mode="stdout")
        grab = False
        for line in buf.getvalue().splitlines():
            stripped = line.strip()
            if stripped.startswith("found:"):
                grab = True
                continue
            if stripped.startswith("not found:"):
                grab = False
                continue
            if grab and stripped.startswith("- "):
                found.append(stripped[2:].strip())

    _log(f"  independent (torch)       : get_cpu_capability()={torch_cap!r}, "
         f"PERF_WITH_AVX2=1 -> {torch_avx2}")
    _log(f"  independent (numpy)       : dispatched features = {found}")

    import kestrel_kernels
    archive = os.path.join(os.path.dirname(kestrel_kernels.__file__), "kestrel_cpu.kstlc")
    payload = {
        "path": archive,
        "bytes": os.path.getsize(archive) if os.path.isfile(archive) else None,
        "sha256": _sha256(archive) if os.path.isfile(archive) else None,
    }
    _log(f"  kestrel_cpu.kstlc         : {payload['bytes']} bytes, "
         f"sha256 {str(payload['sha256'])[:16]}...")

    return {
        "available": available,
        "conformer_isa": conformer,
        "ternary_gemm_isa": cpu.ternary_gemm_isa(),
        "pool_cpus": list(cpu.pool_cpus()),
        "pool_threads": cpu.pool_threads(),
        "torch_cpu_capability": torch_cap,
        "torch_PERF_WITH_AVX2": torch_avx2,
        "numpy_dispatched": found,
        "payload": payload,
    }


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── ARM 2 ─────────────────────────────────────────────────────────────────────
def _fixtures(M: int, K: int, N: int, seed: int = 1234):
    import numpy as np
    rng = np.random.default_rng(seed)
    codes = rng.integers(-1, 2, size=(N, K)).astype(np.int8)
    scales = (rng.random((N, K // 128)) * 0.05 + 0.01).astype(np.float32)
    x = rng.standard_normal((M, K)).astype(np.float32)
    return codes, scales, x


def _pack(codes):
    import numpy as np
    u = (codes.astype(np.int16) + 1).astype(np.uint8)
    u = u.reshape(codes.shape[0], codes.shape[1] // 4, 4)
    return (u << np.array([0, 2, 4, 6], dtype=np.uint8)).sum(-1, dtype=np.uint8)


def arm2_small_gemm(threads: int, neg: bool = False) -> dict:
    import numpy as np
    import kestrel_kernels._cpu as cpu

    M, K, N = 64, 256, 64
    codes, scales, x = _fixtures(M, K, N)
    panels = cpu.ternary_pack_panels(_pack(codes))

    _log("")
    _log(f"ARM 2 -- {M}x{K} @ {K}x{N} ternary GEMM: scalar oracle vs each named path")
    _log(f"  threads={threads} (house budget for a measurement probe)")

    ref = np.empty((M, N), dtype=np.float32)
    cpu.ternary_gemm_reference(x, panels, scales, ref, group_size=128)
    _log(f"  reference (scalar oracle) : ok, sum={float(ref.sum()):.6f}")

    out = {}
    for isa in ("scalar", "avx2", "avxvnni", "avx512vnni"):
        got = np.empty((M, N), dtype=np.float32)
        started = time.perf_counter()
        try:
            cpu.ternary_gemm(x, panels, scales, got,
                             group_size=128, threads=threads, isa=isa)
        except Exception as exc:
            out[isa] = {"ran": False, "error": f"{type(exc).__name__}: {exc}"}
            _log(f"  isa={isa:<12}: REFUSED -> {type(exc).__name__}: {exc}")
            continue
        elapsed_ms = (time.perf_counter() - started) * 1000
        identical = bool(np.array_equal(ref, got))
        out[isa] = {"ran": True, "identical": identical,
                    "max_abs_diff": float(np.abs(ref - got).max()),
                    "ms": round(elapsed_ms, 3)}
        _log(f"  isa={isa:<12}: ran in {elapsed_ms:6.2f} ms, "
             f"bit-identical={identical}, max|diff|={float(np.abs(ref - got).max()):.3e}")

    # ARM 2b -- the payload's REAL signature, with no isa= at all.  If this is
    # what ships and it works, then the scalar path is live and only the SIMD
    # names are absent.
    got = np.empty((M, N), dtype=np.float32)
    try:
        cpu.ternary_gemm(x, panels, scales, got, group_size=128, threads=threads)
        same = bool(np.array_equal(ref, got))
        out["(no isa= kwarg)"] = {"ran": True, "identical": same}
        _log(f"  no isa= kwarg            : ran, bit-identical={same} "
             f"<- what the shipped path would call")
    except Exception as exc:
        out["(no isa= kwarg)"] = {"ran": False, "error": f"{type(exc).__name__}: {exc}"}
        _log(f"  no isa= kwarg            : {type(exc).__name__}: {exc}")

    if neg:
        wrong = ref.copy()
        wrong[0, 0] += 1.0
        red = not bool(np.array_equal(wrong, ref))
        out["_control"] = {"red_as_required": red}
        _log(f"  CONTROL (corrupted ref)  : identical={not red} -> "
             f"{'RED as required' if red else 'GREEN (CONTROL BROKEN)'}")

    return out


# ── ARM 3 ─────────────────────────────────────────────────────────────────────
def arm3_loader(force_isa: str, threads: int) -> dict:
    """What the real loader picks, and what FORCING the packed path does."""
    import numpy as np
    import kestrel_kernels.ternary as ternary

    _log("")
    _log("ARM 3 -- resident_form('cpu') through the real kestrel loader")
    shipped = None
    try:
        shipped = ternary.resident_form("cpu")
        _log(f"  as shipped               : resident_form('cpu') = {shipped!r}")
    except Exception as exc:
        shipped = f"{type(exc).__name__}: {exc}"
        _log(f"  as shipped               : RAISES {shipped}")

    result = {"as_shipped": shipped, "force_isa": force_isa}
    ternary.set_gemm_isa(force_isa)
    forced_form = None
    try:
        forced_form = ternary.resident_form("cpu")
        _log(f"  set_gemm_isa({force_isa!r})  : accepted; "
             f"ternary_gemm_isa() -> {ternary.ternary_gemm_isa()!r}; "
             f"resident_form('cpu') -> {forced_form!r}")
    except Exception as exc:
        forced_form = f"{type(exc).__name__}: {exc}"
        _log(f"  set_gemm_isa({force_isa!r})  : resident_form still raises {forced_form}")
    result["with_force_form"] = forced_form

    # The trap, measured end to end: build a real packed TernaryWeight in the
    # forced 'gemm8' mode and multiply with it.
    if forced_form == "gemm8":
        import kestrel_kernels._cpu as cpu
        import torch
        M, K, N = 64, 256, 64
        codes, scales, x = _fixtures(M, K, N)
        weight = ternary.TernaryWeight(
            torch.from_numpy(_pack(codes)), torch.from_numpy(scales.astype(np.float16)), K)
        try:
            weight.materialize(torch.float32)
            _log(f"  materialize()            : ok, mode={weight.mode!r} "
                 f"(the panels were packed, so the LOAD looks healthy)")
        except Exception as exc:
            _log(f"  materialize()            : RAISES {type(exc).__name__}: {exc}")
            result["materialize_error"] = f"{type(exc).__name__}: {exc}"
            ternary.set_gemm_isa(None)
            return result
        try:
            y = ternary.ternary_linear_torch(torch.from_numpy(x), weight)
            _log(f"  first projection         : ok, sum={float(y.sum()):.6f}")
            result["projection"] = "ok"
        except Exception as exc:
            _log(f"  first projection         : RAISES {type(exc).__name__}: {exc}")
            result["projection_error"] = f"{type(exc).__name__}: {exc}"
        _ = cpu
    ternary.set_gemm_isa(None)
    return result


# ── ARM 4 ─────────────────────────────────────────────────────────────────────
def arm4_payload_and_wheels() -> dict:
    """The payload's own NOTICE, and whether any other published wheel differs."""
    import kestrel_kernels

    archive = os.path.join(os.path.dirname(kestrel_kernels.__file__), "kestrel_cpu.kstlc")
    blob = open(archive, "rb").read()
    notice = []
    for s in re.findall(rb"[ -~]{12,}", blob):
        text = s.decode("ascii", "replace")
        if "NOTICE" in text or "Kestrel" in text or "key" in text or "prohibited" in text:
            notice.append(text)

    _log("")
    _log("ARM 4 -- the payload's own words, and the wheel it came from")
    for line in notice:
        _log(f"  notice: {line}")
    _log(f"  payload sha256           : {_sha256(archive)}")

    # Is the installed payload the ONLY published one?  Compare against the wheel
    # pip would hand out for this exact platform tag.
    found = []
    for root in (r"G:\Temp\kk-check",):
        if not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            if not name.endswith(".whl"):
                continue
            import zipfile
            with zipfile.ZipFile(os.path.join(root, name)) as z:
                for entry in z.namelist():
                    if entry.endswith("kestrel_cpu.kstlc"):
                        data = z.read(entry)
                        found.append({
                            "wheel": name,
                            "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "same_as_installed": hashlib.sha256(data).hexdigest()
                                                == _sha256(archive),
                        })
    for item in found:
        _log(f"  published wheel          : {item['wheel']} -> kestrel_cpu.kstlc "
             f"{item['bytes']} B, sha256 {item['sha256'][:16]}..., "
             f"same_as_installed={item['same_as_installed']}")
    if not found:
        _log("  published wheel          : NOT CHECKED (no wheel staged) -- a "
             "'grep returned zero' with a shelf life; re-run with a wheel in "
             "G:\\Temp\\kk-check")
    return {"notice": notice, "payload_sha256": _sha256(archive), "wheels": found}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="redux-gemm8-probe",
        description="Measure whether the Photon/kestrel gemm8 int8 CPU path runs here.")
    parser.add_argument("--threads", type=int, default=2,
                        help="threads handed to the kernel (house budget: <=2)")
    parser.add_argument("--neg-arm", action="store_true",
                        help="run the corrupted-expectation control in ARM 2")
    parser.add_argument("--force-isa", default="avx2",
                        help="ISA to force in ARM 3 (default: avx2)")
    parser.add_argument("--json", action="store_true", help="also print one JSON line")
    args = parser.parse_args(argv)

    cpu = arm1_capability()
    small = arm2_small_gemm(args.threads, neg=args.neg_arm)
    loader = arm3_loader(args.force_isa, args.threads)
    payload = arm4_payload_and_wheels()

    ran = {k: v for k, v in small.items() if k != "_control" and v.get("ran")}
    identical = {k: v for k, v in ran.items() if v.get("identical")}
    refused = {k: v for k, v in small.items() if k != "_control" and not v.get("ran")}

    _log("")
    _log("VERDICT")
    if identical:
        _log(f"  paths that RUN and MATCH the scalar oracle: {sorted(identical)}")
    if refused:
        _log(f"  paths the payload REFUSED: {sorted(refused)}")
        for k in sorted(refused):
            _log(f"    {k}: {refused[k]['error']}")
    _log(f"  payload reports available : {cpu['available']}")
    _log(f"  CPU really has (torch)    : {cpu['torch_cpu_capability']}")
    _log(f"  CPU really has (numpy)    : AVX2 in {cpu['numpy_dispatched']}")
    _log(f"  resident_form as shipped  : {loader['as_shipped']!r}")
    if "projection_error" in loader:
        _log(f"  FORCING the packed path   : dies at the first projection -> "
             f"{loader['projection_error']}")
    if args.neg_arm:
        ctrl = small.get("_control") or {}
        _log(f"  control (must be RED)     : red_as_required={ctrl.get('red_as_required')}")

    if args.json:
        print(json.dumps({"type": "result", "cpu": cpu, "small_gemm": small,
                          "loader": loader, "payload": payload},
                         ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
