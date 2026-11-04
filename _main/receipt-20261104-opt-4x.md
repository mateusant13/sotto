# Sotto — três cortes de custo no caminho da legenda (2026-11-04)

Lane `Opt4x`, worktree `H:/sotto-wt/Opt4x` (branch `lane/opt-4x`, base `8007032`).
Nenhuma janela aberta, nenhum áudio do dono aberto, nenhum modelo carregado, nenhum
`pip`/`npm` corrido. Todos os números abaixo saem de um comando que está escrito ao
lado dele; o que não foi corrido diz `[INFERENCE]`.

Instrumentos (ficheiros fora do repo, em `I:/cc-tmp/opt4x/`, para o gatilho não os
confundir com produto):

| instrumento | o que mede |
|---|---|
| `prof-lagnote.py` | cProfile + cronómetro no `SottoShell` REAL (o método do `receipt-20261104-profiling.md` §b) |
| `_main/lag-note-cost-oracle.py` | o custo da função sozinha + os 10 campos publicados, contra uma reimplementação independente |
| `blockms-probe.py` / `blockcost-min.py` | cadência de chunk no `FileTap` REAL + custo por segundo de áudio (numpy real) |
| `pump-poll-cost.py` | custo de CPU do laço de poll idle do pump WASAPI, 5 ms vs 2 ms |
| `meter-cadence.py` | a linha `BRIDGE_METER` (IPC) por segundo |
| `panel-ingest-bench3.js` + `ab2.js` | ingest do painel: os DOIS ficheiros (HEAD e worktree) em processos alternados, 7 rondas, 20 000 linhas/ronda, 13 ingests/linha |
| `floor.js` / `floor2.js` | o piso: o protocolo sozinho, e o protocolo + os tokens do contrato |

---

## A tabela

| # | alvo | instrumento | ANTES | DEPOIS | razão | o que custou |
|---|---|---|---|---|---|---|
| 1 | CPU de aplicar uma legenda | `prof-lagnote.py` (cProfile + relógio, classes reais) | **27,4 / 31,7 / 34,7 µs** (3 pares) | **6,6 / 5,2 / 4,9 µs** | **4,15x … 7,05x** (mediana dos pares **6,10x**) | +46 linhas no shell; 10 campos publicados idênticos; 0 chamadas de gerador |
| 1b | idem, só a função | `lag-note-cost-oracle.py` | 16,4 µs (mutante `sort-per-caption`, o código de ontem) | **0,891 µs/legenda** | **18,4x** na função | — |
| 2 | cadência de publicação | `blockms-probe.py` (`FileTap` real, montagem real de chunk) | **p50 596,1 / 602,2 / 591,4 ms** (piso 600) | **p50 561,4 / 557,9 / 562,1 ms** (piso 560) | 600→560 é o TETO do modelo: 1,06x e o resto é zero | +0,31 % de um núcleo (poll do pump) + 0,004 % (tap) + 98 B/s de IPC |
| 3 | ingest do painel | `panel-ingest-bench3.js` (node, ficheiro REAL, dois motores) | **16,65 … 20,75 µs/linha** (mediana das rondas) | **10,26 … 13,26 µs/linha** | **1,55x … 1,80x** — NÃO 4x, ver §3.3 | +113/−37 linhas (comentários incluídos), 0 alocação nova |

O `32,8 µs/linha` do recibo anterior reproduz-se nesta máquina só com a máquina
carregada (o mesmo HEAD deu 33,0 na primeira medição e 15,5–22,9 em rondas
seguidas). Por isso o §3 compara SEMPRE HEAD-contra-worktree na MESMA ronda, e
não o número antigo contra o número novo.

---

## 1. CPU de aplicar a legenda: 31,7 µs → 5,2 µs

### 1.1 O defeito, nomeado

```python
ages.append((int(audio_ms), bool(held), bool(blown), live))
del ages[:-200]
if len(ages) % 25 == 0:          # <-- com a janela CHEIA isto e' SEMPRE verdade
    ordered = sorted(a for a, _h, _b, _l in ages)   # 4 geradores de 200 por legenda
```

