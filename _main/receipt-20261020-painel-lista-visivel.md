# Receipt — the live caption BOX was hidden while the caption was in it — 2026-10-20

Lane: panel live box. Write scope was `app/panel/panel.js`, ONE new file (`_main/panel-live-box-oracle.js`),
ONE step block in `_main/_audit-verify-all.cmd`, and this receipt. Nothing else was touched: no
`app/webview/**`, no `worker/**`, no `app/panel/panel.html`, no `app/panel/panel.css`, no
`app/panel/themes/**`, no existing gate, no `app/_legacy-electron/**`. Nothing was launched: no shell, no
worker, no browser, no audio device, and no process of the owner's was touched. Every number below comes
from `node` reading bytes, from jsdom running the panel's own files, or from read-only `git`.

---

## 0. THE COMPLAINT, AND THE MEASUREMENT THAT EXPLAINS IT

The owner sent a photo of an EMPTY panel (00:44:14) and said the app *"parece viva mas nao entrega nada"*.

The measurement (NOT repeated here — it is the ground truth this lane was given) is
`H:\sotto\_main\panel-state.json`, read at 02:22:35 on 2026-10-20 with the app running and the owner's
YouTube open:

    "namedState": "no-worker",
    "panel": { "live": { "count": 1, "hidden": true,
                         "lines": [ { "latest": false, "provisional": true,
                                      "text": "demais para este video , mas aqui" } ],
                         "provisionalCount": 1, ... },
               "placeholder": { "hidden": false, "title": "Warming up the teleprompter", ... } }

The caption HAD ARRIVED. `live.count = 1` — the line was in the DOM, with the right text, and it was
**PROVISIONAL**. And `live.hidden = true` — the list it was in was hidden, so the line was in the DOM and
INVISIBLE, while the placeholder stayed on screen. The owner saw a placeholder and an empty box.

## 1. THE MECHANISM (read in the shipped bytes, not guessed)

* `app/panel/panel.html:679` — `<ol class="captions__list" id="caption-list" hidden>`: the list is born
  with the `hidden` attribute.
