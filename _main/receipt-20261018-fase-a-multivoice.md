# Fase A — detector barato de "havia duas vozes ao mesmo tempo?"

**Data:** 2026-10-18 · **Autor:** Mavis · **Raiz:** `H:\sotto` (a raiz do produto)
**Estado do Sotto durante este trabalho:** FECHADO. Nada foi lançado.

---

## 1. O que o dono pediu, e o que isto responde

Verbatim (2026-10-18):

> *"se em tempo real for pesado pro usuario separar as vozes, devemos fazer isso
> depois apenas. mas preciamos detectar que sao multiplas vozes, pra decidir isso
> pra processar depois quando e seguro e nao travar o pc do usuario."*

Duas metades: **manter a detecção ligada**, **adiar a separação**. Esta é a
primeira metade, medida e em produto. A segunda metade precisa de uma política
que é do dono (§7).

---

## 2. O BLOQUEIO que esta fase abriu — e fechou

A sessão anterior tinha deixado a Fase A parada num erro que parecia do
onnxruntime: cinco formas de entrada e nenhuma aceita.

**A causa era uma suposição minha, não do modelo.** O probe calculava um fbank
Kaldi em Python e alimentava o modelo com ele. O modelo nunca quis um fbank.

Rastreio do grafo (`I:\cc-tmp\trace-x.py`, 50 nós, 153 `value_info`):

```
input  x: [N, 1, T]                     <- T em AMOSTRAS a 16 kHz
  /sincnet/wav_norm1d/InstanceNormalization
  /sincnet/conv1d.0/Conv                filtros [80, 1, 251], stride 10
  /sincnet/Abs                          -> [N, 80, floor(T/10-251/10)+1]
  /sincnet/pool1d.0/MaxPool  stride 3   -> [N, 80, .../3...]
  /sincnet/norm1d.0/InstanceNormalization
  /sincnet/LeakyRelu                    -> primeiro Conv profundo
output y: [N, frames, 7]                  7 classes powerset
```

**O filterbank É a primeira camada do modelo** (SincNet, 80 filtros aprendidos).
Não há fbank para calcular em Python.

**Consequência que vale mais do que o desbloqueio:** o blocker *"provar que o
meu fbank é igual ao fbank C++ do sherpa, que não é exposto"* **deixa de
existir**. O único consumidor do áudio passa a ser o próprio modelo, que é o
mesmo que o sherpa usa. Não há uma segunda implementação que possa divergir em
silêncio.

### O mapa frame → tempo

```
1 frame = 270 amostras = 16,875 ms
        = stride 10 do sinc conv × 3³ (três MaxPool de stride 3)
```

Derivação arquitectural, verificada contra **7 comprimentos medidos**
(32 000 a 960 000 amostras).

*Por que não transcrevi a expressão `floor` do grafo:* fiz, e ela erra **+1
frame em 4 de 7 comprimentos**, em float64, float32 e float64+epsilon — todas a
mesma (`I:\cc-tmp\frame-formula.py`). Um self-check que diz "DIVERGE" por 1
frame em 3 552 é ruído, e parece um defeito que não existe.

---

## 3. A regra que eu escrevi ERRADA, e a que a medição corrigiu

Primeira tentativa: *"a classe 6 é a de duas vozes"*. **F1 = 0,000.**

Motivo — as 7 classes powerset do pyannote são **1 + 3 + 3**, e eu só testava
uma das três:

| classe | significado | evidência que o fixa |
|---|---|---|
| `0` | ninguém | sozinho `{0}`; 56,9 s de não-fala → `{0:3552}` |
| `1 2 3` | **uma** voz, em três slots | `pt-br` sozinha `{0:143, 2:1079}`; `en-us` sozinha `{0:161, 2:534}` |
| `4 5 6` | **duas** vozes simultâneas | `call.wav` (2 vozes, 2,5 s de sobreposição) → `{…, 6:118}` e as **118 caem todas dentro** da sobreposição medida |

**A leitura decisiva é o clip de QUATRO vozes**
(`_main/diar-models/0-four-speakers-zh.wav`): 56,9 s, 16,5 s de fala,
distribuição `{0:1780, 1:2, 2:608, 3:976}` — **zero frames de 4/5/6**, porque
não há sobreposição. Se 4/5/6 fossem "muita gente a falar", teriam disparado
lá. Confirma que o slot não é "quantas pessoas no canal".

E no braço de 100 % de sobreposição **construído**, disparou a classe **4**, não
a 6: `{0: 67, 1: 20, 2: 2, 4: 606}`.

---

## 4. A verdade é construída, não inferida

Nos clips `call*.wav` a verdade vinha da pipeline completa — mesma família de
modelo que a Fase A substitui, e em `call180.wav` essa pipeline deu **6 vozes
para 2 pessoas**, ou seja, suspeito.

Aqui a verdade é **exacta por construção**: dois clips de voz única misturados
com deslocamentos conhecidos; a sobreposição é a contagem de cobertura ≥ 2.

### Erro meu, que o portão apanhou

Primeira versão do portão: `mask[a:b] = True` — isso é *"alguém está a
falar"*, não *"dois estão a falar"*. Resultado: o braço de **0 %** reportava
**23,49 s** de sobreposição, e o de mesma voz reportava 11,73 s. Todas as
métricas de precisão/recall estavam a medir a coisa errada. Corrigido para
cobertura por amostra.

---

## 5. Números — `_main/multivoice-oracle.py`, **13/13**, braço negativo **executado**

Pré-condições **medidas** antes de qualquer veredicto: `pt-br` sozinha → 1 voz;
`en-us` sozinha → 1 voz; as duas em **sequencial** → **2 vozes** (são mesmo
pessoas diferentes); a **mesma** voz em duas camadas → **1 voz**.

| braço | sobreposição verdadeira | disparou | P | R | F1 |
|---|---|---|---|---|---|
| A-seq — 0 % | 0,00 s | **0,00 s** | — | — | — |
| A-metade — 50 % | 5,91 s | 3,95 s | 1,000 | 0,669 | 0,801 |
| A-forte — 100 % | 11,73 s | 10,23 s | 1,000 | 0,872 | **0,932** |
| A-mesma — mesma voz ×2 | 11,73 s (1 pessoa) | **0,00 s** | — | — | — |

**A-mesma é o contra-teste que torna o detector honesto:** a mesma pessoa em duas
camadas **não** dispara. Logo o detector mede **pessoas**, não volume.

**Custo (soma dos braços, 64,1 s de áudio):**

| | RTF |
|---|---|
| só segmentação (Fase A) | **0,0097** |
| pipeline completa | 0,503 |
| | **52× mais barata** |

**Braço negativo** (`MULTI_CLASSES → (2,)`, a classe que domina o áudio de uma
voz): F1 **0,006** na sobreposição real, mas dispara **10,24 s** na mesma voz
duplicada. Rejeitado.

---

## 6. Em produto — `_main/speaker-watch-oracle.py`, **39/39**, negativo **FAIL 8/38**

| peça | onde | o que faz |
|---|---|---|
| `--watch-only`, `--watch-out`, `--watch-hold` | `worker/speaker_sidecar.py` | mesma captura, mesmo `RingBuffer`, mesma escrita atómica; só muda o modelo carregado e o que se escreve |
| `_load_powerset`, `powerset_windows`, `multivoice_spans`, `watch_tick` | mesmo | powerset sobre a onda crua; filtro de hold |
| `--speakers-cheap` | `app/webview/sotto_webview.py` | arranca o **mesmo** sidecar com `--watch-only`; `--speakers` mantém argv byte-idêntico |
| `watch_payload_if_fresh`, `multivoice` | `worker/speaker_bridge.py` | leitor da Fase A |
| `MultiVoiceWatch` | `app/webview/sotto_webview.py` | o consumidor |

Resultados no caminho de produto (mesmos controlos, `RingBuffer` real):

| braço | disparou | onde |
|---|---|---|
| 100 % sobreposição | 8,67 s em 3 spans | **todos dentro** da sobreposição verdadeira |
| 50 % | 3,80 s em 1 span | dentro |
| 0 % / mesma voz ×2 | **0,00 s** | — |

**Janelas SEM sobreposição entre si** (10 s de janela, passo 10 s). É
exactamente o eixo da decisão do dono: a Fase B precisa de passo 10 s para dar
2 slots (passo 20 s dá **4** para as mesmas 2 pessoas); a Fase A **não precisa
de sobreposição nenhuma**, porque não mantém identidade.

### A garantia estrutural

O payload de watch **não tem `segments`**. `speaker_bridge.payload_if_fresh`
exige `segments` e devolve `None` sem ela — logo **não existe estado em que o
caminho das legendas veja um payload de watch**: "não medido" nunca aparece no
painel como "medido: zero vozes". Verificado nos dois sentidos pelo portão
(o leitor de fala recusa o payload de watch; o leitor de watch recusa um payload
de fala), e `multivoice(None)` devolve `measured=False`, distinguível de
`measured=True, multivoice=False`.

### Memória — mesma máquina, mesma corrida, 2 núcleos

`_main/_watch-rss-probe.py`:

| processo | RSS em regime |
|---|---|
| só segmentação (Fase A) | **90,3 MB** |
| pipeline completa | **135,4 MB** |

Os 207 MB medidos antes são o **sidecar real** (captura, argparse,
`sounddevice`); os 135,4 MB são um filho mínimo com os mesmos dois modelos.
Nenhum dos três é este processo, e por isso nenhum está citado no `--speakers`.

---

## 7. A auditoria — o que a ligação toda mostrava

### 7.0 Um degrau que explica "pesado para o utilizador"

O RTF da pipeline completa medido aqui (`_main/_phase-b-cliff-probe.py`, mesmo
processo, mesmo áudio, 2 núcleos):

| janela | só segmentação (Fase A) | pipeline completa (Fase B) |
|---|---|---|
| 4 s | RTF 0,0256 | RTF 0,1007 |
| 8 s | RTF 0,0176 | RTF 0,0265 |
| **10 s** | RTF 0,0147 | **RTF 0,0423** |
| **11 s** | RTF 0,0212 | **RTF 0,6683** ← degrau, ×16 |
| 14 s | RTF 0,0150 | RTF 1,6930 |
| 20 s | RTF 0,0154 | RTF 1,5196 |

**A segmentação não tem degrau** — é plana em todo o intervalo. O degrau é da
metade de **embeddings + clustering**, e é brutal: a partir de 11 s a pipeline
fica **acima de tempo real** (RTF > 1) e fica lá.

**E não é só lentidão: é resposta errada.** Mesmos 23,5 s de duas pessoas em
sequência, mesmo modelo, mesmo threshold:

| como foi passado ao diarizador | parede | vozes encontradas |
|---|---|---|
| clip único de 23,5 s | **71,08 s** (RTF 3,019) | **1** — errado |
| três janelas de 10 s | **0,20 s** (RTF 0,009) | **2** — certo |

**355× mais rápido, e a resposta passa de errada para certa.** Por isso
`SAFE_WINDOW_S` não é uma preferência de performance — é um **limite de
correcção**, e por isso vive no código com um AVISO em vez de num comentário.

Duas consequências:

1. **A janela de omissão do sidecar são 10 s — do lado bom por UM segundo.**
   `--window-s` é um flag que mexemos, e subir a janela "para dar mais contexto",
   que é o movimento natural, põe o diarizador mais lento do que a call inteira.
   Guardado como `SAFE_WINDOW_S`, com AVISO no arranque (aviso, não recusa:
   quem escolheu uma janela maior pode ter razões que eu não vejo).
2. **Os clips guardados caem sozinhos do lado bom.** São `span + 2 s` de
   contexto, ou seja 2–7 s, muito abaixo do degrau. A Fase B sobre eles mediu
   RTF 0,012–0,09.

A hipótese que eu tinha primeiro — "aquilo era custo de arranque, não de
regime" — está **refutada**: a 1.ª e a 5.ª passagem de um clip de 5 s dão
0,031 s e 0,032 s. O que muda é o comprimento, não o aquecimento.

### 7.0.1 DER — a precisão da cadeia, que nunca tinha sido medida

Até aqui havia um número de precisão, o cMAP (90,4 %), e o cMAP mede uma coisa
específica: **dada** a rotulagem do diarizador, conseguimos permutar os rótulos
a quem pertencem. Não mede se o diarizador **descobriu** as vozes certas nem se
**segmentou** o tempo certo.

Corrido em janelas de 10 s com `StableSpeakerSlots` — isto é, no caminho de
produto — DER no braço sem sobreposição:

| limiar de referência | DER | missed | **confusão** | falso alarme |
|---|---|---|---|---|
| 0,02 | 18,4 % | 147 | **9 frames (0,95 %)** | 46 |
| 0,05 | 25,3 % | 134 | 9 (1,02 %) | 114 |
| 0,10 | 37,9 % | 122 | 8 (1,02 %) | 213 |
| 0,20 | 60,3 % | 103 | 8 (1,23 %) | 344 |
| 0,35 | 90,7 % | 77 | 5 (0,95 %) | 467 |

**A confusão — fala atribuída à pessoa errada, que é o produto — fica em
0,95–1,23 % da fala, em todo o varrimento.** E 2 slots globais para 2 pessoas.

A primeira versão do portão exigia "DER < 45 %" e foi a RED com 90,7 %. Esse
veredicto media **a minha actividade de referência**, não o diarizador: subir o
limiar encurta a referência (18,5 s → 10,2 s) e tudo o que o diarizador ouviu
passa a falso alarme **por construção**. O portão passou a julgar a confusão, e
a reportar a faixa de DER como informação com o porquê escrito.

Arma negativa: rótulos da hipótese baralhados no tempo → DER máximo **98,3 %**.
O portão sabe dizer NÃO.

### 7.1 O buraco: um sinal sem consumidor

```
VoiceMeeter (loopback 48k) ─┬─► sotto_worker.py ─► RNNT ─► captions JSONL
                             │        ▲ --speakers      │
                             │        │                 ▼
                             └─► speaker_sidecar.py ──► diar-live.json
      RingBuffer/tick        │                               │
             │               │ speaker_bridge.py             │
             │               │ └► source=voice:speaker-N     │
             │               ▼                               ▼
 diar-watch.json ◄── FASE A  (sem `segments`)   panel.js → ponto colorido
             │
             └──► NINGUÉM LÊ          ← buraco
```

`--speakers-cheap` escrevia um ficheiro que ninguém lia. Detetar sem consumidor
não decide nada. **Corrigido** com `MultiVoiceWatch`, que **regista** e
**não decide**.

O que o watcher deliberadamente **não** faz: não escreve no painel, não acrescenta
um número à legenda (o dono tirou um número visível duas vezes, e
`panel-voice-dot-oracle.js` é o portão que garante que o painel não ganha
texto), e **não lança a separação de vozes** — *quando* isso é seguro para o PC
dele é política do dono.

### 7.2 Hipótese refutada por medição: o pipe do sidecar

`SpeakerSidecar` abre o filho com `stdout=subprocess.PIPE` e **não tem leitor** —
ao contrário do `WorkerBridge`, que tem a thread `_pump`. Hipótese: o pipe
enche e o sidecar trava a meio de uma call.

**Medido, e a hipótese está errada.** Uma call de 8 h produz **309,4 KB** e o
filho escreve tudo sem bloqueio (`I:\cc-tmp\pipe-real-volume.py`); uma primeira
medição engoliu **12,3 MB** sem travar. **Não se toca neste caminho.**

O primeiro instrumento deste teste morreu — `p.wait()` sem ler o pipe trava, e
o timeout é o que o distingue de uma travagem real.

### 7.3 Defeito que eu escrevi, e que o portão apanhou

`MultiVoiceWatch.poll_once` registava em **qualquer** mudança, portanto uma
janela quieta depois de uma barulhenta saía como
`WATCH_MULTIVOICE spans=0 seconds=0.00` — alarme falso. Um log que grita lobo
em silêncio é pior que nenhum log, porque quem lê deixa de acreditar.

Corrigido: só regista quando houve spans; a primeira leitura quieta diz
`WATCH_ALIVE`, que separa *"a correr e quieto"* de *"nunca correu"*.

