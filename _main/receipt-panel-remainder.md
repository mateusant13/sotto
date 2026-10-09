# Receipt — the panel remainder lane (layout first, then the owner's finishing batch)

Lane: `app/panel/**` (+ `_main/_design-lane/gen_themes.py`, which OWNS the generated
theme CSS). The owner's shell was never touched: **shell pid 28428, worker pid 29008**,
alive for the whole lane (`Get-Process` at the end: worker CPU 9036 s, 549 MB, 5
threads). No visible window was opened by anything here — every browser arm ran
`msedge --headless=new`, and no shell/worker was ever launched.

---

## 0. What the owner was actually looking at, and why ("parece que ta wip")

**A comment TERMINATOR was written inside a comment block** in `panel.html` (next to
the controls). Everything after it stopped being a comment and became **naked text in
the body**, which the panel PAINTED: ~1067 characters of developer prose.

Measured consequence, on the shipped panel at 380x900, theme-1:

| block | before the fix |
|---|---|
| `.panel__header` (grid row 1) | **742.5 px** (33 x 22.5 px = the inherited `line-height`) |
| `.captions` (the live box) | 140 px — its FLOOR |
| `#captions-body` clientHeight | **115 px** (116 rows, 7122 px of scrollHeight) |
| `.history` | **8 px** — cut inside |

The owner's own `_main/panel-state.json`, taken from his RUNNING shell at 10:38:52,
says `live.scroll.client = 115`. **Two independent instruments, one number.** That is
the "not structured" he was looking at: ~2 lines of caption in a 900 px panel.

**Another lane fixed the comment at 11:17:22** (`git diff app/panel/panel.html`: 8
insertions, 1 deletion) — not this lane. This lane's instrument had already caught it
and would have caught it again; after the fix the same probe returned
`liveH=740.6 histH=47.7 clipped=0`.

**How the leak was NAMED, not guessed:** the header's height was a multiple of 22.5 px
under every row template, `tallest` (any descendant > 40 px) was EMPTY, and a node
census of the header with its element children detached found `text:NONWHITESPACE: 1`
carrying 1067 rendered characters. An empty flex box cannot be 360 px tall; something
non-element was generating line boxes. That is the transferable step.

---

## 1. TASK 1 — LAYOUT: the transcript above, the live box below. DONE, measured

### The rule, from the owner, verbatim
> *"a legenda ao vivo, no painel, tem que ficar embaixo do painel. o historico a cima"*

### Before -> after, block by block (theme-1, 380x900, state=live)

| block | BEFORE x,y wxh | AFTER x,y wxh | |
|---|---|---|---|
| header | 15,15 350x28 | 15,15 350x28 | unchanged |
| controls | 174.6,15 190.4x28 | 174.6,15 190.4x28 | unchanged |
| **history** | 15,803.6 350x47.7 | **15,53 350x47.7** | moved to the top |
| **live** | 15,53 350x740.6 | **15,110.7 350x740.6** | moved below |
| liveBody | 15,76.3 350x717.3 | 15,133.9 350x717.3 | moved |
| status | 15,861.3 350x27.8 | 15,861.3 350x27.8 | unchanged |
| order | `header, captions, stripbar, history, status` | `header, history, captions, stripbar, status` | |
| liveBelowHistory | dom=**False** y=**False** | dom=**True** y=**True** | |
| liveH / historyH | 740.6 / 47.7 | 740.6 / 47.7 | **the product kept every pixel** |
| overlaps / clipped / cutInside | 0 / 0 / [] | 0 / 0 / [] | |

**The two files are ONE decision.** `.panel` is a CSS grid and `grid-template-rows` is
assigned in DOM ORDER, so `panel.html`'s section order and
`panel.css`'s `grid-template-rows: auto auto minmax(140px, 1fr) auto` had to move
together. A template that does not match the markup hands the `1fr` to the wrong block —
and that is measured, not asserted: the `neg-rows` control does exactly that and the
live box collapses to its content.

The move was made by `_main/_panel-layout-reorder.py`, which **asserts** the current
order, moves the block whole, and proves the move is byte-reversible; it refuses if
another lane has edited the file first.

### The gate, both colours in one command
`py -3 _main/_panel-geometry-arm.py --themes theme-1..5 --state live,expanded` ->
**GREEN on all 10 arms** (`overlaps=0 clipped=0 cut=0`).

