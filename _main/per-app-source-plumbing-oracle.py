"""Per-app source plumbing oracle (STEP 2/3) -- IN PROCESS, LAUNCHES NOTHING.

WHAT IT GATES.  The per-app tap lane added, to 'worker/sotto_worker.py':

  * 'ProcessLoopbackTap' + its COM helpers (STEP 2), reachable ONLY through a
    candidate row that carries 'process_loopback: True'. The ladder DOES offer
    that row -- as rung 'p', behind 'if target_pid:' and AFTER rung C, so an
    explicit '--device' still wins and a run with no pid returns the
    pre-change candidate list unchanged;
  * 'tap_source(dev)' (STEP 3), the STABLE identity of the audio behind a
    candidate row: 'proc:<pid>' / 'device:<name>' / 'file:<name>';
  * 'LineFormer.set_source()' + a 'source' key that '_event()' adds ONLY when a
    source was given, so the arms that have none ('--selftest', the file arm)
    keep emitting exactly the bytes they emitted before the key existed.

WHY IT EXISTS.  The lane delivered no receipt and no instrument, and the code
carried a defect that 'py_compile' CANNOT see and that no launch has been
allowed to catch since the owner's stop order: 'import ctypes' in this file is
LOCAL to '_pmc()', so the module-level PLP block read an unbound name and
'import sotto_worker' died with NameError.  The app would have started, spawned
a worker, and shown nothing -- the same shape as the frozen tap the owner
reported.  CHK-1 below is that check, and the --neg-arm proves it can go RED.

NOT MEASURED HERE, and not claimable from a green run: whether a real
process-loopback tap opens on this build inside the WORKER (the gate measured
that outside it), whether two workers in one shell is the right topology
(STEP 5), and whether the panel keys rows by (source, start) (STEP 4).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER_DIR = os.path.join(ROOT, "worker")
WORKER = os.path.join(WORKER_DIR, "sotto_worker.py")

SOURCE_GUARD = '**({"source": self.source} if self.source is not None else {}),'
CTYPES_GUARD = "import ctypes\r\n_PLP_DWORD = ctypes.c_ulong"
CTYPES_GUARD_LF = "import ctypes\n_PLP_DWORD = ctypes.c_ulong"

failures = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not ok:
        failures.append(name)


def load_module(path, name):
    """Import a worker revision by PATH (so a mutant copy is a real subject)."""
    if WORKER_DIR not in sys.path:
        sys.path.insert(0, WORKER_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def run_checks(mod, tag):
    """Every check, against 'mod'. Returns the list of failed check names."""
    del failures[:]
    print("== %s" % tag)

    # CHK-1 -- THE MODULE IMPORTS AT ALL. This is the check the lane's code
    # failed: py_compile passes on a module-level NameError.
    check("CHK-1 imports without NameError", True, "loaded %s" % os.path.basename(mod.__file__))

    # CHK-2 -- the identity strings, one per source kind.
    proc = mod.tap_source({"process_loopback": True, "target_pid": 4242})
    dev = mod.tap_source({"name": "CABLE Output (VB-Audio Virtual Cable)"})
    fil = mod.tap_source({"file_tap": "C:/tmp/speech.wav"})
    check("CHK-2 tap_source proc", proc == "proc:4242", proc)
    check("CHK-2 tap_source device", dev == "device:CABLE Output (VB-Audio Virtual Cable)", dev)
    check("CHK-2 tap_source file", fil == "file:speech.wav", fil)

    # CHK-3 -- NO SOURCE => NO KEY. The exact key set of the pre-existing arms.
    before = {"type", "text", "start", "end", "final", "closed"}
    plain = mod.LineFormer()
    ev = plain.push("ola mundo", start=0.0, end=1.0)[0]
    check("CHK-3 no-source event has no 'source' key", "source" not in ev, str(sorted(ev)))
    check("CHK-3 no-source event key set unchanged", set(ev) == before, str(sorted(ev)))

    # CHK-4 -- A SOURCE => THE KEY, on BOTH channels (live box and the close).
    src = mod.LineFormer(source="proc:4242")
    part = src.push("ola mundo", start=0.0, end=1.0)[0]
    check("CHK-4 partial carries source", part.get("source") == "proc:4242", str(part.get("source")))
    src.flush()
    closed = src.take_closed()
    check("CHK-4 closed carries source", bool(closed) and closed[0].get("source") == "proc:4242",
          str(closed[0].get("source")) if closed else "no closed event")
    check("CHK-4 closed is the final channel", bool(closed) and closed[0].get("final") is True)

    # CHK-5 -- set_source REPOINTS; reset() does NOT clear it (stream vs line).
    swap = mod.LineFormer(source="proc:1")
    swap.push("a", start=0.0, end=1.0)
    swap.set_source("device:CABLE Output")
    swap.reset()
    after = swap.push("b", start=2.0, end=3.0)[0]
    check("CHK-5 set_source repoints and survives reset", after.get("source") == "device:CABLE Output",
          str(after.get("source")))
    swap.set_source(None)
    none_ev = swap.push("c", start=4.0, end=5.0)[0]
    check("CHK-5 set_source(None) removes the key again", "source" not in none_ev, str(sorted(none_ev)))

    # CHK-6 -- the WIRE keeps it: line_events() drops 'closed' and nothing else.
    wire = mod.line_events([part, closed[0]])
    check("CHK-6 line_events preserves source", all(e.get("source") == "proc:4242" for e in wire),
          str([e.get("source") for e in wire]))
    check("CHK-6 line_events still drops 'closed'", all("closed" not in e for e in wire))
    check("CHK-6 line_events coerces final", [e["final"] for e in wire] == [False, True],
          str([e["final"] for e in wire]))

    # CHK-7 -- STATIC: the factory dispatches, the two open sites stamp the tap,
    # the run loop hands it to the former.
    with open(WORKER, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    check("CHK-7 factory routes process_loopback", 'if device.get("process_loopback"):' in text)
    check("CHK-7 factory returns ProcessLoopbackTap", "return ProcessLoopbackTap(" in text)
    check("CHK-7 both open sites stamp tap.source",
          text.count("tap.source = tap_source(") == 2, "count=%d" % text.count("tap.source = tap_source("))
    check("CHK-7 run loop hands the source to the former",
          'former.set_source(getattr(live, "source", None))' in text)
    check("CHK-7 candidate row is built for a pid",
          text.count("def process_loopback_candidate(") == 1)

    # CHK-8 -- GATED, NOT INERT. The ladder DOES offer a process row; what makes
    # the shipped path unchanged is the gate in front of it. A run with no pid
    # passes target_pid=None, so the row is never built and the candidate list
    # is the pre-change list.
    lines = text.splitlines()
    offer_at = [i for i, ln in enumerate(lines) if "offer(process_loopback_candidate(" in ln]
    gated = bool(offer_at) and lines[offer_at[0] - 1].strip() == "if target_pid:"
    check("CHK-8 rung 'p' is offered behind 'if target_pid:'", gated,
          "offer at line %s" % (offer_at[0] + 1 if offer_at else "ABSENT"))
    check("CHK-8 that is the only call site",
          len([ln for ln in lines if "process_loopback_candidate(" in ln and "def " not in ln]) == len(offer_at),
          "call sites=%d" % len(offer_at))
    check("CHK-8 --target-pid defaults to None",
          'ap.add_argument("--target-pid", default=None' in text)
    check("CHK-8 the env fallback is the only other source",
          'os.environ.get("SOTTO_TARGET_PID")' in text)
    check("CHK-8 device_candidates takes the pid as an optional",
          "def device_candidates(cfg_audio=None, wanted=None, target_pid=None):" in text)
    call_shape = "device_candidates(audio_cfg, wanted, target_pid=target_pid)"
    check("CHK-8 the pid reaches both ladder entries",
          text.count(call_shape) == 2, "count=%d" % text.count(call_shape))
    # CHK-8b -- AND THE MIX IS NEVER SUBSTITUTED SILENTLY for the app the owner
    # asked for: the fall-through is reported once, loudly, with the word.
    check("CHK-8b separation loss is reported as an event",
          'reason="per-app-tap-lost"' in text)

    # CHK-9 -- the declared format is the one the gate measured, not the mix,
    # and the SDK's mode values are the real ones (INCLUDE is 0, not 1).
    check("CHK-9 declared format 48000/2ch/32", (mod.PLP_DECLARED_RATE, mod.PLP_DECLARED_CHANNELS,
                                                 mod.PLP_DECLARED_BITS) == (48000, 2, 32))
    check("CHK-9 SDK mode values (INCLUDE=0, EXCLUDE=1)",
          (mod.PLP_MODE_INCLUDE_TARGET_PROCESS_TREE,
           mod.PLP_MODE_EXCLUDE_TARGET_PROCESS_TREE) == (0, 1),
          "include=%d exclude=%d" % (mod.PLP_MODE_INCLUDE_TARGET_PROCESS_TREE,
                                     mod.PLP_MODE_EXCLUDE_TARGET_PROCESS_TREE))
    check("CHK-9 the tap's default mode is INCLUDE (Chrome needs the tree)",
          "mode=PLP_MODE_INCLUDE_TARGET_PROCESS_TREE)" in text)
    return list(failures)


def neg_arm():
    """Two mutants, each expected to turn a NAMED check RED."""
    print("== NEG-ARM")
    with open(WORKER, "r", encoding="utf-8") as fh:
        live_text = fh.read()          # universal newlines: guards match with \n
    problems = []

    # MUTANT A -- the source key removed from the event.
    if SOURCE_GUARD not in live_text:
        problems.append("mutant A guard not found in the live file")
    else:
        path_a = os.path.join(WORKER_DIR, "_plp-neg-source-worker.py")
        try:
            with open(path_a, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(live_text.replace(SOURCE_GUARD, "**( {} ),"))
            mod_a = load_module(path_a, "_plp_neg_source_worker")
            failed_a = run_checks(mod_a, "MUTANT A (source key removed)")
            want = [n for n in failed_a if n.startswith("CHK-4") or n.startswith("CHK-5")]
            ok = bool(want) and not any(n.startswith("CHK-1") for n in failed_a)
            print(("  PASS " if ok else "  FAIL ") + "mutant A went RED where it had to: " + str(want))
            if not ok:
                problems.append("mutant A did not go RED on CHK-4/CHK-5: %s" % failed_a)
        finally:
            if os.path.exists(path_a):
                os.remove(path_a)

    # MUTANT B -- the module-level ctypes import removed (today's real defect).
    if CTYPES_GUARD not in live_text and CTYPES_GUARD_LF not in live_text:
        problems.append("mutant B guard not found in the live file")
    else:
        path_b = os.path.join(WORKER_DIR, "_plp-neg-ctypes-worker.py")
        try:
            with open(path_b, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(live_text.replace(CTYPES_GUARD, "_PLP_DWORD = ctypes.c_ulong")
                              .replace(CTYPES_GUARD_LF, "_PLP_DWORD = ctypes.c_ulong"))
            try:
                load_module(path_b, "_plp_neg_ctypes_worker")
                ok = False
                detail = "the mutant imported cleanly -- CHK-1 cannot say NO"
            except NameError as exc:
                ok = "ctypes" in str(exc)
                detail = "NameError: %s" % exc
            except Exception as exc:                       # noqa: BLE001 - report anything else
                ok = False
                detail = "%s: %s" % (type(exc).__name__, exc)
            print(("  PASS " if ok else "  FAIL ") + "mutant B RED as the live defect was: " + detail)
            if not ok:
                problems.append("mutant B did not reproduce the import death: " + detail)
        finally:
            if os.path.exists(path_b):
                os.remove(path_b)

    print("  NEG-ARM: %s" % ("PASS -- both mutants RED" if not problems else "FAIL -- " + "; ".join(problems)))
    return problems


def main():
    ap = argparse.ArgumentParser(description="per-app source plumbing oracle (launch-free)")
    ap.add_argument("--neg-arm", action="store_true", help="mutate copies beside the worker")
    args = ap.parse_args()

    print("worker: %s" % WORKER)
    print("worker: %d B sha256=%s" % (os.path.getsize(WORKER), sha256(WORKER)))
    try:
        mod = load_module(WORKER, "sotto_worker_live")
    except Exception as exc:                               # noqa: BLE001 - the whole point
        check("CHK-1 imports without NameError", False, "%s: %s" % (type(exc).__name__, exc))
        print("VERDICT: FAIL -- the worker does not import; nothing else can be measured")
        return 1

    failed = run_checks(mod, "LIVE (working tree)")
    problems = neg_arm() if args.neg_arm else []

    print("VERDICT: %s" % ("PASS" if not failed and not problems else "FAIL"))
    if failed:
        print("  live failures: %s" % failed)
    return 0 if not failed and not problems else 1


if __name__ == "__main__":
    sys.exit(main())