### 7.4 O segundo buraco: o áudio assinalado não sobrevivia

MEDIDO (`_main/_phase-a-retention-probe.py`): o `RingBuffer` é em memória e
**desliza**. Depois de 30 s empurrados num buffer de 10 s sobram 10 s, e os
primeiros 20 s foram libertados. A janela do meio é libertada **10 s** depois
de ter sido vista.

Ou seja: a **detecção** sobrevive (o payload leva tempos absolutos), mas o
**áudio não**. E *"processar depois"* significa precisamente mais tarde do que
isso. **Não era lento: era impossível.**

Corrigido com `--watch-save DIR`: quando a Fase A assinala, escreve um WAV por
span — 16 kHz mono 16 bit, nomeado com o instante absoluto, com 2 s de contexto
de cada lado, escrito por `tmp` + `os.replace` para nunca haver um WAV meio
escrito com o nome final, e com limite FIFO (`--watch-save-max-mb`, omissão
256 MB). **Desligado por omissão**: escrever o áudio do dono num disco sem ele
pedir não se decide aqui.

Porquê clips e não a janela inteira: um troço de 2–7 s ocupa ~100 KB contra os
320 KB da janela, e aponta para o momento que interessou. Guardar a janela toda
seria guardar 80 % de áudio em que havia uma pessoa só.

### 7.5 A Fase B: o que consome o que a Fase A guardou

`_main/multivoice-offline.py` — corre a pipeline completa sobre os clips já
gravados, fora do tempo real, e devolve os segmentos **no relógio da chamada**
(o instante está no nome do ficheiro, não a partir de 0).

- **Não abre dispositivo de áudio nenhum.** Um "processar depois" que vá buscar
  microfone não é depois, é agora com outro nome.
- **Não decide quando corre.** A política é do dono.
- **Não escreve em `_main/diar-live.json`** — esse é o ficheiro de quem está a
  correr em direto; sobrescrevê-lo a partir de um clip de ontem trocaria a
  resposta de agora pela de antes.

Portão do ciclo, `_main/phase-a-b-cycle-oracle.py`: **PASS 13/13**, e o braço
negativo (não guardar o áudio) é **rejeitado** — a Fase B fica sem clips e
recusa com rc=3. A mutação é a fiel: é o estado anterior da feature, em que a
detecção funcionava na mesma e por isso era mais leve. Um portão que olhasse
só para o detector passaria; o que falha é o resto do ciclo.

Um segundo bug meu caiu ainda no meio disto: uma linha de zero-padding inútil
esticava cada clip de volta aos 10 s, anulando a poupança que a feature existe
para fazer. O portão apanhou-o pela duração.

---

## 7.6 O DEFEITO QUE SÓ APARECE AO COMPRIMENTO DE UMA CALL

MEDIDO nas gravações REAIS do dono. `call.wav` (60 s) dá 2 slots. `call180.wav`
(180 s) dá **12 slots para 2 pessoas** — o painel faria 12 pontos coloridos para
duas pessoas.

### A caracterização primeiro, porque muda o que se pode concluir

| | call.wav | call180.wav |
|---|---|---|
| não-fala | 29,1 % | **89,0 %** |
| fala | 47,3 s (79 %) | 21,2 s (12 %) |
| mediana dos segmentos | 2,36 s | **1,52 s** |
| vozes do próprio diarizador | 2 | **6** |

A fragmentação **nasce a montante**: o diarizador dá 6 vozes nesse áudio. O
`StableSpeakerSlots` casa por tempo falado partilhado, e com 1,5 s de fala por
janela não há praticamente o que casar. Não é que o casamento esteja partido.

### Três hipóteses, todas medidas, todas refutadas — menos a quarta

| hipótese | resultado |
|---|---|
| é a falta de sobreposição | **refutada**: mais sobreposição deu *mais* slots (10/5 → 22, 10/3 → 33, 10/2 → 49) |
| `--num-speakers 2` resolve | **refutada**: 12 slots → 12 slots, e 3,7× mais lento |
| `--min-on 2,0 s` resolve | **refutada**: 12 → 4 slots mas **deita fora 58 % da fala** (21,1 s → 8,9 s) |

A quarta é a que resulta, e é a mesma doutrina do resto do projecto: **legenda
sem voz melhor que legenda com a voz errada**.

### A porta de densidade

```python
MIN_SPEECH_FRACTION = 0.30      # 0 desliga
```

Medida nas duas gravações, janela de 10 s:

| | fala por janela (modelo) | fala por janela (envolvente) |
|---|---|---|
| densa — 2 slots | 5,1 a 9,8 s | 3,3 a 7,9 s |
| esparsa — 12 slots | 0,3 a 3,2 s | **0,0 a 2,3 s** |

**Separação limpa**, e a envolvente passa em todos os limiares testados
(0,05 / 0,10 / 0,20 / 0,30). Duas propriedades deliberadas:

- **De energia, não de modelo.** Zero RAM — é o que a torna utilizável na Fase
  A — e independente: o RMS do áudio não sabe nada sobre vozes, ao passo que usar
  a classe 0 do próprio modelo de segmentação seria vigiar o modelo com ele
  próprio.
- **Limiar relativo ao pico da janela**, nunca absoluto: as duas gravações
  medem −18,5 dBFS e −32,5 dBFS. Um limiar em dBFS mediria o ganho.

Quando a janela fica abaixo da porta, publica-se `segments: []` — e não nada.
Publicar nada deixaria no painel a atribuição *antiga*, que é pior. Uma lista
vazia é o que `speaker_bridge.voices()` já lê como "sem vozes".

**Medido depois de ligada, COM A CADÊNCIA DECLARADA** — este número sem a
cadência não se consegue ler, e foi quase um erro meu (ver §7.6):

| cadência | densa (`call.wav`) | esparsa (`call180.wav`) |
|---|---|---|
| **20 s / 10 s** (o default), **com** a porta | 4 atribuídas, **2 slots**, 61,4 s com voz | **16 recusadas, 0 slots** |
| 20 s / 10 s, **sem** a porta | 4 atribuídas, 2 slots, 61,4 s | 16 atribuídas, **6 slots**, 34,9 s |
| 10 s / 10 s, **sem** a porta | 6 atribuídas, **8 slots**, 45,0 s | 18 atribuídas, **12 slots**, 21,1 s |
| 10 s / 10 s, **com** a porta | 6 atribuídas, **8 slots** ⚠ | **18 recusadas, 0 slots** |

⚠ **A porta não arruma a densa a 10 s** — e esta linha é a mais útil do
conjunto. A fala densa passa a porta em todas as janelas (é fala a sério), logo
os 8 slots são um problema de **cadência**, não de densidade. O portão **reprova
essa configuração** — `VERDICT: FAIL (2/13)`, rc=1 — e está certo: quem protege o
painel de 8 pontos para 2 pessoas aqui é o **default de 20 s**, não a porta.

Portanto, com a precisão que o número exige: **a porta é o guard de áudio
esparso, e a cadência é o que carrega o áudio denso.** São guardiões diferentes
para Audio diferente. Eu escrevia isto como se a porta sozinha resolvesse a
identidade, e não resolve.

**Os "12 slots" da caracterização são a 10 s de janela, não a 20 s** (a 20 s são
6). Não é uma medição que mudou — são duas cadências, e a de 10 s reproduz hoje
o número exacto da sessão anterior (12 slots, 18 janelas, 21,1 s), duas vezes.

Reforça, e não enfraquece, a decisão de cadência: **a 10 s a gravação densa já
dá 8 slots para 2 pessoas, com ou sem porta.**

### O que a recusa faz às legendas — o braço que faltava

A porta publica `segments: []`. O risco óbvio é a porta estragar a atribuição. O
risco **real** é outro, e só aparece quando se pergunta o que acontece à legenda
que já estava no painel quando a janela foi recusada.

**Perder o `source` é uma mentira pior do que perder o nome.** Sem `source` não
se sabe sequer de que microfone veio a linha. Medi as duas coisas, com o payload
recusado a passar por `speaker_bridge.apply_to_lines` de verdade:

| o que se passa | medido |
|---|---|
| a recusa **mantém** o `source` do dispositivo | `['device:mic', 'device:mic']` |
| e não inventa uma voz | `[None, None]` |
| a barra de estado diz **zero vozes**, não um erro | `{'n_speakers': 0, ...}` |
| o caminho normal continua a marcar a voz | `['device:mic/voice:speaker-1', ...]` |

A quarta linha é a que impede que isto seja um teste que passa por desligar a
feature que atravessa: o mesmo payload **com** uma voz tem de continuar a marcar.
Sem ela, um portão que só testasse a recusa passaria com `apply_to_lines` a
devolver `source: None` para tudo.

Este braço é **independente da porta** (ele julga o contrato da bridge, não o
limiar), por isso corre nos dois braços — e por isso o `--neg-arm` continua a
dar 8/8 em vez de 4/4.

---

## 7.7 DOIS DEFECTOS NUM INSTRUMENTO QUE NUNCA TINHA SIDO EXECUTADO

`_main/_cpu-load.py` foi escrito para responder a uma pergunta que já estava no
recibo acima ("a que carga foi medido este RTF?") e **não foi corrido**. Quando o
corri, deu duas coisas erradas. As duas estavam no mesmo sítio — a decisão de ler
a carga — e as duas produziam um número que *se lia* como medição.

### Defeito 1 — o ramo de NaN estava invertido

```python
if load == load:   # isto era o codigo
```

`x == x` é verdadeiro para **qualquer número real**; é o único valor falso para
NaN. O código estava escrito ao contrário, e a consequência é dupla: a frase
"carga DESCONHECIDA" saía **quando a carga estava bem medida**, e **nunca** saía
quando a leitura falhava. O ramo estava morto e o seu oposto, vivo.

### Defeito 2 — o padrão de duas chamadas mede o intervalo vazio

```python
psutil.cpu_percent(interval=0.6)     # espera e devolve -- e REINICIA a referencia
return float(psutil.cpu_percent(interval=0.0))   # mede os microssegundos entre as duas
```

O psutil devolve o valor **na chamada bloqueante** e actualiza a referência
interna. A segunda chamada mede o intervalo **entre** as duas — de
microssegundos. Resultado: o instrumento anunciava

```
carga 0%, 20 de 20 nucleos livres
```

**no mesmo instante em que media 3 a 8 núcleos ocupados.** Eu vi este `0.0`
sair do diagnóstico às 22:5x e **passei por ele** — era o próprio bug, escrito
na minha cara, no output. Um número que se lê como caminho quando não é caminho
é pior do que não imprimir, e foi exactamente o que imprimi.

### O que o instrumento diz agora

```
amostra 1: carga global 83% (alta), mas 11 de 20 nucleos livres
amostra 2: carga global 80% (alta), mas 12 de 20 nucleos livres
amostra 3: carga global 81% (alta), mas 10 de 20 nucleos livres
```

**A ressalva dos RTF deste recibo está confirmada por um instrumento, não por
uma impressão.** A máquina está de facto a ~80 % com ~10 núcleos livres — a
invalidação dos números absolutos era real, e a validade das comparações de lado
a lado também.

O veredicto é deliberadamente sobre **núcleos**, não sobre a percentagem global:
91 % em 20 núcleos ainda tem folga; 91 % em 2 não tem.

### O portão: `--self-test`, 9/9, e quatro mutantes vermelhos

Um instrumento que mede a máquina não tem teste — o resultado depende do que a
máquina estiver a fazer. Por isso `load_ok` aceita carga e núcleos **injetados**,
e `--self-test` conduz os estados que o veredicto tem de distinguir. Dois checks
são contra a máquina real, e existem precisamente para apanhar o defeito 2:

- `a carga global NAO e' ~0% havendo N nucleo(s) a >=80%`
- `a carga global nao e' MENOR que a fraccao dos nucleos ocupados`

| mutante | apanhado por | rc |
|---|---|---|
| controlo | PASS 9/9 | 0 |
| `load != load` → `load == load` (defeito 1) | 6 checks | 1 |
| `if load >= CARGA_ALTA_PCT:` → `if False:` | 2 checks | 1 |
| `if total and busy >= total:` → `if False:` | 1 check | 1 |
| **padrão de duas chamadas (defeito 2)** | **1 check — o da consistência** | 1 |

O mutante 4 é a prova de que o portão serve: o defeito que eu cometi é apanhado
por um check escrito exactamente para ele.

Um check deste conjunto chegou a passar **pela razão errada** — `2 de 20` aparece
também no ramo de carga desconhecida, e mutante 1 passava-o por coincidência.
Endureci-o antes de dar o portão por bom: um braço que falha pela razão errada é
pior do que não haver braço.

---

## 7.8 A GUARDA DE CARGA — o instrumento finalmente tem consumidor

O §7.7 deixou `_main/_cpu-load.py` a funcionar. Um instrumento a funcionar e sem
ninguém a chamá-lo é um sinal sem consumidor — **o mesmo buraco que a Fase A
teve com o áudio (§7.4)**, e que não se repete.

O dono: *"processar depois quando é seguro e não travar o pc do usuário."* A
segunda metade da frase é uma condição, e `_main/multivoice-offline.py`
carregava os **135 MB** dos dois modelos sem perguntar se havia folga.

```
rc=3  nenhum clip encontrado
rc=4  a máquina não tem núcleo livre: NÃO CORREU
```

O que a guarda **não** faz: não decide a política dele. Não diz *quando correr* —
diz *agora não*, e só quando não há um núcleo sequer livre. `--ignore-load` existe
para quem sabe o que está a fazer.

### O check difícil: a recusa tem de ser ANTES dos 135 MB

Recusar depois de pagar a carga é pagar para descobrir que não se pode. Mede-se
com um `spy` no carregador, e — este é o ponto — com **um par**:

| | |
|---|---|
| sem folga | `rc=4` e o carregador **não** foi chamado (0 chamadas) |
| `--ignore-load` | o carregador **é** chamado (1 chamada) |

Sem o segundo, o primeiro passa igualmente se o carregador *nunca* pudesse ser
chamado — por um `return` a mais, por um `if` mal posto, por um typo. **Um braço
que passa por não fazer nada é o pior dos dois: parece verde e não mede nada.**

### Um defeito REAL que este portão encontrou

`collect()` aceitava um `.wav` que **não existe**. A Fase B só descobria isso
*depois* de carregar os 135 MB, e rebentava com um traceback cru em vez de dizer
que o ficheiro não estava lá. **Descobrir um caminho errado é de graça; descobrir
depois de carregar 135 MB não é.** Corrigido em `collect()` (ignora e diz) e no
ciclo (um clip ilegível é um clip que se salta, com a razão dita).

### Um portão que ficava INSTÁVEL, e como ficou estável

`phase-a-b-cycle-oracle.py` corre a Fase B por subprocesso. Com a guarda nova,
passava a falhar conforme o que o dono tivesse a fazer — a pior propriedade que
um portão pode ter. Leva agora `--ignore-load`, com o motivo escrito: **a guarda
tem o portão dela** (`offline-load-guard-oracle.py`, **16/16**; neg **9/9**). Um
gate mede uma coisa; dois gates a medir a mesma coisa, um deles fica instável.

### O check que nenhum outro fazia: a LIGAÇÃO

Os checks anteriores todos **encenam** `load_cpu_module`. Se esse caminho levar ao
ficheiro errado, a guarda continua a passar e a Fase B fica a ler que "não há
núcleo livre" para sempre — ou pior, a aceitar sempre. Quatro checks passam pelo
`_cpu-load.py` a sério (tem um hífen no nome, só se carrega por caminho), e
custam **1,2 s de amostragem: nenhum byte de modelo**.

---

## 7.9 O ENSAIO DE ACEITAÇÃO NA CALL REAL — PASS 8/8

`phase-a-b-cycle-oracle` corre a cadeia toda, mas sobre áudio **sintético**. O
ensaio que faltava era o contrário: `_realcall-acceptance.py`, corrido sobre os
**180 s da `call180.wav` do próprio dono**, do princípio ao fim.

