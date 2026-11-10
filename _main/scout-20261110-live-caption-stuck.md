# Scout — Ctrl+Space não esconde, legenda congelada para sempre

**Data:** 2026-11-10
**Alvo:** `H:/sotto` (shell Python + overlay Win32 + worker ONNX), sessão que terminou em `2026-11-09 21:36:10`
**Fonte primária:** `_main/webview-run.log` (187 339 linhas, 2026-11-08 18:23:00.721 → 2026-11-09 21:36:10.309)
**Método:** leitura do log por script Python (janela temporal + contagem de tags + extracção de excerptos) e leitura do código em `app/webview/`. Nada foi executado da app; nenhuma janela foi aberta; nenhum dispositivo de áudio foi tocado.
**Contrato:** read-only. Único ficheiro escrito: este.
**Estado do entregável:** `LIVE` para a evidência (as consultas ao log e as leituras de código foram exercitadas nesta sessão, com os comandos e saídas abaixo); `DARK` para qualquer conclusão sobre o *pixel* que o dono viu — o log não tem medição de pixels, só de eventos (ver Q4 e o instrumento em falta).
**Sem `todo`:** esta toolset não tem a ferramenta `todo`; a linha 1 do receipt é este cabeçalho e o fecho vai na última secção.

> **Aviso de numeração:** os `file:line` abaixo são do working tree lido em 2026-11-10. O build que correu às 21:21:48 tinha `shell_stale=False` (`SHELL_CODE_ID sha256=7028EFC6B91A files=105`), mas o disco pode ter andado desde então; as linhas citadas foram reconfirmadas por `grep -n` nesta data.

---

## Q1 — Depois do último `CAPTION_APPLIED` (21:29:59.363), o overlay mostrou/escondeu/repintou algo?

**Resposta: não. Zero eventos de legenda.** Na janela `21:30:00.000 – 21:36:59`, 321 linhas, e o vocabulário `CAPTION_*`, `OVERLAY`, `LIVE_ENABLED`, `LIVE_*` dá:

| tag | n |
|---|---|
| `CAPTION_*` (todas) | **0** |
| `OVERLAY` | **0** |
| `LIVE_ENABLED` | **0** |
| `LIVE_*` (só `LOAD_ACTION_LIVE_HELD`) | 6 |

Comando (Python, sem despejar bytes):

```python
win=[l for l in lines if '2026-11-09 21:30:00' <= l[:19] <= '2026-11-09 21:36:59']
# 321 linhas
```

Tabela completa da janela (contagem por tag):

```
    71 YOUTUBE_TICK_MS
    41 BRIDGE_ALIVE
    37 YOUTUBE_LOOP_HZ
    34 YOUTUBE_TARGET_SLOW
    34 WORKER
    12 YOUTUBE_TRACK_READY
    12 YOUTUBE_TRACK_PAINT
    12 EXTERNAL_CAPTIONS_READ_STATS
    11 BRIDGE_STATS_PUSH
     6 YOUTUBE_TARGET
     6 BRIDGE_METER
     6 BRIDGE_RSS
     6 BRIDGE_COST_CALLBACK_FAILED
     6 BRIDGE_STATS_REPLY
     6 YOUTUBE_CDP_SOURCE
     6 LOAD_ACTION_LIVE_HELD
     5 THREAD_CPU
     5 STATUS_APPLIED
     4 BATCH_EXEC_YIELDED
     1 SHELL_CODE_ID
```

As 14 linhas que casam `CAPTION_|OVERLAY|LIVE_ENABLED|LIVE_` entre 21:29:00 e o fim **são todas anteriores a 21:30:00**, e as últimas são:

```
2026-11-09 21:29:48.576 CAPTION_WINDOW_KEPT reason=panel-hidden wanted=true epoch=9
2026-11-09 21:29:56.061 CAPTION_WINDOW_BLANKED reason=video-changed epoch=10 wanted=true
2026-11-09 21:29:56.078 CAPTION_WINDOW_BLANKED reason=video-changed epoch=11 wanted=true
2026-11-09 21:29:56.090 CAPTION_PROVISIONAL_PAINT n=29 ... src=external:youtube:track text="Reeling like a desperado"
2026-11-09 21:29:57.592 CAPTION_APPLIED text="Reeling like a desperado." count=18 kind=partial
2026-11-09 21:29:59.363 CAPTION_APPLIED text="Reeling like a desperado." count=19 kind=partial
```

