# Recibo -- a segunda que o YouTube paga (2026-11-09, lane CdpLatency)

Dono, verbatim: *"it should be extremely responsive. and it SHOULD NOT matter that
my pc is exhausted, cause this is not even from the asr models. its from youtube
bridge."*

## 0. Sumario

| # | Pergunta | Resposta medida |
|---|---|---|
| 1 | Onde esta' o **1 s** de `YOUTUBE_TARGET_SLOW ms=1015`? | Na **sonda WebSocket** (`pick_playing` -> `probe_tabs` -> `_ws_eval`) de uma aba `watch` que nao responde ao `Runtime.evaluate`: `1000-1031 ms` por chamada, medido ao vivo (seccao 2). O `/json/list` em si custa `1.2-12.9 ms` (mediana `2.9 ms`, 20 amostras). |
| 2 | Onde esta' a leitura de **8.3 s** (`phases={'target': 8281.0}`)? | NAO na CDP: o marco `target` e' `self._target_window(uia, UIA)` (`sotto_webview.py:4025`), e o custo e' `external_subs.player_source` -> `_address_bar_url` (arvore UIA do Chrome). A CDP corre depois, no marco `youtube`. Preciso de um patch de 12 linhas em `sotto_webview.py` (seccao 4). |
| 3 | O tick paga alguma coisa com a foto quente? | `0.000 ms` por chamada (`n=200`), `p95=0.0011 ms` no oraculo com um transporte falso de **1 s** (`n=1000`). |
| 4 | Foi criada/movida/activada/fechada alguma aba do dono? | Nao: `tabs_before=33`, `tabs_after=33`, `unchanged=True` (conjunto `(id, url, title)` comparado). Alvo ligado: `F21D077DF79322DA3FA90047BFE64631` (aba *"Anime Dorohedoro Season 2 ..."*). |

