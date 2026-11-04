# Receipt — a fonte YouTube do ARRANQUE (`YtSourceOnBoot`), 2026-11-04

## A ordem, restated

O dono quer a legenda do **YouTube** no ecrã com a legenda do Sotto. No arranque a
fonte YouTube não está ligada — `YOUTUBE_TICK_MS src='?' vid='' cdp_age_ms=? rows=?` —
e o que ele lê é o **ASR do áudio do vídeo**, não a faixa do player. O attach tem de
acontecer no arranque, sem esperar que o painel abra; cada tentativa falhada tem de
dizer o motivo; e a linha `YOUTUBE_TICK_MS` tem de trazer sempre `src`, `vid`,
`cdp_age_ms` e `rows`, sem `?`.

Worktree: `H:/sotto-wt/YtSourceOnBoot` — branch `lane/yt-source-on-boot`, base `8007032`.

## PASSO 0 — o processo é o da árvore?

```
$ python _main/live-code-freshness-oracle.py --strict
LIVE_CODE STALE log=H:\sotto\_main\webview-run.log
  pid=42548 started=2026-11-04 10:06:36.407
  processo: sha256=3533907AABB8
  disco   : sha256=E84435F6830A files=39
  porque  : a etiqueta do processo nao e a do disco (hash diferente)
  >>> O QUE O DONO CARREGA NAO E ESTE CODIGO.
```

**STALE.** A app viva é anterior ao código em disco: as linhas de log abaixo são do
build que ele carrega, não do que eu editei. Nenhuma afirmação de *comportamento
depois* vale sem reiniciar a app — e reiniciar a app dele não é desta lane.

## BEFORE — verbatim, do log dele (somente leitura)

```
492884:2026-11-04 10:16:16.811 sotto: YOUTUBE_CDP_HEALTH age=0.0 stats={'reads': 4567, 'errors': 5, 'last_error': 'ValueError: payload sem forma', 'note': 'attached'}
492886:2026-11-04 10:16:17.788 sotto: YOUTUBE_CDP_SOURCE state=wrong-video (vDmjw-c_R2k)
492887:2026-11-04 10:16:17.794 sotto: YOUTUBE_CDP_SOURCE state=ambiguous
```

```
499838:2026-11-04 10:56:04.933 sotto: YOUTUBE_TICK_MS avg=0 max=0 n=20 src='?' vid='MOZIBMBHK-8' cdp_age_ms=2387891 rows=0 why='cdp-fresh-skip'
499860:2026-11-04 10:56:30.641 sotto: YOUTUBE_TICK_MS avg=0 max=0 n=20 src='?' vid='MOZIBMBHK-8' cdp_age_ms=2413609 rows=0 why='cdp-fresh-skip'
499875:2026-11-04 10:56:45.989 sotto: YOUTUBE_TICK_MS avg=0 max=0 n=20 src='?' vid='MOZIBMBHK-8' cdp_age_ms=2428953 rows=0 why='cdp-fresh-skip'
499904:2026-11-04 10:57:16.517 sotto: YOUTUBE_TICK_MS avg=1 max=16 n=19 src='?' vid='MOZIBMBHK-8' cdp_age_ms=2459484 rows=0 why='cdp-fresh-skip'
```

```
493210:2026-11-04 10:19:02.350 sotto: YOUTUBE_TICK_MS avg=0 max=0 n=20 src='?' vid='MOZIBMBHK-8' cdp_age_ms=165250 rows=0 why='cdp-fresh-skip'
500794:2026-11-04 11:05:23.773 sotto: YOUTUBE_TICK_MS avg=36 max=610 n=17 src='?' vid='MOZIBMBHK-8' cdp_age_ms=2946734 rows=0 why='cdp-fresh-skip'
501014:2026-11-04 11:07:27.079 sotto: YOUTUBE_TICK_MS avg=0 max=0 n=20 src='?' vid='MOZIBMBHK-8' cdp_age_ms=3070031 rows=0 why='cdp-fresh-skip'
```

Contagem (mesmo ficheiro, `grep` em Python):

```
tick_src_qmark 1482      (de 3972 linhas YOUTUBE_TICK_MS = 37 %)
first 2026-11-03 18:54:29.378 … src='?' vid='' cdp_age_ms=? rows=? why=''
last  2026-11-04 11:07:27.079 … src='?' vid='MOZIBMBHK-8' cdp_age_ms=3070031 rows=0
health_age_none 15 / health_total 165
preopen_failed 0
boot_attach_lines 0
```

