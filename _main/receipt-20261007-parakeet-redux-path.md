# Recibo — o caminho mais pequeno para um passe BATCH que carimba `producer:'redux'` (H:/sotto, 2026-10-07)

**Lane:** `SottoReduxPath` · **Repo:** `H:/sotto` @ `main` `11df66e` · **Data:** 2026-10-07
**Ambito:** SO o Sotto (ordem do dono: *"trabalha só no sotto. nao mais no maanger ou omp"*).
**Janela/audio:** NADA. Nao arranquei o shell nem o painel. A UNICA coisa que corri foi o worker
em **modo ficheiro, sem device de audio** (`--selftest --audio worker/assets/sample1.flac`), lancado
por `pythonw.exe` (sem consola): nenhum renderer e' tocado, logo *"nao quero ouvir"* e' satisfeito
por construcao. Sem `VoiceMeeter`, sem saida default, sem hotkey.

**Contexto:** lane irmao `SottoLiveVsHistory` landou o CORTE
(`app/electron/history-source.js`, sha `75d175863c286a7aa6c105c7e0258a93d4d8ec078208d18438651981c02bd915`,
recusa `producer:'live'` fail-closed). O seu par de controlo: `AS_SHIPPED` LIVE 1221 / **HISTORY 0**;
`REDUX_TAGGED` HISTORY 130. **Logo o HISTORY esta' VAZIO hoje, por desenho**, ate' algo carimbar
`producer:'redux'`. Este recibo responde: **qual e' o caminho mais pequeno e REAL para o fazer**.

---

## 0. VEREDICTO EM TRES LINHAS

1. **O motor batch NAO esta' no disco.** Zero pesos Parakeet Redux, zero ficheiro GGUF, zero
   `*.safetensors`, zero binario `transcribe*`, e o worker **nao emite sequer um campo `producer`** —
   nada hoje no repo pode carimbar `producer:'redux'`.
2. **O QUE ESTA' no disco e' so' o modelo LIVE** (Nemotron 3.5 streaming, ONNX), e ele **JA' corre
   offline** em modo ficheiro — demonstrei-o abaixo (§4). Mas e' o **MESMO checkpoint do caminho live**;
   carimba'-lo `redux` seria exactamente a falsificacao que o dono proibe, e nao corrige o ERRO
   (`docs/audit/ao-vivo-vs-redux.md` §6.3).
3. **O caminho mais pequeno e' o ONNX — `eschmidbauer/parakeet-redux-onnx` — porque a runtime JA'
   esta' instalada neste box** (`onnxruntime 1.30.0` + `onnxruntime_genai 0.17.1`), provada a correr
   o export ONNX do Nemotron. Nao exige build nem fork nem nova runtime; exige ~436 MB de download,
   o laco de decodificacao RNN-T, e o call site que carimba `producer:'redux'`. O caminho do README
   (GGUF + `transcribe.cpp`) exige um **fork privado** (ver §3-A).

---

## 1. O plano, citado VERBATIM do `README.md` (com numeros de linha, `nl -ba`)

O `README.md` nomeia o plano batch nestas linhas:

```
    20	| streaming ASR | `nvidia/nemotron-3.5-asr-streaming-0.6b` | **verified** | 1,272,450 downloads · 1,169 likes · `nemo` · cache-aware · 35 locales incl. `pt` · `license:other` |
    21	| batch ASR | `moondream/parakeet-redux` | **verified** | 10,187 downloads · 231 likes · `ternary` · `1.58-bit` · 25 languages incl. `pt` · **CC-BY-4.0** |
    22	| inference runtime | `transcribe.cpp` | **verified** | runs **both** models as GGUF · `tq1_g128` ternary · the Nemotron GGUF has **1,835,919 downloads** |
```

```
    24	`transcribe.cpp` is the answer to "what engine runs Parakeet Redux". It is a
    25	C++ runtime, which is what makes the no-resident-Python constraint reachable
    26	from a Tauri/Rust process. The Nemotron checkpoint's native format is
    27	PyTorch/NeMo, so without this runtime the heaviest component would have
    28	dragged a Python environment into the app.
    29	
    30	Alternative paths that exist and are not yet chosen: ONNX
    31	(`eschmidbauer/parakeet-redux-onnx`, `soniqo/Nemotron-…-ONNX-FP16`), CoreML for
    32	Apple silicon, and `sherpa-onnx`.
```

