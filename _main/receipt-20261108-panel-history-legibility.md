# Panel transcript row — measured legibility fix

Owner, verbatim: *"ESSA LEGENDA TA PATETICA."* Scope: the transcript rows the
panel paints on `body[data-surface="panel"]`. No strip rule, no `--strip-*`
property and no `.history` drawer cap was touched (Main owns those).

## Plan

1. Read the real markup/JS/CSS: the row is `.hist` (there is no `.history__row`
   class anywhere in `app/panel/`), built by `makeRow()` in `panel.js`.
2. Measure the REAL cascade (not just the base sheet) with jsdom, before and
   after, via `_main/_panel-history-measure.js`.
3. Fix only the measured defects in `app/panel/panel-unified.css`, under
   `body[data-surface="panel"]`, with a selector strong enough to beat the
   generated themes' own `.hist__text` rule.
4. Check the duplicate-row question at its producer (`history_merge`), not in
   rendering.
5. Re-run the two existing instruments: `_panel2-dom-probe.js` and the
   Chromium clipping/contrast probe.

## 1. What actually wins (measured, theme-1 default)

There is no `.history__row` element. The real classes are `.hist`, `.hist__time`,
`.hist__text`, `.hist__folder`; the list is `#history-list.history__list`.

| Target | Winning declaration (before) | Source |
|---|---|---|
| `.hist` font-family | `var(--font)` → `"Barlow Condensed"` | inherited from the theme's `--font`; no row rule sets it |
| `.hist` font-size | `15px` | inherited; the row does not set one |
| `.hist` line-height | `1.5` | inherited |
| `.hist` padding | `4px 7px` | `panel.css:1006` (`.hist`) — unified did not touch it |
| `.hist` color | `var(--text)` → `#FFFFFF` | inherited |
| `.hist__time` font-family | `var(--font-mono)` → `"IBM Plex Mono"` | `panel.css:1027` + the theme's own `.hist__time` |
| `.hist__time` font-size | `10px` | `panel.css:1027` |
| `.hist__time` color | theme `--text-muted` = `rgba(255,255,255,.3)`; unified's `color-mix(...) !important` wins in Chromium | `panel.css` + `panel-unified.css:219` |
| `.hist__time` opacity | `0.78` (`--hist-time-opacity`) | `panel-unified.css:230` |
| `.hist__folder` (the per-row glyph — it is a FOLDER, not a copy icon) | `width/height:auto; padding:3px 4px`, colour `--text-faint`, 13 px SVG | `panel.css:1053` |
| list gap between rows | `3px` declared, **inert** | `panel.css:994` sets `display:flex; gap:3px`, `panel-unified.css:170` forces `display:block !important`, and block layout ignores `gap`. Measured second-row `margin-top: 0px` |

The two defects the screenshot shows are therefore measured, not aesthetic:

- **Text 9–12.5 px.** The generated themes carry their own
  `:root[data-theme=…] .hist__text` rule (specificity 0,3,0) which beats the base
  sheet, so the row used `--size-small`: theme-1 10 px, theme-2 **9 px**,
  theme-3 11 px, theme-4 12 px, theme-5 **9 px**, cinematic 12.5 px,
  `pd-bcast` **9.5 px**. The stamp was 10 px in every theme.
- **No separation.** The `3px` list gap cannot apply because the list is
  `display:block`; the row's own 4 px padding was the only air.

## 2. Instrument

`_main/_panel-history-measure.js` parses the shipped `app/panel/panel.html`,
loads every stylesheet `panel.html` links in document order and then the theme
file `theme-switcher.js` appends, builds rows exactly as `makeRow()` does, and
prints `getComputedStyle` per theme. `--state=before` removes the block between
`HISTORY-LEGIBILITY-BEGIN/END` from `panel-unified.css` before injection, so both
sides come from the same document and the same order.

