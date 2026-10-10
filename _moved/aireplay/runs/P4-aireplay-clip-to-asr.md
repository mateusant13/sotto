# P4 — CLIP TO ASR: FROM A FILE ON DISK TO A ROW IN THE INDEX

Status: **SPEC — ready for implementation**
Lane: `feat/clip-to-asr`
Depends on: `specs/05-clip-to-asr.md` (stub), `specs/02-asr.md`, `specs/04-index-search.md`

## 1. THE GAP

`specs/05-clip-to-asr.md` is 824 bytes — a audio format contract table and "(Full text
pending.)" There is no code path that takes a clip file from the capture ring, runs ASR
on it, and writes the transcript into the index. The ASR module (`src/asr/transcribe.py`)
is file-fed: `python -m asr.transcribe --wav <file>`. The index module (`src/index/store.py`)
has `insert_segment()` and `insert_vector()`. But nothing connects them.

The ROADMAP P0 says: *"stdin → cut"* and *"WASAPI loopback → muxed audio"*. The clip-to-ASR
pipeline is the second half: once a clip exists, it must be transcribed and indexed.

## 2. THE PIPELINE

```
clip.mp4 on disk
    │
    ▼
extract audio → 16 kHz mono PCM16 WAV
    │
    ▼
ASR transcribe (int8 ONNX Parakeet, 2-thread budget)
    │
    ▼
transcript + word timestamps
    │
    ▼
index: insert video row, insert segment rows, insert speech vectors
```

### 2.1 Audio extraction

The clip is H.264 video + AAC audio (if WASAPI loopback is working) or H.264 video-only
(current state — 8/8 clips have `AUDIO=NONE`). The pipeline must handle both:

- If audio stream exists: extract with `ffmpeg -i clip.mp4 -vn -ac 1 -ar 16000 -f wav -`
- If no audio stream: skip ASR, index the clip with `channels: []` (no speech)

### 2.2 ASR transcription

The ASR engine is `src/asr/runner.py` with `segment_mode == "silence"` and
`INTRA_OP_NUM_THREADS=4` (the measured knee). The input is a WAV file. The output is:
- `text`: full transcript string
- `segments`: list of `{start_ms, end_ms, text}` with word-level timestamps (UNVERIFIED —
  see `AGENTS.md` ASR section)

### 2.3 Index insertion

The index schema (`src/index/schema.sql`) has:
- `video` table: one row per clip file (identity = `content_key` = SHA-256 of file)
- `segment` table: one row per 5-second window, with `start_ms`, `end_ms`, `text`
- `vector` table: one row per segment per channel (`speech`, `ocr`, `visual`)

The pipeline:
1. Compute `content_key` = SHA-256 of the clip file.
2. UPSERT into `video` (idempotent on `content_key`).
3. For each ASR segment: UPSERT into `segment` with `text`, `start_ms`, `end_ms`.
4. For each segment: compute speech embedding (if embedding runtime available) and
   UPSERT into `vector` with `channel='speech'`.
5. If OCR is available: run OCR on frames, insert `channel='ocr'` vectors.
6. If visual embedding is available: compute visual embedding, insert `channel='visual'`.

## 3. THE AUDIO FORMAT CONTRACT

From `src/capture/audio_contract.h`:

| property | value | provenance |
|---|---|---|
| sample rate | 16 000 Hz | `src/asr/constants.py:91` |
| channels | 1 (mono) | `src/asr/audio.py:57-58` |
| sample width | 2 bytes, PCM16 | `src/asr/audio.py:54-55` |

The capture binary must mux audio at this format. The WASAPI loopback
(`src/capture/wasapi_audio.cpp`, 47 739 B) already captures system audio. The muxer
(`src/capture/mp4_writer.cpp`, 13 732 B) must add an AAC audio stream alongside H.264.

## 4. INTEGRATION WITH THE ENGINE

The Engine process (see `P4-aireplay-engine-process.md`) owns this pipeline. When a clip
is written:

1. Engine receives `{"evt": "clip_written", "path": "..."}`.
2. Engine spawns `ffmpeg` to extract audio.
3. Engine runs ASR on the audio (in-process or subprocess).
4. Engine inserts into the index.
5. Engine emits `{"evt": "index_updated", "seg_id": N, "channels": [...]}`.

The pipeline is **async**: the clip is already safe on disk before ASR starts. A slow ASR
never risks the clip (LAW 1: CAPTURE NEVER WAITS FOR AI).

## 5. ACCEPTANCE — tests that can go RED

### ARM-A: Clip with audio → transcript in index

```
clip.mp4 with AAC audio → pipeline → segment rows with text, vector rows with channel='speech'.
```

### ARM-B: Clip without audio → indexed with no speech channel

```
clip.mp4 video-only → pipeline → video row exists, no segment rows, no speech vectors.
```

### ARM-C: Re-run is idempotent

```
pipeline run twice on same clip → same content_key → no duplicate rows.
```

### ARM-D: ASR failure → clip still indexed

```
ASR model missing → pipeline → video row exists, no segment rows, no crash.
```

### ARM-E: Embedding runtime missing → speech channel only

```
embedding weights missing → pipeline → segment rows exist, vector rows only for speech.
```

## 6. FILES TO CREATE

| file | what |
|---|---|
| `src/pipeline/clip_to_asr.py` | The pipeline: extract audio, run ASR, insert into index |
| `src/pipeline/test_clip_to_asr.py` | ARM-A through ARM-E |

## 7. PROVENANCE

- Audio format: `src/capture/audio_contract.h` (READ)
- ASR contract: `specs/02-asr.md` (READ)
- Index schema: `src/index/schema.sql` (READ)
- Pipeline design: `ROADMAP.md` P0 (READ)
- Word-level timestamps: UNVERIFIED (AGENTS.md ASR section)
- Embedding runtime: UNKNOWN (B4 — no weights on disk)
