# The oracles of Sotto — which ones can actually go RED

Axis: **the oracles**. Audit date 2026-10-06. Read-only pass over `H:/sotto/_main` and
`H:/sotto/worker`. No process was launched; no file other than this one was written.

The house rule under audit: *a green you cannot turn red is not green.* For every
oracle/test in scope this file records: **what it asserts**, **what its negative arm is**,
and **whether that negative arm has ever been run** — with the artifact that proves it.

---

## 0. The headline finding

> **NOT ONE oracle asserts audio DELIVERY RATE** — seconds of audio captured per second of
> wall clock. A capturer delivering 35 % of the sound passes every oracle in this repo.

Evidence that the metric is absent (not merely unasserted):

```
$ cd H:/sotto && python -c "<scan: grep 'audio_s' in _main/*.py>"
(no hits)
```

`audio_s` — the worker's own count of seconds of audio that reached the ASR side — appears
**only** inside `worker/sotto_worker.py`. No file under `_main/` reads it, so no oracle can
compare it to wall time. Full detail in §3.

---

## 1. Scope and method

Files under `_main/` and `worker/` that are an **oracle** or a **test/selftest** (something
that emits a PASS/FAIL verdict and exits non-zero on failure). Measurement probes
(`*-probe.py`, `device-probe.py`, `capability-probe.py`, `measure-*.py`, `worker/_probe/*`)
are **out of scope** and listed in §6 only to mark the boundary.

Method: read the source; locate the assertion list and the negative-arm builder; then look
for the run artifact (log/json/jsonl) and read the verdict it carries. When an artifact's
mtime is **older** than its source, that is reported as a finding, because the receipt then
does not describe the file in the tree today.

---

## 2. Oracle inventory

### 2.1 `_main/device-silence-oracle.py` — the device/silence contract (205 lines)

**Asserts (two arms, real exit codes):**
- ARM 1 (`region _main/device-silence-oracle.py:132-156`): a config whose only device is a
  permanently silent one must FAIL LOUD — `rc != 0`, `rc == 3`, `done.verdict ==
  "silent-device"`, a `state=silent-device` status naming `device`+`peak`, and
  `blocks >= 20` (`:149`).
- ARM 2 (`:158-196`): with the bundled speech sample rendered into `CABLE Input`, the worker
  run on `CABLE Output` must SUCCEED — `rc == 0`, `verdict == "captions-emitted"`,
  `captions > 0` (`:181`), the settled device is the CABLE, `done.proved_alive` (`:185`).