`200 % 25 == 0`: a partir da 200.ª legenda o resumo sai em TODAS. Medido no
recibo do profiler: 1 005 000 iterações de gerador em 5 000 legendas = 201 por
legenda, 83 % do caminho de aplicação.

### 1.2 A cura: janela ordenada por inserção + contadores correntes + contador de publicação

`app/webview/sotto_webview.py`, `SottoShell.__init__` e `_caption_lag_note`:

* `_caption_ordered` — a MESMA janela, mantida ordenada por `bisect.insort`; o
  despejo remove a amostra que saiu (`ages.pop(0)`) por `bisect_left`;
  `p50`/`p90`/`max` passam a ser três indexações O(1) no momento de publicar.
* `_caption_over_win` / `_caption_held_win` / `_caption_live_win` — contadores
  correntes (soma ao entrar, subtrai ao sair). Zero `sum()` por legenda.
* `_caption_notes` — o contador que diz QUANDO publicar; a série sai a cada 25
  amostras, como sempre disse que saía. `len(ages) % 25` deixa de existir.
* `_caption_ages` mantém a forma e a ordem antigas `(idade, held, blown, live)`:
  um shell que traga a janela de fora (harness, dublê) é reconstruído DELA
  (`_caption_ordered is None or _caption_ordered_src is not ages`), não de um
  estado implícito — foi assim que as 14 arms antigas continuaram verdes.

Os dez campos publicados são byte-a-byte os mesmos (`n p50 p90 max over held
over_win held_win live_win budget_ms`).

### 1.3 Antes/depois, mesmo instrumento, três pares alternados

```
$ python I:/cc-tmp/opt4x/prof-lagnote.py H:/sotto/app/webview/sotto_webview.py
1k-caption batches s: 0.0320 0.0275 0.0315 0.0268 0.0288
mean us/caption: 29.312          2326754 function calls in 0.542 seconds
  1005000  0.100  <genexpr>   (x2, 201 por legenda)
    5000  0.069  builtins.sorted
   15000  0.061  builtins.sum
    5000  0.024  0.488  _caption_applied

$ python I:/cc-tmp/opt4x/prof-lagnote.py H:/sotto-wt/Opt4x/app/webview/sotto_webview.py
1k-caption batches s: 0.0057 0.0045 0.0043 0.0052 0.0079
mean us/caption: 5.529           268554 function calls in 0.089 seconds
    5000  0.028  on_worker_caption
    5000  0.018 0.042  _caption_applied
    5000  0.011 0.016  _caption_lag_note
```

Três pares (HEAD → worktree, alternados): **27,412→6,611** (4,15x),
**31,679→5,189** (6,10x), **34,720→4,925** (7,05x). Chamadas de função no
perfil: **2 326 754 → 268 554** (8,66x menos). `_caption_applied` cumulativo:
0,488 s → 0,042 s em 5 000 legendas.

Alvo do bilhete: ≤ 6,75 µs. Mediana **5,19 µs**, o pior par **6,61 µs**: dentro.

---

## 2. Cadência de publicação: 604/596 ms → 560 ms

`worker/config.json`: `audio.block_ms` **100 → 40**.

O chunk do modelo são 8960 amostras a 16 kHz = **560 ms**. O tap entrega áudio em
blocos, por isso o chunk só fica completo no bloco em que a soma passa 8960:

* 100 ms = 1600 amostras/bloco → **6 blocos** → piso **600 ms** (sobra 640 amostras
  que deslizam a fase);
* 40 ms = 640 amostras/bloco → **14 blocos EXACTOS** (8960 = 14 × 640) → piso
  **560 ms**, zero sobra.

```
$ python I:/cc-tmp/opt4x/blockms-probe.py 100 40          (três corridas)
block_ms=100  blocos/chunk=6  piso=600 ms  p50=596.1 ms  p50=602.2 ms  p50=591.4 ms
block_ms=40   blocos/chunk=14 piso=560 ms  p50=561.4 ms  p50=557.9 ms  p50=562.1 ms
```

560 ms é o TETO FÍSICO deste desenho (o modelo não devolve nada antes de ter o
chunk inteiro): a razão máxima é 600/560 = 1,07x, e o resto dos 604 ms vistos ao
vivo são fase de escalonamento. Não há 4x para tirar aqui; há os 44 ms de sobra.