| | medido |
|---|---|
| Fase A sobre a call | 18 janelas em 2,2–3,5 s, **RTF 0,012–0,020** |
| janelas com duas vozes | **1 de 18** (1,2 s assinalados) |
| disco | **0,2 MB** para 180 s de áudio |
| clip mais longo | **5,20 s** — bem abaixo do degrau de 10 s, **0 acima** |
| Fase B sobre os clips | **2 vozes** nesse clip, **RTF 0,008**, 1,1 s no total |
| verificação | **PASS 8/8** |

Três coisas que só aparecem aqui e que nenhum outro portão diz:

1. **O clip mais longo dos 180 s foi 5,20 s.** O `--watch-pad-s 2,0` somado ao
   span nunca chegou a 10 s, que é exactamente o degrau medido. A retenção está
   dimensionada para o pior caso que a call produziu, não para o pior caso
   imaginável.
2. **A Fase B acha as duas vozes no clip que a Fase A assinalou** — a cadeia
   fecha no áudio real, não só no sintético.
3. **Uma janela assinalada em 18 não é pouco.** A `call180.wav` é 89 % silêncio;
   6 % das janelas com sobreposição é o que esse áudio contém, não uma falha da
   detector. O número baixo é o número certo.

O que isto **não** diz, e está escrito no próprio relatório: se a atribuição
estava *correcta*. Não há truth humana sobre quando havia duas pessoas a falar
nessa call, e não se inventa. O que fica medido é se o **mecanismo** aguenta o
comprimento — memória, disco, tempo e o limite de 10 s respeitado até ao fim.

---

## 7.10 O que NÃO mudei, e porquê

**O default de cadência continua 20 s de janela / 10 s de passo.** A tensão é
real e não a escondo: o degrau manda janela ≤ 10 s, e a identidade quer
sobreposição.

**E hoje ficou medido que a cadência é o que segura a identidade, não a porta.**
Em `call.wav`, que é áudio real com pausas, 20/10 dá os **2 slots correctos**;
10/10 dá **8 slots**, e dá-os **com a porta ligada** — a fala densa passa a porta
em todas as janelas. O portão reprova essa configuração (`FAIL 2/13`), o que é a
coisa certa a fazer: quem protege o painel de 8 pontos para 2 pessoas é o default
de 20 s.

Isto reformula o que eu tinha escrito acima, e vale a pena ser exacto: **a porta
de densidade protege o áudio esparso; a cadência protege o áudio denso.** Uma
não substitui a outra, e a medição mostra onde cada uma falha.

Trocar o default por 10/5 daria 3–4 slots, ou seja, **visivelmente errado**, para
ganhar uma margem contra um degrau medido em áudio *contínuo* (que não é o que uma
call com pausas entrega ao sidecar). Entre "2 slots correctos" e "3 slots
errados", os 2. Fica o AVISO com os números, e a decisão fica escrita.

## 7.11 O SEGUNDO BURACO DA RETENÇÃO — o áudio do dono desaparecia em silêncio

O primeiro buraco (§7.4) foi a detecção viver e o áudio não. Este é **da mesma
família** e só aparece quando a call é longa o bastante para encher a fila —
ou seja, exactamente quando `--watch-save` está a ser útil.

`--watch-save-max-mb 256` é FIFO: quando o limite chega, o clip **mais antigo** é
apagado. O que estava mal não era o FIFO, era a **conta**:

```python
_evict_oldest(out_dir, max_mb)     # devolvia o nº de ficheiros removidos
return written                     # ...e o valor era DEITADO FORA
```

`watch_tick` publicava `n_clips` = quantos foram **escritos**, nunca quantos
foram **perdidos**.

### O que medi antes de mexer

Corri o portão contra o código de hoje, antes da correcção:

```
[XX] `save_multivoice_clips` DEVOLVE quantos clips apagou -- devolveu function
[XX] os clips contados como guardados sao os que EXISTEM -- contados 1, no disco 0
[XX] `watch_tick` PUBLICA quantos clips a fila perdeu
[XX] e `n_clips` e' o que SOBREVIVEU, nao o que foi escrito -- n_clips=2, no disco 0
[XX] e o payload gravado tambem o diz
```

**`n_clips=2` com zero clips no disco.** Duas consequências:

1. O áudio assinalado do dono desaparece sem log, sem campo no payload, sem nada.
2. **Pior:** a evicção corre *depois* da escrita, na mesma chamada. Com a tampa
   apertada, o clip acabado de escrever era o primeiro a sair — e contava-se como
   guardado. Era a segunda metade do defeito, e é o que produzia `n_clips` sem disco.

### A correcção

- `_evict_oldest` devolve **os nomes** do que removeu, na ordem.
- `save_multivoice_clips` devolve `(sobreviventes, apagados)`, e os
  sobreviventes já excluem um clip que a fila levou **na mesma chamada**.
- `watch_tick` guarda **antes** de publicar, para o payload poder dizer a perda:
  `clips_saved`, `clips_evicted`, `n_clips` (o que ficou) e `n_clips_evicted`.
- A linha de stdout passa a dizer `EVICTED=n (fila cheia...)` com os nomes.

Um payload que diz "assinalei 2 vozes" sem dizer que o áudio já não está lá é um
payload que promete uma coisa que não pode cumprir.

### O portão: `watch-retention-fifo-oracle`, **15/15**, neg **2/2**

Cobre a tampa, a ordem FIFO (o mais novo sobrevive, se alguém sobrevive), a conta
fechar (`sobreviveram + apagados = escritos`), o clip que se apaga a si mesmo, e o
estado e o payload que a shell lê.

**Dois defeitos meus neste portão, ambos corrigidos antes de o dar por bom:**

- A prova da ordem passava sobre `[] == sorted([])` — uma lista vazia, com a tampa
  errada. Um check que passa sobre nada não é um check. Agora a tampa é
  calculada a partir do tamanho real de um clip (60 frames = **31,6 KB**) e
  obrigada a deixar sobreviver mais de um.
- O fixture usava 4 s de áudio para cinco spans que precisam de 12,2 s: **três
  clips nunca eram escritos** e a conta fechava a dizer 5 quando só havia 2.

E um terceiro, no braço negativo: **o veredicto estava invertido.** Os checks
dessa braço escrevem o que o mutante faz, portanto passarem *é* a prova de que ele
se queimou — e eu li a lista de falhas vazia como "escapou". `rc=1` com o mutante
claramente detectado.

O negativo põe `_evict_oldest` a devolver vazio: **0,186 MB com tampa de 0,100 MB,
6 de 6 clips.** A tampa deixou de existir e o portão viu.

A âncora do mutante também falhou **de propósito** quando mudei a assinatura de
`-> int` para `-> list`: o braço negativo disse "a âncora mudou, actualiza este
portão" em vez de aplicar a mutação em silêncio sobre um ficheiro já diferente.
Medir o código antigo depois de o código ter mudado dá um verde que não quer dizer
nada.

### O dono fica a saber? O watcher é a superfície, e ele ignorava o campo

Pôr `clips_evicted` no payload **não chega**: quem lê o payload é
`MultiVoiceWatch`, e a linha que ele escrevia era

```
WATCH_MULTIVOICE spans=3 seconds=8.67
```

O número estava no ficheiro e em lado nenhum que o dono visse. Passa a ser

```
WATCH_MULTIVOICE spans=3 seconds=8.67 AUDIO_PERDIDO=4 (a fila encheu: 4
apagado(s), 1 guardado(s) nesta janela)
```

Uma função nova, `_evicted_note()`, que devolve **a string vazia** quando não
houve evicção — uma janela sem perda é o caso normal e não merece uma linha mais
longa do que já é. Um aviso a mais é um aviso a menos lido.

A shell é **CRLF puro** (12 709 → 12 731 CRLF, **0 LF**), e a edição foi feita por
um script que conta as quebras antes e depois e **aborta** se já houvesse algum LF
sem CR. Uma linha inserida com LF parte essa propriedade em silêncio.

Três arms novas em `speaker-watch-oracle`, contra a classe real importada da
shell: o watcher diz a perda, a mesma linha continua a dizer as vozes, e sem
evicção a linha fica igual ao que era. **37/37**, e o negativo foi de 5/33 para
**8/36** — as três arms apanham a mutação, o que prova que não são decorativas.

E parti **duas arms alheias** ao fazê-lo: escrevi payloads com spans em
`watch_path` e o teste seguinte (`WATCH_ALIVE`, primeira leitura quieta) passou a
ver sobreposição em vez de silêncio. Repus o ficheiro no estado quieto, com o
motivo escrito ao lado. Um gate que se parte quando se lhe acrescenta uma coisa
não é um gate que se leu a sério.

---

## 7.12 O ÚLTIMO ELO: quem corre a separação fica a saber que falta áudio

O sidecar contava o que apaga, o watcher dizia-o ao dono — e **quem chegava
depois da call para correr a Fase B recebia um resultado sem qualquer aviso**.
Separar 3 clips e dizer "pronto" quando foram 7 é a forma mais cara de estar
errado: o dono acredita que leu a call toda.

### E um nome meu que mentia

MEDIDO antes de corrigir: em quatro janelas que perderam 1, 1 e 1 clip, o payload
final dizia `clips_evicted: 1`. O campo lia-se como "perdidos até agora" e era
**"perdidos nesta janela"** — e o payload é reescrito a cada tick, por isso o
histórico da perda vivia só no log, num ficheiro que ninguém pode juntar ao
resultado depois.

Agora são dois campos com nomes honestos: `clips_evicted` (desta janela) e
`clips_evicted_total` (acumulado, que o sidecar carrega entre janelas).

### A distinção que faltava, e que é a mais importante

`loss_report()` tem **três** respostas, não duas:

| estado | devolve | o que o dono lê |
|---|---|---|
| sem payload / sem a chave | `None` | "não há payload para comparar" |
| `clips_evicted_total: 7` | `lost=7` | "INCOMPLETO — perdeu 7" |
| `clips_evicted_total: 0` | `lost=0` | "a fila não perdeu áudio" |
| **`clips_evicted_total: 'x'`** | **`lost=None`** | **"NÃO SEI — e não vou dizer que nada se perdeu"** |

A quarta linha é uma correcção minha dentro da correcção: com `int(payload.get(...) or 0)`,
um campo de lixo devolvia **`lost: 0`** — lixo no campo dito ao dono como "a fila
não perdeu áudio". É a mentira na direcção perigosa, e só aparece se se testar o
caso de lixo.

### Medido numa corrida real

```
TOTAL: 8.0 s de audio em 0.1 s de parede (RTF 0.007)
COMPLETUDE: INCOMPLETO -- a fila FIFO perdeu 5 clip(s) de audio que o
            sidecar JA TINHA ASSINALADO.
            Separar o que resta e' correcto; o que falta Nao reaparece.
            Para nao perder: --watch-save-max-mb maior, ou correr a Fase B
            mais assiduamente.
```

E no payload de saída: `incomplete: true`, `clips_lost: 5`, `watch_payload`. O
**rc continua 0** — o trabalho pedido foi feito; a incompletude do *conjunto de
entrada* é outra coisa, e um `rc != 0` diria "isto falhou", o que não é verdade.

O portão `watch-retention-fifo-oracle` ficou em **29/29** (neg 2/2), com as secções
do acumulado, do reinício e da distinção dos três estados.

### E o acumulado tinha de sobreviver a um REINÍCIO — que acontece sozinho

MEDIDO, e é um furo real: **o sidecar reinicia sozinho durante uma call** — o
watcher reinicia-o. Um total que só vive em memória do processo é esquecido a
cada reinício, e o que acontece a seguir é o pior dos dois: a Fase B, corrida
depois da call, lê o payload, vê `clips_evicted_total: 0` e diz ao dono que o
directório está completo, **sobre áudio que já foi perdido**.

O payload é reescrito a cada janela, mas **sobrevive ao processo** — por isso é
ele que guarda a verdade. `resume_evicted_total()` lê-o no arranque e devolve 0
para payload ausente, ilegível ou corrompido: um ficheiro a meio não pode parar
a detecção de duas vozes.

Isto é a **segunda vez** que o reinício automático do sidecar morde. Vale a pena
não o esquecer quando o próximo bug aparecer só "às vezes".

---

## 7.13 A MEDIÇÃO DOS RTF TEM UMA RESSALVA QUE IMPORTA

**Todos os RTF deste recibo foram medidos com a máquina carregada**, por
processos do dono (`background_server.py` com 3094 s de CPU accumulated desde
as 17:07, um `run.py` e dois watchers). Não matei nada: o `run.py` não é meu,
não existe nenhum `run.py` em `H:\sotto`, e o pai dele é `py -3.11` numa shell
interactiva.

**Isto deixou de ser impressão: `_main/_cpu-load.py` mediu a carga** (§7.7) —
**76 % a 83 % global, 8 a 12 dos 20 núcleos ocupados, 10 a 12 livres.** A máquina
é
realmente carregada, e o veredicto do instrumento é o que este recibo queria
dizer quando escreveu "~91 %": o número absoluto é **pessimista**, e as
comparações de lado a lado mantêm-se.

O que isso invalida: **os números absolutos de RTF são pessimistas.** Uma
medição deu RTF 4,641 no mesmo áudio onde outra dera 0,003 — variação de
contenção, não física.

O que NÃO invalida: **as comparações feitas de seguida umas atrás das outras**,
todas na mesma corrida e sob a mesma carga. O degrau 10 s → 11 s, o factor 355×
entre clip único e janelas, e o RTF 0,0097 da Fase A contra 0,503 da Fase B
foram medidos assim, e é assim que devem ser lidos.

---

## 7.14 D1 — O PIPE DO SIDECAR NÃO TINHA NINGUÉM A LER (achado por um auditor)

Este não é um risco imaginado. É o **modo de falha mais silencioso de toda a
cadeia**, porque não dá nenhum sinal: a atribuição é que deixa de acontecer, e o
dono vê legendas correctas e sem voz nenhuma.

`SpeakerSidecar.start` abria o filho com `stdout=PIPE` e **não arrancava nenhum
leitor**. Isto não é uma hipótese de estilo: o `WorkerBridge` da mesma shell liga
um leitor **por stream** (`:11006`) — o sidecar ficou de fora desse padrão por
acidente. Um `PIPE` que ninguém lê enche, e o filho **trava na escrita**.

**Medido, com a configuração exacta do `SpeakerSidecar`** (`I:\cc-tmp\pipe-fill-probe.py`):

| fact | número |
|---|---|
| o filho escreve | **3 480 B** e **trava** |
| produção do sidecar | **5,8 B/s** (58 B × 1 linha / 10 s) |
| tempo até bloquear | **~10 minutos de call** |
| o que acontece quando bloqueia | a atribuição **desliga, sem alarme** |

O nome do ficheiro de medição é quase o resumo do problema: `pipe-fill-probe`.

**A correcção** é `_start_drain()` — uma thread daemon que lê o stream do filho e
manda **tudo** para o log (`sotto_webview.py:10393`, chamada em `:10390`). Duas
decisões que valem a pena nomear:

1. **O filho é passado explicitamente.** Um dreno que vai buscar `self.child` por
   dentro tem uma janela em que ainda é `None`.
2. **Tudo vai para o log.** Descartar o diagnóstico seria a mesma mentira que uma
   excepção engolida — e é exactamente por aí que este bug vivia: **silêncio do
   dreno é stall, não "nada a dizer".**

**O portão tem DUAS metades e as duas correm** (`speaker-watch-oracle.py:382-418`).
A primeira prova o defeito (sem leitor, o filho trava); a segunda prova a correcção
(o mesmo filho atravessa milhares de linhas). Isto é deliberado e está escrito no
ficheiro: **se só a segunda corresse, o dreno podia desaparecer um dia e o gate
dizia "ok"** — e nesse dia o gate era que estava a mentir, não o código.

