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
Word-level, population = 39 words in that transcript (counted in python, not by hand):
- 38/39 plausible English words = 97.4%
- 1/39 malformed: `tosk` (non-word; context wants "to ask") = 2.6%
Zero Portuguese tokens. 39 words over 13.44 s = 2.9 w/s, speech-dense throughout.
`schoolrooms` is not an error (README prints `school`; the audio says *schoolrooms*).

## C. Classification — CONFIG, already fixed, NOT a code defect
The Portuguese-gibberish class is documented and is a wrong **language prompt**:
`worker/lang_prompt.py:22-25` records that decoding this same ENGLISH sample with
prompt 12 (pt-BR) collapsed 94 tokens to 10 — "the whole English clip decoded
against a Portuguese prompt". That is the signature of the reported
`como ém eu desequipo ela`.

Route: `--lang-id` > `SOTTO_LANG_ID` > `config.json:model.lang_id` > the `"os"`
sentinel (`lang_prompt.py:19`). That sentinel resolves the HOST USER locale
(`lang_prompt.py:236-254`; `os_locale_tag()` = `pt-BR` on this box) to id 12.

- **CONFIG (not code):** `lang_id` = `"os"` or `12` anywhere in that chain.
  Owner: whoever edits config/env. The code path is correct.
- **NOT a HARD DEFECT:** `lang_prompt.py:265,270` refuses an undeclared id with
  exit 2 — never clamped, never guessed.
- **NOT MODEL CHOICE:** the same int8 weights decode English correctly today.

Shipped value is `config.json` `model.lang_id = "auto"` (autoSlot 101), set
2026-10-06. This run confirms it: `lang_id 101, source config:auto`. The fix is
ALREADY IN; the P0 as written is stale.

## D. Model dirs (population = 9 dirs in `H:\sotto\worker\models`, window = 1 clip)
Usable by the shipped worker = **3 of 9**: int8 (measured, rc=0), int4 (measured,
rc=0), fp32 (has every required file, not run). The other 6 are unusable, by
content, not by reputation:
- fp16 — rc=2, MEASURED: `FileNotFoundError … -fp16\genai_config.json`; also
  lacks `vocab.txt`. 1247 MB and the only dir that ships `languages.json`, yet
  incomplete. **Fragility:** int8/int4 read their language table from this broken
  dir (`lang_prompt.py:131-148`), so the language fix depends on a partial export.
- fp32/int4/int8 minus the above; parakeet x3 = different architecture or empty
  (`parakeet-redux-reference` = 0 MB); qwen x2 = LLMs, no encoder/vocab.

Measured arms on this clip (population = 2 runs):
| arm | rc | tokens | RTF | RSS MB | malformed words |
|---|---|---|---|---|---|
| int8 (shipped) | 0 | 120 | 0.177 | 2413.6 | 1/39 `tosk` |
| int4 | 0 | 119 | 0.830 | 2153.0 | 2/40 `drfty`, `us` |

int4 is 4.7x slower here (0.830 vs 0.177) for 1 fewer token.

## E. Doc defect (separate from quality)
`README.md:168-173` quotes 94 tokens RTF 0.144 (int8) and 80/0.110 (int4). Neither
reproduces: 120/0.177 and 119/0.830. Its quoted text is 29 words with double-space
gaps; today's decode is 39 words, of which only 25 words overlap. That table
predates the predictor-carry cure and `docs/audit/predictor-carry-cura.md:164-166`
already states the README "measured arm 2". So the README number is stale — a
documentation defect, NOT evidence of an ASR regression. The 120-token run matches
the documented arm 3 (`predictor-carry-cura.md:162`: 119 tokens, 3 empty chunks).