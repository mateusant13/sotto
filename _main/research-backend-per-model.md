# Backend por modelo — o que existe, o que usamos hoje, o que devíamos usar

**Lane:** pesquisa de motores/runtimes por modelo (não instala nada, não corre modelos pesados).
**Data da medição:** 2026-10-07, tarde. **Máquina:** Windows, RTX 5080 (cc 12.0), Python 3.11.8
(`C:\Program Files\Python311\pythonw.exe`), `HF_HOME=I:\codeintel\hf-cache`.

## Regras de evidência usadas neste documento

- **FACTO CITADO** = veio de uma fonte externa, com URL.
- **FACTO MEDIDO** = foi lido nesta caixa, por um comando cujo resultado está colado aqui.
- **INFERÊNCIA MINHA** = conclusão minha a partir dos dois de cima. Marcada como tal.
- **NÃO MEDIDO** = dito explicitamente, com o instrumento que decidiria.
- "grep devolveu ZERO" tem prazo de validade: **todos os greps e todos os números de linha deste
  documento foram re-corridos em 2026-10-07 antes de serem escritos**, e as revisões estão na tabela
  abaixo. Onde uma linha do `AGENTS.md` já não bate, digo-o.

### Revisões dos ficheiros citados (medidas agora, `Get-FileHash`/`Get-Item`)

| ficheiro | bytes | mtime | sha256 (16 hex) |
|---|---|---|---|
| `worker/sotto_worker.py` | 237489 | 2026-10-07 11:47:51 | `29E4CBFA71C1AC6D` |
| `worker/redux_live.py` | 45281 | 2026-10-07 12:08:01 | `7985190AB5F4F1A6` |
| `worker/redux_batch.py` | 8559 | 2026-10-07 04:39:45 | `C5D44F93C4AA3DA7` |
| `worker/qwen_summary.py` | 84826 | 2026-10-07 06:02:46 | `70F56A88DD551A64` |
| `worker/config.json` | 4707 | 2026-10-07 03:18:11 | `D53E6AE0C7A573F0` |
| `worker/README.md` | 19744 | 2026-10-07 03:24:24 | `8A05B525A7C7DDF7` |
| `AGENTS.md` | 54801 | 2026-10-07 11:01:29 | `3D5E06B01CA5CB09` |

---

## 0. Sumário executivo

1. **A afirmação do `AGENTS.md` de que o `CUDAExecutionProvider` não é carregável é FALSA hoje**, e
   era meia-verdade operacional: falta **um** directório no caminho de DLLs, e o worker **já o
   acrescenta**. O motor ao vivo **não** corre em CPU — corre com CUDA na lista de EPs da sessão.
   Prova colada na §2.
2. **A stack ao vivo é híbrida, não "ORT-GenAI".** `og.Model` dá só o *front end* (mel cache-aware +
   Silero VAD); encoder/decoder/joint são `onnxruntime.InferenceSession` puros e o laço RNNT é
   Python nosso. Prova na §3.1.
3. **`onnxruntime-genai` 0.17.1 instalado é um build SÓ-CPU** (`og.is_cuda_available()` → `False`,
   medido). Existe `onnxruntime-genai-cuda` (facto citado). **Não vale a pena**: o genai só faz o mel
   e o VAD — o trabalho pesado já está no ORT/CUDA. (§3.1, §6)
4. **O `sherpa-onnx` é o achado desta pesquisa.** Existe build **Windows x64 CUDA 13 / cuDNN 9**
   pré-compilado e um **executável de streaming ASR auto-contido** — sem MSVC. E o `1.13.4` que já
   está instalado **não** expõe o prompt de língua por stream que os modelos Nemotron streaming
   publicados em 2026-06 exigem. (§5)
5. **A decisão de forçar CPU no `qwen_summary.py` está apoiada em duas premissas expiradas**
   (`qwen_summary.py:1029-1035`): "ORT anuncia CUDA e não a consegue ligar" e "esta caixa tem CUDA
   12.8". A primeira é falsa hoje; a segunda também (as DLLs de CUDA **13** estão em
   `site-packages\nvidia\cu13\bin\x86_64`). A *decisão* pode continuar certa — mas por outra razão.
6. **O `sherpa-onnx` já suporta o Parakeet TDT v3 com `model_type="nemo_transducer"` e devolve
   timestamps e durações por token** — capacidade que a nossa stack **não tem**, com pesos que
   **já estão em disco** no formato sherpa. É a mudança técnica de maior valor por menor custo. (§5, §8)
7. **Redux: o ONNX int4 ganha do ternário por 6,3× em RAM** (615 MB vs 3,90 GB de pico) com a mesma
   transcrição byte-a-byte. Para um transcritor de fundo "leve", a RAM é que conta. (§3.3)
8. **A GPU não é uma pergunta uniforme por modelo.** Para o Redux/TDT ela mudaria muito; para o
   Nemotron int4 pode não mudar **nada** — há uma medição *no próprio repo* de que `MatMulNBits` int4
   no `CPUExecutionProvider` é ~12× mais rápido que no CUDA. (§6)

---

## 1. O inventário instalado — o que decide tudo

**FACTO MEDIDO** (`importlib.metadata`, 451 distribuições, Python 3.11.8):

| runtime | versão instalada | nota |
|---|---|---|
| `onnxruntime` | **1.30.0** | |
| `onnxruntime-gpu` | **1.30.0** | mesmo directório de pacote que o de CPU |
| `onnxruntime-genai` | **0.17.1** | **build só-CPU** (medido) |
| `sherpa-onnx` | **1.13.4+cuda12.cudnn9** | traz o **seu próprio** ORT 1.24.4 |
| `torch` | 2.7.0+cu128 | `torch.cuda.is_available()` → **True** |
| `ctranslate2` / `faster-whisper` | 4.8.1 / 1.2.1 | instalados, sem uso no repo |
| `moondream` / `kestrel` | 2.6.1 / 0.9.1 | runtime do ternário |
| `onnx` | 1.22.0 | |
| `transformers` / `tokenizers` | 5.15.0 / 0.22.2 | |

**AUSENTES (grep de `importlib.metadata`, zero linhas — e isto é um ZERO com prazo de validade):**
`openvino`, `openvino-genai`, `tensorrt`, `tensorrt-llm`, `nvidia-tensorrt`, `polygraphy`,
`onnxruntime-directml`, `onnxruntime-openvino`, `onnxruntime-qnn`, `torch-directml`, `directml`,
`windows-ai`, `winml`, `nemo`/`nemo-toolkit`, `funasr`, `k2`, `llama-cpp-python`, `openai-whisper`,
`pywhispercpp`, `whispercpp`, `optimum`, `onnx-asr`, `vllm`, `exllamav2`, `mlx`, `speechbrain`,
`pyannote.audio`, `mediapipe`, `vosk`, `webrtcvad`, `sentencepiece`.