> **Ressalva de honestidade deste recibo — e um número que eu quase escrevi
> errado.** O portão imprime `40000 linhas lidas em 6 s (sem dreno, trava aos
> 3480 B)`. A primeira leitura é *o gate exige 40 000*; a segunda é *o limiar são
> 4 000*. **Nenhuma é exacta e por isso vale a pena dizer as duas.** O que o
> código faz (`speaker-watch-oracle.py:415-425`): espera até `len(got) ≥ 4000` (ou
> 6 s), mata o filho, e afirma `len(got) > 4000`. O número impresso **é
> `len(got)` — a medição, não um arredondamento** — e nesta corrida deu 40 000,
> que é o total que o filho escreve. **Limiar e observado são coisas diferentes:**
> o limiar é a afirmação, o observado é o que aconteceu. Um gate que imprimisse
> o limiar como se fosse o resultado seria um `n_clips` (§7.11) com outro nome.

`sotto_webview.py` depois de D1: **12 785 CRLF / 0 LF**, sintaxe OK,
`--check-args` rc=0. **12 785** e não os 12 733 da tabela do §9 — a tabela foi
medida antes desta correcção. **E depois voltou a mudar, por causa de D1b
(§7.17): 12 795 CRLF / 0 LF.** Duas revisões, dois pins, e é exactamente por isso
que o sha anda ao lado do número.

---

## 7.15 D2 — MUTANTES DECORATIVOS: O GATE QUE DIZIA 6/6 E NÃO VIA NADA

Este é o achado mais importante desta revisão, e não é sobre o produto: **é sobre
os portões que mandam no produto.**

O `speaker-sidecar-oracle.py` tinha um mutante que substituía

```
except Exception:      →      except _NeverMatchesThis:
```

`_NeverMatchesThis` **não existe**. A cópia do módulo rebenta com `NameError` no
`import`, **antes de executar um único check** — e o código contava isso:

```python
except Exception as exc:
    print("GREEN mutant ... refused to run")
    caught += 1          # <-- um mutante que NÃO corre, contado como apanhado
```

**6/6 era um número que não dizia nada.** Não "pouco fiável": *zero informação sobre o
mutante que ele dizia provar*. Um gate que infla a sua própria contagem é pior do
que um gate sem braço negativo, porque **compra com o leitor a confiança que
não tem**.

### A regra que saiu daqui

> **Um mutante que não corre não é um mutante apanhado. O gate tem de REPROVAR um
> braço decorativo, nunca inflar o contador.**

Implementação: um contador `weak` à parte, e o veredicto passa a exigir
`weak == 0`. O mutante decorativo passou a **re-lançar** (comportamental) e a
bateria passou a tratar um `tick()` que rebenta como **RED**.

### E a mesma classe de defeito estava em mais dois portões

Provar que um portão mentiu uma vez não é prova de nada sobre os outros. Fui
procurar a **mesma forma** nos dois portões irmãos, e encontrou-se nos dois:

| portão | o que fazia | medido depois da correcção |
|---|---|---|
| `speaker-sidecar-oracle` | `caught += 1` a mutante que não carrega | **34/34 · 6/6 comportamentais** |
| `speaker-plumbing-oracle` | contava `battery()` que rebentava como mutante apanhado | **39/39 · 6/6 comportamental** |
| `speaker-id-oracle:589` | `print("GREEN ... refused to run"); caught += 1` — **literalmente o mesmo código** | **79/79 · 13/13 comportamental** |

**E apareceu uma terceira forma, mais subtil — a que eu não procurava.** No
`speaker-plumbing-oracle`, o mutante `a-crash-in-the-sidecar-kills-the-caption`
trocava `except Exception` por `except ZeroDivisionError`. Ao correr, o
`RuntimeError` do fixture `boom()` **subia por `battery()` inteiro**, e o handler
genérico imprimia *"mutante não correu — DECORATIVO"*.

Ou seja: **um mutante COM DENTES estava a ser classificado como um que não prova
nada** — o erro na direcção oposta, e tão grave como o outro. Um mutante cujo
código rebenta é uma **prova**; o harness é que não conseguia lê-la.

A correcção separa as duas coisas, e é a distinção que faltava em todo este
trabalho:

* **uma excepção que ESCAPA do código em teste é um VERMELHO** — o check
  `OFF-equivalent: a provider that raises -> identical events` passa a registá-la
  como falha nomeada, em vez de a bateria rebentar;
* **uma excepção a CARREGAR o mutante é deco** — `weak += 1`, e o veredicto
  falha;
* **uma bateria que morre depois de carregar é INCONCLUSIVA** — nem apanha, nem
  finge: conta `weak` e diz porquê.

Depois disto o mutante é apanhado pelo check que lhe compete:

```
GREEN mutant a-crash-in-the-sidecar-kills-the-caption
       caught by: OFF-equivalent: a provider that raises -> identical events
```

### O caminho `weak` está provado vivo — não é um ramo morto

Um gate novo que reprova precisa de ser visto a reprovar. Os dois portões
**deram `rc=1` a classificar decorativos** antes da correcção e **`rc=0` depois** —
a mesma execução, o mesmo dia, o único que mudou foi o veredicto. Um ramo que
nunca dispara é uma promessa, não uma porta.

### E um erro **meu**, repetido, no próprio runner

Escrevi o runner da bateria com `$args.Split(' ')` sobre uma string vazia.
`''.Split(' ')` dá `['']` — **um argumento vazio** — e o argparse responde `rc=2`
com uma mensagem que não é um veredicto. O primeiro lote inteiro saiu com
`rc=2` em **7 de 17** portões, e só passou a `rc=0` quando os argumentos passaram
a ser um **array** que se faz splat.

Este erro **já estava na minha lista de erros meus** — "script em lote a
reportar `rc=2` num portão que dava 0". Repeti-o na mesma sessão. O padrão é
sempre o mesmo: **um `rc` que eu não consigo explicar é um erro meu até prova em
contra, e a primeira coisa a fazer é olhar o stdout do processo, não a reação ao
código.**

---

## 7.16 D1b — A MINHA PRÓPRIA CORRECÇÃO PARTIU UM PORTÃO QUE JÁ EXISTIA

Esta é a melhor história da revisão, porque o culpado sou eu e o apanhador foi um
portão escrito **antes** de D1 existir.

`_start_drain` (D1) fazia:

```python
stream = child.stdout
if stream is None:
    return False
```

O teste `is None` está lá e está certo — mas `child.stdout` **levanta
`AttributeError` antes de o teste correr** quando o filho não tem o atributo
`stdout`. Foi o que aconteceu com o duplo do `sidecar-wiring-oracle`:

```
AttributeError: '_FakePopen' object has no attribute 'stdout'
  File "app\webview\sotto_webview.py", line 10390, in start
    self._start_drain(self.child)
  File "app\webview\sotto_webview.py", line 10421, in _start_drain
    stream = child.stdout
```

**A correcção** é `getattr(child, 'stdout', None)`, e o ramo não ficou mudo — passa
a escrever `SIDECAR_DRAIN_SKIPPED reason=filho-sem-stdout-legivel pid=…` no log.
Isto não é só para o gate passar:

> **Um dreno nunca pode ser a razão de o sidecar não arrancar.** Se o `stdout` não
> for um pipe legível, o que existe para drenar é **nada** — e "não havia nada
> para ler" é um facto que se escreve, não uma excepção que se propaga para dentro
> de `start()`.

Depois da correcção: `sidecar-wiring-oracle` **22/22 PASS**, `speaker-watch-oracle`
(o portão do D1, com um `Popen` **real**) **39/39 PASS**. `sotto_webview.py`:
**669 053 B, 12 795 CRLF / 0 bare LF**, sintaxe OK, `--check-args` rc=0. A edição
foi feita por um script que conta CRLF antes e depois e **aborta** se entrar um LF
sem CR — porque editar CRLF com uma ferramenta de texto é a forma mais rápida de
fazer um ficheiro misto sem dar por isso.

### E porque isto é uma boa notícia, e não uma má

O portão **não estava errado**. Ele deu `rc=1` com um traceback, e um traceback que
sai do `main()` é um `rc` não-zero — ou seja, **não foi um verde falso**. A única
coisa que faltava era nomear a falha em vez de a deixar rebentar.

Isto é o contrário do §7.15, e vale a pena dizer em voz alta: ali o portão
**mentiu** (disse 6/6 sem correr nada); aqui o portão **falhou com franqueza**. Um
gate que rebenta é muito melhor do que um gate que aprova. **A lealdade de um
portão mede-se pelo que ele faz quando está errado** — e este não hesitou.

### Uma coisa que eu devia ter feito e não fiz

Devia ter corrido **a bateria inteira** no mesmo minuto em que escrevi D1, e não
só o `speaker-watch-oracle`. A correcção de D1bqou à frente, e o único portão que
a apanhou foi aquele que eu não pensei em correr. A regra que sai daqui já estava
escrita no §7.10 e na nota do `_cpu-load.py`: **um portão que cai depois de uma
edição é o portão a dizer a verdade sobre a edição** — e a primeira coisa a fazer
com essa verdade é não ficar a debater com ela.

---

## 7.17 R1 — RISCO AINDA NÃO MEDIDO: O ZERO DO `stream_epoch` PODE NÃO SER O ZERO DA FALHA

Este ficou **em aberto de propósito**, e registá-lo sem o resolver é parte do
trabalho — porque a tentação, daqui a uns dias, é aplicar um patch sem medir.

`sotto_worker.py:5439` carimba `stream_epoch = time.time()` **à entrada de
`asr_thread`**. Mas o zero que o resto da cadeia usa é **o primeiro chunk
retirado da fila** (`:5806`), e entre os dois há a escada de taps
(`TAP_WINDOW_S = 6.0 s`, `:5182`). Com N candidatos, o skew estimado é
**6 s × N** — e cada legenda seria atribuída a quem falou há ~6–30 s.

**Não foi medido, e não vou fingir que foi.** A medição exige um worker a abrir um
dispositivo de áudio real, e a ordem do dono é para não abrir a app. As três
coisas que sei e que são factos, não estimativas:

1. o `stream_epoch` existe e é carimbado na entrada da thread (`:5439`);
2. o zero do primeiro chunk é noutro sítio (`:5806`);
3. a escada de taps, entre eles, é de 6 s por candidato (`:5182`).

O que **não** sei, e é o que interessa: se o skew é real, se é absorvido pelo
`speaker_id`, e qual é a magnitude. **Não investigar sem autorização do dono** —
investigar isto significa abrir captação de áudio, e essa é a linha que ele
mandou não atravessar.

---

## 7.18 UM PIN QUE APODRECEU SETE DIAS — E A CAUSA, QUE É MAIS ÚTIL QUE O NÚMERO

`AGENTS.md` fixa o tamanho exacto da saída de `run.cmd --help`, e existe um
portão feito exactamente para isso: `_main/agents-md-pins-oracle.py`. Ele mede
**ao vivo** e falha se o documento divergir.

**Correu pela primeira vez hoje, e estava VERMELHO.** O pin dizia:

```
re-measured 2026-10-12 the output is 4956 B, 79 lines, 79 CRLF / 0 bare LF, rc 0,
sha256 91F73971…
```

e o medido hoje é:

```
6934 B, 107 lines, 107 CRLF / 0 bare LF, rc 0,
sha256 51B52939F76C4AA5A35D7D865ED7C6B38C01ACFAD829F36C7A6032C337E01B47
```

### A causa, medida passo a passo (e não adivinhada)

Não bastava dizer "o pin está velho". Medi **cada revisão**:

| revisão | saída do `--help` | linhas | linhas sobre vozes |
|---|---|---|---|
| pin de 2026-10-12 | 4956 B | 79 | — |
| `8639fef~1` (antes do trabalho de orador) | 5336 B | **85** | **0** |
| HEAD (com as flags de orador) | 6934 B | **107** | **13** |

Duas coisas ficam Provadas:

1. O pin de 2026-10-12 **já estava 6 linhas atrasado** antes de o trabalho de
   orador começar. Portanto **não foi o trabalho de orador que o quebrou** — e era
   isso que eu ia dizer se não medisse.
2. O trabalho de orador **acrescentou 22 linhas** ao `--help` (85 → 107), das quais
   **13** são sobre `--speakers`, `--speakers-cheap`, `--save-voice-clips` e
   `--watch-payload`.

### E a pergunta que importa: porque é que ninguém viu?

Porque **o portão não estava na bateria**. A lista do §10 tinha 18 portões e
`agents-md-pins-oracle` não era um deles. Um portão que existe, funciona, e
demonstra que sabe dizer não — **mas não corre, não vigia nada**. Passou sete
dias a apodrecer em silêncio, que é a forma mais comum de um gate morrer:
não por estar partido, por **não estar ligado**.

> **A lição: um portão fora da bateria é um portão que não existe.** A bateria
> é o que decide o que é exigido; o portão é só a capacidade de dizer não.

O portão passou a fazer parte da bateria (§10) e está **GREEN**, e o seu
`--neg-arm` continua a dizer não:

```
AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
CONTROL: 1 failure(s) on the mutated copy (must be > 0)
AGENTS-PINS CONTROL PASS
```

### E o portão tinha um segundo defeito, do mesmo tipo

Ao actualizar o pin, o portão passou a dizer *"the anchor sentence is GONE from
AGENTS.md"*. O anchor era a frase **com a data dentro**:

```python
window(text, "re-measured 2026-10-12 the output is")
```

Isto é o gate **amarrado ao valor**: cada actualização de pin obrigava a editar
o portão, e ninguém quer editar o portão — logo ninguém actualiza o pin, e o
gate acaba por estar a queixar-se de uma frase que ele próprio devia ter
encontrado. O mesmo padrão do `n_clips` (§7.11) e do `clips_evicted` (§7.12):
**um número — ou uma data — colado a uma coisa que muda.**

A correcção é o gate seguir a **frase** e deixar a **data** livre:

```python
window_re(text, r"re-measured \d{4}-\d{2}-\d{2} the output is")
```

E o braço negativo deixou de estar preso à data também — antes ele mutava
`re-measured 2026-10-12`; se a data mudasse, o braço deixava de mutar e
reportava `CONTROL INVALID` (rc=5). Hoje muta o **número**, que é o que
interessa.

**E há uma coisa que este pin provou sobre a minha própria correcção de hoje:**
o `run.cmd` foi convertido de LF para CRLF (§7.19) e a saída do `--help` ficou
**byte-idêntica** (6934 B, sha `51B52939…`, com LF e com CRLF). A medição está
em `I:\cc-tmp\atribuir-pins-drift.py`, que restaura o ficheiro no `finally`.
Ou seja: a conversão **não** mexe no comportamento, e o pin que falhou **não
era culpa da conversão**. Atribuir a causa ao meu próprio acto sem medir teria
sido a leitura errada — e é a leitura errada que este recibo inteiro documenta.

---

## 7.19 O `run.cmd` — O PONTO DE ENTRADA DA APP — ESTAVA EM LF

Este é o mais pequeno e o mais concreto de todos os achados, e é um defeito
**real**, não uma preferência.

`AGENTS.md` diz, sem ambiguidade: *"The app is `app/webview/run.cmd`"*. É o
ficheiro que o dono faz duplo clique. **Medido 2026-10-19:**

| ficheiro | bytes | quebras | sha256[:16] |
|---|---|---|---|
| `app/webview/run.cmd` (antes) | 16 223 | **0 CRLF / 274 bare LF** | `973691C60513D485` |
| `Sotto.cmd` | 2 012 | 32 CRLF / 0 bare LF | — |
| `_main/_audit-verify-all.cmd` | 32 637 | 538 CRLF / 0 bare LF | — |

O `run.cmd` era **o único `.cmd` do repo em LF**, e tem **10 linhas que são só
um `)`** — exactamente a construção mais frágil que o `cmd.exe` tem (blocos de
parênteses). O `AGENTS.md` exige "0 bare LF" em `.cmd`, e os outros dois
obedecem.

**Correcção** (por script, com contagem antes e depois, e **idempotente** — a
segunda execução diz "JA ESTAVA CRLF PURO"):

```
app/webview/run.cmd  16 497 B  274 CRLF / 0 bare LF  sha 0CC916C1E4B187C0
```

### E — isto é a parte que não é óbvia — a conversão é **comportamentalmente neutra**

Medi a saída de `cmd /c run.cmd --help` nas **duas** versões, com o ficheiro
restaurado no `finally` (`I:\cc-tmp\atribuir-pins-drift.py`):

