# Receipt — o motor AO VIVO passa a ser Parakeet Redux, com interruptor reversível

**Lane:** `redux-live` (delegada). **Raiz:** `H:\sotto`. **Data:** 2026-10-07 (madrugada de 2026-10-08).
**Pedido do dono, verbatim:** *"troca o nemotron 3.5 pelo parakeet redux, pra legenda ao vivo. quero testar"*
**Restrição central do pedido:** tem de ser um **interruptor reversível** que ele liga e desliga, **não** uma
substituição irreversível.

---

## 0. TL;DR — o veredicto em cinco linhas

1. **Entregue e medido:** `worker/redux_live.py` corre Parakeet Redux **ao vivo**, com janela deslizante,
   emite o **mesmo contrato JSONL** que o painel já consome, e foi **provado ponta-a-ponta pelo app real**
   (`app/webview/run.cmd`): 25 legendas entregues, 0 mortes, 0 malformadas, 0 `PAGE_ERROR`.
2. **O interruptor é de uma linha e não toca em ficheiro de outra lane:**
   `run.cmd --worker worker\redux_live.py` **liga**; `run.cmd` puro **volta atrás**. Por dentro,
   `--engine onnx|ternary` + `SOTTO_LIVE_ENGINE` escolhem o export.
3. **Motor por omissão = ONNX int4** (o export `eschmidbauer/parakeet-redux-onnx`), porque é
   **6,3× mais leve em RAM** e **~2,2× mais rápido** que o ternário, **com texto byte-idêntico**.
   `--engine ternary` continua disponível (é o checkpoint canónico; o dono testa e decide).
4. **AVISO HONESTO — esta mudança INVERTE a lei da stack que o dono decidiu.** O Redux ternário **não é
   "leve ao contrário do nvidia"**: medido **3830,4 MB de pico RSS** no processo ao vivo contra os
   **574,7 MB** do ONNX int4 e os **1192 MB** documentados do nemotron int8. O ternário é o mais leve
   **em disco** (179 MB) e o mais pesado **em RAM**. A decisão é dele; o número não pode desaparecer.
5. **A máquina aguenta com o ONNX int4 (574,7 MB, 6,4 % dos 20 núcleos); com o ternário, 3,9 GB residentes
   não são distribuíveis** — o ONNX int4 é o único braço simultaneamente leve e neutro em fabricante.

---

## 1. O que foi entregue

| # | entrega | estado |
|---|---|---|
| 1 | `worker/redux_live.py` — motor ao vivo, **ficheiro novo**, nenhum outro ficheiro de outra lane tocado | ✅ 52 471 B, provado ponta-a-ponta |
| 2 | Interruptor reversível (flag/env + `--worker` do shell) | ✅ uma linha para ligar, uma para desligar |
| 3 | Medições com números (latência, CPU, RSS, qualidade, "a máquina aguenta?") | ✅ §5–§7 |
| 4 | Aviso honesto da inversão da lei da stack | ✅ §8 |
| 5 | Prova end-to-end pelo app real + higiene pós-corrida | ✅ §10, §11 |

