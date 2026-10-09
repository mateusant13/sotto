# Recibo — linha temporal de FOCO + fila de foco

**Data:** 2026-10-07 (medições entre 12:0x e 12:18 locais)
**Lane:** investigação e MEDIÇÃO. Metade do objectivo: **a app em foco + a fila de foco**.
**A outra metade NÃO foi feita e não é reivindicada aqui:** *qual* app produz o som, e o
título da aba que toca. Ver §6.
**Objectivo do produto (metadados; nunca mostrado ao utilizador):** relacionar cada
excerto de áudio com a app que estava em foco quando o áudio tocou. Frase do dono:
*"se eu ouvi algum amigo meu falando algo engraçado pelo discord, enquanto eu estava
jogando um jogo, da pra relacionar esse jogo ao audio"*.

**VERDICT do oráculo: `GREEN (10/10)`** — `_main\focus-timeline-oracle.txt`,
`_main\focus-timeline-oracle.json`.

---

## 1. O instrumento, a cadência e a contagem

### 1.1 O instrumento

| peça | ficheiro | o que é |
|---|---|---|
| **a sonda** | `_main\focus-timeline-probe.py` | o instrumento principal. Modos `live` e `poll-only`. |
| lançador | `_main\_focus-launch.py` | `pythonw.exe` que captura tracebacks para um `.log` (senão o erro morre com o processo) |
| censo de janelas | `_main\_focus-window-census.py` | censo do **próprio pid** a 50 ms, com controlo positivo |
| censo de cloaked | `_main\_focus-cloak-census.py` | uma passagem sobre todas as janelas de topo, com o índice Z |
| oráculo de título | `_main\_focus-title-oracle.py` | `GetWindowTextW` vs `SendMessageTimeoutW(WM_GETTEXT)` |
| diag. de threads | `_main\_focus-thread-diag.py`, `_main\_focus-thread-baseline.py` | de onde vêm as threads |
| **o oráculo** | `_main\focus-timeline-oracle.py` | 10 portões, cada um com as DUAS cores; escreve `.json` + `.txt` |

**A via prescrita foi seguida à letra:**

```
SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, 0, cb, 0, 0,
                WINEVENT_OUTOFCONTEXT)          # + GetMessageW numa thread própria
GetForegroundWindow -> GetWindowThreadProcessId -> OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)
                     -> QueryFullProcessImageNameW
GetWindowTextW / GetClassNameW                                  # identidade e título
GetTopWindow(NULL) -> GetWindow(h, GW_HWNDNEXT)                 # a FILA, em ordem Z
  filtros: GetAncestor(GA_ROOT) | IsWindowVisible |
           DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED=14) |
           ~(WS_EX_TOOLWINDOW) | pid != pid-do-dono
```

### 1.2 Cadência: **por evento, não por amostra**

- **A linha temporal é feita de EVENTOS.** O gancho `EVENT_SYSTEM_FOREGROUND` só acorda
  quando o foco muda — não há varrimento periódico para produzir os segmentos.
- **A fila é tirada em CADA transição** (no instante do evento), profundidade 5
  (`queue_depth: 5`), mais a caminhada **inteira** em ordem Z para contagem de razões.
- **A poller** (15 ms nas arms `live`, 1000 ms na arm B) existe como **contra-prova
  independente** e para medir a latência de um amostrador — não é ela que produz a
  linha temporal.
- A thread da poller é a **única** thread que a lane acrescenta (ver §5.2).

### 1.3 A contagem (o que foi realmente medido)

| arm | modo | cadência | duração declarada | eventos de gancho | eventos de poller | total |
|---|---|---|---|---|---|---|
| **A** | live | 15 ms | 300,0 s | 38 | 16 | 54 |
| **A2** | live | 15 ms | 240,0 s | 6 | 4 | 10 |
| **B** | poll-only | 1000 ms | 120,0 s | 0 | 10 | 10 |
| **C** | live, **filtro DESLIGADO** | 15 ms | 120,0 s | 24 | 11 | 35 |
| **D** | live, cross-check de título | 15 ms | 90,0 s | 10 | 12 | 22 |
| **E** | live, razões na caminhada inteira | 15 ms | 90,0 s | 2 | 0 | 2 (+2 marcadores) |

**Total de eventos de gancho registados: 80. Total de registos: 133.**
Censo de janelas do próprio pid: **10 791 amostras a 50 ms** (5 995 + 4 796).

### 1.4 Como se lança (padrão obrigatório neste repo)

```
pythonw.exe H:\sotto\_main\_focus-launch.py <errlog> <script.py> [args...]
```

O `pythonw.exe` é obrigatório: **nunca deixar uma janela visível** (§5.3 prova que não
deixou). Runs longos têm de correr como job em background — um processo lançado de dentro
de uma chamada de ferramenta é morto quando a chamada retorna.

---

## 2. As medições reais

### 2.1 Custo e latência, por arm

