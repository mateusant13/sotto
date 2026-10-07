# Receipt — Parakeet Redux **ternary** on this box (`moondream/parakeet-redux`, CC-BY-4.0)

Lane: batch runner for the Parakeet Redux ternary checkpoint. Date: 2026-10-07.
Artifacts owned by this lane: `worker/redux_batch.py`, this receipt. No other file was edited.

---

## 0. Verdict

**PARITY — both oracle texts reproduced byte-for-byte, by the vendor runtime (path A).**

| | text |
|---|---|
| `_main/redux-ptbr.txt` (oracle, ONNX int4, 6x real time) | `O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira. Os moradores precisam de um caminho alternativo para chegar ao trabalho.` |
| `worker/redux_batch.py` (**ternary**, via Photon) | `O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira. Os moradores precisam de um caminho alternativo para chegar ao trabalho.` |
| `_main/redux-en.txt` (oracle, ONNX int4, 4x real time) | `The radio announced that the bridge over the river will be closed next Monday. Residents need an alternative route to get to work.` |
| `worker/redux_batch.py` (**ternary**, via Photon) | `The radio announced that the bridge over the river will be closed next Monday. Residents need an alternative route to get to work.` |

Diff: **empty on both**. Segment boundaries also agree exactly with the oracle's own
`transcribe.py --timestamps segment` output: pt-BR `0.00–7.92` / `8.24–14.72`, en-US `0.00–4.80` / `4.80–8.16`.

One caveat, stated up front: parity holds **through the dense weight form**, not through Photon's packed
int8 GEMM. Section 2 gives the measurement that forced that, and section 6 says exactly what that leaves
unverified.

---

## 1. Which path, and why — path (A), the vendor runtime

