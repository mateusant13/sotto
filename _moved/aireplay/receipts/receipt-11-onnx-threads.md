# receipt-11-onnx-threads — what was RUN, what was VERIFIED, what is UNKNOWN

**Question (ONE):** for the istupakov int8 ONNX export on this box, is the optimal `intra_op_num_threads`
**1, 2, 4 or 6**? **Answer: 4** — 1.48–1.55× the 2-thread budget, and 6 buys nothing (1.01× on the fixed
grid) or loses (0.83× on silence-aligned chunks) for 600 % of a core instead of 400 %. RSS is unmoved.
Doc: `docs/research/11-onnx-threads.md` (60 lines, sha256 `CAEF5ED6…B82930`).

## 1. What was run — and the two bugs the instrument had to lose first

`_main/probe-onnx-asr-threads.py` (sha256 `20796AE3…1AD8742`) **drives lane 05's instruments unchanged** —
`_main/probe-onnx-asr.py` (sha256 `679AF9A7…26F7AA`, `--chunk-s 10`, "fixed") and
`_main/probe-onnx-asr-split.py` (sha256 `5945E79F…C2892D`, `--mode silence --max-seg 15`, "silence") — on
`H:\sotto\_main\_redux-long\plain-3600s.wav` **[900, 1020), the same ≤120 s slice lane 05 used**, `int8`,
`CPUExecutionProvider`, `inter_op_num_threads=1`, `OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS = intra_op`.
It adds three things the instruments lacked: **CPU % split by PHASE** (the child's own pid polled at 250 ms
from outside; the phase boundary is the child's first per-chunk stdout line), **steady-state RTFx** (first
chunk excluded), and RSS at the same cadence. **Two passes per count, the second in REVERSE order**
(1,2,4,6 then 6,4,2,1) — a drift control, because the box is not quiet.
**Two instrument defects were found and fixed before any number was kept:** (a) the phase detector first
keyed on lines starting with two spaces, which `probe-onnx-asr.py` never emits (its chunk lines start with
`[`), so the first sweep reported `cpu_infer = None` — that sweep was killed by exact pid after reading its
command line, and re-run; (b) the first census was started as a `Start-Job` of a tool shell and died with it,
writing no file — replaced by a detached hidden `pwsh` (`_main/census11.ps1`, sha256 `848116AC…BD80F`).
**All 16 arms returned rc=0 and a JSON.** Raw: `_main/runs/threads11/summary.json` (sha256 `CBAE8D3D…3D04D`),
`_main/logs/threads11.log`, `_main/logs/{fixed,silence}-t*.out`.

## 2. The numbers (MEAN of the two passes; RTFx in steady state)

| `intra_op` | RTFx fixed p1 / p2 (**mean**) | RTFx silence p1 / p2 (**mean**) | CPU % measured (median / max) | RSS after load | peak `wset` | load s |
|---|---|---|---|---|---|---|
| 1 | 2.59 / 3.04 (**2.82**) | 3.34 / 3.21 (**3.28**) | 100 / 106 | 735.3 MB | 880.0 MB | 1.90–3.92 |
| 2 | 4.75 / 5.10 (**4.93**) | 5.66 / 5.58 (**5.62**) | 200 / 313 | 738.7 MB | 882.7 MB | 1.95–4.16 |
| **4** | 7.60 / 6.97 (**7.29**) | **8.77 / 8.70 (8.74)** | 400 / 669 | 738.8 MB | 885.1 MB | 1.96–4.13 |
| 6 | 7.74 / 6.94 (**7.34**) | 7.52 / 6.94 (**7.23**) | 600 / 736 | 741.2 MB | 886.9 MB | 2.07–4.48 |

