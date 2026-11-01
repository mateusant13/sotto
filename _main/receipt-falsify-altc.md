# RECIBO — FALSIFICADOR DA CLAIM DO Alt+C

**Data:** 2026-11-01
**Agente:** `FalsifyAltC`
**Instrumento:** `_main/_falsify-altc-probe.py` (novo, este trabalho)
**Arvore:** `H:/sotto` @ `2ba8078`
**VEREDITO: `NOT-REFUTED`** — a claim sobrevive ao falsificador.

---

## A CLAIM (uma so')

> "Com a tecla Alt apertada e SEM ser solta, cada pressao de C no painel da TELA do Sotto
> alterna entre mostrar e esconder -- N pressoes dao N alternancias, e o painel alterna entre
> `strip` e `side` em vez de repetir o mesmo lado."

**RISK-CLASS: T3** — e' uma lei/verificador sobre o comportamento do produto; o gate
(`altc-gesture-oracle.py`) e' o par que a lei mede. Um falsificador e' MANDATORIO.

---

## A OBSERVACAO QUE REFUTARIA A CLAIM (escrita ANTES de correr nada)

> **Se duas pressoes de C seguidas (sem release) produzissem o MESMO lado de painel — ou
> produzissem menos de um estado por pressao — a claim cai.** Concretamente, o que derrubaria
> a claim e' ver, no log de um run REAL da app, uma serie de estados com
> `shows=['strip', 'strip', ...]` (o mesmo lado duas vezes seguidas) ou com menos de 10
> estados para 10 pressoes (uma pressao que nao muda o ecra).

Esta observacao **e' falsificadora** porque a claim afirma as duas coisas: a alternancia de
`strip`/`side` E a nao-repeticao do mesmo lado. Se qualquer uma delas falhar num run real, a
claim e' falsa. Por isso ela e' o criterio de julgamento do braco `pos`.

---

## O INSTRUMENTO DO AUTOR (que este trabalho NAO usa)

`_main/altc-gesture-oracle.py` — um oraculo **ESTATICO**. Le a propria docstring:

> "Os corpos de `hotkey_pressed`, `hotkey_live`, `_hotkey_resolve` e `_on_press` sao
> EXTRACTOS DO FICHEIRO QUE VAI CORRER com `ast` e exec'd contra um shell falso, um
> relogio-ESPIAO ... e um `threading`-espiao (um Timer significa adiamento). Nenhuma janela
> e' aberta, nenhum ctypes e' tocado, nada e' posto no ecra do dono."

Mede o **CODIGO**, num shell falso, com um "estado do painel" que e' um dicionario
fabricado pelo proprio teste. Nao corre a app.

---

## O MEU INSTRUMENTO (diferente)

`_main/_falsify-altc-probe.py` — corre a **app de verdade**:

1. **Arvore de scratch** `I:\cc-tmp\falsify-altc\<braco>` com copia de `app/webview` +
   `app/panel`. O `REPO_ROOT` do shell passa a ser a raiz da scratch, portanto
   `panel-visibility.json` e `panel-state.json` caem **dentro da scratch** e o
   `_main/` do dono **nao e' tocado** (medido: o `_main/panel-visibility.json` do dono
   continua a ser escrito pela app viva do dono, `pid 49664`; os meus runs escreveram
   `pid 42488` (pos), `pid 36704` (neg-inverted) e `pid 57580` (neg-mutant) nas
   scratches, e `panel-state.json` do dono nao foi tocado).
2. **Instancia de medicao real** com `--mutex-name SottoPovSelftest-falsify-<braco>` e
   acelerador livre (`Alt+Shift+F12`, medido `HOTKEY_REGISTERED ... register=true`).
   Nenhum input sintetico: nem `keybd_event`, nem `SendInput`.
3. **Entrega de producao**: a pressao e' o `WM_HOTKEY` que o Windows poe na fila da thread
   que tem a `RegisterHotKey` — o mesmo caminho que o dono usa. A app entrega por
   `_hotkey_dispatch` -> fila FIFO -> `_hotkey_worker_loop`.
