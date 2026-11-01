# O stall do bridge: `exec_js TIMEOUT after 10.0s`

Lane `lane/goal-bridge`, worktree `H:/sotto-wt/goal-bridge`, base `bcc9778`.
Instrumentos: `_main/bridge-census.py`, `_main/bridge-stall-probe.py`,
`_main/bridge-caption-feeder.py`. Nenhum deles e' carregado sem
`SOTTO_BRIDGE_CENSUS=1`.

## (a) O defeito, no log do dono

```
$ grep -c "exec_js TIMEOUT" _main/webview-run.log
526          # 515 as 10:47; a app do dono continuou a estourar durante esta sessao
$ grep -c "exec_js STALL"   _main/webview-run.log
2
$ grep -c "STATUS_APPLIED"        _main/webview-run.log ; grep -c PLACEHOLDER_APPLIED ...
16056                             ; 4823        ; 43283 BRIDGE_CAPTION_SENT
```

A 10 s por estouro, sao **5260 s (87,7 min)** de uma thread parada -- e a thread
que estoura e' a que carrega as legendas. Os scripts que estouram, por forma:

```
261  (() => {  const txt = (el) => ...        # leitura de diagnostico
 29  (() => {  const title = ""; const body = ""; const kind = "busy";   # placeholder
 11  window.__sotto_emit("status","{\"text\": \"boot\", ...
 10  window.__sotto_emit("status","{\"text\": \"device-rotated (flat)\", ...
  8  window.__sotto_emit("geometry","{\"workX\": 0, ...
```

Por dia: `2026-10-16 275`, `2026-10-15 191`, `2026-11-01 28`, `2026-10-19 25`.

A linha que o dono via nao diz ONDE o tempo foi. Ha' tres donos possiveis e dois
exigem correccoes opostas, e `py-spy dump` esta' NEGADO nesta maquina
(`os error 5`, medido 2026-11-01). Por isso o censo tira as stacks de dentro do
processo: `sys._current_frames()` no instante em que o orcamento estoura.

## (b) O probe

`_main/bridge-stall-probe.py` arranca uma instancia **privada**: `--mutex-name`
propria (a do dono fica intocada), `--log` proprio em `I:\cc-tmp`, token de um
processo `high` (`_main/launch-as-token.py`, porque um filho desta pane mede
`WEBVIEW2_INIT_FAILED 0x80010108`), `--no-tray --no-lazy --no-self-relaunch`.
Nunca passa `--show`: nada aparece na tela do dono.

O trafego vem de `_main/bridge-caption-feeder.py` (`--worker`), que escreve as
MESMAS linhas de `worker/sotto_worker.py`: legenda a 300 ms (`emit_async`),
status a 4 s (`emit`, sincrono na arvore "before") e meter a 1 s. O microfone
desta maquina esta' mudo (`BRIDGE_STATUS_NOAUDIO state="silent-device"`),
portanto uma instancia real mediria um sistema OCIOSO.

Dois detalhes que o primeiro run ensinou, e que estao escritos no probe como
codigo: `--exit-after` e' um FLAG DE MEDICAO, portanto o shell recusa o worker
sozinho (`WORKER_AUTOSTART=declined reason=measurement-flag(--exit-after)`,
medido: zero legendas) -- daí `--with-worker`; e com o gate lazy ligado nao ha'
pagina nenhuma para receber um `emit` (`PANEL_LAZY_GATE_ARMED registered=5` e
depois nada) -- daí `--no-lazy`.

## (c) ANTES -- 300 s, 42 estouros, 42 vezes a MESMA assinatura

```
$ python _main/bridge-stall-probe.py --run --seconds 300 --tag before300
DONE=True log_bytes=...
  exec_js_timeout   42
  exec_js_stall     0
  ui_thread_stall   0
  census_on         1
  captions          346
```

Cada estouro, tabulado (42 linhas `BRIDGE_CENSUS kind="timeout"`):

```
status          {'WaitingForActivation': 42}      # o task NUNCA arrancou
continuation    {'unset': 42}                     # o _complete nunca correu
marshal_ms      {'0.0': 37, '16.0': 3, '15.0': 2} # o UI thread correu-o JA'
budget_ms       {'10000.0': 42}
task_ms         10000.0 .. 10125.0                # o orcamento inteiro, sem resposta
gil_gap_ms max  141.0                             # o GIL nunca esteve preso
```

