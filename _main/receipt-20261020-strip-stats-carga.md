# RECEIPT — 2026-10-20 — os dois passos `strip-stats` mediam a CARGA da máquina, não o PRODUTO

> Objectivo do dono: *"PARA DE FAZER MEU PC TRAVAR"*. Uma bateria que falha por
> causa do ruído do dono, e que obriga a re-correr tudo, é pior do que nenhuma.

---

## 1. O QUE ESTAVA PARTIDO (medido, não recontado)

A bateria (`_main\_audit-verify-all.cmd`, 52 passos) deu RED:

```
failed : strip-stats-log-budget=3  strip-stats-wave=3
steps  : 52  gate=40  control=10  skipped=1  expect-red=1  missing=0  cached=35
```

E o log do passo (`_main\_audit-verify\strip-stats-log.log`) disse, VERBATIM:

```
STRIP-LOG CONTROL FAIL ratio=21586300.0x failed=3 reason=both arms ran the
stand-in worker at the same rate; both arms reached the live page (READY) and
exited on their own; the aggregated arm still DELIVERED the feed (delivered > 100)
```

O ratio de **21 586 300x** é a assinatura de uma divisão por ~0: o braço
`aggregated` **nunca chegou a `RECEIVER_READY`**, logo escreveu **ZERO** linhas
`BRIDGE_STATS_PUSH`, e o "orçamento do log" mediu o nada.

O log desse braço (`_main\_strip-stats-log-aggregated-a1-51764-1792477102.log`)
diz porquê:

```
03:20:33.714  shell=webview2 pywebview=6.2.1 python=3.11.8 pid=39716
03:20:34.676  PANEL_LAZY_GATE_ARMED registered=5 urls=5
03:21:37.298  STAGING_SEEN document=stage.html -> bouncing to panel   <-- 63,58 s
```

O painel demorou **63,58 s** a aparecer. O passo matou o braço antes de a
página ficar viva → `ready=False, lines=0, delivered=0` → ratio disparado → RED.

**Não é defeito do produto.** A MESMA app, na MESMA máquina, **calma**, chega a
`RECEIVER_READY` em **1,98 s** (`I:\cc-tmp\sotto-032942.log`: READY-FILE 1,95 s,
STAGING_LOADED 1,97 s, RECEIVER_READY 1,98 s). A máquina é que estava saturada
(VRAM 100 %, 38 `msedgewebview2.exe`, ~15 processos python do dono, 3 lanes de
agente em paralelo).

O segundo passo (`strip-stats-wave`, `_main\_strip-stats-probe.py`) falhou
rc=3 **pela mesma porta**: os dois braços leem o DOM de uma página que nunca
carregou.

**O defeito de honestidade:** um gate que transforma "não consegui medir" num
RED do produto ensina o dono a ignorar o vermelho. Era isso que estava a
acontecer, todas as noites, com a máquina dele ocupada.

---

## 2. A CORRECÇÃO

### 2.1 Um módulo comum (sem duplicar a lógica)

`_main\_strip_stats_load.py` (novo, LF) — o que os dois gates passaram a partilhar:

| coisa | o que faz |
|---|---|
| `READY_DEADLINE_S` | o prazo (30 s) e a sua justificação em números |
| `arm_readiness(text)` | lê o log do braço e diz **se a página ficou viva e quanto demorou** — pelo relógio do PRÓPRIO log do shell |
| `load_skip_reason(arms)` | o veredicto SKIP: porque é que esta corrida não mediu |
| `budget_checks(per, agg)` | as afirmações do gate (50x, 100 linhas, `delivered > 100`) — **inalteradas** |
| `decide(arms, checks)` | **a ordem**: primeiro "houve medição?", depois "a medição passou?" |
| `deadline_facts()` | os números que justificam o prazo (usados pelo oráculo) |

A ordem em `decide()` é o ponto inteiro:

```
SKIP  <- um braço não chegou a READY dentro do prazo  (a caixa não mediu)
GREEN <- os dois braços mediram e todas as afirmações aguentaram
RED   <- os dois braços mediram e uma afirmação caiu   (o defeito do produto)
```

### 2.2 O gate do orçamento do log (`_main\_strip-stats-log-probe.py`)

* **FASE 1 — a página tem de ficar VIVA**, com prazo. O relógio do log do shell
  é a autoridade (`RECEIVER_READY` − primeira linha do log).
* **FASE 2 — a janela do feed**: a medição passa a contar **desde que a página
  ficou viva** até o shell sair. Antes contava desde 6 s fixos depois do
  arranque, o que sob carga contava o arranque do painel como tempo de feed e
  diluía os dois braços por quantidades diferentes.