| arm | CPU (% de um core) | RSS (MB) | threads | latência do gancho (p50/p95/max, ms) | `handle_ms` p50/p95/max | `dwm_calls` | janelas no censo Z |
|---|---|---|---|---|---|---|---|
| A | 0,479 | 26,50 | — (summary pré-campo) | 0 / 0 / 16 | 2,683 / 12,995 / 24,250 | 550 | 419 |
| **A2** | **0,293** | **26,16** | **5 → 6** | 0 / 15 / 15 | 2,071 / 7,593 / 7,593 | 109 | 417 |
| B (poll 1 s) | 0,052 | 25,26 | — | — (sem gancho) | 0,976 / 1,672 / 1,672 | 120 | 419 |
| C | 0,495 | 26,25 | — | 0 / 0 / 0 | 2,206 / 4,216 / 5,865 | 186 | 419 |
| D (com cross-check) | 0,295 | 25,61 | 5 → 6 | 0 / 16 / 16 | 8,365 / 28,523 / 39,601 | 220 | 421 |
| E | 0,590 | 25,49 | 5 → 6 | 0 / 0 / 0 | 58,530 / 104,627 / 104,627 | 34 | 417 |

**Leitura honesta da latência.** O relógio do Windows aqui tem resolução de **1 ms**
(`GetTickCount64` e `dwmsEventTime`). A latência medida é
`GetTickCount64() - dwmsEventTime`, portanto **o inteiro é um PISO**; o limite superior é
piso+1. Em A, **97,37 % dos 38 eventos deram 0 ms** (isto é: <1 ms), máximo 16 ms. O
`latency_hi_ms` (piso+1) tem máximo 17 ms. Não se promete nada abaixo de 1 ms.

**A arm D mostra o preço do cross-check de título:** `handle_ms` sobe de ~2 ms para
~8 ms (p95 28,5 ms) porque `SendMessageTimeoutW` **espera pela outra thread** da janela
alvo. É o preço de não confiar cegamente no `GetWindowTextW` — e em §2.4 vê-se que o
cross-check não encontrou nenhuma mentira ao nível do topo, portanto **não precisa de
estar no caminho quente**.

### 2.2 Onde está o foco ao longo de 300 s (arm A)

- **38 transições de JANELA** em 299,966 s.
- **32 transições ao nível da APP (pid)** — porque uma app pode ter várias janelas.
- Um amostrador de 1 s, sobre a MESMA actividade, dá **20** transições.
  → **perde 18 de 38 (47 %) ao nível da janela, 12 de 32 (37 %) ao nível da app.**

### 2.3 A fila REAL, em ordem Z, quando um jogo/browser está em foco

Amostra real, arm A, instante do pico de `chatterino.exe` (foco: `Chatterino 2.5.3`):

```
z=1  voicemeeter.exe   "VoiceMeeter"
z=2  explorer.exe      "_aireplay-empty-20261007 – Explorador de Arquivos"
z=3  Discord.exe       "@John Dἱscord - Discord"
z=4  explorer.exe      "Este Computador – Explorador de Arquivos"
```

Isto é exactamente o cenário do dono: **um jogo/uma app em foco, o Discord logo abaixo na
pilha Z.** A fila é o que permite dizer "o áudio pode ter vindo do Discord, que estava a
um Alt+Tab de distância", sem afirmar que veio.

### 2.4 Título: duas vias, e a divergência corre ao CONTRÁRIO da hipótese

`_main\focus-title-oracle.json`:

- **janelas de topo: 396/400 concordam** entre `GetWindowTextW` e `WM_GETTEXT`.
- **restrito a janelas VISÍVEIS (as únicas que podem estar em foco): 22/22 concordam.**
- `gwt_blind` ao nível do topo = **0** — `GetWindowText` **nunca** ficou cego onde
  `WM_GETTEXT` tinha texto. A direcção da divergência é a **oposta** da esperada: são
  janelas auxiliares **INVISÍVEIS** (`IME`, `NVCapContext_…`, `gvrBackgroundClass3`) que
  não respondem a `WM_GETTEXT`. `GetWindowTextW` é o **mais robusto** dos dois aqui.
- **CONTROLO (a outra cor): 2 janelas FILHO de outro processo** onde `GetWindowText`
  devolve `""` e `WM_GETTEXT` devolve texto — classes `Edit` e `ComboBoxEx32`. A
  confiabilidade vale para a janela de **TOPO**, não para os filhos.

### 2.5 O que o título de um navegador dá — e o que NÃO dá

Foco numa janela do Chrome:
`(1) CONTRA O FILIPOPPY? é como tirar doce de criança - YouTube - Google Chrome`

**O que dá:** o título é a **aba ACTIVA** daquela janela. Isso é útil (diz que o vídeo do
YouTube estava à frente) e é tudo.

**O que NÃO dá:** na fila havia **79 janelas de navegador**, com **2 títulos diferentes**
do foco. O título é **por janela** e **não diz qual delas toca som**. Uma aba em segundo
plano que continua a tocar áudio é invisível para este instrumento. **Não se promete
mais do que isto.** (Isto é metade da lane do áudio, ver §6.)

### 2.6 Onde estavam os fantasmas (e porque é que a contagem amostrada mentia)

**Filtro DESLIGADO (arm C)** — a fila crua, os 5 primeiros slots de um evento real:

```
foco: chrome.exe  'CONTRA O FILIPOPPY? … - YouTube - Google Chrome'
raw_walked=23   filtered_n=5   ghost_in_top_slots=4

z=1  WindowsTerminal.exe  ghost_why=invisible   title='MSCTFIME UI'
z=2  WindowsTerminal.exe  ghost_why=invisible   title='Default IME'
z=3  powershell.exe       ghost_why=toolwindow  title=''
z=4  WindowsTerminal.exe  ghost_why=(nenhum)    title='Pesquisa e roadmap do clone do H:\aireplay'
z=5  explorer.exe         ghost_why=invisible   title='MSCTFIME UI'
```

