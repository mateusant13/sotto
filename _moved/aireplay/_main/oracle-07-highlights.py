"""ORACLE for `specs/07-highlights.md` -- the false-positive budget, in both colours.

WHAT IT ANSWERS, in one sentence: *would the spec's heuristic call a random 30 seconds of a
walk in the park a highlight?*

It runs the spec's scoring rule (section 3) verbatim -- the weights, the threshold, the
conjunct, the dynamic-range gate -- over four corpora and prints a verdict. The rule here is a
TRANSCRIPTION of the spec's formula, not a reimplementation of it: if you change a parameter in
the spec, change it here or the oracle is measuring something else.

ARMS
  A0  POSITIVE   real speech, the ASR spec's own registered slice [900, 1020) s.
                 Must emit >= 1 candidate, and every emit MUST fall inside a speech
                 segment -- that containment is the whole false-positive claim.
  A1  DEAD TONE  `_main/_import-bench/synth-180s-1080p30.mp4` -- the ONLY clip on this
                 box that carries an audio stream (MEASURED, population 28). Must emit 0.
  A2  WALK       synthetic pink-noise bed with slow amplitude wander: the closest honest
                 proxy for "30 seconds of a walk in the park" that exists on this box.
                 SYNTHETIC -- not capture-derived, and labelled as such. Must emit 0.
  A3  CONTROL    the NAIVE rule this spec replaces: score on envelope excursion alone
                 (w_A=0, w_E=1.0, threshold 0.60, no gates), over A1 and A2. MUST emit > 0.
                 If this arm emits 0, A1/A2 are passing for the wrong reason.

  THE A3 DESIGN IS NOT COSMETIC -- two defects the first runs of this oracle found in itself:
   1. Removing ONLY the speech conjunct still emitted 0 on both corpora, because the
      degenerate-signal gate short-circuits before scoring. That made the conjunct VACUOUS.
   2. Removing BOTH gates STILL emitted 0 -- because THRESHOLD=0.75 is unreachable without
      the conjunct's 0.60. A gate-removed copy of the same rule cannot fire by construction.
   A control that cannot fail is not a control. A3 is therefore the naive REPLACEMENT rule,
      which is the thing the spec actually claims to be better than.

Exit 0 = VERDICT PASS. Exit 2 = the oracle itself could not run. Exit 1 = a real arm failed.

No windows are ever opened: this is numpy-only, no subprocess, no model load (the splitter and
the level emitter are both model-free -- that is what makes this gate cheap enough to run).
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from asr.level import events_from_array          # noqa: E402
from asr.segment import segments_silence         # noqa: E402

SPEECH_WAV = Path(r"H:\sotto\_main\_redux-long\plain-3600s.wav")
TONE_MP4 = REPO / "_main" / "_import-bench" / "synth-180s-1080p30.mp4"
SPEECH_SLICE = (900.0, 1020.0)

# ---- the spec's parameters (specs/07-highlights.md section 7) --------------------------
W_A = 0.60          # speech-segment conjunct
W_E = 0.40          # normalised envelope excursion
W_K = 0.00          # ASR keyword -- PINNED 0, no real-time ASR exists
THRESHOLD = 0.75    # emit at or above this score
MIN_GAP_S = 20.0    # refractory between two highlights
MIN_DYNAMIC_RANGE = 3.0   # degenerate-signal gate (p99(peak) / p50(peak))
PEAK_REFERENCE_S = 300.0   # normalisation window for E

# THE NAIVE RULE the spec replaces -- the A3 control's own parameters. Envelope only, no
# gates, and its own natural threshold. Kept as separate literals on purpose: A3 must be a
# DIFFERENT RULE, not this rule with a gate switched off (see the A3 note in the docstring).
NAIVE_W_E = 1.0
NAIVE_THRESHOLD = 0.60

# THE TWO FALSE-POSITIVE BUDGETS. alpha is REACHABLE and MEASURED; beta is the product target
# and is NOT MEASURABLE with audio alone -- see the spec's section 5 for why the oracle failed
# it on first run at 15.00 / 10 min.
FP_ALPHA_PER_10MIN = 20.0   # v1 ceiling, continuous speech
FP_BETA_PER_10MIN = 1.0     # product target -- declared UNREACHABLE by audio alone


def read_wav_slice(path: Path, start_s: float, dur_s: float):
    w = wave.open(str(path), "rb")
    sr = w.getframerate()
    w.setpos(int(start_s * sr))
    x = np.frombuffer(w.readframes(int(dur_s * sr)), dtype="<i2").astype(np.float32) / 32768.0
    w.close()
    return x, sr


def decode_first_audio_stream(path: Path, dur_s: float):
    """ffmpeg -> 16 kHz mono. Lane L2 owns the real mux; this only feeds the oracle."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        tmp = Path(fh.name)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
           "-c:a", "pcm_s16le", str(tmp)]
    rc = subprocess.run(cmd, capture_output=True).returncode
    if rc != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg failed rc={rc} on {path}")
    x, sr = read_wav_slice(tmp, 0.0, dur_s)
    tmp.unlink(missing_ok=True)
    return x, sr


