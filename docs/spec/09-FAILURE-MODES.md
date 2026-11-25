# 09 — MODOS DE FALHA: o que acontece quando cada peça falha

Esta página responde, por linha de falha: **quem deteta, o que o código faz a seguir, e o que o dono vê**.
Uma falha sem linha nenhuma não é observável — é hipótese; cada linha nomeia a ETIQUETA que a deteta.
`[CODE]` foi lido em `HEAD` a 2026-11-11; `[MEASURED]` foi re-medido hoje em `_main/webview-run.log`
(207 056 linhas, 25 439 116 B, de `2026-11-08 18:23:00.721` a `2026-11-11 22:56:36.382`). Nenhum número é
copiado de outro documento deste directório.

## 0. Como ler cada linha

Três colunas: **detector** (a etiqueta que torna o acidente um facto datado), **acção** (o que o processo
faz depois de a ler) e **dono** (o texto/cor no painel ou na legenda, via `worker_status_text` e
`caption_status_for`). `[INFERENCE]` Uma assimetria atravessa tudo: a shell pode **matar e relançar** o
worker, mas não lhe pode falar (`stdin=subprocess.DEVNULL`, `sotto_webview.py:23555`) — a política rápida
vive do lado do worker e a shell só observa e substitui.

## 1. Tabela-mestra

| peça | falha | detector | acção | o dono vê |
|---|---|---|---|---|
| worker | saída com código | `BRIDGE_EXIT` | classifica `rc`/`killed`, agenda volta | estado anterior mantém-se |
| worker | saída ≠ 0 | `BRIDGE_DEATH` | `pending_error` + escada `retry` | texto do worker a vermelho |
| worker | traceback na cauda | `BRIDGE_DEATH_CAUSE` | regista a 1.ª linha com `Error`/`Exception` | nada directo (log) |
| worker | morte ordenada pela shell | `BRIDGE_KILLED` | não conta como falha | o estado que a shell pintou |
| worker | vivo e mudo | `BRIDGE_SILENT` (+`_GRACE`,`_WAIT`) | mata e relança | `Worker silent` |
| worker | mudo com veredicto de dispositivo | `BRIDGE_SILENT_BENIGN` | **não mata**; re-arma e nomeia | `No audio to transcribe` |
| worker | carga a decorrer | `BRIDGE_SILENT_LOADING` | re-arma; tecto 180 s | `carregando modelo…` |
| worker | carga presa | `BRIDGE_SILENT_LOAD_TIMEOUT` | mata e relança | `Model load timeout` |
| worker | CPU alta sem linhas | `WORKER_COST_RESTART` | `revive_worker('cost-watchdog')` | nada (silencioso) |
| WebView2 | init falhou | `WEBVIEW2_INIT_FAILED` | regista e segue sem página | painel em branco |
| WebView2 | página ainda não existe | `EMIT_ASYNC_PREWEBVIEW` | descarta o payload | nada |
| painel | navegação não volta | `PANEL_NAV_STALL`/`_FINAL` | re-empurra aos 12 s; arranca sem painel aos 25 s | painel branco, legenda vive |
| arranque | READY não chega | `STARTUP_NOT_READY` + `HANG rc=4` | despeja pilhas; largador sai 4 | consola diz HANG |
| UI | janela não responde | `UI_WATCHDOG_*` | esconde a janela **sem sair** | janela desaparece, processo fica |
| UI | o dono manda fechar | `SHELL_EXIT` → `EXIT_BEGIN` | escalador + matador externo | a app fecha |
| captura | sem dispositivo | `no input device available` | worker sai 2 | `Worker error at device` |
| captura | dispositivo ocupado | `OPEN_RETRY_RETRY` | 2 retries a 1,5 s, depois roda | `No audio endpoint was free` |
| captura | tap bloqueia a abrir | `TAP_OPEN_TIMEOUT` | abandona e segue a escada | o mesmo |
| captura | desktop calado | `device-rotated reason=flat` | **parqueia**, não morre | `worker-parked (…)` |
| motor | pasta do modelo ausente | `model dir not found` | worker sai 2 | `Worker error at model` |
| motor | load rebenta | `stage="model-load"` | worker sai 2 | `Worker error at model-load` |
| motor | GPU ocupada | `VRAM_GUARD_PARKING` | larga motores, mantém processo | `GPU busy` |
| YouTube | porta em baixo | `YOUTUBE_CDP_ATTACH_FAILED` | retry com backoff | legenda do ASR (ou nenhuma) |
| YouTube | alvo velho | `YOUTUBE_TARGET_STALE` | serve o último snapshot | linha antiga por instantes |
| YouTube | aba sem media | `YOUTUBE_CDP_DEAD_TAB` | larga o socket e re-escolhe | idem |
| YouTube | relógio parado | `YOUTUBE_CLOCK_STATIC` | trata como pausa e apaga pixels | ecrã limpo |
| fonte | o player manda no ecrã e o microfone produz uma linha | `EXTERNAL_OWNER` + `ASR_PAINT_REFUSED` | a linha local é **descartada** (nem ecrã nem histórico) e o episódio é contado | nada: a legenda do player |
| processo | shell morta à força | job object | mata `msedgewebview2` e filhos | nada fica para trás |
| processo | 2.ª instância | `SINGLE_INSTANCE already_running=true` | sai 0 | nada aparece |

