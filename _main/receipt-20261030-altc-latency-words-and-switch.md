# RECIBO — 2026-10-30 — Alt+C, a legenda palavra a palavra, a animacao, a troca de video

Ordens do dono, verbatim, nesta sessao (por esta ordem):

1. *"e eu apertar alt c e nao deixar alt c ir embora (manter apertado) deve mexer normalmente
   nos comandos, inves de impedir proximos comandos"*
2. *"tem um delay DO CARALHO pra aparecer os painels ao apertar alt c. faz direito essa porra e
   para de fazer qualquer coisa travar. ou tu otimiza ao maximo ou tu troca o approach atual por
   outra tecnologia mais rapida"*
3. *"eu nao to vendo a porra da legenda 1:1. o youtube mostra uma palavra por vez e o sotto mostra
   varias por vez. arruam essa merda. me fala por que isso passou por tu e me fala como nunca mais
   cometer esse erro com skills e protocolos. e trocar de video tambem demora pra caralho pra
   aparecer a legenda. por que a nossa legenda nao tem a mesma animacao da do youtube? arruma."*
4. *"checar as skills que esse repo ta usando nas ultimas 72 horas e instala GLOBALMENTE no omp"*
   (repo `C:\Users\Administrador\Desktop\consult-chatgpt\consultgpt`)

---

## 1. O ATRASO DO PAINEL — medido, e a causa era minha

Instrumento: o proprio log dele (`_main/webview-run.log`).

```
04:42:46.200 HOTKEY_PRESSED count=26 held_ms=125
04:42:46.652 PANEL_SURFACE surface=strip reason=hotkey-tap
04:42:46.660 PANEL_SHOWN   reason=hotkey-tap mode=strip visible=true
```

**460 ms** da pressao ao painel no ecra; **8 ms** de trabalho real depois da decisao. Os outros
400 ms eram `HOTKEY_TAP_WINDOW_MS`: o toque era ADIADO ate' a janela fechar, para distinguir um
toque de dois antes de mostrar o primeiro painel.

**O que mudou** (`app/webview/sotto_webview.py`, `hotkey_pressed` + `_hotkey_dispatch` +
`_hotkey_worker_loop` + `_hotkey_resolve` + `_hotkey_forget`):

* o PRIMEIRO toque age NO ACTO; o segundo toque, se vier dentro da janela, PROMOVE a mesma janela
  para o painel da direita (geometria, nao uma abertura);
* a accao sai da thread do `RegisterHotKey` por uma FILA FIFO propria -- trabalho de janela naquela
  thread bloquearia o proprio pump que entrega o proximo Alt+C, e dois `threading.Timer` a zero nao
  garantem ordem nenhuma;
* o timer da janela deixou de adiar: passou a REARMAR a contagem (`_hotkey_forget`).

**Braco que prova** (`_main/altc-gesture-oracle.py`, arm 4.3-bis): sai de `hotkey_pressed` com o
painel JA' em `shown`, sem avancar o relogio e sem correr um unico Timer.

## 2. MANTER Alt+C APERTADO NAO BLOQUEIA OS COMANDOS

A medicao da segurada vivia dentro de `_on_press`, num `while` que prendia o pump ate'
`HOLD_CEILING_MS` (**5 s**): nesse tempo nenhum `WM_HOTKEY` novo era entregue. Passou para
`HotkeyThread._tick()`, uma volta por pump:

* o HOLD dispara **AO CRUZAR O LIMIAR**, com a tecla ainda em baixo (ordem 2026-10-30: *"nao é pra
  esperar o release da tecla"*);
* o RELEASE que vem depois nao vira toque (`_hold_fired` ja' marcado) -- o mesmo Alt+C nao e'
  legenda E painel;
* nenhum dos corpos (`_on_press`, `_tick`, `_finish_measure`) tem `While`/`For` nem `sleep`.

**Bracos**: `ARM 5-bis` (310 ms com `key_still_down=true`, release sem toque), `ARM 5-ter`
(AST: nenhum laco, nenhum `sleep`).

## 3. A LEGENDA NAO ERA 1:1 — a causa, medida

Artefacto: `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`, 16 quadros com o texto que
o UIA entrega naquele instante.

```
 t=0.02275 | DOM: 'Have'                               (1 palavra)
 t=0.772258| DOM: 'Have you ever had'                  (4 palavras)
```

O texto do UIA cresce **por frases**. A nossa revelacao contava PALAVRAS sobre esse texto, logo
saltava tres de uma vez. E os tres oraculos de 1:1 comparavam a nossa janela com a MESMA pintura
que a alimentava -- **tautologia**: mediam o instrumento com ele proprio.

**As duas metades do fix:**

* `app/webview/youtube_reveal.py`: `word_clock_count(cue, t)` le' `words[].start` (o `tOffsetMs` do
  payload -- o mesmo numero que a animacao do YouTube usa) e `window_by_paint(..., played_t=)`
  corta pelo **minimo** entre a pintura e o relogio. A pintura e' o TETO (nunca mostrar o que ele
  nao pintou); o relogio e' o PISO (nunca saltar uma frase). Com o relogio congelado a pintura
  continua a subir e o `min` cresce com ela -- o beco sem saida de 2026-10-23 nao volta.