jsdom limitation, stated rather than hidden: it resolves neither `var()` nor
`calc()` nor `color-mix()`. The script resolves `var()`/`calc()` itself from the
document's own custom properties and prints `raw:` plus `resolved:`; a raw
`color-mix()` string is left as-is, and its browser result is asserted by the
Chromium probe in §5.

## 3. Before → after

### theme-1 (default, owner screenshot's dark case)

| Property | Before | After |
|---|---|---|
| `.hist` padding | 4px 7px | **7px 9px** |
| `.hist` line-height | 1.5 | 1.5 |
| `.hist` grid columns | `46px minmax(0,1fr) 20px` | **`60px minmax(0,1fr) 20px`** |
| `.hist__text` font-family | `"Barlow Condensed"` (display face) | **`"Instrument Sans", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif`** |
| `.hist__text` font-size | **10px** | **13.5px** (dial × `--caption-scale`) |
| `.hist__text` line-height | 1.45 | **1.5** |
| `.hist__text` color | `#FFFFFF` | `#FFFFFF` |
| `.hist__time` font-size | **10px** | **11.5px** |
| `.hist__time` line-height | 1.5 | 1.5 |
| second-row `margin-top` | **0px** | **5px** |
| list `display` / `gap` | block / 3px (inert) | block / 3px (inert; the 5px margin is the separation) |

Raw measured after (theme-1):

```
.hist
  raw:      font-family=var(--font) | font-size=15px | line-height=1.5 | grid-template-columns=60px minmax(0, 1fr) 20px | gap=8px | padding-top=7px | padding-bottom=7px | padding-left=9px | margin-top=0px | color=var(--text)
  resolved: font-family="Barlow Condensed",ui-sans-serif,sans-serif | font-size=15px | line-height=1.5 | grid-template-columns=60px minmax(0, 1fr) 20px | gap=8px | padding-top=7px | padding-bottom=7px | padding-left=9px | margin-top=0px | color=#FFFFFF
.hist__time
  raw:      font-family=var(--font-mono) | font-size=11.5px | line-height=1.5 | color=var(--text-muted) | opacity=var(--hist-time-opacity, 0.78) | font-variant-numeric=tabular-nums
  resolved: font-family="IBM Plex Mono",ui-monospace,monospace | font-size=11.5px | line-height=1.5 | color=rgba(255,255,255,0.3) | opacity=0.78 | font-variant-numeric=tabular-nums
.hist__text
  raw:      font-family="Instrument Sans", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif | font-size=calc(13.5px * var(--caption-scale)) | line-height=1.5 | color=var(--text-primary, var(--text, #e8eef2)) | overflow-wrap=anywhere
  resolved: font-family="Instrument Sans", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif | font-size=13.5px | line-height=1.5 | color=#FFFFFF | overflow-wrap=anywhere
.history__list
  raw:      display=block | gap=3px | padding-top=0px
  separation between rows (2nd .hist margin-top): 5px
```

### pd-bcast (a generated panel design)

| Property | Before | After |
|---|---|---|
| `.hist` padding | 4px 7px | **7px 9px** |
| `.hist__text` font-family | `"IBM Plex Mono"` | **`"Instrument Sans", …`** |
| `.hist__text` font-size | **9.5px** | **13.5px** |
| `.hist__text` line-height | 1.45 | **1.5** |
| `.hist__time` font-size | **10px** | **11.5px** |
| second-row `margin-top` | **0px** | **5px** |

Raw measured after (pd-bcast):

