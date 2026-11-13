# RECIBO — o braço negativo deixou de pagar o trabalho inteiro por mutante (2026-11-12)

Tudo o que segue foi medido nesta árvore, nesta sessão. Onde um número aparece, o comando ou o
instrumento que o produziu está ao lado. O defeito é o D-06 de `docs/spec/10-DEFECTS.md`.

## 1. O que estava errado, e como foi achado

A cauda da bateria já estava nomeada por número (D-06). O que faltava era a CAUSA, e a pergunta que a
acha é uma conta: um `--neg-arm` corre `N` mutantes, logo o custo legítimo é `N ×` **o braço que
aquele mutante derruba** — nunca `N ×` a bateria inteira.

```
        positivo   negativo   negativo/positivo
panel-themes            34.8 s     92.2 s     2,6x
panel-header-oracle      8.5 s     59.8 s     7,0x
gaming-hotkey            2.8 s     53.1 s    19,0x
youtube-cdp-source       6.2 s    110.2 s    17,8x
warm-engine             10.0 s     71.3 s     7,1x
```

`cProfile` sobre cada um nomeou o custo, e nos quatro primeiros não era o trabalho do braço.

## 2. As quatro curas, cada uma com o número ANTES e DEPOIS

| # | passo | defeito medido | cura | efeito |
|---|---|---|---|---|
| 1 | `red-as-expected-panel-themes` | `fs.cpSync` de `app/panel` (2 882 ficheiros / 35 MB) = **2 837 ms**, uma vez por mutante × 13 = **~37 s** de cópia pura | uma cópia base + restauro por BYTES dos 4 ficheiros mutados | **92,2 → 56,8 s** sozinho, **43,3 s** na corrida |
| 2 | `red-as-expected-panel-header-oracle` | 9 mutantes × 2 837 ms, mais uma cópia inteira no braço de CONTROLO | o mesmo restauro; o controlo mede a cópia que o `restore()` já repôs | **59,8 → 44,4 s** sozinho, **31,1 s** na corrida |
| 3 | `red-as-expected-gaming-hotkey` | `(a+)+$` com 26 `a` custa **3 773,5 ms** por chamada (2,3 ms com 16, 480,6 com 23): 8× o prazo de 0,45 s, × 5 mutantes | `HOLD_BACKTRACK_A = 20` = **36–46 ms** por chamada, 10–13× abaixo do prazo | **53,1 → 34,8 s** sozinho, **34,7 s** na corrida |
| 4 | `red-as-expected-youtube-cdp-source` | a cache de AST por CONTEÚDO entrou nesta árvore, mas o passo em `_cache/battery-steps.json` carregava o valor velho | rebase do ledger (nenhum código novo) | **110,2 → 12,9 s** sozinho, **12,1 s** na corrida |

Os quatro positivos da mesma corrida, para a razão ser legível: `panel-themes` 40,5 s (paga os 59
desenhos), `panel-header-oracle` 2,3 s, `gaming-hotkey` 3,9 s, `youtube-cdp-source` 5,7 s.

As três curas de código são do INSTRUMENTO, não do produto: nenhuma linha de `app/` ou `worker/` mudou.

**O restauro tem de se provar.** Três mutantes do `panel-themes` tocam o MESMO ficheiro
(`panel-unified.css`); um restauro que falhasse deixaria o mutante seguinte a medir o anterior e as
arms cairiam pelo mutante errado. O `restore()` relê os bytes depois de escrever e **levanta** se não
bater. O controlo do `panel-header` passou a usar o mesmo `restore()` e a função `copyDir` (a única
chamadora que restava) foi apagada.

## 3. O que os veredictos dizem (a cura não pode afrouxar o braço)

```
panel-themes            NEG-ARM: PASS -- 13/13 mutants caught
panel-header-oracle     NEG-ARM VERDICT PASS -- 9 mutant(s), 0 wrong
gaming-hotkey           NEG-ARM PASS -- RED as designed: as cinco regressoes derrubam o oraculo
youtube-cdp-source      NEG-ARM VERDICT: PASS (17/17)
```

## 4. O defeito de PORTÃO que a corrida revelou (e a sua cura)

`spec-coverage-oracle.py` contou **cinco** ficheiros `app/webview/_inputpath-neg-*.py` como produto e
publicou `ausentes=5 VERDICT: FAIL`. Não são produto: `input-path-oracle.py:477` escreve-os dentro da
árvore durante a corrida e `:487` apaga-os no fim (`MUTANT_PREFIX = "_inputpath-neg-"`,
`input-path-oracle.py:73`). A população daquele portão é lida do DISCO, por isso uma corrida
concorrente mudava a resposta.

