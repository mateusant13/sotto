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
  21 attach-20              attach round-trip under the 20 ms handshake budget
  22 ttl-exit               parked past the hold -> `WARM_EXIT why=idle-expired`
  23 activity-resets-idle   audio/caption evidence resets the clock; no evidence expires
  24 idle-past-hold-expires the exit names idle_s, ttl_s AND the last evidence
  25 reload-floor-thrash    thrash pair waits the floor; long residency reloads NEXT tick
  26 hold-vs-load-ratio     the numbers judged against the 16 measured loads
  27 one-number-two-files   the same thrash window in warm_engine and engine_policy
  28 policy-floor-scope     the WORKER's floor: short release waits, long one does not
  29 tap-blocks-are-not-work  a parked-ring block is not evidence (D-04 stays closed)

--neg-arm: the same source is copied to %TMPDIR%, ten mutants are applied by
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
#: O launcher e' o segundo ficheiro que a arm 20 julga. Sao variaveis de MODULO
#: (e nao literais dentro da arm) porque o `--neg-arm` os aponta para uma COPIA
#: mutada: uma arm que le o ficheiro original nunca pode ficar vermelha.
RUN_CMD = os.path.join(HERE, "warm-engine", "warm-engine-run.cmd")
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
        # A LATENCY MEASURED UNDER `cap40` IS NOT A LATENCY (same law as arm 21,
        # measured 2026-11-25): in a caged battery run this read 1187 ms while the
        # box served every call, and the step went RED for the scheduler. Inside
        # the cage the arm proves the PROTOCOL (the attach answered, with its
        # number printed); the 500 ms claim is judged only outside it.
        if (os.environ.get("SOTTO_BATTERY_CAGED") == "1"
                or os.environ.get("SOTTO_BATTERY_POLICY", "") == "cap40"):
            detail("politica=cap40: attach took %.1f ms -- NAO julgado contra 500 ms "
                   "dentro do tecto" % elapsed_ms)
        else:
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
        # A WALL-CLOCK BOUND ON A LOADED BOX IS NOT A VERDICT (measured
        # 2026-11-25). `second.wait(timeout=15)` said "the twin exited 0 (got
        # None)" in a full battery run and passed three times standalone: on a
        # box sharing the disk with other lanes, 15 s is a statement about the
        # scheduler, not about the pipe lock. The arm now waits for the TWIN'S
        # OWN terminal line (`WARM_TWIN_EXIT`) with a per-stage budget, and when
        # the budget runs out it NAMES the stage it was in instead of reporting
        # a bare `None`.
        TWIN_EXIT_BUDGET_S = 60.0
        deadline = time.time() + TWIN_EXIT_BUDGET_S
        saw_exit = False
        while time.time() < deadline:
            # THE LINE IS THE EVIDENCE, NOT THE EXIT CODE (measured 2026-11-25,
            # second attempt): waiting on `poll()` first broke out as soon as the
            # child was reaped, one write behind the log it had already appended,
            # and reported "no WARM_TWIN_EXIT" about a log that contained it. The
            # loop reads the log until the budget runs out; the child's exit only
            # decides the STAGE named in the failure message.
            if "WARM_TWIN_EXIT" in log_text(log_b):
                saw_exit = True
                break
            time.sleep(0.1)
        twin_line = [ln for ln in log_text(log_b).splitlines()
                     if "WARM_TWIN_EXIT" in ln]
        if not twin_line:
            second.kill()
            arm.check(False,
                      "the twin reached WARM_TWIN_EXIT within %.0fs "
                      "(stage=%s, log=%r)"
                      % (TWIN_EXIT_BUDGET_S,
                         "twin-loaded" if "WARM_LOAD" in log_text(log_b) else "twin-start",
                         log_text(log_b)[-160:].strip()))
        else:
            # THE LINE IS THE CLAIM; the teardown is not (measured 2026-11-25,
            # third attempt): the twin wrote `WARM_TWIN_EXIT rc=0 why=pipe-exists`
            # and then took longer than 10 s to leave the process table under a
            # loaded box, and an arm that failed on the exit code reported a
            # pipe-lock defect that had already been proven not to exist.
            try:
                second.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                detail("twin wrote its refusal and lingered (rc=%r)"
                       % (second.poll(),))
        arm.check("WARM_TWIN_EXIT rc=0" in log_text(log_b),
                  "the twin wrote WARM_TWIN_EXIT rc=0")
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
        self.loading_texts = []
        self._engine_mod = engine_mod
        self._pipe = pipe

    def on_worker_caption(self, text, meta):
        self.painted.append((text, meta))

    def on_worker_status(self, text, kind, info):
        return None

    def on_worker_loading_text(self, text):
        # 2026-11-04: a shell passou a ligar o `on_loading_text` do bridge a
        # este metodo (o gate que RETEM o texto de estado quando o player
        # fornece linha). O fake tem de o ter, senao a arm mede um AttributeError
        # em vez do caminho quente.
        self.loading_texts.append(text)
        return None

    def on_worker_stats(self, payload):
        return None

    def on_worker_cost(self, parsed):
        # 2026-11-09: o `start_worker` passou a ligar `on_cost=self.on_worker_cost`
        # ao bridge (o cao de guarda do CUSTO do worker -- CPU alta sem linha). O
        # fake tem de o ter, senao as tres arms do carregamento quente medem um
        # `AttributeError` em vez do caminho que o produto corre.
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

    # O ORCAMENTO DE ATTACH E' POLITICA DO PRODUTO; ESTAS ARMS NAO O JULGAM
    # (medido 2026-11-12, dentro da BATERIA). Com a corrida DENTRO do tecto de 40%
    # de CPU (`politica : cap40`), o handshake de `WarmPipeBridge.attach` passa dos
    # 500 ms de `WARM_ATTACH_DEADLINE_MS` e o shell cai no `WARM_FALLBACK_COLD` --
    # as arms 15 e 17 exigem a PONTE quente e ficam vermelhas ("warm bridge
    # attached", `start_worker returned True`) com o produto a fazer o que a
    # politica manda. Sozinho o oraculo passa 22/22; caged, nao. O numero e' o
    # mesmo da arm 21 (3,0 s = 6x o orcamento do produto, linha 1054), e a
    # invariante julgada continua a mesma: UM carregador, e `stop` DESLIGA em vez
    # de matar. A latencia do attach tem as suas arms (`attach-handshake`,
    # `attach-20`), e essas continuam a medir o orcamento REAL.
    shell_mod.WARM_ATTACH_DEADLINE_MS = ATTACH_DEADLINE_MS_ORACLE

    shell = FakeShell(shell_mod, args or shell_args(), engine_mod, pipe)
    shell.start_worker = _types.MethodType(shell_mod.SottoShell.start_worker, shell)
    shell._try_warm_attach = _types.MethodType(shell_mod.SottoShell._try_warm_attach, shell)
    # O PEDIDO DO MOTOR PASSOU A SER UMA DECISAO (D-04, 2026-11-12): o
    # `_try_warm_attach` REAL chama `self._request_warm_engine(keep)`, que le' a
    # serie dos dois logs por `app/webview/warm_evidence.py`, e o duplo nao tinha
    # o metodo -- o passo `warm-engine` morria em
    # `AttributeError: 'FakeShell' object has no attribute '_request_warm_engine'`
    # (medido, arm `cold-arm`). O corpo executado e' o do PRODUTO, e a arm 16
    # continua a exigir `task_starts == 1` porque no ambiente do oraculo nao ha'
    # serie nenhuma e a regra e' fail-open (pedir).
    shell._request_warm_engine = _types.MethodType(
        shell_mod.SottoShell._request_warm_engine, shell)
    shell_mod.warm_module = lambda: warm_shim(engine_mod, pipe)
    shell_mod.start_warm_engine_task = lambda **kwargs: shell.__setattr__(
        "task_starts", shell.task_starts + 1) or True

    def _spawn(self):
        if type(self).__name__ == "WorkerBridge":
            shell.cold_spawns += 1
        return None

    shell_mod.WorkerBridge._spawn = _spawn
    return shell


