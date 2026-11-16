# 13 - CATALOGO DE MODULOS: cada ficheiro de produto, em palavras

Este documento responde a pergunta que os outros treze deixavam em aberto. eles descrevem
JORNADAS (o que acontece quando o dono aperta uma tecla), e uma jornada atravessa dez modulos sem
os nomear. Aqui a populacao e' a outra: **cada ficheiro de produto tem uma seccao**, com o que ele
garante, quem o chama, o que escreve e o que o utilizador ve quando ele falha.

A regra de prova e' a mesma do resto do directorio: uma frase sem etiqueta nao conta. Cada modulo
traz `[CODE] ficheiro:linha` -- resolvida pelo `_main/spec-citations-oracle.py` -- e, quando a
frase descreve um numero medido, `[MEASURED]` com o comando ou a linha de log.

## A populacao, medida

Medido com o proprio portao (`python _main/spec-coverage-oracle.py`) em 2026-11-15: **114 modulos de produto** nas tres raizes (`app/webview`, `worker`, `app/panel`), mais as classes que sao DADOS e nao comportamento, cada uma descrita uma vez: **84 imagens de skin** em `app/panel/skins/` e **32 sondas** em `worker/_probe/`. Fora da populacao, com razao declarada no portao: `worker/_prefix_audioflag.py` e `worker/_sotto_worker_agcinert.py` (copias congeladas usadas como mutantes) e `worker/runs/` (o mesmo).

O portao da cobertura e' `_main/spec-coverage-oracle.py`, ligado a bateria pelos passos
`spec-coverage` e `red-as-expected-spec-coverage`: ele caminha as tres raizes de produto, aplica as
exclusoes declaradas NO CODIGO (com a razao ao lado de cada uma) e exige que cada caminho esteja
escrito aqui. Um ficheiro casado apenas pelo NOME aparece na linha `NOME-APENAS` e conta como prova
FRACA -- e' a classe de erro que o `10-DEFECTS.md` §D-10 pagou caro para aprender.

## Como ler uma seccao

- **O que faz** -- a garantia, nao a organizacao interna.
- **Quem o chama** -- o simbolo real e o ficheiro, porque um modulo sem chamador e' um modulo morto
  e este projecto ja' pagou por varios (a doenca do instrumento sem passo).
- **O que escreve/le** -- ficheiros, variaveis de ambiente, chaves de estado e as TAGS de log, que
  sao o unico canal pelo qual o dono e os instrumentos veem o modulo.
- **Quando falha** -- o ramo de erro REAL: excepcao, silencio, ou uma linha com nome.
- **Evidencia** -- as linhas que sustentam as frases acima.


---

# A SHELL (`app/webview/`)

## `app/webview/audio_playing.py`

- **O que faz** — Responde a uma única pergunta, por leitura: há som a sair pelos altifalantes agora? Percorre os endpoints de renderização ACTIVOS e lê o pico instantâneo de cada um pela interface de medição do Windows (`IAudioMeterInformation` no endpoint); não abre cliente de áudio e não tem uma única chamada que ESCREVA no dispositivo. `playing()` é verdadeiro quando qualquer pico excede `PEAK_FLOOR` (0.002); `loudest()` devolve o par `(nome, pico)` mais alto, só para o registo do vigia. Falha de leitura é `False`, para um medidor avariado nunca trancar o vigia para sempre.
- **Quem o chama** — `WorkerBridge._schedule_restart` importa o módulo e chama `audio_playing.loudest()` para decidir a troca de endpoint (`[CODE] app/webview/sotto_webview.py:24959`); `WorkerBridge._arm_audio_resume._watch` chama `audio_playing.playing()` num ciclo de 3 s (`[CODE] app/webview/sotto_webview.py:25036`); `shell_relaunch.arm` injecta `audio_playing.playing` como `sound_playing` (`[CODE] app/webview/shell_relaunch.py:306`).
- **O que escreve/lê** — Não escreve ficheiros, env vars nem chaves de estado. Lê apenas os medidores COM dos endpoints de renderização; `render_peaks()` importa `comtypes`/`pycaw` localmente. O próprio módulo não emite tags de log: quem loga é o shell (`ENDPOINT_SWITCH_PROBE_FAILED`, `BRIDGE_RESUME_AUDIO`) e o `shell_relaunch` (`SHELL_RELAUNCH_SOUND_PROBE_OFF`).
- **Quando falha** — `render_peaks()` pode levantar (é a leitura COM crua, e está documentado como tal); `playing()` engole qualquer excepção e devolve `False` (`[CODE] app/webview/audio_playing.py:95`), e `loudest()` engole e devolve `('', 0.0)` (`[CODE] app/webview/audio_playing.py:104`). O utilizador não vê nada: o efeito é o vigia deixar de recusar o relançamento, ou seja, o comportamento anterior a este módulo.
- **Evidência** — `[CODE] app/webview/audio_playing.py:31` (`PEAK_FLOOR = 0.002`); `[CODE] app/webview/audio_playing.py:89` (entrada pública `playing`); `[CODE] app/webview/audio_playing.py:99` (`loudest`).

## `app/webview/batch_queue.py` (1 270 linhas — a fila em disco)

