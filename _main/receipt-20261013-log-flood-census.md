# THE FLOOD IS FOUR EVENTS AT ~1.44 MILLION CALLS EACH, AND ONE OF THEM FAILS EVERY TIME

2026-10-13. Census of `_main/webview-run.log` (808.6 MB) by streaming it once and grouping
every line by the event token after `sotto: `.

```
tamanho: 808.6 MB      linhas: 5 627 892      sem token: 128 382

EVENTO                            LINHAS        MB
panel                          1 445 015     113.0
PANEL_SURFACE                  1 444 917     230.1
WINDOW_GEOMETRY                1 444 916     245.3
PANEL_VISIBILITY_WRITE_FAILED  1 145 063     197.7
<NO-TOKEN>                       128 382      12.3
BRIDGE_STATUS_HELD                 4 035       0.3
BRIDGE_CAPTION_SENT                3 820       0.6
(everything else, each under 2 000 lines)
```

## What this says

**FOUR events account for ~786 MB of the 808.6 MB -- 97 per cent.** Three of them fire almost
exactly the same number of times (~1 444 9xx), which is the signature of ONE loop emitting all
three per iteration. **And `PANEL_VISIBILITY_WRITE_FAILED` fires 1 145 063 times: a write that
FAILS is being attempted over a million times and logged every time.**

**So the log flood (P0-1) and the freeze the owner reports on open and close (P0-3) are very
probably the SAME root cause**, and it is not "the app is chatty" -- it is a loop that runs
~1.4 million times, logs four lines per pass, and fails a visibility write on most passes.

## What is NOT established

* **The loop was not located.** The event names name the SYMPTOM; no call site was read. This is
  the next step and it is the whole of the remaining work on P0-1/P0-3.
* **The rate was not measured** -- 1.44 M calls could be spread over the log history or packed
  into a few bursts. The earlier tail sample showed ~2 000 lines sharing one timestamp, which
  suggests BURSTS, but that is a sample of 2 000 lines out of 5.6 M and is not a rate.
* **Why the visibility write fails is not known.**

## The rule this adds

A log census is cheap -- one streaming pass over 808 MB, seconds -- and it turned "the log is
big" into four named events with counts. **Counting by PATTERN is what attributed it; counting
by size never could.**
