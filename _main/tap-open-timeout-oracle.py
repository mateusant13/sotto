"""ORACLE: OPENING AND CLOSING SOTTO MUST NOT FREEZE THE OWNER'S PC.

Owner, 2026-10-20, verbatim:
  *"abrir ou fechar o sotto, principalemnte fechar, trava pra caralho meu pc.
  arruma."*

WHAT THE OWNER'S OWN LOG SAYS (`H:\sotto\_main\webview-run.log`, his session
of 2026-10-19 20:49-20:50):

    20:49:17.334  BRIDGE_SPAWNED pid=47804
    20:50:25.229  BRIDGE_LOAD_MS ms=67969 worker_load_s=8.75
    20:50:50.070  EXTERNAL_CAPTIONS_RELEASED reason=stopped
    20:50:50.070  EXTERNAL_CAPTIONS_WORKER_RESUMED reason=player-stopped
    20:50:52.379  SHELL_EXIT rc=0 reason=tray-quit

TWO CAUSES, AND BOTH ARE MEASURED HERE:

  A. THE CLOSE: at 20:50:50.070, 0.65 s before the shell exited, the caption
     reader's release path brought the worker BACK. `os._exit` does not kill
     a child process, so that worker was an ORPHAN: after the app closed it
     loaded 1.2 GB of model and ran the capture ladder.

  B. THE OPEN: 68 s from the spawn to the model, of which only 8.75 s is the
     MODEL. The other ~59 s is the CAPTURE LADDER, and the ladder opens the
     candidates IN A LINE. MEASURED 2026-10-20 with
     `_main/probe-capture-open.py --timeout 3` (12 candidates on this box):
     opening "Headset (soundcore Space Q45)" in **MME** and in **Windows
     WASAPI** **BLOCKS** -- it does not come back in 3.0 s and it raises
     NOTHING, so the ladder had no way to know it was waiting. The opens
     that work take 0.19-0.22 s.

THE FIXES UNDER TEST
  * `worker/sotto_worker.py::_open_tap_bounded` -- the open has a deadline
    (`TAP_OPEN_TIMEOUT_S`), a blocked open is rotated past, and the
    ABANDONED tap closes itself when it finally comes back.
  * `app/webview/sotto_webview.py::on_external_captions_released` -- the
    shell does not bring the worker back while it is dying.

ARMS (7)
  w1  an open that works            -> the tap, no error, and it was fast
  w2  an open that BLOCKS           -> a timeout error, and the CALL RETURNED
  w3  an open that raises           -> the error, not a timeout
  w4  an open that blocks, then returns -> the abandoned tap CLOSES itself
  w5  the deadline is the configured one
  s1  the shell is ALIVE            -> the worker comes back (the path works)
  s2  the shell is DYING            -> the worker does NOT come back

MUTANTS (4), each one must turn an arm RED
  m1  the open has no deadline        -> w2, w4
  m2  the abandoned tap is not closed -> w4
  m3  a blocked open is called a success -> w2
  m4  the shell brings the worker back while dying -> s2

It launches nothing: no app, no worker, no audio device, no network. The
worker's own module is imported (its import is cheap -- it does not load the
model) and the tap factory is replaced by a fake.

    python _main\\tap-open-timeout-oracle.py
    python _main\\tap-open-timeout-oracle.py --neg-arm
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import threading
import time
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(REPO, "worker", "sotto_worker.py")
SHELL = os.path.join(REPO, "app", "webview", "sotto_webview.py")

if os.path.join(REPO, "worker") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "worker"))
if os.path.join(REPO, "app", "webview") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "app", "webview"))

#: THE HARD CAP OF EVERY CALL IN THIS GATE. A gate that can hang is worse
#: than a gate that is wrong: the mutant arm m1 removes the deadline, and
#: without this cap the GATE would hang instead of reporting RED.
CALL_CAP_S = 8.0
#: The deadline the product ships.
SHIPPED_TIMEOUT_S = 4.0


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── the fake taps ───────────────────────────────────────────────────────────

class FakeStream(object):
    def __init__(self, owner):
        self.owner = owner

    def start(self):
        self.owner.started += 1
        if self.owner.block_s:
            # THE BLOCK. It is what a driver does when the endpoint is a
            # Bluetooth hands-free device that is not answering.
            time.sleep(self.owner.block_s)
        if self.owner.raise_on_open:
            raise RuntimeError("the endpoint refused")

    def stop(self):
        pass

    def close(self):
        self.owner.closed += 1


class FakeTap(object):
    def __init__(self, owner):
        self.owner = owner
        self.source = ""
        self.stream = FakeStream(owner)

    def stop(self):
        self.owner.closed += 1


class FakeDevice(dict):
    """A candidate row, shaped like the ones the ladder passes."""


def make_device():
    return {"name": "Headset (soundcore Space Q45)", "api": "Windows WASAPI",
            "index": 0, "hostapi": None}


class TapOwner(object):
    """What the fake tap factory hands back, and what it records."""

    def __init__(self, block_s=0.0, raise_on_open=False):
        self.block_s = block_s
        self.raise_on_open = raise_on_open
        self.started = 0
        self.closed = 0
        self.tap = FakeTap(self)

    def close(self, tap):
        """The closer the worker is handed. The worker's own `close_tap` is
        a NESTED function inside `main()`, so the helper takes it as an
        argument -- and this is the gate's stand-in for it."""
        self.closed += 1