Cura: `EPHEMERAL_PREFIXES = ("_inputpath-neg-",)` com a razão escrita ao lado. Provado nos dois
sentidos — com uma cópia plantada à mão (`app/webview/_inputpath-neg-race-probe.py`) o portão
continua `PASS`, e sem ela também; o `--neg-arm` continua a apanhar os dois mutantes e sai **rc=1**.

## 5. O número da bateria, medido numa corrida INTEIRA

O modo rápido não serve para isto: ele SALTA os passos mais lentos da corrida anterior, que são
exactamente os curados, e o número novo nunca apareceria. Corrida inteira, `rc=0`:

```
BATTERY-VERDICT: GREEN WITH 24 SKIPPED - 24 step(s) did NOT verify this run   (17 sao HEAVY)
failed   : -none-
```

E o portão do relógio, antes e depois:

```
antes:   RATCHET-OK -- steps=413 total=2293.3s   (baseline 2731.1s)
depois:  RATCHET-OK -- steps=452 total=1876.8s TARGET NOT MET (gap 1816.8s de 60s)
soma crua da cache: cap40 n=452 total=2363.2s
```

**−854,3 s, −31 %** contra o baseline anterior. A fatia dos `red-as-expected-*` caiu de **60,6 %**
para **53,5 %** do custo (198 passos, 1 263,3 s de 2 363,2 s).

O baseline foi rebasado no mesmo comando (`--rebase-policy` com a razão escrita), porque um ratchet
preso à régua de 2 731,1 s deixaria passar **45 %** de regressão antes de voltar a falar. Dois passos
"engordaram" na corrida e tiveram de ser nomeados em `--accept-growth`:
`caption-overlay-theme` 62,5 s e `stepcache-oracle` 67,4 s medem **5,2 s** e **12,0 s** em janela
calma — era contenda dos meus próprios probes em paralelo, e um rebaseline que absorvesse um aumento
em silêncio seria o ratchet a assinar o próprio aumento.

## 6. As DUAS curas que a mesma classe pedia e que faltavam (medidas nesta sessão)

O §2 curou quatro. Aplicada a MESMA conta aos vizinhos, `cProfile` nomeou mais três, e os três eram a
mesma causa — **`ast.parse`/`ast.get_source_segment` a custar com o TAMANHO do ficheiro em vez de com
o trabalho do braço**:

| # | passo | defeito medido | cura | efeito |
|---|---|---|---|---|
| 5 | `red-as-expected-altc-gesture` | `ast.get_source_segment` re-parte o shell inteiro em cada chamada: **27,8 s de `_splitlines_no_ff`** e **25,6 s de `compile`** num braço de 63 s | árvore e linhas por CONTEÚDO | **56,6 s → 8,5 s** sozinho |
| 6 | `red-as-expected-window-drag` | idem: **37,6 s de `_splitlines_no_ff`** dos 90 s, em 51 chamadas | idem | **55,5 s → 9,9 s** sozinho |
| 7 | `red-as-expected-gaming-hotkey` | **24,9 s em `builtins.compile`** e **95 `ast.parse`** num `--neg-arm` de 57 s | idem | **51,6 s → 30,5 s** sozinho |

Os três braços somavam **163,7 s** e passam a somar **48,9 s**.

**E aqui a cura foi ela própria um defeito, apanhado antes do commit.** A primeira versão escreveu a
mesma cache **cinco vezes**, uma por oráculo, com nomes diferentes (`_PARSE_CACHE`, `_SHELL_AST_CACHE`,
`_SEG_LINES`...). Três já existiam na árvore (`audio-back-detector` desde 2026-11-11 e
`youtube-cdp-source` desde esta manhã, `live-ack` ontem, todas com a mesma medição escrita no
comentário) e esta linha acrescentou três. Cinco cópias de uma convenção é
a classe que esta casa já pagou quatro vezes. Há agora **um** módulo — `_main/_astcache.py`
(`tree(source)`, `lines(source)`, `segment(source, node, missing)`) — e os **seis** oráculos importam
dele (`altc-gesture`, `audio-back-detector`, `gaming-hotkey`, `live-ack`, `window-drag`,
`youtube-cdp-source`).

