# receipt — 07 index & search (store, schema, fusion, reranker, two speeds)

1. **Run (all hidden, `pythonw.exe`, no console, no audio device touched):** the lane budget was pinned
   **before** each launch — `$env:OMP_NUM_THREADS='2'; $env:OPENBLAS_NUM_THREADS='2'; $env:MKL_NUM_THREADS='2'`
   — and the JSON records `thread_env` so no number travels without it. Processes, all started with
   `Start-Process -WindowStyle Hidden` and all exited:
   - `pythonw.exe _main\_index-final-probe.py --json _main\index-final.json` (pid 2660, ~55 s)
   - `pythonw.exe _main\_index-ann-probe2.py --json _main\index-ann.json` (pid 12608, ~170 s; faiss pinned
     with `faiss.omp_set_num_threads(2)` as well, because `OMP_NUM_THREADS` alone is not proof)
   - `pythonw.exe _main\_index-crash2-probe.py --json _main\index-crash2.json --rows 20000` (pid 31284)
   - `pythonw.exe _main\_index-crash-neg-probe.py --json _main\index-crash-neg.json --rows 20000` (pid ~, 25 s)
   - `pythonw.exe _main\_index-hnsw-probe.py` (**died twice, silently, no output** — see §5) and
     `pythonw.exe _main\_index-crash-probe.py --json _main\index-crash.json --rows 20000`
2. **Files, with sha256** (`Get-FileHash -Algorithm SHA256`):
   `docs\research\07-index-search.md` 16 240 B `E51C458B1F57DDC1D3AB52BA5E518916285F077F500EB8A4249729634FEE6A39`;
   `_main\index-final.json` 18 410 B `72B9569D3BB358350044562547DC3AC2EE07C933B7A0D5ECF9AA236A18B25F17`;
   `_main\index-ann.json` 2 296 B `C54B940D9F60AFCD286EE80A9D56E79D3DD88478EFF443AFDE95DE493EA9D275`;
   `_main\index-crash2.json` 2 055 B `7C9EAB8AC13E308C5F6BEB3287CD09895E7B41C29BFFAAD43E5A5727234B447C`;
   `_main\_index-final-probe.py` `430FBA08…`; `_index-ann-probe2.py` `A43F3C30…`; `_index-crash2-probe.py`
   `F6233E66…`; `_index-crash-neg-probe.py` `E78350CD…`. Superseded/inconclusive: `index-crash.json`,
   `index-crash-neg.json` (kept as evidence of the failed control, NOT to be quoted).
3. **Inherited from the interrupted lane and REUSED, not rebuilt:** `_main\_index-store2\A_nopartition.db`
   (120 k vec0, 124.6 MiB) and `_main\_index-store\index.db` (211 200 vec0 partitioned by `video_id`,
   **1050 MiB**). Both were opened read-mostly and only `pragma wal_checkpoint(TRUNCATE)` was run on them.
   Its probe `_index-store-probe3.py` returned **0.0 ms on every arm** — a broken measurement, discarded and
   not cited. Its pre-existing artefacts total **~2.6 GB**; this lane added ~395 MB (§6).
4. **What settles each question (all MEASURED at 2 threads, this box, 2026-10-07):**
   - **Store:** numpy brute force **7.64 ms** (120 k, `k=100`) / **15.99 ms** (211 200, three channels);
     `sqlite-vec` vec0 **118.9 / 136.1 ms** at 120 k (**16×** numpy) and **902 / 1074 ms** plus a **1050 MiB**
     file when partitioned by `video_id`; faiss `IndexFlatIP` **4.95 ms/query** in a batch of 100; faiss HNSW
     build **85.21 s**, query **0.154–1.216 ms**, `recall@10` **0.034–0.29**, file **134.8 MiB**, and
     **`remove_ids` is not implemented** (`RuntimeError`, MEASURED). Crossover **50 ms at N ≈ 582 k**.
   - **Schema:** the answer JOIN measured at **0.011 ms** → `"clip_0644.mp4 @ 04:05.0"`; one file carries the
     relational half + 211 200 fp16 vectors = **137.34 MiB / 144.01 MB** (**+33.2 %** over payload).
   - **Fusion:** RRF over three channels, query → 10 explainable hits **72.6 ms min / 83.2 ms median**; window
     controls **10/10 in (42, 0–60 s)** and **exactly 1 hit in (42, 60–65 s)**.
   - **Reranker:** measured GEMM **53.8 GFLOP/s** fp32 at 2 threads ⇒ the smallest candidate
     (`ms-marco-MiniLM-L6-v2`, 22 714 113 params, apache-2.0) costs **10.8 s** for 100×128-token candidates;
     lexical overlap over the same 100 candidates = **0.146 ms**. **Verdict: no reranker.**
   - **Two speeds:** light commit of one 5 s window (segment + transcript + 2 vectors) **0.061 ms median /
     p95 0.198 ms**; bulk insert **92 688 vectors/s**; promotion is idempotent because
     `embedding(seg_id, channel)` is the primary key.
   - **Arithmetic:** the brief's **122.88 MB FP32 / 61.44 MB FP16** is right **for ONE vector per segment**;
     three channels = **216.27 MB FP32 / 108.13 MB FP16** (**1.76×**), plus **+33.2 %** store overhead.