O arranque, do mesmo log:

```
490373:2026-11-04 10:06:36.483 sotto: CAPTION_PIPELINE_START reason=pre-webview
490448:2026-11-04 10:06:40.798 sotto: YOUTUBE_CDP_SOURCE state=attached
```

### O que os números dizem (leitura do código, não inferência)

1. **A porta CDP não abre no arranque.** `SottoShell.start_caption_pipeline` chamava
   `self._yt_cdp_ensure()` — método que existe **no `ExternalCaptionWatcher`**, não na
   shell. `AST`: `_yt_cdp_ensure in ExternalCaptionWatcher line 3364`,
   `start_caption_pipeline in SottoShell line 12662`. O `AttributeError` caía no
   `except` e saía como `YOUTUBE_CDP_PREOPEN_FAILED`; a porta abria no primeiro tick
   do laço — 4,3 s depois, com o WebView2 pelo meio.
2. **`src='?'`** porque `_yt_diag` só era escrito em dois ramos de `_read`; os outros
   não escreviam nada e o `.get('src','?')` publicava a interrogação.
3. **`cdp_age_ms=2413609`** (40 min) porque a idade ficou congelada no instante em que
   aquele ramo correu, não no instante em que a linha saiu.
4. **A `cdp-fresh-skip` mentia**: `_fresh = _age is not None and _age <= 8.0`, e 2413 s
   não é fresco. O build carregado é anterior à correção da etiqueta (`STALE` acima).

## A mudança

### `app/webview/youtube_cdp_source.py`

- **`resolve_port(port=None)`** (novo): argumento → `SOTTO_YT_CDP_PORT` → 9222. Existe
  para um oráculo poder apontar o attach a um `/json/list` de fotografia sem tocar no
  Chrome do dono. `boot_attach` e `CdpCaptionSource.__init__` passam a usá-la.
- **`boot_attach(port=None, attempts=3, delay=0.25, timeout=0.4, log, sleep)`** (novo):
  faz a MESMA pergunta do laço (`list_targets` + `pick_target`), sem janela em primeiro
  plano, sem evento de painel e sem tick. Devolve `(ok, motivo)` e escreve **uma linha
  por tentativa**:
  `YOUTUBE_CDP_BOOT_ATTACH attempt=1/3 ok=false reason=port-closed port=… ms=… err=…`.
  Tecto medido: uma sonda contra porta fechada custa **2,0 s de `URLError`** nesta
  máquina; quatro dessas seguravam o arranque ~10 s. Com 0,4 s por sonda o pior caso é
  ~1,45 s — o remédio não pode fazer o mesmo estrago que a doença.
- **`video_id_from_url(url)`** (novo): o `v=` de um `watch`, um sítio só.
- **`CdpCaptionSource._connect`**: contador de tentativas + `_attach_log`, que escreve
  `YOUTUBE_CDP_ATTACH_OK attempt=N ok=true reason=only-tab … video_id=…` ou
  `YOUTUBE_CDP_ATTACH_FAILED attempt=N ok=false reason=port-closed|no-youtube-tab|ambiguous|no-ws-url|ws-failed ms=…`.
  As primeiras 20 saem todas, depois uma em cada 50 (`_ATTACH_LOG_N` / `_ATTACH_LOG_EVERY`):
  o Chrome pode ficar fechado a tarde inteira e o log não paga 30 linhas/min.
- **`ATTACH_PROBE_TIMEOUT_S = 1.5`**: a sonda de attach da thread, não a chamada geral
  (o `/json/list` mais lento já medido é 1125 ms sob carga).

### `app/webview/sotto_webview.py`

- **`SottoShell._yt_cdp_boot_attach()`** (novo, ~12729): chamado por
  `start_caption_pipeline` **antes** do watcher e do worker. Honra `SOTTO_YT_CDP=0`
  (`skipped reason=SOTTO_YT_CDP=0`), chama `boot_attach`, cria a `CdpCaptionSource`
  **na shell** e arranca-a; sem ligação publica
  `YOUTUBE_CDP_BOOT_ATTACH_DEFERRED reason=… retry_s=2`.
- **`start_caption_pipeline`**: `self._yt_cdp_ensure()` → `self._yt_cdp_boot_attach()`
  (a chamada morta descrita acima).
- **`ExternalCaptionWatcher._yt_cdp_ensure`**: adota a fonte da shell quando ainda não
  tem nenhuma — uma thread por aba, não duas.
