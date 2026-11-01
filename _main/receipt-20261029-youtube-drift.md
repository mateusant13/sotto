# receipt 20261029 — youtube drift oracle

Lane: `YoutubeDrift`. Deliverable: `_main/youtube-drift-oracle.py` (NEW file, no existing file modified).

## What it measures (printed by the tool itself)

- **REFERENCE** = the player's own payload `_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3`
  (sha256 `9806e76a435a8af8f8f6c98745579e5e14d08f57b6b85c23dc66286b461d67ab`): line start
  `tStartMs` + `tOffsetMs` of the segment holding the last word of the observed row.
- **OBSERVATION** = the player's live rows `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`
  (sha256 `b8c397e42d281a5d060388be62c84b29130f22a394c8e1d58b685737bb183adf`): `samples[].t`,
  `samples[].segs[].t` with `v` true, first sample in which the row is visible.
- `drift_ms = observado_ms - referencia_ms`, per row, signed. No boolean "synced" anywhere
  (`grep -c synced` below).

Mapping: the player re-draws the same line as it reveals words (`Have` → `Have you ever had`
→ full row), so each distinct visible text is one observation, word-aligned prefix-matched
into a payload line; the reference is the time of its **last** visible word. `>>` speaker
marker and whitespace normalised on both sides; `v:false` rows skipped.

**Sign semantics (honest):** with the formula the brief itself prescribes
(`observed - payload`), `drift_ms < 0` means **the player showed the row before its own payload
says**, therefore our payload-driven reveal is **LATE** by `|drift|`; `drift_ms > 0` means we are
EARLY. The brief's prose ("negative = we are EARLY") is inverted for that formula — reported, not
silently followed. The tool prints the convention it applies.

## Command 1 — positive arm

```
python _main/youtube-drift-oracle.py
EXIT=0
```

Output (verbatim body):

```
video            : WdaHAGRBB6s
REFERENCIA       : payload do player -- H:\sotto\_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3 (sha256 9806e76a435a8af8f8f6c98745579e5e14d08f57b6b85c23dc66286b461d67ab)
OBSERVACAO       : player ao vivo      -- H:\sotto\_main\fixtures\yt-WdaHAGRBB6s.live-compare-20261026.json (sha256 b8c397e42d281a5d060388be62c84b29130f22a394c8e1d58b685737bb183adf)
regra            : drift_ms = observado_ms - referencia_ms
referencia       : tStartMs da linha + tOffsetMs do segmento da ultima palavra observada
observacao       : samples[].t da PRIMEIRA amostra em que a linha aparece visivel
sinal            : drift_ms < 0 => o player mostrou ANTES do payload => a NOSSA
                   revelacao (que segue o payload) esta TARDE por |drift_ms|;
                   drift_ms > 0 => a nossa revelacao esta CEDO por drift_ms.
texto            : espaco normalizado e marcador de falante `>>` removido nos DOIS lados
amostras         : 16 | passo min/mediana/max = 637/656/849 ms (resolucao da medicao)
linhas do payload: 19 | observadas: 16 | com drift: 16 | NA: 0

MODO             : referencia do payload, sem desvio

linhas medidas (ordem de observacao):
  cue=1 row=Have drift_ms=+23 observed_ms=22.8 ref_ms=0.0
  cue=1 row=Have you ever had drift_ms=+132 observed_ms=772.3 ref_ms=640.0
  cue=1 row=Have you ever had to kill a man? drift_ms=+213 observed_ms=1412.6 ref_ms=1200.0
  cue=2 row=No. drift_ms=+179 observed_ms=2059.2 ref_ms=1880.0
  cue=3 row=Then drift_ms=+75 observed_ms=2714.8 ref_ms=2640.0
  cue=3 row=Then this sword drift_ms=+39 observed_ms=3358.6 ref_ms=3320.0
  cue=3 row=Then this sword is useless. drift_ms=+347 observed_ms=4027.2 ref_ms=3680.0
  cue=4 row=Don't drift_ms=+41 observed_ms=4681.3 ref_ms=4640.0
  cue=4 row=Don't worry about me, drift_ms=+131 observed_ms=5530.6 ref_ms=5400.0
  cue=4 row=Don't worry about me, Yamato. drift_ms=+704 observed_ms=6224.1 ref_ms=5520.0
  cue=4 row=Don't worry about me, Yamato. I'll be drift_ms=+244 observed_ms=6883.8 ref_ms=6640.0
  cue=5 row=fine. drift_ms=+84 observed_ms=6883.8 ref_ms=6800.0
  cue=6 row=After the ritual, drift_ms=+64 observed_ms=8264.3 ref_ms=8200.0
  cue=6 row=After the ritual, I'd drift_ms=+28 observed_ms=8907.6 ref_ms=8880.0
  cue=6 row=After the ritual, I'd love to train with drift_ms=+25 observed_ms=9544.8 ref_ms=9520.0
  cue=7 row=you sometime. drift_ms=+432 observed_ms=10192.1 ref_ms=9760.0

SUMMARY n=16 min_ms=+23 max_ms=+704 mean_ms=+172.5 median_ms=+107.2
payload nunca observado: 12/19 linhas (fora da janela das amostras): cues 8,9,10,11,12,13,14,15,16,17,18,19
CONVENCAO drift_ms negativo = player adiantado = a nossa revelacao TARDE

YOUTUBE-DRIFT VERDICT MEASURED (rc=0) -- n=16 mean_ms=+172.5 median_ms=+107.2
```

