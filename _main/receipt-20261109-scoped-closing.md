# RECEIPT — scoped closing of the 2026-11-09 Sotto worklists (evidence that exists today)

Written 2026-11-09, 14:0x, by an OMP subagent (`ScopedClosingReceipt`), read-only.

**What this is.** For each of the six worklists named in the assignment, the acceptance rows are
re-listed and each row is marked with the evidence produced by **re-running the focused gate
today** — never by repeating what the worklist claimed. Nothing here was launched: no Sotto window,
no app restart, no synthetic input, no visible terminal, no Herdr, no battery, no baseline edit,
no product edit. Every child process went through `_main/hidden-launch.py` (`CREATE_NO_WINDOW` +
`STARTUPINFO` with `STARTF_USESHOWWINDOW`/`SW_HIDE`, `stdin=DEVNULL`), with
`TMP=TEMP=TMPDIR=I:\cc-tmp`.

**What this is not.** It is not a pass on runtime behaviour. The live instance is a different
process from the disk (see §7), so every row below is at most `fixed, NOT verified`.

## 0. Snapshot this receipt measures

- HEAD `e88c649` ("regra: um pin do code-health so' descreve o que esta' no commit"), 14:03:49.
- Measurement window 13:52:xx → 14:06:44. **The tree moved under the measurement**: commits
  `feee26d` 13:44:11, `36e849f` 13:48:31, `ff0bd62` 13:55:33, `18f1436` 13:59:56, `f12dcd3`
  14:02:59, `5a9e1d4` 14:03:26, `e88c649` 14:03:49 landed while gates were running. Two rows
  **flipped between two runs of the same command in this window** (§4 F5 and §5); both readings
  are reported, with their times, because the flip is itself the finding.
- Product bytes at the final snapshot (sha256 prefix, size):

| file | bytes | sha256[:16] | mtime |
|---|---|---|---|
| `app/panel/panel.html` | 80 655 | `FCBBF2A2F1420835` | 09:33:16 |
| `app/panel/panel.css` | 163 429 | `5BCF0E9646278F10` | 09:33:16 |
| `app/panel/panel-unified.css` | 26 028 | `4A5A7C8A4707BF24` | 12:21:37 |
| `app/panel/panel.js` | 219 959 | `9B927049269B4C2F` | 10:04:54 |
| `app/panel/history-store.js` | 19 322 | `5D7C8167F567DFA2` | 12:08:16 |
| `app/panel/history-context-store.js` | 12 980 | `C6937BF36CE4C9EA` | 13:48:58 |
| `app/webview/history_context.py` | 11 827 | `751370D2FDDDAE1E` | 12:07:40 |
| `app/webview/sotto_webview.py` | 1 249 897 | `F8B67C6E90368F7B` | 13:57:53 |
| `app/webview/youtube_cdp_source.py` | 85 439 | `C22899B7D2B917EA` | 12:02:47 |
| `app/webview/caption_overlay.py` | 83 880 | `78A3421662489D8F` | 08:02:17 |
| `app/webview/caption_drag.py` | 12 566 | `553824B2242B3E87` | 07:24:24 |
| `app/webview/load_shedding.py` | 58 820 | `EA74E60D0AE01EA9` | 09:43:02 |
| `worker/engine_switch.py` | 71 767 | `595D987C8ADB6D6B` | 09:20:24 |
| `worker/engine_policy.py` | 23 499 | `AF4951EE52295718` | 08:43:44 |
| `worker/sotto_worker.py` | 473 754 | `C7E5157C86DC5B62` | 13:42:50 |
| `_main/panel-history-clip-probe.mjs` | 35 068 | `25438E6BDD356B2D` | 10:18:10 |

  `panel-unified.css`, `caption_overlay.py`, `caption_drag.py` and the DOM probe match, byte for
  byte, the hashes their worklists recorded — those four artifacts are measured on the bytes
  the worklists describe. `history-context-store.js` (8 605 → 12 980 B), `worker/sotto_worker.py`
  and `app/webview/sotto_webview.py` do **not**: they carry later work (§5).

- Instrument: one runner, `G:/Temp/opencode/scoped-closing/run-gates.py` (scratch, not product),
  which executes each gate through `hidden-launch.run(capture=True)` and writes the raw stdout +
  stderr + `RC=` to `G:/Temp/opencode/scoped-closing/logs/<gate>.log`. Every verdict line below is
  copied from those logs (or, where marked, from the delivered output of a run whose log file a
  later rerun overwrote).

## 1. THE TABLE

Legend: **PASS** = the gate ran and its own verdict says green/red-as-designed; **FAIL** = the gate
ran and its verdict is not green; **SKIPPED** = the gate was not run (reason given) and the row is
**UNVERIFIED** — a skipped gate is never a pass.

Worklist key: **panel** = `.agent-work/TODO-omp-panel-all-themes-20261109.md` + `TODO-omp-panel-all-themes-20261109.md`; **caption** = `.agent-work/TODO-omp-caption-overlay-design-drag-20261109.md`; **ctrlspace** = `.agent-work/TODO-omp-ctrlspace-youtube-readiness-20261109.md`; **history** = `.agent-work/TODO-omp-history-dedupe-recall-20261109.md`; **perf** = `.agent-work/TODO-omp-sotto-performance-20261109.md`.

