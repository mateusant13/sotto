"""Segmentation: BY SILENCE, never on a fixed grid -- `specs/02-asr.md` section 3.

A fixed 10 s grid cuts words in half; the measured ratio against the reference is 0.229
(docs/research/05-onnx-asr.md:105). Cut on silence and the int8 export's text IS the Redux
text (05-onnx-asr.md:107-110).

The algorithm below is a verbatim port of `_main/probe-onnx-asr-split.py:45-95` -- the probe
that produced every number in the spec -- with the constants named. It is energy-only:
onnx-asr's own Silero VAD is not on disk and was never exercised (05-onnx-asr.md:119-120).

The splitter is deterministic and model-free, so its output on a registered slice is a
byte-level regression target that costs no inference to check.
"""

from __future__ import annotations

from .constants import (
    CONTROL_SEGMENT_MODE,
    DEFAULT_SEGMENT_MODE,
    FIXED_GRID_S,
    FRAME_MS,
    MAX_SEGMENT_S,
    MIN_SEGMENT_S,
    MIN_SILENCE_S,
    MODE_FIXED,
    MODE_SILENCE,
    PAD_S,
    SAMPLE_RATE,
    SILENCE_ABS_FLOOR,
    SILENCE_FLOOR_PERCENTILE,
    SILENCE_THRESHOLD_MULT,
)

__all__ = ["segments_silence", "segments_fixed", "segments_for_mode", "SEGMENT_MODES"]

SEGMENT_MODES = (MODE_SILENCE, MODE_FIXED)


def segments_silence(
    x,
    sample_rate: int = SAMPLE_RATE,
    frame_ms: int = FRAME_MS,
    min_silence_s: float = MIN_SILENCE_S,
    max_segment_s: float = MAX_SEGMENT_S,
    min_segment_s: float = MIN_SEGMENT_S,
    pad_s: float = PAD_S,
) -> list[tuple[float, float]]:
    """Cut a float32 mono array into speech segments, on silence.

    Returns [(start_s, end_s)] in seconds relative to the start of `x`. Segments carry
    `pad_s` of context either side, which is why adjacent segments overlap.
    """
    import numpy as np

    frame_s = frame_ms / 1000.0
    fl = int(round(sample_rate * frame_s))
    if fl <= 0 or len(x) < fl:
        return []
    n = len(x) // fl
    frames = x[: n * fl].reshape(n, fl)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)

    floor = float(np.percentile(rms, SILENCE_FLOOR_PERCENTILE))  # probe:50
    thr = max(floor * SILENCE_THRESHOLD_MULT, SILENCE_ABS_FLOOR)  # probe:51
    silent = rms < thr

    # a silent run of >= min_silence_s is cut at its MIDPOINT (probe:54-65)
    min_run = int(round(min_silence_s / frame_s))
    cuts: list[int] = []
    i = 0
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            if j - i >= min_run:
                cuts.append((i + j) // 2)
            i = j
        else:
            i += 1

    bounds = [0, *cuts, n]
    segs: list[tuple[int, int]] = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = (a, b)
        # oversize segments are split at the QUIETEST frame in [min_seg, max_seg] (probe:70-75)
        while (seg[1] - seg[0]) * frame_s > max_segment_s:
            lim_lo = seg[0] + int(round(min_segment_s / frame_s))
            lim_hi = seg[0] + int(round(max_segment_s / frame_s))
            if lim_hi <= lim_lo:
                break
            k = int(np.argmin(rms[lim_lo:lim_hi])) + lim_lo
            segs.append((seg[0], k))
            seg = (k, seg[1])
        segs.append(seg)

    pad = int(round(pad_s / frame_s))
    out: list[tuple[float, float]] = []
    for a, b in segs:
        if (b - a) * frame_s < min_segment_s:  # probe:80-81
            continue
        if b > a and silent[a:b].all():  # probe:82-83: silence-only segments are dropped
            continue
        out.append((max(0, (a - pad) * fl) / sample_rate, min(len(x), (b + pad) * fl) / sample_rate))
    return out


def segments_fixed(total_s: float, chunk_s: float = FIXED_GRID_S) -> list[tuple[float, float]]:
    """CONTROL ONLY -- the forbidden grid. Exists so the oracle can prove it is worse."""
    out: list[tuple[float, float]] = []
    t = 0.0
    while t < total_s - 1e-6:
        b = min(t + chunk_s, total_s)
        out.append((t, b))
        t = b
    return out


def segments_for_mode(x, mode: str = DEFAULT_SEGMENT_MODE, max_segment_s: float = MAX_SEGMENT_S,
                      fixed_chunk_s: float = FIXED_GRID_S, sample_rate: int = SAMPLE_RATE):
    """Dispatch on the LITERAL mode names, never on the (mutable) default constant."""
    if mode == MODE_SILENCE:
        return segments_silence(x, sample_rate=sample_rate, max_segment_s=max_segment_s)
    if mode == MODE_FIXED:
        return segments_fixed(len(x) / float(sample_rate), fixed_chunk_s)
    raise ValueError(f"unknown segment mode {mode!r}; expected one of {SEGMENT_MODES}")