## 2. Morte do worker

### 2.1 As cinco classes, uma etiqueta cada

| etiqueta | quando | o que decide | linha |
|---|---|---|---|
| `BRIDGE_EXIT` | o filho terminou | imprime `rc`,`killed`,`spawns`,`captions` e a cauda de stderr | `sotto_webview.py:24406` |
| `BRIDGE_DEATH_CAUSE` | há `Error`/`Exception` no stderr | publica a última linha do worker | `:24415` |
| `BRIDGE_KILLED` | `killed=True` | **não** conta como morte; a volta já está agendada | `:24423` |
| `BRIDGE_DEATH` | `rc != 0` sem homicídio da shell | `deaths += 1`; `kind` sai do veredicto | `:24463` |
| `BRIDGE_SILENT` | sem progresso na janela | mata e relança com `reason=silent` | `:24392` |

`[CODE]` `BRIDGE_KILLED` existe porque o `rc=1` de um homicídio ordenado **parecia** falha
(`sotto_webview.py:23220-23228`); a cor lê o veredicto do worker, não o código de saída — `no-audio` só
com `last_error is None` e `last_no_audio is not None`, e crash sem veredicto é `error` (`:24452-24457`).
`[MEASURED]` `grep -c -F 'BRIDGE_DEATH rc='` → **6**; `... 'BRIDGE_DEATH_CAUSE '` → **0**;
`... 'BRIDGE_KILLED pid='` → **1** (2026-11-11): as seis mortes não deixaram linha de causa.

### 2.2 Duas janelas, e uma graça antes de matar

`[CODE]` `WORKER_SILENCE_MS = 30000` depois de `model-loaded`, `WORKER_LOAD_SILENCE_MS = 180000` antes;
`_silence_window` encurta a de carga pelo tempo já gasto (`sotto_webview.py:1457`, `:1465`, `:24137-24155`).
`[CODE]` Antes de matar, o vigia pergunta se o progresso avançou: se sim, `BRIDGE_SILENT_GRACE` e a janela
recomeça; senão `BRIDGE_SILENT_WAIT` volta dentro da graça, 10 % da janela com piso de 50 ms
(`:1483-1494`, `:24358-24391`). `[MEASURED]` `grep -c -F 'BRIDGE_SILENT_GRACE '` → **3**;
`... 'BRIDGE_SILENT_WAIT '` → **4**; `... 'BRIDGE_SILENT ms='` → **1** (2026-11-11): a graça disparou
mais vezes do que o assassínio.

### 2.3 O ramo benigno é o que mudou o comportamento

`[CODE]` Com veredicto de "nada para transcrever" (`WORKER_NO_AUDIO_STATES`/`_VERDICTS`,
`sotto_webview.py:1411-1428`), o vigia **não mata**: escreve `BRIDGE_SILENT_BENIGN`, pinta `Audio tap
silent - nothing to transcribe` com tipo `busy` e re-arma (`:24253-24299`). `[MEASURED]`
`grep -c -F 'BRIDGE_SILENT_BENIGN '` → **19** contra **1** `BRIDGE_SILENT ms=` (2026-11-11).

### 2.4 As três escadas (`_schedule_restart`)

| escada | condição | primeiro passo | tecto | código |
|---|---|---|---|---|
| `retry` | crash ou morte desconhecida | 1 000 ms, dobrando | 30 000 ms | `sotto_webview.py:24576-24577` |
| `device-switch` | `kind=no-audio` **e** há som noutro endpoint | 250 ms | 2 trocas grátis | `:1515-1516` |
| `no-audio` | `kind=no-audio` sem som, ou trocas gastas | 15 000 ms, dobrando | 300 000 ms | `:1540-1542` |

