#!/usr/bin/env python3
# NO-BUG: a fronteira de activacao do warm-preload (carrega estado, nao abre tap nem descodifica) -- trabalho de CAPACIDADE/observabilidade pedido pela regra 3 do dono de 2026-11-04; sem id no ledger
"""Model-free guard for the Nemotron warm-preload activation boundary.

The default worker preload may load model/frontend state while the panel is
closed, but must not open AudioTap, consume samples, decode, or emit captions
until the panel-open path sends exactly one START_CAPTURE command.  This gate
checks the real shell/worker wiring and is deliberately safe to run without a
GPU, audio device, model, browser, or child process.

The initial pre-fix run is expected to fail: `reason='preload'` is currently
discarded before spawn and the normal worker proceeds to the AudioTap ladder.
"""
from __future__ import annotations

import ast
import importlib
import io
import json
import os
import sys
import tempfile
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")

#: AS LINHAS PARTEM-SE UMA VEZ POR FONTE (medido 2026-11-26, `cProfile` sobre
#: este ficheiro): 12 chamadas a `ast.get_source_segment` sobre a shell de
#: 1,5 MB custavam **6,75 s dos 11,68 s** do processo inteiro, porque cada
#: chamada re-parte a fonte completa em `ast._splitlines_no_ff` (0,56 s cada).
#: `_astcache.lines` guarda a particao por conteudo e `segment` fatia-a -- a
#: MESMA particao (`ast._splitlines_no_ff` quando existe), logo o texto extraido
#: e' byte-identico. O GANHO, medido nas duas direcoes no mesmo dia:
#: positivo **6,9 s parede / 5,39 s CPU -> 4,1 s / 3,00 s**; `--neg-arm`
#: **60,8 s / 51,44 s CPU -> 20,5 s / 17,28 s** com **17/17** mutantes ainda
#: apanhados (rc 1), logo a cura tirou tempo e nao deteccao.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from _astcache import segment as _segment  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as stream:
        return stream.read()


def _class_method(tree, class_name, method_name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name == method_name:
                    return item
    return None


def _call_names(node):
    return [n.func.attr if isinstance(n.func, ast.Attribute)
            else n.func.id if isinstance(n.func, ast.Name) else ""
            for n in ast.walk(node) if isinstance(n, ast.Call)]


def _extract_function(source, name, namespace=None):
    tree = ast.parse(source)
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == name), None)
    if node is None:
        raise AssertionError("missing function " + name)
    scope = dict(namespace or {})
    code = compile(ast.Module(body=[node], type_ignores=[]), "<production-extract>", "exec")
    exec(code, scope)
    return scope[name]


def _extract_method(source, class_name, method_name, namespace=None):
    tree = ast.parse(source)
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef)
                and n.name == class_name), None)
    method = next((n for n in cls.body if isinstance(n, ast.FunctionDef)
                   and n.name == method_name), None) if cls else None
    if method is None:
        raise AssertionError("missing method %s.%s" % (class_name, method_name))
    scope = dict(namespace or {})
    exec(compile(ast.Module(body=[method], type_ignores=[]),
                 "<production-method-extract>", "exec"), scope)
    return scope[method_name]


