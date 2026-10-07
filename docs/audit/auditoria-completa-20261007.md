# Auditoria completa — Sotto (`H:\sotto`), 2026-10-07

**Pedido do dono (verbatim):** *"faz full audit do app. tem varias coisas quebradas e nao
funcionando e design ruim e display ruim. tambem compara pesquisando online como cada modelo
deve ser usado"*.

**Alcance:** todo o app (`app/webview` = a app; `app/electron` = o painel que as duas shells
hospedam + a shell legada; `worker/`; `worker/config.json`) e os modelos do stack
(Nemotron 3.5 ASR streaming 0.6B + export ONNX/ORT-GenAI, Silero VAD, Parakeet Redux,
`transcribe.cpp`), comparados com a documentação upstream.

**Como ler a coluna `conf`:** `medido` = corri o instrumento e vi o número;
`medido(repo)` = o repo já tem o recibo, citado; `código` = lido no ficheiro, linha citada;
`raciocinado` = inferência com o falsificador nomeado.

---

## 0. Limite desta sessão — o que NÃO consegui medir (e porquê)

Não arranquei a app nem um browser headless nesta sessão: **o sandbox desta sessão recusa as
duas coisas**, e isso fica registado para não se confundir com defeito do produto.

| tentativa | resultado | causa |
|---|---|---|
| `pythonw sotto_webview.py --no-hotkey --log …` | o shell morre depois de `HOT_RELOAD_DISABLED`; `webview.start()` levanta | `pythonnet` → `System.ComponentModel.Win32Exception: **Acesso negado**` em `Process.GetProcessHandle` → `Python.Runtime.Platform.WindowsLoader.GetAllModules()`; logo `RuntimeError: Failed to initialize Python.Runtime.dll`. Receipt: `_main/_audit-probe/plain.log.stderr` |
| `python -c "import clr"` (mínimo) | falha igual, fora da app | idem — é o sandbox, não o Sotto |
| `msedge --headless=new --screenshot …` (para fotografar o painel) | `FATAL:mojo\public\cpp\platform\platform_channel.cc:187 Check failed: Acesso negado` | o sandbox bloqueia *named pipes*; o Chromium não arranca |

**Consequência para esta auditoria:** não há captura de ecrã. Todas as afirmações de *display*
vêm de (a) os ficheiros `panel.html` / `panel.css` / `panel.js`, (b) as medições que o próprio
repo já registou (`_main/panel-state.json`, `app/electron/_dom-probe-*.json`,
`_main/panel-paint-probe.log`, `_main/webview-run.log`, 2,3 MB de corridas reais),
(c) execução dos módulos DOM-free em Node, e (d) uma receita nova (§2.2).
Deixei o harness de render pronto mas NÃO executado (`_main/_audit-render/`), para quem tiver
um sandbox que permita Edge headless.

---

## 1. Veredito

A app **funciona em pedaços e mente em três sítios**:

1. **O arranque documentado não liga o worker.** `run.cmd` (o que o dono clica) não passa
   `--with-worker`, e `main()` só arranca o worker sob esse flag. Resultado: Alt+C abre um
   painel que diz "Waiting for audio" e **nunca transcreve nada**.
2. **A metade de cima do painel é inalcançável por construção.** O "History · Redux" aceita
   apenas linhas com `producer:'redux'`, e **nada no repo escreve esse campo**: feed, busca,
   "Show in folder" e todo o writer de histórico do shell estão mortos. O `history/` parou de
   crescer em **2026-10-06 19:58**.
3. **O worker pode terminar "com sucesso" sem uma única legenda.** `done.verdict` pode ser
   `captions-emitted` com `captions: 0` → exit 0 → a shell pinta um fim saudável.

E cinco coisas quebradas a seguir em gravidade: o tap WASAPI **nunca é fechado** numa rotação
(o endpoint abandonado continua a alimentar a fila e os contadores do veredicto); o **hot
reload do painel parte o painel**; a guarda `provisionalRoute` **não pode ser verdadeira**; o
**Hot reload do painel** (de novo, porque perde legendas até reiniciar); e a app **não tem
como ser fechada** a partir da própria UI.

Tabela de achados (detalhe nas secções seguintes):

| id | sev | conf | título | onde |
|---|---|---|---|---|
| **F1** | P0 | código + log | o arranque documentado (`run.cmd`) não arranca worker nenhum → Alt+C nunca transcreve | `app/webview/run.cmd:155`, `app/webview/sotto_webview.py:1824-1825, 2454-2471, 3923-4022` |
| **F2** | P0 | medido | o HISTORY não pode ser alimentado: nenhuma meta do motor live traz `producer` → 0 linhas no disco | `app/electron/history-source.js:51,61-63`, `panel.js:335-351`, `caption-formulation.js:408`, receipt `_main/_audit-probe/history-dead.log` |
| **F3** | P0 | código + medido(repo) | `done.verdict="captions-emitted"` com `captions:0` e exit 0 | `worker/sotto_worker.py:2862, 3030` |
| **F4** | P0 | código + medido(repo) | o tap WASAPI nunca é fechado na rotação; o endpoint abandonado continua a entregar áudio e a somar contadores | `worker/sotto_worker.py:2574-2579`, `worker/wasapi_loopback.py:723-730, 930-943` |
| **F5** | P1 | medido(repo) | o hot reload do painel navega para `file://…panel.html?sotto_hr=N` → `chrome-error://chromewebdata/`, o painel deixa de pintar até reiniciar | `app/webview/sotto_webview.py:2517` |
| **F6** | P1 | medido | guarda morta: `panel.js` lê `engine.state().provisionalRoute`, campo que o motor nunca devolve | `panel.js:104` vs `caption-formulation.js:582-586` |
| **F7** | P1 | código | a app **não tem como ser fechada** pela UI: `quit` existe na ponte e nenhum controlo o chama | `panel.js` (0 chamadas), `sotto_webview.py:1234`, `preload.js:103`, `main.js:877` |
| **F8** | P1 | código | dois classificadores independentes do mesmo status; o do painel é uma regex de prosa que não conhece o vocabulário do worker | `panel.js:619` vs `sotto_webview.py:289-311` |
| **F9** | P1 | raciocinado | o campo de busca do painel não pode receber teclado: a janela é `WS_EX_NOACTIVATE` + `focusable(false)` e é mostrada com `SW_SHOWNOACTIVATE` | `sotto_webview.py:1474-1476, 630-631, 2373-2384` |
| **F10** | P1 | medido(repo) | RTF > 1 na CPU: a app não acompanha a fala em tempo real; CUDA é pedido e não carrega | `_main/_review-segrerun.out`, `docs/model-specs/README.md:130-146` |
| **F11** | P2 | código | `max_symbols_per_step: 10` é usado como orçamento do *chunk*, não por frame | `worker/sotto_worker.py:466,736,750-780` vs `docs/model-specs/README.md:83-85` |
| **F12** | P2 | código | o segundo passe (M3) não repõe o front-end cache-aware nem o VAD (`self.sp`), e não há reset na rotação de dispositivo | `worker/sotto_worker.py:567-587, 2365, 2443-2445` |
| **F13** | P2 | código | `model.lang_id` ausente cai no locale do host (`os`), não no `auto` documentado | `worker/sotto_worker.py:1971-1974`, `worker/lang_prompt.py:236-254` |
| **F14** | P2 | código | `use_vad` no código tem default `False` e contradiz `config.json`/docs; `create_streaming_processor()` é incondicional | `worker/sotto_worker.py:2004, 499-500` |
| **F15** | P2 | código | o candidato de dispositivo é ordenado UMA vez no arranque; a cura documentada (`prefer_rendering_now`) não existe | `worker/wasapi_loopback.py:594` (sem caller), `docs/audit/ordem-dos-candidatos.md:152` |
| **F16** | P2 | código | `GetBuffer` chamado com 4 de 5 parâmetros (o 5.º, `pu64QPCPosition`, é out-pointer) | `worker/wasapi_loopback.py:855-863, 892` |
| **F17** | P2 | código | `asr.labels` + `done.text` crescem sem limite e saem numa única linha JSONL no fim | `worker/sotto_worker.py:526, 771, 3023` |
| **F18** | P2 | código | excepções fora dos poucos `try` escapam ao contrato JSONL (EOF sem `done`/`error`) | `worker/sotto_worker.py:808-810, 1482, 1966, 2100` |
| **F19** | P2 | código | `docs/AGENTS.md:102` (contexto auto-carregado por TODOS os agentes) afirma que o segundo passe está AUSENTE — é falso nesta revisão | `AGENTS.md:102` vs `worker/sotto_worker.py:2325, 567, 511` |
| **F20** | P2 | código | o `README.md` da raiz descreve outro produto (Tauri/Rust/Svelte, "Status: Planning") enquanto a app WebView2 existe | `README.md:48-64` |
| **D1-D9** | Design | código | ver §3 | `panel.html`, `panel.css`, `panel.js` |

**O que está bem** (§5): a geometria (clamps reais), o caminho rato/click-through
(**medido: 50 toggles** `POINTER_INTERACTIVE`), a disciplina de stdout do worker, o
vocabulário de saída (exit 3 + `silent-device`), a arquitectura de linhas/segundo passe
(que é literalmente o desenho que a Azure documenta para legendagem ao vivo) e o estilo da
linha provisória.

---

## 2. Quebrado

### F1 — P0 — o arranque documentado não liga worker nenhum

- **Onde:** `app/webview/run.cmd:155` (a linha que spawna o shell) passa apenas `--log`,
  `%*` e `--ready-file`; `app/webview/sotto_webview.py:1824-1825` chama `start_worker` **só**
  dentro de `if self.args.with_worker:`; `main()` (:3923-4022) não tem nenhum arranque
  incondicional do worker; a única outra chamada é o reinício do hot reload (:2559).
- **Medido no log real (`_main/webview-run.log`, 2,3 MB):** 32 arranques de shell, **10 com
  worker, todos com `reason=with-worker`**; nenhum arranque default tem `WORKER_AUTOSTART`.
- **Objectão prevista, verificada:** os únicos sítios no repo que passam o flag são
  instrumentos de lanes — `_main/_app-drive.py:75` (`run.cmd --with-worker`,
  "Drive the OWNER'S APP") e `_main/_live-launch.py:15-16` (`--with-worker`, cujo docstring diz
  "launch the app the owner's way" *e depois acrescenta o flag*). Não há atalho no Desktop, no
  menu Iniciar nem chave `Run` a apontar para o Sotto (verifiquei), e `README.md` da raiz não
  documenta o `--with-worker` (nem conhece esta app, §7). Ou seja: quem carrega em Alt+C pelo
  caminho que está escrito **não** ouve nada.
