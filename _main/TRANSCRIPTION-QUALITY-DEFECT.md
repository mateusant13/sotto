# TRANSCRIPTION QUALITY IS THE REAL DEFECT -- the sample is ENGLISH and the worker answers in PORTUGUESE

Written 2026-10-07 16:16:58 -03:00 at HEAD 5bae79a.

## 1. THE REFERENCE -- worker/README.md:164-170, quoted
> "Measured, `sample1.flac` (13.44 s), CPU, only the walk differing -- the original
> table, kept for provenance:"
> `drafty school  day For a fortnight He'll have  an appearance At some Sunday`
> `morning and  he can come to  immediate          94 tokens, RTF 0.144`

So `worker/assets/sample1.flac` is an ENGLISH passage (Dickens), and the documented
decode is **94 tokens of English**.

## 2. WHAT MY RUNS PRODUCED -- POPULATION = 2, WINDOW = 2026-10-07 16:04-16:17
Both runs: same file, same `--max-chunks 40`, same `lang_id 101 (auto)`, same device.

| run | rc | captions | finals | tokens | final text |
|---|---|---|---|---|---|
| 1 (16:04) | 0 | 7 | 1 | 12 | "o desequipo ela" |
| 2 (16:17) | 0 | 5 | 2 | -- | **"Pra ter algum in"** |

**Both are Portuguese. Both are one-eighth of the documented token count.**

## 3. THIS CONTRADICTS THE PROJECT'S OWN DOCUMENTATION
worker/README.md states `'auto'` "got 89/94 tokens on the ENGLISH clip AND 18/18 on the
Portuguese one -- it is the only one of the three that is good on BOTH", and that the wrong
prompt collapsed the English sample "from 94 tokens to 10". My runs used `auto` and got
12 tokens, in the wrong language.

Either the auto language slot is no longer behaving as documented, or the decode path in my
runs is not the path the README measured. **I do not know which**, and I am not going to
guess. That is the work order.

## 4. WHY THIS MATTERS MORE THAN ANY P0 I HAVE RAISED BEFORE
Every other finding in this session was about whether code EXISTS or RUNS. This one is
about whether the product is CORRECT -- and a live-caption overlay that answers an English
speaker in Portuguese is worse than no overlay, because it looks like it is working.

## 5. WHAT IS STILL UNKNOWN -- POPULATION = 0
- Whether the language misdetection is a model/config regression or an artefact of the
  device the tap settled on (CABLE Input carried a 0.35 peak on a silent-ish path in run 1).
- Whether the 94-token figure reproduces at all on this host today.
- Whether the worker has a per-run `lang_id` override that, if set, restores it.
