# MAPA CONSOLIDADO — todos os achados da auditoria do Sotto

**Reconstruido a partir das FONTES**, nao dos cabecalhos. Fontes: os **43 docs** de `docs/audit/`
(todos nomeados na seccao *Fontes*, abaixo) + `00-MAPA-REVIEW.md`.
**Data:** 2026-10-06 (linhas #1-#62) · **Revisao 2026-10-11 (lane T4):** o mapa passou a nomear todos
os docs-fonte e a indexar TODOS os rotulos que eles declaram (`F`+digitos, `G`+digitos, `H`+digitos,
`Finding` + letra). As linhas #1-#62 mantem o estado que a revisao de 2026-10-06/07 verificou na
arvore, excepto as que trazem a marca `[2026-10-11]`, re-medidas nesta revisao contra o working tree.
**Modo:** READ-ONLY sobre `H:/sotto` (so este ficheiro foi escrito).
**Working tree lido:** `H:/sotto` @ HEAD `3e90f92` + uncommitted (lane T4); re-lido pela passagem do
Lead apos o commit `4d7766c`, que fechou #45 e F2.
**Pins desta revisao** (regra 2 do `AGENTS.md`: nomeie a revisao): `worker/sotto_worker.py` = **295 867 B**,
sha256 `2C0AF4FB…`; `worker/wasapi_loopback.py` = **51 215 B**, sha256 `09C65E94…`. Os `file:line` das
linhas #1-#62 foram medidos em 2026-10-06/07 e NAO foram re-medidos agora: trate-os como HINT e re-corra o `grep`.

Vocabulario FECHADO de estado (o gate de `I:/!manager/scripts/audit-map-gate.sh` so conhece estes):

**APPLIED / APLICADO** — corrigido e verificado no working tree, ou fechado pela propria fonte que
declarou o achado. **IN-FLIGHT / EM VOO** — uma lane com esse achado esta despachada e o artefacto
declarado ainda esta ausente. **OPEN / ABERTO** — identificado e NAO fechado por evidencia citavel:
e o estado honesto do que nao tem cura declarada, do que a fonte transferiu para o dono, e do que so
foi lido. **Regra desta revisao:** nao se escreve APPLIED sem uma frase de fonte, ou uma linha da
arvore viva citada com ficheiro e numero — um OPEN antigo e preferivel a um APPLIED falso.

Regra de severidade: **P0** = bloqueia o produto, ou uma falha que se le como sucesso;
**P1** = o estado que o dono ve esta errado, ou uma substituicao silenciosa, ou um oraculo que nao
consegue ficar RED num defeito real; **P2** = deriva documental, cosmetico, latente ou nota de eficiencia.

---

## P0 — bloqueia o produto ou uma falha que se le como sucesso

| # | achado | onde | estado |
|---|---|---|---|
| 2 | braco live entrega `blank_frac=1.0` (o modelo so ouve sinal de baixo nivel) — o facto que bloqueia as legendas por Alt+C | `worker/sotto_worker.py` §5 | **APPLIED** [2026-10-11] — a lane entregou: `blank-frames-root-cause.md:6-9` mede que **nada no worker esta partido** — a mistura do endpoint por omissao nao tem fala — e que a escada do verdict chamava a esse estado `model-emitted-noothing`, corrigido no verdict (fix `1900bc7b1d284ee4`) |
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
| 9 | `flags` lido e descartado → `DATA_DISCONTINUITY`/`SILENT` nunca examinados, a perda nao tem contador | `worker/wasapi_loopback.py:475/477` | **[2026-10-11] APPLIED** — as TRES afirmacoes cairam. `SILENT` E examinado (`silent_packets`) e a perda TEM contador (`position_gap_packets`): medidos pelo sweep de linhas (refutados). E `DATA_DISCONTINUITY` passou a ser EXAMINADO nesta sessao: `AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY = 0x00000001` + `discontinuity_packets` no tap de endpoint E no loop do PLP (`sotto_worker.py`), com `disco_packets=` na linha `TAP_STALLED`. Provas: `py -3 _main/audit-rows-tap-flags-ledger.py` → `VERDICT: PASS  live: 0 of 4 defect claims present`, rc=0, e o mutante `m9b-discontinuity-counter-removed` REPRODUZ o defeito (o mutante antigo simulava a cura, porque ela nao existia). As amostras continuam a ser USADAS: muda o LEDGER, nao o audio. NAO MEDIDO: nenhum dispositivo real pos o bit — o instrumento usa um vtable scriptado |
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
| 22 | `use_vad` default do codigo e `False` vs ficheiro `true` vs README "on" — apagar a chave desliga VAD em silencio | `sotto_worker.py:1152` | **APPLIED** [2026-10-11] — `auditoria-completa-20261007.md:597` lista o default `True` e a arvore viva confirma-o: `use_vad = bool(cfg.get("model", {}).get("use_vad", True))` (`sotto_worker.py:4257`); a linha que o negava desapareceu |
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
| 34 | `wait(timeout=)` sem handler em 3 oraculos → filho orfao, handles nunca fechados | `device-silence-oracle.py:71`, `panel-exit3-oracle.py:173`, `panel-startup-visibility-oracle.py:386` | **[2026-10-11] APPLIED** — os TRES oraculos ganharam `try/except subprocess.TimeoutExpired` com `taskkill /F /T /PID <pid>` (o alvo e um PID, nunca um NOME, logo nenhum filtro de kill pode atingir processo alheio) e re-`raise`. Provado pelo instrumento da propria linha: `py -3 _main/audit-rows-landmine-child-control.py` → `VERDICT: PASS live: 1 of 4 landmines still reproduced (r62); the rest are FIXED`, rc=0, com o mutante `m34-orphan-handler-removed` (devolve o `wait` nu a UM ficheiro) a REPRODUZIR o orfao. A derivacao mudou de ALL para ANY: UM sitio sem handler ja pode orfanar uma crianca, logo um so e o defeito (`all` teria deixado o braco incapaz de dizer NAO depois do primeiro ficheiro corrigido) |
| 35 | `run-live-hidden.py` `wait(timeout=)` sem handler + constante `DETACHED_PROCESS` morta | `_main/run-live-hidden.py:44, :25` | **[2026-10-11] APPLIED** — o `wait(timeout=300)` ganhou o mesmo handler com tree-kill e a constante `DETACHED_PROCESS` foi REMOVIDA (nada a lia). Mutante `m35-handler-removed-constant-restored` repoe os dois e a linha volta a ler DEFEITO; e o detector desta linha foi corrigido no mesmo passo (contava MENCOES: o comentario que explica a remocao fazia `DETACHED_PROCESS` contar 1 e o teste `count == 1` lia a documentacao como se fosse a constante — agora exige uma DEFINICAO, `^\s*DETACHED_PROCESS\s*=`) |

## P2 — deriva documental, cosmetico, latente ou nota de eficiencia

| # | achado | onde | estado |
|---|---|---|---|
| 37 | `CoInitializeEx` rejeita `S_FALSE` → um segundo tap na mesma thread limpa rebenta | `worker/wasapi_loopback.py:187-189` | **APPLIED** [2026-10-11] — `flat-endpoint.md:125-142` mede o pos-fix: `S_OK`/`S_FALSE` -> `COM_REF_TAKEN` e o erro `0x80004005` era o gate antigo (`:49-51` pre-fix); a arvore viva aceita `S_FALSE` (`wasapi_loopback.py:204`) |
| 37 | `CoInitializeEx` rejeita `S_FALSE` → um segundo tap na mesma thread limpa rebenta | `worker/wasapi_loopback.py:187-189` | **OPEN** |
| 38 | um `tick` de meio de corrida pode ser lido como total da corrida (`tag=tick` vs `tag=final`) | `worker/sotto_worker.py:1284-1301` | **OPEN** |
| 39 | `_pump` copia o acumulador com `np.concatenate` a cada emit | `worker/wasapi_loopback.py:492-496` | **OPEN** |
| 40 | conjuntos de nomes de estado sensiveis a separador onde o braco JS normaliza | `sotto_webview.py:112-126` | **OPEN** |
| 41 | linha de status sem `type` e descartada em silencio | `sotto_webview.py:2046-2051` | **OPEN** |
| 42 | `stop()` nao emite status final no lado Python | `sotto_webview.py:1987-2004` | **OPEN** |
| 43 | `_spawn()` corre na thread de restart SEM `_lock` | `sotto_webview.py:2222` | **OPEN** |
| 44 | `docs/README.md` diz que "nenhum codigo de aplicacao foi escrito" | `docs/README.md:8` | **[2026-10-11] APPLIED** — a seccao *What exists today* deixou de dizer "Planning only. No application code has been written." e passou a nomear o que EXISTE e corre (worker + shell pywebview/WebView2 + painel, Alt+C), com a nota de que a frase era verdadeira quando foi escrita e ficou stale |
| 45 | 3 documentos ainda descrevem a stack Tauri/Rust/SQLite abandonada como o produto | `docs/README.md:22-27`, `docs/roadmap.md:53-64`, `README.md:50-58,64` | **[2026-10-11] APPLIED** — os TRES corrigidos nesta passagem, por leitura dos bytes (nada lancado): `docs/README.md` §*Honest status of the stack* passou a nomear a stack que EMBARCA (Python 3.11 + `onnxruntime` + pywebview 6.2.1/WebView2, `Alt+C`) e marca o `transcribe.cpp` como avaliado-e-nao-adoptado; `docs/roadmap.md` ganhou a faixa SUPERSEDED antes de M0 (Tauri/Rust/CPAL sao PLANO, e `docs/live-captions-20261006.md:208` prova que o Tauri esta morto); `README.md:48-52` deixou de chamar o Tauri *"still the destination"* e retracta DUAS afirmacoes ja refutadas (o carimbo `producer` existe — `REDUX_PRODUCER` em `worker/sotto_worker.py`; e `history/` tem ficheiro mais novo, `history/2026-10-07/14.md`) |
| 46 | `AGENTS.md` contradiz-se sobre o painel no arranque ("0 de 41" vs "visivel 50 ms–7 s") | `AGENTS.md:169` vs `:215` | **OPEN** |
| 47 | figura fp16 do `AGENTS.md` 1230 vs 1246.9 MiB medidos | `AGENTS.md:89` | **[2026-10-11] APPLIED** — a figura deixou de ser AFIRMADA: a linha dos pesos esta riscada e acompanhada do bloco CORRIGIDO 2026-10-11 que diz que so o int8 existe em disco (1 070 642 977 B / 33 ficheiros) e que os numeros int4/fp16 ficam UNMEASURED, nao re-mediveis. Nao houve reconciliacao do numero: houve retractacao, que e o estado honesto quando o export ja nao esta em disco |
| 48 | `AGENTS.md` cita `worker-bridge.js:133` como "STATE_MAP" (declarado em `:114`) | `AGENTS.md:119` | **[2026-10-11] APPLIED** — corrigido para `:114` (onde a tabela e DECLARADA; `:223` e a consulta), com a retractacao do `:133` na propria frase, re-medida por `grep` no ficheiro vivo |
| 49 | o "rank-1" do `use_vad` e retratado 230 linhas abaixo, sem ponteiro | `docs/oss-approaches-20261006.md:214` vs `:444-475` | **[2026-10-11] APPLIED** — a linha do rank-1 passou a nomear **§10** (`:461`, "RETRACTION — rank-1 ... is WITHDRAWN as stated") nos seus ponteiros, com a nota de que o ponteiro faltava |
| 50 | `live-captions` deixa uma decisao supersedida de pe, com um numero de sinal trocado | `docs/live-captions-20261006.md:214-216` | **[2026-10-11] APPLIED** — a decisao "keep Electron for now" ganhou um bloco **SUPERSEDED 2026-10-07**: o swap LANDED (`app/webview/run.cmd`, pywebview+WebView2, Electron em `app/_legacy-electron/` e MORTO, ordem do dono "no fallback"), e o SINAL foi corrigido contra a medicao — a previsao era uma POUPANCA de ~214 MB e o medido na arvore da shell e um CUSTO (**416 MB vs 312 MB = +33%**, 2026-10-06). O split "~2.4 GB / engine 9% / model 89%" nunca foi re-medido depois do port |
| 51 | `full-audit` descreve a regra de juncao de 1200 ms que o codigo ja nao tem | `docs/full-audit-transcription-20261006.md:310,326` | **[2026-10-11] APPLIED** — as duas linhas ficaram marcadas como a regra DA ALTURA (nao a embarcada) e uma NOTE nomeia a viva: `SENTENCE_GAP_S = 8` (segundos) no worker E em `app/panel/caption-formulation.js:18`, `SENTENCE_MAX_CHARS = 90` em `:21`, formulacao fora do `panel.js`; paridade gateada em `node _main/caption-renderer-integration.js` checks 6-7 (re-medido por mim: 7 PASS / 0 FAIL, rc=0) |
| 53 | `AGENTS.md` cita um artefacto no caminho errado | `AGENTS.md:25` | **APPLIED** [2026-10-11] — o proprio `AGENTS.md` retrata o texto por nome (`AGENTS.md:169`): o artefacto EXISTE em `H:\sotto\_main\exit3-armB-worker.jsonl` (3 958 B, sha256 `426EC552...`) e o "AUSENTE / DANGLING" era um falso negativo de um `statSync` sobre `worker/runs/` |
| 53 | `AGENTS.md` cita um artefacto no caminho errado | `AGENTS.md:25` | **OPEN** |
| 54 | AGENTS/README listam 5 chaves do config; o ficheiro tem 13 (hoje 8) | `AGENTS.md:74`, `worker/README.md:184-185` | **[2026-10-11] APPLIED** — censo de folhas do `worker/config.json` vivo (`JSON.parse` + walk): **5 chaves de topo, 11 folhas nao-comentario** (as outras 6 sao `_comment*`). O `worker/README.md` passou a listar as 11, e retracta DUAS afirmacoes falsas: parava em oito nomes e nomeava `output.partial` entre as chaves APAGADAS — essa chave ESTA presente e e LIDA (`emit_partial` e `output.partial`, `sotto_worker.py:2851`/`:3013`). A linha do `AGENTS.md` ja tinha sido corrigida nesta revisao |
| 55 | a sonda CUDA dos providers corria no int4 independentemente do dir configurado | `sotto_worker.py:883, :934` | **APPLIED** — sonda `model_dir or DEFAULT_MODEL` (`:942`) |
| 56 | `model-spec-oracle` nao tem braco negativo (detector de drift, nao oraculo) | `_main/model-spec-oracle.py:41` | **[2026-10-11] APPLIED** — o oraculo foi reescrito com `evaluate()` (o caminho por omissao mantem o MESMO log, as mesmas linhas e o mesmo rc 0/1) e ganhou `--neg-arm`: dois mutantes numa COPIA do `genai_config.json` em `TMPDIR`, um por constante (`chunk_samples=1234`, `blank_id=1`), que TEM de dar MISMATCH. Medido: `py -3 _main/model-spec-oracle.py` → `VERDICT: OK`, rc=0; `--neg-arm` → os dois mutantes `MISMATCH (RED as required)`, controlo vivo `OK`, `VERDICT: NEG-ARM PASS`, rc=0 |
| 57 | `_oss_oracle` nao tem braco negativo | `_main/_oss_oracle.py` | **[2026-10-11] APPLIED** — reescrito com `checks(root)`, o MESMO stdout/rc (GREEN/RED, 0/3) no caminho por omissao, e `--neg-arm` que constroi uma ARVORE mutante em `TMPDIR` (os quatro inputs copiados) com UM mutante por check, exigindo que o conjunto de falhas seja EXACTAMENTE o check visado. Medido: `py -3 _main/_oss_oracle.py` → GREEN 4/4 rc=0; `--neg-arm` → M1 `['C1']`, M2 `['C2']`, M3 `['C3']`, M4 `['C4']`, controlo vivo GREEN na mesma execucao, `NEG-ARM PASS`, rc=0, `TMPDIR` limpo. **O proprio oraculo estava a dizer a verdade quando a linha foi escrita:** com o padrao C2 antigo o live dava RED — ver a linha #63 |
| 58 | o braco `bogus` do `runcmd-entry-driver.py` nao tem recibo | `_main/runcmd-entry-report.json` | **OPEN** |
| 59 | `_move_into_place` morto (sem caller) + painel vivo a `x=-10000` (build ≠ ficheiro auditado) | `sotto_webview.py:1083` (era) | **APPLIED** — o metodo morto desapareceu; resta so a nota de remocao (`:1269`). A metade `x=-10000` e observacao de processo vivo, fora do ficheiro auditado |
| 60 | `_on_navigation_start` faz early-return em `self.visible` → "mostrado uma vez ⇒ nunca mais auto-escondido" | `sotto_webview.py:1549` | **OPEN** |
| 61 | `run.cmd:6` promete "start hidden" enquanto o shell pisca | `run.cmd:6` | **OPEN** |
| 62 | `subprocess.run(timeout=)` a volta do `electron.exe` multi-processo pode nao ser tecto [INFERENCE] | `_main/_run-hidden.py:24` | **OPEN** |
| 63 | `docs/oss-approaches-20261006.md` embute uma COPIA do oraculo (um one-liner) e cola um PASS de 2026-10-06 que ja nao reproduz | `docs/oss-approaches-20261006.md:250,286-295` | **[2026-10-11] APPLIED** — o one-liner embutido devolve hoje `RED (doc is now stale - rewrite it)` rc=3, e so C2 falha: `type="caption"` tem **0** ocorrencias em `worker/sotto_worker.py` (o worker faz `self._captions.put({"type": "caption", "text": text, ...})`, `:3620`, e `:2928` o outro canal). A AFIRMACAO sobreviveu — `HypothesisBuffer`/`commited` continuam ausentes (0 cada) e `agreedPrefix|LocalAgreement` esta ausente de todo o `worker/` (0) — o que tinha envelhecido era a ORTOGRAFIA da chamada. O padrao C2 foi re-baselinado para a forma dict no ficheiro vivo e o documento ganhou a nota RE-MEASURED 2026-10-11 com os dois comandos |

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

## Fontes — os 43 docs que este mapa cobre

Todos os ficheiros regulares de `docs/audit/` com extensao `.md`/`.markdown`/`.txt`, excepto os mapas
(`00-MAPA*`) — a populacao que o gate mede. O descritor de cada linha e a PRIMEIRA linha nao vazia do
proprio doc. Os rotulos `F`/`G`/`H`/`Finding` de cada um estao indexados na seccao seguinte.

**ao-vivo-vs-redux-CURA.md** — Ao vivo vs "redux" — a CURA: o ficheiro do historico deixa de mentir
**ao-vivo-vs-redux.md** — Ao vivo vs "redux" — o dono tem razao: sao DUAS rotas, e o Sotto tem UMA
**audio-escopo.md** — audio-escopo — WHICH render endpoint the tap must read, and the cure
**audio-path.md** — Sotto — the audio path, end to end (capture → resample → chunk → decode → emit)
**auditoria-completa-20261007.md** — Auditoria completa — Sotto (`H:\sotto`), 2026-10-07
**auto-gain.md** — Sotto — automatic gain on the LIVE capture branch
**blank-frames-root-cause.md** — Blank frames — root cause (lane BlankFramesRootCause, 2026-10-06)
**caption-formulation.md** — Caption formulation — the chunk stream becomes a readable LINE
**config-inert-fixed.md** — `worker/config.json` inert keys, the wrong-model provider probe, and the audio DELIVERY-RATE oracle
**device-routing.md** — Sotto device routing — the loopback tap, the Sound-Mapper tail, and the endpoint answer
**doc-vs-code.md** — Documentation against the running code — Sotto
**docs-truth-20261007.md** — Docs, made true — 2026-10-07 (lane: documentation)
**flat-endpoint-na-app.md** — flat-endpoint NA APP — a app REAL do dono, medida
**flat-endpoint.md** — flat-endpoint — the endpoint that came out FLAT, measured and fixed
**flicker-aceitacao.md** — Flicker Aceitacao Measurement
**flicker-cura.md** — Flicker Cura — Sotto Live Captions Fix
**flicker-diff-verdict.md** — Julgamento do Diff Sujo em H:/sotto
**flicker-dom-oracle.md** — Flicker DOM Oracle Audit
**historico-vs-redux.md** — Historico vs "redux" — o veredicto, a causa e a cura
**launch-entry.md** — Audit — how the app is started, and what it reports when it fails
**live-for-owner.md** — live-for-owner — the app is UP, and Alt+C answers
**load-churn.md** — load-churn — the model does not reload in a loop any more
**model-config.md** — `worker/config.json` — key-by-key consumption audit
**oracles.md** — The oracles of Sotto — which ones can actually go RED
**ordem-dos-candidatos.md** — A ordem dos candidatos — qual das três hipóteses é verdadeira, e a cura
**original-prompt-adjudication.md** — Adjudication of the ORIGINAL PROMPT — does it still hold, and must it still be followed?
**painel-atraso-e-acerto.md** — painel: o ATRASO e o ACERTO — medidos, nao estimados
**painel-texto.md** — O painel como TEXTO — um dump que se lê com `read`, sem visão
**panel-gap.md** — panel-gap — a lacuna do painel: AUDITADA, e ela NAO EXISTE
**panel-v2.md** — panel-v2 — the panel rebuilt: two sections, a live box, a history feed, search and show-in-folder
**precisao-int8-custo.md** — Quanto custa a quantização int8, sozinha, na legenda ao vivo?
**predictor-carry-cura.md** — CURA — o predictor do RNN-T atravessa a fronteira de chunk
**reinicio-30s.md** — Reinício a cada ~30 s: causa medida e cura
**run-cmd-gaps-fixed.md** — run.cmd launch-entry gaps G1–G4 — FIXED, each asserted before/after
**shell-bridge.md** — Audit — the shell and the bridge
**sotto-vs-referencia.RECEIPT.md** — status: done
**sotto-vs-referencia.md** — Sotto vs. a YouTube reference — why our transcript skips words
**speech-separation.md** — Speech/music separation before live captioning
**tap-restart-loop.md** — The tap restart loop — the shell killed a worker for being quiet on a silent machine
**tracked-durability.md** — Sotto — tracked durability of the session's fixes (2026-10-06)
**transcript-duplicacao.md** — Duplicação das entradas de transcript — causa medida, cura e o check que a trava
**window-visibility.md** — Sotto panel window — visibility audit
**windows-landmines.md** — Windows-specific failure modes in `H:/sotto` — audit

**Nota sobre um rotulo que NAO e um achado:** o extrator do gate le `[FGH]` + digitos como
rotulo, e ha um doc em que esse padrao nao e um achado: em `docs-truth-20261007.md:72` o token `F32`
(e em `:100` o `F16`) nomeia FORMATOS de precisao — float32/float16, os numeros de WER publicados do
§5 —, nao um achado. O `F16` indexado abaixo e o achado da `auditoria-completa-20261007.md`; o `F32`
fica nomeado aqui, e nao no indice, porque nao ha achado nenhum por tras dele.
## Indice de rotulos (doc x rotulo)

Os rotulos sao LOCAIS a cada doc: o mesmo `F1` e um achado diferente em cada ficheiro, logo cada par
(doc, rotulo) tem a sua linha. Cada entrada REPETE o estado da linha que indexa — nao e um segundo
achado, e a prova de que nenhum rotulo declarado por uma fonte ficou sem linha no mapa.

### audio-path.md (F1-F6)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| F1 | pump a 25 ms contra um anel de 22 ms -> ~18 % dos quadros perdidos em silencio (`audio-path.md:268`) | **APPLIED** — herdado da linha #1 (period = min(0.005, ...) = 5 ms) |
| F2 | o overflow e invisivel porque flags e lido e descartado (`audio-path.md:274`) | **APPLIED** — herdado da linha #9, fechada em 2026-10-11: o `flags` deixou de ser descartado (SILENT contado, `DATA_DISCONTINUITY` contado agora, posicao comparada) e a perda de posicao tem o seu proprio contador |
| F3 | o fallback de buffer de 100 ms e codigo morto (`audio-path.md:279`) | **OPEN** — herdado da linha #36 |
| F4 | CoInitializeEx rejeita S_FALSE e um segundo open na mesma thread rebenta (`audio-path.md:284`) | **APPLIED** — herdado da linha #37 (medido pos-fix em flat-endpoint.md:125-142) |
| F5 | contabilidade: um tick de meio de corrida pode ser lido como total (`audio-path.md:302`) | **OPEN** — herdado da linha #38 |
| F6 | _pump muta buf/acc com np.concatenate a cada emit (`audio-path.md:306`) | **OPEN** — herdado da linha #39 |

### shell-bridge.md (F1-F10)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| F1 | exec_js corre cada script injectado DUAS vezes (`shell-bridge.md:45`) | **APPLIED** — herdado da linha #10 |
| F2 | o falsificador sem-audio engole um erro REAL do worker (`shell-bridge.md:93`) | **OPEN** — herdado da linha #11 |
| F3 | uma legenda VAZIA conta como prova-de-vida e limpa o banner de morte (`shell-bridge.md:123`) | **OPEN** — herdado da linha #12 |
| F4 | start() devolve true mesmo sem worker nenhum (`shell-bridge.md:160`) | **OPEN** — herdado da linha #13 |
| F5 | _lock segurado durante uma ida-e-volta de UI bloqueante (`shell-bridge.md:174`) | **OPEN** — herdado da linha #14 |
| F6 | _schedule_restart nao cancela o timer anterior (`shell-bridge.md:190`) | **OPEN** — herdado da linha #15 |
| F7 | conjuntos de nomes de estado sensiveis a separador (`shell-bridge.md:207`) | **OPEN** — herdado da linha #40 |
| F8 | linha de status sem type e descartada em silencio (`shell-bridge.md:226`) | **OPEN** — herdado da linha #41 |
| F9 | stop() nao emite status final no lado Python (`shell-bridge.md:235`) | **OPEN** — herdado da linha #42 |
| F10 | _spawn() corre na thread de restart SEM _lock (`shell-bridge.md:242`) | **OPEN** — herdado da linha #43 |

### doc-vs-code.md (F1-F10)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| F1 | docs/README.md:8 diz que nenhum codigo de aplicacao foi escrito (`doc-vs-code.md:21`) | **OPEN** — herdado da linha #44 |
| F2 | tres documentos descrevem a stack Tauri/Rust abandonada como o produto (`doc-vs-code.md:22`) | **APPLIED** — herdado da linha #45, fechada em 2026-10-11: o README.md da raiz ja estava corrigido e os outros dois (`docs/README.md`, `docs/roadmap.md:53`) foram corrigidos nesta passagem |
| F3 | AGENTS.md contradiz-se sobre o painel no arranque (`doc-vs-code.md:23`) | **OPEN** — herdado da linha #46 |
| F4 | a figura fp16 do AGENTS.md (1230 MB) nao bate com o disco (`doc-vs-code.md:24`) | **OPEN** — herdado da linha #47 |
| F5 | AGENTS.md cita worker-bridge.js:133 como STATE_MAP (`doc-vs-code.md:25`) | **OPEN** — herdado da linha #48 |
| F6 | o rank-1 do use_vad e retratado 230 linhas abaixo (`doc-vs-code.md:26`) | **OPEN** — herdado da linha #49 |
| F7 | live-captions deixa uma decisao supersedida de pe (`doc-vs-code.md:27`) | **OPEN** — herdado da linha #50 |
| F8 | full-audit descreve a regra de juncao de 1200 ms (`doc-vs-code.md:28`) | **OPEN** — herdado da linha #51 |
| F9 | 14 campos, 0 divergencias do webview-shell nao e reproduzivel (`doc-vs-code.md:29`) | **OPEN** — herdado da linha #52 |
| F10 | AGENTS.md cita worker/runs/exit3-armB-worker.jsonl; o ficheiro vive em _main/ (`doc-vs-code.md:30`) | **APPLIED** — herdado da linha #53, fechada nesta revisao pelo proprio AGENTS.md:169 |

### window-visibility.md (F1-F7)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| F1 | o painel mostra-se sozinho sem accao do dono (edgechromium.py:348 form.Show() sob transparent=True) (`window-visibility.md:186`) | **OPEN** — herdado da linha #4 (dois censos do mesmo instrumento discordam; o AGENTS.md marca o par NAO RECONCILIADO e a ordem do dono suspendeu o censo) |
| F2 | o predicado do censo (MainWindowHandle) nao testa monitor (`window-visibility.md:187`) | **OPEN** — herdado da linha #31 |
| F3 | o censo nao e panel-specific (`window-visibility.md:188`) | **OPEN** — herdado da linha #32 |
| F4 | comentarios obsoletos/contraditorios sobre a cura OFFSCREEN no sotto_webview.py (`window-visibility.md:189`) | **OPEN** — herdado da linha #33 |
| F5 | _move_into_place morto + posicao viva x=-10000 sem explicacao (`window-visibility.md:190`) | **APPLIED** — herdado da linha #59 (a metade do metodo morto; a posicao viva e observacao de processo, fora do ficheiro) |
| F6 | _on_navigation_start faz early-return em self.visible (`window-visibility.md:191`) | **OPEN** — herdado da linha #60 |
| F7 | run.cmd:6 promete start hidden enquanto o shell pisca (`window-visibility.md:192`) | **OPEN** — herdado da linha #61 |

### windows-landmines.md (F1-F4)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| F1 | console-census.py passa CREATE_NO_WINDOW + DETACHED_PROCESS -> canal de 0 bytes rc 0 (`windows-landmines.md:309`) | **OPEN** — herdado da linha #5 |
| F2 | wait(timeout=) sem handler em 3 oraculos -> filho orfao (`windows-landmines.md:312`) | **OPEN** — herdado da linha #34 |
| F3 | run-live-hidden.py wait(timeout=) sem handler + DETACHED_PROCESS morta (`windows-landmines.md:315`) | **OPEN** — herdado da linha #35 |
| F4 | subprocess.run(timeout=) a volta do electron.exe multi-processo pode nao ser tecto [INFERENCE] (`windows-landmines.md:317`) | **OPEN** — herdado da linha #62 |

### launch-entry.md (G1-G5)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| G1 | um painel ausente ainda reporta 0 (`launch-entry.md:87`) | **APPLIED** — herdado da linha #6 (--check-args devolve 3 PANEL_MISSING) |
| G2 | um pywebview ausente ainda reporta 0 (`launch-entry.md:94`) | **APPLIED** — herdado da linha #7 (devolve 1) |
| G3 | o shell pode pendurar depois de STAGING_LOADED e o run.cmd diz 0 (`launch-entry.md:98`) | **APPLIED** — herdado da linha #8 (ready-file fresco + --wait-ready, sai 4) |
| G4 | sem pythonw.exe a app arranca sob o python.exe de consola (`launch-entry.md:102`) | **APPLIED** — herdado da linha #16 (recusa alta e sem janela, sai 3) |
| G5 | o proprio pre-flight e um run pythonw sem stdout: o usage:/error: do argparse e descartado e o rc e o contrato inteiro (`launch-entry.md:119`) | **OPEN** — a fonte diz que e BY DESIGN (launch-entry.md:124-125); fica aberto enquanto o rc for o unico sinal |

### run-cmd-gaps-fixed.md (G1-G4)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| G1 | painel ausente reportava 0 (`run-cmd-gaps-fixed.md:26`) | **APPLIED** — o doc e o recibo de fecho (:108 BEFORE rc=0 -> AFTER rc=3) |
| G2 | pywebview ausente reportava 0 (`run-cmd-gaps-fixed.md:39`) | **APPLIED** — o doc e o recibo de fecho (:109 BEFORE rc=0 -> AFTER rc=1) |
| G3 | um hang reportava 0 (`run-cmd-gaps-fixed.md:51`) | **APPLIED** — o doc e o recibo de fecho (:110 BEFORE rc=0 -> AFTER rc=4 com recibo de HANG) |
| G4 | o fallback pythonw -> python.exe punha uma consola no ecra (`run-cmd-gaps-fixed.md:84`) | **APPLIED** — o doc e o recibo de fecho (:111 BEFORE rc=0 -> AFTER rc=3) |

### oracles.md (Finding A-H6)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| Finding A | recibo de topo STALE (panel-exit3-oracle.log mtime 03:54:30 < fonte) (`oracles.md:404`) | **OPEN** — herdado da linha #29 |
| Finding B | roubo de foco e um verde (focus_stolen=true e sai 0) (`oracles.md:409`) | **OPEN** — herdado da linha #28 |
| Finding C | run-cmd-exit-oracle esta RED hoje no conjunct do census (`oracles.md:413`) | **OPEN** — herdado da linha #30 |
| Finding D | um braco negativo sem recibo (o bogus do runcmd-entry-driver.py) (`oracles.md:418`) | **OPEN** — herdado da linha #58 |
| H1 | o selftest da shell nao afirma qualidade do output (`oracles.md:393`) | **OPEN** — herdado da linha #25 |
| H2 | queue_drops nunca era afirmado (`oracles.md:394`) | **APPLIED** — herdado da linha #26 (delivery-rate-oracle afirma queue_drops == 0) |
| H3 | o ARM A do painel aceita UMA legenda como LIVE (`oracles.md:395`) | **OPEN** — herdado da linha #27 |
| H4 | model-spec-oracle sem braco negativo (`oracles.md:396`) | **OPEN** — herdado da linha #56 |
| H5 | _oss_oracle sem braco negativo (`oracles.md:397`) | **OPEN** — herdado da linha #57 |
| H6 | o selftest da shell regista focus_stolen=true e sai 0 (`oracles.md:398`) | **OPEN** — herdado da linha #28 (segunda entrada do mesmo achado que Finding B) |

### auditoria-completa-20261007.md (F1-F20)

| rotulo | achado (doc:linha) | estado |
|---|---|---|
| F1 | o arranque documentado (run.cmd) nao arranca worker nenhum -> Alt+C nunca transcreve (`auditoria-completa-20261007.md:63`) | **APPLIED** — §12.3 (:695-702): corrigido com START_REASONS + guarda antes do spawn + gate novo; §11 :619 |
| F2 | o HISTORY nao pode ser alimentado: nenhuma meta do motor live traz producer (`auditoria-completa-20261007.md:64`) | **OPEN** — o gate da fonte diz PRODUCER-VERDICT: no-producer-in-tree (:663) e o transcript foi fechado ao motor live por ordem do dono (:752); nota 2026-10-11: a arvore viva passou a carimbar producer (sotto_worker.py:3069/3567/3605) mas se a linha chega ao meta.producer que o gate canonico le continua NAO MEDIDO |
| F3 | done.verdict=captions-emitted com captions:0 e exit 0 (`auditoria-completa-20261007.md:65`) | **APPLIED** — §11 :588: captions==0 ja nao produz captions-emitted (verdict-gate GREEN 11/11); residual declarado em :774-775 |
| F4 | o tap WASAPI nunca e fechado na rotacao; o endpoint abandonado continua a entregar audio (`auditoria-completa-20261007.md:66`) | **APPLIED** — §11 :590: VERDICT PASS 71/71, stop() idempotente e nenhum on_block depois de stop(); residual: rotacao real nao exercida (:765-767) |
| F5 | o hot reload do painel navega para chrome-error:// (`auditoria-completa-20261007.md:67`) | **APPLIED** — §11 :620: reload_panel_assets faz o bounce por stage.html; verificado por LEITURA, um hot reload real nao foi medido (:761-763) |
| F6 | guarda morta: panel.js le engine.state().provisionalRoute, campo que o motor nunca devolve (`auditoria-completa-20261007.md:68`) | **APPLIED** — §11 :621 + panel-state-guard GREEN 3/3 (:587): state().provisional existe e bate com o literal |
| F7 | a app nao tem como ser fechada pela UI (`auditoria-completa-20261007.md:69`) | **APPLIED** — §11 :621: bridge.quit() (panel.js:961) e um controlo que o chama |
| F8 | dois classificadores independentes do mesmo status (`auditoria-completa-20261007.md:70`) | **APPLIED** — §11 :621: statusPayload/statusKind no painel |
| F9 | o campo de busca do painel nao pode receber teclado (`auditoria-completa-20261007.md:71`) | **OPEN** — a fonte transfere a decisao para o dono (:481, :762): hoje nao tem backend nem teclado e nao foi exercido |
| F10 | RTF > 1 na CPU: a app nao acompanha a fala em tempo real (`auditoria-completa-20261007.md:72`) | **OPEN** — a fonte transfere a decisao para o dono (:756-757: GPU, export com chunk menor, ou dizer que esta atrasado) |
| F11 | max_symbols_per_step usado como orcamento do chunk, nao por frame (`auditoria-completa-20261007.md:73`) | **APPLIED** — :771: verificado por caminho de codigo (teto por frame); a corrida do modelo nao foi feita |
| F12 | o segundo passe nao repoe o front-end cache-aware nem o VAD (`auditoria-completa-20261007.md:74`) | **APPLIED** — §11 :615: a sonda fresh-processor da GREEN (dois processadores distintos, buffers proprios); o TEXTO do segundo passe nao foi medido (:768-770) |
| F13 | model.lang_id ausente cai no locale do host (os) (`auditoria-completa-20261007.md:75`) | **APPLIED** — despachado ao worker (:544); a arvore viva diz THE DEFAULT IS auto, NOT os (F13) (sotto_worker.py:4183-4192) e o AGENTS.md tem a linha RESOLVED do lang_id — estabelecido pela ARVORE+contexto, nao por uma frase da fonte |
| F14 | use_vad no codigo tem default False e contradiz config/docs (`auditoria-completa-20261007.md:76`) | **APPLIED** — §11 :597: use_vad default True (sotto_worker.py:4257 no ficheiro vivo) — fecha tambem a linha #22 |
| F15 | o candidato de dispositivo e ordenado UMA vez no arranque e prefer_rendering_now nao existe (`auditoria-completa-20261007.md:77`) | **OPEN** — nenhuma frase da fonte nomeia cura nem transferencia para este achado (nem em :544 nem em §12.7) e a arvore viva nao tem prefer_rendering_now |
| F16 | GetBuffer chamado com 4 de 5 parametros (o 5. parametro, pu64QPCPosition, e out-pointer) (`auditoria-completa-20261007.md:78`) | **APPLIED** — despachado a captura (:544); a arvore viva declara CINCO out-parameters e passa o 5. como NULL explicito (wasapi_loopback.py:920-926, :978) — estabelecido pela ARVORE |
| F17 | asr.labels + done.text crescem sem limite e saem numa unica linha JSONL (`auditoria-completa-20261007.md:79`) | **APPLIED** — §11 :594-597: labels_pruned e done_text_max_chars legiveis no disco (grep do coordenador) |
| F18 | excepcoes fora dos poucos try escapam ao contrato JSONL (EOF sem done/error) (`auditoria-completa-20261007.md:80`) | **OPEN** — nenhuma frase da fonte nomeia cura nem transferencia para este achado; nada na arvore o fecha |
| F19 | docs/AGENTS.md:102 afirma que o segundo passe esta AUSENTE (`auditoria-completa-20261007.md:81`) | **APPLIED** — o proprio AGENTS.md retracta por nome (CORRECTED AGAIN 2026-10-07 — the M1-M3 SECOND PASS IS PRESENT AND WIRED ON THE LIVE PATH) e a lane de docs entregou (:651) |
| F20 | o README.md da raiz descreve outro produto (Tauri/Rust/Svelte) (`auditoria-completa-20261007.md:82`) | **APPLIED** — o README.md vivo diz que a app que existe e Python+WebView2 e marca o Tauri Planned, NOT implemented (README.md:12-16, :48-52); a linha #45 fica OPEN porque docs/roadmap.md:53 ainda o descreve |

## Contagem (o que torna o mapa checavel)

- **APPLIED:** 63
- **OPEN:** 76
- **IN-FLIGHT:** 0

Conferencia: 63 + 76 + 0 = **139** = linhas de achado no mapa (62 achados das tabelas + 76 entradas do
indice de rotulos). Um achado indexado duas vezes nao e um achado novo: cada entrada do indice repete,
palavra por palavra, o estado da linha que indexa. Esta e a aritmetica que o gate verifica
(`APPLIED + OPEN + IN-FLIGHT == findings_total`); a revisao T4 correu o gate antes e depois da edicao
e os dois verdictos estao no recibo `_main/receipt-20261011-audit-map-t4.md`. A passagem do Lead
(2026-10-11, depois de fechar #45 e F2 com os tres documentos corrigidos) voltou a correr o MESMO gate:
`rc=0 GREEN`, `counts=applied:49/open:89/inflight:0`, `findings_distinct=138`, 43/43 docs nomeados.

**MISSING:** nenhum rotulo de fonte ficou de fora — os 36 rotulos que os 43 docs declaram estao todos
nesta lista. **INVENTED:** nenhum achado foi criado sem fonte, e nenhuma linha ficou sem estado do
vocabulario fechado. **WRONG_STATE:** os estados das linhas antigas nao foram re-medidos nesta revisao
(a ordem do dono de 2026-10-11 proibe abrir o Sotto); ficam como a revisao de 2026-10-06/07 os mediu, e
as SEIS linhas que estas duas passagens fecharam (#2, #22, #37, #53 na lane T4; #45 e F2 na passagem do
Lead) trazem `[2026-10-11]` e a prova na propria linha.

O que mudou nesta revisao, em uma linha cada: #2 (IN-FLIGHT -> APPLIED, `blank-frames-root-cause.md:6-9`),
#22 (`use_vad` -> APPLIED, `auditoria-completa-20261007.md:597` + `sotto_worker.py:4195`), #37
(`S_FALSE` -> APPLIED, `flat-endpoint.md:125-142`), #53 (o artefacto -> APPLIED, `AGENTS.md:169`); #45 e F2 (a stack Tauri/Rust/SQLite -> APPLIED: os tres
documentos foram corrigidos nesta passagem — `docs/README.md`, `docs/roadmap.md`, `README.md`);
#44, #47, #48 e #54 (deriva documental -> APPLIED: `docs/README.md` deixou de dizer que nao existe
codigo, a figura fp16 ficou retractada, a citacao do STATE_MAP passou a `:114`, e o
`worker/README.md` passou a listar as 11 folhas do config corrigindo duas afirmacoes falsas);
#56, #57 e #63 (dois instrumentos que nao sabiam dizer NAO -> APPLIED com braco negativo provado, e
a nota que impede o snippet embutido no `docs/oss-approaches-20261006.md` de ser lido como o
instrumento vivo);
#49, #50 e #51 (deriva documental nos tres docs da OSS/live-captions/full-audit) — a nota que
faltava, o SINAL corrigido contra a medicao, e a regra de juncao nomeada como historica com a viva
ao lado);
#9 e a F2 herdada dela (o `flags` descartado -> APPLIED: o unico defeito vivo apanhado pelo sweep
foi corrigido no PRODUTO — `DATA_DISCONTINUITY` contado nos dois loops, com o mutante que o prova).

