# OMP panel — all themes (layout, controls, dragging)

Status: dispatched directly through OpenCode Go 2 / DeepSeek V4.1 Flash with the active `H:\env` config.
The dispatch TODO was attached to the request but was **not present as a file** in the tree; this file is
the lane's record, written from the dispatched scope and updated with what the source and the gates
measured.

## Required start

- Read this editable TODO first.
- Read the following skills before source edits: `C:/Users/Administrador/.agents/skills/task-resolver/SKILL.md`;
  `H:/sotto/.opencode/skills/bug-hunt-sotto/SKILL.md`; the design skill the dispatch names as
  `design-taste-frontend` (resolves to `C:/Users/Administrador/.agents/skills/_packs/design/taste-skill/SKILL.md`).
- Use the project's active bug-hunt procedure for the reported defect. Treat the current live process as
  STALE and do not claim runtime behavior verified.
- Do not delegate to another agent or relay through one. This is a direct OMP lane.

## Owned paths

- `app/panel/panel.html`
- `app/panel/panel.css`
- `app/panel/panel-unified.css`
- `app/panel/panel.js`
- `_main/panel-themes-oracle.mjs`
- `_main/panel-header-oracle.js`
- `_main/panel-drag-targets-oracle.js`

## Acceptance

- MECHANICAL: one composition works on all 59 selectable designs — header controls in the contract order
  (settings immediately left of close, X last), a search glyph that reveals the field on demand, no visible
  scrollbar while the feed still scrolls by wheel and keyboard, the history tools row reachable by mouse at
  any feed length, no bottom void, panel dragging targets that exclude the feed/inputs/dropdowns.
- JUDGMENT: inspect offscreen renders at representative and edge designs for spacing, row hierarchy
  (quiet stamp / bright line), void, and theme distinctness; keep each design's own identity instead of
  flattening 59 payloads into one.

## Existing gates

- `_main/panel-themes-oracle.mjs` and `--neg-arm` (all 59 designs)
- `_main/panel-header-oracle.js` and `--neg-arm`
- `_main/panel-drag-targets-oracle.js` and `--neg-arm`

All three are already wired in `_main/_audit-verify-all.cmd` (`panel-themes`/`red-as-expected-panel-themes`
at lines 612/614, `panel-header-oracle` and `panel-drag-targets-oracle` at 578–582).

## Shared constraints

- Read `AGENTS.md` and this TODO before editing; follow the task-resolver and bug-hunt-sotto procedures.
  Process freshness at this session is STALE (pid 50452, source files changed after its 2026-11-09 08:14:03
  start). No runtime symptom may be called verified.
- Do not launch, restart, show, or synthesize input to the Sotto app. Preserve every existing dirty change;
  never reset, restore, or rewrite unrelated files.
- No full battery, build, model benchmark, or mutation campaign without a current exclusive heavy lease and
  the project artifact preflight. Keep work source-focused; a focused gate uses its existing positive and
  negative arms.
- Keep all subprocesses hidden through the repo launcher / hidden execution method. No visible terminal,
  popup, browser, or owner-screen activity.
- Record the evidence, changed paths, and remaining runtime limits in this TODO.
- Do not add Bend laws for latency or budgets. No load-bearing Bend claim/proof was touched by this lane.

## Scope boundary

Own only the listed paths. Do not edit `history-store.js`, subtitle/overlay code, worker/model files, history
storage, battery wiring, `AGENTS.md`, or `_audit-verify-all.cmd`. `app/panel/brand-bridge.js`,
`theme-switcher.js`, `theme-tune.js`, `lazy-assets.js`, `skin-host.js`, `skin-layout.css` and `themes/*` are
read but not edited.

## Lane result

### What the source and the real page showed

Two defects, both measured on the shipped page in a private headless browser (no app launch, no owner
profile, no synthetic Windows input), both invisible to the three gates as they stood:

1. **The tools row scrolled away with the feed.** `panel-unified.css` made `.history__body` the scroller
   (`display:block; overflow:auto`), and `panel.js` pins the feed to its newest line on every render. The
   tools row is a child of that scroller, so at the pinned bottom it measured `top=-3940 px` on theme-1
   (48 rows, 380x900): `#history-search-button` and `#history-root` were painted above the viewport and no
   mouse could press them. The oracle's `search-on-demand` arm still passed, because it calls `.click()` on
   the element — an element does not have to be on screen to be clicked. A green arm on an unreachable
   control.
