# As LEIS da legenda do YouTube no Sotto -- CLAIMS ONLY.
#
# O DONO, 2026-10-22, verbatim:
#     *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou nao,
#     igual o youtube."*
#     *"tem que bater timing, linha/quebra de linha e etc, 1:1."*
#
# O QUE ESTE FICHEIRO PROVE, e o que NAO prova.
#
# PROVE: as DECISOES PURAS do caminho 1:1 -- quantas palavras de uma linha o
# YouTube ja revelou num instante, se uma linha esta viva nesse instante, e
# quantas linhas a janela mostra -- E, desde 2026-10-30, a ORDEM DO EPOCH DE
# FONTE da legenda propria (DECISAO 5, no fim deste ficheiro): o epoch nunca
# decresce, uma pintura so carrega o epoch corrente, e a fonte nova comeca com
# a fila vazia e os pixeis limpos. Cada `law` e um enunciado sobre o modelo
# abaixo, quantificado sobre TODAS as entradas do seu dominio, verificado pelo
# kernel (Lean 4.34 via BendTT).
#
# NAO PROVE, e por isso nao se afirma aqui:
#
#   1. O ORCAMENTO DE TEMPO (o "quase 1:1" do dono). Uma lei prova uma ORDEM,
#      nunca um milissegundo. O drift e medido pelo falsificador
#      `_main/youtube-drift-oracle.py`, que imprime `drift_ms` por linha contra
#      a linha do tempo do proprio YouTube. Nao existe "synced" booleano aqui.
#   2. O DESENHO NO ECRA DO DONO. A lei prova o DADO que entra no overlay; o
#      overlay nativo (`app/webview/caption_overlay.py`) e o que ele VE, e os
#      mirrors (`_main/youtube-reveal-oracle.py`, `_main/youtube-rows-oracle.py`)
#      amarram as leis as funcoes de PRODUCAO.
#   3. A INTENCAO. Uma lei prova o enunciado escrito, nao o enunciado que o
#      dono queria.
#
# A DIVISAO (a mesma de consultgpt, 2026-10-28). Este ficheiro tem DECLARACOES
# e o MODELO de que elas precisam. As PROVAS vivem em `bend_core/PROOF.bend`, um
# `def Laws.<nome>` por lei -- a forma que o Bend 2 documenta. MEDIDO em bend
# 2.0.39: um def nomeado `<alias>.<law>` PREENCHE uma lei declarada noutro
# ficheiro (inclusive com nome pontuado), e `bend PROOF.bend --verdict` imprime
# ALL PROOFS CHECK (rc=0). O Bend tambem RECUSA um PROOF.bend ao lado de um
# LAWS.bend que ele nao importa, de modo que o par nao se separa em silencio.
#
# QUEM ESCREVE O QUE. A convencao a montante e "um humano escreve as leis, um
# agente escreve as provas". E uma convencao, nao um limite de capacidade: um
# agente pode escrever as duas. O que a divisao compra e SEPARACAO DE REVISAO
# -- mudar uma lei e um diff diferente de mudar a sua prova.
#
# AS RESTRICOES DO BEND, e como este modelo as cumpre. Todas MEDIDAS em bend
# 2.0.39 neste ficheiro (e nao por suposicao):
#
#   1. O `List<a>` do Base exige um `Quant` como primeiro argumento das suas
#      funcoes, e um tipo `Data` como `Tok` nao e um `Quant` -> "expected :
#      Quant, observed : Data". Por isso o modelo declara as proprias listas
#      (`Toks`), que sao `Data` como o resto.
#   2. O Bend NAO TEM `if` (o guia: *"There is also no `if` syntax yet. Use
#      `match` on `True{}` and `False{}` instead"*), e um `match` nao pode
#      scrutinizar um valor COMPUTADO ("a match cannot scrutinize a computed
#      value"). Logo as duas implementacoes do modelo sao o `Bool.pick` (que
#      aceita uma condicao computada -- MEDIDO) e o `match` sobre um VALOR
#      (que so aceita um parametro ou um valor ligado por padrao).
#   3. NAO HA RECUSAO MUTUA (o guia: *"mutual recursion is not allowed"*), e um
#      def so pode chamar um def ANTERIOR ou a si mesmo. Por isso cada recursao
#      esta num unico def, e os lemmas vem ANTES de quem os usa.
#   4. O Bend e AFIL: um valor nao pode ser usado duas vezes (MEDIDO: "expected
#      : b, observed : b (consumed more than once)"). Os parametros que uma
#      prova precisa de mencionar mais de uma vez sao marcados `+` (apagados),
#      e o `+` propaga-se do binder da LEI para o parametro do def que a prova
#      (MEDIDO: uma lei com `for +a: Nat` aceita um def de prova que usa `a`
#      duas vezes) E para o que o `match` liga sobre um parametro apagado
#      (MEDIDO: com `for +toks`, o `tail` ligado pelo `match` pode aparecer no
#      comprimento E na contagem; sem o `+`, o mesmo `tail` da "consumed more
#      than once").
#
# Verify:  bash tools/bend_verify.sh          (leis + provas + controlos + guardas)
#          python _main/bend_mirror.py         (as leis contra a producao real)
#          cd bend_core && bend PROOF.bend --verdict   (o portao das provas)
#          cd bend_core && bend LAWS.bend              (so as afirmacoes: reports
#                                                       cada lei como claim aberto)
# Toolchain: docs/bend/BEND_PROOFS_REFERENCE.md, docs/bend/BEND_LAW_GUIDE.md
#
# MEDIDO 2026-11-08: o portao deste repositorio e `tools/bend_verify.sh` (ele
# existe AQUI desde 2026-10-30; a nota anterior dizia o contrario e estava
# errada). Ele fixa o INVENTARIO de leis e o CONJUNTO de controlos, e por isso
# acrescentar uma lei aqui exige acrescentar a linha nos DOIS pins de la
# (senao o gate sai 5 / 3). O portao das PROVAS e, e sempre foi,
# `bend PROOF.bend --verdict`.

import Base

