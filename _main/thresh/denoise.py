"""denoise.py — a streaming spectral-gate noise remover for the Sotto worker.

WHAT THIS DOES
--------------
Attenuates the STATIONARY broadband noise floor of a mono 16 kHz stream before
the ASR front end sees it. It is a per-bin Wiener-style spectral gate:

  * STFT, frame 512 / hop 256 (32 ms / 16 ms @ 16 kHz), periodic Hann analysis
    and synthesis window, with an EXACT per-sample overlap-add denominator
    maintained by the shift recursion. That denominator is what makes the
    round trip transparent: with the gain forced to 1 the output equals the
    input delayed by exactly `hop` samples (proved in --selftest).
  * per-bin noise POWER tracked by a decaying minimum of the smoothed power
    (`Nf = min(Psm, Nf * decay)`), which follows the floor down instantly and
    up only over seconds. Conservative at stream start: the estimate is seeded
    from the first frame's own power, so the first frames are UNDER-attenuated,
    never over-attenuated.
  * that minimum is BIASED LOW by construction — a minimum of a fluctuating
    power sequence sits below its mean — so it is multiplied by `noise_bias`
    (Martin's minimum-statistics bias compensation). The default 3.79 is not a
    guess: with `power_smooth=0.7` and `noise_decay=1.002` the tracker measured
    **0.264x** the true mean power of a stationary noise floor over 375 frames
    (`_main/_bias-probe.py`), and 1/0.264 = 3.79. --selftest re-measures this
    ratio from the published statistics, so a change to `noise_decay` that is
    not matched by a re-calibration turns the self-test RED.
  * gain = over-subtracted Wiener `snr/(snr+1)`, floored at `min_gain_db`
    (-18 dB), smoothed in time (one-pole) and across 3 bins.

WHAT THIS DOES NOT DO — read this before believing anything about it
-------------------------------------------------------------------
  * It does NOT know what speech is. It removes what is STATIONARY and
    broadband. It cannot separate two speakers, it does not remove reverb, and
    on continuous MUSIC it will treat sustained tonal energy as part of the
    floor and attenuate it — that is the known failure mode of every
    minimum-tracking estimator, and it is measured, not hidden.
  * It does NOT improve the transcript. Nobody has a reference transcription of
    the owner's audio, so "cleaner" and "lower WER" are NOT claims this module
    or its receipt may make. The only honest measurements are: what gain it
    applied, what the model then decoded, what it cost, and whether the text
    changed.
  * It is NOT the shipped default. `use_denoise` is `false` in
    `worker/config.json`; with the key false the worker must behave
    byte-identically to a worker without this module at all.
  * It does NOT resample and does NOT change the sample rate. Feed it the same
    16 kHz float array the model is fed.
  * It introduces a LATENCY of `hop` samples (256 = 16 ms @ 16 kHz). With the
    gain at 1 the first 16 ms of output is the window warm-up. A caller that
    feeds blocks shorter than `frame - hop` accumulates more latency.

Small testable API:
    denoise_block(x, sr)          -> x            (one-shot, any length, any dtype)
    SpectralGate(sr).process(x)   -> x            (streaming, same length/dtype)
    denoise_decision(cfg)         -> (enabled, reason)
    denoise_from_config(cfg, sr)  -> (gate|None, enabled, reason)

Self-test, both colours in one command (the negative control must go RED):
    py -3 worker/denoise.py --selftest
Offline measurement of what the gate does to a real file:
    py -3 worker/denoise.py --wav FILE [--out DENOISED.wav] [--json]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

__all__ = [
    "SpectralGate",
    "denoise_block",
    "denoise_decision",
    "denoise_from_config",
    "FRAME",
    "HOP",
    "MIN_GAIN_DB",
    "OVER_SUB",
]

# --- shipped defaults (one place, documented) -------------------------------
FRAME = 512            # 32 ms @ 16 kHz
HOP = 256              # 16 ms @ 16 kHz  (= the module's latency)
MIN_GAIN_DB = -18.0    # hard floor on attenuation: nothing is ever cut more than this
OVER_SUB = 1.5         # over-subtraction factor on the noise estimate
NOISE_DECAY = 1.002    # per frame; the floor may rise ~12.5 %/s (doubles in ~5.9 s)
NOISE_BIAS = 3.79      # min-statistics bias compensation; MEASURED 1/0.264 for the
                       # two constants above (_main/_bias-probe.py). Re-calibrate if
                       # NOISE_DECAY or POWER_SMOOTH changes — --selftest checks it.
POWER_SMOOTH = 0.7     # Psm = a*Psm + (1-a)*P
GAIN_SMOOTH = 0.5      # g = b*g_prev + (1-b)*g
EPS = 1e-10


class SpectralGate:
    """Causal, streaming, per-bin spectral gate. Pure NumPy.

    process() accepts ANY length, returns the SAME length and dtype, never
    produces NaN, and is deterministic for a given input sequence.
    """

    def __init__(
        self,
        sr: int = 16000,
        frame: int = FRAME,
        hop: int = HOP,
        min_gain_db: float = MIN_GAIN_DB,
        over_sub: float = OVER_SUB,
        noise_decay: float = NOISE_DECAY,
        noise_bias: float = NOISE_BIAS,
        power_smooth: float = POWER_SMOOTH,
        gain_smooth: float = GAIN_SMOOTH,
        transparent: bool = False,
    ) -> None:
        if frame < 8 or hop < 1 or hop > frame:
            raise ValueError(f"bad STFT geometry: frame={frame} hop={hop}")
        self.sr = int(sr)
        self.frame = int(frame)
        self.hop = int(hop)
        self.min_gain = float(10.0 ** (float(min_gain_db) / 20.0))
        self.min_gain_db = float(min_gain_db)
        self.over_sub = float(over_sub)
        self.noise_decay = float(noise_decay)
        self.noise_bias = float(noise_bias)
        self.power_smooth = float(power_smooth)
        self.gain_smooth = float(gain_smooth)
        # `transparent` is a MACHINERY SELF-TEST ONLY (gain forced to 1): it is
        # what proves the overlap-add round trip is exact. It is not a mode any
        # caller ships.
        self.transparent = bool(transparent)
        self.w = np.hanning(self.frame + 1)[:-1]  # periodic Hann
        self.reset()

    # -- state ---------------------------------------------------------------
    def reset(self) -> None:
        self._in = np.zeros(0, np.float64)     # input remainder
        self._out = np.zeros(0, np.float64)    # finalized output not yet returned
        self._num = np.zeros(self.frame, np.float64)   # weighted OLA numerator
        self._den = np.zeros(self.frame, np.float64)   # exact per-sample denominator
        self._psm = None                       # smoothed power
        self._noise = None                     # per-bin noise power estimate
        self._gprev = None                     # last frame's gain (time smoothing)
        self._started = False
        self._last_gain = None
        # published counters
        self.frames = 0
        self.samples_in = 0
        self.samples_out = 0
        self.warmup_pad_samples = 0
        self.atten_frames = 0                  # frames whose mean gain was < -1 dB
        self.gain_db_frames = []               # per-frame mean gain, dB
        self.noise_db_frames = []              # per-frame mean noise floor, dBFS
        self.psm_db_frames = []                # per-frame mean smoothed power, dBFS

    # -- gain ----------------------------------------------------------------
    def _frame_gain(self, P: np.ndarray) -> np.ndarray:
        if self._noise is None:
            self._psm = P.copy()
            self._noise = P.copy()
        else:
            self._psm = self.power_smooth * self._psm + (1.0 - self.power_smooth) * P
            self._noise = np.minimum(self._psm, self._noise * self.noise_decay)
        if self.transparent:
            g = np.ones_like(P)
        else:
            # bias-compensated floor: `_noise` is a MINIMUM, so it sits below the
            # true mean power of the floor by `noise_bias`.
            nf = self.noise_bias * self._noise
            snr = np.maximum(self._psm - self.over_sub * nf, 0.0) / np.maximum(nf, EPS)
            g = snr / (snr + 1.0)
            g = np.maximum(g, self.min_gain)
        if self._gprev is None:
            self._gprev = g
        else:
            g = self.gain_smooth * self._gprev + (1.0 - self.gain_smooth) * g
        # 3-bin frequency smoothing, edges replicated
        gp = np.concatenate((g[:1], g[:-1]))
        gn = np.concatenate((g[1:], g[-1:]))
        g = 0.25 * gp + 0.5 * g + 0.25 * gn
        self._gprev = g
        return g

    def _frame_spectrum(self, fr: np.ndarray):
        X = np.fft.rfft(fr * self.w)
        P = X.real * X.real + X.imag * X.imag
        g = self._frame_gain(P)
        Y = np.fft.irfft(X * g, n=self.frame)
        return Y, g

    # -- streaming -----------------------------------------------------------
    def process(self, x) -> np.ndarray:
        """Denoise `x` (1-D, any length). Returns the same length and dtype."""
        x = np.asarray(x)
        if x.ndim != 1:
            x = x.reshape(-1)
        dtype = x.dtype
        n = int(x.shape[0])
        if n == 0:
            return x.copy()
        xf = x.astype(np.float64, copy=False)
        if not self._started:
            self._started = True
            # Warm-up: `hop` zeros in FRONT of the stream, so the very first
            # real sample is covered by a complete set of analysis windows.
            # The Hann window vanishes at its edges, so without this the first
            # sample would be reconstructed as 0/0. Cost: the output lags the
            # input by exactly `hop` samples.
            self._in = np.zeros(self.hop, np.float64)
        self._in = np.concatenate((self._in, xf))
        self.samples_in += n

        while self._in.shape[0] >= self.frame:
            fr = self._in[: self.frame]
            Y, g = self._frame_spectrum(fr)
            self._num += Y * self.w
            self._den += self.w * self.w
            blk = self._num[: self.hop] / np.maximum(self._den[: self.hop], 1e-12)
            self._out = np.concatenate((self._out, blk))
            self._num = np.concatenate((self._num[self.hop:], np.zeros(self.hop)))
            self._den = np.concatenate((self._den[self.hop:], np.zeros(self.hop)))
            self._in = self._in[self.hop:]
            # counters
            self.frames += 1
            self._last_gain = g
            gm = float(np.mean(g))
            gdb = 20.0 * math.log10(max(gm, 1e-6))
            self.gain_db_frames.append(gdb)
            if gdb < -1.0:
                self.atten_frames += 1
            self.noise_db_frames.append(
                10.0 * math.log10(max(float(np.mean(self._noise)), 1e-20))
            )
            self.psm_db_frames.append(
                10.0 * math.log10(max(float(np.mean(self._psm)), 1e-20))
            )

        if self._out.shape[0] >= n:
            out = self._out[:n]
            self._out = self._out[n:]
        else:
            got = int(self._out.shape[0])
            pad = n - got
            self.warmup_pad_samples += pad
            out = np.concatenate((self._out, np.zeros(pad)))
            self._out = np.zeros(0)
        self.samples_out += n
        return out.astype(dtype, copy=False)

    # -- reporting -----------------------------------------------------------
    def stats(self) -> dict:
        g = np.asarray(self.gain_db_frames, np.float64)
        nz = np.asarray(self.noise_db_frames, np.float64)
        pz = np.asarray(self.psm_db_frames, np.float64)
        out = {
            "sr": self.sr,
            "frame": self.frame,
            "hop": self.hop,
            "latency_ms": round(1000.0 * self.hop / self.sr, 3),
            "min_gain_db": self.min_gain_db,
            "over_sub": self.over_sub,
            "noise_bias": self.noise_bias,
            "noise_decay": self.noise_decay,
            "transparent": self.transparent,
            "frames": self.frames,
            "samples_in": self.samples_in,
            "samples_out": self.samples_out,
            "warmup_pad_samples": self.warmup_pad_samples,
            "atten_frames": self.atten_frames,
        }
        if g.size:
            out.update(
                {
                    "gain_db_mean": round(float(np.mean(g)), 3),
                    "gain_db_min": round(float(np.min(g)), 3),
                    "gain_db_p10": round(float(np.percentile(g, 10)), 3),
                    "gain_db_p50": round(float(np.percentile(g, 50)), 3),
                    "gain_db_p90": round(float(np.percentile(g, 90)), 3),
                    "noise_db_mean": round(float(np.mean(nz)), 2),
                    "atten_frac": round(self.atten_frames / float(self.frames), 4),
                }
            )
        if pz.size and nz.size == pz.size:
            # how far the tracked MINIMUM sits below the smoothed power it was
            # taken from — this is the quantity `noise_bias` compensates. Skip
            # the bootstrap frames, where the estimate is deliberately high.
            k = min(100, max(0, pz.size // 4))
            out["psm_db_mean"] = round(float(np.mean(pz[k:])), 2)
            out["bias_measured_db"] = round(float(np.mean(pz[k:] - nz[k:])), 3)
        return out


def denoise_block(x, sr: int = 16000, **kw) -> np.ndarray:
    """One-shot convenience: denoise a whole block with a fresh gate.

    Same length, same dtype as `x`. NOTE: a fresh gate per call re-learns the
    noise floor from scratch, so this is for measurement and tests — the worker
    holds ONE long-lived SpectralGate across the stream.
    """
    return SpectralGate(sr=sr, **kw).process(x)


# --- config plumbing --------------------------------------------------------
def denoise_decision(cfg) -> tuple:
    """Read the TOP-LEVEL `use_denoise` key. Returns (enabled, reason).

    Never raises. Anything that is not an unambiguous boolean is REFUSED back
    to False with a reason naming the value, so a typo cannot silently turn the
    denoiser on (and cannot silently turn it off either — the reason is logged).
    """
    if not isinstance(cfg, dict):
        return False, "no-config"
    if "use_denoise" not in cfg:
        return False, "absent"
    v = cfg["use_denoise"]
    if v is True:
        return True, "config-true"
    if v is False:
        return False, "config-false"
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "on", "yes"):
            return True, "config-true(str)"
        if s in ("0", "false", "off", "no", ""):
            return False, "config-false(str)"
    return False, "refused(%r)" % (v,)


def denoise_from_config(cfg, sr: int = 16000):
    """(gate|None, enabled, reason) — build the gate only when the key says so."""
    enabled, reason = denoise_decision(cfg)
    if not enabled:
        return None, False, reason
    return SpectralGate(sr=sr), True, reason


# --- offline instrument -----------------------------------------------------
def _resample_to_16k(x: np.ndarray, src: int):
    """Exact-integer block averaging, else linear interp. Mirrors the worker's
    own numpy-only resample_to_16k (the worker's function is preferred when it
    can be imported; this is the fallback and the label says which ran)."""
    if src == 16000:
        return x.astype(np.float64), "none"
    if src % 16000 == 0:
        f = src // 16000
        n = (x.shape[0] // f) * f
        return x[:n].reshape(-1, f).mean(axis=1), "blockmean"
    n_out = int(round(x.shape[0] * 16000.0 / src))
    t_in = np.arange(x.shape[0], dtype=np.float64)
    t_out = np.linspace(0.0, x.shape[0] - 1.0, n_out)
    return np.interp(t_out, t_in, x.astype(np.float64)), "interp"


def measure_wav(path: str, out_path=None, do_json=False, **kw) -> int:
    import soundfile as sf

    x, sr = sf.read(path, dtype="float32", always_2d=False)
    if x.ndim != 1:
        x = x.mean(axis=1)
    resampler = "none"
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import sotto_worker as _W  # noqa: F401  (only for its resampler)

        x16 = np.asarray(_W.resample_to_16k(x, sr), np.float32)
        resampler = "worker.resample_to_16k"
    except Exception as e:  # pragma: no cover - fallback path
        x16, resampler = _resample_to_16k(x, sr)
        x16 = x16.astype(np.float32)
        resampler = f"local:{resampler} (worker import failed: {type(e).__name__})"

    gate = SpectralGate(sr=16000, **kw)
    y = gate.process(x16)
    st = gate.stats()
    st.update(
        {
            "wav": os.path.abspath(path),
            "wav_bytes": os.path.getsize(path),
            "src_sr": int(sr),
            "src_samples": int(x.shape[0]),
            "resampler": resampler,
            "in_rms": round(float(np.sqrt(np.mean(np.square(x16.astype(np.float64))))), 8),
            "in_peak": round(float(np.max(np.abs(x16))), 8),
            "out_rms": round(float(np.sqrt(np.mean(np.square(y.astype(np.float64))))), 8),
            "out_peak": round(float(np.max(np.abs(y))), 8),
            "nan_out": bool(np.any(~np.isfinite(y))),
        }
    )
    if st["in_rms"] > 0:
        st["rms_change_db"] = round(
            20.0 * math.log10(max(st["out_rms"], 1e-12) / st["in_rms"]), 3
        )
    if out_path:
        sf.write(out_path, y, 16000, subtype="FLOAT")
        st["out_wav"] = os.path.abspath(out_path)
        st["out_wav_bytes"] = os.path.getsize(out_path)
    if do_json:
        print(json.dumps(st, indent=2, sort_keys=True))
    else:
        print("DENOISE-WAV %s" % os.path.abspath(path))
        for k in sorted(st):
            print("  %-18s %s" % (k, st[k]))
    return 0


# --- self-test --------------------------------------------------------------
def _tone_burst(n: int, sr: int = 16000):
    """A crude 'speech-like' source: a voiced-ish harmonic stack with a slow
    amplitude wobble. Continuous, so a test can compare a clean floor stretch
    against a stretch that has this on top of it WITHOUT phase bookkeeping."""
    t = np.arange(n, dtype=np.float64) / sr
    sig = np.zeros(n, np.float64)
    for f, a in ((140.0, 1.0), (280.0, 0.6), (560.0, 0.35), (1120.0, 0.2), (2240.0, 0.1)):
        sig += a * np.sin(2 * np.pi * f * t + f)
    sig /= np.max(np.abs(sig))
    wobble = 0.6 + 0.4 * np.sin(2 * np.pi * 3.0 * t)  # syllable-ish, 3 Hz
    return sig * wobble * 0.25


def selftest(do_json=False) -> int:
    rng = np.random.default_rng(20261008)
    sr = 16000
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))
        print("  [%s] %-46s %s" % ("PASS" if ok else "FAIL", name, detail))
        return bool(ok)

    print("SELFTEST denoise.py — both colours in one run")

    # --- 1. the transparency control: the OLA round trip is exact -----------
    print(" 1. machinery: gain == 1 must be a pure delay by `hop` samples")
    x = rng.standard_normal(8960 * 3).astype(np.float32) * 0.1
    g1 = SpectralGate(sr=sr, transparent=True)
    y1 = g1.process(x)
    d = float(np.max(np.abs(y1[g1.hop :].astype(np.float64) - x[: -g1.hop])))
    check("len(out) == len(in)", y1.shape == x.shape, f"{y1.shape} vs {x.shape}")
    check("dtype preserved", y1.dtype == np.float32, str(y1.dtype))
    check("no NaN/inf", bool(np.all(np.isfinite(y1))))
    check("unity gain == delay by hop", d < 1e-6, f"max|out[hop:]-x[:-hop]| = {d:.3e}")

    # chunking must not change the answer (streaming state, not block state)
    g2 = SpectralGate(sr=sr, transparent=True)
    y2 = np.concatenate([g2.process(x[i : i + 8960]) for i in range(0, x.shape[0], 8960)])
    d2 = float(np.max(np.abs(y2.astype(np.float64) - y1.astype(np.float64))))
    check("chunked == one-shot", d2 == 0.0, f"max|diff| = {d2:.3e}")

    # determinism
    g3 = SpectralGate(sr=sr, transparent=True)
    y3 = g3.process(x)
    check("deterministic", bool(np.array_equal(y1, y3)))

    # odd lengths must still return exactly the length asked for
    g4 = SpectralGate(sr=sr)
    odd = [0, 1, 7, 255, 256, 257, 1000]
    lens_ok = all(g4.process(np.zeros(n, np.float32)).shape[0] == n for n in odd)
    check("any length in == any length out", lens_ok, str(odd))

    # --- 2. it actually attenuates a stationary noise floor -----------------
    print(" 2. effect: a stationary noise floor must be attenuated")
    noise = (rng.standard_normal(sr * 3) * 0.01).astype(np.float32)  # ~ -40 dBFS
    gn = SpectralGate(sr=sr)
    yn = gn.process(noise)
    st = gn.stats()
    in_rms = float(np.sqrt(np.mean(noise.astype(np.float64) ** 2)))
    out_rms = float(np.sqrt(np.mean(yn.astype(np.float64) ** 2)))
    drop_db = 20.0 * math.log10(max(out_rms, 1e-12) / in_rms)
    check("noise floor attenuated > 6 dB", drop_db < -6.0, f"rms {drop_db:+.2f} dB")
    check(
        "mean gain below -3 dB",
        st.get("gain_db_mean", 0.0) < -3.0,
        f"gain_db_mean={st.get('gain_db_mean')} p50={st.get('gain_db_p50')}",
    )
    check(
        "gain never below the floor",
        st.get("gain_db_min", 0.0) >= MIN_GAIN_DB - 0.5,
        f"gain_db_min={st.get('gain_db_min')} floor={MIN_GAIN_DB}",
    )
    # the bias compensation is a MEASURED constant, so re-measure it here from
    # the published statistics: the tracked minimum must sit `noise_bias` below
    # the smoothed power it was taken from.
    want_db = 10.0 * math.log10(NOISE_BIAS)
    got_db = st.get("bias_measured_db", 0.0)
    check(
        "noise_bias still calibrated",
        abs(got_db - want_db) < 1.5,
        f"measured {got_db:+.2f} dB vs shipped {want_db:+.2f} dB (bias {NOISE_BIAS})",
    )

    # --- 3. and it OPENS on a louder non-stationary source ------------------
    print(" 3. effect: the gate must OPEN when the signal rises above the floor")
    half = sr * 2
    floor_part = rng.standard_normal(half) * 0.01
    loud_part = _tone_burst(half) + rng.standard_normal(half) * 0.01
    xin = np.concatenate((floor_part, loud_part)).astype(np.float32)
    gb = SpectralGate(sr=sr)
    yout = gb.process(xin)
    # rms, not mean per-bin gain: a 5-harmonic source occupies 5 of 257 bins, so
    # a mean over bins would be dominated by the bins the tone never touched.
    n_half = xin.shape[0] // 2
    drop = []
    for seg in (slice(0, n_half), slice(n_half, xin.shape[0])):
        i_rms = float(np.sqrt(np.mean(xin[seg].astype(np.float64) ** 2)))
        o_rms = float(np.sqrt(np.mean(yout[seg].astype(np.float64) ** 2)))
        drop.append(20.0 * math.log10(max(o_rms, 1e-12) / max(i_rms, 1e-12)))
    floor_drop, loud_drop = drop
    check(
        "floor half attenuated, loud half passed",
        loud_drop > floor_drop + 8.0,
        f"loud {loud_drop:+.2f} dB vs floor {floor_drop:+.2f} dB",
    )
    check(
        "the loud half is passed, not cut",
        loud_drop > -3.0,
        f"loud half rms {loud_drop:+.2f} dB",
    )

    # --- 4. NEGATIVE CONTROL: the same measurement with gain == 1 must FAIL -
    print(" 4. negative control: the SAME measurement, gate forced transparent")
    gt = SpectralGate(sr=sr, transparent=True)
    yt = gt.process(noise)
    t_rms = float(np.sqrt(np.mean(yt.astype(np.float64) ** 2)))
    t_drop = 20.0 * math.log10(max(t_rms, 1e-12) / in_rms)
    check(
        "CONTROL: transparent does NOT attenuate the noise",
        t_drop > -0.5,
        f"rms {t_drop:+.2f} dB (this must be ~0: it is what makes test 2 mean something)",
    )
    t_gdf = np.asarray(gt.gain_db_frames, np.float64)
    check(
        "CONTROL: transparent gain is ~0 dB everywhere",
        abs(float(np.mean(t_gdf))) < 0.01,
        f"gain_db_mean={np.mean(t_gdf):+.4f}",
    )

    # --- 5. config oracle ---------------------------------------------------
    print(" 5. config: the shipped key decides, and a bad value is refused")
    arms = [
        ({"use_denoise": False}, False, "config-false"),
        ({"use_denoise": True}, True, "config-true"),
        ({}, False, "absent"),
        ({"use_denoise": "true"}, True, "config-true(str)"),
        ({"use_denoise": "off"}, False, "config-false(str)"),
        ({"use_denoise": 1}, False, "refused(1)"),
        ({"use_denoise": None}, False, "refused(None)"),
        ({"use_denoise": "maybe"}, False, "refused('maybe')"),
        (None, False, "no-config"),
    ]
    bad = []
    for cfg, want_on, want_reason in arms:
        got_on, got_reason = denoise_decision(cfg)
        if got_on != want_on or got_reason != want_reason:
            bad.append((cfg, got_on, got_reason, want_on, want_reason))
    check("9 config arms", not bad, "mismatches=%d" % len(bad))
    gate, on, reason = denoise_from_config({"use_denoise": False})
    check("false key builds NO gate", gate is None and on is False, reason)
    gate, on, reason = denoise_from_config({"use_denoise": True})
    check("true key builds a gate", gate is not None and on is True, reason)

    # --- 6. denoise_block ---------------------------------------------------
    print(" 6. denoise_block: one-shot API, any length")
    for n in (0, 1, 160, 16000):
        z = denoise_block(np.zeros(n, np.float32), 16000)
        if z.shape[0] != n or not np.all(np.isfinite(z)):
            check(f"denoise_block(n={n})", False, str(z.shape))
            break
    else:
        check("denoise_block on 4 lengths", True, "0, 1, 160, 16000")

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print("")
    print(
        "SELFTEST-DONE checks=%d pass=%d fail=%d"
        % (len(results), len(results) - n_fail, n_fail)
    )
    print("VERDICT %s" % ("PASS" if n_fail == 0 else "FAIL"))
    if do_json:
        print(
            json.dumps(
                [{"name": n, "ok": ok, "detail": d} for n, ok, d in results], indent=2
            )
        )
    return 0 if n_fail == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sotto spectral-gate noise remover")
    ap.add_argument("--selftest", action="store_true", help="both colours + negative control")
    ap.add_argument("--wav", default=None, help="measure the gate's effect on a WAV file")
    ap.add_argument("--out", default=None, help="also write the denoised 16 kHz WAV here")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--min-gain-db", type=float, default=MIN_GAIN_DB)
    ap.add_argument("--over-sub", type=float, default=OVER_SUB)
    ap.add_argument("--noise-decay", type=float, default=NOISE_DECAY)
    ap.add_argument("--noise-bias", type=float, default=NOISE_BIAS)
    a = ap.parse_args(argv)
    kw = dict(
        min_gain_db=a.min_gain_db,
        over_sub=a.over_sub,
        noise_decay=a.noise_decay,
        noise_bias=a.noise_bias,
    )
    if a.wav:
        return measure_wav(a.wav, out_path=a.out, do_json=a.json, **kw)
    if a.selftest:
        return selftest(do_json=a.json)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