`[CODE]` A decisão é a função pura `device_death_delay` (`sotto_webview.py:1519-1546`); a saída limpa
(`rc=0`) tem piso `CLEAN_EXIT_FLOOR_MS = 20000`, nomeado por `BRIDGE_RESTART_FLOOR` (`:1502`,
`:24578-24584`). `[MEASURED]` `grep -c -F 'BRIDGE_RESTART_FLOOR '` → **1**: `2026-11-11 01:04:52.664
BRIDGE_RESTART_FLOOR ladder=retry delay_ms=1000 floor_ms=20000 why=clean-exit-not-a-crash`. `[CODE]` **A
escada `retry` não tem tecto de tentativas**: `self.restarts` é incrementado e nunca comparado com um
máximo (`:24576-24577`); só a `no-audio` compara (`:24523`). `[INFERENCE]` Um crash reabre o modelo.

### 2.5 O tecto do `no-audio`: parar de recarregar

`[CODE]` `no_audio_restart_cap=3` (`sotto_webview.py:23069`); ao atingi-lo escreve
`BRIDGE_RESTART_SUPPRESSED`, passa a `NO_AUDIO_STATE` com uma frase que manda verificar a rotagem e carregar
em Alt+C (`:24523-24540`); `_arm_audio_resume` sonda `audio_playing.playing()` de 3 em 3 s e respawna no
primeiro som (`:24605-24647`). `[MEASURED]` `grep -c BRIDGE_RESTART_SUPPRESSED` → **0** (2026-11-11).

### 2.6 `cost-watchdog`: CPU alta com zero linha

`[CODE]` `on_worker_cost` journaliza `BRIDGE_WORKER_COST` uma vez por minuto (`COST_LOG_INTERVAL_S=60`) e
chama a decisão pura `cost_watchdog.plan` (`sotto_webview.py:20487-20510`): `cpu_pct_avg >= BUSY_PCT=60.0`
**e** zero linha (`rows_since_tick`) durante `STALL_TICKS=18`, piso `FLOOR_S=600`, tecto `MAX_PER_HOUR=3`
(`cost_watchdog.py:38-57`). Executa `revive_worker('cost-watchdog')` (`:20512-20535`). `[MEASURED]`
`grep -c WORKER_COST_RESTART` → **0** (2026-11-11): ligado, nunca disparou.

## 3. WebView2

`[CODE]` `_on_core_ready` testa `args.IsSuccess`; falso → `WEBVIEW2_INIT_FAILED
error=<InitializationException>` e **retorna**, sem retry (`sotto_webview.py:13962-13970`). `self.core`
fica `None` e tudo o que depende da página bate no guarda seguinte. A razão do perfil efémero é esta
falha: um perfil partilhado com o processo anterior a morrer dá `0x800700AA` e a app sobe sem página
(`:26344-26348`). `[MEASURED]` `grep -c WEBVIEW2_INIT_FAILED` → **0** (2026-11-11).

`[CODE]` O pipeline de legenda arranca **antes** do WebView2 (`start_caption_pipeline('pre-webview')`,
`sotto_webview.py:26212`), por isso há eventos com `self.core is None`: o emissor escreve **uma** linha
`EMIT_ASYNC_PREWEBVIEW kind=... reason=no-core` e descarta o payload (`:20650-20663`). `[MEASURED]`
`grep -c EMIT_ASYNC_PREWEBVIEW` → **1** (2026-11-11).

`[CODE]` `_arm_panel_stall_watch` corre no fio `sotto-panel-stall`: aos **12 s** sem ficheiro de prontidão
escreve `PANEL_NAV_STALL` e re-empurra `load_url` noutro fio (porque `load_url` também não volta com o
browser morto); aos **25 s** escreve `PANEL_NAV_STALL_FINAL` e chama `_complete_startup`, que arranca
worker, legenda e hotkeys sem a página (`sotto_webview.py:14090-14160`), com
`PANEL_NAV_RETRY_FAILED`/`PANEL_NAV_COMPLETE_FAILED` nas metades (`:14136`, `:14154`) e `url=`, `core=`,
`threads=` no estado (`:14110-14118`). `[MEASURED]` `grep -c PANEL_NAV_STALL` → **0**;
`grep -c PANEL_SHOW_REFUSED` → **29** (2026-11-11): a recusa de mostrar é frequente, o stall não ocorreu.