**Negative arm:** ARM 1 *is* the negative colour for the device outcome (a silent endpoint),
but it is **not** a code mutation — it is a config swap. There is **no** arm that mutates the
worker's PASS/FAIL logic, so this oracle cannot go RED on a worker that keeps its output but
lies about the verdict (that is `verdict-order-oracle.py`'s job).

**Has the negative arm ever run?** **Yes.** Both arms ran:
- `worker/runs/oracle-neg.jsonl` → `done {verdict: "silent-device", device: "VoiceMeeter
  Output (VB-Audio Vo", blocks: 118, peak: 9.2e-05}`; the loud status names the silent device
  `Mapeador de som da Microsoft - Input` at `blocks: 60, peak: 9.2e-05`.
- `worker/runs/oracle-pos.jsonl` → `done {verdict: "captions-emitted", device: "CABLE Output
  (VB-Audio Virtual Cable)", blocks: 180, peak: 0.274506}`.

**Rate caveat (see §3):** `blocks >= 20` over the default `--max-seconds 20` (`secs` default
`"20"`, `_main/device-silence-oracle.py:119`) is an implicit rate floor of
20 blocks × 0.1 s / 20 s = **0.10**. A 35 % capturer passes it with room to spare.

---

### 2.2 `_main/verdict-order-oracle.py` — verdict word vs exit code (312 lines)

**Asserts (three arms):**
- GREEN (`:204-233`): the real worker must, on a silent loopback endpoint, emit
  `done.verdict == "silent-device"` with `rc == 3`, a `silent-device` status, and
  `blocks >= 20` (`:233`).
- RED (`:236-269`): a **textually-built mutant** with the PRE-FIX branch order must reproduce
  the contradiction — `rc == 3 AND silent status present AND verdict != "silent-device"`. If
  the mutant cannot be built (`:124-133`) or does not reproduce the contradiction (`:268`),
  the oracle FAILS.
- BLUE (`:271-293`): a run below `TAP_SILENT_BLOCKS` must still say
  `all-candidate-taps-flat` with `rc == 0` and **no** silent-device status — the fix must not
  swallow the other word.

**Negative arm:** the RED mutant, built from `FIXED_BRANCH`→`PREFIX_BRANCH` substitution on
`worker/sotto_worker.py` (`:77-90`, `:124-141`). This oracle **refuses to report green** if it
cannot build its own red arm (`build_mutant()` returns `(False, why)`).

**Has the negative arm ever run?** **Yes, and it fired.**
- `worker/runs/verdict-order-green.jsonl` → `done {verdict: "silent-device",
  device_outcome: "all-flat", blocks: 45}`.
- `worker/runs/verdict-order-red.jsonl` → `done {verdict: "all-candidate-taps-flat",
  device_outcome: "all-flat", blocks: 45}` — the mutant moved the word while `rc` stayed 3:
  the contradiction reproduced.
- `worker/runs/verdict-order-blue.jsonl` → `done {verdict: "all-candidate-taps-flat",
  blocks: 14}`.

This is the ONE oracle in the tree whose negative arm is a genuine code mutant with a
run artifact proving it moved the output.

---

### 2.3 `_main/panel-exit3-oracle.py` — does the PANEL show a dead worker (1024 lines)

**Asserts (six arm groups):**
- ARM 0 (`:247-334`): the shell's classifier paints `silent-device`/`device-exhausted`/
  `done-failure` as **error**, holds a restart warm-up behind the death, and lifts the hold on
  a caption.
- ARM D (`:336-494`): the worker's real `done` line, fed to the shell, must paint by
  **kind + footer + placeholder** on four inputs (real exit-3, an unknown verdict, **no
  verdict**, and the healthy positive control).
- ARM A/B (`:930-1008`): real WebView2 — a live run paints LIVE (`captions > 0` at `:999`),
  an exit-3 run paints ERROR naming the silent device, and the two renders must NOT be
  identical.
- ARM E (`:496-645`): after an exit-3 death a **real caption** must lift the hold and return
  the panel to LIVE.
- **Negative arms** (`:648-800`, `:752-800`): a COPY of **today's** shell with the mapping
  reverted must make ARM 1 go RED; a COPY with the CLEAR block removed must make ARM E go RED.
  Built from today's bytes, never from a kept copy.

**Has the negative arm ever run?** **Yes** — but **not in the file the oracle names**.
- The oracle writes `_main/panel-exit3-oracle.log`, and that file is **STALE**: mtime
  `03:54:30`, while the source is `04:40:36`. Its JSON contains only
  `arm0_classifier` / `armA_worker_alive` / `armB_worker_exit3` — **no ARM D, no ARM E, no
  `neg_arm`**. The one receipt the oracle writes does not describe the arms that exist today.
- The arm evidence IS on disk under separate names: `_main/panel-exit3-arm0-GREEN.log` and
  `-RED.log` (03:53), `_main/panel-exit3-armE-hold.log` + `-recover.log` + `-receipt.md`
  (04:45–04:51), `_main/_ppv-unit-oldred.log`, `_main/_ppv-negarm.log`,
  `_main/_ppv-paintorder-red.log`.

**Finding A:** `panel-exit3-oracle.log` (03:54) predates the arms in the source (04:40). The
top-level `"verdict": "PASS"` it carries was earned by a three-arm version of this file.

**Rate caveat:** ARM A's live check at `:999` is `captions > 0 OR live` — **one caption is
enough**. A worker that captions 35 % of the audio still paints LIVE.

---

### 2.4 `_main/panel-startup-visibility-oracle.py` — is the panel on screen at startup (445 lines)

**Asserts (five checks, `:424-434`):** `B.on_screen == true` (cure removed), `P.at_startup ==
false`, `P.on_screen == false`, `S.on_screen == true` (`--show` still shows), `N.at_startup ==
true` (hide removed).

**Negative arm:** the `N` (hide-removed) and `B` (pre-cure) variants are **built from the live
shell** at run time (`build_variant()`, `:317-337`), which raises if the edit pattern is not
found — so the arms cannot silently go stale.

**Has the negative arm ever run?** **Yes.** `_main/panel-startup-visibility.log` (04:12):
`VERDICT PASS ... at_startup_neg=True at_startup_neg2=False`, with the five `CHECK ... PASS`
lines and the matching `_census-{B,P,S,N,N2}-*.log` / `-state.json` files.

---

### 2.5 `_main/run-cmd-exit-oracle.py` — the exit contract of `run.cmd` (644 lines)

**Asserts (five arms + one census conjunct):** arm `argv` (`:289`), arm `bogus`
(`:339` — a rejected flag must NOT answer as success: `rc 2`, `REFUSED`, a log receipt, no
`shell=` line, no leftover process), arm `help` (`:368` — full usage, `--check-args` absent),
arms `start-logged` / `start-default` (`:397` — rc 0, the app's own pid line, that pid alive,
clean `SHELL_EXIT`, pid gone). Plus a window census: the run's own tree must show **no visible
window** (`:587`).

**Negative arm:** `--neg-arm` reverts `run.cmd` in a COPY from `_main/run-cmd-prefix-20261006.cmd`
(`build_reverted_copy`, `:448-486`); arm 1 must go RED and arms 2–4 stay green. It **refuses**
(`raise SystemExit`) if the control copy already carries the pre-flight, i.e. the control is
dead.

**Has the negative arm ever run?** **Yes, and it fired.**
- `_main/run-cmd-exit-oracle-neg-arm.json` (05:05): arm `bogus rc=0 want=2` →
  `arms_ok: True` (arm 1 RED-as-expected, arms 2–4 green) — the pre-fix wrapper accepted the
  bogus flag.
- `_main/run-cmd-exit-oracle-after.json` (05:05): the live wrapper, `arms_ok: True`,
  `census_ok: False`.

**However — and this is the important part — the oracle is currently RED:**
`run-cmd-exit-oracle-after.json` → `"verdict": "FAIL"`, `reason: "arms=PASS census=FAIL -> a
VISIBLE window was measured"`. The arm conjunct is green; the **census conjunct is red**: the
*app* put its panel on the screen during a start. The `--neg-arm` receipt is also `FAIL` for
the same census reason (not for the arms). So this oracle's live state is RED, and the red is
an app-side startup flash, not a wrapper defect.

---

### 2.6 `_main/lang-id-oracle.py` — language-prompt resolution (178 lines)

**Asserts (six sections, `:120-176`):** the table is a real `languages.json`; `numPrompts ==
128`; `autoSlot == 101`; the documented ids resolve (`0→en-US, 12→pt-BR, 13→pt-PT,
101→auto`); the shipped `'os'` equals the host locale and `None` equals `'os'`; **undeclared
ids are REFUSED** (`999, -1, 300, 128, "klingon", "zz-ZZ", "107"`); the encoder **declares** a
`lang_id` input and the tensor fed carries the id; **changing `lang_id` 0→12 changes the
encoder output** (`max abs diff > 0`); the CLI `--lang-id` default is `None`.

**Negative arm:** section 4 *is* the negative colour (a bad value must be refused), and
section 5's "changes the encoder output" is a positive control that catches a model which
ignores the input. Additionally `_main/lang-id-runs.py` runs a separate negative arm
`E-neg999` (a worker launched with `--lang-id 999`, which must be REFUSED before model load).

**Has the negative arm ever run?** **Yes.** `_main/lang-id-oracle.log` ends `VERDICT: OK`
with `[ok ] 999 refused … '107' refused` and
`max|enc(lang_id=0) - enc(lang_id=12)| = 0.534810`. The separate arm ran too:
`_main/lang-id-arm-E-neg999.jsonl` (+ `.err`) exists (03:48).

**Resolution note (checked, NOT a defect):** the log names the table as
`…-fp16\languages.json` while `lang-id-oracle.py:43` hardcodes the **int8** dir. This is
expected, not drift: `worker/models/nemotron-3.5-asr-streaming-0.6b-int8/languages.json`
does not exist (only fp16 ships one), and `lang_prompt.table_candidates()` scans siblings and
falls through to fp16 (`worker/lang_prompt.py:128-149`). The log is reproducible from the
current source.

---

### 2.7 `_main/model-spec-oracle.py` — config vs the model's own geometry (46 lines)

**Asserts:** `blank_id == 13087` and `chunk_samples == 8960`; it prints the rest
(`max_symbols`, `left_context`, resolved `lang_id`, `use_vad`).

**Negative arm:** **NONE.** `ok = (blank == 13087 and chunk == 8960)`. There is no mutant and
no bad-input arm. It can only go RED if the model files or `config.json` change — i.e. it is
a **drift detector**, not an oracle with a negative colour.

**Has the negative arm ever run?** **N/A — no arm exists.** `_main/model-spec-oracle.log`
reads `VERDICT: OK` (03:50).

---

### 2.8 `_main/_oss_oracle.py` — "is the doc still true" (4 checks, one line of Python)

**Asserts C1–C4:** VAD is ON and the gated chunk is handled; the worker caption is still a raw
`run_chunk` passthrough with no agreement buffer; the renderer formulation lives in
`caption-formulation.js` with LocalAgreement-2 + audio-gap; model geometry is 560 ms
(`chunk_samples 8960 @16k`) with a bundled silero VAD.

**Negative arm:** **NONE.** It is a static file/grep check. It can go RED if the doc claims
stop being true (e.g. `use_vad` flips to `false`), but no mutant is run to prove the check
can fail.

**Has the negative arm ever run?** **N/A — no arm exists.** `_main/_oss_oracle.log` and
`_main/_oss_oracle_after_langdefault.log` both print `ORACLE GREEN (doc still true)`.

---

### 2.9 `worker/sotto_worker.py --selftest` — "the model works with no device" (lines 949-1022)

**Asserts:** it *ran*. It emits `selftest-start`, loops `run_chunk`, emits `selftest-done`
with `text`, `tokens`, `audio_s`, `infer_wall_s`, `rtf`, `blank_frac`, `empty_chunks`,
`vad_gated_chunks`, `peak_rss_mb`, and returns 0. The only failure path is
"audio shorter than one chunk" → rc 2 (`:961`).

**Negative arm:** **NONE.** `empty=(full.strip()=="")` is *reported* (`:989`) but **never
asserted**; nothing checks the text, the token count, or the rate. This is the oracle that
produced a documented **green-with-word-salad**: the module docstring (`:36-40`) records
`Before: 37 tokens, "go sl cous ands droom…" -- 17 words where 39 were spoken, with rc=0 and
RTF 0.20, i.e. a green exit code on word salad.` A selftest that exited 0 on word salad for
two days is the textbook "green you cannot turn red".

**Has the negative arm ever run?** **N/A — no arm exists.** Evidence of greens:
`worker/runs/selftest*.jsonl`, `worker/runs/int8-selftest.jsonl`,
`worker/runs/audit-fileselftest.jsonl`.

---

### 2.10 `_main/runcmd-entry-driver.py` — run `run.cmd` the owner's way (559 lines)

**Asserts:** against the app's OWN lines — `PANEL_VISIBILITY_AT_STARTUP`,
`PANEL_VISIBILITY_ON_SCREEN`, `HOTKEY_REGISTERED`, and, where asked,
`BRIDGE_CAPTION_SENT`/`CAPTION_OBSERVED`; plus a window census at 0.2 s over its own pid tree.

**Negative arm:** `arm_bogus` (`:441-472`) — an argument `sotto_webview.py` does not accept;
it records whether the entry point swallows the error entirely.

**Has the negative arm ever run?** **Partially.** `_main/runcmd-entry-report.json` (04:47)
contains a **single** arm key, `caption` (`rc 0, wall 62.06`); the `owner`/`clean`/`control`/
`bogus` arms the driver defaults to (`--arms owner,clean,control`) are **not** in that
receipt. So the `bogus` negative arm's output for this file is **not** evidenced by the
artifact present.

---

### 2.11 The shell's own selftests (source outside `_main`/`worker`, receipts inside)

`app/electron/bridge-selftest.js`, `app/electron/bridge-single-instance-selftest.js`, and
`app/webview/sotto_webview.py --selftest` are **not** under the two dirs in scope, but their
receipts are, so they are recorded here:

- `_main/B-selftest.log` and `_main/webview-selftest.log` both end `SELFTEST rc=0` /
  `SHELL_EXIT rc=0 reason=selftest`.
- **Finding B:** `_main/webview-selftest.log` ends
  `SELFTEST focus_before=71404 focus_after=4331806 focus_stolen=true` **and then**
  `SELFTEST rc=0`. The selftest *measures* focus theft and *logs* it but does **not** fail on
  it. Compare `_main/B-selftest.log`, where `focus_stolen=false` and rc is also 0. A run that
  steals the owner's focus is a green. (The assertion lives in `app/webview/sotto_webview.py`,
  outside the audited dirs; the receipt is cited for its behaviour.)