2. **A hidden grid item left a 333 px void.** `#transcript-note` carries `[hidden]`, which is `display:none`
   and therefore *not a grid item*. `grid-template-rows: auto auto minmax(0,1fr)` then put the body in the
   second (`auto`) row and left the `1fr` row empty. Measured on theme-1 with a four-row feed: `.history`
   80..857 (777 px) but `.history__body` 95..523.8 (428.8 px), i.e. 333 px of dead panel under the newest
   line. With the 60-row fixture the same miscount is invisible (the auto row is filled by content anyway),
   which is why the existing arms never saw it.

### Edits (this lane)

- `app/panel/panel-unified.css` (final shape; the first cut of this block was a 3-row grid and was
  re-expressed as flow for the size ratchet — see *Code-health ratchet* below)
  - `.history` is a **column flow** (`display:flex; flex-flow:column`), so its three children (bar, note,
    body) are placed by DOM order and a `[hidden]` note takes 0 px instead of displacing the body into an
    `auto` row. No `grid-template-rows`, no per-child `grid-row` placements.
  - `.history__body` and `.history__list` share one rule: `display:flex; flex-flow:column; flex:1;
    min-height:0; overflow:hidden; scrollbar-width:none`. The **list** overrides `overflow-y:auto`, so the
    list is the only scroller and the tools row + status note never scroll away; `::-webkit-scrollbar` is
    `width:0` for both (one `:is()` rule), which is what the A3 arm reads.
  - `.history__list > :first-child { margin-top: auto }` — a feed shorter than the panel sits on the floor,
    newest line directly above the status line, no lower void.
  - Duplicate `.history__list` rules (the ones that came before this block) removed. `.hist + .hist` stays
    at HEAD's `margin-top: 5px` — the first cut replaced it with a flex `gap` and this lane reverted that
    (one less hunk, same 5 px spacing).
- `_main/panel-themes-oracle.mjs`
  - `resolveScroller()`: the arms resolve the scroller the way the product does (`panel.js historyScroller`
    — nearest `overflow:auto|scroll` ancestor whose content overflows), instead of hard-coding
    `.history__body`. A4 (`scrollable`), A10 (`keyboard-scroll`) and the reported `overflow-y`/`scroller`
    detail use it.
  - New arm A5-bis `search-reachable`: the tools row must lie inside the drawer's box and inside the window.
  - New arm A5-ter `short-feed-on-floor`: the list is trimmed to its last 3 rows (detached, then re-attached
    before the evaluate returns, because the page is shared by every CSS theme), scrolled to the bottom, and
    the newest row's bottom must be the box's floor within 8 px.
  - Mutants M9 (drawer back to being the scroller → `search-reachable` must go red) and M10 (`margin-top:auto`
    → `0` → `short-feed-on-floor` must go red); M2 stays anchored on the body rule that holds
    `overflow:hidden; scrollbar-width:none`, M3 on the list's `overflow-y:auto`, and M9/M10 were re-anchored
    to the final one-line shapes when the block was compressed (a mutant anchored on the old grid text
    would have gone "not caught" for a reason that has nothing to do with the arm).
- `app/panel/panel.html`, `app/panel/panel.css`, `app/panel/panel.js`, `_main/panel-header-oracle.js`,
  `_main/panel-drag-targets-oracle.js`: **not edited by this lane.** They arrived dirty in the working tree
  (the 2026-11-09 panel/design work of the previous sessions) and were preserved byte-for-byte.

### Changed paths and hashes (after this lane's edits)

- `app/panel/panel-unified.css` — sha256 `4A5A7C8A4707BF24B59F25721E1A9664DF8A0432BB8D5C1ADDAAD1DA2A8296E0`, 26 028 B
- `_main/panel-themes-oracle.mjs` — untracked, sha256 `F4013FF0663B6297DF575E8F23A85163A303C6E00528EA03C694D92244D7CC1D`, 59 302 B
- Pre-existing dirty work in the owned set (not touched): `panel.html` +63/−48, `panel.css` +16/−18,
  `panel.js` +220/-19, `panel-header-oracle.js` +99/-31. `panel-unified.css` now shows +32/−17 against HEAD
  (after the size shrink; it was +94/−9 before), which still mixes that earlier panel work with this lane's
  block (the `.history` / `.history__body` / `.history__list` rules and the duplicate-rule removal described
  above).
  `panel-drag-targets-oracle.js` matches HEAD.