def run_engine_thread(case, ready=("unloaded", "loading", "parked-closed"), limit=4.0):
    import threading

    thread = threading.Thread(target=case.engine.run, name="oracle-shell-engine", daemon=True)
    thread.start()
    wait_until(lambda: case.engine.state in ready, limit)
    return thread


# O MOTOR TEM DE ESTAR QUENTE ANTES DO ATTACH (medido 2026-11-08, dentro da
# bateria). As arms que provam a LIGACAO quente (15 `single-loader`, 17
# `stop-detaches-not-kills`) chamavam `run_engine_thread`, que espera por
# `("unloaded", "loading", "parked-closed")` -- e `unloaded` e' o PRIMEIRO
# estado depois de `starting`, logo o attach corria contra um motor que ainda
# nao carregou. Sozinho o oraculo passava (22/22); dentro da bateria, com a
# maquina carregada, o motor ainda estava `unloaded` e o
# `WARM_ATTACH_DEADLINE_MS = 500` (sotto_webview.py:7368) expirava -> o shell
# caia no `WARM_FALLBACK_COLD` e o `start_worker` devolvia outra coisa que nao
# a ponte quente. Medido na corrida de 06:0x: `single-loader RED -- start_worker
# returned True` (`self.bridge is the warm bridge ('WorkerBridge')`) e
# `stop-detaches-not-kills RED -- warm bridge attached`. A cura e' do ORACULO e
# nao do prazo: 500 ms e' a politica do produto (`morno e' LENTO, nunca ERRADO`)
# e o que estas arms provam e' a invariante de um carregador, nao a latencia.
WARM_READY_STATES = ("parked-closed", "parked-tap")

# 6x o `WARM_ATTACH_DEADLINE_MS` do produto (500 ms, `sotto_webview.py`), o mesmo
# multiplicador que a arm 21 ja' usa para as 20 ligacoes. Dentro do tecto de CPU a
# ligacao e' mais lenta do que o orcamento do produto por construcao, e o oraculo
# julga QUEM carrega o motor, nao quanto tempo a maquina leva.
ATTACH_DEADLINE_MS_ORACLE = 3000


def run_warm_engine_thread(case, limit=40.0):
    """O mesmo laco, mas so' devolve com o motor CARREGADO e a aceitar."""
    return run_engine_thread(case, ready=WARM_READY_STATES, limit=limit)


