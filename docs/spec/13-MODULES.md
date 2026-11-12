# 13 - CATALOGO DE MODULOS: cada ficheiro de produto, em palavras

Este documento responde a pergunta que os outros treze deixavam em aberto. eles descrevem
JORNADAS (o que acontece quando o dono aperta uma tecla), e uma jornada atravessa dez modulos sem
os nomear. Aqui a populacao e' a outra: **cada ficheiro de produto tem uma seccao**, com o que ele
garante, quem o chama, o que escreve e o que o utilizador ve quando ele falha.

A regra de prova e' a mesma do resto do directorio: uma frase sem etiqueta nao conta. Cada modulo
traz `[CODE] ficheiro:linha` -- resolvida pelo `_main/spec-citations-oracle.py` -- e, quando a
frase descreve um numero medido, `[MEASURED]` com o comando ou a linha de log.

## A populacao, medida

Medido com o proprio portao (`python _main/spec-coverage-oracle.py`) em 2026-11-12: **115 modulos de produto** nas tres raizes (`app/webview`, `worker`, `app/panel`), mais as classes que sao DADOS e nao comportamento, cada uma descrita uma vez: **84 imagens de skin** em `app/panel/skins/` e **32 sondas** em `worker/_probe/`. Fora da populacao, com razao declarada no portao: `worker/_prefix_audioflag.py` e `worker/_sotto_worker_agcinert.py` (copias congeladas usadas como mutantes) e `worker/runs/` (o mesmo).

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

## `app/webview/bridge_census.py`

- **O que faz** — O censo da ponte, activo só com `SOTTO_BRIDGE_CENSUS` ligado: devolve o objecto que o `_main/bridge-census.py` constrói em `attach(log)`, ou `None` quando o interruptor está desligado. Existe para responder ONDE o tempo foi quando um `exec_js` não responde — `sys._current_frames()` em vez de `py-spy`. `task_bits()` traduz o estado .NET da chamada em `{'status', 'continuation'}`, separando "o JS respondeu e o Python nunca foi chamado" de "o renderer nunca devolveu nada". O resultado é memoizado em `_BRIDGE_CENSUS`, e o contrato é NUNCA LANÇAR.
- **Quem o chama** — O shell embrulha-o em `_bridge_census()` (`[CODE] app/webview/sotto_webview.py:751`) e `_task_bits()` (`[CODE] app/webview/sotto_webview.py:755`); o consumidor é o `_run` do caminho `exec_js`, que faz `census = _bridge_census()` e `census.no_answer(token, _task_bits(box, done))` (`[CODE] app/webview/sotto_webview.py:14877`).
- **O que escreve/lê** — Lê a env var `SOTTO_BRIDGE_CENSUS` (aceita `1`/`true`/`yes`/`on`) e carrega `_main/bridge-census.py` por caminho (`spec_from_file_location('bridge_census', path)`). Não escreve ficheiros nem estado persistente; mantém apenas o global `_BRIDGE_CENSUS`. Loga `BRIDGE_CENSUS_ON path=... tick_ms=...` no sucesso e `BRIDGE_CENSUS_FAILED ...` no fracasso.
- **Quando falha** — Qualquer excepção ao carregar/executar o instrumento vira `warn('BRIDGE_CENSUS_FAILED ...')` e `_BRIDGE_CENSUS = None`: a shell arranca sem censo (`[CODE] app/webview/bridge_census.py:59`). Em `task_bits`, um `task` ilegível dá `status='unreadable'` e um evento ilegível dá `continuation='?'` (`[CODE] app/webview/bridge_census.py:86`); não há excepção que escape.
- **Evidência** — `[CODE] app/webview/bridge_census.py:46` (leitura da env var); `[CODE] app/webview/bridge_census.py:56` (tag `BRIDGE_CENSUS_ON`); `[CODE] app/webview/bridge_census.py:68` (`def task_bits`).

## `app/webview/caption_wrap.py`

