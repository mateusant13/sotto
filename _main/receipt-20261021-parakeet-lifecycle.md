# Recibo — medição do segundo pass (Parakeet) e do lifecycle (2026-10-21)

**O DONO, verbatim (2026-10-21):**
> *"legenda ao vivo, com o modelo nemotron, mostra na minha tela quando eu quero, e no painel da
> direita tambem. mas qualquer legenda que ja passou (nao é mais ao vivo) tem que ser processada tambem
> pelo parakeet, ou imediatamente, ou com delay, ou quando seguro de fazer isso, tipo quando nao to com
> outras coisas pesadas abertas. tem que ter um lifecycle inteligente. o parakeet da segundo pass pra
> melhorar a precisao das legendas. porem, se minha legenda ao vivo ta desativada e eu nao to usando, é
> só o parakeet que comanda."*

Este recibo é a **MEDIÇÃO** que a implementação vai usar. Nada aqui é de memória.

---

## A. OS PESOS — **ESTÃO EM DISCO** (a contradição do `AGENTS.md` resolvida por bytes)

`H:\sotto\worker\models\` (o **product root**; os pesos são git-ignored e não existem em nenhum
worktree):

| directoria | bytes | ficheiros |
|---|---|---|
| `nemotron-3.5-asr-ptbr-onnx-int4` | 783 537 972 | 32 |
| `parakeet-redux-onnx-int4` | **436 071 657** | 22 |

**O PARAKEEP ESTÁ LÁ.** O export ONNX int4, completo:
`encoder-model.onnx` 343 841 943 B · `decoder_joint-model.onnx` 72 552 270 B ·
`preprocessor.onnx` 1 224 294 B · `vad-model.onnx` 18 300 687 B · `transcribe.py` 17 844 B ·
`vocab.txt` 93 939 B · `config.json` 375 B · `README.md` 5 849 B · `requirements.txt` 181 B.

**E O MODELO AO VIVO MUDOU DE NOME:** `worker/config.json` diz
`model.dir = "models/nemotron-3.5-asr-ptbr-onnx-int4"` — **não** é o
`nemotron-3.5-asr-streaming-0.6b-int8` que o `AGENTS.md` ainda citava. **O texto do
`AGENTS.md` estava desatualizado** e a medição é o que vale.

**O `parakeet-redux-ternary` e o `parakeet-redux-reference` NÃO estão** — só o ONNX int4. É
justamente o motor **leve** (615 MB de pico medidos contra 3,90 GB do ternário).

## B. OS RUNNERS

| runner | o que é | quem o chama |
|---|---|---|
| `worker/redux_batch.py` | o pass **em lote** sobre áudio acumulado | o **worker**, via `ReduxHiddenSwitch` |
| `worker/redux_live.py` | **"Sotto LIVE transcriber — Parakeet Redux (TDT) as the engine of the live box"** — o motor **ao vivo** do Parakeet, o mesmo contrato de fio | o **worker**, via `--redux-live` / `SOTTO_REDUX_LIVE` |

O `redux_live.py` fala o mesmo contrato de fio e é **586 MB contra 1 988 MB** (comentário do
shell, `:74-97`).

## C. A LIGAÇÃO HOJE (o que está ligado e o que não está)

| mecanismo | gatilho | ligado por omissão? |
|---|---|---|
| `SOTTO_REDUX_LIVE=1` → motor **Parakeet ao vivo** | o env var | **SIM** — `app/webview/run.cmd:94` põe `SOTTO_REDUX_LIVE=1` por omissão |
| `--redux-when-hidden` / `SOTTO_REDUX_WHEN_HIDDEN=1` → pass **em lote** com o runner `redux_batch` | **só quando o PAINEL ESTÁ ESCONDIDO** (`ReduxHiddenSwitch` + `PanelVisibilityReader`, `sotto_worker.py:6029-6040`) | **NÃO** — é opt-in |
| o shell a lançar `redux_live.py` | — | **NÃO** — o shell nunca o lança (só o worker) |

## D. OS BURACOS, UM A UM, CONTRA O PEDIDO DO DONO

1. **"qualquer legenda que já passou tem que ser processada também pelo parakeet"** — hoje o
   pass em lote só corre **quando o painel está escondido** e **só se o dono o pedir**. Com o
   painel aberto (o modo ao vivo), **não há segundo pass nenhum**.
2. **"ou imediatamente, ou com delay, ou quando seguro de fazer isso"** — hoje não há lifecycle:
   há **uma** política (painel escondido → lote). Não existe o "adiado", nem o
   "oportunista" (esperar que a máquina esteja livre), nem a escolha.
3. **"se a minha legenda ao vivo está desativada e eu não to usando, é só o parakeet que comanda"**
   — hoje, com o painel escondido, quem transcreve é o **Nemotron** (o worker continua a correr;
   o `ReduxHiddenSwitch` é um **segundo** motor por cima, não a troca). E o buraco medido de
   2026-10-21: quando uma legenda externa (YouTube) acaba, `on_external_captions_released()`
   **não traz o worker de volta** (de propósito — *"abrir ou fechar o sotto... trava pra caralho
   meu pc"*), pelo que **depois** de uma legenda do YouTube **não há nem legenda do YouTube nem
   transcrição do modelo**.
4. **O `REDUX_PRODUCER`** existe (`worker/sotto_worker.py:3595`, `"redux"`) e o `history-source.js`
   aceita uma linha canónica **só** com `producer === 'redux'` — mas o shell continua a dizer, em
   `:7284-7287`, que *"NO engine in this repo ever stamps `producer`"* e que o motor Parakeet
   *"is neither on disk nor called"*. **A primeira frase é verdadeira; a segunda já não é** (os
   pesos estão em disco) — o texto do shell está desatualizado e é a **fonte da verdade** que
   o painel usa para colapsar o feed (`canonicalProducer: None`).
5. **O custo** (medido pelo próprio repo, `_main/redux-cost-onnx.log`): o ONNX int4 mede
   **615,3 MB** de pico de RSS e **RTF 8,33** — o ternário, 3,90 GB. A escolha é pelo **preço em
   RAM**, como a LEI DA STACK diz.

## E. O PLANO (para a lane de implementação)

1. **O lifecycle, com três políticas e um interruptor**: `imediato` (cada linha fechada vai
   logo ao Parakeet), `adiado` (uma fila, processada em lote quando N linhas se juntam) e
   `oportunista` (a fila só é drenada quando a máquina está **livre** — o sinal tem de ser
   barato: **carga da CPU** e **memória da GPU** (`nvidia-smi`), amostrados pelo próprio processo,
   sem lançamento nenhum). O padrão tem de respeitar a **fome do dono** (o `emit_async` e o
   `WorkerReloadPolicy` já existem para isso).
2. **O motor único**: com a legenda ao vivo **desligada**, o Parakeet passa a ser **o** motor
   (a LEI DA STACK: *"o nvidia é pro ao vivo, o parakeet redux é pro geral"*), e não um motor
   por cima do outro.
3. **O `producer`**: o segundo pass tem de carimbar `producer = "redux"` na linha que reescreve,
   para o histórico canónico a aceitar. Hoje **ninguém o carimba**.
4. **O buraco do "nem o YouTube nem o modelo"**: fechar o ciclo do `on_external_captions_released`
   sem ressuscitar o treadmill de model loads (o `no_audio_backoff` e o `WorkerReloadPolicy` são
   exatamente para isso).
5. **O texto do shell** (`:7284-7287`) tem de ser **corrigido** — um doc que mente sobre o disco
   é um defeito, não uma nota.

## F. O QUE **NÃO** FOI MEDIDO

- **O custo desta corrida** (a Parakeet a transccrever de facto): nenhum modelo foi carregado
  nesta sessão — nem o Nemotron, nem o Parakeet — e nada foi renderizado.
- **A latência do segundo pass** com áudio real: `redux_live.py` não foi executado.
- **O que a máquina está a fazer quando o dono diz "não to com outras coisas pesadas abertas"**:
  a escolha do sinal (carga da CPU? GPU? janela da frente?) é uma decisão de **produto** — o
  dono, ou a medição do custo real — e fica declarada, não adivinhada.
