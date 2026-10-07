# Duplicação das entradas de transcript — causa medida, cura e o check que a trava

Data: 2026-10-06. Alvo: `H:/sotto` — a app **a correr**. Nada foi relançado; tudo
abaixo é leitura do que ela já escreveu, mais replay de um stream real pelo motor
real.

A queixa do dono, verbatim:

> "e por que duplica as entradas de transcript? por que nao da append, sempre?
> fica duplicando linha."

Requisito que sai daqui, e não é curiosidade: **cada legenda nova = UMA linha
nova, e NUNCA a mesma linha duas vezes.**

---

## 0. Veredicto

**Uma causa, dois sítios visíveis.** O motor de renderização
(`app/electron/caption-formulation.js`) escrevia a MESMA linha duas vezes em
história quando o worker continuava uma linha que o renderer já tinha
commitado. O ficheiro em disco e a lista do painel mostram o mesmo defeito, e a
lista do painel é fiel ao ficheiro — logo **não há duplicação no render**.

Cura: o motor passa a lembrar-se do que já escreveu (início, fim de áudio e as
palavras da linha) e, quando o fragmento seguinte re-cobre essa mesma linha,
acrescenta **só as palavras novas**. O append é preservado; o que desaparece é
a repetição.

Nada em `worker/wasapi_loopback.py` foi tocado. Nada em `worker/sotto_worker.py`
foi tocado: o worker cumpre o contrato que ele próprio documenta.

---

## 1. O artefacto do dono, contado

Comando (`python -`, stdlib, sobre os dois ficheiros):

```
history/2026-10-06/06.md: 124 entries, 3 exact-duplicate pairs, 83 word-prefix-growth pairs
history/2026-10-06/07.md:  13 entries, 0 exact-duplicate pairs,  7 word-prefix-growth pairs
```

Em 137 linhas, **93 pares** onde a linha seguinte é a anterior mais palavras.

### 1a. As linhas duplicadas REAIS — texto igual, timestamps diferentes

`H:/sotto/history/2026-10-06/06.md`:

```
linha   4 [06:17:31]  O rádio.
linha  12 [06:19:47]  O rádio.
linha  49 [06:40:19]  Speaking.
linha  69 [06:42:06]  Speaking.
linha  50 [06:40:23]  Speaking In dra Schoolro Day after For.
linha  70 [06:42:09]  Speaking In dra Schoolro Day after For.
```

Estas são as respostas literais à pergunta "por que duplica as entradas de
transcript": a MESMA frase, escrita duas vezes, com horas diferentes.

### 1b. E as que crescem por prefixo — texto a crescer, não texto igual

`H:/sotto/history/2026-10-06/07.md`, as 7 todas:

```
linha 1 [07:01:02] -> linha 2 [07:01:06]
    "After Day for He'll have."
    "After Day for He'll have Sunday and he can."
linha 3 [07:01:28] -> linha 4 [07:01:31]
    "Schoolrooms Day after."
    "Schoolrooms Day after He'll an appearance."
linha 4 [07:01:31] -> linha 5 [07:01:37]
    "Schoolrooms Day after He'll an appearance."
    "Schoolrooms Day after He'll an appearance and he can immediate Going a slushy coun Roads."
linha 6 [07:01:39] -> linha 7 [07:01:42]     "Speaking damp." -> "Speaking damp in drafty scho Day after day."
linha 7 [07:01:42] -> linha 8 [07:01:45]     "... Day after day." -> "... Day after day He'll have to an appearance."
linha 8 [07:01:45] -> linha 9 [07:01:46]     "... He'll have to an appearance." -> "... He'll have to an appearance Sunday mor."
linha 10 [07:01:52] -> linha 11 [07:01:58]   "And he can immediately Going along Country Roads speaking to."
                                             -> "... speaking to He'll have to pu."
```

É o mesmo defeito: nas duas primeiras linhas "After Day for He'll have" é
escrito **duas vezes** — uma sozinho, uma dentro da linha maior.

