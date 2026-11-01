# Recibo - 2026-10-26 - a legenda do YouTube 1:1: o que bate, e o que NAO bate

Brief: `I:\!manager\state\herdr\briefs\20261026-sotto-objective.md`.
Owned paths: `H:\sotto`. Sem commit, sem push, sem screenshot, sem panes novas.

**Estado deste recibo: `executado` com metade medida e metade NAO verificada.** As duas metades
estao separadas abaixo, e a separacao e o ponto do recibo.

## 1TO1

### 1. O que foi comparado, e com que dados (aceitacao 1)

Video nomeado: **`WdaHAGRBB6s`** (o das reclamacoes de 2026-10-22). As duas pontas ficam guardadas
em ficheiro, no repo, com sha256:

| ponta | ficheiro | tamanho |
|---|---|---|
| payload do player (YouTube) | `_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3` | 9304 B, sha256 `9806e76a435a8af8f8f6c98745579e5e14d08f57b6b85c23dc66286b461d67ab` |
| cues servidos pelo Sotto | `_cache/youtube-captions/WdaHAGRBB6s.jsonl` | 3137 B, `lang=en-orig`, `fetched_at=1792791307.5899339` |
| **captura lado a lado** | `_main/fixtures/yt-WdaHAGRBB6s.1to1-capture.json` | 5220 B |
| **relatorio legivel** | `_main/youtube-1to1-report.md` | 677 amostras |

A comparacao e feita **no mesmo instante** e pelo **mesmo codigo de producao**: `parse_json3` +
`youtube_window.live_lines` + `collapse_growth` (a funcao que `sotto_webview.py:2408-2416` chama),
com o payload do player como referencia. 19 linhas desenhadas, 19 cues, 677 amostras a 50 ms.

Resultado de hoje (`python _main\youtube-1to1-oracle.py`):

```
source-is-youtube        GREEN  payload do player=True | cues servidos == parse do payload=True
capacity-from-payload    GREEN  rcRows=2 no payload | o Sotto desenha 2
words-1to1               GREEN  amostras com texto diferente: 0/677
linebreaks-1to1          GREEN  amostras com numero de linhas diferente: 0/677
timing-1to1              GREEN  transicoes do player sem par: 0/19 | a mais: 0/20
word-reveal-1to1         RED    segmentos com tOffsetMs no payload: 69 | offsets nos cues: 0
YOUTUBE-1TO1 VERDICT RED
```

**Qual elemento falha: a REVELACAO PALAVRA-A-PALAVRA.** Nao as palavras, nao a posicao da quebra,
nao o timing. O payload do YouTube traz `tOffsetMs` em 69 dos 106 segmentos -- o player revela a
linha palavra a palavra -- e nenhum cue servido carrega offset, logo o Sotto pinta a linha inteira
de uma vez.

Onde isso nasce, no codigo do caminho vivo: `sotto_webview.py:2287-2307` acaba de ler as palavras
que o player esta a pintar (`painted`, cresce palavra a palavra) e devolve `self._yt_lines(track,
cue.start + 0.001)` -- **o texto inteiro do cue**. O reveal das palavras lidas existe so no ramo
`painted-untracked` (antes do track chegar), por `youtube_window.paint_line`.

### 2. A fonte e o track do YouTube (aceitacao 2)

Prova-se por IGUALDADE, nao por afirmacao, e a igualdade e uma arm do gate, nao uma nota:

1. os cues servidos pela app sao **exactamente** `youtube_captions.parse_json3(<payload do player>)`
   -- `served_equal = True`, medido hoje contra `_cache/youtube-captions/WdaHAGRBB6s.jsonl`;
2. o documento de origem e o do **player**: tem `events` + `wpWinPositions` + `wireMagic` (o
   documento de legendas do YouTube, nao uma transcricao nossa);
3. nenhum modelo de fala entra neste caminho: `parse_json3` le `events[].segs[].utf8`, e o worker de
   ASR nao e importado por nenhum dos modulos da comparacao.

**O que NAO se prova assim:** que o player, na maquina dele, esteja a pintar a MESMA faixa. A cache
diz `player_source=painted-no-match` e `player_match=False` -- na recolha, a faixa pintada nao
coincidiu com a servida. Isso e a metade viva, e ela esta no item 6.

### 3. A regra de lingua (aceitacao 3)

