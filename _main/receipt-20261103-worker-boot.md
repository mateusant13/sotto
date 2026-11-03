# Worker boot: where the 65-206 s goes, and 2.4x taken out of it

Date: 2026-11-03. Lane: worker boot (`worker/**` only). Repo `H:/sotto`, MAIN TREE
(weights live only there and are git-ignored).

**VERDICT UP FRONT, because the ticket asked for 4x and this did not reach 4x:**

| metric | before | after | ratio |
|---|---|---|---|
| worker-boot → `model-loaded` (idle box, A/B/A) | 12.87 / 12.85 s | **5.27 s** | **2.44x** |
| worker-boot → `model-loaded` (disk contended, A/B/A/B) | 14.35 / 21.40 s | **7.79 / 9.29 s** | **~2.1x** |
| boot file-read volume (cache-independent) | 340.3 MB / 2878 reads | **125.9 MB / 753 reads** | **2.70x bytes, 3.82x reads** |
| steepest single run seen (busy box, instrumented baseline) | 24.59 s | 5.27 s | 4.7x |

The 4x is real only on a busy box; on an idle box the honest number is **2.4x**. The
remaining second and a half to five seconds is one session, and §8 says exactly what
it is. Nothing below is extrapolated: every number is a `RESULT` line from a run in
this file's commands.

---

## 1. How it is reproduced (no audio device, nothing rendered)

```bash
cd H:/sotto
python worker/_probe/boot-io.py                       # the instrument: seconds + READ BYTES + the phase line
python worker/_probe/boot-io.py --script <path>       # same, against any copy of the worker
python worker/_probe/boot-control.py                  # negative control: HEAD arm / worktree arm / HEAD arm
python worker/_probe/boot-phases.py all               # the same phases, in one process, no priority throttle
python worker/_probe/_churn.py 600 &                  # optional: put the disk in the owner's condition
```

`boot-io.py` spawns `python worker/sotto_worker.py --selftest --stats-interval 0`
— file source, **no audio device**, the self-test `worker/README.md` already ships —
and reads, at `model-loaded`: wall clock, the child's own `GetProcessIoCounters`
(`read_bytes` / `read_count` via psutil), `load_phases_s`, and the new
`WORKER_BOOT_PROF` line from stderr.

The worker's own phase line (new, ONE line on stderr, and also the additive
`boot_prof_s` key on `model-loaded`):

```
WORKER_BOOT_PROF cuda_dirs=0.047 probe=0.248 numpy_import=0.253 ort_import=0.253
                 og_import=0.267 sess_encoder=4.927 sess_decoder=5.096 sess_joint=5.427
                 og_model=10.079 og_processor=10.299
```

Values are seconds since `sotto_worker` was imported. `load_phases_s` is unchanged,
key for key, for every existing reader.

## 2. The baseline breakdown (instrumented HEAD, 2026-11-03)

One run, `--selftest --providers auto`, phases from `WORKER_BOOT_PROF`:

| phase | s | share |
|---|---|---|
| `_add_cuda_dll_dirs()` (imports **torch**) | 7.88 | 32 % |
| CUDA liveness probe (a session that is thrown away) | 3.54 | 15 % |
| numpy + onnxruntime + onnxruntime_genai imports | 0.13 | 1 % |
| **encoder session** | 4.59 | 19 % |
| decoder session | 0.15 | 1 % |
| joint session | 0.22 | 1 % |
| **`og.Model`** (genai front end) | 7.71 | 31 % |
| `og.StreamingProcessor` | 0.13 | 1 % |
| **total, process start → `model-loaded`** | **24.35** (wall 24.59) | |

Two of the four heavy phases are **pure waste**, and they were the two nobody had
timed: `import torch` exists only to learn the path of `torch/lib`;
the CUDA probe exists only to create and destroy a session.

## 3. What changed (4 changes, each with the number that justified it)

### 3.1 `_add_cuda_dll_dirs()` no longer imports torch — 7.88 s → 0.05 s

