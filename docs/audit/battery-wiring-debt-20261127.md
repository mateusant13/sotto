# Battery wiring debt — 2026-11-27

Lane `WiringDebt`, isolated worktree `C:\Users\Administrador\.omp\wt\tb3af0f898\m`.
Target: `_main/battery-wiring-baseline.json` (98 entries: oracle files that exist and are named in no `call :step`).
No file was deleted and no baseline entry was removed in this pass.

## Measurement and method

Command run in this tree (rc=0):

```
python _main/battery-wiring-oracle.py
CHECK census-readable    PASS  populacao=358 ligados=260 sem_passo=98
CHECK baseline-schema     PASS  0 entrada(s) sem file/reason/date
CHECK baseline-ceiling    PASS  baseline com 98 entrada(s) <= CEILING 124
CHECK new-unwired         PASS  nenhum oraculo novo sem passo
CHECK baseline-orphans    PASS  nenhuma entrada orfa
CHECK step-line-shape     PASS  nenhuma linha `call :step` nomeia uma classe que o parser nao aceita
CHECK wiring-counted      PASS  ligados=260 sem_passo=98 populacao=358
SUMMARY populacao=358 ligados=260 sem_passo=98 ceiling=124
BATTERY-VERDICT battery-wiring PASS checks=7 fail=0
rc=0
```

Every one of the 98 was run twice here: plain, and with `--neg-arm` (15 s triage ceiling; the
slow ones were retried at 40 s). The census of real references came from
`python _main/unreferenced-oracle-census.py --json` (rc=0) plus `git grep -n -F <name>` over all
tracked files, because the census deliberately ignores `docs/audit/*`, `instruments-battery.mjs`
and `runs/*` and would otherwise overstate how dead a file is. "Wired" means a literal
`call :step` line in `_main/_audit-verify-all.cmd`, exactly as `battery-wiring-oracle.py:125-131`
counts it — a name inside a `REM`, a registry, a doc or `features.json` is **not** wiring.

Classes:

- **WIRE** — real invariant, positive rc=0 within 40 s, `--neg-arm` demonstrably catches its
  injected defect, and no wired step proves the same claim.
- **WIRE-HOLD** — real invariant, but one of the gates is missing: no `--neg-arm`, a broken
  fixture, a neg-arm that is inert/red-by-error, or >40 s. Not eligible for wiring today.
- **DUPLICATE** — an existing wired step (named) already proves the invariant.
- **DEAD** — superseded/non-oracle helper with the strict proof: no code caller, no
  `call :step`, no documentation reference (inventory/config rows are not callers).

`sem_passo` before = **98**, after = **98**. No entry was removed: while a baselined file still
exists and is unwired, removing its entry makes `new-unwired` FAIL and a deletion would be a
ratchet lie. The two DEAD files are listed for a later pass that deletes the files and the
entries together (a shrinking change).

## 98-row classification

Evidence abbreviations: `pos=rc/time`, `neg=rc/time` with the printed control marker; `dup:`
names the wired step; `dead` points to the proof below.

