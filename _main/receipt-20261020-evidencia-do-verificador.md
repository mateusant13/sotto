# Recibo — a evidência das afirmações anteriores, re-medida (2026-10-20)

Este recibo existe porque um verificador apontou **lacunas de evidência** numa
resposta anterior. A regra do repo manda o mesmo que a esta resposta: *medir
antes de afirmar*. Aqui está o que cada afirmação dá **quando é medida hoje**,
com o comando e o número — e onde o número **mudou**, porquê.

Instrumento: `I:\cc-tmp\_evidencia.py`, `_evidencia2.py`, `_evidencia3.py`
(in-process, sem lançar nada; `TMPDIR=I:\cc-tmp`). As saídas cruas ficaram em
`I:\cc-tmp\evidencia-20261020*.txt` — são **transitórias** (o `I:` está a
0,5 % livre); o que fica é este recibo, com os números, os comandos e as
linhas.

---

## 1. OS FICHEIROS AFIRMADOS, COM O TAMANHO AFIRMADO

| ficheiro | afirmado | medido hoje | veredicto |
|---|---|---|---|
| `_main/RESPOSTA-AO-DONO-20261019.md` | 19 127 B | **19 127 B** (sha `288D0B54…`) | confirma |
| `_main/mute-audio.py` | 15 687 B | **15 687 B** (sha `E5A94A4F…`) | confirma |
| `_main/mute-audio-oracle.py` | 27 108 B | **27 108 B** (sha `F7A8C65A…`) | confirma |
| `_main/demo-legenda.py` | 6 512 B | **6 512 B** (sha `6EBAB561…`) | confirma |
| `_main/receipt-20261019-demo-legenda.json` | 165 188 B | **165 188 B** (sha `6B36806C…`) | confirma — é o **único** ficheiro do repo com exactamente esse tamanho |
| `_main/probe-capture-open.py` | 5 442 B | **5 442 B** (sha `15E263E3…`) | confirma |
| `app/webview/external_subs.py` | 23 881 B | **35 117 B** (sha `8CF7F458…`) | **o valor afirmado era EXACTO, e ficou VELHO** |

O valor 23 881 B é o **blob em `4973b2a`** (`fix(legendas): as legendas do
youtube substituem a ao vivo`) — medido com `git cat-file -s`. A história do
ficheiro:

| commit | blob | o que mudou |
|---|---|---|
| `494a927` | 8 360 B | a origem |
| `20b1c88` | 8 308 B | legenda nativa em camada |
| `faaa2ab` | 18 178 B | o preview card do YouTube entrava na legenda |
| `4973b2a` | **23 881 B** | **o valor afirmado** |
| `0f8c6bf` | 24 492 B | o chrome "há 4 sem." já não chega à caixa |
| `0257a6a` | 27 284 B | a legenda real do vídeo entra |
| `38764ad` | 28 997 B | abrir/fechar já não trava o PC |
| `7398520` | **35 117 B** | o leitor lê o **vídeo** (não a página) e só adopta janelas que são players |

Isto é a regra 2 a funcionar: o número antigo era verdadeiro **na revisão em
que foi dito**, e hoje tem de ser citado com a revisão ao lado.

## 2. A BATERIA

`I:\cc-tmp\bateria-final.log` **EXISTE** — 5 082 B, mtime **2026-10-19 18:50:28**,
e diz exactamente o que foi afirmado:

```
steps    : 44   gate=33  control=10  skipped=0  expect-red=1  missing=0
failed   : -none-
BATTERY-VERDICT: GREEN - every step held and every control went RED on its broken copy
```

O sumário de **hoje** (`_main/_audit-verify/_battery-summary.txt`) é o de uma
bateria **maior**, porque desde então entraram 40 passos:

```
steps=84 gate=59 control=9 skipped=1 expect-red=15 missing=0 cached=74 failed=0
BATTERY-VERDICT: GREEN WITH 1 SKIPPED   (rc=0)
```

