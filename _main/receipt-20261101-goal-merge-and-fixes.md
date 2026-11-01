# Recibo — goal 2026-11-01, a colheita das lanes e as correcções que eu medi

Data: 2026-11-01, sessão do dono. HEAD de partida `0946aba`; HEAD no fim deste recibo
`981177e` (as lanes seguintes citam o seu próprio commit).

Este documento existe para uma coisa só: dizer **o que foi medido, por quem, com que
comando**, e o que continua **por medir**. `reported`/`fixed` nunca se apresentam como
`verified`: não houve app reiniciada *pelo dono* com teclado *dele*.

## 1. O que entrou por fusão

| lane | commit | o que entrega | conflito e resolução |
|---|---|---|---|
| `lane/goal-yt` | `a667849` | um motor de display para os dois produtores (YouTube e ASR ao vivo) | automática |
| `lane/goal-hotkey` | `f3d860f` | a tela como número; entrega ≠ latência; foco condicional | selftest ficou com a lane; o show ficou com o meu `map_panel`, depois substituído pela lane de pintura |
| `lane/goal-paint` | `41e7bc6` | sem espera de página no show, ack de tinta limitado, foco só com pointer lock | `map_panel`/`pointer_captured` **apagadas** — `pointer_lock_state` já mede o mesmo, e duas definições divergem |
| `lane/goal-load` | `0b8ff8c` | despejo por carga medido contra a instância **viva** | oráculo fica com a lane (seletor, ARM 5b, neg-arm) |
| `lane/goal-profile` | `7e17f70` | recibo de perfil: 9 correcções ordenadas com ganho medido | automática (só ficheiros novos) |
| eu | `f613373` | o primeiro plano do painel passa a ser condicional | — |
| eu | `981177e` | o token de estado paga um `stat`, não 414 KB relidos a cada 2 s | — |

## 2. Números medidos hoje, com o comando ao lado

| afirmação | comando | número |
|---|---|---|
| o painel **não** rouba o primeiro plano | `SOTTO_POV_TAG=main python _main/pov-selftest.py --run --wait 200 --exit-after 45` | `SELFTEST rc=0 broken=false`, `focus_stolen=false focus_stolen_by_own_window=false`, `focus_before=focus_after` |
| o show mapeia sem actuar | idem, linhas `PANEL_SHOWN` | `show=SW_SHOWNOACTIVATE focus=no-pointer-lock paint_ack=true wait_ms=0..62` |
| Alt+C alterna a cada pressão (10 pressões) | idem, arm `ten_press_alternations` | 10/10 na ordem `strip/hide/side/hide…` |
| pressão → acção do gesto | `python _main/altc-first-caption-oracle.py --log I:/cc-tmp/pov-selftest-main.log` | painéis **285 ms**, legenda **8 ms** (orçamento 1500 ms) — instância de medição, **não** o teclado do dono |
| o contrato do gesto tem 86 arms | `python _main/altc-gesture-oracle.py` (+ `--neg-arm`) | `GREEN arms=86 pass=86 fail=0`; neg-arm `RED as designed` |
| o despejo por carga | `python _main/load-shedding-oracle.py` (+ `--neg-arm`) | `GREEN arms=78 pass=78`; neg-arm `RED as designed` (`escolheu=222`) |
| a fila drena tudo | `python _main/live-queue-oracle.py` | `PASS arms=32 fail=0` |
| o alvo da app | `python _main/app-target-oracle.py` | `PASS live=GREEN(9/9)` |
| o veredicto de foco morde | `python _main/selftest-focus-oracle.py` | `PASS` (própria janela RED, controlo estranho GREEN) |
| o hash memoizado invalida | sonda `file_sha256` (hit / reescrita / mesmo tamanho / ausente) | `8ed3f6ad…` = `8ed3f6ad…` → `f144a690…` → `82d81517…` → `None` |

## 3. O que NÃO está provado (e é dito, não escondido)

- **Nada disto é o teclado do dono.** O instrumento posta `WM_HOTKEY`; o input sintético
  não é evidência sobre a app dele (`docs/hotkey-gestos.md`).