| # | file | class | evidence / wired step |
|---:|---|---|---|
| 01 | `_cura-oracle-suite.py` | DUPLICATE | suite runner over other oracles, not an invariant; `battery-wiring` + `unreferenced-census` already gate the population; pos>15 s, no `--neg-arm` |
| 02 | `_focus-title-oracle.py` | WIRE-HOLD | real focus-title claim; pos rc=2 (`--out` required), no neg-arm |
| 03 | `_launch-gate.py` | DUPLICATE | shipped-shell launch claim; `battery-launch` (and `hidden-launch`) run that path; pos>40 s |
| 04 | `_ordem-cura-oracle.py` | WIRE-HOLD | moment-of-choice endpoint; pos rc=1 `KeyError`, neg rc=1 `wasapi_loopback` import error |
| 05 | `_oss_oracle.py` | WIRE-HOLD | pos rc=1, model file absent; neg rc=1 same setup error (not a control) |
| 06 | `aceitacao-gate.py` | WIRE-HOLD | owner register is machine-checkable; pos rc=0/0.09 s, no `--neg-arm` |
| 07 | `audio-meter-oracle.py` | WIRE | pos rc=0/1.77 s; neg rc=0/1.62 s, 3 arms RED, 0 controls broken |
| 08 | `audio-recorder-oracle.py` | WIRE | pos rc=0/0.50 s; neg rc=0/0.61 s, `NEG-ARM: PASS` |
| 09 | `battery-rows-gate.py` | DUPLICATE | dup: `battery-wiring` (battery row shape and census) |
| 10 | `benign-status-arm-oracle.py` | DUPLICATE | dup: `stall-heartbeat` (silence heartbeat truth) |
| 11 | `bridge-handler-map-oracle.py` | WIRE | pos rc=0/0.75 s; neg rc=0/0.95 s, 13 checks incl. bad-entry mutants |
| 12 | `canonical-producer-oracle.py` | DUPLICATE | dup: `history-producer-gate` (producer stamp) |
| 13 | `caption-lines-oracle.py` | WIRE-HOLD | pos rc=2, missing `_wav-before.jsonl` fixture; no neg-arm |
| 14 | `caption-overlay-free-oracle.py` | DUPLICATE | dup: `complaints-closure` (caption button opens nothing); neg rc=1 `NEG-ARM: FAIL` at 25 s |
| 15 | `caption-punctuation-oracle.py` | WIRE | pos rc=0/0.81 s; neg rc=0/1.26 s, `NEG-ARM VERDICT: PASS` — distinct from `punctuation` (model placement) |
| 16 | `caption-wrap-oracle.py` | DUPLICATE | dup: `caption-native-wrap` (native renderer is what is painted; panel caption.html is not loaded) |
| 17 | `channel-class-site-oracle.py` | WIRE-HOLD | pos rc=1, census artefact gone; neg rc=0 with mutant caught but setup broken |
| 18 | `child-channel-oracle.py` | WIRE-HOLD | real console/no-window claim; pos rc=0/1.44 s, no `--neg-arm` |
| 19 | `cine-themes-oracle.py` | WIRE | pos rc=0/4.47 s; neg rc=0/2.46 s, 8 mutants, 0 wrong/inert |
| 20 | `cinematic-designs-oracle.py` | WIRE | pos rc=0/0.73 s; neg rc=0/2.05 s, 6 mutants, 0 wrong/inert |
| 21 | `cited-instruments-oracle.py` | DUPLICATE | dup: `spec-citations` (cited proofs can be run); pos rc=1, artefacts gone |
| 22 | `cobertura-oracle.py` | DUPLICATE | dup: `unreferenced-census` + `spec-coverage` (every area has an instrument) |
| 23 | `config-keys-oracle.py` | DUPLICATE | dup: `config-truth` (`worker/config.json` truth/readers) |
| 24 | `csp-inline-oracle.py` | WIRE-HOLD | real CSP/no-inline claim; pos rc=0/0.09 s; `--neg-arm` adds a check but prints no `NEG-ARM PASS` marker |
| 25 | `delivery-rate-oracle.py` | WIRE-HOLD | real capture-rate claim; pos rc=1 `VERDICT: RED`, no neg-arm |
| 26 | `der-oracle.py` | DUPLICATE | dup: `speaker-watch` (diarization quality); pos rc=1, audio fixture absent |
| 27 | `device-ladder-doc-oracle.py` | WIRE | pos rc=0/0.09 s; neg rc=0/0.10 s, `NEG-ARM PASS`; `device-ladder-cost` measures seconds, not README order |
| 28 | `device-ladder-rescan-oracle.py` | WIRE | pos rc=0/0.35 s; neg rc=0/0.38 s, `NEG-ARM PASS` (memoized table caught) |
| 29 | `emit-queue-bound-oracle.py` | WIRE | pos rc=0/0.20 s; neg rc=0/0.36 s, 1000-post mutant caught; distinct from `qi-log-bound` (QI log vs UI emit queue) |
| 30 | `focus-and-flash-gate.py` | DEAD | proof below: >40 s, no caller/doc/battery, superseded by `hidden-launch`, `panel-flash-contradiction` |
| 31 | `focus-timeline-oracle.py` | WIRE-HOLD | real probe-summary claim; pos rc=0/0.25 s, no `--neg-arm` |
| 32 | `forbidden-audio-line-oracle.py` | WIRE-HOLD | real "device in use" line ban; pos rc=0/6.99 s, no neg-arm |
| 33 | `foreign-chars-oracle.py` | DUPLICATE | dup: `panel-language` (language/character contract); pos rc=1, neg control passes |
| 34 | `gen-cinematic-repro-oracle.py` | WIRE | pos rc=0/0.74 s; neg rc=0/0.53 s, shipped file not reproduced under mutation |
| 35 | `gen-themes-repro-oracle.py` | WIRE | pos rc=0/0.68 s; neg rc=0/0.81 s, 6/7 generated files differ under mutation |
| 36 | `hook-cost-oracle.py` | DUPLICATE | dup: `input-path` (its own doc says the hook was removed on 2026-10-30) |
| 37 | `meter-chain-oracle.py` | WIRE | pos rc=0/1.09 s; neg rc=0/5.97 s, 66 checks with mutants |
| 38 | `multivoice-oracle.py` | DUPLICATE | dup: `speaker-watch`; pos rc=1, ONNX model absent |
| 39 | `named-panel-state-oracle.py` | WIRE | pos rc=0/0.14 s; neg rc=0/0.20 s, 2 failures where >0 required |
| 40 | `no-audio-latch-oracle.py` | DUPLICATE | dup: `external-resume-latch` (no-audio evidence latch); pos rc=1 RED |
| 41 | `offline-load-guard-oracle.py` | WIRE | pos rc=0/2.70 s; neg rc=0/2.53 s, negative branch is the PASS condition |
| 42 | `offscreen-cure-comment-oracle.py` | WIRE | pos rc=0/0.15 s; neg rc=0/0.17 s, `NEG-ARM PASS` (low-value prose guard) |
| 43 | `panel-chrome-marks-oracle.py` | WIRE | pos rc=0/0.14 s; neg rc=1/0.29 s, `NEG-ARM: PASS -- 6/6`; `panel-chrome` gates CSS/chrome, not the six owner byte rows |
| 44 | `panel-flash-numbers-reconciliation-oracle.py` | DUPLICATE | dup: `panel-flash-contradiction` (flash numbers carry population/predicate) |
| 45 | `panel-startup-visibility-oracle.py` | DUPLICATE | dup: `panel-hidden-at-startup-oracle`; pos rc=1, pre-cure variant gone |
| 46 | `panel-state-atomic-oracle.py` | WIRE-HOLD | pos rc=0/6.79 s; neg not finished at 40 s |
| 47 | `panel-visibility-guard-oracle.py` | WIRE | pos rc=0/0.17 s; neg rc=0/1.00 s, `NEG-ARM PASS` on the re-assert guard |
| 48 | `phase-a-b-cycle-oracle.py` | DUPLICATE | dup: `offline-load-guard` (phase A guard → phase B consumer); pos rc=1, fixture gone |
| 49 | `preflight-refusal-visible-oracle.py` | DUPLICATE | dup: `input-path` (run.cmd refusal path); pos rc=1 `negative seek` |
| 50 | `queue-drops-whitelist-oracle.py` | WIRE-HOLD | real queue-drop claim; pos rc=0/0.31 s, no neg-arm |
| 51 | `ram_gate.py` | WIRE-HOLD | helper gate needing `--uncapped/--capped`; pos rc=2, no neg-arm |
| 52 | `ready-stream-blindness-oracle.py` | WIRE | pos rc=0/2.09 s; neg rc=0/0.25 s, `NEG-ARM PASS`; `relaunch-ready` is about PID reuse, not the PTY/readiness stream |
| 53 | `redux-live-overlay-oracle.py` | DUPLICATE | dup: `redux-live-pending-cap`; its own neg run says `NEG: NOT RUN` |
| 54 | `render-protection-gate.py` | WIRE-HOLD | real two-layer background claim; pos rc=0/0.11 s, no neg-arm |
| 55 | `restart-30s-oracle.py` | WIRE | pos rc=0/10.87 s; neg rc=0/11.43 s, pre-fix copy still loops (caught) |
| 56 | `revive-pipeline-oracle.py` | DUPLICATE | dup: `revival-gate` (`scripts\revival_gate.py`); pos rc=1, executable absent |
| 57 | `rtf-cpu-attribution-oracle.py` | DUPLICATE | dup: `cpu-tripwire` (CPU attribution); pos rc=1, cited artefact gone |
| 58 | `run-cmd-exit-oracle.py` | DUPLICATE | dup: `battery-run` + `exit-backstop`; pos/neg both >40 s |
| 59 | `run-cmd-refusal-path-oracle.py` | DUPLICATE | dup: `input-path` (run.cmd refusal, no mangled capture) |
| 60 | `run-cmd-verdict-attribution-oracle.py` | DUPLICATE | dup: `verdict-gate`; pos rc=1, neg rc=1 `NEG-ARM FAIL` |
| 61 | `runcmd-arm-coverage-oracle.py` | DUPLICATE | dup: `spec-coverage` + `seam-coverage`; pos rc=1, fixture gone |
| 62 | `s7-silence-window-oracle.py` | DUPLICATE | dup: `silence-kill` + `batch-silence-gate`; pos rc=1 |
| 63 | `scale_gate_selftest.py` | DUPLICATE | self-test helper for a moved tree; no wired invariant of its own; `gate` family is covered by `battery-heavy-gate`; pos rc=2 |
| 64 | `second-pass-default-oracle.py` | DUPLICATE | dup: `caption-wanted-default` |
| 65 | `selftest-focus-oracle.py` | WIRE | pos rc=0/0.09 s; neg rc=0/0.11 s, `NEG-ARM PASS` (self-test control) |
| 66 | `selftest-quality-oracle.py` | WIRE | pos rc=0/0.08 s; neg rc=0/0.12 s, `NEG-ARM PASS` (empty transcript refused) |
| 67 | `sidecar-wiring-oracle.py` | WIRE | pos rc=0/2.06 s; neg rc=0/2.25 s, `BELOW_NORMAL` mutant fell; `speaker-sidecar-gpu-policy` checks GPU policy |
| 68 | `skin-strip-gate.py` | DUPLICATE | dup: `strip-width` + `strip-stats-load-oracle` |
| 69 | `speaker-density-gate-oracle.py` | DUPLICATE | dup: `speaker-watch`; pos rc=1, GPU adapter absent |
| 70 | `speaker-id-oracle.py` | DUPLICATE | dup: `speaker-watch`; pos rc=1, `H:\sotto\_main\_hoje-ctrl.json` absent |
| 71 | `speaker-plumbing-oracle.py` | DUPLICATE | dup: `per-app-source-plumbing`; pos rc=1 `NameError: os` |
| 72 | `speaker-slots-oracle.py` | WIRE | pos rc=0/0.29 s; neg rc=0/0.25 s, identity RED-OK |
| 73 | `staging-hang-artefact-oracle.py` | DUPLICATE | dup: `stall-heartbeat` + `open-close-stall`; pos rc=1, quoted artefact gone |
| 74 | `stale-receipt-oracle.py` | DUPLICATE | dup: `receipt-provenance`; pos rc=0 reports 2/3 stale, neg rc=0 `NEG-ARM PASS` |
| 75 | `start-menu-shortcut-gate.py` | DUPLICATE | dup: `tray-menu`; pos rc=1 |
| 76 | `strip-drag-shell-oracle.py` | WIRE | pos rc=0/0.18 s; neg rc=0/0.35 s, 8 check(s) with mutants |
| 77 | `strip-geometry-oracle.py` | DUPLICATE | dup: `strip-geometry-restore`; pos rc=1 `FakeShell` missing attribute |
| 78 | `surface-loop-oracle.py` | WIRE | pos rc=0/0.24 s; neg rc=0/0.40 s, 2 of 5 arms RED with guard deleted |
| 79 | `tap-restart-loop-oracle.py` | DUPLICATE | dup: `tap-stall-watchdog`; pos rc=2 REFUSED, guard marker gone |
| 80 | `tap-stall-policy-oracle.py` | DUPLICATE | dup: `tap-stall-watchdog` + `tap-delivery-stall` |
| 81 | `theme-button-contrast-oracle.py` | WIRE | pos rc=0/0.11 s; neg rc=0/0.13 s, `NEG-ARM VERDICT: PASS`, mutant restored |
| 82 | `theme-button-geometry-oracle.py` | WIRE | pos rc=0/0.11 s; neg rc=0/0.22 s, `NEG-ARM VERDICT: PASS`, CRLF kept |
| 83 | `timeout-tree-ceiling-oracle.py` | DUPLICATE | dup: `batch-executor-ceiling` (`subprocess.run(timeout=)` tree ceiling); no neg-arm |
| 84 | `unfinished-items-coverage-oracle.py` | WIRE-HOLD | pos rc=0/0.20 s; `--neg-arm` output equals positive, i.e. inert control (no new RED) |
| 85 | `verdict-order-oracle.py` | DUPLICATE | dup: `verdict-gate`; its only battery mention is a `REM` at line 3316, not a step; pos rc=1 |
| 86 | `wake-tick-gate.py` | DEAD | proof below: pos rc=3 STALLED, no caller/doc/battery |
| 87 | `wasapi-buffer-fallback-oracle.py` | WIRE | pos rc=0/0.11 s; neg rc=0/0.10 s, `NEG-ARM PASS` (old period restored caught) |
| 88 | `watch-retention-fifo-oracle.py` | WIRE | pos rc=0/1.34 s; neg rc=0/0.37 s, `BRACO NEGATIVO: PASS` |
| 89 | `webview-child-gate.py` | DUPLICATE | dup: `webview2-runtime`; pos/neg both >40 s |
| 90 | `webview-shell-field-count-oracle.py` | DUPLICATE | dup: `census-instrument` (shell field census); pos rc=1, fixture gone |
| 91 | `wordmark-metrics-oracle.py` | WIRE | pos rc=0/0.12 s; neg rc=0/0.25 s, `NEG-ARM VERDICT: PASS` |
| 92 | `worker-busy-loop-oracle.py` | WIRE | pos rc=0/0.95 s; neg rc=0/1.08 s, `NEG-ARM VERDICT: PASS`; CPU half distinct from `worker-churn`/`worker-park` |
| 93 | `worker-eof-contract-oracle.py` | WIRE | pos rc=0/0.20 s; neg rc=0/0.11 s, `NEG-ARM PASS` (re-raise guard removed) |
| 94 | `worker-reload-guard-oracle.py` | DUPLICATE | dup: `worker-churn`; pos rc=1 RED on arms 1,3,4,7,8,9 |
| 95 | `worker-respawn-ceiling-oracle.py` | DUPLICATE | dup: `worker-churn` (own doc points there); pos rc=1 `NameError` |
| 96 | `worker-restart-guard-oracle.py` | DUPLICATE | dup: `worker-churn` + `worker-silence-grace`; pos rc=1, neg rc=1 `IndentationError` |
| 97 | `youtube-window-oracle.py` | WIRE-HOLD | pos rc=0/0.19 s; neg rc=1/0.20 s but `NEG-ARM` control is `FAIL` (1 check broke), not a working control |
| 98 | `zipc-designs-oracle.py` | WIRE-HOLD | pos rc=0/0.89 s; neg rc=1/2.22 s, `NEG-ARM VERDICT: FAIL -- 6 mutant(s), 1 wrong` |

