# Lane BootFast — tempo ate' a PRIMEIRA legenda

Data: 2026-11-04. Worktree: `H:/sotto-wt/BootFast` (branch `lane/boot-fast`, HEAD `8007032`).
Ficheiros que esta lane podia tocar: `app/webview/sotto_webview.py` (regiao
`BRIDGE_SPAWN`/boot do worker/`WORKER_READY`), `worker/sotto_worker.py` (caminho de
boot/carga), mais UM oraculo novo. **O `app/webview/sotto_webview.py` nao foi tocado** — o
numero mostra por que (ver §3): o shell ja' esta' de pe' em ~2 s e nao ha' nada para cortar
antes do `ShowWindow`/hotkey.

## 0. A ORDEM, reformulada

O defeito medido pelo log do dono: `SHELL_STARTUP_STAGE` 09:57:24 -> primeira
`CAPTION_PAINT` 09:58:29 = **65 s** de app aberta sem legenda. A aceitacao dele: **legenda
ate' 3 s depois de a app estar de pe'**.

## 1. Instrumento (novo, e o entregavel que sobrevive)

`_main/time-to-first-caption-oracle.py` — le' o log VIVO, acha a ULTIMA
`SHELL_STARTUP_STAGE` (ou `--pid N`), acha a PRIMEIRA `CAPTION_PAINT` que **nao e' um
placeholder de estado** (`carregando modelo…`, `Starting worker…`), e imprime a diferenca
em ms + a tabela de fases. PASS so' abaixo de 3000 ms. Nao larga nada: nem app, nem janela,
nem dispositivo de audio, nem modelo — le' um ficheiro.

```
$ python _main/time-to-first-caption-oracle.py --log H:/sotto/_main/webview-run.log --pid 32540
run under test : shell pid=32540 started 2026-11-04 09:57:24.323
first caption  : 09:58:29.360  +65037 ms  text="audience"

  +ms   stage
  ----- ----
     98   BRIDGE_SPAWNED
   8616   WORKER_PROVIDERS
   8620   BRIDGE_LOAD_MS
  17388   STATUS_APPLIED capture-started
  62033   BRIDGE_METER                (primeiro bloco com blocks>=1)
  65014   CAPTION_IN
  65037   CAPTION_PAINT              <-- a queixa dele, reproduzida ao ms
   6252   YT_FRAME (fonte externa, nao somada)

limit          : 3000 ms (owner: a caption within 3 s of the app being up)
TIME-TO-FIRST-CAPTION VERDICT: FAIL        (rc=1)
```

O instrumento reproduz os 65 s da queixa dele a partir do ficheiro — 65037 ms.

Tres armadilhas que o proprio instrumento teve e que estao fechadas por teste:
1. o payload real escreve `"blocks":1.0` (JSON), nao `blocks=1.0` — a tabela saia com `-`
   mesmo com a linha no ficheiro;
2. uma cadeia `elif` fica PRESA na marca que falta: enquanto `BRIDGE_METER` nao chegava,
   `CAPTION_IN` e `YT_FRAME` nunca eram testados (o primeiro `YT_FRAME` do pid 32540 e'
   +6,2 s e a cadeia dizia +82,6 s). Sao `if` independentes agora, e o braco negativo
   `no-meter-marks-not-starved` reprova a cadeia (provado com uma copia mutada: `MISMATCH`,
   rc=1);
3. um `CAPTION_PAINT` de ESTADO nao e' uma legenda: aceita-lo daria PASS a uma app que
   nunca transcreveu nada.

Bateria (`_main/_audit-verify-all.cmd`, logo a seguir ao par do `youtube-land`, que e' o
precedente de "le' o log vivo"):

```
call :step always time-to-first-caption 0 "_main\time-to-first-caption-oracle.py;_main\webview-run.log" "%OUT%\time-to-first-caption.log" python _main\time-to-first-caption-oracle.py
call :skipped time-to-first-caption !STEP_RC! "%OUT%\time-to-first-caption.log" "TIME-TO-FIRST-CAPTION VERDICT: PASS" "TIME-TO-FIRST-CAPTION VERDICT: SKIPPED" "TIME-TO-FIRST-CAPTION VERDICT: SKIPPED"
call :step red-as-expected-time-to-first-caption 1 "_main\time-to-first-caption-oracle.py" "%OUT%\time-to-first-caption-neg.log" python _main\time-to-first-caption-oracle.py --neg-arm
call :expectred red-as-expected-time-to-first-caption !STEP_RC! "%OUT%\time-to-first-caption-neg.log" "NEG-ARM: PASS"
```

