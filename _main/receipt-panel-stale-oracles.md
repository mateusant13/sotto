# Receipt — the stale oracles, updated to the owner's new contract (2026-10-08)

Lane: panel. Scope of the edits: `_main/` instruments only (plus the regenerated
harness). No `worker/**`, no `app/webview/**`, no `app/panel/**` in this pass.

## Why this came first

A green oracle that asserts a string the owner removed is not a stale document —
it is a **lie told to the aggregate**. `_panel-chrome-arm.py` was RED on seven
assertions, every one of them naming the panel while the disagreement was between
the panel and the oracle. Two of the seven were not even about my change: they
were about a table the probe kept as a **second copy** of the arm's own
expectations. The generalisable part: **the expectation lived in two files and
only one of them moved.**

## The owner's new contract, as the assertions now read it

| what he said (verbatim) | before | after |
|---|---|---|
| *"to falando desse numero a esquerda. o vermelho. nao é pra ter mais ele"* | the per-line ORDINAL is PAINTED (`.caption__index`, `\d{3,}`) | **NOT painted** (`paintedIndexCount == 0`) **AND** the ordinal survives as STATE (`data-index`, monotonic) **AND** the clock is still painted on both a committed and the forming row **AND** the forming row's clock is a DIFFERENT colour |
| *"tambem nao escreve ao vivo. escreve live"* | `AO VIVO` / `rascunho ao vivo` / `· ao vivo ·` | `LIVE` / `rascunho live` / `· live ·` |
| *"e bota o nome 'sotto' em todos os temas"* | theme-1 `SOTTO`, theme-4 `SOTTO` | `sotto` in all five, counted over RENDERED elements (exactly 1), with `text-transform: none` asserted separately because that property silently overrules his spelling |
| *"tira o 'receiving captions'. deixa só um icone dinamico"* | healthy footer text == `'Receiving captions'` | healthy footer text is **EMPTY** **AND** the footer wears `status--live` (the icon's own class) **AND** an ERROR still paints its sentence |

Every inversion is asserted as a **PAIR**: the absence plus a positive control
that cannot be satisfied by a document that has simply lost the block. That rule
is what the parent asked for and it is what the new assertions encode.

## BEFORE → AFTER, per oracle, with battery membership

| instrument | a battery step? | BEFORE | AFTER |
|---|---|---|---|
| `_main/_panel-chrome-arm.py` + `_main/_panel-chrome-probe.js` | **no** | **RED — 7 problems** (6 stale strings, 1 stale ordinal claim) | **GREEN — 0 problems**, both the reduced-motion and the emulated-motion arms |
| `_main/_panel2-dom-probe.js` | **no** | **CRASHED** — `TypeError: Cannot read properties of null (reading 'textContent')` at `:319`, because it dereferenced `#hud-state`, deleted with the HUD by an earlier lane. A crash reports *nothing*, so its other stale claims were invisible | **GREEN — 65/65 arm(s)** |
| `_main/panel-exit3-oracle.py` | **YES** — `call :control control-panel-exit3-neg-arm` | `verdict PASS`, but the live half asserted only the SHELL-side sentence; the PAINT was not asserted at all | `verdict PASS`, `failures []`, rc 0 — and the live half is now the pair (painted text empty **and** `status--live` present) in **both** the unit arm and `--arm-e-real` |
| `_main/_panel-clear-lifted-mutant.py` | via exit3 (the negative arm) | faithful byte-copy of the shell + one mutation | **NOT EDITED** — see below |
| `_main/_armE-fake-worker.py` | via exit3 | docstring: *"The DOM must show 'Receiving captions'"* | docstring updated to the class contract |
| `_main/_audit-render/panel-harness.html` | read by the panel2 probe | **STALE** — written `09:24:27`, before the HUD removal: it still contained `id="hud-rows"` and its script list had no `surface.js` | **REGENERATED** with `_main/_audit-render/make-harness.py` → `37906 B`, `12:09:57`, `hud-rows` 0, `surface.js` 3 |

The battery's own `panel-state-guard-gate` step was re-run and is **GREEN (3/3)**;
it does not read the sentence.

## Staleness that was NOT mine, and was hiding behind the others

Three of the failures above predate this pass and were invisible until the crash
and the second-copy table were fixed:

1. **`#hud-state` / `#hud-rows` / `#hud-folder-button`** — the HUD was deleted
   (*"tira a hud, nao quero mais. deixa tudo clean."*) and `_panel2-dom-probe.js`
   kept 20+ assertions about it. The assertions now follow the **capabilities**
   instead: "open in folder" survives on the transcript bar (`#history-root`,
   same `revealPath(null)`), Pause survives in the header control row, and the
   stats rows are asserted ABSENT from the document.
2. **The `·` tail mark** — `_panel2-dom-probe.js` read it out of
   `.caption__provisional`, but `panel.js` puts it in its own
   `.caption__mark` element ("so the word spans stay countable by `paintWords`").
   The probe was reading the wrong element; the product was correct.
3. **`#history` display `'block'` vs `'grid'`** — the drawer is a grid, and an
   earlier arm of the same probe already expected `'grid'`.

## The one thing this pass did NOT fix, because it is not this lane's file

**The shell decides `namedState` by matching the sentence the panel no longer paints.**

`app/webview/sotto_webview.py:4057` —

```python
if panel_status == 'Receiving captions':
    return 'receiving'
```

`panel_status` is the panel's own painted footer text, read back through
`PANEL_STATE_PROBE`. The panel still **pushes and acknowledges** the sentence (so
`LIVE_STATUS_TEXT` in the oracle stays correct), but it no longer **paints** it —
measured live in `_main/panel-state.json`: `status = {kind: "live", text: ""}`,
and `namedState = "no-audio"` where the old code would have answered `receiving`
whenever a caption had committed.

**Consequence, stated as a claim with its instrument:** `namedState` can no longer
be `'receiving'`; it always falls through to the worker's vocabulary. The fix
belongs to the shell lane and is one line — key off `status.kind == 'live'`
instead of the sentence text — which is exactly why the panel's change should
have been paired with it.

**And the oracle that gates this feeds the string itself.**
`_main/restart-30s-oracle.py:378-380` calls
`_named_panel_state(worker, 'Receiving captions')` — an input no panel produces any
more. It will keep passing while describing nothing reachable. It is **not** a
battery step, and the battery step that does touch this area
(`panel-state-guard-gate.js`) is green and independent. Named here so the next
reader does not read that green as coverage.

**Why `_panel-clear-lifted-mutant.py` was left alone:** it is a byte-copy of the
shipped shell with exactly ONE mutation (the CLEAR path removed), and the exit3
oracle re-injects that path to build its "fixed" copy. Editing a second line in it
would make the negative control differ from the shell in two places, and the
control would stop proving which change moved the verdict. The shell-side mapping
above is the honest place to fix it.

## Own cost

2 headless browser arms (the chrome arm runs the page twice: reduced motion, then
emulated motion), ~4 s each; 1 `node` run per oracle pass (`_panel2-dom-probe.js`
is jsdom, in-process); 1 harness regeneration; 0 WMI calls; 0 shell/worker
launches; the owner's pids 28428 / 29008 were never touched and no window was
mapped.

---

# ADDENDUM — the day/hour gallery, theme-3, and the live WebView2 verification

Lane: panel. Files written: `app/panel/history-gallery.js` (new),
`app/panel/panel.js`, `_main/history-gallery-oracle.js` (new),
`_main/_panel2-dom-probe.js`, `_main/_audit-verify-all.cmd`,
`_main/_panel-geometry.js`, `_main/_design-lane/gen_themes.py` + the
regenerated `app/panel/themes/*.css`. No `worker/**`, no `app/webview/**`.

## Order of work, and the tie-break rule I applied

The parent's fixed order was (1) stale oracles, (2) the day/hour gallery,
(3) theme-3 + live verification, (4) the rest of the brief. Item 1 was closed
before this pass. For every decision below I took the branch that **(a)** loses no
work, **(b)** is reversible, **(c)** is measured — and the reason is recorded at
the decision, not here in the abstract.

## 1. The day/hour gallery — buttons only, no automatic list

**Why it is computed client-side.** The panel reaches the store only through the
bridge `historyApi` (`bridge.history`), implemented by the shell in
`app/webview/sotto_webview.py` — not this lane's file, and adding a bridge method
is not authorised. So the gallery buckets the entries the panel has *already*
loaded.

**`app/panel/history-gallery.js`** (7638 B, mtime 12:27:55) is DOM-free with the
dual-export pattern this repo already uses for testable page modules:

```js
if (typeof module !== 'undefined' && module.exports) module.exports = X;
if (typeof window !== 'undefined') window.X = X;
```

so the oracle `require`s the SHIPPED function instead of regexing DOM-bound
`panel.js`. Exports `SottoHistoryGallery = { RANGES, entryStamp, dayKey, hourKey,
buckets, rangeOf, inRange, select, pick }`. `RANGES = [{id:'24h',label:'24 h',
hours:24},{id:'1h',label:'1 h',hours:1}]` — 24 h first, then 1 h, a simple button.
`entryStamp` builds the Date **from parts** (`new Date(y, m-1, d, hh, mm, ss)`),
never `new Date(entry.date)`: on this box (`GMT-0300`,
`getTimezoneOffset() === 180`) the string form silently shifts a day —
`new Date('2026-10-08')` → *Wed Oct 07 21:00 local*. The oracle prints
`TZ: offsetMinutes=180 observable=true` so the trap is visible in the log.

**Buttons only.** `renderGallery()` paints the range row UNCONDITIONALLY, before
the empty check, so the way out of an empty range is always on screen. Day and
hour buttons appear only once a range is picked; until then the list shows the
hint `Pick a day or an hour above.` (`history__empty--hint`). `pushEntry` no
longer auto-appends: `renderGallery()` runs only when the new line falls outside
the open bucket. The list does not populate itself — that is asserted.

**Gate.** `_main/history-gallery-oracle.js` — 6 arms, **GREEN 6/6**, rc=0, exit
code `controlsOk ? 0 : 1`. Its `--neg-arm` injects the bare-date parse
(`new Date(entry.date)`) and prints `NEG-ARM-VERDICT: PASS … local-arm-red=true`
— a real inversion, not the vacuous no-op the first draft had.

**The strongest evidence is a real mutant run, not a hand-written control.**
`_main/_panel2-dom-probe.js` honours `SOTTO_PANEL_DIR`, so it can be pointed at a
**mutant copy of the panel** (`cp -r app/panel $d`, break one thing, expect RED).
With `for (const entry of historyEntries) dom.historyList.append(makeRow(entry));`
restored in `renderFeed`'s final `else`:
`SOTTO_PANEL_DIR=H:\sotto\_main_neg-panel-gallery node _main\_panel2-dom-probe.js`
→ **`RESULT: RED — 2 violation(s) — 76/78 arm(s)`**, failing exactly
`FAIL [G] THE LIST DOES NOT POPULATE ITSELF` and `FAIL [G] pressing a RANGE clears
the bucket and the list goes back to the hint`, rc=1. Mutant copy deleted after
`Resolve-Path` verified the path. **The hand-written `control` I first wrote for
that arm was wrong** — written from the same intuition as the code under test, it
misstated the old behaviour and never failed, because `arm()` only requires
`real !== control`. A control written from the same intuition as the code proves
nothing; it is now the measured mutant value.

**Two defects, named and not hidden:**

- With entries present but **all older than 24 h**, the gallery shows only the two
  range buttons plus `Nothing in the last 24 h.` — no wider range exists, so a
  store whose newest line is two days old cannot be browsed. The owner asked only
  for 24 h then 1 h, so this is honest, not an oversight.
- In the jsdom harness a confirmed Pause leaves `#strip-word` reading `Starting`
  even though `bridge.pause` was called; the probe asserts only that the word is
  non-empty and the dialog is closed.

**The gallery is legitimately EMPTY against the live store**, and that is not a
bug in it: the history feed accepts a line only if `meta.producer === 'redux'`
(`app/panel/history-source.js:51`, `:61-63`, fail-closed) and **nothing in the
repo stamps that field** (`grep -rn producer worker/` → ZERO matches; newest
archive `history/2026-10-06/19.md`). So the buttons hide. The oracle and ARM G's
fixture prove the bucketing; the live store cannot exercise it.

## 2. theme-3 — the +13.5 px, measured

**The parent's premise was already satisfied.** `app/panel/panel.html:171-175` is
ONE `.chrome--mano` flex cell whose children are already siblings:
`chrome__brand` + `chrome__draft` + `chrome__page`. Moving the name into
`rascunho live`'s cell changes nothing — it is already there.

**Where the 13.5 px actually came from:** `.chrome__draft` *and* `.chrome__page`
each wrapped to **two** lines inside a 138.6 px cell.

**A single-line header at 380 px is impossible, and this is a measured lower
bound, not a preference.** The three WRAPPED child widths are
`24.1 + 68 + 26.5 = 118.6`; plus two 10 px flex gaps that is **138.6 = exactly the
head cell's width**, so both wider items were already compressed to fit. Their
unwrapped widths are strictly greater, so one line needs
`≥ 138.6 + 10 (column gap) + 201.4 (controls) = 350.0 px` — and in fact more than
the 350 px header.

**The fix, and why it is not squeezing** (`"Não espremas"`): the name keeps its own
size. The decoration goes.
`_main/_design-lane/gen_themes.py:1058`:

```
@S@ .chrome--mano .chrome__page{ display: none; }
```

preceded by a comment block recording the width budget above. Theme CSS is
**generated** — hand-editing `app/panel/themes/*.css` is lost work. Regenerate with
`py -3 _main\_design-lane\gen_themes.py`; measured at the time: only `theme-3.css`
changed (22423 → 22400 B) and 6 of 7 artifacts came back **byte-identical**, so the
generator is idempotent.

**BEFORE → AFTER** (Edge, 380×900, theme-3, `live`):

| | BEFORE | AFTER |
|---|---|---|
| header box | **41.5 px** | **28 px** |
| live box (`derived.liveHeight`) | **747** | **760.5** |
| `chrome__draft` | 68 × 37.5, **2 lines** | 69.8 × 18.8, **1 line** |
| `chrome__page` | 26.5 × 33, **2 lines** | **0 × 0, `display:none`, 0 lines** |
| name box | 24.1 × 15, 1 line, fs 10px, `text-transform: none` | unchanged |
| header columns | `138.594px 201.406px` | unchanged |

The 13.5 px went back to the live box: **747 → 760.5**, exactly the pre-name
theme-3 number.

**The name costs 0 px on themes 1, 4 and 5** — their `liveHeight` is the pre-name
value (762 / 759 / 741) and the brand is 1 line everywhere. theme-2's +2.2 px is
pre-existing and unchanged. theme-3's +13.5 px is now 0.

**`pág. 1` — the decision, and its one-line revert.** It is static, it names a page
in a transcript that has none, and it is the same class of decoration the owner
removed twice already (item B, item 3). Hiding it is therefore consistent, and the
revert is **that one line in `gen_themes.py`** plus a regeneration. Option left
open, unmeasured and out of scope: move it to theme-3's existing
`.chrome--mano[data-chrome="foot"]` block.

## 3. A concurrency finding that invalidates the previous green

**At 13:09:59 another lane rewrote `panel.css`, `panel.html`, `panel.js` and all
five `themes/*.css`** — i.e. *after* my 12:47:46 battery run. Sizes moved:
`panel.js` 97234 → **99400 B**, `theme-3.css` 22400 → **23034 B**.

My work survived: `theme-3.css:596` still carries
`:root[data-theme='theme-3'] .chrome--mano .chrome__page { display: none; }`,
`gen_themes.py:1058` still carries the rule, and `panel.html:438` / `:714` still
carry the gallery nav and the `history-gallery.js` script tag.

Re-measured against those bytes, all green:

| check | result |
|---|---|
| `node --check app/panel/panel.js` | **rc=0** |
| `node _main/history-gallery-oracle.js` | **GREEN 6/6** |
| `node _main/_panel2-dom-probe.js` | **GREEN 78/78** |
| `py -3 _main/_panel-geometry-arm.py --browser edge --label name-after2` | **VERDICT: GREEN**, rc=0 |

and the five-theme numbers are **identical** to the table above — t1 28/762,
t2 50.5/741, t3 **28/760.5** with the page kid `display:none h=0 lines=0`,
t4 28/759, t5 50.5/741, and 0 overlaps / 0 clipped / 0 cutInside on all five. The
theme-3 fix survived another lane's regeneration, re-measured on the new bytes.

**Consequence for the aggregate, stated plainly:** the 12:47:46 battery triple
describes *earlier* bytes of `panel.{html,css,js}`. It is stale, and a battery
re-run is required before anyone claims the aggregate gate is green for the
current tree. That re-run is `_main\_audit-verify\_run-20261008-post1309.log`.

## 4. Live WebView2 verification

**The owner's own log** `_main/webview-run.log` (4.31 MB, mtime 13:24:08):

```
HOT_RELOAD_FLUSH kind=panel files=["panel.css", "panel.html", "panel.js"] events=12 debounce_ms=250
HOT_RELOAD_PANEL_DONE files=["panel.css", "panel.html", "panel.js"] reload=84 hotkey=Alt+C
HOT_RELOAD_APPLIED reload=84 visible=false hotkey_still_registered=true
HOT_RELOAD_KEPT_HIDDEN reason=owner-had-it-hidden reload=84
```

with **zero `PAGE_ERROR` in the entire file** and `BRIDGE_CAPTION_SENT
delivered=true` still flowing at the tail.

**The owner's own `_main/panel-state.json`** (writtenAt 13:24:41, producerPid
**28428** = the owner's shell) — this is exactly the machine check AGENTS.md names
for the staging bounce:

| field | value | what it proves |
|---|---|---|
| `panel.url` | `file:///H:/sotto/app/panel/panel.html` | the reload landed on the **real document**, not `chrome-error://chromewebdata/` |
| `shell.reloadCount` | 84 | the reload happened |
| `live.count` | **0** | **non-negative** — not the `-1` "`#caption-list` absent" sentinel |
| `worker.captions` | 8379 | the worker is transcribing |

**A fresh-process pixel check**, `py -3 _main\panel-paint-probe.py --secs 9` →
**`PAINT-VERDICT PASS`**, rc=0: `asked` **PAINTED** (`hwnd=51453850`,
`on_monitor=False`, `rect=(-10000, 66, -9620, 966)`, `printwindow_ok=True`,
`getdibits_rows=900`, `distinct_colours=65`), `notasked` **NO-WINDOW** with two
`PANEL_SHOW_REFUSED reason=not-asked … cure=_gate_form_show source=edgechromium.py:348`,
`RECEIVER_READY hasBridge=True`, `PRELOAD_ACTIVE hasSotto=true methods=17`.
`Select-String` over both `_main\_paint-*.log` → no `PAGE_ERROR`, no `Uncaught`,
no `ReferenceError`/`SyntaxError`. The copy renders at x=-10000, so **nothing
appeared on the owner's screen**.

**Limitations, stated rather than glossed:**

- The paint hash moved `1e762bdd6b55d0c6` → `bd507b1dbfd3f7b7`. That is expected —
  my own edits changed the panel's text and markup — and the probe's PASS
  criterion is `distinct_colours > 1` (non-blank), not hash equality. The painted
  theme is the **persisted theme-4**, not theme-3.
- **`themes/` is not watched.** `app/webview/hot_reload.py:55`
  `PANEL_ASSETS = frozenset(('panel.html','panel.css','panel.js'))` and L440-448
  arm exactly two directories (`kind=panel`, `kind=worker`). A reload triggered by
  a watched file re-parses the whole document, so a fresh `history-gallery.js`
  **is** fetched; but a **theme-only edit triggers no event at all**. So the
  theme-3 fix reaches the owner only via a reload caused by some other asset, or a
  shell restart — which is forbidden. And the live theme is theme-4, so even a
  restart would not paint theme-3 without changing the owner's persisted theme
  (not authorised).
- **`panel-state.json` is written unconditionally by any shell**, so my
  measurement shell overwrote the owner's state (writtenAt 13:18:41, producerPid
  38332, `live.count 0`). The owner's shell rewrote it at 13:24:41. For
  owner-live evidence prefer the owner's own log, or re-read the state after the
  owner's shell has written it again.

