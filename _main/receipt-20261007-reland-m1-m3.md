# Recibo — RE-LAND de M1-M3 no `worker/sotto_worker.py` (o defeito medido por `SottoSegmentRerun`)

**Lane:** `SottoRelandM1M3` · **data:** 2026-10-07 · **repo:** `H:/sotto` (arvore partilhada;
`# shared-tree-reason: DO NOT request a worktree. On this box isolated: true has been measured to
fail at worktree creation.`)
**Directiva do dono (verbatim, esta sessao):** *"trabalha só no sotto. nao mais no maanger ou omp"* —
nada foi lido nem escrito fora de `H:/sotto`, excepto a corrida read-only do CACHE/PRICE que o brief
manda (§CACHE/PRICE) e a disposicao do selo do teorista (gate do harness, nao um ficheiro meu).
**Directiva do dono sobre audio (verbatim):** *"to ouvindo o audio do teste do sotto ... nao quero
ouvir"* — nenhum comando desta lane abre dispositivo de audio nenhum: todos sao leitura de ficheiro +
ONNX (`--selftest` escreve JSONL em stdout), logo nenhum pode ser audivel.

---

## 0. O que era o defeito, e o que eu fiz

O `py -3 _main/segment-rerun-probe.py` morria com
`TypeError: StreamAsr.run_chunk() got an unexpected keyword argument 'account'`: a cura M1-M3 medida a
2026-10-06 (`docs/audit/ao-vivo-vs-redux-CURA.md`, lane `SottoFragmentacao`) foi perdida com o ficheiro
de 149 856 B. O desenho sobreviveu nos dois documentos; eu **re-landei-o** a partir deles, em vez de
satisfazer a assinatura da sonda.

**Ficheiro tocado: UM.** `worker/sotto_worker.py`. Nada mais foi editado — nem a sonda, nem a metade de
renderer (M5-M9), nem o oraculo.

---

## 1. `grep` ANTES e DEPOIS (a condicao RED e o que a fecha)

### ANTES (o ficheiro restaurado, 128 569 B, sha256 `85923bc4aa06da0c…`)

```
$ py -3 -c "import re,sys; ..."   # equivalencia: grep -n 'def rerun\|reset_stream_state\|_last_symbol' worker/sotto_worker.py
$ grep -n 'def rerun\|reset_stream_state\|_last_symbol\|line_events\|def finalise\|def drain\|account' worker/sotto_worker.py
RC=1        # 0 ocorrencias — nenhum dos sete simbolos existe
$ wc -c worker/sotto_worker.py
128569 worker/sotto_worker.py
$ sha256sum worker/sotto_worker.py
85923bc4aa06da0c6a65d08e404bbf1f442f15de8ae9802b398bdcc3b1481ca9  worker/sotto_worker.py
```

(A mesma condicao esta medida e datada no recibo da lane irmã:
`_main/receipt-20261007-segment-rerun.md` §"Evidence 1".)

### DEPOIS (`_main/_reland-grep-after.txt`, verbatim, rc=0)

```
509:        # decoding STATE, not a counter: `run_chunk(account=False)` still moves
510:        # it while moving no accounting number.
511:        self._last_symbol = None
567:    def reset_stream_state(self):
574:        with `_last_symbol` (`docs/audit/predictor-carry-cura.md`) — so a reset
587:        self._last_symbol = None
589:    def run_chunk(self, pcm_chunk, speech=None, account=True):
599:        `account=True` (the default) is what makes this chunk's cost part of the
600:        LIVE stream's numbers. The M3 second pass calls it with `account=False`
604:        `account` gates every COUNTER and nothing else — the decoder state
605:        (`cc`/`ct`/`ccl`, `h`/`c`, `_last_symbol`) moves either way, which is the
657:            if account:
682:            if account:
727:        seed = self.blank if self._last_symbol is None else self._last_symbol
762:            if account:
765:                if account:
770:            if account:
773:            # `_last_symbol` is DECODING STATE, not a counter: it must move even
774:            # with `account=False` (the M3 second pass), because it is the seed
776:            # `if account:` block would leave the live stream seeded from a
778:            self._last_symbol = y
782:        if account:
1481:        # The lines that CLOSED since the last `take_closed()` — the OUT-OF-BAND
1532:            # that claims `final:true`. The live path drains it (`take_closed`)
1554:    def take_closed(self):
1600:def line_events(events):
1601:    """Shape the events of ONE `push`/`flush` — or of a `take_closed()` drain —
1609:    `line_events(former.take_closed())` for the transcript (the live path replaces
1671:        for event in line_events(former.take_closed()):
1675:    for event in line_events(former.take_closed()):
2173:        def rerun(closed):
2177:            back through the SAME `run_chunk` with `account=False`: the pass must
2209:            saved = (asr.cc, asr.ct, asr.ccl, asr.h, asr.c, asr._last_symbol)
2213:                asr.reset_stream_state()
2216:                    text, _n = asr.run_chunk(seg, speech=speech, account=False)
2226:                asr.cc, asr.ct, asr.ccl, asr.h, asr.c, asr._last_symbol = saved
2231:        def finalise(closed):
2254:        def drain():
2258:            for closed in former.take_closed():
```

