"""Candidate-order arm: rotations before the first caption, and the seconds to it.

Runs the SHIPPED worker out of a chosen directory against a stimulus that is
timed to a chosen EVENTS, not to a wall-clock guess:

  * the fixture is rendered into the WASAPI `CABLE Input` -- the endpoint this
    box's audio actually goes to, and NOT the default render endpoint
    (`VoiceMeeter Input`), which is what makes the choice matter at all;
  * `mode=spawn`   : the fixture becomes audible `play_delay_s` after the SPAWN.
  * `mode=capture` : the fixture becomes audible `play_delay_s` after the FIRST
    `capture-started` line -- i.e. while the ladder is inside its first window.
    This is the arm that separates "the reading can answer" from "it cannot":
    the order was fixed before the audio existed, and only the SECOND choice can
    know better.

Every worker stdout line is timestamped on ARRIVAL, so the arm can report, in
seconds from spawn: the number of `device-rotated reason=flat` rows before the
first caption, and when the first caption landed.

The stimulus stream is opened on the MAIN thread: opening it on a worker thread
fails on this box with `PortAudioError ... WdmSyncIoctl: DeviceIoControl GLE =
0x00000490` (measured, 6/6 attempts), while the same device opens fine from the
main thread -- so the thread only flips a mute flag, and never touches PortAudio.

    python.exe _main/_ordem-arm.py <worker-dir> <out-prefix> <mode> <play-delay-s> <max-seconds>
"""
import json
import os
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

PYEXE = r"C:\Program Files\Python311\python.exe"
CREATE_NO_WINDOW = 0x08000000
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "..", "worker", "assets", "sample1.flac")

worker_dir = os.path.abspath(sys.argv[1])
prefix = os.path.abspath(sys.argv[2])
mode = sys.argv[3]
play_delay = float(sys.argv[4])
max_seconds = sys.argv[5] if len(sys.argv) > 5 else "20"

log = open(prefix + ".out", "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


# ── the stimulus device ──────────────────────────────────────────────────────
devs = sd.query_devices()
apis = sd.query_hostapis()
cable_idx = None
for i in range(len(devs)):
    d = devs[i]
    if d["max_output_channels"] > 0 and "cable input" in d["name"].lower() \
            and "wasapi" in apis[d["hostapi"]]["name"].lower():
        cable_idx = i
        break
if cable_idx is None:
    p("!! no WASAPI CABLE Input render device -- no stimulus")
    sys.exit(2)
p("stimulus device id=%d name=%r api=%r" % (cable_idx, devs[cable_idx]["name"],
                                            apis[devs[cable_idx]["hostapi"]]["name"]))

pcm, src_sr = sf.read(FIXTURE, dtype="float32")
if pcm.ndim > 1:
    pcm = pcm.mean(axis=1)
rate = int(sd.query_devices(cable_idx)["default_samplerate"])
n = int(len(pcm) * rate / src_sr)
data = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)
p("fixture %s src_sr=%d -> out_sr=%d samples=%d (%.2f s)"
  % (os.path.basename(FIXTURE), src_sr, rate, n, n / rate))

stop = threading.Event()
pos = [0]
on = [False]     # the fixture is audible only while this is True
trigger = [None]  # wall time the stimulus is timed from


def cb(outdata, frames, t, status):
    if not on[0]:
        outdata[:] = 0
        return
    need, out = frames, []
    while need > 0:
        take = min(need, len(data) - pos[0])
        out.append(data[pos[0]:pos[0] + take])
        pos[0] += take
        need -= take
        if pos[0] >= len(data):
            pos[0] = 0
    chunk = np.concatenate(out)
    outdata[:len(chunk), 0] = chunk
    if outdata.shape[1] > 1:
        outdata[:len(chunk), 1] = chunk
    outdata[len(chunk):] = 0