**Ficheiros de OUTRAS lanes que eu NÃO toquei:** `worker/sotto_worker.py`, `worker/redux_batch.py`,
`app/panel/*`, `app/webview/*` (incluindo `app/webview/README.md`), `app/webview/run.cmd`, `AGENTS.md`.
Escrevi **apenas** `worker/redux_live.py` e os meus instrumentos/receipt dentro de `H:\sotto\_main\`.

---

## 2. O interruptor — como ligar, como voltar atrás

### 2.1 Nível 1 — qual processo é o worker (o interruptor do pedido)

O shell **já tinha** o encaixe; **não foi preciso editar nada**. Re-verificado na revisão actual:

| o quê | onde |
|---|---|
| `--worker` (argparse) | `app/webview/sotto_webview.py:7377` (`help='worker entrypoint to spawn'`) |
| `--python` | `app/webview/sotto_webview.py:7378` |
| `DEFAULT_WORKER_PATH` | `app/webview/sotto_webview.py:65` = `normpath(HERE/../../worker/sotto_worker.py)` |
| `worker_path=self.args.worker` / log | `:5788` / `:5797` (`WORKER_PATH …`) |
| `WorkerBridge.__init__(…, worker_path, …)` | `:6460` (`self.worker_path` em `:6467`) |
| `_spawn()` — guarda alta `BRIDGE_WORKER_MISSING path=…` | `:6636`, `:6640-6649` |
| `env` com `SOTTO_CAPTURE_MODE` | `:6675` |
| `SOTTO_AUDIO_DEVICE` (só quando `device is not None`) | `:6676-6677` |
| `creationflags = CREATE_NO_WINDOW (0x08000000)` em nt | `:6679-6680` |
| spawn `[self.command, self.worker_path]` | `:6684` |
| `run.cmd` passa `%*` intacto; só acrescenta `--log`/`--ready-file` | `app/webview/run.cmd:161-173` |

⇒ **LIGAR:** `run.cmd --worker worker\redux_live.py`
⇒ **VOLTAR ATRÁS (trivial):** `run.cmd` (ou `run.cmd --worker worker\sotto_worker.py`)

Consequência importante: **o shell não passa NENHUMA flag extra ao worker** — só o caminho. Por isso
`redux_live.py` tem de estar **correcto nos seus defaults**. Está: `--engine onnx`, `--window-s 5.0`,
`--step-s 2.0`, config lida de `worker/config.json`.

E o caminho errado **falha alto, não em silêncio**: um `--worker` mal escrito produz
`BRIDGE_WORKER_MISSING path=…` (medido no código, `:6640-6649`).

### 2.2 Nível 2 — qual export do Redux (dentro do motor)

Precedência: `--engine` > `SOTTO_LIVE_ENGINE` > `onnx` (omissão). Um valor desconhecido **sai com 2**, nunca
é coagido.

```
run.cmd --worker worker\redux_live.py                          # ONNX int4 (omissão, leve)
run.cmd --worker worker\redux_live.py --engine ternary         # ternário canónico
set SOTTO_LIVE_ENGINE=ternary && run.cmd --worker worker\redux_live.py
```

Os dois braços **são Parakeet Redux** — o mesmo modelo, dois exports. Não é uma escolha de modelo.

### 2.3 O que NÃO foi feito, e por quem é devido

`app/webview/README.md` **não foi editado** (é ficheiro de outra lane). **Fica devida uma linha de
README/`--help` no shell** ao dono do `app/webview/` — o interruptor existe e está documentado no
`--help` do `redux_live.py` (epilog com `RawDescriptionHelpFormatter`, os dois sentidos), mas a
documentação de topo do app ainda não o menciona. **Isto é uma dívida declarada, não um esquecimento.**

### 2.4 COLISÃO / ORTOGONALIDADE com o interruptor de uma lane irmã — reportar, não confundir

**Existem agora DOIS interruptores e eles são ORTOGONAIS.**

| | interruptor | o que faz | onde | estado |
|---|---|---|---|---|
| (1) | `--redux-when-hidden` (lane irmã `SottoReduxVisibility`, `_main/receipt-redux-visibility.md`) | troca o motor **DENTRO** do worker ao vivo quando o painel está escondido, gate em `panel-visibility.json` fresco, a correr o **runner batch** | `worker/sotto_worker.py:3017` (flag, default **OFF**), `:4012` (`redux_optin`), `:4020` (armado), `:4557` (update guardado) | **NÃO está ligado no app do dono** (precisa `SOTTO_REDUX_WHEN_HIDDEN=1` + reinício) |
| (2) | **o meu** | **substitui o processo worker inteiro** | `run.cmd --worker worker\redux_live.py` | provado ponta-a-ponta hoje |

**Com (2) activo, o (1) não está no mesmo processo.** Não competem, não se somam, e nenhum dos dois
invalida o outro. O caminho escondido do (1) usa o **Redux batch**, por isso a minha medição de 3,9 GB do
ternário é **directamente relevante para o orçamento de RAM deles também** — e o receipt deles já regista
uma falha de alocação sob essa carga (§17).

---

## 3. O contrato JSONL — confirmado por LEITURA antes de implementar

Li `worker/sotto_worker.py` e `app/panel/panel.js` **antes** de escrever o motor. O que o painel consome:

**Forma 1 — hipótese cumulativa (a legenda em curso), `final:false`:**
```json
{"type":"caption","text":"<linha inteira até agora>","start":<fixo por segmento>,"end":<a crescer>,"final":false,"producer":"redux"}
```
**Forma 2 — linha fechada, `final:true`:** igual, com `"final":true`.

Pontos do painel que **determinam** a forma (verificados linha a linha):

- `caption-formulation.js:203 createEngine({onCommit, onProvisional, now})`; `onProvisional(committed, provisional)` `:649`; `onCommit(line, reason, meta)` `:498`; API `:706-718` `{ingest, flush, expireHold, reset, visible, state}`.
- **O voto final é lido de `meta.final`:** `caption-formulation.js:621` `if (meta && typeof meta.final === 'boolean') bufferSawFinal = true;` e `:622` `if (meta && meta.final === true) bufferFinal = true;`; `routeFor()` `:382` → `'final'` se `bufferFinal`, senão `'provisional-draft'`; `routeSource()` `:414` → `'worker-stamped'`.
- **O `producer` é rastreado e o primeiro valor ganha:** `:303 bufferProducer`, `:307 bufferProducerConflict`, leitura `:311`, primeiro valor `:326-327`, conflito `:330`, `committedProducer()` devolve `null` a menos que `bufferSawProducer && !bufferProducerConflict` (`:335-336`).
- `panel.js:575-580 wireCaptions()` → `bridge.onCaption(({text, meta}) => { armHoldTimer(); engine.ingest(text.trim(), meta || {}); })`.
- `panel.js:414-443` — ligação real: `onCommit: (text, reason, meta) => { retireProvisional(); addCaption(text, reason, meta); }` (`:439-440`), `onProvisional: (committed, provisional) => renderProvisional(committed, provisional)` (`:442`).
- `panel.js:460-468 armHoldTimer()` — `setTimeout(..., COMMIT_MAX_HOLD_MS)` → `engine.expireHold()`; constantes `SENTENCE_GAP_S = 8` (`:72`), `SENTENCE_MAX_CHARS = 90` (`:75`), `COMMIT_MAX_HOLD_MS = 1500` (`:99`).
- **O shell transforma TODA chave extra em `meta`:** `sotto_webview.py:6826-6842` `meta = {k: v for k, v in message.items() if k not in ('type','text')}` ⇒ `start`, `end`, `final`, `producer`, `model` chegam todos ao painel. Uma legenda é também **a única coisa que levanta uma morte pendente** (`BRIDGE_DEATH_LIFTED reason=caption`).

### 3.1 As duas armadilhas que o contrato impõe (e como o motor as evita)

Lendo `panel.js:591-659 addCaption`: `const start = meta.start`; `existing = committedByStart.get(start)`;
**se existe e está ligado → SUBSTITUI o texto no lugar**; senão cria `<li>`. E `renderProvisional`
(`:495-558`) procura a linha em curso por `querySelector('.caption--provisional')` — é um **singleton**.

| armadilha | consequência | regra que o motor segue |
|---|---|---|
| dois segmentos fechados com o **mesmo `start`** | o segundo **substitui** a linha do primeiro e o texto dele é **destruído** (linhas < linhas fechadas) | `start` **único por segmento fechado** |
| `start` a **avançar a cada parcial** | o teste de revisão (`start < lastAudioEnd`, `:534`) falha, cada parcial é tratado como continuação e as palavras **repetem-se** | `start` **fixo durante o segmento** |

Ambas foram **provadas por oráculo** (§7.2), não por leitura.

---

## 4. Janela e passo — escolhidos por MEDIÇÃO, não por palpite

**Escolhidos: `--window-s 5.0` / `--step-s 2.0`.** (omissão do ficheiro; `DEFAULT_WINDOW_S=5.0`,
`DEFAULT_STEP_S=2.0`).

A regra que manda: **`compute(janela) < step`**, senão a fila cresce sem limite e a latência diverge.

### 4.1 Porque NÃO `step_s = 1.0` (a evidência)

Duas corridas reais com `--window-s 5.0 --step-s 1.0` (`_main/redux-live-smoke.jsonl`,
`_main/redux-live-noagc.jsonl`), lidas das próprias linhas `done`:

| stream | `mean_compute_s` | `max_compute_s` | `overruns` | janela maior |
|---|---|---|---|---|
| `redux-live-smoke.jsonl` | 3.678 | 4.465 | **5/5 passes** | 10,10 s (!) |
| `redux-live-noagc.jsonl` | 4.503 | 5.191 | **5/5 passes** | 10,10 s (!) |

⇒ com `step_s=1.0` **todos** os passes ultrapassam o passo e a janela deixa de ser um limite (10,10 s
apesar de `--window-s 5.0`). É a evidência directa da escolha de `2.0`.

### 4.2 O que mudou no código por causa disto

- `_drain_pending(limit=…)` faz da janela um **tecto duro**: alimenta no máximo `limit` segundos e
  **devolve o resto à FRENTE** da fila (`self.pending.appendleft(joined[room:])`); com `room <= 0`
  devolve 0 e re-enfileira tudo.
- `backlog_s()` diz **quanto espera**; `max_window_s` no `done` é como o tecto é **verificado**, não afirmado.
- `decode_loop()` usa `next_step = now + step` (**não** `+= step`) ⇒ os passes coalescem em vez de
  acumularem fila; a mensagem `WARN LIVE_STEP_OVERRUN` carrega `backlog_s`.
- `should_close(text)` compara `self.open_seconds >= self.window_s - 1e-6` (o épsilon fecha o defeito do
  `window_s=10.10`).

### 4.3 O resultado, medido (pós-correcção)

| motor | `mean_compute_s` | `max_compute_s` | `overruns` | `max_window_s` | `backlog_s` no fim |
|---|---|---|---|---|---|
| ONNX int4 | 0.95 | 1.244 | **0 / 14 passes** | 5.0 | **0.00** |
| ternário | 1.018 | 1.144 | **0 / 5 passes** | 5.0 | **0.00** |

`effective_step_s=1.244` (ONNX) — ou seja o passo efectivo ficou **abaixo** de 2,0 s: **não há backlog, não
há divergência**. Fonte: linhas `done` de `_main/redux-live-latency-onnx.jsonl` e
`_main/redux-live-latency-ternary.jsonl`.

---

## 5. Latência (áudio → texto no ecrã)

**Instrumento:** `_main/redux-live-latency-probe.py` (17 537 B). Lança o motor com
`creationflags=CREATE_NO_WINDOW (0x08000000)`, redirecciona o stdout da criança para **ficheiro**,
faz poll a cada **20 ms** e carimba cada linha com `time.perf_counter()`. **Não abre nenhum dispositivo
de áudio** — usa `--wav`. Origem = a linha `capture-started`; `lag = (_t_wall − origin) − end`.

Porque isto é uma latência **verdadeira** e não uma ficção: `worker.FileTap` (docstring em
`sotto_worker.py`) lê o WAV **em tempo real**, num ritmo de relógio de parede, "a forma exacta de um
callback do PortAudio, menos o dispositivo" — logo a posição no WAV **é** o relógio e `t_wall − end` é a
latência áudio→texto.

### 5.1 Resultado — ambos os motores a 5,0 / 2,0

| motor | 1º parcial | finais min / média / max | declive | veredicto |
|---|---|---|---|---|
| **ONNX int4** | **+1,02 s** | +0,62 / **+1,34** / +2,17 s | **−0,025 s por s de áudio** | **TRACKS-REAL-TIME** |
| **ternário** | **+1,06 s** | +0,63 / **+1,25** / +2,09 s | **−0,120 s por s de áudio** | **TRACKS-REAL-TIME** |

Declive negativo e plano (|declive| < 0,15) ⇒ **a latência NÃO diverge, acompanha o tempo real**. É o
número que o brief exigia. Fontes: `_main/redux-live-latency-onnx-v2.out`,
`_main/redux-live-latency-ternary-v2.out`.

### 5.2 A corrida ONNX PRÉ-correcção, mantida como controlo antes/depois

`_main/redux-live-latency-onnx.out` (rc=0, pré-fix): `wall=51.9s audio covered=26.8s captions=4 (2 final)`;
`WARN LIVE_STEP_OVERRUN pass=2 compute_s=16.61 step_s=1.0 window_s=10.10`;
`VERDICT DIVERGES (lag grows +nan s per audio-s)`. **É de confiança zero** (o `nan` vem do defeito 1 da
§13) e está **superada** pela v2 — mas fica registada porque é a prova de que o defeito existia.

---

## 6. Custo: CPU, RSS, e "a máquina aguenta o dono a jogar/ver vídeo?"

### 6.1 Processo AO VIVO (o que interessa para esta entrega)

| motor | RSS após load | **pico RSS** | CPU-s | % de um núcleo | % dos 20 núcleos | caixa ocupada durante a corrida |
|---|---|---|---|---|---|---|
| **ONNX int4** | 498,9 MB | **574,7 MB** | 41,5 em 32,3 s | 128,4 % | **6,4 %** | 11,81/20 (59,1 %) |
| **ternário** | 3650,5 MB | **3830,4 MB** | 37,2 em 25,1 s | 148,3 % | **7,4 %** | 11,08/20 (55,4 %) |

O worker do dono queimou **75,3** / **68,5** CPU-s e o shell **0,4** CPU-s nas mesmas janelas — **nunca
tocados**. Caixa: i5-13600K, 20 processadores lógicos, RAM 48888 MB total / 24314 MB livres.

**Custo de arranque (visível para o utilizador):** `model-loaded load_s=10.94` no ternário contra
`1.93` no ONNX ⇒ **trocar para ternário acrescenta ~9,0 s a cada arranque do worker.** Não é ruído, é
tempo que o dono espera.

### 6.2 Custo por chamada, medido em lote (`_main/redux-engine-cost-probe.py` → `redux-cost-*.log`)

Os três textos são **byte-idênticos ao oráculo cp1252** em todos os braços.

| motor | RSS pós-imports | RSS pós-load | **pico RSS** | load s | compute s (15 s áudio) | RTF | notas |
|---|---|---|---|---|---|---|---|
| ternário CPU dense | 19,4 MB | 3651,1 MB | **3855,8 MB** | 7,52 | 3,94 | 3,81× | `torch_threads=2` |
| ternário CUDA | 19,5 MB | 1342,9 MB | **1860,3 MB** | 4,60 | 2,26 | 6,64× | VRAM alloc 2483,7 / pico 2611,0 / reservada 2832,0 MB, RTX 5080; `torch_threads=14` |
| **ONNX int4 CPU** | 53,2 MB | 497,6 MB | **615,3 MB** | 0,90–1,05 | 1,62–1,80 | **8,33–9,26×** | `providers=['CPUExecutionProvider']` |

### 6.3 Curva de custo por tamanho de janela — DUAS tabelas, ambas rotuladas

**(a) CONTENDIDA** (`_main/redux-live-arm3.out`, ARM 1 do window-probe) — havia outro processo ONNX
(pid 41236, 642 MB), `node 8084` (1319 MB) e o worker do dono a ~1 núcleo vivos:

| janela | wall |
|---|---|
| 2,00 s | 2,557 s |
| 3,00 s | 3,820 s |
| 5,00 s | **10,774 s** |
| 8,00 s | **22,493 s** |

Veredicto do probe: `NO (window, step) pair fits`. **Este veredicto está ERRADO como afirmação sobre o
modelo** — ver (b).

**(b) NÃO-CONTENDIDA** (`_main/redux-live-arm1-recheck.py`, `--threads 2 --passes 2`, processo fresco,
uma sessão partilhada, leitor de referência):

| janela | pass 1 wall / cpu | pass 2 wall / cpu |
|---|---|---|
| 2,00 s | 1,328 / 2,422 | 0,851 / 2,188 |
| 3,00 s | 1,130 / 2,250 | 0,931 / 2,281 |
| 5,00 s | 1,358 / 2,688 | 1,323 / 2,672 |
| 8,00 s | 2,026 / 3,828 | 2,150 / 3,656 |

`wall/cpu` 0,39–0,59 (CPU-bound, ~2 threads ocupados, **não** desschedulerizado); spread de wall ≤1,6× e de
cpu ≤1,1×. ⇒ **o `5 s → 10,774 s` do ARM 1 era CONTENÇÃO DA MÁQUINA, não o modelo.**

**CPU-s por segundo de áudio (à prova de contenção, `time.process_time()`):**
`2s = 1,15 · 3s = 0,76 · 5s = 0,54 · 8s = 0,47`
⇒ há um custo fixo de ~2,2 CPU-s mais ~0,2 CPU-s por segundo de áudio: **janelas maiores são mais
eficientes por segundo de áudio**. É por isso que não se "resolve" o custo encolhendo a janela.

**Método de atribuição de CPU (o que decidiu a contradição dos 8×):** `time.perf_counter()` (parede) aos
pares com `time.process_time()` (CPU-s queimados pelo MEU processo, todos os threads). parede ≫ cpu ⇒
DESCHEDULADO; parede < cpu ⇒ multi-thread CPU-bound. **`process_time()` é à prova de contenção** — foi o
discriminador que fechou a contradição.

**`--threads 2` é o óptimo MEDIDO, não apenas o orçamento da casa:** `threads=0` (omissão ORT = 20) é
10–20× mais lento em parede; `arena=off` é pior que a omissão.

### 6.4 A resposta directa: "a máquina aguenta?"

- **ONNX int4 a 5,0/2,0: SIM, é utilizável com o dono a jogar/ver vídeo.** 574,7 MB residentes, 6,4 % dos
  20 núcleos, latência plana em +1,34 s. É o braço que eu recomendo.
- **Ternário: NÃO é viável para uso contínuo** — **3,90 GB residentes**, +9 s em cada arranque, e não é
  distribuível (ver §8.3). Não declaro o ternário motor ao vivo por omissão (decisão pré-autorizada, §15).
- **Não medi um stall do PC.** Retirei a frase não-suportada "o dono teve um stall de ~2 s" do docstring
  (não tinha instrumento atrás) e substituí-a pelos factos medidos: 3,9 GB residentes, caixa 59,1 %
  ocupada durante o braço ao vivo. **O que eu POSSO afirmar é o custo; o que eu NÃO posso afirmar é que
  ele não incomoda — isso o dono sente, eu não.**

### 6.5 A alternativa se for pesado demais

O export ONNX **é** a alternativa, e é re-baixável:
`hf download eschmidbauer/parakeet-redux-onnx` → **27 ficheiros / 436 066 441 B (415,87 MB) em ~12,4 s**
(medido hoje). Não precisa de `torch`, não precisa de GPU: **`onnxruntime>=1.22` + numpy e mais nada**
(é o `requirements.txt` do próprio export).

---

## 7. Qualidade — paridade com `redux_batch.py` (o oráculo)

### 7.1 Paridade batch: byte-idêntica

Os três braços do motor (ternário CPU, ternário CUDA, ONNX int4) produzem **texto byte-idêntico** ao
oráculo `_main/redux-ptbr.txt` (e ao `redux-en.txt` no clipe inglês), incluindo fronteiras de segmento.
`text_matches_oracle: true` em `_main/redux-cost-onnx.log`.

### 7.2 Paridade do CONTRATO com o painel — oráculo a sério

`_main/redux-live-contract-oracle.js` (13 663 B) corre o **`app/panel/caption-formulation.js` real** sobre
o **`_main/redux-live-smoke.jsonl` real**, com as três regras de linha do `panel.js` modeladas e ancoradas.

| braço | medido | veredicto |
|---|---|---|
| `A0/formulation-loads`, `A0/panel-anchors`, `A0/stream-is-real` | — | GREEN |
| `A1/one-row-per-closed-line` | 3 linhas fechadas → **3 linhas** (3 anexadas, **0 substituídas**) | GREEN |
| `A2/no-commit-ever-replaced-a-row` | `replaced=0` | GREEN |
| `A3/segment-identity-is-distinct` | `start values: [0, 8.2, 16.1]` | GREEN |
| `A4/no-duplicated-words` | sem bigramas repetidos | GREEN |
| `A5/provisional-is-a-singleton` | máximo **1** linha provisória simultânea | GREEN |
| **`B1/control-went-RED`** | `rows=5 (shipped=3) replaced=2 repeated bigrams=4` | **RED como exigido** |
| **`C1/control-went-RED`** | `3 closed line(s) -> 1 row(s), replaced=1` | **RED como exigido** |

`VERDICT PASS — 8/8 shipped-contract arm(s) held`. **Ambas as cores**: o braço B (o defeito "`start = end`")
e o braço C ("`start = 0.0` em todo o lado") provam que o oráculo **sabe dizer não**.

### 7.3 Deriva ao vivo vs batch — divulgação honesta

O motor ao vivo **não tem paridade byte-a-byte com `redux_batch.py`**: ao vivo a 5,0/2,0 aparecem
`"práxima"` por `"próxima"`, uma alucinação `"vai ser entrada."` na linha 6 do stream ONNX v2 (corrigida
na linha 7), e fronteiras de linha que re-cobrem áudio quando o WAV dá a volta. **Os dois exports ao vivo
concordam byte-a-byte entre si** no mesmo áudio. O oráculo batch continua byte-idêntico nos três braços.
A causa é o regime: batch vê o clipe inteiro, o motor ao vivo vê janelas de 5 s.

### 7.4 O que a história real mostra sobre o contrato (interacção ao vivo)

O ficheiro que a corrida ponta-a-ponta escreveu (§10.3) tem **5 linhas, todas `route=final
src=worker-stamped`, `reason=chars` a 65–80 caracteres** e `start` a avançar monotonicamente
(0 / 5 / 10 / 15 / 25) ⇒ **nenhuma linha foi substituída**. Nota de comportamento: quem fecha a maioria das
linhas é o **tecto de caracteres do painel** (`SENTENCE_MAX_CHARS = 90`), não o meu `--max-line-chars 88`.

---

## 8. AVISO HONESTO — esta mudança INVERTE a lei da stack do dono

### 8.1 A lei, verbatim (dono, 2026-10-07)

> *"o nvidia é pro ao vivo, o parakeet redux é pro geral. o ao vivo só acontece quando o painel ta aberto.
> quando ta fechado, o redux entra, e vira um transcritor LEVE ao contrario do nvidia."*

O Redux é, nessa lei, **o transcritor LEVE**. O pedido de hoje põe o Redux **ao vivo** — e a palavra
"leve" viaja com ele para um regime onde ela **não se verifica**.

### 8.2 O número que não pode desaparecer

| motor | pico RSS medido | relação |
|---|---|---|
| **Redux ternário** (o checkpoint canónico, ao vivo) | **3830,4 MB** | **6,7× o ONNX int4** |
| Redux ONNX int4 (o export) | **574,7 MB** ao vivo / 615,3 MB em lote | 1× |
| nemotron streaming int8 (o motor ao vivo de hoje) | **1192 MB** documentado | 0,31× do ternário |

⇒ **O Redux ternário NÃO é "leve ao contrário do nvidia": é ~3,2× mais pesado em RAM que o nemotron que
ele substitui, e ~6,7× mais pesado que o export ONNX do mesmo modelo.** Ele é o mais leve **em disco**
(179 MB) e o mais pesado **em RAM**. A lei da stack foi escrita a olhar para o disco; **o que decide é a
RAM**.

**A decisão é do dono.** O que eu não posso fazer é deixar o número cair fora do receipt.

### 8.3 Restrição de distribuição (o dono exige que a GPU funcione para QUALQUER utilizador)

| braço | RAM | distribuição |
|---|---|---|
| ternário dense CPU | ~3,9 GB | ❌ não distribuível |
| ternário CUDA | 1860 MB host + 2611 MB VRAM | ❌ exige GPU NVIDIA |
| **ONNX int4** | **615 MB**, ~8,3× tempo real, `onnxruntime` + numpy | ✅ **único braço leve E neutro em fabricante** |

### 8.4 Porque é que o ternário é pesado (a causa, não a impressão)

O kernel int8 compilado do kestrel está **inacessível nesta máquina** (`ternary_gemm_isa()` → `'scalar'`
apesar de o CPU ter AVX2), então o runner cai na forma **`dense` documentada**: **193/193 camadas ternary
desquantizadas de uma vez para float** no carregamento ⇒ o pico de ~3,9 GB. Ver §9.

---

## 9. Photon / `gemm8` — medido PRIMEIRO, por ordem do agente pai

O dono perguntou *"e o parakeet redux nao é usado com o photon?"*. O agente pai ordenou **medir o caminho
`gemm8` int8 do Photon ANTES de escrever o motor ao vivo**. Feito. **Instrumento:**
`_main/redux-gemm8-probe.py` (19 168 B) → `_main/redux-gemm8-probe.log` (6 563 B).

**Veredicto: o `gemm8` NÃO corre aqui — é código AUSENTE, não uma barreira de licença/chave.**

| sonda | resultado |
|---|---|
| `gemm_isa_available('avx2' / 'avxvnni' / 'avx512vnni')` | `False` / `False` / `False` |
| `ternary_gemm_isa()` | **`'scalar'`** |
| `ternary_gemm(..., isa='avx2')` | `ValueError: no 'avx2' matrix-multiply path on this machine` |
| `conformer_isa('avx2')` | `ValueError: no 'avx2' conformer vector width on this machine` |
| o CPU **tem** AVX2? | **SIM** — `torch.backends.cpu.get_cpu_capability() == 'AVX2'` |
| `kestrel_cpu.kstlc` | 51 598 B, sha256 `946ac2a0fcab8158e1dbda22746b0a430912478397b66ad817974b5da7bda453`, **byte-idêntico** ao payload publicado do `kestrel_kernels-0.7.4-cp311-cp311-win_amd64.whl` |
| **controlo `--neg-arm`** | `identical=False -> RED as required` |

**Armadilha medida (vale mais que o resultado):** `set_gemm_isa('avx2')` é **aceite** — e depois
`resident_form('cpu')` devolve `'gemm8'`, `materialize()` **sucede**, e é a **PRIMEIRA projecção** que
rebenta. Ou seja, o caminho falha **depois** de parecer que funcionou. É por isso que o patch de
`resident_form` que o `redux_batch.py` faz (`_weight_form`, `:64`) é a **forma correcta** de o tratar, e
não uma gambiarra.

⇒ **Consequência para a decisão:** o `gemm8` não é hoje uma saída para o peso do ternário. Se um dia
correr, o ternário empacotado seria leve **e** em RAM **e** em disco — mas isso é uma promessa, não uma
medição, e eu não a faço.

---

## 10. Prova PONTA-A-PONTA pelo app REAL

### 10.1 O instrumento

`_main/e2e-redux-shell-arm.py` (13 320 B) conduz o **app verdadeiro** (`app/webview/run.cmd`) com
`--worker H:\sotto\worker\redux_live.py --with-worker --no-hotkey --exit-after 45
--log _main\e2e-redux-shell.log`, `SOTTO_FILE_TAP` apontado ao WAV (⇒ **nenhum dispositivo de áudio é
aberto**, não colide com o endpoint que o worker do dono segura), `cwd=ROOT`,
`creationflags=CREATE_NO_WINDOW`.

`--with-worker` é **obrigatório**: `--no-hotkey` e `--exit-after` estão no conjunto
`measurement-flag(<flag>)` que **suprime** o arranque do worker (`sotto_webview.py:2672-2678`).

Censo de janelas em processo a **100 ms** (ctypes `EnumWindows`/`IsWindowVisible`/`GetWindowTextW`/
`GetClassNameW`/`GetWindowThreadProcessId`, com `argtypes` explícitos), thread `e2e-census`, pids
resolvidos com **UM** `pwsh … Get-Process … ConvertTo-Json` **depois** da amostragem.

### 10.2 Resultado — `_main/e2e-redux-shell-arm.out` (rc=0, `VERDICT PASS`)

- `run.cmd returned rc=0 after 49.57s`; **`shell pid 40680 gone at +50.9s`**.
- **`samples=345` a 100 ms**, `distinct pids with a window=11`; controlo pré-spawn: 11 pids.
- **ARM A / nenhuma janela do shell ou do painel: `forms=[]` → GREEN.**
- **ARM B / o instrumento não está cego: outro pid visível em 345/345 amostras → GREEN.**
- **ARM C / nenhum pid da família python tem janela: `[]` → GREEN.**
- Donos de janela nomeados: `13748 (explorer)`, `1628 (chrome)`, `9000 (explorer)`, `8696 (powershell)`,
  `21492 (WindowsTerminal)`, `25544 (chatterino)`, `21376 (cmd)`, `32276 (voicemeeter)`,
  `20364 (Discord)`, `20112 (TextInputHost)`, `16516 (NVIDIA Overlay)`.
- `BRIDGE_CAPTION_SENT count=25 deaths=0 malformed=0`; `PAGE_ERROR: []`; `BRIDGE_WORKER_MISSING: []`.
- **`VERDICT PASS -- no_window=True instrument_not_blind=True no_python_window=True
  captions_through_the_shell=True`**

### 10.3 O log do PRÓPRIO shell — `_main/e2e-redux-shell.log` (11 466 B)

As linhas decisivas:

| linha | conteúdo |
|---|---|
| `:40` | `WORKER_PATH H:\sotto\worker\redux_live.py` |
| `:42` | `BRIDGE_START reason=with-worker … capture=callback` |
| `:45` | **`BRIDGE_SPAWNED pid=5588 argv=["…python.EXE", "H:\\sotto\\worker\\redux_live.py"] worker_sha256=b81612333ec60977 SOTTO_CAPTURE_MODE=callback SOTTO_AUDIO_DEVICE=(unset)`** |
| `:46` | **`WORKER_AUTOSTART=started reason=with-worker`** |
| `:47` | **`CODE_STATE reason=worker-started-with-worker worker_disk=b81612333ec60977 worker_loaded=b81612333ec60977 worker_stale=false shell_disk=ea014d8f2cacd72e shell_loaded=ea014d8f2cacd72e shell_stale=false`** |
| `:29`/`:32` | `PANEL_SHOW_REFUSED reason=not-asked opacity=1.0 show_requested=false panel_shown=false` ×2 |
| `:39` | `PANEL_VISIBILITY_ON_SCREEN visible=false where=startup hwnd=16131246` |
| `:56-58` | `BRIDGE_CAPTION_SENT delivered=true text="The radio announced that the bridge over the…"` |
| `:59,66,72,84,96` | **`HISTORY_APPEND path="H:\\sotto\\history\\2026-10-07\\14.md"` bytes=78/81/80/71/66** |

⇒ **O shell real hashou o meu ficheiro por conta própria (`worker_sha256=b81612333ec60977`) e confirmou
`worker_stale=false`.** Não é a minha palavra sobre a minha palavra.

**Nota:** o shell lança **`python.EXE`**, não `pythonw.exe` — é o `CREATE_NO_WINDOW (0x08000000)` que o
mantém invisível, e isso está **medido** (345 amostras), não assumido.

### 10.4 O feed canónico da história FOI ABERTO — e o ficheiro existe

`H:\sotto\history\2026-10-07\14.md` — **789 B, mtime 2026-10-07 14:20:55, sha256
`0fe964b2c2aab9c0674ae032b226db4ff83041099db4237ea4a7013aeb8b550c`**. É o ficheiro **mais recente** de
`history/` (o anterior era `history/2026-10-06/19.md`, mtime 2026-10-06 19:58:36). Conteúdo integral:

```
- [14:20:24] The radio announced that the bridge over the river will be closed next Monday. <!-- route=final start=0.00 src=worker-stamped reason=chars 78 -->
- [14:20:26] Residents need an alternative route to get to work. The radio announced that the. <!-- route=final start=5.00 src=worker-stamped reason=chars 80 -->
- [14:20:32] Bridge over the river will be closed next Monday. Residents need an alternative. <!-- route=final start=10.00 src=worker-stamped reason=chars 79 -->
- [14:20:42] Closed next Monday. Residents need an alternative route to get to work. <!-- route=final start=15.00 src=worker-stamped reason=chars 71 -->
- [14:20:55] Residents need an alternative route to get to work. The radio and. <!-- route=final start=25.00 src=worker-stamped reason=chars 65 -->
```

**`route=final` + `src=worker-stamped` prova que o meu `final:true` chegou ao painel e foi honrado.**

Existe porque `redux_live.py` carimba `producer: "redux"` — o literal que
`app/panel/history-source.js:51 CANONICAL_PRODUCER` exige.

**DIVULGAÇÃO:** é o arquivo do dono e o áudio é uma **amostra sintética minha**, não fala dele.
**Decisão: MANTER** (apagar é uma linha para ele: `Remove-Item history\2026-10-07\14.md`). Reversível nos
dois sentidos.

### 10.5 Higiene pós-corrida — nenhum órfão

`_main/_e2e-orphan-check.ps1` (1 707 B, escrito como **ficheiro `.ps1`** porque um filtro de lista de
processos não pode usar a forma inline `-Command`) → `_main/_e2e-orphan-check.out` (330 B, rc=0):

- `ORPHAN-CHILD: pid 5588 is GONE -> GREEN`
- `ORPHAN-SCAN: no process command line mentions redux_live.py -> GREEN`
- `OWNER-PID 28428: alive name=pythonw cpu_s=200,0 rss_mb=101`
- `OWNER-PID 29008: alive name=python cpu_s=29.651,3 rss_mb=137`
- `SOTTO-FAMILY processes now: 1` → `pid 28428 name=pythonw.exe`

**Re-verificado no fim desta lane** (uma passagem de `Get-Process`, sem `Get-CimInstance` em loop):
`pid=29008 python cpu_s=31.413,1 rss=139 MB` e `pid=28428 pythonw cpu_s=210,4 rss=102 MB` — **vivos,
intocados**; nenhum processo com `redux_live.py`; e **todos** os 14 processos da família python com
`MainWindowHandle=0` (nenhuma janela visível).

**Divulgação de geração de processo:** o dono **reiniciou o app dele** entre medições — o worker dele é
agora `pid 29008` com `cpu_s≈31` e 139 MB, **não** o processo de 14853,7 CPU-s / 436 MB do censo anterior.
Os números de contenção antigos descrevem uma geração de processos que já não existe.

---

## 11. A regra "nunca deixar janela visível" — medida QUATRO vezes

| # | instrumento | cadência / contagem | resultado |
|---|---|---|---|
| (a) | `_main/redux-live-window-census.py` — worker nu | **100 ms**, 52 amostras | ARM A `child_visible=0`; ARM B outro-pid visível 52/52; controlo pré-spawn **23 janelas visíveis / 11 pids**; ARM C `python-family=[]` → GREEN; `VERDICT PASS` |
| (b) | **`--neg-arm`** do mesmo | 100 ms, 45 amostras | **ARM C `python-family=['14268:python']` → RED como exigido** ⇒ o verde do ARM C **não é vazio** |
| (c) | ARM C ganhou nome | — | o `pid 13748 (2 win) [""]` que ficou por explicar é **`explorer`** |
| (d) | **a corrida real do shell** (§10) | **100 ms, 345 amostras** | ARM A/B/C GREEN + `PANEL_SHOW_REFUSED`×2 + `PANEL_VISIBILITY_ON_SCREEN visible=false` |

A criança é lançada com `creationflags=CREATE_NO_WINDOW (0x08000000)`. **O controlo positivo não lança
uma consola real de propósito** — isso roubaria o foco ao dono.

**Regra respeitada:** `pythonw.exe` **ou** `creationflags 0x08000000`; **nada foi morto**; os pids
28428/29008 **nunca** foram tocados, com um stream a tocar.

---

## 12. Ficheiros criados — sha256 e tamanho de TODOS

Censo **fresco**, medido com `Get-FileHash -Algorithm SHA256` (32 hex mostrados; os hashes completos estão
no `.out` desta lane). **39 ficheiros presentes, 0 em falta, total 235 707 B.**

| bytes | sha256 (32) | caminho |
|---|---|---|
| 52471 | `b81612333ec6097726fbb6b8aaca26cf` | **`worker\redux_live.py`** ← a entrega |
| 13320 | `5e981228b087fdaf039521ea5affdca7` | `_main\e2e-redux-shell-arm.py` |
| 2338 | `0ee7bc97fa22a3147b6759b95d3ff5e9` | `_main\e2e-redux-shell-arm.out` |
| 11466 | `692883cfa362f7898e167ab712126513` | `_main\e2e-redux-shell.log` |
| 1707 | `24ae658a68be5c77bb0431343fb8de54` | `_main\_e2e-orphan-check.ps1` |
| 330 | `69e99bcfeb4e135b23a0f665ce6a7f13` | `_main\_e2e-orphan-check.out` |
| 11204 | `3ce1c931515af010fc9d1add0f8e3c97` | `_main\redux-live-window-census.py` |
| 1413 | `b48bd5ce88b105201590097265be2609` | `_main\redux-live-window-census.out` |
| 869 | `ef107b7f3937cad43c4f60efb9096880` | `_main\redux-live-window-census-neg.out` |
| 17537 | `b8cbc8ab7805d79206608912f89edac9` | `_main\redux-live-latency-probe.py` |
| 4568 | `56fa447d8d3f5a7ba617a94540285709` | `_main\redux-live-latency-onnx.jsonl` |
| 1261 | `cce6629c472ebde7df3c15834c03e82f` | `_main\redux-live-latency-onnx.out` |
| 1327 | `3eab015cfce42d6512414fb8412835be` | `_main\redux-live-latency-onnx-v2.out` |
| 2544 | `ca6073a83a36995c217cefc00cf62c8b` | `_main\redux-live-latency-ternary.jsonl` |
| 1332 | `2e365312ace190ae8eb1d464550e31ab` | `_main\redux-live-latency-ternary-v2.out` |
| 5961 | `da0e0f126d94b5eeb94e859f5e7a255b` | `_main\redux-live-arm1-recheck.py` |
| 1674 | `bee2224e3cb50ba93aec4a38e689f058` | `_main\redux-live-arm1-recheck.out` |
| 13663 | `6aea2480a83d94cbfaf100d324552206` | `_main\redux-live-contract-oracle.js` |
| 1850 | `67e9a68289d275e004e78e7975956044` | `_main\redux-live-contract-oracle.out` |
| 7500 | `77fdb957549c13ec0e1030df8e3be9fc` | `_main\redux-live-cost-attribution.py` |
| 3712 | `260379359bcfc5c82365057b0ed8952e` | `_main\redux-live-cost-attribution.out` |
| 0 | `e3b0c44298fc1c149afbf4c8996fb924` | `_main\redux-live-cost-attribution.err` |
| 15687 | `0c3759013081e2e956ed5774db9615c6` | `_main\redux-live-window-probe.py` |
| 1406 | `87a8a623557582785f6b60a9606ab283` | `_main\redux-live-window-probe.out` |
| 578 | `548959474c9cef2ba87ff5f5b28d487b` | `_main\redux-live-window-probe.err` |
| 5653 | `682ab5426f21bafbc2c03c39c143d17c` | `_main\redux-live-arm3.out` |
| 0 | `e3b0c44298fc1c149afbf4c8996fb924` | `_main\redux-live-arm3.err` |
| 2572 | `6914af35cae91601f6cd5fe1a8ee09d6` | `_main\redux-live-smoke.jsonl` |
| 1692 | `74318edbdb66b06be26180f2efeda66c` | `_main\redux-live-smoke.err` |
| 2693 | `e131036bcb934dcea7ceea6b23542448` | `_main\redux-live-noagc.jsonl` |
| 1309 | `df0d605d7b081014cbe632de8814483d` | `_main\redux-live-noagc.err` |
| 19168 | `968b2acff98ffef90ed98e3a2f59b340` | `_main\redux-gemm8-probe.py` |
| 6563 | `0dc5d0bb4d3ed4b57c82cc2bdbedc222` | `_main\redux-gemm8-probe.log` |
| 13765 | `9dd49370c0df1d291b8014c17a0359cf` | `_main\redux-engine-cost-probe.py` |
| 1554 | `27f00e37b5bf85496535f2a6a65e3b89` | `_main\redux-cost-onnx.log` |
| 1585 | `5be85be086f4eebefed150e2dc5c7c86` | `_main\redux-cost-ternary-cpu.log` |
| 2879 | `c7b040adcb09605c0b7d7f543a35f77a` | `_main\redux-cost-ternary-cuda.log` |
| 293 | `d57189eadfbf4b695873cbae517f0493` | `_main\redux-ptbr.txt` (oráculo, **cp1252**) |
| 263 | `e31f90f854401f95f5ec32604cbeaad1` | `_main\redux-en.txt` (oráculo) |

**Ficheiros que NÃO existem (divulgação, para ninguém os citar):**
- **`_main\redux-live-latency-ternary.out` — NÃO EXISTE** (`Test-Path` → `False`). A tentativa ternária
  pré-correcção escreveu **só** o seu `.jsonl`. Não citar.
- O próprio `receipt-redux-live.md` (este ficheiro) não está na tabela — é o produto, não um artefacto de
  medição; o seu tamanho/hash é o que se vê ao lado.

**Discrepância de 1 byte, declarada:** uma contagem aritmética anterior do **mesmo conjunto** deu
235 706 B; o censo fresco deu **235 707 B**. Não atribuo a diferença a nada — fica registada em vez de
escondida. O número válido é o fresco.

**`_main\` tem ficheiros de OUTRAS lanes que eu NÃO criei e NÃO reclamo:**
`redux-flag-gate.py` (23 337 B, sha256 `fcf83a05ed2ab5361840cf6453296544f30e67c6da9ba16a5169de2fcbaaf108`) e
`_main\_redux-gate-mutants\{verdict-counts-batch,switch-wired,stamp,env-optin}.py`;
`redux-long-probe.py` (31 047 B, sha256 `c7694fa13c666f55eb4710920d427a17c1f0287d48509f50cc81423d0979f135`);
`_main\_redux-visibility-probe.py`; `_main\receipt-redux-visibility.md`;
`_main\receipt-live-seam-verification.md`; `_main\receipt-battery-reds.md`; `_main\_ep-logs\_whelp.txt`.

---

## 13. Defeitos encontrados e corrigidos (com a prova de cada um)

| # | defeito | prova | correcção | estado |
|---|---|---|---|---|
| 1 | `lag = _t_wall − end` misturava `perf_counter()` (≈17300) com segundos de áudio ⇒ `+17299,22 s`, declive `nan` | `_main/redux-live-latency-onnx.out` | `lag = (_t_wall − origin) − end` | ✅ corrigido |
| 2 | **A janela NÃO era um tecto duro:** `window_s=10.10` apesar de `--window-s 5.0` | `WARN LIVE_STEP_OVERRUN … window_s=10.10` | `_drain_pending(limit=…)` + épsilon em `should_close` + `max_window_s` na telemetria | ✅ provado: v2 dá `maior janela 5.0s` |
| 3 | **`SOTTO_FILE_TAP` não era honrado** — `open_tap` chamava `worker.device_candidates(...)` directamente, e essa função **não lê a variável** (o worker ramifica em `sotto_worker.py:3374-3382`, ANTES da escada) ⇒ o meu motor abriria um endpoint REAL onde o worker de origem não abre nenhum, colidindo com o do dono | leitura do código | `tap_candidates()` + retorno de **5 valores** + saída antecipada `fatal_rc` | ✅ provado ponta-a-ponta (25 legendas, **nenhum** dispositivo aberto, nenhuma morte) |
| 4 | `TypeError: unsupported operand type(s) for /: 'str' and 'str'` no braço ternário ao vivo | job `pwsh-2732`, rc=1, 0 legendas, `model load failed:` | `redux_batch.load_runtime` é tipada `model_dir: Path`; passei `Path(model_dir)`. **`redux_batch.py` NÃO foi editado.** | ✅ provado por re-execução (job `pwsh-2783`, rc=0, `TRACKS-REAL-TIME`, 9 legendas) |
| 5 | `TypeError: 'Event' object is not callable` em `sampler.join()` | `_main/redux-live-latency-probe.py:240` | o `Sampler` fazia `self._stop = threading.Event()`, sombreando `threading.Thread._stop` → renomeado `self._halt` | ✅ |
| 6 | **Corrida ao vivo "verde" silenciosa:** `blocks=0, captions=0, verdict=no-captions, rc=0` | `done` do primeiro ensaio | `worker.FileTap` não faz nada até `tap.stream.start()`; `run_wav` passou a chamá-lo | ✅ |
| 7 | `KeyError: 0` em `arm_segmenter` | `redux-live-window-probe.py:254` | `transcribe.py:309` devolve um **dict** → helper com `.get("text")` | ✅ |
| 8 | `NameError: name 'np' is not defined` | idem | `import numpy as np` dentro do braço | ✅ |
| 9 | `UnicodeEncodeError: 'charmap' codec can't encode '\ufffd'` | stderr | `_utf8_streams()` com `reconfigure(encoding="utf-8", errors="replace", line_buffering=True)` | ✅ |
| 10 | `TEXT MATCHES ORACLE: False` num transcrito correcto | — | `_main/redux-ptbr.txt` é **cp1252**; `_oracle_text()` tenta UTF-8 e depois cp1252 | ✅ |
| 11 | `TypeError: function takes at most 5 arguments (6 given)` | `ternary_gemm_reference(..., threads=1)` | a assinatura de referência **não tem `threads`** — argumento removido | ✅ |
| 12 | Crash do bloco de impressão do probe | `min(fy)`/`mean(fy)` antes do veredicto `NO-CAPTIONS` | guardado por `if fy:` | ✅ |
| 13 | Chaves em falta na linha `WINDOW` | `KeyError` | `dones=[...]` / `done = dones[-1] if dones else {}` + seis `.get(...)` | ✅ |
| 14 | Oráculo imprimia `[PASS]` em braços de controlo que acabara de medir RED | — | passou a `ok: bRed` / `ok: cRed` incondicional | ✅ |