**Quatro dos cinco primeiros slots eram fantasmas** e a app real só aparecia em z=4. Sem
o filtro, a "fila de foco" é lixo.

**CONTROLO do filtro (a outra cor): arm C, filtro desligado → 135 fantasmas na fila,
espalhados por 33 eventos, todos os 5 slots poluídos.** Com o filtro ligado (arm A):
**0 fantasmas na fila filtrada**, e o filtro rejeitou **243 janelas ao longo de 56 eventos**.

**O erro que os números revelaram.** A lista `ghosts` guarda só **8 amostras** por evento,
e essas 8 estão enviesadas para o **topo** da ordem Z, onde dominam as rejeições
`invisible`/`toolwindow`. Uma pesquisa por `cloaked` na arm A deu **ZERO** — e a conclusão
"o sub-filtro cloaked está morto" teria sido **falsa**. A cura foi contar as razões na
**caminhada inteira**, e correr a **arm E**:

```
arm E (90,038 s, 4 registos, 766 janelas caminhadas):
  raw_walked = 23 / 360 / 360 / 23
  ghost_reasons_total = {invisible: 720, toolwindow: 22, ok: 16, own-pid: 6, cloaked(2): 2}
  → cada uma das duas caminhadas de 360 janelas rejeitou 1 janela por CLOAKED
```

**O sub-filtro cloaked decide, ao vivo, 2 vezes em 90 s.** Não estava morto: estava
invisível na amostra.

**CONTROLO do sub-filtro cloaked** — `_main\focus-cloak-census.json`, uma passagem com
índice Z: 417 janelas caminhadas, 23 visíveis, 9 passam, 394 invisíveis, 144 toolwindow,
**12 cloaked**, `cloaked_min_z = 4`. Posições Z cloaked:
`4, 8, 9, 105, 289, 290, 375, 376, 377, 378, 379, 380`.

A linha decisiva — a única janela que **só** o cloaked rejeita:

```
z=289  Windows.UI.Core.CoreWindow  TextInputHost.exe  ("Experiência de Entrada do Windows")
       visible=True   toolwindow=False   cloaked=2  → rejected_by = cloaked(2)
```

As outras cloaked já tinham sido rejeitadas antes por invisível ou toolwindow
(z=4 `XamlExplorerHostIslandWindow`; z=8/9 `ThumbnailDeviceHelperWnd`; z=105
`ApplicationManager_DesktopShellWindow`). Isto é a **cor verde do gate** e ao mesmo tempo
a prova de que o controlo não é vazio.

### 2.7 O app do dono fora da fila

**Regra de identificação, em duas partes:**

1. **Varredura de `cmdline` (psutil), uma vez no arranque** — encontrou exactamente
   `28428` (`sotto_webview.py`) e `29008` (`sotto_worker.py`).
2. **Regra de título + classe** — `title == "Sotto"` **e** classe a começar por
   `WindowsForms10.Window.8.app`. Aplicada em cada evento.

**CONTROLO (a outra cor): a varredura só-no-arranque é INSUFICIENTE.** Seis **outras**
instâncias do shell Sotto (`5396, 5940, 8896, 27020, 33188, 36508`) apareceram **depois**
do arranque da arm e **chegaram ao FOCO da linha temporal**. A lista de pids congelada no
arranque perdeu-as todas (`{5396: 2, 33188: 2, 8896: 2, 36508: 2, 27020: 2, 5940: 2}` — 2
eventos cada). Conclusão: **a lista de pids do arranque não chega; é preciso a regra
título+classe (ou re-varrer numa cadência lenta).**

Com a regra: **6 pids do painel vistos, 0 na fila filtrada.**

### 2.8 Onde os fantasmas NÃO aparecem, e a prova de que a sonda não é cega

Censo do **próprio pid da sonda**, a 50 ms:

| arm | amostras | cadência | wall | pid da sonda visível | pid em foco visível (controlo) | janelas visíveis/amostra |
|---|---|---|---|---|---|---|
| A | **5 995** | 50,0 ms | 300,024 s | **0** | **5 995** | 23,13 |
| A2 | **4 796** | 50,0 ms | 240,012 s | **0** | **4 796** | 23,01 |

**Zero de 10 791 amostras, com um controlo positivo vivo em todas elas.** A sonda **não
cria HWND nenhum** (só `GetTopWindow`/`GetWindow`/`DwmGetWindowAttribute`, nunca
`CreateWindow`), e isto é a prova de máquina disso. Uma ausência sem controlo positivo não
seria prova — aqui há.

---

## 3. Os 10 portões, com as DUAS cores

Todos em `_main\focus-timeline-oracle.txt` / `.json`. **`SKIP` não é um passe** — não há
nenhum `SKIP` no resultado final.

### G1 `eventos-nao-amostras` — **GREEN**
- **VERDE:** 38 transições de JANELA em 299,966 s; ao nível da APP (pid): 32. Um
  amostrador de 1 s dá 20. Contra-prova com poller **independente** (arm A2): **o gancho
  perdeu 0** das que a poller viu (`hook_missed_vs_independent_poller: 0`).
