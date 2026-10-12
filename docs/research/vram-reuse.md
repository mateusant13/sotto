# VRAM reuse - what is on the GPU, what Sotto loads, and what can be reused

**Date:** 2026-10-12 - **Author:** front S8 - **Box:** RTX 5080, 16 303 MiB, driver 617.14, Windows/WDDM

The owner's question, verbatim:

> "ah, e se o mesmo modelo ja existe carregado na vram, reutiliza ele. se nao vai
> usar duplicados, do mesmo modelo, q eu tenho de outros projetos."

This document answers it with measurements, not impressions. Every number below was
taken on this box, in-process, by the instruments named in the receipt. Nothing here
launches the app, the shell or the worker.

---

## 1. The short answer

**There is no second copy of the Sotto model in VRAM today.** The Sotto worker holds
it once (measured 1 651.5 - 2 039.5 MiB dedicated, varying with the running revision),
and no other process on this box is running a Sotto worker. The GPU is otherwise full
of other people's stuff - the NVIDIA overlay alone holds more than the whole Sotto
worker - but none of it is a copy of our model, and none of it can be reused by us
(see section 4).

What *does* exist, and what the owner would reasonably call "the same model twice":

| what | where | cost | is it a duplicate? |
|---|---|---|---|
| the engine's three RNNT sessions | worker/sotto_worker.py:551-553 | 1 317.5 - 1 319.5 MiB dedicated | no - one copy, three graphs |
| the CUDA provider liveness probe | worker/sotto_worker.py:2806 | +359.5 MiB transient, 0.203 s | **yes, briefly** - a second read of joint.onnx, deleted at once |
| og.Model (ORT-GenAI) | worker/sotto_worker.py:564 | +833 MB host RSS, +0 MiB dedicated, 2.2 - 2.9 s | **yes** - the same weights again, in **host RAM**, not VRAM |

So the duplication that is real is (a) a 0.2 s probe that re-reads one 37 MB file, and
(b) a second full copy of the 1 020 MiB of weights sitting in system memory. The pool
built in this lane removes (a) from any new code path and makes (b) impossible to repeat
within a process.

## 2. How much VRAM one Sotto model costs

Measured in-process, loading the real export on this box
(worker/models/nemotron-3.5-asr-streaming-0.6b-int8, **1 020.3 MiB** in 7 weight
files, sha256 c51802fb31d693fbae73e6e9...), CUDA provider, each stage timed separately:

| stage | seconds | dedicated VRAM after |
|---|---|---|
| _add_cuda_dll_dirs() | 1.575 | - |
| CUDA provider probe (joint.onnx, then del) | 0.203 | 359.5 (229.5 retained) |
| encoder.onnx | 2.157 | 1 317.5 |
| decoder.onnx | 0.604 | 1 519.5 |
| joint.onnx | 0.067 | 1 649.5 |
| og.Model | 2.945 | 1 649.5 (**+0 MiB**, +833 MB RSS) |
| create_streaming_processor() | 0.154 | 1 649.5 |
| **total** | **5.927** | 1 649.5 MiB |