E 7 chamadas que RESPONDERAM, tarde (`BRIDGE_CENSUS kind="slow"`), com
`task_ms` = **7266, 8469, 5265, 2078, 1265, 1125, 1016 ms**. O task nao esta'
morto: esta' LENTO. E' a diferenca entre um canal partido e um canal estrangulado.

O censo de threads do primeiro estouro (`11:03:14.989`, verbatim):

```
BRIDGE_CENSUS kind="timeout" script="window.__sotto_emit(\"status\",\"{\\\"text\\\": \\\"capture-started\\\", \\\"kind\\\": \\\"busy\\\"}\")" budget_ms=10000.0 marshal_ms=0.0 task_ms=10016.0 elapsed_ms=10016.0 status="WaitingForActivation" continuation="unset" gil_gap_ms=78.0 gil_gap_at="11:03:13.281" calls=20 answered=19 noanswer=1 uptime_s=38.9

BRIDGE_CENSUS_THREAD name="sotto-worker-stdout"  where=bridge-census.py:221:threads<-...:no_answer<-sotto_webview.py:8028:exec_js
BRIDGE_CENSUS_THREAD name="MainThread"           where=winforms.py:834:create_window<-__init__.py:303:start<-sotto_webview.py:15806:main
BRIDGE_CENSUS_THREAD name="Thread-231 (_call)"   where=threading.py:327:wait<-threading.py:479:acquire<-edgechromium.py:160:evaluate_js<-winforms.py:450:evaluate_js
BRIDGE_CENSUS_THREAD name="Thread-230 (_call)"   where=...:edgechromium.py:160:evaluate_js<-winforms.py:450:evaluate_js
BRIDGE_CENSUS_THREAD name="Thread-229"           where=threading.py:331:wait<-threading.py:629:wait
   ... mais SEIS threads `Thread-NNN (_call)`, todas em edgechromium.py:160:evaluate_js
BRIDGE_CENSUS_THREAD name="sotto-log"            where=sotto_webview.py:1264:_log_writer<-threading.py:982:run
BRIDGE_CENSUS_THREAD name="sotto-hotkey-panels"  where=sotto_webview.py:4024:run
```

A thread que estoura e' `sotto-worker-stdout` -- o pump que le' o stdout do
worker, o mesmo que carrega as legendas. O `MainThread` esta' no message loop do
WinForms (`create_window`, onde vive o `Application.Run`).

## (d) A causa, nomeada, e os quatro candidatos refutados

**Causa: o caminho do `emit` esperava por um `Task` que o renderer do WebView2
serve tarde (1,0-8,5 s medidos) ou nao serve de todo, e a resposta nao era usada
por ninguem.** Uma notificacao pagava o orcamento inteiro de 10 s.

| candidato | veredicto | prova |
|---|---|---|
| (a) pool de threads do bridge esgotado por um `js_bridge_call` sem resposta | **consequencia, nao causa** | `js_bridge_call` nao tem pool: `util.py:336` faz `Thread(target=_call)` -- uma thread por chamada, sem tecto. As oito `_call` do censo estao presas em `edgechromium.py:160` (`semaphore.acquire()`), a espera pela resposta `evaluate_js` que so' e' libertada por uma continuacao agendada no **UI scheduler** (`edgechromium.py:152-156`). Ficam presas porque o MESMO task nao completa. Mas nenhuma delas segura o shell 10 s: quem espera 10 s e' o nosso `exec_js`. |
| (b) um `Promise` de JS que nunca resolve | **refutado** | `ExecuteScriptAsync` nao espera promises (medido 2026-10-06, registado em `exec_js`). E o censo diz mais: `status=WaitingForActivation` significa que o task nunca ARRANCOU -- nao houve JS nenhum a correr para criar promise. |
| (c) UI thread bloqueado por um `wait()` no caminho do emit | **refutado** | `marshal_ms=0.0` em 37 de 42: o UI thread correu o callable imediatamente. `UI_THREAD_STALL` = **0** no run inteiro e **2** em 19 dias de log, contra 526 `TIMEOUT`. `gil_gap_ms` max 141 ms. |
| (d) o host do WebView2 a ser ceifado (`RPC_E_DISCONNECTED`) | **refutado neste estouro** | um host morto FAZ FALHAR os tasks (`IsFaulted` + `RPC_E_DISCONNECTED`); estes ficam `WaitingForActivation` para sempre, e o processo mantem o pid e as threads. As 7 respostas tardias (`task_ms` 1016-8469) provam que o renderer estava vivo e a atrasar-se. |

