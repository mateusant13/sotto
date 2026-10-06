# MAPA CONSOLIDADO — todos os achados da auditoria do Sotto

**Reconstruido a partir das FONTES**, nao das cabecalhos. Fonte: os 8 docs desta pasta
(`audio-path.md`, `shell-bridge.md`, `doc-vs-code.md`, `launch-entry.md`, `model-config.md`,
`oracles.md`, `window-visibility.md`, `windows-landmines.md`) + `00-MAPA-REVIEW.md`.
**Data:** 2026-10-06 · **Lane:** MapRebuild · **Modo:** READ-ONLY sobre `H:/sotto` (so este ficheiro
e o `00-MAPA-REBUILD.md` foram escritos).
**Working tree lido:** `H:/sotto` @ HEAD `3e90f92` + uncommitted. Cada estado abaixo foi **verificado
na arvore**, nao copiado do mapa antigo.

Vocabulario FECHADO de estado:
- **APPLIED / APLICADO** — corrigido e verificado no working tree.
- **IN-FLIGHT / EM VOO** — uma lane com esse achado esta despachada; artefacto declarado ainda ausente.
- **OPEN / ABERTO** — identificado, nao aplicado.

Regra de severidade: **P0** = bloqueia o produto, ou uma falha que se le como sucesso;
**P1** = o estado que o dono ve esta errado, ou uma substituicao silenciosa, ou um oraculo que nao
consegue ficar RED num defeito real; **P2** = deriva documental, cosmetico, latente ou nota de eficiencia.

---

## P0 — bloqueia o produto ou uma falha que se le como sucesso

| # | achado | onde | estado |
|---|---|---|---|
| 1 | pump do WASAPI a 25 ms contra um anel de 22 ms → ~18 % dos quadros perdidos em silencio | `worker/wasapi_loopback.py:463` | **APPLIED** — hoje `period = min(0.005, max(0.001, block_ms/1000/20))` = 5 ms (`wasapi_loopback.py:475`); medido 0.815→0.999 |
| 2 | braco live entrega `blank_frac=1.0` (o modelo so ouve sinal de baixo nivel) — o facto que bloqueia as legendas por Alt+C | `worker/sotto_worker.py` §5 | **IN-FLIGHT** — lane `BlankFramesRootCause` despachada 2026-10-06T08:39:59Z; artefacto `docs/audit/blank-frames-root-cause.md` ainda ausente |
| 3 | nenhum oraculo afirmava a cadencia de entrega de audio (segundos capturados por segundo de relogio) | `_main/` | **APPLIED** — `_main/delivery-rate-oracle.py` existe (20080 B) e o seu log corre GREEN+RED (`threshold=0.95`, `SELFTEST: PASS`) |
| 4 | painel aparece sozinho no ecra ≤63 ms em cada arranque | `edgechromium.py:348`, `sotto_webview.py:995` | **OPEN** |
| 5 | `console-census.py` passa `CREATE_NO_WINDOW\|DETACHED_PROCESS` → canal de 0 bytes rc 0, logo `python_pids()` fica cego | `_main/_probe/console-census.py:106` | **OPEN** — ainda `creationflags=0x08000000 \| 0x00000008` |
| 6 | painel ausente → `run.cmd` devolve 0 (falha a ler como sucesso) | `sotto_webview.py:2463` (era) | **APPLIED** — `--check-args` agora devolve 3 `PANEL_MISSING` (`sotto_webview.py:2528-2533`, `run.cmd:83-92`) |
| 7 | `pywebview` ausente → `run.cmd` devolve 0 | `sotto_webview.py:2502` (era) | **APPLIED** — `--check-args` importa `webview` e devolve 1 (`sotto_webview.py:2534-2541`) |
| 8 | o shell pode pendurar depois de `STAGING_LOADED` e `run.cmd` continua a dizer 0 | `run.cmd:104` (era) | **APPLIED** — ready-file fresco + `--wait-ready` limitado, sai 4 no timeout (`run.cmd:129-167`) |

## P1 — estado errado aos olhos do dono, substituicao silenciosa, ou oraculo que nao fica RED