Controls: `--neg-arm` ->
* `neg-order` **RED** on the DOM order, on the y axis AND on the flexible row;
* `neg-rows` **RED** on the flexible row.

**Both controls were broken first and that is the lesson.** (a) The first `neg-order`
re-inserted the live block immediately AFTER the transcript — exactly where it already
was — so it was a NO-OP and came back GREEN. (b) The first `neg-rows` injected an inline
`<style>`, and **the panel's own CSP is `style-src 'self'`, so the browser REFUSED it**:
a silent no-op, GREEN again. The control now writes a same-origin stylesheet and links
it. A control that does not change the subject is not a control.

### Two instrument defects this lane found and fixed (they had been reporting lies)
* **The controls check was unsatisfiable.** It compared the control cluster's BOTTOM to
  the header's MIDLINE — which a vertically centred 28 px cluster can never satisfy, so
  a CORRECT layout went RED. Now it asks the real question: is the cluster's box inside
  the header's box.
* **`clipped` flagged the caption list inside `#captions-body`.** That box is
  `overflow-y: auto`: a caption list is SUPPOSED to be taller than it. The claim is
  about the panel's own rows, so the check now covers the rows that share the panel's
  column. It had been reporting a defect that was the product working.

---

## 2. `--strip-height`: the strip's height is now ONE number

Exposed on `:root` in `app/panel/panel.css`:

```
--strip-height: 150px;    <- THE NAME the shell can read back:
                             getComputedStyle(document.documentElement)
                               .getPropertyValue('--strip-height')
--strip-chrome: 78px;     <- MEASURED, see below
```

It is **load-bearing, not decorative**: the strip's grid derives its live row's floor
from it — `minmax(calc(var(--strip-height) - var(--strip-chrome)), 1fr)` = the 72 px
floor it always had. Change one number and the shell's window and the strip's floor move
together. The 78 px is measured on the strip surface at 380x900: top border+padding 11 +
live 822 + gap 8 + stripbar 26 + gap 8 + status 14 + padding+border 11 = 900.

Strip surface, all five themes: **GREEN** (`overlaps=0 clipped=0 cut=0 flex=live
liveH=822 stripVar="150px"`). Nothing in the strip DOM prevents the shell from sizing
the window: the strip's rows are `live | stripbar | status`, exactly the
`minmax(...) auto auto` the template already had.

**Still not mine, and still true:** Alt+C opens the 380x900 panel because the shell half
of the owner's decision (open the SHORT STRIP) was never implemented —
`bridge.setPanelSurface()` (`panel.js`) has no shell counterpart. The strip's DOM does
NOT block that.

---

## 3. The owner's item 1 — the `033` is GONE. Proven as a PAIR

It is the **per-line ORDINAL** (`lineOrdinal`), painted only by the `bcast` direction as
`001 11:33:16`, red on the forming line and grey on the closed ones. Removed from the
paint in BOTH creation sites (`renderProvisional` and the commit path) and from the
generated theme CSS (via `gen_themes.py`, then regenerated — never hand-edited).

**The pair, measured on the same document as the screenshot:**

| channel | value |
|---|---|
| `indexElements` | **0** |
| `timeElements` | 4 of 4 rows |
| `timeTexts` | `11:43:16, 11:43:16, 11:43:17, 11:43:17` |
| `timeColors` | grey, grey, grey, **rgb(255, 210, 74)** |
| `lastRowClass` | `caption caption--provisional` |
| `lastRowTimeColor` | **rgb(255, 210, 74)** (yellow — the live line) |
| `lastRowRail` | **solid 2px rgb(255, 106, 85)** (the red rail, NOT touched) |
| `dataIndex` | `['1','2','3','4']` — the ordinal survives as STATE |

Screenshots: `_main/_panel-paint-theme2-live.png` (2x, 920x1960) — the live line reads
`11:43:17 O som chega antes.` and the four closed lines above it. The yellow clock and
the red rail were kept because the owner did not complain about either; only the number
left.

**Also removed with it:** the inert `grid-template-columns` on `.caption` in theme-2
(nothing ever set `display: grid` on `.caption` — it was dead CSS), and the base
`.caption__index` rule.

---

## 4. Item B — the diagnostic prose is off the screen. FOUR sites, not one

