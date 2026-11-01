# Recibo - 2026-10-26 - a revelacao palavra-a-palavra do YouTube, vermelha -> verde

Brief: `I:\!manager\state\herdr\briefs\20261026-sotto-objective.md`.
Owned paths: `H:\sotto`. Sem commit, sem push, sem screenshot, sem panes novas.

Este recibo FECHA o unico elemento que faltava do check 1:1 (`word-reveal-1to1`) e mede o que
fica por verificar no render e no Alt+C.

## REVEAL

### 1. O vermelho, medido ANTES (duas vezes, com o mesmo instrumento)

Com a arm antiga (`_main/youtube-1to1-before.txt`, saida guardada):

```
word-reveal-1to1   RED   segmentos com tOffsetMs no payload: 69 | offsets que os cues carregam: 0
YOUTUBE-1TO1 VERDICT RED
```

A arm antiga contava CAMPOS. Endurecida para medir o DESENHO (o prefixo revelado em cada
instante, contra o prefixo que o payload ja revelou), o mesmo estado deu o numero que importa:

```
word-reveal-1to1   RED   prefixo revelado diferente: 388/677 amostras | segmentos com tOffsetMs
                         no payload: 69 | palavras com relogio nos cues servidos: 0
t=  0.00s (prefixo revelado)
   YOUTUBE: ['Have']
   SOTTO  : ['Have you ever had to kill a man?']
```

388 de 677 amostras com desenho diferente, e a primeira divergencia e a queixa do dono: o
YouTube mostra `Have` e o Sotto mostra a linha inteira de uma vez.

### 2. O que mudou, ficheiro a ficheiro (e o que NAO mudou)

| ficheiro | mudanca | porque |
|---|---|---|
| `app/webview/youtube_captions.py` | `_segs_words(segs, start)` (nova) + `"words"` no cue + juncao em `_absorb_punct` | o cue passa a levar o `tOffsetMs` do payload como instante absoluto de cada palavra |
| `app/webview/youtube_window.py` | `_live_cues`, `revealed_text`, `revealed_lines` (novas) | a janela de duas linhas passa a saber revelar cada linha ate `t`; `live_lines` continua a existir e a devolver o texto inteiro |
| `app/webview/sotto_webview.py` | `_yt_lines` chama `revealed_lines`; `_tick`/`external_caption`/`push_caption_to_window` transportam `instant`; `ov.set_text(..., instant)` | o prefixo ja revelado chega ao overlay e NAO volta a ser sproutado a 45 ms/palavra |
| `_cache/youtube-captions/WdaHAGRBB6s.jsonl` | reconstruida com `words` + `rebuilt_from`/`rebuilt_at`/`rebuilt_note` | a entrada de 2026-10-22 nao tinha relogio; `fetched_at` original preservado |
| `_main/youtube-cache-rebuild.py` | novo instrumento da migracao | recusa escrever quando a entrada antiga nao e, campo a campo, o parse do payload |
| `_main/youtube-1to1-oracle.py` | `--cues served\|parsed`, `revealed_*`, arm `reveal-wired`, 2 mutantes novos | comparar com o que a app SERVE (nao com o parse fresco) e medir as ancoras do caminho vivo |
| `_main/youtube-sync-oracle.py` | a assercao 3.2 passa a exigir `revealed_lines` | a regra mudou; o braco negativo continua a dar RED (verificado) |

Regras que ficaram escritas no codigo, cada uma com o seu porque:

* **sem `words` no cue, `revealed_text` devolve o texto inteiro** — o comportamento antigo, e o
  unico honesto quando o payload nao declara relogio;
* **a revelacao e sempre um PREFIXO do texto do cue**; se a concatenacao das palavras nao for
  prefixo, devolve o texto inteiro em vez de inventar um meio-caminho;
* **nenhuma palavra aparece antes do instante dela** — e o que impede o Sotto de mostrar mais
  do que o YouTube mostra;
* **`_join_segs` continua a ser a unica regra de juncao**: um cue so ganha `words` quando
  `"".join(palavras).strip() == body`, conferido no proprio `parse_json3`.

A reconstrucao da cache RECUSA-SE a escrever quando diverge, e isso foi exercitado:

```
conferido: 19/19 cues iguais em start/end/text
revelacao: 19 cues com relogio, 88 palavras com instante
releitura: cache_read aceita=True cues=19 relogio_em_todos=True stale=False
```

A copia da entrada anterior esta em `G:\Temp\opencode\WdaHAGRBB6s.before-rebuild.jsonl`
(3137 B); a nova mantem `fetched_at=1792791307.5899339` e diz de onde veio.

### 3. O verde, medido DEPOIS (mesmo video, mesmas 677 amostras)

```
source-is-youtube        GREEN  payload do player=True | cues servidos == parse do payload=True
capacity-from-payload    GREEN  rcRows=2 no payload | o Sotto desenha 2
words-1to1               GREEN  amostras com texto diferente: 0/677
linebreaks-1to1          GREEN  amostras com numero de linhas diferente: 0/677
timing-1to1              GREEN  transicoes do player sem par: 0/18 | a mais: 0/18
word-reveal-1to1         GREEN  prefixo revelado diferente: 0/677 amostras | segmentos com
                                tOffsetMs no payload: 69 | palavras com relogio nos cues: 88
reveal-wired             GREEN  ancoras do caminho vivo ausentes: 0/4
SUMMARY elementos=7 vermelhos=0
YOUTUBE-1TO1 VERDICT GREEN
```