torch was imported **only** to compute `dirname(torch.__file__) + '/lib'`.
`torch/lib` on this box is **5.8 GB in 38 DLLs**; the import maps a good part of it
for a directory path. `importlib.util.find_spec("torch")` answers the same question
without executing the module, and the directory is then added to the DLL search path
exactly as before (`os.add_dll_directory` + PATH prepend).

Proof that CUDA still loads without torch in the process (`boot-phases.py
cuda_nvidia_only`, nvidia wheels only, no torch/lib at all):

```
PHASE cuda_dirs_s=0.006
PHASE probe_joint_cuda_s=0.738
providers ['CUDAExecutionProvider', 'CPUExecutionProvider'] dirs 8
```

### 3.2 the CUDA liveness probe is the REAL encoder session — 3.54 s → 0.20 s

`choose_providers()` used to open `joint.onnx` with `CUDAExecutionProvider`, read
`get_providers()`, and drop it — paying the CUDA EP's DLL load in a session that was
then discarded, and leaving the encoder to do it again. It now returns the REQUEST;
`StreamAsr` creates the encoder with the full list, ORT falls back to CPU if the EP
cannot dlopen, and `get_providers()` on the session that will actually run is the
answer. A wrong request costs nothing extra — there is no second creation.

The `stage="providers"` event moved **after** the load and now reports
`providers_selected` = the ANSWER (plus the new `providers_requested`). That keeps
`WORKER_PROVIDERS` and `_main/worker-providers-oracle.py` meaning what they meant — a
GPU provider available and not used is still red — and makes it evidence from the
loaded session instead of from a probe. `cuda_probe_model` keeps its key and now names
the export whose encoder the decision was read from; `provider_probe_ms` keeps its key
and now times the provider-list selection (a registry query).

### 3.3 per-graph `SessionOptions`: the encoder is optimized at BASIC — 3.50 s → 2.18 s

`worker/_probe/boot-phases.py`, one process, same graph:

```
encoder ORT_ENABLE_ALL    3.50 s
encoder ORT_ENABLE_BASIC  2.18 s
encoder bytes + BASIC     2.14 s   (bytes alone 2.56 s -> inside the noise of BASIC alone)
encoder nopat             2.45 s
```

The encoder (24 int4 layers, 690 MB of weights) is what ORT's full optimization pass
walks. The decoder and the joiner are 0.15 s / 0.22 s **and are called per frame**:
they keep `ORT_ENABLE_ALL`, whose LSTM fusion is paid once at load and used thousands
of times. Trading 0.1 s of boot for per-frame latency would be the wrong direction.
`SOTTO_LOAD_AB` keeps its arms (`bytes`, `basic`, and a new `full` to force ALL).

### 3.4 `og.Model` moved off the `model-loaded` path — 7.71 s out of the boot

`og.Model` reads 2.7 MB (7 read ops) and was measured at **2.0-3.2 s alone, 7.7-9.3 s
inside this worker**. Nothing before the first chunk needs it: the panel's
`model-loaded` (what `BRIDGE_LOAD_MS` and the bridge watchdog measure) needs the three
sessions, and the shell still has to arm capture.

It is now built on a daemon thread started by `main()` **after** the `model-loaded`
emit, and every reader reaches it through the `sp` property, which joins. The position
matters and is measured: `og.Model` **holds the GIL** for its whole duration (a 50 ms
loop in the main thread stalls 1.53 s while a builder thread is inside `og.Model`
for 1.56 s), so a thread started before the emit would buy nothing.

Consequences that are stated rather than hidden:
* `peak_rss_mb` on `model-loaded` no longer includes genai's own copy of the weights
  (measured drop: 785 → 62 MB). The key means "peak the boot reached" and the code
  comment now says so.
* if the front end fails, it is now AFTER `model-loaded`, so the builder emits
  `state="error", stage="frontend"` itself — no silent stream.