# ---------------------------------------------------------------------------
# O MODELO
#
# Tres entidades, e so tres, porque sao as que as decisoes do caminho 1:1
# manipulam:
#
#   Tok  -- uma PALAVRA da legenda, com o instante ABSOLUTO em que o player a
#           escreve (`tOffsetMs` do payload do YouTube). A palavra e o que o
#           player REVELA, palavra a palavra.
#   Toks -- as palavras de uma linha, por ordem.
#   Cue  -- uma LINHA da janela, com o instante em que comecou e o em que acaba.
#
# Os numeros sao `Nat` porque o tempo do payload e em MILISSEGUNDOS, e a lei
# nao precisa de mais precisao para afirmar ORDEM.
# ---------------------------------------------------------------------------

type Tok is Data:
  Tok{at_ms: Nat}

type Toks is Data:
  ToksNil{}
  ToksCon{head: Tok, tail: Toks}

type Cue is Data:
  Cue{start_ms: Nat, end_ms: Nat}

# ---------------------------------------------------------------------------
# PRIMITIVAS
# ---------------------------------------------------------------------------

def Tok.at_ms(tok: Tok) -> Nat:
  match tok:
    case Tok{at_ms}:
      at_ms

def Toks.length(toks: Toks) -> Nat:
  match toks:
    case ToksNil{}:
      0n
    case ToksCon{head, tail}:
      (1n + Toks.length(tail) : Nat)

def Cue.start_ms(cue: Cue) -> Nat:
  match cue:
    case Cue{start_ms, end_ms}:
      start_ms

def Cue.end_ms(cue: Cue) -> Nat:
  match cue:
    case Cue{start_ms, end_ms}:
      end_ms

# ---------------------------------------------------------------------------
# DECISAO 1 -- A PALAVRA JA CHEGOU?
#
# E a definicao do "revelado" no YouTube: o player escreve a palavra quando
# chega a sua hora. MEDIDO no payload de `WdaHAGRBB6s`: 69 dos 106 segmentos
# trazem `tOffsetMs`, e o player revela `Have` em 0 ms, ` you` em 240 ms,
# ` ever` em 400 ms. A PRODUCAO e `youtube_window.revealed_text`, que inclui a
# palavra sse `word.start <= t`.
#
# O MODELO tem DUAS implementacoes do mesmo indicador, e a lei que as amarra e
# a que apanha o sinal trocado:
#
#   * `Nat.of_bool` -- o `match` sobre o valor (`True{}`/`False{}`);
#   * `Nat.revealed_flag` -- o `Bool.pick`, que aceita uma condicao COMPUTADA
#     (a comparacao `at_ms <= t_ms`), que e a forma que a producao usa.
#
# As duas sao deliberately DIFERENTES no codigo, e a lei diz que concordam.
# ---------------------------------------------------------------------------

# O indicador, via `match` sobre o valor.
def Nat.of_bool(b: Bool) -> Nat:
  match b:
    case True{}:
      1n
    case False{}:
      0n

# O indicador, via `Bool.pick` sobre a condicao computada.
def Nat.revealed_flag(due: Bool) -> Nat:
  Bool.pick(Nat, due, 1n, 0n)

# REJECTS: um indicador que devolvesse o VALOR em vez do booleano (por exemplo
# a diferenca `t_ms - at_ms`). Uma palavra em 240 ms, instante 1000 ms: o
# indicador e 1, e um modelo que devolvesse a diferenca daria 760.
law Nat.revealed_flag_is_zero_or_one:
  for due: Bool
  {Nat.is_le(Nat.revealed_flag(due), 1n) == True{} : Bool}

# AS DUAS FORMAS DO INDICADOR SAO A MESMA. O `match` sobre o valor e o
# `Bool.pick` sobre a condicao computada sao as duas formas que o codigo usa
# (uma onde o booleano ja existe, outra onde e preciso de o computar), e a lei
# diz que concordam palavra a palavra.
#
# REJECTS: uma das duas formas com o SINAL TROCADO -- `of_bool` devolvendo 0
# em `True{}`, ou `revealed_flag` devolvendo 1 em `False{}`. As duas sao
# simetricas, e por isso esta lei e a que amarra as duas metades do indicador.
law Nat.of_bool_agrees_with_revealed_flag:
  for due: Bool
  {Nat.of_bool(due) == Nat.revealed_flag(due) : Nat}

# ---------------------------------------------------------------------------
# DECISAO 2 -- QUANTAS PALAVRAS DE UMA LINHA JA FORAM REVELADAS.
#
# O MODELO soma o indicador de cada palavra. A contagem e a que a producao
# materializa como PREFIXO: `youtube_window.revealed_text` filtra as palavras
# por `word.start <= t` e junta-as, e `youtube_reveal.first_words` corta o
# texto do cue no numero de palavras que o player ja pintou.
# ---------------------------------------------------------------------------

# A palavra `tok` ja chegou no instante `t_ms`?
def Tok.due(tok: Tok, +t_ms: Nat) -> Bool:
  Nat.is_le(Tok.at_ms(tok), t_ms)

# Quantas palavras de `toks` ja chegaram no instante `t_ms`.
def Toks.count_due(toks: Toks, +t_ms: Nat) -> Nat:
  match toks:
    case ToksNil{}:
      0n
    case ToksCon{head, tail}:
      (Nat.revealed_flag(Tok.due(head, t_ms)) + Toks.count_due(tail, t_ms) : Nat)

# REJECTS: uma contagem que devolvesse o numero TOTAL de palavras da linha,
# sem olhar o relogio. Uma linha com uma palavra em 240 ms e um instante de
# 1000 ms: a contagem e 1, e um modelo que devolvesse `length` daria 1 tambem
# -- por isso a lei da MONOTONIA (abaixo) e a que apanha esse modelo.
law Toks.count_due_counts_only_due_words:
  for +toks: Toks
  for +t_ms: Nat
  {Nat.is_le(Toks.count_due(toks, t_ms), Toks.length(toks)) == True{} : Bool}

# A LINHA VAZIA: nao ha nada a revelar. E a fronteira que um modelo que
# devolvesse sempre 1 (o "conta tudo") violaria.
#
# REJECTS: um modelo com a BASE da contagem em 1 (o `+1` no caso vazio -- um
# `length` que conta tambem o terminador da lista): numa linha vazia daria 1,
# e a contagem do YouTube e 0.
law Toks.count_due_of_an_empty_line_is_zero:
  for t_ms: Nat
  {Toks.count_due(ToksNil{}, t_ms) == 0n : Nat}