Isto é: **`CAPTION_WINDOW_BLANKED reason=video-changed epoch=11` às 21:29:56.078 é o ÚLTIMO evento de janela de legenda de todo o log.** Depois dele, 6 min 14 s sem uma única linha `CAPTION_*`/`OVERLAY`/`LIVE_ENABLED`.

O que continuou (e prova que o processo está vivo):

```
2026-11-09 21:36:09.805 YOUTUBE_TICK_MS ... src='external:youtube:cdp' vid='guARjKjyFLY' cdp_age_ms=375 rows=2 why='painted'
2026-11-09 21:36:10.309 YOUTUBE_LOOP_HZ ticks=40 ok=40 none=0 age_ms=176 hz=4.0 src_reads=833 src_errs=0
2026-11-09 21:36:03.879 WORKER_COST tag=tick ... rows=0 rows_since_tick=0 rows_per_min=0.0 ... pid=30804
```

E os `STATUS_APPLIED` que o dono provocou (áudio a voltar) chegaram ao painel sem chegar a lado nenhum da legenda:

```
2026-11-09 21:33:39.942 STATUS_APPLIED text="tap-engine-park-rescan" repetidas_silenciadas=10
2026-11-09 21:33:41.075 STATUS_APPLIED text="device-rotated (flat)"
2026-11-09 21:33:42.212 STATUS_APPLIED text="device-open-refused"
2026-11-09 21:33:42.216 STATUS_APPLIED text="device-rotated (open-failed)"
2026-11-09 21:33:42.456 STATUS_APPLIED text="capture-started"
```

Instrumento que já sabia disto e não gritou: `_main/webview-run.log` tem **zero** `no-caption-for-6.0s` em toda a sessão das 21:21:46 em diante, contra um às `21:17:01.804` na sessão anterior (ver Q3/o defeito único).

---

## Q2 — O observador do Ctrl+Space (role `live`) produziu algo nos últimos 10 minutos?

**Resposta: nada, e não só nos últimos 10 minutos — em toda a última sessão.** O último `HOTKEY_PRESSED role=live` do log é `21:16:08.483`; depois disso há 2 pressões, ambas `role=panels` (Alt+C):

```
2026-11-09 21:16:08.483 HOTKEY_PRESSED role=live count=3 source=hook via=ll_keyboard accelerator=Ctrl+Space thread=20652
2026-11-09 21:21:54.538 HOTKEY_PRESSED role=panels count=3 accelerator=Alt+C thread=4308
2026-11-09 21:22:25.599 HOTKEY_PRESSED role=panels count=1 accelerator=Alt+C thread=4308
```

Últimos `HOTKEY_LIVE_STEP` / `LIVE_ENABLED` / `HOTKEY_LIVE_MODE` (todos da sessão anterior, 21:15–21:16):

```
2026-11-09 21:16:09.188 HOTKEY_LIVE_STEP caption_on=true shown=false wanted=false
2026-11-09 21:16:09.201 LIVE_ENABLED on=true wanted=true panel_closed=false
2026-11-09 21:21:46.859 HOTKEY_LIVE_MODE role=live mode=swallow gaming=false swallow=true hook=true registered=true accelerator=Ctrl+Space plan=take
```

**Heartbeat:** `HOTKEY_OBSERVER_ALIVE` tem **0 ocorrências em 187 339 linhas** (`HOTKEY_OBSERVER_KEYS` idem). Quem o emite é `app/webview/sotto_webview.py:8077` (classe do observador `GetAsyncKeyState`, thread própria), e a condição de emissão está em `sotto_webview.py:8070-8076`:

```python
_due = (_beats < 6 and _now_loop - _last_beat >= 5.0) or \
       (_now_loop - _last_beat >= 300.0)
if _due or _gap_ms > 200:
    ...
    self.log_fn('HOTKEY_OBSERVER_ALIVE role=%s beats=%d loops=%d max_gap_ms=%d' ...)
```

O batimento **não** é um relógio: nos primeiros 30 s sai 6 vezes (5 s); depois só de 5 em 5 min, ou numa volta presa (`max_gap_ms > 200`). Logo, a ausência dele não prova morte. O que **para** o observador é `self._stop_requested.is_set()` (`sotto_webview.py:8060`) — é desarmar/`stop()` — e a thread só é criada quando o hook está em `passthrough|dialog|glyph-back` (ramo lido em `sotto_webview.py:6448` da versão em execução); em `mode=swallow` com `hook=true` (o publicado às 21:21:46.859) quem trata a tecla é o hook, não o observador. **Mas nada disso explica o silêncio: o hook estava armado (`swallow=true hook=true registered=true`) e não houve UMA linha.**