### 1c. O feed do painel é fiel ao ficheiro — não há duplicação no render

O `PANEL_V2_PROBE` da mesma sessão carrega o `feed` que o painel pintou
(`_main/webview-run.log:495`). Comparado com o texto dos dois ficheiros:

```
rendered feed entries  : 137
owner's file entries   : 137
feed == file, in order : True
```

137 = 124 + 13. O feed não acrescenta nem inventa uma linha: **toda a
duplicação que o dono vê já está no que foi commitado.**

---

## 2. O contrato do worker (a peça que explica tudo)

O worker manda a **LINHA**, não a porção nova. `worker/sotto_worker.py:1409-1417`:

```python
# `start` is the START OF THE LINE, never the newest chunk's start.
# A renderer that joins fragments itself (panel.js /
# caption-formulation.js) detects a re-cover by `start < lastAudioEnd`
# and REPLACES the line it already shows; sending the chunk's own
# start instead reads as a NEW fragment and the line duplicates
# itself word for word. MEASURED against the real renderer module.
```

Medido no stream real `worker/runs/gate-live-speech.jsonl` — parcial e
acumulativo, mesmo `start`, `end` a crescer:

```json
{"type":"caption","text":"Immediately after","start":0.56,"end":1.12}
{"type":"caption","text":"Immediately after Going alo","start":0.56,"end":2.24}
{"type":"caption","text":"Immediately after Going alo Country roads","start":0.56,"end":3.36}
```

O renderer é suposto JUNTAR e SUBSTITUIR dentro da linha. E é o que faz — até
haver um commit. `commit()` chamava `takeBuffer()`, que faz `lastAudioEnd = null`:

```js
function takeBuffer() {
  const all = visible();
  committed = []; provisional = []; prevWords = [];
  lastAudioEnd = null;          // <-- a âncora de re-cover, destruída
  return all;
}
```

Depois de um commit, a continuação da mesma linha deixa de ser reconhecível
como continuação: `start < lastAudioEnd` já não pode ser verdade, porque
`lastAudioEnd` é `null`. O fragmento acumulativo é então lido como linha NOVA,
com as palavras já escritas lá dentro outra vez.

E há um commit a meio da linha porque o *hold deadline* do painel é **1500 ms**
(`COMMIT_MAX_HOLD_MS`) enquanto o worker só fecha a linha ao fim de **8 s de
silêncio** (`SENTENCE_GAP_S`) — ou pontuação terminal, ou 90 caracteres. O
renderer fecha a linha muito antes de o worker a considerar fechada.

---

## 3. Diagnóstico: a hipótese confirmada e as eliminadas

Os candidatos (a)-(d) do briefing, cada um com o comando e o número. Nenhum
deles foi assumido.

### (b) worker a re-emitir após `device-rotated` — **ELIMINADA**

```
$ python -  (sobre _main/webview-run.log)
BRIDGE_SPAWNED (worker process starts)     : 2      # linhas 374 e 529
spawns ANTES da primeira caption            : 1      # 374, antes da 422
spawns DENTRO da janela de captions         : 0      # janela = linhas 422..486
WORKER_AUTOSTART lines                      : 2
BRIDGE_EXIT lines                           : 1      # linha 498
device-rotated events DENTRO da janela      : 1      # linha 432
BRIDGE_CAPTION_SENT consecutivos iguais     : 0
```

A única rotação dentro da janela, `_main/webview-run.log:432`:

```
BRIDGE_SILENT_BENIGN ms=15000 pid=35672 state=no-audio
  because="device-rotated reason=flat peak=0.250702 floor=0.002" restarts=0
```

`pid=35672` é o mesmo do spawn da linha 374 e `restarts=0`: **o mesmo processo,
sem restart**. O segundo spawn (linha 529) é depois da última caption (486) —
é a sessão seguinte. Uma re-emissão pós-rotação deixaria duas
`BRIDGE_CAPTION_SENT` consecutivas com o mesmo texto; há **zero**.