stream = None
last = None
for attempt in range(6):
    try:
        stream = sd.OutputStream(device=cable_idx, samplerate=rate, channels=2,
                                 dtype="float32", callback=cb)
        stream.start()
        break
    except Exception as exc:
        last = exc
        stream = None
        p(".. stream open attempt %d failed: %s: %s"
          % (attempt + 1, type(exc).__name__, str(exc)[:120]))
        time.sleep(1.0)
if stream is None:
    p("!! could not open the stimulus stream: %s" % last)
    sys.exit(2)
p("stimulus stream OPEN (silent until the trigger)")


def stimulus_thread():
    while trigger[0] is None and not stop.is_set():
        time.sleep(0.005)
    target = trigger[0] + play_delay
    while time.time() < target and not stop.is_set():
        time.sleep(0.005)
    on[0] = True
    p("STIMULUS_ON at spawn+%.3f" % (time.time() - t0))


# ── the worker ───────────────────────────────────────────────────────────────
t0 = time.time()
if mode == "spawn":
    trigger[0] = t0
threading.Thread(target=stimulus_thread, daemon=True).start()

proc = subprocess.Popen(
    [PYEXE, "-u", os.path.join(worker_dir, "sotto_worker.py"),
     "--max-seconds", max_seconds],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
    errors="replace", bufsize=1, creationflags=CREATE_NO_WINDOW, cwd=worker_dir,
)
p("SPAWN mode=%s delay=%.2f argv=%s pid=%d"
  % (mode, play_delay, [PYEXE, os.path.join(worker_dir, "sotto_worker.py")], proc.pid))

rows = []
lock = threading.Lock()


def pump(stream_, name):
    for line in stream_:
        line = line.rstrip("\n")
        now = time.time()
        with lock:
            rows.append((now - t0, name, line))
        if name == "err":
            p("  err +%.3f %s" % (now - t0, line))
        elif mode == "capture" and trigger[0] is None and "capture-started" in line:
            trigger[0] = now


ts = [threading.Thread(target=pump, args=(proc.stdout, "out")),
      threading.Thread(target=pump, args=(proc.stderr, "err"))]
for t in ts:
    t.start()
rc = proc.wait(timeout=300)
for t in ts:
    t.join(timeout=5)
stop.set()
try:
    stream.stop()
    stream.close()
except Exception:
    pass
p("EXIT rc=%d at spawn+%.3f" % (rc, time.time() - t0))

json.dump([{"t": round(t, 3), "s": s, "line": ln} for t, s, ln in rows],
          open(prefix + ".lines.json", "w", encoding="utf-8"), indent=0)

# ── what the arm measured ────────────────────────────────────────────────────
rotations = []
first_capture = None
first_caption = None
captures = []
for t, s, ln in sorted(rows):
    if s != "out":
        continue
    try:
        o = json.loads(ln)
    except Exception:
        continue
    if o.get("type") == "status":
        if o.get("state") == "capture-started":
            captures.append((round(t, 3), o.get("device"), o.get("attempt")))
            if first_capture is None:
                first_capture = (round(t, 3), o.get("device"), o.get("attempt"), o.get("of"))
        if o.get("state") == "device-rotated":
            rotations.append((round(t, 3), o.get("reason"), o.get("from"), o.get("to"),
                              o.get("peak"), o.get("attempt")))
    if o.get("type") == "caption" and first_caption is None:
        first_caption = (round(t, 3), o.get("text"))

rot_before_caption = len(rotations) if first_caption is None else \
    len([r for r in rotations if r[0] < first_caption[0]])

summary = {
    "arm": os.path.basename(prefix),
    "mode": mode,
    "play_delay_s": play_delay,
    "rc": rc,
    "rotations_total": len(rotations),
    "rotations_before_first_caption": rot_before_caption,
    "rotations": rotations,
    "captures": captures,
    "first_capture": first_capture,
    "first_caption": first_caption,
}
json.dump(summary, open(prefix + ".summary.json", "w", encoding="utf-8"), indent=1)
p("")
p("SUMMARY %s" % json.dumps(summary))
log.close()
print(json.dumps(summary))