- **A primeira exibição depois de um arranque gasta ~342 ms em 20 frames em branco** (lane
  de pintura, censo com 3 536+1 641 frames a 57,3 Hz): é o primeiro *present* do WebView2 no
  processo, não a ordem do shell. As exibições seguintes medem `blank_frames=0`. As duas
  alavancas testadas para o curar (superfície antes do mapa; janela estacionada fora do ecrã)
  **falharam** e foram revertidas — `grep _park_off_screen` → 0.
- **O braço negativo do censo de pintura não fechou.** `--variants uncured` mediu
  `shows=0`: a variante sem a cura nunca completa um show (fica presa), portanto a
  comparação de frames em branco contra a variante má **não existe**; o que existe é o
  defeito a manifestar-se como bloqueio. O censo publica `FAIL (no-show-measured)`.
- **`exec_js TIMEOUT after 10.0 s` continua vivo hoje** (10:33:17 e 10:35:05 no log do
  dono). Está a ser diagnosticado por uma lane com o rasto de stacks (py-spy está negado
  nesta caixa: `Acesso negado (os error 5)`, medido).
- **`nvenc.test.mjs` falha 1 de 5** nesta máquina (`need at least 2 keyframes to measure a
  GOP, got 1`) — o encoder da GPU devolveu um só keyframe no clipe de teste; é ambiente, e
  não foi «corrigido» mexendo no teste.

## 4. Instrumentos corrigidos nesta sessão (e porquê)

1. `_main/pov-selftest.py` — **uma tag por run** (`SOTTO_POV_TAG`): eu e uma lane corríamos
   o mesmo instrumento em duas árvores e ambos escreviam `pov-selftest.log`; o reap de um
   matou a instância do outro (medido 10:25). Agora log, runner **e mutex** levam a tag.
2. `_main/pov-selftest.py` — **reap**: um run cujo `RC=` nunca chega deixava o processo vivo
   (pid 38692, oito minutos, com a `Ctrl+Space` registada — e a app do dono arrancou a seguir
   com `HOTKEY_REGISTER_FAILED role=live winerror=1409`). A identidade é a mutex privada no
   `CommandLine`; o kill delega a um filho `high`.
3. `app/webview/sotto_webview.py` — `SOTTO_LIVE_HOTKEY`: uma instância de medição nunca se
   senta na tecla do dono (o inverso também era verdade).
4. `app/webview/sotto_webview.py` — `focus_steal_allowed` deixou de ser a constante
   `'hotkey'` e passa a ser o que a máquina mede agora (`pointer_lock_state()['clipped']`).

## 5. Disco, no fim

- worktrees **deste** goal removidas depois da fusão: `goal-yt`, `goal-hotkey`,
  `goal-paint`, `goal-load`, `goal-profile` (≈605 MB). Ficam `goal-ratchet`, `goal-bridge`,
  `goal-anim` — vivos, morrem quando as suas lanes fecharem.
- As worktrees anteriores a este goal não foram tocadas: não são minhas.

## 6. Depois das fusões: três nomes usados e nunca definidos (o produto estava partido)

A app do dono estava a correr `BRIDGE_DEATH rc=4 ... captions=0` e **ninguém transcrevia**.
A causa não foi uma lane má: foi a **fusão** de duas lanes que mexeram no mesmo ficheiro.
Nenhum portão da casa apanha isto — `py_compile` olha a sintaxe e a bateria **importa** os
módulos, e um import passa. O que apanhou foi um varrimento novo:

| defeito | onde | porquê é invisível | efeito medido |
|---|---|---|---|
| `REDUX_LIVE_DEFAULT` usado no `argparse` e fora da lista de `from engine_switch import (...)` | `worker/sotto_worker.py` | o nome só é lido quando `main()` corre | `BRIDGE_DEATH rc=4`, `captions=0` |
| `slice_blocks` chamado quando o nome é `_slice_blocks` | `worker/engine_policy.py`, no caminho do **despejo** | a segunda chamada está **dentro** do `except BaseException`, logo o `NameError` sai do handler | worker morto a meio de um lote |
| `_window_is_ours` perdeu a definição (era usada em 2 sítios) | `app/webview/sotto_webview.py` | `NameError` só nasce no tick do `ClickWatcher` | o "clique fora" nunca fechava o painel |

