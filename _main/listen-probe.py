"""PASSIVE listen across every input endpoint for N seconds. Injects nothing.

This is the owner's-eye question answered without touching his audio: while
whatever he is playing runs by itself, which loopback endpoint (if any) carries
it? The inject-all probe proved the CAPTURE path works; this proves whether
anything is ROUTED at this instant.

Usage: py -3 _main/listen-probe.py [seconds]
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import sounddevice as sd

SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
FLOOR = 0.002

# Only loopback-ish endpoints. Microphones are excluded because a microphone
# picking up the room would answer a different question.
SKIP = ("microfone", "microphone", "line input", "mixagem")


def main() -> int:
    print(json.dumps({
        "probe": "listen-probe", "secs": SECS, "floor": FLOOR, "mode": "passive",
        "default_output": sd.query_devices(sd.default.device[1])["name"],
    }, ensure_ascii=False), flush=True)

    peaks: dict[int, float] = {}
    blocks: dict[int, int] = {}
    streams = []

    def make_cb(idx):
        def cb(indata, frames, tinfo, status):
            mono = indata.mean(axis=1) if indata.ndim > 1 else indata
            blocks[idx] = blocks.get(idx, 0) + 1
            p = float(np.abs(mono).max()) if mono.size else 0.0
            if p > peaks.get(idx, 0.0):
                peaks[idx] = p
        return cb

    for d in sd.query_devices():
        if d["max_input_channels"] <= 0:
            continue
        if any(k in d["name"].lower() for k in SKIP):
            continue
        rate = 16000
        try:
            sd.check_input_settings(device=d["index"], channels=1, dtype="float32", samplerate=16000)
        except Exception:
            rate = int(d["default_samplerate"])
        try:
            st = sd.InputStream(device=d["index"], channels=1, samplerate=rate,
                                dtype="float32", blocksize=int(rate * 0.05), callback=make_cb(d["index"]))
            st.start()
            streams.append(st)
        except Exception:
            pass

    print(json.dumps({"probe": "listen-probe", "stage": "listening", "inputs": len(streams)}, ensure_ascii=False), flush=True)
    time.sleep(SECS)
    for st in streams:
        try:
            st.stop()
            st.close()
        except Exception:
            pass

    rows = []
    for d in sd.query_devices():
        i = d["index"]
        if i not in blocks:
            continue
        rows.append({
            "idx": i,
            "api": sd.query_hostapis(d["hostapi"])["name"],
            "name": d["name"],
            "peak": round(peaks.get(i, 0.0), 6),
            "blocks": blocks[i],
            "carrying": peaks.get(i, 0.0) >= FLOOR,
        })
    rows.sort(key=lambda r: -r["peak"])
    for r in rows:
        print(json.dumps(r, ensure_ascii=False), flush=True)
    carrying = [r for r in rows if r["carrying"]]
    print(json.dumps({
        "probe": "listen-probe",
        "verdict": "AUDIO-ROUTED" if carrying else "NOTHING-ROUTED",
        "carrying": [f"{r['api']}#{r['idx']} {r['name']} peak={r['peak']}" for r in carrying],
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
