# RECIBO — a legenda "ao vivo" com o video parado (2026-11-08)

O dono, verbatim:

> "comportamento esquisito ... quando eu deixo o video pausado, a legenda fica ao vivo,
> quando eu pauso, ela volta e fica travada em outro momento. a relacionada ao youtube"

**Estado: `fixed`, NAO `verified`.** O autor nao e' o verificador. O passo de replay/verificacao
independente deste recibo nao foi corrido por mim (ver §9 e §11).

---

## 0. PASSO 0 — a instância viva nao julga nada disto

```
$ python _main/live-code-freshness-oracle.py --strict
LIVE_CODE STALE pid=55104 started=2026-11-08 13:38:36, processo sha256=1C4A7E1DAE1C
                     vs disco FD56234EEB84 (files=101)
```

`STALE`. Pela letra do `docs/bug-hunt.md` (PASSO 0) a primeira accao seria reiniciar a app —
**nao foi feita por mim de proposito**: uma lane nao poe a app no ecra do dono. Tudo o que este
recibo afirma sobre o processo vivo vem do **log** que essa instancia escreveu
(`_main/webview-run.log`, 17:33-17:54), nao de a ter observado a correr. **O dono tem de
reiniciar** para a cura entrar em vigor; ate' la' o comportamento dele e' o de antes.

---

## 1. Cluster e impacto

| campo | valor |
|---|---|
| cluster | o estado publicado do player (`paused`/`ended`/`currentTime`/`playbackRate`) alimenta o relogio da legenda (`youtube_clock`) |
| impacto | com o video PARADO a legenda continua a revelar palavras ("fica ao vivo"); com o video A TOCAR ela congela ou salta para outro instante ("travada em outro momento"). Uma pausa falsa tambem dispara a BORDA que forca uma pintura congelada (`_yt_pause_epoch`) |
| onde | `app/webview/sotto_webview.py`, `_yt_cdp_snapshot` — **o unico sitio que publica esse estado** |

Nao e' um defeito de tolerancia: `youtube_clock.instant` faz exactamente o que promete (arm A4
passa: PAUSED nao anda um milissegundo). E' o estado que chega errado.

## 2. Observado vs esperado

* **esperado**: o `paused`/`ended`/`currentTime` que decide a legenda pertence ao video que a
  app esta' a servir (`self.yt_video_id`).
* **observado**: pertence ao video que a FONTE CDP escolheu — que pode ser outra aba, outro
  video, outro instante.

## 3. Reproducao (evidencia num ficheiro)

`_main/fixtures/yt-pause-foreign-state-20261108.txt` — linhas **verbatim** de
`_main/webview-run.log`, recortadas por numero de linha, com o cabecalho a dizer o que cada
bloco prova. O que decide:

```
17:33:35.251 YOUTUBE_VIDEO_CHANGED video_id=KoXXVCFjbk8
17:33:36.455 YOUTUBE_TICK_MS ... vid='pW2ktrJlsyE' cdp_age_ms=62 rows=0 why='painted'
17:33:38.526 YOUTUBE_CDP_PACED paused=True  poll_s=0.50        <- a pausa de pW2ktrJlsyE
17:34:05.583 YOUTUBE_CDP_PACED paused=False poll_s=0.08
17:34:06.174 YOUTUBE_CDP_PACED paused=True  poll_s=0.50
17:34:07.621 YOUTUBE_CDP_PACED paused=False poll_s=0.08
17:34:08.476 YOUTUBE_CDP_PACED paused=True  poll_s=0.50
17:34:11.477 YOUTUBE_CDP_PACED paused=False poll_s=0.08
17:34:07.287 YOUTUBE_CLOCK_HELD t=2.60 served=6.56 floor=6.56
17:34:11.032 YOUTUBE_CLOCK_HELD t=0.00 served=6.56 floor=6.56 <- o relogio da OUTRA aba
```

Tres factos, cada um medido:

1. `YOUTUBE_TICK_MS ... vid=` e' `_yt_diag['vid']`, escrito do **proprio snapshot**
   (`sotto_webview.py:_yt_diag`, campo `vid`). Ele diz `pW2ktrJlsyE` enquanto o video servido e'
   `KoXXVCFjbk8`: a foto e' de outro video.