### 2.1 O custo, medido nas três rubricas

```
$ python I:/cc-tmp/opt4x/blockcost-min.py        (minimo de 9 rondas, numpy real)
block_ms=100  custo min=252 / 257 us por SEGUNDO de audio
block_ms=40   custo min=358 / 375 us por SEGUNDO de audio     -> +~110 us/s (pior)

$ python I:/cc-tmp/opt4x/pump-poll-cost.py
period=5 ms -> 187 iteracoes/s, CPU do laco=0.312% de um nucleo
period=2 ms -> 404 iteracoes/s, CPU do laco=0.625% de um nucleo   -> +0,31 % de um nucleo

$ python I:/cc-tmp/opt4x/meter-cadence.py
block_ms=100 blocks_per_window=1 janela=100 ms 10.00 Hz linha=39 B -> 390 B/s
block_ms=40  blocks_per_window=2 janela=80 ms  12.50 Hz linha=39 B -> 488 B/s
```

O custo NÃO é plano, e a parte grande não é do tap: `worker/wasapi_loopback.py:969`
deriva o período de poll do próprio block (`min(0.005, max(0.001, block_ms/1000/20))`),
logo 100 ms→5 ms (200 polls/s) e 40 ms→2 ms (500 polls/s). Isso vale **+0,31 % de um
núcleo** — 40x o que a mudança de bloco poupa/ganha no tap. Se o custo tiver de ser
plano, a linha é UMA e é noutro ficheiro (não é desta lane):

```python
period = min(0.005, max(0.005, self.block_ms / 1000.0 / 20.0))   # piso de 5 ms
```

Relatado ao dono, não aplicado: `worker/wasapi_loopback.py` não está nos ficheiros
desta lane.

### 2.2 O que NÃO foi provado

* **O número AO VIVO é `[INFERENCE]`**: a instância do dono não foi reiniciada
  (o launcher não é desta lane) e o worktree não tem `worker/models/` nem
  dispositivo. O `FileTap` mede a aritmética exacta do tap e da montagem do
  chunk; a fase de escalonamento que separa 561 de 604 ms não está medida.
* `SOTTO_OWNER_AUDIO_OK` não foi pedido. `_main/delivery-rate-oracle.py` fica
  `UNMEASURED` (rc=4) no worktree por falta de modelo, não por causa disto.

---

## 3. Ingest do painel: 1,55x–1,80x (NÃO 4x, e porquê)

### 3.1 O que foi cortado (`app/panel/caption-formulation.js`)

| sítio | o que fazia | o que faz |
|---|---|---|
| `words()` | `trim().split(/\s+/).filter(Boolean)` — 3 passagens sobre o texto | `match(/\S+/g)` — 1 passagem, mesmas palavras (medido 243→189 ns) |
| `ingest` (ré-leitura) | `visible().filter(...)` a cada fragmento, mesmo com o buffer VAZIO | o caso vazio escrito à mão; o filtro só corre com buffer |
| `ingest` (`hypothesis`) | `visible().concat(opening)` — array de todo o buffer para o concatenar fora | `committed.concat(provisional, opening)`, e com o buffer vazio a hipótese É o fragmento |
| `ingest` (`prevWords`) | dois `map` sobre a mesma hipótese | uma passagem |
| `ingest` (`fragWords`) | `incoming.map(t => t.w)` — cópia de um array que já existe | `parts` |
| `ingest` (teto) | `visibleText()` = `map().join(' ')` para ler `.length` | `visibleLength()` soma comprimentos |
| tokens | `parts.map((w,i) => ({w, a:…, b:…}))` — closure por fragmento | `claimToken()` num laço com um literal |
| `formulateTokens` | array `merged` + `clean` (14 slots) e 3 regex Unicode por palavra e por iteração | compactação no próprio `parts`; formas minúsculas calculadas só no ramo que as lê; `firstTwo` sem `slice/map/join` |

Um objeto pool de tokens chegou a ser tentado e foi REMOVIDO: medido pior
(11,16 → 10,18 µs, mediana de 7 pares), porque as transições de mapa
`null`→número custam mais do que a alocação que evitam.

