# RECIBO -- o custo da pintura da legenda (cache do RASTER, nao do quadro)

Lane: `PaintCostNuclear`. Data: 2026-11-08. Arvore: `H:\sotto`.

Ordem: o watcher nomeou a pintura da legenda como o maior consumidor de CPU
nomeado da shell, medido na instancia viva do dono (`pythonw.exe` 42572):
`cpu=33.5%` de um nucleo, `THREAD_CPU top=sotto-caption-paint:10%`, e uma pintura
de 2 linhas a **11,6 ms de p95 / 6,7 de p50** (caixa real de 1040x240 a escala 2.0).

O DEFEITO NAO ERA O GDI+ SER LENTO. Era ele ser chamado quando nada mudou de
glifo: `_premultiplied_bitmap` reconstruia o caminho do texto
(`GraphicsPath.AddString` + `DrawPath` + `FillPath`, por linha) em TODOS os
quadros, e entre dois quadros de uma legenda parada o unico numero que muda e' o
alfa do `UpdateLayeredWindow` (255 -- o fade foi tirado). A cura guarda o RASTER
COMPOSTO e chaveia-o por tudo o que move um pixel dele.

## ANTES (paste verbatim, caminho ANTERIOR = `git show HEAD:app/webview/overlay_paint.py`)

```
caixa 758x227, 2 linhas + anterior
HEAD       p50=7.362 p95=10.662 max=17.102  (n=100)
miss       p50=6.846 p95=9.005 max=9.684  (n=30, cache limpo antes de cada)
hit        p50=0.077 p95=0.181 max=0.696  (n=100)
```

A implementacao ANTERIOR e a nova correm no MESMO processo, intercaladas
(`HEAD` em 100 iteracoes, depois as 100 do hit), para partilharem a carga da
maquina -- ha' outras lanes a correr nesta arvore. A caixa e' a do tema de painel
(placa + regua + LED) a escala 2.0, 2 linhas vivas + a linha anterior.

## DEPOIS

| braco | p50 (ms) | p95 (ms) | max (ms) | n |
|---|---|---|---|---|
| HEAD (antes) | 7,362 | 10,662 | 17,102 | 100 |
| miss (codigo de sempre + guardar a copia) | 6,846 | 9,005 | 9,684 | 30 |
| **hit (cache)** | **0,077** | **0,181** | 0,696 | 100 |
| hit, medido pelo oraculo (A2) | 0,069 | 0,094 | 1,099 | 200 |

Portao de A2: hit p95 <= **2,0 ms** -> medido **0,094 ms** (21x abaixo do tecto).
O miss nao e' portao (e' o codigo de sempre) e nao regrediu.

## A IGUALDADE DE PIXEL (A1) -- 4152 comparacoes, 0 diferencas

48 bases x (12 com varredura **cheia 0..255** de alfa + 36 com passo 15 +
9 vetores de alfa MISTURADOS por base). Cada comparacao e' o bitmap inteiro:
`stride x altura` bytes de `Format32bppPArgb`, sha256 e comprimento.

Bases: 3 temas (`youtube` sem placa / painel com placa+regua+LED / o MESMO painel
sem placa) x 2 escalas (1.0, 2.0) x 8 formas (1 linha; 2 linhas; 2 linhas com
`roll=0.45`; linha anterior; linha anterior vazia; linha longa que quebra; caixa
estreita com o texto na borda direita; 3 linhas com `roll=0.30`).

```
A1 PASS -- 4152 comparacoes byte a byte contra HEAD
```

## A CHAVE DO CACHE

Chave = `(linhas vivas como tuplo, linha anterior, largura, altura, _freeze(geo),
roll)`. `geo` e' o dict INTEIRO de `_geom` congelado (dict -> tuplo de pares
ordenados), e carrega, sem enumeracao manual:

familia (`fontFamily`), `livePx`/`prevPx` e os derivados `cur_px`/`prev_px`,
`liveWeight`/`prevWeight`, `liveItalic`/`prevItalic`, `liveUpper`/`prevUpper`,
`liveColor`/`prevColor`/`strokeColor`/`strokePx`, `plate` + `plateRadius`,
`ruleW`/`ruleColor`, `led`/`ledW`/`ledH`, `gap`, `pad` e os derivados `pad_t/r/b/l`,
`leading`/`prevLeading` -> `line_h`/`prev_h`, `x_text`, `align`, `scale` via
`cur_px`/`pad_*`.

