# O que o Sotto é, o que eu assumi errado, e o estado dos teus 47 prompts

*Dono, 2026-10-19 15:5x. Reescrevi a resposta anterior: ela partia de uma
premissa errada (a de "dar nome às vozes"), e por isso respondia à pergunta
errada.*

---

## 1. O que o Sotto é (com as tuas palavras, não com as minhas)

O `AGENTS.md` tem a tua aceitação, verbatim:

> *"e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer
> audio do meu pc. e legendas."*

Ou seja: **o Sotto é uma legenda ao vivo, de qualquer áudio do PC, num overlay
global, com Alt+C.** Nada mais. Não é uma ferramenta de dublagem, não é um
rastreador de falantes, não tem pessoas dentro.

## 2. O que eu assumi errado — e era uma merda, sim

**Assumi que o Sotto tinha "nomes de voz"**, e a partir daí construí metade
da minha framing: os "nomes" como decisão tua, o "quem falava quando" como
truth humana, o DER como métrica de aceitação.

**De onde veio:** o design do painel mostrava linhas com falantes, e eu li
isso como "o produto tem pessoas". Não tem. Tu disseste-o agora, e tens
razão: **é só separar o áudio para transcrever cada falante em separado.** O
que interessa é que a legenda saia certa — não é a etiqueta.

**O que fiz com isso:** está tudo no meu arquivo de resposta anterior e no
recibo. Vou **corrigir o texto** para que nenhuma lane e nenhum agente
herde a premissa errada. E sai da lista de decisões: **ninguuma decisão tua
passa a ser "dar nome a ninguém"**.

## 3. "DER" — o que era, e porque não devia ter-te dito isso

DER = *Diarization Error Rate*: uma métrica padrão de diarização, a fração de
tempo em que a atribuição de falantes está errada. Saiu do meu jargão de
engenharia e não te serve de nada.

**O que interessa, em português:** o modelo achou as vozes certas? A legenda
saiu certa? Em vez de um DER, o número que te interessa é **"a legenda ao
vivo está certa?"** — e isso mede-se vendo a legenda, não num índice de erro
de diarização.

## 4. "Qual é a Fase B?" — e onde entra o clone do ShadowPlay

**Fase A** (o que fiz): *detetar* que há duas vozes ao mesmo tempo, em tempo
real, barato, sobre a onda crua. Só para **decidir** se vale a pena separar.

**Fase B** (o que fiz): *separar* mesmo — as duas vozes em streams separados —
**offline/depois**, com um modelo leve, para não pesar no teu PC enquanto
transcreve. É a tua ideia de 2026-10-18, verbatim: *"se em tempo real for
pesado pro usuario separar as vozes, devemos fazer isso depois apenas. mas
preciamos detectar que sao multiplas vozes, pra decidir isso pra processar
depois quando e seguro e nao travar o pc do usuario."* ✓

**E o clone do NVIDIA ShadowPlay é OUTRO PRODUTO** — `app/shadowplay/`, com
15 suites de teste próprias: captura D3D11→NVENC, replay ring, clip writer,
hotkeys, áudio, e **`captions.js` + `broadcast.js`**, que são a junção: as
legendas do Sotto entram no clip gravado (sidecar de captions por clip).

**Erro meu:** eu tratei a Fase B como "o Sotto acaba aqui" e nunca te disse
que a junção com o ShadowPlay é o outro lado da moeda. A pergunta que tens
feito e que eu não respondi: **o que é que eu próprio tenho de entregar para
que a junção exista?** E é a lista de baixo.

---

## 5. Os teus 47 prompts — o estado honesto

Extraí-os do histórico (47 mensagens, de 2026-10-17 a hoje) e classifiquei
cada um. **Contei, não estimei.**

### Feitos e medidos

