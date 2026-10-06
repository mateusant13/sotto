"""Probe: the WASAPI loopback capture RING, in ms, from the endpoint the tap opens.

Why this exists: `_main/delivery-rate-oracle.py --mutant pump` reverts
`wasapi_loopback.py` to the pre-fix poll (`period = max(0.005, block_ms/1000/4)` =
25 ms) and on 2026-10-06 the ORACLE measures duty ~1.00 with it, i.e. the defect
does NOT reproduce here. The audit (`docs/audit/audio-path.md` §3.1) measured
`GetBufferSize` = 1056 frames = 22 ms, which is why a 25 ms poll dropped ~18 %.
This prints the same two numbers NOW, so "the mutant is green" is attributed to a
measured ring instead of a guess.

Prints one JSON line: {"ring_frames":N,"ring_ms":X,"dev_period_default_ms":X,
"dev_period_min_ms":X,"rate":R,"poll_ms_at_block100":X}
No window: imported and run under pythonw, nothing spawned.
"""

import ctypes
import json
import os
import sys
from ctypes import POINTER, wintypes

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "worker"))
import wasapi_loopback as w  # noqa: E402


def main():
    opened = {"n": 0}

    def on_block(_block):
        opened["n"] += 1

    tap = w.WasapiLoopbackTap(on_block, block_ms=100)
    tap.start()                                    # opens client + capture + pump
    try:
        client = tap._client
        # IAudioClient vtable: 3=Initialize 4=GetBufferSize 8=GetMixFormat
        #                       9=GetDevicePeriod 10=Start 14=GetService
        get_buffer_size = w._vtbl(client, 4, w.HRESULT, POINTER(wintypes.DWORD))
        get_device_period = w._vtbl(
            client, 9, w.HRESULT, POINTER(ctypes.c_int64), POINTER(ctypes.c_int64)
        )
        frames = wintypes.DWORD(0)
        hr = get_buffer_size(client, ctypes.byref(frames))
        default_p, min_p = ctypes.c_int64(0), ctypes.c_int64(0)
        hr2 = get_device_period(client, ctypes.byref(default_p), ctypes.byref(min_p))
        rate = tap.rate
        block_ms = 100
        poll_ms = max(1.0, block_ms / 20.0)
        print(json.dumps({
            "hr_getbuffersize": hr,
            "hr_getdeviceperiod": hr2,
            "ring_frames": frames.value,
            "rate": rate,
            "ring_ms": round(1000.0 * frames.value / rate, 2) if rate else None,
            "dev_period_default_ms": round(default_p.value / 10000.0, 2),
            "dev_period_min_ms": round(min_p.value / 10000.0, 2),
            "poll_ms_at_block100_fixed": poll_ms,
            "poll_ms_at_block100_prefix": 25.0,
        }))
    finally:
        tap.close()


if __name__ == "__main__":
    main()
