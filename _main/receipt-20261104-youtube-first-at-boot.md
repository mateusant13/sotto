# Receipt -- a primeira legenda do YouTube chega antes do modelo (2026-11-04)

Lane `YtFirstAtBoot`, branch `lane/yt-first-at-boot`, worktree `H:/sotto-wt/YtFirstAtBoot`
(base `62641ec`). Nada aqui foi medido no ecra do dono: uma lane nao abre janela
(`SOTTO_NEVER_ON_OWNER_SCREEN`) e nenhum comando deste trabalho abre endpoint de audio.

## A queixa, verbatim (terceira vez no dia)

> "é estupido 'carregando o modelo' e nao mostrar instantaneamente as legendas do
> youtube, assim que eu abro o app."

## O que estava a acontecer (medido no arranque do dono, 12:15:15)

    CAPTION_WINDOW_DEFERRED_APPLIED on=true        15.349   superficie da legenda de pe'
    BRIDGE_SPAWNED                                  15.887   worker largado
    EXTERNAL_CAPTIONS_WATCH started                 16.001   observador começa
    CAPTION_PAINT instant=false "carregando modelo…" 16.816  PRIMEIRA pintura da superficie

A superficie existia 1,5 s antes do primeiro estado e a primeira coisa que ela mostrava
era o texto do ASR. A faixa do YouTube nao precisava de nada disso: ela vem do DOM do
player por CDP (`app/webview/youtube_cdp_source.py`, adoptada no arranque desde `79d6976`).

## A ORDEM, antes e depois

`SottoShell.start_caption_pipeline` (chamado em `main()` com `reason=pre-webview`, antes do
WebView2 -- `sotto_webview.py:19681`).

ANTES (`git show 62641ec:app/webview/sotto_webview.py`):

    try: self._yt_cdp_boot_attach()          # porta CDP, solta, sem passo nomeado
    except: log('YOUTUBE_CDP_PREOPEN_FAILED')
    for step, call in (('watcher', ...), ('worker', ...)):
        try: call()
        except: log('CAPTION_PIPELINE_STEP_FAILED step=%s')

DEPOIS:

    steps = (('cdp', _cdp_step), ('watcher', ...), ('worker', ...))     # lista ORDENADA
    for step, call in steps:
        try: call()
        except: log('CAPTION_PIPELINE_STEP_FAILED step=%s error=%r')
    log('CAPTION_PIPELINE_ORDER steps=cdp,watcher,worker')             # a ordem MEDIDA

O worker continua a ser o ULTIMO passo e a sua falha continua a ser um `log` e nao um
`raise` (arm E: o worker levanta e a ordem nao muda). A diferenca que importa nao e' a
sequencia -- essa ja' era `cdp,watcher,worker` no HEAD -- e' que agora ela e' uma
sequencia ESCRITA com uma linha que a torna legivel no log dele:

    CAPTION_PIPELINE_ORDER steps=cdp,watcher,worker

A cura que o dono sente e' outra, e esta' na superficie: nenhum texto de estado passa
enquanto o player fornecer.

## A REGRA, e onde ela mora

1. `player_track_owns(state)` (`sotto_webview.py:1860`, funcao PURA) e o predicado:
   `rows`/`snap_rows` (o DOM do player TEM linhas agora), `epoch` (`_player_frame_seen`:
   uma janela do player chegou ao ecra e nao foi libertada) ou `painted_at` (o player
   pintou ha menos de `PLAYER_TRACK_FRESH_S = 10 s`).
2. `SottoShell.on_worker_loading_text` (`:13879`) e a porta do texto de estado, agora
   ligada a `on_loading_text` na ponte em vez de `push_caption_to_window`. Se a regra
   disser que a superficie e' do player: `CAPTION_LOADING_TEXT_WITHHELD reason=player-track`
   e NADA e' pintado. Sem faixa: `self.push_caption_to_window(text)` -- o caso (c)
   continua honesto.
3. `_player_frame_seen` passa a True em `push_caption_to_window` quando `rows is not None`
   (caminho do player) e a False em `on_external_captions_released` (o player largou).
