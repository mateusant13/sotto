# DeepInfer — o que se transfere para o Sotto (e o que não)

**Data:** 2026-10-23 · **Fonte:** `https://github.com/deepseek-ai/DeepInfer` (clone raso em
`I:\cc-tmp\deepinfer`, 4,6 MB, fora do repo — não polui a árvore).

## O que o DeepInfer é, sem rodeios

Um motor de **serving de LLM** (DeepSeek-V4.1-Flash) para Linux, **SM100** (Blackwell) e Ascend 950,
construído sobre vLLM/SGLang/TensorRT-LLM. Traz kernels próprios (FlashMLA, DeepGEMM, DeepEP),
paralelismo MoE/EP, EPLB, KV cache, prefill/decode disaggregation, e — a parte interessante — três
**ideias de política** que não dependem do hardware.

O Sotto não é um servidor de LLM: é um **ASR RNNT** (nemotron, 747 MB) em ONNX Runtime GenAI, Windows,
uma GPU de consumidor, com o Parakeet como segundo pass. **Nenhuma linha de código se aproveita**, e o
próprio README o diz: exige GCC ≥ 13, CUDA 13, Python 3.12, Linux. O que se transfere são **conceitos**,
e três deles atacam exactamente os problemas medidos neste repo.

---

## 1. *Bounded replay* → o segundo pass do Sotto (o mais directo)

**No DeepInfer:** `DEEPINFER_YOCO_PREFILL_TRUNCATION_MODE=compact` +
`DEEPINFER_YOCO_PREFILL_KEEP_TOKENS=140`. Em vez de reprocessar o prefill inteiro, **reproduz só uma
cauda limitada** (a janela SWA + o máximo de backtracking). O código está em
`deepinfer/model_executor/input_metadata/yoco.py` e `.../models/v4_modules/yoco.py`; a equivalência é
testada em `examples/yoco/yoco_equiv.py` (52 KB — um teste **diferencial** contra o caminho completo).

**No Sotto:** o segundo pass (redux) re-transcreve áudio. A versão com replay limitado é: **re-decodificar
só uma janela à volta da região instável** — a cauda desde o último token estável, com margem — em vez
da utterance inteira. Isto é "fewer trips to memory" a sério: menos áudio descodificado, menos memória
tocada, mesmo resultado.

**O portão que o DeepInfer ensina a exigir:** o `yoco_equiv.py` existe porque a optimização **muda o que
o modelo vê**. Em Sotto, a afirmação equivalente é "o texto com replay limitado é igual ao texto com
replay completo". Isso é um teste **diferencial** sobre um corpus, não uma opinião.

## 2. Verificação agendada por confiança → escolher ONDE gastar o Parakeet

**No DeepInfer:** `DSpark` + *confidence-scheduled verification* — gera tokens draft e usa **estimativas
de confiança** para decidir quando vale a pena verificar (`DEEPINFER_USE_NEXTN_DECODE`, default 5).

**No Sotto:** já há dois motores, e o `AGENTS.md` §3 manda "lifecycle inteligente". O conceito que falta
é o **critério**: correr o Parakeet onde a confiança do pass ao vivo é baixa (score por token baixo,
fronteira de chunk a cair a meio de uma palavra, VAD instável) e **não** correr onde é alto. Hoje o
segundo pass é agendado pelo *estado* (visível/escondido, park, piso de 45 s) e não pela *dúvida*.

**O portão:** fracção de áudio re-decodificado (tem de descer) **e** qualidade (não pode descer). Um
número sem o outro é uma optimização que mente.

## 3. *Batch invariance* e determinismo → um portão de PROPRIEDADE que o Sotto não tem

**No DeepInfer:** `DEEPINFER_BATCH_INVARIANT=1` e `DEEPINFER_ENABLE_MTP_VARLEN=0` + `seq_seed` fixo
existem porque **a composição do batch muda silenciosamente o resultado**. É uma propriedade anunciada,
não um acidente.

**No Sotto:** as fronteiras de chunk dependem da **chegada em tempo real** do áudio, logo o mesmo WAV
pode produzir texto diferente conforme o timing. É exactamente a classe de defeito do dono
("legendas instáveis", "palavras partidas"). O portão: **mesmo WAV, dois tamanhos de chunk, texto igual**
(tolerando apenas o que a política de junção de fragmentos declarar). Isto é implementável hoje com o
caminho `--audio` que já existe, e é o item mais barato dos três.

## 4. (menor) *Asynchronous scheduling* — sobrepor CPU e GPU

No DeepInfer é o *batch scheduler* a correr em paralelo com a execução no device. No Sotto o laço RNNT é
**Python síncrono**: codifica o chunk e só depois descodifica tokens. Sobrepor o encode do chunk N+1 com
o decode do chunk N é uma vitória de **latência** (não de memória) para a legenda ao vivo. Custo médio,
risco médio, e exige um teste de ordem (não pode reordenar tokens).

## 5. (de método) Duas regras que o DeepInfer pratica e que o Sotto deve copiar

- **Cada optimização atrás de uma variável de ambiente, com default declarado e documentado.** É o mesmo
  padrão do `SOTTO_LOAD_AB` que ficou hoje no worker. Um travão sem nome é uma alteração invisível.
- **Dizer o que falta para ser "completo".** O README lista "Required for a complete inference service
  (not included)". O Sotto tem o equivalente em "POR MEDIR / NÃO ATRIBUÍDO" — e é a razão por que esse
  capítulo não pode desaparecer.

---

## O que NÃO se transfere

| do DeepInfer | porque não |
|---|---|
| Kernels (FlashMLA, DeepGEMM, DeepEP, TileLang) | SM100/CUDA 13; o Sotto corre ONNX Runtime + cuDNN num GPU de consumidor |
| MoE EP / EPLB / KV cache / disaggregation | são de serving de LLM com milhares de sequências; o Sotto tem **um** stream de áudio |
| Ascend NPU | não existe nesta máquina |
| Build Linux/GCC 13/Python 3.12 | o produto é Windows + Python 3.11 |
| *Structured outputs* (regex/JSON/EBNF) | o Sotto emite texto de ASR, não geração condicionada por gramática |

## Ordem recomendada (com ids do roadmap)

1. **Determinismo (conceito 3)** → portão novo `_main/transcript-determinism-oracle.py`: o mesmo WAV em
   dois `chunk_samples` tem de dar o mesmo texto. Barato, protege a promessa central, e é a única coisa
   aqui que se pode pagar **hoje**.
2. **Verificação por confiança (conceito 2)** → P1 do roadmap: o critério de agendamento do segundo pass.
3. **Replay limitado (conceito 1)** → P1: menos áudio re-decodificado, com `yoco_equiv`-style differential.

**Nota de honestidade:** nada disto é uma cura de performance. O perfil de hoje diz que 93 % do tempo do
worker é **load** (`encoder` 19,013 s de 22,8 s), e nenhum conceito do DeepInfer toca nisso — o DeepInfer
assume o modelo já carregado. O load continua a ser o P1.1–P1.5 do roadmap, com medição própria.
