# receipt — 02 ASR: the first spec + the first product code of this repo

1. **What was asked.** Write `specs/02-asr.md` from what is **MEASURED** (engine = the int8 ONNX
   export; CPU; `intra_op=4`/`inter_op=1`; silence segmentation; ~10 s segments → ~0.88 GB flat;
   parity against the ternary oracle; the cost is in the encoder; a compact 10 Hz level event on
   stdout for the panel's wave), each constant with its provenance; **implement `src/asr/`** (a real
   module: CLI runner, named measured constants, silence segmentation, the 10 Hz level emitter, a
   parity harness); **prove the reproduction on the same slice** `plain-3600s.wav [900,1020)`
   (read-only from `H:\sotto`) with **RTFx, peak RSS and the text**; and leave **an oracle with both
   colours**. Deliverables written: `specs/02-asr.md` · `src/asr/{__init__,constants,audio,segment,level,engine,runner,transcribe,parity}.py`
   · `_main/{asr02-selftest,asr02-threadprobe,asr02-run,asr02-census,oracle-02-asr}.py` · artifacts in
   `_main/runs/asr02/` and `_main/logs/`.

2. **Answer in one line, and it REPRODUCES: the registered numbers hold.** On the same 120 s slice,
   same mode, same threads, the runner produced **11 segments (median 6.98 s, max 13.82 s)**,
   **814 chars whose sha256 is `746dfd19…` — byte-identical to the registered reference**, peak
   `wset` **924.3–926.4 MB** across 6 runs (registered 920.2–929.7), RSS after load
   **738.1–740.4 MB** (registered 734.9–741.6), **steady RTFx 6.15–9.17** (registered 8.74 on a
   quiet box; **this box was NOT quiet** — ambient 36 % plus the owner's live worker), and
   **1200 level events at exactly 10.0 Hz**. The ternary parity arms are **EXACT**: EN 130/130
   ratio 1.000000, and PT **159/159 ratio 1.000000** — *better than the registered 0.993711*.

3. **Prohibitions honoured.**
   - **Thread budget: `intra_op = 4`, `inter_op = 1`, `OMP/OPENBLAS/MKL/NUMEXPR = 4`** — the measured
     knee, not the minimum (law 8's ≤2 belongs to measurement lanes, `11-onnx-threads.md:53-57`).
     **What was actually used, measured:** the process's own CPU% during inference read
     **333.7–512.5 % median, ≤549 % max** over 6 runs, and a dedicated probe (below) shows the
     process is **not** 4 cores — the pin bounds ORT's pool, not the process. Disclosed, not hidden.
   - **No audio device was opened.** Every input was a `.wav`; the code has no capture path. The
     owner's worker (pid **29008**, holds an endpoint) and shell (pid **28428**) were **read from the
     process list once to confirm identity and never touched**.
   - **No visible window.** Every entry point is `pythonw.exe`; every child is spawned with
     `CREATE_NO_WINDOW` and stdout to a **FILE** (never a pipe). Two independent censuses at
     **100 ms** (the house 60 s census cannot see a short window): the oracle's own **381 samples →
     `visible_hits=0`, `distinct_pids=0`**, and a separate census over a **driver-spawned** child
     (**63 samples → 0 hits**, `CENSUS-VERDICT: CLEAN`).
   - **Writes only inside `H:\aireplay`**; `H:\sotto` was read-only (two wavs + two oracle txts +
     nothing else). **Nothing was killed**, so no kill filter was needed; the app was never touched.
   - **Model download: none.** The artefact was already on disk and was re-verified: the three LFS
     blobs' sha256 and the two small files' git blobIds match the HF API **5/5**.

4. **MEASURED — the reproduction, against the registered numbers.**

   | quantity | registered (doc, line) | this lane (6 runs) | verdict |
   |---|---|---|---|
   | segments | 11, median 6.98 s, max 13.82 s (`runs/threads11/silence-t4-p1.json`) | **11, 6.98 s, 13.82 s**; splitter boundaries differ by **0.000000 s** | exact |
   | transcript | 814 chars, sha256 `746DFD19…` (`11-onnx-threads.md:45`) | **814 chars, sha256 `746dfd19eabd1644d37dd5dbc9df4d661926b50c99d8d94520f732404bbd81cf`** | **byte-identical** |
   | peak `wset` | 920.2–929.7 MB silence (`11-onnx-threads.md:31-33`) | **924.3 / 925.1 / 925.9 / 926.2 / 926.3 / 926.4 MB** | inside the band |
   | RSS after load | 734.9–741.6 MB, 16 arms (`11-onnx-threads.md:30`) | **738.1–740.4 MB** | inside the band |
   | steady RTFx | 8.74 silence @4 threads (`11-onnx-threads.md:24`) | **6.15–9.17** (box loaded; ambient 36 %) | at/under the edge — **disclosed** |
   | load | 1.96–4.13 s @4 threads | 2.2–3.3 s | inside |
   | level cadence | 10 Hz, windowed, ≤~96 B (`12-audio-level-contract.md:20,43`) | **1200 events / 120.0 s = 10.0 Hz**, max **58 B** (mean 54.4) | exact |
   | encoder share | ≥95 % (`05-onnx-asr.md:91-93`) | **96.6 % steady** (last segment) — see §7 | holds, with a caveat |

5. **MEASURED — parity (the harness ships both kinds of oracle, labelled).**
   - **EN (TERNARY oracle)**: `src-en-8s.wav` vs `_main/redux-en.txt` → **EXACT, 130/130 chars,
     ratio 1.000000, 0 char/0 word diff blocks** — matches `05-onnx-asr.md:101`.
   - **PT (TERNARY oracle)**: `src-pt-15s.wav` vs `_main/redux-ptbr.txt` (cp1252, auto-detected) →
     **EXACT, 159/159, ratio 1.000000, 0 diff blocks — the hyphen in `segunda-feira` survives.**
     **This CORRECTS `05-onnx-asr.md:102`**: that arm's registered `ratio 0.993711` / one char came
     from a **ONE-SHOT 15 s pass** (`_main/runs/pt-15s.json`: one 15 s chunk, text
     `…segunda feira…`). **With silence segmentation the same clip is exact**, so the registered
     difference was a **chunking effect, not the model** — the same lesson as §3 of the spec. The
     PT lock in `constants.py` is tightened to EXACT accordingly.
   - **long slice (REGRESSION lock)**: the same-engine reference → **ratio 1.000000, 0 blocks,
     sha `746DFD19…`**. Labelled REGRESSION, never sold as independent evidence.
   - **fixed 10 s grid (CONTROL, must fail)**: ratio **0.21751** (648 vs 814 chars, 2 char-diff
     blocks, 5 word-diff blocks) — the registered trap is **0.229**, measured against a *different*
     reference (the sibling captions), so the two numbers are not the same claim; both say the grid
     destroys the text.

6. **MEASURED — the oracle, BOTH COLOURS, one command** (`_main/oracle-02-asr.py`, pythonw):
   `ARM-0` static **11/11 gates** · `ARM-A` product **12/12 gates** (threads 4/1, CPU provider only,
   silence, 11 segments, 814 chars + sha, 10 Hz × audio_s, `wset` in band, `rtfx_steady ≥ 5`) ·
   `ARM-B` **RED as expected** — a COPY of `src/asr` with `DEFAULT_SEGMENT_MODE` reverted to the grid
   → ratio 0.21751 · `ARM-C` **RED as expected** — a COPY with `INTRA_OP_NUM_THREADS` reverted to 1 →
   the run reports `intra=1` and the contract check fails. Each copy is patched with **exactly one**
   substitution (asserted). **`ORACLE-02-ASR VERDICT: PASS`, rc 0** (`_main/runs/asr02/oracle-02-asr.json`).
   **THE ORACLE EARNED ITS KEEP ON ITS FIRST RUN:** ARM-B reported `mode=fixed` while producing the
   *silence* text (ratio 1.0) — the dispatch compared against the **mutable default constant** instead
   of the literal mode name, so a broken copy silently ran the product's own path. Fixed
   (`constants.MODE_SILENCE/MODE_FIXED`, dispatch on the literals), and the model-free selftest now
   carries a `mode-dispatch-is-literal` guard so it cannot come back.

7. **MEASURED — the thread pin, and the one claim that does NOT survive as written.**
   `_main/asr02-threadprobe.py` (the product's own engine, same 10 s chunk ×3, in-process 250 ms CPU
   poll, inference phase only): **1 thread → 99.9 % median / 106.2 % max** (exactly one core);
   **4 threads → 507.1 % median / 781.2 % max** (≈5 cores), RTFx **3.30 → 7.21 = 2.18×**, text
   identical. So `11-onnx-threads.md:27`'s "CPU % measured = exactly N" is true **at 1 thread** and
   **not** true at 4 on the product's path — the mel preprocessor and ORT's own pool add cores. The
   *configuration* (`intra=4`, `inter=1`) is still the contract and is what the oracle checks, but
   **the AI Scheduler must budget ~5–8 cores for the ASR process, not 4** (law 8). Recorded in the
   spec §2 and in `constants.PROCESS_CPU_PCT_MEASURED`.

8. **MEASURED — where the cost is, re-derived from the product's own code** (`--phases` probes the
   first AND the last segment, `_main/runs/asr02/repro-silence-t4.json`): **last segment (3.96 s)
   preprocess 0.0038 · encode 0.4530 · decode 0.0122 s → encoder 96.6 %**; **first segment (8.06 s)
   preprocess 0.1454 · encode 1.2619 · decode 0.0170 s → encoder 88.6 %**, because the first
   preprocessor call is **38×** the steady one. So "encoder ≥95 %" is a **steady-state** figure and
   the first segment pays a cold-preprocessor warm-up; the TDT loop is 1.2–2.6 % either way.
   **Optimise the encoder, never the decode loop.**

9. **Corrections owed to the research docs (found here, stated plainly).**
   - **`05-onnx-asr.md:25` prints the artefact total as `670 589 803 B` — a 30 000-byte arithmetic
     slip.** The five registered files sum to **670 619 803 B** (652 183 999 + 18 202 004 + 139 764 +
     93 939 + 97); both round to 670.6 MB, which is what `AGENTS.md:162` and the HF tree say. The
     spec and `constants.py` use the measured sum, and the selftest checks it.
   - **`05-onnx-asr.md:102`'s PT "one difference" is a one-shot artefact** (§5 above).
   - **`11-onnx-threads.md:27`'s "CPU% = exactly N" holds only at 1 thread** on the product's path (§7).

10. **UNKNOWN, named.** Game audio (music/explosions/overlap) — still zero measurements for any
    candidate (`04-asr.md:132-134`) · audio past 120 s continuous under the budget (the lanes were
    budget-bound; the 20 min curve is the same slice repeated, `05-onnx-asr.md:60-66`) · the knee on
    a genuinely quiet box (none was available; my absolute RTFx is load-limited) · 8+ threads · the
    CUDA path · word timestamps · whether ORT's pool behaviour (the extra cores in §7) can be
    configured away without losing throughput (`session.intra_op.allow_spinning` — **not run**).

11. **Cost of being wrong, stated.** If the level event had stayed a run-maximum at 0.1 Hz, the
    panel's wave would be a monotone line that only rises — visually convincing and not the audio
    (`receipt-12-audio-level-contract.md:45-47`). If the fixed grid had been the default, the
    transcript would be **648 chars of seam garbage instead of 814 chars of the right text** — a
    search index over words that were never said.

**How to re-run everything (no device, no window, `H:\aireplay` only):**
`pythonw.exe _main\asr02-selftest.py` (model-free, rc 0) ·
`pythonw.exe _main\asr02-threadprobe.py` (the thread probe) ·
`pythonw.exe _main\asr02-run.py` (smoke + reproduction + ternary parity + regression) ·
`pythonw.exe _main\oracle-02-asr.py` (the gate: both colours, rc 0 = PASS) ·
`python src\asr\transcribe.py --wav FILE [--json]` or, from `src\`, `python -m asr.transcribe`.
