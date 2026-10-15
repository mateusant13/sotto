# "ARRASTAR TA TRAVADO" -- NAO ESTA TRAVADO, ESTA A VIBRAR. E o laço tem numero

O dono: *"a porra de arrastar a janela e completamente travado"*.

## MEDIDO: o arrasto CORRE, e move a janela

    STRIP_DRAG           = 1 498 ocorrencias no log
    STRIP_DRAG_REFUSED   = 0        (nenhuma recusa)

Ou seja: o caminho pagina -> `setStripOffset` -> `_set_strip_offset` -> `SetWindowPos`
esta LIGADO e a mover a janela de verdade. **A primeira hipotese -- "nao chega la" -- esta
morta.**

## E o que ele FAZ, linha a linha

    13:57:46.096  phase=move  offset=(22,-102)  to=(801,804)  base=(779,906)
    13:57:46.100  phase=move  offset=(16, -94)  to=(795,812)  base=(779,906)
    13:57:46.111  phase=move  offset=(22,-102)  to=(801,804)  base=(779,906)
    13:57:46.117  phase=move  offset=(16, -94)  to=(795,812)  base=(779,906)
    13:57:46.127  phase=move  offset=(22,-102)  to=(801,804)  base=(779,906)
    13:57:46.142  phase=end   offset=(22,-102)  to=(801,804)  base=(779,906)

**A janela salta entre DUAS posicoes, 6 px em x e 8 px em y, ~11 ms entre saltos.** O
`base` nunca muda -- esta fixo em (779,906) -- mas o `offset` ALTERNA. Isso e um **LACO DE
REALIMENTACAO**, e o mecanismo e este:

  1. a pagina calcula o deslocamento do ponteiro em relacao a posicao VIVA da janela;
  2. o shell move a janela para esse deslocamento;
  3. **mover a janela muda a posicao do ponteiro em relacao a ela**;
  4. volta ao passo 1, com um numero diferente -- e o ciclo nunca converge.

**Nao e lentidao nem bloqueio: e uma ida-e-volta infinita entre dois pontos.** O dono sente
"travado" porque a janela resiste a sair do par de posicoes em vez de seguir o rato.

## O caminho existe, e este e o numero que faltava

O `_set_strip_offset` foi escrito com o cuidado certo -- o comentario diz *"The offset is
CUMULATIVE from the dock, so this never accumulates a delta -- `_strip_dock_base` is the
fixed origin"* -- e o `base` esta mesmo fixo no log. **O defeito nao esta no shell: esta em
QUEM CALCULA o offset.** O shell faz o que lhe pedem, fielmente, 1 498 vezes.

## O que fica por fazer, e e uma linha de JS

O offset tem de ser calculado da posicao do ponteiro no INICIO do arrasto e do ponto de
agarre no INICIO -- `pointer_now - pointer_start` -- e nao da posicao viva da janela. Assim
o numero nao depende de a janela ja ter andado, e o laco desaparece.

Fica nomeado com o ficheiro e a linha: o drag da barra esta em `panel.html` (~:1087, o
comentario do shell cita-o) e chama `bridge.setStripOffset({x, y, phase})`.

## E uma nota sobre o metodo

**Antes de ler o codigo do arrasto outra vez, medi se ele corria** -- e corre. Depois olhei
o que ele FAZ, e o que ele faz esta escrito 1 498 vezes no log. **Duas leituras do log
responderam o que eu ia tentar deduzir do codigo.**