### 13.1 Defeitos DIVULGADOS e não corrigidos (de propósito)

- **`StepCounter` do `_main/redux-live-window-probe.py`:** o `__exit__` restaura **só**
  `decoder_joint.run`, **nunca** `encode`. A contagem de passos do encoder fica a contar para sempre.
  Não corrigi porque o número que uso dessa corrida (a tabela **contendida** de §6.3a) é `wall`, não passos.
- **`_main/redux-live-cost-attribution.py` usa `import transcribe as reference`** — o áudio vem do leitor
  do **ffmpeg**, **não** do caminho ao vivo (`soundfile` + `np.interp`). A tabela de §6.3b é sobre o
  **leitor de referência**; a curva de CPU-s por segundo de áudio é o que transporta.
- **Desvio no braço `ternary-cuda`:** `torch.get_num_threads() == 14`, não 2 — `_configure_cpu_threads`
  só aplica `cpu_threads` quando `device.type == "cpu"`. A linha da tabela está rotulada.

---

## 14. Divulgações de efeitos colaterais

1. **RE-BAIXEI `worker/models/parakeet-redux-onnx-int4/` depois de o dono ter mandado apagá-lo**
   (*"usa o de 179m. o outro deleta"*, 2026-10-07). **27 ficheiros / 436 066 441 B (415,87 MB)**,
   baixados em **~12,4 s**. Sem ele não há braço leve e a comparação de 6,3× não existiria.
   **Re-baixável a qualquer momento** com `hf download eschmidbauer/parakeet-redux-onnx`;
   **apagável outra vez** com um `Remove-Item`. O dono decide.
