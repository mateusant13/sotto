"""Measure the PEAK each input endpoint actually delivers, per host API.

Why this exists: the live run reported "CABLE Output" opened but 3.1e-05 peak,
while a sibling run on the SAME configured name reported 0.738586. A name is not
the variable that decides whether audio arrives -- the HOST API behind the index
is. This probe opens each endpoint for N seconds and reports the real peak, so
the choice between MME / DirectSound / WASAPI / WDM-KS is measured, not guessed.

Usage: py -3 _main/device-probe.py [seconds]
Prints one JSON line per endpoint plus a summary line.
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import sounddevice as sd

SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
BLOCK_MS = 100
FLOOR = 0.002

INTERESTING = ("cable", "voicemeeter", "mapeador", "mixagem", "entrada", "prim", "stereo")


def main() -> int:
    devs = [d for d in sd.query_devices() if d["max_input_channels"] > 0]
    rows = []
    for d in devs:
        if not any(k in d["name"].lower() for k in INTERESTING):
            continue
        api = sd.query_hostapis(d["hostapi"])["name"]
        peak = {"v": 0.0}
        blocks = {"n": 0}

        def cb(indata, frames, tinfo, status, _p=peak, _b=blocks):
            mono = indata.mean(axis=1) if indata.ndim > 1 else indata
            _b["n"] += 1
            p = float(np.abs(mono).max()) if mono.size else 0.0
            if p > _p["v"]:
                _p["v"] = p

        rate = 16000
        native = False
        try:
            sd.check_input_settings(device=d["index"], channels=1, dtype="float32", samplerate=16000)
        except Exception:
            rate = int(d["default_samplerate"])
            native = True
        rec = {
            "idx": d["index"],
            "api": api,
            "name": d["name"],
            "rate": rate,
            "native_rate": native,
            "peak": 0.0,
            "blocks": 0,
            "open_error": "",
        }
        try:
            st = sd.InputStream(
                device=d["index"], channels=1, samplerate=rate, dtype="float32",
                blocksize=int(rate * BLOCK_MS / 1000), callback=cb,
            )
            st.start()
            time.sleep(SECS)
            st.stop()
            st.close()
            rec["peak"] = round(peak["v"], 6)
            rec["blocks"] = blocks["n"]
        except Exception as exc:
            rec["open_error"] = f"{type(exc).__name__}: {exc}"
        rows.append(rec)
        print(json.dumps(rec, ensure_ascii=False), flush=True)

    live = [r for r in rows if r["peak"] >= FLOOR]
    print(json.dumps({
        "probe": "device-probe",
        "secs": SECS,
        "floor": FLOOR,
        "opened": len(rows),
        "carrying_audio": [f"{r['api']}#{r['idx']} {r['name']} peak={r['peak']}" for r in live],
        "silent": [f"{r['api']}#{r['idx']} {r['name']} peak={r['peak']}" for r in rows if r["peak"] < FLOOR],
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