## 5. An instrument defect I found and fixed in `_main/_panel-geometry.js`

L367 read the **first** `.chrome__brand` in the document — theme-2's
`chrome--bcast` — on **all five** themes, so `carrierRect` came back `0×0` for
themes 1/3/4/5 and the "name cost" numbers would have been measured on the wrong
element. Fixed with a visibility-aware `shownCarrier()`, plus a new
`headerReport = {blockCls, block, kids, header, headerColumns, headerRows,
headerChildCount}` and `carrierLines` / `carrierFontSize`. `node --check` rc=0.

**And a measurement trap worth more than the fix:** `getClientRects().length` is
**useless for a wrapping block** — a `display:block`/flex box returns 1 rect no
matter how many lines it wrapped to. Line count must be `rect.h / lineHeight`.
That is exactly why the old probe reported `lines=1` for the two boxes that had
each wrapped to two lines, and why the +13.5 px was invisible to the instrument
that was supposed to see it.

## 6. The battery wiring, measured

| | PRE-edit (`_run-20261008-strip-battery.log`, 12:23:30) | AFTER (`_run-20261008-gallery.log`, 12:47:46) |
|---|---|---|
| steps | 38 — gate=28 control=8 skipped=1 expect-red=1 missing=0 | **41** — gate=30 control=9 skipped=1 expect-red=1 missing=0 |
| failed | `strip-stats-log-budget=3` | same single failure |
| verdict | `BATTERY-VERDICT: RED - 1 step(s) failed` | `BATTERY-EXITCODE=1` |

