# 08 — Import Library: ~1000 videos / ~300 GB into the SAME index, without copying

**Question (one):** how do we import ~1000 videos / ~300 GB from a plain HDD into the **same index** as the new clips — **no copies of the videos, no days of waiting?**
`MEASURED` = a command on this box produced it (instrument named) · `READ` = a source says it · `UNKNOWN` = nobody has shown it.
Host: Windows 11 Pro · i5-13600K · RTX 5080 · source volume **`I:` = Seagate ST4000DM004**, 4 TB, the volume that also holds the owner's `I:\importantes\Videos\` (`02-ocr.md` §0). **This lane opened no owner video.** Every number below is from its own synthetic clip `_main\_import-bench\synth-180s-1080p30.mp4` (295 501 289 B, 180 s, 1080p30, x264 crf26, **13.13 Mbps, 2 s GOP**) and from a non-personal HF blob on the HDD. Instruments: `_main/_import08-media.py` (`media08.json/.log`), `_main/_import-hdd2.py` (`hdd2.json`), `_main/_import-bench.py` (`run.log`, first pass). ~13–19 other python processes were running during both passes — these are a recorded **contended** range, not a quiet-box benchmark.

## 0. Answer in one line

**Never copy, never re-encode, never sweep frames: `scan + ffprobe` (≈1–3 min) makes the whole library browsable, and the deep channels (transcript → visual) are a *resumable, preemptible* background queue whose wall clock is the ASR — 12–24 h under the brief's own 10-min-average assumption — not the HDD, whose full pass costs 48 min–4.3 h.**

## 1. The scan — what "library" means, and the identity key

- **The index is the database; the folder is only an input.** A scan never owns the tree and never writes into it (brief line 1428: *"não precisa mover nem converter"*). Enumeration + one `stat` + one `ffprobe` per file creates the row **before** any content work: that is what makes the library navigable in minutes.
- **What to keep, to resume after a stop or a crash** — one durable job table in SQLite (WAL, on the NVMe, never on `I:`): `asset(file_key, content_key, path, size, mtime_ns, duration, codec, w, h, fps, bitrate, last_seen_scan, missing)` + `job(asset_id, stage, chunk, params_hash, state, attempts, lease_expires_at, started_at, finished_at, error)`, stages `probe → thumb → audio → asr → frame → embed → ocr`. **Recovery is one UPDATE**: every row left `running` whose lease expired goes back to `pending`; nothing else is re-derived.
- **Idempotence is a schema rule, not a hope**: the output is keyed by `(content_key, stage, params_hash, chunk)` and **the payload and the `done` row commit in the same transaction**, so a power-off can never leave "transcript written, job still pending" (double work) nor "job done, no transcript" (a silent hole). `missing=1` on a vanished file is a *state*, never a delete — a hit can then say "this video is gone" instead of silently losing the memory.
- **The unit of loss is the chunk, not the file**: 30 s of audio takes **0.068 s** to extract (MEASURED), so a hard power-off costs one chunk, never a 2-hour re-read.

**Identity — the trade-off, each cost MEASURED here:**

| key | survives rename/move | recognises a copy | cost | breaks when |
|---|---|---|---|---|
| full path | ✗ | ✗ | 0 | any rename → the 300 GB is re-processed |
| `size + mtime_ns` | ✗ | ✗ | 1 stat | `touch`, restore-from-backup, copy that resets mtime |
| **NTFS file id + volume serial** | **✓ (same volume)** | ✗ (a copy is a new object) | **1 open, 22 µs, 0 bytes read** (`GetFileInformationByHandleEx FileIdInfo`: vol `721160841945409291` + 128-bit id, whose first 8 bytes carry the 64-bit MFT index on NTFS — checked against `file_index_64`) | copy, format, exFAT/FAT, another machine |
| whole-file **SHA-256** | ✓ | **✓** | **CPU 882.6 MB/s → 300 GB = 5.8 min** (warm cache); **the DRIVE is the cost: 48 min–4.3 h** | nothing real |
| head+tail 1 MiB + size | ✓ | ~ (misses same-size/same-header pairs) | 2 seeks, 2 MiB → 7.7 ms/file warm | two encoder-identical clips of equal size |

