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
| D-04 | cada abertura paga uma carga de motor quente (7,5–26,0 s, ~1 GB) que expira em 600 s antes de a vez dela chegar — as aberturas distam horas | ALTO | aberto, com a escolha nomeada (TTL vs pedir por evidência) |
| D-05 | o portão do relógio julgava 36 de 449 passos quando invocado sem `--policy`, e o RED descrevia a invocação | MÉDIO | **corrigido** — recusa `CANNOT-MEASURE` (rc 2) antes de escrever; 6 arms; neg-arm 6/6 |
| D-06 | a bateria presa a `cap40` soma 2 470,3 s em 413 passos (o portão julga 2 293,3 s), contra um alvo declarado de 60 s | MÉDIO | aberto, com a cauda nomeada |
| D-07 | o número do painel no arranque circulou em QUATRO versões sem população (braço/arranques/fase), e o portão exigia a contradição em vez de resolvê-la | ALTO | **corrigido** — leitor puro `--read`, fixture do único log vivo, portão re-escrito; neg-arm 3/3 |
| D-08 | o censo do painel abria o próprio log com `'w'` a cada linha: **cada invocação apagava a evidência da anterior** (4 073 B → 42 B, medido) | ALTO | **corrigido** — append com rotação, `--read` imprime sem escrever |
| D-09 | o menu do ícone re-armava **as duas** teclas: o `Ctrl+Space` do dono ficava preso no fio velho, o novo recebia 1409 e o gate de recuo abria — o mesmo toque alternava duas vezes | CRÍTICO | **corrigido, NÃO verificado** — `arm_hotkey_role` recusa um segundo fio por papel; oráculo + neg-arm 6/6 |
| D-10 | o braço `7d` do `altc-gesture` exigia a lista literal de toques do desligar: quando a cura de 2026-11-11 acrescentou `_caption_status_stop`/`_caption_off_ack`, o passo passou a acusar produto CERTO e a bateria ficou RED | MÉDIA | **corrigido** — o braço julga o domínio (só legenda, e a janela tem de ser tocada); 5º mutante prova; 98/98, neg-arm 5/5 |
| D-12 | o `--ready-file` do G3 era escrito pelo caminho dos 25 s, que completa o arranque com a página do painel **pendurada**: o largador respondia 0 ao único HANG que sabe medir, e o painel ficava branco | ALTO | **corrigido** — `_mark_launch_ready(panel_loaded)`; `LAUNCH_READY_WITHHELD why=panel-nav-stalled`; arms C1/C2 + mutante B2 |
| D-13 | a ordem do dono "passe de lote ligado" valia só por `run.cmd`; o autostart do logon larga `pythonw` e não passa por ele, logo no logon o motor de lote corria **DESLIGADO** | ALTO | **corrigido** — `env.setdefault('SOTTO_REDUX_LIVE','1')` em `_child_env`, ao lado da irmã; arms novas do `app-target` |
| D-14 | o motor quente entra na lista de *reap* da saída (`.kill()` levanta, `.wait()` não existe) e o matador externo mata-o pelo pid, com dois docstrings a prometer o contrário | MÉDIO | **aberto**, com a escolha nomeada (lista de *backstop* separada) |
| D-15 | uma largada de MEDIÇÃO (`--probe-v2` e mais oito) tomava lock privado e escrevia `panel-state.json`/`panel-visibility.json` por cima dos ficheiros da app viva — o worker do dono recebia `visible=false` e perdia o nível de shed de uma sonda | ALTO | **corrigido, NÃO verificado** — um único predicado para lock e estado, sufixo = nome do lock, worker lê o mesmo ficheiro; 15 arms + neg-arm 3/3 |
| D-11 | a segunda legenda da janela substituía a primeira no latch de `emit_async`: **fala perdida sem uma linha no log**, e é a página que commita o histórico — o histórico perdia a mesma fala | CRÍTICO | **corrigido** — kinds de EVENTO enfileiram (tecto 32, excedente CONTADO em `CAPTION_EMIT_DROPPED`); 6 arms, neg-arm 2/2 com o mutante novo |

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

**O que já existe, e o que ele custa de facto (medido 2026-11-12).** O motor quente
(`_main/warm-engine/`, tarefa `SottoWarmEngine`) **é** pedido pelo shell — `WARM_ENGINE_START_TASK
rc=0 registered=present` em **7** das 18 aberturas desde a cura de 2026-11-10 — e **carrega**:

```
$ tail -25 _main/warm-engine.log
2026-11-11 01:04:05 WARM_LOAD_MS ms=8060.0  resident_mb=1010.2
2026-11-11 01:13:57 WARM_EXIT why=idle-expired held_s=600.0
2026-11-11 17:34:35 WARM_LOAD_MS ms=12471.5 resident_mb=1010.2
2026-11-11 17:44:22 WARM_EXIT why=idle-expired held_s=600.1
2026-11-11 20:01:27 WARM_LOAD_MS ms=26027.8 resident_mb=1012.8
2026-11-11 20:11:01 WARM_EXIT why=idle-expired held_s=600.1
2026-11-11 20:47:16 WARM_LOAD_MS ms=7452.1  resident_mb=999.5   (deferido antes: WARM_LOAD_DEFERRED why=shed-alta)
2026-11-11 20:50:38 WARM_EXIT why=idle-expired held_s=600.1
```

E o shell, na abertura seguinte, diz sempre o mesmo:

```
$ grep -o "WARM_FALLBACK_COLD reason=[a-z-]*" _main/webview-run.log | sort | uniq -c
     18 WARM_FALLBACK_COLD reason=absent        (7 delas com WARM_ENGINE_START_TASK rc=0)
```

**A leitura, e ela muda o defeito.** O attach **não** está quebrado: o motor nasce ~1 s depois da
recusa, carrega em 7,5–26,0 s e depois **sai sozinho ao fim de exactamente 600 s**
(`WARM_PARK_TTL_S = 600.0`, `app/webview/warm_engine.py:66` — o mesmo TTL do worker, escolhido de
propósito). As aberturas dele distam **2 h a 16 h** (`01:03 → 17:34 → 20:01 → 20:40`), logo o
processo expira sempre antes da vez em que pagaria.

O defeito real não é "o attach falha": é que **cada abertura paga uma carga de modelo que ninguém
usa** — ~1 GB residente por dez minutos × 18, e a carga do worker continua a acontecer de qualquer
maneira depois. O custo medido de uma carga de motor é **7,5–26,0 s** de disco e CPU no arranque em
que ele já está a arrancar o resto.

**Estado.** aberto, com a escolha nomeada — e é do dono, porque as duas opções mudam o produto:

1. **aumentar o TTL/janela** — o motor passa a sobreviver entre aberturas (`WARM_PARK_TTL_S` é a
   constante; o `IDLE_HOLD_MAX_S` do worker é o mesmo número por desenho), ao preço de ~1 GB
   residente parado enquanto ele não abre a app;
2. **não pedir o motor** quando a abertura anterior já provou que a distância é de horas — o log
   tem a série que diz isso, e o pedido passa a ser por evidência, não por omissão.

O que fecha nas duas: uma sessão nova em que o primeiro `Alt+C` mostra `WARM_ATTACHED`, e
`_main/time-to-first-caption-oracle.py` mede a primeira linha dentro de 3 000 ms do primeiro áudio.

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

## D-07 — quatro números do mesmo instrumento, nenhum com população

**Antes.** `AGENTS.md` carregava uma nota que dizia, com todas as letras, que o painel no arranque
estava numa **contradição que ninguém resolveu**, e listava três leituras do *mesmo* instrumento:
`live` **0/20** com a janela mapeada (4/20 sem a cura), **18/20** e **88/130** amostras visíveis, e
o `run.cmd` citava ainda **11 de 20**. Nenhuma das três dizia contra qual braço, quantos arranques
executados, ou em que fase do arranque o episódio caiu. E o portão
(`_main/panel-flash-contradiction-oracle.py`) **exigia** o estado congelado: as armas eram as duas
frases, os três números, a palavra `NÃO reconciliada` e a frase "ninguém escolhe um lado". Ele
passou por um mês — enquanto os logs que sustentavam os números eram apagados (D-08).

**A resolução veio da população, não de uma nova medição** (a ordem do dono proíbe re-correr o
censo). O único log sobrevivente é o de 2026-10-11, agora fixado em
`_main/fixtures/panel-startup-flash-census-20261011.log`, e o leitor puro que este defeito trouxe lê
o que ele de fato mediu:

```
$ python _main/panel-startup-flash-census.py --read _main/fixtures/panel-startup-flash-census-20261011.log
CENSUS-READ log=panel-startup-flash-census-20261011.log sha256=2f2c641959b3db02 arms=live
ARM-SUMMARY-READ arm=live launches=19/20 launches_with_mech=3/19 launches_with_owner=3/19
                 launches_at_startup=0/19 arm_on_screen_flag=0/19 samples=3110
                 mech_samples=36 owner_samples=36 occluded_samples=3
                 longest_mech_ms=663 longest_owner_ms=663
rc=0
```