`[CODE]` `_start_startup_stack_watch`, armado no início de `main`, aos 15/30/60 s sem READY escreve
`STARTUP_NOT_READY s=<n> threads=<n>` e despeja todas as pilhas para `_main/_startup-stacks.log`
(`sotto_webview.py:25900-25943`). O `run.cmd` espera de forma limitada e, sem ficheiro, escreve `HANG rc=4
by=run.cmd-readiness` e sai 4 (`run.cmd:276-285`). `[MEASURED]` `grep -c STARTUP_NOT_READY` → **2**;
`grep -c "HANG rc=4"` → **2**, a última na linha 207056 (2026-11-11). `[INFERENCE]` O `run.cmd` **não**
mata a app que largou — o `start ""` é anterior à espera — logo o rc=4 é relatório e a shell fica viva.

## 4. UI presa

`[CODE]` O vigia pergunta `WM_NULL` com `SendMessageTimeoutW` de 5 em 5 s, prazo 6 000 ms; três golpes
(`UI_WATCHDOG_STRIKES=3`) ou seis quando a pilha do UI **não tem nenhum frame nosso**
(`UI_WATCHDOG_STRIKES_FOREIGN=6`) (`sotto_webview.py:13001-13014`, `:13024-13044`). A política é pura:
`ERROR_TIMEOUT=1460` é a única assinatura de prazo; `NOERR_STRIKES=6`/`NOERR_HARD_CAP=12` cobrem `got=0`
sem assinatura (`ui_watchdog_policy.py:57,67,74`, `:102-160`); amostra em que o laço demorou 1,5× o
orçamento não soma golpe (`UI_WATCHDOG_STARVED`, `ui_watchdog_policy.py:79`, `sotto_webview.py:13240`)
e antes da primeira resposta nenhum golpe conta (`UI_WATCHDOG_NOANSWER_BEFORE_FIRST`, `:13255`).

`[CODE]` O ramo de confirmação escrevia `UI_WATCHDOG_EXIT code=9` e saía. A ordem do dono de 2026-11-09
("*should close only because of me, or hard kill from task manager*") substituiu-o: hoje escreve
`UI_WATCHDOG_RECOVER code=9 -- a UI nao respondeu; a janela sai do ecra e o processo FICA` e chama
`_ui_hung_recover`, que faz `ShowWindow(SW_HIDE)` e `UI_HUNG_RECOVER ... still_alive=true`
(`sotto_webview.py:13313`, `:13357`). `[CODE]` O caso que motivou a mudança foi `UI_WATCHDOG_NOERR_CAP
noerr=12 err=0` seguido de saída, com o processo vivo (`:13286-13312`). `[MEASURED]`
`grep -c -F 'UI_WATCHDOG_EXIT'` → **1**, em `2026-11-09 21:18:11.250`; `... 'UI_WATCHDOG_RECOVER code'`
→ **0**; `... UI_WATCHDOG_RECOVERED` → **66**; `... UI_WATCHDOG_STARVED` → **6** (2026-11-11).
`[INFERENCE]` `ShowWindow` é cross-thread e funciona no estado em que o vigia dispara.

`[CODE]` `request_exit` escreve `SHELL_EXIT rc=... reason=...` e chama `_hard_exit`
(`sotto_webview.py:17188`, `:17251`), idempotente e com prazo em cada espera: `TerminateProcess` em si
próprio aos **2,5 s** (`EXIT_ESCALATE_S`), matador externo com **4,0 s** (`EXIT_KILLER_GRACE_S`), reap
total de **1 800 ms**, `EXIT_TERMINATE`, drenagem de **0,75 s** (`:1789-1792`, `:1953-2005`).
`[CODE]` `exit_killer.py` abre o pid **com carimbo de criação**, mata os filhos, depois o shell, e escreve
`EXIT_KILLER_FIRED`/`EXIT_KILLER_ORPHAN` no mesmo log (`exit_killer.py:100-150`). `[INFERENCE]` É o único
dono que sobrevive a um processo preso num `DllMain`. O motor quente **não** entra na lista de filhos a
matar (`keep_warm`), para atravessar o reinício (`sotto_webview.py:17263-17286`).

## 5. Captura

`[CODE]` Sem candidatos, o worker emite `state="error" stage="device" detail="no input device available"`
e `return 2` (`sotto_worker.py:7318-7320`). A shell vê `rc=2` sem veredicto de dispositivo: `BRIDGE_DEATH
kind=error`, `pending_error` vermelho e escada `retry`. `[MEASURED]` `grep -c 'no input device available'`
→ **0** apesar de 14 `BRIDGE_EXIT` (2026-11-11): a máquina do dono tem sempre endpoints.