| run.cmd | saída do `--help` | sha256[:16] |
|---|---|---|
| LF (original do HEAD) | 6934 B, 107 CRLF / 0 bare LF | `51B52939F76C4AA5` |
| CRLF (depois da conversão) | 6934 B, 107 CRLF / 0 bare LF | `51B52939F76C4AA5` |

**Byte-idênticos.** Portanto a conversão não mudou o que a app faz — só pôs o
ficheiro de acordo com o contrato do próprio repo e com o que o `cmd.exe`
espera. (E se tivesse mudado, isso era um sinal de que o `run.cmd` dependia das
quebras de linha, o que também não é mau — mas tinha de ser **medido**, não
assumido.)

### Por que estava em LF, se o `git` põe CRLF?

Porque `core.autocrlf=true` (repo) converte LF→CRLF **no checkout**, e o blob
guardado é LF. O que estava em disco não era um artefacto de checkout: era o
estado deixado por uma escrita posterior. Ou seja, o LF era **um estado
transitório**, não um estado duradouro — mas era o estado **no disco do dono, no
ficheiro que ele faz duplo clique**, e é esse que conta.

---

## 7.20 `core.autocrlf=true` SEM `.gitattributes` — O CENSO, E PORQUÊ NÃO O ESCREVI

Este é o achado que o dono tem de decidir, e por isso vai **medido e com a
solução pronta**, em vez de uma opinião minha.

**O que existe:** `core.autocrlf = true`, e **não existe `.gitattributes`**.
Efeito: no checkout, o Git converte LF→CRLF em tudo o que é texto.

**O censo (medido hoje, `git ls-files --eol` sobre a árvore inteira):**

| estado | ficheiros | o que é |
|---|---|---|
| `i/lf  w/crlf` | **1110** | **chegam CRLF a qualquer checkout** — converte-se à vontade |
| `i/lf  w/lf` | 1971 | já estão LF em disco (escritos depois do checkout) |
| `i/crlf` | 13 | já CRLF no índice (inclui `sotto_webview.py`) |
| **total versionado** | **3833** | |

Por extensão, no grupo exposto: 318 `.txt`, 225 `.json`, 165 `.md`, **121
`.py`**, 67 `.mjs`, 44 `.js`, 41 `.css`, 33 `.html`, 20 `.rc`, 19 `.ps1`.

**A leitura honesta deste achado:** *não há nenhuma falha medida associada.*
Nenhum portão falha por causa disto — o único pin de quebras que o repo
verifica (`canonical-producer-oracle.py:286`) espera **`worker/sotto_worker.py`
em CRLF**, e é isso que o Git lhe dá. Portanto isto **não é um defeito com
sintoma**; é uma **inconsistência de política** latente, e a política do repo é
do dono.

**E há uma razão técnica para eu não o escrever sem ele:** o `.gitattributes`
correcto não é só um ficheiro novo — é um `.gitattributes` **acompanhado de um
`git add --renormalize`**, e essa operação varre **as 770 entradas alheias que
estão staged** (ver §12). Normalizar agora passaria por cima de trabalho que
não é meu e que foi deliberadamente deixado intacto. **Fazer a correcção a
meio, sem o dono, seria exactamente o erro que este recibo documenta.**

**A correcção, pronta para um comando, se o dono disser sim** (não a aplico):

```
# .gitattributes  -- medido 2026-10-19, censo de 3833 ficheiros versionados
# Sem este ficheiro, core.autocrlf=true converte LF->CRLF em 1110 deles no
# checkout. NAO renormaliza nada sozinho: so passa a dizer o que se quer.
* text=auto eol=lf
*.cmd  text eol=crlf
*.bat  text eol=crlf
app/webview/sotto_webview.py  text eol=crlf
app/panel/panel.js            text eol=crlf
```

e depois, **num passo separado e com o índice limpo**:

```
git add --renormalize . && git commit -m "chore(eol): fixar as quebras de linha"
```

**O que eu recomendo, com a ressalva honesta:** aplicar a **segunda** parte
(`.gitattributes`) e **não** renormalizar já. Assim o que está em disco deixa de
poder ser convertido em checkout futuros, sem tocar em nenhum dos 770
ficheiros alheios. A renormalização pode ser um commit próprio, com o índice
limpo, e com o dono a saber o que ela faz.

**E a decisão continua a ser dele** — porque a pergunta "os `.py` do `worker/`
devem ser LF ou CRLF?" não é técnica, é de política, e eu não tenho autoridade
para a responder. O que eu tinha era a obrigação de **a medir** e de **a
deixar escrita**, e está feito.

---

## 7.21 ONZE FRASES ONDE UMA PALAVRA FOI SUBSTITUÍDA POR CARACTERES CHINESES

Esta é a que eu menos esperava, e a que mais mexe no material que os outros
agentes leem.

**O defeito:** uma palavra portuguesa ou inglesa **substituída** por caracteres
CJK. O sinal de um IME que estava ligado. A frase continua a parecer uma frase,
e **o sinal não aparece no terminal** — aparece no diff, e só se alguém ler com
atenção.

**Medido** (`git ls-files` sobre os 3015 ficheiros de texto versionados, com
os bytes lidos e os codepoints impressos): **11 linhas, em 10 ficheiros**. Um
deles em **código de produto** (`worker/audio_recorder.py`); os outros em
portões e em recibos.

| ficheiro | linha | o que estava (por codepoint) | o que é |
|---|---|---|---|
| `worker/audio_recorder.py` | 20 | 4 ideogramas (U+80AF U+5B9A U+4E0D U+4F1A) + `quer` | *"que o dono **certamente não** quer"* |
| `_main/sidecar-wiring-oracle.py` | 18 | 2 ideogramas (U+6751 U+957F) + `occurido` | *"a substituição tinha **acontecido**"* |
| `_main/forbidden-audio-line-oracle.py` | 11 | 2 ideogramas (U+70B9 U+4EAE) + `ava`, e a frase inglesa `working Customers Passing` no meio de uma frase portuguesa | *"a escada **inteira acendia**"* |
| `_main/panel-runtime-dom.py` | 23 | 3 ideogramas (U+7B2C U+4E00 U+6279) | *"Uma **primeira leva** de corridas"* |
| `_main/_recording-quality.py` | 15 | 1 ideograma (U+59FF) + `eca` | *"a receber **silêncio**"* |
| `app/shadowplay/.../FRICTION-LEDGER.md` | 371 | 2 ideogramas (U+4EA4 U+6362) | *"a **troca** errada"* |
| `_main/receipt-20261017-...` | 34 | 2 ideogramas (U+9ED1 U+7684) | *"**acabou de o matar**"* |
| `_main/receipt-20261017-...` | 49 | 1 ideograma (U+6768) + a virgula CJK U+3001 | *"layouts **e ficheiros**"* |
| `_main/receipt-20261018-parakeet-clamp-menu.md` | 124 | 1 ideograma (U+649E) + `ou` | *"pelo shell **chocou**"* |
| `_main/receipt-20261018-sentence-structure.md` | 67 | 3 ideogramas (U+81EA U+7136 U+4F1A) | *"O dono **naturalmente** vai suspectar"* |
| `_main/receipt-strip-surface.md` | 468 | 2 ideogramas (U+52A0 U+4E0A) | *"o `settled` **já** resolve"* |

(Os caracteres estão describedos **por codepoint** e não pelo glifo, por duas
razões: o glifo não é legível por quem não lê chinês — o codepoint é — e este
recibo **não** guarda ideogramas de propósito, para que o portão de §7.21.1
não precise de uma excepção para ele. A lista continua verificável: cada
codepoint está no Unicode, e o portão apanha a classe sem precisar de um
catálogo em ideogramas.)

**Onde a palavra original não era recuperável**, não adivinhei: reescrevi a
frase em português correcto, com o mesmo sentido. Uma palavra restaurada por
chute é uma mentira nova, e este recibo não precisa de uma.

### 7.21.1 O portão que faltava — e a excepção que ele tem de fazer

Não havia nenhum. A classe já tinha acontecido antes (o meu próprio histórico
desta sessão regista caracteres chineses a escaparem) e **repetiu-se** — que é
exatamente o que acontece a um erro recorrente sem portão: ele volta, e quando
volta já traz **código de produto** atrás.

O portão novo é `_main/foreign-chars-oracle.py`, e o seu desenho foi tirado do
**censo**, não da intuição:

| | caracteres estranhos no ficheiro | veredicto |
|---|---|---|
| **defeito** (palavra trocada) | **1 a 4** | apanha |
| **legítimo** (citação, fixture, doc em russo) | **19 a 55** | não apanha |

O limiar é **8**: mais do dobro do maior defeito e menos de metade do menor caso
legítimo. A separação é uma **medida**, não uma palpite.

E o que o portão **não** apanha, com o motivo escrito no ficheiro:

* **`.json`** — são *dados*: transcrições de ASR, fixtures, payloads. Texto não
  latino num payload é o dado a falar, não um defeito.
* **`_moved/`** — árvore estacionada de outro projecto, com documentação em
  russo e japonês. O próprio repo a chama "parked, not the product".
* **Pontuação CJK** (`。`) — é pontuação de uma língua, não uma palavra trocada.
  A regra caça **letras**.
* **Grego** (alfa, beta, delta) — **notação científica normal neste repo**
  (canais alpha/beta no painel, e uma fila de índices que usa letras gregas como
  dados). Um portão que apanha notação científica é um portão que se desliga.
  *Isto só apareceu porque o portão foi corrido e mostrou 6 falsos positivos* —
  o Grego estava na minha primeira versão e saiu por medição, não por taste.
* **Este próprio ficheiro** — não é preciso: o catálogo de §7.21 descreve os
  caracteres **por codepoint**, não pelo glifo. Um catálogo em ideogramas
  obrigaria o portão a ter uma excepção para este ficheiro, e **uma excepção
  para o ficheiro que documenta a excepção é o fim da linha**. A regra ficou
  assim: *nenhum ficheiro deste repo guarda ideogramas de propósito.*

**E o braço negativo é executado:** injecta um ideograma numa cópia de um
ficheiro real e exige que o gate a rejeite. O que ele fez:

```
CONTROL: mutacao em AGENTS.md -> REJEITADA (o gate viu)
AGENTS-CHARS CONTROL PASS
```

### A lição, que é maior do que o portão

> **Um defeito que se repete não é azar: é um portão que falta.** E o sintoma
> desta classe é especialmente traiçoeiro, porque a frase **parece** correcta.
> Por isso a defesa não pode ser "ter cuidado" — tem de ser um instrumento que
> apanha o sinal.

---

## 7.22 O PORTÃO DO GRAVADOR ESTAVA VERMELHO POR UMA RAZÃO QUE DEIXOU DE EXISTIR

Este apareceu sozinho: eu corri a bateria, e `audio-recorder-oracle` deu
**rc=1**. Antes de fazer seja o que fosse, **atribuí a causa** — porque a
atribuição errada é a forma mais cara de perder tempo.

**A prova** (`I:\cc-tmp\atribuir-audio-red.py`, que restaura o ficheiro no
`finally`): corri o portão com o `worker/audio_recorder.py` **do HEAD** e com o
**meu**. Resultado **idêntico**: os mesmos 2 braços vermelhos, as mesmas
mensagens. **A falha precede a minha edição** — e a minha edição era um
comentário, que não muda contagens de segmentos.

**A causa, depois de ler o código:** o commit **`109aeb6`** passou o gravador de
WAV para **FLAC** (decisão de 2026-10-17, lossless, 2,2x menor) e mudou o roll
dos segmentos — e **não actualizou o portão**. O portão ficou a procurar
`.wav` num gravador que escreve `.flac`, e a afirmar uma conta de segmentos
derivada de um `_maybe_roll` que já não existe.

| | o portão esperava | o gravador faz (medido) |
|---|---|---|
| formato | `.wav` | **`.flac`** (com queda para WAV se não houver `soundfile`) |
| roll | `ceil(19 200 / 8 960)` = 3 chunks = 1,68 s (arredonda **para cima**) | 2 chunks = 17 920 = 1,12 s (arredonda **para baixo**) |
| segmentos em 6 chunks | 2 | 3 |

**E o gravador está CORRECTO.** Medido: **3 x 17 920 = 53 760 = exactamente as
6 x 8 960 alimentadas.** Nenhuma amostra perdida, nenhuma duplicada, e o índice
concorda com o ficheiro em disco (17 920 amostras, 1,12 s, pico e rms reais).

**O que eu reescrevi no portão** — não para o deixar verde, mas para o pôr a
testar **a promessa** em vez da **implementação**:

* **W2** passa a ler o ficheiro **que o gravador escreveu** (FLAC *ou* WAV, via
  `soundfile` *ou* `wave`) e a exigir: mono, 16 kHz, 16 bits, *frames do
  ficheiro = amostras do índice*, e o round-trip das amostras com erro de
  quantização < 2e-4 (medido: **1,53e-05**).
* **W3** passa a afirmar **"nenhuma amostra se perde"** e **"cada segmento fica
  dentro de um chunk do pedido"** — em vez de uma conta exacta de segmentos. A
  **direcção** do arredondamento é uma escolha de implementação; **que cada
  amostra alimentada saia, uma vez e uma só, não é**.
* **W5** passou a exigir também `rate` e `format` na linha do índice.
* **W4** passou a procurar ficheiros de áudio **em qualquer formato** (antes só
  via `.wav`).

**E o braço negativo foi reescrito com seis mutantes, todos ancorados no código
ACTUAL** — porque três dos cinco antigos ancoravam em `self._wav` e em
`self._samples`, que **já não existem**: o mutante "não aplicava", e o portão
dizia-o. Os seis novos, todos comportamentais:

```
RED  no silence guard: digital zero is filed as audio      -> ['W4 silence was filed']
RED  the index is never written                            -> ['W5 the index is empty', ...]
RED  segments never roll: the whole run lands in one file  -> ['W3 a segment of 53760 samples']
RED  the rate the recorder writes is wrong                 -> ['W2 8000 Hz', ...]
RED  the index lies about the sample count                 -> ['W2 17920 frames != index 17921', ...]
RED  the index lies about the peak                         -> ['W5 the index says the peak is not positive']
```

**Resultado: 7/7 GREEN, e o portão ficou MAIS FORTE do que estava** (mutantes
comportamentais: 3 de 5 -> 6 de 6).

> **Um portão vermelho que se desactualizou é pior do que nenhum portão**:
> ensina o leitor a ignorar o vermelho, e o vermelho é a única coisa que o
> portão tem para dar. Este estava vermelho desde `109aeb6` — e ninguém reparou,
> porque a leitura natural de "vermelho" é "está a passar alguma coisa", não
> "o portão está a falar de um formato que deixou de existir".

---

## 7.23 O PORTÃO DO WRAPPER ACUSOU UMA APLICAÇÃO DO DONO — E ESTAVA CERTO E ERRADO

Este é o caso mais interessante da sessão, porque o portão **tinha razão em
existir** e **razão em falhar**, ao mesmo tempo.

**O que aconteceu.** A bateria de 2026-10-19 13:16 devolveu
`run-cmd-exit-oracle` com **rc=1**: dois braços (`bogus` e `help`) vermelhos,
com a mesma mensagem —

```
[NO] no process is left behind in this tree :: leftovers=[23456]
```

— e o censo viu **uma janela visível** chamada `'Sotto'`.

### O "leftover" 23456 não era nosso

**Medido:** o pid 23456 é o **`LuaTools.exe`** — uma aplicação sem qualquer
relação com o Sotto — criada em **2026-10-17 08:26:38**, dois dias antes, e
cujo `ParentProcessId` guardado é **22988**, que era **o pid do próprio oráculo
nesta corrida**.

A causa é uma coisa que o Windows faz e que ninguém escreve num portão:
**os pids são reciclados.** O `tree()` do censo anda a árvore **por parent pid**,
e por isso adopta como "filho" qualquer processo cujo pai registado coincida
com o pid actual do oráculo — incluindo um de dois dias atrás.

E a regra do repo já tinha a resposta escrita, desde sempre:

