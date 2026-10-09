"""Build controlled music/game-bed mixes of a LABELLED diarization target, so
"does music break it?" becomes a DER number instead of an opinion.

Target:  _main\\diar-models\\0-four-speakers-zh.wav -- the vendor's own 4-speaker
         control, whose 10 segments / 4 labels are published AND reproduced
         byte-exactly by our --num-speakers 4 arm. Ground truth exists.
Bed:     the owner's OWN non-speech audio, _main\\live-sample-cable-input-90s.wav
         seconds 50.0-88.0. Provenance, not a genre claim: it is 38 s of
         continuous -33 dBFS audio in which BOTH the Redux ASR (word
         timestamps) and the pyannote segmenter find no speech, while both
         find the speech in 29.5-49.4 s of the same file (so the negative is a
         live instrument's negative, not a deaf one).

SNR is defined as 20*log10(rms(target) / rms(bed)) -- the bed's level relative
to the whole target file, not to its speech frames. Stated because the choice
moves the number.

Read-only instrument: reads WAVs, writes WAVs. Never opens an audio device.
"""
import argparse
import json
import os

import numpy as np
import soundfile as sf


def load_mono(path, want_sr=None):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if want_sr and sr != want_sr:
        n_out = int(round(len(x) * want_sr / sr))
        t_in = np.arange(len(x)) / sr
        t_out = np.arange(n_out) / want_sr
        x = np.interp(t_out, t_in, x).astype(np.float32)
        sr = want_sr
    return x, sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=r"_main\diar-models\0-four-speakers-zh.wav")
    ap.add_argument("--bed", default=r"_main\live-sample-cable-input-90s.wav")
    ap.add_argument("--bed-start", type=float, default=50.0)
    ap.add_argument("--bed-end", type=float, default=88.0)
    ap.add_argument("--snrs", default="15,5,0,-5")
    ap.add_argument("--outdir", default=r"_main\diar-mix")
    ap.add_argument("--peak-cap", type=float, default=0.95)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    tgt, sr = load_mono(args.target, want_sr=16000)
    bed_all, bed_sr = load_mono(args.bed, want_sr=sr)
    a, b = int(args.bed_start * sr), int(args.bed_end * sr)
    bed = bed_all[a:b]
    if len(bed) == 0:
        raise SystemExit("empty bed slice")

    # tile the bed to the target length
    reps = int(np.ceil(len(tgt) / len(bed)))
    bed = np.tile(bed, reps)[:len(tgt)]

    rms_t = float(np.sqrt(np.mean(tgt ** 2)))
    rms_b = float(np.sqrt(np.mean(bed ** 2)))
    peak_t = float(np.max(np.abs(tgt)))
    print("target %s  sr=%d  %.3fs  rms=%.6f (%.2f dBFS)  peak=%.4f"
          % (args.target, sr, len(tgt) / sr, rms_t, 20 * np.log10(rms_t), peak_t))
    print("bed    %s  [%.1f,%.1f]s  rms=%.6f (%.2f dBFS)  peak=%.4f"
          % (args.bed, args.bed_start, args.bed_end, rms_b, 20 * np.log10(rms_b),
             float(np.max(np.abs(bed)))))

    manifest = []
    clean = os.path.join(args.outdir, "mix-clean.wav")
    sf.write(clean, tgt, sr)
    manifest.append({"name": "mix-clean", "snr_db": None, "path": clean,
                     "rms": rms_t, "peak": peak_t, "note": "target alone"})

    for s in [float(v) for v in args.snrs.split(",")]:
        # want 20log10(rms_t / rms_bed_scaled) = s  ->  scale = rms_t / (10**(s/20) * rms_b)
        scale = rms_t / ((10.0 ** (s / 20.0)) * rms_b)
        mixed = tgt + scale * bed
        pk = float(np.max(np.abs(mixed)))
        gain = 1.0
        if pk > args.peak_cap:
            gain = args.peak_cap / pk
            mixed = mixed * gain
        name = "mix-snr%+03d" % int(round(s))
        p = os.path.join(args.outdir, name + ".wav")
        sf.write(p, mixed.astype(np.float32), sr)
        # measured, post-gain SNR
        rms_m = float(np.sqrt(np.mean(mixed ** 2)))
        meas = 20 * np.log10(rms_t * gain / (scale * rms_b * gain))
        print("%-14s snr_req=%+.1f dB  bed_gain=%.4f  out_peak=%.4f  out_rms=%.6f  snr_measured=%+.2f"
              % (name, s, scale, float(np.max(np.abs(mixed))), rms_m, meas))
        manifest.append({"name": name, "snr_db": s, "path": p,
                         "bed_gain": float(scale), "out_gain": float(gain),
                         "out_peak": float(np.max(np.abs(mixed))),
                         "out_rms": rms_m,
                         "snr_measured_db": float(meas)})

    # bed-only arm: a control that MUST come back with ~no speech
    bed_only = bed * (rms_t / rms_b)
    p = os.path.join(args.outdir, "mix-bedonly.wav")
    sf.write(p, bed_only.astype(np.float32), sr)
    manifest.append({"name": "mix-bedonly", "snr_db": None, "path": p,
                     "out_rms": float(np.sqrt(np.mean(bed_only ** 2))),
                     "note": "bed alone at the target's rms; must yield ~0 speech"})
    print("%-14s out_rms=%.6f  (must yield ~0 speech)" % ("mix-bedonly", float(np.sqrt(np.mean(bed_only ** 2)))))

    json.dump(manifest, open(os.path.join(args.outdir, "manifest.json"), "w", encoding="utf-8"), indent=1)
    print("wrote", os.path.join(args.outdir, "manifest.json"))


if __name__ == "__main__":
    main()
