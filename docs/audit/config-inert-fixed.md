# `worker/config.json` inert keys, the wrong-model provider probe, and the audio DELIVERY-RATE oracle

**Lane:** SottoConfigInert. **Date:** 2026-10-06. **Repo:** `H:\sotto` (working tree; both target files were
uncommitted before and after this lane — see §6 for hashes).
**Closes:** ticket **#614** (inert keys + provider probed on the wrong model) and **#610** (no oracle
asserted the audio delivery rate).
**Reads from:** `docs/audit/model-config.md` (the audit that named each defect) and `docs/audit/oracles.md` §3
(the audit that named the rate hole).

**Files touched**

| file | change |
|---|---|
| `worker/config.json` | 5 inert keys **deleted**; `audio.block_ms` and `output.min_chars` **wired**; two `_comment_live` notes added |
| `worker/sotto_worker.py` | `DEFAULT_MODEL` now int8; `choose_providers(requested, model_dir)` probes the CONFIGURED model and returns it; `cuda_probe_model` emitted; `audio.block_ms` passed to `LoopbackTap`; `output.min_chars` applied by both caption emitters |
| `worker/README.md`, `AGENTS.md` | the config key lists now match the file |
| `_main/delivery-rate-oracle.py` | **NEW** — the #610 oracle (`audio_s / wall_s >= 0.95`, `queue_drops == 0`) |
| `_main/config-keys-oracle.py` | **NEW** — the mechanical gate for (a)+(b): every leaf key has a reader; `DEFAULT_MODEL` agrees with `config.model.dir` |
| `_main/dr-ring-probe.py` | **NEW** — measures the WASAPI capture ring in ms (explains the pump mutant) |
| `docs/audit/config-inert-fixed.md` | this file |

---

## 0. Verdict

- **(a) inert keys** — 5 **deleted** (`audio.match`, `audio.sample_rate`, `audio.channels`, `audio.latency`,
  `output.partial`), 2 **wired and proven to move behaviour** (`audio.block_ms`, `output.min_chars`).
  Proved twice: by output (`capture-started.block` 4800 → 2400; 3 captions → 2 captions) and by a new
  mechanical gate that goes RED on an inert key.
- **(b) wrong model probed** — the CUDA liveness probe now opens `os.path.join(model_dir, "joint.onnx")`,
  the export the run will load, and names it in the `providers` status; `DEFAULT_MODEL` now names the same
  directory as `config.model.dir` (int8). Proved by calling `choose_providers` with two different model dirs.
- **(c) the missing oracle** — `_main/delivery-rate-oracle.py` exists, reads the counters the worker already
  printed, and is a **green that goes red**: live arm GREEN at duty 0.96–0.97, control (WAV) GREEN, and two
  LIVE mutant arms RED (0.7751 and 0.2935). `--selftest` passes, including the required "control arm goes RED
  if you invert the threshold".

---

## 1. Defect (a) — seven keys that pretended to configure something

### 1.1 Decision, per key, and why

| key (shipped value) | choice | why |
|---|---|---|
| `audio.match: "heuristic"` | **DELETE** | The name heuristic is applied **unconditionally** (`heuristic_loopback_score`, called for every device). There is no branch on this key and no alternative implementation to select — wiring it would mean **inventing** a second matching mode nobody asked for. Deleting removes the pretence that the mode is selectable. |
| `audio.sample_rate: 16000` | **DELETE** | Three other places already declare the sample rate and they are the authority: the model's own `genai_config.json`, its `audio_processor_config.json`, and the capture constant `TARGET_SR = 16000`. Wiring this key would let a config edit change the rate while the model keeps its own — silently corrupting the mel front end. |
| `audio.channels: 1` | **DELETE** | Channels is hardcoded by contract: the PortAudio tap opens `channels=1`, and the WASAPI tap mixes the endpoint's N channels to mono. Nothing reads the key; wiring it would let a config value contradict the loopback mix format. |
| `audio.latency: "low"` | **DELETE** | Nothing anywhere maps `"low"`/`"high"` to anything — a leftover of an earlier PCM design. There is no behaviour to wire it to. |
| `output.partial: false` | **DELETE** | No consumer, and the streaming product's whole point is that captions are emitted as they arrive. The opposite behaviour would be a new feature, not a wiring. |
| `audio.block_ms: 100` | **WIRE** | It was **already** a function parameter (`LoopbackTap(..., block_ms=100)`, `WasapiLoopbackTap(block_ms=100)`) — only the **call site** passed none, so the parameter default always won. Wiring it names the effective value instead of inventing one, and it is the same knob the WASAPI pump derives its poll period from. |
| `output.min_chars: 1` | **WIRE** | Both emitters used `if text.strip():`, i.e. an implicit threshold of **1 character**. Reading the key makes that implicit 1 explicit and configurable; a value below 1 is refused back to 1 **loudly**, not silently clamped. |

