# RECIBO -- o menu da bandeja nunca ficava em primeiro plano (2026-11-10)

**VEREDITO: CURADO (receita do `AttachThreadInput` + log que diz o que o Windows
responde). NAO verificado no clique real do dono** -- a app nao estava a correr
(`SHELL_EXIT rc=0 reason=tray-quit`, 09:37:21) e um menu de bandeja so' se abre com
um clique no icone, que este recibo nao pode fabricar sem por uma janela no ecra
dele. A proxima linha `TRAY_MENU_FOREGROUND` diz qual das duas metades aconteceu
(ver §7).

Ficheiros tocados:

| ficheiro | o que mudou |
|---|---|
| `app/webview/sotto_webview.py` | `TrayIcon._show_menu` deixa de chamar `SetForegroundWindow` cru; passa por `TrayIcon._take_menu_foreground` (par de `AttachThreadInput`) e por `TrayIcon._restore_menu_foreground`; a linha `TRAY_MENU_FOREGROUND` passa a publicar o estado MEDIDO (`is_foreground`, `reason`, `attached`, `attach_err`, `fg_before`, `fg_thread`, `me_thread`, `fg_restored`); `user32.GetWindowThreadProcessId` ganha `restype`/`argtypes` |
| `_main/tray-menu-oracle.py` | o seam grava o par de `AttachThreadInput`; arms 19-21 (attach em volta da chamada, log = o que o SO diz, estado devolvido = o do SO); 2 mutantes novos |

Nao se tocou nos itens do menu, no texto, nos ids, no `refresh_menu`, no painel nem
no hotkey.

## 1. O estado ANTES (medido pelo assento principal, log vivo)

`_main/webview-run.log:187611-187634`, sesso~es de 2026-11-10 09:37 -- **13 de 13
`ok=0`**:

```
2026-11-10 09:37:16.317 sotto: TRAY_MENU_FOREGROUND ok=0 err=0 hwnd=40638334 is_foreground=0 menu_ms=47
2026-11-10 09:37:16.395 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=78
2026-11-10 09:37:16.856 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=31
2026-11-10 09:37:17.115 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=32
2026-11-10 09:37:17.174 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=15
2026-11-10 09:37:17.220 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=31
2026-11-10 09:37:17.275 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=47
2026-11-10 09:37:17.342 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=62
2026-11-10 09:37:17.431 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=78
2026-11-10 09:37:17.502 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=32
2026-11-10 09:37:17.562 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=31
2026-11-10 09:37:17.596 sotto: TRAY_MENU_FOREGROUND ok=0 err=1446 hwnd=40638334 is_foreground=0 menu_ms=15
2026-11-10 09:37:20.651 sotto: TRAY_MENU_FOREGROUND ok=0 err=0 hwnd=40638334 is_foreground=0 menu_ms=5063
```

O `err=1446` era carrego~es: o `SetForegroundWindow` nao publica `GetLastError`, o
valor lido era o ultimo erro alheio do fio. O SINAL e' o valor de retorno (0) e,
melhor, o que o sistema diz do primeiro plano -- `is_foreground=0`, 13/13.

## 2. A CAUSA, medida (nao assumida)

1. **A fechadura de primeiro plano deste hospedeiro esta' no MAXIMO.** O Windows
   so' deixa por uma janela em primeiro plano se o processo que chama fizer parte da
   lista curta (e' o processo em primeiro plano, foi lancado por ele, recebeu o
   ultimo evento de input, ... **ou a fechadura de primeiro plano expirou**). Com a
   fechadura a 24.8 dias, a ultima condicao nunca se verifica:

   ```
   GETFOREGROUNDLOCKTIMEOUT rc 1 value 2147483647      # SPI_GETFOREGROUNDLOCKTIMEOUT = 0x7FFFFFFF ms
   ```

2. **O clique do dono nao chega ao processo da bandeja**, chega ao `explorer` --
   logo a condicao "recebeu o ultimo evento de input" e' do explorer, nao nossa.
   E o processo da bandeja tambem nao e' o processo em primeiro plano (o Chrome
   do dono estava em primeiro plano: `fg hwnd 591320` title
   `"... - YouTube - Google Chrome"`).