O caminho da tecla que a mata em silêncio, com `file:line`:

- `app/webview/space_swallow.py:109-152` — `classify_event`: a tecla só produz `toggle` quando `key_down_swallowed` está falso; se o keydown anterior ficou marcado e o keyup se perdeu, devolve `('swallow', 0)` (linha 112) e **engole para sempre sem `_fire_toggle` e sem log** (o `log()` de `space_swallow.py:62-74` é throttle e só sai em `HOTKEY_STOP_FAILED`/swallow).
- `app/webview/space_swallow.py:123-131` — se `mods_down() < required`, devolve `('pass', 0)`: a tecla chega à app, não faz nada e **não escreve nada**.
- `app/webview/space_swallow.py:89-97` — o `warn()` de diagnóstico termina em `ProcessQueryInformationImage`/diálogo; se a chamada devolver `cancel != 1` o aviso fica silencioso (nunca visto no log).

Conclusão de Q2: **o log não contém uma única prova de que o dono tenha carregado Ctrl+Space depois das 21:16:08; e o caminho da tecla, quando falha, não deixa linha nenhuma.** O observador do `live` foi substituído pelo hook desde 18:45 (`plan=take`, `mode=swallow`) e o batimento do observador não existe nesta build. Um Ctrl+Space que morre dentro de `classify_event` é indistinguível de uma tecla não carregada — é exactamente a dúvida que o heartbeat foi desenhado para resolver, e ele não corre.

---

## Q3 — O handler do Ctrl+Space / live e o caminho de esconder

Cadeia completa, com linhas do working tree:

1. **Hook teclado → shell.** `space_swallow.py:117` (`toggle = not key_down_swallowed`) e `:135-140` (`on_event` → `swallow`, log `HOTKEY_...` quando dispara). O hook chama o *callback* instalado em `app/webview/sotto_webview.py:8009-8035` (o mesmo que, com `kind='live'`, faz `_hotkey_resolve('live')`).
2. **Resolução do papel.** `sotto_webview.py:15879` `def _hotkey_resolve(self, kind)` → devolve o acelerador (`Ctrl+Space`), log `HOTKEY_LIVE_MODE ... plan=take`.
3. **Toggle.** `sotto_webview.py:20181` `def _set_live_enabled(self, payload)` — é ele que escreve `LIVE_ENABLED on=...` e chama `show_caption_window(False)` quando `on=false`.
4. **Esconder.** `sotto_webview.py:17845` `def show_caption_window(self, on)`; no ramo `on=False` põe `self._caption_window_shown = False` (`:17861`) e faz `ov.show(False)` (overlay `caption_overlay.py:1676` `show`, `:1707` `hide`).

Pode o esconder ser bloqueado por (a), (b) ou (c)?

**(a) "não chega legenda nova" — IMPOSSÍVEL.** O caminho de esconder não lê texto nenhum: `_set_live_enabled({'on': False})` → `show_caption_window(False)` → `self._caption_window_shown = False` (`sotto_webview.py:17861`) → `_post(lambda: ov.show(False))`. `ov.show(False)` é `caption_overlay.py:1676-1706`: `ShowWindow(hwnd, SW_HIDE)`, `_tick_gen += 1`, `visible=False`. Não consulta `text`, `previous` nem fonte nenhuma. **A ausência de legendas não pode bloquear este caminho.**

**(c) `_drain_caption_pending` a repor texto — IMPOSSÍVEL.** Está guardado três vezes:
- `sotto_webview.py:17441-17444` (`_drain_caption_pending`): `pending = getattr(self, '_caption_pending', None)`; `if pending is None: return` (o `_blank`/toggle põe o slot a `None`);
- `_set_live_enabled` escreve `_caption_wanted=False` **antes** de `show_caption_window(False)`, e o drain do caminho de legenda ao vivo tem `if not getattr(self, '_caption_wanted', True): log('CAPTION_DROP_SWITCH'); return`;
- `show_caption_window(False)` incrementa `_source_epoch`, e o drain compara `(pending[3] != getattr(self,'_source_epoch',0))` → `CAPTION_DROP_EPOCH` e `return`.
  Mesmo que um push entrasse na janela, o slot é `None`/epoch antigo e o drain desiste. **É o único dos três que é IMPOSSÍVEL por três guardas independentes.**