# A LINHA DE UMA PALAVRA: a contagem e o indicador dessa palavra. E a lei que
# recusa um modelo que devolvesse sempre 0 (nunca revelava nada) e um que
# devolvesse sempre 1 (revelava tudo).
#
# REJECTS: o sempre-0 e o sempre-1. Com uma palavra em 240 ms: no instante
# 1000 ms a contagem e 1 (o sempre-0 daria 0); no instante 0 ms a contagem e 0
# (o sempre-1 daria 1). Um modelo que ignorasse `t_ms` nao passa nos dois.
law Toks.count_due_of_one_word_is_its_flag:
  for tok: Tok
  for t_ms: Nat
  {Toks.count_due(ToksCon{tok, ToksNil{}}, t_ms)
     == Nat.revealed_flag(Nat.is_le(Tok.at_ms(tok), t_ms)) : Nat}

# A MONOTONIA: revelar mais tarde nunca revela MENOS. E a propriedade que
# distingue "contar as palavras que ja passaram" de "devolver o total".
#
# REJECTS: uma revelacao decrescente (um modelo que, ao passar do tempo,
# devolvesse MENOS palavras reveladas) e um modelo com o sinal trocado. Com
# uma palavra em 240 ms: `count_due(0) = 0` e `count_due(1000) = 1`; o sinal
# trocado daria o contrario.
law Toks.count_due_is_monotone_in_time:
  for +toks: Toks
  for +t1_ms: Nat
  for +t2_ms: Nat
  for +h: {Nat.is_le(t1_ms, t2_ms) == True{} : Bool}
  {Nat.is_le(Toks.count_due(toks, t1_ms), Toks.count_due(toks, t2_ms)) == True{} : Bool}

# ---------------------------------------------------------------------------
# DECISAO 3 -- A LINHA ESTA VIVA?
#
# O payload declara a janela em `wpWinPositions[1]`: `rcRows: 2` (duas linhas) e
# `ccCols: 40`.
#
# A REGRA DA VIDA: uma linha esta VIVA se COMECOU e ainda NAO ACABOU. O
# intervalo e MEIO-ABERTO de proposito: duas linhas que se tocam (uma acaba
# exactamente quando a outra comeca) nunca sao vivas as duas, e o `rcRows` nunca
# e excedido. A PRODUCAO e `youtube_window._live_cues`, que testa
# `start <= t < end`.
#
# O MODELO recebe os DOIS FATOS -- "ja comecou" e "ja acabou" -- e decide. A
# lei amarra essa decisao a `and(started, not(ended))`, que e o enunciado
# escrito do YouTube.
# ---------------------------------------------------------------------------

# A linha esta viva: comecou e nao acabou.
def Nat.live_flag(started: Bool, ended: Bool) -> Bool:
  Bool.pick(Bool, started, Bool.pick(Bool, ended, False{}, True{}), False{})

# REJECTS: uma vitalidade que ignorasse o FIM da linha (`live = started`), uma
# que confundisse o sinal (`live = ended`), e uma vitalidade sempre verdadeira
# (`live = True{}`). Com os quatro pares de fatos, a lei exige exactamente o
# comportamento do YouTube: viva so quando comecou e ainda nao acabou.
law Nat.live_flag_is_started_and_not_ended:
  for started: Bool
  for ended: Bool
  {Nat.live_flag(started, ended) == Bool.and(started, Bool.not(ended)) : Bool}

# O ESTADO INICIAL: uma linha que ainda nao comecou nao esta viva. E a lei que
# recusa uma vitalidade que so olhasse para o fim.
#
# REJECTS: uma vitalidade que so olhasse para o FIM (`live = not(ended)`), que
# declara viva uma linha que ainda nao comecou, e uma vitalidade constante
# (`live = True{}`). Com `started = False{}` a resposta do YouTube e `False{}`
# para os dois valores de `ended`, e as duas dariam `True{}` num deles.
law Nat.live_flag_is_false_before_the_line_starts:
  for ended: Bool
  {Nat.live_flag(False{}, ended) == False{} : Bool}

# ---------------------------------------------------------------------------
# DECISAO 4 -- QUANTAS LINHAS A JANELA MOSTRA.
#
# A janela mostra as linhas VIVAS, e no maximo `rcRows` (duas). A PRODUCAO e
# `youtube_reveal.window_by_paint`, que corta a janela com
# `out[-max(1, capacity + ROLLUP_ROWS):]`.
#
# O MODELO: o numero de linhas mostradas e o MINIMO entre as linhas vivas e a
# capacidade. A lei amarra o `Bool.pick` (a forma da producao) ao `Nat.min`
# (a forma de referencia), e a lei seguinte diz que a janela NUNCA excede a
# capacidade -- que e o que impede a janela de mostrar tres linhas quando o
# YouTube mostra duas.
#
# REJECTS: uma janela que mostrasse MAIS linhas do que a capacidade (o
# `capacity + 1` sem o `ROLLUP_ROWS` certo, ou um `+1` a mais), e uma janela
# que escondesse linhas vivas.
law Nat.window_rows_is_the_minimum:
  for +live_rows: Nat
  for +capacity: Nat
  {Nat.window_rows(live_rows, capacity) == Nat.min(capacity, live_rows) : Nat}

# O TETO DA JANELA: nunca mais linhas do que a capacidade. E a lei que recusa
# o `+1` a mais.
#
# REJECTS: o `capacity + 1` do `ROLLUP_ROWS` contado a mais -- um
# `min(capacity + 1, live_rows)`: com 3 linhas vivas e capacidade 2 mostraria 3,
# e o YouTube mostra 2.
law Nat.window_rows_never_exceeds_the_capacity:
  for +live_rows: Nat
  for +capacity: Nat
  {Nat.is_le(Nat.window_rows(live_rows, capacity), capacity) == True{} : Bool}

