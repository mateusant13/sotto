"""Inspect WAV files: header, duration, peak/RMS per channel, sha256. READ ONLY."""
import hashlib
import struct
import sys
import wave

import numpy as np


def info(path):
    out = {"path": path}
    with open(path, "rb") as fh:
        raw = fh.read()
    out["sha256"] = hashlib.sha256(raw).hexdigest()
    out["bytes"] = len(raw)
    import soundfile as sf

    si = sf.info(path)
    out["channels"] = si.channels
    out["rate"] = si.samplerate
    out["sampwidth"] = 4 if si.subtype.startswith("FLOAT") else 2
    out["subtype"] = si.subtype
    out["format"] = si.format
    out["frames"] = si.frames
    out["seconds"] = si.frames / float(si.samplerate)
    a, _ = sf.read(path, dtype="float64", always_2d=True)
    if out["channels"] > 1:
        a = a.reshape(-1, out["channels"])
    else:
        a = a.reshape(-1, 1)
    out["peak_per_ch"] = [float(np.max(np.abs(a[:, c]))) for c in range(out["channels"])]
    out["rms_per_ch"] = [float(np.sqrt(np.mean(a[:, c] ** 2))) for c in range(out["channels"])]
    # fraction of 100ms windows below -50 dBFS -> digital silence
    win = int(0.1 * out["rate"])
    mono = a.mean(axis=1)
    n = len(mono) // win
    if n:
        w2 = mono[: n * win].reshape(n, win)
        r = np.sqrt(np.mean(w2 ** 2, axis=1))
        out["windows_100ms"] = int(n)
        out["windows_below_-50dBFS"] = int(np.sum(r < 10 ** (-50 / 20.0)))
        out["windows_below_-40dBFS"] = int(np.sum(r < 10 ** (-40 / 20.0)))
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        d = info(p)
        for k, v in d.items():
            print(f"{k}: {v}")
        print("-" * 60)