Relatorio legivel: `_main/youtube-1to1-report.md`. Captura lado a lado:
`_main/fixtures/yt-WdaHAGRBB6s.1to1-capture.json`.

**Controle negativo: 9 mutantes, cada um recusado pela arm que lhe compete**
(`python _main\youtube-1to1-oracle.py --neg-arm` -> `NEG-ARM PASS mutations=9 named-arm-fail=0`,
rc=1 POR DESENHO):

| mutante | injecta | arm que recusa |
|---|---|---|
| `single-cue` | o caminho de um cue so | `linebreaks-1to1` |
| `shift-cue-start` | a linha nova 400 ms tarde | `timing-1to1` |
| `mangle-cue-word` | uma palavra a mais | `words-1to1` |
| `join-cues` | duas linhas fundidas | `linebreaks-1to1` |
| `one-line-window` | o Sotto desenha 1 linha | `linebreaks-1to1` |
| `stale-served` | os cues servidos sao de outra faixa | `source-is-youtube` |
| `drop-offsets` | o relogio desaparece dos cues | `word-reveal-1to1` |
| `flat-reveal` | todas as palavras ao mesmo tempo | `word-reveal-1to1` |
| `unwired-reveal` | `_yt_lines` volta a `live_lines` | `reveal-wired` |

### 4. Portoes, depois da mudanca

```
youtube-captions-oracle   PASS  arms 66/66  mutants 17/17
youtube-sync-oracle       PASS  checks=11 fail=0   (--neg-arm: RED por desenho)
youtube-window-oracle     PASS  checks=12 fail=0
youtube-paint-first       PASS
youtube-foreign-paint     PASS
caption-native-wrap       PASS  4/4
tooling-intent            PASS  declaradas=13 sem declaracao=160 (ratchet intacto)
battery-wiring            PASS  populacao=173 ligados=49 sem_passo=124 ceiling=124
agents-md-pins            PASS  2 pins + CONTROL PASS
state-page                PASS  passos=130 PASS=47 FAIL=6 STALE=54 NOT RUN=2
```

Novo pin de `_main\_audit-verify-all.cmd`: **120822 B**, **1593 CRLF**, sha256
`6A491D091FC8E68612C06BAC1643A9904E4C4015C2878F8B80F00E86144FD199`.

**Dois portoes continuam VERMELHOS, e os dois por divida que nao e deste trabalho:**

* `exception-hygiene` FAIL — `worker/sotto_worker.py now=8 baseline=7` (medido: e o UNICO ficheiro
  que diverge da linha de base, e e um ficheiro sujo de outra lane, que este trabalho nao toca).
* `code-health` FAIL — ratchet estrutural. Cresceram `sotto_webview.py`, `youtube_captions.py` e
  `youtube_window.py` (as hunks do §2) e tambem `worker/sotto_worker.py`, que nao e meu. A linha
  de base NAO foi subida: subi-la em bloco absorveria a divida da outra lane, e subi-la a mao
  seria ajustar o portao ao resultado. Fica vermelho e declarado.

### 5. O que NAO foi verificado — incluindo um defeito encontrado no caminho

1. **O ecra.** O relay CDP `127.0.0.1:9224` continua **DOWN** (medido hoje), logo
   `_main/yt-1to1-live-compare.py` nao correu. O que esta provado e o DESENHO que o caminho vivo
   produz (`revealed_lines` + as 4 ancoras), nao os pixeis.
2. **A latencia do poll.** `EXTERNAL_CAPTIONS_WATCH` le a cada **300 ms** (`INTERVAL_S = 0.30`),
   e o payload revela palavras a cada 240-400 ms. Logo o prefixo entregue NUNCA esta adiantado,
   mas pode estar **ate um poll atras** (300 ms). Sem a app a correr isto nao se mede.
3. **UM DEFEITO QUE APARECEU AO LER O CAMINHO VIVO, NAO CORRIGIDO:** `_tick` (linha 2474-2475)
   faz `source, lines = got[0]` e depois `line = lines[-1]` -- **a janela de DUAS linhas que
   `_yt_lines` calcula e deitada fora, e so a ultima chega a caixa de legenda**. Ou seja: o
   desenho de duas linhas existe no dado e nao no ecra. Nao foi tocado porque muda o que o dono
   ve e nao ha como o verificar hoje (item 4 abaixo).
4. **Dois arranques a frio.** O portao de performance esta **AMBER** (`commit-pct=86.0 >= 80.0`,
   `heavy_allowed=False`), logo o censo de arranque (`_main/panel-startup-flash-census.py`) nao
   correu. Ao nivel da regra: `panel-hidden-at-startup-oracle` PASS.
5. **O Alt+C real.** Ao nivel da regra: `hotkey-gesture-oracle` **14/14 GREEN**. O toque real do
   dono nao se substitui por evento sintetico (AGENTS.md: `keybd_event`/`SendInput` medem o
   Windows, nao a app).

### 6. Reverter

`_cache/youtube-captions/WdaHAGRBB6s.jsonl` <- `G:\Temp\opencode\WdaHAGRBB6s.before-rebuild.jsonl`;
`_yt_lines` de volta a `live_lines`; retirar `instant` das tres assinaturas em `sotto_webview.py`;
apagar `_segs_words`/`words` de `youtube_captions.py` e as tres funcoes novas de
`youtube_window.py`; apagar `_main/youtube-cache-rebuild.py`. O pin do AGENTS.md volta a
**120510 B / 1591 CRLF / `6430978E254777DDE47C01CFE0AC0B45FBEAA0F5ED97681DD5BDA9EDE36A059F`**.
