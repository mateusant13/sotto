"""Speech-vs-music/game classifier, so a claim about "music in the audio" is a
measurement and not an impression.

Instrument: the envelope MODULATION SPECTRUM. Speech has its dominant envelope
energy in the 2-8 Hz "syllabic" band (Scheirer & Slaney, "Construction and
evaluation of a robust multifeature speech/music discriminator", ICASSP 1997);
music and game beds put theirs at the beat/bar rate (0.5-2 Hz) and in broadband
transients. The reported statistic is

    mod_ratio = energy(2-8 Hz) / energy(0.5-2 Hz)

on the RMS envelope of a 4 s window, hopped 1 s.

Both colours are required and both are provided by --controls:
  POSITIVE (must read as SPEECH): the bundled pt-BR clip, the vendor control file
  NEGATIVE (must read as NON-SPEECH): a synthetic drone, a synthetic music bed
A statistic that cannot separate those two has no standing to classify anything.

Read-only: reads WAVs, writes a JSON/table. Never opens an audio device.
"""
import argparse
import json
import sys

import numpy as np
import soundfile as sf

FRAME = 0.025
HOP = 0.010
WIN_S = 4.0
STEP_S = 1.0


def load_mono(path):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    return x.mean(axis=1), sr


def envelope(x, sr):
    """RMS envelope sampled at 1/HOP Hz (100 Hz)."""
    n = int(FRAME * sr)
    h = int(HOP * sr)
    sr_env = 1.0 / HOP
    if len(x) < n:
        return np.zeros(0), sr_env
    k = 1 + (len(x) - n) // h
    idx = np.arange(n)[None, :] + h * np.arange(k)[:, None]
    fr = x[idx]
    w = np.hanning(n).astype(np.float32)[None, :]
    return np.sqrt((fr * fr * w * w).sum(axis=1) / (w * w).sum()), sr_env


def mod_ratio(env, sr_env):
    """energy(2-8 Hz)/energy(0.5-2 Hz) of the envelope over a WIN_S window."""
    w = int(WIN_S * sr_env)
    if len(env) < w:
        return None
    e = env[:w].astype(np.float64)
    e = e - e.mean()
    if e.std() < 1e-9:
        return 0.0
    e = e * np.hanning(w)
    P = np.abs(np.fft.rfft(e)) ** 2
    f = np.fft.rfftfreq(w, 1.0 / sr_env)
    lo = P[(f >= 0.5) & (f < 2.0)].sum()
    hi = P[(f >= 2.0) & (f < 8.0)].sum()
    return float(hi / max(lo, 1e-30))


def trace(path):
    x, sr = load_mono(path)
    env, sr_env = envelope(x, sr)
    w = int(WIN_S * sr_env)
    h = int(STEP_S * sr_env)
    out = []
    t = 0.0
    i = 0
    while i + w <= len(env):
        r = mod_ratio(env[i:i + w], sr_env)
        seg = x[int(t * sr):int((t + STEP_S) * sr)]
        rms = 20 * np.log10(max(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 1e-10, 1e-10))
        out.append({"t": round(t, 3), "mod_ratio": r, "rms_dbfs": round(float(rms), 2)})
        t += STEP_S
        i += h
    return out


def synth_controls(sr=16000, secs=12.0):
    t = np.arange(int(sr * secs)) / sr
    rng = np.random.default_rng(7)
    # music bed: 3 harmonic tones + 1 Hz amplitude beat + light noise
    music = (0.30 * np.sin(2 * np.pi * 220 * t)
             + 0.22 * np.sin(2 * np.pi * 330 * t)
             + 0.18 * np.sin(2 * np.pi * 440 * t))
    music *= (0.6 + 0.4 * np.sin(2 * np.pi * 1.0 * t))
    music += 0.02 * rng.standard_normal(len(t))
    # drone: single sustained tone, no syllabic structure
    drone = 0.3 * np.sin(2 * np.pi * 110 * t) + 0.05 * rng.standard_normal(len(t))
    return music.astype(np.float32), drone.astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--controls", action="store_true")
    args = ap.parse_args()

    rows = trace(args.wav)
    print("== %s ==" % args.wav)
    print("  t(s)   mod_ratio  rms_dBFS   class")
    for r in rows:
        c = "SPEECH" if (r["mod_ratio"] or 0) >= 1.0 else "NON-SPEECH"
        print("  %5.0f   %9.3f  %8.1f   %s" % (r["t"], r["mod_ratio"] or 0.0, r["rms_dbfs"], c))

    if args.controls:
        print()
        print("== CONTROLS ==")
        import tempfile, os
        music, drone = synth_controls()
        for name, sig in (("synthetic-music-bed", music), ("synthetic-drone", drone)):
            p = os.path.join(tempfile.gettempdir(), "_modctl_%s.wav" % name)
            sf.write(p, sig, 16000)
            rr = trace(p)
            vals = [r["mod_ratio"] for r in rr if r["mod_ratio"] is not None]
            print("  %-24s n=%d  median_mod_ratio=%.3f  -> %s"
                  % (name, len(vals), float(np.median(vals)),
                     "SPEECH" if np.median(vals) >= 1.0 else "NON-SPEECH"))
        for name, p in (("bundled-pt-br-sample", r"_main\pt-br-sample.wav"),
                        ("vendor-4spk-control", r"_main\diar-models\0-four-speakers-zh.wav")):
            rr = trace(p)
            vals = [r["mod_ratio"] for r in rr if r["mod_ratio"] is not None]
            print("  %-24s n=%d  median_mod_ratio=%.3f  -> %s"
                  % (name, len(vals), float(np.median(vals)),
                     "SPEECH" if np.median(vals) >= 1.0 else "NON-SPEECH"))

    if args.out:
        json.dump(rows, open(args.out, "w", encoding="utf-8"), indent=1)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