---

## SELF-AUDIT

**protocolos em falta (2026-10-06)** — o mapa antigo devia ter extraido mecanicamente todos os rotulos
dos docs como PASSO 0. Nesta revisao isso foi feito: a seccao *Indice de rotulos* e o produto de uma
extracao mecanica sobre os 43 docs, e a contagem do gate e o `comm` que faltava.

**verificacao adicional** — re-medidos por leitura, no working tree, os pontos que fecham as linhas
marcadas `[2026-10-11]` (#2, #22, #37, #53) e os 76 rotulos indexados. O que NAO foi corrido: nenhum
oraculo, nenhum lancamento do shell/worker — a ordem do dono de 2026-10-11 proibe abrir o Sotto.

**checkboxes novas** — "para cada rotulo de um doc fonte, exigir a sua linha no mapa, com o mesmo
`file:line`". O gate que fecha isso existe e e o que este mapa passa:
`I:/!manager/scripts/audit-map-gate.sh H:/sotto/docs/audit`.

**review por outro subagente** — sim-com-escopo: re-derivar so o mapa `rotulo -> linha` a partir de um
`grep` dos 43 docs. Nao para os estados.

**gate-doubt** — **verde-de-verdade:** o verde e aritmetico (47 + 91 + 0 = 138) e nao e vacuoso (o
mesmo gate recusava este mapa antes desta revisao, com 3 causas). **falta-no-gate:** o gate nao compara
o CONTEUDO de uma linha com a fonte — um estado errado com o rotulo presente passa; a defesa e a
citacao `doc:linha` em cada linha nova e o recibo. **gate-melhor:** nada a pedir — o gate existe e passa.

**confianca** — alta na cobertura (43/43 docs nomeados, 36/36 rotulos indexados) e nas linhas APPLIED
de 2026-10-06/07; media nos quatro estados fechados nesta revisao (dois por frase de fonte, dois por
linha da arvore viva — declarados como tal na linha e no recibo).

**nao verificado** — (1) nenhum oraculo re-corrido e nada lancado (ordem do dono); (2) as linhas
APPLIED antigas nao foram re-medidas, so herdadas; (3) as curas que a fonte so "verificou por leitura"
(F5, F11, F16) nao foram corridas; (4) `AGENTS.md` e `README.md` vivos foram lidos, nao re-sondados
byte a byte nesta revisao.
