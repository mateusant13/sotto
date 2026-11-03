"""The after-arm with the load's priority window DISABLED, for the boot A/B.

    python worker/_probe/no-background.py --selftest --stats-interval 0

`PROCESS_MODE_BACKGROUND_BEGIN` (CPU idle, I/O very low, memory lowest) exists
because the owner's desktop froze while the worker loaded 1.2 GB
(`worker/sotto_worker.py`, `_enter_load_background_mode`). It also makes the load
itself 2-3x slower, which is half of "65 s to model-loaded". This file does not
change the product: it patches the two entry points in memory so the SAME code
can be measured with and without the throttle, and the receipt can quote both.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.dirname(HERE)
if WORKER not in sys.path:
    sys.path.insert(0, WORKER)

import sotto_worker as w  # noqa: E402

w._enter_load_background_mode = lambda: "no-background(probe)"
w._leave_load_background_mode = lambda entered: entered

if __name__ == "__main__":
    sys.exit(w.main())