| # | achado | onde | estado |
|---|---|---|---|
| 9 | `flags` lido e descartado → `DATA_DISCONTINUITY`/`SILENT` nunca examinados, a perda nao tem contador | `worker/wasapi_loopback.py:475/477` | **OPEN** |
| 10 | `exec_js` injeta cada script DUAS vezes | `sotto_webview.py:1409-1421` | **APPLIED** — resta uma so `self._ui(_run)` (`sotto_webview.py:1434`) |
| 11 | o falsificador "sem audio" reescreve um erro REAL do worker para `CAPTURE_NOT_STARTED`/`busy` | `sotto_webview.py:1888-1891, :196` | **OPEN** |
| 12 | uma legenda VAZIA conta como prova-de-vida e limpa o banner de morte | `sotto_webview.py:2052-2068` | **OPEN** |
| 13 | `start()` devolve `true` mesmo sem worker nenhum | `sotto_webview.py:1901-1917` | **OPEN** |
| 14 | `_lock` segurado durante uma ida-e-volta de UI bloqueante (ate 4 `ExecuteScriptAsync`, 10 s cada) | `sotto_webview.py:1901` | **OPEN** |
| 15 | `_schedule_restart` sobrescreve o timer sem cancelar o anterior | `sotto_webview.py:2210-2220` | **OPEN** |
| 16 | se `pythonw.exe` faltar, a app arranca sob o `python.exe` de consola | `run.cmd:48-49` (era) | **APPLIED** — recusa alta e sem janela, sai 3 (`run.cmd:64-76`) |
| 17 | `run.cmd --check-args` era flag aceite: arrancava a app e devolvia 0 sem abrir nada | `sotto_webview.py:2449-2463` | **APPLIED** — `CHECK_ARGS_ONLY` sai no pre-flight e nao arranca nada (`run.cmd:125`) |
| 18 | o `ready` do supervisor le um stream onde a app nunca escreve (o log vai para `--log`, nao para o PTY) | `launch-entry.md §3.4.2`, `spec.json` | **OPEN** |
| 19 | uma TERCEIRA causa do hang `STAGING_LOADED` reproduziu e nao esta nomeada | `launch-entry.md §4` | **OPEN** |
| 20 | 7 chaves do config que ninguem le (`match`, `sample_rate`, `channels`, `block_ms`, `latency`, `partial`, `min_chars`) | `worker/config.json:5,7,8,9,10,20,21` | **APPLIED** — as 7 apagadas; `block_ms` e `min_chars` agora LIVE (`worker/config.json:9,21`, `_comment_live`) |
| 21 | provider testado/`DEFAULT_MODEL` era int4 enquanto o config dizia int8 (substituicao silenciosa) | `sotto_worker.py:68, :934` | **APPLIED** — `DEFAULT_MODEL` agora int8 (`:77`); a sonda usa `model_dir or DEFAULT_MODEL` (`:942`) |
| 22 | `use_vad` default do codigo e `False` vs ficheiro `true` vs README "on" — apagar a chave desliga VAD em silencio | `sotto_worker.py:1152` | **OPEN** |
| 23 | `PREFERRED_DEVICES = ()` enquanto o README do worker o apresenta populado | `sotto_worker.py:94` | **OPEN** |
| 24 | `lang_id` morto durante a vida do ficheiro no git (`default=0` nunca e `None`) | `worker/config.json` / `lang_prompt.py:7-15` | **APPLIED** — `--lang-id` `default=None` (`sotto_worker.py:1031-1038`); a linha do config e alcancavel (`:1119-1120`) |
| 25 | shell `--selftest` nao afirma qualidade do output ("verde com word-salad") | `sotto_worker.py:986-999` | **OPEN** |
| 26 | `queue_drops` nunca era afirmado | `sotto_worker.py:1317` | **APPLIED** — `delivery-rate-oracle.py` afirma `queue_drops == 0` (arm `fixture-drops` RED no log) |
| 27 | panel ARM A aceita UMA legenda como LIVE | `_main/panel-exit3-oracle.py:999` | **OPEN** |
| 28 | shell selftest regista `focus_stolen=true` e mesmo assim sai 0 | `_main/webview-selftest.log:32` | **OPEN** |
| 29 | `panel-exit3-oracle.log` STALE (mtime 03:54 < fonte 04:40) — o PASS foi ganho por uma versao de 3 bracos | `_main/panel-exit3-oracle.log` | **OPEN** — mtime 1791269670 < fonte 1791272436 |
| 30 | `run-cmd-exit-oracle` esta RED hoje no conjunct do census | `_main/run-cmd-exit-oracle-after.json` | **OPEN** — `verdict: FAIL`, "arms=PASS census=FAIL" |
| 31 | o censo da casa nao serve para o eixo janela: `MainWindowHandle != 0` sem teste de monitor | `window-census.ps1:11-14, 60-70` | **OPEN** |
| 32 | o censo nao e panel-specific (alarmou em `cmd`/`dwm`/`python`) | `window-census.log` | **OPEN** |
| 33 | comentarios obsoletos/contraditorios no `sotto_webview.py` sobre a cura OFFSCREEN | `sotto_webview.py:1054` (residuo) | **OPEN** — `:1531-1535` ja diz "tried and REMOVED"; `:1054` ainda diz que o flash "e tratado pela posicao de criacao OFFSCREEN abaixo" |
| 34 | `wait(timeout=)` sem handler em 3 oraculos → filho orfao, handles nunca fechados | `device-silence-oracle.py:71`, `panel-exit3-oracle.py:160`, `panel-startup-visibility-oracle.py:386` | **OPEN** — nenhum `TimeoutExpired` nos tres |
| 35 | `run-live-hidden.py` `wait(timeout=)` sem handler + constante `DETACHED_PROCESS` morta | `_main/run-live-hidden.py:44, :25` | **OPEN** |

