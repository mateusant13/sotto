# Separar o áudio por pessoa e depois correr o Parakeet Redux em cima — dá?

**Pergunta do dono, verbatim:** *"e se tem algum modelo que separa audio por pessoas encontradas no audio.
ao separar, ai usar o parakeet redux encima. nao sei se da. pesquisa bem."*

**Lane:** investigação (só escreveu em `_main/`). **Data:** 2026-10-08. **Não instalei nem corri nenhum
modelo pesado** — os números que não existem estão marcados como *NÃO MEDIDO* com o instrumento que os
mediria, em vez de serem inventados.

---

## 0. Resposta curta

| pergunta | resposta |
|---|---|
| Dá para separar o áudio por pessoa no caso dele (jogo ao vivo com amigos)? | **Só em condições restritas** — e nenhuma delas é o jogo ao vivo pelo cabo de loopback |
| O Redux pode correr "em cima" dos fluxos separados? | **Tecnicamente sim, economicamente não**: é batch, custa **N× tempo para N pessoas**, e o sinal que lhe chega é *pior* que o mix original |
| Alternativa melhor? | **Sim, e é a que um produto shipa:** diarização + **uma** passada de ASR com etiqueta de quem falou — o ASR corre **1×, não N×** |
| Já existe algo nesta máquina? | `sherpa-onnx 1.13.4` **já está instalado** e traz o pipeline de diarização. **Nenhum modelo de diarização ou de separação está em disco.** `pyannote.audio`/`speechbrain`/`nemo-toolkit` **ausentes** |
| Caminho mínimo com valor real? | Diarização (1 passada) + o Redux que já existe (1 passada) → transcrição com `pessoa 1/2/3` por linha |

**A frase que decide:** o que o dono quer chama-se **diarização** ("quem falou quando") e está resolvido
por modelos abertos; o que ele imagina que precisa chama-se **separação de fontes** (arrancar fisicamente
a voz de cada pessoa do mix) e degrada-se exactamente no áudio dele. E, no caso Discord, **a separação já
existe a montante** — o problema não está no modelo, está em quem o pode pedir.

---

## 1. As duas coisas que estão a ser confundidas

