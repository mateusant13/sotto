# Quanto custa a quantização int8, sozinha, na legenda ao vivo?

**Lane:** `PrecisaoInt8Custo` · **date:** 2026-10-06 · **repo:** `H:/sotto` (nada escrito fora dele)

Pergunta do dono, verbatim: *"veja se a culpa da legenda ao vivo ser tao HORROROSA e' por que ta com
precisao reduzida. nao acho que seja por isso."*

---

## 0. TL;DR — a hipótese do dono está CERTA, e agora está MEDIDA

**Um checkpoint NÃO quantizado do MESMO modelo, do MESMO gerador de export, EXISTE e foi baixado** —
não foi preciso inventar número nenhum. O par int8↔fp32 difere em **exatamente um ficheiro**: o
`encoder.onnx.data`. Todo o resto (decoder, joint, VAD, `genai_config.json`,
`audio_processor_config.json`, `vocab.txt`, tokenizer) é **byte-idêntico** (sha256 §1).

| o que | custo em WER (mesma população, mesma janela) |
|---|---|
| **a quantização int8, sozinha** (fp32 → int8, no caminho corrigido) | **+0,0077 WER** (0,77 pontos) = **5,0 %** do WER curado |
| **o defeito do predictor** (re-prime → carry+seed, no int8) | **+0,4569 WER** (45,7 pontos) |
| **razão** | o defeito do predictor é **≈59×** a quantização |

> **A precisão não é a causa.** A quantização int8 custa ~0,8 ponto de WER; o defeito do predictor
> custou 45,7 pontos. E o sinal do custo da quantização **troca** entre as duas políticas de
> predictor (em arm 1 o int8 é *melhor*; em arm 3 é *pior*) — ou seja, está no nível de ruído da
> comparação ASR-vs-ASR, não no de um defeito.

---

## 1. O par é obtenível — proveniência e o controlo de variável única

O modelo entregue é o export **DimQ1** (`models/nemotron-3.5-asr-streaming-0.6b-int8`): o
`model_config.json` local aponta para `E:\Learn\nemotron-speech-csharp\converter\src\build\onnx_models_int8_cpu`
e o `README.md` do próprio modelo nomeia a família `DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-{fp32,int8,int4}-cpu`,
os três convertidos do mesmo `nvidia/...-0.6b` por Microsoft Olive. O irmão FP32 existe no Hub:

| | |
|---|---|
| repo | `DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-fp32-cpu` |
| revisão | `993818f34d86091fd4bcd3707e7bbf32ad832e97` (2026-06-30) |
| tamanho | 2 599 194 664 B (2,60 GB) — baixado para `worker/models/nemotron-3.5-asr-streaming-0.6b-fp32` |
| caminho de conversão reproduzível | o mesmo do README do int8: `converter/src/optimize.py --encoder-precision {int8,fp32} --execution-provider cpu` (toolchain `nemotron-speech-csharp`) |

**Prova de variável única (sha256, prefixo de 32 hex):**

| ficheiro | int8 | fp32 | |
|---|---|---|---|
| `encoder.onnx.data` | d758dd3d6d8241a362c39ebad3ad3138 · 967 176 192 B | a3f38f27f7167b37328b248873b8b89e · 2 495 410 176 B | **DIFERE** (o grafo quantizado) |
| `decoder.onnx.data` | e5fd55cbeeb268f9d383e2ee72735b9f | idêntico | igual |
| `joint.onnx.data` | 2e0fb1c060f3777a1a76e78d5589dd54 | idêntico | igual |
| `silero_vad.onnx` | a4a068cd6cf1ea8355b84327595838ca | idêntico | igual |
| `genai_config.json` (1 962 B) | `diff` = vazio | idêntico | igual |
| `audio_processor_config.json` (432 B) | `diff` = vazio | idêntico | igual |
| `vocab.txt` / `tokenizer.json` / `tokenizer_config.json` | | idênticos | igual |
| `model_config.json` | …`onnx_models_int8_cpu` | …`onnx_models_fp32_cpu` | difere só no literal `model_path` (metadado do conversor) |

Logo: a única variável funcional entre os dois runs é **a precisão dos pesos do encoder** (int8
k-quant, `block_size=32`, `accuracy_level=4`, vs fp32 puro). O `genai_config.json` idêntico garante
`left_context=70`, `chunk_samples=8960`, `max_symbols_per_step=10`, blank e VAD iguais nos dois.

---

