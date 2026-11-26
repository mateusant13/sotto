#!/usr/bin/env python
# NO-BUG: instrumento (2026-11-25) do contrato de UMA captura por chamada -- publica o bloco misturado num socket loopback com taps FALSOS, nao corrige o produto e nao abre dispositivo
"""ORACLE: ONE MIXED CAPTURE, ONE CLIENT, A BOUNDED QUEUE AND AN HONEST FALLBACK.

WHY THIS INSTRUMENT EXISTS
--------------------------
The measured defect (`worker/sotto_worker.py` and `worker/speaker_sidecar.py`,
2026-11-25) was TWO loopback taps and TWO microphone streams for ONE call. The
worker's `mic_tap.open_stream` already mixes the owner's voice into the render
tap and hands 16 kHz mono float32 to the ASR; the sidecar then opened the same
kind of pair again. Two devices cost twice as much, can resolve to different
endpoints (measured already: VoiceMeeter vs. the owner's actual headphones),
and mix the microphone twice.

`worker/capture_share.py` publishes the exact block at the worker's ASR stage
boundary (`sotto_worker.py`, after `resample_to_16k`) on a loopback-only TCP
port. This oracle uses a REAL Windows loopback socket for every transport arm
and FAKE taps for the device arms -- no audio device is opened, no popup is
created, no model is loaded. It gates:

  a  one client gets the exact bytes, in order, and nothing is sent when alone
  b  the one client slot refuses a second client (with a named reason)
  c  a slow reader makes the bounded queue DROP and COUNT, never grow
  d  with no publisher, the real sidecar `main` prints its fallback reason and
     constructs its own tap
  e  SOTTO_CAPTURE_SHARE=0 disables the client even with a publisher listening
  f  the worker's real `LoopbackTap` + real `mic_tap.open_stream` construct one
     device pair, while the sidecar in shared mode constructs ZERO taps

THE NEGATIVE ARM IS BEHAVIOURAL. Each mutation is written to a temporary copy
of the real source and that copy is EXECUTED by the arm that owns it. A mutant
whose anchor is missing or whose battery crashes counts as DECORATIVE, not as
caught -- an oracle that says 6/6 while testing four mutations proves nothing.

Run:  python _main/capture-share-oracle.py
      python _main/capture-share-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import io
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER_DIR = os.path.join(ROOT, "worker")
CS_PATH = os.path.join(WORKER_DIR, "capture_share.py")
SIDECAR_PATH = os.path.join(WORKER_DIR, "speaker_sidecar.py")
WORKER_PATH = os.path.join(WORKER_DIR, "sotto_worker.py")
MIC_PATH = os.path.join(WORKER_DIR, "mic_tap.py")
if WORKER_DIR not in sys.path:
    sys.path.insert(0, WORKER_DIR)

EXIT_PASS, EXIT_FAIL = 0, 1
_LOAD_SEQ = [0]


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fresh_name(prefix: str) -> str:
    _LOAD_SEQ[0] += 1
    return "%s_%d" % (prefix, _LOAD_SEQ[0])


def free_port() -> int:
    """An unused loopback port, obtained from the OS rather than guessed."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def source(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def func_from(src: str, name: str):
    for node in ast.parse(src).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise RuntimeError("no function %s in source" % name)


def result(ok, name, detail=""):
    return (bool(ok), name, str(detail))


# ── (a) exact bytes, one client, zero cost while alone ───────────────────────
def arm_exact(bundle):
    cs = bundle["cs"]
    logs = []
    port = free_port()
    pub = client = None
    try:
        pub = cs.Publisher(port=port, log=logs.append).start()
        import numpy as np
        alone = np.arange(320, dtype=np.float32)
        idle = pub.publish(alone)
        if idle or pub.connected or pub.queued or pub.drops:
            return result(False, "a exact blocks / idle publisher",
                          "idle publish=%r connected=%r queued=%d drops=%d"
                          % (idle, pub.connected, pub.queued, pub.drops))

        client = cs.connect_client(port=port, log=logs.append)
        if client is None:
            return result(False, "a exact blocks / idle publisher",
                          "client refused: %r" % logs)
        if not wait_until(lambda: pub.connected, 1.0):
            return result(False, "a exact blocks / idle publisher",
                          "publisher never saw the client: %r" % logs)
        got = []
        client.set_sink(lambda block: got.append(block.tobytes()))
        client.start()
        expected = []
        for i in range(6):
            block = (np.arange(320, dtype=np.float32) + i * 0.25)
            expected.append(block.tobytes())
            pub.publish(block)
        arrived = wait_until(lambda: len(got) >= len(expected), 2.0)
        exact = got[:len(expected)] == expected
        connected = "CAPTURE_SHARE client=connected from=worker" in logs
        return result(arrived and exact and connected and not idle,
                      "a exact blocks / idle publisher",
                      "arrived=%d/%d exact=%s idle=%r connected_line=%s"
                      % (len(got), len(expected), exact, idle, connected))
    finally:
        if client is not None:
            client.stop()
        if pub is not None:
            pub.stop()