**FACTO MEDIDO — não há toolkit CUDA nesta caixa.** `$env:CUDA_PATH` =
`C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8` e `Test-Path` → `False`.
`Get-Command trtexec,nvcc` → nada. **As DLLs de CUDA 13 vêm de wheels pip**, em
`C:\Program Files\Python311\Lib\site-packages\nvidia\cu13\bin\x86_64\`
(`cublas64_13.dll` 54873200 B, `cublasLt64_13.dll` 493474416 B, `cudart64_13.dll`,
`nvrtc64_130_0.dll`, `nvJitLink_130_0.dll`), com dist-infos `nvidia_cublas-13.8.0.4`,
`nvidia_cuda_runtime-13.4.92`, `nvidia_cudnn_cu13-9.27.0.42`.

**FACTO MEDIDO — um só directório de pacote, vários wheels empilhados.**
`onnxruntime\capi\` tem `onnxruntime.dll` 18036536 B (ORT 1.30.0),
`onnxruntime_providers_cuda.dll` 184755512 B, `onnxruntime_providers_tensorrt.dll` 912184 B, mais
restos renomeados `~%pi`, `~-pi`, `~.pi`, `~=pi`, `~api`, `~~pi` (um deles com
`onnxruntime_providers_cuda.dll` de 312608800 B). **Isto é uma armadilha de manutenção**: o wheel de
CPU e o de GPU escrevem no mesmo sítio.

---

## 2. A correcção do `AGENTS.md` sobre o CUDA — comando e saída

O `AGENTS.md` diz, na secção *Measured facts*:

> `CUDAExecutionProvider` is **requested but not loadable here** — ORT silently returns
> `['CPUExecutionProvider']`. The box runs on CPU.

**FACTO MEDIDO — as duas metades, com a saída colada:**

**(a) `get_available_providers()` nunca devolveu só CPU nesta revisão:**

```
ort.get_available_providers() -> ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
ort.get_device()              -> GPU
onnxruntime 1.30.0 / onnxruntime-gpu 1.30.0
```

**(b) numa shell limpa, uma sessão real que PEDE CUDA cai para CPU** — e a razão é uma DLL:

```
Error loading "...\onnxruntime\capi\onnxruntime_providers_cuda.dll" which depends on
"cublasLt64_13.dll" which is missing. (Error 126)
Failed to create CUDAExecutionProvider. Require cuDNN 9.* and CUDA 13.*
SESSION_ACTUAL ['CPUExecutionProvider']
```

**(c) UM directório corrige-o.** Quatro braços, mesma sessão:

| braço | o que foi posto no caminho de DLLs | `SESSION_ACTUAL` |
|---|---|---|
| `base` | nada | `['CPUExecutionProvider']` |
| `torchlib` | `torch\lib` (CUDA **12**: `cublas64_12.dll`, `cublasLt64_12.dll`) | `['CPUExecutionProvider']` |
| **`cu13`** | **só** `site-packages\nvidia\cu13\bin\x86_64` | **`['CUDAExecutionProvider', 'CPUExecutionProvider']`** |
| `all-nvidia` | todos os `site-packages\nvidia\**` | `['CUDAExecutionProvider', 'CPUExecutionProvider']` |

**INFERÊNCIA MINHA:** o `torch\lib` não serve porque o ORT 1.30 pede **CUDA 13** e o torch 2.7.0+cu128
traz CUDA 12 — nomes de DLL diferentes (`cublas64_13` vs `cublas64_12`), logo não é uma questão de
versão "velha", é uma questão de *nome inexistente*.

**(d) O worker que está em produção já faz isto.** `worker/sotto_worker.py:277`
(`def _add_cuda_dll_dirs()`), chamado em `:3251`, **antes** do `import onnxruntime`, com os handles
guardados em `_DLL_DIR_HANDLES` (`:273`). E a corrida ao vivo responde por si:

```
{"state":"boot","stage":"providers",
 "providers_available":["TensorrtExecutionProvider","CUDAExecutionProvider","CPUExecutionProvider"],
 "providers_selected":["CUDAExecutionProvider","CPUExecutionProvider"],
 "note":"","cuda_dirs_ms":1360,"provider_probe_ms":301}