3. **NAO e' a janela invisivel** (a hipotese (b) do pedido, REFUTADA por medicao).
   A mesma janela `WS_POPUP` foi testada escondida e com o bit `WS_VISIBLE` ligado
   (`ShowWindow(SW_SHOWNA)`, tamanho 0x0 -- nada e' desenhado), em ambos os casos
   com o Chrome em primeiro plano:

   ```
   W 24183830 hidden_visible_flag False fg0 1776462
   HIDDEN  SetForegroundWindow -> False is_fg False
   after SW_SHOWNA IsWindowVisible True
   VISIBLE SetForegroundWindow -> False is_fg False
   ```

   Tornar a janela visivel nao da' o primeiro plano. O que falta e' PERMISSAO.

4. **A receita documentada e' recusada por UIPI quando a janela em primeiro plano
   pertence a um processo de integridade mais alta**, e nesta bancada e' o que
   acontece -- nao por causa da receita, mas por causa de quem mede:

   ```
   me      {'rid': 8192}    # SECURITY_MANDATORY_MEDIUM_RID
   explorer{'rid': 12288}   # SECURITY_MANDATORY_HIGH_RID  (o explorer do dono corre em HIGH)
   Shell_TrayWnd hwnd 65866 pid 13884 tid 14540   attach(True)=0 err=5   # ERROR_ACCESS_DENIED
   Progman       hwnd 65976 pid 13884 tid 13888   attach(True)=0 err=5
   AttachThreadInput(fg_thread=12744, me) -> 0 err 5
   ```

   **A MEDICAO ACIMA E' FEITA A PARTIR DE UM PROCESSO MEDIUM** (o executor deste
   recibo). A app do dono e' lancada pela sessao dele, que nesta maquina corre em
   HIGH (`explorer` HIGH); um attach HIGH->HIGH e' permitido. Por isso este recibo
   NAO pode provar o `ok=1` da receita aqui -- prova a receita e prova a recusa.

## 3. O que foi acrescentado (sequencia exacta)

Dentro do clique (`_show_menu`), antes do `TrackPopupMenu`:

```
seq = user32.GetForegroundWindow()                      # quem esta' em primeiro plano AGORA
    me      = kernel32.GetCurrentThreadId()
    fg_tid  = user32.GetWindowThreadProcessId(seq)       # o fio dessa janela
    attach  = user32.AttachThreadInput(me, fg_tid, TRUE) # a receita: filas LIGADAS
    ctypes.set_last_error(0)  antes da chamada, para o attach_err ser deste chamamento
    ok      = user32.SetForegroundWindow(hwnd)           # instalado dentro do attach
    attach(me, fg_tid, FALSE)                            # no `finally` -- desligar e' obrigatorio
    is_fg   = (user32.GetForegroundWindow() == hwnd)     # o SO, nao o pedido
```

- o par de `AttachThreadInput` so' corre quando ha' um primeiro plano **de outro
  fio** (`seq` e `hwnd` diferentes, `fg_tid != me`); um attach aos nossos proprios
  fios nao faz nada e o `SetForegroundWindow` passa so' porque o processo ja' tem o
  primeiro plano (esse e' o caso `already-foreground`);
- ordem mantida: primeiro plano -> `PostMessage(WM_NULL)` -> `TrackPopupMenu`
  (a arm 5 continua a julga-la);
- **depois** do menu, `_restore_menu_foreground`: se o primeiro plano ainda for a
  nossa janela invisivel, devolve-o ao `fg_before`. Uma janela invisivel em primeiro
  plano come as teclas do dono; e se ele fechou o menu clicando noutra app, essa
  app ja' tem o foco e nao se lhe toca (so' corre quando `GetForegroundWindow()==hwnd`).

A linha do log passa a ser a medicao inteira:

```
TRAY_MENU_FOREGROUND ok=0 is_foreground=0 reason=attach-denied attached=0 attach_err=5 \
  fg_before=1776462 fg_thread=46092 me_thread=59384 fg_restored=0 hwnd=1573548 menu_ms=188
```

`reason` e' derivado do que o sistema devolveu: `already-foreground` |
`took-foreground` | `no-foreground-window` | `foreground-denied-attached` |
`attach-denied` | `foreground-denied-same-thread` | `foreground-denied` |
`failed:<Excecao>`.

## 4. Oraculo: `_main/tray-menu-oracle.py` (verbatim)