Totals by class: WIRE 32, WIRE-HOLD 18, DUPLICATE 46, DEAD 2 (98 rows).

## Five recommended WIRE pairs

Ranked by invariant value, control quality and runtime. Commands were run in this tree; rc was
captured with `out=$(python _main/<f> [args] 2>&1); rc=$?`:

```
POS panel-chrome-marks-oracle.py       rc=0 | VERDICT: PASS -- B3, C3, C4, C7, C8 and D7 hold on the shipped bytes
NEG panel-chrome-marks-oracle.py       rc=1 | NEG-ARM: PASS -- 6/6 rows caught their own injected defect
POS worker-eof-contract-oracle.py      rc=0 | VERDICT: PASS -- every catchable exit now ends in a terminal event or a meaningful code
NEG worker-eof-contract-oracle.py      rc=0 | NEG-ARM PASS: a guard that re-raises must let the exception escape
POS ready-stream-blindness-oracle.py   rc=0 | VERDICT: PASS -- the readiness line goes to the log/ready-file and NOT to the PTY
NEG ready-stream-blindness-oracle.py   rc=0 | NEG-ARM PASS: an app that answered on stdout would have to be caught here
POS worker-busy-loop-oracle.py         rc=0 | VERDICT: PASS
NEG worker-busy-loop-oracle.py         rc=0 | NEG-ARM VERDICT: PASS -- control GREEN, mutant RED
POS device-ladder-doc-oracle.py        rc=0 | VERDICT: IN SYNC -- the README describes the ladder the code has today
NEG device-ladder-doc-oracle.py        rc=0 | NEG-ARM PASS
```