A camada de baixo (porque e' que o renderer serve tarde) tem uma leitura
consistente nos dados: a janela do painel esta' **escondida** em todos estes
estouros (`PANEL_SHOW_REFUSED ... visible=false`, e a janela so' mapeia no Alt+C),
e o Chromium estrangula um renderer oculto. O repo ja' tinha esta medicao escrita
noutro sitio (`PAINT_ACK_TIMEOUT_MS`: *"uma janela ESCONDIDA e' travada pelo
compositor nesta maquina"*). **Nao e' o que se corrige aqui:** o shell nao pode
depender do estado de visibilidade do renderer para entregar um status, e o custo
tem de ser zero ou uma linha de log.

## (e) A correcao

`app/webview/sotto_webview.py`, dentro da regiao do bridge:

1. `emit(kind, payload)` deixa de ser um round trip. As TRES chamadas do produto
   -- `status` (`send_status`, do pump do worker), `geometry` (`send_geometry`,
   da thread da hotkey) e `external-caption` (da thread do YouTube) -- descartam
   o valor de retorno: sao notificacoes. Passam a `emit_nowait` -> `_post`
   (`BeginInvoke`), que nao tem orcamento nenhum para estourar. Quando o post
   nao entra (form ainda nao existe) sai `EMIT_DROPPED kind=... reason=no-form`.
2. `apply_panel_state` deixa de esperar pela ESCRITA do placeholder. O valor
   lido servia para UMA linha de log (`PLACEHOLDER_APPLIED title=`), e custava
   ate' 10 s do pump por status (29 dos 526 estouros sao este script). A linha
   mantem a grafia e passa a dizer o que se ESCREVEU (`posted=true`); um post
   recusado e' `PLACEHOLDER_DROPPED`, nunca silencio.
3. O instrumento: `exec_js` passou a guardar o `Task` em `box['task']` e a
   escrever `BRIDGE_CENSUS`/`BRIDGE_CENSUS_THREAD` no estouro. E' o que faz um
   estouro futuro ser um diagnostico em vez de um numero.

O que NAO mudou, de proposito: o orcamento por omissao de `exec_js` continua
10 s para LEITURAS (`BRIDGE_PROBE`, `PANEL_V2_INJECT`, `--dump-dom`), porque
baixa-lo mudaria o comportamento dos oraculos de outras lanes e nao e' o
defeito. Depois desta mudanca nenhum caminho que o dono sente espera pelo
renderer: legenda (`emit_async`), status, geometria, placeholder e a janela da
legenda (`_post` com trava) -- todos postam.

## (f) DEPOIS -- 600 s, o mesmo probe, a mesma instancia privada

```
$ python _main/bridge-stall-probe.py --run --seconds 600 --tag after600
LAUNCH tree=H:/sotto-wt/goal-bridge log=I:\cc-tmp\bridge-after600.log
  exec_js_timeout  0        <- a aceitacao
  exec_js_stall    0
  ui_thread_stall  0
  census_on        1
  captions         1875
  reaped           []

$ grep -c "exec_js TIMEOUT"      I:/cc-tmp/bridge-after600.log   -> 0
$ grep -c "BRIDGE_CENSUS kind"   I:/cc-tmp/bridge-after600.log   -> 0   # nem estouro nem lento
$ grep -c "EMIT_DROPPED"         I:/cc-tmp/bridge-after600.log   -> 0
$ grep -c "PLACEHOLDER_DROPPED"  I:/cc-tmp/bridge-after600.log   -> 0
$ grep -c "STATUS_APPLIED"       I:/cc-tmp/bridge-after600.log   -> 1094
$ tail -1                        I:/cc-tmp/bridge-after600.log
   ... SHELL_EXIT rc=0 reason=requested statsPushes=0 statsReplies=25 meterPushes=608
```

O primeiro (e unico) resumo do censo no run inteiro:

```
BRIDGE_CENSUS_SUMMARY calls=3 answered=1 noanswer=0 max_marshal_ms=16.0 max_task_ms=16.0 gil_gap_ms=0.0
```

(o resumo sai na primeira resposta e a cada 250; com o caminho das notificacoes
fora do `exec_js`, houve tao poucas chamadas que so' a primeira linha saiu --
**tres** chamadas com o censo ja' ligado, contra `calls=20` aos 38,9 s no braco
"antes", onde cada status custava duas.)

| medida, mesmo probe, mesma instancia privada | ANTES (300 s) | DEPOIS (600 s) |
|---|---|---|
| `exec_js TIMEOUT after 10.0s` | **42** | **0** |
| `exec_js STALL` / `UI_THREAD_STALL` | 0 / 0 | 0 / 0 |
| legendas entregues (`BRIDGE_CAPTION_SENT`) | 346 (**1,15/s**) | 1875 (**3,13/s**) |
| `status=WaitingForActivation` no censo | 42 de 42 | 0 |
| chamadas `exec_js` com censo ligado | 20 aos 38,9 s | 3 no total |
| `EMIT_DROPPED` / `PLACEHOLDER_DROPPED` | 0 / 0 | 0 / 0 |

A taxa de legendas e' o segundo veredicto, e nao estava no pedido: no braco
"antes" o pump so' entregou 1,15 legenda/s porque passou o run preso em blocos de
10 s (42 estouros x 10 s); depois entrega 3,13/s, que e' o ritmo a que o feeder
escreve (300 ms). O canal deixou de perder tempo, nao apenas de escrever uma
linha de erro.

**Aceitacao da lane:**

```
$ python -m py_compile app/webview/sotto_webview.py        -> rc=0
$ SOTTO_POV_TAG=lane-bridge python _main/pov-selftest.py --run
   SELFTEST step=1-strip-cold posted=true seen=true screen=(True, 'strip')  latency_ms=63.0
   SELFTEST step=2-hidden     posted=true seen=true screen=(False, 'strip') latency_ms=47.0
   SELFTEST step=3-panel      posted=true seen=true screen=(True, 'side')   latency_ms=31.0
   SELFTEST step=4-hidden     posted=true seen=true screen=(False, 'side')  latency_ms=94.0
   SELFTEST arm=5-ten presses observed == expected (10 de 10)
   SELFTEST step=6-live       posted=true seen=true screen=(False, 'strip') latency_ms=16.0
   SELFTEST focus_stolen=false  broken=false  first_show_ms=63.0 first_show_slow=false budget_ms=1500
   SELFTEST rc=0
```

O caminho que esta lane NAO possui (hotkey, paint, strip/side) mede o mesmo que
antes: `<1 s` na primeira exibicao e o foco do dono intocado. O `emit` postado
nao mexeu na sequencia nem na latencia do show.



## (g) Reproduzir

```
git worktree add -b lane/goal-bridge H:/sotto-wt/goal-bridge bcc9778
python -m py_compile app/webview/sotto_webview.py

# ANTES (a arvore sem o item (e)): 300 s
python _main/bridge-stall-probe.py --run --seconds 300 --tag before300

# DEPOIS: 600 s
python _main/bridge-stall-probe.py --run --seconds 600 --tag after600

# a instancia e' privada e morre no fim; se sobreviver, o probe mata-a pela
# identidade do `--mutex-name` (nunca por nome de processo)
```

O probe repoe o que a instancia escreve NA ARVORE (`_main/panel-visibility.json`
e `_main/panel-state.<mutex>.json`): medido 2026-11-01, um run deixou o repo
sujo, e um instrumento que suja o repo faz o proximo leitor achar que o produto
mudou. Imprime `tree_artifacts={'visibility': 'restored'|'unchanged', ...}`.

`--burn N` existe para o braco de CARGA (N processos a CPU, prioridade
BELOW_NORMAL, filhos do probe, mortos com ele). Nao foi preciso: os 42 estouros
do braco "antes" sairam sem carga nenhuma, na instancia privada, com a pagina
carregada e o painel escondido -- que e' o estado de producao do dono.
