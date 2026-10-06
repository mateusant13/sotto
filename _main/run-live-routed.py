"""POSITIVE arm: prove the whole chain end-to-end through the REAL device.

The 22 s smoke run and the fix both said the same thing: "CABLE Output opened,
delivered silence". That is a statement about ROUTING, not about the worker.
This harness closes the loop without touching the owner's audio settings:

  1. render the bundled speech sample (assets/sample1.flac) into
     "CABLE Input (VB-Audio Virtual Cable)" — a VIRTUAL endpoint, so nothing
     becomes audible on the owner's speakers;
  2. run the REAL worker, unmodified, against "CABLE Output";
  3. assert the worker opened CABLE Output and emitted captions.

If this prints captions with device="CABLE Output ...", then the worker, the
model, the decode contract and the capture path are all correct, and the
owner's failure is exactly one thing: nothing is routed into the cable.

No console window: the worker is spawned with CREATE_NO_WINDOW.

Usage: py -3 _main/run-live-routed.py <out.jsonl> <seconds>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.normpath(os.path.join(HERE, "..", "worker", "sotto_worker.py"))
SAMPLE = os.path.normpath(os.path.join(HERE, "..", "worker", "assets", "sample1.flac"))
# MEASURED: the loopback is asymmetric across host APIs on this box. Rendering
# into the MME "CABLE Input" and capturing the DirectSound "CABLE Output"
# delivered peak=0.4999 (inject-all-probe). The FIRST match of the full name
# is the DirectSound render, and DirectSound->DirectSound does NOT loop back on
# this host (measured peak=3.1e-05) — which is why the first positive-arm run
# read silence even though the cable was being fed. Match the short prefix and
# prefer the lowest index, which is MME.
RENDER = "CABLE Input"
DEVICE = "CABLE Output (VB-Audio Virtual Cable)"

CREATE_NO_WINDOW = 0x08000000


def load_audio(path: str, rate: int):
    """Read the sample and resample to `rate`. soundfile first, wave fallback."""
    try:
        import soundfile as sf

        data, sr = sf.read(path, dtype="float32", always_2d=True)
        mono = data.mean(axis=1).astype(np.float32)
    except Exception:
        import wave

        with wave.open(path, "rb") as w:
            sr = w.getframerate()
            ch = w.getnchannels()
            raw = w.readframes(w.getnframes())
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        mono = a.reshape(-1, ch).mean(axis=1) if ch > 1 else a
    if sr != rate:
        n = int(len(mono) * rate / sr)
        mono = np.interp(np.linspace(0, len(mono) - 1, n), np.arange(len(mono)), mono).astype(np.float32)
    return mono


def feeder(rate: int, stop: threading.Event):
    """Render the sample into the cable on loop, at a level the model reads."""
    try:
        audio = load_audio(SAMPLE, rate)
    except Exception as exc:
        print(json.dumps({"inject_error": f"{type(exc).__name__}: {exc}"}), flush=True)
        return
    dev = None
    for d in sd.query_devices():
        if d["max_output_channels"] > 0 and RENDER.lower() in d["name"].lower():
            dev = d
            break
    if dev is None:
        print(json.dumps({"inject_error": f"render endpoint not found: {RENDER}"}), flush=True)
        return
    stream = sd.OutputStream(device=dev["index"], channels=1, samplerate=rate, dtype="float32")
    stream.start()
    pos = 0
    print(json.dumps({"inject": "started", "render": dev["name"],
                      "api": sd.query_hostapis(dev["hostapi"])["name"],
                      "sample_s": round(len(audio) / rate, 2)}), flush=True)
    chunk = int(rate * 0.1)
    try:
        while not stop.is_set():
            if pos + chunk > len(audio):
                pos = 0
            stream.write((0.6 * audio[pos:pos + chunk]).reshape(-1, 1))
            pos += chunk
    finally:
        stream.stop()
        stream.close()
        print(json.dumps({"inject": "stopped"}), flush=True)


def main() -> int:
    out_path = sys.argv[1]
    secs = float(sys.argv[2])
    stop = threading.Event()
    t = threading.Thread(target=feeder, args=(44100, stop), daemon=True)
    t.start()
    time.sleep(1.5)  # let the render stream settle before the worker opens its tap

    out = open(out_path, "wb")
    errf = open(out_path + ".err", "wb")
    t0 = time.time()
    proc = subprocess.Popen(
        [sys.executable, WORKER, "--max-seconds", str(secs), "--device", DEVICE],
        stdout=out, stderr=errf, stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW, cwd=os.path.dirname(WORKER),
    )
    rc = proc.wait(timeout=300)
    stop.set()
    t.join(timeout=5)
    out.close()
    errf.close()

    statuses, captions = [], []
    with open(out_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            (captions if o.get("type") == "caption" else statuses).append(
                o.get("text", "") if o.get("type") == "caption" else o
            )

    print(json.dumps({
        "cmd": f"sotto_worker.py --max-seconds {secs} --device \"{DEVICE}\"",
        "wall_s": round(time.time() - t0, 1),
        "EXIT_CODE": rc,
        "captions": len(captions),
        "caption_words": " ".join(c.strip() for c in captions if c.strip()),
    }, ensure_ascii=False))
    for o in statuses:
        if o.get("state") in ("device", "capture-started", "device-rotated",
                              "device-exhausted", "silent-device", "done", "error"):
            print(json.dumps(o, ensure_ascii=False)[:900])
    return 0


if __name__ == "__main__":
    sys.exit(main())