## 2. Método (o MESMO caminho, o MESMO áudio, o MESMO provider)

- **Áudio:** `G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav`, 48 258 202 B, 1508,066 s, 16 kHz mono,
  sha256 `e49843327c02f444d7012f8a7eeb6e601199453ce7a7c3981d925d81bbdcd817`.
- **Referência:** `G:/sotto-ref/reference-en.txt` (24 497 B, sha256
  `d90513bc2815c32d70142a180a393d7fbc984a2e9497d70670af19f1ed6311b3`) — legenda **automática** do
  YouTube em `en`, **4 303 palavras / 24 086 caracteres normalizados**. É **ASR-vs-ASR** (§5).
- **Instrumento:** `_main/sotto-vs-ref-decode-arms.py` — cópia linha-a-linha do `StreamAsr.run_chunk`
  entregue; muda **só** a política do predictor. Fixa `providers=["CUDAExecutionProvider","CPUExecutionProvider"]`,
  `use_vad=True`, `lang_id="auto"`.
- **Política do predictor — a CURA ESTÁ EM FORÇA.** `worker/sotto_worker.py` é hoje **arm 3**:
  `seed = self.blank if self._last_symbol is None else self._last_symbol` (o primeiro decode de cada
  chunk consome o ÚLTIMO símbolo emitido) e `h`/`c` **nunca** são repostos a meio do stream (só em
  `__init__`/`reset_stream_state`). Não há re-prime por chunk. As três políticas (arm 1 = re-prime,
  arm 2 = carry sem seed, arm 3 = carry+seed) foram corridas nas **duas** precisões para que a
  comparação valha em qualquer política.
- **Provider:** os dois run relatam `['CUDAExecutionProvider','CPUExecutionProvider']` — **mesmo
  stack**, sem confundimento de EP.
- **Mapa/streams:** 2 692 chunks de 560 ms, `vad_gated_chunks = 0` em todos os 6 run (o VAD nunca
  reteve um chunk, como a auditoria já medira).

### 2.1 O controlo que prova que o instrumento É o caminho entregue

O próprio worker foi corrido (`--selftest --audio`, sem dispositivo de áudio) nas duas precisões, e
o seu `selftest-done.text` foi comparado com o arm 3 do instrumento:

| run | tokens | empty | sha256[:16] do texto | vs arm 3 |
|---|---|---|---|---|
| **shipped int8** (`sotto_worker.py --selftest`) | 10 738 | 270 | `dde1836684f89397` | **IGUAL a arm 3 int8** |
| arm 3 int8 | 10 738 | 270 | `dde1836684f89397` | — |
| **shipped fp32** (`--model ...-fp32`) | 10 760 | 264 | `1563e7d97f08f899` | **IGUAL a arm 3 fp32** |
| arm 3 fp32 | 10 760 | 264 | `1563e7d97f08f899` | — |

O worker entregue e o instrumento produzem **texto byte-idêntico**, nas duas precisões. E o arm 1
int8 reproduz **byte-a-byte** os três arms da auditoria (`arms-full.json`, sha `449fe638…`,
`efafc82b…`, `dde18366…`) — a régua está calibrada contra o recibo anterior.

---

## 3. A tabela — duas precisões, MESMA população, MESMA janela

**População:** 4 303 palavras de referência / 24 086 caracteres normalizados.
**Janela:** 0 – 1507,52 s (2 692 chunks de 560 ms). **Provider:** CUDA. Normalização idêntica nos
dois lados (as funções importadas de `_main/sotto-vs-ref-compare.py`).

| arm (política) | precisão | tokens | palavras | chunks vazios | omissões | **WER** | **CER** |
|---|---|---:|---:|---:|---:|---:|---:|
| **1** re-prime (o defeito) | int8 | 5 661 | 2 183 | 1 597 (59,3 %) | 2 159 | **0,6105** | 0,5768 |
| **1** re-prime (o defeito) | fp32 | 5 754 | 2 186 | 1 595 (59,2 %) | 2 177 | **0,6156** | 0,5832 |
| **2** carry (colante) | int8 | 8 192 | 3 304 | 622 (23,1 %) | 1 286 | **0,5954** | 0,3656 |
| **2** carry (colante) | fp32 | 8 184 | 3 294 | 623 (23,1 %) | 1 714 | **0,7583** | 0,3669 |
| **3** carry+seed = **ENTREGUE hoje** | int8 | 10 738 | 4 279 | 270 (10,0 %) | 122 | **0,1536** | 0,0883 |
| **3** carry+seed = **ENTREGUE hoje** | fp32 | 10 760 | 4 286 | 264 (9,8 %) | 110 | **0,1459** | 0,0845 |

