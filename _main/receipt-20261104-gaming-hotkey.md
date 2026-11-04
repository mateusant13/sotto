# Recibo — Ctrl+Space em gaming, o nao-roubo de foco, e a deteccao de jogo

Lane: `lane/gaming-hotkey`, worktree `H:/sotto-wt/GamingHotkey` (base `HEAD` = 62641ec).
Data: 2026-11-04.

## A ordem, verbatim

*"e em gaming: control espaço nao da display na legenda. nao faz nada. nem on nem off. fora de gaming:
control espaço nao ativa o espaço em apps. detecta 'gaming' parecido com o que meu projeto !watcher do
disco i faz."*

Tres coisas: (1) em jogo o Ctrl+Space nao faz nada; (2) fora do jogo o Space nao chega `a app; (3)
DETECTAR gaming como o `I:/!watcher`. O que esta' abaixo separa o que foi MEDIDO do que so' a maquina
dele pode provar -- e nao ha' nenhuma linha aqui que apresente `reported` como `verified`.

## Defeito 1 — "em gaming nao da display na legenda, nem on nem off"

### O que o log dele ja' tinha (medido, `_main/webview-run.log` de hoje)

```
2026-11-04 12:13:23.250 HOTKEY_OBSERVER_ALIVE role=live beats=935 loops=236525 max_gap_ms=1703
2026-11-04 12:13:33.362 HOTKEY_PRESSED role=live count=17 source=observed via=state
2026-11-04 12:15:41.627 HOTKEY_PRESSED role=live count=1  source=observed via=state
2026-11-04 12:15:41.628 HOTKEY_LIVE_STEP caption_on=false shown=false wanted=true
2026-11-04 12:16:51.026 HOTKEY_PRESSED role=live count=2  source=observed via=state
2026-11-04 12:16:51.027 HOTKEY_LIVE_STEP caption_on=false shown=true  wanted=true
```

Duas leituras, e as duas importam:

1. **`max_gap_ms=1703`** — a volta do observador chegou a **1,7 s**. Um toque de Ctrl+Space mais curto
   que a volta cai INTEIRO entre duas leituras. E' o medidor que o ticket nomeia, e ele estava (e
   continua) no log.
2. **A pressao E' vista** quando a volta nao esta' presa (`count=1`, `count=2`, `via=state`). O que o
   fio nao controla e' QUANDO ele corre.

### A cura do toque perdido ja' existia; o que faltava era CPU

O bit 0 do `GetAsyncKeyState` (a borda que o Windows guarda) foi instalado a 2026-11-04 e **esta'
provado aqui contra o caso medido**: com o GIL TOMADO por uma chamada C de ~2,7 s (o analogo exacto
da leitura UIA que produziu `max_gap_ms=29266`), a pressao que caiu la' dentro foi entregue:

```
ARM (h2) -- o GIL tomado por uma chamada C (o caso medido: UIA 29 s)
  GREEN a pressao que caiu DENTRO do GIL tomado foi vista (uma, e so' uma)  presses=1
  GREEN a volta ficou presa como no log do dono  max_gap_ms=2719 (o log dele mediu 203..29266)
  GREEN a entrega veio do BIT 0 (via=latched)  ['HOTKEY_PRESSED role=live count=1 source=observed via=latched']
```

O que **nao** existia e foi acrescentado: **a prioridade do fio**. Um jogo e' outro processo -- nao
segura o nosso GIL, mas DISPUTA o CPU, e um fio `NORMAL` perde essa disputa. Agora o observador pede
`THREAD_PRIORITY_ABOVE_NORMAL` (`hotkey_gesture.OBSERVER_PRIORITY = 1`) e PUBLICA o resultado,
medido no Windows, nao prometido:

| | antes (`HEAD` 62641ec) | depois |
|---|---|---|
| `grep -c SetThreadPriority\|OBSERVER_PRIORITY` no shell e no gesto | **0** e **0** | 3 linhas (argtypes + chamada + constante) |
| prioridade lida de volta num fio (`GetThreadPriority`) | `0` (NORMAL, nunca pedida) | **`1` (ABOVE_NORMAL), `ok=True`** — braco (i) |
| linha no log | nenhuma | `HOTKEY_OBSERVER_PRIORITY role=live ok=true priority=1 why=cpu-contention-in-games` |

`TIME_CRITICAL` (15) foi RECUSADO de proposito: tiraria CPU ao shell e ao UI thread por uma leitura
de teclado.

### O caso fullscreen, e porque a pressao nao depende dele

* `PassiveHotkeyThread.run` so' le' `user32.GetAsyncKeyState` -- medido por `ast` no ficheiro:
  `user32` names = `['GetAsyncKeyState']`, e nada mais.
* `_hotkey_resolve` **nao** chama `GetForegroundWindow` nem pergunta `is_gaming()` (dois bracos `ast`
  no oraculo). Logo a janela de um jogo exclusivo -- que e' outra janela, ou outro desktop -- nao
  entra na decisao.
* No painel, o caminho mede o primeiro plano e o log diz o que fez: `FOREGROUND_KEPT reason=no-pointer-lock
  hwnd=21702250 mapped=false` (12:15:43). O `FOREGROUND_KEPT` existe para libertar um *pointer lock*;
  sem lock, nada e' tocado.

## Defeito 2 — "fora de gaming: o Space nao chega `as apps"

### O que foi medido, nas funcoes REAIS, antes e depois

O caminho inteiro do toggle foi executado como o ficheiro o escreve (`_hotkey_resolve` ->
`_set_live_enabled` -> `show_caption_window` -> `NativeCaptionOverlay.show`), com um **GRAVADOR** no
lugar do `user32`: ele registra cada chamada e o valor de cada flag, e nao chama o Windows.

| medicao (efeito, nao texto) | antes (`HEAD`) | depois |
|---|---|---|
| chamadas no toggle de duas pressoes | `SetWindowPos`, `ShowWindow` | identico (o caminho nao foi tocado) |
| `ShowWindow` | `4` (SW_SHOWNOACTIVATE), `0` (SW_HIDE) | identico |
| `SetWindowPos` flags | `83` = `SWP_NOSIZE\|SWP_NOMOVE\|SWP_NOACTIVATE\|SWP_SHOWWINDOW` | identico |
| APIs de primeiro plano (`SetForegroundWindow`, `SetActiveWindow`, `SetFocus`, `BringWindowToTop`, `AttachThreadInput`, `SetWindowLong`) | **0** | **0** |
| APIs que COMEM teclas (`RegisterHotKey`, `SetWindowsHookEx`, `keybd_event`, `SendInput`, `BlockInput`) | **0** | **0** |
| o interruptor | `on, off` (`[True, False]`), overlay mostrado/escondido na mesma ordem | identico |

E a pergunta "quem e' que esta' com a tecla?", medida com o mesmo instrumento da casa
(`RegisterHotKey` + `UnregisterHotKey` imediato, sem janela, o padrao de `_main/_audit-hotkey-probe.py`):

```
Ctrl+Space     register_ok= True  winerror= 0     <- LIVRE: ninguem a tomou
Alt+C          register_ok= False winerror= 1409  <- tomada pela instancia viva do Sotto (panels)
Ctrl+Shift+F12 register_ok= True  winerror= 0
```

**Diagnostico.** O Sotto NAO engole o Ctrl+Space: nao o registra, nao instala hook de teclado, nao
sintetiza input, e o toggle nao move o primeiro plano nem uma vez. `GetAsyncKeyState` LE' o estado e
nao consome nada -- a propria razao pela qual a tecla da legenda deixou de ser registada em 2026-11-02
(*"control mais espaço é crouch e jump no jogo... nao ta funcionando, por causa do sotto"*).

O que sobra, e que este recibo **nao** fecha:

* `Ctrl+Space` nao e' uma combinacao que escreva espaco em NENHUMA app do Windows (o Ctrl esta' em
  baixo). Em apps ele e' um atalho do programa (no Word, "limpar formatacao"), ou nada. Se o dono
  espera um ESPACO no texto, a expectativa e' que nao bate com o Windows -- e nenhuma mudanca no
  Sotto pode produzir esse espaco sem injectar input, que este repo proibe.