The owner: *"tambem tira essas coisas como 'h sotto history 400 lines no canonial writer
400 lines the transcript'"*. He quoted a line count TWICE, so I swept for the family —
**four paint sites, all found, all stopped:**

| # | site | what it painted |
|---|---|---|
| 1 | `panel.js transcriptNoteText()` | `400 lines · no canonical writer — the transcript stays read-only.` |
| 2 | `panel.js updateLiveHint()` | `6 lines` above the captions |
| 3 | `panel.js applyTranscriptMode()` -> `#history-count` | `400 lines` in the bar |
| 4 | `panel.js` -> `#history-root` | `H:\sotto\history` — the full path |

**Nothing was deleted, it MOVED.** The honest sentence is still built
(`transcriptNoteTitle`) and still on the bar's `title`; the path is still in the button's
`title` and in `historyRootPath`; the counts are still the live state
(`historyEntries.length`, `#caption-list` children). The folder button keeps its
capability and gained a folder glyph, so the affordance is still VISIBLE — the path is
just no longer painted.

**Measured win:** the collapsed transcript bar went **47.7 px -> 30 px** and the live box
gained it (`liveH 740.6 -> 762` on theme-1). The screenshot shows the bar as
`TRANSCRIPT` + the folder glyph, nothing else.

---

## 5. Item 3 — the status is an ICON; the sentence is off the screen

`Receiving captions` is no longer painted. `#status-dot` carries `data-state` and the
three states differ in **SHAPE, not only colour** (a colour-blind reader loses colour):
idle = hollow ring, live = filled + a ring that breathes, error = red + ring.

**ONE DELIBERATE EXCEPTION, disclosed:** an **error** still paints its sentence.
`AGENTS.md` makes it law that the panel names the worker's own cause and the DEVICE, and
`_main/panel-exit3-oracle.py` gates it; an icon cannot say *"Silent audio device —
Mapeador de som da Microsoft — Input [MME]"*. He asked for the phrase he sees all day to
go; he did not ask for a silent death. The healthy sentence is not gone either — it is
**visually offscreen, not `hidden`** (`clip-path`, 1 px box), so a screen reader still
reads it.

The pulse is `opacity` on a pseudo-element bounded by `inset: 0` — compositor-only, no
layout, no blur, and cancelled under `prefers-reduced-motion`. **The first version used
`inset: -3px` and was caught by the instrument:** the halo spilled out of the 7 px dot,
the strip's 14 px status row read `scrollHeight 18 > clientHeight 13`, and the strip went
RED on `cutInside: ['status']`. A decorative glow that trips a layout gate is a real
defect; it is fixed and the strip is GREEN again.

---

## 6. Item 4 — `ao vivo` -> `live`, decided THEME BY THEME

| theme | before | after | why |
|---|---|---|---|
| theme-2 Broadcast | footer `AO VIVO` | **`LIVE`** | it is a status word |
| theme-3 Manuscrito | `rascunho ao vivo` | **`rascunho live`** | the phrase keeps its identity |
| theme-4 Cinema Card | `· ao vivo ·` | **`· live ·`** | it is the live-ness indicator |
| theme-1 Teleprompter | `LENDO` | **unchanged** | "reading" is not a translation of "live"; it is the direction's own word |
| theme-5 Instrumento | `OUVINDO` | **unchanged** | "listening", same reason |
| theme-2 header | `REC` | **unchanged** | a recorder's own lamp |

Forcing `LIVE` into the last three would have flattened three directions into one. He
said *"nos temas relevantes"*, and this is the reading: the word goes where it is a
status word, and stays where it is the direction's own voice.

---

## 7. The name `sotto`, in all five themes and on both surfaces

Owner: *"e bota o nome 'sotto' em todos os temas."* Lowercase, drawn by each theme's own
typography, never competing with the state word or the clock.

**Counted in the PAINTED DOM** (rendered elements only — the four hidden chrome blocks
hold their own text and are not counted):

| theme | header count | carrier | colour | text-transform | header text painted |
|---|---|---|---|---|---|
| theme-1 | **1** | wordmark | rgb(126,139,153) | none | `sotto LENDO Teleprompter` |
| theme-2 | **1** | `.chrome__brand` | rgb(191,192,194) | none | `sotto REC CH·01 11:51:25 Broadcast` |
| theme-3 | **1** | `.chrome__brand` | rgb(127,138,151) | none | `sotto rascunho live pág. 1 Manuscrito` |
| theme-4 | **1** | `.chrome__brand` | rgb(164,148,127) | none | `sotto · live · Cinema Card` |
| theme-5 | **1** | `.chrome__brand` | rgb(117,124,133) | none | `sotto ON Instrumento` |

