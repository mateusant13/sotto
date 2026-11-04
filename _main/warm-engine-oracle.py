#!/usr/bin/env python3
# NO-BUG: CAPACIDADE/observabilidade (desenho state/design/warm-worker-20261104.md). O oraculo que o proprio desenho declara em divida: sem ele A4/A6/A7/A11/A12/A15 nao estao medidos.
"""WARM-ENGINE ORACLE -- o motor quente tem de provar as quatro fechaduras e o veto.

WHAT THIS FILE IS. The design (``state/design/warm-worker-20261104.md``) is a
contract with sixteen acceptance rows; its own debt note says the instrument
does not exist, and that until it does **A4, A6, A7, A11, A12 and A15 are not
measured**. This is that instrument.

WHAT IT RUNS -- headless by construction: in-process objects, one named pipe in
a temp namespace, two short-lived child processes, and files under %TMPDIR%.
It launches NO app, opens NO audio endpoint, mutates NO endpoint, and touches
NO window. Every child carries ``CREATE_NO_WINDOW``.

THE ARMS (each GREEN/RED on its own):

  01 g1-alta-refuses        fresh `alta` published + light measurement -> no permission
  02 g1-unknown-defers      no measurement at all -> `WARM_LOAD_DEFERRED`, never a load
  03 worst-of-two           measured `leve` + published `muito-alta` -> the worse wins
  04 g1-loads-on-leve       the ONLY permitted regime -> exactly one load, `WARM_LOAD_MS`
  05 g1-engine-defer-log    at `alta` the engine loads ZERO times and says why
  06 g2-tap-refused         `open_parked_tap` at `alta` opens nothing (`WARM_TAP_REFUSED`)
  07 g3-attach-shed         level rose between load and attach -> mode=shed, no session
  08 g4-release             `muito-alta` for > 120 s -> weights released, process alive
  09 ring-newest-first      8 s bound, newest chunk FIRST, ages ascending from 0
  10 replay-boundary        exactly 2000 ms paints, 2001 ms is history (one definition)
  11 attach-handshake       real pipe: hello schema/pid, attach < 500 ms, re-attach works
  12 stale-sha-refused      wrong plugin digest -> `WARM_HELLO_REFUSED why=stale-code`
  13 twin-pipe              two engines, one pipe -> one READY, one `WARM_TWIN_EXIT rc=0`
  14 twin-mutex             mutex held -> the second engine exits 0 before any pipe work
  15 single-loader          `self.bridge` non-None -> no `WorkerBridge` is constructed
  16 cold-arm               no engine -> `WARM_FALLBACK_COLD`, today's cold path runs
  17 stop-detaches          stop() sends a message; `.kill()` refuses; engine survives
  18 sender-never-blocks    a stalled peer drops meter/stats first, captions last
  19 pid-identity           pid+start written, removed on exit, dead pid named
  20 no-bypass              no env var / flag / task argument skips G1-G4 (R6)

--neg-arm: the same source is copied to %TMPDIR%, six mutants are applied by
LITERAL replacement, and each mutant must turn at least one arm RED. rc=1 and
``NEG-ARM PASS`` when every mutant is caught; rc=0 when one escapes.

Usage:
    python _main/warm-engine-oracle.py
    python _main/warm-engine-oracle.py --neg-arm
    python _main/warm-engine-oracle.py --verbose
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEBVIEW = os.path.join(ROOT, "app", "webview")
ENGINE = os.path.join(WEBVIEW, "warm_engine.py")
SHELL = os.path.join(WEBVIEW, "sotto_webview.py")
TASK_XML = os.path.join(HERE, "warm-engine", "warm-engine-task.xml")
MODEL_DIR = os.path.join(ROOT, "worker", "models", "nemotron-3.5-asr-ptbr-onnx-int4")

VERBOSE = False
#: Per-arm deadline. Six mutants x twenty arms must stay inside a battery step.
ARM_TIMEOUT_S = 60.0
CREATE_NO_WINDOW = 0x08000000
# STARTF_USESHOWWINDOW + SW_HIDE: o cinto ao lado dos suspensorios. Um filho que
# ignora CREATE_NO_WINDOW (um instalador, um `.vbs` por wscript) honra este.
STARTF_USESHOWWINDOW = 0x00000001
SW_HIDE = 0


def say(message=""):
    print(message, flush=True)


def detail(message):
    if VERBOSE:
        say("    " + message)


def tmpdir():
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return base if os.path.isdir(base) else tempfile.gettempdir()


if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)


# ── module loading ──────────────────────────────────────────────────────────
def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ── arm bookkeeping ─────────────────────────────────────────────────────────
class Arm:
    def __init__(self, number, name):
        self.number = number
        self.name = name
        self.bad = []
        self.notes = []

    @property
    def label(self):
        return "%02d %s" % (self.number, self.name)

    def check(self, condition, message):
        detail("%-4s %s" % ("PASS" if condition else "FAIL", message))
        if not condition:
            self.bad.append(message)
        return bool(condition)

    def note(self, message):
        self.notes.append(message)
        detail("note " + message)

    def ok(self):
        say("[arm %-26s] %s%s" % (self.label, "GREEN" if not self.bad else "RED",
                                  "" if not self.bad else " -- " + self.bad[0]))
        return not self.bad


# ── small fixtures ──────────────────────────────────────────────────────────
class Clock:
    def __init__(self, now=1000.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)
        return self.now


class Probe:
    """`LoadProbe.reread()` with a scripted answer -- no machine is measured here."""

    def __init__(self, commit=50.0, cpu=10.0):
        self.commit = commit
        self.cpu = cpu
        self.calls = 0

    def reread(self):
        self.calls += 1
        return self.commit, self.cpu, True

    def set(self, commit, cpu):
        self.commit, self.cpu = commit, cpu


class CountingLoader:
    def __init__(self, module, delay=0.0):
        self.module = module
        self.calls = 0
        self.delay = delay
        self.asr = None

    def load(self):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        self.asr = self.module.FakeGraph()
        return self.asr, 12.5

    def unload(self, _asr=None):
        return None


class FakeConn:
    def __init__(self):
        self.lines = []
        self.closed = False

    def send_line(self, text):
        self.lines.append(text)

    def close(self):
        self.closed = True

    def envelopes(self, tag):
        out = []
        for line in self.lines:
            if line.startswith(tag + " "):
                try:
                    out.append(json.loads(line[len(tag) + 1:]))
                except ValueError:
                    out.append({})
        return out


def write_visibility(path, level, age_s=0.0):
    payload = {"schema": "sotto.panel-visibility/1", "shed": level,
               "writtenAtEpoch": time.time() - float(age_s),
               "staleAfterSeconds": 9.0}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return payload


def wait_until(predicate, timeout=5.0, step=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def log_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


class EngineCase:
    """One in-process engine with its own pipe namespace, log and pid file."""

    def __init__(self, module, work, tag, probe=None, vis=None, clock=None,
                 loader=None, tap_opt_in=False):
        self.module = module
        self.work = work
        os.makedirs(self.work, exist_ok=True)
        self.probe = probe or Probe()
        self.vis = vis or os.path.join(work, "visibility-%s.json" % tag)
        self.clock = clock or Clock()
        self.loader = loader or CountingLoader(module)
        self.pipe = r"\\.\pipe\sotto-warm-oracle-%s-%d" % (tag, os.getpid())
        self.mutex = "Local\\SottoWarmEngineOracle.%s.%d" % (tag, os.getpid())
        self.pid_path = os.path.join(work, "pid-%s.txt" % tag)
        self.log_path = os.path.join(work, "log-%s.txt" % tag)
        self.engine = module.WarmEngine(
            session="oracle", model_dir=MODEL_DIR, root=ROOT, loader=self.loader,
            log_path=self.log_path, pid_path=self.pid_path, pipe=self.pipe,
            mutex=self.mutex, gate_fn=self.gate, clock=self.clock,
            tap_opt_in=tap_opt_in, visibility_path=self.vis,
        )

    def gate(self):
        return self.module.load_gate(probe=self.probe, visibility_path=self.vis,
                                     now=time.time())

    @property
    def log(self):
        return log_text(self.log_path)

    def client(self):
        """A peer wired the way a real one is: envelopes leave through
        `_raw_send` -> `_conn`, exactly as on the pipe.

        Without this the arm reads `[]` and calls it evidence, while the engine
        had in fact answered (`WARM_ATTACH_SHED`) into a connection object the
        test never installed.
        """
        conn = FakeConn()
        self.engine._conn = conn
        self.engine._sender = self.module.Sender(self.engine._raw_send, self.engine.log)
        return conn

    def flush(self, timeout=2.0):
        if self.engine._sender is not None:
            self.engine._sender.flush(timeout)

    def load(self):
        self.engine.state = "unloaded"
        self.engine._next_load_at = 0.0
        self.engine.tick()
        if self.engine._load_thread is not None:
            self.engine._load_thread.join(timeout=5.0)

    def close(self):
        try:
            self.engine.quit = True
            if self.engine._sender is not None:
                self.engine._sender.close()
            self.engine.shutdown()
        except Exception:  # noqa: BLE001 -- cleanup must not mask a verdict
            pass


# ── arms 01-05: the load gate ───────────────────────────────────────────────
def arm_g1_alta(mod, work):
    arm = Arm(1, "g1-alta-refuses")
    vis = os.path.join(work, "vis-alta.json")
    write_visibility(vis, "alta", 0.0)
    gate = mod.load_gate(probe=Probe(50.0, 10.0), visibility_path=vis)
    arm.check(gate["allowed"] is False, "measured leve + published alta -> allowed=False")
    arm.check(gate["level"] == "alta", "worst level is alta (got %r)" % (gate["level"],))
    arm.check(gate["why"] == "shed-alta", "why names the level (got %r)" % (gate["why"],))
    old = os.path.join(work, "vis-stale.json")
    write_visibility(old, "alta", 60.0)
    stale = mod.load_gate(probe=Probe(50.0, 10.0), visibility_path=old)
    arm.check(stale["allowed"] is True, "a STALE alta is not a measurement (age 60 s > 9 s)")
    return arm


def arm_g1_unknown(mod, work):
    arm = Arm(2, "g1-unknown-defers")
    vis = os.path.join(work, "vis-absent.json")
    gate = mod.load_gate(probe=Probe(None, None), visibility_path=vis)
    arm.check(gate["measured"] is False, "no measurement -> measured=False")
    arm.check(gate["allowed"] is False,
              "`unknown` is NOT permission to preload (allowed=False)")
    arm.check(gate["why"] == "no-measurement", "why=no-measurement (got %r)" % (gate["why"],))
    case = EngineCase(mod, work, "unk", probe=Probe(None, None), vis=vis)
    try:
        case.engine.state = "unloaded"
        case.engine._next_load_at = 0.0
        case.engine.tick()
        arm.check(case.loader.calls == 0, "the engine loaded ZERO graphs")
        arm.check("WARM_LOAD_DEFERRED why=no-measurement" in case.log,
                  "the deferral names the reason in the log")
    finally:
        case.close()
    return arm


def arm_worst_of_two(mod, work):
    arm = Arm(3, "worst-of-two")
    vis = os.path.join(work, "vis-veryhigh.json")
    write_visibility(vis, "muito-alta", 0.0)
    gate = mod.load_gate(probe=Probe(41.0, 3.0), visibility_path=vis)
    arm.check(gate["commit_pct"] == 41.0, "the measurement is the one the probe returned")
    arm.check(gate["level"] == "muito-alta", "the published level wins when it is worse")
    arm.check(gate["allowed"] is False, "allowed=False at muito-alta")
    hi = mod.load_gate(probe=Probe(95.0, 10.0),
                       visibility_path=os.path.join(work, "vis-absent-2.json"))
    arm.check(hi["level"] == "muito-alta", "the MEASURED level wins when IT is worse")
    arm.check(hi["allowed"] is False, "allowed=False at measured muito-alta")
    return arm


def arm_g1_loads_on_leve(mod, work):
    arm = Arm(4, "g1-loads-on-leve")
    case = EngineCase(mod, work, "leve", probe=Probe(40.0, 5.0))
    try:
        case.load()
        arm.check(case.loader.calls == 1, "exactly ONE load at leve (got %d)" % case.loader.calls)
        arm.check(case.engine.asr is not None, "the graph is resident")
        arm.check("WARM_LOAD_BEGIN" in case.log, "WARM_LOAD_BEGIN was written")
        arm.check("WARM_LOAD_MS" in case.log, "WARM_LOAD_MS was written")
        arm.check(case.engine.state == "parked-closed",
                  "state is parked-closed, not attached (%r)" % case.engine.state)
    finally:
        case.close()
    return arm


def arm_g1_engine_defer_log(mod, work):
    arm = Arm(5, "g1-engine-defer-log")
    vis = os.path.join(work, "vis-alta2.json")
    write_visibility(vis, "alta", 0.0)
    case = EngineCase(mod, work, "alta", probe=Probe(50.0, 10.0), vis=vis)
    try:
        case.load()
        arm.check(case.loader.calls == 0, "at alta the engine loaded ZERO graphs")
        arm.check("WARM_LOAD_DEFERRED why=shed-alta" in case.log,
                  "the log names the level that refused")
        arm.check("WARM_LOAD_BEGIN" not in case.log, "WARM_LOAD_BEGIN never happened")
    finally:
        case.close()
    return arm


# ── arms 06-08: tap, attach, residency ──────────────────────────────────────
def arm_g2_tap_refused(mod, work):
    arm = Arm(6, "g2-tap-refused")
    vis = os.path.join(work, "vis-alta3.json")
    write_visibility(vis, "alta", 0.0)
    case = EngineCase(mod, work, "tap", probe=Probe(50.0, 10.0), vis=vis,
                      tap_opt_in=True)
    try:
        case.engine.asr = mod.FakeGraph()
        opened = case.engine.open_parked_tap()
        arm.check(opened is False, "no tap is opened at alta")
        arm.check(case.engine._tap is None, "no tap object was kept")
        arm.check("WARM_TAP_REFUSED why=g2" in case.log, "WARM_TAP_REFUSED why=g2 was written")
    finally:
        case.close()
    return arm


def arm_g3_attach_shed(mod, work):
    arm = Arm(7, "g3-attach-shed")
    vis = os.path.join(work, "vis-rising.json")
    write_visibility(vis, "leve", 0.0)
    case = EngineCase(mod, work, "g3", probe=Probe(40.0, 5.0), vis=vis)
    conn = case.client()
    try:
        case.load()
        arm.check(case.engine.asr is not None, "loaded under leve first")
        # BOTH witnesses rise: the published level AND the measured one (a
        # published file alone is a claim; the gate takes the worse of the two).
        write_visibility(vis, "muito-alta", 0.0)
        case.probe.set(95.0, 30.0)
        case.engine.on_command({"op": "attach", "live": False}, conn)
        case.flush()
        replies = conn.envelopes("WARM_ATTACHED")
        arm.check(bool(replies), "the engine replied WARM_ATTACHED")
        arm.check(replies and replies[0].get("mode") == "shed",
                  "mode=shed when the level rose (got %r)"
                  % (replies[0].get("mode") if replies else None))
        arm.check(case.engine.session_obj is None, "no decode session was created")
        arm.check("WARM_ATTACH_SHED" in case.log, "WARM_ATTACH_SHED was written")
    finally:
        case.close()
    return arm


def arm_g4_release(mod, work):
    arm = Arm(8, "g4-release")
    vis = os.path.join(work, "vis-vh4.json")
    write_visibility(vis, "leve", 0.0)
    clock = Clock(500.0)
    case = EngineCase(mod, work, "g4", probe=Probe(40.0, 5.0), vis=vis, clock=clock)
    try:
        case.engine.asr = mod.FakeGraph()
        case.engine.loaded_at = clock()
        write_visibility(vis, "muito-alta", 0.0)
        case.engine.tick()
        arm.check(case.engine.asr is not None,
                  "119 s of muito-alta: the weights are still resident")
        clock.advance(121.0)
        case.engine.tick()
        arm.check(case.engine.asr is None, "after >120 s the weights are RELEASED")
        arm.check(case.engine.state == "unloaded", "state is unloaded")
        arm.check("WARM_RELEASE" in case.log, "WARM_RELEASE was written")
        arm.check(case.loader.calls == 0, "release did not load anything")
    finally:
        case.close()
    return arm


# ── arms 09-10: ring and replay ─────────────────────────────────────────────
def arm_ring_newest_first(mod, work):
    arm = Arm(9, "ring-newest-first")
    ring = mod.PcmRing(seconds=8.0, rate=mod.TARGET_SR)
    total = ring.size
    data = mod.__dict__  # noqa: F841  -- keeps the import list honest, no numpy here
    import numpy as np

    ramp = np.arange(total, dtype="float32")
    ring.push(ramp)
    chunks = ring.newest_first_chunks(890)
    arm.check(bool(chunks), "the full ring yields chunks")
    if chunks:
        age0, first = chunks[0]
        arm.check(age0 == 0, "the newest chunk has audio_ms=0 (got %d)" % age0)
        arm.check(float(first[-1]) == float(ramp[-1]),
                  "the FIRST chunk ends at the newest sample")
        ages = [age for age, _ in chunks]
        arm.check(ages == sorted(ages), "ages are ascending (newest first)")
        arm.check(chunks[-1][0] < 8000, "no chunk is older than the 8 s ring")
    ring2 = mod.PcmRing(seconds=2.0, rate=100)
    ring2.push(np.arange(500, dtype="float32"))
    kept = ring2.tail()
    arm.check(len(kept) == 200, "the ring holds exactly seconds*rate samples (%d)" % len(kept))
    arm.check(float(kept[-1]) == 499.0, "the newest sample is kept")
    return arm


def arm_replay_boundary(mod, work):
    arm = Arm(10, "replay-boundary")
    arm.check(mod.replay_is_history(2000) is False, "2000 ms paints (inside the budget)")
    arm.check(mod.replay_is_history(2001) is True, "2001 ms is history")
    arm.check(mod.replay_is_history(0) is False, "0 ms paints")
    arm.check(mod.replay_is_history(None) is True, "an unknown age is HISTORY, not a paint")
    return arm


# ── arm 11-12: the channel ──────────────────────────────────────────────────
def arm_attach_handshake(mod, work):
    arm = Arm(11, "attach-handshake")
    case = EngineCase(mod, work, "hs", probe=Probe(40.0, 5.0))
    thread = None
    try:
        import threading

        thread = threading.Thread(target=case.engine.run, name="oracle-engine", daemon=True)
        thread.start()
        arm.check(wait_until(lambda: case.engine.asr is not None, 6.0),
                  "engine finished its load")
        handle, why = mod.warm_pipe.open_client(case.pipe, 1500)
        arm.check(handle is not None, "client attached to the pipe (%s)" % why)
        if handle is None:
            return arm
        conn = mod.warm_pipe.PipeConn(handle)
        hello_line = conn.readline(timeout_s=1.0)
        arm.check(bool(hello_line and hello_line.startswith("WARM_HELLO ")),
                  "WARM_HELLO arrived")
        hello = json.loads(hello_line[len("WARM_HELLO "):]) if hello_line else {}
        arm.check(hello.get("schema") == mod.SCHEMA, "schema is sotto.warm/1")
        arm.check(int(hello.get("pid") or 0) == os.getpid(),
                  "hello names THIS pid (the engine learned it, the shell did not create it)")
        arm.check(hello.get("loaded") is True, "hello says loaded=True")
        t0 = time.monotonic()
        conn.send_line(json.dumps({"op": "attach", "live": False, "replay": False}))
        reply = None
        while time.monotonic() - t0 < 2.0:
            line = conn.readline(timeout_s=0.5)
            if line and line.startswith("WARM_ATTACHED "):
                reply = json.loads(line[len("WARM_ATTACHED "):])
                break
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        arm.check(reply is not None, "WARM_ATTACHED arrived")
        arm.check(elapsed_ms <= 500.0, "attach took %.1f ms <= 500 ms" % elapsed_ms)
        conn.send_line(json.dumps({"op": "detach", "why": "oracle"}))
        conn.close()
        arm.check(wait_until(lambda: case.engine.session_obj is None, 3.0),
                  "detach ended the session")
        # RE-ATTACH: the same engine must accept a second shell without a load.
        handle2, why2 = mod.warm_pipe.open_client(case.pipe, 1500)
        arm.check(handle2 is not None, "second attach opened the pipe (%s)" % why2)
        if handle2 is not None:
            conn2 = mod.warm_pipe.PipeConn(handle2)
            arm.check(bool(conn2.readline(timeout_s=1.0)), "second WARM_HELLO arrived")
            conn2.send_line(json.dumps({"op": "attach", "live": False, "replay": False}))
            seen = False
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                line = conn2.readline(timeout_s=0.5)
                if line and line.startswith("WARM_ATTACHED "):
                    seen = True
                    break
            arm.check(seen, "re-attach without a load")
            arm.check(case.loader.calls == 1, "ONE load across two attaches (got %d)"
                      % case.loader.calls)
            conn2.send_line(json.dumps({"op": "quit", "why": "oracle"}))
            conn2.close()
    finally:
        case.engine.quit = True
        if thread is not None:
            thread.join(timeout=3.0)
        case.close()
    return arm


def arm_stale_sha_refused(mod, work):
    arm = Arm(12, "stale-sha-refused")
    case = EngineCase(mod, work, "sha", probe=Probe(40.0, 5.0))
    conn = case.client()
    try:
        case.engine.asr = mod.FakeGraph()
        case.engine.on_command({"op": "attach", "expect_sha256": "deadbeef",
                                "model_key": case.engine.key}, conn)
        arm.check("WARM_HELLO_REFUSED why=stale-code" in case.log,
                  "WARM_HELLO_REFUSED why=stale-code was written")
        arm.check(case.engine.quit is True, "the stale engine asks to quit")
        arm.check(case.engine.session_obj is None, "no session was created")
    finally:
        case.close()
    return arm


# ── arms 13-14: the twin locks ──────────────────────────────────────────────
def _spawn_engine(work, tag, pipe, mutex, pid, log, extra=()):
    argv = [sys.executable, "-u", ENGINE, "--no-model", "--session", "oracle",
            "--pipe", pipe, "--mutex", mutex, "--pid-file", pid, "--log-file", log]
    argv.extend(extra)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return subprocess.Popen(argv, cwd=WEBVIEW, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            startupinfo=si, creationflags=CREATE_NO_WINDOW)


def arm_twin_pipe(mod, work):
    arm = Arm(13, "twin-pipe")
    pipe = r"\\.\pipe\sotto-warm-oracle-twin-%d" % os.getpid()
    mutex = "Local\\SottoWarmEngineOracle.twin.%d" % os.getpid()
    pid_a = os.path.join(work, "twin-a.pid")
    pid_b = os.path.join(work, "twin-b.pid")
    log_a = os.path.join(work, "twin-a.log")
    log_b = os.path.join(work, "twin-b.log")
    first = _spawn_engine(work, "twin-a", pipe, mutex, pid_a, log_a)
    second = None
    try:
        arm.check(wait_until(lambda: "WARM_PIPE_READY" in log_text(log_a), 6.0),
                  "the first engine created the pipe")
        # A DIFFERENT mutex on purpose: the twin must be refused by the PIPE
        # lock, so this arm measures `FILE_FLAG_FIRST_PIPE_INSTANCE` and not the
        # mutex arm's fact a second time.
        second = _spawn_engine(work, "twin-b", pipe, mutex + "-b", pid_b, log_b)
        try:
            rc = second.wait(timeout=15)
        except subprocess.TimeoutExpired:
            second.kill()
            rc = None
        arm.check(rc == 0, "the twin exited 0 (got %r)" % (rc,))
        arm.check("WARM_TWIN_EXIT rc=0" in log_text(log_b),
                  "the twin wrote WARM_TWIN_EXIT")
        arm.check("WARM_PIPE_READY" not in log_text(log_b),
                  "the twin never became a serving pipe")
        # The first engine is still the only one, and it answers.
        handle, why = mod.warm_pipe.open_client(pipe, 1000)
        arm.check(handle is not None, "the first engine still answers (%s)" % why)
        if handle is not None:
            conn = mod.warm_pipe.PipeConn(handle)
            arm.check(bool(conn.readline(timeout_s=1.0)), "first engine said WARM_HELLO")
            conn.send_line(json.dumps({"op": "quit", "why": "oracle"}))
            conn.close()
    finally:
        for proc in (second, first):
            if proc is None:
                continue
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        for path in (pid_a, pid_b):
            try:
                os.remove(path)
            except OSError:
                pass
    return arm


def arm_twin_mutex(mod, work):
    arm = Arm(14, "twin-mutex")
    tag = "mx%d" % os.getpid()
    mutex = "Local\\SottoWarmEngineOracle.%s" % tag
    handle, created = mod.warm_pipe.create_mutex(mutex)
    arm.check(created is True, "the oracle holds the mutex first")
    case = EngineCase(mod, work, tag, probe=Probe(40.0, 5.0))
    case.mutex = mutex
    case.engine.mutex_name = mutex
    case.engine.pipe_name = r"\\.\pipe\sotto-warm-oracle-mx-%d" % os.getpid()
    case.engine._mutex_handle = None
    try:
        arm.check(case.engine.acquire() is False, "the second engine refused ownership")
        arm.check("WARM_TWIN_EXIT rc=0 why=mutex-exists" in case.log,
                  "the log names the mutex as the reason")
        arm.check(case.engine.asr is None, "the twin loaded NOTHING")
    finally:
        if case.engine._mutex_handle is not None:
            mod.warm_pipe.release_mutex(case.engine._mutex_handle)
            case.engine._mutex_handle = None
        case.close()
        mod.warm_pipe.release_mutex(handle)
    return arm


# ── arms 15-17: the shell edge ──────────────────────────────────────────────
class FakeShell:
    """Just enough SottoShell for the SHIPPED `start_worker` to run in-process."""

    def __init__(self, mod, args, engine_mod, pipe):
        self.args = args
        self.bridge = None
        self.START_REASONS = mod.SottoShell.START_REASONS
        self.exiting = None
        self._source_epoch = 0
        self._caption_pending = None
        self.cold_spawns = 0
        self.task_starts = 0
        self.painted = []
        self._engine_mod = engine_mod
        self._pipe = pipe

    def on_worker_caption(self, text, meta):
        self.painted.append((text, meta))

    def on_worker_status(self, text, kind, info):
        return None

    def on_worker_stats(self, payload):
        return None

    def on_worker_meter(self, sample):
        return None

    def push_caption_to_window(self, text, tap_ms=None):
        return None

    def code_state_log(self, reason):
        return None

    def apply_panel_state(self, *args, **kwargs):
        return None

    def speaker_sidecar(self):
        raise AssertionError("no sidecar in this arm")

    def multivoice_watch(self):
        raise AssertionError("no sidecar in this arm")


def shell_args(**overrides):
    values = dict(python=sys.executable, worker=os.path.join(ROOT, "worker", "sotto_worker.py"),
                  device=None, capture=None, speakers=False, speakers_cheap=False,
                  no_warm_engine=False, warm_engine_keep=True, app_target=None)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def warm_shim(mod, pipe):
    class PipeShim:
        def __getattr__(self, name):
            return getattr(mod.warm_pipe, name)

        def pipe_name(self, _key):
            return pipe

    class Shim:
        SCHEMA = mod.SCHEMA

        ROOT = mod.ROOT
        warm_pipe = PipeShim()
        model_dir_from = staticmethod(lambda root=None: MODEL_DIR)
        plugin_sha256 = staticmethod(lambda root=None: mod.plugin_sha256(ROOT))
        load_gate = staticmethod(lambda **kw: {"allowed": True, "level": "leve"})
        replay_is_history = staticmethod(mod.replay_is_history)

    return Shim


def load_shell_counts(shell_mod):
    """Wrap `WorkerBridge.__init__` so a construction is COUNTED, never hidden."""
    counts = {"worker": 0}
    original = shell_mod.WorkerBridge.__init__

    def _init(self, *args, **kwargs):
        if type(self).__name__ == "WorkerBridge":
            counts["worker"] += 1
        return original(self, *args, **kwargs)

    shell_mod.WorkerBridge.__init__ = _init
    return counts


def make_shell(shell_mod, engine_mod, pipe, args=None, spawn=None):
    import types as _types

    shell = FakeShell(shell_mod, args or shell_args(), engine_mod, pipe)
    shell.start_worker = _types.MethodType(shell_mod.SottoShell.start_worker, shell)
    shell._try_warm_attach = _types.MethodType(shell_mod.SottoShell._try_warm_attach, shell)
    shell_mod.warm_module = lambda: warm_shim(engine_mod, pipe)
    shell_mod.start_warm_engine_task = lambda **kwargs: shell.__setattr__(
        "task_starts", shell.task_starts + 1) or True

    def _spawn(self):
        if type(self).__name__ == "WorkerBridge":
            shell.cold_spawns += 1
        return None

    shell_mod.WorkerBridge._spawn = _spawn
    return shell


def run_engine_thread(case):
    import threading

    thread = threading.Thread(target=case.engine.run, name="oracle-shell-engine", daemon=True)
    thread.start()
    wait_until(lambda: case.engine.state in ("unloaded", "loading", "parked-closed"), 4.0)
    return thread


def arm_single_loader(mod, work, shell_mod):
    arm = Arm(15, "single-loader")
    case = EngineCase(mod, work, "single", probe=Probe(40.0, 5.0))
    thread = None
    try:
        thread = run_engine_thread(case)
        pipe = case.engine.pipe_name
        counts = load_shell_counts(shell_mod)
        shell = make_shell(shell_mod, mod, pipe)
        started = shell.start_worker("default")
        arm.check(started is True, "start_worker returned True")
        arm.check(isinstance(shell.bridge, shell_mod.WarmPipeBridge),
                  "self.bridge is the warm bridge (%r)" % type(shell.bridge).__name__)
        arm.check(counts["worker"] == 0, "NO cold WorkerBridge was constructed")
        arm.check(shell.cold_spawns == 0, "WorkerBridge._spawn never ran")
        # THE EXISTING GUARD IS THE GATE: a second start refuses on `self.bridge`.
        again = shell.start_worker("default")
        arm.check(again is False, "a second start_worker refused (self.bridge is not None)")
        arm.check(counts["worker"] == 0, "still no cold bridge")
        shell.bridge.stop("closing")
        arm.check(case.engine.quit is False, "stop() did not kill the engine")
    finally:
        case.engine.quit = True
        if thread is not None:
            thread.join(timeout=3.0)
        case.close()
    return arm


def arm_cold_arm(mod, work, shell_mod):
    arm = Arm(16, "cold-arm")
    pipe = r"\\.\pipe\sotto-warm-oracle-absent-%d" % os.getpid()
    counts = load_shell_counts(shell_mod)
    shell = make_shell(shell_mod, mod, pipe)
    try:
        started = shell.start_worker("default")
        arm.check(started is False, "the cold bridge's start reported False (spawn stubbed)")
        arm.check(counts["worker"] == 1, "exactly one cold WorkerBridge was constructed")
        arm.check(shell.cold_spawns == 1, "today's cold path ran exactly once")
        arm.check(isinstance(shell.bridge, shell_mod.WorkerBridge)
                  and not isinstance(shell.bridge, shell_mod.WarmPipeBridge),
                  "the bridge is the COLD one")
        arm.check(shell.task_starts == 1,
                  "the scheduler was asked to start an engine for the NEXT open")
        if shell.bridge is not None:
            shell.bridge.stop("closing")
    finally:
        pass
    return arm


def arm_stop_detaches(mod, work, shell_mod):
    arm = Arm(17, "stop-detaches-not-kills")
    case = EngineCase(mod, work, "stop", probe=Probe(40.0, 5.0))
    thread = None
    try:
        thread = run_engine_thread(case)
        pipe = case.engine.pipe_name
        counts = load_shell_counts(shell_mod)
        shell = make_shell(shell_mod, mod, pipe)
        shell.start_worker("default")
        bridge = shell.bridge
        arm.check(isinstance(bridge, shell_mod.WarmPipeBridge), "warm bridge attached")
        arm.check(bridge.child is not None, "the bridge has a child proxy")
        try:
            bridge.child.kill()
            killed = True
        except (RuntimeError, AttributeError):
            killed = False
        arm.check(killed is False, "child.kill() REFUSES (the shell does not own it)")
        arm.check(bridge.stop("closing") is True, "stop() answered True")
        arm.check(case.engine.quit is False, "the engine is STILL ALIVE")
        arm.check(case.engine.asr is not None, "and still holds the graph")
        # A quit reason DOES ask it to stop (hot reload = stale code).
        bridge2, why = shell_mod.WarmPipeBridge.attach(
            deadline_ms=500, live=False, device=None, capture_mode="mix",
            target_pid=None, keep_warm=False, log=lambda _m: None)
        arm.check(bridge2 is not None, "the engine accepts again after stop (%s)" % why)
        if bridge2 is not None:
            bridge2.stop("hot-reload")
            arm.check(wait_until(lambda: case.engine.quit is True, 3.0),
                      "hot-reload asks the engine to quit (stale by definition)")
    finally:
        case.engine.quit = True
        if thread is not None:
            thread.join(timeout=3.0)
        case.close()
    return arm


# ── arms 18-20: writer, identity, bypass ────────────────────────────────────
def arm_sender_never_blocks(mod, work):
    arm = Arm(18, "sender-never-blocks")
    log_path = os.path.join(work, "sender.log")

    def log(message):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    blocked = []

    def slow_send(_text):
        time.sleep(0.05)

    sender = mod.Sender(slow_send, log, capacity=16)
    try:
        t0 = time.monotonic()
        dropped_meter = 0
        dropped_caption = 0
        for i in range(400):
            before = sum(sender.dropped.values())
            ok = sender.put("meter-%d" % i, "meter")
            after = sum(sender.dropped.values())
            dropped_meter += (after - before)
        for i in range(400):
            before = sum(sender.dropped.values())
            ok = sender.put("caption-%d" % i, "caption")
            after = sum(sender.dropped.values())
            dropped_caption += (after - before)
        elapsed = time.monotonic() - t0
        arm.check(elapsed < 2.0, "800 puts returned in %.3fs (no call blocks)" % elapsed)
        arm.check("WARM_SEND_DROPPED class=meter" in log_text(log_path)
                  or dropped_meter > 0,
                  "meter lines were dropped first and counted (%d)" % dropped_meter)
        arm.check("WARM_SEND_OVERFLOW class=caption" in log_text(log_path),
                  "caption overflow announces itself")
        arm.check(sender.overflow is True, "the stream is declared overflowed")
    finally:
        sender.close()
    return arm


def arm_pid_identity(mod, work):
    arm = Arm(19, "pid-identity")
    case = EngineCase(mod, work, "pid", probe=Probe(40.0, 5.0))
    thread = None
    try:
        thread = run_engine_thread(case)
        arm.check(wait_until(lambda: os.path.exists(case.pid_path), 3.0),
                  "the pid file was written")
        identity = mod.read_pid_file(case.pid_path)
        arm.check(identity is not None and identity["pid"] == os.getpid(),
                  "the pid file names the engine pid")
        arm.check(bool(identity and identity.get("started")),
                  "and its START TIME (the identity that makes a kill legal)")
        case.engine.quit = True
        thread.join(timeout=3.0)
        thread = None
        arm.check(not os.path.exists(case.pid_path), "the pid file is removed on exit")
        stale = os.path.join(work, "stale.pid")
        with open(stale, "w", encoding="utf-8") as handle:
            handle.write("999999\t1.0\toracle\tkey\tsha\tnow\n")
        arm.check(mod.pid_alive(999999) is False, "a dead pid reads as dead")
    finally:
        case.engine.quit = True
        if thread is not None:
            thread.join(timeout=3.0)
        case.close()
    return arm


def arm_no_bypass(mod, work):
    arm = Arm(20, "no-bypass")
    text = open(ENGINE, encoding="utf-8").read()
    shell_text = open(SHELL, encoding="utf-8").read()
    for token in ("SOTTO_WARM_FORCE", "WARM_FORCE", "--force-load"):
        arm.check(token not in text and token not in shell_text,
                  "no %s anywhere (R6)" % token)
    arm.check("def load_gate(probe=None, visibility_path=" in text,
              "load_gate's signature takes NO force argument")
    arm.check("allowed" in text and '"allowed": bool(measured and worst == "leve")' in text,
              "the permission is the measured+leve conjunction")
    xml = open(TASK_XML, encoding="utf-8").read() if os.path.exists(TASK_XML) else ""
    arm.check("<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in xml,
              "the task refuses a second instance")
    arm.check("<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>" in xml,
              "the task has no 3-day limit (F14)")
    arm.check("<Triggers />" in xml or "<Triggers/>" in xml,
              "NO logon trigger (R4: the box is loaded at login)")
    arm.check("<RestartOnFailure>" in xml and "<Count>2</Count>" in xml,
              "crash restart is bounded at 2 (R3)")
    arm.check("--no-model" in text, "the instrument switch is explicit and only skips the LOAD")
    return arm


# ── arms 21-22: attach latency over 20 handshakes, and the TTL ──────────────
def arm_attach_latency(mod, work):
    """A4's actual row: p50 <= 300 ms, p95 <= 500 ms, 0 timeouts over 20 attaches.

    One attach proves the handshake EXISTS; twenty prove it is not a lucky
    sample and that a detach leaves the engine attachable -- the failure mode
    where the engine is attachable exactly once and every later shell pays a
    cold boot.
    """
    arm = Arm(21, "attach-20")
    case = EngineCase(mod, work, "lat", probe=Probe(40.0, 5.0))
    # A4 is a WALL-CLOCK number: the scripted clock would print `ms=0.0` for
    # every attach and make the row unmeasurable while looking green.
    case.engine.clock = time.monotonic
    case.engine._last_detach_at = time.monotonic()
    thread = None
    samples = []
    timeouts = 0
    try:
        thread = run_engine_thread(case)
        arm.check(wait_until(lambda: case.engine.asr is not None, 6.0),
                  "one load done before the loop")
        for index in range(20):
            handle, why = mod.warm_pipe.open_client(case.pipe, 1500)
            if handle is None:
                timeouts += 1
                detail("attach %d: open failed (%s)" % (index, why))
                continue
            conn = mod.warm_pipe.PipeConn(handle)
            hello = conn.readline(timeout_s=1.0)
            if not hello:
                timeouts += 1
                conn.close()
                continue
            t0 = time.monotonic()
            conn.send_line(json.dumps({"op": "attach", "live": False, "replay": False}))
            got = None
            while time.monotonic() - t0 < 1.0:
                line = conn.readline(timeout_s=0.2)
                if line and line.startswith("WARM_ATTACHED "):
                    got = json.loads(line[len("WARM_ATTACHED "):])
                    break
            if got is None:
                timeouts += 1
            else:
                samples.append(float(got.get("ms") or 0.0))
            conn.send_line(json.dumps({"op": "detach", "why": "oracle"}))
            conn.close()
            if not wait_until(lambda: case.engine.session_obj is None, 3.0):
                arm.check(False, "detach %d did not end the session" % index)
                break
        arm.check(timeouts == 0, "0 timeouts over 20 attaches (got %d)" % timeouts)
        arm.check(len(samples) == 20, "20 measured handshakes (got %d)" % len(samples))
        if samples:
            ordered = sorted(samples)
            p50 = ordered[len(ordered) // 2]
            p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
            say("  attach-20: p50=%.1f ms p95=%.1f ms max=%.1f ms n=%d"
                % (p50, p95, ordered[-1], len(ordered)))
            arm.check(p50 <= 300.0, "p50 %.1f ms <= 300 ms (A4)" % p50)
            arm.check(p95 <= 500.0, "p95 %.1f ms <= 500 ms (A4)" % p95)
        arm.check(case.loader.calls == 1,
                  "ONE load across 20 attaches (got %d) -- A5/A7" % case.loader.calls)
        arm.check(case.log.count("WARM_LOAD_BEGIN") == 1,
                  "ONE WARM_LOAD_BEGIN in the log")
    finally:
        case.engine.quit = True
        if thread is not None:
            thread.join(timeout=3.0)
        case.close()
    return arm


def arm_ttl_exit(mod, work):
    """A11's other half: the parked engine must RELEASE itself after the TTL."""
    arm = Arm(22, "ttl-exit")
    clock = Clock()
    case = EngineCase(mod, work, "ttl", probe=Probe(40.0, 5.0), clock=clock)
    case.engine.park_ttl_s = 2.0
    try:
        case.load()
        arm.check(case.engine.asr is not None, "the graph is resident")
        arm.check(case.engine.session_obj is None, "nobody is attached")
        case.engine.tick()
        arm.check(case.engine.quit is False, "inside the TTL it stays parked")
        clock.advance(3.0)
        case.engine.tick()
        arm.check(case.engine.quit is True, "past the TTL the engine asks to exit")
        arm.check("WARM_EXIT why=idle-expired" in case.log,
                  "the log names the TTL, not a mystery exit")
    finally:
        case.close()
    return arm