- `always`: a verdade esta' FORA dos ficheiros (a sessao viva), nunca em cache.
- `:skipped` (nao `:record`): sem legenda pintada o oraculo diz `VERDICT: SKIPPED` com
  rc=0 e o passo conta-se em `skipped=` — um skip NUNCA e' um portao que passou. Um log
  ABSENTE (worktree, maquina onde a app nunca correu) tambem e' SKIPPED rc=0, provado no
  braco negativo (`missing-log-skips`), porque `:skipped` le' rc!=0 como FALHA.
- uma medicao >= 3000 ms **nao** e' skip: rc=1 e o passo reprova. O numero e' a aceitacao.

## 2. Negativo (o instrumento julgado contra si proprio, 9/9)

```
$ python _main/time-to-first-caption-oracle.py --neg-arm
  green-1.2s                     rc=0 PASS      (want rc=0 PASS) ok
  red-9s                         rc=1 FAIL      (want rc=1 FAIL) ok
  red-at-3000ms                  rc=1 FAIL      (want rc=1 FAIL) ok
  stale-earlier-run-win          rc=1 FAIL      (want rc=1 FAIL) ok
  placeholder-is-not-a-caption   rc=0 SKIPPED   (want rc=0 SKIPPED) ok
  no-caption-yet                 rc=0 SKIPPED   (want rc=0 SKIPPED) ok
  no-meter-marks-not-starved     rc=0 PASS      (want rc=0 PASS) ok
  no-start-stamp                 rc=2 SEM DADOS (want rc=2 SEM DADOS) ok
  missing-log-skips              rc=0 SKIPPED   (want rc=0 SKIPPED) ok
NEG-ARM: PASS -- 9/9 cases
```

`red-9s` e' exactamente o caso que o ticket pede (log sintetico com a primeira legenda aos
9 s) e sai rc=1. `red-at-3000ms` fixa o limite: 3000 exactos NAO passa.

## 3. Onde estao os 65 s — medidos, nao opinados

Duas fontes, as duas com comando.

**(a) O log do dono** (§1). Decomposicao do pid 32540:

| fase | +ms | delta | o que e' |
|---|---|---|---|
| `BRIDGE_SPAWNED` | 98 | 98 | o worker foi largado 98 ms depois do shell |
| `BRIDGE_LOAD_MS` | 8 620 | 8 522 | spawn -> grafo carregado |
| `capture-started` | 17 388 | 8 768 | gate + escada de dispositivo + tap |
| `BRIDGE_METER` | 62 033 | 44 645 | **espera por audio** (a maquina estava calada) |
| `CAPTION_IN` | 65 014 | 2 981 | ~3 s de audio ate' o modelo fechar a primeira linha |
| `CAPTION_PAINT` | 65 037 | 23 | o overlay pintou |

O maior termo NAO e' o modelo: sao **44,6 s de maquina calada**. Nesse intervalo o worker
fez exactamente o que a cura de 2026-11-02 manda (`tap-silent-desktop`, 09:57:48.476:
nenhum endpoint a renderizar -> manter a tap em vez de reabrir clientes WASAPI), e o audio
so' apareceu quando o dispositivo foi rotacionado as 09:58:25. Um numero que se leia como
"a app demora 65 s a carregar" esta' errado.

**(b) Um boot do worker cronometrado, na worktree, sem dispositivo e sem janela**
(`SOTTO_FILE_TAP=worker/assets/sample1.flac`, cada linha de stdout carimbada na chegada,
`CREATE_NO_WINDOW`; modelo real, `--model H:/sotto/worker/models/...`):

```
$ python I:/cc-tmp/boot-timed.py I:/cc-tmp/wt-before.tsv worker/sotto_worker.py \
    --model H:/sotto/worker/models/nemotron-3.5-asr-ptbr-onnx-int4 --max-seconds 40
      0 ms  boot start
      2 ms  boot lang
    184 ms  model-loading
   5624 ms  boot providers
   5624 ms  model-loaded          load_s=5.44   (sess_encoder 5.32 / decoder 5.48 / joint 5.63)
   7335 ms  gate                  (+1711 ms = a construcao do og.Model segura o GIL)
   7413 ms  device
   7556 ms  capture-started
   9014 ms  primeira legenda      ("going")     -> 9,0 s
```

O mesmo `StreamAsr` com a maquina ociosa e o ficheiro em cache mede `load_s=1.47` (probe
isolado); no boot real mede 5,44 s. A diferenca e' EcoQoS
(`PROCESS_MODE_BACKGROUND_BEGIN`, a cura do "abrir ou fechar trava o PC") mais contencao
com o WebView2 do proprio shell. E o `BRIDGE_LOAD_MS` do shell (8,5-10,5 s) e' maior que o
boot isolado (5,6 s) porque o shell, no mesmo instante, esta' a carregar o painel — no
pid 42548 o `WEBVIEW_NAV done t=10094` chega 10,1 s.

