# ARK-ASR-0.6B: e' melhor que o Parakeet, ou que o nemotron? (medido, 2026-10-30)

Ordem do dono, verbatim: *"edge0 ark asr 0.6b < veja se é melhor que o parakeet, ou
melhor que o nemotron atual. usa caso sim."*

**VEREDICTO: NAO.** Nos dois lugares onde um motor pode entrar neste repo — o
fundo/batch (Parakeet Redux) e o ao vivo (nemotron) — o ARK-ASR perde nas tres
metricas que decidem, e no portugues **traduz em vez de transcrever**. Nada foi
integrado; o que segue e' a medicao.

## 1. O que foi medido, e com que instrumento

Duas metades, e a diferenca esta' dita: o **parakeet e o nemotron** correm na minha
harness (`_main/engine-compare.py`, guardada no repo para re-medir), com o MESMO wav
(16 kHz mono, resample por `soxr` quando a fonte e' 22 050 Hz) e as mesmas quatro
medidas (`load_s`, `infer_s`, `xRT` = audio decorrido / tempo de parede, pico RSS).
O **ARK** corre pelo script que o proprio publicador do modelo entrega
(`infer_ark_audio_onnx.py`), com a mesma fonte de 16 kHz e o mesmo relogio em volta —
reimplementar o decode dele seria medir a minha copia, nao o modelo.

- Parakeet: `worker/redux_live.OnnxBackend` sobre `worker/models/parakeet-redux-onnx-int4` (416 MB).
- nemotron: `worker.sotto_worker.StreamAsr` sobre `worker/models/nemotron-3.5-asr-ptbr-onnx-int4` (748 MB), alimentado a 560 ms por bloco (o passo do ao vivo).
- ARK-ASR: `Edge0/ark-asr-0.6b-int8-onnx` (1,77 GB em disco), pelo script que o
  proprio repo publica (`infer_ark_audio_onnx.py`, int8, CPU).

Clipes: `_main/pt-br-sample.wav` (15,0 s) e `_main/en-us-sample.wav` (8,5 s).

| motor | clipe | audio | infer | xRT | pico RSS | texto |
|---|---|---|---|---|---|---|
| **parakeet-onnx-int4** | pt-BR | 15,0 s | **2,04 s** | **7,36×** | **653 MB** | *O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira. Os moradores precisam de um caminho alternativo para chegar ao trabalho.* — exacto |
| **parakeet-onnx-int4** | en-US | 8,5 s | 1,25 s | 6,83× | 598 MB | *The radio announced that the bridge over the river will be closed next Monday. Residents need an alternative route to get to work.* — exacto |
| **nemotron-int4** (560 ms) | pt-BR | 15,0 s | 18,20 s | 0,82× | 1232 MB | pt-BR reconhecivel (a harness imprime o texto cru dos blocos, com os tokens de tempo; nao e' o texto formatado do worker) |
| **ark-asr-0.6b-int8** | en-US | 8,5 s | 31,25 s | **0,27×** | **2358 MB** | *The radio announced that the bridge over the river will be closed next Monday. Residents need an alternative route to get to work.* — exacto |
| **ark-asr-0.6b-int8** | pt-BR | 15,0 s | 24,51 s | 0,61× | **2478 MB** | *The radio announced that the bridge over the river will be **interdited** on the **next second Friday**. The **mor零ers** need **a** alternative route to get to work.* — **INGLES**, com erros |

Comandos:

```
python _main/engine-compare.py _main/pt-br-sample.wav,_main/en-us-sample.wav --engine parakeet
python _main/engine-compare.py _main/pt-br-sample.wav --engine nemotron
python H:\ark-asr-probe\infer_ark_audio_onnx.py --audio I:\cc-tmp\pt-br-sample-16k.wav
```

## 2. Porque e' que isto decide, e nao e' discussao de gosto

1. **O portugues nao esta' na lista dele.** O cartao do modelo (e os metadados do
   HF) listam 19 linguas — zh, en, de, ja, fr, ko, es, pl, it, ro, hu, cs, nl, fi,
   hr, sk, sl, et, lt — e **pt nao esta'**. Medido no clipe pt-BR: saiu **ingles**
   ("interdited", "next second Friday", "mor零ers"), ou seja o modelo **traduziu**
   em vez de transcrever. Contra a lei do repo (*"legendas nao traduzem"*), e
   contra a unica lingua que o dono usa todos os dias.
2. **Nao faz ao vivo.** E' um encoder Whisper-style + decoder Qwen2 autorregressivo
   em janelas de 30 s (`max_audio_seconds=30`, `max_new_tokens=256`). Nao ha modo de
   chunk/estado incremental: nao substitui o nemotron, que entrega texto a cada
   560 ms.
3. **Custa 3,8× mais RAM que o parakeet** (pico 2 478 MB contra 654 MB) e e' **~9× mais lento** no mesmo clipe (0,61× contra 7,36× de tempo real). A regra da casa
   escolhe o motor de fundo pelo **preco em RAM**; aqui nao ha' empate — perde nas
   duas.
4. **A pilha e' outra.** Pede `torch` + `transformers` com `trust_remote_code=True`
   (codigo remoto executado), enquanto o caminho do repo e' ONNX Runtime puro. O
   export int8 ONNX existe e foi o que medi; mesmo assim, 1,77 GB de ficheiros novos
   contra 416 MB do parakeet int4.

## 3. O que mudaria a resposta (para nao se repetir a medicao por engano)

- Um checkpoint **com portugues** e **sem traducao** (existe um `ARK-ASR-3B-NoTranslate`
  de terceiros; nao medido — 3B, e o dobro do custo de RAM).
- Um modo **streaming/incremental** publicado pelo autor: enquanto for janela de 30 s
  autorregressiva, nao entra no lugar do nemotron.
- Se algum dia entrar, o lugar seria o **fundo**, e passaria por um export ONNX com
  menos RAM que os 615 MB do parakeet — nenhum dos builds publicos chega la'.

## 4. O que esta' no disco depois disto

- `H:\ark-asr-probe\` (1,77 GB + o `model/` duplicado) = **apagado** no fim desta
  medicao; o repo nao ganhou um byte.
- Nenhum ficheiro de `H:\sotto` foi alterado por esta investigacao, e nenhuma
  dependencia nova foi instalada (`torch`, `transformers` e `onnxruntime` ja' estavam
  presentes).
- Lease `heavy` da frota **devolvido** no fim (`performance-gate.py release`).

## 5. SELF-AUDIT — o que este recibo NAO prova

1. **O texto do nemotron nao foi formatado.** A harness le o retorno por bloco; o
   `held`/timing tokens que aparecem na linha sao do meu extrator, nao do worker. A
   comparacao de *qualidade* entre nemotron e ARK no pt e' portanto grosseira — mas
   a decisao nao depende dela: depende da lingua e do custo.
2. **CPU, nao GPU.** Na GPU os numeros do ARK mudam (a build int8 e' de CPU; a
   `onnxruntime_providers_cuda.dll` desta maquina nao carrega — falta
   `cublasLt64_13.dll`, medido no log). Nao ha' GPU no caminho do Sotto hoje.
3. **Um clipe por lingua, 8,5 s e 15 s.** Nao e' WER sobre corpus: e' a decisao
   "entra ou nao entra", e para isso o clipe e a lista de linguas bastam.
4. **A primeira passagem desta medicao correu os dois clipes no MESMO processo** e
   o segundo saiu contaminado (`parakeet` en a 2,41× contra 6,83× num processo
   limpo; `nemotron` pt a 0,61× contra 0,82×). A tabela acima e' a dos processos
   SEPARADOS, que e' a comparavel; a variacao entre eles nao foi investigada alem
   disto e fica escrita para quem repetir.

**`verified` nao se escreve aqui**: uma corrida real da app, com o dono a ver, nao
aconteceu. O que existe e' medicao em processo, com instrumento e numeros.
