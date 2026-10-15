COM OLHOS: o que o print novo mostrou, e tres defeitos que o grep nao viu

A visão foi habilitada (o interruptor estava no perfil WEB, não no headless).
O primeiro print novo do painel (theme-1, 380x900) mostra:

CAB ECALHO: SOTTO - EM ESPERA - [icone] Teleprompter - A A [pausa] [X]
   -> correcto: o HISTORICO e o EM CURSO sairam das barras (B5 confirmado com olhos).

NO CANTO SUPERIOR ESQUERDO: "TRANSCRIPT" com um icone de pasta, AINDA renderizado.
   -> o dono disse "tira o botao de transcript". O CONTROL (o toggle) saiu, mas o
      ROTULO da gaveta continua la. B6/C8 precisam de decisao: o rotulo sai tambem?

O BLOCO NEGRO QUE O DONO CHAMOU DE GLITCH: nao e um glitch -- E A LISTA DE LEGENDAS.
   Medido no panel-state.json ao mesmo tempo:
     live.count            = 156 linhas
     scroll.height         = 10 810 px
     scroll.client         = 766 px
     scroll.overflowing    = true, top = 10 044, atBottom = true

   Ou seja: 156 linhas de transcri EMPILHADAS numa janela de 766 px, e o painel
   mostra a mais recente no fundo. O "rectangulo preto" e esse scrollback. E um
   defeito real e conhecido do registro: o historico nao tem limite -- TO-12 media
   3 000 escritas/h e 77 MB/h com uma lista de 200 linhas. Aqui estao 156 e ja dao
   10 810 px.

A CAIXA VERMELHA NO FUNDO: "Preload bridge missing - captions are impossible".
   -> Este E o erro vermelho que o dono reportou, e aparece quando o shell de medicao
      corre sem a ponte. Nao e o silent-device. E um terceiro estado de erro, e nao
      estava no mapa que eu medi.

O QUE ISTO MUDA: tres coisas que eu afirmei com grep precisam de revisao com olhos,
e uma que eu nao tinha visto de todo (a caixa vermelha do preload). O registro diz
agora o que foi VISTO e nao so o que foi medido em bytes.