2. **`history\2026-10-07\14.md` (789 B)** — criado pela minha corrida ponta-a-ponta, com áudio sintético
   meu. §10.4. **Manter ou apagar é decisão dele.**
3. **`worker/models/parakeet-redux-reference/__pycache__\transcribe.cpython-311.pyc` (30 946 B)** — efeito
   colateral das **minhas** importações. O directório de referência passou de 3 para **4 ficheiros /
   143 104 B**. Inofensivo; apagável.
4. **`parakeet-redux-onnx-int4`: correcção de um número meu anterior.** Eu tinha dito "12 ficheiros"; o
   censo correcto é **27 ficheiros / 415,87 MB**.
5. **Censos dos directórios de modelo:** `parakeet-redux-onnx-int4` 27 ficheiros / 436 066 441 B (415,87 MB),
   topo `encoder-model.onnx` 343 841 943 · `decoder_joint-model.onnx` 72 552 270 · `vad-model.onnx`
   18 300 687 · `preprocessor.onnx` 1 224 294; `parakeet-redux-ternary` **17 ficheiros / 179 020 262 B
   (170,73 MB)** (`model.safetensors` 177 774 490, sha256 `78ec2573…`); `parakeet-redux-reference`
   4 ficheiros / 143 104 B.

---

## 15. Decisões tomadas sob autonomia (o dono saiu; regra de desempate)