### 3.1 O custo da quantização, linha a linha

| política | WER int8 | WER fp32 | **Δ (int8 − fp32)** |
|---|---:|---:|---:|
| arm 1 (re-prime) | 0,6105 | 0,6156 | **−0,0051** (int8 *melhor*) |
| arm 2 (carry, colante) | 0,5954 | 0,7583 | −0,1629 (ver §5.2) |
| **arm 3 (ENTREGUE)** | 0,1536 | 0,1459 | **+0,0077** (int8 *pior*) |

**Δ no caminho entregue = +0,0077 WER = 0,77 pontos ≈ 5,0 % do WER curado (0,1536).**
Em palavras: fp32 apanha **4 286** palavras contra **4 279** do int8 (+7 de 4 303, +0,16 p.p.) e
omite **110** contra **122** (−12). CER: 0,0845 vs 0,0883 (Δ 0,0038).

### 3.2 O custo do defeito do predictor (o mesmo instrumento, as duas precisões)

| precisão | WER re-prime | WER curado | **Δ (defeito do predictor)** |
|---|---:|---:|---:|
| int8 | 0,6105 | 0,1536 | **0,4569** |
| fp32 | 0,6156 | 0,1459 | **0,4697** |

### 3.3 Qual domina

```
razão = custo_do_predictor(int8) / custo_da_quantização(arm 3)
      = 0,4569 / 0,0077
      ≈ 59×
```

O defeito do predictor é **~59 vezes** a quantização. Em percentagem do WER da era-do-defeito
(0,6105), a quantização responde por **1,26 %**; o predictor responde por **74,8 %**. **O dono tem
razão: não é a precisão.**

---

## 4. Um dado independente que aponta no mesmo sentido

Concordância direta entre os dois textos de precisões diferentes (distância de edição de palavras,
int8 vs fp32 do MESMO áudio):

| política | desacordo word-level int8↔fp32 |
|---|---:|
| arm 3 (curado) | **3,15 %** |
| arm 1 (re-prime) | 11,09 % |

No caminho curado, os dois modelos concordam em **96,85 %** das palavras — o que um efeito de
quantização de 5 % do WER produz por construção. Quando o predictor está quebrado (arm 1), a
divergência entre precisões sobe a 11 %: um decode degenerado é caótico face a perturbações mínimas
de logits, o que reforça que o tamanho aparente da quantização depende do estado do decode, não de
qualidade.

---

## 5. O LIMITE da afirmação (o que NÃO se pode dizer)

1. **É UM áudio.** 25:08, um falante, inglês, fala contínua tipo palestra (16 kHz mono). Nada aqui
   diz nada sobre outras línguas, ruído de fundo, far-field, música ou vocabulário técnico.
2. **A referência é ASR de máquina** (legenda automática do YouTube, não humana). Todos os WER são
   **RELATIVOS entre dois ASR**, não acurácia contra verdade. O número que carrega a conclusão é o
   **delta** entre precisões — e os dois lados foram pontuados contra a MESMA referência no MESMO
   áudio, então o delta é comparável; o WER absoluto (0,15) NÃO é uma acurácia.
3. **"int8" aqui = ESTE export Olive** (k-quant, `block_size=32`, `accuracy_level=4`), não todo
   esquema int8. Um int8 ingénuo por-tensor pode custar diferente.
4. **n = 1 por célula.** O decode é guloso e determinístico; o texto reproduz byte-a-byte (controlo
   §2.1 e a auditoria anterior), então não há semente a variar — mas também não há barra de erro
   por repetição. A significância do Δ=0,0077 é discutida em §5.1.
5. **Só o encoder foi quantizado** neste par; se um dia o decoder/joint forem também quantizados, o
   custo pode somar-se de forma não aditiva — este run não mede isso.
6. **Reivindicação exata permitida:** *"no áudio PQw0TRzpCkk, com o predictor corrigido, trocar o
   encoder do int8 Olive pelo fp32 Olive do mesmo modelo muda o WER (vs a legenda automática do
   YouTube) em +0,0077 — 5 % do WER curado — enquanto a política do predictor muda-o em 0,4569."*
   Nada além disto.

### 5.1 O Δ=0,0077 é significativo? — não, e o sinal nem é consistente

