# A CURA DO E3/E4 EXECUTADA: o scrim plano virou as tres camadas do zip

LANE D. Commit da cura: 4177150 (mais 91d3f98, o braco negativo depois da medicao).
Este recibo e o numero de cada um dos 25 temas, os stops copiados do zip, e o que ficou
por provar. O prompt do dono e o criterio: _main/aceitacao-dono.md, linhas E3/E4.

    "tu ta simplesmente botando de forma burra alguns designs por cima do painel e ai
     fica duas coisa sobrepostas que nao fazem sentido como se fosse um glitch, em
     diversos designs"   (E4)
    "por que tem personagens falando em um dos designs replicados?"                 (E3)

## OS STOPS, COPIADOS DO ZIP -- verbatim

_main/_design-lane/zips/cinematic/src/index.css:90-98:

    .scrim-top    { background: linear-gradient(to bottom, rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0)); }
    .scrim-bottom { background: linear-gradient(to top, var(--scrim, rgba(4, 7, 14, 0.72)) 0%, rgba(0, 0, 0, 0) 100%); }
    .vignette     { background: radial-gradient(125% 95% at 50% 42%, transparent 52%, rgba(0, 0, 0, 0.44) 100%); }

e a ordem em que o zip as poe sobre a fotografia (components/Backdrop.tsx:35-37):
vinheta, scrim-top, scrim-bottom -- a fotografia e a BASE. O que o gerador passou a
emitir (medido em app/panel/themes/cinematic.css:1995-2001, cine-last-reel):

    background-image:
      linear-gradient(to bottom, rgba(0,0,0,0.5), rgba(0,0,0,0)),                   <- scrim-top
      linear-gradient(to top, var(--cine-scrim), rgba(0,0,0,0)),                    <- scrim-bottom
      radial-gradient(125% 95% at 50% 42%, transparent 52%, rgba(0,0,0,0.44) 100%), <- vinheta
      url(backdrops/last-reel.jpg);                                                 <- a fotografia, POR ULTIMO
    background-size: cover, cover, cover, cover;                                    <- um valor por camada
    background-position: center, center, center, center;

Os stops sao os do zip, na mesma ordem. A unica diferenca e var(--cine-scrim) no lugar
de var(--scrim): o nome do token no nosso painel, e o VALOR vem do mesmo sitio --
zips/cinematic/src/themes.ts diz "scrim": "rgba(4,8,16,0.68)" e gen_cinematic.py:577
mapeia '--cine-scrim': v['--scrim']. O 0.68 estava certo o tempo todo; o que estava
errado era a FORMA (e a forma era minha).

## ONDE ENTROU A CURA, e porque nos DOIS sitios

1. gen_cinematic.py theme_css() (~linha 810, os 10 temas base do zip cinematic): o bloco
   do backdrop passou a compor as tres camadas + a fotografia. Antes:
   linear-gradient(var(--cine-scrim), var(--cine-scrim)), url(...) + cover, cover.
2. gen_cinematic.py main(), o default dos extras (~linha 1432): a MESMA composicao, MAS
   so emitida quando o extra NAO traz css proprio com .panel e foto. Medido: os 15 extras
   (cine_extra_c1 / cine_extra_c2) trazem todos css proprio com .panel+url, e essa regra
   vem DEPOIS e GANHA. Emitir a default para eles criaria DUAS regras .panel por tema --
   o defeito do receipt-20261015-duas-imagens-no-painel.md
   ("UMA regra .panel por tema, com UMA background-image"). Confirmado pelo Lead, que
   mudou so o sitio 1 e mediu 15 temas com as camadas do zip e 12 planos: a regra
   duplicada nao cura nada.
   Nos bytes: regras .panel de temas cine- 92 -> 77 (as 15 defaults duplicadas
   desapareceram); fotografia com scrim plano 27 -> 2 (esses 2 sao as PLACAS
   .captions__body de duas cenas de cinematic-1, cine-fieldnotes:3467 e
   cine-dustlight:3803 -- o prato claro proprio do design, nao a fotografia).

## O QUE NAO SE TOCOU: cine_extra_c1.py e cine_extra_c2.py (medido, nao preguica)