`[CODE]` `AUDCLNT_E_DEVICE_IN_USE` (`0x8889000A`) é reconhecido; a escada tenta **duas** vezes com 1,5 s
(`OPEN_RETRY_RETRY`) e passa ao candidato seguinte (`sotto_worker.py:8526-8542`); quando o último falha, o
estado é `audio-endpoint-unavailable reason=ladder-exhausted` com texto neutro e recusas cruas fora de
`STATUS_BODY_FIELDS` (`:8578-8612`), que a shell traduz para *"No audio endpoint was free - Sotto keeps
looking"*, fora do vermelho (`sotto_webview.py:2196-2199`). `[MEASURED]` `grep -c OPEN_RETRY_RETRY` → **0**;
`grep -c OPEN_LADDER_EXHAUSTED` → **0** (2026-11-11).

`[CODE]` Sinais abaixo de `TAP_PEAK_FLOOR = 0.002` numa janela de `TAP_WINDOW_S = 6.0`
(`sotto_worker.py:370-371`): o candidato roda com `reason="flat"` (`:8976`), backoff de 1 s a 8 s
(`:1142`) e tecto `MAX_ROTATIONS_WITHOUT_SIGNAL = 8` (`:575`). Quem abriu, correu `TAP_SILENT_BLOCKS = 20`
blocos e ficou sob o piso é **nomeado** `state="silent-device"` com dispositivo, API, `peak` e `floor`
(`:397`, `:9170-9200`). Um veredicto de dispositivo **não fecha a sessão**: `park_session` mantém o modelo
residente e reabre o dispositivo num backoff de 15 s a 300 s, chamando `progress()` em fatias de 4 s para
o vigia de silêncio não matar a sessão (`:1095-1101`, `:1256-1300`). `[MEASURED]`
`grep -c -F 'device-rotated reason=flat'` → **44**; `grep -c -F 'SILENT-DEVICE '` → **0**;
`grep -c -F 'worker-parked'` → **64**; `grep -c -F 'WORKER_PARKED'` → **1** (2026-11-11).

`[CODE]` A abertura corre num fio `tap-open` com prazo `TAP_OPEN_TIMEOUT_S = 4.0`; se não volta, é
abandonada, o fio fecha o tap quando regressar, e o registo é `TAP_OPEN_TIMEOUT ... (the open BLOCKED
...)`; o fecho falhado leva `TAP_OPEN_ABANDONED_CLOSE_FAILED` (`sotto_worker.py:603`, `:4383-4425`,
`:4411`). `[MEASURED]` `grep -c TAP_OPEN_TIMEOUT` → **0** (2026-11-11); o caso está medido no comentário
(headset Bluetooth, ~59 s na escada), não neste log.

`[CODE]` Dois latches exclusivos: `_external_parked` (o player fornece a legenda) e `_vram_parked` (outra
app quer a GPU); `park_worker_for_vram` recusa com `_external_parked` posto (`sotto_webview.py:19724-19764`).
Ambos largam **o motor**, nunca o processo: `set_engine_park` escreve a chave no `panel-visibility.json` que
o worker já sonda (`:19702-19721`). O desparque externo limpa `_external_parked` e chama
`set_engine_park(None)` **antes** de a visibilidade decidir o que recarregar (`:19836-19868`);
`resume_after_vram` limpa `_vram_parked` antes de testar `showing` (`:19766-19795`). `[MEASURED]`
`grep -c EXTERNAL_CAPTIONS_ENGINE_PARKED` → **31**; `... _ENGINE_RESUMED` → **3**;
`grep -c -F 'EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting'` → **2** (2026-11-11).
`[INFERENCE]` O 31/3 é a assinatura do latch: parque por borda, desparque à espera de uma condição.

## 6. Motor

`[CODE]` Antes de carregar, `if not os.path.isdir(model_dir)` → `status state="error" stage="model"
detail="model dir not found: <pasta>"` e `return 2` (`sotto_worker.py:7064-7065`). `[INFERENCE]` É o crash
determinístico de §2.4: a escada `retry` reabre a cada 30 s e nada muda. `[MEASURED]`
`grep -c 'model dir not found'` → **0** (2026-11-11).

`[CODE]` Qualquer excepção de `StreamAsr(...)` produz `state="error" stage="model-load"` com `<Tipo>:
<mensagem>` e `peak_rss_mb`, e `return 2`; o `finally` devolve sempre a prioridade
(`sotto_worker.py:7098-7113`). O estado `error` está em `WORKER_ERROR_STATES`
(`sotto_webview.py:1371-1376`), é guardado em `last_error` e escrito como `BRIDGE_STATUS_ERROR`
(`:24058-24066`). `[MEASURED]` `grep -c 'No registered plugin EP device found'` → **5** (2026-11-11);
`[INFERENCE]` quedas `rc=1` ficam sem `BRIDGE_DEATH_CAUSE` (0) porque a cauda mostrada é
`WORKER_THREADS`/`lang_id`/aviso ONNX.

