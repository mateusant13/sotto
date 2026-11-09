# The live engine's execution provider: CUDA vs CPU, measured (2026-11-09)

Lane `GpuLiveEngine`. Question: should the STREAMING engine (`StreamAsr` — encoder +
decoder + joint, 560 ms chunks, `worker/models/nemotron-3.5-asr-ptbr-onnx-int4`) run on
`CUDAExecutionProvider` or `CPUExecutionProvider`, and does the shipped code already
take the better one?

**ANSWER: CUDA wins on every axis that matters, the transcript is bit-identical, and the
shipped path ALREADY chooses it — no product edit is required.** Evidence below.

---

## 1. Where the provider is chosen at runtime today

| # | what | where |
|---|------|-------|
| 1 | the ONE call site that resolves the live engine's providers | **`worker/sotto_worker.py:6618-6620`** — `providers, available, note, cuda_probe_model = choose_providers(args.providers or cfg.get("model", {}).get("providers"), model_dir)` |
| 2 | the default when neither `--providers` nor the config names one | **`worker/sotto_worker.py:4489-4491`** — `auto = not req or "auto" in …` → `req = ["CUDAExecutionProvider", "CPUExecutionProvider"]` |
| 3 | the shipped config value | **`worker/config.json:18`** — `"providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]` (line 16 at HEAD; a peer's `audio.target_name` insert above it moved it to 18 — the VALUE is unchanged from HEAD) |
| 4 | the shell never overrides it | `app/webview/sotto_webview.py:21203` — `self.extra_args = tuple(extra_args or ())`, so the shipped argv is `[command, worker_path]`; `grep -n providers app/webview/sotto_webview.py` finds only the READ of `providers_selected` for the `WORKER_PROVIDERS` log line (line 22033-22035) |
| 5 | the warm-engine path | `app/webview/warm_engine.py:396` — `worker.choose_providers(None, self.model_dir)` → the same `auto` default |

Both sources rank CUDA first and keep `CPUExecutionProvider` as the fallback, so the CPU
path stays reachable three ways: `--providers cpu`, `model.providers` in
`worker/config.json`, and automatic fallback when the CUDA EP cannot dlopen
(`StreamAsr.provider_note` = `cuda-registered-but-not-loadable` says so out loud).

**Read back off the running product, not off the code** — `_main/webview-run.log`, the
last `WORKER_PROVIDERS` line, written while the owner's app was live:

```
2026-11-09 18:59:37.205 sotto: WORKER_PROVIDERS selected=CUDAExecutionProvider,CPUExecutionProvider
available=TensorrtExecutionProvider,CUDAExecutionProvider,CPUExecutionProvider note= cuda_probe=nemotron-3.5-asr-ptbr-onnx-int4
```

---

## 2. The instrument: `_main/live-engine-provider-ab.py`

One arm per PROCESS, on purpose: load seconds, peak RSS and process CPU% are per-process
numbers, and building both arms in one interpreter would bill the first arm's CUDA arena
to the second. The provider is resolved by the SHIPPED resolver (`choose_providers`), not
by a literal list written in the probe. The arm feeds the engine exactly what the live
loop feeds it: one 8960-sample chunk per `run_chunk`, 26 chunks, 3 passes, stream state
(`reset_stream_state()` + `reset_frontend()`) reset between passes.

**Fixture**: `_main/fixtures/stack-compare/ptbr-radio-14s.wav` — 661 544 B, 22050 Hz mono,
14.56 s, the repo's own reference clip (`reference.json` beside it). Resampled to 16 kHz
by the LIVE PATH's own function (`worker/sotto_worker.py:2587 resample_to_16k`, the
non-integer `np.interp` arm), not by a second convention in the probe.

**Command lines** (both arms, identical launcher, identical cage, identical thread plan):

```
PYTHONPATH=I:/!watcher python -m watcher run --cpu 40 -- python _main/live-engine-provider-ab.py --arm cpu  --out _main/_cache/provider-ab-cpu.json
PYTHONPATH=I:/!watcher python -m watcher run --cpu 40 -- python _main/live-engine-provider-ab.py --arm cuda --out _main/_cache/provider-ab-cuda.json
python _main/live-engine-provider-ab.py --compare _main/_cache/provider-ab-cpu.json _main/_cache/provider-ab-cuda.json
```