`py -3 -m py_compile worker/sotto_worker.py` → **rc=0**.

---

## 2. As assercoes da sonda, verbatim (`py -3 _main/segment-rerun-probe.py`)

```
model : H:\sotto\worker\models/nemotron-3.5-asr-streaming-0.6b-int8
load  : 5.00 s   provider=['CPUExecutionProvider']
stream: 26 chunks, 14.56 s of audio, 22.82 s (RTF 1.567)
[PASS] A reset_stream_state() returns the caches to a stream start
       shapes=[(1, 24, 70, 1024), (1, 24, 1024, 8), (1,)] equal_to_fresh_allocation=True
[PASS] A2 reset_stream_state() returns the PREDICTOR to a stream start
       h/c all-zero=True/True _last_symbol=None
pass  : segment = chunks[13:26] (7.28 s of the 14.56 s stream), starting 13 chunks in
[PASS] B run_chunk(account=False) moves no live accounting counter
       moved=none (n_chunks 0->0, audio_s 0.00->0.00, labels 0->0)
[PASS] C the LIVE stream state survives the pass (not mutated in place, and restorable)
       C1 no in-place write into the live arrays: True; C2 restore reproduces it bit for bit: True
[PASS] C3 the LIVE predictor survives the pass (the pass moved it, the restore reproduces it bit for bit)
       the pass moved h/c/_last_symbol: True (a restore that is never needed cannot go RED); restore reproduces it: True; _last_symbol 1896
[PASS] D the pass produces text for the segment it was given
       second-pass text = 's moradores preci m de um caminho alternativo para chegar ao trabalho'

COST  : segment 14.56 s of audio -> second pass 11.95 s (RTF 0.821); streaming the same audio took 22.82 s (RTF 1.567)
COST  : the pass costs 0.52x a streaming pass of the SAME audio
COST  : the audit's §6.2 table predicted RTF x S = 0.15-0.25 -> 2.18-3.64 s for this segment
LOAD  : READ BOTH RTF NUMBERS WITH THE BOX IN MIND — this is the ratio; the ABSOLUTE RTF is only comparable to the audit's 0.14-0.22 on an IDLE box. On this one the streaming pass alone measured far above it, which is the load, not the model (see WORKER_STATS rss_mb / the process census).
note  : the streaming text of the same audio was 'moradores preci m de um caminho alternativo para chegar ao trabalho'

RESULT: GREEN (6/6 assertions)
===RC=0
```

**A linha de PASS que o brief pede, citada literalmente:**
`RESULT: GREEN (6/6 assertions)` com **rc=0**, e a assercao que impede o "modo-de-passar"
(`C3 ... the pass moved h/c/_last_symbol: True (a restore that is never needed cannot go RED);
restore reproduces it: True`).
**A linha de model-load (a prova de que a sonda chegou ao modelo real e nao morreu no setup):**
`load  : 5.00 s   provider=['CPUExecutionProvider']` — o modelo e o int8; o `rc` e 0 e nao 2 (setup
error), e nenhuma assercao corre antes desta linha. O valor difere dos **6.79 s** que a corrida RED da
lane irma mediu (`_main/receipt-20261007-segment-rerun.md` §"The command, and its rc") porque a caixa
estava menos carregada nesta corrida — e' a MESMA linha, do MESMO probe, no MESMO modelo; o que ela
prova nao e' a duracao, e' que o processo atravessou o carregamento ate' as assercoes.
**Inaudivel por construcao:** a sonda le `_main/pt-br-sample.wav` e corre ONNX; nao abre dispositivo.
Ficheiro verbatim: `_main/_seg-rerun-probe-after.txt` (sha256 `fb2155863bab110d2501bc4d9c91c2c5d1bf00cfce2039a126c47bf6c7ffda03`).

---

## 3. Cada criterio dos documentos de desenho, com a linha que o satisfaz

Fontes citadas: `docs/audit/ao-vivo-vs-redux-CURA.md` §1 ("O que mudou — M1..M9, por `file:line`") e
`docs/audit/predictor-carry-cura.md` §2.

