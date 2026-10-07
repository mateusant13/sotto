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

## C. Classification — CONFIG, already fixed, NOT a code defect
The Portuguese-gibberish class is documented and is a wrong **language prompt**:
`worker/lang_prompt.py:22-25` records that decoding this same ENGLISH sample with
prompt 12 (pt-BR) collapsed 94 tokens to 10 — "the whole English clip decoded
against a Portuguese prompt". That is the exact signature of the reported
`como ém eu desequipo ela`.

Route: `--lang-id` > `SOTTO_LANG_ID` > `config.json:model.lang_id` > the `"os"`
sentinel (`lang_prompt.py:19`). The `"os"` sentinel resolves the HOST USER locale
(`lang_prompt.py:236-254`, `os_locale_tag()` = `pt-BR` on this box) to id 12.

- **CONFIG (not code):** `lang_id` = `"os"` or `12` in the resolution chain above.
  Owner: whoever edits config/env. Code path is correct.
- **NOT a HARD DEFECT:** `lang_prompt.py:265,270` refuses an undeclared id with
  exit 2 — never clamped, never guessed.
- **NOT MODEL CHOICE:** the same int8 weights decode English correctly today.

Current shipped value is `config.json` `model.lang_id = "auto"` (autoSlot 101),
set 2026-10-06. This run confirms it: `lang_id 101, source config:auto`.
So the fix is ALREADY IN and the P0 is stale.

## D. Usable model dirs (population = 9 dirs in `H:\sotto\worker\models`)