# ── (b) one slot only ────────────────────────────────────────────────────────
def arm_one_slot(bundle):
    cs = bundle["cs"]
    logs = []
    port = free_port()
    pub = first = None
    try:
        pub = cs.Publisher(port=port, log=logs.append).start()
        first = cs.connect_client(port=port, log=logs.append)
        if first is None or not wait_until(lambda: pub.connected, 1.0):
            return result(False, "b second client refused",
                          "first client never connected: %r" % logs)
        second = cs.connect_client(port=port, log=logs.append)
        refused = second is None
        named = any("fallback reason=busy" in line for line in logs)
        still = pub.connected and first.alive
        return result(refused and named and still, "b second client refused",
                      "second=%r named=%s first_alive=%s logs=%r"
                      % (second, named, first.alive, logs))
    finally:
        if first is not None:
            first.stop()
        if pub is not None:
            pub.stop()


# ── (g) a stranger's failed handshake must not eject the slot holder ────────
def arm_stranger(bundle):
    """REVIEWER FINDING 2026-11-25: closing a silent newcomer used to call
    `_disconnect("handshake failed")`, which released the slot the legitimate
    sidecar held -- any local process could push the product back onto TWO
    loopback+mic pairs by connecting and saying nothing. The slot belongs to
    whoever passed the handshake; a stranger is answered BUSY and closed."""
    cs = bundle["cs"]
    logs = []
    port = free_port()
    pub = first = stalled = None
    try:
        pub = cs.Publisher(port=port, log=logs.append).start()
        first = cs.connect_client(port=port, log=logs.append)
        if first is None or not wait_until(lambda: pub.connected, 1.0):
            return result(False, "g a stranger cannot eject the slot holder",
                          "first never connected: %r" % logs)
        stalled = socket.create_connection(("127.0.0.1", port), timeout=2.0)
        # Say NOTHING, exactly as a broken local peer would.
        ejected = wait_until(lambda: not pub.connected, 1.5)
        still = (not ejected) and pub.connected and first.alive
        return result(still, "g a stranger cannot eject the slot holder",
                      "ejected=%s pub_connected=%s first_alive=%s logs=%r"
                      % (ejected, pub.connected, first.alive, logs[-3:]))
    finally:
        if stalled is not None:
            try:
                stalled.close()
            except OSError:
                pass
        if first is not None:
            first.stop()
        if pub is not None:
            pub.stop()


# ── (h) an orderly client stop is not a publisher failure ──────────────────
def arm_orderly_stop(bundle):
    """MEASURED 2026-11-25: `stop()` shuts the socket down before the reader
    sees `_stop`, so the EOF branch declared `publisher-closed` and the sidecar
    opened a DUPLICATE local loopback tap while shutting down -- the second
    device pair this transport exists to prevent. Only a stop we did not ask
    for is a failure, and that is asserted here directly instead of through the
    sidecar's shutdown race."""
    cs = bundle["cs"]
    logs = []
    port = free_port()
    pub = client = None
    try:
        pub = cs.Publisher(port=port, log=logs.append).start()
        client = cs.connect_client(port=port, log=logs.append)
        if client is None:
            return result(False, "h an orderly stop is not a failure",
                          "connect failed: %r" % logs)
        client.set_sink(lambda _b: None)
        client.start()
        import numpy as np
        block = np.full(1600, 0.25, dtype=np.float32)
        for _ in range(3):
            pub.publish(block)
        wait_until(lambda: pub.queued == 0, 1.0)
        client.stop()
        named = [line for line in logs if line.startswith("CAPTURE_SHARE fallback")]
        ok = client.failure_reason is None and not named
        return result(ok, "h an orderly stop is not a failure",
                      "reason=%r fallback_lines=%r"
                      % (client.failure_reason, named))
    finally:
        if client is not None:
            client.stop()
        if pub is not None:
            pub.stop()


