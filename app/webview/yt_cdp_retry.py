"""Backoff for a CDP caption source that failed to start.

MEASURED 2026-11-26 (`_main/webview-run.log`, session pid 103760): the shell's
`_yt_cdp_ensure` sets the sentinel `False` when `source.start()` raises, and
line `app/webview/sotto_webview.py:5564` then returns early on every later tick:

    if source is False:
        return None

One transient exception therefore kills the cheap path for the WHOLE session.
What the owner sees after that is the freeze: with no CDP source the caption
read falls into the accessibility tree, where a single read measured

    EXTERNAL_CAPTIONS_READ_MS ms=16437.0 phases={'painted': 15906.0, ...}

and the 4 Hz loop collapsed to `YOUTUBE_LOOP_HZ hz=0.1..1.5`. `yt_read_budget`
bounds each read; this module is what brings the cheap path BACK, because a gate
that recovers on its own is worth more than a gate that only refuses politely.

The rule: a failure arms a cooldown, never a tombstone. 5 s, doubling, capped at
60 s, and every arming names itself (`YOUTUBE_CDP_SOURCE_RETRY tries=n
next_s=..`), so a session that never reconnects is a session that says so.

Pure by design: the caller owns the clock, the oracle owns the schedule.
"""

FIRST_DELAY_S = 5.0
MAX_DELAY_S = 60.0
SCALE = 2.0


def next_delay(attempts):
    """Seconds to wait after `attempts` consecutive failures (>= 1)."""
    try:
        n = int(attempts)
    except (TypeError, ValueError):
        n = 1
    if n <= 1:
        return FIRST_DELAY_S
    delay = FIRST_DELAY_S
    for _ in range(n - 1):
        delay = min(MAX_DELAY_S, delay * SCALE)
    return delay


def arm(attempts, now):
    """After failure number `attempts`: `(next_at, delay_s, event)`."""
    try:
        n = int(attempts)
    except (TypeError, ValueError):
        n = 1
    if n < 1:
        n = 1
    delay = next_delay(n)
    return (float(now) + delay, delay,
            'YOUTUBE_CDP_SOURCE_RETRY tries=%d next_s=%.0f' % (n, delay))


def due(attempts, next_at, now):
    """True when the cooldown is over and another start is worth attempting."""
    try:
        return float(now) >= float(next_at or 0.0)
    except (TypeError, ValueError):
        return False
