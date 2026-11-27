# Recibo — o passo mais caro da bateria: 12 chamadas a `get_source_segment` re-partiam a shell inteira

Medido 2026-11-26, `H:/sotto`, HEAD `74b2183e6c`, com `_cache/battery-steps.json` da corrida #19
(GREEN, 610 passos, 0 falhas, 1724,99 s).

## 1. O alvo foi escolhido pelo número, não pelo nome

`red-as-expected-nemotron-preload` era o passo com **maior CPU registada** da bateria:
**46,2 s**. (Os passos com maior *parede* são os `panel-*`, 154,9 s e 105-106 s, mas nenhum deles tem
`cpu_s` — nunca voltaram a correr desde que o amostrador de CPU existe, logo a parede deles mede a
jaula, não o passo.)

## 2. `cProfile` nomeou a linha antes de qualquer edição

`python -m cProfile -o I:/cc-tmp/nemo2.prof _main/nemotron-preload-oracle.py`, 11,68 s dentro do
perfilador:

|função|cumtime|nota|
|---|---|---|
|`check_sources`|7,157 s|a extração de segmentos de fonte|
|`ast.get_source_segment` → `_splitlines_no_ff`|**6,750 s em 12 chamadas**|0,56 s por chamada: **re-parte a fonte de 1,5 MB inteira** a cada segmento|
|`builtins.compile`|3,283 s|as 13 `ast.parse`|
|`run_status_controls`|1,924 s||

A convenção da casa já existia: `_main/_astcache.py` (`lines()` guarda a partição por conteúdo,
`segment()` fatia-a com a MESMA `ast._splitlines_no_ff`, logo o texto extraído é byte-idêntico). É a
mesma cura que o `gaming-hotkey-oracle` recebeu em 2026-11-12 (24,9 s em `builtins.compile`).

## 3. A troca: 12 sítios, uma importação

`ast.get_source_segment(` → `_segment(` nos 12 sítios, com `from _astcache import segment as _segment`
depois do `sys.path.insert` do próprio diretório (semântica igual: sem nó devolve `None`, e todos os
sítios já faziam `or ""`).

## 4. O par medido, nas duas direções, caged (`--cpu 40 --io very-low`)

|corrida|parede|CPU do filho|veredicto|
|---|---|---|---|
|positivo, antes|6,9 s|5,39 s|`PASS -- preload activation and hidden panel routing are enforced`|
|positivo, depois|**4,1 s**|**3,00 s**|`PASS` (idêntico)|
|`--neg-arm`, antes|60,8 s|51,44 s|`NEG-ARM: PASS -- 17/17`, rc 1|
|`--neg-arm`, depois|**20,5 s**|**17,28 s**|`NEG-ARM: PASS -- 17/17`, rc 1|

A cura tirou tempo **e não** deteção: 17/17 mutantes continuam apanhados, rc 1 nos dois lados.

## 5. Uma arm que não era pura, apanhada no caminho

A primeira corrida sob `cProfile` devolveu
`VERDICT: FAIL -- ready-before-open status did not clear on activation` — e a projeção
(`caption_status_for`) é pura sobre um dicionário... exceto por dois campos que vinham VIVOS da ponte
(`loaded=bridge.loaded`). `_pump` põe `self.state` (`sotto_webview.py:25963`) **antes** de
`self.loaded` (`:26040`) para a MESMA mensagem `model-loaded`, logo `loaded=False` com
`worker_state='frontend-ready'` responde `model-loading`. Medido: **1 de 3** corridas sob perfilador
vermelha, 2 de 2 simples verdes. É a classe que este ficheiro já tinha substituído uma vez
(`if status_events:`, comentário no sítio). Cura: uma **barragem limitada** (5 s) para o facto do
contrato (`bridge.loaded`) antes de julgar, com falha nomeada se ele nunca chegar — não uma espera
cega. Verificado depois: positivo `PASS`, `--neg-arm` `17/17`.

## 6. O que isto vale na bateria

46,2 s de CPU → 3,0 s no passo positivo; 51,4 s → 17,3 s no braço vermelho. A CPU total registada da
bateria (`total_cpu_s 399,26`) perde a maior parcela de um único passo, e o ratchet por passo lê o
número novo (min das últimas 3 leituras, nunca um aumento).

Ficheiros: `_main/nemotron-preload-oracle.py` (12 sítios + barragem),
`_main/_astcache.py` (reutilizado, não alterado).
