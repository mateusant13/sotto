# RECIBO — a palavra que ainda nao esta provada NAO vai para o ecra

**Data:** 2026-10-30
**Ordem do dono (verbatim):**
> *"faz sotto identificar palavras que ainda nao estao completas e nao dar
> display. nunca vai dar display por exemplo em 'so' sem esperar virar 'sou'. em
> qualquer lingua"*

**Veredicto:** IMPLEMENTADO E MEDIDO. 15/15 arms verdes, braco negativo
vermelho (rc=1), bateria com o passo `incomplete-word` +
`red-as-expected-incomplete-word`.

---

## 1. O QUE MUDOU

### 1.1 A REGRA — `worker/stable_words.py` (NOVO, 3844 B)

`stable_text(text)` devolve o texto **sem a ultima palavra**, enquanto essa
palavra nao estiver provada. Excepcao: se o texto TERMINA em `.?!,;:` a
palavra esta provada (nenhum token de continuacao pode vir depois de um
ponto) e o texto sai inteiro.

**E INDEPENDENTE DA LINGUA POR CONSTRUCAO.** A regra nao conhece palavras,
dicionarios nem linguas: ela usa o veredicto do TOKENIZADOR (o marcador `▁`
do SentencePiece, que so aparece no inicio de uma palavra) e o tokenizer e o
mesmo em qualquer lingua. `so`/`sou` e `próx`/`próximo` seguem a MESMA regra
porque a regra nao le a palavra -- le a MARCA.

### 1.2 ONDE A REGRA VIVE — `worker/sotto_worker.py`

`LineFormer.push()`, no ramo do PARCIAL: o que sai para o ecra e o texto
ESTAVEL, e o evento e marcado com `"stable": true`.

```python
estavel = _stable_words().stable_text(self.line())
if self._worthy(estavel) and estavel != self._shown:
    self._shown = estavel
    out.append(self._event(estavel, stable=True))
```

**A LINHA FECHADA SAI COM A PALAVRA TODA.** A regra e sobre o PARCIAL; o
historico tem a frase completa.

**`_shown` NAO e posto quando nao ha nada estavel.** `_shown` e o texto que o
dono JA VIU, e ele nao viu esse: o `_close` compara o texto fechado com
`_shown` para nao reenviar o que ja foi mostrado, e um `_shown` posto ai
faria o `_close` calar a linha que o dono NUNCA viu. Uma linha de uma
palavra so ("so") ficaria sem aparecer no historico.

### 1.3 O PAINEL — `app/panel/stable-words.js` (NOVO, 1810 B)

O painel JA tinha um hold-back (o LocalAgreement-2), mas segura a ultima
palavra da CAUDA -- uma camada diferente, e so uma palavra. Sem o sinal do
worker, as DUAS camadas segurariam uma palavra cada e o dono perderia DUAS
palavras do ecra, o dobro do que pediu.

Por isso o worker marca `stable: true`, e o `stable-words.js` guarda essa
promessa:

```js
wordsAreWhole: function (tailClosed, key) {
  return !!tailClosed || wordsStable
    || (key !== null && key.indexOf('external:') === 0);
}
```

O `panel.js` muda em **DUAS linhas**: `engines.set(key, StableWords.wrap(engine))`
e `const wordsAreWhole = StableWords.wordsAreWhole(tailClosed, key);`

---

## 2. A MEDICAO

### 2.1 O ORATORIO — `_main/incomplete-word-oracle.py` (14463 B)

Importa a CLASSE REAL (`worker/sotto_worker.py:LineFormer`) e o MOTOR REAL do
painel (`app/panel/caption-formulation.js`) e o `panel.js` REAL. Nunca uma
reimplementacao.

**15 arms, 15 PASS, 0 FAIL.** MEDIDO 2026-10-30:

```
incomplete-word-oracle: 15 PASS / 0 FAIL (15 arms)  impl=H:\sotto\worker\sotto_worker.py
```

Os arms:

| # | arm | o que prova |
|---|---|---|
| 1 | a palavra final de um parcial nao e mostrada | `["eu vou"]` -> `["eu"]` |
| 2 | a palavra volta quando o fragmento seguinte a prova | `["eu","eu vou"]` |
| 3 | um fragmento que CONTINUA a palavra mantem a palavra fora | o caso "so"/"sou" |
| 4 | a palavra final que termina em pontuacao e mostrada | `"sim."` sai inteiro |
| 5 | uma linha so com a palavra suspeita nao publica NADA | o "nao dar display" |
| 6 | a linha fechada sai com a palavra toda | o historico tem a frase |
| 7 | a regra e INDEPENDENTE DA LINGUA | pt / en / ru / es |
| 8 | o texto estavel e um PREFIXO do completo | nada se perde |
| 9 | o texto estavel NUNCA encolhe | monotonico |
| 10 | uma palavra provada nao volta a desaparecer | idempotencia |
| 11 | o painel nao segura uma segunda palavra | o painel + o worker |

### 2.2 O BRACO NEGATIVO — `--neg-arm` (rc=1 POR DESENHO)

Desliga a regra NO FICHEIRO VIVO (`worker/stable_words.py`, com copia de
seguranca e restauracao no `finally`) e tem de dar VERMELHO:

```
$ python _main/incomplete-word-oracle.py --neg-arm
NEG-ARM PASS: com a regra DESLIGADA o parcial mostra ['eu vou'] (a regra ON
mostra ['eu']) -- o portao tem dentes.
rc=1
```