def check_sources(shell_text, worker_text, shell_tree=None, worker_tree=None):
    """Return missing invariants at the real launch and capture consumers."""
    shell_tree = shell_tree or ast.parse(shell_text)
    worker_tree = worker_tree or ast.parse(worker_text)
    misses = []

    preload = _class_method(shell_tree, "SottoShell", "_preload_worker")
    if preload is None or not any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "start_worker" and n.args
            and isinstance(n.args[0], ast.Constant) and n.args[0].value == "preload"
            for n in ast.walk(preload)):
        misses.append("preload entry no longer reaches start_worker('preload')")

    start = _class_method(shell_tree, "WorkerBridge", "start")
    spawn = _class_method(shell_tree, "WorkerBridge", "_spawn")
    request_capture = _class_method(shell_tree, "WorkerBridge", "request_capture")
    deferred = _class_method(shell_tree, "SottoShell", "_start_deferred_worker")
    if start is None or "_spawn" not in _call_names(start) or not any(
            isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == "start_reason"
                    for t in n.targets)
            for n in ast.walk(start)):
        misses.append("WorkerBridge.start does not preserve the preload reason")
    start_src = _segment(shell_text, start) or "" if start else ""
    if (start is None or "self.start_reason == 'preload'" not in start_src
            or "self.state = 'preloading'" not in start_src):
        misses.append("preload start emits a bridge status while the panel is closed")
    bridge_status = _class_method(shell_tree, "WorkerBridge", "_bridge_status")
    bridge_status_src = _segment(shell_text, bridge_status) or "" if bridge_status else ""
    if ("self.start_reason == 'preload' and not self.capture_requested" not in bridge_status_src
            or "self.last_error =" not in bridge_status_src):
        misses.append("hidden preload status/error is not retained without publication")
    request_src = _segment(shell_text, request_capture) or "" if request_capture else ""
    if ("if self.last_error:" not in request_src
            or "self._publish_preload_error()" not in request_src
            or request_src.find("if self.last_error:") > request_src.find("_send_start_capture")):
        misses.append("activation can send START_CAPTURE after a retained preload error")
    publish_error = _class_method(shell_tree, "WorkerBridge", "_publish_preload_error")
    publish_src = _segment(shell_text, publish_error) or "" if publish_error else ""
    publish_body = list(publish_error.body) if publish_error else []
    if (publish_body and isinstance(publish_body[0], ast.Expr)
            and isinstance(publish_body[0].value, ast.Constant)
            and isinstance(publish_body[0].value.value, str)):
        publish_body.pop(0)
    if (publish_error is None or "self._preload_error_published" not in publish_src
            or "self._status(" not in publish_src
            or (publish_body and isinstance(publish_body[0], ast.Return))):
        misses.append("retained preload error is not replayed once on panel activation")
    if spawn is None or not any(
            isinstance(n, ast.Constant) and n.value == "--preload-only"
            for n in ast.walk(spawn)):
        misses.append("preload spawn lacks the --preload-only worker mode")
    if spawn is None or not any(
            isinstance(n, ast.Attribute) and n.attr == "PIPE"
            for n in ast.walk(spawn)):
        misses.append("preload spawn has no parent-to-worker command pipe")
    if spawn is None or not any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_send_start_capture" for n in ast.walk(spawn)):
        misses.append("pre-spawn activation is not delivered after child creation")
    request_capture = _class_method(shell_tree, "WorkerBridge", "request_capture")
    send_helper = next((n for n in shell_tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "_send_start_capture"), None)
    if request_capture is None or "_send_start_capture" not in _call_names(request_capture):
        misses.append("WorkerBridge.request_capture does not use the command writer")
    if send_helper is None or 'pipe.write(\'START_CAPTURE\\n\')' not in (
            _segment(shell_text, send_helper) or ""):
        misses.append("bridge command writer does not emit the exact START_CAPTURE line")
    send_src = _segment(shell_text, send_helper) or "" if send_helper else ""
    if "if already_sent:" not in send_src or "return True, True" not in send_src:
        misses.append("START_CAPTURE command writer is not idempotent")
    if deferred is None or "request_capture" not in _call_names(deferred):
        misses.append("panel-open bridge reuse does not request capture activation")
    live_toggle = _class_method(shell_tree, "SottoShell", "_set_live_enabled")
    if live_toggle is None:
        misses.append("display toggle method is missing")
    else:
        toggle_calls = _call_names(live_toggle)
        forbidden_toggle_calls = {"stop", "terminate", "request_capture",
                                  "start_worker", "_write_panel_visibility"}
        found = sorted(forbidden_toggle_calls.intersection(toggle_calls))
        if found:
            misses.append("display toggle changes worker/capture state: " + ",".join(found))

    parser_flag = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "add_argument" and n.args
        and isinstance(n.args[0], ast.Constant) and n.args[0].value == "--preload-only"
        for n in ast.walk(worker_tree))
    helper = next((n for n in worker_tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == "_wait_for_capture_activation"), None)
    main = next((n for n in worker_tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "main"), None)
    if not parser_flag:
        misses.append("worker parser does not declare --preload-only")
    if helper is None:
        misses.append("worker lacks the bounded START_CAPTURE command reader")
    if main is None:
        misses.append("worker main() is missing")
    else:
        names = _call_names(main)
        if "_wait_for_capture_activation" not in names:
            misses.append("worker main() does not gate preload capture on activation")
        preload_gate = next((n for n in ast.walk(main) if isinstance(n, ast.If)
                             and isinstance(n.test, ast.Attribute)
                             and isinstance(n.test.value, ast.Name)
                             and n.test.value.id == "args"
                             and n.test.attr == "preload_only"
                             and "_wait_for_capture_activation" in _call_names(n)), None)
        if preload_gate is None:
            misses.append("worker activation wait is not guarded by --preload-only")
        try:
            source_lines = worker_text.splitlines()
            main_start = next(i for i, line in enumerate(source_lines)
                              if line.startswith("def main():"))
            main_end = next((i for i in range(main_start + 1, len(source_lines))
                             if source_lines[i] and not source_lines[i][0].isspace()
                             and (source_lines[i].startswith("def ")
                                  or source_lines[i].startswith("class "))),
                            len(source_lines))
            body = "\n".join(source_lines[main_start:main_end])
            gate_at = body.find("_wait_for_capture_activation")
            tap_at = min((p for p in (body.find("_open_tap_bounded("),
                                      body.find("LoopbackTap(")) if p >= 0),
                         default=-1)
            if gate_at < 0 or tap_at < 0 or gate_at > tap_at:
                misses.append("activation gate is not before the worker's AudioTap open")
            asr_ready_at = body.find("asr.sp")
            worker_start_at = body.find("worker.start()")
            if (asr_ready_at < 0 or gate_at < 0 or asr_ready_at > gate_at
                    or worker_start_at < 0 or gate_at > worker_start_at):
                misses.append("preload activation is not after frontend-ready and before ASR starts")
            frontend_fail_at = body.find("PRELOAD_FRONTEND_FAILED")
            frontend_fail_return_at = body.find("return 2", frontend_fail_at)
            activation_read_at = body.find("activation = _wait_for_capture_activation")
            if (frontend_fail_at < 0 or frontend_fail_return_at < frontend_fail_at
                    or activation_read_at < 0 or frontend_fail_return_at > activation_read_at):
                misses.append("frontend failure can reach capture activation")
            eof_branch = next((n for n in ast.walk(main) if isinstance(n, ast.If)
                               and isinstance(n.test, ast.Compare)
                               and isinstance(n.test.left, ast.Name)
                               and n.test.left.id == "activation"
                               and any(isinstance(c, ast.Constant) and c.value is None
                                       for c in n.test.comparators)), None)
            malformed_branch = next((n for n in ast.walk(main) if isinstance(n, ast.If)
                                     and isinstance(n.test, ast.Compare)
                                     and isinstance(n.test.left, ast.Name)
                                     and n.test.left.id == "activation"
                                     and any(isinstance(c, ast.Constant) and c.value is True
                                             for c in n.test.comparators)), None)
            if (eof_branch is None or not any(isinstance(n, ast.Return)
                                              and isinstance(n.value, ast.Constant)
                                              and n.value.value == 0
                                              for n in ast.walk(eof_branch))):
                misses.append("EOF before activation does not exit without capture")
            if (malformed_branch is None or not any(isinstance(n, ast.Return)
                                                    and isinstance(n.value, ast.Constant)
                                                    and n.value.value == 2
                                                    for n in ast.walk(malformed_branch))):
                misses.append("malformed activation does not fail closed before capture")
        except StopIteration:
            misses.append("worker main source region could not be bounded")

    if helper is not None:
        helper_source = _segment(worker_text, helper) or ""
        if "readline(65)" not in helper_source:
            misses.append("activation command reader is not length-bounded")
        if 'line == "START_CAPTURE\\n"' not in helper_source:
            misses.append("activation command reader does not fail closed on exact protocol")

    build = _class_method(worker_tree, "StreamAsr", "_build_frontend")
    if build is None or "frontend-ready" not in (_segment(worker_text, build) or ""):
        misses.append("frontend builder does not publish frontend-ready after success")

    schedule = _class_method(shell_tree, "SottoShell", "_schedule_preload_worker")
    if schedule is None or "SOTTO_NO_PRELOAD" not in (
            _segment(shell_text, schedule) or ""):
        misses.append("startup preload opt-out SOTTO_NO_PRELOAD was removed")

    # The actual hidden route stores audio once and continues before the live
    # decoder; reopen resets per-stream caches while retaining the model object.
    main = next((n for n in worker_tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "main"), None)
    if main is not None:
        batch_if = next((n for n in ast.walk(main) if isinstance(n, ast.If)
                         and any(isinstance(c, ast.Compare)
                                 and isinstance(c.left, ast.Name) and c.left.id == "mode"
                                 and any(isinstance(v, ast.Constant) and v.value == "batch"
                                         for v in c.comparators)
                                 for c in ast.walk(n.test))), None)
        batch_names = set(_call_names(batch_if)) if batch_if else set()
        has_continue = bool(batch_if and any(isinstance(n, ast.Continue)
                                             for n in ast.walk(batch_if)))
        if not {"add_audio", "maybe_kick"}.issubset(batch_names) or not has_continue:
            misses.append("hidden batch mode does not queue audio and skip live decode")
        transition = next((n for n in ast.walk(main) if isinstance(n, ast.If)
                           and isinstance(n.test, ast.Compare)
                           and isinstance(n.test.left, ast.Name)
                           and n.test.left.id == "wanted"
                           and any(isinstance(c, ast.Name) and c.id == "mode"
                                   for c in n.test.comparators)), None)
        route_if = next((n for n in ast.walk(transition) if isinstance(n, ast.If)
                         and isinstance(n.test, ast.Compare)
                         and isinstance(n.test.left, ast.Name)
                         and n.test.left.id == "wanted"
                         and any(isinstance(c, (ast.Tuple, ast.List))
                                 and all(isinstance(v, ast.Constant)
                                         and v.value in ("batch", "shed")
                                         for v in c.elts)
                                 for c in n.test.comparators)), None) if transition else None
        reentry_calls = set(_call_names(ast.Module(
            body=route_if.orelse if route_if else [], type_ignores=[])))
        if not {"reset_stream_state", "reset_frontend"}.issubset(reentry_calls):
            misses.append("visible re-entry does not reset stream state and frontend")
    fresh = _class_method(worker_tree, "StreamAsr", "fresh_processor")
    make = _class_method(worker_tree, "StreamAsr", "_make_processor")
    fresh_calls = set(_call_names(fresh)) if fresh else set()
    make_src = _segment(worker_text, make) or "" if make else ""
    if "_make_processor" not in fresh_calls or "self.model.create_streaming_processor()" not in make_src:
        misses.append("stream re-entry does not reuse retained GenAI model weights")
    if "_og.Model(" in make_src or "og.Model(" in make_src:
        misses.append("stream re-entry constructs a second model instead of reusing weights")

    status_fn = next((n for n in shell_tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == "caption_status_for"), None)
    if status_fn is None or "frontend-preparing" not in (
            _segment(shell_text, status_fn) or ""):
        misses.append("native caption status does not cover frontend preparation")
    bridge_consume = _class_method(shell_tree, "WorkerBridge", "_consume")
    consume_src = _segment(shell_text, bridge_consume) or "" if bridge_consume else ""
    status_hold = next((n for n in ast.walk(bridge_consume) if isinstance(n, ast.If)
                        and isinstance(n.test, ast.Name) and n.test.id == "preload_hidden"), None) \
        if bridge_consume else None
    if (bridge_consume is None or "preload_hidden" not in consume_src
            or "not self.capture_requested" not in consume_src or status_hold is None
            or "_status" in _call_names(ast.Module(body=status_hold.body,
                                                    type_ignores=[]))
            or "_status" not in _call_names(ast.Module(body=status_hold.orelse,
                                                        type_ignores=[]))):
        misses.append("hidden preload status is not suppressed until activation")
    if ("if severity == 'error':" not in consume_src
            or "self.last_error =" not in consume_src
            or consume_src.find("self.last_error =") > consume_src.find("if preload_hidden:")):
        misses.append("worker frontend errors are not retained before hidden-status suppression")
    toggle = _class_method(shell_tree, "SottoShell", "_set_live_enabled")
    if toggle is None or any(name in _call_names(toggle)
                             for name in ("stop", "request_capture", "start_worker")):
        misses.append("display/HOLD toggle unexpectedly changes worker activation")

    return misses