`[CODE]` `VramGuard` lê NVML de 3 em 3 s; abaixo de `LOW_MB=1200` por **duas** amostras seguidas e com o
worker `loaded`, chama `park_worker_for_vram`; acima de `RESUME_MB = LOW_MB + MODEL_VRAM_MB = 3200`,
`resume_after_vram`, com graça de 90 s (`sotto_webview.py:3350-3382`, `:3394`, `:3438-3500`). NVML que não
responde não derruba nada: `VRAM_GUARD_READ_FAILED` e o laço continua (`:3439`); `pynvml` ausente leva
`VRAM_GUARD_UNAVAILABLE` e termina o fio (`:3423-3427`). `[MEASURED]` `grep -c VRAM_GUARD_PARKING` → **3**;
`grep -c VRAM_GUARD_RESUMING` → **3**; `grep -c VRAM_GUARD_READ_FAILED` → **545**, com
`error=NVMLError_OperatingSystem(17)` em `2026-11-09 17:23:42.314` (2026-11-11). `[INFERENCE]` 545
leituras falhadas e 0 `VRAM_GUARD_UNAVAILABLE`: o guarda ficou cego, não desligado.

`[CODE]` `worker_status_kind` testa primeiro o veredicto de no-audio e só depois o erro: os estados de
no-audio são um **subconjunto** de `WORKER_ERROR_STATES`, e a ordem inversa pintava de vermelho um desktop
calado (`sotto_webview.py:2050-2078`). `worker_status_text` traduz os HRESULT conhecidos
(`HRESULT_AUDIO_READINGS`, incluindo `0x8889000A` → "already in use … press Alt+C") e deixa os
desconhecidos **crus** (`:2129-2158`, `:2160-2233`). Na legenda, `caption_status_for` é a única fonte do
"porque está vazio": `model-loading`, `no-track`, `waiting-player-row`, `no-audio` ou `waiting-first-line`,
pela ordem em que resolvem primeiro, e `None` quando não há nada honesto a dizer (`:3105-3145`; textos em
`:3087-3102`). `[CODE]` `worker-parked` **não** tem mapeamento — não está em `WORKER_ERROR_STATES` nem em
`WORKER_WARMUP_STATES`, logo cai em `readable` e o rodapé mostra `worker-parked (reason)`
(`:2050`, `:2160`; `sotto_worker.py:1287`). `[INFERENCE]` É a lacuna de UX mais visível desta secção.

## 7. Fonte externa (YouTube)

`[CODE]` A porta é `DEFAULT_PORT = 9222`, sobreponível por `SOTTO_YT_CDP_PORT`/argumento
(`youtube_cdp_source.py:77-96`). Recusa de ligação é `port-closed`; `/json/list` que estoura o prazo é
`probe-timeout`; erro de protocolo é `probe-failed (<Nome>)` — só a recusa é a porta (`:836-856`). Cada
tentativa falhada escreve `YOUTUBE_CDP_ATTACH_FAILED` com `attempt`, `reason`, `port` e `ms`, com backoff
`RETRY_S=2,0` (`:110-130`, `:2328-2340`). `[MEASURED]` `grep -c 'reason=probe-timeout'` → **65**;
`grep -c 'reason=port-closed'` → **0**; `grep -c YOUTUBE_CDP_ATTACH_FAILED` → **58**, a última
`2026-11-11 17:39:26.927 ... attempt=6 ok=false reason=ambiguous port=9222 ms=594 tabs=10`.

`[CODE]` A idade do id escolhido é comparada com o TTL do refrescador; duas cadências sem publicação levam
`YOUTUBE_TARGET_STALE age_ms=... ttl_s=...`, no máximo uma vez por 5 s
(`youtube_cdp_source.py:1795-1812`). Uma foto de socket abandonado é descartada antes de publicar
(`tab-stale`), e uma aba com `readyState=0` larga o socket e volta à sonda com `YOUTUBE_CDP_DEAD_TAB`
(`:2195-2225`). `[MEASURED]` `grep -c YOUTUBE_TARGET_STALE` → **30**, a última `2026-11-11 20:01:19.426
... age_ms=1015 ttl_s=0.5 attached=True refreshes=32`; `grep -c YOUTUBE_CDP_DEAD_TAB` → **10**
(2026-11-11). `[INFERENCE]` TTL de 0,5 s com idade de 1,0 s: o socket está ligado e o refrescador parou.

