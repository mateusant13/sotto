# 10 — The ternary Redux runner at the 2-thread budget

**Question (ONE):** the ternary/TDT Redux runner is registered at **5–14× real time** (`receipt-redux-ternary.md`)
and the int8 ONNX export measured **6.06× at 2 threads** (`05-onnx-asr.md` §4). The ternary's 5–14× was taken at
**default threads**, and this box proved ORT's default is pathological. **So what is the ternary's RTFx at 2
threads — better, equal or worse than its own default?**
**Scope: cost only** — parity is proven byte-identical and is NOT re-run. `MEASURED` = a command on this box
produced it, file named · `READ` = source read, file+line · `UNKNOWN` = nobody has shown it.
Host: Windows 11 · i5-13600K (14C/20T) · RTX 5080 · CPU only · owner's app (shell 28428, worker 29008) left running.

## 0. Answer in one line

**The runner refuses the budget; imposing it through the runtime's own knob makes the ternary SLOWER — ~4.1× real
time, ~1.8× under its own default of 4 threads — so at the 2-thread budget the int8 ONNX export (6.06×, ~0.9 GB)
beats it on speed AND on RAM.**

## 1. The runner does not accept a thread limit — MEASURED

- `H:\sotto\worker\redux_batch.py` (8559 B, sha256 `C5D44F93…A989`) has **no thread flag**: its argparse is
  `--wav --json --model-dir --device --timestamps` (`READ`, `:149-156`).
- With `OMP_NUM_THREADS=2` **and** `OPENBLAS_NUM_THREADS=2` exported, torch reads **2** at import — and the
  kestrel runtime **overwrites it at load with 4**: `torch_threads(before=2, after_load=4, after_infer=4)`
  (`arm-env2t-as-is.json`). Mechanism (`READ`): `redux_batch.py:108` sets `cpu_threads = None`, so
  `kestrel/models/parakeet_tdt/runtime.py:176-196` calls `torch.set_num_threads(_default_cpu_threads(...))`;
  on Windows `_physical_cpu_count()` returns `os.cpu_count()` (`:84-87`) and `is_ternary` is True (`weights.py:182`)
  → `_NATIVE_GEMM_THREAD_CAP = 4` (`:53`). **The env vars are inert for this runner.**
- Control, the raw script, unmodified, `OMP_NUM_THREADS=2`: `120.0s of audio in 16.90s, 7x real time`
  (`raw-runner-control.err`) — the default-thread speed, i.e. the env var changed nothing.
- The runtime's OWN documented knob (`RuntimeConfig.cpu_threads`) **does** work: `torch_threads(after_load=2)`,
  CPU median 184–188 % ≈ 1.8 effective threads. That is the only way to impose 2 threads, and it is what the
  `forced2t` arms use (via `_main/redux-2t/redux-2t-probe.py`, which imports the runner read-only).

## 2. RTFx — 2 threads is WORSE, by ~1.8×

Same audio as the ONNX lane: `plain-3600s.wav` **[900,1020)**, 16 kHz mono, cut to `_main/redux-2t/slice-900-1020.wav`
(3 840 044 B, sha256 `08E60694…FE62`, 120.000 s). All arms serial, one process each, 13 arm JSONs in `_main/redux-2t/`.

| arm (same 120 s slice) | torch threads | audio s | RTFx steady | RTFx pass 0 | peak `wset` | CPU med | load s |
|---|---|---|---|---|---|---|---|
| default, as shipped | **4** | 1200 | **7.41** | 7.29 | 4619 MB | 337 % | 4.57 |
| default, as shipped | 4 | 360 (×2 runs) | 7.52 / 6.27 | 6.74 / 6.23 | 4612 MB | 343–358 % | 6.1 / 8.1 |
| **OMP=2 only, as shipped** | **4** | 120 | 6.29 | 6.29 | 4583 MB | 291 % | 10.33 |
| forced **2** | **2** | 1200 | **4.12** | 3.78 | 4505 MB | 184 % | 10.01 |
| forced 2 | 2 | 600 | 4.29 | 4.36 | 4581 MB | 186 % | 10.30 |
| forced 2 | 2 | 360 (×2 runs) | 3.55 / 3.48 | 3.82 / 3.46 | 4582 / 4486 MB | 188 / 186 % | 10.1 / 14.0 |
| default · `src-en-8s` / `src-pt-15s` | 4 | 25.6 / 45 | 6.57 / 7.31 | 6.03 / 6.57 | 3887 / 3893 MB | 351–358 % | 6.1 / 5.1 |
| forced 2 · `src-en-8s` / `src-pt-15s` | 2 | 25.6 / 45 | 3.96 / 4.01 | 3.92 / 4.23 | 3799 / 3787 MB | 180–183 % | 9.9 / 10.1 |