# E NUNCA MAIS LINHAS DO QUE AS VIVAS: a janela nao inventa linhas.
#
# REJECTS: uma janela que INVENTASSE linhas -- o `max(live_rows, capacity)` no
# lugar do `min`, ou um `capacity` devolvido sem olhar as vivas: com uma linha
# viva e capacidade 2 mostraria 2, e o YouTube mostra 1.
law Nat.window_rows_never_exceeds_the_live_rows:
  for +live_rows: Nat
  for +capacity: Nat
  {Nat.is_le(Nat.window_rows(live_rows, capacity), live_rows) == True{} : Bool}

# ---------------------------------------------------------------------------
# A CAPACIDADE DA JANELA, vista de fora.
#
# `Nat.window_rows` e a DECISAO; a capacidade que entra nela e um dado do
# payload (`rcRows: 2` mais a linha que rola para fora, MEDIDO: 3 linhas
# visiveis em 4 das 16 amostras do video `WdaHAGRBB6s`).
# ---------------------------------------------------------------------------

def Nat.window_rows(+live_rows: Nat, +capacity: Nat) -> Nat:
  Bool.pick(Nat, Nat.is_le(capacity, live_rows), capacity, live_rows)

# ===========================================================================
# DECISAO 5 -- A ORDEM DO EPOCH DE FONTE (2026-10-30)
#
# O DONO, 2026-10-30, verbatim: *"a legenda do audio anterior aparece no audio
# novo"*. O defeito nao e' de texto nem de timing: e' de ORDEM -- um texto
# enfileirado para uma fonte de audio e' pintado quando a fonte ja e' outra.
#
# O FATO MEDIDO, em `app/webview/sotto_webview.py` (numeros de linha lidos no
# ficheiro a 2026-10-30):
#
#   * `_blank_caption_window` (:15775) faz
#         self._source_epoch = int(getattr(self, '_source_epoch', 0)) + 1
#         self._caption_pending = None
#     e depois esconde o overlay (`ov.show(False)`) -- limpa pixeis E fila.
#   * `start_worker` (:15459) faz AS MESMAS duas linhas quando um worker arranca
#     (`self._source_epoch = int(...) + 1`, `self._caption_pending = None`):
#     "UM WORKER NOVO E' UMA FONTE NOVA". Nao mexe nos pixeis.
#   * `push_caption_to_window` (:16230) grava no slot UNICO
#         (now, text, previous, int(getattr(self, '_source_epoch', 0)))
#     -- o texto viaja com o epoch COM QUE FOI ENFILEIRADO.
#   * `_drain_caption_pending` (:15979-...) compara ANTES de pintar:
#         cur = int(getattr(self, '_source_epoch', 0))
#         if epoch != cur: log CAPTION_DROP_EPOCH ...
#         ov.set_text(...)
#
# O QUE ESTE MODELO PROVE: a ordem do epoch e' a ordem das fontes. Um epoch
# que nunca decresce; um texto estampado com E so pinta com o epoch corrente
# igual a E; e a transicao para uma fonte nova deixa o widget LIMPO (fila
# vazia, nada no ecra), de modo que o primeiro texto da fonte nova e' o
# primeiro texto escrito depois dessa limpeza.
#
# O QUE NAO PROVE: que existe UM slot so (e' a producao que o garante, e o
# `_drain` e' um `_post` na thread de UI); que a thread de UI corre quando o
# modelo diz; nem o orcamento de tempo (o "quase 1:1"), que continua a ser
# medido por `_main/youtube-drift-oracle.py`. Um `CAPTION_DROP_EPOCH` no log e'
# o modelo a funcionar -- e nao prova nenhuma; a prova e' este ficheiro.
#
# A REACHABILITY (F-6), nomeada: `start_worker` e `_blank_caption_window` sao
# os DOIS sitios que incrementam o epoch, e ambos limpam a fila; o
# `_caption_idle_hide` chama o segundo a cada 6 s de silencio (linhas
# `CAPTION_WINDOW_IDLE_HIDDEN` no log de 2026-10-17 citadas no proprio
# docstring). O `push` seguinte carimba o epoch novo, e o `_drain` que corre
# depois de um arranque ou de um blank e' o input que as tres leis restringem.
# ===========================================================================

# O SLOT: o unico texto enfileirado, com o epoch com que foi carimbado.
type Slot is Data:
  SlotIdle{}
  SlotHeld{stamp: Nat}

# O ESTADO DO WIDGET: o epoch da fonte, o slot, e se ha pixeis no ecra.
type Cap is Data:
  Cap{epoch: Nat, slot: Slot, shown: Bool}

# OS ACONTECIMENTOS. Sao exactamente os quatro sitios da producao acima.
type Ev is Data:
  EvNewSource{}
  EvBlank{}
  EvPush{}
  EvDrain{}

# Uma sequencia de acontecimentos: uma sessao.
type Evs is Data:
  EvsNil{}
  EvsCon{head: Ev, tail: Evs}

def Cap.epoch(c: Cap) -> Nat:
  match c:
    case Cap{epoch, slot, shown}:
      epoch

def Cap.slot(c: Cap) -> Slot:
  match c:
    case Cap{epoch, slot, shown}:
      slot

def Cap.shown(c: Cap) -> Bool:
  match c:
    case Cap{epoch, slot, shown}:
      shown

def Slot.is_idle(slot: Slot) -> Bool:
  match slot:
    case SlotIdle{}:
      True{}
    case SlotHeld{stamp}:
      False{}

# O EPOCH E' O MESMO? A forma ESTRUTURAL -- o `match` sobre os dois numeros,
# que e' a forma que a guarda `epoch != cur` da producao tem depois de o
# compilador lhe tirar a negacao.
def Nat.same_epoch(a: Nat, b: Nat) -> Bool:
  match a b:
    case 0n 0n:
      True{}
    case 0n 1n+bp:
      False{}
    case 1n+ap 0n:
      False{}
    case 1n+ap 1n+bp:
      Nat.same_epoch(ap, bp)

# A DECISAO DO `_drain`: pintar (1) ou largar (0). A PRODUCAO larga quando
# `epoch != cur`; o modelo devolve o indicador da IGUALDADE, que e' a mesma
# guarda com a negacao resolvida, e a lei abaixo amarra-o a uma segunda
# implementacao da igualdade (`Cmp.is_eq(Nat.cmp(..))`, a que o Base ja tem).
def Nat.paint_flag(stamp: Nat, +cur: Nat) -> Nat:
  Nat.revealed_flag(Nat.same_epoch(stamp, cur))

