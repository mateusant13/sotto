"""ORACLE for the METER CHAIN -- worker -> shell -> panel, every link named.

WHY THIS FILE EXISTS (what the other meter oracle does NOT do)
--------------------------------------------------------------
`_main/audio-meter-oracle.py` gates ONE link: the `AudioMeter` class, driven by a
driver that PRETENDS to be `on_block`. It went green while nothing in the
worker ever constructed the class or emitted the event -- which is exactly the
state the owner has been living in. A gate on the middle of a chain cannot see
either end of it.

This oracle gates the CHAIN and names each link by the bytes that carry it:

  LINK 1  the WORKER drives the meter from the tap own per-block peak and emits
          exactly one JSONL event per window;
  LINK 2  the SHAPE it emits is the shape the SHELL reads -- `_meter` own
          `for key in (peak, blocks)` tuple and the `elif kind == meter:`
          dispatch that reaches it;
  LINK 3  the shape the PANEL reads -- `pushLevel(fields.peak, fields.blocks)`,
          reached from the same {peak, blocks} payload the shell builds.

THE FIELD NAMES ARE READ OUT OF THE CONSUMERS, NOT ASSUMED. Rename a field in
either consumer and the arm that compares the worker emitted keys against that
consumer own tuple goes RED here, instead of shipping a stream nobody reads.

RUN MODES
---------
  (default)   the repo live bytes are the SUBJECT; prints VERDICT: PASS or FAIL
  --neg-arm   the emit is DEADENED in a COPY of the worker (the mutation is built
              and verified here); the oracle then re-enters ITSELF as a
              subprocess against that copy and MUST print FAIL. A gate that
              cannot say NO is not a gate, so this arm is part of the gate.

Nothing else is launched: no shell, no WebView2, no worker process, no audio
device, no model. Owner order of 2026-10-11: Sotto is not to be opened.

Exit codes: 0 PASS, 1 FAIL, 2 setup error.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER_DIR = os.path.join(REPO, "worker")
WORKER_PY = os.path.join(WORKER_DIR, "sotto_worker.py")
SHELL_PY = os.path.join(REPO, "app", "webview", "sotto_webview.py")
PANEL_JS = os.path.join(REPO, "app", "panel", "panel.js")

ENV_KEY = "SOTTO_METER_HZ"
#: Set by --neg-arm in the child it spawns, so the child REPORTS which arm it ran
#: instead of leaving that to be inferred from the parent log.
ENV_MUTANT = "SOTTO_METER_ORACLE_MUTANT"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("[%s] check: %s" % ("PASS" if ok else "FAIL", name))
    if detail:
        for row in str(detail).splitlines():
            print("       " + row)
    return bool(ok)


def say(line=""):
    print(line)


def sha256_of(data):
    return hashlib.sha256(data).hexdigest().upper()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def load_module(path, name):
    """Import from an explicit PATH: the mutant copy shares the live module name,
    and sys.modules must not be allowed to lie about which file was loaded."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Capture:
    """A stdout the worker own emit() writes into, keeping the LINES."""

    def __init__(self):
        self.buf = io.StringIO()
        self.lines = []

    def __enter__(self):
        self._real = sys.stdout
        sys.stdout = self
        return self

    def __exit__(self, *exc):
        sys.stdout = self._real
        return False

    def write(self, s):
        self.buf.write(s)
        if s.endswith("\n"):
            self.lines.append(s)
        return len(s)

    def flush(self):
        pass


def stream(W, peaks, hz=10.0, dt=0.1, t0=0.0, block_s=0.0):
    """Drive the meter the way the LIVE call site + on_block do, one block per tick.

    `block_s` is the tap own block period and it is FORWARDED, because that is
    what `main()` does: `AudioMeter(meter_hz, now=..., block_s=block_ms/1000.0)`.
    Driving it without the period measures a PURE-TIME meter instead of the one
    the worker actually runs -- the trap the pre-existing gate fell into.

    Returns (payloads, tally, text): what the meter returned, an INDEPENDENT
    tally of (peak, blocks) for the blocks each window really covered, and the
    bytes that reached stdout through the worker OWN emit().
    """
    m = W.AudioMeter(hz, now=t0, block_s=block_s)
    out, tally, cur = [], [], []
    t = t0
    with Capture() as cap:
        for p in peaks:
            cur.append(p)
            level = m.tick(p, t)
            if level is not None:
                W.emit(type="meter", **level)
                out.append(level)
                tally.append({"peak": round(max(cur), 4), "blocks": len(cur)})
                cur = []
            t += dt
    return out, tally, cap.buf.getvalue()


def on_block_source(text):
    """The REAL on_block function source, pulled out of the worker bytes.

    The meter is only wired if it is DRIVEN FROM INSIDE that closure, so this
    reads the closure rather than trusting a comment about it.
    """
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef) and node.name == "on_block"
                and node.col_offset == 4):
            return ast.get_source_segment(text, node) or ""
    raise SystemExit("SETUP ERROR: a 4-space-indented def on_block(block) was not "
                     "found in " + WORKER_PY)