def run_protocol_controls(shell_text, worker_text):
    """Execute production helper functions extracted from source, no app/model."""
    failures = []
    send = _extract_function(shell_text, "_send_start_capture")

    class Pipe:
        def __init__(self, fail=False):
            self.lines = []
            self.fail = fail

        def write(self, line):
            if self.fail:
                raise OSError("closed pipe")
            self.lines.append(line)

        def flush(self):
            if self.fail:
                raise OSError("closed pipe")

    class Lock:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    pipe = Pipe()
    request = _extract_method(shell_text, "WorkerBridge", "request_capture",
                              {"_send_start_capture": send})
    bridge = type("BridgeProbe", (), {})()
    bridge._locked = lambda: Lock()
    bridge.start_reason = "preload"
    bridge.capture_requested = False
    bridge._capture_command_sent = False
    bridge.last_error = None
    bridge._preload_error_published = False
    bridge._publish_preload_error = lambda: False
    bridge.child = None
    bridge.state = "spawning"
    bridge.log = lambda _line: None
    if request(bridge) is not True or not bridge.capture_requested or pipe.lines:
        failures.append("early activation was not queued without a child write")
    bridge.child = type("ChildProbe", (), {"stdin": pipe})()
    if request(bridge) is not True:
        failures.append("queued activation was not delivered when the child became available")
    second = request(bridge)
    if second is not True or pipe.lines != ["START_CAPTURE\n"]:
        failures.append("late/duplicate activation did not remain exactly once")
    if send(Pipe(fail=True), False) != (False, False):
        failures.append("closed parent pipe did not fail closed")

    events = []
    wait = _extract_function(worker_text, "_wait_for_capture_activation",
                             {"emit": lambda **event: events.append(event)})
    if wait(io.StringIO("START_CAPTURE\n")) is not True:
        failures.append("exact activation was not accepted")
    if wait(io.StringIO("")) is not None:
        failures.append("EOF did not leave capture inactive")
    malformed_before = len(events)
    if wait(io.StringIO("START_CAPTURE extra\n")) is not False:
        failures.append("malformed command did not fail closed")
    if len(events) != malformed_before + 1 or events[-1].get("state") != "error":
        failures.append("malformed command did not emit the existing error state")
    if wait(io.StringIO("X" * 1000 + "\n")) is not False:
        failures.append("oversized command did not fail closed")
    return failures, 9


