# RECIBO - o show que confia no que nao foi confirmado, e o RED de um processo velho (2026-11-10)

Card: `p0 arranque: demora DEMAIS a responder a keybindings/qualquer coisa -- tornar extremo`.
Tudo aqui foi medido nesta arvore hoje, com o comando ao lado. Nenhum numero foi copiado de log
antigo.

## 1. O que o card pedia, e o que estava por baixo

| metade | instrumento | numero medido |
|---|---|---|
| resposta do Alt+C (o show) | `_main/paint-live-show-oracle.py` sobre `_main/webview-run.log` | 22 shows, `content_wait_ms` p50 31 / p95 125 / max 250, `wait_ms` p50 15 / p95 78, **total p50 78 / p95 157 / max 297**, `paint_ack=false` **zero** |
| a linha que reprovava | o mesmo oraculo | `PANEL_SHOWN ... content_ack=false content_why=ui-thread-busy content_attempts=1 content_wait_ms=250.0 paint_ack=true wait_ms=47.0` as 2026-11-09 21:21:55.103 |
| quem escreveu essa linha | `python _main/live-code-freshness-oracle.py` | `LIVE_CODE STALE pid=52792 started=2026-11-09 21:21:46.700` -- o processo e' anterior a' cura |

Ou seja: o portao estava RED por uma linha produzida por **codigo anterior**, e a causa dessa linha
era uma metade do proprio instrumento que nunca podia disparar.

## 2. As tres curas, cada uma com a sua prova

### 2-a. O orcamento e' da ESPERA, nao de uma pergunta

`app/webview/sotto_webview.py` -- `gate_probe` entregava `left` (o orcamento inteiro) a' primeira
pergunta. Uma pagina com a UI ocupada nao responde nesses 250 ms, e `gate_should_retry` -- que existe
para `ui-thread-busy` -- ficava sem orcamento nenhum. Agora:

```python
CONTENT_GATE_ATTEMPT_FRACTION = 0.5      # metade do orcamento por pergunta
ask_s = max(CONTENT_GATE_RETRY_MIN_S,
            min(left, budget_s * CONTENT_GATE_ATTEMPT_FRACTION))
```

O pior caso continua **250 ms de espera total** (nunca 250 ms por tentativa) e uma pagina ocupada
recebe duas perguntas. O 0,5 vem do campo: `content_wait_ms` de um show BOM tem p95 **125 ms** = metade
do orcamento.

### 2-b. A soma e' o que o olho paga