Ficheiros meus tocados: `app/webview/youtube_cdp_source.py` (+ oraculos
`_main/youtube-cdp-source-oracle.py`, `_main/youtube-cdp-boot-oracle.py`,
`_main/youtube-cdp-latency-oracle.py`, sondas `_main/cdp-latency-probe.py`,
`_main/cdp-source-live-probe.py`). `app/webview/youtube_window.py` e
`youtube_clock.py`/`youtube_monotonic.py` **nao** foram tocados (o oraculo da
janela ja' estava verde: 12/12).

## 1. Tabela dos saltos (Chrome vivo do dono, `127.0.0.1:9222`)

Comando: `python _main/cdp-latency-probe.py 9222 12`

```
raw-tcp-connect        {"min": 0.12, "median": 0.88,  "p95": 10.38, "max": 10.38}
urllib /json/version   {"min": 0.46, "median": 1.43,  "p95": 11.96, "max": 11.96} bytes=455
keepalive /json/version{"min": 0.15, "median": 0.21,  "p95": 0.75,  "max": 0.75}  bytes=455
urllib /json/list      {"min": 1.21, "median": 2.88,  "p95": 12.9,  "max": 12.9}  bytes=25189
keepalive /json/list   {"min": 0.62, "median": 1.01,  "p95": 3.46,  "max": 3.46}  bytes=25189
app list_targets       {"min": 1.55, "median": 3.04,  "p95": 12.82, "max": 12.82} watch_tabs=2 others=9
```

| salto | quem chama | custo por chamada | chamadas/s | payload |
|---|---|---|---|---|
| `GET /json/list` (socket novo) | `list_targets` | 1.2-12.9 ms (med 2.9) | 2/s (`_TID_TTL_S=0.5`), 0.1/s em regime lento (`_TID_SLOW_TTL_S=10`) | 25 714 B / 32 abas (2 `watch`, 1 275 B) |
| `GET /json/list` (keep-alive) | sonda | 0.6-3.5 ms (med 1.0) | idem | idem |
| `list_targets` + `pick_target` (`_tid_refresh(probe=False)`) | fio `yt-cdp-target` | 0-16 ms (med 16) | 2/s | idem |
| `probe_tabs`/`_ws_eval` (`_tid_refresh(probe=True)`) | fio `yt-cdp-target` (regime antigo) | **1000-1031 ms** (timeout de socket) | 1 por ~10 s (`ttl_s=10`) | frames WS minusculos |
| `target_video_id()` (foto quente) | tick do laco de legenda (`sotto_webview.py:2465,2773,3589,4262`) | **0.000 ms** (p95 0.0011 ms em 1000) | ate' 25/s | nenhum |
| `_target_window` -> `player_source` (UIA) | leitura externa (`sotto_webview.py:4025`) | **8 281 ms** (1 amostra em 468; mediana 31.7 ms) | 1/leitura | arvore UIA do Chrome |

O `EXTERNAL_CAPTIONS_READ_STATS n=468 mean_ms=31.7 p95_ms=16 max_ms=8281` do log
vivo e' consistente com a ultima linha: a mediana e' baixa, o maximo e' uma
unica chamada UIA patologica -- nao e' a CDP.

## 2. O mecanismo da segunda (provado, nao inferido)

`python -`, com a lista real de abas e a funcao real:

```
tabs=2 watch=2
pick_playing timeout=1.0 trial 1 ms=1031 vid='guARjKjyFLY' why=foreground
pick_playing timeout=1.0 trial 2 ms=1000 vid='guARjKjyFLY' why=foreground
pick_playing timeout=1.0 trial 3 ms=1000 vid='guARjKjyFLY' why=foreground
```

1000/1031 ms e' o **timeout de socket** (`PROBE_TIMEOUT_S=1.0`) de uma das duas
abas `watch`: a aba de fundo nao responde ao `Runtime.evaluate`, o `_ws_eval`
espera o tecto inteiro, e o `pick_playing` so' devolve depois disso. E' o mesmo
numero do log: `YOUTUBE_TARGET_SLOW ms=1015/1016 ... src=refresher` a cada ~11 s
(`ttl_s=10` depois da chamada lenta).

O que mudou no meu ficheiro para este caminho:

* `PROBE_TIMEOUT_S 1.0 -> 0.35`, `PROBE_BUDGET_S = 0.5` e *deadline* em
  `probe_tabs` (`_main/youtube-cdp-latency-oracle.py` L3: `ms=500`, frozen de
  5 s, `abandoned=1`);
* `_tid_refresh(probe=False)`: a re-escolha do fio **nao sonda WebSocket** --
  lista + URL/titulo (`0-16 ms`, medido);
* a sonda cara nao se repete de 1 em 1 s: o TTL viaja com a escolha
  (`PLAYING_PROBE_SLOW_TTL_S=5.0`);
* `target_video_id()` com foto quente = leitura de memoria; com foto ausente e
  fonte arrancada paga no maximo `_TID_INLINE_WAIT_S=0.10` (primeira pergunta) ou
  `_TID_WAIT_S=0.30` (ligada mas ainda sem publicacao) -- **nunca** a pergunta.

## 3. Antes / depois (mesma maquina)

| metrica | antes (log vivo, pid shell 27568, 21:35-21:36) | depois (modulo novo neste processo, mesmo Chrome) |
|---|---|---|
| `YOUTUBE_TARGET_SLOW` | `ms=1015`, `ms=1016`, `ms=1016` a cada ~11 s | `_tid_refresh(probe=True)`: `437 ms` / `568 ms` com o orcamento de 500 ms; `_tid_refresh(probe=False)`: `0-16 ms` |
| `target_video_id()` no tick | podia pagar `_tid_refresh()` inteiro no fio do laco (comentario do proprio ficheiro: `EXTERNAL_CAPTIONS_READ_MS ms=1000.0 phases={'target': 16.0, 'source': 1000.0}`, 984 ms dentro) | `0.000 ms` (mediana de 200 chamadas, foto quente); `p95=0.0011 ms` em 1000 chamadas com transporte falso de 1 s (`_main/youtube-cdp-latency-oracle.py` L1) |
| `EXTERNAL_CAPTIONS_READ_MS` | `ms=8281.0 phases={'import': 0.0, 'target': 8281.0}` (UIA) | **nao medivel sem `sotto_webview.py`** -- patch na seccao 4 |
| `YOUTUBE_LOOP_HZ` | `3.9` / `4.0` (`ticks=40 ok=40`) | nao medivel sem reiniciar a app; o que o laco paga ao tick cai de ~1000 ms/11 s para 0 |

O processo da shell (`pid 27568`) ja' nao existe as 22:06 (o dono fechou a app as
21:36; o worker `30804` ainda vive). Nao a relancei -- regra da lane. O "depois" e'
medido no **mesmo Chrome** com o modulo novo (`_main/cdp-source-live-probe.py`):