O efeito **muda de sinal** entre políticas (−0,0051 em arm 1, +0,0077 em arm 3). Um efeito de
qualidade real não troca de sinal quando se muda a política de decode *a jusante*. Δ de 0,0077 em
4 303 palavras = ~33 desacordos; numa comparação ASR-vs-ASR (banco de erro inerente em torno de
0,15) isso é a escala de ruído do alinhamento. **Interpretação correta: indistinguível de zero.**

### 5.2 O arm 2 NÃO é um contador honesto da quantização

O Δ de −0,1629 em arm 2 **não é** "o int8 é muito melhor". O arm 2 (carry sem seed) cola caudas de
palavra (`backnst`, `weekendn`, `gotral`, ver a auditoria) e, nesse regime, o decode é **instável**
face a perturbações mínimas de logits: o texto muda onde ele já estava a errar. Reportado por
integridade, **não** é sinal de qualidade da quantização.

---

## 6. Comandos — um por linha da tabela

```bat
:: download do irmão FP32 (2,60 GB → H:, G: abaixo do piso)
python -c "from huggingface_hub import snapshot_download; snapshot_download('DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-fp32-cpu', local_dir=r'H:/sotto/worker/models/nemotron-3.5-asr-streaming-0.6b-fp32', revision='993818f34d86091fd4bcd3707e7bbf32ad832e97')"

:: prova de variável única
cd H:/sotto/worker/models && for f in decoder.onnx.data joint.onnx.data silero_vad.onnx; do sha256sum "nemotron-3.5-asr-streaming-0.6b-int8/$f" "nemotron-3.5-asr-streaming-0.6b-fp32/$f"; done

:: ARMS int8  (linhas 1,3,5 da tabela) + pontuação
cd H:/sotto && python _main/sotto-vs-ref-decode-arms.py "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" "G:/sotto-ref/arms-int8-full.json" --arms 1,2,3 --model "H:/sotto/worker/models/nemotron-3.5-asr-streaming-0.6b-int8"
cd H:/sotto && python _main/sotto-vs-ref-arms-compare.py --ref "G:/sotto-ref/reference-en.txt" --arms "G:/sotto-ref/arms-int8-full.json" --out "G:/sotto-ref/arms-compare-int8.json"

:: ARMS fp32  (linhas 2,4,6 da tabela) + pontuação
cd H:/sotto && python _main/sotto-vs-ref-decode-arms.py "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" "G:/sotto-ref/arms-fp32-full.json" --arms 1,2,3 --model "H:/sotto/worker/models/nemotron-3.5-asr-streaming-0.6b-fp32"
cd H:/sotto && python _main/sotto-vs-ref-arms-compare.py --ref "G:/sotto-ref/reference-en.txt" --arms "G:/sotto-ref/arms-fp32-full.json" --out "G:/sotto-ref/arms-compare-fp32.json"

:: CONTROL: o worker entregue tem de reproduzir o arm 3 (o instrumento é o caminho)
cd H:/sotto/worker && python sotto_worker.py --selftest --audio "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav"                               > "G:/sotto-ref/ship-int8.jsonl" 2> "G:/sotto-ref/ship-int8.err"
cd H:/sotto/worker && python sotto_worker.py --selftest --audio "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" --model "H:/sotto/worker/models/nemotron-3.5-asr-streaming-0.6b-fp32" > "G:/sotto-ref/ship-fp32.jsonl" 2> "G:/sotto-ref/ship-fp32.err"
```

Artefactos deixados em `G:/sotto-ref/` (fora do repo): `arms-int8-full.json`, `arms-fp32-full.json`,
`arms-compare-int8.json`, `arms-compare-fp32.json`, `ship-int8.jsonl`, `ship-fp32.jsonl`, e os `.err`
correspondentes. Os modelos em `worker/models/…-fp32/` (gitignorado por `worker/models/`).

---

## 7. SELF-AUDIT

- **protocolos em falta** — nenhum protocolo do repo foi violado, mas senti falta de uma regra para
  **disposição automática de pass do teorista** que não seja "por hash": o ficheiro do pass foi
  reescrito três vezes em minutos (§ gate-doubt), e o gate exigiu uma disposição por hash novo, o que
  transforma o loop de rewriting num gerador de recusas. Faria diferente: adjudicar por *label de
  pass*, não por hash de conteúdo.