def install_fake_tap(mod, owner):
    """Replace the worker's tap factory with the fake, and return the undo."""
    saved = mod.LoopbackTap

    def fake_loopback_tap(device, on_block, want_rate=None, block_ms=100):
        return owner.tap

    mod.LoopbackTap = fake_loopback_tap
    return saved


def restore_fake_tap(mod, saved):
    mod.LoopbackTap = saved


def call_bounded(fn, *args, **kwargs):
    """Call `fn`, and never wait longer than `CALL_CAP_S` for it.

    Returns `(ok, value)`. `ok` is False when the call did not come back --
    which is the RED the mutant arm m1 must produce.
    """
    box = {}

    def _work():
        try:
            box["value"] = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    th = threading.Thread(target=_work, name="gate-call", daemon=True)
    th.start()
    th.join(CALL_CAP_S)
    if th.is_alive():
        return False, None
    if "error" in box:
        return True, box["error"]
    return True, box.get("value")


# ── the worker arms ─────────────────────────────────────────────────────────

def arm_w1_works(mod):
    """An open that works: the tap comes back, no error, and it was fast."""
    owner = TapOwner()
    saved = install_fake_tap(mod, owner)
    try:
        started = time.monotonic()
        ok, value = call_bounded(mod._open_tap_bounded, make_device(),
                                 lambda *a: None, block_ms=100,
                                 close=owner.close)
        took = time.monotonic() - started
    finally:
        restore_fake_tap(mod, saved)
    if not ok:
        return False, "a working open did not come back inside %.1fs" % CALL_CAP_S
    tap, error = value
    if tap is None:
        return False, "a working open returned no tap"
    if error is not None:
        return False, "a working open returned an error: %r" % (error,)
    if took > 1.0:
        return False, "a working open took %.2fs" % took
    return True, "in %.3fs" % took


def arm_w2_blocks(mod):
    """An open that BLOCKS: a timeout, and the CALL RETURNED."""
    owner = TapOwner(block_s=30.0)
    saved = install_fake_tap(mod, owner)
    try:
        started = time.monotonic()
        ok, value = call_bounded(mod._open_tap_bounded, make_device(),
                                 lambda *a: None, block_ms=100,
                                 close=owner.close)
        took = time.monotonic() - started
    finally:
        restore_fake_tap(mod, saved)
    if not ok:
        return False, ("a BLOCKED open held the call for more than %.1fs -- the "
                       "ladder would wait with it" % CALL_CAP_S)
    tap, error = value
    if tap is not None:
        return False, "a blocked open returned a tap"
    if error is None:
        return False, "a blocked open was reported as a SUCCESS"
    if not isinstance(error, TimeoutError):
        return False, "a blocked open raised %r, not a timeout" % (error,)
    if took > SHIPPED_TIMEOUT_S + 2.0:
        return False, "the timeout took %.2fs (deadline %.1fs)" % (took,
                                                                  SHIPPED_TIMEOUT_S)
    return True, "gave up after %.2fs with %r" % (took, type(error).__name__)


