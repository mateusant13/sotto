# Recibo — atribuição de orador em AUDIO REAL DE CALL (2026-10-18)

O dono, verbatim: *"o modelo que a gente tem nao separa faixa de audio dos falantes
ou sei la? [...] eu to com pessoas na call do discord agora falando. testa
imediatamente"*.

Este recibo regista o que foi medido sobre **a call dele**, com o **modelo real**,
e — com igual peso — o que **não** ficou provado.

---

## 1. VEREDITO CURTO

**Sim, separa.** O modelo do sidecar encontra **duas vozes distintas** no áudio real
dela, com 79 % do tempo em fala, e a identidade de cada voz **sobrevive à janela
deslizante em 90,4 %** dos pares de janelas.

O que **não** ficou provado é a segunda voz: na janela medida ela falou **1,5 s**
(3 frames de 0,5 s), amostra que não sustenta uma afirmação. Isso está escrito no
instrumento, que **recusa** devolver PASS com essa amostra (§5).

---

## 2. O QUE FOI CORRIDO, E ONDE

```powershell
$py = 'C:\Program Files\Python311\python.exe'
$env:TMPDIR='I:\cc-tmp'

# 1. captura da call (sem modelo, sem ASR: so o tap WASAPI)
& $py I:\cc-tmp\record-call.py --seconds 60 --out I:\cc-tmp\call.wav --device 'VoiceMeeter'
#    -> endpoint 'WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)' 48000 Hz
#    -> 1 920 000 B, 60,0 s, 600 blocos, peak 0,998, RC=0

# 2. diarizacao com o modelo real
& $py H:\sotto\_main\_call-diar-cmap.py --audio I:\cc-tmp\call.wav --threads 2 `
      --dump I:\cc-tmp\cmap-dump.json
