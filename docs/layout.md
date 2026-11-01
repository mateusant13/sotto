# Layout do repo

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.


| path | o que é |
|---|---|
| `app/webview/run.cmd` | **A APP.** Arranca escondida, **arranca o WORKER**, espera Alt+C. `--no-worker` = só shell, `--show` = painel já, `--with-worker` = alias. `%*` passa intacto; a pré-flight `--check-args` recusa flags inválidas com rc≠0 sem lançar nada. |
| `app/webview/sotto_webview.py` | o shell: WebView2 + pywebview. Auto-start do worker decidido por `_worker_autostart_reason` (5 razões; só `default` arranca). |
| `worker/sotto_worker.py` | captura → chunk → encode → RNNT greedy decode → JSONL no stdout. |
| `worker/config.json` | fonte do `model.dir`, `lang_id`, `use_vad`, providers (todas lidas). |
| `worker/models/` | pesos (git-ignored, só em `H:\sotto`). |
| `app/panel/` | **O PAINEL** (`panel.{html,css,js}` + módulos carregados pelo documento). CSS de temas é **GERADO** — nunca editar à mão. |
| `app/webview/hot_reload.py` | watcher de assets do painel/worker com debounce; recarrega o painel em sítio. |
| `app/_legacy-electron/` | **MORTO.** Não é fallback. |
| `docs/model-specs/` | docs do próprio modelo, verbatim + índice normativo. |
| `_main/` | sondas, oráculos e logs. |
| `docs/shell-contract.md` | contrato do shell (strip, SetWindowPos, hot reload, meter). |
| `docs/AGENTS-archive-20261021.md` | o histórico completo deste ficheiro. |

**PIN do `run.cmd --help` (medido 2026-10-21 01:5x):** re-measured 2026-10-21 the output is 6934 B,
107 lines, 107 CRLF / 0 bare LF, rc 0, sha256
`51B52939F76C4AA5A35D7D865ED7C6B38C01ACFAD829F36C7A6032C337E01B47`. O portão do pin é
`_main/agents-md-pins-oracle.py`: se o `--help` mudar, este número muda, e o gate obriga a re-medir **aqui**.
(O número vai **sem asteriscos**: o braço negativo do portão muta o número com um padrão que exige
`the output is ` seguido dos dígitos — com o `**` do markdown o padrão não pega e o portão perde o
seu braço negativo.)
