# ALT+C: a tecla regista e o ciclo avanca, MAS o painel nao vem para a frente

## O que esta MEDIDO (log do dono, 2026-10-16)

  * HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true mod_norepeat=true
    -- cinco vezes, uma por arranque. A tecla NAO esta tomada e regista sempre.
  * O CICLO AVANCA: 05:57:04 strip, 05:57:04 side, 05:57:07 strip, 05:57:11 side, com
    PANEL_HIDDEN pelo meio. HIDDEN -> STRIP -> SIDE -> HIDDEN, que e o contrato dele.
  * MAS: PANEL_FOREGROUND_UNLOCK ok=FALSE nas quatro. O SetForegroundWindow e RECUSADO.

## A causa

O Windows so deixa um processo por o seu janela em primeiro plano se JA for o processo em
primeiro plano (ou tiver recebido o ultimo input). A shell do Sotto e um processo de fundo
com janela invisivel: o pedido e recusado por REGRA DO SISTEMA, nao por defeito do codigo.

Consequencia pratica: o painel e mapeado e fica TOPMOST, mas nao ganha o foco -- e aparece
ATRAS da janela que ele esta a usar. Para ele, Alt+C nao faz nada.

## A cura aplicada

`AttachThreadInput`: enquanto a nossa fila de input esta LIGADA a do thread que tem o
primeiro plano, o Windows trata os dois como um so para efeitos de activacao, e a chamada
passa. Desligar no finally e obrigatorio -- deixar as filas ligadas prende o input dos dois
processos um ao outro.

    def _foreground_steal_attached(hwnd):
        fg = GetForegroundWindow(); t_fg = GetWindowThreadProcessId(fg); t_me = GetCurrentThreadId()
        attached = AttachThreadInput(t_me, t_fg, True)
        BringWindowToTop(hwnd)
        ok = SetForegroundWindow(hwnd)
        finally: AttachThreadInput(t_me, t_fg, False)

E o `foreground_unlock` passou a INSISTIR por este caminho quando a chamada simples falha.
Log proprio: PANEL_FOREGROUND_ATTACH ok=<bool> fg_thread=<n> me_thread=<n> attached=<bool>.

MEDIDO em processo, sem lançar a app e sem tocar no ecra: o helper existe, os argtypes estao
declarados, a chamada com hwnd=0 devolve False sem levantar, e o ATTACH respondeu
`attached=true`. py_compile rc=0, 560 259 B.

## O que NAO esta provado

Nao houve uma pressao fisica de Alt+C depois desta cura. O que esta provado e o mecanismo e
que o caminho corre. A prova final e o log dele a mostrar PANEL_FOREGROUND_ATTACH ok=true
na proxima vez que premir a tecla -- com o painel a aparecer POR CIMA.

## E um facto que explica metade da queixa

A app estava FECHADA: o shell morreu as 06:20:50 sem SHELL_EXIT e sem dump (a ultima saida
limpa foi 05:43:35). Sem shell nao ha tecla. Reiniciei-a (pid 11168 as 06:56:50) e o log
confirma HOTKEY_REGISTERED + caption window created + as duas curas de transparencia.
