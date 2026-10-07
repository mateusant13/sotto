# receipt-10-redux-2-threads — what was RUN, what was VERIFIED, what is UNKNOWN

**Question (ONE):** the ternary Redux runner is registered at **5–14× real time** but that was measured at
**default threads**, and this box proved ORT's default is pathological. **What is its RTFx at 2 threads — better,
equal or worse than its own default?** Answer: **WORSE — ~4.1×, ~1.8× under its own default of 4 threads — and
the runner refuses the 2-thread budget unless the runtime's own knob is used.** Doc: `docs/research/10-redux-2-threads.md`.

## 1. What was run, and the audio being compared

- **`H:\sotto\worker\redux_batch.py` was NOT edited and NOT copied**: `sha256 C5D44F93C4AA3DA7905FEF5A40A61464E3D165BEABF3C57A139D9AA0C9DEA989`,
  8559 B, mtime 2026-10-07. The probe (`_main/redux-2t/redux-2t-probe.py`) **imports** its `load_runtime` / `transcribe`
  — the same two functions the script calls — and adds only instrumentation (torch thread read-back, 1 Hz RSS+CPU,
  encoder/decoder module timing, per-pass wall). **Nothing in `H:\sotto` was written.**
- **Same audio as the ONNX lane:** `plain-3600s.wav` **[900,1020)** → `_main/redux-2t/slice-900-1020.wav`
  (3 840 044 B, sha256 `08E60694F490C1A849CD22E1870F5008DAB39EE5C027B7565FD659E894EFFE62`, 120.000 s, 16 kHz mono
  PCM_16), cut by `_main/redux-2t/make_slice.py`. **3.8 MB, well under the ~200 MB cap.** Slices repeated in series
  (10×, 5×, 3×), never a long single file.
- Weights: `parakeet-redux-ternary\model.safetensors` 177 774 490 B `78EC25733EE0D0C1586D1346FC86DB9D0C2E436E3A8AB1D32A82D1BB8F848D21`.
  Runtime path: **`dense`** (kestrel's documented fallback; `ternary_gemm_isa()` → `None`, `ternary_gemm_ready()` → `False`),
  i.e. the same residency the 3.90 GB figure came from.
- **No audio device was opened** (wav files only). **Nothing was killed.** The owner's app was left alone: shell
  **28428** and worker **29008** were alive and untouched before, during and after (verified by a
  `Get-CimInstance Win32_Process` census naming the full artifact paths).

## 2. The budget — the runner does NOT accept it (MEASURED, and that IS the result)

- `OMP_NUM_THREADS=2` + `OPENBLAS_NUM_THREADS=2` were exported for every budgeted arm. **torch read 2 at import and
  the kestrel runtime overwrote it to 4 at load**: `torch_threads(before=2, after_load=4, after_infer=4)`
  (`arm-env2t-as-is.json`). `READ`: `redux_batch.py:108` sets `cpu_threads = None` → `runtime.py:176-196` calls
  `torch.set_num_threads(_default_cpu_threads(...))`; `_physical_cpu_count()` falls back to `os.cpu_count()` on
  Windows (`:84-87`) and `_NATIVE_GEMM_THREAD_CAP = 4` (`:53`) because `is_ternary` is True (`weights.py:182`).
- **Control on the raw script, unmodified, `OMP_NUM_THREADS=2`:** `redux_batch: slice-900-1020.wav: 120.0s of audio
  in 16.90s, 7x real time` (`_main/redux-2t/raw-runner-control.err`) — the env var changed nothing.
- The budget is therefore imposed through the **runtime's own documented knob** (`RuntimeConfig.cpu_threads`, via a
  subclass in the probe). It works: `torch_threads(after_load=2)`, **CPU median 184–188 %** ≈ 1.8 effective threads
  (`cpu_effective_threads` in every arm JSON). **Thread count is measured, not assumed.**

## 3. The numbers (13 arms, `_main/redux-2t/arm-*.json`; full tables in the doc)

| arm | torch thr | audio s | RTFx steady | pass 0 | peak `wset` | CPU med | load s |
|---|---|---|---|---|---|---|---|
| default, as shipped | **4** | 1200 | **7.41** | 7.29 | 4619 MB | 337 % | 4.57 |
| **OMP=2 only, as shipped** | **4** | 120 | 6.29 | 6.29 | 4583 MB | 291 % | 10.33 |
| forced **2** | **2** | 1200 | **4.12** | 3.78 | 4505 MB | 184 % | 10.01 |
| forced 2 | 2 | 600 | 4.29 | 4.36 | 4581 MB | 186 % | 10.30 |
| forced 2 | 2 | 360 ×2 | 3.55 / 3.48 | 3.82 / 3.46 | 4582 / 4486 MB | 188 / 186 % | 10.1 / 14.0 |
| default | 4 | 360 ×2 | 7.52 / 6.27 | 6.74 / 6.23 | 4612 MB | 343–358 % | 6.1 / 8.1 |
| clips `en-8s` / `pt-15s`, default | 4 | 25.6 / 45 | 6.57 / 7.31 | 6.03 / 6.57 | 3887 / 3893 MB | 351–358 % | 6.1 / 5.1 |
| clips `en-8s` / `pt-15s`, forced 2 | 2 | 25.6 / 45 | 3.96 / 4.01 | 3.92 / 4.23 | 3799 / 3787 MB | 180–183 % | 9.9 / 10.1 |

