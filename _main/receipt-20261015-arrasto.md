# "ARRASTAR ESTA TRAVADO" -- a resposta, e nao era o codigo do arrasto

O dono: *"a porra de arrastar a janela e completamente travado"*.

## MEDIDO: ele NUNCA entrou em modo de edicao

Contagem no log inteiro (`_main/webview-run.log`):

    TRAY_COMMAND      = 5     <- todas elas QUIT
    TRAY_QUIT         = 5
    TRAY_EDIT         = 0     <- NUNCA
    TRAY_OPEN         = 0     <- NUNCA
    PANEL_EDIT_MODE   = 0     <- NUNCA
    PANEL_EDIT        = 0

E o menu da bandeja existe -- esta no log, duas vezes:

    TRAY_MENU [1]='Open panel' [3]='Edit caption position' [sep] [2]='Quit Sotto'

## A CONCLUSAO, e nao e um bug do arrasto

O arrasto esta implementado e o caminho esta completo: bandeja -> `ID_TRAY_EDIT` ->
`set_edit_mode` -> `edit_mode=True` -> o hook passa a tratar o movimento ->
`WM_EDIT_DRAG` -> `edit_drag_to` -> `SetWindowPos`. **Nada disso correu uma vez.**

**O defeito e de DESENHO:** o arrasto so existe DENTRO de um modo de edicao que mora
num item da bandeja. O dono arrasta a janela, nada mexe, e nao ha razao nenhuma para
ele suspeitar que tem de ir a bandeja primeiro. Ele usou a bandeja CINCO vezes e todas
elas para sair -- o que e exactamente o que se espera de um menu que ele nao tem motivo
para explorar.

E o pedido dele nao fala de modo nenhum. [32218], verbatim: *"o painel de baixo tem que
ser movivel pra cima ou pra baixo ou pros lados"*. **Ele pediu um painel MOVEL. O que
existe e um painel movel SE ele descobrir um item de bandeja.**

## O que ficou feito nesta rodada, e o que falta

FEITO: os tres `return False` MUDOS do `edit_drag_to` passaram a escrever no log
(`PANEL_EDIT_DRAG_REFUSED why=... edit_mode=... moves=...`, rate-limited a uma linha por
segundo). Antes, "esta travado" nao deixava rasto nenhum para se ler; agora deixa. E o
`py_compile` esta rc=0.

A CORRIGIR, e e a proxima: **tirar o arrasto de tras do modo de edicao.** O caminho que
respeita o pedido dele e o corpo do painel ser uma PEGA: a barra de baixo ja e
interactiva (tem botoes), portanto arrastar o corpo da barra move a janela, mantendo os
botoes clicaveis. A complicacao esta dita no `set_edit_mode`: o painel e click-through
(`WS_EX_TRANSPARENT`) para o Alt+C ser usavel sobre um filme, e e por isso que o modo de
edicao existe. Uma pega no corpo da barra nao precisa de levantar esse bit no painel
inteiro -- so na barra, que ja e a superficie interactiva.

## E a licao, que e desconfortavel

Eu passei tempo a ler `edit_drag_to`, `edit_grab`, os clamps, a `work_area()` -- a
procura de um bug dentro de uma funcao que **nunca correu uma vez**. Um unico `Select-String
"TRAY_EDIT"` no log teria respondido em segundos. **A regra: antes de ler o codigo de um
caminho, medir se o caminho JA correu.**
