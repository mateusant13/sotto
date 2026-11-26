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

## Stores: raiz, produtor, tecto, retencao

Toda a pasta que uma ferramenta escreve e nunca le de volta para correccao e' um STORE, e um store sem
os quatro factos declarados e' um defeito, nao uma tarefa de arrumacao (`H:\pi-agent\AGENTS.md`). Os
numeros abaixo sao os que o CODIGO le -- o nome da constante e o ficheiro, nunca um numero de linha que
envelhece sozinho.

| store | raiz | produtor | tecto | retencao |
|---|---|---|---|---|
| transcricao | `history/<YYYY-MM-DD>/<HH>.md` | `app/webview/sotto_webview.py` `history_append` (twin `app/panel/history-store.js`, só de oráculos) | nenhum (só tempo) | `HISTORY_RETENTION_H` = 4320 h (180 d); `_history_prune` no primeiro append de cada hora |
| log vivo | `_main/webview-run.log` | `app/webview/sotto_webview.py` `_open_log` | `SOTTO_LOG_CAP_MB`, default 64 MB | cauda `SOTTO_LOG_KEEP_MB` = 16 MB; roda no arranque (`LOG_ROTATED`) |
| segmentos do ring | `history/audio/<dia>/` | `worker/audio_ring.py` (ffmpeg) | `SOTTO_AUDIO_RING_CAP_MB`, default `DEFAULT_CAP_MB` = 600 MB, o mais VELHO sai primeiro | `SOTTO_AUDIO_RING_HOURS` = 12 h; o segmento aberto nunca e' podado |
| journal de falhas | `history/audio/gaps.jsonl` | `worker/audio_ring.py` | `GAP_FILE_MAX_BYTES` = 512 KiB | ultimas `GAP_ROWS_KEEP` = 2000 linhas |
| indices do ring | `history/audio/index.jsonl` | `worker/audio_ring.py` (fim de cada segmento) | `INDEX_FILE_MAX_BYTES` = 512 KiB | ultimas `INDEX_ROWS_KEEP` = 2000 linhas |
| ancoras de linha | `history/audio/lines.jsonl` | `worker/audio_ring.py` `append_line_anchor` | `LINES_FILE_MAX_BYTES` = 1 MiB | ultimas `LINES_ROWS_KEEP` = 4000 linhas |

MEDIDO 2026-11-26: `history/` = 663 325 B em 55 ficheiros; `_main/webview-run.log` = 38 683 394 B (o
tecto roda no ARRANQUE, nao a meio de uma sessao longa). Os dois indices da raiz estavam FORA da poda
(`_prune` so' desce nas pastas de dia) -- dois ficheiros append-only sem tecto, corrigidos no mesmo dia
com `_trim_jsonl_file` e provados por `_main/audio-ring-journal-oracle.py`.

**PIN do `run.cmd --help` (medido 2026-10-21 01:5x):** re-measured 2026-10-21 the output is 6934 B,
107 lines, 107 CRLF / 0 bare LF, rc 0, sha256
`51B52939F76C4AA5A35D7D865ED7C6B38C01ACFAD829F36C7A6032C337E01B47`. O portão do pin é
`_main/agents-md-pins-oracle.py`: se o `--help` mudar, este número muda, e o gate obriga a re-medir **aqui**.
(O número vai **sem asteriscos**: o braço negativo do portão muta o número com um padrão que exige
`the output is ` seguido dos dígitos — com o `**` do markdown o padrão não pega e o portão perde o
seu braço negativo.)