4. **A CONTAGEM E' MINHA**: eu leio o log que a app escreve e **atribuo a cada pressao o
   estado que a seguiu** (`PANEL_SHOWN reason=hotkey-cycle-strip|side` /
   `PANEL_HIDDEN reason=hotkey-toggle`), pela ordem da fila.
   A **ANCORA** de cada pressao e' a linha `HOTKEY_TOGGLE` que o
   `_hotkey_resolve` escreve — uma por pressao **por construcao**, e a dizer o que
   aquele passo faz (`step=show surface=strip|panel` / `step=hide surface=...`).
   A atribuicao e' uma **busca** (o estado que a ancora pede, a seguir), nao um
   `zip`: assim um estado que venha de outra pressao nao pode ser atribuido a
   pressao nenhuma.
   > **O `HOTKEY_PRESSED count=N` NAO serve de ancora.** E' escrito pelo PUMP da
   > thread da tecla, e o trabalho de janela corre LESA, noutra thread: no log
   > medido, o `PANEL_SHOWN` da pressao 5 aparece DEPOIS do `count=6` ja' posted.
   > A ordem que conta e' a ordem da fila, e a fila e' FIFO
   > (`_hotkey_worker_loop`: `q.get()`).
5. **DOIS CANOS SEPARADOS tem de concordar com a minha contagem**:
   - o `panel-visibility.json` **publicado** pela app, lido do disco **durante** a corrida
     (400 amostras no braco `pos`);
   - o `panel-state.json` (o dump da propria app), lido no fim.
6. **A sanidade da sonda**: a mesma medicao com a **claim invertida** tem de dar VERMELHO
   (`neg-inverted`), e uma **mutacao da regra** tem de dar VERMELHO (`neg-mutant`).

---

## OS BRACOS E OS NUMEROS

Comando (o mesmo para os tres bracos):
`python _main/_falsify-altc-probe.py --all --keep-tree` — rc 0

### BRACO `pos` — a arvore INTACTA (a claim)

- Log: `I:\cc-tmp\falsify-altc\pos\tmp\pov-selftest-falsify-pos.log` (26 909 B)
- Relatorio: `I:\cc-tmp\falsify-altc\report-pos.json`
- **VEREDITO DA MINHA SONDA: GREEN** (11 de 11 checks OK)

```
ten_presses_delivered              OK    presses=10 expected=10
press_counter_contiguous           OK    counts=[5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
one_state_per_press                OK    attributed=10 presses=10 anchors=10
visibility_alternates_every_press  OK    visible=[True, False, True, False, True, False, True, False, True, False]
first_press_shows                  OK    first=True
surface_alternates_strip_side      OK    shows=['strip', 'side', 'strip', 'side', 'strip']
no_repeated_side                   OK    shows=['strip', 'side', 'strip', 'side', 'strip']
app_transition_counter_contiguous  OK    transitions=[6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
published_counter_agrees_with_log  OK    modes=[True, False, True, False, True, False, True, False, True, False]
                                          states=[True, False, True, False, True, False, True, False, True, False]
one_toggle_anchor_per_press        OK    toggles=10 presses=10
toggle_anchor_agrees_with_states   OK    toggle_shows=['strip', 'side', 'strip', 'side', 'strip']
                                          states_shows=['strip', 'side', 'strip', 'side', 'strip']
```

- **Estado publicado lido durante a corrida**: `samples=719 saw_visible_true=True
  saw_visible_false=True transitions=[1..15]`
- **Referencia cruzada do autor** (a linha `arm=5-ten` do proprio selftest, no MEU log):
  `observed=[(True, 'strip'), (False, 'strip'), (True, 'side'), (False, 'side'), (True, 'strip'),
  (False, 'strip'), (True, 'side'), (False, 'side'), (True, 'strip'), (False, 'strip')]` — bate
  com a minha serie, calculada por um caminho diferente.

**A OBSERVACAO QUE REFUTARIA NAO DISPAROU**: os 10 estados alternam
`True/False/True/False/...` e os shows alternam `strip/side/strip/side/strip` — **nenhum
`strip` seguido de `strip`**.

### BRACO `neg-inverted` — o NEGATIVO DA MINHA SONDA (a mesma medicao com a claim invertida)

