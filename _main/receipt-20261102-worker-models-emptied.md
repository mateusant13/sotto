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

## Reproduzir a medicao

```
du -sh worker/models/*                      # o que esta' la, hoje
grep -n "model dir not found" _main/webview-run.log | tail -3
python -c "import json;print(json.load(open('worker/config.json'))['model']['dir'])"
python _main/model-spec-oracle.py           # rc != 0 enquanto o nemotron nao voltar
```