Delta exactly **+3 steps**, my three rows:
`history-gallery-oracle=0` (`:record`), `panel2-dom-probe=0` (`:record`),
`control-history-gallery-neg-arm=0 [CONTROL] went RED on the broken copy as
required`. `_main\_audit-verify-all.cmd` stayed pure CRLF
(`LF=518 CRLF=518 bareLF=0`), sha256 `8F86034014FCA362…`, because cmd.exe seeks a
batch file by byte offset and LF-only endings run the tail twice.

**No step in the battery references `theme`, `themes/`, `chrome__page`,
`chrome--mano` or the geometry arm.** The theme-3 fix is therefore not gated by
the aggregate at all. Named, not hidden.

## 7. A cross-lane failure, reported and not fixed

`strip-stats-log-budget` RED (rc=3) is **pre-existing and not this lane's**:
`_main\_audit-verify\strip-stats-log.log` is 0 bytes and
`_strip-stats-log-probe.json` shows 5 of 6 checks failed
(`per_sample.push_lines=0`, `per_sample.autostart=[]`, `aggregated.push_lines=1`,
`pushes_total=null` on both arms, `ratio=0.0`). Both arms exceeded the deadline
(`window_s` 57.98 / 64.69 > 24+20) and were killed; the per-sample log ends at
`PRELOAD_INSTALLED` with no `STAGING_LOADED` / `PANEL_LOADED` /
`WORKER_AUTOSTART` / `SHELL_EXIT`. My "the needle is unreachable" hypothesis was
**refuted by checking** (`print` exists at L180). The stall is upstream in the
shell's navigation/exit path, in the strip lane's files.

