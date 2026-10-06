"""All-inputs capture while a known tone is injected into a chosen render end.

The previous probe paired one render with one capture and read silence. That
cannot distinguish "the render stream never played" from "the loopback never
delivered". This one opens EVERY input endpoint simultaneously and renders into
ONE endpoint, so the single number that matters is: did ANY input see the tone
we injected, and if so which.

  render_played   : peaks seen on the inputs while injecting (>= floor => the
                    render really produced audio)
  nothing_seen    : NO input saw the injected tone -- either the render stream
                    is not producing, or no loopback on this box delivers it

Usage: py -3 _main/inject-all-probe.py [seconds] [render_substring] [hz]
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np
import sounddevice as sd

SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
RENDER = sys.argv[2] if len(sys.argv) > 2 else "VoiceMeeter Input"
HZ = float(sys.argv[3]) if len(sys.argv) > 3 else 440.0
AMP = 0.5
FLOOR = 0.002


def main() -> int:
    rd = None
    for d in sd.query_devices():
        if d["max_output_channels"] > 0 and RENDER.lower() in d["name"].lower():
            rd = d
            break
    print(json.dumps({
        "probe": "inject-all-probe",
        "render": rd["name"] if rd else None,
        "render_api": sd.query_hostapis(rd["hostapi"])["name"] if rd else None,
        "secs": SECS,
        "hz": HZ,
        "amp": AMP,
        "floor": FLOOR,
    }, ensure_ascii=False), flush=True)
    if rd is None:
        return 2

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
        except Exception as exc:
            print(json.dumps({"idx": d["index"], "name": d["name"], "open_error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), flush=True)

    out_rate = int(rd["default_samplerate"])
    cout = sd.OutputStream(device=rd["index"], channels=1, samplerate=out_rate, dtype="float32")
    cout.start()
    print(json.dumps({"probe": "inject-all-probe", "stage": "streams-open",
                      "inputs_open": len(streams)}, ensure_ascii=False), flush=True)

    t0 = time.time()
    phase = 0.0
    step = 2 * np.pi * HZ / out_rate
    while time.time() - t0 < SECS:
        n = int(out_rate * 0.1)
        buf = (AMP * np.sin(phase + step * np.arange(n))).astype(np.float32).reshape(-1, 1)
        phase += step * n
        cout.write(buf)
    cout.stop()
    cout.close()
    time.sleep(0.5)
    for st in streams:
        try:
            st.stop()
            st.close()
        except Exception:
            pass

    seen = []
    for d in sd.query_devices():
        i = d["index"]
        if i not in blocks:
            continue
        seen.append({
            "idx": i,
            "api": sd.query_hostapis(d["hostapi"])["name"],
            "name": d["name"],
            "peak": round(peaks.get(i, 0.0), 6),
            "blocks": blocks[i],
            "saw_tone": peaks.get(i, 0.0) >= FLOOR,
        })
    seen.sort(key=lambda r: -r["peak"])
    for r in seen:
        print(json.dumps(r, ensure_ascii=False), flush=True)
    carrying = [r for r in seen if r["saw_tone"]]
    print(json.dumps({
        "probe": "inject-all-probe",
        "verdict": "TONE-OBSERVED" if carrying else "NOTHING-SEEN",
        "carrying": [f"{r['api']}#{r['idx']} {r['name']} peak={r['peak']}" for r in carrying],
        "render": rd["name"],
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