### 3.2 Antes/depois (três corridas completas, 7 pares cada)

```
$ cd I:/cc-tmp/opt4x && node ab2.js
run A: MIN old=15.53 new=8.36 (1.86x)   MED old=16.65 new=10.26   ratio mediana=1.73x
run B: MIN old=14.98 new=8.87 (1.69x)   MED old=16.89 new= 9.39   ratio mediana=1.79x
run C: MIN old=18.22 new=10.43 (1.75x)  MED old=20.75 new=13.26   ratio mediana=1.55x
```

O `ab2.js` corre os DOIS ficheiros (HEAD e worktree) em processos separados,
alternados, com o mesmo banco de 64 linhas e a mesma semente. A ronda C é a
máquina mais carregada (HEAD subiu 30 % do B para o C) — por isso a razão
emparelhada é a linha séria, e ela fica em **1,55x–1,80x**.

### 3.3 Porque não há 4x: o piso está medido

```
$ node I:/cc-tmp/opt4x/floor.js
PISO us/line (13 splits, nada mais): 2.22
$ node I:/cc-tmp/opt4x/floor2.js
PISO 2 us/line (tokens do contrato, sem contas): 5.42
```

* 13 `words(fragmento)` por linha custam **2,2 µs** — o protocolo, sem motor.
* 13 fragmentos × 15 palavras = 195 objectos de token + 3 arrays por fragmento
  (o array de tokens e as duas fatias `committed`/`provisional` que o
  renderer do painel consome) custam **5,4 µs** — o CONTRATO, sem nenhuma das
  contas do motor.
* 4x sobre o HEAD desta máquina (15,5–20,8) seria **3,9–5,2 µs/linha**, ou seja
  um valor no piso do contrato e abaixo do que o contrato custa sozinho com as
  contas do motor (8,4–13,3).

Para descer daqui é preciso MUDAR O CONTRATO: passar ao renderer a janela e o
índice de concordância (`committed.length`) em vez de dois arrays de tokens
fatia­dos, ou reutilizar UM array de tokens por linha. As duas coisas mexem na
superfície que `_main/_panel2-dom-probe.js` (94 arms) e
`_main/join-harness.js` (11 arms) fixam — é decisão de quem manter o painel,
não um corte local desta lane. Fica dito, com números, em vez de prometido.

---

## 4. Ficheiros mudados

| ficheiro | função / região | porque |
|---|---|---|
| `app/webview/sotto_webview.py` | `import bisect`; `__init__` (bloco da legenda, ~8860); `_caption_lag_note` (~13101) | janela ordenada por inserção, contadores correntes, contador de publicação |
| `app/panel/caption-formulation.js` | `words`, `visibleLength` (novo), `claimToken` (novo), `formulateTokens`, `ingest` | §3.1 — oito alocações/passagens por fragmento cortadas |
| `worker/config.json` | `audio.block_ms` 100 → 40 + `_comment_block_ms` | §2, com o custo medido escrito ao lado |
| `_main/lag-note-cost-oracle.py` | NOVO, 5 arms, 4 mutantes | custo da função, planura com a janela cheia, os 10 campos contra uma reimplementação independente, cadência de publicação, deslize da janela |
| `_main/caption-lag-budget-oracle.py` | +1 arm `lag-stats-counters-bounded`, +1 mutante | os contadores correntes podem subir e não descer: `n=200` continua e a série mente. É a NOVA forma de falha que esta mudança criou, e o mutante mostra a arm a apanhá-la (`over_win` 58 → 143) |

## 5. Portões