def arm_w3_raises(mod):
    """An open that RAISES: the error comes back, and it is not a timeout."""
    owner = TapOwner(raise_on_open=True)
    saved = install_fake_tap(mod, owner)
    try:
        ok, value = call_bounded(mod._open_tap_bounded, make_device(),
                                 lambda *a: None, block_ms=100,
                                 close=owner.close)
    finally:
        restore_fake_tap(mod, saved)
    if not ok:
        return False, "the call did not come back"
    tap, error = value
    if tap is not None:
        return False, "a failed open returned a tap"
    if error is None:
        return False, "a failed open reported no error"
    if isinstance(error, TimeoutError):
        return False, "a failed open was reported as a TIMEOUT"
    return True, "%s: %s" % (type(error).__name__, error)


def arm_w4_abandoned_closes(mod):
    """An open that blocks and then returns: the tap CLOSES ITSELF."""
    owner = TapOwner(block_s=1.2)
    saved = install_fake_tap(mod, owner)
    try:
        ok, value = call_bounded(mod._open_tap_bounded, make_device(),
                                 lambda *a: None, block_ms=100,
                                 timeout_s=0.3, close=owner.close)
    finally:
        restore_fake_tap(mod, saved)
    if not ok:
        return False, "the call did not come back"
    tap, error = value
    if tap is not None:
        return False, "a blocked open returned a tap"
    # The abandoned thread is still inside its 1.2 s sleep. Give it time to
    # come back and close what it opened.
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline and owner.closed == 0:
        time.sleep(0.05)
    if owner.closed == 0:
        return False, ("the abandoned tap was NOT closed -- it would keep the "
                       "endpoint for the rest of the run")
    return True, "closed=%d" % owner.closed


def arm_w5_deadline(mod):
    """The deadline is the configured one, and it can be overridden."""
    value = getattr(mod, "TAP_OPEN_TIMEOUT_S", None)
    if not isinstance(value, (int, float)):
        return False, "TAP_OPEN_TIMEOUT_S is %r" % (value,)
    if value <= 0:
        return False, "the deadline is %r -- an open with no deadline is the bug" % value
    if value > 10.0:
        return False, "the deadline is %.1fs, too long to keep the ladder moving" % value
    # IT IS OVERRIDABLE: the gate needs a short deadline for w4.
    import inspect
    sig = inspect.signature(mod._open_tap_bounded)
    if "timeout_s" not in sig.parameters:
        return False, "the deadline cannot be overridden"
    return True, "%.1fs" % value


# ── the shell arms ──────────────────────────────────────────────────────────

class FakeShell(object):
    """The shell, with the REAL `on_external_captions_released` bound."""

    def __init__(self, mod, exiting):
        self.exiting = threading.Event()
        if exiting:
            self.exiting.set()
        self.visible = True
        self._caption_window_shown = False
        self._external_parked = True
        self._paused = False
        self._last_external_resume = 0.0
        self.resumes = []
        self.on_external_captions_released = types.MethodType(
            mod.SottoShell.on_external_captions_released, self)

    def start_worker(self, reason):
        self.resumes.append(reason)
        return True


def arm_s1_alive(mod):
    """The shell is ALIVE: the worker comes back. The path must still work."""
    shell = FakeShell(mod, exiting=False)
    shell.on_external_captions_released()
    if not shell.resumes:
        return False, "the worker did NOT come back on a live shell"
    return True, "reason=%s" % shell.resumes[0]


def arm_s2_dying(mod):
    """The shell is DYING: the worker must NOT come back."""
    shell = FakeShell(mod, exiting=True)
    shell.on_external_captions_released()
    if shell.resumes:
        return False, ("the worker came back while the shell was dying: %r -- "
                       "that worker is an ORPHAN (os._exit does not kill a "
                       "child process)" % (shell.resumes,))
    return True, "no worker was started"


# ── the arms ────────────────────────────────────────────────────────────────

def build_arms():
    """(name, which module it judges, the function, what it proves)."""
    return [
        ("w1", "w", arm_w1_works,
         "an open that works: the tap, no error, fast"),
        ("w2", "w", arm_w2_blocks,
         "an open that BLOCKS: a timeout, and the call RETURNED"),
        ("w3", "w", arm_w3_raises,
         "an open that raises: the error, not a timeout"),
        ("w4", "w", arm_w4_abandoned_closes,
         "an open that blocks and then returns: the tap CLOSES ITSELF"),
        ("w5", "w", arm_w5_deadline,
         "the deadline is the configured one"),
        ("s1", "s", arm_s1_alive,
         "the shell is ALIVE: the worker comes back"),
        ("s2", "s", arm_s2_dying,
         "the shell is DYING: the worker does NOT come back"),
    ]