**O equivalente foi PROVADO, não assumido.** A `segment()` reimplementa a fatia que o CPython faz em
`ast.get_source_segment`, e uma partição de linhas diferente deslocaria o segmento e o braço julgaria
o texto do lado. Medido contra o próprio CPython: **751 nós** em quatro ficheiros de `app/` e **150
nós sorteados** do shell de 26 774 linhas → **0 divergências**; o shell não tem `\f` (`ESC_FORMS
False`), o único carácter em que as duas partições diferem.

## 7. Dois defeitos de PORTÃO que a rodada revelou (e as suas curas)

1. **`meter-chain-oracle --neg-arm` era um controlo que não podia falhar.** Ele imprimia
   **`64 PASS / 2 FAIL`** e **`VERDICT: PASS`** na mesma corrida: o `rc` era calculado ANTES dos
   quatro checks do braço negativo e o `tail_summary(rc)` recebia esse valor velho. Agora
   `tail_summary(None)` recalcula de `RESULTS`.
2. **Os mutantes filhos morriam pelo motivo ERRADO.** As cópias vivem num tempdir, e o
   `worker/sotto_worker.py` põe o **seu próprio** diretório no `sys.path` — a cópia punha o tempdir,
   logo o `import punctuation_model` da linha 133 levantava `ModuleNotFoundError` e o filho saía
   `rc=1` por um import falhado, nunca pelo medidor. Um `rc≠0` que vem do import é indistinguível de
   um que vem do defeito. `load_module` passa a pôr `worker/` no `sys.path` antes de carregar.
   (Sem a cura do (1) isto teria continuado invisível: o braço dizia PASS.)
3. **O `meter-chain` tinha ainda uma arm de contagem fixa.** `len(pre_existing) == 3` com a frase "as
   três ramificações de pico" — o `on_block` vivo tem SEIS `if` de topo (`_AUDIO_RING`, os três de
   pico, `evicted`, `dropped`) mais o do medidor, logo a contagem passou a acusar três acréscimos
   LEGÍTIMOS do produto. Um braço de não-regressão que conta irmãos mede o crescimento do ficheiro.
   Agora ele exige as três condições de PICO **pelo nome** (`counters["peak"]`,
   `device_peak["value"]`, `1e-4`) e exactamente UM ramo do medidor.
4. **O `meter-chain` morria antes do primeiro check** (`NameError: name 'block_ms' is not defined`):
   `block_ms` é um LOCAL de `main()` e o `on_block` real o lê em
   `_live_queue.max_blocks(block_ms)`; o arnês do braço 4 injectava tudo menos esse. O valor passou a
   ser lido do FONTE (`audio.block_ms` default pelo literal do `main()`), nunca escrito à mão.
   Estado: `meter-chain-oracle: 55 PASS / 0 FAIL`, `VERDICT: PASS`.

## 8. O que NÃO se corta, e por quê

`red-as-expected-warm-engine` (73,4 s / 6 mutantes = 1,2× o positivo) paga um SUBPROCESSO real por
mutante — é o isolamento que o braço compra, e um cache partilhado entre mutantes mediria o mutante
anterior. `caption-overlay-theme` (62,5 s) e `headphone-cut` (60,7 s) renderizam os 59 desenhos e
leem um dispositivo de áudio. `load-shedding` (39,8 s) re-corre a população de 257 arms uma vez por
coorte de mutantes: é a unidade de cobertura dele, e um cache por (arm, mutação) deixaria de provar
que o mutante derruba **a** arm que o nomeia. Cortá-los exige cortar a POPULAÇÃO do braço, que é uma
decisão de cobertura e não de relógio.

**`altc-gesture` e `window-drag` saíram desta lista** porque a razão escrita aqui estava ERRADA: eles
não pagavam subprocesso nenhum, pagavam `ast.get_source_segment` a re-partir o shell por chamada
(§6). Um "não se corta" que nunca foi medido é a mesma classe do pin que ninguém re-mede.

## 9. O QUE NÃO ESTÁ VERIFICADO

* Nada disto foi visto na tela do dono. A prova é de oráculo, de cache de bateria e de uma corrida
  completa; `verified` continua a exigir uma corrida real da app pela mão dele.
* Os 24 passos SKIPPED da corrida não são gates que passaram, e 17 deles são a classe HEAVY (abrem o
  ecrã dele, o dispositivo de áudio ou a GPU) que não corre sem `SOTTO_BATTERY_HEAVY=1`.

