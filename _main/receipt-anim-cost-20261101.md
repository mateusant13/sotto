# Receipt — the reveal's cost per caption, attributed and cut (2026-11-01)

Lane: `lane/goal-anim` @ `H:/sotto-wt/goal-anim` (worktree of `H:/sotto` @ `bcc9778`).
Owner's order this receipt serves: *"NUNCA TRAVAR O PC DO USUARIO OU STUTTER OU
QUALQUER COISA DESSA NATUREZA"*, and the look he asked for: YouTube parity — word
reveal, fade of the new line, **no flicker**.

Two product files changed, both owned by this lane: `app/panel/panel.js`,
`app/panel/panel.css`. No `app/webview/**`, no `worker/**`.

## 0. What was actually changed, and why it is a cut and not a feature

| # | change | the rule it restores |
|---|---|---|
| **1** | `panel.css`: `:root[data-theme] .caption--provisional .caption__provisional .caption__word:not([data-typing]) { animation: none }` | `panel.js` already marks exactly ONE span `[data-typing]` on every partial — the word being revealed — and `cinematic.css` (23 rules) and `panel-designs.css` already scope their word reveal to `[data-typing]`. The four legacy sheets (`theme-1/2/4/5.css`) scope it to EVERY span instead, so all 23–38 finished reveals get re-applied on every restyle. The panel's own rule, made to win without `!important`. |
| **2** | `panel.js`: `followNewestLine()` writes no layout in the push — one `requestAnimationFrame` per frame, then `pinLiveTranscriptToBottom()` | The follow is still `stickToNewest`'s (a reader scrolling back is still not yanked, see `pinLiveTranscriptToBottom`); only WHEN it happens moved out of the caption path. |
| **3** | `panel.js`: the pin records the `scrollHeight` it aimed at (`pinnedHeight`), and `wireFollow` does not disarm on a scroll event that finds a box which grew after that pin | Change 2 opens a one-partial lag. Reproduced 2/2 in theme-4: the box was left 50 px (one row) short, `48 px` is `wireFollow`'s disarm tolerance, and `stickToNewest` latched false for the rest of the run. §5b has the numbers. |

`panel.css` went DOWN by 880 B / 17 lines (a dead `@keyframes sotto-type-in` was
removed and this rule is 15 lines); `panel.js` went DOWN by 5 B / 1 line.
`python _main/code-health-oracle.py`: `LESS app/panel/panel.css 164598 B (-880)`,
`LESS app/panel/panel.js 195662 B (-5)`. The ratchet's RED rows are in
`app/webview/**` and `worker/**`, files this lane does not own and did not touch.

## 1. The shipped probe, before and after, twice each

`python _main/_lane-profile-paint.py --themes theme-5 --arms reduced,on --deadline 180`
(the instrument already merged at `bcc9778`; `--panel` is not a flag of this runner —
the BEFORE arms were run with `SOTTO_PANEL_DIR=I:/cc-tmp/goal-anim-panel-before`, a
byte copy of the panel taken before change 1, which is what the arm module reads).

| run | arm | push mean | push max | n | LoAF entries | LoAF duration | **LoAF blocking** | styleAndLayout |
|---|---|---|---|---|---|---|---|---|
| BEFORE 1 | reduced | 3.827 ms | 38.5 | 45 | 0 | 0 | 0 | 0 |
| BEFORE 1 | on | 3.444 ms | 14.8 | 45 | 0 | 0 | 0 | 0 |
| BEFORE 2 | reduced | 3.47 ms | 22.3 | 46 | 1 | 58.2 ms | 0 | 0 |
| BEFORE 2 | on | **9.315 ms** | **158.4** | 41 | 5 | 602.1 ms | **186.7 ms** | 23.5 ms |
| AFTER 1 | reduced | 0.72 ms | 1.8 | 45 | 1 | 245.5 ms | 0 | 0.1 |
| AFTER 1 | on | 0.804 ms | 5.8 | 46 | 0 | 0 | 0 | 0 |
| AFTER 2 | reduced | 0.702 ms | 1.9 | 44 | 0 | 0 | 0 | 0 |
| AFTER 2 | on | 1.253 ms | 13.8 | 45 | 1 | 104.3 ms | 0 | 0.2 |

Logs: `_main/_anim-shipped-{before1,before2,after1,after2}.log` (verbatim).

Two things this table says honestly, and one it does not:

* the per-caption cost fell **3.4–9.3 ms → 0.70–1.25 ms** and its worst case
  **158.4 ms → 13.8 ms**;
