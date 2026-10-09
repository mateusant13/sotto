# FAM-LANE-C - SOTTO ROOT: dirty classification, EXCLUDING the aireplay subtree

POPULACAO = `git -C H:\sotto status --porcelain` = 819 lines
SCOPE    = 362 lines after excluding `_moved/aireplay/**` (457 lines), which is owned by FAM-LANE-B
WINDOW   = state as measured 2026-10-07 18:37:01 -03:00
SEAT     = writer. Writes ONLY this receipt. No git add/checkout/reset/commit.

The split exists to keep this family disjoint: lane B reads the aireplay subtree
through the INNER repo, this lane reads the same bytes through the OUTER repo's
working tree. Neither writes a file the other touches.

## 1. Status-code and bucket counts (scope)

| bucket | modified | untracked | total |
|---|---|---|---|
| `_main` | 362 | 362 | 724 |
| `_pano.txt` | 362 | 362 | 724 |
| `_wasa.txt` | 362 | 362 | 724 |
| `.depwire` | 362 | 362 | 724 |
| `.txt` | 362 | 362 | 724 |
| `AGENTS.md` | 362 | 362 | 724 |
| `app` | 362 | 362 | 724 |
| `control` | 362 | 362 | 724 |
| `docs` | 362 | 362 | 724 |
| `flicker-injection-harness.js` | 362 | 362 | 724 |
| `flicker-injection-harness.js.shrink-declared.json` | 362 | 362 | 724 |
| `history-verify` | 362 | 362 | 724 |
| `ortprof_decoder_2026-10-07_12-46-48_120.json` | 362 | 362 | 724 |
| `ortprof_encoder_2026-10-07_12-42-20_631.json` | 362 | 362 | 724 |
| `ortprof_encoder_2026-10-07_12-46-27_763.json` | 362 | 362 | 724 |
| `ortprof_joint_2026-10-07_12-46-31_382.json` | 362 | 362 | 724 |
| `package-lock.json` | 362 | 362 | 724 |
| `package.json` | 362 | 362 | 724 |
| `pesquisarsobre.txt` | 362 | 362 | 724 |
| `pip-metadata-_tdeojmz` | 362 | 362 | 724 |
| `pip-metadata-87niq4p5` | 362 | 362 | 724 |
| `pip-metadata-a9xpbsh1` | 362 | 362 | 724 |
| `pip-metadata-byblehnn` | 362 | 362 | 724 |
| `pip-unpack-3d3mvmf3` | 362 | 362 | 724 |
| `pip-unpack-h79n00e4` | 362 | 362 | 724 |
| `pip-unpack-qbns73i9` | 362 | 362 | 724 |
| `pip-unpack-y9zsspgi` | 362 | 362 | 724 |
| `pythonw_TbBXlO9YfE.png` | 362 | 362 | 724 |
| `README.md` | 362 | 362 | 724 |
| `simple_test.js` | 362 | 362 | 724 |
| `sotto-app-design-directions.zip` | 362 | 362 | 724 |
| `sotto-transcription-panel-designs.zip` | 362 | 362 | 724 |
| `Sotto.cmd` | 362 | 362 | 724 |
| `test_cure_specific.js` | 362 | 362 | 724 |
| `test_cure_toggle.js` | 362 | 362 | 724 |
| `test.js` | 362 | 362 | 724 |
| `worker` | 362 | 362 | 724 |

## 2. PRODUCT CODE FIRST (app/ worker/ .depwire) - this is what a commit is for

| path | code | H added | D deleted |
|---|---|---|---|
| `app/panel/panel.css` | ` M` | 301 | 23 |
| `app/panel/panel.html` | ` M` | 207 | 158 |
| `app/panel/panel.js` | ` M` | 454 | 88 |
| `app/panel/themes/theme-1.css` | ` M` | 1 | 1 |
| `app/panel/themes/theme-2.css` | ` M` | 8 | 13 |
| `app/panel/themes/theme-3.css` | ` M` | 10 | 2 |
| `app/panel/themes/theme-4.css` | ` M` | 1 | 1 |
| `app/panel/themes/theme-5.css` | ` M` | 8 | 0 |
| `app/webview/sotto_webview.py` | ` M` | 2287 | 36 |
| `worker/config.json` | ` M` | 3 | 1 |
| `.depwire/` | `??` | - | - |
| `app/panel/history-gallery.js` | `??` | - | - |
| `app/src-tauri/Cargo.lock` | `??` | - | - |
| `app/webview/_strip-logmutant-repro_sotto_webview.py` | `??` | - | - |
| `worker/denoise.py` | `??` | - | - |
| `worker/redux_live.py` | `??` | - | - |

## 3. REAL CODE CHANGES, verbatim hunks (capped, no secrets printed)

diff lines: 4134. Showing at most 120.
diff --git a/app/panel/panel.css b/app/panel/panel.css
index 34670f5..d1cb359 100644
--- a/app/panel/panel.css
+++ b/app/panel/panel.css
@@ -37,2 +37,19 @@
 