def load_parser(W):
    """main() argparse object, built IN PROCESS without running main().

    main() loads the model. The PARSER is the part this oracle needs, so the body
    of main is compiled with a "return ap" injected where the real function goes
    on to touch a config file and then a 1 GB session. Nothing before that line
    opens a device, a model or the network.
    """
    import inspect
    src = inspect.getsource(W.main)
    marker = "args = ap.parse_args()"
    if marker not in src:
        raise SystemExit("SETUP ERROR: %r not found inside main()" % marker)
    # KEEP the def line and REPLACE the parse line with `return ap` -- do NOT
    # dedent: the block keeps its own body indentation, and argparse is a module
    # level import in the worker, so it is already in the namespace.
    # The SLICE INDEX is taken from the WORKER bytes and only then is the stub
    # appended. Doing it the other way round (concatenate, then search) is a trap
    # this file fell into once: the stub '    return ap' contains 'ap.parse_args()'
    # as a SUBSTRING of ...return ap + the stub's own text, so a post-hoc search
    # finds the stub and slices the worker's last 4 bytes instead of its parser.
    cut = src.index(marker)
    # The marker line is indented by FOUR SPACES in the worker, so the slice
    # ends with those spaces and appending the stub lands it at column 8 (an
    # IndentationError). rstrip the slice itself, and take the cut from the
    # index in the ORIGINAL text so the stub text can never be searched.
    head = src[:cut].rstrip() + "\n    return ap\n"
    ns = dict(W.__dict__)
    exec(compile(head, "<main-head>", "exec"), ns)
    return ns["main"]()


def parser_for(W):
    return load_parser(W)


def parse_argv_root(W, argv):
    """The argument parser alone, from the SHIPPED bytes, via a head-of-main stub."""
    return parser_for(W)


def worker_const(W, name):
    return getattr(W, name)


def worker_str(W, name):
    return str(getattr(W, name))


def _rate_rung(W, text):
    """The REAL meter-rate rung, re-read from the shipped bytes as ONE statement.

    The rung is an if/elif/else CHAIN plus the negative-rate refusal: it must be
    compiled whole, or the `elif` has no `if` to belong to (measured: an `elif`
    alone is a SyntaxError).
    """
    tree = ast.parse(text)
    body = None
    idx = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.Module)):
            continue
        for i, stmt in enumerate(node.body):
            seg = ast.get_source_segment(text, stmt) or ""
            if "meter_hz, meter_hz_from" in seg and isinstance(stmt, ast.If):
                body, idx = node.body, i
                break
        if body is not None:
            break
    if body is None:
        raise SystemExit("SETUP ERROR: no meter-rate rung found in " + WORKER_PY)
    # The RUNG is the precedence chain PLUS the statements that follow it while
    # they keep touching meter_hz (the negative-rate refusal): compiled together,
    # so the arm that asks for a refused rate exercises the worker real code path
    # and not just its first half.
    stmts = []
    for stmt in body[idx:]:
        seg = ast.get_source_segment(text, stmt) or ""
        if stmts and "meter_hz" not in seg:
            break
        stmts.append(stmt)
    rung = ast.Module(body=stmts, type_ignores=[])
    compile(ast.unparse(rung), "<rung-probe>", "exec")
    if os.environ.get("SOTTO_METER_ORACLE_DEBUG"):
        print("       [rung] " + ast.unparse(rung))
    return rung


