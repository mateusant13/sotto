# Recibo — `worker/models/` foi esvaziado a 2026-11-01 16:28, e o que disso se restaurou

Nao e' um defeito de codigo: e' um FICHEIRO que deixou de estar no disco, e o sintoma que ele produz
(worker morre no arranque, motor ao vivo sem modelo) so' aparece a quem corre a app.

## A linha temporal, medida no log da instancia do dono (`_main/webview-run.log`)

|hora (local)|linha|
|---|---|
|16:25:23.284|`STATUS_APPLIED text="model-loading"`|
|16:25:45.307|`STATUS_APPLIED text="model-loaded"` — o nemotron CARREGOU|
|16:27:39.224|`BRIDGE_EXIT pid=31392 rc=3 … stderr_tail=["REDUX_SWITCH_STOP armed=true switches=1 segments=1 segment_lines=0 kicks=1 batch_seconds=3.7 …"]`|
|16:28:30.037|`BRIDGE_STATUS_ERROR … text="Worker error at model - model dir not found: H:\sotto\worker\models/nemotron-3.5-asr-ptbr-onnx-int4"`|
|16:29:34 / 16:29:38|o mesmo erro, e `BRIDGE_DEATH rc=2 deaths=4 kind=error`|
|16:32:16 / 16:32:18|o mesmo erro outra vez|

`worker/models` tem `mtime = 2026-11-01 16:28` — o directorio foi mexido exactamente nesse instante, e
hoje (2026-11-02, antes da restauracao) estava **vazio: 0 entradas**.

