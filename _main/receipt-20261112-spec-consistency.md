# RECIBO — a especificação passa a contar o que existe (2026-11-12)

A campanha de documentação fechou os 14 ficheiros, mas três coisas ficaram por dizer: um defeito
`corrigido` no ledger continuava `aberto` no registo vivo, a tabela-resumo do ledger não conhecia
o último defeito, e três tags de produção que a cura do `D-23` escreve não estavam no glossário.
Nada disto é cosmético: o `STATUS.md` é o registo, e quem o ler amanhã decide por ele.

## 1. O registo vivo contra o ledger — duas linhas, medida por comparação

Comando: um script que extrai as linhas `| D-nn |` dos dois ficheiros e imprime as colunas de
estado lado a lado (`STATUS` × `10-DEFECTS.md`).

| defeito | `STATUS` dizia | o ledger dizia | o que está medido |
|---|---|---|---|
| D-04 | `aberto; a escolha é do dono` | `corrigido, NÃO verificado` — `warm_evidence`, 13 arms, neg-arm 5/5 | o commit `4927ff3` mudou o código para pedir o motor **por evidência**; o `STATUS` estava a descrever o código de antes |
| D-19 | `**corrigido**` | `corrigido, NÃO verificado` — `cost_watchdog.window_expired`, 43 arms | o código está no disco, mas o processo que corre na máquina dele é anterior: `corrigido` sem `verificado` é a frase que este repo proíbe |
| D-23 | ausente da tabela-resumo do ledger | descrito na §D-23 | a tabela é o índice: um defeito fora dela não é encontrado por quem procura |

Duas correcções aplicadas: o `STATUS` do `D-04` passa a dizer o que o código faz e deixa aberta **só**
a escolha TTL-vs-adiar (que continua a ser dele); o `D-19` passa a `corrigido, NÃO verificado` com a
razão escrita; a linha `D-23` entra na tabela-resumo.

## 2. As três tags que a cura do `D-23` escreve, e que nenhum glossário nomeava

Medido no código antes de escrever a linha:

```
$ grep -n "EXTERNAL_OWNER owner=\|ASR_PAINT_REFUSED owner=" app/webview/sotto_webview.py
19615:        log(f'EXTERNAL_OWNER owner={owner} previous={previous} '
19651:            log(f'ASR_PAINT_REFUSED owner=player source={source or "-"} '
21931:        log('CAPTION_WANTED_START on=%s reason=%s stored=%s stored_at=%s'
$ grep -n "EXTERNAL_OWNER\|ASR_PAINT_REFUSED" docs/spec/12-GLOSSARY.md
(0 linhas)
```

Três linhas novas na §3.4 do glossário, cada uma com o campo que só se entende pela história:
`EXTERNAL_OWNER` com `suppressed_episode`/`suppressed_total` (a primeira versão do contador era
zerada antes de ser lida e media sempre `0`), `ASR_PAINT_REFUSED` com a palavra **descartada** (a
linha local não vai ao ecrã nem ao histórico), e `CAPTION_WANTED_START` com `stored=`/`stored_at=`
(a escolha do disco não vence o arranque — `D-02`).

E uma linha nova na tabela-mestra do `09-FAILURE-MODES.md`, porque é uma falha que o dono **vê**
como ausência de legenda local enquanto o player manda: detector, acção e o que ele vê.

## 3. O orçamento por passo deixa de ser uma excepção muda

O `panel-hidden-at-startup` mediu **55,7 s** sozinho e **242,77 s** numa corrida carregada — o mesmo
passo, o mesmo código, e a variância é a máquina. Ele declara `SOTTO_STEP_OVERRIDE_S=420` na própria
linha, e a §3 do `11-TARGET.md` passa a dizer por que: a excepção é declarada **no passo que a pede**
e provada pelo braço A7 do `step-deadline.py`; subir o tecto sem esse passo é a batota que a casa
proíbe.

## 4. O selo re-medido — três vezes, porque as duas primeiras medições já estavam velhas

| o quê | valor anterior | medido agora | comando |
|---|---|---|---|
| ficheiros | 16 | **16** | `os.listdir(docs/spec)` |
| linhas (sem `README.md`) | 5 299 | **5 312** | soma de `len(text.splitlines())` |
| `[CODE]` | 1 326 | **1 329** | `re.findall(r'\[([A-Z]+)\]')` |
| `[MEASURED]` | 170 | **170** | idem |
| `[INFERENCE]` | 61 | **61** | idem |
| `[UNKNOWN]` | 68 | **68** | idem |
| citações resolvidas | 1 443 | **1 446** | `python _main/spec-citations-oracle.py` |
| população de produto | 115 | **115** (32 em `worker/_probe/`, 84 em `app/panel/skins/`) | `spec-coverage-oracle.population()` |
| `sotto_webview.py` | 26 362 linhas / 227 membros | **26 774 linhas / 217 membros** | `ast` sobre o corpo de `SottoShell` |

O último número é o que mais custa: o antigo contava **todas** as funções e métodos com outro
critério. O que está escrito agora é medido com a definição ao lado (membros do corpo de
`SottoShell`), para que a próxima sessão possa repetir a conta em vez de acreditar no número.

## 5. Portões re-corridos depois das edições

```
$ python _main/spec-citations-oracle.py
SPEC-CITATIONS: docs=16 citacoes=1446 sem_ficheiro=0 fora_de_alcance=0 index_ausente=0 fora_da_tabela=0
SPEC-CITATIONS VERDICT: PASS

$ python _main/spec-coverage-oracle.py
SPEC-COVERAGE docs=16 ausentes=0 nome_apenas=5 classes_sem_seccao=0
SPEC-COVERAGE VERDICT: PASS
```

## 6. O que NÃO está verificado

* Nada disto foi observado no processo dele: são documentos a descrever código, e o critério de
  aceitação do `00-PROMISE.md` §4 exige `pid` e hora. O `D-04` e o `D-19` ficam `corrigido, NÃO
  verificado` até ele reiniciar a app.
