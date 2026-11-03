# RECEIPT — Ctrl+Space: o interruptor da legenda ao vivo (lane HotkeyLatency-2)

Data: 2026-11-03 · repo `H:/sotto` · lane `HotkeyLatency-2`
Ficheiros mudados: `app/webview/sotto_webview.py`, `_main/altc-gesture-oracle.py`,
`_main/hotkey-live-toggle-oracle.py` (novo).

---

## 1. O caminho inteiro, com ficheiro:linha

Cada elo é do ficheiro que corre hoje (linhas medidas depois das três edições).

```
PassiveHotkeyThread.run()            sotto_webview.py:4959 (classe)
  GetAsyncKeyState (nao consome)     -> borda de descida da combinacao
  log HOTKEY_PRESSED role=live       sotto_webview.py:5035-5036
  self.on_hotkey()  -> hotkey_live   sotto_webview.py:5037
hotkey_live()                        sotto_webview.py:10186  -> _hotkey_dispatch('live')
_hotkey_dispatch(kind)               sotto_webview.py:10199  -> q.put(kind)  (FIFO, sem espera)
_hotkey_worker_loop()                sotto_webview.py:10218  -> _hotkey_resolve(kind)
_hotkey_resolve('live')              sotto_webview.py:10237-10253
  shown = _caption_window_shown      (10247)                 <-- DECISAO (corrigida)
  on = not shown
  log HOTKEY_LIVE_STEP caption_on=.. shown=.. wanted=..
  -> _set_live_enabled({'on': on})
_set_live_enabled(payload)           sotto_webview.py:13026
  _caption_wanted = on               (13059)
  _caption_wanted_store(on)          (13060)  -> _main/caption-wanted.json
  log LIVE_ENABLED on=..             (13071-13072)  <-- AGORA AQUI (era depois da janela)
  show_caption_window(on)            (13076)
show_caption_window(on)              sotto_webview.py:11374
  _caption_window_shown = on         (11381 / 11390)
  _post(_show) / _post(hide)         BeginInvoke, nao espera
  exec_js_post('...data-caption-window, "on"|"off"')   (11412)  <-- NAO ESPERA
  exec_js_post -> _post -> core.ExecuteScriptAsync     sotto_webview.py:9100
```

O que **não** está no caminho: `_read`/`_youtube`/`external_subs` (outra lane),
`_hotkey_queue` a bloquear, qualquer lock, qualquer janela de debounce ou
`Timer` (o pump só entrega, `MOD_NOREPEAT`/borda dão uma entrega por toque).

## 2. Causa medida (duas, ambas com linha de log)

Sessão do dono, `_main/webview-run.log` (lido, nunca escrito):

```
02:43:53.734 HOTKEY_REGISTERED role=panels accelerator=Alt+C thread=53772
02:43:53.736 HOTKEY_OBSERVED   role=live accelerator=Ctrl+Space register=false
02:44:20.679 ... (arranque; CAPTION_WANTED_RESTORED on=true from=2026-11-03T01:05:14)
02:45:08.011 UI_WATCHDOG_STRIKE  strike=1 hwnd=26484292 err=0
02:45:13.955 HOTKEY_PRESSED role=panels count=1 accelerator=Alt+C
02:45:14.415 PANEL_SHOWN reason=hotkey-cycle-strip ... wait_ms=78.0     <- 460 ms
02:45:19.182 POINTER_INTERACTIVE active=true click_through=false
02:45:19.219 LIVE_ENABLED on=true wanted=true panel_closed=false        <- (A)
02:45:24.645 HOTKEY_PRESSED role=live count=1 source=observed           <- A PRESSAO
02:45:24.646 HOTKEY_LIVE_STEP caption_on=false shown=true wanted=true   <- 1 ms
02:45:46.106 UI_WATCHDOG_STRIKE strike=1
02:45:51.917 UI_WATCHDOG_RECOVERED strikes=1
02:45:51.919 LIVE_ENABLED on=false wanted=false panel_closed=false      <- 27,3 s
```

**(A) A acção saía fora de tempo — o UI thread era o relógio do gesto.**
A decisão é instantânea (1 ms), mas a linha `LIVE_ENABLED` da MESMA pressão só
aparece **27,3 s** depois, exactamente entre um `UI_WATCHDOG_STRIKE` e o
`UI_WATCHDOG_RECOVERED` do mesmo intervalo. A causa é uma linha de código:

- antes: `show_caption_window` escrevia a marca do painel com
  `self.window.evaluate_js(...)` (`pywebview/platforms/edgechromium.py:160`),
  que bloqueia em `semaphore.acquire()` **sem limite** até o message loop correr
  o script. O dump de threads do processo confirma o bloqueio:
  `Thread-20x (_call)` → `webview/util.py:264` → `window.evaluate_js` →
  `edgechromium.py:160 semaphore.acquire()`.
- `_hotkey_worker_loop` ficava com o item em execução esse tempo todo, logo uma
  segunda pressão não encontrava a thread pronta, e o `LIVE_ENABLED` vinha
  depois da janela: o log invertia a ordem das acções.

O `LIVE_ENABLED on=true` das 19.219 **não é de uma tecla**: não existe nenhuma
pressão `role=live` antes das 24.645 (`count=1` é a primeira da sessão) e ele
não tem `HOTKEY_LIVE_STEP` ao lado; é a outra porta do mesmo interruptor, a
página (`bridge.setLiveEnabled` → tabela do bridge, `sotto_webview.py:7216`),
37 ms depois de `POINTER_INTERACTIVE active=true` (19.182).

**(B) O interruptor lia a intenção, não o ecrã.**
`_caption_wanted` é restaurado `true` ao arranque com a janela escondida
(`CAPTION_WANTED_RESTORED on=true from=...01:05:14`). Com a decisão a ler essa
flag, a **primeira** pressão de Ctrl+Space da sessão — a única coisa que o dono
fez — "ligava" um interruptor já ligado e **desligava** a legenda:
`caption_on=false` logo depois de o log dizer `on=true`. É esse o
`caption_on=false` que ele lê como "a tecla não liga nada".

## 3. A cura (mínima, sem tocar no caminho da legenda)

1. `_hotkey_resolve` (live): a decisão passa a ler **o que está no ecrã**,
   `_caption_window_shown` — a mesma verdade que o lamp do painel pinta
   (`data-caption-window`). Uma pressão muda SEMPRE o ecrã: arranque com intenção
   ligada e nada na tela → a pressão LIGA; legenda apagada por silêncio
   (`_blank_caption_window`, `shown=false`/`wanted=true`) → a pressão LIGA; ela à
   vista → DESLIGA. `_caption_wanted` continua a ser a condição de
   `push_caption_to_window` e continua a ser gravada em `caption-wanted.json`.
2. `_set_live_enabled`: comita o estado, grava, e escreve **`LIVE_ENABLED` antes**
   de mexer na janela. O que se mede é a acção; o que a janela demora diz-se por si.
3. `show_caption_window`: a marca do painel passa de `window.evaluate_js`
   (bloqueia sem limite no UI thread) para **`exec_js_post`** — o mesmo idioma
   que `emit`/`arm_paint_ack` já usam (`BeginInvoke`, ordem preservada, chamador
   segue). Falha de post continua a deixar linha nomeada
   (`CAPTION_WINDOW_PANEL_MARK_FAILED reason=no-post`).

Semântica preservada: Ctrl+Space comuta a legenda ao vivo (um toque = uma
comutação, sem debounce); Alt+C continua só dos painéis; a tecla é **observada**
(`GetAsyncKeyState`, `PassiveHotkeyThread`), nunca tomada — o jogo continua a
receber Ctrl+Space.

## 4. Instrumento e veredictos

`_main/hotkey-live-toggle-oracle.py` — extrai com `ast` os corpos REAIS de
`_hotkey_resolve`, `_set_live_enabled`, `show_caption_window`,
`_caption_wanted_store`, `exec_js_post` e da classe REAL
`PassiveHotkeyThread`, e corre-os contra um shell falso com o **UI thread
injectado** (`_post` = fila que não corre; `window.evaluate_js` = o bloqueio
real, denunciado em vez de pendurado). A tecla é injectada como sequência de
frames de `GetAsyncKeyState`, portanto o evento entra pela borda de descida da
thread que corre em produção. Nenhuma janela, nenhum ctypes, nenhum input
sintético, nenhum arranque do app.