**Decision: two keys, not one.** `file_key = (volume_serial, ntfs_file_id)` is the free "have I seen this *object*" memo (a rename then costs one open and **zero** reprocessing); `content_key = SHA-256` is the durable identity the index hangs off, computed **as a by-product of the first pass that already reads the bytes** (the audio demux) — hashing is 5.8 min of CPU against 1–4 h of the drive, so a separate hash pass is the most expensive way to learn nothing. Truncated/unreadable files: `probe` fails → `state=failed` + error string + `quality=truncated`, and the readable head is **still indexed**, because a search that hides a broken video is a lost memory.

## 2. The queue — hours of work that must not touch the game or the recording

- **One process, one sequential reader, a small compute pool.** MEASURED on this HDD: 4 KiB random = **0.041–0.13 MB/s, median 17–91 ms, p95 up to 516 ms**; 8 threads gave **0.14 MB/s with the median latency 184.6 ms vs 90.8 ms single-thread** (first pass) — a single mechanical head, so concurrency buys queue reordering, not throughput. Forbid it structurally: **one** reader thread, files in path order, prefetch ≤2–3, reads ≥8 MiB with `FILE_FLAG_SEQUENTIAL_SCAN`.
- **Priority:** `interactive` (the poster/metadata of what the user is looking at) > `foreground` (metadata + thumbnail sweep, minutes) > `deep` (ASR, frames). The **live-capture path is not in this queue at all** — separate process, own budget (law 1). Deep work yields the instant the panel opens or a game starts, because Redux is **3.90 GB RSS** and live Nemotron **1192 MB** must never run at once (`04-asr.md` §2).
- **Pause/resume** is at chunk granularity (≤30 s of work) with a commit per chunk, and the deep pass runs under `SetPriorityClass(BELOW_NORMAL)` + `PROCESS_MODE_BACKGROUND_BEGIN`, so Windows throttles its I/O itself.
- **If the owner switches the PC off mid-way:** committed chunks are kept, the in-flight chunk is redone, and the queue is rebuilt from the DB at next start. Nothing is recomputed and **the library never needs the HDD to be present** — a result whose drive is missing says "offline".
- **Co-existence was observed, not controlled:** the owner's own live app kept delivering captions (`H:\sotto\_main\webview-run.log`, `count 48→50`) while this lane decoded video and pulled the HDD — evidence that the import can live beside the live engine, but it is **not** a substitute for the yield policy above, and the throughput numbers in §6 were collected under that contention.
- **One correction with a measured basis:** do **not** spawn the ASR per file — `redux_batch.py` pays **3.7–4.3 s of model load per invocation** = **1–1.2 h of pure loading across 1000 files** on top of the ASR. Load `ParakeetTdtRuntime` once and transcribe the whole queue in-process.

## 3. The order — metadata first, then the expensive channels, each useful alone

| step | work | cost per file (MEASURED) | useful the moment it finishes |
|---|---|---|---|
| **D0 probe** | `ffprobe` header only | **0.0425 s**, reads only the header/index | **the whole library**: browse, sort by date/duration/resolution, filename search, real durations + the ETA |
| **D1 poster** | 1 thumbnail per video, input-side seek | **0.111–0.145 s and 3.3–3.4 MB** (×0.012 of the file) | a visual gallery |
| **D2 transcript** | audio → 16 kHz (0.143 s, ×0.601 bytes) → Redux | 7–14× real time, **3.90 GB RSS**, load once | *"where did I talk about X"* — the query that actually pays |
| **D3 visual** | decode + image embedding, 1 frame/5 s | decode is **59× real time** whatever the sample rate; embedding **UNKNOWN** (EmbeddingGemma 2 unverified) | *"the Ferrari moment"*, semantic visual search |
| **D4 OCR** | — | **2.4–41 s per 1080p frame** (`02-ocr.md` §1) — a full sweep is refused | only per-video, opt-in, on already-recorded frames |

