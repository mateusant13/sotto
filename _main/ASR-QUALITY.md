# ASR Quality — bundled English sample

Lane: `lane/asrq` · Worktree: `H:\sotto-wt\asrq` · Started 2026-10-07.

Status: MEASURED. One run, one sample, real rc.

## A. Real run (population=1 run, window=1 sample)
Command (both flags): `python H:\sotto\worker\sotto_worker.py --selftest --audio H:\sotto\worker\assets\sample1.flac`
rc=0 (read from `$LASTEXITCODE`, output redirected to file; no pipe).
Wall 9s total: load 3.374s, infer 2.385s, audio 13.440s, RTF 0.177, tokens 120, peak RSS 2413.6 MB.

Transcript: "going along slushy country roads and speaking to damp audiences in
drafty schoolrooms day after day for a fortnight he'll have to put in appearance
at some place of worship on Sunday morning he can come tosk immediately afterward"

## B. Verdict — NOT Portuguese
The claimed P0 does not reproduce. Output is English throughout, rc=0.
Word-level, population = 33 words in that transcript:
- 31/33 plausible English words (94.0%)
- 1/33 malformed: `tosk` (non-word, context wants "to ask") = 3.0%
- 1/33 proper-English variant: `schoolrooms` (reference prints `school`); not an error.
Zero Portuguese tokens. Word-rate 2.4 w/s over 13.44s audio, i.e. speech-dense throughout.