# ---------------------------------------------------------------------------
# LEI 2 -- UMA PINTURA SO CARREGA O EPOCH CORRENTE.
#
# A guarda do `_drain` e' uma igualdade, e o modelo diz isso dos DOIS lados:
# epoch igual pinta, epoch diferente nao pinta. A igualdade do modelo
# (`Nat.same_epoch`, estrutural) e' amarrada a uma SEGUNDA implementacao da
# mesma igualdade (`Cmp.is_eq(Nat.cmp(..))`, a que o Base ja traz) -- e por
# isso a lei nao passa nem com "nunca pinta" (o lado do igual falharia) nem com
# "pinta sempre" (o lado do diferente falharia). Uma implicacao escrita com
# `for h:` nao apanhava o "nunca pinta" (F-6b, BEND_PROOFS_REFERENCE.md §8):
# uma premissa impossivel dispensa qualquer conclusao.
#
# REJECTS: o `_drain` ANTERIOR a 2026-10-30, que pintava o que estivesse no
# slot sem comparar nada -- a legenda do audio anterior no audio novo. Uma
# guarda trocada (`stamp <= cur`, "pinta tudo o que nao venha do futuro")
# tambem nao passa: com o carimbo 2 e o epoch 1 as duas respostas diferem.
law Nat.no_cross_source_paint:
  for +stamp: Nat
  for +cur: Nat
  {Nat.paint_flag(stamp, cur)
     == Nat.of_bool(Cmp.is_eq(Nat.cmp(stamp, cur))) : Nat}

# A FONTE NOVA (`start_worker`): epoch + 1 e a fila limpa. Os pixeis ficam --
# esta transicao nao chama `ov.show(False)`.
#
# As transicoes leem o estado pelas PROJECCOES (`Cap.epoch(c)`) e nao por um
# `match` sobre `c`. Nao e' estilo: um `match` sobre uma variavel nao reduz
# enquanto o kernel nao a divide, e por isso `Cap.epoch(Cap.on_blank(c))`
# ficaria preso com `c` neutro -- um `def` que constroi o construtor deixa a
# projeccao reduzir (iota) em qualquer estado. MEDIDO: a versao com `match`
# dentro das transicoes recusou a prova de `epoch_step_le` com
# "expected: is_le(epoch, Cap.epoch(Cap.on_drain(Cap{...})))".
def Cap.on_new_source(+c: Cap) -> Cap:
  Cap{Nat.add(1n, Cap.epoch(c)), SlotIdle{}, Cap.shown(c)}

# O BLANK (`_blank_caption_window`): epoch + 1, fila limpa e pixeis limpos. E a
# transicao que a lei 3 restringe, linha a linha.
def Cap.on_blank(+c: Cap) -> Cap:
  Cap{Nat.add(1n, Cap.epoch(c)), SlotIdle{}, False{}}

# O PUSH (`push_caption_to_window`): o texto carimba o epoch CORRENTE e
# sobrescreve o slot -- o epoch aparece duas vezes porque o carimbo e' o epoch
# do estado, e por isso o parametro e' apagado.
def Cap.on_push(+c: Cap) -> Cap:
  Cap{Cap.epoch(c), SlotHeld{Cap.epoch(c)}, Cap.shown(c)}

# A guarda do drain, vista do SLOT: e' este Bool que decide a pintura. E a
# MESMA igualdade que `Nat.paint_flag` (aqui o Bool, la o indicador 0/1), e a
# lei 2 e' a que amarra essa igualdade a segunda implementacao do Base.
def Slot.paints(slot: Slot, +cur: Nat) -> Bool:
  match slot:
    case SlotIdle{}:
      False{}
    case SlotHeld{stamp}:
      Nat.same_epoch(stamp, cur)

# O DRAIN (`_drain`): o slot esvazia-se sempre (foi consumido), e os pixeis
# so mudam quando a guarda deixa pintar.
def Cap.on_drain(+c: Cap) -> Cap:
  Cap{Cap.epoch(c), SlotIdle{},
      Bool.or(Cap.shown(c), Slot.paints(Cap.slot(c), Cap.epoch(c)))}

def Cap.step(+c: Cap, ev: Ev) -> Cap:
  match ev:
    case EvNewSource{}:
      Cap.on_new_source(c)
    case EvBlank{}:
      Cap.on_blank(c)
    case EvPush{}:
      Cap.on_push(c)
    case EvDrain{}:
      Cap.on_drain(c)

def Evs.run(evs: Evs, +c: Cap) -> Cap:
  match evs:
    case EvsNil{}:
      c
    case EvsCon{head, tail}:
      Evs.run(tail, Cap.step(c, head))

# ---------------------------------------------------------------------------
# LEI 1 -- O EPOCH DA FONTE NUNCA DECRESCE.
#
# Uma fonte e' uma ordem: se o numero de uma fonte pode voltar atras, um
# carimbo do passado pode coincidir com o presente e a guarda do `_drain` deixa
# de distinguir as fontes. E por isso que o incremento e' `+ 1` e nunca um
# `= 0` ("recomecar a numeracao").
#
# REJECTS: um `_blank_caption_window` que RESETASSE o epoch
# (`self._source_epoch = 0` em vez de `int(...) + 1`) -- a implementacao
# plausivel "recomeca a numeracao na fonte nova", que faz um texto da fonte
# anterior carimbar 0 e o epoch corrente voltar a 0 depois de um blank.
law Cap.epoch_monotonic:
  for +evs: Evs
  for c: Cap
  {Nat.is_le(Cap.epoch(c), Cap.epoch(Evs.run(evs, c))) == True{} : Bool}