**A crenca de "54 s de carga do modelo" esta' errada duas vezes**: o grafo leva 4,6-5,4 s
de trabalho do worker; os 8,5-10,5 s do `BRIDGE_LOAD_MS` incluem o arranque do
interpretador e a contencao com o shell; 54 s nao aparece em nenhum arranque desta sessao.

**O shell nao tem nada para cortar antes da janela**: no log do dono o painel nasce a
+69 ms, o hotkey `Alt+C` a +74 ms, o icon na tray a +136 ms, o worker e' largado a +85 ms
e a primeira navegacao (`WEBVIEW_NAV start`) a +1 329 ms. Por isso
`app/webview/sotto_webview.py` nao foi tocado.

## 4. A mudanca que eu tentei — e que medi PIOR, portanto NAO vai

Hipotese: `og.Model` (a construcao do front end) segura o GIL por toda a sua duracao e
estava ANTES da escada de dispositivos, enfileirando 1,7-3,4 s de trabalho de captura.
Mover `asr.start_frontend()` para junto do arranque da thread de ASR deixaria a escada e a
abertura do tap correrem primeiro. Mecanismo medido e confirmado:

```
LOAD_S 1.47                     (StreamAsr com maquina ociosa e ficheiro em cache)
LADDER_ALONE_S 1.79 (+peaks 0.50)          (device_candidates + leitura de picos)
FRONTEND_S 1.86  thread_start_returned_after_s 1.83   <-- o GIL: start() so' volta no fim
LADDER_UNDER_FRONTEND_S 2.25  (alone 2.30)            <-- a escada NAO e' penalizada
```

Implementada, compilada e medida em par intercalado na mesma seam (worktree, ficheiro,
mesma maquina, boots consecutivos):

| marca | ANTES (HEAD) | DEPOIS (patch) |
|---|---|---|
| `model-loaded` | 5 624 ms (load 5,44 s) | 4 802 ms (load 4,58 s) |
| `gate` | 7 335 ms | 4 802 ms |
| `capture-started` | 7 556 ms | **7 927 ms** |
| primeira legenda | **9 014 ms** | **10 199 ms** |

O patch moveu `capture-started` para 3,1 s depois de `model-loaded` (era 1,9 s) e a
primeira legenda ficou 1,2 s PIOR — com o boot a ser 16 % mais rapido na maquina (load
4,58 vs 5,44 s), portanto a regressao nao e' deriva da maquina. A "sobreposicao gratuita"
da escada com o `og.Model` existe isoladamente (2,25 vs 2,30 s), mas no boot real o que
acontece e' contencao: o `og.Model` passa a competir com a thread de ASR e o pump de audio,
e a construcao estica de 1,7 s para 3,1 s. **Revertido.** Nao entrego uma optimizacao que
so' mediu pior; o par intercalado fica aqui para ninguem repetir a ideia.

O que o ticket autoriza e que eu NAO implementei: um **preloader** (um processo que tem o
grafo quente e que o shell adopta). E' a unica rota para os 3 s (§6), e nao e' uma
reordenacao: o shell fala com o worker por `stdin`/`stdout` de um `Popen` que ele mesmo
larga e mata (`BRIDGE.stop`, `BRIDGE_SPAWNED pid=...`), portanto um worker que sobreviva
ao shell precisa de um canal novo (named pipe/socket) e de uma regra de posse — desenho,
nao corte. Meia implementacao disto parte a app de forma pior do que o defeito.

## 5. Nota de load (a coordenacao que o ticket exige)

Antes de tocar em qualquer coisa de carga: `write agent://LoadAutoResume-2`. Resposta
verbatim: *"No boot-path load gate from my lane. My owned symbols (do NOT edit):
`resume_catch_up()` and `_resume_gate()` ... Nothing in my lane gates boot loading, so the
pre-window boot work and caption paint path are yours."* Nada do caminho de boot foi
alterado por mim, portanto nao ha' colisao. Nao acrescentei portao de carga nenhum: "nunca
carregar o grafo com a maquina em carga alta" e' uma politica que nao e' minha para
inventar, e o `performance-gate.py` estava `GREEN` (commit 57,4 %) quando medi; o lease
`heavy` foi pedido (`id=a51543e3046246ebba2ea6148d11f413`, ttl 900 s, owner `BootFast`) e
**devolvido** (`released heavy lease ...`, `leases: heavy=0/1`).

## 6. O achado — explicito, como o ticket pede