Why these and not the other 28 WIRE rows: each has a control that actively injects a defect and
reports it caught (not an inert flag), a source-file-only positive run, and a wired neighbour
that proves a different claim. `panel-chrome-marks` is the only baselined oracle whose neg-arm
has the exact `rc=1` + `NEG-ARM: PASS` contract of the `qi-log-bound` pair. The other four use the
self-test convention already present in this battery (`panel-chrome-neg`, `base-themes-neg`):
their neg-arm is *asserted green* when the mutant is caught, so `:expectred` would reject a
correct run. Their blocks below are paste-ready as written — do not change their rc to 1.

### 1. `panel-chrome-marks` — exact `qi-log-bound` shape (`:expectred`)

```cmd
REM `panel-chrome-marks` -- OS SEIS AFIRMACOES BYTE-A-BYTE DONO NAO PODEM SER PROSA (medido
REM 2026-11-27). `aceitacao-gate` apontava B3/C3/C4/C7/C8/D7 como frases sem instrumento; este
REM le panel.html, panel.css e os temas e prova cada uma. O mutante sem tecto E' o braco vermelho.
if exist _main\panel-chrome-marks-oracle.py (
call :step panel-chrome-marks 0 "_main\panel-chrome-marks-oracle.py;_main\aceitacao-dono.md;app\panel\panel.html;app\panel\panel.css" "%OUT%\panel-chrome-marks.log" python _main\panel-chrome-marks-oracle.py
call :record panel-chrome-marks !STEP_RC!
) else ( call :record panel-chrome-marks MISSING )
if exist _main\panel-chrome-marks-oracle.py (
call :step red-as-expected-panel-chrome-marks 1 "_main\panel-chrome-marks-oracle.py;_main\aceitacao-dono.md;app\panel\panel.html;app\panel\panel.css" "%OUT%\panel-chrome-marks-neg.log" python _main\panel-chrome-marks-oracle.py --neg-arm
call :expectred red-as-expected-panel-chrome-marks !STEP_RC! "%OUT%\panel-chrome-marks-neg.log" "NEG-ARM: PASS"
) else ( call :expectred red-as-expected-panel-chrome-marks MISSING "%OUT%\panel-chrome-marks-neg.log" "NEG-ARM: PASS" )
```