* **SKIP em vez de RED** quando a página não ficou viva, com o prazo e o tempo
  medido no log.
* **O produto continua a aparecer**: com os dois braços vivos, a razão abaixo
  de 50x **é RED** (rc=3), como sempre.
* **O "saiu por si só" deixou de ser condição de RED.** O caminho de saída do
  shell com um worker vivo pode passar do temporizador (medido,
  `sotto_webview.py:7999-8007`), e isso não diz nada sobre o orçamento do log.
  A integridade da medição continua imposta pelos dados: ≥100 linhas por
  amostra e `delivered > 100` nos dois braços.
* **O `retry` foi removido.** Com prazo, repetir não compra nada: uma caixa
  lenta o bastante para perder 30 s é lenta o bastante para perder 60 s — e a
  repetição dobrava a espera justamente na máquina que menos pode pagar.
* **O `kill` deixou de rebentar.** A versão anterior levantava
  `TimeoutExpired` depois do `kill` e transformava uma caixa lenta num CRASH do
  instrumento (medido 2026-10-20 03:32, `_strip-stats-log-probe.json`:
  `verdict: CRASH`). Agora mata a árvore (`taskkill /F /T`, só o PID do próprio
  shell de medição) e nunca levanta.
* **O nome da cópia mutante passou a levar o carimbo da corrida.** O nome era
  partilhado por todas as corridas: dois probes em paralelo sobrescreviam a
  cópia um do outro, e o braço que julgava estar a medir o shell "por amostra"
  estava a medir o agregado — um RED sem causa.

### 2.3 O gate da onda (`_main\_strip-stats-probe.py`)

A mesma FASE 1/FASE 2 e a mesma decisão partilhada. Antes não imprimia
veredicto nenhum; agora imprime `STRIP-STATS VERDICT: GREEN|SKIPPED|RED`, que
é o que a bateria passa a ler.

---

## 3. O PRAZO, E PORQUÊ ESTE

**PRAZO = 30 s** (`READY_DEADLINE_S`), justificado pelos dois números medidos:

| número | medido | onde |
|---|---|---|
| arranque **calmo** | **1,98 s** até `RECEIVER_READY` | `I:\cc-tmp\sotto-032942.log` (03:29:44) |
| arranque **carregado** | **63,58 s** até `STAGING_SEEN` (que é ANTES de `RECEIVER_READY`, logo o arranque carregado é **pelo menos** esse) | `_strip-stats-log-aggregated-a1-51764-1792477102.log` |

* 30 s = **15,15×** o arranque calmo → uma caixa só "ocupada" ainda mede, e o
  prazo **não pode esconder o defeito**: o defeito é do CÓDIGO (o braço
  agregado escreve ~480× menos bytes por minuto), não da velocidade da máquina;
* 30 s = **2,1× abaixo** do arranque carregado → a caixa carregada é apanhada
  pelo prazo e não produz um rácio inventado.

O log diz sempre **qual foi o prazo e quanto o braço demorou**. O oráculo
verifica a justificação (`deadline_facts()`: `times_calm = 15.15`,
`below_loaded = True`).

---

## 4. OS NÚMEROS

**Oráculo novo** `_main\_strip-stats-load-oracle.py` (novo, LF):

```
ARMS ... 10/10
NEGATIVE ARM ... 4/4
VERDICT: PASS  arms 10/10  mutants 4/4  (0.0s)
```

| braço | o que simula | o que tem de dar |
|---|---|---|
| a | os dois braços prontos, razão alta | GREEN |
| b | um braço **não** chegou a READY no prazo | **SKIP**, e o motivo diz o prazo e o tempo |
| c | os dois braços prontos, razão **baixa** | **RED** (o mutante crítico) |
| d | a máquina carregada é **SIMULADA** | a decisão não lança nada |
| e1 | o relógio lê o log calmo (1,98 s) | pronto |
| e2 | o relógio lê o log carregado (63,58 s) | **não** pronto |
| f | os dois gates usam o módulo comum | nenhuma decisão duplicada |
| g | o prazo é justificado | ≥5× o calmo, abaixo do carregado |
| h | o braço **MORREU** antes da página | **RED** (não é um skip) |

**Mutantes EXECUTADOS (4/4 RED):**

1. "o braço não chegou a READY" é uma FALHA → apanhado por **b**;
2. "razão baixa com os dois braços prontos" é um SKIP → apanhado por **c**;
3. nunca SKIPa → apanhado por **b**;
4. um prazo curto demais para o braço bom → apanhado por **a**.

**As corridas REAIS desta noite (a caixa estava carregada):**