O prompt da lane dizia que os tres geradores poem o scrim plano. MEDIDO, nao e verdade
para os dois extras: nenhum dos dois poe scrim plano. Cada um poe o overlay PROPRIO do
seu design, do SEU zip:

    cine_extra_c1.py:294-301   background-image: <wallOverlay da cena>, url(foto)
                              background-size: cover, cover                        (2 camadas)
    cine_extra_c2.py:319-327   background-image: <overlay_1>, <overlay_2>, url(foto)
                              background-size: cover, cover, cover                 (3 camadas)

Substituir o overlay de um zip pelas camadas de outro zip seria por o design do zip A
por cima do design do zip B -- exactamente o contrario da fidelidade que o dono pediu
(E1: "pq tu copiou as coisas das demos q sao sem sentido?"; E2: "imita mais os .zip").
Os dois ja passam o gate novo (tabela abaixo), com os seus proprios gradientes.

## ANTES E DEPOIS, os 25 temas

O censo antigo (alpha do scrim plano) deu, ANTES, medido por mim as 01:44 no estado
entao em disco: 25 temas, 14 ok, 11 GAP (VERDICT: FAIL, rc=1). O censo NOVO (a luminancia
da composita na zona da legenda) deu, correndo o MESMO codigo contra os bytes de antes
(git show 8b15adf:...cinematic.css) e contra os de agora:

    ANTES (codigo novo, bytes velhos): 15/25 -- 10 GAP, os 10 que pintavam scrim plano
    DEPOIS (codigo novo, bytes novos): 25/25 -- 0 GAP, rc=0

A diferenca entre o 11 do censo antigo e o 10 do novo e EXACTAMENTE cine-linen, e vale
regista-la: o censo antigo lia a PRIMEIRA regra .panel com url() de cada tema, que nos
extras e a default do gerador -- uma regra que NUNCA pinta, porque o css proprio do extra
vem depois e ganha. cine-linen pintava sempre o overlay proprio (0.72 no stop de baixo,
rgba(20,16,11,.72)), e o censo antigo acusava-o de GAP por uma regra morta. O censo novo
le a regra PINTADA: a ULTIMA .panel do tema que carrega a fotografia.

Tabela (numeros do censo novo, o mesmo codigo dos dois lados; mid_share = a fracao da
fotografia que sobrevive no MEIO do painel):

| tema | antes | depois | o que mudou |
|---|---|---|---|
| cine-analog | ok, mid_share 0.62 | ok, 0.62 | nada -- overlay propio |
| cine-blue-hour | ok, 0.71 | ok, 0.71 | nada |
| cine-cafe | ok, 0.68 | ok, 0.68 | nada |
| cine-cellar | ok, 0.75 | ok, 0.75 | nada |
| cine-dustlight | ok, 0.79 | ok, 0.79 | nada |
| cine-ember | ok, 0.74 | ok, 0.74 | nada |
| cine-fieldnotes | ok, 0.73 | ok, 0.73 | nada |
| cine-last-reel | GAP (plano) | ok, 0.38 -> 0.51 | 3 camadas do zip |
| cine-last-train | ok, 0.73 | ok, 0.73 | nada |
| cine-linen | ok, 0.87 | ok, 0.87 | nada -- era falso GAP do censo antigo |
| cine-midnight-rain | GAP (plano) | ok, 0.47 -> 0.53 | 3 camadas do zip |
| cine-motel-glow | GAP (plano) | ok, 0.38 -> 0.51 | 3 camadas do zip |
| cine-north-fog | GAP (plano) | ok, 0.36 -> 0.50 | 3 camadas do zip |
| cine-paper-moon | GAP (plano) | ok, 0.43 -> 0.53 | 3 camadas do zip |
| cine-quiet-streets | GAP (plano) | ok, 0.51 -> 0.54 | 3 camadas do zip |
| cine-rainglass | ok, 0.72 | ok, 0.72 | nada |
| cine-rainline | ok, 0.86 | ok, 0.86 | nada |
| cine-reading-hour | ok, 1.04 | ok, 1.04 | nada |
| cine-rooftop | ok, 0.78 | ok, 0.78 | nada |
| cine-shelves | ok, 0.71 | ok, 0.71 | nada |
| cine-study-light | GAP (plano) | ok, 0.34 -> 0.50 | 3 camadas do zip |
| cine-tideline | ok, 0.72 | ok, 0.72 | nada |
| cine-tideline-body | GAP (plano) | ok, 0.53 -> 0.55 | 3 camadas do zip |
| cine-velvet-dusk | GAP (plano) | ok, 0.47 -> 0.54 | 3 camadas do zip |
| cine-warm-hour | GAP (plano) | ok, 0.54 -> 0.55 | 3 camadas do zip |

