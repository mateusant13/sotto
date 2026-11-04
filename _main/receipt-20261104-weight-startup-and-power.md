# Receipt — peso, arranque e recuperacao de energia/sessao (2026-11-04)

Ordem do dono, verbatim: *"mede peso/arranque"*. Nao havia instrumento que
respondesse as duas perguntas na MESMA corrida: o censo de custo de 2026-10-31
media uma sessao ja' quente, e o censo do primeiro frame mede o que acontece
DEPOIS de a pagina existir. O buraco era exactamente o que ele sente — entre o
duplo-clique e o primeiro pixel.

## 1. Instrumento (`_main/weight-startup-probe.py`)

Larga a app pelo caminho da lane (escondida, `SOTTO_LANE_LAUNCH=1` +
`_main/keepalive.py`) ou pela tarefa `\Sotto` (`--launch task`, integridade do
dono), carimba cada marco do log VIVO pelo `t=` do PROPRIO shell (ms desde o
processo), e amostra a ARVORE de processos a 1 Hz (RSS, threads, handles, CPU).
Mata pelo ARTEFACTO (`sotto_webview.py` / `sotto_worker.py` / `keepalive.py`),
nunca por palavra generica.

**Quatro defeitos do proprio instrumento, encontrados e corrigidos na hora:**

| defeito | medicao que o revelou | cura |
|---|---|---|
| amostrava o PID 0 (*System Idle*, memoria do SISTEMA) | `rss_mb=3558.8 cpu_s=477778` a 2,1 s | pids zero filtrados |
| carimbava os marcos pela hora da leitura, nao pelo `t=` | `nav1=nav2=nav3=4875ms` | `t=(\d+)` da linha |
| kill por `psutil` numa app de integridade superior | `AccessDenied (pid=14212)` com a app de pe' | `schtasks /end /tn Sotto` + `AccessDenied` tolerado |
| julgava o log ANTES do estimulo (no braco vivo) | 7 FAILs sobre uma app a funcionar | releitura depois do post |

## 2. Arranque (corrida 2026-11-04 07:43, integridade do dono, escondida)

Carimbos do proprio shell (`t=` ms desde o processo):

| marco | t (ms) | delta |
|---|---|---|
| `SHELL_STARTUP_STAGE` (processo vivo) | 0 | — |
| overlay + `BRIDGE_SPAWNED` + `TRAY_ICON_ADD ok=true` | 60–160 | 0,16 s |
| `WEBVIEW2_PROFILE` | 1650 | 1,5 s |
| `WEBVIEW_NAV subscribed` / `stage.html start` | 1906 / 1922 | 0,25 s |
| `stage.html` DOM | 6656 | **4,7 s** (1,1 KB de HTML) |
| `panel.html` start | 7063 | 0,4 s |
| `panel.html` DOM → `RECEIVER_READY` | 9297 → 9328 | **2,2 s** |
| primeiro frame da pagina (dentro do renderer) | 10 043 (firstPaint 3040 ms depois do doc) | |
| `WORKER_AUTOSTART` | 10 093 | 0,8 s |
| `BRIDGE_LOAD_MS ms=19765` (worker carregado) | 19 765 | **9,7 s de modelo** |

**O que a pagina custa e o que o WebView2 custa:** o `PANEL_BOOT_PROFILE` do
proprio renderer diz `dom=2235 ms`, `dcl=2235`, `loadEvent=2243`,
`firstPaint=3040 ms` e **`longtasks: []`** — a pagina NAO esta' bloqueada por JS.
Os 7,4 s entre o arranque e o `RECEIVER_READY` sao WebView2 (browser process a
frio + o esboco `stage.html`), e os 4,7 s do `stage.html` sao o mesmo custo pago
uma vez por uma pagina de 1,1 KB. Duas navegacoes, um renderer.

**Variancia medida (o mesmo codigo, horas diferentes):** a corrida de 06:30
gastou 19,9 s ate' ao `panel.html` (t=19 906) e a `run.cmd` desistiu aos 30 s
(`HANG rc=4 by=run.cmd-readiness`) antes de a pagina estar pronta; a de 07:43
chegou ao `RECEIVER_READY` em 9,3 s. Ou seja: **arranque = 9 a 30 s, dominado
pelo WebView2 e pela carga da maquina** (I: a 99 % e 722 processos, medido).

**Uma lane NAO consegue medir o caminho do WebView2:** a largada pela pane
(medium) morre em `WEBVIEW2_INIT_FAILED 0x80010108 RPC_E_DISCONNECTED` e
`TRAY_ICON_ADD ok=false winerror=5` (UIPI) — as fases ate' ao painel ficam
medidas, o resto nao. E' por isso que o probe tem `--launch task`.

## 3. Peso

| corrida | 5 s | 30 s | 60 s | 100 s | processos | threads | CPU na janela |
|---|---|---|---|---|---|---|---|
| lane (medium), 100 s | 233 MB | 1321 MB | 1907 MB | 1907 MB | 4 | 111 | 53,7 s |
| tarefa (integridade do dono), 77 s | 525 MB | 1539 MB | 1540 MB | — | 11 | 308 | 40,2 s |