# ── (c) bounded queue, counted drops ────────────────────────────────────────
def arm_drops(bundle):
    cs = bundle["cs"]
    logs = []
    port = free_port()
    pub = raw = None
    cap = 8
    try:
        pub = cs.Publisher(port=port, log=logs.append, max_blocks=cap).start()
        raw = socket.create_connection(("127.0.0.1", port), timeout=2.0)
        raw.sendall(cs.HELLO)
        reply = b""
        while not reply.endswith(b"\n") and len(reply) < 32:
            reply += raw.recv(1)
        if reply != cs.OK:
            return result(False, "c bounded queue counts drops",
                          "handshake=%r" % reply)
        import numpy as np
        block = np.arange(16384, dtype=np.float32)        # 64 KiB per block
        for _ in range(400):                              # 25 MiB, no reader
            pub.publish(block)
        dropped = wait_until(lambda: pub.drops > 0, 2.0)
        bounded = pub.queued <= cap
        before = pub.drops
        for _ in range(50):
            pub.publish(block)
        counted = pub.drops > before
        lines = [line for line in logs if line.startswith("CAPTURE_SHARE_DROP dropped=")]
        reported = max((int(line.rsplit("=", 1)[1]) for line in lines), default=0)
        ok = dropped and bounded and counted and reported >= 1 and reported <= pub.drops
        return result(ok, "c bounded queue counts drops",
                      "drops=%d queued=%d cap=%d reported=%d lines=%d"
                      % (pub.drops, pub.queued, cap, reported, len(lines)))
    finally:
        if raw is not None:
            try:
                raw.close()
            except OSError:
                pass
        if pub is not None:
            pub.stop()


class _FakeStream:
    def __init__(self, counter=None):
        self.counter = counter
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1
        if self.counter is not None:
            self.counter["starts"] += 1

    def stop(self):
        self.stopped += 1


class _FakeTap:
    def __init__(self, counter=None):
        self.stream = _FakeStream(counter)
        self.rate = 48000


def _fake_session():
    return types.SimpleNamespace(
        sotto_cuda_device_census=True,
        sotto_graph_assignment_readback="1",
        sotto_node_assignment_counts={"CUDAExecutionProvider": 46},
        sotto_node_assignment_cuda_share=1.0,
        sotto_node_assignment_cpu=[],
        sotto_runtime_fallback_readback=False,
        sotto_provider_readback=["CUDAExecutionProvider"],
    )


def run_sidecar_watch(bundle, port, enabled, counter, tmp, cs_override=None):
    """Run the REAL sidecar main with fake endpoints/taps, no device, no model."""
    import capture_share as shipped_cs

    cs = cs_override if cs_override is not None else bundle["cs"]
    mod = load_module(bundle["sidecar"], fresh_name("sidecar_watch"))
    model = os.path.join(tmp, "watch-model.onnx")
    with open(model, "wb") as fh:
        fh.write(b"placeholder, never read by the fake session")
    fake_wasapi = types.SimpleNamespace(
        loopback_device_specs=lambda: [{"name": "fake endpoint",
                                        "rate": 48000, "default": True}],
        live_endpoint_order=lambda: [],
        default_render_endpoint=lambda: None,
        WasapiLoopbackTap=lambda *a, **k: _FakeTap(counter),
    )

    def fake_tap(_spec, _sink, **_kwargs):
        counter["taps"] += 1
        return _FakeTap(counter), "mic=fake"

    prior_cs = sys.modules.get("capture_share")
    prior_wasapi = sys.modules.get("wasapi_loopback")
    prior_loader = mod._load_powerset
    prior_tap = mod._tap_for
    prior_evicted = mod.resume_evicted_total
    old_env = {k: os.environ.get(k) for k in
               ("SOTTO_CAPTURE_SHARE", "SOTTO_CAPTURE_SHARE_PORT")}
    out = io.StringIO()
    try:
        sys.modules["capture_share"] = cs
        sys.modules["wasapi_loopback"] = fake_wasapi
        mod._load_powerset = lambda *_a, **_k: _fake_session()
        mod._tap_for = fake_tap
        mod.resume_evicted_total = lambda _path: 0
        os.environ["SOTTO_CAPTURE_SHARE"] = enabled
        os.environ["SOTTO_CAPTURE_SHARE_PORT"] = str(port)
        with contextlib.redirect_stdout(out):
            rc = mod.main(["--watch-only", "--seg-model", model,
                           "--duration-s", "-1"])
    finally:
        mod._load_powerset, mod._tap_for = prior_loader, prior_tap
        mod.resume_evicted_total = prior_evicted
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if prior_cs is None:
            sys.modules.pop("capture_share", None)
        else:
            sys.modules["capture_share"] = prior_cs
        if prior_wasapi is None:
            sys.modules.pop("wasapi_loopback", None)
        else:
            sys.modules["wasapi_loopback"] = prior_wasapi
    del shipped_cs
    return rc, out.getvalue()


