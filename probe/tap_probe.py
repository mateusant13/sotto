"""Does any loopback device actually CAPTURE sound right now?

The panel says "Waiting for audio" and the owner says his PC has audio playing
all the time. Those can only both be true if the tap is on the wrong device, or
if no tap exists. This answers it by MEASURING, not by listing names: for each
candidate input it opens a real stream for a few seconds and reports peak and
RMS amplitude.

A device that opens but returns all zeros is the important result. Names
appearing in query_devices() prove the device is enumerated, NOT that it carries
signal, and the owner's report is evidence that the two were conflated.
"""

import json
import sys
import time

import numpy as np
import sounddevice as sd

WINDOW_S = 2.0
SR = 48000
CANDIDATE_HINTS = ("loopback", "cable", "voicemeeter", "sound mapper", "render", "output", "mix")

results = {"devices": [], "captured": []}


def looks_like_tap(name):
    low = name.lower()
    return any(h in low for h in CANDIDATE_HINTS)


def measure(device, seconds=WINDOW_S):
    """Open a real stream and measure it. Returns a dict, never raises.

    Uses a CALLBACK stream, not the blocking reader: PortAudio on this host
    refuses blocking reads with PaErrorCode -9999 'Blocking API not supported
    yet' (Windows WDM-KS), which is why every device failed on the first run of
    this probe. The callback path is the non-blocking one PortAudio does support.
    """
    out = {
        "device": device["name"],
        "channels": device["max_input_channels"],
        "default_rate": int(device["default_samplerate"]),
        "state": "UNKNOWN",
    }
    peak = [0.0]
    rms_acc = [0.0]
    blocks = [0]
    overflowed = [False]

    def cb(indata, frames, time_info, status):
        if status:
            overflowed[0] = True
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata
        peak[0] = max(peak[0], float(np.max(np.abs(mono))))
        rms_acc[0] += float(np.sqrt(np.mean(mono**2)))
        blocks[0] += 1

    ch = min(2, device["max_input_channels"])
    try:
        stream = sd.InputStream(
            device=device["index"],
            channels=ch,
            samplerate=SR,
            dtype="float32",
            blocksize=1024,
            callback=cb,
        )
        with stream:
            time.sleep(seconds)
        rms = rms_acc[0] / blocks[0] if blocks[0] else 0.0
        out.update(
            {
                "state": "CAPTURED" if peak[0] > 0.001 else "SILENT",
                "blocks": blocks[0],
                "peak": round(peak[0], 6),
                "rms": round(rms, 6),
                "samplerate_used": SR,
                "channels_used": ch,
                "overflowed": bool(overflowed[0]),
            }
        )
    except Exception as exc:
        out.update({"state": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
    return out


devs = sd.query_devices()
inputs = [d for d in devs if d["max_input_channels"] > 0]
print(f"INPUT DEVICE POPULATION = {len(inputs)}", flush=True)

# Measure every candidate tap plus every distinct input name, deduplicated, so a
# microphone cannot be silently reported as the system tap.
seen = set()
targets = []
for d in inputs:
    key = d["name"]
    if key in seen:
        continue
    seen.add(key)
    targets.append(d)

candidates = [d for d in targets if looks_like_tap(d["name"])]
others = [d for d in targets if not looks_like_tap(d["name"])]

print(f"CANDIDATE TAPS = {len(candidates)}", flush=True)
for d in candidates:
    r = measure(d)
    results["captured"].append(r)
    print(
        f"  TAP   {r['state']:9s} peak={r.get('peak', 0.0):.6f} "
        f"rms={r.get('rms', 0.0):.6f}  {r['device']}"
        + (f"  [{r['error']}]" if "error" in r else ""),
        flush=True,
    )

# A short sweep of the rest, so if the real tap is named something unexpected we
# find it rather than reporting silence across the board.
print(f"OTHER INPUTS SWEPT = {min(len(others), 8)}", flush=True)
for d in others[:8]:
    r = measure(d, seconds=1.0)
    results["devices"].append(r)
    print(
        f"  OTHER {r['state']:9s} peak={r.get('peak', 0):.6f}  {r['device']}",
        flush=True,
    )

live = [r for r in results["captured"] if r["state"] == "CAPTURED"]
results["verdict"] = (
    f"{len(live)} candidate tap(s) carried signal"
    if live
    else "NO candidate tap carried signal - every loopback-capable input returned silence"
)
print("VERDICT " + results["verdict"], flush=True)
print(json.dumps(results, indent=2, ensure_ascii=False))
sys.exit(0 if live else 1)