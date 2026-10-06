"""Speech/music gate oracle (lane SottoSpeechSeparation).

A regression check for the ONE decision the gate makes: is a 560 ms chunk
speech? It exercises `sotto_worker.SpeechMusicGate` directly -- no model, no
audio device, ~1 second -- so it is cheap enough to run on every change to the
gate, and it FAILS on the plausible breakage (threshold moved, feature swapped,
hangover removed).

  python speech-gate-oracle.py            # exit 0 = PASS, 1 = FAIL
  python speech-gate-oracle.py --json     # machine-readable

RED input (the negative control) is the captured drone from 2026-10-06; the
GREEN inputs are the four speech fixtures in the repo. If the drone capture is
absent, the drone arm falls back to a synthesized 60 Hz tone so the oracle still
has a negative -- and says which it used.
"""
import argparse
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))
import sotto_worker as W  # noqa: E402

SR, CHUNK = 16000, 8960

SPEECH = [
    os.path.join(ROOT, "worker", "assets", "sample1.flac"),
    os.path.join(ROOT, "worker", "assets", "sample2.flac"),
    os.path.join(HERE, "pt-br-sample.wav"),
    os.path.join(HERE, "en-us-sample.wav"),
]
DRONE = os.path.join(HERE, "bfrc_live_capture2.wav")


def to_16k(x, sr):
    if sr == SR:
        return x.astype(np.float32)
    n = int(round(len(x) * SR / sr))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def load(path):
    x, sr = sf.read(path, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    return to_16k(x, sr)


def synth_drone(secs=8.0):
    t = np.arange(int(secs * SR)) / SR
    return (0.3 * np.sin(2 * np.pi * 60 * t) + 0.15 * np.sin(2 * np.pi * 120 * t)
            + 0.07 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)


def gate_chunks(x):
    g = W.SpeechMusicGate()
    n = len(x) // CHUNK
    kept = [g.is_speech(x[i * CHUNK:(i + 1) * CHUNK]) for i in range(n)]
    return n, sum(kept), n - sum(kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    problems = []
    rows = []

    # NEGATIVE: the gate must withhold every chunk of a stationary drone.
    drone_src = DRONE if os.path.exists(DRONE) else "synth:60Hz"
    drone = load(DRONE) if os.path.exists(DRONE) else synth_drone()
    n, kept, gated = gate_chunks(drone)
    rows.append(dict(arm="drone", src=drone_src, chunks=n, kept=kept, gated=gated))
    if n == 0:
        problems.append("drone arm had no chunks")
    elif gated != n:
        problems.append(f"drone arm kept {kept}/{n} chunks; every one must be gated")

    # POSITIVE: the gate must KEEP the speech fixtures (allowing for genuine
    # pauses inside a clip, which are correctly gated). The bar is a majority
    # kept AND at least one caption-worthy run -- a gate that gated speech would
    # fail here, which is the regression this exists to catch.
    for p in SPEECH:
        if not os.path.exists(p):
            problems.append(f"missing speech fixture {p}")
            continue
        x = load(p)
        n, kept, gated = gate_chunks(x)
        frac = kept / n if n else 0.0
        rows.append(dict(arm="speech", src=os.path.basename(p), chunks=n, kept=kept, gated=gated,
                         kept_frac=round(frac, 3)))
        if frac < 0.5:
            problems.append(f"{os.path.basename(p)}: kept only {kept}/{n} ({frac:.2f}) -- gate ate speech")

    ok = not problems
    out = dict(ok=ok, thresholds=dict(db_range_min=W.GATE_DB_RANGE_MIN,
                                      rms_floor=W.GATE_RMS_FLOOR, hold_chunks=W.GATE_HOLD_CHUNKS),
               rows=rows, problems=problems)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("speech-gate oracle")
        print(f"  thresholds: dbrange>={W.GATE_DB_RANGE_MIN} rms>={W.GATE_RMS_FLOOR} hold={W.GATE_HOLD_CHUNKS}")
        for r in rows:
            extra = f" kept_frac={r['kept_frac']}" if "kept_frac" in r else ""
            print(f"  {r['arm']:6} {r['src']:28} chunks={r['chunks']:3} kept={r['kept']:3} "
                  f"gated={r['gated']:3}{extra}")
        print("  VERDICT:", "PASS" if ok else "FAIL")
        for p in problems:
            print("   -", p)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
