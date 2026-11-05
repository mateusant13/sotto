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

> **CICLO DE TRÊS CASAS (corrigido a 2026-11-05, ordem do dono, verbatim):**
> *"meu double alt c ta dando hide no painel de baixo. sendo que o double alt c
> era pra mostrar o painel da direita"*. O ciclo anterior escondia no segundo
> toque e só mostrava o painel da direita depois de um hide pelo meio — com dois
> painéis, um ciclo de duas casas nunca mostra os dois. Ordem em vigor:
>
> | pressão | ecrã |
> |---|---|
> | 1 (de escondido) | faixa de **baixo** |
> | 2 | painel da **direita** |
> | 3 | **escondido** |
> | 4 | faixa de baixo outra vez |
>
> Um toque é instantâneo (nenhum relógio no caminho) e DOIS toques seguidos
> caem no painel da direita. `_main/altc-gesture-oracle.py` — 97 arms, e o
> mutante `blank-alternation` (o ciclo apagado) tem de dar RED.

| tecla | o que faz | código |
|---|---|---|
| **Alt+C** | **um passo** do ciclo de três casas, por pressão: escondido → faixa de baixo → painel da direita → escondido | `SottoShell.hotkey_pressed` → `_hotkey_resolve` → `hotkey_gesture.next_surface` |
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

**Os NÚMEROS também vivem lá desde 2026-11-04.** `MODIFIER_BITS` (nome→bit do
`RegisterHotKey`), `MODIFIER_VKS` (o VK genérico), `MODIFIER_VK_VARIANTS` (os VK
laterais) e `POLL_S` (a cadência do observador) estão em `hotkey_gesture.py`,
expostos por `hotkey_numbers()`; o shell lê-os por aquele acesso e não guarda
nenhuma das quatro tabelas. Antes disto o shell tinha as três primeiras e o
parser vivia no módulo — duas verdades sobre a mesma tecla, e a segunda envelhece
sozinha (`_MOD_BITS`, `_MODIFIER_VK`, `_MODIFIER_VARIANTS` e as constantes
`MOD_ALT`/`MOD_CONTROL`/`MOD_SHIFT`/`MOD_WIN`, que só existiam para alimentar
`_MOD_BITS`, foram apagados). A ABI que o shell precisa de escrever —
`MOD_NOREPEAT`, `WM_HOTKEY`, o id da tecla — fica do lado de quem fala com o
Windows.

**A pressão do Ctrl+Space é da TECLA, não da combinação** (2026-11-04). O
observador lê `GetAsyncKeyState`: o modificador é uma **condição** (`0x8000` em
baixo agora, ou `0x0001` "carregado desde a leitura anterior") e a pressão é a
**borda do grupo da tecla**. O latch (`held`) é por tecla, então ele só evita que
a tecla em baixo conte a cada volta; uma borda NOVA conta mesmo com o latch de pé.
Antes o mesmo teste cobria as duas coisas: uma solta perdida (o laço já publicou
`max_gap_ms=609`) deixava o latch preso e o `C` martelado não dava segunda
pressão — o braço (f) do oráculo mede exatamente esse caso.
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
| `python _main/altc-gesture-oracle.py` | **ALTC-GESTURE GREEN — arms=96 pass=96** (medido 2026-11-04) |
| `python _main/altc-gesture-oracle.py --neg-arm` | **NEG-ARM PASS, rc=1**: `defer-400ms` derruba 5 arms (10 pressões → 0 mudanças, `Timer` de 0,4 s armado, as duas pressões a 10 s viram uma), `hold-threshold` derruba 2 (`HOTKEY_HOLD_MS`/`is_hold` de volta), `blank-alternation` derruba 10 (o ciclo deixa de esconder: `next_surface` devolve sempre `strip`) e `combination-latch` derruba o braço (f) com o observador a contar **1** pressão em 4 (medido 2026-11-04) |
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
* **(e)** o braço VERMELHO: reinstalar o adiamento de 400 ms, o limiar de HOLD,
  **apagar o ciclo** ou repor o latch por combinação derruba o oráculo — corrido,
  `--neg-arm` (quatro mutantes, rc=1);
* **(f)** **4 pressões de `C` com o `Alt` em baixo o tempo inteiro**, pelo caminho
  real: o corpo de `hotkey_pressed` → `_hotkey_resolve` → `next_surface` → os
  `show_strip`/`show_side`/`hide_panel` do ficheiro, e depois o **observador real**
  (`PassiveHotkeyThread.run`, com o estado das teclas injectado). A sequência
  exigida é `show,hide,show,hide` — **pressão 1 mostra a faixa, 2 esconde, 3 mostra
  o painel da direita, 4 esconde** — e as quatro contam `count=1..4` mesmo quando a
  solta entre duas pressões **cai inteira entre duas voltas** do observador (o
  `max_gap_ms=609` medido). Uma solta perdida atrasa a pressão seguinte; nunca a
  engole.

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