#    RC=0
```

O instrumento novo é **`_main/_call-diar-cmap.py`** (13,9 KB). `--dump`/`--from-dump`
existem porque cada passage custa ~90 s de CPU: sem eles, iterar um mutante
obrigava a pagar o modelo por cada tentativa.

---

## 3. NÚMEROS

**[A] Uma passagem sobre os 60 s** (o melhor caso que este modelo alcança):

```
vozes distintas : 2  -> [0, 1]
segmentos      : 15
fala           : 47,3 s de 60,0 s (79 %)
sobreposta     : 2,5 s (5 % da fala) -- gente a falar por cima
duracao/turno  : mediana 2,36 s, min 0,51 s, max 8,05 s
```

**[B] A cadência que o sidecar usa** (janela 20 s = `DEFAULT_WINDOW_S`, passo 10 s =
`DEFAULT_EVERY_S`):

```
janela  0  [  0.0.. 20.0]   4 seg  vozes=[0]
janela  1  [ 10.0.. 30.0]   3 seg  vozes=[0]
janela  2  [ 20.0.. 40.0]   6 seg  vozes=[0, 1]
janela  3  [ 30.0.. 50.0]   8 seg  vozes=[0, 1]
janela  4  [ 40.0.. 60.0]   6 seg  vozes=[0]
```

**cMAP** (identidade da voz preservada na região de sobreposição, com
emparelhamento 1-para-1 dos rótulos — os rótulos são arbitrários por janela, sem
isso o instrumento não mede nada):

```
0->1  100,0 %   (12 frames)
1->2   75,0 %   (20 frames)
2->3   86,7 %   (15 frames)
3->4  100,0 %   (10 frames)
cMAP GLOBAL = 90,4 %  em 4 pares
```

---

## 4. TRÊS ARMAS DE LEITURA, E PORQUÊ A MENOR É A QUE IMPORTA

| braço | global | voz minoritária | RC |
|---|---|---|---|
| positivo | 90,4 % | 100 % (**3 frames**) | 4 |
| mutante `time` (posições ±1,5 s) | 86,7 % | 100 % (1 frame) | 4 |
| mutante `label` (identidade baralhada) | 85,4 % | **0,0 %** | 4 |
| mutante `both` | 76,2 % | **0,0 %** | 4 |

O achado que mudou o instrumento: **o cMAP global é dominado pela voz
maioritária**. Numa call real uma voz ocupa ~90 % dos frames, portanto mesmo com as
etiquetas **completamente baralhadas** o número global só cai de 90,4 % para
85,4 %. O número global diz sobretudo *"a voz grande continua a ser a voz
grande"* — que é a parte fácil. O que parte a tela ao meio é a voz **pequena**
deixar de ser a mesma pessoa a cada janela, e para isso o instrumento mede cada
voz separadamente (`por_cluster` em `cmap`).

Por isso o `--neg-mode label` (identidade baralhada) leva a voz minoritária a
**0 %** e é o braço que prova que a métrica sabe dizer *não*.

---

## 5. POR QUE O RC É 4 E NÃO 0

`MIN_MINORITY_FRAMES = 30`. Na primeira passagem a voz minoritária tinha **3
frames** e o instrumento imprimia "voz menor 100,0 % — PASS". Com 3 frames isso não
é uma medição: é um denominador quase zero.

O instrumento passou a devolver **`INSUFICIENTE` (rc=4)** com este texto:

```
VERDICT: INSUFICIENTE -- a voz minoritaria so tem 3 frames e o piso e 30.
O cMAP GLOBAL (90.4%) mede sobretudo a voz maior, que e' a parte facil.
Isto NAO e um PASS e nao se deve ler como tal: e' falta de amostra.
```

Um porta que passa sem medir o que diz é pior do que não haver porta.

---

## 6. ERROS MEUS NESTA MEDIÇÃO (todos apanhados por instrumentos, nenhum por introspeccao)

| # | erro | quem apanhou | custo |
|---|---|---|---|
| 1 | **Deslocamento do mutante fora do `if`** — a coluna do cMAP comparava janela *k* com *k+1* deslocada de meia janela | o próprio instrumento: "sem fala na sobreposição" em **todos** os pares, com áudio cheios de fala ali | o número de cabeçalho (2 vozes) continuava certo; **a coluna do cMAP não media nada** e teria passado |
| 2 | **`_shuffle_time` era uma nenhuma-operação** — embaralhava a lista e reordenava por `t[0]`, o campo que não tinha tocado | o braço negativo imprimiu **90,4 %**, exactamente igual ao positivo | mutante decorativo; **teria comprado um VERDICT falso**. Segunda vez nesta sessão (a primeira foi `(a,b,c)` como operador vírgula em `MUTANTS`) |
| 3 | **`Select-Object -Last N` matou o processo** — RC=−1 e nenhum output | o próprio RC | o braço negativo não mediu nada |
| 4 | **WAV escrito com bytes float32 sob cabeçalho de 16 bits** — 60 s gravaram-se como "120 s" | a contagem de blocos (4800 amostras/bloco, 10 blocos/s = 1× real) | a primeira medição de duração foi **falsa por um factor 2** |
| 5 | **`mono.mul()`** — `.mul` é de torch, não de numpy; a exceção matou a thread do pump e o script imprimiu **RC=0** com WAV de 0 B | eu, ao ver o WAV vazio | o gravador dizia sucesso sem ter gravado;a guarda `dur < 0.8*seconds → rc 3` foi acrescentada por causa disto |
| 6 | **Sobreposição somada par a par** | — | com 3 vozes contava a mesma amostra duas vezes; trocado por **união** por varrimento |
| 7 | **Teste sintético com segmentos fora da janela** — dava `n=0` e eu quase culpei a lógica | o teste em si | 1 volta perdida |
| 8 | **Só 3 frames declarados como PASS** | a regra `MIN_MINORITY_FRAMES` | um verde que não era medição |

---

## 7. ESTADO DEPOIS DESTA SESSÃO

**Corrido e verde** (após a edição dos rótulos):

```
_main\speaker-sidecar-oracle.py       arms 34/34   mutants 6/6     RC=0
worker\speaker_sidecar.py --selftest  VERDICT: PASS               RC=0
```

**Alterado em produto:** `worker/speaker_sidecar.py`, 29 293 B → **29 288 B**,
**0 CRLF / 666 LF** (LF preservado), sha256 `87F1B430…` (antes da correção dos
rótulos). Alteração: **cinco** `print("selftest: …")` no **caminho LIVE** passaram a
`print("sidecar: …")`. Linhas 306, 618, 626, 639, 654. A linha 400 e as 419/435
**ficam** `selftest:` porque estão dentro de `capture_selftest()`, onde o rótulo
é verdadeiro.

Porque conta: a corrida real imprimiu `selftest: capturing …` **enquanto carregava
os 277 MB do modelo** e produzia atribuição real. Quem lesse o log — ou eu, mais
tarde — concluiria que aquilo era um selftest sem modelo.

**Instrumento novo:** `_main/_call-diar-cmap.py`.

**Nada commitado, nada pushado** — proibido pelo dono.

---

## 8. O QUE FALTA, E O QUE NÃO DEPENDE DE NINGUÉM

| item | estado | depende do dono? |
|---|---|---|
| duas vozes no áudio real da call | **PROVADO** (15 segmentos, 2 vozes) | não |
| identidade da voz maior sobrevive à janela | **PROVADO** (90,4 %) | não |
| identidade da **voz menor** sobrevive à janela | **POR PROVAR** — 3 frames, o instrumento recusa o verde | precisa de uma gravação em que os dois falem mais, **ou** de rótulos humanos |
| DER no regime Discord | **POR MEDIR** — exige truth de uma pessoa | **sim** |
| como o painel **mostra** a voz | **POR DECIDIR** — `panel.js` tem **zero** ocorrências de `speaker` para pintar; a `source` só vai para `line.dataset.source` (`panel.js:1061`), nunca para texto | **sim** (design) |
| nomes (`speaker-1` → "o Rui") | **POR DECIDIR**; quando existirem têm de ser **só de exibição** — renomear não pode mover linhas | **sim** |

### A lacuna de produto que fica escrita

Com `--speakers` ligado, duas pessoas dão **duas linhas** — que é o pedido. Mas o
painel **não pinta nome nenhum**: `grep -n speaker app/panel/panel.js` devolve
**uma** ocorrência, e é uma string de estado (`:3282`). A `source` vai para
`line.dataset.source` e nunca é pintada. Ou seja: hoje o dono vê duas linhas de
texto e **nada que diga quem falou o quê**. A exibição é uma decisão de design
dele, e por isso não foi inventada aqui.
---

## 9. PESQUISA: O EXEMPLO OFICIAL DO SHERPA-ONNX (2026-10-18, depois desta medição)

Fonte primária, obtida por `web_fetch` (a pesquisa `web_search` falhou três vezes
com `MATRIX_TOOL_REQUEST_FAILED`):

- <https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-speaker-diarization.py>
- <https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/python.html>

Verbatim da docstring oficial de `init_speaker_diarization`:

> **cluster_threshold**: If num_speakers is -1, then this threshold is used for
> clustering. **A smaller cluster_threshold leads to more clusters, i.e., more
> speakers. A larger cluster_threshold leads to fewer clusters, i.e., fewer
> speakers.**

### A MINHA HIPOTESE ESTAVA ERRADA, E A DOCUMENTACAO CORRIGIU-A

Eu tinha escrito que `--threshold 0.9` era "1,8× mais estrito" que a omissão
(0,5) e que por isso causava a sobre-divisão. **Está ao contrário pela regra
documentada:** threshold maior → MENOS clusters. O `--threshold 0.9` está
correcto.

Varrimento medido (`_main/_diar-threshold-sweep.py`, modelo carregado uma vez,
`call.wav` = 60 s densos, verdade-terra = 2 vozes):

| threshold | vozes | delta |
|---|---|---|
| 0,50 (omissão da biblioteca) | 3 | **+1** |
| 0,70 | 2 | 0 |
| **0,90 (o que o sidecar corre)** | **2** | **0** |

Ou seja: a omissão da biblioteca **parte uma pessoa em dois** neste áudio. O
nosso 0,9 está certo, e a medição prova-o. **Não se mexer no `--threshold`.**

### O que o exemplo oficial faz, e nós não

O exemplo fixa `num_speakers=4` quando sabe quantas pessoas são
(`sd = init_speaker_diarization(num_speakers=4)`). É exactamente o que
`--num-speakers 2` fez aqui:

| | auto (`-1`) | fixado (`2`) |
|---|---|---|
| janelas que veem **as duas** vozes | 2 de 5 | **5 de 5** |
| frames da voz minoritária | 3 (1 par) | **8 (2 pares)** |
| cMAP da voz minoritária | 100 % (3 fr) | 100 % (8 fr) |

O exemplo oficial também passa `window_shift_ratio=0.1` ao sub-config pyannote.
**A nossa versão não aceita esse argumento**: sherpa-onnx **1.13.4** tem a
assinatura `(model: str)` apenas, e `window_shift_ratio` só chegou ao master
depois desta release. Está escrito em `_load_sherpa_diarizer` e continua verdade.

---

## 10. O BUG REAL QUE A MEDIÇÃO DE 3 MIN DESCUBRIU

`call180.wav` (180 s, mesma call, mais tarde) tem **21,2 s de fala em 180 s
(12 %)**. Com a **mesma** configuração que deu 2 vozes nos 60 s densos, devolveu
**6 vozes para 2 pessoas** (15 segmentos, mediana de turno **1,52 s**, contra
**2,36 s** nos densos). Sete das dezassete janelas devolveram **zero segmentos**
(`No speakers found in the audio samples`).

Não é o threshold (acima). É a **fala esparsa**: turnos curtos e isolados dão
poucos embeddings, e poucos embeddings são ruidosos, e embeddings ruidosos
partem-se em mais clusters.

Isto importa porque **cada cluster vira uma `source` diferente** — ou seja, até
**6 linhas no painel para 2 pessoas**, que é exactamente o que a `source` por voz
existe para impedir.

**Ainda não está corrigido.** A correcção com números é tornar o número de
clusters **estável entre janelas** em vez de o deixar ser decidido de novo em
cada uma; e o braço `--num-speakers 2` medido é a prova de que isso funciona.
---

## 11. O BUG VERDADEIRO (o que a §10 supunha) E A CORRECCAO

### O que eu supus, e por que estava errado

Eu escrevi que o bug era "6 clusters para 2 pessoas" e que a correccao era
estabilizar o numero de clusters. **O numero nunca foi o problema.** Medi a
etiqueta **CRUA** — a que e' realmente publicada, sem alinhamento — contra o
cMAP, que alinha:

| audio | CRU (o que o painel via) | cMAP (alinhado) |
|---|---|---|
| 60 s densos, auto | **70,2 %** | 87,7 % |
| 180 s esparso | **93,8 %** | 100,0 % |
| 60 s, `num_clusters=2` | **68,4 %** | 89,5 % |

Pares Responsible: `1->2` cru 25,0 % / cMAP 75,0 %; `15->16` cru **0,0 %** /
cMAP 100,0 % com mapa `{0:1, 1:0}` — uma inversao total.

**Fixar `num_speakers` piorou o numero cru** (68,4 % contra 70,2 %). A contagem
nao era o defeito; a **NUMERACAO** era.

`tick` publicava o numero local do diarizador. `source` e' a chave da linha no
painel (`panel.js:386` `rowIdentity`). Publicar o numero cru significa que **as
legendas de UMA pessoa saltam entre duas linhas de 10 em 10 segundos** — que e'
exactamente o que a `source` por voz existe para impedir.

### Porque o `cmap` nunca viu isto

Porque o `cmap` **alinha** os dois conjuntos de etiquetas antes de pontuar: os
rotulos sao arbitrarios, e sem alinhar leria "mudou o numero" como "mudou a
pessoa". Esse alinhamento e' **exactamente o que esconde o defeito**. A metrica
era cega **por construcao**. E' a forma mais afiada da regra que este repo repete:
*uma guarda que o design torna equivalente nao pode ser apanhada por uma
medicao construida sobre esse mesmo design.*

### A correccao

`worker/speaker_sidecar.py` — nova classe `StableSpeakerSlots` + os segmentos
publicados por `tick` passam por ela. Cada etiqueta local de uma janela e'
casada com o **slot global que partilha mais tempo falado** com ela; slots que
não falam há mais de `horizon_s` (60 s) são **podados ANTES do casamento**.

Três decisões dentro disso, todas por medição:

- **Casar por TEMPO FALADO partilhado**, não por número nem por ordem. Medido:
  casar por ordem de entrada dá o mesmo resultado em 4 permutações (arm 4 do
  portão).
- **Podar ANTES de casar.** A primeira versão podava depois, o que tornava o
  horizonte uma promessa vazia: um slot calado há mais de `horizon_s` ainda
  podia ganhar o casamento. O braço que exigia o contrário era impossível de
  satisfazer — apanhou-me.
- **`local_speaker` viaja ao lado de `speaker`.** Sem ele, um bug de remapeamento
  é invisível no payload published.

Replay das janelas **reais** da call, antes vs depois:

| audio | CRU antes | **CRU depois** |
|---|---|---|
| 60 s densos | 70,2 % | **87,7 %** |
| 180 s esparso | 93,8 % | **100,0 %** |
| 60 s, `num_clusters=2` | 68,4 % | **89,5 %** |

Slots globais usados no ficheiro denso: **2** (que é o número certo de pessoas).

**O que a correcção NÃO resolve**, dito com todas as letras: o resíduo de
87,7 % não é numeração. É o diarizador mudar de ideias sobre quem fala na
fronteira entre turnos — e nenhuma camada de renomeação conserta isso, porque
não é um problema de nome.

### Porta nova

`_main/speaker-slots-oracle.py` — **15/15** arms, e o `--neg-arm` (uma cópia que
deixa passar o número local, ou seja, **o código de antes da correcção**) vai a
**RED em 5 arms**, incluindo *"a renumeracao 0->1 devolve o MESMO slot global"*.

`tick(slots=None)` fica **byte-idêntico** ao comportamento antigo — verificado
por arm. `--no-stable-slots` devolve o comportamento anterior e imprime um
aviso.

### Correcção colateral: o retry do `os.replace` era demasiado curto

`_replace_with_retry` com `attempts=8, delay_s=0.02` (~160 ms) deu
**`lost=1 of 150`** — um RED verdadeiro na arm *"the writer lost zero publishes
on Windows"*. As duas corridas seguintes deram `lost=0 of 150`. Um portão que é
verde quase sempre não é um portão em que se possa confiar no dia em que importa,
e a reparação não é re-correr até ficar verde: é **40 × 25 ms (~1,0 s)**, um
bloqueio na publicação e não na transcrição, contra publicar nada.

### Bateria depois da correcção (tudo RC=0)

```
speaker-slots-oracle            VERDICT: PASS  arms 15/15
speaker-slots-oracle --neg-arm  VERDICT: PASS  (RED em 5 arms)
speaker-sidecar-oracle          VERDICT: PASS  arms 34/34  mutants 6/6
speaker-id-oracle               VERDICT: PASS  arms 79/79  mutants 13/13
speaker-plumbing-oracle         VERDICT: PASS  arms 39/39  mutants 6/6
caption-lines-oracle            12 PASS / 0 FAIL
per-app-source-plumbing-oracle  VERDICT: PASS
sidecar --selftest              VERDICT: PASS
sidecar --capture-selftest      VERDICT: PASS
panel-two-voices --neg-arm      VERDICT: PASS
```

`worker/speaker_sidecar.py`: 29 288 B → **36 555 B**, **0 CRLF / 806 bare LF** (LF
preservado), sha256 `4E1AD9E7CB939B50F6EF855781D80027D6D598521D72EA1F8C31EE1900B4191E`.
---

## 12. A VOZ FEZ-SE VISIVEL (a lacuna que o dono pointed, 2026-10-18 17:36)

O dono: *"ainda estou em chamada no discord. ja conseguiu separar as vozes?"* —
e depois, ao ver o estado: *"acho que tu precisa pesquisar... e continua"*.

O que faltava **não** era medição. Era **exibição**: `grep -n speaker
app/panel/panel.js` devolvia **uma** ocorrência, uma string de estado. A `source`
por voz chegava ao painel como `data-source` e nunca era pintada. Duas pessoas
davam duas linhas de texto e **nada que dissesse quem falou o quê**. Uma
funcionalidade que não se vê não está acabada.

### Decisões, todas minhas (o dono mandou: *"tu nao vai depender mais de mim ou do
meu verde"*)

1. **PONTO COLORIDO, ZERO TEXTO NOVO.** O dono tirou um número visível duas vezes,
   *"nao e' pra ter mais ele"*, pelo mesmo elemento em todas as linhas. Um nome é
   decisão de design que ele não tomou. O ponto diz a frase inteira — "estas duas
   linhas são a mesma pessoa, estas outras não" — sem pôr mais uma string à frente
   de uma legenda. A identidade fica na linha como `data-voice` para o que ele
   quiser fazer dela.
2. **TOM DO ÂNGULO DOURADO** sobre o número do slot: duas vozes nunca caem na
   mesma cor, e a cor não muda entre janelas — que é o que a torna legível.
3. **`source` CONTINUA SENDO UMA CHAVE OPACA.** `voiceFromSource` só lê a string;
   nada do que devolve entra em `rowIdentity`, `committedByStart` ou
   `retireProvisional`. Se o tom fosse a chave, renomear uma voz moveria linhas —
   exactamente a falha que a chave opaca existe para impedir. Gateado.

`worker/speaker_sidecar.py` não mudou por isto. `app/panel/panel.js` +
`app/panel/panel.css` sim, e ambos com CRLF/LF preservados.

### O caminho que faltava, e o braço que o apanhou

A primeira versão pintava o ponto **só no commit**. A sonda mostrou:

```
li | class="caption caption--provisional" | data-source=device:X/voice:speaker-1
   | data-voice=undefined | dots=0
