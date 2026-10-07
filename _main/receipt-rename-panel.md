# Receipt — `app/electron/` → `app/panel/` + `app/_legacy-electron/` (2026-10-07)

**Brief (parent):** *"electron? tamo usando electron? nao devia. e se nao tamo, muda o nome"* — the app is
**WebView2** (`app/webview/sotto_webview.py`), not Electron. The folder `app/electron/` was named after a
shell the app is not, and it mixed the LIVE panel assets with the DEAD earlier Electron shell.

**Verdict: DONE. `app/electron/` no longer exists; the app runs from `app/panel/` and is transcribing.**

---

## 1. What moved where

| destination | contents | files |
|---|---|---|
| `app/panel/` | `panel.html`, `panel.css`, `panel.js`, `caption-formulation.js`, `history-source.js`, `history-store.js`, `surface.js`, `theme-switcher.js`, `themes/{theme-1..5.css,themes.js}`, plus **`package.json`** (see §2) | 15 |
| `app/_legacy-electron/` | the WHOLE dead arm: `main.js`, `preload.js`, `worker-bridge.js`, `hot-reload.js`, `main.js.backup`, `bridge-selftest.js`, `bridge-single-instance-selftest.js`, `worker-proc-count-probe.js`, `dom-probe.js`, `flicker-preload.js`, `transcript-append-oracle.js`, `package.json`/`package-lock.json`, `node_modules/` (1176 files), `_hotreload/`, `_single-instance/`, `README.md`/`BRIDGE.md`/`HOTRELOAD.md`, all its logs and stale `.current`/`.bak`/`_modified` scratch | 1263 |

**Nothing was deleted.** `Move-Item` only; the empty directory was removed after asserting it was empty
and that the resolved path was exactly `H:\sotto\app\electron`.

### sha256 verification of the move

```
BEFORE: 1268 files, 345.5 MB   (manifest: _main\_rename-manifest-before.csv, relpath + sha256 + mtime)
left in app\electron: 0
app\electron removed: True
app\_legacy-electron: 1254 files
before=1268 after=1268
MISSING: 0   ADDED: 0   DIFFERENT: 0
SHA256 MOVE VERDICT: ALL 1268 FILES BYTE-IDENTICAL AT THE NEW PATHS
```
`app/panel` is now 15 files (14 moved + the `package.json` in §2); `app/_legacy-electron` is 1263
(1254 moved + 9 `__pycache__/*.pyc` written by the `py_compile` in §5).
No file under `app/electron/**` changed while the work was in flight (the before-manifest was taken
immediately before the move and every hash matched).

---

## 2. THE REGRESSION THIS MOVE CAUSED, CAUGHT BY THE PARENT, AND ITS FIX

**Symptom:** after the move, 7 battery steps went red with
`TypeError: F.createEngine is not a function` / `createEngine absent in app\panel\caption-formulation.js`.

**Cause, measured, not guessed:** Node picks a `.js` file's module type from the **nearest
`package.json` walking up from that file**. Before the move that was `app/electron/package.json`
(`sotto-electron`, **no `type` field** → CommonJS). After the move the nearest one is
`app/package.json`, which carries **`"type": "module"`** (it belongs to the older Vite/Svelte/Tauri tree
at `app/src`). So every `require('app/panel/<file>.js')` in `_main/` resolved as ESM and returned an
**empty namespace**:

```
node -e "const m=require('H:/sotto/app/panel/caption-formulation.js'); console.log(Object.keys(m))"
  keys=            createEngine= undefined            <- the regression
node -e "...require('H:/sotto/app/_legacy-electron/caption-formulation_modified.js')..."
  keys= createEngine                                  <- the old dir still resolves as CJS
```

**Fix — a module-type marker, NOT a change to any panel file:** `app/panel/package.json` =
`{"type": "commonjs"}` with a long `description` saying why it exists and that it must not be deleted.
`app/package.json` was deliberately NOT touched (its `type: module` is load-bearing for Vite/Svelte).

```
node -e "require('H:/sotto/app/panel/caption-formulation.js')"
  keys= createEngine,formulate,describeReadiness,agreedPrefixLength,words,SENTENCE_GAP_S,...
  createEngine= function
node app\_legacy-electron\transcript-append-oracle.js   -> RESULT: GREEN  rc=0
```

