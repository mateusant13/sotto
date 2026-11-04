# Recibo -- imitacao 1:1 das legendas do YouTube (lane YtOneToOne-2)

Worktree `H:/sotto-wt/YtOneToOne`, branch `lane/yt-one-to-one`, base `82e16a5` (HEAD).
Data: 2026-11-04. Nada foi lancado: sem app, sem janela, sem audio, log vivo lido em
somente-leitura.

## A ORDEM, restabelecida

O dono, verbatim: *"entender literalmente como funciona as legendas do youtube e o display e
as animacoes e as quebras de linha 1:1 e imitar no sotto. mesmo quando é só transcricao em
tempo real."*

## INSTRUMENTO

Cinco oraculos da lane, todos python puro, nenhum abre janela:

| oraculo | o que julga |
|---|---|
| `_main/youtube-word-clock-oracle.py` | a linha cresce UMA palavra por tick e nunca mais que o relogio do payload |
| `_main/youtube-reveal-oracle.py` | a janela do caminho vivo contra as linhas que o player pintou + a tabela em ms |
| `_main/youtube-rows-oracle.py` | linhas, quebras e caixa do player `dom_match`/`breaks_match` |
| `_main/youtube-monotonic-oracle.py` | a legenda nunca recua (regra pura + replay do corpus) |
| `_main/incomplete-word-oracle.py` | a palavra nao provada nao vai para o ecra, em qualquer lingua |

Corpus novo commitado: `_main/fixtures/yt-caption-clock-replay-20261104.json` (206 028 B),
extraido do log do dono por um comando unico (censo abaixo).

## ANTES (medido nesta arvore, antes de qualquer edicao)

```
youtube-word-clock-oracle          rc=0  WORD-CLOCK GREEN -- arms=20 pass=20 fail=0
youtube-reveal-oracle              rc=0  4 elementos, nenhuma medida em ms; --neg-arm saia 1 NOS DOIS casos
youtube-rows-oracle                rc=0  YOUTUBE-ROWS GREEN
youtube-monotonic-oracle           rc=2  YOUTUBE-MONOTONIC NO-VERDICT -- webview-run.log sem linhas YOUTUBE_CAPTION
youtube-monotonic-oracle --neg-arm rc=2  (o braco negativo tambem nao tinha veredicto)
incomplete-word-oracle             rc=0  26 PASS / 0 FAIL
youtube-1to1-oracle                RED    source-is-youtube (PRE-EXISTENTE, fora desta lane)
```

Quatro defeitos medidos, nao tres opinioes:

1. **A palavra nova podia ser datada ATRAS do que o ecra ja' mostrara.** `LiveRows.push`
   datava as palavras novas por `at` tal e qual, e `at` chega como `monotonic() - late_s`
   (`caption_overlay.set_text`), onde `late_s` e' o atraso do ASR *daquela* entrega. Um lote
   mais atrasado que o anterior RECUA `at`. Reproduzido:

   ```
   lr.push("alpha bravo charlie", 100.0); lr.push("alpha bravo charlie delta echo", 99.0)
   starts = [100.0, 100.12, 100.24, 99.0, 99.18]
   frame(100.1) -> ['alpha bravo charlie']      # tres palavras do FUTURO
   ```
   `frame` conta `start <= t` e corta um PREFIXO, logo mostrava palavras que ainda nao foram
   faladas e ESCONDIA `delta`/`echo`, que ja' o tinham sido. E' a mesma classe da queixa de
   2026-10-30 (*"repete a legenda de instantes atras"*).

2. **A lei "a legenda nao recua" nao tinha medicao nenhuma numa arvore limpa.** O oraculo
   lia `_main/webview-run.log`, um artefacto de RUNTIME que nao existe numa worktree: `rc=2`
   e `NO-VERDICT`, `--neg-arm` incluido.

3. **O replay lia 65 % do log e calava os outros 35 %.** Censo do log do dono
   (`_main/webview-run.log`, 64 372 760 B):

   ```
   caption_lines=8711  clock(painted-other-track)=434  paint(has-cue)=5242
   fora do replay: painted-lines=1257, cdp-lines=1778      # = 3035 linhas (34,8 %)
   ```
   As 3035 sao o ramo PINTADO (`lines=`/`ratio=`, zero instantes) -- nao alimentam as duas
   regras de relogio -- mas o oraculo nao o dizia em lado nenhum.