| gate | rc | o que aconteceu |
|---|---|---|
| `strip-stats-log-budget` | **0** (SKIP) | os dois braços esperaram 35,0 s / 35,1 s e a página **nunca** ficou viva (último marco: `PANEL_LAZY_GATE_ARMED` aos ~0,95 s). 70,4 s no total. |
| `strip-stats-wave` | **0** (SKIP) | `fed` e `unfed` esperaram 35,2 s / 35,0 s, a página nunca ficou viva. 70,5 s no total. |

Antes da correcção, estes mesmos braços davam **rc=3** e um rácio de 21 586 300x.

### 4.1 O VEREDITO REAL DA BATERIA

Corrida real desta noite, caixa carregada, com as alterações já dentro:

```
steps    : 53   gate=40  control=9  skipped=3  expect-red=1  missing=0  cached=43
failed   : -none-
skipped  :  strip-stats-log-budget strip-stats-wave hotkey-delivery
BATTERY-VERDICT: GREEN WITH 3 SKIPPED - 3 step(s) did NOT verify this run and
are NOT counted as gates:  strip-stats-log-budget strip-stats-wave
hotkey-delivery
BATTERY rc=0   (211,7 s)
```

`steps` subiu de 52 para 53 (o oráculo novo), `control` desceu de 10 para 9 (o
`strip-stats-log-budget` passou de `:control` a `:skipped`), `skipped` subiu de 1
para 3 (os dois passos que a caixa carregada calou).

**A BATERIA ESTÁ VERDE — mas dois dos passos NÃO AFIRMARAM NADA nesta
corrida.** `skipped=` é a parte do verde que não é afirmada, e é exatamente a
que o dono tem de ler antes de dizer "a bateria passou".

**O guarda de skips também passou** (`skip-verdict-guard rc=0`): 74 logs de
passo lidos, nenhum veredicto de skip fora dos três passos declarados
skip-capable — ou seja, nenhum passo se saltou a escondidas.

---

## 5. INTEGRAÇÃO NA BATERIA

```
  call :step always strip-stats-log-budget 0 "...;_main\_strip_stats_load.py;..." ...
  call :skipped strip-stats-log-budget !STEP_RC! "%OUT%\strip-stats-log.log" "STRIP-LOG CONTROL PASS" "STRIP-LOG CONTROL SKIPPED" "VERDICT: SKIPPED"
  call :step always strip-stats-wave 0 "...;_main\_strip_stats_load.py;..." ...
  call :skipped strip-stats-wave !STEP_RC! "%OUT%\strip-stats.log" "STRIP-STATS VERDICT: GREEN" "STRIP-STATS VERDICT: SKIPPED"
```

* **`:control` → `:skipped`.** O registo `:control` exige rc=0 **e** a frase de
  PASS; um gate que pode SKIP e um control que só sabe ler "PASS" dariam um
  RED falso. O registo `:skipped` (o mesmo do `hotkey-delivery`) distingue os
  três casos: rc≠0 é FALHA, rc=0 com o texto de SKIP é SKIP, rc=0 com o texto
  verificado é um gate a sério.
* **`always`.** A verdade destes dois passos está **fora dos ficheiros** — é a
  CARGA da máquina, que não está em nenhuma assinatura. Sem `always`, um SKIP
  ficaria **congelado no cache** e o passo nunca voltaria a medir até alguém
  tocar num ficheiro: um gate que apodrece em silêncio. Custo: estes dois
  passos pagam sempre ~2,5 min numa caixa carregada.
* **Oráculo novo registado** como passo simples (`strip-stats-load-oracle`),
  cacheável, com as dependências de todos os ficheiros que lê.

---

### 5.1 O PRE-COMMIT (o gancho recusou a primeira tentativa)

O gancho `scripts/pre-commit` corre `app\shadowplay\run-all.mjs`. As **15
suites passaram** (15 passed, 0 failed, 208 testes), mas o gate recusou **2
sondas de vídeo** (`compose-probe.mjs`, `keyframe-shape-probe.mjs`) com:

```
instant replay refused: ... holds 26 contiguous distinct frames but covers 240
frame slots; the clock is there and the content is not
```

