"""Audio in: PCM 16 kHz mono PCM16 wav slices.

The contract is the model's own (`specs/02-asr.md` section 8): 16 kHz mono PCM16. Anything
else is REFUSED LOUDLY -- a silent resample is how a language or a level gets destroyed.
This module never opens an audio device; it reads a file.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Iterator

from .constants import SAMPLE_RATE

__all__ = ["WavFormatError", "WavInfo", "wav_info", "read_slice", "iter_blocks"]


class WavFormatError(RuntimeError):
    """The file is not 16 kHz mono PCM16 -- refused, never converted."""


class WavInfo:
    __slots__ = ("path", "sample_rate", "channels", "sampwidth", "frames", "duration_s")

    def __init__(self, path: Path, sample_rate: int, channels: int, sampwidth: int, frames: int):
        self.path = path
        self.sample_rate = sample_rate
        self.channels = channels
        self.sampwidth = sampwidth
        self.frames = frames
        self.duration_s = frames / float(sample_rate) if sample_rate else 0.0

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sampwidth": self.sampwidth,
            "frames": self.frames,
            "duration_s": round(self.duration_s, 3),
        }


def wav_info(path: str | Path) -> WavInfo:
    p = Path(path)
    if not p.exists():
        raise WavFormatError(f"wav not found: {p}")
    with wave.open(str(p), "rb") as f:
        return WavInfo(p, f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getnframes())


def _check(info: WavInfo) -> None:
    if info.sampwidth != 2:
        raise WavFormatError(f"expected PCM_16 (sampwidth=2), got sampwidth={info.sampwidth}: {info.path}")
    if info.channels != 1:
        raise WavFormatError(f"expected mono, got channels={info.channels}: {info.path}")
    if info.sample_rate != SAMPLE_RATE:
        raise WavFormatError(
            f"expected {SAMPLE_RATE} Hz (the model contract), got {info.sample_rate} Hz: {info.path}"
        )


def read_slice(path: str | Path, offset_s: float = 0.0, max_s: float = 0.0):
    """Read [offset_s, offset_s+max_s) as float32 mono in [-1, 1]; max_s<=0 reads to the end."""
    import numpy as np  # imported here so the thread env is pinned before numpy loads

    info = wav_info(path)
    _check(info)
    with wave.open(str(info.path), "rb") as f:
        start = int(round(offset_s * info.sample_rate))
        f.setpos(min(max(start, 0), info.frames))
        left = info.frames - start if max_s <= 0 else min(info.frames - start, int(round(max_s * info.sample_rate)))
        raw = f.readframes(max(left, 0))
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def iter_blocks(x, block_samples: int) -> Iterator[tuple[int, object]]:
    """Yield (start_sample, block) for a float32 mono array; the last block may be short."""
    n = len(x)
    i = 0
    while i < n:
        yield i, x[i : i + block_samples]
        i += block_samples