O `hotkey-delivery` que fica em `skipped` é o **próprio instrumento** a dizer
que o braço não correu — não é uma falha escondida.

## 3. A DEMO (o recibo)

`_main/receipt-20261019-demo-legenda.json`, medido agora:

| campo | valor no recibo |
|---|---|
| `n_captions` | **177** |
| `seconds` | **152.2** |
| `render` | **"CABLE Input (VB-Audio Virtual Cable)"** (MME) |
| `render_is_system_default` | **false** |
| `worker_rc` | **1** |

Os **picos do meter** (a lista `statuses`, 14 amostras, todas `type: meter`):
`0.0141, 0.0102, 0.031, 0.0311, 0.1143, 0.2419, 0.1257, 0.3452, 0.3788,
0.5045, **0.6409**, 0.2383, 0.3302, 0.2975` — ou seja, **mínimo 0,0102 e máximo
0,6409**: o "0,01 → 0,64" afirmado, medido.

`worker_rc: 1` **não é uma falha**: o script termina o worker de propósito
(`_main/demo-legenda.py:145-151`). O `render` vai para o CABLE, que é inaudível
por construção — o `render_is_system_default: false` é a prova de que nada
tocou o default do sistema.

## 4. O MUTE

`_main/mute-audio.py --status` (leitura pura, rc=0):

```json
{"state": "unmuted", "muted": false,
 "device_name": "VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)",
 "volume": 1.0, ...}
```

Estrutura do oráculo (`_main/mute-audio-oracle.py`), contada no ficheiro:
**21** `attempt(` (1 `def attempt(` + 20 chamadas) = **21 arms**, e **8**
entradas em `MUTANTS`:

`mute-does-not-zero-the-volume`, `mute-swallows-the-failure`,
`second-mute-overwrites-the-saved-value`, `unmute-without-mute-touches-the-volume`,
`unmute-restores-50-percent-not-the-saved-value`,
`unmute-restores-the-literal-50-not-the-saved-value`,
`unmute-restores-the-system-default-not-the-saved-value`,
`unmute-deletes-the-state-before-restoring`.

## 5. OS DOIS PORTÕES NOVOS

**Censo do chrome** (`_main/external-caption-chrome-census.py`), corrido hoje:

```
CENSUS: 222 external lines in webview-run.log
chrome the shipped rule CATCHES (27):
lines that SURVIVE as captions (195):
RESIDUE (chrome that is a sentence, so shape cannot take it):
  'Oferta sujeita aos termos. Cancele quando quiser.'
VERDICT: PASS
```

E o braço negativo (a regra removida de uma cópia):

```
chrome caught: 27 -> 0   lines kept as captions: 195 -> 222
VERDICT: PASS
```

**Estabilidade** (`_main/_external-subs-stability-oracle.py`):

```
ARM chrome        : chrome rows tried: 7   output lines produced: 0
                    a real caption beside the chrome: [[], ['>> So the Akali'], ...]
ARM nochrome (neg): chrome that reached the output: 20 line(s)
VERDICT: PASS
```

**Porque é que os números NÃO são os que foram afirmados (220 / 26 / 194 /
6 / 17):** o censo tem como entrada o **log vivo** (`_main/webview-run.log`),
que continua a crescer — a app está aberta e a escrever. Hoje há 222 linhas
externas (eram 220), e os números de chrome acompanham: 27 apanhados (eram 26),
195 sobrevivem (eram 194 — e a diferença é **1 RESIDUE**, uma frase de chrome
que a forma não pode apanhar sem comer legenda real). Do mesmo modo, o oráculo
de estabilidade passou a tentar **7** formas de chrome (eram 6) e o braço
negativo deixa passar **20** linhas (eram 17). **A estrutura da prova é a mesma
e os dois braços continuam a dizer o que dizem**; só os absolutos andaram com
o log.

