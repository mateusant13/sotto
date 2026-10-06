"""Positive control: does the loopback chain work AT ALL on this box?

The live run found every preferred tap silent. Two rival explanations, and they
demand opposite fixes:

  (A) the code/capture path is broken, or
  (B) nothing is routed into the cable right now.

This settles it without the owner having to play anything: render a KNOWN tone
into each render endpoint ("CABLE Input", "VoiceMeeter Input", ...) and measure
which INPUT endpoint receives it. A chain that returns the injected peak is
proved end to end; a chain that returns silence on a tone WE just sent is
measured, not guessed.

Usage: py -3 _main/inject-probe.py [seconds] [freq]
Prints one JSON line per (render, capture) pair actually exercised.
"""

from __future__ import annotations

import json
import sys
import threading
import time

import numpy as np
import sounddevice as sd

SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
FREQ = float(sys.argv[2]) if len(sys.argv) > 2 else 440.0
AMP = 0.5
FLOOR = 0.002

# Render endpoints worth injecting into, and the input endpoints that would
# receive that render stream if the owner's routing is intact.
PAIRS = [
    ("CABLE Input (VB-Audio Virtual Cable)", "CABLE Output (VB-Audio Virtual Cable)"),
    ("VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)", "VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)"),
    ("Mapeador de som da Microsoft - Output", "Mapeador de som da Microsoft - Input"),
]


def find_out(substr):
    for d in sd.query_devices():
        if d["max_output_channels"] > 0 and substr.lower() in d["name"].lower():
            return d
    return None


def find_in(substr):
    for d in sd.query_devices():
        if d["max_input_channels"] > 0 and substr.lower() in d["name"].lower():
            return d
    return None


def open_stream(dev, is_input, callback=None):
    rate = 16000 if is_input else int(dev["default_samplerate"])
    try:
        if is_input:
            sd.check_input_settings(device=dev["index"], channels=1, dtype="float32", samplerate=16000)
        else:
            sd.check_output_settings(device=dev["index"], channels=1, dtype="float32", samplerate=rate)
    except Exception:
        rate = int(dev["default_samplerate"])
    st = (sd.InputStream if is_input else sd.OutputStream)(
        device=dev["index"], channels=1, samplerate=rate, dtype="float32",
        **({"callback": callback} if callback is not None else {}),
    )
    return st, rate


def run_pair(render_name, capture_name):
    rec = {
        "render": render_name,
        "capture": capture_name,
        "injected_hz": FREQ,
        "injected_amp": AMP,
        "capture_peak": 0.0,
        "blocks": 0,
        "error": "",
    }
    rd, cd = find_out(render_name), find_in(capture_name)
    if rd is None or cd is None:
        rec["error"] = f"endpoint not found (render={rd is not None} capture={cd is not None})"
        return rec

    peak = {"v": 0.0}
    blocks = {"n": 0}

    def cb(indata, frames, tinfo, status):
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata
        blocks["n"] += 1
        p = float(np.abs(mono).max()) if mono.size else 0.0
        if p > peak["v"]:
            peak["v"] = p

    try:
        cin, cin_rate = open_stream(cd, True, cb)
        cout, cout_rate = open_stream(rd, False)
        cin.start()
        cout.start()
        t0 = time.time()
        phase = 0.0
        step = 2 * np.pi * FREQ / cout_rate
        while time.time() - t0 < SECS:
            n = int(cout_rate * 0.1)
            buf = (AMP * np.sin(phase + step * np.arange(n))).astype(np.float32).reshape(-1, 1)
            phase += step * n
            cout.write(buf)
        cout.stop()
        cout.close()
        time.sleep(0.4)
        cin.stop()
        cin.close()
        rec["capture_peak"] = round(peak["v"], 6)
        rec["blocks"] = blocks["n"]
        rec["capture_rate"] = cin_rate
        rec["render_rate"] = cout_rate
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def main() -> int:
    print(json.dumps({"probe": "inject-probe", "secs": SECS, "floor": FLOOR,
                      "default_output": repr(sd.query_devices(sd.default.device[1])["name"])},
                     ensure_ascii=False), flush=True)
    proved = []
    for render_name, capture_name in PAIRS:
        rec = run_pair(render_name, capture_name)
        rec["carries_injected"] = bool(not rec["error"] and rec["capture_peak"] >= FLOOR)
        if rec["carries_injected"]:
            proved.append(f"{render_name} -> {capture_name} peak={rec['capture_peak']}")
        print(json.dumps(rec, ensure_ascii=False), flush=True)
    print(json.dumps({"probe": "inject-probe", "verdict": "chain-proved" if proved else "NO-CHAIN-PROVED",
                      "proved": proved}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