| # | prompt | como sei que está feito |
|---|---|---|
| 1, 8–11 | CPU dos subagents, matar processos indesejados, parar de spawnar | censo de janela a 60 s; 0 processos do Sotto agora |
| 6 | goal para o Sotto | goal activo, com o objectivo por escrito |
| 7, 15, 44 | separar áudio de pessoas no Discord: modelo vs engenharia, e em duas fases | Fase A + Fase B construídas, com portões |
| 13, 31, 34, 35 | Alt+C / duplo / triplo, esconder o painel, palavra-por-palavra (não letra) | documentados e portados no `AGENTS.md` |
| 16, 26, 27, 32, 33 | bugs de legenda, travamento ao ativar, ícone do YouTube, "2" do nada, cortar palavras | corrigidos e com portão |
| 17–19, 38 | a GPU/CPU a 100% | **guarda de carga** + medição (nunca mais) |
| 21 | áudio guardado até processar, depois apagado; modelo leve em tempo real; **nemotron não** | retenção FIFO + guarda; o "modelo bom" (Redux) reescreve a linha do nemotron |
| 28 | "arruma TODOS OS DESIGNS" | gerador de temas com o scope corrigido; 8 folhas, zero fuga |
| 37 | "não é pra ter o modelo no repo do GitHub" | `worker/models/` ignorado; nunca versionado |
| 45, 46 | full audit + **um** subagent | auditoria entregue (o subagent encontrou o pipe sem leitor e os mutantes decorativos) |
| 47 | as cinco perguntas | esta resposta |

### Feitos, mas **não te disse** (erro de comunicação, não de trabalho)

| # | prompt | a resposta existe |
|---|---|---|
| **43** | *"2 slots para 2 pessoas (era 8), por que não 8? pesquisa como fazer"* | **Está medido, no código**: com `--num-speakers 2` o modelo dá **12 slots** (3,7× mais lento); com `--min-on 2,0 s` dá 4 slots mas **deita fora 58 % da fala**. O horizonte (`StableSpeakerSlots`, 60 s) casa por **tempo falado**, não por similaridade — por isso 2 chamadas curtas são 2 pessoas, e 8 slots era o bug do horizonte (8 slots para 2 pessoas). **8 slots é o sintoma, não o objectivo.** |
| 30 | legenda ao vivo com maiúsculas e estrutura de frase | a formulação da legenda (`caption-formulation.js`) e a troca letra-a-letra do S4 |
| 14 | tamanho da legenda, como o YouTube quebra a linha | a janela própria da legenda, com o `zip-overlay.css` |
| 36 (metade) | *"índice de que pesa 4 GB? faz full audit"* | censo: **`_main` = 3,6 GB** (modelos de diarização: mossformer2 670 MB, sherpa, UVR), `_moved` 2,6 GB, `worker` 1,2 GB (os pesos), `app` 795 MB, `.git` 10,7 MB. O "índice" são **artefactos e pesos**, não o histórico |
| 5 | "são simplesmente dots, não texto" | o painel passou a dizer o que está a fazer |

### **NÃO feitos** — e aqui é que está a culpa

| # | prompt | onde está |
|---|---|---|
| **22–25** | o **!watcher** no disco I: — "faz o watcher fazer o trabalho dele. e sempre iniciar com o windows" | é **outro projeto**, no disco I:, não neste repo. Tenho de ir lá ver o estado |
| 42 | *"me fala se tu usou [a pasta rea] ou não e porquê"* | resposta a dar: **não usei** — e porquê |
| 29 | a busca tem de ser "extremamente inteligente" | por confirmar |
| 20 | "por que eu fico sem áudio de tempos em tempos?" (o headphone a desconectar) | por confirmar |

> **Actualizado 17:0x — o #36/#40/#41 passou de "não feito" a "corrido e medido".**
> Ver a secção 7. A demo nunca tinha corrido; hoje correu.

---

## 6. O que estou a fazer AGORA, por esta ordem

1. **Esta resposta no teu VS Code** (já aberta).
2. **Ir ao disco I: ao !watcher** — ver o estado dele, porque me pediste para
   o fazer funcionar e para arrancar com o Windows, e isso não é deste repo.
3. **Responder ao #42** — a pasta `rea`: usei-a ou não, e porquê.
4. **Confirmar #29, #20 e #5** — os três que ficaram em aberto.

**E o que NÃO vou fazer:** voltar a abrir o "Sotto inteiro" sem linha de
chegada. A lista de restos acima é a linha de chegada, e é curta.

---

## 7. O que aconteceu depois desta resposta (16:5x — 17:4x)

Três coisas, e as três são tuas.

### 7.1 A DEMO — a legenda ao viva, com a cadeia inteira

O teu pedido mais antigo por responder era *"mostra pra mim a legenda ao vivo …
de forma natural, encaixa no sotto"*. **O script existia e nunca tinha
corrido.** Correu hoje:

| | |
|---|---|
| fonte | o teu `pt-br-sample.wav`, render para **"CABLE Input"** (o cabo virtual) |
| saiu som nos teus altifalantes? | **Não** — o recibo regista `render_is_system_default: false` |
| worker | modelo `nemotron-3.5-asr-ptbr-onnx-int4`, carregado em 11,6 s |
| dispositivo que o worker tapsou | `WASAPI loopback: CABLE Input`, **tentativa 1 de 12** |
| **legendas** | **177** em **152 s** |

A legenda cresceu linha a linha, como deve ser: `'segunda'` → `'segunda os os
moradores'` → `'… precisam de um caminho alternativo'` → `'… para chegar ao
trabalho'`.

**O que isto prova:** a cadeia inteira funciona nesta máquina — áudio real →
cabo → worker → transcrição em português → JSONL, que é exactamente o que o
overlay consome. **O que não prova:** que a legenda *pintada* no teu ecrã é
correcta — isso exige a app aberta, e estavas em chamada.

### 7.2 A tua ordem n.º 1 — *"muta o audio de teste"*

Fiz isto: `_main/mute-audio.py` (pycaw), com um portão de **21/21 arms e
8/8 mutantes** e um `--neg-arm` que dá vermelho por desenho.

**Medido:** o default de saída do teu PC é **"VoiceMeeter Input"**; o mute
põe o volume a 0 e o unmute repõe **exactamente** o valor guardado (o
round-trip é quantizado a float32, portanto repõe-se o valor *lido*, nunca o
escrito). O teu volume está em **1,0** e o estado é `unmuted` depois de cada
corrida.

**Continua por medir, e digo-to:** que o mute tape *todos* os caminhos até aos
teus ouvidos. Em 07/10 medi-se som real na sala (mic 0,24–0,77) por um caminho
que não identifiquei. Medir isso exige renderizar áudio. Esse pendency fica
**aberto** — não o vou declarar fechado.

### 7.3 A tua ordem n.º 2 — *"as legendas do youtube substituem a ao vivo"*

**Primeiro, o que já existia e tu não sabias:** a substituição **funciona**,
e está no log da tua app:

```
EXTERNAL_CAPTION_SENT count=1 source=external:youtube final=false text="1,9 mil"
EXTERNAL_CAPTIONS_WORKER_PARKED source=external:youtube pid=40208
BRIDGE_STOP reason=external-captions pid=40208
```

O worker de ASR é **parado** e a linha do YouTube ocupa a caixa. Não é uma
sobreposição — é uma substituição.

**Segundo, o defeito:** o que chegava à caixa era muitas vezes **chrome do
YouTube**. Censo das **220 linhas externas reais** do teu log: **17 de 21**
(17/10) e **9 de 199** (18/10) eram chrome — o contador de views (`"1,9 mil"`,
`"15 mil há 8 h"`), a idade do vídeo (`"há 1 dia"`), um handle de chat
(`"@zachw2906"`), um separador (`"·"`) e números soltos (`"344"`, `"2"`).

**A causa era dupla:** os filtros viam **uma palavra de cada vez** (um contador
partido pelo YouTube em `"1,9"` + `" mil"` era invisível), e o gate temporal
**não pode** apanhar um contador — um contador de views fica quieto durante
minutos e ganha streak como uma legenda.

**A correcção** (`app/webview/external_subs.py`): as regras passam a ser
julgadas **na linha já unida** e **ancoradas à linha inteira**, para não comer
uma legenda real. **Depois: 26 chrome apanhados, 194 legendas sobrevivem,
nenhuma legenda real comida.**

**E dois portões novos, agora na bateria:** um conduz o `caption_lines` real
contra polls sintéticos (6 formas de chrome → **0** linhas; a legenda real
sobrevive ao lado do chrome; sem a regra, **17** linhas de chrome chegam à
saída), e o outro mede as 220 linhas do teu log (sem a regra, os sobreviventes
sobem de 194 para **220**).

### 7.4 E uma coisa que encontrei pelo caminho, que não é tua

A bateria grande (`_main/_audit-verify-all.cmd`) está **vermelha em 8 passos**,
e **não é culpa de hoje**: os ficheiros que esses portões leem estão
inalterados desde o último commit, e o `verdict-gate` é de **07/10** — julga
código de 19/10. Já mandei duas lanes resolverem isso. Os **meus** dois portões
novos estão verdes, e a bateria de oradores (24 portões) volta a correr depois
disto.