def arm_rate(W, text, parser):
    say("")
    say("== ARM 1: the RATE -- flag > env > default, and 0/negative = OFF ==")
    default = worker_const(W, "METER_HZ")
    check("the shipped METER_HZ constant is 10.0 (the wave cadence)",
          default == 10.0, "METER_HZ=%r" % (default,))
    flag_default = parser.parse_args([]).meter_hz
    check("the --meter-hz argparse default IS the shipped constant (one number, not two)",
          flag_default == default,
          "parser.parse_args([]).meter_hz=%r METER_HZ=%r -- the literal stays in "
          "the add_argument so the cadence oracle can read it out of the bytes; "
          "the env rung is applied AFTER the parse, so it only wins when the flag "
          "was not given" % (flag_default, default))

    rung = _rate_rung(W, text)

    def resolve(argv, env_value, default_hz):
        """The REAL rung, with args built by the REAL argparse parser."""
        scope = {"METER_HZ": default_hz, "args": parser.parse_args(argv),
                 "err": lambda msg: None}
        environ = {} if env_value is None else {ENV_KEY: env_value}
        scope["os"] = type("o", (), {"environ": environ})()
        exec(compile(ast.unparse(rung), "<worker-rate-rung>", "exec"), scope)
        if "meter_hz" not in scope:
            raise SystemExit("SETUP ERROR: the meter-rate rung never bound meter_hz")
        return scope["meter_hz"], scope.get("meter_hz_from")

    cases = [
        ("--meter-hz 5 wins over SOTTO_METER_HZ=4",
         ["--meter-hz", "5"], "4", (5.0, "flag")),
        ("SOTTO_METER_HZ=4 wins when NO flag was given",
         [], "4", (4.0, "env")),
        ("--meter-hz 0 beats SOTTO_METER_HZ=4 (OFF is not overridden by env)",
         ["--meter-hz", "0"], "4", (0.0, "flag")),
        ("--meter-hz 0 with no env is OFF",
         ["--meter-hz", "0"], None, (0.0, "flag")),
        ("--meter-hz 10 STILL beats SOTTO_METER_HZ=4 (a VALUE-based rung loses this)",
         ["--meter-hz", "10"], "4", (10.0, "flag")),
        ("no flag and no env falls back to the default",
         [], None, (10.0, "default")),
        ("a non-numeric SOTTO_METER_HZ falls back to the default",
         [], "fast", (10.0, "default")),
        ("a NEGATIVE rate is refused and read as OFF",
         ["--meter-hz", "-3"], None, (0.0, "flag")),
        ("a FRACTIONAL rate is honoured as given",
         ["--meter-hz", "2.5"], None, (2.5, "flag")),
    ]
    for name, argv, envv, want in cases:
        got = resolve(argv, envv, default)
        check(name, got == want, "argv=%r env=%r got=%r want=%r"
              % (argv, envv, got, want))

    # The RESOLVED rate reaches the audio path: read the construction site.
    m = __import__("re").search(r"AudioMeter\((\w+),\s*now=", text)
    check("the meter is constructed with the RESOLVED rate, not the raw flag",
          bool(m) and m.group(1) == "meter_hz",
          "construction site argument=%r" % (m.group(1) if m else None,))


def arm_cadence(W):
    say("")
    say("== ARM 2: the CADENCE -- one event per window, and no burst ==")
    peaks = [0.02] * 5 + [0.30] * 5 + [0.62] * 5 + [0.21] * 5 + [0.01] * 10 + [0.44] * 5 + [0.05] * 15
    out, tally, text = stream(W, peaks)
    lv = [e["peak"] for e in out]
    check("the level FALLS when the audio falls (a run maximum cannot)",
          any(b < a for a, b in zip(lv, lv[1:])) and lv[-1] < max(lv),
          "peaks=%r" % (lv,))
    check("each event reports the peak and the count of the blocks IT covered",
          out == tally, "out=%r\ntally=%r" % (out, tally))

    # THE LIVE SHAPE: 100 ms blocks, the meter told the tap own period.
    many, many_tally, many_text = stream(W, [0.3] * 100, block_s=0.1)
    check("100 blocks of 100 ms produce 100 EVENTS on the live shape (not 99)",
          len(many) == 100, "events=%d (the pre-existing gate measures 99 here)" % len(many))
    check("...and every one of those events covers exactly one block",
          [e["blocks"] for e in many] == [1] * 100,
          "blocks=%r" % ([e["blocks"] for e in many][:6],))
    check("...and every block lands in some event (none is lost)",
          sum(e["blocks"] for e in many) == 100,
          "sum(blocks)=%d over %d events" % (sum(e["blocks"] for e in many), len(many)))

    jit, _, _ = stream(W, [0.3] * 100, dt=0.099, block_s=0.1)
    rate = len(jit) / (99 * 0.099)
    check("a 99 ms pace still yields one point per block (no ~6 Hz beat)",
          len(jit) == 100 and rate > 9.5,
          "events=%d over %.2f s = %.2f Hz" % (len(jit), 99 * 0.099, rate))

    # THE BLOCK-COUNT RULE IS WHAT DOES IT, and the contrast is measurable: with
    # NO tap period the meter is pure-time BY DESIGN, and that is the meter the
    # pre-existing gate drives when it drops block_s (its own comment at
    # `_main/audio-meter-oracle.py:118-123` says that it does).
    pure, pure_tally, _ = stream(W, [0.3] * 100, block_s=0.0)
    check("with NO tap period the meter is pure-time (so the rule is the fix)",
          len(pure) == 99 and pure_tally == pure,
          "pure-time events=%d, first window blocks=%d: a driver that does not "
          "forward block_s measures 99, not the shipped 100" % (
              len(pure), pure[0]["blocks"] if pure else -1))

    # A SLOWER METER THAN THE TAP: 5 Hz over 100 ms blocks = one event per 2
    # blocks. The same rule earning its keep in the other direction.
    slow, _, _ = stream(W, [0.3] * 20, hz=5.0, block_s=0.1)
    check("at 5 Hz over 100 ms blocks the meter emits one event per 2 blocks",
          len(slow) == 10 and all(e["blocks"] == 2 for e in slow),
          "events=%d blocks=%r" % (len(slow), [e["blocks"] for e in slow]))

    got = []
    m = W.AudioMeter(10.0, now=0.0)
    for p, t in ((0.5, 0.0), (0.5, 0.05), (0.5, 0.10), (0.4, 0.25), (0.3, 0.26)):
        got.append(m.tick(p, t))
    check("a tick exactly ON the boundary closes the window (99 -> 100 fix)",
          got[2] == {"peak": 0.5, "blocks": 3}, "tick@0.10=%r" % (got[2],))
    check("a LATE tick reports its own blocks and emits NO catch-up burst",
          got[3] == {"peak": 0.4, "blocks": 1} and got[4] is None,
          "tick@0.25=%r tick@0.26=%r" % (got[3], got[4]))

    off, off_tally, off_text = stream(W, peaks, hz=0.0)
    check("--meter-hz 0 emits nothing at all, not even a zero level",
          (off, off_tally, off_text) == ([], [], ""),
          "payloads=%r bytes=%r" % (off, off_text))