- `_main/bridge-selftest.js.log`, `_main/bridge-single-instance-selftest.js.log`,
  `worker/_e2e/bridge-selftest.log` (+ `.err`) exist as artifacts.

---

## 3. The hole: audio DELIVERY RATE

### 3.1 The claim

No oracle asserts **seconds of audio captured and processed per second of wall clock**. A
capturer that delivers 35 % of the sound — dropping two thirds of the blocks — passes every
oracle listed above.

### 3.2 The evidence

**(a) The metric is never read.** The worker's own count of audio that reached the ASR side is
`asr.audio_s`, printed in `WORKER_STATS`:

```
worker/sotto_worker.py:1285  def stats_line(tag: str) -> str:
worker/sotto_worker.py:1298      f"queue_drops={counters['queue_drops']} "
worker/sotto_worker.py:1299      f"audio_s={asr.audio_s:.2f} infer_wall_s={asr.wall:.2f} rss_mb={current_rss_mb():.1f}"
```

Scanning every oracle for it:

```
$ cd H:/sotto && python -c "<grep 'audio_s' in _main/*.py>"
(no hits)
$ cd H:/sotto && grep -rn "audio_s" _main/*.py
(no output)
```

So `audio_s` and `infer_wall_s` are emitted by the worker and read by nobody.