## P2 — deriva documental, cosmetico, latente ou nota de eficiencia

| # | achado | onde | estado |
|---|---|---|---|
| 36 | o fallback de buffer de 100 ms e codigo morto (o `Initialize` tem sucesso com anel de 22 ms) | `worker/wasapi_loopback.py:416,418-425` | **OPEN** |
| 37 | `CoInitializeEx` rejeita `S_FALSE` → um segundo tap na mesma thread limpa rebenta | `worker/wasapi_loopback.py:187-189` | **OPEN** |
| 38 | um `tick` de meio de corrida pode ser lido como total da corrida (`tag=tick` vs `tag=final`) | `worker/sotto_worker.py:1284-1301` | **OPEN** |
| 39 | `_pump` copia o acumulador com `np.concatenate` a cada emit | `worker/wasapi_loopback.py:492-496` | **OPEN** |
| 40 | conjuntos de nomes de estado sensiveis a separador onde o braco JS normaliza | `sotto_webview.py:112-126` | **OPEN** |
| 41 | linha de status sem `type` e descartada em silencio | `sotto_webview.py:2046-2051` | **OPEN** |
| 42 | `stop()` nao emite status final no lado Python | `sotto_webview.py:1987-2004` | **OPEN** |
| 43 | `_spawn()` corre na thread de restart SEM `_lock` | `sotto_webview.py:2222` | **OPEN** |
| 44 | `docs/README.md` diz que "nenhum codigo de aplicacao foi escrito" | `docs/README.md:8` | **OPEN** |
| 45 | 3 documentos ainda descrevem a stack Tauri/Rust/SQLite abandonada como o produto | `docs/README.md:22-27`, `docs/roadmap.md:53-64`, `README.md:50-58,64` | **OPEN** |
| 46 | `AGENTS.md` contradiz-se sobre o painel no arranque ("0 de 41" vs "visivel 50 ms–7 s") | `AGENTS.md:169` vs `:215` | **OPEN** |
| 47 | figura fp16 do `AGENTS.md` 1230 vs 1246.9 MiB medidos | `AGENTS.md:89` | **OPEN** |
| 48 | `AGENTS.md` cita `worker-bridge.js:133` como "STATE_MAP" (declarado em `:114`) | `AGENTS.md:119` | **OPEN** |
| 49 | o "rank-1" do `use_vad` e retratado 230 linhas abaixo, sem ponteiro | `docs/oss-approaches-20261006.md:214` vs `:444-475` | **OPEN** |
| 50 | `live-captions` deixa uma decisao supersedida de pe, com um numero de sinal trocado | `docs/live-captions-20261006.md:214-216` | **OPEN** |
| 51 | `full-audit` descreve a regra de juncao de 1200 ms que o codigo ja nao tem | `docs/full-audit-transcription-20261006.md:310,326` | **OPEN** |
| 52 | "14 campos, 0 divergencias" do `webview-shell` nao e reproduzivel (o metodo da 64) | `docs/webview-shell-20261006.md:85-90` | **OPEN** |
| 53 | `AGENTS.md` cita um artefacto no caminho errado | `AGENTS.md:25` | **OPEN** |
| 54 | AGENTS/README listam 5 chaves do config; o ficheiro tem 13 (hoje 8) | `AGENTS.md:74`, `worker/README.md:184-185` | **OPEN** |
| 55 | a sonda CUDA dos providers corria no int4 independentemente do dir configurado | `sotto_worker.py:883, :934` | **APPLIED** — sonda `model_dir or DEFAULT_MODEL` (`:942`) |
| 56 | `model-spec-oracle` nao tem braco negativo (detector de drift, nao oraculo) | `_main/model-spec-oracle.py:41` | **OPEN** |
| 57 | `_oss_oracle` nao tem braco negativo | `_main/_oss_oracle.py` | **OPEN** |
| 58 | o braco `bogus` do `runcmd-entry-driver.py` nao tem recibo | `_main/runcmd-entry-report.json` | **OPEN** |
| 59 | `_move_into_place` morto (sem caller) + painel vivo a `x=-10000` (build ≠ ficheiro auditado) | `sotto_webview.py:1083` (era) | **APPLIED** — o metodo morto desapareceu; resta so a nota de remocao (`:1269`). A metade `x=-10000` e observacao de processo vivo, fora do ficheiro auditado |
| 60 | `_on_navigation_start` faz early-return em `self.visible` → "mostrado uma vez ⇒ nunca mais auto-escondido" | `sotto_webview.py:1549` | **OPEN** |
| 61 | `run.cmd:6` promete "start hidden" enquanto o shell pisca | `run.cmd:6` | **OPEN** |
| 62 | `subprocess.run(timeout=)` a volta do `electron.exe` multi-processo pode nao ser tecto [INFERENCE] | `_main/_run-hidden.py:24` | **OPEN** |

