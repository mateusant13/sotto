# Splitting `app/webview/sotto_webview.py` — the only measured path to `architecture_coherence >= 90`

- **2026-11-27 · o plano nasce de uma medicao, nao de uma ideia.** `benchmarks/sliders.json` declara
  `architecture_coherence` 60 com alvo 90; `slider_scorecard.py report` (piso 90) conta-o como gap de 30.
  O ficheiro mede **28 655 linhas** e **623 declaracoes de topo** (contadas por `ast` a 2026-11-27), com
  tres classes a dominar: `SottoShell` **10 245 LOC** (`:13936-24180`), `ExternalCaptionWatcher`
  **3 645** (`:4299-7943`), `WorkerBridge` **1 784** (`:24981-26764`). Nenhuma fatia de 2 % move a nota;
  e' preciso cortar por dominio, e cada corte tem de ser provado por um oraculo que ja' existe.

## Regras do corte (cada uma custou uma sessao)

- **2026-11-27 · um corte por vez, com checkpoint antes.** `git_checkpoint.py snapshot --name pre-split-S<N>
  --bundle I:\cc-tmp\sotto-pre-split-S<N>.bundle` + `git bundle verify` antes da primeira linha movida.
- **2026-11-27 · o portao de cada fatia e' o oraculo do SEU dominio**, nao uma suite generica; mais
  `_main/undefined-names-oracle.py` (prova que nenhum nome ficou sem definicao depois de o simbolo sair do
  modulo), `_main/dead-unwired-oracle.py` (prova que o modulo novo tem chamador), `_main/battery-launch.py
  --verify` (prova que a bateria continua a apontar para instrumentos que existem).
- **2026-11-27 · o ficheiro NAO e' importavel como teste.** Ele tem 623 declaracoes de topo e corre codigo
  no import; um `python -c "import sotto_webview"` abriria caminho para a app na tela do dono. A prova de
  ligacao e' estatica (AST + o oraculo de nomes) e a prova viva e' o arranque do DONO, que uma lane nao
  faz — o recibo diz `fixed, NOT verified` ate' ele reiniciar.
- **2026-11-27 · enquanto o worker e a shell dele correm, um corte so' mexe em ficheiros**: nada de o
  reiniciar, nada de `--show`, nada de panes.

## Ordem das fatias (independentes, das mais baratas e mais provadas para as caras)

|fatia|simbolos (linhas a 2026-11-27)|destino|portao|
|---|---|---|---|
|S1|`MSG`, `MONITORINFO`, `dpi_scale`, `_shcore`, `_monitor_scale`, `_selection_monitor`, `_display_for_monitor`, `primary_display`, `select_display_for_point`, `_selection_monitors_and_primary`, `target_placement`, `target_display` (`:3406-3750`)|`app/webview/display_geometry.py`|`_main/multi-monitor-oracle.py` (6 arms)|
|S2|`parse_accelerator`, `hotkey_numbers`, `hotkey_config`, `HotkeyThread`, `LiveHotkeyThread`, `PassiveHotkeyThread` (`:8825-9677`)|`app/webview/hotkey_arms.py`|`_main/altc-gesture-oracle.py` (104), `_main/altc-soak-oracle.py`|
|S3|`NOTIFYICONDATAW`, `WNDCLASSEXW`, `TrayIcon`, `menu_items`, `raise_visible_priority`, `warn_hotkey_unavailable`, `arm_hotkey*` (`:10792-11697`)|`app/webview/tray_surface.py`|`_main/tray-menu-oracle.py` (27), `_main/panel-language-oracle.js`|
|S4|`set_layered_color_key` .. `dock_strip` (`:7952-8575`)|`app/webview/window_chrome.py`|`_main/topmost-keepalive-oracle.py` (10), `_main/overlay-ink-oracle.py`|
|S5|`_reap_child` .. `census_line`, `_open_log`/`_log_*` (`:1842-2715`)|`app/webview/process_lifecycle.py`|`_main/relaunch-ready-oracle.py` (8), `_main/console-window-audit.py`|
|S6|`SottoHost` + `PanelVisibilityWriter` (`:12828-13754`)|`app/webview/host_window.py`|`_main/panel-hidden-at-startup-oracle.py`, `_main/ui-watchdog-oracle.py`|
|S7|`ExternalCaptionWatcher` (`:4299-7943`) partido por testemunha: relogio / seek / leitura com orcamento|`app/webview/yt_clock.py`, `yt_read.py`, `yt_watch.py`|`_main/yt-capture-replay-oracle.py` (43 arms), `_main/yt-pause-disagreement-oracle.py`, `_main/yt-read-budget-oracle.py`|
|S8|`SottoShell` (`:13936-24180`) por dominio de metodo, na ordem que os oraculos ditam|`app/webview/shell_*.py`|a bateria inteira, um passo por fatia|

## Aceitacao de cada fatia, medida

- o oraculo do dominio verde **antes e depois** (o mesmo comando, a mesma arvore);
- `undefined-names` GREEN com a populacao a incluir o modulo novo;
- `dead-unwired` PASS (sem `new-unwired`);
- `_main/_gitattributes-verify.py` PASS (o ficheiro novo declara o seu dialecto: `app/webview/*.py` = CRLF);
- `codeintel health --budget-ms 10000` colado antes/depois, com o delta de `architecture_boundaries`;
- o recibo diz `fixed, NOT verified` ate' o dono reiniciar, excepto quando a fatia nao toca o arranque.

## O que este plano NAO resolve

- **2026-11-27 · `delivery_balance` fica fora.** O teto medido e' 78 (`landing_ratio_check.py:86` exige
  `AGENTS.md <= 250` linhas; o livro de regras tem 1 299 por dever de transporte). Nenhum corte de codigo
  mexe nisso: e' decisao do dono, nao trabalho de lane.