Congelar o dict inteiro e' de proposito: enumerar os campos e' como o proximo
token do painel entra em cache com o raster do tema anterior.

**O ALFA DE ANIMACAO NAO ESTA' NA CHAVE, E NAO PODE SER APLICADO DEPOIS.**
A tentacao era multiplicar o raster cacheado pelo alfa do quadro. Isso NAO e' o
mesmo pixel: o GDI+ compoe o CONTORNO e o PREENCHIMENTO dois sobre o fundo
(`out = F*k + (S*k + B(1-k*A_s))(1-k*A_f)`), e a multiplicacao de um raster ja'
composto da' `C*k + B*k(1-A)`; onde os dois se sobrepoem diferem por `k(1-k)`.
Logo um alfa parcial NAO usa o cache (cai no caminho de pintura de sempre, byte
por byte o de antes) e o contador `bypass` mostra-o. Custo zero na app: todos os
chamadores passam 255 -- `_row_alphas` e' `[255] * n` nos tres sitios de
`caption_overlay.py` desde que o dono mandou tirar o fade, e `None` no resto.
O oraculo mede as duas coisas: o alfa parcial a 0/128/255 e os vetores misturados.

## LIMITE E OBSERVABILIDADE

LRU de **8** entradas (`_PAINT_CACHE_MAX`), com contadores
`hits/misses/evictions/bypass/entries/max` expostos por `_paint_cache_stats()` e
impressos pelo oraculo. Medido: 10 chaves distintas -> `entries=8 evictions=2`;
pedido repetido -> `hits` sobe e o raster e' identico ao de um miss limpo.

Memoria: <= 8 rasters de 32 bpp. Nesta caixa (758x227) = 688 kB cada, **<= 5,5 MB**;
na caixa real do dono (1040x240) ~1,0 MB cada, **<= 8 MB**.

## SITIOS (file:line, medidos agora)

- `app/webview/overlay_paint.py:676` `_PAINT_CACHE = OrderedDict()`; `:677` `_PAINT_CACHE_MAX = 8`
- `:681` `_freeze` -- tema -> hashable, sem enumerar campos
- `:697` `_paint_key` -- a identidade do raster (ou `None` quando nao pode usar cache)
- `:715` `_paint_cache_get` -- hit devolve uma **copia** (`Clone`) e conta
- `:729` `_paint_cache_put` -- guarda uma **copia**; fecha a entrada substituida
- `:758` `_paint_cache_clear`; `:768` `_paint_cache_stats`
- `:776` `_premultiplied_bitmap` -- MESMA assinatura e mesmos posicionais; agora: geom, chave, hit/miss, put
- `:804` `_paint_bitmap` -- o corpo de pintura de SEMPRE, movido, intacto
- `app/webview/caption_overlay.py:1127` -- o chamador; **nao foi tocado**

O `except_pass` do ficheiro NAO cresceu (2 -> 2): o fecho de bitmaps usa
`contextlib.suppress`, nao `except: pass`.

## NEG-ARM (A4) -- dois mutantes em COPIA, rc=1, `NEG-ARM: PASS`

```
paint-cost: 48 bases, 12 com varredura cheia 0..255
NEG: 6 bases reduzidas, alfas 0/128/255
  MUTANTE lookup-off: pixel_red=0 hit_ms p50=34.45 p95=107.20 (portao 2.0)
  MUTANTE roll-off-key: pixel_red=2 (t0/s1.0/roll45 k=255, t1/s2.0/roll45 k=255) hit_p95=2.21 ms
NEG-ARM: PASS
```

- **lookup-off**: o cache e' construido e nunca servido. Os pixels continuam
  certos (`pixel_red=0`) e o CUSTO cai para o vermelho -- e' o mutante que prova
  que a arm de custo mede o cache e nao o GDI+.
