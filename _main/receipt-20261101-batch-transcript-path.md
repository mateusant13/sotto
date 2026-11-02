# Recibo — a linha do parakeet chega ao disco: `route=batch` (2026-11-01T22:03Z)

Fecha o buraco que o falsificador independente nomeou (cartao #32) e que o dono tinha descrito de
memoria em 2026-10-06, verbatim: *"o historico simplesmente mostra a legenda ao vivo, inves de mostrar
a versao processada pelo redux"* e *"o historico nao e' pra ser NUNCA o historico do live nvidia. e'
pra ser do parakeet redux"*.

## O defeito, com instrumento

O motor de batch emite MUITO pouco: medido em `worker/redux_batch.py:185-197`, a linha e'

```json
{"type": "caption", "text": "...", "start": 1.234, "end": 5.678, "producer": "redux"}
```

**sem `route`, sem flag `final`**. E o choke point do painel recusava essa linha **uma instrucao antes**
da guarda que existe para a aceitar:

```js
const route = meta && meta.route;
if (route !== 'final') return;              // <- recusava PRIMEIRO
if (!isCanonicalLine(meta)) return;         // <- nunca chegava aqui
```

Censo da loja inteira (`grep -rho "route=[a-z-]*" history/`): **1571 `route=final`**, **11
`route=provisional-draft`**, **0 de batch**. E as 502 linhas sem sufixo nenhum sao TODAS de 2026-10-06
ou antes — ou seja, de antes do sufixo existir (`history/2026-11-01/*.md` em diante nao tem uma).

## A cura, em tres metades

|ficheiro|o que mudou|
|---|---|
|`app/panel/history-source.js`|`transcriptRoute(meta)` decide a rota, fail-closed: nao-canonico -> `null`; `provisional-draft` -> `null`; rota desconhecida num canonico -> `null`; `final` fica `final`; **canonico sem rota -> `batch`**. Vive aqui porque este e' o ficheiro DAM-FREE que o oraculo executa.|
|`app/panel/panel.js`|`recordHistory` deriva a rota em vez de a exigir (o call site fica fino: uma chamada, um `if (!route) return;`).|
|`app/webview/sotto_webview.py`|`HISTORY_ROUTES = ('final', 'provisional-draft', 'batch')`, e o escritor `_history_provenance` passa a imprimir `route=batch`.|

`batch` e **nao** `final` de proposito: `route=final` significa "o segundo passe do worker VIVO fechou
esta linha", e uma linha de batch vestindo esse nome forjaria exactamente o campo que uma auditoria le
para separar as duas fontes.

## O portao: `_main/_redux-transcript-path.py`

Nao julga uma copia: executa as tres metades do **ficheiro entregue**.

|metade|arms|como|
|---|---|---|
|decisao|7/7|`require('app/panel/history-source.js')` e chama `transcriptRoute` (batch sem rota, batch com rota inventada, worker fechado, provisional, live, sem producer, sem meta)|
|call site|4/4|extrai o corpo REAL de `recordHistory` de `panel.js` por casamento de chavetas e corre-o contra stubs: batch -> `append` chamado 1x com `route:'batch'`; live/provisional -> 0 chamadas|
|escritor|5/5|extrai `_history_provenance` com `ast` e executa so' essa funcao: `{'route':'batch'}` -> `route=batch start=12.50`; rota fora da tupla -> `''`|

**Braco negativo** (`--neg-arm`, rc 1 = a arvore consegue ficar vermelha, a convencao da casa): muta
**copias** para a forma ANTERIOR nos tres lados — `transcriptRoute` volta ao `if (route !== 'final')
return null`, a tupla volta a `('final','provisional-draft')` — e exige:

```
FAIL batch-no-route         want='batch'   got=None
FAIL panel:batch-no-route   want=(1,'batch') got=calls=0
FAIL batch-line             want='route=batch' got=''
FAIL batch-line-start       want='start=12.50' got=''
NEG-ARM: PASS — all three mutants go RED on exactly the batch arms
```

Os ficheiros vivos sao LIDOS, nunca escritos, pelo braco negativo.

## Cabo na bateria

`_main/_audit-verify-all.cmd`: `redux-transcript-path` + `red-as-expected-redux-transcript-path`
(deps: os quatro ficheiros acima). O pin do `.cmd` foi re-medido e vive no `AGENTS.md`:
**155976 B, 2011 CRLF, 0 bare LF**, sha256 `A4D2D1ED…43B2B55C`; `agents-md-pins-oracle.py` PASS e
`battery-class-oracle.py` PASS medidos depois da edicao.

## O que NAO esta provado

**Nao ha verificacao ao vivo.** A instancia do dono saiu as **19:03:44** (`SHELL_EXIT rc=0
reason=tray-quit`, `webview-run.log`) e uma lane nao a levanta no ecra dele. O codigo que a proxima
instancia carrega e' o curado (mtime 18:46, anterior ao arranque de 19:03 que ja' correu com ele), mas
**uma linha `route=batch` em disco so' se prova com audio a tocar na app a correr**. Estado honesto:
`FIXED, NOT VERIFIED` para a superficie viva; `VERIFIED` para o caminho do ficheiro (16 arms + 4
mutantes).

Reproduzir:

```
python _main/_redux-transcript-path.py            # rc 0
python _main/_redux-transcript-path.py --neg-arm  # rc 1 (convencao red-as-expected)
```