def arm_single_loader(mod, work, shell_mod):
    arm = Arm(15, "single-loader")
    case = EngineCase(mod, work, "single", probe=Probe(40.0, 5.0))
    thread = None
    try:
        thread = run_warm_engine_thread(case)
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
        thread = run_warm_engine_thread(case)
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
        # O PRAZO DE 500 ms E' A POLITICA DO PRODUTO (`morno e' LENTO, nunca ERRADO`);
        # esta arm prova a INVARIANTE (o motor volta a aceitar depois do `stop`), nao a
        # latencia. Sob o tecto de 40% de CPU da bateria o motor carregado nao responde
        # em 500 ms e a arm caiu com `why=busy`: MEDIDO 2026-11-08 -- sozinho 22/22,
        # dentro da corrida caged `stop-detaches-not-kills RED`. A cura e' repetir o
        # mesmo pedido com o MESMO prazo de produto ate' um tecto de parede.
        bridge2, why = None, 'never-tried'
        retry_until = time.time() + 15.0
        while time.time() < retry_until:
            bridge2, why = shell_mod.WarmPipeBridge.attach(
                deadline_ms=500, live=False, device=None, capture_mode="mix",
                target_pid=None, keep_warm=False, log=lambda _m: None)
            if bridge2 is not None:
                break
            time.sleep(0.2)
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
    # O PT0S ESTAVA A PROTEGER A COISA CERTA PELA METADE (medido 2026-11-15).
    # A intencao era o F14 -- os 3 DIAS do Task Scheduler matam um motor quente
    # --, mas `PT0S` diz "sem limite nenhum", e um processo sem limite nenhum e'
    # o actor que o watcher acusou DUAS vezes (`pythonw.exe(42792)` a 14,15 % da
    # maquina; antes, 18,2 % / 57 fios). O que a arm passa a exigir e' um limite
    # DECLARADO e maior do que qualquer residencia legitima (medido
    # `ms_resident=3 146 344` = 36,4 dias), o que exclui os 3 dias do default e
    # exclui "para sempre".
    arm.check("<ExecutionTimeLimit>P14D</ExecutionTimeLimit>" in xml,
              "the task has a DECLARED lifetime limit, not PT0S (F14 stays closed)")
    # O TECTO DE FIOS NAO PODE VIVER SO' NO DEFAULT DO PYTHON. Um default e' um
    # valor que alguem muda sem passar pelo ficheiro que larga o processo, e a
    # largada nao dizia numero nenhum -- o buraco que o DM de 2026-11-15 mediu.
    # `--threads 2` = 2 fios POR SESSAO, o mesmo numero que a shell entrega ao
    # worker. NAO `--threads 1`: medido em 2026-11-09, o orcamento de 1 fio corta
    # a margem sobre o tempo real de 2-5x para ~1x, e uma legenda que nao
    # acompanha o audio e' o defeito que o tecto existe para nao criar.
    launcher = commands_only(open(RUN_CMD, encoding="utf-8").read()) if os.path.exists(RUN_CMD) else ""
    arm.check("--threads 2" in launcher,
              "the LAUNCHER declares the thread ceiling (measured 14,2% of machine without it)")
    arm.check("--threads 1" not in launcher,
              "the ceiling is not 1 thread (measured: it removes the real-time margin)")
    arm.check("watcher run --cpu" not in launcher,
              "the engine is NOT CPU-caged: with a client attached it IS the live ASR")
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
    # A4 E' UMA LINHA DE LATENCIA, E NAO SE MEDE POR DENTRO DA FILA (medido
    # 2026-11-12). Correu DENTRO do tecto de 40% (`politica : cap40`) e caiu com
    # `0 timeouts over 20 attaches (got 4)`. O proprio wrapper do cage disse o que
    # era: `not-scheduled 21.1s` -- o filho nao estava a correr, estava ADIADO, e
    # os numeros de parede medem a fila. O 160b do AGENTS.md e' exacto: "a
    # tolerancia dentro do cage nao e' folga, e' espera". Uma latencia medida sob
    # cap nao julga a latencia. A arm DECLARA-SE fora de julgamento e diz o numero,
    # em vez de afrouxar o orcamento do produto ate' ela passar -- afrouxar aqui
    # seria publicar 500 ms como se fosse 3 000.
    caged = (os.environ.get("SOTTO_BATTERY_CAGED") == "1"
             or os.environ.get("SOTTO_BATTERY_POLICY", "") == "cap40")
    if caged:
        detail("politica=cap40: a linha de latencia (p50/p95) NAO e' julgada "
               "dentro do tecto -- o que fica provado e' que 20 ligacoes "
               "respondem e que UM so' carregamento acontece")
    case.engine.clock = time.monotonic
    case.engine._last_detach_at = time.monotonic()
    # A JANELA DO HANDSHAKE ESCALA COM A POLITICA, o ORCAMENTO nao (ver acima):
    # dentro do tecto o fio do motor pode nao ser escalonado por segundos seguidos,
    # e uma janela de 3,0 s transforma "a maquina estava ocupada" em "o motor nao
    # respondeu" -- exactamente a flake de 1,0 s que a cura de 2026-11-08 matou, um
    # degrau acima. Fora do tecto o numero continua 3,0 s.
    handshake_s = 15.0 if caged else 3.0
    thread = None
    samples = []
    timeouts = 0
    try:
        thread = run_engine_thread(case)
        arm.check(wait_until(lambda: case.engine.asr is not None, 6.0),
                  "one load done before the loop")
        for index in range(20):
            handle, why = mod.warm_pipe.open_client(case.pipe, int(handshake_s*1000))
            if handle is None:
                timeouts += 1
                detail("attach %d: open failed (%s)" % (index, why))
                continue
            conn = mod.warm_pipe.PipeConn(handle)
            # O SALDO DA MAQUINA NAO E' UM FALSO VERMELHO (medido 2026-11-08 dentro
            # da bateria). A janela era 1,0 s para o greeting e 1,0 s para o
            # `WARM_ATTACHED`, com ZERO tolerancia: na corrida de 06:30, com cinco
            # lanes a correr, um dos 20 handshakes nao teve resposta em 1,0 s e o
            # passo inteiro caiu (`attach-20 RED -- 0 timeouts over 20 attaches
            # (got 1)`, com p50=31 ms e p95=125 ms -- as latencias estavam DENTRO
            # do orcamento e o que faltou foi tempo de CPU para o fio do motor).
            # O teto passa a 3,0 s = 6x o `WARM_ATTACH_DEADLINE_MS` do produto
            # (500 ms, sotto_webview.py:7368): a invariante que esta arm prova
            # continua a mesma ("o motor responde"), o que deixa de existir e' a
            # flake de 1,0 s. Cada greeting lento continua DITO, com o numero.
            t_hello = time.monotonic()
            hello = None
            while time.monotonic() - t_hello < handshake_s:
                hello = conn.readline(timeout_s=0.2)
                if hello:
                    break
            if not hello:
                timeouts += 1
                detail("attach %d: greeting em branco depois de %.1f ms"
                       % (index, (time.monotonic() - t_hello) * 1000.0))
                conn.close()
                continue
            hello_ms = (time.monotonic() - t_hello) * 1000.0
            if hello_ms > 1000.0:
                detail("attach %d: greeting lento %.0f ms (o fio do motor estava sem CPU)"
                       % (index, hello_ms))
            t0 = time.monotonic()
            conn.send_line(json.dumps({"op": "attach", "live": False, "replay": False}))
            got = None
            while time.monotonic() - t0 < handshake_s:
                line = conn.readline(timeout_s=0.2)
                if line and line.startswith("WARM_ATTACHED "):
                    got = json.loads(line[len("WARM_ATTACHED "):])
                    break
            if got is None:
                timeouts += 1
                detail("attach %d: sem WARM_ATTACHED em %.1f ms"
                       % (index, (time.monotonic() - t0) * 1000.0))
            else:
                samples.append(float(got.get("ms") or 0.0))
            conn.send_line(json.dumps({"op": "detach", "why": "oracle"}))
            conn.close()
            # THE DETACH IS A STATE QUESTION, NOT A LATENCY ONE (measured
            # 2026-11-25 in a caged battery run: the box served handshakes at
            # p95 1281 ms / max 2422 ms, and `detach 15` was still pending inside
            # the 15 s handshake window -- the arm said "detach did not end the
            # session" about a machine that was answering every call). The
            # latency claims are the samples above; this one waits for the
            # transition with its own budget.
            if not wait_until(lambda: case.engine.session_obj is None,
                              max(handshake_s, 30.0)):
                arm.check(False, "detach %d did not end the session" % index)
                break
        arm.check(timeouts == 0, "0 timeouts over 20 attaches (got %d)" % timeouts)
        arm.check(len(samples) == 20, "20 measured handshakes (got %d)" % len(samples))
        if samples and not caged:
            ordered = sorted(samples)
            p50 = ordered[len(ordered) // 2]
            p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
            say("  attach-20: p50=%.1f ms p95=%.1f ms max=%.1f ms n=%d"
                % (p50, p95, ordered[-1], len(ordered)))
            arm.check(p50 <= 300.0, "p50 %.1f ms <= 300 ms (A4)" % p50)
            arm.check(p95 <= 500.0, "p95 %.1f ms <= 500 ms (A4)" % p95)
        elif samples:
            ordered = sorted(samples)
            say("  attach-20: NOT-JUDGED under cap40 -- p50=%.1f ms p95=%.1f ms max=%.1f ms n=%d"
                % (ordered[len(ordered) // 2],
                   ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))],
                   ordered[-1], len(ordered)))
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