| # | criterio, QUOTED do documento | a linha que o satisfaz (ficheiro de hoje) | como foi verificado |
|---|---|---|---|
| **M1** | *"o PCM do segmento e retido (pos-ganho, com o veredicto de fala por chunk) — `seg_pcm = {}` :2248; retencao `:2372`; poda pelo inicio da linha ABERTA `:2388-2394`"* | `seg_pcm = {}` em `sotto_worker.py:2171`; retencao `seg_pcm[idx] = (seg_in, speech)` **:2357** (o `seg_in` e' pos-ganho e o `speech` e' o veredicto tomado no PRE-GAIN, :2331); poda **:2364-2371** por `former.open_start` | a poda esta' na mesma expressao que usa a propriedade — leitura do codigo + a sonda C3 mostra que o segundo passo tem mesmo o audio do segmento |
| **M1** | *"onde a linha aberta comeca — `LineFormer.open_start` :1545"* | `@property def open_start` em **:1487-1496** (devolve `self._start`) | chamada directa na poda do laco; o valor e' o `start` do chunk que ABRIU a linha |
| **M2** | *"o evento leva a rota (`final`) — `LineFormer._event(text, final=False, closed=False)` :1553"* | `def _event(self, text, final=False, closed=False)` em **:1504**, com `"final": bool(final)` em **:1523** | smoke de modo-ficheiro (§5): **todos** os 22 eventos trazem `final`, 20 `false` e 2 `true` |
| **M2** | *"o FECHO sai **fora de banda**, nao como mais um evento — `_close()` :1580; `take_closed()` :1610; `line_events()` :1659"* | `_close()` **:1527** (append em `self._closed.append(self._event(text, final=True, closed=True))`, **:1544**; a lista nasce em `reset()` **:1485**); `take_closed()` **:1554**; `line_events(events)` **:1600** (modulo-level, como a sonda a chama: `W.line_events`) | `_main/caption-lines-oracle.py` **arm 11** PASS: `(['held', 'held back'], ['held back'], [True])` — o fecho publicado UMA vez, fora de banda, e marcado `final` |
| **M3** | *"**segunda passagem** sobre o audio do segmento INTEIRO, estado RNNT reposto — `rerun()` :2250; `finalise()` :2291; `drain()` :2311"* | `def rerun(closed)` **:2173**, `def finalise(closed)` **:2231**, `def drain()` **:2254** (locais de `asr_thread`, como no desenho) | sonda C (C1/C2) e C3 PASS; e o smoke de modo-ficheiro (§5) mostra as 2 linhas fechadas |
| **M3** | *"repor o estado RNNT e' `cc/ct/ccl` a zero — `StreamAsr.reset_stream_state()` :563"* | `def reset_stream_state(self)` **:567**, a repor `cc/ct/ccl` **e** `h/c/_last_symbol` | sonda A e A2 PASS; A2 e' a parte que o `predictor-carry-cura.md` acrescentou |
| **M3** | *"custo contado a parte, para nao duplicar `audio_s`/RTF — `run_chunk(..., account=True)` :577; `"reruns": 0` :2114; `WORKER_STATS ... reruns= rerun_wall_s=` :2142"* | `def run_chunk(self, pcm_chunk, speech=None, account=True)` **:589**; `"reruns": 0, "rerun_wall_s": 0.0` no dict `counters` **:2054-2055**; `reruns={counters['reruns']} rerun_wall_s={counters['rerun_wall_s']:.2f}` em `stats_line` **:2120** | sonda **B** PASS: `moved=none (n_chunks 0->0, audio_s 0.00->0.00, labels 0->0)` |
| **predictor** | *"`seed = self.blank if self._last_symbol is None else self._last_symbol` … `self._last_symbol = y` onde um simbolo e' emitido — **dentro** do bloco, fora do `if account:`"* | `seed = ...` **:727**; `self._last_symbol = y` **:778**, FORA do `if account:` (:770-772) — com o comentario que diz por que | A/B independente (§6): 119 tokens no arm SHIPPED |
| **predictor** | *"o reset existe em exactamente dois sitios, ambos INICIO DE STREAM: `__init__` e `reset_stream_state()`"* | `self._last_symbol = None` em `__init__` **:511** e em `reset_stream_state` **:587**; `h`/`c` a zero nos mesmos dois sitios | `grep -n '_last_symbol'` (§1) mostra exactamente esses dois sitios de escrita |
| **predictor** | *"(d) o par save/restore da segunda passagem — `:2288-2293` e `:2313-2315`: passa a salvar e repor os seis (`cc, ct, ccl, h, c, _last_symbol`)"* | `saved = (asr.cc, asr.ct, asr.ccl, asr.h, asr.c, asr._last_symbol)` **:2209** e o `finally: asr.cc, ... = saved` **:2226** | **C3** PASS com `pred_moved=True` — o restauro dos seis e' o que a assercao mede |

