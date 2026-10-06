# Receipt — SottoPanelPaintsVerdict (lane do buraco que duas lanes nomearam e nenhuma possuiu)

Repo `H:/sotto`. A pergunta: **o shell WebView2 PINTA o veredicto que o worker escreve?**

`_main/panel-exit3-oracle.py` (lane `SottoExit3Panel`) afirma que o shell pinta um worker MORTO
como erro, e alimenta-o com um STATUS `silent-device`. `_main/verdict-order-oracle.py` (lane
`SottoVerdictShadow`) afirma que o `done.verdict` do WORKER bate com o exit code. O receipt dela
diz, verbatim: `falta_no_gate: The oracle checks the WORKER's word vs code, not that the
panel/shell renders it`. Nenhuma das duas alimentou ao shell a linha REAL que o worker escreve
no fim de um run exit-3 — o `done` com `verdict=silent-device`. Este receipt fecha isso.

## 1. O veredicto conhecido (exit 3) chega PINTAADO como erro — medido no DOM real

`py -3 _main/panel-exit3-oracle.py` → `verdict PASS`, `failures []`. ARM B (worker forçado num
device silencioso, exit 3), DOM lido pelo probe da própria shell:

```
rendered.text      = "Worker stopped (exit 3) - Worker finished on silent-device"
rendered.className = "status status--error"        rendered.error = true
placeholderTitle   = "Worker stopped"
placeholderBody    = "verdict=silent-device device=Mapeador de som da Microsoft - Input
                      peak=0.000122 blocks=60 captions=0 tokens=0 chunks=10 rotations=0 …"
status_applied_tail= [ "Silent audio device - Mapeador de som da Microsoft - Input [MME]
                        peaked 0.000122 < floor 0.002",
                       "Worker finished on silent-device",
                       "Worker stopped (exit 3) - Worker finished on silent-device" ]
```

A ARM A (worker vivo) no mesmo ficheiro: `text="Receiving captions"`, `error=false`,
`live=true`, `captions=8`. As duas cores saem na MESMA invocação.

## 2. O braço discriminante: um `done` cujo veredicto a shell NÃO conhece

Novo `arm0_done_verdict` no MESMO oracle (não há um terceiro), a alimentar `WorkerBridge._consume`
— o canal por onde a página é pintada — com a linha `done` real:

| caso | kind | footer | placeholder |
|---|---|---|---|
| `done` + `verdict=silent-device` (a linha real do exit 3) | **error** | `Worker finished on silent-device` | `verdict=silent-device device=… ` |
| `done` + veredicto que ninguém ensinou (`a-verdict-this-shell-never-learned`) | **error** | `Worker finished on a-verdict-this-shell-never-learned` | `verdict=…` |
| `done` + **SEM veredicto nenhum** | **error** | `Worker finished on an UNKNOWN verdict - the worker never said it transcribed` | `device=… peak=… blocks=…` |
| controlo positivo: `done` + `captions-emitted` | **busy** | `done` | (neutro) |
| sequência real `silent-device` → `done` no MESMO bridge | **error** | `Worker finished on silent-device` | `verdict=silent-device device=…` |

O controlo positivo existe para que a arm não possa passar pintando TUDO a vermelho.

## 3. O DEFEITO (e a linha que mudou)

`app/webview/sotto_webview.py:146` — `worker_status_kind` lia

```python
if verdict and verdict not in HEALTHY_DONE_VERDICTS:      # ANTES
```

`verdict and` era o swallow um nível abaixo: um `done` sem veredicto (ou com veredicto vazio)
**saltava** o teste, caía no `FAILURE_WORDS_RE` — que não contém a palavra `done` — e o painel
pintava o token nu `"done"` com o mesmo estilo NEUTRO de um fim saudável. Um worker que nunca
disse que transcreveu era mostrado no único estado que significa que transcreveu. A regra do
contrato já era a forma POSITIVA; o código dizia outra coisa.

```python
verdict = str((message or {}).get('verdict') or '').strip()
if verdict not in HEALTHY_DONE_VERDICTS:                  # DEPOIS  (sotto_webview.py:153-155)
    return 'error'
```