**Strip surface: count = 1 on all five** (`sotto Live on Pause Open panel …`). The strip
hides the header, so it carries its own name — it could not come from the header.

`text-transform` was the trap and it is worth naming: theme-1's `--brand-upper` was
`uppercase` and theme-4's rule forced `uppercase`, so the markup's `sotto` would have
rendered `SOTTO` — the one property that silently overrules the owner's own spelling.
Both are now `none`, and the gate FAILS if any theme transforms the name.

**WHAT THE NAME COST (measured, before -> after, same instrument):**

| theme | header BEFORE | AFTER | delta | live box |
|---|---|---|---|---|
| theme-1 | 28 | 28 | **0** | 762 -> 762 |
| theme-2 | 48.3 | 50.5 | **+2.2** | 743.3 -> 741 |
| theme-3 | 28 | **41.5** | **+13.5** | 760.5 -> 747 |
| theme-4 | 28 | 28 | **0** | 759 -> 759 |
| theme-5 | 50.5 | 50.5 | **0** | 741 -> 741 |

**theme-3 is the one that did not fit for free and I am telling you rather than squeezing
it:** its header is a 2-column grid and the name made the line wrap to two rows. Nothing
overlaps, nothing is clipped, the live box still has 747 px — but it is 13.5 px the
caption box paid. If that is too much, the fix is to put the name in the same cell as
`rascunho live` instead of beside it; I did not do it because a smaller, tracked-out
manuscript header is a design decision, not a bug.

Screenshots per theme: `_main/_panel-brand-theme{1..5}.png` (2x). Geometry GREEN on all
five, panel AND strip.

---

## 8. The worker's CPU with the panel CLOSED vs OPEN — the parent's question

Instrument: `_main/_panel-worker-cpu-sampler.ps1` — **`Get-Process` on ONE known pid, 1
Hz, NO WMI, no process enumeration, one thread**, 300 s, 296 samples. It reads the
worker's CPU beside the panel's own published visibility (`_main/panel-visibility.json`).

| regime | worker CPU | wall | of one core |
|---|---|---|---|
| panel VISIBLE | 314.3 s | 244.6 s | **128.5 %** |
| panel HIDDEN | 17.9 s | 55.2 s | **32.4 %** |
| whole sample | 332.1 s | 299.8 s | **110.8 %** |

The panel toggled 12 times during the sample (`hotkey`, `click-outside`, `boot`,
`edit-tray`). **With the panel closed the live engine still burns 32.4 % of a core — it
does not stop**, which is the structural defect (the visibility hook was never
implemented; the stack law needs it).

**THE FALSIFIER, stated plainly: the difference between the two rows is NOT attributable
to visibility.** The audio source was not held constant (the owner was watching video),
and a quiet stretch costs the worker nothing whatever the panel is doing. What IS proven
is that the worker burns core with the panel shut. A clean test needs the SAME audio
through both regimes, or the panel held closed for a whole track.

---

## 9. The two questions the parent asked about the fixture

* **Is the live panel painting programmer prose as captions? NO — but the panel WAS
  painting developer prose, and it was the header defect in §0.** All 116
  `panel.caption-list` texts in the owner's `panel-state.json` are real transcription
  (English + Portuguese); a regex scan for `panel.js|panel.css|panel.html|<!--|CSS|DOM|
  fixture|surface=|caption__|TODO|grid-template|function |const ` returned **0 hits**.
* **The renderer fixture is clean.** `H:\aireplay\_main\render-panel-temas.py` uses
  **real PT-BR from the owner's own history**, quoted with file+line and verified against
  those files (it refuses to run otherwise). It never used document prose. The stale
  sentence is in `_main/receipt-panel-per-theme-chrome.md` §6.
* Re-run at the end of this lane: **`VERDICT: PASS`**, five captures, `window census 122
  samples / 0 visible`.

---

## 10. NOT DONE — and this is the part that matters