```
.hist
  raw:      font-family=var(--font) | font-size=15px | line-height=1.5 | grid-template-columns=60px minmax(0, 1fr) 20px | gap=8px | padding-top=7px | padding-bottom=7px | padding-left=9px | margin-top=0px | color=var(--text)
  resolved: font-family="IBM Plex Mono","SFMono-Regular",monospace | font-size=15px | line-height=1.5 | grid-template-columns=60px minmax(0, 1fr) 20px | gap=8px | padding-top=7px | padding-bottom=7px | padding-left=9px | margin-top=0px | color=#FFFFFF
.hist__time
  raw:      font-family=var(--font-mono) | font-size=11.5px | line-height=1.5 | color=var(--text-muted) | opacity=var(--hist-time-opacity, 0.78) | font-variant-numeric=tabular-nums
  resolved: font-family="IBM Plex Mono","SFMono-Regular",monospace | font-size=11.5px | line-height=1.5 | color=rgba(255,255,255,0.45) | opacity=0.78 | font-variant-numeric=tabular-nums
.hist__text
  raw:      font-family="Instrument Sans", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif | font-size=calc(13.5px * var(--caption-scale)) | line-height=1.5 | color=var(--text-primary, var(--text, #e8eef2)) | overflow-wrap=anywhere
  resolved: font-family="Instrument Sans", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif | font-size=13.5px | line-height=1.5 | color=#FFFFFF | overflow-wrap=anywhere
.history__list
  raw:      display=block | gap=3px | padding-top=0px
  separation between rows (2nd .hist margin-top): 5px
```

### Same measurement across the seven measured themes (body text / stamp)

| theme | body before | body after | stamp before → after |
|---|---|---|---|
| theme-1 | 10px | 13.5px | 10 → 11.5 |
| theme-2 | 9px | 13.5px | 10 → 11.5 |
| theme-3 | 11px | 13.5px | 10 → 11.5 |
| theme-4 | 12px | 13.5px | 10 → 11.5 |
| theme-5 | 9px | 13.5px | 10 → 11.5 |
| cine-midnight-rain | 12.5px | 13.5px | 10 → 11.5 |
| pd-bcast | 9.5px | 13.5px | 10 → 11.5 |

All seven also went from `padding-top/bottom 4px` and `second-row margin-top
0px` to `7px` and `5px`, at line-height `1.5` (≥ 1.35).

Reproduce both sides:

```
node _main/_panel-history-measure.js --state=before theme-1 pd-bcast
node _main/_panel-history-measure.js theme-1 pd-bcast
```

## 4. The change

`app/panel/panel-unified.css` only, inside `body[data-surface="panel"]`:

- row: `grid-template-columns: 60px minmax(0,1fr) 20px` (46 px cannot hold
  `HH:MM:SS` at 11.5 px IBM Plex Mono: 8 × 0.6 em = 55.2 px), `padding 7px 9px`,
  `line-height 1.5`;
- `.hist + .hist { margin-top: 5px }` (the list's `gap` cannot work under the
  `display:block` this file already forces);
- row text: Instrument Sans (bundled, present on disk), `13.5px ×
  --caption-scale`, `line-height 1.5`;
- stamp: `11.5px`, line-height 1.5; its colour relation and 0.78 opacity are the
  ones already measured by `panel-history-clip-probe.mjs` and are unchanged.