```
(`_main/vad-arm-after-w.jsonl`, linha 3)

e o próprio motor imprime a sua lista (`sotto_worker.py:505`
`self.providers = self.enc.get_providers()`; o `print` da lista está em `:2772`):

```
providers    : ['CUDAExecutionProvider', 'CPUExecutionProvider']
```
(`_main/vad-arm-after-w.err.txt:11`, `_main/proof-mc8.err:11`, `_main/runcmd-entry-caption-044624.log`)

**VEREDICTO DA §2: a frase do `AGENTS.md` está ERRADA e tem de sair.** O `choose_providers()`
(`:1734`) tem uma sonda de vivacidade com `note=` para `cuda-registered-but-not-loadable`,
`cuda-unavailable` e `cuda-not-registered` — e na corrida ao vivo o `note` é `""`, ou seja **a sonda
passou**.

**O que isto NÃO prova** (importante): que *todos os nós* do encoder foram atribuídos à GPU. A lista
de EPs da sessão é o que está medido. **Instrumento que decidiria a atribuição por nó:** correr uma
sessão com `sess_options.enable_profiling = True` no modelo real e ler o `providers` de cada nó no
perfil JSON — não feito aqui (a lane não corre modelos pesados).

**Correcção secundária:** o `AGENTS.md` volta a estar desactualizado nos números de linha do
`rerun`/`finalise`/`drain`. **FACTO MEDIDO** na revisão de hoje (237489 B, `29E4CBFA…`):
`def rerun` → `:3637`, `def finalise` → `:3732`, `def drain` → `:3755`. O `AGENTS.md` diz `:2654`,
`:2748`, `:2771` (revisão de 173388 B). É a terceira vez no mesmo dia que estes números se movem.

---

## 3. Ficha por modelo

### 3.1 `nemotron-3.5-asr-streaming-0.6b-int8` — o motor AO VIVO

**Directório:** `worker/models/nemotron-3.5-asr-streaming-0.6b-int8/` (1021,04 MB em disco).
`config.json` do worker: `model.dir` aponta aqui, `lang_id: "auto"`, `use_vad: true`,
`providers: ["CUDAExecutionProvider","CPUExecutionProvider"]`.

#### (1) Arquitectura e o que ela impõe ao runtime

**FACTO MEDIDO** (cabeçalho do grafo, `onnx.load(..., load_external_data=False)`): o encoder int8
recebe

```
audio_signal [1,65,128]      length [1]
cache_last_channel [1,24,70,1024]   cache_last_time [1,24,1024,8]
cache_last_channel_len [1]          lang_id [1]
```

É um **Conformer streaming cache-aware** com **RNNT** por cima. `genai_config.json`:
`"type": "nemotron_speech"`, `vocab_size 13088`, `blank_id 13087`, `left_context 70`,
`conv_context 8`, `pre_encode_cache_size 9`, `chunk_samples 8960` (560 ms a 16 kHz), VAD
`threshold 0.3` / `silence_duration_ms 3360` / `prefix_padding_ms 560`.

**Implicações para o runtime, em três linhas:**
- **estado obrigatório entre chamadas** → o runtime tem de aceitar entradas/saídas de cache, ou
  fornecer o *front end* cache-aware. Um motor "offline" não serve.
- **um prompt de língua por stream** (`lang_id [1]`) → o runtime tem de o poder injectar. Isto vai
  ser a linha divisória do `sherpa-onnx` (§5).
- **decodificação RNNT greedy com `max_symbols_per_step 10`** → ou o runtime traz o laço, ou
  trazemos nós (é o que fazemos).

#### (2) Runtimes que existem para este modelo

| runtime | existe? | mantido? | corre em Windows sem MSVC? | serve aqui? |
|---|---|---|---|---|
| **`onnxruntime` (EP CPU)** | sim, 1.30.0 | sim | sim | **sim — é o que usamos para enc/dec/joint** |
| **`onnxruntime` (EP CUDA)** | sim | sim | sim, se as DLLs de CUDA 13 estiverem no caminho | **sim — e está a ser usado** (§2) |
| **`onnxruntime-genai`** | sim, 0.17.1 | sim | sim | **parcial — só o `StreamingProcessor` (mel + VAD)**; `AsrProcessor` **não existe** neste build (medido) |
| `onnxruntime-genai-cuda` | **sim** ([doc oficial](https://onnxruntime.ai/docs/genai/howto/install.html)) | sim | sim | **não vale a pena** — ver §6 |
| **ORT + TensorRT EP** | sim (a DLL existe, 912184 B) | sim | **não** — falha: `depends on "cublas64_13.dll" which is missing` | não, sem o toolkit CUDA 13 |
| **TensorRT-LLM** | sim, mas **não é motor de ASR** | sim | — | **não** (ver §4) |
| **sherpa-onnx** (streaming transducer) | **sim, 1.13.4 instalado; 1.13.8 é a última** | sim | **sim** — há `.exe` de streaming auto-contido e build CUDA-13 win-x64 | **quase** — falta o prompt de língua (§5) |
| DirectML / OpenVINO / Windows ML | pacotes existem no ecossistema | — | — | **não instalados**; para um 0.6B cache-aware não trazem nada que o CUDA EP não traga |
| whisper.cpp / ggml | **não** para Nemotron | — | — | **não** — nenhum motor ggml implementa Nemotron streaming |
| NVIDIA NeMo | sim | sim | não (PyTorch + toolchain) | **não** — é a ferramenta de *treino/export*, não de inferência de produção; traz 2+ GB de deps |
| CTranslate2 | sim | sim | sim | **não** — CTranslate2 serve Whisper e seq2seq Transformer; **não** implementa RNNT/TDT com caches |

#### (3) O que USAMOS hoje — com prova

**FACTO MEDIDO — é um híbrido, não "ORT-GenAI":**

| peça | quem a corre | prova |
|---|---|---|
| encoder / decoder / joint | **`onnxruntime.InferenceSession` puro** | `sotto_worker.py:501-503`; `:505 self.providers = self.enc.get_providers()` |
| mel cache-aware + Silero VAD | **`onnxruntime_genai`** (`og.Model` + `StreamingProcessor`) | `:514 self.model = og.Model(model_dir)`; `self.sp = self.fresh_processor()` |
| laço RNNT greedy, `max_symbols_per_step 10` | **Python nosso** | o worker inteiro; `blank_id 13087` vem do `genai_config.json` |
| prompt de língua | lido de volta do grafo, não presumido | `:541-547` (read-back de `lang_id`) |
| selecção de provider + sonda de vivacidade | `choose_providers()` | `:1734-1803` |

**Porque é que isto importa:** qualquer proposta de "trocar o ORT-GenAI por X" tem de perceber que o
genai aqui vale **pouco** (mel + VAD) e que o valor está no ORT + no laço Python. Trocar o genai não
toca no que é caro.

#### (4) O que DEVÍAMOS usar + custo

**Veredicto curto: ficar como está.** O ORT é o runtime certo para este modelo — é o único que expõe
as caches e o `lang_id` sem escrever C++.

Duas mudanças concretas, ambas pequenas:

- **(4a) Parar de pedir o `TensorrtExecutionProvider`.** Ele está na lista de
  `get_available_providers()` e falha a carregar em **toda** a corrida (`Error 126`,
  `cublas64_13.dll`). Custo: **10 minutos** (retirar da lista pedida, ou aceitar que a sonda o marque
  como não-carregável e o registe no `note`). Ganho: um `note` limpo e um log que não mente.
  Risco: nenhum. Perde-se: nada — ele nunca carregou.
- **(4b) Fazer a medição que falta: atribuição por nó.** `enable_profiling=True` numa corrida real,
  ler o perfil, contar nós por EP. Custo: **1 hora**, um `--wav` já existente. Decide se a GPU está
  a fazer trabalho ou só a decorar a lista. **É a medição que eu não fiz e que mais valor tem aqui.**

#### (5) Veredicto

**Sim — o backend está certo.** Uma ressalva e uma correcção de registo:

- **Correcção de registo:** `AGENTS.md` afirma que a caixa corre em CPU. **Falso.** (§2)
- **Ressalva:** a GPU está *pedida e ligada*; não está *provado que trabalha* (4b).
- **Quanto ganharia se a GPU entrasse: NADA — ela já entrou** (a lista de EPs da sessão tem
  `CUDAExecutionProvider`). Se a pergunta for "quanto se ganharia se a GPU *de facto* processasse os
  nós", a resposta é **"não sei"**, e quem decide é a medição (4b).
- **Alerta específico do int4:** o próprio repo mede que `MatMulNBits` int4 é ~12× mais rápido no
  `CPUExecutionProvider` que no CUDA (`qwen_summary.py:20` e `:100`: *"MatMulNBits int4 on
  CPUExecutionProvider returns 557-617 GFLOP/s, ~12x more"*). Se essa medição se transportar para o
  encoder int4, **a GPU pode ser mais LENTA** para o int4. Para o **int8** (que é o que o
  `config.json` selecciona) a história é outra. Isto é a razão pela qual (4b) não é curiosidade.

---

### 3.2 As outras três exportações do Nemotron (`fp16`, `fp32`, `int4`)

**FACTO MEDIDO** (varredura dos directórios):

| directório | MB | `genai_config.json` |
|---|---|---|
| `...-int4` | 756,59 | `type=nemotron_speech` |
| `...-int8` | 1021,04 | `type=nemotron_speech` |
| `...-fp16` | 1246,99 | **AUSENTE** |
| `...-fp32` | 2478,79 | `type=nemotron_speech` |

**FACTO MEDIDO — o `fp16` não tem `genai_config.json`.** Consequência directa:
`og.Model(model_dir)` **não o consegue abrir**. Ele só é utilizável por ORT puro, e nesse caso
perde-se o *front end* cache-aware do genai (teríamos de o reimplementar em Python). **É uma
exportação órfã para a nossa arquitectura.**

**INFERÊNCIA MINHA:** o `fp32` (2,48 GB) existe para diagnóstico/verificação de precisão, não para
produção; o `int8` é o compromisso escolhido (o `config.json` aponta lá) e o `int4` é a alternativa
leve. Isto está de acordo com a decisão já registada no `AGENTS.md` (int8, +268 MB de RSS vs int4).

**Veredicto: Sim para o `int8` (em uso); o `fp16` devia ser marcado como não-utilizável pelo genai, e
o `fp32`/`int4` como arquivo.** Custo de arrumar a documentação: 15 minutos.

---

### 3.3 `parakeet-redux` — o motor GERAL (duas formas em disco)

**A LEI DA STACK** diz: Redux é o motor geral, quando o painel está fechado, batch sobre o áudio
acumulado, **leve — o oposto do NVIDIA**.

**FACTO MEDIDO — as duas formas, hoje:**

| forma | directório | MB | o que a corre |
|---|---|---|---|
| **ONNX int4** | `worker/models/parakeet-redux-onnx-int4/` | **415,87** | `onnxruntime` + `numpy`, laço TDT portado |
| **ternário** | `worker/models/parakeet-redux-ternary/` | **170,73** | runtime do vendor (Photon/kestrel) → traz `torch` |

Ficheiros do ONNX int4 (medidos): `encoder-model.onnx` 343841943, `decoder_joint-model.onnx`
72552270, `preprocessor.onnx` 1224294, `vad-model.onnx` 18300687, `vocab.txt` 93939,
`transcribe.py` 17844, `config.json`, `requirements.txt` (**`onnxruntime>=1.22` + numpy, mais nada**).

> **Nota de contradição documental:** o `AGENTS.md` diz que o `parakeet-redux-onnx-int4` foi
> **apagado** a pedido do dono. **Está em disco agora** (415,87 MB, mtime 2026-10-07 11:58:16,
> re-baixado nesta sessão). Quem ler o `AGENTS.md` amanhã lê o contrário do que o disco diz.

#### (1) Arquitectura e implicações

**FACTO MEDIDO — ficha do export:** `nemo-conformer-tdt`, `vocab_size 8193`, **`blank_id 8192`**,
`max_tokens_per_step 10`, `durations [0,1,2,3,4]`, `encoder_frame_seconds 0.08`, 16 kHz. É um
**TDT** (token-and-duration transducer), **não** o RNNT do Nemotron: cada passo emite um token **e**
um salto de duração. **O laço de decodificação é outro** — é preciso portar o `transcribe.py`.

**FACTO MEDIDO — o encoder Redux é OFFLINE e sem estado:** recebe
`audio_signal ['batch',128,'time']` + `length ['batch']`. Sem caches. Isto **encaixa exactamente**
com a lei da stack (batch sobre áudio acumulado) e **desqualifica-o para ao vivo** — não é uma
preferência, é a assinatura do grafo.

#### (2) Runtimes

| runtime | existe? | serve o Redux? | nota |
|---|---|---|---|
| `onnxruntime` (CPU) | sim | **sim — é o que usamos** | `requirements.txt` do export pede só isto |
| `onnxruntime` (CUDA) | sim | sim | ganho real: é um encoder de 344 MB, denso, batch |
| `kestrel`/`moondream` (ternário) | sim, 2.6.1/0.9.1 | sim, paridade provada | custo de RAM enorme (§6) |
| `sherpa-onnx` `OfflineRecognizer.from_transducer` | **sim, com `model_type="nemo_transducer"`** | **sim** | ver §5 — e traz **timestamps** |
| whisper.cpp `parakeet-cli` | **sim**, whisper.cpp ≥ 1.9 | para o TDT v3, não para o Redux | ver §3.4 |
| TensorRT-LLM | sim | **não** | §4 |

#### (3) O que USAMOS hoje

- **ONNX int4:** `worker/redux_live.py` (45281 B, `7985190A…`) com `--engine onnx` **por omissão**;
  `worker/redux_batch.py` (8559 B) para o ternário.
- **FACTO MEDIDO — o custo do caminho ONNX** (`_main/redux-cost-onnx.log`):
  `onnxruntime providers : ['CPUExecutionProvider']` — **CPU, não GPU**;
  **15,0 s de áudio em 1,80 s = 8,33× tempo real**; **RSS de pico 615,3 MB**; threads 2;
  `text MATCHES ORACLE True`.

#### (4) O que DEVÍAMOS usar — a comparação com números

| | ONNX int4 | ternário (kestrel) |
|---|---|---|
| disco | 415,87 MB | **170,73 MB** ← ganha |
| **RSS de pico** | **615,3 MB** | **3,90 GB** ← perde **6,3×** |
| velocidade | 8,33× tempo real | 7–14× tempo real |
| carga | (não medida isolada) | 3,6–4,3 s |
| dependências | `onnxruntime` + `numpy` | + `torch` + kestrel (488,3 MB instalados) |
| paridade | byte-a-byte com o oráculo | byte-a-byte com o oráculo |

**A razão do desastre de RAM do ternário, medida:** o kernel int8 compilado do kestrel está
**inacessível nesta máquina** — `_cpu.ternary_gemm_isa()` → `'scalar'` **apesar de o CPU ter AVX2**
(o payload `kestrel_cpu.kstlc` é protegido e não traz a chave). O runner cai então na forma **dense
documentada**: 193/193 camadas ternary desquantizadas de uma vez → 3,90 GB.
(Receipt: `_main/receipt-redux-ternary.md`.)

**VEREDICTO: para o papel de "transcritor LEVE de fundo", o ONNX int4 é o certo.** 6,3× menos RAM, e
o critério declarado pelo dono é ser **leve**. O ternário ganha em disco (170 vs 416 MB) — e o disco
não é o recurso escasso. Custo de manter o ONNX: **zero**, já corre.

#### (5) Quanto ganharia se a GPU entrasse: **MUITO — e é o modelo onde mais ganha**

**INFERÊNCIA MINHA, com a base à vista:** o Redux corre hoje em `['CPUExecutionProvider']`
(*medido*, `_main/redux-cost-onnx.log`), é um encoder **denso de 344 MB**, **batch** e **sem estado**
— ou seja, sem o problema de caches que torna o TensorRT EP difícil no Nemotron. É o candidato
natural para o CUDA EP.
**O que decide o número:** correr `redux_live.py --engine onnx` com
`--providers CUDAExecutionProvider,CPUExecutionProvider` no mesmo `--wav` de 15 s e comparar
`infer_wall_s`. **Não medido aqui** (a lane não corre modelos pesados). **Não invento percentagem.**

---

### 3.4 `parakeet-tdt-0.6b-v3` — o TDT canónico, em TRÊS cópias e duas convenções de nomes

**FACTO MEDIDO:**

| cópia | ficheiros | convenção |
|---|---|---|
| `H:\aireplay\models\parakeet-tdt-0.6b-v3-onnx\` | `encoder-model.int8.onnx` 652183999, `decoder_joint-model.int8.onnx` 18202004, `nemo128.onnx` 139764, `vocab.txt` | **istupakov** (`onnx-asr`) |
| `H:\VOD.RIP-models\parakeet-models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8\` | `encoder.int8.onnx` 652184281, `decoder.int8.onnx` 11845275, `joiner.int8.onnx` 6355277, `tokens.txt` | **sherpa-onnx** |
| `H:\VOD.RIP-models\parakeet-models\sherpa-onnx-nemo-parakeet-redux\` | `encoder.onnx` 343842409, `decoder.onnx` 47249584, `joiner.onnx` 25285351, `tokens.txt` | **sherpa-onnx** |

**FACTO MEDIDO — a assinatura do encoder TDT v3 é idêntica à do Redux export:**
`ir=8`, `opset=[('ai.onnx',17)]`, entradas `audio_signal ['…',128,'…']` + `length`,
saída `outputs [...,1024,...]` + `encoded_lengths`. Mesma família, mesmo contrato offline.

#### (2) Runtimes

| runtime | existe? | nota |
|---|---|---|
| `onnxruntime` + laço TDT próprio | sim | é o que o `redux_live.py` já faz |
| **`sherpa-onnx` `OfflineRecognizer.from_transducer(model_type="nemo_transducer")`** | **sim** | **devolve `result.tokens` / `result.timestamps` / `result.durations`** |
| **whisper.cpp ≥ 1.9 (`parakeet-cli`)** | **sim** | motor TDT **dentro** do whisper.cpp; GGUF q8_0 669 MB, q4_0 356 MB |
| `onnx-asr` (pip) | sim | pacote Python do istupakov, não instalado |
| CTranslate2 | **não** | não implementa TDT |

**FACTO CITADO — sherpa-onnx tem exemplo oficial para exactamente estes ficheiros:**
`python-api-examples/offline-nemo-parakeet-decode-file.py` chama
`OfflineRecognizer.from_transducer(encoder, decoder, joiner, tokens, num_threads=1, provider="cpu",
decoding_method="greedy_search", model_type="nemo_transducer")` sobre
`sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/{encoder.int8.onnx, decoder.int8.onnx, joiner.int8.onnx,
tokens.txt}` — [exemplo raw](https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/python-api-examples/offline-nemo-parakeet-decode-file.py).

**FACTO CITADO — whisper.cpp ≥ 1.9 traz um motor Parakeet TDT** e os GGUF do v3 existem em f16
(1256 MB), q8_0 (669 MB), q5_0 (434 MB) e q4_0 (356 MB), carregáveis com
`parakeet-cli -m <file>`; o próprio cartão avisa que **não** é compatível com os GGUF do
`mudler/parakeet.cpp` — [cartão](https://huggingface.co/JoaoZaokk/parakeet-tdt-0.6b-v3-ggml/raw/main/README.md).

**INFERÊNCIA MINHA (marcada):** o motor Parakeet do whisper.cpp é o **offline** do whisper.cpp
(não-streaming) — não vi na documentação nenhuma afirmação de streaming para ele. **Não medido.**

#### (3) O que USAMOS hoje

**FACTO MEDIDO — o TDT v3 NÃO tem call site no worker.** O motor geral em uso é o Redux
(`redux_batch.py`, `redux_live.py`). O `H:\aireplay\src\asr\constants.py:53,65` aponta
`MODEL_DIR = REPO_ROOT/"models"/"parakeet-tdt-0.6b-v3-onnx"` — mas `H:\aireplay` é o **projecto
final** (Tauri), não o `H:\sotto` de hoje.

#### (4) O que DEVÍAMOS usar — **a mudança de maior valor por menor custo desta pesquisa**

**Adoptar `sherpa-onnx` como segunda implementação do TDT, para obter os timestamps.**
Motivos, por ordem:

1. **Dá uma capacidade que não temos:** `result.timestamps` e `result.durations` por token. A nossa
   stack emite texto sem tempo. Para o histórico do painel (e para o "Memory Engine" do
   `H:\aireplay`), tempo por palavra é a diferença entre uma transcrição e uma transcrição
   *navegável*.
2. **É uma segunda implementação independente do mesmo laço** — serve de oráculo cruzado ao nosso
   `transcribe.py`/`redux_live.py`. Se os dois concordarem byte-a-byte, o nosso laço está certo.
3. **Os pesos já estão em disco** no formato sherpa
   (`H:\VOD.RIP-models\parakeet-models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8\`) — **zero
   download**.
4. **O pacote já está instalado** (`sherpa-onnx 1.13.4`).

**Custo: ~1 dia** (um script de sonda + comparação com o oráculo existente). **Risco: baixo** — não
toca em nada que hoje funciona; corre num processo separado. **O que se perde: nada.**

**Ressalva obrigatória:** `sherpa_onnx` e `onnxruntime_genai` **não coexistem neste processo numa
ordem de import** (medido, §5.3). A sonda tem de correr em processo próprio, ou importar o genai
primeiro.

#### (5) Veredicto

**Sim — o backend certo para o TDT é ORT hoje, e o `sherpa-onnx` é a evolução certa amanhã**, pela
razão específica dos timestamps. **Quanto ganharia se a GPU entrasse: MUITO** (é batch, denso, sem
estado, 652 MB de encoder) — mesma ressalva do §3.3: o número decide-se a correr, não a adivinhar.

---

### 3.5 Os dois LLMs pequenos (`qwen3-0.6b-arm-int4`, `qwen3.5-0.8b-ortgenai-cpu`)

**FACTO MEDIDO:**

| directório | MB | `genai_config.json` | ficheiros |
|---|---|---|---|
| `qwen3-0.6b-arm-int4` | 472,16 | `type=qwen3`, `decoder.filename=model.onnx`, `provider_options` **vazio** | `model.onnx` 331869 + `model.onnx.data` 483328000 + tokenizer 11422650 + `example.py`, `metadata.yaml`, `config.yaml`, `SHA256SUMS.txt` |
| `qwen3.5-0.8b-ortgenai-cpu` | 719,72 | `type=qwen3_5`, `decoder.filename=text.onnx`, `provider_options` **vazio** | `text.onnx` + `text.onnx.data` 539492352, **`vision.onnx` + `vision.onnx.data` 57999360**, `embedding.onnx` + `.data` 135135232, `processor_config.json`, `model_config.json` |

**Duas leituras que mudam a ficha:**

- **O `qwen3.5-0.8b` é multimodal (tem torre de visão).** Não é um "LLM pequeno de resumo": é um
  VLM de 0,8B exportado para ORT-GenAI. Se o papel dele no repo é resumir texto, **a torre de visão
  é 58 MB de pesos que ninguém usa**.
- **O `qwen3-0.6b-arm-int4` chama-se "arm"** e o `provider_options` está **vazio**. **NÃO MEDIDO:** se
  este export é QNN/ARM (inutilizável em x64) ou apenas um nome. **Instrumento que decide:** abrir
  `model.onnx` só com o cabeçalho (`onnx.load(..., load_external_data=False)`) e ver se há nós
  `QLinearConv`/`com.microsoft` de QNN, ou correr `og.Model()` e ler `model.device_type`.

#### (3) O que USAMOS hoje — **e aqui há um problema real**

`worker/qwen_summary.py` (84826 B, `70F56A88…`) usa ORT-GenAI e **força explicitamente a CPU**
(`:1039-1043`):

```python
config = og.Config(str(model_dir))
if force_cpu:
    config.clear_providers()
    config.append_provider("cpu")
