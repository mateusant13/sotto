# Recibo — trade-offs do WORKER (`worker/sotto_worker.py`)

**Lane:** `_tradeoff-worker` · **data:** 2026-10-13 15:2x -03:00
**Alvo:** `H:\sotto` (arvore do produto). **Nada foi editado** — so este recibo.

## Pin do sujeito (re-medido agora, regra 2 de `AGENTS.md`)

`worker/sotto_worker.py` = **333 008 B / 6 306 linhas / 6 305 CRLF / 0 LF isolado,
sha256 `ba853e0b3077aefa6f179b993325b1df9d58e898818798f9368f944d14551d92`,
mtime 2026-10-12 21:42:06.015Z** (instrumento: `node` sobre os bytes +
`crypto.createHash('sha256')`). E o mesmo ~333 KB do briefing.
`grep -n deliberate` devolve **13**, nao 20 — ver §2.

## Regras duras respeitadas

* **Nada lancado.** Nenhuma app, nenhum shell, nenhum worker. Todos os instrumentos deste
  recibo sao **em processo** (`import sotto_worker` num filho `py -3` que nunca abre
  `sotto_webview.py`, `run.cmd`, nenhum tap e nenhum `StreamAsr`) ou **leituras de disco**.
  `$env:TMPDIR="I:/cc-tmp"` em todas as execucoes.
* **Nada editado no produto.** So este ficheiro.
* **Medido antes de afirmado.** Tudo o que tem numero foi medido nesta sessao, excepto onde
  digo **ARTEFACTO** (ja estava no disco e nomeio o ficheiro) ou **UNMEASURED**.

---

## 1. TL;DR — o que o Lead tem de saber antes de aplicar

1. **O custo por chunk do worker, fora do modelo, e de 164 us e nao vale a pena otimizar.**
   Medido com o GC desligado: `on_block` 24,4 us + meter 3,1 us + gate 30,5 us + AGC 105,8 us
   + `LineFormer.push` 3,2 us + poda 0,3 us = **163,8 us por chunk de 560 ms**. Sobre o custo
   do modelo no run do dono (607,54 s para 25 550 chunks) isso e **0,6 %**. Nao ha aqui
   nenhum "trabalho por iteracao a mais" de monta. A otimizacao obvia (float32 em vez de
   float64 no `sumsq`) poupa 0,28 s em 4 h — nao vale mexer nos digitos do `rms`.
2. **O unico custo por segmento que DOBRA a maquina e a segunda passagem (M3).**
   No run do dono: `infer_wall_s=607.54`, `rerun_wall_s=628.66` -> a segunda passagem custa
   **103,5 % de toda a inferencia ao vivo** (quatro artefactos independentes: 0,89x, 0,84x,
   1,06x, 1,04x). O run passa de RTF 0,0425 para **0,0864** — 2,03x. E a auditoria do proprio
   projecto (`docs/audit/ao-vivo-vs-redux.md` §6.3) diz que re-decodificar com o **mesmo
   checkpoint** nao corrige o erro, so o corte — e o corte ja e entregue pelo M2. O §7.2 do
   mesmo doc dizia "o custo real da 2a passagem" **UNMEASURED**. Esta agora medido: nao paga
   o que gasta.
3. **A resposta a "o que ainda se regista demasiado?" e: nao e o worker.** No log do dono
   (`_main/webview-run.log`, 16,78 MB), **79 221 de 112 551 linhas (70,4 %)** sao do SHELL
   (`PANEL_SURFACE` 30 652, `WINDOW_GEOMETRY` 30 649, `PANEL_VISIBILITY_WRITE_FAILED`
   17 890). O worker so escreve `WORKER_STATS` a 0,1 Hz (`statsPushes=1502` no run de 4 h).
   O que o worker ainda empurra demais e o **meter**: 145 969 eventos, ~87,6 % deles sobre
   silencio digital (ver T-09).

---

## 2. Os trade-offs, um a um

Formato: **(1)** a linha exacta e o que afirma · **(2)** o que COMPRA · **(3)** o que CUSTA,
medido · **(4)** VEREDICTO · **(5)** a mudanca concreta e a prova, se MELHORAR.

### T-01 · `PREFERRED_DEVICES = ()` — a lista de dispositivos vazia