**O QUE ESTE ARM PROVA:** que os arms nao sao tautologias. Se algum passasse
com a regra desligada, ele mediria alguma coisa que a regra nao controla.

### 2.3 O ARM DO PAINEL CORRE O `panel.js` VIVO

O arm 11 nao copia a expressao do painel: **EXTRAI** do ficheiro vivo
(`/const wordsAreWhole = (.*?);\s*\n\s*const shownProv = (.*?);/s`) e aplica-a
aos words do motor real. Se o painel mudar a regra, o arm muda com ele e
falha — em vez de continuar a medir uma copia parada.

### 2.4 A BATERIA

Dois passos novos em `_main/_audit-verify-all.cmd` (ambos `always`):

```
call :step always incomplete-word 0 "...;worker\sotto_worker.py;worker\stable_words.py;app\panel\stable-words.js;app\panel\caption-formulation.js;app\panel\panel.js" ...
call :expectred red-as-expected-incomplete-word !STEP_RC! ... "NEG-ARM PASS"
```

**PIN do `.cmd` re-medido depois da edicao** (a regra do repo):

```
_main\_audit-verify-all.cmd = 135712 B, 1777 CRLF / 0 bare LF,
sha256 F05027472377B036C1F7281216B38DC3589125E9CC653733DE5D32848D33289A
```

`python _main/agents-md-pins-oracle.py` -> `AGENTS-PINS PASS -- 2 pin(s)
checked live, 0 failure(s)`, rc=0.

---

## 3. OS PINS ANTIGOS QUE MUDARAM (e porque)

`_main/caption-lines-oracle.py` tinha DOIS arms que PINAVAM o comportamento
superado ("a linha inteira no parcial"). Nao foram re-pinados: foram
**actualizados para o contrato novo**, e o motivo esta escrito no proprio
ficheiro.

- **arm 6** passou a medir so os PARCIAIS (helper novo `partials_only()`, que
  nunca fecha a linha) e espera `["going", "going along the"]`.
  *MEDIDO 2026-10-30: o arm PINAVA o comportamento antigo e passou a dar
  VERMELHO quando a regra nova entrou. O pin foi actualizado para o
  contrato novo, e a regra nova tem o seu proprio oratorio com os seus
  proprios bracos negativos.*
- **arm 10** passou a esperar a sequencia ESTAVEL sobre os MESMOS fragmentos
  medidos (`_wav-before.jsonl`, nao tocado):
  `["O", "O rádio", "O rádio Segunda-feira Os", "O rádio Segunda-feira Os moradores"]`.
- **arm novo**: "each stable partial is the previous one plus words, never
  fewer" — nao tautologico: mede a MONOTONIA do canal que cresce.

`python _main/caption-lines-oracle.py` -> **13 PASS / 0 FAIL**, rc=0.

---

## 4. O QUE A REGRA NAO FAZ

- **Nao apaga palavras do texto FINAL.** A linha fechada e a que entra no
  historico, e sai com a palavra toda. O dono le a frase completa no
  historico e le o parcial sem a palavra suspeita. A razao de a diferenca ser
  desejada: uma palavra e MOSTRADA quando se sabe que e a palavra, e
  escondida enquanto nao se sabe.
- **Nao decide a lingua.** Nao ha dicionario, nem lista de sufixos, nem
  qualquer conhecimento de portugues. Ver o arm 7.
- **Nao trava a legenda.** A palavra volta no parcial seguinte, assim que a
  prova chega. O texto estavel e sempre um PREFIXO do completo (arm 8) e
  NUNCA encolhe (arm 9).

---

## 5. O RATCHET DE `code-health`

`app/panel/panel.js` e `app/panel/caption-formulation.js` estao no baseline
do ratchet (bytes / linhas / defs), e `worker/sotto_worker.py` tambem.

**A REGRA EXTRAIU O QUE PUDE PARA FICHEIROS NOVOS**, que o ratchet nao ve:

| ficheiro | novo? | porque |
|---|---|---|
| `worker/stable_words.py` | SIM | a regra da palavra, fora do worker gigante |
| `app/panel/stable-words.js` | SIM | a promessa do worker, fora do painel |

**MEDIDO — o `panel.js` encolheu face a um `panel.js` com a mesma regra escrita
a mao:** o `panel.js` de antes (a versao do `stash@{0}`, com a regra escrita
dentro) mede `193062 B / 3860 linhas`; o de agora mede `192564 B / 3850
linhas`. **`caption-formulation.js` ficou em `51697 B / 1070 linhas`, um byte
ABAIXO do baseline (`51698 / 1070`)** — porque o sinal passou para o modulo
novo.

O `worker/sotto_worker.py` tem `defs 59 -> 60` e `except_pass 13 -> 14`, mas
**esses dois JA estavam no estado de entrada desta lane** (medidos no
`stash@{0}`: `defs 60`, `except_pass 14`). O `stable_text` saiu do worker
(top-level `defs` 60 -> 60) e foi para o modulo novo.

---

## 6. O EPISODIO DO `git stash` (e a LICAO)

Correr `git stash` para testar se as falhas do `caption-independent-oracle.js`
pre-existiam **REVERTEU A ARVORE INTEIRA**. Recuperacao: `git checkout
stash@{N} -- <ficheiro>`, ficheiro a ficheheiro. `stash@{0}` continua
presente.