### 2. `worker-eof-contract` — self-test neg arm (`:record`)

```cmd
REM `worker-eof-contract` -- O TOPO DO WORKER NAO PODE DEIXAR O JSONL ABERTO (medido 2026-11-27).
REM `contract_guard` tem de emitir um evento terminal e devolver 4; `SystemExit` guarda o seu numero.
REM O `--neg-arm` restaura o guard que re-levanta e E' VERDE quando o apanha (rc=0, como `panel-chrome-neg`).
if exist _main\worker-eof-contract-oracle.py (
call :step worker-eof-contract 0 "_main\worker-eof-contract-oracle.py;worker\sotto_worker.py;app\webview\sotto_webview.py" "%OUT%\worker-eof-contract.log" python _main\worker-eof-contract-oracle.py
call :record worker-eof-contract !STEP_RC!
) else ( call :record worker-eof-contract MISSING )
if exist _main\worker-eof-contract-oracle.py (
call :step worker-eof-contract-neg 0 "_main\worker-eof-contract-oracle.py;worker\sotto_worker.py" "%OUT%\worker-eof-contract-neg.log" python _main\worker-eof-contract-oracle.py --neg-arm
call :record worker-eof-contract-neg !STEP_RC!
) else ( call :record worker-eof-contract-neg MISSING )
```

