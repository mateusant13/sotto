# As duas teclas: Alt+C = painéis, Ctrl+Space = legenda ao vivo

> Movido de `AGENTS.md` em 2026-10-23 (trim). **REESCRITO em 2026-11-01**: o
> contrato de 1 toque / 2 toques / HOLD foi aposentado pelo dono, e a legenda ao
> vivo mudou de tecla. Este ficheiro já descreveu dois contratos mortos
> (`HOTKEY_CAPTION_DEFER_MS`, `HOTKEY_GESTURE_MS`, `HOTKEY_HOLD_MS`,
> `HOTKEY_TAP_WINDOW_MS`, `HOLD_CEILING_MS`, `is_hold`, `resolve_taps`,
> `hotkey_hold`, `HotkeyThread._tick`) — **nenhum deles existe no código**. Um doc
> que descreve código removido é a segunda verdade que este repo paga caro.

## O contrato EM VIGOR (ordem do dono, 2026-11-01, verbatim)

> *"modifica a legenda ao vivo hotkey. bota o padrao como control espaço. e os
> painels deixa alt c. faz os paineis alternarem mesmo se eu deixar alt apertado
> o tempo inteiro e spammando c. alterna entre show e hide."*

| tecla | o que faz | código |
|---|---|---|
| **Alt+C** | **um passo** do ciclo dos painéis, por pressão: escondido → faixa de baixo, faixa → escondido, escondido → painel da direita, painel → escondido | `SottoShell.hotkey_pressed` → `_hotkey_resolve` → `hotkey_gesture.next_surface` |
| **Ctrl+Space** | liga/desliga a **legenda ao vivo**, uma vez por pressão, e **não toca em painel nenhum** | `SottoShell.hotkey_live` → `_set_live_enabled` |

**Um `WM_HOTKEY` = um passo, imediato.** Não há janela de espera, não há limiar de
duração, não há adiamento, não há segundo relógio: o `Alt` pode ficar em baixo o
tempo inteiro e o `C` pode ser martelado — cada entrega avança o ciclo uma vez.
`MOD_NOREPEAT` continua a garantir **um** `WM_HOTKEY` por pressão física.

O ciclo alterna o **próximo show** com a **memória da última superfície aplicada**
(`surface_applied`): escondido depois de uma faixa volta na faixa, escondido depois
do painel volta no painel. `hide_panel` **não** apaga essa memória — é ela que faz
`show/hide/show/hide` alternar em vez de repetir o mesmo painel.

## As teclas vivem num só sítio

`app/webview/hotkey_gesture.py` (`PANELS_ACCELERATOR = 'Alt+C'`,
`LIVE_ACCELERATOR = 'Ctrl+Space'`). O shell lê-as por `hotkey_numbers()` /
`hotkey_config()` e **não tem cópia**; `parse_accelerator` delega no módulo puro.
O ficheiro do dono é `_main/hotkey-settings.json` (`{"panels": "Alt+C",
"live": "Ctrl+Space"}`), escrito e validado por `hotkey_settings.write`: tecla
inválida ou ficheiro estragado **nunca** deixam a app surda — volta à fábrica e o
motivo vai para o log.

## O que foi apagado, e porquê

`HOTKEY_HOLD_MS = 200`, `HOTKEY_TAP_WINDOW_MS = 400`, `HOLD_CEILING_MS = 5000`,
`is_hold`, `resolve_taps`, `surface_for`, `hotkey_threshold`, `hotkey_hold`,
`_hotkey_tap_count`, `_hotkey_forget`, `_get_hotkey_hold`, `_set_hotkey_hold`,
`HotkeyThread._tick` / `_finish_measure` / `_measuring` / `_threshold` /
`_alt_is_down` / `_deliver_hold` / `fake_hold_ms`, e o `on_hold` que os ligava.
**Nada disto servia o contrato novo**: ele não pergunta a hora nem a duração a
ninguém, por isso cada um destes nomes era código morto a fingir de contrato.

