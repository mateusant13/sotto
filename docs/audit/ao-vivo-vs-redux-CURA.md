# Ao vivo vs "redux" — a CURA: o ficheiro do historico deixa de mentir

> **PARCIALMENTE SUPERADO em 2026-10-06, pela lane `HistoricoVsRedux`**
> (`docs/audit/historico-vs-redux.md`). Duas afirmacoes deste documento deixaram de valer:
> §2.4 e §6.4 (e o M8) descrevem a linha `route=provisional-draft` a CHEGAR ao ficheiro do dono —
> o dono recusou explicitamente esse texto ("o historico simplesmente mostra a legenda ao vivo"),
> e a partir de agora **o historico aceita SO' `route=final`**: o painel
> (`panel.js recordHistory`), o store Electron (`history-store.js append`) e o store da app real
> (`sotto_webview.py history_append`) recusam um `provisional-draft`. A sonda com as duas cores e'
> `node _main/historico-vs-redux-probe.js` (`--gate-off` para o RED). §6.2 ("a app ficou a correr /
> recarregou o painel sozinha") **nao foi verdade com o painel a render**: o hot reload do painel
> aterra numa pagina de erro do Chromium — medido e reproduzido, ver
> `app/webview/sotto_webview.py:2415` e a §6 do documento novo.

Lane: `SottoFragmentacao` · 2026-10-06 · desenho = `docs/audit/ao-vivo-vs-redux.md` §5 (M1-M9)
Estado: implementado e medido. A app ficou **a correr** (recarregou o painel sozinha; ver §6).

---

## 0. O defeito, em duas linhas

A string pintada na caixa AO VIVO era **o mesmo objecto** que ia para o historico:
`panel.js:85 onCommit -> :153 addCaption(text) -> :185 recordHistory(text) -> :287 .append(text)`.
Duas consequencias medidas no ficheiro do dono, antes desta cura:

- **352 de 473 linhas (74,4 %) com <= 3 palavras**, mediana **1**;
- **473 de 473** acabam em pontuacao terminal — e essa pontuacao e **inventada** por
  `formulate()` (`caption-formulation.js:148-159`).
- 0,0 % das linhas diziam se eram uma frase fechada ou um fragmento que o *hold* de 1500 ms
  abandonou. **O ficheiro nao tinha como saber.** Era esse o defeito.

## 1. O que mudou — M1..M9, por `file:line`

### Worker — `worker/sotto_worker.py`

| # | o que | onde |
|---|---|---|
| M1 | o PCM do segmento e retido (pos-ganho, com o veredicto de fala por chunk) | `seg_pcm = {}` :2248; retencao `:2372`; poda pelo inicio da linha ABERTA `:2388-2394` |
| M1 | onde a linha aberta comeca | `LineFormer.open_start` :1545 |
| M2 | o evento leva a rota (`final`) | `LineFormer._event(text, final=False, closed=False)` :1553 |
| M2 | o FECHO sai **fora de banda**, nao como mais um evento | `_close()` :1580; `take_closed()` :1610; `line_events()` :1659 |
| M3 | **segunda passagem** sobre o audio do segmento INTEIRO, estado RNNT reposto | `rerun()` :2250; `finalise()` :2291; `drain()` :2311 |
| M3 | repor o estado RNNT e' `cc/ct/ccl` a zero | `StreamAsr.reset_stream_state()` :563 |
| M1-M3 | custo contado a parte, para nao duplicar `audio_s`/RTF | `run_chunk(..., account=True)` :577; `"reruns": 0` :2114; `WORKER_STATS ... reruns= rerun_wall_s=` :2142 |

### Renderer — `app/electron/caption-formulation.js`

| # | o que | onde |
|---|---|---|
| M5 | `ingest` le `meta.final`; `final:false` -> **so' provisorio**, nunca `onCommit` | `const provisionalRoute` :367, `finalRoute` :368 |
| M3 | `final:true` **substitui** o provisorio e e o unico texto que fecha a linha | `if (finalRoute) { … }` :370 e o `commit('final-pass')` no fim de `ingest` :512 |
| M5 | as regras de fronteira (gap de audio, cap de 90 chars) nao disparam no provisorio | `:377` e `:388` |
| M6 | `expireHold` **deixa de escrever**: marca nao-confirmado e devolve `''` | `expireHold()` :540 |
| M7 | o `reason` (ja calculado, ja deitado fora) viaja para o caller | `commit()` :321 |
| M8 | a rota no ficheiro: `final` so' quando o worker FECHOU a linha | `lineFinalPass` :245 |
| M8 | o texto do FICHEIRO (sem a pontuacao **inventada** num rascunho) | `const fileText = route === 'final' ? … : …` :336; `formulate(text, opts)` :157 |
| M6/M8 | rota + identidade da linha expostas ao painel | `state()` :562 |

### Painel e stores — `app/electron/panel.js`, `history-store.js`, `main.js`, `worker-bridge.js`, `app/webview/sotto_webview.py`

| # | o que | onde |
|---|---|---|
| M7/M8 | o painel passa a receber e a entregar `reason` e `meta` | `onCommit: (text, reason, meta)` `panel.js:88`; `addCaption(text, reason, meta)` :168; `recordHistory(text, reason, meta)` :296 |
| M8 | `route`/`start`/**`reason`** na linha | `options = {source, route, start, reason}` `panel.js:305-310` |
| M6 | o deadline **re-arma** em vez de escrever | `panel.js:104` |
| M9 | a caixa diz que a linha e' provisoria (`·`, classe `caption--provisional` que JA existia) | `panel.js:138` |
| M8 | o sufixo escrito no ficheiro (WebView2 — a app real) | `_history_provenance()` `sotto_webview.py:2009`; `history_append(text, options)` :2037; `options` vindos do painel :1266; escrita :2055 |
| M8 | o sufixo no store do Electron | `provenance(meta)` `history-store.js:75`; `append(text, meta)` :89; `main.js:826` |
| M8 | a rota chega ao renderer tambem no arranque Electron | `worker-bridge.js:717` |
| M8 | o sufixo e' METADATA: todos os leitores do FICHEIRO o removem antes de tratar o resto como texto | `sotto_webview.py:121,2102`; `history-store.js:40,151`; `transcript-append-oracle.js:332` |

**Formato da linha, depois:**

```
- [HH:MM:SS] <texto>   <!-- route=final start=<s> reason=<regra> -->
```

`route=final` = o worker fechou a linha sobre o **segmento inteiro** (M3).
`route=provisional-draft` = a linha saiu pelo caminho terminal (`flush` de uma mudanca de
estado) sem o worker a ter fechado — e nesse caso **nao leva a pontuacao inventada**.
`start` e' a identidade da linha do worker (`sotto_worker.py:_event`), a mesma que viaja no
JSONL, pelo que o ficheiro se reconcilia com o stream.

---

## 2. ANTES / DEPOIS

### 2.1 O ficheiro do dono, ANTES (medido nesta lane, 13:23, `history/2026-10-06/*.md`)

```
entries 473
<=3 words: 352      (74.4 %)
>3 words : 121
median words per entry: 1
ends in terminal punctuation: 473  (473/473 = 100 %)
```

(o documento de auditoria mediu 472 / 74,6 %; entre a auditoria e esta leitura o ficheiro
ganhou uma linha — `10.md` foi de 5 para 6 registos. As duas contagens sao a mesma coisa.)

### 2.2 O mesmo stream de fala real, com as duas semanticas

`node _main/history-route-oracle.js --audio G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav --max-chunks 400`
— 224 s da MESMA fala que o tap ao vivo estava a ouvir, pelo MESMO worker, pelo MESMO motor:

```
stream    : 1226 caption events — 1091 provisional, 135 final

CONTROL (semantica pre-cura, o MESMO stream): {"entries":1221,"over3":279,"short":942,"shortPct":77.1,"median":2}
NEW     (rota respeitada, o MESMO stream):    {"entries":135, "over3":134,"short":1,  "shortPct":0.7,"median":16}
```

| | CONTROL (antes) | NEW (depois) |
|---|---|---|
| registos | 1221 | **135** |
| <= 3 palavras | 942 (**77,1 %**) | 1 (**0,7 %**) |
| > 3 palavras | 279 (22,9 %) | 134 (99,3 %) |
| mediana de palavras | 2 | **16** |
| provisorios no ficheiro | por construcao | **0** |

**As duas contagens pedidas:** a fraccao de linhas com <=3 palavras cai de **74,4 %** (ficheiro
do dono) / **77,1 %** (controlo no mesmo stream) para **0,7 %**. A contagem absoluta de linhas
com >3 palavras *baixa* (279 -> 134) porque o ficheiro passa a ter **um registo por segmento**
em vez de **um por fragmento** — as 1221 linhas do controlo sao os pedacos das mesmas 135 falas.
Por isso a comparacao e' feita em **fraccao**, que e' o numero honesto.

### 2.3 A PROVA E' O FICHEIRO — o artefacto, relido do disco

`H:/sotto/history-verify/2026-10-06/10.md` (escrito pelo `history-store.js` real):

```
- [...] O rádio Segunda-feira Os moradores.   <!-- final start=0.56 -->
- [...] Sorry for the For the last couple I was out Actually, but But I'm finally And it wasn't AI.   <!-- final start=0.56 -->
- [...] But But we still got That we need Especially from Open A 'cause the Right now from Open AI.   <!-- final start=7.84 -->
- [...] Is a Not much it is GPT It's not G It is not the GPT Six point one as But what we So far.   <!-- final start=16.24 -->
```
… 136 linhas, **todas** com `route=final`, **nenhuma** com o sufixo em falta.

> O texto acima e' o do **modelo** (palavra-salada onde o modelo erra) — `docs/audit/ao-vivo-vs-redux.md`
> §6.3 ja diz que re-decodificar NAO corrige o erro, so' corrige o **corte**. O que mudou aqui e'
> o corte: mediana 2 -> 16 palavras, e a fronteira passou a ser a do **audio** (a do worker), nao
> a da **cadencia de entrega** (o deadline de 1500 ms do painel).

### 2.4 AO VIVO — a app real, sem eu a relancar

O painel recarregou-se pela propria vigilancia (`HOT_RELOAD_PANEL_DONE`) e um worker NOVO arrancou
depois da edicao (pid 26036, 10:31:37). O ficheiro do dono, escrito pela app, ganhou:

```
- [10:33:52] Nossa, eu vou. <!-- route=provisional-draft start=3.36 reason=status-change -->
- [10:36:54] Olha <!-- route=provisional-draft start=6.72 reason=status-change -->
```

A primeira foi escrita **antes** de o painel apanhar a regra da pontuacao; a segunda **depois**, e
e' visivel no ficheiro: `route=provisional-draft` **e sem o ponto final inventado**. As duas
carregam `route=` e `start=`. Antes desta cura, as duas eram indistinguiveis de frases.

Minutos depois chegaram as linhas **fechadas pelo worker**, ou seja a rota `final` (M3) exercida
AO VIVO:

```
- [10:42:14] Ho Hora que eu ganho.                                                <!-- … route=final … -->
- [10:42:51] Não, em uma ho Caralho Isso, man Olha bote O Li Tem uns drago O dra Olha o play de De E eu ten.   <!-- … route=final … -->
- [10:43:07] Ai i.                                                                 <!-- … route=final … -->
```

Censo do ficheiro do dono nesse instante, com o sufixo removido antes de contar palavras (e' o
que o torna comparavel):

```
PRE-cure  (sem sufixo): 502 entries, 379 <=3 words (75.5 %)
POST-cure (com sufixo):   7 entries,   4 <=3 words (57.1 %)
ALL                    : 509 entries, 383 <=3 words (75.2 %)
```

**O que isto diz, sem arredondar:** o mecanismo esta' provado ao vivo, nas duas rotas. A
**estatistica** do ficheiro do dono ainda nao pode cair de 74,6 % para 0,7 %, e por duas razoes
que nao sao a cura: (a) 502 das 509 linhas sao anteriores a cura e nunca serao recalculadas — o
ficheiro e' append-only; (b) das 7 linhas pos-cura, 4 sao `provisional-draft`, escritas pelo
`flush` de mudanca de estado do painel quando o worker foi morto antes de fechar a linha (nesta
caixa o tap esta' **plano**: `BRIDGE_SILENT_BENIGN … reason=flat`, e `BRIDGE_EXIT … rc=1` em
**37 de 37** arranques). Ha' um bilhete aberto para essa segunda parte
(`c7c667a6c6bb04282b5e9624`, liquidado como fora do contrato M1-M9: o M6 da auditoria declara o
`flush` o caminho terminal legitimo, e mexer em QUANDO ele dispara e' desenho novo).

A **medicao** que o ticket de acceptance pede vem por isso da corrida determinista sobre o MESMO
audio (§2.2) — mesmo worker, mesmo motor, mesmo store — que e' onde a comparacao
antes/depois e' legitima, porque as duas semanticas correm sobre o **mesmo** stream.

---

## 3. O que NAO mudou (a condicao do dono)

- **Latencia da legenda ao vivo:** nao muda. M5/M6 actuam **depois** de o texto ser pintado:
  `ingest` continua a chamar `onProvisional` a cada parcial e a caixa continua a crescer ao vivo.
  O que mudou e' so' o que decide **sair para o ficheiro**.
- **Texto da caixa ao vivo:** o `addCaption` pinta o mesmo texto que pintava. A pontuacao do
  **rascunho** so' difere no FICHEIRO (M8), nao no ecra.
- **Uma unica mudanca no ecra, e e' pedida pelo desenho:** a linha provisoria leva agora um `·`
  final e a classe `caption--provisional` que **ja existia** (M9). Se nao era isto que se queria,
  e' uma linha em `panel.js:138`.
- **Nao se subiu** `COMMIT_MAX_HOLD_MS` (1500 ms) para os 8 s do worker: o desenho §5.3 proibe-o
  exactamente para nao mexer no tempo da legenda.

---

## 4. Custo da segunda passagem (M3) — o que a auditoria deixou em aberto

A auditoria §7 deixa **NAO-VERIFICADO** o custo real da 2a passagem (a tabela do §6.2 e
`RTF x S` inferido). Duas coisas ficaram montadas para o fechar:

- `run_chunk(..., account=False)` mantem a passagem **fora** dos contadores do ao vivo, para que
  `audio_s`, `tokens=` e todos os RTF de `WORKER_STATS` continuem a ser a afirmacao sobre **uma**
  passagem;
- a passagem tem contadores proprios, publicados em `WORKER_STATS`:

```
reruns=<n> rerun_wall_s=<s>
```

`_main/segment-rerun-probe.py` mede-a isolada, no mesmo `StreamAsr`, sobre a mesma gravacao, sem
dispositivo de audio. **GREEN, 4/4 assercoes:**

| assercao | resultado |
|---|---|
| A `reset_stream_state()` devolve as caches ao inicio de um stream | PASS — `(1,24,70,1024)`, `(1,24,1024,8)`, `(1,)`, iguais a uma alocacao nova |
| B `run_chunk(..., account=False)` nao move contador nenhum | PASS — `n_chunks` 0->0, `audio_s` 0.00->0.00, `labels` 0->0 |
| C o estado do stream AO VIVO sobrevive a passagem | PASS — C1 as arrays vivas nao sao escritas em sitio (o risco §7 da auditoria sobre o `InferenceSession`), C2 o restauro reproduz bit a bit |
| D a passagem produz texto | PASS — `'O rádio Segunda feira Os moradores'` |

**Custo medido (duas corridas, 14,56 s de audio cada):** a passagem custou **0,91x** (e, numa
caixa mais carregada, **0,78x**) uma passagem de streaming sobre o **mesmo** audio — ou seja,
**re-decodificar o segmento custa aproximadamente o que custou decodifica-lo**. A inferencia
`RTF x S` do §6.2 da auditoria (0,15-0,25 -> 2,18-3,64 s para este segmento) descreve bem a
forma, mas o **valor absoluto depende da carga**: nesta caixa (a app ao vivo + orfaos) uma
passagem de streaming sozinha mediu RTF 1,59-3,04, contra os 0,14-0,22 que a auditoria mediu
numa caixa ociosa. Leia o **ratio**, nao o RTF absoluto.

**E o texto da 2a passagem foi IGUAL ao do streaming** (`'O rádio Segunda feira Os moradores'`).
Isso e' o esperado e esta' dito no §6.3 da auditoria: re-decodificar **nao corrige o erro do
modelo**, garante a **fronteira** — a linha fecha sobre o segmento inteiro, e o renderer deixa de
poder escrever um prefixo.

---

## 5. As portas (o que impede a regressao)

| porta | comando | resultado |
|---|---|---|
| append/duplicacao | `node app/electron/transcript-append-oracle.js` | **GREEN** |
| linhas do worker (12 arms, inclui o novo arm 11) | `python _main/caption-lines-oracle.py` | **12 PASS / 0 FAIL** |
| a rota ate' ao ficheiro (fim-a-fim, 5 arms) | `node _main/history-route-oracle.js --audio <wav>` | **GREEN** |
| a 2a passagem isolada | `python _main/segment-rerun-probe.py` | ver o recibo |

O arm 11 e' **novo** e existe porque a cura mudou o contrato num ponto medido: com o guarda
`text != self._shown` a suprimir o fecho, uma corrida de 14,5 s em modo ficheiro emitia
**3 provisorios e ZERO finais** — um historico que nunca recebia uma linha. O fecho passou a sair
**fora de banda** (`take_closed()`), o que mantem os arms 6/8/9/10 intactos (a ligacao que o
renderer ve' nao mudou) e publica o fecho na mesma.

## 6. O que a cura NAO resolve (explicito)

1. **O erro do modelo.** "Going alo slas" continua "Going alo slas" — e' o mesmo checkpoint
   (§6.3). Tirar o ERRO exige um modelo batch que **nao esta no disco**.
2. **A app tinha de recarregar.** O painel recarrega sozinho (ficou provado); o **worker** e
   recarregado por politica (`min_interval_ms=180000`, "applies at the next boundary") e apanha a
   cura no arranque seguinte. Nada foi relancado a mao.
3. **O auto-teste do shell continua a escrever no historico real** (`sotto_webview.py:2290-2291`).
   Ja' era defeito na auditoria (§4.4) e **nao** foi tocado aqui.
4. **O `provisional-draft` no ficheiro.** Um stream que morre de facto escreve os ultimos
   provisorios, agora **marcados** e **sem pontuacao inventada**. E' a leitura do §5.2/M6: o
   `flush()` e' o unico caminho terminal legitimo — mas um rascunho continua a ser um rascunho, e o
   ficheiro diz isso.

## 7. Os ficheiros tocados

```
worker/sotto_worker.py                      (M1, M2, M3)
app/electron/caption-formulation.js         (M3, M5, M6, M7, M8)
app/electron/panel.js                       (M6, M7, M8, M9)
app/electron/history-store.js               (M8)
app/electron/main.js                        (M8 — o meta deixava de ser deitado fora)
app/electron/worker-bridge.js               (M8 — o arm Electron levava a rota ao renderer)
app/electron/transcript-append-oracle.js    (le o sufixo como METADATA)
app/webview/sotto_webview.py                (M8 — o store da app real)
_main/caption-lines-oracle.py               (arm 11: o fecho fora de banda)
_main/history-route-oracle.js               (novo — a rota ate' ao ficheiro)
_main/segment-rerun-probe.py                (novo — a 2a passagem isolada)
```

## 6b. ESTADO NO FIM (17:45Z) — a metade de renderer foi de-landada

Este documento descreve uma cura que foi medida GREEN as 13:40Z e que **ja' nao esta' no disco**.
Medido as 17:45Z:

- `app/electron/caption-formulation.js` perdeu M5/M6/M7/M8 (zero ocorrencias das marcas; `onCommit(`
  sem `meta`; `expireHold()` a commitar outra vez). Os outros seis ficheiros da cura mantiveram-se.
- `panel.js` foi reescrito por outra lane (`docs/audit/historico-vs-redux.md`), com a intencao certa
  ("so' linha fechada pelo worker") mas com o fallback `|| 'final'` a torna-la vacua, porque o motor
  nao devolve `route`.
- Resultado no ficheiro do dono (`history/2026-10-06/14.md`): `route=final` em linhas fechadas por
  `hold-timeout` / `audio-gap`, e sem `start=`. No mesmo dia, `11.md` mostra as linhas da cura
  (`route=final start=N reason=final-pass`) — a cura funcionou e foi substituida.
- Quem apanhou: `node _main/history-route-oracle.js` -> **RED, 4 violacoes**. O oraculo de append
  continua GREEN porque **nao cobre a rota** — e' por isso que a de-landagem passou em silencio.
- Bilhete `4fb5b25380cbc8269977e22e` (P1). Nao corrigi: o ficheiro pertence a uma lane activa e este
  assento nao tem `dispatch` para coordenar.

O que continua a valer deste trabalho: o desenho M1-M9, as medicoes do §2, o oraculo que apanhou a
de-landagem, a sonda da 2a passagem e o arm 11.
