# RECEIPT — a cauda da legenda ao vivo (2026-11-04)

## O que estava errado

`CAPTION_APPLIED` era a unica medida de "quando o pixel mudou" e misturava
duas perguntas diferentes:

1. a `final` chega pelo `take_closed` SEM `tap_ms`, e o shell reusava o tap da
   ultima parcial → a idade saia do intervalo entre duas frases.
   MEDIDO (sessao do dono, 04:00-01:25, 18030 pinturas no log):
   `CAPTION_APPLIED ... kind=final aged_kind=hold-expired audio_ms=166615`
   para uma linha de 3 s; `CAPTION_LAG_STATS n=200 p50=634 p90=45402 over=109`.
2. a linha `final` entrava na serie do ecra, logo o p90 e o `over=` mediam a
   duracao das frases.

## O que foi medido depois de separar os canais

Sessao viva, 191 pinturas que MUDARAM o texto (a primeira aparicao):

    p50 = 195 ms   p90 = 1645 ms   <=400 ms = 54,5%

Bimodal, sem quase nada entre 400 e 1500 ms. O pico nos 1500 ms e' o relogio
`COMMIT_MAX_HOLD_MS` do PAINEL: o `LineFormer` so' ve' o fim da frase quando o
fragmento SEGUINTE chega, e o bloco que vem depois das ultimas palavras
decodifica VAZIO — `push` nunca corre, e a palavra nao provada fica a espera.

## A cura

`worker/silence_tail.py` decide quando o silencio PROVA a cauda (0,8 s = 1,5
blocos de 560 ms) e `LineFormer.publish_on_silence` publica o texto ACTUAL da
linha com `stable: true` — o que `app/panel/stable-words.js::wordsAreWhole` ja'
le'. A linha NAO fecha (`SENTENCE_GAP_S = 8.0` decide onde quebra), logo o
historico nao ganha linhas por pausa.

O instrumento: `age` deixou de ser fabricada (tap consumido por uma pintura) e a
`final` saiu da serie, com o nome `aged_kind=final-close` no log.

## Prova

- `_main/incomplete-word-oracle.py` 26/26 (4 arms novos: silencio curto nao
  publica, 0,9 s publica a linha inteira `stable`, um silencio publica uma vez,
  a linha continua aberta; controlo = a mesma funcao com o limiar em 99 s).
- `_main/caption-lag-budget-oracle.py` 13/13 arms, `--neg-arm` 9/9 mutantes
  apanhados (dois novos: tap reaproveitado, linha fechada contada).
- `_main/caption-lines-oracle.py` 13/13.
- Ponta a ponta no worker REAL, `--selftest --audio _main/live-sample-cable-input-90s.wav`:
  a cauda `PC` de `força luvas do` saiu como evento proprio publicado pelo
  silencio (31 eventos de legenda, `empty_chunks=32`).

## Portao estrutural (nao foi silenciado)