1. **`:103`**: a lista shipped e vazia e a correspondencia e heuristica. O comentario
   (`:83-103`) afirma que um nome literal descreve o encaminhamento de uma pessoa e que a
   MME trunca nomes em 31 caracteres.
2. **COMPRA:** universalidade — o produto funciona numa maquina sem VB-Cable. O ladder
   (rung a = WASAPI loopback de todos os endpoints de render activos; b = heuristica por nome;
   c = `--device` explicito; p = uma arvore de processo).
3. **CUSTA:** quando o primeiro candidato esta morto, cada candidato custa ate `TAP_WINDOW_S`
   = 6 s (`:218`) mais o backoff do ladder (`:5958`, 1 s a duplicar ate 8 s). **MEDIDO no run
   do dono: zero `device-rotated`, zero `reason=flat`** (`STATUS_APPLIED` sao 469 linhas,
   todas `"Receiving captions"`; 1 819 legendas entregues do primeiro candidato). O custo
   teorico nao foi pago nenhuma vez.
4. **VEREDICTO: MANTER.** A compra e medida (0 rotacoes em 4 h, 1 828 legendas); o custo, zero
   no caminho real.

### T-02 · `TAP_PEAK_FLOOR = 0.002`

1. **`:219`**, com a CORRECAO de 2026-10-06 em `:216-217` e a medicao em `:197-200`. O floor
   separa MORTO de RENDERIZADO e nada mais.
2. **COMPRA:** um tap que abre mas nao ouve diz `silent-device` / exit 3 em vez de culpar o
   modelo (`:4131-4132`, `:6005-6010`).
3. **CUSTA:** uma comparacao por bloco (`:4975`) e a constante. Nada por chunk.
4. **VEREDICTO: MANTER.** O comentario da correcao ja refuta a objecao obvia (o floor 0,101929
   era audio renderizado real, nao um idle floor — medido em `_main/sdr_idlefloor.out`).

### T-03 · "uma legenda assenta o ladder"

1. **`:5734` `if counters["captions"] > caps_before:`** — o teste de aceitacao; e `:5736`
   `elif dev.get("rung") == "fallback" and device_peak["value"] >= tap_floor:` para a
   re-entrada.
2. **COMPRA:** um floor nao prova fala; so uma legenda assenta o ladder. Evita o run que
   "assentou no primeiro nao-morto" e depois reporta `captions=0`.
3. **CUSTA:** uma leitura de contador por iteracao do laco da janela (20 Hz, ver T-16) — nao
   por chunk.
4. **VEREDICTO: MANTER.**

### T-04 · `lang_id` por omissao `auto`

1. **`:4535` `THE DEFAULT IS auto, NOT os`**, e `:511` `There is deliberately NO literal 0`
   no construtor. Precedencia `--lang-id` > `SOTTO_LANG_ID` > config > auto (`:4555-4562`).
2. **COMPRA:** nao destruir um idioma por silencio — em pt-BR, `os` resolvia para 12 e o
   sample ingles colapsava de 94 para 10 tokens; `auto` deu 89/94 e 18/18 (`AGENTS.md`).
3. **CUSTA:** resolucao **uma vez** por run, antes do `_add_cuda_dll_dirs()` (`:4552-4553`).
   `self.lid` e um array fixo (`:585`) passado em cada chamada do encoder — **zero custo por
   chunk**. Verificado: `config.json` tem `model.lang_id = "auto"`.
4. **VEREDICTO: MANTER.**

### T-05 · `use_vad` por omissao `true`

1. **`:4609`** com a explicacao da ordem da API em `:4600-4608`; `use_vad:false` e honrado
   pelo `set_option`, nao por construir um processador sem VAD (`:676-677`).
2. **COMPRA:** e um **poupador por chunk**, nao um custo. Quando o Silero retem um chunk,
   `sp.process()` devolve `None` e o encoder nunca e chamado (`:822-828`).
3. **CUSTA:** quando a VAD retem, a saida antecipada ainda conta o tempo — custo ~0. **MEDIDO
   no run do dono: `music_gated_chunks=23130` de `chunks=25550` (90,4 %) +
   `vad_gated_chunks=160`** -> o encoder so correu 2 420 vezes em 4 h. O gate e a razao pela
   qual o worker aguenta 14 308 s de audio em 607 s de inferencia.
4. **VEREDICTO: MANTER.**