The text rule had to be raised to
`html body[data-surface="panel"] .history__list .hist__text` (0,3,2 vs the
theme's 0,3,0): without it the theme's `--size-small` still won the font-size,
which the before/after run caught on the first attempt.

**Font on disk** (no missing file):

```
-rwxrwxrwx 17748 app/panel/fonts/instrument-sans-latin-400-italic.woff2
-rwxrwxrwx 16860 app/panel/fonts/instrument-sans-latin-400-normal.woff2
-rwxrwxrwx 17232 app/panel/fonts/instrument-sans-latin-500-normal.woff2
-rwxrwxrwx 17408 app/panel/fonts/instrument-sans-latin-600-normal.woff2
```

`panel.html` and `panel.css` are untouched.

## 5. Duplicate rows: not real on the current path

`rowIdentity(source, start)` (`panel.js:551`) is the row key on the live path;
the transcript list itself is fed by the shell's store, and the store decides
`append` / `replace` / `skip` in `history_merge` (`app/webview/sotto_webview.py:839`).
An identical commit returns `skip`, and the shell logs it
(`HISTORY_DUPLICATE_SKIPPED`, `sotto_webview.py:13742`); `panel.js` obeys
(`pushEntry`: `if (action === 'skip') return;`). Proof:

```
$ python _main/history-merge-oracle.py
ok  a1-igual-skip
...
ok  c1-uma-linha-por-enunciado
...
HISTORY_E2E_LOG ... HISTORY_DUPLICATE_SKIPPED time=03:37:24 bytes=82 | ...
VERDICT: PASS arms 22/22
```

So no rendering-side dedupe was added: that would hide a producer bug instead of
fixing it. (Two *legitimately* repeated sentences separated by another line stay
two rows — the oracle's `a9`/`a6` arms protect that.)

## 6. Verification

- `node _main/_panel2-dom-probe.js` → **GREEN, 87/87 arms**, unchanged. This
  probe injects **only `panel.css`** (`PANEL_CSS` at its line 86), which was not
  edited, so no arm can move; the run is the confirmation, not the argument.
- `node _main/panel-history-clip-probe.mjs` (headless Chromium, 45 themes):
  `CLIPPED rows in 0 theme(s)`, `LINE-CLAMPED rows in 0 theme(s)`,
  `STAMP UNREADABLE (<3:1) in 0 of 45 theme(s)`, `STAMP LOUDER THAN TEXT in 0`,
  `NOT LEFT-ALIGNED rows in 0`.
- `python _main/history-merge-oracle.py` → PASS 22/22.
- `git diff` of `panel-unified.css` contains no `body[data-surface="strip"]`,
  `--strip-*`, or `.history` max-height change.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: PanelCaptionLayout
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PanelCaptionLayout']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PanelCaptionLayout']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-08T06:41:45.900877+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PanelCaptionLayout']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PanelCaptionLayout']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — the brief calls the element `.history__row`; the real
  class is `.hist`. I probed the real markup first, but I should have written
  that correction down before reading CSS, since a literal search for the asked
  selector returns nothing and invites a wrong conclusion.
- **verificacao adicional** — a real-browser computed-style dump (Playwright)
  instead of jsdom; jsdom cannot resolve `var()/calc()/color-mix()`, so the
  timestamp colour needed the Chromium probe to be proven. Cost: one extra
  Playwright run (~25 s), which I did for clip/contrast but not for the numeric
  font dump.
- **checkboxes novas** — add to this class of work: *"for every property the
  acceptance names, print the winning declaration's selector + specificity, not
  only the value"*. A font-size value alone hid that the theme's 0,3,0 selector
  was beating unified; comparing specificity would have caught it before the
  first edit.
- **review por outro subagente** — sim, `sim-com-escopo`: a CSS reviewer should
  check the cascade against the two runtime-appended sheets (`cinematic.css`,
  `panel-designs.css`) and the 371 px wrap width.
- **gate-doubt**:
  - `verde-de-verdade:` `_panel2-dom-probe` 87/87 is green by construction for
    this change (it reads only `panel.css`); it verifies "nothing else broke",
    not the fix. `panel-history-clip-probe` is the load-bearing green: it loads
    the shipped `panel.html` in Chromium, so the new sheet is in its cascade. I
    did not pin a stale artifact — the probe reads the files at run time.
  - `falta-no-gate:` the clip probe checks geometry and stamp contrast, but NOT
    font-size, padding or inter-row spacing — the very properties this task
    fixes. A future edit could set the body back to 9 px and every gate would
    stay green.
  - `gate-melhor:` add an arm to `panel-history-clip-probe.mjs`: for the default
    theme assert `parseFloat(getComputedStyle('.hist__text').fontSize) >= 13`,
    `paddingTop >= 6`, and `marginTop >= 4` on the second row. Input that must
    stay RED: restore `.hist__text { font-size: var(--size-small) }` in
    `theme-1.css`.
- **confianca** — alta for the measured numbers and zero clipping; media for how
  13.5 px feels at 371 px (no human eye in the loop; that is the owner's call).
- **nao verificado** — visual appearance on the owner's screen; the skin mode
  (shadow-root mockups) beyond what the 45-theme probe covers; the 371×892
  window with a real scrollbar.