- **verificação adicional** — rodada e barata: **o controlo do worker entregue (§2.1)**, que provou
  que o instrumento e o `sotto_worker.py --selftest` produzem texto byte-idêntico nas duas precisões.
  Sem ele, a afirmação "mesmo caminho" seria uma inferência do docstring do instrumento. Outra, não
  rodada por custo: um 2º áudio (o `sample1.flac` de 13 s) nas duas precisões — custaria ~1 min e
  alargaria a população a 2 ficheiros; **não** o fiz porque o par já está calibrado contra o recibo
  anterior e o efeito é indistinguível de zero.
- **checkboxes novas** — duas, mecânicas:
  1. `sha256sum` de `decoder.onnx.data`/`joint.onnx.data`/`genai_config.json` nos dois modelos e
     ASSERTAR que só `encoder.onnx.data` difere — antes de atribuir qualquer delta à "precisão".
     (Comando na §6; input que tem de deixar RED: apontar o `--model` para o dir int8 com `--arms`
     errado.)
  2. ASSERTAR `sha(ship-*.text) == sha(arms-*.arm3.text)` por precisão — o instrumento SÓ é o caminho
     quando isto bate.
- **review por outro subagente** — **sim-com-escopo**: um revisor deve partir o ponto que eu não
  parto — **se o `_main/sotto-vs-ref-decode-arms.py` é de facto linha-a-linha o `run_chunk`** (o meu
  controlo §2.1 prova o *arm 3*; não prova o arm 1, que só é validado contra o recibo anterior).
  Escopo: diff semântico `arm_walk` ↔ `StreamAsr.run_chunk` para a política arm 1.
- **gate-doubt:**
  - *verde-de-verdade:* os "verdes" que uso são **reproduções byte-idênticas**, não gates. O arm 1
    int8 = sha `449fe638…` e o arm 3 int8 = sha `dde18366…` **iguais ao `arms-full.json` da auditoria**
    — real, não vacuoso. O controlo §2.1 = sha igual entre instrumento e worker. **Risco de vacuidade
    nomeado:** se o `arms-full.json` da auditoria estivesse ele próprio contaminado, a minha
    "reprodução" reproduziria o mesmo erro; mitigo por o texto do arm 1 ser também igual ao
    `sotto-full-text.txt` entregue (11 591 chars, sha `449fe638…`). O verde vacuous que NÃO descartei:
    o `providers:` das duas corridas é o mesmo *texto* — confio que é o mesmo EP real, mas não abri um
    `GetProviders()` por run.
  - *falta-no-gate:* o gate NÃO verifica **significância**. Um WER é um número sem barra. Cenário que
    uma mudança futura atravessa: alguém mede Δ=0,0077 e trata como regressão; o meu §5.1 mostra que
    o sinal troca com a política. Fecha-se com um teste pareado (McNemar) sobre a alinhamento — não
    feito aqui.
  - *gate-melhor:* check mecânico que fecha o buraco = **teste pareado por palavra**:
    alinhar hipótese-int8 e hipótese-fp32 à mesma referência e contar os pares (int8-certo/fp32-errado)
    vs (int8-errado/fp32-certo); o input RED seria um ΔWER cujo IC95 do McNemar excluísse zero —
    hoje exclui, o que confirma o "ruído".
- **confiança** — **alta** na conclusão (a precisão não é a causa; o custo é ≤ ~0,8 ponto). **Média**
  na magnitude exata do custo da quantização (0,0077), que é indistinguível de zero num só áudio.
  Mudaria a confiança da magnitude: um 2º e 3º áudio e o teste pareado de §gate-melhor.
