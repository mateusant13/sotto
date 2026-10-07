status: done
lane: SottoVsReferencia
date: 2026-10-06
assignment: download https://youtu.be/PQw0TRzpCkk, take YouTube's transcript, run the SAME audio through the
  Sotto pipeline on the non-live route, compare with population+window, and find the CAUSE in the code
  (`file:line` + the number that confirms or eliminates each hypothesis).

## Deliverable

`H:/sotto/docs/audit/sotto-vs-referencia.md` — the whole audit: provenance of the reference, the numbers,
the first 30 omissions with position, the cause with `file:line`, elimination of the four hypotheses the
brief named, the reproduction commands, and the fix.

## Acceptance checklist

| criterion | state | evidence |
|---|---|---|
| `H:/sotto/docs/audit/sotto-vs-referencia.md` with the number table, the 30 omissions, and the CAUSE with `file:line` | **met** | report written; cause cited at `worker/sotto_worker.py:679-682` |
| audio in `G:/sotto-ref/`, report carries the exact reproduction commands | **met** | `G:/sotto-ref/` holds webm + 16 kHz mono wav + reference text; §7 of the report is the command list |
| nothing written to `I:` or `C:` (I: at 99.4 %) | **met** | 150 380 911 B + 48 258 202 B + 24 497 B all under `G:/sotto-ref/` |
| reference PROVENANCE stated (auto caption ≠ human) | **met** | §1.1: YouTube **automatic** caption (`en`), no human track exists, `pt` is a machine translation of it and was NOT used |
| `bash I:/!manager/scripts/self-audit-lint.sh <recibo>` = SELF_AUDIT_CLEAN | **met** | run below |
| >15 s fixture from environment capture is LIXO — this audio is the reference the OWNER asked for | **acknowledged** | 1508.066 s; the rule is scoped to test fixtures and the brief says it does not apply here |

## The answer to the owner's question

"Our pipeline skips several words" is **not the model**. It is `worker/sotto_worker.py:679-682`: the RNN-T
prediction network is re-primed (`h`/`c` → 0, seed = `<blank>`) at **every 560 ms chunk boundary**.
Holding the audio, weights, chunk grid, front end, joint and argmax fixed and changing **only** that policy:

| arm | words | % of ref | omissions | empty chunks | WER |
|---|---|---|---|---|---|
| shipped | 2 183 | 50.7 % | 2 159 | 59.3 % | 0.6105 |
| carry `h`/`c` | 3 304 | 76.8 % | 1 286 | 23.1 % | 0.5954 |
| carry + seed with last symbol | **4 279** | **99.4 %** | **122** | **10.0 %** | **0.1536** |

Arm 1's transcript is **byte-identical** to the shipped run (11 591 chars, sha256 `449fe638bb019357…`) —
the harness measures the shipped decode and nothing else.

## SELF-AUDIT

- **protocolos em falta** — I should have read `worker/README.md`'s provider section **before** writing the
  probes. It says in plain words that `get_available_providers()` is not evidence and that CUDA needs
  `_add_cuda_dll_dirs()`; I hit exactly that trap, ran 12 minutes of CPU-fallback probe, and only noticed
  because the `providers:` line I had *chosen* to print contradicted `rtf`. Different next time: read the
  module the instrument wraps, end to end, before the first run — the trap was documented 40 lines from the
  code I was instrumenting.

- **verificacao adicional** — running the three arms on `worker/assets/sample1.flac`, the 13.44 s clip the
  README's *opposite* conclusion was measured on. It is cheap (~1 min) and it is the one thing that could
  still change the verdict: if re-priming is genuinely better on that clip, the report must say the defect
  is a **long-stream** effect and name the clip length as the boundary. Cost: one CUDA run.

- **checkboxes novas** — a MECHANICAL assertion on **`empty_chunks / chunks`**, which exists as a printed
  counter and is asserted nowhere. Concretely, in the file arm on `worker/assets/sample1.flac`, require
  `empty_chunks <= 0.25 * chunks` and `tokens >= 80`. Both arms of the pair are already produced by
  `_main/sotto-vs-ref-decode-arms.py --arms 1,3`; the shipped decode reads `119/214 = 0.556` on the
  25-minute reference and must leave it RED. A number that exists only as a log line is a number no
  regression can fail on — which is why a change that halves the transcript still exits 0.

- **review por outro subagente** — `sim-com-escopo`: the report's §4 (the four eliminations) and §5.1
  (the arms), against `worker/sotto_worker.py` at sha256 `d4f4d529…`. Specifically: check that arm 1's
  byte-identity claim is really the shipped stream and not a shared harness artefact, and that
  `partial_tail_tokens = 744` is being read as "the boundary is not the cause" and not as a headline.