### (c) `on_worker_caption` chamado duas vezes por legenda — **ELIMINADA**

```
BRIDGE_CAPTION_SENT calls (on_worker_caption)  : 29
payloads distintos                             : 29
payload entregue duas vezes                    : 0
```

29 chamadas, 29 textos distintos. E o próprio worker confirma a contagem —
`_main/webview-run.log:498`:

```
BRIDGE_EXIT pid=35672 rc=1 spawns=1 captions=28 statuses=18 malformed=0
```

28 captions do worker + 1 injectada pelo probe (`A legenda ao vivo SOTTO-V2-…`)
= as 29. Isto reconcilia o `worker_captions_counter 28` já medido.

### (a) buffer do painel a re-renderizar — **ELIMINADA como causa independente**

O §1c mede o feed do painel byte-a-byte contra o ficheiro: 137 = 137, mesma
ordem, mesmos textos. A lista `live` cresce com a mesma linha porque o motor lhe
entrega duas linhas commitadas — não porque a lista se repita.

Nota de um caminho que examinei e **não** é causa: `panel.js:136-138`
(`retireProvisional`) selecciona a linha por `.caption--provisional`, classe que
`renderProvisional` desliga quando `isProvisional` é falso. Se esse ramo
disparasse, a linha provisória ficaria órfã e o commit acrescentaria a gémea. Não
dispara: `provisional = hypothesis.slice(agreed)` e, como `hypothesis` é sempre a
linha visível mais pelo menos uma palavra nova (`opening.length >= 1`, garantido
pelo `return` novo), `agreed < hypothesis.length` e portanto
`provisional.length > 0` sempre. Código morto — deixado como está, porque a
evidência não o nomeia.

### (d) histórico a registar a MESMA frase com timestamps diferentes — **CONFIRMADA (sintoma)**

§1a: `O rádio.` nas linhas 4 e 12, `Speaking.` nas 49 e 69, e
`Speaking In dra Schoolro Day after For.` nas 50 e 70. É exactamente o que o
dono descreve, e a causa é a do §2 — o mesmo fragmento re-coberto escrito uma
segunda vez.

### A causa única, medida

Replay do stream REAL (`worker/runs/gate-live-speech.jsonl`) pelo motor REAL,
com o *hold deadline* a disparar **depois de cada fragmento** (o pior caso, e o
que produziu o ficheiro do dono):

```
$ node app/electron/transcript-append-oracle.js --pretend <motor pré-cura>
#gate-live-speech (cumulative, live tap): 2 worker lines, 13 commits, 103 words
```

103 palavras escritas onde o worker disse **27** (15 + 12). As 76 a mais são a
repetição, e o oracle imprime-a palavra a palavra:

```
append is not exact — the line must appear once, in order
      expected (15 words): immediately after going alo country roads speaking to day after day for a fort he'll
      committed (60 words): immediately after immediately after going alo immediately after going alo country roads …
      lines committed: ["Immediately after.","Immediately after Going alo.","Immediately after Going alo Country roads.",…]
```

---

## 4. A cura

`app/electron/caption-formulation.js` — três mudanças, todas no motor.

**1) Estado que sobrevive ao commit** (o que antes era destruído):

```js
let emittedEnd = null;      // fim de áudio da última linha escrita
let emittedStart = null;    // o `start` dessa linha = a identidade da linha
let emittedWords = [];      // as palavras dessa linha como o worker as tinha
```

**2) `commit()` grava o que ficou coberto** em vez de o esquecer:

```js
if (line) {
  onCommit(line, reason);
  emittedEnd = audioEndOf(all);
}
```

**3) `ingest()` reconhece a continuação e escreve só o que é novo:**

```js
const fragWords = incoming.map((t) => t.w);
let opening = incoming;
if (start !== null && start === emittedStart && emittedEnd !== null && start < emittedEnd) {
  opening = incoming.slice(agreedPrefixLength(emittedWords, fragWords));
} else if (start === null && emittedWords.length) {
  if (fragWords.length === emittedWords.length
      && agreedPrefixLength(emittedWords, fragWords) === fragWords.length) {
    return;                       // a mesma legenda outra vez: nada a acrescentar
  }
}
if (!opening.length) return;      // nada novo -> NUNCA a mesma linha duas vezes
emittedStart = start;
emittedWords = fragWords;
```

