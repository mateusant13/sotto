`## SELF-AUDIT` was appended last turn, but my final answer has to stand alone — preambles and prior blocks can collapse. Here is the complete, self-contained report.

# VERDICT: FAIL

An implementer following this spec exactly produces a search box that returns hits whose displayed text does not contain the query, a schema whose three provenance channels cannot share one key, and a `NOT NULL UNIQUE` anchor column with no producer.

| # | sev | where | defect | fix |
|---|---|---|---|---|
| 1 | **BLOCKER** | §2.4 + §1.4 | `INSERT OR REPLACE INTO transcript/ocr` deletes the conflicting row **without firing `AFTER DELETE`** (`recursive_triggers` OFF by default; §1.1 never sets it). Stale tokens survive; `fts_orphans`=0 so §2.5 cannot see it | `UPDATE … WHERE seg_id=?` when `RETURNING` yielded an existing id, `INSERT` only when it did not. Ban `INSERT OR REPLACE` on `transcript`/`ocr`, **or** set `PRAGMA recursive_triggers=ON` in §1.1 |
| 2 | **BLOCKER** | §1.2 + §5 #1 vs §4.3 | `segment` is declared a **5 s window**; §4.3 writes **one row per ASR chunk** (3.96–13.82 s, median 6.98 s, never 5 s-aligned) — **11 rows vs 24** for the same 120 s | Make `segment` the 5 s window, attribute each chunk to every window it overlaps; **or** restate §5 at the ASR grain (≈86 000 segments). Not both |
| 3 | **BLOCKER** | §1.2 + §4.1 | `clip_uuid` — recovery anchor, `NOT NULL UNIQUE`, `register_clip`'s idempotence key — has **no source**: 0 hits in `src/capture/*.{h,cpp}`, 0 in specs 01/03. Same for `produced_by`, `src_device_id/name`. `frames` is renamed from `frames_in_clip`; `base_abs`/`end_abs`/3 `*_in_window` dropped | Name the four fields as **synthesised capture-side** additions for lane 03; document the `frames_in_clip` rename |
| 4 | MAJOR | §1.2, §1.3, §4.2 ×2, §4.3 | 5 citations point at wrong lines (`runner.py:232`→**233**; `audio.py:53-62`→**53-61**; `transcribe.py:105-107`→**112-114**, exit 2 at :114; `engine.py:50-71`). **Claims all correct** | Correct the five line refs |
| 5 | MAJOR | §5 #27 | `producer` example hard-codes `intra=4`; §7's own cross-check ran at `intra=2`. Copying the literal mislabels every 2-thread run | Mark provenance, or emit from `done.threads` |
| 6 | MINOR | §1.2 | `ON CONFLICT` **merges silently** on a same-ms start; no counter | Add `segments_collided` to §6.3 |
| 7 | MINOR | §7 fact 3 | "gaps of **−10.26 s**" — real gap is **+10.26 s** (`seg3` ends 947.600, `seg4` starts 957.860) | Sign |
| 8 | MINOR | §1.5 rule 1 | The minimum transform neutralises a trailing `*`, silently turning prefix `acess*` into a literal phrase — the same failure class the section exists to prevent | Emit the prefix form outside the quotes |

**Evidence for #1** — `fts5vocab(transcript_fts,'row')`, one row, `a ponte` → `segunda-feira`:

```
A: INSERT OR REPLACE, recursive OFF (default) → index ['a','feira','ponte','segunda']  stale: True
B: same + recursive_triggers=ON              → ['feira','segunda']                       stale: False
C: explicit UPDATE                           → ['feira','segunda']                       stale: False
D: DELETE + INSERT                           → ['feira','segunda']
E: 'integrity-check' → []   (NOT corrupt) ; MATCH 'ponte' → 1 row whose text is 'segunda-feira'
```

**Evidence for #2** — registered clip: durations `[3.96, 5.08, 6.96, 6.98, 8.06, 8.08, 13.76, 13.82]`, none = 5.00, none grid-aligned.