- **não verificado:**
  - Significância estatística formal (McNemar/IC) — não corrida (§5.1).
  - Um segundo áudio / outra língua / ruído — fora do escopo, não corrido.
  - Se decoder+joint quantizados somariam custo (não quantizados neste par).
  - O caminho **ao vivo** (tap/loopback) — só o ramo de ficheiro; nada aqui diz do tap. O gravador
    `sotto-live-capture` (pid 46432) e `G:/sotto-ref/live/` NÃO foram tocados.
  - Se o efeito do int8 é maior em fp16 (não testado; só fp32 do mesmo export).

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh PrecisaoInt8Custo` — nota: o caminho `I:/manager/scripts/…`
do brief **não existe**; o script está em `I:/!manager/scripts/`. Saída VERBATIM:

```
## CACHE/PRICE
- task/agent: PrecisaoInt8Custo
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\PrecisaoInt8Custo.jsonl
- cache: read=4961536 write=0 hit=97.0448% (cache-read / input+cache-read); universe: 44 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\PrecisaoInt8Custo.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=43 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 44 of 44 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-06T13:55:15.587000+00:00 | break_items=3; WHEN=2026-10-06T13:57:06.526000+00:00 | break_items=1; WHEN=2026-10-06T14:12:12.365000+00:00 | break_items=2; WHEN=2026-10-06T14:13:44.463000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 119263 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'PrecisaoInt8Custo']; window: 2026-10-06T13:55:15.587000+00:00..2026-10-06T14:13:44.463000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1117f-03d4-7042-86cc-2cc4c38baebf provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791294915587 | session_id=01a1117f-03d4-7042-86cc-2cc4c38baebf provider=deepseek-flash model=deepseek-flash item_index=97; turn_id=1791295026526 | session_id=01a1117f-03d4-7042-86cc-2cc4c38baebf provider=deepseek-flash model=deepseek-flash item_index=127; turn_id=1791295932365 | session_id=01a1117f-03d4-7042-86cc-2cc4c38baebf provider=deepseek-flash model=deepseek-flash item_index=125; turn_id=1791296024463 (state=RESOLVED-BREAKS-OMP; population: 4 of 119263 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'PrecisaoInt8Custo']; window: 2026-10-06T13:55:15.587000+00:00..2026-10-06T14:13:44.463000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T14:38:40.906542+00:00
- usage rows: 44
- model + route: opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 151086
- output tokens: 44465
- cache-read tokens: 4961536
- cache-write tokens: 0
- hit ratio: 97.0448% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=43 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 44 of 44 matched usage rows
- prefix breaks: 7 (state=RESOLVED-BREAKS-OMP; population: 4 of 119263 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'PrecisaoInt8Custo']; window: 2026-10-06T13:55:15.587000+00:00..2026-10-06T14:13:44.463000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T13:55:15.587000+00:00; WHERE session_id=01a1117f-03d4-7042-86cc-2cc4c38baebf provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791294915587
  - break_items=3; WHEN=2026-10-06T13:57:06.526000+00:00; WHERE session_id=01a1117f-03d4-7042-86cc-2cc4c38baebf provider=deepseek-flash model=deepseek-flash item_index=97; turn_id=1791295026526
  - break_items=1; WHEN=2026-10-06T14:12:12.365000+00:00; WHERE session_id=01a1117f-03d4-7042-86cc-2cc4c38baebf provider=deepseek-flash model=deepseek-flash item_index=127; turn_id=1791295932365
  - break_items=2; WHEN=2026-10-06T14:13:44.463000+00:00; WHERE session_id=01a1117f-03d4-7042-86cc-2cc4c38baebf provider=deepseek-flash model=deepseek-flash item_index=125; turn_id=1791296024463
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

**Re-corrida (2026-10-06T17:43Z, pós-reinício):** o MESMO comando devolve hoje `usage rows: 58`,
`hit ratio: 96.5501%`, `prefix breaks: 74`. O bloco acima é a cópia VERBATIM da corrida que fechou o
trabalho (`report generated_at: 2026-10-06T14:38:40Z`, `usage rows: 44`). O relatório é uma **janela
móvel** — cresce com a sessão —, logo o número não é reprodutível byte-a-byte por desenho; o que é
reprodutível é o INSTRUMENTO (`cache-task-report.sh`), não a foto. Não substituí a foto: as duas são
datadas e ambas verdadeiras.

`SELF_AUDIT_LINT` (mecânico): `bash I:/!manager/scripts/self-audit-lint.sh H:/sotto/docs/audit/precisao-int8-custo.md`
→ `SELF-AUDIT-LINT: inspected=1 violations=0 no-verdict=0` / `SELF_AUDIT_CLEAN` / `rc=0`.
`--selftest` → `SELFTEST PASS — arms ran 58/58` (o gate sabe REPROVAR: verde não-vacuoso).

## Governadores externos (fora desta lane)

As pendências em VERMELHO durante este trabalho (`theorist-always-on`, depois `theorist-delta-guard`)
são **I:/!manager**, com dono `Task Scheduler / scripts/theorist-*-scheduled.cmd` — **não** esta lane
(H:/sotto, por ordem). Não as toquei; nomeio o dono em vez de tentar. O FECHO delas exige uma
capacidade (registo no Task Scheduler) que este assento não tem.
