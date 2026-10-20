#!/usr/bin/env python3
"""THE PANEL-STARTUP DEADLINE the two strip-stats gates share.

WHY THIS EXISTS (measured 2026-10-20, not guessed). The battery went RED twice
on the same night for the same reason -- the BOX, not the product:

  * the log-budget gate ran its two arms; the `aggregated` arm never reached
    `RECEIVER_READY`, so it wrote ZERO push lines, the ratio became a division
    by ~0 and the gate printed
    `STRIP-LOG CONTROL FAIL ratio=21586300.0x failed=3`;
  * that arm's own log says why. The shell started at 03:20:33.714,
    `PANEL_LAZY_GATE_ARMED` at 03:20:34.676 and `STAGING_SEEN` at 03:21:37.298
    -- 63.6 s after the start -- and the arm was killed before the page went
    live (`_strip-stats-log-aggregated-a1-51764-1792477102.log`);
  * the SAME app on the SAME box, CALM, reaches `RECEIVER_READY` in 1.98 s
    (`I:\\cc-tmp\\sotto-032942.log`: READY-FILE 1.95 s, STAGING_LOADED 1.97 s,
    RECEIVER_READY 1.98 s). So the product is not slow. The box was: VRAM at
    100 %, 38 `msedgewebview2.exe` alive, the owner's own python processes and
    three agent lanes at once.

A GATE THAT FAILS BECAUSE IT COULD NOT MEASURE IS A GATE THAT TRAINS ITS
READER TO IGNORE THE RED. So the rule this file encodes:

  * the panel has to be LIVE for a measurement to exist. If an arm's page does
    not go live within the deadline, the gate has measured NOTHING, and it
    says so -- SKIP, loudly, with the numbers -- instead of turning "I could
    not measure" into a failure of the product;
  * an arm that DID go live in time is measured exactly as before. A low ratio
    is still a RED: the defect must keep showing up.

THE DEADLINE: 30 s, and the two numbers that justify it:
  * 30 s is 15x the CALM startup (1.98 s), so a merely busy box still measures
    and the deadline cannot hide the defect -- the defect is a property of the
    CODE (the aggregated arm writes ~480x fewer bytes per minute), not of how
    fast the machine is;
  * 30 s is 2.1x BELOW the LOADED startup (63.58 s to `STAGING_SEEN`, which is
    BEFORE `RECEIVER_READY`, so the loaded startup is at least that long), so
    the loaded box is caught by the deadline instead of producing a bogus
    ratio.

WHAT IS *NOT* HERE, on purpose: no threshold was loosened. The 50x ratio, the
100-line floor and the `delivered > 100` floor are the gate's claims and they
are unchanged. This file only decides WHETHER there is a measurement at all.

The gate that proves this file honest is `_main/_strip-stats-load-oracle.py`:
it runs the decision logic against simulated boxes (a loaded one included) and
against four broken copies of this file.
"""
from __future__ import annotations

import os
import re
import time

#: The milestone that means "the page is LIVE and the feed can flow". The shell
#: logs it before any push (`sotto_webview.py:5269`).
READY_MILESTONE = 'RECEIVER_READY'

#: MEASURED 2026-10-20 03:29:44 on this box, CALM: the shell's first log line
#: to `RECEIVER_READY`. The owner's own app, idle box
#: (`I:\\cc-tmp\\sotto-032942.log`).
CALM_READY_S = 1.98

#: MEASURED 2026-10-20 03:20:33 -> 03:21:37 on this box, LOADED: the shell's
#: first log line to `STAGING_SEEN`, which happens BEFORE `RECEIVER_READY` --
#: so the loaded startup is AT LEAST this long
#: (`_strip-stats-log-aggregated-a1-51764-1792477102.log`).
LOADED_STAGE_S = 63.58

#: The deadline, in seconds, for the page to go live. See the docstring.
READY_DEADLINE_S = 30.0

#: How many times faster the aggregated arm has to be, in bytes per minute.
RATIO_FACTOR = 50

#: The milestones the timeline reports, in the order they happen. Only names
#: that really appear in the shell's log.
TIMELINE_MILESTONES = (
    'PANEL_LAZY_GATE_ARMED',
    'STAGING_SEEN',
    'STAGING_LOADED',
    'PRELOAD_INSTALLED',
    'WORKER_AUTOSTART',
    READY_MILESTONE,
)

_TS_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})')


def read_log(path):
    """The text of a log file, or '' when it does not exist yet."""
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def log_lines(text, needle):
    """The lines of `text` that carry `needle`."""
    return [ln for ln in text.splitlines() if needle in ln]


def parse_ts(line):
    """The epoch seconds of a log line's own timestamp, or None."""
    m = _TS_RE.match(line)
    if not m:
        return None
    year, month, day, hour, minute, second, millis = (int(x) for x in m.groups())
    try:
        base = time.mktime((year, month, day, hour, minute, second, 0, 0, -1))
    except (OverflowError, ValueError):
        return None
    return base + millis / 1000.0


def milestone_timeline(text):
    """{milestone: seconds since the FIRST line of the log}.

    The first line of a shell log is the shell's own first line, so the numbers
    are "how long after the launch did this happen" -- the same measure the
    calm run and the loaded run were read with.
    """
    first = None
    out = {}
    for line in text.splitlines():
        stamp = parse_ts(line)
        if stamp is None:
            continue
        if first is None:
            first = stamp
        for name in TIMELINE_MILESTONES:
            if name in line and name not in out:
                out[name] = round(stamp - first, 3)
    return out