Regra do agente pai: escolher a opção que **(a)** não perde trabalho, **(b)** é reversível,
**(c)** é medida — e registar a decisão e a razão.

| # | decisão | razão | reversibilidade |
|---|---|---|---|
| 1 | **Motor por omissão = `onnx` (ONNX int4)** | 6,3× mais leve em RAM (574,7 vs 3830,4 MB) e ~2,2× mais rápido, **texto byte-idêntico**; é o único braço neutro em fabricante | `--engine ternary` ou `SOTTO_LIVE_ENGINE=ternary` |
| 2 | **`--window-s 5.0 --step-s 2.0`** | medido: `step_s=1.0` deu **5/5 overruns**; `2.0` dá **0/14** e **0/5** com `backlog_s=0.00` | duas flags |
| 3 | **NÃO declarar o ternário motor ao vivo por omissão** (default pré-autorizado pelo agente pai) | 3,90 GB residentes e não distribuível; o dono testa e decide | uma flag |
| 4 | **Manter `history\2026-10-07\14.md`** | apagar destrói a única prova de que o feed canónico abre; manter é reversível | um comando |
| 5 | **Não editar `app/webview/README.md`** | é ficheiro de outra lane; a regra da casa é "cada lane edita os seus" | dívida declarada a quem o possui |
| 6 | **Não implementar a mudança no runner da lane irmã** (apontá-lo ao ONNX int4) | o ficheiro é deles; eu só reporto a opção (§17) | n/a |

