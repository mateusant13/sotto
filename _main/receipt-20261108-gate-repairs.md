# RECIBO - a corrida de 2026-11-08 e os cinco portoes que ela derrubou

A corrida de `_main\_audit-verify-all.cmd` de **2026-11-08T08:5xZ** terminou
`BATTERY-VERDICT: RED - 17 step(s) failed`, `steps=371`. Este recibo trata as
dezessete, uma a uma, e separa as que eram MINHAS (o que eu quebrei hoje) das que
eram ancoras mortas (o que o produto deixou de ter) e das que eram instrumentos a
mentir sobre si proprios.

Commit: `fae12d7 bateria: cinco portoes vermelhos, e a razao de cada um`.

## 1. As dezessete, e onde cada uma aterrou

| # | passo | antes | causa | depois |
|---|---|---|---|---|
| 1 | `console-window-audit` | FAIL `1 sitio(s) que abrem janela` | `_main/paint-cost-oracle.py:150` largava `git` por `subprocess.run` cru; sob `pythonw` o filho herda consola NOVA | PASS `0 sitio(s)` |
| 2 | `exception-hygiene` | FAIL medido 42 contra baseline 41 | a +1 era a guarda do `log_fn` do timer do quadro (`caption_overlay.py:481-484`), que existe para o log nunca matar o relogio | PASS medido 42 = baseline 42 |
| 3 | `claims-date` | FAIL 5 afirmacoes sem data | quatro linhas da LEI DO CUSTO com numero e sem data NA LINHA (a data do cabecalho nao vale) | PASS 3 com licenca |
| 4 | `input-path` | FAIL 3 (2 mutantes nao construiveis) | `timer-sempre`/`hook-volta` ancoravam num `_tick` que ja' nao existe; `stop-nao-mata` na constante `_POLL_TIMER_ID` onde o codigo usa `self._timer_id` | PASS 9/9 mutantes apanhados |
| 5 | `seam-coverage` | FAIL (o `hook-volta` do `input-path` nao podia ser construido) | o mesmo de cima, lido por outro oraculo | PASS |
| 6 | `strip-surface-oracle` | RED `geometry_for.default: got (770, 840, 380, 148), expected (440, 840, 1040, 148)` | o pin do default era o de `e36a09b` (a laje 1040); o `02f6df9` desfez-no ("faixa de baixo: 380 outra vez") | PASS, 5/5 mutantes, 118 arms |
| 7 | `log-sink-dead` | rc=0 | o `neg_arm` devolvia `0 if apanhado else 1`, invertido contra a convencao da casa | rc=1 |
| 8 | `red-as-expected-log-sink-dead` | rc=0, frase ausente | o oraculo imprimia `NEG-ARM PASS` sem os dois pontos; o `:expectred` exige `NEG-ARM: PASS` | rc=1 + frase |
| 9 | `youtube-first-at-boot` neg | rc=0 | — | ver #10 |
| 10 | `red-as-expected-youtube-first-at-boot` | rc=0, frase ausente | o mutante 4 e' uma COPIA de `youtube_cdp_source`, que carrega `youtube_window` PELO CAMINHO (`_load_sibling`, :50); o irmao nao era copiado junto -> `FileNotFoundError: <tmp>\youtube_window.py` | rc=1 + `NEG-ARM: PASS (4/4)` |
| 11 | `red-as-expected-cdp-target-async` | rc=0 | log velho de uma corrida anterior a esta sessao | rc=1 + frase, medido |
| 12 | `red-as-expected-youtube-cdp-source` | rc=0 | idem | rc=1 + `NEG-ARM VERDICT: PASS` |
| 13 | `red-as-expected-input-path` | rc=101 | `--neg-arm` do `input-path` saia 101 enquanto os mutantes nao podiam ser construidos | rc=1 + `NEG-ARM PASS` |
| 14 | `red-as-expected-claims-date` | rc=0 | idem | rc=1 + `NEG-ARM PASS` |
| 15 | `skip-verdict-guard` | RED `1 undeclared skip verdict(s) in 404 step log(s)` (`shell-thread-budget.log`) | o oraculo le a shell VIVA e responde `VERDICT: SKIPPED` com a app fechada; declarado com `:record` esse skip honesto virava RED da CORRIDA | passo declarado `:skipped`; guarda GREEN `414 step log(s)` |
| 16 | `SHELL-THREAD-BUDGET` (o proprio) | SKIPPED `reason=no-live-shell` | nao era defeito: e' o desfecho normal com a app fechada | idem, agora contado em `skipped=` |
| 17 | `state-page` / `agents-md-pins` | pin do `.cmd` medido antes das curas | as curas mudaram o ficheiro | pin re-medido: 287904 B / 3480 CRLF / `87A169AE...8CF94D9F` |

