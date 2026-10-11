"""Oracle for the settled-tap stall watchdog and the pump-death record.

THE OWNER'S FAILURE (measured 2026-10-11): Alt+C showed nothing while the desktop
was loud. Cause: the worker's tap STOPPED DELIVERING blocks -- device_blocks froze
at 59 (5.6 s of audio, 6 captions) and the capture loop's settled branch spun at
10 Hz for 34 minutes without ever asking whether the tap still delivered.

ARMS, and how each one can say NO:
  ARM 1  a pump that dies in GetNextPacketSize is RECORDED (the real _pump is
         executed with a stubbed COM layer) -- not swallowed by a bare break.
  ARM 2  the same for the GetBuffer path.
  ARM 3  NO FALSE POSITIVE: a tap whose blocks keep arriving is left alone. The
         block under test is extracted FROM THE LIVE WORKER FILE by indentation,
         so a stale copy cannot pass.
  ARM 4  THE CURE: blocks frozen past the bound -> close the tap, re-open in
         place, emit capture-started(reopened=True), and DO NOT exit.
  ARM 4b after the same-device retries are spent, a FRESH enumeration's other
         endpoint is taken (the audio may simply have MOVED).
  ARM 5  NEGATIVE CONTROL: the same block with the watchdog branch deleted does
         NOTHING on ARM 4's inputs -> the gate can say NO.
  ARM 6  PREMISE: device_blocks is incremented by the TAP's own callback (not by
         the capture loop), so a frozen counter means the tap stopped delivering;
         and the watchdog sits INSIDE the settled branch.

Exit 0 = every arm as expected. 3 = a product gap. 2 = the instrument could not
measure (a needle is missing) -- never a silent pass.
"""
import ctypes
import importlib.util
import re
import sys
import threading
import time

WORKER = r"H:\sotto\worker\sotto_worker.py"
TAP = r"H:\sotto\worker\wasapi_loopback.py"
FAILED = []
MISSING = []


def arm(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else ""))
    if not ok:
        FAILED.append(name)
    return ok


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


src = open(WORKER, "r", encoding="utf-8", errors="replace").read()
tsrc = open(TAP, "r", encoding="utf-8", errors="replace").read()
lines = src.splitlines()

# ---------------------------------------------------------------- ARM 6 premise
inc = [i for i, l in enumerate(lines) if l.strip() == 'device_blocks["value"] += 1']
iset = [i for i, l in enumerate(lines) if l.strip() == "if settled:"]
iwd = [i for i, l in enumerate(lines) if l.strip() == 'if device_blocks["value"] != stall_blocks:']
if len(inc) != 1 or len(iset) != 1 or len(iwd) != 1:
    MISSING.append("anchors inc=%d settled=%d wd=%d" % (len(inc), len(iset), len(iwd)))
    print("FAIL ARM 6 premise: anchors inc=%d settled=%d wd=%d" % (len(inc), len(iset), len(iwd)))
else:
    k = inc[0]
    owner = None
    for j in range(k, -1, -1):
        m = re.match(r"^(\s*)def\s+(\w+)", lines[j])
        if m and len(m.group(1)) < len(lines[k]) - len(lines[k].lstrip()):
            owner = m.group(2)
            break
    ind_set = len(lines[iset[0]]) - len(lines[iset[0]].lstrip())
    ind_wd = len(lines[iwd[0]]) - len(lines[iwd[0]].lstrip())
    if owner in (None, "main"):
        MISSING.append("block counter owner=%r (line %d)" % (owner, k + 1))
        print("FAIL ARM 6 premise: counter owner=%r at line %d; context: %s" % (owner, k + 1, [x.strip()[:40] for x in lines[k - 2:k + 3]]))
    else:
        arm("ARM 6 premise: counter is the TAP callback's (%s), watchdog is inside settled" % owner,
            iwd[0] > iset[0] and ind_wd > ind_set,
            "counter@%d settled@%d wd@%d indent %d>%d" % (k + 1, iset[0] + 1, iwd[0] + 1, ind_wd, ind_set))

# --------------------------------------------------- ARM 1/2 the pump records WHY
try:
    wl = load(TAP, "wl_tap")
except Exception as exc:
    MISSING.append("wasapi_loopback import: %s" % exc)
    wl = None