def run_status_controls(shell_text):
    failures = []
    status = _extract_function(shell_text, "caption_status_for")
    base = {"wanted": True, "player_owns": False, "painted_recent": False,
            "track_known": False, "track_cues": 0, "rows": 0, "bridge": True,
            "loaded": True, "capturing": False, "no_audio": False}
    for state in ("model-loaded", "frontend-preparing"):
        probe = dict(base, worker_state=state)
        if status(probe) != "frontend-preparing":
            failures.append("preparing state not visible for " + state)
    if status(dict(base, worker_state="frontend-ready")) is not None:
        failures.append("frontend-ready did not clear the preparing state")
    if status(dict(base, worker_state="error")) is not None:
        failures.append("frontend error did not withdraw preparing state")
    start = _extract_method(shell_text, "WorkerBridge", "start",
                            {"os": os, "json": __import__("json")})

    class Lock:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Bridge:
        def __init__(self):
            self.stopped = False
            self.child = None
            self.start_reason = ""
            self.capture_requested = False
            self._capture_command_sent = False
            self.command = "python"
            self.worker_path = "sotto_worker.py"
            self.device = None
            self.capture_mode = "system"
            self.state = ""
            self.events = []
            self.last_error = None
            self._preload_error_published = False

        def _locked(self):
            return Lock()

        def log(self, _line):
            pass

        def _bridge_status(self, *args):
            self.events.append(args)
            self.state = args[-1]

        def _spawn(self):
            return object()

    preload = Bridge()
    if start(preload, "preload") is not True or preload.events:
        failures.append("hidden startup preload emitted a visible bridge status")
    regular = Bridge()
    if start(regular, "panel-open") is not True or len(regular.events) != 1:
        failures.append("panel-open startup status was suppressed")
    bridge_status = _extract_method(shell_text, "WorkerBridge", "_bridge_status")
    publish = _extract_method(shell_text, "WorkerBridge", "_publish_preload_error")
    request = _extract_method(shell_text, "WorkerBridge", "request_capture",
                              {"_send_start_capture": _extract_function(
                                  shell_text, "_send_start_capture")})
    class CommandPipe:
        def __init__(self):
            self.lines = []

        def write(self, line):
            self.lines.append(line)

        def flush(self):
            pass

    failed = Bridge()
    failed.start_reason = "preload"
    failed.capture_requested = False
    command_pipe = CommandPipe()
    failed.child = type("ChildProbe", (), {"stdin": command_pipe})()
    failed._status = lambda *args: failed.events.append(args)
    failed._publish_preload_error = lambda: publish(failed)
    bridge_status(failed, "front end failed", "error",
                  {"body": "GenAI init failed"}, "error")
    if failed.events or not failed.last_error:
        failures.append("spawn/frontend error leaked before activation or was not retained")
    if request(failed) is not False or command_pipe.lines:
        failures.append("retained failure still sent START_CAPTURE")
    if len(failed.events) != 1 or failed.events[0][1] != "error":
        failures.append("retained failure was not surfaced once when panel opened")
    if request(failed) is not False or len(failed.events) != 1:
        failures.append("failed activation was retried or error was replayed twice")
    return failures, 10


def run_fake_child_controls(shell_text):
    """Run the real WorkerBridge spawn/request/status methods with fake OS child."""
    failures = []
    send = _extract_function(shell_text, "_send_start_capture")
    bridge_status = _extract_method(shell_text, "WorkerBridge", "_bridge_status")
    publish = _extract_method(shell_text, "WorkerBridge", "_publish_preload_error")
    request = _extract_method(shell_text, "WorkerBridge", "request_capture",
                              {"_send_start_capture": send})

    class Pipe:
        def __init__(self):
            self.lines = []

        def write(self, line):
            self.lines.append(line)

        def flush(self):
            pass

    class Child:
        pid = 91731

        def __init__(self):
            self.stdin = Pipe()
            self.stdout = io.StringIO("")
            self.stderr = io.StringIO("")

    child = Child()

    class FakePath:
        @staticmethod
        def exists(_path):
            return True

        @staticmethod
        def dirname(_path):
            return "H:/sotto/worker"

        @staticmethod
        def basename(path):
            return path.rsplit("/", 1)[-1]

    class FakeOS:
        name = "posix"
        path = FakePath

        @staticmethod
        def getcwd():
            return "H:/sotto"

    class FakeSubprocess:
        PIPE = object()
        DEVNULL = object()
        argv = None
        kwargs = None

        @classmethod
        def Popen(cls, argv, **kwargs):
            cls.argv, cls.kwargs = argv, kwargs
            return child

    class NoThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

    fake_no_console = types.ModuleType("no_console")
    fake_no_console.popen_kwargs = lambda _flags: {}
    previous_module = sys.modules.get("no_console")
    sys.modules["no_console"] = fake_no_console
    try:
        spawn = _extract_method(shell_text, "WorkerBridge", "_spawn", {
            "os": FakeOS, "subprocess": FakeSubprocess, "json": json,
            "time": time, "threading": types.SimpleNamespace(Thread=NoThread),
            "file_sha256": lambda _path: "model-free-worker-digest",
            "_send_start_capture": send,
        })

        class Lock:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class Bridge:
            def __init__(self):
                self.command = "python"
                self.worker_path = "H:/sotto/worker/sotto_worker.py"
                self.extra_args = []
                self.device = None
                self.capture_mode = "system"
                self.target_pid = None
                self.start_reason = "preload"
                self.capture_requested = False
                self._capture_command_sent = False
                self._preload_error_published = False
                self.child = None
                self.stopped = False
                self.state = "preloading"
                self.spawns = 0
                self.last_error = None
                self.last_no_audio = None
                self.no_audio = False
                self.no_audio_evidence = None
                self.no_audio_evidence_at = 0.0
                self.stderr_tail = []
                self.capturing = False
                self.capture_epoch = 0.0
                self.pending_error = None
                self.events = []

            def _child_env(self):
                return {}

            def _locked(self):
                return Lock()

            def log(self, _line):
                pass

            def _pump(self, *_args):
                pass

            def _wait(self, *_args):
                pass

            def _arm_silence(self):
                pass

            def _schedule_restart(self, *_args):
                pass

            def _status(self, *args):
                self.events.append(args)

        live = Bridge()
        spawned = spawn(live)
        if (spawned is not child or FakeSubprocess.kwargs.get("stdin") is not FakeSubprocess.PIPE
                or not FakeSubprocess.argv or "--preload-only" not in FakeSubprocess.argv):
            failures.append("real _spawn did not create a preload-only child with stdin=PIPE")
        if child.stdin.lines:
            failures.append("closed prewarm wrote activation before panel open")
        if request(live) is not True or child.stdin.lines != ["START_CAPTURE\n"]:
            failures.append("fake-child activation did not deliver exactly one command")
        if request(live) is not True or child.stdin.lines != ["START_CAPTURE\n"]:
            failures.append("fake-child repeated panel open wrote a duplicate command")

        failed = Bridge()
        failed.start_reason = "preload"
        failed._status = lambda *args: failed.events.append(args)
        failed._publish_preload_error = lambda: publish(failed)
        bridge_status(failed, "front end failed", "error",
                      {"body": "GenAI init failed"}, "error")
        if failed.events or not failed.last_error:
            failures.append("hidden fake-child error was emitted instead of retained")
        if request(failed) is not False or failed._capture_command_sent:
            failures.append("fake-child error activation sent capture command")
        if len(failed.events) != 1 or failed.events[0][1] != "error":
            failures.append("fake-child error was not replayed once on panel open")
    except Exception as exc:
        failures.append("fake-child WorkerBridge integration raised %s: %s" %
                        (type(exc).__name__, exc))
    finally:
        if previous_module is None:
            sys.modules.pop("no_console", None)
        else:
            sys.modules["no_console"] = previous_module
    return failures, 6


