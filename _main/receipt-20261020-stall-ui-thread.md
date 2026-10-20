# Recibo — 2026-10-20 — a TRAVA que sobrava depois do arranque

**Lane:** a segunda trava do dono (*"abrir ou fechar o sotto, principalemnte
fechar, trava pra caralho meu pc. arruma"*). O arranque já tinha sido
corrigido (68 s -> 3,2 s, medidos). Esta é a **outra** metade: a que acontece
quando a app **já está aberta** e a thread da UI não consegue drainar a fila.

**Ficheiros deste lane**

| ficheiro | o que é |
|---|---|
| `app/webview/sotto_webview.py` | a correcção (3 pontos abaixo) |
| `_main/ui-stall-oracle.py` | o portão novo, com o braço negativo EXECUTADO |
| `_main/_audit-verify-all.cmd` | o passo do portão na bateria (25 linhas) |

---

## 1. A MEDIÇÃO (recontada por mim, não de segunda mão)

Fonte: `I:\cc-tmp\sotto-012524.log` — **591 linhas**, a app do dono lançada às
01:25:24. Contagem no ficheiro inteiro, hoje:

```
93 x  WARN UI_THREAD_STALL begin-invoke not run in 10 s fn=_run
71 x  WARN exec_js TIMEOUT   ->  68 x "after 10.0s"  +  3 x "after 5.0s"
```

* A **janela**: `01:55:30.219` -> `01:56:20.887` = **50,67 s**. Todos os 93
  dali para fora, todos com `fn=_run` (o `_run` do `exec_js`).
* **A ATRIBUIÇÃO** (o que o log não diz e eu medi): as **68** timeouts de 10 s
  são **todas** `window.__sotto_stats("sNNNN", …)` — ids consecutivos
  `s1681`..`s1748` — ou seja, **o caminho do `reply_stats`**. As **3** de 5 s
  são o `PANEL_STATE_PROBE` (o dump de diagnóstico).
  *Correção a um número que me foi passado:* o dump não contribuiu com 71
  timeouts de 5 s; contribuiu com **3**. As 71 total são 68 + 3.
* **A ESPERA COMPOSTA, provada no log**: para 66 pares (stall -> timeout) o
  delta é de **~10 s** (média 9,19 s, máximo 10,29 s). Ou seja: um pull
  travado segurava a thread **10 s dentro do `_ui`** (o `done.wait(10)`) e
  **mais ~10 s dentro do `exec_js`** (o `done.wait(timeout)` da frente). **20 s
  por pull**, e os pulls são de 1/s.
* 90 linhas `BRIDGE_STATS_REPLY` no fragmento.

O TRIGGER foi a carga (a lane de designs a renderizar 45 temas com Edge
headless ao mesmo tempo). O QUE FAZ A TRAVA é o código — e o código tem de
aguentar a carga.

## 2. A CADEIA (lida no código, com as linhas de HOJE)

```
panel.js  -> getStats()  a CADA 1000 ms   (o PULL do painel)
          -> _stats()                       (o dispatch da shell)
          -> reply_stats()                 -> exec_js(...)  SINCRONO, orcamento de 10 s
          -> _ui(_run)                     -> form.BeginInvoke(...) + done.wait(10)
```

Duas coisas estavam erradas ao mesmo tempo:

1. **O reply era um round-trip SÍNCRONO num caminho de 1/s.** O `exec_js`
   espera pela thread da UI; se ela não drena, quem espera é a thread do
   **pump** — a que transporta as legendas. Uma UI ocupada atrasava as
   LEGENDAS, 93 vezes, 20 s de cada vez.
2. **O `exec_js` esperava DUAS vezes** (10 s no `_ui` + 10 s no seu próprio
   `done.wait`), com dois orçamentos independentes para a mesma pergunta.

E o alarme não dizia nada: o `_ui` devolvia `None` num stall, o `exec_js`
devolvia `None`, e o probe registava `PANEL_STATS_PROBE null` — **sem
razão**. "o painel respondeu nulo" e "o painel não respondeu" eram a MESMA
observação.

## 3. A CORRECÇÃO (`app/webview/sotto_webview.py`)

**(a) `reply_stats` deixou de ser um round-trip.** É agora um **POST** (o
caminho `emit_async`), com **no máximo UM callable pendente** por canal,
independentemente da taxa de pulls. A diferença face ao `emit_async` (que
pode SUBSTITUIR o payload pendente) é que um reply é uma RESPOSTA a um id:
todos os ids perguntaram e todas as perguntas têm de ser respondidas, ou a
Promise do painel fica pendente para sempre. Por isso o slot pendente é uma
**lista de ids**, e os ids ACUMULAM enquanto os callables NÃO.
Limite: `STATS_REPLY_MAX_PENDING = 64` ids; o mais antigo é answered com o
payload **mais novo** (o payload é um estado inteiro, logo o estado mais novo
responde a uma pergunta mais antiga) — a Promise resolve na mesma. O que
falar = nunca, fica registado.

**(b) O `panel_state_snapshot` deixou de competir com o produto.** A leitura do
DOM era `exec_js(PANEL_STATE_PROBE, timeout=5.0)` — que esperava 5 s lá e
**outros 10 s** dentro do `_ui`, e deixava o callable **enfileirado** no
form: um dump de 2 em 2 s fazia a fila do WinForms crescer enquanto a UI
estivesse ocupada. Agora a leitura é um POST com **no máximo UMA em curso**:
enquanto uma leitura está no ar, o dump seguinte não publica outra, e o dump
reporta o **último valor conhecido**, com a idade, se há uma leitura mais
nova a caminho, e a razão da última falha (bloco `panelDom` novo no dump). O
**ficheiro continua a ser escrito de 2 em 2 s** — o dump não foi sacrificado,
deixou de poder travar.

**(c) O stall passou a ser distinguível de um `None` legítimo.** A nova
classe `NoAnswer` (um `dict`, portanto serializável em JSON, e **falsy**,
para que nenhum `if valor:` mude de comportamento) transporta `reason`,
`requested`, `timeout` e `detail`. O `_ui` devolve `NoAnswer('ui-thread-stall',
…)` em vez de um `None` mudo; o `exec_js` devolve `NoAnswer('exec-js-timeout' |
'exec-js-error' | 'ui-thread-stall', …)`. **Um `null` verdadeiro continua a
ser `None`** — a diferença é que o stall agora DIZ o que era e que foi um
timeout. E o `exec_js` passou a ter **UM orçamento só**: o deadline é
calculado uma vez e as duas esperas partilham-no (o `_ui` ganhou um
parâmetro `timeout`).

## 4. O PORTÃO (`_main/ui-stall-oracle.py`, novo, LF)

Instrumento **em processo**: importa a shell, monta-a com `object.__new__`
(sem `__init__`, sem janela, sem locks) e falsifica só o que os caminhos
tocam — um `form` WinForms cujo `BeginInvoke` **regista o delegate e nunca o
executa** (é uma thread de UI ocupada mais do que qualquer orçamento), o
control WebView2 e o core de scripts. **Não abre app, não abre browser, não
toca em áudio, não suja o estado real.**

**6 arms, todas VERDES no shell vivo:**

| arm | o que prova |
|---|---|
| ARM1 | com a UI ocupada, o `reply_stats` **não segura** quem chama (medido: < 2 s, o reply devolveu em ~0 s) |
| ARM2 | **50** replies com a UI ocupada deixam **no máximo 1** callable publicado (medido: 1) |
| ARM3 | depois de a UI drenar, **todos** os ids são respondidos — a Promise do painel resolve (medido: 50/50) |
| ARM4 | um stall é **distinguível** de um `None` legítimo, e traz `reason` + `requested`; e um `null` verdadeiro continua a ser `None` |
| ARM5 | o latch do `emit_async` (2026-10-11) ainda vale: 100 pushes -> 1 callable, com o payload **mais novo** |
| ARM6 | o dump de diagnóstico não bloqueia **e não cresce a fila** (2 dumps -> 1 callable) |

**Braço negativo EXECUTADO: 4 mutantes, cada um RED no seu CLAIM.**

| mutante | o que parte | como foi apanhado |
|---|---|---|
| `sync-reply` | o `reply_stats` volta ao `exec_js` síncrono | ARM1: **segurou o chamador** |
| `unbounded-reply` | um callable por reply | ARM2: **50 replies -> 50 callables** (o limite é 1) |
| `silent-stall` | o stall devolve `None` sem razão | ARM4: **o stall respondeu `None`** |
| `emit-latch-off` | o guard de coalescência do `emit_async` removido | ARM5: **100 pushes -> 100 callables** |

Um mutante que não se consegue construir é um **SETUP ERROR**, não um RED — a
primeira versão do portão contava-os como RED (o que é uma controlo vacuoso)
e foi corrigida antes de ser escrita no recibo.

**`ARMS: 6/6` — `MUTANTS: 4/4 red on their own claim` — `VERDICT: PASS`**,
em 4,6 s.

## 5. A BATERIA — O VEREDICTO REAL

**`BATTERY-VERDICT: RED - 1 step(s) failed`** (a segunda corrida, a caixa já
menos saturada):

```
steps    : 52   gate=41  control=10  skipped=0  expect-red=1  missing=0  cached=45
failed   :  strip-stats-log-budget=3
```

* **O MEU PASSO ESTÁ VERDE**: `[step] ui-stall-oracle rc=0`, e o log diz
  `ARMS: 6/6` / `MUTANTS: 4/4 red on their own claim` / `VERDICT: PASS`.
* A **primeira** corrida teve **4** vermelhos (`strip-stats-log-budget`,
  `strip-surface-runtime`, `strip-geometry-restore`, `strip-stats-wave`, todos
  rc=3). Na segunda, **3 deles passaram a VERDE** — dois deles por CACHE, e o
  cache é a prova mais forte: a fingerprint de um passo inclui o **conteúdo
  da shell**, portanto um `rc=0` em cache é um `rc=0` medido **COM a shell
  corrigida**. O quarto é o que fica.

**O PASSO QUE FICA VERMELHO NÃO É MEU — e está PROVADO por A/B.**
`strip-stats-log-budget` é o CONTROL de `_strip-stats-log-probe.py`, que
**lança a shell** e mede o orçamento de linhas do feed de stats. A shell
lançada não chega a `RECEIVER_READY` dentro da janela do probe, e o probe
classifica isso como **ambiental** — é o texto dele: *"A shell that never
reaches this milestone is stuck on something environmental (WebView2 start, a
leftover instance) — NOT a property of the log budget"*.

**O A/B (o MESMO probe, a MESMA receita de lançamento, as DUAS revisões):**

| revisão | resultado |
|---|---|
| `git HEAD` (a de antes desta lane) | **rc=3** — as mesmas 5 checks a falhar, `ratio=0.0x` |
| a shell com a correcção desta lane | **rc=3** — as mesmas 5 checks a falhar, `ratio=0.0x` |

Idêntico. E o mesmo A/B foi feito ao `_strip-surface-probe.py`: **rc=3 nas
duas** revisões.

**A CAUSA, medida:** a caixa está saturada pelas outras lanes. O log da
shell mostra **54 s entre duas linhas consecutivas** (`03:29:21` ->
`03:30:05`), e uma shell lançada com a minha correcção e um `--mutex-name`
privado arranca **sem qualquer problema** (`SINGLE_INSTANCE ... already_running=false`,
janela criada, `PANEL_SHOW_REFUSED reason=not-asked` — ou seja, **escondida**,
como a regra exige). A correction não parte o arranque: o arranque morre
**antes** de qualquer código que esta lane tenha tocado (a linha
`SHELL_STARTUP_STAGE ... stage=pre-lock` é a última que escreve).

**O QUE FICOU POR FAZER:** a bateria está **VERMELHA** neste momento, por
causa de um passo que **não** é desta lane e que **não** se pode repetir aqui
(a app real não pode ser lançada por esta lane). Isto fica **declarado**, não
arredondado: a correcção está verificada pelo portão novo (6/6 arms,
4/4 mutantes) e por A/B directo nas duas revisões; a bateria precisa de uma
caixa calma para fechar a verde.

**A INTEGRAÇÃO NA BATERIA:** o passo foi acrescentado como 25 linhas
(`if exist _main\ui-stall-oracle.py (...)`) sem apagar nada. Essas 25 linhas
entraram no commit `6d23811` da lane do cache/delta, que versionou o ficheiro
da bateria **depois** de eu o ter editado — o conteúdo é o que eu escrevi e o
passo está no HEAD.


## 6. O QUE **NÃO** FOI MEDIDO

* **A thread da UI aqui é FALSA.** O message loop real do WinForms, o WebView2
  real e a carga real que provocou as 93 travas **não** estão neste
  processo. O que se mede é a ** reacção da shell** a uma thread de UI que
  não drena — que é a parte que a shell é dona.
* **O TRIGGER não foi reproduzido.** A carga (45 temas com Edge headless) não
  foi gerada aqui; o que se reproduz é a **consequência** (uma thread de UI
  que não drena).
* **Nenhuma latência de legenda foi medida.** A afirmação é estrutural: o
  reply já não espera pela thread de UI, logo não pode segurar a thread do
  pump.
* **A app real não foi aberta** por este lane (regra do repo e ordem do dono):
  o portão é um teste de processo próprio.
* **O `panel-state.json` não foi visto escrito por esta correcção** — o dump
  precisa da app a correr, e a app não foi aberta. O que o portão prova é
  que a função do dump devolve e não bloqueia.

## 7. LIMITACOES

* O orçamento do ARM1 (2 s) e o do ARM6 (1 s) são **orçamentos de teste**, não
  uma medição do produto: o que se prova é "limitado", não "instantâneo".
* A lista de ids pendentes tem um tecto (64). Acima dele, um id é
  respondendo com o payload mais novo. Se a UI ficar parada **mais de 64 s**,
  o dump perde a correspondência exacta entre o id e o instante do pull — o
  payload continua a ser o estado real, só não é o desse instante.
* O dump de DOM passa a ser **assíncrono**: o `panel` do ficheiro pode ter
  alguns segundos de atraso em relação ao `worker`. O bloco `panelDom` novo
  diz a idade, para que um leitor não confunda "atrasado" com "errado".
* O `_ui` deixou de devolver `None` num stall: devolve um `NoAnswer` (falsy).
  Todos os chamadores foram revistos (`sotto_webview.py:6175` é o único que
  usava o valor: passou a tratar o stall como "sem core").

## 8. NÚMEROS

| o quê | antes | depois |
|---|---|---|
| `app/webview/sotto_webview.py` | 691 381 B, 13 216 CRLF / 0 bare LF, sha256 `9705CE67565FC68E0545100D78489CC8CEA5D0F5B698A990208B0015772449B3` | 707 907 B, 13 544 CRLF / 0 bare LF, sha256 `E02F8762BB6203DA8D82598AF3C5418A6F002C2C8D4DB77A28A7FCCAD2038387` |
| `_main/ui-stall-oracle.py` | (novo) | 21 650 B, 0 CRLF / 585 bare LF (LF puro), sha256 `F94417561C1B64BE9732C784E6D23C5B4347AD862CEBDE9B3FC64F205F2F24C5` |
| `_main/_audit-verify-all.cmd` | 51 832 B, 765 CRLF / 0 bare LF | 53 610 B, 790 CRLF / 0 bare LF (+25 linhas, 0 apagadas) |