This is the single most transferable finding of the rename: **moving a `.js` file across a directory
boundary can change its module type, and the failure is silent (an empty namespace, not a throw).**

---

## 3. Every reference updated

### 3a. Live path (must be true for the app to run)
| file | change |
|---|---|
| `app/webview/sotto_webview.py` | `PANEL_DIR` `'electron'`→`'panel'` + 7 comment/docstring path mentions (`:4,:6,:8,:57,:167,:187,:1001,:2416,:2755,:3632,:4880`) |
| `app/webview/hot_reload.py` | `:5` — the port-source mention → `app/_legacy-electron/hot-reload.js` |
| `app/webview/run.cmd` | `:20-22` — "app\electron\ is the EARLIER shell" re-stated: the panel is `app\panel\`, the earlier shell `app\_legacy-electron\` |
| `app/webview/README.md` | `:147`, the "Electron tree is legacy" section (`:159-175`), `:184`, `:195` |
| `AGENTS.md` | the two Layout rows (`app/electron/` + its panel row) replaced by `app/panel/` and `app/_legacy-electron/`; `:124`, `:140`, `:155`, `:229` |
| `README.md` | `:23`, `:26`, `:150` |
| `app/package.json` | `"main": "electron/main.js"` → `"_legacy-electron/main.js"` (the dead arm's manifest, kept resolvable) |
| `.gitignore` | `app/electron/_hotreload/`, `_single-instance/`, `_dom-probe-*.json` → `app/_legacy-electron/...` |

### 3b. Runnable instruments (`_main/`, root tests)
*Path literals re-pointed (`'app','electron'`→`'app','panel'`, `app/electron/`→`app/panel/`,
raw `H:\sotto\app\electron\...`→the new root):*
`_audit-history-dead.js`, `_lane2-reset-probe.js`, `_panel2-dom-probe.js` (incl. its **functional**
harness-source assertions at `:556-560`), `_panel2-repeat-probe.js`, `_review-panel.js`,
`caption-renderer-integration.js`, `history-route-oracle.js`, `history-producer-gate.js`,
`historico-vs-redux-probe.js`, `join-harness.js`, `live-vs-history-source-oracle.js`,
`panel-live-vs-history-probe.js`, `panel-state-guard-gate.js`, `probe-20261007-node-twin.js`,
`route-stamp-gate.js`, `silent-fallback-probe.js`, `vad-renderer-arms.js`,
`run-cmd-exit-oracle.py` (both temp-tree builders + 2 docstring mentions),
`panel-hidden-at-startup-oracle.py`, `_audit-probe-20261007.py`, `measure-readiness.py`,
`measure-asr-warmup.py`, `_probe/hotreload-acceptance.py`, `redux-flag-gate.py`, `_oss_oracle.py`,
`_design-lane/gen_themes.py` (writes `themes/`), `_design-lane/contrast.py`,
`_design-lane/theme-assert-lib.js`, `_audit-render/stub.js`, `_audit-render/make-harness.py`
(`SRC` + `REL`), `_audit-verify-all.cmd` (`node app\_legacy-electron\transcript-append-oracle.js`),
`simple_test.js`, `test_cure_specific.js`, `test_cure_toggle.js`,
`app/_legacy-electron/transcript-append-oracle.js` (its engine pointer → `../panel/caption-formulation.js`,
and its usage lines).
*Regenerated, not hand-edited:* `_main/_audit-render/panel-harness.html`
(`python _main\_audit-render\make-harness.py` — every asset now `../../app/panel/...`).

### 3c. Frozen/dated fixtures — only the FUNCTIONAL literal re-pointed
`_prefix-under-test.py`, `sotto-webview-prefix-20261006.py`, `_panel-clear-lifted-mutant.py`,
`_panel-verdict-benign-mutant.py`, `_ppv-paintorder-mutant.py`, `_shell-visible-neg-arm.py`,
`_tap-restart-prefix-mutant.py`, `_restart-30s-prefix-mutant.py`, `app/webview/_vis-live-sotto_webview.py`
— each had exactly one executable path literal (`PANEL_DIR`) re-pointed to `'panel'`, because their
oracles (`panel-exit3-oracle.py`, `run-cmd-exit-oracle.py --neg-arm`) would otherwise die with
`PANEL_MISSING` and read RED for the wrong reason. Their **prose is the frozen revision's own text and
was deliberately left** (they are dated copies: one is literally named `…-20261006.py`).
`_main/_redux-gate-mutants/*.py` were **regenerated from the edited shell at 05:19:05** by
`redux-flag-gate.py` and already carry `app/panel` — no edit needed.

---

## 4. The remaining `app/electron` hits — final census and why each stands

```
$ grep -rn "app[\\/]electron" (repo, excluding node_modules/.git/_audit-verify/runs/models/pycache/dist/src-tauri)
TOTAL: 1235 hits in 541 files
  618  logs + JSON/TXT evidence (records)            <- R7
  219  docs/** (dated audits/receipts)               <- R3
  213  OTHER: dated snapshots + frozen fixtures      <- R4/R5
  154  _main/*.md dated receipts                     <- R3
   20  app/_legacy-electron/** (dead arm internals)  <- R4
    9  worker/**                                     <- R6
    2  app/panel/** (the one dated comment)          <- R2
```
* **R1 — updated (0 hits left):** §3a-3c. Every RUNNABLE reference resolves; nothing in this list is code.
* **R2 — `app/panel/caption-formulation.js:7`** (`app/electron/panel-run.log`): a **dated measurement
  record of 2026-10-06** inside a comment. Left **by the parent's explicit ruling** (Answer A: fix the 5
  that name a live sibling, leave the 6th). This is a decision, not an oversight.
* **R3 — `docs/**` and `_main/*.md` (373 hits):** dated audits and receipts. The parent's rule: *"in
  historical logs/receipts, LEAVE them (they are records of what was true then)"*. The three docs that
  are LIVE (AGENTS.md, README.md, app/webview/README.md) were corrected.
* **R4 — `app/_legacy-electron/**` (20 hits):** the dead arm's own files, docs and logs
  (`HOTRELOAD.md`, `BRIDGE.md`, `README.md`, `main.js`, `hot-reload.js`, the `.current`/`.bak` scratch).
  They describe the tree they sit in, as it was. The arm is **no longer runnable as an arm** — its own
  `path.join(__dirname,'panel.html')` now points at a directory that no longer holds the panel — and that
  is disclosed rather than papered over: the panel lives in `app/panel/`, and the owner ruled
  *"sem fallback. webview2 é pra funcionar, pronto."*
* **R5 — dated snapshots/fixtures (213):** `_main/_ordem-before/sotto_worker.py`,
  `_main/control/caption-formulation-pre.js`, `_main/_tmp-head-worker.py`, the frozen shell copies of
  §3c (their prose), the `.log.mirror`/`.stdout` pairs, `flicker-injection-harness.js` (already broken
  before this rename: it loads `app/electron/index.html`, which never existed — the real file is
  `app/index.html`), and `test.js` + `*.js` files that `require('electron')` (the npm PACKAGE, not a path).
* **R6 — `worker/**` (9 hits):** comment references in `worker/sotto_worker.py` (`:1683`, `:1771`,
  `:1922`, `:2296`) and `worker/README.md`. **The brief forbids editing anything under `worker/`, so
  these are left untouched and reported** — they are the one place where a stale `app/electron/…`
  mention still describes a LIVE asset. Owner's call; the fix is a 4-line comment change.
  (The 40 hits in `_main/_redux-gate-mutants/*.py` are COPIES of that worker file: they carry the same
  comments and are left consistent with it.)
* **`_main/_redux-producer-path.js` (4 hits): LEFT ALONE ON PURPOSE.** Another lane was rewriting it
  while this lane worked (mtime 05:19:26, then 05:20:15, after this lane's edit attempt failed with
  *"file changed since it was read"*). That lane made it path-tolerant — it tries `app/panel/` first and
  PRINTS the path it used, with `app/electron/` and `app/_legacy-electron/` as dead fallbacks — and its
  prose explains the move. Per the parent's rule (*"do not fight it, do not reconcile it, report it"*)
  this file was not touched. Its fallback list still names two paths the engine is not in; harmless
  (the engine exists only in `app/panel/`), and its owner will trim it.

---

## 5. Syntax gates

```
$ node --check  (every .js that MOVED)
app/panel:    caption-formulation.js 0  history-source.js 0  history-store.js 0  panel.js 0
              surface.js 0  theme-switcher.js 0
legacy:       bridge-selftest.js 0  bridge-single-instance-selftest.js 0
              caption-formulation_modified.js 0  dom-probe.js 0  flicker-preload.js 0
              hot-reload.js 0  main.js 0  preload.js 0  transcript-append-oracle.js 0
              worker-bridge.js 0  worker-proc-count-probe.js 0           (17/17 rc=0)
$ node --check  (every edited _main .js)                                   23/23 rc=0

$ python -m py_compile app\webview\sotto_webview.py                    rc=0
$ python -m py_compile app\webview\hot_reload.py app\webview\panel_state.py  rc=0
$ python -m py_compile  (25 more touched .py incl. all fixtures)            rc=0, 0 failures
$ python -m py_compile  (9 .py in app/_legacy-electron)                     rc=0
```

---

## 6. The battery — and a defect IN the battery that every earlier receipt inherited

`cmd /c "_main\_audit-verify-all.cmd"`, three runs: baseline (before the move, `_main\_rename-baseline-battery.log`),
post-move (`_main\_rename-final-battery.log`), final (`_main\_rename-final2-battery.log`).

**THE BATTERY WAS LYING ABOUT `rc`.** Steps 39-113 are `if exist ( … )` blocks and each printed
`rc=%ERRORLEVEL%` **inside** the block. In `cmd.exe` a parenthesised block is parsed as ONE command, so
`%ERRORLEVEL%` is expanded **at parse time** — those 12 steps printed the errorlevel of whatever command
preceded the block, never their own. Two "pre-existing reds" (`panel-state-guard-gate rc=1`,
`lane2-reset-probe rc=2`) were **artifacts of that expansion**; run directly both are **GREEN rc=0**.
Fixed the reporter: `setlocal EnableDelayedExpansion` + `rc=!ERRORLEVEL!`. (The file has no literal `!`.)
This is a **behaviour fix beyond path references** and is disclosed as such.

**Final run — every step, honest rc:**

| step | rc | | step | rc |
|---|---|---|---|---|
| py_compile sotto_webview.py | **0** | | lane2-reset-probe | **0** |
| py_compile hot_reload+panel_state | **0** | | lane3-verdict-probe | **0** |
| py_compile sotto_worker.py | **0** | | lane4-tap-stop-probe | **0** |
| py_compile wasapi_loopback+lang_prompt | **0** | | audit-history-dead | **0** |
| transcript-append-oracle | **0** | | worker-start-wiring | **0** |
| live-vs-history-source-oracle | **0** | | embedded-js-check | **0** |
| historico-vs-redux-probe | **0** | | lane1-worker-default-arms | **0** |
| **history-producer-gate** | **1** | | review-f1f3 | **0** |
| panel-state-guard-gate | **0** | | review-tapstop | **0** |
| **verdict-gate** | **2** | | hotkey-registration | **0** |
| **hotkey-delivery** | **1** | | autostart-status | **0** |
| | | | fresh-processor-probe | **0** |

**17 rc=0, 3 red. Not one of the three is caused by the rename:**

1. **`history-producer-gate rc=1`** — its own verdict: *"PRODUCER-VERDICT: inconsistent … a non-test
   source stamps a producer but the ENGINE meta carries none"*. It lists the stampers:
   `worker/redux_batch.py:17,189,202` and `worker/sotto_worker.py:2375,2413`. `worker/sotto_worker.py`
   was written at **05:17:08**, i.e. AFTER my 05:15 baseline (which ran this step when it was still rc=0
   by direct measurement). A concurrent worker lane changed the stamping contract; the gate is correctly
   RED until ARM A is extended. `_main/verdict-gate.py`-style fix belongs to that lane.
2. **`verdict-gate rc=2`** — *"SETUP ERROR: decide_verdict reads counters['redux_captions'], which this
   gate's arm table does not provide. Extend HEALTHY in verdict-gate.py"*. Same 05:17:08 worker change
   (the `redux_captions` counter). The gate refuses to report on a predicate it cannot feed — correct
   behaviour. The fix is in `_main/verdict-gate.py` + the worker lane's contract, not a path.
3. **`hotkey-delivery rc=1`** — *"HOTKEY_REGISTER_FAILED accelerator=Alt+C winerror=1409"*
   (ERROR_HOTKEY_ALREADY_REGISTERED): the **owner's app is live and holds Alt+C**. Its fallback, mutex
   and toggle arms all PASS. AGENTS records this oracle `VERDICT: GREEN` when no Sotto instance holds the
   key. Environmental, and it is the correct reading of a shared exclusive resource.

**For the record, the two steps the parent named as unacceptable are GREEN, and the artifact is why they
looked red:** direct runs `node _main\panel-state-guard-gate.js` → `RESULT: GREEN — 3/3 arm(s)` rc=0 and
`node _main\_lane2-reset-probe.js` → `RESULT: GREEN — reset() clears the engine…` rc=0.

---

## 7. The decisive check — the app STARTS FROM THE NEW PATH

```
$ cmd /c "python app\webview\sotto_webview.py --dump-dom --with-worker --dump-dom-wait 10 --no-hotkey --no-hot-reload --log _main\_rename-check.log"
sotto: STAGING_LOADED core=yes -> navigating to panel H:\sotto\app\panel\panel.html
sotto: BRIDGE_GATE=GREEN hasPanelElement=true url=file:///H:/sotto/app/panel/panel.html panelSaidBridgeMissing=false
sotto: DOMDUMP {"body":[380,900],"els":{"#panel":{...380x900...},".captions":{...},"#placeholder":{...}},"sheets":1,...}
sotto: BRIDGEPROBE {... "hasPanelElement":true,"hasSotto":true,"panelSaidBridgeMissing":false,
        "placeholder":{"title":"Listening"},"statusText":"capture-started",
        "url":"file:///H:/sotto/app/panel/panel.html"}                       <- THE NEW PATH
sotto: SHELL_EXIT rc=0 reason=dump-dom                                       (DUMP_DOM rc=0)
```
* **`BRIDGE_GATE=GREEN`** — the gate is not vacuous: it asserts the `#panel` element, no
  `panelSaidBridgeMissing`, AND a url ending in `panel.html`, all three.
* **Panel URL = `file:///H:/sotto/app/panel/panel.html`** (the new path).
* The probe's own worker reached `statusText = capture-started` and the shell stopped it at exit
  (`BRIDGE_STOP reason=exit` → `BRIDGE_EXIT rc=1 … captions=0 statuses=8`). **Its 10 s window produced
  0 captions** — reported honestly rather than dressed up: the owner's app was live and holding the
  `VoiceMeeter Input` loopback at that moment, so a second worker on the same endpoint is the documented
  `AUDCLNT_E_DEVICE_IN_USE` race, not a load failure.
* **Captions DO flow on the new path — measured on the real app, not the probe:** the relaunched shell
  (pid 27492) logged **7 × `BRIDGE_CAPTION_SENT delivered=true`** with real text
  (`"report including the rule designed to detect similar incidents in the future"`) and 1
  `CAPTION_APPLIED`, worker `deaths=0`.

---

## 8. The relaunch (owner's app: never left dead, never shown)

**Kill filter — the parent's requirement, the line now in `_main/relaunch-sotto.ps1`:**
```powershell
$isApp    = ($c -match '(?i)H:[\\/]sotto[\\/]app[\\/]webview[\\/]sotto_webview\.py') -and ($c -match '--log')
$isWorker = ($c -match '(?i)H:[\\/]sotto[\\/]worker[\\/]sotto_worker\.py')
```
Full path under `H:\sotto`, both slash styles, case-insensitive — nothing outside this checkout can match.
Measured effect: **`TOTAL killed=2`** — exactly the owner's shell (pid 36680) and its worker (pid 32044),
no collateral, then a hidden relaunch (`pythonw.exe … sotto_webview.py --log …`, **no `--show`**).
Why a restart was needed at all: the running shell held the module-level `PANEL_HTML` constant pointing at
the old path, so the move made its next hot reload navigate to a path that no longer exists.

**The relaunched app, from `_main/panel-state.json` (producerPid 27492) and `_main/webview-run.log`:**

| claim | evidence |
|---|---|
| boots from the new path | `HOT_RELOAD_WATCH kind=panel dir="H:\sotto\app\panel"`; `STAGING_LOADED … panel H:\sotto\app\panel\panel.html` |
| panel URL | `"panel.url": "file:///H:/sotto/app/panel/panel.html"` |
| renderer alive | `"rendererReady": true`, `"bridgeInstalled": true`, `RECEIVER_READY`, `PRELOAD_ACTIVE hasSotto=true methods=14` |
| **window NOT visible** | `PANEL_VISIBILITY_ON_SCREEN visible=false where=startup hwnd=… panel_shown=false show_requested=false`; `"shell.visible": false`; `panelVisibility.visible=false`; `PANEL_SHOW_REFUSED … panel_shown=false count=2 cure=_gate_form_show` |
| hot reload works, and stays hidden | touched `app/panel/panel.js` (append + byte-exact revert, sha256 `5F6B0645C5D3CCF4…` identical before/after): `HOT_RELOAD_EVENT … action=3` → `HOT_RELOAD_FLUSH` → `HOT_RELOAD_PANEL_DONE files=["panel.js"] reload=1 hotkey=Alt+C` → `HOT_RELOAD_APPLIED reload=1 visible=false hotkey_still_registered=true` → **`HOT_RELOAD_KEPT_HIDDEN reason=owner-had-it-hidden reload=1`** (twice, reload=1 and reload=2) |
| **no `PANEL_SHOWN reason=hot-reload`** | zero matches in the log since the relaunch |
| Alt+C | `HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show\|hide mod_norepeat=true` |
| worker | `WORKER_AUTOSTART=started reason=with-worker`, `"state":"capture-started"`, `capturing=true`, `deaths=0`, `captions=7`, device `WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)` |

---

## 9. What I could NOT verify / deliberately did not do

* **`worker/**` still cites `app/electron/…`** in 4 comment lines + `worker/README.md` (2). The brief
  forbids editing `worker/`, so a stale mention survives in the one file every worker reader loads.
* **The dead Electron arm is no longer runnable AS an arm.** Its own `path.join(__dirname,'panel.html')`
  now points at a directory that no longer holds the panel. I did not rewrite the dead arm's internals:
  the owner ruled no fallback, and other lanes hold uncommitted edits in exactly those files
  (`git status` showed `M app/electron/main.js`, `worker-bridge.js`, `package.json` before the move).
  `git show HEAD:` found no tracked baseline for `_main/_panel2-dom-probe.js` or the harness, so a
  couple of pre-existing reds below rest on reasoning + a control arm, not on a checkout.
* **`_main/_panel2-dom-probe.js` is RED, and was RED before the rename — with both colours shown.**
  `FAIL [H]` compares `sources.slice(-4)` against an expectation whose first element is `stub.js`, while
  the harness's real last four are `themes/themes.js, theme-switcher.js, panel.js, drive.js`: the theme
  lane's two injected scripts made that arm stale, independent of any path prefix. Control: the same
  probe with the OLD `app/electron/` prefixes restored (my scratch copy, run then removed) fails the same
  arm with `want=[["stub.js","../../app/electron/surface.js",…]]`. My edit strictly improved one half of
  it (`…surface.js` present: `false` → `true`). `FAIL [O]` is a CSS `display` mismatch with no path in it.
  This probe is not part of the battery.
* **Two long-lived instances share one audio endpoint.** The probe's 0-caption window is that race, and I
  did not kill the fresh app to get a cleaner probe — the owner's app takes priority over a nicer number.
* **`docs/**` and `_main/*.md` (373 dated hits) were not rewritten.** Correcting them would falsify dated
  measurements; the three live docs were corrected instead.
* **The window census is 60 s**, so it cannot prove the absence of a short flash. The absence of a visible
  window after the relaunch rests on the shell's own `PANEL_VISIBILITY_ON_SCREEN visible=false` +
  `PanelState.panel_shown=false` + two `PANEL_SHOW_REFUSED`, not on a census.

---

## 10. Files written by this lane

`app/panel/package.json` (**new**, the module-type marker) · `app/webview/{sotto_webview.py,hot_reload.py,run.cmd,README.md}`
· `AGENTS.md`, `README.md`, `app/package.json`, `.gitignore` · 33 instruments under `_main/` + 3 root
test scripts + `app/_legacy-electron/transcript-append-oracle.js` · 9 frozen fixtures (one literal each)
· `_main/_audit-render/panel-harness.html` (regenerated) · `_main/relaunch-sotto.ps1` (kill filter only)
· `_main/_audit-verify-all.cmd` (path + the `!ERRORLEVEL!` reporting fix) · 5 path comments inside
`app/panel/**` (parent's Answer A; the 6th left as a dated record) · this receipt.
Evidence files: `_main\_rename-manifest-before.csv`, `_main\_rename-{baseline,final,final2}-battery.log`,
`_main\_rename-check.log`.
