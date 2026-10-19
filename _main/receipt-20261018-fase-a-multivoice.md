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

## 6. Em produto — `_main/speaker-watch-oracle.py`, **34/34**, negativo **FAIL 5/33**

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
4. **Nada foi commitado nem pushado** — proibido.

---

## 9. Ficheiros tocados (medidos 2026-10-18, depois de **todas** as edições)

Instrumento: `node`/leitura dos bytes para tamanho e quebras, `sha256` sobre
esses mesmos bytes. **Um pin desatualizado aqui é trabalho feito duas vezes** —
por isso re-medido, e não copiado da tabela anterior.

| ficheiro | bytes | quebras | sha256[:12] |
|---|---|---|---|
| `worker/speaker_sidecar.py` | 66 591 | 0 CRLF / 1 420 LF | `8444c32013bb` |
| `worker/speaker_bridge.py` | 11 242 | 0 CRLF / 255 LF | `083e572dd805` |
| `app/webview/sotto_webview.py` | 665 772 | **12 733 CRLF / 0 LF** | `b7bc6781e9e0` |
| `_main/multivoice-oracle.py` | 15 596 | LF (361) | `b022615619de` |
| `_main/speaker-watch-oracle.py` | 16 463 | LF (389) | `8ad94914e515` |
| `_main/multivoice-offline.py` | 16 771 | LF (374) | `ca5f4074af4d` |
| `_main/phase-a-b-cycle-oracle.py` | 9 851 | LF (230) | `ea58c1162787` |
| `_main/der-oracle.py` | 14 712 | LF (356) | `13bd2a60e02d` |
| `_main/speaker-density-gate-oracle.py` | 10 574 | LF (258) | `7373fa846b2a` |
| `_main/offline-load-guard-oracle.py` | 11 071 | LF (287) | `a0a38b924a09` |
| `_main/watch-retention-fifo-oracle.py` | 20 610 | LF (456) | `0352841aba5f` |
| `_main/_cpu-load.py` | 11 582 | LF (259) | `d01bc085976a` |
| `_main/_phase-b-cliff-probe.py` | 7 328 | LF (188) | `9ae9300c4163` |
| `_main/_phase-a-retention-probe.py` | 2 501 | LF (61) | `2cc5e096ca1e` |
| `_main/_watch-rss-probe.py` | 4 259 | LF (125) | `6c73d61e9838` |
| `_main/_seg-powerset-probe.py` | 9 839 | LF (211) | `1e123ee029ce` |

Instrumentos de caracterização e ensaios (não portões; escritos para responder a
uma pergunta e poderem ser deitados fora — mas **executados**, que é o que o
§7.7 mostrou que importa):

| ficheiro | bytes | quebras | sha256[:12] |
|---|---|---|---|
| `_main/_fragment-levers.py` | 5 035 | LF (130) | `3571ddf758d7` |
| `_main/_density-gate-probe.py` | 6 127 | LF (141) | `a06bc867af24` |
| `_main/_speech-seconds-probe.py` | 5 321 | LF (134) | `59b7c26eee19` |
| `_main/_energy-gate-probe.py` | 5 359 | LF (138) | `4489c34902fd` |
| `_main/_recording-quality.py` | 5 680 | LF (142) | `b1815b24dcfb` |
| `_main/_realcall-acceptance.py` | 9 540 | LF (236) | `9acb607f319a` |
| `_main/_cliff-contiguous-probe.py` | 4 815 | LF (123) | `3ddf5ef62bec` |
| `_main/_cadence-probe.py` | 5 184 | LF (134) | `3b548e1f1675` |
| `_main/_sidecar-replay-real.py` | 5 900 | LF (138) | `ace1fa8e8351` |

`git log -1` = `109aeb6`, **nada commitado, nada pushado**.

---

## 10. Bateria depois de TODAS as edições

| portão | resultado |
|---|---|
| `multivoice-oracle` | PASS 13/13 · neg **rejeitado** |
| `speaker-watch-oracle` | PASS **37/37** · neg **FAIL 8/36** (mutação rejeitada — eram 5/33 antes das três arms novas) |
| `phase-a-b-cycle-oracle` | PASS 13/13 · neg **rejeitado** (sem áudio, a Fase B recusa com rc=3) |
| `der-oracle` | PASS 2/2 · neg **DER 98,3 %** com rótulos ao acaso |
| `speaker_density-gate-oracle` | **PASS 13/13** · neg **PASS 8/8** (a fragmentação volta: 6 slots a 20 s, 12 a 10 s) |
| `_realcall-acceptance.py` | **PASS 8/8** · 180 s da **call real do dono**, ponta a ponta |
| `_cpu-load.py --self-test` | **PASS 9/9** · **4/4 mutantes rc=1** |
| `offline-load-guard-oracle` | **PASS 16/16** · neg **PASS 9/9** (a recusa desaparece e o carregador passa a ser chamado) |
| `watch-retention-fifo-oracle` | **PASS 26/26** · neg **PASS 2/2** (0,186 MB com tampa de 0,100 MB; 6 de 6 clips) |
| `speaker-plumbing-oracle` | PASS 39/39 · 6/6 mutantes |
| `speaker-id-oracle` | PASS 79/79 · 13/13 mutantes |
| `speaker-sidecar-oracle` | PASS 34/34 · 6/6 mutantes |
| `speaker-slots-oracle` | **PASS 18/18** (era 15/15: +`SilentRing`, que prova que uma janela de silêncio sai `declined`) |
| `sidecar-wiring-oracle` | PASS 22/22 |
| `caption-lines-oracle` | PASS 12/12 |
| `per-app-source-oracle` | PASS |
| `app-target-oracle` | PASS 9/9 · M1 e M2 **RED-as-expected** |
| `speaker_sidecar.py --selftest` | PASS (não toca em onnxruntime nem sherpa) |

**`speaker-slots` e `speaker-sidecar` foram re-corridos hoje de propósito.** Tinham
sido corrigidos depois da bateria anterior — o fixture de silêncio era
`[0.0]*8000`, e **a porta de densidade recusa silêncio (que é o correcto)**: o
fixture estava a medir a porta em vez do slots, e os dois portões caíam. Corrigir
o fixture e não re-correr é a forma mais barata de deixar um verde falso no
histórico; por isso rc=0 e 34/34 + 6/6 medidos **depois** da correcção.

`phase-a-b-cycle-oracle` também foi **re-corrido depois** de a Fase B ganhar a
guarda: **13/13** e neg **4/4**. Sem o `--ignore-load` que lhepus, esse portão
passaria a falhar conforme a carga da máquina.

E os flags novos da shell são aceites pelo parser (rc=0) enquanto um flag
inventado é recusado (rc=2) — o contrato de `--check-args`, que `run.cmd` usa
para não responder sucesso a uma flag rejeitada.

---

## 11. O que esta revisão acrescenta, em três linhas

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