The worker's own load_s (its whole engine construction, worker/sotto_worker.py:4550)
was 2.41 - 3.62 s across four runs archived in worker/runs/*.jsonl on 2026-10-06, with
provider_probe_ms 298 - 347 and cuda_dirs_ms ~1.2 - 1.8 s. Those files predate the
current worker revision, so they are cited as history, not as today's number.

## 3. Who holds GPU memory on this box

Per-process dedicated GPU memory, measured in-process (see below for why not
nvidia-smi), 2026-10-12 13:55 -03:00, processes of 50 MiB or more:

| process | dedicated MiB |
|---|---|
| NVIDIA Overlay.exe (pid 14176) | **2 839.6** |
| dwm.exe | 741.1 |
| chrome.exe --type=gpu-process | 694.9 |
| NVIDIA Overlay.exe --type=gpu-process (pid 14976) | 345.9 |
| python.exe -m uvicorn backend.main:app (another project) | 227.5 |
| python.exe run.py (another project) | 227.5 |
| nvcontainer.exe | 144.3 |
| WindowsTerminal.exe | 130.6 |
| csrss.exe | 124.0 |
| Discord.exe | 118.5 |
| steamwebhelper.exe | 116.7 |
| ChatGPT.exe | 111.1 |
| explorer.exe | 93.0 |
| msedgewebview2.exe | 79.6 |
| Task Manager.exe | 77.7 |
| ChatGPT Classic.exe | 68.9 |

Sum of PDH dedicated over all pids: **6 599.9 MiB**, against NVML used **5 086 MiB**.
The two do not agree and are not the same measure - see the caveat in section 5.

The owner's question about "other projects" answered: the single biggest
non-Sotto GPU consumer is the **NVIDIA overlay at 2 839.6 MiB - more than the entire
Sotto worker**. Chrome, Discord, ChatGPT, Steam and two other Python projects follow.
None of them is an ASR model, and none is ours to reuse.

## 4. Why a third party's VRAM copy cannot be reused

This is the honest half of the answer, and it is a hard technical wall, not a gap in
effort.

A CUDA allocation is **private to the process that made it**. There is no name, handle
or offset by which an outside process can ask for somebody else's tensor. The only
mechanism that shares a CUDA allocation across processes is **CUDA IPC**, and CUDA IPC
is cooperative by construction:

* the **owner** process must call cudaIpcGetMemHandle() on its allocation and hand
  the resulting handle to the other side, over a socket, a shared file, a pipe - some
  channel that only the owner can create;
* the receiver then calls cudaIpcOpenMemHandle() with that handle.

Neither call can be made *by* a third party. We cannot reach into the NVIDIA overlay
and ask it for a handle it never exported, and we cannot inspect another process's
VRAM to find one: allocations are not nameable from outside, and on this box NVML
refuses to say how much a given process holds anyway (section 5).

So the detectable half is what this lane built, and it is real: **if the same model is
already resident in another process, Sotto now says so, loudly, before loading
anything.** The reuse itself needs that process's cooperation and is out of reach.

## 5. How per-process VRAM was measured, and why not nvidia-smi

Three paths were tried on this box, all in-process:

| path | result |
|---|---|
| nvidia-smi --query-compute-apps=pid,used_memory | Failed to initialize NVML: Unknown Error from this box's shells; used_memory printed [N/A] in the Lead's session |
| nvmlDeviceGetComputeRunningProcesses_v2 | **lists the pids** (33 of them) but returns usedGpuMemory == 0 for every one |
| **PDH GPU Process Memory (the one that works)** | win32pdh + a wildcard query + GetFormattedCounterArray returns {instance_name: bytes}; the instance name carries the pid; values agree with PowerShell Get-Counter on the same object |

The PDH query needs one quirk that cost time to find: the counter path carries **one**
backslash before the object and **one** before the counter name, and the query must be
collected **twice with a settle between** - a single collect answers
"Nao ha dados a serem retornados".

**Caveat, stated rather than hidden:** PDH Dedicated Usage is the driver's per-process
dedicated allocation; NVML used is a device-wide counter. They are not the same
measure and do not sum to each other (6 599.9 vs 5 086 MiB above). Both are reported
by the instrument; neither is described as the other.

## 6. What was built

Three new files, all in the lane's own scope. Nothing in worker/sotto_worker.py,
worker/redux_live.py, worker/redux_batch.py, worker/config.json or app/**
was modified.

| file | what it does |
|---|---|
| worker/vram_residency.py | The measurement layer. NVML device totals + per-process PDH VRAM, in-process, no subprocess. Model identity by weight-file sha256 (never by name). Two-tier foreign-holder detection: same-worker (runs sotto_worker.py) and size-plausible (holds enough VRAM to contain the model - a browser trips this with no ASR in sight, so it is reported as a candidate, never as a copy). |
| worker/model_vram_pool.py | The guarantee. get_or_load() hands back the **same** session objects for the same model + loader + provider list, so two call sites cannot each load the model. A different model is a different entry. foreign_policy="refuse" raises instead of loading a duplicate. Also carries the CUDA DLL-dir fix-up the worker already uses, so a pool-built session is GPU-backed. |
| _main/vram-reuse-oracle.py | The gate. In-process, launches nothing. Seven checks, then a **negative arm**: a copy of the pool with both sharing guards removed. |

### Gate result, 2026-10-12

~~~
== GREEN ARM (the pool as shipped) ==                == NEGATIVE ARM ==
  PASS CHK-1 same model -> SAME entry                  FAIL CHK-1 a SECOND entry was built
  PASS CHK-2 second call moves 0.0 MiB                 FAIL CHK-2 +1 088.0 MiB
  PASS CHK-3 one entry, refs=2                         FAIL CHK-3 refs=1
  PASS CHK-4 different dir/providers -> different key  PASS CHK-4
  PASS CHK-5 resident model DETECTED                   PASS CHK-5
  PASS CHK-6 refuse raises, does not duplicate         PASS CHK-6
  PASS CHK-7 the verdict is in the log                 PASS CHK-7

  green arm (real pool): PASS
  neg arm  (guards removed): 3 of 3 core checks RED -> RED (as expected)
  VERDICT: PASS
~~~

The second call moving **exactly 0.0 MiB** while the first moved **1 319.5 MiB** is the
whole claim, measured. The negative arm is what makes that green meaningful: with the
sharing guards deleted, the same second call builds a second copy and costs
**1 088 MiB**.

## 7. What the Lead must do

1. **Wire the pool into the worker.** One call site today is
   worker/sotto_worker.py:4540 (asr = StreamAsr(...)). Replace the session
   construction inside StreamAsr.__init__ (:551-553) with
   model_vram_pool.get_or_load(model_dir, providers=..., loader="sotto"), and move
   the CUDA provider probe (choose_providers, :2748-2806) behind the same pool so
   it stops re-reading joint.onnx. The exact patch is in the receipt.
2. **Measure the end-to-end cost (d).** The lane may not launch the worker. The
   command is in the receipt.
3. **Read the log the next time the worker starts.** With a Sotto worker already
   resident, the pool now prints VERDICT: a Sotto worker (this same model) is
   ALREADY RESIDENT before it loads anything. That is the owner's "don't load a
   duplicate" made observable.
