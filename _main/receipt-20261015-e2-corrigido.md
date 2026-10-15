# E2 CORRIGIDO E MEDIDO: o fundo deixou de ser a banda mais clara

O dono: "compara as prints das demos dos .zip com as prints do que ta implementado
atual. eu nao gostei dos atuais. e pra imitar mais os .zip."

O INSTRUMENTO: _main/zip-fidelity-by-numbers.py -- compara a demo do zip e o painel
shipped por NUMEROS (perfil de luminancia em tercos, fracao escura, energia de arestas,
cor da tinta). Nao confia em olho, e esta sessao retractou tres vezes por acreditar na
minha propria leitura de um print.

O DEFEITO MEDIDO, e era de FORMA:
  demo  top=0.144 mid=0.162 bot=0.084   claro em cima, ESCURO em baixo
  shot  top=0.108 mid=0.091 bot=0.140   escuro em cima, CLARO em baixo
A zona da legenda -- que devia ser a mais escura -- era a MAIS CLARA do ecra. O zip
(index.css:90-98) escurece o fundo com `.scrim-bottom` (`to top, var(--scrim) 0%,
transparent 100%`), porque as palavras sao o que tem de vencer.

AS QUATRO TENTATIVAS, cada uma com o numero que a mediu:
  1. overflow-x em .captions__body ........ sem efeito (o tema sobrepoe-se)
  2. overflow-x em #caption-float ......... sem efeito (a linha nao vive la)
  3. gradiente com --bg-slab-strong ...... bot 0.140 -> 0.150, PIOROU (token CLARO)
  4. escuro --bg-slab, largo ............. bot 0.108 mas mid 0.061 (demasiado largo)
  5. escuro --bg-slab, apertado ao fundo .. bot 0.105, mid 0.082  <- ESTA

O RESULTADO, medido:
  antes  top=0.108 mid=0.091 bot=0.140   DELTA bot = 0.056
  depois top=0.108 mid=0.082 bot=0.105   DELTA bot = 0.020   medio 0.054 -> 0.045

O fundo passou de banda mais clara para a mais escura, que e a forma da demo. O que
FALTA, e esta dito: o meio. A demo tem mid=0.162 (a fotografia) e o theme-1 nao tem
fotografia -- mid=0.082. Isso nao e um defeito de codigo, e uma decisao de desenho: se
os temas theme-N devem ter cena fotografica como os cine-*, isso e uma escolha.

O que ficou no gerador, com a medicao que o justifica: o escuro e HELD flat nos
ultimos 22% da caixa e desaparece aos 52% -- a forma do .scrim-bottom do zip com o
token escuro do proprio tema.