### T-06 · o gate fala/musica

1. **`:4666-4682`** (activo no ramo vivo por omissao); a decisao e **pre-ganho**
   (`:5352-5358`) e `run_chunk` nao decide segunda vez em audio pos-ganho (`:792-796`).
2. **COMPRA:** isolar fala de musica/drone; um chunk nao-fala nunca chega ao encoder
   (`:784-803`).
3. **CUSTA:** `SpeechMusicGate.is_speech` = **30,5 us por chunk** com fala, **29,4 us** em
   silencio digital (medido, GC off). Nao ha caminho rapido para silencio — o numpy paga o
   mesmo. 0,13 % do tempo do modelo.
4. **VEREDICTO: MANTER.** Nao ha o que cortar; a decisao tem de ser por chunk.

### T-07 · o AGC (`AutoGain`), aplicado so a fala

1. **`:1172-1208`** (a ordem: decidir primeiro, ganhar depois) e `:5359-5362`.
2. **COMPRA:** uma fonte quieta transcreve em vez de dar verde com zero legendas (`:1173-1186`:
   quiet `peak=0.100510` -> 0 legendas; normal -> 5).
3. **CUSTA:** **105,8 us/chunk com fala, 44,1 us sem fala, 34,5 us em silencio digital**
   (medido, GC off). A ordem faz o custo ser proporcional a fala — o design funciona como foi
   anunciado. 0,46 % do tempo do modelo.
4. **VEREDICTO: MANTER.**

### T-08 · `join_fragments` e o unico lugar que decide um separador

1. **`:2898` `It is deliberately the ONLY place that decides a separator`.
2. **COMPRA:** a cura do "shi t" do dono — uma fronteira de chunk nao e uma fronteira de
   palavra; e `line()` e o *lookahead* de `max_chars` medem a mesma linha real (`:3073`).
3. **CUSTA:** ha **2 call sites** de `join_fragments` dentro de `push` (o lookahead e o
   `line()`) — a linha e juntada duas vezes por chunk. **MEDIDO: `LineFormer.push` = 3,16 us
   medio, p95 4,9 us, max 24,1 us** (GC off, 600 pushes). A linha e limitada por
   `SENTENCE_MAX_CHARS = 90` (`:2935`), portanto o segundo join e O(90) e nao O(n^2) — nao
   ha armadilha de crescimento.
4. **VEREDICTO: MANTER.**

### T-09 · o nivel do meter, um evento por bloco

1. **`:4997-5010`** — "NO log line per block ... a per-block line here is exactly what would
   make the owner log grow with the audio", e depois, mais abaixo, o **proprio** evento
   `emit(type="meter", peak=..., blocks=...)` a cada janela fechada (`:5007-5010`).
2. **COMPRA:** a onda do painel: um pico **por janela**, reposado a cada *tick*, a ~10 Hz.
3. **CUSTA (medido):**
   * `AudioMeter.tick` = 0,56 us/bloco -> 0,06 s em 144 191 blocos. Irrisorio.
   * `json.dumps` do evento = **1,39 us** -> 0,20 s. Irrisorio.
   * **Mas o VOLUME nao e irrisorio.** `blocks_per_window = 1` (10 Hz / 100 ms), por isso o
     worker emite um evento por bloco aconteca o que acontecer. **No run do dono:
     `meterPushes=145969`** (contador do shell na linha `SHELL_EXIT`), com
     `nonzero_blocks=17850` de `blocks=144191` — **87,6 % (126 341) dos blocos sao silencio
     digital**, e portanto ~87,6 % dos eventos de meter carregam `peak < 1e-4`, na maioria
     exactamente `0.0`. A taxa sustentada medida nas janelas `BRIDGE_METER` do shell foi
     **9,83 Hz**.
   * O custo do outro lado do cano (leitura do pipe, parse, dispatch JS, repintar a onda) e do
     shell — **UNMEASURED por mim**.
4. **VEREDICTO: MELHORAR — prioridade BAIXA.** O padrao e o mesmo que a correcao de hoje
   (`panel.js:1913` / `panel_state.py:78`): trabalho por iteracao que podia ser por
   **transicao**.