# ── the arm table ───────────────────────────────────────────────────────────
def run_arms(mod, work, shell_mod):
    results = []
    os.makedirs(work, exist_ok=True)
    #: No arm may wedge the gate. A hang is not a verdict: the traceback is
    #: dumped and the step dies with a NON-ZERO rc -- the battery reads that as
    #: red, and the `--neg-arm` step then lacks "NEG-ARM PASS" and reds too.
    import faulthandler

    def run(fn, *args):
        label = getattr(fn, "__name__", "arm")
        say("  arm %-26s ..." % label)
        sys.stdout.flush()
        faulthandler.dump_traceback_later(ARM_TIMEOUT_S, exit=True)
        try:
            results.append(fn(*args))
        except Exception as exc:  # noqa: BLE001 -- an arm that throws is RED, not gone
            arm = Arm(0, label)
            arm.check(False, "arm raised %r" % (exc,))
            results.append(arm)
            say("  arm %-26s RAISED %r" % (label, exc))
        finally:
            faulthandler.cancel_dump_traceback_later()

    run(arm_g1_alta, mod, work)
    run(arm_g1_unknown, mod, work)
    run(arm_worst_of_two, mod, work)
    run(arm_g1_loads_on_leve, mod, work)
    run(arm_g1_engine_defer_log, mod, work)
    run(arm_g2_tap_refused, mod, work)
    run(arm_g3_attach_shed, mod, work)
    run(arm_g4_release, mod, work)
    run(arm_ring_newest_first, mod, work)
    run(arm_replay_boundary, mod, work)
    run(arm_attach_handshake, mod, work)
    run(arm_stale_sha_refused, mod, work)
    run(arm_twin_pipe, mod, work)
    run(arm_twin_mutex, mod, work)
    run(arm_single_loader, mod, work, shell_mod)
    run(arm_cold_arm, mod, work, shell_mod)
    run(arm_stop_detaches, mod, work, shell_mod)
    run(arm_sender_never_blocks, mod, work)
    run(arm_pid_identity, mod, work)
    run(arm_no_bypass, mod, work)
    run(arm_attach_latency, mod, work)
    run(arm_ttl_exit, mod, work)
    return results