- **O que faz** — A **fila em disco** do áudio que ficou sem transcrição, e o executor que a corre. Ordem do dono (2026-11-03): *"os modelos entram e saem conforme a carga do sistema, e o audio nao processado e' processado sozinho quando a carga libera -- SEM NUNCA TRAVAR A MAQUINA DO DONO"* `[CODE] app/webview/batch_queue.py:1`. Duas classes: `BatchQueue` (24 métodos, o estado durável e a adopção de spools órfãos) e `BatchExecutor` (18, o processo filho, com tecto de CPU, prioridade `BELOW_NORMAL` e tecto de fios).
- **Quem o chama** — O shell e o `load_shedding` `[CODE] app/webview/sotto_webview.py:9083`.
- **O que escreve/lê** — `%TMPDIR%/sotto-batch-queue` (ou `SOTTO_BATCH_QUEUE_DIR`), `adopted.json`, os spools `sotto-pending-audio-*`. O env do filho herda o tecto de threads (`THREAD_ENV_KEYS`: `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, …).
- **Quando falha** — Um item que falha tem `MAX_ATTEMPTS` e backoff exponencial, e depois vai para o estado `done` em vez de girar para sempre. Um spool cujo dono morreu é adoptado só acima de `ADOPT_MIN_AGE_S` (nunca se rouba um spool vivo). O pior caso é o áudio ficar na fila; nunca se perde.
- **Evidência** — `[CODE] app/webview/batch_queue.py:213` (`BatchQueue`); `[CODE] app/webview/batch_queue.py:612` (`child_env`); `[CODE] app/webview/batch_queue.py:664` (`BatchExecutor`). Portão: `_main/batch-queue-drain-oracle.py`.

## `app/webview/bridge_census.py`

- **O que faz** — O censo da ponte, activo só com `SOTTO_BRIDGE_CENSUS` ligado: devolve o objecto que o `_main/bridge-census.py` constrói em `attach(log)`, ou `None` quando o interruptor está desligado. Existe para responder ONDE o tempo foi quando um `exec_js` não responde — `sys._current_frames()` em vez de `py-spy`. `task_bits()` traduz o estado .NET da chamada em `{'status', 'continuation'}`, separando "o JS respondeu e o Python nunca foi chamado" de "o renderer nunca devolveu nada". O resultado é memoizado em `_BRIDGE_CENSUS`, e o contrato é NUNCA LANÇAR.
- **Quem o chama** — O shell embrulha-o em `_bridge_census()` (`[CODE] app/webview/sotto_webview.py:751`) e `_task_bits()` (`[CODE] app/webview/sotto_webview.py:755`); o consumidor é o `_run` do caminho `exec_js`, que faz `census = _bridge_census()` e `census.no_answer(token, _task_bits(box, done))` (`[CODE] app/webview/sotto_webview.py:14877`).
- **O que escreve/lê** — Lê a env var `SOTTO_BRIDGE_CENSUS` (aceita `1`/`true`/`yes`/`on`) e carrega `_main/bridge-census.py` por caminho (`spec_from_file_location('bridge_census', path)`). Não escreve ficheiros nem estado persistente; mantém apenas o global `_BRIDGE_CENSUS`. Loga `BRIDGE_CENSUS_ON path=... tick_ms=...` no sucesso e `BRIDGE_CENSUS_FAILED ...` no fracasso.
- **Quando falha** — Qualquer excepção ao carregar/executar o instrumento vira `warn('BRIDGE_CENSUS_FAILED ...')` e `_BRIDGE_CENSUS = None`: a shell arranca sem censo (`[CODE] app/webview/bridge_census.py:59`). Em `task_bits`, um `task` ilegível dá `status='unreadable'` e um evento ilegível dá `continuation='?'` (`[CODE] app/webview/bridge_census.py:86`); não há excepção que escape.
- **Evidência** — `[CODE] app/webview/bridge_census.py:46` (leitura da env var); `[CODE] app/webview/bridge_census.py:56` (tag `BRIDGE_CENSUS_ON`); `[CODE] app/webview/bridge_census.py:68` (`def task_bits`).

## `app/webview/caption_drag.py` (334 linhas — arrastar a legenda com Ctrl)

- **O que faz** — O **decisor** do arrasto da legenda, puro e sem uma única chamada Win32. Ordem do dono: *"segurar control, permite eu arrastar a legenda pra onde eu quero. e o control segurado tambem vai ter um indicativo bem minimo de que da pra arrastar a legenda"* `[CODE] app/webview/caption_drag.py:1`. A emenda de 2026-11-15 é a que dá o nome ao ficheiro: *"as legendas devem se CENTRALIZAR aonde eu deixei meu mouse"* — o destino não é o cursor-pega mas o **centro da janela no cursor**, do primeiro tick em diante; agarrar pela ponta direita é só a maneira de dizer "quero esta legenda", nunca um deslocamento a preservar `[CODE] app/webview/caption_drag.py:8`. Duas funções puras fazem tudo: `drag_plan` (o plano do tick) e `clamp_pos` (nunca sai do ecrã). `pulse_alpha` dá o indicativo mínimo.
- **Quem o chama** — `caption_overlay`, no tick da janela: é o único importador `[CODE] app/webview/caption_overlay.py:201`.
- **O que escreve/lê** — O offset persistido (`caption-drag-offset.json`, `STATE_PATH`), para a legenda voltar onde o dono a deixou. Lê o rect do ecrã e o estado do Ctrl.
- **Quando falha** — Um offset guardado que já não cabe no ecrã é *clampado*, nunca descartado. Sem Ctrl a tecla não faz nada — o arrasto não tem modo implícito.
- **Evidência** — `[CODE] app/webview/caption_drag.py:170` (`clamp_pos`); `[CODE] app/webview/caption_drag.py:214` (`drag_plan`); `[CODE] app/webview/caption_drag.py:301` (`load_offset`). Portão: `_main/caption-drag-oracle.py` (11 arms).

## `app/webview/caption_overlay.py` (2 008 linhas — a janela da legenda)

- **O que faz** — Desenha a legenda na **tela inteira, por cima de tudo**, numa janela Win32 em camadas com transparência por pixel. Existe porque o WebView2 não consegue transparência por pixel dentro do host WinForms do pywebview (o `TransparencyKey` não consegue tratar os pixéis opacos do filho do WebView2, medido e documentado na origem) — sem este ficheiro a legenda é uma placa sólida atrás das palavras `[CODE] app/webview/caption_overlay.py:1`. Cinco classes de responsabilidade: `NativeCaptionOverlay` (40 métodos, a janela e o laço), `_PlayerCue` (a linha do player, com roll-up), `_DragCanvas` (o arrasto com Ctrl), e as estruturas Win32. A taxa de quadros é derivada de um **orçamento declarado** (`CAPTION_FRAME_BUDGET`), nunca do custo bruto: período = custo / orçamento `[CODE] app/webview/caption_overlay.py:81`.
- **Quem o chama** — O shell, em `SottoShell`, e só ele: é o único importador, e constrói a janela preguiçosamente na primeira vez que a legenda é pedida `[CODE] app/webview/sotto_webview.py:13382`. A metade **pura** da pintura (medida, layout, bitmap) está em `overlay_paint.py`; aqui fica a **janela** e o ciclo de mensagens.
- **O que escreve/lê** — Não escreve ficheiros de estado; lê `caption-settings.json` e `caption-theme.json` pelo `caption_settings`, e o offset do arrasto de `caption-drag-offset.json` pelo `caption_drag`. Lê do shell o provedor `z_below` para nunca subir por cima do painel: ele é consultado a cada `show` e devolve o painel só quando ele está visível `[CODE] app/webview/caption_overlay.py:1926`.
- **Quando falha** — A janela em camadas pode existir e **não pintar** (a classe do P0 do dono: `visible=true` e nada no ecrã); por isso `_screen_proof` mede o pixel em vez de confiar no bit `WS_VISIBLE` `[CODE] app/webview/caption_overlay.py:1860`. Um `SetWindowDisplayAffinity` que falha devolve o modo lido de volta e a legenda continua visível ao dono; nunca morre por isso.
- **Evidência** — `[CODE] app/webview/caption_overlay.py:45` (`EX_STYLE`); `[CODE] app/webview/caption_overlay.py:81` (`CAPTION_FRAME_BUDGET`); `[CODE] app/webview/caption_overlay.py:214` (`_clamp_rows`); `[CODE] app/webview/caption_overlay.py:1994` (`probe`). Portão: `_main/caption-overlay-screen-oracle.py` e `_main/caption-plate-oracle.py`.

## `app/webview/caption_settings.py` (151 linhas — a escolha do dono)

- **O que faz** — Persiste o que o dono escolheu para a legenda: `target_lang` (a língua alvo da tradução, default `pt`), e o **aspecto** da legenda nativa (`opacity` 0,30-1,0 e `plate` `tight`). Existe porque o shell nasce antes do painel e uma escolha só em memória seria esquecida no arranque seguinte `[CODE] app/webview/caption_settings.py:1`. O `opacity` escala o alfa da **placa** e nunca a tinta do texto.
- **Quem o chama** — O shell, o `caption_overlay` e o `youtube_captions` `[CODE] app/webview/sotto_webview.py:12598`.
- **O que escreve/lê** — `_main/caption-settings.json` e `_main/caption-theme.json`, com escrita atómica. Lê `SOTTO_CAPTION_SETTINGS` e `SOTTO_CAPTION_THEME`.
- **Quando falha** — Tudo o que não resolve cai no default e o ficheiro é reescrito: um valor fora do intervalo é *clampado* (`MIN_OPACITY`..`MAX_OPACITY`), nunca aceite. Um `plate` desconhecido cai em `tight`.
- **Evidência** — `[CODE] app/webview/caption_settings.py:29` (`path`); `[CODE] app/webview/caption_settings.py:62` (`save`); `[CODE] app/webview/caption_settings.py:86` (`set_visual`). Portão: `_main/caption-plate-oracle.py`.

## `app/webview/caption_wrap.py`

- **O que faz** — Quebra uma legenda em no máximo `MAX_LINES` (2) linhas que caibam em `max_px`, numa costura natural (fim de frase, fim de oração ou antes de conjunção/preposição), e NUNCA parte, inventa, reordena ou perde palavras: o que não cabe volta como `overflow`. `wrap_tail()` devolve as ÚLTIMAS duas linhas e o texto que rolou para fora. `budget_px()` calcula o tecto de uma linha como `min(68 % da área de trabalho, medida de REPRESENTATIVE[:42])`, com piso de 160 px.
- **Quem o chama** — `CaptionOverlay._wrap_fn` importa `caption_wrap as cw` e chama `cw.wrap(text, cur_w, budget, max_lines=cw.UNBOUNDED_LINES)` (`[CODE] app/webview/caption_overlay.py:1511`); `overlay_paint._measure_budget` chama `_cw.budget_px(...)` (`[CODE] app/webview/overlay_paint.py:599`); `overlay_paint._layout` chama `_cw.wrap_tail(...)` e `_cw.wrap(...)` (`[CODE] app/webview/overlay_paint.py:639`).
- **O que escreve/lê** — Nada: puro stdlib (`re`), sem I/O, sem env vars, sem estado de módulo, sem tags de log.
- **Quando falha** — O módulo não tem ramo de erro próprio: não apanha excepções do `measure` do chamador nem de `str(text)`. Entrada vazia devolve `([], '')`; `max_lines <= 0` devolve `([], texto)`. As garantias são aritméticas — `_greedy_end` dá a uma palavra mais larga que o orçamento a sua própria linha em vez de a cortar (`[CODE] app/webview/caption_wrap.py:305`).
- **Evidência** — `[CODE] app/webview/caption_wrap.py:55` (`MAX_LINES = 2`); `[CODE] app/webview/caption_wrap.py:78` (`CHAR_CEILING = 42`); `[CODE] app/webview/caption_wrap.py:403` (`budget_px`).

## `app/webview/capture_exclusion.py`

- **O que faz** — Esconde a janela da legenda de quem captura o ecrã sem a esconder do dono, chamando `SetWindowDisplayAffinity` uma vez por janela. A escada de modos é `WDA_EXCLUDEFROMCAPTURE` (0x11, só a partir da build 19041) → `WDA_MONITOR` (0x01) → nada; o modo devolvido é SEMPRE lido de volta do sistema, porque pedir 0x11 e ficar com 0x00 é uma falha e não um sucesso. `enabled()` é o interruptor, **DESLIGADO por omissão** (ordem do dono, 2026-11-06: *"retira o 'modo stealth' da legenda. deixa desativado por padrao, e ativavel nas configs do sotto"*).
- **Quem o chama** — `CaptionOverlay._create` importa o módulo e chama `capture_exclusion.apply(hwnd, want=capture_exclusion.enabled())`, logando depois `CAPTION_OVERLAY_CAPTURE` ou `CAPTION_OVERLAY_CAPTURE_FAILED` (`[CODE] app/webview/caption_overlay.py:697`); `NativeCaptionOverlay.set_capture_exclude(want=None)` aplica ou remove a afinidade na janela VIVA (`[CODE] app/webview/caption_overlay.py:851`), e o shell chega lá pelo handler `caption-capture-exclude`.
- **O que escreve/lê** — Um único predicado: `SOTTO_CAPTURE_EXCLUDE` (`1`/`0`) manda quando está definido; senão a chave `capture_exclude` de `_main/caption-settings.json` (default `False`, escrita por `caption_settings.set_capture_exclude`); ficheiro ausente ou partido resolve DESLIGADO e nunca levanta (`[CODE] app/webview/capture_exclusion.py:60`, `[CODE] app/webview/caption_settings.py:110`). Lê também a build do Windows via `sys.getwindowsversion().build`. As tags de log vivem no chamador, não aqui.
- **Quando falha** — Sem `hwnd` devolve `{'mode': 0, 'ok': False, 'why': 'sem hwnd'}`. Se ambos os degraus falharem, devolve `ok=False` com `why='SetWindowDisplayAffinity falhou (error=N)'` lido de `get_last_error` (`[CODE] app/webview/capture_exclusion.py:111`); o chamador envolve a chamada em `try` e uma excepção vira `CAPTION_OVERLAY_CAPTURE_FAILED` — a legenda nunca morre por isto.
- **Evidência** — `[CODE] app/webview/capture_exclusion.py:36` (`MIN_BUILD_EXCLUDE = 19041`); `[CODE] app/webview/capture_exclusion.py:74` (leitura de `SOTTO_CAPTURE_EXCLUDE`); `[CODE] app/webview/capture_exclusion.py:84` (`def apply`).

## `app/webview/code_identity.py`

- **O que faz** — Produz a etiqueta do código que ESTE processo carregou: `sha256=<12 hex> files=<n>` mais ` missing=...` quando algum ficheiro não pôde ser lido. `code_files()` é a única definição da lista — ficheiros explícitos (`_CODE_ID_FILES`), todos os `*.py` da pasta, os globs da página (`../panel/*.js`, `*.css`, `*.html`, `themes/*.css`) e `../../worker/*.py` — e é dela que o processo e o oráculo de frescura leem, para não medirem conjuntos diferentes.
- **Quem o chama** — O shell define `code_identity()` que delega no módulo (`[CODE] app/webview/sotto_webview.py:2514`), usa-o no `main()` para logar `SHELL_CODE_ID %s` (`[CODE] app/webview/sotto_webview.py:26500`) e re-exporta `_CODE_ID_FILES`, `_CODE_ID_GLOBS` e `code_files` para o `_main/live-code-freshness-oracle.py` ler daqui (`[CODE] app/webview/sotto_webview.py:2504`).
- **O que escreve/lê** — Só lê: abre cada ficheiro em binário e alimenta o `hashlib.sha256`. Não escreve ficheiros, env vars nem chaves de estado; não emite tags de log (a tag `SHELL_CODE_ID` é do shell).
- **Quando falha** — Um `OSError` num ficheiro não interrompe a etiqueta: o nome entra em `missing` e a string termina com ` missing=<lista>` (`[CODE] app/webview/code_identity.py:127`); a contagem é `len(names) - len(missing)`. Erros de glob também são apanhados e registados na mesma lista. Não há excepção levantada por leitura falhada.
- **Evidência** — `[CODE] app/webview/code_identity.py:37` (globs da página); `[CODE] app/webview/code_identity.py:42` (globs do worker); `[CODE] app/webview/code_identity.py:125` (formato da etiqueta).

## `app/webview/cost_watchdog.py` (153 linhas — o custo sem trabalho)

- **O que faz** — Decide **quando um worker que queima CPU não está a produzir nada** e por isso deve ser reiniciado. Nasceu de uma medição: o watcher leu o worker do dono a **270,6 %c** numa janela e **1,2 %c** noutra — e o produto não tinha série nenhuma para julgar as duas. A correcção importa tanto quanto a regra: o mesmo código, em 12 amostras de 5 s, deu **73 113 87 1 1 0 65 99 209 1 1 0 %c** (mediana 33) — o worker alterna rajadas com ociosidade, e **uma janela única pode cair inteira dentro de uma rajada** e chamar de degradação o que é trabalho `[CODE] app/webview/cost_watchdog.py:1`.
- **Quem o chama** — O shell (`import cost_watchdog`), no vigia de custo `[CODE] app/webview/sotto_webview.py:65`.
- **O que escreve/lê** — Nada; é puro. Lê a série `WORKER_COST` (que a shell journaliza como `BRIDGE_WORKER_COST` uma vez por minuto). O dono único da expiração de janela é `window_expired`.
- **Quando falha** — Um worker abaixo de `BUSY_PCT` nunca é reiniciado, e há piso (`FLOOR_S`) e tecto (`MAX_PER_HOUR`) para o remédio não virar o defeito. Um caso sem série é ausência, não aprovação.
- **Evidência** — `[CODE] app/webview/cost_watchdog.py:68` (`window_expired`); `[CODE] app/webview/cost_watchdog.py:91` (`plan`); `[CODE] app/webview/cost_watchdog.py:142` (`busy_rows`). Portão: `_main/cost-watchdog-oracle.py`.

## `app/webview/exit_killer.py` (185 linhas — matar de fora, porque de dentro não se consegue)

- **O que faz** — Um processo separado, criado **antes** de a saída começar, que mata o Sotto por handle se a saída não completar. Medido em 2026-11-04 no log do dono: às 13:01:36.080 o shell escreveu `UI_WATCHDOG_EXIT code=9`, e **70 minutos depois o mesmo pid (20448) estava vivo** com 36 threads, 8 de 10 janelas sem responder a `WM_NULL`, e o worker filho vivo com 3,9 GB privados `[CODE] app/webview/exit_killer.py:1`. Nenhum primitivo *dentro* do processo garante esse fim: se o processo fica preso num `DllMain` ou no loader lock, a thread que ia matar o processo também está presa.
- **Quem o chama** — Ninguém o importa: é um **subprocesso**, largado por `_spawn_exit_killer` `[CODE] app/webview/sotto_webview.py:1917`.
- **O que escreve/lê** — Lê o pid e um **carimbo de criação** (`identity`, `open_checked`), porque um pid reciclado nunca é morto; mata os filhos primeiro e escreve no log do shell.
- **Quando falha** — Um pid que já morreu é sucesso silencioso; um pid cujo carimbo não bate é recusa. `_sweep_children` roda também no caminho em que `OpenProcess` chegou tarde (`EXIT_KILLER_SKIPPED ... reason=no-handle`), porque o shell arma o matador e sai em milissegundos.
- **Evidência** — `[CODE] app/webview/exit_killer.py:62` (`identity`); `[CODE] app/webview/exit_killer.py:103` (`_sweep_children`); `[CODE] app/webview/exit_killer.py:173` (`main`). Portão: `_main/exit-backstop-oracle.py` (13/13, `--neg-arm` 5/5).

## `app/webview/external_subs.py`

- **O que faz** — Lê as legendas que o próprio player já está a mostrar, pela árvore de acessibilidade (UI Automation), e devolve `[(source, [linha1, linha2])]` para o YouTube e o Stremio. O separador entre legenda e "chrome" do player é TEMPORAL e posicional: uma linha tem de se manter igual (ou crescer como prefixo de si mesma) por `_CONFIRM_POLLS` (2) polls, e uma linha confirmada que fica fora do centro por `_UNSHAPED_DROP_POLLS` (6) é apagada. `player_source()` decide a fonte com cache de 1 s; `find_player_window()` devolve o primeiro player VISÍVEL, testado por `_window_is_player` e não pelo título sozinho; `edit_values()` devolve todos os valores de controlos Edit.
- **Quem o chama** — `ExternalCaptionWatcher.run` chama `external_subs._uia()` (`[CODE] app/webview/sotto_webview.py:4051`); o mesmo watcher chama `external_subs.caption_lines(hwnd, uia, UIA)` em `_read_inner` (`[CODE] app/webview/sotto_webview.py:4603`), `external_subs.player_source` e `find_player_window` em `_target_window` (`[CODE] app/webview/sotto_webview.py:4718`), e `external_subs.edit_values` em `_youtube_video_id` (`[CODE] app/webview/sotto_webview.py:6580`).
- **O que escreve/lê** — Lê a árvore UIA do processo alvo (COM), a barra de endereço do Chromium e o nome do processo por `QueryFullProcessImageNameW`. Mantém dois estados de módulo, ambos só em memória: `_RUNS` (hwnd → linhas com streak/held, limitado a `_RUNS_MAX` = 32 janelas) e `_PLAYER_SOURCE_CACHE` (TTL `_PLAYER_SOURCE_TTL_S` = 1.0 s). Não escreve ficheiros nem env vars. Não emite tags de log: as linhas `EXTERNAL_CAPTIONS_*` são do shell, e o que este módulo imprime é o `--probe` (`POLL ...`, `PROBE ...`, `PROBE_ERROR`).
- **Quando falha** — Quase todos os leitores têm `except Exception` e devolvem o vazio (`_process_name` → `""`, `_window_title` → `""`, `_descendants` → `None`, `edit_values` → `[]`); `caption_lines` devolve `[]` quando não há player reconhecido, quando o rect é degenerado ou quando não há candidatos, e nesses casos chama `_reset(hwnd)` — uma janela que não é player nunca "reclama" as legendas. `_uia()` NÃO apanha: pode levantar do COM, e é o `try` do shell que produz `EXTERNAL_CAPTIONS_UNAVAILABLE` (`[CODE] app/webview/sotto_webview.py:4054`).
- **Evidência** — `[CODE] app/webview/external_subs.py:511` (o separador temporal `_stable`); `[CODE] app/webview/external_subs.py:725` (`player_source` e o TTL); `[CODE] app/webview/external_subs.py:818` (`caption_lines`).

## `app/webview/gaming_mode.py` (620 linhas — detectar jogo, e mais nada)

- **O que faz** — Responde a **uma** pergunta: o dono está num jogo agora? Ordem do dono (2026-11-04): *"em gaming: control espaço nao da display na legenda. nao faz nada. nem on nem off. fora de gaming: control espaço nao ativa o espaço em apps"* `[CODE] app/webview/gaming_mode.py:1`. Este ficheiro é a metade **detectar**: `is_gaming()` e **uma** linha de log por transição. Não suspende nada, não baixa prioridade, não mexe no worker nem no áudio — quem pergunta decide. A tabela é pura (`live_hotkey_plan`) precisamente para poder ser executada por um oráculo sem tocar no sistema.
- **Quem o chama** — O shell, no fio da tecla ao vivo `[CODE] app/webview/sotto_webview.py:8346`.
- **O que escreve/lê** — O censo de processos (`Toolhelp32`) e a janela em primeiro plano. Não escreve ficheiros. Tags de transição com o nome do jogo.
- **Quando falha** — Sem permissão para ler um processo, cai em "não é jogo" (o estado seguro: a tecla volta a funcionar normalmente). Requer `CLIENT_FOREGROUND_STREAK_REQUIRED` tiques de consistência para um *client* (anti-cheat) contar, o que evita um falso positivo de uma janela de launcher.
- **Evidência** — `[CODE] app/webview/gaming_mode.py:174` (`is_game_name`); `[CODE] app/webview/gaming_mode.py:240` (`foreground_owns_space`); `[CODE] app/webview/gaming_mode.py:578` (`live_hotkey_plan`). Portão: `_main/gaming-hotkey-oracle.py`.

## `app/webview/history_context.py` (310 linhas — de onde veio o áudio)

- **O que faz** — Guarda, em cada linha do histórico, o **contexto** de quando foi dito: `sourceApp`, `audioSource`, `viewingApp`, `viewingTitle` e `viewingUrl` — sem screenshots, sem gravação de ecrã, sem etiquetas de voz e sem credenciais `[CODE] app/webview/history_context.py:1`. A captura é ao **tempo da transcrição**, não ao tempo do commit: o que estava na tela quando a frase foi dita, não quando a linha fechou.
- **Quem o chama** — O shell, ao carimbar a linha (`token_in`) e ao escrever o contexto `[CODE] app/webview/sotto_webview.py:16087`.
- **O que escreve/lê** — Codifica o contexto num token compacto (`ctx1=...`) que viaja na própria linha do histórico. Lê o processo em primeiro plano e o título da janela, com TTL de cache.
- **Quando falha** — Um campo que não se consegue ler é **omitido**, não inventado: a linha fica com os campos que existiam. Um URL que não faz parse é descartado em vez de guardado a meio.
- **Evidência** — `[CODE] app/webview/history_context.py:111` (`normalize`); `[CODE] app/webview/history_context.py:128` (`encode`); `[CODE] app/webview/history_context.py:287` (`snapshot`). Portão: `_main/history-context-oracle.py`.

## `app/webview/hot_reload.py` (666 linhas — editar e ver)

- **O que faz** — Vigia os ficheiros-fonte e recarrega a app/shell quando o disco muda. É o **porte** do `app/_legacy-electron/hot-reload.js`, não um rival: um módulo Node/CommonJS não se pode `require` dum processo Python, mas o contrato é reproduzido à letra — **vigiar DIRECTORIOS, nunca ficheiros** (um save de editor é write-temp-then-rename, e um handle no FICHEIRO morre nesse rename: é o clássico "hot reload funciona duas vezes e depois para"), e debounce de rajada (`DEBOUNCE_MS = 250` ms de silêncio, por classe de mudança) `[CODE] app/webview/hot_reload.py:1`.
- **Quem o chama** — O shell (`import hot_reload`), e constrói o objecto em `self.hot_reload` `[CODE] app/webview/sotto_webview.py:58`.
- **O que escreve/lê** — `ReadDirectoryChangesW` com `FILE_NOTIFY_CHANGE_*` numa pasta por vez. A lista `PANEL_ASSETS` e `watched_worker_files` dizem o que conta como "a app mudou" — um ficheiro fora das duas listas não provoca recarga.
- **Quando falha** — Um buffer de notificações transbordado (`ERROR_NOTIFY_ENUM_DIR`) não perde o evento: força uma re-varredura em vez de assumir "não mudou nada".
- **Evidência** — `[CODE] app/webview/hot_reload.py:52` (`DEBOUNCE_MS`); `[CODE] app/webview/hot_reload.py:69` (`watched_worker_files`); `[CODE] app/webview/hot_reload.py:84` (`PANEL_ASSETS`).

## `app/webview/hotkey_gesture.py` (260 linhas — a regra das teclas, pura)

- **O que faz** — A tabela do gesto: **um passo por pressão, e nenhum relógio**. Ordem do dono, 2026-11-01: *"modifica a legenda ao vivo hotkey. bota o padrao como control espaco. e os painels deixa alt c. faz os paineis alternarem mesmo se eu deixar alt apertado o tempo inteiro e spammando c"* `[CODE] app/webview/hotkey_gesture.py:1`. Isto **substitui** o contrato anterior, que media a DURAÇÃO da segurada com três relógios a discordar (`HOTKEY_HOLD_MS`, `HOTKEY_TAP_WINDOW_MS`, `HOLD_CEILING_MS`) e uma thread a fazer polling para medir o que o dono já sabia `[CODE] app/webview/hotkey_gesture.py:12`. As funções puras são `parse_accelerator`, `hotkey_numbers`, `next_surface` e `advance`.
- **Quem o chama** — O shell (o despacho da tecla e o ciclo dos painéis), e o `hotkey_settings` para validar o ficheiro dele `[CODE] app/webview/sotto_webview.py:2953`.
- **O que escreve/lê** — Nada: é puro de propósito, porque é ele que o oráculo executa. `MODIFIER_BITS` é a tabela que `hotkey_numbers()` lê.
- **Quando falha** — Um acelerador que não faz parse devolve `None` e o chamador cai no default de fábrica. Um gesto a meio (tecla presa, `keyup` perdido) não deixa estado: o contador de toques é drenado no primeiro token.
- **Evidência** — `[CODE] app/webview/hotkey_gesture.py:123` (`parse_accelerator`); `[CODE] app/webview/hotkey_gesture.py:195` (`next_surface`); `[CODE] app/webview/hotkey_gesture.py:235` (`advance`). Portão: `_main/altc-gesture-oracle.py` e `_main/hotkey-spam-oracle.py` (19 arms).

## `app/webview/hotkey_settings.py` (161 linhas — a tecla num ficheiro)

- **O que faz** — Guarda as teclas do dono em disco (os painéis e a legenda ao vivo), e o interruptor `panels_enabled`. Existe porque a *regra* (`hotkey_gesture.py`) tem de continuar pura e importável sem I/O — é ela que o oráculo executa — e porque uma tecla que muda mora num ficheiro, não numa constante `[CODE] app/webview/hotkey_settings.py:1`. Três propriedades que se pagam sozinhas: um ficheiro estragado não deixa o Sotto sem hotkey (tudo o que não se lê volta ao valor de fábrica), uma escolha sobrevive ao reinício, e o menu da bandeja reescreve o texto da acção.
- **Quem o chama** — O shell, no estado das teclas `[CODE] app/webview/sotto_webview.py:8051`.
- **O que escreve/lê** — `_main/hotkey-settings.json` (`PATH`), com `_CACHE` para não reler o disco a cada tique. Chaves `PANELS_KEY`, `LIVE_KEY`, `PANELS_ENABLED_KEY`.
- **Quando falha** — Tudo o que não resolve cai em `DEFAULTS`. Um valor fora do vocabulário é descartado, nunca aceite: um `panels_enabled` que não é booleano lê-se como o default.
- **Evidência** — `[CODE] app/webview/hotkey_settings.py:55` (`DEFAULTS`); `[CODE] app/webview/hotkey_settings.py:73` (`accelerators`); `[CODE] app/webview/hotkey_settings.py:136` (`panels_enabled`). Portão: `_main/hotkey-panels-switch-oracle.py`.

## `app/webview/load_shedding.py` (1 265 linhas — o shedding por carga)

- **O que faz** — Decide **que motor corre** pela pressão da máquina. Ordem do dono, verbatim: *"shedding por carga -- alta: desliga nemotron, so parakeet; muito alta: desliga parakeet tambem. AUDIO SEMPRE fica para processar depois"* `[CODE] app/webview/load_shedding.py:1`. A regra é desigual de propósito: o nemotron (ao vivo, caro) cai primeiro, o parakeet (lote, leve) cai depois, e o **áudio nunca é a coisa que se larga**. A escada tem histerese e um piso de permanência (`MIN_DWELL_S`) para não oscilar.
- **Quem o chama** — O shell (o monitor e a acção) e o `batch_queue` e o `warm_engine` `[CODE] app/webview/sotto_webview.py:14112`.
- **O que escreve/lê** — Lê `SOTTO_LOAD_SHED`, `SOTTO_LOAD_SHED_ACT`, `SOTTO_REDUX_WHEN_HIDDEN`, `SOTTO_CAPTURE_MODE`. Lê commit e carga do sistema por `sample_load`. Publica o nível em `panel-visibility.json` (é o ficheiro que o worker **obedece**).
- **Quando falha** — A acção é **ARMADA por omissão** (`ACTION_ARMED_DEFAULT = True`, ordem do dono de 2026-11-03); `SOTTO_LOAD_SHED_ACT=0` desarma-a e existe para as corridas de medição, não para o dia-a-dia `[CODE] app/webview/load_shedding.py:836`. A histerese é assimétrica de propósito: subir de nível é imediato (segurança), descer espera `CONFIRM_SAMPLES` e há um piso de `ACTION_FLOOR_S = 180 s` entre duas descidas, porque descer é o que **recarrega modelo** `[CODE] app/webview/load_shedding.py:839`.
- **Evidência** — `[CODE] app/webview/load_shedding.py:86` (`level_for`); `[CODE] app/webview/load_shedding.py:450` (`sample_load`); `[CODE] app/webview/load_shedding.py:1222` (`open_action`). Portão: `_main/load-shedding-oracle.py`.

## `app/webview/no_console.py`

- **O que faz** — É o par que esconde de facto a consola de um processo filho: devolve os kwargs de `subprocess.Popen` com `creationflags |= CREATE_NO_WINDOW` (0x08000000) MAIS um `STARTUPINFO` com `STARTF_USESHOWWINDOW` e `wShowWindow = 0` (SW_HIDE). `creationflags` sozinho não chega quando o pai não tem consola — e neste produto nenhum pai tem (`pythonw.exe`). Fora do Windows devolve só `creationflags` (o extra pedido), porque `startupinfo()` devolve `None`.
- **Quem o chama** — `SpeakerSidecar.start` (`[CODE] app/webview/sotto_webview.py:23145`), o spawn do worker (`[CODE] app/webview/sotto_webview.py:23910`), `reveal_in_folder` (`[CODE] app/webview/sotto_webview.py:16424`), `batch_queue` (`[CODE] app/webview/batch_queue.py:626`) e `shell_relaunch` (`[CODE] app/webview/shell_relaunch.py:280`).
- **O que escreve/lê** — Nada: não escreve ficheiros nem env vars, não lê estado, não emite log. A única leitura é `os.name` para decidir se o par é aplicável.
- **Quando falha** — Não tem ramo de erro. Em `os.name != 'nt'`, `startupinfo()` devolve `None` e `popen_kwargs()` devolve apenas `{'creationflags': flags}`; em Windows devolve também `'startupinfo'` (`[CODE] app/webview/no_console.py:58`). O consumidor (`_main/console-window-audit.py`, citado no cabeçalho) é quem recusa um spawn com `creationflags` sem este par.
- **Evidência** — `[CODE] app/webview/no_console.py:39` (`CREATE_NO_WINDOW = 0x08000000`); `[CODE] app/webview/no_console.py:44` (ramo não-Windows); `[CODE] app/webview/no_console.py:56` (OR dos flags).

## `app/webview/overlay_paint.py` (1 126 linhas — a metade pura da pintura)

- **O que faz** — Toda a aritmética da legenda nativa que se pode medir **sem abrir janela**: medir texto, escolher a fonte, calcular o layout dentro do orçamento de largura, compor o bitmap pré-multiplicado e a **cache de tinta** (a chave guarda o raster, e um hit custa 0,063 ms contra 6,55 ms a reconstruir o texto inteiro) `[CODE] app/webview/overlay_paint.py:1`. Existe por causa do ratchet: `caption_overlay.py` cresceu para 1 337 linhas e uma função de 146, e a cura que o próprio ratchet nomeia é extrair sem tocar no comportamento `[CODE] app/webview/overlay_paint.py:692`.
- **Quem o chama** — `caption_overlay.py` (a janela) e o shell `[CODE] app/webview/sotto_webview.py:22147`.
- **O que escreve/lê** — Nada persistente. Lê a env var `SOTTO_CAPTION_OVERLAY_PNG` (salva o bitmap para inspecção) e os ficheiros de fonte de `_FONT_DIR`. Estatísticas da cache em `_PAINT_CACHE_STATS`.
- **Quando falha** — Tudo o que falha devolve o **default** em vez de levantar: uma família de fonte que não resolve cai em `_THEME_DEFAULT`, um número ilegível cai no `_num` do default. A consequência de um defeito aqui é visual (placa errada, linha cortada), nunca uma excepção que mate a legenda.
- **Evidência** — `[CODE] app/webview/overlay_paint.py:38` (`_measure`); `[CODE] app/webview/overlay_paint.py:604` (`_layout`); `[CODE] app/webview/overlay_paint.py:729` (`_paint_cache_get`). Portão: `_main/paint-cost-oracle.py`.

## `app/webview/panel_focus.py`

- **O que faz** — É a política de primeiro plano do painel, e os únicos sítios do shell que chamam `SetForegroundWindow`. `pointer_lock_state()` lê o clip rect do cursor (`GetClipCursor` contra `SM_CXVIRTUALSCREEN`/`SM_CYVIRTUALSCREEN`, tolerância de 8 px) para saber se a app em primeiro plano tem o rato preso. `foreground_unlock()` só toma o primeiro plano quando há pointer lock (`SW_RESTORE` + `SW_SHOW` + `SetForegroundWindow`, com `AttachThreadInput` como segunda tentativa); com o cursor livre mapeia o painel com `SW_SHOWNOACTIVATE` e não rouba o foco. `set_topmost()` re-afirma `HWND_TOPMOST` sem mover, redimensionar nem activar.
- **Quem o chama** — O shell embrulha as três entradas: `set_topmost(hwnd)` (`[CODE] app/webview/sotto_webview.py:7275`, usada em `13615` e `16632`), `pointer_lock_state()` (`[CODE] app/webview/sotto_webview.py:7308`) e `foreground_unlock(hwnd)` (`[CODE] app/webview/sotto_webview.py:7313`, usada em `17119`/`17207`). `selftest_instrument.run_selftest` recebe `pointer_lock_state` por parâmetro e não importa daqui.
- **O que escreve/lê** — Não escreve ficheiros nem estado. Lê `GetClipCursor`, `GetCursorInfo`, `GetSystemMetrics` e `GetForegroundWindow`. Emite as tags `FOREGROUND_TAKEN` / `FOREGROUND_KEPT` (uma por show) e `PANEL_FOREGROUND_ATTACH` / `PANEL_FOREGROUND_ATTACH_FAILED` / `PANEL_FOREGROUND_UNLOCK_FAILED`. Importa `CURSORINFO` e `RECT` de `win32_types`.
- **Quando falha** — `foreground_unlock` nunca levanta: qualquer excepção vira `PANEL_FOREGROUND_UNLOCK_FAILED error=...`, `reason='failed'` no dict devolvido e o Alt+C segue (`[CODE] app/webview/panel_focus.py:212`). `pointer_lock_state` também não levanta: um probe falhado devolve `clipped=False` e `detail='clip-probe-failed=...'` (`[CODE] app/webview/panel_focus.py:109`) — errar para "não roubar o foco". `set_topmost` devolve o booleano do `SetWindowPos`.
- **Evidência** — `[CODE] app/webview/panel_focus.py:47` (`set_topmost`); `[CODE] app/webview/panel_focus.py:154` (`foreground_unlock`); `[CODE] app/webview/panel_focus.py:208` (tag `FOREGROUND_KEPT`).

## `app/webview/panel_state.py` (347 linhas — o painel em texto)

- **O que faz** — Escreve o estado do painel num **único JSON**, a cada `interval_s` e a pedido, para que o estado se leia do disco por qualquer instrumento, sem olhos e sem captura de ecrã. Todos os campos são estado que a app **já** tem, lidos onde já aterra (o `WorkerBridge.state` e a sua máquina de estados), nunca um segundo caminho que possa discordar `[CODE] app/webview/panel_state.py:1`.
- **Quem o chama** — O shell (`import panel_state`), que escreve por `PanelStateWriter` `[CODE] app/webview/sotto_webview.py:69`.
- **O que escreve/lê** — `_main/panel-state.json` (`SCHEMA`), com `write_atomic` (ficheiro temporário + rename), porque um leitor nunca pode apanhar um JSON a meio. `read_state`, `age_seconds` e `freshness` são o lado leitor; `main --request` pede um dump imediato.
- **Quando falha** — A **idade não é auto-reportada**: um ficheiro velho lê-se como velho (`freshness`), não como verdade. Um escritor que morre deixa o ficheiro com a idade a crescer, e o leitor diz `STALE` em vez de "igual".
- **Evidência** — `[CODE] app/webview/panel_state.py:118` (`PanelStateWriter`); `[CODE] app/webview/panel_state.py:231` (`freshness`); `[CODE] app/webview/panel_state.py:307` (`main`).

## `app/webview/power_recovery.py`

- **O que faz** — Traduz as mensagens de energia e de sessão do Windows (`WM_POWERBROADCAST`, `WM_WTSSESSION_CHANGE`) em eventos com nome — `resume`, `unlock`, `connect` — e num plano puro de acções (`topmost`, `worker`, `geometry`): resume pede as três, unlock e connect pedem topmost+geometria, e lock/suspend/logoff não pedem nada. O transporte é uma janela POPUP top-level de tamanho zero, criada numa thread própria com bomba de mensagens, que recebe os broadcasts e chama os handlers; nenhuma acção levanta as outras.
- **Quem o chama** — `SottoShell._start_power_recovery` constrói `PowerRecovery({ACT_TOPMOST: _topmost, ACT_WORKER: _worker, ACT_GEOMETRY: _geometry}, log=log)` e chama `.attach()` (`[CODE] app/webview/sotto_webview.py:13643`); o resultado é logado em `POWER_RECOVERY_READY`.
- **O que escreve/lê** — Não escreve ficheiros nem env vars. Lê as constantes Win32 e o registo de notificações de sessão (`WTSRegisterSessionNotification`); mantém em memória `fired`, `hwnd`, `_registered`. Tags: `POWER_RECOVERY_ATTACHED`, `POWER_RECOVERY_CLASS_FAILED`, `POWER_RECOVERY_WINDOW_FAILED`, `POWER_RECOVERY_REGISTER_FAILED`, `POWER_RECOVERY_WNDPROC_FAILED`, `POWER_RECOVERY_DETACHED`, `POWER_RESUME event=... actions=...`, `POWER_RESUME_ACTION_FAILED`. A thread chama-se `sotto-power-window`.
- **Quando falha** — `RegisterClassExW` falha com erro diferente de 1410 (classe já existe num restart) → `POWER_RECOVERY_CLASS_FAILED` e `attach()` devolve `self._registered` (False), sem levantar (`[CODE] app/webview/power_recovery.py:218`); `CreateWindowExW` falha → `POWER_RECOVERY_WINDOW_FAILED`. Um handler que levanta é apanhado e vira `POWER_RESUME_ACTION_FAILED`, e o ciclo continua (`[CODE] app/webview/power_recovery.py:301`). Nada disto impede a app de subir: o `attach()` do shell está dentro de `try` e um erro vira `POWER_RECOVERY_ATTACH_FAILED`.
- **Evidência** — `[CODE] app/webview/power_recovery.py:72` (o plano `_PLANS`); `[CODE] app/webview/power_recovery.py:79` (`classify`); `[CODE] app/webview/power_recovery.py:292` (tag `POWER_RESUME`).

## `app/webview/run-cmd-log-append.py`

- **O que faz** — Acrescenta um recibo ao log do shell a partir do sítio onde o `cmd.exe` não consegue: `open(..., "a")` em vez de `>>`, porque o `>>` do `cmd` leva erro 32 com a app a correr. Aceita `--append-file PATH` (lê o ficheiro e acrescenta o texto, garantindo newline final) e `--line TEXT`, pela ordem em que aparecem. Não imprime nada — corre sob `pythonw.exe`, cujo stdout é `None` — e SAI 0 mesmo quando a escrita falha, porque um recibo perdido não pode transformar um bom arranque num arranque falhado.
- **Quem o chama** — O `run.cmd` chama-o duas vezes com o interpretador windowless: `"%PYW%" "%HERE%run-cmd-log-append.py" ... --append-file "%REFUSAL%" --line "sotto: PREFLIGHT_REFUSED ..."` (`[CODE] app/webview/run.cmd:268`) e a variante `--line "sotto: HANG rc=4 by=run.cmd-readiness"` (`[CODE] app/webview/run.cmd:318`). Não é importado por nenhum módulo Python.
- **O que escreve/lê** — Escreve no ficheiro de log cujo caminho é o primeiro argumento (`_main/webview-run.log`, na chamada do `run.cmd`), em UTF-8 e modo append; lê o ficheiro indicado por `--append-file`. Erros vão para `stderr` com o prefixo `run-cmd-log-append:` — que sob `pythonw` não vai a lado nenhum.
- **Quando falha** — Sem argumentos → `return 2`; argumento desconhecido → `return 2` (`[CODE] app/webview/run-cmd-log-append.py:65`); ficheiro de `--append-file` ilegível → mensagem em stderr e esse pedaço é omitido; falha ao abrir o log para append → mensagem em stderr e `return 0` (`[CODE] app/webview/run-cmd-log-append.py:74`). Sem texto nenhum → `return 0` sem tocar no ficheiro.
- **Evidência** — `[CODE] app/webview/run-cmd-log-append.py:45` (`def main`); `[CODE] app/webview/run-cmd-log-append.py:68` (o ramo sem texto); `[CODE] app/webview/run-cmd-log-append.py:75` (`return 0` depois de falhar a escrita).

## `app/webview/selftest_instrument.py`

- **O que faz** — É o instrumento das duas medições do shell, fora do produto. `run_selftest` prova que as duas hotkeys entregam exactamente um passo por pressão, em seis armas (quatro pressões isoladas, dez pressões em sequência e um Ctrl+Space), usando `simulate_press` (um `WM_HOTKEY` posto na fila real) e nunca `keybd_event`; mede ENTREGA (`posted`) e LATÊNCIA (`latency_ms` contra `SELFTEST_STEP_BUDGET_MS`, 1500 ms) como duas cláusulas separadas. `selftest_broken` é o veredicto puro. `probe_reload` prova a guarda de reload do worker em três armas (guard, storm, burst) contra ficheiros e um watcher reais.
- **Quem o chama** — `SottoShell.run_selftest` delega com as peças do produto por parâmetro (`[CODE] app/webview/sotto_webview.py:22625`); `probe_reload()` do shell chama `selftest_instrument.probe_reload(...)` (`[CODE] app/webview/sotto_webview.py:26186`); o shell importa os nomes como superfície histórica (`[CODE] app/webview/sotto_webview.py:95`).
- **O que escreve/lê** — Cria e apaga um directório temporário `sotto-reload-` com `panel/` e `worker/` em `probe_reload`; fora disso não escreve ficheiros nem env vars. Lê a janela em primeiro plano (`GetForegroundWindow`) e o PID dono (`GetWindowThreadProcessId`). Tags: `SELFTEST threads`, `SELFTEST state=hidden`, `SELFTEST step=`, `SELFTEST arm=5-ten`, `SELFTEST focus_steals=`, `SELFTEST focus_before=`/`focus_after=`, `SELFTEST broken=`, `SELFTEST expectation=`, `SELFTEST rc=`, `HOTKEY_STOP_FAILED`; `probe_reload` imprime `ARM ...`/`VERDICT ...`/`SELFTEST reload rc=`.
- **Quando falha** — Se uma das threads de hotkey não sobe: `SELFTEST broken=um dos threads da hotkey nao subiu`, `SELFTEST rc=3` e `shell.request_exit(3, reason='selftest-threads')` (`[CODE] app/webview/selftest_instrument.py:269`). Com veredicto `broken`, `rc = 3`; nos dois casos o fim é `shell.request_exit(rc, reason='selftest')`. Em `probe_reload`, um watcher que não arranca devolve 3, e cada arma que não bate o esperado põe `rc = 3`.
- **Evidência** — `[CODE] app/webview/selftest_instrument.py:80` (orçamento); `[CODE] app/webview/selftest_instrument.py:102` (veredicto puro); `[CODE] app/webview/selftest_instrument.py:468` (`probe_reload`).

## `app/webview/shell_relaunch.py` (511 linhas — a app reabre-se sozinha)

- **O que faz** — Reabre a app quando o **próprio fonte** muda: sem acção do dono, sem aprovação. Existe porque mostrar uma mudança de código no ecrã dele exigia uma de duas coisas, e ele recusou as duas — uma lane a largar a app (proibido por `SOTTO_NEVER_ON_OWNER_SCREEN`) ou ele a fechar e reabrir. Medido em 2026-10-30: dos cinco caminhos de largada a partir desta pane (`medium`, o desktop dele `high`), filho directo não fala com a taskbar/WebView2, `explorer.exe <ficheiro>` não executa (0/3), token emprestado do Explorer nunca executa, `CreateProcessAsUser` dá `err=5`; o **único** que executa é a tarefa agendada dele `[CODE] app/webview/shell_relaunch.py:1`.
- **Quem o chama** — O shell, no fim do `main()`: `shell_relaunch.arm(shell, log)` `[CODE] app/webview/sotto_webview.py:27299`.
- **O que escreve/lê** — O contador de relançamentos (`COUNTER_REL`, lido/escrito por `_read_counter`/`_write_counter`) e o `fingerprint` do fonte. Vigia `WATCH_DIRS` com `WATCH_SUFFIXES`.
- **Quando falha** — A escada de limites existe para o vigia não virar um ciclo: `STABLE_S` (só depois de a app estar estável), `FLOOR_S` (piso entre relançamentos), `CAP_PER_HOUR` (tecto por hora) e `BACKOFF_S`. Audio a tocar recusa o relançamento (`sound_playing`). Um relançamento recusado **diz por quê**.
- **Evidência** — `[CODE] app/webview/shell_relaunch.py:92` (`fingerprint`); `[CODE] app/webview/shell_relaunch.py:138` (`within_cap`); `[CODE] app/webview/shell_relaunch.py:288` (`arm`). Portão: `_main/shell-relaunch-oracle.py`.

## `app/webview/sotto_webview.py` (27 364 linhas — a shell inteira)

- **O que faz** — É o processo que o dono abre: cria a janela WebView2, serve `app/panel/panel.html` **byte a byte** (não há segundo copy do painel), expõe à página o objecto `window.sotto` e é o **dono único** de tudo o que é sistema operativo — a tecla global, a bandeja, a legenda nativa, o worker filho, o motor quente, a fila de lote, o vigia da UI e o matador da própria saída. Substituiu a shell Electron (`app/_legacy-electron/main.js`), e o contrato com a página é um port linha-a-linha de `preload.js` `[CODE] app/webview/sotto_webview.py:1`. A forma é de **classes com uma responsabilidade cada**: `SottoShell` (221 métodos, a coordenação), `SottoHost` (a janela), `WorkerBridge` (26 métodos, a vida do worker filho), `ExternalCaptionWatcher` (52, o caminho do YouTube), `TrayIcon` (19, a bandeja), `CaptionOverlay` fica noutro ficheiro `[CODE] app/webview/sotto_webview.py:4919`.
- **Quem o chama** — Ninguém: é o `main()` do processo. Entra por `app/webview/run.cmd` (o `.cmd` lê `--help` do próprio shell) e é o **único** ficheiro do repo cujo `main()` é o produto. Tudo o resto ou é importado por ele, ou é um subprocesso que ele larga.
- **O que escreve/lê** — É o maior escritor de estado do produto: `_main/webview-run.log` (o log vivo), `_main/panel-state.json` (`panel_state`), `_main/panel-visibility.json` (o ficheiro que o **worker obedece**), `_main/caption-settings.json`, `_main/caption-wanted.json`, `_main/shell-relaunch.json`, `_main/diar-watch.json`, `_main/_startup-stacks.log` (o dump das threads no arranque). Lê dezenas de env vars, e três delas mudam o produto: `SOTTO_CAPTURE_MODE`, `SOTTO_REDUX_WHEN_HIDDEN` e `SOTTO_CDP_PORT`. Tags de log: mais de 200, e as que o dono vê no painel são as que começam por `BRIDGE_`, `CAPTION_`, `PANEL_`, `YOUTUBE_`, `HOTKEY_` `[CODE] app/webview/sotto_webview.py:369`.
- **Quando falha** — Três classes, cada uma com o seu tratamento: (1) **a página não responde** — há um orçamento (`SHOW_BUDGET_MS`, `CONTENT_GATE_TIMEOUT_MS`) e um retry que **divide o orçamento entre tentativas** (`CONTENT_GATE_ATTEMPT_FRACTION`), porque uma pergunta que consome tudo nunca tem segunda `[CODE] app/webview/sotto_webview.py:442`; (2) **o worker morre** — o `WorkerBridge` respawna com escada de backoff e um piso de 20 s para uma saída limpa (`CLEAN_EXIT_FLOOR_MS`), e carimba a causa (`BRIDGE_DEATH_CAUSE`) `[CODE] app/webview/sotto_webview.py:2007`; (3) **a saída não completa** — `_hard_exit` escala em 2,5 s e, se o `ExitProcess` não voltar com CLR/WinForms/WebView2/GDI+ carregados, o matador externo mata por handle `[CODE] app/webview/sotto_webview.py:1917`. O utilizador vê a app fechar-se; nunca um diálogo modal.
- **Evidência** — `[CODE] app/webview/sotto_webview.py:160` (`file_url`); `[CODE] app/webview/sotto_webview.py:751` (`_bridge_census`); `[CODE] app/webview/sotto_webview.py:988` (`history_merge`); `[CODE] app/webview/sotto_webview.py:1917` (`_spawn_exit_killer`); `[CODE] app/webview/sotto_webview.py:2007` (`_hard_exit`). Ratchet estrutural: `_main/code-health-oracle.py` recusa **qualquer** crescimento de bytes/linhas/defs/classes/função-mais-longa/`except: pass`/`global` deste ficheiro — foi por isso que 20 módulos saíram dele para ficheiros próprios.

## `app/webview/space_swallow.py` (395 linhas — a tecla que não vaza)

- **O que faz** — Tira o `Ctrl+Space` do resto do Windows enquanto a legenda o está a usar. Ordem do dono, verbatim: *"control espaço pra ligar ou desligar a legenda nao deve vazar pra outros apps. to usando control espaço pra ativar a legenda quando vejo um video no youtube, e isso faz o espaço pausar o video"* `[CODE] app/webview/space_swallow.py:1`. A medição que o obriga: `RegisterHotKey` **não** tira a tecla do caminho de input — o Windows entrega `WM_HOTKEY` **e** continua a entregar o `WM_KEYDOWN`/`WM_CHAR` à janela em foco. O que a remove é um `WH_KEYBOARD_LL` que engole o evento.
- **Quem o chama** — O shell, no fio da tecla ao vivo `[CODE] app/webview/sotto_webview.py:8325`.
- **O que escreve/lê** — Só o hook; nenhum ficheiro. `STUCK_HELD_S` existe porque um `keyup` perdido deixava a tecla presa para sempre.
- **Quando falha** — O braço que prova a cura é o **estado preso**: `key_down_swallowed` de pé há mais de 3 s sem `keyup` deixava de engolir e a tecla nunca alternava, sem uma linha no log. A testemunha é o **relógio**, não o bit físico (um `keydown` chega sempre com a tecla em baixo).
- **Evidência** — `[CODE] app/webview/space_swallow.py:130` (`classify_event`); `[CODE] app/webview/space_swallow.py:186` (`_real_mods_down`); `[CODE] app/webview/space_swallow.py:72` (`STUCK_HELD_S`). Portão: `_main/ctrlspace-swallow-oracle.py` (21/21) + `_main/ctrlspace-swallow-probe.py` (mede no Windows: a segunda reserva da mesma combinação devolve 1409).

## `app/webview/stage.html`

- **O que faz** — É um documento HTML vazio (só `head` com o título `Sotto (staging)` e um `body` vazio) que existe para o preload poder ser registado ANTES de o painel ser parseado. Não pinta nada, não corre script nenhum, não é o painel nem uma segunda UI: é a página que compra uma navegação de ordenação. O shell abre-a, regista o preload nesse ambiente e só depois navega para `panel.html`.
- **Quem o chama** — `SottoShell.create_window` abre a janela com `url = file_url(STAGE_HTML)` (`[CODE] app/webview/sotto_webview.py:12956`, com `STAGE_HTML` definido em `119`); o `_on_loaded` detecta `here.endswith('/stage.html')` e navega para `PANEL_HTML` (`[CODE] app/webview/sotto_webview.py:14652`); `reload_panel_assets` volta a carregar `STAGE_HTML` para forçar um parse novo (`[CODE] app/webview/sotto_webview.py:22373`).
- **O que escreve/lê** — Nada: é estático, sem script, sem CSS, sem rede. As tags pertencem ao shell (`STAGING_SEEN`, `STAGING_LOADED`).
- **Quando falha** — Dentro do ficheiro não há comportamento que possa falhar. Se a navegação de volta ao painel não acontecer, o que fica no ecrã é uma página em branco — é exactamente o defeito descrito no shell em `14636` e a razão pela qual o bounce passou a ser decidido pelo documento (`_current_document()`), e não pelo booleano `self.staged`.
- **Evidência** — `[CODE] app/webview/stage.html:5` (o título e a ausência de conteúdo); `[CODE] app/webview/sotto_webview.py:119` (`STAGE_HTML`); `[CODE] app/webview/sotto_webview.py:14652` (deteção da página de staging).

## `app/webview/text_normalize.py`

- **O que faz** — Remove a repetição que o motor inventou: uma corrida de `MIN_RUN` (3) ou mais palavras idênticas separadas só por espaço vira uma; uma corrida de 2 só cai quando a palavra NÃO está em `EMPHASIS` (aí precisa de 4). A pontuação quebra a corrida (`Nao, nao, nao.` e `Yeah. Yeah.` não se tocam), e a caixa/pontuação do sobrevivente são as da PRIMEIRA ocorrência — incluindo o ponto final da última. `is_filler_line()` é verdadeiro só quando a linha INTEIRA é preenchimento (`m+`/`hm+`/`mhm+`).
- **Quem o chama** — `_history_entries` aplica `text_normalize.collapse_runs(text)` e de seguida `text_normalize.is_filler_line(text)` ao ler o histórico (`[CODE] app/webview/sotto_webview.py:16213`); `push_caption_to_window` aplica `collapse_runs` só ao caminho do ASR, quando `rows is None` (`[CODE] app/webview/sotto_webview.py:19203`).
- **O que escreve/lê** — Nada: puro stdlib (`re`), sem I/O, sem env vars, sem estado de módulo, sem tags de log. O ficheiro em disco continua o registo cru — a normalização acontece ao ler e ao pintar.
- **Quando falha** — Não há ramo de erro; a garantia é de identidade: sem corrida devolve o MESMO objecto (`text is resultado`) para o caminho vivo não pagar cópia por quadro (`[CODE] app/webview/text_normalize.py:118`), e texto vazio devolve o próprio texto (`[CODE] app/webview/text_normalize.py:90`).
- **Evidência** — `[CODE] app/webview/text_normalize.py:49` (`MIN_RUN = 3`); `[CODE] app/webview/text_normalize.py:53` (`EMPHASIS`); `[CODE] app/webview/text_normalize.py:130` (`is_filler_line`).

## `app/webview/thread_names.py`

- **O que faz** — Dá a cada thread da shell um nome legível de FORA do processo: envolve `threading.Thread.start` uma única vez e, no arranque de cada thread, escreve o `Thread.name` como descrição do SO via `SetThreadDescription` (truncado a `_MAX_CHARS - 1` = 63 caracteres). Cobre também as subclasses que sobrescrevem `run` (para essas `_target` é `None`), trocando `self.run` por um wrapper. `name_current()` existe para o fio principal, que não passa por `install()`. Não muda o corpo de nenhuma thread, é idempotente e engole todos os erros.
- **Quem o chama** — `_open_log` importa o módulo e chama `thread_names.install()` e `thread_names.name_current('sotto-main')` dentro de um `try` (`[CODE] app/webview/sotto_webview.py:2414`).
- **O que escreve/lê** — Escreve a descrição do fio no kernel (`SetThreadDescription`); não escreve ficheiros nem env vars. Mantém o global `_INSTALLED`. Não emite log: um nome é diagnóstico.
- **Quando falha** — `_set_description` devolve `False` quando `SetThreadDescription` não existe ou o Windows recusa (`[CODE] app/webview/thread_names.py:40`); `install()` devolve `False` se o monkey-patch falhar e `True` sem reinstalar quando `_INSTALLED` já é verdadeiro (`[CODE] app/webview/thread_names.py:61`). Nenhuma destas falhas chega ao utilizador — o custo é o fio aparecer sem nome no censo de CPU.
- **Evidência** — `[CODE] app/webview/thread_names.py:33` (`_MAX_CHARS`); `[CODE] app/webview/thread_names.py:47` (o truncamento); `[CODE] app/webview/thread_names.py:102` (`installed`).

## `app/webview/topmost_keepalive.py`

- **O que faz** — Devolve `WS_EX_TOPMOST` à janela quando ela o perde, perguntando de 2 em 2 s. A decisão é pura (`should_reassert`): só age quando a janela está VISÍVEL e o estilo já não tem o bit; uma janela escondida, ou um leitor que devolve `None`, não autoriza nenhuma chamada ao USER32. Quando o bit está lá, o laço não toca em nada — não chama `ShowWindow`, não move, não redimensiona.
- **Quem o chama** — `SottoShell._start_topmost_keepalive` constrói `TopmostKeepalive(hwnd, window_visible, _style_of, set_topmost, log, interval=DEFAULT_INTERVAL_S)` e chama `.start()` (`[CODE] app/webview/sotto_webview.py:13582`); `_style_of` lê `GetWindowLongW(h, GWL_EXSTYLE)`.
- **O que escreve/lê** — Não escreve ficheiros nem env vars; lê o estilo estendido da janela. Tags: `TOPMOST_REASSERT lost=true ticks=N`, `TOPMOST_LOST_STILL ticks=N`, `TOPMOST_READ_FAILED`, `TOPMOST_REASSERT_FAILED`, `TOPMOST_TICK_FAILED`. A thread chama-se `sotto-topmost` e é daemon.
- **Quando falha** — Um leitor que levanta em `tick()` vira `TOPMOST_READ_FAILED error=...` e a volta não age (`[CODE] app/webview/topmost_keepalive.py:82`); uma re-afirmação que levanta vira `TOPMOST_REASSERT_FAILED`; um `reassert` que devolve falso vira `TOPMOST_LOST_STILL` — o bit continua perdido e o laço volta a tentar. O `run()` ainda apanha qualquer excepção do próprio `tick()` como `TOPMOST_TICK_FAILED`, para o laço não morrer.
- **Evidência** — `[CODE] app/webview/topmost_keepalive.py:26` (`WS_EX_TOPMOST`); `[CODE] app/webview/topmost_keepalive.py:34` (`should_reassert`); `[CODE] app/webview/topmost_keepalive.py:94` (tag `TOPMOST_REASSERT`).

## `app/webview/ui_watchdog_policy.py`

- **O que faz** — Decide QUANDO uma amostra do cão-de-guarda da UI conta como golpe, e é pura para poder ser exercitada sem janela. `classify()` devolve uma de quatro palavras: `starved` (o laço demorou mais de `STARVE_FACTOR` × o orçamento, logo a amostra não vale), `answered` (`got` != 0), `strike` (`got == 0` e `err == ERROR_TIMEOUT` 1460) ou `noerr` (`got == 0` sem assinatura). `feed()` mantém duas sequências separadas e devolve `wait`/`confirm`; `confirm()` só manda `exit` com a assinatura 1460; `hard_cap()` fecha o caso sem assinatura às `NOERR_HARD_CAP` (12) voltas.
- **Quem o chama** — `SottoShell._start_ui_watchdog.loop` usa tudo: `_wd_policy.State(self.UI_WATCHDOG_STRIKES)` (`[CODE] app/webview/sotto_webview.py:13408`), `_wd_policy.classify(got, err, took_s, budget_s)` (`[CODE] app/webview/sotto_webview.py:13429`), `_wd_policy.feed(state, kind)` (`[CODE] app/webview/sotto_webview.py:13463`), `_wd_policy.confirm(state, kind)` (`[CODE] app/webview/sotto_webview.py:13481`) e `_wd_policy.hard_cap(state)` (`[CODE] app/webview/sotto_webview.py:13482`).
- **O que escreve/lê** — Nada: sem I/O, sem env vars, sem ficheiros. Constantes verbatim: `ERROR_TIMEOUT = 1460`, `ERROR_INVALID_WINDOW_HANDLE = 1400`, `NOERR_STRIKES = 6`, `NOERR_HARD_CAP = 12`, `STARVE_FACTOR = 1.5`. Não emite tags de log (o shell emite `UI_WATCHDOG_*`); o `_selftest` imprime `PASS`/`FAIL` e `VERDICT: ...`.
- **Quando falha** — Entrada não numérica em `classify` devolve `'starved'`, nunca inventa um golpe (`[CODE] app/webview/ui_watchdog_policy.py:102`); `err` ilegível conta como 0, logo cai em `noerr` e não em `strike`. O módulo não levanta em uso normal; o pior caso é uma amostra inválida que zera a sequência.
- **Evidência** — `[CODE] app/webview/ui_watchdog_policy.py:67` (`NOERR_STRIKES`); `[CODE] app/webview/ui_watchdog_policy.py:74` (`NOERR_HARD_CAP`); `[CODE] app/webview/ui_watchdog_policy.py:126` (`feed`).

## `app/webview/warm_engine.py` (1 626 linhas — o motor quente)

- **O que faz** — Mantém o grafo do ASR **já carregado** num processo que a shell não largou: a shell **anexa-se** a ele por um named pipe e um mutex. Existe por uma medição: a primeira legenda do dia custou **65 037 ms**, e o arranque a frio isolado **9 014 ms** — os dois números têm a mesma forma, a shell não legenda até um processo que ela largou ter lido 1,9 GB de pesos `[CODE] app/webview/warm_engine.py:1`. O contrato é "no máximo um loader", garantido por dois objectos de kernel (`warm_pipe.py`).
- **Quem o chama** — O shell pede-o em `_request_warm_engine`, através da tarefa `SottoWarmEngine` `[CODE] app/webview/sotto_webview.py:18332`. O anexo lê-se em `warm_engine.log`/`warm_engine.pid`.
- **O que escreve/lê** — `warm-engine.log`, `warm-engine.pid`, e lê `panel-visibility.json` (o nível de shedding publicado). TTL de parque `WARM_PARK_TTL_S = 1800 s` — 158x a mediana medida da carga (11 380,6 ms) e 1/4 da menor distância entre duas aberturas (2 h), substituindo os 600 s que pagaram 8 cargas para zero anexos —, ring de áudio `WARM_RING_S = 8,0 s` e orçamento de threads `WORKER_THREADS_DEFAULT = 2` `[CODE] app/webview/warm_engine.py:109`.
- **Quando falha** — A decisão de **pedir ou não** o motor quente não é deste ficheiro: é de `warm_evidence.py`, e por uma razão medida — 8 cargas, 8 saídas, **zero** anexos, com aberturas a distarem 2-16 h contra um TTL de 600 s `[CODE] app/webview/warm_evidence.py:1`. Um `WARM_ATTACH_SHED` é o motor a recusar o anexo porque a máquina está sob carga; nesse caso a shell segue sem ele.
- **Evidência** — `[CODE] app/webview/warm_engine.py:109` (`WARM_PARK_TTL_S`); `[CODE] app/webview/warm_engine.py:291` (`load_gate`); `[CODE] app/webview/warm_engine.py:1560` (`main`). Portão: `_main/warm-engine-oracle.py` (22 arms, 6/6 mutantes).

## `app/webview/warm_evidence.py` (117 linhas — o motor quente paga-se?)

- **O que faz** — Responde, pela **série** e não por omissão, se vale a pena pedir o motor quente. Existe por uma medição (D-04): o shell pedia `SottoWarmEngine` a cada abertura, o motor carregava 7,5-26,0 s de disco e ~1 GB, e saía ao fim do TTL; as aberturas do dono distavam **2 h a 16 h**. Resultado no log inteiro do motor: **8** `WARM_LOAD_MS`, **8** `WARM_EXIT`, **ZERO** `WARM_ATTACHED` — cada carga foi jogada fora, no arranque em que o shell já está a ler 1,9 GB `[CODE] app/webview/warm_evidence.py:1`. A regra é a mais conservadora que resolve isso sem escolher o produto: **com evidência suficiente e zero anexos, não se pede**. Uma evidência curta (menos de `MIN_LOADS` cargas) **não** autoriza recusar — um histórico de duas aberturas não diz nada sobre a terceira `[CODE] app/webview/warm_evidence.py:27`.
- **Quem o chama** — O shell, em `_request_warm_engine` `[CODE] app/webview/sotto_webview.py:18351`.
- **O que escreve/lê** — Nada; é puro. Lê a cauda do log do motor (`SHELL_TAIL_BYTES`, `LOAD_TAG`, `ATTACH_TAG`) e conta as tags.
- **Quando falha** — Sem série legível é **fail-open**: pede (o comportamento anterior). O instante em que um anexo acontece reabre o crédito.
- **Evidência** — `[CODE] app/webview/warm_evidence.py:39` (`verdict`); `[CODE] app/webview/warm_evidence.py:64` (`count_tag`); `[CODE] app/webview/warm_evidence.py:105` (`request_verdict_for`). Portão: `_main/warm-evidence-oracle.py` (13/13, `--neg-arm` 5/5).

## `app/webview/warm_pipe.py` (494 linhas — os primitivos que as duas metades partilham)

- **O que faz** — Os objectos de kernel e os nomes que o motor quente e a shell têm de partilhar **byte a byte**: o pipe nomeado (`FILE_FLAG_FIRST_PIPE_INSTANCE`) e o mutex nomeado segurado pela vida do processo. O motor é criado pelo Task Scheduler, sobrevive à shell, e a shell só lhe pode *anexar* — a "no máximo um loader" (INV-1/INV-2) é propriedade dos dois objectos de kernel, por isso as duas metades partilham **uma** implementação em vez de cada uma carregar a sua cópia da dança Win32 `[CODE] app/webview/warm_pipe.py:1`. **Nada aqui arranca um processo, abre um dispositivo ou toca numa janela** — é o que torna o módulo testável.
- **Quem o chama** — O `warm_engine.py` (que o importa por caminho) e o shell pelo `WarmPipeBridge` `[CODE] app/webview/sotto_webview.py:25603`.
- **O que escreve/lê** — Bytes no pipe; nomes derivados de `model_key`/`pipe_name`. Os códigos de erro são parte do contrato (`ERROR_PIPE_BUSY`, `ERROR_BROKEN_PIPE`, `ERROR_FILE_NOT_FOUND`, `ERROR_ACCESS_DENIED`), porque cada um significa uma acção diferente.
- **Quando falha** — Um nome que não cabe no limite do Windows é recusado por nome, não truncado. Um pipe que já existe é `ERROR_PIPE_BUSY` — a shell *anexa*, não reconstrói.
- **Evidência** — `[CODE] app/webview/warm_pipe.py:35` (`DEFAULT_PIPE_PREFIX`); `[CODE] app/webview/warm_pipe.py:39` (`FILE_FLAG_FIRST_PIPE_INSTANCE`). Portão: `_main/warm-engine-oracle.py`.

## `app/webview/webview2_args.py` (80 linhas — o porto de depuração é nosso)

- **O que faz** — Remove o `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` **herdado** do processo que largou a app. O loader do WebView2 lê essa variável do ambiente do processo uma única vez, quando o ambiente é criado — logo um valor herdado de uma lane, de um terminal com `--remote-debugging-port=9333` ou de um perfil de shell abre um porto de depuração em **todas** as janelas WebView2 da app, e — pior — faz o produto comportar-se diferente na sessão do dono e na de uma lane, que é a pior classe de defeito que existe aqui: a medição passa e o dono não tem o comportamento `[CODE] app/webview/webview2_args.py:1`. O produto não precisa de porto nenhum: a fonte do YouTube lê o browser **do dono** em 9222.
- **Quem o chama** — O shell, dentro de `apply_webview2_environment` `[CODE] app/webview/sotto_webview.py:26743`.
- **O que escreve/lê** — Lê e reescreve a variável de ambiente do próprio processo; `--cdp-port N` / `SOTTO_CDP_PORT=N` é a única forma de a pedir explicitamente.
- **Quando falha** — O plano (`plan`) é puro e testável; se nada há a remover, `apply` não toca no ambiente.
- **Evidência** — `[CODE] app/webview/webview2_args.py:36` (`plan`); `[CODE] app/webview/webview2_args.py:61` (`apply`). Portão: `_main/webview2-args-scope-oracle.py` (12 arms, 3 mutantes).

## `app/webview/win32_types.py`

- **O que faz** — Declara as três estruturas Win32 puras do shell: `RECT`, `POINT` e `CURSORINFO`. São `ctypes.Structure` sem lógica, sem chamadas Win32 e sem dependências deste repo; `CURSORINFO.ptScreenPos` é um `POINT`, e é por isso que os três andam juntos. Saíram do shell por causa do tecto de classes do ratchet, sem mudar um byte do que o Windows vê.
- **Quem o chama** — `panel_focus` importa `CURSORINFO, RECT` (`[CODE] app/webview/panel_focus.py:23`); o shell importa `CURSORINFO, POINT, RECT` (`[CODE] app/webview/sotto_webview.py:105`) e re-exporta os mesmos nomes para `dock_strip`, `clamp_geometry`, `target_display`, `pointer_lock_state` e os `argtypes` de `GetClipCursor`.
- **O que escreve/lê** — Nada. Apenas `import ctypes` e `ctypes.wintypes as wt`; sem env vars, sem ficheiros, sem estado, sem log.
- **Quando falha** — Não tem ramo de erro: são declarações de tipo. Um campo mal declarado não falha aqui — falha como leitura errada no chamador, que é o risco que o cabeçalho nomeia ao manter os três no mesmo sítio.
- **Evidência** — `[CODE] app/webview/win32_types.py:23` (`class RECT`); `[CODE] app/webview/win32_types.py:28` (`class POINT`); `[CODE] app/webview/win32_types.py:32` (`class CURSORINFO`).

## `app/webview/word_fade.py` (126 linhas — o fade da linha nova)

- **O que faz** — O fade de ~120 ms com que uma **linha nova** entra, como no YouTube. Ordem do dono (2026-10-30): *"por que a nossa legenda nao tem a mesma animacao da do youtube? arruma."* `[CODE] app/webview/word_fade.py:1`. Só metade do que o YouTube faz precisa de código aqui: dentro de uma linha as palavras aparecem uma a uma — isso não é animação, é o instante de cada palavra, e resolve-se com o relógio de palavra (`youtube_reveal.word_clock_count`) e a recomposição a 60 ms; o fade da linha nova é **este** ficheiro.
- **Quem o chama** — `caption_overlay`, no tick da janela `[CODE] app/webview/caption_overlay.py:875`.
- **O que escreve/lê** — Nada. `alpha_at`, `done`, `next_delay` e `alpha_out` são aritmética sobre o tempo decorrido. `FRAME_S = 1/240` / `FRAME_HZ = 240` é o **tecto** de quadro que o dono autorizou, não a taxa: quem limita é a pintura medida.
- **Quando falha** — Uma animação que não acaba não existe: `done` fecha por tempo decorrido, não por um quadro que chegou. O relógio é `time.perf_counter`, nunca `monotonic` (nesta máquina o `monotonic` avança de 15 em 15 ms).
- **Evidência** — `[CODE] app/webview/word_fade.py:31` (`DURATION_S`); `[CODE] app/webview/word_fade.py:53` (`alpha_at`); `[CODE] app/webview/word_fade.py:47` (`FRAME_HZ`). Portão: `_main/word-clock-oracle.py`.

## `app/webview/youtube_captions.py` (2 515 linhas — a faixa oficial)

- **O que faz** — Vai buscar a **faixa de legenda real** do vídeo (json3/VTT) e o tempo do player. Ordem do dono, verbatim: *"faz a legenda do youtube mostrar na tela em tempo real. se precisar pegar o tempo do video, faça"* `[CODE] app/webview/youtube_captions.py:1`. Duas peças: o **parser** (`parse_json3`, `parse_vtt`, `cue_at`) e a **escolha de língua**, que carrega a regra das três línguas do dono — `UNTRANSLATED_LANGS = ('en','pt','es')`, com qualquer outra a ir para a língua escolhida em `caption-settings.json` `[CODE] app/webview/youtube_captions.py:625`.
- **Quem o chama** — O shell e o `youtube_monotonic` `[CODE] app/webview/sotto_webview.py:1`.
- **O que escreve/lê** — Uma cache em disco por vídeo (`CACHE_DIR`, `CACHE_SCHEMA`), com quatro TTLs distintos: faixa encontrada, sem faixa, retry de payload e candidato. Lê `SOTTO_YT_CACHE_DIR`, `SOTTO_YT_PLAYER_TRACK`, `SOTTO_YT_PROFILE`.
- **Quando falha** — Sem faixa o resultado é `NO_TRACK` (com TTL curto, para não repetir a busca a cada abertura); um payload ilegível cai no retry, não numa afirmação. Nunca levanta para o chamador: o pior caso é a legenda do YouTube não existir e o ASR local continuar.
- **Evidência** — `[CODE] app/webview/youtube_captions.py:210` (`video_id_from_url`); `[CODE] app/webview/youtube_captions.py:377` (`parse_json3`); `[CODE] app/webview/youtube_captions.py:660` (`_target_langs`). Portão: `_main/youtube-captions-oracle.py` (66 arms, `--neg-arm` 18/18).

## `app/webview/youtube_cdp_source.py` (2 490 linhas — a segunda fonte do YouTube)

- **O que faz** — Lê a legenda do YouTube pelo **DOM do próprio Chrome** através da CDP (DevTools Protocol), em vez da árvore de acessibilidade. Existe por uma medição: com a aba do YouTube em **segundo plano** o Chrome deixa de expor a janela de legenda na árvore de acessibilidade — 3 minutos com o instrumento todo desligado deram **um** `YOUTUBE_CAPTION` e depois nada `[CODE] app/webview/youtube_cdp_source.py:1`. Uma classe, `CdpCaptionSource` (32 métodos), que: resolve a porta, escolhe a aba certa (`choose_target`, `pick_playing`), extrai as linhas e o `video.currentTime` no **mesmo snapshot**, e faz o *rebind* quando a aba morre.
- **Quem o chama** — O shell (`app/webview/sotto_webview.py`), única importação `[CODE] app/webview/sotto_webview.py:1`. O irmão que carrega é `youtube_window.py`, importado **pelo caminho** porque o nome tem hífen.
- **O que escreve/lê** — Lê `SOTTO_YT_CDP_PORT` (default `DEFAULT_PORT`) e nada mais do ambiente. Não escreve ficheiros de estado: as linhas vão para o shell, que as guarda em `_LAST_PLAYER_TRACK`. As tags de erro são em português de propósito: `slow`, `dead`, `FAILED`.
- **Quando falha** — A classe do defeito que já custou uma sessão: **reconexão não é evidência de troca de vídeo**. Uma aba adoptada numa reconexão fabricava o `VIDEO_CHANGED` que ela própria depois reportava — `adopted` 5 vezes, `CAPTION_WINDOW_BLANKED` 46 vezes, com 7 ms a carregar dois blanks. Por isso `pick` nunca adopta aba que não seja o vídeo declarado, e nunca prefere uma `paused-loaded` a uma a tocar `[CODE] app/webview/youtube_cdp_source.py:681`. Um prazo de leitura estourado é `slow` (rotina, 65 vezes numa sessão), não `dead`.
- **Evidência** — `[CODE] app/webview/youtube_cdp_source.py:80` (`resolve_port`); `[CODE] app/webview/youtube_cdp_source.py:159` (`EXTRACT_JS`); `[CODE] app/webview/youtube_cdp_source.py:842` (`parse_snapshot`); `[CODE] app/webview/youtube_cdp_source.py:1225` (`rebind_verdict`). Portão: `_main/youtube-cdp-source-oracle.py`.

## `app/webview/youtube_clock.py` (184 linhas — a tolerância da adivinha)

- **O que faz** — Governa **quanto** se pode adivinhar o relógio do player entre duas leituras, pelo que o player nos disse. O defeito que o obriga (dono, 2026-11-07): *"e ridiculo o fato que um stutter qualquer do meu pc, faca a legenda dessincronizar ... se a porra da legenda do youtube ta se movendo, mesmo com o stutter acontecendo, a NOSSA legenda que pegamos do youtube, TAMBEM"* `[CODE] app/webview/youtube_clock.py:1`. O número é medido, não escolhido: `_main/fixtures/yt-paint-freeze-20261104.json` tem 745 amostras reais do Chrome dele, e para pares a 3-5 s o erro de extrapolar com o relógio de parede é mediana 1 ms / p95 4 ms / máximo 34 ms.
- **Quem o chama** — O shell, no caminho do YouTube e no rebase da primeira amostra autoritativa `[CODE] app/webview/sotto_webview.py:5483`.
- **O que escreve/lê** — Nada; aritmética sobre `player_state` (PLAYING/PAUSED/ENDED/UNKNOWN) e o instante da amostra.
- **Quando falha** — Um estado ausente **não** é "a andar": serve-se a amostra em vez de extrapolar (`paused` ausente não é afirmação). Um `rebase` desfaz o que nós adiantámos na primeira amostra autoritativa.
- **Evidência** — `[CODE] app/webview/youtube_clock.py:87` (`state_of`); `[CODE] app/webview/youtube_clock.py:121` (`instant`); `[CODE] app/webview/youtube_clock.py:160` (`rebase`). Portão: `_main/stutter-caption-oracle.py` (14 arms).

## `app/webview/youtube_monotonic.py` (285 linhas — a legenda não recua)

- **O que faz** — Garante que o relógio do player **nunca** faz a legenda recuar. A queixa do dono (2026-10-30): *"a legenda nao ta sincronizada direito. e parece que repete a legenda de instantes atras no ao vivo, depois desbuga, e mostra ao vivo"* `[CODE] app/webview/youtube_monotonic.py:1`. Medido em `_main/webview-run.log` (2 126 linhas `YOUTUBE_CAPTION`): **129** linhas são um cue cujo INÍCIO é anterior ao da linha servida antes — 37,6 s atrás, 40,4 s atrás, e uma **359,0 s** atrás; a cue `start=34.239` foi servida **três vezes em 24 s**. Não era lentidão: era um relógio congelado que o ramo `painted-other-track` confiava.
- **Quem o chama** — O shell, em `_yt_decide` `[CODE] app/webview/sotto_webview.py:5629`.
- **O que escreve/lê** — Nada; `decide` e `advance` são puras. `paint_signature`/`PaintStall` detectam a pintura parada, `STALE_S` e `CUE_SAME_EPS` separam um seek para trás legítimo de um congelamento.
- **Quando falha** — Um **seek** do dono para trás é honrado (`SEEK_BACK_S`), não estrangulado: a regra distingue recuo espúrio de recuo pedido. Sem assinatura da pintura, não se afirma paragem.
- **Evidência** — `[CODE] app/webview/youtube_monotonic.py:50` (`decide`); `[CODE] app/webview/youtube_monotonic.py:143` (`paint_signature`); `[CODE] app/webview/youtube_monotonic.py:155` (`PaintStall`). Portão: `_main/youtube-monotonic-oracle.py`.

## `app/webview/youtube_reveal.py` (811 linhas — a janela revelada)

- **O que faz** — A janela revelada pelas palavras que o player **já pintou**, para a nossa legenda aparecer palavra a palavra como no YouTube. Ordem do dono (2026-10-22): *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou nao, igual o youtube"* `[CODE] app/webview/youtube_reveal.py:1`. O `parse_json3` carrega o `tOffsetMs` de 69 dos 106 segmentos para dentro dos cues, e `youtube_window.revealed_lines` corta a linha no instante certo — medido, o prefixo revelado bate com o do payload em **0/677** divergências.
- **Quem o chama** — O shell, no caminho de pintura do player `[CODE] app/webview/sotto_webview.py:6619`.
- **O que escreve/lê** — Nada. `painted_prefix_count`, `word_clock_count`, `window_by_paint`, `rows_from_cues` e `row_text` são puras.
- **Quando falha** — Sem `tOffsetMs` no payload, não há revelação palavra a palavra e a linha aparece inteira — degradação, nunca truncagem a meio de uma palavra. `MAX_LAG_S` e `WORD_GAP_S` limitam o que se mostra.
- **Evidência** — `[CODE] app/webview/youtube_reveal.py:235` (`word_clock_count`); `[CODE] app/webview/youtube_reveal.py:283` (`window_by_paint`); `[CODE] app/webview/youtube_reveal.py:410` (`rows_from_cues`). Portão: `_main/youtube-1to1-oracle.py` (arm `word-reveal-1to1`).

## `app/webview/youtube_window.py` (551 linhas — o display de duas linhas)

- **O que faz** — O display do YouTube **como ele o define**: duas linhas, quebra por linha, o histórico e a linha pintada. Ordem do dono (2026-10-22): *"e tambem ter o display 1:1. e pra surgir palavras, quebrar linhas..."* `[CODE] app/webview/youtube_window.py:1`. É também o **dono único** da lista de marcadores de fala (`_SPEAKER_MARKERS`): o `>>` (`&gt;&gt;` antes de descodificar, `>>` depois, `\u203a\u203a` na faixa automática) é do PLAYER e morre na entrada de cada caminho — `strip_speaker_markers` aplica-se a `rows`, `items` e `segs` `[CODE] app/webview/youtube_window.py:246`.
- **Quem o chama** — O shell, no caminho do YouTube e no carregamento do irmão pelo caminho `[CODE] app/webview/sotto_webview.py:4932`.
- **O que escreve/lê** — Nada persistente. `CAPACITY`, `ROWS_CAP` e `COLS` fixam a geometria; `window_key`, `history_line` e `paint_line` produzem as três formas de texto do mesmo cue.
- **Quando falha** — `collapse_growth` impede o muro de prefixos (nove `<li>` para a mesma frase, cada uma com mais palavras que a anterior). Um cue sem marcador de fala não é adivinhado.
- **Evidência** — `[CODE] app/webview/youtube_window.py:140` (`revealed_lines`); `[CODE] app/webview/youtube_window.py:351` (`strip_speaker_markers`); `[CODE] app/webview/youtube_window.py:381` (`painted_rows`). Portão: `_main/youtube-rows-oracle.py` e `_main/youtube-cdp-source-oracle.py` (arm `sem-marcador-de-fala`).

## `app/webview/z_order.py`

- **O que faz** — Decide e aplica QUAL das duas janelas do Sotto fica por cima: o painel, sempre, quando as duas estão visíveis. Três peças, as duas primeiras puras: `should_raise(panel_visible, caption_visible, panel_above_caption)` devolve `False` se qualquer uma estiver escondida (mover o Z de quem ninguém vê é uma chamada ao USER32 sem efeito) e `True` só quando as duas aparecem e a legenda está por cima `[CODE] app/webview/z_order.py:43`; `is_above(target, below, prev_of)` sobe a cadeia a partir de `below` com `GetWindow(h, GW_HWNDPREV)` e devolve `False` para `target == below` (uma janela não está acima de si própria, e dizê-lo faria o aplicador não agir no dia em que os dois handles coincidissem), com tecto `CHAIN_LIMIT = 64` `[CODE] app/webview/z_order.py:40,55`. A terceira é `ZAuthority`, que recebe **todas** as chamadas ao sistema por argumento (`panel_of`, `caption_of`, `visible_of`, `prev_of`, `insert_below`, `log`) para o oráculo poder conduzir a decisão sem abrir janela `[CODE] app/webview/z_order.py:78`.
- **Quem o chama** — `SottoShell._z_authority()` constrói-o **uma vez** (cache em `_z_authority_cache`) sobre `user32.GetWindow`, `window_visible` e o `insert_below` do módulo `[CODE] app/webview/sotto_webview.py:13824`. `_raise_above_caption(why)` é a porta única e corre em dois caminhos: em cada `show` do painel (`show-panel`, `show-strip`, `show-side`) `[CODE] app/webview/sotto_webview.py:16991,17442,17535`, e no tique de 2 s do `topmost_keepalive` como `extra=lambda: self._raise_above_caption('keepalive')` `[CODE] app/webview/sotto_webview.py:13894`. O `caption_overlay` lê o provedor `z_below` logo abaixo do mapa da legenda, para a linha nova não voltar a subir por cima do painel `[CODE] app/webview/caption_overlay.py:598,1926`.
- **O que escreve/lê** — Não escreve ficheiros nem env vars; lê handles, `IsWindowVisible` e a cadeia de Z. Tags: `Z_ORDER_RAISED why=... panel=N caption=N raised=N` (só quando a escrita devolveu sucesso), `Z_ORDER_RAISE_REFUSED`, `Z_ORDER_RAISE_FAILED`, `Z_ORDER_READ_FAILED`, `Z_ORDER_ENSURE_FAILED`. `CAPTION_BELOW_PANEL = ('caption', 'panel')` nomeia o contrato sem repetir literais `[CODE] app/webview/z_order.py:159`.
- **Quando falha** — Nenhuma chamada levanta para o chamador: `order_ok` apanha uma leitura que falhe e devolve `ok=True` com `Z_ORDER_READ_FAILED` (o Z é higiene, não pode derrubar um `show` nem o tique do vigia), `raise_panel` apanha a escrita e publica `Z_ORDER_RAISE_FAILED`, e um `SetWindowPos` que devolve falso publica `Z_ORDER_RAISE_REFUSED` em vez de contar como cura `[CODE] app/webview/z_order.py:112,139`. `ensure` só age quando `order_ok` disse que o painel está por baixo — a segunda chamada seguida escreve **zero**, que é o invariante que impede um `SetWindowPos` por tique para sempre (medido: `antes_ok=False agiu=True depois_ok=True 2a=False raised=1 calls=1`).
- **Evidência** — `[CODE] app/webview/z_order.py:43` (`should_raise`); `[CODE] app/webview/z_order.py:55` (`is_above`); `[CODE] app/webview/z_order.py:128` (`ensure`); `[CODE] app/webview/sotto_webview.py:7486` (`insert_below`, o único `SetWindowPos` desta cura); `[CODE] app/webview/topmost_keepalive.py:115` (`TOPMOST_EXTRA_FAILED`, o ramo que impede o `extra` de matar o tique). Portão `_main/z-order-oracle.py`: 16 arms, `A15`/`A16` criam duas janelas REAIS fora do écran virtual e medem o Win32 em vez de acreditarem no nome da API; `--neg-arm` 5/5.

---

# O WORKER (`worker/`)

# Catálogo de módulos — worker do ASR

Um bloco por módulo. Cada facto abaixo foi lido no ficheiro citado; quando o
módulo não está no caminho de produção, a evidência do grep está no próprio
bloco.

## `worker/audio_queue_consumer.py`

- **O que faz** — Consome a fila que o `audio_recorder` escreve (`index.jsonl` +
  FLAC) e transcreve cada segmento com o Parakeet Redux ONNX, via
  `redux_live.OnnxBackend`. Entrega o texto ao próprio `AudioRecorder`, que apaga
  o áudio e grava `results.jsonl`; o consumidor não apaga nada por si. Antes de
  carregar o modelo recusa qualquer caminho que contenha `sotto_worker` ou
  `nemotron`, e exige `parakeet-redux` no caminho.
- **Quem o chama** — `main()` (CLI `--once` / `--watch`) e, nos testes,
  `_main/audio-retention-e2e.py:35` (`import audio_queue_consumer as consumer`).
  **Nenhum ficheiro do produto o spawna**: grep por `audio_queue_consumer` em
  `*.js`/`*.py`/`*.cmd` não devolve nenhuma chamada fora de docs, testes e do
  próprio módulo — não está no caminho de produção.
- **O que escreve/lê** — Lê `index.jsonl` e `results.jsonl` do `queue_dir`, e os
  FLAC referenciados. Escreve indirectamente `results.jsonl` via
  `rec.mark_processed(...)`. Env: `SOTTO_AUDIO_DIR` é o default de `queue_dir`;
  `ONNX_DIR` é `worker/models/parakeet-redux-onnx-int4`.
- **Quando falha** — Caminho proibido: `SystemExit` com
  `audio-queue-consumer: REFUSED -- ...` antes de qualquer carregamento. Uma
  excepção a transcrever um segmento é apanhada e convertida em
  `state='error:<Tipo>'`, com log `audio-queue-consumer: FALHOU <file> -- <exc>`.
  No `watch`, uma falha de ciclo é apanhada e logada como
  `audio-queue-consumer: ciclo falhou -- ...`; o loop continua.
- **Evidência** — `[CODE] worker/audio_queue_consumer.py:62` (loop sobre
  `FORBIDDEN_MODEL_SUBSTRINGS`), `[CODE] worker/audio_queue_consumer.py:165`
  (except que produz `error:%s`), `[CODE] worker/audio_queue_consumer.py:171`
  (`rec.mark_processed(...)`).

## `worker/audio_recorder.py`

- **O que faz** — É a fila de áudio do caminho ao vivo: acumula blocos PCM 16 kHz
  mono, fecha segmentos por duração (`DEFAULT_SEGMENT_S = 60.0`), grava FLAC
  (`PCM_16`) e cai para WAV se o `soundfile` faltar ou falhar. Descarta silêncio
  digital e impõe um tecto de backlog (`DEFAULT_MAX_PENDING_BYTES = 512 MiB`),
  apagando o segmento não processado mais antigo quando o tecto é excedido.
  `mark_processed()` apaga o áudio em QUALQUER estado terminal (texto, vazio ou
  erro) e deixa o texto em `results.jsonl`.
- **Quem o chama** — `sotto_worker.py:8306`
  (`_audio_recorder.from_env(log=err)`), `sotto_worker.py:7945`
  (`recorder.accept(block)`) e `sotto_worker.py:8148` / `9122`
  (`recorder.close()`). `audio_queue_consumer.py:171` chama `mark_processed`.
- **O que escreve/lê** — Escreve `<prefixo>-<data>-<NNNN>.flac`, `index.jsonl` e
  `results.jsonl` em `outdir`. Env: `SOTTO_AUDIO_DIR` (o opt-in inteiro; sem ela
  `from_env` devolve `None`), `SOTTO_AUDIO_SEGMENT_S`,
  `SOTTO_AUDIO_MAX_PENDING_MB`. Tags: `AUDIO_RECORDER_FAILED`,
  `AUDIO_RECORDER_WRITE_FAILED`, `AUDIO_RECORDER_FLAC_FAILED`,
  `AUDIO_DELETE_FAILED`, `AUDIO_DELETED_AFTER_PROCESSING`,
  `AUDIO_DROPPED_OVER_CAP`, `AUDIO_RECORDER_CLOSED`.
- **Quando falha** — `accept()` nunca levanta: apanha tudo, loga
  `AUDIO_RECORDER_FAILED <Tipo>: <msg>` e faz `_flush(keep=False)` (descarta o
  buffer). Uma falha a gravar loga `AUDIO_RECORDER_WRITE_FAILED ... path=...` e
  não regista a linha no índice. Uma falha a apagar em `mark_processed` loga
  `AUDIO_DELETE_FAILED` e grava na mesma o resultado com `audio_deleted: False`.
- **Evidência** — `[CODE] worker/audio_recorder.py:102` (`def accept`),
  `[CODE] worker/audio_recorder.py:107` (log `AUDIO_RECORDER_FAILED`),
  `[CODE] worker/audio_recorder.py:316` (`SOTTO_AUDIO_DIR`).

## `worker/caption_noise.py`

- **O que faz** — Dois predicados sobre uma legenda INTEIRA: `is_noise_caption`
  (toda a legenda é `m`/`hm`/`mhm` com pontuação terminal) e
  `is_foreign_script_caption` (uma sequência de >= 2 letras fora do alfabeto
  latino). `admit_batch_caption(sw, text)` é o ponto único: devolve `False` e
  incrementa `sw.noise_lines` ou `sw.script_lines`, para que o log diga qual das
  duas regras removeu a janela.
- **Quem o chama** — `engine_policy.py:372` (`if not admit_batch_caption(sw,
  text): continue`) e `engine_switch.py:1634` (import local, mesmo guarda no
  caminho `_run_runner`). Ambos em produção.
- **O que escreve/lê** — Não abre ficheiros nem lê env. Escreve apenas os
  contadores `noise_lines` / `script_lines` no objecto switch; esses contadores
  saem na linha `REDUX_ENGINE_DONE ... noise_lines=... script_lines=...` de
  `engine_policy.py:391`.
- **Quando falha** — `admit_batch_caption` não tem ramo de erro próprio. No
  chamador de `engine_switch`, a chamada está dentro de `try` e uma excepção vira
  `REDUX_BATCH_NOISE_FILTER_FAILED reason=...`; em `engine_policy` a chamada não
  é protegida, logo uma excepção sobe e aborta o passe.
- **Evidência** — `[CODE] worker/caption_noise.py:90`
  (`sw.noise_lines = ... + 1`), `[CODE] worker/caption_noise.py:93`
  (`is_foreign_script_caption(text)`), `[CODE] worker/engine_policy.py:372`
  (chamada real).

## `worker/denoise.py`

- **O que faz** — Portão espectral causal e streaming (STFT frame 512 / hop 256,
  Hann periódica, piso de ruído por mínimo decrescente com compensação de viés
  `NOISE_BIAS = 3.79`), com ganho mínimo `MIN_GAIN_DB = -18.0`. `process(x)`
  devolve o mesmo comprimento e dtype, com 16 ms de latência e sem NaN.
  `denoise_decision(cfg)` lê a chave TOP-LEVEL `use_denoise` e recusa valores
  ambíguos como `refused(<valor>)`.
- **Quem o chama** — Ninguém no produto. Grep por
  `denoise|SpectralGate|denoise_from_config|use_denoise` em
  `worker/sotto_worker.py`, `worker/engine_*.py`, `worker/redux_*.py` e `app/`
  não devolve nenhum import nem chamada — **NÃO está no caminho de produção**, ao
  contrário do que o comentário `_comment_use_denoise` de `config.json` afirma
  ("ONE call site inside StreamAsr.run_chunk"). Os únicos pontos de entrada são
  `main()` (`--selftest`, `--wav`) e `measure_wav`.
- **O que escreve/lê** — Nenhum ficheiro por omissão; `--wav/--out` escreve um
  WAV de 16 kHz (`subtype="FLOAT"`). Lê o dict de configuração em memória; a
  chave enviada está em `worker/config.json:27` (`"use_denoise": false`).
- **Quando falha** — `denoise_decision` nunca levanta: devolve
  `(False, "refused(%r)")` para qualquer coisa que não seja booleano/string
  reconhecida. `SpectralGate.__init__` levanta `ValueError` para geometria
  inválida (`frame < 8`, `hop < 1`, `hop > frame`). `process` não levanta para
  entrada vazia (devolve cópia).
- **Evidência** — `[CODE] worker/denoise.py:305` (`def denoise_decision`),
  `[CODE] worker/denoise.py:605` (`if a.wav:`), `[CODE] worker/config.json:27`
  (`"use_denoise": false`).

## `worker/inspect_model.py`

- **O que faz** — É um script descartável de inspecção, não um módulo: no import
  executa logo `og.Model(...)` sobre um caminho absoluto hardcoded
  (`H:/sotto/worker/models/nemotron-3.5-asr-streaming-0.6b-int8`), percorre os
  atributos à procura de objectos tipo sessão e compara-os com sessões
  `onnxruntime` carregadas à mão. Só imprime; não expõe API.
- **Quem o chama** — Ninguém: `import inspect_model` não existe em nenhum
  ficheiro do repo. Só é mencionado em prosa (`app/webview/hot_reload.py:60`) e
  em notas de `_main/`. **Fora do caminho de produção.**
- **O que escreve/lê** — Lê `encoder.onnx`, `decoder.onnx`, `joint.onnx` e o
  modelo `onnxruntime-genai` no directório hardcoded. Escreve só stdout; nenhum
  ficheiro, nenhuma env var.
- **Quando falha** — Sem `try` à volta das linhas de topo: se
  `onnxruntime_genai` não estiver instalado, ou o directório do modelo não
  existir, o script morre com a excepção do import/carregamento antes de
  imprimir o cabeçalho. Os blocos internos de inspecção usam `except: pass`.
- **Evidência** — `[CODE] worker/inspect_model.py:6` (`model_dir = r'H:/sotto/...'`),
  `[CODE] worker/inspect_model.py:7` (`m = og.Model(model_dir)`),
  `[CODE] worker/inspect_model.py:16` (`def check_for_sessions`).

## `worker/lang_prompt.py`

- **O que faz** — Resolve o prompt de língua do ASR contra a tabela que o próprio
  modelo traz (`languages.json`, `promptDictionary` + `autoSlot`), com a
  precedência `--lang-id` > `SOTTO_LANG_ID` > `config.json` > sentinela `"os"`.
  Um id não declarado é REFUSED com `LangIdError` — nunca é clampado nem
  arredondado. Devolve um `Resolution` (`lang_id, tag, source, requested, table,
  note`) que vai para a linha de estado `state="lang"`.
- **Quem o chama** — `sotto_worker.py:1495` (`import lang_prompt`) via
  `_lang_prompt()`; chamadas reais em `sotto_worker.py:1581`
  (`resolve_lang_id(lang_id, model_dir, table=self.lang_table)`) e
  `sotto_worker.py:6965` (resolução no arranque). Produção.
- **O que escreve/lê** — Lê `languages.json` (no `model_dir`, num export irmão, ou
  em `docs/model-specs/original/fp16/languages.json`). Env: `SOTTO_LANG_ID`
  (`ENV_VAR`), lida pelo worker em `sotto_worker.py:6958`. Não escreve ficheiros;
  o CLI `--list` imprime a tabela.
- **Quando falha** — `load_language_table` levanta `LangIdError` se não encontrar
  nenhuma tabela; `resolve_lang_id` levanta `LangIdError` com a lista de slots
  declarados para um id/tag desconhecido. No arranque do worker a excepção é
  apanhada em `sotto_worker.py:6966`: emite `type="status", state="error",
  stage="lang-id"`, loga `FATAL lang-id: <msg>` e devolve código 2. Dentro de
  `StreamAsr.__init__` a excepção propaga (o comentário em `1581` diz
  "Raises lang_prompt.LangIdError — never clamps").
- **Evidência** — `[CODE] worker/lang_prompt.py:221` (`def resolve_lang_id`),
  `[CODE] worker/lang_prompt.py:55` (`ENV_VAR = "SOTTO_LANG_ID"`),
  `[CODE] worker/sotto_worker.py:6969` (`err(f"FATAL lang-id: {exc}")`).

## `worker/parakeet_ultra.py`

- **O que faz** — Instrumento de comparação do Parakeet Ultra
  (`parakeet-tdt-0.6b-v3` pós-treinado), com dois backends de API igual à do
  Redux (`transcribe(pcm) -> (text, segments)`): `onnx` (delega no
  `transcribe.py` do export, com um `_greedy_onnx` que corrige o loop de duração
  zero do export) e `torch` (checkpoint em `ParakeetForTDT`, fp16 em CUDA).
- **Quem o chama** — Só `ultra_export.verify()` (`ultra_export.py:365`) e o CLI.
  **NÃO está no caminho de produção** — o próprio docstring diz "NAO EMBARCA
  (medido 2026-11-08). Nada no produto importa este modulo"; o grep por
  `parakeet_ultra` em `worker/sotto_worker.py`, `engine_switch.py`,
  `engine_policy.py` e `redux_batch.py` não devolve nada.
- **O que escreve/lê** — Não escreve ficheiros. Lê `encoder-model.onnx`,
  `preprocessor.onnx`, `ultra-config.json`, `ultra.safetensors`,
  `ultra-tokenizer.json`. Env: `SOTTO_ULTRA_ONNX_DIR`, `SOTTO_ULTRA_SRC_DIR`.
  Com `--json` imprime uma linha JSON (`engine`, `load_s`, `infer_s`, `audio_s`,
  `xrt`, `text`, `segments`).
- **Quando falha** — `OnnxBackend.__init__` levanta `SystemExit` com
  `parakeet_ultra: no ONNX build in <dir>` quando falta `encoder-model.onnx`.
  `TorchBackend` levanta `SystemExit` para checkpoint incompatível
  (`checkpoint does not match ParakeetForTDT`) e para buffers deixados em `meta`.
- **Evidência** — `[CODE] worker/parakeet_ultra.py:4` (`NAO EMBARCA ... Nada no
  produto importa este modulo`), `[CODE] worker/parakeet_ultra.py:223`
  (`class OnnxBackend`), `[CODE] worker/parakeet_ultra.py:304` (`raise
  SystemExit("parakeet_ultra: checkpoint does not match ParakeetForTDT ...`).

## `worker/punctuation_model.py`

- **O que faz** — Restaurador de pontuação opcional (sherpa-onnx
  `online-punct-en`, int8, CPU, 1 fio). Aplica uma guarda de língua obrigatória:
  só corre quando a tag começa por `en`; caso contrário `punctuate()` devolve o
  texto intacto. Depois do modelo, filtra as marcas: `?`/`!` a meio são
  removidos, `?`/`!` finais viram `.`, e uma vírgula final é apagada.
- **Quem o chama** — `sotto_worker.py:133` (import de topo), `1588`
  (`punctuation_model.set_lang(self.lang_tag)`), `5353`
  (`text = punctuation_model.punctuate(text)` na emissão de legenda), `7117-7118`
  (`supported_lang(...)` → `load()`) e `7136` (`punct_model=punctuation_model.log_line()`
  no status de boot). Produção.
- **O que escreve/lê** — Lê `worker/models/punct-en/model.int8.onnx` e
  `bpe.vocab`; env `SOTTO_PUNCT_MODEL` (`0` desliga). Não escreve ficheiros;
  produz a linha `PUNCT_MODEL active=... loaded=... reason=... lang=...` dentro do
  campo `punct_model` do evento de status.
- **Quando falha** — `punctuate` é sempre seguro: sem modelo, sem pacote, com
  língua errada ou com o motor a levantar, devolve a mesma string. `load()`
  devolve `None` e grava o motivo em `status()` (`disabled-by-env`,
  `model-absent`, `package-absent (...)`, `load-failed (...)`). O worker carrega
  no boot apenas se `supported_lang(current_lang())`.
- **Evidência** — `[CODE] worker/punctuation_model.py:218` (`def punctuate`),
  `[CODE] worker/punctuation_model.py:133` (guarda `== "en"`),
  `[CODE] worker/sotto_worker.py:5353` (chamada na legenda).

## `worker/punctuation_prosody.py`

- **O que faz** — Metade sem modelo da pontuação: `normalise(text, pauses)` usa a
  pausa medida (ms) depois de cada token para (1) apagar uma vírgula com pausa
  < `DROP_FLOOR_MS = 200.0`, (2) inserir `,` a partir de `CLAUSE_MIN_MS = 250.0`
  e `.` a partir de `SENTENCE_MIN_MS = 600.0`, e (3) fechar a última palavra se a
  pausa final for de frase. Funções puras, sem I/O nem estado.
- **Quem o chama** — Ninguém: `import punctuation_prosody` / `from
  punctuation_prosody` não existe em nenhum ficheiro. **NÃO está no caminho de
  produção.** `app/webview/prose_punct.py` reimplementa as mesmas constantes
  (cita `SENTENCE_MIN_MS` em comentário) em vez de importar o módulo.
- **O que escreve/lê** — Nada. Recebe `text` e `pauses` (números ou dicts com
  `ms`) e devolve a string; não toca em ficheiros nem em env.
- **Quando falha** — Entrada degenerada é identidade: texto vazio, `pauses`
  vazio/ausente, ou tipo não-lista devolvem o texto tal e qual; pausas `None`,
  NaN, negativas ou não numéricas são ignoradas. Nunca levanta.
- **Evidência** — `[CODE] worker/punctuation_prosody.py:109`
  (`def normalise(text, pauses)`), `[CODE] worker/punctuation_prosody.py:63`
  (`SENTENCE_MIN_MS = 600.0`), `[CODE] worker/punctuation_prosody.py:128`
  (`if not text or not pauses ...: return text` — o guarda de entrada degenerada).

## `worker/speaker_id.py`

- **O que faz** — Funções puras que decidem QUEM fala, por tempo: converte
  segmentos do diarizador em `Segment`, atribui a cada linha de legenda o speaker
  com maior sobreposição total (mínimo `0.30` s de fala), com desempate
  determinístico (maior trecho contínuo, início mais cedo, forma textual) e
  rótulos estáveis `speaker-1`, `speaker-2`, ... por primeira aparição.
  `attribute_from_payload` é o ponto único: acrescenta `speaker` e, quando há
  dono, muda a `source` para `.../voice:<label>`, aplicando `window_offset` para
  juntar o zero do worker ao zero do sidecar.
- **Quem o chama** — `speaker_bridge.py:43`
  (`from speaker_id import attribute_from_payload, summarize`), e o bridge é
  chamado em produção por `sotto_worker.py:5522-5535`
  (`speaker_bridge.apply_to_lines(...)`) e `7619-7620`
  (`speaker_bridge.PayloadCache()`), este último só com `--speakers`.
- **O que escreve/lê** — Nada: nem ficheiros, nem env, nem log. Recebe o payload
  já calculado por outro processo e devolve novos dicts (não muta as linhas).
- **Quando falha** — Nunca levanta por dados maus: `speaker_for_window` devolve
  `None` para janelas inválidas ou sem sobreposição suficiente;
  `segments_from_rows` descarta linhas sem `start`/`end` numéricos ou sem
  speaker; `attribute_from_payload(None, ...)` é pass-through que carimba
  `speaker: None` e mantém `base_source`.
- **Evidência** — `[CODE] worker/speaker_id.py:288`
  (`def attribute_from_payload`), `[CODE] worker/speaker_id.py:82`
  (`def speaker_for_window`), `[CODE] worker/speaker_bridge.py:43` (import).

## `worker/ultra_export.py`

- **O que faz** — Exporta um checkpoint Parakeet TDT para o ABI ONNX de três
  grafos que o `transcribe.py` do Redux já fala: `encoder-model.onnx`,
  `decoder_joint-model.onnx` e, se o checkpoint tiver `vad_head.*`,
  `vad-model.onnx`; consolida os pesos em sidecars `.onnx.data` e escreve
  `config.json`/`vocab.txt`. `--verify` compara os tokens do torch com os do
  export e imprime `PARITY ... identical=<bool>`.
- **Quem o chama** — CLI apenas; o único import é `ultra_export.py:365`
  (`import parakeet_ultra`) dentro de `verify`. **NÃO está no caminho de
  produção.**
- **O que escreve/lê** — Escreve em `--out`: os três grafos, `<grafo>.onnx.data`,
  `config.json`, `vocab.txt`, e copia `transcribe.py` + `preprocessor.onnx` do
  export de referência. Lê `ultra-config.json`, `ultra.safetensors`,
  `ultra-tokenizer.json`. Nenhuma env var.
- **Quando falha** — `SystemExit` para checkpoint que não corresponde a
  `ParakeetForTDT` (`missing=... unexpected=...`), para dtype não suportado e
  para tensores deixados por materializar (`unmaterialized tensors after load`).
  A exportação do grafo VAD é a única não fatal: imprime
  `vad-model.onnx NOT exported: <Tipo>: <msg>` e continua.
- **Evidência** — `[CODE] worker/ultra_export.py:86` (`raise SystemExit(` com
  `ckpt does not match`), `[CODE] worker/ultra_export.py:294`
  (`vad-model.onnx NOT exported`), `[CODE] worker/ultra_export.py:191`
  (`GRAPHS = (...)`).

## `worker/unified_asr.py`

- **O que faz** — Núcleo de streaming em chunks do
  `nvidia/nemotron-labs-unified-asr-0.6b` sobre NeMo, com quatro configurações de
  contexto (`lat160`, `lat320`, `lat560`, `lat1120`), decode RNNT greedy que
  transporta estado entre chunks e medição de WER (Levenshtein com normalização
  que preserva acentos). Imprime uma linha `UNIFIED_CHUNK` por chunk e
  `UNIFIED_SELFTEST`/`UNIFIED_ROW` nos modos CLI.
- **Quem o chama** — Só o CLI (`--selftest`, `--ladder`). não há `import
  unified_asr` em nenhum ficheiro do repo; **NÃO está no caminho de produção** e
  exige o venv isolado `I:/cc-tmp/nemo-venv`.
- **O que escreve/lê** — Lê o `.nemo` (`I:/cc-tmp/models-src/unified.nemo` por
  omissão) e WAVs; escreve `--rows-jsonl` (default `I:/cc-tmp/unified-rows.jsonl`,
  append por linha) e `--json-out`. Nenhuma env var.
- **Quando falha** — `UnifiedAsr.__init__` levanta `SystemExit` com
  `UNIFIED_UNAVAILABLE reason=no-nemo ...` quando o NeMo não está importável, e
  `reason=no-prompt-dictionary` / `reason=unsupported-lang lang=...` quando a
  língua não está na tabela. `--selftest` sem WAV imprime
  `UNIFIED_SELFTEST verdict=FAIL reason=missing-wav` e devolve 2.
- **Evidência** — `[CODE] worker/unified_asr.py:140` (`class UnifiedAsr`),
  `[CODE] worker/unified_asr.py:153` (`UNIFIED_UNAVAILABLE reason=no-nemo`),
  `[CODE] worker/unified_asr.py:314` (`UNIFIED_CHUNK cfg=%s ...`).

## `worker/unified_fixtures.py`

- **O que faz** — Gera o conjunto de fixtures pt-BR/en-US para a escada do
  Unified-ASR com as vozes SAPI instaladas (`Microsoft Maria Desktop`,
  `Microsoft Zira Desktop`), escrevendo em ficheiro via `SpFileStream` (nunca
  toca no endpoint de áudio). O texto autorado É a referência, e é gravado em
  `reference.json` já normalizado.
- **Quem o chama** — Só o CLI (`--out`, `--selftest`); nenhum `import
  unified_fixtures` existe no repo. **NÃO está no caminho de produção.**
- **O que escreve/lê** — Escreve `<out>/<id>.wav` (16 kHz mono `PCM_16`),
  `<out>/<id>.raw.wav` (temporário, apagado a seguir) e `<out>/reference.json`.
  Lê os WAVs de novo no `--selftest`. Nenhuma env var.
- **Quando falha** — `SystemExit("voice not installed: ...")` se a voz não
  existir na máquina; `--selftest` conta fixtures em falta ou com sr/canais
  errados, imprime `MISSING`/`FIXTURE ... BAD` e devolve 1. Um erro de SAPI sobe
  como excepção depois de `stream.Close()` no `finally`.
- **Evidência** — `[CODE] worker/unified_fixtures.py:67`
  (`raise SystemExit("voice not installed: %s"`), `[CODE] worker/unified_fixtures.py:128`
  (`reference.json`), `[CODE] worker/unified_fixtures.py:126`
  (`print("BUILT %s ...")`).

## `worker/vram_residency.py` e `worker/model_vram_pool.py` (APAGADOS, 2026-11-15)

- **Estado** — Os dois ficheiros **já não existem**. Saíram com o D-33, e a razão está medida, não
  suposta: o censo por `ast` sobre `app/`, `worker/` e `_main/` devolvia **duas** importações de
  `model_vram_pool` no repositório inteiro, uma delas a do oráculo que o guardava
  (`_main/vram-reuse-oracle.py`) e **nenhuma** de produto; e `vram_residency` tinha como único
  consumidor o próprio pool, numa linha de `import` que morreu com ele. O oráculo do primeiro estava congelado na
  dívida `REASON-MISSING preencher a mao` desde 2026-10-25, logo nunca corria na bateria.
- **O que se perdeu, e o que não** — Perdeu-se uma biblioteca de medição de VRAM intra-processo
  (NVML para totais de dispositivo e pids com contexto CUDA; PDH `GPU Process Memory` para
  dedicada/partilhada por processo; identidade de modelo por SHA-256 dos pesos, nunca pelo nome;
  detentores estrangeiros em dois níveis, `same-worker` e `size-plausible`). **Nada disso estava no
  caminho de produção**: a shell mede VRAM por `pynvml` directamente e o caminho real de uma carga
  é `worker/sotto_worker.py` → `StreamAsr`.
- **O contrato que continua verdadeiro** — A VRAM é **privada do processo que a alocou**; reutilizá-la
  entre processos exigiria `cudaIpcGetMemHandle` do dono. Um pool `get_or_load` por processo não
  poderia partilhar sessões ORT com outro processo, e é por isso que a cura certa para uma segunda
  cópia é **não carregar**, não partilhar.
- **Se um dia voltar a ser preciso** — `git show 7720efcba3^:worker/vram_residency.py` e
  `git show 7720efcba3^:worker/model_vram_pool.py` têm o código inteiro com a proveniência das duas
  fontes de medição (o cabeçalho do `vram_residency` explica por que `nvidia-smi` e
  `nvmlDeviceGetComputeRunningProcesses_v2` não servem nesta box). O instrumento que os substitui
  para a pergunta "quem ocupa a GPU agora" é `pynvml` dentro do `VramGuard` da shell.

## `worker/_probe/ (32 ficheiros)`

- **O que é** — Directório de rascunho: 32 scripts `*.py` (de 96 ficheiros na
  pasta, incluindo logs, JSON e um `README.md` que é a model card do
  `nemotron-3.5-asr-streaming-0.6b-onnx-int4` copiada do Hugging Face) usados para
  medições pontuais de boot, CPU, grafos ONNX, quantização e decode. Executam no
  import (código ao nível do módulo, ex.: um deles constrói `og.Model(MODEL_DIR)` no
  topo), com caminhos absolutos para `worker/assets` e `worker/models`.
- **Embarque** — Nenhum destes ficheiros embarca no produto:
  `worker/_probe/` está no `.gitignore` (linha 115), e nenhum módulo de
  `worker/` ou `app/` importa `_probe` (grep por `import _probe` / `from _probe`
  devolve zero). **NÃO está no caminho de produção.**
- **Como é invocado** — À mão, com o interpretador do sistema
  (`python worker/_probe/<script>.py`); não há runner nem entrada no `package.json`
  que os chame. Os 5 ficheiros que ainda aparecem em `git ls-files` são restos de
  um `git add -f` anterior, cobertos pela mesma regra de ignore.
- **Evidência** — `[CODE] .gitignore:115` (`worker/_probe/`), e o facto de o directório ser
  ignorado é a própria evidência: os 32 `.py` existem **só nesta máquina**. Nenhuma linha deles é
  citável num clone limpo, e por isso este bloco não cita nenhuma — descreve a pasta e o que ela
  faz, e diz que ela não embarca. Um `git add -f` de sondas de medição seria a mesma classe do
  `D-01` (evidência que o índice não reproduz), agora paga para um ficheiro que ninguém corre em
  produção.

---

# O PAINEL (`app/panel/`)

# Catálogo de módulos — o painel web (`app/panel/`)

Âmbito: a UI do painel (HTML/CSS/JS servidos ao WebView2). Cada bloco descreve o contrato do ficheiro — o que garante, quem o chama, o que toca e como falha — com a linha que o prova. Contagens feitas no disco nesta data: 45 temas (30 em `themes/themes.js`, 5 em `themes/panel-designs.js`, 10 em `themes/zipc-panels.js`) e 20 skins congeladas.

---

## `app/panel/button-contract.css`

- **O que faz** — Fixa a geometria de *todos* os controlos nas duas superfícies, com `!important` e escopo por superfície: a fila do painel é `position: fixed`, `top: calc(14px + (56px - 28px) / 2)`, `right: 14px`, `gap: 4px`, `z-index: 60`; cada icon-button 28×28; o theme-button 90 px; o header reserva `padding-right: 290px` para o ponto decorativo não ficar por baixo. A ordem de pintura é imposta por `order` sobre os ids (`#theme-button`=1 … `#hide-button`=6) e, na strip, 1..9 (`#strip-state`=9), com todas as etiquetas escondidas excepto a do `#strip-live-button`. Fecha ainda o furo dos diálogos fechados e põe a lista de temas em duas colunas sem scrollbar.
- **Quem o chama** — É uma folha: carregada por `panel.html` como `<link rel="stylesheet" href="button-contract.css" />`. O ficheiro diz de si mesmo que é o último (`button-contract.css:1`), mas no documento actual `panel-unified.css` é carregado **depois** dele (`panel.html:95`), logo «último» não é verdade no `panel.html` de hoje; o que continua verdade é que todas as regras são `!important` e sobrevivem a qualquer folha de tema.
- **O que escreve/lê** — Não escreve nada e não corre código. Lê do DOM apenas `html body[data-surface="panel"|"strip"]`, os ids `#theme-button`, `#theme-chevron`, `#font-smaller-button`, `#font-larger-button`, `#panel-pause-button`, `#hide-button`, `#strip-*`, e as classes `.panel__controls`, `.stripbar`, `.theme-dropdown__list`, `.theme-dropdown__option`, `.pause-dialog`, `.tune-dialog`. Sem logs, sem ficheiros, sem estado.
- **Quando falha** — Não tem ramo de erro: uma regra cujo nó não existe é inerte, sem aviso e sem log. O único caso que este ficheiro trata explicitamente é o diálogo fechado que o `panel.css` pintava (`display: grid` incondicional na strip) — e só cobre `.pause-dialog` e `.tune-dialog`; um terceiro `<dialog>` com a mesma regra voltaria a pintar-se.
- **Evidência** — `[CODE] app/panel/button-contract.css:50` (`position: fixed !important;`), `[CODE] app/panel/button-contract.css:65` (`top: calc(14px + (56px - 28px) / 2) !important;`), `[CODE] app/panel/button-contract.css:162` (`#theme-button { order: 1 !important; }`).

## `app/panel/caption-float.css`

- **O que faz** — As regras próprias da legenda flutuante, em três contratos: (1) visibilidade a partir do **próprio** estado `#caption-float[data-float="on"]` e um guarda duro que a esconde sobre o painel completo (`body[data-surface="panel"] #caption-float`); (2) nada pinta — a lista de descendentes (`stage`, `col`, `prev`, `line`, `credits`, `meter`, `meter-fill`) leva `background:none`, `border:0`, `box-shadow:none` e `backdrop-filter:none`, e o único corpo é a barra `__led`; (3) geometria sem painel (`top:auto; bottom:0; height:auto`). Define ainda os tokens da «exibição YouTube» (`--caption-size:36px`, outline 6 px, `text-wrap:balance`, `overflow-wrap:normal`, `hyphens:none`) e, sob `html[data-brand]`, lê os tokens `--brand-*` já em px para a legenda vestir o design seleccionado.
- **Quem o chama** — Carregada por `panel.html` e por `caption.html`; e o próprio módulo JS a injecta quando não a encontra (`caption-float.js:96`, `ensureStyles`).
- **O que escreve/lê** — Não escreve. Lê do documento os atributos `data-float`, `data-surface`, `data-caption-doc`, `data-brand` e as variáveis `--caption-face`, `--caption-size`, `--caption-weight`, `--caption-leading`, `--caption-outline`, `--caption-prev-size`, `--caption-prev-outline`, `--caption-scale`, `--brand-*`, `--accent-gradient`/`--accent-from`/`--accent-to`. Sem logs, sem ficheiros.
- **Quando falha** — Sem `[data-float="on"]` nada aparece (o `panel.css` deixa `#caption-float` em `display:none`) e, com `body[data-surface="panel"]`, o guarda vence mesmo que o JS peça `on`. Variáveis ausentes caem nos fallbacks declarados (ex.: `--brand-rule-w, 0px` remove a barra em vez de inventar uma). Não há erro possível — é declaração.
- **Evidência** — `[CODE] app/panel/caption-float.css:48` (`#caption-float[data-float="on"] {`), `[CODE] app/panel/caption-float.css:55` (`body[data-surface="panel"] #caption-float {`), `[CODE] app/panel/caption-float.css:101` (`#caption-float,` — início da lista que não pinta).

## `app/panel/caption-float.js`

- **O que faz** — A legenda flutuante como overlay **independente**: estado próprio (`on`, `show/hide/toggle/setFloat`), DOM próprio (constrói `#caption-float` com os cinco ids que os probes usam se o documento não os tiver), folha própria e feed próprio (`window.sotto.onCaption`) **apenas** quando não existe `.panel` no documento. Nunca pinta quando o shell já escreveu `data-caption-window` no `<html>`: aí a legenda é a janela nativa e esta é a cópia de página. Espelha `data-float` no host e no `documentElement` porque é daí que o shell lê a altura da strip.
- **Quem o chama** — `panel.js`: `syncCaptionFloat()` (o botão live chama `api.setFloat`) e os pontos de push de texto/nível — `[CODE] app/panel/panel.js:3490`, `[CODE] app/panel/panel.js:1712`, `[CODE] app/panel/panel.js:4382`. Expõe-se em `window.SottoCaptionFloat`.
- **O que escreve/lê** — Escreve: `data-float="on"|"off"` no host e em `document.documentElement`, `host.style.display`, `aria-hidden`, a classe `is-empty` na linha (com o texto `OUVINDO…`) e `is-on` no `led`/`meter`, `meterFill.style.transform = scaleX(...)`, `prev`/`credits` text, e um `<link data-sotto-caption-float="1">` para `caption-float.css`. Lê: `body[data-float]`, `body[data-surface]`, `documentElement[data-caption-window]`, a existência de `.panel`, e `window.sotto.onCaption`/`window.SottoCaptionSource.onCaption`. Não escreve ficheiros nem logs.
- **Quando falha** — Sem `document.body` não há `mount()` e `push()` sai em silêncio (`nodes()` devolve falso); sem `<head>` não injecta a folha; sem ponte `selfFeed()` devolve falso e a legenda fica sem texto (não lança); um `onCaption` que lança é apanhado e a subscrição fica a `null` (silêncio); e, por desenho, com `data-caption-window` presente o overlay nunca pinta — é o caso normal da app viva.
- **Evidência** — `[CODE] app/panel/caption-float.js:216` (`&& d0.documentElement.hasAttribute('data-caption-window')) {`), `[CODE] app/panel/caption-float.js:230` (`host.setAttribute('data-float', want ? 'on' : 'off');`), `[CODE] app/panel/caption-float.js:239` (`d.documentElement.setAttribute('data-float', ...)`).

## `app/panel/caption.html`

- **O que faz** — Página autónoma da legenda: `<html>` com `data-caption-window`, `data-caption-doc` e `data-float="on"`, página transparente, `#caption-float` fixo a `inset:0`. O script inline corta o texto à **cauda** que cabe em duas linhas (busca binária sobre palavras), mede a linha renderizada para encostar o ponto à esquerda do primeiro `rect`, e expõe `window.SottoCaption` (`set`, `neededHeight`, `credits`, `listening`).
- **Quem o chama** — No código vivo, **ninguém**: o shell define `CAPTION_HTML` e nunca o usa (`sotto_webview.py:116`, sem outra referência no ficheiro), e o `panel.html` regista que esta é a «dead caption document … not on the live path». Quem chama de facto a API são os oráculos/probes: `_main/_design-lane/caption-display-oracle.py:286-287` e `_main/_design-lane/capwin-probe.py:76-78`.
- **O que escreve/lê** — Escreve: `line.textContent`/`prev.textContent`/`prev.hidden`, `credits.textContent`/`hidden`, a classe `is-empty` na linha, `is-on` no `.caption-float__led`, e `led.style.left`/`top` com `!important`; publica `window.SottoCaption` e `window.SottoCaption_neededHeight`. Lê: os ids `caption-float-line`, `caption-float-prev`, `caption-float-credits`, `.caption-float__stage`, `document.fonts.ready`, e as fontes/variáveis da folha.
- **Quando falha** — Os quatro nós são apanhados **sem null-check** (`caption.html:127-130`), pelo que um documento sem estes ids lança na primeira chamada a `SottoCaption.set`; `captionPlaceDot()` devolve cedo e limpa `left` quando a linha não tem `firstChild`; `captionWatchFonts()` desiste sem `document.fonts`; `captionFitLines()` limpa o texto quando a entrada é vazia.
- **Evidência** — `[CODE] app/panel/caption.html:149` (`var CAPTION_MAX_LINES = 2;`), `[CODE] app/panel/caption.html:225` (`window.SottoCaption = {`), `[CODE] app/panel/caption.html:32` (`background: transparent !important; overflow: hidden !important;`).

## `app/panel/history-context-store.js`

- **O que faz** — O códec puro do token `ctx1=`: cinco campos com letras fixas (`a`=sourceApp, `s`=audioSource, `v`=viewingApp, `t`=viewingTitle, `u`=viewingUrl), percent-encode/decode byte-a-byte iguais aos do gémeo Python (`quote(value,safe='')` / `unquote(...,'replace')`), limites por campo (64/96/64/120/300), corpo máximo de 512 caracteres, e normalização de URL http(s) que remove query, fragmento e userinfo — com a excepção do id de vídeo do YouTube (`?v=`).
- **Quem o chama** — `history-store.js`, no `require` do topo: `[CODE] app/panel/history-store.js:27`. Este ficheiro **não** é exportado para `window` (só `module.exports`, linha 290), portanto não corre no painel; o `history-store.js` é, por sua vez, o gémeo Node do armazém Python, usado pelo `app/_legacy-electron/main.js:26` e pelos oráculos (`_main/_audit-history-dead.js:68`).
- **O que escreve/lê** — Não toca em ficheiros nem em DOM: é funções sobre strings. O formato que escreve/lê é o comentário de linha `<!-- … ctx1=<corpo> … -->`, extraído por `contextTokenIn` (regex ancorada ao início do comentário) — ver `[CODE] app/panel/history-context-store.js:283`. Constantes: `VERSION='ctx1'`, `MAX_TOKEN_CHARS=512`.
- **Quando falha** — `%` malformado fica literal (não apaga o campo); um carácter não-ASCII ao lado de um escape faz `percentDecode` lançar, e `decodeContext` apanha e **omite** o campo; letra desconhecida é ignorada; URL não-http(s) devolve `''`; um campo que não cabe no orçamento é truncado por code point e os seguintes são descartados. Sem logs.
- **Evidência** — `[CODE] app/panel/history-context-store.js:59` (`const VERSION = 'ctx1';`), `[CODE] app/panel/history-context-store.js:110` (`function percentDecode(value) {`), `[CODE] app/panel/history-context-store.js:290` (`module.exports = {`).

## `app/panel/history-gallery.js`

- **O que faz** — Agrupamento puro por dia e por hora (chaves em hora **local**, construídas a partir de `date`+`time` separados, nunca de uma string concatenada) e selecção por janela (`24h` e `1h`) terminando em `now`; devolve `{days, total, skipped}` e recusa entradas no futuro.
- **Quem o chama** — **Nada em `app/panel`**: `panel.html` não tem `<script src="history-gallery.js">` e nenhum ficheiro do painel referencia `SottoHistoryGallery`. O módulo exporta-se para `window` (linha 191) e para `module.exports` (linha 190) e é consumido pelo oráculo `_main/history-gallery-oracle.js` e pelo harness `_main/_audit-render/make-harness.py:37`. O próprio `panel.js` regista que a galeria foi removida do painel: «the markup, the counters, the pick state and the module that bucketed the entries» (`panel.js:2530-2534`).
- **O que escreve/lê** — Nada: sem DOM, sem ficheiros, sem logs, sem estado global mutável (`RANGES` é constante).
- **Quando falha** — Uma entrada cujo `date`/`time` não casa com os regex (ou produz `Invalid Date`) é **descartada e contada** em `skipped`, não cai em «hoje»; `inRange` devolve falso para `range` desconhecido e para `age < 0` (carimbo futuro); `select`/`pick` mantêm a ordem decrescente e devolvem `0` quando um dos carimbos é ilegível (não reordenam ao acaso).
- **Evidência** — `[CODE] app/panel/history-gallery.js:41` (`const RANGES = [`), `[CODE] app/panel/history-gallery.js:93` (`function buckets(entries) {`), `[CODE] app/panel/history-gallery.js:191` (`window.SottoHistoryGallery = SottoHistoryGallery;`).

## `app/panel/lazy-assets.js`

- **O que faz** — O loader de arranque (injectado pelo preload do shell *antes* de qualquer script da página) que adia cinco recursos até o tema precisar deles: `themes/cinematic.css`, `themes/panel-designs.css`, `skins/skins.js`, `skin-host.js` e `skin-layout.css`. A tabela `NEEDS` é um teste de prefixo ao id do tema. Antes de injetar cada `<link>`/`<script>`, **pede** ao shell os bytes reais (o gate responde 200 vazio a um URL não pedido) e só injecta na confirmação; o par de skin é carregado na ordem do contrato: `skins.js` → (load) → `skin-host.js` → (load) → `skin-layout.css`.
- **Quem o chama** — O shell, como preload: `[CODE] app/webview/sotto_webview.py:211` (`LAZY_LOADER_JS`) e o comentário de injecção em `sotto_webview.py:11329`. Expõe `window.SottoLazy` (`assets()`, `needs()`, `reload()`, `log()`) para probes.
- **O que escreve/lê** — Lê `localStorage['sotto.theme']`, `<html data-theme>` e `SottoThemeManifest.fallback` (por essa ordem, com `theme-1` no fim). Escreve elementos com `data-sotto-lazy="theme"` e `data-sotto-lazy="skin"`, chama `pywebview.api.dispatch(JSON.stringify({kind:'lazy-asset', payload:{url}}))` ou, em fallback, `window.sotto.dispatch('lazy-asset', {url})`, e regista `sotto-lazy: <kind> <detail>` por `console.debug`, além do array `LOG`.
- **Quando falha** — Sem `pywebview.api` nem `window.sotto` volta a tentar a cada 100 ms **sem limite** (`ask`, linha 173 e seguintes); só com o canal fire-and-forget espera 40 turnos de 50 ms (~2 s) e depois injeta mesmo assim; um `api.dispatch` que nunca resolve é desbloqueado por um `settle` de 1500 ms. Se os bytes nunca forem autorizados, o elemento é servido vazio: o painel fica no tema base sem skin, sem retry loop (declarado no cabeçalho do ficheiro).
- **Evidência** — `[CODE] app/panel/lazy-assets.js:73` (`var NEEDS = {`), `[CODE] app/panel/lazy-assets.js:80` (`'cine-': ['themes/cinematic.css', 'skins/skins.js', 'skin-host.js',`), `[CODE] app/panel/lazy-assets.js:102` (`window.console.debug('sotto-lazy: ' + kind + ' ' + detail);`).

## `app/panel/letter-swap.js`

- **O que faz** — Diff carácter-a-carácter (Myers guloso, prefixo/sufixo removidos, limite `MYERS_MAX_CELLS = 250000` e degradação **reportada**) que repinta uma linha só com as letras mudadas/inseridas, em spans com stagger. A animação só corre quando a linha que chega declara um produtor **diferente** do anterior (`producerSwap`) — revisões live→live trocam em silêncio. O estilo é uma única folha injectada com duas regras (opacity+transform), e `prefers-reduced-motion: reduce` desliga-a.
- **Quem o chama** — `panel.js`, ao substituir uma linha existente: `[CODE] app/panel/panel.js:1641` (`window.SottoLetterSwap.apply(body, null, text, {...})`). Expõe-se em `window.SottoLetterSwap` e `module.exports`.
- **O que escreve/lê** — Escreve: `<style id="sotto-letter-swap-styles">`, as classes `letter-swap--swapped` e `letter-swap__ch--new`, os atributos `data-swap-changed`, `data-swap-animated`, `data-anim-index`, e as custom properties `--ls-delay`/`--ls-dur`; guarda memória por elemento em `WeakMap` (`painted`, `pending`) e um `setTimeout` para `finish()`. Lê: `el.childNodes`, `el.textContent`, `matchMedia('(prefers-reduced-motion: reduce)')`. Sem ficheiros e sem logs.
- **Quando falha** — Se o elemento tem filhos que não são nossos (um `<mark>` de pesquisa), `hasForeignChild` detecta e o módulo **não reescreve**: devolve `skipped:true, textUnchanged:true`; sem elemento, troca só o texto; diff acima do limite devolve `degraded:true`; e todos os caminhos terminam com `replaceChildren` + stats no elemento, nunca com excepção.
- **Evidência** — `[CODE] app/panel/letter-swap.js:53` (`var MYERS_MAX_CELLS = 250000;`), `[CODE] app/panel/letter-swap.js:222` (`function producerSwap(pair) {`), `[CODE] app/panel/letter-swap.js:302` (ramo `skipped` com `textUnchanged: true`).

## `app/panel/skin-host.js`

- **O que faz** — Monta um design vendor **congelado** dentro de uma shadow root aberta em `#skin`: liga `skins/skin-shim.css` e o CSS compilado do zip, compõe `.skin` com os quatro fragmentos (`stage`, `col` com `panel`+`caption`, `chrome`), copia as variáveis `--*` do design para o wrapper **e para o `<body>`**, descobre os slots (palavra viva, caret, lista de histórico) e escreve neles o estado que o `panel.js` lhe empurra. Apaga a ficção do mockup (`silence`/`silenceChrome`: nomes, `6 SPEAKERS`, `94% CONF`, `39 wpm`, `Tonight · …`) e marca os controlos mortos para o shim os remover. Segue o tema **só** pelo atributo `data-theme` no `<html>`.
- **Quem o chama** — `follow()` arma um `MutationObserver` em `documentElement[data-theme]` e corre uma vez no arranque; o `panel.js` chama a API exposta: `live` (panel.js:1475), `line` (1716), `filterVia` (2488), `level` (4377), `status` (4632). O `brand-bridge.js` lê `skin.slots()` para medir a legenda nativa (`brand-bridge.js:383`). Carregado pelo `lazy-assets.js`, não pelo `panel.html`.
- **O que escreve/lê** — Escreve: shadow root de `#skin`; `document.body` `data-skin="1"` e `data-skin-theme="<id>"`; variáveis `--*` no `.skin` e no `<body>` (removidas no `unmount`); atributos `data-skin-lines`, `data-skin-line`, `data-skin-footer`, `data-skin-hide`, `data-skin-dead-text`, `data-skin-dead-row`, `data-skin-avatar`, `data-skin-time`; texto nos slots e `bars[i].style.height/opacity` no medidor. Lê: `window.SOTTO_SKINS` (manifesto zips/themes) e `window.SOTTO_SKIN_HTML` (fragmentos), ambos no parse (linhas 41-42), e `state.via`/`state.lines` vindos do painel.
- **Quando falha** — `mount(id)` devolve `false` sem entrada, sem fragmento ou sem shadow root e, nesse caso, `follow()` faz `unmount()` (limpa shadow, variáveis do `<body>` e os atributos `data-skin*`) em vez de deixar metade montada; `discover()` pode devolver refs parciais e cada `render*` sai cedo quando o slot não existe; o `innerHTML` do fragmento é vendor e não é validado. Sem logs próprios.
- **Evidência** — `[CODE] app/panel/skin-host.js:412` (`if (!frag) return false;`), `[CODE] app/panel/skin-host.js:528` (`document.body.setAttribute('data-skin', '1');`), `[CODE] app/panel/skin-host.js:969` (`if (mount(id)) return;` — o `unmount()` imediatamente a seguir é o ramo de falha).

## `app/panel/skin-layout.css`

- **O que faz** — O único ficheiro nosso que decide *onde* um skin se senta no nosso painel: esconde a nossa caixa de legendas e o chrome por direcção (`.captions`, `.chrome`), tenta esconder a coluna e o chrome do vendor (`.skin__col`, `.skin__chrome` — regras que, dentro da shadow root, nunca casam, como o próprio `skin-shim.css` regista; quem as esconde ali é a linha 104 do shim), mapeia a paleta do design (`--surface`, `--line`, `--text`, `--blur`) nos nossos tokens (`--bg-slab`, `--text-primary`, …), fixa uma app bar de 56 px e faz `#skin` começar **debaixo** dela (`top:56px; height:calc(100% - 56px)`), e mantém a linha de estado visível — incluindo `status--error` — porque é o único sítio onde a causa do worker aparece.
- **Quem o chama** — Injectada pelo `lazy-assets.js` (`[CODE] app/panel/lazy-assets.js:289`), só quando um tema `cine-*` precisa do par de skin; não está no `<head>` do `panel.html`.
- **O que escreve/lê** — Não escreve. Lê `body[data-skin]`, `body[data-skin-theme]` e `body[data-surface]`, e as variáveis que o `skin-host.js` põe no `<body>` (`--surface`, `--line`, `--text`, `--blur`, `--text-dim`, `--text-faint`). Todas as regras de composição estão presas a `[data-surface="panel"]`.
- **Quando falha** — Fora da superfície `panel` nada disto se aplica: na strip o `#skin` é escondido (`skin-layout.css:48`) e o slab mantém-se — a regra que antes não era surface-scoped produzia a strip branca que o cabeçalho documenta. Sem as variáveis do design, os fallbacks do ficheiro (`--surface:#0b0f14`, `--line:rgba(...)`, `--text:#e8eef2`) tomam conta. As regras por-design (11 «bar» + 5 «float» + 4 «sidebarHead») são neutralizadas de propósito pelo bloco do app bar único (linha 235).
- **Evidência** — `[CODE] app/panel/skin-layout.css:41` (`body[data-skin][data-surface="panel"] #skin {`), `[CODE] app/panel/skin-layout.css:69` (`body[data-skin][data-surface="panel"] .captions,`), `[CODE] app/panel/skin-layout.css:281` (`body[data-skin][data-surface="panel"] #skin {` — o bloco `top:56px`).

## `app/panel/stable-words.js`

- **O que faz** — O sinal de que a última palavra de um parcial está **provada**: guarda um booleano e responde a `wordsAreWhole(tailClosed, key)` — verdadeiro quando a linha fechou (`tailClosed`), quando o worker prometeu (`stable:true`) ou quando a fonte é o player (`key` começa por `external:`). Envolve o `ingest` do motor para registar `meta.stable` **antes** de o motor pintar. O estado começa falso: um evento sem a chave é tratado como «não provado».
- **Quem o chama** — `panel.js`: `StableWords.wrap(engine)` ao construir cada motor (`[CODE] app/panel/panel.js:1159`) e `StableWords.wordsAreWhole(tailClosed, key)` no render (`[CODE] app/panel/panel.js:1354`). Carregado antes do `panel.js` (`panel.html:1250`).
- **O que escreve/lê** — Escreve: `wordsStable` (módulo) e substitui `engine.ingest` por um wrapper que lê `meta.stable === true` (linha 67). Publica `window.StableWords` e `module.exports`. Sem ficheiros, sem logs, sem DOM.
- **Quando falha** — Qualquer valor que não seja `true` (chave ausente, string `"true"`, `1`) faz `set` gravar falso, e o painel segura a última palavra; não há erro nem aviso — só a decisão conservadora. Se o motor não tiver `ingest`, `wrap` lança imediatamente no `engine.ingest.bind`.
- **Evidência** — `[CODE] app/panel/stable-words.js:26` (`var wordsStable = false;`), `[CODE] app/panel/stable-words.js:54` (`wordsAreWhole: function (tailClosed, key) {`), `[CODE] app/panel/stable-words.js:67` (`api.set(meta && meta.stable === true);`).

## `app/panel/zip-overlay.css`

- **O que faz** — O idioma «Zip D/E»: pílula de estado da strip (`#strip-state` com `order:99`, `.stripbar__state` sem `flex:1`, borda a 0.38), slab escuro só com a legenda off, linha da legenda em serifa `1.45em`, ponto verde de 6 px, `border:0` e `box-shadow:none` no `.panel`/`.captions__body`, scrollbar escondida, página `html[data-caption-doc]` transparente, e o esconder da legenda de página quando existe janela própria (`html[data-caption-window]:not([data-caption-doc])`).
- **Quem o chama** — **Só `caption.html`** (`[CODE] app/panel/caption.html:24`); o `panel.html` deixou de a carregar de propósito (comentário em `panel.html:72-81`: «ZIP-OVERLAY.CSS IS RETIRED FROM THE PANEL»). Ou seja: no caminho vivo do painel é inerte; o seu único consumidor é a página de legenda morta.
- **O que escreve/lê** — Não escreve. Lê `body[data-surface]`, `body[data-float]`, `html[data-caption-doc]`, `html[data-caption-window]`, e `--font-serif`.
- **Quando falha** — As regras do «STEP 3» sobre `.captions__list` são **inertes por construção**: na strip `.captions` está `display:none` (o próprio ficheiro cita `panel.css:2855`), pelo que pintam propriedades de nós que não renderizam; e o passo 2 ficou limitado a `:not([data-float="on"])` porque a mesma janela é a barra e o overlay. Se fosse recarregada no painel, as suas regras `body[data-float="on"]` voltariam a apanhar o overlay do painel, pois o `panel.js` escreve `data-float` no `<body>` (`panel.js:3557`).
- **Evidência** — `[CODE] app/panel/zip-overlay.css:261` (`width: 6px !important;`), `[CODE] app/panel/zip-overlay.css:361` (`font-size: 1.45em !important;`), `[CODE] app/panel/zip-overlay.css:402` (`body .panel {` — o `border:0` que remove a moldura de todos os designs).

---

## app/panel/themes/*.css e *.js

- **O que é a camada de temas** — Doze ficheiros e uma pasta `backdrops/`: cinco direcções base (`app/panel/themes/theme-1.css`, `app/panel/themes/theme-2.css`, `app/panel/themes/theme-3.css`, `app/panel/themes/theme-4.css` e `app/panel/themes/theme-5.css`, cada uma scoped a `:root[data-theme='theme-N']`), o conjunto gerado `cinematic.css` (25 nomes distintos `data-theme='cine-*'`, contados por grep), os cinco painéis do 2.º zip em `panel-designs.css` (`pd-*`) e os dez painéis do 3.º zip em `zipc-panels.css` (`GlassCards`, `Hairline`, `Paper`, `Quotes`, `Ledger`, `Feed`, `Bubbles`, `Timeline`, `Chips`, `Gutter`), mais os três manifestos (`themes.js`, `panel-designs.js`, `zipc-panels.js`), `fonts.css` e os 27 `.jpg` de `backdrops/` (referenciados por 25 nomes distintos em `cinematic.css`). `fonts.css` declara 16 famílias em 70 `@font-face`, servidas por 70 `.woff2` de `app/panel/fonts/` (contados no disco em 2026-11-12: 70 `url()` e 71 ficheiros no directorio -- um `ibm-plex-mono-latin-700-normal.woff2` sem face).
- **Como o `panel.html` carrega** — `fonts.css` (linha 48), `theme-1..5.css` (60-64) e `zipc-panels.css` (71) são `<link>` do `<head>`; `cinematic.css` e `panel-designs.css` **não** estão no `<head>`: são pedidos em runtime pelo `lazy-assets.js` quando o tema activo tem o prefixo `cine-`/`pd-` (`[CODE] app/panel/lazy-assets.js:80`). Os manifestos são scripts síncronos antes do switcher (`app/panel/themes/themes.js` em `panel.html:1264`, `panel-designs.js` em 1269, `zipc-panels.js` em 1271), porque `fetch()` de `file://` é recusado — e cada fragmento faz `push` para `SottoThemeManifest.themes`; total contado: 30 + 5 + 10 = 45.
- **Como um tema é escolhido e persistido** — `theme-switcher.js` guarda a escolha em `localStorage['sotto.theme']` (`[CODE] app/panel/theme-switcher.js:42`, leitura em :64, escrita em :79). No arranque lê a store e aplica-a **antes** da primeira pintura (`[CODE] app/panel/theme-switcher.js:1099-1100`), com `'theme-1'` como fallback do manifesto (`app/panel/themes/themes.js:281`). A troca é **uma** escrita de atributo — `el.dataset.theme = theme.name` (linha 961) — seguida de `writeStore` (linha 962); nada é recarregado ou re-parseado. É esse atributo que o `lazy-assets.js` e o `skin-host.js` observam; um nome desconhecido é recusado e devolve o tema actual.

## `app/panel/themes/fonts.css`

- **O que faz** — As 70 faces (`@font-face`) das 16 famílias que os três zips de design pedem, em `latin` apenas (`U+0000-00FF` mais o bloco de pontuação tipográfica, `[CODE] app/panel/themes/fonts.css:29`) e todas com `font-display: swap` (primeira em `:27`, última em `:717`): um tema nunca declara uma face, só nomeia uma família em `--font-sans`/`--font-mono`. É **gerado** por `_main/_design-lane/build_fonts.py` (cabeçalho, `:4`) — editar à mão perde-se na próxima geração.
- **Quem o chama** — Um único `<link>` do `<head>` do painel, **antes** de qualquer folha de tema (`[CODE] app/panel/panel.html:48`), e é carregado uma vez para todos os 45 temas: uma `@font-face` não tem selector, não pinta nem declara cor, logo não pode colidir com um tema (`[CODE] app/panel/themes/fonts.css:7`).
- **O que escreve/lê** — Não escreve nada e não corre código. Lê 70 ficheiros de `app/panel/fonts/*.woff2`, somados no disco: **1 345 304 B = 1 313,8 KiB** para as faces referenciadas (medido 2026-11-12), o que confere com o número que o próprio ficheiro declara (`[CODE] app/panel/themes/fonts.css:15`).
- **Quando falha** — Um `.woff2` ausente **não** levanta nada: o browser cai para a família seguinte da pilha do tema, sem uma linha em log — a falha é silenciosa por construção. Duas dívidas medidas hoje: existe **um** ficheiro a mais no disco do que faces no CSS (`ibm-plex-mono-latin-700-normal.woff2`; 71 ficheiros contra 70 `url()`), peso morto de uma face; e o cabeçalho manda ler `fonts/LICENSE-NOTES.md` para as licenças (SIL OFL 1.1), ficheiro que **não existe** em `app/panel/fonts/` nem em `_main/_design-lane/`, logo a atribuição que as 16 licenças exigem não está embarcada.
- **Evidência** — `[CODE] app/panel/themes/fonts.css:4` (`GENERATED by ...build_fonts.py`), `[CODE] app/panel/themes/fonts.css:27` (`font-display: swap;`), `[CODE] app/panel/themes/fonts.css:29` (`unicode-range: U+0000-00FF,...`), `[CODE] app/panel/panel.html:48` (`<link rel="stylesheet" href="themes/fonts.css" />`).

## `app/panel/themes/panel-designs.css`

- **O que faz** — Os **cinco** painéis do 2.º zip como estrutura própria, não como recoloração: `pd-tele`, `pd-bcast`, `pd-mano`, `pd-cine`, `pd-instr`, cada um scoped a `:root[data-theme='pd-X']` (primeiro em `:43`). A regra do dono que o ficheiro obedece — *"quero que cada tema encontrado dentro dos .zip fique com o design IGUAL, e só muda a posição dos botões"* — aterra na última regra de cada desenho, a do cluster de controlos (`.panel__controls`, `:649` em `pd-tele`; `:2947` em `pd-cine`). **Gerado** por `_main/_design-lane/gen_themes.py` (cabeçalho, `:3`), com `--trace` a imprimir a linha do zip de onde cada valor saiu.
- **Quem o chama** — **Não** está no `<head>`. É adiada: o `lazy-assets.js` injecta-a quando o tema activo tem o prefixo `pd-` (`NEEDS['pd-'] = ['themes/panel-designs.css']`, `[CODE] app/panel/lazy-assets.js:84`), depois de o shell confirmar o pedido — o gate responde `200` vazio a um URL não pedido.
- **O que escreve/lê** — Não escreve. Lê `:root[data-theme]` (escrito pelo `theme-switcher.js`) e os tokens que o tema base deixou.
- **Quando falha** — Se o pedido ao shell nunca aterrar, o `<link>` recebe os `200` vazios e o painel pinta o tema base sem esta folha: a aparência degrada-se para um tema que existe, sem erro de consola. Não há retry automático — o `lazy-assets.js` declara que um fetch que se repete sozinho num esquema local é como um diagnóstico se torna um hang (`[CODE] app/panel/lazy-assets.js:60`).
- **Evidência** — `[CODE] app/panel/themes/panel-designs.css:649` (`:root[data-theme='pd-tele'] .panel__controls {`), `[CODE] app/panel/lazy-assets.js:84` (`'pd-': ['themes/panel-designs.css']`), `[CODE] app/panel/panel.html:1269` (`<script src="themes/panel-designs.js"></script>`).

## `app/panel/themes/panel-designs.js`

- **O que faz** — O **fragmento de manifesto** do 2.º zip: cinco entradas (`pd-tele`, `pd-bcast`, `pd-mano`, `pd-cine`, `pd-instr`) com `name`, `label`, `file`, `swatch`, `group: 'panel-designs'` e `groupLabel: 'Painéis (2.º zip)'` (`:33`). O `swatch` de cada entrada **é** o token de acento do desenho na folha irmã (`#E8574F` em `pd-tele`/`pd-bcast`/`pd-instr`, `#E0A63C` em `pd-mano`, `#F1ECE2` em `pd-cine`; o cabeçalho diz de que linha do zip cada um veio). Não é um tema: existe porque os cinco nomes **reutilizam** os cinco nomes do 1.º zip com outra implementação, e por isso vivem num conjunto separado — a ordem é `themes.js` → `panel-designs.js` → `zipc-panels.js`, nunca o mesmo ficheiro.
- **Quem o chama** — `<script>` síncrono do `panel.html` (`:1269`), **depois** de `themes.js` e **antes** de `zipc-panels.js` e do `theme-switcher.js`: `fetch()` de `file://` é recusado, logo um manifesto tem de ser um script e não um JSON pedido.
- **O que escreve/lê** — Lê `window.SottoThemeManifest` e faz `push` das cinco entradas em `manifest.themes` (`:70-74`), com a guarda `typeof manifest.themes.push !== 'function'` — um manifesto ausente devolve sem levantar. O consumidor lê `theme.group`/`theme.groupLabel` para o cabeçalho de grupo do dropdown (`[CODE] app/panel/theme-switcher.js:199`).
- **Quando falha** — Se o `themes.js` não tiver corrido, o ficheiro sai em silêncio e os cinco temas **não existem** no dropdown: não há erro, há 40 temas em vez de 45. E é gerado (`:3`), logo uma edição à mão aqui é apagada pela próxima corrida de `gen_themes.py`.
- **Evidência** — `[CODE] app/panel/themes/panel-designs.js:33` (`groupLabel: 'Painéis (2.º zip)'`), `[CODE] app/panel/themes/panel-designs.js:74` (`manifest.themes.push(fragment[i]);`), `[CODE] app/panel/panel.html:1269` (`<script src="themes/panel-designs.js"></script>`).

## `app/panel/themes/zipc-panels.css`

- **O que faz** — Os **dez** painéis do 3.º zip (`cinematic-transcription-app-designs (1).zip`) como estrutura: `GlassCards` (`:67`), `Hairline`, `Paper`, `Quotes`, `Ledger`, `Feed`, `Bubbles`, `Timeline`, `Chips`, `Gutter` (`:2200`), cada um scoped a `:root[data-theme='X']` e cada um a fechar no seu `.panel__controls` (o último, `Gutter`, em `:2436`). **Gerado** por `_main/_design-lane/gen_zipc.py --profile designs` (`:4-5`).
- **O defeito que fecha** — Os dez desenhos eram **um** esqueleto recolocado dez vezes: medido no ficheiro embarcado, todos declaravam os mesmos 18 selectores e os mesmos 24 membros de vírgula, e só oito declarações de layout/tipografia diferiam (`:11-17`). O controlo de fidelidade do gerador é um segundo perfil, `--profile legacy`, que reproduz o ficheiro anterior **byte a byte** (35 875 B, sha256 `9E32F9160C38B855…`, `:5-7`).
- **Quem o chama** — **No `<head>`**, ao contrário do 2.º zip: `<link rel="stylesheet" href="themes/zipc-panels.css" />` (`[CODE] app/panel/panel.html:71`), carregada para todos os temas porque cada desenho é scoped.
- **O que escreve/lê** — Não escreve. Constrói tudo do DOM que o painel já tem — gradientes (incluindo `repeating-`), `grid`, pseudo-elementos com `content`, raios, filtros, contadores e `order` — porque o documento do painel não está no âmbito de escrita desta camada e nenhum elemento novo é permitido (`:30-36`).
- **Quando falha** — Um `data-theme` que não seja um destes dez nomes não apanha regra nenhuma desta folha: o painel fica com o tema base, sem erro. E, por ser gerado, uma correcção escrita aqui desaparece na próxima geração.
- **Evidência** — `[CODE] app/panel/themes/zipc-panels.css:67` (`:root[data-theme='GlassCards'] {`), `[CODE] app/panel/themes/zipc-panels.css:2200` (`:root[data-theme='Gutter'] {`), `[CODE] app/panel/panel.html:71` (`<link rel="stylesheet" href="themes/zipc-panels.css" />`).

## `app/panel/themes/zipc-panels.js`

- **O que faz** — O **fragmento de manifesto** do 3.º zip: dez entradas (`GlassCards`, `Hairline`, `Paper`, `Quotes`, `Ledger`, `Feed`, `Bubbles`, `Timeline`, `Chips`, `Gutter`, esta em `:91`), `group: 'zipc-panels'`, `groupLabel: 'Painéis (3.º zip)'`, `file: 'themes/zipc-panels.css'` e o `swatch` de cada uma a ser o acento do próprio desenho.
- **Quem o chama** — `<script>` síncrono do `panel.html` (`:1271`), **depois** de `panel-designs.js` e antes do switcher — a ordem é o que garante que os três conjuntos não colidem num nome (`[CODE] app/panel/themes/zipc-panels.js:4`).
- **O que escreve/lê** — Lê `window.SottoThemeManifest` e faz `push` das dez entradas (`:100-101`), com a guarda `Array.isArray(manifest.themes)` — sem manifesto o ficheiro devolve sem levantar.
- **Quando falha** — Ausente o `themes.js` ou o `panel-designs.js`, os dez temas não aparecem e o dropdown fica com 35 em vez de 45, em silêncio. Gerado (`:2`), como os irmãos.
- **Evidência** — `[CODE] app/panel/themes/zipc-panels.js:91` (`name: 'Gutter',`), `[CODE] app/panel/themes/zipc-panels.js:101` (`manifest.themes.push(fragment[i]);`), `[CODE] app/panel/panel.html:1271` (`<script src="themes/zipc-panels.js"></script>`).

## app/panel/skins/cinematic-2/ (82 ficheiros de design: 80 templates + 2 folhas; 103 ficheiros no total)

- **O que é uma skin** — A marcação **congelada** de um design vendor: para cada um dos **20** designs (`index.json` → `designs`/`frozen`) há quatro fragmentos `‹design›.stage.html`, `‹design›.chrome.html`, `‹design›.panel.html` e `‹design›.caption.html` — 20 × 4 = **80** templates — mais o CSS compilado do zip (`app.css`, `app.raw.css`) e `index.json`; `img/` guarda 20 imagens. Total 103 ficheiros (80 HTML + 2 CSS + 1 JSON + 20 imagens). O `index.json` declara `"viewport": [380, 900]`, `"css": "app.css"` e `"complete": true`. O empacotador (`_main/_skin-owner/pack_skins.py`) publica-os em `skins/skins.js` como dois objectos: `window.SOTTO_SKINS` (20 entradas em `themes`, um `zips['cinematic-2']` com `brandFrom`/`brandTo`/`css`/`mute`/`mutePatterns`/`viewport` — 134 palavras e 12 padrões contados) e `window.SOTTO_SKIN_HTML` (20 chaves `"cinematic-2/<design>"`, cada uma com `caption`/`chrome`/`panel`/`stage`).
- **Quem as monta** — `skin-host.js`, nunca o `panel.html`: `mount(id)` resolve `entryFor(id)` → `fragmentsFor()` e compõe o `innerHTML` com os quatro fragmentos (`[CODE] app/panel/skin-host.js:438-445`). O `id` é o `data-theme` do `<html>`; `has(id)` exige entrada **e** fragmento. A selecção é, por isso, a mesma de qualquer tema (localStorage/atributo) — não há segundo mecanismo.
- **O que o runtime garante** — Quatro garantias lidas do código: (1) a montagem é tudo-ou-nada — sem entrada, sem fragmento ou sem shadow root devolve `false` e o `follow()` chama `unmount()` (`skin-host.js:412`, `:969-970`), limpezas incluídas (`data-skin`/`data-skin-theme` e as `--*` do `<body>` são removidas, `skin-host.js:549`); (2) o `panel.js` nunca é chamado de dentro do host — o contrato é unidireccional e as chamadas são guardadas por `SottoSkin.active`; (3) as variáveis do design são copiadas para o `<body>` para que os nossos botões/estado vistam a paleta; (4) no estado **actual** do shim, as quatro camadas vendor **não pintam**: `app/panel/skins/skin-shim.css` faz `display:none !important` em `.skin__stage`, `.skin__chrome`, `.skin__scrim` e `.skin__col` (que contém `panel` e `caption`) — ver `[CODE] app/panel/skins/skin-shim.css:104`. O que o skin entrega ao ecrã é, por conseguinte, a paleta via variáveis e os seletores de `skin-layout.css`; o que o utilizador vê com cada design é `[UNKNOWN] — precisa de página renderizada`.

## app/panel/skins/ (o resto)

- **O que é** — Dois ficheiros além da pasta `cinematic-2/`: `skins.js` (812 978 B, gerado por `pack_skins.py`, com o comentário de topo «GENERATED … do not hand-edit») e `skin-shim.css` (11 430 B). O `skins.js` é o **único** produtor de `window.SOTTO_SKINS` e `window.SOTTO_SKIN_HTML` — é um script, não JSON, pela mesma razão dos manifestos de tema. O `skin-shim.css` é a folha que o vendor carrega **dentro** da shadow root: repõe o que uma shadow tree perde (`:host` no lugar de `html,body,#root`, `box-sizing`), fixa a composição e remove os controlos mortos/marketing do mockup por atributos que o `skin-host.js` marca (`[data-skin-footer]`, `[data-skin-hide]`, `[data-skin-dead-row]`, `[data-skin-dead-text]`).
- **Quem o usa** — O `skin-host.js` liga as duas por `<link>`/manifesto em `mount()`: primeiro `skins/skin-shim.css`, depois o `zip.css` do manifesto (`[CODE] app/panel/skin-host.js:421-422`); o `skins.js` é injectado pelo `lazy-assets.js` (`[CODE] app/panel/lazy-assets.js:276`). Nada em `app/panel` referencia estes ficheiros sem ser por esse caminho.
- **Quando falha** — Sem `skins.js` carregado, `window.SOTTO_SKINS` é `null`, `has()` devolve falso para todos os ids e nenhuma skin monta — o painel fica no tema, sem erro visível (é o modo degradado documentado no `lazy-assets.js`). O `skin-shim.css` mantém regras de um estado vazio que o host já não escreve (`[data-skin-empty]` em `app/panel/skins/skin-shim.css:237` e `:248`) — CSS inerte, não um comportamento.

## Lacunas

O que este catalogo NAO prova, e que ninguem deve ler como provado:

- **Que a linha citada diga o que a frase diz.** O portao resolve a citacao; a leitura e' humana
  (ou de outro modelo), e o `STATUS.md` ja' registou duas frases que passaram o portao e estavam
  erradas.
- **O comportamento SOB a app viva.** Cada seccao descreve o contrato do codigo. Se o processo do
  dono corre codigo anterior (`live-code-freshness-oracle` = STALE), nada disto foi observado a
  correr: `[MEASURED]` so' aparece quando existe uma linha de log ou um comando deste mes.
- **O que o olho ve.** As seccoes de CSS e de JS do painel descrevem o que o ficheiro PINa. Uma
  afirmacao sobre o pixel exige pagina renderizada, e o instrumento que a mede
  (`_main/panel-themes-oracle.mjs`, `_main/panel-header-oracle.js`) mede a composicao, nao o gosto.
- **As classes.** As 84 imagens de skin e as 32 sondas estao descritas COMO CLASSE: um ficheiro
  novo dentro delas nao aparece aqui por nome, e o portao aceita-o pela classe. Isso e' deliberado e
  esta' escrito no codigo do portao, nao aqui.
