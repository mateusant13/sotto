RETRACCAO: o bloco negro NAO e defeito -- ha um limite de 200, por desenho

Na rodada anterior disse ao dono, com numeros na mao, que o rectangulo negro era
historico sem limite e um defeito real. ESTAVA ERRADO, e a prova estava a duas
linhas de onde eu tinha medido.

MEDIDO AGORA:
  panel.js:41   /** Cap on rendered LIVE lines, matching MAX_CAPTIONS in the shell. */
  panel.js:42   const MAX_CAPTIONS = 200;
  panel.js:1037 while (dom.list.childElementCount > MAX_CAPTIONS) { ... removeChild(first) }
  sotto_webview.py:91   MAX_CAPTIONS = 200
  sotto_webview.py:3871 del self._shell.caption_log[:-MAX_CAPTIONS]

Ou seja: a lista viva TEM limite, 200, e o painel estava em 156 -- DEBAIXO do limite.
O que eu tomei por ausencia de limite era o limite a funcionar. E o mesmo erro de
sempre: procurei o defeito onde esperar encontra-lo em vez de onde o codigo estava.

O que ISSO muda, e e a parte util:

1. A minha afirmacao ao dono era falsa e tem de ser retratada. Um defeito que nao
   existe nao se corrige -- e se eu o tivesse "corrigido" tinha estragado o que funciona.

2. O que continua REAL, e visto com os olhos no mesmo print: a linha em formacao
   TRANSBORDA pela direita ("FRASE AINDA ESTA EM FORMA" cortada na margem). Isso e
   um defeito de verdade, e nao tinha sido visto por nenhum grep.

3. E a caixa vermelha "Preload bridge missing - captions are impossible" continua la,
   e e um TERCEIRO estado de erro que nao estava no mapa que eu medi.

4. Uma pergunta de DESENHO fica aberta, e nao e um defeito: 200 linhas de
   historico por baixo da legenda viva. O esboco do dono mostra a legenda, nao um
   transcript. Se ele quiser menos linhas visiveis, o numero desce -- mas isso e
   decisao dele, nao um bug meu.