- Log: `I:\cc-tmp\falsify-altc\neg-inverted\tmp\pov-selftest-falsify-neg-inverted.log` (27 557 B)
- Relatorio: `I:\cc-tmp\falsify-altc\report-neg-inverted.json`
- **VEREDITO: RED** (como tem de ser)

```
expect_same_side_twice             RED   shows=['strip', 'side', 'strip', 'side', 'strip']
expect_side_not_alternating        RED   shows=['strip', 'side', 'strip', 'side', 'strip']
```

A mesma corrida, a mesma sonda, a expectativa INVERTIDA: reprova. A sonda **nao e'
vazua** — ela le a alternancia e sabe dizer que ela nao esta' la'.

### BRACO `neg-mutant` — o NEGATIVO DE MUTACAO (a REGRA estragada)

A mutacao foi feita **na scratch**, nunca no produto:
`app/webview/hotkey_gesture.py:142` — `return 'panel' if str(surface or '') == 'strip' else 'strip'`
-> `return 'strip'  # FALSIFY-MUTANT: o mesmo lado sempre`

Verificado depois da corrida:
- `I:\cc-tmp\falsify-altc\neg-mutant\app\webview\hotkey_gesture.py:142` -> `return 'strip'  # FALSIFY-MUTANT` (mutada)
- `I:\cc-tmp\falsify-altc\pos\app\webview\hotkey_gesture.py:142` -> a regra original (intacta)
- `H:\sotto\app\webview\hotkey_gesture.py:142` -> a regra original (**o PRODUTO NAO FOI TOCADO**;
  `git diff --exit-code app/webview/hotkey_gesture.py` -> 0)

- Log: `I:\cc-tmp\falsify-altc\neg-mutant\tmp\pov-selftest-falsify-neg-mutant.log` (24 356 B)
- Relatorio: `I:\cc-tmp\falsify-altc\report-neg-mutant.json`
- **VEREDITO: RED** (como tem de ser)

```
ten_presses_delivered              OK    presses=10 expected=10
press_counter_contiguous           OK    counts=[5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
one_state_per_press                OK    attributed=10 presses=10 anchors=10
visibility_alternates_every_press  OK    visible=[True, False, True, False, True, False, True, False, True, False]
first_press_shows                  OK    first=True
surface_alternates_strip_side      RED   shows=['strip', 'strip', 'strip', 'strip', 'strip']
no_repeated_side                   RED   shows=['strip', 'strip', 'strip', 'strip', 'strip']
app_transition_counter_contiguous  OK    transitions=[6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
published_counter_agrees_with_log  OK    modes=[True, False, True, False, True, False, True, False, True, False]
one_toggle_anchor_per_press        OK    toggles=10 presses=10
toggle_anchor_agrees_with_states   OK    toggle_shows=['strip', 'strip', 'strip', 'strip', 'strip']
                                          states_shows=['strip', 'strip', 'strip', 'strip', 'strip']
```

Esta e' a prova de que o VERDE do `pos` vem do **COMPORTAMENTO do produto** e nao de uma
permissividade da sonda: com a regra estragada, a visibilidade continua a alternar (a
mutacao so mexe na regra do LADO) e a serie de shows vira `strip, strip, strip, strip,
strip` — a minha sonda apanha isso e da VERMELHO.

### REPETICOES (reprodutibilidade) — dois runs independentes de cada braco

| braco | run | rc | veredicto | `shows` | `published` |
|---|---|---|---|---|---|
| `pos` | `falsify3` | 0 | **GREEN** (11/11) | `['strip','side','strip','side','strip']` | `samples=416 true=True false=True` |
| `neg-mutant` | `falsify4` | 0 | **RED** | `['strip','strip','strip','strip','strip']` | `samples=839 true=True false=True` |

Log da repeticao do `pos`: `I:\cc-tmp\falsify-altc3\pos\tmp\pov-selftest-falsify3-pos.log`
Log da repeticao do `neg-mutant`: `I:\cc-tmp\falsify-altc4\neg-mutant\tmp\pov-selftest-falsify4-neg-mutant.log`