**Checked and SOUND:** §1.3's offset formula ran against all 11 real segments (the *wrong* reading is 900.0 s early, exactly as §7 predicts) · §1 DDL executes **verbatim** on real SQLite **3.43.1**, `ENABLE_FTS5` present · `ON CONFLICT … RETURNING` valid, re-pass = 11 rows, no twins · `content_rowid='rowid'` on composite-PK `ocr` MEASURED correct (note: `pragma table_info` does **not** list `rowid`) · `resample_to_16k` at `sotto_worker.py:1090-1105` exact · `''` legal, `NOT NULL` satisfiable · `producer`/`model_sha256` genuinely absent from the 34 keys · §1.5's escaper survived 32 queries without raising.

## POPULATION AND WINDOW

| population | n | completeness |
|---|---|---|
| `specs/04-index-search.md` | **866 / 908 lines (95.4 %)** | **lines 1-42 NOT READ** |
| `src/asr/` ground truth | ~98 lines of 7 files | partial |
| `src/capture/replay.h` | 179 / 179 | complete |
| `src/capture/common.h` | 0 | never opened |
| real `done` object | 1 file, 4 811 B, 34 keys, 11 segments | complete |
| SQLite queries | 32 MATCH + 11 upserts + 5 scenarios + 1 DDL | complete |
| citations checked | ~9 → **5 wrong** | partial |
| `receipt-07` / `research 07` | **0 lines** | not read |

**WINDOW:** one continuous pass, 2026-10-07, ~20 min wall clock, **no re-measurement, no second pass, no independent re-run**, on a box whose load I did not control. The data is **n = 1 clip, PT/EN radio read-aloud, intra=2** — nothing here generalises to gaming footage, OCR corpora, or 4-thread runs.

## SELF-AUDIT

**Protocols I named as mine and did not follow.** (1) **Spec lines 1-42 — the title block and §0 THE DECISION — were never opened.** I started at line 43 and did not notice until this audit. That is the section most likely to contain a constraint contradicting BLOCKER 2; **BLOCKER 2's confidence drops 0.6 → 0.45.** (2) **`receipt-07` and `research 07`: zero lines.** Check 10 is therefore **PARTIAL**, not done — and I marked it `completed` in the todo list. Wrong. (3) **`lane-spec04-index-cost.log` never opened** — §1.4's `+3.75 MiB` and §3.6's entire latency table are taken on the spec's word. (4) **`level.py` never touched**; `common.h` and4 others grepped-only. (5) **The `ascii`+`remove_diacritics` claim was never tested** — I proved the recommended tokenizer works, not that the warned-against one fails.

**Extra verification beyond the brief, and what it earned.** The brief asked whether `fts_orphans` stays 0. It does — which would have made BLOCKER 1 invisible. I read the FTS5 **index** via `fts5vocab(…,'row')` instead of the content table. My first script crashed with `database disk image is malformed`; rather than report that as a finding I re-ran it as **5 isolated scenarios, one fresh connection each**, which is what separated "corrupt" from "stale".

**Controls that could say NO.** BLOCKER 1 shipped with its own falsifier: A predicted stale; **B** (`recursive_triggers=ON`), **C** (`UPDATE`), **D** (`DEL`+`INSERT`) each predicted fresh. All four agreed — a one-sided run would have looked identical. Scenario E is the deliberate broken control: `'integrity-check'` returned clean `[]`, proving this is silent recall loss, not data loss.