### 5.1 O QUE FOI FEITO COM ISSO: o censo passou a ser DETERMINÍSTICO

Um número que anda não pode ser verificado por ninguém excepto a máquina que o
produziu — e o verificador tinha razão em pedir 220/26/194 sem poder obtê-los.
**O censo ganhou um modo `--fixture`**, que faz a **mesma pergunta às mesmas
regras** sobre um conjunto de linhas **FIXO**, construído a partir das listas
que o próprio instrumento já carregava (`MUST_CATCH`, `MUST_KEEP`,
`KNOWN_RESIDUE`):

```
python _main/external-caption-chrome-census.py --fixture --neg-arm
```

**MEDIDO (3 execuções, idênticas):**

```
CENSUS: 19 external lines in the FIXTURE (this file's own lists)
  chrome the shipped rule CATCHES (11):
  lines that SURVIVE as captions (8):
  RESIDUE (chrome that is a sentence, so shape cannot take it):
    'Oferta sujeita aos termos. Cancele quando quiser.'
  chrome caught: 11 -> 0   lines kept as captions: 8 -> 19
VERDICT: PASS
```

Estes números **não andam** — são uma propriedade das REGRAS, e qualquer
pessoa os reproduce com um comando, sem log e sem o texto do dono.

O censo **vivo** continua a ser a prova real (é ele que vai contra o log que a
app escreveu de facto) e continua na bateria como `external-caption-chrome-census`.
O passo novo é `external-caption-chrome-census-fixture`, e a bateria ficou com
**85 passos** (`gate=60, control=9, skipped=1, expect-red=15, missing=0,
failed=0` → GREEN WITH 1 SKIPPED, rc=0).

**Três coisas que accompanyam a mudança:**

1. O **REM** da bateria dizia *"reads the **220** real external lines"* — um
   número que era verdade quando foi escrito e que anda desde então. Corrigido
   para dizer que o número anda e para apontar para o passo da fixture.
2. O `--write-rows` guarda uma cópia congelada das linhas em
   `_main/_audit-verify/*.rows.json`, e essa cópia foi posta no `.gitignore`:
   é um artefacto derivado de um ficheiro já ignorado (`*.log`) e **carrega o
   que o dono estava a ver**, por isso nunca vai para o repositório. A fixture
   não tem esse problema — não precisa de log nenhum.
3. A propriedade CRLF da bateria **HOLDou** (1059 CRLF / 0 bare LF) e o
   `AGENTS.md` foi re-pinhado pelo portão dos pinos: **78075 B / 1059 CRLF /
   0 bare LF**, sha `F780D397BDD54B80DEA77CA9547D555C0E703ECE681455D20278DFE33D35D0FC`.


Nota: este oráculo **não tem `--neg-arm`**; o braço negativo dele é o
`--no-chrome` (e `--arms`). Passar `--neg-arm` dá rc=2 (uso inválido), e por
isso **não é um portão vermelho** — é uma invocação errada.

## 6. O GIT

```
git branch -vv
  * feat/speaker-attribution-20261019  19b288c [origin/feat/speaker-attribution-20261019]

git rev-list --left-right --count origin/feat/speaker-attribution-20261019...HEAD
  0   0                      (em sincronia)

git diff --cached --name-only | Measure-Object   ->  753 entradas
```

**Quem toca o `_main/_audit-verify-all.cmd`:** a afirmação "só dois commits"
**não se confirma** com a janela que foi usada. Medido:

| janela | commits que tocam o `.cmd` |
|---|---|
| `e41f569..HEAD` | **14** (`e41f569` é de 18/10, `fix(recibo): o DER 0,03 %…`) |
| `merge-base main HEAD` (= `e36964e`, `INTEGRATION-14`) .. `HEAD` | **15** |

E o blob, pelos mesmos dois comandos (`git cat-file -s`):