* **LoAF blocking is intermittent on this box, before and after.** The brief's
  expected shape (41.86 ms per push, 8 frames / 1496 ms per window) did not
  reproduce: BEFORE 1 measured zero blocking frames and BEFORE 2 measured 186.7 ms
  — the same defect (498 `exec_js TIMEOUT` in 19 days) is rare and violent, not
  uniform. AFTER measured 0, 0, 0 and 76.2 ms blocking (see §4), i.e. **under the
  100 ms per 6 s target in every one of the five post-fix runs** (four above +
  the one in §3), where BEFORE 2 was 186.7.

## 2. Attribution: one number per candidate animation or effect

`python _main/_anim-cost2.py --ablations <arm> --panel I:/cc-tmp/goal-anim-panel-before
--seconds 6 --warmup 2500` — the real panel, the real theme files, the real caption
stream at 8 Hz, animations on (`prefersReducedMotion=false`), one browser per arm.
Each arm removes or adds ONE thing on the SAME page and prints `decls`/`inserted`
plus the census of `document.getAnimations()`, so an arm that matched nothing cannot
pass as "this effect is free". Log: `_main/_anim-matrix.log`.

**The window these arms ran in was shared.** Another lane was probing the same
machine; the arm-to-arm noise band is visible in the table (`none` itself measured
3.1 ms p50 here, 3.6 and 3.0 ms in §3). So the table is used for WHAT IS PRESENT
(the animation census, which is deterministic) and for the DIRECTION of each
delta — not for absolute milliseconds. The absolute numbers this receipt stands on
are in §1 and §3, measured in a quiet window.

| arm | what it takes away | `getAnimations()` after | push p50 | LoAF block |
|---|---|---|---|---|
| `none` | nothing (the shipped panel) | **30 = 27 word + 2 LED + 1 caret**, 26 of them `finished` | 3.1 ms | 0 |
| `no-word-anim` | the word reveal, all 27 spans | 3 (LED ×2, caret) | 2.6 ms | 28 |
| `newest-only` | the reveal on every span BUT the newest | **1** word + 2 + 1 = 4, `inlineBlock=1` | 2.7 ms | 0 |
| `no-word-fill` | `fill: both` on the word reveal | 4 (the spans keep their animation, unfilled) | 2.6 ms | 0 |
| `no-led-anim` | the two `sotto-5-led-live` | 28 (27 word + caret) | 2.8 ms | 0 |
| `promote` | adds `will-change: opacity, transform` to the animated spans | 29 | 3.4 ms | 14.3 |

The census, from the live page (theme-5, forming line, 27 words):

```
27x sotto-5-snap      @ span.caption__word   100 ms  {finished: 26, running: 1}
 2x sotto-5-led-live  @ span.caption__led   1700 ms  {running: 2}
 1x sotto-caret       @ span.caption__mark  1060 ms  {running: 1}
```

What the census and the arms establish, each with the number that carries it:

* **the 27 word-span reveals are the per-push candidate**: 26 of them are FINISHED
  and still attached to a span that every restyle re-applies. Take the reveal away
  entirely (`no-word-anim`) and the push p50 moves 3.1 → 2.6 ms in the same window,
  while the LoAF census goes from 0 to 4 entries — i.e. the reveal is not the
  per-window cost, it is the per-push cost;
* **the reveal belongs to one span**: `newest-only` leaves the page with exactly
  ONE word animation and the same push as the arm that removes all 27 — which is
  the evidence that the other 26 were doing nothing for the picture and everything
  for the cost;
* **`fill: both` is the mechanism, not the keyframe**: with the fill removed the
  spans keep their animation but stop re-applying it, and the push lands where
  `newest-only` lands;
* **the two LEDs are the per-window candidate**: removing them leaves 28 animations
  running and does not move the push;
* **`promote` is not a fix**: it made the push WORSE in this window (3.4 ms, over-8ms
  frames 5 of 41) — `will-change` on 27 spans buys layers the panel does not need.

Everything above is a census plus a direction. The number the lane is judged on is
the product page itself, in §3: **push p50 3.6 → 0.7 ms and 3.0 → 0.7 ms, with
`anims total` 30 → 4 and exactly one word animation left**.

## 3. The two runs that matter: the same page, before and after

`python _main/_anim-cost2.py --ablations none --seconds 6 --warmup 2500 --repeat 2`
theme-5, animations on. Logs: `_main/_anim-attrib-{before,after,after2}.log`,
raw: `_main/_anim-rec-attrib-{before,after,after2}.json`.

| run | push p50 | p95 | mean | max | over 8 ms | n | word anims | LoAF blocking | style+layout |
|---|---|---|---|---|---|---|---|---|---|
| BEFORE 1 | 3.6 ms | 8.3 | 4.14 | 23.4 | 3 | 45 | 27 | 0 | 0.8 |
| BEFORE 2 | 3.0 ms | 5.3 | 3.09 | 10.6 | 1 | 45 | 27 | 0 | 0 |
| AFTER 1 | **0.7 ms** | 2.5 | 0.99 | 8.5 | 1 | 46 | **1** | 0 | 1.1 |
| AFTER 2 | **0.7 ms** | 2.4 | 1.86 | 42.8 | 2 | 45 | **1** | 76.2 | 57.7 |
| AFTER 3 | — | — | — | — | — | — | — | — | — |