4. **Dois bracos negativos mentiam sobre o proprio resultado.** `youtube-reveal-oracle.py`
   e `incomplete-word-oracle.py` saiam `rc=1` tanto quando apanhavam o mutante como quando
   nao apanhavam, contra o contrato da casa (`rc=1` quando apanha, `rc=0` quando nao).
   E `youtube-word-clock-oracle.py` tinha o default `ROOT = "H:\sotto"`: corrido dentro de
   uma worktree, julgava os ficheiros da arvore VIVA.

## A MUDANCA (ficheiro + funcao + porque)

| ficheiro | funcao | porque |
|---|---|---|
| `app/webview/youtube_reveal.py` | `LiveRows.push` | piso monotono no relogio da palavra nova: `base = max(at, ultima+passo)`. O `start` de uma palavra nunca e' anterior ao de uma palavra ja' no ecra, e duas palavras nunca partilham o mesmo instante (senao entram no mesmo quadro). Nao muda nada no caminho em que `at` ja' esta' a frente. |
| `_main/youtube-word-clock-oracle.py` | `ROOT`, `arm_word_start_never_rewinds`, `neg_arm` | `ROOT` passa a resolver a arvore do PROPRIO oraculo (`SOTTO_ROOT` continua a servir para julgar outra de proposito). ARM 8 mede a propriedade acima em tres pontas: relogios nao decrescentes, ecra == relogio datado a cada 10 ms de -120 a +220 ms, e a palavra falada nao escondida. O `neg_arm` ganhou a mutacao correspondente (tirar o piso) e exige que a ARM 8 fique VERMELHA. |
| `_main/youtube-reveal-oracle.py` | `word_ms_table`, `neg_arm_clock_shift`, `main` | a tabela em ms por palavra (abaixo), as arms `word-ms-table` e `word-ms-table-monotone`, e o mutante do relogio +50 ms que a tabela TEM de ver. Contrato do `--neg-arm` corrigido. |
| `_main/youtube-monotonic-oracle.py` | `read_fixture`, `read_log`, `main` | corpus commitado quando o log vivo nao existe; censo impresso sempre (linhas usadas, por forma, e as que ficam de fora nomeadas); contrato do `--neg-arm` corrigido. |
| `_main/incomplete-word-oracle.py` | `neg_arm` | contrato do `--neg-arm` corrigido (rc=0 quando o mutante nao e' apanhado). |
| `_main/fixtures/yt-caption-clock-replay-20261104.json` | (novo) | o corpus medido: 5 663 linhas apos dedupe consecutivo, com `caption_lines`, `shapes` e a razao de existir. |

sha256 (16 hex), antes -> depois:

```
app/webview/youtube_reveal.py        49b1bcfd86169f00 -> 4bf9a62295438002
_main/youtube-word-clock-oracle.py   df11bb583f8d8ed2 -> 820aba03b4382756
_main/youtube-reveal-oracle.py       28fd024256bdb293 -> 3aebb1e95c7823f4
_main/youtube-monotonic-oracle.py    086050f4dba1fa8e -> e5545d5db3a3510f
_main/incomplete-word-oracle.py      e21a54f2c9031237 -> 8e6eb3b2b7006cb7
_main/fixtures/yt-caption-clock-replay-20261104.json  (novo) a7cd98ad50709629
```

## A TABELA, palavra a palavra, em ms (a aceitacao da lane)

`python _main/youtube-reveal-oracle.py`, cue 0 do payload do player
(`yt-WdaHAGRBB6s.en-orig.json3`, `"Have you ever had to kill a man?"`).
`player_ms` = o `tOffsetMs` que o PROPRIO player carrega (o payload e' o documento do player:
`payload.is_player_document = true` no artefacto `1to1-capture`); `sotto_ms` = o primeiro
instante, em passos de 1 ms, em que a funcao de producao (`youtube_reveal._reveal_text`, a que
`frame` chama) mostra a palavra.

```
  palavra   player_ms   sotto_ms drift_ms
  Have            0.0        0.0      0.0
  you           240.0      240.0      0.0
  ever          400.0      400.0      0.0
  had           640.0      640.0      0.0
  to            800.0      800.0      0.0
  kill          920.0      920.0      0.0
  a            1160.0     1160.0      0.0
  man?         1200.0     1200.0      0.0
```

drift 0,0 ms em 8/8 palavras, e a medida e' de DUAS PONTAS: 1 ms antes do instante declarado a
palavra ainda nao esta' no ecra (`early_ms`), e no instante declarado esta'. Uma ponta so'
passaria com um motor que mostra tudo de uma vez.

O QUE ESTA TABELA **NAO** DIZ: ela mede o DESENHO contra o relogio declarado do player, nao os
pixels. O que a leitura do UIA/CDP entrega **atrasa-se** desse relogio -- medido pelo
`_main/youtube-drift-oracle.py` no mesmo fixture: `n=16 mean_ms=+172,5 median_ms=+107,2
max_ms=+704` (positivo = player adiantado = a nossa revelacao TARDE quando segue a pintura).
E' por isso que o caminho vivo COPIA a pintura em vez de extrapolar o relogio.

## DEPOIS (medido nesta arvore, depois da mudanca)

```
youtube-word-clock-oracle           rc=0  WORD-CLOCK GREEN -- arms=23 pass=23 fail=0
youtube-reveal-oracle               rc=0  reveal 15/15 | word-ms-table 8/8 drift 0 ms |
                                         word-ms-table-monotone SIM (4 elementos + 2 arms novas)
youtube-rows-oracle                 rc=0  YOUTUBE-ROWS GREEN
                                         SUMMARY samples=16 rows_match=16/16 draw_match=16/16
                                         BREAKS  samples=16 dom_match=16/16 text_match=16/16
                                                 breaks_match=16/16 older_row=4/4 shape=16/16
                                                 visible_box=15/16 (fora do veredicto, ver abaixo)
youtube-monotonic-oracle            rc=0  VERDICT GREEN -- 14 PASS / 0 FAIL
                                         corpus=yt-caption-clock-replay-20261104.json
                                         linhas=5663 (relogio 434, pintura 5242)
                                         fora do replay: cdp-lines=1778, painted-lines=1257
                                         regra ANTIGA recua 227 (pior 1759,92 s); regra NOVA recua 0
incomplete-word-oracle              rc=0  26 PASS / 0 FAIL (26 arms)
```

O corpus commitado reproduz o veredicto do log vivo: as duas regras dao os mesmos numeros
(antiga 227 recuos, nova 0) sobre as mesmas 428 linhas servidas.

## BRACOS NEGATIVOS (todos rc=1, contrato da casa)

```
youtube-word-clock-oracle --neg-arm   rc=1  NEG-ARM PASS -- RED as designed: o mutante derruba o oraculo
                                     + "piso do relogio da palavra removido -> arm 8 RED em 2/3 checks
                                        (as palavras de uma linha tem relogios nao decrescentes;
                                         o ecra mostra exactamente o que o relogio ja' datou)"
youtube-reveal-oracle --neg-arm       rc=1  NEG-ARM PASS (pintura atrasada: janela RED;
                                            relogio+50 ms: drift -50,0 ms na tabela)
youtube-rows-oracle --neg-arm         rc=1  NEG-ARM PASS -- the arm 'rows-from-player' is broken on 13/16
youtube-monotonic-oracle --neg-arm    rc=1  NEG-ARM PASS -- a regra ANTIGA recuou o ecra 227 vez(es)
                                            em 428 linha(s), pior 1759,92 s
incomplete-word-oracle --neg-arm      rc=1  NEG-ARM PASS: com a regra DESLIGADA o parcial mostra
                                            ['eu vou'] (a regra ON mostra ['eu'])
```

Cada braco foi mutado por DENTRO do ficheiro que julga (copia ou mutacao restaurada no `finally`),
e nao por uma reimplementacao ao lado.

## As outras quatro metades da ordem, e o que cada uma custou

* **Quebras de linha do player, nunca por contagem de palavras** -- `youtube_rows_oracle`
  `breaks_match=16/16`, `text_match=16/16`, `older_row=4/4`, sobre as 16 amostras em que o
  player pintou `>>`-lines (`_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json`).
  O caminho vivo usa `_yt_rows(painted,` e o `window_by_paint` foi proibido (`reveal-oracle`
  `wiring-is-live`, lido por AST e nao por texto).
* **Fade da linha nova, medido em ms** -- o unico fade MEDIDO no fixture e' o da linha que SAI:
  `word_fade.EXIT_S = 0.45 s`, e o intervalo medido e' **0,424 .. 0,552 s** (o modelo reproduz
  os 16 quadros). O fade de ENTRADA (`word_fade.DURATION_S = 0.12`) **nao tem medicao** no
  fixture: nenhum artefacto guarda alfa por pixel do player. E o dono JA' mandou tira-lo duas
  vezes (`caption_overlay.FADE_ON = False`), logo nao corre no produto; o braco da ARM 7 do
  `youtube-word-clock-oracle` prova as duas metades do botao.
  `[INFERENCE]` 120 ms de entrada = valor a olho, o proprio docstring o diz.
