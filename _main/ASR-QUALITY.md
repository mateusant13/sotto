# ASR Quality — bundled English sample

Lane `lane/asrq` · wt `H:\sotto-wt\asrq` · 2026-10-07 · commits 7bbe982, 5dbbbc1, a2c8f7c, 748e710.

## A. Run (population=1 run, window=1 clip)
`python H:\sotto\worker\sotto_worker.py --selftest --audio H:\sotto\worker\assets\sample1.flac`
Both flags. rc read from `$LASTEXITCODE` with output redirected to file, never piped.
**rc=0.** load 3.374 s, infer 2.385 s, audio 13.440 s, RTF 0.177, tokens 120, RSS 2413.6 MB, lang 101 auto.

Transcript: "going along slushy country roads and speaking to damp audiences in drafty schoolrooms day after day for a fortnight he'll have to put in appearance at some place of worship on Sunday morning he can come tosk immediately afterward"

## B. Verdict: NOT Portuguese — the P0 does not reproduce
Population=39 words (python-counted, not by hand): **38/39 plausible English (97.4%)**, 1/39 malformed — `tosk`, where context wants "to ask" (2.6%). Zero Portuguese tokens. 2.9 w/s, speech-dense. `schoolrooms` is correct, not an error.

## C. Classification: CONFIG, already fixed. Not code, not model choice.
This exact failure is documented at `worker/lang_prompt.py:22-25`: prompt 12 (pt-BR) on this ENGLISH sample collapses 94 tokens to 10, "the whole English clip decoded against a Portuguese prompt" — the `como ém eu desequipo ela` signature.

Chain: `--lang-id` > `SOTTO_LANG_ID` > `config.json:model.lang_id` > the `"os"` sentinel (`lang_prompt.py:19`), which maps host locale to pt-BR to id 12 (`lang_prompt.py:236-254`).
- **CONFIG:** `lang_id` is `"os"`/`12` anywhere in that chain. Owner = config/env editor.
- **Not a hard defect:** `lang_prompt.py:265,270` refuses undeclared ids, exit 2, never clamps.
- **Not model choice:** the same int8 weights decode English correctly today.

Shipped value is `lang_id: "auto"` (101), set 2026-10-06; this run logs `source config:auto`. The fix already shipped; the P0 is stale.

## D. Dirs (population=9 in `H:\sotto\worker\models`, window=1 clip)
**3 of 9 usable**: int8 (rc=0), int4 (rc=0), fp32 (complete, unrun). The other 6 unusable by content:
- **fp16, rc=2, MEASURED:** `FileNotFoundError … -fp16\genai_config.json`; also no `vocab.txt`. 1247 MB, yet incomplete — and the only dir shipping `languages.json`, from which int8/int4 read their language table (`lang_prompt.py:131-148`).
- parakeet x3: different architecture; `parakeet-redux-reference` is 0 MB. qwen x2: LLMs, no encoder/vocab.

| arm (2 runs) | rc | tokens | RTF | RSS MB | malformed |
|---|---|---|---|---|---|
| int8 | 0 | 120 | 0.177 | 2413.6 | 1/39 |
| int4 | 0 | 119 | 0.830 | 2153.0 | 2/40 |

int4 is 4.7x slower for 1 fewer token.

## E. Doc defect, not a regression
`README.md:168-173` quotes 94/0.144 and 80/0.110; measured 120/0.177 and 119/0.830. Its text is 29 words, only 25 overlapping today's 39. It predates the predictor-carry cure, and `predictor-carry-cura.md:164-166` already says the README "measured arm 2". The 120-token run matches documented arm 3 (`:162`, 119 tokens, 3 empty chunks).