model = og.Model(config)
report["is_cuda_available_reported"] = bool(og.is_cuda_available())   # :1044
```

E a **justificação escrita no ficheiro** (`:1029-1035`, verbatim) é:

> *"The provider is set through `og.Config` rather than left to the export's own `genai_config.json`:
> measured on this box, ORT **advertises** CUDA and cannot bind it (`cublasLt64_13.dll` missing, ORT
> 1.30 wants CUDA 13 / **this box has 12.8**), so an export that asks for CUDA would silently fall
> back to CPU while claiming otherwise."*

**FACTO MEDIDO — as DUAS premissas desta justificação estão expiradas:**
1. *"ORT anuncia CUDA e não a consegue ligar"* → **falso**; com `nvidia\cu13\bin\x86_64` no caminho, a
   sessão liga (§2c). O worker ao vivo prova-o em produção.
2. *"esta caixa tem 12.8"* → **falso**; as DLLs de **CUDA 13** estão em
   `site-packages\nvidia\cu13\bin\x86_64\`, e é de lá que o worker as tira.

**E há uma terceira camada, medida:** `og.is_cuda_available()` → **`False`** em todos os braços —
porque o wheel `onnxruntime-genai 0.17.1` instalado é **só-CPU**. Ou seja: **mesmo que o CUDA
estivesse perfeito, o genai instalado nunca usaria a GPU.** As duas coisas foram confundidas.

**O que isto significa para a decisão:** o `clear_providers()+append_provider("cpu")` pode continuar
**certo** — mas não pela razão que lá está escrita. Há uma medição no mesmo ficheiro que aponta para
CPU por outro motivo (`:20`, `:100`: *"MatMulNBits int4 on CPUExecutionProvider returns 557-617
GFLOP/s, ~12x more"*), que é uma razão **de kernel**, não de disponibilidade.

#### (5) Veredicto

**Não sei — e nomeio a medição que decide.**
- **A decisão (CPU) está provavelmente certa**, por causa do kernel int4.
- **A justificação está errada** e tem de ser reescrita, senão o próximo agente repete-a (já está a
  ser repetida no `AGENTS.md`).
- **Medição que decide o provider do `qwen_summary`:** correr o mesmo resumo com
  `--force-cpu` e sem ele, medindo tokens/s e RSS, **depois** de instalar
  `onnxruntime-genai-cuda` (facto citado: existe). Se o CUDA perder (provável, pelo int4), a decisão
  fica provada; se ganhar, temos um ganho de graça.
- **Medição que decide o `arm-int4`:** o cabeçalho do grafo (acima).

---

### 3.6 Modelos de embedding

**FACTO MEDIDO — o que existe:**
`H:\VOD.RIP-data\embed-models-test\` com `xenova-e5-small\e5_{bnb4,fp16,int8}.onnx`
(397322585 / 235336732 / 118101148 B) e `xenova-rerankers\{bger_base_bnb4, bger_base_int8,
mmarco_bnb4, mmarco_int8}.onnx`; caches HF para `intfloat/multilingual-e5-small`,
`Qwen/Qwen3-Embedding-0.6B`, `BAAI/bge-m3` (4,25 GB),
`onnx-community/Qwen3-Reranker-0.6B-ONNX`.

**FACTO MEDIDO — `google/embeddinggemma-2` NÃO foi encontrado** na listagem do cache HF; existe uma
referência a `"embeddinggemma-2-440m-256d"` em `_moved\aireplay\_main\_index-final-probe.py:269`.
**NÃO MEDIDO / NÃO RESOLVIDO:** onde os pesos vivem. A busca por directório `*embeddinggemma*` em
`I:\`, `H:\` e `C:\Users\Administrador` estava a correr quando este relatório foi escrito (job
`pwsh-1995`, sem saída nova). **Não afirmo ausência — nomeio o instrumento e o seu estado.**

**Runtime:** todos estes ONNX são servidos por `onnxruntime` puro (não há nada de especial: são
encoders densos, batch, sem estado). **GPU: ganharia muito** — mesma família de argumento do §3.3.
`sentencepiece` está **ausente** (grep de metadados, zero linhas), o que pode importar para alguns
tokenizers.

---

## 4. Runtimes que NÃO servem — e porquê, um a um

| runtime | serve algum modelo nosso? | porquê |
|---|---|---|
| **TensorRT-LLM** | **NÃO** | É um motor de inferência de **LLM** (backend PyTorch, in-flight batching, paged KV cache). Não tem pipeline de transducer RNNT/TDT. O suporte a fala é recente e estreito: um PR *"[TRTLLM-12341][feat] Add Whisper support to the PyTorch backend"* ([PR #16141](https://github.com/NVIDIA/TensorRT-LLM/pull/16141/files/9a000d7006d638c163e73933f4f7698c831c5d4c)) e uma página de *encoder-decoder models* ([docs](https://nvidia.github.io/TensorRT-LLM/1.3.0rc25/models/encoder-decoder.html)) — Whisper e seq2seq, **não** caches de Conformer streaming nem TDT. Além disso exigiria compilar/instalar um toolchain pesado numa caixa sem toolkit CUDA. |
| **TensorRT (EP do ORT)** | não hoje | A DLL existe (`onnxruntime_providers_tensorrt.dll`, 912184 B) e falha: `depends on "cublas64_13.dll" which is missing`. Exigiria o **toolkit CUDA 13 completo** (~3 GB) + `trtexec`, e um *engine* por forma de cache — no Nemotron streaming a forma muda com o contexto, o que torna o cache de engines problemático. Custo alto, ganho incerto. |
| **DirectML** | não instalado | `onnxruntime-directml`/`torch-directml`/`directml` ausentes. É uma API **DirectX 12**, sem suporte a kernels int4 `MatMulNBits` maduros, e não traz nada que o CUDA EP não traga numa RTX 5080. |
| **OpenVINO / Windows ML** | não instalado | `openvino`, `openvino-genai`, `windows-ai`, `winml` ausentes. São stacks Intel/NPU-first; numa caixa NVIDIA o custo de integração não se paga. |
| **sherpa-onnx** | **SIM — ver §5** | O único "não" é o prompt de língua por stream no wheel instalado. |
| **whisper.cpp / ggml** | **SIM para o TDT v3** (`parakeet-cli`), não para o Nemotron | ggml não tem Conformer cache-aware nem Nemotron. |
| **torch / `kestrel`** | sim, é o que corre o ternário | Custo medido: 3,90 GB de RSS (§3.3). |
| **NVIDIA NeMo** | não | É toolchain de treino/export (PyTorch, 2+ GB de dependências), não runtime de produção. |
| **CTranslate2** | não | Serve Whisper e seq2seq Transformer; **não** implementa RNNT/TDT com caches. |
| **`onnx-asr`** | para o TDT v3 (istupakov) | Existe como pacote pip; **não instalado**. É um wrapper de ORT — não acrescenta runtime, acrescenta conveniência de nomes de ficheiros. |
| **vLLM / exllamav2 / mlx** | não | LLM-only / Apple-only. |

---

## 5. `sherpa-onnx` — o achado desta pesquisa

### 5.1 O que está instalado e o que a versão instalada sabe fazer

**FACTO MEDIDO** — `sherpa-onnx 1.13.4+cuda12.cudnn9`, em
`C:\Program Files\Python311\Lib\site-packages\sherpa_onnx\`:
`__init__.py`, `cli.py`, `offline_recognizer.py`, `online_recognizer.py`, `keyword_spotter.py`,
`display.py`, `utils.py`; `lib\_sherpa_onnx.cp311-win_amd64.pyd` 5680640,
`lib\onnxruntime.dll` 14430752 (**ORT 1.24.4**), `lib\onnxruntime_providers_cuda.dll` 275606552,
`lib\onnxruntime_providers_tensorrt.dll` 833048, `lib\sherpa-onnx-c-api.dll` 4580864.

**FACTO MEDIDO — superfície de API (introspecção):**
- `OnlineRecognizer.from_*` = `from_nemo_ctc, from_paraformer, from_t_one_ctc, from_transducer,
  from_wenet_ctc, from_zipformer2_ctc`.
- `OfflineRecognizer.from_*` = **22 construtores**, incluindo `from_transducer`, `from_nemo_ctc`,
  `from_nemo_canary`, `from_whisper`, `from_qwen3_asr`, `from_moonshine_v2`, `from_medasr_ctc`,
  `from_cohere_transcribe`, `from_funasr_nano`, `from_omnilingual_asr_ctc`.
- `OnlineRecognizer.from_transducer` assinatura completa: `provider='cpu'` (valores documentados:
  **cpu, cuda, coreml**) + os botões de TensorRT (`trt_max_workspace_size`,
  `trt_engine_cache_enable`, `trt_timing_cache_enable`, …) + `model_type=''`.
- `online_recognizer.py:39` — docstring: *"`:meth:`from_transducer` -- Zipformer, **Nemotron**, etc."*
- `online_recognizer.py:232-234` — `model_type`: *"Valid values are: conformer, lstm, zipformer,
  zipformer2. All other values lead to loading the model twice."*