`_main/code-health-oracle.py` VERDICT FAIL, com os numeros:
`sotto_webview.py` 18599→18645 linhas (ja' estava 18637 no HEAD antes deste
trabalho) e `sotto_worker.py` 7356→7413 (a decisao vive em modulo novo
justamente para nao crescer mais; so' a chamada ficou no worker).
`shell_relaunch.py +43 B` e' anterior a este trabalho.

## O painel mostra a palavra (medido, 2026-11-04)

O evento que `publish_on_silence` emite passa pelo mesmo caminho do painel que
qualquer parcial. Executado o motor REAL em Node
(`caption-formulation.js::createEngine` + `stable-words.js::wrap`):

    ingest('hello wor', {stable:true, final:false}) -> wordsStable=true
      tailClosed=false  wordsAreWhole=true    <- a ultima palavra PINTA
    ingest('outra linha', {final:false})        -> wordsAreWhole=false
                                                  <- sem a promessa, segura

Logo a cura nao depende do relogio do painel: depende do sinal que o worker
passou a mandar no silencio.

## A bateria (2026-11-04, corrida oculta a partir da lane)

`_main\_audit-verify-all.cmd` -> **BATTERY-VERDICT: RED - 4 step(s) failed**,
com `failed: code-health=2 gitattributes-verify=1 strip-hot-reload=3
skip-verdict-guard=1`.

O `_main/_audit-verify/_battery-summary.txt` das **02:32** (antes deste
trabalho) tem a MESMA linha, com os mesmos rcs: nenhuma falha nova. As quatro
sao anteriores: `code-health` e' o ratchet destes ficheiros (medido acima),
`gitattributes-verify` diverge em 26 ficheiros de `_main/_falsify/` (nenhum
deles destas mudancas), `strip-hot-reload` falha nas arms C/E do
`WorkerReloadPolicy` e `skip-verdict-guard` le' dois logs do proprio battery.

A corrida so' foi possivel depois de corrigir `_main/hidden-launch.py`: `run()`
e `popen()` passavam `creationflags=` DUAS vezes e morriam com
`TypeError: got multiple values for keyword argument 'creationflags'` ANTES de
arrancar o filho. Medido: `run(['cmd','/c',r'_main\_audit-verify-all.cmd'])`
devolvia o Traceback e nenhum passo corria; agora devolve `rc=0` com a saida do
filho. O portao `console-window-gate.py` que o AGENTS.md nomeia **nao existe
nesta arvore** (o `battery-wiring-oracle` nao o acusa porque o passo esta'
`record`), logo a bandeira nunca foi conferida por execucao.

## O helper ganhou o portao que faltava (medido, 2026-11-04 06:0x)

O paragrafo acima dizia o essencial e parava aí: `hidden-launch.py` foi
corrigido e a bateria correu, mas **nada julgava o helper por execucao**. A
bandeira existia (duas vezes) e o `Popen` morria -- um portao de TEXTO veria a
bandeira presente e passaria.

`_main/hidden-launch-oracle.py`, quatro arms, cada um a julgar o EFEITO no
sistema operativo:

|arm|o que exige|medido|
|---|---|---|
|`run()`|`GetConsoleWindow()==0` no filho, com a saida de volta|`hwnd=0 visible=False`|
|`popen()`|o mesmo pelo outro caminho|`hwnd=0 visible=False`|
|CENSO|nenhuma janela de consola VISIVEL na arvore do filho, por `EnumWindows`|`amostras=16 janelas=[]`|
|DURACAO|`run` espera: 3 s de filho => >=3 s|`wall=3.10s out='DONE'`|

```
hidden-launch-oracle: 4 PASS / 0 FAIL (4 arms)
```

O arm do CENSO nasceu com **duas** formas de mentir, as duas fechadas com a
medicao ao lado: uma excepcao dentro da thread deixava `seen == []` e o arm
verde (por isso o `samples > 0` e' condicao do PASS -- medido `amostras=0` e
RED quando a thread morria); e contar TODAS as janelas de consola da maquina
apanhava as `PseudoConsoleWindow` do proprio terminal do harness (pids 25924 e
31660), por isso o censo filtra pela ARVORE do filho.

O controle de `GetConsoleWindow()` **nao serve nesta maquina** e isso esta'
declarado no ficheiro: sem a bandeira o filho TAMBEM devolve `hwnd=0` quando o
pai nao tem consola (este harness nao tem) -- um arm que nao consegue ficar
vermelho nao e' uma afirmacao, e fica o censo no lugar dele.

**Braco negativo** (`--neg-arm`): repoe o `TypeError` numa COPIA do modulo (o
`creationflags=` outra vez no `Popen`) e exige as quatro arms vermelhas com
`rc=1` -- medido `4 / 4` -- e a frase `NEG-ARM PASS` no log, que e' a que o
`:expectred` da bateria procura.

**Fiacao:** dois passos novos na `_main/_audit-verify-all.cmd` (`hidden-launch`
e `red-as-expected-hidden-launch`), o pin re-medido (**190395 B**, **2389
CRLF**, sha256 `10A533CEC403E8AB3C2CAB69B7016CD71C11EC8F9A84FF3EF109D78704EC7969`)
e o `agents-md-pins-oracle` PASS. `battery-wiring` conta **97 ligados**
(tecto 124) e `battery-class` PASS: nenhum dos dois e' `always` a largar a app.

**O que o `:expectred` apanhou na primeira corrida, e vale o registo:** o
oraculo imprimia `NEG-ARM: PASS` (com dois pontos) e a bateria procura
`NEG-ARM PASS` -- o passo apareceu em `failed: red-as-expected-hidden-launch=1`
com o rc certo. A frase passou a `NEG-ARM PASS:` a partir do oraculo, nao do
`.cmd`: a convencao da casa e' a do `.cmd`.

## O feed que gritava sem pagina (medido e curado, 2026-11-04 06:3x)

Instancia propria escondida (pid 42340, 02:48:14) mostrou o defeito ao vivo:

```
02:48:24 WEBVIEW2_INIT_FAILED error=(0x80010108) RPC_E_DISCONNECTED
02:48:38 CAPTION_IN ... text="desse doinheiro vai ficar ali no cantinho"
02:48:38..02:49:24  WARN POSTED_CALLABLE_FAILED fn=_run
                    AttributeError: 'NoneType' object has no attribute 'ExecuteScriptAsync'
```

`grep -c POSTED_CALLABLE_FAILED` = **541** em ~60 s (uma por amostra do
medidor), com a fonte do YouTube a **chegar** e a nunca poder ser pintada. O
`emit` e o `exec_js_post` ja' declaravam que o pipeline de legendas arranca
ANTES do WebView2, de proposito; o feed de `stats` era o irmao sem a guarda.

A cura, em `emit_async._run` (o pop do latch FIRST, para o feed nao parar):

|antes|depois|
|---|---|
|um `WARN` por amostra, 541/min, com excepcao a atravessar o `Invoke`|UMA linha `EMIT_ASYNC_PREWEBVIEW kind=… reason=no-core`, e o payload sai do latch (a proxima amostra reabre)|

`_main/emit-prewebview-oracle.py` corre o `emit_async` REAL (stub de `System`,
que este interprete nao tem: `ModuleNotFoundError: No module named 'System'`,
medido) e julga tres coisas:

```
[PASS] 50 pushes sem pagina: UMA linha, zero excepcoes   linhas_EMIT_ASYNC_PREWEBVIEW=1
[PASS] com pagina o feed NAO pode ser engolido           scripts=5 ultimo=window.__sotto_emit("stats","{\"n\": 4}")
[PASS] depois de a pagina existir o mesmo kind volta a postar   scripts_depois=1 (antes=0)
emit-prewebview-oracle: 3 PASS / 0 FAIL (3 arms)
```

`--neg-arm`: desliga a CONDICAO numa COPIA (trocar a linha por `pass` deixava o
corpo do `if` sem pai -- `IndentationError`, medido) e exige a arm A vermelha:
`excepcao="AttributeError: 'NoneType' object has no attribute 'Invoke'"`
`linhas_EMIT_ASYNC_PREWEBVIEW=0`, `NEG-ARM PASS: 1 de 3 arm(s) vermelha(s)`,
rc=1. Fiacao: dois passos na bateria (`emit-prewebview` +
`red-as-expected-emit-prewebview`), pin re-medido, `battery-wiring` **98
ligados** (tecto 124).

## Verificacao viva da app (2026-11-04, 02:54)

`_main/sotto-relaunch.py --relaunch --tag emit-prewebview-fix` -- a instancia
anterior (pid 29272) estava em codigo anterior ao dia. Depois:

|o que|numero|
|---|---|
|`live-code-freshness --strict`|**FRESH** `sha256=F53F8977E99C` == disco|
|mutex|`pid 46264 GANHOU a mutex`; saude `hotkey:true tray:true webview2_failed:false`|
|arranque escondido|`PANEL_VISIBILITY_AT_STARTUP visible=false`|
|WebView2 -> pagina do painel|`WEBVIEW_NAV dom t=1609` / `dom t=1813` / `done t=1828` (**1,8 s**)|
|worker|`BRIDGE_SPAWNED pid=35904` + `BRIDGE_LOAD_MS ms=10641`|
|spam do feed|`POSTED_CALLABLE_FAILED` desde o arranque = **0**|
|`UI_THREAD_STALL`|**0**|

O que **nao** pode ser medido nesta instancia: a legenda PINTADA. A fonte do
YouTube reporta `YOUTUBE_TICK_MS ... vid='' rows=? why=''` -- nao ha aba a
tocar -- e nao ha audio a entrar, logo `CAPTION_IN` = 0. Na instancia anterior
o mesmo caminho entregou texto real (`CAPTION_IN` as 02:48:38, verbatim acima),
e a pintura (`CAPTION_APPLIED count=200`) tem a sua medicao na sessao do dono
(01:25:39). Uma lane que force a pintura precisa de abrir um video ou de um
endpoint de audio -- as duas coisas sao dele, nao minhas.

## A bateria na corrida definitiva (2026-11-04 06:0x)

```
steps=248 gate=133 control=8 skipped=15 expect-red=92 missing=0 cached=80 failed=4
failed:  code-health=2 gitattributes-verify=1 strip-hot-reload=3 skip-verdict-guard=1
BATTERY-VERDICT: RED - 4 step(s) failed
```

**Duração: 644 s de parede** (`timeout=2400`, corrida oculta por
`_main/hidden-launch.py`: `cmd /c _main\_audit-verify-all.cmd`). A corrida
anterior de hoje, com os MESMOS quatro vermelhos e dois passos menos, foi
**426 s** -- a diferenca e' a app viva a carregar o worker durante a corrida
mais os quatro passos novos, nao um preguico novo. O passo `hidden-launch` e o
seu `red-as-expected` passaram; o mesmo para `emit-prewebview`.

Os quatro vermelhos sao ANTERIORES a este trabalho e estao nomeados:
`code-health` e' o ratchet (`app/webview/sotto_webview.py` 990 345 -> 994 502 B
e `worker/sotto_worker.py` 394 856 -> 397 645 B; parte do primeiro e' minha --
~1,4 KB pelo guarda que tirou 541 linhas de WARN por minuto -- e o resto vem
das mudancas ja' commitadas hoje), `gitattributes-verify` diverge em ficheiros
de `_main/_falsify/` que nao toco, `strip-hot-reload` falha as arms C/E do
`WorkerReloadPolicy` e `skip-verdict-guard` le' dois logs da propria bateria.
**O baseline do ratchet e' do dono** (`--update` diz "so com o dono de acordo"),
por isso ele fica vermelho e escrito, nao movido por mim.

## A cadeia viva medida ponta a ponta, de um FICHEIRO (2026-11-04 03:11)

`SOTTO_FILE_TAP=H:\sotto\_main\pt-br-sample.wav` + `sotto-relaunch.py --relaunch`:
o worker da app alimentado por um WAV (22050 Hz, 15,0 s), **sem abrir
endpoint nenhum** -- nada foi tocado no áudio do dono.

```
steps  # pid 48180, FRESH (sha256=EBBBFF9BB4C9 == disco)
CAPTION_IN             27     "Radio anunciou que aponte sobre o rio..."
CAPTION_PAINT_LAG      24
  audio->paint (ms)    n=24  p50=115  p90=268  max=1294   (budget 1500)
  queue      (ms)      n=24  p50=0    p90=2    max=80
  source age (ms)      n=26  p50=81   p90=182  max=1259
over=true               0
POSTED_CALLABLE_FAILED  0
EMIT_ASYNC_PREWEBVIEW   0
UI_THREAD_STALL         0
```

Isso é a aceitação do dono em número: a legenda nasce **115 ms** (mediana) e
**268 ms** (p90) depois do áudio, com o orçamento de 1500 ms nunca estourado.
O `CAPTION_APPLIED` = 3 é o contador do histórico (só a linha que o worker
FECHOU entra), coerente com 15 s de amostra.

A app voltou ao modo normal em seguida (`--tag back-to-device-ladder`), para
não ficar presa na tap de ficheiro: pid 50768, FRESH, `webview2_failed=false`,
`CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s` (sem fonte, como deve).