- **VERMELHO:** amostrar de 1 s em 1 s **perde 18 de 38** transições de janela que
  existiram de facto (12 de 32 ao nível da app).

### G2 `latencia-do-hook` — **GREEN**
- **VERDE:** arm A p50=0 / p95=0 / **max=16 ms**, 97,37 % <1 ms (n=38). Arm A2
  p50=0 / p95=15 / max=15 ms, 83,3 % <1 ms (n=6).
- **VERMELHO:** o amostrador a 1 s tem latência **média 500 ms / máxima 1000 ms** — é o
  limite estrutural de qualquer cadência fixa.

### G3 `filtro-de-fantasmas` — **GREEN**
- **VERDE:** fila filtrada com **0 fantasmas**; o filtro rejeitou **243 janelas em 56
  eventos**. Sub-filtro cloaked: 12 cloaked no censo de uma passagem (de 417 top-level),
  das quais **1 é VISÍVEL e não-toolwindow** — só o cloaked a rejeita (`TextInputHost.exe`);
  e o mesmo filtro decidiu **AO VIVO 2 vezes** na arm E, contando a caminhada inteira
  (`{invisible: 720, toolwindow: 22, ok: 16, own-pid: 6, cloaked(2): 2}`).
- **VERMELHO:** filtro DESLIGADO → **135 fantasmas na fila, em 33 eventos** (arm C).

### G4 `app-do-dono-fora-da-fila` — **GREEN**
- **VERDE:** a regra título+classe viu **6 pids** do painel; **0 na fila filtrada**.
- **VERMELHO:** a varredura de pids **só no arranque** perdeu
  `{5396: 2, 33188: 2, 8896: 2, 36508: 2, 27020: 2, 5940: 2}`.

### G5 `x->y->x` — **GREEN**
- **VERDE:** **3 padrões A→B→A ao nível da APP (pid)** com excursão ≥0,5 s, de **33
  segmentos de app**. O mais longo: `explorer.exe -> WindowsTerminal.exe -> explorer.exe`
  com 0,21 s / 24,59 s / 0,62 s. **O melhor caso de produto:**
  `chrome.exe -> chatterino.exe -> chrome.exe` com **39,64 s / 5,60 s / 14,55 s**.
- **VERMELHO / CONTROLO:** ao **nível da JANELA** a mesma janela dá **14 padrões crus**,
  a maioria espúria (`chrome.exe → pythonw.exe → chrome.exe` onde o `pythonw` é a minha
  própria sonda; e 3 "focou no app chrome.exe" seguidos para 3 janelas do Chrome). É esta
  a prova de que **é preciso colapsar por pid** — o produto pergunta pela **APP**, não pela
  janela. Também: **6 segmentos do painel do Sotto caíram** da narrativa
  (`[5396, 5940, 8896, 27020, 33188, 36508]`).

### G6 `custo` — **GREEN**
- **VERDE (arm A2):** CPU **0,293 % de um core** (arm A: 0,479 %), RSS **26,16 MB**,
  `handle_ms` p50 **2,071 ms** / p95 7,593 ms; threads **5 antes da poller → 6 com a
  poller**.
- **VERMELHO / CONTROLO:** um `pythonw.exe` **sozinho** já traz **5 threads** (medido,
  `_main\focus-thread-baseline.json`, `threads_after_psutil_import: 5`). O orçamento de
  ≤2 threads é do **instrumento**, não do interpretador. A lane acrescenta **exactamente
  +1** — `_main\focus-thread-diag.json`: 5 → 6 (com a poller) → 5 (depois de parar),
  com os mesmos 5 ids de thread no início e no fim.

### G7 `titulo-duas-vias` — **GREEN**
- **VERDE:** no foco da arm D, **21/21 concordam**; janelas de topo **VISÍVEIS: 22/22**.
- **VERMELHO / CONTROLO:** **2 janelas FILHO** de outro processo onde `GetWindowText`
  devolve vazio e `WM_GETTEXT` devolve texto (`ComboBoxEx32`, `Edit`).

### G8 `contrato-da-narrativa` — **GREEN**
- **VERDE (junção ligada):**
  `usuario esta no foco do app game.exe(Meu Jogo) ... usuario focou no app Discord.exe(Discord) : audio continua ... usuario voltou pro game.exe(Meu Jogo) : audio continua`
- **VERMELHO / CONTROLO (junção desligada):**
  `... usuario focou no app Discord.exe(Discord) ... usuario voltou pro game.exe(Meu Jogo)`
  — sem o `audio continua`. Um gate que não consegue perder a frase não prova nada.

### G9 `censo-de-janelas-do-probe` — **GREEN**
- **VERDE:** a sonda visível em **0 de 4 796 amostras @50 ms** (arm A: **0 de 5 995**).
- **VERMELHO / CONTROLO:** o **pid em foco** visível em **4 796** amostras — o
  instrumento **não está cego**.

### G10 `titulo-do-navegador` — **GREEN (com limite declarado)**
- **VERDE:** título do foco (classe `Chrome_WidgetWin_1`) = aba activa:
  `(1) CONTRA O FILIPOPPY? é como tirar doce de criança - YouTube - Google Chrome`