- Scratch evidence (not product code): `G:/Temp/opencode/shot-panel.mjs`, `shot-search.mjs`,
  `diag-skin.mjs`, `themes-positive2.json`, screenshots under `G:/Temp/opencode/shots/`.
- Run-unchanged (not edited by this lane; hashes in *Luna handoff*): `_main/panel-history-clip-probe.mjs`
  (35 068 B) and `_main/history-retention-fixture.py` (9 127 B).

### Code-health ratchet (integration request, 2026-11-09 ~12:0x)

The `code-health` oracle was RED on this lane's file inside a four-file change set. The ceiling is
per-file and the baseline was **not** touched:

| | bytes | lines |
|---|---|---|
| `_main/code-health-baseline.json` (untouched) | 26 040 | 511 |
| **before** (first cut, grid) | 29 240 → `RED bytes piorou de 26040 para 29240` | 562 → `RED lines piorou de 511 para 562` |
| **after** | 26 028 → `LESS ... 26028 B (-12)` | 492 → `LESS ... 492 linhas` |

What the 3 200 B / 51 lines were, and where they went (behaviour unchanged; every declaration the
oracle's mutants anchor on is still on its own line, and the mutants were re-anchored where the shape
changed):

- the two prose blocks that explained the two defects (~2 900 B / 51 lines) now live **here**, not in the
  CSS; the file keeps a one-line pointer to this TODO.
- the 3-row grid, its `grid-template-rows` and the five per-child `grid-row` placements were replaced by
  **flow order** (`.history`, `.history__body`, `.history__list` as column flex): same relations, ~600 B.
- the two `::-webkit-scrollbar` rules became one `:is(.history__body,.history__list)` rule (~47 B), and the
  list's `gap` was dropped by reverting `.hist + .hist` to HEAD's own 5 px margin (~25 B).

`code-health` still exits 2 overall, and the remaining RED lines are **outside this lane's paths** (the
integration request forbids touching them): `app/webview/sotto_webview.py` (bytes/lines),
`app/webview/youtube_cdp_source.py` (bytes/lines/defs/globals) and `worker/wasapi_loopback.py`
(bytes/lines/max_func). My file has no RED line left.

### Focused evidence

Hidden subprocesses only (`Start-Process -NoNewWindow` + redirected stdout; Node via `node.exe`, Playwright
headless `msedge`, no app launch, no synthetic input):

- `node _main/panel-themes-oracle.mjs --json …` (all 59 designs) → **rc 0**, `VERDICT: PASS -- themes=59
  arms=13 failed_arms=0 fatal_page_errors=0`; every arm `pass=59 fail=0`; `CAPTION-FACES distinct=true (33
  computed tuples)`, `CAPTION-PLATES distinct=true (58 computed beds)`; `PAGE-ERRORS 40` are the 20 skin
  mockups' unshipped wallpaper `.jpg`s (informational, as before).
- `node _main/panel-themes-oracle.mjs --neg-arm` → **rc 1** (the house convention for "caught"),
  `NEG-ARM: PASS -- 10/10 mutants caught`: M1 header-adjacent 0/4, M2 no-visible-scrollbar 0/4, M3
  scrollable 0/4, M4 no-bottom-void 0/4, M5 caption-plate 1/3, M6 no-demo-circles 0/4, M7 inventory
  refused, M8 keyboard-scroll 0/4, **M9 search-reachable 0/4**, **M10 short-feed-on-floor 2/2 fail**.
- Both re-run on the final bytes (26 028 B, sha256 `4A5A7C8A…`): positive **rc 0 in 41 s**, `themes=59
  arms=13 failed_arms=0`, every arm `pass=59 fail=0`; neg-arm **rc 1 in 100 s**, `10/10 mutants caught`
  (M9 `search-reachable 0/4`, M10 `short-feed-on-floor 2/2 fail`). One
  intermediate full run (12:1x) reported `caption-plate` red on `Quotes` only (`dbg.capEls=0`, i.e. the
  brand probe had no caption yet) while another lane was rewriting `history-store.js`; `--only Quotes`
  passed, and the full re-runs above passed 59/59 — recorded as a probe-timing flake, not as a defect.
- `node _main/panel-header-oracle.js` → **rc 0**, `VERDICT: GREEN -- 32/32 arm(s)`.
- `node _main/panel-header-oracle.js --neg-arm` → **rc 1**, `NEG-ARM VERDICT PASS -- 9 mutant(s), 0
  wrong`, every mutant turning the arm it names RED and the unmutated copy staying GREEN (`CONTROL … arms
  red: 0`).