Os dois tetos julgavam cada metade (`content_wait_ms<=350`, `wait_ms<=400`); um show de
`300 + 200 = 500 ms` passava com as duas verdes. O oraculo passou a julgar
`content_wait_ms + wait_ms <= 400` (o mesmo orcamento que ja' existia) e a publicar a cauda:
`total_p50_ms` / `total_p95_ms` / `total_max_ms`. Medido: 78 / 157 / 297 ms -- a rede existe para a
cauda que hoje nao existe.

### 2-c. STALE nao e' veredicto sobre a arvore

O oraculo pergunta ao `live-code-freshness-oracle.py`; com o processo `STALE` **ou** `UNKNOWN` um RED
vira `PAINT-LIVE VERDICT: SKIPPED (processo STALE -- a evidencia e' do codigo anterior...)` e cada
falha e' reimpressa como `STALE-EVIDENCE` (a evidencia nunca se apaga). A demissao e' a funcao PURA
`demote_stale(verdict, fresh)` e o `--neg-arm` julga a matriz inteira:

| entrada | saida exigida |
|---|---|
| `RED` + `STALE` | `SKIPPED` |
| `RED` + `FRESH` | `RED` (um processo fresco continua a reprovar) |
| `RED` + `UNKNOWN` | `SKIPPED` |
| `GREEN` + `STALE` | `GREEN` |
| `SKIPPED` + `FRESH` | `SKIPPED` |

## 3. Os bracos

* `show-soma-acima-do-orcamento` -- muta a ultima linha para `content_wait_ms=300` + `wait_ms=200`:
  cada metade SOB o seu teto, a soma acima do orcamento. Apanhado so' pela arm da soma.
* `busy_attempts >= 2` -- a pergunta que **gasta tudo o que lhe dao** (como a producao faz) tem de
  receber uma segunda chance dentro dos mesmos 250 ms. Com o codigo de antes este braco mede
  `attempts=1`; foi por isso que a sequencia de brinquedo antiga (50 ms por pergunta) nao via o
  defeito: dava cinco tentativas num caso que a producao dava uma.

## 4. Medido, nesta arvore

```
python _main/paint-live-show-oracle.py
  PAINT-LIVE processo=STALE (LIVE_CODE STALE log=...webview-run.log)
  STALE-EVIDENCE conteudo nao aplicado antes do mapa (2026-11-09 21:21:55.057): ack=false why=ui-thread-busy ...
  STALE-EVIDENCE show 2026-11-09 21:21:55.103: content_ack=false (o mapa nao esperou o conteudo)
  PAINT-LIVE VERDICT: SKIPPED (processo STALE -- a evidencia e' do codigo anterior; o proximo arranque a julga)
  rc=0

python _main/paint-live-show-oracle.py --neg-arm
  red-stale-demovido -> SKIPPED ok · red-fresh-fica-red -> RED ok · red-unknown-demovido -> SKIPPED ok
  green-nunca-mexe -> GREEN ok · skipped-nunca-mexe -> SKIPPED ok · constante-do-gate-em-falta -> REFUSED ok
  NEG-ARM cases=19 caught=19
  NEG-ARM PASS   rc=1 (convencao da casa: o negativo que apanha sai 1)

python _main/agents-md-pins-oracle.py        -> AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
python _main/battery-wiring-oracle.py        -> PASS populacao=294 ligados=186 sem_passo=108
python _main/undefined-names-oracle.py       -> GREEN -- 19 ficheiros, 0 nomes usados e nunca definidos
```

## 4-bis. O extractor que montava um namespace INCOMPLETO (medido no proprio dia)

A primeira versao da cura pendurou o `--neg-arm` **40 s** em vez de falhar. Causa, achada com
`faulthandler`: `_main/content-gate-answer-probe.py` injecta no namespace das funcoes extraidas uma
lista FIXA de constantes (`GATE_CONSTANTS`) que nao conhecia `CONTENT_GATE_ATTEMPT_FRACTION`; o
`NameError` caia DENTRO do `try/except Exception` que existe para a pagina muda, o relogio ficava
parado em 0 s (a pergunta nunca acontecia) e o `while True` do `gate_probe` girava para sempre.

Curado em duas metades: a constante entrou na allowlist, e `missing_gate_constants()` **recusa** um
namespace incompleto antes de o executar (`SystemExit` com o nome do que falta). Provado:

```
missing with the constant dropped from the allowlist: ['CONTENT_GATE_ATTEMPT_FRACTION']
refused: o gate usa constante(s) que o extractor nao injecta: CONTENT_GATE_ATTEMPT_FRACTION
```

e o braco `constante-do-gate-em-falta` julga as duas metades (a fonte real nao tem constante em
falta; a allowlist sem ela e' recusada) em toda corrida.

## 5. O que NAO esta' verificado

* `fixed, NOT verified`: o numero que fecha este card e' o **proximo arranque do dono** -- com o
  processo `FRESH`, um show com `content_ack=false` volta a ser RED e o oraculo o nomeia. A linha
  `LADDER_TRY`/`PANEL_SHOWN` desse arranque e' a evidencia; eu nao abro a janela dele.
* O ganho de latencia do Alt+C **nao** foi medido num processo com a cura: a p95 de 157 ms e' do
  processo STALE. O que esta' provado aqui e' que o portao deixou de julgar codigo velho e que o
  orcamento tem duas chances em vez de uma.
* `_main/_cache/sotto_webview_nograce.py` (fixture de outro oraculo) ainda carrega o `gate_probe`
  antigo: e' copia descartavel, nao embarca.