### 3. `ready-stream-blindness` — self-test neg arm (`:record`)

```cmd
REM `ready-stream-blindness` -- O READY VAI PARA --log/ready-file, NAO PARA O PTY (medido 2026-11-27).
REM pythonw+start em run.cmd nao tem stdout; quem disser o contrario tem de ser apanhado pelo mutante.
if exist _main\ready-stream-blindness-oracle.py (
call :step ready-stream-blindness 0 "_main\ready-stream-blindness-oracle.py;app\webview\sotto_webview.py;app\webview\run.cmd;docs\audit\launch-entry.md" "%OUT%\ready-stream-blindness.log" python _main\ready-stream-blindness-oracle.py
call :record ready-stream-blindness !STEP_RC!
) else ( call :record ready-stream-blindness MISSING )
if exist _main\ready-stream-blindness-oracle.py (
call :step ready-stream-blindness-neg 0 "_main\ready-stream-blindness-oracle.py;app\webview\sotto_webview.py;app\webview\run.cmd" "%OUT%\ready-stream-blindness-neg.log" python _main\ready-stream-blindness-oracle.py --neg-arm
call :record ready-stream-blindness-neg !STEP_RC!
) else ( call :record ready-stream-blindness-neg MISSING )
```

### 4. `worker-busy-loop` — self-test neg arm (`:record`)