* A leitura alternativa da frase dele -- "nao ativa [a legenda] em apps" -- tem uma pista no mesmo
  log: entre as duas pressoes de hoje ha' um `LIVE_ENABLED on=true wanted=true` as **12:15:44.674**
  SEM nenhuma linha `HOTKEY_PRESSED` antes dele, 1,1 s depois de um Alt+C. Ou seja: um segundo
  escritor do interruptor (a pagina, na carga do painel) pode re-ligar a legenda entre duas pressoes,
  e duas pressoes seguidas caem no mesmo estado -- que se ve como *"nem on nem off"*. Nao e' desta
  lane (o escritor e' do painel), fica NOMEADO aqui com as linhas exactas para quem o for fechar.

## Requisito 3 — `app/webview/gaming_mode.py` (novo)

Um tick de **2 s**, UM `CreateToolhelp32Snapshot` (uma enumeracao; zero hooks), e mais nada. Expoe
`is_gaming()` e publica **uma linha por transicao**:

```
GAMING_MODE on=true game="eldenring.exe" why=in-match ticks=1 raw=true dwell_left=11
GAMING_MODE on=false game="" why=dwell ticks=12 raw=false dwell_left=0
```

A verdade e' a do `!watcher`, portada e com as diferencas escritas no ficheiro:

| do watcher | fonte lida hoje | no Sotto |
|---|---|---|
| `GAME_NAMES` (24 nomes, `cs2.exe` .. `deadlock.exe`) | `watcher/games.py:21-45` | copia literal |
| `IN_MATCH_NAMES = GAME_NAMES` / `detect_games` / `primary_game` | `games.py:74,178-228,231` | `detect_games`/`primary_game` |
| cliente (League/Riot) so' conta com foco, streak 3 | `games.py:56-75,198-206` | `CLIENT_FOREGROUND_STREAK_REQUIRED = 3` |
| dwell `game_dwell_ticks = 10` (`config.py:254`, tick `600 ms` -> ~6,0 s) | `models.py:433`, `config.py:245` | `GAME_DWELL_TICKS = 10`, tick 2 s -> **20 s** (declarado: 10 ticks dele × o nosso tick) |
| `gaming = hit.in_match or mode is GAMING` | `engine.py:1223` | `gaming_mode` devolve `in_match` + dwell, sem mood |
| `_gaming_for_mood` (relogio re-armado so' por vista real, `tick - seen <= dwell`) | `engine.py:2398-2416` | o mesmo, e o off-by-one foi corrigido por um braco (ver abaixo) |
| `*-Win64-Shipping.exe` exige `cpu_pct >= 2.0` | `games.py:191-215` | **nao** conta sem CPU medida — a diferenca esta' escrita no topo do modulo |

**O que ele VAI fazer:** responder `is_gaming()`/`game_name()`/`snapshot()` a quem perguntar, e deixar
no log UMA linha por transicao (o dono le' o log; uma linha por tick de 2 s seriam 43 200 por dia).

**O que ele NAO vai fazer:** suspender, parar ou despriorizar o worker, o modelo, o audio, o historico,
ou qualquer projecto; mudar `poll_s` de quem quer que seja. Nao ha' uma unica API de accao no ficheiro
-- medido por `ast` (braco 0): `user32` = `GetForegroundWindow`, `GetWindowThreadProcessId`, e zero
`SuspendThread`/`TerminateProcess`/`SetPriorityClass`/`SetThreadPriority`. O dono pediu para DETECTAR;
ligar isto a um auto-suspender seria uma ordem que ele nao deu.

Fiacao: `arm_gaming_watcher(shell)` no arranque (antes das teclas, e independente de `--no-hotkey`) e
`stop_gaming_watcher` nos dois caminhos de saida. Falhar a arrancar escreve `GAMING_WATCH_FAILED` e a
app vive na mesma.

## O instrumento — `_main/gaming-hotkey-oracle.py`

`ast` extrai do FICHEIRO QUE VAI CORRER os corpos de `_hotkey_resolve`, `_set_live_enabled`,
`show_caption_window`, `NativeCaptionOverlay.show` e a classe `PassiveHotkeyThread`; eles correm
contra um shell falso, um `user32`-GRAVADOR e uma maquina de estados de teclado com a semantica do
`GetAsyncKeyState` (0x8000 = em baixo, 0x0001 = carregada desde a leitura anterior). **Nenhuma janela
e' aberta, nenhum ctypes de input e' tocado, nenhuma tecla sintetica.**

`python _main/gaming-hotkey-oracle.py` -> `GAMING-HOTKEY GREEN -- arms=53 pass=53 fail=0 (rc=0)`

Os bracos: (a) pressao em GAMING e' vista e liga; (b) a segunda desliga; (c) o toggle nao rouba o
primeiro plano (flags medidas); (d) nenhuma API que come teclas, e o observador so' le'
`GetAsyncKeyState`; (e) `is_gaming()` True para jogo nomeado / False para `explorer/python/chrome`, e
o detector REAL nesta maquina nao inventa jogo (521 processos lidos, 0 hits); (f) o dwell mantem True
N ticks e cai no seguinte; (g) o custo do tick; (h) pressao inteira dentro de uma volta perdida por um
laco que come a maquina; (h2) o GIL tomado (2719 ms) e a entrega por `via=latched`; (i) a prioridade
pedida e' a lida de volta.

### `--neg-arm` (muta uma COPIA quatro vezes)

`python _main/gaming-hotkey-oracle.py --neg-arm` -> **rc=1**, ultima linha `NEG-ARM PASS -- RED as
designed: as quatro regressoes derrubam o oraculo`.

| mutante | o que restaura | vermelho em |
|---|---|---|
| `foreground-stolen-on-toggle` | `SW_SHOW` + `SetForegroundWindow` no overlay | (c): `NENHUMA API de primeiro plano` -> `['SetForegroundWindow']` |
| `dwell-removed` | `gaming = raw` | (f): `[False x10]` |
| `in-match-ignored` | `is_game_name -> (True, False)` | (e): `eldenring.exe -> is_gaming()` False, e 6 bracos em cascata |
| `observer-poll-starved` | volta de 1 s e sem o bit 0 | (a)/(b)/(h)/(h2): `presses=0` |

## Medido antes e depois

| medicao | antes (`HEAD` 62641ec) | depois |
|---|---|---|
| `app/webview/gaming_mode.py` | **nao existe** | 493 linhas; `is_gaming()`, 1 linha por transicao |
| oraculo contra a arvore do `HEAD` | `VERDICT: FAIL -- gaming_mode.py ausente` | `arms=53 pass=53 rc=0` |
| prioridade do observador | nunca pedida (0 ocorrencias) | pedida, `1`, lida de volta |
| custo do tick do detector (521 processos) | — (por `OpenProcess`/pid: **29,05 ms**) | **12,32 ms** tipico / 26,8 ms com a maquina carregada (orcamento declarado 50 ms) |
| dwell com a vista fora | — (o primeiro corte deste ficheiro dava 9 de 10 ticks) | **10 de 10**, e cai no 11o |
| `ShowWindow`/`SetWindowPos` no toggle | `4`/`0`, flags `83` | identico |
| APIs de primeiro plano / que comem teclas no toggle | `0` / `0` | `0` / `0` |

## Portoes vizinhos (corridos nesta worktree)

| portao | resultado |
|---|---|
| `_main/gaming-hotkey-oracle.py` | `GAMING-HOTKEY GREEN -- arms=53 pass=53 fail=0` (rc=0) |
| `--neg-arm` | rc=1, `NEG-ARM PASS`, 4/4 |
| `_main/agents-md-pins-oracle.py` | `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)` (`run.cmd --help` 7985 B intacto; bateria `214450 B`, `2666 CRLF` / 0 bare LF, sha256 `626A2922…3EF540013`) |
| `_main/battery-class-oracle.py` | `BATTERY-CLASS VERDICT PASS -- arms=3 fail=0` |
| `_main/battery-wiring-oracle.py` | `BATTERY-VERDICT battery-wiring PASS checks=7 fail=0` (`new-unwired` PASS) |
| `_main/lane-screen-gate.py` | `PASS checks=3 fail=0`; `--neg-arm` 4 mutantes, 4 apanhados |
| `_main/owner-screen-gate.py` | `PASS -- achados=0 <= baseline=0` |
| `_main/console-window-audit.py` | `CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela` |
| `_main/undefined-names-oracle.py` | `GREEN -- 18 ficheiros de producao, 0 nomes usados e nunca definidos` |
| `_main/altc-gesture-oracle.py` | `ALTC-GESTURE GREEN -- arms=96 pass=96 fail=0` e `--neg-arm` PASS |
| `python -m py_compile` nos quatro ficheiros | OK |

O `altc-gesture-oracle.py` recebeu a migracao obrigatoria do cutover: o namespace do observador que ele
injeta passou a fornecer `GetCurrentThread`/`SetThreadPriority`, que o `run` agora chama -- sem isso a
chamada ficava escondida dentro de um `except` e o braco media um caminho que ja' nao existe.

## A correccao de INSTRUMENTO que isto obrigou (`_main/lane-screen-gate.py`)

O portao acusou o oraculo novo de "input sintetico": a regex dele contava as PALAVRAS dentro de um
literal (`KEY_EATING = ('RegisterHotKey', 'keybd_event', ...)`) como se fossem CHAMADAS -- punha
vermelho o ficheiro que existe para provar a ausencia delas. O censo dos `.py` passa a ser por `ast`
(uma CHAMADA injecta; um literal que a nomeia, nao); `.cmd/.bat/.ps1` e um `.py` que nao parseia
continuam pelo texto. O `--neg-arm` do portao continua a apanhar **4 de 4** mutantes.

## Ficheiros mudados

```
app/webview/gaming_mode.py             NOVO -- detector (snapshot 2 s, regra do !watcher, dwell, 1 linha por transicao)
app/webview/sotto_webview.py           prioridade do observador + argtypes; arm/stop_gaming_watcher; atributo self.gaming
app/webview/hotkey_gesture.py          OBSERVER_PRIORITY = 1 (o dono dos numeros da tecla)
_main/gaming-hotkey-oracle.py          NOVO -- 53 arms, 4 mutantes
_main/_audit-verify-all.cmd            passo `gaming-hotkey` + `red-as-expected-gaming-hotkey` (+22 linhas, CRLF)
_main/altc-gesture-oracle.py           namespace do observador: GetCurrentThread/SetThreadPriority
_main/lane-screen-gate.py              censo de input sintetico por `ast` nos .py
AGENTS.md                              pin da bateria re-medido (214450 B / 2666 CRLF / sha256)
```

## O que so' o jogo DELE pode provar (e o que eu nao afirmo)

1. **Que a pressao aparece no ecra dele durante um jogo.** Daqui meco o observador, a decisao e o
   overlay com janelas falsas; nao meco um jogo a correr. Precisa de: `grep HOTKEY_PRESSED
   _main/webview-run.log` com um jogo aberto -- e, no jogo, `HOTKEY_LIVE_STEP` logo a seguir.
2. **Fullscreen exclusivo.** Um overlay `WS_EX_LAYERED|WS_EX_NOACTIVATE|TOPMOST` pode ficar por baixo
   de um jogo em fullscreen EXCLUSIVO (o DWM e' contornado). Se as linhas sairem e ele nao vir nada, o
   proximo passo e' borderless, nao um segundo instrumento -- mas isso e' medicao dele, nao minha.
3. **Aquisicao exclusiva do teclado** por parte de um jogo (DirectInput) pode tornar
   `GetAsyncKeyState` cego enquanto o jogo corre. Se o log dele nao tiver NENHUMA linha
   `HOTKEY_PRESSED` com o jogo em primeiro plano, essa e' a hipotese a atacar em seguida (e a saida
   seria uma segunda leitura independente, nao um hook).
4. **O "nem on nem off" do interruptor.** As duas pressoes de hoje as 12:15:41 e 12:16:51 caíram
   `caption_on=false` porque `wanted=true` nos dois casos, e as 12:15:44.674 um `LIVE_ENABLED on=true`
   apareceu sem pressao. Ate' esse segundo escritor ser fechado, o estado que ele ve' pode ser o
   oposto do que ele acabou de pedir.
5. **A tecla fisica.** Um `keybd_event` mede o Windows, nao a app (AGENTS, medido 2026-10-23). Nenhum
   braco aqui sintetiza um evento, e nenhum o faria valer como prova.
