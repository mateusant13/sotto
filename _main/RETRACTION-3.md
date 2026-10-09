# RETRACTION 3 -- there is NO language defect. I was transcribing the room.

Written 2026-10-07 16:22:45 -03:00 at HEAD 1c68cbe. Supersedes TRANSCRIPTION-QUALITY-DEFECT.md.

## 1. THE CAUSE, quoted from the source -- worker/sotto_worker.py:3422-3423
`audio_file = os.environ.get("SOTTO_AUDIO_FILE") or (args.audio if args.selftest else None)`
`if args.selftest or audio_file:`

**`--audio` is ignored unless `--selftest` is also passed.** Without it, the argument
is silently discarded and the worker takes the LIVE DEVICE path.

## 2. WHAT I ACTUALLY MEASURED
Every run I made was `python sotto_worker.py --audio ...\sample1.flac --max-chunks N`
-- **no `--selftest`**. So `audio_file` was None and the worker opened WASAPI and
transcribed whatever was audible on this host. The Portuguese output ("o desequipo ela",
"Pra ter algum in") was real speech from the room, not the sample. **The model was right.
My measurement was wrong.**

## 3. THE SAME SAMPLE WITH --selftest -- POPULATION = 1, WINDOW 16:22:25-16:22:33
`python H:\sotto\worker\sotto_worker.py --selftest --audio H:\sotto\worker\assets\sample1.flac`
**rc = 0**, and the final caption reads:
`"Sunday morning he can come tosk immediately afterward"  final:true`

worker/README.md:169-170 quotes the reference as
`"morning and  he can come to  immediate          94 tokens, RTF 0.144"`.

**The transcription is English and it matches the documented reference.** The rt=3
"silent-device" refusals were the live path finding no active device -- also correct
behaviour, in a different mode.

## 4. WHAT IS ACTUALLY WRONG HERE
Not the model. The INTERFACE: `--audio` silently does nothing without `--selftest`.
There is no warning, no error, no stderr note. A user (me) passes a file path, gets a
plausible-looking caption stream, and has no way to know it came from the microphone.
A flag that is silently ignored is a defect even when everything behind it is correct.

SUGGESTED FIX, small and specific: if `args.audio` is set and `--selftest` is not,
either auto-enable file mode or exit non-zero with a one-line explanation. The same trap
already bit this project once -- `worker/README.md` documents that a deleted
`model.dir` silently substitutes a different model. **Silent substitution is this
project's recurring failure mode, in the model and now in the CLI.**

## 5. STATUS OF MY P0 ITEMS THIS HOUR -- 7 raised, 6 refuted
project empty | weights absent | receipts tainted | worker cannot start | fails at both ends
| transcription wrong  -- all six were my measurement errors. The seventh, the scale gate
passing at 0% compliance, is real and remains open.

## 6. STILL UNKNOWN -- POPULATION = 0
- The full token count on the selftest path (I captured the final line, not WORKER_STATS).
- Whether the panel receives live captions through the shell bridge.
- Whether Alt+C delivers.