def arm_readiness(text, deadline_s=READY_DEADLINE_S):
    """The readiness of ONE arm: did the page go live, and how long did it take.

    `ready_s` is the arm's OWN clock -- the seconds between the first line of
    the arm's log and its `RECEIVER_READY` line. It is None when the milestone
    never appeared. `ready` is `ready_s` within the deadline: a page that came
    up too late cannot carry a measurement, and the gate must SAY that instead
    of measuring the wrong thing.
    """
    timeline = milestone_timeline(text)
    ready_s = timeline.get(READY_MILESTONE)
    lock_refused = 'already_running=true' in text
    ready = ready_s is not None and ready_s <= deadline_s
    if ready:
        reason = 'the page went live %.1fs after the launch' % ready_s
    elif ready_s is not None:
        reason = ('the page went live %.1fs after the launch -- LATE, the '
                  'deadline is %.0fs' % (ready_s, deadline_s))
    elif lock_refused:
        reason = ('the shell refused to start: the measurement lock was already '
                  'held (already_running=true) -- another measurement shell is '
                  'still alive')
    else:
        reason = ('the page never reached %s (the last milestone seen: %s)'
                  % (READY_MILESTONE,
                     ', '.join('%s@%.1fs' % (k, v) for k, v in timeline.items())
                     or 'none'))
    return {
        'ready': ready,
        'ready_s': ready_s,
        'deadline_s': deadline_s,
        'timeline': timeline,
        'lock_refused': lock_refused,
        'reason': reason,
    }


def load_skip_reason(arms, deadline_s=READY_DEADLINE_S):
    """Why this run CANNOT measure (None when it can).

    An arm that missed the deadline is an ENVIRONMENTAL fact, not a property of
    the log budget: its page never went live, so its numbers say nothing about
    the feed. Saying so is the whole point -- a RED here would be a lie about
    the product.

    ONE EXCEPTION, and it is the dangerous one: an arm whose shell was DEAD
    before the deadline did not run slowly, it FAILED. `--exit-after` is armed
    only after the panel loads, so a shell that is gone before the page is live
    crashed or refused to start. That is not the box being busy; it is the
    product, and it must NOT be excused as a skip.
    """
    for arm in arms:
        if arm.get('ready'):
            continue
        if arm.get('shell_alive_at_deadline') is False:
            continue
        tag = arm.get('tag', '?')
        waited = arm.get('waited_s')
        waited_txt = ('%.1fs' % waited) if waited is not None else 'n/a'
        return ("the '%s' arm did not reach %s within the %.0fs deadline "
                "(waited %s; %s) -- "
                "the box was too loaded to measure, so this run CANNOT claim "
                "the result"
                % (tag, READY_MILESTONE, deadline_s, waited_txt,
                   arm.get('reason') or 'the page never went live'))
    return None


def budget_checks(per, agg):
    """The claims the LOG BUDGET gate makes about its two arms."""
    per_delivered = per.get('delivered') or 0
    agg_delivered = agg.get('delivered') or 0
    return [
        ('both arms reached the live page (READY) within the deadline',
         bool(per.get('ready')) and bool(agg.get('ready'))),
        ('both arms ran the stand-in worker at the same rate',
         bool([ln for ln in (per.get('autostart') or [])
               if 'reason=with-worker' in ln])
         and bool([ln for ln in (agg.get('autostart') or [])
                   if 'reason=with-worker' in ln])),
        ('the per-sample arm logged a line PER SAMPLE (>= 100 lines)',
         (per.get('push_lines') or 0) >= 100),
        ('the aggregated arm logged at most a handful of lines',
         (agg.get('push_lines') or 0) <= 3),
        ("the feed's bytes per minute fall by at least %dx" % RATIO_FACTOR,
         (agg.get('push_bytes_per_min') or 0) * RATIO_FACTOR
         <= (per.get('push_bytes_per_min') or 0)),
        ('the aggregated arm still DELIVERED the feed (delivered > 100)',
         agg_delivered > 100),
        ('the per-sample arm delivered the same feed (the control is not idle)',
         per_delivered > 100),
    ]


def decide(arms, checks, deadline_s=READY_DEADLINE_S):
    """The verdict of a strip-stats gate: GREEN, SKIP or RED.

    `arms` are the per-arm measurements (each with `tag` and `ready`); `checks`
    are the PRODUCT claims, each a (what, ok) pair. The ORDER is the whole
    point: a run that could not measure SKIPs, and only a run that measured
    gets to fail.
    """
    skip = load_skip_reason(arms, deadline_s)
    if skip is not None:
        return {'verdict': 'SKIP', 'skip_reason': skip, 'failed': [],
                'reason': skip}
    failed = [what for what, ok in checks if not ok]
    if failed:
        return {'verdict': 'RED', 'skip_reason': None, 'failed': failed,
                'reason': '; '.join(failed)}
    return {'verdict': 'GREEN', 'skip_reason': None, 'failed': [],
            'reason': 'every claim held'}


def deadline_facts(deadline_s=READY_DEADLINE_S):
    """The numbers that justify the deadline -- the oracle reads them."""
    return {
        'deadline_s': deadline_s,
        'calm_ready_s': CALM_READY_S,
        'loaded_stage_s': LOADED_STAGE_S,
        'times_calm': round(deadline_s / CALM_READY_S, 2) if CALM_READY_S else None,
        'below_loaded': deadline_s < LOADED_STAGE_S,
        'justified': CALM_READY_S * 5 <= deadline_s < LOADED_STAGE_S,
    }