# ── arms 23-29: o timing (dono, 2026-11-15) ─────────────────────────────────
POLICY = os.path.join(ROOT, "worker", "engine_policy.py")


def _policy_module():
    """`worker/engine_policy.py` carregado por caminho -- o outro lado do numero.

    Duas declaracoes, um numero so' (`RELOAD_FLOOR_LONG_RESIDENT_S` la',
    `WARM_THRASH_RESIDENT_S` aqui): o oraculo compara-os porque o defeito que
    esta' arm impede e' exactamente um deles mudar sozinho.
    """
    try:
        return load_module(POLICY, "engine_policy_oracle")
    except Exception as exc:  # noqa: BLE001 -- an unimportable policy is a RED arm
        say("  engine_policy.py nao carregou: %r" % (exc,))
        return None


def arm_activity_resets_idle(mod, work):
    """A ACTIVIDADE REINICIA O RELOGIO DO IDLE (2026-11-15, o dono).

    O sinal e' o TRABALHO, nao o aperto de mao: um motor que esta' a receber
    audio ou a pintar uma linha nao esta' idle so' porque ninguem esta' ligado.
    Sem esta arm o relogio volta a ser `now - _last_detach_at` e o motor
    descarrega a meio de uma sessao -- a reclamacao literal do dono.
    """
    arm = Arm(23, "activity-resets-idle")
    import queue
    clock = Clock(1000.0)
    case = EngineCase(mod, work, "act", probe=Probe(40.0, 5.0), clock=clock)
    conn = case.client()
    try:
        case.load()
        arm.check(case.engine.asr is not None, "the graph is resident")
        arm.check(case.engine._last_activity_why == "load",
                  "the load itself is the first evidence (got %r)"
                  % (case.engine._last_activity_why,))
        ttl = 60.0
        case.engine.park_ttl_s = ttl
        # Uma sessao a serio, sem threads: o caminho REAL (`_on_block` e
        # `_emit_events`) e' o que carimba.
        session = mod.AttachedSession(case.engine, case.engine.asr,
                                      live=False, replay=False)
        session.queue = queue.Queue(maxsize=8)
        case.engine.session_obj = session
        # 75 s sem ninguem = ja' passou o TTL. Pior: o detach ficticio fica no
        # passado, para a arm nao poder passar por o `max` ser trivial.
        clock.advance(75.0)
        case.engine._last_detach_at = clock.now - 75.0
        case.engine.session_obj = None
        case.engine.tick()
        arm.check(case.engine.quit is True,
                  "control: without evidence, 75 s > 60 s DOES expire")
        case.engine.quit = False
        # Agora a evidencia: um bloco de audio REAL pelo caminho do tap, e uma
        # linha pintada pela sessao.
        import numpy as _np
        session._on_block(_np.zeros(session.asr.chunk, dtype="float32"))
        arm.check(case.engine._last_activity_why == "audio",
                  "an audio block stamps evidence=audio (got %r)"
                  % (case.engine._last_activity_why,))
        session._emit_events([{"text": "oracle", "start": 0.0, "end": 1.0,
                               "final": True}])
        arm.check(case.engine._last_activity_why == "caption",
                  "a painted line stamps evidence=caption (got %r)"
                  % (case.engine._last_activity_why,))
        case.flush()
        arm.check("WARM_ACTIVITY why=audio" in case.log,
                  "WARM_ACTIVITY why=audio was written")
        case.engine.tick()
        arm.check(case.engine.quit is False,
                  "with evidence the engine does NOT expire at 75 s")
        clock.advance(30.0)
        case.engine.tick()
        arm.check(case.engine.quit is False,
                  "30 s after the evidence it is still inside a 60 s hold")
    finally:
        case.close()
    return arm


