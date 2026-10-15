# O DUPLICADO RESOLVIDO -- e resolvido de forma que nao o deixa sem legenda

Com a legenda numa janela propria, a legenda DENTRO do painel passava a ser uma
segunda. O dono quer a independente (*"nao acoplado"*), portanto a do painel tem de sair
-- mas tira-la de vez, antes de ele ter visto a nova, era deixa-lo sem legenda nenhuma
se a nova falhasse. **Sao duas coisas diferentes: tirar a antiga, e tira-la apenas
quando a nova esta mesmo no ecra.**

## Como ficou

`show_caption_window` escreve uma MARCA no documento do painel, DEPOIS de o `show()` da
janela da legenda ter corrido:

    self.window.evaluate_js(
        'document.documentElement.setAttribute('
        '"data-caption-window", %s)' % ('"on"' if on else '"off"'))

E a folha que a le e a `zip-overlay.css`, que e a ULTIMA a carregar:

    html[data-caption-window="on"] #caption-float { display: none !important; }

**A ORDEM E A REDE:** a marca so e escrita se o `show()` e o `evaluate_js` do estado
correrem. Se a janela falhar, a marca nunca chega, e a legenda do painel fica onde
estava. O dono nunca fica sem legenda nenhuma -- que era o unico risco real de tirar a
antiga.

**CUSTO:** um `exec_js` por TRANSICAO do live, nao por legenda. O atributo vive no
documento e a folha resolve-o sozinha a partir dai.

## E o que isto NAO resolve, dito

Um `try` em Python so apanha o que o Python ve. Se o `show()` devolver sucesso e a
janela ainda assim nao aparecer no ecra dele, a marca e escrita e a legenda do painel
esconde-se. **Por isso e que o passo seguinte continua a ser ELE confirmar a correr:** a
rede protege contra uma excepcao, nao contra um sucesso que mente. Um teste honesto disso
existe -- `IsWindowVisible` -- e a marca devia le-lo. Fica nomeado como o que falta.

`py_compile` rc=0, 541 726 B.