O scrim plano deixava 0.28-0.38 da fotografia no meio (e 0.32 no 0.68 da regra do zip);
as tres camadas deixam 0.50-0.55 nos dez temas curados -- a fotografia ve-se no meio,
que e o desenho do zip.

A ZONA DA LEGENDA (o terco de baixo, onde o texto tem de vencer), contraste da tinta
0xF1,0xF5,0xF9 contra a composita, no ponto mais fraco da zona (y=600 de 900) e no centro
(y=750): os dez curados ficaram entre 12.11 e 18.45 de contraste no ponto mais fraco
(antes, com o scrim plano, o valor era o mesmo em toda a banda porque a camada era plana
-- era esse o defeito: nem legenda nem fotografia). Os 15 extras: 6.27 a 16.59 no ponto
mais fraco. Nenhum tema abaixo do soalho CONTRAST_FLOOR = 3.0.

## O CENSO, REESCRITO -- e porque a metrica mudou

O censo media o ALPHA de --cine-scrim. Depois da cura esse valor ja nao e a metrica: nao
ha scrim plano nenhum na folha. O censo novo (_main/photo-scrim-census.py) le a regra
PINTADA e mede:

1. FORMA (E4): a composicao tem de ser GRADIENTES sobre a fotografia -- nenhuma camada
   plana (uma camada que pinta a mesma cor em todo o painel e o scrim plano, medida em
   21 pontos do painel), a fotografia por ULTIMO, e background-size com UM valor por
   camada (background-position tambem, quando declarado).
2. ZONA DA LEGENDA (E3): a LUMINANCIA DA COMPOSITA no terco de baixo, no ponto mais
   fraco e no centro, com o contraste da tinta da legenda gateado a 3.0.
3. O MEIO, medido e reportado por tema: a fracao da fotografia que sobrevive la.