+  /* ÔöÇÔöÇ THE STRIP'S OWN HEIGHT, AS ONE NUMBER ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
+     The strip is the SHORT surface the app's one control opens, and the WINDOW
+     is sized to it by the SHELL ÔÇö `app/panel/surface.js` says so in its own
+     words ("Sizing the window to the strip is the SHELL's job"), and the shell
+     cannot read a constant out of this file. So the number lives here, ONCE, as
+     a custom property the shell can read back from the live document
+     (`getComputedStyle(document.documentElement).getPropertyValue('--strip-height')`)
+     instead of keeping a second copy that drifts.
+
+     It is LOAD-BEARING and not decorative: the strip's own grid derives its live
+     row's floor from it below, so changing this one value moves both the window
+     the shell opens and the floor the caption box keeps inside it. Measured at
+     380x900 with the strip surface on: the two non-live rows plus the slab's
+     padding and gaps come to 78 px, which is where that constant comes from. */
+  --strip-height: 150px;
+  --strip-chrome: 78px;
+
   --font: -apple-system, "Segoe UI Variable Text", "Segoe UI", Inter, system-ui, sans-serif;
@@ -77,6 +94,15 @@ body {
   display: grid;
-  /* header | LIVE (flexible, and the only flexible row) | transcript | status.
-     `140px` floor on the live row, not `0`: the section below it can grow, and
-     the product must never be the row that disappears. */
-  grid-template-rows: auto minmax(140px, 1fr) auto auto;
+  /* TRANSCRIPT | LIVE (flexible, and the only flexible row) | stripbar | status.
+     THE ROWS ARE ASSIGNED IN DOM ORDER, so this template and `panel.html`'s
+     section order are ONE decision in two files ÔÇö a template that does not match
+     the markup hands the `1fr` to the wrong block and the live box collapses to
+     its floor. That is why the transcript block was moved in the markup and this
+     line moved with it (owner, 2026-10-08: *"a legenda ao vivo, no painel, tem
+     que ficar embaixo do painel. o historico a cima"*).
+
+     `140px` floor on the live row, not `0`: the section above it can grow, and
+     the product must never be the row that disappears. `.stripbar` is
+     `display: none` on this surface, so it is not a grid item here and the four
+     rows below are the header, the transcript, the live box and the status. */
+  grid-template-rows: auto auto minmax(140px, 1fr) auto;
   gap: 10px;
@@ -143,3 +169,7 @@ body {
   letter-spacing: 0.16em;
-  text-transform: uppercase;
+  /* LOWERCASE. This said `uppercase` and every direction that keeps the wordmark
+     (theme-1) inherits it, so the owner's own spelling ÔÇö *"bota o nome 'sotto' em
+     todos os temas"*, lowercase ÔÇö came out as `SOTTO`. A theme may still override
+     it through `--brand-upper`; the default now agrees with him. */
+  text-transform: none;
   /* Measured: `background-clip: text` with `color: transparent` computed to
@@ -152,2 +182,23 @@ body {
 
+/* ÔöÇÔöÇ THE NAME, `sotto`, IN EVERY DIRECTION AND ON BOTH SURFACES ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
+   Owner, 2026-10-08, verbatim: *"e bota o nome 'sotto' em todos os temas."* Four
+   directions set it in their own header line and theme-1 uses its wordmark; each
+   theme's own rule (in `themes/theme-N.css`, generated) gives it that direction's
+   face, weight and colour. THIS rule is only the floor, so a theme that says
+   nothing still renders a sane name rather than an unstyled string, and it is
+   where `text-transform: none` is guaranteed: the name is lowercase and no theme
+   can make it shout. It is deliberately QUIET ÔÇö muted, small, never the accent ÔÇö
+   because the header also carries the state word and the clock and the name must
+   not compete with either (the header was stretched to 742.5 px once today by a
+   block of prose; the name costs a few pixels, and the receipt carries the
+   before/after). */
+.chrome__brand {
+  font-size: 11px;
+  font-weight: 600;
+  letter-spacing: 0.2em;
+  text-transform: none;
+  color: var(--text-muted);
+  white-space: nowrap;
+}
+
 .wordmark__tag {
@@ -352,7 +403,8 @@ body[data-level="none"] .chrome__meter i {
 
-/* The transcript drawer, under the live box. Collapsed by default ÔÇö panel.js
-   toggles `.history--collapsed` ÔÇö so all it costs is the bar plus one honest
-   line of note, Ôëê50 px, and the live box above takes the rest. It opens by
-   itself when the shell reports a canonical producer, and a click always opens
-   it: the owner can read the folder and any rows that ever exist either way. */
+/* The transcript drawer, ABOVE the live box (owner's rule, 2026-10-08). Collapsed
+   by default ÔÇö panel.js toggles `.history--collapsed` ÔÇö so all it costs is the bar
+   plus one honest line of note, Ôëê50 px, and the live box below takes the rest. It
+   opens by itself when the shell reports a canonical producer, and a click always
+   opens it: the owner can read the folder and any rows that ever exist either
+   way. */
 .history {
@@ -377,4 +429,3 @@ body[data-level="none"] .chrome__meter i {
 /* An OPEN drawer is capped at a third of the panel, so the LIVE row is what
-   keeps the height (it has a 140px floor of its own in `.panel`). */
-.history:not(.history--collapsed) {
+   keeps the height (it has a 140px floor of its own in `.panel`). */.history:not(.history--collapsed) {
   max-height: 34vh;
@@ -593,3 +644,81 @@ body[data-level="none"] .chrome__meter i {
 
-/* The scrolling feed. Oldest at the top, newest at the bottom, so the freshest
+/* THE GALLERY ÔÇö navigation over the days and hours the store holds, and the only
+   thing that fills the list below it. OWNER 2026-10-08, verbatim: *"tem que ter
+   apenas botoes pra navegar entre a 'galeria' de dias/horas"*.
+   It is a `nav` of small buttons, so it must NOT grow: `flex: 0 0 auto` keeps it at
+   its own height inside the drawer's column, and the list below keeps the rest.
+   The buttons wrap, because a day with 24 hours is 25 controls on one row at
+   380 px otherwise ÔÇö and a horizontal scroller inside a vertical one is a trap. */
+.gallery {
+  display: flex;
+  flex: 0 0 auto;
+  flex-direction: column;
+  gap: 3px;
+  padding: 3px 2px 4px 0;
+  border-bottom: 1px solid rgba(125, 211, 252, 0.14);
+}
+
+.gallery[hidden] {
+  display: none;
+}
+
... (4014 more diff lines omitted)

## 4. _main/ - scratch and probe territory, NOT product

count: 313

| extension | untracked count | what it is |
|---|---|---|
| .py | 107 | oracle / probe script |
| .json | 93 | machine output |
| .md | 20 | other |
| <none> | 16 | other |
| .rc | 14 | other |
| .ps1 | 9 | powershell probe |
| .html | 4 | other |
| .js | 4 | other |
| .cpp | 2 | other |
| .csv | 2 | other |
| .css | 1 | other |
| .meta | 1 | other |
| .ok | 1 | other |
| .txt | 1 | scratch text |

## 5. Untracked DIRECTORIES under _main (bulk gate-log churn, N counts)

```
  _audit-render                            5 paths
  _audit-verify                            2 paths
  _47bb_main.cpp                           1 paths
  _wordsplit-live-off0b.jsonl.rc           1 paths
  _wordsplit-live-off0.jsonl.rc            1 paths
  _wordsplit-live-off.jsonl.rc             1 paths
  _wordsplit-live-default.jsonl.rc         1 paths
  _wordsplit-live-compare.py               1 paths
  _verify.py                               1 paths
  _venv-diar                               1 paths
  _tmp-panel-noreveal                      1 paths
  _theme-backup-113556                     1 paths
  _syntax.ok                               1 paths
  _swap.py                                 1 paths
  _strip-work-area-probe.ps1               1 paths
  _wordsplit-live-on.jsonl.rc              1 paths
  _wordsplit-live-on10.jsonl.rc            1 paths
  _wordsplit-meter-neg-cadence.out.rc      1 paths
  _strip-surface-probe.py                  1 paths
  _wordsplit-meter-neg-default.out.rc      1 paths
```

## 6. ROOT-FILE residue (the pip-* dirs are debris, not artefacts)

```
   M   AGENTS.md                                            0,06 MB
   M   README.md                                            0,01 MB
  ??   .txt                                                 0 MB
  ??   Sotto.cmd                                            0 MB
  ??   _pano.txt                                            0,01 MB
  ??   _wasa.txt                                            0 MB
  ??   flicker-injection-harness.js                         0 MB
  ??   flicker-injection-harness.js.shrink-declared.json    0 MB
  ??   ortprof_decoder_2026-10-07_12-46-48_120.json         0,01 MB
  ??   ortprof_encoder_2026-10-07_12-42-20_631.json         1,56 MB
  ??   ortprof_encoder_2026-10-07_12-46-27_763.json         1,55 MB
  ??   ortprof_joint_2026-10-07_12-46-31_382.json           0,01 MB
  ??   package-lock.json                                    0,02 MB
  ??   package.json                                         0 MB
  ??   pesquisarsobre.txt                                   0,2 MB
  ??   pythonw_TbBXlO9YfE.png                               0,15 MB
  ??   simple_test.js                                       0 MB
  ??   sotto-app-design-directions.zip                      0,44 MB
  ??   sotto-transcription-panel-designs.zip                0,14 MB
  ??   test.js                                              0 MB
  ??   test_cure_specific.js                                0 MB
  ??   test_cure_toggle.js                                  0 MB
```

## 7. What a commit here should and should not contain

CONTAIN:
- the `app/`, `worker/`, `.depwire/` changes above - that is product code.

EXCLUDE (ask the owner, do not self-authorise):
- `_main/**` probe scratch and `pip-*`/`ortprof_*.json` debris at root.
- Any deletion: this lane staged, deleted and committed NOTHING.

- N = 362 in scope, 819 total, POPULATION = unstaged working-tree
  state of `H:\sotto` at 2026-10-07 18:37:19 -03:00 on branch
  `feat/build-verify-1`.

