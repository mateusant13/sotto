# Sotto — o que aterrou em 2026-11-04 (recibo de pouso)

Uma linha por defeito do dono, com **o instrumento** que o julga e o **numero medido**. Onde a
medicao depende da sessao dele, esta dito `UNMEASURED` e nao se afirma.

## Legenda ao vivo

| defeito (palavras dele) | o que mudou | instrumento | medido |
|---|---|---|---|
| "demora pra caralho mostrar" (`MUIIITO DEMORA`) | **33,5 s dos 48,4 s nao eram o modelo**: a primeira escolha de endpoint abria um `IAudioClient` por endpoint (3,8 s) para devolver um MORTO | `_main/first-capture-fast-oracle.py` (10 arms + 4/4 mutantes) | escolha pelo medidor vivo: **735 ms / 6 endpoints, sem abrir cliente**; morte por dispositivo **250 ms** (era 15 s); morto declarado em **2 s** com rotacao in-process (sem recarregar 1,9 GB). Resta ~9 s: 0,6 spawn + 5,8 modelo + 0,74 meter + 1,94 primeiro bloco. `UNMEASURED` no arranque DELE |
| legenda fora de sync (~1,5 s) | o relogio vem do audio; a linha fechada nao espera o lote | `caption-budget`, `sync` (drift_ms) | ver `receipt-20261104-sync-*`; o dente de serra do `queue_ms` medido as 12:14 (`cdp_age_ms` a cair de 7 120 s) |
| duplicacao no historico | dedup no choke point | `caption-dup-repro.py` | 79 iguais consecutivas medidas antes; a cura e' de TEXTO, o carry do predictor nao se desliga |
| a fonte do YouTube nao liga (`src='?'`) | a escolha de aba **decide** em vez de adiar | `_main/youtube-first-at-boot-oracle.py` (9 arms + 3/3) | medido no log dele as 12:15:15: `YOUTUBE_CDP_BOOT_ATTACH ok=false reason=ambiguous tabs=5 others=3` tres vezes seguidas. Agora: um a tocar vence, dois estaveis, nenhum a tocar nunca e' ambiguo (`sticky-last`) |
| texto de estado por cima da linha do player | o texto e' RETIDO enquanto o player fornece | o mesmo oraculo | `CAPTION_LOADING_TEXT_WITHHELD reason=player-track`; `CAPTION_PIPELINE_ORDER steps=cdp,watcher,worker` publicado; fallback UMA vez por episodio de silencio |

## Hotkey e paineis

| defeito | o que mudou | instrumento | medido |
|---|---|---|---|
| "control espaco nao ativa espaco em apps" | o caminho do toggle foi executado com um `user32` gravador | `gaming-hotkey-oracle.py` (56 arms, 4/4) | **0** APIs de primeiro plano, **0** APIs que comem teclas; `SetWindowPos` flags **83** (`SWP_NOACTIVATE`), `ShowWindow` 4/0, `on,off` na ordem. `Ctrl+Space register_ok=True` — a tecla esta' **livre**; `Alt+C`=1409 porque a instancia do dono a tem |
| "no jogo o hotkey nao funciona" | observador em `ABOVE_NORMAL` + a borda entregue `via=latched` | o mesmo | `HOTKEY_OBSERVER_PRIORITY ok=true priority=1` (lido de volta `before=0 after=1`); a volta perdida de **2719 ms** medida num braco entrega a pressao |
| deteccao de jogo | `app/webview/gaming_mode.py` portado do `!watcher` | o mesmo | tick **12,32 ms** (521 processos), 26,8 ms carregado, orcamento 50 ms; **um** `CreateToolhelp32Snapshot`, zero hooks, READ-ONLY provado por `ast` |
| o oraculo do jogo era FLAKY | o braco (g) julgava o PIOR relogio de parede: `worst=51,24 ms` e `56,72 ms` contra 50 ms, sem regressao | o proprio | depois: `read_names` contado + custo intrinseco contra o piso medido na mesma corrida; **20/20** em sequencia e **20/20** com 5 instancias. `--neg-arm` 4/4 |