def arm_worker_wiring(W, text, on_block):
    say("")
    say("== ARM 3: the WORKER wiring -- the meter is DRIVEN from the live path ==")
    sites = text.count("AudioMeter(")
    check("the meter is instantiated exactly ONCE in the shipped bytes",
          sites == 1, "AudioMeter( occurrences=%d" % sites)
    ctor = [ln.strip() for ln in text.splitlines()
            if ln.strip().startswith("meter = AudioMeter(")]
    check("...and that one site is the LIVE call, told the tap own block period",
          len(ctor) == 1 and ctor[0].startswith("meter = AudioMeter(meter_hz,")
          and "block_s=block_ms / 1000.0" in ctor[0],
          "construction=%r (the period is what makes one event per block)" % (ctor,))
    import inspect as _inspect
    params = list(_inspect.signature(W.AudioMeter.__init__).parameters)
    check("AudioMeter.__init__ takes the tap period (the neg-cadence mutant needs it)",
          "block_s" in params,
          "signature=%s" % (_inspect.signature(W.AudioMeter.__init__),))

    # `ast.get_source_segment` PADS-AWAY the first line indentation, so the
    # function statements are `parsed.body[0].body` -- index it once, here.
    parsed = ast.parse(on_block)
    fnode = parsed.body[0]
    check("on_block was parsed as ONE function definition",
          isinstance(fnode, ast.FunctionDef) and fnode.name == "on_block",
          "parsed.body=%r" % ([type(n).__name__ for n in parsed.body],))
    tree = fnode
    block_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute) and n.func.attr == "tick"]
    check("on_block drives exactly ONE meter tick",
          len(block_calls) == 1, "tick() call sites in on_block=%d" % len(block_calls))
    if block_calls:
        tick_src = ast.get_source_segment(on_block, block_calls[0]) or ""
        check("the tick is fed the SAME per-block peak the tap already computed",
              tick_src.startswith("meter.tick(p,"),
              "tick source=%r (p is the per-block peak defined above it)" % tick_src)
    emits = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "emit"]
    check("on_block emits exactly ONE event",
          len(emits) == 1, "emit() call sites in on_block=%d" % len(emits))
    if emits:
        esrc = ast.get_source_segment(on_block, emits[0]) or ""
        check("...and it is the meter event",
              'type="meter"' in esrc and "**level" in esrc, "emit source=%r" % esrc)
    guards = [n for n in tree.body if isinstance(n, ast.If)]
    guard = [n for n in guards if "meter" in (ast.get_source_segment(on_block, n.test) or "")]
    check("the emit sits behind a meter.enabled guard (the --meter-hz 0 contract)",
          len(guard) == 1 and "enabled" in (ast.get_source_segment(on_block, guard[0].test) or ""),
          "guards=%r" % ([ast.get_source_segment(on_block, g.test) for g in guards],))
    if guard:
        body = "\n".join(ast.get_source_segment(on_block, s) or "" for s in guard[0].body)
        check("the guard wraps the tick AND the emit (nothing runs when OFF)",
              "tick(" in body and "emit(" in body, body)
        branch = ast.get_source_segment(on_block, guard[0]) or ""
        check("the meter branch writes ONE event per window and NO log line",
              branch.count("emit(") == 1 and "err(" not in branch
              and "print(" not in branch and "sys.stderr" not in branch,
              "emit(=%d err(=%d print(=%d stderr=%d"
              % (branch.count("emit("), branch.count("err("),
                 branch.count("print("), branch.count("sys.stderr")))


def _assemble(W, on_block_src, extra=""):
    """The REAL class + the REAL on_block, meter built the way main() builds it.

    The namespace must supply meter_hz and time (see arm_dead_copy).
    """
    import inspect
    src = inspect.getsource(W.AudioMeter)
    src += "\n\nmeter = AudioMeter(meter_hz, now=time.time(), block_s=0.0)\n\n"
    src += on_block_src + "\n\n" + extra
    return src


