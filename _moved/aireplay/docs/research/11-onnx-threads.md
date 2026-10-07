# 11 — The optimal `intra_op_num_threads` for the int8 ONNX export

**Question (ONE):** for the istupakov int8 ONNX export on THIS box, is the best `intra_op_num_threads`
**1, 2, 4 or 6**? **Answer: 4.** It is **1.48–1.55× faster than 2**; **6 buys nothing** (1.01× fixed) or
**loses** (0.83× silence-aligned) for 600 % of a core instead of 400 %. **RAM does not move: 1 → 6 threads
costs +6 MB (+0.8 %)** — the 4 threads are speed for free. `MEASURED` = a command here produced it, file
named · `READ` = source read, file+line given · `UNKNOWN` = nobody has shown it. i5-13600K · Windows 11 · CPU only.

## 0. How it was run

`05-onnx-asr.md` §4 measured 1 / 2 / 6 / ORT-default and never **4**, and its thread arms used the **fixed
10 s grid** — the trap its own §5 scores at 0.229. `_main/probe-onnx-asr-threads.py` drives the **same
instruments, unchanged**, one arm at a time: `probe-onnx-asr.py --chunk-s 10` ("fixed") and
`probe-onnx-asr-split.py --mode silence --max-seg 15` ("silence"), on `plain-3600s.wav` **[900, 1020), the
same ≤120 s slice**, `int8`, CPU provider, `inter_op=1`, `OMP/OPENBLAS/MKL = intra_op`, **two passes per
count, the second REVERSED** (drift control); children `CREATE_NO_WINDOW` → FILE, **no audio device opened**. Raw: `_main/runs/threads11/summary.json`, `_main/logs/threads11.log`, `_main/logs/{fixed,silence}-t*.out`.

## 1. The numbers — RTFx in STEADY STATE (first chunk excluded, §3), MEAN of the two passes

| `intra_op` | RTFx fixed p1 / p2 (**mean**) | RTFx silence p1 / p2 (**mean**) | CPU % measured (median / max) | RSS after load | peak `wset` | load s |
|---|---|---|---|---|---|---|
| **1** | 2.59 / 3.04 (**2.82**) | 3.34 / 3.21 (**3.28**) | **100 / 106** | 735.3 MB | 880.0 MB | 1.90–3.92 |
| **2** | 4.75 / 5.10 (**4.93**) | 5.66 / 5.58 (**5.62**) | **200 / 313** | 738.7 MB | 882.7 MB | 1.95–4.16 |
| **4** | 7.60 / 6.97 (**7.29**) | **8.77 / 8.70 (8.74)** | **400 / 669** | 738.8 MB | 885.1 MB | 1.96–4.13 |
| **6** | 7.74 / 6.94 (**7.34**) | 7.52 / 6.94 (**7.23**) | **600 / 736** | 741.2 MB | 886.9 MB | 2.07–4.48 |

**The CPU column proves the pin was honoured:** 100 / 200 / 400 / 600 % — exactly N cores, no
oversubscription (silence reads 475 / 637 %: its energy splitter adds NumPy). **Marginal return per
thread: 1→2 = 1.75× / 1.72× · 2→4 = 1.48× / 1.55× · 4→6 = 1.01× / 0.83×** (fixed / silence) — the knee is
at **4**, and past it the curve is flat, then negative. **RSS is the weights, not the threads:** after load
**734.9–741.6 MB** over all 16 arms (spread 6.7 MB, monotone +6 MB from 1 to 6); peak `wset`
**879.6–886.9 MB** fixed / **920.2–929.7 MB** silence (lane 05: 873.7 / 909.1). Segment length sets the
peak; the thread count does not.

## 2. Where it stops paying — and the honest caveat

4 → 6 is a **tie** on the fixed grid (+1.8 % p1, −0.4 % p2) and a **14–20 % LOSS** on silence-aligned chunks
(both passes). The strongest single fact: **the two quietest arms of the whole sweep were `silence-t6-p1`
(ambient 11.2 %) and `-p2` (15.2 %) — and 6 threads still lost to 4**, which ran at ambient 27.8 % / 13.8 %.
**Disclosure — the box was NOT quiet:** whole-machine CPU was **10–47 %** (other lanes plus the owner's live
worker, pid 29008), so every absolute RTFx here is **14–19 % below lane 05's quiet-box numbers** — the
2-thread row (4.93 vs its 6.06) is the cleanest cross-check, both sides `OMP=2`. The **ranking and the knee**
are what this lane measures, and contention penalises the higher counts more, so the knee is not a load artefact.

**Controls.** All **8 arms of each instrument produced BYTE-IDENTICAL text** (fixed 648 chars; silence 814),
so the thread choice carries no quality trade. Lane 05's "first call after load is 2.5× faster" **does not
reproduce as a law**: first-chunk ÷ steady RTFx ranges **0.41–2.63** over the 16 arms — slower at 4 and 6
threads on the fixed grid (0.41–0.61, a warm-up cost), faster at 2 on silence (2.56 / 2.63), 1.0–2.3 at 1
thread. **Sign not stable, mechanism UNKNOWN** — hence the steady-state column above.

## 3. Verdict, and what stays UNKNOWN

- **Pin `intra_op_num_threads = 4`, `inter_op = 1`.** 1.48–1.55× the 2-thread budget for +2 cores and
  **+6 MB**; 6 threads is the same RAM for nothing, or a loss. Against ORT's **default** (3.11× while burning
  690 %, `05-onnx-asr.md` §4) 4 threads is **~2.4× the throughput at 400 %** — the default stays forbidden.
- **For law 8:** 4 threads is ~4 of 20 logical CPUs, far under the 7.3-core incident that law was written
  from; the AI Scheduler still owns the budget, and this is the ONNX engine's setting inside it.
- **UNKNOWN:** the knee on a genuinely quiet box (none was available); whether 6 would edge past 4 on the
  fixed grid alone (+1.8 % once, −0.4 % once — inside the noise); the mechanism of the first-chunk anomaly;
  **8 threads and above (never run — outside this lane's budget)**; the CUDA path; audio past 120 s.