* `app/panel/panel.css:1262` — `.captions__list[hidden] { display: none; }`: that attribute BITES (an
  author `display` would otherwise beat the user-agent's `[hidden]`).
* `app/panel/panel.js` — `addCaption()` was the ONLY function that ever took the attribute off
  (`dom.placeholder.hidden = true; dom.list.hidden = false;`) and the ONLY one that ever hid the
  placeholder. `addCaption` runs when a line **COMMITS**.
* `renderProvisional()` creates the `<li>`, appends it to the list and touches NEITHER attribute. A line
  that is still **PROVISIONAL** never goes through `addCaption`.
* `wireExternalCaptions()` → `engine.reset(); engine.ingest(text, meta);` and `engine.flush('external-final')`
  ONLY when `meta.final === true`. The shell's `final` is false while the cue does not change
  (`app/webview/sotto_webview.py:2084`), so the YouTube line stays provisional — and invisible — for as
  long as the cue sits still.

So the caption was painted into a `display: none` box, and the placeholder — which only the commit path
hides — stayed on screen. The owner was right: the app was alive and delivering nothing VISIBLE.

## 2. THE FIX (`app/panel/panel.js`, +44 lines / -2 lines, 5 hunks)

One named function owns the invariant, and it is called at the three points where the list's contents
change:

    panel.js:903   function syncCaptionBox() {
                     if (!dom.list) return;
                     if (dom.list.childElementCount > 0) {
                       dom.list.hidden = false;
                       if (dom.placeholder) dom.placeholder.hidden = true;
                     } else {
                       dom.list.hidden = true;
                       if (dom.placeholder) dom.placeholder.hidden = false;
                     }
                   }

    panel.js:1014  renderProvisional()  — right after `dom.list.append(line)`: the PROVISIONAL row is
                                         painted, so the box shows it.
    panel.js:1082  retireProvisional()  — after the row is removed: the box emptied itself, so the
                                         placeholder comes back.
    panel.js:1240  addCaption()          — after the COMMITTED row is in the list: the box shows it.

`addCaption`'s two eager lines (`dom.placeholder.hidden = true; dom.list.hidden = false;`) were REMOVED
and replaced by the call at `:1240`: the placeholder and the list are ONE slot in two states, and one
function now decides which state the slot is in. The end state of the commit path is unchanged (list
visible, placeholder hidden) — the oracle proves it (arm A runs the provisional path; the committed path
is the `panel2-dom-probe` battery step, still GREEN).

THE OTHER DIRECTION IS NOT BROKEN. When the box empties, `syncCaptionBox()` puts the list back to `hidden`
and brings the placeholder back — the state the markup was born in. Arm C measures it.

REVISION (the bytes, measured with `node` over the file):

| | bytes | sha256 | CRLF | bare LF |
|---|---|---|---|---|
| before | 180 546 | `2FB6E8F9CDAE5066EAAB03CD9E67C10CB902412B3993092577702F66564F5C0D` | 3602 | 0 |
| after | 182 599 | `75B2D886A85D825118CD27103CA3ADD763813C616FD6FBE39D26FC6D0233C920` | 3644 | 0 |

The file is still **CRLF pure** (0 bare LF) and the sha MOVED, so the change is real. The edit was made
BY BYTES (a script that refuses to write unless every anchor matches exactly once and the file is CRLF
pure before and after), never by a line-ending-oblivious editor.

## 3. THE GATE — `_main/panel-live-box-oracle.js` (NEW, 20 078 B, LF pure)

It loads the REAL `app/panel/panel.html` in jsdom, executes the panel's OWN `<script src>` list (as classic
scripts, so the panel's functions are the panel's), installs the shell's bridge in `beforeParse`, and
asserts against the resulting DOCUMENT. `panel.js` is never stubbed, re-implemented or edited by the
oracle. No window, no browser, no audio, no network, the running app is never touched.

    node _main\panel-live-box-oracle.js          -> arms 4/4, mutantes 3/3 RED, VERDICT: PASS, rc=0
    SOTTO_PANEL_DIR=<dir> node ...\panel-live-box-oracle.js   -> the arms only (the "before" measurement)

ARMS (the shipped panel):

| arm | claim | result |
|---|---|---|
| A | a painted line shows the box and hides the placeholder | PASS |
| B | the INITIAL state (list hidden, no rows) keeps the placeholder visible | PASS |
| C | after the box empties, the placeholder comes back | PASS |
| D | the painted line carries the cue the owner saw | PASS |

**arms : 4/4**

Arm C is the oracle DELETING the line (`list.removeChild(row)`) and then telling the panel its own open
row is gone (`retireProvisional`, the panel's own emptying event — the one `addCaption` calls before it
writes the closed line). The claim is read off the document: 0 rows, list hidden, placeholder visible.

MUTANTS — real copies of the panel on disk, ONE break each in `panel.js`, and the SAME arms run against
them. A mutant whose anchor does not match exactly once is a setup error, never a silent no-op.

| mutant | break | RED on | the others |
|---|---|---|---|
| M1 | re-hides the list right after painting it | **A** | B, C, D GREEN |
| M2 | hides the placeholder but does NOT show the list | **A** | B, C, D GREEN |
| M3 | never shows the placeholder again | **C** | A, B, D GREEN |

**mutantes : 3/3 RED** — and each mutant is RED on EXACTLY the claim it breaks, which is what makes the
other arms meaningful.

## 4. BEFORE vs AFTER (the same instrument, the same claim)

The pre-fix bytes were RECONSTRUCTED (the inverse of the fix, verified byte-for-byte:
180 546 B, sha256 `2FB6E8F9…`, CRLF 3602 / bare 0) and the oracle was pointed at them with
`SOTTO_PANEL_DIR`:

    BEFORE (pre-fix panel.js)                      AFTER (the fixed panel.js)
    arm A  FAIL  listHidden=true   listVisible=false    arm A  PASS  listHidden=false  listVisible=true
                 placeholderHidden=false                          placeholderHidden=true
                 placeholderVisible=true                         placeholderVisible=false
    arm B  PASS                                            arm B  PASS
    arm C  PASS                                            arm C  PASS
    arm D  PASS                                            arm D  PASS
    arms : 3/4   VERDICT: FAIL (rc=1)                     arms : 4/4   VERDICT: PASS (rc=0)