Measured drift is **positive on all 16 rows**: our payload-driven timeline fires **earlier**
than the player's wall clock in this capture (median +107 ms, mean +172 ms, max +704 ms).
The right-hand tail is bounded by the sampling resolution (median gap 656 ms): the first sample
that shows a row can lag its true paint by up to one sample period, so the max is
sampling-limited, not a claim about the app.

## Command 2 — negative arm (`--neg-arm`)

```
python _main/youtube-drift-oracle.py --neg-arm
EXIT=1
```

Body (the shifted report is printed first; tail is the verdict):

```
MODO             : ARM NEGATIVA: referencia do payload deslocada em +250 ms
...
SUMMARY n=16 min_ms=-227 max_ms=+454 mean_ms=-77.5 median_ms=-142.8
...
NEG-ARM: desvio injectado na referencia = +250 ms (payload tStartMs/tOffsetMs)
NEG-ARM: linhas comparadas nas duas medicoes = 16 | sem par = 0
NEG-ARM: mean_ms +172.5 -> -77.5 (delta -250.0 ms, esperado -250.0)
NEG-ARM: Have | sem desvio drift_ms=+23 | com desvio drift_ms=-227 (delta -250)
NEG-ARM: Have you ever had | sem desvio drift_ms=+132 | com desvio drift_ms=-118 (delta -250)
NEG-ARM: Have you ever had to kill a man? | sem desvio drift_ms=+213 | com desvio drift_ms=-37 (delta -250)
NEG-ARM PASS: o instrumento viu o desvio injectado de +250 ms em 16/16 linhas (cada drift_ms baixou exactamente -250 ms)
YOUTUBE-DRIFT VERDICT RED-BY-DESIGN (rc=1) -- a referencia foi deslocada em +250 ms e a medicao tem de falhar
```

Every one of the 16 drifts moved by exactly `-250 ms`; the arm names the offset and exits 1.

## Extra robustness runs (beyond acceptance, run here)

```
python _main/youtube-drift-oracle.py --fixture _main/fixtures/does-not-exist.json3
EXIT=2
MEDICAO AUSENTE: fixture ausente: _main/fixtures/does-not-exist.json3
YOUTUBE-DRIFT VERDICT NO-MEASURE (rc=2) -- ausencia de fixture nao e medicao
```