Três consequências, cada uma uma frase nova na lei:

1. O shell **curado** pintou em **3 de 19** arranques — não 0/20. `0/20` descreve uma corrida cujo
   log não existe: vale `UNMEASURED aqui`.
2. **Nenhum** episódio foi no arranque (`launches_at_startup=0/19`). Nos três, a linha de log
   corrente do shell era `PANEL_VISIBILITY_INVARIANT armed=true where=before_show` e, em dois deles,
   o `TRAY_MENU` — ou seja o que aparece não é o flash de arranque que a nota nomeava, é a dança do
   painel **depois** de o shell já estar de pé. `18/20` é o braço `nogate-nonet` (cura **e** rede
   arrancadas, como o docstring do censo diz): é o número de ANTES da cura, não um rival do número
   de depois.
3. Um número sem braço, sem arranques e sem fase não é um número — é uma frase.

**Depois.** O portão foi re-escrito para exigir a população: A1 nomeia o instrumento, A2 o leitor
puro, A3 o log sobrevivente, A4 as duas figuras do braço `live` com fase, A5 o `18/20` ao lado do
seu braço, A6 `UNMEASURED` ao lado de todo número sem log, A7 **recusa** a frase congelada, A8 exige
que a destruição da evidência esteja no registo (para o próximo instrumento não a repetir).

```
$ python _main/panel-flash-contradiction-oracle.py
VERDICT: PASS -- every flash number names its arm, its launch count and its phase; the surviving log
is citable without re-running the census, and the frozen contradiction is gone            rc=0

$ python _main/panel-flash-contradiction-oracle.py --neg-arm
  caught M1-A4 by A4   caught M2-A7 by A7   caught M3-A5 by A5
NEG-ARM PASS: 3/3 mutants, each caught by its own arm                                     rc=1
```

Cada mutante é apanhado **pela sua própria arma** — apagar a fase derruba A4, repor a frase
congelada derruba A7, tirar o nome do braço do `18/20` derruba A5 — e o negativo devolve `1` ao
apanhar, que é a convenção desta casa (um negativo que devolve 0 é um controlo que não pode falhar).

**Estado.** corrigido. O que continua `UNMEASURED`: se o painel aparece na tela do dono no arranque,
e por quanto tempo. Fechar isso exige uma corrida do shell dele — e a nota agora diz o que fazer com
esse número quando ele existir: braço, arranques, fase, arquivo.

## D-08 — o instrumento apagava a própria evidência

**Antes.** `_main/panel-startup-flash-census.py` gravava cada linha assim:

```
def log(msg: str) -> None:
    _lines.append(msg)
    with open(LOG, 'w', encoding='utf-8') as f:     # <-- 'w', POR LINHA
        f.write('\n'.join(_lines) + '\n')
```

O `'w'` é correto **dentro** de uma corrida (o buffer `_lines` é a fonte) e destrutivo **entre**
corridas: a primeira linha de uma invocação nova trunca o ficheiro. Medido em 2026-11-12, ao
adicionar o modo `--read`: um `--read` inocente deixou o log de 2026-10-11 com **42 B**, onde havia
**4 073 B** e 19 arranques. O ficheiro é `*.log` e o `.gitignore` o exclui, portanto a evidência não
existia em mais lado nenhum.

É a mesma classe que a casa já pagou três vezes (um instrumento cujo positivo só sabe falar por uma
janela real; um portão que acusa quem está certo; um oráculo que devolve sucesso quando o próprio
input é `None`): **um instrumento que apaga aquilo que mede não pode resolver uma discussão sobre a
medição.**

**Depois.** `log()` faz *append*, com **uma** rotação para `<nome>.1` acima de 4 MiB, e um
`OSError` escreve `CENSUS-LOG-WRITE-FAILED` no stdout em vez de desaparecer; `--read` fala por
`print` e nunca toca no ficheiro. Prova de que a leitura não escreve:

```
$ cp <fixture> /i/cc-tmp/flash-before.log
$ python _main/panel-startup-flash-census.py --read <fixture> > /dev/null
$ cmp /i/cc-tmp/flash-before.log <fixture> && echo "EVIDENCE UNTOUCHED"
EVIDENCE UNTOUCHED
```

**Estado.** corrigido, com a reconstrução declarada: o fixture de 2026-10-11 é uma **cópia verbatim**
do log impresso por `cat` antes de ele ser truncado, e o cabeçalho do ledger diz isso — um fixture
que se apresenta como original quando não é seria o defeito D-08 em roupas novas.

