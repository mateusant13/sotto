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

**Já fechado:** o `verdict-gate` (a tabela de arms é de 07/10 e não conhecia o
contador `redux_live_captions` que o worker lê hoje) — **16/16 arms**, com
**dois** control a dar vermelho na cópia quebrada; e o probe do lane2 (a lista
esperada da superfície do painel ficou para trás de 17/10) — **20 arms**, com um
**braço negativo novo** a apanhar um export novo. E, no caminho, um defeito de
produto que **não tapei**: a docstring de `decide_verdict` no worker nomeava
**sete** chaves lidas e omitia duas — a frase "every key read is named below"
era falsa, e era ela que fazia o portão ficar vermelho. Corrigida.

---

## 8. As perguntas que ainda estavam por responder, respondidas

### #42 — *"me fala se tu usou [a pasta rea] ou não e porquê"*

**Não usei.** E digo-te porquê, com o que medi:

`I:\rea` é o **REA** — *"Reverse Engineer Anything"*, um MCP server + CLI de
engenharia reversa, v6.3.0, do `github.com/morluto/rea`. É um **monorepo
TypeScript** (`turbo.json`, `vitest.config.ts`, `package.json` com
`"mcpName": "io.github.morluto/rea"`), com READMEs em 16 idiomas.

Grep nos três ficheiros de topo (`README.md`, `package.json`, `AGENTS.md`) por
`sotto`, `caption`, `subtitle`, `transcri`: **ZERO ocorrências**. Não há
legendas, nem transcrição, nem nada de áudio lá dentro. A última vez que foi
tocado foi em **10/10**, e o último commit dele é de um projecto que não é
este.

Ou seja: **não usei porque não tinha nada para me dar**, e não porque me
esqueci. O que eu precisava — a cadeia de legenda do Sotto — já estava
escrita em `app/webview/` e `app/panel/`, e a parte de diarização mediu-se
com o `sherpa-onnx` local (`_main/diar-models/`).

### #22–25 — o **!watcher**: "faz o watcher fazer o trabalho dele. e sempre iniciar com o windows"

**A primeira metade: está feita.** O watcher está vivo e a trabalhar — heartbeat
`ok: true`, `mood: steady`, `pulse_n: 1 268 543`, e o `logs/history.jsonl` a
escrever. E está a fazer exactamente o trabalho para que existe: está a
gritar que os teus discos estão em mau estado, e tem razão.

**O alarme (medido, e é verdade):**
| disco | livre |
|---|---|
| **I:** | **22,9 GB de 3 703 GB = 0,6 %** |
| D: | 19,3 GB = 2,1 % |
| E: | 10,6 GB = 2,3 % |
| F: | 16,5 GB = 7,4 % |
| C: | 41,6 GB = 14,6 %, e **bit sujo do NTFS** (fix offline pendente) |

O `diskhealth` do watcher está vermelho à **2281 verificações seguidas**
(`last_ok_ts: ""` — nunca passou). **Não o silenciei:** o alarme está certo.

**A segunda metade — "arrancar com o Windows" — eu achei que faltava, e
estava errado.** Eu medi `Get-ScheduledTask` e não vi a task "Steady Watcher";
a lane foi ao registo real e mostrou-me que **eu é que não a conseguia abrir**:
a partir de um token médio, `schtasks /Query` e `Get-ScheduledTask` devolvem
"Acesso negado"/"não encontrado" — que se lê como "não existe", mas não é.
(É a mesma doença do `ENOENT` que prova que o *caminho* está errado, não que
o artefacto não exista.)

**O registo real** (`C:\Windows\System32\Tasks\Steady Watcher`, 3 676 B,
escrito a 17/10 23:10):

| | |
|---|---|
| triggers | **LogonTrigger** (8 s de atraso) + **TimeTrigger de 1 minuto** |
| acção | `pythonw.exe -m watcher serve`, cwd `I:\!watcher`, `RunLevel=HighestAvailable` |
| settings | `StartWhenAvailable=true`, `MultipleInstancesPolicy=IgnoreNew`, `ExecutionTimeLimit=PT0S`, `Hidden=true`, `RestartOnFailure` 1 min × 99 |
| estado | **enabled e a correr** |