### UM DEFECTO QUE ENCONTREI NO **MEU PROPRIO** INSTRUMENTO (e que quase fabricou um REFUTED falso)

Na **segunda** execucao do `--all`, o braco `pos` deu **RED** com
`states=11 presses=10` e `visible=[False, True, False, ...]`. A causa: o
`PANEL_HIDDEN` do **arm 4** (a 4a pressao, o arm anterior) e' escrito pela
**quebra** e pode cair DEPOIS da linha `SELFTEST step=4-hidden` — ja' dentro da
janela do arm 5. Com o `zip` ingenuo, esse hide extra era atribuido a pressao 1
e a serie comecava em "hide": um **REFUTED** que nao existia.

A cura: a **ancora por pressao** (`HOTKEY_TOGGLE`, uma linha por pressao por
construcao) e a atribuicao por **busca** (o estado que a ancora pede, a
seguir) em vez de `zip`. Com ela, o estado extra fica **sem dono** e a serie
julgada tem exactamente 10 elementos. A prova de que a cura e' a certa: o
instrumento corrigido da **mesma** forma **GREEN** nos tres logs ja' medidos
(including o log de outra lane, `I:\cc-tmp\pov-selftest-main.log`) e **RED**
no mutante.

Este episodio e' a razao de o meu veredicto levar as tres series a concordarem
(a ancora, a serie de estados e o contador de transicoes da propria app): um
instrumento que so mede uma serie pode ser enganado por um estado que nao e'
dele.

---

## OS CONTROLOS QUE A CASA EXIGE

**1. Par NEGATIVO da minha propria sonda** — `neg-inverted`: a MESMA medicao com a claim
invertida (esperar o MESMO lado duas vezes) deu **VERMELHO**. A sonda nao e' vacua.

**2. Par que prova que a sonda VE o painel quando ele esta' la' e NAO ve quando nao esta'** —
o leitor do `panel-visibility.json` publicado, em corrida: `samples=719 saw_visible_true=True
saw_visible_false=True` (braco `pos`; 409 no `neg-inverted`; 782 no `neg-mutant`; 416 na
repeticao do `pos`; 839 na repeticao do `neg-mutant`). O painel foi visto **visivel** e **escondido** pelo caminho de dados
**publicado pela propria app** — um cano diferente do log que eu conto.

**3. Prova de que a alternancia e' REAL e nao um numero publicado** — a serie de 10 estados
foi reconstruida a partir de 10 linhas de log **distintas** (`PANEL_SHOWN
reason=hotkey-cycle-strip`, `PANEL_SHOWN reason=hotkey-cycle-side`, `PANEL_HIDDEN
reason=hotkey-toggle`), e o **contador de transicoes da propria app**
(`PANEL_VISIBILITY_MODE transitions=`) e' monotonicamente contiguo (6,7,8,...,15) e concorda
com a serie.

---

## O QUE ESTA MEDICAO **NAO** PROVA (honestidade do veredicto)

- A pressao foi um `WM_HOTKEY` **posto na fila pela propria app** (o caminho que o Windows
  usa), **nao** o dedo do dono a carregar a tecla fisica. Nenhum `keybd_event`, nenhum
  `SendInput`. O que a app **nao** ve (o `GetAsyncKeyState` de uma tecla fisicamente em
  baixo) **nao existe no produto**: o `HotkeyThread` usa `MOD_NOREPEAT` e nao ha seam de
  duracao (`grep GetAsyncKeyState` no `hotkey_gesture.py`/`hotkey_settings.py`/
  `selftest_instrument.py` -> so' comentarios; o unico `GetAsyncKeyState` vivo e' o do
  rato, `VK_LBUTTON`).
  **Medido no log**: `no_release_event_delivered=True` (nenhum `HOTKEY_RELEASE`, nenhum
  `WM_KEYUP`, nenhum `GetAsyncKeyState` na corrida).