- **O que faz** — Quebra uma legenda em no máximo `MAX_LINES` (2) linhas que caibam em `max_px`, numa costura natural (fim de frase, fim de oração ou antes de conjunção/preposição), e NUNCA parte, inventa, reordena ou perde palavras: o que não cabe volta como `overflow`. `wrap_tail()` devolve as ÚLTIMAS duas linhas e o texto que rolou para fora. `budget_px()` calcula o tecto de uma linha como `min(68 % da área de trabalho, medida de REPRESENTATIVE[:42])`, com piso de 160 px.
- **Quem o chama** — `CaptionOverlay._wrap_fn` importa `caption_wrap as cw` e chama `cw.wrap(text, cur_w, budget, max_lines=cw.UNBOUNDED_LINES)` (`[CODE] app/webview/caption_overlay.py:1511`); `overlay_paint._measure_budget` chama `_cw.budget_px(...)` (`[CODE] app/webview/overlay_paint.py:599`); `overlay_paint._layout` chama `_cw.wrap_tail(...)` e `_cw.wrap(...)` (`[CODE] app/webview/overlay_paint.py:639`).
- **O que escreve/lê** — Nada: puro stdlib (`re`), sem I/O, sem env vars, sem estado de módulo, sem tags de log.
- **Quando falha** — O módulo não tem ramo de erro próprio: não apanha excepções do `measure` do chamador nem de `str(text)`. Entrada vazia devolve `([], '')`; `max_lines <= 0` devolve `([], texto)`. As garantias são aritméticas — `_greedy_end` dá a uma palavra mais larga que o orçamento a sua própria linha em vez de a cortar (`[CODE] app/webview/caption_wrap.py:305`).
- **Evidência** — `[CODE] app/webview/caption_wrap.py:55` (`MAX_LINES = 2`); `[CODE] app/webview/caption_wrap.py:78` (`CHAR_CEILING = 42`); `[CODE] app/webview/caption_wrap.py:403` (`budget_px`).

## `app/webview/capture_exclusion.py`

- **O que faz** — Esconde a janela da legenda de quem captura o ecrã sem a esconder do dono, chamando `SetWindowDisplayAffinity` uma vez por janela. A escada de modos é `WDA_EXCLUDEFROMCAPTURE` (0x11, só a partir da build 19041) → `WDA_MONITOR` (0x01) → nada; o modo devolvido é SEMPRE lido de volta do sistema, porque pedir 0x11 e ficar com 0x00 é uma falha e não um sucesso. `enabled()` é o interruptor, ligado por omissão.
- **Quem o chama** — `CaptionOverlay._create` importa o módulo e chama `capture_exclusion.apply(hwnd, want=capture_exclusion.enabled())`, logando depois `CAPTION_OVERLAY_CAPTURE` ou `CAPTION_OVERLAY_CAPTURE_FAILED` (`[CODE] app/webview/caption_overlay.py:697`).
- **O que escreve/lê** — Lê a env var `SOTTO_CAPTURE_EXCLUDE` (valor por omissão `'1'`; `0`/`false`/`off`/`no` desligam) e a build do Windows via `sys.getwindowsversion().build`. Não escreve ficheiros nem estado. As tags de log vivem no chamador, não aqui.
- **Quando falha** — Sem `hwnd` devolve `{'mode': 0, 'ok': False, 'why': 'sem hwnd'}`. Se ambos os degraus falharem, devolve `ok=False` com `why='SetWindowDisplayAffinity falhou (error=N)'` lido de `get_last_error` (`[CODE] app/webview/capture_exclusion.py:93`); o chamador envolve a chamada em `try` e uma excepção vira `CAPTION_OVERLAY_CAPTURE_FAILED` — a legenda nunca morre por isto.
- **Evidência** — `[CODE] app/webview/capture_exclusion.py:31` (`MIN_BUILD_EXCLUDE = 19041`); `[CODE] app/webview/capture_exclusion.py:63` (leitura de `SOTTO_CAPTURE_EXCLUDE`); `[CODE] app/webview/capture_exclusion.py:66` (`def apply`).

## `app/webview/code_identity.py`

