# AUDITORIA COMPLETA DA LEGENDA DO YOUTUBE — 2026-11-02 23:2x

Ordem do dono, verbatim: *"tu vai fazer tudo igual a legenda do youtube. mesmo quando é só
transcricao em tempo real, deve imitar o comportamento da legenda do youtube"* e *"tu nao entender
100% o caminho de cada coisa e os gargalos. tu vai usar ferramentas de profiling e debugger"*.

Este recibo é a auditoria do caminho **medida no processo vivo** (`pid` no log, `H:\sotto`), não uma
leitura de código. Cada número traz o instrumento e a hora. O que não foi medido está dito como não
medido.

---

## 1. O CAMINHO, DO ÁUDIO AO PIXEL (o que roda em cada volta)

```
tick do laco externo (cadencia 120 ms de espera; ~1,1-4,7 leituras/s medidas)
  |
  +-- _read(hwnd)
  |     +-- _target()               janela em foco / titulo        YT_PROF stage=target
  |     +-- _source()               que produtor manda na tela      YT_PROF stage=source
  |     +-- _youtube()
  |           +-- _youtube_video_id   BARRA DE ENDERECO (UIA)  <-- GARGALO HISTORICO
  |           +-- _youtube_painted    NOMES (+ RECTS) dos spans visiveis  <-- 2a peca
  |           +-- youtube_captions.align_painted   acha o cue da faixa
  |           +-- _yt_rows            pintura -> linhas de tela (+ histerese)
  |           +-- _yt_lines           faixa -> linhas (relogio do player)
  +-- _tick(got)                    decide o quadro e pinta a overlay
  |     +-- overlay set rows         EXTERNAL_CAPTION_DRAWN / YT_FRAME
  +-- yt_live_frame()               re-render ENTRE leituras (relogio + faixa)  <-- 3o produtor
```

Três escritores possíveis de texto na tela (**a origem de todos os defeitos de render**):
`_yt_rows` (pintura), `_yt_lines` (faixa com relógio interpolado), e o caminho de ASR
(`sotto_worker`) — este último só fala quando o YouTube não está a fornecer nada.

---

## 2. OS DEFEITOS, CADA UM COM A MEDIDA QUE O PROVA

| # | defeito | medida (instrumento, hora) | cura | oráculo |
|---|---|---|---|---|
| D1 | **flicker A/B/A/B** — a linha actual e a anterior trocadas | `caption-frame-audit` janela 23:05:00-23:08:30: **901 quadros, 491 oscilações, 10 pulos de linha**; exemplos `cima, tentando` ↔ `cima, tentando pressionar o ` | dois produtores no mesmo ecrã: o re-render de 60 ms (`yt_live_frame`) recomponha a faixa com relógio interpolado enquanto a pintura fornecia a linha. Agora o re-render é **condicionado** a `painted_now` (2 s) e leva etiqueta própria `external:youtube:liveframe` | `_main/caption-producer-oracle.py` 5/5 + `--neg-arm` |
| D2 | **duas fotos da mesma pintura** (texto de uma leitura, rects da anterior) | código: `painted_words` era chamado com `with_rect=False` e os rects vinham noutra chamada | `_youtube_painted` faz **uma** leitura com `with_rect=True` e reaproveita o rect do filho cujo texto não mudou | arm `one-photo-with-rects` + `rect-reuse` |
| D3 | **gargalo da barra de endereço** — 119 ms de 124 por tick | `cProfile` (`_main/_yt-cprofile.txt`, 23:13): `_youtube` 124 ms, `_youtube_video_id` 119 ms, `external_subs.edit_values` 119 ms | id do vídeo em cache por janela, invalidado pelo título, TTL 30 s | leitura medida 47-234 ms depois (antes 109-500) |
| D4 | **histerese das linhas** — crescer passa, encolher espera 280 ms | log: `YT_FRAME` a alternar 2↔3 linhas em 280 ms | `_yt_rows_settle` + `ROWS_SETTLE_S` | arm `row-hysteresis` |
| D5 | **auditoria só media overlay ligado** | `caption-frame-audit --since 23:15` → `VERDICT: NO-FRAMES` com a legenda desligada | `_tick` publica `YT_FRAME src=.. rows=.. lines=..` em cada mudança; o auditor lê as duas etiquetas | janelas 23:05 (FLICKER) e 23:19 (CLEAN) lidas pelo mesmo parser |
| D6 | **atraso publicação = 151 s** (instrumento mentiroso) | relatório de 23:19: `mediana=151731 ms` — emparelhava uma leitura de minutos antes | par só vale a ≤1,5 s; o resto conta-se como `sem par` | mesma janela agora: `mediana=343 ms pior=1472 ms` |
| D7 | **`_t0` não definido** em `_yt_rows_impl` (introduzido por mim hoje) — com o profiler ligado o caminho da pintura devolvia `[]` | log: 4× `YOUTUBE_PAINT_ROWS_FAILED` | `_t0 = time.monotonic()` no impl; contagem de falhas parada em 4 (todas de antes) | `_main/undefined-names-oracle.py` GREEN |