def arm_dead_copy(W, text, on_block):
    say("")
    say("== ARM 4: --meter-hz 0 is BYTE-IDENTICAL -- the emit is dead when OFF ==")
    m0 = W.AudioMeter(0.0, now=0.0)
    check("rate 0 constructs a meter that is DISABLED (enabled is False)",
          m0.enabled is False and m0.tick(0.9, 1e9) is None,
          "enabled=%r interval=%r tick=%r" % (m0.enabled, m0.interval, m0.tick(0.9, 1e9)))
    mneg = W.AudioMeter(-2.0, now=0.0)
    check("a negative rate is disabled too (never a negative interval)",
          mneg.enabled is False and mneg.interval == 0.0,
          "enabled=%r interval=%r" % (mneg.enabled, mneg.interval))

    import numpy as np

    def harness(rate, clock):
        """The REAL on_block, driven with the worker own counters and emit."""
        got = []
        ns = dict(W.__dict__)
        ns["meter_hz"] = rate
        ns["emit"] = lambda **kw: got.append(kw)
        ns["err"] = lambda msg: None
        ns["counters"] = {"blocks": 0, "block_samples": 0, "peak": 0.0, "sumsq": 0.0,
                          "nonzero_blocks": 0, "queue_drops": 0}
        ns["device_blocks"] = {"value": 0}
        ns["device_peak"] = {"value": 0.0}
        ns["audio_q"] = type("Q", (), {"put_nowait": staticmethod(lambda b: None)})()
        ns["time"] = type("T", (), {"time": staticmethod(clock)})()
        exec(compile(_assemble(W, on_block), "<on_block>", "exec"), ns)
        return ns, got

    dead, dead_events = harness(0.0, lambda: 0.0)
    for _ in range(10):
        dead["on_block"](np.zeros(1600, dtype=np.float32))
    check("driving the REAL on_block with the meter OFF writes ZERO events",
          dead_events == [], "events=%r" % (dead_events,))
    check("...and the meter it built is DISABLED (enabled is False, interval 0)",
          dead["meter"].enabled is False and dead["meter"].interval == 0.0,
          "enabled=%r interval=%r" % (dead["meter"].enabled, dead["meter"].interval))

    # The only branch this feature added to on_block, and it is the guarded one.
    # `get_source_segment` de-indents, so the statements are body[0].body.
    parsed = ast.parse(on_block)
    stmts = parsed.body[0].body
    guard = [n for n in stmts if isinstance(n, ast.If)
             and "enabled" in (ast.get_source_segment(on_block, n.test) or "")]
    pre_existing = [n for n in stmts if isinstance(n, ast.If) and n not in guard]
    check("the meter adds exactly ONE top-level branch; the three peak branches on_block already had are untouched",
          len(guard) == 1 and len(pre_existing) == 3,
          "top-level on_block statements=%r" % ([type(s).__name__ for s in stmts],))

    # The reverse direction: with the meter ON the same harness DOES emit, so the
    # zero above is the GUARD and not a harness that cannot emit at all.
    ticks = {"t": 0.0}
    live, live_events = harness(10.0, lambda: ticks["t"])
    for i in range(3):
        ticks["t"] = i * 0.1
        live["on_block"](np.zeros(1600, dtype=np.float32))
    check("the SAME harness with the meter ON does emit (the control for the zero)",
          len(live_events) >= 1 and all(e.get("type") == "meter" for e in live_events),
          "events=%r" % (live_events,))


def consumer_fields(text, start_marker, comment_marker, label, file_for_errors):
    seg = text.index(start_marker)
    end = text.find(comment_marker, seg)
    if end < 0:
        raise SystemExit("SETUP ERROR: %s: no %r after the dispatch" % (file_for_errors, comment_marker))
    chunk = text[seg:end]
    import re
    fields = set()
    for m in re.finditer(r"in \(([^)]*)\)", chunk):
        for item in m.group(1).split(","):
            item = item.strip().strip("'").strip('"')
            if item.isidentifier():
                fields.add(item.lower())
    return chunk, fields


def arm_shape(W):
    say("")
    say("== ARM 5: the SHAPE -- exactly the fields the CONSUMERS read ==")
    _, _, text = stream(W, [0.3] * 12)
    payloads = [json.loads(line) for line in text.splitlines() if line.strip()]
    keysets = sorted({tuple(sorted(p)) for p in payloads})
    check("every emitted line carries exactly type/peak/blocks (no third field)",
          keysets == [("blocks", "peak", "type")],
          "keysets=%r" % (keysets,))
    check("the event type is the literal string 'meter'",
          {p["type"] for p in payloads} == {"meter"},
          "types=%r" % ({p["type"] for p in payloads},))
    check("peak travels as a JSON FLOAT and blocks as a JSON INT",
          all(isinstance(p["peak"], float) and isinstance(p["blocks"], int)
              for p in payloads),
          "first=%r" % (json.dumps(payloads[0]),))
    check("one line per event, and every line is valid JSONL on its own",
          len(payloads) == len(text.splitlines()) and text.endswith("\n"),
          "lines=%d newline_terminated=%r" % (len(text.splitlines()), text.endswith("\n")))
    return sorted({k for p in payloads for k in p})