`_main/undefined-names-oracle.py` varre 13 ficheiros de produção, tem `--neg-arm` que
reproduz o defeito de hoje numa fixture (acusa) e par mudo (o par correcto passa); está na
bateria como `undefined-names` + `red-as-expected-undefined-names`.

**Verificação no produto:** `python _main/sotto-relaunch.py --relaunch` →
`pid 25112 GANHOU a mutex`, `saude ... code_id=AB042936B24A`, `LIVE_CODE FRESH`
(processo == disco), `BRIDGE_START reason=preload` e o processo do worker **vivo**
(pid 45272) — o `NameError` do arranque desapareceu. O único aviso vivo é o do áudio:
`BRIDGE_DEATH rc=3 kind=no-audio "Audio tap carried no signal - every candidate device was
flat"`, com o endpoint por omissão medido **não silenciado e a 100 %** — é silêncio de
fonte, não da app.

## 7. O bug que mata o Alt+C de vez em quando não é do Alt+C

`python _main/sotto-relaunch.py --relaunch` **abortou** às 10:56: `kill pid=13120 NAO morreu
em 15 s`. Uma segunda tentativa matou-o em 1 s. O log do mesmo instante tem três
`WARN exec_js TIMEOUT after 10.0s` — a thread da UI presa no bridge. Um processo com a UI
presa não responde ao kill delegado na primeira tentativa. Está a ser diagnosticado por uma
lane (py-spy está negado nesta caixa: `Acesso negado (os error 5)`).

## 7. Um `--exit-after` que nao fechava: a medicao PROMOVIA-SE a app do dono

Medido 2026-11-01 11:14-11:24. O `_main/pov-selftest.py` largava o shell com
`--selftest --exit-after 45` **sem** `--no-self-relaunch`. Resultado: aos 45 s o shell nao
morria -- **re-lancava-se** como a instancia do dono (pid 40064, viva e a escrever
`panel-state.json` seis minutos depois), ja' sem a tag da medicao e a segurar o mutex
`Local\SottoShell`. Uma largada de medicao que se promove a app e' a mesma classe do
incidente que o `reap()` deste ficheiro existe para apanhar, mas por outra porta: o
`reap` so' mata o que ainda tem a tag.

Correccao: a linha do runner passa a levar `--no-self-relaunch`. Prova (o mesmo comando,
tag privada `reap`): `SELFTEST rc=0`, `shell: RC=0`, e o censo de `pythonw` a seguir **nao
tem** o par de processos do run (antes tinha: 46640/44468).

### Censo de fugas (2026-11-01 11:2x)
Sete `pythonw.exe` anteriores (`13604, 25628, 21216, 26064, 54632, 36516, 55956`) existem
na caixa mas **nenhum e' do Sotto**: `grep -c "pid=<n>" _main/webview-run.log` da' **0**
para os sete, e nenhum carrega modulo de `sotto`/`webview`/`onnx`. O unico par que o run
deixou (46640/44468) morreu com a correccao acima. Ou seja: hoje o Sotto nao tem instancia
orfaa -- o pid 40064 e' a app viva e fresca do dono (`live-code-freshness --strict`:
processo sha256 == disco sha256, `Alt+C` e `Ctrl+Space` com `register=true`).

## 8. O gargalo que fazia as legendas chegarem a 1,15/s: `emit` era um round-trip de 10 s

Lane `lane/goal-bridge` (recibo dela em `_main/receipt-bridge-stall.md`), mesmas sondas antes
e depois numa instancia privada:

|medida|antes (300 s)|depois (600 s)|
|---|---|---|
|`exec_js TIMEOUT after 10.0s`|42 (todos `status=WaitingForActivation`, `continuation=unset`)|0|
|legendas entregues|346 (1,15/s)|1875 (3,13/s, o ritmo do feeder)|
|`EMIT_DROPPED` / `PLACEHOLDER_DROPPED`|0 / 0|0 / 0|