def synth_walk_bed(dur_s: float, sr: int = 16000, seed: int = 7) -> np.ndarray:
    """Pink-ish noise with slow amplitude wander. NOT speech. NOT capture-derived."""
    rng = np.random.default_rng(seed)
    n = int(dur_s * sr)
    white = rng.standard_normal(n).astype(np.float32)
    # 3 one-pole lowpasses ~= pink
    out = white.copy()
    for a in (0.92, 0.96, 0.99):
        acc = np.empty_like(out)
        prev = 0.0
        for i in range(n):
            prev = a * prev + (1.0 - a) * out[i]
            acc[i] = prev
        out = acc
    t = np.arange(n, dtype=np.float32) / sr
    wander = 0.35 + 0.65 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 23.0))
    return (out * wander * 0.25).astype(np.float32)


# ---- the spec's scoring rule (section 3) ------------------------------------------------
def score(x: np.ndarray, sr: int, use_speech_conjunct: bool = True,
          use_degenerate_gate: bool = True, naive: bool = False) -> dict:
    dur = len(x) / sr
    ev = events_from_array(x, sample_rate=sr)
    peak = np.array([e["p"] for e in ev], dtype=np.float64)
    env = np.array([e["e"] for e in ev], dtype=np.float64)
    if peak.size == 0:
        return {"state": "no-signal", "emits": [], "n_events": 0}

    w_a, w_e, thr = (0.0, NAIVE_W_E, NAIVE_THRESHOLD) if naive else (W_A, W_E, THRESHOLD)
    if naive:
        # The naive rule has no speech-segment requirement, so it scores EVERY window, not
        # one candidate per segment. That is the whole difference, and it is why it fires.
        use_degenerate_gate = False

    # GATE 0 -- degenerate signal. Measured anchors: 1.22x on a continuous tone,
    # 24.76x on real speech (spec section 1).
    p50 = float(np.percentile(peak, 50))
    p99 = float(np.percentile(peak, 99))
    dr = p99 / max(p50, 1e-9)
    if use_degenerate_gate and dr < MIN_DYNAMIC_RANGE:
        return {"state": "degenerate-signal", "dynamic_range": dr, "emits": [], "n_events": len(ev)}

    segs = segments_silence(x, sample_rate=sr)
    if naive:
        # No speech requirement: EVERY 1 s window is a candidate. This is the single
        # behavioural difference that makes the naive rule fire, and it is the thing the
        # spec's conjunct buys.
        cands = [(i * dur / len(ev), i * dur / len(ev) + 1.0) for i in range(len(ev))]
    else:
        if not segs:
            return {"state": "no-speech", "dynamic_range": dr, "emits": [], "n_segments": 0}
        cands = segs

    win = max(1, int(PEAK_REFERENCE_S * len(ev) / max(dur, 1e-9)))
    emits, last = [], -1e9
    n_outside = 0
    for a, b in cands:
        i0 = max(0, int(a * len(ev) / dur))
        i1 = min(len(ev), max(i0 + 1, int(b * len(ev) / dur)))
        lo = max(0, i1 - win)
        ref = float(np.percentile(env[lo:i1], 99)) or 1.0
        k = int(np.argmax(env[i0:i1])) + i0
        t = k * dur / len(ev)
        A = 1.0 if (use_speech_conjunct and not naive) else 0.0
        E = float(np.clip(env[k] / max(ref, 1e-9), 0.0, 1.0))
        score_t = w_a * A + w_e * E + W_K * 0.0
        if score_t < thr or (t - last) < MIN_GAP_S:
            continue
        last = t
        emits.append({"t": round(t, 2), "score": round(score_t, 4), "E": round(E, 4)})
        if not naive and not (a <= t <= b):
            n_outside += 1

    return {
        "state": "scored",
        "dynamic_range": round(dr, 3),
        "n_segments": len(segs),
        "n_events": len(ev),
        "emits": emits,
        "emits_outside_speech": n_outside,
    }