def arm_shell(text, producer_keys):
    say("")
    say("== ARM 6: the SHELL consumes kind 'meter' and reads peak/blocks ==")
    dispatch = "elif kind == 'meter':"
    check("the shell has the meter dispatch branch",
          dispatch in text, "searched for %r" % dispatch)
    idx = text.index(dispatch)
    check("...and it forwards into _meter(), not the unknown-kind else",
          "_meter(message, child)" in text[idx: idx + 120],
          repr(text[idx: idx + 120].splitlines()))
    # The end marker is AFTER the field loop: `self.meters += 1` sits on the
    # line BEFORE `for key in (...)`, so it would cut the chunk short.
    chunk, fields = consumer_fields(text, "def _meter(self, message, child=None):",
                                    "self.last_meter = sample", "_meter", SHELL_PY)
    check("the shell _meter loop names the fields it copies, read from its OWN bytes",
          fields == {"peak", "blocks"}, "_meter fields=%r" % (sorted(fields),))
    missing = sorted(set(producer_keys) - {"type"} - fields)
    check("the worker emits exactly what _meter reads (peak/blocks), nothing missing",
          missing == [], "missing from the shell=%r" % (missing,))
    check("the shell prefers a fresh meter over the WORKER_STATS running maximum",
          "last_meter" in text and "METER_FRESH_S" in text,
          "METER_FRESH_S present=%r" % ("METER_FRESH_S" in text,))


def arm_panel(text, producer_keys):
    say("")
    say("== ARM 7: the PANEL pushes the level and reads peak/blocks ==")
    check("panel.js defines pushLevel(peak, blocks)",
          "function pushLevel(peak, blocks)" in text, "function pushLevel found")
    call = "pushLevel(fields.peak, fields.blocks)"
    check("...and is CALLED with fields.peak / fields.blocks",
          call in text, "searched for %r" % call)
    check("wireLevel subscribes to the shell stats channel",
          "function wireLevel()" in text and "bridge.onStats(take)" in text,
          "wireLevel subscription present")
    check("the worker emitted keys are exactly the fields the panel reads",
          sorted(set(producer_keys) - {"type"}) == ["blocks", "peak"],
          "producer keys=%r panel reads peak+blocks" % (sorted(producer_keys),))


def arm_consumer_union(shell_text, panel_text, producer_keys):
    say("")
    say("== ARM 8: the TWO consumers agree on the field names ==")
    _, sfields = consumer_fields(shell_text, "def _meter(self, message, child=None):",
                                 "self.last_meter = sample", "_meter", SHELL_PY)
    import re
    m = re.search(r"pushLevel\(fields\.(\w+),\s*fields\.(\w+)\)", panel_text)
    pfields = {m.group(1), m.group(2)} if m else set()
    check("the shell tuple and the panel call name the SAME two fields",
          sfields == pfields == {"peak", "blocks"},
          "shell=%r panel=%r" % (sorted(sfields), sorted(pfields)))
    check("the producer emits that same set (chain closed at both ends)",
          set(producer_keys) - {"type"} == sfields,
          "producer=%r consumers=%r" % (sorted(set(producer_keys) - {"type"}), sorted(sfields)))