**3000 ms e' IMPOSSIVEL neste box com o motor local frio.** O piso medido, com a maquina
calada e o modelo em cache:

    carga do grafo          4,6 - 5,4 s   (1,47 s so' com tudo quente)
    front end (og.Model)    1,7 - 3,4 s
    ~2 chunks de audio      1,0 - 3,0 s   para o modelo fechar a primeira linha
    ------------------------------------------------
    piso                    ~8 - 11 s     (medido: 9,0 s na seam do ficheiro)

Com a escada de dispositivo do caminho vivo (`capture-started` a +17,4 s no log dele) o
piso real de um arranque a frio e' ~13 s, e o log do dono mostra 65 s porque 44,6 s desses
foram maquina calada. Nenhuma reordenacao de codigo leva 13 s a 3 s: **so' um worker com o
grafo ja' quente (preloader / adopcao) pode.** Isto e' um achado, nao uma desculpa: a
aceitacao de 3 s e' uma meta de processo quente, e o instrumento passa a dizer o numero em
cada bateria para o dono poder decidir se quer o preloader.

O caminho que MAIS se aproxima dos 3 s hoje nao e' o motor local: e' a fonte externa. No
pid 42548 o primeiro `YT_FRAME` chega a **+4 482 ms** e no pid 32540 a **+6 252 ms** — o
YouTube ja' tinha texto antes de o grafo estar quente (e no pid 42548 nao pintou porque a
legenda ao vivo estava desligada: `CAPTION_WANTED_RESTORED on=false`, e a pintura foi
recusada com `YOUTUBE_TRACK_PAINT ... reason=no-caption-window-lang`). Essa rota pertence a'
lane YtSourceOnBoot/YtOneToOne (eu nao toquei `_youtube_cdp_source`, `_external_captions_youtube`
nem o preopen de CDP); fica o numero aqui porque e' o unico que pode chegar aos 3 s sem
preloader.

## 7. O que NAO consegui provar

- **O AFTER do caminho VIVO (dispositivo real).** Medir isso exige abrir os endpoints de
  audio do dono (loopback WASAPI) enquanto a app dele (pid 42548) esta' a correr; a regra e'
  `SOTTO_OWNER_AUDIO_OK=1`, que eu nao tenho, e o custo medido de churn de clientes WASAPI
  e' o "freeze" que ele reportou em 2026-11-02. Portanto nao ha' numero de AFTER na seam
  viva: o proximo arranque dele e' o AFTER, e o oraculo (passo da bateria) le'-o sozinho.
  `[INFERENCE]` A decomposicao viva (17,4 s ate' `capture-started`) e' o log dele, nao uma
  medicao minha.
- **O ganho/regressao do patch na seam viva.** Medido na seam do ficheiro e revertido por
  isso; na seam viva seria `[INFERENCE]` e eu nao entrego inferencia como resultado.
- **A ordem exacta dentro do `og.Model`.** `boot_prof_s` publicou a fase como ausente nos
  boots desta lane (`og_model` so' apareceu num probe isolado: 5,815 s) — nao sei se o
  publish perde a marca ou se o build acabou depois do publish; nao persegui porque nao
  muda a conclusao.
- **A duracao do `WEBVIEW_NAV` (2,0 s no pid 32540 vs 10,1 s no pid 42548)** e' contencao
  entre o shell e o worker; nao a atribui a nenhum dos dois sem medida.

## 8. Ficheiros (worktree `H:/sotto-wt/BootFast`)

```
 M _main/_audit-verify-all.cmd          (+18 linhas: o comentario com o porque + o par time-to-first-caption e o seu negativo)
?? _main/time-to-first-caption-oracle.py   (novo: o instrumento, ~430 linhas)
```

`worker/sotto_worker.py` e `app/webview/sotto_webview.py`: **inalterados** (§4 e §3).

Receipt: `H:/sotto/_main/receipt-20261104-boot-fast.md` (este ficheiro).

## 9. Comandos, verbatim

```
$ python -m py_compile _main/time-to-first-caption-oracle.py          -> COMPILE OK
$ python _main/time-to-first-caption-oracle.py --neg-arm              -> NEG-ARM: PASS -- 9/9 cases (rc=0)
$ python _main/time-to-first-caption-oracle.py --log H:/sotto/_main/webview-run.log --pid 32540
      -> +65037 ms, TIME-TO-FIRST-CAPTION VERDICT: FAIL (rc=1)
$ python _main/time-to-first-caption-oracle.py --log H:/sotto/_main/webview-run.log
      -> pid 42548, +461609 ms, FAIL (rc=1)   [a legenda ao vivo estava desligada; CAPTION_IN a +114191]
```