```
tabs_before=33 watch=2
  youtube_target id=F21D077DF79322DA3FA90047BFE64631 title='Anime "Dorohedoro Season 2" Non-Credit Opening...'
  youtube_target id=E606035CB2A9A2C3C2AC8087CC506906 title='I discovered a sound that leaks your exact location...'
list_ms n=20 min=2.4 median=3.6 p95=16.2 max=37.2
source start_ms=93.2 cold_ms=34.8 cold_vid=''
refresh_noprobe_ms=91.5 pick='' refresh_probe_ms=568.6 pick='guARjKjyFLY'
tabs_after=33 unchanged=True
  LOG YOUTUBE_CDP_ATTACH_OK attempt=1 ok=true reason=foreground port=9222 ms=485 pick=guARjKjyFLY
  LOG YOUTUBE_TARGET_SLOW ms=547 vid=guARjKjyFLY ttl_s=10 src=refresher
```

(`cold_ms=34.8` e' o caminho "ligada mas ainda sem publicacao" com a espera
curta; o valor sai do cache a partir da primeira publicacao. O `refresh_noprobe=91.5`
e' a primeira chamada, fria; em regime: `0, 15, 16, 16, 47 ms`, mediana 16 ms.)

## 4. O 8.3 s: o patch que eu nao posso aplicar (`sotto_webview.py` e' do Main)

O marco `target` fecha **antes** da CDP:

```
app/webview/sotto_webview.py:4025        hwnd = self._target_window(uia, UIA)
app/webview/sotto_webview.py:4026        _yt_mark(self, 'target')
app/webview/sotto_webview.py:4370        src = external_subs.player_source(fg, uia, UIA)
```

`player_source` chama `_address_bar_url` (UIA) para ler a barra de endereco do
Chrome; com a janela do YouTube em primeiro plano o titulo ja' provou tudo o que
a UIA ia ler (`_window_is_player` devolve `external:youtube` por titulo+processo,
`external_subs.py:711`). Sugestao exacta (`_target_window`, linhas 4362-4375):

```diff
--- a/app/webview/sotto_webview.py
+++ b/app/webview/sotto_webview.py
@@ -4362,11 +4362,28 @@
                     _tl = str(title or '').lower()
-                    if ('youtube' in _tl or 'stremio' in _tl
-                            or 'stremio' in str(_proc or '').lower()
-                            or not _proc):
+                    if 'youtube' in _tl:
+                        # O TITULO JA' PROVOU, COM O PROCESSO, O QUE A UIA IA
+                        # LER (2026-11-09, MEDIDO): `EXTERNAL_CAPTIONS_READ_MS
+                        # ms=8281.0 phases={'target': 8281.0}`. `url=''` salta
+                        # `_address_bar_url` e decide com `_window_is_player`
+                        # (titulo + nome do processo, ambos Win32 em us).
+                        try:
+                            src = external_subs.player_source(fg, uia, UIA,
+                                                              url='')
+                        except Exception:
+                            src = ''
+                    elif ('stremio' in _tl
+                          or 'stremio' in str(_proc or '').lower()
+                          or not _proc):
                         # `not _proc` = nao se sabe quem e' a janela: ai a
                         # pergunta cara volta a ser feita, porque uma janela
                         # desconhecida pode ser um player que a CDP nao ve.
                         try:
-                            src = external_subs.player_source(fg, uia, UIA)
+                            _t_uia = time.monotonic()
+                            src = external_subs.player_source(fg, uia, UIA)
+                            _ms_uia = (time.monotonic() - _t_uia) * 1000.0
+                            if _ms_uia >= 300.0:
+                                # UM VEREDICTO NAO PODE CUSTAR 8 s EM SILENCIO.
+                                log('YOUTUBE_TARGET_UIA_SLOW ms=%.0f '
+                                          'verdict=%s title=%r'
+                                          % (_ms_uia, src or '-',
+                                             str(title)[:60]))
                         except Exception:
                             src = ''
```

Porque e' seguro: `_window_is_player(titulo, processo, '')` e' a MESMA regra que
`player_source` aplica depois de ler a URL (`external_subs.py:709-718`); a unica
diferenca e' uma janela de browser com "youtube" no titulo mas noutra pagina --
que agora e' adoptada como `external:youtube` (a CDP e o resolvedor de titulo
corrigem a identidade no tick seguinte). O caso do Explorador com "youtube" no
nome da pasta continua recusado (`_is_browser(proc)`).

Ressalva honesta: um "orcamento duro" a serio para o ramo `not _proc` nao se faz
com um `Thread` com prazo -- a chamada COM segura o GIL (esta' documentado no
proprio ficheiro: 29,3 s sem o observador do Ctrl+Space). Por isso o patch acima
*mede e publica* o custo em vez de fingir que o corta; a alternativa real e'
tirar a UIA do caminho da leitura (uma thread de aquecimento com o proprio
objecto COM), que e' uma mudanca maior e fica para o Main decidir.

## 5. O que verifiquei (tudo verde, e os negativos a vermelho)

| comando | resultado |
|---|---|
| `python _main/youtube-cdp-latency-oracle.py` | `VERDICT: PASS (arms=4 fail=0)` -- L1 `p95=0.0011 ms` (1000 chamadas, transporte de 1 s), L2 `YOUTUBE_TARGET_STALE age_ms=1157 ttl_s=0.5`, L3 `ms=500` com aba congelada de 5 s, L4 `mediana_ms=94` |
| `python _main/youtube-cdp-latency-oracle.py --neg-arm` | `NEG-ARM: PASS (tres mutantes, os tres apanhados)` (`inline` -> L4 RED ~1 s; `sem-orcamento` -> L3 RED 5 s; `sem-idade` -> L2 RED) |
| `python _main/youtube-cdp-source-oracle.py` | `VERDICT: PASS (23/23)` |
| `python _main/youtube-cdp-source-oracle.py --neg-arm` | `NEG-ARM: PASS (16/16)` |
| `python _main/youtube-cdp-boot-oracle.py` | `VERDICT: PASS (9/9)` |
| `python _main/youtube-cdp-boot-oracle.py --neg-arm` | `NEG-ARM: PASS (6/6)` |
| `python _main/yt-source-singleton-oracle.py` | `PASS (4/4)` |
| `python _main/youtube-window-oracle.py` | `PASS 12/12` |
| `python _main/yt-loop-uia-oracle.py` | `PASS (arms=4 fail=0)` |
| `python _main/yt-target-stale-oracle.py` | 6/7 -- `STALE-ID` PASS (era FAIL, corrigido); `REBOUND` vermelho por causa do amortecimento do Main |

`REBOUND`: prova de que nao e' meu -- com um `FakeCdp` (sem o meu ficheiro) e a
shell real, uma unica chamada a `_youtube` escreve so'
`YOUTUBE_TARGET_REBIND_ARMED`; a mudanca do Main (`YT_REBIND_CONFIRM_S = 1.5`)
exige duas leituras, e o oraculo faz uma.

## 6. Bugs de oraculo que a corrida do `--neg-arm` desenterrou (corrigidos)

1. `_main/youtube-cdp-source-oracle.py`, mutante `sem-assinatura`: a ancora tinha
   `if (cached and ...` com parenteses; o codigo real (reescrito nesta lane)
   nao os tem -> a mutacao **nao aplicava** e a arm ficava `NOT-CAUGHT` (corrida
   anterior: `VERDICT: FAIL (15/16)`). Corrigida a ancora -> `CAUGHT`.
2. `--neg-arm`, mutante `sem-preabertura`: escrevia a copia a partir de `src`
   (fonte do MODULO) e usava-a como `shell_path` -- o "CAUGHT" era o shell a
   rebentar no import, nao a mutacao a remover a chamada. Agora usa `shell_src`;
   com a chamada a desaparecer, `porta-cdp-abre-no-arranque` cai de verdade.
3. `_main/youtube-cdp-boot-oracle.py` e `youtube-cdp-source-oracle.py` procuravam
   `self._yt_cdp_boot_attach()` (com parenteses); o Main passou a chamada a
   `threading.Thread(target=self._yt_cdp_boot_attach, ...)` (arranque nao
   bloqueante, 2026-11-09). As verificacoes passaram a procurar o NOME e o
   mutante troca `target=self._yt_cdp_boot_attach,` por `target=lambda: None,`;
   a arm do arranque espera agora (ate' 5 s) pela resposta do fio, em vez de a
   exigir sincrona. `9/9` e `6/6`.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: CdpLatency
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CdpLatency']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CdpLatency']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-10T01:10:36.905468+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CdpLatency']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CdpLatency']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

status: done

## 7. SELF-AUDIT

- **protocolos em falta** -- devia ter corrido o `--neg-arm` do oraculo de
  origem *antes* de escrever a sonda nova: dois mutantes estavam podres
  (ancora velha, ficheiro errado) e um deles dava verde falso. Da proxima:
  `--neg-arm` primeiro, e uma assercao `mutante != original` em cada escrita.
- **verificacao adicional** -- faltou medir o `YOUTUBE_LOOP_HZ` *depois* com a
  app a correr; custa reiniciar a app no ecra do dono, o que a lane proibe.
  Fica o custo por tick (0.000 ms) e o oraculo como prova indirecta.
- **checkboxes novas** -- `python _main/youtube-cdp-latency-oracle.py --neg-arm`
  tem de imprimir `PASS` e cada mutante tem de verificar que o ficheiro mudou
  antes de o carregar (2 linhas: `assert mut != original`).
- **review por outro subagente** -- sim-com-escopo: o patch proposto para
  `sotto_webview.py` (seccao 4), porque toca um ficheiro que nao e' meu.
- **gate-doubt**:
  - verde-de-verdade: `youtube-cdp-latency-oracle --neg-arm` -- os tres mutantes
    foram escritos em copias e *carregados por `spec`*; o L3 RED mediu `ms=5047`
    com a aba congelada de 5 s e o L4 RED mediu `~1016 ms`, logo o verde do
    caminho normal nao e' passar por construcao. O `youtube-cdp-source-oracle`
    23/23 correu sobre o ficheiro real; o `--neg-arm` 16/16 inclui agora o
    `sem-assinatura` corrigido.
  - falta-no-gate: nada verifica que `_target_window` **nao** abre a UIA com um
    titulo de YouTube -- e' exactamente o buraco de onde saiu o `target=8281.0`.
    Um futuro `player_source` voltar a ser chamado ali passa verde em todos os
    oraculos desta lane.
  - gate-melhor: um braco em `_main/page-scan-browser-oracle.py` (ou um novo
    `youtube-target-window-oracle.py`) que injecte um `player_source` falso de
    2 s e exija `_target_window` < 50 ms com titulo "- YouTube"; com o codigo de
    hoje fica RED (~2000 ms), com o patch da seccao 4 fica GREEN.
- **confianca** -- alta no diagnostico e no caminho do tick (medido ao vivo,
  com negativo); media na estimativa de quanto o `YOUTUBE_LOOP_HZ` sobe na app
  real, porque depende do `sotto_webview.py` (patch pendente).
- **nao verificado** -- `YOUTUBE_LOOP_HZ` depois, com a app reiniciada (proibido
  nesta lane); o patch da seccao 4 aplicado de facto; o comportamento do
  `_target_window` com o patch num browser cujo titulo diz "youtube" mas a
  pagina nao e' YouTube.