# ── (d) no publisher: real sidecar falls back to its own tap ────────────────
def arm_fallback(bundle, tmp, cs_override=None):
    port = free_port()                                   # deliberately no listener
    counter = {"taps": 0, "starts": 0}
    rc, out = run_sidecar_watch(bundle, port, "1", counter, tmp, cs_override)
    named = "CAPTURE_SHARE fallback reason=no-publisher" in out
    connected = "CAPTURE_SHARE client=connected" in out
    ok = rc == 0 and named and not connected and counter["taps"] == 1 \
        and counter["starts"] == 1
    return result(ok, "d fallback when no publisher",
                  "rc=%d taps=%d starts=%d reason=%s out=%r"
                  % (rc, counter["taps"], counter["starts"], named, out[-200:]))


# ── (i) a BUSY slot degrades to NO DIARIZATION, not to a second device pair ──
def arm_busy_slot(bundle, tmp):
    """MEDIDO 2026-11-26: com a slot ocupada, o sidecar abria o SEU loopback+micro
    enquanto o worker ja' capturava nos MESMOS endpoints (`taps=1`,
    `MIC_CAPTURE mic=fake`) -- o "UMA CAPTURA, UM LEITOR" do AGENTS.md violado
    pelo proprio fallback. A degradacao correcta e' NOMEADA e sem dispositivo:
    rc=2, `fallback reason=busy`, `no diarization`, zero taps, zero micros."""
    cs = bundle["cs"]
    port = free_port()
    pub = raw = None
    try:
        pub = cs.Publisher(port=port, log=lambda _m: None).start()
        # Um cliente cru segura a slot sem `connect_client` (o HELLO e' publico).
        raw = socket.create_connection(("127.0.0.1", port), timeout=2.0)
        raw.sendall(cs.HELLO)
        reply = raw.recv(32)
        counter = {"taps": 0, "starts": 0}
        rc, out = run_sidecar_watch(bundle, port, "1", counter, tmp)
        named = "CAPTURE_SHARE fallback reason=busy" in out
        degraded = "no diarization" in out
        ok = (reply.startswith(b"OK") and rc == 2 and named and degraded
              and counter["taps"] == 0 and counter["starts"] == 0
              and "MIC_CAPTURE" not in out)
        return result(ok, "i busy slot degrades to no second device",
                      "rc=%d taps=%d starts=%d named=%s degraded=%s out=%r"
                      % (rc, counter["taps"], counter["starts"], named,
                         degraded, out[-160:]))
    finally:
        if raw is not None:
            raw.close()
        if pub is not None:
            pub.stop()


# ── (e) explicit off switch beats a live publisher ──────────────────────────
def arm_disabled(bundle, tmp, cs_override=None):
    cs = bundle["cs"]
    logs = []
    port = free_port()
    pub = None
    try:
        pub = cs.Publisher(port=port, log=logs.append).start()
        counter = {"taps": 0, "starts": 0}
        rc, out = run_sidecar_watch(bundle, port, "0", counter, tmp, cs_override)
        named = "CAPTURE_SHARE fallback reason=disabled" in out
        ok = rc == 0 and named and not pub.connected and counter["taps"] == 1
        return result(ok, "e SOTTO_CAPTURE_SHARE=0 disables client",
                      "rc=%d named=%s connected=%r taps=%d out=%r"
                      % (rc, named, pub.connected, counter["taps"], out[-200:]))
    finally:
        if pub is not None:
            pub.stop()


