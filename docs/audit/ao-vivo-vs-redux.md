# Ao vivo vs "redux" — o dono tem razao: sao DUAS rotas, e o Sotto tem UMA

Lane: `SottoAoVivoVsRedux` · 2026-10-06 · entregavel = diagnostico, **nenhum ficheiro de produto foi tocado**
(esta lane so' escreveu este `.md`).

Pergunta do dono, verbatim:

> *"e veja por que a gente e burro e nao sabe a diferenca de usar o ao vivo (legenda ao vivo) e usar o redux
> para o historico do transcript/transcript nao ao vivo para legenda ao vivo"*

## 0. Resposta em cinco linhas

1. **A rota AO VIVO existe e tem UM produtor** — o worker (`worker/sotto_worker.py`), que manda JSONL no stdout.
2. **A rota "redux" NAO existe como rota de ASR.** A palavra `redux` no codigo **nomeia o ficheiro do
   historico** (`H:/sotto/history/<YYYY-MM-DD>/<HH>.md`), nao uma segunda passagem sobre o audio.
3. **O acoplamento e' literal:** o texto que vai para o historico **e' o mesmo objecto de string** que foi
   pintado na caixa ao vivo — `onCommit(text)` → `addCaption(text)` → `recordHistory(text)`.
   Ha' **um** call site de `recordHistory` no repo inteiro (`app/electron/panel.js:185`).
4. **Nao ha' segunda passagem nenhuma.** O unico "segundo passe" do repo e' o `selftest()` do worker
   (`worker/sotto_worker.py:1495`), que corre o **mesmo** modelo de streaming sobre um ficheiro, pela
   `--selftest`, e nao refina nada em tempo real.
5. **O custo medido:** dos 472 registos no historico do dono, **74,6 % tem 3 palavras ou menos**
   (mediana = 1 palavra) e **472 de 472 acabam em pontuacao terminal** — porque a pontuacao e' **inventada**
   pelo `formulate()` (`app/electron/caption-formulation.js:148-159`). O ficheiro *parece* frases e nao e'.

---

## 1. As duas rotas no codigo, com `file:line`

### 1.1 Rota AO VIVO — **existe**, e' a unica rota de texto que existe

| passo | onde | o que faz |
|---|---|---|
| captura → chunks de 560 ms | `worker/sotto_worker.py:2067-2070` (`buf = buf[asr.chunk :]`) | o buffer e' **descartado** chunk a chunk |
| decode | `worker/sotto_worker.py:560` `run_chunk()` | RNNT greedy por chunk |
| juncao em LINHA | `worker/sotto_worker.py:1396` `class LineFormer`, `:1454` `push()`, `:1446` `_close()`, `:1489` `flush()` | a LINHA cresce; fecha em gap de audio ≥ 8 s, 90 chars, ou pontuacao terminal |
| emissao | `worker/sotto_worker.py:1432` `_event()`, `:2096-2098` `for event in former.push(...)` | **este e' o objecto de texto da rota (1)**; `start` = **inicio da LINHA**, `end` cresce |
| flush terminais | `worker/sotto_worker.py:2052-2054` (troca de device), `:2087-2088` (excepcao), `:2100-2102` (`--max-chunks`), `:2107-2109` (stream parou) | os unicos caminhos que fecham a linha por paragem |
| shell recebe | `app/webview/sotto_webview.py:2131-2132` `on_worker_caption()` → `self.emit('caption', ...)` | ponte para a pagina (WebView2 = a app) |
| pagina → painel | `app/webview/sotto_webview.py:828-831` (`normalise` + `emit('caption', …)`) → `app/electron/panel.js:141-148` `wireCaptions()` | entrega ao motor |
| motor | `app/electron/caption-formulation.js:297-414` `ingest()`, `:401-403` LocalAgreement-2, `:413` `onProvisional` | commit vs provisional |
| pintura ao vivo | `app/electron/panel.js:108-133` `renderProvisional()` (classe `caption--provisional`, `:131`) | **reescreve a linha no lugar** — isto ja' e' o "provisorio" da UI |
| commit | `app/electron/caption-formulation.js:277-289` `commit()` → `:282` `onCommit(line, reason)`; `:430-433` `expireHold()` → `commit('hold-timeout')` | `reason` ∈ {`audio-gap Ns`, `chars N`, `hold-timeout`, `flush`} |
| painel | `app/electron/panel.js:84-85` `onCommit: (text, reason) => addCaption(text, reason)` | **`reason` e' DESCARTADO aqui** (§4.4) |
| **escrita do historico** | `app/electron/panel.js:185` `recordHistory(text)` | **o MESMO `text`** |

### 1.2 Rota HISTORICO / "redux" — **existe como STORE, nao como rota de ASR**

| passo | onde |
|---|---|
| `recordHistory()` | `app/electron/panel.js:281-296` — `historyApi.append(text, { source: 'live' })` (`:287`) |
| preload (Electron) | `app/electron/preload.js:138-150` → IPC `sotto:history-append` |
| main (Electron) | `app/electron/main.js:820-833` → `historyStore.append(payload.text)` |
| store (Electron) | `app/electron/history-store.js` `append()` → `<repo>/history/<date>/<HH>.md` |
| **app real** (WebView2) | pagina embutida `app/webview/sotto_webview.py:876-894` `window.sotto.history` → `:1166-1169` `_history_append` → `:1831-1854` `history_append()`, linha escrita em **`:1848`**: `f'- [{time}] {body}\n'` |
| layout | `app/webview/sotto_webview.py:89-101`, `HISTORY_ROOT` = `H:/sotto/history` (`SOTTO_HISTORY_ROOT` overrides) |

> A organizacao das duas rotas esta' escrita no proprio `panel.html:22-26` e `panel.js:5-9`:
> **TOP `.history` = "the accumulated transcript ("redux")"**, **BOTTOM `.captions` = "the LIVE caption box"**.
> Dois *sitios* na UI, **uma** fonte de texto.

### 1.3 O que a palavra `redux` nomeia no codigo — e o que NAO nomeia

`grep -rn "redux|batch|refine|final|repair"` sobre `H:/sotto` (case-insensitive, `app/`, `worker/`, `docs/`):

| token | onde | o que e' |
|---|---|---|
| `redux` (codigo) | `sotto_webview.py:89,876,1160,1817`; `main.js:820`; `history-store.js`; `panel.js:6`; `panel.html:23,109` | **o nome do STORE do historico** (`History · Redux` e' o rotulo da UI) |
| `redux` (docs) | `README.md:21,41,54-55`, `roadmap.md:64`, `stack-verification.md:478-514` | **o MODELO batch** `moondream/parakeet-redux` — nao esta' no repo |
| `refine` | **so' em `docs/oss-approaches-20261006.md:123,236,430`** (citacao do README do RealtimeSTT) | nenhum codigo |
| `repair` | `sotto_webview.py:1593` `_install_bootstrap('post-load-repair')` | recarregar a pagina quando o parse falha — nada a ver com ASR |
| `batch` | so' comentarios (`sotto_webview.py:3482`, `run.cmd:106,128`) | nada a ver com ASR |
| `final` | `caption-formulation.js` (`TERMINAL`, `final` em comentarios) | nao existe `final: true/false` em evento nenhum |

**Conclusao da §1.3:** o nome "redux" foi **emprestado** para o ficheiro do historico. Quem le o codigo
conclui que "o redux" e' o historico; o dono usa "redux" para **o modelo batch**. Os dois sentidos **nao se
tocam no codigo**, e e' essa a confusao que ele nomeia.

---

## 2. PROVA do acoplamento (hoje)

**O ponto exacto:**

```
app/electron/panel.js:84-85   const engine = window.SottoFormulation.createEngine({
                                onCommit: (text, reason) => addCaption(text, reason),
app/electron/panel.js:153     function addCaption(text) {
app/electron/panel.js:185       recordHistory(text);          <-- MESMA string, sem copia, sem 2o produtor
app/electron/panel.js:287       .append(text, { source: 'live' })
```

E o motor so' tem **uma** origem de texto:

```
app/electron/caption-formulation.js:277  function commit(reason) {
app/electron/caption-formulation.js:280    const line = formulate(all.map((t) => t.w).join(' '));
app/electron/caption-formulation.js:282    onCommit(line, reason);
```

**Nao ha' segundo caminho.** Prova mecanica de que **um** so' writer alimenta o historico:

```
$ grep -rn "recordHistory" app/ | grep -v node_modules
app/electron/panel.js:185:  recordHistory(text);
app/electron/panel.js:281:function recordHistory(text) {
```

Um unico call site, e o argumento e' o parametro de `addCaption`, que e' o parametro de `onCommit`, que e' a
`line` do `commit()`. **Tres saltos, zero transformacao.** O historico herda *exactamente* o que a caixa ao
vivo pintou, incluindo o corte e o erro do modelo.

**O caminho do "provisorio"** (que o dono quer que NAO entre no historico) e' este, e ele **entra**:

```
panel.js:99    engine.expireHold()                     (dispara 1500 ms depois do ultimo caption)
caption-formulation.js:430  function expireHold() {
caption-formulation.js:431    if (!provisional.length) return '';
caption-formulation.js:432    return commit('hold-timeout');      <-- o PROVISORIO vira linha COMMITADA
panel.js:186                  recordHistory(text)                 <-- e vai para o ficheiro
```

Ou seja: **o provisorio entra no historico pela porta do `hold-timeout`.** O comentario do proprio ficheiro
(`caption-formulation.js:420-429`) admite-o — *"the ONLY situation in which abandoning the hold is correct"* —
mas o que ele chama "correcto" e' correcto **para a caixa ao vivo**, e o Sotto aplica-o tambem ao ficheiro.

---

## 3. Ha' uma segunda passagem sobre o audio do segmento? **NAO.**

| candidato a "redux" | existe? | esta' ligado? | por quem |
|---|---|---|---|
| `selftest()` (`worker/sotto_worker.py:1495`) | sim | **so' por `--selftest`** (`:1845`), modo ficheiro | corre o **mesmo** modelo de streaming sobre `sample1.flac`; nao refina nada |
| `output.partial` (`worker/config.json` `output.partial: true`) | sim | **ligado** (`sotto_worker.py:1691`, `:2015`, `:1484`) | escolhe *parcial vs linha fechada* — **nao** e' uma 2a passagem |
| modelo batch (Parakeet Redux / `transcribe.cpp`) | **nao esta' no disco** (`ls worker/models/` → so' `nemotron-3.5-asr-streaming-0.6b-{int4,int8,fp16}`) | **nao** | — |
| `refine` / `repair` / `final` no codigo | **nao** | — | — |

A unica segunda passagem que existe **no mundo** e' o `_main/asr-test/` do manager scratch (fora de
`H:/sotto`), citado em `docs/audit/original-prompt-adjudication.md:85` (R7): **Parakeet v3 int8 CUDA, RTF 0.256**
vs **Parakeet Redux CUDA, RTF 0.769**. Nao ha' um unico call site disso dentro do produto.

