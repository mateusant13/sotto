# Receipt — 2026-11-04 — o gate de conteudo nao lia a resposta

Lane `PanelContentGate` · worktree `H:/sotto-wt/PanelContentGate` · branch `lane/panel-content-gate`
Ficheiros: `app/webview/sotto_webview.py` (`CONTENT_GATE_JS`, constantes, `gate_answer_payload`,
`gate_verdict`, `gate_should_retry`, `gate_probe`, `content_gate`, os tres `PANEL_SHOWN`),
`_main/paint-live-show-oracle.py`, novo instrumento `_main/content-gate-answer-probe.py`.

## A lei do dono, verbatim

> *"nada, literalmente nada, deve ter bug de render. o painel dar show, nao deve carregar o
> background e mostrar, e depois carregar a ui ou algo assim. isso e inaceitavel."*

## O sintoma, verbatim do log do dono (`_main/webview-run.log`)

```
12:15:43.542 PANEL_CONTENT surface=strip ack=false applied="None" style=false sized=false size=0x0 head="" vis= wait_ms=0.0 why=bad-answer order=before-map reason=hotkey-cycle-strip timeout_ms=250.0
12:51:45.143 PANEL_CONTENT surface=strip ack=false applied="None" style=false sized=false size=0x0 head="" vis= wait_ms=16.0 why=bad-answer order=before-map reason=hotkey-cycle-strip timeout_ms=250.0
12:51:45.180 PANEL_SHOWN ... content_ack=false content_wait_ms=16.0 paint_ack=true wait_ms=31.0
```

O oraculo `_main/paint-live-show-oracle.py` estava VERMELHO em cima disto, e o vermelho era correcto.
O que faltava era o PORQUE: `why=bad-answer` nao diz nada.

## Os tres candidatos, e qual o replay provou

Instrumento: `_main/content-gate-answer-probe.py` (copia o `app/panel/panel.html` real e os ficheiros
que ele referencia para `$TMPDIR`, acrescenta-lhe UM script externo — a CSP e' `script-src 'self'` —,
avalia o `CONTENT_GATE_JS` e publica `typeof`, o valor e `JSON.stringify(valor)`, que e' o contrato do
`ExecuteScriptAsync`; Edge em `--headless=new`, sem janela).

| candidato | veredicto | evidencia |
|---|---|---|
| (a) a pagina ainda nao definiu a funcao (string = `TypeError: ... is not a function`) | **REFUTADO** | o script e' auto-contido (nao chama funcao da pagina; `SottoSurfaces` e' opcional e tem fallback); o valor medido COMECA por `{` e o `error` dentro dele e `""` |
| (b) outra excepcao JS (a string seria a mensagem) | **REFUTADO** | mesma medida: `{"surface":"strip","style":true,...}` com `error:""`; um `throw` apanhado pelo `catch` do gate sairia como JSON com `error` nao vazio, e um throw FORA do try nao existe (o corpo esta todo dentro dele) |
| (c) `exec_js` devolveu a STRING do JSON, nao o dicionario | **PROVADO** | ver abaixo |

### (c), medido

O script SHIPPED do dia (`CONTENT_GATE_JS` do `H:/sotto/app/webview/sotto_webview.py` nao tocado,
`len=1315`) avaliado na pagina REAL, viewport 380x40:

```
typeof = str
value  = {"surface":"strip","style":true,"sized":false,"w":380,"h":0,"bg":"rgba(11, 15, 20, 0.98)","head":"none","vis":"visible","error":""}
wire   = "{\"surface\":\"strip\",\"style\":true,\"sized\":false,\"w\":380,\"h\":0,\"bg\":\"rgba(11, 15, 20, 0.98)\",\"head\":\"none\",\"vis\":\"visible\",\"error\":\"\"}"
exec_js answer type = str
```

`CONTENT_GATE_JS` termina em `return JSON.stringify(out)` — uma string — e o `ExecuteScriptAsync`
JA' serializa o valor de retorno em JSON; o `json.loads` do `exec_js` entrega a string
`'{"surface":...}'`, que caia no `else` do gate: `why='bad-answer'`, `out['error']` vazio.