## 8. Own cost of this addendum's pass

~1 five-theme geometry arm (10 headless Edge launches, sequential, ~2-4 s each);
1 paint-probe run (2 shell copies, ~40 s, off-desk at x=-10000, temp `.py` created
and removed inside `app/webview/`); 1 theme regeneration (7 artifacts rewritten,
6 byte-identical); 1 mutant panel copy created (888 files) and deleted; 3 `node`
runs (oracle, panel probe, `--check`) plus 1 `node --check`; ~10 read-only
greps/JSON inspections; 1 full battery run (background). No WMI calls, no
`Get-CimInstance Win32_Process` in any loop, no window mapped, and the owner's
pids **28428** (shell) and **29008** (worker) were never touched, restarted or
signalled.

## 9. The aggregate battery green, and why it is not the last word

`_main\_audit-verify\_run-20261008-post1309.log` (13:34:10):
`steps : 42 gate=31 control=9 skipped=1 expect-red=1 missing=0`, `failed : -none-`,
`BATTERY-VERDICT: GREEN WITH 1 SKIPPED (hotkey-delivery)`, `BATTERY-EXITCODE=0`.
This is the first fully green aggregate run in this lane's span, and it retires the
`strip-stats-log-budget` RED of §7 (fixed by the strip lane).

**It certifies the tree as of 13:09:59, and the remaining brief edits invalidate it by
construction** — `panel.html`/`panel.js` are still to lose two buttons and gain the typing
reveal. Per the parent's tie-break rule: (a) *loses no work* — it is a valid, banked
statement about those exact bytes; (b) *reversible* — re-running the battery is pure
re-execution; (c) *measured* — one run at the end quotes the final bytes. So the panel
edits go first and the battery runs **once** at the end; both greens are reported with
their distinct byte-revisions rather than one being silently overwritten.