- **`ExternalCaptionWatcher._yt_diag_now()`** (novo): compõe os cinco campos do
  `YOUTUBE_TICK_MS`. `src`/`vid`/`why` = último ramo conhecido (`unattached`/`none`/
  `no-frame` quando não há ramo); `cdp_age_ms` e `rows` lidos **agora**
  (`snapshot_age()` + `len(yt_cdp_rows)`).
- **`YOUTUBE_TICK_MS`**: `rows=%s` → `rows=%d`, e os `.get('src','?')`/
  `.get('age','?')`/`.get('rows','?')` desaparecem.
- **Diag seteado por quem produz**: `_yt_cdp_snapshot` publica
  `src='external:youtube:cdp'` com `vid`/`age`/`rows` da foto; os dois ramos sem janela
  escrevem `unattached`/`none`; o ramo do `cdp-fresh-skip` deixa de poder escrever `?`.

### `_main/youtube-cdp-source-oracle.py`

A11 (`porta-cdp-abre-no-arranque`) e o mutante `sem-preabertura` procuravam
`self._yt_cdp_ensure()` — a chamada que nunca funcionou. Passam a procurar
`self._yt_cdp_boot_attach()`. Sem isto o portão existente ficava vermelho sobre código
correto (um portão que não é atualizado não é um portão que passou).

### `docs/youtube-source-identity.md`

Secção nova com o defeito medido, a regra (arranque pede o attach; diagnóstico sem `?`)
e as linhas de log novas.

## AFTER — o que foi executado

### O oráculo novo (`_main/youtube-cdp-boot-oracle.py`)

```
$ python _main/youtube-cdp-boot-oracle.py
arranque-sem-painel              PASS  asked=1 alive=True calls=['watcher', 'worker:declined']
                                       YOUTUBE_CDP_BOOT_ATTACH attempt=1/3 ok=true reason=only-tab port=56442 ms=15 tabs=1 others=0
controle-porta-desligada         PASS  created=None skipped=1 'YOUTUBE_CDP_BOOT_ATTACH skipped reason=SOTTO_YT_CDP=0'
retry-limitado                   PASS  ok=False why=port-closed lines=3 last='YOUTUBE_CDP_BOOT_ATTACH attempt=3/3 ok=false reason=port-closed port=56444 ms=406 err=URLError'
controle-retry-ligado            PASS  ok=True why=only-tab lines=1
aba-que-navegou                  PASS  vid=NEWNEWNEWNE 'YOUTUBE_CDP_SOURCE state=attached'
controle-aba-ainda-aberta        PASS  vid=OLDOLDOLDOL adopted=0 'YOUTUBE_CDP_ATTACH_OK attempt=4 ok=true reason=named port=56454 ms=0 video_id=OL'
diagnostico-sem-interrogacao     PASS  empty=('unattached', '', 'none', 0, 'no-frame')
                                       qmark=('external:youtube', 'VID12345678', '1500', 2, 'no-frame')
                                       none_age=('external:youtube', 'VID12345678', 'none', 2, 'no-frame')
linha-do-log-completa            PASS  format=True qmark_defaults=False
VERDICT: PASS (8/8)
```

Como cada arm fala com o produto (nenhuma procura texto):

- **A1** executa `SottoShell.start_caption_pipeline('pre-webview')` REAL sobre uma
  subclasse cujo `__init__` não corre: sem painel, sem WebView2, sem args. A chamada
  tem de produzir `YOUTUBE_CDP_BOOT_ATTACH ok=true` e deixar `_yt_cdp_source` vivo na
  shell. **Controle:** `SOTTO_YT_CDP=0` → nenhuma fonte e uma linha `skipped`.
- **A2** executa `boot_attach` contra uma porta fechada (3 tentativas, 3 linhas de
  motivo) e **contra** um `/json/list` de fotografia (`ok=true`, uma linha).
- **A3** executa o laço REAL (`CdpCaptionSource._run`) com um WebSocket de fotografia:
  o vídeo declarado desapareceu das abas e a foto traz outro → `_video_id` passa a
  `NEWNEWNEWNE` e o estado diz `adopted:OLDOLDOLDOL->NEWNEWNEWNE`; **controle** com as
  duas abas abertas → não adota, `_video_id` fica `OLDOLDOLDOL`, estado
  `wrong-video (NEWNEWNEWNE)`.
