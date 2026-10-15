O DOM NAO VEIO: --dump-dom deu 62 linhas de log, nao um DOM

Objectivo da rodada: descobrir em que elemento vive a linha em formacao que
transborda, com o DOM RENDERIZADO em vez de um grep ao ficheiro -- que foi o que me
deixou corrigir o contentor errado na rodada anterior.

MEDIDO: `sotto_webview.py --show --no-hotkey --dump-dom` deu 10 996 B em 62 linhas, e
NAO tem DOM nenhum:
  sem <body>, sem o markup do painel, sem o texto da legenda
  tem a palavra "captions" -- so nos nomes dos campos do log

Ou seja: a flag existe (run.cmd:102 marca NEEDS_STDOUT para ela) mas o que ela escreve
nao chegou ao stdout que capturei. Precisa de --dump-dom-wait, ou escreve noutro sitio,
ou precisa de a janela estar pronta antes de a pedir.

O que esta FEITO e o que FALTA, sem adornos:
  FEITO   o rotulo TRANSCRIPT saiu e foi visto com os olhos (B6)
          o HISTORICO/EM CURSO estao fora das barras, visto com os olhos (B5)
          a hipotese do bloco negro foi RETRACTADA com prova (limite 200 existe)
  FALTA   em que elemento vive a linha que transborda -- sem isso, qualquer correccao
          que eu faca e a mesma da rodada 3: um tiro as cegas que nao muda o render.
          E a comparacao E2 do print novo com a demo do .zip.

O instrumento que faltA nao e um grep -- e um que pergunte ao DOM. Enquanto nao o
tiver, o defeito do overflow fica ABERTO e nomeado, e nao "corrigido".