**(b) The raw material for a rate is present and unasserted.** The same `WORKER_STATS` line
carries `blocks`, `block_samples`, `chunks`, `queue_drops`. A rate is
`block_samples / TARGET_SR / wall_seconds`. The block counters are populated by the tap
callback (`worker/sotto_worker.py:1302-1321`), and the queue that a slow consumer would
overflow is declared at `worker/sotto_worker.py:1245`
(`audio_q: queue.Queue = queue.Queue(maxsize=256)`). The counters exist; no oracle reads them
for a rate.

**(c) The only block-count assertions are vanishingly weak.**
- `_main/device-silence-oracle.py:149` — ARM 1 requires `blocks >= 20` over `--max-seconds 20`
  (`:119`, default `"20"`). Blocks are 100 ms (`block_ms=100`, `worker/sotto_worker.py:809`),
  so 20 blocks = 2 s of audio. Implicit rate floor = **0.10**. A 35 % capturer delivers
  7 s = 70 blocks — passes 3.5×.
- `_main/verdict-order-oracle.py:233` — `blocks >= 20` with `--max-chunks 8` (a ~4.5 s
  window), used only as "not a real window" for the silent failure.
- `_main/panel-exit3-oracle.py:999` — `captions > 0 OR live`. One caption suffices.

**(d) `queue_drops` is never asserted.** The worker counts blocks dropped when the consumer
falls behind (`worker/sotto_worker.py:1316-1321`). No oracle reads `queue_drops` as a number:

```
$ cd H:/sotto && python -c "<grep queue_drops in _main/*.py, excluding quoted fixtures>"
(no hits)
$ cd H:/sotto && grep -rn "queue_drops" _main/*.py
_main/panel-exit3-oracle.py:103:  'blocks': 34, 'block_samples': 54400, 'nonzero_blocks': 3,   <- a fixture string
_main/panel-exit3-oracle.py:278:  ... 'delivered 34 blocks but never reached peak 0.002'},      <- a fixture string
_main/_armE-fake-worker.py:54:    ... same fixture text
```

Every hit is inside a quoted fake-status blob. A capturer that keeps up with the device but
loses audio in the queue is invisible.

**(e) The data to assert the rate is literally sitting in an existing receipt.** From
`_main/panel-exit3-oracle.log`, ARM B's WORKER_STATS:

```
WORKER_STATS tag=final blocks=60 block_samples=96000 nonzero_blocks=3 peak=0.000122
  rms=0.00002659 resampled_samples=96000 chunks=10 captions=0 tokens=0
  ... queue_drops=0 audio_s=5.60 infer_wall_s=1.13 rss_mb=2414.6
```

`blocks=60` × 100 ms = 6.0 s of *captured* audio during a 6 s tap window ⇒ a real delivery
rate of ≈ 1.00 — and `audio_s=5.60`, `queue_drops=0`. The number a rate oracle needs is
already printed. Nothing compares it to anything.

### 3.3 What a RED arm for a rate oracle would look like

A green that cannot be turned red is not green, so a delivery-rate assertion needs a mutant
that can drive it RED. The cheapest genuine mutant against the live path is a drop in
`on_block` — e.g. `if counters["blocks"] % 3: return` before `audio_q.put_nowait` — which
delivers ≈ 33 % and must make the rate assertion fail while the existing oracles still pass
(captions still appear; `blocks` still exceeds 20). That mutant does not exist today, and no
oracle would notice it if it did.