`drift_ms=NA` path, injecting a player row that exists in no payload line:

```
python _main/youtube-drift-oracle.py --live I:/cc-tmp/drift/live-bad.json
EXIT=0
  cue=NA row=zzz invented row drift_ms=NA reason=nenhuma linha do payload comeca por estas palavras
```

`python -m py_compile _main/youtube-drift-oracle.py` → `COMPILE_OK`.

No boolean sync claim: `grep -c '"synced"\|synced' _main/youtube-drift-oracle.py` → 0
(the word does not occur; every per-row line carries `drift_ms=<signed integer>`).

## Scope / ratchet

- Only new files: `_main/youtube-drift-oracle.py`, this receipt. No existing file touched
  (`git status --porcelain | grep -i drift` → `?? _main/youtube-drift-oracle.py` only).
- `python _main/code-health-oracle.py` → `CH_EXIT=2`, RED on `sotto_webview.py`,
  `youtube_captions.py`, `youtube_window.py`, `sotto_worker.py` — all pre-existing per the
  brief; `grep -c youtube-drift` in its report = 0, i.e. the new file is not in the ratchet.
- No window was opened; only `python` processes. No commit, no push.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: YoutubeDrift
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['YoutubeDrift']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['YoutubeDrift']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-10-29T08:33:38.037554+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['YoutubeDrift']; this task's identity matches no ledger row
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['YoutubeDrift']; this task's identity matches no ledger row
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — I followed the brief's formula verbatim but its one-line sign gloss
  contradicts that formula. I should have surfaced that conflict as a question to Main before
  shipping; instead I applied the formula and printed the derived (and correct) semantics. Fixed by
  documenting it in the tool banner and here; a short message to Main follows.
- **verificacao adicional** — Ran the two extra arms (missing fixture → rc=2, unmatched row →
  `drift_ms=NA`) and the compile check; these were cheap and are what turn "the tool runs" into
  "the tool has the branches the brief asked for". A deeper check (replaying every sample against
  the app's live window, not just the payload) is out of scope here and would need the app process.
- **checkboxes novas** — Add a mechanical assertion `python _main/youtube-drift-oracle.py --neg-arm
  >/dev/null; test $? -eq 1` plus `grep -qE 'drift_ms=[+-]?[0-9]+|drift_ms=NA'` on the positive
  output, so a future edit that replaces a number with an opinion ("synced") goes RED.
- **review por outro subagente** — `sim-com-escopo` — check only the row-matching rule
  (prefix match + last-word reference) against the payload, since that is the one judgement call.
- **gate-doubt** —
  - `verde-de-verdade:` the rc=0 run is real measurement, and it can go a different colour: the
    `--neg-arm` run of the same code path exits 1 with a named +250 ms offset (observed above),
    so the green is not pass-by-construction. `python -m py_compile` → `COMPILE_OK` is a real
    compile, not a cached artifact.
  - `falta-no-gate:` the oracle only covers the samples present in the fixture (0.02–10.19 s of a
    33.8 s payload); a change that breaks timing at 12 s–33 s passes this oracle untouched
    (12/19 payload lines never observed). Also nothing checks the app process itself — only the
    fixtures.
  - `gate-melhor:` mechanical: a capture with ≥1 sample inside every cue, then require
    `linhas do payload: N | observadas: N` (all payload cues observed) in the positive output;
    an input with a payload cue outside the sampled window keeps it RED (12/19 today).
- **confianca** — `alta` for the instrument and its negative arm; `media` for any statement about
  the app's true timing, because the fixture's 656 ms sampling grid bounds per-row resolution.
- **nao verificado** — the live app process end-to-end (never launched, per the owner's
  `SOTTO_NEVER_ON_OWNER_SCREEN` order); behaviour on videos other than `WdaHAGRBB6s`; the
  `youtube-reveal-oracle.py` RED (different lane, not touched).