```
    54	- **ASR** — Nemotron 3.5 streaming while recording; Parakeet Redux for the
    55	  canonical transcript afterwards.
```

e o estado:

```
    62	## Status
    63	
    64	Planning. See `docs/roadmap.md`.
```

O `docs/roadmap.md` fecha o mesmo desenho em **M2**:

```
    64	**M2 — First transcription.** Parakeet Redux through `transcribe.cpp` over an
    65	M1 file. Batch, not streaming. Exit: real words out of the sample, with the
    66	model's actual resident cost measured. This is the earliest point where the
    67	CC-BY-4.0 attribution obligation bites.
```

> **Nota critica (o que o README diz e o que o disco faz):** `README.md:22` afirma que
> `transcribe.cpp` corre "both models" como GGUF com `tq1_g128`. **Isso e' falso para o release
> upstream** — medido em `docs/stack-verification.md:366-410`: o upstream
> (`handy-computer/transcribe.cpp` v0.3.1, MIT) **nao** tem o tipo ggml `TQ1_G128`; o preset de
> quantizacao do upstream e' so' `F16, Q8_0, Q6_K, Q5_K_M, Q4_K_M`, e `parakeet-redux` **nao esta'**
> na tabela de familias. Os pesos ternary exigem o fork `NairoDorian/transcribe.cpp`
> (`patches/ggml/0003-tq1_g128-ternary.patch`). Ver §3-A.
> `README.md:64` diz "Status: Planning" — e o `docs/audit/doc-vs-code.md:22` (R4/R8) mediram que o
> stack descrito (`Tauri/Rust/CPAL/transcribe.cpp/SQLite`) **nao e' o stack que corre** (o app e'
> Python + WebView2, ASR e' ONNX Runtime). Logo o README **descreve um plano**, nao o presente.

---

## 2. INVENTARIO — o que ESTA' e o que NAO esta' no disco (medido hoje)

### 2.1 PRESENTE

Fonte: `ls -la worker/models/*/`, `sha256sum`, `python -c "import onnxruntime,onnxruntime_genai"`.

| artefacto | path | bytes | sha256 | o que e' |
|---|---|---|---|---|
| Nemotron ONNX **int8** (o modelo LIVE shipped) | `worker/models/nemotron-3.5-asr-streaming-0.6b-int8/` | dir inteiro | ver 14 linhas abaixo | o unico motor ASR carregavel hoje |
| —— encoder | `…-int8/encoder.onnx` | 2,815,853 | `008f9f689453a097dc98680eb4c8ce47a0ed3cb7c20498ff321dcb223b28dac7` | header |
| —— encoder weights | `…-int8/encoder.onnx.data` | 967,176,192 | `d758dd3d6d8241a362c39ebad3ad3138a5f18c24248acee6c963837ffcb3c36c` | **os pesos** (~150× o header) |
| —— decoder | `…-int8/decoder.onnx` (+ `.data` 59,785,216) | 4,696 | `9277dacdb7d0e2e32c8969f733ef8808fe438260adf1ea91875873b832fe5a41` | |
| —— joint | `…-int8/joint.onnx` (+ `.data` 37,830,656) | 2,136 | `f585442de8cce8531f5ab2832ac75920b062ef6e354df79bec1b51d45bbc3737` | |
| —— VAD | `…-int8/silero_vad.onnx` | 2,243,022 | `a4a068cd6cf1ea8355b84327595838ca748ec29a25bc91fc82e6c299ccdc5808` | |
| —— genai config | `…-int8/genai_config.json` | 1,962 | `0fdbafa35aca9db89c69f82cadb7b66a2e5260114fcc19d05e87d87dde15fb4f` | |
| Nemotron ONNX **fp16 / int4 / fp32** | `worker/models/nemotron-3.5-asr-streaming-0.6b-{fp16,int4,fp32}/` | 1.24 GB / 756 MB / 2.5 GB | (mesma familia) | exports alternativos do MESMO checkpoint live |
| config do worker | `worker/config.json` | 3,760 | `acdd039434e0531e29bc4e21b43a0fa0c5de3ebe83dd1f8e47f8707716a103ee` | `model.dir=models/nemotron-3.5-asr-streaming-0.6b-int8` |
| amostra bundled | `worker/assets/sample1.flac` | 282,378 | `cb5c48a2d1d6f7dedd0330f088a4cbe76de1a86e6a6109c06d255bb1ca2f7542` | 13.69 s @ 16 kHz mono |
| guard do produtor (SottoLiveVsHistory) | `app/electron/history-source.js` | 3,708 | `75d175863c286a7aa6c105c7e0258a93d4d8ec078208d18438651981c02bd915` | recusa `live`, aceita `redux` |
| choke point do painel | `app/electron/panel.js` | 26,388 | `9099fb3c513408645d8ca5025cb65b1b215123baab03b7703085eae775686bd7` | unico writer do store |
| **runtime ONNX** | `onnxruntime` (pip, Python 3.11.8) | — | — | `1.30.0`, providers `[Tensorrt, CUDA, CPU]` |
| **runtime genai** | `onnxruntime_genai` (pip) | — | — | `0.17.1` |
| **runtime HF** | `huggingface_hub` (pip, `probe/which_import.py`) | — | — | disponivel para download |
| toolchain | `python`/`pythonw` 3.11.8, `ffmpeg`/`ffprobe` | — | — | em PATH |