12 braços, 30 asserções:

```
ARM (a) -- o arranque nao pode gastar a primeira pressao
  GREEN wanted=true restaurado + janela escondida -> a pressao LIGA  wanted=True shown=True
  GREEN HOTKEY_LIVE_STEP diz caption_on=true  ['HOTKEY_LIVE_STEP caption_on=true shown=false wanted=true']
ARM (b) -- com ela a' vista, a pressao desliga
  GREEN shown=true -> a pressao DESLIGA  wanted=False shown=False
  GREEN o overlay recebeu show(False)  [False]
ARM (c) -- 'pigmentos ausentes, interruptor ligado': a pressao faz ver
  GREEN shown=false com wanted=true (blanked) -> a pressao LIGA  wanted=True shown=True
  GREEN o overlay recebeu show(True)  [True]
ARM (d) -- o UI parado nao pode ser a latencia do gesto
  GREEN a pressao devolve em < 50 ms com o UI parado  elapsed_ms=0.0
  GREEN nenhum callable postado tinha corrido na decisao  ran=0 queued=2
  GREEN LIVE_ENABLED saiu NA DECISAO (antes do trabalho de UI)  ['LIVE_ENABLED on=true wanted=true panel_closed=false']
  GREEN o estado ja' comutou quando a pressao voltou  wanted=True shown=True
ARM (e) -- evaluate_js nao e' o caminho do interruptor
  GREEN window.evaluate_js nunca foi chamado  []
ARM (f) -- duas pressoes seguidas, UI ainda parado
  GREEN as duas pressoes comutam para lados OPOSTOS (estado novo, nao cache)
  GREEN depois de dois toques o estado voltou ao inicio
  GREEN as duas decisoes sairam com o UI ainda parado  ran=0 queued=4
ARM (g) -- a pagina e' avisada por POST, na ordem
  GREEN 2 transicoes -> 2 shows + 2 marcas postados  queued=4
  GREEN as marcas dizem on e depois off, na ordem das pressoes
ARM (h) -- o evento vem da thread REAL, com a tecla injectada
  GREEN a classe PassiveHotkeyThread foi extraida do ficheiro
  GREEN dois toques -> dois eventos (a segurada nao repete)  pressed=2
  GREEN cada toque comutou a legenda uma vez, para lados opostos
ARM (i) -- Alt+C continua a ser so' dos paineis
  GREEN role=panels nao escreve LIVE_ENABLED nem HOTKEY_LIVE_STEP
  GREEN o painel apareceu (o ciclo segue o seu caminho)
ARM (j) -- o interruptor sobrevive ao arranque
  GREEN caption-wanted.json gravou on=true  {'on': True, 'at': '2026-11-03T02:53:32'}
  GREEN e a pressao seguinte gravou on=false  {'on': False, ...}
ARM (k) -- a janela falhar nao pode perder o interruptor
  GREEN a pressao nao levanta com o show() a rebentar  None
  GREEN o estado comutou na mesma
  GREEN a falha foi DITA (POSTED_CALLABLE_FAILED), nao silenciada
ARM (l) -- estrutural: a primitiva que bloqueia e a ordem do log
  GREEN show_caption_window nao chama evaluate_js
  GREEN show_caption_window usa exec_js_post
  GREEN LIVE_ENABLED sai ANTES de show_caption_window no codigo que corre  before
  GREEN o interruptor le' o que esta' no ecra (_caption_window_shown)

hotkey-live-toggle GREEN -- arms=30 pass=30 fail=0 (rc=0)
```

`--neg-arm` (muta uma CÓPIA da árvore, três mutantes independentes):