Tres provas independentes de que foi isto e nao uma pagina parada:

1. **A impressao digital da linha viva.** `size=0x0 head="" vis=` VAZIOS sao os DEFAULTS do `out`
   (`{'applied': None, 'style': False, 'sized': False, 'w': 0, 'h': 0, ...}`): o ramo do
   DICIONARIO nunca correu em nenhuma das duas linhas. A sonda imprime isso como
   `branch=default fields-are-real=false` para as duas.
2. **O mesmo `exec_js`, 63 ms antes, devolveu uma `str` de verdade nessa sessao.**
   `12:51:45.080 STRIP_HEIGHT from=148 to=40 source=css css_value=40` sai de
   `strip_height_from_css`, que so' aceita `isinstance(raw, str)`. O contrato esta medido no log do
   dono, nao inferido.
3. **Nenhum show fez ack NUNCA:** `grep -c "PANEL_CONTENT surface=.*ack=true"` = **0** em todo o log.
   Um "a pagina ainda nao estava pronta" de vez em quando nao produz zero-em-todos.

### O SEGUNDO defeito, medido no mesmo replay

`ack` ainda seria FALSO depois de ler a string, porque `sized` lia o RECT DO `body`:

```
body  = {"w":380,"h":0}     html = {"w":380,"h":0}     bodyCS height = "0px"
panel = {"w":380,"h":40}    innerH = 40, clientH = 40
```

Medido nas duas superficies e em tres viewports (`380x40`, `380x148`, `520x900`): `body` e `<html>`
medem altura 0 SEMPRE (`body { height: 0 }`; o layout vive nos filhos absolutos). `sized` era FALSO
PARA SEMPRE. O elemento que tem caixa e' `.panel` — e o rect dele ja' era lido no caminho do show com
a janela escondida: `12:51:45.092 STRIP_WIDTH ... to=380 source=content` vem de `strip_width_dom`,
que mede exactamente `.panel.getBoundingClientRect().width`, 53 ms antes do gate que falhou.

## A cura (a classe, nao o timestamp)

1. **`gate_answer_payload(answer)`** — aceita o DICIONARIO **e** o JSON em string (a forma que a
   pagina devolve). Tudo o que nao for nenhum dos dois sai com `why` NOMEADO
   (`page-error` / `page-not-ready`) e os primeiros **120** chars crus em `out['error']`. O literal
   `bad-answer` NAO existe mais no codigo do gate.