## D-09 — o interruptor do `Alt+C` trocava o dono da tecla da legenda

**Antes.** A perna de ARMAR do menu do ícone chamava `arm_hotkey(self, requested)`, que arma **as
duas** teclas (`panels` e `live`) e faz `shell.live_hotkey = arm_hotkey_role(shell, 'live', ...)`
sem parar o fio anterior. O fio velho continuava com o `WH_KEYBOARD_LL` e com o `RegisterHotKey`; o
novo pagava 1409 (`HOTKEY_LIVE_REGISTER_FAILED role=live`), o observador de recuo lia
`registered=False` e abria o gate — logo **um** `Ctrl+Space` físico alternava o display duas vezes
(liga e desliga no mesmo toque). O `stop_panels_hotkey` já sabia que a legenda não é dele; o arm não
sabia.

```
$ git show HEAD:app/webview/sotto_webview.py > <tmp>/sotto_webview.py
$ python _main/hotkey-panels-switch-oracle.py      # braços 10 e 11 contra o shell de HEAD
BEFORE-FAIL toggle_arms_panels_only            roles=['panels', 'live'] live_kept=False
BEFORE-FAIL rearm_refused_when_already_armed   same=False constructed=True
```

**Impacto.** O caminho principal do dono — desligar e religar o `Alt+C` no menu, que ele pediu em
2026-11-07 — deixava a tecla da legenda com dois donos, um deles órfão.

**Depois.** Duas metades, e a segunda é a que impede a classe em qualquer chamador futuro:

1. o handler arma **só** `panels` (`arm_hotkey_role(self, 'panels', requested, HOTKEY_FALLBACKS)`);
2. `arm_hotkey_role` decide por **três** bordas, e cada uma é um braço do oráculo:

| o papel já tem… | o pedido é… | o que a função faz | tag do log |
|---|---|---|---|
| fio vivo **e registado** | a **mesma** combinação | devolve o fio — um dono | `HOTKEY_REARM_USED` |
| fio vivo **sem registo** (observador de recuo) | a mesma combinação | **pára e tenta de novo** | `HOTKEY_REARM_REPLACE why=same-accel-not-registered` |
| fio vivo | combinação **diferente** | pára o velho e arma o novo | `HOTKEY_REARM_REPLACE why=different-accel` |

A segunda linha é o que impede um defeito novo: `panels_hotkey_state()` decide o texto do menu por
`registered`, logo devolver o observador faria do item **“Ativar atalho Alt+C”** um botão que nunca
liga (`toggled=true armed=0` para sempre). Uma tentativa nova é honesta — ela regista e diz o
resultado.

```
$ python _main/hotkey-panels-switch-oracle.py
ARM PASS toggle_arms_panels_only              roles=['panels'] live_kept=True
ARM PASS rearm_kept_when_registered            same=True  made=0 stopped=False
ARM PASS rearm_retries_when_not_registered     stopped=True made=1
ARM PASS rearm_replaces_a_different_accel      stopped=True made=1
CHECK arms=21 failed=0
VERDICT: PASS
$ python _main/hotkey-panels-switch-oracle.py --neg-arm
MUTANT toggle_rearms_the_live_key:              CAUGHT arms=['toggle_arms_panels_only']
MUTANT second_arming_creates_a_second_thread:   CAUGHT arms=['rearm_kept_when_registered']
MUTANT rearm_refuses_a_taken_key_forever:       CAUGHT arms=['rearm_retries_when_not_registered',
                                                           'rearm_replaces_a_different_accel']
NEG-ARM SUMMARY cases=7 caught=7
NEG-ARM: PASS
```

O “antes” dos quatro braços, medido contra o shell de `6ac68ae^` (`git show` para um temporário,
`judge_wiring` do mesmo oráculo): `roles=['panels','live'] live_kept=False`, `made=1` sem `stopped`
nas três bordas.

Um defeito de instrumento caiu junto: o braço 9 daquele oráculo gravava `arm_hotkey`, e desde a cura
o handler chama `arm_hotkey_role` — o registro **real** de `Alt+C` era pago dentro do oráculo
(medido: `enabled=False` no braço do toggle). Agora o stub é no **papel**, e nenhum
`RegisterHotKey` de verdade é pago por um instrumento.

**Estado.** corrigido, NÃO verificado: a cura está no ficheiro e o processo do dono carrega código
anterior (lei do `STALE`). Fecha com uma abertura dele e o menu do ícone usado duas vezes.