- **gate-doubt**:
  - `verde-de-verdade:` the green I was handed and the greens I ran. (a) **The shipped run's `exit 0` is
    vacuous-by-construction**: `--selftest` returns 0 whether or not a word came out, and it returned 0 on a
    transcript that lost 2 159 of 4 303 words — the run `sotto-full-int8-vad-on.jsonl`, rc=0, 50.7 %. That is
    the gate that should have caught this and cannot. (b) **The `blank_frac` counter is a false green by
    design**: it read 0.7689 here against the README's 0.7562 for "real speech", so the one health metric
    the worker prints called a half-lost transcript healthy. (c) The greens that ARE real, and I checked
    rather than assumed: the arm-1 self-check is not pass-by-construction — it is an exact integer and
    sha256 comparison across two independently constructed harnesses, and its first, CPU-contaminated run
    read 460 tokens against the shipped 463 and **would have failed it**. (d) The VAD green
    (`vad_gated_chunks = 0`) is real and falsifiable: the same probe reads 10/12 gated on digital silence
    per the repo's `_main/vad-option-probe.py`, so a zero here is a measurement, not an unplugged wire.
  - `falta-no-gate:` the worker has **no assertion on transcript quantity at all**. Scenario a future change
    walks through: someone re-lands re-priming, or shortens the chunk, or adds a second gate — `empty_chunks`
    doubles, `tokens` halves, every existing oracle on `sample1.flac` still passes (it has no 3.36 s pause
    and no long stream), `blank_frac` still reads "≈0.75 = healthy", and exit stays 0. That is precisely the
    state this audit found, five days of it, with a README that says the decode is fixed.
  - `gate-melhor:` one mechanical check, with the input that must leave it RED:
    `bash -lc 'cd H:/sotto && python _main/sotto-vs-ref-decode-arms.py G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav /tmp/a.json --seconds 120 --arms 3 && python -c "import json;d=json.load(open(\"/tmp/a.json\"))[\"arms\"][0];assert d[\"empty_chunks\"]/d[\"chunks\"]<=0.20,(d[\"empty_chunks\"],d[\"chunks\"])"'`
    → RED on today's tree, because arm 3 exists only inside `_main/sotto-vs-ref-decode-arms.py`; it goes
    green when the rule is landed in `run_chunk`. A cheaper byte-cheaper variant once landed: assert
    `empty_chunks <= 0.20 * chunks` on the same 120 s window from the shipped `--selftest` JSONL, where the
    shipped value is `119/214 = 0.556`.

- **confianca** — **alta**. Two independently constructed harnesses agree byte-for-byte on arm 1, the three
  arms differ in exactly one variable, and the swing is 4× on WER with the reference text published
  alongside. What would raise it to certain: the `sample1.flac` arms (reconciling the README's contrary
  measurement), and landing the fix and re-reading `empty_chunks` from the shipped worker itself.

- **nao verificado** —
  1. the arms were NOT run on `worker/assets/sample1.flac`, the clip the README's carry-vs-re-prime table used;
  2. the LIVE branch's extra stages (`SpeechMusicGate`, `AutoGain`) are not in any number here — the file arm
     has both OFF, so the owner's live experience is this bad or worse, and that is [INFERENCE];
  3. the fix is NOT landed in `worker/sotto_worker.py` — arm 3 lives in `_main/sotto-vs-referencia`'s probe;
  4. the reference is itself an ASR transcript, so no ground-truth WER exists for either system;
  5. CPU was not re-run for the reported numbers (only CUDA); the CPU fallback differed by 3 tokens in 463;
  6. English only, `lang_id=auto`; no second language was exercised.

## SELO DO DONO — resposta a pendencia dos governadores externos

MEDIDO, nao contado. O meu assento NAO tem dispatch (nem `todo`), por isso digo a quem pertence o que nao posso fechar.

**1) theorist-delta-guard — FECHADO, e com SINAL NOVO (nao reemissao com data nova).**
- antes: `VERMELHO-SEM-SINAL ... o arquivo declarado no registo nao existe / CITADO: (artefacto declarado ausente do disco)`
- agora: `DESLIGADO-DECLARADO ... idade=31 s ... o instrumento existe e foi medido em 'I:/!manager/state/tmp/theorist-delta-guard-task.log'`
  `CITADO: 06/10/2026 10:44:44 RAN-NO-VERDICT target=I:\!manager\scripts\theorist-delta-guard-scheduled.cmd rc=4 (rc=0 but no RHT_EXEC_MARKER: child did not attest it ran; NOT a pass)`