**Knee = 4.** Marginal return: 1→2 = 1.75× / 1.72× · 2→4 = **1.48× / 1.55×** · 4→6 = **1.01× / 0.83×**
(fixed / silence). **CPU % is the proof the pin was honoured: exactly N cores** (silence reads 475 / 637 %
because its energy splitter adds NumPy). **RSS after load spans 734.9–741.6 MB across all 16 arms** — a
6.7 MB spread, monotone +6 MB from 1 to 6 threads: **the weights set the RSS, not the threads**, so the
4 threads are speed for free. Peak `wset` 879.6–886.9 MB (fixed) / 920.2–929.7 MB (silence), matching lane
05's 873.7 / 909.1 — segment length still sets the peak. **Load: 1.88–2.30 s warm, 3.9–4.5 s under load**
(the first load of the sweep read 3.92 s; the same arm later read 1.90 s — page cache plus ambient load).

## 3. Two controls, both of which could have said NO

- **Transcript parity:** all **8 arms of each instrument produced BYTE-IDENTICAL text** (fixed 648 chars,
  silence 814) — the thread count carries no quality trade, and the four rows are comparable.
- **The first chunk is atypical, but NOT in a fixed direction:** first-chunk ÷ steady RTFx ranges **0.41 to
  2.63** over the 16 arms (slower at 4/6 on the fixed grid, faster at 2 on silence). Lane 05's "2.5× faster
  first call" is therefore **not a law**; the mechanism is UNKNOWN and every RTFx above excludes it.
- **The window census is not vacuous:** `_main/census11.ps1`, **4737 samples at 200 ms over 1200 s**,
  `visible_hits=862`, **`distinct_pids=1`** — and that pid is **28428, the owner's own `Sotto` shell**
  (started 08:01:55, before this lane). **No pid of mine ever mapped a window**; every child was spawned
  `CREATE_NO_WINDOW` with output to a FILE, never a pipe.

## 4. Budget and house rules — as run

Never above **6** threads; every arm a **≤120 s** slice, **in series** (no two arms alive at once);
**362 KB** written across 36 files (limit ~200 MB); **all writes inside `H:\aireplay`** (the wav was read
read-only from `H:\sotto`); **no audio device opened** (wav only); **no network** (local model dir →
`offline=True`); the model directory is untouched (newest mtime 06:47:53, before this lane).
**The owner's processes were not touched** — pids **28428** and **29008** still hold their 08:01:55/56 start
times. Two processes of mine were killed, **by exact pid after reading their command lines** (15380, 16072).
Free RAM returned to ~29.8 GB. **The machine never reacted badly.**

## 5. UNKNOWN, by name

(1) **The knee on a genuinely quiet box** — none was available: whole-machine CPU ran **10–47 %** during the
sweep (other lanes plus the owner's live worker 29008), so every absolute RTFx here is **14–19 % below lane
05's quiet-box numbers** (2 → 4.93 vs 6.06; 6 → 7.34 vs 8.51; 1 → 2.82 vs 3.30). The ranking and the knee are
what this lane measures; contention penalises the higher counts more, so the knee is not a load artefact —
but a quiet-box confirmation is still owed. (2) Whether 6 would edge past 4 on the **fixed grid alone**
(+1.8 % in p1, −0.4 % in p2 — inside the noise). (3) **8 threads and above — never run** (outside this lane's
budget). (4) The mechanism of the first-chunk anomaly. (5) The CUDA path. (6) Audio past 120 s continuous.

## 6. Reconciliation with lane 05

Nothing of lane 05's was overwritten; its instruments and results stand. Where this lane meets it: RSS after
load 735–741 MB (its 735–748), peak `wset` 880–887 / 920–930 MB (its 881.4 / 923.1), silence-aligned peak
908–916 MB (its 909.1). Its thread table (1 → 3.30×, 2 → 6.06×, 6 → 8.51×, default → 3.11×) is reproduced
**in order** at 2.82 / 4.93 / 7.34 here (means), lower in absolute value for the contention named in §5.
**What this lane adds:** the missing **4-thread row** (the knee), the silence-aligned thread sweep (its own
§5 trap avoided), the phase-split CPU proof that the pin is honoured exactly, the flat-RSS-vs-threads result,
the 16-arm transcript parity, and the refutation of the first-call rule as a law.