## Carga, arranque e higiene

| item | o que mudou | instrumento | medido |
|---|---|---|---|
| "modelos carregados dependendo da carga, volta sozinho quando libera" | `load-shedding` (tabela + histerese) permanece DESARMADO por omissao | `load-shedding-oracle.py` | **215/215** arms verdes |
| arranque quente | motor fora da shell, `WARM_HELLO`, TTL de parque, release em 120 s com `muito-alta` | `warm-engine-oracle.py` (22 arms, 6/6) | anexo **p50 0,0 ms / p95 16 ms** em 20; `unknown` nunca carrega. **A tarefa NAO esta' registada** (`schtasks /query SottoWarmEngine` -> nao encontrada): o motor quente e' codigo + portao, nao um processo a correr na maquina dele. A1/A2/A3 UNMEASURED (precisam de shell com audio) |
| leak | `BRIDGE_RSS` uma vez por minuto, julgado pela FORMA da serie | `rss-trend-oracle.py` (4 arms) | serie viva de 12:16..12:19: **1769,6 -> 1773,8 -> 1774,2 -> 1774,2** com `blocks` a subir 1005 -> 5511: aquecimento que assenta, nao fuga |
| espaco em disco | 11 worktrees merged removidas | `git worktree list` | `H:` 29 G livres; sobram `WarmEngineImpl-2`, `YtFirstAtBoot`, `GamingHotkey` (as tres tem commit por mergear/re-mergear) |

## Portoes

- `_main/_audit-verify-all.cmd` = **218401 B / 2705 CRLF / 0 bare LF**,
  sha256 `4CD44B1C58EB7944EB24C2DB0BB53AE83D7B0F0BA2A0F6A99FE73B8C93350DB1`, re-medido as 13:09.
- `run.cmd --help` = **8544 B / 131 linhas / 131 CRLF / 0 bare LF**, rc 0,
  sha256 `6015D4A76D9C43DD9FA02559CCBC6CC76F0573E8ECBA177CF656FA58D6717DDE`.
- `agents-md-pins-oracle.py` PASS (2 pins).
- Quatro classes que a bateria nomeou depois dos merges, todas reparadas com a sua medicao:
  `exception-hygiene` (divida 42 -> 41, o endpoint que nao se descreve passa a ser NOMEADO),
  `code-health` (re-medido pelo codigo novo), `console-window-audit` (o motor quente largava um
  filho com `creationflags` e mais nada -> `STARTUPINFO`+`SW_HIDE`, 1 sitio -> 0),
  `red-as-expected-worker-churn` (o piso da saida limpa passou a ser aplicado em DOIS sitios e o
  mutante mudava so' o primeiro; agora muta os dois e o braco 1 cai: `armed_ms=1000 floor=20000`).
- Pre-commit suites: `suites_ok=true gate_ok=true`, 9 passed / 0 refused, exit 0.

## O que NAO esta' medido (e por isso nao se afirma)

1. **O arranque no ecra dele** com esta arvore: nenhuma lane abre a app na tela do dono. O numero
   que conta e' `SHELL_STARTUP_STAGE -> primeiro CAPTION_PAINT` no log da instancia dele, depois de
   reiniciar sobre este codigo.
2. **A janela quente a correr de verdade**: a tarefa nao esta' registada.
3. **O jogo a frente**: `GetAsyncKeyState` pode ser cegado por aquisicao exclusiva de DirectInput, e
   um overlay `WS_EX_NOACTIVATE` pode ficar por baixo do fullscreen exclusivo. So' o jogo dele diz.
4. **`youtube-sync-oracle`** esta' vermelho identicamente na base: pre-existente, nao deste trabalho.