Ao nivel da REGRA, medido hoje: `python _main\youtube-captions-oracle.py` -> **PASS, arms 66/66,
mutants 17/17**, com um caso por lingua:

* `a46` um video INGLES serve a legenda INGLES, nunca a traducao;
* `a47` um video ESPANHOL serve a legenda ESPANHOLA (o "menos espanhol" do dono);
* `a48` um video em PORTUGUES serve a legenda em INGLES;
* `a49` um video em CHINES serve a legenda em INGLES (a traducao);
* `a56`/`a57` a traducao escolhida a mao vence a politica.

**NAO verificado:** os tres casos com um player real a tocar (um en, um pt-BR, um es) -- precisa da
metade viva do item 6.

### 4. Dois arranques a frio com UI real (aceitacao 4) -- **NAO VERIFICADO**

Instrumento que existe: `_main/panel-startup-flash-census.py` (censo a 25 ms) e o passo
`panel-hidden-at-startup-oracle` (que passa hoje: `VERDICT: PASS`, com o braco negativo a apanhar
um `SottoShell` sem `_vram_parked`). Mas:

* o censo precisa da app a arrancar, e o portao de performance **recusou** o lease heavy duas vezes
  hoje -- a segunda com a razao medida `commit-pct=86.2 >= amber 80.0`;
* o proprio AGENTS.md regista uma **contradicao nao reconciliada** neste instrumento (censo de 25 ms
  mede `live` 0/20 com a janela mapeada; o bullet historico mede 18/20). Escolher um lado antes de
  acreditar num dos dois seria inventar um numero;
* e o painel visivel e do dono: `SOTTO_NEVER_ON_OWNER_SCREEN` continua em vigor.

**Input que falta, nomeado:** uma janela GREEN no portao de performance + a palavra do dono para uma
corrida visivel. Sem as duas, nao ha dois arranques a frio medidos por esta lane.

### 5. Alt+C com duplo-toque em 1,5 s (aceitacao 5) -- **NAO VERIFICADO**

Ao nivel da REGRA, medido hoje: `python _main\hotkey-gesture-oracle.py` -> **14/14 GREEN, PASS**
(inclui "uma pressao depois do duplo e um gesto NOVO"). O gesto tem `HOTKEY_DOUBLE_MS` proprio e
`docs/hotkey-gestos.md` fixa a ordem on/off -> painel de baixo -> painel da direita.

**NAO verificado:** o toque real dele. O AGENTS.md e explicito: *nenhum evento sintetico e evidencia
sobre a app* -- `keybd_event`/`SendInput` medem o Windows, e ja foi medido que os quatro `err=0` do
pressionador deram **zero** linhas no log do Sotto. **Input que falta, nomeado:** o dono a premir
Alt+C duas vezes em menos de 1,5 s, com a app a correr; a lane le `panel-state.json` depois.

### 6. O check que fica, e o vermelho mostrado primeiro (aceitacao 6)

`_main/youtube-1to1-oracle.py` -- 6 arms, um mutante por arm, **ligado a bateria**:

```
call :step always youtube-1to1 0 ...            python _main\youtube-1to1-oracle.py
call :step always red-as-expected-youtube-1to1 1 ... python _main\youtube-1to1-oracle.py --neg-arm
call :expectred red-as-expected-youtube-1to1 !STEP_RC! ... "NEG-ARM PASS"
```

**Vermelho, mostrado primeiro**, de duas maneiras:

1. **O defeito real** (acima): `YOUTUBE-1TO1 VERDICT RED`, `word-reveal-1to1` com 69 offsets no
   payload e 0 nos cues. Este passo fica **vermelho na bateria de proposito** -- e o defeito do
   dono, nao uma regressao -- e esta escrito no pin do AGENTS.md para ninguem ler o vermelho como
   quebra.
2. **O caminho historico**, `--path single-cue` (o `cue_at` de um cue so):
   `words-1to1` RED **639/677**, `linebreaks-1to1` RED **639/677**. Ou seja: o check nao e um
   selo que passa sempre -- ele mede o que o dono reclamou e dispara quando o desenho deriva.

Controle negativo: `python _main\youtube-1to1-oracle.py --neg-arm` ->
**`NEG-ARM PASS mutations=7 named-arm-fail=0`** (rc=1 POR DESENHO). Cada mutante mexe UMA ponta:

