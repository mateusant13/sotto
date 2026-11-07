# RECIBO — rodada 2 do dono (2026-11-07)

Tudo o que se segue foi corrido nesta arvore hoje. Onde esta `PASS` o comando esta ao lado.

## 1. O que o dono pediu, e onde aterrou

| # | pedido (verbatim) | onde aterrou | instrumento | veredicto |
|---|---|---|---|---|
| 1 | *"remove o 'Show in folder'. tem que ser SOMENTE um icone"* | `app/panel/panel.html` (o `<span>` saiu; fica o `<svg>`) + `panel-unified.css` | `_main/panel-header-oracle.js` **ARM 8** | `ARMS: ... 8=3/3`, `VERDICT: GREEN -- 24/24` |
| 2 | *"os dois tem que ficar a direita"* | idem (`justify-content: flex-end` na linha das ferramentas) | idem, ARM 8 | idem |
| 3 | *"tira qualquer frase de efeito ... 'the room, so far'"* | `app/panel/skins/skin-shim.css` (`[data-skin-dead-text]`), marcado por `skin-host.js markDeadControls()` | `_main/panel2-dom-probe.js` | 87/87 |
| 4 | *"falta varios temas q nao foram modificados"* | `app/panel/panel-unified.css` (carrega por ULTIMO) + o shim dentro do shadow root | `_main/panel-history-clip-probe.mjs` | `CLIPPED 0`, `LINE-CLAMPED 0`, `STAMP UNREADABLE 0` em 45 temas |

## 2. O que esta rodada ACHOU e que nao estava a ser pedido

### 2.1 Uma mentira de CACHE em tres passos da bateria (fechada com portao)

Os tres passos que montam o `app/panel/panel.html` REAL declaravam deps incompletas (`panel2-dom-probe`
16, `panel-header-oracle` 11, `panel-history-clip` 9) para uma pagina que carrega **25** assets — e os
tres manifestos de tema (`themes/themes.js`, `themes/panel-designs.js`, `themes/zipc-panels.js`) nao
estavam em nenhuma lista. O `_stepcache` responde HIT pelo fingerprint das deps DECLARADAS: editar um
tema deixaria os tres passos a reimprimir um PASS sobre o ficheiro antigo.

* `_main/panel-deps-oracle.py` (novo): compara as deps declaradas com o `panel.html` real.
  `VERDICT: PASS -- 18/18 arm(s)`; `--neg-arm` → `NEG-ARM: PASS -- o mutante foi apanhado`.
* Duas correcoes de INSTRUMENTO nos proprios neg-arms, ambas medidas:
  * o `page` do oraculo partia outra vez o caminho (`app\panel\panel\themes\...`) e reportava 15
    falhas fantasma — passa a usar o caminho que `panel_assets()` ja devolve;
  * o `replace(..., 1)` do neg-arm apagava o asset de OUTRO passo da `.cmd` e o mutante "passava" —
    o mutante passa a ser escopado a uma linha.
* Passos novos na bateria: `panel-deps` + `red-as-expected-panel-deps`.

### 2.2 O `panel-header-oracle` tinha um mutante que nao podia ficar vermelho

Medido: `order: 5` no lamp APROXIMA-O do pause do lado errado (o vao CRESCE) e a arm ficava verde; um
`width` em `panel.css` perdia a cascata para o `!important` posterior do `panel-unified.css`; e mutar
esse bloco vencedor para 400 px derruba OUTRA arm, nao a do vao. O mutante foi retirado e o estado
honesto ficou escrito no ficheiro: **a ARM 2 passa como medicao POSITIVA e nao tem controlo falso**
(`ARM 2 HAS NO WORKING NEGATIVE CONTROL, AND SAYING SO IS PART OF THE ARM`).

### 2.3 `caption-dup-repro` morria num `AttributeError`