`app/webview/sotto_webview.py:168-178` — `worker_status_text` ganhou a frase do caso sem
veredicto (antes sairia `Worker finished on None`, o f-string de uma chave ausente):
`Worker finished on an UNKNOWN verdict - the worker never said it transcribed`.

**Mapeamentos da shell alterados:** exactamente dois, ambos no bloco `done`:
`worker_status_kind` (`app/webview/sotto_webview.py:144-155`) e `worker_status_text`
(`app/webview/sotto_webview.py:168-179`). Nenhum outro mapeamento (`WORKER_ERROR_STATES`,
`WORKER_WARMUP_STATES`, `HEALTHY_DONE_VERDICTS`, `FAILURE_WORDS_RE`, `_status`) foi tocado.

## 4. Braço NEGATIVO — derivado do ficheiro de HOJE, não de uma cópia guardada

`py -3 _main/panel-exit3-oracle.py --unit --neg-arm` → `PASS`, e o filho é que conta:

```
child_rc = 1
src_sha16    = d4392f8779a8f948
mutant_sha16 = 0fb21eaa1bffb779      (a mutação MOVEU o hash)
child_failures = [ "ARM D/done-no-verdict: kind='busy' expected 'error' (footer='done')",
                   "ARM D/done-no-verdict: the footer is a bare/neutral token, not a failure: 'done'",
                   "ARM D/done-no-verdict: an error with an EMPTY placeholder body …",
                   "ARM D/done-no-verdict: an error with no placeholder title …" ]
```

O mutante é construído por `build_neg_mutant()`, que reverte **uma linha** do shell de hoje
(`verdict not in` → `verdict and verdict not in`) e recusa-se a reportar veredicto se a linha não
aparecer exactamente uma vez ou se o hash não se mover. O gate só passa se o mutante ficar
VERMELHO **e** vermelho pela razão CERTA: `done-no-verdict` falha, e
`done-silent-device-exit3` / `done-unknown-verdict` / `done-healthy-control` continuam verdes.

## 5. AGENTS.md