```
$ python _main/lag-note-cost-oracle.py
cost-under-budget            PASS 0.891 us/legenda (orcamento 6.75, recibo 27.1)
cost-flat-with-full-window   PASS janela 20=0.820 us  janela 200=0.853 us  razao=1.04x
series-fields-exact          PASS todos os 10 campos iguais a janela a mao
series-published-every-25    PASS 8 linha(s) para 200 legendas (esperado 8), n=200
series-window-is-200         PASS n=200 max=1474 (esperado n=200 max=1474)
VERDICT: PASS (5/5 arms)            rc=0

$ python _main/lag-note-cost-oracle.py --neg-arm
mutante sort-per-caption         APANHADO (cost-under-budget: 16.365 us; series-published-every-25: 200 linhas)
mutante held-win-zero            APANHADO (series-fields-exact: held_win 11 -> 0.0)
mutante window-never-drops       APANHADO (series-fields-exact, series-window-is-200: n=475)
mutante ordered-never-evicts     APANHADO (series-fields-exact, series-window-is-200: n=475)
NEG-ARM: PASS (4/4 mutantes apanhados)    rc=1

$ python _main/caption-lag-budget-oracle.py
lag-stats-serie              PASS CAPTION_LAG_STATS n=25 p50=112 p90=2400 max=3200 over=2 held=0 over_win=2 held_win=0 live_win=24 budget_ms=1500
lag-stats-counters-bounded   PASS publicado over_win=58.0 held_win=40.0 live_win=171.0 n=200.0 | janela over=58 held=40 live=171 n=200
VERDICT: PASS (15/15 arms)          rc=0

$ python _main/caption-lag-budget-oracle.py --neg-arm
mutante contador da janela sobe e nao desce APANHADO (lag-stats-counters-bounded: publicado over_win=143 vs janela 58)
NEG-ARM: PASS (11/11 mutantes apanhados)   rc=1

$ node _main/_panel2-dom-probe.js      RESULT: GREEN — 94/94 arm(s)
$ node _main/join-harness.js           REAL JOIN-HARNESS: PASS (11 arms)
$ node --check app/panel/caption-formulation.js   (sem saida = ok)
$ python _main/undefined-names-oracle.py    UNDEFINED-NAMES GREEN -- 18 ficheiros de producao, 0 nomes usados e nunca definidos
$ python _main/console-window-audit.py      CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela
$ python _main/audio-meter-oracle.py        11 PASS / 0 FAIL (11 arms)
$ python _main/live-queue-oracle.py         LIVE-QUEUE VERDICT PASS -- arms=32 fail=0
```

### 5.1 Ratchet do `code-health-oracle.py`: BASELINE NOTE (o portão está RED e é esperado)

```
RED  app/panel/caption-formulation.js: bytes piorou de 52824 para 55224
RED  app/panel/caption-formulation.js: lines piorou de 1091 para 1167
RED  app/webview/sotto_webview.py: lines piorou de 19192 para 19238
```

Nota exigida pelo bilhete. Contra o HEAD DESTE worktree: `caption-formulation.js`
+113/−37 linhas, `sotto_webview.py` +54/−8. O código cresceu porque o desenho
antigo era curto e errado (quatro geradores) e o novo tem de manter duas
estruturas coerentes (a janela em ordem de chegada e a mesma janela ordenada) e
um caminho de reconstrução para harnesses. O que NÃO cresceu: o custo. Os bytes
do shell até BAIXARAM contra o baseline guardado (−16 844 B); o vermelho é só
a métrica de linhas.

## 6. O que esta lane NÃO provou

1. **A cadência ao vivo** (604 → ~561 ms): `[INFERENCE]`. Só se mediu com o
   `FileTap` real; a instância do dono corre o worker antigo e o worktree não
   tem modelo nem dispositivo. Requer reinício do worker (não é desta lane).
2. **O custo do pump WASAPI ao vivo com `block_ms=40`**: medido o laço de sleep
   (0,31 % → 0,63 % de um núcleo), NÃO medido com o dispositivo aberto; a chamada
   COM `GetNextPacketSize` por iteração não entra nesse número — `[INFERENCE]`
   que seja da ordem de poucos µs/s a 500 iterações/s.
3. **A latência ponta-a-ponta** (p50 195 ms): não se mediu o efeito dos 44 ms de
   cadência no p50 do dono; mediu-se a cadência, que é 94 % dessa conta
   (publish−tap), mas a composição final não foi corrida.
4. **O piso do painel** (§3.3) é medido para os dois componentes separadamente
   (2,2 µs o protocolo, 5,4 µs o contrato de tokens); a soma exacta num único
   laço não foi medida.