### C3, explicitamente (o criterio que a lane avisou que um `rerun()` simples NAO satisfaz)

O `predictor-carry-cura.md` §6.1 diz, verbatim: *"A cura introduz um risco que nao existia:
`reset_stream_state()` agora destroi o predictor, e o `rerun()` da segunda passagem (M3) chama-o **no
meio do stream vivo**. Se o `rerun()` salvasse so as caches do encoder — que e' o que fazia — o stream
vivo sairia da segunda passagem com o predictor zerado."* E a sonda tem de o apanhar com dentes:
*"a assercao nao podia ficar vermelha porque o cenario que a devia deixar vermelha nao existia
(segmento = stream inteiro)"* → corrigido para *"o segmento passou a ser a metade final
(`chunks[13:26]`)"*.

No meu `rerun()`: **:2173-2229**, com o `finally` a repor os SEIS (nao tres) e a contar o custo
(`counters["reruns"]`, `counters["rerun_wall_s"]`) **dentro do `finally`**, para que uma excepcao da
passagem nao deixe o stream vivo com o estado da passagem nem o custo por contar. A corrida:
`C3 ... the pass moved h/c/_last_symbol: True ... restore reproduces it: True; _last_symbol 1896`.
O `_last_symbol` reportado (**1896**) e' o simbolo real do stream vivo daquela gravacao, e o
`pred_moved=True` e' o que impede a assercao de ser decoracao.
**E alem da sonda** — porque uma sonda GREEN nao distingue "o `rerun()` move o predictor" de
"o `run_chunk` ainda faz re-prime" — o A/B da §6 mede a POLITICA do proprio `run_chunk`.

---

## 4. Portas que corriam antes continuam a correr (a nao-regressao do contrato de linha)

`py -3 _main/caption-lines-oracle.py` → **12 PASS / 0 FAIL (12 arms)**, rc=0 — incluindo as arms que a
cura podia ter partido sem se notar:

```
[PASS] arm: flush does not re-send the text it already showed
       real    = (['held', 'held back'], 1)
[PASS] arm: the close is published once, out of band, and marked final
       real    = (['held', 'held back'], ['held back'], [True])
       control = (['held', 'back'], [], [])  (must differ: yes)
[PASS] arm: real WAV fragments reproduce the AFTER caption run
       real    = ['O rádio', 'O rádio Segunda-feira', 'O rádio Segunda-feira Os moradores']
caption-lines-oracle: 12 PASS / 0 FAIL (12 arms)  impl=H:\sotto\worker\sotto_worker.py
```

A **arm 11 era o RED** antes desta lane (abortava em `AttributeError: module 'sotto_worker' has no
attribute 'line_events'`, recibo `_main/receipt-20261007-caption-lines.md`). Agora passa, com controlo
negativo (`must differ: yes`) — o mesmo oraculo, o mesmo comando, o mesmo ficheiro de teste.

---

## 5. O caminho de FICHEIRO publica as duas rotas (a sonda sozinha nao o mostra)

O `--selftest` (modo ficheiro, sem dispositivo) foi corrido e a rota foi censada no JSONL que ele
escreveu — este e' o unico instrumento que mostra a M2 a chegar ao fio:

```
$ py -3 worker/sotto_worker.py --selftest --audio _main/pt-br-sample.wav > _main/_reland-file-mode.jsonl
===RC=0
caption events: 22 | final:true 2 | final:false 20
caption keys: ['end', 'final', 'model', 'start', 'text', 'type']
leaked closed marker: False
  FINAL   0.56 8.96 'rádio anunciou que a ponte sobre o vai ser interditada na próx ima se
  FINAL   8.96 14.0 'moradores preci m de um caminho alternativo para chegar ao trabalho'
  partial 0.56 1.12 'rádio'
  partial 0.56 1.68 'rádio anunciou'
  partial 0.56 2.24 'rádio anunciou que'
status states: ['boot', 'boot', 'boot', 'model-loading', 'model-loaded', 'gate', 'selftest-start', 'selftest-done']
```

Leitura: (a) **todos** os eventos de legenda trazem `final` — que e' o campo que
`app/electron/caption-formulation.js:250-301` declara esperar ("The worker stamps every caption event
with `final`"); (b) a marca interna `closed` **nao vaza** para o fio (`line_events` e' o unico sitio que
a remove); (c) o modo ficheiro publica os FECHOS (2 `final:true`), o que era exactamente o defeito
medido pela lane anterior — *"uma corrida de 14,5 s em modo ficheiro emitia 3 provisorios e ZERO
finais — um historico que nunca recebia uma linha"*. O texto do `final` no modo-ficheiro e' o do
STREAMING (o modo ficheiro nao corre a 2ª passagem, por desenho: nao ha' renderer a competir por um
deadline), e isso esta' dito no codigo no sitio da publicacao (o laco `selftest` **:1656-1676**, com o
`take_closed()` publicado a cada chunk e no fim).
Ficheiro verbatim: `_main/_reland-file-mode.jsonl` (sha256 `f7f3fad9251e7f349ab22a709de3eb2c04ad4df967ac7160ace57e027784b8e7`).