```
=== NEG-ARM le-a-intencao: o interruptor volta a ler `_caption_wanted`
FALHA: wanted=true restaurado + janela escondida -> a pressao LIGA  -- wanted=False shown=False
FALHA: HOTKEY_LIVE_STEP diz caption_on=true  -- ['HOTKEY_LIVE_STEP caption_on=false shown=true wanted=true']
FALHA: shown=false com wanted=true (blanked) -> a pressao LIGA  -- wanted=False shown=False
FALHA: o interruptor le' o que esta' no ecra (_caption_window_shown)
hotkey-live-toggle VERMELHO -- arms=30 pass=25 fail=5 (rc=1)
NEG-ARM le-a-intencao PASS -- RED as designed
=== NEG-ARM espera-pelo-ui: a marca do painel volta a `evaluate_js`
FALHA: window.evaluate_js nunca foi chamado
FALHA: 2 transicoes -> 2 shows + 2 marcas postados  -- queued=2
FALHA: as marcas dizem on e depois off, na ordem das pressoes  -- []
FALHA: show_caption_window nao chama evaluate_js
hotkey-live-toggle VERMELHO -- arms=30 pass=25 fail=5 (rc=1)
NEG-ARM espera-pelo-ui PASS -- RED as designed
=== NEG-ARM log-no-fim: LIVE_ENABLED deixa de sair na decisao
FALHA: LIVE_ENABLED saiu NA DECISAO (antes do trabalho de UI)  -- []
FALHA: cada toque comutou a legenda uma vez, para lados opostos  -- []
FALHA: LIVE_ENABLED sai ANTES de show_caption_window no codigo que corre  -- after
hotkey-live-toggle VERMELHO -- arms=30 pass=27 fail=3 (rc=1)
NEG-ARM log-no-fim PASS -- RED as designed

NEG-ARM PASS -- RED as designed: 3 mutantes derrubam o oraculo
```

## 5. Instrumentos vizinhos

`_main/altc-gesture-oracle.py` (o instrumento de 2026-11-01 das duas teclas)
corria o `_hotkey_resolve` real contra um `FakeShell` que só tinha
`_caption_wanted`; o braço (d) dele passou a ver `[True, True]` porque o fake não
tinha a outra verdade. O fake foi completado (`_caption_window_shown`, escrito
por `_set_live_enabled` do fake), como o shell real faz — o braço (d) voltou a
medir o que diz medir:

```
ALTC-GESTURE GREEN -- arms=86 pass=86 fail=0 (rc=0)
ALTC-GESTURE --neg-arm: NEG-ARM PASS -- RED as designed (2 regressoes)
```

`_main/altc-first-caption-oracle.py` lê o log do dono e emparelha
`HOTKEY_PRESSED role=live` com `LIVE_ENABLED`/`HOTKEY_LIVE_STEP`; a linha
`HOTKEY_LIVE_STEP` mantém o prefixo `caption_on=` (só ganhou campos depois dele),
portanto o emparelhamento não muda — a partir desta cura a `LIVE_ENABLED` sai no
instante da decisão e o número deixa de incluir o stall do UI.

Corrido só para confirmar que não parte (ele próprio lança uma instância de
MEDIÇÃO `--selftest`, que não toma a tecla do dono):

```
ALTC-FIRST-CAPTION VERDICT NO-MEASURE (rc=2)
MEDICAO AUSENTE: nenhuma sessao com pressao nasceu do build que esta' no disco
```

É o veredicto PRÓPRIO dele e não é regressão desta cura: exige uma pressão vinda
de um build que já não está no disco, e a pressão real é a que o dono fizer com a
app viva — este lane não inventa input.

## 6. sha256

```
2f9864f1960d921d1dc14faebc528a8f1ce295a6124c8dba52be151b11fba56e  app/webview/sotto_webview.py
28c22e3ffc92dcd0a7371dc87d66dfe8168fbfec3ed398ed5f1628c84e616bce  _main/hotkey-live-toggle-oracle.py
f4d362693dd7a16812f347d12d95be2ff27b961ff6fe37d6eea8084f81127ee3  _main/altc-gesture-oracle.py
```

(`sotto_webview.py` carrega também trabalho de OUTRAS lanes ainda não commitado —
YouTube/`YouTubeTrackThread`; o hash acima é o do ficheiro inteiro como está no
disco, e as três regiões desta lane são as descritas na §3.)

## 7. Regras respeitadas

- O app vivo **não foi relançado nem morto**; nenhuma janela aberta; nenhum input
  sintético; `_main/webview-run.log` foi apenas **lido**.
- Intactos: `_read`/`_youtube`/`external_subs`/`youtube_*` (outra lane).
- Limite conhecido: o `LIVE_ENABLED` da decisão é o que o instrumento mede; a
  latência até o pixel aparecer continua a ser do overlay/UI (`_post`), e esse
  número não é deste ticket.