- `node _main/panel-drag-targets-oracle.js` → **rc 0**, `VERDICT: PASS -- 12 arms, 0 divergentes` (feed rows,
  row text, list, search input and theme dropdown drag 0; panel, header, wordmark, controls wheel and strip
  drag 1).
- `node _main/panel-drag-targets-oracle.js --neg-arm` → **rc 1**, `NEG-ARM: PASS -- o mutante que apaga a
  exclusao dos rows foi apanhado`.
- All four were re-run after the size shrink changed the layout model (grid → flow): header 7 s / neg 67 s,
  drag 4 s / neg 2 s, same verdicts as above. `code-health` was re-run last: see *Code-health ratchet*.

### Luna handoff — 60-day retention DOM subcheck (lease-backed, 2026-11-09 ~12:3x)

The subcheck asked for: a 60-day transcript entry **visible and searchable by its stored context**, and a
200-day entry **excluded**, measured in the real panel DOM. The arms and the fixture for exactly this
already existed in `_main/panel-history-clip-probe.mjs` + `_main/history-retention-fixture.py`; what was
missing was the run under the central gate and the recorded DOM result. **Neither file was edited by this
lane** (probe sha256 `25438E6BDD356B2D914BCD241E436C4C2D306DE6298A07356468274A16B4F6D4`, 35 068 B, mtime
10:18; fixture sha256 `54FE600175AB430B2656BB5FA79CC1E28966F00331C800DBD5C6FC77CE01EF0D`, 9 127 B).

**Central performance gate (checked and held first, released after):**

- `python I:\!manager\tools\performance-gate.py status` → **rc 2**, `performance-gate: UNKNOWN`,
  `sample-unknown:disk counter read failed` (`Get-CimInstance Win32_PerfRawData_PerfDisk_PhysicalDisk`
  timed out after 12.0 s), `heavy_allowed=False`, `leases: heavy=0/1 light=0/3`.
- `acquire --kind heavy --owner omp-panel-history-clip --ttl 1800` → **rc 0**:
  `granted heavy lease id=230bfe41f0ea4c84b2c631f0b5a06791 owner=omp-panel-history-clip ttl=1800.0s
  expires_in=1800.0s state=green`.
- `validate --id 230bfe41f0ea4c84b2c631f0b5a06791 --kind heavy` → **rc 0**: `valid heavy lease id=… owner=
  omp-panel-history-clip expires_in=1728.2s state=green` (the three earlier `rc 3` usages were missing
  `--kind`, not a policy refusal).
- The lease was held for both probe runs and released right after:
  `release --id 230bfe41f0ea4c84b2c631f0b5a06791` → **rc 0**, `released heavy lease id=… owner=
  omp-panel-history-clip`.

**Positive arm — `node _main/panel-history-clip-probe.mjs`, rc 0 in 9 s:**

```
RETENTION DOM: feed rows=3 (want 3) 60-day=visible near(179d)=visible 200-day=excluded context="device:mic · Code: main.py · https://example.com/watch"
RETENTION ARMS feedCount=GREEN feedSixty=GREEN feedNear=GREEN feedNoLeak=GREEN ctxPaint=GREEN searchCtx=GREEN searchNoLeak=GREEN chipIsHourOnly=GREEN dayInTitle=GREEN
```

The same run kept the panel-identity half green: `ROW FACE: 28 distinct (family + size) across 45 theme(s)`,
`NOT LEFT-ALIGNED rows in 0 theme(s)`.

**Negative arm — `node _main/panel-history-clip-probe.mjs --neg-arm`, rc 1 in 7 s** (the house convention:
the control exits 1 when it catches, and each mutant must red its own arm):

```
  mutant HISTORY_RETENTION_H 4320 -> 48: feedCount=RED feedSixty=RED feedNear=RED ctxPaint=RED
  mutant HISTORY_RETENTION_H 4320 -> 2160 (90 days): feedNear=RED
  mutant context paint removed: ctxPaint=RED
  mutant context note removed: searchCtx=RED
  mutant window predicate admits everything: feedNoLeak=RED
  mutant search window removed: searchNoLeak=RED
NEG-ARM: PASS -- identity caught (1 face(s), the positive measures 28); 6/6 retention mutant(s) caught
```