**Rule that sets the order: value ÷ cost, cheapest-to-resume first — not pipeline elegance.** D0 is minutes and makes the product usable; D2 is the first *content* channel and the only one that must read the whole library; D3 is the most expensive and the least defined. **OCR is not a library sweep at any price**: 120 k frames × ~8 s ≈ **267 h**.

## 4. Thumbnails — yes, one poster each, and never inside the video

- **Do it**: a gallery and a search result without a picture are not usable. One **poster per video**, not 1 fps.
- **Size (MEASURED)**: a 320 px q4 JPEG is **5 755–6 139 B**. 1000 posters ≈ **6 MB**; a 10-frame filmstrip ≈ 61 MB. A **1 fps gallery over the brief's 1000×10 min = 3.66 GB** of JPEGs and no matching value — refuse it.
- **Where**: `%LOCALAPPDATA%\Sotto\thumbs\<content_key[0:2]>\<content_key>_<t>_w320_q4.jpg` — a **derived cache on the NVMe**. Three nevers: **never inside the container** (that is a remux = rewriting 300 GB and invalidating the very `size`/`mtime`/hash you identified the file by), never in the owner's video folder (the library stays read-only), never with the DB/index/temp on the HDD either.
- **Cost to generate (MEASURED)**: 0.12 s + 3.4 MB per file, because the seek lands on the previous keyframe and decoding starts there — so the cost scales with **GOP length, not file size**: `bytes ≈ GOP_s × Mbps/8` (2 s × 13.13 Mbps ÷ 8 = 3.3 MB, exactly what was measured). All 1000 posters ≈ **3–6 min and ~3.4 GB of reads**.

## 5. What NOT to do — each line carries the measurement that forbids it

1. **Do not extract frames to disk as a stage.** 1 fps = **3.66 GB** of JPEGs for 1000×10 min videos, plus the decode. Pipe frames to the embedder in memory (raw rgb24 224² = 150 kB/frame; 120 k frames = 18 GB of pipe traffic, disk-free).
2. **Do not re-encode, remux or "optimise".** It is the only operation that costs a full read **and** a full write, loses quality, and changes the identity and mtime you just recorded.
3. **Do not open 10 files in parallel on the HDD.** MEASURED: 8 threads = **0.14 MB/s at double the latency** (184.6 ms vs 90.8 ms). The head is one.
4. **Do not seek on the output side.** One thumbnail with `-ss` **after** `-i`: **4.491 s / 267.7 MB (×0.950 of the file)**, against **0.111 s / 3.3 MB (×0.012)** with `-ss` before `-i` — **40× the time, 80× the bytes, the same JPEG**. Never let one frame cost the whole video.
5. **Do not hash the library as its own pass**: 5.8 min of CPU, but the drive pays 48 min–4.3 h. Hash the bytes D2 is already reading.
6. **Do not sweep OCR** (2.4–41 s/frame; 120 k frames ≈ 267 h) and **do not run the deep pass while the panel is open or a game runs** (3.9 GB + 1.2 GB + a 0.6–2.9 GB ring on one box).
7. **Do not use the path as identity, and do not "organise" the library** — the first re-indexes 300 GB after a rename, the second destroys the owner's own structure.
8. **Do not put the DB, thumbnails or index on `I:`** — the drive must do nothing but big sequential reads.

## 6. Numbers — where the time goes, with the hypotheses in the open

| MEASURED | value |
|---|---|
| HDD sequential (NOBUF), 8 MiB chunks @0/1/2 GiB | **54.9 / 19.7 / 33.6 MB/s**; 1 MiB chunks 22.4; **32 MiB chunks @512 MiB = 106.0 MB/s** |
| HDD sequential, first pass (contended), 512 MiB | **40.3 MB/s** |
| HDD random 4 KiB | pass 2: **0.041 MB/s** (median 21.9 ms, **p95 516 ms**) / 0.13 MB/s (17.1 ms); pass 1: 0.04 MB/s (90.8 ms), ×8 threads 0.14 MB/s (184.6 ms) |
| full software decode, 1080p30 | **3.049 s per 180 s = 59× real time**, reads ×1.000 |
| audio → 16 kHz WAV / one 30 s chunk | **1256× / 2635× real time**; bytes ×0.601 / ×0.102 |
| ASR (Redux ternary, cited from the sibling tree) | **7–14× real time**, 3.90 GB RSS, 3.7–4.3 s load |