---
## D-10 — um portão que acusa quem está certo

**Antes.** O braço `7d` do `_main/altc-gesture-oracle.py` afirmava
`watched.touched == ["show_caption_window(False)"]`. A cura de 2026-11-11 (commit `c51b104`: *OFF
responde*) pôs `_caption_status_stop()` e `_caption_off_ack()` no mesmo ramo — as duas da **mesma**
janela —, e o braço passou a falhar. O passo é `always` na bateria, logo a bateria ficou RED sobre
produto certo.

```
$ python _main/altc-gesture-oracle.py
RED   desligar a legenda toca SO' na janela da legenda  ['show_caption_window(False)',
      '_caption_status_stop', '_caption_off_ack']
ALTC-GESTURE VERMELHO -- arms=98 pass=97 fail=1 (rc=1)
```

**Impacto.** O defeito é do instrumento e não da legenda: um portão que acusa quem está certo perde a
autoridade, e este custa 15 s em **toda** corrida.

**Depois.** O braço julga o **domínio**: cada toque tem de começar por `show_caption_window(`,
`_caption_status_` ou `_caption_off_ack`, e `show_caption_window(False)` tem de estar na lista — a
frase diz "só a janela da legenda" e é isso que fica medido. As armas de texto
(`_set_live_enabled NAO nomeia hide_panel/show_panel/worker/history`) continuam a existir, e um
**quinto** mutante fecha o buraco de "um braço que não pode falhar": `hide_panel('caption-on')`
reinstalado no desligar derruba o oráculo.

```
$ python _main/altc-gesture-oracle.py
ALTC-GESTURE GREEN -- arms=98 pass=98 fail=0
$ python _main/altc-gesture-oracle.py --neg-arm
NEG-ARM caption-off-closes-the-panel PASS -- RED as designed
NEG-ARM PASS -- RED as designed: as cinco regressoes derrubam o oraculo
```

**Estado.** corrigido; não toca no caminho da legenda, só no instrumento.

## D-11 — a legenda que o latch engolia

**Onde.** `app/webview/sotto_webview.py`, `emit_async` + `_run` (o latch por `kind`).

**Antes** (leitura do código, 2026-11-12):

```python
with lock:
    already = kind in pending
    pending[kind] = payload      # substitui a pendente
if already:
    return
```

O latch existe para o feed do medidor, onde **43 amostras/s** foram medidas: ali a última amostra
*é* o estado, e substituir a pendente é o certo. Uma legenda não é estado. `emit_async('caption', …)`
(caminho do worker) e `emit_async('external-caption', …)` (YouTube com o painel escondido) são o
**único** portador da fala até à página, e é a página que a commita ao histórico (`onCaption` →
`historyApi`). Colapsar A com B deixa a fala de A sem linha no log e sem linha no histórico — o oposto
do invariante que o mesmo ficheiro escreve desde 2026-11-03 ("nenhuma fala desaparece em silêncio").

**É alcançável?** A janela é um despacho de UI entre o `Invoke` e o `_run`. Esta máquina tem a thread de
UI ocupada de forma medida: `PANEL_SHOW_COST … total_ms=3142` na sessão do dono
(`_main/receipt-20261110-altc-paint-3142ms.md`, o fixture RED do `--paint-arm`). Com legendas a
~2/s e uma janela de 3 s, mais de uma legenda cai dentro dela.

**Depois** (mesma árvore):

```python
EVENT_EMIT_KINDS = ('caption', 'external-caption')
EVENT_EMIT_MAX = 32
```

* os dois kinds de evento **enfileiram**; o `_run` drena a lista **em ordem**, um script por payload;
* o tecto é o que o latch existia para dar, e o que passa dele é **contado e dito**:
  `CAPTION_EMIT_DROPPED kind="caption" n=8 cap=32 why=page-drain-fell-behind`;
* todo o resto (`stats`, `level`, …) continua a colapsar como antes — a cura dos eventos não desfez o
  tecto do feed.

**Medido.** `_main/emit-prewebview-oracle.py`, contra o ficheiro que embarca:

```
[PASS] duas legendas antes do drain: as DUAS chegam, na ordem   queued=1 scripts=2
[PASS] o feed de estado CONTINUA a colapsar (um script, o mais novo)   scripts=1
[PASS] 40 legendas com a pagina parada: 32 entregues e n=8 DITO
       dropped=['CAPTION_EMIT_DROPPED kind="caption" n=8 cap=32 why=page-drain-fell-behind']
emit-prewebview-oracle: 6 PASS / 0 FAIL (6 arms)
```

