# RECIBO — T4: o mapa consolidado passa o proprio gate, sem inventar um estado

**Data:** 2026-10-11 · **Lane:** T4 (mapa consolidado) · **Ordem do dono em vigor:** NAO ABRIR O SOTTO
**Ficheiro editado (o unico):** `docs/audit/00-MAPA-CONSOLIDADO.md`
**Ficheiro criado (o unico):** `_main/receipt-20261011-audit-map-t4.md` (este)
**Nada foi lancado:** nenhum `.cmd`, nenhum `run.cmd`, nenhum shell/WebView2, nenhum worker, nenhum dos
oraculos. Toda a verificacao foi leitura de bytes.

---

## 1. O que o gate mediu

| medicao | ANTES (mapa de 2026-10-06/07) | DEPOIS |
|---|---|---|
| rc | **1 (RED)** | **0 (GREEN)** |
| `docs` | 43 | 43 |
| `findings_total` | 83 | **138** |
| `findings_distinct` | 83 | **138** |
| `count_rows` | 2 | 3 |
| `counts` | `absent-or-partial` | **`applied:47/open:91/inflight:0`** |

---

## 2. O verdicto do gate, VERBATIM

Comando (identico nas duas pontas, o argumento e o directorio da auditoria):

```
bash -lc 'I:/!manager/scripts/audit-map-gate.sh H:/sotto/docs/audit > I:/cc-tmp/gate-t4-before.out 2> I:/cc-tmp/gate-t4-before.err; echo rc=$?'
```

### 2.1 ANTES — `I:/cc-tmp/gate-t4-before.out` (152 B) + `.err` (1345 B)

```
rc=1
audit-map-gate: dir=H:/sotto/docs/audit map=00-MAPA-CONSOLIDADO.md docs=43 findings_total=83 findings_distinct=83 count_rows=2 counts=absent-or-partial
audit-map-gate: RED (rc=1) — REFUSE: map is deficient (3 cause(s))
  - CAUSE: NAMED-DOC-MISSING — source doc(s) not referenced in the map: ao-vivo-vs-redux.md ao-vivo-vs-redux-CURA.md audio-escopo.md auditoria-completa-20261007.md auto-gain.md caption-formulation.md config-inert-fixed.md device-routing.md docs-truth-20261007.md flat-endpoint.md flat-endpoint-na-app.md flicker-aceitacao.md flicker-cura.md flicker-diff-verdict.md flicker-dom-oracle.md historico-vs-redux.md live-for-owner.md load-churn.md ordem-dos-candidatos.md original-prompt-adjudication.md painel-atraso-e-acerto.md painel-texto.md panel-gap.md panel-v2.md precisao-int8-custo.md predictor-carry-cura.md reinicio-30s.md run-cmd-gaps-fixed.md sotto-vs-referencia.md sotto-vs-referencia.RECEIPT.md speech-separation.md tap-restart-loop.md tracked-durability.md transcript-duplicacao.md
  - CAUSE: ROW-NO-STATE — finding row(s) with no state from the closed vocabulary (map line(s): 118 121 122 126 130 155 158 161 165 167 168 171 174 179)
  - CAUSE: LABEL-UNMAPPED — finding label(s) declared by a source doc but absent from the map: F1 F10 F11 F12 F13 F14 F15 F16 F17 F18 F19 F2 F20 F3 F32 F4 F5 F6 F7 F8 F9 Finding A Finding B Finding C Finding D G1 G2 G3 G5 H1 H2 H3 H4 H5 H6
  The audit may NOT be reported as finished. 'N/N axes delivered' is not 'work done'.
```

### 2.2 DEPOIS — `I:/cc-tmp/gate-t4-after.out` (295 B) + `.err` (0 B, vazio)

```
rc=0
audit-map-gate: dir=H:/sotto/docs/audit map=00-MAPA-CONSOLIDADO.md docs=43 findings_total=138 findings_distinct=138 count_rows=3 counts=applied:47/open:91/inflight:0
audit-map-gate: GREEN (rc=0) — map complete: 43/43 docs named, 138 distinct finding(s), every row stated, applied/open counted
```

---

## 3. Identidade do que foi entregue

- `docs/audit/00-MAPA-CONSOLIDADO.md` = **36 541 B**, sha256
  `2D9C9F389A64CA2218C6B254982196597CDC748987905FEDE60C5129E865E399`, **359 linhas, 0 CRLF** (LF-only,
  como o original).