**Precedência do interruptor dentro do motor:** `--engine` > `SOTTO_LIVE_ENGINE` > `onnx`; um valor
desconhecido **sai com 2**, nunca é coagido (a mesma disciplina do `--lang-id`).

---

## 16. O que NÃO foi provado (declarado, não omitido)

1. **O caminho de DISPOSITIVO ao vivo com o Redux.** Todas as medições usaram `--wav`/`SOTTO_FILE_TAP`
   porque **o worker do dono segura o endpoint** — abri-lo seria colidir com um stream a tocar. **O teste
   verdadeiro com dispositivo é do dono, com o app reiniciado.** O que herdei e está no código: a mesma
   selecção de dispositivo e o **mesmo tratamento de endpoint ocupado**
   (`_is_device_in_use` = `"8889000a" in text.lower()`, `DEVICE_IN_USE_RETRIES=3`,
   `DEVICE_IN_USE_WAIT_S=1.5`, `status/device-rotated`) — **lido de `sotto_worker.py:4051-4138`, herdado,
   mas NÃO exercitado num endpoint realmente ocupado por mim.**
2. **Áudio contínuo > ~30 s.** O WAV dá a volta, logo as fronteiras de segmento re-cobrem áudio. Não é o
   mesmo que 10 minutos de fala seguida.