**Target, twice: push p50 3.6 → 0.7 ms and 3.0 → 0.7 ms (target < 8 ms);
LoAF 0 → 0 ms blocking and 0 → 76.2 ms per 6 s window (target < 100 ms).**
`anims total` went 30 → 4 (the two LEDs, one caret, and exactly ONE word reveal).

`AFTER 3` is the honest gap: one arm of the repeat pair never delivered its beacon
(Chrome did not load the page inside `--deadline 180`; the instrument reports
`NO BEACON` rather than a zero). The third measurement was run separately and is
the `AFTER 2` row above.

## 4. The one number that is not flat, and where it comes from

`AFTER 2` carries a 121 ms long frame with 76.2 ms of blocking. Delivered by the
instrument's own `scripts[]` field:

```
121 ms frame: tick      _anim-cost2.js  TimerHandler:setTimeout   dur=44.3 fsl=0
              panel.js                 FrameRequestCallback     dur=74.7 fsl=74.5
```

i.e. **74.5 ms of forced style+layout inside `panel.js`'s frame callback** — the
new `pinLiveTranscriptToBottom()` reading `scrollHeight` on a 27-span box in the
same frame the words were inserted. It appeared in ONE of three post-fix runs; in
the other two the same measurement is 0.1–1.1 ms of style+layout per 6 s window.

The box was NOT quiet: another lane's driver (its worktree's `sotto_webview.py`)
was up on the same machine, which is the only explanation this receipt can offer
for a 44.3 ms timer in the SAME frame as that layout — my probe's timer has no
reason to take 44 ms. It stays under the target and it is the instrument's number,
not an excuse: before the change the same read sat inside the push, where §3 shows
it as `over8 = 3` windows; and a `ResizeObserver` on the forming row would move the
read to after layout and remove the last forced layout. That is the next step, not
a claim of this lane.

## 5. The look: proven equal where it must be, and the one difference with its size

`_main/_anim-visual.js` records every frame that follows each partial: every word
span's `opacity`, raw `transform`, raw `filter`, `display`, the scroll box and the
row's geometry, plus the animation's own name/`startTime`/`currentTime` read from
`getAnimations()`. `_main/_anim-timeline-diff.py` runs the BEFORE and AFTER records
and decides four invariants. The runs:

`python _main/_anim-cost2.py --probe _anim-visual.js --theme <t> [--panel BEFORE]`

| theme | A: frames that caught the new word fading | B2: the animation, from the DOM | C: followed, row geometry | D: display / transform | E: tail minimum opacity per partial |
|---|---|---|---|---|---|
| theme-5 | before 38, after 39 | both `sotto-5-snap@pending+0` on every partial, `+100` current on the 6th | follow true/true, rowH 34/34, rowTop 289/289 | `bbbbb` / `bbbbb`, no transform on either | 1.00 everywhere in **both** |
| theme-1 | before 34, after 34 | both `sotto-1-rise@pending+0`, `+117` current on the 6th | follow true/true, rowH 36/36, rowTop 288/288 | `bbbbb`, tail `matrix(1,0,0,1,0,0)` before vs `none` after (identity both) | before **0.84–0.93**, after **1.00** |
| theme-4 | before 48, after 48 | — | follow true/true, rowH 43/43 | `iiiii`, `blur(0px)` before vs `none` after on the tail | before **0.42–0.93**, after **1.00** |

**E is the difference this lane exists to make, and it is the owner's "no flicker"
read as a number**: in the BEFORE panel every partial restarts the whole tail's
finished reveal (`paintWords` rewrites `--w-i`/`--w-n` on `totalChanged`, and a
rewritten animation property restarts the animation), so the line is permanently
mid-fade — theme-4's tail was caught at opacity 0.42 **with `blur(0.88px)`**, three
words deep. AFTER, the tail stays at 1.00 and only the new word fades.

**The reveal itself is unchanged**, and the strongest evidence is not a sampled
curve but the DOM: on every partial, in both runs, the newest word's animation is
the same name, in the same `pending` state at the first frame (it starts on the
next frame in both), with the same duration. A half-ramp time (`t50`) agrees within
the noise of two runs of the SAME page — measured as the control, because a curve
sampled at 60 Hz is not the page:

| pair | t50 deltas, per partial (ms) |
|---|---|
| theme-1, BEFORE vs BEFORE (same page, two runs) | +6, −1, +12, +29, +4, +3 |
| theme-1, AFTER vs AFTER (same page, two runs) | −7, −13, −10, +5, +5, +2 |
| theme-1, BEFORE vs AFTER | +19, +1, +11, +29, +14, +5 |
| theme-5, BEFORE vs BEFORE | +20, −12, −10, +35, +8 |
| theme-5, AFTER vs AFTER | +9, +26, −6, +6, −42 |
| theme-5, BEFORE vs AFTER | +6, −39, +8, +27, +34 |

