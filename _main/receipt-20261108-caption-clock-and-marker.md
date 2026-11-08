# RECIBO - o relogio do frame, o tecto de 240 Hz e o marcador `>>` (2026-11-08)

Duas ordens do dono, verbatim:

1. *"acho que a animacao da legenda pode ir ate 240hz"*
2. *"o youtube escreve >> em algumas legendas. nao transmita isso pro sotto"*

Cada numero abaixo foi medido nesta arvore, nesta sessao, com o comando ao lado. Onde diz
`UNMEASURED`, nao foi medido e nao se afirma.

---

## 0. O que estava errado no relogio (a causa raiz, e ela nao era o sleep)

**`time.monotonic()` nesta maquina avanca de 15,000 ms em 15,000 ms.**

```
granularidade minima time.monotonic   = 15.000000 ms
granularidade minima time.perf_counter = 0.000300 ms
iteracoes com monotonic congelado: 125542
```

Todo o prazo de quadro do overlay (`_tick_deadline`, `_next_delay`, o custo da pintura) era
aritmetica sobre esse relogio. Consequencia medida com o laco REAL, antes da cura:

| pedido | entregue antes | delta p50 |
|---|---|---|
| 240 Hz (4,167 ms) | **65 quadros/s** | 16,00 ms |
| 60 Hz (16,7 ms) | **40 quadros/s** | 31,00 ms |

Ou seja: o tecto de 60 Hz que a casa tinha tambem estava a ser servido em degraus de 15/31 ms. A
animacao nunca andou no relogio; andou no grao do `GetTickCount64`.

**A CURA:** `caption_overlay._frame_now = time.perf_counter` (QPC, monotonico, 0,0003 ms) usado
SO' no prazo do frame. Os carimbos que viajam para fora do overlay continuam em
`time.monotonic()` -- comparam com o relogio do shell, e misturar escalas num numero seria pior
do que o defeito.

Depois da cura, o mesmo laco, com o mesmo instrumento:

| pedido | entregue depois | delta p50 | p90 |
|---|---|---|---|
| 240 Hz, pintura 0 ms | **218 quadros/s** | 4,59 ms | 4,72 ms |
| 60 Hz | **57 quadros/s** | 17,37 ms | 18,01 ms |

Uma das arms ANTIGAS ja' carrega a diferenca: A1 ("o relogio pinta") contava **64 frames em 1 s**
antes da cura e conta **186** depois.

---

## 1. O tecto de 240 Hz (ordem 1)

* `app/webview/word_fade.py`: `FRAME_S = 1.0 / 240.0` (era 1/60) e `FRAME_HZ = 240`.
* `caption_overlay._arm_tick` -> `_limit_by_paint`: **o pedido nunca e' mais curto do que a
  pintura que ele pede**. Regra: `delay = max(delay, custo_medido * 1.02)`, com uma linha
  `CAPTION_FRAME_LIMIT want_hz=.. paint_ms=.. rate_hz=..` a cada 5 s (nao por quadro).
* `caption_overlay._tick` mede o custo real de `_update()` (`_paint_cost_s`).
* `_tick_loop`: o ultimo trecho do sono e' `time.sleep`, nao `Event.wait`.

**POR QUE O `sleep` E NAO O `Event` -- medido:** `Event.wait(4,167 ms)` devolve com **5,03 ms** de
minimo (tecto de 192 Hz), enquanto `time.sleep(4 ms)` devolve em **4,17-4,2 ms** (239 Hz). O
`Event` continua a ser o que acorda cedo quando o prazo muda; abaixo de 5 ms quem dorme e' o
`sleep`.