> *"A kill filter names the ARTIFACT, never a generic word. Match
> `sotto_worker\.py`, `sotto_webview\.py` or the electron/webview exe path."*

O check de "sobrou algum processo" **não a seguia**: aceitava a árvore inteira.

**A correcção** filtra por **linha de comando** (o artefacto nomeado) **e por
hora de criação** (um resíduo tem de ser deste run):

* **nosso** = a linha de comando nomeia `sotto_webview.py`, `sotto_worker.py`,
  `speaker_sidecar.py`, `speaker_bridge.py` ou `run.cmd`;
* **deste run** = foi criado depois de o oráculo começar.

A linha de comando vem do **WMI** numa chamada só (a tabela de processos do
censo dá o nome do exe, não a linha de comando). Se o WMI não responder, o
check **diz que foi mais fraco** e cai para o filtro pelo nome do exe — não
inventa.

### E a correcção tem de ter dentes — e prova isso

Um filtro que nunca dispara também é um filtro que não prova nada; e um filtro
que dispara sempre acusa o dono. Por isso o oráculo ganhou um `--self-test` que
cria **dois filhos reais** e exige a classificação certa dos dois:

```
SELF-TEST o filtro de residuos:
  [ok]   um filho com `sotto_webview.py` na linha de comando tem de ser NOSSO -> True
  [ok]   um filho com linha de comando neutra tem de ser ALHEIO -> True
SELF-TEST PASS -- o filtro distingue o nosso do alheio
```

Este ramo é o **único** do oráculo que **não toca no produto** — não lança a
app, não abre dispositivo, não escreve nada.

### A janela visível: o que é, e o que NÃO é

O censo apanhou uma janela `'Sotto'` (classe `WindowsForms10.Window.8`, que é
a janela WinForms do pywebview) durante **1 amostra em 297** — cerca de 100 ms.
Pertencecia ao **pid 53784**, que era a app do braço `start-default` — um
braço que **lança a app de propósito**.

**Três censuses hoje, e a honestidade é esta:**

| corrida | amostras | com janela visível |
|---|---|---|
| 13:16 (bateria) | 297 | **1** |
| 13:22 (braços launch-free) | 87 | 0 |
| 13:23 (completa) | 290 | 0 |

**Não é uma constante.** É uma **corrida**: a janela existe durante uma
amostra, ou não existe. E ainstrumentação certa para a medir já existe e é
`_main/panel-startup-flash-census.py` — que **a ordem do dono de 2026-10-11
parou**, porque o censo estava a fazer o PC dele travar. Esse T2 ficou
**UNMEASURED** por ordem, e **não o medi agora**: medir o flash significa
lançar a app repetidamente, e essa é a linha que ele mandou não atravessar.

O que fica escrito é a **medição**, não a conclusão: *o flash existe, é raro
(1 em 674 amostras hoje), e o instrumento que o mede em condições controladas
está parado por ordem do dono.*

### E o que o portão diz do census

O próprio oráculo é explícito, e está escrito no código:

> *"The census is reported above and is NOT part of this exit code: a visible
> window is an APP-side fact, and reading it as 'the wrapper failed' is the
> confusion this oracle was indicted for."*

Isto está certo — o **contrato de saída** é do wrapper, e a janela é um facto
do lado da app. Mas a distinção só é útil se alguém **ler as duas coisas**,
e é por isso que o censo está no mesmo ecrã e não enterrado num log.

### Resultado

**ARM-VERDICT PASS 5/5 · GAP-VERDICT PASS 4/4 · CENSUS-VERDICT PASS 290
amostras, 0 com janela visível** — e o falso positivo do `LuaTools.exe` deixou
de existir porque o check passou a dizer o que diz que diz: *sobrou algo
**nosso**?*

---

## 7.24 O PRÓPRIO GATE TINHA UM ORÇAMENTO MENOR DO QUE O QUE MEDIA

Este é o único caso da sessão em que **o portão estava certo e o gate estava
errado** — e vale a pena porque mostra uma coisa que ninguém gosta de ouvir:
**um gate que obriga a ser contornado deixa de ser um gate.**

### O que aconteceu

O `pre-commit` recusou o commit `ea73f3c` **duas vezes**, sempre com a mesma
saída:

```
  |   perf-probe.mjs       FAILED     exit null:
  RESULT 8 passed, 1 refused
  GATE 8 passed / 1 refused, exit 1
  VERDICT  suites_ok=true gate_ok=false
```

`exit null` em Node significa **processo morto**. O que mata um processo dentro
do `spawnSync` é o `timeout`. E aqui está a causa, que é uma medição e não uma
suspeita:

| o que | onde | valor |
|---|---|---|
| orçamento **por probe** | `parse-gate.mjs:221` | **120 s** |
| orçamento do **gate inteiro** | `run-all.mjs:65` | **300 s** |
| custo real do `perf-probe.mjs` | **medido 2026-10-19** | **231 s** (200 pressões × 1 156 ms) |

O probe é **legítimo** e **lento** — e não cabia no orçamento. Pior: os probes
correm **sequencialmente** (`classify()` usa `spawnSync`, que bloqueia), e o
orçamento do runner tinha de cobrir o do gate.

**E o próprio autor do gate já tinha escrito o sintoma**, na nota do `--repeat`:

> *"the same tree gave 3 passed / 1 refused on one commit and 4 passed / 0
> refused six minutes later, with no change in between."*

O que variava era a **carga**. O que eu medi hoje é o mesmo fenómeno pelo
outro lado: não é o código que quebrou, é o **orçamento** que não acompanha o
código. E o gate dizia *"perf-probe FAILED"* sem nunca dizer *"o orçamento
matou-o"* — que é a pior forma de um gate falhar: parecer que o produto
está partido.

### A prova de que o probe está são

Corrido **isolado**, sem o gate, com métricas normais:

```
N=200  PRESS_PATH_TOTAL_MS=231233.77  PER_PRESS_US=1156168.88
FIRST=0001.mp4  LAST=0200.mp4  SEQUENCE_MONOTONIC=true
ONE_MIB_WRITE_MS=11.71  DISK_BYTES_MEASURED=5305552
```

E o `perf-probe.mjs` **importa só `"./index.js"` e a stdlib do node** — não lê
nenhum dos ficheiros que o commit tocava. A falha não era minha, e isso
também não se presume: mede-se.

### A fuga, usada uma vez, declarada

O commit `ea73f3c` saiu com `SOTTO_SKIP_RUN_ALL=1`, que é a fuga que o **próprio
hook** autoriza e exige que se declare:

> *"Fix it, or set `SOTTO_SKIP_RUN_ALL=1` and say so in the message."*

E foi declarado, com os números todos dentro da mensagem do commit. **Uma
fuga declarada é um registo; uma fuga silenciosa é um gate morto.**

### E depois, a correcção de fundo, num commit à parte

O commit `eccf66b` mudou o orçamento para **por probe**, com
`perf-probe.mjs` a **600 s** (2,6× sobre os 231 s medidos) e o gate inteiro a
**900 s**. E — o que é o ponto — **esse commit foi julgado pelo gate, sem fuga**:

```
  |   perf-probe.mjs       PASS       exit 0, all 4 receipt keys printed, and 1 truth-valued key(s) compared
  |   RESULT 9 passed, 0 refused
  GATE 9 passed / 0 refused, exit 0
  VERDICT  suites_ok=true gate_ok=true
```

**O gate a provar a correcção é a prova.** E o que **não** mudou: o probe
continua a ter de imprimir as chaves de recibo e a sair com 0; o `RED ARM`
continua a ter de ser recusado; as 15 suites continuam a correr todas.

### E uma coisa que o `.gitignore` devia ter dito

`_main/diar-live.json` — o **payload de runtime** do diarizador — não estava
versionado **nem ignorado**. Um `git add -A` trazia para dentro do repo o
resultado da diarização **desta máquina**, reescrito a cada execução. Não é uma
captura de um instrumento: é a **saída do produto**, e a saída de uma run não
perence ao histórico do código. Uma linha no `.gitignore`.

### A lição

> **Um gate que falha por carga, e não por defeito, ensina o leitor a
> contorná-lo.** E um gate contornado é pior do que um gate inexistente, porque
> ainda dá a ilusão de que está a vigiar. A diferença entre os dois está em
> **dizer qual é a razão** — e o `exit null` não dizia nada. Foi por isso que
> o gate recebeu um orçamento **medido** e não um número maior à sorte.

---

## 7.25 O PORTÃO DO `run.cmd` MEDIA A VIDA DA APP A PARTIR DO INSTANTE ERRADO

O único vermelho da bateria `g` (2026-10-19 14:00) era o `run-cmd-exit-oracle`,
e a linha que o reprovava era esta:

```
[NO] the wrapper returned BEFORE the app exited (the wait is the bounded
     READINESS handshake, not the 8.0s lifetime) :: wrapper_ms=8198 app_lives=8.0s
```

À primeira vista parece um sintoma: *"o wrapper demorou 8,198 ms a responder"*.
**Não era.** O log da própria app dizia que ela estava perfeitamente saudável:
`PRELOAD_ACTIVE hasSotto=true` e `SHELL_EXIT rc=0`. O check é que estava a
medir a coisa errada — e a coisa errada era **o instante a partir do qual se
conta a vida da app**.

### A vida da app começa na prontidão, não no arranque

O timer de `--exit-after` é armado na shell **depois** da navegação do painel
completar — está no callback que também chama `mark_launch_ready`
(`app/webview/sotto_webview.py:6044`, dentro do mesmo bloco que chama
`mark_launch_ready` em `:5882`). Portanto a app não vive `exit_after` segundos
a contar do arranque: vive `exit_after` segundos a contar de **T_ready**, o
instante em que o painel ficou pronto.

Medido no log da run `g` (o log carimba cada linha em milissegundos,
`sotto_webview.py:1143-1144`):

```
2026-10-19 14:04:23.587  sotto: PRELOAD_ACTIVE hasSotto=true …      <- T_ready
2026-10-19 14:04:31.724  sotto: TRAY_ICON_DELETE ok=true …           <- o timer disparou
2026-10-19 14:04:34.873  sotto: SHELL_EXIT rc=0 reason=requested …   <- a morte
```

`23.587 + 8 s = 31.587` — e o `TRAY_ICON_DELETE` está às `31.724`. **A app
viveu 11,286 s depois de ficar pronta**, com `--exit-after 8`. O wrapper, que
espera pela *prontidão*, voltou a essa altura (`T_ready + ~0,1 s`).

Ou seja: a margem real entre o wrapper voltar e a app morrer é de **~11 s**, e
**não depende da carga da máquina** — porque o timer nasce em T_ready, que é
justamente o instante que o wrapper espera. O check antigo comparava o retorno
do wrapper com `8 s` contados **desde o arranque**, e por isso reprovava uma
app saudável numa máquina saturada. Era a mesma classe de erro do §7.24: **um
gate que falha por carga em vez de por defeito**.

### A correcção: duas medições independentes, e nenhuma delas depende da carga

1. **A app estava VIVA quando o wrapper voltou?** — medição pontual, feita logo
   a seguir ao retorno: o pid publicado pela própria app, vivo ou morto. Se
   estivesse morta, o wrapper podia ter esperado a morte e estar a responder
   *"pronto"* a uma app que já não existia.
2. **A margem, lida do próprio log** — o instante da morte (o carimbo da linha
   `SHELL_EXIT`) contra o instante do retorno do wrapper. Os dois são o mesmo
   relógio desta máquina, e as duas leituras são conservadoras: o carimbo é
   anterior à morte real e o retorno é posterior ao retorno real, logo uma
   margem negativa é mesmo negativa.

**O que o check já não faz** (e é preciso dizer): o check antigo também
limitava a *prontidão* da resposta do wrapper. A nova medição já não o faz — mas
isso está coberto pelo contrato do produto, que é o **limite de 30 s**
(`SOTTO_READY_BOUND`, `sotto_webview.py:12565`) e se manifesta como **rc 4**
(HANG), que o check `rc == 0` apanha. A promptness deixa de ser uma medição
deste portão e passa a ser o que é: uma propriedade do limite do produto.

### O mutante: a prova de que os checks novos TÊM dentes

Um check que nunca foi posto a falhar não é um check. O mutante é a app que
**só fica pronta quando já está morta** — a forma exacta do defeito que a
medição (1) existe para apanhar. E o **controlo** é a mesma app de mentira com
a polaridade oposta: fica pronta e **continua viva**.

O mutante é um *stub* em Python puro — sem WebView2, sem modelo, sem janela.
O `run.cmd` é o de verdade, byte a byte; só a shell é o stub. O custo são
alguns segundos e o PC do dono não sente nada.

| | a app no instante do retorno | margem |
|---|---|---|
| **controlo** (pronta e viva) | `alive=True` (observada 46 ms depois do retorno) | **+2 938 ms** |
| **mutante** (pronta só ao morrer) | `alive=False` (observada 143 ms depois) | **−287 ms** |

O instrument **diz não** quando o contrato está partido, e **diz sim** quando
não está. A margem negativa do mutante é determinística (o stub deixa a
morte assentar 250 ms antes de o wrapper resolver a espera) — não é uma
corrida.

### Resultado (run `h`, 2026-10-19 14:37)

```
ARM start-logged  rc=0 want=0 PASS pid=51172
    [ok] the app was STILL RUNNING when the wrapper returned … :: observed_95ms_after_the_return
    [ok] the wrapper returned BEFORE the app exited … :: margin=8767ms wrapper_ms=6614
ARM start-default rc=0 want=0 PASS pid=61612
    [ok] the app was STILL RUNNING when the wrapper returned … :: observed_64ms_after_the_return
    [ok] the wrapper returned BEFORE the app exited … :: margin=9149ms wrapper_ms=3994
MUTANT-VERDICT PASS  the MUTANT is red on the two new checks and the CONTROL is green
ARM-VERDICT PASS 5/5 · GAP-VERDICT PASS 4/4 · CENSUS-VERDICT PASS 235 amostras, 0 visíveis
```

E o ramo negativo continua a saber dizer não: `--neg-arm` →
`ARM-VERDICT PASS arm1(bogus) RED-as-expected=True arms2-4-still-green=True
failed=['bogus']`, e o `--self-test` do filtro de resíduos → **PASS**.

### A lição

> **O número que se lê como caminho quando não é caminho é pior do que não
> imprimir.** `wrapper_ms=8198` lia-se como *"o wrapper demorou"* e o veredicto
> lia-se como *"o wrapper falhou"*. Nenhum dos dois era verdade: o wrapper
> tinha cumprido exactamente o que promete, e a app estava de pé. A correção não
> foi afrouxar a asserção — foi **descobrir de que instante se conta a vida** e
> medir a partir daí, com **duas** observações independentes e um mutante ao
> lado que prova que ambas sabem dizer *não*.

---

## 7.26 A AUDITORIA DE 2026-10-19 — O QUE ELA DEIXOU ABERTO, E O QUE EU FECHEI

O subagent de **full audit** entregou o seu relatório (a nota "bloqueado" era
uma única chamada de `Set-Location` que ele contornou; o resto do trabalho
correu). Os **dois** achados mais graves dele — o pipe do sidecar sem leitor e
os mutantes decorativos — **já estavam corrigidos** por mim (§7.14 e §7.15),
porque os encontraram pelo mesmo caminho. O que ele deixou **aberto** foi outra
coisa, e é isso que está aqui.

### O censo dos `except:` da shell — a medição que faltava

O auditor escreveu, e com razão: *"não avaliei um a um se engulam um erro
observável. Isso é leitura, não medição — está por fazer."*

Feito. Instrumento: `ast` sobre `app/webview/sotto_webview.py`, a classificar
cada handler pelo que o corpo **faz** com a excepção.

| | |
|---|---|
| handlers no total | **157** (o "uns 23" do auditor eram os `except:` **nus**) |
| registam o erro (chamam `log`/`warn`/`print`) | **90** |
| **engolem em silêncio** | **46** (24 com `pass`, 22 que seguem em frente) |
| devolvem um valor | **20** |
| re-lançam | **1** |
| apanham `BaseException` | **1** — e **re-lança**, portanto está certo |