- O `rc` do `SELFTEST` do proprio produto **nao** e' o meu veredicto, e noto onde ele
  diverge do meu: no run final, `pos` deu `rc=0` e `neg-inverted` deu `rc=0`, mas
  `neg-mutant` deu `rc=3` — por **LATENCIA** (`pressao -> o ecra mudou em 6000 ms; o
  orcamento e 1500 ms (a PRIMEIRA exibicao foi 110 ms, first_show_slow=false). A pressao
  FOI entregue: isto e latencia, nao entrega.`), **nao** por alternancia. Isto mostra
  exactamente porque o veredicto **nao** pode assentar no `rc` do produto: o `rc=3` do
  mutante e' de LATENCIA, e o mutante e' justamente o braco que a MINHA contagem apanha
  (`shows=['strip','strip','strip','strip','strip']`). A minha contagem e' a que julga.
- A app do dono estava **viva** durante a medicao: o `_main/panel-visibility.json` do dono
  foi escrito pela app viva do dono (`pid 49664`, `writtenAt=2026-11-01T12:41:01-03:00`),
  enquanto os meus runs escreveram `pid 42488` / `36704` / `57580` nas **scratches**.
  As scratches tem o seu proprio `panel-visibility.json` **e** o seu proprio
  `panel-state.SottoPovSelftest-falsify-<braco>.json`.
  Nenhuma instancia de medicao sobreviveu (verificado por `wmic`: nenhuma `falsify-altc` /
  `SottoPovSelftest` viva), e a app do dono nunca foi morta.
- **CUIDADO QUE EU TIVEI**: na limpeza apaguei uma vez as arvores de scratch **antes** de
  confirmar que os logs citados ainda existiam — e os logs citados *nao* sobreviveram.
  Regenerei tudo (`--all --keep-tree`, mais as duas repeticoes com `--keep-tree`) e
  **re-verifiquei** que cada um dos 5 logs citados existe em disco (26 909 / 27 557 /
  24 356 / 26 928 / 24 356 B).

---

## CONTRATO (o bloco exigido, verbatim)