## 10. O `window-drag` ficou RED na corrida — três defeitos do BRAÇO, nenhum do código

O passo ficou RED em **duas** corridas seguidas desta linha, com duas causas DIFERENTES, e nenhuma
delas no produto. As duas medições, coladas como saíram:

```
  RED   A6 taxa-entregue  hz=184.7 upgrades=24 gaps_p95_ms=10.49 gaps_max_ms=12.14 n=23 elapsed_ms=130 floor=200
  RED   A6 taxa-entregue  hz=183.3 upgrades=56 gaps_p95_ms=13.76 gaps_max_ms=31.55 n=55 elapsed_ms=304 floor=200
```

### 10.1 O relógio do gesto começava antes do fio existir

`n=23`, `elapsed_ms=130` para uma janela que devia ser de 300 ms: o gesto foi **truncado**. O ponteiro
falso fixava `t0` na CONSTRUÇÃO, e `begin()` espera até 100 ms pelo fio da pega anterior — quando o
primeiro `GetAsyncKeyState` chegava, a janela de 300 ms já ia gasta e a arm media o custo de abrir o
fio, não a taxa do laço. Curado em dois sítios: o relógio começa no **primeiro** `GetAsyncKeyState`
(`self.t0 is None`) e a taxa passou a ser `(n-1) / (último - primeiro carimbo)`, não
`updates / vida_do_fio` — o `finally` que escreve o `WINDOW_DRAG_PERSIST` também entrava no
denominador.

### 10.2 A taxa absoluta mede a contenda da máquina

Com o gesto inteiro, a MESMA árvore deu **239,9 / 239,7 / 240,1 Hz** fora da corrida e **183,3 / 184,7**
dentro dela, com **61,1 %** de CPU da máquina a ser de outras lanes. Um piso de 200 Hz sobre um laço de
240 Hz é um piso com **17 %** de margem, e ele reprovou o código correto duas vezes.

### 10.3 A cauda (max, depois p95) também oscila, e é o Windows

Cinco leituras de 3 gestos somados, mesma árvore, na mesma janela:

| p50 | p95 | max | hz | runs_hz |
|---|---|---|---|---|
| 4,12–4,14 ms | 5,05–**10,50** ms | 6,83–**25,11** ms | 229,4–240,0 | 202,3–240,2 |

O intervalo típico **não se move** (4,12–4,14 ms = 240 Hz) enquanto o p95 varia 2x e o máximo 3,7x. Duas
estimativas intermediárias foram medidas e RECUSADAS antes da final: a fatia de intervalos acima de
8 ms deu `19/62 = 30,6 %` num gesto e `0/72` no seguinte (a corrida caged rouba ~80 ms de uma vez), e
agregar três gestos ainda deu `23,7 %` numa leitura contra `0,0 %` em outra.

**A cura:** o braço julga o **p50 do intervalo** (`P50_GAP_MS = 8.0`) somando três gestos de 300 ms.
A distância entre o laço curado e a regressão é 4x (4,17 ms contra 16,7 ms), e 8,0 fica no meio com
1,9x de margem para cada lado. A taxa fica só como rede de sanidade (`RATE_SANITY_HZ = 100`). O que a
mediana não vê — um gesto inteiro congelado — é medido pelo `n >= 60` e pela arm A12.

Medido: **cinco execuções seguidas PASS (12/12)** e o controle com o mutante de 60 Hz:

```
NEG-ARM: PASS -- A5 rc=1 (caught) / A10 rc=1 (caught) / A6-60hz rc=1 (caught)
A6 taxa-entregue  p50_gap_ms=4.12 p95_ms=4.59 max_ms=4.72 hz=240.1 runs_hz=[240.1, 240.1, 240.2] n=215
```

O mutante `WINDOW_DRAG_FRAME_HZ = 60` cai pelo **p50** (16,7 ms contra o teto de 8,0), que é o braço
que ele existe para guardar.

**E o caminho pelo qual o `_astcache` se parte foi encontrado por acidente, medido:** a sonda que
levantou a distribuição acima importou o oráculo por `importlib` a partir de `H:/sotto` e caiu em
`ModuleNotFoundError: No module named '_astcache'` — o import por nome só resolve quando o diretório
do SCRIPT está no `sys.path`, o que é verdade em `python _main\x.py` e mentira em qualquer
instrumento que importe outro. Os **seis** oráculos passaram a pôr o próprio diretório no `sys.path`
antes do import.