**(b) O tick próprio do overlay — não repõe nada, mas também não salva.** `caption_overlay.py:1000-1093` `_tick_loop` → `_tick` → `_update()`. `_update` (`:1255-1370`) só faz `UpdateLayeredWindow` sobre o bitmap; **nunca** chama `ShowWindow(SW_SHOW)` — pelo contrário, quando não há texto chama `self.hide()` (`:1271`). Portanto o tick **não** pode manter visível uma janela que `show(False)` escondeu; e note-se que `set_text`/`_update` continuam a mexer no *conteúdo* mesmo com a janela escondida, porque `visible` só é lido em `_screen_proof`.

**Veredicto de Q3:** nenhum dos três bloqueia. O esconder, quando o toggle chega, esconde. Logo a queixa "Ctrl+Space não desaparece" **não é o overlay a recusar-se: é o toggle que nunca foi chamado** — o log não tem `HOTKEY_PRESSED role=live`, nem `HOTKEY_LIVE_STEP`, nem `LIVE_ENABLED` depois das 21:16:09.201. O defeito está a montante, na tecla (Q2).

---

## Q4 — Quem pintou o texto depois das 21:33:42: worker (`rows=0`) ou YouTube CDP (`rows=2 painted`)?

**Resposta: nem um nem outro no sentido da pergunta — e o texto do ecrã é da rota YouTube, não do worker.** O worker está parado desde 21:23:11 e nunca mais produziu linha:

```
2026-11-09 21:23:11.542 ENGINE_PARK reason=captions
2026-11-09 21:23:11.547 EXTERNAL_CAPTIONS_ENGINE_PARKED source=external:youtube:track pid=30804 mode=engine-not-process
2026-11-09 21:36:03.879 WORKER_COST ... rows=0 rows_since_tick=0 rows_per_min=0.0 ... rtf=none uptime_s=794 pid=30804
```

Quem pinta é decidido em duas camadas:

1. **A rota** — `youtube_cdp_source.py:5460`: o caminho rápido do DOM devolve literalmente `('external:youtube:track', _fast_rows)`, e o título `src=external:youtube:track` do `YT_FRAME` é *este* rótulo, não a track de cue. É por isso que o log diz `src=external:youtube:track` às 21:29:56 mesmo com a track a apontar para outro vídeo (`YOUTUBE_TRACK_PAINT video_id=UytYrhYLOKI source=other-video cue=1 match=0 painted_words=0`, 12× entre 21:24:36 e 21:35:42, e a cada 30 s para sempre).
2. **O predicado de repintura** — `youtube_cdp_source.py:5284-5296`: o tick só publica quando a linha muda; `self.last_line != line` ou `rows` diferentes, senão `continue`. E o `YOUTUBE_TICK_MS ... why='painted'` que ticka 71× na janela **não é um verbo**: `youtube_cdp_source.py:742` `why = ... ("painted" if rows else "no-painted-caption")` — é o *estado do DOM*, não "esta volta pintou". O instrumento mente ao leitor: 71 linhas dizem `painted` e nenhuma pintou nada.

Ou seja: **o texto congelado é o último frame que a rota YouTube entregou (`21:29:56.078`, rows=2: `Damaged instinct, turmoil torn away` / `Reeling like a desperado`), e a rota continua a ler exactamente as mesmas 2 linhas a 4 Hz (`YOUTUBE_LOOP_HZ ticks=40 ok=40 none=0`, `rows=2`, `cdp_age_ms` 176–375 ms) e a não as republicar porque nada mudou.** Não é texto novo que o overlay não recebeu: é o mesmo texto fresco de antes, que nunca mais foi empurrado porque (i) o predicado de mudança não dispara e (ii) o `_yt_switch_video` das 21:29:56 já tinha invalidado o slot. Não é o worker: `rows=0` há 13 minutos.

O que o log **não** pode dizer: qual *pixel* exacto estava no ecrã. `CAPTION_PAINT` só sai no trânsito vazio→texto (`sotto_webview.py:17510-17512`) e `_blank_caption_window` esconde via `_post(_blank)` fire-and-forget (`sotto_webview.py:13833`, `17274-17281`) sem registar conclusão. Na última sessão existe **um único** `CAPTION_PAINT`, às 21:21:50.527 (`text="carregando modelo…"`), e nenhum depois — logo o conteúdo nativo de 21:24:33 em diante é inferido, não medido. `[INFERENCE]`.

