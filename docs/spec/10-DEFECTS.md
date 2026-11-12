# 10 — O LEDGER DE DEFEITOS

Um defeito entra aqui quando tem **três coisas**: o estado de ANTES (o que se observa), o estado de
DEPOIS (o que se passa a observar), e o comando que produziu os dois. O que não tem as três é uma
opinião e não entra.

**Escala.** `CRÍTICO` = o produto mente sobre si mesmo ou não faz a jornada principal · `ALTO` = uma
jornada funciona mal de forma reprodutível · `MÉDIO` = custo, ou um instrumento cego · `BAIXO` =
higiene. Um defeito `CRÍTICO` só fecha com oráculo **e** braço negativo.

**Estados.** `aberto` · `corrigido` (o código mudou) · `corrigido, NÃO verificado` (a cura está no
ficheiro e o processo que ele carrega ainda não a tem — a lei do `STALE`), `fechado` (observado a
funcionar pela mão do dono).

## Resumo

| id | uma linha | gravidade | estado |
|---|---|---|---|
| D-01 | dois mutantes congelados do worker não estavam no git; dois oráculos dependiam deles | ALTO | **fechado** no código (`git add -f`), `git ls-files` prova |
| D-02 | o arranque obedecia a `caption-wanted.json` e um `false` gravado suprimia a legenda em TODA a abertura seguinte | CRÍTICO | **corrigido, NÃO verificado** — o processo do dono corre código anterior |
| D-03 | `ast.get_source_segment` re-parte o ficheiro inteiro por chamada: um passo novo custou 143,9 s | MÉDIO | corrigido no oráculo desta campanha; os outros sítios por medir |
| D-04 | a carga do modelo a frio custa 5,2–21,0 s no log vivo, e a primeira legenda paga-a | ALTO | aberto — o motor quente existe; `UNMEASURED` no processo dele |
| D-05 | o portão do relógio julgava 36 de 449 passos quando invocado sem `--policy`, e o RED descrevia a invocação | MÉDIO | **corrigido** — recusa `CANNOT-MEASURE` (rc 2) antes de escrever; 6 arms; neg-arm 6/6 |
| D-06 | a bateria presa a `cap40` soma 2 470,3 s em 413 passos (o portão julga 2 293,3 s), contra um alvo declarado de 60 s | MÉDIO | aberto, com a cauda nomeada |

---

## D-01 — os mutantes congelados fora do índice

**Antes.** `worker/_sotto_worker_agcinert.py` e `worker/runs/_verdict-order-mutant.py` existiam só
na árvore de trabalho: `.gitignore:121` listava o primeiro e `worker/runs/` excluía o segundo.
Dois oráculos os executam:

```
$ grep -n "_sotto_worker_agcinert\|_verdict-order-mutant" _main/agc_order_live.py _main/verdict-order-oracle.py
_main/agc_order_live.py:37:  MUTANT = os.path.join(ROOT, "worker", "_sotto_worker_agcinert.py")
_main/verdict-order-oracle.py:71:  MUTANT = os.path.join(RUNS, "_verdict-order-mutant.py")
```

**Impacto.** Num clone limpo os dois instrumentos não correm — e o `agc_order_live.py` é a sonda que
mediu a ordem do AGC. Um instrumento que só existe na máquina onde nasceu não é um instrumento.

**Depois.** `git add -f` + `.gitignore` com a razão escrita; `.gitattributes` regenerado pelo próprio
gerador do repo (`python _main/_make-gitattributes.py --write`; `--verify` rc=0), com as duas linhas
novas a prendê-los a `text eol=crlf`.

```
$ git ls-files worker | grep -E "_agcinert|_verdict-order|_prefix_audioflag"
worker/_prefix_audioflag.py
worker/_sotto_worker_agcinert.py
worker/runs/_verdict-order-mutant.py
```

**Estado.** fechado no código (commit `b016118`). O que fecharia de vez: uma linha na bateria que
`git ls-files` os dois nomes — hoje nada impede que um `git rm --cached` volte a esvaziá-los.

## D-02 — a legenda não abria, e o ficheiro é que mandava

**Ordem do dono (2026-11-11, verbatim):** *"as soon as i open it, should start the subtitles in my
screen. the ctrl space."*