## 2. As duas curas que nao sao "ajustar numero"

### 2.1 O `git` do `paint-cost` abre consola

`subprocess.run(['git', ...])` sem `creationflags`: com a bateria a largar os
passos por `pythonw` (sem consola propria) o Windows da' uma consola NOVA ao
filho. A cura passa pelo helper da casa (`_main/hidden-launch.py`, carregado por
`importlib` porque o nome tem hifen). Medido antes/depois com o censo AST:
`NO-FLAG 1 -> 0`, `CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela`
(2026-11-08, 13,1 s de censo).

### 2.2 Dois mutantes que nao podiam ser construidos

`build_mutant` recusa uma ancora que case 0 vezes -- e recusou. Um mutante que
nao pode ser construido e' um invariante SEM CONTROLO, e o portao ficava vermelho
com a razao certa. As ancoras foram movidas para o sitio de HOJE:

- `timer-sempre` -> a linha do `_restart_timer` que decide `want` pelo
  `_wants_poll()` (o mutante tira a guarda: o tick arranca sempre).
- `hook-volta` -> a mesma linha, com um `SetWindowsHookExW(14, ...)` plantado ao
  lado (o hook global de volta ao caminho vivo).
- `stop-nao-mata` -> `user32.KillTimer(None, self._timer_id or _POLL_TIMER_ID)`.

## 3. O que ficou medido depois das curas

| instrumento | veredicto | quando |
|---|---|---|
| `console-window-audit.py` | PASS, 0 sitio(s) | 2026-11-08 |
| `exception-hygiene-oracle.py` | PASS, medido 42 = baseline 42 | 2026-11-08 |
| `claims-date-oracle.py` | PASS | 2026-11-08 |
| `input-path-oracle.py` | PASS, 9/9 mutantes | 2026-11-08 |
| `seam-coverage-oracle.py` | PASS | 2026-11-08 |
| `_strip-surface-oracle.py` | CONTROL PASS, `broken-copies-red=5 arms=118` | 2026-11-08 |
| `_skip-verdict-guard.py` | GREEN, 414 logs, control 5/5 | 2026-11-08 |
| `agents-md-pins-oracle.py` | PASS, 2 pins ao vivo | 2026-11-08 |
| `battery-wiring-oracle.py` | PASS, `ligados=159 sem_passo=109 populacao=268` | 2026-11-08 |
| `battery-class-oracle.py` | PASS, arms=3 | 2026-11-08 |
| `battery-budget-oracle.py` | RATCHET-OK, `total=2270.6s` de um tecto 6091.3 s | 2026-11-08 |

## 4. O QUE NAO ESTA' VERIFICADO

- A corrida completa re-feita por causa destas curas estava a correr quando este
  recibo foi escrito: o `BATTERY-VERDICT` dela e' o que conta, e ele vive em
  `_main\_audit-verify\_battery-summary.txt` com o run id ao lado. Um recibo que
  cita o veredicto antes de o ter e' precisamente o que a LEI DOS TESTES proibe.
- `verified` continua impossivel de uma lane: nenhuma destas curas foi vista no
  ECRA do dono.
