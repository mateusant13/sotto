"""Integration gate for the idle-tap freeze (owner report 2026-10-12).

THE OWNER'S FAILURE, MEASURED in _main/webview-run.log L93666 (the shell's captured
worker stderr, the only TAP_STALLED line in 103 648):

    TAP_STALLED device='WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)'
      stalled_s=60.0 blocks=0 captions=608 reopens=32
      pump_exited=False pump_hr=0 pump_where=''
      silent_packets=0 gap_packets=0 disco_packets=0

  A pump that is ALIVE, read ZERO packets, and was being rotated away from for the
  33rd time. In the live run (pid 39388) 34 `device-rotated (tap-stalled)` statuses
  landed between evidence_age_s=649 and 3114 -- intervals of 4.4, 5.5, 11, 13, 14,
  16, 17, 18, 21, 22 ... seconds, i.e. the freeze cadence the owner described as
  "uma travada muito forte a cada alguns segundos".

WHY: a settled tap whose `device_blocks` froze was ALWAYS re-opened, even when the
only fact available was "no packets arrived" -- which is exactly what an endpoint
nothing renders into legitimately does (measured:
docs/audit/blank-frames-root-cause.md:154 -- 5 of 6 active render endpoints return
n=0; worker/wasapi_loopback.py:982-984 spins at 5 ms on that branch and never sets
pump_exited).

WHAT THE SHIPPED CODE NOW DOES (added 2026-10-12 by a concurrent lane, verified
here rather than re-delivered): worker/sotto_worker.py::tap_stall_reason classifies
the stall into pump-dead / idle-rearm / endpoint-idle, and the run loop WAITS on
endpoint-idle instead of re-opening. This oracle EXECUTES the extracted run-loop
branch, which the sibling policy oracle does not: that one tests the pure function
and its call site, this one tests the integrated behaviour.

ARMS (each can say NO):
  1 IDLE, INSIDE THE IDLE BOUND -- blocks=0, pump alive, 60 s idle, 0 reopens:
        NO rotation, NO close, NO TAP_STALLED. This is the measured live state.
  2 PUMP DEAD -- pump_exited=True, blocks=0: MUST still rotate, fast, and the
        payload must name reason=pump-dead.
  3 IDLE PAST THE BOUND -- 400 s idle, 0 reopens: rotates ONCE, reason=idle-rearm,
        i.e. the audio may have MOVED and one re-scan is earned.
  4 IDLE PAST THE BOUND, CAPPED -- 400 s idle, 20 reopens: waits, because
        TAP_REOPEN_MAX clients is the run's ceiling.
  5 NO FALSE POSITIVE -- blocks still arriving: nothing happens.
  6 NEGATIVE CONTROL -- the policy replaced by the old always-re-open form, on
        arm 1's inputs: it DOES rotate, so this gate can say NO.

Exit 0 = every arm as expected. 2 = the instrument could not measure.
"""
import re
import sys
import time

WORKER = r"H:\sotto\worker\sotto_worker.py"
FAILED = []
MISSING = []


def arm(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("  " + detail if detail else ""))
    if not ok:
        FAILED.append(name)
    return ok


src = open(WORKER, "r", encoding="utf-8", errors="replace").read()
lines = src.splitlines()

anchor = [i for i, l in enumerate(lines) if l.strip() == "if settled:"]
inc = [i for i, l in enumerate(lines) if l.strip() == 'device_blocks["value"] += 1']
wd = [i for i, l in enumerate(lines)
      if l.strip() == 'if device_blocks["value"] != stall_blocks:']
call = [i for i, l in enumerate(lines)
        if "tap_stall_reason(" in l and not l.lstrip().startswith("def ")]
if len(anchor) != 1 or len(inc) != 1 or len(wd) != 1 or len(call) != 1:
    print("FAIL anchors: settled=%d inc=%d wd=%d policy_call=%d" % (
        len(anchor), len(inc), len(wd), len(call)))
    sys.exit(2)
i0 = anchor[0]
ind0 = len(lines[i0]) - len(lines[i0].lstrip())
i1 = i0 + 1
while i1 < len(lines):
    s = lines[i1]
    if s.strip() and (len(s) - len(s.lstrip())) <= ind0:
        break
    i1 += 1
block = "\n".join(l[ind0:] for l in lines[i0:i1])
print("EXTRACTED settled branch: lines %d-%d (%d lines), policy call at %d" % (
    i0 + 1, i1, i1 - i0, call[0] + 1))
if not (i0 < wd[0] < i1) or not (i0 < call[0] < i1):
    print("FAIL the extracted branch is not the watchdog arm")
    sys.exit(2)