O número sozinho não diz nada; o que diz alguma coisa é **onde** cada um
está, e o mapa por função mais interna levou-me a quatro que **não são
indiferentes**: são catches defensivos em caminhos onde o silêncio **tem
consequência que o dono sente**.

### Quatro falhas engolidas que tinham consequência — fechadas

| onde | o que o silêncio escondia |
|---|---|
| `WorkerBridge.stop()` | o `kill()` **e** o `terminate()` falhavam: um worker de 2 GB sobrevivía e `stop()` respondia *"parou"* — **a captação continuava** |
| `SottoShell.show_panel()` | o reset `no_audio_restarts = 0` falhava: o **Alt+C deixava de ser o caminho de volta** ao worker que morreu em silêncio |
| `WorkerBridge._kill_and_restart()` | o `terminate()` falhava: o worker sobrevivía e o restart agendava-se a seguir — **dois captadores no mesmo dispositivo** |
| `WorkerBridge._schedule_restart()` | o `cancel()` do timer antigo falhava: o timer sobrevivia — **exactamente o bug da row #15 (2026-10-11)**, dois reinícios para uma morte |

Os quatro passaram a **dizer o que aconteceu** (`BRIDGE_KILL_FAILED`,
`BRIDGE_NO_AUDIO_RESET_FAILED`, `BRIDGE_TERMINATE_FAILED`,
`BRIDGE_RESTART_TIMER_CANCEL_FAILED`), com o token-forma que o resto do log da
shell usa. Nenhum deles muda o comportamento quando **não** há excepção: aqui
só se acrescenta a voz que faltava.

O `except BaseException` da shell (único) foi verificado: **re-lança**, portanto
o `Ctrl+C` ainda interrompe. Está certo como está.

### A constante morta que prometia um acoplamento — agora é um portão

`worker/speaker_sidecar.py` tinha `DEFAULT_MAX_AGE_S = 30.0` com o comentário
*"Must be >= the bridge's `DEFAULT_MAX_AGE_S` […] Kept as a constant here so the
coupling is visible."*. **A cópia nunca era lida.** Nada a usava, portanto
mudar a janela da ponte deixava aquele ficheiro a **afirmar uma relação que já
não existia** — e o auditor tinha razão em chamar-lhe um comentário que mente.

Agora o acoplamento é um **check**, e o check tem **dois mutantes** que o
apanham pela razão certa:

```
GREEN the sidecar's freshness window is the bridge's (the copy is not stale)  sidecar=30.0s bridge=30.0s
GREEN the bridge's window outlives two publish cadences (a payload is fresh when it is read)  window=30.0s cadence=10.0s margin=10.0s
GREEN mutant a-stale-freshness-copy         caught by: the sidecar's freshness window is the bridge's (the copy is not stale)
GREEN mutant a-cadence-outlives-the-window  caught by: the bridge's window outlives two publish cadences (a payload is fresh when it is read)
VERDICT: PASS  arms 36/36  mutants 8/8
```

O porquê de **duas** cadências e não uma: com a janela a valer exactamente
para uma cadência, o acoplamento só é verdade no caso perfeito — e o caso
perfeito é o que não acontece. A margem medida é de **10 s**.

### O `catch` vazio do `strip-drag.js` — convenção quebrada, gravidade baixa

O ficheiro tem **quatro** catches: três trazem um valor seguro ou uma
explicação. O quarto — `catch (err) {}` — não tinha corpo **nem razão**, e era
o único do ficheiro assim. Passou a dizer o que a convenção do painel exige
(`console.error("sotto: <TOKEN> …")`, como em `history-store.js`).

**Gravidade baixa, e é preciso dizê-lo:** a shell expõe `beginWindowDrag`
(`sotto_webview.py:3978`), portanto o `native` é verdadeiro e o `tell()` — que
é onde o catch vive — está no **caminho de fallback** que a app real não toma.
O que o catch engoliria é o offset da strip num host sem arrasto nativo.

### O que a auditoria deixou por medir (e o que eu também não medi)

1. **R1 — o skew do `stream_epoch`**: por medir exige worker com dispositivo
   de captura real, que é a linha que o dono mandou não atravessar. **Não
   medido, não sondado.**
2. **O modelo sherpa**: `_main/_speaker-chain-live.py` nunca correu nesta
   sessão — a cobertura do modelo real é **ZERO**. Os números nos comentários
   (275 MB, RTF 0,416, DER 0,03 %) são de 2026-10-18 e **não foram
   re-medidos**.
3. **O runtime do painel**: nada foi renderizado. O `catch` vazio era o único
   sintoma de leitura estática; o resto continua por ver em execução.

---

## 7.27 PESQUISA ONLINE — O QUE O UPSTREAM DIZ, E O QUE ISSO MUDA

O dono perguntou porque é que eu não pesquisava nada online. **Porque não
pesquisei — zero vezes em 15 horas.** Corrigido hoje. O `web_search` do
toolbox está a falhar (`MATRIX_TOOL_REQUEST_FAILED`), por isso fui pelo
`web_fetch` às **fontes primárias**.

**Fonte 1 — o exemplo oficial do sherpa-onnx (Xiaomi/k2-fsa):**
`https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/python-api-examples/offline-speaker-diarization.py`
**Fonte 2 — a documentação:** `https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html`
**Fonte 3 — o upstream do modelo do repo:** `https://github.com/DimQ1/nemotron-speech-csharp`

### O que a pesquisa CONFIRMA

| | upstream | Sotto | |
|---|---|---|---|
| modelo de segmentação | `sherpa-onnx-pyannote-segmentation-3-0` | o mesmo | ✅ |
| modelo de embedding | 3D-Speaker `eres2net_base_16k` | o mesmo | ✅ |
| `min_duration_on` | 0.3 | 0.3 | ✅ |
| `min_duration_off` | 0.5 | 0.5 | ✅ |
| ground truth | `0-four-speakers-zh.wav` | **o mesmo ficheiro** (1 819 586 B) | ✅ |

O DER de 0,03 % foi medido contra a **amostra do próprio upstream**, com os
**modelos do próprio upstream**. A config espelha a do upstream — a excepção
`window_shift_ratio` está de fora porque o sherpa-onnx 1.13.4 (a versão
instalada) ainda não tem o parâmetro, e isso está escrito no código.

### A ÚNICA diferença — e a medição resolveu-a

| | upstream | Sotto | o que significa |
|---|---|---|---|
| `FastClusteringConfig.threshold` | **0.5** | **0.9** | a docstring do upstream: *"a smaller cluster_threshold leads to more clusters (more speakers); a larger one leads to fewer"* |

**MEDIDO HJE** no ground truth de 4 vozes **do próprio upstream**
(`_main/diar-models/0-four-speakers-zh.wav`, 56,86 s de áudio, 2 threads),
com o instrumento `_main/_diar-run.py` (o do DER), duas corridas:

| limiar | vozes encontradas | RTF | parede |
|---|---|---|---|
| **0,9 (nosso)** | **4** — o número certo | 0,528 | 30,0 s |
| 0,5 (o do exemplo upstream) | **7** — sobre-partiu | 0,422 | 24,0 s |

**Logo o nosso 0,9 está certo e o 0,5 do exemplo partiria a mesma gravação em
7 vozes.** Isto deixou de ser uma decisão do dono e passou a ser um número: o
limiar **fica 0,9**. Recipientes: `I:\cc-tmp\diar-upstream-t0.9.json` e
`I:\cc-tmp\diar-upstream-t0.5.json`.

O RTF medido agora (0,528) confirma a ordem de grandeza do 0,416 anunciado.
E fica explicado o RTF 0,003 que o `der-oracle.py` imprime: o áudio dele é
quase todo silêncio, e sem fala o passo caro — a extracção dos embeddings —
quase não corre. **Não é uma contradição; é a diferença entre medir o modelo e
medir a aritmética.**

### O que a pesquisa NÃO mudou

- O `threshold` **não** é o limiar de detecção da Fase A: é o do *clustering*
  (a distância de cosseno a partir da qual dois embeddings passam a ser
  vozes diferentes). A detecção "há duas vozes?" é a Fase A, que tem o seu
  próprio portão (`multivoice-oracle.py`). Está escrito no código, e agora
  também está aqui.
- Nenhuma conclusão do recibo muda. A pesquisa **confirma** a proveniência
  (é o upstream, não é invenção nossa) e **marca uma decisão** que é do dono.

---

## 8. O que NÃO está feito

1. **Política de "quando é seguro separar as vozes"** — é do dono. As condições
   já estão medidas e são bem mais baratas do que eu primeiro reportei:
   sobre os clips que a Fase A de facto guarda (2–7 s), a Fase B mede
   **RTF 0,012–0,09**; o preço de arranque dos dois modelos é **0,49 s** e paga-se
   uma vez por processo, se a fila for processada num processo só. O que falta é
   a *decisão* — quando acelerar.
   **Não adivinho isto**: um agendador que lance 135 MB no PC dele durante uma
   call é a forma mais rápida de repetir o que ele mandou parar. O que entregue
   é a capacidade (`multivoice-offline.py`), não o agendador.
   **O que ficou feito desde então, e não é a decisão:** a Fase B agora tem uma
   **guarda de carga** (§7.8) que recusa com `rc=4` antes dos 135 MB quando não há
   um núcleo livre, e imprime a carga no RTF e dentro do payload. Isto não diz
   *quando* correr — diz *agora não*, e só num caso que se mede. O agendador e a
   decisão continuam a ser dele.
2. **DER no regime Discord** — exige truth humana do dono.
3. **Nomes das vozes** — exige os nomes reais dele. Não se inventam.
4. ~~**Nada foi commitado nem pushado** — proibido.~~ **SUPERADO 2026-10-19.**
   O dono mandou *"pusha quando conseguir"*, e foi feito: branch
   `feat/speaker-attribution-20261019`, commit **`8639fef`**, **exactamente 38
   ficheiros**, 13 080 inserções, já no remoto. As **770 entradas alheias** que
   estavam *staged* (ZIPs na raiz, um directório literal `%SystemDrive%`,
   `_main`, `probe/`, `_moved/`, `history-verify/`, `runs/`) foram
   **deliberadamente deixadas de fora** e o índice foi salvo em
   `.git/index.backup-20261019`. PR:
   `https://github.com/mateusant13/sotto/pull/new/feat/speaker-attribution-20261019`.
   O destino dessas 770 entradas continua a ser **decisão do dono** — ver §12.
   (O número é **770**, não 778: ver §9. Eu vinha a escrever 778 sem medir, que
   é precisamente o defeito que este recibo documenta noutros sítios.)
5. **R1 — o skew do `stream_epoch`** (§7.17). Descrito, delimitado e **não
   medido**: medir exige captação de áudio real, que é a linha que o dono mandou
   não atravessar. Não é um bug com um sítio fixo; é um risco com uma magnitude
   desconhecida.

---

## 9. Ficheiros tocados (**re-medidos 2026-10-19**, depois de **TODAS** as edições)

Instrumento: `node`/leitura dos bytes para tamanho e quebras, `sha256` sobre
esses mesmos bytes. **Um pin desatualizado aqui é trabalho feito duas vezes** —
por isso re-medido, e não copiado da tabela anterior.

| ficheiro | bytes | quebras | sha256[:12] |
|---|---|---|---|
| `worker/speaker_sidecar.py` | 67 261 | LF (1 431) | `7b236ad3510e` |
| `worker/speaker_bridge.py` | 11 242 | LF (255) | `083e572dd805` |
| `worker/speaker_id.py` | 15 917 | LF (357) | `9a8c2c6de80d` |
| `worker/audio_recorder.py` | 13 577 | LF (327) | `8bacaeb9baed` |
| `app/webview/sotto_webview.py` | 670 842 | **12 815 CRLF / 0 LF** | `4bc836c15c9d` |
| `app/panel/strip-drag.js` | 7 318 | **173 CRLF / 0 LF** | `b93a438ed9c0` |
| `app/webview/run.cmd` | 16 497 | **274 CRLF / 0 LF** | `0cc916c1e4b1` |
| `AGENTS.md` | 95 769 | LF (986) | `b9cbddc56b27` |
| `_main/multivoice-oracle.py` | 15 596 | LF (361) | `b022615619de` |
| `_main/speaker-watch-oracle.py` | 19 330 | LF (445) | `9c2463e203bb` |
| `_main/multivoice-offline.py` | 16 771 | LF (374) | `ca5f4074af4d` |
| `_main/phase-a-b-cycle-oracle.py` | 9 851 | LF (230) | `ea58c1162787` |
| `_main/der-oracle.py` | 14 712 | LF (356) | `13bd2a60e02d` |
| `_main/speaker-density-gate-oracle.py` | 10 574 | LF (258) | `7373fa846b2a` |
| `_main/offline-load-guard-oracle.py` | 11 071 | LF (287) | `a0a38b924a09` |
| `_main/watch-retention-fifo-oracle.py` | 20 610 | LF (456) | `0352841aba5f` |
| `_main/_cpu-load.py` | 11 582 | LF (259) | `d01bc085976a` |
| `_main/speaker-plumbing-oracle.py` | 27 059 | LF (587) | `ad20f6cd258c` |
| `_main/speaker-id-oracle.py` | 33 124 | LF (711) | `53e7f87101ac` |
| `_main/speaker-sidecar-oracle.py` | 21 391 | LF (435) | `11649d7e9449` |
| `_main/speaker-slots-oracle.py` | 10 964 | LF (251) | `bc48c5862b60` |
| `_main/sidecar-wiring-oracle.py` | 12 215 | LF (290) | `c5ee99aae588` |
| `_main/caption-lines-oracle.py` | 11 248 | LF (252) | `bf5c48b68919` |
| `_main/per-app-source-plumbing-oracle.py` | 12 997 | LF (257) | `72b46e413af3` |
| `_main/app-target-oracle.py` | 26 957 | LF (620) | `f7b3e9c65965` |
| `_main/agents-md-pins-oracle.py` | 7 838 | LF (183) | `b21e1da36053` |
| `_main/foreign-chars-oracle.py` | 10 990 | LF (277) | `70243b42e0ee` |
| `_main/audio-recorder-oracle.py` | 16 542 | LF (380) | `ede5401a75c7` |
| `_main/forbidden-audio-line-oracle.py` | 7 622 | LF (177) | `c6dbc89603c3` |
| `_main/run-cmd-exit-oracle.py` | 86 293 | LF (1 740) | `713f9e06ec3b` |

> **O próprio recibo (`_main/receipt-20261018-fase-a-multivoice.md`) não está
> nesta tabela, de propósito.** Um ficheiro que escreve o seu próprio tamanho
> muda-o no instante em que o escreve — a linha seria mentira no instante em
> que aparecesse. O sha do recibo também não: mudaria a cada secção. Quem
> precisar dele mede-o no momento.

> **Porque esta tabela foi re-escrita e não acrescentada:** a anterior dizia
> `sotto_webview.py` = 665 772 B / **12 733** CRLF / `b7bc6781e9e0`, e
> `speaker-watch-oracle` = 16 463 B / `8ad94914e515`. **Ambos mudaram depois** —
> a shell por causa de D1 e D1b (§7.14, §7.16), o portão porque ganhou o braço
> do dreno, e o `run.cmd` porque estava em LF (§7.19). Um pin desatualizado aqui
> não é um defeito de documento: é a próxima lane a citar `12 733` e a medir
> 12 795 e a concluir que alguém mexeu onde não devia. Por isso: **medido hoje,
> com o sha ao lado para se saber de que revisão se fala.**
>
> **E esta revisão (depois do §7.25) mudou DOIS pins desta tabela**, e ambos
> por causa do mesmo achado: o `run-cmd-exit-oracle.py` passou de 70 879 B
> (`e5885b807dae`) para 86 293 B (`713f9e06ec3b`) — as duas medições novas do
> contrato G3 e a fase do mutante com o seu controlo — e o `AGENTS.md` passou
> de 94 860 B (`24a53e99b3d6`) para 95 769 B (`b9cbddc56b27`), porque a linha
> que dizia *"the wrapper returns in ~250 ms while the app lives 8 s"* estava
> **podre desde o handshake G3** (é de 2026-10-06, e o wrapper hoje espera pela
> prontidão: 4–7 s medidos). Uma linha falsa no `AGENTS.md` é lida por todos os
> agentes — por isso se corrige no mesmo sítio em que se mede.
>
> **E a revisão seguinte (§7.26) mudou mais QUATRO pins**, todos pelo mesmo
> motivo — as quatro falhas engolidas com consequência, a constante que passou
> a ser portão, e o `catch` vazio: a shell passou de 669 053 B / 12 795 CRLF
> (`d45c7336fc20`) para **670 842 B / 12 815 CRLF** (`4bc836c15c9d`); o
> `speaker_sidecar.py` de 66 591 B (`8444c32013bb`) para 67 261 B
> (`7b236ad3510e`); o `speaker-sidecar-oracle.py` de 19 368 B (`a0e5436dbfbb`)
> para **21 391 B** (`11649d7e9449`); e o `app/panel/strip-drag.js` — que
> **não estava na tabela** — entra com 7 318 B / **173 CRLF** (`b93a438ed9c0`).
> A shell e o `strip-drag.js` são CRLF puro e foram editados **por bytes**,
> com um script que aborta se introduzir LF nu (§7.26).