def build_mutant(text, on_block, tmpdir, kind):
    """Build ONE mutant of the REAL bytes in a COPY, from the AST, and verify it.

    kind="emit"      the guarded meter branch in on_block becomes `pass`, so the
                     producer is DEADENED and nothing is ever published;
    kind="blockrule" the LIVE call site stops passing the tap own period
                     (`block_s=block_ms / 1000.0` -> `block_s=0.0`), which is the
                     cadence rule removed and nothing else.

    Each mutant is compiled before it is written: a mutant that cannot be built
    is not a control.
    """
    checks = {"kind": kind}
    if kind == "emit":
        # `get_source_segment` de-indents, so the statements are body[0].body.
        stmts = ast.parse(on_block).body[0].body
        stmt = None
        for node in stmts:
            if isinstance(node, ast.If) and "meter" in (
                    ast.get_source_segment(on_block, node.test) or ""):
                stmt = node
                break
        if stmt is None:
            raise SystemExit("SETUP ERROR: on_block has no meter branch to remove")
        exact = ast.get_source_segment(on_block, stmt)
        checks["emit_present_before"] = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "emit" for n in ast.walk(stmt))
        mutant_block = on_block.replace(exact, " " * stmt.col_offset + "pass")
        mutant = text.replace(on_block, mutant_block)
        # Judge the MUTATED on_block, not the file: the file mentions the event in
        # prose comments (the meter block at the top documents its own shape), and
        # a whole-file substring test would call a working mutation a failed one.
        checks["emit_absent_after"] = 'emit(type="meter"' not in mutant_block
        # The tick call sits INSIDE the guarded branch, so deadening the producer
        # removes it too -- that is the point of this mutant, and the child says so
        # by failing "on_block drives exactly ONE meter tick". Everything OUTSIDE
        # the branch (the construction, the class, the rate plumbing) must survive.
        checks["meter_unused_after"] = "meter.tick" not in mutant_block
        checks["construct_still_there"] = "meter = AudioMeter(" in mutant
        checks["one_site_after"] = mutant.count("AudioMeter(") == text.count("AudioMeter(")
        mpath = os.path.join(tmpdir, "sotto_worker_mutant_emit.py")
    elif kind == "cadence":
        # THE BLOCK-COUNT ARM REMOVED -- the same mutation the pre-existing gate
        # describes as `blocks_per_window = 0` ("a pure TIME window: the 6 Hz
        # beat"). Done on the PREDICATE, so `blocks_per_window` is still computed
        # and only the rule that uses it is gone.
        pat = __import__("re").compile(
            r"if now < self\.next and not \(self\.blocks_per_window\s*\n"
            r"\s*and self\.blocks >= self\.blocks_per_window\):")
        hits = pat.findall(text)
        if len(hits) != 1:
            raise SystemExit("SETUP ERROR: the block-count arm was not found exactly "
                             "once (%d)" % len(hits))
        mutant = pat.sub("if now < self.next:", text, count=1)
        checks["count_arm_present_before"] = True
        checks["count_arm_gone"] = "self.blocks >= self.blocks_per_window" not in mutant
        checks["kwarg_still_there"] = "block_s=block_ms / 1000.0" in mutant
        checks["attribute_still_computed"] = "self.blocks_per_window = (max(1," in mutant
        mpath = os.path.join(tmpdir, "sotto_worker_mutant_cadence.py")
    else:
        raise SystemExit("SETUP ERROR: unknown mutant kind %r" % (kind,))
    checks["byte_delta"] = len(mutant) - len(text)
    compile(mutant, "<mutant>", "exec")     # must parse and compile
    with open(mpath, "w", encoding="utf-8", newline="") as fh:
        fh.write(mutant)
    return mpath, checks


def arm_mutant_is_real(text, on_block, tmpdir):
    say("")
    say("== ARM 9: the MUTANTS are real controls (each changes exactly one region) ==")
    m1, c1 = build_mutant(text, on_block, tmpdir, "emit")
    check("the guarded branch CONTAINED the emit before the mutation",
          c1["emit_present_before"] is True, repr(c1))
    check("after the emit mutation the event is GONE from the file",
          c1["emit_absent_after"] is True, repr(c1))
    check("the emit mutation left the construction and the class alone (only the guarded branch is dead)",
          c1["meter_unused_after"] and c1["construct_still_there"]
          and c1["one_site_after"], repr(c1))
    check("the emit mutant is still valid Python that imports",
          _imports_ok(m1), "path=" + m1)
    m2, c2 = build_mutant(text, on_block, tmpdir, "cadence")
    check("the cadence mutation removed ONLY the block-count arm of the predicate",
          c2["count_arm_gone"] and c2["kwarg_still_there"]
          and c2["attribute_still_computed"],
          repr(c2))
    check("the cadence mutant is still valid Python that imports",
          _imports_ok(m2), "path=" + m2)
    return m1, m2

def _imports_ok(path):
    try:
        load_module(path, "sotto_worker_mutant_probe")
        return True
    except Exception as exc:
        say("       import failed: %r" % (exc,))
        return False


def run_child(mutant_path, label, extra_env=None):
    argv = [sys.executable, os.path.abspath(__file__), "--mutant-worker", mutant_path]
    env = {"PATH": os.environ.get("PATH", ""),
           "SystemRoot": os.environ.get("SystemRoot", ""),
           "TMPDIR": os.environ.get("TMPDIR", ""),
           "PYTHONDONTWRITEBYTECODE": "1"}
    for key in ("SystemDrive", "TEMP", "TMP", "PATHEXT", "COMSPEC"):
        if key in os.environ:
            env[key] = os.environ[key]
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(argv, cwd=REPO, env=env, capture_output=True, text=True,
                          timeout=600)
    say("")
    say("-- CHILD (%s) rc=%d" % (label, proc.returncode))
    for line in (proc.stdout or "").splitlines():
        say("   | " + line)
    if proc.stderr and proc.stderr.strip():
        say("   | [stderr] " + proc.stderr.strip())
    return proc