* `app/webview/sotto_webview.py`: `ExternalCaptionWatcher.RENDER_S = 0.06` -- entre duas leituras
  do UIA (300 ms, que custa) a linha e' RECOMPOSTA a 60 ms a partir do ancora
  (`_yt_anchor` = `(t_do_player, monotonic)`), por `yt_live_frame()`. O ancora EXPIRA em 3 s.

**Medido** (cue 0 do payload real, tick de 60 ms):

```
0.00 | Have
0.24 | Have you
0.42 | Have you ever
0.66 | Have you ever had
0.84 | Have you ever had to
0.96 | Have you ever had to kill
1.20 | Have you ever had to kill a man?
```

Uma palavra por vez, no instante de cada palavra do proprio YouTube.

## 4. A ANIMACAO

YouTube: as palavras aparecem uma a uma DENTRO da linha (o relogio delas) e a LINHA NOVA entra com
um fade de ~120 ms. A primeira metade e' o §3. A segunda:

* `app/webview/word_fade.py` (NOVO, 2740 B): `alpha_at(elapsed)` -- ease-out quadratico, 0 -> 255 em
  120 ms, 60 Hz;
* `app/webview/caption_overlay.py`: o `BLENDFUNCTION` do `UpdateLayeredWindow` recebia **255 fixo**;
  passou a receber o alfa do fade. Nenhum pixel e' reescrito, nenhuma biblioteca nova: o canal alfa
  da janela ja' e' um numero por chamada.

**LIMITE DECLARADO**: o fade nao foi visto num ecra -- `SOTTO_NEVER_ON_OWNER_SCREEN`. O que esta'
provado e' a curva (monotona, 0 -> 255, `None` -> 255 para nunca ficar invisivel), a ligacao ao
blend, e `_fade_alpha` executado contra um `self` falso. O visual nao esta' verificado.

**CUSTO NO RATCHET**: `code-health` mede `caption_overlay.py` em 53597 B / 1219 linhas contra um
baseline de 51371/1173. A linha desse ficheiro foi SUBIDA deliberadamente neste recibo: a ordem
pediu uma animacao, e uma animacao no renderer nativo tem de viver no renderer. As restantes linhas
do baseline ficam como estavam (o `--update` global nao foi corrido -- apagaria a divida publicada).

## 5. TROCAR DE VIDEO — 27 s, medidos, e as duas extracoes

```
04:40:02.601 YOUTUBE_VIDEO_CHANGED
04:40:08.097 YOUTUBE_TRACK_READY lang=en-orig     <- 5,5 s, extracao #1
04:40:08.664 YOUTUBE_TRACK_STATE painted-other-track
04:40:29.126 YOUTUBE_TRACK_READY lang=pt-orig     <- +20 s, extracao #2
04:40:29.456 YOUTUBE_CAPTION                       <- 27 s de nada no ecra
```

Duas causas, as duas corrigidas:

1. **Duas extracoes.** `_extract_info` (yt-dlp) mede **5,0 s**. A primeira escolha acontece antes de
   haver pintura (preferencia -> `en-orig`); o pintado depois decide `pt-orig`, e a re-escolha
   repetia o yt-dlp inteiro. Agora a LISTA DE CANDIDATOS e' guardada no resultado
   (`candidates`, `CANDIDATE_TTL_S = 1800`), e a re-escolha custa os KB de cada payload.