- **Efeito:** duplo-clicar `run.cmd`, carregar Alt+C → painel bonito a dizer
  "Waiting for audio / Nothing is being transcribed yet", com o rodapé "Idle · no audio source",
  **para sempre**. O dono vê uma app a fingir que está à espera de áudio quando não existe
  sequer processo de transcrição. Isto é a aceitação dele ("*que o alt c mostre as transcricoes
  em tempo real, de qualquer audio do meu pc*") a falhar no caminho mais óbvio.
- **Correcção mínima:** ou `run.cmd` passa `--with-worker` por omissão (e `--no-worker` para
  desligar), ou `main()` arranca o worker sempre que não foi pedido `--no-worker`. A segunda é
  preferível: mantém a wrapper sem tabela de flags própria.
- **Correcção melhor:** o painel deve dizer o que é verdade — sem bridge, "captions are
  impossible" (já existe essa mensagem em `panel.js:62-68`); com bridge e sem worker, tem de
  dizê-lo em vez de "Idle · no audio source".

### F2 — P0 — o HISTORY ("History · Redux") não pode ser alimentado

- **Onde:** `app/electron/history-source.js:51` (`CANONICAL_PRODUCER = 'redux'`), `:61-63`
  (`isCanonicalLine` exige `meta.producer === 'redux'`), `panel.js:335-351` (o choke point:
  `route !== 'final'` → recusa, e depois `isCanonicalLine` → recusa).
- **Receita nova (`node _main/_audit-history-dead.js` → `_main/_audit-probe/history-dead.log`):**
  o motor REAL, alimentado com o formato do worker (`final:false` … `final:true`), entrega ao
  painel exatamente

  ```
  meta={"route":"final","start":0,"routeSource":"worker-stamped"}
  ```

  — **sem `producer`**, porque `caption-formulation.js:408` constrói a meta com três chaves
  literais. O predicado REAL recusa; o store REAL grava **0 linhas**.
- **`grep -r "producer"` no repo inteiro:** só existe em `history-source.js`, nos comentários,
  no oráculo e nos recibos. **Nenhum código escreve `producer:'redux'`.** E o motor batch que
  poderia escrevê-lo (Parakeet Redux) não está no disco nem tem call site.
- **Efeito:** a metade superior do painel — feed, busca, "Show in folder" por linha, o
  `history_append`/`tail`/`search` do shell (1933 escritas históricas no log, hoje 0) — é
  **decorativa**. E o arquivo do dono parou: o ficheiro mais recente em `history/` é
  `history/2026-10-06/19.md`, mtime `19:58:36`.
- **O erro de processo que isto revela (e é o que importa corrigir):**
  `_main/live-vs-history-source-oracle.js` está **VERDE** — e o braço que devia provar que o
  caminho canónico está *aberto* **injeta ele próprio** `producer:'redux'` (`:219`), enquanto o
  braço "AS SHIPPED" monta a meta à mão sem copiar `producer` (`:111-117`). Ou seja: o gate
  afirma um caminho que nenhum código percorre. É a mesma classe de defeito que este repo já
  nomeia ("um gate que não pode dizer não" — aqui: um gate que só testa a parte que ele mesmo
  alimenta).
- **Correcção mínima:** um braço novo no oráculo que faça a pergunta em falta — "algum produtor
  do repo carimba `producer`?" (grep + a meta REAL do motor) → fica VERMELHO hoje. Fechar o
  buraco a sério exige o motor batch; até lá, o painel não deve fingir que tem histórico (§3, D1).

### F3 — P0 — "captions-emitted" com zero legendas

- **Onde:** `worker/sotto_worker.py:2862` — um `else:` incondicional.
- **Reprodução (lida no código):** chega-se lá sempre que falham todos os predicados anteriores,
  incluindo `captions == 0` com `vad_gated_chunks == 0` e `music_gated_chunks < chunks` — por
  exemplo com `use_vad` a falso (default do código, F14) ou com uma stream que o VAD deixa passar
  e o modelo não descodifica. Também engole o caminho de excepção do thread de ASR
  (`:2496` emite `state="error"`, põe `stop` e retorna → o `else` de `:2862` emite `done` e o
  `return 3 if ran_but_silent else 0` (`:3030`) devolve **0**.
- **Efeito:** `{"state":"done","verdict":"captions-emitted","captions":0}` → a shell trata
  `captions-emitted` como fim saudável (`HEALTHY_DONE_VERDICTS`) → o painel mostra um fim
  normal com o transcript vazio. É a mesma mentira que o comentário em `:2791-2796` diz ter
  sido curada para o caso "all-flat".
- **Correcção:** exigir `captions > 0` no predicado do `captions-emitted` e nomear o caso
  contrário (`model-emitted-nothing` / `captions-zero`) com exit não-zero.

### F4 — P0 — o tap WASAPI nunca é fechado numa rotação

- **Onde:** `worker/sotto_worker.py:2574-2579`

  ```python
  def close_tap(t):
      try:
          t.stream.stop()      # WasapiLoopbackTap não tem stop()
          t.stream.close()
      except Exception:
          pass                 # ← engole o AttributeError
  ```

  `worker/wasapi_loopback.py:723-730`: a propriedade `stream` devolve `self`; a classe tem
  `start` (`:732`), `close` (`:930`), `_start`, `_open`, `_pump` e **nenhum `stop`**
  (`grep "def stop"` → 0). Logo `close()` — o único sítio que faz `self._stop.set()`, chama
  `IAudioClient::Stop` e liberta as referências COM — é **inalcançável**, e `__exit__` também
  (o worker nunca usa `with`).
- **Efeito:** a thread `_pump` abandonada continua a chamar `on_block(...)` → continua a
  empurrar áudio do endpoint abandonado para `audio_q` e a somar `blocks`/`block_samples`/`peak`
  — exatamente os números de que dependem o veredicto `silent-device`, o `proved_alive` e o
  **exit 3**. Áudio de um dispositivo que a corrida diz ter deixado pode virar legenda.
- **Medido(repo):** `worker/runs/gate-live-silence.jsonl:12` fecha com `blocks=181`,
  `block_samples=680000`; resolvendo com os dois tamanhos de bloco (4800 no WASAPI, 1600 no MME)
  dá 122 callbacks WASAPI contra 60 creditados no ledger (`:11`) — ~60 callbacks extra do tap
  abandonado, atribuídos ao candidato seguinte. `gate-live-drone.jsonl:18` mostra as duas
  janelas a seguir ao abandono a ~2× a cadência do código (122 e 119 contra 10/s).
- **Falsificador nomeado:** um probe que abra dois taps, feche um com o caminho real e conte as
  chamadas de `on_block` por dispositivo depois do fecho (esperado hoje: ≠ 0).
- **Correcção mínima:** `close_tap` deve tentar `close()` primeiro (idempotente) e nunca
  engolir em silêncio; melhor: pôr um `stop()` real na classe, e fazer o ledger marcar cada
  bloco com o `gen` do tap que o entregou.

### F5 — P1 — o hot reload do painel parte o painel

- **Onde:** `app/webview/sotto_webview.py:2517`:
  `url = file_url(PANEL_HTML) + f'?sotto_hr={self.reload_count}'`.
- **Medido(repo, AGENTS.md + `docs/audit/*`):** depois de um `HOT_RELOAD_PANEL_DONE`, o
  `_main/panel-state.json` lê `panel.url = chrome-error://chromewebdata/` e `panel.live.count = -1`
  (sentinela de `#caption-list` ausente). Reproduzido duas vezes em 2026-10-06.
- **Efeito:** o dono edita o `panel.css`/`panel.js` (a feature que existe para ele), e o painel
  deixa de pintar legendas até reiniciar a app. É uma funcionalidade que se auto-destrói.
- **Correcção:** não pôr query-string num `file://` (o `?` não é carácter legal em nome Windows).
  Cache-busting por outro caminho: `location.reload(true)`-equivalente no WebView2
  (`core.Reload()`), ou navegar para uma segunda página `stage.html` e voltar, ou copiar o
  painel para um ficheiro com nome versionado.

### F6 — P1 — uma guarda que não pode ser verdadeira

- **Onde:** `panel.js:104` — `if (engine.state().provisionalRoute) armHoldTimer();`
- **Medido (executei o motor real):** `Object.keys(engine.state())` =
  `committed,provisional,lastAudioEnd`. `provisionalRoute` é `undefined` **sempre**.
- **Efeito:** o "re-armar o deadline enquanto o motor segura uma linha provisória" nunca
  acontece; hoje está mascarado porque `armHoldTimer()` corre em cada `onCaption`. Qualquer
  refactor que confie neste ramo fica silenciosamente morto.
- **Correcção:** ler `engine.state().provisional.length > 0` (campo que existe).

### F7 — P1 — a app não tem como ser fechada

- **Onde:** `panel.html` não tem controlo de saída (grep `quit|Exit|Close` → 0);
  `panel.js` nunca chama `bridge.quit()` (0 chamadas); a ponte implementa-o
  (`sotto_webview.py:1234` → `shell.quit`, `preload.js:103` → `ipcMain.on('sotto:quit')`,
  `main.js:877`).
- **Efeito:** a app (uma janela sem moldura, `skipTaskbar=true`, sem ícone de tabuleiro, sem
  entrada de menu Iniciar — verifiquei: não há atalhos nem chaves `Run`) só se fecha por
  Task Manager. Desligar o PC ou matar o processo `pythonw` são as únicas saídas.
- **Correcção:** um botão de saída no cabeçalho (já há espaço e um padrão de ícones) ou um menu
  de contexto; e/ou um ícone de tabuleiro com Sair.

### F8 — P1 — dois classificadores para o mesmo status

- **Onde:** o shell classifica em `worker_status_kind` (`sotto_webview.py:289-311`, com o
  vocabulário do worker, `HEALTHY_DONE_VERDICTS`, etc.) e o painel **reclassifica por regex de
  prosa** em `panel.js:619`: `/stopped|error|dead|no audio|no working/i`.
- **Efeito de desenho:** o `kind` que o shell calculou é **descartado** (o handler do painel
  recebe só `text`: `bridge.onStatus((text) => …)`), e a regex não conhece
  `device-exhausted`, `silent-device` nem `done` sem veredicto. Hoje o resultado final é salvo
  pela ORDEM (o shell faz `send_status` e depois um `exec_js` que volta a pôr título/severidade
  — `apply_panel_state`, `:2002-2015`), mas a pintura correta depende dessa ordem não declarada.
  Estado conseguido: o painel pinta "à prova de hoje", por sorte.
- **Correcção:** `onStatus` deve receber `kind` (a ponte já o tem) e `panel.js` não deve
  reclassificar nada; uma fonte de verdade.

### F9 — P1 — o campo de busca não pode receber teclado (raciocinado)

- **Onde:** `sotto_webview.py:1474-1476` põe `WS_EX_NOACTIVATE` na janela; `:630-631` mostra-a
  com `SW_SHOWNOACTIVATE`; o pywebview cria-a com `focusable=false` (log de arranque:
  `panel setFocusable(false) ok (WS_EX_NOACTIVATE)`).
- **Raciocínio:** uma janela `WS_EX_NOACTIVATE` não se torna foreground num clique; logo o
  foco de teclado nunca entra nela e o `<input type="search" id="search-input">`
  (`panel.html:120-128`) nunca recebe caracteres — e pior, escrever com o painel à frente
  manda as teclas para a janela que estava em foco (a app de trás).
- **Falsificador nomeado:** com o painel visível, `SendInput`/`WM_CHAR` no campo e ler
  `document.activeElement` + o valor do input via `exec_js`.
- **Nota:** isto não é um bug de teclado isolado — é a contradição de desenho mais funda do
  painel: ele traz uma UI interativa (input, busca, botões) numa janela construída para nunca
  receber foco. E, com F2, a busca não teria o que devolver de qualquer forma.

### F10 — P1 — na CPU a app não acompanha a fala

- **Medido(repo):** `_main/segment-rerun-probe.py` imprime `RTF 5.843` (85,07 s de parede para
  14,56 s de áudio) na caixa carregada; o recibo da lane, na mesma caixa ociosa, mede
  **1.567 streaming / 0.821 no passe** (`_main/review-20261007-sotto-changes.md:70-74`).
  RTF > 1 significa **mais lento que o tempo real**: a legendagem atrasa-se de forma
  acumulada, enche `audio_q` (`queue_drops`) e o `LineFormer` fecha linhas por
  `chars`/`gap` muito depois de a fala ter passado.
- **Contexto upstream:** `CUDAExecutionProvider` é pedido e o ORT devolve só CPU
  (`docs/model-specs/README.md:130-146`); a NVIDIA mede 6× tempo real em CPU com chunks de
  160 ms Q8_0 noutra máquina — não há milagre a esperar deste binário nesta caixa.
- **Correcção (de produto):** ou a rota GPU (`docs/gpu-route-20261006.md`), ou um export com
  chunk menor (ver §4.1 — a latência é do export, não do código), ou dizer no painel que a
  transcrição está a correr atrás (e não fingir tempo real).

---

## 3. Design e display

Tudo abaixo é `código` (os ficheiros do painel) salvo indicação. Não há captura de ecrã (§0).
O painel tem 380×900 (o `dock_right` encolhe em ecrãs pequenos: `min(900, h-2m)`, largura
`min(380, 34% do work area)` — esta parte está boa).

| id | defeito | onde | porque é defeito | correcção |
|---|---|---|---|---|
| **D1** | **44% do painel é um feed que fica vazio para sempre.** A grelha é `auto minmax(0,1fr) minmax(0,1.25fr) auto` → o History leva `1/2.25 ≈ 44%` da altura útil (~338 px de 761), e com F2 nunca tem uma linha. Sobra uma caixa, uma nota e uma caixa de busca que nunca encontra nada | `panel.css:71-91`, `panel.html:107-158` | o olho vai para o vazio; a app parece avariada (e está, do lado do dado) | enquanto não existir motor batch, o History não deve ocupar metade do painel: recolher a uma linha ("a transcrição canónica chega quando o passe batch existir") e dar a altura à legenda viva |
| **D2** | **O rodapé corta a causa.** `.status__text` é `white-space: nowrap; text-overflow: ellipsis` e as frases que o shell compõe são longas ("Silent audio device - Mapeador de som da Microsoft - Input [MME] peaked 0.000122 < floor 0.002") | `panel.css:672-678`, `sotto_webview.py:343-347` | os números que justificam a morte são exatamente a cauda que desaparece nos 380 px | permitir 2 linhas no rodapé, ou pôr a causa no placeholder e o rodapé curto |
| **D3** | **O estado inicial é uma afirmação falsa.** `panel.html:189` diz "Idle · no audio source" e o placeholder diz "Waiting for audio… Captions appear here line by line the moment audio reaches Sotto" | `panel.html:174-178, 189`, `panel.js:619-627` (só muda com status) | com F1, nenhum status chega nunca: a app anuncia espera por áudio quando não há worker. "no audio source" também contradiz o próprio repo (há áudio; o que falta é processo) | estado inicial = "sem worker" (o shell sabe-o), e o texto do placeholder a dizer isso |
| **D4** | **A copy de warm-up tem um número congelado**: "measured warm-up on this machine: 7.0 s to the first caption" | `caption-formulation.js:101-119, 173-186` | é uma medição de uma corrida, apresentada como facto permanente ao dono | medir de novo ou dizer "cerca de 7 s" com data |
| **D5** | **Três affordances para uma ação morta**: o botão `#history-root`, o botão "Show in folder" e o 📁 de cada linha chamam todos `revealPath` | `panel.js:242-245, 461-471`, `panel.html:110-152` | redundância + expectativa | um só, e só quando houver linhas |
| **D6** | **Ícone emoji numa UI de SVG** (`folder.textContent = '\u{1F4C1}'`) | `panel.js:466` | inconsistência visual e renderização dependente da fonte de emoji | SVG igual aos outros |
| **D7** | **Rótulos que nomeiam implementação**: "Live · NVIDIA", "History · Redux" | `panel.html:109, 166` | o `Redux` não corre; o `NVIDIA` é o vendor. O dono lê nomes de motores num produto que devia falar de legendas | "Ao vivo" / "Transcrição" (e o nome do produtor, se fizer falta, num tooltip) |
| **D8** | **`user-select: none` em tudo** | `panel.css:57` | numa app cujo produto é texto, não se consegue copiar uma legenda nem uma linha do histórico | `user-select: text` no texto das legendas/histórico |
| **D9** | **Nada se ajusta ao utilizador**: sem tamanho de letra alternativo, sem escolha de idioma/dispositivo/modelo na UI (o `model.lang_id` só existe no `config.json`, embora o modelo suporte 35 locales), sem tema claro, sem mover/redimensionar | `panel.html` (não há settings), `worker/config.json` | o artefacto é um overlay fixo de 380 px para qualquer monitor e qualquer idioma | no mínimo: idioma e dispositivo no painel (o worker já aceita `--device`/`SOTTO_AUDIO_DEVICE`), e um tamanho de letra relativo |

**Não encontrei** defeitos de contraste que valham achado: o `--text-faint` foi ajustado com
medição registada (`panel.css:28-30`) e as cores de texto usadas estão acima de 4,5:1 sobre
`#0b0f14`. O que é *abaixo* do razoável é o **tamanho** (10-11,5 px para rótulos, horas e
*dicas*), não o contraste — e isso é uma escolha, não um erro de cálculo.

Coisas de display que estão CERTAS e não devem ser "arrumadas": `[hidden]{display:none}`
explícito para vencer o `display:flex` do autor (`panel.css:491-493` — defeito real já pago),
`.caption--provisional` com travessão tracejado + itálico (`panel.css:521-530`), que é
exatamente a recomendação da AWS para palavras instáveis; `prefers-reduced-motion`
(`:634-639`); `followNewestLine` só quando já se está perto do fundo (`panel.js:217-221`);
`aria-live="polite"` na legenda viva e `off` no histórico.

---

## 4. Modelo vs documentação — como cada modelo DEVE ser usado

Fontes: cartões HF e código dos runtimes (links inline). Está separado o que é **doc do
modelo**, **doc do runtime** e **inferência**.

### 4.1 Nemotron 3.5 ASR Streaming 0.6B (o motor ao vivo)

**O que a doc diz (e o código cumpre):**

| parâmetro | doc do modelo / export | `worker/config.json` / código | veredicto |
|---|---|---|---|
| `chunk_samples` | **8960 = 560 ms** (`DimQ1/…-int8` `genai_config.json`, e o cartão do export: "Chunk size 0.56s (8,960 samples @ 16kHz)") | 8960 no `genai_config.json` do modelo, lido pelo ORT-GenAI | ✅ |
| `blank_id` | 13087 (`config.json` `"blank_token_id": 13087`, `vocab_size 13088`) | 13087 (`vocab.txt` com 13088 linhas, índice 13087 = `<blank>` — confirmado) | ✅ |
| `max_symbols_per_step` | 10, **por frame de encoder** ("ceiling on one frame's label run") | lido, mas usado como orçamento do chunk: `limit = self.max_sym * T + 16` (`:736`) e um não-branco re-codifica **sem avançar `ti`** (`:750-780`) | ❌ **F11** |
| `left_context` | 70 | 70 | ✅ |
| `lang_id` | default do motor = **0 = en-US**; `auto` = 101; o cartão mede LangID ≥ auto em quase todas as línguas | `config.json` traz `"auto"` (a decisão certa, recebida com medição no `AGENTS.md`), **mas se a chave for apagada o código cai no locale do host** (`os`, = 12/`pt-BR` nesta máquina), não em `auto` | ❌ **F13** |
| VAD (Silero) | o cartão do modelo **não** fala de VAD. 0.3/3360/560 são os valores do export `DimQ1` (copiados para `config.json`); os defaults oficiais do Silero são 0.5/100/30 com histerese `neg_threshold` | 0.3/3360/560 (os mesmos do export) | ⚠️ defensável (vem do export), mas vale saber que **não é normativo** |
| precisão | NeMo **não** suporta `compute_dtype != float32` em modelos cache-aware (`NotImplementedError`); int4 custa ~0,25 pp de WER em inglês vs ~0,02 do int8 (medições do `transcribe.cpp`) | o repo escolheu int8 (`worker/config.json model.dir`) | ✅ boa troca |
| licença | **OpenMDW-1.1**, uso comercial OK; distribuir exige reter a licença + avisos | `README.md:42-44` diz "license:other … must be read before this ships" (gate em aberto) | ⚠️ o gate pode ser **fechado hoje** com a citação da OpenMDW-1.1 |

**Onde o uso do modelo diverge de forma material:**

1. **A latência é do EXPORT, não do código.** O chunk está fixo em 560 ms dentro do ONNX
   (`chunk_samples`, `left_context 70`); o cartão oferece 80/160/320/560/1120 ms. Trocar
   `audio.block_ms` (100 ms no config) só muda a granularidade da captura. Quem quiser
   legenda mais rápida tem de **converter outro export** com `chunk_samples` 1280/2560/5120 —
   e trocar latência por WER (§4.1 da doc: R=13 → 1120 ms para máxima precisão).
2. **O segundo passe não começa de um estado de stream** (F12): `reset_stream_state()` repõe
   `cc/ct/ccl`, `h/c`, `_last_symbol` — mas **nunca** `self.sp` (o front-end mel cache-aware +
   o VAD do ORT-GenAI). O passe re-alimenta os chunks pelo mesmo `run_chunk`, portanto o
   estado vivo entra no passe — e é ESSE texto que sai com `final:true` e que o transcript
   aceitaria. Também na rotação de dispositivo: o código repõe `agc` e `asr.gate` (`:2443-2445`)
   mas não o `sp`.
3. **`use_vad`**: o default do código é `False` (`:2004`) e contradiz o `config.json` (true) e
   a documentação; e `create_streaming_processor()` é chamado antes de `set_option`, portanto
   `use_vad:false` não impede a construção do processador com o VAD declarado no
   `genai_config.json` (F14).
4. **Duas cópias dos pesos em residente** (S2-4 do lane do worker): três `InferenceSession`
   (encoder/decoder/joint) **e** um `og.Model(model_dir)` para o processador de streaming —
   ~2,1 GB medidos numa corrida real (`rss_mb: 2089.4`) contra 1192 MB de uma sessão
   (`docs/model-specs/README.md:142-143`).

### 4.2 Silero VAD

- **Frames:** o wrapper oficial exige **512 amostras a 16 kHz (32 ms)** e prepende 64 de
  contexto → o tensor que entra no ONNX tem **576**; qualquer coisa abaixo de 32 ms levanta
  `ValueError` ("Input audio chunk is too short"). O estado é `[2,1,128]` (v5) — o par `h`/`c`
  é o v1/v4, não o ficheiro atual.
- **Defaults oficiais:** `threshold 0.5`, `min_silence_duration_ms 100`, `speech_pad_ms 30`,
  `min_speech_duration_ms 250`, histerese `neg_threshold = max(threshold-0.15, 0.01)`.
  O que o Sotto usa (0.3/3360/560) **não é recomendação da NVIDIA nem da Silero**: são os
  valores gravados no `genai_config.json` do export `DimQ1` — o mesmo ficheiro de onde o
  `worker/config.json` os copiou. É defensável, mas não é "a doc".
- **Reset entre streams:** o wrapper reseta silenciosamente quando o `sr` ou o batch mudam —
  o que, nesta pipeline, quer dizer que a mudança de dispositivo (que muda a taxa nativa antes
  do resample) deve ser acompanhada de reset explícito + log. Hoje não é (§4.1.2).
- **Quem chama:** o worker **não** chama `silero_vad.onnx` diretamente (grep: nenhuma
  referência em `worker/*.py` além do `genai_config.json`); quem o usa é o processador do
  ORT-GenAI via `set_option("use_vad", …)`. Logo os avisos de 512/576 amostras não são um bug
  do Sotto — mas o `config.json` publica `use_vad` como se fosse uma decisão do worker.

### 4.3 Parakeet Redux (o motor batch que o HISTORY espera)

- **O que é:** "1.58-bit version of parakeet-tdt-0.6b-v3 … every encoder weight is −1, 0 or +1",
  178 MB, 113× tempo real em 8 cores. **Formato safetensors** (`ternary.json` + `U8` empacotado
  em base-3), **não GGUF**. **Runtime documentado: Photon** (`pip install moondream`,
  `md.photon("moondream/parakeet-redux")`).
- **Línguas:** 25 (o Nemotron cobre 35) — o `README.md` do repo diz "25 languages incl. pt",
  correto.
- **VAD:** "the weights carry a small voice-activity head on the encoder's subsampler … **No
  external VAD model is needed**". Quem ligar o Silero à frente do Redux está a duplicar a
  segmentação.
- **Onde degrada (importa para áudio de desktop):** ruído. MUSAN 9 condições: **9,04 vs 6,72**
  do original; FLEURS alemão a 0 dB: 19,18 vs 14,45. O áudio deste produto é o *mix* do PC:
  música, jogo, compressão — precisamente o regime onde o ternary perde.
- **`transcribe.cpp`**: o repo verdadeiro é **`handy-computer/transcribe.cpp`** (MIT);
  `mudler/transcribe.cpp` **não existe** (HTTP 404). O catálogo Parakeet dele tem 13 variantes e
  **o Redux não é uma delas**; onde menciona a Moondream aponta para o irmão
  `parakeet-ultra`. O único GGUF do Redux é de terceiros e o seu README explica que é uma
  **des-quantização** para F16/Q8_0/Q4_K ("the GGUF therefore holds ordinary F16/Q8_0/Q4_K
  weights") — ou seja, o "ternário" desaparece no caminho.
  **Conclusão para a frase do `README.md:22`:** "transcribe.cpp não abre o GGUF ternário do
  Redux" está certo por acidente; o que está errado é a alternativa implícita ("precisa do fork
  não lançado"). O caminho honesto é Photon (runtime do dono do modelo) ou um export ONNX num
  runtime que já exista — ambos exigem alguém a escrever o loop de descodificação e a carimbar
  `producer:'redux'`.
  **CORRECÇÃO 2026-10-07 (a lane dos docs apanhou, e ela tinha razão):** a minha frase "o ternário
  desaparece no caminho" está ERRADA no que sugere sobre precisão. O cartão do
  `cstr/parakeet-redux-GGUF` diz que o payload é desempacotado **exactamente**
  (`w = scale · (code − 1)`) e que os transcrições de **F16, Q8_0 e Q4_K são idênticas ao Photon**
  nos dois clipes de teste — logo a F16 é sem perdas e a objecção válida é o *fork/packaging* (e o
  facto de nenhum projecto upstream listar o Redux como variante), não a precisão do formato.
  **E um risco de procurement que a lane encontrou e nem eu nem a pesquisa tínhamos posto em
  primeiro plano: o export que este repo CORRE está etiquetado `cc-by-nc-4.0`** (não-comercial),
  enquanto o modelo base é OpenMDW-1.1 (uso comercial). Duas leituras independentes concordam na
  etiqueta; a etiqueta pode estar errada (o repo que ela diz herdar dá 404), mas enquanto não
  estiver esclarecida, **o artefacto que se distribui é o export, não o cartão do modelo base**.
- **Estado do repo:** `_main/research-parakeet-redux.md` já conclui isto (opção C = ONNX em
  `onnxruntime` 1.30 já instalado) e o próprio ficheiro admite "HISTORY is currently
  fail-closed and empty by design". Nada disso está implementado.

### 4.4 Decodificação gulosa (RNNT) — o que a referência faz e o Sotto não

Três implementações concordam em seis regras (NeMo `GreedyRNNTInfer`, ORT-GenAI
`TransducerState`/`ParakeetTdt`, sherpa-onnx):

1. o frame do encoder é buscado **uma vez por `t`** e reutilizado para todos os símbolos desse `t`;
2. o `blank_id` vem da metadata do modelo (aqui 13087) — não se inventa;
3. o estado do preditor avança **só quando sai um não-branco**;
4. o tempo avança só no branco (ou ao bater o teto);
5. **é obrigatório um teto por frame** — no TDT da ORT-GenAI o comentário é literal: um
   `(blank, duration=0)` "emits nothing AND doesn't advance current_t_ … The loop would hang on
   the same frame forever";
6. o preditor é **semeado com o branco/SOS** e o prime não se emite.

O Sotto cumpre 1, 2, 3, 4 e 6 — mas o teto (5) é implementado como orçamento do chunk
(F11), e a semente é `[blank|last_symbol]` em vez do prefixo corrente (desvio **declarado** no
`docs/model-specs/README.md:83-85` e justificado por uma medição de WER em
`worker/README.md:66-90`). Nota: o sherpa-onnx **não** é referência copiável para este modelo —
tem o branco *hardcoded* a 0 e trata `unk` como branco.

---

## 5. O que está bem (não "arrumar")

- **Geometria:** `dock_right` (`sotto_webview.py:457-497`) contém-se no work area, encolhe a
  largura a 34% e a altura a `h-2m`, e volta a fazer clamp das coordenadas. Testável e correto.
- **Rato/click-through: funciona.** Tinha a hipótese de que `WS_EX_TRANSPARENT` matava o
  `mouseenter` e tornava botões inalcançáveis. **Refutada por medição:**
  `_main/webview-run.log` tem **50** linhas `POINTER_INTERACTIVE active=true click_through=false`
  (e 50 a `false`), ou seja o par entra/sai está a funcionar nas corridas reais.
- **Discurso de falha do worker:** vocabulário próprio (`silent-device`, `device-exhausted`,
  `captions-emitted`), exit 3 para "abriu e ouviu silêncio", e um painel que segura a morte até
  uma legenda a levantar — isto é mais do que a maioria dos apps faz.
- **Disciplina de stdout** do worker: `emit()` é o único escritor de stdout e faz flush;
  todos os `print` vão para stderr. O contrato JSONL não se corrompe.
- **Arquitectura de linha + segundo passe:** é exatamente a forma que a Azure documenta
  ("Post-stream refinement … runs a second recognition pass … Only the final result is replaced
  with a more accurate version that uses broader audio context") e que a AWS justifica
  ("recognition may revise words as it gains more context"). O desenho está certo; falta-lhe o
  reset de estado (§4.1.2).
- **Linha provisória** com estilo distinto (tracejado + itálico) e LocalAgreement-2: é a
  recomendação literal da AWS ("display non-stable words in a different format, such as
  italics").
- **Higiene de janela:** `_gate_form_show`, `_reassert_hidden`, `--no-hotkey` nos probes,
  `CREATE_NO_WINDOW` em tudo o que spawna — o repo tem regras e cumpre-as.

---

## 6. Plano de correcção sugerido (por ordem de valor)

1. **Ligar o worker por omissão** (F1) — 3 linhas. Sem isto, nada do resto é visível ao dono.
2. **Fechar o gate que mente** (F2, parte 1): um braço no oráculo que pergunte "algum produtor
   carimba `producer`?" → vermelho hoje; e **corrigir `AGENTS.md`** para dizer que o HISTORY
   está vazio por desenho e que o oráculo injeta o carimbo.
3. **`captions-emitted` exige `captions > 0`** (F3) — 1 linha + nome novo para o caso.
4. **`close_tap` de verdade** (F4) — `close()` primeiro, `stop()` a sério, e o ledger a marcar
   o `gen` de cada bloco.
5. **Hot reload sem query-string** (F5) — `core.Reload()`; hoje a feature parte o painel.
6. **`panel.js:104`** (F6) e **`onStatus(text, kind)`** (F8) — duas linhas e uma fonte de
   verdade de severidade.
7. **Painel honesto e utilizável:** estado inicial "sem worker" (D3), History recolhido
   enquanto não há produtor (D1), 2 linhas no rodapé (D2), `user-select: text` (D8), botão de
   saída (F7), e decidir sobre o campo de busca (F9 + F2: hoje não tem backend nem teclado).
8. **Reset de stream** no segundo passe e na rotação (F12), `max_symbols_per_step` por frame
   (F11), `lang_id` sem fallback para `os` (F13), `use_vad` default coerente (F14).
9. **RTF** (F10): decidir conscientemente entre GPU, export de chunk menor e dizer no painel
   que está a correr atrás.
10. **Documentação que mente** (§7) — `AGENTS.md:102` primeiro, `README.md` da raiz depois.

---

## 7. Documentação que mente (e que já custou trabalho)

| onde | afirma | verdade |
|---|---|---|
| `AGENTS.md:102` (contexto auto-carregado por TODOS os agentes) | "`grep -n 'def rerun\|reset_stream_state\|_last_symbol'` devolve ZERO matches… o segundo passe está AUSENTE hoje" | **Falso nesta revisão**: `def rerun` = `worker/sotto_worker.py:2325`, `reset_stream_state` = `:567`, `_last_symbol` = `:511/:587/:727/:778/:2361/:2378`. O passe M1-M3 **está** ligado ao caminho vivo (`drain`→`finalise`→`rerun`, `:2406-2412`). Um lane que acredite no `AGENTS.md` vai "re-landar" uma feature que já existe |
| `caption-formulation.js:296-299` | "The live worker is the pre-cure snapshot (`worker/sotto_worker.py`, 128569 B) whose `_event` never stamps `final`" | o ficheiro tem 150592 B e `_event` carimba `final` (`:1621-1641`) |
| `panel.js:308-324` | "9 of the 13 lines written after the cure are `provisional-draft`" (justifica o fallback) | os números vieram do histórico de 06/10; hoje o caminho `final` existe e o que falta é o `producer` |
| `README.md` (raiz):48-64 | "**Shell** — Tauri 2, Rust, Svelte 5 … No Electron", "Planning. See `docs/roadmap.md`" | a app é `app/webview/run.cmd` (WebView2 + pywebview 6.2.1) e existe há dois dias; o painel é HTML/CSS/JS. O `README.md` da raiz descreve **outro produto** |
| `worker/README.md:20-22` | 9 estados | o código emite também `gate`, `device-rotated`, `device-exhausted`, `silent-device`, `music-only-capture`, `no-speech-in-capture` |
| `worker/README.md:178-183` | o candidato é abandonado pelo `--tap-peak-floor`; "every candidate flat → `device-exhausted`" | desde 06/10 uma **legenda** assenta a escada (`:2653-2655`) e o floor só classifica; a escada re-entra no candidato com sinal (`:2737-2746`) |
| `wasapi_loopback.py:865-878` | o período do pump "derived from the RING, not from our own block size" | o código calcula-o de `block_ms` (`:878`) |
| `README.md:41-44` | Nemotron é `license:other` e "must be read before this ships" | é **OpenMDW-1.1**, uso comercial explícito; distribuir exige reter a licença + avisos. O gate pode ser fechado |

---

## 8. Método e artefactos

**Oráculos que corri (sem janela, sem áudio):**

- `node _main/live-vs-history-source-oracle.js` → `RESULT: GREEN — 13/13` (e o §2.2 explica o
  que ele **não** pergunta).
- `node _main/historico-vs-redux-probe.js` → `GREEN` (o transcript leva só `route=final`).
- `node app/electron/transcript-append-oracle.js` → `RESULT: GREEN — every worker line is
  appended once, in order, word for word` (receipt `_main/_audit-probe/transcript-append.log`).
- `node _main/_audit-history-dead.js` (**novo**) → prova que a meta real não tem `producer`,
  que o predicado real recusa e que o store real grava 0 linhas.
- execução do motor real em Node para ler `Object.keys(engine.state())`.

**Ficheiros que criei (nenhum ficheiro existente foi alterado):**

| caminho | para que serve |
|---|---|
| `_main/_audit-history-dead.js` + `_main/_audit-probe/history-dead.log` | a receita de F2 |
| `_main/_audit-probe-20261007.py` + `_main/_audit-probe/plain.log(.stdout/.stderr)` | a sonda de arranque/pixels que o sandbox bloqueou; guarda o erro do `pythonnet` como recibo |
| `_main/_audit-fake-worker.py` | worker falso (só os dois formatos de linha reais) para a sonda acima |
| `_main/_audit-render/{panel-harness.html,stub.js,drive.js,make-harness.py}` | harness de render do painel com os ficheiros REAIS + uma ponte stub; pronto, NÃO executado (o Edge headless não arranca neste sandbox) |

**Contagens no log real** (`_main/webview-run.log`, 2,3 MB): 32 arranques de shell ·
10 com worker (todos `reason=with-worker`) · 1932 `CAPTION_APPLIED` · 1933 `HISTORY_APPEND`
(histórico — antes do carimbo passar a ser exigido) · 9744 `BRIDGE_CAPTION_SENT` ·
15 `BRIDGE_STATUS_ERROR` · 61 `PANEL_SHOWN` · 50 `POINTER_INTERACTIVE` · **0 `CAPTIONS_CLEARED`** ·
**0 `REVEAL_IN_FOLDER`** · 6 `HOT_RELOAD_PANEL_DONE`.

**O que este relatório NÃO prova:** que o painel pinta mal *naquele* monitor (não houve ecrã);
que o clique no Clear não funciona (nunca foi clicado — o *hover* funciona, medido); e nenhuma
das consequências do tap abandonado na *saída* do ASR (o próprio lane declara que só mediu o
ledger).

---

## 9. Adenda 2026-10-07 — o round de correcções, e um erro MEU que o controlo apanhou

Depois desta auditoria as correcções foram despachadas em lanes paralelas (dono de ficheiro
exclusivo, interfaces congeladas): F1/F5/F9 no shell, o painel inteiro com autoridade de design,
F3/F11/F12/F13/F14/F17 no worker, F4/F16 na captura, os docs que mentem, e três gates novos.
Os recibos vivem neste mesmo ficheiro à medida que aterram.

**Duas coisas que este round acrescentou ao método, e que valem mais do que os números:**

1. **UM LIMITE NOVO DO SANDBOX: `run.cmd` não é executável nesta sessão, e não é culpa dele.**
   O lookup de Python do wrapper usa `for /f ('py -3 -c …')`, e `for /f` captura stdout por um
   *pipe*; o sandbox desta sessão nega pipes, logo o cmd reporta o comando substituído inteiro
   como não reconhecido e o wrapper sai 3 com `run.cmd: no python found on this machine`.
   Confirmado **direto e aninhado, antes e depois da conversão CRLF**. Consequência para quem
   vier depois: os braços `--help` (rc 0) e `--bogus-flag` (rc 2) do `run-cmd-exit-oracle.py`
   **não podem ser corridos aqui** — têm de ser corridos numa sessão com pipes, e não se pode
   ler um vermelho deles como regressão.
2. **UMA AFIRMAÇÃO MINHA, REFUTADA POR CONTROL O DENTRO DA MESMA HORA.** Ao criar o
   `Sotto.cmd` (o atalho da raiz) vi o batch imprimir fragmentos do seu próprio header como
   comandos (`'tto' não é reconhecido…`, rc 255) e concluí que a causa era o `run.cmd` estar
   gravado com line endings LF, que o `cmd.exe` desincronizaria num batch aninhado. **É FALSO.**
   O controlo (o mesmo corpo, com o `for /f` com pipe dentro de bloco e um header REM, escrito
   em LF-only e em CRLF e chamado de um batch pai) dá **exactamente o mesmo resultado nas duas
   versões**, e um batch LF-only mínimo aninhado corre limpo. O que eu estava a ver era quase de
   certeza a leitura rasgada de um ficheiro que OUTRA lane estava a reescrever nesse instante
   (`run.cmd`, mtime 03:17:00, contra a minha chamada às 03:16:59-03:17:00). A conversão para
   CRLF ficou (é a convenção, e é comportamentalmente idêntica), mas a razão escrita no código
   teve de ser corrigida — uma causa inventada num comentário é exactamente a classe de defeito
   que a §7 deste relatório acusa. Lição registada: um sintoma observado enquanto outra lane
   escreve no ficheiro não é um atributo do ficheiro.

---

## 10. Estado das correcções (snapshot 2026-10-07, meio do round)

Bateria: `_main\_audit-verify-all.cmd` → recibos em `_main\_audit-verify\*.log`.
Este snapshot foi tirado **com lanes ainda a escrever**, por isso uma linha `rc` de um passo
pode descrever uma corrida que apanhou um ficheiro a meio (foi o caso de `lane4-tap-stop`, cujo
log próprio do lane diz `VERDICT PASS 71/71`). O snapshot final é refeito com as lanes paradas.

| passo | resultado no snapshot | o que prova |
|---|---|---|
| `py_compile` shell / helpers / worker / captura | **rc=0 nos 4** | nenhuma lane deixou sintaxe partida |
| `transcript-append-oracle.js` | **rc=0 GREEN** | a classe de duplicação do transcript continua curada |
| `live-vs-history-source-oracle.js` | **rc=0 GREEN 13/13** | o predicado de fonte continua fail-closed |
| `historico-vs-redux-probe.js` | **rc=0 GREEN** | o store continua a recusar `provisional-draft` |
| `history-producer-gate.js` (novo) | **GREEN + `PRODUCER-VERDICT: no-producer-in-tree`** | o gate que faltava: diz que **nada** no repo carimba `producer`, que o motor real não o traz, e que o disco fica a 0 — e detecta que o oráculo antigo se auto-injecta (`copies-commits-and-stamps=true`). Não finge que o transcript funciona |
| `panel-state-guard-gate.js` (novo) | **GREEN 3/3** | `panel.js:132` lê `state().provisional`, que existe; o conjunto de chaves do motor bate com o literal da fonte; o gate não é vácuo (exige ≥1 leitura) |
| `verdict-gate.py` (novo) | **GREEN 11/11** | `decide_verdict` existe, `main()` chama-o (`:3205`, `:3209`), e — o achado F3 — `captions==0` **já não** produz `captions-emitted`; as palavras de no-audio pré-existentes mantêm-se |
| `_lane3-verdict-probe.py` | rc=0 | a mesma tabela, pela mão da lane 3 |
| `_lane4-tap-stop-probe.py` | log do lane: **`VERDICT PASS 71/71`** | `stop()` existe, é idempotente, e **nenhum `on_block` depois de `stop()`** |
| `_lane2-reset-probe.js` | **MISSING no snapshot** | a lane 2 ainda não o escreveu (o `reset()` do motor é o que ele verifica) |
| `_audit-history-dead.js` | rc=0 | a receita do F2 continua a recusar a meta real |

**Já aterrado e legível no disco (verificado por grep meu, não pelo recibo da lane):**
`worker/sotto_worker.py` tem `decide_verdict` (`:2000`), `fresh_processor` (`:592`),
`reset_frontend` (`:653`), `labels_pruned` (`:551`), `captions-zero` (`:2111`),
`done_text_max_chars` (`:2223`) e `use_vad` default `True` (`:2333`);
`app/electron/panel.js` tem `canonicalProducer` (`:277`), `history--collapsed` (`:364`),
`bridge.quit()` (`:961`), `payload.kind` (`:864`) e `state().provisional` (`:132`);
o shell decidiu o arranque por ordem declarada (o `AGENTS.md` da lane 5 cita
`sotto_webview.py:1845-1866`).

**Pendente para o fecho:** recibos das lanes 4 (captura) e 5 (docs) — as lanes 1, 2, 3 e 6 já
entregaram e os seus trabalhos foram verificados por mim (§11); depois a bateria limpa, a revisão
adversarial do diff e a tabela final substituindo esta.

---

## 11. Verificação independente do coordenador (2026-10-07, depois das lanes)

Não aceitei nenhum recibo de lane como prova. O que eu mesmo corri e vi:

| verificação | como | resultado |
|---|---|---|
| **F12 — o pressuposto que a lane 3 declarou NÃO medido** | `python _main\_audit-fresh-processor-probe.py` (carrega o int8, sem dispositivo, sem janela) | **GREEN**: dois `create_streaming_processor()` do mesmo `og.Model` existem, são objectos distintos, e cada um tem buffer próprio — um processador FRESCO com meio chunk não devolve features, o mesmo processador devolve-as quando o SEU buffer chega a um chunk, e o primeiro continua a funcionar depois disso. Logo `fresh_processor()`/`reset_frontend()` entregam mesmo um front-end VAZIO. Receipt: `_main/_audit-probe/fresh-processor.log` |
| **o meu próprio instrumento estava errado (e soube-o antes de acusar o código)** | primeira corrida do probe acima | **RED no meu arm5** — eu exigia features de MEIO chunk depois de um chunk consumido, o que o contrato "uma chamada por chunk" proíbe. O arm3 vê exactamente isso num processador fresco. Corrigi o INSTRUMENTO (arm5 passou a dar a A um chunk inteiro) e a segunda corrida deu GREEN. Um RED meu teria incriminado o código por obedecer à sua doc |
| **os dois arms que o reordenamento do painel partiu** | editei `app/webview/sotto_webview.py` (a lane do shell já tinha parado): `historyAboveLive` → `liveAboveHistory` (`:1085`, conjunção `:2957`) e o meio-transcript do probe passou a ser CONDICIONAL em `canonicalProducer`, com o ramo `no-producer-in-tree` a exigir o estado honesto (feed vazio, disco vazio, busca desligada) e a reportar qual ramo correu | probe deixou de ser um gate que não podia dizer sim; `PANEL_V2_PROBE` agora diz em que ramo está |
| **que o meu próprio edit não parte a JS embutida** (o `py_compile` não a vê) | `python _main\_audit-embedded-js-check.py` (novo: extrai cada blob e chama `node --check`) | **GREEN — 7 blobs**, e imprime os campos de cada um: `liveAboveHistory` no INJECT, `searchInputDisabled` no READ_LIVE. Receipt: `_main/_audit-verify/jscheck.log` |
| **F1 no shell** | greps meus + o arm oracle da lane | `--no-worker` (`:3950`), regra factorada `_worker_autostart_reason` (`:2654-2670`), chamada em `:1869`; `_main/_lane1-worker-default-arms.py` → **GREEN 15/15** (default/`--show` arrancam; `--no-worker`/env/5 flags de medição recusam; `--with-worker` força mesmo com `--dump-dom`; D3 nomeia a flag) |
| **F5 no shell** | leitura da região + grep | `reload_panel_assets` faz o bounce por `stage.html` (`:2763`, `:2766`); o único `?sotto_hr=` que resta é a docstring que cita o código morto (`:2733`) |
| **F3/F6/F7/F8/D1/D2/D8 no painel** | greps meus no `panel.js`/`panel.css`/`panel.html` | `statusPayload`/`statusKind` (`:811/:860/:876`), `state().provisional.length` (`:132`), `engine.reset()` no Clear (`:972`, engine `:595`), `bridge.quit` + `#quit-button` (`:961`, html `:99`), `history--collapsed` (css `:229`), `line-clamp: 2` (`:837`), `user-select: text` (`:697`), **`dom.searchInput.disabled = !searchable` (`:380`)** — o campo que o meu arm do probe lê — e as duas strings que não podiam quebrar intactas (`:494`, `:508`) |
| **F2 — o gate novo** | `node _main\history-producer-gate.js` | `PRODUCER-VERDICT: no-producer-in-tree`, com o meta real impresso (sem `producer`), 58 ficheiros varridos sem carimbo, 0 linhas no disco, e a nota de que o oráculo antigo se auto-injecta |
| **os gates novos e os antigos** | `_main\_audit-verify-all.cmd` | `py_compile` 4/4 rc=0; `transcript-append`/`live-vs-history` 13/13/`historico-vs-redux` verdes; `verdict-gate.py` 11/11; `panel-state-guard` 3/3 |

**Duas descobertas de método que valem mais do que os números acima:**
1. **Este sandbox nega QUALQUER `CreatePipe`** — não só o `for /f` do cmd. O meu próprio
   verificador de JS morreu com `PermissionError: [WinError 5]` em
   `subprocess.run(capture_output=True)` e teve de escrever para ficheiro. Isso explica, de uma
   vez, o `run.cmd` inexecutável aqui e o `python.exe` filho com stdio piped
   (`0xC0000142`) que a lane 3 mediu.
2. **Um instrumento meu esteve errado e foi corrigido antes de acusar o código** (§11, segunda
   linha). É a terceira vez neste dia que um "vermelho" era do instrumento ou de uma leitura
   rasgada, não do artefacto — e é a razão pela qual este relatório insiste em nomear o
   instrumento, a cadência e o número em cada afirmação.

---

## 12. Fecho do round (2026-10-07) — revisões, o que eu mesmo quebrei, e o que fica

### 12.1 Revisões (nomeadas, como o próprio `AGENTS.md` agora exige)

| ficheiro | bytes | sha256 (16) | quem |
|---|---|---|---|
| `app/webview/sotto_webview.py` | 206048 | `6A9C0E8EFD321FF0` | lane 1 + 2 edições minhas (F5/wiring/probe) |
| `app/electron/panel.js` | 40529 | `9EECA16E393F664C` | lane 2 |
| `app/electron/panel.html` / `panel.css` | 13131 / 20999 | `ECCFADE60624D93E` / `A4C22636A41F45C0` | lane 2 |
| `app/electron/caption-formulation.js` | 30345 | `BD05361B02AE767C` | lane 2 (`reset()`) |
| `worker/sotto_worker.py` | 175998 | `4E6D6AE30C43FF21` | lane 3 + o meu hardening do veredicto |
| `worker/wasapi_loopback.py` | 50461 | `940F7DD7F22AECE0` | lane 4 + o meu `_stop` re-test |
| `worker/config.json` | 4707 | `D53E6AE0C7A573F0` | lane 3 |
| `AGENTS.md` / `README.md` | 35367 / 13015 | `3F3704E17BCB2211` / `67823366ECE365C4` | lane 5 |
| `Sotto.cmd` (novo) | 2012 | `900B025C79DA6561` | eu |

### 12.2 A bateria final, com verdicto nomeado em cada artefacto

`_main\_audit-verify-all.cmd` → recibos em `_main\_audit-verify\*.log`. **16 de 16 rc=0:**

```
py_compile        shell / helpers / worker / captura     rc=0 (4/4)
oracle            transcript-append      GREEN — every worker line is appended once, in order
oracle            live-vs-history        GREEN — 13/13 arm(s)
oracle            historico-vs-redux     GREEN — the transcript carries only the worker-closed line
gate              history-producer       GREEN — PRODUCER-VERDICT: no-producer-in-tree
gate              panel-state-guard      GREEN — 3/3 arm(s)
gate              verdict                GREEN (11/11)
gate              worker-start-wiring    GREEN — o reason que a regra devolve é o que decide
probe             lane1-worker-default   GREEN — all 15 arm(s)
probe             lane2-reset            GREEN — reset() clears the engine, and the cleared line
                                               cannot come back
probe             lane3-verdict          VERDICT PASS
probe             lane4-tap-stop         VERDICT PASS 71/71 (NO on_block after stop())
probe             review-f1f3            PART A GREEN / PART B GREEN
probe             review-tapstop         UPHELD (guard presente → 0 chamadas) e REFUTED no mutante
check             embedded-js            GREEN — 7 blobs parseiam sob node
probe             fresh-processor        GREEN — dois processadores do mesmo og.Model são
                                               independentemente bufferizados
receita           audit-history-dead     o painel recusa TODAS as linhas que este motor produz
```

### 12.3 O achado mais importante do round: os fixes introduziram um P0, e NENHUM gate o viu

**O `_worker_autostart_reason` era calculado e DESCARTADO.** `start_worker(reason)` não olhava
para o `reason`, e o call site em `_on_loaded` é incondicional — pelo que **todo o arranque
spawnava worker**, incluindo `--dump-dom`/`--selftest`/`--memory`/`--no-hotkey`/`--exit-after`
(ou seja: cada arm de medição pagava ~2 GB de modelo, exactamente o custo que o conjunto de
supressão existe para evitar), e o caminho D3 dizia ao dono *"No transcription worker is
running (started with --dump-dom)"* **enquanto um worker carregava**.

Pior: **os dois instrumentos que passaram testavam a REGRA, não a LIGAÇÃO** — os 15 arms da lane
1 e os 22 arms do revisor chamam a função pura; nenhum deles arranca a shell. Foi encontrado a ler
o call site, não a correr um gate. É literalmente a classe de defeito que este round combate
("um instrumento que testa o modelo e certifica a máquina"), desta vez introduzida pelos próprios
fixes.

Corrigido em `sotto_webview.py`: `START_REASONS = ('default','with-worker','hot-reload')` e um
teste de `reason` **antes** de qualquer trabalho de spawn, com recusa registada no mesmo formato
(`WORKER_AUTOSTART=declined reason=… by=start_worker`). Gate NOVO para a classe, e não para o
caso: `_main\_audit-worker-start-wiring.py` — afirma que a regra existe, que o seu valor vai para
o call site, que o teste precede o spawn e que a recusa fala. **Controlo negativo provado:**
removendo a guarda numa cópia, o gate vai a `WIRING-VERDICT: RED`; no ficheiro vivo, `GREEN`.
(`--shell <path>` existe para que o controlo corra sobre uma cópia e nunca sobre o código que se
distribui.)

### 12.4 A refutação do revisor, e o que ela obrigou a mudar

O revisor **refutou** a afirmação "depois de `stop()` retornar, `on_block` nunca mais é chamado":
o `_pump` testa `_stop` **uma vez** no topo do loop, portanto uma thread já passada do teste mas
entalada **antes** do `_cb_lock` toma o lock depois de `stop()` retornar e entrega mais um bloco
(demo dele: `+0.70 s`; e é esse bloco que o ledger passa a atribuir ao candidato seguinte — um
resíduo limitado do próprio F4). Corrigido com uma linha em `wasapi_loopback.py` (re-testar
`_stop` **dentro** do lock) e o probe dele passou de "REFUTED" a `UPHELD` — mas o probe
**modelava** a ordem antiga por mão, pelo que eu o tornei sensível à fonte (`GUARD_IN_SOURCE`):
sem isso ele diria RED para sempre, contra um ficheiro que já está certo.

**Erros nos instrumentos do revisor (declarados e corrigidos por mim, porque um deles é
exactamente a classe que ele foi contratado para caçar):**
- `_review-f1f3.py` PART B: os filtros de `hits` e `reverse` faziam-no imprimir **RED em qualquer
  revisão** — a lista "captions que NÃO é positivo" continha `captions=1`/`2` (que SÃO positivos e
  DEVEM dar o word saudável) e `reverse` contava os casos de desenho (um `ran_but_silent=True`
  com `captions=3` dá `silent-device` por contrato, não por mentira). Corrigidos os dois filtros,
  acrescentado `raises` ao verdicto, e o probe passou a `PART A GREEN / PART B GREEN`.
- `_review-tapstop.py`: verdicto independente da fonte (acima).

### 12.5 O que EU quebrei no caminho (e como o soube)

Ao endurecer `decide_verdict` contra valores não-numéricos, pus o helper a nível de módulo —
e os gates deste repo **extraem o texto da função e executam-no isolado**, pelo que a revisão
passou a dar `NameError: name '_int_counters' is not defined`. Quem o apanhou foi o probe do
revisor (que corre a função extraída), não o gate da lane 6 (que importa o módulo). Corrigido
pondo a coerção **dentro** da função, e a razão ficou escrita no código. Passo a incluir, como
critério de aceitação de qualquer função que os gates executem: **tem de ser auto-contida**.

### 12.6 F2 — a honestidade do HISTORY, agora com três gates e um UI

O transcript continua **fail-closed** (só `producer:'redux'` entra, e nada o carimba), mas deixou
de fingir: `history.root()` publica `canonicalProducer: null`, o painel **recolhe** a gaveta do
transcript a ~48 px, desliga a busca com a razão no `title`, e o probe de aceitação da shell
passou a ser **condicional** — o meio-transcript exige o estado honesto quando não há produtor e
reporta `transcriptBranch`. Três instrumentos vigiam a classe: `history-producer-gate.js`
(nada carimba), `_audit-history-dead.js` (a meta real é recusada), e o gate antigo continua verde.
`_main/panel-live-vs-history-probe.js:190` ainda afirma que o produtor live vem do
`_event` do worker — um **terceiro** ficheiro a descrever um produtor que ninguém escreve: fica
nomeado aqui e é uma linha a corrigir quando alguém tocar aquele probe.

### 12.7 Decisões de design que tomei (e o que decidi NÃO fazer)

1. **A legenda viva é o produto e leva o espaço**; o transcript é secundário e colapsa. A ordem
   do DOM é a ordem visual (a lane 2 recusou um truque de CSS que mantivesse o arm antigo verde
   com o layout mudado — um gate mantido verde por uma mentira).
2. **A UI fica em inglês** (as frases de estado são compostas em código, em inglês; meia tradução
   seria pior).
3. **O transcript continua fechado ao motor live** — foi ordem do dono, e o gate mantém-se.
4. **`Sotto.cmd` na raiz** como o que se clica, a delegar em `app/webview/run.cmd` (que guarda o
   contrato: pré-flight de argumentos, arranque escondido, handshake de prontidão).
5. **Não fiz**: o motor batch (Redux) — é um projecto, não um fix; settings na UI (sem evidência
   de necessidade); abrir o transcript ao live (proibido pelo dono); mexer no `F10`/RTF (medido e
   registado, mas a decisão — GPU, export com chunk menor, ou dizer que está atrasado — é dele).

### 12.8 O que NÃO está verificado, dito com todas as letras

- **Nada foi verificado a CORRER a app.** Este sandbox bloqueia o `pythonnet` e o Chromium, logo
  o F5 (o bounce de hot reload), o F9 (foco/teclado), o D9/D1 (o desenho pintado), e o arranque
  real do worker **não foram exercidos** — só lidos e, onde possível, exercidos por gates de
  ficheiro. O primeiro `run.cmd` numa máquina que possa correr é a verificação que falta.
- **O tap real numa rotação** não foi testado (sem dispositivo). Falsificador nomeado: depois de
  um `device-rotated`, o `blocks=` por candidato para o candidato ABANDONADO tem de parar de
  crescer (hoje lê ~2×).
- **O texto do segundo passe** com o front-end fresco (F12): a independência dos processadores
  está medida (§11), o **texto** não — falsificador: re-decodificar um segmento duas vezes, uma
  por front-end, e comparar.
- **O `F11`** (teto por frame) foi verificado por caminho de código, não por corrida do modelo:
  falsificador = mesmo clipe em file mode, contagem de tokens antes/depois (uma **queda** é
  truncagem).
- **`captions-zero`** (F3) é um word novo: a shell pinta-o como erro (positive test em
  `HEALTHY_DONE_VERDICTS`) e nenhuma corrida real o produziu ainda.

**Veredicto do round:** os 20 achados da auditoria estão corrigidos ou explicitamente
transferidos para o dono com o custo medido; os fixes trouxeram **um P0 próprio** (a regra do
worker descartada), que este fecho apanha, corrige e gateia; e o registo do repo — incluindo o
`AGENTS.md` que todos os agentes carregam — passou a dizer a verdade em vez de repetir medições
de revisões mortas.

---

## 13. Alt+C: o único controlo, medido (2026-10-07, pedido do dono "faz o alt c funcionar")

### 13.1 O que eu medi primeiro, e o que isso eliminou

`_main\_audit-hotkey-probe.py` regista cada candidato exatamente como a shell o faz
(`hWnd=NULL`, `MOD_NOREPEAT`), lê o `GetLastError` e **desregista logo** (a chave fica presa
microssegundos; sem janela, sem dispositivo):

```
Alt+C (SHIPPED)   YES   ok            Alt+Shift+C  YES   ok
Ctrl+Alt+C        YES   ok            Ctrl+Shift+C YES   ok
Alt+F9            NO    ALREADY REGISTERED by another program (1409)
```

**`Alt+C` está LIVRE nesta caixa.** Logo "Alt+C não faz nada" nunca foi a tecla tomada — e
`Alt+F9` tomado tornou-se o isco honesto do teste de fallback (§13.2). O log real corrobora o
resto do caminho: `HOTKEY_REGISTERED accelerator=Alt+C register=true` **17×** e
`PANEL_SHOWN reason=hotkey visible=true` **30×** — o par entrar/sair sempre existiu.

### 13.2 O que estava mesmo em falta (e agora existe, com prova)

| lacuna | porquê isso importa | correcção + prova |
|---|---|---|
| **Registo de uma tentativa só** | se a tecla estivesse tomada, a shell logava `HOTKEY_REGISTER_FAILED` e seguia com o hotkey morto, invisível, sem mensagem: um app brickado com a aparência de app a funcionar | `HOTKEY_FALLBACKS` + `arm_hotkey()`; se TODAS caírem, um diálogo de erro num thread daemon (o painel não pode ser o mensageiro — nada o consegue abrir). **Prova com isco real**: `Alt+F9` → `1409` → `HOTKEY_TRY_FAILED` → `Alt+Shift+C` registado → `WARN HOTKEY_FALLBACK requested=Alt+F9 using=Alt+Shift+C` |
| **Nenhuma guarda de instância** | um segundo shell não consegue registar Alt+C e continuava a correr invisível → o Alt+C do dono respondia ao PRIMEIRO (possivelmente velho). Com autostart (login + duplo-clique), a colisão deixa de ser hipotética | `take_single_instance_lock()` (mutex `Local\SottoShell`, libertado pelo kernel ao morrer — sem lock velho). **Prova**: primeiro detentor `True`, segundo `False`, nome diferente `True` |
| **Toggle a decidir por cache** | `self.visible` pode ser invalidado por fora (o `form.Show()` do pywebview na navegação, o re-assert de visibilidade) → um `True` velho faz o PRIMEIRO Alt+C ser um HIDE no-op de um painel que o dono não vê: "não acontece nada" até carregar duas vezes | `toggle_panel` pergunta `IsWindowVisible` e loga `PANEL_VISIBILITY_CACHE_STALE` quando o cache mentia |

**Entrega provada sem app nem tecla física** (`_main\_audit-hotkey-delivery.py`,
`VERDICT: GREEN`): registo → um `WM_HOTKEY` REAL postado no queue da própria thread do hotkey →
o handler corre em <2 s → chama `toggle_panel('hotkey')`. É "Alt+C funciona" menos a tecla física
e a janela.

### 13.3 Arranque com o Windows (pedido do dono) — instalado e verificado

`HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Sotto` =
`"C:\Program Files\Python311\pythonw.exe" "H:\sotto\app\webview\sotto_webview.py" --log "H:\sotto\_main\webview-run.log"`,
confirmado por leitura independente (`reg query`) e por `--autostart-status` → `AUTOSTART=on`,
`matches this checkout: True`.

- **Nunca `run.cmd`** como alvo: um `.cmd` é programa de consola, logo o Windows abriria uma
  consola **em cada login** — proibido neste repo, e a census da casa nomeia consolas órfãs.
  `pythonw.exe` é GUI-subsystem: sem consola, sem janela, e a shell faz o que o duplo-clique faz
  (worker incluído, F1).
- `--autostart-status` existe porque o valor embute caminhos absolutos: se a árvore mudar de sítio,
  diz `matches this checkout: False` em vez de falhar em silêncio no login.
- **Nota de sandbox:** a escrita ao registo foi NEGADA na primeira tentativa
  (`AUTOSTART_INSTALL_FAILED PermissionError(13, 'Acesso negado')`) — o código apanhou-a e disse-a,
  em vez de fingir sucesso. Corri o comando idêntico uma vez com acesso alargado (aprovação do
  dono) e a leitura independente confirmou o valor. O `--uninstall-autostart` não precisa disso.

### 13.4 O que continua NÃO verificado (e é o próximo passo do dono)

- **A tecla física e a janela.** O registo, a entrega e o dispatch estão provados; o que falta é
  uma pressão real de Alt+C com o WebView2 a pintar — este sandbox bloqueia o `pythonnet`, logo o
  painel não pode ser mapeado aqui. **Primeiro teste na máquina dele: duplo-clique em `Sotto.cmd`,
  carregar Alt+C, e o painel deve aparecer com legendas.** Se aparecer `VISIBILITY_CACHE_STALE` ou
  `HOTKEY_FALLBACK` no log, os instrumentos desta secção dizem o que aconteceu.
- **O autostart a valer no login** só se prova depois de um logoff/login (o valor está escrito e
  lido; o efeito no próximo login é do Windows).

---

## 14. Com a app A CORRER e um vídeo a tocar: três P0 encontrados ao vivo (2026-10-07)

O dono pediu "inicia pra mim o sotto" e pôs um vídeo a tocar. Correr a app de verdade — a primeira
vez nesta sessão — encontrou três defeitos que nenhum gate de ficheiro podia ver, e **um deles foi
introduzido por mim** na véspera desta secção.

### 14.1 O painel estava MORTO em todas as execuções: `let` na linha errada (TDZ)

**Sintoma no ecrã do dono:** o worker transcrevia (pico **0,44**, `captions (worker) = 119`), a shell
registava milhares de `BRIDGE_CAPTION_SENT delivered=true`, e o painel ficava congelado em
*"Starting the worker"*, com `#caption-list` a medir **`display:none`** e a caixa vazia
(`live.count = 0`).

**Causa, provada pelo próprio DOM real (`--dump-dom --with-worker`):**

```
PAGE_ERROR Uncaught ReferenceError: Cannot access 'selectedEntry' before initialization
  at markRevealState (panel.js:428:23)
  at wireHistory     (panel.js:304:3)
  at                 (panel.js:87:3)
```

`wireHistory()` corre no arranque do módulo (`:87`), chama `markRevealState()` (`:304`) que lê
`selectedEntry` — declarado com `let` em `:263`, **176 linhas depois**. `let`/`const` são içados mas
não inicializados, logo é `ReferenceError` (temporal dead zone): **o bloco `else` rebentava no seu
primeiro comando e `wireCaptions()`, `wireStatus()`, `wireStats()` e `wireControls()` NUNCA corriam**,
em cada arranque, desde a lane 2. O painel não parecia partido, parecia calado.

**Correção:** o estado da secção de histórico (`historyEntries`, `selectedEntry`, `searchQuery`,
`searchHits`, `canonicalProducer`) foi içado para **antes** do bloco de arranque, com a regra escrita
no código ("qualquer estado que um init possa tocar é declarado acima do init"), e as declarações
antigas removidas (um segundo `let` do mesmo nome seria `SyntaxError`). Verificado: `node --check`
limpo, cada `let` declarado **uma** vez, `let selectedEntry` em `:104` antes de `wireHistory()` em
`:129`.

**Verificação no painel real, com o vídeo a tocar (português):**

```
CAPTION_APPLIED text="Que o Lula faltou que o Lula falta debate, que o Lula foge de debates? Não tem ne."
CAPTION_APPLIED text="Determinação."
STATUS_APPLIED  text="Receiving captions"
#caption-list   display=flex   rect=16,82,348,288     ← visível
#placeholder    display=none   rect=0,0,0,0           ← escondido
```

### 14.2 O instrumento que faltava: a shell não via erros da PÁGINA

Nada disto era observável: `evaluate_js` reporta a **chamada** da shell, que teve sucesso, não o
JavaScript da página. Adicionado ao bridge injetado (corre *antes* dos scripts da página, logo apanha
um throw de inicialização): `window.addEventListener('error' | 'unhandledrejection')` →
`post('page-error')` → `_page_error` → `WARN PAGE_ERROR text=… at=ficheiro:linha:coluna stack=…`.
Um evento de **recurso** (favicon/stylesheet 404, sem mensagem, sem posição, sem stack) é filtrado de
propósito: um `PAGE_ERROR` falso em cada arranque ensinaria o próximo leitor a ignorar a palavra.
**Foi este instrumento que nomeou o bug de 14.1** — sem ele, "o painel não mostra nada" continuaria
sem causa.

### 14.3 O worker morria em ciclo: `AUDCLNT_E_DEVICE_IN_USE` (86 mortes)

Medido no log da app real: **86 `BRIDGE_DEATH`**, todas `wasapi_loopback.WasapiError:
Initialize(SHARED|LOOPBACK) failed: 0x8889000A` = `AUDCLNT_E_DEVICE_IN_USE`, `captions=0`,
reinício a cada 2 s, para sempre — com o endpoint `WASAPI loopback: CABLE Input`.

Duas causas, ambas corrigidas em `worker/sotto_worker.py`:

1. **O `try` cobria a construção do tap, não a ABERTURA.** `WasapiLoopbackTap` abre o endpoint dentro
   de `start()` → `_open()` (`wasapi_loopback.py:878-890`), fora de qualquer guarda por candidato: o
   erro subia como traceback e matava o worker sem nomear o dispositivo. Agora há **um só sítio** que
   abre um candidato, com a mesma emissão honesta (`error`, `stage=open-stream`, `device`, `api`,
   `detail`) e rotação.
2. **`DEVICE_IN_USE` é quase sempre o NOSSO predecessor.** A shell respawna 2 s depois de uma saída e
   a libertação do endpoint pode ficar para trás, logo o worker seguinte vê como ocupado o endpoint
   que estava a funcionar — rodar para longe dele é ao contrário. Agora um endpoint ocupado é
   **esperado e repetido duas vezes** (1,5 s) antes de a escada avançar; qualquer outro motivo roda
   imediatamente.

**Prova:** corrida direta do worker durante 30 s no vídeo do dono → candidato **1 de 10**
(`WASAPI loopback: CABLE Input`), `rate=48000`, legendas reais. Na app, depois da correção:
`deaths=0 restarts=0`, `captions (worker)=119`, `worker peak=0,443448`, e o endpoint de volta ao
`CABLE Input`.

### 14.4 A MINHA regressão: a guarda de instância única brickava todos os instrumentos

`take_single_instance_lock()` (secção 13.2, escrita por mim) recusava o segundo shell com
`SINGLE_INSTANCE already_running=true` — incluindo os de MEDIÇÃO. Com a app do dono a correr,
**todo o instrumento do repo deixou de arrancar**: o meu próprio `--dump-dom` foi recusado. A guarda
protege o **hotkey global**, que é o único recurso exclusivo; uma corrida de medição não registra
hotkey nenhum (é para isso que o `AGENTS.md` obriga a `--no-hotkey`). Corrigido: a guarda é saltada
com `SINGLE_INSTANCE_SKIPPED reason=<flag>` para `--no-hotkey`, `--dump-dom`, `--selftest`,
`--memory` e `--probe-v2` (a união é deliberada, para um probe esquecido continuar a correr e o log
dizer qual flag o escusou).

### 14.5 Display: **substituir**, não acrescentar — verificado com o vídeo a tocar

O dono: *"antes ele ficava dando append em linhas novas ou algo assim"*. O motor emite a hipótese
**cumulativa** (`start` fixo no segmento, `end` a crescer, `text` inteiro, `final:false`), e o painel
já estava desenhado para reescrever **uma** linha no lugar (`renderProvisional`, `panel.js:137-175`)
e só fechar quando os words commitam (`dropProvisional`). Isso agora é medido, não afirmado: durante
**40 s** com o vídeo a tocar a caixa passou de **14 → 25 linhas** (≈1 linha por frase FECHADA)
enquanto chegavam centenas de parciais; se fosse append por parcial seriam milhares. A ordem é a
certa (mais antigo em cima) e a rolagem só desce se o leitor estiver perto do fundo
(`panel.js:285-290`, janela de 48 px) — ler para trás nunca é interrompido.

**Aberto, nomeado com o falsificador (NÃO corrigido de propósito):** as palavras partidas que se veem
nos dados reais — `"não comp arecer"`, `"sse desequi líbrio"`. O `▁` (marcador de início de palavra)
é convertido em espaço e depois **descartado** por `.strip()` em `detok` (`sotto_worker.py:587`), e
`push()` volta a juntar com `" ".join(...)` sobre `frag.strip()` (`:1814`/`:1834`). Resultado: **cada
fronteira de chunk passa a ser fronteira de palavra**. A correção é preservar o espaço inicial (ele é
o sinal "este chunk continua a palavra anterior") através de `detok` e da agregação da linha, o que
toca ~6 sítios (`_words` em `:1727`/`:1803`, `line()` em `:1751`, o cap de `max_chars`, `_close()`);
não a fiz no fim de uma sessão de 4 horas porque uma mudança errada aqui garfa **todas** as legendas.
**Falsificador:** correr o worker 20 s no vídeo e procurar um fragmento cuja fronteira de chunk caia
a meio de palavra — hoje aparece em segundos (`"comp arecer"`), depois da correção não pode aparecer.