**Controlo.** O negativo deixou de conhecer um mutante só. Cada mutante é julgado **pelas SUAS** arms:

```
NEG-ARM[guarda-removida]:  1 de 6 arm(s) vermelha(s); esperadas=['50 pushes sem pagina']
NEG-ARM[evento-colapsado]: 2 de 6 arm(s) vermelha(s); esperadas=['duas legendas antes do drain',
                                                               '40 legendas com a pagina parada']
NEG-ARM PASS: 2 de 2 mutante(s) apanhado(s) pela SUA arm   (rc=1)
```

O mutante `evento-colapsado` é a implementação de **ontem** (`if False and kind in EVENT_EMIT_KINDS`),
e é ele que prova que as arms D e F têm dentes. Um controlo que só conhece o defeito de ontem
certifica o defeito de hoje — foi exactamente o que aconteceu aqui: o `--neg-arm` desta casa estava
verde (3 arms, 1 mutante) enquanto a fala se perdia.

**Estado.** corrigido; **não verificado** — `verified` exige o processo do dono a correr ISTO, e o
processo dele está `STALE` até reiniciar. O caminho do YouTube com o painel ESCONDIDO
(`external-caption`) usa o mesmo latch e não foi exercitado com uma página real nesta rodada.

---

## D-12 — o ficheiro de prontidão respondia 0 ao hang

**Onde.** `app/webview/sotto_webview.py`: `_arm_panel_stall_watch` (25 s) → `_complete_startup` →
`mark_launch_ready`; contrato em `app/webview/run.cmd:64-70` e `:312-319`.

**Antes.** O vigia de 25 s completa o arranque **com a página do painel ainda pendurada** (é o motivo
de ele existir: a legenda não depende da página) e chamava `_complete_startup`, que fazia
`mark_launch_ready(self.args.ready_file)`. `run.cmd` promete, por palavras, o contrário: *"the shell
touches it once the panel navigation has completed, and run.cmd waits for it, BOUNDED, exiting 4 on
timeout"*. O G3 nasceu de um caso medido (2026-10-06): `STAGING_LOADED` e mais nada, e o largador a
responder **0**. O caminho dos 25 s reintroduzia exactamente esse falso positivo — para um painel
branco, sem documento nenhum.

**Depois.** `_mark_launch_ready(panel_loaded)`:

* `panel_loaded=True` (o `_on_loaded` do painel, i.e. a navegação completou) → escreve o ficheiro;
* `panel_loaded=False` (o caminho dos 25 s) → **não escreve** e diz
  `LAUNCH_READY_WITHHELD path=... why=panel-nav-stalled`. O `run.cmd` dá rc=4 e escreve `HANG`; a app
  continua a correr, porque foi largada destacada (`start ""`) e a legenda já está de pé.

**Medido** (`_main/panel-nav-stall-oracle.py`, o método REAL nos dois estados):

```
ARM 3 — o ficheiro de prontidao so aparece quando o painel carregou
  [PASS] C1 stall path: ficheiro AUSENTE e a linha diz por que — existe=False
         linhas=["LAUNCH_READY_WITHHELD path='...ready.txt' why=panel-nav-stalled"]
  [PASS] C2 painel carregado: o ficheiro aparece com o pid — conteudo='ready pid=21460'
VERDICT: PASS
```

**Controlo.** O negativo deste oráculo conhecia **um** mutante (o retry inline, de 2026-11-05). Entrou o
segundo, que arranca a guarda numa cópia:

```
NEG-ARM PASS — os dois mutantes sao apanhados pelas SUAS arms   (rc=1)
  B1 retry inline  -> a conclusao fica refem do load_url
  B2 guarda fora   -> o ficheiro ESCRITO com o painel pendurado (o defeito)
```

**Estado.** corrigido; **não verificado** — o rc=4 do `run.cmd` só se mede com uma largada real pela
mão dele, e um painel que não carrega não se reproduz a pedido.

---

## D-13 — a ordem do dono dependia da porta de entrada

**Onde.** `app/webview/sotto_webview.py` (`_child_env`, `autostart_command`),
`app/webview/run.cmd:113,140`.