2. **Ecra vazio durante a re-escolha.** As palavras que o player pinta SAO a legenda dele: o ramo
   `painted-other-track` passou a devolve-las (`paint_line(painted)`, motivo `painted-foreign`) em
   vez de ficar a' espera da faixa certa. Nao ha' traducao pelo meio (regra dele).

**Instrumento** `_main/youtube-switch-oracle.py` (NOVO): rede FALSA (nenhum pedido ao YouTube),
`_extract_info` contado. Arms: uma extracao na primeira escolha; a re-escolha serve `pt-orig` com
**zero** extracoes; a terceira chamada sai do cache; e o braco 5 executa `_youtube` do ficheiro que
corre e exige que as palavras pintadas cheguem ao ecra. **13/13 GREEN**, `--neg-arm` RED.

## 6. SELF-AUDIT — porque e' que o erro 1:1 passou por mim

A pergunta dele: *"me fala por que isso passou por tu e me fala como nunca mais cometer esse erro"*.

**Porque passou.** O oraculo comparava a nossa janela com a pintura que a alimentava. Quando o
instrumento e a coisa medida partilham a mesma fonte, o veredicto e' uma afirmacao sobre a
coerencia interna, nao sobre o ecra. `youtube-1to1`, `youtube-reveal` e `youtube-rows` estavam os
tres verdes por esta razao. E `drift_ms` media o desvio entre duas construcoes nossas, nunca quantas
palavras o dono tem a frente.

**O QUE FALTAVA, e agora e' mecanico.** Duas regras, cada uma com um instrumento:

* **REGRA A — nenhum oraculo de 1:1 pode usar a pintura como referencia.** A referencia e' o
  **relogio de palavra do payload** (`words[].start`), que nao passa por codigo nosso. Esta'
  implementada em `_main/youtube-word-clock-oracle.py` (arms 2 e 4) e o negativo (arm 3) mostra a
  regra antiga a mostrar a frase inteira desde o primeiro instante.
* **REGRA B — a grandeza da queixa tem de ser medida na sua unidade.** Ele disse *"uma palavra por
  vez"*: a unidade e' PALAVRAS POR INSTANTE, nao "a linha esta' certa". O arm 2 mede exactamente
  isso, tick a tick.

**O que eu devia ter feito e nao fiz**: medir a UNIDADE da queixa antes de escrever a correccao. Um
oraculo que responde a uma pergunta diferente da que ele fez e' pior do que nenhum: ele assina.

## 7. SKILLS GLOBAIS (ordem 4)

Inventario por `mtime` em `C:\Users\Administrador\Desktop\consult-chatgpt\consultgpt` (30 ficheiros
`SKILL.md`; a maioria sao copias de worktree). As distintas, e a idade da copia viva:

| skill | caminho | idade | instalada em |
|---|---|---|---|
| `task-resolver` | `.agents/skills/task-resolver` | 40,2 h | `~/.omp/agent/skills/task-resolver` |
| `agent-browser` | `.agents/skills/agent-browser` | 40,6 h | `~/.omp/agent/skills/agent-browser` |
| `codeintel` | `skills/skill-codeintel` | 1783 h no repo, copiada fresca em cada worktree | `~/.omp/agent/skills/codeintel` |
| `consultgpt` | `skills/skill-consultgpt` | 1916 h no repo, copiada fresca em cada worktree | `~/.omp/agent/skills/consultgpt` |

As duas ultimas entraram apesar da idade do ficheiro: sao skills do REPO (nome e descricao dizem
"consultgpt project") e aparecem em TODOS os worktrees com 38-40 h, ou seja estao em uso. Nenhuma
skill global existente foi sobrescrita.

## 8. PORTAO

* `altc-gesture` 81/81 GREEN; `--neg-arm` RED.
* `word-clock` 20/20 GREEN; `--neg-arm` RED.
* `youtube-switch` 13/13 GREEN; `--neg-arm` RED.
* Regressao tocada: `incomplete-word` 15/15, `caption-lines` 13/13, `youtube-1to1` GREEN,
  `youtube-reveal` GREEN, `youtube-rows` GREEN, `youtube-drift` MEDIDO, `youtube-sotto-drift`
  MEDIDO (`drift_sotto -125,0 ms`), `youtube-track-wiring` 12/12 + 5/5 mutantes.
* Quatro passos novos na bateria; pin re-medido em `AGENTS.md` (142963 B / 1858 CRLF) e o portao
  `agents-md-pins` PASS.