No loader anywhere accepted the deleted keys (re-verified at this revision, §1.3), so deleting them from
`config.json` is the whole fix for those five.

### 1.2 The wire, and the proof it changes behaviour

`worker/sotto_worker.py`:

- `audio.block_ms` → read into `block_ms`, validated, passed at the call site:
  `tap = LoopbackTap(dev, on_block, block_ms=block_ms)`.
- `output.min_chars` → read into `min_chars`, validated, and applied by **both** emitters:
  `selftest(asr, audio, args, min_chars)` and the live `asr_thread` (`if len(text.strip()) >= min_chars:`).

One variable per run, two runs per knob, same machine, same model:

```
$ pythonw worker/sotto_worker.py --config worker/config.json        --max-seconds 3 --tap-window 3 --stats-interval 0
$ pythonw worker/sotto_worker.py --config _main/config-block50.json --max-seconds 3 --tap-window 3 --stats-interval 0
proof-blocks100: capture-started rate=48000 block=4800
proof-blocks50: capture-started rate=48000 block=2400

$ SOTTO_AUDIO_FILE=_main/pt-br-sample.wav pythonw worker/sotto_worker.py --config worker/config.json
$ SOTTO_AUDIO_FILE=_main/pt-br-sample.wav pythonw worker/sotto_worker.py --config _main/config-minchars8.json
proof-mc1 (config worker/config.json): 3 captions: ['O rádio', 'Segunda-feira', 'Os moradores']
proof-mc8 (config _main/config-minchars8.json): 2 captions: ['Segunda-feira', 'Os moradores']
```

`4800 frames @ 48 kHz = 100 ms`, `2400 = 50 ms` → `audio.block_ms` is now the tap's block. And the caption
whose trimmed length is 7 (`"O rádio"`) is suppressed at `min_chars=8` and kept at `min_chars=1` → the key
is the emitter's threshold. (The two config fixtures are in-memory copies of the shipped file with exactly
one key changed: `_main/config-block50.json`, `_main/config-minchars8.json`.)

### 1.3 The deleted keys have no reader — re-verified at this revision

```
python - <<'PY'   # access forms .get("<key>") / ["<key>"] over worker/ + app/, code files only
...
_main\config-vad-off.json: "match"      <- a stale CONFIG FIXTURE for another oracle, not a reader
_main\lang-id-config-13.json: "latency" <- idem
worker\runs\oracle-neg-config.json: ... <- idem (fixture)
worker\sotto_worker.py: min_chars       <- the WIRE this lane added
worker\wasapi_loopback.py: "channels"   <- self.ep.channels, the ENDPOINT's channel count
probe\tap_probe.py: "channels"          <- idem
docs\model-specs\original\*/genai_config.json: "sample_rate"  <- the MODEL's own config
PY
```

Every remaining hit is a **model** config, an **endpoint** attribute, or a stale **fixture** — no worker code
reads any of the five deleted keys. The fixtures (`_main/config-vad-off.json`, `_main/lang-id-config-13.json`,
`worker/runs/oracle-neg-config.json`, `worker/runs/neg-only-silent.json`) are other lanes' copies of the old
file kept deliberately narrow; an unknown key is ignored by the loader, so they still work, but they are now
stale copies and are named here so nobody mistakes them for the shipped file.

---

## 2. Defect (b) — the CUDA probe opened a model the run never loaded

Two defects in one place (`docs/audit/model-config.md` §6.3, §6.5):

1. `choose_providers` built its probe path from the module constant:
   `os.path.join(DEFAULT_MODEL, "joint.onnx")` — so a run of the configured **int8** export proved CUDA on
   the **int4** graph.
2. `DEFAULT_MODEL = …-int4` while `config.model.dir = …-int8`: deleting `model.dir` silently substituted a
   different (smaller) model, contradicting `worker/README.md` and `AGENTS.md`.

