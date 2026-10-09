"""Lane SottoLiveAudioSweep -- INSTRUMENT 1: what is carrying audio on this box RIGHT NOW.

Two questions, both answered WITHOUT opening any stream:

  (a) every ACTIVE RENDER endpoint, with its own `IAudioMeterInformation` peak
      sampled over a window. The worker's tap is a LOOPBACK of a render endpoint,
      so this names what the owner's worker is reading.
  (b) every ACTIVE CAPTURE endpoint, with the same meter. Rung (b) of the worker's
      ladder opens a CAPTURE endpoint by name (`CABLE Output ...`), and a second
      CAPTURE endpoint on the same audio (VoiceMeeter's own bus outputs) is the
      free way in while the worker holds its one.

`worker/wasapi_loopback.py` is the repo's own module and is IMPORTED, not copied:
its `_meter_peak` / `_make_enumerator` / `_mix_spec` / `_release` are the measured
COM plumbing, and a second hand-written copy is a second thing to drift.

No stream is opened, so nothing needs closing and no endpoint can be left held.
Cadence: meter_ms per endpoint, one pass. Written to stdout as one JSON object.
"""

import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(os.path.dirname(HERE), "worker")
sys.path.insert(0, WORKER)

import wasapi_loopback as W  # noqa: E402

E_CAPTURE = 1


def _enum_flow(flow, meter_ms):
    """Every ACTIVE endpoint of `flow` (0=render, 1=capture), each with meter peak."""
    com = W._com_init()
    out = []
    try:
        ole32 = W._ole32()
        enum = W._make_enumerator(ole32)
        try:
            coll = ctypes.c_void_p()
            hr = W._vtbl(enum, 3, W.HRESULT, wintypes.DWORD, wintypes.DWORD,
                         ctypes.POINTER(ctypes.c_void_p))(
                enum, flow, W.DEVICE_STATE_ACTIVE, ctypes.byref(coll))
            if hr != 0 or not coll:
                return {"error": "EnumAudioEndpoints(flow=%d) failed: %s" % (flow, W._fmt(hr)),
                        "endpoints": []}
            try:
                count = wintypes.UINT(0)
                W._vtbl(coll, 3, W.HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))
                for i in range(count.value):
                    dev = ctypes.c_void_p()
                    if W._vtbl(coll, 4, W.HRESULT, wintypes.UINT,
                               ctypes.POINTER(ctypes.c_void_p))(coll, i, ctypes.byref(dev)) != 0 or not dev:
                        continue
                    try:
                        row = {"index_in_flow": i}
                        try:
                            ep = W._mix_spec(dev, ole32)
                            row.update({
                                "name": ep.name,
                                "endpoint_id": ep.endpoint_id,
                                "rate": ep.rate,
                                "channels": ep.channels,
                                "bits": ep.bits,
                                "format_tag": ep.format_tag,
                            })
                        except Exception as exc:
                            row["mix_spec_error"] = "%s: %s" % (type(exc).__name__, exc)
                        row["meter_peak"] = W._meter_peak(dev, meter_ms)
                        out.append(row)
                    finally:
                        W._release(dev)
            finally:
                W._release(coll)
        finally:
            W._release(enum)
    finally:
        if com == W.COM_REF_TAKEN:
            W._com_uninit()
    out.sort(key=lambda r: -(r.get("meter_peak") or 0.0))
    return {"error": None, "endpoints": out}


def main():
    meter_ms = float(sys.argv[1]) if len(sys.argv) > 1 else 0.4
    t0 = time.time()
    doc = {
        "instrument": "live-audio-sweep-endpoints.py",
        "cadence": "one IAudioMeterInformation pass per endpoint, meter_ms=%.2f" % meter_ms,
        "opened_no_stream": True,
        "render": _enum_flow(0, meter_ms),
        "capture": _enum_flow(1, meter_ms),
        "wall_s": None,
    }
    doc["wall_s"] = round(time.time() - t0, 3)
    print(json.dumps(doc, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