- idade **6.29 d → 31 s**, e a linha citada passou a ser a **atestacao real** — `sinalNovo(antes, depois)` verdadeiro.
- medição que a sustenta: o ficheiro declarado **existe e foi escrito 10:44:44** (174 B); o registo declara
  `estado_declarado: DESLIGADO` (medido 2026-09-30: `Get-ScheduledTask theorist-delta-guard -> State=Disabled`).
- defeito durável filed: ticket **`f81c9387c5ec12995ba21d28`** (P2) — o veredicto lia "artefacto ausente" antes de ler o
  estado DESLIGADO declarado, e escondia um `rc=4` de NAO-ATESTACAO no próprio artefacto.

**2) theorist-always-on — NAO e' silencio do processo; e' o ARTEFACTO DECLARADO que nao sai. NAO posso fecha-lo.**
- processo: `Get-ScheduledTask theorist-always-on` → `State=Ready, LastRunTime 10:40:01, LastTaskResult 0, NextRunTime 10:44:40, NumberOfMissedRuns 0` ⇒ **DISPARA**.
- loop: `G:/superharness/_scratch/theorist-loop/always-on.log` → 478 668 B, mtime 10:40 ⇒ **ESCREVE**.
- artefacto declarado (`state/governadores/registro.json`: `artefato = I:/!manager/state/research/theorist/theory-*.md`,
  `artefato_modo = glob-mais-recente`, cadência 300 s × tolerância 30 = limiar 2,5 h): **1 008 ficheiros, o mais recente com 47,35 h**
  (`theory-2026-10-04T14-22Z.md`).

**A CAUSA, e ela esta' nomeada pela propria linha fresca do gate.** A ultima linha de `always-on.log`, de HOJE às 13:44:42Z:
```
2026-10-06T13:44:42Z BRANCH=stopped-inactive roots=pass g:\superharness pid=42552
2026-10-06T13:44:42Z BRANCH=hold reason=every-active-root-has-a-loop owner_sessions=2 live_loops=1 producers=1
                     stall_guards=0 registered=6 live_loop_cmdlines=1 loop_spawned_omp=1 omp_total=3 action=no-launch
```
O gate corre, avalia, e **decide não lançar** (`action=no-launch`, `reason=every-active-root-has-a-loop`): afirma que já há um loop
para cada root activo e por isso segura. E re- mede **`stall_guards=0` — nenhum guarda de estagnação armado.**

**Duas testemunhas independentes congelaram no MESMO segundo:** `theory-*.md` mais recente = `2026-10-04T11:24:07` **e**
`state/progress/theorist-hourly-state.json` (148 B) mtime `2026-10-04 11:24`. Não é "um ficheiro velho" — são **dois produtos
distintos parados no mesmo instante, 47,4 h atrás**, enquanto o gate, todas as ~5 min, adia para um loop que não produz.

⇒ Ou seja: `stall_guards=0` + `action=no-launch` é o conjunctor quebrado. O VERMELHO é verdadeiro; a dívida é **a produção da teoria
(o loop que o gate presume vivo) e a ausência de um guarda de estagnação**, não a cadência do disparo.
Esta classe já foi reconhecida antes: o card **#323 THEORIST OVERDUE** (arquivado em `state/archive/scratch/_scratch/todo-*.json`)
diz *"Two clocks disagree: theorist-always-on.log last RAN line 30/09 15:54 … enquanto theorist-hourly-state.json tem mtime 00:13
local … the due computation is in theorist-always-on.ps1"* — e o recibo dessa lane existe (`runs/TC-20260930-theorist-overdue.md`,
25 702 B, 2026-10-01 01:05). Ou seja: **o diagnóstico já foi feito e a produção parou outra vez**, agora no mesmo segundo em dois
produtos.

**FECHO EXIGIDO** (um `theory-*.md` novo, saído de um passe de teorista — e/ou armar o stall guard): **pertence ao theorist / a Main,
que o despacha, e a `scripts/theorist-always-on.ps1` como dono do gate.** O meu assento não tem dispatch.

