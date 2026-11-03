# A LEGENDA DO YOUTUBE, 1:1 -- o que foi medido, o que mudou, e onde esta' o resto

Data: 2026-11-03 00:2x-01:0x. Dono, verbatim: *"tu da play colega. tu faz tudo. tu nao
vai depender de mim. tu vai voltar quando tiver tudo resolvido e provado que a legenda
tem tudo 1:1"*, e no meio do trabalho: *"falei pra tu nao me fazer ouvir. e eu to
ouvindo"*.

## O instrumento (novo)

`_main/_yt-live-latency.py` -- mede o Sotto contra o PROPRIO player, com o video a
tocar, e responde com numeros que um humano sente:

| metrica | o que e' |
|---|---|
| `latency_ms_*` | para cada mudanca de linhas do player, quanto tempo o Sotto levou a desenhar AQUELAS linhas |
| `agree_pct` | % de amostras em que o ecra do Sotto mostra EXACTAMENTE as linhas do player |
| `display_age_ms_*` | ha' quanto tempo o texto no ecra ja' nao e' o do player |
| `oscillations` | A -> B -> A dentro de 500 ms -- o *"ficando sumindo e aparecendo"* do dono, contado |
| `frames_ahead` / `frames_stale` | quadros nossos com texto que ele ainda nao pintou / ja' largou |

Tres invariantes no instrumento, cada um nascido de um defeito MEDIDO:

1. **SILENCIO**: `muted=true` + `volume=0` re-afirmados a CADA avaliacao. Um
   `v.muted = true` isolado nao bastou -- o dono ouviu o video.
2. **A ABA NAO E' FOCADA**: CDP crua (`127.0.0.1:9222` -> `Runtime.evaluate`), nunca
   `agent-browser tab` (que trouxe a aba para a frente) e nunca `Target.activateTarget`.
3. **SO' PAGINA DO YOUTUBE, E SO' O VIDEO QUE O SOTTO LE**: o `video_id` vem do log do
   proprio Sotto (`YOUTUBE_CAPTION video_id=`). Medido antes disto: com duas abas do
   YouTube abertas o leitor agarrou o outro video e o veredicto saiu todo errado (68
   mudancas do player contra 0 quadros "ausentes" do Sotto -- porque eram videos
   diferentes).

Tambem: `Page.setWebLifecycleState(active)` + `Emulation.setFocusEmulationEnabled`
porque uma aba em segundo plano deixa de PINTAR a legenda (medido: 90 s de
reproducao com `rows=[]` em 219 de 219 amostras -- nao era o Sotto, era o instrumento
a ler uma pagina congelada), e o filtro de geometria de `.caption-window` porque o DOM
guarda um terceiro segmento a sair da caixa (`n_all=3` com `n_inside=2`).

## O que estava errado no produto (medido, nao suposto)

Tudo abaixo foi lido do log vivo e do player ao mesmo tempo:

| # | defeito | evidencia | correcao |
|---|---|---|---|
| D1 | O rect de um filho atravessava LEITURAS (`reuse=`) | quadros nossos `['conseguiu ainda esta entrar. viva, da para']` onde o player mostra `['conseguiu entrar. mas vamos ver, viper', 'ainda esta viva, da para']` -- palavras certas, ordem trocada; e `'ainda esta viva, da para da para'` | o rect vem sempre da leitura DESTA foto (`youtube_captions._painted_items`, `reuse` removido do contrato) |
| D2 | Duas linhas do player agrupadas numa so' nossa | `['da >> o galera. brasil nao pode deixar']` vs `['da galera', '>> o brasil nao pode deixar']` -- o marcador `>>` aparecia no MEIO | `youtube_window.rows_from_items`: um marcador de fala no meio da linha e' uma fronteira de linha |
| D3 | O mesmo filho lido duas vezes virava palavra repetida | `'aguenta, nao [grito] nao ta ta escrito'` vs `'aguenta, nao [grito] ta escrito'` | `rows_from_items`: duplicado EXACTO (texto + rect) sai |
| D4 | A rolagem do player esperava 280 ms | o "rolar a linha velha para fora" caia no ramo de histerese e o ecra mostrava o instante anterior | `_yt_rows_is_player_step`: escrever, rolar e largar o fim passam NO MESMO tick; so' uma mudanca que nao e' um passo dele espera |
| D5 | A leitura esperava 120 ms ociosos em cima de um custo de 62-110 ms | periodo real ~200-230 ms | `INTERVAL_S` 0.12 -> 0.04: o resto do orcamento e' o custo da leitura |

## Numeros (45 s de video a tocar, mesma sessao, `--period 0.12`)

| medicao | antes (D1-D5 por corrigir) | depois |
|---|---|---|
| quadros desenhados | 35 | 96 |
| quadros iguais ao player no instante | 6 | 42 |
| latencia mediana (mudanca -> desenho) | 97 ms | **88 ms** (noutra janela: 65 ms) |
| mudancas do player reproduzidas | 6/53 | 24/71 |

Isto NAO e' 1:1 ainda: a amostragem do instrumento (120 ms) e' mais fina do que o
intervalo entre quadros do player (~600 ms), mas as duas fontes nao sao a mesma foto, e
o `agree_pct` fica entre 7 % e 20 % conforme o trecho do video.

## O defeito que apareceu por cima (EM ABERTO)