* **Regra da palavra incompleta em qualquer lingua** -- 26 arms, incluindo pt/en/ru/es no mesmo
  arm; a regra usa o marcador `▁` do tokenizer, que nao depende da lingua.
* **Revelacao ancorada no relogio do AUDIO** -- `caption_overlay.set_text` publica
  `live.push(full, monotonic() - late_s)`, e `late_s` e' a idade do audio daquela linha
  (`tap_ms` -> `_drain_caption_pending`), nao a hora de chegada do ASR. Medido no log do dono
  (1 443 pinturas): `p50 = 188 ms`, `p90 = 4 719 ms`, `p99 = 52 275 ms`, `max = 203 282 ms`;
  **88,5 %** das linhas ancoram exactamente. O tecto de 3,0 s do shell apanha as outras
  **11,5 %** (166 linhas), e nessas a ancora curta-se em `p50 = 11 122 ms`, `p90 = 48 567 ms`,
  `max = 200 282 ms` -- o efeito e' a linha inteira aparecer de uma vez em vez de palavra a
  palavra. O tecto vive em `sotto_webview.py` (fora dos ficheiros desta lane).

## O QUE NAO ESTA PROVADO / FICA ABERTO

* **`rate = 0` (video em pausa) nao se distingue de 1x.** O shell poem `rate = 1.0` quando
  `yt_cdp_rate` sai de `[0.05, 16]` e o overlay clampa o mesmo intervalo, logo uma pausa e'
  lida como 1x. O estrago e' LIMITADO por medicao: `_PlayerCue.clock` extrapola no maximo
  `PLAYER_HOLD_S = 3,0 s` depois da ultima leitura, portanto uma pausa revela no maximo 3,0 s
  de cue a mais. Fechar isto exige `paused` no payload do cue -> `sotto_webview.py`, que nao e'
  desta lane.
* **`visible_box=15/16`** e' o `_PlayerCue.frame` com `rollup=0, exit_s=0`: a terceira linha
  (a que rola para fora) nao e' desenhada pelo overlay. O modelo do `youtube_reveal.frame`
  mantem-na (`older_row=4/4`) e o intervalo medido do roll-out e' 0,424..0,552 s; o overlay
  encolhe para 2 linhas porque a ordem do dono de 2026-11-03 tirou a terceira linha do ecra
  (*"o YouTube mostra DUAS"*, `painted_rows`). E' um compromisso MEDIDO, nao um esquecimento:
  desenhar a terceira punha o Sotto a mostrar a linha seguinte antes do player.
* **`youtube-1to1-oracle` continua RED em `source-is-youtube`** -- PRE-EXISTENTE (medido antes
  de qualquer edicao nesta arvore, e igual em `H:/sotto`). Nao e' desta lane e nao foi mexido.
* **A tabela em ms e' do desenho, nao dos pixels**; o atraso da FONTE (UIA/CDP) mede-o o
  `youtube-drift-oracle` (`mean +172,5 ms`, `max +704 ms`). Um numero nao substitui o outro.