The BEFORE row is the owner's ground truth, reproduced: `rows=1, listHidden=true, placeholderHidden=false`
is exactly `live.count=1, live.hidden=true, placeholder.hidden=false`. The line was there and it was
invisible.

## 5. THE BATTERY — `_main/_audit-verify-all.cmd`

ONE step block was added (lines 182-194), after the `panel2-dom-probe` step, PURELY ADDITIVE: the file
was edited BY BYTES at a unique anchor, and the other lane's uncommitted work in that file (the
`:step`/`:record`/cache rewrite) is still there, byte for byte. The battery file is CRLF pure (0 bare LF).

    call :step panel-live-box-oracle 0 "_main\panel-live-box-oracle.js;app\panel\panel.html;app\panel\panel.css;app\panel\panel.js;..." "%OUT%\panel-live-box-oracle.log" node _main\panel-live-box-oracle.js
    call :record panel-live-box-oracle !STEP_RC!

    node _main\panel-live-box-oracle.js      (the step's own log: _main\_audit-verify\panel-live-box-oracle.log)

BATTERY RESULT (the real run, 2026-10-20 02:37, log `I:\cc-tmp\battery-run-20261020-b.txt`, on the file
as it stands NOW — the other lane's last write was 02:37:00 and my step block is still in it):

    steps    : 51   gate=39  control=10  skipped=1  expect-red=1  missing=0  cached=46
    failed   : -none-
    skipped  :  hotkey-delivery
    BATTERY-VERDICT: GREEN WITH 1 SKIPPED - 1 step(s) did NOT verify this run and are NOT counted as gates:  hotkey-delivery

`per-step: ... panel-live-box-oracle=0 ...` — the new gate passed. The step's own log holds a REAL run
(`_main\_audit-verify\panel-live-box-oracle.log`: `arms : 4/4`, `mutantes : 3/3 RED`, `VERDICT: PASS`),
and the cache cannot hide it: `app\panel\panel.js` is one of its deps, so any change to the panel
re-runs it. The battery was run TWICE (02:35 and 02:37) and both runs are GREEN with the same counts.

(The count grew from the 48 steps / 37 gates the briefing quoted to 51 / 39 because the OTHER lane's
cache/delta work added steps to the same battery in the same window; the +1 gate that is mine is
`panel-live-box-oracle`. `hotkey-delivery` was already skipped before this change — it is the instrument
saying its own arm did not run, and it is NOT counted as a gate.)

## 6. THE PRE-COMMIT HOOK — A DECLARED ESCAPE HATCH, NOT A SILENT BYPASS

`git commit` ran the repo's hook, which runs `app/shadowplay/run-all.mjs` — the runner of the **CLONE**
(a different product; that tree lives under `_moved/aireplay/` and is parked). Measured:

    SUITES 15 passed, 0 failed, 0 unreported          <- every *.test.mjs on disk
    GATE   7 passed / 2 refused, exit 1
    refused: compose-probe.mjs, keyframe-shape-probe.mjs
    both with the SAME measured reason: the NVENC screen capture returned
    "25 contiguous distinct frames but covers 240 frame slots; the clock is there
     and the content is not"  -> a property of the CAPTURED SCREEN, not of code.

Neither probe reads anything this lane touched (grep for `panel.js`, `panel-live-box`,
`_audit-verify-all`, `receipt-2026` in both: **0 occurrences**), and the hook always runs them — it does
not select probes by the changed files, so the other lane's commits run the same two probes. This is the
SAME condition the recent commits of this repo already declared, with the same escape hatch
(`SOTTO_SKIP_RUN_ALL=1`), and the hook itself says so: *"Fix it, or set SOTTO_SKIP_RUN_ALL=1 and say so
in the message."* The commit therefore carries that escape hatch, DECLARED IN THE COMMIT MESSAGE. This
lane did not touch the clone and did not try to fix a parked, screen-dependent probe.

## 7. WHAT WAS NOT MEASURED (stated, not hidden)

1. **THE REAL WebView2 WINDOW.** Everything above is jsdom over the panel's own files, loaded from
   `file://`. The owner's actual window is WebView2, and the claim "the owner SEES the caption" was NOT
   measured on it: no shell was launched, no window was opened. The DOM the owner sees is the DOM the
   oracle asserts on, but the PAINT is not the same instrument.
2. **THE OWNER'S LIVE SESSION.** The `panel-state.json` reading is the ground truth this lane was GIVEN
   (02:22:35); it was not re-measured after the fix, because measuring it means opening the panel.
3. **THE OTHER SURFACES.** The fix is in `panel.js`, which the strip, the side panel and the panel surface
   all share; only the STRIP/document level was exercised (the same `panel.html`).
4. **A REAL COMMIT PATH FROM A PROVISIONAL LINE.** Arm A paints a provisional row (the owner's case). The
   COMMITTED path is covered by the existing `panel2-dom-probe` battery step, which stayed GREEN.
5. **THE TEMPORAL BEHAVIOUR.** Whether the cue's `final` arrives, and how long the line stays
   provisional, belongs to the shell (`app/webview/sotto_webview.py`), which this lane did not touch.

## 8. LIMITATIONS AND OPEN RISKS

1. **THE CONCURRENT-Write RISK ON THE BATTERY.** `_main/_audit-verify-all.cmd` is being edited by another
   lane at the same time. The file moved four times under me (48 800 B at 02:33, 50 621 B at 02:34:54 —
   the bytes my insertion landed on, 53 653 B at 02:36:35, back to 51 832 B / sha `7CACF6AE…` at 02:37:00).
   My insertion was made BY BYTES on top of the bytes that were on disk at the moment, and the other
   lane's hunks were verified to be intact afterwards (`CACHE_STATE`, `_stepcache.py`, `:step`, `:record`
   all present; the git diff against the index is 242 insertions / 103 deletions). My block survived every
   write of theirs. If that lane ever rewrites the file from a copy taken BEFORE 02:34:54, my step block
   will be lost and the battery will stop running this gate — the FIX itself is unaffected. Re-check the
   block's presence after that lane lands.
2. **THE ORACLE USES TWO INTERNALS.** `window.retireProvisional` (arm C) and the `syncCaptionBox`
   function's own text (the mutant anchors) are panel internals. If a future refactor renames them, the
   oracle says SETUP ERROR (a missing anchor is refused, never silently accepted) instead of passing.
3. **THE MUTANT COPY SKIPS `app/panel/_fonts/`** (a 20 MB font cache no arm reads). Every file the panel
   LOADS is copied; the copy lives in `%TMPDIR%\sotto-panel-live-box-oracle` and is removed at the end.
4. **THE COMMIT PATH'S TEMPORARY STATE.** `addCaption` calls `retireProvisional` (which may empty the box
   and bring the placeholder back) and only then writes the committed row. The two happen inside one
   synchronous function, so no repaint occurs between them; the oracle cannot see a repaint, and neither
   can the owner. This is an argument, not a measurement.

---

## APPENDIX — the files

| file | what | bytes | endings |
|---|---|---|---|
| `app/panel/panel.js` | the fix (5 hunks, +44/-2) | 182 599 | CRLF 3644 / bare 0 |
| `_main/panel-live-box-oracle.js` | the gate (NEW) | 20 078 | LF (bare 521 / CRLF 0) |
| `_main/_audit-verify-all.cmd` | one step block (lines 182-194) | 51 832 | CRLF 765 / bare 0 |
| `_main/receipt-20261020-painel-lista-visivel.md` | this receipt (NEW) | — | LF |