### O antes e o depois, pelo MESMO instrumento

| janela | quadros | s | oscilações | pulos | repinturas | veredicto |
|---|---|---|---|---|---|---|
| 23:05:00-23:08:30 (antes) | 901 | 193,2 | **491** | 10 | 0 | `FLICKER` |
| 23:19:30-23:20:34 (depois) | 10 | 64,2 | **0** | 0 | 0 | `CLEAN` |

A janela "depois" é mais curta e com o vídeo em pausa: o número que vale não é a contagem, é a
**ausência de oscilação** num caminho onde antes havia 2,5 oscilações por segundo.

---

## 3. CUSTO POR ESTÁGIO (o que o profiling diz hoje)

`cProfile` de uma volta de `_youtube`: **124 ms → 5 ms** depois de D3.

`YT_PROF` em regime (23:12-23:14):

| estágio | ms |
|---|---|
| `target` / `source` | 0 |
| `paint` (nomes + rects, com reaproveitamento) | 0-16 |
| `words` | 0-16 |
| `rows` | 0 |
| `tick` | 0 |
| leitura completa (`EXTERNAL_CAPTIONS_READ_MS`) | 47-234 (era 109-500) |

O que resta dos 47-234 ms é o **UIA do Windows**, não o nosso código: uma travessia de ~1.500 nós do
Chrome custa dezenas de ms por chamada e não há cache que a evite quando a janela muda de estado.
O passo seguinte, se ele quiser menos, é reduzir a FREQUÊNCIA de leitura (hoje ~1 leitura/s com o
vídeo em pausa) e deixar o re-render cobrir os intervalos — que é exactamente o desenho do
`yt_live_frame`, agora com uma fonte só.

---

## 4. O QUE ESTÁ VERDE NOS ORÁCULOS (corridos hoje, depois das curas)

| oráculo | veredicto |
|---|---|
| `caption-producer-oracle` | PASS 5/5 (+ `--neg-arm` PASS) |
| `caption-frame-audit --neg-arm` | PASS 4/4 |
| `hotkey-observed-oracle` | PASS 6/6 (Ctrl+Espaço passivo, 210 ms) |
| `youtube-verbatim-oracle` | PASS |
| `youtube-1to1-oracle` | GREEN |
| `youtube-monotonic-oracle` | GREEN 14/14 (recuos: antiga 224, nova 0) |
| `undefined-names-oracle` | GREEN (18 ficheiros, 0 nomes indefinidos) |
| `console-window-gate` | PASS (sem janelas de consola nos processos do Sotto) |

---

## 5. O QUE NÃO ESTÁ MEDIDO (e por isso não se afirma)

1. **O flicker com o overlay LIGADO na tela dele.** A janela pós-cura mede o quadro DECIDIDO
   (`YT_FRAME`), não o pixel. O pixel exige a legenda ligada, e ligá-la é gesto dele (a lei
   `SOTTO_NEVER_ON_OWNER_SCREEN` proíbe-me de a pôr no ecrã). Quando ele fizer HOLD no Ctrl+Espaço de
   novo, `EXTERNAL_CAPTION_DRAWN` passa a ter quadros e o mesmo auditor julga-os sem mudar uma linha.
2. **A revelação palavra-a-palavra contra o relógio do player em vídeo A TOCAR**, com esta cura. A
   última medição (4,5 e 15) foi antes dela; `youtube-1to1-oracle` diz GREEN sobre fixtures.
3. **O caminho do ASR** (Parakeet a fundo, Nemotron ao vivo) não foi tocado nesta auditoria.
4. **`youtube-rows-oracle` está RED também em `HEAD`** — é anterior a este trabalho (confirmado com a
   árvore limpa em worktree próprio); não foi tratado aqui.

---

## 6. COMO RE-MEDIR (um comando por pergunta)

```bat
python _main/caption-frame-audit.py --since 23:05:00 --until 23:08:30   :: antes
python _main/caption-frame-audit.py --since 23:19:30                    :: agora
python _main/caption-producer-oracle.py --neg-arm                       :: a guarda ainda guarda?
python _main/undefined-names-oracle.py                                  :: nomes indefinidos
```

O `cProfile` liga-se com `SOTTO_YT_CPROFILE=1` e escreve `_main/_yt-cprofile.txt`; o `YT_PROF` com
`SOTTO_YT_PROFILE=1`. Os dois são opt-in e custam nada quando desligados.