* `--selftest`, probes and any direct `StreamAsr(...)` user never start the thread:
  `_join_frontend()` builds it inline, exactly like the pre-change code.

## 4. After

Same instrument, same command, one run:

| phase | before | after |
|---|---|---|
| `cuda_dirs` | 7.88 | **0.05** |
| provider decision | 3.54 | **0.20** |
| imports (np/ort/og) | 0.13 | 0.07 |
| encoder session | 4.59 | 4.68 |
| decoder | 0.15 | 0.17 |
| joint | 0.22 | 0.33 |
| **`model-loaded`** | **24.35** | **5.43** |
| `og.Model` (now after the event) | 7.71 | 4.65 |
| `og.StreamingProcessor` (after the event) | 0.13 | 0.22 |

`model-loaded` payload: `load_s=5.21`, `load_phases_s={"encoder":4.657,"decoder":0.168,
"joint":0.331,"sessions_total":5.156}`, `providers=["CUDAExecutionProvider",
"CPUExecutionProvider"]`. The LAST run of the same command before this receipt was
written came back at `load_s=4.61` (`WORKER_BOOT_PROF cuda_dirs=0.022 probe=0.188
sess_encoder=4.306 sess_decoder=4.503 sess_joint=4.794 og_model=8.011`), i.e. the
5.3 s here is the conservative end of 4.6-5.3 s, not the best case.

**The decode contract is untouched**: `blank_id 13087`, `max_symbols_per_step 10`,
`chunk_samples 8960` are read from `genai_config.json` and were not edited. Evidence
that the transcript did not move: `--selftest` before and after produce the **same 119
tokens and the same caption text** (md5 of every `"text"` value: `024eb03e…` both).

## 5. Negative control — the number returns

`python worker/_probe/boot-control.py` materialises `git show HEAD:worker/sotto_worker.py`
next to the real file (the worker imports `engine_switch`/`live_queue` BY NAME from its
own directory), measures HEAD, the worktree, and HEAD again with the same instrument:

```
== HEAD (before)         wall_to_model_loaded_s=12.87  read_mb=340.3 read_ops=2878
== WORKTREE (after)      wall_to_model_loaded_s=5.27   read_mb=125.9 read_ops=753
== HEAD (before, again)  wall_to_model_loaded_s=12.85  read_mb=340.3 read_ops=2878
```

Same check with the disk in the owner's condition (`_churn.py` reading
`encoder.onnx.data` in a loop for the whole comparison):

```
== head   wall_to_model_loaded_s=14.35  first_caption_s=20.76  read_mb=340.3
== after  wall_to_model_loaded_s=7.79   first_caption_s=19.63  read_mb=125.9
== head   wall_to_model_loaded_s=21.40  first_caption_s=24.28  read_mb=340.3
== after  wall_to_model_loaded_s=9.29   first_caption_s=26.16  read_mb=125.9
```

And the cache-independent statement, which is the one that survives a busy disk:

| | HEAD | after |
|---|---|---|
| bytes read during boot | 340.3 MB | **125.9 MB** (2.70x less) |
| read operations during boot | 2878 | **753** (3.82x fewer) |

## 6. Why 4x is not claimed

On an idle box the boot is now 5.3 s of which 4.7 s is ONE thing: the encoder
session. Two of the four heavy phases were waste and are gone; the other two are the
CUDA EP's DLL map and the weights. Getting to 4x would mean deleting real work, and
the only way to do that in this tree is to move `model-loaded` before the model — which
is exactly the kind of number that looks good and is a lie.

## 7. The single biggest remaining cost

**The encoder session: 4.5-4.7 s, 86-90 % of what is left.** It is:

1. the CUDA EP's DLL map — `onnxruntime_providers_cuda.dll` 184 MB + cublasLt/cublas
   735 MB + cuDNN 597 MB ≈ **1.5 GB**, on `C:`;
