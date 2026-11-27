# `harness/twins/` — os twins offline que ESTA arvore realmente tem

Um twin é o comportamento visto em BYTES GRAVADOS, reproduzido sem browser, sem janela e sem o vídeo
do dono. Não é um segundo portão: o dono do invariante continua a ser o oráculo nomeado na coluna da
direita, e é ELE que corre na bateria. Um twin que virasse uma segunda cópia da mesma asserção seria
o trabalho pago duas vezes em toda a corrida.

|twin|gravado por|replay (o dono do invariante)|o que ele pode provar|o que ele NÃO pode|
|---|---|---|---|---|
|`yt-player`|`_main/yt-snapshot-capture.py` (Chrome próprio, porta 9341, `--mute-audio`, escondido) → `_main/fixtures/yt-snapshot-*.json`|`python _main/yt-capture-replay-oracle.py` (43 braços, `--neg-arm` 7/7) = passo `yt-capture-replay`|`currentTime`/`paused`/`readyState` a 50 ms, a pausa real, o recuo real de um seek, e o que `youtube_clock.pause_proven` + `youtube_monotonic` DECIDIRIAM -- o código do produto, importado|o TEXTO da cue sem sessão (medido 2026-11-26: `200` com 0 bytes em 26 faixas de 3 vídeos → `CANNOT-MEASURE why=no-caption-segment`)|
|`yt-paint-freeze-20261104`|captura de 0,05 s de `r-AsGBMDI6c` (745 amostras)|o mesmo `yt-capture-replay-oracle.py`|o congelamento do dono já estava gravado: 744 amostras com as MESMAS `rows` e o relógio a andar 37,2 s|idem|
|`yt-clock-replay-20261104`|série do relógio do YouTube|`_main/yt-producer-soak-oracle.py` / `_main/youtube-monotonic-oracle.py`|monotonia, seek nomeado, o chão a descer com a âncora|a frescura da foto (o `stamp` nasce na leitura) — dono: `yt-pause-disagreement-oracle.py`|
|`panel-startup-flash-census-20261011`|censo de arranques|`_main/panel-startup-flash-census.py --read`|a população de 20 arranques como ela foi medida (leitor puro, não re-executa)|qualquer número de OUTRA população (`18/20` e `0/20` são outros braços)|
|`boot-interaction-altc-paint-{fast,slow}`|dois arranques reais|`_main/altc-gesture-oracle.py`|o gesto medido com a faixa a pintar e devagar|input sintético (`keybd_event`/`SendInput` mede o Windows, não o Sotto)|

## Como se acrescenta um twin

1. Grava com uma sonda de vida limitada, no MEU ambiente (porta e perfil próprios, `--mute-audio`), e
   escreve o fixture com DOIS carimbos (`perf_ms`/`epoch_ms`) e a origem.
2. O replay pergunta ao código do PRODUTO (importado), nunca a uma re-escrita da regra.
3. O braço tem de saber ficar vermelho: mutar a expectativa (não o produto) tem de dar `MISSING` + rc 1.
4. O oráculo entra na bateria em par com o seu `red-as-expected-*` no MESMO commit; um twin que ninguém
   corre não é um twin.