4. `ExternalCaptionWatcher._release` publica a queda UMA vez por episodio de silencio
   (`_released_for_silence`, rearmado no primeiro quadro servido): o `_tick` com
   `yt_mode=True` e sem linha voltava ao metodo a cada leitura depois de `YT_RELEASE_S` e
   chamava `on_external_captions_released()` em TODOS os ticks seguintes -- worker
   reerguido, ASR a entrar, player a voltar. `last_seen = 0.0` acompanha a queda.
5. `youtube_cdp_source.boot_attach` publica a decisao da aba com o campo `why=`
   (`YOUTUBE_CDP_BOOT_ATTACH ... ok=true reason=playing pick=<id> why=playing`), para o
   log do dono responder "porque e' que aquela aba foi escolhida" sem inferencia.

## O que o oraculo EXECUTA (funcoes reais, nunca regras copiadas)

`_main/youtube-first-at-boot-oracle.py` carrega `app/webview/sotto_webview.py` e
`youtube_cdp_source.py` em importlib e corre:

| arm | o que executa | resultado |
|---|---|---|
| A sem-faixa-o-estado-e-honesto | `start_caption_pipeline` real (worker levanta de proposito) + `on_worker_loading_text` + `push_caption_to_window` + `overlay.set_text` | PASS `painted=True surface=['carregando modelo…']` |
| B faixa-ao-vivo-recusa-o-estado | `ExternalCaptionWatcher._tick(got)` real -> `external_caption` -> `push_caption_to_window` -> `set_text`, depois `on_worker_loading_text` | PASS `withheld=False after_loading=[]` |
| C faixa-ao-vivo-worker-pronto-sem-duplo-pintar | o mesmo com `worker_ready` | PASS `player_paints=1` (uma pintura do player, nenhuma do estado) |
| D sem-faixa-worker-pronto-igual | o mesmo com worker pronto e sem fonte | PASS `surface=['Starting worker... (sotto_worker.py)', 'carregando modelo…']` (inalterado) |
| E ordem-do-arranque | `start_caption_pipeline` com `_yt_cdp_boot_attach`/`start_external_caption_watcher`/`start_worker` instrumentados, worker a LEVANTAR | PASS `events=['cdp','watcher','worker'] source_at_watcher=True worker_fail_logged=True` |
| F queda-da-faixa-uma-so-vez | `_tick([], True)` x3 + `_release('youtube-no-track')` x2 sobre uma faixa que pintou e desapareceu | PASS `releases=1 shell_releases=1 loading_after=1 owns=False` |
| H cinco-abas-uma-a-tocar | `choose_playing` + `probe_tabs` + `boot_attach` contra um servidor `/json/list` falso (WS falso com 2 leituras) | PASS `pick=PLAYINGPLAY why=playing` |
| I duas-a-tocar-decide-e-nao-tropeca | `choose_playing` duas vezes + `previous` fixo | PASS `('AAAAAAAAAAA','playing')` estavel; `previous=BBBB` -> `sticky-last` |
| J nenhuma-a-tocar-nunca-e-ambiguo | `boot_attach` com 3 abas paradas | PASS `no-playing` tres vezes, nunca "ambiguous" |

    $ python _main/youtube-first-at-boot-oracle.py
    YOUTUBE-FIRST-AT-BOOT VERDICT: PASS (9/9)          rc=0

## Os mutantes (`--neg-arm`), sobre uma COPIA do shell

| mutante | mutacao | veredicto |
|---|---|---|
| o-estado-por-cima-da-faixa | `on_worker_loading_text`: `if owned:` -> `if False:` | CAUGHT (arm B/D) |
| observador-depois-do-worker | `steps` -> `(cdp, worker, watcher)` | CAUGHT (arm E) |
| queda-dispara-duas-vezes | apaga `if self._released_for_silence and not had_line: return False` | CAUGHT (arm F, `releases` > 1) |

    $ python _main/youtube-first-at-boot-oracle.py --neg-arm
    NEG-ARM o-estado-por-cima-da-faixa       CAUGHT
    NEG-ARM observador-depois-do-worker      CAUGHT
    NEG-ARM queda-dispara-duas-vezes         CAUGHT
    NEG-ARM: PASS (3/3 mutantes apanhados)             rc=1

As mutacoes sao aplicadas com as terminaçoes de linha do shell (CRLF): a primeira versao
deste braco usava ancoras LF e o `assert` do mutante disparava -- um mutante que nao
aplica e' um mutante que escapa.

## A BATERIA