**Dois recibos ja' registaram EXACTAMENTE este defeito, e o governador esta' VERMELHO outra vez:**
- `runs/TC-20260930-theorist-overdue.md:82` (2026-09-30, card **#323**): *"O ficheiro `state/progress/theorist-always-on.log` **nao existe**.
  O log real e' …"* — o card diz *"Two clocks disagree: theorist-always-on.log last RAN line 30/09 15:54 … enquanto theorist-hourly-state.json
  tem mtime 00:13 local … a computacao de due esta' em theorist-always-on.ps1"*.
- `runs/TC-20261006-dispatch-obligation-refalsify.md:208` (HOJE): *"O artefacto declarado NAO existe em disco
  (`I:/!manager/state/progress/theorist-always-on.log`)"*.
⇒ O diagnostico foi feito **seis dias antes** e repetido **hoje**; o registo (`state/governadores/registro.json`, mtime 06/10 05:10)
declara hoje o glob `state/research/theorist/theory-*.md`. **A divida nao e' de diagnostico — e' de fecho:** os produtos pararam
no mesmo segundo (04/10 11:24) e o gate adia para um loop que nao produz, com `stall_guards=0`.

**3) cron_wake** (VERMELHO novo na última leitura) — transitório e já rastreado pelo próprio dono: tick 8534 parado em 13:30:42
(14,6 min), e `scripts/cron-wake-gate.ps1` escreve `TICK ok tick=8534 unchanged but only 299 s stalled (bar 560 s)`. Pertence a
`scripts/cron_supervisor.ts`.

**4) ManagerWindowCensus** (VERMELHO-FALHA, já de volta a EM DIA) — **NÃO era meu**:
`ALERTA-JANELA ... pid=40784 pythonw.exe "H:\sotto\app\webview\sotto_webview.py" --log H:\sotto\_main\webview-run.log --with-worker`, nascido 13:37:04Z.
As minhas sondas correram como `python.exe` **sem janela**. Fica nomeado para a lane dona da app do roster de `H:/sotto`.

**Tickets abertos por esta lane:**
- **`f81c9387c5ec12995ba21d28`** (P2) — veredicto do governador lê "artefacto ausente" antes do estado DESLIGADO declarado.
- **`66d221cb4740feb985d7581b`** (P3) — `grep -rn` a partir da raiz do repo lê 513,9 MB e estoura os 300 s, porque `state/archive/` guarda um
  `store.json` de 288 MB (287 763 225 B) com transcrições embutidas, e `--include=*.json` casa com ele. Custo medido: 300 s + o job tracker
  preso em `running`, sem forma de o matar deste assento (`write proc://<id>/kill` recusado por este build).