**Verdict on the asked question: WORSE.** 2 threads is **~1.8× slower** than the runner's own default — **1.72–2.16×**
across every paired arm (7.41/4.12 = 1.80 on the 1200 s arms; the four **interleaved** 360 s arms give 7.52 vs 3.55
and 6.27 vs 3.48). The honest 2-thread number for the ternary is **≈4.1×** (range 3.48–4.30 over 13 arms), **not 5–14×**.
The regime is flat — pass 0 ≈ steady. **PyTorch's default is NOT pathological the way ORT's is**: 4 threads deliver
337 % CPU and 1.8× the throughput, so pinning 2 threads costs real speed instead of buying it.

## 3. Where the time goes, and the RAM — encoder-bound, and 5× the ONNX export

- **Encoder 79.7–88.5 % of inference, decode 3.3–11.0 %** (`encoder_s` / `decoder_s` in every arm JSON, timed on
  the model's own `encoder` / `decoder` module calls) — **the same shape as the ONNX lane** (`05-onnx-asr.md:91-95`).
  Optimising the TDT loop buys nothing here either.
- **Load is thread-bound too: 4.6–8.1 s at 4 threads vs 9.9–14.0 s at 2** — the dense dequantisation of 193
  layers is compute, so the budget doubles the load as well.
- **RSS after load 3614–3885 MB; peak `wset` 4486–4619 MB at the 120 s slice**, 3787–3893 MB on the short clips.
  The registered "3.90 GB" is a **short-clip** figure: at 120 s the ternary peaks at **4.5–4.6 GB**.
- **Curve over 1200 s (10×120 s in series, 165 / 301 points at 1 Hz): FLAT — no leak.** After load the default
  arm sits at 3682–3775 MB mean per 17 s segment with a recurring per-pass spike to ~4.43 GB (max 4616 MB);
  the 2-thread arm 3491–3655 MB with the same spike to ~4.42 GB. The spikes repeat identically each pass —
  per-pass working set, not accumulation.

## 4. The choice, closed

| at the 2-thread budget, same slice | RTFx | peak RSS | weight on disk |
|---|---|---|---|
| ternary Redux (`redux_batch.py`, own pause-aligned segmentation) | **3.48–4.30×** (≈4.1×) | **4.49–4.58 GB** | 179 MB |
| int8 ONNX export (`05-onnx-asr.md` §3–4, `READ` — not re-measured here) | **6.06×** (10 s chunks) / 5.55× (20 min) / 6.28× (silence-aligned) | **0.87–0.92 GB** | 670.6 MB |

**The ONNX int8 export wins on both axes at the budget the house mandates: ~1.4–1.5× faster and ~4.9–5.2× lighter.**
The fear that the comparison "premiou o motor mal-educado" is refuted — **the ternary is the engine whose registered
speed does not survive the budget.** The only ONNX arm the ternary beats is "one 120 s encoder pass" (3.92×), the
unsegmented one-shot the ONNX lane itself flagged as the trap. At 4 threads the ternary reaches 7.41×, but the ~5× RAM gap stands.
**UNKNOWN:** ONNX int8 at 4 threads (its measured points are 1 / 2 / 6 / default — 4 is an interpolation) · ternary on CUDA (never run) · audio past 120 s.