Porque é que cada guarda está lá:

* `start === emittedStart` e **não** `start < emittedEnd` sozinho: um **restart
  do worker** reinicia o relógio de áudio, e a primeira caption da sessão nova
  chega com um `start` muito ABAIXO do da linha emitida. Com `<`, o restart era
  lido como re-cover e as primeiras palavras da sessão nova eram engolidas. Com
  `===`, o restart cai fora e nada se perde. (Caso de teste dedicado no oracle.)
* A remoção é **textual** (`agreedPrefixLength` contra as palavras da linha
  emitida), e o áudio só FECHA o portão. Um portão errado custa zero palavras: a
  remoção máxima é o prefixo que o fragmento realmente repete.
* Sem posição de áudio (`start === null`) o motor não consegue distinguir "o
  worker estendeu a linha" de "o worker começou outra frase com a mesma
  abertura". Adivinhar aí apagaria palavras em silêncio, por isso só cai o caso
  **provavelmente igual**: o texto exacto outra vez.

### O que o append preserva, e o que muda à vista

Preservado: cada palavra nova é escrita **uma vez**, pela ordem falada, e nada é
apagado — o histórico continua append-only e o *hold deadline* continua a
fechar linhas, como antes.

Mudança visível, e é de propósito: ao pé de um commit a meio da linha, a linha
seguinte passa a conter **só as palavras novas**. Onde o dono via

```
- [07:01:02] After Day for He'll have.
- [07:01:06] After Day for He'll have Sunday and he can.
```

passa a ver

```
- [07:01:02] After Day for He'll have.
- [07:01:06] Sunday and he can.
```

A frase fica partida em duas linhas em vez de ser escrita duas vezes. Nomeio a
alternativa e **não** a tomei: subir `COMMIT_MAX_HOLD_MS` (1500 ms) até ao
`SENTENCE_GAP_S` do worker (8 s) faria a linha inteira ser commitada uma só vez,
mas muda QUANDO a legenda aparece no painel e nenhuma medição nomeia o prazo
como errado.

---

## 5. Verificação: o check que distingue append de duplicação

`app/electron/transcript-append-oracle.js`. Replay dos streams REAIS
(`gate-live-speech.jsonl` acumulativo; `ACCEPT-after.jsonl` delta) pelo motor
REAL, com o deadline a disparar depois de cada fragmento e no fecho da linha,
mais casos unitários nomeados.

A asserção primária é a **igualdade exacta**: as palavras commitadas, por ordem,
têm de ser as palavras da linha do worker, uma vez cada.

* **DUPLICAÇÃO** — uma palavra escrita duas vezes → a concatenação não bate.
* **PERDA** — uma palavra escrita zero vezes → a concatenação não bate.

Um check que só procurasse duplicados aprovava uma "cura" que simplesmente
comesse a continuação. Por isso o mutante de perda existe.

```
$ node app/electron/transcript-append-oracle.js --pretend <motor pré-cura>
RESULT: RED — 16 violation(s)      # 11 DUPLICATE + 2 "append is not exact" + casos unitários

$ node app/electron/transcript-append-oracle.js --pretend <mutante: opening = []>
RESULT: RED — 3 violation(s)       # commit 2 words onde a linha tem 15: PERDA

$ node app/electron/transcript-append-oracle.js
engine under test: H:\sotto\app\electron\caption-formulation.js
#gate-live-speech (cumulative, live tap): 2 worker lines, 13 commits, 27 words, …
#ACCEPT-after (delta, file mode): 16 worker lines, 16 commits, 29 words, …
RESULT: GREEN — every worker line is appended once, in order, word for word
```