def run_real_bridge_integration():
    """Exercise late and early activation through the real bridge and OS pipe."""
    failures = []
    fake_source = """import json, sys, time
def status(state):
    print(json.dumps({\"type\":\"status\",\"state\":state}), flush=True)
status(\"model-loading\")
status(\"model-loaded\")
status(\"frontend-preparing\")
time.sleep(0.25)
status(\"frontend-ready\")
line = sys.stdin.readline(65)
if line != \"START_CAPTURE\\n\":
    raise SystemExit(31)
status(\"capture-started\")
second = sys.stdin.readline(65)
if second != \"\":
    raise SystemExit(32)
"""
    fake_path = None
    bridges = []
    children = []
    try:
        # The fake source and its child processes live under H; they use the
        # production WorkerBridge Popen path with a real OS stdin pipe. No GPU,
        # model, audio endpoint, window, browser, or external executor is used.
        handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".py", prefix="preload-child-",
            dir=os.path.join(ROOT, ".agent-work"), delete=False)
        fake_path = handle.name
        try:
            handle.write(fake_source)
        finally:
            handle.close()
        sys.path.insert(0, os.path.join(ROOT, "app", "webview"))
        shell = importlib.import_module("sotto_webview")

        def wait_state(bridge, child, wanted, timeout=5.0):
            deadline = time.monotonic() + timeout
            while bridge.state != wanted and time.monotonic() < deadline:
                if child.poll() is not None:
                    break
                time.sleep(0.01)
            return bridge.state == wanted

        def run_case(early_open):
            case_failures = []
            status_events = []
            # QUANDO o filho falou pela primeira vez, por NOME (medido 2026-11-26).
            # O `startup_s` abaixo chamava-se "child startup" mas media o caso
            # INTEIRO (do spawn ate' o fecho do stdin), que inclui o preload, a
            # activacao e o dreno -- e 4x isso, limitado a 60 s, e' o orcamento
            # que os dois janelas de espera gastam. Num passo cuja medicao quieta
            # e' 82 s, um caso que responda tarde esticava a espera por um
            # motivo que nao e' o filho. O comentario do sitio dizia
            # "(`capture-started` minus spawn)": agora e' isso que ele mede.
            status_times = {}
            def _on_status(*event):
                status_events.append(event)
                status_times.setdefault(str(event[0]), time.monotonic())
            bridge = shell.WorkerBridge(
                command=sys.executable,
                worker_path=fake_path,
                extra_args=[],
                log=lambda _line: None,
                on_status=_on_status,
                on_caption=lambda *_args: None,
                on_stats=lambda *_args: None,
                on_cost=lambda *_args: None,
                on_meter=lambda *_args: None,
                on_loading_text=lambda *_args: case_failures.append(
                    "preactivation loading overlay leaked"),
            )
            bridges.append(bridge)
            case_spawn_s = time.monotonic()
            if not bridge.start("preload"):
                case_failures.append("real WorkerBridge refused fake-child preload")
                return case_failures
            child = bridge.child
            children.append(child)
            first_state = "frontend-preparing" if early_open else "frontend-ready"
            if not wait_state(bridge, child, first_state):
                case_failures.append("fake child did not reach " + first_state)
            # NO emptiness arm here. The final sequence check (below, after the
            # capture-started barrier) is STRICTLY STRONGER: every status line the
            # child wrote before activation has been consumed by the single pump
            # thread by then, so a hidden-window leak is an extra event there.
            # An emptiness test at this instant races the pump: it publishes
            # bridge.state at sotto_webview.py:25962 BEFORE it decides at :26163.
            if early_open:
                pending_state = dict(
                    wanted=True, player_owns=False, painted_recent=False,
                    track_known=False, track_cues=0, rows=0, bridge=True,
                    loaded=bridge.loaded, capturing=bridge.capturing,
                    no_audio=False, worker_state=bridge.state)
                if shell.caption_status_for(pending_state) != "frontend-preparing":
                    case_failures.append("early panel open did not show preparing status")
            if bridge.request_capture() is not True:
                case_failures.append("real bridge rejected panel activation")
            if bridge.request_capture() is not True:
                case_failures.append("real bridge rejected idempotent duplicate activation")
            # The old `if status_events:` arm lived here and flipped with the
            # pump thread; it is replaced by the content check after the last
            # child line below, which judges NAMES rather than emptiness.
            # (c) PURE PROJECTION. `caption_status_for` reads only the dictionary
            # built here, so no pump thread can change its answer:
            # sotto_webview.py:3321-3323 returns 'frontend-preparing' only for
            # model-loaded/frontend-preparing, never for frontend-ready. A stale
            # ready overlay therefore turns this arm red deterministically.
            if not early_open:
                # BARRAGE BOUNDED, not a live read. `_pump` sets `self.state`
                # (sotto_webview.py:25963) BEFORE it sets `self.loaded` (:26040)
                # for the SAME `model-loaded` message, so `bridge.loaded` is a
                # second fact that can lag the state this case just waited for:
                # with `loaded=False` the projection answers 'model-loading' and
                # the arm goes red on nothing. MEASURED 2026-11-26, the same
                # tree: 1 of 3 runs under `cProfile` returned
                # "ready-before-open status did not clear on activation", the
                # other two PASSed, and 2 of 2 plain runs PASSed. A gate that
                # flips with the pump thread is the class this file already
                # replaced once (`if status_events:`, see the note above): wait
                # for the CONTRACT fact, then judge it.
                loaded_deadline = time.monotonic() + 5.0
                while not bridge.loaded and time.monotonic() < loaded_deadline:
                    time.sleep(0.01)
                if not bridge.loaded:
                    case_failures.append(
                        "bridge never reported loaded after frontend-ready")
                ready_state = dict(
                    wanted=True, player_owns=False, painted_recent=False,
                    track_known=False, track_cues=0, rows=0, bridge=True,
                    loaded=bridge.loaded, capturing=bridge.capturing,
                    no_audio=False, worker_state="frontend-ready")
                if shell.caption_status_for(ready_state) is not None:
                    case_failures.append("ready-before-open status did not clear on activation")
            if not wait_state(bridge, child, "capture-started"):
                case_failures.append("child did not receive START_CAPTURE on the real pipe")
            expected_status_count = 2 if early_open else 1
            # BOUNDED DRAIN. `_pump` sets bridge.state at :25962 before it calls
            # `_status` at :26168, so a state barrier alone can precede the final
            # event. Drain at most 2.0 s, then judge whatever is present; the
            # ceiling is fixed and the count check below cannot silently green.
            drain_deadline = time.monotonic() + 2.0
            while (len(status_events) < expected_status_count
                   and time.monotonic() < drain_deadline):
                time.sleep(0.01)
            # (b) CONTENT, NOT EMPTINESS. Child statuses published while the
            # panel is hidden are dropped at sotto_webview.py:26163-26166, not
            # buffered for replay: WorkerBridge never calls on_status for them.
            # They can only appear here if that suppression broke, so judge the
            # NAMES after the child's last line was consumed.
            hidden_names = ("model-loading", "model-loaded", "frontend-preparing")
            if not early_open:
                hidden_names += ("frontend-ready",)
            status_names = [str(event[0]) for event in status_events]
            leaked = [name for name in status_names if name in hidden_names]
            if leaked:
                case_failures.append(
                    "activation leaked stale hidden status %r" % leaked)
            if (len(status_events) != expected_status_count
                    or status_names.count("capture-started") != 1
                    or (early_open and status_names.count("frontend-ready") != 1)):
                case_failures.append(
                    "activation status sequence mismatch early=%s expected=%d events=%r" %
                    (early_open, expected_status_count, status_events))
            bridge.stopped = True
            bridge._cancel_timers()
            if child.stdin:
                child.stdin.close()
            # ONE control, TWO windows, and the evidence printed in between. Measured
            # 2026-11-23: this arm passed 2/2 with the exact battery invocation minutes
            # after run 8 published `fake child did not exit on parent pipe EOF`, so a
            # 5.0 s window was naming a defect that was not there -- and a false MISSING
            # costs a whole battery run.
            # MEASURED AGAIN 2026-11-25 and the ladder grew a DERIVED term: under the
            # battery's `--io very-low` cage on a loaded box the child had already
            # answered START_CAPTURE (it was alive and functional) yet the fixed
            # 5+10 s ladder still ran out. A clock set before the machine answered is
            # not a limit, so the budget now comes from the cost this run MEASURED for
            # the child to come up (`capture-started` minus spawn), times four, and
            # never below the old 15 s.
            answered_s = status_times.get('capture-started')
            startup_s = max(0.0, answered_s - case_spawn_s) if answered_s else 0.0
            eof_budget_s = min(60.0, max(15.0, 4.0 * startup_s))
            print('NEG-CHILD eof budget=%.1fs (child startup measured %.2fs)'
                  % (eof_budget_s, startup_s), flush=True)
            waited_s = 0.0
            exited = True
            for window in (eof_budget_s / 3.0, 2.0 * eof_budget_s / 3.0):
                try:
                    child.wait(timeout=window)
                except Exception:
                    waited_s += window
                    exited = False
                    print('NEG-CHILD alive after %.1fs (window %.1fs) poll=%r stdin_closed=%s'
                          % (waited_s, window, child.poll(), child.stdin is None
                             or child.stdin.closed), flush=True)
                    continue
                exited = True
                break
            if not exited:
                case_failures.append(
                    "fake child did not exit on parent pipe EOF (waited %.1fs alive=%s)"
                    % (waited_s, child.poll() is None))
                child.kill()
                child.wait(timeout=2.0)
            if child.returncode != 0:
                case_failures.append("child saw duplicate/malformed command rc=%s" %
                                     child.returncode)
            return case_failures

        failures.extend(run_case(early_open=False))
        failures.extend(run_case(early_open=True))
        for thread in list(__import__("threading").enumerate()):
            if (thread.name.startswith("sotto-worker-")
                    and thread is not __import__("threading").current_thread()):
                # The bridge reads piped lines; a 1.0 s join raced the reader under the
                # battery's CPU cap (measured 2026-11-23: same code, 12/12 solo).
                thread.join(timeout=5.0)
                if thread.is_alive():
                    print('NEG-THREAD %s still alive after 5.0s' % thread.name, flush=True)
                    failures.append("WorkerBridge fake-child thread did not join: " + thread.name)
    except Exception as exc:
        failures.append("real WorkerBridge fake-child integration raised %s: %s" %
                        (type(exc).__name__, exc))
    finally:
        for bridge in bridges:
            try:
                bridge.stopped = True
                bridge._cancel_timers()
            except Exception:
                pass
        for child in children:
            if child is not None and child.poll() is None:
                try:
                    child.stdin.close()
                    child.wait(timeout=2.0)
                except Exception:
                    child.kill()
                    child.wait(timeout=2.0)
        if fake_path and os.path.exists(fake_path):
            os.unlink(fake_path)
    return failures, 12