**What the numbers mean, and what they do not:**

- `feed rows=3 (want 3)` is the fixture's own expectation over the real history root: the 60-day line, the
  near-window line (`HISTORY_RETENTION_H - 1 day`) and the fresh line; the 200-day line is on disk but
  excluded from the tail. The context string is the one the *writer* stored (`history_append`'s five
  fields rendered by the page), not a literal in the probe.
- `searchCtx` / `searchNoLeak` answer from `SottoShell.history_search` over that root, with a query
  (`main.py` / `other.py`) that appears **only in the context**, never in the line text — so a hit proves
  the search reached the context, and the 200-day line staying out proves the search window too.
- Scope the fixture pins: it makes the store's prune an explicit no-op (`_history_pruned_stamp`), because
  the *store's* retention is `_main/history-context-oracle.py`'s subject (s19–s21), not this probe's. This
  gate owns the PANEL window, the context paint and the search over a real root.
- Battery wiring was **read, not edited**: `_main/_audit-verify-all.cmd` lines 584/585 already run
  `panel-history-clip` and 616/617 run `red-as-expected-panel-history-clip` (expecting `NEG-ARM: PASS`),
  both naming `_main/history-retention-fixture.py`. No battery change was made or needed.
- Ceiling unchanged: this is the shipped bytes in a private headless browser. The live shell is STALE
  (pid 50452), so the DOM result is `fixed, NOT verified` against the running app, like everything else in
  this lane.

### Judgment (offscreen renders, inspected by eye)

- **Void** — theme-1 with 48 rows, re-measured after the size shrink: `.history` 80..857, `.history__body`
  95..857, tools row 95..119, `.history__list` 125..857, newest row at the floor. With **4 rows**: the
  feed's first row starts at 455.3 and the newest row's bottom is the floor (857), status line 867..890 at
  the panel's bottom edge; `Timeline` the same shape (rows from 507.6, floor 854.8). The empty space is
  above the transcript, none below it.
- **Tools reachable** — magnifier and folder glyph paint at 95..119 in every inspected design, including
  with the search field open (field 100..124, 292 px wide, focused; the list reflows below it).
- **Spacing** — row heights follow each design instead of one global number (re-measured after the shrink,
  unchanged by it): theme-1 94.4 px, theme-2 77.8, theme-3 92.3, theme-4 99.5, theme-5 78.0, `Timeline`
  80.8, `cine-adobe` 75.8, `pd-tele` ~246 (its own `--size-caption`; tall rows are that design's identity,
  not a bug). Inter-row gap 5 px, uniform (the `.hist + .hist` margin), rows start at 125 in the seven
  panel designs and at 59 in `cine-adobe`, which insets its drawer differently.
- **Hierarchy** — the stamp is the quiet element and the line is the bright one in all inspected renders
  (theme-1..5, `Timeline`, `GlassCards`, `pd-tele`, `cine-adobe`); the folder glyph stays faint at the row's
  right edge, so the eye reads time → text → affordance.
- **Theme distinctness** — 33 distinct caption faces and 58 distinct caption beds across 59 designs; 45 CSS
  designs plus 20 frozen skins (6 shared ids → 59 picker entries). Skins paint the vendor mockup in `#skin`
  shadow DOM as ordered, with our `.history` laid out underneath and measured.

### Independent review / evidence

None. The gates are self-run and the renders self-inspected. They are not text reads — the oracle executes
the real page, the real wheel/keyboard scroller and real layout, and its negative arm mutates *copies* of the
panel and requires the named arm to go red — but there is no separate author/reviewer split, so the ceiling
for runtime behavior is `fixed, NOT verified`.

### Remaining uncertainty

- The live app is STALE (pid 50452 predates the files). Nothing here was observed in the running shell; the
  measurements are the oracle's and the probe's own headless renders of the shipped bytes.
- `.history--collapsed` keeps its `display:none` body from `panel.css`; nothing writes the class today. With
  flow the hidden body simply takes no space, so the old `minmax(0,1fr)`-row trap that note carried is gone
  with the grid — but the collapsed state itself is still unexercised by any gate.
- The 20 skins are frozen vendor mockups by owner order, so their `img/*.jpg` wallpapers are absent and the
  page reports 40 non-fatal load errors. The arms measure the underlying `.history` for them and say so.
- `panel-dragging` is proved on the exclusion list only; the actual window drag on the live app is a shell
  behaviour outside these three gates.