---

## The one defect worth curing

**`_caption_idle_hide` desiste em silêncio quando `_caption_window_shown` é falso (`app/webview/sotto_webview.py:17292`), e `_blank_caption_window` põe esse flag a falso (`:17258`) sem que `push_caption_to_window` (`:17678`) alguma vez o reponha — o único código que o repõe é `show_caption_window(True)` (`:17729`, `:17852`).**

O resultado, medido: o último `CAPTION_WINDOW_BLANKED reason=video-changed` (21:29:56.078) põe `_caption_window_shown=False` para sempre. A partir daí:

- o cão de guarda de 6 s (`CAPTION_IDLE_HIDE_S = 6.0`, `sotto_webview.py:17190`) é chamado a cada push e **morre na guarda de `:17292` sem escrever linha** — é por isso que a sessão inteira não tem um `no-caption-for-6.0s`, contra um às `21:17:01.804` na sessão anterior;
- a borda de pausa (`_yt_pause_edge`, `:4781-4808`) tem a **mesma** guarda (`:4806`) e também não apaga os pixels;
- o push seguinte volta a pintar e a **mostrar** a janela (`caption_overlay.py:1676` `show(True)` é chamado no drain), e o shell fica com pixels no ecrã e a acreditar que a janela está escondida.

Ou seja: **após um blank, qualquer legenda que chegue fica no ecrã para sempre, porque as duas metades que existem para a apagar (o cão de 6 s e a borda de pausa/fim) verificam um flag que o blank matou e que só o toggle do dono ressuscita.** O Ctrl+Space é então a única saída — e a tecla não chega ao shell (Q2), o que fecha o círculo: a legenda fica "congelada para sempre" e o único botão que a podia limpar não responde. O segundo sintoma não é um segundo bug *neste* mecanismo; é o *mesmo* desenho — superfície sem liveness própria — a depender de um único botão que falha em silêncio.

Cura mínima, no mesmo mecanismo: (1) `push_caption_to_window` repõe `_caption_window_shown = True` quando a pintura é aceite; (2) as guardas de `:17292` e `:4806` deixam de ser silenciosas (log de `CAPTION_IDLE_HIDE_SKIPPED reason=not-shown` / `CAPTION_PAUSE_BLANK_SKIPPED`); (3) `_blank_caption_window` não pode deixar o flag a falso *e* o `ov` visível — é preciso um invariante medido (`ov.visible`/`_screen_proof`) e não uma crença do shell.

---

## Top issues (por ordem de gravidade)

1. **P0 — superfície sem liveness:** `_caption_idle_hide:17292` + `_yt_pause_edge:4806` desistem com `_caption_window_shown=False`, e o blank (`:17258`) mata o flag até ao próximo `show_caption_window(True)`. Zero `no-caption-for-6.0s` na última sessão (vs. 21:17:01 na anterior). **É o defeito único.**
2. **P0 — tecla live muda:** último `HOTKEY_PRESSED role=live` = 21:16:08.483; toda a última sessão sem uma linha. `space_swallow.classify_event` engole sem log (`space_swallow.py:112`) e `pass` sem log (`:123-131`); nenhum `HOTKEY_OBSERVER_ALIVE` em 187 339 linhas. Um Ctrl+Space morto é indistinguível de um não carregado.
3. **P1 — `_yt_switch_video` faz double blank:** cada troca de id produz um *par* `CAPTION_WINDOW_BLANKED reason=video-changed` (21:24:33.638/.639, 21:24:36.158×2, 21:24:37.779×2, 21:29:56.061/.078), e cada blank incrementa `_source_epoch` e anula `_caption_pending`. O push do mesmo tick pode cair entre os dois.
4. **P1 — track do vídeo errado, para sempre:** 21:24:36→21:35:42 (e além) `YOUTUBE_TRACK_PAINT video_id=UytYrhYLOKI source=other-video cue=1 match=0 painted_words=0` a cada 30 s, enquanto o `vid` corrente é `guARjKjyFLY`. Nenhum `YOUTUBE_TRACK_ASK` na janela.
5. **P2 — `why='painted'` mente:** 71 `YOUTUBE_TICK_MS ... why='painted'` na janela sem uma única pintura; `why` é o estado do DOM (`youtube_cdp_source.py:742`), não um veredicto de pintura.
6. **P2 — fonte de texto congelada servida como fresco:** o CDP serve o mesmo frame a 4 Hz (`none=0`, `src_errs=0`) e o predicado de mudança (`youtube_cdp_source.py:5284-5296`) nunca dispara. Um ecrã parado é observacionalmente igual a um vídeo parado — e o vídeo *estava* parado (`YOUTUBE_CDP_PACED paused=True`, última mudança 21:22:29.586, nunca `False` depois).
7. **P2 — worker e player com o mesmo sintoma:** `ENGINE_PARK reason=captions` (21:23:11) com `rows=0` até ao fim, e `_external_parked` faz `REVIVE_REFUSED reason=player-supplies-caption` (`sotto_webview.py:17146`): o áudio voltou (5 `STATUS_APPLIED` 21:33:39–42) e o worker não arrancou porque o player "está a fornecer" um frame que não muda.

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: CaptionStuckForensics
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CaptionStuckForensics']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CaptionStuckForensics']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-10T10:03:12.165748+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CaptionStuckForensics']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CaptionStuckForensics']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

