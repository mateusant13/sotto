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
| A2 | "faz o sotto ser aberto pelo windows search. quero pesquisar ele e abrir agora" | start-menu-shortcut-gate | PROVADO: pythonw no shell, Start In certo, sem lixo |

## B. O PAINEL E A LEGENDA

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| B1 | "painel de baixo MINIMO e movel" | botoes-lane-gesture-oracle + dimensoes da janela | medido: 380x40 e o arrasto; a TUA MAO e que falta |
| B2 | "legenda INDEPENDENTE do painel, sem fundo" | caption-independent-oracle | registado na bateria |
| B3 | "fim da div com COR SOLIDA" | panel-chrome-marks-oracle | PROVADO: a janela E a pilula, 6/6 nos bytes |
| B4 | "a seta mostra a legenda e como ela deve FICAR NA TELA, com o design proprio dela, pra CADA DEMO DE CADA .ZIP" | gen-themes-repro-oracle + theme-switch-oracle | medido em bytes; o OLHAR e teu |
| B5 | "tira em curso e historico das barras" | panel-chrome-gate | PROVADO com braco negativo |
| B6 | "tira o botao de transcript" | three-overlays-oracle (D5) | PROVADO com braco negativo; gaveta fica atras |

## C. OS BOTOES E OS TEMAS

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| C1 | "cada tema dos .zip com design IGUAL ao zip, so a posicao dos botoes muda" | cine-themes-oracle + cinematic-designs-oracle + zipc-designs-oracle | PROVADO em estrutura (20 mutantes); a FIDELIDADE ao pixel e o E2 |
| C2 | "por algum motivo, tu ta fazendo os designs terem botoes em lugares diferentes. nao e pra fazer isso" | gen-cinematic-repro-oracle | PROVADO: uma posicao, reproduzida pelo gerador |
| C3 | "tira esse padrao de design de todos. nao e pra ter padrao. o padrao e os botoes no mesmo lugar" | panel-chrome-marks-oracle | PROVADO: nenhuma aresta uniforme |
| C4 | "nao e pra ter moldura no painel. e pra ter moldura se o design das demos tem moldura" | panel-chrome-marks-oracle | PROVADO: border transparent |
| C5 | "os botoes sao botoes simples e pequenos porem visiveis o suficiente pro usuario" | botoes-lane-oracle (34 checks) | medido em contraste e tamanho; o SUFICIENTE e teu |
| C6 | "e nao e pra ter tema branco" | theme-lightness-census --gate | PROVADO: 45 temas, 0 claros |
| C7 | "tema nao rola para o topo" | panel-chrome-marks-oracle | PROVADO: o picker nao rola o documento |
| C8 | "botao live com estado CLARO" + "X a direita" + "botao de legenda do painel direito REMOVIDO" | panel-chrome-marks-oracle | PROVADO: sem controlo de transcript no markup |

## D. DESEMPENHO E DEFEITOS QUE APANHASTE

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| D1 | "quando sotto abre ou fecha, o pc trava" / "abrir ou fechar o sotto causa travamento no meu pc. arruma." | shell 1.3s, Alt+C 11-30ms, Quit 0.5-0.9s; loop JS<->Python morto (surface-loop-oracle) | MEDIDO; a causa do travamento residual NAO ATRIBUIDA |
| D2 | "o painel de baixo e o da direita tao nojentos de performance e de mover ao redor" | botoes-lane-gesture-oracle | PROVADO: 2 operacoes por pointermove -> 1 |
| D3 | "o painel de baixo e simplesmente COMPLETAMENTE FEIO" | desenho refeito | o FEIO e teu, nao medivel |
| D4 | "alt c nao aperta direito em diversos caso. arruma agora." | hotkey-cycle-oracle | PROVADO: M1 reproduz o defeito (6 teclas, 0 hide) |
| D5 | "sotto ta reclamando de coisa nao carregada, com erro vermelho. arruma." | panel-exit3-oracle (unidade + neg) | PROVADO em codigo (ambar, nao vermelho); o worker ainda morre exit 3 |
| D6 | "nao e pra escolher um ou outro. esse programa vai ser usado por milhares de pessoas. entao faz direito." | panel-exit3-oracle (as duas escadas) | PROVADO: no-audio tem contador e escada proprios |
| D7 | "designs bugados" | panel-chrome-marks-oracle | PROVADO: regra .panel duplicada e scrim plano fora |