O stream delta dá 16 commits / 29 palavras **antes e depois** da cura: o
caminho do modo ficheiro não regrediu.

Três comandos, reproduzíveis:

```bash
# 1. o motor de hoje: GREEN, exit 0
node app/electron/transcript-append-oracle.js

# 2. a prova de que o oracle não é vácuo: um motor ANTERIOR à cura tem de dar
#    RED. `HEAD` serve enquanto a cura não estiver commitada; depois dela,
#    aponte-se para o commit anterior.
git show HEAD:app/electron/caption-formulation.js > /tmp/pre-cura.js
node app/electron/transcript-append-oracle.js --pretend /tmp/pre-cura.js

# 3. a prova de que o oracle também apanha PERDA: um mutante que simplesmente
#    deita fora a continuação tem de dar RED por "append is not exact".
sed -e 's|opening = incoming.slice(agreedPrefixLength(emittedWords, fragWords));|opening = [];|' \
    app/electron/caption-formulation.js > /tmp/perda.js
node app/electron/transcript-append-oracle.js --pretend /tmp/perda.js

# 4. o censo do artefacto do dono (medição, ver a nota abaixo)
node app/electron/transcript-append-oracle.js --history history/2026-10-06/06.md
```

Casos unitários cobertos, cada um uma regra que o dono enunciou: a mesma legenda
duas vezes → 1 linha; restart do worker com relógio a recuar → sem perda; restart
que repete o texto por coincidência → legenda NOVA (2 linhas); frase nova depois
de uma pausa → intacta; sem posição de áudio → o texto igual não é escrito duas
vezes; e a continuação de uma linha já commitada → só as palavras novas.

### O censo `--history` é uma medição, não o portão

```
$ node app/electron/transcript-append-oracle.js --history history/2026-10-06/07.md
13 entries; exact duplicates: 0; word-prefix growth: 7   -> exit 1
```

Contra o ficheiro do dono isto é honesto e RED. Mas um ficheiro, sozinho, não
distingue um defeito de um worker que fechou a linha e depois voltou a falar a
mesma abertura — logo **não** é ele o portão da regressão; o portão é o replay
pelo motor real, onde a linha do worker é conhecida. `--history` fica como
instrumento de medição para o próximo lane que olhar para dados do dono.

---

## 6. Limites: o que NÃO ficou provado

* **O ficheiro do dono não foi regenerado.** Isso exigiria relançar a app, e a
  ordem era medir sem a relançar. A prova é o replay do mesmo formato de stream
  (acumulativo, mesmo `start`, `end` a crescer) pelo mesmo motor, e a
  reconciliação do defeito com as 93 pares do ficheiro — não uma segunda captura.
* **O log não traz `start`/`end`** (`BRIDGE_CAPTION_SENT` imprime só `text`),
  por isso o stream do ficheiro 06.md/07.md não foi reexecutado palavra a
  palavra; executou-se `gate-live-speech.jsonl`, que tem a mesma forma e traz a
  posição. [INFERENCE] que a sessão das 07:01 é do mesmo tipo — sustentada pelo
  §1b (o crescimento por prefixo só é produzível por um parcial acumulativo).
* **Não medido**: quanto tempo a app leva agora a encher uma linha depois de um
  commit (o painel mostra a linha curta antes de a completar). É
  comportamento observável novo e vale uma medição própria.

---

## 7. Ficheiros tocados

| ficheiro | o quê |
|---|---|
| `app/electron/caption-formulation.js` | a cura (§4) |
| `app/electron/transcript-append-oracle.js` | o check novo (§5) |
| `app/electron/package.json` | script `transcript-append-oracle` (convenção do `bridge-selftest:node`) |
| `docs/audit/transcript-duplicacao.md` | este documento |

**Não tocados**: `worker/wasapi_loopback.py` (eixo do áudio, de outra lane),
`worker/sotto_worker.py` (cumpre o contrato documentado), `app/electron/panel.js`
(a lista é fiel ao ficheiro — §1c), `app/electron/history-store.js` e o
`history_append` do `sotto_webview.py` (ambos são `'a'` puro, uma linha por
chamada: o caminho do append nunca duplicou).