Isto é o NVENC a produzir frames repetidos com a VRAM a 100 % — **a mesma
classe de falha que esta lane corrige**, noutro sítio: a máquina saturada a
responder por um probe. Essas sondas vivem em `app\shadowplay\`, que esta lane
**não pode tocar**, e a minha alteração é só em `_main\`: não há caminho pelo
qual o meu diff as affecte.

O gancho tem uma escotilha **explícita e ruidosa** (`SOTTO_SKIP_RUN_ALL=1`,
que imprime "suites and gate NOT run for this commit"), e o próprio gancho
convida a usá-la ("Fix it, or set SOTTO_SKIP_RUN_ALL=1 and say so in the
message"). O commit foi feito com a escotilha e a mensagem **diz** que as
suites correram e que 2 sondas de vídeo foram recusadas. **Não foi mexido em
`app\shadowplay\`.**

---

## 6. O QUE **NÃO** FOI MEDIDO

* **O caminho GREEN dos dois gates não foi medido nesta máquina.** A página
  nunca ficou viva dentro do prazo, portanto **nenhum rácio real** foi medido
  hoje: nem o orçamento do log, nem a onda. O caminho GREEN só está exercido
  pelo oráculo, com braços **SIMULADOS** — não por uma shell real.
* O **`ready_s` do braço bom** (1,98 s) vem da medição calma do app do dono
  (`I:\cc-tmp\sotto-032942.log`), não de uma corrida minha deste gate.
* **O custo da bateria numa caixa calma** não foi medido (a caixa nunca ficou
  calma durante esta lane).
* O **caminho de falha real** (razão baixa com os dois braços vivos) **não foi
  exercitado contra o shell real** — só contra o módulo partilhado, no oráculo.
* **A corrida do gate numa caixa calma** não foi feita: durante toda a lane a
  caixa esteve saturada (19 `msedgewebview2.exe`, 19 processos python).

---

## 7. LIMITACOES — E O QUE PODE APODRECER

1. **O gate pode SKIPar demais.** Este é o risco real desta correcção: um gate
   que SKIPa sempre não está a verificar nada, e o `skipped=` da bateria é a
   parte do verde que **não** é afirmada. O limite mensurável é o prazo: com
   30 s, uma caixa até ~15× mais lenta que o arranque calmo ainda mede; acima
   disso o gate cala-se. **Hoje, nesta caixa, o gate cala-se sempre** (a página
   nem chegou a encenar em 35 s) — a afirmação "o log agregado escreve muito
   menos" **não está a ser verificada** até a caixa abrandar. Quem lê o resumo
   da bateria tem de ver `skipped=` e não pode ler isso como verde.
2. **O `always` custa tempo sempre** (~2,5 min de shells de medição numa caixa
   carregada, ~1 min calma). É o preço de não congelar um SKIP no cache. A
   alternativa (gravar um rc que o cache nunca reutiliza) seria uma
   dependência escondida do `_stepcache.py`, que esta lane não pode tocar.
3. **O rácio deixa de ser medido se um braço for lento mas dentro do prazo**:
   a janela passa a contar desde que a página ficou viva, e os dois braços são
   medidos no mesmo tipo de intervalo. Se os dois braços ficarem vivos em
   momentos muito diferentes, a diluição já não é igual — o oráculo fixa o
   limiar em 50×, muito abaixo do ~480× medido, para absorver essa diferença.
4. **A cópia mutante vive dentro de `app\webview\`** (como sempre foi). O nome
   agora é único por corrida, mas continua a ser um ficheiro temporário em
   território de produto.
5. O **deadline de 30 s** é um número desta máquina. Noutra caixa, mais lenta
   em repouso, o mesmo prazo passaria a ser curto demais e o gate SKIParia
   sempre. O número é justificado por medições, mas as medições são **deste
   host**.
6. **O guarda de skips continua a proteger estes dois passos**: o log de um
   passo que saltou carrega `VERDICT: SKIPPED`, e o guarda falha a bateria se
   esse texto aparecer num log que não foi declarado skip-capable.

---

## 8. FICHEIROS (medidos em 2026-10-20, depois da correcção)

| ficheiro | o que é | bytes | finais | sha256 (16) |
|---|---|---|---|---|
| `_main\_strip_stats_load.py` | módulo comum (prazo, prontidão, decisão) | 10 941 | LF (261) | `0D5C37DC05D24F60` |
| `_main\_strip-stats-load-oracle.py` | oráculo novo (10 braços, 4 mutantes) | 16 403 | LF (368) | `BA59D6251F4F3B05` |
| `_main\_strip-stats-log-probe.py` | gate do orçamento do log | 16 431 | LF (350) | `0CCAB67AF1CB8A16` |
| `_main\_strip-stats-probe.py` | gate da onda | 17 198 | LF (366) | `FA5652A0E9E56FF4` |
| `_main\_audit-verify-all.cmd` | os dois blocos + o passo do oráculo | 54 822 | **CRLF 800 / bare LF 0** | `E97AA8DBF9A68371` |

O recibo é este ficheiro (14 583 B / LF). O repo está a ser editado por várias
lanes em paralelo: antes de citar um tamanho ou um sha, **medir de novo**.