**Antes.** O ficheiro de estado do dono, lido nesta máquina:

```
$ cat _main/caption-wanted.json
{"on": false, "at": "2026-11-11T17:41:48"}
```

`_caption_wanted_at_start` lia esse `false` e devolvia `False`; `create_window` não armava
`_caption_show_pending`; o overlay nunca aparecia. Como o único escritor do ficheiro era o próprio
HOLD do `Ctrl+Space`, **desligar uma vez era desligar para sempre** — a próxima sessão nascia muda e
ele tinha de premir a tecla outra vez para descobrir que estava tudo bem.

**Depois.** A decisão é pura (`SottoShell.caption_wanted_at_start`): liga por omissão; desliga numa
corrida de MEDIÇÃO (`MEASUREMENT_FLAGS`, a mesma tabela do worker) ou numa largada de lane
(`SOTTO_LANE_LAUNCH=1`); `SOTTO_CAPTION_WANTED_DEFAULT=0|1` sobrepõe-se a tudo; o desacordo com o
ficheiro vai para o log (`CAPTION_WANTED_START_OVERRIDES`).

```
$ python _main/caption-wanted-default-oracle.py | tail -1
VERDICT: PASS -- 21/21 arm(s)
$ python _main/caption-wanted-default-oracle.py --neg-arm | grep NEG-ARM
NEG-ARM: PASS -- 4/4 mutantes apanhados
```

**Estado.** corrigido, **NÃO verificado**. O oráculo `live-code-freshness` diz, sobre a instância
viva:

```
$ python _main/live-code-freshness-oracle.py | tail -4
MUDOU DEPOIS DO ARRANQUE: sotto_webview.py
>>> O QUE O DONO CARREGA NAO E ESTE CODIGO.
>>> fechar a app e abrir de novo ANTES de julgar o sintoma.
```

O que fecha: ele abrir a app e a legenda aparecer — uma linha `CAPTION_WANTED_START on=true
reason=default` na sessão nova.

## D-03 — o oráculo que pagava 143,9 s para ler uma função

**Antes.** `ast.get_source_segment(src, node)` refaz `splitlines()` da fonte **inteira** em cada
chamada. O oráculo novo desta campanha extraía 264 nós de `sotto_webview.py` (26 mil linhas):

```
383055125 function calls in 144.346 seconds
  264  118.273s  _splitlines_no_ff
```

Um passo de bateria que custa dois minutos e meio para ler funções é um passo que ninguém corre, e
um portão que ninguém corre não é portão.

**Depois.** A tabela de linhas é construída **uma vez** e a fatia é `''.join(lines[a:b])`:

```
$ time python _main/caption-wanted-default-oracle.py | tail -1
VERDICT: PASS -- 21/21 arm(s)
real 0m0.469s
```

**Estado.** corrigido em dois sítios medidos. `_main/audio-back-detector-oracle.py:62-84` e
`_main/ctrlspace-swallow-oracle.py:619` já tinham pago e documentado a mesma conta; os outros 38
ficheiros que chamam `ast.get_source_segment` **não foram medidos** — só um passo caro os denuncia.

O segundo sítio medido, e o mais caro: `_main/gaming-hotkey-oracle.py:class_methods` extraía os
métodos de `SottoShell` um a um. A/B na mesma fonte (2026-11-11):

```
methods=214 old=52.105s new=0.8521s identical=True diffs=0
```

61× mais barato, e **byte-idêntico** — a arm que importa, porque a emulação erra fácil:
`get_source_segment` **não** é um `dedent`. A primeira linha começa na coluna do nó e a última corta
na coluna final, e a indentação das linhas do meio **fica como está**; foi isso que fez a primeira
tentativa (com `textwrap.dedent`) rebentar em `IndentationError: unexpected indent` no `ast.parse` do
fragmento, apanhado pelo `--neg-arm` do próprio oráculo antes de qualquer commit. Medido depois:
`GAMING-HOTKEY GREEN -- arms=56 pass=56 fail=0` (rc=0) e `NEG-ARM PASS -- 5/5` (rc=1), com o passo
negativo de **116,4 s → 57,7 s**.