A proveniência da remoção está medida, não afirmada — no log dele de 2026-10-30,
pressão de Alt+C → `PANEL_SHOWN` levava **460 ms**, dos quais **8 ms** eram
trabalho real: **87 % da latência era o nosso próprio adiamento**, e o limiar de
200 ms partia o gesto ao meio sempre que o `Alt` ficava em baixo. Hoje o caminho
não lê relógio nenhum.

O que **ficou**: `RegisterHotKey` + `MOD_NOREPEAT` (um evento por pressão),
`PeekMessage(PM_REMOVE)` + `WaitMessage` (pump ocioso, sem sonda periódica),
`UnregisterHotKey` no thread que registou, e `simulate_press` (posta o mesmo
`WM_HOTKEY` na fila — é o seam de medição; `keybd_event` mede o Windows, não a
app).

## Verificação

| instrumento | veredicto |
|---|---|
| `python _main/altc-gesture-oracle.py` | **ALTC-GESTURE GREEN — arms=86 pass=86** (medido 2026-11-01) |
| `python _main/altc-gesture-oracle.py --neg-arm` | **NEG-ARM PASS**: `defer-400ms` derruba 5 arms (10 pressões → 0 mudanças, `Timer` de 0,4 s armado, as duas pressões a 10 s viram uma) e `hold-threshold` derruba 2 (`HOTKEY_HOLD_MS`/`is_hold` de volta) |
| `python _main/altc-first-caption-oracle.py` | mede pressão → acção por **papel** (`role=panels` → `HOTKEY_TOGGLE`, `role=live` → `HOTKEY_LIVE_STEP`); sem log do build do disco dá `NO-MEASURE` (rc=2), que não é verde |
| `python _main/altc-first-caption-oracle.py --neg-arm` | **NEG-ARM PASS cases=12**, incluindo «pressão de uma tecla creditada com a acção da outra → NO-ACTION», «duas teclas na mesma sessão → vale a pior» e «uma tecla sem acção → NO-MEASURE, não verde» |
| `python _main/selftest-focus-oracle.py` | **PASS**: o braço «own window took the foreground» continua **RED**, o «control» **GREEN**; a excepção do Alt+C é declarada pela leitura, não presumida |
| `python _main/pov-selftest.py --run` (instrumento de fora, instância privada `--mutex-name SottoPovSelftest` + tecla livre `Alt+Shift+F12`) | **`SELFTEST rc=0`** medido 2026-11-01 10:28:27: `delivered=true presses=14`, dez alternâncias na ordem, `latency_ms=156,47,47,16,15,47,0,47,15,31,16,63,31,31,16`, `first_show_ms=156 first_show_slow=false budget_ms=1500` |

`_main/pov-selftest.py` é um instrumento **de fora**: não altera o shell, arranca uma
instância privada (`--mutex-name SottoPovSelftest`, `--no-hotkey`, `--no-worker`) que
arma só a tecla de sonda `Alt+Shift+F12` e lê o log dela; o dono nunca vê nada. Duas
execuções seguidas a 2026-11-01 ficaram presas em `STAGING_LOADED ... navigating to
panel` (CPU a 85%, `PRELOAD_INSTALLED` levou 19 s em vez de 4) e um `--wait 260`
resolveu-as; a lentidão é da máquina, não do gesto, e o instrumento não deve ser
afinado para ela.

Os braços do oráculo (lista impressa no arranque, e é a mesma que ele julga):

* **(a)** 10 pressões de Alt+C → **exactamente 10 mudanças** de visibilidade, com os
  shows a alternar `strip,panel,strip,panel,strip`;
* **(b)** duas pressões separadas por 10 s de relógio → **duas** mudanças;
* **(c)** uma pressão com 300 ms de relógio → **uma** mudança, e **nenhum** toggle de
  legenda;
* **(d)** Ctrl+Space → a legenda comuta **uma vez por pressão**, e nenhum painel mexe;
* **(e)** o braço VERMELHO: reinstalar o adiamento de 400 ms (ou o limiar de HOLD)
  derruba o oráculo — corrido, `--neg-arm`.