3. **O ternário em CUDA dentro do processo AO VIVO.** Só o braço **batch** foi medido em CUDA.
4. **O `gemm8` empacotado do Photon.** Medido como **ausente** (§9); não refutado como possibilidade futura.
5. **Nenhuma medição de "incomódo" subjectivo.** Posso afirmar o custo (574,7 MB / 6,4 % dos núcleos;
   3830,4 MB no ternário). **Não posso afirmar que o dono não sente** — isso só ele sabe.

---

## 17. Notas cross-lane (correcções que NÃO me pertencem aplicar)

### 17.1 O bullet do `AGENTS.md` sobre o `producer` está FALSO — 16 correspondências, 3 ficheiros

O `AGENTS.md` afirma: *"**Nothing in the repo writes that field:** `grep -rn producer worker/` → **ZERO
matches**"*. **Re-executado hoje: 16 correspondências em TRÊS ficheiros.**

| ficheiro | linhas |
|---|---|
| `worker/redux_batch.py` | `:17`, `:189`, `:202` (`"producer": PRODUCER`, `PRODUCER = "redux"`) |
| `worker/sotto_worker.py` | `:2123`, `:2130-2131` (um comentário que **cita o zero obsoleto**), `:2134` (**`REDUX_PRODUCER = "redux"`**), `:2569`, `:2582` (`"producer": str(payload.get("producer") or REDUX_PRODUCER)`), `:2583` (`"producerModel"`), `:2620` (`"producer": REDUX_PRODUCER` em `redux-batch-empty`), `:3023` |
| `worker/redux_live.py` | `:290`, `:329`, `:532`, `:1070` (**meu**) |