class _FakeRealTap:
    def __init__(self, counter, on_block=None, **_kwargs):
        counter["taps"] += 1
        self.rate = 16000
        self.on_block = on_block
        self.stream = _FakeStream(counter)


def worker_device_count(worker_path, mic_src=None):
    """Execute the worker's real LoopbackTap + mic_tap.open_stream on fakes."""
    count = {"taps": 0, "mics": 0, "starts": 0}
    mic_src = mic_src if mic_src is not None else source(MIC_PATH)

    class FakeConversationTap:
        def __init__(self, mic, sink, note=""):
            self._on_primary = sink

        def attach(self, tap):
            return tap

    def fake_mic_or_refusal(_prefer):
        count["mics"] += 1
        return object(), "mic=fake"

    ns = {
        "__name__": "capture_share_worker_sandbox",
        "TARGET_SR": 16000,
        "err": lambda *_a, **_k: None,
        "ProcessLoopbackTap": lambda *a, **k: None,
        "FileTap": lambda *a, **k: None,
        "_PortAudioTap": lambda *a, **k: None,
        "_mic_or_refusal": fake_mic_or_refusal,
        "ConversationTap": FakeConversationTap,
    }
    body = [func_from(source(worker_path), "LoopbackTap"),
            func_from(mic_src, "open_stream")]
    prior_wasapi = sys.modules.get("wasapi_loopback")
    prior_mic = sys.modules.get("mic_tap")
    try:
        sys.modules["wasapi_loopback"] = types.SimpleNamespace(
            WasapiLoopbackTap=lambda on_block, **kw: _FakeRealTap(count, on_block, **kw))
        exec(compile(ast.Module(body=body, type_ignores=[]), worker_path, "exec"), ns)
        sys.modules["mic_tap"] = types.SimpleNamespace(open_stream=ns["open_stream"])
        tap = ns["LoopbackTap"](
            {"name": "fake render endpoint", "wasapi_loopback": True,
             "endpoint_id": "fake-id"},
            lambda _block: None)
        return count, tap
    finally:
        if prior_wasapi is None:
            sys.modules.pop("wasapi_loopback", None)
        else:
            sys.modules["wasapi_loopback"] = prior_wasapi
        if prior_mic is None:
            sys.modules.pop("mic_tap", None)
        else:
            sys.modules["mic_tap"] = prior_mic


# ── (f) one device pair opened by the worker, none by the shared sidecar ────
def arm_one_device(bundle, tmp, worker_path=None):
    bundle_worker = worker_path if worker_path is not None else bundle["worker"]
    count, tap = worker_device_count(bundle_worker)
    worker_one = count["taps"] == 1 and count["mics"] == 1 and tap is not None

    cs = bundle["cs"]
    port = free_port()
    pub = None
    try:
        pub = cs.Publisher(port=port, log=lambda _m: None).start()
        counter = {"taps": 0, "starts": 0}
        rc, out = run_sidecar_watch(bundle, port, "1", counter, tmp)
        # The sidecar IS the client here: its fake `_tap_for` counts every
        # device it would have opened. In shared mode that count must be 0,
        # while the worker's real tap code above constructed exactly one.
        shared = ("CAPTURE_SHARE client=connected from=worker" in out
                  and counter["taps"] == 0 and rc == 0)
        ok = worker_one and shared
        return result(ok, "f one worker device / zero client devices",
                      "worker_taps=%d worker_mics=%d sidecar_taps=%d "
                      "connected=%s rc=%d"
                      % (count["taps"], count["mics"], counter["taps"],
                         "CAPTURE_SHARE client=connected" in out, rc))
    finally:
        if pub is not None:
            pub.stop()


