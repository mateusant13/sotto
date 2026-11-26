"""Envelope for the accessibility-tree caption read.

MEASURED 2026-11-26, owner's session (pid 103760, video TGOe1w8m5OU): with no
CDP source attached, `_yt_painted_words` fell into
`youtube_captions.painted_words` (the UIA tree) and ONE tick blocked

    EXTERNAL_CAPTIONS_READ_MS ms=16437.0 phases={'painted': 15906.0, 'track': 16422.0, ...}

which collapsed the 4 Hz loop to `YOUTUBE_LOOP_HZ hz=0.1..1.5` (median 0.5) and
left snapshots stale (`YOUTUBE_SNAPSHOT_STALE age_ms=77797` against
`max_age_ms=1500..3000`). On screen that is exactly the owner's report: the
subtitles worked for two seconds and then froze, and unpausing did not bring
them back.

The rule this module carries is the repo's own: a stage has a BUDGET and a
TYPED REFUSAL, never a clock that hides where it stalled. A read over the budget
is not retried at the same cadence -- it buys a hold proportional to what it
spent, and while the hold lasts the caller serves the last words it had instead
of blocking the loop again. The hold is named in the log, so an episode is
`YOUTUBE_UIA_SLOW_BUDGET ms=15906.0 hold_s=47.7` and not a silent freeze.

Pure by design: no imports, no clock of its own, so the caller owns time and the
oracle can drive every branch without a browser.
"""

#: A good UIA read measured 62-110 ms on this box; 350 ms is 3x the worst of
#: them and still inside one 4 Hz tick (250 ms is the tick, so a read at the
#: budget already costs more than a tick's worth of slack -- it is a ceiling,
#: not a target).
UIA_BUDGET_MS = 350.0

#: A read that overran buys back its own cost, times this, with a floor. 15906 ms
#: measured -> 47.7 s of serving what we already had, instead of the same block
#: on every tick.
HOLD_SCALE = 3.0
HOLD_MIN_S = 2.0


def decide(elapsed_ms, blocked_until, now):
    """Judge one completed read.

    Returns `(serve_cached, blocked_until, event)`:
      * `serve_cached` -- the caller must NOT block on the tree right now;
      * `blocked_until` -- the new hold deadline (0.0 clears it);
      * `event` -- the line to log when this read re-armed a hold, else None.
    """
    try:
        elapsed_ms = float(elapsed_ms)
    except (TypeError, ValueError):
        return (False, 0.0, None)
    if elapsed_ms <= UIA_BUDGET_MS:
        return (False, 0.0, None)
    hold = max(HOLD_MIN_S, (elapsed_ms / 1000.0) * HOLD_SCALE)
    return (True, float(now) + hold,
            'YOUTUBE_UIA_SLOW_BUDGET ms=%.1f hold_s=%.1f' % (elapsed_ms, hold))


def serving_cached(blocked_until, now):
    """True while a hold from a slow read is still in force."""
    try:
        return float(now) < float(blocked_until or 0.0)
    except (TypeError, ValueError):
        return False