5. **Controls (the house rule — an instrument that cannot say NO is worthless).**
   - **Crash safety, both colours in ONE instrument** (`_index-crash2-probe.py`), with the kill aimed by a
     `T:` marker at the instant the writer is **inside** a transaction and `taskkill /F /PID` on the exact pid:
     **ARM A** WAL/`synchronous=NORMAL` → `integrity_check=ok`, **16 000 rows = a clean multiple of the 2 000
     batch**, KNN answers, **green**. **ARM B** `journal_mode=OFF, synchronous=OFF` → **18 041 rows**, a *torn*
     count, RED. **ARM C** + `cache_size=50` → `integrity_check` = **"database disk image is malformed"**, 6
     invalid page numbers, query raises `DatabaseError: database disk image is malformed`, RED. **Two red
     controls ⇒ the green is earned.** The first attempt (`_index-crash-probe.py`, fixed 0.35 s sleep) could
     not say NO: its control came back **green** because the in-flight transaction fitted in SQLite's page
     cache and never reached the file. That first green is **not** quoted as evidence.
   - **Fusion:** explainability control (`all 10 hits name ≥ 1 channel`, all three channels in the top-10,
     10/10 matched by >1 channel) and two window controls (above).
   - **fp16:** stored-fp16 top-10 is **identical** to the fp32-stored top-10 (10/10).
6. **Disk added by this lane: ~395 MB, no single artefact above ~200 MB** — `_index-final\store.db` 144.0 MB
   (the recommended store, kept as the concrete artefact), `_index-ann\hnsw.faiss` 141.4 MB,
   `_index-final\vec0-live.db` 22.2 MB, `_index-crash\` 43 MB, `_index-crash2\` 44 MB,
   `_index-final\light.db` 0.27 MB. **Installed nothing.** Everything used was already present
   (`numpy` 1.26.4, `sqlite-vec` 0.1.9, `faiss-cpu` 1.15.1, `pyarrow` 25.0.0). Licences and installed bytes
   were read from the local dist-info (MEASURED): `sqlite-vec` **"MIT License, Apache License, Version 2.0"**,
   295 723 B; `faiss-cpu` **MIT**, 64.5 MiB; `numpy` BSD, 68.4 MiB. **READ** (not installed, so not measured):
   `hnswlib` 0.8.0 is **sdist-only** on PyPI (no wheel for any platform, so it cannot be built without MSVC
   14.0+, absent here); `lancedb` 0.40.0 Apache-2.0 pulling `pyarrow>=16`; `qdrant-client` 1.19.1 Apache-2.0
   pulling `grpcio`/`httpx`/`protobuf`. **No model was downloaded and no weights were loaded.**
7. **Window and audio discipline:** every process was `pythonw.exe` (GUI subsystem — it creates no console)
   launched `-WindowStyle Hidden`; **no audio device was opened**; no visible window was created. Checked
   against the house census: `_main\logs\window-census.log` and `_main\logs\census11.log` contain **no
   `ALERTA-JANELA` naming any pid of mine** (2660, 11892, 5228, 12608, 31284) — the only entries in the window
   name **pid 28428**, the owner's own `sotto_webview.py`, which was already running. Caveat, stated because
   the house earned it: a 60 s census can only prove presence, so this is "the census never named me", not
   "nothing could have flashed".
8. **UNKNOWN, and the fixture caveats I will not hide:**
   - The **speech 60 % / OCR 16 %** coverage fractions are this lane's **assumption**, not a measurement —
     §6 of the doc is parametric in them. Real numbers come from lane 02 and the ASR lane.
   - The **`store.db` fixture's text rows use an independent random draw** from the vector corpus, so a hit's
     `transcript`/`ocr` text can be NULL even when the channel is present. The **JOIN itself is measured**
     (0.011 ms, and it returns a real path + `start_ms`); the text pairing is a fixture artefact.
   - **HNSW recall on real embeddings** is unknown — 3–29 % is on random unit vectors, the easy case to
     disbelieve, and it is **not** a prediction.
   - **The scan at the product's 4-thread knee** (expect ~2×), the **window-filtered scan after slicing per
     video**, **whether an int8 reranker changes the verdict**, the **FTS5 list's RRF weight**, and **a crash
     inside faiss's whole-file dump** — all named in the doc's §7 with the experiment that settles each.
   - The interrupted lane's `_index-hnsw-probe.py` **wrote nothing twice** (0-byte log, empty work dir) and
     `faiss.IndexHNSWFlat.remove_ids` raises; the staged rewrite `_index-ann-probe2.py` is why this lane has
     HNSW numbers at all — **and its `remove_ids` failure is itself the finding**, not a workaround.