Fixed by (i) pointing `DEFAULT_MODEL` at the **int8** directory the shipped config names, (ii) taking
`model_dir` as an argument and probing `os.path.join(model_dir or DEFAULT_MODEL, "joint.onnx")`, (iii)
returning that path and emitting it as `cuda_probe_model` in the `state="boot", stage="providers"` line, so
every run **says** which export it probed.

Proof — one function, three arguments, only the argument changed:

```
$ pythonw -c "... import sotto_worker as w; w.choose_providers(['cuda','cpu'], model_dir) ..."
config.model.dir            : models/nemotron-3.5-asr-streaming-0.6b-int8
sotto_worker.DEFAULT_MODEL  : worker\models\nemotron-3.5-asr-streaming-0.6b-int8
basenames equal             : True
choose_providers(model_dir=CONFIGURED (int8)                 ) probed=nemotron-3.5-asr-streaming-0.6b-int8/joint.onnx selected=['CPUExecutionProvider'] note='cuda-registered-but-not-loadable'
choose_providers(model_dir=a DIFFERENT model (int4)          ) probed=nemotron-3.5-asr-streaming-0.6b-int4/joint.onnx selected=['CPUExecutionProvider'] note='cuda-registered-but-not-loadable'
choose_providers(model_dir=no model_dir arg -> code fallback ) probed=nemotron-3.5-asr-streaming-0.6b-int8/joint.onnx selected=['CPUExecutionProvider'] note='cuda-registered-but-not-loadable'
```

The probe path **follows the argument** (int8 → int8, int4 → int4) and the no-argument fallback is int8,
i.e. it agrees with the shipped config. Note the CUDA `note` here: in this bare in-process call
`_add_cuda_dll_dirs()` has not run, so the provider cannot dlopen — that is an artefact of the proof harness,
not of the probe path under test; in a real run (which calls `_add_cuda_dll_dirs()` first) the same endpoint
selects `["CUDAExecutionProvider","CPUExecutionProvider"]` and `cuda_probe_model` reads
`nemotron-3.5-asr-streaming-0.6b-int8`.

And a REAL run names it (stdout, the `state="boot", stage="providers"` line):

```
$ pythonw worker/sotto_worker.py --config worker/config.json --max-seconds 2 --tap-window 2 --stats-interval 0
providers status now carries: ['cuda_dirs_ms', 'cuda_probe_model', 'providers_selected']
  cuda_probe_model = nemotron-3.5-asr-streaming-0.6b-int8
```

---

## 3. Defect (c) — the missing delivery-rate oracle (#610)

### 3.1 What it asserts, and the measurement law

```
audio_s / wall_s >= 0.95      AND      queue_drops == 0
```

`audio_s` and `queue_drops` are the counters `worker/sotto_worker.py` **already printed** in `WORKER_STATS`
(the `stats_line()` format string and the `on_block()` counters it reports) and in the `done` payload. The
oracle reads both and cross-checks them against each other (`WORKER_STATS.final vs done agree on audio_s`).
The brief's accounting hole — the one the audit named — was that **no file read those numbers**; now one does.

**The measurement law, honoured literally.** `wall_s` is the interval between the arrival of the worker's own
`{"state":"capture-started"}` (live arm) or `{"state":"selftest-start"}` (file arm) and `{"state":"done"}` /
`{"state":"selftest-done"}` — **never** process start. The worker's lines carry no clock, so the oracle
timestamps them as they arrive on the pipe. The startup (model load + device open + CUDA probe ≈ 5 s) is
therefore excluded, which is exactly what removes the FALSE duty ≈ 0.37 the diary records paying for twice.
Every ratio printed carries its numerator and denominator on the same line.

### 3.2 The arms — and the numbers

One command, four arms, no window (`pythonw`, children spawned with `CREATE_NO_WINDOW` alone):

```
$ pythonw _main/delivery-rate-oracle.py --all
```