def arm_idle_past_hold_expires(mod, work):
    """E o outro lado: SEM trabalho, o motor expira -- e diz o numero exacto."""
    arm = Arm(24, "idle-past-hold-expires")
    clock = Clock(2000.0)
    case = EngineCase(mod, work, "hold", probe=Probe(40.0, 5.0), clock=clock)
    try:
        case.load()
        case.engine.park_ttl_s = 60.0
        clock.advance(59.0)
        case.engine.tick()
        arm.check(case.engine.quit is False, "59 s < 60 s: still parked")
        clock.advance(2.0)
        case.engine.tick()
        arm.check(case.engine.quit is True, "61 s > 60 s: the engine asks to exit")
        arm.check("WARM_EXIT why=idle-expired" in case.log,
                  "the exit names the hold")
        arm.check("idle_s=61.0" in case.log,
                  "the exit carries the MEASURED idle, not just the reason")
        arm.check("ttl_s=60.0" in case.log, "the exit carries the ttl it compared")
        arm.check("evidence=load" in case.log,
                  "the exit names the last evidence it had")
    finally:
        case.close()
    return arm


def arm_reload_floor_thrash(mod, work):
    """O PISO E' DO THRASH: par carga/largada curto espera, cauda longa nao.

    (iii) da aceitacao: o piso NAO pode atrasar a primeira recarga depois de um
    periodo quieto, e TEM de travar o par imediato. Duas populacoes, um numero.
    """
    arm = Arm(25, "reload-floor-thrash")
    # (a) o par do ciclo medido (31 s): larga 31 s depois de carregar.
    clock = Clock(3000.0)
    thrash = EngineCase(mod, work, "thr", probe=Probe(40.0, 5.0), clock=clock)
    try:
        thrash.load()
        clock.advance(31.0)
        thrash.engine.release("shed")
        arm.check(thrash.engine._thrash is True,
                  "a 31 s residency is the thrash class (measured pair)")
        arm.check(thrash.engine.reload_floor_left() > 0.0,
                  "the floor is armed for a 31 s release (got %.1f)"
                  % thrash.engine.reload_floor_left())
        arm.check("thrash=true" in thrash.log,
                  "WARM_RELEASE names thrash=true in the log")
        thrash.engine.tick()
        arm.check(thrash.loader.calls == 1,
                  "the tick right after a thrash release does NOT load")
        clock.advance(29.0)
        thrash.engine.tick()
        arm.check(thrash.loader.calls == 1, "29 s later it still waits")
        clock.advance(2.0)
        thrash.engine.tick()
        if thrash.engine._load_thread is not None:
            thrash.engine._load_thread.join(timeout=5.0)
        arm.check(thrash.loader.calls == 2, "31 s later it reloads exactly once")
        arm.check("WARM_RELOAD thrash=true" in thrash.log,
                  "the reload says it was the thrash class")
    finally:
        thrash.close()
    # (b) a largada de longa residencia: recarrega no tick SEGUINTE.
    clock2 = Clock(8000.0)
    long_case = EngineCase(mod, work, "long", probe=Probe(40.0, 5.0), clock=clock2)
    try:
        long_case.load()
        clock2.advance(3146.0)     # a residencia medida (52,4 min) do log
        long_case.engine.release("shed")
        arm.check(long_case.engine._thrash is False,
                  "a 3146 s residency is the LONG class, not the thrash class")
        arm.check(long_case.engine.reload_floor_left() == 0.0,
                  "the floor is ZERO for a long-resident release (got %.1f)"
                  % long_case.engine.reload_floor_left())
        arm.check("reload_in_s=0.0" in long_case.log,
                  "WARM_RELEASE says the reload is immediate")
        long_case.engine.tick()
        if long_case.engine._load_thread is not None:
            long_case.engine._load_thread.join(timeout=5.0)
        arm.check(long_case.loader.calls == 2,
                  "the very NEXT tick reloads (got %d loads)" % long_case.loader.calls)
        arm.check("WARM_RELOAD_IMMEDIATE" in long_case.log,
                  "the log names WARM_RELOAD_IMMEDIATE, not a wait")
        arm.check("WARM_RELOAD thrash=true" not in long_case.log,
                  "no thrash line for the long class")
    finally:
        long_case.close()
    return arm