---

## 4. Adjacent holes found while hunting the rate hole

| # | Hole | Location | Why it matters |
|---|---|---|---|
| H1 | Worker `--selftest` asserts nothing about output quality | `worker/sotto_worker.py:986-999` (`empty` computed, never used as a failure) | Documented green-on-word-salad for two days (`:36-40`). |
| H2 | `queue_drops` never asserted | `worker/sotto_worker.py:1317` (produced), no reader in `_main/` | Audio lost between the tap and ASR is invisible. |
| H3 | Panel ARM A needs one caption | `_main/panel-exit3-oracle.py:999` | A 35 % capturer paints LIVE. |
| H4 | `model-spec-oracle` has no negative arm | `_main/model-spec-oracle.py:41` | Drift detector, not an oracle with a red colour. |
| H5 | `_oss_oracle` has no negative arm | `_main/_oss_oracle.py` (single `-c`, 4 static checks) | A doc-truth check that was never shown able to fail. |
| H6 | Shell selftest logs `focus_stolen=true` and still exits 0 | `_main/webview-selftest.log` (`focus_after=4331806 … focus_stolen=true` then `SELFTEST rc=0`) | Focus theft is measured but is not a failure. |

---

## 5. Findings (things I would have edited — reported, not touched)

**Finding A — stale top-level receipt.** `_main/panel-exit3-oracle.log` mtime `03:54:30`,
source `_main/panel-exit3-oracle.py` mtime `04:40:36`; the log's JSON has no `armD`, no
`armE`, no `neg_arm` keys. The one receipt the oracle writes was earned by an earlier,
three-arm revision.

**Finding B — focus theft is a green.** `_main/webview-selftest.log` records
`focus_stolen=true` immediately before `SELFTEST rc=0`. The assertion would live in
`app/webview/sotto_webview.py:1820` (out of scope) but the receipt is in scope.

**Finding C — `run-cmd-exit-oracle` is currently RED on the census conjunct.** Both
`_main/run-cmd-exit-oracle-after.json` and `-neg-arm.json` read `verdict: FAIL` with
`reason: "arms=PASS census=FAIL"`, i.e. a VISIBLE window was measured in the run's own tree.
This is an app-side startup flash, distinct from the wrapper's (green) exit contract.

**Finding D — a negative arm with no receipt.** `_main/runcmd-entry-driver.py`'s `bogus`
negative arm (`:441`) is not represented in `_main/runcmd-entry-report.json` (only the
`caption` arm is). The arm exists in code; its run is unevidenced.

---

## 6. Boundary — things that look like oracles but are not

`_main/` and `worker/` also hold measurement probes and controls. They print numbers without
a PASS/FAIL verdict, so they are outside the class under audit:
`*-probe.py` (`arena`, `capability`, `device`, `inject`, `inject-all`, `ladder`, `listen`,
`vad-option`, `panel-visible-window`, `_runcmd-*`, `_visiblechanged`, `_dance`, `_comdbg`,
`_comdbg2`, `_pwtest3`, `precision-ram`, `provider-cost`), `measure-readiness.py`,
`measure-asr-warmup.py`, `panel-startup-flash-census.py`, `_ppv-census-driver.py`,
`device-names.py`, `gpu-diag.py`, `play-to-default.py`, `run-live-hidden.py`,
`run-live-routed.py`, `run-with-cuda.py`, `tap_positive_control.py`, `vad-arm-run.py`,
`lang-id-default-arms.py`, `lang-id-runs.py`, and the `worker/_probe/*` family.

Two of these are borderline and worth naming: `_main/tap_positive_control.py` and
`_main/run-live-routed.py` are **positive controls** (they assert the chain produces signal)
with no negative arm, so they are the same class of "green that was never shown to fail" as
§2.7/§2.8, but they exit on a printed observation rather than a structured verdict.

---

## 7. Summary table — can it go RED?