# ── the mutants ─────────────────────────────────────────────────────────────

MUTANTS = (
    ("m1", "the open has no deadline",
     WORKER, "    th.join(limit)", "    th.join()"),
    ("m2", "the abandoned tap is not closed",
     WORKER, "            try:\n                closer(tap)",
     "            try:\n                pass"),
    ("m3", "a blocked open is called a success",
     WORKER, "        return None, TimeoutError(\"the open blocked for more than %.2fs\" % limit)",
     "        return None, None"),
    ("m4", "the shell brings the worker back while dying",
     SHELL, "        if self.exiting.is_set():\n"
            "            log('EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting')\n"
            "            return False\n", ""),
)


def build_mutants():
    """A copy of each product file per mutant, in a temp dir.

    THE FILES ARE READ WITH UNIVERSAL NEWLINES. The shell is CRLF and the
    worker is CRLF too, and an anchor written with "\\n" would never match
    a "\\r\\n" in the file -- the mutant would then be reported as a
    missing anchor and the gate would abort instead of testing it. The
    MUTANT COPY is written with LF, which Python does not care about.
    """
    tmpdir = tempfile.mkdtemp(prefix="freeze-oracle-")
    out = []
    for name, _why, target, old, new in MUTANTS:
        with io.open(target, "r", encoding="utf-8") as fh:
            source = fh.read()
        n = source.count(old)
        if n != 1:
            print("ABORT: the mutant %s anchor occurs %d times in %s."
                  % (name, n, os.path.basename(target)))
            return None
        path = os.path.join(tmpdir, "%s_%s.py" % (
            os.path.basename(target).replace(".py", ""), name))
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(source.replace(old, new))
        if target == WORKER:
            mod = load_module(path, "sotto_worker_mutant_%s" % name)
        else:
            mod = load_module(path, "sotto_webview_mutant_%s" % name)
        out.append((name, mod))
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    neg_only = "--neg-arm" in argv

    for path in (WORKER, SHELL):
        if not os.path.exists(path):
            print("ABORT: %s is missing." % path)
            return 2

    mod_worker = load_module(WORKER, "sotto_worker_live")
    mod_shell = load_module(SHELL, "sotto_webview_live")
    arms = build_arms()

    def run_arm(fn, which, worker_mod, shell_mod):
        return fn(worker_mod if which == "w" else shell_mod)

    failures = 0
    if not neg_only:
        print("=== the LIVE product")
        for name, which, fn, why in arms:
            try:
                ok, detail = run_arm(fn, which, mod_worker, mod_shell)
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, "raised %r" % (exc,)
            if ok:
                print("  ok   %-4s %s -- %s" % (name, why, detail))
            else:
                failures += 1
                print("  RED  %-4s %s -- %s" % (name, why, detail))

    print("")
    print("=== the MUTANTS: each one must turn an arm RED")
    mutants = build_mutants()
    if mutants is None:
        return 2
    by_name = dict(mutants)
    caught = 0
    for name, why, target, _old, _new in MUTANTS:
        mod = by_name[name]
        # The mutant replaces ONE file; the other stays the live one.
        worker_mod = mod if target == WORKER else mod_worker
        shell_mod = mod if target == SHELL else mod_shell
        reds = []
        for arm_name, which, fn, _why2 in arms:
            try:
                ok, detail = run_arm(fn, which, worker_mod, shell_mod)
            except Exception as exc:  # noqa: BLE001
                reds.append("%s (raised %r)" % (arm_name, exc))
                continue
            if not ok:
                reds.append(arm_name)
        if reds:
            caught += 1
            print("  ok   %-4s caught by %s -- %s" % (name, ",".join(reds), why))
        else:
            failures += 1
            print("  RED  %-4s NOT CAUGHT -- %s" % (name, why))

    if neg_only:
        print("")
        print("VERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por desenho: o braco "
              "negativo REPROVA de proposito)"
              % ("PASS" if caught == len(MUTANTS) else "FAIL", caught, len(MUTANTS)))
        return 1

    print("")
    ok = not failures
    print("VERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", len(arms) - failures, len(arms),
             caught, len(MUTANTS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
