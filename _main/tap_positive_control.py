"""POSITIVE CONTROL for Sotto's tap: does any candidate device actually carry
the audio the machine is PLAYING?

Main's measurement of 2026-10-06 showed the worker capturing 24.64 s from
'Mapeador de som da Microsoft - Input' with peak=0.000122 and every ASR chunk
blank. That number alone cannot distinguish:
  (a) the machine was playing nothing, from
  (b) the tap is the wrong endpoint.

This script removes that ambiguity by measuring each candidate device TWICE:
once while the machine is playing a known file through the DEFAULT render
endpoint, and once in silence. A device that carries system audio MUST diverge
between the two arms. A device that reports ~0 in both is either the wrong
endpoint or a dead one - and either way it cannot be the tap.

Read-only: opens streams, prints a table, writes nothing.
"""

from __future__ import annotations

import time

import numpy as np
import soundfile as sf
import sounddevice as sd

ASSET = r"H:/sotto/worker/assets/sample1.flac"
ARM_SECONDS = 3.0
SILENCE = 1e-5

CANDIDATE_SUBSTRINGS = (
    "Mapeador",
    "VoiceMeeter",
    "CABLE",
    "Mixagem",
    "primario",
    "Stereo Mix",
    "Alto-falante",
    "Speakers",
    "HDMI",
)


def candidates():
    out = []
    for i, d in enumerate(sd.query_devices()):
        if int(d["max_input_channels"]) < 1:
            continue
        name = d["name"]
        if any(s.lower() in name.lower() for s in CANDIDATE_SUBSTRINGS):
            out.append(i)
    return out


def measure(idx: int, seconds: float):
    """Open a CALLBACK input stream; return (peak, rms, nonzero, blocks, err)."""
    d = sd.query_devices(idx)
    ch = max(1, min(2, int(d["max_input_channels"])))
    rate = int(d["default_samplerate"] or 48000)
    peak = 0.0
    acc = 0.0
    n = 0
    nonzero = 0
    blocks = 0

    def cb(indata, frames, t, status):
        nonlocal peak, acc, n, nonzero, blocks
        a = np.abs(indata)
        p = float(a.max()) if a.size else 0.0
        if p > peak:
            peak = p
        acc += float((indata.astype(np.float64) ** 2).sum())
        n += indata.size
        if p > SILENCE:
            nonzero += 1
        blocks += 1

    try:
        with sd.InputStream(
            device=idx, channels=ch, samplerate=rate, callback=cb, blocksize=0
        ):
            time.sleep(seconds)
    except Exception as e:  # noqa: BLE001 - the failure IS the datum
        return (-1.0, -1.0, -1, -1, f"{type(e).__name__}: {e}")
    rms = float(np.sqrt(acc / n)) if n else 0.0
    return (peak, rms, nonzero, blocks, "")


def main() -> int:
    data, sr = sf.read(ASSET, dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    clip = data[: int(sr * ARM_SECONDS)]
    cands = candidates()
    print(f"# asset={ASSET} sr={sr} clip={clip.shape[0]/sr:.2f}s")
    print(f"# candidates={len(cands)}")
    print("# idx | name | arm | peak | rms | nonzero_blocks | blocks | err")
    rows = []
    for idx in cands:
        name = sd.query_devices(idx)["name"]
        # ARM A: silence (nothing playing)
        r_sil = measure(idx, ARM_SECONDS)
        # ARM B: the machine is playing the clip through its DEFAULT output
        sd.play(clip, sr)
        time.sleep(0.35)
        r_play = measure(idx, ARM_SECONDS)
        sd.stop()
        time.sleep(0.2)
        for arm, r in (("silence", r_sil), ("playing", r_play)):
            print(
                f"{idx} | {name} | {arm} | {r[0]:.6f} | {r[1]:.6f} | "
                f"{r[2]} | {r[3]} | {r[4]}"
            )
        rows.append((idx, name, r_sil, r_play))
    print("# --- verdict ---")
    for idx, name, rs, rp in rows:
        if rp[0] < 0:
            print(f"# {name}: UNMEASURABLE ({rp[4]})")
        elif rp[0] >= SILENCE and rp[0] > rs[0] * 3:
            print(f"# {name}: CARRIES SYSTEM AUDIO (silence peak {rs[0]:.6f} -> playing peak {rp[0]:.6f})")
        elif rp[0] >= SILENCE:
            print(f"# {name}: signal in BOTH arms ({rs[0]:.6f} / {rp[0]:.6f}) - diverges=false, not proof")
        else:
            print(f"# {name}: SILENT IN BOTH ARMS (peak {rs[0]:.6f} / {rp[0]:.6f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