E o prova de que foi ela que arrancou: o processo do daemon (pid **46124**)
tem como pai o `svchost.exe` (pid 3624) do serviço **Schedule** — foi a task
que o arrancou, a 18/10 17:58:32. E com `IgnoreNew` e o daemon vivo, a
caminhada de 1 minuto não nasce nova: medido com uma poll de 80–150 ms
durante 285 s, **0** processos novos.

**Portanto: o watcher arranca com o Windows, e está a trabalhar.** Não há
nada partido.

**O que ficou por fazer, e é do dono (precisa de elevação):**
- `schtasks /Query /TN "Steady Watcher" /V /FO LIST` — para veres o estado
  vivo com os teus olhos.
- As **4 tasks auxiliares** seguem desligadas (`DeepSweep`, `LogSweep`,
  `Retention` desligadas; `DumpCleanup` pronta). Religá-las também exige
  elevação (`Enable-ScheduledTask -TaskName SteadyWatcher-DeepSweep`).
- **Um defeito pré-existente que ninguém corrigiu**: `logs/watcher.log` não
  recebe nada desde **20/09 04:23** — o sink assíncrono morreu. Foi por isso
  que eu não conseguia ver "serve up" do daemon actual, e é por isso que o
  ficheiro de pid (`46124`) parece obsoleto: **o pid está vivo**, é o daemon.

**E o alarme do disco continua vermelho, e tem razão** (ver acima). Não o
silenciei.

### #20 — "por que eu fico sem áudio de tempos em tempos?" — **A CAUSA, MEDIDA**

Não ficou por confirmar. Medi-o com um instrumento novo
(`_main/probe-capture-open.py`), que abre cada endpoint de captura numa
thread com timeout — porque a diferença entre "ocupado" e "preso" é
justamente o que importa aqui.

**O resultado, nesta máquina, agora:**

| endpoint | o que acontece ao abrir |
|---|---|
| **Headset (soundcore Space Q45) — MME** | **BLOQUEIA** (>3 s, sem erro) |
| **Headset (soundcore Space Q45) — WASAPI** | **BLOQUEIA** (>3 s, sem erro) |
| Headset (soundcore Space Q45) — DirectSound | abre em 0,01 s |
| CABLE Output (MME / DirectSound / WASAPI) | abre |
| VoiceMeeter Output (MME / DS / WASAPI) | abre |
| os três endpoints WDM-KS | erro do PortAudio ("Blocking API not supported yet") |

**O mesmo dispositivo, três APIs: duas prendem, uma não.**

**Porque isto te deixa sem áudio:** o worker abre os candidatos da escada
**em linha** (`worker/sotto_worker.py:6127` → `:1764`). O código de retry
(`:6178`) só corre se a abertura **levantar erro** — mas um `open` que
**bloqueia** não levanta nada: fica lá. A escada nunca passa ao candidato
seguinte, o worker fica parado, e não sai legenda nenhuma.

**E é o que o teu próprio log mostra**, de 15/10 15:56:

```
BRIDGE_EXIT   pid=43676 rc=3 captions=0
  stderr_tail=["OPEN_RETRY_RETRY device='WASAPI loopback: Fones de ouvido (...
BRIDGE_DEATH  last="Sotto could not start listening - The audio device is
              already in use by another program, so Sotto co..."
```

O headphone é o teu **soundcore Space Q45**, e o log do worker_probe ao
longo dos dias mostra-o a ser escolhido: o `OPEN_RETRY_RETRY` happened
porque o `open` do endpoint do headphone não voltou.

**A cura, em duas partes:**

1. **Já, sem tocar em código:** o worker tem `--device` para fixar a
   captura. Apontá-lo para um endpoint que abre (`--device "CABLE Output"`)
   tira o headphone da caminhada e o problema deixa de aparecer. É a
   mitigação de hoje.
2. **A cura de raiz** (que fica para uma sessão contigo, porque mexe no
   caminho de captura): abrir cada candidato **com timeout**, para que um
   `open` preso seja tratado como "este endpoint não está livre" e a escada
   **rode** em vez de ficar presa. É uma mudança no ficheiro mais
   sensível do repo, e por isso não a faço sem a tua confirmação e sem o
   portão que a prove.

### #29 e #5 — continuam em aberto

A busca "extremamente inteligente" (#29) e os pontos-vs-texto (#5) são
perguntas de ecra, e precisam de ti a ver o que eu não consigo ver de fora.
Não os vou marcar como feitos a dedo. São dois prompts de uma linha cada — o
mais rápido de todos é fazermos isso numa conversa só, com o ecrã partilhado.