# ---------------------------------------------------------------------------
# LEI 3 -- A FONTE NOVA COMECA LIMPA.
#
# Antes do primeiro texto de uma fonte nova houve uma LIMPEZA: a transicao do
# blank leva o epoch para o seguinte, esvazia o slot unico e tira os pixeis.
# Duas consequencias, e ambas importam: um texto da fonte anterior nao pode ser
# o proximo a pintar (o slot esta vazio), e o que o dono ve no instante da
# fonte nova nao e' o texto antigo (os pixeis estao limpos).
#
# O terceiro conjunct amarra o epoch do blank a EXACTAMENTE o seguinte -- nem o
# mesmo (que nao seria fonte nova) nem um salto -- com a igualdade do PROPRIO
# modelo (`Nat.same_epoch`). Que essa igualdade e' a do Base e' o que a lei 2
# prova; aqui ela so precisa de ser reflexiva.
#
# REJECTS: o `_blank_caption_window` com `self._caption_pending = None`
# apagado -- as duas linhas sao adjacentes, e sem essa o texto do audio
# anterior continua no slot quando a fonte nova comeca. E o mesmo sitio com
# `ov.show(False)` apagado: a fila limpa mas o ecra nao.
law Cap.display_clean_before_new_source:
  for +c: Cap
  {Bool.and(
     Bool.and(Bool.not(Cap.shown(Cap.on_blank(c))),
              Slot.is_idle(Cap.slot(Cap.on_blank(c)))),
     Nat.same_epoch(Cap.epoch(Cap.on_blank(c)),
                    Nat.add(1n, Cap.epoch(c)))) == True{} : Bool}

# ===========================================================================
# DECISAO 6 -- QUEM PODE ESCREVER O HISTORICO CANONICO (2026-11-05)
#
# A PRODUCAO e `app/panel/history-source.js`, a funcao `historyDecision(meta)`
# -- a UNICA decisao de "esta linha entra no historico, e sob que rota?".
# MEDIDO no proprio ficheiro (lido a 2026-11-08, 152 linhas):
#
#   * `route === 'final'`            -> ACEITA com a rota `final` (a linha foi
#                                       FECHADA; o produtor e' so procedencia);
#   * `route === 'provisional-draft'`-> RECUSA com o motivo `provisional-draft`
#                                       (a legenda AO VIVO -- o "NUNCA" do dono,
#                                        2026-10-07, verbatim: *"o historico nao
#                                       e' pra ser NUNCA o historico do live"*);
#   * qualquer outra rota NAO VAZIA  -> RECUSA com `unknown-route` (o escritor
#                                       nao conhece esta rota);
#   * sem rota + `producer === 'redux'` -> ACEITA com a rota `batch`;
#   * sem rota + qualquer outro produtor (incluindo ABSENTE) -> RECUSA com
#     `no-route-no-producer` -- FAIL-CLOSED: nada diz que a linha acabou.
#
# O QUE ESTE MODELO PROVE: essas cinco regras, e a CONSISTENCIA DO INSTRUMENTO
# (`transcriptRoute(meta) === null` sse `historyRefusal(meta) !== null`): uma
# recusa que nao sabe dizer-se e' o defeito que este modulo foi ensinado a nao
# cometer (`recordHistory` a reporta como `HISTORY_REFUSED`).
#
# O QUE NAO PROVE: o conteudo do texto, o store em disco, nem qual rota o motor
# de formulacao VOTOU (essa e' a DECISAO 7). A ponte com a producao esta em
# `_main/bend_mirror.py`, que executa a funcao REAL (via `node`) sobre o dominio
# inteiro -- uma lei aqui e uma amostra ali, e nenhuma substitui a outra.
#
# A ENTRADA DE PRODUCAO QUE CHEGA A CADA LEI (F-6): os `meta` que
# `caption-formulation.js::commit` entrega ao `recordHistory` do painel, e os
# que `panel.js` monta a partir da linha gravada -- `route` vem de
# `routeFor()` (`'final'` | `'provisional-draft'`) e `producer` vem do worker
# (`'redux'` | `'live'` | ausente). Rotas desconhecidas chegam de escritores que
# nao sao este motor; e' por isso que a recusa `unknown-route` existe.
# ===========================================================================

# O produtor que a linha DECLARA -- o `producerOf(meta)`, normalizado.
type Prod is Data:
  ProdNone{}
  ProdLive{}
  ProdRedux{}
  ProdOther{tag: Nat}

# A rota que a linha DECLARA -- o `meta.route`, e so os tres valores que a
# producao distingue (ausente, `final`, `provisional-draft`, qualquer outra).
type InRoute is Data:
  InRouteAbsent{}
  InRouteFinal{}
  InRouteProvisional{}
  InRouteOther{name: Nat}

# A rota que o historico GRAVA -- nenhuma, `final`, ou `batch`.
type OutRoute is Data:
  OutNone{}
  OutFinal{}
  OutBatch{}

# O motivo de uma recusa -- `null` (aqui `ReasonNone`) quando a linha entrou.
type OutReason is Data:
  ReasonNone{}
  ReasonProvisional{}
  ReasonUnknownRoute{}
  ReasonNoRouteNoProducer{}

def OutRoute.is_none(r: OutRoute) -> Bool:
  match r:
    case OutNone{}:
      True{}
    case OutFinal{}:
      False{}
    case OutBatch{}:
      False{}

def OutReason.is_none(r: OutReason) -> Bool:
  match r:
    case ReasonNone{}:
      True{}
    case ReasonProvisional{}:
      False{}
    case ReasonUnknownRoute{}:
      False{}
    case ReasonNoRouteNoProducer{}:
      False{}

# O codigo do produtor, para a lei extensional o poder comparar com o literal
# `redux` do ficheiro de producao.
def Prod.code(producer: Prod) -> Nat:
  match producer:
    case ProdNone{}:
      0n
    case ProdLive{}:
      1n
    case ProdRedux{}:
      2n
    case ProdOther{tag}:
      3n

# `isCanonicalLine(meta)` -- o produtor e' o canonico (`'redux'`)?
def Hist.producer_is_canonical(producer: Prod) -> Bool:
  match producer:
    case ProdRedux{}:
      True{}
    case ProdLive{}:
      False{}
    case ProdNone{}:
      False{}
    case ProdOther{tag}:
      False{}

# `historyDecision(meta).route` -- a rota QUE ENTRA, ou nenhuma.
def Hist.route_of(route: InRoute, producer: Prod) -> OutRoute:
  match route:
    case InRouteFinal{}:
      OutFinal{}
    case InRouteProvisional{}:
      OutNone{}
    case InRouteOther{name}:
      OutNone{}
    case InRouteAbsent{}:
      match producer:
        case ProdRedux{}:
          OutBatch{}
        case ProdLive{}:
          OutNone{}
        case ProdNone{}:
          OutNone{}
        case ProdOther{tag}:
          OutNone{}