`history_append` passou a chamar `self._history_prune()` (`sotto_webview.py:13475`); o duble do repro
nao tinha o metodo e o laco inteiro morria. O duble agora CONTA a chamada e nao toca no disco: a
limpeza real varre `HISTORY_ROOT` e apaga dias antigos do dono, e um repro de duplicacao nao pode ter
esse efeito. `CAPTION-DUP-VERDICT PASS fases=5 falharam=0`.

### 2.4 O terminal na tela dele vinha da NOSSA corrida da bateria

A queixa de hoje — *"to vendo terminal dar pop up, DE NOVO, na minha tela"* — foi rastreada ao
processo exato pelo watcher: `python _main\youtube-hidden-clock-oracle.py --neg-arm` com o pai
`python step-deadline.py`, avo `cmd.exe`, bisavo `python` da corrida. Mecanismo: um `cmd.exe` sem
consola (largado por uma lane) nao tem como passar `CREATE_NO_WINDOW` a um filho `python`; o Windows
aloca-lhe uma consola NOVA e o Windows Terminal a mostra por ~0,3 s.

**Cura:** as CINCO linhas em que a `.cmd` larga o proprio `python` passam a largar `pythonw`
(`pythonw` nao tem consola nenhuma e o `step-deadline` larga os filhos por `hidden-launch.popen` com
`CREATE_NO_WINDOW`, logo a arvore inteira fica muda). Medido antes de escolher, porque `pythonw` tem
fama de perder o stdout: `pythonw I:..\w2.py > ficheiro` escreve (`FROM-PYW`) e
`pythonw _main\step-deadline.py -- python child.py > log` entrega `CHILD-OUT` no ficheiro — o log do
passo continua a ser a evidencia.

### 2.5 `code-health` absorve o crescimento declarado desta rodada

`--update` medido, diff antes/depois: `panel.js` **encolheu** (213721 -> 211730 B), `panel-unified.css`
e `space_swallow.py` entram como ficheiros novos, `hotkey-hold.css` sai, e crescem `skin-host.js`,
`skin-layout.css`, `strip-drag.js`, `theme-switcher.js`, `gaming_mode.py`, `sotto_webview.py`
(+4 `except_pass`), `youtube_cdp_source.py` — todos com o defeito que esta rodada veio curar.

## 3. O QUE ESTA' VERIFICADO E O QUE NAO ESTA'

* **Verificado por execucao:** todos os comandos citados acima, nesta arvore, hoje.
* **NAO verificado:** nada disto foi visto na TELA do dono. A app viva que ele carrega e' de
  2026-11-07 10:24:53 e o oraculo de frescura diz `STALE` — `python _main/live-code-freshness-oracle.py
  --strict`. Qualquer veredicto sobre o que ele ve' exige reiniciar a app, e reiniciar e' dele.

## 4. A bateria: de 9 passos vermelhos para 3, e o que cada um era

Corrida de referencia nesta sessao (antes das curas deste recibo): `BATTERY-VERDICT: RED - 9 step(s) failed`,
`failed : red-as-expected-youtube-cdp-boot=0 worker-park=1 caption-dup-repro=1 caption-switch-race=1
code-health=2 stall-under-load=1 paint-live-show=1 hotkey-live-toggle=1 strip-surface-oracle=3`.