> **O que o R7 do adjudication ja' diz, e que confirma a tese do dono:** o plano original (README `:54-55`)
> era *"Nemotron streaming while recording; **Parakeet Redux for the canonical transcript afterwards**"* — ou
> seja, **o desenho de duas rotas estava no papel e foi abandonado**. O que ficou foi a rota (1) escrevendo no
> sitio que era da rota (2).

---

## 4. Custo medido do acoplamento

> **PINO DE MEDICAO — leia antes dos numeros.** As contagens desta seccao estao presas ao estado da
> arvore NO MOMENTO em que foram feitas, e a arvore MEXEU durante esta lane: `git status` mostra
> `app/electron/caption-formulation.js`, `app/electron/panel.js`, `app/webview/sotto_webview.py` e
> `worker/sotto_worker.py` modificados **por outras lanes**, em paralelo. Re-censo no fim da lane, pelo
> mesmo comando, sobre TODOS os ficheiros que entretanto apareceram:
>
> | ficheiro | registos | terminam em pontuacao |
> |---|---|---|
> | `06.md` | 124 | 124 |
> | `07.md` | 13 | 13 |
> | `09.md` | 330 | 330 |
> | `10.md` | 54 | 35 |
> | `11.md` | 49 | 0 |
> | `14.md` | 65 | 0 |
> | `15.md` | 247 | 0 |
> | **TOTAL** | **882** | **502** |
>
> Ou seja: a populacao passou de 472 para 882 e **a propriedade "472/472 em pontuacao terminal" deixou de
> valer** para tudo o que foi escrito depois das 11h. **Nao atribuo a causa** — nao sei se outra lane
> mexeu no `formulate()`, se foram escritos por outro caminho, ou os dois; as duas coisas sao
> observaveis por terceiros com o comando do §8, ponto 3. O que isto prova e' a tese do §6.2 pelo lado
> negativo: **nada no repo vigia a FORMA deste ficheiro**, por isso ele muda de forma sem que nenhum gate
> fique vermelho. Quem implementar o §5 deve re-correr os censos antes, nao reusar estes numeros.