5. **Mudanca concreta:** quando N janelas consecutivas fecharem com `peak == 0.0`, baixar a
   cadencia para 1 Hz e restaurar os 10 Hz na primeira janela nao-nula. Para a onda nao ficar
   colada no ultimo valor, a primeira dessas janelas tem de sair com `peak=0` (o painel
   desenha zero, que e o que desenharia), e o relogio de `blocks` tem de continuar a fechar
   para que um canal continue a ver-se no `blocks`.
   **Prova de que nao quebra nada:** novo braco em `_main/meter-chain-oracle.py` /
   `_main/audio-meter-oracle.py` a afirmar (a) 3 janelas a zero -> a 4.a suprimida, (b) a 1.a
   janela nao-nula volta a emitir a 10 Hz, (c) `--meter-hz 0` continua byte-identico (braco
   existente no oracle ja cobre isto), (d) `stats.blocks` continua a reflectir um canal.

### T-10 · a segunda passagem M3 sobre o segmento fechado  <- **o achado principal**

1. **`:5045 def rerun(closed)`**, chamada de `finalise()` (`:5140`) <- `drain()` (`:5163`) <-
   `publish_captions()` **dentro do thread `asr_thread`** (`:5184-5391`). Cada linha fechada
   re-decodifica **todos** os chunks do seu segmento com `account=False` (`:5120`), depois de
   `reset_stream_state()` (`:5115`) e de um `fresh_processor()` (`:5105`).
2. **COMPRA:** que o texto `final:true` seja decodificado sobre uma **frente nova** com o
   segmento inteiro, e nao contra uma frente que ja viu o segmento. Em teoria evita o corte a
   meio de palavra no ultimo chunk.
3. **CUSTA (medido, artefactos):**

   | artefacto | `chunks` | `infer_wall_s` (viva) | `reruns` | `rerun_wall_s` (2.a) | razao |
   |---|---|---|---|---|---|
   | run do dono `_main/webview-run.log` | 25 550 | **607,54** | 231 | **628,66** | **1,035** |
   | `_main/_live-seam-en.err` | 24 | 2,93 | 3 | 2,62 | 0,894 |
   | `_main/_redux-visibility/on.stderr.log` | 34 | 6,97 | 4 | 7,35 | 1,055 |
   | `_main/_redux-visibility/real.stderr.log` | 45 | 8,70 | 4 | 7,30 | 0,839 |

   No run do dono: 607,54 + 628,66 = **1 236,20 s, dos quais 50,9 % sao a segunda passagem**;
   `audio_s=14308` -> RTF passa de **0,0425** para **0,0864** (**2,03x**). A corrida acontece
   **no thread da ASR**, portanto durante uma re-decodificacao de linha nenhum chunk vivo e
   decodificado e a fila `audio_q` continua a receber blocos.
   **E a compra nao esta demonstrada:** em `_main/_worker-fixed.out` os 5 `final` diferem do
   ultimo parcial da mesma `start` em **5 de 5** — e as duas versoes sao igualmente
   palavra-salada. `docs/audit/ao-vivo-vs-redux.md` §6.3 diz, do mesmo projecto:
   *"re-decoding nao corrige \"Going alo slas\" para \"Going along slushy\""* e *"Chega para
   tirar o CORTE — sim ... Nao precisa de modelo novo"* — o corte e o que o M2 (`_close` /
   `take_closed`, `:3028`) ja entrega. O §7.2 do mesmo doc lista *"O custo real da 2a
   passagem"* como **UNMEASURED**; esta agora medido e ~1x a inferencia inteira.
   **A nota que fecha o argumento:** `finalise()` (`:5156`) ja tem o *fallback*
   `ev["text"] = text or ev.get("text")` — ou seja, **sem a segunda passagem o `final` leva o
   texto da transmissao, que e exactamente a ultima string parcial que o dono ja leu**. O
   caminho alternativo ja existe e ja e exercitado (e o que corre quando o audio do segmento
   ja nao esta retido, `:5071-5096`).
4. **VEREDICTO: MELHORAR** (com a opcao de REMOVER se o dono preferir zero complexidade). A
   segunda passagem deve ser **opt-in**, nao shipped.
