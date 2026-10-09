"""Content map of a WAV: log-mel spectrogram + energy, so a human (or an agent
reading the PNG) can see WHERE speech is, where music/game audio is, and where
the diarizer's boundaries land.

Read-only instrument: reads a WAV, writes a PNG + a per-second feature table.
No audio device is ever opened.

Usage:
  py -3 _main\\_diar-content-map.py --wav FILE --out PNG [--from-json arm.json]
"""
import argparse
import json
import os
import sys

import numpy as np
import soundfile as sf

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load_mono(path):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    return x, sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--from-json", default=None,
                    help="diarization JSON whose segments are drawn as bars")
    ap.add_argument("--title", default=None)
    ap.add_argument("--n-mels", type=int, default=128)
    ap.add_argument("--n-fft", type=int, default=1024)
    ap.add_argument("--hop", type=int, default=160)
    args = ap.parse_args()

    x, sr = load_mono(args.wav)
    dur = len(x) / sr

    # --- log-mel spectrogram (our own, no torch) ---
    n_fft, hop = args.n_fft, args.hop
    win = np.hanning(n_fft).astype(np.float32)
    n_frames = 1 + max(0, (len(x) - n_fft) // hop)
    S = np.empty((n_fft // 2 + 1, n_frames), dtype=np.float32)
    for i in range(n_frames):
        seg = x[i * hop: i * hop + n_fft]
        if len(seg) < n_fft:
            seg = np.pad(seg, (0, n_fft - len(seg)))
        S[:, i] = np.abs(np.fft.rfft(seg * win))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)

    # mel filterbank (slaney-ish, plain triangular on Hz)
    def hz2mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel2hz(m):
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    n_mels = args.n_mels
    mel_pts = mel2hz(np.linspace(hz2mel(0.0), hz2mel(sr / 2), n_mels + 2))
    fb = np.zeros((n_mels, len(freqs)), dtype=np.float32)
    for m in range(n_mels):
        lo, ce, hi = mel_pts[m], mel_pts[m + 1], mel_pts[m + 2]
        if hi <= lo:
            continue
        left = (freqs - lo) / max(ce - lo, 1e-9)
        right = (hi - freqs) / max(hi - ce, 1e-9)
        fb[m] = np.clip(np.minimum(left, right), 0.0, None)
    M = fb @ S
    MdB = 20.0 * np.log10(np.maximum(M, 1e-10))

    # --- per-second features ---
    sec = int(np.ceil(dur))
    rms_db, centroid, flatness = [], [], []
    for t in range(sec):
        a, b = t * sr, min((t + 1) * sr, len(x))
        w = x[a:b]
        if len(w) == 0:
            rms_db.append(-120.0); centroid.append(0.0); flatness.append(0.0)
            continue
        rms_db.append(20.0 * np.log10(max(float(np.sqrt(np.mean(w ** 2))), 1e-10)))
        W = np.abs(np.fft.rfft(w * np.hanning(len(w))))
        wf = np.fft.rfftfreq(len(w), 1.0 / sr)
        p = W ** 2 + 1e-12
        centroid.append(float((wf * W).sum() / max(W.sum(), 1e-12)))
        flatness.append(float(np.exp(np.mean(np.log(p))) / np.mean(p)))

    # --- diarization bars ---
    segs = []
    if args.from_json:
        d = json.load(open(args.from_json, encoding="utf-8"))
        segs = d.get("segments", [])

    fig, axes = plt.subplots(
        3, 1, figsize=(20, 10), sharex=True,
        gridspec_kw={"height_ratios": [5, 1.2, 1.2]})

    ax = axes[0]
    extent = [0, n_frames * hop / sr, 0, sr / 2000.0]
    im = ax.imshow(MdB, origin="lower", aspect="auto", extent=extent,
                   cmap="magma", vmin=MdB.max() - 80, vmax=MdB.max())
    ax.set_ylabel("kHz")
    ax.set_title(args.title or os.path.basename(args.wav))
    fig.colorbar(im, ax=ax, pad=0.005, label="dB")

    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    for s in segs:
        ax.axvline(s["start"], color="cyan", lw=0.7, alpha=0.55)
        ax.axvline(s["end"], color="cyan", lw=0.7, alpha=0.55)
        ax.hlines(7.2, s["start"], s["end"],
                  color=colors[s["speaker"] % 10], lw=5)
        ax.text((s["start"] + s["end"]) / 2, 7.6, "s%02d" % s["speaker"],
                ha="center", fontsize=7, color="white")

    ax2 = axes[1]
    ax2.plot(np.arange(sec) + 0.5, rms_db, color="tab:green", lw=1)
    ax2.axhline(-40, color="tab:red", ls=":", lw=1)
    ax2.axhline(-50, color="tab:orange", ls=":", lw=1)
    ax2.set_ylabel("dBFS/s")
    ax2.grid(alpha=0.3)

    ax3 = axes[2]
    ax3.plot(np.arange(sec) + 0.5, centroid, color="tab:blue", lw=1, label="centroid Hz")
    ax3b = ax3.twinx()
    ax3b.plot(np.arange(sec) + 0.5, flatness, color="tab:red", lw=1, label="flatness")
    ax3b.set_yscale("log")
    ax3.set_ylabel("centroid Hz", color="tab:blue")
    ax3b.set_ylabel("flatness", color="tab:red")
    ax3.set_xlabel("seconds")
    ax3.grid(alpha=0.3)

    plt.tight_layout()
    fig.savefig(args.out, dpi=90)
    print("wrote", args.out)

    print("sec  rms_dBFS  centroid_Hz  flatness")
    for t in range(sec):
        print("%3d  %8.1f  %10.0f  %8.4f" % (t, rms_db[t], centroid[t], flatness[t]))


if __name__ == "__main__":
    main()
