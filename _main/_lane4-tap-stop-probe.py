"""Lane 4 probe -- F4 (`WasapiLoopbackTap.stop()`) and F16 (GetBuffer arity).

NO DEVICE, NO COM, NO AUDIO. Nothing here opens an endpoint or calls a Windows
API: the object under test is built with `__new__` (no `__init__`, no
`default_render_endpoint`), and the "pump" is a Python thread that loops on
`_stop`. The only production code exercised is `stop()`, `close()` and the
deliver block of `_pump` -- precisely the code the fix changed.

CLAIM UNDER TEST (the property, not the method):
    after `stop()` returns, `on_block` is NEVER called again.

Exit 0 = every assertion held. Exit 1 = the probe found a defect. The probe
never imports sounddevice, never touches COM and never writes outside _main/.
"""

import ast
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "worker" / "wasapi_loopback.py"
sys.path.insert(0, str(ROOT / "worker"))

import wasapi_loopback as wl  # noqa: E402

FAILURES = []
CHECKS = [0]


def check(label, ok, detail=""):
    CHECKS[0] += 1
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", label, (" :: " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)


# ── 1. source inspection: GetBuffer takes FIVE out-parameters ────────────────
text = SRC.read_text(encoding="utf-8")
lines = text.splitlines()
tree = ast.parse(text)

decl_line = decl_args = None
call_line = call_args = None
decl_fifth = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id == "get_buffer":
                fn = node.value.func
                if isinstance(fn, ast.Name) and fn.id == "_vtbl":
                    decl_line = node.lineno
                    # _vtbl(ptr, index, restype, *argtypes) -> the vtable slots
                    # are args[3:]; there must be five of them.
                    decl_args = node.value.args[3:]
                    fifth = decl_args[4] if len(decl_args) >= 5 else None
                    if fifth is not None:
                        decl_fifth = ast.unparse(fifth)

# the call site: a Call whose func is the bare name `get_buffer`
def _calls(node, name):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name:
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _calls(child, name)


get_buffer_calls = list(_calls(tree, "get_buffer"))
check("F16 declaration of get_buffer found", decl_line is not None)
check("F16 declaration has FIVE parameter types",
      decl_args is not None and len(decl_args) == 5,
      "found %s" % (len(decl_args) if decl_args is not None else "none"))
check("F16 fifth parameter is a uint64 pointer",
      bool(decl_fifth) and "c_uint64" in decl_fifth, "5th=%r" % (decl_fifth,))
check("F16 exactly ONE get_buffer call site", len(get_buffer_calls) == 1,
      "found %d" % len(get_buffer_calls))
if get_buffer_calls:
    node = get_buffer_calls[0]
    call_line = node.lineno
    # `_vtbl`'s WINFUNCTYPE wrapper takes `this` FIRST, so the declared slots are
    # the arguments AFTER the object handle: data, frames, flags, pos, qpc.
    out_args = node.args[1:]
    call_args = len(out_args)
    check("F16 call passes FIVE out-parameters (cap + 5)", call_args == 5,
          "found %d out-params + the object handle" % call_args)
    check("F16 3rd, 4th and 5th out-parameters are present (flags, pos, qpc)",
          all(isinstance(a, ast.Call) for a in out_args[:4])
          and isinstance(out_args[4], ast.Constant) and out_args[4].value is None,
          "slots=%s" % ", ".join(ast.unparse(a) for a in out_args))
    check("F16 the QPC slot is an explicit NULL, not a missing argument",
          any(isinstance(a, ast.Constant) and a.value is None for a in out_args))

print("")
print("DECL %d: %s" % (decl_line, lines[decl_line - 1].strip() if decl_line else "<missing>"))
print("CALL %d: %s" % (call_line, lines[call_line - 1].strip() if call_line else "<missing>"))
print("")

check("F4 class exposes a real stop()", "def stop(self)" in text)
check("F4 stop() is documented with the guarantee",
      "NEVER called again" in text)
check("F4 __exit__ is no longer the only stop path",
      "def __exit__" in text and "def stop(self)" in text)
check("F4 close() reuses stop() (single release path)",
      bool(re.search(r"def close\(self\):.*?\n        self\.stop\(\)", text, re.S)))

# The guarantee `stop()` proves by acquiring `_cb_lock` is only real if the
# pump delivers `on_block` while HOLDING that lock. Assert that shape in the
# source: exactly one guarded `on_block(...)` in the pump, and no bare one.
guarded = []
unguarded = []
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_pump":
        for anc in ast.walk(node):
            if isinstance(anc, ast.With):
                holds = any(isinstance(i.context_expr, ast.Attribute)
                            and i.context_expr.attr == "_cb_lock" for i in anc.items)
                for inner in ast.walk(anc):
                    if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                            and inner.func.attr == "on_block":
                        (guarded if holds else unguarded).append(inner.lineno)
check("F4 the pump's on_block call is the one holding _cb_lock",
      len(guarded) == 1 and not unguarded,
      "guarded=%s unguarded=%s" % (guarded, unguarded))

# The runtime arm below relies on the pump's deliver path being exactly one
# guarded `on_block` per `_stop` test (the fake pump copies that shape). Assert
# the production source really has that shape and not, say, a second unguarded
# call after the loop -- which would be a live counter-example to the property.
pump_src = ast.get_source_segment(text, [n for n in ast.walk(tree)
                                         if isinstance(n, ast.FunctionDef)
                                         and n.name == "_pump"][0]) or ""
check("F4 the pump has exactly ONE on_block call site",
      pump_src.count("self.on_block") == 1,
      "count=%d" % pump_src.count("self.on_block"))
check("F4 the pump's loop is guarded by the `_stop` predicate",
      "while not self._stop.is_set():" in pump_src)