- **LIMITE (não se promete o resto):** **79 janelas de navegador na fila**, com **2 títulos
  DIFERENTES** do foco. O título é **por janela** e **não diz qual delas toca som**.

---

## 4. Contrato de dados proposto

### 4.1 O evento (uma linha JSONL por evento) — `_main\focus-timeline-A-live.jsonl`

```jsonc
{
  "t": 1791384783.7754,          // epoch (s, float)
  "t_mono_ms": 1234567,          // relógio monotónico, para juntar com áudio
  "source": "hook",              // hook | poll | probe
  "reason": "foreground-event",  // foreground-event | poll-detect | arm-start | arm-stop
  "event_time_ms": 1234551,      // dwmsEventTime — o carimbo do PRÓPRIO evento
  "latency_ms": 16,              // GetTickCount64() - dwmsEventTime  (PISO, ver §5.1)
  "latency_hi_ms": 17,           // piso + 1 (limite superior honesto)
  "stale": false,                // o foco já mudou outra vez quando a fila foi tirada?
  "handle_ms": 2.683,            // custo de tratar este evento

  "focus": {                     // QUEM estava em foco
    "hwnd": "0x000206C4", "pid": 1628, "tid": 7880,
    "exe": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "title": "… - Google Chrome", "title_len": 61,
    "class": "Chrome_WidgetWin_1"
  },
  "prev": { /* … o mesmo objecto, ou null */ },
  "focus_changed": true,

  "queue": [                     // A FILA DE FOCO: os N seguintes na ordem Z
    { "z": 1, "hwnd": "0x00041384", "pid": 1628, "tid": 7880,
      "exe": "…\\chrome.exe", "title": "level down trolling - YouTube - Google Chrome",
      "class": "Chrome_WidgetWin_1",
      "passes_filter": true, "ghost_why": null },
    { "z": 2, "hwnd": "0x00051316", "pid": 25544,
      "exe": "G:\\Program Files\\Chatterino\\chatterino.exe",
      "title": "Chatterino 2.5.3", "class": "Qt671QWindowIcon",
      "passes_filter": true, "ghost_why": null }
  ],
  "queue_depth": 5,
  "raw_walked": 23,              // janelas percorridas na caminhada Z inteira
  "filtered_n": 5,               // quantas passaram o filtro

  "ghost_in_top_slots": 4,       // fantasmas nos N primeiros slots (o que o filtro salvou)
  "ghost_rejected_n": 19,
  "ghosts": [ { "hwnd": "…", "pid": 21492, "title": "MSCTFIME UI",
                "class": "MSCTFIME UI", "why": "invisible" } ],   // amostra de 8
  "ghost_reasons_all": { "invisible": 16, "toolwindow": 2, "ok": 5 },
                                 // razões na CAMINHADA INTEIRA (a cura do viés de amostra)
  "ghost_filter": true,

  "id_object": 91, "id_child": 0,
  "event": 327680              // o código do evento Win32
}
```

**`reason` — o campo que se pediu, com estes valores:**
`foreground-event` (veio do gancho) | `poll-detect` (a poller notou a mudança) |
`arm-start` / `arm-stop` (marcadores de fronteira da arm, com a fila do momento).

### 4.2 A narrativa — `sotto.focus-timeline/1`

```jsonc
{
  "schema": "sotto.focus-timeline/1",
  "level": "APP (pid)",          // o produto pergunta pela APP; a janela é diagnóstico
  "window_segments": 51, "app_segments": 33,
  "segments": [
    { "i": 4, "t0": 1791384842.1417, "t1": 1791384881.7848, "dwell_s": 39.6431,
      "hwnd": "0x000206C4", "key": 1628,           // key = PID (o colapso por app)
      "merged_windows": 2,                          // 2 janelas do Chrome viraram 1 segmento
      "titles": ["Auditoria completa … - Google Chrome", "ping … - Google Chrome"],
      "focus": { /* … */ }, "queue": [ /* … */ ], "reason": "foreground-event" }
  ],
  "transitions": [
    { "t": 1791384881.7848,
      "from": { "pid": 1628, "exe": "…\\chrome.exe", "title": "…" },
      "to":   { "pid": 25544, "exe": "…\\chatterino.exe", "title": "Chatterino 2.5.3" },
      "queue_at_transition": [ /* a fila no INSTANTE da transição */ ],
      "audio_segment_id": "aud-1",
      "audio_continues": true }                     // -> ": audio continua"
  ],
  "join_key": "temporal containment"                // audio.start <= focus.t < audio.end
}
```

**Como a narrativa do dono se representa.** A frase pedida, verbatim:

> *"usuario esta no foco do app x: audio com falas tocando...:usuario focou no app y: audio
> continua... usuario voltou pro x: audio continua..."*

- `x → y → x` = **três segmentos consecutivos** com `key` (pid) `x`, `y`, `x`, e a
  excursão `y` com duração mínima (o oráculo usa ≥0,5 s para excluir o ruído do
  Alt+Tab/`XamlExplorerHostIslandWindow`, que dura ~10-60 ms).
- `: audio com falas tocando` = o **primeiro** segmento tocado por um segmento de áudio.
- `: audio continua` = **o MESMO `audio_segment_id` contém `focus.t` do novo segmento**.
  É contenção temporal, nada mais: **não se afirma que o áudio veio daquela app** (§6).