- **43 docs-fonte** (a populacao que o gate mede) — todos nomeados no mapa, na seccao *Fontes*.
- **138 linhas de achado** = as **62** linhas #1-#62 (os achados de 2026-10-06/07, intactas no estado) +
  **76** entradas novas do *Indice de rotulos* (um par doc x rotulo). O indice existe porque o gate exige
  cada rotulo que uma fonte declara presente no mapa; **um achado indexado nao e um achado novo** — cada
  entrada repete o estado da linha que indexa, e diz de qual linha o herdou.

---

## 4. Os quatro estados que mudaram nas linhas #1-#62

| linha | de | para | o que estabelece |
|---|---|---|---|
| #2 (braco live entrega `blank_frac=1.0`) | IN-FLIGHT | **APPLIED** | `docs/audit/blank-frames-root-cause.md:6-9` — *"nothing in the worker is broken. The capture is alive and the model is fine — the audio in the default render endpoint's mix during every failing run contains no speech ... and `main()`'s verdict ladder called that state `model-emitted-nothing`"*. A lane entregou o artefacto e o verdict foi corrigido; a linha deixa de apontar para uma lane em voo |
| #22 (`use_vad` default `False`) | OPEN | **APPLIED** | `docs/audit/auditoria-completa-20261007.md:597` — *"`done_text_max_chars` (`:2223`) e `use_vad` default `True` (`:2333`)"* — e a arvore viva confirma: `use_vad = bool(cfg.get("model", {}).get("use_vad", True))` em `worker/sotto_worker.py:4257` (pin abaixo) |
| #37 (`CoInitializeEx` rejeita `S_FALSE`) | OPEN | **APPLIED** | `docs/audit/flat-endpoint.md:125-130` — *"Three outcomes, because they differ in what the caller then owes: `S_OK`/`S_FALSE` -> a reference was taken (`COM_REF_TAKEN`)"*; e `:140-142` mede o pos-fix (*"oracle arm `genuine-failure-refused` was `CRASH` pre-fix, `raise` ... post-fix"*). Na arvore viva: `if hr in (S_OK, S_FALSE):` em `worker/wasapi_loopback.py:204` |
| #53 (`AGENTS.md` cita `worker/runs/exit3-armB-worker.jsonl`) | OPEN | **APPLIED** | o proprio `AGENTS.md:169` retrata o texto por nome: *"o artefacto EXISTE, em `H:\sotto\_main\exit3-armB-worker.jsonl` ... O texto AUSENTE / DANGLING que aqui esteve era um falso negativo de um `statSync` sobre `worker/runs/` (directorio errado)"* |

Nenhuma outra linha #1-#62 mudou de estado. Em particular ficam **OPEN** por falta de evidencia citavel:
#4 (o painel aparece sozinho), #45 (`docs/roadmap.md:53` ainda descreve Tauri — o `README.md` da raiz e que
foi reescrito), #46, #47, #48, #54 e todas as linhas #44-#62 nao listadas acima.

---

## 5. As 76 entradas do indice de rotulos (o que foi ACRESCENTADO ao mapa)

Coluna *frase-fonte*: a linha do proprio doc que declara o achado (citada por numero, verbatim ate 190
caracteres, com `**` removido). Coluna *estado*: `herdado da linha #N` = o estado ja estava no mapa
desde 2026-10-06/07 e **nao** foi re-medido nesta revisao; a citacao entre parenteses, quando existe, e o
que a linha #N invoca. Resumo: **29 APPLIED, 47 OPEN, 0 IN-FLIGHT**.