**Antes.** `run.cmd` escreve `if not defined SOTTO_REDUX_LIVE set "SOTTO_REDUX_LIVE=1"` no processo da
shell, e o shell passa `os.environ` ao worker — logo uma abertura por `run.cmd` tem o passe de lote do
parakeet LIGADO (ordem do dono de 2026-10-18). O autostart do logon **não** passa por `run.cmd`:
`autostart_command()` larga `"pythonw.exe" "sotto_webview.py" --log ...`, e não pode largar um `.cmd`
(um `.cmd` é consola, e uma consola no ecrã dele é proibida — medido e reclamado). A escada do worker é
flag → ambiente → config (`worker/sotto_worker.py:5803`) com `worker/config.json` `"enabled": false`:
no logon o passe de lote corria **desligado**, e o mesmo binário tinha dois comportamentos conforme
quem o abriu.

**Depois.** `env.setdefault('SOTTO_REDUX_LIVE', '1')` em `_child_env`, ao lado de
`SOTTO_REDUX_WHEN_HIDDEN='1'` (que já fazia exactamente isto): a decisão vive onde **toda** abertura
passa, e um `SOTTO_REDUX_LIVE=0` explícito continua a ganhar.

**Medido** (`_main/app-target-oracle.py`, arm `e`, com o ambiente apagado por `mock.patch.dict`):

```
  ARM e  [GREEN]  no target -> no SOTTO_TARGET_PID
    sem a variavel (logon): o filho recebe SOTTO_REDUX_LIVE=1
    um 0 explicito do dono continua a ganhar
VERDICT: PASS  live=GREEN(9/9)  M1 env line removed=RED-as-expected(['d'])  M2 tree-root rule removed=RED-as-expected(['b'])
```

O contrato byte-a-byte daquele oráculo (`env == os.environ + SOTTO_CAPTURE_MODE +
SOTTO_REDUX_WHEN_HIDDEN, nada mais`) foi actualizado com a chave nova e o comentário que diz porquê.

**Bónus, e a razão de a dívida do oráculo ser o mesmo defeito:** o `app-target` tinha **zero**
chamadores na bateria (`battery-wiring` contava-o em `sem_passo`) e o banco de ensaio dele apodreceu —
`FakeShell` não tinha `on_worker_cost`, a arma `g` morria em `AttributeError` e o oráculo publicava
FAIL sobre um caminho que nunca correu. Reparado, com passo próprio no par `app-target` +
`red-as-expected-app-target` (`always`, porque lê a tabela de processos viva), e a dívida congelada
apagada do `battery-wiring-baseline.json` (`ligados=199 sem_passo=107`, PASS 7/7).

**Estado.** corrigido; **não verificado** — a abertura do logon só se mede no próximo logon dele.

---

## D-14 — o motor quente é morto pelo pid, e o código diz que não pode

**Onde.** `app/webview/sotto_webview.py`: `_exit_children` (17344-17360), `_WarmChild` (24780-24805),
`_reap_children_for_exit`, `_hard_exit`; `app/webview/exit_killer.py:118-148`.