**Narrativa real produzida (arm A, nível APP, painel removido) — o formulário do dono,
sobre apps reais:**

> usuario esta no foco do app WindowsTerminal.exe(Pesquisa e roadmap do clone do H:\aireplay)
> : audio com falas tocando ... usuario focou no app chrome.exe(Auditoria completa do app e
> redesign — DeepSeek Harness - Google Chrome) : audio continua ... usuario focou no app
> explorer.exe : audio continua ... usuario voltou pro WindowsTerminal.exe(…) : audio
> continua ... usuario voltou pro chrome.exe(…) : audio continua ... usuario focou no app
> chatterino.exe(Chatterino 2.5.3) : audio continua ... usuario voltou pro chrome.exe(ping —
> DeepSeek Harness - Google Chrome) : audio continua ... usuario focou no app
> wgc-probe.exe(wgc probe) : audio continua ... (+ 23 transições)

E a **outra cor**: a mesma narrativa ao **nível da JANELA** está cheia de
`usuario voltou pro pythonw.exe(Sotto) : audio continua` — a **fuga do painel** que o
colapso por app e a regra título+classe removem. As duas versões estão no `.json`
(`narrative_real.text` e `narrative_real.text_at_window_level`).

---

## 5. Limites medidos e armadilhas (o que a medição ensinou)

### 5.1 A latência tem um chão de 1 ms
`dwmsEventTime` e `GetTickCount64` são ambos de 1 ms. A diferença é um **PISO**: reporta-se
`latency_ms` (piso) **e** `latency_hi_ms` (piso+1). "0 ms" significa **<1 ms**, nunca
"instantâneo".

### 5.2 O orçamento de threads
O orçamento de ≤2 threads é do **instrumento**. Um `pythonw.exe` **sozinho** já traz **5**
(`focus-thread-baseline.json`). A lane acrescenta **+1** (a poller): 5 → 6 → 5, com os
mesmos ids de thread antes e depois (`focus-thread-diag.json`).

### 5.3 Nunca deixar janela visível — provado, não afirmado
`0 de 10 791` amostras a 50 ms, com controlo positivo vivo em todas (§2.8).

### 5.4 `stale` — o instante do evento vs o instante da fila
O `hwnd` do gancho está **correcto no instante do evento**, mas a fila é tirada ~2-7 ms
depois. Quando `stale: true` (11 dos 38 eventos da arm A), o foco **já mudou outra vez** e
a fila é um pequeno desvio. O campo existe para que o consumidor saiba disso.

### 5.5 Dois bugs de instrumento encontrados PELOS NÚMEROS
1. **A poller partilhava `last_fg` com o gancho** → o gancho consumia cada mudança primeiro
   e a poller nunca a via: **38 transições de gancho contra 9 da poller na MESMA janela**
   (arm A). Corrigido com um `last_poll_fg` próprio (arm A2) — e é por isso que a arm A
   está marcada `INVALIDO` no relatório do G1 e a contra-prova é a arm A2.
2. **A contagem de razões amostrada (8 slots) mentia** (§2.6). Corrigido com
   `reasons_all` na caminhada inteira.

