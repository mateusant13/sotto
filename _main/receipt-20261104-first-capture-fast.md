# Lane FirstCaptureFast — a PRIMEIRA legenda, de 48 s para os segundos

Data: 2026-11-04. Worktree: `H:/sotto-wt/FirstCaptureFast` (branch `lane/first-capture-fast`,
HEAD de partida `62641ec`). Ficheiros desta lane: `worker/sotto_worker.py`,
`worker/wasapi_loopback.py`, `app/webview/sotto_webview.py` (SO' a funcao da politica de
morte/espera), `_main/first-capture-fast-oracle.py` (novo), `_main/_audit-verify-all.cmd` e
`AGENTS.md` (pin da bateria). `WorkerBridge`, `start_worker`, `revive_worker` e a ordem do
boot **nao foram tocados** — sao de outra lane.

## 0. O "antes", medido (o arranque dele, verbatim do `_main/webview-run.log`)

```
12:15:15.269  SHELL_STARTUP_STAGE pid=56116 stage=pre-lock
12:15:15.887  BRIDGE_SPAWNED pid=13904                        +0,6 s
12:15:27.263  WORKER gate
12:15:31.059  STATUS_APPLIED device / capture-started         +15,2 s   <- custo 1
12:15:34.368  BRIDGE_DEATH rc=3 kind=no-audio
              last="Worker finished on no-callback-blocks"              <- custo 2
12:15:49.377  BRIDGE_SPAWNED pid=56188                        +34,1 s   <- custo 3
12:16:01.781  BRIDGE_STATUS_HELD state="capture-started"
12:16:03.721  CAPTION_PAINT "the tip"                         +48,4 s   <- a queixa
```

O modelo carrega em 5,8 s e **nao** era o problema. Os 48,4 s eram tres custos empilhados,
todos ligados ao **endpoint errado**:

| # | custo | quanto | de onde veio |
|---|-------|--------|--------------|
| 1 | a primeira picagem foi `VoiceMeeter Input` (morto) | **15,2 s** | a escada oferecia por ordem *estatica*; a pergunta "quem toca AGORA?" so' existia na rotacao. E `device_candidates()` gastava 3,8 s a ativar um `IAudioClient` por endpoint (`gate` 12:15:27.263 -> `device` 12:15:31.059) para devolver um endpoint MORTO |
| 2 | a morte foi declarada tarde | **3,3 s** (31,059 -> 34,368) e o piso era a janela do desktop parado | `no-callback-blocks` so' decidia ao fim da janela, e as duas causas — candidato morto / maquina calada — eram indistinguiveis |
| 3 | a shell esperou 15 s por uma morte de DISPOSITIVO | **15,0 s** (34,368 -> 49,377) | `BRIDGE_RESTART reason=exit ladder=no-audio in_ms=15000`: o backoff de crash aplicado a um endpoint errado |

48,4 − (15,2 + 3,3 + 15,0) = 14,9 s de trabalho real (modelo + o primeiro bloco do caminho de
audio, que num endpoint bom entregou a legenda **1,94 s** depois de `capture-started`:
12:16:01.781 -> 12:16:03.721).

## 1. Custo 1 — a primeira picagem pergunta ao medidor VIVO

`worker/wasapi_loopback.py`: `live_endpoint_order()` (nova) enumera os endpoints de render ATIVOS
e le **so'** `IAudioMeterInformation` — **nenhum `IAudioClient` aberto**, devolvendo
`[{endpoint_id, name, meter_peak, is_default}]` ordenado por quem esta' a renderizar.
`live_render_peaks()` passa a ser uma vista dessa funcao (mesma assinatura, mesmo `{}` em falha).

`worker/sotto_worker.py`: rung A de `device_candidates()` usa `live_endpoint_order()` em vez de
`loopback_device_specs()`, e `main()` faz a primeira picagem ANTES de abrir o tap:

```python
if not wanted:
    signal_ranked_next(candidates, 0, tap_floor)   # rung C (`--device`) continua a ganhar
err("CAPTURE_FIRST_PICK chosen=... static_first=... moved=... probe_ms=N of=6 floor=...")
```