```
# delivery-rate-oracle  2026-10-06T05:46:38  threshold=0.95  invert=False
# worker=H:\sotto\worker\sotto_worker.py

[PASS] ARM=live               duty = numerator audio_s=14.56 / denominator wall_s=15.09 = 0.9646  (threshold 0.95)  queue_drops=0 [WORKER_STATS.tag=final]
        tap: numerator block_samples/48000=15.10 / denominator wall_s=15.09 = 1.0004  (151 blocks x 4800 frames @48000 = 15.10 s; informational: what the tap handed over)
        WORKER_STATS.final vs done agree on audio_s: True
        open=(capture-started) end=(done) streams=1 rotations=0 rc=0
[PASS] ARM=wav-control        duty = numerator audio_s=15.12 / denominator wall_s=3.03 = 4.9885  (threshold 0.95)  queue_drops=0 [n/a (file arm has no queue)]
        open=(selftest-start) end=(selftest-done) streams=1 rotations=0 rc=0
[RED ] ARM=live-pump-mutant   duty = numerator audio_s=11.76 / denominator wall_s=15.09 = 0.7791  (threshold 0.95)  queue_drops=0 [WORKER_STATS.tag=final]
        tap: numerator block_samples/48000=12.40 / denominator wall_s=15.09 = 0.8215  (124 blocks x 4800 frames @48000 = 12.40 s; informational: what the tap handed over)
        WORKER_STATS.final vs done agree on audio_s: True
        open=(capture-started) end=(done) streams=1 rotations=0 rc=0
        REASON: duty 0.7791 >= 0.95 is false
[RED ] ARM=live-drop-mutant   duty = numerator audio_s=4.48 / denominator wall_s=15.25 = 0.2938  (threshold 0.95)  queue_drops=0 [WORKER_STATS.tag=final]
        tap: numerator block_samples/48000=15.20 / denominator wall_s=15.25 = 0.9967  (152 blocks x 4800 frames @48000 = 15.20 s; informational: what the tap handed over)
        WORKER_STATS.final vs done agree on audio_s: True
        open=(capture-started) end=(done) streams=1 rotations=0 rc=0
        REASON: duty 0.2938 >= 0.95 is false

VERDICT: RED
```

`VERDICT: RED` is correct for `--all`: it runs two arms that are *supposed* to be red. Run without `--all`
each arm is judged alone, so `pythonw _main/delivery-rate-oracle.py` (live) exits 0.

Reading of that transcript:

- **live** — the shipped worker, capture from the default render endpoint. GREEN, duty **0.9646**
  (the residual gap from 1.00 is the decoder's one-chunk buffer lag: the last <0.56 s of delivered audio has
  not yet been handed to `run_chunk` when the run ends; the *informational* tap ratio, `block_samples/rate`
  over the same wall, is **1.0004** — 151 blocks × 100 ms = 15.10 s captured in 15.09 s, which is the
  delivery itself, and it shows the loss is zero).
- **wav-control** — `SOTTO_AUDIO_FILE=_main/pt-br-sample.wav`. GREEN by a wide margin (**4.9885**): the file
  arm feeds the same `asr` object with no device and no queue, so it consumes 15.12 s of audio in 3.03 s of
  wall. It is the device-free control: it proves the oracle runs the real worker end to end when no endpoint
  can be opened, and its load-bearing role is the inverted-threshold arm in §3.3.
- **live-pump-mutant** — a **LIVE** run of a COPY of the worker whose `wasapi_loopback.py` is reverted to the
  pre-fix poll (`period = max(0.005, block_ms/1000/4)` = 25 ms). **RED at duty 0.7791** (124 blocks × 100 ms =
  12.40 s captured in 15.09 s). This is the defect class the audit measured at 0.815; a 15 s window plus the
  chunk lag puts it at 0.78, and the `tap` line (**0.8215**) shows the loss is **upstream of the queue**
  (`queue_drops=0`) — the capture ring overflow itself, not the consumer.