### O foco: ninguém perde o teclado — a excepção é o cursor CAPTURADO

`foreground_unlock` existia para *"todos os Alt+C"*, com a justificação escrita na
app de que *"when he presses the app's only control he is asking for the panel"*,
e cada show da hotkey logava `focus_stolen=intentional(hotkey)`. O
`pov-selftest` reprovava-o com toda a razão
(`broken=the panel TOOK the foreground ... SW_SHOWNOACTIVATE is the contract`):
o painel é `WS_EX_TRANSPARENT`, portanto o roubo do primeiro plano **não lhe dava
clique nenhum** — só tirava o teclado a quem ali estava (as setas do YouTube, a
caixa onde se escrevia).

O que aquele roubo comprava era o **rato de volta** quando um jogo tem o cursor
capturado: é perder o primeiro plano que faz o *pointer-lock* ser largado. Isso
só é verdade **quando há captura para largar**, e é isso que passou a ser medido
(`pointer_captured()` → `GetClipCursor` comparado com o ecrã virtual):

| estado do cursor | o que o show faz | o que o log diz |
|---|---|---|
| livre | `set_topmost` + `SW_SHOWNOACTIVATE` | `show=SW_SHOWNOACTIVATE mapped=true focus_stolen=false` |
| capturado (jogo) | `foreground_unlock` (recupera o rato) | `show=SW_SHOW+FOREGROUND focus_stolen=intentional(pointer-lock)` |

`map_panel()` é a única função que decide isto, para a faixa e o painel da
direita não divergirem. O veredicto do `selftest` continua a aceitar a excepção
**declarada pela leitura** (`focus_steal_allowed`) e reprova qualquer roubo que
não a declare — o `selftest-focus-oracle` prova-o: o braço `own window took the
foreground` continua **RED**, e o `control` continua **GREEN**.

## A auditoria completa

O caminho inteiro, a prioridade de cada gesto e a lista dos erros que continuam
vivem em **`docs/hotkey-altc-full-audit.md`** (ordem dele, 2026-10-30 09:33).

## O que continua verdadeiro do texto anterior

A medição de 2026-10-21 — 2 pressões a 400 ms dentro de uma janela de 250 ms
viravam "legenda on/off e nada" — foi real. O desenho que ela originou morreu
também; **a lição não**: o que o dono faz com a mão não é o que um contador de
eventos diz que ele fez. Ele pediu alternância, e alternância é uma contagem de
entrega, não uma leitura de relógio.

## `Ctrl+Space`: TOMADO fora de jogo, DEVOLVIDO ao jogo (2026-11-05)

Ordem do dono, verbatim: *"faz o control espaço nao inputar espaço pra outros
apps. mas desativa isso em jogos. entao control espaço em um jogo pode sim
apertar espaço. só que nao vai ter display de legenda, pra ter, tenho que dar
alt c e ativar manualmente"*.

Duas metades, uma tabela só — `gaming_mode.live_hotkey_plan`, pura e medida:

| em jogo? | registo | o que acontece |
|---|---|---|
| não | `RegisterHotKey` + `MOD_NOREPEAT` | o Windows entrega `WM_HOTKEY` à shell; **o espaço não chega à janela em foco** e a legenda alterna |
| sim | `UnregisterHotKey` | o jogo recebe o `Ctrl+Space` **nativo** (sem `SendInput`, logo sem o problema do raw input) e a shell **não alterna nada** |

A legenda dentro do jogo liga-se com o **Alt+C** e o botão LIVE do painel — a
tecla não é um caminho alternativo para isso.

O fio é `LiveHotkeyThread` (`app/webview/sotto_webview.py`): pump com prazo de
250 ms, relê o modo, `take`/`give-back` na transição, e **uma linha de log por
transição** (`HOTKEY_LIVE_MODE mode=swallow|passthrough gaming=<bool>`), nunca uma
por volta. Um `WM_HOTKEY` que já estava na fila quando o jogo chegou **não
alterna** (`suppressed=true why=not-swallowing`): a fila não pode decidir por ele.

Sem detector de jogo, ou com o registo recusado (`winerror=1409`, outro programa
tem a combinação), a tecla **não é tomada**: fica o observador de 2026-11-02, que
alterna a legenda e **deixa o espaço passar**, e o log diz
`swallow=false the_key_passes_through=true` — um recuo declarado, não um
silêncio.

Provas: `_main/ctrlspace-swallow-oracle.py` (14 arms contra o `user32`-gravador;
`--neg-arm` 4/4) e `_main/ctrlspace-swallow-probe.py`, que mede no Windows desta
máquina o que nenhum fake dá — medido: primeira reserva `1`, segunda reserva da
mesma combinação `0` com `err=1409`, terceira depois do `Unregister` `1`.

