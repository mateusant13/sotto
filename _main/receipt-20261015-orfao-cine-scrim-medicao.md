# ORFAOS --cine-scrim: 13 TEMAS DECLARAM E NAO LEEM (medido no loop da lane D)

cinematic.css, medido 2026-10-15 sobre os bytes shipped:
  declara --cine-scrim : 25 temas
  le var(--cine-scrim) : 12 temas
  ORFAOS             : 13 temas (cafe, rainglass, tideline, analog, shelves,
                        rooftop, ember, rainline, cellar, linen, reading-hour,
                        last-train, blue-hour)

PORQUE: os 13 sao dos extras (cine_extra_c1/c2), que componem o overlay PROPRIO com
literias rgba do proprio tema -- por ex. cafe: linear-gradient(180deg,
rgba(28,17,10,0.62) 0%, rgba(20,13,9,0.34) 46%, ...) -- e nunca leem a variavel. A
variavel e declarada pelo gen_cinematic no bloco de todos os 25 temas.

DECISAO PARA OS ROUNDS AUTOMATICOS ( nao tomada ainda): para os 13, ou a variavel
ganha um leitor real e util, ou a declaracao sai em cada um. O que NAO pode ficar: um
token declarado e morto, que e orfao que os oraculos C1/C existem para apanhar.

NOTA: os oraculos cine-themes/cinematic-designs dao VERDE hoje, logo a sua tabela de
--cine-scrim como "lido" deve vir de outro sitio (p.ex. contado via --scrim ou via bloco
compartilhado) -- e isso e uma questao em aberto a verificar nos rounds.
