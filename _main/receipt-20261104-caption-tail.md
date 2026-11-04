# RECEIPT — a cauda da legenda ao vivo (2026-11-04)

## O que estava errado

`CAPTION_APPLIED` era a unica medida de "quando o pixel mudou" e misturava
duas perguntas diferentes:

1. a `final` chega pelo `take_closed` SEM `tap_ms`, e o shell reusava o tap da
   ultima parcial → a idade saia do intervalo entre duas frases.
   MEDIDO (sessao do dono, 04:00-01:25, 18030 pinturas no log):
   `CAPTION_APPLIED ... kind=final aged_kind=hold-expired audio_ms=166615`
   para uma linha de 3 s; `CAPTION_LAG_STATS n=200 p50=634 p90=45402 over=109`.
2. a linha `final` entrava na serie do ecra, logo o p90 e o `over=` mediam a
   duracao das frases.

## O que foi medido depois de separar os canais

Sessao viva, 191 pinturas que MUDARAM o texto (a primeira aparicao):

    p50 = 195 ms   p90 = 1645 ms   <=400 ms = 54,5%

Bimodal, sem quase nada entre 400 e 1500 ms. O pico nos 1500 ms e' o relogio
`COMMIT_MAX_HOLD_MS` do PAINEL: o `LineFormer` so' ve' o fim da frase quando o
fragmento SEGUINTE chega, e o bloco que vem depois das ultimas palavras
decodifica VAZIO — `push` nunca corre, e a palavra nao provada fica a espera.

## A cura

`worker/silence_tail.py` decide quando o silencio PROVA a cauda (0,8 s = 1,5
blocos de 560 ms) e `LineFormer.publish_on_silence` publica o texto ACTUAL da
linha com `stable: true` — o que `app/panel/stable-words.js::wordsAreWhole` ja'
le'. A linha NAO fecha (`SENTENCE_GAP_S = 8.0` decide onde quebra), logo o
historico nao ganha linhas por pausa.

O instrumento: `age` deixou de ser fabricada (tap consumido por uma pintura) e a
`final` saiu da serie, com o nome `aged_kind=final-close` no log.

## Prova

- `_main/incomplete-word-oracle.py` 26/26 (4 arms novos: silencio curto nao
  publica, 0,9 s publica a linha inteira `stable`, um silencio publica uma vez,
  a linha continua aberta; controlo = a mesma funcao com o limiar em 99 s).
- `_main/caption-lag-budget-oracle.py` 13/13 arms, `--neg-arm` 9/9 mutantes
  apanhados (dois novos: tap reaproveitado, linha fechada contada).
- `_main/caption-lines-oracle.py` 13/13.
- Ponta a ponta no worker REAL, `--selftest --audio _main/live-sample-cable-input-90s.wav`:
  a cauda `PC` de `força luvas do` saiu como evento proprio publicado pelo
  silencio (31 eventos de legenda, `empty_chunks=32`).

## Portao estrutural (nao foi silenciado)

`_main/code-health-oracle.py` VERDICT FAIL, com os numeros:
`sotto_webview.py` 18599→18645 linhas (ja' estava 18637 no HEAD antes deste
trabalho) e `sotto_worker.py` 7356→7413 (a decisao vive em modulo novo
justamente para nao crescer mais; so' a chamada ficou no worker).
`shell_relaunch.py +43 B` e' anterior a este trabalho.

## O painel mostra a palavra (medido, 2026-11-04)

O evento que `publish_on_silence` emite passa pelo mesmo caminho do painel que
qualquer parcial. Executado o motor REAL em Node
(`caption-formulation.js::createEngine` + `stable-words.js::wrap`):

    ingest('hello wor', {stable:true, final:false}) -> wordsStable=true
      tailClosed=false  wordsAreWhole=true    <- a ultima palavra PINTA
    ingest('outra linha', {final:false})        -> wordsAreWhole=false
                                                  <- sem a promessa, segura

Logo a cura nao depende do relogio do painel: depende do sinal que o worker
passou a mandar no silencio.