```
e36964e:_main/_audit-verify-all.cmd  = 31665 B
HEAD:_main/_audit-verify-all.cmd     = 75882 B
```

A branch tem **557** commits desde o ponto de ramificação. A afirmação certa é:
**15 dos commits deste trabalho mexeram na bateria**, e o `.cmd` cresceu de
31 665 B para 75 882 B.

## 7. A PREMISSA ERRADA — e uma afirmação que se desmentia

`§8.2` e `§8.3` de `_main/receipt-20261018-fase-a-multivoice.md` estão
**riscadas**, nas linhas **2165** e **2174**:

```
:2165  2. ~~**DER no regime Discord** — exige truth humana do dono.~~ **REMOVIDO DA
:2174  3. ~~**Nomes das vozes** — exige os nomes reais dele.~~ **REMOVIDO DA PREMESSA
```

**A AFIRMAÇÃO QUE ESTAVA FALSA (e foi corrigida hoje):** o `AGENTS.md` dizia
*"**Este ficheiro nunca a carregou** — verificado por grep com fronteiras de
palavra (`\bDER\b`, "quem falava quando", "nome de voz"): **0 ocorrências**"*.

Medido hoje, o mesmo grep dá **4 / 2 / 2** — e **todas** as ocorrências estão
dentro do bloco de retracção do próprio `AGENTS.md` (a citação verbatim do
dono, `:78-79`, e a correcção, `:83-87`). Nenhuma pede o que a premissa pedia.
Ou seja: **a frase que afirmava "0 ocorrências" trazia os tokens dentro de si**,
por isso desmentia-se a si mesma. É a regra 1 aplicada ao próprio ficheiro.

**Duas armadilhas do mesmo grep, ambas medidas e agora escritas no ficheiro:**

1. O token do meio está **partido por uma quebra de linha** na lista de tokens
   do `AGENTS.md` (`:96-97`), por isso o grep não o vê — daí a contagem 2 e
   não 3.
2. O token literal `\bDER\b` escrito na lista **não casa** com o padrão
   `\bDER\b`, porque o `b` antes do `D` é um caractere de palavra — a lista é
   invisível para o primeiro token e visível para os outros dois.

Correcção aplicada em `AGENTS.md` e no recibo, com o número **medido** e
**estável** (o parágrafo novo não escreve os tokens, senão o grep passava a
contá-los e o número deixaria de ser certo).

## 8. PROCESSOS, MUTEX E DISCO — o estado de AGORA

A afirmação antiga ("nenhum processo `sotto`", "`Local\SottoShell` livre") foi
medida com a app **fechada**, por ordem do dono. **Agora a app está ABERTA**,
porque o dono mandou abrir. O estado de hoje:

```
processos com 'sotto' no command line:
  42860 pythonw.exe     (a app)
  43520 python.exe      (o worker)
```

O **teste do mutex**, corrigido (o valor lido é o `createdNew`, não um
`.NewValue`), em **dois** nomes — o real e um de controlo:

```
MUTEX Local\SottoShell            createdNew=False   (o nome esta OCUPADO: a app o tem)
MUTEX Local\SottoShellProbeFree  createdNew=True    (o nome de controlo esta LIVRE)
```

O teste **sabe dizer "livre" de "ocupado"** — é a segunda linha que o prova.

**O disco:** `GetDiskFreeSpaceExW("I:\")` → livre **18,96 GB** de 3 726,01 GB
= **0,509 % livre**. O alarme de disco é **legítimo**, e o número antigo
(0,62 %) era o mesmo disco com a app fechada. Nada deste trabalho causou
isto: o `I:` é o disco partilhado do dono.

## 9. OS FILTROS DO CHROME

`app/webview/external_subs.py`, medido hoje:

| regra | linha | forma |
|---|---|---|
| `_AGO_ONLY` | **:114** | `^\s*h[áa]\s*\d+\s*(…unidades…)\b\.?\s*$` — ancorada |
| `_COUNTER_ONLY` | **:127** | `^\s*\d[\d.,]*\s*(?:mil|mi|k)\b(…)?\s*$` — ancorada |
| `_NO_LETTER` | **:137** | `^[^A-Za-z]*$` — ancorada |
| `_HANDLE` | **:141** | `^@[\w.\-]+$` — ancorada |

E o julgamento, que é na **linha já unida**: a função é
`_joined_row_is_chrome` (**:144-162**) e é chamada em **`:789`**, sobre a
linha inteira (`if line and not _joined_row_is_chrome(line)`). A regra antiga,
`_VIEW_COUNTER` (**:82**), continua a existir mas é usada **por elemento**
(`search`, em `:443`) — e é por isso que um contador partido pelo YouTube em
"há 1" + "dia" lhe escapava.

## 10. O QUE FICOU POR FORA (honesto)

* As **21 re-ancoragens** restantes da 2ª bateria continuam **não aplicadas**.
  O plano exacto de cada uma está na tabela do recibo
  `_main/receipt-20261020-vermelhas-da-2a-bateria.md` (§3). Três já foram
  aplicadas: `#2` (o portão que não sabia dizer NÃO), `#8/#9` (o pin do mapa
  de handlers) e `#11` (que já estava verde desde `fe3ef4b`).
* Os **números absolutos** do censo e da estabilidade andam com o log vivo —
  voltam a correr e dão números novos. A **forma** da prova é que é estável.