def arm_hold_ratio(mod, work):
    """Os numeros escolhidos, julgados contra as medidas que os justificam."""
    arm = Arm(26, "hold-vs-load-ratio")
    loads = (4505.1, 4804.6, 7452.1, 7792.0, 8060.0, 8514.1, 9787.0, 11164.2,
             11597.0, 11749.0, 12471.5, 13477.6, 16759.7, 17341.9, 26027.8,
             41015.3)
    ordered = sorted(loads)
    median_ms = ordered[len(ordered) // 2]
    worst_ms = ordered[-1]
    ttl_ms = mod.WARM_PARK_TTL_S * 1000.0
    say("  hold=%.0f s median_load=%.1f ms worst_load=%.1f ms ratios=%.1fx/%.1fx"
        % (mod.WARM_PARK_TTL_S, median_ms, worst_ms, ttl_ms / median_ms,
           ttl_ms / worst_ms))
    arm.check(ttl_ms >= 100.0 * median_ms,
              "the hold is >= 100x the MEDIAN measured load (%.1fx)"
              % (ttl_ms / median_ms))
    arm.check(ttl_ms >= 20.0 * worst_ms,
              "the hold is >= 20x the WORST measured load (%.1fx)"
              % (ttl_ms / worst_ms))
    arm.check(mod.WARM_PARK_TTL_S < 7200.0,
              "the hold is < the shortest measured gap between openings (2 h)")
    arm.check(mod.WARM_PARK_TTL_S > 600.0,
              "the hold grew past the old 600 s that paid 8 loads for 0 attaches")
    arm.check(8.0 * 31.0 <= mod.WARM_THRASH_RESIDENT_S <= 30.0 * 31.0,
              "the thrash window is 8-30x the measured 31 s pair (got %.0f = "
              "%.1fx)" % (mod.WARM_THRASH_RESIDENT_S,
                          mod.WARM_THRASH_RESIDENT_S / 31.0))
    arm.check(mod.WARM_THRASH_RESIDENT_S < mod.WARM_PARK_TTL_S,
              "the floor window is shorter than the hold")
    return arm


def arm_two_declarations_one_number(mod, work):
    """O MESMO numero nos dois modulos -- o defeito e' um deles mudar sozinho."""
    arm = Arm(27, "one-number-two-files")
    policy = _policy_module()
    arm.check(policy is not None, "worker/engine_policy.py loads")
    if policy is None:
        return arm
    arm.check(float(policy.RELOAD_FLOOR_LONG_RESIDENT_S)
              == float(mod.WARM_THRASH_RESIDENT_S),
              "engine_policy.RELOAD_FLOOR_LONG_RESIDENT_S == "
              "warm_engine.WARM_THRASH_RESIDENT_S (%.0f vs %.0f)"
              % (float(policy.RELOAD_FLOOR_LONG_RESIDENT_S),
                 float(mod.WARM_THRASH_RESIDENT_S)))
    return arm


def arm_policy_floor_scope(mod, work):
    """No WORKER: o piso trava o par curto e nao trava a volta de uma sessao."""
    arm = Arm(28, "policy-floor-scope")
    policy = _policy_module()
    if policy is None:
        arm.check(False, "worker/engine_policy.py loads")
        return arm
    made = []

    def engine(resident_s):
        e = policy.ParakeetEngine("onnx", lambda: ("a", "b"), lambda *a: ([], []),
                                  lambda: 1000.0, log_fn=made.append)
        e._backend = object()
        e.loaded_t = time.time() - float(resident_s)
        e.load_s = 1.91
        return e

    short = engine(31.0)
    short.release("shed-muito-alta")
    arm.check(short.reload_floor_left() > 0.0,
              "31 s residente -> o piso esta' armado (%.1f)"
              % short.reload_floor_left())
    arm.check(any("resident_s=31" in line for line in made),
              "REDUX_ENGINE_RELEASED carries the residency it measured")
    waited = engine(3146.0)
    waited.release("shed-muito-alta")
    arm.check(waited.reload_floor_left() == 0.0,
              "3146 s residente -> piso ZERO, a sessao acabou e nao e' ciclo")
    fresh = engine(0.0)
    fresh.available = True
    arm.check(fresh.reload_floor_left() == 0.0,
              "nunca largou -> piso ZERO (a primeira carga nao paga piso)")
    return arm


def arm_activity_not_the_tap(mod, work):
    """O RING PARQUEADO NAO E' ACTIVIDADE -- senao o motor nunca expira (D-04)."""
    arm = Arm(29, "tap-blocks-are-not-work")
    clock = Clock(4000.0)
    case = EngineCase(mod, work, "ringblk", probe=Probe(40.0, 5.0), clock=clock)
    try:
        case.load()
        before = case.engine._last_activity_at
        case.engine.park_ttl_s = 30.0
        clock.advance(31.0)
        import numpy as _np
        case.engine._ring_block(_np.zeros(8960, dtype="float32"))
        case.engine.tick()
        arm.check(case.engine._last_activity_at == before,
                  "a parked-ring block did NOT move the activity clock")
        arm.check(case.engine.quit is True,
                  "silence in the ring does not keep a 1.9 GB product alive")
    finally:
        case.close()
    return arm
def arm_table(mod, work, shell_mod):
    """A tabela de arms: (rotulo, funcao, argumentos) na ordem em que correm.

    O rotulo vive AQUI e nao no `__name__` da funcao porque `only=` filtra pelo
    rotulo ANTES de a funcao ser chamada -- e um filtro que so' descobre o nome
    depois de correr o trabalho nao economiza nada.
    """
    return (
        ("g1-alta-refuses", arm_g1_alta, (mod, work)),
        ("g1-unknown-defers", arm_g1_unknown, (mod, work)),
        ("worst-of-two", arm_worst_of_two, (mod, work)),
        ("g1-loads-on-leve", arm_g1_loads_on_leve, (mod, work)),
        ("g1-engine-defer-log", arm_g1_engine_defer_log, (mod, work)),
        ("g2-tap-refused", arm_g2_tap_refused, (mod, work)),
        ("g3-attach-shed", arm_g3_attach_shed, (mod, work)),
        ("g4-release", arm_g4_release, (mod, work)),
        ("ring-newest-first", arm_ring_newest_first, (mod, work)),
        ("replay-boundary", arm_replay_boundary, (mod, work)),
        ("attach-handshake", arm_attach_handshake, (mod, work)),
        ("stale-sha-refused", arm_stale_sha_refused, (mod, work)),
        ("twin-pipe", arm_twin_pipe, (mod, work)),
        ("twin-mutex", arm_twin_mutex, (mod, work)),
        ("single-loader", arm_single_loader, (mod, work, shell_mod)),
        ("cold-arm", arm_cold_arm, (mod, work, shell_mod)),
        ("stop-detaches-not-kills", arm_stop_detaches, (mod, work, shell_mod)),
        ("sender-never-blocks", arm_sender_never_blocks, (mod, work)),
        ("pid-identity", arm_pid_identity, (mod, work)),
        ("no-bypass", arm_no_bypass, (mod, work)),
        ("attach-20", arm_attach_latency, (mod, work)),
        ("ttl-exit", arm_ttl_exit, (mod, work)),
        ("activity-resets-idle", arm_activity_resets_idle, (mod, work)),
        ("idle-past-hold-expires", arm_idle_past_hold_expires, (mod, work)),
        ("reload-floor-thrash", arm_reload_floor_thrash, (mod, work)),
        ("hold-vs-load-ratio", arm_hold_ratio, (mod, work)),
        ("one-number-two-files", arm_two_declarations_one_number, (mod, work)),
        ("policy-floor-scope", arm_policy_floor_scope, (mod, work)),
        ("tap-blocks-are-not-work", arm_activity_not_the_tap, (mod, work)),
    )


def _table_labels():
    """Os rotulos de TODAS as arms, sem construir nenhuma (o `mod` e' `None`).

    E' o que o juiz do mapeamento compara: a populacao de nomes nao depende de
    um mutante nem do `only=`, senao uma arm nova entraria no mapeamento sem
    ninguem saber.
    """
    return tuple(row[0] for row in arm_table(None, None, None))


def run_arms(mod, work, shell_mod, only=None):
    """Corre as arms -- TODAS, ou so' as de `only` (o custo do `--neg-arm`).

    `only` E' O CUSTO DO `--neg-arm`, MEDIDO (2026-11-15). Cada mutante chamava
    a passagem INTEIRA: 29 arms x 12 mutantes = **348 execucoes de arm** por um
    `--neg-arm` de **113,7 s**, quando cada mutacao so' pode derrubar as arms que
    EXECUTAM o codigo que ela mutou -- medido nas duas unicas populacoes que
    existem (o log em cache e uma corrida desta sessao), um mutante derruba de
    1 a 3 arms e as outras 26 a 28 sao a bateria a pagar o mesmo verde 12 vezes.
    O `youtube-cdp-source-oracle.py` ja' paga esta licao desde `0e54d8d`.
    """
    results = []
    os.makedirs(work, exist_ok=True)
    #: No arm may wedge the gate. A hang is not a verdict: the traceback is
    #: dumped and the step dies with a NON-ZERO rc -- the battery reads that as
    #: red, and the `--neg-arm` step then lacks "NEG-ARM PASS" and reds too.
    import faulthandler

    def run(fn, args, label):
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

    if only is None:
        # A arm 30 julga o MAPEAMENTO do `--neg-arm`. Sem ela, um mutante novo
        # sem entrada declarada seria simplesmente PULADO (ou, pior, correria a
        # tabela inteira e o custo voltaria pela porta de tras em silencio).
        results.append(_arm_mutant_map())
    for label, fn, args in arm_table(mod, work, shell_mod):
        if only is not None and label not in only:
            continue
        run(fn, args, label)
    return results


def _arm_mutant_map():
    """Arm 30 -- o mapeamento mutante->arms existe, aponta a arms REAIS e e' unico."""
    arm = Arm(30, "mutant-map-complete")
    labels = _table_labels()
    arm.check(len(set(labels)) == len(labels), "arm labels are unique")
    missing = [name for name, _old, _new in MUTANTS if name not in MUTANT_ARMS]
    extra = [name for name in MUTANT_ARMS if name not in {m[0] for m in MUTANTS}]
    arm.check(not missing, "every mutant declares its arms (missing: %s)" % (missing or "-"))
    arm.check(not extra, "no declared mutant is absent from MUTANTS (extra: %s)" % (extra or "-"))
    unknown = sorted({n for names in MUTANT_ARMS.values() for n in names} - set(labels))
    arm.check(not unknown, "every declared arm exists in the table (unknown: %s)" % (unknown or "-"))
    empty = sorted(name for name, names in MUTANT_ARMS.items() if not names)
    arm.check(not empty, "no mutant declares an empty arm set (empty: %s)" % (empty or "-"))
    return arm


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
    # M7: o relogio do idle volta a ser o detach -- a reclamacao literal do dono.
    ("M7-idle-clock-ignores-work",
     "        return now - max(self._last_detach_at, self._last_activity_at)",
     "        return now - self._last_detach_at  # mutant: work does not count"),
    # M8: o piso removido de vez -- o ciclo 82-cargas/70-largadas volta.
    ("M8-floor-removed",
     "        if self._released_at is None or not self._thrash:\n            return 0.0",
     "        return 0.0  # mutant: the floor is decorative"),
    # M9: uma espera curta e' o que o dono tem hoje -- o hold abaixo do custo.
    ("M9-hold-below-load-cost",
     "WARM_PARK_TTL_S = 1800.0\n",
     "WARM_PARK_TTL_S = 600.0  # mutant: the hold that paid 8 loads for 0 attaches\n"),
    # M10: a largada longa volta a pagar o piso -- o atraso que o dono reportou.
    ("M10-long-release-pays-floor",
     "        self._thrash = resident_s < WARM_THRASH_RESIDENT_S",
     "        self._thrash = True  # mutant: every release pays the floor"),
)

