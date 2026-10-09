# Recibo — a FAIXA (strip) e o MODO DE EDIÇÃO

Lane: `app/webview/sotto_webview.py` (só este ficheiro). Data: 2026-10-08.
Ficheiro no fim da lane: ver §9 (tamanho/sha256).

O dono, verbatim, sobre o Alt+C: **"alt c > abre embaixo. passo o mouse encima >
aparece mais botoes"**. E a decisão já registada no painel
(`app/panel/surface.js:6-8`): o Alt+C abre uma **FAIXA CURTA**, não o painel de
380x900. Metade disto existia (o painel); a metade da shell nunca tinha sido
escrita — `grep -n 'surface|strip' app/webview/sotto_webview.py` não tinha UMA
implementação. É o que esta lane escreveu.

---

## 1. TAREFA A — `bridge.setPanelSurface(surface, reason)`, o membro que faltava

**Contrato**, no mesmo sítio de `getInfo`/`onCaption`/`onStatus`:

```js
window.sotto.setPanelSurface(surface, reason) -> true|false   // 'strip' | 'panel'
window.sotto.getStats()                       -> {peak, blocks}   (id round-trip)
window.sotto.onStats(cb)                      -> unsubscribe
```

* `surface` é validado por `normalise_surface_name` (`'strip'`/`'panel'`); um nome
  desconhecido é **recusado** com `PANEL_SURFACE_REFUSED` e devolve `false` — nunca
  é adivinhado. (`_main/_strip-surface-oracle.py` tem esse braço.)
* `panel.js:1239-1248` (`openFullPanel`) chama `bridge.setPanelSurface('panel',
  reason)` e só cai no fallback de layout se a chamada não existir. **Existe agora.**
* A ordem é DOCUMENTO primeiro (`exec_js` espera), HWND depois, para a janela nunca
  mostrar o CSS de uma superfície com o tamanho da outra.

O `dispatch` é **accionado**, não procurado por texto: o oráculo chama o
`SottoHost.dispatch` real com o fio real (`{"kind":"panel-surface", …}`) contra uma
shell de stand-in que registra o que lhe foi pedido — uma entrada de dicionário que
nenhum código alcança passaria num teste de texto.

**Provas (todas medidas):**

| o quê | onde |
|---|---|
| `PRELOAD_ACTIVE … methods=17` (antes 14) | `_main/_strip-surface-probe.json` arm A |
| dispatch roteia `panel-surface` → `set_panel_surface(surface, reason)` | oráculo, braço accionado |
| o COPY sem o membro vai **RED** nesse membro | oráculo, controlo 1 |
| o COPY sem a entrada de routing vai **RED** no braço accionado | oráculo, controlo 2 |

---

## 2. TAREFA B — a geometria da faixa, em números

**O ecrã dele, medido** (`_main/_strip-work-area-probe.ps1`, P/Invoke
`EnumDisplayMonitors`/`GetMonitorInfoW`):

```
DPI=96 scale=1  monitors=1  device=\\.\DISPLAY1 primary=True
monitor=[0,0 1920x1080]  work=[0,0 1920x1032]     (1032 + 48 = 1080: a barra de tarefas)
cursor=(1013,600)  monitor_at_cursor=65537  primary_monitor=65537
```

**A faixa nesse ecrã** (a MESMA linha que a shell escreve, `WINDOW_GEOMETRY`):

```
WINDOW_GEOMETRY reason=surface-strip ok=true last_error=0
                window=1040x150@(440,834) docked=bottom-centre
OUTSIDE_CLICK_PROBE shown visible=true armed=true rect=(440,834,1480,984)
```

* `width = min(1040, max(480, round(work.width*0.62)))` → **1040** em 1920.
* `height` → **150**, e NÃO é uma constante nesta shell (ver abaixo).
* `x = work.x + (work.width-width)//2` → **440** (centrada).
* `y = work.y + work.height - height - 48` → **834**; a base é 984, ou seja 48 px
  acima do fundo da **área de trabalho** (1920x1032), que é o que limpa a barra de
  tarefas.

**A proposta da lane anterior foi CONFIRMADA, com uma correcção vinda da lane do
painel: a ALTURA.** Eu tinha escrito `148` (a partir do "~150 px" de
`panel.css:1527`, que é um comentário). A lane do painel mediu o número real e
declarou-o em `:root`:

```
panel.css:52   --strip-height: 150px;
panel.css:53   --strip-chrome: 78px;
panel.css:44   (documenta o shell a lê-lo com getComputedStyle)
panel.css:1060 grid-template-rows: minmax(calc(var(--strip-height) - var(--strip-chrome)), 1fr) auto auto;
```

**Regra aceite: o CSS é a ÚNICA fonte de verdade da altura; a shell lê-a em tempo
de execução.** Não há `148` nem `150` escrito na shell como valor de operação —
`STRIP_HEIGHT_FALLBACK = 148` só é usado quando a página não consegue responder, e
**cada uso é registado como fallback**. O caminho usado foi o **runtime**, no
momento em que a faixa é aplicada (a página já está carregada; antes da primeira
pintura não é preciso, porque a janela é criada na geometria do painel e só muda
no show):

```
STRIP_HEIGHT from=148 to=150 source=css css_value=150 extra=0 reason=surface-probe-outside-click
```