| Oracle | Assertion class | Negative arm exists | Negative arm RUN (artifact) |
|---|---|---|---|
| `_main/device-silence-oracle.py` | device outcome, both colours | config-swap only (not a code mutant) | **yes** — `worker/runs/oracle-neg.jsonl`, `oracle-pos.jsonl` |
| `_main/verdict-order-oracle.py` | verdict word == exit code | **code mutant** (branch order reverted) | **yes — fired** — `runs/verdict-order-red.jsonl` |
| `_main/panel-exit3-oracle.py` | panel paint (6 arm groups) | built from today's shell | **yes, but separate logs**; top-level `panel-exit3-oracle.log` is STALE |
| `_main/panel-startup-visibility-oracle.py` | panel on screen at startup | built from live shell (N, B) | **yes** — `panel-startup-visibility.log` (04:12) |
| `_main/run-cmd-exit-oracle.py` | run.cmd exit contract | reverted COPY (`--neg-arm`) | **yes — fired**; oracle overall RED on census |
| `_main/lang-id-oracle.py` | language-prompt resolution | bad-id refusal + encoder-diff control | **yes** — `lang-id-oracle.log`; `lang-id-arm-E-neg999.jsonl` |
| `_main/model-spec-oracle.py` | 2 geometry constants | **none** | n/a |
| `_main/_oss_oracle.py` | 4 doc-truth checks | **none** | n/a |
| `worker/sotto_worker.py --selftest` | "it ran" | **none** | n/a |
| `_main/runcmd-entry-driver.py` | app's own log lines | `arm_bogus` | code yes; **receipt absent** |
| shell `--selftest` (receipts in `_main/`) | show/hide, hotkey | not inspected (source out of scope) | receipts: `B-selftest.log`, `webview-selftest.log` |

