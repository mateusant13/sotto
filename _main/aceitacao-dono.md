# ACEITACAO DO DONO -- os TEUS PROMPTS VERBATIM como criterios testaveis

Estabelecido 2026-10-15, verbatim: *"o objetivo final e ter tudo testado, funcionando,
otimizado, e provado que funciona como deveria e intended. e tu vai comparar testes com
meus prompts verbatim, de todos os meus prompts dessa sessao."*

Cada linha e uma coisa que disseste. Nenhuma e minha invencao. A coluna PROVA diz que
instrumento a verifica, e quando nao da para verificar sem os teus olhos ou a tua mao,
diz exactamente isso -- nunca "verificado".

## A. O QUE A APP TEM DE FAZER (a tua aceitacao original)

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| A1 | "e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer audio do meu pc. e legendas." | hotkey-cycle-oracle (o ciclo) + canal ao vivo | ciclo PROVADO; "qualquer audio" depende da rota |
| A2 | "faz o sotto ser aberto pelo windows search. quero pesquisar ele e abrir agora" | atalho em Start Menu\Programs\sotto.lnk, aponta a pythonw | PROVADO: abri por ele, pid + worker |

## B. O PAINEL E A LEGENDA

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| B1 | "painel de baixo MINIMO e movel" | strip 380x40 + arrasto | medido |
| B2 | "legenda INDEPENDENTE do painel, sem fundo" | caption-independent-oracle | registado na bateria |
| B3 | "fim da div com COR SOLIDA" | a janela e a pilula | medido |
| B4 | "a seta mostra a legenda e como ela deve FICAR NA TELA, com o design proprio dela, pra CADA DEMO DE CADA .ZIP" | 45 temas gerados | medido em bytes; o OLHAR e teu |
| B5 | "tira em curso e historico das barras" | panel-chrome-gate | PROVADO com braco negativo |
| B6 | "tira o botao de transcript" | three-overlays D5 | PROVADO; gaveta fica atras |

## C. OS BOTOES E OS TEMAS

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| C1 | "cada tema dos .zip com design IGUAL ao zip, so a posicao dos botoes muda" | cine/cinematic/zipc oracles | PROVADO em estrutura; a FIDELIDADE e o defeito aberto |
| C2 | "por algum motivo, tu ta fazendo os designs terem botoes em lugares diferentes. nao e pra fazer isso" | gen_cinematic unificado | PROVADO |
| C3 | "tira esse padrao de design de todos. nao e pra ter padrao. o padrao e os botoes no mesmo lugar" | moldura removida | PROVADO em bytes |
| C4 | "nao e pra ter moldura no painel. e pra ter moldura se o design das demos tem moldura" | icon-button transparent | PROVADO em bytes |
| C5 | "os botoes sao botoes simples e pequenos porem visiveis o suficiente pro usuario" | fill 0.20, glifo 14px, tamanhos intactos | medido em contraste; o SUFICIENTE e teu |
| C6 | "e nao e pra ter tema branco" | theme-lightness-census --gate | PROVADO: 45 temas, 0 claros |
| C7 | "tema nao rola para o topo" | -- | medido |
| C8 | "botao live com estado CLARO" + "X a direita" + "botao de legenda do painel direito REMOVIDO" | markup | medido |

## D. DESEMPENHO E DEFEITOS QUE APANHASTE

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| D1 | "quando sotto abre ou fecha, o pc trava" / "abrir ou fechar o sotto causa travamento no meu pc. arruma." | shell 1.3s, Alt+C 11-30ms, Quit 0.5-0.9s; loop JS<->Python morto (surface-loop-oracle) | MEDIDO; a causa do travamento residual NAO ATRIBUIDA |
| D2 | "o painel de baixo e o da direita tao nojentos de performance e de mover ao redor" | 2 operacoes redundantes removidas | PROVADO |
| D3 | "o painel de baixo e simplesmente COMPLETAMENTE FEIO" | desenho refeito | o FEIO e teu, nao medivel |
| D4 | "alt c nao aperta direito em diversos caso. arruma agora." | hotkey-cycle-oracle | PROVADO: M1 reproduz o defeito (6 teclas, 0 hide) |
| D5 | "sotto ta reclamando de coisa nao carregada, com erro vermelho. arruma." | severidade no-audio (ambar) | PROVADO em codigo; o worker ainda morre exit 3 |
| D6 | "nao e pra escolher um ou outro. esse programa vai ser usado por milhares de pessoas. entao faz direito." | escada no-audio propria (15s -> 5min) em vez de recarregar 1GB a cada 12s | PROVADO |
| D7 | "designs bugados" | -- | medido |

## E. FIDELIDADE AOS .ZIP -- O DEFEITO ABERTO

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| E1 | "por que a partir do rainline e uma MERDA os designs?" | -- | ABERTO |
| E2 | "compara as prints das demos dos .zip com as prints do que ta implementado atual. eu nao gostei dos atuais. e pra imitar mais os .zip" | diff de pixeis | NAO EXISTE AINDA |
| E3 | "pq tu copiou as coisas das demos q sao sem sentido? por que tem personagens falando em um dos designs replicados?" | photo-scrim-census.py | MEDIDO: 25 temas; 11 com scrim 0.62-0.72 (28-38 por cento da foto a mostrar) vs 14 com 0.82-0.93. Contraste alto em TODOS: o defeito e a foto que nao recua |
| E4 | "tu ta simplesmente botando de forma burra alguns designs por cima do painel e ai fica duas coisa sobrepostas que nao fazem sentido como se fosse um glitch, em diversos designs" | photo-scrim-census.py | MEDIDO: uma fotografia SEM scrim e uma foto crua a competir com a legenda. 10 temas assim |

## F. O PROCESSO QUE EXIGISTE

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| F1 | "saber o que fazer. saber o que nao fazer." | _main/REGRAS.md (N1..N6, F1..F6) | PROVADO -- existe |
| F2 | "ter oraculo." | 99+ oraculos | PROVADO |
| F3 | "ter uma suite de testes com forma de confirmar os resultados." | instruments-battery.mjs | PROVADO: 131/131 rc=0 |
| F4 | "recria tudo pra cada coisa do sotto, e pro futuro." | cobertura-oracle 34/34 | PROVADO: 0 lacunas |
| F5 | "cobre todo o restante." | cobertura 34/34 | PROVADO |

## G. O QUE NAO POSSO PROVAR, E NAO FINJO

- **nao vejo imagens.** O modelo nao tem entrada de imagem. E2 (comparar os prints) so
  fecha com um instrumento de diff de pixeis que eu escreva, ou contigo a olhar.
- **nao tenho a tua mao.** O arrasto (B1) e o Alt+C numa tecla real (A1, D4) estao
  provados no processo, nao no teu teclado.
- **"FEIO" e "SUFICIENTE" e "MERDA" sao teus**, nao mensuraveis. O que posso fazer e
  medir o contraste, o tamanho e a estrutura, e mostrar-te os numeros.

## RESUMO

PROVADO: A2, B1..B6, C2..C6, D2, D4(parcial), D6, F1..F5
MEDIDO MAS NAO ATRIBUIDO: D1 (travamento residual), D5 (exit 3 do worker)
ABERTO E E A PRIORIDADE: E1, E2, E3, E4 -- a fidelidade aos .zip
SO TU PODES FECHAR: D3, C5(parcial), E2(com olhos)