`set_strip_height(height, reason)` continua a existir como a mudança de runtime: em
vez de substituir o CSS, registra uma **adição** (`strip_height_extra`, hoje 0), e a
janela mede `css + extra`. Nada o chama hoje — ver §7.

**Multi-ecrã: NÃO medido, e digo o que sei.** Esta caixa tem **1 monitor**, portanto
não há como medir. O que o código faz (inalterado): `primary_display()` usa
`MonitorFromPoint(POINT(0,0), MONITOR_DEFAULTTOPRIMARY)` — a faixa abre no monitor
**PRIMÁRIO**, **não** no do cursor. Numa máquina com dois monitores isso é uma
decisão por tomar, não um resultado medido: `cursor=(1013,600)` e
`monitor_at_cursor=65537` são iguais ao primário *aqui*, o que não prova nada sobre
lá.

**Mudança de resolução: NÃO medido** (não há como mudar a resolução desta caixa).
A mitigação existe e está medida por outra via: a geometria guardada é **limitada à
área de trabalho actual** no arranque, com UMA linha de log quando move algo (§3).

---

## 3. TAREFA C — o modo de edição (mover a faixa)

**Entrada: só o menu do tray.** `TRAY_MENU [1]='Open panel' [3]='Edit caption
position' [sep] [2]='Quit Sotto'`. O id 3 chama `set_edit_mode(not self.edit_mode,
'tray')`; o mesmo item sai.

* **Movimento:** `make_click_through(hwnd, False)` + remover `WS_EX_NOACTIVATE`,
  e `SetWindowPos` a **baixa frequência** — o arrasto corre na thread do
  `OutsideClickWatcher` que já existe (≤2 threads, orçamento respeitado), o hook só
  compara e faz `PostThreadMessageW`, e o movimento acontece no message loop dessa
  thread com um **mínimo de 50 ms entre amostras** (`EDIT_DRAG_MIN_INTERVAL_MS`).
  `docs/release-and-overlay-plan.md:75-78` é a razão: mover a janela nativa por
  frame pisca.
* **Persistência: o ficheiro que JÁ EXISTE.** `_main/panel-visibility.json`, chave
  `geometry` — **não um segundo ficheiro** (dois ficheiros deixariam a shell e o
  poll do worker a discordar sobre qual é autoritativo). O `schema` continua
  `sotto.panel-visibility/1` porque nenhum campo foi renomeado nem removido, e o
  leitor do worker (`PanelVisibilityReader`) lê `visible`/`writtenAtEpoch`/
  `staleAfterSeconds` e ignora o resto — lido, não assumido.
* **Restauro: limitado à área de trabalho actual**, uma vez, com uma linha quando
  move.

**Medido (arm D de `_main/_strip-surface-probe.py`, janela NUNCA vista —
`form.Opacity = 0`, e nenhum rato físico é movido):**

```
PANEL_EDIT_MODE on=true  reason=tray surface=strip click_through=false noactivate=false
                         rect=(440,834,1480,984) hint=drag_the_band
PANEL_EDIT_PROBE outside_click_while_editing closed=false visible=true decision=edit-mode
PANEL_EDIT_GEOMETRY_SAVED surface=strip window=1040x150@(700,400) moves=1 work=1920x1032@(0,0)
PANEL_EDIT_PROBE file_geometry={"surface":"strip","x":700,"y":400,"width":1040,"height":150,
                                "docked":"edited","workWidth":1920,"workHeight":1032}
                file_pid=4324 file_schema="sotto.panel-visibility/1"
PANEL_EDIT_MODE on=false reason=tray moves=1 … click_through=true noactivate=true
```

**Restauro + limitação, medido** (`_main/_strip-restore-probe.py`; a chave é
semeada logo a seguir a uma escrita da shell do dono, para ganhar a janela de 3 s,
e o ficheiro original é **reposto no fim**):

```
in-bounds : PANEL_GEOMETRY_RESTORED surface=strip rect=1040x148@(700,400) clamped=false
off-screen: PANEL_GEOMETRY_RESTORED surface=strip rect=1040x148@(880,884) clamped=true
            PANEL_GEOMETRY_CLAMPED  surface=strip was=1040x148@(5000,5000)
                                    now=1040x148@(880,884) work=1920x1032@(0,0)
```

Repare no `148` do restauro: é um **rect guardado pelo dono**, e um rect guardado é
honrado como está (a altura do CSS é o valor por omissão, não uma camisa-de-forças
sobre uma escolha explícita dele).

---

## 4. TAREFA D — `getStats`/`onStats`, a onda, E O ORÇAMENTO DE LOG

Payload **exactamente** `{peak, blocks}`, ambos `float`, tirados do
`WORKER_STATS` do próprio worker (`last_worker_stats['fields']`). Um campo que o
worker não imprimiu fica **ausente** — nunca 0 —, porque `panel.js:1641` recusa um
`peak` não finito: ausente significa "sem medição". `queue_drops`/`rate` (o chip
"behind", `panel.js:1738`) **não são fabricados**: esta shell não os calcula.

**A entrega é na cadência do worker, e a PUSH não espera.** `on_worker_stats` é
chamado uma vez por linha `WORKER_STATS` — ou seja, uma vez por AMOSTRA do
medidor. Duas consequências, e as duas foram tratadas:

* **`emit_async`** (novo): o `emit` normal bloqueia num `Task[String]`. Quem chama
  `on_worker_stats` é a thread do pump que lê o **stderr do worker — a MESMA que
  entrega as legendas**. Um round trip por amostra atrasaria as legendas, portanto
  a push usa `_ui` (`BeginInvoke`, sem espera) e larga o `Task`. A ordem entre duas
  pushes não é garantida e não precisa de ser: cada uma leva o payload INTEIRO.
* **O LOG É AGREGADO, O DADO NÃO.** Uma linha por amostra é um log sem limite — e
  foi um log sem limite que fez o medidor do worker ser DESLIGADO. Agora:
  a PRIMEIRA push é registada, e depois no máximo **uma linha a cada
  `STATS_LOG_INTERVAL_S = 30 s`**, cada uma com o número de amostras que
  representa (`in_window_s=`, `rate_hz=`). O painel continua a receber TUDO.

**Medido, as duas cores num só comando** (`_main/_strip-stats-log-probe.py`; o
controlo é um COPY da shell de hoje com a agregação revertida, e o worker de
stand-in publica a **20 Hz** — a forma de um medidor a sério):

| braço | linhas de log | **bytes de log da feed / minuto** | amostras ENTREGUES |
|---|---|---|---|
| por amostra (o defeito) | 467 | **98 605 B/min** (~96 KB/min) | 467 |
| agregado (a correcção) | 1 | **290 B/min** | **476** |

**340× menos log, com a feed INTEIRA** (476 pushes entregues contra 467 do
controlo — a agregação não descarta uma única amostra). O log inteiro do braço
agregado cresce 2 346 B/min, e isso são as linhas periódicas da própria shell
(`PANEL_VISIBILITY_MODE`, `PANEL_STATE_WRITER`), não a feed.

**Medido ponta a ponta com um worker de stand-in** (`_main/_strip-stats-worker.py`,
que **não abre dispositivo de áudio**) — `_main/_strip-stats-probe.py`, os dois
lados num só comando:

```
fed   (--with-worker): BRIDGE_STATS_PUSH count=1 payload={"peak":0.443448,"blocks":812.0}
                       BRIDGE_STATS_REPLY id=s1 count=1 payload={}   (o POLL do painel)
                       DOM do painel: data-level="live", barras --meter-h 0.443 ×10
                       contador do próprio painel: __sotto_emit.counts = {stats:4, geometry:1, status:2}
unfed (--no-worker)  : data-level="none", barras vazias,
                       __sotto_emit.counts = {geometry:1, status:1}  (SEM chave `stats`)
                       e o poll CONTINUA a ser respondido com {} — ausente não vira zero
```

**Porque é que o contador `__sotto_emit.counts` existe:** o medidor é alimentado
por DUAS vias — o poll de 1000 ms e a push — e um `data-level="live"` sozinho não
distingue uma push a funcionar de um poll a fazer o trabalho todo. O contador
separa-os, e é o painel a dizê-lo.

O `SHELL_EXIT` passou a levar `statsPushes=`/`statsReplies=`: como a push só é
registada uma vez por intervalo, um arranque curto nunca mostraria quantas
amostras a feed levou — e esse é exactamente o número que impede alguém de
"resolver" um log grande desligando o dado.

---

## 5. O DEFEITO QUE ISTO APANHOU — `SetWindowPos` + `HWND_TOPMOST` (erro 1400)

A faixa **mudava de largura e não se movia**: ficava em `(1528,66)` (a posição do
painel) com o tamanho da faixa.

```
antes:  WINDOW_GEOMETRY reason=surface-strip ok=false window=1040x148@(440,836)
        PANEL_EDIT_MODE on=true … rect=(1528,66,2568,214)
```

Causa, provada pelo código de erro e não por palpite: `user32.SetWindowPos` estava
sem `argtypes`, portanto o ctypes marshala cada `int` Python como um `int` C de 32
bits e `HWND_TOPMOST` (-1) chegava a um parâmetro `HWND` de 64 bits como
**0x00000000FFFFFFFF** — handle inválido. `last_error=1400`
(`ERROR_INVALID_WINDOW_HANDLE`), com o TAMANHO ainda aplicado.

```
depois: WINDOW_GEOMETRY reason=surface-strip ok=true last_error=0 window=1040x150@(440,834)
        PANEL_EDIT_MODE on=true … rect=(440,834,1480,984)
```

A correcção é a assinatura declarada (`user32.SetWindowPos.argtypes`, 7
argumentos) e está **afirmada no oráculo**, não confiada. **Consequência lateral,
dita por ser verdade:** o `set_topmost()` que já existia usava a mesma chamada e
**falhava em silêncio** desde sempre (não registra nada); agora passa a funcionar.
Ninguém tinha notado porque a janela já nasce *always on top* pelo pywebview.

---

## 6. O QUE O Alt+C ABRE AGORA, EXACTAMENTE