- **roll-off-key**: `float(roll)` sai da chave. O custo continua verde e a
  IGUALDADE cai nas duas bases com `roll=0.45` a alfa 255 (as unicas em que o
  cache e' servido) -- e' o mutante que prova que a chave carrega a geometria.

Nota honesta sobre o `34,45 ms` do primeiro mutante: nesse braco cada quadro
pinta E repoe a MESMA chave no cache. Fora do oraculo o mesmo caminho mede
~5,9 ms; os 34-107 ms vieram da contencao das outras lanes a correr nesta arvore
(a variacao entre corridas foi 34-95 ms). O portao e' `> 2,0 ms` e esta' 17x
acima do ruido, por isso nao decide nada por margem.

## A3 -- DELTA DE CPU [INFERENCE]

Nao ha' corrida da app: o `pid 42572` do dono corre o codigo ANTERIOR e segura o
mutex de instancia unica -- matar essa instancia para medir a nova seria fechar a
legenda dele. A aritmetica, do oraculo:

```
A3 [INFERENCE] orcamento 40%: antes 7.19 ms -> 56 Hz; depois 0.07 ms -> 5789 Hz
(tecto do relogio 240 Hz); guardado por pintura: 7.12 ms; 104.11x menos; mesmas
13.9 pinturas/s (o que 10% de um nucleo pagava): 10.0% -> 0.10% de um nucleo
```

O ORCAMENTO e' o que limita o nucleo; o CACHE e' o que compra TAXA.
`CAPTION_FRAME_BUDGET = 0.40` (`caption_overlay.py:81`, outra lane) poe o periodo
a `custo / 0.40`: com a pintura de 0,07 ms o tecto de CPU continua 40% **por
construcao** e o que cresce e' a taxa. A 240 Hz sao precisos <= 1,67 ms de
pintura por quadro; 0,07 ms deixa 24x de folga (antes: 11,6 ms x 240 = 2,8
nucleos, impossivel, e por isso o laco pintava a ~34 Hz).

## WIRING -- entregue ao dono da integracao (NAO editado por mim)

Por ordem do `Main`, `_main\_audit-verify-all.cmd` e o pin do `AGENTS.md` tem um
so' dono. As duas linhas, no formato do ficheiro:

```
call :step paint-cost 0 "_main\paint-cost-oracle.py;app\webview\overlay_paint.py;app\webview\caption_overlay.py" "%OUT%\paint-cost.log" python _main\paint-cost-oracle.py
call :record paint-cost !STEP_RC!
call :step red-as-expected-paint-cost 1 "_main\paint-cost-oracle.py;app\webview\overlay_paint.py;app\webview\caption_overlay.py" "%OUT%\paint-cost-neg.log" python _main\paint-cost-oracle.py --neg-arm
call :expectred red-as-expected-paint-cost !STEP_RC! "%OUT%\paint-cost-neg.log" "NEG-ARM: PASS"
```

Ponto de insercao: imediatamente a seguir ao par `caption-rollup`
(`call :record caption-rollup !STEP_RC!` / `call :expectred
red-as-expected-caption-rollup ...`), antes do bloco `if exist
_main\caption-tick-thread-oracle.py`.

Custo do passo: **90 s** medidos (o `SOTTO_STEP_DEADLINE_S` da bateria e' 240 s).
Tamanho do oraculo: **23352 B**, 522 linhas, LF (o `overlay_paint.py` tambem e' LF).

## code-health

`overlay_paint.py` cresceu (37862 B/824 linhas/19 defs -> 44098/970/26) e a
absorcao foi declarada no baseline, nunca afrouxada: `except_pass` ficou em 2 e
`max_func` DESCEU de 152 para 148 (`_normalise_theme`). O baseline tambem absorveu
o crescimento ja' aterrado de `caption_overlay.py` (75883 B/1569 -> 77800/1603),
que e' da lane do `Main` -- ela re-mede no fim. `CODE-HEALTH VERDICT PASS`.

## NAO MEDIDO

- **Nao ha' prova na instancia viva.** O `pid 42572` corre o codigo ANTERIOR e
  segura o mutex de instancia unica; abrir a app mostraria uma janela na tela do
  dono e matar a instancia dele nao e' permitido.
- **O CPU real da thread depois da cura** (`sotto-caption-paint` no
  `THREAD_CPU`) nao foi lido: seria preciso a app nova a correr.
- **O `LockBits` + `memmove` do chamador** (`caption_overlay._update`, ~0,2-0,4 ms
  por quadro nesta caixa) nao entra no numero da pintura e nao foi medido aqui.
- **O caminho do arrasto** (`_paint_drag_outline`, que escreve no bitmap
  devolvido): o cache devolve uma COPIA, logo a marca nao pode envenenar o cache,
  mas a marca em si nao foi medida nesta corrida.
- **Dois monitores / mudanca de escala a meio**: `scale` esta' na chave e o oraculo
  cobre 1.0 e 2.0, mas nao uma troca de monitor ao vivo.
- **O tecto de CPU do `watcher`** (`python -m watcher run --cpu 40 -- ...`) nao pode
  ser aplicado: `ModuleNotFoundError: No module named watcher` nesta maquina. As
  medicoes correram sem tecto, num so' processo, com outras lanes activas -- o que
  explica a variacao de 5,3 a 15,3 ms nas leituras do HEAD entre corridas.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: PaintCostNuclear
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PaintCostNuclear']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PaintCostNuclear']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-08T07:58:11.203280+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PaintCostNuclear']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PaintCostNuclear']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** -- o protocolo de "um invariante, um dono" que devia ter
  aplicado ANTES de escrever a arm A7: escrevi-a e o `Main` teve de a mandar tirar
  por ja' ter dono (`caption-tick-thread-oracle.py`, arm A7). Da proxima vez,
  procurar quem ja' mede o invariante antes de o medir outra vez.
- **verificacao adicional** -- uma corrida da app nova com o `THREAD_CPU` e o
  `SHELL-THREAD-BUDGET` a ler `sotto-caption-paint` DEPOIS da cura. Custa: abrir a
  app na tela do dono (proibido por esta ordem) ou esperar que ele reinicie por sua
  vontade; fica como a unica prova que falta.
- **checkboxes novas** -- `python _main\paint-cost-oracle.py` tem de devolver
  `PAINT-COST PASS` E `--neg-arm` tem de devolver rc=1 com `NEG-ARM: PASS`; nenhum
  dos dois sozinho prova nada (o verde sem o vermelho nao sabe se mede).
- **review por outro subagente** -- sim-com-escopo: revisao do `_paint_key`
  (e' a chave que decide a igualdade de pixel) e da decomposicao do alfa.
- **gate-doubt**:
  - `verde-de-verdade:` o A1 compara o bitmap NOVO contra o modulo carregado de
    `git show HEAD:...` -- nao contra uma copia a mao nem contra um hash guardado,
    logo nao pode passar por construcao. Provado que nao e' vacuo pelo mutante
    `roll-off-key`: os MESMOS 4152 bytes de comparacao SO' caem quando a chave
    perde um campo (2 bases a 255), i.e. a comparacao tem poder de detectar.
    A corrida A2 mede 200 hits DEPOIS de um miss e exige `hits >= 200` nos
    contadores -- se o cache nao servisse, a arm de custo mediria o miss (7 ms).
  - `falta-no-gate:` o A1 prova igualdade contra o HEAD de HOJE. Se o HEAD de
    amanha mudar a pintura e esta lane nao for re-corrida, o oraculo passa a
    comparar contra um passado que ja' ninguem quer -- e um cache que devolva
    rasters de duas versoes diferentes do desenho continuaria verde. O gate tambem
    NAO cobre o caminho do arrasto (`_paint_drag_outline` escreve no bitmap
    devolvido): se um dia o hit devolvesse o bitmap do cache em vez de uma copia,
    a marca ficaria gravada para sempre e nenhum braco disto cai.
  - `gate-melhor:` um braco que, depois de um hit, chame `_paint_drag_outline` no
    bitmap devolvido e exija que o hit SEGUINTE da mesma chave continue igual ao
    miss limpo (o "envenenamento do cache"). Mecanico: `_render` -> desenhar no
    bitmap -> `_render` de novo -> comparar com `_render` de um modulo limpo;
    entra em RED se o segundo raster diferir.
- **confianca** -- alta na igualdade de pixel (4152 comparacoes + 2 mutantes a
  cair) e no custo do hit (0,094 ms de p95 contra um tecto de 2,0); media no delta
  de CPU, que e' aritmetica e nao uma medicao da app.
- **nao verificado** -- CPU real da thread depois da cura; o `LockBits`/`memmove`
  do chamador; o caminho do arrasto; troca de monitor a vivo; o tecto de 40% do
  `watcher` (modulo ausente).

status: done