```

**A linha que o dono está a ver enquanto a frase forma é a provisional.** O
`applyVoice` foi também posto em `renderProvisional` (`panel.js`, depois do bloco
de criacao), idempotente. Re-sonda: `data-voice=speaker-1 | dots=1`.

### Porta nova: `_main/panel-voice-dot-oracle.js` — 18/18, mutante RED

O `--neg-arm` usa um mutante **fiel**: `rowIdentity` que esquece a metade do
dispositivo e fica so com o numero da voz. Duas linhas de dois apps com o mesmo
`speaker-1` colapsam numa so. **RED em 2 arms.**

**Dois mutantes INERTES que eu perdi antes de o portao ficar honesto** — e sao a
mesma licao da 3a vez nesta sessao:

| mutante inerte | porque | custo |
|---|---|---|
| vaza o TOM na chave | cada linha ja tem `source` unico; somar mais um termo unico a uma chave unica **nao muda nada** | 30 arms verdes com o painel partido |
| exercita so o provisional | as linhas provisional sao chaveadas pelo Map `provisionalRows` no `source` cru, **nunca** pelo `rowIdentity` | o mutente da chave nao podia aparecer |

O que os dois obrigaram a fazer: exercitar tambem o **caminho de commit**, que e'
onde `rowIdentity` corre. Um `bridge.onStatus({text, kind})` faz o flush de todos
os engines (`panel.js:3076`) e fecha as linhas. So ai o mutante foi RED.

### As quebras MINHAS de esperanca (nenhuma era bug do painel)

| o que eu esperava | o que e' verdade | quem me corrigiu |
|---|---|---|
| `data-start` = `"10"`/`"11"` na linha de voz | linhas **provisional** nao tem `data-start`; e' estampado no commit | o proprio arm, a RED |
| `data-start` = `"50"` depois do commit | o commit usa o `start` do **primeiro** segmento da fonte, nao do ultimo | a sonda do DOM |
| `emit({text, meta})` minimo | o painel precisa de `chunk_start` + `closed`; `meta.final` sozinho **nao** commita | o oratorio existente, que ja o escrevera |
| regex "nao casa" | casava — o **PowerShell** comera o `$` no teste inline | teste num ficheiro |

Um arm que falha pela razao errada e como um defeito a serio passa por "instavel".
---

## 13. "PORQUE NAO 8?" — o 8 ERA O BUG, E A PESQUISA DIZ COMO SE FAZ DE FACTO

### O 8

`_main/_sidecar-replay-real.py` empurra os 60 s **reais** da call pelo
`RingBuffer` REAL, com a cadencia REAL, pelo `tick` REAL, com o modelo REAL — e
le o payload REALMENTE publicado. Resultado com as slots ligadas:

```
#  estado    seg   slots na janela        mapa local->global
0  written   2     [1]                    {'1': 1}
1  written   4     [1]                    {'0': 1}      <- slot NOVO
2  written   3     [1]                    {'0': 1}      <- slot NOVO
3  written   6     [1, 2]                 {'0': 2, '1': 1}   <- slot NOVO
4  written   8     [1, 2]                 {'0': 2, '1': 1}
5  written   6     [2]                    {'0': 2}

