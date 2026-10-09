# Recibo — Execution Providers (EP) do ONNX Runtime nesta máquina, medidos

**Lane:** `execution-providers` (delegada). **Data:** 2026-10-08.
**Pergunta do dono, verbatim:** *"pesquisa as engines e etc, todo backend, que deveria ser usado pra cada
modelo que temos. veja se tu ta com a melhor stack e escolhas realmente"*.
**Alcance desta lane (o do pai, verbatim):** *"e tu e obrigado a fazer a gpu dos usuarios, qualquer
usuario, funcionar"* — não "fazer a 5080 dele funcionar": **a GPU de QUALQUER usuário tem de funcionar.**
**Escrita:** só em `H:\sotto\_main\`. Nada foi morto. Nada foi aberto em dispositivo de áudio. Nenhuma
janela visível foi deixada.

---

## 0. Resposta directa — SIM ou NÃO

**SIM. O ORT usa a GPU nesta máquina, e não é só "anexada": ela EXECUTA.**

Três níveis de prova, do mais fraco ao mais forte. **Os três são instrumentos diferentes e respondem
perguntas diferentes** — não os confundir é metade deste recibo.

| # | pergunta | instrumento | resposta verbatim |
|---|---|---|---|
| 1 | o *pacote* oferece CUDA? | `ort.get_available_providers()` | `['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']` |
| 2 | a *sessão* usa CUDA? | `InferenceSession.get_providers()` | `["CUDAExecutionProvider", "CPUExecutionProvider"]` |
| 3 | a CUDA **executa** nós, ou só está anexada? | profiler do ORT (`enable_profiling=True`), contagem de eventos `cat=="Node"` por `args.provider` | encoder: **1792 de 1793 nós na CUDA (99,94 %)**, 100,0 % do tempo |

O nível 3 é o que o pai pediu explicitamente (*"no int8 ao vivo a GPU está ligada à sessão, mas se
*trabalha* não se sabe"*) e é o único que responde. **Uma sessão pode reportar
`['CUDAExecutionProvider','CPUExecutionProvider']` e correr todos os nós na CPU** — foi exactamente o que
o `dml` fez (ver §4), e é por isso que `get_providers()` sozinho não serve como prova.

### 0.1 Atribuição de nós por EP — instrumento `_ep_nodes.py`, cadência pontual, 1 inferência por grafo

| grafo | EP pedido | `nodes_total` | `nodes_by_provider` | `%nós` | `%tempo` | veredicto |
|---|---|---|---|---|---|---|
| `encoder.onnx` | CUDA | 1793 | `{CUDA: 1792, CPU: 1}` | 99,94 / 0,06 | 100,0 / 0,0 | **GPU-EXECUTES** |
| `decoder.onnx` | CUDA | 11 | `{CUDA: 11}` | 100 / 0 | 100 / 0 | **GPU-EXECUTES** |
| `joint.onnx` | CUDA | 11 | `{CUDA: 11}` | 100 / 0 | 100 / 0 | **GPU-EXECUTES** |
| `encoder.onnx` | CPU (**controlo positivo**) | 1800 | `{CPU: 1800}` | 100 / 0 | 100 / 0 | controlo OK |

O único nó de CPU no encoder é `Tile`, 94 µs — ruído de fronteira, não trabalho.
`top_cpu_kernels_us: [["Tile", 94]]`.
**Nota de leitura do instrumento:** o campo `verdict` diz *"o EP PEDIDO executa"*, por isso a linha de
controlo (CPU) também lê `GPU-EXECUTES`. Ler `nodes_by_provider`, não o rótulo, na linha de controlo.
Ficheiros de perfil: `H:\sotto\ortprof_encoder_2026-10-07_12-42-20_631.json` (e os irmãos de decoder/joint).

### 0.2 Prova ponta-a-ponta no caminho de PRODUÇÃO (a evidência mais forte)

Instrumento: o **próprio `--selftest`** do worker, lançado por `_hidden_run.py` sob
`Start-Process -Wait`, com `--config H:\sotto\worker\config.json` real, o áudio
`_main\pt-br-sample.wav`, `--threads 4`, ambiente da app (`C:\Program Files\Python311\python.exe`).
Cadência: 1 execução por EP. Isto não é um probe meu a imitar o worker — é o worker.

| braço | `providers_selected` | `state=model-loaded providers` | `note` | `load_s` | `rss_mb` | `peak_rss_mb` |
|---|---|---|---|---|---|---|
| CPU | `["CPUExecutionProvider"]` | `["CPUExecutionProvider"]` | `cuda-not-registered` | 23,48 | 2089,2 | 2108,1 |
| CUDA | `["CUDAExecutionProvider"]` | `["CUDAExecutionProvider","CPUExecutionProvider"]` | `""` (limpo) | **5,81** | **1665,6** | **1684,8** |

Ambos os braços: `providers_available ["TensorrtExecutionProvider","CUDAExecutionProvider","CPUExecutionProvider"]`,
`cuda_probe_model "nemotron-3.5-asr-streaming-0.6b-int8"`, `cuda_dirs_ms` 2070/1719,
`provider_probe_ms` 62/476, `lang_id 101`, `lang "auto"`, `lang_input "lang_id"`.

**Duas consequências medidas que não estavam previstas:**
- **CUDA carrega 4,04× mais rápido** (5,81 s vs 23,48 s).
- **CUDA usa ~423 MB MENOS de RSS de host** (1665,6 vs 2089,2). O custo do CUDA nesta caixa é
  **disco**, não RAM — o que muda a decisão de "o que embarcar" (§5).

**Paridade de transcrição no caminho de produção é EXACTA** — os dois braços produzem **streams de
legenda byte-idênticos**, incluindo as duas linhas `final=True`:
`rádio anunciou que a ponte sobre o vai ser interditada na próxima segunda-feira.  Os` (start 0.56) e
`moradores precim de um caminho alternativo para chegar ao trabalho` (start 8.96).
Mesma sequência de fragmentos, mesma ordem. **Trocar o EP não muda uma letra no caminho real.**

---

## 1. Instrumentos, cadência e contagem (regra da casa: nomear o instrumento)

Todos criados por esta lane, todos em `H:\sotto\_main\`.

| instrumento | bytes | sha256 (16) | o que mede | cadência / contagem |
|---|---|---|---|---|
| `_ep_probe.py` | 2290 | `EFBA91A810521D02` | censo de EPs; `get_providers()` real de uma sessão; modos `--census`, `--cuda-dlls`, naive | 1 sessão por invocação |
| `_ep_bench.py` | 8419 | `A718ACFA6E12B7AA` | latência por chunk, RTF, núcleos usados, RSS, CPU%, GPU%, sha256 do texto. Espelha o braço de ficheiro do worker chunk-a-chunk | `--reps` passagens; amostrador de GPU a **0,1 s** (`nvidia-smi`) |
| `_ep_chain.py` | 5451 | `904A86F83B8F2FBF` | a **cadeia de fallback**: que EP é escolhido, e porquê, nível a nível | 1 sonda por nível, `encoder.onnx` |
| `_ep_nodes.py` | 5947 | `1CFB3C471A7879CD` | **atribuição de nós por EP** via profiler do ORT | 1 inferência por grafo |
| `_hidden_run.py` | 994 | `BB1EF2E72788448B` | lançar `pythonw.exe` com `creationflags 0x08000000` e capturar stdout | 1 execução por invocação |

**Trap do instrumento, medida e documentada:** `_ep_bench.py`'s `tokens_total` e `text_chars`
**ACUMULAM ao longo de `--reps`** (70/151 com `reps=1`, 144/306 com `reps=2`). **NÃO são métricas de
paridade nem de qualidade.** A paridade assenta nos braços `--selftest` byte-idênticos (§0.2);
`text_head` é estável e é a comparação utilizável.

**Trap do instrumento 2:** `pythonw.exe` é subsistema GUI, portanto o operador `&` do PowerShell
**retorna imediatamente sem esperar**. Sem `Start-Process -Wait` os ficheiros de saída parecem "nunca
criados" quando estão apenas a ser escritos. E `pythonw.exe` tem `sys.stdout is None`, pelo que
redireccionamento de shell produz **ZERO bytes**.

### 1.1 Ficheiros de log criados (todos em `_main\_ep-logs\`, com sha256(16))

```
bench-appcpu.json        1409 B  FF572616E1F94AEE      chain-cpu-nogpu.json    1381 B  039BD1835CA051C6
bench-appcuda.json       1494 B  AE31A1433D9CA44A      chain-dml-prefer.json   1459 B  C930251B56F2C4C6
bench-cpu-1t.json        1419 B  3C64853429BF9E4D      chain-gpu-forcedrop.json 1126 B CDC9DE56CECBC8C1
bench-cpu-2t.json        1427 B  2535530CC575CF80      chain-gpu-prefer.json   1171 B  B9D89C8DF3018C95
bench-cpu-4t.json        1416 B  9AA30E72996049E0      nodes-encoder-cuda.json 1403 B  E49182EAEF025DBA
bench-cpu-4t-conf.json   1428 B  BD056DF0A5B96A16      nodes-encoder-cpu.json  1562 B  E8C0B85F2239ED79
bench-cpu-8t.json        1415 B  3B8F89892BAE123C      nodes-decoder-cuda.json  917 B  7C02CF4F8C7D092B
bench-cpu-8t-conf.json   1428 B  4F8903AC820C49AA      nodes-joint-cuda.json    853 B  BE7DCEB7B76FD68C
bench-cuda-2t.json       1399 B  88D05F488EE1B1EA      selftest-cpu.jsonl      6356 B  566FDA565494515C
bench-gpu-1t.json        1383 B  D9F048743C49885E      selftest-cuda.jsonl     6386 B  5FD657EF59DA1222
bench-gpu-2t-conf.json   1389 B  F3A5B23694228022      dml-verbose.txt        87399 B  8C803513CEA8644D
bench-gpu-4t.json        1373 B  D9367EA4F42198B7      dml-verbose0.txt       89350 B  2CCC3B5BBA3E9C4D
bench-gpu-4t-conf.json   1388 B  4F225D82278C24E3
bench-gpu-8t.json        1367 B  F6BEF66F3975523D
```
(`.txt` gémeos de cada `.json` existem com o mesmo conteúdo impresso; sha256 diferentes por diferença de
terminador.) Os dois `selftest-*.jsonl` são UTF-8 válido, terminações `\n`, **44 linhas cada**.

---

## 2. Tabela provider × (latência, CPU%, GPU%, RSS) — incluindo a linha de base CPU

Máquina: 20 núcleos lógicos, 20 físicos. Modelo: `nemotron-3.5-asr-streaming-0.6b-int8`.
Áudio: `pt-br-sample.wav` (15,00 s, 26 chunks). `--warmup-chunks 2`.

**AVISO QUE MANDA NA LEITURA — a caixa estava CONTENCIOSA.** Esta máquina corre a app do dono
(shell 28428 + worker 29008) e outras lanes ao mesmo tempo. Os números "carregados" e os "quietos"
(`-conf`) estão **20× afastados** entre si para o MESMO braço. **A estatística robusta é a RAZÃO
CUDA:CPU medida de seguida na mesma passagem, não o RTF absoluto.**

### 2.1 Braços quietos (`-conf`) — a leitura utilizável

| tag | provider real | thr | rtf_best | chunk_med_ms | núcleos usados | RSS pico MB | CPU% proc | CPU% sist | GPU% méd | headroom live (560 ms) | core·s / audio·s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **appcuda** | CUDA+CPU | 4 | **0,1256** | 70,27 | 4,78 | 2406,1 | 478,7 | 92,5 | 46,4 | **8,0×** | **0,600** |
| appcpu | CPU | 4 | 0,6667 | 470,92 | 12,16 | 2435,4 | 711,9 | 95,6 | 27,8 | 1,19× | 8,107 |
| cpu-4t-conf | CPU | 4 | 0,8037 | 414,26 | 8,31 | 2051,8 | 831,0 | 99,6 | 28,6 | 1,35× | 6,679 |
| cpu-8t-conf | CPU | 8 | 1,1977 | 671,79 | 11,85 | 2054,4 | 1183,6 | 98,6 | 29,0 | **0,83×** | 14,193 |
| gpu-2t-conf | CUDA+CPU | 2 | **0,0963** | 57,78 | 4,83 | 1947,6 | — | — | 37,4 | **9,7×** | **0,465** |
| gpu-4t-conf | CUDA+CPU | 4 | **0,0926** | 54,97 | 5,47 | 1950,4 | — | — | 34,1 | **10,2×** | **0,507** |

### 2.2 Braços carregados (contaminados — mantidos por completude e para mostrar o tamanho da contaminação)

| tag | provider real | thr | rtf_best | chunk_med_ms | núcleos usados | RSS pico MB | CPU% proc | GPU% méd | core·s / audio·s |
|---|---|---|---|---|---|---|---|---|---|
| cpu-1t | CPU | 1 | 15,2348 | 4913,81 | 0,28 | 2049,3 | 27,8 | 17,5 | 4,266 |
| cpu-2t | CPU | 2 | 5,1920 | 1619,86 | 1,20 | 2050,7 | 120,2 | 17,3 | 6,230 |
| cpu-4t | CPU | 4 | 6,9446 | 3373,10 | 1,54 | 2051,3 | 153,8 | 28,8 | 10,695 |
| cpu-8t | CPU | 8 | 4,6772 | 2617,31 | 4,16 | 2052,9 | 416,3 | 27,0 | 19,457 |
| cuda-2t | CUDA+CPU | 2 | 1,7249 | 686,99 | 0,49 | 1936,8 | — | 20,2 | 0,845 |
| gpu-1t | CUDA+CPU | 1 | 2,0306 | 966,07 | 0,39 | 1533,0 | — | 22,9 | 0,792 |
| gpu-4t | CUDA+CPU | 4 | 0,1912 | 99,20 | 3,04 | 1938,0 | — | 29,6 | 0,581 |
| gpu-8t | CUDA+CPU | 8 | 0,1326 | 72,99 | 3,76 | 1952,9 | — | 30,0 | 0,499 |

### 2.3 O que a coluna GPU% NÃO prova (e por que está aqui)

`GPU% méd` vale **17–30 % em TODOS os braços, inclusive os puramente CPU** — porque a 5080 já está a
servir a app do dono (4,4–6,4 GB em uso). **`gpu_util` NÃO é discriminador nesta caixa.** O `gpu_mem_mb_max`
de 6444 MB é dominado por essa carga pré-existente, não pela minha sessão. A prova de que a GPU trabalha
é a **contagem de nós** (§0.1), não a utilização.

### 2.4 Lacuna declarada (SKIP não é passe)

`cpu_percent_process` está **em branco** nos braços da família `gpu*` — `psutil` não estava instalado
nesse venv. **Não medi o CPU% do processo nesses braços.** O que compensa é `cores_used_infer`
(tempo de CPU do processo / tempo de parede), que é uma medida independente e está presente.

### 2.5 A joelheira de threads e a devolução de núcleos (o congelamento do dono)

A joelheira `intra_op_num_threads=4` foi medida **na CPU**. Com GPU a joelheira muda de sítio:

- **CPU 4t:** 6,68–8,11 **core·s por audio·s**; headroom live 1,19–1,35× — marginal.
- **CPU 8t** (o default automático do worker: `min(8, 20//2)` = 8): 671,79 ms de chunk mediano contra
  560 ms de chunk de áudio = **0,83×, NÃO acompanha o tempo real.**
- **CUDA 4t:** 0,51–0,60 **core·s por audio·s**; headroom live 8–10×.

**Núcleos devolvidos à máquina: ~6 a ~14**, conforme o braço de CPU contra o qual se compara.
Isto é a cura do congelamento que o dono reportou, e é a razão pela qual
**com GPU funcional a reserva de ~5–8 núcleos do ASR pode ser levantada.**

---

## 3. Caminho recomendado — os passos exactos que corri, e o resultado de cada um

### 3.1 A receita de instalação: a ARMADILHA, e a correcção. Ambas as cores, medidas

Este é o achado mais accionável deste recibo, e **contradiz a receita ingénua que qualquer pessoa
escreveria.**

**COR VERMELHA — a receita ingénua, em venv limpo (`gpu2`):**
```powershell
& 'C:\Program Files\Python311\python.exe' -m venv H:\sotto\_main\_epvenvs\gpu2
& H:\sotto\_main\_epvenvs\gpu2\Scripts\python.exe -m pip install --no-cache-dir --progress-bar off "onnxruntime-gpu[cuda,cudnn]" onnxruntime-genai
```
O pip regista `Installing collected packages: …, onnxruntime-gpu, onnxruntime, …, onnxruntime-genai, nvidia-cudnn-cu13`
— **o `onnxruntime` simples é instalado DEPOIS do build GPU** (é dependência dura do `onnxruntime-genai`).
Resultado medido:
- `_ep_probe.py --census` → `available: ["AzureExecutionProvider","CPUExecutionProvider"]`
- sessão CUDA real sobre `encoder.onnx` com `_add_cuda_dll_dirs()` → `REAL_get_providers: ["CPUExecutionProvider"]`, `error: null`, `load_s: 1.802`
- `UserWarning: Specified provider 'CUDAExecutionProvider' is not in available provider names.Available providers: 'AzureExecutionProvider, CPUExecutionProvider'`

**O `error` é `null` e a carga "sucede": ORT fica CPU-only em SILÊNCIO.** É a pior classe de falha.

**Prova de propriedade (por que isto acontece), por RECORD do wheel:**
| dist-info | entradas `onnxruntime/capi/` | entradas `providers_cuda` |
|---|---|---|
| `onnxruntime-1.30.0.dist-info` | 21 | **0** |
| `onnxruntime_gpu-1.30.0.dist-info` | 23 | **1** |

O wheel simples **sobrescreve 21 ficheiros partilhados e deita fora o `providers_cuda`**. Os três
pacotes instalam-se no **mesmo namespace `onnxruntime`** e quem ganha é **a ORDEM do pip** (último
escritor ganha, ficheiro a ficheiro).

**COR VERDE — a receita corrigida, no MESMO venv, uma linha:**
```powershell
& H:\sotto\_main\_epvenvs\gpu2\Scripts\python.exe -m pip install --no-cache-dir --progress-bar off --force-reinstall --no-deps onnxruntime-gpu==1.30.0
```
Resultado medido:
- `_ep_probe.py --census` → `available: ["TensorrtExecutionProvider","CUDAExecutionProvider","CPUExecutionProvider"]`
- `_ep_probe.py --cuda-dlls <modelo>\encoder.onnx CUDAExecutionProvider` → `REAL_get_providers: ["CUDAExecutionProvider","CPUExecutionProvider"]`, `error: null`, `load_s: 2.254`, stderr `CUDA_DLL_DIRS: applied`

**A ÚNICA variável era a ordem de instalação.** Os extras `[cuda,cudnn]` fizeram o seu trabalho
correctamente: `nvidia-cublas 13.8.0.4`, `nvidia-cudnn-cu13 9.27.0.42`, `nvidia-cufft 12.4.0.43`,
`nvidia-curand 10.4.4.72`, `nvidia-cuda-nvrtc 13.4.92`, `nvidia-cuda-runtime 13.4.92`,
`nvidia-nvjitlink 13.4.92` — todos instalados, e
`…\gpu2\Lib\site-packages\nvidia\cu13\bin\x86_64\cublasLt64_13.dll` presente a **493 474 416 B**.

**Detalhe que engana:** `onnxruntime-gpu 1.30.0`'s METADATA declara o runtime CUDA como **EXTRAS
OPCIONAIS, não dependências duras** — `nvidia-cuda-nvrtc~=13.0; extra == "cuda"`,
`nvidia-cuda-runtime~=13.0; extra == "cuda"`, `nvidia-cufft~=12.0; extra == "cuda"`,
`nvidia-curand~=10.0; extra == "cuda"`, `nvidia-cudnn-cu13~=9.0; extra == "cudnn"`; as dependências
duras são só `flatbuffers`, `numpy>=1.21.6`, `packaging`, `protobuf>=4.25.8`. **`nvidia-cublas` não é
nomeado em NENHUM dos extras** — e no entanto `cublasLt64_13.dll` é exactamente a DLL que faltava. A
cadeia resolve transitivamente: `nvidia-cudnn-cu13` → `nvidia-cublas` → `nvidia-cuda-nvrtc`.
O RECORD do próprio wheel do ORT **não contém entradas `nvidia`** — ele não traz runtime CUDA nenhum.

### 3.2 O caminho CUDA desta caixa é FUNCIONAL, não ausente

O `AGENTS.md` dizia o contrário e foi corrigido a montante enquanto esta lane trabalhava (§6). O que é
verdade, medido:
- uma sessão que pede CUDA numa **shell limpa** cai para CPU por **exactamente UMA DLL**: `cublasLt64_13.dll`, WinError 126.
  Texto verbatim do ORT:
  `onnxruntime::ProviderLibrary::Get [ONNXRuntimeError] : 1 : FAIL : Error loading "...\onnxruntime\capi\onnxruntime_providers_cuda.dll" which depends on "cublasLt64_13.dll" which is missing. (Error 126: "Não foi possível encontrar o módulo especificado.")`
  mais `Failed to create CUDAExecutionProvider. Require cuDNN 9.* and CUDA 13.*, and the latest MSVC runtime.`
- **uma directoria resolve**: `site-packages\nvidia\cu13\bin\x86_64` no caminho de busca de DLLs.
  (`torch\lib` é CUDA **12** e NÃO serve.)
- **o worker já faz isto**: `worker/sotto_worker.py:277` (`_add_cuda_dll_dirs()`), chamado de `:3251`
  antes da carga do modelo. Revisão verificada: **242 082 B, mtime 2026-10-07T13:09:59,
  sha256 `64E7EC6F6C35C33600E9D50C11AC7D8CE96FBE1FEF87C24CD628BDF03F314E61`**.

**Consequência para a decisão:** um veredicto de "não há GPU utilizável nesta caixa" é **FALSO**.

### 3.3 A cadeia de fallback — as quatro cores, medidas

Instrumento `_ep_chain.py`, `--threads 2`, sonda `encoder.onnx`. `startup_log_line` verbatim:

```
chain-dml-prefer  (venv dml)
EP_CHAIN chosen=CPUExecutionProvider available=DmlExecutionProvider,CPUExecutionProvider
  trace=DmlExecutionProvider:silently-dropped (session fell back to ['CPUExecutionProvider'])
      > CUDAExecutionProvider:not-registered (package does not offer it)
      > CPUExecutionProvider:OK

chain-gpu-prefer  (venv gpu)
EP_CHAIN chosen=CUDAExecutionProvider available=TensorrtExecutionProvider,CUDAExecutionProvider,CPUExecutionProvider
  trace=DmlExecutionProvider:not-registered (package does not offer it)
      > CUDAExecutionProvider:OK

chain-gpu-forcedrop  (venv gpu, --force-fail 0)   ← A COR FORÇADA
EP_CHAIN chosen=CPUExecutionProvider available=TensorrtExecutionProvider,CUDAExecutionProvider,CPUExecutionProvider
  trace=CUDAExecutionProvider:FORCED-FAIL (instrument: this level was told to fail)
      > CPUExecutionProvider:OK

chain-cpu-nogpu  (venv cpu)                       ← "qualquer utilizador sem GPU nenhuma"
EP_CHAIN chosen=CPUExecutionProvider available=AzureExecutionProvider,CPUExecutionProvider
  trace=DmlExecutionProvider:not-registered (package does not offer it)
      > CUDAExecutionProvider:not-registered (package does not offer it)
      > CPUExecutionProvider:OK
```

**A cadeia cai bem.** O braço `forcedrop` é a prova em cor forçada: quando se diz ao nível CUDA para
falhar, a cadeia **desce e ainda transcreve** — e regista a razão. O braço `cpu-nogpu` é o caso "sem GPU
nenhuma": nenhum EP de GPU está registado, a cadeia desce para CPU, e o ORT **não levanta** — degrada.

**O que a cadeia NUNCA pode fazer:** usar `get_available_providers()` para decidir o que foi usado.
O `chain-dml-prefer` é o contra-exemplo vivo: o DML **está registado e disponível**, a sessão foi criada,
e mesmo assim caiu para CPU em silêncio. O `_ep_chain.py` regista o `get_providers()` **real** em cada
nível, e é por isso que apanha o `silently-dropped`.

### 3.4 Onde a cadeia vive no código de produção

`worker/sotto_worker.py`: `choose_providers(requested, model_dir=None)` em `:1734` →
`(providers, available, note, probed_model)`, com a sonda de vivacidade CUDA em `:1788-1800`; chamado de
`:3253`, depois de `_add_cuda_dll_dirs()` em `:3251`. `providers_selected=providers` em `:3262`.
As três notas de diagnóstico: `:1795 "cuda-registered-but-not-loadable"`,
`:1800 f"cuda-unavailable: {type(exc).__name__}: {str(exc)[:160]}"`, `:1802 "cuda-not-registered"`.
`StreamAsr.__init__` em `:458`; `self.providers = self.enc.get_providers()` em `:505` — **o real, não o
disponível.** `state="model-loaded"` com `providers=asr.providers` em `:3290-3297`.

**`worker/config.json` linha 14:** `"providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]`.

### 3.5 O que se perde com DirectML vs CUDA, e o que se perde na CPU

**DirectML vs CUDA** — DirectML perde **o encoder inteiro**, e portanto não é um caminho mais lento: é um
caminho que **não existe** para este modelo. Ver §4. O que o DirectML *ganharia* (ser vendor-neutral:
servir NVIDIA, AMD e Intel) é exactamente o que ele não entrega aqui.

**Na CPU perde-se:**
- **Velocidade:** RTF 0,67–0,80 vs 0,09–0,13 → **~7× a ~8,7× mais lento** (quieto).
- **Headroom live:** 1,19–1,35× a 4t, **0,83× a 8t** — a 8t a transcrição **fica atrás do tempo real**.
- **Núcleos:** 6,68–14,19 core·s por audio·s vs 0,47–0,60 → **~6 a ~14 núcleos** que a máquina não tem.
- **Tempo de carga:** 23,48 s vs 5,81 s.
- **RAM de host:** +423 MB.
- **Qualidade:** **NÃO se perde qualidade.** A paridade no caminho de produção é byte-idêntica (§0.2).

**Nota honesta sobre uma divergência real:** no `_ep_bench.py` (não no worker) o CUDA produz
`aponte` onde a CPU produz `a ponte`. Reproduz no mesmo venv e nas duas famílias de venv. É
não-determinismo de ponto flutuante do EP numa decisão greedy no fio da navalha, e **o CUDA está do lado
PIOR**. No `--selftest` do worker, que é o caminho que embarca, os dois braços são **byte-idênticos**.
Reporto a divergência porque é real; não a apresento como custo do CUDA no produto.

---

## 4. O que NÃO consegui fazer, com o erro exacto

### 4.1 DirectML não pode embarcar hoje — três bloqueios independentes, todos medidos

**Bloqueio 1 — dependência insatisfazível:**
```
ERROR: Could not find a version that satisfies the requirement onnxruntime-directml>=1.26.0
```
`onnxruntime-genai-directml 0.14.1` exige `onnxruntime-directml>=1.26.0`; o mais recente no PyPI é
**1.24.4**. A variante DirectML do genai **não é instalável na versão que faz falta**.

**Bloqueio 2 — parede de versão de API no caminho de salvamento:**
`onnxruntime-genai==0.17.1 --no-deps` sobre `onnxruntime-directml==1.24.4` (venv `dml2`) falha no import:
```
The requested API version [26] is not available, only API versions [1, 24] are supported in this build. Current ORT Version is: 1.24.4
ImportError: DLL load failed while importing onnxruntime_genai: Uma rotina de inicialização da biblioteca de vínculo dinâmico (DLL) falhou.
```
E o `onnxruntime-genai-directml` que *é* instalável (0.13.1) **não abre o modelo**:
```
RuntimeError Error encountered while parsing '...\genai_config.json' JSON Error: model:encoder:inputs: Unknown value "lang_id" at line 29 index 29
```

**Bloqueio 3 — o muro de operadores (a razão REAL):** o EP DirectML **funciona**; o que ele não consegue
é **compilar o encoder**.
```
joint.onnx        → ['DmlExecutionProvider','CPUExecutionProvider']   OK
silero_vad.onnx   → ['DmlExecutionProvider','CPUExecutionProvider']   OK
encoder.onnx      → ['CPUExecutionProvider']                          FALHA
```
Texto verbatim do ORT (mascarado):
```
*************** EP Error ***************
EP Error 'utf-8' codec can't decode byte 0xe2 in position 289: invalid continuation byte when using ['DmlExecutionProvider']
Falling back to ['CPUExecutionProvider'] and retrying.
```

**DESMASCARADO** — chamei o binding de baixo nível e li `UnicodeDecodeError.object`:
```python
from onnxruntime.capi import _pybind_state as C
so = ort.SessionOptions(); so.intra_op_num_threads = 2
sess = C.InferenceSession(so, path, True, False)
try:
    sess.initialize_session(['DmlExecutionProvider'], [dict()], set())
except UnicodeDecodeError as e:
    print(e.object.decode('cp1252'))
```
(`initialize_session` é `(Sequence[str], Sequence[Mapping[str,str]], Set[str])` — passar `None` no terceiro
argumento dá `TypeError: incompatible function arguments`.) Mensagem crua, 308 bytes, descodificada em
**cp1252**:
```
[ONNXRuntimeError] : 6 : RUNTIME_EXCEPTION : Exception during initialization:
E:\_work\1\s\onnxruntime\core\providers\dml\DmlExecutionProvider\src\MLOperatorAuthorImpl.cpp(2853)
\onnxruntime_pybind11_state.pyd!00007FFEFC652FEC: (caller: 00007FFEFC672A01) Exception(1) tid(9fac)
80070057 Parâmetro incorreto.
```
**`0x80070057` = `E_INVALIDARG`** no autor de operadores do DML. Mecanismo: o texto de erro do DML sai na
codepage ANSI pt-BR e o pybind11 descodifica-o como UTF-8, pelo que um `UnicodeDecodeError` **substitui o
erro real** e o ORT larga o provider. Um re-run com `log_severity_level = 0` mostrou na mesma só as 4
linhas mascaradas — **os bytes crus são o único canal.**

**A causa, medida e decisiva — o domínio de ops contrib:**
| grafo | ocorrências do domínio `com.microsoft` | ops |
|---|---|---|
| `encoder.onnx` | **220** | `MatMulNBits`, `CausalConv1D`, `ConformerConvolution`, `ConvSubsampling`, `MaskedConvSequential`, `RelPositionMultiHeadAttention`, `RemoveOptionalBiasFromConvJ` |
| `joint.onnx` | **0** | só `MatMul` simples |

**O DirectML carrega os grafos sem contrib e falha no grafo com contrib.** Não é configuração, não é
versão, não é caminho de DLL: **é suporte de operadores que não existe a montante.** Não há nada que esta
lane possa fazer no nosso lado.

### 4.2 Não testado — e SKIP não é passe

- **`onnxruntime-gpu` num host SEM driver NVIDIA nenhum.** Não tenho tal máquina e não posso esconder a
  GPU. Os proxies mais próximos medidos são (a) o braço `cpu` (`CUDAExecutionProvider:not-registered`) e
  (b) o venv `gpu` **antes** de os wheels cu13 serem instalados (CUDA pedido, caiu para CPU em silêncio,
  sem crash). **São proxies, não o caso.**
- **DirectML num GPU AMD ou Intel real.** O bloqueio do encoder (§4.1) é independente do vendor, mas
  **não o medi num AMD/Intel** — só o inferi da censo de ops.
- **O par shell/worker de longa duração (28428/29008)** ponta-a-ponta sem perturbar a app do dono. Não fiz.
- **`onnxruntime-directml` não está instalado no ambiente da app** — só nos meus venvs.

### 4.3 Limites de permissão desta lane

Sou um subagente delegado; **o meu âmbito de permissão foi fixado no arranque e não posso alargá-lo de
dentro**. Prompts de aprovação estão desactivados: operações que precisem de aprovação são rejeitadas
automaticamente. Nenhuma operação deste recibo precisou disso — mas se a decisão de §5 exigir tocar em
`worker/`, `app/panel/` ou `app/webview/`, **isso está fora do meu âmbito** e é o pai que tem de o fazer.

### 4.4 Erros de infraestrutura encontrados pelo caminho (para o próximo não os repetir)

- **`pip install` paralelos contra a mesma cache ficam pendurados indefinidamente** (três jobs em
  paralelo, todos travados). Resolvido: **um de cada vez**, com `--no-cache-dir --progress-bar off`.
- **`pip index versions` pendura aqui** (>300 s, duas vezes). Evitar.
- **`nvidia-cublas-cu13` no PyPI é um STUB 0.0.1** (`Available versions: 0.0.1`). Os wheels CUDA-13 reais
  **não** levam o sufixo `-cu13`; só o cuDNN leva (`nvidia-cudnn-cu13`).
- **Processos `pythonw` órfãos** das invocações sem `-Wait` seguravam `selftest-cpu.jsonl` aberto
  (`Remove-Item: … being used by another process`). São meus, modo ficheiro, sem dispositivo de áudio, sem
  janela; terminam sozinhos — **não os matei** (regra da casa).

---

## 5. A decisão de produto: QUE PACOTE EMBARCA, e como a escolha é feita no arranque

### 5.1 O problema real

Os três pacotes (`onnxruntime`, `onnxruntime-gpu`, `onnxruntime-directml`) **instalam-se no mesmo
namespace `onnxruntime`** e **não podem coexistir**. Qual ganha é decidido pela **ordem do pip**. E o
`onnxruntime-genai` — que o motor híbrido usa para o mel/VAD — tem **dependência dura no `onnxruntime`
simples**, pelo que **reintroduz a armadilha do sombreamento sempre que é instalado depois**.

### 5.2 Recomendação

**Embarcar `onnxruntime-gpu[cuda,cudnn]` com uma guarda de ordem de instalação obrigatória.**

Receita medida (a cor verde de §3.1), em duas linhas, nesta ordem:
```powershell
pip install "onnxruntime-genai==0.17.1" "onnxruntime-gpu[cuda,cudnn]==1.30.0"
pip install --force-reinstall --no-deps "onnxruntime-gpu==1.30.0"   # <- a guarda
```
E, **no arranque**, a escolha não é feita por leitura de config: é feita pela **cadeia de §3.3**, que
sonda, cai e **regista o `get_providers()` real**.

**Porquê:**
1. **É a única receita medida que acende uma GPU NVIDIA de raiz** — e a correcção é uma linha.
2. **O custo é disco, não RAM:** o CUDA usa **423 MB MENOS de RSS de host** e carrega **4× mais rápido**.
   O ~1,3 GB de wheels `nvidia-*` é disco.
3. **A cadeia existente do worker já degrada correctamente** em hosts não-NVIDIA — **quatro braços
   medidos** (§3.3), incluindo o caso "sem GPU nenhuma".
4. **Embarcar só `onnxruntime` deixa a própria máquina do dono a RTF 0,80 / 6,7 core·s por audio·s —
   que é o congelamento que ele reportou.**

**O que isto custa, dito e não escondido:** num host AMD ou Intel, os wheels `nvidia-*` são
**peso morto** (~1,3 GB de disco) e o ORT cai para CPU — o mesmo comportamento que teria com o pacote
simples. **O DirectML não é alternativa hoje** (§4.1). Portanto a escolha é honestamente: *pagar 1,3 GB de
disco em todas as máquinas para que as máquinas NVIDIA funcionem*, ou *não ter GPU em máquina nenhuma*.

### 5.3 O caminho vendor-neutral que faria o DirectML valer a pena — o que teria de mudar

Para o DirectML servir **qualquer** GPU (o que é o objectivo declarado do pai), falta **a montante**:
1. `onnxruntime-genai-directml` ≥ 0.17.1 contra `onnxruntime-directml` ≥ 1.26.0 (a API 26); **e**
2. **suporte do DML a `MatMulNBits`** e aos restantes ops `com.microsoft` do encoder.

**Ou**, no nosso lado, uma de duas:
- o worker ganhar o **seu próprio front-end de mel/VAD** (deixando de precisar do genai), **e**
- um **export int8 livre de ops contrib**.

**Ambos são trabalho grande e fora do âmbito desta lane.** Fica registado como o caminho, não como o
plano.

### 5.4 `consultgpt`

**Não consultei o `consultgpt`.** Razão, registada: a decisão de §5.2 não é uma questão de impressão ou de
design — é decidida por medições que já tinha (a cor verde/vermelha de §3.1, os 423 MB, as 4 braços da
cadeia, o muro de ops do DML). **Não aceitei nem rejeitei nada dele porque não perguntei.** Se o pai
quiser uma segunda opinião sobre o trade-off de 1,3 GB em hosts AMD/Intel, esse é o ponto onde valeria a
pena.

---

## 6. Correção do `AGENTS.md` — JÁ ATERROU A MONTANTE (não re-propor, não editar)

**Não editei o `AGENTS.md`** (proibido). A frase falsa foi **corrigida a montante enquanto esta lane
trabalhava** — a minha proposta de correcção **já lá está**. Registro-a como **aterrada**, com a citação:

> ~~`CUDAExecutionProvider` is **requested but not loadable here** — ORT silently returns
> `['CPUExecutionProvider']`. The box runs on CPU.~~ **CORRECTED 2026-10-08 — THAT SENTENCE IS FALSE.
> MEASURED: `ort.get_available_providers()` → `['TensorrtExecutionProvider','CUDAExecutionProvider',
> 'CPUExecutionProvider']`, and `get_device()` → `GPU`.** … a CUDA-requesting session in a CLEAN shell
> falls back to CPU for exactly ONE missing DLL — `cublasLt64_13.dll`, WinError 126 — and **one directory
> fixes it**: `site-packages\nvidia\cu13\bin\x86_64` on the DLL search path. `torch\lib` is CUDA 12 and
> does NOT serve it. **The worker already does this** — `worker/sotto_worker.py:277`
> (`_add_cuda_dll_dirs()`), called from `:3251` before the model load (both re-verified against the
> 242 082 B / sha256 `64E7EC6F…` revision) — so the live run IS GPU-backed.

**Revisão contra a qual a citação foi verificada:** `worker/sotto_worker.py` 242 082 B, mtime
2026-10-07T13:09:59, sha256 `64E7EC6F6C35C33600E9D50C11AC7D8CE96FBE1FEF87C24CD628BDF03F314E61`.

### 6.1 A segunda correcção — proposta aqui, e **TAMBÉM JÁ ATERROU A MONTANTE**

O `AGENTS.md` corrigiu *"a CUDA não carrega"* mas, quando escrevi esta secção, **ainda não dizia que a
receita de instalação ingénua reduz o ORT a CPU-only em silêncio.** Propus a linha abaixo (nunca a
escrevi — proibido). **Estado à data desta re-verificação: ATERRADA.** O `AGENTS.md` carregado agora
contém o bullet **"THE SHIPPING RECIPE HAS A SILENT FAILURE MODE — MEASURED 2026-10-08"**, com os
**números exactos do meu RECORD** (`capi_entries=21`, `providers_cuda_entries=0` vs `23` / `1`), o
`error: null`, a correcção de uma linha (`--force-reinstall --no-deps`) e a frase final sobre a ordem do
pip decidir ficheiro a ficheiro. **Portanto: não re-propor, não editar.** O texto que segue fica como o
registo do que foi proposto, e a citação que o confirma está imediatamente a seguir.

Proposta de linha (agora aterrada; **não a escrevi**):

> **THE SHIPPING RECIPE HAS A SILENT FAILURE MODE — MEASURED 2026-10-08.**
> `pip install "onnxruntime-gpu[cuda,cudnn]" onnxruntime-genai` installs plain `onnxruntime` LAST (it is
> `onnxruntime-genai`'s hard dep) and the plain wheel overwrites 21 shared `onnxruntime/capi/` files and
> drops `providers_cuda` (`onnxruntime-1.30.0.dist-info` RECORD: `capi_entries=21`,
> `providers_cuda_entries=0`; `onnxruntime_gpu-1.30.0.dist-info`: `23` / `1`). Result:
> `available: ['AzureExecutionProvider','CPUExecutionProvider']` and a CUDA-requesting session returns
> `['CPUExecutionProvider']` with **`error: null`** — CPU-only ORT, silently. The fix is one line after:
> `pip install --force-reinstall --no-deps onnxruntime-gpu==1.30.0` → back to
> `['TensorrtExecutionProvider','CUDAExecutionProvider','CPUExecutionProvider']`. **The three ORT packages
> share the `onnxruntime` namespace; pip's install ORDER decides which one wins, file by file.**

**Confirmação da aterragem (verificada, não inferida):** o `AGENTS.md` carregado nesta sessão contém o
bullet acima **literalmente**, incluindo as três perguntas separadas —
*"`get_available_providers()` = what the PACKAGE supports; `InferenceSession.get_providers()` = what the
SESSION uses; only the ORT profiler says what EXECUTES"* — e a distinção explícita entre esta falha e a
do `cublasLt64_13.dll` / WinError 126 (*"there the provider is listed and fails to initialise; here it is
not listed at all and the error is `null`"*). Nada do meu §6.1 ficou por aterrar.

---

## 7. Resumo de uma página

| pergunta | resposta |
|---|---|
| O ORT usa a GPU nesta caixa? | **SIM** — e ela **executa** (1792/1793 nós do encoder, 100 % do tempo) |
| `get_providers()` da sessão real | `["CUDAExecutionProvider", "CPUExecutionProvider"]` |
| `get_available_providers()` | `['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']` |
| Ganho do CUDA vs CPU (quieto) | **~7–8,7× mais rápido**; 0,47–0,60 vs 6,68–14,19 core·s/audio·s |
| Núcleos devolvidos à máquina | **~6 a ~14** |
| Carga do modelo | 5,81 s (CUDA) vs 23,48 s (CPU) — **4× mais rápido** |
| RSS de host | 1665,6 MB (CUDA) vs 2089,2 MB (CPU) — **423 MB MENOS** |
| Paridade de transcrição | **byte-idêntica** no caminho de produção |
| DirectML embarca? | **NÃO** — encoder tem 220 ops `com.microsoft`/`MatMulNBits`, DML dá `E_INVALIDARG` |
| A cadeia de fallback cai bem? | **SIM** — 4 braços medidos, incluindo o forçado e o "sem GPU nenhuma" |
| O que embarcar | **`onnxruntime-gpu[cuda,cudnn]` + guarda de ordem de instalação** |
| O `AGENTS.md` | corrigido **a montante**; não editei. §6 e §6.1 **ambas aterradas** — nada por aterrar |
| Não testado | `onnxruntime-gpu` sem driver NVIDIA; DirectML em AMD/Intel; par shell/worker longa duração |

**Regra que este recibo deixa para o próximo:** *`get_available_providers()` é o que o PACOTE suporta;
`InferenceSession.get_providers()` é o que a SESSÃO usa; só o profiler do ORT diz o que EXECUTA.*
As três perguntas são diferentes e a resposta de uma não implica a outra.