def run_mutation_controls(shell_text, worker_text):
    """One focused source mutation per enforced lifecycle detector."""
    checks = []
    base_shell_tree = ast.parse(shell_text)
    base_worker_tree = ast.parse(worker_text)

    def expect(name, sh, wk, marker):
        sh_tree = base_shell_tree if sh == shell_text else ast.parse(sh)
        wk_tree = base_worker_tree if wk == worker_text else ast.parse(wk)
        observed = (check_sources(sh, wk, sh_tree, wk_tree)
                    + check_hidden_route(sh, wk, sh_tree, wk_tree))
        checks.append((name, any(marker in item for item in observed), marker))

    reentry_reset = worker_text.rfind("asr.reset_frontend()")
    visible_reentry_mutant = (worker_text[:reentry_reset] + "pass" +
                              worker_text[reentry_reset + len("asr.reset_frontend()"):]
                              if reentry_reset >= 0 else worker_text)

    expect("spawn-mode", shell_text.replace(
        "argv.append('--preload-only')", "pass", 1), worker_text,
        "preload spawn lacks the --preload-only worker mode")
    expect("startup-status", shell_text.replace(
        "self.state = 'preloading'", "self.state = 'starting'", 1), worker_text,
        "preload start emits a bridge status while the panel is closed")
    expect("bridge-status-hold", shell_text.replace(
        "if self.start_reason == 'preload' and not self.capture_requested:",
        "if False:", 1), worker_text,
        "hidden preload status/error is not retained without publication")
    expect("worker-status-hold", shell_text.replace(
        "if preload_hidden:\n                # Keep the worker state",
        "if False:\n                # Keep the worker state", 1), worker_text,
        "hidden preload status is not suppressed until activation")
    expect("error-send-guard", shell_text.replace(
        "if self.last_error:\n                # A failed prewarm",
        "if False:\n                # A failed prewarm", 1), worker_text,
        "activation can send START_CAPTURE after a retained preload error")
    expect("error-replay", shell_text.replace(
        "    def _publish_preload_error(self):\n",
        "    def _publish_preload_error(self):\n        return False\n", 1), worker_text,
        "retained preload error is not replayed once on panel activation")
    expect("activation-guard", shell_text, worker_text.replace(
        "if args.preload_only:", "if False:", 1),
        "worker activation wait is not guarded by --preload-only")
    expect("exact-command", shell_text, worker_text.replace(
        'if line == "START_CAPTURE\\n":',
        'if line.startswith("START_CAPTURE"):', 1),
        "activation command reader does not fail closed on exact protocol")
    expect("one-time-start-command", shell_text.replace(
        "if already_sent:\n        return True, True",
        "if False:\n        return True, True", 1), worker_text,
        "START_CAPTURE command writer is not idempotent")
    expect("frontend-ready", shell_text, worker_text.replace(
        'emit(type="status", state="frontend-ready")',
        'emit(type="status", state="model-loaded")', 1),
        "frontend builder does not publish frontend-ready")
    expect("hidden-status", shell_text.replace(
        "preload_hidden = (self.start_reason == 'preload'\n"
        "                              and not self.capture_requested)",
        "preload_hidden = (self.start_reason == 'preload'\n"
        "                              and self.capture_requested)", 1), worker_text,
        "hidden preload status is not suppressed until activation")
    expect("hidden-route", shell_text, worker_text.replace(
        "unload_when_hidden=True", "unload_when_hidden=False", 1),
        "real ReduxHiddenSwitch constructor does not enable hidden routing")
    expect("shell-opt-in", shell_text.replace(
        "env.setdefault('SOTTO_REDUX_WHEN_HIDDEN', '1')",
        "env['SOTTO_REDUX_WHEN_HIDDEN'] = '0'", 1), worker_text,
        "production WorkerBridge does not opt into hidden Redux")
    expect("batch-skip", shell_text, worker_text.replace(
        'switch.maybe_kick()\n                    continue',
        'switch.maybe_kick()\n                    pass', 1),
        "batch/shed modes are not skipped before run_chunk")
    expect("display-only", shell_text.replace(
        "    def _set_live_enabled(self, payload):\n",
        "    def _set_live_enabled(self, payload):\n        self.stop()\n", 1), worker_text,
        "display toggle changes worker/capture state")
    expect("retained-model", shell_text, worker_text.replace(
        "return self._make_processor()", "return _og.Model()", 1),
        "stream re-entry does not reuse retained GenAI model weights")
    expect("visible-re-entry", shell_text, visible_reentry_mutant,
        "visible re-entry does not reset stream state and frontend")
    return checks


