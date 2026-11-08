# RECIBO — a legenda que o dono lê: a língua, a face, a roda (2026-11-08)

Tudo aqui foi executado nesta árvore, hoje. Onde há número, o comando que o produziu está ao lado.
O que não foi medido diz `UNMEASURED` — nenhuma linha deste recibo é inferência disfarçada.

## 1. As ordens, verbatim, e onde cada uma aterrou

| # | o que ele disse | onde aterrou | instrumento | veredicto |
|---|---|---|---|---|
| 1 | *"eu ja falei pra NAO traduzir entre pt br ingles e espanhol entre si. mas pra traduzir o resto pra linguagem que eu escolhi pro sotto. que no caso é pt br. entao eu to vendo um anime agora, e a legenda ta aparecendo japones."* | `app/webview/caption_settings.py` (novo) + `_target_langs` | `_main/youtube-captions-oracle.py` (66 arms, `--neg-arm` 18/18) | `PASS` |
| 2 | *"e faz o botao de config pra eu escolher pra qual lingua traduzir."* | seletor `Traduzir para:` no menu do painel (`panel.js`/`panel.html`), `setTranslationTarget` → shell → `_main/caption-settings.json` | `_main/panel-history-wheel-probe.mjs` arm `M` | `M GREEN` (29 opções, `fr` postado uma vez) |
| 3 | *"voce fez todas as legendas iguais em todos os temas"* / *"falta varios temas q nao foram modificados"* | `app/panel/panel-unified.css` (a regra de vitória deixa de fixar a face) | `_main/panel-history-clip-probe.mjs` (45 desenhos, 6 arms + `--neg-arm`) e `_main/theme-caption-identity-oracle.py` (5 arms + 4 mutantes) | `28 faces distintas`, `--neg-arm` cai para **1** |
| 4 | *"eu nao consigo usar meu scroll pra scrollar as legendas no historico."* | `panel.js` (`historyScroller`/`wireHistoryWheel`/`pinHistoryToBottom`) + `panel.css` | `_main/panel-history-wheel-probe.mjs` (W2/W2b, roda real do Chromium) | `PROBE GREEN`, `--neg-arm` muda **uma** linha e derruba W2/W2b |

## 2. A tradução — o defeito era o SEGUNDO pedido

O módulo servia `TARGET_LANG = 'en'` e

    _target_langs('ja')  ==  ('en', 'ja')

Nenhum vídeo japonês tem faixa inglesa; o `pick` seguinte era a **própria língua original**, e era
ela que chegava ao ecrã. Medido hoje no oráculo (executado, não lido):

    _target_langs('ja') == ('pt', 'ja')      # a escolha primeiro, o original so' como 2o pedido
    _target_langs('en') == ('en',)           # en/pt/es: a propria lingua, nunca traduzida
    _target_langs('pt') == ('pt',)
    escolha 'fr': _target_langs('ja') == ('fr', 'ja'); _target_langs('en') == ('en',)
    escolha 'ja': _target_langs('ja') == ('ja',)   # pedir a propria lingua seria pedi-la duas vezes

A escolha vive em `_main/caption-settings.json` (ignorado pelo git — é a escolha **dele**, não da
árvore), escrita por `tempfile` + `os.replace`, e um ficheiro ausente/corrompido responde `'pt'`.

## 3. A face — a regra que vencia a batalha das folhas vencia também o desenho

`panel-unified.css` carrega **por último** e carregava `font-family: ... !important` em todas as
superfícies: 45 desenhos, uma face. A cura tira a face da regra de vitória e deixa lá só a caixa
(19,5 px / `.34em`), que é o que precisa mesmo de vencer um tema.

Medido no RENDER (Chromium, os 45 desenhos, com as folhas que o `lazy-assets.js` entrega por
pedido — sem elas o probe media 30 desenhos com a face de RECURSO e chamava isso de identidade):

    ROW FACE: 28 distinct (family + size) across 45 theme(s)
    LINE UNREADABLE (<4.5:1) in 0 of 45 | CLIPPED in 0 | STAMP UNREADABLE in 0
    --neg-arm: ROW FACE: 1 distinct across 45  (rc=1)

A arm do `--neg-arm` repõe a regra literal de antes da cura e exige a queda. Foi assim que o
`theme-caption-identity` também nasceu: ele julga a CSS, o `panel-history-clip` julga os pixels.

## 4. A roda — a causa era um contentor fantasma, e as outras quatro foram refutadas

Uma propriedade de cada vez, o mesmo documento, a mesma roda (`_main/_receipt-wheel-before.log` /
`_main/_receipt-wheel-after.log`):

| arm | mudança | resultado |
|---|---|---|
| E0 | o que embarca antes | `body 0->0` — **nada** |
| E1 | `.history__list { overscroll-behavior: auto }` | `body 0->400` → **esta é a causa** |
| E2 | `.history__list { overflow: visible }` | `body 0->400` (a mesma causa, outro termo) |
| E3 | `.history__body { overflow: hidden }` | `body 0->0` (controlo: o probe lê a caixa certa) |
| — | `body.scrollBy(0,200)` | `scrollTop=200` (a caixa anda; só o caminho da roda estava morto) |

`#history-list` carrega `overflow-y: auto` **e** `overscroll-behavior: contain` mas é pintado
`display: block`, logo a caixa tem a altura do conteúdo (`clientHeight == scrollHeight == 5961`) e
nunca rola; quem rola é `.history__body` (`630 / 5985`), e o `contain` do fantasma **para a roda
antes de ela chegar lá**. A cura não adivinha a caixa: `historyScroller()` pergunta ao documento
qual antepassado tem `overflow-y: auto|scroll|overlay` **e** conteúdo mais alto que a caixa.

Depois da cura, o mesmo probe:

    W2  GREEN — a real wheel over the rows moved body (delta 400)
    W2b GREEN — the far-right column of the rows scrolls too
    --neg-arm: `wireHistoryWheel();` removido NUMA CÓPIA -> W2/W2b RED, rc=1, "NEG-ARM: PASS"

O controlo é uma mutação cirúrgica do próprio mecanismo, numa cópia — nunca "o `panel.js` de HEAD",
que apodrece no dia em que a cura é cometida (a armadilha que o `paint-cost` já mediu).

## 5. O que NÃO está verificado

- **Nada disto foi visto na tela do dono.** A prova é Chromium headless + oráculos + arms que não
  renderizam áudio nem abrem janela. `verified` continua a exigir uma corrida real, pela mão dele.
- A roda foi medida por `page.mouse.wheel` (evento confiável) na janela de 380x900 do probe;
  a janela real dele tem outra altura, e o `historyScroller()` não depende dela — mas isso é
  `UNMEASURED` até ele rolar a lista.
- O seletor de língua foi exercitado no probe (`M`), não no WebView2 vivo.
