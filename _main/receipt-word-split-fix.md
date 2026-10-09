# RECEIPT — the word split in the captions ("shi t"), fixed

**Lane:** SottoWordSplit · **Scope:** ONE thing — the caption text must not split words.
**File changed:** `worker/sotto_worker.py` only. The word-split change was verified at
**228 079 B** / sha256 `73A4CA72D8A50D4FD404EFC5DD0D205313958B79BB715B80E6CD7946C927543A`; the file
then gained the audio meter (task 2, `receipt-audio-meter.md`), later defaulted **OFF** by the owner's
decision, and is now **237 024 B** / sha256
`CEFD18689BD54F681E7F5666437DCECA28E9E61B3F3C41666697E4FD3829BAF1`. **Every number below was
re-measured on that final revision**: `_main/word-split-trace.json` records
`worker_sha256: CEFD18689BD54F68…` with the same 26 chunks and the same split, and every oracle was
re-run — **12/12 GREEN**, `--neg-arm` **PASS** (7 RED), caption-lines **12/12**, verdict-gate
**GREEN 14/14**, `py_compile` rc 0.
The registration's line hints were re-read against THIS revision; every number below is from it.
**Not touched:** `app/panel/`, `app/webview/sotto_webview.py`, `history-*.js`,
`caption-formulation.js`, the owner's shell (pid 28428) or worker (pid 29008).
**No audio device was opened.** Every measurement below is the offline file path
(`soundfile` + `StreamAsr.run_chunk`), because the owner's worker holds the endpoint.
**The owner's RUNNING worker predates this fix** (pid 29008, started 08:01:56): the fixed text
reaches him when his worker next restarts, not before.

---

## 1. The defect, reproduced — verbatim

The registered cause was confirmed, not inherited. `_main/word-split-trace.py` re-decodes
`_main/pt-br-sample.wav` with the worker's own `StreamAsr`, spies on `detok()`'s `ids`, and records
per 560 ms chunk BOTH the **raw** text (markers kept, so the boundary fact is visible) and the
**stripped** text (`run_chunk()`'s real return; asserted equal, so the trace cannot drift from the
shipped path). The probe opens no device.

Real input — three consecutive chunks of the owner's own Portuguese clip:

| chunk | window | first real token | raw `detok` | shipped `run_chunk()` |
|---|---|---|---|---|
| 10 | 5.60–6.16 s | `▁próx` | `" próx"` | `"próx"` |
| 11 | 6.16–6.72 s | **`ima`** (no marker) | `"ima"` | `"ima"` |
| 17 | 9.52–10.08 s | `▁preci` | `" preci"` | `"preci"` |
| 18 | 10.08–10.64 s | **`m`** (no marker) | `"m de"` | `"m de"` |
| 15 | 8.40–8.96 s | **`.`** (no marker) | `".  Os"` | `".  Os"` |

**The model is right and the join is wrong.** Chunk 11 carries NO `▁`: the model is saying "this is
the rest of the word I was spelling". `detok()`'s `.strip()` (`:587`) throws that fact away, and
`line()`'s `" ".join(...)` (`:1751` before the fix) put a space back in at every seam. Verbatim
caption the owner sees, BEFORE, from the real `--selftest` run:

```
rádio anunciou que a ponte sobre o vai ser interditada na próx ima segunda-feira .  Os
moradores preci m de um caminho alternativo para chegar ao trabalho
```

Both `final:true` lines (the only text the transcript takes) are affected. There were exactly
**3** mid-word seams in the 26 chunks: indexes 11, 15, 18.

## 2. The fix — a chunk boundary is not a word boundary

Two new pure helpers plus five touched sites; **`_close()` needed no change** (it reads `line()`),
which is a deviation from the "~6 sites" hint in the registration — reported, not hidden.