| # | worklist | subject | claim (as the worklist words it) | gate command | verbatim verdict (rc, wall) | status |
|---|---|---|---|---|---|---|
| P1 | 59 themes, structural contract | panel | "all 59 theme entries pass the positive theme oracle; its negative arm catches 10/10" | `node _main/panel-themes-oracle.mjs --json …` / `--neg-arm` | not run — launches headless Chromium (`chromium.launch({channel:'msedge'})`, oracle lines 847/1117) | **SKIPPED (browser) → UNVERIFIED** |
| P2 | header order: settings immediately left of close, X last | panel | "header controls in the contract order … X last" | `node _main/panel-header-oracle.js` | `VERDICT: GREEN -- 32/32 arm(s)` (rc=0, 4.2 s) | **PASS** |
| P2n | same, falsifiable | panel | "negative control catches its mutations" | `node _main/panel-header-oracle.js --neg-arm` | `NEG-ARM VERDICT PASS -- 9 mutant(s), 0 wrong` (rc=1, 114.8 s) | **PASS** |
| P3 | no portrait/demo circles | panel | "no portrait/demo circles" | panel-themes arm M6 `no-demo-circles` | not run — browser (above) | **SKIPPED → UNVERIFIED**; source-only negative: `grep -n "demo-circle\|portrait" app/panel/panel.css app/panel/panel-unified.css app/panel/panel.js` → no match |
| P4 | hidden scrollbar, scrolling retained | panel | "hidden scrollbar with scrolling retained" | panel-themes arms A3/A4/A10 | not run — browser | **SKIPPED → UNVERIFIED**; source: `panel-unified.css:171` `scrollbar-width: none !important`, `:175` `::-webkit-scrollbar { width: 0 !important }`, `:173` list `overflow-y: auto` |
| P5 | search is a glyph that opens on demand, closed by default | panel | "search is a button that opens the input on demand and is closed by default" | panel-themes arms A5 `search-on-demand`, A5-bis `search-reachable` | not run — browser | **SKIPPED → UNVERIFIED**; source: `panel.html` `#history-search` carries `hidden`, `#history-search-button` carries `aria-expanded="false"` |
| P6 | panel drag targets exclude feed/inputs/dropdowns | panel | "panel dragging targets that exclude the feed/inputs/dropdowns" | `node _main/panel-drag-targets-oracle.js` | `VERDICT: PASS -- 12 arms, 0 divergentes` (rc=0, 2.2 s) | **PASS** |
| P6n | same, falsifiable | panel | "the mutant that erases the rows exclusion is caught" | `node _main/panel-drag-targets-oracle.js --neg-arm` | `NEG-ARM: PASS -- o mutante que apaga a exclusao dos rows foi apanhado` (rc=1, 1.9 s) | **PASS** |
| P7 | panel drag responsive, 240 Hz ceiling | panel | "panel drag remains responsive with a measured 240 Hz ceiling/contract" | no light gate measures the panel window drag rate; the drag oracle counts targets only | — | **UNVERIFIED (no gate)**; source-only: `sotto_webview.py:8092` `EDIT_DRAG_FRAME_HZ = 240` |
| P8 | no bottom void | panel | "no bottom void" | panel-themes arms A5-ter `short-feed-on-floor` / A11 `no-bottom-void` | not run — browser | **SKIPPED → UNVERIFIED**; source: `panel-unified.css:174` `.history__list > :first-child { margin-top: auto !important }`, `:157-158` `.history` as `display:flex; flex-flow:column` |
| P9 | 60-day row visible/searchable with context, 200-day excluded (panel DOM) | panel | "the existing history DOM probe passed … 6/6 retention mutants" | `node _main/panel-history-clip-probe.mjs` (+ `--neg-arm`) | not run — boots headless Chromium (`panel-history-clip-probe.mjs:87`), and its own receipt records it under an exclusive **heavy** lease `230bfe41f0ea4c84b2c631f0b5a06791` | **SKIPPED (browser + heavy) → UNVERIFIED** |
| P10 | judgment: void/spacing/hierarchy/theme distinctness in renders | panel | "inspect the actual headless rendered panel" | none (judgment, offscreen renders) | — | **source-only / judgment, not re-inspected today** (re-inspection needs the browser) |
| C1 | every payload gets a designed plate/face (59) | caption | "all 59 theme payloads pass the plate/face oracle; negative control catches 3/3" | `python _main/caption-overlay-theme-oracle.py` | **not run**: its payload report `_main/_cache/panel-themes.json` (09:36:12) is older than `panel-unified.css` (12:21:37) and `panel-themes-oracle.mjs` (12:11:28), so `_stale()` is true and the oracle would call `node _main/panel-themes-oracle.mjs --json` → Chromium (oracle lines 132-155) | **SKIPPED (browser refresh) → UNVERIFIED** |
| C2 | no portrait/demo circle on the overlay | caption | "all 59 normalised themes report `led=false`" | same oracle | not run — same reason | **SKIPPED → UNVERIFIED**; source-only (prior reading of the normaliser) |
| C3 | overlay draggable, bounded up to 240 Hz | caption | "`VERDICT: PASS (14/14)` … `P13 arrasto: 128 Hz entregues`" | `python _main/caption-drag-oracle.py` | `VERDICT: PASS (14/14)` (rc=0, 2.3 s); this run: `P13 arrasto: 217 Hz entregues, 219 ticks, 0 pinturas` | **PASS** |
| C3n | same, falsifiable | caption | "all plan mutants red … `NEG-ARM VERDICT: PASS (plan=CAUGHT, poll=3/3)`" | `python _main/caption-drag-oracle.py --neg-arm` | `NEG-ARM VERDICT: PASS (plan=CAUGHT, poll=3/3)` (rc=1) | **PASS** |
| C4 | one thread, no Timer-per-frame, paint budget | caption | "tick-thread gate 10/10" | `python _main/caption-tick-thread-oracle.py` | `VERDICT: PASS (10/10)` (rc=0, 2.7 s), `A10 laco real: fracao de nucleo 0.27 <= orcamento (23 Hz, 21 quadros)` | **PASS** |
| C4n | same, falsifiable | caption | "`NEG-ARM VERDICT: PASS (6/6)`" | `python _main/caption-tick-thread-oracle.py --neg-arm` | `NEG-ARM VERDICT: PASS (6/6)` (rc=1, 2.9 s) | **PASS** |
| C5 | hidden/idle display does not stop model or history | caption | "hide/keep-model/history gate 14 arms" | `python _main/caption-kept-on-hide-oracle.py` | `caption-kept-on-hide-oracle: PASS` (rc=0, 2.5 s) — arms B/C/D `pushes=0 hist=1`, `CAPTION_WINDOW_KEPT reason=panel-hidden wanted=true` | **PASS** |
| C5n | same, falsifiable | caption | "`NEG-ARM: PASS -- hide=CAUGHT … retoma=CAUGHT`" | `python _main/caption-kept-on-hide-oracle.py --neg-arm` | `NEG-ARM: PASS -- hide=CAUGHT pausa=CAUGHT deferred=CAUGHT display=CAUGHT pausa-pixels=CAUGHT release=CAUGHT escopo=CAUGHT retoma=CAUGHT` (rc=1, 2.6 s) | **PASS** |
| C6 | judgment: contrast/line fit/hierarchy in stills | caption | "59 offscreen renders, `contrast_min=1.81` …" | none (judgment over `_main/_cache/theme-stills`) | — | **source-only / judgment, not re-inspected today** |
| Y1 | Ctrl+Space display switch independent of Alt+C | ctrlspace | "source review … support independence from Alt+C" | **none of the three named gates measures it.** I ran two extra focused light gates (labelled: not named by the worklist): `python _main/hotkey-live-toggle-oracle.py`, `python _main/caption-switch-race-oracle.py` | `hotkey-live-toggle GREEN -- arms=38 pass=38 fail=0` (rc=0, 6.4 s) — arm (i) `Alt+C continua a ser so' dos paineis`, arm (l) `o interruptor le' o que o DONO possui (_caption_wanted)`; `CAPTION-SWITCH-RACE GREEN -- arms=13 pass=13 fail=0` (rc=0) | **PASS by the two extra gates**; without them the row is source-only |
| Y1n | same, falsifiable | ctrlspace | — | `--neg-arm` on both | `NEG-ARM PASS -- RED as designed: 5 mutantes derrubam o oraculo` (rc=1, 19.7 s); `NEG-ARM: PASS -- a saida do arm A1 depende do guarda` (rc=1) | **PASS** |
| Y2 | YouTube captions do not wait for the model spinner | ctrlspace | "`PASS 12/12` … `legenda-antes-do-webview2-sem-espera`" | `python _main/youtube-first-at-boot-oracle.py` | `YOUTUBE-FIRST-AT-BOOT VERDICT: PASS (12/12)` (rc=0, 10.5 s) — `legenda-antes-do-webview2-sem-espera PASS pipeline_line=23399 webview.start_line=23544 default_wait_zero=True`; `faixa-ao-vivo-recusa-o-estado PASS withheld=False`; `ordem-do-arranque PASS events=['cdp','watcher','worker']` | **PASS** |
| Y2n | same, targeted reject | ctrlspace | "`NEG-ARM PASS (5/5)` rc=1, `webview-antes-da-legenda` CAUGHT" | `python _main/youtube-first-at-boot-oracle.py --neg-arm` | `NEG-ARM: PASS (5/5 mutantes apanhados)` (rc=1, 40.9 s) | **PASS** |
| Y3 | stale pixels clear on pause/end/silence, model/history continue | ctrlspace | "clearing stale pixels on idle/pause/end without unloading the model or stopping history" | `python _main/caption-kept-on-hide-oracle.py` (row C5 above) | `caption-kept-on-hide-oracle: PASS` (rc=0) — `[PASS] fim do video apaga os pixels blanks=['youtube-paused-or-ended']`, `[PASS] silencio sem pausa continua a apagar blanks=['no-caption-for-6.0s']` | **PASS** |
| Y4 | CDP source: adoption, pause edge, dedup of state lines | ctrlspace | "`VERDICT: PASS (23/23)` … neg `16/16`" | `python _main/youtube-cdp-source-oracle.py` / `--neg-arm` | `VERDICT: PASS (23/23)` (rc=0, 5.6 s); `NEG-ARM VERDICT: PASS (16/16)` (rc=1, 79.4 s) | **PASS** |
| Y5 | single refresher thread, loop rate bounded | ctrlspace | "`VERDICT: PASS (arms=8 fail=0)` … neg 3 mutants" | `python _main/cdp-target-async-oracle.py` / `--neg-arm` | `VERDICT: PASS (arms=8 fail=0)` (rc=0, 2.7 s) — `A4-STATE-RATE PASS YOUTUBE_LOOP_HZ=6 (esperado 6)`, `A5-STATE-BUDGET PASS linhas/s=0.133 (alvo <=0.2)`; `NEG-ARM: PASS (tres mutantes, os tres apanhados)` (rc=1, 12.2 s) | **PASS** |
| Y6 | live behaviour (captions before model, clearing on the owner's screen) | ctrlspace | "No live runtime claim is verified" | — | freshness says STALE (§7) | **UNVERIFIED (runtime)** |
| H1 | dedupe without eating genuine repeats | history | "`VERDICT: PASS arms 32/32`; `--neg-arm` 2/2" | `python _main/history-merge-oracle.py` / `--neg-arm` | `VERDICT: PASS arms 32/32` (rc=0, 0.2 s); `NEG-ARM PASS mutants 2/2` (rc=1) | **PASS** |
| H2 | context persisted, searchable, exportable, Py↔Node parity | history | "`VERDICT: PASS arms 102/102`; neg 10/10" | `python _main/history-context-oracle.py` / `--neg-arm` | **13:56 run: `VERDICT: FAIL arms 115/120` (rc=1)** — `RED s17b-janela-proxima-ainda-serve`, `RED s25-nova-sessao-nao-herda-8s`, `RED s25b-nova-sessao-nao-herda-anel`, `RED s11-export-viewing`, `RED x1-node-le-python`; **14:05 re-run on the bytes that landed at 13:55-13:57: `VERDICT: PASS arms 120/120` (rc=0, 0.6 s)**; neg `NEG-ARM PASS mutants 16/16` (rc=1, 5.2 s) | **PASS at 14:05, FAIL at 13:56** — see §4 F5 and §5 |
| H3 | a closed caption line reaches the transcript with its producer; provisional drafts refused | history | "`history-write-oracle.py` -> PASS; `--neg-arm` -> `NEG-ARM: PASS`" | `python _main/history-write-oracle.py` / `--neg-arm` | `VERDICT: PASS — a closed caption line (live or batch) reaches the` … (rc=0, 10.7 s); `NEG-ARM: PASS — the closed-line arms go RED under the old refusal` (rc=1, 4.6 s) | **PASS** |
| H4 | 60-day item survives tail + search-by-context + export with context | history | "fixture confirms 60-day export with context" | `python _main/history-retention-fixture.py` | rc=0: `{"retention_h": 4320, "expected": {"day60": "2026-09-10", "day200": "2026-04-23", "dayNear": "2026-05-14", "nearDays": 179.0, "dayRecent": "2026-11-09", "feedRows": 3, "searchOne": 1, "searchLeak": 1}, … "export": {"entries": 4, "has60": true, "hasContext": true}}` | **PASS (store level)** |
| H5 | the 200-day line is excluded **by the panel** | history | "60-day visible/searchable, 200-day excluded (real DOM)" | `node _main/panel-history-clip-probe.mjs` | not run — browser + heavy lease (row P9) | **SKIPPED → UNVERIFIED** |
| H6 | 180-day window, no log churn | history | "`s19`-`s21` and `g16`-`g22`, both hosts log only when `removed` is non-zero" | inside `history-context-oracle.py` (H2) | `ok s19-retencao-seis-meses`, `ok s20-dia-antigo-apagado`, `ok s21-dia-recente-fica`, `ok g17-dia-antigo-apagado`, `ok g21-env-apaga-o-antigo` | **PASS** |
| H7 | window constants are the documented 180 days | history | "`HISTORY_RETENTION_H = 4320`" | source | `sotto_webview.py:781 HISTORY_RETENTION_H = int(os.environ.get('SOTTO_HISTORY_RETENTION_H') or 4320)`; `history-store.js:41 const RETENTION_H = Number(process.env.SOTTO_HISTORY_RETENTION_H) \|\| 4320` | **source-only (constants), consistent with H6** |
| H8 | judgment: context useful without bloat / full recording | history | "context must be useful … without a full screen recording" | none | — | **source-only / judgment** |
| E1 | first display does not wait for an unnecessary reload | perf | "`unload_when_hidden` defaults to `False` … the only load paths left are the reload floor and the warm budget" | `python _main/redux-arm-weights-oracle.py` (R1-R8 are the reload-floor arms) | `SETUP ERROR: the store driver failed: Cannot find module './history-context-store'` → `VERDICT: SETUP ERROR` (rc=2, 0.3 s) | **FAIL (gate cannot run) → UNVERIFIED**; see §6 F1 |
| E2 | load/release policy cannot thrash | perf | "load-shedding positive gate passes 252/252; its negative arm catches 25/25" | `python _main/load-shedding-oracle.py` / `--neg-arm` | `LOAD-SHEDDING GREEN -- arms=252 pass=252 fail=0` (rc=0, 26.8 s); `--neg-arm` rc=1 (195.5 s) — the driver returns 1 **only** if all 19 mutants were caught (`main()` in the oracle), e.g. `NEG-ARM(largada-buraco) PASS -- RED as designed`, `NEG-ARM(largada-eco) PASS -- RED as designed` | **PASS (mechanism)** |
| E3 | memory-pressure release/reload floors explicit and guarded | perf | "`RELEASE_PERSIST_S = 120 s` … reload floor `max(60 s, 10 x load_s)`" | `load-shedding-oracle.py` (arms) + source | arms green (E2); `load_shedding.py:47 HIGH_PCT = 88.0`, `:52 VERY_HIGH_PCT = 94.0`, `:684 RELEASE_PERSIST_S = 120.0`, `:689 RELEASE_HYSTERESIS_PCT = 4.0`, `:697 RELEASE_GAP_S = 15.0`; `engine_policy.py:53 RELOAD_FLOOR_S = 60.0`, `:57 RELOAD_FLOOR_LOAD_FACTOR = 10.0` | **PASS (mechanism) for the shedding side; the reload-floor side's own gate is E1 → UNVERIFIED** |
| E4 | CPU thread ceiling on cold/warm/stream | perf | "worker-thread limit passes 15/15; negative catches 11/11" | `python _main/worker-thread-limit-oracle.py` / `--neg-arm` | `VERDICT: FAIL (14/15)` (rc=1, 2.3 s) — `A4 session-options RED intra=1 inter=1` (the arm expects `session_options(fake_ort,'',2)` → intra=2; the file now gives the non-encoder graphs `min(threads, SMALL_GRAPH_THREADS=1)`, `sotto_worker.py:91`); neg: `MUTATION IMPOSSIVEL: "'WORKER_THREADS',\n 'REDUX_SWITCH'," nao existe em H:\sotto\app\webview\sotto_webview.py` (rc=1) | **FAIL (positive) + negative arm could not mutate → UNVERIFIED negative** |
| E5 | worker cost watchdog (CPU with no rows) | perf | "`cost-watchdog-oracle.py` → 32/32 … neg 10/10" | `python _main/cost-watchdog-oracle.py` / `--neg-arm` | `VERDICT: arms=37 pass=37 fail=0` / `VERDICT: PASS` (rc=0, 0.7 s); `NEG-ARM: PASS -- 10/10 mutantes apanhados` (rc=1, 1.7 s) | **PASS** |
| E6 | code-health ratchet | perf | worklists record `CODE-HEALTH FAIL` / `FAIL 11 metrics` | `python _main/code-health-oracle.py` | **13:58 run: `CODE-HEALTH VERDICT FAIL` (rc=2), `piorem: 8 metrica(s)`**; **14:05 re-run: `piorem: 0 metrica(s)` / `CODE-HEALTH VERDICT PASS` (rc=0, 1.2 s)** | **PASS at 14:05, FAIL at 13:58** — the flip is a baseline re-pin, §5 |
| E7 | runtime: reload count, stutter, first display, drag rate on the owner's instance | perf | "`fixed, NOT verified` … UNMEASURED" | `python _main/live-code-freshness-oracle.py --strict`; `python app/webview/panel_state.py --read` | `LIVE_CODE STALE` (rc=3): `pid=? started=?`, `processo: sha256=77D4D1680260`, `disco : sha256=EAB6892F23EF files=104`, `prova A : hash diferente`, `prova B : indisponivel`; panel state rc=0: `freshness = FRESH`, `reason = periodic sequence=10396 producerPid=50452`, `namedState = tap-dead-endpoint` | **UNVERIFIED (runtime, by construction)** |

## 2. SKIPPED gates — the full list, with why

| gate | why not run | what would close it |
|---|---|---|
| `node _main/panel-themes-oracle.mjs` (+`--neg-arm`) | launches **headless Chromium** (`chromium.launch({channel:'msedge', headless:true})`, lines 847/1117). This assignment's hard rule is "no browser". It is **not** declared `heavy` in `_main/_audit-verify-all.cmd` (the ten `call :step heavy` lines are `panel-paint-first-measure`, `parakeet-ultra`, `strip-surface-runtime`, `red-as-expected-strip-surface`, `strip-geometry-restore`, `control-panel-exit3-neg-arm`, `altc-first-caption`, `red-as-expected-shell-relaunch`, `shell-relaunch`, `power-recovery-live` — none of them ours) | the owner authorizing a browser process, or a battery run of steps 612/614 |
| `node _main/panel-history-clip-probe.mjs` (+`--neg-arm`) | headless Chromium (`:87`) **and** its own receipt records it under an exclusive heavy lease `230bfe41f0ea4c84b2c631f0b5a06791` | a heavy lease + browser authorization; battery steps 584/616 |
| `python _main/caption-overlay-theme-oracle.py` (+`--neg-arm`) | its payload report is stale by its own guard (report 09:36:12 < `panel-unified.css` 12:21:37 < `panel-themes-oracle.mjs` 12:11:28), so it would spawn `node panel-themes-oracle.mjs` → Chromium (`:132-155`) | a fresh payload report (browser) or a battery run of step 600/602 |
| `_main/_cache/_theme_stills.py` (judgment stills) | not a gate; re-rendering 59 stills is judgment work, not a focused gate | owner/lane judgment pass |
| `_main/nemotron-thread-bench.py` | outside this assignment; needs the exclusive heavy lease | owner authorization + heavy lease |
| `I:/!watcher/tools/artifact-census.py --project H:/sotto` | no heavy step was executed in this assignment, so the heavy preflight had no consumer | a heavy run |
| `_main/artifacts-census` | does not exist under that name in the tree | n/a |
| `_main/panel_state.py` | **path does not exist**; the instrument is `app/webview/panel_state.py` — I ran that one instead (`--read`, rc=0) | n/a |
| `_main/shell-thread-cpu.py` | would measure the **STALE** pid 50452 / an old worker; no fresh process exists, so the number would describe code that is not on disk | a fresh owner-launched instance |

Performance gate, read-only state query at 13:51 (`python I:/!manager/tools/performance-gate.py status`):
`performance-gate: GREEN`, `heavy_allowed=True amber_light_allowed=False`, `leases: heavy=0/1 light=0/3`.
No lease was taken because no heavy step was run.

## 3. Claims with NO gate (source-only)

These are named as source-only, not as passes:

1. **Panel 240 Hz drag ceiling** (`sotto_webview.py:8092 EDIT_DRAG_FRAME_HZ = 240`). The drag
   *targets* are gated (P6); the *rate* is not, for the panel window. The 240 Hz figure that is
   gated belongs to the caption overlay loop (`caption_drag.py:52`) — a different subject.
2. **No portrait/demo circles** in the panel and on the overlay (P3, C2). Only the browser gates
   assert it; a grep finds no such construct in the panel styles/scripts, which is absence of code,
   not a measurement.
3. **Search closed by default** (P5). `hidden` + `aria-expanded="false"` is the source shape; the
   arm that presses it is the browser oracle.
4. **Hidden scrollbar / scrolling retained / no bottom void** (P4, P8). The CSS rules exist
   (`panel-unified.css:157-175`); the arms that measure the computed box are browser-only.
5. **History 180-day constants** (H7) — read from both hosts; the behaviour is gated by H6, the
   *values* are source.
6. **Judgment rows** (P10, C6, H8): rendered spacing/hierarchy/contrast and "context useful without
   bloat" are judgment, self-inspected previously, not re-inspected today.
7. **The 82 loads / 70 releases replay** (`_main/receipt-20261109-reload-floor.md` §8: 10 of 84
   `muito-alta` windows would release, 15 of 59 reload pairs deferred at 60 s). No standalone gate
   command reproduces it; the only file that mentions `LOAD_ACTION_PUBLISHED` is
   `_main/load-shedding-oracle.py`, and the numbers in the receipt are a one-off replay of
   `_main/webview-run.log`. Treat as a prior measurement, not as today's gate.
8. **Ctrl+Space independence without the two extra gates** (Y1): none of the three worklist-named
   gates measures it; the row rests on `hotkey-live-toggle-oracle` + `caption-switch-race-oracle`,
   which I ran although the worklist did not name them.

## 4. Findings that are not rows (the tree's own gate defects, measured today)

### F1 — `redux-arm-weights` cannot run: a gate copy step was not updated for the new module

```
SETUP ERROR: the store driver failed: Cannot find module './history-context-store'
Require stack:
- I:\cc-tmp\redux-arm-weights-cyxh317s\store-G\history-store.js
VERDICT: SETUP ERROR                                   rc=2
```

`app/panel/history-store.js:41` now `require`s `./history-context-store` (the codec extraction), but
the redux oracle materialises only `history-store.js` into its temp `store-G/` directory. The same
defect class was fixed in `history-context-oracle.py` when the module was extracted; it was **not**
fixed in `redux-arm-weights-oracle.py`. Consequence: **R1-R8 (the reload floor: `max(60 s, 10 x
load_s)`, defer-vs-tail) have no running gate today.** This is the reload half of acceptance row E1.

### F2 — `worker-thread-limit` positive is RED on an in-flight product change

`A4 session-options RED intra=1 inter=1`: the arm calls `session_options(_FakeOrt(), '', 2)` and
expects `intra=2`; the current function (`worker/sotto_worker.py:4437-4445`) gives the non-encoder
graphs `min(threads, _small_graph_threads())` with `SMALL_GRAPH_THREADS = 1` (`:91`). The arm was
written before that split. Whether the arm or the product is right is a decision, not a measurement.

### F3 — `worker-thread-limit --neg-arm` cannot mutate, and rc=1 alone is ambiguous

```
MUTATION IMPOSSIVEL: "'WORKER_THREADS',\n                       'REDUX_SWITCH'," nao existe em H:\sotto\app\webview\sotto_webview.py
```

`ENGINE_VISIBLE_TAGS` (`sotto_webview.py:1366-1380`) gained explanatory comments between the tags at
13:57:53, so the M11 anchor no longer exists. The battery is safe here — `:expectred` also requires
the log to print `NEG-ARM: PASS`, which this log does not — but a reader who trusts the **rc** alone
would read rc=1 as "caught". It is not.

### F4 — the freshness oracle's prova B is blind once the log grows past 4 MiB

`_main/live-code-freshness-oracle.py` reads `TAIL_BYTES = 4 * 1024 * 1024` (`:71`). The shell's start
line is `2026-11-09 08:14:03.288 … SHELL_STARTUP_STAGE pid=50452` at line 511251 of
`_main/webview-run.log`; **bytes after that line at 14:00 = 7 704 739 (7.35 MiB)**, so it is outside
the window. Result today: `pid=? started=?`, `prova B : indisponivel`. The verdict (`STALE`) is still
right — it comes from prova A (process `sha256=77D4D1680260` vs disk `sha256=EAB6892F23EF`) — but the
start instant and pid that every other receipt quotes are **not obtainable from this instrument
today**, and the oracle reports them as `?` rather than as "outside the window".

### F5 — the tree moved during the measurement, twice changing a verdict

- `history-context`: `FAIL arms 115/120` at 13:56 → `PASS arms 120/120` at 14:05.
- `code-health`: `FAIL, piorem: 8` at 13:58 → `PASS, piorem: 0` at 14:05.

Neither flip is mine. Both are explained in §5. Any receipt that quotes only one of the two numbers
is quoting a tree that no longer exists.

## 5. Code-health and dirty-state attribution (as measured, not as claimed)

**The 13:58 FAIL (rc=2) named eight metrics, none of them the caption or panel lane's own:**

```
RED  app/panel/history-context-store.js: bytes piorou de 8605 para 12980
RED  app/panel/history-context-store.js: lines piorou de 217 para 300
RED  app/webview/sotto_webview.py: bytes piorou de 1244408 para 1249897
RED  app/webview/sotto_webview.py: lines piorou de 23544 para 23640
RED  worker/sotto_worker.py: bytes piorou de 468615 para 473754
RED  worker/sotto_worker.py: lines piorou de 8882 para 8990
RED  worker/sotto_worker.py: defs piorou de 89 para 92
RED  worker/sotto_worker.py: except_pass piorou de 20 para 21
piorem: 8 metrica(s)
CODE-HEALTH VERDICT FAIL
```

**The 14:05 PASS (rc=0):**

```
piorem: 0 metrica(s)
CODE-HEALTH VERDICT PASS
```

**Attribution of the flip.** `_main/code-health-baseline.json` was re-pinned at **14:03:26** by commit
`5a9e1d4` ("code-health baseline: re-pin NOMEADO, so' do que esta' commitado", 8 lines changed),
after `f12dcd3` ("o `--update` deixa de fixar ficheiros NAO commitados"). So today's green is
**baseline-refresh-driven, not shrink-driven**: the three files did not shrink between 13:58 and
14:05 (`history-context-store.js` 12 980 B both times, `sotto_worker.py` 473 754 B both times,
`sotto_webview.py` 1 249 897 B both times). I did not run `--update` and did not touch the baseline;
the refresh came from another lane.

**Dirty state at 14:06** (`git status --short`, 44 entries). Relevant to the worklists:

- `worker/sotto_worker.py` is **clean vs HEAD** yet was RED against the 13:58 baseline → that RED
  was baseline lag, not dirty drift.
- `app/panel/history-context-store.js` is **clean vs HEAD** (committed in `f12dcd3`) at 12 980 B
  against the old pin of 8 605 B → same class.
- `app/webview/sotto_webview.py` was `M` when the 13:58 FAIL was produced and shows **no diff at
  14:06** → its RED was in-flight work that has since been committed (`f12dcd3`, `18f1436`).
- Still dirty and relevant: `app/panel/history-store.js` (+240 lines), `app/panel/panel-unified.css`
  (+49/-…), `worker/wasapi_loopback.py` (+34), `_main/panel-history-clip-probe.mjs` (+293) — the last
  one's **bytes equal** the sha the panel worklist recorded (`25438E6B…`, 35 068 B), so that diff is
  older than the receipt, not newer.
- `_main/code-health-baseline.json` is now clean (committed at 14:03:26).

**Preserved.** I edited nothing in the product, the baselines, `AGENTS.md` or the battery. The only
files I created are this receipt and the scratch runner/logs under `G:/Temp/opencode/scoped-closing/`.

## 6. What the owner must authorize next

1. **A browser run of the three browser gates** — `panel-themes` (+neg), `panel-history-clip`
   (+neg, under a heavy lease), `caption-overlay-theme` (+neg). They are headless and invisible
   (no owner profile, no synthetic input), they are already battery steps (584/600/612 and their
   `red-as-expected` pairs), and they are the **only** evidence for: 59-theme contract, hidden
   scrollbar/scrolling, search-on-demand reachability, no bottom void, 60-day panel visibility with
   the 200-day line excluded, and the overlay's 59 plates/faces. Until they run, those rows are
   UNVERIFIED — including the two worklists' central claim.
2. **A fix decision on the two broken gates** (they are instrument edits, not product edits, so
   they need the owning lane or the owner's word): `redux-arm-weights-oracle.py` must copy
   `history-context-store.js` next to `history-store.js` (F1), and `worker-thread-limit-oracle.py`
   must re-anchor M11 on the current `ENGINE_VISIBLE_TAGS` shape and decide A4's expectation
   against the encoder/small-graph split (F2/F3). Until then the reload-floor and the thread-ceiling
   rows have no working control.
3. **A freshness-instrument decision** (F4): `TAIL_BYTES = 4 MiB` is smaller than the distance from
   the shell's start line to the log's end today (7.35 MiB). Either the oracle must scan back to the
   last `SHELL_STARTUP_STAGE` regardless of size, or every receipt must stop quoting `pid`/`started`
   from it. This is the instrument that decides whether *any* runtime claim is admissible.
4. **A fresh owner-launched instance** (never by a lane; `--no-self-relaunch` is set). Only then can
   these be measured on the same process/thread: live panel drag rate, live caption drag rate, theme
   search/drag behaviour, caption hide/resume with model+history continuing, worker CPU/thread
   ceiling (`WORKER_THREADS`/`WORKER_THREAD_PLAN`/`WORKER_COST`/`WORKER_GENAI_THREADS` lines do not
   exist in the current process's log), reload count (`REDUX_ENGINE_LOAD`/`REDUX_BATCH_DEFERRED`),
   startup and first-display latency, and stutter before/after.
5. **A baseline policy statement.** `_main/code-health-baseline.json` was re-pinned today by another
   lane while the worklists said "do not refresh the baseline merely to turn the gate green without
   owner authorization". Today's green is exactly that kind of green (§5). The owner should say
   whether the 14:03:26 pin is accepted as the new ceiling; if not, the ratchet must be re-derived
   from a named commit with the three files' growth explained.
6. **Heavy-only work**: `nemotron-thread-bench.py`, `parakeet-ultra-oracle.py`, `strip-surface`,
   `shell-relaunch`, `power-recovery-live` — all `call :step heavy` in the battery, all unmeasured
   here, all needing the exclusive heavy lease (`heavy_allowed=True` at 13:51, `leases: heavy=0/1`).

## 7. Runtime ceiling, stated once

The live shell is **pid 50452**, alive and reporting (`panel_state.py --read`: `freshness = FRESH`,
`producerPid=50452`, `namedState = tap-dead-endpoint`, 106 committed lines, 0 provisional), but its
bytes are not the disk's: `processo sha256=77D4D1680260` vs `disco sha256=EAB6892F23EF` (104 files),
verdict `LIVE_CODE STALE` (rc=3). Everything in §1 is therefore **source + gate level**: the code on
disk does what its oracles say, and **nothing is claimed about what the owner's screen does today**.
The stale instance's own state (`tap-dead-endpoint`, and consecutive equal committed lines such as
`"Hound and that's."` twice) is **not** evidence for or against the dedupe row: it is old code, and
genuine repeats are supposed to survive.

The last 4 MiB of its log do carry one load/release cycle, quoted verbatim:

```
13:11:43.754 WORKER REDUX_ENGINE_LOAD engine=onnx model=parakeet-redux-onnx-int4 load_s=0.84 rss_mb=492.5 loads=1
13:15:32.011 WORKER REDUX_ENGINE_RELEASED engine=onnx reason=shed-muito-alta rss_before_mb=16.1 rss_after_mb=36.7 releases=1
13:16:34.330 WORKER REDUX_ENGINE_LOAD engine=onnx model=parakeet-redux-onnx-int4 load_s=2.26 rss_mb=494.6 loads=2
```

`REDUX_BATCH_DEFERRED` does not appear anywhere in that window, and `WORKER_THREADS` /
`WORKER_COST` / `WORKER_GENAI_THREADS` / `WORKER_THREAD_PLAN` appear **zero** times — the
observability the performance lane added is not in this process. The release line **cannot** say
which gate branch decided it: `engine_policy.release(reason=…)` (`:265-283`) receives only the
`reason` label, while the gate's own `why` (`cpu-apenas` / `memoria-sustentada` /
`memoria-emergencia`) is passed to `_release_engine` and never reaches this line. So this 62 s
load→release→load pair neither confirms nor refutes the cure; it is the shape of the reported cycle,
produced by worker pid 14712 (`BRIDGE_METER … childPid=14712`, spawned 12:58:50, i.e. after
`engine_policy.py` 08:43 and `engine_switch.py` 09:20) inside shell pid 50452, which predates the
13:57:53 shell bytes. A `REDUX_ENGINE_LOAD`-per-hour count that judges the cure needs the fresh
instance of §6 item 4.

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: ScopedClosingReceipt
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['ScopedClosingReceipt']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['ScopedClosingReceipt']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-09T17:06:40.364456+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['ScopedClosingReceipt']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['ScopedClosingReceipt']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — I did not run `todo init` because this toolset has none (declared at the
  top of my result instead). The protocol I *felt* missing: there is no rule telling a closing lane
  what to do when the tree commits **during** its measurement window; I handled it by timestamping
  every run and reporting both sides of each flip (§4 F5), but a rule ("a receipt names HEAD and the
  window, and re-runs any row whose file mtime is newer than the run") would have made it mechanical.
- **verificacao adicional** — I would re-run the three browser gates under the heavy lease if this
  assignment allowed a browser; that is the only way the two worklists' central rows stop being
  UNVERIFIED. Cost: ~41 s (panel-themes) + ~100 s (neg) + ~9 s (DOM probe) + ~7 s (its neg) under a
  1800 s lease — cheap, but forbidden here.
- **checkboxes novas** — two mechanical ones: (a) after any oracle that copies product files into a
  temp dir, `node --check` (or a one-line `require`) of **every** file the copied file requires —
  that is the check that would have caught F1 before it became a `SETUP ERROR`; (b) for every
  `--neg-arm`, assert that the log contains the driver's own `NEG-ARM: PASS` string and that no
  `MUTATION IMPOSSIVEL`/`SETUP ERROR` line exists — the check that separates "caught" from "could
  not mutate" (F3).
- **review por outro subagente** — `sim-com-escopo`: re-run the three browser gates + the two
  broken-gate fixes, and verify the §5 attribution against `git log` at a frozen HEAD.
- **gate-doubt** —
  - `verde-de-verdade:` (1) `CODE-HEALTH VERDICT PASS` at 14:05 is **not** a green of the code: the
    same command said `FAIL, piorem: 8` at 13:58 on byte-identical files, and the difference is the
    baseline re-pin at 14:03:26 (`5a9e1d4`). The green is real as a statement about the pin, not
    about the tree. (2) `LOAD-SHEDDING GREEN -- arms=252` and `--neg-arm` rc=1: the driver returns 1
    only if **all 19** mutants were caught (`main()`), so the rc is not vacuous — but the transcript's
    last block prints the mutant's own population (`arms=252 pass=250 fail=2`), which a reader can
    mistake for the driver's verdict. (3) `worker-thread-limit --neg-arm` rc=1 **is** vacuous if read
    by rc alone: it exits 1 on `MUTATION IMPOSSIVEL` (F3). (4) `history-context PASS 120/120` at
    14:05 is real for those bytes, and it is the same command that said `FAIL 115/120` twenty minutes
    earlier — the pass depends on the commit, not on the worklist.
  - `falta-no-gate:` the class is "a gate that copies the tree and forgets a file the tree now
    requires": a change to `history-store.js`'s `require` graph walks straight into F1, and a change
    to `ENGINE_VISIBLE_TAGS`'s **formatting** (comments between tags) walks into F3. Neither gate has
    a precondition arm ("the mutant anchor exists", "every required sibling was copied") that would
    fail as a **setup** error distinct from "the defect survived".
  - `gate-melhor:` one mechanical check: in `redux-arm-weights-oracle.py`'s copy step, after copying,
    run `node --check I:\cc-tmp\…\store-G\history-store.js` plus a `node -e "require('./store-G/history-store.js')"`
    and exit **2** (setup) with the missing module named — the input that must leave it RED is the
    current tree (it does, with `Cannot find module './history-context-store'`).
- **confianca** — `alta` for the rows whose gates ran (the verdict lines are quoted from saved logs
  with rc and wall time, and the product bytes are hashed); `baixa` for the eight browser-gated rows
  and for every runtime statement — those are UNVERIFIED by construction, not by my failure.
- **nao verificado** — 59-theme contract (panel), no-demo-circles, hidden-scrollbar/scrolling,
  search-on-demand reachability, no bottom void, panel 240 Hz drag rate, panel-level 60-day/200-day
  DOM, overlay 59 plates/faces, overlay LED ellipse, judgment renders/stills, the 82/70 reload replay,
  reload-floor arms R1-R8 (gate broken), thread-ceiling A4 and its negative arm, and every live
  runtime behaviour (reload count, stutter, first display, drag rate, worker CPU/threads).

