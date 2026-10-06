"""SottoAgcSpeechOrder — LIVE proof of the ORDER, three arms on the SAME code.

The order this lane establishes: the speech/music decision runs on the PRE-GAIN
signal, and the gain is applied to the SPEECH component only. These arms measure
that on the shipped worker, live, through the default render loopback.

  drone      : play the REAL captured drone (worker source: peak 0.103287, rms
               -37.6 dBFS, 90% of energy below 1 kHz). The gate calls it non-speech,
               so the AGC must HOLD: gain_max_db=+0.0 while gain_would_max_db
               reports the boost it refused. captions ~0.
  speech     : play a quiet-but-SPEECH clip (played peak ~0.1005). The gate keeps
               it, so the AGC must APPLY: gain_max_db>0 and a caption appears.
  redfixture : the SAME quiet-speech source through the SAME code with the
               `agc.process(...)` call removed (a mutant written NEXT TO the worker
               so its imports resolve). The gate must read RED.

Everyone is spawned with pythonw + CREATE_NO_WINDOW (0x08000000) ALONE. No window.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

ROOT = r"H:\sotto"
PYW = r"C:\Program Files\Python311\pythonw.exe"
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
CFG = os.path.join(ROOT, "worker", "config.json")
DRONE = os.path.join(ROOT, "_main", "agc_drone_floor.wav")
SPEECH = os.path.join(ROOT, "_main", "pt-br-sample.wav")
MUTANT = os.path.join(ROOT, "worker", "_sotto_worker_agcinert.py")
CREATE_NO_WINDOW = 0x08000000
SECONDS = int(os.environ.get("AGCO_SECONDS", "20"))

# The exact shipped line whose removal makes the stage inert (the RED fixture).
GAIN_LINE = "seg_in = agc.process(seg, speech=speech) if agc_enabled else seg"


def make_mutant():
    src = open(WORKER, encoding="utf-8").read()
    assert GAIN_LINE in src, "the gain line moved; update the fixture"
    mut = src.replace(GAIN_LINE, "seg_in = seg  # MUTANT: AGC application removed")
    with open(MUTANT, "w", encoding="utf-8") as fh:
        fh.write(mut)
    print(f"MUTANT written: {MUTANT} (gain line removed)")


def load(path, gain=None):
    x, sr = sf.read(path, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if gain is not None:
        x = (x * gain).astype(np.float32)
    return x, sr


def summarise(path):
    caps, done = [], None
    for ln in open(path, encoding="utf-8"):
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            o = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if o.get("type") == "caption":
            caps.append(o.get("text"))
        if o.get("state") == "done":
            done = o
    keys = ("verdict", "captions", "peak", "peak_out", "gain_db", "gain_max_db",
            "gain_would_max_db", "held_blocks", "speech_blocks", "agc",
            "music_gated_chunks", "gate", "queue_drops")
    return caps, {k: done[k] for k in keys if done and k in done}


def run(arm, worker, src, src_sr, seconds, stop):
    out = open(os.path.join(ROOT, "_main", f"agco_{arm}.jsonl"), "w", encoding="utf-8")
    errf = open(os.path.join(ROOT, "_main", f"agco_{arm}.err"), "w", encoding="utf-8")
    env = os.environ.copy()
    env.pop("SOTTO_AUDIO_FILE", None)
    env.pop("SOTTO_AGC", None)      # default = on
    env.pop("SOTTO_GATE", None)     # default = on (live)
    # `--tap-window 60` > `--max-seconds` PINS candidate 1 (the default render
    # loopback) for the whole run: a flat candidate (the drone, which captions
    # nothing) would otherwise rotate onto VoiceMeeter/CABLE carrying a sibling
    # lane's audio, and the arm would measure the sibling, not the drone.
    argv = [PYW, worker, "--config", CFG, "--stats-interval", "5",
            "--tap-window", "60", "--max-seconds", str(seconds)]
    p = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=errf,
                         creationflags=CREATE_NO_WINDOW)

    def player():
        while not stop.is_set():
            try:
                sd.play(src, src_sr, blocking=True)
            except Exception as exc:  # noqa: BLE001
                print("play error:", exc)
                return

    th = threading.Thread(target=player, daemon=True)
    th.start()
    t0 = time.time()
    try:
        rc = p.wait(timeout=180)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = "TIMEOUT"
    stop.set()
    try:
        sd.stop()
    except Exception:  # noqa: BLE001
        pass
    out.close()
    errf.close()
    time.sleep(0.5)
    caps, done = summarise(os.path.join(ROOT, "_main", f"agco_{arm}.jsonl"))
    print(f"ARM {arm} rc={rc} wall={time.time()-t0:.1f}s captions={len(caps)} {caps}")
    print(f"     done={json.dumps(done)}")
    return rc


def main():
    make_mutant()
    drone, dsr = load(DRONE, gain=1.0)
    speech, ssr = load(SPEECH)
    orig = float(np.abs(speech).max())
    sg = 0.1005 / orig
    speech = (speech * sg).astype(np.float32)
    print(f"DRONE  {DRONE} sr={dsr} peak={abs(drone).max():.6f}")
    print(f"SPEECH {SPEECH} sr={ssr} played_peak={abs(speech).max():.6f} (gain {20*np.log10(sg):+.1f} dBFS)")

    only = sys.argv[1] if len(sys.argv) > 1 else None
    arms = (
        ("drone", WORKER, drone, dsr),
        ("speech", WORKER, speech, ssr),
        ("redfixture", MUTANT, speech, ssr),
    )
    for arm, worker, src, sr in arms:
        if only and only != arm:
            continue
        run(arm, worker, src, sr, SECONDS, threading.Event())
    print("DONE")


if __name__ == "__main__":
    main()