| gesto | superfície | janela |
|---|---|---|
| **Alt+C** (e o fallback de hotkey) | **faixa** | 1040x150@(440,834), aplicada **enquanto está escondida** |
| Alt+C outra vez | esconde (a janela fica no tamanho da faixa) | — |
| tray → `Open panel` | **painel** | 380x900@(1528,66) (o `dock_right` de sempre) |
| `--show` | **painel** | 380x900@(1528,66) — inalterado, byte a byte |
| botão "Open panel" da faixa (`panel.js:1239`) | painel | 380x900@(1528,66) via `setPanelSurface` |

O Alt+C está **fixado** à faixa: mesmo que ele tenha aberto o painel a partir da
faixa, o Alt+C seguinte dá-lhe a faixa curta outra vez (não o painel que acabou de
deixar). `--show` e o tray pedem o painel **explicitamente**. A mudança de tamanho
acontece no caminho do *show*, com a janela ainda escondida — é o único momento em
que um `SetWindowPos` não pode piscar, e é por isso que nenhuma outra medição da
casa mudou de números.

---

## 7. O QUE NÃO ESTÁ FEITO, E O QUE NÃO FOI MEDIDO

1. **O crescimento por hover NÃO está ligado.** O dono disse *"passo o mouse encima
   > aparece mais botoes"*: os botões a aparecer são CSS do painel (`:hover`), e a
   metade da shell é `set_strip_height()`, que existe e está medido como função mas
   **nada o chama**. Não o liguei porque (a) quem revela os botões é a lane do
   painel, e (b) crescer a janela num hover é um `SetWindowPos` numa janela
   VISÍVEL — um por transição, não por frame — e não foi medido contra o reveal do
   CSS. **É a única metade da frase dele que fica por fazer.**
2. **`--show` não foi medido no ecrã** (mostraria uma janela na secretária dele, o
   que é proibido). O que existe: a chamada passa `surface='panel'` explicitamente
   e o oráculo afirma isso; e a superfície aplicada não muda quando já é a pedida,
   portanto não há redimensionamento nenhum.
3. **`--selftest` não foi corrido** — ele mostra a faixa, e isso é uma janela na
   secretária dele.
4. **Multi-ecrã e mudança de resolução: não medidos** (§2).
5. **Um restauro real entre arranques não foi observado com uma chave que o dono
   tenha escrito**: a shell dele (pid 28428, revisão anterior) reescreve
   `panel-visibility.json` a cada 3 s **sem** a chave, e apagou a minha logo a
   seguir. Medido, textualmente: depois do arm D, o ficheiro lia
   `pid=28428 … geometry=null`. **A chave só sobrevive quando ele reiniciar com
   esta shell** — e é aí que o restauro (§3) passa a valer.
6. **A bateria `_main\_audit-verify-all.cmd` foi tocada depois** (decisão do pai,
   §12): os cinco instrumentos desta lane entraram nela como passos
   `:record`/`:control`, com o ficheiro a permanecer **CRLF**. O `AGENTS.md`
   também foi escrito (bloco aditivo, §12).
7. **O modo de edição não foi exercitado com um rato físico** — por desenho: a
   amostra de arrasto é postada no message loop real da thread do watcher
   (`PostThreadMessageW`), que é exactamente o caminho que o hook usa, menos a
   entrega do movimento pelo SO. O `edit_grab` fica `None` (ninguém carregou no
   botão), portanto o teste move a ORIGEM da faixa para o ponto, não com o offset
   do cursor.
8. **Um modo de medição não pode pendurar-se** — regra aprendida aqui: uma excepção
   a escapar de um callback de `threading.Timer` morre num stderr que o `pythonw`
   não tem e deixa uma shell **escondida viva para sempre** (medido: um
   penduramento de 70 s). `run_edit_mode_probe`/`run_stats_probe` escrevem a
   excepção no LOG e saem num `finally`, e o oráculo afirma esse `finally`.

---

## 8. INSTRUMENTOS (com o custo desta lane)

| instrumento | o que prova | comando |
|---|---|---|
| `_main/_strip-surface-oracle.py` | contrato JS, dispatch accionado, geometria, clamp, menu do tray, chave `geometry`, altura lida do CSS, orçamento de log — **+ 4 controlos negativos** | `pythonw.exe _main\_strip-surface-oracle.py` → `GREEN`, e cada COPY vai RED no que lhe falta |
| `_main/_strip-surface-probe.py` | a shell a correr: 4 braços (A Alt+C aplica a faixa; B censo de janelas a 100 ms; C menu do tray; D modo de edição) | `pythonw.exe _main\_strip-surface-probe.py` → `GREEN` |
| `_main/_strip-restore-probe.py` | o restauro da geometria guardada e a limitação, e que o ficheiro fica como estava | `pythonw.exe _main\_strip-restore-probe.py` → `GREEN` |
| `_main/_strip-stats-probe.py` | `getStats`/`onStats` a alimentar a onda (com o contador de push do painel), **com o controlo sem worker** | `pythonw.exe _main\_strip-stats-probe.py` → `GREEN 15/15` |
| `_main/_strip-stats-log-probe.py` | o orçamento de log da feed, **antes/depois**, a 20 Hz, com o COPY por-amostra como controlo | `python.exe _main\_strip-stats-log-probe.py` → `GREEN`, `STRIP-LOG CONTROL PASS ratio=574.8x` (460 linhas/83 405 B·min⁻¹ vs 1 linha/145,1 B·min⁻¹, 440 pushes entregues) |
| `_main/_strip-work-area-probe.ps1` | a área de trabalho real e o monitor | `pwsh -File _main\_strip-work-area-probe.ps1` |
| `_main/_strip-stats-worker.py` | worker de stand-in (cadência por `SOTTO_STANDIN_HZ`): **não abre dispositivo de áudio** | usado pelos dois instrumentos acima |