# A PORTA: aceita sse ha' uma rota.
def Hist.accepted(route: InRoute, producer: Prod) -> Bool:
  Bool.not(OutRoute.is_none(Hist.route_of(route, producer)))

# A SEGUNDA FORMA da porta, escrita como a REGRA e nao como a projeccao. A lei
# `Hist.accepted_agrees_with_its_two_forms` e' o que impede as duas de
# divergirem -- e' o que a F-6b pede de um def com codominio `Bool`.
def Hist.accepted_reference(route: InRoute, producer: Prod) -> Bool:
  match route:
    case InRouteFinal{}:
      True{}
    case InRouteProvisional{}:
      False{}
    case InRouteOther{name}:
      False{}
    case InRouteAbsent{}:
      match producer:
        case ProdRedux{}:
          True{}
        case ProdLive{}:
          False{}
        case ProdNone{}:
          False{}
        case ProdOther{tag}:
          False{}

# `historyDecision(meta).reason` -- o motivo, ou nenhum.
def Hist.reason_of(route: InRoute, producer: Prod) -> OutReason:
  match route:
    case InRouteFinal{}:
      ReasonNone{}
    case InRouteProvisional{}:
      ReasonProvisional{}
    case InRouteOther{name}:
      ReasonUnknownRoute{}
    case InRouteAbsent{}:
      match producer:
        case ProdRedux{}:
          ReasonNone{}
        case ProdLive{}:
          ReasonNoRouteNoProducer{}
        case ProdNone{}:
          ReasonNoRouteNoProducer{}
        case ProdOther{tag}:
          ReasonNoRouteNoProducer{}

# REJECTS: uma porta que recusasse a linha FECHADA porque o produtor nao e' o
# canonico -- a regra ANTERIOR a 2026-11-05, que deixou o historico do dono com
# ZERO escritores (`3830 CAPTION_APPLIED, 0 HISTORY_APPEND`, medido no log dele).
law Hist.final_route_is_accepted:
  for producer: Prod
  {Hist.accepted(InRouteFinal{}, producer) == True{} : Bool}

# REJECTS: a porta PERMISSIVA -- uma linha `provisional-draft` (a legenda ao
# vivo) a entrar no historico. E' o defeito que o dono reportou verbatim
# (*"o historico simplesmente mostra a legenda ao vivo"*, 2026-10-06).
law Hist.provisional_route_is_refused:
  for producer: Prod
  {Hist.accepted(InRouteProvisional{}, producer) == False{} : Bool}

# REJECTS: a separacao de 2026-10-07, apagada -- `producer:'live'` sem rota a
# entrar como `batch`. O "NUNCA" do dono.
law Hist.live_producer_is_never_canonical:
  {Hist.accepted(InRouteAbsent{}, ProdLive{}) == False{} : Bool}

# REJECTS: um default permissivo que aceitasse a linha sem rota sem o produtor
# canonico -- o `|| 'final'` que o painel tinha antes de 2026-10-06.
law Hist.absent_claim_is_accepted_only_from_the_canonical_producer:
  for producer: Prod
  {Hist.accepted(InRouteAbsent{}, producer)
     == Hist.producer_is_canonical(producer) : Bool}

# REJECTS: `unknown-route` a entrar como se fosse uma rota conhecida. Um
# escritor que inventa uma rota nao diz que a linha acabou.
law Hist.unknown_route_is_refused:
  for name: Nat
  for producer: Prod
  {Hist.accepted(InRouteOther{name}, producer) == False{} : Bool}

# A LEI EXTENSIONAL do produtor canonico (F-6b): o predicado tem de ser
# EXACTAMENTE o codigo do `redux`, e nao um `True{}` constante.
law Hist.canonical_producer_is_exactly_the_redux_code:
  for producer: Prod
  {Hist.producer_is_canonical(producer)
     == Nat.same_epoch(Prod.code(producer), 2n) : Bool}

# F-6b: o `Bool` da porta nao pode ficar constante. As duas formas do mesmo
# enunciado -- a projeccao e a regra -- tem de concordar em TODAS as entradas.
law Hist.accepted_agrees_with_its_two_forms:
  for route: InRoute
  for producer: Prod
  {Hist.accepted(route, producer)
     == Hist.accepted_reference(route, producer) : Bool}

# O INSTRUMENTO: recusar e' dizer por que. `transcriptRoute(meta) === null` sse
# `historyRefusal(meta) !== null` -- uma recusa muda e' o defeito que este
# modulo existe para nao repetir.
law Hist.refusal_names_itself:
  for route: InRoute
  for producer: Prod
  {Hist.accepted(route, producer)
     == OutReason.is_none(Hist.reason_of(route, producer)) : Bool}

# ===========================================================================
# DECISAO 7 -- A VOTACAO DE ROTA DA FORMULACAO (2026-11-04)
#
# A PRODUCAO e `app/panel/caption-formulation.js::routeFor(reason)` e o seu
# companheiro `routeSourceFor(route)` -- as duas metades da decisao que o
# `commit` carimba no `meta` que chega a DECISAO 6. MEDIDO no ficheiro (lido a
# 2026-11-08, 1277 linhas):
#
#   routeFor(reason):
#     if (bufferFinal)     return 'final';              -- o worker FECHOU
#     if (bufferSawFinal)  return 'provisional-draft';  -- o worker votou ABERTO
#     return PANEL_CLOSED_REASON.test(reason)
#              ? 'provisional-draft'                    -- e' o painel que fecha
#              : 'final';                               -- o AUDIO fechou
#
#   routeSourceFor(route):
#     worker vote            -> 'worker-stamped'
#     producer declarado     -> 'worker-stamped-producer'
#     sem voto, rota 'final' -> 'fallback'      <-- o default silencioso, NOMEADO
#     sem voto, restante     -> 'panel-deadline'
#
# O QUE ESTE MODELO PROVE: o voto do worker manda; o fecho do PAINEL nunca
# fabrica um `final` (logo nunca mete a legenda ao vivo no historico); o
# fecho do AUDIO, sem voto, cai no default `final` (o fallback existe e e'
# deliberado -- apaga-lo esvazia o historico do dono); e o rotulo `fallback`
# aparece EXACTAMENTE naquele caso e em nenhum outro, para que um de-landing do
# contrato do worker (P1 `4fb5b25380cbc8269977e22e`) seja legivel no texto
# gravado e nao invisivel.
#
# O QUE NAO PROVE: o TEMPO. `COMMIT_MAX_HOLD_MS` (1500 ms) e o limiar do
# `describeReadiness` (7 s) sao orcamentos medidos pelo falsificador
# (`_main/youtube-drift-oracle.py`, `_main/panel-commit-stable-oracle.py`), e
# uma lei nunca prova um milissegundo.
#
# A ENTRADA DE PRODUCAO (F-6): `commit(reason)` e chamado por `flush`
# (`'flush'`/`'status-change'`), por `expireHold` (`'hold-timeout'`), pelo
# `ingest` (`'audio-gap …'`, `'chars …'`, `'stable'`). As flags vem dos
# fragmentos do worker (`meta.final`), o produtor do `meta.producer`, e o
# `reason` e' literal no ponto de chamada.
# ===========================================================================