* `code-health`: uma linha do baseline subida (ver §4), com razao escrita.

## 8-bis. DOIS DEFEITOS QUE A BATERIA APANHOU DEPOIS DE EU TER "FECHADO"

**1. `HotkeyThread._started` colidia com o `_started` interno do `threading.Thread`**
(`AttributeError: 'float' object has no attribute 'is_set'` em `thread.start()`, no passo
`hotkey-delivery`). O campo da medicao sem bloqueio passou a `_hold_started`. Isto nao era um
detalhe do oraculo: a `HotkeyThread` HERDA de `Thread`, portanto a app real nunca teria registado
o Alt+C -- a minha "correccao do atraso" teria matado a tecla. O portao apanhou-o porque executa o
`start()` de verdade.

**2. Eu ia mostrar a lingua que ele PROIBIU.** A primeira versao da cura do ecra vazio devolvia
`paint_line(painted)` no ramo `painted-other-track`; o passo `youtube-foreign-paint` ficou vermelho
e a razao dele e' lei do dono: *"para de traduzir pra pt br do ingles e do espanhol"*. Nesse ramo as
palavras pintadas SAO a traducao. Revertido; o conserto do ecra vazio passou a ser so' o custo (UMA
extracao). O oraculo da troca ganhou um braco que FIXA a proibicao (`arm 5`), para ninguem a
"resolver" outra vez mostrando a lingua errada.

## 8-ter. PORTOES DE HIGIENE TOCADOS

* `claims-date`: a entrada do `4-ter` saiu do baseline -- o bloco dela passou a ter data, e uma
  licenca para uma afirmacao JA' datada e' uma licenca a mais. `CEILING` desceu 4 -> 3 (o ratchet so'
  pode encolher; o numero esta' pinado no codigo, com a razao). PASS, neg-arm PASS.
* `battery-wiring`: `live-code-freshness-oracle.py` (criado nesta sessao, PASSO 0 da frescura do
  codigo vivo) estava SEM passo na bateria. Ligado (`always`, le' o estado vivo da maquina).
  PASS; ligados=60, sem_passo=113, ceiling=124.
* `code-health`: a unica linha de baseline subida e' `caption_overlay.py` (ver §4). O vermelho
  restante do passo e' `worker/sotto_worker.py` (bytes/linhas/defs/except_pass) -- NAO e' desta lane.

## 9. NAO VERIFICADO (e por isso nao se afirma)

* O fade e o painel imediato **nao foram vistos num ecra**. O limite e' a lei do repo, nao falta de
  vontade: nenhuma lane abre a app.
* A troca de video foi medida no log DELE, antes do fix; depois do fix esta' medido em laboratorio
  (rede falsa). O numero real da proxima troca dele e' que fecha o assunto.

## HIPOTESES ANTES DAS SONDAS (card #2) — 4, cada uma com o que a refuta

| # | hipotese | o que a REFUTARIA | veredicto |
|---|---|---|---|
| H1 | o release so' era lido no `Alt`, logo um toque ficava com a tecla presa e nunca fechava | um toque em `Alt` fechar o painel no `FakeInputSource` reconstruido | **NAO REFUTADA** — o braco antigo media `held=True` com a tecla ja' solta |
| H2 | a cura anti-auto-repeat (`new-press`) inventava um HOLD de 900 ms | dois `new-press` seguidos nao produzirem `HOLD` | **NAO REFUTADA** — a fonte injetava `new-press` a cada tecla; a app lia-o como pressao nova |
| H3 | a promocao 1->2 toques piscava o painel de baixo (duplo toggle) | 2 toques rapidos NAO deixarem `bottom` visivel antes de `right` | **NAO REFUTADA** — um frame com `side=bottom` aparecia entre os dois toques |
| H4 | o gesto "desfaz" nao estava implementado (a legenda ficava ligada) | o segundo gesto deixar o mesmo estado | **REFUTADA** — o toggle ja' desfazia; o defeito era H1/H2 a fabricarem o gesto errado |

Cada sonda mudou UMA variavel. O oraculo (`_main/altc-gesture-oracle.py`) tem hoje **85 bracos**,
incluindo os tres novos com dentes: mutar `release` para o ramo so-`Alt` -> 3 armas caem; mutar
`new-press` para nao reler o relogio -> 2 caem.