`_main/_audit-verify-all.cmd`, logo depois do par `youtube-cdp-boot`:

    call :step always youtube-first-at-boot 0 "_main\youtube-first-at-boot-oracle.py;app\webview\sotto_webview.py;app\webview\youtube_cdp_source.py" "%OUT%\youtube-first-at-boot.log" python _main\youtube-first-at-boot-oracle.py
    call :record youtube-first-at-boot !STEP_RC!
    call :step always red-as-expected-youtube-first-at-boot 1 "..." "%OUT%\youtube-first-at-boot-neg.log" python _main\youtube-first-at-boot-oracle.py --neg-arm
    call :expectred red-as-expected-youtube-first-at-boot !STEP_RC! "%OUT%\youtube-first-at-boot-neg.log" "NEG-ARM: PASS"

Veredicto dos instrumentos (corridos nesta lane):

    python _main\battery-wiring-oracle.py   BATTERY-VERDICT battery-wiring PASS checks=7 fail=0
                                            (populacao=226 ligados=115 sem_passo=111)
    python _main\battery-class-oracle.py    BATTERY-CLASS VERDICT PASS -- arms=3 fail=0
                                            (nenhum passo `always` corre um largador; nada abre janela)
    python _main\agents-md-pins-oracle.py   AGENTS-PINS PASS -- 2 pin(s), 0 failure(s)

Pin do AGENTS.md actualizado para `_main\_audit-verify-all.cmd` = **214172 B**, **2656 CRLF**
/ 0 bare LF, sha256 `D016390D5DEA3DAF7460EBEDBBB4E85932760DD1032E13EAC4380B28AB875DE3`, escrito com
`newline=''`.

## Ficheiros, bytes e sha256 (antes -> depois)

| ficheiro | HEAD | agora | bytes |
|---|---|---|---|
| `app/webview/sotto_webview.py` | `dab096736239f1c1` | `82813d9d8439ac4e` | 1061804 |
| `app/webview/youtube_cdp_source.py` | `a2487a46b3ea0914` | `24a32ed7615ce0cc` | 45944 |
| `_main/_audit-verify-all.cmd` | `73485bf7e5146da8` | `d016390d5dea3daf` | 214172 |
| `_main/youtube-first-at-boot-oracle.py` | -- (novo) | `f11f6de6a3f6a813` | 30752 |

## Orfaos nao tocados por esta lane

* `youtube-sync-oracle.py` -- RED (`3.5 o sitio pintado usa a janela revelada pela
  PINTURA`), **identico no HEAD** (`H:/sotto`): pre-existente, nao e' desta cura.
* `youtube-1to1-oracle.py` fica RED num worktree novo so' porque `_cache/` (untracked)
  nao viaja com o worktree: com a cache copiada de `H:/sotto`, GREEN 11/11.
* `code-health-oracle.py` -- RED no HEAD (13 metricas piores, `worker/wasapi_loopback.py`
  entre elas) e RED aqui com 6: o que cresce e' codigo novo
  (`youtube_cdp_source.py` +10 975 B, +262 linhas, +8 `def`s), e a divida de
  `except Exception: pass` NAO cresce -- as duas que a primeira versao deste codigo
  introduziu foram trocadas por `_arm_timeout` / `_drop`, que devolvem um booleano em vez
  de `pass`.

## O que continua UNMEASURED -- e nao e' um veredicto

1. **Uma janela real com uma aba real do YouTube.** Nenhuma lane pode abrir a app no ecra
   do dono, e o Chrome com uma aba a tocar nao existe nesta sessao. As arms usam um
   servidor `/json/list` falso e um WebSocket falso: o que esta' provado e' a DECISAO
   (`pick_playing`, `boot_attach`, o campo `why=`), nao a ligacao a um Chrome verdadeiro.
2. **O relogio de parede do arranque ate' a primeira linha do player** (`time-to-first-
   caption` le o log VIVO e esta' em SKIP sem uma sessao a correr). O que esta' medido e'
   quem pinta primeiro: com faixa, a superficie nao recebe texto de estado nenhum.
3. **A instancia do dono (pid 42548) e' anterior a `fc1fc2f`**; o relatorio dele de
   "loading, depois apanha, depois lento" e' codigo antigo. Esta lane nao o repara nem
   declara reparado.