Owner's instruction was to run the 179 MB ternary artifact and use Photon. Done:
`pip install moondream` (2.6.1) → brings **kestrel** 0.9.1 (Photon's engine) →
`kestrel.models.parakeet_tdt.weights.load_parakeet_tdt()` reads `ternary.json` + `model.safetensors`
and unpacks the packed ternary weights itself. **No custom unpacker was written**; `worker/ternary_unpack.py`
does not exist. No hand-rolled TDT loop either — the vendor's own decode loop runs.

### 1.1 The install plan, read before installing (`pip install --dry-run`)

`python -m pip install --dry-run moondream` → 13 packages, **606.4 MB** of downloads:

| package | version | download |
|---|---|---|
| moondream | 2.6.1 | 0.1 MB |
| kestrel | 0.9.1 | 0.6 MB |
| kestrel-kernels | 0.7.4 | 4.4 MB |
| kestrel-kernels-bundle-a…e | 0.7.4 | 5 × 93.1 MB = **465.5 MB** |
| kestrel-native | 0.1.8 | 3.1 MB |
| torch-c-dlpack-ext | 0.1.5 | 1.5 MB |
| **torch** | **2.14.1** | **124.1 MB** |
| setuptools / sympy | 84.0.0 / 1.14.0 | 0.8 / 6.3 MB |

The torch entry was checked for the trap the brief warned about: **it is not a multi-GB CUDA build.**
The 2.14.1 `win_amd64` wheel is 124.1 MB and the resolver pulls **no `nvidia-*` packages at all** — it is
the CPU-only Windows wheel. So the plan was not blocked.

### 1.2 What was actually installed (torch deliberately *not* touched)

`torch 2.7.0+cu128` was **already present** on this box, and installing `moondream` normally would have
**replaced** it with the CPU-only 2.14.1. Two reasons to keep it:

* `worker/sotto_worker.py:289` imports torch to locate CUDA DLLs (`_add_cuda_dll_dirs`), and another lane
  owns that file;
* `torch_c_dlpack_ext` 0.1.5 selects its addon by torch version — it ships `torch24…torch29`, i.e. **nothing
  for torch 2.14** — while `torch27-cpu.dll` matches what is here exactly.

Exact command run (system Python 3.11, `C:\Program Files\Python311`):

```
python -m pip install --no-deps --no-input ^
  moondream==2.6.1 kestrel==0.9.1 kestrel-kernels==0.7.4 ^
  kestrel-kernels-bundle-a==0.7.4 kestrel-kernels-bundle-b==0.7.4 kestrel-kernels-bundle-c==0.7.4 ^
  kestrel-kernels-bundle-d==0.7.4 kestrel-kernels-bundle-e==0.7.4 ^
  kestrel-native==0.1.8 torch-c-dlpack-ext==0.1.5
```

```
Successfully installed kestrel-0.9.1 kestrel-kernels-0.7.4 kestrel-kernels-bundle-a-0.7.4
kestrel-kernels-bundle-b-0.7.4 kestrel-kernels-bundle-c-0.7.4 kestrel-kernels-bundle-d-0.7.4
kestrel-kernels-bundle-e-0.7.4 kestrel-native-0.1.8 moondream-2.6.1 torch-c-dlpack-ext-0.1.5
```

**Installed size on disk: 488.3 MB** (kestrel 5.2 + kestrel_kernels 24.6 + kestrel_native 10.2 +
moondream 0.2 + torch_c_dlpack_ext 4.4 + five bundles 443.7). Download was 480.3 MB (torch excluded).
`pip check`-relevant: the dependency `torch>=2.8` declared by kestrel is **not** satisfied on paper
(2.7.0 is installed); it is satisfied in practice — see 2.1. That is a deliberate, reported deviation.

---

## 2. The one real blocker, and how it was resolved

### 2.1 It was not torch (measured)

```
python -c "import torch; from kestrel_kernels.ternary import ternary_gemm_isa, resident_form; print(ternary_gemm_isa())"
1.22s
scalar
```

`torch 2.7.0+cu128` imports, `kestrel_kernels` imports, and `torch_c_dlpack_ext` installs
`torch.Tensor.__dlpack_c_exchange_api__` from `libtorch_c_dlpack_addon_torch27-cpu.dll` — so kestrel's
DLPack bootstrap succeeds on the older torch. Nothing in the vendor stack complained about the version.

### 2.2 What *is* broken: the protected CPU kernel payload exposes only `scalar`

```
_cpu.ternary_gemm_isa()      -> 'scalar'      conformer_isa() -> 'scalar'
gemm_isa_available('avx2')   -> False         ('avx512vnni', 'avxvnni', 'sse4', 'neon-*' all False)
```

This is a real CPU with AVX2 — `torch.backends.cpu._is_avx2_supported() == True`, and Windows'
`IsProcessorFeaturePresent(40)` returns 1 (checked directly through ctypes). But `kestrel_kernels`
ships its kernels inside a **protected payload**, `kestrel_cpu.kstlc` (51,598 bytes), whose own banner
says *"This payload is obfuscated. The key is not stored in this file."* Only the scalar reference comes
back out of it on this Windows wheel. Checked against the next release too: `kestrel-kernels==0.7.5`
ships a byte-count-identical `kestrel_cpu.kstlc` (51,598 B), so this is not a 0.7.4 bug fixed upstream.

Consequence: `resident_form("cpu")` raises `NotImplementedError` and **no ternary weight can be
materialized on the CPU as shipped**. That is the packaged fast path (Photon's 113x-real-time number) and
it is **unavailable on this box**.

### 2.3 The fallback used: Kestrel's own documented dense oracle

`kestrel_kernels/ternary.py`'s module docstring names three resident forms; the third — *"other:
`TernaryWeight.dequantized()` expands the codes into the activation dtype once. This is the oracle the two
above are tested against"* — is exactly the arithmetic the packed kernel is tested against. `redux_batch.py`
selects it when, and only when, the packed kernel is absent:

```python
import kestrel_kernels.ternary as ternary
if not ternary.ternary_gemm_ready():          # 'scalar' -> no int8 GEMM on this box
    original = ternary.resident_form
    ternary.resident_form = lambda d: "dense" if torch.device(d).type == "cpu" else original(d)
```

Verified in-process: `ternary layers by resident mode: {'dense': 193}` — every one of the manifest's 193
quantized encoder projections is materialized dense. The unpacking itself (`unpack_export`: base-3 digits
→ 4 codes/byte → `scales[row, col//128] * (code-1)`) is Photon's own code, untouched.

**Cost, measured (two independent instruments, in-process `GetProcessMemoryInfo` and an external
`Get-Process.WorkingSet64` poll): peak working set 3.90 GB** (2.42 GB of that is 604 M ternary weights ×
4 B fp32, plus the transient dequantization buffers). The packed path would have been ~180 MB of weights.
This is the one place where the delivered runner is *not* "LEVE", and it is a direct consequence of 2.2.

---

## 3. The deliverable — `worker/redux_batch.py`

CLI contract unchanged and honoured:

```
python worker/redux_batch.py --wav PATH [--json] [--model-dir DIR]
```

* one JSON line per segment on **stdout**: `{"type": "caption", "text": "...", "start": <s>, "end": <s>, "producer": "redux"}`
* everything else (weight form, load time, timings) on **stderr**, so stdout stays a clean JSONL stream
* stdout/stderr are pinned to UTF-8 (`reconfigure(encoding="utf-8", errors="replace", line_buffering=True)`),
  the same convention `sotto_worker.py:2732` uses — without it a `>` redirect re-encodes `á` to `0xE1`
  and the line stops being valid UTF-8 (measured: yes, it did, before the fix)
* `--json` appends one final `{"type":"result", ...}` line (whole text, duration, compute seconds, RTF).
  The caption lines are printed whether or not `--json` is given, so a consumer that only wants captions
  never has to pass anything.
* never opens an audio device, never spawns a process → no console window of its own
* `--model-dir` defaults to `<script>/models/parakeet-redux-ternary`

### 3.1 Commands and their output (verbatim)

```
> python worker\redux_batch.py --wav _main\pt-br-sample.wav --json
{"type": "caption", "text": "O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira.", "start": 0.0, "end": 7.92, "producer": "redux"}
{"type": "caption", "text": "Os moradores precisam de um caminho alternativo para chegar ao trabalho.", "start": 8.24, "end": 14.72, "producer": "redux"}
{"type": "result", "text": "O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira. Os moradores precisam de um caminho alternativo para chegar ao trabalho.", "segments": 2, "duration": 15.0, "compute_seconds": 1.127, "real_time_factor": 13.31, "producer": "redux", "wav": "H:\\sotto\\_main\\pt-br-sample.wav", "model_dir": "H:\\sotto\\worker\\models\\parakeet-redux-ternary"}
stderr: redux_batch: resident weight form = dense
        redux_batch: loaded in 3.93s from H:\sotto\worker\models\parakeet-redux-ternary
        redux_batch: pt-br-sample.wav: 15.0s of audio in 1.13s, 13x real time

> python worker\redux_batch.py --wav _main\en-us-sample.wav
{"type": "caption", "text": "The radio announced that the bridge over the river will be closed next Monday.", "start": 0.0, "end": 4.8, "producer": "redux"}
{"type": "caption", "text": "Residents need an alternative route to get to work.", "start": 4.8, "end": 8.16, "producer": "redux"}
stderr: redux_batch: resident weight form = dense
        redux_batch: loaded in 3.73s from H:\sotto\worker\models\parakeet-redux-ternary
        redux_batch: en-us-sample.wav: 8.5s of audio in 0.74s, 12x real time
```

Reproduction of the parity claim (run from `H:\sotto`):

```
python -c "import json,pathlib,subprocess,sys;R=pathlib.Path(r'H:\sotto');o=[l for l in (R/'_main/redux-ptbr.txt').read_bytes().decode('cp1252').splitlines() if l.strip() and not l.startswith('model loaded')][-1].strip();p=subprocess.run([sys.executable,str(R/'worker/redux_batch.py'),'--wav',str(R/'_main/pt-br-sample.wav'),'--json'],capture_output=True);m=[json.loads(l) for l in p.stdout.decode('utf-8').splitlines() if l.strip()];print('ORACLE:',o);print('MINE  :',[x for x in m if x['type']=='result'][0]['text']);print('EQUAL :',o==[x for x in m if x['type']=='result'][0]['text'])"
```

(`_main/redux-ptbr.txt` is cp1252 on disk — the earlier ONNX run wrote it through a redirected stdout —
hence `.decode('cp1252')`; `_main/redux-en.txt` is pure ASCII so either codec works.)

### 3.2 Measured cost

| | measured |
|---|---|
| load (in-process, from `ParakeetTdtRuntime()` to ready) | **3.7 – 4.3 s** typical; 3.7–6.7 s end-to-end while the owner's app is running |
| whole process (interpreter + torch import + load + infer) | **7.1 – 9.6 s** wall |
| pt-BR, 15.00 s of audio | 1.06 – 2.13 s → **7 – 14x real time** |
| en-US, 8.54 s of audio | 0.70 – 1.33 s → **6 – 12x real time** |
| peak working set | **3.90 GB** (see §2.3) |
| threads | 8 (the runtime's own CPU policy: `os.cpu_count()` capped at 8) |
| device | CPU only; `device="cpu"` is fixed in the runner |

The speed spread is the box, not the model: a 3-run sweep at one point measured 7.0x / 5.5x / **3.5x** on
the same 15 s file while `Win32_Processor.LoadPercentage` read 58 % with 8 other processes (chatterino,
MsMpEng/Defender, chrome, Task Manager) burning CPU. The best repeatable figure is ~14x. For reference the
ONNX int4 oracle on the same file was 6x. **Speed here is a busy-desktop range, not a controlled benchmark.**

### 3.3 The documented vendor entry point also works (not just my wrapper)

The README's own API — the thing `pip install moondream` advertises — works against the local directory
once `model_path` is supplied, and returns the same text and the same segments:

```python
import moondream as md, torch
speech = md.photon("moondream/parakeet-redux", device="cpu", dtype=torch.float32,
                   model_path=r"H:\sotto\worker\models\parakeet-redux-ternary")
result = speech.transcribe(audio=r"H:\sotto\_main\pt-br-sample.wav", timestamps="segment")
```
```
weight form: dense
md.photon() constructed in 9.56s
transcribe() in 2.83s
TEXT: O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira. Os moradores precisam de um caminho alternativo para chegar ao trabalho.
    {'text': 'O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira.', 'start': 0.0, 'end': 7.92}
    {'text': 'Os moradores precisam de um caminho alternativo para chegar ao trabalho.', 'start': 8.24, 'end': 14.72}
```

`md.photon()` alone (no `model_path`) **cannot** take a local directory — it routes the argument through
`kestrel.models.registry.get_spec()`, which knows model *ids* only:

```
ValueError: Unknown model 'H:\\sotto\\worker\\models\\parakeet-redux-ternary'.
Known models: … 'moondream/parakeet-redux', …
```

So the id-plus-`model_path` form above is the correct local invocation, and it works. `worker/redux_batch.py`
does **not** go through it: constructing the full Photon engine takes 9.6 s versus 3.8 s for the model
runtime directly (`kestrel.models.parakeet_tdt.runtime.ParakeetTdtRuntime`), and the CLI contract demands a
fast start. Same weights, same loader, same decode loop, same tokenizer, same segmenter — only the async
engine/scheduler layer in between is skipped.

---

## 4. House rules

**No window.** Launched as a real `pythonw.exe` child with `CREATE_NO_WINDOW`, census of the child's own
pid every **25 ms** for the whole 8.5 s run:

```
python _main\_redux-window-census.py
pid=8892 rc=0 wall=8.50s samples=213 visible_samples=0 longest=0.000s
exit=0
```

`visible_samples=0` of 213 at 25 ms. (The 60 s house census cannot prove absence — that is why this ran its
own cadence.)

**No audio device.** Two measurements:

* `tasklist /m <dll> /fi "PID eq <pid>"` during a live run: `WINMM.dll` is mapped (from `t=3 s`, i.e.
  during import/load, before any audio file is opened) but **`wdmaud.drv` — the legacy wave device driver —
  and `mmdevapi.dll` — the WASAPI device API — are both absent at t=3 s and t=8 s.** No device handle is
  created.
* `kestrel_native`'s SBOM: **no device backend at all** — `cpal`, `alsa`, `wasapi`, `coreaudio`, `rodio`,
  `miniaudio` are all absent; its audio surface is `open_audio_file_mono` / `open_audio_mono`, decoding
  files with **symphonia** (pure Rust, incl. `symphonia-codec-pcm` / `symphonia-format-riff` for WAV). The
  library has no API that could open a device.

**The owner's app was not touched.** No `sotto_worker.py` / `sotto_webview.py` was killed or started; the
only processes this lane launched were its own `python`/`pythonw` runs, each of which exited.

**Files.** Wrote: `worker/redux_batch.py`, this receipt. Read-only: everything else. Scratch deleted
(§7). `worker/models/parakeet-redux-reference/` was read, not modified. No ONNX was re-downloaded.

---

## 5. Environment facts this lane measured (may be useful elsewhere)

* **`torch.cuda.is_available()` is `True` on this box** — `NVIDIA GeForce RTX 5080`, `torch 2.7.0+cu128`.
  AGENTS.md's "CUDA is requested but not loadable" is true of **ONNX Runtime's** `CUDAExecutionProvider`,
  not of torch. The ternary runner still pins `device="cpu"` on purpose (the stack law wants the light CPU
  transcriber, and the GPU is the owner's).
* CPU is an **i5-13600K: AVX2 present, AVX-512 fused off** (`_is_avx512_supported() == False`). Even the
  vendor's documented ISA ladder would have selected **avx2**, not avx512vnni, on this part.
* `kestrel.model_download.ensure_model_weights()` returns `None` for `moondream/parakeet-redux` (its
  registry spec carries no single weight `filename`), so `RuntimeConfig.model` alone would have sent the
  loader to `huggingface_hub.snapshot_download` — i.e. to the network, into `HF_HOME=I:/codeintel/hf-cache`.
  Passing `model_path` avoids that entirely, and the runner never touches the network.

---

## 6. What is NOT verified / could not be done

1. **Photon's packed int8 CPU kernel (`gemm8`) never ran.** It is not in this wheel's payload (§2.2), so
   the shipped fast path — and the README's 113x-real-time number — is **unmeasured here**, not disproved.
   Everything below the weight form is the vendor's own code; the weight form is not.
2. **Audio longer than 30 s was never exercised.** Both oracle clips are under 15 s, so
   `pause_segments` / the model's own VAD head (which IS present: `vad_head` tensors load, `model.vad_head
   is not None`) never had to cut anything. The 2-caption output on the 15 s pt-BR clip is the sentence
   splitter (`_timed_segments`), not the VAD. The long-form path is untested.
3. **Word/character timestamps were never compared to a reference.** Only the segment boundaries were, and
   only against the ONNX oracle's own segment output.
4. **Two clips, one domain, one language pair** (pt-BR and en-US, clean 16 kHz WAV, same speaker corpus as
   before). No noise, no far-field, no music, no overlap. Nothing here says anything about robustness.
5. **No streaming/live path was touched** (`LiveAudioBuffer`, `live_audio_windows`, `STREAM_WINDOW_SECONDS`).
   This is the batch path only.
6. **The dense-vs-packed numerical difference was not quantified.** Kestrel documents `dense` as the oracle
   the packed path is tested against (bit-identical on MPS, "the oracle" on CPU), but this lane did not
   produce a third measurement to prove it: the packed path cannot run here to compare against.
7. **`--device cuda` was not tested.** It is exposed, and `resident_form("cuda") == "dense"` is a
   supported (if unoptimized) vendor path — 604 M weights as fp32 would not fit comfortably in 16 GB
   alongside activations in fp32, but bf16 would. Untried.
8. **Speed is noisy, not benchmarked.** §3.2's spread is background load on the owner's desktop. No
   quiet-box number exists.
9. **Load time is 3.8 s, not "a few tenths of a second".** It meets "loads in a few seconds" only in the
   loose sense; the ONNX oracle's own log line was `model loaded in 1.4s`. The gap is the dense
   dequantization in §2.3.
10. **The dependency `torch>=2.8` (declared by kestrel 0.9.1) is formally unsatisfied** — torch 2.7.0+cu128
    is what is installed and what was used. It worked for every code path exercised here, but a future
    vendor path could rely on a 2.8+ API this lane never reached.

---

## 7. Scratch created and deleted

`_main/_redux-dryrun/` (pip plan + report json + run logs), `_main/_redux-wheels/` (downloaded wheels and
their extracted trees), `_main/_redux-probe.py`, `_main/_redux-parity.py`, `_main/_redux-cli-parity.py`,
`_main/_redux-window-census.py`, `_main/_redux-mem.py`, `_main/_redux-photon.py` — all deleted. The
evidence for every number above is quoted in this file.

## 8. Attribution (CC-BY-4.0)

Model `moondream/parakeet-redux`, a 1.58-bit ternary re-quantisation of `nvidia/parakeet-tdt-0.6b-v3` by
NVIDIA — both **CC-BY-4.0**, attribution required. Runtime: **Photon** / `kestrel` by moondream. The
checkpoint, the runtime and their notices remain as published; this receipt and `worker/redux_batch.py`
add a wrapper and a measurement, nothing more.