O custo do probe, medido nesta maquina agora (6 endpoints, so' medidores):

```
$ python -c "import sys,time; sys.path.insert(0,'worker'); import wasapi_loopback as w; \
             t=time.monotonic(); w.live_endpoint_order(); print((time.monotonic()-t)*1000)"
735 ms   (primeira leitura)   750 ms   (a seguir, cache quente)   6 endpoints
```

0,7 s de leitura compra o endpoint certo; os 3,8 s de ativacoes por endpoint desapareceram (o
`IAudioClient` do endpoint escolhido e' aberto por `WasapiLoopbackTap.__init__`, uma vez).

## 2. Custo 2 — `no-callback-blocks` depressa, sem confundir "calado" com "morto"

`first_block_decided()` ja' tinha o piso `TAP_FIRST_BLOCK_MAX_S = 2.0`; agora o piso e' aplicado
ao **primeiro** bloco e a decisao de zero-blocos pergunta ao medidor *qual das duas causas* e'
(`dead_first_block_plan()`, funcao PURA):

* sinal a sair noutro endpoint -> `action="rotate"` **no processo**, sem morrer nem recarregar
  1,9 GB de modelo (`TAP_DEAD_FAST ... action=rotate why=signal-elsewhere next=... peak=...`);
* nenhum endpoint a renderizar -> `action="wait"`: a regra do desktop parado fica **inteira**
  (`TAP_QUIET_DESKTOP ... keep-the-tap`, janela 12/24/48/60 s inalterada), e a pergunta re-arma
  quando a janela cresce (`window_ended` limpa `counters['quiet']`);
* medidor ilegivel (`{}`) -> `action="dead"` — "sem leitura" nunca e' "sem sinal", o
  comportamento anterior mantem-se.

O limite de 2 trocas no processo (`TAP_DEAD_SWITCH_MAX`) impede que uma escada partida se torne
um laco de recarga.

## 3. Custo 3 — morte por DISPOSITIVO nao espera 15 s

`app/webview/sotto_webview.py`, a funcao da politica (e SO' ela): `device_death_delay()`, pura e
testavel, chamada de dentro de `WorkerBridge._schedule_restart`:

```
kind=no-audio + ha' som a sair agora + < 2 trocas  ->  250 ms  (ladder=device-switch)
kind=no-audio + nada a renderizar                  ->  15 s    (why=nothing-is-rendering-a-switch-cannot-help)
kind=no-audio + orcamento de trocas gasto          ->  15 s    (why=device-switch-budget-spent)
rc=1/crash (kind != no-audio)                      ->  1 s -> 30 s  (backoff preservado)
```

Decisao publicado por escrito, sempre: `ENDPOINT_SWITCH reason=... ladder=... delay_ms=...
switch=N/2 dead=<endpoint> live=<endpoint> peak=... no_audio_restarts=...`. A leitura que
responde "trocar adianta?" e' `audio_playing.loudest()` (so' medidores, so' leitura). Uma corrida
que ja' deu legenda (`captions > 0`) recomeca o orcamento: e' um episodio novo.

## 4. O instrumento (o entregavel que sobrevive)

`_main/first-capture-fast-oracle.py` — executa as funcoes REAIS, incluindo o
`WorkerBridge._schedule_restart` real com um `threading.Timer` FALSO (nada e' lancado). 10 arms:

```
$ python _main/first-capture-fast-oracle.py
ARM 1-dead-first-pick-switches-fast                    PASS   (picagem move o vivo + 250 ms, nunca 15000)
ARM 2-live-first-pick-costs-one-read                   PASS   (slot 0 intacto, 1 leitura, probe_ms>=40)
ARM 3-device-death-restarts-in-250ms                   PASS   (_schedule_restart REAL)
ARM 4-device-switch-is-bounded                         PASS
ARM 5-quiet-machine-keeps-the-backoff                  PASS
ARM 6-crash-death-keeps-the-backoff                    PASS   (rc=1 -> 1000 ms, ladder=retry)
ARM 7-dead-deadline-2s-does-not-clip-a-live-endpoint    PASS   (1,94 s -> nao roda; 2,0 s -> roda)
ARM 8-desktop-quiet-is-not-a-dead-endpoint             PASS   (plan=wait + silent_desktop_hold 12/24 s)
ARM 9-signal-elsewhere-rotates-in-process              PASS
ARM 10-wiring                                          PASS
VERDICT: GREEN arms=10 fail=0      rc=0
```

`--neg-arm` muta uma COPIA de cada ficheiro em quatro defeitos e exige os quatro VERMELHOS:
espera do desktop removida (arm 8), piso de 60 s (arm 7), primeira picagem sem medidor (arm 1),
backoff de 15 s de volta na morte de dispositivo (arm 3). **rc=1 por desenho**:

```
NEG-ARM m1-a-espera-do-desktop-parado-removida                PASS (red=8-...)
NEG-ARM m2-o-piso-do-candidato-morto-volta-a-espera-inteira   PASS (red=7-...)
NEG-ARM m3-a-primeira-picagem-salta-o-medidor                 PASS (red=1-...,2-...)
NEG-ARM m4-o-backoff-de-15s-volta-para-a-morte-de-dispositivo  PASS (red=1-...,3-...)
NEG-ARM: PASS -- 4/4 mutante(s) apanhado(s)                 rc=1
```

O oraculo nao larga a app, nao abre dispositivo para escrita e nao silencia nada: a unica leitura
de dispositivo e' o medidor (`IAudioMeterInformation`), e a regra "nao abrir 12 clientes" do
`_main/tap-silent-desktop-oracle.py` fica respeitada (o `live_endpoint_order` nao abre
`IAudioClient` nenhum).

## 5. Ligacao na bateria + pin

`_main/_audit-verify-all.cmd`, logo depois do par `time-to-first-caption` (17 linhas):

```
call :step always first-capture-fast 0 "_main\first-capture-fast-oracle.py;worker\sotto_worker.py;app\webview\sotto_webview.py;worker\wasapi_loopback.py" "%OUT%\first-capture-fast.log" python _main\first-capture-fast-oracle.py
call :record first-capture-fast !STEP_RC!
call :step red-as-expected-first-capture-fast 1 "..." "%OUT%\first-capture-fast-neg.log" python _main\first-capture-fast-oracle.py --neg-arm
call :expectred red-as-expected-first-capture-fast !STEP_RC! "%OUT%\first-capture-fast-neg.log" "NEG-ARM: PASS"
```

As quatro linhas foram exercitadas num `cmd /c` (harness com os dois comandos reais):
`gate_rc=0 neg_rc=1 expectred_hastext_rc=0`. Os meta-oraculos da bateria, corridos:

```
battery-wiring  PASS  checks=7 fail=0   ligados=115 sem_passo=111 populacao=226  (`first-capture-fast` conta como ligado)
battery-class   PASS  arms=3 fail=0
battery-heavy-gate PASS
cobertura       PASS  34/34
agents-md-pins  PASS  2 pin(s) checked live, 0 failure(s)
```

Pin da bateria em `AGENTS.md` re-medido e reescrito (o ficheiro e' LF; a bateria e' CRLF e foi
escrita em binario, 0 bare LF):

```
_main\_audit-verify-all.cmd = 214451 B, 2661 CRLF / 0 bare LF
sha256 4FCFD951A8B79959D1D1C5325C8679929AB472330723266B4ED8977C8D81536B
```

## 6. O "depois" — o que fica medido e o que NAO fica

O que o codigo elimina do caminho critico, somado a partir da tabela do §0: 15,2 + 3,3 + 15,0 =
**33,5 s dos 48,4 s**. O que resta e' trabalho real: spawn (0,6 s) + carga do modelo (5,8 s) + a
leitura do medidor (0,74 s) + o primeiro bloco do caminho de audio (1,94 s, medido no endpoint
bom) ≈ **9 s**, e a troca em processo corta o pior caso (medidor falha, primeira janela cai no
endpoint errado) para 2,0 s + 250 ms em vez de 15 s + recarga de modelo.

**UNMEASURED (e e' dele):** os 9 s sao ARITMETICA sobre medidas reais, nao um arranque medido.
Um restart de verdade na sessao do dono — `CAPTION_PAINT` depois de `SHELL_STARTUP_STAGE`, lido
pelo `_main/time-to-first-caption-oracle.py` — e' o unico numero que fecha isto, e so' ele o pode
correr. Tambem nao medido aqui: a taxa de acerto do medidor numa maquina com VÁRIOS endpoints a
renderizar ao mesmo tempo (a leitura devolve peaks reais, mas a escolha entre dois que tocam nao
tem ainda um arranque do dono por tras).