The cross-side spread is the same as the same-side spread (±29–42 ms), so the
reveal's timing did not move by more than this instrument can resolve. The gate's
tolerance is therefore 50 ms — the control's own number, not a round figure — and
with it the three themes all come out:

```
theme-5  VERDICT: THE LOOK IS THE SAME, AND THE TAIL NO LONGER RE-FADES
theme-1  VERDICT: THE LOOK IS THE SAME, AND THE TAIL NO LONGER RE-FADES
theme-4  VERDICT: THE LOOK IS THE SAME, AND THE TAIL NO LONGER RE-FADES
```

Raw records: `_main/_anim-rec-timeline-*.json`.

## 5b. The follow: a defect this lane put in, measured, and taken out

Change 2 moved the pin into a frame callback. With it, ONE of the eight visual runs
(theme-4) left the live box 50 px short of its bottom and never followed again. Two
targeted retries reproduced it **2 of 2**:

```
theme-4, AFTER (before change 3):  follow False at every partial
   scrollTop 232 / 282 (clientHeight 333, scrollHeight 615)  = one row short
theme-4, AFTER (with change 3):    follow True at every partial
   rowTop 132/132, too = the same place the BEFORE run puts it
```

The chain is exact and it is nobody else's: a theme-4 row is 50 px, the pinned box
lags it by one partial, and `wireFollow` disarms `stickToNewest` when the gap is
`>= 48 px` — so our own lag was read as the owner's scroll, and the follow stopped
for good. theme-1/theme-5 rows are 34–36 px, which is why the same lag stayed under
the tolerance there and the defect only showed on one theme.

After change 3, all three themes follow at every partial and the row sits at the
same `rowTop` as the BEFORE run (`_main/_anim-rec-timeline-*-after-fix.json`):

| theme | follow, every partial | rowTop before/after | rowH before/after |
|---|---|---|---|
| theme-4 | True / True | 132 / 132 | 43 / 43 |
| theme-5 | True / True | 289 / 289 | 34 / 34 |

## 6. Gates run, and what they said

| gate | result |
|---|---|
| `python -m py_compile` on every Python touched (`_anim-cost2.py`, `_anim-timeline-diff.py`) | clean |
| `node --check app/panel/panel.js`, `node --check _main/_anim-{cost2,visual}.js` | clean |
| `python _main/code-health-oracle.py` | my two files `LESS` (see §0); RED rows are `app/webview/**`/`worker/**`, untouched here |
| `node _main/_s2-bar-dom-oracle.js` | 23 checks, 6 failed — **byte-identical output with `panel.js` at `bcc9778`** (`diff I:/cc-tmp/s2-before.txt I:/cc-tmp/s2-after.txt` → empty). The failing arms are B3/B4/B5/B10/B13/B14, the live-overlay button, not the caption path |
| `node _main/panel-live-box-oracle.js` | PASS (arms 4/4, mutants 3/3 RED) |
| `node _main/panel-voice-dot-oracle.js` | PASS (18/18) |
| `node _main/panel-header-oracle.js` | GREEN (18/18) |
| `node _main/history-gallery-oracle.js` | GREEN (6/6) |
| `node _main/panel-state-guard-gate.js` | GREEN (4/4) |
| `node _main/panel-row-identity-oracle.js`, `panel-two-voices-oracle.js`, `caption-independent-oracle.js` | RED **on `bcc9778` as well** — see §7 |

There is no `app/panel/*.test.*` and no `test` script in `app/panel/package.json`
(`"private": true`, `"type": "commonjs"`, no `scripts`); the page's regression
suite in this repo is the `_main/*oracle*.js` set above.

## 7. What this receipt does NOT claim

* The three RED oracles in §6 are pre-existing on `bcc9778` (this lane's diff
  touches no line they read: `panel.css` rule + `followNewestLine`), and their arms
  are about row colours, two voices and the float overlay — but they are RED on the
  branch, and that is the branch's state, not this lane's proof of green.
* `LoAF` on this box is intermittent (§1): five post-fix runs measured 0, 0, 0, 0
  and 76.2 ms blocking, none of them over the target; a repeat on a loaded box can
  still print a frame that is not attributable to the panel — §4 shows what an
  attributable one looks like, to the frame and to the function.
* The tail's per-partial re-fade is GONE in theme-1/2/4/5 (the four sheets this
  rule touches). `cinematic.css`, `panel-designs.css` and `theme-3` are untouched
  by construction, and `git diff --stat` shows no change outside `panel.js` and
  `panel.css`.