2. **`gate_probe(name, ask, budget)`** — o laco: uma pergunta, e repeticoes **dentro do mesmo
   orcamento** (`CONTENT_GATE_TIMEOUT_MS` = 250 ms e' o TECTO, cada `exec_js` recebe o que RESTA, o
   piso de repeticao e' `CONTENT_GATE_RETRY_MIN_S` = 20 ms). Um ack na primeira tentativa nao paga
   nada; nada e' mais lento do que o pior caso de hoje.
3. **`CONTENT_GATE_JS` mede `.panel`**, nao `body` (o defeito de `sized` acima).
4. **A linha do show usa a resposta:** os tres `PANEL_SHOWN` publicam
   `content_why=<nomeado> content_attempts=N`, e um show sem a pagina vestida escreve tambem
   `WARN PANEL_UNDRESSED surface=... why=... wait_ms=... attempts=... error=...`. A falha aberta NAO
   mudou: o mapa acontece na mesma; o que muda e' que ele deixa de poder dizer "show" sem dizer
   porque nao estava vestido.

**Porque retry e nao readiness-event/state-read** (a escolha que o ticket pede): o replay mostra que a
pagina RESPONDEU em 16 ms com `surface=strip, style=true` — ela estava pronta. Nao havia corrida com o
DOM; havia um shell a ler mal a resposta. Um evento de prontidao resolveria um problema que nao existe
e nao resolveria o que existe. A repeticao entra como o que ela e': uma segunda leitura barata para a
janela transitoria (carregamento de CSS, primeira pintura), limitada pelo orcamento que ja' existia.

## Bracos

`python _main/paint-live-show-oracle.py --log H:/sotto/_main/webview-run.log` → **GREEN**, rc=0:

```
PAINT-LIVE replay 2026-11-04 12:15:43.542: content_ack=true why=applied applied="strip" style=true sized=true size=756x488 head="none" viewport=756x488 gate_ms=10.6 attempts=1
PAINT-LIVE replay 2026-11-04 12:51:45.143: content_ack=true why=applied applied="strip" style=true sized=true size=756x488 head="none" viewport=756x488 gate_ms=10.6 attempts=1
PAINT-LIVE show LEGADO 2026-11-04 12:51:45.180: content_ack=false na linha, REPLAY ack=true why=applied
PAINT-LIVE VERDICT: GREEN
```

O `REPLAY` e' o que ele diz ser: a pagina REAL + o `CONTENT_GATE_JS` SHIPPED + o `gate_probe` SHIPPED,
medidos agora. A linha do processo antigo fica impressa verbatim, marcada `LEGADO`, porque o shell
daquela sessao nao sabia ler a resposta e nada reescreve o log dele.

`--neg-arm` → `NEG-ARM cases=12 caught=12`, `NEG-ARM PASS`, rc=1 (expect-red da casa):

| braco | mutacao | esperado | medido |
|---|---|---|---|
| show-sem-ack | `paint_ack=true` → false | RED | RED |
| mapa-antes-do-conteudo | o `PANEL_CONTENT` para DEPOIS do `PANEL_SHOWN` | RED | RED |
| show-sem-ack-conteudo | `content_ack=true` → false | RED | RED |
| conteudo-nao-aplicado | `ack=true` → false na linha do gate | RED | RED |
| show-lento | `wait_ms=951` | RED | RED |
| sessao-sem-aquecimento | remove `PAINT_WARM` | RED | RED |
| fonte-mapa-antes-do-gate | gate depois do mapa no fonte | RED | RED |
| **fonte-bad-answer-de-volta** | `gate_answer_payload` volta a devolver `('bad-answer')` | RED | RED |
| **fonte-sem-repeticao** | remove o `gate_should_retry` do `gate_probe` | RED | RED |
| **bad-answer-de-volta-derruba-o-log** | o MESMO mutante, julgado contra o LOG do dono | RED | RED (`replay ... ack=false why=bad-answer`) |
| retry-recupera-dentro-do-orcamento | `gate_probe` SHIPPED + relogio de brinquedo: resposta ma, depois boa / sequencia que nunca acka | GREEN | `attempts=2 wait_ms=32.0` / `attempts=5 wait_ms=250.0` |
| **retry-removido** | o mesmo, com a repeticao removida | RED | RED (`attempts=1 why=page-error`) |

Positivos: `POSITIVE-CONTROL: o fonte REAL tem a ordem, a leitura e a repeticao? sim` e
`POSITIVE-CONTROL: o log REAL e' julgado com replay? replayadas=1 veredicto=GREEN`.

Nota de honestidade sobre os bracos: a amostra dos mutantes de log passou a ser uma SESSAO SINTETICA
FECHADA (com o seu proprio `SHELL_STARTUP_STAGE`). Com o log real + cauda sintetica, o
`PANEL_CONTENT` de 12:51 — que o replay agora acka — satisfazia a ordem do show sintetico e o braco
`mapa-antes-do-conteudo` publicava GREEN sem que o mutante fizesse nada. Medido, corrigido.

## Relogio de parede

| | antes | curado |
|---|---|---|
| `PANEL_CONTENT wait_ms` (12:15:43) | 0.0 ms | — (mesma 1 pergunta, so' que lida) |
| `PANEL_CONTENT wait_ms` (12:51:45) | 16.0 ms | orcamento identico: 1 chamada, `left = 250 ms` |
| custo do script DENTRO da pagina (replay) | — | **5.3–10.6 ms** (execucoes repetidas) |
| `PANEL_SHOWN wait_ms` (o mapa + paint ack) | **31.0 ms** | inalterado: a cura nao acrescenta espera nenhuma (o `wait_paint_ack` nao mudou) |
| pior caso do gate | 250 ms | **250 ms** (`attempts` so' gasta o que sobra; medido: 5 tentativas ate' 250.0 ms quando nada acka) |
| caminho resolvido | — | `attempts=1` (medido com o `gate_probe` shipped) |

## Verificacoes que correram

- `python _main/paint-live-show-oracle.py --log H:/sotto/_main/webview-run.log` → GREEN, rc=0.
- `... --neg-arm` → `cases=12 caught=12`, PASS, rc=1.
- `python _main/agents-md-pins-oracle.py` → `AGENTS-PINS PASS -- 2 pin(s) checked live`.
- `python _main/battery-wiring-oracle.py` → `BATTERY-VERDICT battery-wiring PASS checks=7 fail=0`
  (nenhum oraculo novo sem passo: a sonda nao esta na populacao — o glob e' `*oracle*`/`*-gate.py`).
- `python _main/tooling-intent-oracle.py` → FAIL com **9** vermelhas, e o conjunto e' BYTE-IDENTICO ao
  de `H:/sotto` (`diff` dos dois conjuntos vazio). E' divida PRE-EXISTENTE (9 oraculos antigos sem
  `BLOCKS:`/`NO-BUG:`); esta lane nao a aumenta. A declaracao desta lane (`NO-BUG:`) foi movida para a
  linha 1 do ficheiro: o contrato so' le as primeiras 60 linhas, e a docstring acrescentada empurrava-a
  para a 62 -- medido pelo proprio oraculo, que passou a chamar-lhe "ferramenta nova".
- `content_gate` executado como metodo (fonte extraido, `exec_js` falso devolvendo o que o WebView2
  devolve): resposta boa → `ack=true why=applied attempts=1` e a linha
  `PANEL_CONTENT ... attempts=1 error=""`; resposta ma → `ack=false why=page-error attempts=22
  wait_ms=234.0 error="TypeError: is not a function"` + `WARN PANEL_UNDRESSED ... why=page-error`.

## UNMEASURED (e porquê)

1. **Uma sessao VIVA com o shell curado.** A lei `SOTTO_NEVER_ON_OWNER_SCREEN` proibe esta lane de
   pôr a app no ecra do dono; a prova do caminho curado e' o replay da pagina real + o `gate_probe`
   shipped, nao uma linha de log produzida pela app.
2. **O que o `ExecuteScriptAsync` devolve quando o script LANCA.** Nao foi medido no WebView2 (isso
   exige o controlo instanciado). O que o replay mede e' a forma do valor de retorno de um script que
   NAO lanca, que e' o caso deste gate; e o `catch` do proprio script ja' transforma qualquer excepcao
   interna num JSON com `error` preenchido — caminho novo: `why=page-error`.
3. **`documentElement.clientWidth/Height` com a janela escondida neste box.** Por isso a cura NAO os
   usa: `sized` le o rect de `.panel`, e esse rect foi lido no log do dono com a janela escondida
   (`STRIP_WIDTH ... to=380`, 12:51:45.092).
4. **O cliente real da faixa (380x40) em headless.** `--window-size=380,40` da' `innerWidth=0`
   (minimo de janela do Windows ~492x56); o replay corre a 756x488 e imprime o viewport MEDIDO. O que
   ele prova e' o PREDICADO (superficie, `display` do cabecalho, caixa nao vazia), nao o tamanho.
5. **A linha de 12:15:43 foi replayada com a superficie `strip`** (como o log diz), mas o seu
   `PANEL_SHOWN` (`content_wait_ms=0.0`, `wait_ms=140.0`) pertence a uma sessao ANTERIOR ao ultimo
   `SHELL_STARTUP_STAGE` (12:21:21.980): o veredicto da sessao viva julga o show de 12:51, e o de
   12:15 entra no bloco de replay como evidencia, nao como veredicto.
6. **`reported` e `fixed` nao sao `verified`:** o que esta medido e' (i) a forma da resposta da pagina,
   (ii) o ack do codigo shipped sobre essa resposta, (iii) os mutantes. O dono ver a faixa vestida no
   primeiro frame do proximo Alt+C e' a medicao que falta, e ela e' dele.