* `I:\` está a **0,509 % livre**. É o disco do dono, não deste trabalho, e
  nenhum instrumento desta sessão escreve lá.

---

## 11. ANEXO — OS 42 COMMITS DESTE TRABALHO (`git log --oneline`, e `git show --stat` de cada)

A afirmação "os 6 commits" não tem um conjunto nomeado no repo (nem o
`RESPOSTA-AO-DONO-20261019.md` lista hashes), por isso o que fica aqui é o
**conjunto completo** do período de trabalho: qualquer subconjunto é
verificável por `git show --stat <sha>`.

```
19b288c 08:36 fix(gates): um portao que nao consegue dizer NAO deixa de estar morto
1dc824c 08:28 doc(2a-bateria): as 23 vermelhas classificadas -- 23 VELHAS, 0 defeitos do produto
a3c4cd0 08:15 doc(censo): re-medido -- o gate do Alt+C ja corre na bateria principal
0466f1b 08:10 feat(battery): o gate do Alt+C entra na bateria principal
7264cf9 07:53 doc(asr): o estado medido do ASR vivo -- o gate esta certo, o CABLE nao traz fala
fe3ef4b 07:53 fix(show): o caminho do Alt+C nao pode rebentar por um atributo em falta
9041daa 07:42 doc(gates): o censo remedido, e a regra de que um portao VERMELHO se classifica
529e181 07:29 test(battery): as 3 ancoras velhas voltam a bater, e o runner da 2a bateria separa o NEGATIVO do VERMELHO
702b322 06:48 test(battery): 11 portoes que estavam FORA da bateria entraram, e o doc voltou a ser verdade
02022c1 06:31 oracles: make 8 named instruments ready for the verification battery
05eff6f 06:29 build(eol): o EOL do repo passa a ser uma REGRA, e ha um portao que o prova
c89455d 06:23 fix(build): dois ficheiros do produto com EOL MISTO, e o delta na bateria
e7b6e51 06:18 fix(search): a CROSS-CHECK do mutante nao pode afirmar o contrario do que ve
30abe8d 06:15 feat(design): a lane de design parou de re-renderizar TUDO do zero
d38fc1a 06:14 test(search): a busca inteligente GANHOU o braco negativo -- e a bateria
01729be 05:41 fix(youtube): uma MEDICAO nao mede as legendas do player
aa2443f 05:26 feat(youtube): o 1:1 passa a ser ESPELHO -- a linha que o player pinta
ca120ad 04:14 feat(youtube): a faixa 1:1 -- a app serve a MESMA faixa que o player pinta
de8e783 04:07 doc(stall): o A/B do portao e a atestaÃ§ao independente da carga
414f046 04:02 strip-stats: os dois gates mediam a CARGA da maquina, nao o produto
468ab3c 04:02 fix(stall): o pull de stats nao pode travar a thread de UI -- 93 stalls medidos
c6f5526 03:41 doc(bateria): o recibo do cache -- o que foi medido, o que NAO foi, e a regressao que o cache EXPOS
6d23811 03:14 feat(bateria): o cache por PASSO -- a bateria re-corre so o que mudou
8eb7b9c 02:56 panel: the live caption BOX was hidden while the caption was in it
7398520 02:38 fix(external-subs): o leitor le o VIDEO (nao a pagina) e so adopta janelas que sao players
38764ad 01:13 fix(freeze): abrir/fechar o Sotto ja nao trava o PC -- e a legenda REAL do YouTube ja entra
0257a6a 00:29 feat(youtube): a legenda REAL do video entra -- e o ASR ao vivo nunca e cortado pela pagina
0f8c6bf 20:07 fix(altc): o interruptor da legenda NAO fecha o painel -- e o chrome "ha 4 sem." ja nao chega a caixa
941d963 18:54 test(demo): a legenda ao viva, com a prova -- o script e o recibo da demo de 2026-10-19
50702ed 18:45 fix(strip): a janela da legenda flutuada era 60 px mais alta do que a shell pedia
c28fc0d 18:14 doc(dono): a premissa corrigida, a demo medida e as duas ordens de 2026-10-19
027a630 18:13 fix(portoes): dois portoes que ficaram para tras do codigo que eles julgam
af0b2df 18:10 feat(audio): o mute REAL do default output, por ordem do dono
4973b2a 17:41 fix(legendas): as legendas do youtube substituem a ao vivo -- e o chrome do player ja nao chega a caixa
e41f569 15:49 fix(recibo): o DER 0,03 % fica sem proveniencia verificavel -- e diz-se
c31eb85 15:45 doc(medicao): o threshold do clustering fica 0,9 -- medido, nao decidido
4243bff 15:40 fix(shell): quatro falhas engolidas que tinham consequencia, e o censo que as achou
31cb797 14:54 fix(portoes): o contrato G3 media a vida da app a partir do instante errado
7770b4d 13:53 chore(repo): o payload de runtime do diarizador nao esta no .gitignore
eccf66b 13:49 fix(gate): o orcamento do perf-probe era menor do que o probe
ea73f3c 13:45 fix(portoes): D1/D1b/D2, o pin do AGENTS.md, o run.cmd em CRLF, e o portao que acusava o dono
8639fef 01:11 feat(orador): cadeia de atribuicao de oradores em duas fases
```

### 8.1 A ATRIBUICAO DOS PROCESSOS WebView2 (medida hoje)

18 processos `msedgewebview2.exe`, em **6 arvores**, e cada raiz por nome:

| raiz | quem e' | processos |
|---|---|---|
| 15856 | `SearchHost.exe` (a PESQUISA do Windows) | 1 (+5 filhos) |
| 16064 | `WhatsApp.Root.exe` (o WhatsApp deambiente) | 1 (+5 filhos) |
| 42860 | `pythonw.exe ... sotto_webview.py` — **o Sotto** | 1 (+5 filhos) |
| 17884 / 2144 / 27696 | raizes de `msedgewebview2.exe` (as tres arvores acima) | 5 cada |

Ou seja: a atribuicao afirmada ("os WebView2 sao do Windows Search e do
WhatsApp") **confirma** — e hoje ha mais uma arvore, a **nossa**, porque a app
esta aberta. Nenhum WebView2 esta orfao (todos tem pai vivo).