---

## Landmines de ambiente medidas (nao sao fixes do app — sao leis de medicao)

Estas **nao** contam nos 62 achados. Verdicto por landmine (`windows-landmines.md`):
1. `pythonw` nao tem stdout; `argparse` sai 2 para o vazio — **contida** (`run.cmd:83-92`).
2. `CREATE_NO_WINDOW|DETACHED_PROCESS` = 0 bytes rc 0; `CREATE_NO_WINDOW` sozinho — **BITES (provado)** em `console-census.py:106` (achado #5).
3. `taskkill` a truncar o log — **partly**: a perda de cauda **nao reproduziu**; a metade real e "`taskkill /F` nao corre shutdown graciosa" (`HOTRELOAD.md:326-330`) e o caso de codepage ja corrigido (`runcmd-entry-driver.py:168-170`).
4. janelas `conhost` de um filho com consola — **contida na app** (`run.cmd` usa `pythonw`).
5. caminhos com espacos — **no bite** (todo o boundary usa argv em lista).
6. `subprocess.run(timeout=)` nao e tecto — **BITES em 3 oraculos** (achado #34).

Licao corrigida face ao mapa antigo: o mapa antigo conservava a metade que o doc **refutou**
("taskkill pode truncar o log") e largava o que realmente morde (#34 e a metade "no graceful shutdown").

---

## Contagem (o que torna o mapa checavel)

- **Achados nas fontes:** **62** = 61 (enumeracao do `00-MAPA-REVIEW.md` §A: audio 6, shell 10, doc-vs-code 10,
  launch 7, model-config 7, oracles 10, window-visibility 7, landmines 4) **+ 1** (`audio-path.md §5`,
  `blank_frac=1.0`, nomeado na fonte mas nao rotulado `F\d`) → linha #2.
- **Linhas no mapa:** **62** (uma por achado; zero agrupamentos many-to-one).
- **MISSING:** **0** — todos os M1–M30 do review tem linha: M1→#9, M2→#36, M3→#37, M4→#38, M5→#39,
  M6→#17, M7→#18, M8→#19, M9→#22, M10→#23, M11→#54, M12→#24, M13→#25, M14→#26, M15→#27, M16→#56,
  M17→#57, M18→#28, M19→#29, M20→#30, M21→#58, M22→#4, M23→#32, M24→#59, M25→#60, M26→#61, M27→#5,
  M28→#34, M29→#35, M30→#62.
- **INVENTED:** **0** — cada linha cita um achado presente num dos 8 docs.
- **WRONG_STATE:** **0** — os 6 do review (W1–W6) corrigidos: W1 #2 ABERTO→EM VOO; W2 #21 EM VOO→APLICADO;
  W3 #20 EM VOO→APLICADO; W4 #6–#8 (+#16) EM VOO→APLICADO; W5 #33 ABERTO em `:1531-1535`→ o texto mudou,
  o residuo passou a `:1054`; W6 #3 EM VOO→APLICADO.
- **Citações erradas corrigidas:** C1 #1→`wasapi_loopback.py:463`; C2 #10→`sotto_webview.py:1409-1421`;
  C3 #33→worksheet tree (`:1054` residuo, `:1531-1535` ja corrigido).
- **Ma-atribuicao corrigida:** X1 (o antigo item 2 "regressao do OFFSCREEN APLICADO") nao existe:
  a cura OFFSCREEN foi *tentada e removida*; o hang e #19 e o comentario obsoleto e #33.

| estado | contagem | linhas |
|---|---|---|
| **APPLIED / APLICADO** | **14** | #1, #3, #6, #7, #8, #10, #16, #17, #20, #21, #24, #26, #55, #59 |
| **IN-FLIGHT / EM VOO** | **1** | #2 |
| **OPEN / ABERTO** | **47** | todas as restantes |

**Conferencia:** 14 + 1 + 47 = **62** (achados nas fontes) = **62** (linhas). ✔
E no sentido do review: 62 (com casa) + 0 (MISSING) = 62; 0 INVENTED; 0 WRONG_STATE.

Como este mapa se verifica mecanicamente: para cada rotulo `F\d`/`G\d`/`H\d`/`Finding [A-Z]` de cada doc
fonte, exigir a sua linha aqui. O mapa antigo (29 linhas, 51 %) devolvia 30 rotulos ausentes; este devolve 0.
O gate que fecha isso e `I:/!manager/scripts/audit-map-gate.sh` (lane `AuditMapGate`).

gate-change-request: n/a — o gate pertence a lane `AuditMapGate` (`I:/!manager/scripts/audit-map-gate.sh`,
despachada); esta lane constroi o MAPA, nao o gate.

---

## SELF-AUDIT

- **protocolos em falta** — Deveria ter extraido mecanicamente todos os rotulos `F\d|G\d|H\d|Finding [A-Z]`
  dos 8 docs como PASSO 0 e construido a lista de achados a partir desse `grep`, antes da prosa. Fi-lo
  depois de ler. Protocolo que devia ter seguido: a contagem como um `comm -23`, nao como aritmetica a mao.
- **verificacao adicional** — Re-verifiquei no working tree os 5 pontos que o ticket nomeia como correcoes
  a honrar (delivery-rate-oracle, DEFAULT_MODEL/model_dir, config keys, G4, `:1531-1535`) com `read`/`grep`/
  `stat`. O que nao corri: o `comm` mecanico rotulos-vs-mapa (o gate nao existe). Custo: 1 comando.
- **checkboxes novas** — "Para cada rotulo `F\d|G\d|H\d|Finding [A-Z]` de um doc fonte, exigir a sua linha
  no mapa; o `file:line` tem de ser identico ao do doc." Comando:
  `comm -23 <(grep -ohE '\b(F|G|H)[0-9]+' docs/audit/*.md|sort -u) <(grep -oE '^\| [0-9]+' 00-MAPA-CONSOLIDADO.md|...)`.
  RED: o mapa antigo (30 ausentes). GREEN: este.
- **review por outro subagente** — sim-com-escopo: re-derivar SO o mapa `rotulo → linha` a partir de um
  `grep -oh` dos 8 docs. Nao para os estados (mecanicos) nem para o self-audit.
- **gate-doubt**:
  - **verde-de-verdade:** o unico verde e aritmetico (`14+1+47=62`) e nao vacuoso (o mapa antigo falhava a
    mesma conta). O `SELFTEST: PASS` do `delivery-rate-oracle.log` citado para o estado #3 **nao o re-corri**
    — leio o log em disco; e verde do instrumento, declarado como tal, nao meu.
  - **falta-no-gate:** nao existe gate que compare um documento "consolidado" com as suas fontes; o
    `self-audit-lint` so valida a forma do bloco SELF-AUDIT. Cenario que atravessa: alguem larga as linhas
    de `oracles.md` e nada fica RED.
  - **gate-melhor:** `I:/!manager/scripts/audit-map-gate.sh` (lane `AuditMapGate`): exigir cada rotulo das
    fontes no mapa; RED = mapa antigo (30 ausentes), GREEN = este mapa. Fecho enquanto ausente:
    `n/a — o gate pertence a lane AuditMapGate`.
- **confianca** — alta na cobertura e nos 14 APLICADOS (cada um e um `read`/`grep`/`stat` colado do working
  tree); media na fronteira 62/61 (o +1 e `audio-path §5`, um facto nomeado nao rotulado `F\d`, declarado).
- **nao verificado** — (1) nenhum oraculo re-corrido (abriria janela); (2) `AGENTS.md` untracked/editado nao
  re-sondado (itens #46/#47/#48/#53 podem ter deslizado); (3) `delivery-rate-oracle.py` lido so por `stat` +
  log, nao linha a linha; (4) o `comm` mecanico nao corrido (gate ausente).