- Worker sozinho: `BRIDGE_RSS rss_mb=1049.8` estavel, sem audio a correr.
- Pico da arvore: **3558 MB** na primeira amostra bruta — era o PID 0, nao a
  app (ver §1). Depois da correcao, o pico observado e' **1614 MB**.
- Handles: 2128 (lane) e 5130 (tarefa, com WebView2 vivo). Threads caem de 597
  durante o load para 111-308 em regime.
- **Nao ha' fuga visivel nesta janela**: 1907,0 → 1907,8 MB em 78 s (a serie do
  `BRIDGE_RSS` da shell da' 1049,8 MB constante em duas leituras a 60 s de
  distancia). Uma fuga mais lenta que 1 MB/min nao seria vista por 2 minutos —
  o `rss-trend` da bateria julga a FORMA de series longas, e e' ele o portao.

## 4. Recuperacao de energia e de sessao (`app/webview/power_recovery.py`)

Buraco medido: `grep -n "WM_POWERBROADCAST\|WM_WTSSESSION_CHANGE\|
WTSRegisterSessionNotification" app/webview/sotto_webview.py` = **0**.

Decisao pura (`classify` + `plan`) e transporte proprio:

| evento | accoes |
|---|---|
| `PBT_APMRESUME{AUTOMATIC,SUSPEND,CRITICAL}` | topmost + worker(probe) + geometry |
| `WTS_SESSION_UNLOCK` | topmost + geometry (**worker NAO se reinicia**: 14-26 s por nada) |
| `WTS_{CONSOLE,REMOTE}_CONNECT` | topmost + geometry (os monitores mudaram) |
| lock / suspend / logoff / desconhecido | nada |

Transporte: janela **POPUP de tamanho zero, top-level**, criada numa thread com
bomba de mensagens. Tres tentativas, duas refutadas por medicao:

1. `NativeWindow.AssignHandle` na form do painel → `ATTACHED` + `PostMessage`
   aceite + **zero** `POWER_RESUME`: o WinForms recria o handle quando o
   WebView2 sobe e a subclasse morre com o antigo.
2. Janela propria na thread que chama `_on_before_show` → aceite e **zero**
   despachos: uma mensagem postada so' corre numa thread que BOMBEIA, e quem
   bombeia e' a `Application.Run`, noutra thread.
3. Janela propria + thread com `GetMessage`/`DispatchMessage` → **entrega**.

Provas:
- `_main/power-recovery-oracle.py`: **28/28 arms** (classificacao, plano,
  ordem, isolamento de accao que falha, log, e transporte hermetico — janela real
  desta maquina a receber `SendMessage` e um `PostMessage` bombeado).
- `--neg-arm`: **3/3 mutantes** apanhados (unlock a reiniciar o worker, resume
  sem o flavour SUSPEND, uma accao a matar as seguintes).
- `--live-arm` (app real, escondida): **9/9** — `POWER_RESUME event=resume` e
  `event=unlock` no log, `POWER_RESUME_TOPMOST` = resume+unlock,
  `POWER_RESUME_WORKER` = resume, `POWER_RESUME_GEOMETRY` = resume+unlock,
  zero `POWER_RESUME_ACTION_FAILED`.

**O que NAO se prova e nao se afirma:** que o Windows emita o evento quando a
maquina dele dormir e acordar. Nenhum instrumento deste repo pode dormir o PC do
dono; o que esta' provado e' o caminho (`WndProc` real, mensagem real, accoes
reais).

## 5. Copiado do RE, e o que foi recusado com o risco nomeado

| ideia | origem | o que aterrou aqui |
|---|---|---|
| topmost devolvido por laco (2 s) | Perssua `powerRecovery.js`, Handy | `app/webview/topmost_keepalive.py` — commit `bf222e9` |
| click-through so' depois de `FRAMECHANGED`, e LIDO de volta | Perssua `WindowMouseControl`, Live-Subtitles `overlay.py:247-252` | `apply_click_through()` — commit `16f7d5f` |
| velocidade do player no relogio da legenda | Perssua (sync com o video) | `playbackRate` interpolado — commit `1ca6d3d` |
| recuperar do sleep/unlock (o Windows avisa) | Perssua `powerRecovery.js` | este recibo, §4 |

**Recusado, com a razao medida:**

- **hit-test por rects (`setShape`)**: o Sotto ja' faz melhor — a propria pagina
  pede interactividade e a shell alterna `WS_EX_TRANSPARENT` +
  `WS_EX_NOACTIVATE` (`set_pointer_interactive`, `POINTER_INTERACTIVE` no log).
  Uma lista fixa de rects seria uma segunda fonte de verdade a apodrecer.
- **prefixo `committed/tentative` (Handy)**: congela texto que pode estar errado,
  e o defeito que ele resolve (linha cumulativa re-escrita) ja' foi curado no
  motor (`caption-cumulative`). O modo de falha do congelamento e' pior.
- **audio helper em Rust (Perssua)**: o worker ja' abre WASAPI em Python e o
  custo medido e' do MODELO (18,9 s de load), nao da captura.