`[CODE]` Com a porta aberta e sem foto, o caminho serve as **últimas** linhas conhecidas com
`why='cdp-stale'` em vez de cair na árvore de acessibilidade, que pode prender 17 s
(`sotto_webview.py:4946-4960`); uma mudança de `why` escreve `YOUTUBE_PAINT_STATE` (`:4993`). Quando o
player pausa/termina, a borda apaga os pixels; sem legenda durante `CAPTION_IDLE_HIDE_S = 6.0`, a janela é
esvaziada com `CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s` (`:18030`, `:18170-18180`).
`[MEASURED]` `grep -c 'why=cdp-stale'` → **12**; `grep -c CAPTION_WINDOW_BLANKED` → **313**
(2026-11-11).

`[CODE]` `CLOCK_STATIC_PAUSE_S = 2.0`: se `currentTime` não muda durante 2 s, o player é tratado como
pausado mesmo que a foto diga `paused=false` (`sotto_webview.py:5087-5124`); a primeira vez no episódio
escreve `YOUTUBE_CLOCK_STATIC held_s=... t=... paused_flag=... vid=...` (`:5324-5340`). No relógio
extrapolado, `HOLD_S = 8.0`, `BUDGET_S = 0.15` e `FRESH_S = 0.30` (`youtube_clock.py:57,61,69`); uma
leitura atrás do chão servido escreve `YOUTUBE_CLOCK_HELD t=... served=... floor=...` (`:5429`).
`[MEASURED]` `grep -c -F 'YOUTUBE_CLOCK_HELD t='` → **5 478**, da primeira `2026-11-08 18:24:05.403` à
última `2026-11-09 17:05:34.263`; `grep -c YOUTUBE_CLOCK_STATIC` → **0** (2026-11-11). `[INFERENCE]` O chão
monotónico é accionado milhares de vezes; a pausa por relógio estático não ocorreu nesta janela.

## 8. Higiene de processo

`[CODE]` `_hold_kill_on_close_job` cria um job com `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` e associa o próprio
processo; sucesso leva `SHELL_JOB_ARMED pid=... kill_on_close=true`, e cada falha leva `SHELL_JOB_FAILED
stage=create|limits|assign|exception` (`sotto_webview.py:8597-8674`). `[INFERENCE]` É o único mecanismo que
sobrevive a um `TerminateProcess` do shell, onde nenhum código Python corre. `[MEASURED]`
`grep -c SHELL_JOB_ARMED` → **17**; `grep -c SHELL_JOB_FAILED` → **0** (2026-11-11).

`[CODE]` `sweep_stale_webview_profiles` apaga `%TEMP%\tmp*\EBWebView` com mais de 5 400 s (90 min) e
devolve `(dirs, bytes)`; a idade é a guarda contra apagar o perfil de uma sonda viva
(`sotto_webview.py:11159-11200`), e só corre fora de largadas de medição, escrevendo
`WEBVIEW2_PROFILE_SWEEP dirs=... mb=...` (`:26330-26342`). `[MEASURED]`
`grep -c -F 'WEBVIEW2_PROFILE_SWEEP dirs='` → **16** (2026-11-11).

`[CODE]` O mutex é `Local\SottoShell` (`sotto_webview.py:8274`). `take_single_instance_lock` devolve `not
exists` e escreve `SINGLE_INSTANCE name=... already_running=...`; `ERROR_ALREADY_EXISTS` (183) é a única
recusa, e falha de `CreateMutexW` **deixa passar** (`:8676-8702`). A segunda largada da APP avisa que já
corre e `return 0`, sem janela, tray ou worker (`:26155-26158`); largadas de MEDIÇÃO levam um mutex
derivado das flags (`measurement_lock_name`, `:8722-8740`), e duas idênticas colidem
(`SINGLE_INSTANCE_MEASURE_BUSY`, `:26144-26153`). `[INFERENCE]` Instância antiga a segurar o mutex faz a
nova sair **0 sem sintoma**: ao dono parece que "não abriu" e o Alt+C responde à velha. `[MEASURED]`
`grep -c -F 'SINGLE_INSTANCE name='` → **17**, `grep -c -F 'already_running=true'` → **0**,
`grep -c SINGLE_INSTANCE_MEASURE_BUSY` → **0** (2026-11-11).