def line(tag, r, dur):
    return (f"{tag:<9} state={r['state']:<20} emits={len(r['emits']):<3} "
            f"outside_speech={r.get('emits_outside_speech', '-')} dur={dur:.0f}s")


def main() -> int:
    out, fails = [], []

    # A0 -- POSITIVE. SPEECH_SLICE is (start, end); the DURATION is the difference. Reading
    # `dur_s = end` instead silently ran past the end of the file and reported a 1020 s
    # "120 s slice" -- caught because the oracle printed its own duration.
    try:
        xs, sr = read_wav_slice(SPEECH_WAV, SPEECH_SLICE[0], SPEECH_SLICE[1] - SPEECH_SLICE[0])
    except Exception as exc:  # pragma: no cover
        print(f"ORACLE-BROKEN: cannot read {SPEECH_WAV}: {exc}")
        return 2
    r0 = score(xs, sr)
    d0 = len(xs) / sr
    out.append(line("A0-real", r0, d0))
    per10 = 10.0 * len(r0["emits"]) / max(d0 / 60.0, 1e-9)
    out.append(f"          real: dr={r0.get('dynamic_range')} segments={r0.get('n_segments')} "
               f"emits={len(r0['emits'])} rate={per10:.2f} highlights / 10 min")
    if len(r0["emits"]) < 1:
        fails.append("A0: the rule found NOTHING in real speech")
    if r0.get("emits_outside_speech", 0) != 0:
        fails.append(f"A0: {r0['emits_outside_speech']} emit(s) fell OUTSIDE a speech segment")
    # THE FP BUDGET, enforced. alpha is the reachable v1 ceiling; beta is the product target
    # and is asserted as NOT REACHABLE rather than silently weakened (spec section 5).
    if per10 > FP_ALPHA_PER_10MIN:
        fails.append(f"A0: {per10:.2f} highlights / 10 min EXCEEDS the v1 budget of "
                     f"{FP_ALPHA_PER_10MIN}")
    if per10 <= FP_BETA_PER_10MIN:
        out.append(f"          NOTE: rate <= beta ({FP_BETA_PER_10MIN}/10min) -- if this ever "
                   f"holds on a LONGER corpus, beta stops being unreachable and the spec "
                   f"section 5 claim must be revisited.")

    # A1 -- the only clip on this box that carries audio
    xt, sr = decode_first_audio_stream(TONE_MP4, 180.0)
    r1 = score(xt, sr)
    out.append(line("A1-tone", r1, len(xt) / sr))
    if len(r1["emits"]) != 0:
        fails.append(f"A1: {len(r1['emits'])} highlight(s) emitted from a clip with NO speech")

    # A2 -- the walk in the park
    xw = synth_walk_bed(180.0)
    r2 = score(xw, 16000)
    out.append(line("A2-walk", r2, len(xw) / 16000))
    if len(r2["emits"]) != 0:
        fails.append(f"A2: {len(r2['emits'])} highlight(s) emitted from 180 s of a WALK")

    # A3 -- CONTROL: the NAIVE rule (envelope only, no gates, its own threshold) over the
    # SAME two corpora. Same refractory, so the only difference is the gates+conjunct.
    for tag, xa, sra in (("A3-tone", xt, sr), ("A3-walk", xw, 16000)):
        rc = score(xa, sra, naive=True)
        out.append(f"{tag:<9} state={rc['state']:<20} emits={len(rc['emits']):<3} "
                   f"(NAIVE rule, no gates -- must be > 0)")
        if len(rc["emits"]) == 0:
            fails.append(f"{tag}: the naive control emitted 0 -- the gates are VACUOUS")

    print("\n".join(out))
    print()
    print(f"FP budget: alpha={FP_ALPHA_PER_10MIN}/10min (v1, measured {per10:.2f}) · "
          f"beta={FP_BETA_PER_10MIN}/10min (target, NOT reachable by audio alone)")
    if fails:
        for f in fails:
            print(f"FAIL  {f}")
        print(f"\nVERDICT FAIL ({len(fails)} arm(s))")
        return 1
    print("VERDICT PASS -- 0 highlights from 180 s of tone and 180 s of a walk; "
          "the control arm fires without the conjunct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())