## 10. The cost instrument — RED, and the RED is the deliverable

**Verdict: `VERDICT: RED`, rc=1, on every one of the 7 runs in this pass.** Per the
standing rule, **no limit was tuned** — `('forcedLayout','mean'): 0.25` and
`FORCED_MIN_DELTA = 0.05` are exactly as they were before the pass. What follows is what
the instrument said, why it said it, and what I repaired.

### 10.1 The control was vacuous three times, each time for a different reason

The control's job is to make the channel move so the channel can be shown to *say NO*.
It failed to do that in three successive ways, and each failure was found by measuring,
not by reading:

1. **It never installed (CSP).** `installRelayoutControl()` built an `@keyframes` +
   `animation: … !important` rule as a `document.createElement('style')` appended to
   `<head>`. `panel.html:22–25` carries
   `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src
   'self'; style-src 'self'; …">`. A **meta CSP applies regardless of transport**, so the
   element was refused *even though the arm serves the page over its own
   `http://127.0.0.1:<port>/arm/…` server* — the arm's HTTP transport is not a
   workaround. Proof: the `relayout` arm's computed `animationName` was the **theme's own**
   (`sotto-5-led-live` on theme-5, `none` on theme-2); `cost-relayout` appeared in no arm,
   and the rule's other selector (`.chrome__meter i`) had no target at all (`meter=none`
   in all six cells). The control arm was behaviourally identical to `on`.
2. **It installed but wrote to an out-of-flow box.** Cure #1 moved the write to CSSOM
   (`el.style.prop = v`), which `style-src` does **not** govern. It reported
   `{"installed":true,"writes":360,"skipped":0}` — a genuine proof of installation — while
   the channel still measured `relayout` *cheaper* than `on` (0.233 vs 0.327). Cause:
   `panel.css:1703–1712` declares `.caption__led { display:none; position:absolute; … }`,
   and an absolutely-positioned box dirties only itself.
3. **It dirtied the wrong read.** Cure #2 retargeted to `#caption-list` (in-flow) and
   wrote `padding-bottom` per frame. The aggregate moved (+0.108 / +0.088, above the 0.05
   floor) but **run-to-run it flipped sign**: control delta on the aggregate was
   `+0.139, +0.055, −0.058` (theme-2) and `+0.051, +0.095, −0.065` (theme-5). Cause, found
   by splitting the timing: **the read order**. `led.offsetWidth` runs *first* and flushes
   the pending style+layout — including the control's dirty padding. The control's cost was
   therefore paid inside the **first** bucket, and the second bucket (`list.scrollHeight`)
   was a cache hit **by construction** (measured 0.000–0.009 ms on every arm).

### 10.2 The repair that made the channel interpretable

`_main\_panel-anim-cost.js` now times the two reads **separately** and publishes them as
`forcedLed` / `forcedList` (the aggregate `forcedLayout` is kept, unchanged, so nothing
already measured is lost). `_panel-anim-cost-arm.py` asserts the sensitivity PAIR on
`forcedLed.mean` — the read the control causally owns, because it is the one that flushes —
and prints the second read as the "already paid for" note. It also **gates the control's
proof of life**: an arm that claims `installed` and reports `writes == 0` is a hard FAIL,
which is the defect class (1) above made unrepresentable.

### 10.3 What the instrument now says, over 6 runs of the final code

`theme-5` / `theme-2`, 3 repeats each, `_panel-anim-cost-final{1,2,3}.log`:

| quantity | measured | reading |
|---|---|---|
| `forcedLed.mean`, `reduced` | 0.008 – 0.014 ms | baseline: a cache hit |
| `forcedLed.mean`, `on` | 0.209 – 0.354 ms | **11× – 56×** the baseline, in 6/6 runs |
| animation delta (`on`−`reduced`) | 0.190 – 0.333 ms | always present, never near zero |
| control delta (`relayout`−`on`) | +0.066, +0.028, +0.038 (t2); +0.021, +0.114, −0.049 (t5) | **PASSES the 0.05 floor in only 2 of 6 runs** |
| `forcedList.mean`, all arms | 0.000 – 0.009 ms | cache hit, as the read order predicts |
| `frame.p95` on the `on` arm | 16.7 – 16.8 ms, `over50 = 0` | **all 18 arm-runs; zero dropped frames** |
| `loaf.count` / `seen` / `dropped` | 0 / 2 / 2, every arm | the style/layout channel is empty in-window |
| `control.writes` | 358 – 361 | the CSSOM write lands every frame |