| passo | causa medida | cura | agora |
|---|---|---|---|
| `caption-dup-repro` | o duble nao tinha `_history_prune`, que o choke point passou a chamar | duble conta a chamada e nao toca no disco | `CAPTION-DUP-VERDICT PASS fases=5 falharam=0` |
| `caption-switch-race` | o mundo do teste nao carregava `_caption_replay_allowed`, que e' `FunctionDef` de topo: `NameError` engolida pelo `except` e o replay nunca corria | o oraculo compila a regra REAL junto do metodo REAL | `GREEN arms=13 pass=13`, `--neg-arm RED as designed` |
| `red-as-expected-youtube-cdp-boot` | a mutacao 3 julgava a regra que NAO decidia (havia duas: `declared-closed` e o override da aba ligada) | o `_adopt_world` isola tres mundos: `stale-list`, `navigated`, `attached-tab` | `VERDICT: PASS (9/9)`, `--neg-arm PASS (6/6)` |
| `worker-park` | a arm P14 plantava um mutante que nunca chegava ao caminho julgado | o mutante passou a mudar o comportamento que a arm mede | `VERDICT: GREEN (15/15)` |
| `strip-surface-oracle` | SEIS pins exigiam um payload `stats` SEM `paused`; o shell carimba `paused` de proposito desde 2026-11-06 | os seis pins passam a incluir `'paused': False`, com o porque escrito no ficheiro | `RC=0`, `broken-copies-red=5 arms=118` |
| `code-health` | crescimento declarado desta rodada | `--update` medido e diffado | `CODE-HEALTH VERDICT PASS` |
| `stall-under-load`, `paint-live-show`, `hotkey-live-toggle` | leem o log da instancia VIVA, que e' de 10:24:53 e o oraculo de frescura chama `STALE` | **nao se curam no codigo**: exigem reiniciar a app | **pendente, e o reinicio e' dele** |

O log vivo mediu, as 10:25:54, `LIVE_ENABLED_FAILED on=true error=NameError("name '_caption_replay_allowed'
is not defined")` -- o processo vivo corre uma mistura de codigo (a chamada tinha aterrado, a definicao
nao). No ficheiro de hoje o nome e' `FunctionDef` de topo em `sotto_webview.py:10706` e o uso em
`:17945`; um `ast` confirma. Nao e' um defeito do codigo em disco: e' a assinatura do `STALE`.

## 5. A queixa de stutter (ordem do dono, 2026-11-07)

*"se a porra da legenda do youtube ta se movendo, mesmo com o stutter acontecendo, a NOSSA legenda que
pegamos do youtube, TAMBEM."*

O que o codigo fazia, medido: `_youtube_time()` extrapolava do ultimo `video.currentTime` da CDP mas
**cortava a extrapolacao em 0,5 s**, com a justificacao escrita de que um renderer adiado nao pode
empurrar a legenda; e a ancora da revelacao tinha o seu proprio teto redondo, `YT_ANCHOR_MAX_S` = 3 s.
Os dois numeros inventavam uma parada que o player nunca disse.

**FECHADO (`app/webview/youtube_clock.py` + `_main/stutter-caption-oracle.py`).** A tolerancia deixa de
ser um numero redondo e passa a ser o ESTADO PUBLICADO pelo snapshot:

|estado que o player publicou|o que a legenda faz|
|---|---|
|`paused=false`, `ended=false`|conta com o relogio de parede ate' `HOLD_S` = 8 s|
|`paused`/`ended` verdadeiros|nao anda um milissegundo|
|campo ausente / sem amostra|serve a ultima amostra e nao adivinha|

O numero de 8 s nao e' o limite da precisao: medido nas 745 amostras REAIS do Chrome dele
(`_main/fixtures/yt-paint-freeze-20261104.json`, janelas 3-8 s, n=60258), o relogio do player anda
1 s por 1 s de parede com deriva de **4,25 ms/s** (|erro| p95 4 ms, maximo 34 ms) -- ou seja, o relogio
sozinho permitiria extrapolar 35 s dentro do orcamento de 150 ms que o contrato pede. O teto e' o risco
de o player ter mudado de estado enquanto ninguem o lia, e esse numero quem marca e' o CONTRATO (1-5 s
de stutter), nao a fisica do relogio. E o que NOS adiantamos e' nosso para desfazer: a primeira amostra
autoritativa que chegue depois de uma extrapolacao descarta-a (`rebase`), com o `eps` separando "isto e'
meu" de "isto e' um seek".

Medido antes/depois pelo proprio oraculo:

|stutter|erro max ANTES|texto mudo ANTES|erro max DEPOIS|texto mudo DEPOIS|
|---|---|---|---|---|
|3 s|2,312 s (4,6x o orcamento)|2,66 s|**0,021 s**|0,70 s|
|5 s|4,411 s (8,8x)|4,66 s|**0,021 s**|1,34 s|