```
ARM PASS window_created hwnd=1573548
ARM PASS tray_thread_priority_raised now=1 (1 = ABOVE_NORMAL) log='TRAY_THREAD_PRIORITY was=0 now=1 ask=1 ok=1'
ARM PASS tray_loop_calls_the_raise TRAY_THREAD_PRIORITY no laco=True
ARM PASS hidden_on_owner_screen IsWindowVisible=0
ARM PASS toolwindow_no_taskbar exstyle=0x80
ARM PASS not_message_only ga_parent=0x1000C style=0x84000000
ARM PASS never_visible_bit style_visible=0
ARM PASS left_click_opens_panel posted=[(273, 1)] expected_id=1
ARM PASS right_click_opens_menu menu_shown=1 posted=[]
ARM PASS right_click_does_not_open_panel posted=[]
ARM PASS menu_recipe_order calls=['SetForegroundWindow', 'PostMessageW', 'TrackPopupMenu']
ARM PASS menu_posts_wm_null_before calls=[('AttachThreadInput', True, 59384, 46092, 0, 5), ('SetForegroundWindow', 1573548, 0), ('PostMessageW', 0, 1573548, 0), ('TrackPopupMenu', 258, 185, 935, 1573548, 12129191)]
ARM PASS menu_owned_by_tray_window calls=[('AttachThreadInput', True, 59384, 46092, 0, 5), ('SetForegroundWindow', 1573548, 0), ('PostMessageW', 0, 1573548, 0), ('TrackPopupMenu', 258, 185, 935, 1573548, 12129191)]
ARM PASS foreground_measured_and_logged log=['TRAY_LEFT_CLICK id=1', 'TRAY_COMMAND id=1', 'TRAY_MENU_FOREGROUND ok=0 is_foreground=0 reason=attach-denied attached=0 attach_err=5 fg_before=1776462 fg_thread=46092 me_thread=59384 fg_restored=0 hwnd=1573548 menu_ms=188']
ARM PASS menu_attaches_the_foreground_thread foreign=65976 steps=['AttachThreadInput', 'SetForegroundWindow', 'PostMessageW', 'TrackPopupMenu'] attach=[('AttachThreadInput', True, 59384, 13888, 0, 5)]
ARM PASS menu_foreground_log_is_what_the_os_says line='TRAY_MENU_FOREGROUND ok=0 is_foreground=0 reason=attach-denied attached=0 attach_err=5 fg_before=65976 fg_thread=13888 me_thread=59384 fg_restored=0 hwnd=1573548 menu_ms=0'
ARM PASS menu_foreground_state_is_the_os is_foreground=False os_says=False reason=attach-denied attach_err=5
ARM PASS menu_hotkey_item_says_disable_when_armed text=['Desativar atalho Alt+C']
ARM PASS menu_hotkey_item_says_enable_when_disarmed text=['Ativar atalho Alt+C']
ARM PASS menu_live_item_says_enable_with_accel text=['Ligar legendas (Ctrl+Space)']
ARM PASS menu_live_item_says_disable_when_on text=['Desligar legendas (Ctrl+Space)']
ARM PASS menu_keeps_the_three_shipped_ids ids=[1, 4, 5, 3, 2]
ARM PASS menu_is_built_once_and_reused menu_handles=[12129191, 12129191]
ARM PASS tray_command_routes_the_hotkey_id calls=['toggle']
ARM PASS tray_command_routes_the_live_id calls=['live']
CHECK arms=25 failed=0
VERDICT: PASS
```

As tres arms novas:

- **19 `menu_attaches_the_foreground_thread`** -- injecta um primeiro plano
  ESTRANGEIRO (`GetForegroundWindow` devolve `GetShellWindow()`), e exige que o par
  de `AttachThreadInput` apareca **antes** de `SetForegroundWindow` e (quando o
  attach passou) **depois** dele; a arm nao depende de o Windows conceder nada, so'
  da ordem, e por isso nao passa numa sessao e falha na outra.
- **20 `menu_foreground_log_is_what_the_os_says`** -- com o mesmo primeiro plano
  injectado, o `GetForegroundWindow` nunca devolve o `hwnd`, logo a linha TEM de
  dizer `is_foreground=0`, `fg_before=<o injectado>` e um `reason` de recusa:
  um `is_foreground=1` ali e' mentira e cai.