### 10.4 Findings, stated and not tuned away

- **(a) The instrument's verdict is a coin flip on unchanged bytes.** `ANIMATION-ON vs OFF`
  came back **FAIL, PASS, PASS** for theme-5 and **PASS, FAIL, FAIL** for theme-2 — the same
  bytes, the same cadence, opposite verdicts. The aggregate animation delta spans
  **0.210–0.338 (theme-2) and 0.223–0.334 (theme-5)**, i.e. a run-to-run spread of
  **0.111–0.128 ms** against a **0.25 ms** threshold. The threshold sits *inside* the noise.
  A single run of this arm cannot answer the owner's question; only the ratio can.
- **(b) The animation's cost is real and large, and it is STYLE RECALC, not layout.**
  `forcedLed` reads `offsetWidth` on an element that `panel.css:1703` sets to
  `display:none` — no rule turns it on — so the 0.2–0.35 ms it costs on the motion arm
  cannot be that element's layout. It is the pending style recalc for the whole document,
  which `offsetWidth` flushes. A forced single-element relayout (the control) costs
  **0.02–0.07 ms**, ~5–10× *less*. So the channel is dominated by style recalc, which is
  what finding (c) predicted, and the LED is now understood as a style-recalc probe.
- **(c) The user-visible answer is GREEN.** `frame.p95 = 16.7–16.8 ms` and
  `over50 = 0` in **all 18 arm-runs** of the final code — one vsync interval, zero dropped
  frames. 0.2–0.35 ms is ~1.5 % of a frame. The animation is affordable; the RED belongs to
  the instrument's resolution, not to the panel.
- **(d) The `loaf` limits are vacuous and stay that way.** LoAF emits an entry only for
  frames ≥ 50 ms, and this panel never has one, so `loaf.count = 0` on every arm and every
  `loaf.*` limit compares 0 to a positive number. The observer is installed and *does* see
  entries (`seen=2`), and the window filter correctly drops them as start-up — so this is an
  empty channel, not a missing instrument.

### 10.5 What I did NOT do, and the correct next step

I did not lower `FORCED_MIN_DELTA`, raise the 0.25 limit, widen the window, or drop the
control to make this green. The instrument's resolution is the defect and the numbers above
are its honest answer. The repair that would actually work — **out of this pass's budget,
and stated rather than attempted** — is one of: (i) n ≥ 8 repeats and compare **medians with
a band** instead of single-run deltas; (ii) a ≥ 30 s window to shrink the spread; or
(iii) make the arm's verdict the **ratio** (`on`/`reduced` ≥ 5×), which is stable at 11–56×
in 6/6 runs, and keep the absolute limit only as a report. All three need a decision from
the owner about what he wants the threshold to mean, which is why none was taken here.

### 10.6 Files and instruments touched

`_main\_panel-anim-cost.js` (read-order split, `forcedLed`/`forcedList`, `control.applied`,
CSSOM control with `writes`/`skipped`), `_main\_panel-anim-cost-arm.py` (proof-of-life gate,
pair assertion moved to `forcedLed`, the control's own question restated so the arm no longer
prints two opposite verdicts for one control, `control`/split print lines). Transcripts:
`_main\_panel-anim-cost-run2.log`, `-run3.log`, `-rep{1,2,3}.log`, `-split{1,2,3}.log`,
`-final{1,2,3}.log`; raw payloads in `_main\_panel-anim-cost.json`. Neither file is a battery
step (grep of `_main\_audit-verify-all.cmd` for `anim-cost` → zero matches), so these edits
cannot move the aggregate verdict.

**One arm-level defect found and fixed on the way:** the arm applied the
`on`-vs-`reduced` LIMITS to a `relayout`-vs-`on` delta and, when they did not fire, printed
`THAT IS A FAILING CONTROL` **and** set `all_ok = False` — twenty lines above a pair
assertion printing PASS for the same control. Those limits judge MAGNITUDE; the control
answers SENSITIVITY. Two opposite verdicts on one control is a bug in the arm, and the block
now prints the magnitude fact (`+0.019 … UNDER the 0.25 limit, so these limits would NOT
flag a per-frame relayout by themselves`) without failing the run.

## 11. The rest of the brief — the ordinal, the four paint sites, the status icon, the name, and the two bugs the typing reveal exposed

### 11.1 Item 1 — the red per-line ordinal, gone (and what is NOT the ordinal)

The owner, verbatim: *"tira esse numero de 033 11:21:03. no caso tira esse 033"*, corrected
to *"to falando desse numero a esquerda. o vermelho. nao é pra ter mais ele"* — the per-line
**ordinal**, on every row.

**Gone, with a citation in the shipped bytes.** `panel.css:1690–1693` records the removal in
place of the dead rule:

> `/* The per-line ordinal USED to be painted here (`.caption__index`, `bcast` only). … gone with it. The ordinal survives as `li[data-index]` for the DOM probes. */`

and `panel.js:246` says the same from the script side. Measured: **`indexElements=0`** — no
`.caption__index` element is created anywhere, so no digit is painted in any theme.

**What survives, and why it is not a visual.** `stampOrdinal` (`panel.js:285`) still runs at
`:598` and `:719` and writes **`line.dataset.index`** and **`line.dataset.indexPadded`**
(`:287–288`). Those are attributes for the DOM probes, not paint: nothing in `panel.css` or
any theme reads them (`attr(` → zero matches across `panel.css` + all five themes). So the
number is still *in the DOM* and is *nowhere on screen*. Stated as a residual, not hidden: if
the owner wants it out of the DOM too, it is the two lines at `panel.js:287–288`.