- **A4** executa `_yt_diag_now()` nos três estados (vazio, com `src='?'`, fonte com
  foto de 1,5 s) e exige cinco campos completos, idade **viva** (`1500`).
- **A5** exige `rows=%d` e a ausência dos defaults `'?'` no fonte da shell.

```
$ python _main/youtube-cdp-boot-oracle.py --neg-arm
NEG-ARM arranque-sem-painel            CAUGHT
NEG-ARM retry-limitado                 CAUGHT
NEG-ARM aba-que-navegou                CAUGHT
NEG-ARM diagnostico-sem-interrogacao   CAUGHT
NEG-ARM VERDICT: PASS (4/4)
RC=1
```

`rc=1` é o resultado esperado (`--neg-arm` devolve 1 QUANDO APANHA o mutante): as quatro
mutações são a chamada de arranque trocada por `pass`, o retry preso a uma tentativa, a
adoção removida, e o `if not src or src == '?'` desligado.

### Regressão nos portões vizinhos

```
$ python _main/youtube-cdp-source-oracle.py            → VERDICT: PASS (11/11)
$ python _main/youtube-cdp-source-oracle.py --neg-arm  → VERDICT: PASS (6/6)   rc=1
$ python _main/yt-target-stale-oracle.py              → VERDICT: PASS (arms=7 fail=0)
$ python _main/yt-loop-uia-oracle.py                  → VERDICT: PASS (arms=4 fail=0)
$ python _main/reveal-park-oracle.py                  → VERDICT: GREEN (5/5 arms)
$ python _main/youtube-track-wiring-oracle.py         → VERDICT: PASS  arms 12/12  mutants 5/5
$ python _main/owner-screen-gate.py                   → OWNER-SCREEN VERDICT PASS (achados=0 <= baseline=0)
$ python _main/console-window-audit.py                → CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela
```

### O motivo por tentativa, medido na thread real

`CdpCaptionSource` real contra uma porta fechada, 6 s de observação:

```
port 57309 lines 3
  YOUTUBE_CDP_SOURCE state=port-closed
  YOUTUBE_CDP_ATTACH_FAILED attempt=1 ok=false reason=port-closed port=57309 ms=1500 err=URLError
  YOUTUBE_CDP_ATTACH_FAILED attempt=2 ok=false reason=port-closed port=57309 ms=1500 err=URLError
```

Antes desta mudança o mesmo troço publicava apenas `state=port-closed` na primeira vez e
nada depois (o `_publish` só fala quando o estado MUDA) — é a razão de 40 minutos de
`src='?'` sem uma linha que dissesse "a porta não abriu".

## Ficheiros alterados (sha256 dos primeiros 16 hex)

| ficheiro | sha256 | bytes |
|---|---|---|
| `app/webview/youtube_cdp_source.py` | `a2487a46b3ea0914…` | 34969 |
| `app/webview/sotto_webview.py` | `d4ade44e5b567f1c…` | 1030451 |
| `_main/youtube-cdp-boot-oracle.py` (novo) | `54bb1dad0c4e327e…` | 20527 |
| `_main/youtube-cdp-source-oracle.py` | `e6c455d310504a83…` | 14140 |
| `docs/youtube-source-identity.md` | `b874059c788c2112…` | 6469 |

`git diff --stat`: 4 ficheiros, +311 / −19 (mais o oráculo novo, untracked).

## O que NÃO ficou provado

- **O efeito na app viva.** O `PASSO 0` deu `STALE`: a instância do dono (pid 42548,
  10:06:36) corre um build anterior. Um arranque novo é dele (ou do autostart); esta
  lane não larga a app. **[INFERENCE]** Depois de reiniciar, o log deve mostrar
  `YOUTUBE_CDP_BOOT_ATTACH … ok=true` **antes** de `EXTERNAL_CAPTIONS_WATCH started`
  e nenhuma linha `YOUTUBE_TICK_MS` com `src='?'`.
- **O tempo até à primeira linha do player** com o attach no arranque: não medido nesta
  sessão (exige reiniciar a app). O único número medido aqui é o custo do pedido:
  15 ms contra um `/json/list` que responde, 406 ms por tentativa contra porta fechada.
- **`YOUTUBE_CDP_HEALTH`** não foi mudado: o pedido era dizer o que ele diz (diz
  `attached` / `reads` / `errors` — e `age=0.0` com a foto fresca), não acrescentar
  campos.
- Os 1 482 `src='?'` citados são **do build carregado**, não do código editado: são a
  evidência do defeito, não uma medição do remédio.