2. the 690 MB int4 encoder (`encoder.onnx.data`, on `H:`) and its prepack/optimization;
3. all of it at the process's deliberate `BELOW_NORMAL` priority
   (`_lower_process_priority`, the owner's "abrir ou fechar trava pra caralho" fix).
   The same session costs **1.7-1.9 s** in a plain probe at NORMAL priority: that
   difference is the price of the desktop staying usable, and it is not mine to
   remove.

## 8. Options evaluated and REJECTED, with the number

| option | measurement | verdict |
|---|---|---|
| `session.use_ort_model_bytes_directly=1` | encoder 2.56 s alone, 2.14 s with BASIC vs 2.18 s BASIC alone | inside noise; left behind `SOTTO_LOAD_AB=bytes` |
| `optimized_model_filepath` cache | write 4.36 s, load-from-cache 4.39 s, plain 4.59 s; the written graph is 0.9 MB because the weights are external data | no gain, real invalidation risk — not landed |
| intra-op threads 1 / 2 / 4 / 8 | 2.08 / 1.59 / 1.94 / 1.74 s | no winner outside noise; shipped default (`OMP_NUM_THREADS=4`) kept |
| run the load WITHOUT the background-priority window | `boot-io --script worker/_probe/no-background.py` → **10.23 s** vs 6.87 s with it | the throttle is not the latency (the box is); change NOT made |
| decoder/joint before the encoder | the encoder is 97 % of the session time; the order only decides which session pays the EP load | no gain |
| start decoding (decoder+joint) while the encoder finishes | there is no audio before capture starts and no frame without the encoder | not reachable |
| CPU EP for the encoder | loads in 0.28 s (shell lane's measurement) but the engine drops from 10.75x to 2.27x realtime (`_main/worker-providers-oracle.py` header) | trading 4 s of boot for 4.7x slower inference — refused |

## 9. Oracles

```
python -m py_compile worker/sotto_worker.py worker/_probe/{boot-phases,boot-io,boot-control,no-background,_churn}.py   -> OK
python _main/undefined-names-oracle.py         -> UNDEFINED-NAMES GREEN -- 18 production files, 0 names used and never defined
python _main/live-code-freshness-oracle.py --strict -> LIVE_CODE FRESH (rc=0, sha256=C9577260A133 files=39, "hash do processo == hash do disco")
```

**Caveat on the freshness verdict, and it matters:** that oracle tracks
`app/webview/*.py` + `app/panel/*` (`app/webview/code_identity.py:23-38`). `worker/**`
is **not** in its file set, so GREEN says the shell is fresh — it says nothing about
this change being live in the running process. The proof that this change is live is
the `WORKER_BOOT_PROF` line and `boot_prof_s` in §1/§4, which did not exist at HEAD.

## 10. Files touched

* `worker/sotto_worker.py` — the four changes above, `_BOOT_PROF`/`_prof`/`_prof_publish`,
  `session_options()`, the `sp` property and the front-end lifecycle.
* `worker/_probe/boot-phases.py` — per-phase arms (importtorch / notorch / cuda_* /
  probe / encoder* / og / all).
* `worker/_probe/boot-io.py` — the instrument (seconds AND bytes, `--script`).
* `worker/_probe/boot-control.py` — the negative control (HEAD vs worktree vs HEAD).
* `worker/_probe/no-background.py` — the rejected-throttle arm.
* `worker/_probe/_churn.py` — the disk-contention generator used by §5.

**`worker/_probe/` is git-ignored on purpose** (`.gitignore:104`, the directory holds
run logs and per-day scratch). These six files are therefore LOCAL instruments: the
commands above reproduce on this tree, and a clone needs them force-added
(`git add -f worker/_probe/boot-io.py …`) or copied from this receipt's description.
They add no runtime dependency — `sotto_worker.py` never imports them.

Nothing outside `worker/**` was edited (`app/webview/sotto_webview.py` and
`_main/panel-state…json` show as modified in `git status` and are ANOTHER lane's
work, untouched by this one).