- **O que faz** — Produz a etiqueta do código que ESTE processo carregou: `sha256=<12 hex> files=<n>` mais ` missing=...` quando algum ficheiro não pôde ser lido. `code_files()` é a única definição da lista — ficheiros explícitos (`_CODE_ID_FILES`), todos os `*.py` da pasta, os globs da página (`../panel/*.js`, `*.css`, `*.html`, `themes/*.css`) e `../../worker/*.py` — e é dela que o processo e o oráculo de frescura leem, para não medirem conjuntos diferentes.
- **Quem o chama** — O shell define `code_identity()` que delega no módulo (`[CODE] app/webview/sotto_webview.py:2514`), usa-o no `main()` para logar `SHELL_CODE_ID %s` (`[CODE] app/webview/sotto_webview.py:26500`) e re-exporta `_CODE_ID_FILES`, `_CODE_ID_GLOBS` e `code_files` para o `_main/live-code-freshness-oracle.py` ler daqui (`[CODE] app/webview/sotto_webview.py:2504`).
- **O que escreve/lê** — Só lê: abre cada ficheiro em binário e alimenta o `hashlib.sha256`. Não escreve ficheiros, env vars nem chaves de estado; não emite tags de log (a tag `SHELL_CODE_ID` é do shell).
- **Quando falha** — Um `OSError` num ficheiro não interrompe a etiqueta: o nome entra em `missing` e a string termina com ` missing=<lista>` (`[CODE] app/webview/code_identity.py:127`); a contagem é `len(names) - len(missing)`. Erros de glob também são apanhados e registados na mesma lista. Não há excepção levantada por leitura falhada.
- **Evidência** — `[CODE] app/webview/code_identity.py:37` (globs da página); `[CODE] app/webview/code_identity.py:42` (globs do worker); `[CODE] app/webview/code_identity.py:125` (formato da etiqueta).

## `app/webview/external_subs.py`

- **O que faz** — Lê as legendas que o próprio player já está a mostrar, pela árvore de acessibilidade (UI Automation), e devolve `[(source, [linha1, linha2])]` para o YouTube e o Stremio. O separador entre legenda e "chrome" do player é TEMPORAL e posicional: uma linha tem de se manter igual (ou crescer como prefixo de si mesma) por `_CONFIRM_POLLS` (2) polls, e uma linha confirmada que fica fora do centro por `_UNSHAPED_DROP_POLLS` (6) é apagada. `player_source()` decide a fonte com cache de 1 s; `find_player_window()` devolve o primeiro player VISÍVEL, testado por `_window_is_player` e não pelo título sozinho; `edit_values()` devolve todos os valores de controlos Edit.
- **Quem o chama** — `ExternalCaptionWatcher.run` chama `external_subs._uia()` (`[CODE] app/webview/sotto_webview.py:4051`); o mesmo watcher chama `external_subs.caption_lines(hwnd, uia, UIA)` em `_read_inner` (`[CODE] app/webview/sotto_webview.py:4603`), `external_subs.player_source` e `find_player_window` em `_target_window` (`[CODE] app/webview/sotto_webview.py:4718`), e `external_subs.edit_values` em `_youtube_video_id` (`[CODE] app/webview/sotto_webview.py:6580`).
- **O que escreve/lê** — Lê a árvore UIA do processo alvo (COM), a barra de endereço do Chromium e o nome do processo por `QueryFullProcessImageNameW`. Mantém dois estados de módulo, ambos só em memória: `_RUNS` (hwnd → linhas com streak/held, limitado a `_RUNS_MAX` = 32 janelas) e `_PLAYER_SOURCE_CACHE` (TTL `_PLAYER_SOURCE_TTL_S` = 1.0 s). Não escreve ficheiros nem env vars. Não emite tags de log: as linhas `EXTERNAL_CAPTIONS_*` são do shell, e o que este módulo imprime é o `--probe` (`POLL ...`, `PROBE ...`, `PROBE_ERROR`).
- **Quando falha** — Quase todos os leitores têm `except Exception` e devolvem o vazio (`_process_name` → `""`, `_window_title` → `""`, `_descendants` → `None`, `edit_values` → `[]`); `caption_lines` devolve `[]` quando não há player reconhecido, quando o rect é degenerado ou quando não há candidatos, e nesses casos chama `_reset(hwnd)` — uma janela que não é player nunca "reclama" as legendas. `_uia()` NÃO apanha: pode levantar do COM, e é o `try` do shell que produz `EXTERNAL_CAPTIONS_UNAVAILABLE` (`[CODE] app/webview/sotto_webview.py:4054`).
- **Evidência** — `[CODE] app/webview/external_subs.py:511` (o separador temporal `_stable`); `[CODE] app/webview/external_subs.py:725` (`player_source` e o TTL); `[CODE] app/webview/external_subs.py:818` (`caption_lines`).