### 2.2 AUSENTE (o que o plano exige e o disco NAO tem)

Comandos que devolveram **VAZIO** (executados hoje, neste repo):

| comando | resultado |
|---|---|
| `find H:/sotto -not -path './.git/*' \( -iname '*.gguf' -o -iname '*.safetensors' -o -iname '*transcribe*' \)` | **VAZIO** |
| `ls H:/sotto/worker/models/` | **so'** `nemotron-3.5-asr-streaming-0.6b-{fp16,fp32,int4,int8}` — nenhum `parakeet*` |
| `grep -rn "producer" worker/` | **VAZIO** — o worker nao emite este campo (so' o painel o LE) |
| `which transcribe transcribe-cli transcribe_server` | **VAZIO** (so' `C:\WINDOWS\system32\main.cpl`, um applet do Painel de Controlo, nao um CLI) |
| call site de um job batch | **VAZIO** — `grep -rni "batch"` acha so' comentarios (ONNX GEMM, `run.cmd --check-args`) |
| segunda passagem M1–M3 no worker | **AUSENTE** — `grep -c 'def rerun\|reset_stream_state\|_last_symbol' worker/sotto_worker.py` = 0 (recibo `_main/receipt-20261007-segment-rerun.md`: a cura que os criou foi perdida com o ficheiro de 149 856 B) |

**Lista do ausente, nomeada:** (a) pesos `moondream/parakeet-redux` — ausente; (b) GGUF ternary
`Nairod785/parakeet-redux-gguf` — ausente; (c) binario/runtime `transcribe.cpp` — ausente;
(d) export ONNX `eschmidbauer/parakeet-redux-onnx` — ausente; (e) **qualquer** call site que
dispare um job batch — ausente; (f) o campo `producer` na saida do worker — ausente.

---

## 3. AS OPCOES DECISION-READY (o que o dono tem de decidir, e o custo de cada uma)

**A decisao de fundo, uma so': qual e' o MOTOR a que o transcrito canonico esta' reservado.**
O `producer:'redux'` e' so' uma string que o choke point (`panel.js`) compara — **nao prova o motor**.
Quem escolher pode carimba'-la com QUAISQUER palavras; a honestidade esta' em carimba'-la com o motor
que o plano nomeia, ou em mudar o plano.

### Opcao A — GGUF + fork `transcribe.cpp` (o plano do README, ao pe' da letra)

- **Runtime a construir:** `NairoDorian/transcribe.cpp` (fork de `handy-computer/transcribe.cpp`, MIT,
  `fork:true`, 0 stars, ultimo push 2026-09-26) — o UNICO build que traz `GGML_TYPE_TQ1_G128` (id 96)
  via `patches/ggml/0003-tq1_g128-ternary.patch`. O upstream v0.3.1 **nao** abre estes pesos
  (`docs/stack-verification.md:366-410`, 4 fontes). Custo: **clone + build C++/CMake**, contra um
  ABI **pre-1.0** ("MAY break between 0.x minor releases") e um fork de um so' maintainer.
- **Artefacto a descarregar:** `Nairod785/parakeet-redux-gguf` — TQ1_F16 **179,312,288 B** /
  TQ1_Q8_0 **159,121,504 B** / TQ1_Q4_K **156,696,672 B**. Licenca declarada no repo: `cc-by-4.0`
  (claim do terceiro sobre um derivado quantizado do `moondream/parakeet-redux`, que declara
  `cc-by-4.0` — verificado na pagina HF). **Atribuicao obrigatoria.**
- **Call site a escrever:** disparar `transcribe_run` sobre o WAV do segmento e emitir uma linha
  com `producer:'redux'`.
- **Custo total:** ALTO. O unico build que serve **nao tem release** — os prebuilt Windows
  (`transcribe-native-0.3.1-windows-x86_64-cpu-vulkan.tar.gz`) sao do UPSTREAM e **nao** carregam
  TQ1. Portanto: build proprio do fork + vendor de um binario pre-1.0.
- **Verde que NAO se compra:** o fork mede FLEURS-fr WER 8.32/8.31/8.18 % contra 4.65 % do
  `parakeet-ultra` upstream (`stack-verification.md`), i.e. a compressao ternary custa precisao.

### Opcao B — GGUF upstream + `transcribe.cpp` de stock (DESISTIR do Redux ternary)

- **Runtime:** `handy-computer/transcribe.cpp` v0.3.1 (MIT) — **prebuilt Windows existe**, ou build
  com `cmake -B build` (binario `transcribe-cli` auto-contido, sem deps).
- **Artefacto:** uma quantizacao Parakeet **suportada pelo upstream** (`parakeet-tdt-0.6b-v3` etc.,
  Q4_K_M/Q8_0). **Isto NAO e' `moondream/parakeet-redux`** — e' o segundo modelo do par do
  RealtimeSTT (`docs/oss-approaches-20261006.md` A2, "*needs a second model. Not started*").
- **Custo:** BAIXO para chegar a um passe batch a funcionar (binario + um GGUF + call site). **Custo
  de PRODUTO:** muda o plano — o campo `History · Redux` passa a nomear um motor que nao e' Redux.
  Decisao do dono.

### Opcao C — ONNX + a runtime que JA' esta' instalada **(o caminho mais pequeno)**

- **Runtime:** **ZERO a instalar.** `onnxruntime 1.30.0` + `onnxruntime_genai 0.17.1` ja' estao
  presentes e **provadamente funcionais neste box** — a demonstracao do §4 corre o export ONNX do
  Nemotron com eles, offline.
- **Artefacto a descarregar:** `eschmidbauer/parakeet-redux-onnx` (**CC-BY-4.0**, verificado na
  pagina HF) — export ONNX multi-grafo de `moondream/parakeet-redux`:
  `preprocessor.onnx` **1.2 MB** + `encoder-model.onnx` **344 MB** + `decoder_joint-model.onnx`
  **73 MB** + `vad-model.onnx` **18 MB** ≈ **436 MB**, com `vocab.txt`, `config.json`, `transcribe.py`
  e `export_onnx.py`. O encoder por omissao usa `com.microsoft::MatMulNBits` (operador contrib do ORT,
  suportado pelo CPU provider instalado); o repo documenta um export denso float32 `--bits 0`.
- **Call site a escrever:** o laco greedy do transducer (preprocessor -> encoder -> decoder_joint) +
  carimbar `producer:'redux'`. Sem build, sem fork, sem runtime nova.
- **Custo:** BAIXO-MEDIO (≈436 MB de download + o laco de decode). E' o **unico** caminho onde a
  runtime ja' esta' paga e provada, e o artefacto **ja' esta' nomeado pelo proprio README:30-32**.
- **Caveats:** export de TERCEIRO (eschmidbauer) do `moondream/parakeet-redux`; capacidade de
  *streaming* nao verificada; atribuicao CC-BY-4.0.

### Decisao secundaria (a que `stack-verification.md` chama "uma decisao de arquitectura")

**Bundle dos pesos vs download no primeiro uso.** Se o Sotto **descarrega** os pesos, a clausula de
redistribuicao do OpenMDW-1.1 (Nemotron) **nao** dispara e so' resta a obrigacao de aviso MIT do
`transcribe.cpp`. Se os **bundle**, viaja a papelada. Isto decide como o produto trata os pesos.

### Recomendacao mecanica (nao vinculativa)

**Opcao C**, com **Opcao B** como plano B se o dono aceitar trocar "Redux" por um Parakeet upstream, e
**Opcao A** apenas se o dono quiser literalmente o ternary — sabendo que isso compra um fork privado.
Seja qual for: o call site que emite a linha tem de **carimbar `producer:'redux'` explicitamente**
(o worker hoje nao emite `producer` nenhum, e o choke point e' fail-closed: uma linha sem o campo e'
recusada).

---

## 4. DEMONSTRACAO — o UNICO motor presente transcreve um WAV offline (headless)

E' a demonstracao condicional que o brief pede — **e ela carrega a sua propria etiqueta honesta**.
O que ESTA' no disco e' `pythonw.exe` + `onnxruntime 1.30.0` + `onnxruntime_genai 0.17.1` a carregar
`worker/models/nemotron-3.5-asr-streaming-0.6b-int8` (ONNX) pelo proprio `--selftest` do worker
("*transcribe a file, no audio device needed*"). **Isto NAO e' Parakeet Redux — e' o MESMO checkpoint
do caminho LIVE.** Prova duas coisas ao mesmo tempo: (1) existe no box um caminho de decodificacao
offline que corre, sem rede e sem janela; (2) o unico motor presente e' o live, logo **nao pode** ser
o que carimba `redux`.

Comando exato (lancado por `pythonw.exe`, sem consola; nada e' tocado no device de audio):

```
$ cd H:/sotto && "C:/Program Files/Python311/pythonw.exe" worker/sotto_worker.py --selftest --audio worker/assets/sample1.flac > _main/_reduxpath-demo-selftest.out 2> _main/_reduxpath-demo-selftest.err
rc=0
```

`stderr` (verbatim):

```
lang_id      : 101 (auto) source=config:auto table=languages.json
--- selftest ---
audio        : worker/assets/sample1.flac
audio_s      : 13.440
load_s       : 3.881
infer_wall_s : 3.517
rtf          : 0.262
tokens       : 120
blank_frac   : 0.5833 (frames=288 empty_chunks=3 vad_gated_chunks=0 music_gated_chunks=0 gate=off)
peak_rss_mb  : 2406.9
providers    : ['CUDAExecutionProvider', 'CPUExecutionProvider']
RECOGNISED   : "going along slushy country roads and speaking to damp audiences in drafty schoolrooms day after day for a fortnight he'll have to put in appearance at some place of worship on Sunday morning he can come tosk immediately afterward"
--- end selftest ---
```

`stdout` (JSONL, as linhas `final:true` que o choke point teria de aceitar — note a AUSENCIA de
`producer`): as tres linhas fechadas foram

```
{"model": "nemotron-3.5-asr-streaming-0.6b-int8", "type": "caption", "text": "going along slushy country roads and speaking to damp audiences in drafty school rooms day", "start": 0.56, "end": 5.6, "final": true}
{"model": "nemotron-3.5-asr-streaming-0.6b-int8", "type": "caption", "text": "after day for a fortnight he'll have to put in appearance at some place of worshi p on", "start": 5.6, "end": 10.64, "final": true}
{"model": "nemotron-3.5-asr-streaming-0.6b-int8", "type": "caption", "text": "Sunday morning he can come to sk immediate ly afterward", "start": 10.64, "end": 13.44, "final": true}
```

(evidencia completa em `_main/_reduxpath-demo-selftest.out` sha `04024c458947eda666b9d0de30ed4e020b4a7a6d2194bb40dcc1b5fd7c62b0e3`,
e `_main/_reduxpath-demo-selftest.err` sha `1c04dd710759b146949e631e14fa78d8e024a7045674c72f848cd990ce6c4776`.)

**O que a demonstracao PROVA e o que NAO prova:**
- PROVA: ha' um caminho offline real, sem rede, sem device, sem janela, que transcreve um WAV com a
  runtime presente. Comportamento: `rc=0`, 120 tokens, RTF 0.262, `reconheceu` texto real.
- **NAO PROVA** um passe `producer:'redux'`: o evento nao traz `producer`, o modelo e' o live, e o
  unico codigo que sabe ler `producer` e' o choke point do painel (que o recusaria, por ausencia do
  campo). Carimba'-lo seria falso.
- Efeito colateral verificado: o HISTORY nao mudou (`find history -type f` → so' os 9 ficheiros de
  `2026-10-06`; nada de `2026-10-07`), logo a demo nao poluiu o transcrito do dono.

---

## 5. NAO VERIFICADO (explicito)

1. **O motor batch.** Nenhum peso/binario Parakeet Redux foi baixado ou corrido — por ordem (nao
   instalar/descarregar). O que o §3 diz de A/B/C vem das fontes primarias ja' colhidas
   (`docs/stack-verification.md`, README) e de uma consulta web as paginas HF; **nao** de execucao.
2. **A qualidade do `eschmidbauer/parakeet-redux-onnx` neste box.** Nao corri os grafos; os tamanhos
   e a licenca vem da pagina HF (a resposta do `gpt_search` nao conseguiu ler o `/api/models/...`
   cru, so' a pagina). O `--bits 0` "plain ONNX" e' documentado, nao presente.
3. **Capacidade de streaming do parakeet-redux.** Nem o upstream nem o card ternary a declaram
   (`stack-verification.md` §"NOT ESTABLISHED" ponto 4) — se o 2o motor tiver de ser streaming, e'
   questao aberta.
4. **Custo residente de qualquer um dos motores batch.** Ninguem publicou RAM/VRAM
   (`stack-verification.md`); so' o Nemotron presente tem RSS medido (2406.9 MB de pico agora).
5. **Ausencia de janela durante a demo.** O `pythonw.exe` nao abre consola por construcao, mas o
   censo da casa amostra de 60 em 60 s e **nao** prova a ausencia (`AGENTS.md`); nao corri um censo
   proprio a 25 ms. O que posso afirmar: `pythonw.exe` + modo ficheiro, e a accao nao arranca o shell.

---

## 6. SELO DO DONO (a pendencia que chegou a esta lane enquanto trabalhava)

O selo endereca **2 de 24 governadores externos em VERMELHO — `observer` e `theorist-delta-guard`** —
e pede que eu os resolva OU nomeie quem tem a capacidade. **Esses governadores sao de `I:/!manager` /
`G:/superharness`, NAO do Sotto.** A minha ordem desta lane e' explicita: *"trabalha só no sotto. nao
mais no maanger ou omp"* e o brief proibe edicoes em manager/omp. **Nao tentei** — nomeio:

- **`observer` (VERMELHO-DAEMON-STALE):** dono = `G:/superharness/scripts/observer.sh` (daemon,
  pid medido 23368/claim 23424). O fecho exige **restart do daemon** a partir do shell que tem o pid.
  **Dono da capacidade:** o assento que sustenta o `observer.sh` (SuperHarness daemon owner) — nao eu.
- **`theorist-delta-guard` (VERMELHO-SILENCIO):** dono = Task Scheduler
  `scripts/theorist-delta-guard-scheduled.cmd -> theorist-delta-guard.ps1`. O fecho exige uma **linha
  nova** do governador (nao a mesma com data nova). **Dono da capacidade:** quem sustenta a
  task agendada / o script `theorist-delta-guard.ps1` em `I:/!manager`.
- **A linha `tools:` que o selo pede** (`agents/SottoReduxPath.md`) vive em `I:/!manager/agents/` —
  **fora do meu ambito de escrita** nesta lane (editar so' `H:/sotto`). **Dono:** o **assento
  principal** (tem escrita em manager + `dispatch`); eu nao a escrevo.

Nada disto fecha o meu entregavel, e nada disto eu posso fechar sem violar a minha ordem. Fica nomeado.

---

## SELF-AUDIT

- **protocolos em falta** — faltou-me um protocolo para **medir a ausencia de janela de um comando que
  eu proprio lanco**. O `AGENTS.md` diz que o censo de 60 s nao prova ausencia; eu nao tinha um
  instrumento a 25 ms proprio para prender a demo, e por isso a demo fica com `pythonw.exe` (garantia
  por construcao) mas **sem censo proprio**. Faria diferente: correr `_main/panel-startup-flash-census.py`
  ou o `_armE-window-census.py` sobre o pid da demo, ou dizer no brief que basta o `pythonw`.
- **verificacao adicional** — corri a barata: **executei** o motor presente (nao so' `grep`), e
  confirmei por `find`/`ls`/`grep` que tudo o que o plano exige esta' ausente. A que NAO corri e'
  cara ou proibida: descarregar ~436 MB do `parakeet-redux-onnx` e correr o laco greedy — esta' fora
  da ordem ("nao instalar/descarregar"). Custo se fosse permitida: ~1 download + 1 script; seria o
  unico teste que fecha a Opcao C de ponta a ponta.
- **checkboxes novas** — MECANICO: *antes de prometer um passe batch, correr
  `python -c "import onnxruntime,onnxruntime_genai,os;print(onnxruntime.__version__,onnxruntime_genai.__version__)"`
  E `find H:/sotto -iname '*.gguf' -o -iname '*.safetensors' -o -iname '*transcribe*'`
  — o primeiro diz se a runtime JA' esta' paga; o segundo, se o motor existe.* RED input: hoje o
  segundo devolve VAZIO, e isso **tem** de deixar a promessa RED. E: *todo call site novo que emite
  transcrito canonico tem de vir com uma arm que o carimba `producer:'redux'` E uma que o deixa sem o
  campo (recusada)*, senao a guarda e' indistinguivel de "escrever nada".
- **review por outro subagente** — **sim-com-escopo**: (a) atacar **so'** a escolha da Opcao C como
  "mais pequena", confrontando-a com o facto de o export ONNX ser multi-grafo e de terceiro (um
  reviewer pode ver a Opcao B como mais honesta apesar do build); (b) confirmar na pagina HF
  `eschmidbauer/parakeet-redux-onnx` os tamanhos e a licenca que eu li via `gpt_search` (nao li o
  `/api/models` cru). Nao vale re-rever a demonstracao (comando + rc + texto reais).
- **gate-doubt**:
  - **verde-de-verdade:** o `rc=0` e o texto da demo sao reais — o modelo carregou
    (`load_s : 3.881`, `model-loaded`), o `text` nao-vazio (`empty: false`, 120 tokens), o RTF medido
    (0.262), e o comando e' o proprio entry point do worker. **Um verde que eu DESCONTO:** a
    demonstracao prova "existe um caminho offline", **nao** "existe um passe `redux`" — eu proprio a
    etiqueto como NAO sendo o motor canonico. O `find`/`grep` de ausencia devolveu vazio, e um vazio
    pode ser um **padrao errado**; por isso listei os comandos exactos (para um reviewer os repetir).
  - **falta-no-gate:** nada no repo verifica que o motor que carimba `redux` e' o motor PLANEJADO. O
    choke point so' compara a string `producer`. Cenario que atravessa: um call site que corra o
    Nemotron live e carimbe `producer:'redux'` **passa** o choke point e enche o HISTORY com o texto
    do live — a mesma doenca que a lane irma curou, pela porta do outro lado.
  - **gate-melhor:** MECANICO: uma assercao que leia a PROVENIENCIA real do modelo no momento do
    carimbo — ex.: o evento de linha tem de carregar o `model` de origem, e um oracle exige
    `model != <o modelo live do config>` para aceitar `producer:'redux'`. RED input: uma linha
    `{"model":"nemotron-3.5-asr-streaming-0.6b-int8","producer":"redux"}` tem de ser RECUSADA. Nao o
    escrevi — editar o painel e' de outra lane e o meu alvo era a decisao, nao o gate.
- **confianca** — **alta** no inventario (presente/ausente medido por 4 instrumentos: `find`, `ls`,
  `grep`, `sha256sum`) e na demonstracao (comando + rc + texto reais). **media** nas Opcoes A/B/C:
  os custos vem de fontes primarias ja' colhidas (stack-verification) e de uma consulta web a pagina
  HF, **nao** de eu ter construido ou corrido qualquer um dos motores batch.
- **nao verificado** — (1) qualquer motor batch a correr (proibido instalar/descarregar); (2) o
  `/api/models` cru do `parakeet-redux-onnx` (so' a pagina); (3) custo residente do motor batch;
  (4) censo de janela proprio durante a demo (so' `pythonw.exe` por construcao); (5) se o dono quer
  literalmente Redux ternary (Opcao A) ou aceita trocar de motor (Opcao B).

---

## CACHE/PRICE

Comando (o brief escreveu `I:/manager/…`, que **nao existe**; o caminho real e' `I:/!manager/…`),
`bash I:/!manager/scripts/cache-task-report.sh SottoReduxPath` — **rc=0**. Output VERBATIM:

```
## CACHE/PRICE
- task/agent: SottoReduxPath
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoReduxPath.jsonl
- cache: read=1916928 write=0 hit=93.0290% (cache-read / input+cache-read); universe: 22 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoReduxPath.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=20 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs …
- when-failed: break_items=3; WHEN=2026-10-07T05:39:01.825000+00:00 | break_items=3; WHEN=2026-10-07T05:39:02.632000+00:00 | break_items=2; WHEN=2026-10-07T05:41:07.563000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 126309 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoReduxPath']; window: 2026-10-07T05:39:01.825000+00:00..2026-10-07T05:41:07.563000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a114df-3b99-778f-98be-f39f7cb41c7c provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791351541825 | session_id=01a114df-3b99-778f-98be-f39f7cb41c7c provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791351542632 | session_id=01a114df-3b99-778f-98be-f39f7cb41c7c provider=deepseek-flash model=deepseek-flash item_index=82; turn_id=1791351667563 (state=RESOLVED-BREAKS-OMP; population: 3 of 126309 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoReduxPath']; window: 2026-10-07T05:39:01.825000+00:00..2026-10-07T05:41:07.563000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-07T05:42:26.288238+00:00
- usage rows: 22
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 143642
- output tokens: 24744
- cache-read tokens: 1916928
- cache-write tokens: 0
- hit ratio: 93.0290% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 … | opencode-go-1/deepseek-flash: calls=20 … | opencode-go-1/mimo-v2.6-flash: calls=1 …; partition sums to the reported total: … $0.00000000 vs $0.00000000 over 22 of 22 matched usage rows
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP; population: 3 of 126309 … window: 2026-10-07T05:39:01.825000+00:00..2026-10-07T05:41:07.563000+00:00 …)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-07T05:39:01.825000+00:00; WHERE session_id=01a114df-3b99-778f-98be-f39f7cb41c7c provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791351541825
  - break_items=3; WHEN=2026-10-07T05:39:02.632000+00:00; WHERE session_id=01a114df-3b99-778f-98be-f39f7cb41c7c provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791351542632
  - break_items=2; WHEN=2026-10-07T05:41:07.563000+00:00; WHERE session_id=01a114df-3b99-778f-98be-f39f7cb41c7c provider=deepseek-flash model=deepseek-flash item_index=82; turn_id=1791351667563
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

(Quatro linhas reflowed para caber; os numeros sao exactos. `verdict: UNKNOWN` e' honesto: nao ha'
veredicto de aceitacao guardado neste instrumento.)

## SELF-AUDIT-LINT

`bash I:/!manager/scripts/self-audit-lint.sh H:/sotto/_main/receipt-20261007-parakeet-redux-path.md`
→ `SELF-AUDIT-LINT: inspected=1 violations=0 no-verdict=0` / `SELF_AUDIT_CLEAN` / **rc=0**.

## git disclosure

`H:/sotto` esta' em `main` @ `11df66e`. **Esta lane nao fez commit** e so' escreveu ficheiros NOVOS em
`_main/` (o recibo e as duas saidas da demo). Nenhum ficheiro de produto foi tocado
(`app/electron/**`, `worker/**` intactos; shas de `history-source.js`/`panel.js` iguais aos do recibo
da lane irma).