**O custo, medido com `GetProcessTimes`/`GetProcessMemoryInfo` (nativos, sobre
handles já abertos — WMI nenhum, passeio de processos nenhum):**

* `_strip-surface-probe.py`: processo do probe **0,188 s de CPU / 21,3 MB**; as 4
  shells somam **3,329 s de CPU**, ~**110 MB** de pico cada, 6,5–11,5 s de relógio.
* `_strip-stats-probe.py`: probe **0,031 s**; shells **1,563 s**.
* Censo de janelas: `EnumWindows` **dentro do próprio processo**, a **100 ms**, e só
  durante os 8 s do braço B (~80 amostras) — nunca em contínuo.
* Todos os 16 arranques desta lane passaram `--no-worker`: os 16 logs dizem
  `WORKER_AUTOSTART=declined reason=no-worker` → **nenhum carregamento de modelo,
  nenhum tap de áudio**.
* Nenhuma janela foi mostrada em nenhum braço: o braço B é um censo de 100 ms sobre
  a própria árvore de pids e deu **0 amostras visíveis**; os braços A e D usam
  `form.Opacity = 0` (visível para o Windows, invisível para o dono) e o braço C
  passa `--exit-after` sem mostrar.

---

## 9. ESTADO FINAL

`app/webview/sotto_webview.py` — os meus próprios bytes terminavam em **389 256 B,
sha256 `C4E04600BF1E4D96…`**, e o ficheiro está agora em **397 180 B / sha256
`EA014D8F2CACD72E…` (7 199 linhas)** porque **outra lane lhe acrescentou bytes
depois**. Compilado `python -m py_compile` → rc 0, e **todos os marcadores desta lane
continuam presentes**: `_arm_exit_watchdog` `:3115`, `run_hover_probe` `:5426`,
`set_panel_surface` `:4659`, o ramo `meter` `:6843`, `_stats_log_maybe` `:5009`,
`strip_height_from_css` `:4572`, `WorkerReloadPolicy` `:6178`. A revisão anterior
deste recibo dizia 348 088 B / `9AB7FBC9F76E2980…` — **os dois números ficaram
stale**; o vigente é o de cima, e vale a regra 2 do `AGENTS.md`: **quando se cita uma
revisão, cita-se o sha256.** `app/panel/**` **não foi tocado** (nenhuma variável CSS
nova foi precisa: `--strip-height` já existia). `worker/**` e `run.cmd`: intocados. A
bateria `_main\_audit-verify-all.cmd` e o `AGENTS.md` **foram tocados por decisão do
pai** (§12).

**Resolvido desde a primeira redacção deste recibo:** (b) os instrumentos já estão
na bateria; (c) a linha do `AGENTS.md` sobre o `SetWindowPos`/`HWND_TOPMOST` já
existe, com o resto do bloco. **Continua pendente para o pai decidir:** (a) ligar o
crescimento por hover (§7.1) — não ligado, e agora medido (§11).
---

## 10. O DEFEITO DO HOT RELOAD — *"e tu estás a correr código antigo"*

O dono disse isto, e era verdade. **20 QUEUED / 20 DEFERRED / 0 APPLIED / 0
respawns** desde que o worker dele arrancou às 08:01:56: cada pedido de reload era
adiado, nunca aplicado. Causa: o GUARD de adiamento pergunta `is_capturing()`, que é
verdadeiro sempre que o worker está a capturar — e um worker com áudio a tocar
**nunca pára**, portanto a fronteira nunca chegava. O dono correu código com horas
e reportou bugs já corrigidos.

A correção é uma **política com ordem**, não um if. `WorkerReloadPolicy`:

| passo | constante / regra | porque |
|---|---|---|
| 1 DEBOUNCE | `WORKER_RELOAD_DEBOUNCE_MS = 2000` | não recarregar por cada byte escrito |
| 2 GUARD | nunca a meio de uma captura (`WORKER_CAPTURING_STATES = {'capture-started'}`) | não partir uma linha no meio |
| 3 FRONTEIRA | esperar por uma linha que o WORKER **FECHOU** (`final:true`) | o boundary é do worker, não do relógio |
| 4 TETO | `WORKER_RELOAD_MAX_DEFER_MS` → aplicar na mesma e registar `HOT_RELOAD_WORKER_FORCED reason=no-boundary-in-Ns` | **nunca indefinitely** |
| 5 PISO | `WORKER_RELOAD_MIN_INTERVAL_MS = 180000` | limita quantas vezes um modelo pode recarregar |

**O TETO N = 25 000 ms, JUSTIFICADO POR MEDIÇÃO, não por palpite.** O dono disse para
eu escolher o N e justificá-lo. A cadência real de fechos de linha é ≈3,6 s (14 → 25
linhas em 40 s com um vídeo a tocar), portanto 25 s são cerca de **sete** intervalos
de linha fechada — a fronteira ganha quase sempre, o caminho FORCED fica a excepção
(o `no-boundary-in-Ns` só entra se passarem 25 s sem uma linha fechada), e o pior
caso passa de "nunca" para "meio minuto". O PISO de 3 min continua a limitar a taxa
de reload de modelo, e um reload forçado custa um warm-up de modelo (2,0–8,3 s,
1,4–2,1 GB RSS).

