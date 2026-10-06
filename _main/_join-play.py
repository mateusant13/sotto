"""Play a speech file into a VIRTUAL CABLE, so the worker captures it live.

This is the audio source for the caption-join measurement (lane SottoCaptionJoin).
It plays `worker/assets/sample1.flac` on a named OUTPUT device — the VB-Audio
"CABLE Input" — whose only destination is the paired "CABLE Output", which the
worker taps. Nothing reaches a speaker, so this runs under `pythonw.exe` with
no console and no sound.

    pythonw.exe _main/_join-play.py <output-device-substring> [seconds] [file]
"""
import sys
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

target = sys.argv[1] if len(sys.argv) > 1 else "CABLE Input"
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
path = sys.argv[3] if len(sys.argv) > 3 else "H:/sotto/worker/assets/sample1.flac"

pcm, sr = sf.read(path, dtype="float32")
if pcm.ndim > 1:
    pcm = pcm.mean(axis=1)

idx = None
for i, d in enumerate(sd.query_devices()):
    if d["max_output_channels"] > 0 and target.lower() in d["name"].lower():
        idx = i
        break
if idx is None:
    sys.stderr.write(f"no output device matching {target!r}\n")
    raise SystemExit(2)

# The transport is fed in blocks under a callback rather than one long `write`:
# a single write of 60 s of audio would be one blocking call that a stop cannot
# interrupt, and the point here is a bounded, interruptible source.
pos = 0
silence = np.zeros(0, dtype=np.float32)
pcm = np.concatenate([pcm, np.zeros(800, dtype=np.float32)])  # a real pause between reps


def callback(outdata, frames, time_info, status):
    global pos
    need = frames
    out = []
    while need > 0:
        take = min(need, len(pcm) - pos)
        out.append(pcm[pos : pos + take])
        pos += take
        need -= take
        if pos >= len(pcm):
            pos = 0
    chunk = np.concatenate(out)
    outdata[: len(chunk), 0] = chunk
    if outdata.shape[1] > 1:
        outdata[: len(chunk), 1] = chunk
    outdata[len(chunk) :] = 0


sys.stderr.write(f"PLAYING device={sd.query_devices(idx)['name']!r} file={path} sr={sr} seconds={seconds}\n")
sys.stderr.flush()
with sd.OutputStream(device=idx, samplerate=sr, channels=2,
                     dtype="float32", callback=callback):
    time.sleep(seconds)
sys.stderr.write("PLAY_DONE\n")
sys.stderr.flush()