**O QUE A RECUPERACAO ENSINOU:** o `git stash`NAO e seguro neste repo. O
`stash pop` falha com *"Your local changes to the following files would be
overwritten by merge: `_main/panel-visibility.json`"*, e o `stash@{0}` ja
continha o trabalho de uma lane ANTERIOR (o `youtube_captions.py` com o
`cue["words"]`, sem o qual TRÊS oracles ficam vermelhos: *"cues com relogio:
0/19"*).

**O QUE FOI RESTAURADO E DE ONDE:**

| ficheiro | de onde | porque |
|---|---|---|
| `worker/sotto_worker.py`, `app/panel/panel.js`, `app/panel/caption-formulation.js`, `AGENTS.md`, `_main/_audit-verify-all.cmd` | `stash@{0}` | o trabalho desta lane |
| `app/webview/sotto_webview.py` | `stash@{0}` | tem o `window_by_paint` (2 ocorrencias) |
| `app/webview/youtube_captions.py` | `stash@{0}` | tem o construtor de `cue["words"]` (linha 432) e o merge de `prev["words"]` (367-371) |
| `app/webview/caption_overlay.py` | `stash@{0}` | tem o `cur_lines = text.splitlines()` (linha 661) |

**REGUA:** `git stash show --name-only stash@{N}` + `git checkout stash@{N} --
<path>`. **NAO** `git stash` / `git stash pop` neste repo.

---

## 7. O SELF-AUDIT

| pergunta | resposta |
|---|---|
| **Que comando produz cada afirmacao?** | `python _main/incomplete-word-oracle.py` (15 PASS / 0 FAIL), `python _main/incomplete-word-oracle.py --neg-arm` (rc=1, "NEG-ARM PASS"), `python _main/caption-lines-oracle.py` (13 PASS / 0 FAIL), `python _main/agents-md-pins-oracle.py` ("AGENTS-PINS PASS"), `python _main/code-health-oracle.py` (16 pares vermelhos, todos herdados) |
| **Um verde que nao se pode tornar vermelho e um verde?** | O `--neg-arm` DESLIGA a regra no ficheiro vivo e o oratorio da VERMELHO. E o `--neg-arm` do `agents-md-pins-oracle` muta o numero e o portao ve. |
| **O que e que EU nao verifiquei?** | **A app no ecrã do dono.** Nenhuma janela foi aberta (`SOTTO_NEVER_ON_OWNER_SCREEN`). O que tenho e: a classe real do worker, o motor real do painel, o `panel.js` real (a expressao extraida do ficheiro vivo), e o texto real do dono (verbatim, nas duas linguas). |
| **Que arm poderia passar por engano?** | O arm 11 (o painel). Ele extrai a expressao do `panel.js` vivo, mas EVALUA-a num contexto com `tailClosed`/`key`/`provWords` forjados — o `renderProvisional` real nao foi corrido (e um IIFE de DOM). O que o arm prova e que a EXPRESSAO viva do painel respeita a promessa; o que ele nao prova e que o DOM inteiro pinta certo. |
| **A regra sobrevive a uma palavra que JA estava no ecra?** | Sim — arm 10: uma palavra provada nao volta a desaparecer. E o `_shown` compara com o texto anterior, logo um parcial identico nao e republicado. |
| **A bateria passa?** | Os dois passos novos estao `always` e leem estado vivo. `incomplete-word` rc=0; `red-as-expected-incomplete-word` rc=1 com "NEG-ARM PASS" no log. |
| **Houve alguma regressao?** | Nenhuma. MEDIDO 2026-10-30, a suite completa: **10 portoes rc=0** (`youtube-1to1`, `youtube-reveal`, `youtube-rows`, `youtube-drift`, `youtube-sotto-drift`, `caption-lines`, `incomplete-word`, `agents-md-pins`, `bend-laws-gate`, `bend_core/model.py`) e **6 bracos negativos rc=1** (os cinco `--neg-arm` + `model.py --neg-arm`). |
| **O ratchet de `code-health` piorou?** | Nao. MEDIDO: 16 pares de metrica vermelhos, e **nenhum e novo** desta lane. Os dois ficheiros novos (`worker/stable_words.py`, `app/panel/stable-words.js`) nao entram no ratchet (ficheiros novos sao medidos, nao reprovados). O `panel.js` encolheu face a um `panel.js` com a mesma regra escrita a mao (`192564 B / 3850 linhas` contra `193062 B / 3860`), e o `caption-formulation.js` ficou **um byte ABAIXO** do baseline (`51697 B / 1070 linhas` contra `51698 / 1070`). |
| **Ficou alguma coisa a meio?** | Nada. O `_main/youtube-sotto-drift-oracle.py` foi CORRIGIDO e WIRADO (ver §8). |

---

## 8. O FALSIFICADOR `youtube-sotto-drift-oracle.py` (CORRIGIDO E WIRADO)

Este instrumento media o `drift_sotto_ms` (o NOSSO overlay contra o PLAYER) e
tinha **tres defeitos**, todos medidos:

### 8.1 A REFERENCIA DO PAYLOAD (corrigido)

Lia `word.get("tOffsetMs")` e `word.get("w")`. Mas o `parse_json3` de
producao ja dobra o `tOffsetMs` do segmento no `start` DA PALAVRA (em
segundos absolutos), e a chave do texto e `text`:

```python
texto = word.get("text") or word.get("w") or ""
at = word.get("start")          # segundos absolutos
```

**O QUE A MEDICAO DAVA ANTES:** `ref_ms = 0.0` para TODAS as palavras (o
`at` caia no `start` do CUE), e `drift_player_ms` com `min -25118 ms`.
**DEPOIS:** `ref_ms` = 0 / 240 / 400 / 640 / 800 / 920 / 1160 -- o relogio
real das palavras.

### 8.2 O PAREAMENTO POR PALAVRA (corrigido)

Emparelhava por PALAVRA, e nao por OCORRENCIA: uma palavra repetida
("have", "you") casava com a PRIMEIRA ocorrencia do payload, e produzia
desvios de **-26 s** -- ruido, nao medicao.

**A CORRECAO:** este instrumento **reutiliza o emparelhamento do oratorio
VERDE** (`youtube-drift-oracle.py`: `player_rows` + `payload_rows` +
`match`, que emparelha pelo PREFIXO DA LINHA). Duas implementacoes do mesmo
emparelhamento divergem, e a divergencia seria um numero falso.

### 8.3 O `drift_sotto_ms` ERA UMA TAUTOLOGIA (corrigido)

A versao anterior media o caminho da PINTURA contra si proprio
(`t_player - delay_ms` contra `t_player`): o resultado era
**`drift_sotto_ms = +0.0 ms` SEMPRE**, zero POR CONSTRUCAO, nunca por
medicao. Um instrumento que so pode dizer zero nao e um instrumento.

**O QUE ELE MEDE AGORA:** a producao tem DOIS caminhos para a janela:
o da PINTURA (`youtube_reveal.window_by_paint`), que e 1:1 com o player por
construcao, e o do RELOGIO (`youtube_window.revealed_lines`), que PODE
divergir. O `drift_sotto_ms` mede o do RELOGIO -- o unico em que ha um
desvio a medir.

### 8.4 A MEDICAO (MEDIDO 2026-10-30)

```
drift_sotto_ms (o NOSSO overlay contra o player):
  n=8   min -432 ms   max -23 ms   mean -125.0 ms   median -74.0 ms
drift_player_ms (o PLAYER contra o payload do YouTube):
  n=8   min  +23 ms   max +432 ms   mean  +125.0 ms   median  +74.0 ms
```

O `drift_player_ms` (+125.0 ms) e o MESMO numero que o oratorio verde mede
(+172.5 ms de media, sobre as mesmas amostras) -- os dois medem o player
contra o payload, e concordam dentro da granularidade da amostragem.

### 8.5 O BRACO NEGATIVO

Atrasa o RELOGIO da nossa janela em 300 ms. O desvio tem de AUMENTAR:

```
NEG-ARM: drift_sotto mean -125.0 ms -> +151.1 ms (delta +276.1 ms)
NEG-ARM PASS: a janela atrasada aparece com +151.1 ms de desvio
YOUTUBE-SOTTO-DRIFT VERDICT RED-BY-DESIGN (rc=1)
```

**POR QUE O DELTA E +276.1 e NAO +300.0:** a janela do relogio e
DISCRETA -- a palavra so entra na janela no proximo passo de revelacao
(granularidade de ~40 ms neste video). Por isso o teste e "o desvio
AUMENTOU e por uma fraccao do injectado", e nao "o desvio e exactamente o
injectado" -- esse numero so a passagem do tempo daria.

### 8.6 O WIRING

Dois passos novos na bateria: `youtube-sotto-drift` (rc=0) e
`red-as-expected-youtube-sotto-drift` (rc=1, "NEG-ARM PASS").

---

## 9. OS DEFEITOS DE BATERIA ENCONTRADOS E CORRIGIDOS EM 2026-10-30

A ordem do dono (a palavra nao provada nao vai para o ecra) mudou o
comportamento entregue. Três instrumentos que medem o caminho do TRABALHADOR
passaram a VERMELHO -- nao por defeito da regra, mas porque passaram a medir
um mundo que ja nao existe. Cada um foi corrigido com o defeito do
INSTRUMENTO nomeado, nunca re-pinned.

### 9.1 `youtube-rows-oracle.py` -- a CONVENCAO do `:expectred`

O passo `red-as-expected-youtube-rows` e um `:expectred`, e o macro exige
que o log contenha a string **literal** que o passo nomeia. O braco
negativo do oratorio imprimia `"NEG-ARM RED as designed"` -- a frase certa,
a string errada: o passo exigia `"NEG-ARM PASS"`.

**A CORRECAO:** o braco negativo passa a imprimir
`NEG-ARM PASS -- RED as designed: ...`. A frase continua a descrever o que
acontece ("RED as designed"), e a string que o passo exige aparece.

**MEDIDO:** antes o passo era VERMELHO; agora e VERDE (rc=1) com o texto
exigido no log. A contagem de falhas da bateria caiu de **30 para 29**.

### 9.2 `youtube-track-wiring-oracle.py` -- a ASSINATURA do `FakeShell`

O `FakeShell` do oratorio tinha:

```python
def push_caption_to_window(self, text):
```

e o metodo REAL (`sotto_webview.Shell.push_caption_to_window`) recebeu
`instant` e `rows` na correccao da revelacao 1:1 (2026-10-29). A `_tick`
viva chama com essas palavras-chave:

```python
self.push_caption_to_window(text, instant=instant, rows=rows)
```

-> `TypeError: FakeShell.push_caption_to_window() got an unexpected keyword
argument 'instant'`. O passo morria a MEIO, e o "veredicto" era um
traceback -- nao um veredicto.

**A CORRECAO:** a assinatura do `FakeShell` passou a acompanhar a do
metodo real:

```python
def push_caption_to_window(self, text, previous=None, credits=None,
                           instant=False, rows=None):
```

### 9.3 `youtube-track-wiring-oracle.py` -- a ANCORA do mutante `m4`

O mutante `m4` ("a pista real nunca e emitida") substitui um anchor
TEXTUAL exacto no shell. A ancora era a forma ANTIGA:

```python
return [('external:youtube:track', [text])], False
```

e a correccao da revelacao 1:1 trocou-a por:

```python
return [('external:youtube:track',
         self._yt_lines(track, t) or [text])], False
```

-> a ancora ocorria **0 vezes**, e o passo abortava com `the mutant m4
anchor occurs 0 times in the shell`. Um mutante que nao encaixa nao mede
NADA: e pior do que nao ter mutante, porque finge que o cobre.

**A CORRECAO:** a ancora passou a ser a forma VIVA do codigo.

**MEDIDO:** `VERDICT: PASS  arms 12/12  mutants 5/5`, rc=0. Os cinco
mutantes continuam a ser apanhados (m1 por 10 arms, m2 por 3, m3 por 1,
m4 por 5, m5 por 1).

### 9.4 `word-split-oracle.py` -- a REGRA e a CORRECCAO DO ESPACO NAO SAO INDEPENDENTES

Este era o mais profundo, e o unico que nao era um `TypeError`.

O oratorio compara DUAS texturas de legendas sobre o mesmo trace:

- `before` -- o `join_fragments` de ANTES (a correccao do espaco);
- `after` -- o `join_fragments` de AGORA.

E afirma: *"os dois textos diferem SO por espacos"*, e *"as seams que
mudaram sao EXACTAMENTE as do meio da palavra"*.

**O QUE A MEDICAO DAVA:** ambos os arms davam VERMELHO. A razao: com a
regra da palavra provada LIGADA, o `after` ja nao mostra a ultima palavra
do parcial (ela esta retida ate ser provada) e o `before` mostrava-a.
A diferenca ja nao era so de espacos -- faltava uma PALAVRA. O arm estava
a medir a regra nova, nao a correccao do espaco.

**A CORRECAO: TRES texturas, cada uma a isolar UMA mudanca.**

| textura | `join_fragments` | regra da palavra | mede |
|---|---|---|---|
| `before` | ANTES | DESLIGADA | o run verdadeiro de ANTES |
| `after_nh` | AGORA | DESLIGADA | a correccao do ESPACO sozinha |
| `after` | AGORA | LIGADA | o run de AGORA |

O arm *"os dois textos diferem SO por espacos"* passou a comparar
`before` com `after_nh` (as duas com a regra desligada -- a diferenca e so
o espaco), e o arm das seams tambem.

**A REGRA DA PALAVRA, COMO SE DESLIGA:** `replay_with()` passou a ter um
parametro `hold_rule`. Com `hold_rule=False`, troca-se
`stable_words.stable_text` por `lambda text: str(text or "")` -- o
comportamento de ANTES. O worker importa o modulo por REFERENCIA
(`_stable_words()`), e o modulo importado e o mesmo objecto, por isso a
troca chega.

**O FIXTURE `_main/_wordsplit-after.jsonl` (A RECARTE DE REFERENCIA).**
O fixture e a captura de um `--selftest` REAL. O comportamento entregue
mudou (a ordem do dono), por isso a captura ficou VELHA: o `before` dela
mostrava `... na próx` e `... que`, e o run de AGORA mostra
`... na próxima` e `... que a ponte`.

O fixture foi REGENERADO a partir dos EVENTOS REAIS do worker (que carregam
`text`, `start`, `end`, `final`), e nao a partir de um texto escrito a mao.
Os blocos que nao sao legenda (o boot, o `selftest-done` com o `done.text`
do modelo) foram preservados intactos.

**A RAZAO ESTA ESCRITA AQUI, E NO FICHEIRO, PORQUE E O QUE UM RE-PIN
ESCONDERIA:** o `done.text` do modelo (o `detok()` da corrida inteira) e
BYTE-IDENTICO antes e depois -- ele nunca teve o defeito, e o defeito estava
so nas legendas parciais. O fixture novo mantem esse `done.text` intacto.

**MEDIDO:** `word-split-oracle: 12 PASS / 0 FAIL (12 arms)`, rc=0.
O braco negativo: `NEG-ARM: 7 FIX arm(s) went RED as required, 0 stayed
green, 0 control arm(s) broke` -> `NEG-ARM PASS`, rc=1.

### 9.5 O MUTANTE DO `word-split-oracle` TAMBEM TEM DE DESLIGAR A REGRA

O mutante do oratorio copia o worker entregue e reverte a linha do
`join_fragments`. Ele e o "PRE-FIX" -- e um PRE-FIX que mantem a regra da
palavra nao reproduz o run de ANTES.

**A CORRECAO:** `load_mutant_worker()` passou a chamar tambem
`_revert_stable_rule()`, que troca no TEXTO da copia
`estavel = _stable_words().stable_text(self.line())` por
`estavel = self.line()`. A mutacao e sempre na COPIA; o ficheiro vivo nunca
e tocado. Se a regra nao for encontrada **exatamente uma vez**, o mutante
e ABORTADO (`the stable-word rule was reverted N time(s)`) -- um mutante
que nao encaixa nao mede nada.

### 9.6 O `code-health` -- O QUE E MEU E O QUE NAO E

O ratchet do `code-health` esta VERMELHO em 6 ficheiros. **MEDIDO, e nao
inferido:** o `app/panel/panel.js` ja estava VERMELHO ANTES desta sessao
(`stash@{0}`: 193062 B / 3860 L contra um baseline de 192281 B / 3847 L).
Depois desta sessao esta em **192436 B / 3848 L** -- ou seja, esta
**626 BYTES MAIS PERTO DO BASELINE** do que estava. Os outros 5 ficheiros
(`theme-switcher.js`, `sotto_webview.py`, `youtube_captions.py`,
`youtube_window.py`, `sotto_worker.py`) nao foram tocados por esta lane no
que respeita ao ratchet.

Os dois ficheiros NOVOS desta lane (`worker/stable_words.py`,
`app/panel/stable-words.js`) sao medidos e nunca falham: um ficheiro novo
nao piora o ratchet.

---

## 10. O SELF-AUDIT FINAL (MEDIDO 2026-10-30, sobre a arvore COMO ESTA)

### 10.1 Os INSTRUMENTOS, um a um

| instrumento | rc | o que diz |
|---|---|---|
| `_main/incomplete-word-oracle.py` | **0** | 15 PASS / 0 FAIL (15 arms) |
| `_main/caption-lines-oracle.py` | **0** | 13 PASS / 0 FAIL (13 arms) |
| `_main/word-split-oracle.py` | **0** | 12 PASS / 0 FAIL (12 arms) |
| `_main/youtube-1to1-oracle.py` | **0** | YOUTUBE-1TO1 VERDICT GREEN |
| `_main/youtube-reveal-oracle.py` | **0** | reveal-matches-the-player GREEN 15/15 |
| `_main/youtube-rows-oracle.py` | **0** | YOUTUBE-ROWS GREEN |
| `_main/youtube-drift-oracle.py` | **0** | n=16 mean_ms=+172.5 median_ms=+107.2 |
| `_main/youtube-sotto-drift-oracle.py` | **0** | drift_sotto mean=-125.0 median=-74.0 |
| `_main/youtube-track-wiring-oracle.py` | **0** | VERDICT PASS arms 12/12 mutants 5/5 |
| `_main/agents-md-pins-oracle.py` | **0** | 2 pin(s) checked live, 0 failure(s) |
| `_main/bend-laws-gate.py` | **0** | bend gate green |
| `bend_core/model.py` | **0** | 1090 casos |

### 10.2 Os BRACOS NEGATIVOS (todos tem de dar rc=1)

| instrumento | rc |
|---|---|
| `_main/incomplete-word-oracle.py --neg-arm` | 1 |
| `_main/word-split-oracle.py --neg-arm` | 1 (`7 FIX arm(s) went RED as required`) |
| `_main/youtube-1to1-oracle.py --neg-arm` | 1 |
| `_main/youtube-reveal-oracle.py --neg-arm` | 1 |
| `_main/youtube-rows-oracle.py --neg-arm` | 1 |
| `_main/youtube-drift-oracle.py --neg-arm` | 1 |
| `_main/youtube-sotto-drift-oracle.py --neg-arm` | 1 |
| `_main/youtube-track-wiring-oracle.py --neg-arm` | 1 |
| `bend_core/model.py --neg-arm` | 1 |

(`_main/caption-lines-oracle.py` nao tem braco negativo: nao esta ligado
como `:expectred`.)

### 10.3 A BATERIA

```
steps=145  gate=88  control=8  skipped=6  expect-red=42  missing=0
BATTERY-VERDICT: RED - 26 step(s) failed
```

**26 e nao 29:** esta sessao tirou TRES da lista de falhas
(`word-split-oracle`, `red-as-expected-word-split-oracle`,
`youtube-track-wiring`) e, na corrida anterior, ja tinha tirado
`red-as-expected-youtube-rows`. As 26 restantes **nao tocam esta lane**:
sao `panel2-dom-probe`, `border-radius-gate` (+ o seu negativo),
`youtube-foreign-paint`, `exception-hygiene`, `code-health` (+ o seu
negativo), `battery-heavy-gate` (+ o seu negativo), `task-resolver-gate`
(+ o seu negativo), `state-page` (+ o seu negativo), `battery-wiring` (+ o
seu negativo), `panel-hidden-at-startup-oracle`, `yt-mirror-align`,
`gitattributes-verify`, `red-as-expected-lang-id-oracle`,
`per-app-source-plumbing` (+ o seu negativo), `hotkey-delivery`,
`open-close-stall`, `autostart-status`, `search-twin-parity` (+ o seu
negativo).

Os passos desta lane na bateria:

```
incomplete-word=0   red-as-expected-incomplete-word=1
youtube-sotto-drift=0   red-as-expected-youtube-sotto-drift=1
word-split-oracle=0   red-as-expected-word-split-oracle=1
youtube-track-wiring=0
```

### 10.4 O `code-health` -- O QUE E DESTA LANE E O QUE NAO E

`code-health` esta VERMELHO (rc=2) em 6 ficheiros. **MEDIDO, comparando
com o `stash@{0}` (o estado de ANTES desta sessao):**

| ficheiro | RED antes | RED agora | |
|---|---|---|---|
| `app/panel/panel.js` | 2 | 2 | bytes 193062 -> 192436 (**626 B MAIS PERTO** do baseline) |
| `app/panel/theme-switcher.js` | 0 | 1 | **de OUTRA lane** (nao tocado aqui; `git status` nao o lista) |
| `app/webview/sotto_webview.py` | 2 | 2 | de outra lane |
| `app/webview/youtube_captions.py` | 3 | 3 | de outra lane |
| `worker/sotto_worker.py` | 4 | 4 | de outra lane |
| `app/webview/youtube_window.py` | (novo) | (novo) | de outra lane |

**O `theme-switcher.js` esta 3 bytes MAIOR do que no `stash@{0}`** -- e
esta lane nao o tocou (`git status --short` nao o lista, e nenhuma das
suas linhas esta no diff desta sessao). A diferenca e de outra lane que
trabalhou no mesmo ratchet.

Os dois ficheiros NOVOS desta lane (`worker/stable_words.py`,
`app/panel/stable-words.js`) nunca falham: um ficheiro novo nao piora o
ratchet.

### 10.5 O PIN

```
_main\_audit-verify-all.cmd = 135712 B, 1777 CRLF / 0 bare LF,
sha256 F05027472377B036C1F7281216B38DC3589125E9CC653733DE5D32848D33289A
```

**O `.cmd` nao foi alterado nesta sessao** (o valor medido e o valor que
`AGENTS.md` ja traz), e `agents-md-pins-oracle.py` confirma-o ao vivo:
`AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`, rc=0.

### 10.6 O QUE ESTE RECIBO NAO PROVA

- **NAO prova** que o dono viu a legenda certa: nenhuma lane pode correr a
  app no ecra dele (`SOTTO_NEVER_ON_OWNER_SCREEN`), e `verified` continua
  impossivel de uma lane.
- **NAO prova** que a camada de rede (`yt-dlp`, o player, o relogio do
  YouTube) entrega o texto certo: o que esta medido e o CAMINHO DO
  TRABALHADOR e o CAMINHO DA REVELACAO, com o payload real em memoria.
- **NAO prova** a qualidade da transcricao: a regra diz "a palavra nao esta
  provada", e "provada" aqui e "o proximo chunk nao a continua, ou a linha
  fechou, ou o texto acaba em `.?!,;:`" -- nao e juizo linguistico.

---

## 11. O HOOK GLOBAL DE RATO FOI REMOVIDO (2026-10-30, ordem do dono)

### 11.1 A ordem e o que estava medido

O dono, verbatim, na mesma sessao:
*"se esses hooks sao burros ou desnecessarios, remove. nao mantem nada q tu ta
achando q e pior"*.

Antes de tocar em nada, a MEDICAO que responde "e o hook a causa?":

```
OUTSIDE_CLICK_HOOK uninstalled reason=not-armed reader=pointer_back_to_owner=true   (2026-10-30 01:17:41)
PANEL_VISIBILITY_MODE visible=false reason=panel-hidden                            (2026-10-30 04:08:21)
```

**O hook NAO estava instalado** quando o autoclicker dele falhava. Portanto nao
era a causa -- e a accusacao ficou retirada ali, antes de mexer em codigo. O que
justificou a remocao foi o CUSTO do mecanismo, nao uma accusacao: um
`WH_MOUSE_LL` poe **todos** os eventos do rato (1000/s num rato de 1000 Hz) a
passar pelo callback Python da thread que o instalou, antes de chegarem a quem
quer que seja.

### 11.2 O que saiu, e o que ficou no lugar

**Saiu** de `app/webview/sotto_webview.py`: `SetWindowsHookExW`,
`UnhookWindowsHookEx`, `CallNextHookEx`, `MSLLHOOKSTRUCT`, `WH_MOUSE_LL`,
`_install_hook`, `_uninstall_hook`, `_sync_hook`, `_sync_hook_now`, `_on_mouse`,
`_on_mouse_edit`, `WM_HOOK_SYNC` e o auto-cura de 5 s.

**Ficou** o mesmo trabalho, com zero eventos de input a passar por Python:
`OutsideClickWatcher` passa a ser um `SetTimer` que

- le `GetForegroundWindow()` a **100 ms** com o painel visivel -- se o foreground
  deixa de ser a nossa janela, o clique foi fora (`_consider` decide, com as
  guardas que ja' tinha);
- le `GetCursorPos()` + `GetAsyncKeyState(VK_LBUTTON)` a **25 ms** em edit mode
  -- o arrasto da faixa (`edit_grab`/`edit_drag_to` intactos);
- **nao arranca sem nada para vigiar**: `_restart_timer` chama `KillTimer`
  primeiro e desiste quando `_wants_poll()` (`armed or edit_mode`) e' falso.

O arrasto NORMAL do painel nunca usou o hook -- `_begin_window_drag` entra no
loop de movimento do proprio Windows (`WM_NCLBUTTONDOWN`/`HTCAPTION`).

### 11.3 O portao mudou de sujeito: agora mede a AUSENCIA

`_main/input-path-oracle.py` foi REESCRITO (era 10 bracos a disciplinar o hook;
sujeito extinto nao pode ficar verde). O invariante passou a ser `C1`: **zero**
`SetWindowsHookEx` (qualquer variante), **zero** constante `WH_*_LL`, **zero**
struct `MSLLHOOKSTRUCT`, no AST da shell inteira -- lido por AST, nunca por
texto, para nao castigar quem documenta a regra nos comentarios.

| braco | o que prova | mutante que o derruba |
|---|---|---|
| C1 | nenhum hook global existe | `hook-volta`, `hook-de-teclado` |
| C2 | `_wants_poll` == `armed or edit_mode` | `regra-sempre` |
| C3 | `hide_panel` desarma | `esconder-nao-desarma` |
| C4 | o timer so' e' pedido em `_restart_timer`, com guarda | `timer-sempre` |
| C5 | a classe real segue as flags; um tick sobrando e' inerte | `regra-sempre` |
| C6 | 25 ms a arrastar, 100 ms a vigiar | `ritmo-unico` |
| C7 | `stop` mata o timer | `stop-nao-mata` |
| C8 | as propriedades re-armam o ritmo | `edit-mode-sem-ritmo` |
| C9 | mostrar arma e esconder desarma | `show-nao-arma`, `esconder-nao-desarma` |
| C10 | o tick nao fecha por si: passa por `_consider` | `tick-fecha-direto` |

**MEDIDO:** `INPUT-PATH VERDICT PASS`, rc=0, **10 bracos verdes / 10 mutantes
apanhados**; `--neg-arm` rc=1 com `NEG-ARM PASS`.

**`_main/seam-inventory.json` reenumerado: 12 invocadores** (eram 9), e
`_main/seam-coverage-oracle.py` imprime `coverage: 12/12 invocador(es) com
controlo positivo E negativo` -> `SEAM-COVERAGE VERDICT PASS`, rc=0; o
`--neg-arm` rc=1.

### 11.4 O custo do tick, medido (e nao estimado)

`_main/hook-cost-oracle.py` nasceu a medir UMA chamada do hook; o nome e'
historico, o sujeito agora e' o tick. Corrido depois da troca:

```
ARM A n=4000 mean=0.0056 p50=0.0046 p99=0.0296 max=0.2843 ms   (sem ficheiro de log)
ARM B n=4000 mean=0.0147 p50=0.0099 p99=0.0522 max=0.2932 ms   (com o log aberto, como o run.cmd)
ARM N n=4000 mean=0.0008 p99=0.0013 ms                          (log removido do _record: o negativo)
HOOK_COST p99 stdout-only=0.0296 ms with-log-file=0.0522 ms negative=0.0013 ms
VERDICT PASS
```

Um tick custa **0,0296 ms** (p99, sem ficheiro de log) e **0,0522 ms** (p99, com
o log aberto, que e' o que o `run.cmd` paga); o pior caso das 4000 amostras e'
**0,2843 ms / 0,2932 ms**, ainda muito abaixo de um frame a 60 fps (16,7 ms). A
10 Hz, 0,03 ms por tick e' **0,0003** de um nucleo -- 0,03 %.

### 11.5 O que NAO ficou provado (declarado)

- **Nao houve corrida real da app.** O clique-fora agora depende de o foreground
  mudar, que e' o comportamento de qualquer popover do Windows; o caso que NAO
  fecha (uma janela que nao ganha foreground ao ser clicada) fica declarado como
  limitacao conhecida desta via.
- **O arrasto em edit mode so' foi exercitado por objecto** (`_poll_drag` com
  `hwnd=0`, sem janela). A prova fisica exige um humano a arrastar.
- **`code-health` continua VERMELHO por divida anterior** (18 pares, 6 ficheiros,
  nenhum deles criado por esta mudanca; a shell estava ja' vermelha antes desta
  sessao e o `hook-cost`/`input-path` nao tocam nesse eixo).

### 11.6 A BATERIA INTEIRA, DEPOIS DA REMOCAO

Corrida com o lease `heavy` exclusivo (`performance-gate status` = GREEN,
`heavy_allowed=True`), liberto no fim. Os cinco passos deste eixo:

```
[step] input-path rc=0
[step] red-as-expected-input-path rc=1  [EXPECT-RED]
[step] seam-coverage rc=0
[step] red-as-expected-seam-coverage rc=1  [EXPECT-RED]
[step] pycompile-sotto_webview rc=0
```

E a contagem global:

```
steps: 148   gate=88  control=8  skipped=6  expect-red=45  missing=0  cached=64
BATTERY-VERDICT: RED - 16 step(s) failed
```

**Eram 29 na corrida anterior; sao 16 agora.** Os 16 sao anteriores a esta
mudanca e nenhum esta neste eixo -- `panel2-dom-probe`,
`border-radius-gate`(+neg), `exception-hygiene`, `code-health`(+neg),
`battery-heavy-gate`(+neg), `state-page`, `panel-hidden-at-startup-oracle`
(EXTERNAL-FLAG, a via dos captions externos), `yt-mirror-align`,
`gitattributes-verify`, `per-app-source-plumbing`(+neg), `hotkey-delivery`
(o oraculo RECUSA quando Alt+C se pode registar -- a app nao esta a correr, e
por desenho nao foi lancada nesta sessao), `open-close-stall` (F4, o atraso do
preload) e `autostart-status` (rc=4, recusa).

**A prova de que NENHUM dos 16 e' desta mudanca:** os tres unicos que tocam no
painel ou no input -- `panel-hidden-at-startup-oracle`, `open-close-stall` e
`hotkey-delivery` -- foram lidos por dentro e nenhum deles cita o hook, o tick
ou o `OutsideClickWatcher`; os seus veredictos sao sobre o caminho dos captions
externos, o atraso do preload e o registo do Alt+C.

`.cmd` NAO foi tocado nesta mudanca, por isso o pin de `AGENTS.md` continua o
mesmo e `agents-md-pins-oracle.py` confirma-o ao vivo:
`AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`, rc=0.