PARAMS = ("settled, device_blocks, now, err, emit, close_tap, LoopbackTap, tap_holder, "
          "block_ms, on_block, device_candidates, audio_cfg, wanted, candidates, "
          "attempt_no, counters, device_peak, time, tap_stall_reason, "
          "TAP_STALL_S, TAP_STALL_SAME_DEVICE_TRIES, TAP_STALL_MAX_S, "
          "TAP_IDLE_MAX_S, TAP_REOPEN_MAX, TAP_REOPEN_MIN_S, "
          "seed_tap, seed_dev, seed_stall_blocks, seed_stall_since, "
          "seed_stall_backoff, seed_stall_reopens, seed_idle_logged")
INIT = ("    tap = seed_tap\n    dev = seed_dev\n"
        "    stall_blocks = seed_stall_blocks\n"
        "    stall_since = seed_stall_since\n"
        "    stall_backoff = seed_stall_backoff\n"
        "    stall_reopens = seed_stall_reopens\n"
        "    idle_logged = seed_idle_logged\n"
        "    tap_source = lambda d: 'device:' + str(d.get('name'))\n"
        "    target_pid = None\n")
RET = ("    return dict(stall_blocks=stall_blocks, stall_since=stall_since, "
       "stall_backoff=stall_backoff, stall_reopens=stall_reopens, "
       "idle_logged=idle_logged, dev=dev)")


def run_block(text, args, tag):
    body = "\n".join("        " + l for l in text.splitlines())
    prog = "def run(%s):\n%s    for _once in (0,):\n%s\n%s" % (
        PARAMS, INIT, body, RET)
    ns = {}
    exec(compile(prog, "<extracted:%s>" % tag, "exec"), ns)
    return ns["run"](**args)


class FakeStream:
    def __init__(self, pump_exited=False, hr=0):
        self.pump_exited = pump_exited
        self.pump_exit_hr = hr
        self.pump_exit_where = ""
        self.silent_packets = 0
        self.position_gap_packets = 0
        self.discontinuity_packets = 0

    def start(self):
        return None


class FakeTap:
    def __init__(self, target, pump_exited=False):
        self.rate, self.block = 48000, 4800
        self.stream = FakeStream(pump_exited)
        self.target = target
        self.source = None


DEVS = [{"name": "CABLE Input (WASAPI)", "endpoint_id": "{aaa}", "rung": "a"},
        {"name": "VoiceMeeter Input (WASAPI)", "endpoint_id": "{bbb}", "rung": "a"},
        {"name": "Speakers (WASAPI)", "endpoint_id": "{ccc}", "rung": "a"}]


def const(name, default):
    m = re.search(r"^%s = ([0-9.]+)" % name, src, re.M)
    if not m:
        MISSING.append("constant %s" % name)
        return default
    return float(m.group(1))


IDLE_MAX = const("TAP_IDLE_MAX_S", 300.0)
REOPEN_MAX = const("TAP_REOPEN_MAX", 20)
REOPEN_MIN = const("TAP_REOPEN_MIN_S", 5.0)
TAP_STALL_S = const("TAP_STALL_S", 8.0)
TAP_STALL_MAX_S = const("TAP_STALL_MAX_S", 60.0)
TRIES = int(const("TAP_STALL_SAME_DEVICE_TRIES", 2))
print("NOTE TAP_STALL_S=%s MAX=%s TRIES=%s IDLE_MAX=%s REOPEN_MAX=%s REOPEN_MIN=%s" % (
    TAP_STALL_S, TAP_STALL_MAX_S, TRIES, IDLE_MAX, REOPEN_MAX, REOPEN_MIN))


def policy(pump_exited, idle_s, reopens):
    """The SHIPPED policy, transcribed from the worker source. ARM 6 builds a
    mutant from this same text, so the two cannot drift apart."""
    if pump_exited:
        return "pump-dead"
    if idle_s >= IDLE_MAX and reopens < REOPEN_MAX:
        return "idle-rearm"
    return "endpoint-idle"