O que fecharia a classe: um censo AST que recuse `get_source_segment` dentro de um laço sobre
`ast.walk`/`cls.body`. Não está escrito: hoje só um passo caro denuncia.

## D-04 — a primeira legenda paga a carga do modelo

**Antes (e hoje).** Seis cargas consecutivas no log vivo do dono:

```
$ grep -o "BRIDGE_LOAD_MS ms=[0-9.]*" _main/webview-run.log | tail -6
BRIDGE_LOAD_MS ms=6969
BRIDGE_LOAD_MS ms=18859
BRIDGE_LOAD_MS ms=5203
BRIDGE_LOAD_MS ms=15109
BRIDGE_LOAD_MS ms=20985
BRIDGE_LOAD_MS ms=19312
```

5,2 s a 21,0 s a ler 1,9 GB, e durante essa janela o ecrã só tem o texto de estado. A ordem de
2026-11-11 ("as soon as i open it, should start the subtitles") exige que a legenda esteja LIGADA —
o que ela não pode prometer é a primeira linha.

**O que já existe.** O motor quente (`_main/warm-engine/`, tarefa `SottoWarmEngine`) e o preload:
medido na campanha do motor quente, o attach custa **0,97 s** contra 41 s de carga a frio.

**Estado.** aberto. `UNMEASURED` no processo dele: nenhum `WARM_LOAD_MS` no log vivo desta janela.
O que fecha: uma sessão nova em que `WARM_LOAD_MS` aparece antes do primeiro `Alt+C`, e a primeira
linha chega dentro de 3 000 ms do primeiro áudio (`_main/time-to-first-caption-oracle.py`).

## D-05 — o portão do relógio tem veredicto, e eu li-o mal

**Antes (a leitura errada, minha).** A primeira invocação que fiz foi a nua:

```
$ python _main/battery-budget-oracle.py
BATTERY-BUDGET policy=None: 413 passo(s) de OUTRA politica ficam de fora: ...
BATTERY-BUDGET VERDICT RED -- steps=36 total=115.4s TARGET MET
  RED politica de largada diferente do baseline (baseline='cap40', corrida=None) -- re-medir ...
```

E eu escrevi "hoje não existe veredicto de relógio". **Falso.** A bateria nunca corre o oráculo nu: o
`.cmd` passa a política da própria corrida —

```
$ grep -n "CAGE_POLICY" _main/_audit-verify-all.cmd | head -2
126:if defined SOTTO_BATTERY_CAGED (set "CAGE_POLICY=cap40") else (set "CAGE_POLICY=none")
3747:  ... python _main\battery-budget-oracle.py --policy "!CAGE_POLICY!"
```

Com a política que a corrida de facto usa:

```
$ python _main/battery-budget-oracle.py --policy cap40
BATTERY-BUDGET VERDICT RATCHET-OK -- steps=413 total=2293.3s TARGET NOT MET (gap 2233.3s de 60s)
```

**O que fica de pé, e é o defeito.** Um `--policy` omitido não falha em voz alta: ele **redefine a
população** (413 passos saem, 36 ficam) e comparara os 36 com um baseline de outra política, para
depois dar RED por uma razão que descreve a invocação e não a árvore. Um leitor apressado — eu —
conclui "o portão está quebrado". A cura óbvia é o oráculo **recusar** sem `--policy` quando o
baseline traz uma (`CANNOT-MEASURE: invocação sem política`), em vez de julgar.

**A cura, e ela é uma recusa.** Uma invocação que **omite** `--policy` sobre um baseline que tem
uma não devolve mais um veredicto: devolve `CANNOT-MEASURE` com rc 2, antes de qualquer escrita —
`smooth()` grava o histórico do passo, e uma invocação incompleta que reescrevesse a série seria pior
que o RED falso. `--policy none` continua a ser uma **escolha declarada** e não recusa; um baseline
sem política também não.