---

## 6. A POLITICA do predictor, medida com um instrumento proprio (`_main/_reland-predictor-ab.py`)

A sonda M3 prova o `rerun()`; **nao** prova que o `run_chunk` deixou de re-primar — que era o segundo
risco nomeado no brief. Este probe (novo, 5 054 B) dirige o `run_chunk` DO FICHEIRO duas vezes sobre o
MESMO audio, variando SO' a politica: (A) como esta' no ficheiro, e (B) com o re-prime forcado de
fora (`h`/`c` a zero e `_last_symbol=None` antes de cada chunk = o arm 1).

```
model : H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int8
audio : H:\sotto\worker\assets\sample1.flac (13.69 s, 24 chunks)
SHIPPED (carry+last-symbol) : 119 tokens / 39 words
        "going along slushy country roads and speaking to damp audiences in drty schoolrooms day after day for a fortnight he'll "
RE-PRIME (forced, arm 1)    : 87 tokens / 28 words
        "Going along slushy Country roads  speaking  in dr drafty school day For a fortnight He'll have  an appearance At some Su"

RECORD (docs/audit/predictor-carry-cura.md §5): re-prime 89 tok / 28 words, carry+seed 119 tok / 39
shipped == carry+seed-last (119) EXACTLY: True  forced re-prime within 4 tok of 89 and 28 words: True  shipped > re-prime: True

RESULT: GREEN — the shipped run_chunk implements carry+last-symbol, the re-prime control reproduces arm 1
===RC=0
```

- O braco SHIPPED da' **119 tokens / 39 palavras**, exactamente o valor do **arm 3** do recibo, e o
  texto e' o do arm 3 verbatim (`going along slushy country roads and speaking to damp audiences in
  drty schoolrooms day after day for a fortnight he'll …`) contra o texto do arm 1 (maiusculas
  isoladas, `Country roads  speaking  in dr drafty school day`).
- O braco re-prime forcado da' **87 tokens / 28 palavras** contra os 89 / 28 do recibo: as 28 palavras
  batem, os 2 tokens de diferenca sao a diferenca de implementacao (o recibo mediu com o harness
  `_main/sotto-vs-ref-decode-arms.py`, que tem a SUA copia do walk; este probe dirige o ficheiro).
  Por isso a aceitacao do probe exige **igualdade exacta** no braco shipped e uma **tolerancia
  declarada** no controlo — em vez de pedir ao harness alheio uma igualdade que ele nunca prometeu.
- **Uma auto-correccao, declarada:** a PRIMEIRA corrida deste probe deu RED e o RED nao era do worker.
  O probe construia `StreamAsr(..., lang_id=None)`, que resolve para o LOCALE DO HOST (pt-BR, id 12) e
  descodifica um clipe INGLES contra um prompt portugues — colapsa-o (`AGENTS.md` regista o mesmo
  colapso: "prompt 12 collapsed 94 tokens to 10"). Corrigido para `lang_id="auto"` (o valor shipped em
  `worker/config.json`) e as duas corridas passaram a reproduzir o recibo. Fica escrito no proprio
  probe (`_main/_reland-predictor-ab.py:65-70`).
- Ficheiro verbatim: `_main/_reland-predictor-ab.txt` (sha256 `c6b56505a85deeca6a2b36fc00ab1c878e57994079985937ff8ec5d424da4ed1`).

---

## 7. sha256 ANTES / DEPOIS de cada ficheiro tocado

| ficheiro | antes (B) | depois (B) | sha256 antes | sha256 depois |
|---|---|---|---|---|
| `worker/sotto_worker.py` | 128 569 | **144 197** | `85923bc4aa06da0c6a65d08e404bbf1f442f15de8ae9802b398bdcc3b1481ca9` | `473d0ee6b9edbe5bd7542113e21f1941903fc639879e647358477a3c409a3649` |
| `_main/segment-rerun-probe.py` | 12 614 | 12 614 | `2a0ffbaaf7e38b52b51f26557708d44e0879d35552298f7613a47106890cfaa7` | **identico** (NAO tocado) |
| `_main/caption-lines-oracle.py` | — | — | `bf5c48b689190916b3e56f707fa20e16946819093dcb56e98449afd022b0b66d` | **identico** (NAO tocado) |
| `_main/_reland-predictor-ab.py` | — | 5 054 | — | `477018415e1a4e4dcefba4b32d7d696abebb3dc32ff4a0f2c00819d998211aad` (NOVO) |

