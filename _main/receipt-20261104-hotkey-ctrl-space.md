# Recibo — hotkeys: Ctrl+Space para a legenda, Alt+C alterna os painéis

Lane: `lane/hotkey-ctrl-space`, worktree `H:/sotto-wt/HotkeyCtrlSpace` (base `HEAD` = 82e16a5).
Data: 2026-11-04.

## A ordem, restateada

Ordem do dono (2026-11-01, verbatim, a mesma que `hotkey_gesture.py` cita): *"modifica a
legenda ao vivo hotkey. bota o padrao como control espaco. e os painels deixa alt c. faz os
painéis alternarem mesmo se eu deixar alt apertado o tempo inteiro e spammando c. alterna
entre show e hide."*

Em aceitação mecânica:

1. `Ctrl+Space` = legenda ao vivo on/off (padrão), `Alt+C` = painéis.
2. O gesto dos painéis **alterna show/hide com o `Alt` em baixo o tempo todo e o `C`
   martelado** — e uma pressão engolida por uma solta perdida é o defeito desta lane.
3. Os números das teclas (vocabulário, VK, bit do `RegisterHotKey`, cadência do observador)
   vivem num só sítio, `hotkey_gesture.py`, lidos por `hotkey_numbers()`.

> Nota de contrato: a frase de 1 toque / 2 toques / HOLD do ticket é o contrato **aposentado**
> em 2026-11-01 (a própria ordem acima o substitui, e `docs/hotkey-gestos.md` o registra). O
> contrato em vigor, e o que esta lane mede, é **uma pressão = um passo imediato**:
> escondido → faixa (1), faixa → escondido (2), escondido → painel da direita (3),
> painel → escondido (4). Nada aqui mede duração de segurada nem janela de toques.

## Instrumento

* `_main/altc-gesture-oracle.py` — extrai com `ast` os corpos reais de `hotkey_pressed`,
  `hotkey_live`, `_hotkey_resolve` e do observador `PassiveHotkeyThread.run`, e executa-os
  contra um shell falso, um relógio-espião e um `threading`-espião. **Nenhuma janela, nenhum
  `ctypes`, zero `SendInput`/`keybd_event`.**
* Braço novo **(f)**: 4 pressões de `C` com o `Alt` em baixo, em duas formas — pela decisão
  (`hotkey_pressed` → `_hotkey_resolve` → `next_surface` → `show_strip`/`show_side`/
  `hide_panel`) e pelo observador real com o estado das teclas injetado (`key_state`, a costura
  que o módulo já tinha).
* Instrumento de fora, para a cadeia inteira real: `_main/_falsify/hotkey-spam-driver/driver.py`
  (`HotkeyThread` real com pump e fila de mensagens real, `hotkey_pressed` real, fila FIFO real,
  `_hotkey_resolve` real, `next_surface` do disco; só a janela é falsa). Sem registro global: o
  `HotkeyThread` corre com `register=False`.

## ANTES (medido nesta lane, antes de editar)

| medição | comando | número |
|---|---|---|
| braços do oráculo | `python _main/altc-gesture-oracle.py` | `arms=86 pass=86` |
| observador, `Alt` em baixo, 4 pressões de `C` com as soltas **perdidas** (código de antes) | mutante `combination-latch` (restaura o latch por combinação) no `--neg-arm` | **1** pressão, `accoes=['show']` |
| vocabulário das teclas | `grep -n "_MOD_BITS\|_MODIFIER_VK\|_MODIFIER_VARIANTS\|POLL_S" app/webview/sotto_webview.py` | **4** tabelas no shell + o parser no módulo |
| portão de janelas de consola | `python _main/console-window-audit.py` | **FAIL** — 1 sítio: `_main/line-closed-oracle.py:91 NO-FLAG larga node sem guarda` |

O `console-window-gate.py` que o ticket nomeia **não existe nesta árvore** (o `AGENTS.md` já o
diz: *"o `console-window-gate.py` que esta regra citava nunca existiu nesta arvore"*). O portão
real é `_main/console-window-audit.py` (censo AST) + `_main/console-window-watch.py` (vigia
vivo). Rodei o primeiro; o segundo lança um alvo no ecrã e não é preciso aqui.

## A mudança

### 1. `app/webview/hotkey_gesture.py` — os números passam a ter um dono só