ARMS = [
    ("a exact blocks / idle publisher", arm_exact),
    ("b second client refused", arm_one_slot),
    ("c bounded queue counts drops", arm_drops),
    ("d fallback when no publisher", arm_fallback),
    ("e SOTTO_CAPTURE_SHARE=0 disables client", arm_disabled),
    ("f one worker device / zero client devices", arm_one_device),
    ("g a stranger cannot eject the slot holder", arm_stranger),
    ("h an orderly stop is not a failure", arm_orderly_stop),
    ("i busy slot degrades to no second device", arm_busy_slot),
]

#: (label, source file, old, new, owning arm). Every mutation must make the
#: owning arm RED when the MUTATED SOURCE IS EXECUTED, not merely grep'd.
MUTANTS = [
    ("publish-truncates-a-byte", "cs",
     "            self._queue.put_nowait(payload)\n            return True",
     "            self._queue.put_nowait(payload[:-1])\n            return True"),
    ("second-client-accepted", "cs",
     "                with self._lock:\n"
     "                    busy = self._connected\n"
     "                    if not busy:\n"
     "                        self._connected = True",
     "                with self._lock:\n"
     "                    busy = False\n"
     "                    self._connected = True"),
    ("queue-made-unbounded", "cs",
     "self._queue = queue.Queue(maxsize=max(1, int(max_blocks)))",
     "self._queue = queue.Queue(maxsize=0)"),
    ("fallback-reason-silenced", "cs",
     '        log("CAPTURE_SHARE fallback reason=no-publisher (%s)" % type(exc).__name__)',
     "        pass  # mutation: no fallback reason is printed"),
    ("disable-env-ignored", "cs",
     "    if share_disabled(env):\n        log(\"CAPTURE_SHARE fallback reason=disabled\")",
     "    if False:\n        log(\"CAPTURE_SHARE fallback reason=disabled\")"),
    #: The anchor MUST name the rung arm `f` exercises (the WASAPI endpoint):
    #: the first draft anchored on the bare `open_stream`/`return tap` triple,
    #: which now occurs on three rungs, so `replace(..., 1)` mutated the
    #: process-loopback branch and arm `f` -- which opens the wasapi branch --
    #: never executed the mutant. A mutation that lands somewhere the arm cannot
    #: see is decorative, and this one reported SURVIVED on the merged tree.
    ("worker-opens-two-taps", "worker",
     "            return wasapi_loopback.WasapiLoopbackTap(\n"
     "                on_block, block_ms=block_ms, endpoint_id=device.get(\"endpoint_id\"))\n"
     "\n"
     "        tap, mic_note = mic_tap.open_stream(make_primary, on_block)\n"
     "        err(\"MIC_CAPTURE %s\" % mic_note)\n"
     "        return tap",
     "            return wasapi_loopback.WasapiLoopbackTap(\n"
     "                on_block, block_ms=block_ms, endpoint_id=device.get(\"endpoint_id\"))\n"
     "\n"
     "        tap, mic_note = mic_tap.open_stream(make_primary, on_block)\n"
     "        err(\"MIC_CAPTURE %s\" % mic_note)\n"
     "        other, _note = mic_tap.open_stream(make_primary, on_block)\n"
     "        return tap if other is None else other"),
    ("stranger-ejects-slot", "cs",
     "            except (OSError, socket.timeout):\n"
     "                # A STRANGER'S FAILED HANDSHAKE MUST NOT EJECT THE CLIENT THAT\n",
     "            except (OSError, socket.timeout):\n"
     "                self._disconnect(\"handshake failed\")\n"
     "                # A STRANGER'S FAILED HANDSHAKE MUST NOT EJECT THE CLIENT THAT\n"),
    ("busy-fallback-opens-second-pair", "sidecar",
     '    if busy:\n'
     '        print("sidecar: no diarization -- capture slot busy; "\n'
     '              "no second device opened")\n'
     '        return 2\n',
     ''),
    ("orderly-stop-looks-like-crash", "cs",
     "                    if not self._stop.is_set():\n"
     "                        self._fail(\"publisher-closed\")\n"
     "                    return\n"
     "                size = struct.unpack(\"<I\", head)[0]",
     "                    self._fail(\"publisher-closed\")\n"
     "                    return\n"
     "                size = struct.unpack(\"<I\", head)[0]"),
]


def bundle_for(cs_path=CS_PATH, worker_path=WORKER_PATH, sidecar_path=SIDECAR_PATH):
    return {
        "cs": load_module(cs_path, fresh_name("capture_share_live")),
        "sidecar": sidecar_path,
        "worker": worker_path,
        "cs_path": cs_path,
        "sidecar_path": sidecar_path,
    }