**The ambiguity I have to disclose, because the thing that remains is also red.** What is
still painted at the left of a row is **`.caption__led`, a 4 px rail — not a number**:
`panel.css:1703–1712` (`display:none; position:absolute; width:4px; border-radius:99px;
background:var(--accent-from)`), turned **on for the provisional line by exactly one rule**,
`theme-5.css:631` (`display:block; left:-4px; background:var(--accent)`), and neutralised in
all five directions under reduced motion (theme-1:627, theme-2:661, theme-3:628, theme-4:626,
theme-5:714 — each an `animation:none !important; transition:none !important` group). I read
the owner as meaning the **ordinal**, not the rail, on the strength of his own words: *"esse
**numero**"* and *"033"* is three digits, while a rail has no digits. **If he meant the red
rail, that is a different change and this receipt does not claim it.**

Also measured, so the row's remaining furniture is on record: **`timeElements=4`**, committed
times in `rgb(138,140,142)` and the live one in `rgb(255,210,74)` — the times stay, they were
never the complaint (`11:21:03` is the *right* half of his sentence).

### 11.2 Item B — the four "things like" the owner struck out

*"tambem tira essas coisas como 'h sotto history 400 lines no canonial writer 400 lines the
transcript'"*. **Four paint sites, all four removed**, and the measured win on theme-1: the
transcript bar **47.7 → 30 px** and the live box **740.6 → 762 px**. `#history-count` is now
`hidden` in the markup (`panel.html:341`), so the count is not merely unstyled — it is not
rendered. The four were: the note text, the live `N lines` hint, `#history-count`, and the
`H:\sotto\history` path.

### 11.3 Item 3 — "receiving captions" out, one dynamic icon in

*"tira o 'receiving captions'. deixa só um icone dinamico"*. Measured across all five themes:
**`Receiving captions` → 0 occurrences** and **`ao vivo` → 0 occurrences** (the second is
item 4). The dynamic icon is the `.chrome__state` element (`panel.css:1667`), driven by
`.chrome__on`/`.chrome__off` (`:1652`).

**The exception, disclosed rather than papered over:** an **ERROR** still paints its sentence.
The healthy sentence is not deleted but moved off-screen and kept readable —
`.status__text--offscreen` (`panel.css:1156`), which is **not `hidden`**, so it stays in the
accessibility tree and the shell's own status probe still reads it. That choice is what
created the cross-lane break already reported in §7 (the shell's `namedState` can never be
`'receiving'`, `sotto_webview.py:4057`); it is named there and not silently patched here.

### 11.4 Item 4 — `live`, not `ao vivo`, and the name in every theme

*"tambem nao escreve ao vivo. escreve live. nos temas relevantes"* and *"e bota o nome
'sotto' em todos os temas."*

Measured, all five themes: **`ao vivo` = 0**; **`Receiving captions` = 0**; **`sotto` present
in all five** (counts 1/3/1/1/8 for themes 1–5); and **the visible carrier's
`text-transform` is `none` on all five** (`carrierTransform="none"` in the geometry arm's
`brand` payload, `real` state) — i.e. the name reads **lowercase as seen**, everywhere.

**The trap that had to be measured rather than reasoned about.** `--brand-upper` is set to
`uppercase` in themes 2/4/5 and `none` in 1/3, and it is consumed by `.wordmark__name`
(`text-transform: var(--brand-upper)`, theme-2/5 line 127) — so it *looks* like the name is
upper-cased in three of five directions. It is not: themes 2/4/5 **hide** `.wordmark__name`,
and **every** `.chrome__brand` rule pins `text-transform: none` (`panel.css:199`, theme-2
L572, theme-3 L573, theme-4 L580, theme-5 L572). **In no theme is an uppercase brand
visible.** The owner's spelling is safe, and it is safe for a reason that is invisible to
reading — which is why it is asserted (`_panel-chrome-arm.py:477–491`: `brandCount != 1`,
`brandTextTransform != 'none'` and `brandText != 'sotto'` are each a failure) and not
assumed.

### 11.5 Item A/2 — the search side: the list that used to show itself

*"na pesquisa dos transcript, tira o historico que ja mostra sozinho. tem que ter apenas
botoes pra navegar entre a 'galeria' de dias/horas"*. The gallery itself is §1. What belongs
here is the **negative half**: with no bucket chosen, `renderFeed()` paints **nothing**
(`panel.js:1290–1328`) — the branch is `'Pick a day or an hour above.'`. It is gated by an arm
that can say NO (`_main/_panel2-dom-probe.js:754–766`), and that arm's **control is the
standing example of the whole doctrine**: the first control was written from the same
intuition as the code under test and was **wrong** (it predicted 4 rows); a real run against a
mutant with the auto-append restored painted **5**, and carried the text `too old`/`broken`
the intuition had not predicted. Recorded in the probe comment at `:757–764`.

### 11.6 The typing reveal — the mechanism, and the two bugs it exposed

**Mechanism.** The newest word of the forming line gets one `<span class="caption__ch">` per
character (`paintChars`, `panel.js:~381`), and `panel.css` reveals them with a **discrete**
`opacity` animation — `1ms linear forwards`, `animation-delay: calc(var(--c-i) *
var(--type-step, 26ms))` — gated **off** under `@media (prefers-reduced-motion: reduce)`.
`--type-step` is a *fallback* var, not a `:root` declaration, so a theme can set its own
speed or `0ms`, and **deleting the CSS block is a complete revert of the feature**. This is
why it was built this way: the reveal has a measured pair on otherwise identical bytes.

**Bug 1 — the first `paintChars` left every fresh non-typing word EMPTY**, so a whole line
rendered blank. Caught by ARM S. Fixed with an unconditional-but-guarded write (return early
only when the single child is already a text node equal to the word).