5. **Mudanca concreta:** um botao `model.second_pass` (config) + `--no-second-pass` (flag),
   precedencia flag > env > config > **`false`**, lido uma vez em `main()` ao lado de
   `output.partial`. `finalise()` so chama `rerun(closed)` quando o botao esta ligado; quando
   esta desligado devolve `ev` com o texto da transmissao — **o mesmo caminho de fallback de
   `:5156`, ja provado**. `reruns` / `rerun_wall_s` ficam a 0 e a linha `WORKER_STATS` mantem
   os campos (byte-identica).
   **Como se prova que nao quebra nada:**
   * `_main/segment-rerun-probe.py` continua verde nos bracos A/A2/C/C3 com o botao ligado (a
     isolamento estado-vivo/passagem nao muda).
   * Braco novo: com o botao desligado, para cada `start`, `final.text === ultimo parcial com
     esse start` (relacao que hoje e quebrada em 5/5), e `reruns=0`, `rerun_wall_s=0`.
   * `_main/caption-lines-oracle.py` continua verde (M2 e o canal parcial nao sao tocados).
   * `done.verdict` continua `captions-emitted` (`decide_verdict` le `counters['captions']`,
     nao os reruns) e o exit code nao muda.
   * Efeito esperado no run do dono: inferencia total de **1 236 s -> 607 s** (RTF
     **0,0864 -> 0,0425**).
   * `--redux-when-hidden` e `--redux-live` sao ortogonais e ficam iguais.

### T-11 · `counters["sumsq"]` em float64 por bloco

1. **`:4979`** `counters["sumsq"] += float((block.astype("float64") ** 2).sum())`, dentro de
   `on_block` — o caminho que a propria lane jurou nao tornar numa linha por bloco
   (`:4997-5000`).
2. **COMPRA:** o `rms` da linha `WORKER_STATS` (`:4930`) com acumulacao exacta.
3. **CUSTA:** **4,35 us por bloco** (so o `astype` sao 0,80 us; o quadrado+soma float64 e o
   resto). Em 144 191 blocos = **0,63 s em 4 h**. A alternativa float32
   (`float(np.dot(blk, blk))`) mede **2,40 us** -> pouparia 0,28 s.
4. **VEREDICTO: MANTER.** 0,1 % do tempo do modelo; a alternativa muda os digitos do `rms`, que
   e um numero que os bracos de controlo comparam.

### T-12 · a passagem em lote off-thread

1. **`:3432` `THE BATCH PASS IS OFF-THREAD, and deliberately`.
2. **COMPRA:** a transmissao nunca e bloqueada pelo motor batch; o writer unico do JSONL
   mantem-se (`:3441`); um snapshot por execucao (`:3593-3600`).
3. **CUSTA:** hoje, **zero**: `REDUX_WHEN_HIDDEN_DEFAULT = False` (`:3150`) e
   `REDUX_LIVE_DEFAULT = False` (`:3219`) -> `switch is None`, `overlay is None`, e cada site e
   guardado por `if switch is not None` (`:5288`, `:5469`...). Quando ligado, o custo por bloco
   e **O(1) amortizado**: `add_audio` = lock + append (`:3573-3588`). **MEDIDO:** o aparo da
   lista (`list.pop(0)` sobre os 1 200 blocos de `REDUX_MAX_AUDIO_DEFAULT_S=120`) custa
   **13,3 us por bloco** — o mesmo que um `deque` (14,9 us), portanto **nao vale trocar o
   tipo**; e o `np.concatenate` de 120 s de audio custa 4,7 ms **por kick** (um a cada 15 s).
4. **VEREDICTO: MANTER.** Inerte por omissao e barato quando ligado.

### T-13 · a coercao dentro de `decide_verdict`

1. **`:4102 def _as_int`**, com `:4096-4101` a explicar porque vive la: os gates fazem `exec`
   do texto da funcao e um helper de modulo daria `NameError`.
2. **COMPRA:** a funcao ser total — `captions='0'` (string) anunciava `captions-emitted`, e
   `chunks='0'` rebentava com `TypeError` em vez de dar um `done`.
3. **CUSTA:** uma dict comprehension de 9 chaves **uma vez por run** — `decide_verdict` tem
   **um unico call site** (`:6018`), no fim. Ordem de us.
4. **VEREDICTO: MANTER.** Nao ha caminho mais barato que ja nao seja este.

---

## 3. O que ainda se regista / empurra demais (a pergunta do briefing)