---

## 8. Adenda — a cura foi deslandada em silêncio, e reposta (17:41Z–17:44Z)

Este secção existe porque o facto aconteceu DEPOIS de o §5 ter sido medido, e é
da mesma classe que este documento combate: **"entregue" não é uma condição.**

### O que se mediu

| hora (Z) | `caption-formulation.js` | `node app/electron/transcript-append-oracle.js` |
|---|---|---|
| 17:41 | 20548 B, com `emittedStart`/`emittedEnd`/`emittedWords` | `rc=0` **GREEN** |
| 17:42 | 17188 B, **sem** as três variáveis | `rc=1` **RED — 16 violations** |

A assinatura do RED é a pré-cura exacta: `#gate-live-speech (cumulative, live
tap): 2 worker lines, 13 commits, 103 words` onde o worker disse 27.

### A causa, medida e não suposta

```
$ git rev-parse HEAD
11df66e2bf18c4eeaf6d633a6a39a3f25502e0f7        # inalterado
$ git diff -U0 -- app/electron/caption-formulation.js
@@ -341,7 +341,7 @@ function createEngine(options) {
-    onProvisional(visibleText(), provisional.length > 0);
+    onProvisional(committed, provisional);
```

**Um hunk, uma linha.** Não houve commit, nem revert, nem checkout: outra lane
escreveu este ficheiro partilhado a partir da versão pristina (o conteúdo de
`HEAD`), e nessa escrita caíram as três edições. O ficheiro é hot-reloaded pela
app a correr (`HOT_RELOAD_WATCH kind=panel dir=H:\sotto\app\electron`), logo o
motor revertido foi apanhado em execução.

### O que NÃO apanhou

- `git status` disse `M app/electron/caption-formulation.js` **antes e depois** —
  a mesma letra para o ficheiro curado e para o ficheiro revertido.
- `deliverables` disse `PRESENT` **antes e depois** — o caminho existia nos dois.
- Nenhum instrumento do fleet reportou nada.

O **único** detetor foi eu voltar a correr o oracle. É por isso que a linha

```
node app/electron/transcript-append-oracle.js
```

está agora escrita, como pré-condição de escrita, no cabeçalho de estado do
próprio `caption-formulation.js` — o sítio onde o próximo escritor a vai ver.

### O que não pude fazer

`write agent://PainelAtrasoEAcerto` (avisar a lane irmã) é **recusado** nesta
build: `this build exposes no delegation seam (ctx.executeTool is absent)`. Uma
lane não consegue dizer a um par que está prestes a sobrepor-lhe o trabalho —
o mesmo buraco que o observer registou às 17:42Z como `ABERTO/#961 CAPACIDADE
EM FALTA`. Fica reportado como ticket.

### Estado reposto, verificado

- 21492 B; `emittedStart` / `emittedEnd` / `emittedWords` presentes; a linha 344
  da lane irmã **preservada**; `node --check` rc=0; oracle **rc=0 GREEN**.

### Perigo de segunda ordem, que não toquei (não é meu ficheiro)

A assinatura nova da lane irmã `onProvisional(committed, provisional)` não casa
com o consumidor `panel.js:108 renderProvisional(text, isProvisional)`: esse faz
`line.querySelector('.caption__text').textContent = text` (um array pinta
`[object Object],[object Object]`) e
`line.classList.toggle('caption--provisional', Boolean(isProvisional))` (um array
é sempre truthy, logo o toggle deixa de distinguir provisional de confirmado).
Se aquela mudança está a meio, o painel pinta mal hoje.

Tickets abertos com as provas: `46aa3bb2a923172652e870e6` (o deslandamento
silencioso) e `0cddee932696d010c3e12243` (o selo do theorist a re-keysar a
disposição no hash de conteúdo de um ficheiro que o próprio loop reescreve, o que
bloqueou este `edit` duas vezes).
