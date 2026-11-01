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
# Verify:  python _main/bend-laws-gate.py      (leis + provas + controlos + guardas)
#          cd bend_core && bend PROOF.bend --verdict   (o portao das provas)
#          cd bend_core && bend LAWS.bend              (so as afirmacoes: reports
#                                                       cada lei como claim aberto)
# Toolchain: docs/bend/BEND_PROOFS_REFERENCE.md, docs/bend/BEND_LAW_GUIDE.md
#
# MEDIDO 2026-10-29: a linha apontava para `bash tools/bend_verify.sh`, que nao
# existe NESTE repositorio (e um caminho herdado do `consultgpt`, de onde este
# pacote foi portado). O portao real aqui e `_main/bend-laws-gate.py`, que
# envolve o `bend --verdict` e acrescenta os catorze controlos negativos e as
# duas sondas de tamper.
#
# MEDIDO 2026-10-30: o gate MUDOU de forma. `_main/bend-laws-gate.py` fixa a
# INVENTARIO de leis e o CONJUNTO de controlos, e por isso acrescentar uma lei
# aqui exige acrescentar a linha nos dois pins de la (senao o gate sai 5). O
# portao das PROVAS e, e sempre foi, `bend PROOF.bend --verdict`.

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
#   * `_blank_caption_window` (:9719) faz
#         self._source_epoch = int(getattr(self, '_source_epoch', 0)) + 1
#         self._caption_pending = None
#     e depois esconde o overlay (`ov.show(False)`) -- limpa pixeis E fila.
#   * `start_worker` (:9514) faz AS MESMAS duas linhas quando um worker arranca
#     (`self._source_epoch = int(...) + 1`, `self._caption_pending = None`):
#     "UM WORKER NOVO E' UMA FONTE NOVA". Nao mexe nos pixeis.
#   * `push_caption_to_window` (:9798) grava no slot UNICO
#         (now, text, previous, int(getattr(self, '_source_epoch', 0)))
#     -- o texto viaja com o epoch COM QUE FOI ENFILEIRADO.
#   * `_drain` (:9812-9819) compara ANTES de pintar:
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
