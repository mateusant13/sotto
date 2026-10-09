"""highlights.py -- the auto-highlight detector: score a moment, refuse the rest.

================================================================================
WHAT THIS IS, AND WHY IT IS BUILT ON FRAMES
================================================================================

ShadowPlay's second signature move: the app watches the stream and saves the clip
itself when something worth keeping happens, instead of waiting for a hotkey.

The previous design for this feature is `specs/07-highlights.md`, which existed at
HEAD and was DELETED from the working tree (440 lines, sha256
4CF88A02B0D733601D3849ABD07DA1E64D1E4F79DEED9D3731A32CDA68214F8C -- byte-identical
to `_main/_deleted-blob-backup/783d0f475998_specs__07-highlights.md`).  It scored
AUDIO, and it was reviewed as RED: `receipts/review-L15.md` S1 (CRITICAL) measured
a footstep-shaped corpus firing the rule 36/36, and named the dynamic-range gate "a
silence detector wearing a highlight detector's clothes".

This implementation keeps the good half of that design -- an explicit scoring rule,
an explicit refractory, a loud refusal vocabulary, a gate with both colours -- and
changes the SIGNAL, for a reason that is measured on this box and not chosen:

    27 of 27 capture outputs carry NO audio stream (`receipts/review-L15.md` S4,
    POPULATION=28 clips, WITH_AUDIO=1, and that one is an ffmpeg synthetic).
    Video is 27 of 27.  A detector built on the signal that is actually present is
    buildable today; one built on the signal that is absent is a dependency.

================================================================================
THE RULE, AND WHY EACH HALF IS THERE
================================================================================

A frame change has a size (`diff`) and a CONTEXT (what that scene normally does).
Two numbers, because one is not enough, and the reason is measured, not stylistic:

  * `diff` ALONE cannot tell "a spike happened" from "this clip is busy": in the
    45-clip population below, the QUIET clips peak at diff<=0.0322 and the BUSY
    clips sit at p50>=0.1117 -- 3.5x apart -- but a *sustained* busy clip and a
    *quiet* clip have the SAME max/p50 shape.  See ARM Q/ARM B in the receipt.

  * `diff / baseline` ALONE cannot either, and this is the trap the dead spec fell
    into: a ratio rewards impulsiveness.  Measured on this host, the per-clip
    max/p50 of SUSTAINED activity reaches 3.02 -- see `HIGH_RISE_CEILING_SUSTAINED`
    -- so any rise threshold under that fires all day on footage that never stops
    moving.

So the rule needs the third thing, which is the actual definition of a moment:

  * A moment is a BURST: change that spikes and comes BACK.  Sustained activity is
    not a moment, it is a scene.  `BURST_MAX_S` says so, and it is the arm the
    dead spec's rule lacked.

Every threshold below carries its provenance in PROVENANCE.  A number nothing
measured is a bug in this file, same rule the rest of this repo runs on.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Iterable

__all__ = [
    "HighlightConfig",
    "Highlight",
    "HighlightDetector",
    "detect_series",
    "PROVENANCE",
    "ABS_FLOOR_MEASURED",
    "HIGH_RISE_CEILING_SUSTAINED",
    "HIGH_RISE_QUIET",
    "DEFAULTS_CHOSEN_WITHOUT_DATA",
]

# ==================================================================================
# MEASURED ON THIS HOST.  Every number here has a population and a window; see
# `_main/_hl-frame-stats-probe.py`, `_main/_hl-frame-stats-probe.log` and the
# receipt.  Change the corpus and these stop being true.
# ==================================================================================

#: POPULATION = every *.mp4/*.mkv/*.mov > 200 KB under `_main/` (recursive), one
#: ffmpeg decode each, no sampling.  N = 45 clips / 987.7 s / 9832 frame-diffs.
#: WINDOW = one run, 2026-10-08, all files present on disk.
#: The 10 clips of the quiet class peak at diff <= 0.03223; the busiest clip in the
#: population bottoms out at p50 = 0.11177.  ABS_FLOOR sits inside that empty band,
#: at ~2x the quiet ceiling, because a floor placed exactly ON an observed maximum
#: is a floor that one noisy frame crosses.
ABS_FLOOR_MEASURED = 0.065

#: MEASURED on this host under the DETECTOR'S OWN definition: the largest
#: `diff / trailing-median` reached anywhere in a clip of sustained activity.
#: POPULATION = the 35 clips whose per-clip p50 >= 0.05, 660.2 s, one decode each.
#:
#: CORRECTION, and it matters: an earlier pass of this lane quoted 3.02 here.
#: That number is `max / p50(whole clip)`, a DIFFERENT quantity, and the gate
#: caught it: with the threshold set from it, lowering the threshold to 3.03
#: changed nothing at all on the population.  The honest figure for the
#: expression the rule actually evaluates is 3.170.
HIGH_RISE_CEILING_SUSTAINED = 3.17

#: MEASURED, and it is the most important sentence in this file:
#:
#:     THE RISE ALONE DOES NOT SEPARATE QUIET FROM BUSY.
#:
#: The quiet clips reach a rise of 3.601.  The busy clips reach 3.170.  Quiet is
#: HIGHER.  POPULATION = all 45 clips / 983.2 s, both classes, one decode each.
#: A quiet scene has a tiny baseline, so any small wobble divides by almost
#: nothing and produces a huge ratio -- the ratio REWARDS impulsiveness, exactly
#: as `receipts/review-L15.md` S1 measured for the deleted spec's audio rule.
#:
#: CONSEQUENCE, and it decides the whole rule: the rise may not be the gate that
#: refuses quiet footage.  `abs_floor` is, and the MEASURED reason it can be is
#: that the two classes do not overlap in absolute terms -- quiet peaks at
#: diff = 0.03223, busy bottoms out at p50 = 0.11177.  The gate proves which
#: guard does the work by opening the other one (ARM M1).
HIGH_RISE_QUIET = 3.601

#: Chosen without data, and said so.  There is no labelled gameplay corpus on this
#: box (N = 0), so there is nothing to fit these against.
DEFAULTS_CHOSEN_WITHOUT_DATA = (
    "cooldown_s", "lookback_s", "confirm_s",
    "burst_max_s", "recovery_ratio", "baseline_floor",
    "pre_roll_s", "post_roll_s",
)

PROVENANCE: dict[str, str] = {
    "abs_floor": (
        f"MEASURED on this host. POPULATION = 45 clips / 987.7 s under _main/ "
        f"(one decode each, no sampling); quiet-class ceiling 0.03223, busy-class "
        f"floor 0.11177. Default {ABS_FLOOR_MEASURED} sits in the gap at ~2x the "
        f"ceiling. NOT transferable to another resolution, fps or content without "
        f"re-running _main/_hl-frame-stats-probe.py."),
    "rise_threshold": (
        f"DERIVED FROM A MEASURED GAP, and the gap is narrow, so read it twice. "
        f"Upper edge: the sustained-activity ceiling, "
        f"{HIGH_RISE_CEILING_SUSTAINED} (MEASURED, 35 clips / 660.2 s -- a threshold "
        f"at or under this fires all day on footage that never stops moving). "
        f"Lower edge: the rise of a real full-frame flash over busy footage, 3.36 "
        f"(MEASURED, N = 1; the flash is SYNTHETIC, the frames around it are real "
        f"capture).  The default 3.25 sits in a gap 0.19 wide.  THIS IS THE MOST "
        f"FRAGILE NUMBER IN THIS FILE: one side is N=35, the other is N=1.  It was "
        f"3.5 until the gate measured that 3.5 REFUSES the flash this feature exists "
        f"to catch -- a default that fails its own purpose is worse than no default."),
    "inertness_note": (
        "MEASURED AND DISCLOSED, because a silent default is the defect this repo has "
        "retracted over and over.  In the SHIPPED configuration `rise_threshold` does "
        "NO work on either class of the measured population: `abs_floor` refuses the "
        "quiet clips before the rise is consulted, and `burst_max_s` refuses the busy "
        "ones.  Sweeping it from 3.5 down to 2.0 changes the busy count by nothing.  It "
        "is load-bearing in exactly one place -- ARM S2, a burst over a moving scene -- "
        "and that is where the gate tests it.  This is the same shape as S2 of the "
        "deleted spec, where the whole measured rate came from MIN_GAP_S alone."),
    "cooldown_s": (
        "DEFAULT CHOSEN WITHOUT DATA. It is the rate cap, not the detector: "
        "whatever the score does, no more than 60/minute by default. The product "
        "argument for a LARGE value is in the receipt; no measurement supports "
        "this number."),
    "lookback_s": (
        "DEFAULT CHOSEN WITHOUT DATA. Length of the trailing window the baseline "
        "is taken from. It must be long enough to contain the quiet floor of the "
        "scene and short enough to survive a scene change; 8 s is a guess."),
    "confirm_s": (
        "DEFAULT CHOSEN WITHOUT DATA. How long after a candidate we wait to see "
        "whether it came back. Costs nothing at the START of a clip because the "
        "clip is cut RETROACTIVELY out of the ring -- see highlights_contract.py."),
    "burst_max_s": (
        "DEFAULT CHOSEN WITHOUT DATA, and it is the arm that says 'a moment is a "
        "burst, activity is not'. It is what makes the sustained-activity arm of "
        "the gate go red rather than green."),
    "recovery_ratio": (
        "DEFAULT CHOSEN WITHOUT DATA. How far back DOWN the diff has to fall, as a "
        "multiple of the pre-spike baseline, for the burst to count as finished."),
    "baseline_floor": (
        "DEFAULT CHOSEN WITHOUT DATA, but CONSTRAINED: it sits below the smallest "
        "per-clip p50 in the measured population (0.00455), so it can only ever "
        "matter in digital silence -- where the absolute gate has already refused. "
        "It exists to stop the rise dividing by zero, and it is deliberately NOT "
        "the same number as abs_floor: using abs_floor here caps the reachable "
        "rise at abs_floor_ratio and made a real 0.2 impulse read as 3.08. That was "
        "a measured defect in this lane's own first pass, not a hypothetical."),
    "pre_roll_s": (
        "DEFAULT CHOSEN WITHOUT DATA. How much history before the peak the clip "
        "must contain. Bounded by what the ring can give, which is ASKED, never "
        "assumed (RingSpanProbe::span_seconds, trigger.h:121)."),
    "post_roll_s": (
        "DEFAULT CHOSEN WITHOUT DATA. How long after the peak the clip runs, so "
        "the moment can resolve."),
}


@dataclass(frozen=True)
class HighlightConfig:
    """Every knob, every default, every provenance string.

    Frozen on purpose: a detector whose behaviour can be changed by a stray
    attribute write is a detector whose measured rate belongs to no configuration.
    Use `replace()`.
    """

    # --- the score -------------------------------------------------------------------------
    # Two separate gates doing two separate jobs.  Collapsing them into one number
    # is the defect this lane measured on its own first pass: with `abs_floor` as
    # the rise denominator, the largest rise the rule could ever express was
    # 0.2/0.065 = 3.08, which is BELOW the measured ceiling of sustained activity --
    # i.e. the detector could not have seen a genuine spike.
    abs_floor: float = ABS_FLOOR_MEASURED        # absolute gate: is there ANY change here?
    rise_threshold: float = 3.25              # relative gate: is it unusual FOR THIS SCENE?
    baseline_floor: float = 0.002                # anti-division only; never a gate
    # --- the refractory -------------------------------------------------------------------
    cooldown_s: float = 30.0
    # --- the baseline ---------------------------------------------------------------------
    lookback_s: float = 8.0
    # --- what makes it a MOMENT rather than activity ---------------------------------------
    burst_max_s: float = 1.0
    confirm_s: float = 2.0
    recovery_ratio: float = 2.0
    # --- the clip window -------------------------------------------------------------------
    pre_roll_s: float = 6.0
    post_roll_s: float = 8.0

    def __post_init__(self) -> None:
        if self.rise_threshold <= HIGH_RISE_CEILING_SUSTAINED:
            # Not a warning: a rise threshold at or under the measured ceiling of
            # sustained activity is the exact defect this detector exists to not
            # have, and it would be reintroduced silently by a config file.
            raise ValueError(
                f"rise_threshold={self.rise_threshold} is at or below the MEASURED "
                f"rise ceiling of sustained activity ({HIGH_RISE_CEILING_SUSTAINED}); "
                f"the rule would fire all day on footage that never stops moving")

    @classmethod
    def unchecked(cls, **kw) -> "HighlightConfig":
        """Build a config the product REFUSES to build.  FOR THE GATE ONLY.

        `__post_init__` exists so a config file cannot quietly ship a rule that
        fires all day.  But the gate's entire job is to open that guard and see
        whether anything changes -- and it cannot do that through the front door.
        This is the back door, named for what it is, and it returns the value that
        the constructor threw away.
        """
        kw = dict(kw)
        defaults = {f.name: f.default for f in fields(cls)}
        defaults.update(kw)
        obj = object.__new__(cls)          # bypass __post_init__ on purpose
        for name, val in defaults.items():
            object.__setattr__(obj, name, val)
        return obj

    @property
    def window_s(self) -> float:
        return self.pre_roll_s + self.post_roll_s

    def provenance(self) -> dict[str, str]:
        return dict(PROVENANCE)


@dataclass(frozen=True)
class Highlight:
    """One decision, with the numbers that produced it.

    A fire that cannot be explained afterwards is a fire the user cannot trust and
    cannot turn off.  Every field here is something a log line can print.
    """

    t_peak_s: float
    diff: float
    baseline: float
    rise: float
    burst_s: float
    pre_roll_s: float
    post_roll_s: float
    reason: str

    @property
    def window_start_s(self) -> float:
        return self.t_peak_s - self.pre_roll_s

    @property
    def window_end_s(self) -> float:
        return self.t_peak_s + self.post_roll_s

    @property
    def window_s(self) -> float:
        return self.window_end_s - self.window_start_s


class HighlightDetector:
    """Streaming state machine. Feed it frames, get told when something happened.

    `push()` takes ONE sample and returns a fired `Highlight` or None.  The
    look-ahead (`confirm_s`) is why a decision can arrive AFTER the moment: the
    clip is cut out of the ring retroactively, so a decision that costs a second
    of detection latency costs nothing at the front of the clip.
    """

    def __init__(self, cfg: HighlightConfig, fps: float) -> None:
        if fps <= 0:
            raise ValueError(f"fps must be > 0, got {fps}")
        self.cfg = cfg
        self.fps = float(fps)
        self._lookback = max(1, int(round(cfg.lookback_s * fps)))
        self._confirm = max(0, int(round(cfg.confirm_s * fps)))
        self._burst_max = max(1, int(round(cfg.burst_max_s * fps)))
        self._cooldown = max(0.0, cfg.cooldown_s)
        self._series: list[float] = []
        self._last_fire_t: float | None = None
        self.fired: list[Highlight] = []
        #: an open candidate waiting for its confirm window to close
        self._pending: tuple[int, float, float, float] | None = None
        #: index until which a latched sustained run refuses to open new candidates
        self._blocked_until = -1
        #: Counters the gate quotes.  A refusal that leaves no trace is the defect
        #: this whole feature is about, so every gate in it is counted, not felt.
        self._suppressed_cooldown = 0
        self._rejected_sustained = 0
        self._rejected_no_recovery = 0
        self._rejected_below_floor = 0

    # -- instrumentation the gate quotes; never a silent counter --------------------
    @property
    def counters(self) -> dict[str, int]:
        return {
            "fired": len(self.fired),
            "suppressed_by_cooldown": self._suppressed_cooldown,
            "rejected_sustained": self._rejected_sustained,
            "rejected_no_recovery": self._rejected_no_recovery,
            "rejected_below_floor": self._rejected_below_floor,
        }

    def push(self, diff: float) -> Highlight | None:
        """One frame's change value. Returns the highlight if THIS call is the one
        that resolves a pending candidate -- not necessarily the frame that caused
        it.  See the class docstring: the decision needs look-ahead it cannot have
        at the instant the spike arrives."""
        self._series.append(float(diff))
        i = len(self._series) - 1
        if i < 1:
            return None

        # 1. is THIS sample a candidate?  One at a time: a second candidate inside
        # the confirm window would be inside the cooldown anyway.
        if self._pending is None and i > self._blocked_until:
            base = self._baseline_at(i)
            rise = diff / max(base, self.cfg.baseline_floor)
            if diff < self.cfg.abs_floor:
                self._rejected_below_floor += 1
            elif rise >= self.cfg.rise_threshold:
                self._pending = (i, base, diff, rise)

        # 2. has an open candidate now seen its whole confirm window?
        if self._pending is None:
            return None
        p_i, base, p_diff, rise = self._pending
        if i < p_i + self._confirm:
            return None                      # not enough of the future yet

        self._pending = None
        burst = self._burst_length_from(p_i)

        if burst > self._burst_max:
            # Sustained activity, not a moment.  Latch the whole run so a camera
            # pan is refused ONCE instead of re-tested on every single frame.
            self._rejected_sustained += 1
            self._blocked_until = i
            return None
        if not self._recovers(p_i, base):
            self._rejected_no_recovery += 1
            return None

        t = p_i / self.fps
        if self._last_fire_t is not None and (t - self._last_fire_t) < self._cooldown:
            self._suppressed_cooldown += 1
            return None

        h = Highlight(
            t_peak_s=t, diff=p_diff, baseline=base, rise=rise, burst_s=burst / self.fps,
            pre_roll_s=self.cfg.pre_roll_s, post_roll_s=self.cfg.post_roll_s,
            reason=f"diff {p_diff:.5f} >= abs_floor {self.cfg.abs_floor} and "
                   f"rise {rise:.2f} >= {self.cfg.rise_threshold} over a baseline of "
                   f"{base:.5f}; burst {burst / self.fps:.2f}s <= "
                   f"{self.cfg.burst_max_s}s and it came back")
        self._last_fire_t = t
        self.fired.append(h)
        return h

    def flush(self) -> Highlight | None:
        """End of stream: resolve a candidate that never got its full confirm window.

        Without this, the LAST highlight in a recording is lost every time -- the
        classic off-by-one that makes a detector look like it misses the ending,
        and which no amount of tuning fixes.
        """
        if self._pending is None:
            return None
        p_i, base, p_diff, rise = self._pending
        self._pending = None
        burst = self._burst_length_from(p_i)
        if burst > self._burst_max:
            self._rejected_sustained += 1
            return None
        if not self._recovers(p_i, base):
            self._rejected_no_recovery += 1
            return None
        t = p_i / self.fps
        if self._last_fire_t is not None and (t - self._last_fire_t) < self._cooldown:
            self._suppressed_cooldown += 1
            return None
        h = Highlight(
            t_peak_s=t, diff=p_diff, baseline=base, rise=rise, burst_s=burst / self.fps,
            pre_roll_s=self.cfg.pre_roll_s, post_roll_s=self.cfg.post_roll_s,
            reason=f"diff {p_diff:.5f} >= abs_floor {self.cfg.abs_floor} and rise "
                   f"{rise:.2f} >= {self.cfg.rise_threshold} over a baseline of "
                   f"{base:.5f}; burst {burst / self.fps:.2f}s (end of stream)")
        self._last_fire_t = t
        self.fired.append(h)
        return h

    # -- internals -------------------------------------------------------------------
    def _baseline_at(self, i: int) -> float:
        lo = max(0, i - self._lookback)
        window = self._series[lo:i]
        if not window:
            return self.cfg.baseline_floor  # cold start: no history, no claim either way
        srt = sorted(window)
        mid = len(srt) // 2
        med = srt[mid] if len(srt) % 2 else (srt[mid - 1] + srt[mid]) / 2.0
        return max(med, self.cfg.baseline_floor)

    def _burst_length_from(self, i: int) -> int:
        """How many consecutive samples from i stay above the floor."""
        n = 1
        j = i + 1
        while j < len(self._series) and self._series[j] >= self.cfg.abs_floor:
            n += 1
            j += 1
        return n

    def _recovers(self, i: int, base: float) -> bool:
        """Within confirm_s, does the diff come back to within recovery_ratio*base?

        This is the burst's other half and it is what refuses a scene CHANGE: a
        cut into a busy scene stays busy, and a scene is not a moment.
        """
        stop = min(len(self._series), i + self._confirm + 1)
        budget = base * self.cfg.recovery_ratio
        return any(self._series[j] <= budget for j in range(i + 1, stop))


def detect_series(
    diff: Iterable[float],
    fps: float,
    cfg: HighlightConfig | None = None,
) -> list[Highlight]:
    """Run the detector over a whole series. The offline twin of `HighlightDetector`."""
    cfg = cfg or HighlightConfig()
    det = HighlightDetector(cfg, fps)
    out = [h for h in (det.push(v) for v in diff) if h is not None]
    tail = det.flush()          # never lose the last highlight to an off-by-one
    if tail is not None:
        out.append(tail)
    return out