Durante as medicoes o caminho da PINTURA parou: `EXTERNAL_CAPTIONS_READ_MS` continua
(62-110 ms por leitura, o laco vivo), `YOUTUBE_TRACK_READY ... cached=True` continua a
cada 31 s, e **nenhum `YOUTUBE_CAPTION` / `EXTERNAL_CAPTION_DRAWN` durante 4 minutos**
com o video a tocar (`YT_FRAME` ultimo as 00:45:59.320, ultima leitura 00:49:53.614).
Ou seja: a arvore de acessibilidade do Chrome deixou de expor os filhos da janela de
legenda, e o Sotto nao mostra nada -- que e' exactamente a queixa *"transcricao ao vivo
nao ta funcionando"*.

Foi medido tambem por fora: uma leitura UIA directa (`_a11y_floor.py`) devolve
`rows=[]` enquanto a CDP le a mesma legenda no DOM na mesma janela de tempo.

Ultimo teste a decorrer para atribuir: se as linhas voltarem sozinhas quando NENHUMA
ferramenta CDP toca na pagina, a causa e' o `Page.setWebLifecycleState` /
`Emulation.setFocusEmulationEnabled` do INSTRUMENTO e o produto esta' inocente; se nao
voltarem, o piso e' do Chrome e o Sotto precisa de outra fonte de leitura.

## Os portoes

`_main/caption-producer-oracle.py`: **8 arms verdes**, com quatro mutacoes que derrubam
a arm de cada regra (`--neg-arm`: 4/4):
`rect-does-not-cross-reads`, `player-step-passes` (executa a funcao real do ficheiro em
5 casos), `rows-are-the-players` (executa `rows_from_items` nos dois defeitos medidos),
mais as arms antigas do produtor unico e do `cap` de 2 linhas.

## A PARAGEM DA PINTURA -- reproduzida, e com nome

`YOUTUBE_PAINT_STALL` (novo, 2026-11-03) diz o que antes nao estava escrito:

```
2026-11-03 00:55:10 YOUTUBE_PAINT_STALL seconds=35.8 why=no-painted-caption
2026-11-03 00:56:05 YOUTUBE_PAINT_STALL seconds=91.3 why=no-painted-caption
```

Reproduz a ~36 s de cada arranque e NAO recupera dentro do processo: a leitura continua
(62-110 ms por leitura, laco vivo), o `YOUTUBE_TRACK_READY ... cached=True` continua a
cada 31 s, e a arvore de acessibilidade deixa de expor os filhos da janela de legenda.
Consequencia no ecra: o ultimo quadro fica CONGELADO (a medicao de 120 s deu
`display_age_ms_median=46470` -- o ecra mostrando texto de 46 s atras, e 27 oscilacoes).

Duas causas possiveis, e o teste que as separa (em curso, sem CDP nenhum durante 3 min):

  * se, com o instrumento CALADO, a pintura continuar viva 3 minutos, a causa e' o
    PROPRIO INSTRUMENTO (`Page.setWebLifecycleState(active)` +
    `Emulation.setFocusEmulationEnabled`) a estragar a acessibilidade da aba -- e entao
    todos os numeros acima foram medidos num estado que o instrumento criou;
  * se parar na mesma, o piso e' do Chrome nessa aba e o Sotto precisa de outra fonte.

**O RESULTADO (00:56:21 -> 00:59:30, sem NENHUM CDP a tocar na pagina):**
`YOUTUBE_PAINT_STALL` 4 registos, **1** `YOUTUBE_CAPTION` (00:56:23, dois segundos depois
do arranque) e nada mais durante 3 minutos, com o video a tocar.

Conclusao: **nao e' o instrumento.** Com a aba do YouTube em SEGUNDO PLANO -- que e' o
estado normal quando ele joga com o video noutra janela -- o Chrome deixa de gerar a
arvore de acessibilidade dessa aba, e o Sotto fica sem fonte: nem pintura, nem relogio.
Quando a aba estava activa (as medicoes de 00:23-00:45), tudo funcionou a 62-110 ms.

O QUE ISSO EXIGE (decisao de arquitectura, nao um remendo):
  * **fonte alternativa** para quando a UIA nao expoe a legenda -- a CDP em
    `127.0.0.1:9222` le a mesma legenda em ~10 ms (e' o que este instrumento usa) e
    e' a unica via medida que nao depende de a aba estar activa; a UIA fica como
    fonte de recurso;
  * ou (pior) pedir ao dono que mantenha a janela do video em foco -- o que contraria
    *"roda ele no background"*.

O que NAO se faz enquanto isto estiver aberto: chamar 1:1 ao produto. A ordem de leitura,
a geometria, a quebra de linha e o "passo do player" estao corrigidos e provados; a
FONTE pode desaparecer debaixo deles.

## CORRECCAO DO RECIBO -- o ecra NAO congelou (medido 2026-11-03 01:0x)

A primeira leitura desta paragem dizia que o ultimo quadro ficava CONGELADO no
ecra (`display_age_ms_median=46 470`). A medicao seguinte desmente a leitura e
mantem o numero: o instrumento le o ultimo quadro que a app DESENHOU, e a app
ja' limpa o overlay 6 s depois da ultima legenda --

    CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s epoch=2 wanted=true

-- logo o que o dono ve durante a paragem e' NADA, nao texto velho. Tentei
acrescentar um clear mais cedo (2,5 s) e a instrumentacao mostrou que ele era
redundante: a decisao disparava (`YOUTUBE_PAINT_BLANK_DECISION fire=True`) e nao
mudava o que ja' estava limpo. Foi removido -- um gate que nao muda o ecra e'
peso morto.

O defeito real, esse, mantem-se e e' o que o `YOUTUBE_PAINT_STALL` nomeia: com a
aba do YouTube em segundo plano o Chrome deixa de expor a legenda na arvore de
acessibilidade, e o Sotto nao tem fonte nenhuma para ler. Texto nenhum aparece
ate' a fonte voltar.
