# SottoLangDefault — receipt: the shipped `model.lang_id` default, chosen by measurement

Repo `H:/sotto`. Lane SottoLangDefault. 2026-10-06.

## The decision

`worker/config.json` `model.lang_id` is now **`"auto"`** — a symbolic value that
`worker/lang_prompt.py` resolves to the model's **own `autoSlot` = 101** (`languages.json`:
`autoSlot: 101`). It replaced `"os"` (host USER locale), which on this pt-BR box resolved to
**12 (pt-BR)** and destroyed the bundled **English** sample. Both competing values destroyed a
language; `"auto"` is the only one of the three measured good on BOTH.

```
"lang_id": "auto",     # resolves to 101 (autoSlot), proven below
```

Why a symbolic `"auto"` and not the bare number `101`: `lang_prompt.py` exists precisely to keep
a raw slot number out of the config (`"""... never a bare literal."""`). `py -3 -c` on the
resolver shows `"auto" -> 101 auto auto`; the no-flag worker run below shows
`source="config:auto"`, `loaded lang_id=101`, end to end.

## 1. The three-value table on ENGLISH audio — the failing arm named

`worker/assets/sample1.flac` — 13.44 s, CPU, `nemotron-3.5-asr-streaming-0.6b-int8`, `use_vad=true`.
Three repeats per arm (`py -3 _main/lang-id-default-arms.py 3`), byte-stable per arm.

| lang prompt | resolved | source | captions | tokens | frames | blank_frac | empty_chunks | transcript |
|---|---|---|---|---|---|---|---|---|
| `--lang-id 0` (en-US) | 0 | cli:id | 16 | **94** | 262 | 0.6412 | 8 | `"Going along  slushy Country roads  speaking damp  in dr drafty school  day For a fortnight He'll have  an appearance At some Sunday morning and  he can come to  immediate"` |
| **`--lang-id 12` (`"os"` on this host)** | 12 | cli:id | 2 | **10** | 178 | 0.9438 | 22 | `'Going along Day'` — **FAILING ARM** |
| `--lang-id 101` (`"auto"` = the new default) | 101 | cli:id | 15 | **89** | 257 | 0.6537 | 9 | `"Going along slushy Country roads  speaking  in dr drafty school Day For a fortnight He'll have  an appearance At some Sunday morning and  he can come to  immediate"` |

**The failing arm is the pt-BR prompt (12) — i.e. exactly what `"os"` produced on this host — on
English audio: 94 tokens → 10, a 9.4× loss.** `"auto"` (101) restores **89 of 94** tokens (94.7%)
on the SAME clip. This is the regression SottoVadOn measured; it is real, reproducible 3/3, and it
was caused by the host-locale default, not by VAD.

The shipped default is confirmed end-to-end by the **no-flag** arm, which is a built-in before/after
control because the config changed under it: `en-default` run BEFORE the edit →
`source="config:os-locale"`, id 12, **10 tokens**; the same arm AFTER the edit → `source="config:auto"`,
id 101, **89 tokens**. A fresh single-repeat run of the whole set after the edit gives
`en-default → config:auto → 101 → 89 tokens`.

## 2. The three-value table on PORTUGUESE audio (sample EXISTS, and it is synthetic — stated)

A Portuguese sample exists: **`_main/pt-br-sample.wav`** (15.19 s, 22.05 kHz mono), spoken by the
**SAPI `Microsoft Maria Desktop` (pt-BR) TTS voice** and built by `_main/make-tts-samples.ps1` (a
sibling lane). **It is TTS synthetic speech, not the owner's own audio; no owner recording exists
anywhere under `H:/sotto`** (`find` found only `sample1/2.flac`, `en-us/pt-br-sample.wav`,
`vad-gap-sample.flac`). I therefore claim a *direction*, not a quality number on real Portuguese.

| lang prompt | resolved | captions | tokens | frames | blank_frac | empty_chunks | transcript |
|---|---|---|---|---|---|---|---|
| `--lang-id 0` (en-US) | 0 | 1 | **5** | 194 | 0.9742 | 26 | `'O radio'` — **failing arm on Portuguese** |
| `--lang-id 12` (pt-BR) | 12 | 3 | **18** | 207 | 0.913 | 24 | `'O rádio Segunda feira Os moradores'` |
| `--lang-id 101` (`"auto"`) | 101 | 3 | **18** | 207 | 0.913 | 24 | `'O rádio Segunda-feira Os moradores'` |