- **live-drop-mutant** — a **LIVE** run whose `on_block` discards 2 of every 3 blocks before the queue
  (the audit's own proposed mutant). **RED at duty 0.2938** — while the tap line stays at **0.9967** and
  `queue_drops` stays **0**. This is the arm that shows the oracle catches audio lost *between the tap and
  the decoder*, which is precisely what no existing oracle and no counter could see.

### 3.3 `--selftest`: the gate must be able to go RED

```
$ pythonw _main/delivery-rate-oracle.py --selftest
```

```
# delivery-rate-oracle  2026-10-06T05:48:21  threshold=0.95  invert=False
# worker=H:\sotto\worker\sotto_worker.py

== selftest: fixtures through the SAME evaluator ==
[PASS] ARM=fixture-green      duty = numerator audio_s=14.63 / denominator wall_s=14.83 = 0.9865  (threshold 0.95)  queue_drops=0 [synthetic]
        open=(synthetic) end=(synthetic) streams=1 rotations=0 rc=0
  fix-green: expected GREEN got GREEN -> ok
[RED ] ARM=fixture-lossy      duty = numerator audio_s=4.90 / denominator wall_s=14.83 = 0.3304  (threshold 0.95)  queue_drops=0 [synthetic]
        open=(synthetic) end=(synthetic) streams=1 rotations=0 rc=0
        REASON: duty 0.3304 >= 0.95 is false
  fix-lossy: expected RED got RED -> ok
[RED ] ARM=fixture-drops      duty = numerator audio_s=14.63 / denominator wall_s=14.83 = 0.9865  (threshold 0.95)  queue_drops=7 [synthetic]
        open=(synthetic) end=(synthetic) streams=1 rotations=0 rc=0
        REASON: queue_drops 7 != 0
  fix-mdrops: expected RED got RED -> ok

== selftest: the CONTROL arm (real run), then the same numbers inverted ==
[PASS] ARM=wav-control        duty = numerator audio_s=15.12 / denominator wall_s=3.19 = 4.7443  (threshold 0.95)  queue_drops=0 [n/a (file arm has no queue)]
        open=(selftest-start) end=(selftest-done) streams=1 rotations=0 rc=0
[RED ] ARM=wav-control        duty = numerator audio_s=15.12 / denominator wall_s=3.19 = 4.7443  (threshold 0.95, INVERTED)  queue_drops=0 [n/a (file arm has no queue)]
        open=(selftest-start) end=(selftest-done) streams=1 rotations=0 rc=0
        REASON: duty 4.7443 <= 0.95 is false
  ok: control GREEN under the shipped rule, RED when the threshold is inverted
  (control duty=15.12/3.186999999998079)

SELFTEST: PASS
```

Three synthetic fixtures go through the **same** evaluator (green / lossy / queue-dropped) and the control arm
is run for real, then evaluated twice: GREEN under the shipped `>= 0.95` and **RED when the threshold is
inverted**. That is the required "the control arm goes RED if you invert the threshold", and it is what makes
the shipped green non-vacuous: the threshold participates in the verdict instead of the oracle being
hard-coded green.

### 3.4 Why the reverted pre-fix poll is a valid RED here (and how the ring was measured)

`_main/dr-ring-probe.py` opens the same endpoint through the same module and reads the two numbers the audit
read:

```
$ pythonw _main/dr-ring-probe.py
{"hr_getbuffersize": 0, "hr_getdeviceperiod": 0, "ring_frames": 1056, "rate": 48000, "ring_ms": 22.0,
 "dev_period_default_ms": 10.0, "dev_period_min_ms": 3.0, "poll_ms_at_block100_fixed": 5.0,
 "poll_ms_at_block100_prefix": 25.0}
```

The ring is still **22.0 ms** and the shipped poll is **5 ms** (it drains the ring more than four times per
ring-fill); the reverted 25 ms poll is slower than the ring, which is why the pump mutant loses ~20 %.

### 3.5 A bug this lane made and caught

The `pump` mutant was first written with its replacement template **equal to its own anchor**, so
`str.replace` was a no-op and the "mutant" arm was the *fixed* worker — it came back GREEN (0.9646) and
would have been reported as "the historical defect no longer reproduces", which was **false**. The oracle now
refuses to run a patch that does not change the file (`patch was a NO-OP … refusing to run it`) and the
re-run is RED at 0.7751. Recorded because a mutant that silently equals the original is the same failure
mode as a gate that cannot fail.

---

## 4. The gate for (a) and (b): `_main/config-keys-oracle.py`

The audit's own SELF-AUDIT named this checkbox and said it could not land it ("the brief permits writing
exactly one file, and a gate is executable, not a `.md`"). This lane is that work, so it lands:

1. **every leaf key in `config.json` has ≥1 access form** (`.get("key")` / `["key"]`) in `worker/**/*.py`;
2. **`DEFAULT_MODEL` resolves to the same directory as `config.model.dir`**.

```
$ pythonw _main/config-keys-oracle.py
# config-keys-oracle  H:\sotto\worker\config.json
  key audio.device                 -> 7 consumer(s)  first: worker\sotto_worker.py:674
  key audio.preferred_devices      -> 1 consumer(s)  first: worker\sotto_worker.py:676
  key audio.block_ms               -> 2 consumer(s)  first: worker\sotto_worker.py:1276
  key model.dir                    -> 1 consumer(s)  first: worker\sotto_worker.py:1116
  key model.lang_id                -> 2 consumer(s)  first: worker\lang_prompt.py:11
  key model.use_vad                -> 1 consumer(s)  first: worker\sotto_worker.py:1185
  key model.providers              -> 1 consumer(s)  first: worker\sotto_worker.py:1190
  key output.min_chars             -> 2 consumer(s)  first: worker\sotto_worker.py:1128
  DEFAULT_MODEL agrees with config.model.dir: nemotron-3.5-asr-streaming-0.6b-int8
VERDICT: PASS
```

and it is shown able to fail (selftest plants one inert key and one model-name mismatch):

```
$ pythonw _main/config-keys-oracle.py --selftest
== selftest 1: an inert key must be RED ==
  RED: INERT KEY: 'output.definitely_inert' (json key 'definitely_inert') has 0 access forms (.get("definitely_inert") / ["definitely_inert"]) in worker/**/*.py
  planted key reported RED: True -> ok
== selftest 2: a DEFAULT_MODEL mismatch must be RED ==
  RED: DEFAULT_MODEL DISAGREES: code fallback 'nemotron-3.5-asr-streaming-0.6b-int4' != config model.dir 'nemotron-3.5-asr-streaming-0.6b-int8'
  planted mismatch reported RED: True -> ok
== selftest 3: the shipped config must be GREEN ==
  shipped config GREEN: True -> ok
SELFTEST: PASS
```

**Stated limit:** check 1 is a **string census**, not a dataflow proof. A zero hit means "no access form in
the worker sources", which is exactly the class that shipped seven dead keys; a key read through an
indirection would be a false RED. That direction is chosen deliberately: a false RED costs one grep, a false
green shipped seven keys that pretended to work.

---

## 5. What could NOT be verified, and why

- **The owner's production routing.** Every live-arm number here is from this box's default render endpoint,
  which was quiet (the tap measured blocks; no captions are claimed). The duty is a property of the tap, not
  of the audio content, but a run that actually carries speech was not part of this lane.
- **The PortAudio rung (`_PortAudioTap`).** Unreachable on this host (blocking reads unsupported; rung (a)
  always wins). The delivery-rate oracle measures whichever tap the ladder opens, so it would cover the
  PortAudio rung on a host where it opens — not exercised here.
- **The other two model exports' provider probes** were exercised only through `choose_providers` with an
  explicit `model_dir` (int4), not by loading them.
- **The stale config fixtures** (`_main/config-vad-off.json`, `_main/lang-id-config-13.json`,
  `worker/runs/oracle-neg-config.json`, `worker/runs/neg-only-silent.json`) still carry the five deleted
  keys. They are other lanes' fixtures; the loader ignores unknown keys, so they are harmless, but they now
  differ from the shipped file. Left untouched on purpose (other lanes and their receipts cite them).
- **`_main/delivery-rate-oracle.log`** is overwritten by each run; the transcripts pasted here are the
  per-run stdout captures (`_main/dr-*.out.txt`, `_main/proof-*`).

---

## SELF-AUDIT

- **protocolos em falta** — I did not hash-pin the audited revision before editing, although
  `docs/audit/model-config.md`'s own SELF-AUDIT names that as the thing it got wrong and I read it first.
  I collected hashes at the end (§6). What I would do differently: `sha256sum` the target and its consumers
  as the FIRST command, and re-assert at the end. Also missing from my own protocol, and worth naming: I had
  no rule that a MUTANT must be shown to have changed the file; §3.5 is what that cost.
- **verificacao adicional** — the cheapest check that would most raise confidence and that I did NOT run:
  put the *file* `pt-br-sample.wav` through the WASAPI tap + `resample_to_16k` and confirm the 3:1 boxcar
  path also delivers at duty ≈ 1.0 (cost: one more live run, ~20 s). I skipped it because the live arm
  already exercises the 3:1 path (48 kHz → 16 kHz, exact) and the control arm deliberately exercises the
  `np.interp` path; the two arms therefore cover both resample branches, but not the same branch through both
  drivers. Cheap enough to run; named rather than silently omitted.
- **checkboxes novas (mecanicas)** — (1) `_main/config-keys-oracle.py`, landed: every leaf key of
  `config.json` must have an access form in the worker, RED input = today's pre-fix file (it would have
  flagged exactly the seven), plus `DEFAULT_MODEL == config.model.dir`. (2) **A mutant must be proven to have
  changed the bytes** — `assert patched != original`, with RED input = the no-op patch this lane actually
  wrote (§3.5). (3) Any ratio in any receipt must print numerator and denominator on its own line, with the
  denominator measured from the stream-open event; a bare ratio is the defect the diary records twice.