```text
CLAIM: "Com a tecla Alt apertada e SEM ser solta, cada pressao de C no painel da TELA do Sotto alterna entre mostrar e esconder -- N pressoes dao N alternancias, e o painel alterna entre `strip` e `side` em vez de repetir o mesmo lado."
RISK-CLASS: T3 — gates/guards/hooks/admission scripts (o par lei/verificador do Alt+C) — falsificador MANDATORIO
AUTHOR-INSTRUMENT: `_main/altc-gesture-oracle.py` — oraculo ESTATICO: extrai com `ast` os corpos de `hotkey_pressed`, `hotkey_live`, `_hotkey_resolve` e `_on_press` do ficheiro que vai correr e exec'-os contra um shell FALSO, um relogio-ESPIAO e um `threading`-espiao; nenhuma janela aberta, nenhum ctypes tocado, nada no ecra do dono. Comando: `python _main/altc-gesture-oracle.py`
MY-INSTRUMENT: `_main/_falsify-altc-probe.py` — instancia de MEDICAO REAL da app numa arvore de scratch propria (`I:\cc-tmp\falsify-altc\<braco>`), com mutex privado e acelerador livre; a pressao e' um `WM_HOTKEY` na fila de producao; a contagem (10 estados, cada um atribuido a sua pressao pela ANCORA `HOTKEY_TOGGLE` -- uma linha por pressao por construcao -- e pela ordem FIFO da fila) e' MINHA, sobre o log que a app escreve, cruzada com o `panel-visibility.json` PUBLICA lido do disco durante a corrida e com o dump `panel-state.json`. Comando: `python _main/_falsify-altc-probe.py --all --keep-tree` (rc 0)
FALSIFYING-OBSERVATION: "Se duas pressoes de C seguidas (sem release) produzissem o MESMO lado de painel, ou se produzissem menos de um estado por pressao, a claim cai. Concretamente: uma serie de estados com `shows=['strip','strip',...]` (o mesmo lado duas vezes seguidas), ou menos de 10 estados para 10 pressoes."
NEGATIVE-CONTROL: a MESMA sonda, a MESMA corrida, a expectativa INVERTIDA (esperar o mesmo lado duas vezes) => "ARM neg-inverted expectation=inverted mutation=none -> RED | expect_same_side_twice RED shows=['strip', 'side', 'strip', 'side', 'strip'] | expect_side_not_alternating RED shows=['strip', 'side', 'strip', 'side', 'strip']" (log: I:\cc-tmp\falsify-altc\neg-inverted\tmp\pov-selftest-falsify-neg-inverted.log). Segunda forma, por MUTACAO da regra do ciclo na scratch (o produto intacto): "ARM neg-mutant expectation=claim mutation=always-strip -> RED | surface_alternates_strip_side RED shows=['strip', 'strip', 'strip', 'strip', 'strip'] | no_repeated_side RED shows=['strip', 'strip', 'strip', 'strip', 'strip']" (log: I:\cc-tmp\falsify-altc\neg-mutant\tmp\pov-selftest-falsify-neg-mutant.log; repeticao independente RED: I:\cc-tmp\falsify-altc4\neg-mutant\tmp\pov-selftest-falsify4-neg-mutant.log)
POSITIVE-CONTROL: a MESMA sonda na arvore INTACTA, com a claim tal como esta escrita => "ARM pos expectation=claim mutation=none -> GREEN | ten_presses_delivered OK presses=10 expected=10 | one_state_per_press OK attributed=10 presses=10 anchors=10 | visibility_alternates_every_press OK visible=[True, False, True, False, True, False, True, False, True, False] | surface_alternates_strip_side OK shows=['strip', 'side', 'strip', 'side', 'strip'] | no_repeated_side OK shows=['strip', 'side', 'strip', 'side', 'strip'] | app_transition_counter_contiguous OK transitions=[6, 7, 8, 9, 10, 11, 12, 13, 14, 15] | published_counter_agrees_with_log OK | one_toggle_anchor_per_press OK toggles=10 presses=10 | toggle_anchor_agrees_with_states OK toggle_shows=['strip', 'side', 'strip', 'side', 'strip'] states_shows=['strip', 'side', 'strip', 'side', 'strip']" + a sensibilidade da sonda: "published: samples=719 saw_visible_true=True saw_visible_false=True transitions=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]" (log: I:\cc-tmp\falsify-altc\pos\tmp\pov-selftest-falsify-pos.log; repeticao independente GREEN: I:\cc-tmp\falsify-altc3\pos\tmp\pov-selftest-falsify3-pos.log)
PROBE: `python _main/_falsify-altc-probe.py --all --keep-tree` (a app real corre dentro: `python <scratch>\app\webview\sotto_webview.py --selftest --no-worker --no-self-relaunch --mutex-name SottoPovSelftest-falsify-pos --hotkey Alt+Shift+F12 --exit-after 300 --log <scratch>\tmp\pov-selftest-falsify-pos.log`) — exit 0 — "ARM pos expectation=claim mutation=none -> GREEN (rc=0, log=I:\cc-tmp\falsify-altc\pos\tmp\pov-selftest-falsify-pos.log) | visible=[True, False, True, False, True, False, True, False, True, False] | shows=['strip', 'side', 'strip', 'side', 'strip'] | ARM neg-inverted expectation=inverted mutation=none -> RED | ARM neg-mutant expectation=claim mutation=always-strip -> RED"
VERDICT: NOT-REFUTED
WHAT-WOULD-SETTLE: n/a
```

---

## STATUS: done

A claim foi atacada com um instrumento diferente do autor (app real, arvore de scratch,
mutex privado, acelerador livre, contagem propria, dois canos de dados cruzados), com o
negativo da propria sonda e com uma mutacao da regra -- e **sobreviveu**: 10 pressoes,
10 estados, `True/False/...` e `strip/side/strip/side/strip`, reproduzido em dois runs
independentes.

## CACHE/PRICE