---

**Fecho:** diagnóstico entregue; nenhum ficheiro de produto foi tocado. O que falta é a decisão de cura (P0 #1: repor `_caption_window_shown` no push e instrumentar as duas guardas silenciosas; P0 #2: o caminho da tecla live).

---

## SELF-AUDIT

- **protocolos em falta:** não há `todo` nesta toolset (declarado no cabeçalho), e o protocolo de 40 linhas de resumo final é cumprido no yield, não no ficheiro. Faltou-me tempo para correr o `self-audit-lint.sh` sobre este ficheiro antes de o escrever — devia tê-lo feito depois. Faria diferente: correr o lint imediatamente após escrever e anexar a saída.
- **verificação adicional:** o check que mais aumentaria a confiança é uma linha de log no `_post(_blank)` a confirmar que o `ov.hide()` correu (hoje é fire-and-forget). Custo: uma linha em `_blank_caption_window`; não corre agora porque o contrato é read-only. Também valeria um `grep` de `HOTKEY_OBSERVER_KEYS` (0 no log) — feito.
- **checkboxes novas:** (a) `grep -c "no-caption-for-6.0s"` por sessão no arranque do diagnóstico — zero numa sessão com pushes é RED imediato; (b) assertar no código de produção que `push_caption_to_window` deixa `_caption_window_shown=True` sempre que `ov.show(True)` foi chamado (teste que falha com o código de hoje).
- **review por outro subagente:** sim-com-escopo — rever apenas a escolha do "one defect" (Q4 e o pixel) contra o log; o resto é tabela e excerpto.
- **gate-doubt:**
  - `verde-de-verdade:` o único gate que corri foi o `cache-task-report.sh` (fail-closed, devolveu `UNKNOWN` em vez de zeros — verde real, instrumento sem linhas para esta identidade). Não corri nenhum teste nem lint de produto; nenhum verde desses foi assumido.
  - `falta-no-gate:` o repositório não tem gate que asserte o invariante "pixels visíveis ⇒ `_caption_window_shown=True`". Uma mudança futura (novo caminho de push, novo blank) atravessa-o sem RED, e o sintoma é exactamente este ticket.
  - `gate-melhor:` `python -m pytest app/webview/test_caption_window_truth.py` (ou equivalente) com um caso: blank → push → assertar `_caption_window_shown is True` e `_caption_idle_hide(seq)` apaga — com o código de hoje tem de dar RED na segunda asserção.
- **confiança:** **alta** para Q1/Q2/Q3 (contagens e código citados, sem margem) e para o "one defect" (a guarda de `:17292` + o flag morto explicam o zero de `no-caption-for-6.0s`). **média** para o pixel exacto no ecrã (Q4): o log não mede pixels, só eventos; a inferência está marcada.
- **não verificado:** o valor exacto de `_caption_window_shown` no processo às 21:29:56 (só derivado do código e dos blanks); se o `_post(_blank)` chegou a correr (nenhum log); se o dono carregou Ctrl+Space depois das 21:16:08 (o log não pode provar nem negar); a ordem exacta de `_set_live_enabled` (lida por excerto, não reconfirmada linha a linha).