| mutante | o defeito que injecta | arm que recusa |
|---|---|---|
| `single-cue` | o caminho de um cue so | `linebreaks-1to1` |
| `shift-cue-start` | a linha nova chega 400 ms tarde | `timing-1to1` |
| `mangle-cue-word` | uma palavra a mais | `words-1to1` |
| `join-cues` | duas linhas fundidas numa | `linebreaks-1to1` |
| `one-line-window` | o Sotto desenha 1 linha, o YouTube 2 | `linebreaks-1to1` |
| `stale-served` | os cues servidos sao de outra faixa | `source-is-youtube` |
| `invent-offsets` | offsets que o payload nao declara | `word-reveal-1to1` |

Duas licoes que a primeira versao deste ficheiro pagou, e que ficam no codigo como comentario:
**mutar o payload move as duas pontas** e nao mede fidelidade (a primeira versao fazia isso, e cinco
mutantes saiam "nao apanhados"); e a **janela do YouTube vem do `rcRows` do payload, a do Sotto e
outra variavel** -- se as duas lessem o mesmo numero, o mutante da janela era invisivel.

**A metade "o bloco de render volta":** nao ha check novo para ela; o que existe e
`panel-hidden-at-startup-oracle` (PASS hoje) e o censo de arranque -- que e exactamente o que o item
4 nao conseguiu correr. Entao esta metade da aceitacao 6 esta **meio cumprida**: o check do 1:1
existe e dispara; o check do bloco continua a ser o censo, e o censo nao correu.

### 7. Ligacao e pin (o que a mudanca obriga)

```
battery-wiring  PASS populacao=173 ligados=49 sem_passo=124 ceiling=124
agents-md-pins  PASS 2 pin(s) verificados ao vivo, 0 falhas   (e o --neg-arm: CONTROL PASS)
state-page      PASS passos=130 PASS=77 EXPECTED-RED=26 FAIL=6 STALE=14 NO-VERDICT=5 NOT RUN=2
```

Novo pin de `_main\_audit-verify-all.cmd`: **120510 B**, **1591 CRLF** / 0 bare LF, sha256
`6430978E254777DDE47C01CFE0AC0B45FBEAA0F5ED97681DD5BDA9EDE36A059F` (era 118761 B / 1574 CRLF).

### 8. O que NAO foi verificado -- a lista, sem eufemismo

1. **A metade VIVA do 1:1.** O relay CDP em `127.0.0.1:9224` esta **DOWN** (medido: conexao
   recusada), logo `_main/yt-1to1-live-compare.py` -- que le a janela `.ytp-caption-segment` do
   player a correr -- **nao correu**. O que se mediu foi o payload contra os cues, nao o ecra.
2. **Um payload fresco.** `yt-dlp 2026.08.19` existe e a rede responde (`youtube.com` -> 200), mas o
   extract falha com `Sign in to confirm you're not a bot`; sem cookies nao ha recolha nova. O
   payload comparado e o de **2026-10-22**.
3. **Os tres casos de lingua com player real** (en / pt-BR / es). So a regra foi medida (66 arms).
4. **Dois arranques a frio** (item 4) e **o Alt+C real** (item 5).
5. **A bateria completa depois desta ligacao.** Nao correu: o lease heavy foi recusado (commit
   86,2 %). Os dois passos novos estao `NOT RUN` no registo (`state-page ... NOT RUN=2`), e um passo
   que nao correu nao e um portao que passou.
6. **A revelacao palavra a palavra nao foi corrigida.** O check foi entregue vermelho; o conserto
   exige `parse_json3` a carregar `tOffsetMs`, o poll vivo a emitir a linha a crescer e
   `caption_overlay.set_text` a pintar por offset -- e `sotto_webview.py` esta sob o ratchet de
   `code-health`, que ja esta RED por ficheiros de outra lane.

### 9. Reverter

Apagar `_main/youtube-1to1-oracle.py`, os dois fixtures novos, os dois blocos
`youtube-1to1` / `red-as-expected-youtube-1to1` da `.cmd` e voltar o pin do AGENTS.md a
**118761 B / 1574 CRLF / `F73F330E27F3066EA8EAAB640D83489AD61C0E523CD10EFD05708E634DBF408A`**;
`python _main\sotto-state-page.py --write` regenera a pagina.