### 5.6 Nunca matar nada, nunca abrir um dispositivo de áudio
Nenhum processo foi morto. O app do dono (**shell 28428** + **worker 29008**) nunca foi
tocado. **Nenhum dispositivo de áudio foi aberto** — a lane é de foco, não de áudio.
Escritas confinadas a `H:\sotto\_main\`. `worker/`, `app/panel/` e `app/webview/` não foram
tocados.

### 5.7 `Get-CimInstance Win32_Process` nunca em ciclo
Onde era preciso a lista de processos usou-se `psutil` / `Get-Process`. O
`Get-CimInstance` apareceu só em varreduras **únicas** de identificação.

---

## 6. O que NÃO foi possível fazer, e a razão técnica

| # | não feito | razão técnica |
|---|---|---|
| 1 | **Dizer QUAL app produz o som.** | Não existe, no Win32, uma API de foco que diga quem toca. É preciso `IAudioSessionManager2` / `IAudioMeterInformation` por sessão (`GetPeakValue`), que é **outra lane** e **outro instrumento**. Esta lane mede **foco**, não áudio. |
| 2 | **Dizer QUAL aba do navegador toca som.** | O título de uma janela do Chrome é a aba **ACTIVA** dessa janela. Uma aba em segundo plano a tocar áudio é **invisível** para `GetWindowTextW`. Medido: 79 janelas de navegador na fila, 2 títulos distintos do foco — e nenhum deles diz quem toca. (§2.5, G10.) |
| 3 | **Provar que o áudio "veio" da app em foco.** | A junção implementada é **contenção temporal** (`audio.start <= focus.t < audio.end`). Ela prova **co-ocorrência**, não causalidade nem origem. O campo `audio_continues` diz apenas "o mesmo segmento de áudio ainda estava a tocar". |
| 4 | **Medir com segmentos de áudio REAIS.** | A lane do áudio **não forneceu nenhum segmento**. O `audio_source` de todas as junções é `synthetic-span`. O contrato está pronto para segmentos reais; a medição end-to-end com áudio real **não foi feita aqui**. |
| 5 | **Latência abaixo de 1 ms.** | Chão do relógio do Windows (`dwmsEventTime` e `GetTickCount64` a 1 ms). Reportado como piso + piso+1. |
| 6 | **Impedir AO VIVO a fuga das 6 outras instâncias do shell Sotto.** | Elas apareceram **depois** do arranque da arm e foram apanhadas por **análise offline** (a regra título+classe), não por uma guarda em tempo real. A lista de pids do arranque é insuficiente — está medido (G4, vermelho) e é a correcção a fazer. |
| 7 | **Arm B com os campos de thread.** | A arm B correu com o código da sonda **anterior** à correcção, portanto `threads_before_poller`/`threads_with_poller` são `null` nessa arm. O **modo `poll-only` não é afectado** (é a poller sozinha, sem gancho). O mesmo vale para a arm A, cujo summary é anterior aos campos de thread. As arms A2, D e E têm os campos. |
| 8 | **A contagem de razões do cloaked na arm A.** | A arm A só tem a amostra de 8 slots, enviesada para o topo da ordem Z (foi essa a lição). A contagem na caminhada inteira só existe a partir da arm E — e é a arm E que o G3 cita. |
| 9 | **O gancho perdeu 5 transições na arm A.** | Medido (`hook_missed_vs_independent_poller: 5`) — mas essa arm é a **inválida**, em que a poller partilhava `last_fg` com o gancho. Na arm A2 (poller independente) o gancho **perdeu 0**. Fica declarado que a arm A não serve para essa afirmação. |

**O que fica aberto para a outra metade:** a origem do áudio por sessão
(`IAudioSessionManager2` → pid → cruzar com `focus.pid`), e a aba que toca. Nada disto foi
tentado aqui.

---

## 7. Ficheiros criados — sha256 e tamanho

Todos em `H:\sotto\_main\`. Hashes recolhidos **depois** da última edição da sonda e do
oráculo.

### 7.1 Código

| ficheiro | bytes | sha256 |
|---|---|---|
| `focus-timeline-probe.py` | 30 943 | `B92BB7A9FC248666C498CBB47FFF9C9C51970BD631EF0490E94DF54C5FD614AC` |
| `focus-timeline-oracle.py` | 41 034 | `8CA1B1FA98752797D6CFD75EC5D3628EF5AC4AF16438C5929C29B5E03E9575DC` |
| `_focus-launch.py` | 736 | `231637DAC600635A20CA68B9192B151BA12D2D024419A9FBF16017B424DBA6E1` |
| `_focus-window-census.py` | 4 905 | `F74EA507740CCD8DB143572F36127C45E07731BA3C9C1C9F92B6B3E6F8FD9F58` |
| `_focus-cloak-census.py` | 6 018 | `B013DEE648A0231130057CB7A8118E15C97DA400448634C60FB6A5A8CF607872` |
| `_focus-title-oracle.py` | 7 816 | `F14648CFE96967F0E37436ABC8F759EA0C882CCD52341BE2FD7293D70B6FC9A2` |
| `_focus-thread-baseline.py` | 1 353 | `1B9DDBCF77007320ED33D2E264433E561F39A693EB84F0929658186466453C16` |
| `_focus-thread-diag.py` | 2 089 | `991CAB0EFDA04930B48D446588EB014F6BD44CBDA5E8A7C2B0B4F43FC6D501A6` |

### 7.2 Dados — as arms

| ficheiro | bytes | sha256 |
|---|---|---|
| `focus-timeline-A-live.jsonl` | 213 406 | `C2D01D1C8DE59A9D75FE682A70C8B38DE8AB482A103AB2AD30F920B99CA407DA` |
| `focus-timeline-A-live-summary.json` | 3 172 | `59B45396D3270A0BFCA23B2B47E973436070FCEC4F3E18F89FAC3FD8A1D7ADC5` |
| `focus-timeline-A-census.json` | 813 | `762DF5685EB2FA32ABE14151AFF67CCD75191D7B8AFF370BF109B4BB47CA4EA0` |
| `focus-timeline-A2-live.jsonl` | 43 254 | `570BFCCC2E000B61A1F5D997BEB4A4763AE6CCF547BA329E6B264DB8722414B2` |
| `focus-timeline-A2-live-summary.json` | 3 265 | `2B9AA48F4C1072045895DFC812081FD9DEF28AD2B1C133D657B350162468D868` |
| `focus-timeline-A2-census.json` | 783 | `72B0E6DC339FAA6D19DF0CE5AEBD52E10AD7E4AF8395BAD6C8B81F7F7E4DCFAC` |
| `focus-timeline-B-poll1s.jsonl` | 45 969 | `6A2E10AD4DFA02DF2EA56C05B60F4D13A9CD348E6C33903937D1A97E19F98F66` |
| `focus-timeline-B-poll1s-summary.json` | 3 009 | `310073BFE809770896C5000DC58315F85688020D688AA25DB5493B2345D9A50F` |
| `focus-timeline-C-nofilter.jsonl` | 122 078 | `703BA50602F1A09972055D3F96DD4D77942087571C0AB650DF5067E5A610418A` |
| `focus-timeline-C-nofilter-summary.json` | 3 182 | `74BE8A79CEE22C19164D004465FF9C490287FA1BE42092624E688E0E058DBB5A` |
| `focus-timeline-D-title.jsonl` | 87 696 | `9A54D84963AED1BDB9C2F8580EA2AF1E8C79EAA9822AA6073A94049CBEC6CA4F` |
| `focus-timeline-D-title-summary.json` | 3 268 | `41F8CBD4523A692BBC8AF321423DBB0550396AD1AF6AAAC6D89CECB976F896E0` |
| `focus-timeline-E-reasons.jsonl` | 15 850 | `D20803CAE4504C5B4BF56C202B86B45A8F84D7AB352DFC273E55A0EE1B48ECFE` |
| `focus-timeline-E-reasons-summary.json` | 3 395 | `AB9ACB4D765147610F81C5CB94DA0BF874DB3621D309F4B28260582599D6EFD5` |

### 7.3 Dados — oráculos e diagnósticos

| ficheiro | bytes | sha256 |
|---|---|---|
| `focus-timeline-oracle.json` | 323 680 | `C5438B9D66994C14A211014431C5AA995FBE9CF9941B810A3F04C87F920FC00D` |
| `focus-timeline-oracle.txt` | 4 244 | `8D04424CCF06CF9D3AA4F9C9A54140D039853E2FA4510A1807F4E79624E58ED1` |
| `focus-cloak-census.json` | 4 767 | `BA1B2FFA38BE6A298A3340E2DAD13366D82ECF931482B5E759FA1DA9182B7978` |
| `focus-title-oracle.json` | 141 778 | `3F5B5B1314097B2D3380F60A12F2386069A1FBBABB6946B6E0FC132FF9581EAA` |
| `focus-thread-baseline.json` | 264 | `5AACDE1721663D0CCD7D32450C69D020CAF9927E4B9C8A08E48FE32FC760BE1A` |
| `focus-thread-diag.json` | 1 041 | `90FCBE766CFD984516EE14D982EB3749BE44ACCB012E28020225B5CD46F7626B` |

### 7.4 Logs de lançamento e de arms

| ficheiro | bytes | sha256 |
|---|---|---|
| `_focus-arms.log` | 367 | `70052077C67939D952B86584983C81098AB6B81544DEB5C0E5231414B3990380` |
| `_focus-arms2.log` | 188 | `443D6432B12D28F151F9792DBF69F868BF9135CC055EB0BD931DA01C3D380FE6` |
| `_focus-arms3.log` | 101 | `D72D8182C1C98AEF87B31A326549773DB39B9A7925A3B27BD42965BE6CCF7BF7` |
| `_focus-err-A.log` | 30 | `ABB650D473CD7AC838753EB4B58F3EACE1F1B77BCE84244B4CA0166AF3C42C54` |
| `_focus-err-A2.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |
| `_focus-err-B.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |
| `_focus-err-C.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |
| `_focus-err-D.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |
| `_focus-err-E.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |
| `_focus-err-cen.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |
| `_focus-err-cloak.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |
| `_focus-err-orc.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |
| `_focus-err-tt.log` | 15 | `1E572E5AC2FFCCD07BDB0020D1E250D65B2521B5E1F90C8E86561C2DB9A8B398` |

Os `_focus-err-*.log` de **15 bytes** contêm todos `SystemExit: 0` — saída limpa, sem
traceback. O `_focus-err-A.log` (30 bytes) tem duas linhas (a arm A correu em duas fases).

**Total: 39 ficheiros criados** (8 de código, 20 de dados, 6 de oráculo/diagnóstico,
5 de log agregado, 13 logs de lançamento — contando os logs de 15 B que são idênticos
byte a byte e por isso partilham sha256).

---

## 8. Como reproduzir

```powershell
# a sonda (300 s, filtro ligado, poller a 15 ms) -- em background, nunca numa chamada curta
pythonw.exe H:\sotto\_main\_focus-launch.py H:\sotto\_main\_focus-err-A.log `
  H:\sotto\_main\focus-timeline-probe.py --mode live --secs 300 --poll-ms 15 `
  --jsonl H:\sotto\_main\focus-timeline-A-live.jsonl `
  --summary H:\sotto\_main\focus-timeline-A-live-summary.json `
  --note A-live