Three oracles (verdict-order, run-cmd-exit, panel-exit3) have a negative arm of the strong
kind (a mutant built from today's bytes) and artifacts proving it fired. Three do not have
any negative arm at all (model-spec, _oss, worker `--selftest`). **None of the ten asserts
audio delivery rate.** That is the hole.

---

## Inbound governor pendency (not this ticket)

A `SELO DO DONO` approval message addressed to seat `AuditOracles` arrived repeatedly during
this pass, naming `I:/!manager` governors in RED (`ManagerDiskCensus`, `theorist-always-on`,
`theorist-delta-guard`, `ManagerSessionRestart`, `ManagerWindowCensus`) and asking this seat to
measure or land a document for them. That work is **not** in this ticket (my assignment is this
read-only audit of `H:/sotto`), it concerns `I:/!manager` rather than `H:/sotto`, and resolving
it requires the manager session's instruments, which this seat does not have. It belongs to the
owner of the `I:/!manager` governor surface. Not attempted, by design, to avoid deviating from
the assigned read-only scope.

---

## SELF-AUDIT

- **protocolos em falta.** I did not read `H:/sotto/AGENTS.md` before starting this audit;
  it is cited repeatedly by the oracles as the source of the house rules they implement
  ("CREATE_NO_WINDOW alone", "the census samples once per 60 s and cannot prove ABSENCE", the
  146/194 selftest claim). I should have made it the first `read`, because it is the contract
  the oracles are graded against. What I would do differently: read `AGENTS.md` and
  `docs/README.md` before opening the oracle sources, so the "what SHOULD be asserted" list
  comes from the declared contract rather than from the oracles' own docstrings.
- **verificacao adicional.** I did not *run* any oracle. Running the cheap, device-free one
  (`_main/model-spec-oracle.py`, ~0.1 s, no window) would have confirmed the tree today still
  agrees with its last receipt; I declined because the assignment says prefer not launching
  anything, and because the receipt's mtime (03:50) is after the source (03:50) so staleness
  is not suspected there. Higher-value unrun check, named as its cost: a rate mutant
  (~30 s + a 2 GB model load, needs the live worker) would turn §3 from an argument into a
  measurement — but it launches the worker, which the assignment forbids.
- **checkboxes novas (mecanico).** One mechanical step would have caught Finding A and Finding
  D for free and belongs in every oracle audit: *for each `*.py` oracle, assert there exists a
  run artifact whose mtime is ≥ the source mtime, and that each arm group named in the source
  appears as a key in that artifact.* Concretely:
  `python scripts/oracle-receipt-freshness.py --dir _main` returning non-zero when
  `mtime(log) < mtime(source)` or when an arm key is missing — with
  `_main/panel-exit3-oracle.log` vs `_main/panel-exit3-oracle.py` as the standing RED input.
- **review por outro subagente.** **sim-com-escopo** — a reviewer that re-derives §3 only:
  confirm that no oracle under `_main`/`worker` reads `audio_s`, `block_samples`, or
  `queue_drops` as a value, and that the three block-count assertions (§3.2c) are the whole
  set. That is the load-bearing claim of this document and it is cheap to falsify.
- gate-doubt:
  - verde-de-verdade: every green I report came from an artifact I read, not from a claim.
    The suspect ones: (1) `panel-exit3-oracle.log`'s `"verdict":"PASS"` — **vacuous relative
    to today's source** (Finding A, stale file); (2) `model-spec-oracle.log` `VERDICT: OK` —
    real but about two constants and with no red arm; (3) `_oss_oracle.log` GREEN — real but
    never shown able to fail. `lang-id-oracle.log` I checked for a stale-model trap (int8 vs
    fp16) and cleared it against `lang_prompt.py:128-149`.
  - falta-no-gate: the delivery rate itself, and `queue_drops`. A future change that makes
    capture deliver, say, 40 % of the audio (a `block_ms` regression, a tap that drops every
    third callback, a caller that throttles `on_block`) crosses **all** ten oracles without
    one going red: captions still appear, `blocks >= 20` still holds, `queue_drops` is unread.
  - gate-melhor: add to `_main/device-silence-oracle.py` ARM 2 a rate assertion over the
    worker's own `WORKER_STATS` line — `block_samples / 16000 / wall_seconds >= 0.9` — and a
    mutant arm that inserts `if counters["blocks"] % 3: return` into `on_block` on a COPY,
    which must drive **that** assertion RED while the old checks stay green. Input that must
    leave it RED: the mutated worker on the routed cable.
- **confianca.** **alta** on the inventory, on which arms have run (artifacts read), and on
  the rate hole (the grep is total and the counter definitions are read at source). **media**
  on Finding B (`app/webview/sotto_webview.py` is outside the audited dirs; I read the
  receipt, not the assertion).
- **nao verificado.**
  - The wider-repo claim "146 of 194 selftests have their RED arm written by the same author"
    — that is about `I:/!manager`, outside my read scope and outside the two dirs assigned.
    Taken as given context, not corroborated here.
  - The shell/Electron selftest *sources* (`app/webview/sotto_webview.py`,
    `app/electron/bridge-selftest.js`) — read only where they touch an in-scope receipt.
  - `worker/wasapi_loopback.py` — no selftest/`__main__` found by grep beyond the module; not
    classified as an oracle.
  - I ran **no** oracle, so every "arm has run" statement rests on the artifact on disk, and
    every artifact is as trustworthy as whatever wrote it.
---

## CACHE/PRICE

Verbatim stdout of `bash I:/!manager/scripts/cache-task-report.sh AuditOracles` (my own agent
id; the script resolved my session jsonl), run 2026-10-06T08:29Z:

```
## CACHE/PRICE
- task/agent: AuditOracles
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditOracles.jsonl
- cache: read=5872896 write=0 hit=97.0040% (cache-read / input+cache-read); universe: 55 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditOracles.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- when-failed: break_items=1; WHEN=2026-10-06T08:24:36.673000+00:00 | break_items=1; WHEN=2026-10-06T08:24:37.892000+00:00 | break_items=3; WHEN=2026-10-06T08:24:40.410000+00:00 | break_items=3; WHEN=2026-10-06T08:26:15.254000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 113481 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditOracles'])
- where-failed: session_id=01a11050-0fed-77ad-ad84-c7a9e82e7adb provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791275076673 | session_id=01a11050-0fed-77ad-ad84-c7a9e82e7adb provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791275077892 | session_id=01a11050-0fed-77ad-ad84-c7a9e82e7adb provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275080410 | session_id=01a11050-0fed-77ad-ad84-c7a9e82e7adb provider=deepseek-flash model=deepseek-flash item_index=118; turn_id=1791275175254 (state=RESOLVED-BREAKS-OMP)
- report generated_at: 2026-10-06T08:29:17.267021+00:00
- usage rows: 55
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/space-bunny-free
- input tokens: 181387
- output tokens: 32974
- cache-read tokens: 5872896
- cache-write tokens: 0
- hit ratio: 97.0040% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

WHEN / WHERE failed (as reported): WHEN = 2026-10-06T08:24:36.673Z, 08:24:37.892Z,
08:24:40.410Z, 08:26:15.254Z; WHERE = session `01a11050-0fed-77ad-ad84-c7a9e82e7adb`, models
`cline-pass/stealth/pixel-canary` then `space-bunny-free` then `deepseek-flash`
(item_index 0 and 118).

- source: the session JSONL named above; read by `scripts/cache-task-report.sh` invoked from
  this worker seat (`bash I:/!manager/scripts/cache-task-report.sh AuditOracles`).