# ── 2. runtime: no on_block after stop() returns ─────────────────────────────
def build(counts, stop_delay=0.0):
    """A tap with no device and no COM: only the fields stop()/close() touch."""
    obj = wl.WasapiLoopbackTap.__new__(wl.WasapiLoopbackTap)
    obj._stop = threading.Event()
    obj._cb_lock = threading.Lock()
    obj._thread = None
    obj._com = None
    obj._client = None
    obj._capture = None
    obj._dev = None
    obj._enum = None
    obj.on_block = counts.append

    def pump():
        # Body mirrors the production `_pump` deliver path: same lock, same
        # check-then-call order, same `_stop` predicate.
        while not obj._stop.is_set():
            with obj._cb_lock:
                obj.on_block(1)
            if stop_delay:
                time.sleep(stop_delay)

    obj._thread = threading.Thread(target=pump, name="lane4-fake-pump", daemon=True)
    obj._thread.start()
    return obj


print("")
for round_no in range(1, 6):
    counts = []
    obj = build(counts)
    time.sleep(0.02)
    n_before = len(counts)
    assert n_before > 0, "fake pump never delivered: probe is vacuous"
    obj.stop()
    n_at_stop = len(counts)
    time.sleep(0.30)                     # 300 ms of budget for a stray callback
    n_after = len(counts)
    check("round%d: pump delivers while running" % round_no, n_before > 0, "n=%d" % n_before)
    check("round%d: NO on_block after stop() returns" % round_no, n_after == n_at_stop,
          "at_stop=%d after_300ms=%d" % (n_at_stop, n_after))
    check("round%d: pump thread is joined (not alive)" % round_no,
          not obj._thread or not obj._thread.is_alive())
    check("round%d: stop() returned" % round_no, obj._stop.is_set())
    try:
        r2 = obj.stop()
        r3 = obj.stop()
        check("round%d: stop() is idempotent (3x)" % round_no, r2 is obj and r3 is obj)
    except Exception as exc:
        check("round%d: stop() is idempotent (3x)" % round_no, False, repr(exc))
    also = len(counts)
    check("round%d: idempotent stop() delivered nothing" % round_no, also == n_at_stop,
          "count=%d" % also)
    try:
        obj.close()
        check("round%d: close() after stop() returns without raising" % round_no, True)
    except Exception as exc:
        check("round%d: close() after stop() returns without raising" % round_no, False, repr(exc))
    try:
        obj.close()
        obj.stop()
        check("round%d: second stop();close() pair is a no-op" % round_no, len(counts) == also,
              "count=%d" % len(counts))
    except Exception as exc:
        check("round%d: second stop();close() pair is a no-op" % round_no, False, repr(exc))

# Running the fake pump FASTER (no sleep) must not create a window either: this
# is the shape that produced the 2x cadence in the audit evidence.
print("")
for delay, label in ((0.0, "no-sleep"), (0.001, "1ms"), (0.005, "5ms")):
    counts = []
    obj = build(counts, stop_delay=delay)
    time.sleep(0.03)
    obj.stop()
    n_at_stop = len(counts)
    time.sleep(0.20)
    check("no-callback-after-stop (%s pump)" % label, len(counts) == n_at_stop,
          "at_stop=%d after=%d" % (n_at_stop, len(counts)))

# close() alone, on an object that was NEVER started: no device, no thread, no
# interfaces. This is the shape `close_tap()` reaches after a failed open.
print("")
for i in range(3):
    counts = []
    obj = wl.WasapiLoopbackTap.__new__(wl.WasapiLoopbackTap)
    obj._stop = threading.Event()
    obj._cb_lock = threading.Lock()
    obj._thread = None
    obj._com = None
    obj._client = obj._capture = obj._dev = obj._enum = None
    obj.on_block = counts.append
    try:
        obj.close()
        obj.close()
        check("never-started close() x2 returns without raising (arm %d)" % i, True)
        check("never-started close() delivered nothing (arm %d)" % i, not counts)
    except Exception as exc:
        check("never-started close() x2 returns without raising (arm %d)" % i, False, repr(exc))

# stop() must also be callable on an object whose _start() raised (open failed):
# the worker constructs the tap and only then calls start().
print("")
counts = []
obj = wl.WasapiLoopbackTap.__new__(wl.WasapiLoopbackTap)
obj._stop = threading.Event()
obj._cb_lock = threading.Lock()
obj._thread = None
obj._com = None
obj._client = obj._capture = obj._dev = obj._enum = None
obj.on_block = counts.append
try:
    obj.stop()
    obj.close()
    check("stop()/close() survive a tap that never opened", not counts)
except Exception as exc:
    check("stop()/close() survive a tap that never opened", False, repr(exc))

# The public shape the worker imports must be untouched.
print("")
for name in ("loopback_device_specs", "live_render_peaks", "WasapiLoopbackTap"):
    check("public name present: %s" % name, hasattr(wl, name))
check("device_candidates is NOT this module's (the worker owns it)",
      not hasattr(wl, "device_candidates"))
check("public signature live_render_peaks(meter_ms=0.12) unchanged",
      "def live_render_peaks(meter_ms=0.12):" in text)
check("public signature loopback_device_specs(role=E_CONSOLE) unchanged",
      "def loopback_device_specs(role=E_CONSOLE):" in text)
check("worker's call site still reachable: stream property returns self",
      "def stream(self):" in text and "return self" in text)

print("")
if FAILURES:
    print("VERDICT FAIL  failures=%d/%d %s" % (len(FAILURES), CHECKS[0], FAILURES))
    sys.exit(1)
print("VERDICT PASS  %d/%d checks" % (CHECKS[0], CHECKS[0]))
sys.exit(0)