## `app/webview/no_console.py`

- **O que faz** — É o par que esconde de facto a consola de um processo filho: devolve os kwargs de `subprocess.Popen` com `creationflags |= CREATE_NO_WINDOW` (0x08000000) MAIS um `STARTUPINFO` com `STARTF_USESHOWWINDOW` e `wShowWindow = 0` (SW_HIDE). `creationflags` sozinho não chega quando o pai não tem consola — e neste produto nenhum pai tem (`pythonw.exe`). Fora do Windows devolve só `creationflags` (o extra pedido), porque `startupinfo()` devolve `None`.
- **Quem o chama** — `SpeakerSidecar.start` (`[CODE] app/webview/sotto_webview.py:23145`), o spawn do worker (`[CODE] app/webview/sotto_webview.py:23910`), `reveal_in_folder` (`[CODE] app/webview/sotto_webview.py:16424`), `batch_queue` (`[CODE] app/webview/batch_queue.py:626`) e `shell_relaunch` (`[CODE] app/webview/shell_relaunch.py:280`).
- **O que escreve/lê** — Nada: não escreve ficheiros nem env vars, não lê estado, não emite log. A única leitura é `os.name` para decidir se o par é aplicável.
- **Quando falha** — Não tem ramo de erro. Em `os.name != 'nt'`, `startupinfo()` devolve `None` e `popen_kwargs()` devolve apenas `{'creationflags': flags}`; em Windows devolve também `'startupinfo'` (`[CODE] app/webview/no_console.py:58`). O consumidor (`_main/console-window-audit.py`, citado no cabeçalho) é quem recusa um spawn com `creationflags` sem este par.
- **Evidência** — `[CODE] app/webview/no_console.py:39` (`CREATE_NO_WINDOW = 0x08000000`); `[CODE] app/webview/no_console.py:44` (ramo não-Windows); `[CODE] app/webview/no_console.py:56` (OR dos flags).

## `app/webview/panel_focus.py`

- **O que faz** — É a política de primeiro plano do painel, e os únicos sítios do shell que chamam `SetForegroundWindow`. `pointer_lock_state()` lê o clip rect do cursor (`GetClipCursor` contra `SM_CXVIRTUALSCREEN`/`SM_CYVIRTUALSCREEN`, tolerância de 8 px) para saber se a app em primeiro plano tem o rato preso. `foreground_unlock()` só toma o primeiro plano quando há pointer lock (`SW_RESTORE` + `SW_SHOW` + `SetForegroundWindow`, com `AttachThreadInput` como segunda tentativa); com o cursor livre mapeia o painel com `SW_SHOWNOACTIVATE` e não rouba o foco. `set_topmost()` re-afirma `HWND_TOPMOST` sem mover, redimensionar nem activar.
- **Quem o chama** — O shell embrulha as três entradas: `set_topmost(hwnd)` (`[CODE] app/webview/sotto_webview.py:7275`, usada em `13615` e `16632`), `pointer_lock_state()` (`[CODE] app/webview/sotto_webview.py:7308`) e `foreground_unlock(hwnd)` (`[CODE] app/webview/sotto_webview.py:7313`, usada em `17119`/`17207`). `selftest_instrument.run_selftest` recebe `pointer_lock_state` por parâmetro e não importa daqui.
- **O que escreve/lê** — Não escreve ficheiros nem estado. Lê `GetClipCursor`, `GetCursorInfo`, `GetSystemMetrics` e `GetForegroundWindow`. Emite as tags `FOREGROUND_TAKEN` / `FOREGROUND_KEPT` (uma por show) e `PANEL_FOREGROUND_ATTACH` / `PANEL_FOREGROUND_ATTACH_FAILED` / `PANEL_FOREGROUND_UNLOCK_FAILED`. Importa `CURSORINFO` e `RECT` de `win32_types`.
- **Quando falha** — `foreground_unlock` nunca levanta: qualquer excepção vira `PANEL_FOREGROUND_UNLOCK_FAILED error=...`, `reason='failed'` no dict devolvido e o Alt+C segue (`[CODE] app/webview/panel_focus.py:212`). `pointer_lock_state` também não levanta: um probe falhado devolve `clipped=False` e `detail='clip-probe-failed=...'` (`[CODE] app/webview/panel_focus.py:109`) — errar para "não roubar o foco". `set_topmost` devolve o booleano do `SetWindowPos`.
- **Evidência** — `[CODE] app/webview/panel_focus.py:47` (`set_topmost`); `[CODE] app/webview/panel_focus.py:154` (`foreground_unlock`); `[CODE] app/webview/panel_focus.py:208` (tag `FOREGROUND_KEPT`).

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