`[CODE]` O guarda de órfãos recusa criar worker quando a shell está a sair
(`WORKER_AUTOSTART=declined reason=... by=start_worker`, `sotto_webview.py:17741`, também para
`app-target-unresolved`, `:17803`). O `bridge.stop` mata o filho (`child.kill`, `terminate` de recurso) e
**não** bloqueia o chamador; sobrevivente escreve `BRIDGE_KILL_FAILED` (`:23607-23647`). O desparque
externo tem a sua porta anti-órfão: `EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting`
(`:19845`). Na saída, `_exit_children` devolve só os filhos desta janela, excluindo o motor quente
(`:17263-17286`), e o `exit_killer` mata o resto (`exit_killer.py:142-150`). `[MEASURED]`
`grep -c -F 'WORKER_AUTOSTART=declined'` → **15**; `grep -c BRIDGE_KILL_FAILED` → **0**;
`grep -c -F 'EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting'` → **2** (2026-11-10
19:51:00.367 e 2026-11-11 01:27:43.319).

## 9. Cobertura medida desta página

Comandos `grep -c -F '<etiqueta>' _main/webview-run.log`, a 2026-11-11 sobre 207 056 linhas:

| etiqueta | ocorrências | leitura |
|---|---|---|
| `BRIDGE_EXIT pid=` | 14 | 14 saídas de worker |
| `BRIDGE_DEATH rc=` | 6 | 6 mortes com código ≠ 0 |
| `BRIDGE_SILENT ms=` | 1 | um worker morto por silêncio |
| `BRIDGE_SILENT_BENIGN` | 19 | 19 silêncios nomeados sem matar |
| `BRIDGE_LOAD_MS ms=` | 22 | cargas: min 4 875, mediana 19 312, max 61 781 ms |
| `UI_WATCHDOG_EXIT` | 1 | a única saída do vigia, 2026-11-09 21:18:11 |
| `YOUTUBE_CDP_ATTACH_FAILED` | 58 | a fonte externa falhou anexar 58 vezes |
| `YOUTUBE_CLOCK_HELD t=` | 5 478 | o chão monotónico foi accionado 5 478 vezes |
| `VRAM_GUARD_READ_FAILED` | 545 | NVML cego em 545 amostras |

`[MEASURED]` Também zero neste log: `BRIDGE_DEATH_CAUSE`, `UI_WATCHDOG_RECOVER code`,
`SHELL_JOB_FAILED`, `BRIDGE_RESTART_SUPPRESSED`, `TAP_OPEN_TIMEOUT` (2026-11-11).
`[INFERENCE]` `BRIDGE_SILENT_BENIGN` 19 : `BRIDGE_SILENT` 1 — em `HEAD` o vigia nomeia o silêncio, não mata.

## Lacunas

- `[UNKNOWN]` **Nenhuma execução nova** — evidência de campo é só leitura do log vivo, não lancei a app nem
  a bateria. Fechar: corrida com o modelo ausente, a ver `BRIDGE_DEATH kind=error` → `restart=1..N`.
- `[UNKNOWN]` **O desenho de `worker-parked` no painel** — o mapeamento de texto não existe; não li o que o
  `panel.js` pinta. Fechar: `--dump-dom` num worker parqueado.
- `[UNKNOWN]` **`BRIDGE_SILENT_LOAD_TIMEOUT`, `BRIDGE_RESTART_SUPPRESSED`, `WEBVIEW2_INIT_FAILED`,
  `PANEL_NAV_STALL`, `TAP_OPEN_TIMEOUT`, `model dir not found`** têm 0 ocorrências; são `[CODE]`, não campo.
  Fechar exige forçar cada um (modelo renomeado, porta CDP ocupada, WebView2 sem runtime) numa largada
  de lane escondida e ler a tag no log.
- `[UNKNOWN]` **Os 8 minutos de relógio estático** (2026-11-09 21:29→21:36) estão fora desta janela e
  `YOUTUBE_CLOCK_STATIC` tem 0 ocorrências. Fechar: `grep` no log arquivado dessa data.
- `[UNKNOWN]` **Não sei se a app do dono é `HEAD`** — o portão `_main/live-code-freshness-oracle.py
  --strict` existe e não o executei; sem `FRESH` todo o `[MEASURED]` é sobre código anterior ao processo.
  Fechar exige `python _main/live-code-freshness-oracle.py --strict` devolver `FRESH` sobre o pid vivo.
- `[UNKNOWN]` **`EXIT_KILLER_FIRED`/`EXIT_KILLER_ORPHAN`** não foram medidos, e a escalada dura só se prova
  com processo preso. Fechar: `_main/dead-app-exit-oracle.py` (não corrido, abre processo).