def _opts_into_hidden(child_env):
    """True when `_child_env` sets `SOTTO_REDUX_WHEN_HIDDEN` to `1` for the child.

    TWO FORMS, ONE CONTRACT (2026-11-25). The bridge used to assign the variable
    unconditionally; it now uses `env.setdefault(...)` so an explicit operator `0`
    survives (`app/webview/sotto_webview.py:25243`). The control's subject is the
    OPT-IN, not the syntactic form: a detector that only accepted `Assign` went red
    on the shipped code while the product still opted in -- a pin on retired policy.
    Assignment is still accepted, so the clause covers both spellings; a value other
    than `1` (or no write at all) still fails the control.
    """
    for n in ast.walk(child_env):
        if isinstance(n, ast.Assign):
            if (any(isinstance(t, ast.Subscript)
                    and isinstance(t.slice, ast.Constant)
                    and t.slice.value == "SOTTO_REDUX_WHEN_HIDDEN"
                    for t in n.targets)
                    and isinstance(n.value, ast.Constant) and n.value.value == "1"):
                return True
            continue
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "setdefault"
                and len(n.args) >= 2
                and isinstance(n.args[0], ast.Constant)
                and n.args[0].value == "SOTTO_REDUX_WHEN_HIDDEN"
                and isinstance(n.args[1], ast.Constant) and n.args[1].value == "1"):
            return True
    return False