* **Shell, nao worker.** `_main/webview-run.log` (16 783 779 B, 112 551 linhas):
  `PANEL_SURFACE` 30 652 (30,5 % dos bytes), `WINDOW_GEOMETRY` 30 649 (32,5 %),
  `PANEL_VISIBILITY_WRITE_FAILED` 17 890 (19,5 %). **79 221 linhas / 70,4 %** do ficheiro sao
  do shell. Isto e para lancar as lanes do shell — eu nao meco la.
* **Worker, o que sobra:** `WORKER_STATS` a `--stats-interval 10` s = 0,1 Hz ->
  `statsPushes=1502` no run de 4 h (contador do shell em `SHELL_EXIT`). Duas chamadas de
  `stats_line` no codigo (`:5718`, `:5998`). **MANTER.**
* **Worker, o que empurra demais:** 145 969 eventos de meter a 9,83 Hz sustentado, 87,6 %
  deles sobre silencio digital -> **T-09**.
* **Os contadores do shell dao o denominador** para quem reabrir o log: `SHELL_EXIT` do run do
  dono = `spawns=7, captions=1919, statuses=187, malformed=0, statsPushes=1502,
  statsReplies=14647, meterPushes=145969, rc=1`. `statsReplies` (14 647) e ~10x
  `statsPushes` — outra linha para a lane do shell.

---

## 4. O que eu NAO consegui medir (e porque vale mais que um palpite)

1. **O custo por chunk do modelo em si** (encoder/decoder/joint em ms). Exige carregar o
   `StreamAsr` (~1 GB, GPU/CPU). **Nao carreguei**: o briefing proibe lancar seja o que for e
   um load do modelo na maquina do dono e exactamente o tipo de coisa que ele leu como
   *"travando meu pc"*. O que tenho e derivado dos artefactos: `infer_wall_s/chunks` no run do
   dono = 23,8 ms por chunk (todos) ou 251 ms por chunk **caminhado** (2 420 de 25 550).
2. **Quanto do custo da 2.a passagem e `fresh_processor()` vs re-decodificacao.** A
   consistencia das quatro razoes (0,84x-1,06x ~= 1x a inferencia viva, e ~250 ms por chunk
   re-decodificado, igual ao vivo) aponta para "e a re-decodificacao, nao o setup" — mas a
   separacao precisa de um run com o modelo. **UNMEASURED.**
3. **O custo do outro lado do cano** (leitura do pipe, parse, dispatch, repintura) para os
   145 969 eventos de meter e os 1 919 de legenda. E do shell. **UNMEASURED.**
4. **Se a 2.a passagem causou os `queue_drops=1118`** do run do dono. Durante uma
   re-decodificacao de 2,72 s a 10 blocos/s chegam ~27 blocos, muito abaixo dos 256 da fila —
   portanto **nao atribuivel por medicao**, e nao afirmo que seja.
5. **A escada completa (rung p / PLP).** Nao abri nenhum tap, logo nao medi o custo do poll de
   5 ms do `ProcessLoopbackTap` em condicoes reais. O que me diz respeito directamente esta em
   T-15.

---

## 5. Achado lateral, barato e verificavel: o laco usa `time.sleep` onde o proprio ficheiro
manda `stop.wait`

O comentario de **`:5956`** diz *"`stop.wait` (never time.sleep) so `stop` and
--max-seconds still answer at once"* — e e ele que cumpre (`:5958 stop.wait(...)`). Mas
**tres** sites do mesmo laco usam `time.sleep`: **`:5786`**, **`:5842`** (ramos
`endpoint-idle` / stall) e **`:5847`** (o laco assente, a 20 Hz). Consequencia: `--max-seconds`
e um `stop` so respondem no proximo *tick* (ate 50-100 ms depois) nesses tres ramos, e um ramo
que fica preso em `time.sleep` nao ve o `stop` — o mesmo risco que a casa ja documentou para
`--exit-after`.

**VEREDICTO: MELHORAR — trivial.** Trocar os tres `time.sleep(0.1/0.1/0.05)` por
`stop.wait(0.1/0.1/0.05)` (mesma cadencia, mesma semantica, nenhum comportamento novo).
**Prova:** `_main/rotation-burst-monitor.py` ou um oracle com `--max-seconds`, medindo o tempo
entre o `stop` e o `done` nos tres ramos (arm A: antes, medir o atraso; arm B: depois, zero);
o ramo `endpoint-idle` tem de continuar a nao reabrir (`reopens=0`).

