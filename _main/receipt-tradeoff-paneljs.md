# TRADE-OFF RECEIPT — AREA: PANELJS

**Lane:** trade-off audit (`app/panel/panel.js` + the periodic machinery of the panel's runtime)
**Date:** 2026-10-13 (local) · **Receipt file:** `_main/receipt-tradeoff-paneljs.md`
**Nothing was launched.** No app, no shell, no worker, no probe that starts one. Measurements are
byte-level reads of the product, in-process execution of the product's own pure/standalone code
(`panel_state.write_atomic`, `panel/surface.js`), an in-process count of the shell's own log, and
Node execution of the shell's own `BOOTSTRAP_JS` functions. Every one of those is stated below.

---

## 0. PINS (AGENTS.md rule 2 — re-measured in this session, cite with the date)

| file | size | lines | sha256 (first 16) | mtime |
|---|---|---|---|---|
| `app/panel/panel.js` | **158 015 B** | 3 200 (3 199 CRLF / 0 bare LF) | `E640549906A682DA…` | 2026-10-13T17:55:16Z |
| `app/webview/sotto_webview.py` | **509 411 B** | 9 881 | `D89D33C54367DC09…` | 2026-10-13T17:53:15Z |
| `app/webview/panel_state.py` | **14 550 B** | 337 | `BC5D4F52227F52CC…` | 2026-10-13T17:50:36Z |
| `app/panel/panel.html` | 66 962 B | — | — | — |
| `app/panel/surface.js` | 4 425 B | — | — | — |
| `_main/webview-run.log` | **16 783 779 B** | 112 550 | — | 2026-10-13T17:46:04Z (last line) |

The log's own line, present in the file: `LOG_ROTATED from=847859845 B kept=16777081 B cap=64 MB`.

**THE SHELL MOVED UNDER THIS LANE.** Measured at pin time 17:53:15Z as 509 411 B / 9 881 lines;
by session end it is **509 957 B / 9 889 lines / `9BE0DFAC9C3A3271…`, mtime 2026-10-13T17:58:31Z** —
another lane added 8 lines while I was reading it. **Every shell `file:line` in this receipt was
RE-VERIFIED against that revision** (the anchors were re-grepped one by one at the end). `panel.js`,
`panel_state.py`, `surface.js`, `panel.html` and the log did NOT move. I wrote to no product file; the
only file this lane created is this receipt.
**The log I measured is the KEPT TAIL of an 808 MB file, not a whole run.** Its first line is
2026-10-13T13:53:14.819 and its last is 14:46:04.994 (local). Everything below about "rates" is
measured on that tail and is labelled as such.

---

## 1. THE CENTRAL ANSWER — "os dois polls de 1 Hz ainda se justificam?"

**There is only ONE 1 Hz poll running in the shipped document.** The other one is dead code, and the
proof is a population count, not an impression:

| grep over `H:\sotto\app\` (2743 `js/html/css/py` files) | matches |
|---|---|
| `data-chrome-clock` | **2 — both inside `panel.js`** (the IIFE at `:3185` and its comment). **0 in `panel.html`, 0 in `panel.css`, 0 in any other panel module.** |

`startChromeClock()` at `panel.js:3184-3199` opens with `const nodes = document.querySelectorAll('[data-chrome-clock]'); if (!nodes.length) return;` — so in the shipped document it returns
**before** `setInterval(tick, 1000)` at `:3198` is ever armed. The comment at `:3174-3179` ("THE COST IS
DELIBERATE AND TINY: one `setInterval` at 1 Hz writing a 8-char string into **0 or 1** elements") is
literally accurate about *zero*, and honest about it: the cost of that trade-off **today is 0**. It is
17 lines of dormant, correctly-guarded code. `clockTime()` itself is very much alive
(4 call sites: `:840`, `:1016`, `:1064`, `:1548-1559`).

### The one that does run: `panel.js:2967-2978` (`wireLevel`)

    if (typeof bridge.onStats === 'function') bridge.onStats(take);   // :2967  the PUSH
    if (typeof bridge.getStats === 'function') {
      const pull = () => { … };                                        // :2969-2975
      pull();                                                          // :2976  one read at wire time
      setInterval(pull, 1000);                                         // :2977  ← the poll in question
    }

**What it buys** (measured, from the owner's own run in the log):

* `SHELL_EXIT rc=0 reason=tray-quit statsPushes=1502 statsReplies=14647 meterPushes=145969`
* `statsPushes=1502` × the worker's own 10 s cadence (`shell:452`, `WORKER_STATS_INTERVAL_S = 10.0`)
  ⇒ the run lasted ~4 h 10 min. `statsReplies=14647` over that window ⇒ **1.007 replies/s** — the poll
  ran at exactly its designed 1 Hz for four hours. It works.
* `meterPushes=145969` ⇒ ~10 Hz of real pushes over the same window. So the push channel is not
  hypothetical: it delivered ~146 k payloads, i.e. the pull was **1 % of the traffic** on a channel
  whose data changes 10× more often than it asks.

**What it costs, measured:**
* The log side is already budgeted and measured as negligible: `BRIDGE_STATS_REPLY` appears **18
  times / 2 121 B** in the tail (first reply + every 60th, `shell:6588-6596`) for 14 647 replies — one
  line a minute is the right budget.
* The round trip itself is **UNMEASURED** (page → WebView2 → `SottoHost.dispatch` → `stats()` →
  `reply_stats` → `exec_js` → `window.__sotto_stats`). I cannot measure it without launching the app,
  which this lane does not do. What I can bound: `stats()` builds a ≤4-key dict and `reply_stats`
  does two `json.dumps` of it (sub-millisecond, measured class of work) — the unknown is the
  WebView2 marshalling, and I will not guess it.
* One cost I **can** name from the code and that is not a guess: `stats()` (`shell:6544-6558`,
  `METER_FRESH_S = 2.0`) returns the meter only while it is fresh, and otherwise falls back to the
  `WORKER_STATS` **running maximum** — "a staircase that only rises" (`shell:6539-6541`,
  `panel.js:2931-2933`). At 1 Hz the poll **repaints that staircase once a second**; the push alone
  would repaint it once every 10 s. The poll multiplies the owner-reported defect's refresh rate by
  10 for the exact state in which the defect exists (worker running, no fresh meter).
  Paint cost per `pushLevel` -> `paintLevel` (`panel.js:2888-2918`): 5 × `style.setProperty` on the bars,
  plus `SottoSkin.level()` and `SottoCaptionFloat.setMeter()` — 3 surfaces, one number.

**VERDICT: MELHORAR — keep ONE immediate read at wire time, make the interval a self-disarming
safety net rather than a permanent 1 Hz.** The push is the fast path and is measured alive; the pull is
only insurance for a path the product itself marks UNMEASURED (`panel.js:2941-2945`). Insurance is
worth paying — 1 round trip/s — but it should stop costing the moment the thing it insures is proven
working. And while it runs it actively amplifies the stale-staircase repaint.

---

## 2. THE TRADE-OFFS IN THIS AREA, ONE BY ONE

### TO-1 — `panel.js:2977` — `setInterval(pull, 1000)` (the stats pull)
* §1 above. **MELHORAR.**

### TO-2 — `panel.js:3174, 3184-3199` — the chrome clock, 1 Hz
* **Claims:** "A clock that never ticks is a screenshot" + "THE COST IS DELIBERATE AND TINY … 8-char
  string into 0 or 1 elements … `offsetParent` read per second".
* **Buys:** the `bcast` design's own timecode, the honest way (a real clock instead of a fake CSS
  animation — the same rule that deleted the fake wave, `panel.js:634-637`).
* **Costs:** **0 in the shipped document** (measured: no such element exists). If a theme reintroduces
  the element, the cost is as documented: 1 `Date` + template string, a write **only** to the element
  the active theme actually renders, and only when the text changed (`:3194`). The `offsetParent`
  gate is the cheap not-rendered test, and it is correct.
* **VERDICT: MANTER.** It is dead-but-guarded code, which is the right way to be dead. Do **not**
  delete it on the grounds that it never runs — that is the reasoning that would delete the meter
  next. If it is ever re-armed, it costs 1 write/s, and that is a fine price for a clock.

### TO-3 — `panel.js:1914-1942` — the guard in `setSurface` that closed the feedback loop
Not a "deliberate" comment but the single highest-value thing in this area today, so it belongs here.
* **Claims:** "THE GUARD THAT BREAKS A FEEDBACK LOOP, AND IT IS THE FIX FOR THE OWNER'S FREEZE",
  p50 102/s over 14 536 s, `write_atomic` 8,42 ms ⇒ 118,8 writes/s ceiling.
* **Buys:** everything below. Measured on the tail: **82,3 % of the live log is three kinds**
  (`WINDOW_GEOMETRY` 5 455 226 B / 30 649 lines; `PANEL_SURFACE` 5 118 836 B / 30 652;
  `PANEL_VISIBILITY_WRITE_FAILED` 3 239 505 B / 17 890) — **79 191 of 112 550 lines from one
  976-second loop at a measured mean of 31,40 Hz** (gaps: p50 1,0 ms, p90 98 ms, p99 277 ms,
  max 2,631 s; 12 328 gaps < 1 ms; up to 115 lines in one second; continuous for 818 s + 157 s).
  `PANEL_VISIBILITY_WRITE_FAILED` alone ran at **18,33 Hz**.
* **Costs:** two `SottoSurfaces.current()` reads per `setSurface()` call, and the loss of the
  re-run for a name that did not move — which is precisely the loss that was wanted.
* **VERDICT: MANTER — and I verified it holds, mechanically.** I loaded the **shipped**
  `app/panel/surface.js` in Node with a stub `document` and ran the shipped guard's shape:
  `set('strip')` 100× → **0** `applySurface()` calls; a real `strip→panel→strip` → **2** calls; an
  unknown name → refused, **no** listener fired. `surface.js` fires listeners only when the value
  changed, so `panel.js:1939-1942` cannot be bypassed by an echo. I also audited every page→shell
  handler in `SottoHost.dispatch` (`shell:3664-3717`): **exactly one** of them emits back into the
  page (`_panel_surface` → `set_panel_surface` → `_apply_window_geometry` → `send_geometry`,
  `shell:3865 / 7028 / 7186 / 5044`). The four `send_geometry()` call sites in the whole file are
  `:4724` (once per process), `:4862` (hot reload), `:5761` (`place_panel`) and `:7186`; all four reach
  `panel.js:2801 setSurface(geometry.surface)`, and all four are one-shot or event-driven, so none of
  them can self-sustain. `status-applied`, `caption-applied`, `setStripOffset`,
  `transparency`, `pointer`, `revive`, `info`, `history-append` do **not**. So there is exactly one
  echo path, it now costs one round trip per *real* surface change, and the loop is closed.
  **UNMEASURED:** no run with the guard in place. That needs the Lead to launch once.

### TO-4 — one document, two surfaces (`surface.js`, `panel.js:1902-1950`, `2247-2256`, `2311-2329`)
* **Claims:** the shell switches ONE attribute and resizes the window; the page never navigates and
  never owns the HWND.
* **Buys:** no second HTML file to keep in sync, no navigation cost on Alt+C, and — the part that
  matters for this audit — a resize path the *shell* owns, so the page cannot move a window.
* **Costs:** the echo. The shell must publish geometry back, which is what made TO-3's loop possible;
  and `applySurface()` → `applyLiveEnabled(silent)` → `applyFloat()` → `bridge.setPanelSurface('strip', …)`
  means a *real* surface change costs 1 extra JS→Python→JS round trip (`:2326-2327`).
* **VERDICT: MANTER.** The cost is one round trip per intentional switch, and the alternative
  (navigation) is strictly worse. The guard made the echo safe.

### TO-5 — `stickToNewest` / `wireFollow` (`panel.js:200`, `1077-1094`, `1140-1145`)
* **Claims:** the owner's own scroll is the only thing allowed to stop the follow; a programmatic
  scroll lands at the bottom and therefore keeps the flag armed.
* **Buys:** "never yank the view away from someone reading back", with **no timer** — one boolean,
  one `passive: true` listener, and one `scrollHeight - scrollTop - clientHeight < 48` test per
  scroll event.
* **Costs:** nothing periodic. It is the cheapest of the deliberate choices in this file.
* **VERDICT: MANTER.** This is what "good" looks like in this area: a rule, not a poll.

### TO-6 — `repinTranscriptsAfterLayoutChange` (`panel.js:1159-1166`, `1168-1189`)
* **Claims:** after ANY theme/template/skin change the transcript is at its BOTTOM (owner, verbatim,
  2026-10-12: *"e nao e pra mudanca de design/tema/template ficar scrollando pra cima"*).
* **Buys:** the fix for a late-landing stylesheet reflowing the feed — a real, measured defect with
  three separate causes (the comment names them).
* **Costs:** 4 pins per transition (immediate + `rAF` + 60 ms + 300 ms), ×2 containers, each a
  `scrollHeight` read + a `scrollTop` write (forced layout). ~8 forced layouts **per theme change**,
  not per frame.
* **VERDICT: MANTER.** Work per *transition*, not per iteration — the right shape. If it ever needs
  to be cheaper, the 300 ms arm is the one to drop (the `load`-capture listener at `:1182-1187`
  already covers a stylesheet that lands late).

### TO-7 — the "behind" chip (`panel.js:2981-3010`) — a live feature with no producer
* **Claims:** `behind · N dropped · 0,97×` when `queue_drops > 0` or `rate < 1`.
* **Buys:** the one number on the bar the owner could ACT on (it is what replaced the `400 lines`
  tally he pointed at, `panel.js:1191-1198`).
* **Costs measured — it can never fire:** `stats()` copies **only** `peak`/`blocks` into the payload
  (`shell:6564`, `:6575-6587`), and `shell:6513-6520` says so deliberately ("this shell does NOT
  compute, and must NOT invent"). But the data is **not missing, it is discarded**:
  `worker/sotto_worker.py:4949` prints `queue_drops=` on every `WORKER_STATS` line, and
  `parse_worker_stats` (`shell:489-505`, the whole `fields` dict at `:499-505`) keeps **every** `key=value` token in `fields`. So the shell
  holds the number, whitelists it out, and the panel keeps a code path that has never lit.
* **VERDICT: MELHORAR — two keys, no invention.** Add `queue_drops` (already on the wire, already
  parsed) to the payload the shell copies, and have the panel treat it as absent when the worker did
  not print it (it already does: `Number.isFinite` → `null` → the chip stays hidden). That is a real
  lag indicator for the price of two whitelist entries, and it removes a dead branch that reads as
  a live feature. `rate` should stay absent until someone decides which rate it means
  (`audio_s`/`infer_wall_s` on the same line would give a real-time factor, but that is a product
  decision, not a plumbing one).

### TO-8 — the level meter feed (`panel.js:652-668`, `2863-2918`, `2950-2979`)
* **Claims:** the wave is real or nothing (the fake CSS keyframe wave is deleted, `:634-637`); a
  payload is trusted only for the fields it carries; `dt`-aware exponential release.
* **Buys:** a meter that cannot lie, plus a smoothing that is frame-rate independent.
* **Costs:** none periodic of its own — it is driven entirely by TO-1/TO-14. Its documented
  UNMEASURED half (`:2935-2945`: the wire has never been exercised end to end) is exactly why TO-1's
  pull is worth keeping as insurance.
* **VERDICT: MANTER** the smoothing and the fail-closed payload rule. **This is also the reason TO-1
  must not simply be deleted**: the insurance exists because the push is unproven, and removing the
  poll is what would remove the last independent witness.

### TO-9 — controls that are inert *and say so* (`panel.js:2138-2206`, `2332-2345`)
* **Claims:** "When the shell has no `setLiveEnabled`, the toggle is NOT a lie: it is painted inert,
  `aria-disabled="true"` and its title says the shell does not implement it."
* **Buys:** the owner never discovers a no-op as a surprise. Pause is a two-step `<dialog>` that
  states the missing bridge *before* the press.
* **Costs:** the button row shows a control that does nothing. Measured: the shell defines
  **0** `setLiveEnabled` and **0** `pause` handlers — both controls really are inert, and the code
  says so out loud (that is a *documented* cost, not a hidden one).
* **VERDICT: MANTER.** The alternative — a silent dead control — is the defect class this repo has
  been bitten by twice. Reporting the missing shell methods in the receipt is the right escalation.

### TO-10 — native `<dialog>` for the pause confirm (`panel.js:2332-2360`, `panel.html`)
* **Buys:** Escape-to-close, focus, and modality come from the platform. One `cancel` listener
  (`:2359`) and no hand-rolled trap, no outside-click listener, no document-level keydown.
  Measured listener census in `panel.js`: **25** `addEventListener` calls total, and the only
  document-level ones are the theme `MutationObserver`s and a capture-phase `load` for stylesheets.
* **Costs:** none periodic.
* **VERDICT: MANTER.** Cheapest correct option available.

### TO-11 — `shell:2876` — `if (!flush()) setInterval(flush, 50)` in `BOOTSTRAP_JS` (20 Hz, forever)
Listed because it is periodic and it runs inside the panel, even though the line is the shell's.
* **Claims:** buffer page→shell messages until the pywebview channel opens.
* **Buys:** `bridge.ready()` can fire while `panel.js` is still parsing. Genuinely needed.
* **Costs, MEASURED:** I extracted `channelOpen`/`ensureSink`/`flush` from the shipped
  `BOOTSTRAP_JS` and ran them in Node with a stub `window`: **4,6 ns per `flush()`** once the channel
  is open ⇒ 20 calls/s ⇒ **3 ms of CPU over an 8-hour day** and 576 000 no-op calls. It is never
  cleared, but its cost is real-trivial.
* **VERDICT: MANTER** (hygiene only). If anyone is already in that file, the one-line tidy is
  `var id = setInterval(flush, 50); … if (flush()) clearInterval(id);` — but do not spend a change on
  it. **Known adjacent defect, not mine:** `post()` buffers into `queue` unbounded while the channel
  is closed; if it never opens, the queue grows without limit.

---

## 3. "E O QUE MAIS CORRE PERIODICAMENTE?" — the inventory, with costs

Two of these are outside `panel.js` but run *because of* the panel and are the largest periodic
costs left in this area, so they belong in the receipt. The Lead applies.

### TO-12 — the panel-state dump, 0,5 Hz (`shell:278` `PANEL_STATE_INTERVAL_S = 2.0`; `panel_state.py:167-169`, `:172-200`)
One thread, every 2 s: `exec_js(PANEL_STATE_PROBE, timeout=5.0)` (a blocking DOM read over the same
seam a screenshot uses, `shell:5106`) + `json.dump(indent=2)` + `fsync` + `os.replace`
(`panel_state.py:68-104`, tmp at `:81`, retry at `:93`) — **an unconditional write, every tick, even when nothing changed**
(`panel_state.py:193` has no "did it move" test).
* **Cost, measured in-process on this box** (artifacts `I:/cc-tmp/tradeoff-paneljs-probe.json`,
  `I:/cc-tmp/tradeoff-paneljs-probe2.json`; the number is noisy — the same measurement ran
  2,5–11,6 ms one minute and 13,1–24,6 ms the next, so the honest figure is the range):

  | payload | json bytes | `write_atomic` per write |
  |---|---|---|
  | idle dump (the 2324 B file on disk now) | 2 242 | **2,5 – 13,1 ms** |
  | `MAX_CAPTIONS = 200` live lines + the worker's `WORKER_STATS` fields | 43 022 | **11,6 – 24,6 ms** |
  | `panel-visibility.json` | 582 | **2,5 – 15,0 ms** |

  Steady state (1 800 writes/h for the state dump + 1 200/h for visibility = **3 000 writes/h**):
  * idle: 4,0 MB/h rewritten, ~42–86 s/h of fsync time;
  * with a FULL live list (200 lines, which is exactly what a running session reaches):
    **77,4 MB/h rewritten — ~620 MB over an 8-hour day** — written to the same two files, not appended.
  * **The cost scales with the caption list.** `MAX_CAPTIONS = 200` (`panel.js:42`) is the cap; the
    payload carries **every** committed line's text (`PANEL_STATE_PROBE` `live.lines`, `shell:3367-3374`).
* **Who needs 2 s?** Nobody in the live path. `grep panel-state.json worker/` = **0 matches**; the
  worker reads only `panel-visibility.json` (`worker:3178`, `:3327`, `:5505`). The state dump has an
  on-demand sentinel (`panel_state.py --request`, `shell:275`, `_pending_request` at `panel_state.py:147`) and a
  CLI reader (`--read`), and its own docstring says a ten-minute-old dump is worse than none **because
  it looks current** — which is a reason for `staleAfterSeconds` to be truthful, not for the write to
  be fast (`panel_state.py:30-39`, `:190`).
* **VERDICT: MELHORAR — three changes, none of them behavioural.**
  1. **Event + request + slow tick.** Write on a transition (the `namedState` value moving, or
     `visible` moving) and on the request sentinel, plus a safety tick at **10 s** (the same shape the
     log budget already uses elsewhere: first + one per interval). 0,5 Hz → 0,1 Hz is a **5×** cut
     with no reader affected, because the reader computes its own age.
  2. **Cap `live.lines` in the payload** (e.g. the newest 20 + the `count`). That is an **8×** cut on
     the full-list case (43 022 B → ~5 KB) and removes the one cost that grows with session length.
  3. Keep `panel-visibility.json` at 3 s — the worker is a real consumer with a real latency
     requirement ("hidden for longer than N seconds"), so that cadence is justified. Its measured
     cost (0,7 MB/h) is the price of a working mode switch.
  *How it is proven not to break anything:* the payload's `schema` and every key stay; a probe reads
  the file, drops a request sentinel, and asserts (a) a request lands within one tick, (b) a
  `namedState` transition lands without waiting for the tick, (c) `staleAfterSeconds` ≤ the measured
  gap, (d) `panel.live.count` is still the real child count. Arms of the
  `_main/_strip-surface-oracle.py` / `_main/panel-exit3-oracle.py` family can carry it, and the
  `--neg-arm` is "a reader asserts a dump older than `staleAfterSeconds` is FRESH" — which is what a
  cadence-only design would fail.

### TO-13 — `write_atomic`'s bounded retry (`panel_state.py:93-104`)
* **Buys:** a lost write becomes a delayed one — the right call for a file two writers touch
  (the fixed collision of the 13th).
* **Costs measured, and it is the interesting one:** the retries are **linear** sleeps
  (0,02/0,04/0,06/0,08/0,10/0,12 = **0,42 s per failed write, worst case**). In the loop that ran,
  `PANEL_VISIBILITY_WRITE_FAILED` fired **17 890 times in 976 s = 18,33 Hz** against a writer whose
  cadence is 0,33 Hz — i.e. it asked for up to 7,7 s of sleeping per second of wall clock. The
  writer thread is a dedicated daemon, so it cannot stall the UI, but it **can never catch up**, which
  is why the worker's reader was being handed a stale file. This is the mechanism by which the
  feedback loop silently broke the streaming→redux mode switch: the shell was alive, the file was
  not.
* **VERDICT: MANTER the retry, and CLOSE THE LOOP THAT FEEDS IT** (TO-3). One observable already
  exists: the `writes`/`errors` counters travel in the stop line and `panel-state.json`'s
  `panelVisibility` key publishes the shell half — so the failure was *visible* today. Nothing to
  change in the product; the change is in the register: **the visibility channel was starved for the
  duration of the owner's loop, so `--redux-when-hidden` was not switching.** With the loop closed
  there are 0,33 writes/s and the retry budget is ample.

### TO-14 — the 10 Hz meter push (`worker --meter-hz 10.0`, `shell:6636-6655`)
Not a poll. 145 969 pushes in the owner's run, `emit_async` with the one-pending-payload latch
(`shell:6657-6683`), `BRIDGE_METER` on a 30 s budget (measured: 32 lines / 4 045 B). This is the
correct shape and it is already there — **the panel's level feed is an event; only the fallback is a
poll.** Worth stating plainly in the answer to the central question.

### TO-15 — the log budget (what still gets registered too much)
* **Measured composition of the 16,7 MB tail** — 82,3 % is the three kinds of TO-3's loop; the
  remaining 17,7 % is real events with budgets already applied (`BRIDGE_CAPTION_SENT` 1 182 / 148 209 B,
  `CAPTION_APPLIED` 456 / 56 306 B, `STATUS_APPLIED` 469 / 33 788 B, `STRIP_DRAG` 298 / 31 474 B,
  `OUTSIDE_CLICK` 72 / 9 454 B) and the two stats channels on 30 s budgets
  (`BRIDGE_STATS_PUSH` 33, `BRIDGE_METER` 32).
* **VERDICT: MANTER.** The budget discipline is real and it holds. Rotation exists and works
  (`LOG_ROTATED … cap=64 MB`). The 81 MB/h is gone **because the loop is gone**, not because a budget
  was tightened — so the honest statement is: the log's size is now a function of how much the owner
  actually transcribes and drags, and the periodic machinery contributes **one line a minute**.
* The one remaining per-minute line is TO-1's `BRIDGE_STATS_REPLY`. It is cheap and it is the only
  witness that the pull is being answered. Keep it; if TO-1's improvement lands, this line
  disappears on its own.

---

## 4. WHAT I COULD NOT MEASURE (stated, not guessed)

| claim | why it is unmeasured |
|---|---|
| the cost of the 1 Hz `getStats` round trip | needs a launched shell; this lane launches nothing |
| that the loop is closed **in a live run** with the guard in place | same |
| the meter chain end to end (`panel.js:2935-2945` says so itself) | same — the wire has never been exercised |
| that the improved writers keep every reader happy | needs the oracle run against a running shell |
| `write_atomic`'s exact ms | measured twice, 4 minutes apart, with different results (2,5–24,6 ms). Reported as a range. The cited 8,42 ms sits inside it. |

Nothing in this receipt rests on those. Every verdict above rests on a byte count, an in-process
measurement, or a file I read.

---

## 5. SUGGESTED ORDER FOR THE LEAD

1. **Nothing in `panel.js` is urgent.** The two 1 Hz polls are: one dead (TO-2) and one working at
   1 % of its channel's traffic with one measurable side effect (TO-1). The area's biggest cost —
   82 % of the log — is already closed by TO-3's guard.
2. **TO-1** (make the poll a self-disarming safety net) — small, panel-only, and it needs an oracle
   arm because it touches the one path nobody has ever measured.
3. **TO-7 + TO-12** together — they are the same change in two files (get `queue_drops` out of the
   worker's own line and into the panel; make the periodic dump event-driven and bounded). Both are
   additive, both are provable without launching, and together they take the periodic write load
   from 3 000 writes/h and 77 MB/h down to ~600 writes/h and single-digit MB/h.
4. **Re-measure the loop with the guard in place** (one launch, Lead-operated): the tail I have is
   pre-fix. Until then, "the flood is closed" is a code fact, not a measured one.

**Not touched:** nothing in `app/` was edited. Receipt only, per the lane rules.