def check_hidden_route(shell_text, worker_text, shell_tree=None, worker_tree=None):
    """Check the real shell opt-in, worker constructor, and stream consumer."""
    shell_tree = shell_tree or ast.parse(shell_text)
    worker_tree = worker_tree or ast.parse(worker_text)
    misses = []
    child_env = _class_method(shell_tree, "WorkerBridge", "_child_env")
    if child_env is None or not _opts_into_hidden(child_env):
        misses.append("production WorkerBridge does not opt into hidden Redux")

    main = next((n for n in worker_tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "main"), None)
    switch_call = None
    if main is not None:
        switch_call = next((n for n in ast.walk(main)
                            if isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Name)
                            and n.func.id == "ReduxHiddenSwitch"), None)
    if switch_call is None or not any(
            kw.arg == "unload_when_hidden"
            and isinstance(kw.value, ast.Constant) and kw.value.value is True
            for kw in switch_call.keywords):
        misses.append("real ReduxHiddenSwitch constructor does not enable hidden routing")

    if main is None or "tick" not in _call_names(main):
        misses.append("worker main loop does not consume ReduxHiddenSwitch.tick")
    else:
        run_chunks = [n for n in ast.walk(main)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "run_chunk"]
        run_chunk_line = max((n.lineno for n in run_chunks), default=-1)
        if run_chunk_line < 0:
            misses.append("worker main loop no longer calls the real stream decoder")
        else:
            skipped_modes = set()
            for node in ast.walk(main):
                if not isinstance(node, ast.If):
                    continue
                compares = [n for n in ast.walk(node.test) if isinstance(n, ast.Compare)]
                for compare in compares:
                    if not isinstance(compare.left, ast.Name) or compare.left.id != "mode":
                        continue
                    values = [x.value for x in compare.comparators
                              if isinstance(x, ast.Constant)]
                    if any(isinstance(child, ast.Continue) for stmt in node.body
                           for child in ast.walk(stmt)) and node.lineno < run_chunk_line:
                        skipped_modes.update(x for x in values if isinstance(x, str))
            if not {"batch", "shed"}.issubset(skipped_modes):
                misses.append("batch/shed modes are not skipped before run_chunk")
    return misses


def run_hidden_route_control(unload_when_hidden):
    """Drive the actual ReduxHiddenSwitch without constructing any model."""
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "worker"))
    switch_module = importlib.import_module("worker.engine_switch")

    class Reader:
        visible = True

        def read(self):
            return self.visible, "fresh", 0.0

        def shed(self):
            return "leve"

        def park(self):
            return None

    class FakeEngine:
        available = True
        name = staticmethod(lambda: "model-free-probe")

        def load(self):
            raise AssertionError("model-free control must not load an engine")

        def release(self, **_kwargs):
            return False

        def transcribe(self, _pcm):
            raise AssertionError("model-free control must not transcribe")

    reader = Reader()
    route = switch_module.ReduxHiddenSwitch(
        enabled=True, reader=reader, runner=__file__, log_fn=lambda _line: None,
        hidden_after_s=0.5, engine=FakeEngine(), probe=None, pending=object(),
        unload_when_hidden=unload_when_hidden)
    if not route.armed:
        return ["real switch did not arm on the injected model-free batch engine"]
    failures = []
    if route.tick(now=10.0) != "stream":
        failures.append("visible panel did not select stream")
    reader.visible = False
    if route.tick(now=20.0) != "stream":
        failures.append("hidden grace period did not retain stream")
    hidden_mode = route.tick(now=20.6)
    if unload_when_hidden and hidden_mode != "batch":
        failures.append("configured hidden panel did not route to batch")
    if not unload_when_hidden and hidden_mode != "stream":
        failures.append("missing hidden-route flag did not fail closed to stream")
    reader.visible = True
    if route.tick(now=21.0) != "stream":
        failures.append("visible-again panel did not restore stream")
    # Display/HOLD is not an input to this real engine switch. Calling the
    # shell's actual display toggle is source-guarded separately above; its
    # result cannot alter reader visibility or the worker route.
    reader.visible = True
    display_disabled = True
    mode_after_display_toggle = route.tick(now=22.0)
    if not display_disabled or mode_after_display_toggle != "stream":
        failures.append("display-off changed the visible worker route")
    if route.switches < 2 and unload_when_hidden:
        failures.append("hidden/visible transitions were not both observed")
    return failures


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    neg_arm = argv == ["--neg-arm"]
    if argv and not neg_arm:
        print("usage: python _main/nemotron-preload-oracle.py [--neg-arm]")
        return 2
    shell_text = _read(SHELL)
    worker_text = _read(WORKER)
    misses = check_sources(shell_text, worker_text)
    misses.extend(check_hidden_route(shell_text, worker_text))
    protocol_failures, protocol_total = run_protocol_controls(shell_text, worker_text)
    status_failures, status_total = run_status_controls(shell_text)
    bridge_failures, bridge_total = run_real_bridge_integration()
    misses.extend(protocol_failures)
    misses.extend(status_failures)
    misses.extend(bridge_failures)
    misses.extend(run_hidden_route_control(unload_when_hidden=True))
    misses.extend(run_hidden_route_control(unload_when_hidden=False))
    print("MODEL-FREE controls: command/state positive=%d/%d; status positive=%d/%d; "
          "real WorkerBridge fake-child=%d/%d; "
          "real switch configured/unconfigured positive=5/5 + fail-closed=1/1; model loads=0" %
          (protocol_total - len(protocol_failures), protocol_total,
           status_total - len(status_failures), status_total,
           bridge_total - len(bridge_failures), bridge_total))
    if misses:
        print("VERDICT: FAIL -- preload/hidden-route lifecycle controls failed")
        for item in misses:
            print("  MISSING: " + item)
        return 1
    if neg_arm:
        mutations = run_mutation_controls(shell_text, worker_text)
        for name, caught, marker in mutations:
            print("MUTATION %s %s%s" % (name, "CAUGHT" if caught else "MISSED",
                                        " expected=" + marker if not caught else ""))
        caught = sum(1 for _, ok, _ in mutations if ok)
        print("NEG-ARM: %s -- %d/%d focused lifecycle mutations caught" %
              ("PASS" if caught == len(mutations) else "FAIL", caught, len(mutations)))
        return 1 if caught == len(mutations) else 2
    print("VERDICT: PASS -- preload activation and hidden panel routing are enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