O dono — e o brief anterior que está em `H:\sotto\pesquisarsobre.txt` — já tinham chegado a esta
distinção; ela está escrita lá nas linhas 4322-4332 (*"Sortformer = diarização. Source separation =
separar fontes de áudio misturadas."*) e na 3613 (*"a própria NVIDIA deixa claro que diarização significa
'quem falou quando', não necessariamente remover fisicamente a voz do outro speaker"*). Concordo com
ambas e são o eixo deste relatório.

| | **DIARIZAÇÃO** | **SEPARAÇÃO DE FONTES** |
|---|---|---|
| o que responde | *quem* falou *quando* — segmentos etiquetados | dá-me N **sinais de áudio** separados |
| saída | lista `[início, fim, SPEAKER_xx]` | N ficheiros WAV |
| o mix original | **fica intacto** (é a entrada) | é destruído/reconstruído |
| como se treina | dados reais etiquetados (AMI, CALLHOME, DIHARD, VoxConverse) | quase sempre **misturas sintéticas** de 2 falantes limpos |
| no áudio do dono (jogo + amigos + música) | funciona, com erro a subir | **degrada** — é o regime onde os benchmarks mentem |
| custo de ASR depois | **1×** (o ASR corre sobre o mix, uma vez) | **N×** (N fluxos, cada um do tamanho do original) |
| licenças | há opções comerciais-OK (abaixo) | os pesos abertos que existem são de investigação |
| estado | **resolvido** | **em aberto fora do laboratório** |

**Citação decisiva para a segunda coluna** — [`arxiv 2111.07578`](https://arxiv.org/abs/2111.07578),
*"Monaural source separation: From anechoic to reverberant environments"*: pegar no **SepFormer** (o
estado da arte em misturas anecoicas) e re-optimizá-lo para misturas reverberantes dá **apenas
marginalmente melhor que um baseline PIT-BLSTM**; os próprios autores escrevem que isto é *"surprising
and at the same time sobering, challenging the practical usefulness of many improvements reported in
recent years for monaural source separation on nonreverberant data"*. **citado** — e é o resumo perfeito
de "o benchmark não sobrevive à sala".

**Onde os modelos de separação são treinados** — [`arxiv 2505.05114`](https://arxiv.org/abs/2505.05114)
(LExt, TSE, IEEE TASLP) lista os conjuntos de avaliação do campo: **WSJ0-2mix, WHAM!, WHAMR!** — todos
misturas de **dois** falantes montadas a partir de voz limpa, com ruído/reverberação **adicionados
sinteticamente**. **citado.** Não existe um conjunto "jogo com quatro amigos no Discord por cima de
música".

---

## 2. P1 — "Dá no meu caso?" → **Só em condições restritas**

Separo as condições, porque umas são satisfazíveis hoje e outras não.

### 2.1 O que a diarização dá, e com que erro

| modelo | licença | falantes | erro publicado | corre onde |
|---|---|---|---|---|
| **`nvidia/Nemotron-3-Diarization`** | **`openmdw-1.1`** — o cartão diz *"ready for commercial or non-commercial use"* | **até 8** | o cartão não publica DER no extracto que li | NeMo-Speech.cpp (C++ nativo) ou `nemo-toolkit[asr]` |
| `nvidia/diar_sortformer_4spk-v1` | **`cc-by-nc-4.0` — NÃO comercial** | 4 | **DIHARD3-eval DER 14,76**; CALLHOME 2spk 5,85 / 3spk 8,46 / 4spk 12,59; CHAES 6,86 | NeMo |
| `pyannote/speaker-diarization-3.1` | **MIT mas GATED** — aceitar condições em `pyannote/speaker-diarization-3.1` **e** `pyannote/segmentation-3.0` + token HF | livre | não li a tabela | `pyannote.audio>=3.1`, PyTorch puro |
| **sherpa-onnx** (segmentação + embedding + clustering) | conforme o modelo que se escolher | `num_clusters` explícito | o exemplo do vendor: 56,861 s em **9,688 s** ⇒ **RTF 0,170 (~5,9× tempo real em CPU)** | **`sherpa-onnx` JÁ INSTALADO aqui** |

Todas as linhas da tabela são **citadas** dos cartões/documentação respectivos (URLs na §8).

**O número que assusta e deve assustar:** `DIHARD3-eval = 14,76 DER` no modelo de 4 falantes. DIHARD é o
conjunto *difícil* do campo (áudio "na selva": entrevistas, restaurantes, reuniões gravadas com um
microfone só) — que é **muito mais parecido** com o caso do dono do que AMI ou VoxConverse. **inferência
minha:** num jogo com música por baixo, o DER vai ser pior que 14,76, e 14,76 já significa que ~15% do
tempo falado fica com a etiqueta errada ou sem etiqueta. Isto é utilizável para "quem falou isto?", não é
utilizável para "transcreve só o que o João disse".

**Boa notícia estrutural:** `Nemotron-3-Diarization` é **streaming** com latência configurável (mínimo
80 ms, recomendado 0,32 s, offline 30,4 s), até 8 falantes, inferência em blocos ⇒ duração ilimitada, e
`nemo-speech transcribe meeting.wav --diarize --json` devolve **etiquetas de falante ao nível da
palavra**. É literalmente a forma do produto que o dono quer, em C++, com licença comercial-OK.
**citado.**

### 2.2 As condições em que a separação por pessoa funciona

1. **Se a separação já vier feita a montante.** É o caso do **Discord**: o próprio gateway de voz entrega
   **um fluxo por utilizador**. Citado de [`@kirdock/discordjs-voice-recorder`](https://github.com/Kirdock/discordjs-voice-recorder),
   secção *"Why is voice recording with discord.js such a big pain?"*: *"We don't have a single track for
   a voice channel. **Each user has its own stream.**"* — e o README promete exportar um `.zip` **com
   uma faixa por utilizador**. **Isto é a resposta que o dono realmente quer**, e não precisa de nenhum
   modelo de separação. **Mas exige ser um cliente/bot dentro da chamada** (token de bot, permissões,
   `discord.js`, ffmpeg) — **inferência minha** a partir de o pacote ser uma biblioteca `discord.js`.
   Um programa **externo** que só ouve o cabo de loopback **não tem** esses fluxos: para ele o Discord é
   um mix, ponto.
2. **Se houver 2 falantes, gravação limpa, sem música e sem sobreposição.** É o regime dos conjuntos de
   treino. Sai do caso do dono.
3. **Se houver uma frase de inscrição (*enrollment*) de cada pessoa.** Aí entra **target-speaker
   extraction**: `arxiv 2505.05114` define-o literalmente como *"Given an enrollment utterance of a
   target speaker, LExt aims at extracting the target speaker from the speaker's mixed speech with other
   speakers"*. **citado.** Ou seja: o campo inteiro de "arrancar uma pessoa do mix" **pressupõe que já
   tens um exemplo limpo da voz dessa pessoa**. No jogo ao vivo, ao vivo, não tens.

### 2.3 Veredito P1

**Só em condições restritas.** No caminho do Sotto (capturar o loopback do que toca no PC) a condição
"2 falantes limpos" não se verifica e a condição "enrollment" não existe em tempo real. A condição que
**se verifica** é a 1 — mas ela não é um modelo, é **mudar de onde se lê o áudio**: em vez de
loopback, pedir os fluxos por utilizador ao Discord. **É a única rota que dá separação perfeita, e é
grátis em CPU** (custa um bot e uma decisão de arquitectura).

---

## 3. P2 — "E usar o Parakeet Redux por cima?" → sim, mas paga N×

### 3.1 O Redux é batch, e a factura é de tempo, não de RAM

O Redux nesta caixa (medido por outra lane, registado em `AGENTS.md`; **não repeti a medição**):
`worker/redux_batch.py` corre o ternário `moondream/parakeet-redux` via runtime do vendor —
**15 s de áudio em 1,1–2,1 s = 7–14× tempo real**, carga 3,6–4,3 s, **pico 3,90 GB RSS** porque o kernel
int8 compilado do kestrel está inacessível (`_cpu.ternary_gemm_isa()` → `'scalar'`) e o runner cai na
forma *dense* documentada (193/193 camadas desquantizadas). **medido.**

**Uma correcção ao enquadramento do brief, que importa para a decisão:** N fluxos separados **não**
custam N× a RAM. Se carregar o modelo **uma vez** e iterar os fluxos em série, a RAM fica em 1× (os
3,90 GB) e o que fica N× é o **tempo**. Só se paralelizar é que a RAM vai a N×. **inferência minha**
sobre a medição acima — ninguém mediu ainda o caso "N fluxos, um modelo".

### 3.2 A conta, em números, para 1 hora de jogo com 4 pessoas

| passo | 1 passada (mix) | cadeia imaginada (separar → 4× Redux) |
|---|---|---|
| separação | — | **NÃO MEDIDO** (não há modelo de separação por falante em disco; ver §4) |
| ASR Redux (ternário local, 7–14×) | 1 h ÷ 14…7 = **257–514 s (4,3–8,6 min)** | **4× isso = 17–34 min** |
| RAM no pico | 3,90 GB (medido) | 3,90 GB se em série; **~15,6 GB se 4 em paralelo** |
| qualidade do áudio que entra no ASR | o mix real | 4 fluxos reconstruídos, com artefactos e voz residual dos outros |
| resultado | transcrição do mix | 4 transcrições, cada uma com **o que o separador não conseguiu tirar** |

**O Redux ONNX int4 é o caminho leve, e é o que interessa para "motor de fundo".** O export
`eschmidbauer/parakeet-redux-onnx` (~344 MB encoder + 72 MB decoder, `onnxruntime>=1.22` + numpy e mais
nada) **está de novo em disco** em `worker/models/parakeet-redux-onnx-int4/`. O seu RSS é **~450 MB
— ESTIMATIVA, não medição.** O cartão do Redux dá, para a variante ONNX int8 do *v3* via sherpa-onnx,
**0,67 GB e 42× tempo real** — mas num **EPYC 9575F**, não nesta caixa. **citado, máquina diferente.**

### 3.3 Veredito P2

**Dá, e é má economia.** Para N pessoas: N× o tempo de ASR, mais o custo (não medido, provavelmente
comparável ao ASR) da própria separação, para obter **pior áudio** do que aquele que já entra no Redux
hoje. Um motor de fundo "leve", como a LEI DA STACK o define, é o oposto disto.

---

## 4. P3 — A alternativa que um produto shipa

### 4.1 As três formas, comparadas

| forma | ASR corre | precisa de enrollment | qualidade no áudio do dono | licença |
|---|---|---|---|---|
| **A. separar → ASR por fluxo** (a ideia do dono) | **N×** | não | pior que o mix | pesos abertos são de investigação |
| **B. diarizar → ASR por segmento** | ~1× (só o falado) | não | igual ao mix | há opções comerciais-OK |
| **C. target-speaker ASR** (TS-VAD / SpEx+) | N× (um por alvo) | **SIM** — voz de inscrição | bom se o enrollment for bom | investigação |

**A documentação da própria NVIDIA contrasta B e C**, no índice de modelos do NeMo, ao descrever a
diarização: *"No Speaker Enrollment: Unlike target-speaker ASR systems that require pre-enrollment audio
or speaker embeddings…"* — **citado** (é também a razão pela qual C não serve o caso do dono: no jogo
não há inscrição prévia).

**O que um produto shipa:** nem A nem C — **B**, ou melhor ainda, **a captura por participante** (§2.2).
Zoom/Teams/Meet não separam o mix de ninguém: cada cliente **envia o seu próprio microfone** e o servidor
junta. O Discord é o mesmo caso, e está citado acima. A diarização existe nesses produtos para o caso em
que só há **uma** gravação (uma sala, uma gravação de reunião), que é exactamente a situação do dono
**se** ele ficar no caminho do loopback.

**E há uma forma melhor que B:** `nemo-speech transcribe meeting.wav --diarize --json` faz **a
transcrição e a etiquetagem de falante numa só passada**, com marcas ao nível da palavra. **citado.**

### 4.2 O achado local que poderia tornar isto grátis

**Os pesos do Redux já trazem os tokens de diarização no vocabulário.** Lido directamente do
`vocab.txt` em disco:

```
<|diarize|>        12
<|nodiarize|>      13
<|spkchange|>      14
<|audioseparator|> 15
```

Aparecem **em todos** os vocabulários Parakeet em disco (instrumento e controlo positivo na §7):
`worker\models\parakeet-redux-ternary\`, `worker\models\parakeet-redux-reference\`,
`worker\models\parakeet-redux-onnx-int4\`, `aireplay\models\parakeet-tdt-0.6b-v3-onnx\`. **medido.**

**Mas isto NÃO é uma funcionalidade do Redux, e é aqui que é preciso não se entusiasmar:**

- O cartão do Redux diz que é *"same architecture, same tokenizer"* do `nvidia/parakeet-tdt-0.6b-v3` e
  que *"output conventions are the original's"* — **citado**. Os tokens vêm do tokenizador herdado, que
  é o da família **Canary/Parakeet** onde `<|diarize|>`/`<|spkchange|>` são convenções de **Canary**.
  **inferência minha.**
- O runner de referência que está em disco, `worker/models/parakeet-redux-reference/transcribe.py`
  (401 linhas, lido), **nunca pede** `<|diarize|>` e **não tem ramo nenhum** para `<|spkchange|>` nem
  para `<|audioseparator|>` — `SKIP_PIECES = {"<unk>", "<pad>", "<blk>"}` e mais nada. **medido.**
- As secções que li do cartão do v3 (métricas, licença, uso, *safety*) **não reivindicam diarização**. O
  meio da página foi truncado pelo instrumento de fetch, portanto **NÃO afirmo que o cartão não a
  mencione** — ver o falsificador na §6.

**Capacidade presente no vocabulário ≠ capacidade presente nos pesos.** Um token que nunca é emitido é
vocabulário morto. **Não sei se o Redux sabe diarizar; sei que ninguém aqui lhe pediu.**

### 4.3 Veredito P3

**B ganha, e por muito.** Uma passada de ASR (a que o Sotto já faz) + uma passada de diarização dá
transcrição com etiqueta de pessoa. A separação (A) multiplica o ASR por N para piorar o sinal; o
target-speaker (C) exige uma coisa que o dono não tem ao vivo.

---

## 5. P4 — O que já existe nesta máquina

### 5.1 Presente e utilizável já

- **`sherpa-onnx 1.13.4+cuda12.cudnn9`** — **instalado**, sondado nesta sessão
  (`H:\sotto\_main\_spk-pkg-probe.py`). A documentação do próprio pacote diz que a diarização precisa de
  **`sherpa-onnx>=1.10.28`** — **temos 1.13.4, satisfaz**. O pipeline é *segmentação de falante* +
  *extractor de embedding de falante* + `FastClusteringConfig`. **citado.**
- `torch 2.7.0+cu128`, `torchaudio 2.7.0+cu128`, `onnxruntime 1.30.0`, `onnxruntime-gpu 1.30.0`,
  `faster-whisper 1.2.1`, `librosa 0.11.0`, `soundfile 0.14.0`, `silero-vad 6.2.1`, `kestrel 0.9.1`,
  `moondream 2.6.1`, `transformers 5.15.0`, `numpy 1.26.4`. **medido.**
- **`torch.cuda.is_available()` é TRUE** (RTX 5080) — a nota antiga "CUDA não carregável" vale para o
  `CUDAExecutionProvider` do ORT, **não** para o torch.

### 5.2 Ausente (e ausente com instrumento, não por impressão)

- **`pyannote.audio`, `speechbrain`, `nemo-toolkit`** — `PackageNotFoundError` na sonda desta sessão.
  **medido.** Adoptar qualquer um é uma **instalação nova** — que esta lane **não fez**.
- **Nenhum modelo de diarização ou de separação em disco.** Instrumento: `Get-ChildItem H:\sotto,H:\aireplay
  -Recurse -File -Include *segmentation*.onnx,*speaker*.onnx,*titanet*,*ecapa*,*campplus*,*wespeaker*,
  *3dspeaker*,*sortformer*,*diar*,*sepformer*,*demucs*,*spkrec*` (excluindo `node_modules|site-packages|_epvenvs`)
  devolveu **apenas ficheiros `.md` de diário**. **Controlo positivo passado:** o mesmo estilo de wildcard
  em `*encoder*.onnx` encontrou os 5 encoders de ASR conhecidos — logo o instrumento vê. Busca por **nome
  de directório** (`diar|spk|speaker|embed|ecapa|titanet|wespeaker|sepformer|demucs`): **vazio**.
- **Cache HF ausente:** `Test-Path "$env:USERPROFILE\.cache\huggingface\hub"` → `False`. **medido.**

### 5.3 O que é o `google/embeddinggemma-2` (a pergunta lateral)

**Não é um modelo de voz de falante, e não serve para isto.** Segundo
[`H:\aireplay\docs\research\06-embeddings.md`](H:\aireplay\docs\research\06-embeddings.md) (lane
anterior), é um modelo de **embedding multimodal** (texto+imagem+vídeo+áudio) da Google que produz
**um vector de 768 dimensões por chamada**, 740M parâmetros, ~1,49 GB de download, quatro patamares.
O exemplo do próprio cartão é cross-modal: `cos(imagem_vermelha, "a solid red square") = 0,7290`.
**É embedding semântico para recuperação, não embedding de verificação de falante** — a família certa
para isso é ECAPA-TDNN / TitaNet / CAM++ / WeSpeaker, e **nenhuma está em disco** (§5.2).
Nota local do mesmo ficheiro: `transformers 5.15.0` **não tem** `EmbeddingGemma2Model`.

---

## 6. P5 — O caminho mínimo com valor real

**Recomendação, uma só:** **diarizar e transcrever, cada um numa passada, e juntar por tempo.**

```
áudio (o mix que o Sotto já captura)
   ├─→ Redux, 1 passada  → texto + timestamps        ← JÁ EXISTE e está provado
   └─→ diarização, 1 passada → [início, fim, SPK_xx] ← sherpa-onnx JÁ INSTALADO
                    ↓
        junção por sobreposição temporal
                    ↓
   linha de transcrição com "pessoa 1 / pessoa 2" (nomes só com enrollment)
```

**Custo:** o ASR **não muda** (é exactamente o que o Sotto já corre: 4,3–8,6 min por hora de áudio no
caminho ternário). Acresce a diarização: no exemplo do próprio vendor, **RTF 0,170 em CPU** ⇒ ~10 min por
hora de áudio; **nesta caixa é NÃO MEDIDO**, e a primeira coisa a medir.

**O que isto dá ao dono:** a transcrição que ele já tem, agora com **quem** falou. **O que não dá:**
ficheiros de áudio por pessoa. **inferência minha:** ele vai perceber que não precisa deles — o que ele
quer é saber quem disse o quê.

**Porque é que isto é melhor que a ideia original, em uma linha:** a separação é o único passo da cadeia
que **estraga** o sinal e **multiplica** o custo; a diarização é o único passo que dá a informação
pedida sem tocar no sinal.

**Ordem de trabalho se o dono disser sim:** (1) medir a diarização nesta caixa com um clipe real dele;
(2) se o DER for utilizável, juntar por tempo ao `final` do Redux. **Nenhum dos dois passos exige
instalar nada** — o `sherpa-onnx` já lá está. Só é preciso **descarregar os modelos de diarização**
(segmentação + embedding), que são pequenos e ainda **não estão em disco** (§5.2).

---

## 7. O que decidiria isto — as medições exactas que faltam

Estas são as perguntas cuja resposta muda a decisão. Nenhuma foi corrida por mim; cada uma nomeia o
instrumento.

1. **A diarização funciona no áudio DELE?** — **A medição que decide tudo.**
   Correr o pipeline de diarização do `sherpa-onnx` (segmentação + embedding + clustering) sobre um clipe
   real do dono: 5–10 min de jogo com amigos a falar por cima de música. Medir **DER** contra uma
   etiquetagem manual de 2 min, e **RTF nesta caixa**. Referência a bater: o `DIHARD3-eval = 14,76` do
   sortformer de 4 falantes (que é o conjunto *difícil*). **Se o DER passar de ~25% em áudio com música, a
   recomendação da §6 morre** e a resposta honesta passa a ser "só com captura por participante".
2. **O Redux sabe diarizar?** — **Falsificador barato, e pode tornar a §6 grátis.**
   Correr o `transcribe.py` que está em `worker/models/parakeet-redux-reference/` sobre o clipe de 15 s já
   existente, **forçando o prompt para `<|diarize|>`** (id 12), e registar se o id **14** (`<|spkchange|>`)
   aparece **alguma vez** na saída greedy. Se nunca aparecer sob nenhum prompt, **os tokens são vocabulário
   morto** e a §4.2 fecha. **Se aparecer, o Sotto ganha diarização sem modelo nenhum.** Este teste é meu
   *pedido* e não minha execução — outra lane é dona das medições do Redux.
3. **Qual é o RSS real do export ONNX int4?** — `worker/models/parakeet-redux-onnx-int4/` está de novo em
   disco. O ~450 MB é **estimativa**. Medir o pico de RSS ao correr `transcribe.py` desse export. Se
   ficar em 450–900 MB, é ele que deve ser o "motor de fundo leve" da LEI DA STACK, e os 3,90 GB do
   ternário desaparecem.
4. **O `--device cuda` do runner ternário funciona?** — `torch.cuda.is_available()` é TRUE e a RTX 5080
   está lá. Se funcionar, a factura de tempo da §3.2 cai de uma ordem de grandeza. Ninguém testou.
5. **O Discord expõe fluxos por utilizador a um programa externo?** — Citado que **um bot** os tem
   (§2.2). **NÃO VERIFICADO:** se existe alguma via para uma app de terceiros que não seja um bot dentro
   da chamada. Se existir, é a melhor resposta ao pedido original e **não precisa de modelo nenhum**.
6. **O cartão do `parakeet-tdt-0.6b-v3` menciona diarização?** — o meio da página foi truncado no fetch.
   Reler as secções *Model Architecture* / *How to use* e procurar `diariz`/`spkchange`. Se o cartão
   descrever a convenção, a §4.2 passa de "inferência minha" a **citado**.

---

## 8. Fontes citadas

- Redux (ternário): [`moondream/parakeet-redux`](https://huggingface.co/moondream/parakeet-redux) — CC-BY-4.0, "same architecture, same tokenizer", pior em ruído MUSAN (9,04 vs 6,72).
- ASR base: [`nvidia/parakeet-tdt-0.6b-v3`](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) — CC-BY-4.0; métricas AMI/Earnings-22/LibriSpeech/TED-LIUM.
- Diarização comercial-OK: [`nvidia/Nemotron-3-Diarization`](https://huggingface.co/nvidia/Nemotron-3-Diarization) — `openmdw-1.1`, 8 falantes, 80 ms–30,4 s, NeMo-Speech.cpp `--diarize --json`.
- Diarização não-comercial: [`nvidia/diar_sortformer_4spk-v1`](https://huggingface.co/nvidia/diar_sortformer_4spk-v1) — `cc-by-nc-4.0`, tabela de DER.
- Diarização gated: [`pyannote/speaker-diarization-3.1`](https://huggingface.co/pyannote/speaker-diarization-3.1) — MIT, mas token + condições.
- sherpa-onnx diarização: [índice](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html), [API Python](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/python.html) (`>=1.10.28`), [modelos](https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/models.html) (RTF 0,170).
- sherpa-onnx **separação de fontes**: [índice](https://k2-fsa.github.io/sherpa/onnx/source-separation/index.html), [modelos](https://k2-fsa.github.io/sherpa/onnx/source-separation/models.html) — **só Spleeter 2-stem e UVR**, i.e. *vocais vs acompanhamento*, **nunca por falante**; Spleeter RTF 0,079, UVR RTF 0,732 (1 thread, desktop).
- Separação degrada na reverberação: [`arxiv 2111.07578`](https://arxiv.org/abs/2111.07578).
- Target-speaker extraction exige enrollment: [`arxiv 2505.05114`](https://arxiv.org/abs/2505.05114) (WSJ0-2mix, WHAM!, WHAMR!).
- Discord entrega um fluxo por utilizador: [`Kirdock/discordjs-voice-recorder`](https://github.com/Kirdock/discordjs-voice-recorder).
- NeMo: "No Speaker Enrollment: Unlike target-speaker ASR systems that require pre-enrollment audio or speaker embeddings" — índice de modelos do NeMo.
- In-repo: [`H:\aireplay\docs\research\04-asr.md`](H:\aireplay\docs\research\04-asr.md) (linha 120: *"Overlapping speech is nobody's solved case… None of the three is a diarizer"* — **esta lane corrige e supera essa linha**: existem diarizadores, e um deles é comercial-OK), [`H:\aireplay\docs\research\06-embeddings.md`](H:\aireplay\docs\research\06-embeddings.md), [`H:\sotto\pesquisarsobre.txt`](H:\sotto\pesquisarsobre.txt) linhas 2955-2961, 3613, 4322-4332.

---

## 9. Instrumento das ausências (para que "não existe" seja uma afirmação e não uma impressão)

| afirmação | instrumento | cadência/contagem | controlo positivo |
|---|---|---|---|
| nenhum modelo de diarização/separação em disco | `Get-ChildItem -Recurse -File -Include <16 wildcards>` em `H:\sotto` + `H:\aireplay` | 1 passagem, só `.md` de diário | wildcard `*encoder*.onnx` encontrou os 5 encoders de ASR |
| nenhum directório de diarização | busca por nome de directório | vazio | a mesma busca por `models` devolve 2 |
| `pyannote.audio`/`speechbrain`/`nemo-toolkit` ausentes | `_main\_spk-pkg-probe.py` (importlib.metadata) | 451 distribuições listadas | 11 pacotes de fala presentes, incluindo `sherpa-onnx` |
| cache HF ausente | `Test-Path` no caminho do hub | 1 | o caminho existe na máquina depois de downloads anteriores |
| tokens de diarização no vocabulário | grep `<|spkchange|>` | 6 ficheiros, todos `vocab.txt` | os mesmos ficheiros contêm `<|endoftext|>` |

**Limite declarado:** as ausências acima valem para **esta revisão do disco**. Um `Get-ChildItem` é um
instantâneo — se uma lane descarregar um modelo de diarização amanhã, esta tabela fica velha sem avisar.