---

## 6. Padroes do tipo do bug de hoje (JS<->Python) encontrados no worker

| padrao | onde | estado |
|---|---|---|
| trabalho por iteracao que podia ser por transicao | meter a 10 Hz sobre silencio (T-09) | **MELHORAR, baixa** |
| trabalho por segmento que refaz todo o trabalho por chunk | 2.a passagem M3 (T-10) | **MELHORAR, alta** |
| poll que podia ser evento | `time.sleep` em vez de `stop.wait` (§5); poll WASAPI de 5 ms (T-15) | **MELHORAR, trivial / baixa** |
| escrita que devia ser rara | nada no worker: `err()` so a 0,1 Hz + eventos | MANTER |

### T-15 (fechado) · o poll WASAPI/PLP de 5 ms

`worker/sotto_worker.py:2473-2478` e `worker/wasapi_loopback.py:962-983` usam
`period = min(0.005, max(0.001, block_ms/1000/20.0))` = **5 ms**, um poll puro (nao ha
`SetEventHandle` em lado nenhum — verificado por grep). **MEDIDO:** um laco de
`time.sleep(0.005)` corre a 178 Hz e consome **0,62 % de um nucleo** continuamente. No run do
dono, o endpoint passou 87,6 % do tempo sem renderizar nada — ou seja, ~0,6 % de um nucleo
(~1,5 min de CPU em 4 h) gasto a perguntar "ha pacotes?" a um endpoint calado.
**VEREDICTO: MELHORAR, prioridade BAIXA.** A alternativa e a documentada
`IAudioClient::SetEventHandle` + `WaitForSingleObject`, mantendo o poll so como
*timeout*/rearme. **Risco e porque e baixo e nao medio:** com eventos, o anel tem de aguentar o
que chega entre dois eventos; nao o posso medir sem um endpoint vivo (o dono proibiu lancar), e
um transbordo do anel perde audio em silencio. Instrumento para quem o fizer:
`_main/tap-wait-oracle.py` com um endpoint calado e um a renderizar, medindo (a) 0 pacotes
perdidos, (b) 0 % de nucleo no calado, (c) a cadencia de blocos mantida a 10 Hz.

---

## 7. Como refutar este recibo

```bash
# 1. O pin. Se o worker mexeu, todos os file:line daqui sao HINT (regra 2 de AGENTS.md).
node -e "const fs=require('fs'),c=require('crypto');const b=fs.readFileSync(
  'H:/sotto/worker/sotto_worker.py');console.log(b.length,
  c.createHash('sha256').update(b).digest('hex'))"
#   espera-se: 333008 ba853e0b3077aefa6f179b993325b1df9d58e898818798f9368f944d14551d92

# 2. A segunda passagem custa ~1x a inferencia viva (o achado principal).
grep -o "reruns=[0-9]* rerun_wall_s=[0-9.]* audio_s=[0-9.]* infer_wall_s=[0-9.]*" \
  H:/sotto/_main/webview-run.log

# 3. Os 3 time.sleep que o proprio ficheiro manda trocar.
node -e "const l=require('fs').readFileSync('H:/sotto/worker/sotto_worker.py','utf8').
  split(/\r?\n/);[5786,5842,5847].forEach(n=>console.log(n,l[n-1].trim()))"

# 4. O meter e um evento por bloco, e 87,6% dos blocos sao silencio.
grep -o "meterPushes=[0-9]*" H:/sotto/_main/webview-run.log
grep -o "blocks=[0-9]* .*nonzero_blocks=[0-9]*" H:/sotto/_main/webview-run.log | tail -1

# 5. O fallback que torna T-10 barato de implementar ja existe.
node -e "const l=require('fs').readFileSync('H:/sotto/worker/sotto_worker.py','utf8').
  split(/\r?\n/);console.log(l[5155])"
```

---

## 8. Instrumentos usados nesta sessao (todos em processo, nenhum lanca nada)

`import sotto_worker` + `perf_counter` com **GC desligado**, 200 aquecimentos e 5 000-40 000
repeticoes por medicao; `node` sobre os bytes do worker e dos logs. Nenhuma escrita fora
`I:\cc-tmp` e este recibo. Nenhum processo do dono foi tocado.