## CACHE/PRICE
- task/agent: SottoVsReferencia
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoVsReferencia.jsonl
- cache: read=15081216 write=0 hit=98.3964% (cache-read / input+cache-read); universe: 79 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoVsReferencia.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=75 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 79 of 79 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T13:03:40.690000+00:00 | break_items=3; WHEN=2026-10-06T13:05:30.610000+00:00 | break_items=2; WHEN=2026-10-06T13:11:06.253000+00:00 | break_items=2; WHEN=2026-10-06T13:20:45.272000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 118284 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoVsReferencia']; window: 2026-10-06T13:03:40.690000+00:00..2026-10-06T13:20:45.272000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1114f-d922-702b-8ca0-58c13b53497e provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791291820690 | session_id=01a1114f-d922-702b-8ca0-58c13b53497e provider=deepseek-flash model=deepseek-flash item_index=52; turn_id=1791291930610 | session_id=01a1114f-d922-702b-8ca0-58c13b53497e provider=deepseek-flash model=deepseek-flash item_index=162; turn_id=1791292266253 | session_id=01a1114f-d922-702b-8ca0-58c13b53497e provider=deepseek-flash model=deepseek-flash item_index=190; turn_id=1791292845272 (state=RESOLVED-BREAKS-OMP; population: 4 of 118284 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoVsReferencia']; window: 2026-10-06T13:03:40.690000+00:00..2026-10-06T13:20:45.2…
- report generated_at: 2026-10-06T13:41:08.798347+00:00
- usage rows: 79
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 245791
- output tokens: 89805
- cache-read tokens: 15081216
- cache-write tokens: 0
- hit ratio: 98.3964% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=75 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 79 of 79 matched usage rows
- prefix breaks: 10 (state=RESOLVED-BREAKS-OMP; population: 4 of 118284 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoVsReferencia']; window: 2026-10-06T13:03:40.690000+00:00..2026-10-06T13:20:45.272000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T13:03:40.690000+00:00; WHERE session_id=01a1114f-d922-702b-8ca0-58c13b53497e provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791291820690
  - break_items=3; WHEN=2026-10-06T13:05:30.610000+00:00; WHERE session_id=01a1114f-d922-702b-8ca0-58c13b53497e provider=deepseek-flash model=deepseek-flash item_index=52; turn_id=1791291930610
  - break_items=2; WHEN=2026-10-06T13:11:06.253000+00:00; WHERE session_id=01a1114f-d922-702b-8ca0-58c13b53497e provider=deepseek-flash model=deepseek-flash item_index=162; turn_id=1791292266253
  - break_items=2; WHEN=2026-10-06T13:20:45.272000+00:00; WHERE session_id=01a1114f-d922-702b-8ca0-58c13b53497e provider=deepseek-flash model=deepseek-flash item_index=190; turn_id=1791292845272
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## STATE CHANGE (post-audit) — the cure landed, and the oracle was faithful

Appended 2026-10-06 after the audit, because §9's forward-looking line ("the fix is NOT landed") is now stale.
The audit's NUMBERS remain measurements of `worker/sotto_worker.py` @ sha256 `d4f4d529…` (132 418 B); that
revision is pinned in §2 of the report, so they stay re-derivable.

- `worker/sotto_worker.py` is now **149 856 B, sha256 `04a0aec6fe84ca8e…`**.
- The landed rule is **exactly arm 3** of `_main/sotto-vs-ref-decode-arms.py`: `_last_symbol` at :512/:584/:639/:783,
  `seed = self.blank if self._last_symbol is None else self._last_symbol` at :740, and a comment at :721 that
  quotes this audit's own number ("re-prime per chunk -> 2 183 words (50.7 % of ref)").
- The shipped worker now reports **tokens 10 738 / empty_chunks 270 / 4 279 words (99.4 % of the 4 303-word
  reference)** over the same 1 508 s file — **byte-identical to arm 3** (10 738 / 270 / 4 279, WER 0.1536),
  against the pre-cure arm (5 661 / 1 597 / 2 183, WER 0.6105).
- Landed-run receipts: `G:/sotto-ref/sotto-full-cura.jsonl`, `G:/sotto-ref/ship-int8.jsonl`.
- **Still open, named rather than implied:** the live route's `SpeechMusicGate` + `AutoGain` are unmeasured
  (report §5.3), so `DONO-20261006-caption-quality` is only partly answered — the redux route is fixed and
  measured, the live-arm residual is not.

## ATRIBUICAO — o meu write-set completo (para quem verifica quem tocou o que)

Esta lane (`SottoVsReferencia`) escreveu, em TODOS os repos, apenas:
- `H:/sotto/docs/audit/sotto-vs-referencia.md` (o relatorio) e `...RECEIPT.md` (o recibo)
- `H:/sotto/_main/sotto-vs-ref-probe.py`, `...decode-arms.py`, `...compare.py` (os 3 instrumentos)
- `G:/sotto-ref/*` (video, WAV 16 kHz mono, transcricao de referencia, saidas das corridas)

**Nada sob `H:/sotto/app/` foi aberto ou escrito por esta lane.** Em particular `H:/sotto/app/electron/panel.js`
— o diff pos-fecho que o passe teorista `2026-10-06T15-50Z` F6 aponta (78 insercoes / 20 delecoes / 23 692 B /
sha256 `e374a37e…`) — **nao** tem contribuicao deste trabalho; a atribuicao pertence a lane dona de
`app/electron`, nao a reconciliacao do card #943.

## SELOS TEORISTAS DISPOSTOS NESTA SESSAO

O selo exige disposicao por passe (chaveado pelo sha256 do passe mais recente, e o loop reescreve esse
ficheiro — um passe foi reescrito de sha `54897e9cb7bc99d2` para `4d7af6d2fc82dbad` em segundos, invalidando
uma disposicao ja gravada). Disposicoes gravadas por esta lane:
- `answer` em `2026-10-06T14-12Z` (sha256:31f91d49872ac617) — resolveu o falsificador do F5 daquele passe: o
  artefacto de fecho que o card #943 nao tinha existe, e esta em `H:/sotto/docs/audit/`, nao em
  `I:/!manager/{state/cards,runs}` onde a busca foi feita.
- `skip` em `2026-10-06T17-33Z` (sha256:f2fd93e689f2bc1b) — passe inteiramente de infra-estrutura
  (loop/census/observer), nenhum achado tocando esta lane.
- `answer` em `2026-10-06T15-50Z` (shas 54897e9cb7bc99d2 e depois 4d7af6d2fc82dbad) — F6 daquele passe cai
  neste repo; resolvi a metade da atribuicao pelo meu write-set completo acima.