2. O `paused` alterna **6 vezes em 12 s** sem um unico `YOUTUBE_VIDEO_CHANGED` e sem o dono
   tocar em nada disso: o que alterna e' a pausa da outra aba (a fonte oscila entre alvos).
3. `YOUTUBE_CLOCK_HELD t=0.00` — o `currentTime` publicado e' o **desta** aba (0 s) enquanto o
   `served` (o nosso chao) esta' em 6,56 s. E' o salto para "outro momento".

O segundo bloco (`17:35:04`-`17:50:38`, 15 min) mostra o mesmo com `d7p7l07iMc8`: `paused=True`
publicado durante 15 minutos seguidos enquanto o video servido era `ALAgHtf00oo`, e a legenda
desse video saiu uma vez e ficou parada (`YT_FRAME 'I got the ramp'` as 17:38:40 e 17:38:58).

## 4. As cinco hipoteses, e o que as refutaria

| # | hipotese | falsificador | veredicto |
|---|---|---|---|
| H1 | o estado publicado (`paused`/`ended`/`clock`/`rate`/`_yt_pause_epoch`) pertence ao snapshot, nao ao video servido — `_yt_cdp_snapshot` publica ANTES de olhar para `snap['videoId']` | num instante com `vid=` != video servido, `YOUTUBE_CDP_PACED` nao podia mudar e `YOUTUBE_CLOCK_HELD t=` tinha de bater com o NOSSO relogio | **CONFIRMADA** (§3: muda, e `t=0.00` com `served=6.56`) |
| H2 | `youtube_clock.instant` ainda extrapola com `state == PAUSED` | arm A4 do stutter-caption/`sample_instant(PAUSED)` devolver != base | refutada: A4 PASS (`advance=0.000 s`) |
| H3 | o `_PlayerCue` do overlay avanca sozinho e faz o texto crescer com o video parado | `freeze_rows` tira o relogio de palavra (`words=[]`, `end=None`), portanto o texto nao pode crescer com `t` | refutada: o payload congelado e' funcao do texto, nao de `t` (`youtube_cdp_source.freeze_rows:479-506`) |
| H4 | o chao monotonico (`youtube_monotonic.decide`) e' que prende a legenda | aparecer `YOUTUBE_CLOCK_HELD` com um relogio CORRECTO e o chao preso | refutada: o `t` da propria linha e' que esta' errado (`t=0.00`) |
| H5 | a cache de 1,2 s devolve foto velha do video CERTO, e so' a pausa chega tarde | a cache explica no maximo 1,2 s; `paused=True` durou 15 min | refutada como causa (contribui so' para `cdp_age_ms`) |

**A que ficou, e a medicao que decidiu**: H1, decidida por `YOUTUBE_TICK_MS vid='pW2ktrJlsyE'`
em simultaneo com `YOUTUBE_VIDEO_CHANGED video_id=KoXXVCFjbk8` **e**
`YOUTUBE_CLOCK_HELD t=0.00 served=6.56`. Um valor de pausa/relogio que nao e' do video servido
explica as duas metades da frase do dono com uma so causa.

## 5. Minimizacao

`_main/stutter-caption-oracle.py`, `foreign_state_arm` (linha 316): o menor estado que reproduz —
uma fonte falsa que devolve a foto de OUTRO video, as bandeiras publicadas pelo snapshot REAL, e
uma leitura do relogio. Sem Chrome, sem CDP, sem track: 2 chamadas.

```
B1  a NOSSA aba PARADA em 42,0 s + foto da OUTRA a tocar em 7,0 s
    ANTES: t=8.00  (a legenda anda com o video parado E no instante do outro)
    DEPOIS: t=42.00
B2  a NOSSA aba a TOCAR em 42,0 s + foto da OUTRA parada em 7,0 s
    ANTES: t=7.00, epoch=1, paused=True  (salta para o outro instante e dispara a borda)
    DEPOIS: t=43.00, epoch=0, paused=False
```

## 6. A cura — a CLASSE, no sitio que decide

`app/webview/sotto_webview.py:4455` (`_yt_cdp_snapshot`), **um** sitio, porque e' o unico que
escreve `yt_cdp_clock`/`yt_cdp_rate`/`yt_cdp_paused`/`yt_cdp_ended`/`yt_cdp_playing`/
`_yt_pause_epoch`/`_yt_was_paused`/`shell.yt_source_paused`.