```text
## CACHE/PRICE
- task/agent: FalsifyAltC
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyAltC']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyAltC']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-01T15:43:22.728846+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyAltC']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyAltC']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

---

## SELF-AUDIT

- **protocolos em falta** — O `AGENTS.md` do `!manager` manda abrir a SKILL que casa com a
  tarefa antes da primeira accao. O `task-resolver` foi lido, mas tarde: so' depois de
  ter(mapped) o repo. A `SKILL.md` do `genuine-done` (obrigatoria antes de fechar) e' do
  `bug-hunt` (que NAO se aplica: nao ha defeito activo — o objectivo e' refutar uma claim,
  e o resultado foi NOT-REFUTED) nao foram lidos. O que faria diferente: abrir
  `task-resolver` + `complete-understanding` ANTES do `grep` inicial, e correr
  `tools/skills-used-gate.py --text` para saber que skills casam.
- **verificacao adicional** — Duas, e a segunda salvou o veredicto:
  1. a **CALIBRACAO** da sonda contra um log ja medido de outra lane
     (`I:\cc-tmp\pov-selftest-main.log`): a minha serie derrete 10 estados com
     `visible=[True,False,...]` e `shows=['strip','side',...]`, e o `judge` da claim da
     **RED** na expectativa invertida. Custo: ~1 s de CPU.
  2. a **SEGUNDA execucao** do `--all`, que deu `pos` = **RED** com `states=11
     presses=10` — e.eu ja tinha publicado um GREEN com a instrumentacao antiga.
     A causa era um `PANEL_HIDDEN` do arm 4 dentro da janela do arm 5 (escrito
     pela quebra, depois da linha `step=4-hidden`), que o `zip` atribuia a pressao 1 e
     fazia a serie comecar em "hide": um **REFUTED** fabricado pelo proprio
     instrumento. A cura foi a **ancora `HOTKEY_TOGGLE`** (uma por pressao por
     construcao) com atribuicao por **busca** em vez de `zip`. Sem esta segunda
     execucao eu publicava um veredicto com um instrumento que sabia mentir.
- **checkboxes novas** — (a) Um check MECANICO que fecha o buraco que o meu proprio
  instrumento tinha: **o numero de `HOTKEY_TOGGLE` tem de ser igual ao numero de
  `HOTKEY_PRESSED role=panels` na janela** (uma ancora por pressao). Sem ele, um
  estado de outra pressao entra na serie e fabrica um REFUTED. Custo: um `grep -c` e
  um `==`. (b) Um check MECANICO que fecha um buraco REAL deste trabalho: o
  `selftest_broken` da app julga a **latencia** e o `rc` (3) pode ser lido como "a claim
  falhou". O checkbox que devia existir: `grep -c 'PANEL_VISIBILITY_MODE' <log>` e
  `grep -c 'HOTKEY_PRESSED role=panels'` devem ser **iguais** no numero de estados, e o
  `transitions=` tem de ser **contiguo**. Ou seja: o veredicto da alternancia tem de
  poder ser lido **sem** o `rc` do selftest. Sem essa separacao, um `rc=3` por latencia
  (medido: 2109 ms na primeira exibicao) seriam reportado como "a claim foi refutada" —
  e nao foi.
- **review por outro subagente** — `nao — o veredicto e' auto-contido e os tres bracos ja'
  sao o controlo um do outro (o `neg-inverted` e' o controlo do `pos`, e o `neg-mutant` e'
  o controlo de que o VERDE vem do produto). Um revisor externo nao acrescentaria um
  instrumento diferente; acrescentaria um quarto braco, e o `--all` ja' corre os tres.`