**New checkboxes (mechanical).** `stale_fts_tokens` — build `fts5vocab` for both FTS tables; fail if a term has `doc > 0` while absent from the content table; run after every re-transcription (catches #1; `fts_orphans` provably cannot). `segment_grain_drift` — `SELECT count(*) FROM segment WHERE start_ms % 5000 <> 0` must be 0 under §5 #1; returns 11/11 today. `clip_uuid_source` — grep `clip_uuid` in `src/capture/*` must return ≥1 hit; returns **0**. `spec_citations_resolve` — assert each `file:line` contains the quoted token; fails 5 of ~9. `asr_emit_reproduces` — re-run §7, assert sha256 `f895749477532574` + 11 segs + 814 chars.

**Review by another subagent: none.** I did not route this to a `verifier` child. As root I am **unbound by the SubagentStop lint** that normally forces this section to exist — this is my own compliance, not an enforced gate.

**Confidence, and what moves it.** **High (0.9)** on #1, #3, #6-8 and every "sound" item — executed, reproducible, printed output. **Medium (0.45)** on #2: the measurement is certain, the *remedy* is a design choice, and one implementer-plausible reading ("§4.3 normative, §5's arithmetic is the error") makes it a MAJOR restatement, not a BLOCKER. **Low (0.4)** on #5. *Moves up:* §0 read; receipt-07 showing `ocr` already per-window (narrows #2); lane 03 mid-edit adding `clip_uuid` (downgrades #3 to "spec anticipates code"). *Moves down:* an implementer showing §4.3 is read as chunk-keyed with `segment` window-keyed separately — implausible, not excluded.

**Gate-doubt.** I verified the spec against a transcript I never regenerated, so every "correct" verdict inherits that file's fidelity; it matched `specs/02`'s registered lock on all four cross-checkable numbers, which is reassuring but is not a re-run. And BLOCKER 1's *mechanism* (REPLACE bypasses `AFTER DELETE`) is SQLite semantics independent of my trigger text, but its *severity* depends on the triggers **I** wrote from §1.4's prose — the spec never spells them out. Highest-value untested thing: my own BLOCKER 1 might be an artefact of my trigger reconstruction.

## P0 IN THREE

**NOW:** nothing — the read-only seat forbids edits, so **no fix has landed**. The spec on disk still holds all 3 BLOCKERs and **L4 is coding against it in parallel right now**. That is the live risk this report creates by existing.

**ALREADY:** brief + 866/908 spec lines; `replay.h` complete and the four cited ASR regions; the real `done` object parsed (34+7 keys, absolute seconds, 0.2 s overlaps, no duplicate starts); §1 DDL executed verbatim on 3.43.1; `RETURNING` upsert proven valid and idempotent; composite-PK `rowid` proven; BLOCKER 1 proven via `fts5vocab` across 5 scenarios with 3 fresh-prediction controls; `resample_to_16k` at the exact cited lines; §1.5 escaper attacked with 32 queries; 8 findings with fixes.

**NOT DONE:** spec lines 1-42/§0 · both receipt-07 docs · the cost log · `level.py`/`common.h` · the `ascii` tokenizer claim · an ASR re-run · a second opinion.

## WHAT'S NEXT / WHAT I DID NOT DO

- **Read** spec lines 1-42 (§0) and re-test BLOCKER 2 against it; confirm or drop the 0.45.
- **Read** `receipts/receipt-07-index-search.md` + `docs/research/07-index-search.md` and finish check 10 as a real diff.
- **Open** `_main/lane-spec04-index-cost.log`; verify the FTS5 cost and latency figures independently.
- **Test** `ascii`+`remove_diacritics 2` raising; read `level.py`, `common.h`, the four grepped-only files.
- **Send** this report to a `verifier` subagent to reproduce BLOCKERs 1 and 2 independently.
- **Re-run** §7's ASR command against sha256 `f895749477532574` before treating any of it as final.
- **Wire** `stale_fts_tokens`, `segment_grain_drift`, `clip_uuid_source`, `spec_citations_resolve` into `_main/`.
- **Hand the findings to L4 immediately** — it is coding against a spec with 3 BLOCKERs and has no gate that would stop it; I could not, under a read-only seat.
- **Decide, owner only:** `segment` = the **5 s window** (recommended; preserves §5's arithmetic, one `seg_id` for all three channels) or the **ASR chunk** (forces §5 restated at ≈86 000). L4's T4/T5 cannot be written correctly until this lands — schema, not implementation.
- **Decide, owner only:** whether lane 03 receives `clip_uuid`/`src_device_*` as **required additions**, or §4.1 derives them index-side from `path` + `cut_qpc_ns`. The second weakens §2.5's recovery guarantee and is not mine to pick.

Does your implementation meet the spec? NO - the 866 lines and 32 live queries I actually covered are sound, but spec lines 1-42 (§0), both receipt-07 documents and every cost figure remain unread, so BLOCKER 2 and all of check 10 stay provisional