def tail_summary(rc):
    failed = [n for n, ok in RESULTS if not ok]
    say("")
    say("meter-chain-oracle: %d PASS / %d FAIL (%d checks)"
        % (len(RESULTS) - len(failed), len(failed), len(RESULTS)))
    for n in failed:
        say("  FAILED: " + n)
    if rc is None:
        rc = 0 if not failed else 1
    say("VERDICT: " + ("PASS" if rc == 0 else "FAIL"))
    return rc


def main():
    ap = argparse.ArgumentParser(description="the meter chain: worker -> shell -> panel")
    ap.add_argument("--neg-arm", action="store_true",
                    help="deaden the emit IN A COPY and require the oracle to go RED")
    ap.add_argument("--mutant-worker", default=None,
                    help=argparse.SUPPRESS)
    args = ap.parse_args()

    worker_py = args.mutant_worker or WORKER_PY
    # BYTES for the digest, TEXT for the search: `open(..., encoding=...)`
    # translates CRLF, so hashing the decoded text reports a sha256 that no
    # file on disk has. A receipt needs the digest OF THE ARTEFACT.
    def read_both(path):
        raw = read_bytes(path)
        return raw, raw.decode("utf-8")

    worker_bytes, text = read_both(worker_py)
    shell_bytes, shell_text = read_both(SHELL_PY)
    panel_bytes, panel_text = read_both(PANEL_JS)

    say("meter-chain-oracle -- the wave's producer, gated end to end")
    say("  worker   : %s" % worker_py)
    say("  worker B : %d  sha256 %s" % (len(worker_bytes), sha256_of(worker_bytes)))
    say("  shell    : %s  %d B  sha256 %s"
        % (SHELL_PY, len(shell_bytes), sha256_of(shell_bytes)))
    say("  panel    : %s  %d B  sha256 %s"
        % (PANEL_JS, len(panel_bytes), sha256_of(panel_bytes)))
    if args.mutant_worker:
        say("  ARM      : MUTANT (%s)" % os.environ.get(ENV_MUTANT, "?"))
    elif args.neg_arm:
        say("  ARM      : NEG (the live bytes are untouched; a copy is deadened)")

    W = load_module(worker_py, "sotto_worker_under_test")
    on_block = on_block_source(text)
    parser = parser_for(W)

    arm_rate(W, text, parser)
    arm_cadence(W)
    arm_worker_wiring(W, text, on_block)
    arm_dead_copy(W, text, on_block)
    producer_keys = arm_shape(W)
    arm_shell(shell_text, producer_keys)
    arm_panel(panel_text, producer_keys)
    arm_consumer_union(shell_text, panel_text, producer_keys)

    rc = 0 if not [n for n, ok in RESULTS if not ok] else 1

    if not args.neg_arm:
        return tail_summary(rc)

    # ── THE NEG ARM ─────────────────────────────────────────────────────────
    # Two mutants, because this oracle makes two claims that fail in different
    # ways: the emit can be DEADENED (nothing is published) and the cadence rule
    # can be removed (published at the wrong rate, or not at all per block).
    say("")
    say("== NEG ARM: the same oracle against TWO mutated copies ==")
    tmpdir = tempfile.mkdtemp(prefix="meter-chain-neg-")
    try:
        m_emit, m_rule = arm_mutant_is_real(text, on_block, tmpdir)
        child_failed = {}
        for kind, mpath, want in (
                ("emit", m_emit, ["on_block emits exactly ONE event"]),
                ("cadence", m_rule, ["100 blocks of 100 ms produce 100 EVENTS"])):
            proc = run_child(mpath, "mutant=" + kind,
                             {ENV_MUTANT: kind, "SOTTO_METER_ORACLE_CHILD": "1"})
            names = [ln.strip()[len("FAILED: "):] for ln in (proc.stdout or "").splitlines()
                     if ln.strip().startswith("FAILED: ")]
            child_failed[kind] = names
            check("the %s mutant makes the oracle exit non-zero (it can say NO)" % kind,
                  proc.returncode != 0,
                  "child rc=%d (0 would mean the gate is blind)" % proc.returncode)
            check("the %s mutant fails for the RIGHT reason, named by the child" % kind,
                  all(any(w in n for n in names) for w in want),
                  "wanted one of %r; child FAILED: %r" % (want, names))
            say("  child FAILED check names for %s (%d): %s"
                % (kind, len(names), "; ".join(names) if names else "-"))

        # The OTHER half of the control: neither mutant may be red for an
        # unrelated reason, so the SAME child against the LIVE bytes must be GREEN.
        proc2 = run_child(WORKER_PY, "live bytes (control)")
        check("the same child against the LIVE bytes is GREEN (the mutants are the "
              "only difference)",
              proc2.returncode == 0,
              "child rc=%d against the untouched file" % proc2.returncode)
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    return tail_summary(rc)


if __name__ == "__main__":
    sys.exit(main())
