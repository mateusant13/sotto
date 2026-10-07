# receipt-08-import-library — what was RUN/MEASURED, and what is UNKNOWN

1. **MEASURED (this lane, `_main/_import08-media.py` → `_main/_import-bench/media08.json`+`.log`)** — one synthetic clip
   only (`_import-bench/synth-180s-1080p30.mp4`, 295 501 289 B, 180 s, 1080p30, 13.13 Mbps, 2 s GOP), never an owner file.
   Per-stage costs, seconds and **read amplification from `GetProcessIoCounters` on the retained handle** (read after exit,
   no poll race): `ffprobe` header **0.0425 s**; full decode **3.049 s = 59× RT, ×1.000 bytes**; audio→16 kHz WAV
   **0.143 s = 1256× RT, ×0.601**; one 30 s chunk **0.068 s = 2635× RT, ×0.102**; thumbnail with `-ss` **before** `-i`
   **0.111–0.145 s / 3.3–3.4 MB (×0.012)**, JPEG 5755–6139 B; the same thumbnail with `-ss` **after** `-i`
   **4.491 s / 267.7 MB (×0.950)** — 40× the time, 80× the bytes; 1 fps gallery **180 frames in 2.64 s = 1 151 301 B
   → 3.66 GB per 1000×10 min videos**; SHA-256 **882.6 MB/s** (warm), BLAKE2b 356 MB/s, head+tail 1 MiB **7.7 ms/file**.
2. **MEASURED (this lane, `_main/_import-hdd2.py` → `hdd2.json`)** — the HDD is **`I:` Seagate ST4000DM004**, the same
   volume that holds the owner's `I:\importantes\Videos\` (`02-ocr.md` §0). Read-only, non-personal HF blob, `NOBUF`:
   sequential 8 MiB chunks @0/1/2 GiB = **54.9 / 19.7 / 33.6 MB/s**, 1 MiB chunks 22.4, **32 MiB chunks @512 MiB = 106.0**;
   random 4 KiB **0.041 MB/s (median 21.9 ms, p95 516 ms)** and 0.13 MB/s. First pass (`_import-bench.py`, `run.log`):
   40.3 MB/s seq, 0.04 MB/s random, median 90.8 ms, and **8 threads = 0.14 MB/s with the median latency doubled to
   184.6 ms** — the measured case against parallel readers on this drive.
3. **MEASURED (identity, same probe)** — `GetFileInformationByHandleEx(FileIdInfo)` returns volume serial
   `721160841945409291` + a 128-bit file id in **22 µs with zero bytes read** (its first 8 bytes carry the 64-bit MFT
   index — checked against `GetFileInformationByHandle`'s `nFileIndexHigh/Low`). That is the cheap rename-proof key;
   the content hash is the durable one and must be a by-product of a pass that already reads the file.
4. **READ, cited, not re-measured by this lane** — Redux ternary **7–14× real time / 3.90 GB peak RSS / 3.7–4.3 s load**
   (`H:\sotto\_main\receipt-redux-ternary.md` §2.3/§3.2); live Nemotron **1191.9 MB** and the never-both rule
   (`04-asr.md` §2); OCR **2.4–41 s per 1080p frame** and the owner's own 15.33 s `DVR.mp4` yielding **0 frames in
   >10 minutes** (`02-ocr.md` §0/§1); index arithmetic 120 k × 256 dims = 123 MB fp32 / 61 MB fp16 (brief line 1356).
5. **DESIGN (derived from 1–4, not measured)** — the two-key identity, the single sequential reader + ≤2–3 prefetch,
   the SQLite job table with lease-expiry recovery and payload+`done` in one transaction, chunk-granular pause,
   the D0→D4 order, posters as a derived NVMe cache, the refuse-list, and the **1.25 × average_Mbps crossover**
   (16–85 Mbps for this drive) that decides whether the deep pass is ASR-bound or HDD-bound. One in-process ASR run,
   not one process per file: 1000 × 3.7–4.3 s = **1–1.2 h of pure loading** otherwise.
6. **UNKNOWN, by name** — (a) whether `-vn` demux of a real fragmented MP4 on this HDD degenerates into random I/O
   (here it skipped 40 % of the bytes, free on NVMe; *experiment: copy the synthetic clip to `I:`, 10 min, no owner
   file*); (b) the real library's duration/bitrate (a 7× swing in the ASR estimate); (c) VAD's share of that audio;
   (d) the visual embedding model ("EmbeddingGemma 2" is a brief claim); (e) whether an int8 ONNX runner replaces the
   3.90 GB dense one.
7. **House rules** — nothing was indexed, nothing downloaded, and **no owner video was opened**; the only video read is
   the lane's own synthetic clip. All children were spawned with `CREATE_NO_WINDOW` from `pythonw.exe`, and no audio
   device was opened. **No window census was run by this lane**, so absence of a visible window is argued by mechanism
   (pythonw + `CREATE_NO_WINDOW`), not by a measurement — this lane did not sample at its own cadence, and says so.
8. **Contention, disclosed and named** — the owner's own live app was transcribing throughout
   (`H:\sotto\_main\webview-run.log`, mtime 08:09:34, captions `count 48→50`), and ~13–19 other python processes were
   running. So every throughput number here is a **contended range**. The one thing the pass did show is that the live
   captions kept flowing while this lane decoded video and read the HDD — co-existence, not a controlled arm, and no
   substitute for the yield policy in the doc.
9. **Files written (this lane only)** — `docs/research/08-import-library.md`, this receipt, `_main/_import08-media.py`,
   `_main/_import-bench/{media08.json,media08.log,hdd2.json,thumb08.jpg}`. `_import-bench.py`,
   `_import-hdd2.py`, `_import-io-probe.py` and `_index-bruteforce-probe.py` (the earlier interrupted pass of this lane)
   were **read, not modified**; `_import-io-probe.py` was not run. `H:\sotto` was read only (its logs and receipts).
10. **Fixture retained on purpose** — `_main/_import-bench/synth-180s-1080p30.mp4` (**282 MB**, created by the earlier
   interrupted pass of this lane, `run.log`) was kept so the media numbers can be re-run without touching a real video.
   It is **the lane's own synthetic file, not the owner's footage**, and deleting it would delete the ability to
   reproduce §1. The two empty `*> *.out.log` files the launcher produced were deleted.