Acrescenta `MODIFIER_BITS`, `MODIFIER_VKS`, `MODIFIER_VK_VARIANTS`, `POLL_S` e a função
`hotkey_numbers()` (dict, com cópias rasas). `next_surface` e o ciclo não mudaram; o docstring
do módulo passa a escrever o ciclo **por índice de pressão** (1 mostra a faixa, 2 esconde, 3
mostra o painel, 4 esconde) e diz que o índice é o `count=` do `HOTKEY_PRESSED`.

### 2. `app/webview/sotto_webview.py` — o shell deixa de ter cópia, e a pressão passa a ser da TECLA

* `parse_accelerator` lê `hotkey_numbers().MODIFIER_BITS`; `_MOD_BITS` apagado.
* `PassiveHotkeyThread.__init__` monta os grupos de VK com `hotkey_numbers().MODIFIER_VKS` /
  `.MODIFIER_VK_VARIANTS`; `_MODIFIER_VK`, `_MODIFIER_VARIANTS` e a classe `POLL_S` apagados.
* As constantes `MOD_ALT`/`MOD_CONTROL`/`MOD_SHIFT`/`MOD_WIN` foram apagadas: só existiam para
  alimentar `_MOD_BITS` (nenhum outro consumidor na árvore).
* **`PassiveHotkeyThread.run` — a cura do gesto.** Antes, um único teste cobria a combinação
  inteira (`fresh`/`down` sobre TODOS os grupos) e o latch `held` só re-armava quando todas as
  teclas subiam; uma solta perdida (o laço já publicou `max_gap_ms=609`) deixava o latch preso e
  o `C` martelado não dava segunda pressão. Agora o **modificador é condição** (`0x8000` agora
  ou `0x0001` desde a leitura anterior, no grupo dele) e a **pressão é a borda do grupo da
  TECLA**; o latch é por tecla, e uma borda NOVA conta mesmo com o latch de pé. Os grupos são
  lidos **todos** em toda a volta (sem `break`): ler é o que limpa o bit 0, e sair cedo deixava
  a borda de um `Space` solitário guardada para a volta seguinte.
  `HOTKEY_TRACE` passa a dizer `down=` (tecla) **e** `mods=` (condição).
* `parse_args`: `epilog` novo com as duas teclas (é o texto que `run.cmd --help` imprime).

### 3. `app/webview/run.cmd` — o texto que o dono lê

Bloco `THE TWO KEYS` no cabeçalho: `Alt+C` com a sequência por número de pressão e o `Alt`
preso, `Ctrl+Space` só display (modelo/worker/histórico continuam), e a proveniência dos
números (`hotkey_gesture.py`) e da escolha (`_main/hotkey-settings.json`).

### 4. `_main/altc-gesture-oracle.py` — braço novo e dois mutantes novos

* Arm 8 (f): a sequência `show,hide,show,hide` nas duas formas (decisão e observador real),
  `count=1..4`, e a asserção de que cada pressão fez **exactamente uma** mudança.
* `--neg-arm` ganha `blank-alternation` (o ciclo apagado: `next_surface` devolve sempre `strip`)
  e `combination-latch` (o latch por combinação de volta).

### 5. Fora do escopo declarado, por necessidade da aceitação

* `_main/line-closed-oracle.py`: o único `NO-FLAG` da árvore (`subprocess.run(['node', …])`)
  passa pelo helper da casa `_main/hidden-launch.py` (por caminho, o ficheiro tem hífen).
  Sem isto o portão de janelas de consola continuava vermelho por um ficheiro que não é desta
  lane. O oráculo continua 6/6 PASS e o `--neg-arm` continua 2/2.
* `_main/hotkey-live-toggle-oracle.py`: a namespace que injeta a classe extraída passou a
  fornecer `hotkey_numbers` (as duas tabelas `_MODIFIER_VK`/`_MODIFIER_VARIANTS` deixaram de
  existir no shell). É a migração obrigatória do cutover, não uma mudança de regra.

## DEPOIS (medido nesta lane, depois de editar)