- **review por outro subagente** — **sim-com-escopo**: (a) the delivery-rate oracle's verdict path, in
  particular whether `--selftest` can pass vacuously now that the pump mutant is a real RED (i.e. re-run
  `--all` and check the mutant arms are still RED after any future edit to `wasapi_loopback.py`'s period
  line, whose text the mutant anchors on); (b) the per-key delete-vs-wire table in §1.1, which is a judgement
  call and the cheapest thing in this file to disagree with. *Nao* for the pasted outputs: they are
  re-runnable (the commands are given) so a reviewer should re-run, not re-read.
- **gate-doubt**:
  - **verde-de-verdade:** the greens I claim: (1) the live arm, duty **0.9646**, **real** — the same command
    in the mutant arm reads 0.7791, and the tap line moves with it (1.0004 vs 0.8215), so the number moves
    with the code; (2) the WAV control, **real but weak by construction** — it is a faster-than-real-time file feed, so
    duty ≫ 1 and it can only ever show the oracle *runs*, never that a device delivers; its load-bearing role
    is the inverted-threshold arm; (3) `config-keys-oracle` PASS, **real but a string census** — the limit is
    stated in the file and here. The one green I explicitly do NOT claim: `_main/model-spec-oracle.log` and
    `_oss_oracle.log` were not re-run by me and are cited by nobody here.
  - **falta-no-gate:** the new oracle still does NOT check that the tap is **polling faster than the ring**:
    it checks the *outcome* (duty) not the *mechanism*, so on an endpoint whose ring is large enough a slow
    poll passes. A future change that makes `wasapi_loopback.py` request a bigger ring, or a driver that
    grants a 100 ms ring, would leave the pump mutant GREEN and the oracle would say PASS. Second hole: the
    oracle reads `WORKER_STATS tag=final`, and the audit's F5 (`tick` quoted as a run total) is still
    possible for any *other* reader — nothing in the gate checks that a consumer used `final`.
  - **gate-melhor:** close the first hole mechanically: in `wasapi_loopback._start()`, after
    `GetBufferSize`, assert `ring_frames / rate > poll_period` (or emit `ring_ms`/`poll_ms` into
    `capture-started`), and add `ring_ms <= poll_ms * 1000 -> RED` to the delivery-rate oracle's live arm.
    Command: `pythonw _main/dr-ring-probe.py` today prints `ring_ms 22.0` vs `poll_ms_at_block100_fixed 5.0`
    (passes); the input that must leave it RED is a `wasapi_loopback.py` whose `period` is `block_ms/1000/4`
    — which is exactly the `pump` mutant, and the ring probe's own `poll_ms_at_block100_prefix: 25.0` vs
    `ring_ms: 22.0` is that RED in numbers.