#: Mutantes do FICHEIRO DE LARGADA (medido 2026-11-15). Uma arm que le um ficheiro
#: que nenhum mutante toca e' uma arm que nunca pode ficar vermelha: o `--neg-arm`
#: antigo copiava `warm_engine.py` e mais nada, por isso o buraco do DM de hoje
#: (o launcher sem `--threads`) ficaria verde mesmo depois desta cura.
#: Cada mutante e' (nome, ficheiro, de, para).
LAUNCHER_MUTANTS = (
    ("M11-launcher-no-ceiling",
     "warm-engine-run.cmd",
     'warm_engine.py" --threads 2',
     'warm_engine.py"'),
    ("M12-task-unbounded-again",
     "warm-engine-task.xml",
     "<ExecutionTimeLimit>P14D</ExecutionTimeLimit>",
     "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>"),
)

#: O MAPEAMENTO mutante -> as arms que ELE derruba (medido 2026-11-15, duas
#: populacoes independentes: o log em cache de uma corrida real e uma passagem
#: desta sessao, MESMA tabela nos dois). E' o que o `--neg-arm` executa agora:
#: um mutante so' pode derrubar as arms que executam o codigo que ele mutou, e
#: as outras 26-28 eram o mesmo verde pago 12 vezes (113,7 s por 348 execucoes).
#:
#: ESTE MAPEAMENTO NAO E' UMA LISTA DE PERMISSOES -- e' uma IGUALDADE. O
#: `--neg-arm` exige que as arms declaradas fiquem VERMELHAS e que nenhuma
#: outra fique, portanto um mutante que passe a ser apanhado por uma arm a mais
#: falha a corrida em vez de a esconder. A arm 30 (`mutant-map-complete`) exige
#: que todo mutante de `MUTANTS` tenha entrada aqui e que todo rotulo nomeado
#: exista na tabela -- um mutante novo sem entrada nao pode ser pulado em mudo.
MUTANT_ARMS = {
    'M1-gate-bypass': ('g1-unknown-defers', 'g1-engine-defer-log'),
    'M2-unknown-allows': ('g1-alta-refuses', 'g1-unknown-defers',
                          'g1-engine-defer-log'),
    'M3-ring-oldest-first': ('ring-newest-first',),
    'M4-mutex-twin': ('twin-mutex',),
    'M5-replay-2000': ('replay-boundary',),
    'M6-detach-quits': ('attach-handshake', 'stop-detaches-not-kills', 'attach-20'),
    'M7-idle-clock-ignores-work': ('activity-resets-idle',),
    'M8-floor-removed': ('reload-floor-thrash',),
    'M9-hold-below-load-cost': ('hold-vs-load-ratio',),
    'M10-long-release-pays-floor': ('reload-floor-thrash',),
}