**Nao e' desta lane.** Nenhuma remocao minha toca esta maquina antes de 21:4xZ (=18:4x local); o
`worker/` nao apaga nada (`grep -n "rmtree|os.remove" worker/*.py` da' 0 no caminho de modelos), e o
`engine_switch.py` so' LE o directorio (`redux_checkpoint_missing`). O que apagou 748 MB de pesos entre
16:27:39 e 16:28:30 nao foi o worker.

## O que o produto espera (medido no codigo, nao suposto)

|directorio|quem aponta para ele|manifestos que o carregador exige|estado|
|---|---|---|---|
|`worker/models/nemotron-3.5-asr-ptbr-onnx-int4`|`worker/config.json` → `model.dir`|`genai_config.json`, `vocab.txt`, `.onnx` (783 537 972 B / 32 ficheiros registados em `_main/receipt-20261021-parakeet-lifecycle.md:22`)|**AUSENTE**|
|`worker/models/parakeet-redux-ternary`|`worker/redux_batch.py:39` (`DEFAULT_MODEL_DIR`), `engine_switch.REDUX_CHECKPOINT_RELPATH`|`config.json` **e** `model.safetensors` (`redux_batch.py:112-115`)|**AUSENTE**|
|`worker/models/parakeet-redux-onnx-int4`|`worker/audio_queue_consumer.py:53` (`ONNX_DIR`), `engine_switch.REDUX_LIVE_ONNX_RELPATH`|`config.json` + `encoder-model.onnx` + `decoder_joint-model.onnx` + `preprocessor.onnx` + `vad-model.onnx` + `vocab.txt`|**RESTAURADO** (ver abaixo)|

## O que foi restaurado, e como

O export ONNX int4 do parakeet sobreviveu FORA do repo, em `H:\VOD.RIP-models\parakeet-redux-onnx-int4`
(416 MB: `config.json` 375 B, `encoder-model.onnx` 343 841 943 B, `decoder_joint-model.onnx`
72 552 270 B, `preprocessor.onnx`, `vad-model.onnx`, `vocab.txt`). Como o nome do directorio de destino
e' exactamente o que o codigo procura, a restauracao nao mente sobre a precisao do export:

```
cmd /c "mklink /J worker\models\parakeet-redux-onnx-int4 H:\VOD.RIP-models\parakeet-redux-onnx-int4"
Junção criada para worker\models\parakeet-redux-onnx-int4 <<===>> H:\VOD.RIP-models\parakeet-redux-onnx-int4
```

Junction e nao copia: zero bytes duplicados, e remover o link nao toca nos pesos.
`python worker/audio_queue_consumer.py --model-dir worker/models/parakeet-redux-onnx-int4` arranca e
responde `fila vazia` (rc 0) — o caminho do consumidor ONNX abre.

## O que NAO foi restaurado, e porque (a informacao nao esta nesta maquina)

- **`nemotron-3.5-asr-ptbr-onnx-int4`** (o motor AO VIVO, 748 MB / 32 ficheiros). Nao ha copia: uma
  varredura por nome a profundidade 3 em `H:` e `I:` deu **0** directorios `nemotron*`, e o
  `docs/model-specs/README.md` nomeia o repo de onde os pesos vieram
  (`DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu`) mas **nao** um export `ptbr-int4`: o nome
  `…-ptbr-onnx-int4` e' uma exportacao LOCAL e o repo nao tem o pipeline que a produziu
  (`ls _main/*export* _main/*quant*` → so' o export do `diar-models`). Baixar o int8 e renomea-lo para
  `int4` seria trocar a precisao do motor por um nome — exactamente o que nao se faz.
- **`parakeet-redux-ternary`** (safetensors, 3,90 GB segundo AGENTS.md). Tambem sem copia: o que existe
  em `H:\VOD.RIP-models\` e' o `parakeet-redux-onnx-int4` (ONNX, nao ternario) e `parakeet-models`.

**Consequencia medida na bateria**: os passos que precisam do nemotron (`lang-id-oracle`,
`model-spec-oracle`, `word-split-oracle`, `vad-option-probe`, `fresh-processor-probe` e os seus
`red-as-expected`) falham com `SETUP ERROR: the model directory named by worker/config.json is not
there` — e' o oraculo a dizer a verdade sobre a maquina, nao uma regressao de codigo. Os mesmos passos
volveram a verde no instante em que os pesos voltarem ao caminho que `worker/config.json` nomeia.

## CORRECCAO 2026-11-02 — a junction NAO bastava, e o export completo foi reposto

A primeira tentativa (junction para `H:\VOD.RIP-models\parakeet-redux-onnx-int4`) punha os `.onnx` no
caminho certo e **nao** fazia o motor carregar. A sonda de fila deu a razao exata:

```
audio-queue-consumer: FALHOU seg-0001.wav -- No module named 'transcribe'
audio-queue-consumer: seg-0001.wav state=error:ModuleNotFoundError
```

`worker/redux_live.py:294-305` poe o DIRECTORIO DO MODELO em `sys.path` porque **o export traz o seu
proprio `transcribe.py`** (o laco TDT de referencia, 17 844 B). A copia que sobreviveu em
`H:\VOD.RIP-models` tem os pesos e nao tem esse ficheiro; o fallback `models/parakeet-redux-reference`
tambem nao existe. Ou seja: a junction provava "os bytes estao ali", nunca "o motor carrega".

O proprio recuo do carregador nomeia o instrumento certo — `python _main\fetch-parakeet.py` — e esse
script **nao estava na arvore**: so' no indice do `stash@{0}` (commit `3120551`). Recuperado para
`_main/fetch-parakeet.py` e corrido. Ele baixa `eschmidbauer/parakeet-redux-onnx` na revisao FIXADA e
verifica contagens de bytes + prefixos de sha256 contra os valores registados:

```
GREEN decoder_joint-model.onnx   72552270 B  sha256=97ae0cb0
GREEN encoder-model.onnx        343841943 B  sha256=ade2c65c
GREEN preprocessor.onnx           1224294 B  sha256=3de5742f
GREEN vad-model.onnx             18300687 B  sha256=18dfbe34
GREEN transcribe.py                 17844 B
GREEN vocab.txt / config.json / onnxruntime 1.30.0
VERDICT: GREEN -- os pesos estao em disco e sao os registados
```

A junction foi desfeita e o export vive agora em `worker/models/parakeet-redux-onnx-int4` (416 MB em
`H:`), dentro da arvore que o codigo le. **Prova por EXECUCAO**, com um segmento real na fila:

```
loading Parakeet ONNX from H:\sotto\worker\models\parakeet-redux-onnx-int4
model ready (onnx-int4)
seg-0001.wav state=done wall=10.4s
text='The radio announced that the bridge over the river will be closed next Monday. Residents need an alter.'
```

O `audio=0.0s` dessa linha e' da MINHA linha de indice de teste: `run_once` le `duration_s` do
`index.jsonl` (`audio_queue_consumer.py:170`) e a linha sintetica nao trazia o campo — nao e' defeito
de medida.

**O que continua em falta, e nao tem fonte**: o `nemotron-3.5-asr-ptbr-onnx-int4` (motor AO VIVO). O Hub
publica `nvidia/nemotron-3.5-asr-streaming-0.6b` (multilingue, pt-BR = 12) com `safetensors`, `.nemo` e
`.q8_0.gguf` — **nenhum export ONNX**, e este repo nao tem pipeline de quantizacao (`model_config.json`
do export diz `model_path=/datadisks/disk2/nebanfic/multilingual_onnx_int4_v3`, um caminho da maquina que
o produziu). O caminho GGUF tambem nao existe no produto: `worker/` so' conta `.gguf` como ficheiro de
pesos (`vram_residency.py:211`), nao o carrega.

### O motor LIVE tambem carrega com estes pesos (medido 2026-11-02)

`worker/redux_live.py` e' o mesmo runtime ONNX e nao precisava do nemotron para correr. Alimentado com
`--wav _main/en-us-sample.wav` (sem `--max-seconds`, que por contrato e' `0 = corre ate' pararem` — o
wav e' um alimentador de medicao e repete, nao um bug), o motor arrancou e emitiu o contrato completo:

```
{"model": "onnx-int4", "type": "caption", "text": "...", "start": 845.0, "end": 850.0,
 "final": true, "producer": "redux"}
LIVE_STATS passes=172 captions=342 finals=170 blocks=8946 audio_s=855.0 backlog_s=33.67
           peak=0.689819 overruns=172 mean_compute_s=5.16 max_compute_s=7.29
```

Duas leituras honestas deste numero, e nenhuma delas e' "o motor esta mau":

1. **`overruns=172/172` com `step_s=2.0` e `window_s=5.00`**: cada passe custa ~5,16 s para uma janela
   de 5 s, logo fica em ~0,97x do tempo real e o `backlog_s` sobe para 38 s e fica la. Nesta maquina
   (54 % de CPU, 24,4 GB de RAM livres no momento da medicao) o Redux ONNX **nao sustenta** o passo de
   2 s. E' exactamente a razao de a lei da stack pôr o nemotron no AO VIVO e o parakeet no fundo.
2. O motor de BATCH nao foi medido por este numero: o `wall=10.4s` da sonda de fila inclui o
   carregamento do ONNX (416 MB) dentro do mesmo `run_once`, portanto nao e' taxa de transcricao.

## RESOLVIDO 2026-11-02 — o nemotron voltou, de uma fonte publica que existe

Eu tinha dito que o Hub nao publica export ONNX deste modelo. **Errado para o que importa**: a busca
anterior olhou `nvidia/` e nao `onnx-community/`. O repo publicado e'

    onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4     revisao 8364d9e2dd9da23789b480bdbba9e423717e42ee

e o layout e' exactamente o que `worker/sotto_worker.py` le (ORT GenAI): `genai_config.json`,
`encoder.onnx` + `encoder.onnx.data`, `decoder.onnx`, `joint.onnx`, `vocab.txt`,
`audio_processor_config.json`, `model_config.json`, `tokenizer.json`, `silero_vad.onnx`.
Baixado para `worker/models/nemotron-3.5-asr-ptbr-onnx-int4` — **788 069 519 B em 16 ficheiros**,
contra os 783 537 972 B / 32 ficheiros registados do export local perdido (mesma familia, quantizacao
publicada por outra entidade).

**Os tres numeros normativos batem, lidos do proprio export** (nao assumidos):

```
blank_id=13087   chunk_samples=8960   max_symbols_per_step=10   left_context=56
decoder.hidden_size=640  decoder.num_hidden_layers=2
```

**Os cinco oraculos que estavam vermelhos por `SETUP ERROR` voltaram a verde:** `model-spec-oracle` 0,
`lang-id-oracle` 0, `word-split-oracle` 0, `vad-option-probe` 0, `_audit-fresh-processor-probe` 0
(arm1..arm5 GREEN, "two processors from one og.Model are independently buffered").

**Prova por execucao do motor AO VIVO** (`--audio`, sem dispositivo, headless):

| fixture | providers | load_s | rtf | peak_rss_mb | texto |
|---|---|---|---|---|---|
| `en-us-sample.wav` (8,4 s) | CUDA+CPU | 8,78 | **0,479** | 809 | *The Radio announced that the bridge over the river will be closed next Mone. Residents need an alternative route to get to work* |
| `en-us-sample.wav` | CPU so' | 10,75 | 3,078 | 422 | idem, byte a byte (logo e' deterministico, nao e' deriva de provider) |
| `live-sample-cable-input.wav` (30,1 s) | CUDA+CPU | 9,58 | **0,280** | 785 | *Bora fazer um gland* — 96 % blanks, 26 chunks vazios, 25 gated por VAD: o clipe e' quase todo silencio com uma frase |

`lang_id` resolveu 101 (auto) e 12 (pt-BR) pelos caminhos normais do `lang_prompt`, com a tabela lida de
`docs/model-specs/original/fp16/languages.json` (o export int4 nao traz `languages.json`, como o proprio
`lang_prompt.py:131` ja dizia).

**E o parakeet, na mesma maquina, no MESMO clipe de 30,1 s:** `audio=30.1s wall=12.8s (2.4x tempo
real)`, texto `Bora fazer um plein dout de aí.`. Os dois motores concordam que o clipe diz "bora fazer
um …" e divergem na palavra estrangeira — e' audio dificil, nao falha de um deles.

**O que NAO se afirma**: que este export tenha a mesma qualidade do `multilingual_onnx_int4_v3` local
perdido. Nao existe registo do texto do nemotron nesse clipe de 8,4 s com o artefacto antigo, portanto
uma comparacao seria invencao. O que esta' medido e' que o motor carrega, decodifica, respeita as
constantes e cabe em 810 MB de pico.

## Reproduzir a medicao

```
du -sh worker/models/*                      # o que esta' la, hoje
grep -n "model dir not found" _main/webview-run.log | tail -3
python -c "import json;print(json.load(open('worker/config.json'))['model']['dir'])"
python _main/model-spec-oracle.py           # rc != 0 enquanto o nemotron nao voltar
python _main/fetch-parakeet.py --verify     # o parakeet: GREEN hoje
python worker/sotto_worker.py --audio _main/en-us-sample.wav --max-seconds 60   # o ao vivo: rtf 0.479
```
