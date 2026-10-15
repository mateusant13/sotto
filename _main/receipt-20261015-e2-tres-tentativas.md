# A TERCEIRA TENTATIVA DE CORRIGIR O E2 PIOROU -- e reverti

O E2, medido por _main/zip-fidelity-by-numbers.py contra a demo do zip D:
  demo  top=0.144 mid=0.162 bot=0.084   (claro em cima, escuro em baixo)
  shot  top=0.108 mid=0.091 bot=0.140   (escuro em cima, claro em baixo)

O PERFIL DE LUZ ESTA INVERTIDO, e a zona da legenda -- que devia ser a mais escura --
e a mais clara do ecra.

TENTATIVA 1: `overflow-x: hidden` em `.captions__body`. Sem efeito -- o tema sobrepoe-se
com um selector mais especifico (`:root[data-theme=...] .captions__body`).

TENTATIVA 2: `overflow-x: hidden` em `#caption-float .caption-float__line`. Sem efeito --
a linha nao vive la.

TENTATIVA 3 (esta): no gerador, passar o fundo de `.captions__body` de PLANO para um
gradiente com peso no fundo. O render mudou (62 859 -> 68 732 B, logo a regra pegou),
mas a medicao diz que PIOROU:
  antes  bot=0.140
  depois bot=0.150

O peso que pus no fundo era o `--bg-slab-strong`, que e um TINTE CLARO -- pus mais
claro onde queria menos. Para escurecer a zona da legenda o que falta la e um ESCURA,
nao mais slab: exactamente o que o zip faz com `.scrim-bottom`
(`to top, var(--scrim) 0%, transparent 100%`).

REVERTIDO. O gerador voltou ao estado commitado e os 5 temas e o panel-designs.css foram
regenerados (GEN=0). Nada fica partido, e tambem nada fica "corrigido".

O que esta MEDIDO e o que FALTA:
  MEDIDO  o perfil esta invertido, com numeros, em dois prints diferentes.
  FALTA   por um escuro no fundo -- e o valor certo e o do proprio zip
          (`--cine-scrim`, que eu ja medi: 0.62 a 0.93), nao um que eu invente.

E a contagem: tres tentativas, zero efeito ou pior. O que me safou foi o instrumento
que compara por bytes -- sem ele, a terceira tentativa tinha saido como "corrigido".
