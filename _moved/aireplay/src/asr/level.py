"""The 10 Hz level event -- `specs/02-asr.md` section 7.

Why this module exists, measured: the level the sibling worker publishes today is `peak`, a
RUN MAXIMUM (only ever raised -- three consecutive ticks print the identical 0.554093 while
`rms` drifts, docs/research/12-audio-level-contract.md:14), published on STDERR at 0.1 Hz
(:21) and dropped in the shell (:25-31). A wave drawn from it is a monotone line that only
rises -- the invented wave the owner forbade.

This emitter is the honest datum: a WINDOWED linear sample peak per 100 ms of AUDIO (10 Hz,
:20,23), with instant attack and an exponential release (150-250 ms band, :45), a 128-point
history (:44), and ONE compact JSON object per event on the channel it is given.

The clock is the AUDIO clock, not wall time: a pass that runs 8x real time emits the same
number of events as a live one, and the wave of a 2-hour recording has 72 000 points either
way.
"""

from __future__ import annotations

import json
import math
from collections import deque
from typing import Callable

from .constants import (
    BLOCK_MS,
    LEVEL_EVENT_TYPE,
    LEVEL_HISTORY,
    RELEASE_TAU_S,
    SAMPLE_RATE,
)

__all__ = ["LevelEmitter", "compact_json", "LEVEL_EVENT_BYTES_TYPICAL"]

# A typical event, measured by the module's own test: {"type":"level","a":12.3,"p":0.1234,
# "r":0.01234,"e":0.1234} is 62 bytes. The budget is LEVEL_MAX_EVENT_BYTES.
LEVEL_EVENT_BYTES_TYPICAL = 62


def compact_json(obj: dict) -> str:
    """One line, no spaces -- the channel also carries captions, so bytes are a budget."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class LevelEmitter:
    """Feed PCM blocks; get one compact level event per BLOCK_MS of audio.

    `sink` is called with the event DICT (the caller owns the encoding: the CLI writes
    compact JSON on stdout, a test can keep the dicts).
    """

    def __init__(
        self,
        sink: Callable[[dict], None] | None = None,
        sample_rate: int = SAMPLE_RATE,
        block_ms: int = BLOCK_MS,
        release_tau_s: float = RELEASE_TAU_S,
        history: int = LEVEL_HISTORY,
        audio_offset_s: float = 0.0,
    ):
        self.sample_rate = sample_rate
        self.block_samples = int(round(sample_rate * block_ms / 1000.0))
        self.block_s = self.block_samples / float(sample_rate)
        self.release_tau_s = release_tau_s
        # instant attack, exponential release: env <- max(peak, env * exp(-dt/tau))
        self._release = math.exp(-self.block_s / release_tau_s) if release_tau_s > 0 else 0.0
        self._sink = sink
        self._buf = []
        self._n = 0  # samples buffered
        self._emitted = 0
        self._audio_s = float(audio_offset_s)
        self.envelope = 0.0
        self.peak_max = 0.0
        self.history = deque(maxlen=history)

    # -- feeding ---------------------------------------------------------------------
    def feed(self, block) -> None:
        """Feed a float32 mono block of any length; emits as windows complete."""
        pos = 0
        n = len(block)
        while pos < n:
            take = min(self.block_samples - self._n, n - pos)
            self._buf.append(block[pos : pos + take])
            self._n += take
            pos += take
            if self._n == self.block_samples:
                self._flush()

    def close(self) -> None:
        """Emit a final short window if any audio is buffered (never invents one if empty)."""
        if self._n:
            self._flush()

    # -- the window ------------------------------------------------------------------
    def _flush(self) -> None:
        import numpy as np

        window = self._buf[0] if len(self._buf) == 1 else np.concatenate(self._buf)
        self._buf = []
        self._n = 0
        if len(window) == 0:
            return
        peak = float(np.abs(window).max())  # linear sample peak 0..1 -- 12-audio-level-contract.md:12
        rms = float(np.sqrt(float((window.astype(np.float64) ** 2).mean())))
        self.envelope = max(peak, self.envelope * self._release)
        self.peak_max = max(self.peak_max, peak)
        self._audio_s += len(window) / float(self.sample_rate)
        self._emitted += 1
        self.history.append(self.envelope)
        if self._sink is not None:
            self._sink(
                {
                    "type": LEVEL_EVENT_TYPE,
                    "a": round(self._audio_s, 3),
                    "p": round(peak, 4),
                    "r": round(rms, 5),
                    "e": round(self.envelope, 4),
                }
            )

    # -- reporting -------------------------------------------------------------------
    @property
    def n_events(self) -> int:
        return self._emitted

    @property
    def audio_s(self) -> float:
        return self._audio_s

    @property
    def hz(self) -> float:
        return 1.0 / self.block_s if self.block_s else 0.0

    def summary(self) -> dict:
        return {
            "n_events": self._emitted,
            "hz": round(self.hz, 3),
            "block_ms": int(round(self.block_s * 1000)),
            "peak": round(self.peak_max, 4),
            "release_tau_s": self.release_tau_s,
            "history": self.history.maxlen,
            "history_points": len(self.history),
        }


def events_from_array(x, sample_rate: int = SAMPLE_RATE, **kw) -> list[dict]:
    """Convenience for tests: the events a whole array produces."""
    out: list[dict] = []
    em = LevelEmitter(sink=out.append, sample_rate=sample_rate, **kw)
    em.feed(x)
    em.close()
    return out