if wl is not None:
    m_next = re.search(r"next_size = _vtbl\(\s*cap,\s*(\d+)", tsrc)
    m_get = re.search(r"get_buffer = _vtbl\(\s*cap,\s*(\d+)", tsrc)
    if not (m_next and m_get):
        MISSING.append("_vtbl indices next=%s get=%s" % (bool(m_next), bool(m_get)))
        print("FAIL ARM 1/2: _vtbl indices not found")
    else:
        i_next, i_get = int(m_next.group(1)), int(m_get.group(1))
        print("NOTE _vtbl indices: next_size=%d get_buffer=%d" % (i_next, i_get))

        class AnyObj:
            def __getattr__(self, name):
                return lambda *a, **k: 0

        def run_pump(mode):
            delivered = []
            state = {"calls": 0}

            def vtbl(cap, index, restype, *argtypes):
                if index == i_next:
                    def next_size(c, ptr):
                        state["calls"] += 1
                        if mode == "next":
                            return 0x88890004  # AUDCLNT_E_DEVICE_INVALIDATED
                        ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32))[0] = 4800
                        return 0
                    return next_size
                if index == i_get:
                    def get_buffer(*a):
                        return 0x88890004
                    return get_buffer
                return lambda *a: 0

            wl._vtbl = vtbl
            t = wl.WasapiLoopbackTap.__new__(wl.WasapiLoopbackTap)
            t.on_block = delivered.append
            t.rate, t.block, t.block_ms, t.block_align = 48000, 4800, 100, 4
            t.float_fmt, t.channels = True, 2
            t._stop = threading.Event()
            t._cb_lock = threading.Lock()
            t.np = __import__("numpy")
            t.position_gap_packets, t.silent_packets = 0, 0
            t.pump_exited, t.pump_exit_hr, t.pump_exit_where = False, 0, ""
            t._capture = object()  # _pump names it _capture
            t.ep = AnyObj()
            t._pump()
            return t, delivered

        for mode, where in (("next", "GetNextPacketSize"), ("get", "GetBuffer")):
            try:
                t, delivered = run_pump(mode)
            except Exception as exc:
                MISSING.append("_pump(%s) raised %s: %s" % (mode, type(exc).__name__, exc))
                print("FAIL ARM %s: _pump raised %s: %s" % (mode, type(exc).__name__, exc))
                continue
            ok = (t.pump_exited is True and t.pump_exit_hr == 0x88890004
                  and t.pump_exit_where == where and delivered == [])
            arm("ARM %d pump death recorded (%s)" % (1 if mode == "next" else 2, where), ok,
                "pump_exited=%s hr=0x%08X where=%r delivered=%d" % (t.pump_exited, t.pump_exit_hr, t.pump_exit_where, len(delivered)))

# ------------------------------------------- extract the settled branch BY INDENT
block = None
if len(iset) != 1:
    MISSING.append("settled anchor for extraction (hits=%d)" % len(iset))
else:
    i0 = iset[0]
    ind0 = len(lines[i0]) - len(lines[i0].lstrip())
    i1 = i0 + 1
    while i1 < len(lines):
        s = lines[i1]
        if s.strip() and (len(s) - len(s.lstrip())) <= ind0:
            break
        i1 += 1
    block = "\n".join(l[ind0:] for l in lines[i0:i1])
    print("EXTRACTED settled branch: lines %d-%d (%d lines)" % (i0 + 1, i1, i1 - i0))

PARAMS = ("settled, device_blocks, now, err, emit, close_tap, LoopbackTap, tap_holder, block_ms, "
          "on_block, device_candidates, audio_cfg, wanted, candidates, attempt_no, counters, "
          "device_peak, time, TAP_STALL_S, TAP_STALL_SAME_DEVICE_TRIES, TAP_STALL_MAX_S, "
          "seed_tap, seed_dev, seed_stall_blocks, seed_stall_since, seed_stall_backoff, "
          "seed_stall_reopens")
INIT = ("    tap = seed_tap\n    dev = seed_dev\n    stall_blocks = seed_stall_blocks\n"
        "    stall_since = seed_stall_since\n    stall_backoff = seed_stall_backoff\n"
        "    stall_reopens = seed_stall_reopens\n")
RET = ("    return {\"stall_blocks\": stall_blocks, \"stall_since\": stall_since, "
       "\"stall_backoff\": stall_backoff, \"stall_reopens\": stall_reopens, "
       "\"tap\": tap, \"dev\": dev}\n")


def const(name, default):
    m = re.search(r"^%s = ([0-9.]+)" % name, src, re.M)
    if not m:
        MISSING.append("constant %s" % name)
        return default
    return float(m.group(1))


TAP_STALL_S = const("TAP_STALL_S", 8.0)
TAP_STALL_MAX_S = const("TAP_STALL_MAX_S", 60.0)
TRIES = int(const("TAP_STALL_SAME_DEVICE_TRIES", 2))


def run_block(text, args, tag):
    body = "\n".join("        " + l for l in text.splitlines())
    prog = "def run(%s):\n%s    for _once in (0,):\n%s\n%s" % (PARAMS, INIT, body, RET)
    ns = {}
    exec(compile(prog, "<extracted:%s>" % tag, "exec"), ns)
    return ns["run"](**args)