**Duas regras mais, que saíram do mesmo trabalho:**

- **A OBSOLESCÊNCIA É UMA CONSULTA, NÃO UMA DESCOBERTA.** O watcher de ficheiros não
  consegue dizer ao dono "o worker que está a correr é antigo" — isso exige
  **perguntar**: o shell compara o sha256 em disco com o sha256 com que o worker foi
  lançado (`sha256_disk` vs `sha256_at_spawn`), leva ambos no log E em
  `panel_state_snapshot()['shell']`, e depois de aplicar mostra o **novo pid e o novo
  sha256**.
- **A SHELL NÃO SE RECARREGA A SI PRÓPRIA.** Se os bytes da shell mudou, a divergência
  é mostrada com **uma linha de dica de reinício** — não silenciosamente ignorada.
  E a ordem de reinício depois de mexer no worker: **reiniciar a shell primeiro (ou
  as duas juntas)**, senão a `_consume` da shell antiga continua a inundar
  `BRIDGE_UNKNOWN` com o evento `meter` que o worker novo agora envia.
- Se o hot reload aplica e as legendas piscam uma vez, **isso é aceitável** — a
  alternativa era código que nunca recarregava.

**Gate:** `_main/_strip-reload-probe.py` — 6 braços contra um `WorkerBridge` REAL e um
filho REAL (o `apply_panel_state` é um stub, logo imune ao penduramento do WebView2) →
`GREEN 25/25`. O `--probe-reload` dentro da shell também é GREEN: guard 0/esperado 0;
storm 6/6; burst 1/1; **linha-fechada 0 antes → 1 depois** com `still_capturing=True`;
teto 1 reinício SEM fronteira (`HOT_RELOAD_WORKER_FORCED`); piso 0 reinícios com
`pending_held=True`.

**E UM BUG DE RELÓGIO QUE O BRAÇO DO PISO ENCONTROU.** A política lia
`spawned_at >= self.pending_since`, e o `time.monotonic()` tem um **tick GROSSO** nesta
caixa (duas chamadas seguidas comparam iguais, e ainda iguais 100 µs de intervalo —
medido), por
isso um spawn no mesmo tick era lido como respawn e o braço da fronteira reportava
`APPLIED_AT_BOUNDARY` para um respawn que nunca aconteceu. A comparação passou a
**estrita `>`**. Regra: sempre que uma duração decide se algo aconteceu, lembrar que
o relógio pode não ter ticado.

---

## 11. O HOVER DO DONO, MEDIDO NO RENDERIZADOR, NAS DUAS SUPERFÍCIES

O dono disse, verbatim: *"passo o mouse encima > aparece mais botoes"*. Uma leitura
de CSS não responde à pergunta que ele está a fazer — *se a revelação é só CSS dentro
de uma janela pequena, os botões ainda estão dentro do hit-test, ou são cortados
dele?* — então construí o `--probe-hover`, que sintetiza um hover REAL no renderizador
por CDP `Input.dispatchMouseEvent` (o rato físico do dono nunca se mexe) e lê a
consequência. Janela nunca vista (`Opacity = 0`).

**SUPERFÍCIE FAIXA** (`inner 1040×150`, `.stripbar` `display:flex`, `opacity:1`,
`visibility:visible`): os **quatro** botões estão laid-out (`64×26`, `60×26`, `80×26`,
`83×26`), todos `in_viewport:true`, e todos **`hit_is_button:true`** —
`document.elementFromPoint` no centro de cada um devolve o botão (ou um descendente),
isto é, **estão no hit-test**. O hover sintético é exclusivo e real: mover para cada
centro acende `:hover` exactamente nesse botão e `false` nos outros três. Um clique
sintético no primeiro botão **alterna `aria-pressed` `true → false`**. **Portanto os
botões estão laid-out e clicáveis; o `:hover` só os reestiliza — nada "aparece" no
hover.**

**SUPERFÍCIE PAINEL** (`.stripbar display:none`): cada botão lê `box [0,0]`,
`in_viewport:false`, `hit_is_button:false`, e o probe reporta
`unreachable_no_button_in_viewport` com clique `target:null`. **Na superfície do painel
não há botões de faixa no hit-test para revelar.** (O `innerWidth/innerHeight` do DOM
fica no valor maior da faixa mesmo com a janela a `380×900` — um viewport de layout
stale; o resultado `display:none` + `[0,0]` do hit-test é a parte autoritativa, e o
probe lê um snapshot assentado antes de medir.)

Isto **confirma a leitura do CSS** (`panel.css:1356` — `.strip-button:hover` só muda
`background`/`color`, sem gating de display/opacity/visibility, portanto os três
botões da faixa estão sempre laid-out) **e acrescenta o que a CSS não diz**: no painel
não há nada a revelar, e na faixa os botões são clicáveis. A instrumentação está em
`_main\_hover-probe-run2.log` (o `run` anterior tinha um snapshot lido entre duas
frames, quando a janela `WINDOW_GEOMETRY` e o `display:none` caíam em frames
separados; o `settled`加上 resolve).