## `app/webview/win32_types.py`

- **O que faz** — Declara as três estruturas Win32 puras do shell: `RECT`, `POINT` e `CURSORINFO`. São `ctypes.Structure` sem lógica, sem chamadas Win32 e sem dependências deste repo; `CURSORINFO.ptScreenPos` é um `POINT`, e é por isso que os três andam juntos. Saíram do shell por causa do tecto de classes do ratchet, sem mudar um byte do que o Windows vê.
- **Quem o chama** — `panel_focus` importa `CURSORINFO, RECT` (`[CODE] app/webview/panel_focus.py:23`); o shell importa `CURSORINFO, POINT, RECT` (`[CODE] app/webview/sotto_webview.py:105`) e re-exporta os mesmos nomes para `dock_strip`, `clamp_geometry`, `target_display`, `pointer_lock_state` e os `argtypes` de `GetClipCursor`.
- **O que escreve/lê** — Nada. Apenas `import ctypes` e `ctypes.wintypes as wt`; sem env vars, sem ficheiros, sem estado, sem log.
- **Quando falha** — Não tem ramo de erro: são declarações de tipo. Um campo mal declarado não falha aqui — falha como leitura errada no chamador, que é o risco que o cabeçalho nomeia ao manter os três no mesmo sítio.
- **Evidência** — `[CODE] app/webview/win32_types.py:23` (`class RECT`); `[CODE] app/webview/win32_types.py:28` (`class POINT`); `[CODE] app/webview/win32_types.py:32` (`class CURSORINFO`).

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

## `worker/vram_residency.py`

- **O que faz** — Mede, dentro do processo, quem ocupa VRAM: totais por dispositivo
  e pids com contexto CUDA via NVML, e memória dedicada/partilhada por processo
  via PDH (`GPU Process Memory`). Identifica um modelo pelo conjunto de ficheiros
  de pesos e respectivos SHA-256 (nunca pelo nome), e detecta detentores
  estrangeiros em dois níveis: `same-worker` (cmdline contém `sotto_worker.py`) e
  `size-plausible` (VRAM dedicada >= tamanho do modelo em disco).
- **Quem o chama** — `model_vram_pool.py:37` (`import vram_residency as _res`), e
  o pool usa `pdh_snapshot`, `per_process_vram`, `model_identity`,
  `find_foreign_holders` e `find_model_holders`. **Não está no caminho de
  produção**: `model_vram_pool` não é importado por `sotto_worker.py`,
  `engine_switch.py`, `engine_policy.py` nem `redux_batch.py` — só oráculos de
  `_main/` o usam.
- **O que escreve/lê** — Não escreve nada. Lê os pesos do `model_dir` (para
  hashing), contadores PDH/NVML e a tabela de processos. Nenhuma env var.
- **Quando falha** — `pdh_counter` levanta `RuntimeError` se `pywin32` não for
  importável ou se `CollectQueryData` nunca devolver dados; `device_totals`
  levanta `RuntimeError` sem `pynvml`. A camada de relatório engole isso em
  campos `device_error` / `err_<counter>` (via `residency_verdict`), em vez de
  propagar.
- **Evidência** — `[CODE] worker/vram_residency.py:78`
  (`raise RuntimeError("win32pdh ...")`), `[CODE] worker/vram_residency.py:143`
  (`raise RuntimeError("pynvml ...")`), `[CODE] worker/model_vram_pool.py:37`
  (import).

## `worker/_probe/ (32 ficheiros)`