| rotulo | doc:linha | estado | frase-fonte (o achado) | porque / nota |
|---|---|---|---|---|
| F1 | `audio-path.md:268` | **APPLIED** | F1 — ROOT CAUSE: poll interval exceeds the granted capture ring → silent overflow. | herdado da linha #1 (period = min(0.005, ...) = 5 ms) |
| F2 | `audio-path.md:274` | **OPEN** | F2 — The overflow is invisible because `flags` is read and discarded. | herdado da linha #9 |
| F3 | `audio-path.md:279` | **OPEN** | F3 — The 100 ms-buffer fallback is dead code. | herdado da linha #36 |
| F4 | `audio-path.md:284` | **APPLIED** | F4 — `CoInitializeEx` guard rejects `S_FALSE`, so a second open in the same thread raises. | herdado da linha #37 (medido pos-fix em flat-endpoint.md:125-142) |
| F5 | `audio-path.md:302` | **OPEN** | F5 — Accounting: `tick` read as `final`. `sotto_worker.py:1284-1301` labels the periodic line | herdado da linha #38 |
| F6 | `audio-path.md:306` | **OPEN** | F6 — `_pump` mutates `buf`/`acc` with `np.concatenate` per emit (`wasapi_loopback.py:492-496`) — | herdado da linha #39 |
| F1 | `shell-bridge.md:45` | **APPLIED** | ### F1 — [MEASURED] `exec_js` runs every injected script twice (HIGH) | herdado da linha #10 |
| F2 | `shell-bridge.md:93` | **OPEN** | ### F2 — [MEASURED] The "no audio" falsifier swallows a real worker error (HIGH) | herdado da linha #11 |
| F3 | `shell-bridge.md:123` | **OPEN** | ### F3 — [MEASURED] An empty caption counts as proof-of-life and clears the death banner (MED) | herdado da linha #12 |
| F4 | `shell-bridge.md:160` | **OPEN** | ### F4 — [MEASURED-by-read] `start()` returns `true` even when no worker was spawned (MED) | herdado da linha #13 |
| F5 | `shell-bridge.md:174` | **OPEN** | ### F5 — Lock held across a blocking UI round-trip (MED) | herdado da linha #14 |
| F6 | `shell-bridge.md:190` | **OPEN** | ### F6 — `_schedule_restart` does not cancel the previously armed timer (MED/LOW) | herdado da linha #15 |
| F7 | `shell-bridge.md:207` | **OPEN** | ### F7 — [MEASURED] State-name sets are separator-sensitive where the JS arm normalises (LOW) | herdado da linha #40 |
| F8 | `shell-bridge.md:226` | **OPEN** | ### F8 — A status line without `type` is silently dropped (LOW/latent) | herdado da linha #41 |
| F9 | `shell-bridge.md:235` | **OPEN** | ### F9 — `stop()` emits no final status on the Python side (LOW) | herdado da linha #42 |
| F10 | `shell-bridge.md:242` | **OPEN** | ### F10 — `_spawn()` runs on the restart thread without `_lock` (LOW, race) | herdado da linha #43 |
| F1 | `doc-vs-code.md:21` | **OPEN** | / F1 / `docs/README.md:8` "No application code has been written" / ~5.5k lines of app+worker code / code wins / | herdado da linha #44 |
| F2 | `doc-vs-code.md:22` | **OPEN** | / F2 / `docs/README.md`, `docs/roadmap.md`, `README.md` describe a Tauri/Rust/CPAL/`transcribe.cpp`/Parakeet/SQLite stack as THE stack; `README.md:64` "Status: Planning." / the shipped app i | herdado da linha #45 (o README.md da raiz foi reescrito, mas docs/roadmap.md:53 ainda a descreve) |
| F3 | `doc-vs-code.md:23` | **OPEN** | / F3 / `AGENTS.md:169` "(arm P 0 of 41 samples …)" — panel not visible at startup / `AGENTS.md:215` same file says the panel IS visible 50 ms–7 s; the flash census says so too / census wins; | herdado da linha #46 |
| F4 | `doc-vs-code.md:24` | **OPEN** | / F4 / `AGENTS.md:89` "fp16 1230 MB" / measured 1 307 568 147 B = 1247 MiB / disk wins; 1230 stale / | herdado da linha #47 |
| F5 | `doc-vs-code.md:25` | **OPEN** | / F5 / `AGENTS.md:119` cites `worker-bridge.js:133` as "STATE_MAP" / `STATE_MAP` is declared at `:114`; `:133` is one entry inside it / code wins (citation nit) / | herdado da linha #48 |
| F6 | `doc-vs-code.md:26` | **OPEN** | / F6 / `docs/oss-approaches-20261006.md:214` ranks "flip use_vad" #1 / §10 (`:444`–`:475`) RETRACTS it: "NO-OP on the bundled sample" / §10 wins; §5 left standing / | herdado da linha #49 |
| F7 | `doc-vs-code.md:27` | **OPEN** | / F7 / `docs/live-captions-20261006.md:214` "keep Electron for now … WebView2 saves ~214 MB" / later same day: WebView2 IS the app and costs +33% MORE / later measurement wins / | herdado da linha #50 |
| F8 | `doc-vs-code.md:28` | **OPEN** | / F8 / `docs/full-audit-transcription-20261006.md:310,326` describes the "1200 ms rule" join / `caption-formulation.js:72` `SENTENCE_GAP_S = 8` on the AUDIO timeline; the 1200 ms wall rule i | herdado da linha #51 |
| F9 | `doc-vs-code.md:29` | **OPEN** | / F9 / `docs/webview-shell-20261006.md:90` "fields compared: 14 / MISMATCHES: 0" / I reproduced MISMATCHES: 0, but 64 fields by the doc's own described method / claim holds; the count "14" i | herdado da linha #52 |
| F10 | `doc-vs-code.md:30` | **APPLIED** | / F10 / `AGENTS.md:25` cites `worker/runs/exit3-armB-worker.jsonl` / that file is not there; it lives at `_main/exit3-armB-worker.jsonl` / code wins (wrong path cited) / | herdado da linha #53, fechada nesta revisao pelo proprio AGENTS.md:169 |
| F1 | `window-visibility.md:186` | **OPEN** | * F1 — Self-show with no user action (the axis itself). `edgechromium.py:348` `form.Show()` under `transparent=True`; `sotto_webview.py:995` sets `transparent` by default; measured on screen | herdado da linha #4 (dois censos do mesmo instrumento discordam; o AGENTS.md marca o par NAO RECONCILIADO e a ordem do dono suspendeu o censo) |
| F2 | `window-visibility.md:187` | **OPEN** | * F2 — Census predicate does not match its declared meaning. `I:/!manager/scripts/window-census.ps1:11-14` ("on the screen") vs `:60-70` (`MainWindowHandle`, no monitor test). Fix already ex | herdado da linha #31 |
| F3 | `window-visibility.md:188` | **OPEN** | * F3 — Census is not panel-specific. `window-census.log` alarms on `cmd`/`dwm`/`python` today. An `ALERTA-JANELA` cannot be attributed to the panel without a second census. | herdado da linha #32 |
| F4 | `window-visibility.md:189` | **OPEN** | * F4 — Stale/contradictory docs in `sotto_webview.py`. `:1013-1014` says the flash is handled by the OFFSCREEN position "below", while `:992` creates at real geometry and `:1259-1262` says O | herdado da linha #33 |
| F5 | `window-visibility.md:190` | **APPLIED** | * F5 — Dead method + unexplained live position. `_move_into_place` (`:1083`) has no caller (`grep "_move_into_place(" → only the `def`). Separately, the live hidden panel sat at `x=-10000` ( | herdado da linha #59 (a metade do metodo morto; a posicao viva e observacao de processo, fora do ficheiro) |
| F6 | `window-visibility.md:191` | **OPEN** | * F6 — `_on_navigation_start` early-returns on `self.visible` (`:1549`). Once the owner shows the panel, later navigations are never re-hidden. Intended, but it means "shown once" ⇒ "never a | herdado da linha #60 |
| F7 | `window-visibility.md:192` | **OPEN** | * F7 — `run.cmd` promise vs behaviour. `run.cmd:6` "start hidden"; the shell flashes on screen at startup (F1). The wrapper is otherwise correct (pythonw, `--check-args` preflight, `--log` r | herdado da linha #61 |
| F1 | `windows-landmines.md:309` | **OPEN** | - F1 `_main/_probe/console-census.py:106` — `creationflags=0x08000000 / 0x00000008` | herdado da linha #5 |
| F2 | `windows-landmines.md:312` | **OPEN** | - F2 `_main/device-silence-oracle.py:71`, `_main/panel-exit3-oracle.py:160`, | herdado da linha #34 |
| F3 | `windows-landmines.md:315` | **OPEN** | - F3 `_main/run-live-hidden.py:71` — same missing `except`; and `DETACHED_PROCESS` | herdado da linha #35 |
| F4 | `windows-landmines.md:317` | **OPEN** | - F4 `_main/_run-hidden.py:24` — `subprocess.run(timeout=)` around the multi-process | herdado da linha #62 |
| G1 | `launch-entry.md:87` | **APPLIED** | G1 — a missing panel still reports 0. `--check-args` returns at | herdado da linha #6 (--check-args devolve 3 PANEL_MISSING) |
| G2 | `launch-entry.md:94` | **APPLIED** | G2 — a missing `pywebview` still reports 0. `import webview` is late, inside | herdado da linha #7 (devolve 1) |
| G3 | `launch-entry.md:98` | **APPLIED** | G3 — the shell can hang after `STAGING_LOADED` and `run.cmd` still says 0. | herdado da linha #8 (ready-file fresco + --wait-ready, sai 4) |
| G4 | `launch-entry.md:102` | **APPLIED** | G4 — if `pythonw.exe` is absent, the app launches under `python.exe`. | herdado da linha #16 (recusa alta e sem janela, sai 3) |
| G5 | `launch-entry.md:119` | **OPEN** | G5 — the pre-flight itself is a `pythonw` run with no stdout. argparse writes | a fonte diz que e BY DESIGN (launch-entry.md:124-125); fica aberto enquanto o rc for o unico sinal |
| G1 | `run-cmd-gaps-fixed.md:26` | **APPLIED** | ### G1 — a missing panel reported 0 (`run.cmd` exited 0 while the app exits 3) | o doc e o recibo de fecho (:108 BEFORE rc=0 -> AFTER rc=3) |
| G2 | `run-cmd-gaps-fixed.md:39` | **APPLIED** | ### G2 — a missing `pywebview` reported 0 | o doc e o recibo de fecho (:109 BEFORE rc=0 -> AFTER rc=1) |
| G3 | `run-cmd-gaps-fixed.md:51` | **APPLIED** | ### G3 — a hang reported 0 | o doc e o recibo de fecho (:110 BEFORE rc=0 -> AFTER rc=4 com recibo de HANG) |
| G4 | `run-cmd-gaps-fixed.md:84` | **APPLIED** | ### G4 — the `pythonw` → `python.exe` fallback put a console on the screen | o doc e o recibo de fecho (:111 BEFORE rc=0 -> AFTER rc=3) |
| Finding A | `oracles.md:404` | **OPEN** | Finding A — stale top-level receipt. `_main/panel-exit3-oracle.log` mtime `03:54:30`, | herdado da linha #29 |
| Finding B | `oracles.md:409` | **OPEN** | Finding B — focus theft is a green. `_main/webview-selftest.log` records | herdado da linha #28 |
| Finding C | `oracles.md:413` | **OPEN** | Finding C — `run-cmd-exit-oracle` is currently RED on the census conjunct. Both | herdado da linha #30 |
| Finding D | `oracles.md:418` | **OPEN** | Finding D — a negative arm with no receipt. `_main/runcmd-entry-driver.py`'s `bogus` | herdado da linha #58 |
| H1 | `oracles.md:393` | **OPEN** | / H1 / Worker `--selftest` asserts nothing about output quality / `worker/sotto_worker.py:986-999` (`empty` computed, never used as a failure) / Documented green-on-word-salad for two days ( | herdado da linha #25 |
| H2 | `oracles.md:394` | **APPLIED** | / H2 / `queue_drops` never asserted / `worker/sotto_worker.py:1317` (produced), no reader in `_main/` / Audio lost between the tap and ASR is invisible. / | herdado da linha #26 (delivery-rate-oracle afirma queue_drops == 0) |
| H3 | `oracles.md:395` | **OPEN** | / H3 / Panel ARM A needs one caption / `_main/panel-exit3-oracle.py:999` / A 35 % capturer paints LIVE. / | herdado da linha #27 |
| H4 | `oracles.md:396` | **OPEN** | / H4 / `model-spec-oracle` has no negative arm / `_main/model-spec-oracle.py:41` / Drift detector, not an oracle with a red colour. / | herdado da linha #56 |
| H5 | `oracles.md:397` | **OPEN** | / H5 / `_oss_oracle` has no negative arm / `_main/_oss_oracle.py` (single `-c`, 4 static checks) / A doc-truth check that was never shown able to fail. / | herdado da linha #57 |
| H6 | `oracles.md:398` | **OPEN** | / H6 / Shell selftest logs `focus_stolen=true` and still exits 0 / `_main/webview-selftest.log` (`focus_after=4331806 … focus_stolen=true` then `SELFTEST rc=0`) / Focus theft is measured but | herdado da linha #28 (segunda entrada do mesmo achado que Finding B) |
| F1 | `auditoria-completa-20261007.md:63` | **APPLIED** | / F1 / P0 / código + log / o arranque documentado (`run.cmd`) não arranca worker nenhum → Alt+C nunca transcreve / `app/webview/run.cmd:155`, `app/webview/sotto_webview.py:1824-1825, 2454-24 | §12.3 (:695-702): corrigido com START_REASONS + guarda antes do spawn + gate novo; §11 :619 |
| F2 | `auditoria-completa-20261007.md:64` | **OPEN** | / F2 / P0 / medido / o HISTORY não pode ser alimentado: nenhuma meta do motor live traz `producer` → 0 linhas no disco / `app/electron/history-source.js:51,61-63`, `panel.js:335-351`, `capti | o gate da fonte diz PRODUCER-VERDICT: no-producer-in-tree (:663) e o transcript foi fechado ao motor live por ordem do dono (:752); nota 2026-10-11: a arvore viva passou a carimbar producer  |
| F3 | `auditoria-completa-20261007.md:65` | **APPLIED** | / F3 / P0 / código + medido(repo) / `done.verdict="captions-emitted"` com `captions:0` e exit 0 / `worker/sotto_worker.py:2862, 3030` / | §11 :588: captions==0 ja nao produz captions-emitted (verdict-gate GREEN 11/11); residual declarado em :774-775 |
| F4 | `auditoria-completa-20261007.md:66` | **APPLIED** | / F4 / P0 / código + medido(repo) / o tap WASAPI nunca é fechado na rotação; o endpoint abandonado continua a entregar áudio e a somar contadores / `worker/sotto_worker.py:2574-2579`, `worke | §11 :590: VERDICT PASS 71/71, stop() idempotente e nenhum on_block depois de stop(); residual: rotacao real nao exercida (:765-767) |
| F5 | `auditoria-completa-20261007.md:67` | **APPLIED** | / F5 / P1 / medido(repo) / o hot reload do painel navega para `file://…panel.html?sotto_hr=N` → `chrome-error://chromewebdata/`, o painel deixa de pintar até reiniciar / `app/webview/sotto_w | §11 :620: reload_panel_assets faz o bounce por stage.html; verificado por LEITURA, um hot reload real nao foi medido (:761-763) |
| F6 | `auditoria-completa-20261007.md:68` | **APPLIED** | / F6 / P1 / medido / guarda morta: `panel.js` lê `engine.state().provisionalRoute`, campo que o motor nunca devolve / `panel.js:104` vs `caption-formulation.js:582-586` / | §11 :621 + panel-state-guard GREEN 3/3 (:587): state().provisional existe e bate com o literal |
| F7 | `auditoria-completa-20261007.md:69` | **APPLIED** | / F7 / P1 / código / a app não tem como ser fechada pela UI: `quit` existe na ponte e nenhum controlo o chama / `panel.js` (0 chamadas), `sotto_webview.py:1234`, `preload.js:103`, `main.js:8 | §11 :621: bridge.quit() (panel.js:961) e um controlo que o chama |
| F8 | `auditoria-completa-20261007.md:70` | **APPLIED** | / F8 / P1 / código / dois classificadores independentes do mesmo status; o do painel é uma regex de prosa que não conhece o vocabulário do worker / `panel.js:619` vs `sotto_webview.py:289-31 | §11 :621: statusPayload/statusKind no painel |
| F9 | `auditoria-completa-20261007.md:71` | **OPEN** | / F9 / P1 / raciocinado / o campo de busca do painel não pode receber teclado: a janela é `WS_EX_NOACTIVATE` + `focusable(false)` e é mostrada com `SW_SHOWNOACTIVATE` / `sotto_webview.py:147 | a fonte transfere a decisao para o dono (:481, :762): hoje nao tem backend nem teclado e nao foi exercido |
| F10 | `auditoria-completa-20261007.md:72` | **OPEN** | / F10 / P1 / medido(repo) / RTF > 1 na CPU: a app não acompanha a fala em tempo real; CUDA é pedido e não carrega / `_main/_review-segrerun.out`, `docs/model-specs/README.md:130-146` / | a fonte transfere a decisao para o dono (:756-757: GPU, export com chunk menor, ou dizer que esta atrasado) |
| F11 | `auditoria-completa-20261007.md:73` | **APPLIED** | / F11 / P2 / código / `max_symbols_per_step: 10` é usado como orçamento do *chunk*, não por frame / `worker/sotto_worker.py:466,736,750-780` vs `docs/model-specs/README.md:83-85` / | :771: verificado por caminho de codigo (teto por frame); a corrida do modelo nao foi feita |
| F12 | `auditoria-completa-20261007.md:74` | **APPLIED** | / F12 / P2 / código / o segundo passe (M3) não repõe o front-end cache-aware nem o VAD (`self.sp`), e não há reset na rotação de dispositivo / `worker/sotto_worker.py:567-587, 2365, 2443-244 | §11 :615: a sonda fresh-processor da GREEN (dois processadores distintos, buffers proprios); o TEXTO do segundo passe nao foi medido (:768-770) |
| F13 | `auditoria-completa-20261007.md:75` | **APPLIED** | / F13 / P2 / código / `model.lang_id` ausente cai no locale do host (`os`), não no `auto` documentado / `worker/sotto_worker.py:1971-1974`, `worker/lang_prompt.py:236-254` / | despachado ao worker (:544); a arvore viva diz THE DEFAULT IS auto, NOT os (F13) (sotto_worker.py:4121-4146) e o AGENTS.md tem a linha RESOLVED do lang_id — estabelecido pela ARVORE+contexto |
| F14 | `auditoria-completa-20261007.md:76` | **APPLIED** | / F14 / P2 / código / `use_vad` no código tem default `False` e contradiz `config.json`/docs; `create_streaming_processor()` é incondicional / `worker/sotto_worker.py:2004, 499-500` / | §11 :597: use_vad default True (sotto_worker.py:4195 no ficheiro vivo) — fecha tambem a linha #22 |
| F15 | `auditoria-completa-20261007.md:77` | **OPEN** | / F15 / P2 / código / o candidato de dispositivo é ordenado UMA vez no arranque; a cura documentada (`prefer_rendering_now`) não existe / `worker/wasapi_loopback.py:594` (sem caller), `docs/ | nenhuma frase da fonte nomeia cura nem transferencia para este achado (nem em :544 nem em §12.7) e a arvore viva nao tem prefer_rendering_now |
| F16 | `auditoria-completa-20261007.md:78` | **APPLIED** | / F16 / P2 / código / `GetBuffer` chamado com 4 de 5 parâmetros (o 5.º, `pu64QPCPosition`, é out-pointer) / `worker/wasapi_loopback.py:855-863, 892` / | despachado a captura (:544); a arvore viva declara CINCO out-parameters e passa o 5. como NULL explicito (wasapi_loopback.py:920-926, :978) — estabelecido pela ARVORE |
| F17 | `auditoria-completa-20261007.md:79` | **APPLIED** | / F17 / P2 / código / `asr.labels` + `done.text` crescem sem limite e saem numa única linha JSONL no fim / `worker/sotto_worker.py:526, 771, 3023` / | §11 :594-597: labels_pruned e done_text_max_chars legiveis no disco (grep do coordenador) |
| F18 | `auditoria-completa-20261007.md:80` | **OPEN** | / F18 / P2 / código / excepções fora dos poucos `try` escapam ao contrato JSONL (EOF sem `done`/`error`) / `worker/sotto_worker.py:808-810, 1482, 1966, 2100` / | nenhuma frase da fonte nomeia cura nem transferencia para este achado; nada na arvore o fecha |
| F19 | `auditoria-completa-20261007.md:81` | **APPLIED** | / F19 / P2 / código / `docs/AGENTS.md:102` (contexto auto-carregado por TODOS os agentes) afirma que o segundo passe está AUSENTE — é falso nesta revisão / `AGENTS.md:102` vs `worker/sotto_w | o proprio AGENTS.md retracta por nome (CORRECTED AGAIN 2026-10-07 — the M1-M3 SECOND PASS IS PRESENT AND WIRED ON THE LIVE PATH) e a lane de docs entregou (:651) |
| F20 | `auditoria-completa-20261007.md:82` | **APPLIED** | / F20 / P2 / código / o `README.md` da raiz descreve outro produto (Tauri/Rust/Svelte, "Status: Planning") enquanto a app WebView2 existe / `README.md:48-64` / | o README.md vivo diz que a app que existe e Python+WebView2 e marca o Tauri Planned, NOT implemented (README.md:12-16, :48-52); a linha #45 fica OPEN porque docs/roadmap.md:53 ainda o descre |

Nota de leitura do indice: **dois tokens iguais em docs diferentes sao achados diferentes** — o `F1`
da `audio-path.md` e o poll de 25 ms; o `F1` da `shell-bridge.md` e o `exec_js` duplo; o `F1` da
`auditoria-completa-20261007.md` e o worker que nao arrancava. Por isso o indice tem uma linha por PAR
(doc, rotulo) e nao uma por token.

---

## 6. Transparencia: o que assenta na ARVORE, nao numa frase de fonte

A regra desta lane era: nao escrever APPLIED sem uma frase de fonte, ou uma linha da arvore viva citada
com ficheiro e numero. Tres das entradas novas assentam na ARVORE e **dizem-no na propria linha**:

- **F13** (`auditoria-completa-20261007.md`) — o audit despachou-o ao worker (`:544`) e nenhuma frase do
  doc o fecha; fecha-o o comentario do ficheiro vivo: `worker/sotto_worker.py:4183` — *"THE DEFAULT IS
  `auto`, NOT `os` (F13)"* — mais a linha RESOLVED do `lang_id` no `AGENTS.md`. **Evidencia de arvore +
  contexto, nao de fonte.**
- **F16** (idem) — despachado a captura (`:544`); fecha-o a arvore viva:
  `worker/wasapi_loopback.py:920-925` declara os CINCO out-parameters (*"the earlier [declaration] declared
  only FOUR"*) e `:978` passa o 5.o como `None` explicito. **Evidencia de arvore.**

- **#53 / F10 de `doc-vs-code.md`** — assenta numa retractacao DOCUMENTAL (`AGENTS.md:169`), nao numa
  correccao de codigo: o achado era o caminho errado citado pelo proprio `AGENTS.md`, e o proprio
  `AGENTS.md` o retrata e da o caminho certo. A linha #53 herdou esse fecho nesta revisao.

Ficam DELIBERADAMENTE **OPEN**, apesar de a fonte lhes tocar, os achados em que a melhoria nao fecha o
achado: **F2** da auditoria (o gate da fonte continua `PRODUCER-VERDICT: no-producer-in-tree`, e a
arvore viva so prova que o carimbo existe, NAO que ele chega ao `meta.producer` que o gate canonico le —
por isso a linha carrega um `NAO MEDIDO` em vez de um APPLIED) e **F20** da auditoria, que esta APPLIED
sem fechar a linha #45: o `README.md` da raiz foi reescrito, mas `docs/roadmap.md:53` ainda descreve a
stack Tauri.

---

## 7. O que NAO foi feito (e porquê)

- **Nada foi lancado** — a ordem do dono de 2026-10-11 (*"para de abrir o sotto, ta travando meu pc
  quando ele abre"*) cobre o shell, o worker, o `run.cmd` e o proprio `_main\_audit-verify-all.cmd`.
  Nenhum oraculo foi corrido, nem os que nao precisam de shell.
- **Nenhum estado antigo foi re-medido:** as 18 linhas APPLIED de 2026-10-06/07 foram **herdadas**, e o
  mapa di-lo ("As linhas #1-#62 mantem o estado que a revisao de 2026-10-06/07 verificou na arvore").
- **Nada foi escrito fora dos dois ficheiros** nomeados no topo: nenhum `git add`/`commit`, nenhum toque
  em `worker/`, `app/` ou nos docs-fonte (todos lidos, nenhum editado).

---

## 8. Correccoes durante a escrita (regra 2 do `AGENTS.md`: nomeie a revisao)

O primeiro rascunho do mapa citava `sotto_worker.py:4195` (`use_vad`) e `:2092/2540/2578` (`producer`) —
ancoras medidas numa revisao anterior do worker. Antes de escrever o recibo re-medi o ficheiro vivo:
**`worker/sotto_worker.py` = 295 867 B, sha256 `2C0AF4FB…`** (o pin do `AGENTS.md`, 291 873 B /
`EFDFB098…`, ja era ele proprio stale) e **`worker/wasapi_loopback.py` = 51 215 B, sha256 `09C65E94…`**.
As ancoras foram corrigidas para a revisao medida: `use_vad` em `:4257`, o comentario F13 em `:4183`,
`REDUX_PRODUCER` em `:3069` com os carimbos em `:3567`/`:3605`, e o `period = min(...)` da linha #1 em
`:958` (o `:475` da linha #1 e de 2026-10-06 e o mapa avisa que os `file:line` das linhas #1-#62 sao
HINT). **Licao, a mesma que o `AGENTS.md` ja tinha escrito: um `file:line` e uma afirmacao com prazo de
validade — o pin tem de ser re-medido antes de ser citado.**

---

## 9. Estado final

```
audit-map-gate: GREEN (rc=0) — map complete: 43/43 docs named, 138 distinct finding(s), every row stated, applied/open counted
mapa: 36 541 B · sha256 2D9C9F389A64CA2218C6B254982196597CDC748987905FEDE60C5129E865E399 · 359 linhas · 0 CRLF
47 APPLIED / 91 OPEN / 0 IN-FLIGHT = 138 linhas de achado
```