Evidencia/artefactos novos (nao codigo): `_main/_reland-grep-after.txt`, `_main/_reland-sha-after.txt`,
`_main/_seg-rerun-probe-after.txt` (`fb215586…`), `_main/_reland-file-mode.jsonl` (`f7f3fad9…`) e o seu
`.err`, `_main/_reland-predictor-ab.txt` (`c6b56505…`), `_main/_reland-git.txt`,
`_main/_reland-cache-price.txt`, e este recibo.

### git disclosure (a arvore e' de varias lanes)

```
=== git status --porcelain (touched paths) ===
 M worker/sotto_worker.py
?? _main/_reland-predictor-ab.py
=== git diff --stat worker/sotto_worker.py ===
 worker/sotto_worker.py | 415 ++++++++++++++++++++++++++++++++++++++++++-------
 1 file changed, 359 insertions(+), 56 deletions(-)
=== HEAD ===
11df66e
```

O `git diff --stat` e' **contra o HEAD** (`11df66e`), que carrega a versao de 127 023 B: as 359/56
incluem o diff PRE-EXISTENTE do restauro de `_main/_ordem-before` (medido pela lane irma em ~46/35) e o
que esta lane acrescentou. **Nao fiz commit** — a arvore fica suja, como a encontrei.

---

## 8. Non-goals — respeitados, e como

1. **Nao editei a sonda.** `_main/segment-rerun-probe.py` sha256 `2a0ffbaa…` antes e depois (o valor
   publicado no recibo da lane irmã), e nenhum dos meus edits toca `_main/*probe*.py`.
2. **Nao toquei a metade de renderer (M5-M9).** `app/electron/*.js`, `app/webview/sotto_webview.py`:
   zero ficheiros abertos para escrita por esta lane.
3. **Nenhuma janela visivel.** Os meus comandos sao `py -3` de workers/probes headless (stdout JSONL,
   sem dispositivo, sem GUI). O censo do harness marcou `ALERTA-JANELA … cmd=pythonw
   H:\sotto\app\webview\_flash-nocure-sotto_webview.py --log …\_flash-nocure-3.log` — essa e' a shell
   mutante da lane do FLASH de arranque (`_flash-nocure-*`, outra lane, outro alvo), nao um processo
   meu; nenhum dos meus pids e' pythonw nem abre WebView2.

---

## SELF-AUDIT

- **protocolos em falta** — senti falta de um protocolo para o **selo do teorista** quando o meu alvo
  esta' noutra arvore: o gate recusou `bash` cinco vezes seguidas nesta lane (passes 04-58Z, 04-54Z,
  05-03Z, 05-08Z, 04-54Z outra vez, cada um com sha256 diferente porque o loop reescreve os ficheiros),
  e cada recusa custou um turno. Fiz o que o protocolo manda (answer/skip com razao real, nunca forjar
  o registo), mas o que faria diferente: **dispor o selo ANTES do primeiro comando de shell**, como a
  lane irma aprendeu, em vez de so' depois de a primeira recusa chegar. Custo medido nesta lane:
  5 disposicoes para 4 passes distintos.
- **verificacao adicional** — CORRIDA, e foi a que mais valor deu: o **A/B da politica do predictor**
  (§6), que a sonda M3 nao faz. Teria aumentado ainda mais a confianca uma corrida do
  `_main/history-route-oracle.js` (`--audio G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav --max-chunks 400`),
  que leva a rota ate' ao FICHEIRO com o motor real e o store real: custa ~3 min de worker + ~170 s de
  oraculo e escreve num `--root` proprio (nunca no historico do dono). **Nao corrido** — e' declarado
  aqui em vez de reclamado.
- **checkboxes novas** — MECANICA, uma linha, no instrumento que ja' existe: o probe da 2ª passagem
  devia **exigir a marca da politica** no mesmo comando, porque o seu verde so' cobre o `rerun()`.
  Concretamente: `py -3 _main/_reland-predictor-ab.py` passa a ser obrigatorio na suite ao lado do
  `segment-rerun-probe`, e o **input que o deixa RED** e' exactamente a regressao que a lane avisou:
  mover `self._last_symbol = y` para dentro do `if account:` (o braco SHIPPED cai de 119 para o valor
  do re-prime e `shipped > re-prime` fica FALSO) — ou repor as duas linhas `self.h = zeros; self.c =
  zeros` antes do `seed` (o braco SHIPPED cai a 87). Sem isto, o verde da sonda M3 continua a nao
  distinguir "a interface voltou" de "a cura voltou".