1. **The oracles that asserted the strings I removed are now STALE and I did not update
   them.** They are my lane's instruments and a RED oracle is a real signal, not noise:
   * `_main/_panel-chrome-probe.js:93-95` still expects `AO VIVO`, `rascunho ao vivo`,
     `· ao vivo ·` and (in its docstring) the per-line index;
   * `_main/_panel2-dom-probe.js:317,319,327,360` still expects `Receiving captions`;
   * `_main/_panel-clear-lifted-mutant.py` and `_main/_armE-fake-worker.py` still expect
     `Receiving captions` in the DOM.
   **Until those are updated, a green run of them means nothing** — they assert a
   contract the owner changed. This is the first thing the next pass on this lane should
   do.
2. **Item 2 / item A (the search surface): NOT STARTED.** The owner wants the search to
   stop listing transcriptions by itself and to become **buttons navigating a gallery of
   days/hours (24 h first, then 1 h each)**. The reason it is not done is honest scope:
   the bucketing needs a time-range query and the store's API lives in
   `app/panel/history-*.js`, which this lane is forbidden to touch. It needs either a
   store change from the lane that owns it or an explicit permission to extend it.
3. **Item C (the audio wave): NOT MEASURED.** The parent disabled it
   (`METER_HZ_DEFAULT = 0.0`), so no `peak` reaches the panel and there is nothing to
   confirm yet. What I can state without a measurement: the panel's meter path is wired
   to `onStats` and the wave is painted from the value it receives — **but I have no
   number for "the wave moves", and I am not going to write one I did not take.** When
   `peak` arrives, drive `onStats` with two different peaks and read the bars' computed
   heights; that is the falsifier.
4. **From the original brief, still untouched:** the cost instrument fix (LoAF filtered
   to the measurement window + a `forcedLayoutMs` channel forced by rAF + a control that
   can go RED), the letter-by-letter typing animation, removing `#quit-button`, removing
   `#clear-button`, the measured blur comparison (rgba vs small vs large), and the
   design-zip inventory/port.
5. **Not verified:** the live WebView2 path. Every measurement here is a headless
   Chromium arm on a copy of the real document at 380x900; the owner's own panel has not
   been re-read since the changes. The shell must hot-reload (or restart) to show any of
   this, and `panel-state.json` should then be re-read to confirm `live.scroll.client`
   grew.

---

## 11. Cost of this lane's own work

* **22 headless Edge launches** (~2 s each, sequential, no worker, no window), 1 HTTP
  server thread, 1 sampler thread, and one 300 s `Get-Process` loop at 1 Hz.
* **No WMI, no `Get-CimInstance Win32_Process`, no process enumeration, no window
  census** at any point — the sampler reads ONE pid it already knew.
* **No shell and no worker was ever launched or killed by this lane.**

## 12. Files this lane wrote

| file | size | sha256-16 |
|---|---|---|
| `app/panel/panel.html` | 37433 B | `8B532620BD6A783B` |
| `app/panel/panel.css` | 51514 B | `ED5F9D26893A7106` |
| `app/panel/panel.js` | 88543 B | `A138A8A5AFE16353` |
| `app/panel/themes/theme-1.css` | 22898 B | `DDBF9F9D203A34C0` |
| `app/panel/themes/theme-2.css` | 23230 B | `579B73E2F5C1808F` |
| `app/panel/themes/theme-3.css` | 22423 B | `553678A75D945DE0` |
| `app/panel/themes/theme-4.css` | 22361 B | `2CF7920762904016` |
| `app/panel/themes/theme-5.css` | 23888 B | `A786C8E6B9747AF2` |
| `_main/_design-lane/gen_themes.py` | 71733 B | `872BAEEF7CB9FDE2` |

Theme CSS is GENERATED: `gen_themes.py` was edited and re-run, and its idempotency was
tested first (backup + regenerate + compare: all five byte-identical) so the run could
not silently clobber a hand edit. Backup kept at `_main/_theme-backup-113556/`.

Instruments: `_main/_panel-geometry.js`, `_main/_panel-geometry-arm.py`,
`_main/_panel-layout-reorder.py`, `_main/_panel-worker-cpu-sampler.ps1`,
`_main/_panel-worker-cpu.jsonl`, `_main/_panel-paint-theme2-live.png`,
`_main/_panel-brand-theme{1..5}.png`, and the payloads
`_panel-geometry-{before,after,controls,brand,brand-strip,post-b}.json`.