---

# ADENDA 2026-11-03 00:0x — o ESTILO e o FADE (ordem do dono, com captura)

Duas ordens verbatim, sobre a mesma captura de ecra:

> *"ESSE ESTILO DE LEGENDA E' DO YOUTUBE. NAO SOTTO."*
> *"e ta com animacao fade in que eu JA MANDEI VOCE TIRAR"*

## O que mudou

| # | defeito | cura | prova |
|---|---|---|---|
| D8 | a legenda vestia o design do PAINEL (Segoe UI, placa, farol, alinhamento do painel) | `overlay_paint._THEME_DEFAULT` passa a ser o estilo do player: Arial (Roboto nao esta' instalada -- medido em `C:/Windows/Fonts`), branco, contorno preto solido 5 px, sem placa, alinhado ao centro, peso 400, duas linhas. A shell RECUSA os tokens do painel para a janela da legenda (`set_theme(overlay_paint._THEME_DEFAULT)`), e o log diz de onde veio: `brand=theme-1 plate=no fade=no` | `caption-style-oracle` arms 1, 2, 5 + `--neg-arm` |
| D9 | `_normalise_theme` recalculava `align`/`strokePx`/`strokeColor` a partir de tokens que nao existiam, e o tema do YouTube saia `align=left, strokePx=6.08, strokeColor=(0,0,0,235)` | um tema que DECLARA o valor fica com ele; o calculo antigo fica como fallback de quem nao declara | arm 1 (`errado={}`) |
| D10 | fade de entrada na janela inteira (`word_fade`), mais a linha que saia a desvanecer | `NativeCaptionOverlay.FADE_ON = False`: `_fade_alpha` devolve 255 e a linha que sai nao e' desenhada. Sem fade, `_next_delay` deixa de pedir frames intermediarios -- o bitmap so' e' refeito quando o TEXTO muda | arms 3, 4 + `NEG-ARM fade-back` (com o botao ligado o alfa volta a cair: 0 medido, o oraculo apanha) |
| D11 | o ASR pintava por cima do player: medido 00:01:41-00:01:46, `CAPTION_APPLIED "Pra conseguir."` enquanto o YouTube ja' pintava outra frase | `push_caption_to_window` recusa o caminho do ASR enquanto o player fornecer linhas (janela de 2 s), e conta os recusados (`CAPTION_OVERLAY_DROP reason=external-captions dropped=1,10,50,200,...`) | arm 6 |
| D12 | a janela mostrava TRES linhas (`rows=3` medido 00:01:34) | `youtube_window.ROWS_CAP = 2`: fica com as DUAS ultimas, que sao as que o roll-up do player deixa no ecra | `caption-producer-oracle` arm `rows-capped-at-2` |
| D13 | cada relancamento DESLIGAVA a legenda (`_caption_wanted = False`), e um `io.open` num ficheiro que nao importa `io` fazia a restauracao devolver False em SILENCIO | o interruptor grava `_main/caption-wanted.json` e volta no arranque: medido `CAPTION_WANTED_RESTORED on=true` e o primeiro `EXTERNAL_CAPTION_DRAWN` a seguir | log da sessao 00:12:22 |

## O teste que o dono pediu: de 5 em 5 segundos, contra a pagina

`_main/_yt-sync-live.py` le' o DOM do player (`.ytp-caption-segment` + `currentTime`)
e o ultimo quadro do Sotto, e classifica cada ciclo em `SAME` / `OURS-AHEAD` /
`OURS-BEHIND` / `TEXT-DIFF`. **Nao clica, nao da play, nao mexe no volume** -- som
nenhum sai por causa dele.

Primeira leitura (00:12, video EM PAUSA no dono):

| campo | valor |
|---|---|
| `currentTime` | 773,951 s |
| `paused` | true |
| linhas do player | `['maior pra ficar por último, entendeu?', 'Então eles estão acabando,']` |
| ultimo `EXTERNAL_CAPTION_DRAWN` | `['maior pra ficar por último, entendeu?', 'Então eles estão acabando,']` |
| veredicto | `SAME` |

O ciclo de 5 s corre com o video a tocar quando ele o puser a tocar: a pausa mede
o ACORDO dos textos, nao o atraso.

## O que continua por medir

- **O atraso em video A TOCAR** com todas estas curas: a pausa prova o texto, nao a
  cadencia. O ciclo de 5 s fica a correr e junta amostras.
- **A posicao vertical** da legenda: o Sotto desenha 48 px acima da base da area de
  trabalho; o player desenha dentro do video. Nao foi pedido, e nao foi medido.