```cmd
REM `worker-busy-loop` -- NENHUM while SEM SAIDA NO WORKER (medido 2026-11-27). A metade do
REM respawn ja tem dono (`worker-churn`/`worker-park`); este e' o custo de CPU, lido dos bytes.
if exist _main\worker-busy-loop-oracle.py (
call :step worker-busy-loop 0 "_main\worker-busy-loop-oracle.py;worker\sotto_worker.py;app\webview\sotto_webview.py" "%OUT%\worker-busy-loop.log" python _main\worker-busy-loop-oracle.py
call :record worker-busy-loop !STEP_RC!
) else ( call :record worker-busy-loop MISSING )
if exist _main\worker-busy-loop-oracle.py (
call :step worker-busy-loop-neg 0 "_main\worker-busy-loop-oracle.py;worker\sotto_worker.py" "%OUT%\worker-busy-loop-neg.log" python _main\worker-busy-loop-oracle.py --neg-arm
call :record worker-busy-loop-neg !STEP_RC!
) else ( call :record worker-busy-loop-neg MISSING )
```

### 5. `device-ladder-doc` — self-test neg arm (`:record`)

```cmd
REM `device-ladder-doc` -- O README DESCREVE A MESMA ORDEM DE DISPOSITIVOS DO CODIGO (medido
REM 2026-11-27). `device-ladder-cost` mede SEGUNDOS, nao a ordem documentada; trocar dois rungos
REM no README tem de ser RED no braco negativo.
if exist _main\device-ladder-doc-oracle.py (
call :step device-ladder-doc 0 "_main\device-ladder-doc-oracle.py;worker\sotto_worker.py;worker\README.md" "%OUT%\device-ladder-doc.log" python _main\device-ladder-doc-oracle.py
call :record device-ladder-doc !STEP_RC!
) else ( call :record device-ladder-doc MISSING )
if exist _main\device-ladder-doc-oracle.py (
call :step device-ladder-doc-neg 0 "_main\device-ladder-doc-oracle.py;worker\sotto_worker.py;worker\README.md" "%OUT%\device-ladder-doc-neg.log" python _main\device-ladder-doc-oracle.py --neg-arm
call :record device-ladder-doc-neg !STEP_RC!
) else ( call :record device-ladder-doc-neg MISSING )
```

