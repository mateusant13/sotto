# A CURA DO E3/E4, E A PROVA DE QUE A DECISAO ERA MINHA E NAO DO DONO

O dono, verbatim: tu ta simplesmente botando de forma burra alguns designs por cima do
painel e ai fica duas coisa sobrepostas que nao fazem sentido como se fosse um glitch,
em diversos designs. E: por que tem personagens falando em um dos designs replicados?

Eu tinha dito, nos rounds anteriores, que os 11 valores de scrim (0.62-0.72) vem
verbatim dos .zip, logo a decisao seria do dono.

## EU ESTAVA ERRADO, E A PROVA ESTA NO ZIP

O valor vem mesmo do zip: _main/_design-lane/zips/cinematic/src/themes.ts diz
"scrim": "rgba(4,8,16,0.68)". Mas o que o zip FAZ com esse valor nao e o que eu faco.
zips/cinematic/src/index.css:90-98, as tres camadas do zip:

    .scrim-top    { linear-gradient(to bottom, rgba(0,0,0,0.5), rgba(0,0,0,0)); }
    .scrim-bottom { linear-gradient(to top, var(--scrim) 0%, rgba(0,0,0,0) 100%); }
    .vignette     { radial-gradient(125% 95% at 50% 42%, transparent 52%,
                     rgba(0,0,0,0.44) 100%); }

## O QUE ISTO MUDA

1. O scrim do zip NUNCA e plano. Sao DOIS gradientes opostos -- escuro no topo, escuro
   em baixo -- mais uma vinheta nas bordas. O MEIO da fotografia fica LIMPO, e e por
   isso que a demo do zip nao parece um glitch: a fotografia ve-se inteira no centro e
   a zona da legenda e que esta escura.

2. O que EU compus, em todos os 25 temas (gen_cinematic.py:1412), e
   linear-gradient(var(--cine-scrim), var(--cine-scrim)) -- PLANO, em todo o painel.
   O resultado e uma fotografia inteiramente esbatida: nem se ve, nem desaparece. E
   exactamente duas coisas sobrepostas ... como se fosse um glitch.

3. Logo o valor 0.68 estava CERTO o tempo todo. O que estava errado era a FORMA -- e a
   forma e minha. A decisao nao era do dono: era minha, e eu tinha-a empurrado para
   ele. Foi o custo de nao ter medido a FORMA antes de a declarar decisao dele.

## A CURA, EXACTA

No gerador, a composicao do .panel passa a ser as tres camadas do zip, na mesma ordem
e com os mesmos stops:

    background-image:
      linear-gradient(to bottom, rgba(0,0,0,0.5), rgba(0,0,0,0)),     -- scrim-top
      linear-gradient(to top, var(--cine-scrim), rgba(0,0,0,0)),     -- scrim-bottom
      radial-gradient(125% 95% at 50% 42%, transparent 52%, rgba(0,0,0,0.44) 100%),
      url(backdrops/X.jpg);
    background-size: cover, cover, cover, cover;   -- um valor por camada

Quatro camadas, quatro valores em background-size. E o censo passa a medir o que
importa: nao o alpha de um scrim plano, mas a luminancia da COMPOSITA na ZONA DA
LEGENDA (o terco de baixo), que e onde o texto tem de vencer.

## MEDIDO E FALTA

MEDIDO: o zip tem tres camadas (index.css:90-98); o valor 0.68 e do zip (themes.ts);
a minha composicao e plana (gen_cinematic.py:1412); 11 temas com scrim 0.62-0.72.
FALTA: mudar o gerador, regenerar, e refazer o censo para medir a composita na zona
da legenda em vez do alpha do scrim plano. Feito isso, E3/E4 fecham com numero.