---

## 10. Bateria depois de TODAS as edições

**Re-corrida inteira em 2026-10-19, depois de D1, D1b, D2, da conversão do
`run.cmd`, das 11 correcções de §7.21, das reescritas de §7.22 e §7.23, da
correcção do contrato G3 (§7.25) e das quatro falhas engolidas com
consequência (§7.26)** — não é a bateria de ontem com uma linha nova. Os
números abaixo são desta corrida (`I:\cc-tmp\bateria-20261019h.log` — ver a
nota de rodapé sobre este ficheiro —, 15:07→15:22:37): **24 portões, 0
vermelhos.**

| portão | resultado |
|---|---|
| `multivoice-oracle` | **PASS 13/13** · neg **rejeitado** |
| `speaker-watch-oracle` | **PASS 39/39** · neg **FAIL 8/38** (mutação rejeitada) |
| `phase-a-b-cycle-oracle` | **PASS 13/13** · neg **rejeitado** (sem áudio, a Fase B recusa com rc=3) |
| `der-oracle` | **PASS 2/2** · neg **DER 98,3 %** com rótulos ao acaso |
| `speaker-density-gate-oracle` | **PASS 13/13** · neg **PASS 8/8** (a fragmentação volta: 6 slots a 20 s, 12 a 10 s) |
| `_realcall-acceptance.py` | **PASS 8/8** · 180 s da **call real do dono**, ponta a ponta |
| `_cpu-load.py --self-test` | **PASS 9/9** · **4/4 mutantes rc=1** |
| `offline-load-guard-oracle` | **PASS 16/16** · neg **PASS 9/9** |
| `watch-retention-fifo-oracle` | **PASS 29/29** · neg **PASS 2/2** (0,186 MB com tampa de 0,100 MB; 6 de 6 clips) |
| `speaker-plumbing-oracle` | **PASS 39/39** · **6/6 mutantes, todos comportamentais** |
| `speaker-id-oracle` | **PASS 79/79** · **13/13 mutantes, todos comportamentais** |
| `speaker-sidecar-oracle` | **PASS 34/34** · **6/6 mutantes, todos comportamentais** |
| `speaker-slots-oracle` | **PASS 18/18** |
| `sidecar-wiring-oracle` | **PASS 22/22** — foi **vermelho** antes de D1b (§7.16) |
| `caption-lines-oracle` | **PASS** |
| `per-app-source-plumbing-oracle` | **PASS** |
| `app-target-oracle` | **PASS 9/9** · M1 e M2 **RED-as-expected** |
| **`agents-md-pins-oracle`** | **PASS 2 pins** · neg **CONTROL PASS** — **entrou hoje** (§7.18) |
| **`foreign-chars-oracle`** | **PASS** · neg **CONTROL PASS** — **entrou hoje** (§7.21) |
| **`audio-recorder-oracle`** | **GREEN 7/7** · neg **6/6 mutantes** — **reescrito hoje** (§7.22) |
| `forbidden-audio-line-oracle` | **GREEN** |
| **`run-cmd-exit-oracle`** | **ARM 5/5 · GAP 4/4 · MUTANT PASS · CENSUS PASS (235 amostras, 0 visíveis)** — o contrato G3 medido em **duas** observações independentes, com o mutante e o seu controlo ao lado (§7.25) |
| **`run-cmd-exit-oracle --self-test`** | **PASS** — o filtro distingue o nosso do alheio (§7.23) |
| `speaker_sidecar.py --selftest` | PASS (não toca em onnxruntime nem sherpa) |

**24 portões, 0 vermelhos, depois de tudo.**

### Duas notas de honestidade sobre esta tabela

1. **`sidecar-wiring-oracle` deu `rc=1` na bateria das 13:16** — e era a
   **minha** correcção D1 que o partiu (§7.16). A tabela de cima é a corrida
   **depois** da correcção. A primeira está no log com o traceback, e o traceback
   é a prova de que o portão tem olhos.
2. **`run-cmd-exit-oracle` deu `rc=1` na MESMA bateria** — e o culpado **não
   era o produto**: era o check que acusava o `LuaTools.exe` do dono por causa
   da reciclagem de pids (§7.23). Corrigido, com self-test, e verde na corrida
   seguinte.
3. **O `agents-md-pins-oracle` não estava na bateria até hoje** — e quando
   entrou encontrou **um pin podre de sete dias** (§7.18). Uma bateria é a
   lista do que é exigido; acrescentar um portão muda o que o produto precisa
   de satisfazer.
4. **A bateria `g` (14:00) deu `rc=1` no `run-cmd-exit-oracle`** — e o culpado
   **também não era o produto**: o check media a vida da app a partir do
   *arranque*, e a vida conta-se desde a *prontidão* (§7.25). Com a medição
   corrigida, a mesma app saudável dá **margem de 8767 ms e 9149 ms** entre o
   retorno do wrapper e a sua própria morte, e a app estava **viva** no
   instante do retorno. A bateria `h` (14:40) está verde.
5. **O log `bateria-20261019h.log` foi SOBRESCRITO** pela corrida seguinte: o
   runner tem o caminho do log fixo no script, e a corrida `i` (15:07→15:22:37,
   a que está em cima) escreveu para o mesmo nome. O que **sobrevive** da
   corrida `h` é o resumo por portão, em `I:\cc-tmp\bateria-h-resumo.log` (24
   portões, rc e duração de cada um). A lição, que é de agora em diante: o
   runner tem de receber o caminho do log como argumento.

**`speaker-slots` e `speaker-sidecar` foram re-corridos hoje de propósito.** Tinham
sido corrigidos depois da bateria anterior — o fixture de silêncio era
`[0.0]*8000`, e **a porta de densidade recusa silêncio (que é o correcto)**: o
fixture estava a medir a porta em vez do slots, e os dois portões caíam. Corrigir
o fixture e não re-correr é a forma mais barata de deixar um verde falso no
histórico; por isso rc=0 e 34/34 + 6/6 medidos **depois** da correcção.

`phase-a-b-cycle-oracle` também foi **re-corrido depois** de a Fase B ganhar a
guarda: **13/13** e neg **4/4**. Sem o `--ignore-load` que lhe pus, esse portão
passaria a falhar conforme a carga da máquina.

E os flags novos da shell são aceites pelo parser (rc=0) enquanto um flag
inventado é recusado (rc=2) — o contrato de `--check-args`, que `run.cmd` usa
para não responder sucesso a uma flag rejeitada.

---

## 11. O que esta revisão acrescenta

*(o cabeçalho dizia "em três linhas" e havia quatro; o número também era um pin
que ninguém media. Agora não há número.)*

1. **Um instrumento escrito mas nunca executado tinha dois defeitos que
   produziam um número falso** — e o próprio output do diagnóstico mostrava-os um
   a um. Quem o diz é o `--self-test` (9/9, 4 mutantes vermelhos), não a confiança.
2. **O instrumento ganhou o primeiro consumidor** (§7.8): a Fase B recusa com
   `rc=4` **antes** dos 135 MB quando não há núcleo livre. E esse portão encontrou
   um defeito real — um `.wav` inexistente custava a carga dos modelos para depois
   rebentar num traceback.
3. **O segundo buraco da retenção (§7.11): numa call longa, o áudio assinalado do
   dono desaparecia em silêncio** — e o estado dizia `n_clips=2` com **zero** clips
   no disco. O FIFO estava certo; a *conta* é que não fechava.
4. **E o buraco fechou-se em três elos, não num** (§7.12): o nome `clips_evicted`
   lia-se como acumulado e era da janela (agora há `clips_evicted_total`); o dono
   vê a perda no log (`AUDIO_PERDIDO`); e **quem corre a separação recebe um
   `COMPLETUDE: INCOMPLETO`** em vez de um resultado silenciosamente incompleto.

### E o que a auditoria de 2026-10-19 acrescentou (D1, D1b, D2, §7.14–7.20)

5. **D1 — o pipe do sidecar não tinha ninguém a ler** (§7.14). O filho escrevia
   **3480 B** e travava; a atribuição desligava **sozinha, sem alarme**, ao fim de
   ~10 min de call. Corrigido com um dreno que manda tudo para o log.
6. **D1b — a minha correcção partiu um portão que já existia** (§7.16). O dreno
   levantava `AttributeError` dentro de `start()`. Um dreno nunca pode ser a
   razão de o sidecar não arrancar.
7. **D2 — mutantes decorativos** (§7.15). Três portões contavam como "apanhado"
   mutantes que **nunca executavam um check**. Um gate que infla a sua própria
   contagem compra com o leitor uma confiança que não tem. Agora um mutante que
   não corre **reprova** o gate.
8. **E a distinção que faltava em todo este trabalho:** uma excepção que escapa
   do código em teste é um **vermelho**; uma excepção a carregar o mutante é
   **deco**; uma bateria que morre é **inconclusiva**. Três coisas, três
   veredicto.
9. **Um pin apodreceu sete dias** (§7.18) porque o portão que o vigiava não
   estava na bateria. Entrou hoje — e encontrou-o.
10. **O `run.cmd`, o ponto de entrada da app, estava em LF** (§7.19), com dez
    linhas que são só um `)`. Convertido para CRLF, e **medido como
    comportamentalmente neutro** (saída do `--help` byte-idêntica).
11. **O `core.autocrlf` sem `.gitattributes`** (§7.20): 1110 de 3833 ficheiros
    versionados chegam CRLF a qualquer checkout. **Censo completo e solução
    pronta** — a decisão é do dono, porque é política, não técnica.
12. **O contrato G3 estava medido a partir do instante errado** (§7.25). O check
    comparava o retorno do wrapper com a vida *pedida* da app contada desde o
    arranque — mas o timer de `--exit-after` é armado na *prontidão*, e é dali
    que a vida se conta. Uma app perfeitamente saudável reprovava o portão numa
    máquina saturada (`wrapper_ms=8198` contra `app_lives=8.0s`), e a linha lia-se
    como se o wrapper tivesse falhado. Agora são **duas** observações
    independentes — a app **viva** no instante do retorno, e a **margem** até à
    morte lida do carimbo do próprio log — com um **mutante e o seu controlo** a
    provar que as duas sabem dizer *não*.
13. **A auditoria de 2026-10-19 entregou o que faltava medir** (§7.26): o censo
    dos **157** `except` da shell, com **46** a engolir em silêncio, e o mapa
    por função que levou a **quatro** falhas engolidas **com consequência que o
    dono sente** — o worker que sobrevivia ao `stop()`, o Alt+C que deixava de
    ser caminho de volta, o segundo captador, e o timer de reinício que
    ressuscitava o bug da row #15. E a **constante morta** que prometia um
    acoplamento sem o impor, que passou a ser um **portão com dois mutantes**.
14. **A pesquisa online que faltava** (§7.27) e a **consolidação que faltava**:
    `_main/RESPOSTA-AO-DONO-20261019.md` — as cinco perguntas do dono
    respondidas com números, a linha de chegada que nunca tinha sido
    declarada, e a **lista de restos** com a decisão de cada um (10 itens:
    **1 resolvido por medição** — o `threshold` do clustering, §7.27 —, 5 são
    do dono, 3 ficam para medir depois, 1 fica de fora com o motivo).
    A pesquisa ao upstream **confirma** a proveniência dos modelos e do
    ground truth, e **marca uma diferença** — o `threshold` do clustering
    (nosso 0,9, upstream 0,5) — que é uma flag, e uma decisão do dono.

Nenhum número deste recibo ficou por actualizar sem ser re-medido — e uma
discrepância que cheirava a erro (12 slots contra 6) era só **cadência**, com as
duas reproduzidas hoje. O que ela revelou é mais útil do que o erro imaginado:
**a porta protege o áudio esparso, a cadência protege o áudio denso**, e nenhuma
das duas chega para as duas.

**A lição que atravessa esta revisão inteira:** quase nada aqui era um bug de
lógica. Era um número que não dizia o que media, um valor devolvido e deitado
fora, e um nome que prometia mais do que entregava. Três deles só apareceram
quando o código foi **executado** — e o `_cpu-load.py`, que tinha nascido para
medir a carga, media a zero.

**E a lição de 2026-10-19 é uma ainda mais específica e mais desconfortável:**
os defeitos mais graves que apareceram foram **nos portões, não no produto**.
Um gate que mente é pior do que um produto lento, porque o gate é o que decide
se o produto está bom. Um mutante decorativo, um anchor preso à data, um portão
fora da bateria, uma vida contada desde o instante errado — são quatro maneiras
de o **sistema de medição** estar a mentir com muita confiança. E uma delas (o
pipe sem leitor) **era** um defeito real do produto, escondido exactamente por um
gate que não fazia a pergunta certa.

Por isso a receita que sobrou, e que é o que fica: **cada afirmação nova tem de
trazer o instrumento que a mede, o número que ele deu e o braço negativo que
prova que ele ainda diz não.** Sem o terceiro, os outros dois são uma história
bem contada.

---

## 12. AS 770 ENTRADAS ALHEIAS — O QUE ESTÁ STAGED E PORQUÊ NÃO TOQUEI

**Medido:** `git diff --cached --name-only | Measure-Object -Line` → **770**,
e `grep speaker` dentro dessas 770 → **ZERO**. Nenhuma é minha.

O que lá está: **dois ZIPs na raiz** (`cinematic-transcription-app-designs (1).zip`),
um **directório literal `%SystemDrive%`** (criado por um `set` que não expandiu
— é lixo, mas é lixo *dele*), `_main/` (400), `probe/` (214), `_moved/`,
`history-verify/`, `runs/`.

**Por que não commitei isto:**

1. **Não é meu.** É trabalho de lanes anteriores, e o dono pode querer isso como
   histórico, como issue, ou descartado. Decidir por ele é decidir *o conteúdo
   do repo* por ele.
2. **Um `git commit -a` tê-lo-ia levado comigo** sem ninguém ver. Foi por isso
   que o push foi feito com **38 caminhos explícitos** (`git commit -F ... --
   <38 caminhos>`), que não toca no índice.
3. **O índice está guardado** em `.git/index.backup-20261019`, para que a
   decisão seja reversível.

**O que eu recomendo, e porquê** — três caminhos, todos do dono:

| opção | o que faz | quando é a certa |
|---|---|---|
| **issue** | descreve o que há, sem trazer o conteúdo | se o conteúdo é ruído de lanes e o valor está na *descrição* |
| **commit em batches** | 3–4 commits temáticos, revistos | se o conteúdo tem valor e o dono quer a história |
| **descartar** | `git restore --staged .` e fica por decidir em disco | se é lixo (`%SystemDrive%`, ZIPs) |

**O que está a segurar isto:** o `zipc-designs-oracle` e o `cobertura-oracle`
olham para o que está versionado, e normalizar as quebras de linha (§7.20) ia
passar por cima destas 770. **Duas decisões do dono, o mesmo ficheiro** — e
por isso é melhor tomá-las em conjunto do que uma de cada vez.

---
