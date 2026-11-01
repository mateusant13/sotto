# O gesto do Alt+C (ORDEM 2)

> Movido de `AGENTS.md` em 2026-10-23 (trim). **REESCRITO em 2026-10-30**: o
> contrato de 1/2/3 pressões foi aposentado pelo dono. O texto anterior ficava
> a descrever dois números (`HOTKEY_CAPTION_DEFER_MS`, `HOTKEY_GESTURE_MS`) e um
> desfazer (`_undo_gesture_caption`) que **já não existem no código**; um doc que
> descreve código removido é a segunda verdade que este repo paga caro.

## O contrato EM VIGOR (ordem do dono, 2026-10-30, verbatim)

> *"1 tap = painel de baixo, 2 taps = painel da direita, HOLD = legenda ao vivo on/off"*

| gesto | o que faz | código |
|---|---|---|
| **1 toque** | painel de BAIXO (`show_strip`); **outro toque no MESMO painel fecha** | `SottoShell.hotkey_pressed` → `_hotkey_resolve` |
| **2 toques** | painel da DIREITA (`show_side`), promovendo a janela já mapeada | idem, via `hotkey_gesture.resolve_taps` |
| **HOLD** (≥200 ms) | legenda ao vivo liga/desliga, **ao cruzar o limiar** (não no release) | `HotkeyThread._tick` → `hotkey_hold` |

O número do gesto vive num só sítio: **`app/webview/hotkey_gesture.py`**
(`HOTKEY_HOLD_MS = 200.0`, `HOTKEY_TAP_WINDOW_MS = 400`, `HOLD_CEILING_MS = 5000`).
O shell lê-os por `hotkey_numbers()` e **não** tem cópia. O dono ajusta o limiar
no painel da direita (`hotkey_settings.hold_ms()`, escolhas 300/400/500/700/900/1200);
`hotkey_gesture.py` é o valor de fábrica.

### O limiar é 200 ms por ordem directa (2026-10-30)

Ele, verbatim: *"a porra do alt c, bota 200ms"*. O valor está em
`hotkey_gesture.HOTKEY_HOLD_MS = 200.0`, na lista que o painel da direita oferece
(`hotkey_settings.HOTKEY_HOLD_MS_CHOICES`, 200 primeiro) e no ficheiro vivo
`_main/hotkey-settings.json` (`{"holdMs": 200}`). **O risco está escrito, não escondido:**
com 200 ms, as pressões de 204, 438 e 468 ms da tabela abaixo passam a ser HOLD e comutam
a legenda em vez de mostrar o painel; as outras escolhas (300/400/500/700/900/1200) continuam no dropdown para
ele voltar atrás num clique.

### Porque é que o limiar era 500, passou a 900, e passou a 200 no mesmo dia

O 900 abaixo é **história medida**, não o valor em vigor: ele mandou pôr 200
(*"a porra do alt c, bota 200ms"*) e uma ordem dele substitui a calibração. A
tabela de 21 pressões continua a ser a prova de que 500 estava errado.

Ele, verbatim: *"EU TO APERTANDO ALT C E TA LIGANDO E DESLIGANDO A LEGENDA PORRA. O QUE
EU FALEI QUE E PRA ACONTECER?"*. As **21 pressões** dele nessa sessão, `held_ms` lidos
pelo `HotkeyThread` no log vivo:

```
93  110  187  204  438  468 | 531  578  641 ... 1187  1250  1344  2000  3047
   ele quer o PAINEL                       ^ limiar 500                ele quer a LEGENDA
```

**500 ms caía dentro do primeiro grupo.** 531, 578 e 641 ms eram toques de quem quer o
painel e viravam `HOTKEY_HOLD` — cada um comutava a legenda. O vazio entre o toque mais
lento (**641**) e a segura mais rápida (**1187**) é o único intervalo que os dados deixam
livre; 900 fica 259 ms acima de um e 287 ms abaixo do outro. Reposto o limiar sobre essas
14 pressões reais: **9 toques → painel, 5 seguras → legenda**, exactamente onde ele as põe.

O oráculo (`_main/altc-gesture-oracle.py`) **não** volta a pinar o número, e a
banda `641 < HOTKEY_HOLD_MS < 1187` que ele exigia **deixou de valer** quando o
dono escolheu 200 ms: uma escolha dele substitui a medição, e exigir a banda era
re-pinar contra o dono. O que os braços guardam hoje: o número de fábrica está na
lista que o painel oferece, pedir exactamente esse valor não é aproximado para
outro, e a **consequência** está escrita — com 200 ms o toque mais lento que ele
deu (641 ms) passa a ser HOLD.

## Porque é que o contrato antigo não podia funcionar

O dono, verbatim: *"o alt c nao ta dando display em qualquer painel"*.

O contrato de 2026-10-18 contava **pressões** dentro de uma janela
(`HOTKEY_GESTURE_MS = 700`) e dava a **um** toque a legenda — logo um toque
isolado **nunca mostrava painel nenhum**, e um Alt+C segurado caía em "triplo" e
mostrava o painel errado. Medido no log dele (2026-10-30, 163 rajadas):

| pressões por rajada | 1 | 2 | 3+ |
|---|---|---|---|
| rajadas | 56 | 34 | **73** |

73 de 163 rajadas eram um Alt+C **segurado**. Um contador de presses não é o
gesto.

## Como o gesto é medido agora

`RegisterHotKey` com `MOD_NOREPEAT` entrega **um** `WM_HOTKEY` por pressão e
**nenhum** evento de libertação. A duração lê-se de
`GetAsyncKeyState(VK_MENU)`: o Alt ainda está em baixo quando o `WM_HOTKEY`
chega, e sai quando o dono larga. Para isso a thread da hotkey deixou de
bloquear em `GetMessageW` e passou a `PeekMessage(PM_REMOVE)` + 10 ms de sonda
(`HotkeyThread.run`), e cada entrega escreve
`HOTKEY_PRESSED count=N held_ms=D` — auditável no log dele.

**A legenda desligada é só DISPLAY.** `hotkey_hold` chama `_set_live_enabled` e
mais nada: não descarrega motor, não reinicia worker, não mexe em painel (o
oráculo verifica no **código**, não na docstring).

## Verificação

| instrumento | verdicto |
|---|---|
| `python _main/altc-gesture-oracle.py` | **ALTC-GESTURE GREEN — arms=90 pass=90** (medido 2026-10-30 11:5x; eramm 38 quando o passo nasceu) |
| `python _main/altc-gesture-oracle.py --neg-arm` | **NEG-ARM PASS** (mutante `resolve_taps` → `'strip'` derruba 3 arms) |

Passos da bateria: `altc-gesture` + `red-as-expected-altc-gesture` (ambos
`always`). **Eles substituem três passos** — `hotkey-cycle`, `hotkey-gesture` e
`hotkey-triple` — cujos ficheiros foram apagados: mediam o contrato aposentado,
ficaram vermelhos pela razão certa, e re-piná-los seria fixar um comportamento
que já não existe.

## A auditoria completa

O caminho inteiro, a prioridade de cada gesto e a lista dos erros que continuam
vivem em **`docs/hotkey-altc-full-audit.md`** (ordem dele, 2026-10-30 09:33).

## O que continua verdadeiro do texto anterior

A medição de 2026-10-21 — 2 pressões a 400 ms dentro de uma janela de 250 ms
viravam "legenda on/off e nada" — foi real, e é a proveniência da decisão de
separar relógios. Esse desenho morreu com o contrato; **a lição não**: o que o
dono faz com a mão não é o que um contador de eventos diz que ele fez.