**Hypotheses, all visible:** H1 307 200 MiB of video · H2a **10 min average** (the brief's own line 1347) → **166.7 h of audio at 4.1 Mbps** · H2b 1080p60 gameplay at **30 Mbps → 22.8 h** (307 200 MiB × 8 ÷ 30 Mbps) · H3 Redux at **10×** (midpoint of 7–14×) · H4 HDD **40 MB/s** sustained for a full sequential pass, 20–90 ms per seek · H5 the deep pass runs only with the panel closed, on 8 threads.

**The bottleneck is a crossover, not a constant.** ASR at 10× must be fed 10 s of video per second, i.e. it needs `1.25 × average_Mbps` MB/s from the drive; the measured drive gives 20–106 MB/s, so **break-even ≈ 16–85 Mbps**:

- **case A (4.1 Mbps)**: the ASR needs **5.1 MB/s** — 8–20× inside the drive's range ⇒ **ASR-bound**, the HDD idles.
- **case B (30 Mbps)**: the ASR needs **37.5 MB/s** — at/above the mid-range ⇒ **HDD-bound**: the drive sets the pace, and the seek behaviour (never seek per frame) decides everything.

| stage | case A (166.7 h) | case B (22.8 h) | bound by |
|---|---|---|---|
| D0 probe (1000 files) | **1–3 min** | 1–3 min | CPU + one seek/file |
| D1 posters (1000) | **3–6 min**, ~3.4 GB read | 3–6 min | decode |
| D2 transcript | **12–24 h** (166.7 ÷ 7…14), + 2.1 h of I/O overlapped | **1.6–3.3 h** | ASR (A) / HDD (B) |
| D3 visual (1 frame/5 s) | ≥ **2.8 h** of decode + the model | ≥ **0.4 h** + the model | decode + UNKNOWN model |
| D4 OCR, if swept | ≈ **267 h → refused** | ≈ 267 h → refused | nothing sane |

**A full pass over 300 GB on this drive costs 48 min (106 MB/s) to 4.3 h (20 MB/s)** — so *"without spending days"* is honest in this shape: **minutes** for a browsable library, **3–6 min** more for a gallery, **~2–3.5 h** (high-bitrate case) or **12–24 h** (the brief's 10-min-average case) for transcripts, and only then the visual pass. The lever that turns the pessimistic case into an acceptable one is **scope, not speed**: D0+D1 for all 1000, and D2 either overnight (one 3.9 GB run) or **on demand, per video** (~1 min of ASR per 10-min video) as the user opens or searches — the library is indexed and browsable either way.

## 7. UNKNOWN — the experiment that decides each

1. **Does audio-only demux of a real, fragmented MP4 on this HDD degenerate into random I/O?** Here `-vn` pulled only ×0.601 of the bytes, i.e. **the demuxer skips video data** — free on NVMe (1256×), potentially 20–90 ms per skip on the HDD. `02-ocr.md` §0 already recorded `ffmpeg -vf fps=1` on the owner's own 15.33 s `DVR.mp4` producing **0 frames in >10 minutes** (box memory-starved — caveat kept). *Experiment: copy the synthetic clip to `I:` and time `-vn` demux with `GetProcessIoCounters`. 10 min; no owner file touched.*
2. **The real library's total duration and bitrate** — H2a vs H2b is a 7× swing in the ASR estimate. D0 answers it in ~2 minutes, and the product should print the ETA it derived rather than promise one.
3. **VAD's share of that audio** — if 60 % is silence or music the ASR halves; nobody measured it on this library.
4. **The visual embedding model** (existence, size, RSS, throughput) — *"EmbeddingGemma 2"* is a brief claim to verify per this repo's rule before D3 can be sized.
5. **Whether the int8 ONNX reference runner beats the 3.90 GB dense one** — `04-asr.md`'s open measurement; it changes D2's RSS budget, not its wall clock.