Both arms printed `WORKER_THREAD_PLAN encoder=4 small=1 sessions=3 total_intra=6`, i.e.
the SHIPPED thread budget (`DEFAULT_THREADS = 4`, `worker/sotto_worker.py:648-659`;
`--threads` was 0 = auto in both). The cage is 40 % of 20 logical cores ≈ 8 cores; the
CPU arm used at most 6.2 cores (`cpu_pct_one_core` 616.6), so **the cage never bound the
CPU arm** and did not buy CUDA its win.

---

## 3. The two-column table (paired run, 19:01–19:02, same cage, same audio, same code)

| metric | CPU | CUDA |
|---|---|---|
| providers selected (`session.get_providers()`) | `CPUExecutionProvider` | `CUDAExecutionProvider, CPUExecutionProvider` |
| **model load s** (3 sessions) | **1.085** | **1.713** |
| · of which encoder | 0.999 | 1.602 |
| front end s (`og.Model` + processor, not the provider's cost) | 1.532 | 1.574 |
| **chunk p50 ms** | **228.18** | **41.57** |
| **chunk p95 ms** | **293.92** | **52.45** |
| **chunk max ms** | **353.15** | **165.13** |
| pass-1 p50 ms (session warm-up) | 217.36 | 35.21 |
| **RTF** (decode wall / audio) | **0.4160** | **0.0772** |
| x real time | 2.40x | 12.95x |
| **CPU % of one core** (warm decode) | **616.6** | **650.5** |
| **RSS peak MiB** | **1536.0** | **1599.5** |
| **GPU total MiB** at start → end | 2845 → 4823 (other apps only) | 4823 → **6312** |
| our pid in `nvidia-smi --query-compute-apps` | **not listed** | **listed** (`pid_listed: true`) |
| GPU util machine-wide, max % during decode | 21 (all other apps) | **98** |
| stage enc ms/chunk | 174.5 | 35.2 |
| stage walk (decoder+joint) ms/chunk | 56.7 | 6.2 |
| **transcript sha256** | `c78010ab…6523bfc` | `c78010ab…6523bfc` |

### Replays (same commands, the box is the owner's and it is busy — that variance is itself a datum)

| run | arm | p50 ms | p95 ms | RTF | cpu % one core | load s |
|---|---|---|---|---|---|---|
| A 18:57 | cpu | 487.37 | 773.20 | 0.9254 | 434.9 | 5.726 |
| A | cuda | 36.98 | 54.17 | 0.0759 | 629.4 | 2.169 |
| B 19:00 | cpu | 864.56 | 1247.61 | 1.5873 | 277.1 | 2.279 |
| B | cuda | 34.59 | 48.21 | 0.0663 | 688.3 | 1.117 |
| **C 19:01 (table above)** | cpu | **228.18** | 293.92 | **0.4160** | 616.6 | 1.085 |
| C | cuda | **41.57** | 52.45 | **0.0772** | 650.5 | 1.713 |
| **speedup (cpu RTF / cuda RTF)** | | | | **A 12.2x · B 23.9x · C 5.4x** | | |

**Control: is the CPU arm thread-starved?** One more CPU arm at `--threads 16`
(`encoder=16 small=1 total_intra=18`, everything else identical — the shipped resolver, the
same cage, the same audio, 2 passes):

```
{"arm": "cpu", ... "p50_ms": 334.76, "p95_ms": 520.86, "rtf": 0.6269, "cpu_pct_one_core": 487.2, ...}
```

It is **worse** than the shipped 4-thread plan (228.18 ms / 0.4160): under the same 40 %
cage the extra threads oversubscribe and the process only got 4.9 cores instead of 6.2. The
CPU branch is not short of threads — it is on the wrong resource. (Even if it had matched
its own best, it would still be the 228 ms arm, 5.5x behind CUDA.)

The CPU arm's p50 spans **228 → 865 ms** across three runs of the identical file and code
(3.8x), and in runs A and B it does not hold real time at all (RTF 0.93 / 1.59 — a
14.56 s clip took longer than 14.56 s to decode, at p95 774 ms and 1248 ms per 560 ms
chunk). The CUDA arm spans **34.6 → 41.6 ms** (1.2x). The live engine's latency on CPU is
therefore a function of whatever else the owner's desktop is doing, which is exactly the
complaint the engine exists to answer.

**No loss in quality.** Both arms produced the identical byte string; the probe refuses to
print a verdict unless the hashes match (`compare()` returns 5 and says "the provider
CHANGED THE TEXT — a defect, not an optimisation"):

```
c78010aba9df3609b8e12870866e43e94fc50840b7193bff9e40878de6523bfc
```

```
Rádioanunciouquea pontesobre ovaiserinterditadanapróximasegunda-feira.  Osmoradoresprecim deum caminhoalternativopara chegarao trabalho
```

(`precim` is the model's own error, identical on both providers, and `pass1_equals_warm`
is `true` — every pass, both arms, all 78 decodes each.)

---

## 4. Did the CUDA branch really execute on the GPU?

Three independent checks, in this order of strength:

1. **`session.get_providers()` off the REAL encoder session** that decodes the audio:
   `['CUDAExecutionProvider', 'CPUExecutionProvider']` (the CPU arm answers
   `['CPUExecutionProvider']`). This is read back in `StreamAsr.__init__`
   (`worker/sotto_worker.py:1531`, `self.providers = self.enc.get_providers()`), not
   requested.
2. **`nvidia-smi` names this pid.** `--query-compute-apps=pid,used_memory` lists our pid
   (`pid_listed: true`) from the moment the sessions load, and does **not** list it during
   the CPU arm (`pid_listed: null`). The 150 ms sampler caught it mid-run.
3. **Memory and utilisation move with the engine.** Total VRAM 4823 → 5700 MiB across the
   session load (**+877 MiB**) → **6312 MiB** at the end of the decode (**+1489 MiB** for
   the process); machine-wide GPU utilisation during decode reached **98 %** (mean 30.1 %
   over 14 samples). The CPU arm's readings are flat at 2845 MiB through its own load, and
   the 21 % it shows is other apps — `pid_listed` is what separates the two.

**Caveat, stated rather than hidden**: `used_gpu_memory` answers `[N/A]` per process on
this WDDM box for EVERY process (verified with `nvidia-smi --query-compute-apps=pid,
process_name,used_memory` against 10 unrelated apps), so a per-pid MiB column cannot be
produced here. What can be, and is, is: the pid is listed by nvidia-smi (yes/no), the
machine-wide total delta within one run, and utilisation sampled *while* chunks decode.

**The ORT warning is not a fallback.** Both arms ran on onnxruntime 1.30.0 with
`TensorrtExecutionProvider, CUDAExecutionProvider, CPUExecutionProvider` available, and the
CUDA arm prints, three times:

```
[W:onnxruntime:Default, onnxruntime_pybind_state.cc:855] No registered plugin EP device found for
'CUDAExecutionProvider' with device_id=0
```

That is ORT 1.30 probing the **plugin**-EP registry before using the built-in CUDA EP. It is
followed by `CUDAExecutionProvider` in `get_providers()`, a listed pid, +1489 MiB and a 5.4x
speedup — the built-in provider loaded. It is a misleading log line, not a silent fallback,
and `worker-providers-oracle` would have caught the real thing.

---

## 5. What CUDA costs, and why that does not change the verdict

* **VRAM**: +1489 MiB resident for the process (5700 MiB at session load, 6312 MiB peak) on a
  16 GB card. The code's own note (`worker/sotto_worker.py:1480-1487`) measured
  1175–1703 MiB for this model before; today's number is inside that band.
* **RSS**: +63 MiB (1536.0 → 1599.5).
* **Process CPU**: 650.5 % vs 616.6 % of one core — CUDA does not make the CPU-side work
  disappear (the joint's per-call launches and the genai front end still run there), and it
  is **not** a CPU saving. What it buys is latency: 186.6 ms less per 560 ms chunk.
* **Thread budget**: not the explanation. 16 intra threads made the CPU arm worse
  (334.76 ms, RTF 0.6269, 487.2 % of a core) than the shipped 4 (228.18 ms, RTF 0.4160,
  616.6 %) under the same cage — see the control in §3.
* **Load**: the delta ranges from −3.5 s (runs A, B: CUDA loaded FASTER, cold cublasLt/cuDNN
  page-in) to **+0.63 s** (run C). Even at the worst observed delta the break-even is
  0.63 s ÷ 186.6 ms = **3.4 chunks = 1.9 s of audio**, after which every chunk is 5.5x
  cheaper. The front end (`og.Model`) is unchanged (1.53 vs 1.57 s).

---

## 6. Verdict and the product edit

CUDA wins: 41.57 ms p50 against 228.18 ms, RTF 0.0772 against 0.4160, identical hash,
identical text, both under the same cage and the same 4-thread plan — and it stays inside
one GPU's budget. The CPU branch's best-of-three is still 5.5x slower and, on this box
under normal desktop load, does not hold real time.

**No product edit is made, because the shipped path already chooses CUDA** — item 1, 2, 3
and 4 of §1, and item 5 (`WORKER_PROVIDERS selected=CUDAExecutionProvider,…` at 18:59:37 in
the owner's running app). Changing `worker/config.json:18` or
`worker/sotto_worker.py:4489-4491` would be a no-op restated as a commit; the honest
deliverable is the measurement, the receipt, and the guard that keeps the answer true.

**Gate impact**: `_main/worker-providers-oracle.py` pins this exact question, and it stays
green and still catches the defect — `judge()` reds any "CUDA available, not selected":

```
PYTHONPATH=I:/!watcher python -m watcher run --cpu 40 -- python _main/worker-providers-oracle.py --neg-arm
PASS cuda-selected-passes
PASS silent-cpu-fallback-reds
PASS cpu-only-box-passes
{"cases": 3, "caught": 3}
NEG-ARM: PASS        (exit 1 by the `red-as-expected-*` convention: the control caught the defect)
```

What the gate's headline numbers needed was the range, not a new rule: its docstring said
"CPUExecutionProvider … 2,27x, 247 ms/chunk" as a single figure, while the same file and
code measure 228–865 ms/chunk (2.4x down to 0.63x real time) depending on desktop load.
That range is now stated there, citing this receipt.

On the real log it judges the live product GREEN, which is the answer to "is the shipped
path on the GPU":

```
PYTHONPATH=I:/!watcher python -m watcher run --cpu 40 -- python _main/worker-providers-oracle.py
{"verdict": "PASS", "why": "the live engine is on the GPU", "selected": ["CUDAExecutionProvider", "CPUExecutionProvider"], ...}
WORKER-PROVIDERS VERDICT: PASS
```

---

## 7. Reproducibility fingerprints

```
f412fd1bce02aa6a6d174d9a3d886f7ce7ef24660e856834b1b6a514a2aa7254  worker/sotto_worker.py   (mtime 19:00:09)
048e28fbfcca1b7cf68eaa3ca09d7fbd62c4288e5b3b27fdfbe19bf3893aa899  worker/config.json       (mtime 19:02:36)
c98043cef21721a9c998d59d16186e8df65d0784864bcaeecdcb33390cdfd8e5  _main/live-engine-provider-ab.py
```

`worker/sotto_worker.py` and `worker/config.json` were DIRTY in the working tree during the
measurement (peer lanes; `worker/config.json` gained `audio.target_name`, which this probe
does not read — `model.providers`, `model.dir`, `use_vad` and `lang_id` are untouched).
Python 3.11.8, onnxruntime 1.30.0, onnxruntime-genai 0.17.1, RTX 5080 16 GB.

Per-arm JSON (every pass, every chunk latency, the raw GPU samples):
`_main/_cache/provider-ab-cpu.json` (run C), `_main/_cache/provider-ab-cuda.json` (run C),
`_main/_cache/provider-ab-cpu-16t.json` (the 16-thread control).

No window was opened (everything under the caged launcher; `nvidia-smi` children run with
`CREATE_NO_WINDOW`). No audio device was opened, written or enumerated: the fixture is a
file, read by `soundfile`.

---

## CACHE/PRICE
- task/agent: GpuLiveEngine
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['GpuLiveEngine']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['GpuLiveEngine']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-09T22:06:32.422178+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['GpuLiveEngine']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['GpuLiveEngine']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

> Transcript resolution note: this session's own .jsonl could not be located (`G:/env-data/superharness/sessions/*.journal.jsonl` contains no row from this session, and the script matched 0 usage rows for identity `GpuLiveEngine`). Every field above is therefore the script's fail-closed `UNKNOWN` with its named reason — no field was zeroed in its place.

---

## SELF-AUDIT

- **protocolos em falta** — I did not run the repo's own battery
  (`_main/_audit-verify-all.cmd`) after touching `_main/worker-providers-oracle.py` and
  `worker/README.md`; I ran only the oracle's `--neg-arm`. The rule here is "a permanent
  change updates the docs AND the port that judges it", and I verified the port by hand
  instead of through the battery. What I would do differently: run the battery step for
  `worker-providers` (and the `code-health` ratchet) as the closing step, not the probe.
- **verificacao adicional** — a paired run with the CUDA arm's `run_chunk` instrumented per
  GRAPH (encoder/decoder/joint separately) would prove that no node of the CUDA arm was
  silently executed by ORT's CPU fallback *inside* a CUDA session. `stage enc ms/chunk`
  174.5 → 35.2 already says the encoder moved, and the pid/utilisation say this process was
  on the GPU, but a per-node `Node::GetExecutionProviderType()` census would close it
  exactly rather than by inference. Cost: ~10 min of coding, one 10 s run.
- **checkboxes novas** — one mechanical assertion, not more care:
  `python -c "import json;d=json.load(open('_main/_cache/provider-ab-cuda.json'));assert d['gpu_end']['pid_listed'] and d['p50_ms']<150, d"` — a CUDA arm that reports the EP but did not get listed by nvidia-smi, or that regressed past 150 ms/chunk, must fail the receipt.
- **review por outro subagente** — `sim-com-escopo`: re-run the two arms on an IDLE desktop
  (nothing else using the GPU/CPU) and check the CPU p50 lands inside 228–865 ms. My verdict
  claims a range; a second box-state is the only thing that could move it.
- **gate-doubt**
  - `verde-de-verdade:` two greens to doubt. (1) The oracle's `--neg-arm` PASS is
    **by construction**: it feeds three synthetic `judge()` arguments and never reads a log
    or a session, so it proves the decision FUNCTION, not that a run selected CUDA — the
    proof that a real run selected CUDA is the log line at 18:59:37 and my arms'
    `get_providers()`, read separately. (2) My own arm's `exit 0`/`exit 4` is NOT vacuous:
    `run_arm` returns 4 unless `gpu_active` matches the arm, so a silent CPU fallback on the
    `cuda` arm would have been red, and it was not.
  - `falta-no-gate:` `worker-providers-oracle` reds only "CUDA available and not selected".
    It stays GREEN if a CUDA-selected session executes most nodes on the CPU, and green if
    the live engine gets 10x slower with CUDA still selected — the scenario a future model
    swap (bigger graph, VRAM pressure, ORT per-node fallback) walks straight through.
  - `gate-melhor:` run the CUDA arm of the probe and assert BOTH `pid_listed` and
    `p50_ms < 150` — `python _main/live-engine-provider-ab.py --arm cuda --out X && python -c
    "import json;d=json.load(open(X));assert d['gpu_end']['pid_listed'] and d['p50_ms']<150"`.
    RED fixture that must leave it failing: the same command with `--arm cpu` (the pid is
    never listed and p50 is 228+, so it fails) — i.e. the check cannot pass vacuously.
- **confianca** — `alta` for the verdict (two providers, identical text, 5.4–24x, confirmed
  by three independent GPU instruments and a thread-budget control). `media` for the exact
  CPU numbers, which move with desktop load by 3.8x — the range is the fact, not any single
  figure.
- **nao verificado** — the shipped engine's behaviour on a CPU-only host (no CUDA EP:
  `choose_providers` falls to `CPUExecutionProvider`, not exercised here); the effect of
  `TensorrtExecutionProvider` (never requested, never measured); per-node EP residency
  inside the CUDA session (see `verificacao adicional`); and `_main/_audit-verify-all.cmd`
  as a whole (see `protocolos em falta`).