- **confianca** — **alta** for (a) and (b): each fix has an output that moves with the input, and a reverted
  configuration was measured going RED. **alta** for the mechanism of (c) (four arms, two of them RED, plus
  the ring measured at 22.0 ms against a 5 ms poll). **media** for the *live* duty as the owner will see it:
  one endpoint, quiet, one 15 s window, and the residual 0.03 gap is attributed to the decoder's chunk lag by
  arithmetic rather than by a run with `--max-chunks` that would pin it. What would move it to high: a live
  run carrying real speech with `--max-seconds 60`, where the chunk lag is bounded at <1 % of the window.
- **nao verificado** — (1) the PortAudio rung (§5); (2) a live run carrying speech; (3) the two other model
  exports loaded end to end; (4) whether any consumer outside `H:\sotto` reads the five deleted keys (searched
  the repo only, as the brief scopes me to it); (5) the stale fixtures were read but not updated; (6) the
  oracle's `done`-vs-`WORKER_STATS.final` agreement is a cross-check of two emitters of the same variable, not
  an independent measurement of the audio.

---

## 6. Revision pinned

Files were uncommitted before and after this lane. `sha256sum` at close:

```
39db0c7b21e986314ad80cb1a4bc949afbaa28c02f413883475e61ebaf6e66cf  worker/config.json
0bd24c2bb55a27773668554b049ffcb299c37b57025f0eac2f70ab79748f6ec4  worker/sotto_worker.py
85cda3671c611f45905ce0de83d747f2183e07782487030c64ee58e6b96500d1  worker/README.md
7456ec5514ddb6a05de9d8752cf813f15abd43489838166902b8b0c2f8a5eb06  AGENTS.md
ff97eb48dd46671f6173451000f4ab77c8b6d3aeb6ab1ffcdf31f89d7981b239  _main/delivery-rate-oracle.py
73f7f0f11022ac7d425e0492493517bb71ee3c71dde8e7fcfdaab0b01e679640  _main/config-keys-oracle.py
0e2475345a33e270c9b93d32fbba4bef0445853f53e78580f60b2dd8ad71e900  _main/dr-ring-probe.py
4e7784abb02a83b6540907e2cc1314fe056b5fdade2595bc10d549a20d6257d7  docs/audit/config-inert-fixed.md
```

