"""ADVERSARIAL REVIEW — attack 3: is `stop()`'s GUARANTEE absolute?

`worker/wasapi_loopback.py:758-761` claims: "once this returns, `on_block` is
NEVER called again. The pump is asked to stop (`_stop`), joined, and the callback
lock is taken afterwards, so a callback that was already in flight has returned
and the joined thread cannot start another one."

The primitives, in the code's own order (no COM, no device, no pipe):
  `_pump`  : `while not self._stop.is_set():` (:956)  ... then, with NO second
             `_stop` test in between, `with self._cb_lock: self.on_block(...)`
             (:1017-1018)
  `stop()` : `_stop.set()` (:775) -> `join(timeout=2.0)` (:782) -> `with
             self._cb_lock: pass` (:793)

So the barrier only proves "whoever already HELD the lock is done". A pump thread
that is PAST the loop test but not yet at the lock — the case the join timeout
(:778-781, "a safety valve for a wedged COM call") exists for — will take the
lock after `stop()` returned and call `on_block` anyway.

This reproduces that ORDER with the same primitives. It is the SHAPE, faithful to
the two code paths above; it is NOT the real `_pump` (that needs a device).

    cmd /c "python _main\\_review-tapstop.py > _main\\_review-tapstop.log 2>&1"
"""

import os
import re
import threading
import time

# ── FIRST: IS THE MODELLED ORDER STILL THE SHIPPED ONE? ──────────────────────
# This probe models the pump by hand (a real `_pump` needs a device), so it can
# only speak about the file if it CHECKS the file. The fix landed on 2026-10-07:
# the delivery now re-tests `_stop` INSIDE `_cb_lock`, which closes the wedge this
# probe demonstrates. Without this check the probe would keep printing REFUTED
# against a fixed revision — a stale landmine, and the same "a gate that cannot
# say PASS" class it was written to expose.
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, os.pardir, 'worker', 'wasapi_loopback.py'))
try:
    with open(SRC, encoding='utf-8') as fh:
        _src = fh.read()
except OSError as exc:
    print(f'SETUP ERROR: cannot read {SRC}: {exc!r}')
    raise SystemExit(2)

_guard = re.search(
    r'with self\._cb_lock:\s*\n\s*(?:#[^\n]*\n\s*)*if self\._stop\.is_set\(\):',
    _src)
GUARD_IN_SOURCE = bool(_guard)

stop_evt = threading.Event()
cb_lock = threading.Lock()
fired = []
WEDGE_S = 3.0          # > stop()'s 2.0 s join: the case the timeout exists for


def pump():
    # (1) loop test, (2) work OUTSIDE the lock (a wedged GetBuffer), (3) the lock
    while not stop_evt.is_set():
        time.sleep(WEDGE_S)
        with cb_lock:
            # THE FIX, modelled: the shipped pump now re-tests before delivering.
            if GUARD_IN_SOURCE and stop_evt.is_set():
                return
            fired.append(('on_block', time.monotonic()))
        return


t = threading.Thread(target=pump, daemon=True)
t.start()
time.sleep(0.3)                      # the pump is past its loop test

t0 = time.monotonic()
stop_evt.set()                       # the code: :775
t.join(timeout=2.0)                  # the code: :782
timed_out = t.is_alive()
with cb_lock:                        # the code: :793  (the barrier)
    pass
stop_returned = time.monotonic()
print(f'join timed out (pump kept, as :779-781 describes): {timed_out}')
print(f'stop() returned at +{stop_returned - t0:.2f}s')

t.join()                             # let the pump finish so it can be counted
after = [f for f in fired if f[1] > stop_returned]
print(f'on_block calls total                        : {len(fired)}')
print(f'on_block calls AFTER stop() returned        : {len(after)}')
print(f'the extra call landed +{after[0][1] - stop_returned:.2f}s after stop()'
      if after else 'no call after stop() (the guarantee held in this run)')
print(f'guard present in the LIVE file ({os.path.relpath(SRC, HERE)}): {GUARD_IN_SOURCE}')
print('')
if GUARD_IN_SOURCE and not after:
    print('VERDICT: UPHELD — the shipped pump re-tests `_stop` inside `_cb_lock`, '
          'so the wedge this probe models no longer delivers after `stop()` '
          'returns. This probe is now a REGRESSION CHECK for that guard: delete '
          'the re-test from `worker/wasapi_loopback.py` and the run below flips '
          'back to REFUTED.')
elif GUARD_IN_SOURCE and after:
    print('VERDICT: INCONSISTENT — the guard is in the source AND a callback still '
          'landed after stop(); read the demo order against the shipped lines '
          'before believing either.')
elif after:
    print('VERDICT: REFUTED as stated — the guarantee holds only when the pump '
          'is inside the lock or gone; a >2 s wedge outside it delivers ONE more '
          'callback after stop() returns, which is the block the tap ledger then '
          'attributes to the NEXT candidate.')
    print('FIX (one line): re-test `_stop` INSIDE `_cb_lock` before calling, i.e. '
          '`with self._cb_lock:\n    if self._stop.is_set(): break\n'
          '    self.on_block(...)`')
else:
    print('VERDICT: held in this run')
