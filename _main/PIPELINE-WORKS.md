# THE PIPELINE WORKS -- real capture to real captions, and my 'model absent' P0 was WRONG

Measured 2026-10-07 16:05:07 -03:00. Product root H:\sotto. NOT a worktree.

## 1. THE RETRACTION OF MY OWN RETRACTION
Last turn I reported "worker/models DOES NOT EXIST" and made it a P0. **That was my error.**
I tested `H:\sotto-wt\ArbV8\worker\models` -- a WORKTREE path -- and declared absence from a
sample. The product root is `H:\sotto`. This is the fourth time in one hour I have declared
an absence or a population from a truncated or mis-targeted query. The rule exists; I did not
apply it to myself.

## 2. THE WEIGHTS ARE THERE -- POPULATION = 9 model directories under H:\sotto\worker\models
| model | files | bytes |
|---|---|---|
| nemotron-3.5-asr-streaming-0.6b-int8 | 14 | 1,070,636,361 |
| nemotron-3.5-asr-streaming-0.6b-fp16 | 9 | 1,307,568,147 |
| nemotron-3.5-asr-streaming-0.6b-fp32 | 15 | 2,599,194,664 |
| nemotron-3.5-asr-streaming-0.6b-int4 | 13 | 793,342,660 |
| parakeet-redux-onnx-int4 | 12 | 436,062,801 |
| parakeet-redux-ternary | 6 | 179,015,759 |
| parakeet-redux-reference | 3 | 112,158 |
| qwen3-0.6b-arm-int4 | 10 | 495,095,942 |
| qwen3.5-0.8b-ortgenai-cpu | 14 | 754,682,839 |

## 3. THE REAL RUN -- POPULATION = 1 run, WINDOW = 2026-10-07 16:04:23-16:04:59
`python H:\sotto\worker\sotto_worker.py --audio H:\sotto\worker\assets\sample1.flac --max-chunks 40`
**rc = 0.** 256 JSON lines: 12 status, 230 meter, 7 caption.

- model nemotron-3.5-asr-streaming-0.6b-int8, loaded in **2.91 s**, RSS 1679.3 MB
- providers CUDAExecutionProvider + CPUExecutionProvider
- lang_id 101 (auto) resolved from the model's OWN languages.json
- device **WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)**, 48 kHz, block 4800
- meter **10.0 Hz** on stdout, peak 0.500000

CAPTIONS EMITTED, from the decode itself:
`
"como"                              final:false
"como é"                            final:false
"como ém"                           final:false
"como ém eu"                        final:false
"como ém eu desequipo"             final:false
"como ém eu desequipo ela"          final:false
"o desequipo ela"                   final:true
`

WORKER_STATS, quoted: `chunks=40 captions=7 tokens=12 audio_s=22.40 infer_wall_s=1.82
rtf=0.08 peak_rss_mb=2461.2 queue_drops=0 vad_gated_chunks=0 music_gated_chunks=15`

The worker's own verdict line: `"verdict":"captions-emitted" ... "proved_alive": true,
"proved_device": "WASAPI loopback: CABLE Input", "proved_reason": "caption"`

It also carries a **tap_ledger** naming both endpoints it probed, with blocks and captions per
device, and marking which one settled.

## 4. WHAT THIS MEANS
Real audio in, real Portuguese text out, **RTF 0.08 -- eight times faster than real time**,
with per-device provenance. The transcription path is not a stub, not a fake, and not blocked
on a download. The transcription QUALITY is poor ("como ém eu desequipo ela" for the bundled
sample) and that is a separate open question.

## 5. STILL UNKNOWN -- POPULATION = 0 for each
- Whether the panel RECEIVES these captions live, from the shell's own bridge.
- Whether Alt+C DELIVERS (registration is not delivery).
- What the bundled sample actually says, so transcription quality can be scored rather than
  admired.
