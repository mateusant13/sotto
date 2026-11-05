# A pontuacao de modelo (7,1 MB) e a janela do painel (7 min -> 31 min)

2026-11-05. Duas perguntas dele, dois numeros.

## 1. "nada opensource que ajuda nisso?"

Tinha. O que NAO existia nesta arvore era uma medicao do que serve.

| peca | licenca | disco | CPU | medido nesta maquina |
|---|---|---|---|---|
| `sherpa-onnx-online-punct-en` (Edge-Punct-Casing, arXiv:2407.13142) int8 | Apache-2.0 | **7,1 MB** + 146 KB vocab | 1 fio | carga **75,3 ms**, **6,1-8,5 ms/linha** (mediana 6,8) em **10 linhas reais** de `CAPTION_IN` do log dele |
| pacote `sherpa_onnx` 2.0.1 (cp311 win_amd64) | Apache-2.0 | 2,2 MB wheel / 28 MB instalado | -- | traz o proprio runtime: nenhum `onnxruntime` no `sys.path` |

10 linhas medidas, tempo total 68 ms para o lote inteiro. Um chunk do worker e 560 ms.

**O que ele faz MAL, medido, e por isso a guarda:** sobre portugues, o mesmo modelo
devolve `EU Gosto Muito, disso sabe como E que E` -- caixa aleatoria com aparencia de
pontuacao. Logo a regra e identidade sempre que a tag de lingua nao comeca por `en`
(medido tambem: tag `None` nunca e "provavelmente ingles").

**O `?`:** o modelo ingles poe `?` a meio de uma hipotese parcial (`that I? didn't`,
medido). Como o `punct-prosody-oracle` mostrou que o F0 NAO correlaciona com pergunta,
`?`/`!` sobrevivem so quando FECHAM o texto; a meio sao removidos. `,` e `.` ficam.

**Onde entra:** so na linha FECHADA (`LineFormer._event` com `final or closed`). A
parcial nao leva marca nenhuma -- um comma a saltar de sitio a cada chunk e o defeito
de render que ele chamou inadmissivel.

Portao: `_main/punct-model-oracle.py`, 14 arms, `--neg-arm` 4/4. Duas armadilhas
achadas pelo proprio braco negativo, ambas corrigidas: a copia mutada vivia num
directorio temporario **sem o modelo**, logo `find_model` devolvia `None` e a arm
ficava verde por AUSENCIA em vez de por guarda (falso verde do instrumento); e o
comentario do modulo tinha um apostrofo a fechar a string.

## 2. "historico completamente patetico" -- a janela do painel

`_main/receipt-20261105-right-panel-history.md` (lane RightPanelHistory) mediu, ao vivo:

* `#caption-list` fica cravada em **200** linhas a partir das 16:31:25 e cada commit
  apaga a mais antiga: retencao **7 min 37 s** (a linha mais antiga as 16:32:36 nasceu
  as 16:24:59.898).
* **51 de 200 linhas (25,5 %) eram `A,B,A` EXACTAS**: a frase S comeca com
  `start=None` (2371 de 3321 commits de hoje, 71 %), o primeiro commit da frase
  seguinte ocupa o slot de "ultima linha", e o `final` de S chega depois -- o prefixo
  e comparado contra a linha ERRADA e o texto volta a ser apendado.

Cura, nas duas metades:

* `app/panel/panel.js`: `recentRowsForSource(source, DEDUPE_WINDOW=8)` -- a busca de
  prefixo passa a varrer as ultimas 8 linhas do MESMO source, nos dois sentidos.
* a janela sobe de 200 para **1200** linhas nos dois sitios (`panel.js` e
  `app/webview/sotto_webview.py`): ~120 KB de DOM por 31+ minutos de transcricao.

Portoes: `_main/panel-prefix-row-oracle.py` (7 arms + o call site, `--neg-arm` **4/4**;
o oraculo era VACUO para este caso -- alimentava `isPrefixExtension` directamente e
nunca podia observar que a linha comparada era a errada -- e as suas tres mutacoes
estavam ancoradas no texto antigo) e `node _main/_panel2-dom-probe.js` **94/94 GREEN**.

## SELF-AUDIT

* **protocolos em falta** -- escrevi o modulo antes de ler o irmao `punctuation_prosody.py`
  (mesma convencao: identidade por omissao, `--neg-arm` rc=1). Corrigido depois de ler.
* **verificacao adicional** -- tomada: as 10 linhas reais do log do dono, e nao frases de
  manual. Nao tomada: a legenda VIVA com o modelo ligado (exigiria relancar a app dele).
* **checkboxes novas** -- "um braco negativo corre no MESMO ambiente que o positivo, ou o
  verde pode ser ausencia de pre-condicao" (o falso verde do `find_model`).
* **review por outro subagente** -- nao. O `--neg-arm` e a medicao fizeram esse papel.
* **gate-doubt**
  * `verde-de-verdade:` verdadeiro para a guarda de lingua e para o filtro (mutacoes
    derrubam arms nomeadas). Fraco para "pontua bem": 10 linhas bastam para o custo,
    nao para a qualidade; e o modelo nunca poe ponto final no ultimo trecho.
  * `falta-no-gate:` nada compara a pontuacao com o que o YOUTUBE mostra na mesma fala.
  * `gate-melhor:` essa comparacao -- o `word-reveal-1to1` ja tem o cue do player.
* **confianca** -- `alta` no custo e na guarda; `media` na qualidade percebida.

## CACHE/PRICE
Nenhum modelo de linguagem foi chamado para esta mudanca; o unico modelo e o
restaurador local de 7,1 MB (Apache-2.0), que nao tem custo por token.