| # | site (this revision) | change |
|---|---|---|
| 1 | `:1725-1747` | `WORD_MARK` + `chunk_is_continuation(vocab, ids)` — the fact read from the **TOKENS** (skipping `<special>`s), not from the stripped string |
| 2 | `:1749-1773` | `join_fragments(frags)` — **the ONE separator decision**: a `(text, continues)` pair that continues the open word is glued with no separator, every other takes one space |
| 3 | `:534` | `StreamAsr.__init__`: `self.chunk_continues = False` |
| 4 | `:937` | `run_chunk` publishes `self.chunk_continues = chunk_is_continuation(...)` before returning; `(text, n)` is **unchanged**, so no probe breaks |
| 5 | `:1800-1803`, `:1826-1827`, `:1888-1923` | `_words` holds `(text, continues)` pairs; `line()` = `join_fragments(self._words)`; `push(..., continues=False)`; the `max_chars` lookahead measures the **joined** line, so a glued fragment is charged its own length and no separator |
| 6 | `:2595`, `:3547`, `:3772` | the three real emitters (`selftest`, `rerun`'s second pass, `asr_thread`) pass `continues=asr.chunk_continues` |

`detok()` is deliberately **untouched**: its stripped single string is what `done.text` wants, and
the boundary fact now travels beside the text instead of inside it.

**Failure mode of a forgotten `continues=`, stated plainly:** the keyword defaults to `False`
(= new word), so a caller that forgets it keeps the OLD text (a spurious space) and cannot garble
words together. `grep` finds exactly **3** production `push` sites and all 3 pass it.

## 3. Same input, before vs after

Same command, same WAV, same model; BEFORE is the same path with **only `join_fragments`
reverted** (`_main/word-split-before-run.py` monkeypatches that one function to its pre-fix body
and calls the real `sotto_worker.selftest`).

```
BEFORE  rádio anunciou que a ponte sobre o vai ser interditada na próx ima segunda-feira .  Os
AFTER   rádio anunciou que a ponte sobre o vai ser interditada na próxima segunda-feira.  Os

BEFORE  moradores preci m de um caminho alternativo para chegar ao trabalho
AFTER   moradores precim de um caminho alternativo para chegar ao trabalho
```

22 captions before, 22 after, same line count and same line boundaries. **The two full texts are
identical once spaces are removed** (`before.replace(" ","") == after.replace(" ","")`), and **no
character other than the space is present in BEFORE and absent from AFTER**. The only changes are
the 3 mid-word seams, each of which *deletes exactly one injected space*.

**Independent ground truth.** `done.text` is `detok()` of the WHOLE run's token list — it joins
every token (markers included) and only then turns `▁` into a space, so it never had the defect:

```
rádio anunciou que a ponte sobre o vai ser interditada na próxima segunda-feira.  Os moradores precim de um caminho alternativo para chegar ao trabalho
```

It is **byte-identical before and after** (tokens 70 / frames 252 / blank_frac 0.7222 on both
arms) and it already spells `próxima` and `precim`. So the fix does not invent anything: it makes
the captions agree with the model's own text, which the pre-fix captions did **not**.

## 4. The oracle — two colours, one command each

`_main/word-split-oracle.py` drives the REAL `LineFormer`/`join_fragments`/`chunk_is_continuation`
over the real captured token ids and the real on-disk runs. No model load, no device.

```
py -3 _main/word-split-oracle.py              -> 12 PASS / 0 FAIL (12 arms)  VERDICT: PASS   rc 0
py -3 _main/word-split-oracle.py --neg-arm    -> NEG-ARM: 7 FIX arm(s) went RED as required,
                                                 0 stayed green (must be 0), 0 control arm(s)
                                                 broke (must be 0)          VERDICT: PASS   rc 0
```

The `--neg-arm` reverts the ONE line (`join_fragments` → `" ".join(...)`) and requires every FIX
arm to go RED while the 5 control arms stay GREEN. RED under the revert, measured: *the AFTER text
has the whole words*; *the two texts differ by SPACES ONLY*; *exactly the MID-WORD seams changed*;
*the verbatim glue/space unit*; *the max_chars lookahead*; *the pure replay equals the real
`--selftest` captions*; *the captions agree with `done.text`*. Control arms that stay green in both
colours: *the trace reproduces the real BEFORE run*; *the defect is real in BEFORE*; *the first
fragment is never glued*; *a fragment after a CLOSE starts a word*; *`chunk_is_continuation` reads
tokens and skips specials*.

## 5. Regressions checked (the rest of the text must not move)

| instrument | result |
|---|---|
| `_main/caption-lines-oracle.py` (pre-existing, 12 arms incl. the real-WAV replay) | **12 PASS / 0 FAIL**, rc 0 |
| `_main/verdict-gate.py` (battery step) | **GREEN 14/14**, rc 0 |
| `_main/_audit-fresh-processor-probe.py` (battery step) | **VERDICT: GREEN**, rc 0 |
| `_main/segment-rerun-probe.py` (M3 second pass isolation) | **PASS** A/A2/B/C/C3/D, rc 0 |
| `py_compile worker/sotto_worker.py` | rc 0 |

## 6. What I did NOT prove — read this before trusting the word "fixed"

1. **The LIVE path was never exercised.** The owner's worker (pid 29008) holds the audio endpoint
   and opening another tap is forbidden here, so nothing in this receipt is a live Alt+C caption.
   The live path differs from the file arm in exactly two ways that matter: `asr_thread`'s push
   site (`:3772`, updated) and the M3 second pass (`rerun`'s push, `:3547`, updated). Both were
   read and updated; neither was run.
2. **The second pass was not run end-to-end.** File mode deliberately ships the streaming line and
   never calls `rerun()`, so the `final:true` text this receipt compares comes from the streaming
   `LineFormer`, not from the second pass. `rerun` was verified by reading (it now passes
   `continues=asr.chunk_continues` inside its own `run_chunk` loop) and by the unchanged M3
   isolation probe — not by a run.
3. **`_main/segment-rerun-probe.py` still PRINTS a split second-pass line** (`'s moradores preci m
   de um caminho…'`). That is a **probe-side re-implementation**, not the worker: `:166-168` calls
   `second.push(text, start, end)` with no `continues=`, so it keeps the old join. It is another
   lane's file and was not edited; its arms pass, only its sample text is stale. Any other
   instrument that pushes text into a `LineFormer` by hand needs the same keyword to show the fix.
4. **One clip, one language.** `_main/pt-br-sample.wav`, 15 s, pt-BR, `lang=auto(101)`. English
   (`worker/assets/sample1.flac`) and the bundled long samples were not re-run. The rule is
   language-independent (it is the vocabulary's own marker), but that is an argument, not a
   measurement.
5. **The double space in `".  Os"` survives** — it is INSIDE one chunk's text, not a seam, and the
   owner did not report it. The fix neither creates nor removes it.

## 7. Files this lane added (all under `_main/`)

| file | what |
|---|---|
| `_main/word-split-trace.py` | offline decode → per-chunk raw/stripped text + token ids (`word-split-trace.json`) |
| `_main/word-split-before-run.py` | the real file-mode path with `join_fragments` reverted (the BEFORE run) |
| `_main/word-split-evidence.py` | runs the three model arms sequentially, every child `CREATE_NO_WINDOW` |
| `_main/word-split-oracle.py` | **the oracle**, `--neg-arm` = the pre-fix colour |
| `_main/_wordsplit-run-hidden.py` | window-free command runner (house rule) |
| `_main/word-split-trace.json`, `_wordsplit-{before,after}.jsonl`, `_wordsplit-oracle{,-neg}.out` | the evidence |

## 8. The registration is CLOSED — `AGENTS.md`, edited 2026-10-08

The defect was registered as **OPEN, with its falsifier** in `AGENTS.md` (the panel/caption bullet).
That line became false the moment the fix landed, and by the file's OWN rule 1 (*"a false line here is
not a doc defect — it is work done twice"*) it could not be left standing. **I did not edit it on my
own authority**: `AGENTS.md` is not in this lane's ownership map and it is the file every agent loads,
so I flagged it to the coordinating agent, **who authorized the edit and supplied both substitutions
verbatim** (`session-ab8603de-dc05-40ba-966c-f756dd2a5a4c`). Credit for the decision is theirs; the
numbers are mine.

| what | value |
|---|---|
| the marker | `:481-483` — `**CLOSED 2026-10-08 — FIXED AND GATED. The resolution is at the END of this bullet;` / `the text that follows is the HISTORICAL description of the defect, kept because the` / `mechanism is the transferable part:**` (85 / 85 / 98 chars; the third line also carries the paragraph's pre-existing continuation, `words were split at CHUNK boundaries (…)`, unchanged) |
| the resolution block | `:488-498`, inserted after the paragraph's end (`across a chunk boundary (seconds today).`) |
| `AGENTS.md` after the two edits | **54 797 B**, sha256 `F3EBB4EF90DDC35F195A063C7FB8F5DA7DF67EE5E5D2CDCCEDC55DB88022B9F8` |
| `AGENTS.md` after the rewrap | **54 801 B**, sha256 `3D5E06B01CA5CB09C4D1880221A959F7E4C6182257A8E7008D2EB2E2DCFBDD84` (was **53 517 B** at the start) |
| line endings | **LF only, unchanged in kind** — 599 bare LF / 0 CRLF after the two edits, **601 bare LF / 0 CRLF** after the rewrap (+2, exactly the two new line breaks) |
| `grep 'OPEN, with its falsifier' AGENTS.md` | **0 matches** (re-checked after the rewrap) |

**The rewrap, and why it needed its own proof.** The marker went in as ONE 246-char line (the
authorised text, verbatim) and the coordinating agent then authorised breaking it into three. That is
finishing an insertion **the same agent wrote**, not rewriting someone else's edit — a distinction
worth stating, because my first instinct was to refuse the rewrap on the grounds that literal
substitutions must stay literal, and that instinct was right for *preserved* text and wrong for *the
author's own* text. The break was done by `_main/_agents-md-rewrap.py`, which is an **instrument, not a
text editor**: it refuses to write unless the whitespace-normalised concatenation of the new lines is
byte-identical to the old line, so a dropped or added space fails the run instead of shipping.
Measured: `WORDS UNCHANGED: True (43 words)`, 266 chars → 3 lines. The +4 bytes are exactly the two
breaks (each replaces one space with `\n` + the 2-space indent) and the +2 LF is the same fact counted
in line endings — **the arithmetic closes, which is how I know nothing else moved.**

Both anchors matched **byte for byte**, so no ASCII fallback was needed — including the `▁` and the
accented text, which were inside the replaced region and came through unchanged. The historical
paragraph was kept deliberately (the parent's instruction): the mechanism — `detok` turning the
word-start marker into a space and `.strip()`ing it away — is the transferable part, and the
resolution block sits at the end of the same bullet where a reader arriving from a stale note will
find it.

**The division of labour, recorded because it is the part that generalises:** the lane MEASURED and
raised the false line instead of letting it rot; it did NOT edit `AGENTS.md` on its own authority,
because the file is outside its ownership map and is loaded by every agent; and it proposed the fix
with the numbers only it had. The authorisation and the text are the coordinating agent's; the
measurements and the proofs are this lane's. §8 exists so that a later reader can tell those two apart
without asking.