Causa: as TRES chamadas de `emit` do produto sao notificacoes (ninguem le o valor) e todas
passavam por `exec_js` SINCRONO com orcamento de 10 s; `apply_panel_state` pagava-o DUAS
vezes por status. Candidatos refutados com numero: pool esgotado (nao ha pool -- um Thread
por chamada), promessa JS que nunca assenta (o `ExecuteScriptAsync` nao espera promessas),
UI thread bloqueado (`marshal_ms=0.0` em 37 de 42), host WebView2 ceifado (as respostas que
chegaram 1-8 s depois provam que estava vivo).

Cura: `emit` -> `emit_nowait`/`_post` (sem orcamento, ordem preservada, recusa escrita) e o
placeholder tambem postado. O instrumento (`BRIDGE_CENSUS`, `SOTTO_BRIDGE_CENSUS=1`) passou
a `app/webview/bridge_census.py` -- o `py-spy dump` esta NEGADO nesta maquina (`os error 5`),
logo as stacks saem de dentro com `sys._current_frames()`.

## 9. Portoes do load/resume, corridos hoje neste HEAD

    load-shedding-oracle    GREEN -- arms=78 pass=78 fail=0
    live-queue-oracle       PASS  -- arms=32 fail=0        (nenhum audio fica por transcrever)
    external-resume-oracle  PASS  -- bracos: 8 verdes, 0 vermelhos

## 10. A paridade do YouTube, re-corrida neste HEAD (2026-11-01 11:3x)

Oito portoes, cada um pelo seu comando, ultima linha de cada:

    youtube-1to1-oracle          GREEN
    youtube-monotonic-oracle     GREEN -- 14 PASS / 0 FAIL (recuos: antiga 224, nova 0)
    youtube-reveal-oracle        rc=0, reveal-matches-the-player GREEN 15/15,
                                 cobertura PARCIAL 15/16 (1 amostra sem alinhamento de 3 palavras)
    youtube-rows-oracle          GREEN
    youtube-drift-oracle         MEASURED (rc=0) -- n=16 mean_ms=+172.5 median_ms=+107.2
    youtube-sotto-drift-oracle   MEASURED (rc=0) -- drift_sotto mean_ms=-125.0 median_ms=-74.0
    youtube-paint-first-oracle   PASS
    youtube-switch-oracle        GREEN -- arms=12 pass=12 fail=0

`drift_ms` e' MEDIDO, nunca booleano, e as duas distribuicoes sao de instrumentos
diferentes: `youtube-drift` compara a NOSSA linha com o relogio do cue; `youtube-sotto-drift`
compara o nosso overlay com o PLAYER. A cobertura PARCIAL nao e' um verde: 15 de 16 amostras,
e a que falta nao tem alinhamento de 3 palavras para julgar.

## 11. Um harness de browser que conduz o YouTube de verdade (existe, medido 2026-11-01)

`I:/vod-rip-wt/done/wt-asrsup/e2e/tests/preview-mse-direct.spec.ts` -- Playwright, com
`const YT_URL = 'https://www.youtube.com/watch?v=4kyvGbRpV7M'` e um `openYoutubePreview(page,
url)` que escreve o URL num campo e carrega. Nao e' do Sotto e nao e' copiado para ca: o que
fica registado e' que a caixa TEM um caminho de browser automatizado para um video do YouTube,
se um dia a prova de ponta a ponta precisar de um player real em vez do payload.

O que o Sotto usa hoje, e que corre verde neste HEAD, e' o payload real + o relogio do player:
`youtube-sotto-drift-oracle` (nosso overlay contra o `currentTime`) e `youtube-1to1-oracle`
(677/677 palavras com `tOffsetMs`).

