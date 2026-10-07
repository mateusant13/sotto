"""AudioEscopo — do the PortAudio (rung b) inputs actually carry the audio?

The OLD ladder's rung (b) candidates on this box are the cable/stereo-mix INPUT
devices (`CABLE Output`, `VoiceMeeter Output`, `Mixagem estéreo`). The shell's
retained evidence for the broken run was `device-rotated reason=flat
peak=0.250364` — i.e. SOME candidate carried signal and still produced no
caption. This measures, model-free, what each rung-(b) input delivers while the
fixture is rendered into `CABLE Input`, so the residual loss point is named with
a number instead of guessed.

    pythonw.exe _main/audio-escopo-capture-inputs.py <seconds>
"""
import io
import os
import sys
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "audio-escopo-capture-inputs.log")
log = io.open(LOG, "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


TARGETS = ("cable output", "voicemeeter output", "mixagem est", "entrada (realtek")

devs = sd.query_devices()
apis = sd.query_hostapis()
picks = []
for i in range(len(devs)):
    d = devs[i]
    if d["max_input_channels"] <= 0:
        continue
    low = d["name"].lower()
    if any(t in low for t in TARGETS):
        picks.append((i, d["name"], apis[d["hostapi"]]["name"], int(d["default_samplerate"])))

p("=== rung-(b) INPUT devices on this box ===")
for i, name, api, sr in picks:
    p("  id=%-4d api=%-22s sr=%-6d %r" % (i, api, sr, name))

pcm, src_sr = sf.read(r"H:\sotto\worker\assets\sample1.flac", dtype="float32")
if pcm.ndim > 1:
    pcm = pcm.mean(axis=1)


def play():
    """Render the fixture into the WASAPI `CABLE Input` (sd index 27 here)."""
    idx = None
    for i in range(len(devs)):
        d = devs[i]
        if d["max_output_channels"] > 0 and "cable input" in d["name"].lower() \
                and "wasapi" in apis[d["hostapi"]]["name"].lower():
            idx = i
            break
    if idx is None:
        p("!! no WASAPI CABLE Input render device -- no stimulus")
        return
    rate = int(sd.query_devices(idx)["default_samplerate"])
    n = int(len(pcm) * rate / src_sr)
    data = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)
    pos = [0]
    ext = np.concatenate([data, np.zeros(rate, dtype=np.float32)])

    def cb(outdata, frames, t, status):
        need, out = frames, []
        while need > 0:
            take = min(need, len(ext) - pos[0])
            out.append(ext[pos[0]:pos[0] + take])
            pos[0] += take
            need -= take
            if pos[0] >= len(ext):
                pos[0] = 0
        chunk = np.concatenate(out)
        outdata[:len(chunk), 0] = chunk
        if outdata.shape[1] > 1:
            outdata[:len(chunk), 1] = chunk
        outdata[len(chunk):] = 0

    try:
        with sd.OutputStream(device=idx, samplerate=rate, channels=2, dtype="float32", callback=cb):
            time.sleep(SECONDS + 1.0)
    except Exception as exc:
        p("!! play failed: %s: %s" % (type(exc).__name__, exc))


pt = threading.Thread(target=play, daemon=True)
pt.start()
time.sleep(0.4)

p("")
p("=== capturing each rung-(b) input for %.1f s while the fixture renders into CABLE Input ===" % SECONDS)
for i, name, api, sr in picks:
    chunks = []

    def cb(indata, frames, t, status, _c=chunks):
        _c.append(indata[:, 0].copy())

    try:
        with sd.InputStream(device=i, samplerate=sr, channels=1, dtype="float32", callback=cb):
            time.sleep(SECONDS)
    except Exception as exc:
        p("  %-40r  OPEN/READ FAILED: %s: %s" % (name, type(exc).__name__, exc))
        continue
    x = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    peak = float(np.abs(x).max()) if x.size else 0.0
    rms = float(np.sqrt((x.astype("float64") ** 2).mean())) if x.size else 0.0
    p("  %-40r  api=%-20s n=%-8d peak=%.6f rms=%.6f" % (name, api, x.size, peak, rms))

pt.join(timeout=3.0)
log.close()