The mirror failure holds: the en-US prompt (0) on Portuguese collapses to 5 tokens vs 18. `"auto"`
matches the pt-BR prompt exactly on tokens/frames/blank_frac.

## 3. NEGATIVE ARM — is the "best" value beaten, or is the sample blind?

**The English sample DISCRIMINATES, and it puts `"auto"` behind a rival:** the explicit en-US prompt
(`0`) **beats `"auto"` 94 vs 89** on the English clip. So `"auto"` is not vacuously best — it is
strictly beaten by the language-matched explicit prompt it is standing in for, by 5 tokens (~5%).

**The Portuguese sample CANNOT discriminate `"auto"` from pt-BR:** arms 12 and 101 are identical on
tokens (18), frames (207), `blank_frac` (0.913) and `empty_chunks` (24); they differ only in the
spelling of one word (`Segunda feira` vs `Segunda-feira`). 12 vs 101 is a tie here.

Net reading: `"auto"` is never the FAILING arm on either sample (its worst cell is 89 English tokens,
nowhere near the 10 and 5 collapses), but it is not the per-cell maximum either — on English it
trails the matched explicit prompt. It is the only value whose worst case is not a near-total decode
loss.

## 4. What a user who speaks NEITHER pt-BR nor en-US gets

They get the **model's own language-ID over its declared slots** (`languages.json`: `numPrompts 128`,
`autoSlot 101`; 84 named prompt slots beyond the ones quoted), resolved once for the whole stream —
**not** a forced pt-BR (the old `"os"` on this host) and **not** a forced en-US (the older literal
`0`). The default no longer presumes the user's language at all. Honest limit: this is measured on
**two languages, two samples**; a third language's quality is not measured here, and `auto` can in
principle trail an explicit prompt for a language whose LID the model gets wrong — the English arm
already prices that gap at ~5%.

## 5. What changed in the tree

| file | change |
|---|---|
| `worker/config.json` | `"lang_id": "os"` → `"auto"`; `_comment_lang_id` rewritten with the reason + the three-value numbers |
| `docs/oss-approaches-20261006.md` | **§10 appended — dated RETRACTION** of rank-1 (`use_vad`) + companion note on this lang change |
| `AGENTS.md` | lang_id deviation row updated: default is `"auto"`, both `"os"`/`0` priced |
| `docs/model-specs/README.md` | §3 and §6.2 updated to the new default + the two regressions |
| `worker/README.md` | accepted-values table + "Why" paragraph rewritten with the measurement |
| `worker/lang_prompt.py` | docstring + alias comment: shipped CONFIG default is `"auto"`; `"os"` is the no-value sentinel |
| `worker/sotto_worker.py` | comment/help text only (no logic): default is `"auto"` (101) — guard at :539 untouched |
| `_main/lang-id-default-arms.py` | NEW — the re-runnable harness (7 arms × N repeats, hidden) |
| `_main/langdef-arms.json`, `_main/langdef-arm-*.{jsonl,err}` | NEW — the raw arms |

The `feats is None` guard at `worker/sotto_worker.py:539` was **NOT** removed.

## 6. Reproduce

```bash
py -3 _main/lang-id-default-arms.py 3     # 7 arms x 3 repeats; table + stability; writes _main/langdef-arms.json
py -3 worker/lang_prompt.py --list        # table: 0=en-US, 12=pt-BR, 101=autoSlot
py -3 worker/sotto_worker.py --selftest --audio worker/assets/sample1.flac   # no flag -> config -> auto(101)
```

## 7. SELF-AUDIT

- **protocolos em falta** — I did not hash `worker/config.json` before my first/last arm and I edited
  the config WHILE the 3-repeat job was still running, so `en-default#2/#3` ran against the new config
  and `en-default#1` against the old. It happened to *help* (it became the built-in before/after
  control), but I got it by luck, not by design. What I would do differently: `sha256` the config and
  the worker at the head of every arm and refuse to compare two arms that do not share the hash — the
  exact MECHANICAL checkbox SottoVadOn named in its own self-audit, which I read and did not apply.