**Trapaça do CDP, registada:** o `_cdp` do `mouseMoved` dá `cdp-timeout` (o `Task` sem
genérico do pythonnet não completa o `ContinueWith` num move coalescido), **mas o
efeito acontece na mesma** — o `:hover` muda e o clique funciona (`ok`). A verdade
medida é o estado do DOM, não o `Task`.

---

## 12. A BATERIA, O `AGENTS.md`, E A ARMADILHA QUE A BATERIA ME ENSINOU

**A BATERIA: OS PASSOS DESTA LANE ESTÃO VERDES, MAS O VEREDITO DA PRÓPRIA BATERIA
NÃO É CONFIÁVEL NESTA CORRIDA — E A RAZÃO É MEDIDA, NÃO ADIVINHADA.** As seis
secções desta lane saíram todas `rc=0`:

```
[step] strip-surface-oracle     rc=0  [CONTROL] went RED on the broken copy as required
[step] strip-stats-log-budget   rc=0  [CONTROL] went RED on the broken copy as required
[step] strip-hot-reload         rc=0
[step] strip-surface-runtime    rc=0
[step] strip-geometry-restore   rc=0
[step] strip-stats-wave         rc=0
```

A corrida anterior tinha `strip-stats-log-budget=3` (RED), e a causa era o **próprio
instrumento a mentir**: o probe imprimia a sentença de verdict **só quando GREEN**,
portanto a sua corrida RED escrevia um log de passo de **0 bytes** e o `:control` da
bateria não encontrava `STRIP-LOG CONTROL PASS` — um controlo que reportava "o
instrumento não correu" em vez de "o instrumento correu e falhou". Corrigi o probe
(abaixo) e o passo passou a `rc=0` com o `[CONTROL] went RED on the broken copy`.
As seis secções desta lane saíram todas `rc=0`:

**A CAUSA É O AGREGADOR A SER EDITADO EM CONCURSO — não são os fins de linha.** A
`_main\_audit-verify-all.cmd` está hoje **100 % CRLF (0 bare LF, 518 CRLF, sha256
`8F86034014FCA362…`)**, o que **exclui** a causa documentada do duplo-arranque. E a
causa real tem duas provas: (1) o ficheiro **cresceu de 28 947 B (o estado em que o
deixei) para 31 071 B durante a minha corrida** — outra lane estava a editá-lo; (2) o
`control-history-gallery-neg-arm` saiu `MISSING` na primeira passagem e `rc=0` na
segunda — **um instrumento apareceu a meio da corrida**. `cmd.exe` procura um batch
por **byte offset**; se o ficheiro muda por baixo de um batch em execução, os offsets
guardados derivam e o cmd retoma a meio do ficheiro — exactamente a falha que o
`AGENTS.md` descreve, com um gatilho **novo**: não são os LF, é a **edição concurrente
de um ficheiro partilhado**.

**O terminador existe e está no sítio** (`if not "!BAD!"=="0" exit /b 1` /
`exit /b 0`, logo a seguir ao bloco de sumário), e o `git show HEAD:` da versão
comprometida tem a mesma estrutura — por isso **não há bytes a corrigir**, e eu não
tocaria num ficheiro partilhado que outra lane está a editar. Fica registado como
achado para quem tem o ficheiro: **um veredicto de bateria tirado de uma corrida em
que o batch foi modificado a meio não é um veredicto — é uma união de duas metades.**

**O que o probe de orçamento de log aprendeu (e agora faz):** imprime o verdict **nas
duas cores** (`STRIP-LOG CONTROL PASS` / `STRIP-LOG CONTROL FAIL reason=…`), uma shell
que nunca sai é a **própria** falha nomeada (`killed`/`ready`, não um número lento), a
conta de pushes entregues cai para o `count=` cumulativo do último
`BRIDGE_STATS_PUSH` quando falta o `SHELL_EXIT`, e um braço que nunca chega a
`RECEIVER_READY` é **tentado uma vez** — um penduramento ambiental não é uma medição
do orçamento de log.

**O `AGENTS.md` recebeu um bloco aditivo LF + as três correções**, na mesma edição:
o par CUDA falso (`:181-182`), o bullet "APAGADO" do `redux-onnx-int4` (`:511`), e os
números de linha movidos (`rerun`/`finalise`/`drain`). Medido: **54 801 B → 73 334 B,
601 → 835 bare LF, 0 CRLF, endsWithLF=True**, sha256 `858026665A6F3C78…`. O bloco
traz: os 17 métodos de bridge + 3 membros novos, a geometria medida da faixa
`1040×150@(440,834)` rect `(440,834,1480,984)` base 1032−48, a altura do CSS com
fallback 148 (e cada fallback registado), a regra do log agregado e porque, a
armadilha do `SetWindowPos`/argtypes, a regra de reload (fronteira/teto/piso), o ramo
`meter` e o bug do relógio `>=`→`>`, a regra de fonte de áudio §5.2 verbatim, a regra de
foco G4/6, a limitação multi-ecrã, `--show`/`--selftest` não provados, e a nota de
reinício.