Nova linha de contrato em `H:/sotto/AGENTS.md` (secção "Measured facts that must not be
re-litigated"): **A `done` with NO verdict is an ERROR, not a healthy finish — measured and fixed
2026-10-06**, com as duas linhas de código e o comando do gate.

## 6. Censo de janela contra os MEUS pids (nenhuma janela no ecrã do dono)

Instrumento da casa (`I:/!manager/scripts/window-census.ps1`) dirigido à minha cadence por
`_main/_ppv-census-driver.py` (não enumera nada ele próprio), com `-Log`/`-Estado` próprios:

```
[bootstrap] rc=0 ms=335
BOOTSTRAP: 12 janela(s) registadas como pre-existentes; alarme=0. A proxima corrida mede.

[sample-01] rc=0 ms=363   EM DIA: 12 janela(s) visiveis, 0 novas desde a ultima corrida.
…
[sample-22] rc=0 ms=311   EM DIA: 12 janela(s) visiveis, 0 novas desde a ultima corrida.
```

22 ticks de 15 s (323 s) cobrindo a corrida inteira (90 s): **0 novas, 0 alarmes, nenhum canal
CEGO** (um canal vazio NÃO é lido como zero). Os outros dois instrumentos concordam:

- censo da casa, `state/progress/window-census.log:1495-1498` (07:19:22Z → 07:22:22Z):
  `alarmSet=0`, `visiveis=12` em todos os ticks; o último `ALERTA-JANELA` é de **06:54:22Z**,
  ANTES desta corrida. (O tick das 07:21:22Z traz `reencontro=2` — dois chaves JÁ CONHECIDAS
  reapareceram; não é janela nova, não entra no alarme e não é atribuível a este probe.)
- o próprio shell: `PANEL_VISIBILITY_AT_STARTUP visible=false`,
  `PANEL_VISIBILITY_ON_SCREEN visible=false where=startup`,
  `PANEL_VISIBILITY_REASSERTED reason=navigation visible=false` (4×, as duas navegações × as duas arms).

Cada arm correu com `--no-hotkey` e foi lançada com `CREATE_NO_WINDOW` (0x08000000) — nunca
`DETACHED_PROCESS`.

## 7. O que NÃO foi feito, e quem é o dono

- **A shell Electron (LEGACY) tem o MESMO swallow.** `app/electron/worker-bridge.js:143` mapeia
  `done: {kind:'busy'}` e `describeState` recebe só o token do estado
  (`worker-bridge.js:213,236`) — um `done` com `verdict=silent-device` lá é pintado `busy`. NÃO
  foi tocado: o `AGENTS.md` diz que o Electron é a shell ANTERIOR e **não** é fallback (o dono
  decidiu, WebView2 é a app). Fica nomeado como divergência conhecida, não como trabalho feito.
- O contrato da **página** (`app/electron/panel.js:213`) deriva o erro por uma regex sobre o
  TEXTO (`/stopped|error|dead|no audio|no working/i`) e não vê o `kind`. Não é o mapeamento
  pintado: a shell faz `exec_js` DEPOIS de `send_status` e repõe `status--error` a partir do
  `kind` (medido: `apply_panel_state` → `send_status` → `exec_js`) — é por isso que a ARM B
  responde `true` apesar de o footer de um `done` saudável dizer `done`. Fica nomeado.

## 8. Duas cores a mais, ambas medidas (e um buraco do PRÓPRIO gate fechado)

**(a) O shell PRÉ-FIX, a cópia histórica que o docstring do oracle cita.**
`PANEL_ORACLE_SHELL=H:/sotto/_main/_prefix-under-test.py py -3 _main/panel-exit3-oracle.py --unit`
→ **rc=1**, 27 falhas, incluindo as quatro do braço novo
(`ARM D/done-silent-device-exit3: kind='busy' expected 'error' (footer='done')`). A afirmação do
docstring deixou de ser uma promessa e passou a ser uma corrida. O gate tem agora DUAS cores em
DUAS shells históricas diferentes (a cópia pré-fix e o mutante derivado de hoje).

**(b) O gate tinha um buraco PRÓPRIO, e ele está fechado.** `ARM D` (e o `ARM 0`) leem o `kind` do
callback `on_status`. A classe do DOM é decidida em DOIS passos por `apply_panel_state`:
`send_status(text)` PRIMEIRO — que é onde a regex de prosa da própria página
(`panel.js:213`, `/stopped|error|dead|no audio|no working/i`) liga `status--error` — e só DEPOIS um
`exec_js` que a re-liga a partir do NOSSO `kind`. Trocar essas duas instruções faz a regex da
página ser o pintor FINAL: um erro cujo footer não traz nenhuma palavra da página (o footer do
caso sem veredicto é exactamente um desses) fica pintado NEUTRO no DOM **enquanto ARM D continua
verde**. Isso é um buraco NO gate, portanto a ordem passou a ser ASSERTADA e não confiada
(`arm0_done_verdict`, bloco `paint-order`), fail-closed: se a leitura da forma falhar, ela reporta
falha em vez de silêncio.

**A asserção não é vácua — provado com um mutante da própria ordem.** Uma cópia com
`self.send_status(line)` movido para DEPOIS do `exec_js`
(`_main/_ppv-paintorder-mutant.py`, sha16 `698004d338bdf926` vs `d4392f8779a8f948` do original):

```
PANEL_ORACLE_SHELL=H:/sotto/_main/_ppv-paintorder-mutant.py py -3 _main/panel-exit3-oracle.py --unit  ->  RC=1
FAIL
[ "ARM D/paint-order: `apply_panel_state` toggles status--error BEFORE it sends the text, so the
   page's own prose regex decides the final class and this arm can be green while the panel paints
   NEUTRAL (app/webview/sotto_webview.py)" ]
```

É a ÚNICA falha — todos os outras arms continuam verdes nesse mutante, que é precisamente o
cenário "gate verde, painel neutro" que este bloco existe para não deixar passar.

## 9. A corrida completa REPETIDA na revisão final do oracle, e o censo com ela

As secções 1 e 6 foram medidas numa revisão do oracle ANTERIOR ao bloco `paint-order` (secção
8b). Para que não fique nenhuma evidência de uma revisão diferente da que fica em disco, as duas
correram outra vez depois da última edição:

```
py -3 _main/panel-exit3-oracle.py          -> verdict PASS, failures []
  ARM A: text="Receiving captions"  error=false  live=true  captions=8
  ARM B: text="Worker stopped (exit 3) - Worker finished on silent-device"
         className="status status--error"  error=true  placeholderTitle="Worker stopped"
         placeholderBody="verdict=silent-device device=Mapeador de som da Microsoft - Input
                           peak=0.000122 blocks=60 captions=0 tokens=0 chunks=10 rotations=0 …"
         worker_exits=[3, 3]
  ARM D: done-silent-device-exit3=error, done-unknown-verdict=error, done-no-verdict=error,
         done-healthy-control=busy, real-sequence-silent-device-then-done=error
```

Censo da casa dirigido a 15 s durante essa corrida (`_main/_ppv-census-samples2.log`):
12 ticks, `12 janela(s) visiveis, 0 novas`, todos com canal não-vazio (rc=0, sem `CEGO`); e o
censo partilhado `window-census.log:1502-1505` (07:26:22Z → 07:29:22Z) traz `alarmSet=0` em todos
os ticks, com o último `ALERTA-JANELA` ainda em 06:54:22Z. Duas corridas, dois instrumentos de
censo, zero janelas novas.

---

## SELF-AUDIT

- **protocolos em falta** — devia ter corrido o braço negativo ANTES de escrever a primeira
  versão do `ARM D`, porque a primeira versão do meu controlo positivo estava INVERTIDA (o
  `assert` dizia falha quando o footer saudável era `done`, ou seja o controlo acusava o
  comportamento correto). Apanhei-o só porque corri o gate; um protocolo "o primeiro run de um
  braço novo é um teste do BRAÇO, não do código" teria nomeado isso antes de eu olhar para o
  código da shell. Também não submeti o trabalho ao `falsifier`: o braço negativo é
  auto-construído e auto-lido pelo mesmo ficheiro, o que é auto-verificação e não falsificação
  independente.
- **verificacao adicional** (corrida, barata) — além dos dois mutantes acima, medi (i) o shell
  pré-fix como entrada RED, (ii) o mutante da ORDEM de pintura, e (iii) o censo da casa a 15 s
  durante a corrida inteira. A que teria aumentado mais a confiança e NÃO correu: um run real da
  shell com a linha `done` **sem veredicto** forçada no worker (para ver o footer novo no DOM a
  sério). Custo: uma alteração do worker ou um feed falso, +~2 min de model load — não foi feito
  porque o caminho está coberto por ARM D + ARM B, e porque tocar `worker/sotto_worker.py` não é
  ficheiro deste assento.
- **checkboxes novas** — (1) *Toda a arm que afirma "isto foi PINTADO" tem de trazer, na MESMA
  tabela, um CONTROL — um input saudável que tem de continuar verde; sem ele a arm passa pintando
  tudo a vermelho.* (2) *Toda a arm que lê um `kind` em vez do DOM tem de assertar a ORDEM das
  instruções que produzem o DOM, senão fica verde sobre um painel neutro.* (3) Ficheiro novo:
  `_main/_ppv-census-driver.py` — a cadence do censo tem de ser a NOSSA, e um canal VAZIO tem de
  ser reportado `CEGO`, nunca lido como zero.
- **review por outro subagente** — **sim-com-escopo**: revisão de (a) o bloco `done` do
  `worker_status_kind`/`worker_status_text` e a sua interacção com `_status`/`FALSE_AUDIO_ABSENT_RE`;
  (b) o `build_neg_mutant`/`neg_arm` (é ele próprio um gate a testar um gate); (c) o bloco novo
  `paint-order`. NÃO precisa rever as arms A/B/C herdadas nem o `AGENTS.md`.
- **gate-doubt**:
  - **verde-de-verdade**: o `--unit PASS` NÃO é vácudo e a corrida que o prova é o mutante: se o
    módulo carregado não fosse o ficheiro da shell, a mutação de uma linha não teria mudado o
    veredicto do filho (`child_rc=1`, `mutant_sha16 ≠ src_sha16`). O `PASS` da corrida completa
    vem de OUTRO instrumento (WebView2 real + probe DOM da própria shell) e concorda. Risco
    partilhado nomeado: as duas arms leem o mesmo `BRIDGE_STATUS_ERROR`/`on_status`; o que as
    separa é o DOM real, e isso só corre quando há WebView2 — por isso a corrida completa foi
    feita agora, em vez de se assumir.
  - **falta-no-gate**: o gate NÃO verifica que a shell **arranca** com a app real (o `--dump-dom`
    é um modo de medição). Cenário que o atravessa: alguém liga `apply_panel_state` a um caminho
    que não seja `_status` (ex.: um `on_status` que trate `done` localmente), e todos os braços
    continuam verdes porque alimentam `_consume` directamente. Segundo buraco, já fechado: a ORDEM
    de pintura (secção 8b) — era exactamente um "verde sobre painel neutro", e foi fechado com
    asserção mecânica + mutante.
  - **gate-melhor**: o check mecânico que fecha o buraco acima é o bloco `paint-order` já
    implementado; o input que TEM de o deixar RED é `_main/_ppv-paintorder-mutant.py` (medido:
    rc=1, falha única). Para o buraco do arranque real, o check seria `py -3
    _main/panel-exit3-oracle.py` (a corrida completa) e o input que o deixa RED é o shell pré-fix
    em `PANEL_ORACLE_SHELL` — já medido.
- **confianca** — **alta** para o contrato do `done` (verdict conhecido, desconhecido, ausente) e
  para a ordem de pintura: há duas cores medidas em duas shells diferentes, em três instrumentos
  independentes (callback do bridge, DOM real, censo). **Média** para "isto é o único swallow
  restante": a shell Electron (LEGACY) tem o mesmo defeito e foi deliberadamente não tocada.
- **nao verificado**: (1) o painel Electron real (não corre neste host por decisão do dono);
  (2) um `done` sem veredicto vindo de um WORKER real — medido só pelo feed directo ao bridge;
  (3) a `ARM A` herdada devolveu `worker_exits=[1]` apesar de `captions=8`: NÃO investiguei esse
  exit 1 do primeiro filho (fora do escopo desta lane, mas fica nomeado); (4) o comportamento do
  painel com `--show` (janela visível) não foi exercitado.

## CACHE/PRICE

```
$ bash I:/!manager/scripts/cache-task-report.sh SottoPanelPaintsVerdict
- task/agent: SottoPanelPaintsVerdict
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoPanelPaintsVerdict.jsonl
- cache: read=9821312 write=0 hit=97.9821% (cache-read / input+cache-read); universe: 71 usage rows; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- input tokens: 202267 / output tokens: 52370 / cache-read tokens: 9821312 / cache-write tokens: 0
- prefix breaks: 9 (state=RESOLVED-BREAKS-OMP; 6 of 112650 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce','SottoPanelPaintsVerdict'])
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T07:16:14.056Z; WHERE session_id=01a11011-d2f4-76ad-8f24-529ff81ad841 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791270974056
  - break_items=1; WHEN=2026-10-06T07:16:14.811Z; WHERE session_id=01a11011-... provider=space-bunny-free item_index=0; turn_id=1791270974811
  - break_items=1; WHEN=2026-10-06T07:16:15.320Z; WHERE session_id=01a11011-... provider=ling-3.1-flash-free item_index=0; turn_id=1791270975320
  - break_items=3; WHEN=2026-10-06T07:16:15.863Z; WHERE session_id=01a11011-... provider=deepseek-flash item_index=0; turn_id=1791270975863
  - break_items=2; WHEN=2026-10-06T07:18:20.066Z; WHERE session_id=01a11011-... provider=deepseek-flash item_index=83; turn_id=1791271100066
  - break_items=1; WHEN=2026-10-06T07:25:48.337Z; WHERE session_id=01a11011-... provider=deepseek-flash item_index=225; turn_id=1791271548337
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Os 6 breaks são todos do lado da FROTA (modelo/provider a mudar no primeiro item de uma sessão de
outro harness), não deste trabalho: hit ratio 97.98%, cache-write 0, custo reportado $0.00.

- **verificacao mecanica**: `bash I:/!manager/scripts/self-audit-lint.sh _main/SottoPanelPaintsVerdict.md` → **rc=0**.