- **O que é** — Directório de rascunho: 32 scripts `*.py` (de 96 ficheiros na
  pasta, incluindo logs, JSON e um `README.md` que é a model card do
  `nemotron-3.5-asr-streaming-0.6b-onnx-int4` copiada do Hugging Face) usados para
  medições pontuais de boot, CPU, grafos ONNX, quantização e decode. Executam no
  import (código ao nível do módulo, ex.: `worker/_probe/probe2.py:13` constrói
  `og.Model(MODEL_DIR)`), com caminhos absolutos para `worker/assets` e
  `worker/models`.
- **Embarque** — Nenhum destes ficheiros embarca no produto:
  `worker/_probe/` está no `.gitignore` (linha 115), e nenhum módulo de
  `worker/` ou `app/` importa `_probe` (grep por `import _probe` / `from _probe`
  devolve zero). **NÃO está no caminho de produção.**
- **Como é invocado** — À mão, com o interpretador do sistema
  (`python worker/_probe/<script>.py`); não há runner nem entrada no `package.json`
  que os chame. Os 5 ficheiros que ainda aparecem em `git ls-files` são restos de
  um `git add -f` anterior, cobertos pela mesma regra de ignore.
- **Evidência** — `[CODE] .gitignore:115` (`worker/_probe/`),
  `[CODE] worker/_probe/probe2.py:13` (`model = og.Model(MODEL_DIR)`),
  `[CODE] worker/_probe/diag.py:1` (docstring de diagnóstico de uma execução
  única).

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

- **O que é a camada de temas** — Doze ficheiros e uma pasta `backdrops/`: cinco direcções base (`app/panel/themes/theme-1.css`, `app/panel/themes/theme-2.css`, `app/panel/themes/theme-3.css`, `app/panel/themes/theme-4.css` e `app/panel/themes/theme-5.css`, cada uma scoped a `:root[data-theme='theme-N']`), o conjunto gerado `cinematic.css` (25 nomes distintos `data-theme='cine-*'`, contados por grep), os cinco painéis do 2.º zip em `panel-designs.css` (`pd-*`) e os dez painéis do 3.º zip em `zipc-panels.css` (`GlassCards`, `Hairline`, `Paper`, `Quotes`, `Ledger`, `Feed`, `Bubbles`, `Timeline`, `Chips`, `Gutter`), mais os três manifestos (`themes.js`, `panel-designs.js`, `zipc-panels.js`), `fonts.css` e os 27 `.jpg` de `backdrops/` (referenciados por 25 nomes distintos em `cinematic.css`). `fonts.css` declara 16 famílias em 71 `@font-face`, servidas por 71 `.woff2` em `app/panel/fonts/` (contados no disco).
- **Como o `panel.html` carrega** — `fonts.css` (linha 48), `theme-1..5.css` (60-64) e `zipc-panels.css` (71) são `<link>` do `<head>`; `cinematic.css` e `panel-designs.css` **não** estão no `<head>`: são pedidos em runtime pelo `lazy-assets.js` quando o tema activo tem o prefixo `cine-`/`pd-` (`[CODE] app/panel/lazy-assets.js:80`). Os manifestos são scripts síncronos antes do switcher (`app/panel/themes/themes.js` em `panel.html:1264`, `panel-designs.js` em 1269, `zipc-panels.js` em 1271), porque `fetch()` de `file://` é recusado — e cada fragmento faz `push` para `SottoThemeManifest.themes`; total contado: 30 + 5 + 10 = 45.
- **Como um tema é escolhido e persistido** — `theme-switcher.js` guarda a escolha em `localStorage['sotto.theme']` (`[CODE] app/panel/theme-switcher.js:42`, leitura em :64, escrita em :79). No arranque lê a store e aplica-a **antes** da primeira pintura (`[CODE] app/panel/theme-switcher.js:1099-1100`), com `'theme-1'` como fallback do manifesto (`app/panel/themes/themes.js:281`). A troca é **uma** escrita de atributo — `el.dataset.theme = theme.name` (linha 961) — seguida de `writeStore` (linha 962); nada é recarregado ou re-parseado. É esse atributo que o `lazy-assets.js` e o `skin-host.js` observam; um nome desconhecido é recusado e devolve o tema actual.

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