linhas que o painel faria com este audio: 8
```

**Oito linhas para duas pessoas.** A causa foi apanhada a ler o `tick`:
`slots.remap(..., now=payload["written_at"])`, e `written_at` e'
`time.time()`. Os segmentos, ao contrario, sao absolutos no **relogio da captura**.
Basta os dois relogios divergirem mais que `horizon_s` — e divergem sempre que o
audio nao e' o audio vivo — para que **todo** slot fique mais velho que o corte,
seja podado ANTES do casamento, e nada case. Nova pessoa a cada 10 s, sempre.

Correccao: `now` passou a ser o **fim da janela no relogio da captura**
(`window_start + window_s`), que e' a unica coisa que significa o mesmo que os
intervalos com que e' comparada. Replay depois da correccao:

```
0..5  slots por janela: [1] [1] [1] [1,2] [1,2] [2]
linhas que o painel faria: 2   (slots [1, 2])
```

**Este e' o primeiro caso de cadeia completa com modelo real em todo o
trabalho.** Cada perna anterior tinha um diarizador falso algures, e um
diarizador falso e' ESTAVEL por construcao — que e' precisamente a propriedade
que o defeito ataca.

### A PESQUISA: como se faz de facto

Fonte primaria, <https://github.com/pyannote/pyannote-audio> (README, lido hoje) e
a referencia therein: *"pyannote.audio 2.1 speaker diarization pipeline:
principle, benchmark, and recipe"* (Bredin, INTERSPEECH 2023).

O pyannote **nao** casa janelas por tempo. A arquitectura e':

1. segmentar a fala com a rede de segmentacao (a mesma familia pyannote que o
   sherpa embala);
2. extrair **embeddings** por segmento;
3. **clustering LOCAL** dentro de cada janela deslizante;
4. **CLUSTERING GLOBAL AGLOMERATIVO sobre os CENTROIDES** dos clusters locais
   — e' este passo que segura a identidade ao longo do ficheiro;
5. permutar os rotulos para os tornar monotonicos.

A correccao actual casa por **tempo falado partilhado**. E' mais barata (nao
guarda embeddings) e esta medida a funcionar (cru 70,2 % -> 87,7 %), mas e'
**estruturalmente mais fraca**: so casa o que se sobrepoe, e nao funde duas slots
que o diarizador partiu. O passo 4 e' o que falta.

O sherpa tem as pecas todas, confirmadas na versao instalada (1.13.4):
`SpeakerEmbeddingExtractor.create_stream()` / `accept_waveform` /
`compute(stream) -> 1-D float32`, e `FastClustering`, que e' o aglomerativo.

**O que falta antes de escrever o passo 4 e' um limiar de coseno medido, nao
chutado.** `_main/_slot-cosine-distribution.py` existe para isso e nao produz
limiar nenhum: produz a distribuicao.
---

## 14. A VIA "CORRECTA" (pyannote) FOI MEDIDA E REJEITADA — COM NUMEROS

O passo 4 da arquitectura pyannote e' **clustering global aglomerativo sobre os
centROIDES dos clusters locais**. O sherpa tem as pecas (confirmadas na 1.13.4
instalada): `SpeakerEmbeddingExtractor.create_stream()`,
`accept_waveform(sample_rate, waveform)`, `compute(stream) -> 1-D float32`, e
`FastClustering`, que e' o aglomerativo.

Antes de escrever esse passo, a unica coisa que faltava era o **limiar de
coseno**, e nenhum documento do fornecedor o diz. `_main/_slot-cosine-distribution.py`
mediu-o na audio real da call.

### [A] Nos centroides

```
voz 0: 12 segmentos, 12 embeddings
voz 1:  3 segmentos,  3 embeddings
cos(voz0, voz1) = +0.613          <- DUAS PESSOAS DIFERENTES
```

E, dentro de janelas, a MESMA pessoa partida em dois clusters:

```
coseno local x local, janela 20..40  = +0.697
coseno local x local, janela 30..50  = +0.578
```

**+0.578 (mesma pessoa) e +0.613 (pessoas diferentes). O mesmo numero que o
diferente esta acima do que o igual.**

### [C] Ao nivel do segmento, sem nenhum atalho de centroide

```
MESMA pessoa      : n=69   min +0.038   max +0.808   mediana +0.477
PESSOAS DIFERENTES: n=36   min -0.014   max +0.628   mediana +0.292
```

Folga `min(mesma) - max(diferente) = -0,589`. **NEGATIVA.** Os intervalos
sobrepoem-se quase por inteiro: uma voz sobe a +0.808 e outra desce a +0.038.

### DECISAO

**Nao ha limiar de coseno que funcione neste audio com este modelo.** O
clustering global do pyannote por similaridade e' uma via **medida como
impraticavel aqui**, e nao vai ser escrita.

A correccao por **tempo falado partilhado** entre janelas — mais barata, sem
embeddings — **fica**, e os seus numeros sao melhores do que seria o do outro
metodo: cru 70,2 % -> 87,7 %. Nao e' uma versao mais pobre da via "correcta" nesta
caixa; pode ser a unica que funciona.

O que NAO consigo separar com esta medicao, e fica dito: se a sobreposicao vem
de a segunda voz falar pouco (3 segmentos, ~1,5 s) ou do audio de call ser
comprimido e de banda estreita. As duas hypotheses precisam de dados diferentes
para as separar, e nenhuma delas muda a decisao de hoje.

### E uma mentira minha que ficou no caminho

A primeira versao do script imprimia, para estes numeros:

```
limiar viavel: qualquer valor em (0.628, 0.038) -- e' esse o unico
```

`max(diferente) = 0,628 > min(mesma) = 0,038`: o intervalo esta **VAZIO**, e
apresentado como opcao. Um numero que se le como caminho quando nao e' caminho e'
pior do que nao imprimir nada. Corrigido: o script agora diz **NAO SEPARA** e
explica que o intervalo e' vazio.

### API do sherpa, segunda vez

`OnlineStream.accept_waveform` quer **`(sample_rate, waveform)`** — a taxa
PRIMEIRO. Chamar com a waveform sozinha levanta
`TypeError: incompatible function arguments` e imprime a assinatura. Mesma
classe de erro da config do diarizador: a assinatura pybind, nao a intuicao de
Python.
---

## 15. A LIGACAO AO ARRANQUE — E O DONO CORRIGE O DESENHO

### O que estava em falta

A feature era provada de ponta a ponta e **inalcancavel**: `run.cmd` arranca a
shell, a shell arranca o worker, e ninguem arrancava o sidecar. So havia de
comando a mao.

`worker/sotto_worker.py --speakers` existe; `sotto_webview.py` nao conhecia a
flag (`grep -n speakers` dava **zero**).

### O que foi feito

* `app/webview/sotto_webview.py`: flag `--speakers`; classe **`SpeakerSidecar`**
  (processo proprio, `CREATE_NO_WINDOW` + `BELOW_NORMAL_PRIORITY_CLASS`, recusa
  alto se o ficheiro faltar, `stop()` idempotente); `WorkerBridge` aceita
  `extra_args`, e o argv passa a ser `[command, path] + extra_args` — com
  omissao **vazia**, ou seja, todo o bridge existente spawna exactamente o argv
  de sempre.
* O sidecar arranca **depois** de `if started:` — um worker recusado nao deixa
  277 MB a correr contra ninguem — e morre com a **shell**, nao com o worker: o
  worker reinicia-se sozinho (medido: 88 mortes em 17 min) e matar o diarizador
  a cada reinicio seria o churn que o donoixa.
* **`--speakers` vai em argv, nunca em ambiente.** `_main/app-target-oracle.py`
  ARM e segura "o ambiente e' o de antes mais o que a shell ja acrescentava", e
  meter uma chave nova partia esse arm. Passou: `VERDICT: PASS`.

`_main/sidecar-wiring-oracle.py` — **22/22**, e o `--neg-arm` **executa** o
mutante (uma copia da shell sem `BELOW_NORMAL_PRIORITY_CLASS`) e ve-lo cair.

**O arm "a flag chega ao WORKER por ARGV" foi a RED e encontrou um bug real:** a
shell arrancava o sidecar com `--speakers` e nunca o passava ao worker, que e'
quem o consome. Um diarizador de 207 MB a correr e uma bridge sem o flag que le
o ficheiro dele: o pior dos dois mundos. Corrigido.

### O DONO CORRIGE O DESENHO, E A MEDICA CONFIRMA-LO

*"se em tempo real for pesado pro usuario separar as vozes, devemos fazer isso
depois apenas. mas precisamos detectar que sao multiplas vozes, para decidir isso
pra processar depois quando e seguro e nao travar o pc do usuario."*

**O custo medido.** RSS do sidecar com o modelo real, amos-trado de 8 s a 73 s:

```
t=8s 115 MB ... t=38s 206 MB ... t=48..68s 207 MB (regime) ... saida 67 MB
```

**207 MB em regime**, e ~1,5 nucleos para acompanhar o audio em tempo real. Os
pesos sao muito menores: segmentacao **5,7 MB**, embeddings **37,8 MB**. Os 207 MB
sao runtime, nao pesos. O instinto do dono e' o certo.

**Onde esta o desperdicio.** Com janela de 20 s e passo de 10 s, cada segundo de
audio e' diarizado **duas vezes** (a sobreposicao). E medido que essa
sobreposicao **nao e' desperdicio — e' o que sustenta a identidade**:

| cadencia | slots para 2 pessoas |
|---|---|
| passo 10 s (sobreposicao de 10 s) | **2** — certo |
| passo 20 s (sem sobreposicao) | **4** — duas pessoas viram quatro linhas |

E' o eixo exacto da decisao do dono: **a identidade precisa da sobreposicao; a
sobreposicao e' o que custa.**

**E' aqui que as duas fases encaixam com_precision.** A Fase A nao pergunta
"quem e' quem" — pergunta **"houve duas vozes ao mesmo tempo?"**. E o modelo de
segmentacao responde a isso **sem embeddings e sem clustering**, e a saida
avisa-o: o `model.onnx` devolve `y` de forma `[N, frames, 7]` — as 7 clases
*powerset* do pyannote, que codificam ate 3 falantes simultaneos.

Ou seja: **a pergunta barata nao precisa de identidade, logo nao precisa da
sobreposicao, logo e' barata.** A Fase B (identidade) precisa da sobreposicao, e
por isso corre depois, quando for seguro. O desenho do dono e' o unico que
resolve as duas restricoes ao mesmo tempo.

**O custo de construir a Fase A, medido na API:** sherpa-onnx **1.13.4 nao
expõe a segmentacao isolada**. There is only `OfflineSpeakerDiarization`, que
exige a config de embeddings; e so `FeatureExtractorConfig` esta exportada, sem
a classe de extracao. Para correr o modelo sozinho via `onnxruntime` seria
preciso reimplementar o fbank do Kaldi (80 dim, 25/10 ms) e arriscar divergir
dos numeros que a pipeline produz. Isso e' trabalho real, com o seu proprio
portao de equivalencia — e nao foi feito a Hidden para nao parecer fait.