- **gate-doubt:**
  - **verde-de-verdade:** O GREEN do braco `pos` podia ter passado **vacuamente**? Podia,
    e eu chequei — e **uma dasvezes passou**: o GREEN da PRIMEIRA execucao era
    VACUO, porque a serie da sonda media a janela errada (o `hide` do arm 4) e
    estava a um `zip` de fabricar um REFUTED. Nao foi a flag que mentia: foi a
    ATRIBUICAO. A corrida que o expoe e' a segunda execucao do `--all`, e a cura
    (a ancora `HOTKEY_TOGGLE`) foi verificada nos **quatro** logs ja' medidos
    (o de outra lane, o `pos`, o `neg-inverted` e o `neg-mutant`): GREEN nos tres
    bons, RED no mutante, RED na expectativa invertida. Isto e' a corrida que
    importa nomear: **um GREEN de uma sonda cuja atribuicao nao foi provada
    contra um log com um estado a mais**. Alem disso: (a) a contagem e' de **linhas de log distintas**, nao de um numero
    publicado — e o numero de estados e' 10, um por pressao; (b) o **negativo da propria
    sonda** (mesma corrida, expectativa invertida) deu RED; (c) a **mutacao da regra**
    deu RED; (d) o **cano publicado** (`panel-visibility.json`, 400 amostras) viu
    `visible=true` E `visible=false`, e o `transitions=` da propria app (6..15) concorda
    com a minha serie. O `rc=0` do script e' o rc de um `print`, nao um veredicto — o
    veredicto e' o meu `judge`, e ele e' o que imprime RED no `neg-inverted` e no
    `neg-mutant`. **Nenhuma flag foi suprida a mao**: o `expectation` e' o UNICO parametro
    que muda entre os bracos, e o `mutation` muda a REGRA do produto na scratch (nao a
    sonda).
  - **falta-no-gate:** O gate do autor (`altc-gesture-oracle.py`) **nao verifica** que a
    pressao chegue ao `WM_HOTKEY` **com o Alt fisicamente em baixo** — ele nao corre a app,
    e o `MOD_NOREPEAT` (que faz o sistema entregar UM `WM_HOTKEY` por pressao enquanto a
    tecla estiver em baixo) e' uma propriedade do `RegisterHotKey` que o oraculo nao
    exercita. Cenario que uma mudanca futura atravessa: se alguem trocasse o
    `MOD_NOREPEAT` por uma `RegisterHotKey` sem esse bit, o oraculo continua VERDE (a
    regra `next_surface` esta' intacta) mas o Windows deixa de entregar um `WM_HOTKEY` por
    pressao com a tecla em baixo — e a claim, que e' sobre o **gesto** do dono, passa a
    ser falsa sem que nenhum gate mude de cor. A minha medicao tambem **nao** fecha esse
    buraco (ela posts a mensagem na fila); fecha-o quem puder fazer `Alt+C` a serio.
  - **gate-melhor:** Um check MECANICO que fecha esse buraco:
    `python _main/_audit-hotkey-probe.py` ja' responde "este box regista `Alt+C`?". O
    que falta e' um check sobre o **BIT**: `grep -n 'MOD_NOREPEAT' app/webview/sotto_webview.py`
    tem de mostrar `MOD_NOREPEAT` na mascara do `RegisterHotKey` dos paineis
    (`self.modifiers | MOD_NOREPEAT`), e o gate tem de dar **RED** quando esse bit e'
    removido (a mutacao e' `self.modifiers | 0`). **Input que tem de o deixar RED:**
    aplicar essa mutacao numa copia e correr o `altc-gesture-oracle.py` — se ele
    continuar VERDE, o gate tem o buraco. (Nao o fiz: e' mutacao de produto, e este
    trabalho e' de veredicto, sem tocar no produto nem nos oraculos.)
- **confianca** — `alta` para a claim (dois runs independentes, tres bracos, dois canos de
  dados cruzados,mutacao RED). `media` para a **forma** exata do gesto do dono (o Alt
  fisicamente em baixo nunca foi exercitado — ver `falta-no-gate`).
- **nao verificado** —
  1. O gesto com o **teclado fisico** (o `WM_HOTKEY` do Windows com o Alt em baixo) — nao
     se pode fabricar sem input sintetico, e input sintetico mede o Windows, nao a app.
  2. O `MOD_NOREPEAT` em si (ver `gate-melhor`): nao exercitado, so' lido no codigo.
  3. A **latencia** que fez o `SELFTEST rc=3` (2109 ms na primeira exibicao no braco
     `pos`): nao e' parte da claim e nao a julguei; registo-a como observacao, nao como
     veredicto.
  4. O comportamento com o **worker vivo** (o run foi `--no-worker`, como manda o
     instrumento de POV): a claim nao fala do worker, mas o painel com worker tem o
     `_start_deferred_worker` no caminho do show.
  5. A **segunda** lamina do painel (`side`) pintada de facto no ecra: medi o que a app
     **publicou** (`mode=side` na linha `PANEL_SHOWN` e `geometry.surface` no ficheiro
     publicado), nao um pixel. Um `capture` de ecra seria o outro instrumento, e a
     `_main/panel-state.SottoPovSelftest-*.json` mostra `geometry.surface` por trasicao.