def run_arms(bundle, tmp, cs_override=None, worker_path=None, only=None):
    out = []
    argv = [] if only is None else [only]
    for name, fn in ARMS:
        if argv and name not in argv:
            continue
        try:
            if name.startswith("i "):
                out.append(fn(bundle, tmp))
            elif name.startswith("d ") or name.startswith("e "):
                out.append(fn(bundle, tmp, cs_override))
            elif name.startswith("f "):
                out.append(fn(bundle, tmp, worker_path))
            else:
                out.append(fn(bundle))
        except Exception as exc:                                # noqa: BLE001
            out.append(result(False, name, "ARM CRASHED %s: %s"
                              % (type(exc).__name__, exc)))
        print("  %s %s%s" % ("GREEN" if out[-1][0] else "RED  ", out[-1][1],
                             ("  " + out[-1][2]) if out[-1][2] else ""))
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true",
                    help="run the six source mutations; each must redden its arm")
    args = ap.parse_args(argv)

    for path in (CS_PATH, SIDECAR_PATH, WORKER_PATH, MIC_PATH):
        if not os.path.isfile(path):
            print("RED   module missing: %s" % path)
            return EXIT_FAIL

    with tempfile.TemporaryDirectory(prefix="capture-share-oracle-") as tmp:
        bundle = bundle_for()
        if not args.neg_arm:
            rows = run_arms(bundle, tmp)
            green = sum(1 for ok, _, _ in rows if ok)
            print("\nCAPTURE SHARE VERDICT: %s (%d/%d arms)"
                  % ("PASS" if green == len(rows) else "FAIL", green, len(rows)))
            return EXIT_PASS if green == len(rows) else EXIT_FAIL

        print("NEGATIVE ARM (mutated sources must go RED)")
        caught, weak = 0, 0
        for label, target, old, new in MUTANTS:
            key = target if target in ("cs", "worker", "sidecar") else "worker"
            path = {"cs": bundle["cs_path"], "worker": bundle["worker"],
                    "sidecar": bundle["sidecar_path"]}[key]
            src = source(path)
            if old not in src:
                print("  RED   mutant %-28s ANCHOR MISSING -- oracle is stale" % label)
                weak += 1
                continue
            mutant_path = os.path.join(tmp, "%s_%s.py" % (key, label))
            with open(mutant_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(src.replace(old, new, 1))
            try:
                mutant_bundle = bundle_for(
                    cs_path=mutant_path if key == "cs" else bundle["cs_path"],
                    worker_path=mutant_path if key == "worker" else bundle["worker"],
                    sidecar_path=(mutant_path if key == "sidecar"
                                  else bundle["sidecar_path"]))
                owner = next(name for name, _fn in ARMS
                             if name.startswith(
                                 {"publish-truncates-a-byte": "a ",
                                  "second-client-accepted": "b ",
                                  "queue-made-unbounded": "c ",
                                  "fallback-reason-silenced": "d ",
                                  "disable-env-ignored": "e ",
                                  "worker-opens-two-taps": "f ",
                                  "stranger-ejects-slot": "g ",
                                  "busy-fallback-opens-second-pair": "i ",
                                  "orderly-stop-looks-like-crash": "h "}[label]))
                rows = run_arms(mutant_bundle, tmp, only=owner)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-28s BATTERY CRASHED (%s)" % (label, type(exc).__name__))
                weak += 1
                continue
            if rows and not rows[0][0]:
                print("  GREEN mutant %-28s caught by: %s" % (label, rows[0][1]))
                caught += 1
            else:
                print("  RED   mutant %-28s SURVIVED -- the gate is blind here" % label)

        total = len(MUTANTS)
        ok = caught == total and weak == 0
        print("\nNEG ARM VERDICT: %s (%d/%d mutants caught, %d decorative)"
              % ("PASS" if ok else "FAIL", caught, total, weak))
        # A control run exits 1 when every injected defect was caught (house
        # convention, `:expectred`), 2 when the control itself failed.
        return EXIT_PASS + 1 if ok else EXIT_FAIL + 1


if __name__ == "__main__":
    sys.exit(main())