(`docs/audit/config-inert-fixed.md`'s own hash is of the file **before** this line was inserted; the other
seven are the close-of-lane bytes. The doc is the only file that changes when a receipt is amended.)

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh SottoConfigInert` — output VERBATIM (the harness display caps
some lines at 768 bytes; every numeric field below is complete):

```
## CACHE/PRICE
- task/agent: SottoConfigInert
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoConfigInert.jsonl
- cache: read=10694656 write=0 hit=97.9166% (cache-read / input+cache-read); universe: 62 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoConfigInert.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=55 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 ou…[CORTADA, display cap]
- when-failed: break_items=1; WHEN=2026-10-06T08:36:19.930000+00:00 | break_items=1; WHEN=2026-10-06T08:36:20.572000+00:00 | break_items=1; WHEN=2026-10-06T08:36:21.306000+00:00 | break_items=3; WHEN=2026-10-06T08:36:21.770000+00:00 | break_items=2; WHEN=2026-10-06T08:38:26.509000+00:00 | break_items=1; WHEN=2026-10-06T08:43:27.283000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 113988 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoConfigInert']; window: 2026-10-06T08:36:19.930000+00:00..2026-10-06T08:43:27.283000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791275779930 | session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791275780572 | session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791275781306 | session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275781770 | session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=deepseek-flash model=deepseek-flash item_index=65; turn_id=1791275906509 | session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=deepseek-…[CORTADA, display cap]
- report generated_at: 2026-10-06T08:48:39.336324+00:00
- usage rows: 62
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 227555
- output tokens: 77911
- cache-read tokens: 10694656
- cache-write tokens: 0
- hit ratio: 97.9166% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=55 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; o…[CORTADA, display cap]
- prefix breaks: 9 (state=RESOLVED-BREAKS-OMP; population: 6 of 113988 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoConfigInert']; window: 2026-10-06T08:36:19.930000+00:00..2026-10-06T08:43:27.283000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T08:36:19.930000+00:00; WHERE session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791275779930
  - break_items=1; WHEN=2026-10-06T08:36:20.572000+00:00; WHERE session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791275780572
  - break_items=1; WHEN=2026-10-06T08:36:21.306000+00:00; WHERE session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791275781306
  - break_items=3; WHEN=2026-10-06T08:36:21.770000+00:00; WHERE session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275781770
  - break_items=2; WHEN=2026-10-06T08:38:26.509000+00:00; WHERE session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=deepseek-flash model=deepseek-flash item_index=65; turn_id=1791275906509
  - break_items=1; WHEN=2026-10-06T08:43:27.283000+00:00; WHERE session_id=01a1105b-3654-74b7-a228-24757f544f19 provider=deepseek-flash model=deepseek-flash item_index=199; turn_id=1791276207283
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

(WHEN/WHERE failed is present and complete; the partition and `when-failed` lines are the two the display cap
truncated, and both say so in place.)