# ── mutants ─────────────────────────────────────────────────────────────────
MUTANTS = (
    ("M1-gate-bypass",
     '        gate = self.gate()\n        if not gate["allowed"]:',
     '        gate = self.gate()\n        if False:  # mutant: the gate is decorative'),
    ("M2-unknown-allows",
     '"allowed": bool(measured and worst == "leve"),',
     '"allowed": bool(worst != "muito-alta"),  # mutant: unknown allows'),
    ("M3-ring-oldest-first",
     '            out.append((age_ms, data[end - chunk:end].copy()))',
     '            out.append((age_ms, data[:chunk].copy()))  # mutant'),
    ("M4-mutex-twin",
     '        if not created:',
     '        if False:  # mutant: the mutex lock is decorative'),
    ("M5-replay-2000",
     '        return int(audio_ms) > int(limit_ms)',
     '        return int(audio_ms) >= int(limit_ms)  # mutant'),
    ("M6-detach-quits",
     '        if op == "detach":\n            why = str(message.get("why") or "shell-closing")',
     '        if op == "detach":\n            self.quit = True  # mutant\n            why = str(message.get("why") or "shell-closing")'),
)


def build_mutant(work, name, old, new):
    source = open(ENGINE, encoding="utf-8").read()
    if source.count(old) != 1:
        return None, "anchor appears %d times" % source.count(old)
    mutated = source.replace(old, new)
    directory = os.path.join(work, "mutant-%s" % name)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "warm_engine.py")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(mutated)
    try:
        module = load_module(path, "warm_engine_%s" % name.replace("-", "_"))
    except Exception as exc:  # noqa: BLE001 -- a mutant that will not import is INVALID
        return None, "import failed: %r" % (exc,)
    return module, None