**Antes** (`4455-4497` publicavam; `4498-4521` so' depois recusavam a foto):

```python
if snap is not None:
    self.yt_cdp_clock = (float(snap.get('t')), time.monotonic()) ...   # 4460
    self.yt_cdp_paused = ...                                            # 4476
    self.yt_cdp_playing = ...                                           # 4481
    if _now_paused and not _yt_was_paused: self._yt_pause_epoch += 1    # 4489
    shell.yt_source_paused = self.yt_cdp_paused                         # 4497
if snap is None or not snap.get('items'): return None                   # 4498
seen = snap.get('videoId') or ''                                        # 4500
if declared and seen and declared != seen: ...                          # 4501
```

Recusar a foto **depois** nao desfaz o que ja' foi publicado — e o caminho de fuga
(`seen == _selected`, o que acontece no log do dono) nem sequer a recusa.

**Depois** (`4471-4514`), a identidade decide ANTES de publicar:

```python
seen = str(snap.get('videoId') or '')                                   # 4471
if not (declared and seen and seen != declared):                        # 4472
    self.yt_cdp_clock = ...                                             # 4477
    self.yt_cdp_paused = ...  / _yt_pause_epoch ... / shell.yt_source_paused ...
if snap is None or not snap.get('items'): return None                   # 4515
if declared and seen and declared != seen: ...                          # 4517
```

A fuga `seen == _selected` continua a existir para o que ela foi escrita — as **linhas** do video
novo chegarem antes do rebind (~80 ms). O **relogio** e a **pausa** nao tem essa desculpa: ou sao
deste video, ou nao se publicam, e a ultima amostra nossa envelhece pelo caminho normal que
`youtube_clock` ja' tem (`FRESH_S` / `HOLD_S` / `UNKNOWN`).

**Tradeoff nomeado**: quando a fonte esta' presa noutra aba, o nosso relogio passa a extrapolar a
partir da ULTIMA amostra nossa e, esgotado o `HOLD_S` (8 s), cai para a UIA — em vez de usar (errado)
o relogio da outra aba. 8 s de deriva tolerada e' o contrato que A1/A2 ja' medem; usar o relogio
alheio nao era tolerancia, era outro video.

## 7. Regressao (estilo `stateful`) e a prova do detector

Estilo: **stateful** — o mesmo objecto, duas sequencias de estados publicados. Adicionada ao
oraculo que ja' e' dono desta superficie (`_main/stutter-caption-oracle.py`), nao a um quarto:

* `foreign_state_arm` (`:316`), `FakeSource` (`:272`), arms **B1/B2** (`:573-587`).
* `build()` passou a extrair `_yt_cdp_snapshot` (`:260`) e a fornecer `os`/`_yt_mark` (`:262-265`).
  Se a extracao falhar, `main` diz `NO-VERDICT` — um passo saltado nunca e' um passo passado.

```
$ python _main/stutter-caption-oracle.py
...
PASS B1 a NOSSA aba esta' parada: a foto da OUTRA (a tocar) nao move a nossa legenda
PASS B2 a NOSSA aba toca: a foto da OUTRA (parada) nao congela nem salta a nossa
PASS B2 e a pausa da OUTRA aba nao dispara a BORDA que congela a pintura
STUTTER-CAPTION GREEN -- arms=17 pass=17 fail=0 (rc=0)
```

**O detector tem dentes, com o codigo de ANTES numa COPIA** (`--neg-arm`, mutante **M3** =
`if not (declared and seen and seen != declared):` -> `if True:`; `:689-692`):

```
$ python _main/stutter-caption-oracle.py --neg-arm        (rc=1 = RED como desenhado)
NEG-ARM M3 estado publicado de OUTRO video: B1(andou para t=8.00 com a NOSSA aba parada),
                                            B2(t=7.00 em vez de 43.00),
                                            B2(borda falsa epoch=1 paused=True)
NEG-ARM PASS -- RED as designed:
  M1: A1(erro=2.31s), A3 texto mudo 2.66s ..., A4(andou=0.40s, mudancas=0), A5(andou=0.40s), ...
  M2: A1(erro=2.99s), A3 texto mudo 2.66s ..., A2(erro=4.99s), A3 texto mudo 4.66s ...
  M3: B1(andou para t=8.00 com a NOSSA aba parada), B2(t=7.00 em vez de 43.00),
      B2(borda falsa epoch=1 paused=True)
```

M3 e' exactamente o codigo pre-cura: **as arms B1/B2 so' ficam verdes com a cura**. Os mutantes
M1/M2 (2026-11-07) continuam apanhados, portanto o braco negativo nao perdeu nada.

## 8. Cobertura por invocador

Publicador: **1** — `_yt_cdp_snapshot` (`sotto_webview.py:4380`, a publicacao condicionada em
`4471-4472`), que escreve os 8 campos.

| consumidor | positivo | negativo |
|---|---|---|
| `youtube_clock.sample_instant` via `_youtube_time` | B1/B2 (relogio directo) | M3 |
| `youtube_clock.instant` via `yt_live_frame` | A4/A5/A6 | M1/M2 |
| `_yt_cue_payload` (`paused`/`freeze_rows`) | arm `pausa-corta-a-pintura` de `youtube-cdp-source-oracle` (19/19 PASS) | idem (mutantes do proprio oraculo) |
| `_tick` (`player_stalled`, `pause_edge`) | B2 (`epoch`) | M3 (borda falsa) |
| `poll_step` (cadencia) | `_main/paused-pace-oracle.py` — **8/8 PASS** | `--neg-arm` — **rc=1, 2 arms RED** |

Todos os invocadores enumerados tem positivo **e** negativo. O `poll_step` ja' tinha o seu proprio
oraculo (`_main/paused-pace-oracle.py`, passo `paused-pace` + `red-as-expected-paused-pace` no
`_audit-verify-all.cmd`), e ele passou depois da cura: uma cadencia mais lenta por uma pausa alheia
deixou de ser possivel porque a bandeira que ele le deixou de ser a da outra aba.

## 9. Replay, e quem verifica

| instrumento | resultado |
|---|---|
| `_main/stutter-caption-oracle.py` | **GREEN, arms=17 pass=17** (era 14; +3 B) |
| `_main/stutter-caption-oracle.py --neg-arm` | **rc=1, M1+M2+M3 RED como desenhado** |
| `_main/youtube-monotonic-oracle.py` | GREEN 14/0 |
| `_main/reveal-park-oracle.py` | GREEN 5/5 |
| `_main/youtube-hidden-clock-oracle.py` | GREEN 12/0 |
| `_main/youtube-rate-oracle.py` | PASS 7/7 |
| `_main/youtube-foreign-paint-oracle.py` | PASS |
| `_main/youtube-track-wiring-oracle.py` | PASS 12/12, mutants 5/5 |
| `_main/youtube-cdp-source-oracle.py` | PASS 19/19 (a `abas-em-paralelo` e' de TEMPO: falhou uma vez com a maquina a correr 8 oraculos em serie e passou sozinha, `seq=1.20s par=0.33s`) |
| `_main/paused-pace-oracle.py` | PASS 8/8 |
| `_main/paused-pace-oracle.py --neg-arm` | rc=1, `NEG-ARM PASS -- 2 arm(s) RED, A2 entre elas=True` |
| `_main/code-health-oracle.py` | **RED — causado POR ESTA CURA**: `sotto_webview.py` `bytes piorou de 1202290 para 1203644`, `lines piorou de 22780 para 22796`. O oraculo nao tem escape de "crescimento declarado" (`compare()`: qualquer metrica acima do baseline e' RED); absorver exige `python _main/code-health-oracle.py --update`, que o proprio ficheiro marca "so com o dono de acordo" e que eu NAO toco por instruccao. **Main tem de decidir** (§10) |
| `_main/youtube-sync-oracle.py` | **RED 3.5 — PRE-EXISTENTE e de OUTRA lane**: exige `youtube_reveal.window_by_paint(` no shell e o ramo `painted` deixou de o usar de proposito (`sotto_webview.py:5282`, comentario de 2026-11-02). Nao e' meu, nao o toquei |

**Veredicto honesto: `fixed`, nao `verified`.** Falta (a) o dono reiniciar a app para a instancia
passar a correr este codigo (`PASSO 0` continua `STALE`), e (b) um verificador != autor a repetir
§3/§7 no log NOVO. O que eu exercitei: as funcoes reais extraidas por AST do ficheiro que
embarca, num cenario sintetico — nao o processo.

## 10. O que Main tem de landar no `_audit-verify-all.cmd`

**Nenhum passo novo.** O par que ja' existe cobre as arms novas, porque elas vivem dentro do
mesmo oraculo (o `_audit-verify-all.cmd:1774-1781`, `stutter-caption` + `red-as-expected-stutter-
caption`, ambos `always`). O que muda e' o TEXTO do comentario/contagem: de `14 arms` para
`17 arms` (3 novas B1/B2/B2-borda), e o `--neg-arm` passa a exigir **tres** mutantes (M1/M2/M3) —
a string procurada continua a ser `NEG-ARM PASS`, portanto o `:expectred` nao muda.

`AGENTS.md` (que eu NAO toco) tem `:787-791` a dizer "14 arms": a linha honesta passa a
"o oraculo fecha **17** arms e o `--neg-arm` repoe os dois tectos **e o `_yt_cdp_snapshot` de
antes de 2026-11-08** em COPIA, exigindo A1-A5 + B1/B2 vermelhas".

### 10b. Duas coisas que o `code-health` exige de quem landa, nao de mim

1. `python _main/code-health-oracle.py --update` — a cura custa **+1354 B / +16 linhas** em
   `app/webview/sotto_webview.py` (1202290 -> 1203644 B, 22780 -> 22796 linhas; o codigo e' uma
   guarda + indentacao, o resto e' o comentario que explica a classe). O oraculo esta' **RED** por
   isso e so' o baseline o absorve; o proprio ficheiro diz "so com o dono de acordo".
2. A declaracao em `AGENTS.md`, no molde do que ja' la' esta' para outros crescimentos
   ("`code-health` absorve o crescimento declarado de `panel.js`/`hotkey_gesture.py`/
   `sotto_webview.py`/..."): acrescentar que o estado publicado passou a ser filtrado por
   `videoId` e que o custo medido e' o do ponto 1.

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: YtPauseClock
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['YtPauseClock']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['YtPauseClock']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-08T21:13:29.174475+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['YtPauseClock']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['YtPauseClock']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

O relatorio foi corrido com a minha identidade (`YtPauseClock`) e **nao** com um ficheiro de
transcricao: `bash I:/!manager/scripts/cache-task-report.sh YtPauseClock`. O resolvedor diz
`KEY-ABSENT` — 0 das 105 775 linhas do ledger carregam esta identidade — portanto cada campo sai
`UNKNOWN` (o instrumento e' fail-closed e nao imprime zero). O transcript desta sessao nao vive
num `.jsonl` de agente nesta maquina, vive na `history.db` do harness; nao inventei numeros.

## SELF-AUDIT

Verificado por maquina: `bash I:/!manager/scripts/self-audit-lint.sh
_main/receipt-20261108-yt-pause-clock.md` -> `SELF-AUDIT-LINT: inspected=1 violations=0
no-verdict=0` / `SELF_AUDIT_CLEAN` (rc=0). Nao existe `_main/self-audit-lint.py` nesta arvore.

**protocolos em falta** — corri os oraculos vizinhos **depois** da cura, nao antes: o `docs/bug-hunt.md`
manda correr os instrumentos existentes ANTES de mexer para saber o que ja' era verde. Consequencia
real: nao sei dizer se `youtube-sync-oracle` 3.5 ja' estava vermelho antes de eu tocar em nada —
provei-o por leitura do fonte (`sotto_webview.py:5282`, mudanca de outra lane) em vez de por medida
anterior. Faria a baseline primeiro numa proxima.

**segunda falta, e e' de ferramenta** — renomeei a evidencia (`.log` -> `.txt`, porque `*.log` esta'
no `.gitignore:29` e a prova nao viajaria num commit) e corrigi as tres referencias com `sed -i`
em vez da ferramenta de edicao. O resultado esta' certo, o *caminho* nao: a regra e' edicao por
ferramenta de edicao, e uma substituicao de string em tres ficheiros nao e' excepcao.

**verificacao adicional** — a que teria levantado a confianca e nao e' barata: correr
`_main/caption-frame-audit.py` sobre um `webview-run.log` NOVO com o dono a pausar, para ver
`YOUTUBE_CDP_PACED` (agora) coincidir com `YOUTUBE_VIDEO_CHANGED`. Custa a app reiniciada e um
lapso de uso do dono — nao e' meu para pagar.

**checkboxes novas** — mecanica, para esta classe: em `_yt_cdp_snapshot`, a assercao
"todo o campo escrito ANTES de um `return None`/recusa e' do video declarado". Como comando:
`python _main/stutter-caption-oracle.py --neg-arm` ja' e' a versao executavel (M3 falha se a
publicacao voltar a ser incondicional); a versao *estrutural* seria um lint que recuse escrita de
`self.yt_cdp_*` antes da primeira comparacao com `snap['videoId']` na mesma funcao.

**review por outro subagente** — `sim-com-escopo: repetir §3 (log) e §7 (--neg-arm) numa sessao
propria, e decidir se `_main/fixtures/yt-pause-foreign-state-20261108.txt` e' evidencia suficiente
ou se quer o `webview-run.log` inteiro`.

**gate-doubt** —
* `verde-de-verdade:` `STUTTER-CAPTION GREEN arms=17` — nao passa por construcao: as arms
  comparam com o relogio GRAVADO do player (`yt-paint-freeze-20261104.json`, 745 amostras reais),
  nao com a nossa propria formula. `--neg-arm` corre sobre COPIA do shell (string trocada) e M3
  imprime tres RED distintos; se a string nao existir, o braco imprime `NAO MUTOU` e devolve `[]`
  (ou seja: `NEG-ARM FAIL`), portanto nao ha' verde vacuoso por mutacao falhada. Uma ressalva
  REAL: no braco M1 as arms B1/B2 tambem ficam vermelhas (por causa do tecto de 0,5 s), portanto
  elas nao sao *especificas* de M3 — sao-no pelo `B2(borda falsa epoch=1)`, que so' M3 produz.
  Segunda metade, e a que doeu: o `code-health` **nao** esta' verde — esta' RED por causa desta
  cura (`+1354 B / +16 linhas` em `sotto_webview.py`). O RED e' real e nao vacuoso: o comparador
  e' `b > a` contra um baseline medido, sem flag de escape. Nao o escondi nem toquei no baseline;
  esta' em §9 e §10b como trabalho de quem landa.
* `falta-no-gate:` a cadencia (`poll_step`) NAO e' buraco: `_main/paused-pace-oracle.py` mede-a
  8/8 e o `--neg-arm` devolve rc=1 com 2 arms RED (corri os dois hoje). O buraco real e' o TEMPO:
  nenhuma arm mede o caminho em que a fonte fica presa noutra aba durante MINUTOS — a arm B1/B2
  mede uma foto, nao a sequencia "a fonte troca de aba e nunca volta". Cenario que anda por este
  buraco: um `yt_cdp_playing` congelado em `True` porque a ultima foto NOSSA foi ha' minutos — a
  cura deixa-o envelhecer ate' `HOLD_S` e cair para a UIA, mas nenhuma arm mede esse limite.
* `gate-melhor:` acrescentar a B3 — 60 iteracoes em que a fonte devolve SEMPRE a foto da outra
  aba enquanto o relogio de parede anda 10 s — e exigir que o `t` servido nunca exceda
  `42.0 + HOLD_S` nem volte atras. Fica RED hoje se `HOLD_S` for removido de `instant`, e fica RED
  no M3 (que serviria o relogio alheio). Comando: `python _main/stutter-caption-oracle.py`
  (arm dentro do mesmo ficheiro, mesmo `--neg-arm`).

**confianca** — `alta` na causa (log do dono, dois blocos independentes, mecanismo unico e
localizado); `media` no fecho, porque a instancia que ele corre e' STALE e nao houve verificador.

**nao verificado** — (1) a instancia viva depois de reiniciada; (2) um `webview-run.log` novo com
`YOUTUBE_CDP_PACED` a coincidir com o video servido; (3) `youtube-sync-oracle` 3.5 antes da minha
edicao (julgo-o pre-existente por leitura, nao por medida); (4) `poll_step` com arm propria;
(5) o overlay nativo num ecra real com o video parado.