**Bug 2 — `"anove"`.** `paintWords` reuses word spans **by index**; when a word that had been
a *plain text node* became the newest (typing) word, the typing branch trimmed only *element*
children, so it appended char spans **after** the stale text node — `"a"` + `"nove"`. The fix
removes **every child that is not an element with `className === 'caption__ch'`** first. The
diagnosis was made with a temporary `console.log` (`TYPEDEBUG word="nove" typing=true
pre=["T:a"]`), not by reading.

**Four arms, and they can say NO.** `_main/_panel2-dom-probe.js:831–870`: (1) the reveal is
one word of char spans and no other word has any; (2) growth keeps the nodes already on
screen, adding one; (3) a word that stops being newest collapses back to ONE text node; (4) a
word typed onto a span that held plain text is not concatenated with it.

**Two mutant runs, which is what makes the arms evidence.** MUT-A (reveal-deleted copy):
`RESULT: RED — 4 violation(s) — 78/82`, rc=1, **all four arms named**. MUT-B (the stale-node
filter deleted): `RESULT: RED — 2 violation(s) — 80/82`, with `real=["oroeu",4,5]` vs
`want=["roeu",4,4]` and ARM S reading `"a prova dos anove"`. **The shipped panel is 82/82
GREEN, rc=0.**

**A defect in the arms themselves, found by the mutants and fixed.** The first revision
dereferenced `typingWord(prov).textContent` directly, so under MUT-A the probe **died with
`TypeError: Cannot read properties of null` at `:841`** — rc=1 with **no verdict line, no arm
name, no `real`/`want` pair**. That is exactly the "an instrument must answer a broken panel
with a NAMED RED, never a stack trace" rule, broken by me; every reader (`chOf`, `typingWord`,
`typingText`, `otherCharSpans`, `byText`, `charIdx`, `kids`) was made total.

### 11.7 The instrument's un-gated premise, now gated — and the vacuous PASS it caught

**The premise:** `on` vs `reduced` is a *pair* only if the two arms really ran in different
media states. `reducedMotion` was **printed per arm and never asserted**, so if headless Edge
had defaulted to `no-preference`, both arms would carry motion, the delta would measure the
noise between two identical runs, and the instrument would still print a number **and a
verdict**. This is the same defect as the `<style>`-injection control that was vacuous three
times (§10.1): *a premise that is only printed is not gated.*

**The gate** now sits immediately before the `on`-vs-`reduced` comparison in
`_main/_panel-anim-cost-arm.py`, asserts `{'reduced': True, 'on': False, 'relayout': False}`
with `is not` (so a MISSING field is a FAIL, not a pass), and sets `all_ok = False` with a
named line. Expected values are **measured, not assumed**: all eighteen earlier arm-runs print
the same pattern.

**Positive direction, on the real arm** (`_main/_panel-anim-cost-reveal-on.log`, this pass):
`MEDIA PAIR: reduced reducedMotion=True as expected`, `on … =False as expected`, `relayout …
=False as expected`.

**Negative proof, and it is decisive.** `_main/_panel-anim-cost-arm-mutmedia.py` — the real
arm with the single change `('reduced', False)` → `('reduced', True)` — returned
**`MUTMEDIA-EXITCODE=1`** and printed:

> `MEDIA PAIR: FAIL — the reduced arm reported reducedMotion=False, expected True: the arms are NOT in different media states, so every on-vs-reduced delta below compares an arm with itself and is VACUOUS`

then **`ANIMATION-ON vs OFF: PASS`** and `VERDICT: RED`. **The gate caught a real vacuous PASS
in a live run**: with both arms in one media state the instrument compared the animation to
itself (`led.mean` 0.355 "reduced" vs 0.262 "on" — pure noise) and called it PASS. Without
the gate that run would have shipped a confident *"the animation adds nothing."* Same run
re-showed `FORCED-LAYOUT CHANNEL: FAIL — the control moved it by only ±0.009 ms/frame`.

### 11.8 Two corrections to the record

1. **CRLF is not uniform, and the mutant anchor proved it.** `panel.js` / `panel.css` /
   `panel.html` / `caption-formulation.js` are **CRLF-only**; `history-gallery.js` and
   `_main\_panel-anim-cost-arm.py` are **LF-only** (the arm: 0 CRLF / 479 bare LF / 24613 B).
   A mutant anchor written with `` `n `` against `panel.js` failed `ANCHOR-A MISSING` for
   exactly this reason. **Recipe: `` `r`n `` for the panel, `` `n `` for the cost arm.**
2. **`debounce_ms` is 250, not 2000.** Measured from the shell's own log:
   `HOT_RELOAD_EVENT … debounce_ms=250`, with the whole event→applied sequence completing in
   under 2 s. The 2000 ms figure in `docs/shell-contract.md` describes the *guard* step, not
   this debounce. Also measured: `HOT_RELOAD_KEPT_HIDDEN reason=owner-had-it-hidden` — a
   reload never maps a window.

### 11.9 Own cost of this pass

~36 headless Edge launches, 2 HTTP server threads, 2 sampler threads, one 300 s 1 Hz loop,
~28 `node` oracle/probe runs (5 of them mutants), 1 harness regeneration, 3 mutant panel
copies created and deleted (one 888-file, two 9-file, one 10-file + 3 junctions), 3 full
battery runs (background; the third returned `BATTERY-EXITCODE=0` at 13:34:10), 2 theme
regenerations, 4 five-theme arm runs, 1 paint-probe run, 1 clobber of the shared
`panel-state.json` (reclaimed by the owner's shell, producerPid 28428), ~40 `edit` calls, 12
anim-cost arm runs (~90 s each), 1 hot-reload verification (one `LastWriteTime` touch, 21 log
polls at 2 s, bytes unchanged), and ~100 read-only greps/reads/JSON inspections. **No WMI, no
`Get-CimInstance` in any loop; the owner's shell (28428) and worker (29008) were never
touched; no window was mapped.**
