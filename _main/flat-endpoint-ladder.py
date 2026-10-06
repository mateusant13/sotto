"""Run the REAL worker with the main thread's COM apartment chosen by the CALLER.

Why this exists: the ladder's rung (a) -- WASAPI loopback of the default render
endpoint -- reaches `wasapi_loopback.default_render_endpoint()`, whose COM gate
calls `CoInitializeEx(NULL, COINIT_MULTITHREADED)`. What that call RETURNS on the
ladder thread depends on who touched COM first on that thread, and the worker is
not the only one:

  * untouched thread      -> S_OK, then S_FALSE on the SECOND call  (because the
                            pre-fix gate never released its reference)
  * thread already STA    -> RPC_E_CHANGED_MODE on EVERY call

`device_candidates()` imports sounddevice and calls `sd.query_devices()` BEFORE
rung (a) is probed, and on this machine that leaves the main thread in an STA --
so the defect branch (S_FALSE) is never reached in a natural worker run here.
Measured with `_main/flat-endpoint-oracle.py`, arm `real-two-calls-one-thread`.

This driver pins the branch instead of hoping for it: `mta` initialises the main
thread MTA BEFORE sounddevice is imported, so the ladder thread reports S_FALSE
(the branch the measured defect lived in, `_main/_live_owner3.log:61`), and
`natural` leaves it alone (the branch that happens to work here today).

Nothing is mocked: it starts the real worker through its real `main()`.

    py -3 _main/flat-endpoint-ladder.py mta     --max-seconds 45 --tap-window 5
    py -3 _main/flat-endpoint-ladder.py natural --max-seconds 45 --tap-window 5
"""
import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

mode = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("mta", "natural") else "mta"

if mode == "mta":
    hr = ctypes.WinDLL("ole32", use_last_error=True).CoInitializeEx(None, 0x0)
    sys.stderr.write(
        "driver: CoInitializeEx(MTA) on the main thread -> 0x%08X "
        "(defect branch: the gate sees S_FALSE on the second call)\n" % (hr & 0xFFFFFFFF)
    )
else:
    sys.stderr.write(
        "driver: main thread left alone "
        "(routing branch: whatever initialised COM first decides the apartment)\n"
    )
sys.stderr.flush()

sys.path.insert(0, os.path.join(ROOT, "worker"))
sys.argv = ["sotto_worker.py"] + sys.argv[2:]

import sotto_worker  # noqa: E402

sys.exit(sotto_worker.main())