- **21 `menu_foreground_state_is_the_os`** -- sem injectar nada, compara
  `_take_menu_foreground()['is_foreground']` com um `GetForegroundWindow()==hwnd`
  lido fora da rotina. Se o Windows conceder, os dois dizem 1; se recusar, os dois
  dizem 0. O que nunca pode e' discordarem.

## 5. Braco negativo: `--neg-arm` (rc=1, mutacoes apanhadas)

```
MUTANT foreground_attach_removed: CAUGHT arms=['menu_attaches_the_foreground_thread'] detail=[('menu_attaches_the_foreground_thread', "foreign=65976 steps=['SetForegroundWindow', 'PostMessageW', 'TrackPopupMenu'] attach=[]")]
MUTANT foreground_log_hardcoded_to_1: CAUGHT arms=['menu_foreground_log_is_what_the_os_says'] detail=[('menu_foreground_log_is_what_the_os_says', "line='TRAY_MENU_FOREGROUND ok=0 is_foreground=1 reason=attach-denied attached=0 attach_err=5 fg_before=65976 fg_thread=13888 me_thread=25688 fg_restored=0 hwnd=17898202 menu_ms=0'")]
NEG-ARM SUMMARY cases=9 caught=9
NEG-ARM: PASS
neg-arm rc=1
```

Os 7 mutantes anteriores continuam apanhados (o seam filtra o par de attach da
sequencia que a arm 5 congela, para a cura nao passar por cima dessa arm).

## 6. Nada no ecra do dono

```
$ python _main/owner-screen-gate.py
populacao: 1123 ficheiro(s) de produto; achados=0 baseline=0
OWNER-SCREEN VERDICT PASS -- nenhum script abre janela no ecra do dono (achados=0 <= baseline=0)
```

E, com o oraculo a correr num filho escondido (`_main/hidden-launch.popen`), a
janela da bandeja foi sondada 266 vezes por `FindWindowW('SottoTrayWindow')`:

```
rc 0 samples 266
window-found samples: [(27.4, 35587080, False), (27.6, 35587080, False), (27.9, 35587080, False), ...]
any visible: False
classes after exit: 0
```

Nenhuma janela visivel, e a classe desaparece quando o processo sai.

O censo da casa (`_main/_armE-window-census.py`, psutil + `EnumWindows`), a correr o
oraculo:

```
CENSUS-PID pid_tree_root=61436 samples=1 visible_samples_over_tree=0 distinct=0 child_rc=0
```

(uma so' amostra porque cada iteracao desse censo custa segundos nesta maquina; e'
por isso que a sonda acima, a 250 ms, e' a que vale para "nao apareceu nada".)

```
$ python _main/lane-screen-gate.py
VERDICT: PASS
BATTERY-VERDICT lane-screen-gate PASS  checks=3 fail=0
```

## 7. O LIMITE DESTE RECIBO -- e o que o proximo clique vai dizer

`fixed, NOT verified on the owner's real click`. O que esta' provado:

- o defeito reproduz-se fora da app (processo medium, `SetForegroundWindow` numa
  janela invisivel -> `ok=0 is_fg=0`, o mesmo que os 13 cliques);
- a hipotese "e' a invisibilidade" esta' REFUTADA (uma janela com `WS_VISIBLE`
  recebe a mesma recusa);
- a receita esta' no caminho, na ordem certa, com o detach garantido;
- o log diz o que o sistema diz, e a arm 20 prova que nao mente.

O que NAO esta' provado: que no processo da app o `AttachThreadInput` seja
CONCEDIDO. Isso depende da integridade do processo da app comparada com a da janela
que estiver em primeiro plano (aqui: `explorer` HIGH, este processo MEDIUM,
`err=5`). A proxima linha `TRAY_MENU_FOREGROUND` responde, sem mais instrumentos:

- `reason=took-foreground is_foreground=1 attached=1` -> o menu tomou o primeiro
  plano e fecha com o primeiro clique fora (o defeito esta' fechado);
- `reason=attach-denied attach_err=5` -> o Windows recusou; o log nomeia a recusa
  em vez de a esconder, e o caminho seguinte e' subir a app ao mesmo nivel da
  janela que tem o primeiro plano (decisao do dono, nao deste recibo).