**A latência medida no caminho:** o braço (a) executa o corpo real de
`hotkey_pressed`/`_hotkey_resolve` extraído do ficheiro e cronometra
pressão → mudança de estado: **0,05 ms para as 10 pressões** (≈0,005 ms por
pressão; o dígito varia ao nível do microssegundo entre corridas). Não é o
número da janela — é o do passo, e mostra que o passo não tem espera nenhuma.

O pump REAL foi medido à parte (2026-11-01, `HotkeyThread(register=False)`):
10 `simulate_press` → **10 callbacks**, um por `WM_HOTKEY`, com a fila a dormir em
`WaitMessage` entre eles; `stop()` acorda-a e o `join()` fecha o thread. O número
do ecrã exige um largamento com janela e é `owner-hand` (`--selftest`, que **não**
arma as teclas globais: arranca um `HotkeyThread` de sonda com `register=False`,
mesma fila, mesmo pump).

### Entrega e latência são duas cláusulas (`--selftest`)

Até 2026-11-01 o veredicto do `--selftest` fundia-as: a espera de 3 s expirava, a
leitura dizia `pressed=false` e o teste culpava a **entrega** de uma **lentidão**.
Medido nesse dia: `SELFTEST rc=3` com `broken=the simulated press was not
delivered` numa app que alternava dez vezes em 432 ms. O que está lá agora:

| campo | o que prova | número |
|---|---|---|
| `posted` + `count=` do log | o `WM_HOTKEY` chegou ao shell | 14/14 |
| `latency_ms` | pressão → o ecrã mudou | `SELFTEST_STEP_BUDGET_MS = 1500` (a linha do dono, a mesma do `altc-first-caption`) |
| `first_show_ms` | a exibição FRIA, que paga o primeiro `exec_js` da página | 12 070 ms medidos 2026-11-01 (`HOTKEY_TOGGLE step=show` 10:14:47.808 → `PANEL_SHOWN` 10:14:59.878) |
| janela de medição | quanto o teste espera antes de desistir | 20 s na fria (`SELFTEST_COLD_WINDOW_S`), 6 s nas quentes, 2,5 s por pressão das dez |

Uma exibição fria de 12 s dá **RED por `latency_ms`** (`first_show_slow=true`),
nunca por "pressão não entregue". A arma 5 espera o par **exacto**
(`(visível, superfície)`) de cada pressão: `screen() != anterior` dispara no
`panel_mode` antes de a janela mapear e registava estados meio-aplicados.

### O foco: o show do Alt+C é a única excepção, e está escrita na app

`foreground_unlock` e `show_strip` dizem, em duas docstrings, que o invariante
`SW_SHOWNOACTIVATE` vale para **todos** os caminhos *"EXCEPT the owner's own
Alt+C: when he presses the app's only control he is asking for the panel"*, e
cada show da hotkey loga `PANEL_SHOWN ... focus_stolen=intentional(hotkey)`. O
veredicto passou a aceitar essa intenção declarada (`focus_steal_allowed`) e
continua a reprovar qualquer leitura que **não** a declare — o
`selftest-focus-oracle` prova-o: o braço `own window took the foreground`
continua **RED**, e o `control` continua **GREEN**.

## A auditoria completa

O caminho inteiro, a prioridade de cada gesto e a lista dos erros que continuam
vivem em **`docs/hotkey-altc-full-audit.md`** (ordem dele, 2026-10-30 09:33).

## O que continua verdadeiro do texto anterior

A medição de 2026-10-21 — 2 pressões a 400 ms dentro de uma janela de 250 ms
viravam "legenda on/off e nada" — foi real. O desenho que ela originou morreu
também; **a lição não**: o que o dono faz com a mão não é o que um contador de
eventos diz que ele fez. Ele pediu alternância, e alternância é uma contagem de
entrega, não uma leitura de relógio.