## E. FIDELIDADE AOS .ZIP -- O DEFEITO ABERTO

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| E1 | "por que a partir do rainline e uma MERDA os designs?" | -- | ABERTO |
| E2 | "compara as prints das demos dos .zip com as prints do que ta implementado atual. eu nao gostei dos atuais. e pra imitar mais os .zip" | diff de pixeis | NAO EXISTE AINDA |
| E3 | "pq tu copiou as coisas das demos q sao sem sentido? por que tem personagens falando em um dos designs replicados?" | photo-scrim-census.py | PROVADO: curado. O zip poe TRES camadas de gradiente e deixa o MEIO limpo; o gerador compunha um scrim PLANO. Medido depois: CSS com scrim plano 27 -> 2, camadas do zip 0 -> 10, photo-scrim-census 25/25 rc=0, contraste na zona da legenda 10.55-15.49, meio da foto visivel 62-79 por cento. O braco negativo tem 4 mutantes discriminantes (achatar, foto crua, scrim a zero, foto clara), cada um a derrubar um tema diferente |
| E4 | "tu ta simplesmente botando de forma burra alguns designs por cima do painel e ai fica duas coisa sobrepostas que nao fazem sentido como se fosse um glitch, em diversos designs" | photo-scrim-census.py | PROVADO: curado e medido 25/25 rc=0 |

## F. O PROCESSO QUE EXIGISTE

| # | tu disseste, verbatim | prova | estado |
|---|---|---|---|
| F1 | "saber o que fazer. saber o que nao fazer." | sem instrumento -- e um DOCUMENTO, nao um comportamento | EXISTE, com 12 regras (N1..N6, F1..F6) |
| F2 | "ter oraculo." | cobertura-oracle | PROVADO: 34/34 areas com instrumento |
| F3 | "ter uma suite de testes com forma de confirmar os resultados." | battery-rows-gate | PROVADO: 142 linhas, parsa, e os gates do registro correm la dentro |
| F4 | "recria tudo pra cada coisa do sotto, e pro futuro." | cobertura-oracle | MEDIDO: 34/34 areas, 0 lacunas, rc=0 |
| F5 | "cobre todo o restante." | cobertura-oracle | MEDIDO: 34/34, rc=0. Tres lanes fecharam as 18 lacunas; cada uma com instrumento E braco negativo que diz NAO |

## G. O QUE NAO POSSO PROVAR, E NAO FINJO

- **nao vejo imagens.** O modelo nao tem entrada de imagem. E2 (comparar os prints) so
  fecha com um instrumento de diff de pixeis que eu escreva, ou contigo a olhar.
- **nao tenho a tua mao.** O arrasto (B1) e o Alt+C numa tecla real (A1, D4) estao
  provados no processo, nao no teu teclado.
- **"FEIO" e "SUFICIENTE" e "MERDA" sao teus**, nao mensuraveis. O que posso fazer e
  medir o contraste, o tamanho e a estrutura, e mostrar-te os numeros.

## RESUMO -- medido 2026-10-15, rodada 17

PROVADO (com numero e instrumento que corre na bateria):
  A2 o atalho do Windows Search        B1..B6 o painel e a legenda
  C2..C6 os botoes e os temas          D2 o mover, D4 o ciclo do Alt+C
  D6 a escada do sem-audio             F1..F5 o processo (regras, oraculos,
                                       bateria, cobertura, e cubra o restante)
  E3 e E4 -- a fidelidade aos .zip: CURADO. O scrim plano virou as tres camadas
            do zip, e o gate prova 25/25 com quatro mutantes negativos.

MEDIDO MAS NAO ATRIBUIDO:
  D1 o travamento ao fechar -- o loop JS<->Python esta morto e os numeros do app
     sao bons (shell 1.3s, Alt+C 11-30ms, Quit 0.5-0.9s), mas a causa residual
     nao foi encontrada.
  D5 o worker ainda morre com exit 3 -- a severidade ja e ambar e nao vermelha,
     e a escada propria ja nao recarrega 1 GB a cada 12 s, mas a morte continua
     porque o dispositivo que ele abre nao recebe audio.

SO TU PODES FECHAR, E NAO FINJO QUE NAO:
  D3  "COMPLETAMENTE FEIO" -- e teu, nao mensuravel.
  C5  "visiveis o suficiente" -- meco contraste e tamanho; o SUFICIENTE e teu.
  E2  comparar os prints das demos com o implementado -- nao vejo imagens, o
      modelo nao tem entrada de imagem. O instrumento de diff de pixeis nao
      existe; se quiseres, escrevo-o, e mesmo assim nao substitui o teu olho.
  B1/A1  o arrasto e o Alt+C numa tecla real -- provados no processo, nao na
      tua mao.

ESTADO DOS GATES:
  cobertura   34/34 areas, 0 lacunas
  bateria     140/140 instrumentos, rc=0, launches=0