- **2 threads is 1.72–2.16× SLOWER** than the runner's own default — ~1.8× on every paired arm (7.41/4.12 = 1.80 on
  the 1200 s arms; the four **interleaved** 360 s arms give 7.52 vs 3.55 and 6.27 vs 3.48). Honest 2-thread figure:
  **≈4.1×** (3.48–4.30 over 13 arms). **The registered 5–14× is a 4-thread number.** Regime is flat — pass 0 ≈ steady.
- **Encoder-bound: 79.7–88.5 % of inference; decode 3.3–11.0 %** (timed on the model's own `encoder`/`decoder` module
  calls) — the same shape the ONNX lane found.
- **Load is thread-bound too: 4.6–8.1 s at 4 threads vs 9.9–14.0 s at 2.**
- **RSS:** after load 3614–3885 MB; **peak 4486–4619 MB at the 120 s slice**, 3787–3893 MB on the clips. The
  registered **3.90 GB is a short-clip number**. Curve over 1200 s (165 / 301 points at 1 Hz): **FLAT, no leak** —
  default arm 3682–3775 MB per 17 s segment with a recurring per-pass spike to ~4.43 GB (max 4616); 2-thread arm
  3491–3655 MB, same spike to ~4.42 GB, repeating identically each pass.

## 4. The choice this closes

At the **same 2-thread budget and the same slice**: ternary **3.48–4.30×** (≈4.1×) at **4.49–4.58 GB** vs the int8 ONNX
export's **6.06×** (10 s chunks) / **5.55×** (20 min steady) / **6.28×** (silence-aligned) at **0.87–0.92 GB**
(`05-onnx-asr.md` §3–4, **`READ` — not re-measured in this lane**). **The ONNX int8 export wins on both axes:
~1.4–1.5× faster and ~4.9–5.2× lighter.** The ternary's registered speed does **not** survive the product's own
thread budget, and the only ONNX arm it beats (one unsegmented 120 s pass, 3.92×) is the regime the ONNX lane
flagged as the trap. At 4 threads the ternary reaches 7.41× but the ~5× RAM gap is unchanged.

## 5. Instrument honesty

- **Window census, with its positive control.** `_main/redux-2t/window-census.ps1` samples its own cadence
  (**200–250 ms**, `Get-CimInstance Win32_Process`, filter = the **full artifact paths**
  `H:\aireplay\_main\redux-2t\redux-2t-probe.py` and `H:\sotto\worker\redux_batch.py`, restricted to `python*`).
  Final validation run: **200 samples, 32 process-samples seen, `distinct_pids=1`, `visible_hits=0`** — and the
  positive control is the same regex matching a **known-live** process (`H:\sotto\worker\sotto_worker.py`, pid 29008)
  in a one-shot query. **The first version of this census was VACUOUS and was caught**: `seen_process_samples=0`
  across 720 samples while four arms were running, because the inner `Where-Object { $_.CommandLine -like "*$_*" }`
  rebound `$_` to the pattern string, so the filter could never match anything. Fixed to a single escaped regex and
  re-validated before any absence was claimed. Every arm was launched with `pythonw.exe`.
- **Confound, stated:** the census's WMI sampling ran concurrently with most arms (~0.5 % of a core). Arms were
  **interleaved** (default → 2t → default → 2t, back to back), so the A/B ratio is not affected by it; the absolute
  RTFx of the two 1200 s arms carries the usual ±15 % run-to-run spread this box shows (the owner's app was live).
- **No thread count was assumed anywhere** — every RTFx row above carries the `torch.get_num_threads()` read back
  from the process that did the work, plus its measured CPU %.

## 6. UNKNOWN (nobody has shown these)

- **ONNX int8 at 4 threads** — its measured points are 1 / 2 / 6 / default; 4 is an interpolation, not a measurement.
- The ternary on **CUDA** (`--device cuda`): never run; `torch.cuda.is_available()` is True here but the product is CPU-only (law 5).
- Audio **past 120 s of continuous input** in one file, and the bundled VAD/segmenter's behaviour on game audio, music or overlap.
- Whether the kestrel **`gemm8`** packed kernel (unreachable on this Windows wheel) would change the thread scaling — not measured, not refuted.
- **Why 4 threads and not 8**: `_NATIVE_GEMM_THREAD_CAP = 4` is the vendor's cap for the ternary GEMM path, read from source, not measured as optimal.