O "texto mudo" que resta ja' nao e' o stutter: e' o passo da palavra dentro do proprio cue (a arm A3
exige `gap <= passo_da_palavra + 1 tick`). `python _main/stutter-caption-oracle.py` -> `GREEN arms=14
pass=14 fail=0 rc=0`; `--neg-arm` repoe os dois tetos numa COPIA e exige A1/A2/A3/A4/A5 vermelhas ->
`rc=1`, `NEG-ARM PASS`. Vizinhanca re-medida verde: `youtube-word-clock` 23/23, `paused-pace` 8/8,
`youtube-monotonic` 14/0, `youtube-hidden-clock` 12/0, `reveal-park` 5/5, `youtube-rate` 7/7,
`caption-lag-budget` 15/15, `code-health` PASS.

## 6. A queixa do TERMINAL na tela dele — e a terceira DM, que NAO e' desta arvore

Duas das tres DMs do watcher apontam para a MINHA corrida da bateria (mecanismo e cura em §2.4).
A terceira — `pythonw.exe(14488)`, `H:\!gravador\tools\nsfw\vigia.py --orcamento 5 --intervalo 180
--lote 5 --tempo-max 300`, `io 86.1MB/s`, `creation=50.7/s` — **nao e' o Sotto**: e' outro projecto
(`H:\!gravador`), com cwd de arranque dentro desta arvore. Nenhum processo deste repo tem esse
command line; o pid nao e' meu e nao o matei.

## 7. A PROVA do painel, e o estado em que ele vai encontrar a app

Nove oraculos do painel, corridos nesta arvore depois do ultimo `git add`:

|oraculo|veredicto|
|---|---|
|`_panel2-dom-probe.js`|87 `[PASS]`, **0 `[FAIL]`**|
|`panel-header-oracle.js`|`GREEN -- 24/24 arm(s)`|
|`panel-drag-targets-oracle.js`|`PASS -- 12 arms, 0 divergentes`|
|`panel-history-clip-probe.mjs`|`STAMP LOUDER THAN TEXT in 0 theme(s)` / `NOT LEFT-ALIGNED rows in 0 theme(s)`|
|`panel-pause-payload-oracle.py`|`VERDICT: PASS -- 5/5`|
|`panel-deps-oracle.py`|`VERDICT: PASS -- 18/18`|
|`theme-switch-oracle.js`|`VERDICT: PASS (0 failure(s))`|
|`theme-preview-oracle.js`|`VERDICT: PASS`|
|`panel-unified.css`|carrega por ULTIMO (`panel.html:95`), depois de `button-contract.css` -- e' ele que nenhum tema pode derrotar|

**O QUE A APP DELE ESTA' A CORRER AGORA NAO E' ESTE CODIGO**, medido com o instrumento do PASSO 0:

```
python _main/live-code-freshness-oracle.py --strict
  pid=23244 started=2026-11-07 10:24:53.155
  processo: sha256=B7582B656F92
  disco   : sha256=787FE71E0244 files=99
  porque  : a etiqueta do processo nao e' a do disco (hash diferente)
  >>> O QUE O DONO CARREGA NAO E ESTE CODIGO.
```

O `STALE` e' esperado: a instancia dele nasceu as 10:24 e a rodada inteira aterrou depois. Nada do
que esta' neste recibo vale como afirmacao sobre o comportamento que ele ve' **enquanto essa
instancia estiver viva** -- e o `LIVE_ENABLED_FAILED NameError` do §4 e' exactamente essa assinatura.
Fechar e reabrir e' a primeira accao de qualquer julgamento do sintoma; uma lane nao larga uma
instancia que detenha `Local\SottoShell`, por isso o reinicio e' dele (ou do `sotto-relaunch.py`,
que reusa o token `high` da instancia viva).