# A rota de origem, como `routeSourceFor` a devolve.
type Src is Data:
  SrcWorker{}
  SrcWorkerProducer{}
  SrcPanelDeadline{}
  SrcFallback{}

# `routeFor(reason) == 'final'`? A primeira forma, por `match` nos parametros.
def Fmt.is_final(buffer_final: Bool, saw_final: Bool, panel_closed: Bool) -> Bool:
  match buffer_final:
    case True{}:
      True{}
    case False{}:
      match saw_final:
        case True{}:
          False{}
        case False{}:
          Bool.not(panel_closed)

# A SEGUNDA FORMA da mesma decisao, por `Bool.pick` (a forma que aceita uma
# condicao computada -- que e' a forma que a producao usa).
def Fmt.is_final_reference(buffer_final: Bool, saw_final: Bool, panel_closed: Bool) -> Bool:
  Bool.pick(Bool, buffer_final, True{},
    Bool.pick(Bool, saw_final, False{},
      Bool.pick(Bool, panel_closed, False{}, True{})))

# `routeSourceFor` -- o rotulo que o `commit` carimba no `meta.routeSource`.
def Fmt.source(buffer_final: Bool, saw_final: Bool, has_producer: Bool, panel_closed: Bool) -> Src:
  match buffer_final:
    case True{}:
      SrcWorker{}
    case False{}:
      match saw_final:
        case True{}:
          SrcWorker{}
        case False{}:
          match has_producer:
            case True{}:
              SrcWorkerProducer{}
            case False{}:
              match panel_closed:
                case True{}:
                  SrcPanelDeadline{}
                case False{}:
                  SrcFallback{}

def Src.is_fallback(src: Src) -> Bool:
  match src:
    case SrcFallback{}:
      True{}
    case SrcWorker{}:
      False{}
    case SrcWorkerProducer{}:
      False{}
    case SrcPanelDeadline{}:
      False{}

# A SEGUNDA FORMA do rotulo `fallback`, escrita como o predicado literal.
def Fmt.is_fallback_reference(buffer_final: Bool, saw_final: Bool, has_producer: Bool, panel_closed: Bool) -> Bool:
  Bool.and(Bool.not(buffer_final),
    Bool.and(Bool.not(saw_final),
      Bool.and(Bool.not(has_producer), Bool.not(panel_closed))))

# REJECTS: o voto `final:true` do worker a ser rebaixado pelo `reason` do
# painel -- um `final` genuino a chegar ao historico como `provisional-draft`.
law Fmt.worker_final_vote_is_final:
  for saw_final: Bool
  for panel_closed: Bool
  {Fmt.is_final(True{}, saw_final, panel_closed) == True{} : Bool}

# REJECTS: o voto ABERTO do worker (`final:false`) a ser promovido a `final`
# porque o painel fechou a linha por tempo -- a legenda ao vivo no historico.
law Fmt.worker_partial_vote_is_never_final:
  for panel_closed: Bool
  {Fmt.is_final(False{}, True{}, panel_closed) == False{} : Bool}

# REJECTS: o fecho do PROPRIO painel (`hold-timeout`/`status-change`/`flush`/
# `stable`) a fabricar um `final`. E' o defeito medido em 2026-10-06: 10 de 10
# linhas que o dono leu como "a legenda ao vivo" vinham de `status-change`.
law Fmt.panel_close_never_manufactures_final:
  {Fmt.is_final(False{}, False{}, True{}) == False{} : Bool}

# REJECTS: apagar o default `final` -- sem voto e sem fecho do painel (um
# `audio-gap` ou um `chars`), o historico do dono ficava vazio. O default e'
# DELIBERADO e nao pode ser apagado (ver o docstring de `routeFor`).
law Fmt.audio_close_without_a_vote_is_final:
  {Fmt.is_final(False{}, False{}, False{}) == True{} : Bool}

# F-6b: a decisao `Bool` nao pode ficar constante. As duas formas -- `match`
# sobre os parametros e `Bool.pick` sobre as mesmas condicoes -- concordam em
# todas as entradas.
law Fmt.route_agrees_with_its_two_forms:
  for buffer_final: Bool
  for saw_final: Bool
  for panel_closed: Bool
  {Fmt.is_final(buffer_final, saw_final, panel_closed)
     == Fmt.is_final_reference(buffer_final, saw_final, panel_closed) : Bool}

# A LEI DO DE-LANDING: o rotulo `fallback` aparece EXACTAMENTE quando nao ha'
# voto do worker, nao ha' produtor declarado, e a rota e' `final` -- e em
# nenhum outro caso. Se esta lei partir, um de-landing do contrato do worker
# (ou um default que engoliu o rotulo) fica invisivel no texto gravado.
law Fmt.fallback_is_exactly_the_silent_default:
  for buffer_final: Bool
  for saw_final: Bool
  for has_producer: Bool
  for panel_closed: Bool
  {Src.is_fallback(Fmt.source(buffer_final, saw_final, has_producer, panel_closed))
     == Fmt.is_fallback_reference(buffer_final, saw_final, has_producer, panel_closed) : Bool}