O bloco `# ── THE PAYOFF ──` do caminho escondido (`sotto_worker.py:2555-2634`, com o carimbo em
`:2576-2586`) **carimba explicitamente** `producer` / `producerModel` / `final:True` / `route:"redux-batch"`,
com o comentário de que `app/electron/history-source.js:51,61-63` o exige e que *"uma linha de batch que
chegasse à transcrição sem ele seria recusada"*.

**Conta causal CORRECTA (e correcção da MINHA própria afirmação exagerada):** eu tinha escrito que
"`redux_live.py` é a primeira coisa no repositório a abrir o feed canónico" — **isso está errado como
afirmação sobre o repositório**. O feed estava vazio porque **nenhum dos dois caminhos que carimbam estava
ACTIVO no app do dono** (o runner batch é uma CLI cujo stdout só chega ao painel pelo interruptor de modo
escondido, que está **OFF** por omissão e precisa `SOTTO_REDUX_WHEN_HIDDEN=1` + reinício). O meu motor
carimba-o **por omissão**, e é por isso que a minha corrida é a **primeira escrita MEDIDA** — não a
primeira possível.

**Duas correcções a aplicar por quem possui os ficheiros (eu NÃO os edito):**
`AGENTS.md` (o bullet do zero) e `worker/sotto_worker.py:2131` (o comentário que repete o zero obsoleto).

### 17.2 Corroboração cruzada do orçamento de RAM (lane irmã, §7.1 do receipt deles)

`_main/receipt-redux-visibility.md:279-292`: o braço `fail` deles saiu 2 com
`RuntimeException: [ONNXRuntimeError] 6 : RUNTIME_EXCEPTION : … bad allocation` ao carregar o modelo de
streaming, porque outro processo (`redux-long-probe.py run --cases all --device cpu`, pid 17832) segurava
uma criança `redux_batch.py` sobre um WAV de 300 s a **3571 MB RSS**, deixando 3137 MB livres. Não
mataram nada; esperaram pela memória (19 GB livres) e repetiram → PASS. As palavras deles: *"**the real
runner's documented 3.9 GB peak happens while the streaming model (1.5 GB resident in the owner's live
worker) is still loaded — this switch does NOT unload it — and a sibling process was MEASURED failing to
allocate under exactly that load.** `--redux-when-hidden` with the real engine needs ~4 GB of transient
headroom here; that is the owner's call, not something this lane may tune away."*

**A minha medição independente concorda:** ternário ao vivo pico **3830,4 MB** vs ONNX int4 **574,7 MB**.
⇒ **Apontar o runner deles a um runner ONNX int4 removeria o risco de falta de headroom.**
**Fica como OPÇÃO declarada, NÃO implementada** — o ficheiro é deles.

### 17.3 Revisões sob teste (nomeadas, porque as lanes editam em paralelo)

| ficheiro | bytes | mtime | sha256(16) |
|---|---|---|---|
| `worker/sotto_worker.py` | 242 082 | 07/10/2026 13:09:59 | `64e7ec6f6c35c336` |
| `app/webview/sotto_webview.py` | 397 180 | 07/10/2026 13:09:59 | `ea014d8f2cacd72e` |
| `app/webview/run.cmd` | 9 928 | 07/10/2026 05:18:44 | `a5fc9c96a3c17b8d` |
| **`worker/redux_live.py`** | **52 471** | **07/10/2026 14:15:02** | **`b81612333ec60977`** |

`sha256(16)` = os primeiros 16 hex, que é exactamente o que o shell regista em `CODE_STATE`
(`worker_disk`/`worker_loaded`/`shell_disk`) — foi assim que a prova end-to-end se cruzou com o ficheiro.

---

## 18. Como o dono testa (o caminho mais curto)

```powershell
cd H:\sotto
.\app\webview\run.cmd --worker worker\redux_live.py        # Redux AO VIVO, ONNX int4 (leve)
# ... ele ouve, olha para o painel (Alt+C), decide ...

.\app\webview\run.cmd                                     # VOLTAR ATRÁS: nemotron 3.5 ao vivo
```

Para sentir o peso do ternário (a decisão é dele):

```powershell
.\app\webview\run.cmd --worker worker\redux_live.py --engine ternary
```

**Se quiser o motor leve e ainda não tiver o export:**
```powershell
hf download eschmidbauer/parakeet-redux-onnx   # 27 ficheiros, 415,87 MB, ~12 s
```

**Apagar a linha de história que a minha medição escreveu:**
```powershell
Remove-Item H:\sotto\history\2026-10-07\14.md
```

---

## 19. Ligação à ATRIBUIÇÃO (as licenças exigem, não proíbem)

`moondream/parakeet-redux` ← `nvidia/parakeet-tdt-0.6b-v3`, ambos **CC-BY-4.0**.
Export ONNX: `eschmidbauer/parakeet-redux-onnx` (revisão `1c285ba7…`), **CC-BY-4.0**.
O motor carimba `producer:"redux"` e `model:"onnx-int4"`/`"ternary"` em cada legenda, e o cabeçalho de
`redux_live.py` traz a atribuição completa. **Exige atribuição; não proíbe uso.**

---

*Receipt da lane `redux-live`. Todos os números acima foram medidos nesta máquina nesta sessão; onde um
número é uma crença em vez de uma medição, o texto di-lo. O dono decide.*