Tudo abaixo foi medido nesta lane, hoje, sobre os ficheiros do proprio dono (`H:/sotto/history/`), com
`python` (nao `grep -E`, que o box ignora).

### 4.1 Contagem directa dos 4 ficheiros

| ficheiro | registos | pares "prefixo do seguinte" (duplicacao) | mtime (UTC) |
|---|---|---|---|
| `history/2026-10-06/06.md` | 124 | **83** (67 %) | 09:51:08 |
| `history/2026-10-06/07.md` | 13 | **7** (58 %) | 10:02:08 |
| `history/2026-10-06/09.md` | 330 | 1 | 12:59:34 |
| `history/2026-10-06/10.md` | 5 | 0 | 13:02:26 |
| **total** | **472** | — | — |

`app/electron/caption-formulation.js` tem `mtime = 12:23:59Z`. Logo **06 e 07 sao ANTERIORES a cura**
(`emittedStart`/`emittedWords`, `caption-formulation.js:218-239,376-395`) e **09 e 10 sao POSTERIORES**.
A cura da **duplicacao** funcionou — e o oracle do repo diz o mesmo:

```
$ node app/electron/transcript-append-oracle.js
RESULT: GREEN — every worker line is appended once, in order, word for word
```

### 4.2 O que a cura NAO resolveu — e e' o defeito do dono