```
$ python _main/battery-budget-oracle.py
BATTERY-BUDGET CANNOT-MEASURE -- invocacao sem `--policy`: o baseline foi medido sob 'cap40' e sem a
bandeira a populacao comparada nao e a dele. Passe --policy 'cap40' ... ou --policy none ...
rc=2

$ python _main/battery-budget-oracle.py --policy cap40 | grep -E "VERDICT|ARM (ok|RED) R"
  ARM ok   R1 invocacao nua sobre baseline cap40 RECUSA (rc 2) e nomeia a bandeira
  ARM ok   R2 a MESMA invocacao com --policy cap40 passa
  ARM ok   R3 `--policy none` e uma escolha DECLARADA e passa
  ARM ok   R4 baseline SEM politica nao recusa invocacao nua
  ARM ok   R4b baseline declarado `none` RECUSA a nua e nomeia `none`
  ARM ok   R5 outra bandeira qualquer nao substitui --policy
BATTERY-BUDGET VERDICT RATCHET-OK -- steps=413 total=2293.3s TARGET NOT MET (gap 2233.3s de 60s)

$ python _main/battery-budget-oracle.py --neg-arm | tail -1
NEG-ARM: PASS (6/6 mutantes apanhados; juiz antes: True)          rc=1
```

Os seis braços medem os **dois sentidos**: uma recusa que nunca deixa passar é tão cega quanto a que
nunca recusa, e R2/R3 são o lado que prova que ela não engoliu a medição legítima.

**Estado.** corrigido no oráculo desta campanha (`_main/battery-budget-oracle.py`;
`policy_refusal` pura, recusa antes da escrita, `refusal_arms` na auto-prova). O veredicto real da
árvore é `RATCHET-OK` — 2 293,3 s em 413 passos, alvo de 60 s não atingido (D-06).

## D-06 — o custo da bateria

Duas populações, e é preciso dizer qual é qual — a soma bruta e a que o portão julga:

```
$ python - <<'PY'
import json, io
d = json.load(io.open('_cache/battery-steps.json', encoding='utf-8'))['steps']
rows = [(v.get('elapsed_s') or 0, k) for k, v in d.items()]
cap  = [r for r in rows if d[r[1]].get('policy') == 'cap40']
print('all   n=%d total=%.1fs' % (len(rows), sum(r[0] for r in rows)))
print('cap40 n=%d total=%.1fs' % (len(cap),  sum(r[0] for r in cap)))
PY
all   n=449 total=2585.7s
cap40 n=413 total=2470.3s

$ python _main/battery-budget-oracle.py --policy cap40
BATTERY-BUDGET VERDICT RATCHET-OK -- steps=413 total=2293.3s TARGET NOT MET (gap 2233.3s de 60s)
```

A diferença entre **2 470,3 s** (soma crua das 413 linhas presas a `cap40`) e **2 293,3 s** (o que o
portão julga) é a regra de censura do próprio portão, que descarta um corte e uma medição cujo custo
é de outra fase. Os dois números são verdadeiros e medem coisas diferentes: um é o que a máquina
gastou, o outro o que o portão atribui aos passos.

A cauda, na população presa:

```
  116.4s  red-as-expected-gaming-hotkey
   98.2s  red-as-expected-youtube-cdp-source
   92.2s  red-as-expected-panel-themes
   78.9s  red-as-expected-warm-engine
   60.7s  headphone-cut
   59.8s  red-as-expected-panel-header-oracle
   59.1s  red-as-expected-window-drag
   52.6s  red-as-expected-ctrlspace-swallow
```

**Gravidade MÉDIO, e não é cosmética:** seis passos fazem **506,2 s = 20 %** do total, e cinco deles
são braços NEGATIVOS `red-as-expected-*` que copiam a árvore ou abrem dispositivos reais. O alvo
declarado da casa é 60 s a quente; a soma é **38×** o alvo (2 293,3 / 60).

**Estado.** aberto. O que fecha: cortar a cópia por braço (a casa já fez isso no
`panel-hidden-at-startup`: cópia + renderização + referência **uma vez**, mutações por snapshot) e
voltar a medir com `battery-budget --baseline --rebase-policy <razao>`, com o número de ANTES
(2 293,3 s) ao lado.

---

## O que este ledger NÃO afirma

- Não afirma que o produto está quebrado fora do que está medido acima.
- Não classifica nenhuma jornada como `verified`: `verified` exige o processo do dono a correr ESTE
  código, e a lei do `STALE` continua a valer.
- Não copia números de outros documentos: cada `[MEASURED]` acima traz o comando que o produziu.