| medição | comando | número |
|---|---|---|
| braços | `python _main/altc-gesture-oracle.py` | **ALTC-GESTURE GREEN — arms=96 pass=96 fail=0 (rc=0)** |
| braço (f), decisão | idem | `pressao 1: show strip \| pressao 2: hide strip \| pressao 3: show panel \| pressao 4: hide panel` |
| braço (f), observador real | idem | `presses=4 accoes=['show','hide','show','hide']`, `count=['1','2','3','4']`, também com as soltas perdidas |
| log do caminho | idem | `HOTKEY_TOGGLE step=show surface=strip`, `step=hide surface=strip`, `step=show surface=panel`, `step=hide surface=panel` |
| cadeia inteira real, 4 pressões com `Alt` em baixo | `python driver.py --tree H:/sotto-wt/HotkeyCtrlSpace --n 4 --label wt-n4` | `verdict=GREEN flips=4 visible_sequence=['show','hide','show','hide'] presses_delivered_by_pump=4 all_c_presses_inside_alt_held=True getasynckeystate_reads_during_run=0` |
| compilação | `python -m py_compile app/webview/hotkey_gesture.py app/webview/sotto_webview.py _main/altc-gesture-oracle.py _main/line-closed-oracle.py _main/hotkey-live-toggle-oracle.py` | OK |
| nomes indefinidos | `python _main/undefined-names-oracle.py` | `UNDEFINED-NAMES GREEN — 18 ficheiros de producao, 0 nomes usados e nunca definidos` |
| janelas de consola | `python _main/console-window-audit.py` | `CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela` |
| tela do dono | `python _main/lane-screen-gate.py` | `BATTERY-VERDICT lane-screen-gate PASS checks=3 fail=0` |
| `--help` do wrapper | `hidden-launch.run(['cmd','/c', r'app\webview\run.cmd','--help'])` | `rc=0`, `THE TWO KEYS` presente (o `.cmd` não abre janela) |

## Braço negativo

`python _main/altc-gesture-oracle.py --neg-arm` → **rc=1** (o contrato da casa: rc=1 quando
apanha). Os quatro mutantes:

| mutante | o que restaura | braços que derruba |
|---|---|---|
| `defer-400ms` | o adiamento de 400 ms | 15, incluindo (a) e (f) |
| `hold-threshold` | o limiar de HOLD no módulo do gesto | 2 |
| `blank-alternation` | `next_surface` devolve sempre `strip` (**a alternância apagada**) | 10, incluindo (f) |
| `combination-latch` | o latch por combinação | (f) com as soltas perdidas: `presses=1 accoes=['show']` |

Os dois portões adjacentes também medem o próprio detector: `console-window-audit.py --neg-arm`
rc=1 (`C1(os.system)=True C2(bit sozinho RED)=True C2(baseline perdoa)=True C3(o par
passa)=True`) e `line-closed-oracle.py --neg-arm` rc=1 (`mutants 2/2`).

## Ficheiros mudados

```
app/webview/hotkey_gesture.py        números + hotkey_numbers() + ciclo por índice de pressão
app/webview/sotto_webview.py         parse_accelerator, PassiveHotkeyThread(__init__, run), epilog
app/webview/run.cmd                  bloco THE TWO KEYS no cabeçalho
_main/altc-gesture-oracle.py         ARM 8 (f) + blank-alternation + combination-latch
_main/line-closed-oracle.py          node pelo hidden-launch (era o NO-FLAG do portão)
_main/hotkey-live-toggle-oracle.py   namespace: hotkey_numbers no lugar das tabelas apagadas
docs/hotkey-gestos.md                números, borda da tecla, arms=96, quatro mutantes, braço (f)
```

## O que NÃO consigo provar daqui

* **A app viva.** `pov-selftest`/o log do dono exigem uma instância; esta lane não larga janela e
  não toca em teclas. O caminho medido é o da app (corpos extraídos do ficheiro + `HotkeyThread`
  real com fila real), não o ecrã dele.
* **A tecla registada contra um `Alt+C` físico.** `RegisterHotKey` + `MOD_NOREPEAT` está provado
  estruturalmente (braço 5) e a entrega por `simulate_press` está provada no driver; o
  pressionador físico é `owner-hand`.
* **O latch do observador no processo vivo.** Medido com `key_state` injetado e um relógio
  virtual — determinístico, mas é o estado do Windows que não está aqui.
* `[INFERENCE]` O `State` de 4 pressões com `Alt` preso na app dele depende de a `Alt+C` estar
  registada para o processo (o log diz `HOTKEY_REGISTERED role=panels ... mod_norepeat=true`);
  isso é leitura do log dele, não desta lane.