Os ficheiros **posteriores a cura** continuam a ser **salada de fragmentos**:

```
history/2026-10-06/10.md   (post-cura, 13:02)
- [10:02:12] Going alo slas Country Roads and Speaking to.
- [10:02:15] Day.
- [10:02:18] An appearance.
- [10:02:22] Sunday morning and he he can come to immediate.
- [10:02:26] Roads.
```

A duplicacao sumiu (o `agreedPrefixLength` corta o prefixo ja' escrito) — mas o que sobra e' **a cauda da
frase sem a cabeca**. A frase do modelo foi `"...Going along slushy Country Roads and speaking to day after
day an appearance..."`; o historico ficou com **cinco linhas**, cada uma um pedaco, **nenhuma** delas uma frase.

Censo agregado dos 472 registos:

```
$ python -c "...median/<=3 words/terminal..."
entries 472
<=3 words: 352      (74.6 %)
median words per entry: 1
ends in terminal punctuation: 472  (472/472 = 100 %)
starts lowercase: 0
```

**472 de 472 acabam em `.` `?` `!` `…` — e isso e' fabricado.** `formulate()`
(`app/electron/caption-formulation.js:148-159`) acrescenta um full stop quando a linha nao tem pontuacao
terminal. Consequencia dura: **o ficheiro do historico nao permite distinguir uma frase que o worker fechou
de um fragmento cortado pelo `hold-timeout` de 1500 ms.** A pontuacao mente.

### 4.3 O mecanismo do corte (porque a linha do historico nao e' a linha do modelo)

Duas fronteiras **diferentes** decidem onde a linha acaba, e a do historico e' a mais cedo:

| fronteira | valor | onde | relogio |
|---|---|---|---|
| worker fecha a LINHA | gap **8 s** de audio / 90 chars / pontuacao | `sotto_worker.py:1386,1390,1393` (constantes) e `:1460-1486` (as 3 regras do `push()`) | **audio** |
| painel fecha a linha do painel | **1500 ms** sem caption novo | `caption-formulation.js:99`, `panel.js:95-101` | **parede** |

O painel fecha **antes** do worker em qualquer pausa > 1,5 s — e o Sotto escreve no historico o que o painel
fechou. A fronteira do **historico** e' portanto uma funcao da **cadencia de entrega do ao vivo**, nao do audio.

### 4.4 Dois achados laterais, medidos, que custam correccao barata

- **`reason` e' calculado e jogado fora.** `panel.js:85` passa `(text, reason)`;
  `panel.js:153 function addCaption(text)` **nao recebe `reason`**. O motivo do commit
  ({`audio-gap`, `chars`, `hold-timeout`, `flush`}) existe no momento exacto da escrita e nao vai para o
  ficheiro — e' a proveniencia que falta para auditar o historico. Ja' esta' pago.
- **`{ source: 'live' }` e' jogado fora duas vezes.** `panel.js:287` envia
  `historyApi.append(text, { source: 'live' })`; `app/electron/main.js:824` chama
  `historyStore.append(payload.text)` e `app/webview/sotto_webview.py:1168` chama
  `self._shell.history_append(payload.get('text', ''))` — **o segundo argumento nao existe no destino**.
  O painel ja' **declara a proveniencia** e ninguem a guarda.
- **O auto-teste do shell escreve no historico REAL do dono.** `sotto_webview.py:2290-2291` injecta
  `'A legenda ao vivo SOTTO-V2-<stamp>.'` e o caminho e' o caminho normal: **5 dessas linhas estao hoje em
  `06.md` (4) e `07.md` (1)**. Um teste que suja o artefacto do dono.

---

## 5. Desenho minimo, em forma mecanica

Regra: **so' a rota (2) escreve no historico, e so' depois da linha fechar sobre o audio INTEIRO do segmento.**
A chave do desenho ja' existe e ja' e' enviada: **`start` e' a identidade da LINHA** (`sotto_worker.py:1436-1437`:
*"`start` is the START OF THE LINE, never the newest chunk's start"*). Todas as alteracoes abaixo sao 1:1 com
esse campo.

### 5.1 Worker (`worker/sotto_worker.py`)

```
M1  Guardar o PCM do segmento corrente.
    Onde: asr_thread(), junto ao `former` (`:2015`). Um `bytearray` com os samples 16 kHz mono float32
    desde `former._start` ate' `former._end`. O buffer que HOJE e' descartado (`:2070 buf = buf[asr.chunk:]`)
    nao serve — precisa de um buffer PROPRIO do segmento, alimentado com `seg_in` depois do AGC.
    Custo de memoria: 16000 * 4 B/s = 64 000 B/s  ->  10 s = 640 000 B (625 KiB); 30 s = 1,875 MiB.

M2  Marcar o evento com a rota.
    `_event()` (`:1432`) passa a levar `"final": False` nos parciais.
    `_close()` (`:1446`) NAO emite o texto: emite so' `{"type":"caption","final":False,"text":<partial>,
    "start":<linha>,"end":<linha>}` e DEIXA o fecho para M3.

M3  Segunda passagem sobre o audio do segmento INTEIRO, e e' ELA que emite `final: True`.
    No `_close()`: correr o mesmo `asr.run_chunk()` sobre o buffer do segmento (M1), com o estado RNNT
    RESETADO, agregando com o MESMO `LineFormer` (por isso o resultado tem as mesmas regras de fronteira);
    emitir UM evento `{"type":"caption","final":True,"text":<texto do 2o passe>,"start":<linha>,"end":<end>}`.
    O texto do 2o passe substitui o provisorio do painel e e' o unico que vai ao historico.

M4  O provisorio continua a sair (`emit_partial`), mas nunca com `final: True`.
    E' o que ja' acontece hoje — muda o rotulo, nao o fluxo.
```

### 5.2 Renderer (`app/electron/caption-formulation.js` + `panel.js`)

```
M5  `ingest(text, meta)` le`meta.final` (`caption-formulation.js:297-302`).
    final=true  -> ingestao actual (commita e chama onCommit)
    final=false -> SO' `onProvisional` (reescreve a linha da caixa ao vivo); NUNCA chama `onCommit`.

M6  `expireHold()` (`caption-formulation.js:430-433`) DEIXA de chamar `commit()`.
    Passa a marcar a linha como nao-confirmada (`onProvisional(text, true)`) e a RE-ARMAR o deadline.
    O `hold-timeout` deixa de ser um caminho para o historico. Para o stream que morre de facto existe o
    `flush()` (`:417-419`), que o worker chama em todos os caminhos terminais
    (`sotto_worker.py:2052-2054,2087-2088,2100-2102,2107-2109`)
     — esse JA' fecha a linha e e' o unico caminho terminal legitimo.

M7  `panel.js:153` passa a `function addCaption(text, reason)` e `recordHistory(text, reason)` (`:185`).
    O `reason` — que JA' e' calculado e JA' e' jogado fora (§4.4) — entra na linha do historico.

M8  Formato da linha do historico, com proveniencia e com chave de substituicao:
       - [HH:MM:SS] text            <!-- route=final start=<s> -->
    e, para o caso de reconcilizacao, `route=provisional-draft start=<s>`.

M9  O provisorio vai para a caixa ao vivo com a classe que JA' EXISTE (`caption--provisional`,
    `panel.js:131`), e a UI diz o que ela e' (ex.: `·` a seguir ao texto). Nao ha' CSS novo a inventar.
```

### 5.3 O que fica de fora, deliberadamente

- **Nao** subir `COMMIT_MAX_HOLD_MS` (1500 ms) para os 8 s do worker: isso muda QUANDO a legenda aparece,
  e o dono quer a legenda ao vivo rapida. Este desenho **nao toca na latencia do ao vivo**: M5-M9 so'
  decidem o que **sai** para o ficheiro.
- **Nao** reordenar a UI nem o store: `history_append` continua append-only para o caso normal.

---

## 6. Custo por segmento (ms) — e se o modelo que ja' temos chega

### 6.1 O que esta' medido neste repo (nao estimado)

| numero | valor | fonte |
|---|---|---|
| hop de chunk | 560 ms | `chunk_samples: 8960` @ 16 kHz (`docs/model-specs/README.md`) |
| PCM por segundo | 64 000 B/s (16 kHz mono float32) | aritmetica de `sotto_worker.py` |
| **RTF, fala real, este box, modelo int8** | **0,14 – 0,22** | `worker/runs/*.jsonl` `selftest-done` sobre `sample1.flac`: 0,142 / 0,164 / 0,166 / 0,193 / 0,198 / 0,210 / 0,219 / 0,224 |
| RTF, runs ao vivo (com silencio) | 0,10 – 0,14 | `worker/runs/live-*.jsonl` |
| RTF, pior CPU medido | 0,652 – 0,744 | `worker/runs/gpu-int8-cpu*.jsonl` |
| modelo batch alternativo (Parakeet Redux, CUDA) | RTF **0,769** | `docs/audit/original-prompt-adjudication.md:85` (scratch do manager, **fora** de `H:/sotto`) |
| modelo batch alternativo (Parakeet v3, CUDA) | RTF **0,256** | idem |

### 6.2 Custo da segunda passagem, com o modelo que ja' temos

Custo ≈ `RTF x S` (segundos de audio do segmento) + reset de estado, sobre um modelo **ja' residente**
(int8: RSS ~1192 MB medido, `AGENTS.md`) — **sem download, sem segundo modelo**.

| segmento `S` | custo 2o passe @ RTF 0,15 | @ RTF 0,25 | memoria PCM retida |
|---|---|---|---|
| 5 s | ~0,75 s | ~1,25 s | 320 KiB |
| 10 s | ~1,5 s | ~2,5 s | 625 KiB |
| 30 s | ~4,5 s | ~7,5 s | 1,875 MiB |

*(a interpolacao `RTF x S` a partir dos RTF medidos e' `[INFERENCE]` — a medicao directa seria correr a
`--selftest` sobre um segmento isolado; nao foi corrida nesta lane.)*

**Isto cabe no orcamento?** Para o **historico**, sim: o 2o passe e' *off the critical path* — a legenda ao
vivo ja' apareceu, e o texto final chega ~1-2,5 s depois do fecho da linha. **Mas nao cabe no caminho do
audio** se correr na mesma thread: o `asr_thread` fica 1-2,5 s sem consumir `audio_q`, e a fila e' limitada
(`audio_q = queue.Queue(maxsize=256)` em `sotto_worker.py:1887`; bloqueia 100 ms cada, logo 25,6 s de folga;
o contador `queue_drops` esta' em `:1996-1997`). **Decisao que falta medir** (NAO-VERIFICADO §7): um
`InferenceSession` do onnxruntime e' seguro para `Run()` concorrente, mas **neste repo ha' UMA thread e o
padrao nao foi provado**. Se nao for, a alternativa e' um 2o processo → **+1192 MB de RSS** (medido).

### 6.3 Chega o modelo que ja' temos?

**Para metade, e e' preciso dizê-lo com precisao:**

- **Chega para tirar o CORTE** — sim. Re-decodificar o segmento INTEIRO (em vez de um prefixo que ia a meio)
  e' exactamente o que o modelo de streaming consegue fazer sozinho, com o contexto completo (`left_context:
  70`, `worker/config.json` → `models/nemotron-3.5-asr-streaming-0.6b-int8`). Nao precisa de modelo novo.
- **Chega para tirar o ERRO** — **nao**. E' o **mesmo checkpoint**; re-decoding nao corrige
  `"Going alo slas"` para `"Going along slushy"`. Para "estar CERTO" o dono precisa de um modelo **batch**
  (`docs/roadmap.md:64`, `README.md:54-55`: Parakeet Redux), que **nao esta' no disco** e que
  `docs/stack-verification.md:514` mede como **nao carregavel** por um `transcribe.cpp` upstream sem fork.
- **Ordem barata-primeiro:** M1-M9 com o modelo actual **ja' entrega a rota (2) correcta em arquitectura**
  (fronteira no audio, provisorio fora do historico, proveniencia no ficheiro) e troca-se o motor da 2a
  passagem por um batch mais tarde, **sem tocar na fronteira**.

---

## 7. NAO-VERIFICADO (explicito)

1. **Seguranca de concorrencia do `InferenceSession` ORT neste repo.** Nao corri nada; nao ha' prova
   medida aqui de que `Run()` concorrente seja seguro com este export. Decide o desenho do §6.2.
2. **O custo real da 2a passagem.** A tabela do §6.2 e' `RTF x S` **[INFERENCE]** a partir de RTF medidos
   noutro contexto (ficheiro inteiro vs segmento isolado). Falta medir: `--selftest` sobre um segmento curto
   com o estado resetado a cada segmento.
3. **Onde exactamente nasce a fronteira do worker em producao.** Li as constantes (`SENTENCE_GAP_S = 8`,
   `SENTENCE_MAX_CHARS = 90`, `LINE_TERMINAL = ".!?…"`, `sotto_worker.py:1386-1394`) e o `push()`
   (`:1454-1488`), mas **nao** corri uma sessao ao vivo para ver qual das tres regras fechou cada linha
   concreta. Os motivos estao calculados em cada `commit(reason)` e **nao sao escritos em lado nenhum**
   (§4.4) — e' precisamente por isso que este numero nao existe.
4. **Onde entram as linhas japonesas de `09.md`** (330 registos, 1-2 palavras). A amostra mostra decodes em
   japones sobre audio que nao era japones; **nao** investiguei `lang_id` (`worker/config.json` = `"auto"`)
   nem o routing de dispositivo dessa sessao — esta' fora do escopo desta lane e ja' tem dono
   (`docs/audit/audio-escopo.md`). Fica registado porque move a estatistica dos 472.
5. **Se os 5 `SOTTO-V2-<stamp>` em `06.md`/`07.md` sao o unico lixo de teste no historico do dono.**
   Medi esses 5 por string; nao sei se outros probes escreveram com outro texto.
6. **A contagem por ficheiro pressupoe** que uma linha do historico == um `history_append`. Nao ha' prova
   de que nao houve escrita parcial num crash; a estrutura `- [HH:MM:SS] texto` e' consistente nos 472,
   o que e' evidencia, nao prova.

---

## 8. Como refutar este documento (oracle re-executavel)

```bash
# 1. O acoplamento: se aparecer um SEGUNDO call site de recordHistory, o §2 cai.
grep -rn "recordHistory" H:/sotto/app/ | grep -v node_modules     # espera-se: panel.js:185 e :281

# 2. Nao existe rota redux de ASR: se aparecer um 2o consumidor do modelo, o §3 cai.
ls H:/sotto/worker/models/                                        # espera-se: so' os 3 nemotron

# 3. A pontuacao era fabricada em TODAS as linhas medidas no §4 (472/472) => o ficheiro nao distinguia
#    frase de fragmento. HOJE a propriedade ja' NAO vale para tudo (ver o PINO DE MEDICAO no §4):
#    o comando imprime dois numeros e o segundo deixou de igualar o primeiro.
python -c "import re,glob;R=re.compile(r'^-\s+\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$');rows=[m.group(2) for p in glob.glob('H:/sotto/history/*/*.md') for m in (R.match(l.rstrip()) for l in open(p,encoding='utf-8',errors='replace')) if m];print(len(rows), sum(1 for t in rows if t[-1] in '.!?…'))"

# 4. A duplicacao FOI curada (o resto e' fragmentacao, nao duplicacao).
node H:/sotto/app/electron/transcript-append-oracle.js            # espera-se GREEN
```

**Nota de instrumento (para nao repetir um erro):** `grep -E` e' **ignorado** neste box (uutils), pelo que
todas as contagens deste documento foram feitas em `python` ou em `grep` sem `-E`. Uma contagem feita com
`grep -E` devolveria **0 pares** e sustentaria a conclusao oposta.