## 12. P1 fechado: a app viva e os instrumentos (2026-11-01 11:28-11:4x)

    python _main/sotto-relaunch.py --relaunch --tag main:bridge-cure-1ae1ff6
      kill pid=46972 via token(fonte=14040) ok=True -> mutex livre
      CreateProcessAsUser(fonte=14040) ok=True err=0 filho=33464
      pid 9572 GANHOU a mutex
      saude: {'log': True, 'mutex': True, 'code_id': 'A21E04974C7F', 'hotkey': True, 'tray': True, 'webview2_failed': False}

    python _main/live-code-freshness-oracle.py --strict
      LIVE_CODE FRESH pid=9572 processo sha256 == disco sha256 (files=7)
      HOTKEY_REGISTERED role=panels accelerator=Alt+C     register=true one-press-one-step
      HOTKEY_REGISTERED role=live   accelerator=Ctrl+Space register=true one-press-one-step

Instrumentos do POV em uso: `_main/pov-selftest.py` (instancia privada, token herdado,
`--selftest` empurra o WM_HOTKEY na fila da propria app -- nenhum input sintetico),
`app/webview/selftest_instrument.py` (leitura do ecra + trace de foco),
`_main/panel-paint-first-census.py` (censo de frames blank/content por SHOW),
`app/webview/bridge_census.py` (`SOTTO_BRIDGE_CENSUS=1`, stacks de dentro quando o ponte nao
responde -- `py-spy` esta' negado nesta caixa, `os error 5`), `_main/sim/panel-sim.html`
(simulacao 1:1 do painel+overlay quando a superficie real nao pode ser conduzida).

## 13. Censo de fugas na instancia viva (2026-11-01 11:28-11:40)

**Processos.** Depois do relancamento ha UM processo do Sotto: pid 9572 (o que ganhou
`Local\SottoShell`). Sete `pythonw.exe` antigos continuam na caixa e **nenhum e' do Sotto**:
`grep -c "pid=<n>" _main/webview-run.log` da' **0** para os sete, e nenhum carrega modulo de
`sotto`/`webview`/`onnx`. O par que a minha medicao havia deixado (46640/44468) morreu quando
o `pov-selftest` passou a levar `--no-self-relaunch` (seccao 7).

**RAM.** pid 9572 a T+17 min: `WorkingSet64 = 164 MB`, `PrivateMemorySize64 = 123 MB`.

**O churn do worker esta' CAPADO, e o cap foi visto a funcionar ao vivo.** Quatro mortes por
silencio em 10 minutos e a quarta **nao** reiniciou:

    11:30:33 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=15000
    11:33:09 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=30000
    11:35:48 BRIDGE_RESTART reason=exit ladder=no-audio in_ms=60000
    11:38:59 BRIDGE_RESTART_SUPPRESSED reason=exit ladder=no-audio no_audio_restarts=3 cap=3
             why=restarting-cannot-fix-a-routing-problem resume=press-Alt+C

Ou seja: a regra que o AGENTS.md cita (*"o worker morre e recarrega ~1 GB de modelo 88 vezes em
17 minutos"*) esta' de facto fechada -- tres recargas com escada 15/30/60 s e depois o shell
PARA e diz ao dono o que conferir. O par de 2 s que existe no log e' de 10:50, o laco de
`NameError: REDUX_LIVE_DEFAULT` de ANTES da cura, nao do codigo de hoje.

## 14. Disco: o que o goal ocupou, e o que sobrava de OUTRAS sessoes (2026-11-01 12:0x)

Antes -> depois, medido com `df -h`:

    I:  3.7T  3.6T  45G  99%   ->  60G livre   (+15.3 GiB)
    H:  517G  482G  36G  94%   ->  36G livre   (worktrees do goal removidos: 538 MB)
    G:  239G  182G  57G  77%

O que saiu:
- `H:/sotto-wt/{goal-ratchet,goal-bridge,goal-bridge-before,goal-shellsplit}` -- worktrees
  DESTE goal, ja' fundidos, removidos com `git worktree remove --force` + `prune` (os dois
  ainda vivos, `goal-battery` e `goal-noblank` com as lanes a correr, ficam ate' elas fecharem);
- `I:/cc-tmp/aud.csv` **9.1 GiB** -- um dump de eventos (ETW/WPR) de 2026-10-15, com uma
  cabeca `Event Name,Type,Event ID,...`: um artefacto de analise, nao uma fonte;
- `I:/cc-tmp/runtime-state-copy.sqlite` 3.1 GiB e `I:/cc-tmp/rs-liveness.sqlite` 3.1 GiB --
  copias derivadas de 2026-10-07, com 25 dias.
Ficaram por tocar `I:/cc-tmp/rea-lane` (8.1 GiB) e `I:/cc-tmp/cronfix2` (3.2 GiB): nao sao do
Sotto e nao sei o que sao -- um `rm -rf` de uma arvore alheia nao se faz por conveniencia.

O `.git` do Sotto mede 8.0 GB (pack 4.66 GiB) e NAO cresceu com este goal: `git log --diff-filter=A
-- '.codeintel/*'` da' **0**, e os maiores blobs da historia sao `app/panel/skins/cinematic-2/img/
38663879.png` (2.5 MB) e `_moved/aireplay/_main/_nv-cdx-inventory.txt` (2.3 MB) -- nenhuma arvore
de GB entrou.

## 15. O custo de pintar uma linha de legenda: 3,83 -> 0,72 ms (lane `goal-anim`, `5e38c4c`)

Instrumento: `_main/_lane-profile-paint.py --themes theme-5 --arms reduced,on` (6 s de janela) e
`_main/_anim-cost2.py` (p50). Numeros medidos pela lane, dois runs por braco:

|medida|antes 1 / 2|depois 1 / 2|
|---|---|---|
|push mean|3,83 / 3,47 ms|**0,72 / 0,70 ms**|
|push max|38,5 / 158,4 ms|5,8 / 13,8 ms|
|LoAF blocking (com animacao ligada)|**186,7 ms** / 0|0 / 0|
|`anims total`|30|4|

Tres mudancas: (1) `panel.css` -- o reveal passou a ser scoped ao `[data-typing]` (so'
`theme-1/2/4/5.css` o punha em TODOS os spans, portanto 26 reveals ja' acabados eram
re-aplicados a cada restyle); (2) `followNewestLine()` deixa de escrever layout dentro do push
(um rAF por frame, depois o pin); (3) o pin passa a recordar o `scrollHeight` que apontou, para o
`wireFollow` nao se desarmar do nosso proprio lag de um parcial -- **reproduzido 2/2** no theme-4
(50 px por linha contra a tolerancia de 48) e corrigido.

O LOOK e' o mesmo, provado e nao afirmado: `_main/_anim-timeline-diff.py` sobre registos por frame
(theme-1/4/5) da' "THE LOOK IS THE SAME", e a diferenca fica quantificada -- a cauda era apanhada a
opacidade 0,42-0,93 com blur 0,88 px por parcial antes, e fica a 1,00 depois.

## 16. O POV do dono agora, lido pelos proprios instrumentos (2026-11-01 12:19)

`python app/webview/panel_state.py --read` na instancia viva (pid 50132, `SHELL_CODE_ID
sha256=54D789DEA953 files=39`, fresco):

    namedState    = no-audio
    placeholder   = title='No audio to transcribe'
    endpoint      = 'Mixagem estéreo (Realtek HD Audio Stereo input)' api=None from='done'
    noAudio       = True evidence='done verdict=silent-device'
    deaths        = 4 spawns=4 captions=0

E a escada de dispositivos do worker, no mesmo ficheiro:

    11:52:29 .. 11:53:41   STATUS_APPLIED "device-rotated (flat)"  (8 rotacoes)
    11:53:57  BRIDGE_STATUS_NOAUDIO state="device-exhausted" kind=no-audio
              text="Audio tap carried no signal - every candidate device was flat"

Ou seja: naquele minuto a caixa nao tinha audio em endpoint NENHUM que o worker tentasse -- nao e'
o worker a perder a rotagem, e' a escada a fazer o trabalho dela e a parar. O caminho de volta
existe e e' o documentado: Alt+C -> `_start_deferred_worker('show-panel')` volta a tentar, e o
estado publicado diz ao dono o que conferir. Nada aqui contradiz os gates: `load-shedding`,
`live-queue` e `external-resume` estao verdes neste HEAD.