**A ARMADILHA MAIOR — uma shell pendurada envenena TODOS os arranques seguintes.**
Uma shell lançada com `--exit-after N` é normalmente morta pelo temporizador armado em
`_on_loaded` — que não existe até o painel carregar. Um penduramento a montante do
load deixou uma `pythonw` **escondida viva ~20 minutos** (pid 40876), e enquanto ela
viveu **6 de 6** arranques posteriores penduraram antes de `RECEIVER_READY`. Quando
ela saiu, a mesma caixa mediu **3 de 3 saudáveis** (`HEALTH-VERDICT HEALTHY-ALL`). A
cura está na SHELL, não em cada probe: `_arm_exit_watchdog()` dispara um `os._exit`
duro `EXIT_WATCHDOG_GRACE_S = 60` depois da criação da janela e regista
`SHELL_EXIT_ARMED where=window-created`. Usa `os._exit` e **não** `request_exit` de
propósito: `request_exit` faz join de `bridge.stop()`, que toma a MESMA lock que um
penduramento de arranque pode estar a segurar. Verificado aditivo: um arranque
saudável regista o arm a `after_s=68.0` e mesmo assim sai pelo seu `SHELL_EXIT rc=0`
de sempre.

**Regra de instrumento, ganha aqui:** *"um probe que não imprime nada em RED parece um
probe que nunca corre — e ainda derrota o seu próprio controlo."* E uma segunda, do
meito debugging: `python -c "import pywebview"` falha nesta caixa e **não significa
nada** — a distribuição chama-se `pywebview`, o **nome de importação é `webview`**. Uma
lane concluiu daqui que faltava a dependência; era um teste mau.
---

## 13. A CORRIDA LIMPA DA BATERIA — E O QUE ELA PROVA (e o que não prova)

Depois da primeira corrida (que deu dois sumários por causa da edição concorrente do
`.cmd`), corri a bateria outra vez **com o sha256 do `.cmd` registado antes e depois**:

```
cmd sha before = 8F86034014FCA362E71F9E11755B3E11029A86A0C853CB6DFC318AD5081A2FAB  len=31071
cmd sha after  = 8F86034014FCA362E71F9E11755B3E11029A86A0C853CB6DFC318AD5081A2FAB  len=31071
CHANGED DURING RUN = False
steps-lines in log = 1        <-- UM só sumário, como deve ser
cmd rc=1
```

Isto **confirma por medição a hipótese da §12**: o duplo-arranque vinha de outra lane
editar o `.cmd` a meio da corrida (o ficheiro mudou de 28 947 → 31 071 B nessa
ocasião), **não** dos fins de linha (o ficheiro está 100 % CRLF nas duas corridas).
Com o ficheiro estável, sai **um** sumário e um veredicto.

**Os seis passos desta lane nesta corrida limpa:**

```
strip-surface-oracle    rc=0  [CONTROL] went RED on the broken copy as required
strip-stats-log-budget  rc=0  [CONTROL] went RED on the broken copy as required
strip-hot-reload        rc=0
strip-surface-runtime   rc=0
strip-geometry-restore  rc=3   <-- flake, ver abaixo; CORRIGIDO depois
strip-stats-wave        rc=0
```

Sumário da corrida limpa: `steps : 41  gate=30  control=9  skipped=1  expect-red=1
missing=0`, `BATTERY-VERDICT: RED - 2 step(s) failed`, e as duas falhas foram
`strip-geometry-restore=3` e `skip-verdict-guard=1`. **`missing=0`** (a corrida
anterior tinha `missing=1`) — o `control-history-gallery-neg-arm` já existe.

**O `strip-geometry-restore=3` era uma CORRIDA COM O APP DO DONO, não um defeito.** O
log do braço `in-bounds` mostra que a shell **leu `rect=380x900@(-10000,66)`** — a
geometria de painel por omissão dela própria — e não a faixa `700x148@(700,400)` que o
probe tinha semeado. Porque: **a shell do dono (28428, revisão anterior) reescreve
`panel-visibility.json` a cada ~3 s SEM a chave `geometry`** e, entre a semeada e o
arranque da shell em teste, apagou a semente. **A shell comportou-se bem** — leu o que
estava no ficheiro e limitou-o correctamente ao work area
(`PANEL_GEOMETRY_CLAMPED … work=1920x1032@(0,0)`); foi a EXPECTATIVA do probe que foi
invalidada por um escritor concorrente. Corrigi o instrumento: `launch()` volta a
sementear **imediatamente antes** do `Popen`, e `main()` **tenta cada caso uma vez
mais** se a shell não leu o rect semeado — uma corrida ambiental não é uma medição do
clamp. Corrida isolada depois da correcção: **`GREEN`, 6/6 checks, rc=0**, ambos os
casos na primeira tentativa.

**`skip-verdict-guard=1` NÃO É DESTA LANE** — é o guarda de skips da bateria (de outra
lane). Não toquei nele.

**O que a bateria prova e o que não prova, dito sem pompom:** a bateria sai **RED**
(com `skip-verdict-guard` de outra lane e, na altura, o flake do restauro), **não
GREEN**. O que está provado é que **os passos e os controlos desta lane estão
verdes** e que o `strip-stats-log-budget` deixou de ser o ponto fraco. O que **não**
está provado é um veredicto GREEN da bateria inteira — e dizê-lo seria mentir.