class FakeStream:
    def start(self):
        return None


class FakeTap:
    def __init__(self, target):
        self.rate, self.block = 48000, 4800
        self.stream = FakeStream()
        self.target = target


def inputs(blocks_value, stall_blocks, stall_since, stall_backoff, stall_reopens=0):
    emitted, errs, opened, closed = [], [], [], []
    devs = [{"name": "CABLE Input (WASAPI)", "endpoint_id": "{aaa}", "rung": "a"},
            {"name": "VoiceMeeter Input (WASAPI)", "endpoint_id": "{bbb}", "rung": "a"},
            {"name": "Speakers (WASAPI)", "endpoint_id": "{ccc}", "rung": "a"}]
    args = dict(
        settled=True,
        device_blocks={"value": blocks_value}, now=time.time(),
        seed_stall_blocks=stall_blocks, seed_stall_since=stall_since,
        seed_stall_backoff=stall_backoff, seed_stall_reopens=stall_reopens,
        seed_tap=FakeTap(devs[0]), seed_dev=devs[0],
        err=lambda m: errs.append(m), emit=lambda **kw2: emitted.append(kw2),
        close_tap=lambda t: closed.append(t),
        LoopbackTap=lambda target, on_block, block_ms=0: FakeTap(target),
        tap_holder={"tap": None, "gen": 0}, block_ms=100, on_block=lambda b: None,
        device_candidates=lambda cfg, w: list(devs), audio_cfg={}, wanted=None,
        candidates=list(devs), attempt_no=0, counters={"captions": 6},
        device_peak={"value": 0.9}, time=time, TAP_STALL_S=TAP_STALL_S,
        TAP_STALL_SAME_DEVICE_TRIES=TRIES, TAP_STALL_MAX_S=TAP_STALL_MAX_S)
    return args, emitted, errs, closed


def summarise(emitted, closed, errs):
    states = [(e.get("state"), e.get("reason"), e.get("reopened"), e.get("device")) for e in emitted]
    return "emit=%s closed=%d err=%d" % (states, len(closed), len(errs))


if block:
    a, emitted, errs, closed = inputs(100, 90, time.time() - 1000, TAP_STALL_S)
    run_block(block, a, "arm3")
    arm("ARM 3 no false positive while blocks keep arriving", not emitted and not closed,
        summarise(emitted, closed, errs))

    a, emitted, errs, closed = inputs(59, 59, time.time() - 20, TAP_STALL_S)
    run_block(block, a, "arm4")
    st = [(e.get("state"), e.get("reason")) for e in emitted]
    ok = (("device-rotated", "tap-stalled") in st and ("capture-started", None) in st
          and len(closed) == 1)
    arm("ARM 4 blocks frozen -> re-open in place, no exit", ok, summarise(emitted, closed, errs))

    a, emitted, errs, closed = inputs(59, 59, time.time() - 20, TAP_STALL_S, stall_reopens=TRIES)
    run_block(block, a, "arm4b")
    moved = any(e.get("state") == "capture-started" and e.get("device") != "CABLE Input (WASAPI)" for e in emitted)
    arm("ARM 4b retries spent -> a DIFFERENT endpoint from the fresh enumeration", moved and len(closed) == 1,
        summarise(emitted, closed, errs))

    bl = block.splitlines()
    hit = [i for i, l in enumerate(bl) if l.strip().startswith("elif now - stall_since >= stall_backoff:")]
    if len(hit) != 1:
        MISSING.append("watchdog elif for the negative control (hits=%d)" % len(hit))
        print("FAIL ARM 5: watchdog elif not found for mutation")
    else:
        s = hit[0]
        ind = len(bl[s]) - len(bl[s].lstrip())
        e2 = s + 1
        while e2 < len(bl) and (not bl[e2].strip() or (len(bl[e2]) - len(bl[e2].lstrip())) > ind):
            e2 += 1
        mutant = "\n".join(bl[:s] + bl[e2:])
        a, emitted, errs, closed = inputs(59, 59, time.time() - 20, TAP_STALL_S)
        run_block(mutant, a, "arm5")
        arm("ARM 5 NEGATIVE CONTROL: watchdog deleted -> no recovery", not emitted and not closed,
            "deleted %d lines; " % (e2 - s) + summarise(emitted, closed, errs))

print()
if MISSING:
    print("VERDICT: INSTRUMENT-FAILURE (could not measure: %s)" % "; ".join(MISSING))
    sys.exit(2)
if FAILED:
    print("VERDICT: RED -- %d arm(s) failed: %s" % (len(FAILED), ", ".join(FAILED)))
    sys.exit(3)
print("VERDICT: GREEN -- every arm as expected")
sys.exit(0)