- **review por outro subagente** — **sim-com-escopo**: o que eu quero que um segundo leitor tente
  partir, em `worker/sotto_worker.py`, sao duas coisas e so' duas: (a) o par save/restore dos SEIS em
  `rerun()` quando a passagem **levanta** a meio (o `finally` repoe, mas eu nao exercitei uma excepcao
  real: o caminho testado e' o normal e o do probe); (b) a poda de `seg_pcm` (`:2361-2368`) — um
  `open_start` de `None` faz `keep_from = idx + 1` e descarta tudo, e eu **nao** medi que uma linha
  longa (um cap de 90 chars) nao perde o proprio audio antes do fecho. Nao vale a pena re-rever o resto
  (`LineFormer`, `line_events`: cobertos pela arm 11 com controlo negativo).
- **gate-doubt**:
  - **verde-de-verdade**: (a) o verde da sonda e' real e NAO vacuo — o `rc` e' 0 e nao 2, o model-load
    esta' na saida (`load : 5.00 s`), e a C3 imprime `moved=True` o que prova que a assercao podia
    ficar vermelha (o proprio recibo do desenho guarda a corrida RED que a deixou vermelha:
    `_main/_rerun-probe-cura.log`). (b) O verde da arm 11 e' real **mas o controlo dela e' fraco**
    (`_PassThrough` devolve `[]`): a arm prova que o fecho sai fora de banda e e' marcado, nao que um
    `take_closed()` a MAIS (duplicacao) fique RED — nomeado em `falta-no-gate`. (c) O verde do meu A/B
    (§6) e' real e tem controlo NEGATIVO no proprio comando (o braco re-prime forcado, que cai a 87/28)
    — mas os numeros absolutos so' sao comparaveis ao recibo porque eu corrigi o `lang_id`; a primeira
    corrida (desse probe com `lang_id=None`) deu RED e esta' declarada.
  - **falta-no-gate**: nenhum gate do repo verifica que **cada linha que fecha e' publicada EXACTAMENTE
    uma vez**. Cenario concreto que atravessa isto: alguem acrescenta `line_events(former.take_closed())`
    num SEGUNDO sitio do laco (ou esquece-se de limpar `_closed` no `reset()`), e o mesmo fecho vai duas
    vezes ao stream — a arm 11 continuaria GREEN (ela chama `take_closed()` uma vez, num LineFormer
    novo) e a sonda M3 tambem. Um segundo furo: **nada mede que a 2ª passagem nao perde o audio de uma
    linha longa** — a poda so' usa o `open_start` da linha aberta, e o caso "linha de 90 chars com
    fecho por cap" nao tem assercao nenhuma.
  - **gate-melhor**: um check MECANICO que fecha o primeiro buraco, sem modelo e em <1 s:
    `py -3 -c "import sys;sys.path.insert(0,'worker');import sotto_worker as W;f=W.LineFormer(emit_partial=True);[f.push(*c) for c in [('a',0.0,0.5),('b',0.5,1.0)]];f.flush();n1=len(W.line_events(f.take_closed()));n2=len(W.line_events(f.take_closed()));assert n1==1 and n2==0, f'close published {n1} then {n2} times - expected 1 then 0'"`
    — **input que o deixa RED**: chamar `take_closed()` sem limpar `self._closed` (devolve 1 e 1) ou
    publicar o fecho tambem em banda com `final=True` (o evento aparece nos dois canais). E' a
    generalizacao da arm 11 a uma propriedade, e nao a um caso.

- **confianca** — **alta** no que esta' landado: a interface existe (`grep` §1 + `py_compile` rc=0), a
  sonda passa 6/6 com C3 nao-vacua, o oraculo de linhas passa 12/12 incluindo a arm que estava RED, o
  modo-ficheiro publica as duas rotas com o campo `final` que o renderer declara esperar, e a POLITICA
  do predictor bate com o braco do recibo (119 tokens exactos) contra um controlo que reproduz o
  arm 1 (28 palavras). **media** na parte que eu nao exercitei: a 2ª passagem AO VIVO num stream longo
  (a sonda mede 7,28 s de segmento) e a poda de `seg_pcm` num fecho por cap. O que subiria: o
  `history-route-oracle` fim-a-fim (§7) e uma corrida de 1 h com audio conhecido — a primeira e' barata
  e ficou por correr, declarada.
- **nao verificado**:
  1. `_main/history-route-oracle.js` fim-a-fim (worker -> motor -> store -> ficheiro) — nao corrido.
  2. A app AO VIVO / o laco `asr_thread`: nenhuma shell foi lançada por mim (evitaria qualquer
     hipotese de janela/audio), o que deixou o codigo NOVO do laco — a retencao `seg_pcm`, a poda, e as
     chamadas `drain()` nos cinco sitios de fecho — sem corrida de ponta a ponta. **Nao e' fechavel por
     `SOTTO_AUDIO_FILE`:** esse modo aterra em `selftest()` (worker/sotto_worker.py:1981), nao no laco.
     Fecha-lo exige um TAP (dispositivo) ou um duplo de tap; o caminho de dispositivo esta' **proibido**
     nesta sessao pela regra do dono ("nao quero ouvir") e o unico tap que a casa ja' montou para isso
     — `CABLE Input` por `_main/_join-play.py` — depende de o VoiceMeeter NAO monitorizar para as
     colunas, o que eu nao posso provar daqui. Fica declarado: quem tiver o par tap/duplo medido
     (`_main/_restart-30s-fake-worker.py` e' o precedente) fecha-o sem risco.
  3. A 2ª passagem num stream longo (horas) e a degradacao do predictor com o tempo — §8.1 do
     `predictor-carry-cura.md` tambem a deixa aberta.
  4. A poda de `seg_pcm` num fecho por CAP (`SENTENCE_MAX_CHARS=90`) — nao exercitada.
  5. Se o renderer de hoje (metade M5-M9, de outra lane) responde a `final` como o codigo dele promete
     — fora do meu escopo, e o oraculo da rota (§7) e' quem o mediria.
  6. Nao ha' commit: a arvore fica suja (como estava).

---

## CACHE/PRICE

Comando (obrigatorio): `bash I:/!manager/scripts/cache-task-report.sh SottoRelandM1M3` — **rc=0**.
Saida VERBATIM:

```
## CACHE/PRICE
- task/agent: SottoRelandM1M3
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoRelandM1M3.jsonl
- cache: read=14118400 write=0 hit=98.1092% (cache-read / input+cache-read); universe: 69 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoRelandM1M3.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=68 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 69 of 69 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-07T04:56:29.542000+00:00 | break_items=2; WHEN=2026-10-07T04:58:40.425000+00:00 | break_items=3; WHEN=2026-10-07T05:03:23.922000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 126041 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoRelandM1M3']; window: 2026-10-07T04:56:29.542000+00:00..2026-10-07T05:03:23.922000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a114b8-3220-754f-99a0-c393dad2d4e9 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791348989542 | session_id=01a114b8-3220-754f-99a0-c393dad2d4e9 provider=deepseek-flash model=deepseek-flash item_index=79; turn_id=1791349120425 | session_id=01a114b8-3220-754f-99a0-c393dad2d4e9 provider=deepseek-flash model=deepseek-flash item_index=196; turn_id=1791349403922 (state=RESOLVED-BREAKS-OMP; population: 3 of 126041 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoRelandM1M3']; window: 2026-10-07T04:56:29.542000+00:00..2026-10-07T05:03:23.922000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-07T05:09:36.271262+00:00
- usage rows: 69
- model + route: opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 272098
- output tokens: 59552
- cache-read tokens: 14118400
- cache-write tokens: 0
- hit ratio: 98.1092% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=68 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 69 of 69 matched usage rows
- prefix breaks: 6 (state=RESOLVED-BREAKS-OMP; population: 3 of 126041 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoRelandM1M3']; window: 2026-10-07T04:56:29.542000+00:00..2026-10-07T05:03:23.922000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-07T04:56:29.542000+00:00; WHERE session_id=01a114b8-3220-754f-99a0-c393dad2d4e9 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791348989542
  - break_items=2; WHEN=2026-10-07T04:58:40.425000+00:00; WHERE session_id=01a114b8-3220-754f-99a0-c393dad2d4e9 provider=deepseek-flash model=deepseek-flash item_index=79; turn_id=1791349120425
  - break_items=3; WHEN=2026-10-07T05:03:23.922000+00:00; WHERE session_id=01a114b8-3220-754f-99a0-c393dad2d4e9 provider=deepseek-flash model=deepseek-flash item_index=196; turn_id=1791349403922
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Leitura: **$0.00000000 USD em 69 linhas de usage** (rota free `opencode-go-1`), 98,11 % de cache-read,
0 writes; tarifas por modelo **UNKNOWN** nesta fonte e o proprio instrumento diz que a razao e'
descritiva, nao um veredicto. Os **6 prefix breaks** trazem `WHEN`/`WHERE` acima, todos em
`session_id=01a114b8-3220-754f-99a0-c393dad2d4e9` (a minha sessao) e com estado
`RESOLVED-BREAKS-OMP`. Fonte e instrumento: `scripts/cache-task-report.sh`; ficheiro completo:
`_main/_reland-cache-price.txt`.