**A RESOLUCAO DO RELOGIO DO SISTEMA** (`timeBeginPeriod(1)` / `timeEndPeriod(1)`) e' levantada
enquanto ha' frame armado e devolvida no primeiro instante sem frame (`_timer_period`, idempotente,
fail-open, `CAPTION_FRAME_TIMER period_ms=1/0`). **Nao e' ela que curou o laco** -- medido depois do
relogio certo: `begin(1)` 4,21 ms contra `end(1)` 4,18 ms, dentro do ruido, porque a resolucao desta
maquina ja' estava em 1,00 ms (`NtQueryTimerResolution`) por causa de outro processo. Ela fica para
que um sono de 4 ms nao dependa de QUEM mais corre na maquina: a mesma medicao deu 4,18 ms num
minuto e o laco inteiro 16 ms no seguinte.

**E O CUSTO DA PINTURA, MEDIDO NO TAMANHO REAL** (`_premultiplied_bitmap`, 1040 x 240 px, escala
2.0, tres linhas, `roll=0.5`):

| medida | p50 | p90 | tecto |
|---|---|---|---|
| quadro | **11,6 ms** | 29,4 ms | **86 Hz** |

Logo: **o tecto pedido e' 240 Hz; o custo entrega ~86 Hz.** O gargalo e'
`GraphicsPath.AddString` com contorno, que re-cria o caminho do texto a cada quadro. Um destes
dois numeros sem o outro seria a promessa que o instrumento nao cumpre, e por isso o limite e'
auto-medido e escrito no log. Fonte do custo, por perfil: `overlay_paint.draw_line` 3,2 ms por
linha (144 ms em 45 chamadas), `_make_font` 0,27 ms por construcao -- **duas por quadro**, e agora
sai de um cache (`_FONT_CACHE`, chave = familia+px+peso+italico; o valor guarda a fonte para o
GDI+ nunca entregar uma `FontFamily` cujo `PrivateFontCollection` ja' morreu).

Medido com o limite ligado (pintura declarada 11,6 ms, pedido 240 Hz): **71 quadros/s, p50
12,58 ms**, e o log diz `CAPTION_FRAME_LIMIT want_hz=240 paint_ms=11.60 rate_hz=85`.

### O que NAO foi feito, e por que
A pintura em si nao foi reescrita para 240 Hz. Faze-lo exige guardar o raster do texto (ou o
caminho GDI+) e reaproveita-lo entre quadros, o que muda o desenho que o dono VE -- e a ordem dele
foi um TECTO, nao a promessa de uma taxa. Fica como trabalho medido e nomeado, com o numero que o
justifica (11,6 ms contra um orcamento de 4,17 ms).

---

## 2. O marcador de fala `>>` (ordem 2)

O `>>` chega do player em tres formas -- `&gt;&gt;` no DOM antes de descodificar, `>>` depois, e o
`\u203a\u203a` da faixa automatica -- e em duas posicoes: a abrir a linha e no MEIO dela, quando o
painel junta dois segmentos.

* `app/webview/youtube_window.py`: `_strip_markers` passou a **`strip_speaker_markers`** (dono
  unico da lista `_SPEAKER_MARKERS`) e passou a tirar o marcador tambem **no meio** da linha.
* `app/webview/youtube_cdp_source.py`: os tres campos de texto que alimentam o ecra -- `rows`,
  `items` e `segs` -- passam pelo mesmo normalizador. O caminho que o dono ve' hoje e' o CDP; o
  da UIA ja' o tirava, e era por isso que o simbolo aparecia "em algumas legendas".

**O defeito de instrumento que a primeira versao carregava, e que custou uma medicao:** o modulo
fazia `from youtube_window import ...` dentro de um `try`, e o import so' resolve com o diretorio
da app no `sys.path` -- quando nao resolvia, caia num *fallback* local que so' tirava o marcador
do INICIO, e o `>>` do meio da linha chegava ao ecra. O oraculo carrega o ficheiro por `spec`, que
e' exatamente o caso que nao poe nada no `sys.path`: a arm deu `FAIL` com
`rows=['Nossa.', 'da wave. >> Nossa.', 'ok']`. Curado sendo **carregado pelo caminho**
(`_load_sibling`, `importlib.spec_from_file_location` ao lado do ficheiro), sem fallback duplicado.

### Portao
`_main/youtube-cdp-source-oracle.py`, arm **`sem-marcador-de-fala`**: um payload com as tres formas
e as duas posicoes tem de sair limpo em `rows`, `items` **e** `segs`.

```
sem-marcador-de-fala   PASS  rows=['Nossa.', 'da wave. Nossa.', 'ok'] segs=['Nossa.', 'da wave.', 'Nossa.']
VERDICT: PASS (19/19)
NEG-ARM VERDICT: PASS (15/15)          # 5 mutacoes... ver abaixo
```

Duas correccoes de instrumento no mesmo ficheiro, ambas medidas:

* `linhas-sem-filtro` ficou `NOT-CAUGHT` quando a linha passou a chamar o normalizador -- a ancora
  antiga deixou de existir no fonte e o mutante passou a ser identico ao original. Re-anchorada.
* O mutante vive numa pasta temporaria, e o modulo agora carrega o irmao pelo caminho: o oraculo
  **copia `youtube_window.py` para o lado do mutante**, senao o mutante nao importa e nada e'
  provado (`FileNotFoundError` medido).

---

## 3. Portoes (todos corridos nesta sessao, depois da ultima edicao)

| portao | veredicto |
|---|---|
| `_main/caption-tick-thread-oracle.py` | `VERDICT: PASS (9/9)` |
| `_main/caption-tick-thread-oracle.py --neg-arm` | `NEG-ARM VERDICT: PASS (5/5)` |
| `_main/youtube-cdp-source-oracle.py` | `VERDICT: PASS (19/19)` |
| `_main/youtube-cdp-source-oracle.py --neg-arm` | `NEG-ARM VERDICT: PASS (15/15)` |
| `_main/caption-rollup-oracle.py` | `VERDICT: PASS (8/8)` |
| `_main/paint-row-seam-oracle.py` | `VERDICT: PASS` |
| `_main/caption-switch-race-oracle.py` | `GREEN -- arms=13 pass=13` |
| `_main/youtube-word-clock-oracle.py` | `GREEN -- arms=23 pass=23` |
| `_main/caption-producer-oracle.py` | `VERDICT: PASS (8/8 arms)` |
| `_main/caption-style-oracle.py` | `VERDICT: PASS (8/8 arms)` |

As arms novas do `caption-tick-thread` (a bateria ja' corre este passo):

| arm | o que ela guarda |
|---|---|
| A6 | o tecto de frame e' 1/240 (`word_fade.FRAME_S` e `FRAME_HZ` lidos do ficheiro que embarca) |
| A7 | um custo de 11,6 ms levanta o pedido a 11,83 ms e LOGA `CAPTION_FRAME_LIMIT`; sem custo o pedido passa intacto |
| A8 | o ultimo trecho do sono e' `time.sleep` (o `Event` so' para `timeout >= 1 s`) |
| A9 | o relogio do frame tem grao < 1 ms (200 leituras: `monotonic` da' 15 ms, `perf_counter` < 0,001 ms) |

Mutacoes do `--neg-arm` (cada uma derruba a SUA arm): Timer por frame de volta, tecto de volta a
60 Hz, limite por custo arrancado, relogio de grao grosso.

---

## 4. O QUE NAO ESTA' VERIFICADO

* **A INSTANCIA VIVA DO DONO E' ANTERIOR A ESTE CODIGO.** Medido com
  `python _main/live-code-freshness-oracle.py --strict`:
  `pid=42572 started=2026-11-08 04:01:44.463`, `disco: sha256=3DADD5835C5F files=100`,
  `>>> O DONO CARREGA OUTRO CODIGO`. Nada aqui esta' na app dele: **reabrir antes de julgar
  qualquer sintoma**.
* Nada disto foi visto na TELA dele: a prova e' o laco real conduzido em processo proprio, o
  bitmap medido por fora de uma janela e os oraculos. `verified` continua a exigir a corrida real
  da app.
* A taxa de 240 Hz **nao e' entregue com a pintura de hoje** (86 Hz medidos). O que esta' entregue
  e' o tecto, o limite auto-medido com a linha de log, e um relogio de frame que ja' nao mente.