O avaliador le os MESMOS gradientes que o browser pintaria: linear-gradient por direcao
(sem direcao explicita = to bottom) e radial-gradient por geometria de elipse (posicao ao
longo do raio = distancia a borda da elipse naquela direcao). A fotografia e cortada como
background-size: cover a mostra num painel de 380x900 (app/panel/surface.js: "380x900
panel"; panel.css:150-182: .panel preenche a janela). Falha fechada: uma camada que o
censo nao consegue ler e GAP, nao passe.

### Os QUATRO bracos negativos (o censo tem de poder dizer NAO)

Corre com py -3 _main/photo-scrim-census.py --neg-arm. Cada mutacao numa COPIA num
TemporaryDirectory, e cada uma tem de por VERMELHO o tema que toca, e so esse:

    M1 flat wash     a regra pintada volta ao scrim plano (o defeito do dono)  -> RED, cine-analog
    M2 raw photo     todos os gradientes tirados, fotografia crua               -> RED, cine-analog
    M3 zeroed scrim  --cine-scrim do tema a 0.0 (o braco do censo antigo).      -> RED, cine-last-reel
                     A vitima e escolhida pela REGRA, nao pela ordem: so um tema
                     cuja regra le var(--cine-scrim) pode ser mutado por zero.
                     MEDIDO: com a vitima por ordem (cine-analog, cujo overlay
                     propio usa literais) a mutacao era INERTE -- o braco nao
                     dizia NAO, que e o defeito que o Lead apanhou na bateria
                     (139/140) e que me pediu para arranjar.
    M4 bright photo  uma fotografia de 238,238,238 sob a MESMA composicao.       -> RED, cine-ember
                     A vitima e escolhida por medicao: o tema cuja zona da
                     legenda aguenta mais luz. MEDIDO nessa fotografia clara, o
                     ponto mais fraco da zona desce a 1.78 (cine-ember, cujo
                     overlay propio e um pool de luz quente) e 1.99 (cine-linen).

    NEG-ARM copy untouched: 0 bad (tem de igualar o vivo)
    VERDICT: PASS -- the census can say NO

## VERIFICACAO OBRIGATORIA -- os numeros

    a. ANTES:   py -3 _main/photo-scrim-census.py -> 25 temas, 14 ok, 11 GAP, rc=1
                (medido 01:44 no estado entao em disco; censo antigo, metrica do alpha)
    b. DEPOIS:  py -3 _main/photo-scrim-census.py -> 25/25, rc=0 (tabela acima)
    c. A metrica mudou (alpha plano -> luminancia da composita na zona da legenda);
                mantem as DUAS cores: 4 mutacoes, todas RED, copia intacta verde.
    d. node _main/instruments-battery.mjs -> 140/140 instrument(s) rc=0, failed=0,
                launches=0 (log: I:/cc-tmp/battery-solo.txt).
                MEDIDO TAMBEM, e registado porque ensina: uma corrida da bateria
                COM OUTRA A CORRER AO MESMO TEMPO deu 138/140 -- zipc designs neg
                (rc=1) e surface loop page neg (rc=2), ambos VERDE quando corridos
                sos. Os dois oraculos trabalham em copias sob $TMPDIR; duas
                baterias em paralelo escrevem na mesma pasta. NAO e defeito do
                produto: e o custo de correr o gate duas vezes ao mesmo tempo.
    e. gen-themes-repro-oracle  -> VERDICT PASS (7 ficheiros, 0 diferentes)
       gen-cinematic-repro-oracle -> VERDICT PASS (cinematic.css 351 160 B
                c1cc8fecf90f1704 == fresco; themes.js 9 846 B 589aa22b39db67a8 == fresco)
       -- prova de que o CSS gerado foi REGENERADO e nao editado a mao.
       Mais: theme-lightness-census --gate GREEN (nenhum tema claro), cine-themes-oracle
       PASS, cinematic-designs-oracle PASS, assert-themes.js PASS, generator rc=0 com
       SELF-CHECK ok.

## O QUE FICOU POR PROVAR

  * NAO MEDIDO -- o OLHAR. E2 (comparar com os prints dos .zip) e so teu: este recibo
    mede a luminancia e a estrutura, nao a beleza. O que a medicao diz e que a fotografia
    ficou mais exposta no meio (0.32 -> 0.50-0.55) e que a zona da legenda escureceu,
    que e o desenho do zip.
  * NAO MEDIDO -- o SCROLL e o PAINEL A CRESCER. O censo trata o painel como a caixa
    380x900. O painel move-se e cresce com o historico; a zona da legenda e sempre o
    terco de baixo da caixa, que foi o que medi.
  * NAO MEDIDO -- paper-moon. E o unico tema de chapa clara invertida
    (gen_cinematic.py:154-165, NO_LIGHT_SLAB) e a sua tinta e clara sobre tudo; a
    composita que medi usa a tinta 0xF1,0xF5,0xF9 para todos os temas. O contraste deu
    13.42-13.90, com folga, mas a tinta propria dele e #EDEFF2, nao a minha.
  * NAO MEDIDO -- o --cine-scrim dos extras. Os 15 extras declaram o token no bloco (a
    default do gerador usava-o), mas as regras que pintam usam literais; o token la
    continua, nao lido por nenhuma regra do tema. Nao e defeito desta cura e nao o
    inventei, mas convem dizer que esta la.

## FICHEIROS (working tree; o Lead commitou por nome -- 4177150 e 91d3f98)

    _main/_design-lane/gen_cinematic.py      92 726 B  sha256 ddf9f9feae425f46
    _main/photo-scrim-census.py              33 216 B  sha256 16abc8928f20212d
    app/panel/themes/cinematic.css          351 160 B  sha256 c1cc8fecf90f1704  (regenerado)
    app/panel/themes/themes.js                9 846 B  sha256 589aa22b39db67a8  (regenerado)

NAO toquei em cine_extra_c1.py, cine_extra_c2.py, gen_zipc.py, gen_themes.py,
app/shadowplay/ nem em nenhum CSS a mao.