def neg_arm(work, shell_mod):
    caught = 0
    total = 0
    for name, old, new in MUTANTS:
        total += 1
        module, error = build_mutant(work, name, old, new)
        if module is None:
            say("MUTANT %-22s INVALID -- %s" % (name, error))
            continue
        results = run_arms(module, os.path.join(work, "run-%s" % name), shell_mod)
        red = [arm.name for arm in results if not arm.ok()]
        if red:
            caught += 1
            say("MUTANT %-22s CAUGHT by %s" % (name, ", ".join(red[:3])))
        else:
            say("MUTANT %-22s ESCAPED -- the arms cannot tell it from the real thing" % name)
    say("NEG-ARM %s -- %d/%d mutant(s) caught"
        % ("PASS" if caught == total else "FAIL", caught, total))
    return 1 if caught == total else 0


# ── main ────────────────────────────────────────────────────────────────────
def main(argv=None):
    global VERBOSE
    parser = argparse.ArgumentParser(description="warm engine oracle")
    parser.add_argument("--neg-arm", action="store_true",
                        help="run the mutated copies; every mutant must be caught")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    VERBOSE = args.verbose

    engine = load_module(ENGINE, "warm_engine_oracle_under_test")
    shell = load_module(SHELL, "sotto_webview_oracle_warm")

    work = tempfile.mkdtemp(prefix="warm-engine-oracle-", dir=tmpdir())
    ok = True
    try:
        if args.neg_arm:
            rc = neg_arm(work, shell)
            _report_leftovers()
            return rc
        results = run_arms(engine, work, shell)
        for arm in results:
            ok = arm.ok() and ok
        for arm in results:
            say("%-4s %-30s %s" % ("ok" if arm.ok() else "RED", arm.name,
                                   "" if arm.ok() else "; ".join(arm.bad)))
        say()
        bad = [arm.name for arm in results if not arm.ok()]
        verdict = "PASS" if ok else "FAIL"
        say("WARM-ENGINE VERDICT: %s -- %d arm(s), %d red%s"
            % (verdict, len(results), len(bad), (": " + ", ".join(bad)) if bad else ""))
        _report_leftovers()
        return 0 if ok else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _report_leftovers():
    pid_path = os.path.join(HERE, "warm-engine.pid")
    if not os.path.exists(pid_path):
        say("warm engine pid file: none")
        return
    try:
        engine = load_module(ENGINE, "warm_engine_leftover_probe")
        identity = engine.read_pid_file(pid_path)
        if identity is None:
            say("warm engine pid file: unreadable")
        elif engine.pid_alive(identity["pid"]):
            say("warm engine pid file: LIVE pid=%d" % identity["pid"])
        else:
            say("warm engine pid file: dead pid=%d (stale)" % identity["pid"])
    except Exception as exc:  # noqa: BLE001
        say("warm engine pid file: probe failed %r" % (exc,))


if __name__ == "__main__":
    sys.exit(main())