# o censo do próprio pid, em paralelo (50 ms)
pythonw.exe H:\sotto\_main\_focus-launch.py H:\sotto\_main\_focus-err-cen.log `
  H:\sotto\_main\_focus-window-census.py --secs 300 --cadence-ms 50 `
  --watch-pid <pid-da-sonda> --control-pid <pid-em-foco> `
  --json H:\sotto\_main\focus-timeline-A-census.json

# o oráculo: as 10 portas, as duas cores de cada uma
py -3 H:\sotto\_main\focus-timeline-oracle.py --report H:\sotto\_main\focus-timeline-oracle.json
```

`--note` **não pode conter espaços** — `Start-Process -ArgumentList` não cita elementos de
array com espaços e o argparse morre com `SystemExit: 2` (erro já cometido e corrigido).

---

## 9. Resumo de uma linha

**O gancho `EVENT_SYSTEM_FOREGROUND` dá a linha temporal de foco com <1 ms em 97 % dos
eventos (80 eventos de gancho medidos), a fila em ordem Z com 0 fantasmas em 10 791
amostras vigiadas, e o `x → y → x` do dono sai limpo ao nível da APP (3 padrões, o melhor
`chrome.exe → chatterino.exe → chrome.exe` com 39,6 s / 5,6 s / 14,6 s) — e NÃO diz qual
app toca som, porque isso é outra lane e outra API.**