def inputs(blocks_value, stall_blocks, frozen_s, backoff, reopens=0,
           pump_exited=False, idle_logged=False):
    emitted, errs, closed = [], [], []
    args = dict(
        settled=True, device_blocks={"value": blocks_value},
        now=time.time(),
        seed_stall_blocks=stall_blocks,
        seed_stall_since=time.time() - frozen_s,
        seed_stall_backoff=backoff, seed_stall_reopens=reopens,
        seed_idle_logged=idle_logged,
        seed_tap=FakeTap(DEVS[0], pump_exited), seed_dev=DEVS[0],
        err=lambda m: errs.append(m),
        emit=lambda **kw: emitted.append(kw),
        close_tap=lambda t: closed.append(t),
        LoopbackTap=lambda target, on_block, block_ms=0: FakeTap(target),
        tap_holder={"tap": None, "gen": 0}, block_ms=100,
        on_block=lambda b: None,
        device_candidates=lambda cfg, w, target_pid=None: list(DEVS),
        audio_cfg={}, wanted=None, candidates=list(DEVS), attempt_no=0,
        counters={"captions": 608}, device_peak={"value": 0.9}, time=time,
        tap_stall_reason=policy,
        TAP_STALL_S=TAP_STALL_S, TAP_STALL_SAME_DEVICE_TRIES=TRIES,
        TAP_STALL_MAX_S=TAP_STALL_MAX_S, TAP_IDLE_MAX_S=IDLE_MAX,
        TAP_REOPEN_MAX=REOPEN_MAX, TAP_REOPEN_MIN_S=REOPEN_MIN)
    return args, emitted, errs, closed


def summarise(emitted, closed, errs):
    st = [(e.get("state"), e.get("reason"), e.get("reopened")) for e in emitted]
    return "emit=%s closed=%d err=%d" % (st, len(closed), len(errs))


def rotations(emitted):
    return [e for e in emitted if e.get("state") == "device-rotated"]

# ARM 1 -- idle inside the bound: THE FIX
a, e_, r_, c_ = inputs(0, 0, 60.0, TAP_STALL_S)
run_block(block, a, "arm1")
arm("1 idle (blocks=0, pump alive, 60 s, 0 reopens) -> NO rotation, NO close",
    not e_ and not c_ and not r_, summarise(e_, c_, r_))

# ARM 2 -- a pump that broke is still cured
a, e_, r_, c_ = inputs(0, 0, 20.0, TAP_STALL_S, pump_exited=True)
run_block(block, a, "arm2")
rot = rotations(e_)
re_ = [x for x in e_ if x.get("state") == "capture-started"]
arm("2 pump dead -> rotates, reason=pump-dead, capture-started reopened=True",
    len(rot) == 1 and rot[0].get("reason") == "pump-dead"
    and len(re_) == 1 and re_[0].get("reopened") is True and len(c_) == 1,
    summarise(e_, c_, r_))

# ARM 3 -- idle past the bound earns ONE re-scan
a, e_, r_, c_ = inputs(0, 0, IDLE_MAX + 100.0, TAP_STALL_S)
run_block(block, a, "arm3")
rot = rotations(e_)
arm("3 idle past the bound (400 s) -> rotates once, reason=idle-rearm",
    len(rot) == 1 and rot[0].get("reason") == "idle-rearm" and len(c_) == 1,
    summarise(e_, c_, r_))

# ARM 4 -- ...but the run's client ceiling is honoured
a, e_, r_, c_ = inputs(0, 0, IDLE_MAX + 100.0, TAP_STALL_S, reopens=REOPEN_MAX)
run_block(block, a, "arm4")
arm("4 idle past the bound but capped (20 reopens) -> waits",
    not e_ and not c_, summarise(e_, c_, r_))

# ARM 5 -- no false positive while blocks keep arriving
a, e_, r_, c_ = inputs(100, 90, 1000.0, TAP_STALL_S)
run_block(block, a, "arm5")
arm("5 blocks still arriving -> nothing happens",
    not e_ and not c_ and not r_, summarise(e_, c_, r_))

# ARM 6 -- NEGATIVE CONTROL: the old always-re-open policy DOES rotate.
# The extracted block holds the CALL SITE, not the function body, so the
# mutant replaces the call with the pre-patch unconditional re-open.
OLD = "stall_reason = tap_stall_reason(client_dead, stalled_s, stall_reopens)"
NEW = "stall_reason = \"pump-dead\""
mutant = block.replace(OLD, NEW, 1)
if mutant == block:
    print("FAIL the policy call site moved; the mutant did not land")
    sys.exit(2)
a, e_, r_, c_ = inputs(0, 0, 60.0, TAP_STALL_S)
run_block(mutant, a, "arm6")
rot = rotations(e_)
arm("6 NEGATIVE CONTROL: the pre-patch policy rotates on arm 1's inputs",
    len(rot) == 1 and len(c_) == 1, summarise(e_, c_, r_))

print()
if MISSING:
    print("VERDICT: INSTRUMENT-FAILURE (could not measure: %s)" % "; ".join(MISSING))
    sys.exit(2)
if FAILED:
    print("VERDICT: RED -- %d arm(s) failed: %s" % (len(FAILED), ", ".join(FAILED)))
    sys.exit(3)
print("VERDICT: GREEN -- every arm as expected")
sys.exit(0)