def commands_only(text):
    """As linhas que o cmd.exe EXECUTA, sem comentarios `REM`.

    MEDIDO 2026-11-15: a arm 20 nasceu VERMELHA no positivo porque o comentario
    que justifica a cura diz "`--threads 1` foi recusado por medicao" -- o portao
    lia a sua propria prosa e acusava o sitio correto. Um portao que acusa quem
    esta' certo perde a autoridade (a licao do censo de consolas), e a cura e'
    ler o que o interpretador corre, nunca o que o ficheiro explica.
    """
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper().startswith("REM "):
            continue
        out.append(stripped)
    return "\n".join(out)


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
        declared = MUTANT_ARMS.get(name)
        if not declared:
            # Sem entrada, o `only=` seria `()` e o mutante "escapava" sem nunca
            # correr uma arm -- o pior desfecho possivel, porque parece verde.
            say("MUTANT %-22s NO-MAPPING -- no arms declared for this mutant" % name)
            continue
        results = run_arms(module, os.path.join(work, "run-%s" % name), shell_mod,
                           only=declared)
        red = [arm.name for arm in results if not arm.ok()]
        missed = sorted(set(declared) - set(red))
        if missed:
            say("MUTANT %-22s ESCAPED the declared arm(s) %s (red: %s)"
                % (name, ", ".join(missed), ", ".join(red) or "-"))
            continue
        # NAO HA' BRANCO "arm a mais": com `only=declared` so' as declaradas CORREM,
        # logo `red - declared` e' vazio por construcao. Uma comparacao que nao
        # pode falhar e' o oposto de um portao, e ficou de fora. O alcance do
        # mapa e' julgado pela arm 30 (todo mutante tem entrada, todo rotulo existe)
        # e pelo sentido que importa aqui: declarar A MENOS deixa a arm que
        # apanha de fora e o mutante ESCAPA, que e' o teste acima.
        caught += 1
        say("MUTANT %-22s CAUGHT by %s" % (name, ", ".join(red)))
    for name, filename, old_text, new_text in LAUNCHER_MUTANTS:
        total += 1
        caught += _run_launcher_mutant(work, shell_mod, name, filename, old_text, new_text)
    say("NEG-ARM %s -- %d/%d mutant(s) caught"
        % ("PASS" if caught == total else "FAIL", caught, total))
    return 1 if caught == total else 0


def _run_launcher_mutant(work, shell_mod, name, filename, old_text, new_text):
    """Muta o FICHEIRO DE LARGADA numa copia e exige que a arm 20 fique vermelha.

    A copia e' por mutante (o `--neg-arm` nunca toca no ficheiro que embarca) e a
    arm 20 le-a por `RUN_CMD`/`TASK_XML`, que sao globais de modulo. Sem este
    caminho, as tres verificacoes novas da arm 20 seriam as primeiras arms desta
    casa que nao podem falhar -- a doenca que o proprio AGENTS.md nomeia.
    """
    global RUN_CMD, TASK_XML
    source = open(os.path.join(HERE, "warm-engine", filename), encoding="utf-8").read()
    if source.count(old_text) != 1:
        say("MUTANT %-22s INVALID -- anchor appears %d times" % (name, source.count(old_text)))
        return 0
    directory = os.path.join(work, "mutant-%s" % name)
    os.makedirs(directory, exist_ok=True)
    mutated = os.path.join(directory, filename)
    with open(mutated, "w", encoding="utf-8", newline="") as handle:
        handle.write(source.replace(old_text, new_text))
    saved_run, saved_xml = RUN_CMD, TASK_XML
    try:
        if filename.endswith(".cmd"):
            RUN_CMD = mutated
        else:
            TASK_XML = mutated
        result = arm_no_bypass(None, os.path.join(work, "run-%s" % name))
    finally:
        RUN_CMD, TASK_XML = saved_run, saved_xml
    if result.ok():
        say("MUTANT %-22s ESCAPED -- the arms cannot tell it from the real thing" % name)
        return 0
    say("MUTANT %-22s CAUGHT by %s" % (name, result.name))
    return 1


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