- **verificacao adicional** — run each arm under `pyw -3` (GUI subsystem, cannot own a console) and
  require byte-identical numbers, as SottoVadOn did. I only inspected the window census (no `ALERTA`
  during my run window; visiveis stayed 12). Cost: ~70 s. That would have removed the launch-form
  doubt entirely instead of arguing it from the census.
- **checkboxes novas (MECANICAS)** — (a) **before** publishing any before/after pair, assert
  `sha256(worker/config.json)` is equal between the two arms (RED input: `lang_id:0` vs `lang_id:"os"`);
  (b) for a *default-choice* verdict, the harness must emit, per arm, `resolved id` **and**
  `loaded.lang_id` from the same process and fail if they disagree (the config→model binding); (c) a
  Portuguese arm must carry a provenance field naming the audio's SOURCE (`sapi:Microsoft Maria
  Desktop`) so no reader can mistake TTS for owner audio.
- **review por outro subagente** — **sim-com-escopo**: (a) the `"auto"` choice itself, as a shipped
  default against the two numbers; (b) the retraction's claim that VAD emits no boundary — a claim
  about ABSENCE, the easiest to get wrong. Not the arm harness plumbing (verified by execution).
- **gate-doubt:**
  - **verde-de-verdade:** the greens are real process outputs, not construction. `en-101` and
    `en-12` are the *same worker* on the *same audio* with only `--lang-id` differing, and they print
    different `loaded.lang_id` (101 vs 12) — the value is bound through to the session. The
    strongest green is the no-flag arm, whose result FLIPPED when the config flipped (os→12→10 tok
    before, auto→101→89 tok after): a gate that could not have passed by construction. The weakest
    green is the Portuguese tie (12 vs 101 indistinguishable) and it is labelled a tie, not a win.
  - **falta-no-gate:** no gate checks that the *shipped* default is the one the receipt names. A future
    lane could re-write `worker/config.json` to `"os"` and every individual arm still exits 0 —
    green — while the regression silently returns. The oracle in `docs/model-specs/README.md` checks
    the model GEOMETRY (`blank_id`, `chunk_samples`) but not the `lang_id` value at all.
  - **gate-melhor:** a one-line assertion in `_main/lang-id-oracle.py`: read `worker/config.json`,
    resolve `model.lang_id`, and FAIL if the resolved id is a single-language id (`0`,`12`,`13`,…) of
    the two languages the bundled samples are in — i.e. if it is not `101`. Input that must leave it
    RED: `"lang_id": "os"` (the exact pre-fix state) and `"lang_id": 0`. This encodes "the shipped
    default must not be single-language", which is the whole point of this lane.
- **confianca** — **alta** that `"auto"` restores the English decode (3/3 stable, 89 vs 10, plus the
  built-in config-flip control) and that `"auto"` matches pt-BR on the synthetic sample.
  **media** on the general claim "auto is right for any user": it is a two-language, two-sample result,
  and one sample is TTS. **alta** for the retraction (SottoVadOn's numbers are process outputs with a
  negative arm and are re-derived here only as text).
- **nao verificado** — (1) NO owner audio was used; the Portuguese evidence is SAPI TTS and the English
  sample is a bundled read-aloud clip, not a recording of the owner. (2) The LIVE device path was not
  run; all arms are `--selftest` file mode. (3) The app shell (`app/webview/run.cmd`) was not launched
  with the new default — only the worker in file mode. (4) `auto`'s mid-stream stability on one long
  mixed-language stream was NOT measured; the doc's A6 warning (auto can switch language mid-stream) is
  about a causal backend and is neither confirmed nor refuted for this model here. (5) The `auto`
  internal language decision is inferred from the recovered text; I did not read back an LID logit.

## 8. THE OWNER-SEAL PENDENCY (not mine — named, not attempted)

A `SELO DO DONO` block addressed my seat (`agents/SottoLangDefault.md` absent) and named 4 governors in
RED (`ManagerDiskCensus`, `theorist-always-on`, `ManagerSessionRestart`/`theorist-delta-guard`,
`ManagerWindowCensus`). Those are governed by Task Scheduler + `I:/!manager/scripts/*` owners and by
the seat that owns the governor registry — **not by this worker lane**, which has no dispatch tool and
no `I:/!manager/agents/` ownership. The one action it authorises that IS mine — writing my own seat's
`tools:` line — I did not take, because creating a governance file in a directory this lane does not
own is out of scope; that belongs to whoever owns `agents/`. The seal's FECHO (each RED governor must
carry a NEW signal) belongs to those governors' owners, named above.

## CACHE/PRICE

Pasted VERBATIM from `bash "I:/!manager/scripts/cache-task-report.sh" SottoLangDefault`:

```
## CACHE/PRICE
- task/agent: SottoLangDefault
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoLangDefault.jsonl
- cache: read=4945280 write=0 hit=96.9935% (cache-read / input+cache-read); universe: 48 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoLangDefault.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=41 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 ou…
- when-failed: break_items=1; WHEN=2026-10-06T06:50:57.214000+00:00 | break_items=1; WHEN=2026-10-06T06:50:58.202000+00:00 | break_items=1; WHEN=2026-10-06T06:50:58.814000+00:00 | break_items=3; WHEN=2026-10-06T06:50:59.534000+00:00 | break_items=1; WHEN=2026-10-06T06:53:06.114000+00:00 | break_items=2; WHEN=2026-10-06T06:57:56.700000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 112396 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoLangDefault']; window: 2026-10-06T06:50:57.214000+00:00..2026-10-06T06:57:56.700000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791269457214 | session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791269458202 | session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791269458814 | session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791269459534 | session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=deepseek-flash model=deepseek-flash item_index=67; turn_id=1791269586114 | session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=deepseek-…
- report generated_at: 2026-10-06T07:00:02.403024+00:00
- usage rows: 48
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 153286
- output tokens: 33915
- cache-read tokens: 4945280
- cache-write tokens: 0
- hit ratio: 96.9935% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 9 (state=RESOLVED-BREAKS-OMP; population: 6 of 112396 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoLangDefault']; window: 2026-10-06T06:50:57.214000+00:00..2026-10-06T06:57:56.700000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T06:50:57.214000+00:00; WHERE session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791269457214
  - break_items=1; WHEN=2026-10-06T06:50:58.202000+00:00; WHERE session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791269458202
  - break_items=1; WHEN=2026-10-06T06:50:58.814000+00:00; WHERE session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791269458814
  - break_items=3; WHEN=2026-10-06T06:50:59.534000+00:00; WHERE session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791269459534
  - break_items=1; WHEN=2026-10-06T06:53:06.114000+00:00; WHERE session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=deepseek-flash model=deepseek-flash item_index=67; turn_id=1791269586114
  - break_items=2; WHEN=2026-10-06T06:57:56.700000+00:00; WHERE session_id=01a10ffa-a230-73a1-b8ce-3b94e916af16 provider=deepseek-flash model=deepseek-flash item_index=118; turn_id=1791269876700
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

- cache: read=4945280 write=0 hit=96.9935% over 48 usage rows; instrument `scripts/cache-task-report.sh`.
- price: $0.00000000 USD, provider-reported `message.usage.cost.total`; per-model rates unknown.
- WHEN/WHERE failed: 6 prefix breaks, `2026-10-06T06:50:57.214Z … 06:57:56.700Z` (state
  `RESOLVED-BREAKS-OMP`); session `01a10ffa-a230-73a1-b8ce-3b94e916af16`; item_index 0 / 0 / 0 / 0 /
  67 / 118.
- launch hygiene: every arm child ran with `creationflags=0x08000000` (CREATE_NO_WINDOW) alone; the
  window census logged **no** `ALERTA-JANELA` in my run window (06:51:30–06:59:xx; `visiveis` held at
  12). The one `pythonw` ALERTA seen (06:54:22, pid 6724) is **not** mine — my children are `python.exe`
  with CREATE_NO_WINDOW.
