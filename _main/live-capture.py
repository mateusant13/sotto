"""Continuous audio capture of the OWNER'S LIVE, for building a test fixture.

Owner, 2026-10-06: "na live que ta tocando agora, baixa o audio constantemente.
quando tiver uma frase ou duas ou tres coerentes com a transcricao normal
funcionando, ai da replay nesse audio pra usar de teste pra fazer o sotto
funcionar direito."

Writes 30 s WAV segments, rolling: keeps the last `--keep` and deletes older ones,
so the window containing a good sentence is ALWAYS on disk.

Endpoint choice: the tap delivers FLOAT32 MONO at the endpoint's MIX rate
(48 kHz here); we convert to int16 for the WAV. The endpoint with the HIGHEST
live meter is chosen by default, because that is the one actually rendering --
MEASURED 2026-10-06: `CABLE Input` metered 0.044 while all five others read 0.0,
and that is where the owner's live audio comes out.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "worker"))

import numpy as np  # noqa: E402
import wasapi_loopback as wl  # noqa: E402

SEG_S = 30.0


def pick_endpoint(needle: str | None):
    eps = wl.list_render_endpoints()
    if not eps:
        raise SystemExit("no render endpoints")
    if needle:
        for e in eps:
            if needle.lower() in (e.get("name") or "").lower():
                return e
        raise SystemExit("no endpoint matches %r; have: %s"
                         % (needle, [e.get("name") for e in eps]))
    live = sorted(eps, key=lambda e: float(e.get("meter_peak") or 0.0), reverse=True)
    return live[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"G:/sotto-ref/live")
    ap.add_argument("--device", default=None, help="substring of the endpoint name")
    ap.add_argument("--keep", type=int, default=60, help="segments to retain")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    ep = pick_endpoint(a.device)
    print("ENDPOINT %s  meter=%s  rate=%s  ch=%s"
          % (ep.get("name"), ep.get("meter_peak"), ep.get("rate"), ep.get("channels")), flush=True)

    buf = bytearray()

    def on_block(block, *_rest):
        # float32 MONO at the mix rate -> int16 LE
        x = np.asarray(block, dtype=np.float32).reshape(-1)
        np.clip(x, -1.0, 1.0, out=x)
        buf.extend((x * 32767.0).astype("<i2").tobytes())

    tap = wl.WasapiLoopbackTap(on_block, block_ms=100, endpoint_id=ep.get("endpoint_id"))
    rate = int(tap.rate)
    tap.stream.start()
    print("CAPTURE-STARTED rate=%d block=%d" % (rate, tap.block), flush=True)

    need = int(rate * 2 * SEG_S)
    written, n, t0 = [], 0, time.time()
    try:
        while True:
            time.sleep(0.25)
            if len(buf) < need:
                continue
            chunk = bytes(buf[:need])
            del buf[:need]
            n += 1
            path = os.path.join(a.out, "seg-%05d.wav" % n)
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(chunk)
            written.append(path)
            arr = np.frombuffer(chunk, dtype="<i2")
            peak = int(np.abs(arr).max()) if arr.size else 0
            rms = float(np.sqrt(np.mean((arr.astype(np.float32) / 32768.0) ** 2))) if arr.size else 0.0
            print("SEG %s peak16=%d rms=%.5f keep=%d"
                  % (os.path.basename(path), peak, rms, len(written)), flush=True)
            while len(written) > a.keep:
                old = written.pop(0)
                try:
                    os.remove(old)
                except OSError:
                    pass
    finally:
        try:
            tap.stream.stop()
            tap.stream.close()
        except Exception:
            pass
        print("CAPTURE-ENDED segments=%d wall=%.0fs dir=%s" % (n, time.time() - t0, a.out), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