**Medido por leitura (2026-11-12).** `request_exit` lê `_kids = self._exit_children()` **antes** de
`bridge.stop('exit')`. Com `--warm-engine-keep` desligado (o default; a `--help` diz *"closing Sotto is
a request to stop paying 1.9 GB"*), `bridge.keep_warm` é `False`, logo o `_WarmChild` **entra** na
lista. Aí:

* `_reap_children_for_exit` chama `child.kill()` → o shim **levanta de propósito**
  (`RuntimeError('the shell does not own the warm engine')`) → `EXIT_CHILD_KILL_FAILED`;
* a seguir `child.wait(timeout=...)` → `AttributeError` → `EXIT_CHILD_STUCK ... owner=killer`;
* e o `exit_killer` mata o pid de qualquer maneira (`EXIT_KILLER_CHILD`/`EXIT_KILLER_ORPHAN`).

Nada se perde — o matador é a garantia de que os 1,9 GB vão embora, e é o que a `--help` promete. O que
está errado é **o registo**: duas linhas por saída a dizer que a shell tentou matar e não conseguiu o
que ela nunca possuiu, ao lado de um docstring (`_WarmChild`) e de outro (`_exit_children`) que dizem
que o warm fica **fora** do kill.

**Decisão nomeada (não executada).** Separar as duas listas em `_hard_exit`: `children` (matar +
recolher) e `backstop_pids` (só o matador externo). O warm viaja no segundo, o worker e a sidecar no
primeiro, e as duas linhas mentirosas desaparecem. Custo: uma assinatura e um chamador; ganho: o log
da saída passa a descrever o que aconteceu. **Aberto** — não é dinheiro barato num caminho de saída
que já tem 11 arms e dois matadores.

---

## D-15 — a medição escrevia o estado que a app do dono obedece

**Onde.** `app/webview/sotto_webview.py`: `measurement_lock_name` (8712), `isolated_state_path`
(15460, antes), `start_panel_visibility` (15405), `panel_visibility_snapshot`, `worker_argv_tail`
(23201) e a decisão de lock em `main()` (26277).

**Medido por leitura e por execução (2026-11-12).** A pergunta "esta largada é a app ou uma medição?"
estava escrita **duas vezes**, e as duas cópias discordavam:

* o **lock** pergunta `_measurement_flag(args)` e cai em `measurement_lock_name` →
  `--probe-v2` toma `Local\SottoShell.m.probe_v2`;
* a **isolação do estado** perguntava `args.mutex_name != DEFAULT_MUTEX_NAME`, e uma largada de
  medição **não toca** em `--mutex-name`.

Logo as nove flags da família (`--dump-dom`, `--selftest`, `--memory`, `--no-hotkey`, `--exit-after`,
`--probe-v2`, `--probe-stats`, `--probe-outside-click`, `--probe-edit-mode`) corriam com lock privado
e **escreviam `_main\panel-state.json` e `_main\panel-visibility.json` por cima dos ficheiros da app
viva**. O segundo não é cosmético: `worker/engine_switch.py:478` (`PanelVisibilityReader`) decide
parque pelo `visible` e o nível pelo `shed`, e o payload de uma sonda diz `visible=false` e **não tem**
`park`/`shed` — ou seja a sonda dizia ao worker do dono "estou escondido" e apagava-lhe o nível de
shedding. O `panel_visibility_snapshot` ainda publicava `'path': PANEL_VISIBILITY_PATH`, o ficheiro
que a medição **não** escrevia.

```
ANTES (HEAD 1d6578d)                       DEPOIS (working tree)
lock  = Local\SottoShell.m.probe_v2         lock  = Local\SottoShell.m.probe_v2
state = .\_main\panel-state.json            state = .\_main\panel-state.Local_SottoShell.m.probe_v2.json
visib = _main\panel-visibility.json         visib = _main\panel-visibility.Local_SottoShell.m.probe_v2.json
argv  = []                                  argv  = ['--panel-visibility', '...\panel-visibility.Local_SottoShell.m.probe_v2.json']
```
(script de duas linhas que carrega a shell do `git show HEAD` e a do disco e chama as funções puras;
nenhuma largada, nenhum dispositivo, nenhuma janela)

**A cura.** **UMA** pergunta — `is_measurement_launch(args)` — responde por tudo, e o sufixo do estado
é **o nome que o lock toma** (`measurement_state_tag` → `measurement_lock_name`), pelo que as duas
decisões não podem divergir outra vez. `isolated_state_path` delega em `isolated_state_file`;
`start_panel_visibility` passa pelo mesmo caminho que o `panel-state` já usava; o snapshot publica
`writer.path`; e `worker_argv_tail` entrega ao worker `--panel-visibility <ficheiro isolado>` para
que a medição leia o ficheiro que ela própria escreve. A app do dono fica **byte a byte** igual: sem
flag de medição e com o mutex por omissão, o caminho é o de sempre e nenhuma flag nova entra no argv.

**Portão.** `_main/measurement-isolation-oracle.py` — 15 arms, **sem largar a app**: as nove flags, o
argv do worker, as duas metades estruturais (o corpo real de `start_panel_visibility` e do snapshot) e
um passo **vivo** que executa o `start_panel_visibility` real contra um root temporário e exige a
escrita no ficheiro isolado com o ficheiro da app **inexistente**. Medido: `VERDICT: PASS -- 15/15` e
`NEG-ARM: PASS -- 3/3` (M1 tira a isolação do writer, M2 repõe o predicado antigo, M3 tira a flag do
argv do worker; cada mutante cai pela sua arm, rc=1 ao apanhar). Passos `measurement-isolation` +
`red-as-expected-measurement-isolation` na bateria.

**Estado.** `corrigido, NÃO verificado` — o processo do dono corre código anterior; o que está medido
é a função e o writer reais, não uma abertura da app dele.

---

---
---
---

## O que este ledger NÃO afirma

- Não afirma que o produto está quebrado fora do que está medido acima.
- Não classifica nenhuma jornada como `verified`: `verified` exige o processo do dono a correr ESTE
  código, e a lei do `STALE` continua a valer.
- Não copia números de outros documentos: cada `[MEASURED]` acima traz o comando que o produziu.