### 5.2 O problema, e a medição que o decide

**FACTO CITADO — os modelos Nemotron 3.5 streaming publicados em 2026-06 para sherpa-onnx exigem um
prompt de língua POR STREAM:**

> *"Use per-stream language strings such as "en", "ja", or "auto"."*
> — [README de `csukuangfj2/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-2026-06-11`](https://huggingface.co/csukuangfj2/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-2026-06-11/raw/main/README.md)

> *"The multilingual `prompt_index` encoder input is exposed for per-stream language selection (or
> `auto` = the metadata `auto_prompt_id`)."*
> — [README 320ms](https://huggingface.co/Masterx/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-320ms-2026-06-11/raw/main/README.md),
> [README 560ms](https://huggingface.co/Masterx/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-2026-06-11/raw/main/README.md)

**FACTO MEDIDO — o wheel 1.13.4 instalado NÃO mostra esse caminho:**
- a assinatura de `from_transducer` **não tem** `language`, `lang_id` nem `prompt`;
- `online_recognizer.py` **não contém** nenhuma chamada a `set_option` nem o texto `language`;
- `OnlineStream` expõe um mapa genérico `set_option/get_option/has_option`, e o `c-api.h` documenta
  `SherpaOnnxOnlineStreamSetOption(stream, "is_final", "1")` e **só** menciona *"options such as
  `is_final` for streaming Paraformer"*;
- no `c-api.h` **não há** campo `prompt_index`/nemotron-language; todos os `language` dos cabeçalhos
  pertencem a Whisper, Cohere, SenseVoice/Qwen3-ASR ou LM offline.

**FACTO CITADO — a versão instalada está 4 patches atrás:** a última release é **v1.13.8**
(2026-09-10), e o `sherpa_onnx_macos` no pub.dev já ia em 1.13.8 — [release v1.13.8](https://github.com/k2-fsa/sherpa-onnx/releases/tag/v1.13.8).

**NÃO MEDIDO (e nomeio a medição):** se o 1.13.4 honra `set_option("language", …)` num stream
transducer. **Instrumento:** criar um `OnlineStream` a partir de um Nemotron no formato sherpa e
chamar `stream.has_option("language")` / `set_option` + `get_option`; ou ler
`sherpa-onnx/csrc/online-transducer-model.cc` no master à procura da chave reconhecida. **Não feito
aqui** — exigiria carregar um modelo de 343 MB+, e a lane proíbe corridas pesadas.

**INFERÊNCIA MINHA:** o `set_option` genérico existe desde antes, mas o *reconhecimento* da chave
`language` no caminho online é do tipo de coisa que entra numa release nova. A leitura dos READMEs
(que descrevem builds de 2026-06) e a diferença 1.13.4→1.13.8 apontam nessa direcção — mas isto é
inferência, não medição.

### 5.3 A armadilha medida: `sherpa_onnx` e `onnxruntime_genai` no MESMO processo

**FACTO MEDIDO — os três braços, ambos os sentidos** (`_main/_rb-genai-*.txt`):

| ordem de import | resultado |
|---|---|
| só `genai` | `onnxruntime_genai OK 0.17.1`, `onnxruntime OK 1.30.0` |
| **genai → sherpa** | `onnxruntime_genai OK 0.17.1` **e depois** `sherpa_onnx OK 1.13.4+cuda12.cudnn9` — **os dois funcionam** |
| **sherpa → genai** | `sherpa_onnx OK` **e depois** `onnxruntime_genai FAIL` — `ImportError: DLL load failed`, com o stderr: `The requested API version [26] is not available, only API versions [1, 24] are supported in this build. Current ORT Version is: 1.24.4` |

**Mecanismo (INFERÊNCIA MINHA, mas mecanicamente verificada pelos tamanhos):**
`sherpa_onnx\lib\onnxruntime.dll` (14430752 B, ORT **1.24.4**) é carregado primeiro; o
`onnxruntime-genai.dll` liga-se à DLL **já carregada** em vez de a
`onnxruntime\capi\onnxruntime.dll` (18036536 B, ORT **1.30.0**). **Uma DLL já carregada no processo
ganha a uma DLL com o mesmo nome mais tarde no caminho de procura.** Isto confirma e mecaniza a
armadilha já escrita em `worker/README.md:149`.

**Acção obrigatória para qualquer stack futura:** quem juntar `sherpa-onnx` ao *front end*
ORT-GenAI ao vivo **tem de importar o genai primeiro**, ou correr o sherpa em **processo separado**.
Isto não é uma preferência de estilo; é um `ImportError` medido.

### 5.4 Builds oficiais para Windows — **FACTO CITADO, e é o que torna o sherpa viável sem MSVC**

Da release **v1.13.8** (assets lidos da API do GitHub):

- `sherpa-onnx-v1.13.8-cuda-13.x-cudnn-9.x-onnxruntime1.28.2-win-x64-cuda.tar.bz2` ← **build CUDA 13,
  cuDNN 9, Windows x64, ORT 1.28.2** (e o gémeo CUDA 12.x)
- `sherpa-onnx-v1.13.8-cuda-13.x-cudnn-9.x-onnxruntime1.28.2-linux-x64-gpu.tar.bz2`
- **`sherpa-onnx-streaming-asr-x64-v1.13.8.exe`** ← **executável de ASR streaming auto-contido** (e
  o `-x86`, e os `non-streaming-asr` / `non-streaming-tts`)
- `sherpa-onnx-native-lib-win-x64-1.13.8.jar`, `sherpa-onnx-1.13.8.aar`, e as dezenas de tarballs
  linux/android.

**INFERÊNCIA MINHA de alto valor:** um `.exe` de streaming auto-contido significa que **o sherpa pode
ser testado nesta caixa sem compilar nada e sem tocar no Python** — é o caminho de custo mais baixo
para responder à pergunta do §5.2. E o build **CUDA 13 / cuDNN 9** encaixa exactamente nas DLLs que a
caixa já tem em `site-packages\nvidia\cu13\bin\x86_64` (§1).

---

## 6. Quanto se ganharia se a GPU entrasse — por modelo

Regra: **não invento percentagens.** "Muito / pouco / não sei", com o que decide.

| modelo | ganho com GPU | porquê | o que decide |
|---|---|---|---|
| **nemotron int8 (ao vivo)** | **NÃO SEI — e a GPU já está ligada à sessão** | o EP está na lista (medido); se *trabalha* não está provado | perfil por nó (`enable_profiling=True`) |
| **nemotron int4** | **POUCO, ou NEGATIVO** | o repo mede que `MatMulNBits` int4 é ~12× mais rápido no CPU EP (`qwen_summary.py:20`,`:100`) | mesma medição, no encoder int4 |
| **nemotron fp16/fp32** | **MUITO** | densos, grandes (1,25 / 2,48 GB) | não usados em produção; irrelevante |
| **Parakeet Redux (ONNX int4)** | **MUITO** | corre hoje em `['CPUExecutionProvider']` (medido), é batch/denso/sem estado, 344 MB | `redux_live.py --engine onnx` com `--providers CUDAExecutionProvider,…` no mesmo `--wav` |
| **Parakeet Redux (ternário)** | **POUCO** | o gargalo medido é o **desencriptar 193 camadas** para a forma dense (3,90 GB), não o matmul; e `--device cuda` não foi verificado | correr `redux_batch.py --device cuda` |
| **TDT v3 (sherpa/whisper.cpp)** | **MUITO** | batch, denso, sem estado, encoder 652 MB | o mesmo teste do Redux |
| **qwen3.5-0.8b / qwen3-0.6b (resumo)** | **POUCO, provavelmente** | int4 `MatMulNBits`; e o genai instalado é só-CPU | instalar `onnxruntime-genai-cuda` e medir tokens/s |
| **embeddings** | **MUITO** | encoders densos, batch, sem estado | teste trivial, um `--wav`/texto |

**A conclusão transversal:** o ganho de GPU **não é uma propriedade da caixa, é uma propriedade do
modelo**. Os modelos **int4 `MatMulNBits`** são o caso onde a GPU pode perder; os **int8 e fp16
densos e batch** são onde ela ganha. Isto inverte a intuição de "GPU é sempre melhor" e explica
porque é que a mesma caixa pode ter o motor ao vivo bem servido e o motor de fundo mal servido.

---

## 7. Veredicto por modelo

| modelo | o backend é o melhor? | veredicto |
|---|---|---|
| nemotron int8 (ao vivo) | ORT (enc/dec/joint) + ORT-GenAI (mel/VAD) + laço RNNT Python | **SIM** — com (4a) tirar o TRT da lista e (4b) medir a atribuição por nó |
| nemotron int4 / fp16 / fp32 | ORT | **SIM** para o int4/int8; o **fp16 é órfão** (sem `genai_config.json`) |
| Parakeet Redux (papel "leve") | **ONNX int4 em ORT** | **SIM** — 615 MB vs 3,90 GB de RAM |
| Parakeet Redux (ternário) | kestrel | **SIM para paridade/oráculo**, NÃO para o papel "leve" |
| Parakeet TDT v3 | ORT + laço próprio | **NÃO SEI se é o melhor** — o `sherpa-onnx` traz timestamps que não temos. Custo de mudar: ~1 dia, risco baixo |
| qwen3.5-0.8b / qwen3-0.6b | ORT-GenAI forçado a CPU | **NÃO SEI** — a decisão pode estar certa, a justificação está errada; medição nomeada no §3.5 |
| embeddings | ORT | **SIM** (não usados ainda) |

---

## 8. O que mudaria de maior valor, por ordem

Ordenado por **(valor × barateza)**, não por ambição.

| # | mudança | custo | risco | o que se perde | porque nesta posição |
|---|---|---|---|---|---|
| **1** | **Apagar a frase falsa do CUDA no `AGENTS.md`** e corrigir os números de linha (`rerun` agora é `:3637`, não `:2654`) | **30 min** | nenhum | nada | Todo o agente carrega este ficheiro; uma linha falsa aqui já produziu **duas** decisões erradas a jusante (o CPU forçado no `qwen_summary` e a crença de que a caixa corre em CPU). É a mudança mais barata com o maior efeito multiplicador. |
| **2** | **Reescrever a justificação do CPU forçado em `qwen_summary.py:1029-1035`** e decidir com a medição (instalar `onnxruntime-genai-cuda`, medir tokens/s com e sem `--force-cpu`) | **2 h** | baixo | nada | A decisão pode ficar igual — mas deixa de estar apoiada em duas premissas que o próprio worker refuta em produção. |
| **3** | **Medir a atribuição de nós por EP no encoder ao vivo** (`enable_profiling=True`, contar nós CUDA vs CPU) | **1 h** | nenhum | nada | É a única medição que separa "a GPU está na lista" de "a GPU trabalha". Decide o §6 para o motor principal. |
| **4** | **Adoptar `sherpa-onnx` como segunda implementação do TDT, para timestamps por token** (pesos já em disco, pacote já instalado, correr em processo separado por causa do §5.3) | **~1 dia** | baixo | nada | Acrescenta uma capacidade inexistente (tempo por palavra), dá um oráculo cruzado ao nosso laço TDT, e não toca em nada que funcione. |
| **5** | **Testar o `sherpa-onnx-streaming-asr-x64-v1.13.8.exe`** contra o Nemotron streaming, e responder ao §5.2 (existe `language` por stream?) | **2–4 h** | baixo | nada | Resolve a única dúvida aberta sobre o motor ao vivo, sem compilar nada e sem tocar no Python. |
| **6** | **Levar o Redux ONNX ao CUDA EP e medir** (o `redux_live.py` já tem o caminho; só falta o provider) | **2 h** | baixo | nada | É o modelo onde o ganho de GPU é mais provável (§6) e o que faz o papel de "transcritor de fundo" — onde a CPU é o recurso disputado. |
| **7** | **Marcar o `nemotron-...-fp16` como não-utilizável pelo genai** (não tem `genai_config.json`) e decidir o destino do `fp32` | **15 min** | nenhum | nada | Evita que alguém o seleccione e apanhe um `og.Model` a falhar. |
| **8** | **Decidir o `qwen3-0.6b-arm-int4`** (ler o cabeçalho do grafo; é QNN/ARM ou é nome?) | **30 min** | nenhum | 472 MB se for inútil | 472 MB em disco e um `provider_options` vazio são um convite a um erro silencioso. |
| **9** | **Resolver o `embeddinggemma-2`** — a busca por directório estava a correr e não terminou | **15 min** (relançar) | nenhum | nada | O brief afirma que existe "as embeddings"; não encontrei cache nenhum. **Não afirmo ausência** — o instrumento ainda não respondeu. |
| **10** | **Instalar o toolkit CUDA 13 e experimentar o TensorRT EP** | **~3 GB + 1 dia**, e um engine por forma de cache | **alto** | tempo e disco | Última da lista de propósito: no Nemotron streaming as formas de cache mudam, o que torna o cache de engines problemático, e o ganho sobre o CUDA EP já ligado é incerto. **Não é onde eu gastaria o dia.** |

### O que eu NÃO faria

- **Não trocaria o ORT pelo `sherpa-onnx` no motor ao vivo.** O ORT é o único que expõe as caches e
  o `lang_id` sem escrever C++, e o `sherpa` instalado nem sequer mostra o prompt de língua (§5.2).
- **Não instalaria `onnxruntime-genai-cuda` à espera de ganho no motor ao vivo.** O genai faz o mel
  e o VAD; o encoder é ORT puro (§3.1). O ganho, se existir, é no `qwen_summary`.
- **Não escolheria o ternário para o papel "leve".** 3,90 GB de pico contra 615 MB é a resposta (§3.3).
- **Não instalaria TensorRT-LLM.** Não é um motor de ASR (§4).

---

## 9. O que NÃO foi medido — com o instrumento que o decidiria

Sendo explícito, porque a regra da casa é que a ausência precisa de instrumento:

1. **Atribuição de nós por EP no encoder ao vivo** → perfil ORT (`enable_profiling=True`). §3.1(4b).
2. **Se o `sherpa-onnx` 1.13.4 honra `set_option("language", …)` no online transducer** →
   `stream.has_option("language")` num stream real, ou `online-transducer-model.cc` no master. §5.2.
3. **Se o `sherpa-onnx` 1.13.4 consegue sequer carregar o Nemotron streaming** → carregar
   `worker/models/nemotron-...-int8` no `OnlineRecognizer.from_transducer`. Não feito (modelo pesado).
4. **A identidade do build sherpa instalado** (`git_sha1()`/`git_date()`) → as duas tentativas
   falharam por `SyntaxError` do `-c` do `Start-Process`; o valor de `__version__` está medido
   (`1.13.4+cuda12.cudnn9`), o SHA do commit **não**.
5. **Onde vivem os pesos do `embeddinggemma-2`** → busca por directório, em curso (job `pwsh-1995`).
6. **O ganho real de GPU no Redux/TDT** → correr o mesmo `--wav` com e sem `CUDAExecutionProvider`.
7. **Se o `qwen3-0.6b-arm-int4` é ARM/QNN** → cabeçalho do grafo + `model.device_type`.
8. **Timestamps por palavra no TDT via sherpa** → o exemplo oficial promete `result.timestamps` e
   `result.durations`; **não corrido aqui**.
9. **Áudio >30 s e o segmentador VAD no Redux** → os clipes de referência tinham <15 s.
10. **A coexistência `sherpa` + `genai` num processo de produção** → medida em três braços de
    import (§5.3), mas não num worker real.

---

## 10. Fontes citadas

- ONNX Runtime GenAI — instalação (`onnxruntime-genai-cuda`, `-directml`):
  <https://onnxruntime.ai/docs/genai/howto/install.html>
- sherpa-onnx release **v1.13.8** (assets Windows x64 CUDA 13/cuDNN 9 e `streaming-asr-x64.exe`):
  <https://github.com/k2-fsa/sherpa-onnx/releases/tag/v1.13.8>
- sherpa-onnx — exemplo oficial TDT `nemo_transducer` com timestamps:
  <https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/python-api-examples/offline-nemo-parakeet-decode-file.py>
- sherpa-onnx — modelos Nemotron 3.5 streaming e o prompt de língua por stream:
  <https://huggingface.co/csukuangfj2/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-2026-06-11/raw/main/README.md>,
  <https://huggingface.co/Masterx/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-320ms-2026-06-11/raw/main/README.md>
- whisper.cpp ≥ 1.9 `parakeet-cli` + GGUF do TDT v3:
  <https://huggingface.co/JoaoZaokk/parakeet-tdt-0.6b-v3-ggml/raw/main/README.md>
- TensorRT-LLM — suporte a Whisper (PR) e modelos encoder-decoder:
  <https://github.com/NVIDIA/TensorRT-LLM/pull/16141/files/9a000d7006d638c163e73933f4f7698c831c5d4c>,
  <https://nvidia.github.io/TensorRT-LLM/1.3.0rc25/models/encoder-decoder.html>
- sherpa-onnx — binários pré-compilados Windows x64:
  <https://k2-fsa.github.io/sherpa/onnx/install/windows/generated/download/windows_x64.html>