When these five steps land, `battery-wiring-oracle.py` will report `ligados=265 sem_passo=93`
(98 − 5) and the baseline must lose exactly those five entries in the same commit; otherwise
`baseline-orphans` FAILS. That deletion was deliberately **not** done here: `_audit-verify-all.cmd`
is owned by another lane in this pass.

## DEAD list and proofs

Two entries meet the strict proof (no code caller, no battery `call :step`, no document reference):

| file | proof |
|---|---|
| `_main/focus-and-flash-gate.py` | `grep -c "call :step.*focus-and-flash-gate.py" _main/_audit-verify-all.cmd` → `0`; `git grep -n -F focus-and-flash-gate.py` minus baseline/self → only `_main/lane-screen-baseline.json:14`, `_main/tooling-intent-baseline.json:61`, `benchmarks/blast_radius.json:4056`, `features/features.json:897` (all inventory/config rows); no `.md`, no importer; positive run >40 s; focus/flash claims are covered by wired `hidden-launch` and `panel-flash-contradiction`. |
| `_main/wake-tick-gate.py` | same commands → battery `0`; refs only `.gitattributes:288`, `_main/tooling-intent-baseline.json:147`, `benchmarks/blast_radius.json:6977`, `features/features.json:1258`; no doc/caller; positive rc=3 `STALLED ... no_baseline=True artifact_age > bar=840s`; no `--neg-arm`; superseded by `stall-heartbeat`/`battery-heavy-gate`. |

Exact output captured:

```
$ for f in focus-and-flash-gate.py wake-tick-gate.py; do ... git grep -n -F "$f" ...; done
_main/lane-screen-baseline.json:14:    "focus-and-flash-gate.py": 4,
_main/tooling-intent-baseline.json:61:    "focus-and-flash-gate.py",
benchmarks/blast_radius.json:4056:    "_main/focus-and-flash-gate.py": {
features/features.json:897:        "_main/focus-and-flash-gate.py",
battery call :step refs: 0
.gitattributes:288:_main/wake-tick-gate.py                                    text eol=crlf
_main/tooling-intent-baseline.json:147:    "wake-tick-gate.py",
benchmarks/blast_radius.json:6977:    "_main/wake-tick-gate.py": {
features/features.json:1258:        "_main/wake-tick-gate.py",
battery call :step refs: 0
```

No file was deleted in this pass. A later pass should delete each file **and** its baseline entry
together; that is the only way `sem_passo` shrinks without breaking `new-unwired`.
