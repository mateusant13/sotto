# RECIBO - o juiz do `.gitattributes` era um verde que nao media nada (medido 2026-11-15)

Cada numero abaixo foi medido nesta arvore hoje, com o comando ao lado. Onde a frase diz `PASS`, o
comando foi corrido nesta sessao.

## 1. O defeito, em duas metades

### (a) `--verify` era INERTE

`_main/_make-gitattributes.py` despachava assim:

```python
if modo == '--write':
    ...
else:
    sys.stdout.write(corpo)      # o `.gitattributes` inteiro
```

O `--verify` caia no `else`: imprimia o ficheiro que ele deveria verificar, **media nada** e devolvia
**rc=0**. E `docs/spec/STATUS.md:41` citava exatamente esse `--verify` rc=0 como prova de que o D-01
estava fechado -- um verde que **nenhum checkout produziu**.

**Controlo medido** (o mesmo codigo, as mesmas regras quebradas -- `app/webview/sotto_webview.py text
eol=lf` acrescentado ao `.gitattributes`):

| forma | rc | saida |
|---|---|---|
| antiga (`--verify` no `else`) | **0** | o `.gitattributes` inteiro impresso |
| nova (delega no portao real) | **1** | `DIVERGE ... hoje=CRLF checkout=LF` |

### (b) o rc certo com a prova apagada

A primeira versao da cura deixava o filho HERDAR o nosso stdout. Medido:
`python _make-gitattributes.py --verify > log` corria o portao, devolvia rc=1 e o log ficava com
**823 B** -- exatamente o censo do pai e **ZERO** linhas do portao (o resultado era escrito a partir
do offset 0, por cima do do filho). O controlo minimo (um script que imprime, faz `flush` e larga o
MESMO filho) herdava o stream sem perder nada: so' este caminho perdia. A saida passou a viajar por
**PIPE** e a ser reimpressa. Medido depois: **1139 B**, com o veredicto do portao dentro.

## 2. O juiz ganhou o braco que nao tinha

A comparacao de EOL vivia INLINE dentro do unico caminho que ela mesma julga -- logo nao tinha braco
negativo possivel (a classe "um controle que nao pode falhar"). Extraida para a funcao PURA
`julgar(ficheiro, eol_hoje, eol_checkout, bytes_do_worktree)`, e `--selftest` alimenta essa funcao
REAL com seis fotografias:

```
 uniforme igual              ok IGUAL/CRLF
 uniforme divergente         ok DIVERGE/LF
 LF que virou CRLF           ok DIVERGE/CRLF
 misto no dominante          ok MISTO/CRLF
 misto FORA do dominante     ok DIVERGE/MISTO -> LF (esperava CRLF)
 nao saiu                    ok DIVERGE/NAO SAIU
SELFTEST: PASS -- 6/6 casos
```

O caso 5 e' o mutante que importa. **Prova de que o selftest apanha um juiz quebrado** (mutacao
aplicada ao juiz REAL, nao a uma copia, e restaurada depois):

```
 misto FORA do dominante     FALHA MISTO/LF
SELFTEST: FAIL -- 1/6 casos
MUTANT   rc=1
RESTORED rc=0
```

## 3. O diff fantasma que estava a incomodar o repo inteiro

`git status` mostrava `app/webview/sotto_webview.py` com **27 365 linhas alteradas, para sempre**.
O blob guardava CRLF embora o `.gitattributes` diga `text eol=crlf` (indice = LF, checkout fabrica o
CRLF): o filtro limpava o worktree, o indice ficava sempre diferente, o diff nunca fechava.

`git add --renormalize` no indice **sem tocar no worktree** -- sha256 do ficheiro em disco identico
antes e depois: `8DAFECB51834DBDA60FF9A300045576180D65095555F7A32DF2293E198CA7781`.

O portao acusava mais **quatro** divergencias pre-existentes (`_main/clr-warm-oracle.py`,
`_main/devlab/sotto-dev.cmd`, `_main/receipt-20261112-clr-warm.md`, `worker/sotto_worker.py`).
`python _main/_make-gitattributes.py --write` (a via desenhada pelo proprio ficheiro, que gera as
regras a partir do EOL MEDIDO) fechou as quatro.

**A queda de `worker/sotto_worker.py text eol=crlf` NAO e' regressao** -- esta' verificada:

```
disk: crlf=0 bare_lf=9529                 (o ficheiro e' LF)
worker/*.py  text eol=lf                   (a regra geral ja' o cobre)
git check-attr text eol -> text: set, eol: lf
```

O pin antigo `crlf` contradizia os bytes medidos. O gerador escreve o que mede.

Medido depois:

```
ficheiros de texto versionados: 2733 / identico: 2725 / MISTO normalizado: 8 / DIVERGENTES: 0
git status: IDENTICO (antes e depois)
VERDICT: PASS   rc=0
```

## 4. A armadilha do blob, paga e fechada

O primeiro commit deste trabalho gravou os **BYTES CRUS** da arvore (CRLF) no blob dos dois
ficheiros -- exatamente o diff fantasma que ele existia para fechar. Blobs corrigidos para a forma
filtrada:

```
_main/_audit-verify-all.cmd   blob 396 480 B, crlf=0   |  worktree 401 086 B, crlf=4606, bare_lf=0
app/webview/sotto_webview.py  blob 1 456 292 B, crlf=0 |  worktree 1 483 657 B, crlf=27365, bare_lf=0
```

E o worktree do `.cmd` **tem** de ser CRLF (o `cmd.exe` le o ficheiro por OFFSET de bytes; com LF o
passo e' executado duas vezes -- medido 2026-10-08, escrito no cabecalho do proprio ficheiro). Os
bytes originais foram restaurados e o sha256 de ambos confere com o de antes:
`4382254C...` e `8DAFECB5...`. `git diff` dos dois: **vazio**.

## 5. O que ficou na bateria

| passo | o que prova |
|---|---|
| `gitattributes-verify` | um checkout REAL reproduz a arvore de hoje (2733 ficheiros de texto) |
| `gitattributes-verify-arm` | o JUIZ recusa um MISTO servido fora do terminador dominante (6/6) |

`battery-record-pairing`: **526 passos / 526 nomes com registo / 0 achados**.
`battery-wiring`: PASS `ligados=211 sem_passo=105 populacao=316`.

## 6. Portoes re-medidos depois de tudo

```
AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
SPEC-CITATIONS VERDICT: PASS   (1658 citacoes, 0 sem ficheiro)
CODE-HEALTH VERDICT PASS
BATTERY-VERDICT battery-wiring PASS checks=7 fail=0
battery-record-pairing VERDICT: PASS
BATTERY-CLASS VERDICT PASS -- arms=4 fail=0
```

`git status --porcelain -uall` do repo inteiro: **vazio**.

## 6-bis. O DIFF FANTASMA VOLTOU COM `abe7c44`, E O QUE O FECHOU (medido 2026-11-15, 15:2x)

O commit `abe7c44` (a rodada do `spec`) regravou os BYTES CRUS do worktree nos dois ficheiros que
este recibo tinha acabado de renormalizar. Medido antes da cura:

```
git ls-files --eol  ->  i/crlf  w/crlf  attr/text eol=crlf   _main/load-shedding-oracle.py
                        i/crlf  w/crlf  attr/text eol=crlf   app/webview/sotto_webview.py
git diff HEAD --ignore-cr-at-eol -- <os dois>  ->  VAZIO
```

Ou seja: **zero mudanca de conteudo** e 30 458 linhas de diff, exatamente a assinatura que a seccao 3
descreve. O indice guardava CRLF num ficheiro cuja regra manda LF no blob, logo o filtro limpava o
worktree, o indice ficava sempre diferente e o `git status` nunca fechava.

**A cura e' a mesma via, e o worktree nao foi tocado:**

```
commit 7299e2e  "eol: os dois blobs voltam a LF no indice, como o .gitattributes manda"
 2 files changed, 30458 insertions(+), 30458 deletions(-)
```

Medido depois:

```
git status --porcelain -uall          ->  vazio
git diff HEAD --stat                  ->  vazio
git ls-files --eol                    ->  i/lf  w/crlf  attr/text eol=crlf  (os dois)
worktree _main/_audit-verify-all.cmd  ->  401 086 B, 4606 CRLF / 0 bare LF  (cmd.exe le por OFFSET)
worktree app/webview/sotto_webview.py ->  1 483 579 B, 27 364 CRLF / 0 bare LF
_make-gitattributes.py --verify       ->  VERDICT: PASS -- um checkout reproduz a arvore de hoje
```

A licao que fica escrita: **um commit que grava o `.cmd` ou o shell tem de passar pelo filtro** — a
armadilha da seccao 4 nao foi um acidente de uma sessao, ela reapareceu num commit de outra lane
quatro dias depois, com o recibo dela na arvore.

## 7. O QUE NAO ESTA' VERIFICADO

* A bateria completa (528 passos) foi largada no fim desta sessao; o veredicto dela e' o do log
  `_main/_audit-verify/_*`, nao uma afirmacao deste recibo.
* Nada disto toca a tela do dono nem abre dispositivo de audio: os dois passos leem disco e rodam
  funcoes puras.
