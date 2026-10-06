# `worker/config.json` — key-by-key consumption audit

**Date:** 2026-10-06 · **Repo:** `H:/sotto` · **Scope:** `worker/config.json` and *every* code path that reads it.
**Mode:** READ-ONLY. No file in `H:/sotto` was created, edited, moved or deleted except this one `.md`.
The app was **not** launched; `python`/`pythonw` were **not** started (see §8 for the static-only method).
The live app (pid 30848) was not touched.

**Audited revision (hash-pinned, because both files are UNCOMMITTED — see §7):**

```
989b9304dc8694531f87794a1bbc5deafd298148c4d91392d01f5945b133efa0  worker/config.json
d7718a6376104a6a589159d55109f76bbf2109ac22d57dd10250218e32d8c782  worker/sotto_worker.py
10dd72d1a9e8c071f948c0f344afe25c91e7f0f5df26959c3275e6f2832a3d67  worker/lang_prompt.py
```

---

## 0. Method (what produced each claim)

1. **Line-cited reads** of the file and of every consumer (`read`, line-numbered).
2. **A grep census** over `worker/**.py` and `app/**` for each key's *access form* (a read is a subscript,
   a `.get(...)`, or a JS property read; a **zero** hit is cited as the absence of a consumer). Native grep
   tool, no shell `grep -E` (the box's `grep -E` is a uutils subset and is blocked by the landmine guard, C2).
3. **Runtime receipts already on disk** (`worker/runs/*.jsonl`, `_main/*.jsonl`) — boot lines the worker
   itself wrote on previous runs. These are the only behavioural evidence; I ran nothing.
4. **`git show HEAD:...`** to establish the committed baseline (which differs — §7).

Consumers found, exhaustively: `worker/sotto_worker.py` and `worker/lang_prompt.py`. **No other file in the
repo parses `worker/config.json`.** `app/electron/worker-bridge.js` only mentions it in comments
(`worker-bridge.js:69, 481`: the worker "reads `config.json`"), and `app/webview/*` never opens it — grep for
`config.json` over `app/` returns docs/comments only.

---

## 1. The file as shipped (line numbers)

```
audio.device             (line 3)   null
audio.preferred_devices  (line 4)   []
audio.match              (line 5)   "heuristic"
audio.sample_rate        (line 7)   16000
audio.channels           (line 8)   1
audio.block_ms           (line 9)   100
audio.latency            (line 10)  "low"
model.dir                (line 13)  "models/nemotron-3.5-asr-streaming-0.6b-int8"
model.lang_id            (line 15)  "auto"
model.use_vad            (line 16)  true
model.providers          (line 17)  ["CUDAExecutionProvider", "CPUExecutionProvider"]
output.partial           (line 20)  false
output.min_chars         (line 21)  1
```

## 2. Key-by-key: READ, by what path, with evidence

| key | consumed? | consuming path (file:line) | runtime evidence |
|---|---|---|---|
| `model.dir` | **READ** | `sotto_worker.py:1098` `model_dir = args.model or cfg.get("model", {}).get("dir") or DEFAULT_MODEL`; relative → `os.path.join(HERE, …)` at `:1099-1100` | `_main/census-own-worker.jsonl:4` `"model": "nemotron-3.5-asr-streaming-0.6b-int8"` |
| `model.lang_id` | **READ** | `sotto_worker.py:1119-1120` `elif "lang_id" in (cfg.get("model") or {}): … cfg["model"]["lang_id"], "config"` → `lang_prompt.resolve_lang_id` `:1126` | `_main/census-own-worker.jsonl:2` `"lang_id": 101, "requested": "auto", "source": "config:auto"` |
| `model.use_vad` | **READ** | `sotto_worker.py:1152` `use_vad = bool(cfg.get("model", {}).get("use_vad", False))` → `StreamAsr(..., use_vad=use_vad)` `:1176` → `sp.set_option("use_vad", …)` `:433` | `vad_gated_chunks` now lands in `selftest-done` (33 lines) and `done` (5 lines) in `worker/runs/*.jsonl`; e.g. a `done` line carries `"vad_gated_chunks": 1` |
| `model.providers` | **READ** | `sotto_worker.py:1156` `choose_providers(args.providers or cfg.get("model", {}).get("providers"))` → `def choose_providers` `:883` | `_main/census-own-worker.jsonl:3` `providers_selected: ["CUDAExecutionProvider","CPUExecutionProvider"]` = the file's value |
| `audio.device` | **READ, no effect at shipped value** | `sotto_worker.py:1227-1228` → `device_candidates(cfg_audio, …)`; `:667 if cfg_audio.get("device"): names.append(...)` | value is `null` ⇒ the branch is skipped |
| `audio.preferred_devices` | **READ, no effect at shipped value** | same call; `:669 names.extend(str(n) for n in (cfg_audio.get("preferred_devices") or ()))` | value is `[]` ⇒ contributes no name |
| `audio.match` | **NOT READ — inert** | zero access forms in `worker/`+`app/` | — |
| `audio.sample_rate` | **NOT READ — inert** | zero; the code uses the constant `TARGET_SR = 16000` (`:69`) | value coincides with the constant (see §5) |
| `audio.channels` | **NOT READ — inert** | zero; channels is hardcoded `channels=1` (`:824`, `:833`) and `min(2, …)` (`:816`) | — |
| `audio.block_ms` | **NOT READ — inert** | zero; `block_ms` is a *parameter* defaulting to `100` (`_PortAudioTap.__init__` `:809`, `WasapiLoopbackTap` `wasapi_loopback.py:312`, `LoopbackTap` `:861`), and the call site passes none (`:1414 tap = LoopbackTap(dev, on_block)`) | value 100 coincides with the default → `capture-started` blocks read `"block": 1600` (= 16000 × 100/1000) |
| `audio.latency` | **NOT READ — inert** | zero | — |
| `output.partial` | **NOT READ — inert** | zero | — |
| `output.min_chars` | **NOT READ — inert** | zero | — |

**Cross-check of the "inert" class (grep counts over `worker/`+`app/`, code extensions only):**
`min_chars → 0`, `sample_rate → 0`, `"channels" → 1` (the config file itself), `"match" → 2` (config files only).
Matches for `block_ms` (18), `latency` (35) and `partial` (221) are the *parameter name*, *prose*, and
*"partial symbols"/"partial record"* comments respectively — none is a config read. No string
`cfg_audio.get("match")`, `["output"]`, `get("partial")`, `get("min_chars")`, `get("latency")`,
`get("sample_rate")`, `get("block_ms")` or `get("channels")` exists anywhere in the repo.

---

## 3. The `lang_id` key: dead for the file's git-recorded life, live as of today

**The defect (documented, and reproduced from the record):**

- The committed config carried `"lang_id": 0` — `git show HEAD:worker/config.json:16` → `"lang_id": 0`,
  with `"dir": "...-int4"` (`:15`) and `"use_vad": false` (`:17`). HEAD is `3e90f92`.
- The mechanism is documented at `worker/lang_prompt.py:7-15`: the old line was
  `ap.add_argument("--lang-id", type=int, default=0)`, followed by
  `lang_id = args.lang_id if args.lang_id is not None else cfg[...]["lang_id"]`. **`default=0` is never
  `None`**, so the `else` branch — the only reader of the config key — was unreachable. Same text in
  `docs/model-specs/README.md:109-112`.
- The fix is present in the working tree: `sotto_worker.py:1031-1038` declares `--lang-id` with
  `default=None` (`:1033`), and the config rung is now reachable at `:1119-1120`.

**What I could and could not verify.** The *pre-fix source line* is not recoverable from git: the committed
`worker/sotto_worker.py` is a **different, older generation** (368 lines, no `--lang-id` flag at all, with
`"lang_id": self.lid` at committed line 133), while the working tree is 1699 lines and uncommitted (§7). So
the dead-code claim rests on (a) the in-repo documentation above, (b) the committed config value `0`, and
(c) today's runtime receipt `source: "config:auto"` (`census-own-worker.jsonl:2`) proving the rung now fires —
**not** on a git diff of the fix. Stated, not glossed.

---

## 4. VAD: read, honoured at the processor, and a measured **no-op** on the shipped sample

**The plumbing is real (LIVE, not a stored-but-ignored key).** `use_vad` is read at `sotto_worker.py:1152`,
passed to `StreamAsr` (`:1176`), and set on the generator's streaming processor at `:433`:
`self.sp.set_option("use_vad", "1" if use_vad else "0")`. The option is **consumed** by
`onnxruntime-genai` 0.17.1 — measured with `get_option` read-back and a digital-silence discriminator in
`_main/vad-option-probe.py` (arm off: `get_option('use_vad') = 'false'`, 12/12 silence blocks pass; arm on:
`'true'`, 2 pass then `None` ×10). Receipts: `_main/vad-turn-boundary-20261006.md`; the probe itself at
`_main/vad-option-probe.py:60-84`.

**The threshold set lives in `genai_config.json`, not in `config.json`** (int8 export):

```
genai_config.json:64-68   "vad": { "filename": "silero_vad.onnx",
                                   "threshold": 0.3,
                                   "silence_duration_ms": 3360,
                                   "prefix_padding_ms": 560 }
```

`worker/README.md:175-177` and `docs/model-specs/README.md:121` quote exactly these numbers — **no
contradiction** (0.3 / 3360 / 560 all match).

**The measured no-op.** On the bundled sample the flag changes nothing measurable:

- `_main/vad-arm-before.json` vs `_main/vad-arm-after.json`: `sample1.flac`, VAD off vs on — 16 captions
  each; the arm table in `_main/vad-turn-boundary-20261006.md` (Arm 2) shows field-for-field equality:
  94 tokens, 262 frames, 168 blanks, `blank_frac 0.6412`, `vad_gated_chunks = 0`.
- Reason, named in `docs/model-specs/README.md:161-167`: the 13.44 s clip contains no 3.36 s of silence for
  the VAD to gate. This is a property of **the clip**, not of an inert flag.

**Where the flag *does* move behaviour** (the crash the boolean alone causes): on `_main/vad-gap-sample.flac`
(`sample1` + 6.0 s digital silence + `sample2`), VAD-on without the `None` guard raised
`TypeError: 'NoneType' object is not subscriptable` and exited 1; after the guard in `run_chunk`
(`sotto_worker.py:524-545`, counting `vad_gated_chunks`) it exits 0 and gates 6 chunks
(`_main/vad-turn-boundary-20261006.md`, Arm 1; receipts `_main/vad-arm-gap-on.json` 6 captions vs
`_main/vad-arm-gap-off.json` 4 captions).

**Default divergence (a real one, not doc-vs-file):** the *file* is `true` (config.json:16) but the *code*
fallback is `False` — `cfg.get("model", {}).get("use_vad", False)` (`sotto_worker.py:1152`). Delete the key
and VAD silently turns off, while `worker/README.md:174` says it "is **on**".

---

## 5. Sample rates: three declarations, one actually used

| declaration | value | read by |
|---|---|---|
| `worker/config.json:7` `audio.sample_rate` | 16000 | **nothing** (inert) |
| `worker/models/…-int8/genai_config.json:15` `model.sample_rate` | 16000 | onnxruntime-genai (model's own) |
| `worker/models/…-int8/audio_processor_config.json:4` `audio_params.sample_rate` | 16000 | the mel front end |
| `sotto_worker.py:69` `TARGET_SR = 16000` | 16000 | **the capture/resample path** (`:69`, `:823-829`, `resample_to_16k` `:763-775`, `:954-958`) |

The capture path asks the device for `TARGET_SR` mono directly (`sotto_worker.py:822-836`) and resamples if
the endpoint refuses (`:826-829`, `:1346-1350`). The config's copy is decorative; all four agree on 16000
today, so the inertness is invisible — and that is exactly the failure mode: editing
`config.json.audio.sample_rate` would change nothing and would look like it did.

The **streaming chunk** is likewise not a config value: `chunk_samples: 8960` (0.56 s @ 16 kHz) comes from
`genai_config.json:16`, read back at `sotto_worker.py:397 self.chunk = cfg["chunk_samples"]`, and
cross-checked against the encoder graph (`:320-345`).

---

## 6. Findings: read-but-ignored keys, and defaults that contradict the docs

### 6.1 Keys nothing reads (inert — a knob a user/operator can set that has no effect)
- `audio.match: "heuristic"` (config.json:5) — the name heuristic is applied **unconditionally**
  (`heuristic_loopback_score`, called at `sotto_worker.py:733-736`); there is no branch on this key. It
  *names* a behaviour that is always on, implying it is selectable.
- `audio.sample_rate: 16000` (config.json:7) — see §5.
- `audio.channels: 1` (config.json:8) — channels is hardcoded (`:824`, `:833`).
- `audio.block_ms: 100` (config.json:9) — the effective value is the function-parameter default
  (`:809`, `:861`), not the file.
- `audio.latency: "low"` (config.json:10) — no consumer anywhere; a leftover of an earlier PCM/streaming
  design (nothing in the repo maps "low"/"high" to anything).
- `output.partial: false` (config.json:20) — no consumer.
- `output.min_chars: 1` (config.json:21) — no consumer. Grep over the whole repo for `min_chars`
  in code returns **0**.

### 6.2 Keys read, but with a shipped value that makes them do nothing (by design, and documented as such)
- `audio.device: null` (config.json:3) and `audio.preferred_devices: []` (config.json:4) — read at
  `sotto_worker.py:667`/`:669`, but the shipped values contribute no candidate. The file's own `_comment`
  (config.json:6), `worker/README.md:154-157` and `docs/audio-ladder.md:105-106` state this is deliberate
  ("DELIBERATELY EMPTY"). **Not a defect** — listed so the census is complete rather than selectively green.

### 6.3 Defaults that contradict a doc or a sibling default
1. **`model.dir` vs `DEFAULT_MODEL`.** File = `…-int8` (config.json:13); code fallback =
   `DEFAULT_MODEL = os.path.join(HERE, "models", "nemotron-3.5-asr-streaming-0.6b-int4")`
   (`sotto_worker.py:68`). Remove `model.dir` and the run silently loads **int4**, while
   `worker/README.md:144-146` and `AGENTS.md:23` state the shipped choice is int8 (the different, larger
   model). Same "silent substitution" class the ladder work removed for devices.
2. **`use_vad` code default `False`** (`sotto_worker.py:1152`) vs file `true` and README "on" — see §4.
3. **`PREFERRED_DEVICES` is `()`** (`sotto_worker.py:94`) while `worker/README.md:156-157` presents
   `PREFERRED_DEVICES` as a populated rung between `preferred_devices` and the non-microphone tail. The
   *internal* doc (`docs/audio-ladder.md:105-106`) says it is "**empty on purpose**". So the worker README's
   ladder description and the audio-ladder doc disagree about an empty tuple; the code follows the latter.

### 6.4 A config/documentation gap (not a defect, a drift surface)
`AGENTS.md:74` and `worker/README.md:184-185` list the config as carrying exactly five keys —
`audio.device`, `model.dir`, `model.lang_id`, `model.use_vad`, `model.providers`. The file carries **13**
(twelve above plus `audio.preferred_devices`). The eight unlisted keys are precisely the inert set in §6.1
plus `preferred_devices` — i.e. the doc omits exactly the keys that do nothing, so nothing today contradicts
it, but a future reader has no way to tell an inert key from a live one by reading the docs.

### 6.5 Provider selection reads a *different* model than the run
`choose_providers` (`sotto_worker.py:883`) probes CUDA with a real session on
`os.path.join(DEFAULT_MODEL, "joint.onnx")` (`:934`) — i.e. the **int4** export — regardless of the
configured `model.dir` (int8). The selection the file requests is honoured
(`providers_selected = ["CUDAExecutionProvider","CPUExecutionProvider"]`, `census-own-worker.jsonl:3`), so
this is a probe-path inconsistency, not a wrong provider list; but the CUDA liveness test is run against a
model the run never loads.

---

## 7. Tree state — this audit is of an UNCOMMITTED revision

`git status --short worker/config.json worker/sotto_worker.py` → both ` M`.

- `git show HEAD:worker/config.json` → `dir: …-int4`, `lang_id: 0`, `use_vad: false`,
  `providers: ["CPUExecutionProvider"]`.
- `git show HEAD:worker/sotto_worker.py | wc -l` → **368** lines (an older generation; no `--lang-id` flag).
- Working tree → **1699** lines.

So every "today" claim in this document is about the working tree at the hashes in the header, and the
committed baseline is a *different* worker. A reader comparing against `HEAD` will see a mismatch that is
expected, not a defect. This is why the three hashes are pinned above.

---

## 8. What I could NOT verify, and why

- **No live/capture-path run of my own.** The app is running (pid 30848) and the brief forbids launching it;
  the worker needs a 1.2 GB model session and (for the live path) an audio device. Every behavioural claim
  above therefore cites a receipt **already on disk**, and each is a *previous* run's output, not a run I made.
- **The pre-fix `default=0` source line** is not in git (§3) — the committed worker is a different file.
- **`WasapiLoopbackTap`'s own block/sample handling in the live path** was read (`wasapi_loopback.py:312-322`,
  `:463`), not exercised; the file-mode receipts do not open a WASAPI tap.
- **`output.*` intent.** I can show no code reads `partial`/`min_chars`; I cannot show what they were meant
  for (no comment, no consumer, no receipt).
- **Whether any *external* operator/tool reads these keys** (e.g. a shell script outside the repo). I searched
  `H:/sotto` only; the brief scopes me to the repo.

---

## SELF-AUDIT

- **protocolos em falta** — I did not hash-pin the audited revision *before* starting to read; I collected
  hashes only after the fact, in §7. A sibling lane was editing `worker/config.json` earlier today
  (documented drift in `_main/vad-turn-boundary-20261006.md` and `_main/lang-id-receipt.md`), so my line
  citations are valid only for sha `989b9304…`. What I would do differently: `sha256sum` the target and its
  consumers as the *first* command, exactly as the two sibling self-audits already demand, and re-assert it
  at the end.
- **verificacao adicional** — the cheap extra check that would most raise confidence: a mechanical
  "every JSON key has a consumer" assertion (see the new checkbox below). It is one grep-based pass and would
  have made §2 a gate instead of a survey. I did the pass manually (grep counts in §2) but not as a committed
  oracle, because I may write only this one file.
- **checkboxes novas (MECANICAS)** — add to any config-file audit: for every leaf key in the JSON, assert a
  consumer exists, or the key is on an explicit allow-list of "known-inert/deliberately-empty". Command shape:
  `py -3 -c "import json;cfg=json.load(open('worker/config.json'));…"` emitting `key -> hits` from a grep over
  the code tree, and **exiting non-zero when a key has 0 hits and is not allow-listed**. Input that must leave
  it RED: today's tree — it would flag exactly `audio.match`, `audio.sample_rate`, `audio.channels`,
  `audio.block_ms`, `audio.latency`, `output.partial`, `output.min_chars`. Second checkbox: assert
  `DEFAULT_MODEL`'s directory == `config.model.dir`'s directory (RED on today's tree: int4 vs int8, §6.3).
- **review por outro subagente** — **sim-com-escopo**: (a) the "inert key" set in §2/§6.1, which is an
  *absence* claim and the easiest class to get wrong, and (b) the VAD "no-op on the clip, live at the
  processor" distinction, which is two claims that read alike and must not be collapsed.
- **gate-doubt**:
  - **verde-de-verdade:** I ran **no gate** and claim none. The nearest thing to a green is the repo's own
    `_oss_oracle` / `_main/model-spec-oracle.py`, which I did **not** re-run; I also did not read their
    verdict logs as evidence of anything beyond their own scope. The "greens" in §2 are grep hit-counts — real
    runs of the grep tool — but a zero hit-count is not a proof of no consumer (it is a proof of no *string
    match*); that limit is stated in §2.
  - **falta-no-gate:** no gate in the repo checks that a shipped JSON key has a reader. A future change
    crosses it exactly as today's file already has: someone edits `audio.block_ms` (or adds a new
    `audio.something`) expecting an effect, and every individual oracle still exits 0, because they check
    model geometry and VAD/genai agreement, not config-key reachability. `_main/model-spec-oracle.py` reads
    the config but asserts only `blank_id`/`chunk_samples`.
  - **gate-melhor:** the "every leaf key has a consumer or is allow-listed" assertion above, with the RED
    input named (today's seven inert keys). I could not land it: the brief permits writing exactly one file,
    and a gate is executable, not a `.md`.
- **confianca** — **alta** for the read/not-read split (both the line-cited call paths and the grep census
  agree, and two keys — `use_vad`, `lang_id` — are independently confirmed by runtime receipts). **media**
  for the *historical* claim that `lang_id` was dead "for the whole life of the file": it rests on
  documentation + the committed config value, because the pre-fix source is not in git (§3). What would move
  it to high: the pre-fix `sotto_worker.py` found in a stash/worktree/editor history.
- **nao verificado** — (1) no run I initiated (§8); (2) pre-fix source line absent from git (§3); (3) live
  WASAPI tap path not exercised; (4) intent of `output.*` unknown; (5) consumers outside `H:/sotto` not
  searched; (6) `audio.device`/`preferred_devices` behaviour with a *non-empty* value is read-only-verified
  by code (`:667`/`:669`) and by `_main/SottoDeviceResolution.md`, not by a run of mine.

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh AuditModelConfig` — output pasted VERBATIM:

```
## CACHE/PRICE
- task/agent: AuditModelConfig
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditModelConfig.jsonl
- cache: read=2115712 write=0 hit=92.3170% (cache-read / input+cache-read); universe: 32 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditModelConfig.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=21 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=11 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 32 of 32 matched usage rows
- when-failed: break_items=11; WHEN=2026-10-06T08:24:50.247000+00:00 | break_items=3; WHEN=2026-10-06T08:26:08.770000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 113369 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditModelConfig']; window: 2026-10-06T08:24:50.247000+00:00..2026-10-06T08:26:08.770000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11050-0caf-72c3-aaf9-533471869d8a provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275090247 | session_id=01a11050-0caf-72c3-aaf9-533471869d8a provider=deepseek-flash model=deepseek-flash item_index=88; turn_id=1791275168770 (state=RESOLVED-BREAKS-OMP; population: 2 of 113369 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditModelConfig']; window: 2026-10-06T08:24:50.247000+00:00..2026-10-06T08:26:08.770000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T08:26:55.338824+00:00
- usage rows: 32
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 176078
- output tokens: 14935
- cache-read tokens: 2115712
- cache-write tokens: 0
- hit ratio: 92.3170% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing: exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=21 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=11 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 32 of 32 matched usage rows
- prefix breaks: 14 (state=RESOLVED-BREAKS-OMP; population: 2 of 113369 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditModelConfig']; window: 2026-10-06T08:24:50.247000+00:00..2026-10-06T08:26:08.770000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=11; WHEN=2026-10-06T08:24:50.247000+00:00; WHERE session_id=01a11050-0caf-72c3-aaf9-533471869d8a provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275090247
  - break_items=3; WHEN=2026-10-06T08:26:08.770000+00:00; WHERE session_id=01a11050-0caf-72c3-aaf9-533471869d8a provider=deepseek-flash model=deepseek-flash item_index=88; turn_id=1791275168770
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

- cache: read=2115712 write=0 hit=92.3170% over 32 usage rows; instrument `scripts/cache-task-report.sh`,
  universe = my own session JSONL (named above).
- price: $0.00000000 USD — provider-reported `message.usage.cost.total`; per-model rates unknown in this source.
- when-failed: two prefix-break windows, WHEN 2026-10-06T08:24:50.247Z and 2026-10-06T08:26:08.770Z
  (state `RESOLVED-BREAKS-OMP`); run of `cache-task-report.sh` rc=0.
- where-failed: session `01a11050-0caf-72c3-aaf9-533471869d8a`, provider/model `deepseek-flash`,
  item_index 0 / 88.
- source: `C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditModelConfig.jsonl`
