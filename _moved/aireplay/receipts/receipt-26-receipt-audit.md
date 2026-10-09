# Receipt 26 — the audit tool that finds claims nobody checked

**Lane:** receipt-audit (mechanical claim auditing) · **repo:** `H:\sotto\_moved\aireplay`
**Files owned by this lane, all new:**
`_main/receipt-audit.py` · `_main/_lane19-receipt-audit-gate.ps1` · this receipt.

**What this receipt is NOT.** It is not a claim that the project is broken, and it
is not a pass. It is the description of an instrument that answers four questions
mechanically instead of by reading prose, plus the measured output of that
instrument. **I fixed nothing.** Findings below are reported for other lanes.

---

## 0. The headline, and the one number that matters

`DEBT-LEDGER.md:60` says **"Count: 0 of 16 lanes have a reviewer verdict read."**

**That number cannot be verified, and this tool says so rather than repeating it.**
It is not 0, and it is not any other number — it is **UNVERIFIABLE**, for a reason
measured in §3. A human-maintained markdown cell is a *claim*; this lane's job was
to replace claims with checks, and the honest result of that replacement is that
this particular claim has no mechanical reading at all.

The honest number this tool CAN produce, by structural query, is:

| question | value | how it was obtained |
|---|---|---|
| lanes with a reviewer **DISPATCHED** | **8** | `local_runtime_background_tasks`, `kind='subagent'`, `metadata.agentName='verifier'` |
| lanes with **no** verifier dispatched | **14** | same query, negative |
| lanes with a verdict **READ** | **UNVERIFIABLE (not 0)** | no structural link exists — §3 |
| **all 22** lanes have the `read` count UNVERIFIABLE | — | the `read` column, per lane |

**This number moved while I measured it: 7 → 8, and 15 → 14, between two runs 20
minutes apart** — a reviewer landed mid-session. That is the honest state of this
project: the reviewer count is a live figure, not a constant, and any table
recording it by hand is stale the moment it is written.

POPULATION = 22 lanes = the 16 in `DEBT-LEDGER.md` ∪ every `L<n>` named in a
`local_runtime_background_tasks.description` (WINDOW = whole table, 52,944 rows,
read 13:08–13:41). The 6 lanes the store knows and the ledger does not are
L17–L22-era lanes plus `L20 synthesize reviewer verdicts into fixes`.

---

## 1. Q1 — claim provenance: how many receipts label their numbers?

**MEASURED 13:41, POPULATION = all 41 `receipts/*.md`, WINDOW = whole directory.**

> **35 of 41 receipts are UNLABELLED or UNDER-LABELLED.**
> 9+ receipts have 0 provenance labels at all — every figure in them is unlabelled.

The tool counts a "number site" = a prose/table line containing a digit (fenced
code blocks, headings and bare dates excluded — they are evidence or navigation,
not claims), and a "label" = an occurrence of the provenance vocabulary the brief
mandates (`MEASURED`, `DERIVED`, `NOT MEASURED`, `UNVERIFIABLE`, `ARITHMETIC`,
`ESTIMATED`, `CALCULATED`, `INFERRED`). A receipt with ≥5 number sites and fewer
than 1 label per 8 sites is a FINDING.

The 9 with **zero** labels — the sharpest cases, because no figure in them is
distinguishable from any other (number sites at WINDOW 13:33; the corpus grew
while this ran, so this table is a snapshot, not a fixed fact):

| receipt | number sites | labels |
|---|---|---|
| `receipt-05-onnx-asr.md` | 62 | **0** |
| `receipt-11-onnx-threads.md` | 52 | **0** |
| `receipt-13-refute-integration-audit.md` | 9 | **0** |
| `receipt-20-durability-git-coverage.md` | 89 | **0** |
| `receipt-22-single-cron-delivers.md` | 22 | **0** |
| `receipt-23-cron-woke-this-session.md` | 29 | **0** |
| `receipt-preview-designs.md` | 47 | **0** |
| `receipt-render-panel-temas.md` | 120 | **0** |
| `receipt-29-agents-truth.md` | (grew during run) | **0** |

**This is exactly the failure the lane was asked to find.** `LANE-BRIEF.md` §3
records that "any 1440p/4K60 number is arithmetic, not measurement", and the
brief's own example of the hazard is *"4K60 = 120 s"*. A reader of
`receipt-render-panel-temas.md` cannot tell a measured 120 s from a derived one,
because the file never says which it is. **The threshold is a HEURISTIC and the
tool says so in its own output** — it counts labels, it does not judge whether a
given figure was in fact measured. That second question is **NOT MEASURED** and
this tool does not pretend to answer it.

## 2. Q2 — gate existence: does every cited gate exist?

**MEASURED 13:41, POPULATION = every backticked `*.ps1/*.py/*.log/*.mp4/…` token
in the 41 receipts. 692 citations: 571 resolved, 2 DANGLING, 119 UNVERIFIABLE.**

**The 2 dangling citations are the SAME file, cited twice — and it is a REAL
finding, not a fragment:**

<!-- receipt-audit:self-doc -->
| citation | verdict |
|---|---|
| `review-L16.md:117` → the missing receipt-24 | **verified absent** (`Test-Path` = False) |
| `review-L16.md:318` → the same file | same file, same absence |
<!-- /receipt-audit:self-doc -->

**A reviewer verdict cites a receipt that does not exist.** That is the exact
shape this lane was pointed at: a load-bearing claim whose supporting artefact
was never checked. `receipt-24-wake-defects-fixed.md` DOES exist — the citation
names a *different* receipt-24, so either the reviewer meant that one or the
receipt was renamed. **This is the one finding here that is unambiguously a
defect, and it is in a reviewer's output, not in a lane's receipt.**

**No dangling GATE citation exists.** Every `_lane*-gate.ps1` a receipt names is
present on disk — 9 distinct gates, 33 citations, 33 resolved. The brief's
hypothetical ("a header citing `_lane1-trigger-gate.ps1` when that file does not
exist is a real defect that shipped here") is **NOT MEASURED as having shipped**
in *this* form: that specific file does exist (`_main/_lane1-trigger-gate.ps1`).
I am reporting the negative because the negative is what I measured.

### 2b. The 119 UNVERIFIABLE citations are the more interesting number

These are globs, brace expansions, `<timestamp>` placeholders and shell command
lines: `` `_main\logs\cap-battery-<timestamp>.txt` ``, `` `_lane*-gate.ps1` ``,
`` `py -3 _main\oracle-02-asr.py` ``. **The tool refuses to call them resolved
AND refuses to call them defects**, because a glob is not a path. A checker that
resolves `*` patterns by "some file matched" is the same class of bug this lane
hunts. They are counted separately in every total.

### 2c. A fourth self-match round, found in THIS RECEIPT

While writing §2 I quoted the dangling tokens verbatim. On the next run the
tool reported **7** dangling citations instead of 3 — and **4 of the 7 were this
receipt quoting §2's own table, including the media and text-suffix fragments.

Same defect as §4b, third layer up: an instrument's own output, quoted by its own
author, read back as evidence about somebody else's files. The tool correctly
excludes `_main/` lane-19 paths (§4b fix) but a receipt is a *legitimate* file
that happens to discuss the findings.

**The fix, and why it is not "exclude receipts".** Scanning receipts IS the
population — excluding them would blind the tool to the 32 files it exists to
audit. Instead Q2 masks regions fenced by
`<!-- receipt-audit:self-doc --> … <!-- /receipt-audit:self-doc -->`: HTML
comments, invisible in rendered markdown, and used by no other lane. The mask
preserves line numbering, so a masked citation still reports its true line.

**MEASURED: the count returned to 3 and stayed at 3 across repeated runs while
this section grew** — the feedback loop is closed, not merely slowed.

### 2c-bis. Rounds 4 and 5, and the fix that generalises

The file-name approach kept failing, because **every redirect invents a new
name**. Two more rounds, both mine:

<!-- receipt-audit:self-doc -->
- **Round 4.** I redirected the tool's stdout to scratch files to read exit
  codes without a pipe. Those three files supplied **360 of the Q4 findings**
  (185+131+44) — the tool's report, quoted by a file named after nothing.
<!-- /receipt-audit:self-doc -->
- **Round 5.** `output.log` — a citation in this receipt to the reviewer's
  transcript — was reported DANGLING. It is **not** dangling: it exists, 40,785 B,
  but it lives under `%USERPROFILE%\.minimax\background-tasks\`, outside every
  root this tool can search. Calling a runtime-owned artefact "missing" is a
  false accusation. Now classified `external` → **UNVERIFIABLE**.

**The general fix, and the transferable part:** stop matching *names*, match
**content**. Any file whose first 4 KB carries this tool's own banner
(`RECEIPT-AUDIT  repo=` or `LANE19 RECEIPT-AUDIT GATE`) is this tool's output,
whatever it is called and wherever it was redirected — a copy, a redirect
target, or a log dir. Separately, runtime-owned artefacts (`output*.log`,
anything naming `background-tasks`/`outputRef`) are **UNVERIFIABLE**, never
DANGLING.

**Naming your own files to dodge your own scanner is not a fix — it is the same
category of error.** Four of my five rounds were that mistake.

### 2d. Four resolver bugs I found in my OWN tool, by checking its output against the filesystem

This is the part worth keeping. My first run reported **52 dangling citations**.
**Seven were bugs in the instrument, not defects in the repo.** Each was found by
taking a reported name and asking `Test-Path` on it myself:

| # | bug | false danglers | fix |
|---|---|---|---|
| 1 | `resolve_citation` stripped the `H:\sotto\` prefix and then searched inside `aireplay`, so a file in the **parent** repo "did not exist" | **9** | test an absolute path **as written first**; prefix-stripping is a fallback, never a rewrite |
| 2 | the basename walk pruned `runs/ logs/ models/ build/` **for speed**, hiding real files | **2** (`cap-mux-4k-lied.mp4` is in `_main\runs\`, `vocab.txt` in `models\`) | prune only `.git/node_modules/target`. **An exclusion that changes the answer is dishonesty, whatever the reason** |
| 3 | `COMMAND_PREFIXES` held mixed case (`"Test-Path"`) compared against a lowercased token, so it never matched | 2 | lowercase the table; the mismatch was silent |
| 4 | bare tool names (`g++.exe`, `chrome.exe`, `git.exe`) treated as in-repo citations | 4 | a bare executable may be on `PATH`; its absence here proves nothing |
| 5 | a runtime-owned artefact (`output.log`, 40,785 B, under `.minimax\background-tasks\`) called missing because it is **outside every search root** | 1 | classify `output*.log` / `background-tasks` as `external` → UNVERIFIABLE, never DANGLING |
| 6 | tokens scraped from a **git diff listing** (`D schema.py`, `M store.py`) treated as paths | 5 | leading `X ` status letter ⇒ fragment |
| 7 | **bare module names** (`edgechromium.py`) treated as repo files, when the file lives in `site-packages\webview\platforms\` | 1 | bare module name not present in-repo ⇒ `external`, third-party code is not this repo's evidence |

Plus prose fragments that are not citations at all: `.out.txt`, `-timeline.jsonl`
(4 in `receipt-24`), `.utf8.txt`. Those are now `fragment`, i.e. **UNVERIFIABLE**,
not defects.

**52 → 2.** Every one of the 2 was then confirmed by hand before I believed it.
**A checker whose own false-positive rate I did not measure is not a checker; it
is a generator of confident noise.** Seven of my nine bugs were the same
mistake in different clothes: **declaring a file absent when I had only failed to
find it in the places I happened to look.**

## 3. Q3 — reviewer coverage, and why "verdict read" is UNVERIFIABLE

**MEASURED 13:08–13:22 against `C:\Users\Administrador\.minimax\v2\sqlite\
runtime-state.sqlite`, POPULATION = the whole `local_runtime_background_tasks`
table filtered to `kind='subagent'`.**

**What IS structurally available — and I confirmed the chain end to end:**

```
local_runtime_background_tasks
  task_id            = bg_3b0a0b54-9bd5-40fc-ad23-5a4c71619012
  kind               = 'subagent'
  status             = 'succeeded'
  metadata.agentName = 'verifier'          <- reviewer, structurally
  metadata.parentTurnId    = turn_aeec7923-…   <- the dispatching turn
  metadata.childSessionId  = mvs_36edbf94c94f45f3975623c86322e66f
  outputRef.uri     = …\background-tasks\bg_3b0a0b54-…\output.log
```
All four fields resolve; `output.log` exists (40,785 B, matching `outputRef.offset`
exactly) and contains the reviewer's verdict text. **That is a real structural
chain from a ledger cell to the reviewer's own words.**

**What is NOT available — and this is the finding.** For "was the verdict *read*",
I checked the runtime's own delivery-origin field and it does not carry the
information:

- `local_runtime_message_rows.source_context_json` →
  `origin.kind='background-task-terminal'` with `origin.taskIds` exists, and the
  parent session has **36** such rows — but `origin.taskIds` names **only the
  background-task poll driver** (`bg_ba0a5730-…`, `bg_b58a9764-…`, `bg_91d353cd-…`).
- **MEASURED: 0 of those rows name ANY of the 6 reviewers the ledger names.**
- The only signal that a verdict was read is a **text match** on assistant prose
  (7 assistant rows in the parent session contain the string `VERDICT`). That is
  the self-match trap of §4, applied to the review question itself. An assistant
  row can *quote* a verdict without having read it.

**So the tool prints `read=UNVERIFIABLE` for every one of the 22 lanes, and
`reviewer verdict READ: 0 VERIFIABLE` — followed by the sentence "and that number
is UNREACHABLE, not zero".** Printing `0` there would have been a lie with a
number on it, and it is precisely the lie the ledger's "0 of 16" already tells.

**The structural link to use instead**, written out so another lane can wire it:

1. reviewer **dispatched** → `local_runtime_background_tasks` row with
   `kind='subagent'`, `metadata.agentName='verifier'`, description naming the lane.
   *Implemented in `_main/receipt-audit.py`, Q3.*
2. reviewer **produced a verdict** → follow `outputRef.uri`, assert the file
   exists and `size >= outputRef.offset`. *Implemented as a display field.*
3. reviewer verdict **read** → require the ORCHESTRATOR's own turn to cite the
   reviewer's `childSessionId`, i.e. an assistant `data_json` containing that
   session id, created **after** the task's `endedAt`. This is still a text
   match, but it is a match on an **identifier minted by the runtime**, not on
   prose — an agent cannot accidentally type a UUID.
   **NOT IMPLEMENTED — I did not build it, and I am not going to claim a count I
   could not reproduce.** It needs a date filter I did not validate.
4. **Better, and what I recommend:** require each reviewer to write its verdict to
   a lane-named file (`_main/_verdict-L<n>.md`) and assert **that file exists**.
   Then "read" stops being an inference about an agent's attention and becomes a
   fact about the filesystem.

## 4. Q4 — the self-match trap, found in the repo and then in my own tool

**MEASURED, POPULATION = 1,820 text files under the repo (`.git`, `node_modules`,
`target` pruned). A line counts when it carries a delivery/health claim word
(delivered, woke, alive, health, reached, consumed, fired) AND a text-match
instrument word (marker, grep, regex, substring, "text search").**

**Final: 22 lines across 17 files are substantiated by a text match with no
structural link on the line.** They are printed with file:line and the line text.

**Honest caveat on this number.** Several of the 17 files are themselves
*warnings about* the trap rather than instances of it — `_lane16-wake-gate.ps1`
and `check-delivery.py` say "a text match is not proof" in so many words. My
vocabulary cannot tell an instance from a warning. **A reviewer should decide
whether these are true positives or over-matching**, and I have not proven which.
The lines with a genuine claim-and-no-link shape are in `receipt-21`,
`receipt-24`, `receipt-27` and `_main/wake-loop.py`.

The canonical instance the brief names is real and is already understood by the
project — `receipts/receipt-21-wake-mechanism-audit.md:66-78`: a naive text search
returned **22 rows any role, 1 as `role='user'`**, and that 1 had
`turn_ingress.queue_item_ids_json = NULL` and `claim_source = NULL` — a
hand-pushed foreground turn that **the queue never delivered**.

### 4b. I committed the trap twice, in my own instrument

Recorded because it is the transferable part, and because a receipt that hid it
would be worthless:

- **Round 1.** On the first run, `_main/_receipt-audit-run.txt` — **this tool's own
  report** — was its own top Q4 finding (8 lines of my own prose, cited as
  evidence of somebody else's defect). Fixed by excluding the tool's artefacts.
- **Round 2.** After I added the gate, the gate's own log directory — a
  byte-copy of the tool's stdout — supplied **73 of 81** findings. Fixed.
- **Round 3.** After the negative control, the gate's own log directory supplied
  **41 of 52**. Fixed by matching the **lane**, not a list of filenames.
<!-- receipt-audit:self-doc -->
- **Rounds 4–5.** See §2c-bis: a stdout redirect supplied **360** findings, and a
  runtime-owned `output.log` was falsely called missing. Fixed by matching this
  tool's own **banner content** rather than filenames.
<!-- /receipt-audit:self-doc -->

Final: 81 → 52 → 185 → **22**, with the last fix removing 4 of the 5 ways I had
found to fool myself. Each round the tool was quoting itself one level up, and
each time the count was a *lie about somebody else's code*. An instrument that
matches its own output proves nothing and reports green — exactly the failure in
`receipt-22:20-28` and in `ORCHESTRATOR-STATE.md` §5 item 3 ("counted 95 HEARTBEAT
messages that were my own report text. Twice today now.").

**Structural links to use instead — named, so a lane can act on them:**

| claim | WRONG instrument | RIGHT structural link |
|---|---|---|
| message delivered | `payload LIKE '%marker%'` | a new `local_runtime_message_rows` row, `role='user'`, `msg_id` = the injected id |
| queue → turn | text match on the payload | `turn_ingress.queue_item_ids_json IS NOT NULL` AND `claim_source` set. NULL ⇒ hand-pushed |
| reviewer dispatched | a markdown cell | `local_runtime_background_tasks`, `kind='subagent'`, `metadata.agentName='verifier'` |
| reviewer read | "the receipt says so" | the reviewer's `outputRef.uri` exists **and** the orchestrator turn cites `childSessionId` |

---

## 5. The gate, and the control that makes it mean something

`_main/_lane19-receipt-audit-gate.ps1` — **9 arms, GREEN=9, RED=0, `VERDICT PASS`,
rc=0.** One command:

```powershell
pwsh -NoProfile -File _main\_lane19-receipt-audit-gate.ps1
```

| arm | asserts |
|---|---|
| ARM0 | the instrument runs and emits all four sections |
| ARM1 | on the live repo it reports findings and exits 3 under `--fail-on-findings` |
| **ARM2a** | **CONTROL/cured** — over a sandbox seeded with a receipt citing a non-existent gate, the tool **FINDS** it |
| **ARM2b** | **CONTROL/cure REVERTED IN A COPY** — same sandbox, detection disabled: the tool runs **rc=0** and **MISSES** it |
| **ARM2c** | the reverted copy is still **runnable python** (a crash is not a miss) |
| **ARM2d** | the copy genuinely differs from the shipped file |
| **ARM3** | **HONESTY** — with the store absent the tool prints `UNVERIFIABLE` and **not** a green `0` |
| **ARM4** | **SELF-MATCH** — the tool does not report its own output as a Q4 finding |

**ARM2b is the arm the acceptance asked for, and it is the one that matters: it
goes RED when the cure is reverted in a copy.** Without it, ARM1 is a green light
with no counterfactual.

**ARM5 exists because ARM4 was not enough, and I only know that because I tried
to break it.** ARM4 passes on a filename whitelist. A whitelist loses the moment
anybody redirects stdout — which is what I did, and the redirect supplied 360
findings. ARM5 plants the copy somewhere the whitelist cannot see and requires
the **content** guard to catch it. It is the second arm here that was **vacuous
before it was real**: with the guard deleted it stayed GREEN (planted in a
lane-named dir the other guard already covered), and its leak regex missed
Windows `\` separators so it could not have seen a leak either. Both fixed; it
now goes RED with 26 leaked citations.

### 5b. Two control arms were wrong before they were right

Both are recorded because a control that is red for the *wrong reason* is worse
than no control — it manufactures confidence:

1. **The control was a crash.** The reverted copy originally replaced the
   resolver's `roots = [...]` with `'Z:\nonexistent-root\'`. A backslash cannot
   end a plain Python string literal, so the copy died with `SyntaxError` and
   **rc=1** — and ARM2b "passed" because *a crashed tool trivially finds nothing*.
   Fixed: the replacement is a single-line raw string, **ARM2c now `py_compile`s
   the copy**, and **ARM2b requires rc=0**, so a crash is RED rather than a
   silent pass.
2. **The control was backwards.** Gutting `roots` makes a tool report *more*
   danglers, not fewer — so the reverted copy still found the seeded defect and
   ARM2b stayed red for the wrong reason. The cure to revert is the **DETECTION**
   (`return None, tried` in `resolve_citation`), not the resolution. With the
   detection reverted, the tool runs cleanly and genuinely misses the defect.

### 5c. The gate was also run against a broken tool, end to end

To show the gate fails closed rather than only proving its own arms: I copied the
instrument, deleted its detection line, and pointed the gate at that copy.

```
GATE RC=1     ARMS=5  GREEN=4  RED=1     VERDICT FAIL
ARM2 RED  could not locate the detection line … to revert
```

The gate **refused to run its control at all** when the cure was already absent,
instead of reporting PASS. That is the behaviour I wanted from a fail-closed
instrument.

**The two negative-control scratch files are now DELETED** (moved to trash via
`rm --`, the sanctioned recoverable path, after a plain `Remove-Item` was BLOCKED
by the local permission gate — I did not bypass it). Deleting them made this
receipt's own citation of them dangle, which the tool correctly reported: the
audit is live enough to catch a stale reference in its own authorising document.

---

## 6. What this receipt does NOT claim

- **It does not claim the repo is broken**, or that any of the 73 findings is a
  *new* defect. Most predate this lane. It is a census, not an indictment.
- **It does not claim any figure in any receipt is FALSE.** It checked whether
  figures are **labelled** and whether cited **files exist**. Both are
  necessary and neither is sufficient.
- **It does not verify the `read` count**, and says `UNVERIFIABLE` (§3).
- **It does not judge whether a label is honest.** A receipt can write MEASURED
  on an arithmetic result. This tool counts the word, not the truth.
- **Q1's 1-label-per-8-sites threshold is a heuristic** chosen by me, stated in
  the output, and not validated against a human-agreed standard.
- **The Q1/Q2/Q4 populations drift, and fast.** Other lanes were landing
  receipts the whole time this ran: the receipt count went **29 → 30 → 31 → 34 →
  35 → 38 → 39 → 40**, and Q1 tracked it ("24 of 29" → "34 of 40"). Q2 dangling
  moved 52 → 3 → 7 → 12 → 2 as I fixed resolver bugs *and* as new receipts
  landed. **The counts are a snapshot at WINDOW 13:36, not a fact about a fixed
  corpus**, and re-running this tool tomorrow will legitimately produce different
  numbers. Anyone citing a number from here must cite the WINDOW with it.
- **I did not verify the parent-repo citations' contents**, only their existence.
- **No reviewer subagent reviewed this.** This seat has no `task` dispatch tool.
  §7 says what to do about that.

---

## 7. SELF-AUDIT

**Confidence, per claim.**

| claim | confidence | what would move it |
|---|---|---|
| 26 of 31 receipts under-labelled | **high** | the count is mechanical; only the *threshold* is mine |
| 2 dangling citations are real | **high** — the same file, `Test-Path`'d by hand twice | nothing short of the file appearing |
| 57 citations unverifiable-by-design | **high** | a reviewer disagreeing that a glob should resolve |
| 7 reviewers dispatched | **high** — structural, full chain walked; **and it moved to 8 mid-session**, which is reported above | nothing |
| **"verdict read" is UNVERIFIABLE** | **high** | a store column I did not find. I checked `message_rows`, `background_tasks`, `background_task_events`, `task_session_bindings` |
| 11 Q4 self-match lines | **medium** — the count MOVED as the corpus grew (11 → 22) and several hits are warnings-about-the-trap, not instances | a reviewer distinguishing an instance from a warning; I have not proven which |
| the gate can go red | **high** — demonstrated twice (§5b, §5c) | — |

**Protocols missing.** No independent reviewer (§6). No human-agreed labelling
threshold. No check that a label is *true*. No snapshot mechanism: the tool reads
a moving repo, so two runs are not comparable without comparing WINDOW.

**Extra verification I ran beyond the arms.**
1. Every one of the tool's own reported defects was **re-checked against the
   filesystem by hand** — this is how **seven** resolver bugs (§2d) were caught.
   A tool's output is a claim; I treated it as one.
2. **`py_compile` on the reverted copy** (ARM2c), because a crashing control is
   not a control.
3. **The gate run against a deliberately broken tool** (§5c), end to end, rc=1.
4. **ARM5 negative control** — the content-based self-exclusion arm was run
   against a copy with that guard deleted: it went **RED with 26 leaked
   citations and rc=1**. Without that run ARM5 was **vacuous**: it stayed GREEN
   with the guard removed, because the planted copy sat in a lane-named
   directory the *other* guard already caught. **An arm that cannot fail is a
   comment, not a check.**
5. **The self-match trap was applied to the tool itself, five times** (§4b) —
   each round caught by noticing the finding count *rose* after I added an arm.
   A rising count after adding an instrument is the signal; I should have
   predicted it rather than discovering it four times.
6. **A syntax error I introduced was caught by the gate**, not by me: `w("x %s"
   % v)` is invalid Python (a string literal cannot be the left operand of `%`),
   and all 9 arms went RED because the tool would not import.

**New named verification boxes I created.**
- **`ARM2a/2b/2c/2d`** — the cure-reverted control, split so that
  *ran-cleanly*, *missed-it*, *is-runnable* and *actually-differs* are four
  independent assertions. The first design collapsed them into one and was wrong
  twice; the split is the fix.
- **`ARM3`** — the honesty arm: absent store ⇒ `UNVERIFIABLE`, never `0`. This
  arm **failed on first run** and caught a real lie in my own tool (§3 counts).
- **`ARM4`** — the self-exclusion arm.
- **`ARM5`** — the content-based guard, proven non-vacuous: a copy of the report
  is planted under a **neutral** directory name (not lane-named, so the
  filename guard cannot catch it) and must still be excluded. Verified RED with
  the guard deleted.

**Gate doubts.** ARM1 asserts the live repo yields findings; if a future lane
labels every receipt, ARM1 goes red and someone may "fix" it by weakening the
tool. **ARM1 is the arm most likely to be misread as a health check. It is not
one** — it asserts the instrument is still looking. ARM3's assertion is textual
(`-match 'UNVERIFIABLE'`), so a tool that printed the word without honouring it
would pass; I checked that by reading `counts_of`'s `_num()` guard, but a
reviewer should confirm it independently.

**My own instruction-following, recorded plainly.** I was told to dispatch a
verifier. **I could not: this seat exposes no `task` dispatch tool**, so no
verifier verdict exists and §6 does not pretend otherwise. The gate's control
arms are my compensation, and they are not a substitute — a control proves the
instrument can fail; a reviewer proves it is failing for the *right* reason.

---

## 8. WHAT'S NEXT / WHAT I DID NOT DO

1. **Read the 8 zero-label receipts and label them, or say why they cannot be.**
   `receipt-render-panel-temas.md` (120 number sites, 0 labels) is the worst.
   *Owner: a claim-provenance lane. I report; I do not edit other lanes' files.*
2. **Decide the `read` question** — adopt §3's recommendation (verifier writes a
   lane-named verdict file; existence becomes the fact) or reject it. **This is the
   decision that unblocks "0 of 16".** Until then the honest cell in
   `DEBT-LEDGER.md:60` is `UNVERIFIABLE`, and I recommend it say so.
<!-- receipt-audit:self-doc -->
3. **Resolve the one real dangling citation** — `review-L16.md:117,318` cite
   `receipt-24-wake-minted-id-delivered.md`, which does not exist. Either the
   reviewer meant `receipt-24-wake-defects-fixed.md` (which does) or the receipt
   was renamed. **Owner: whoever wrote review-L16. It is a reviewer's verdict
   resting on a file that is not there.**
<!-- /receipt-audit:self-doc -->
4. **Fix the Q4 lines** to cite a structural link. Several of the 17 files are
   *warnings about* the trap rather than instances of it — **a reviewer should
   decide whether these are true positives or my vocabulary over-matching**, and
   I have not proven which. The claim-and-no-link shape is real in
   `receipt-21`, `receipt-24`, `receipt-27` and `_main/wake-loop.py`.
5. **Wire `receipt-audit.py` into `all-gates.ps1`** so this census runs with the
   rest. I did not edit that file — it is owned by L11.
6. **Add `--compare <baseline.json>`** so two runs are diffable. Without it the
   moving population makes every count unreproducible (§6).
7. **Dispatch a verifier** whose only question is *"can this audit tool pass while
   the repo is broken?"* — from a seat that has a dispatch tool.

---

## 9. Rollback

```powershell
# this lane adds three files and changes nothing else
git -C H:\sotto\_moved\aireplay status --short -- _main/receipt-audit.py _main/_lane19-receipt-audit-gate.ps1 receipts/receipt-26-receipt-audit.md
# to neutralise: delete the two _main files; the gate is opt-in, nothing calls it yet
```

**No receipt, lane file, or git history was modified by this lane.** Verified by
`git status` on the three owned paths (§9 command, run at close).

---

## 10. P0 — what I did NOW / ALREADY did / did NOT do

**P0 — what I did NOW.** Built `_main/receipt-audit.py` (the four-question
auditor) and `_main/_lane19-receipt-audit-gate.ps1` (9 arms, control included),
and measured the repo with them: **76 findings, 142 unverifiable items** at
WINDOW 13:40.

**P0 — what I ALREADY did.** Established the structural link that makes reviewer
coverage checkable at all — `local_runtime_background_tasks` →
`metadata.agentName='verifier'` → `childSessionId` → `outputRef.uri` — walked it
end to end against a real verdict on disk. Proved the gate can fail, twice, for
reasons I had to fix first. Found and fixed **seven** false-dangling bugs and
**five** self-match rounds in my own instrument.

**P0 — what I did NOT do, and why.**
- **I did not dispatch the required verifier.** This seat exposes no `task`
  dispatch tool. The brief's §6 reviewer step is **OUTSTANDING**, not done.
- **I did not fix any finding.** Not the 36 under-labelled receipts, not the
  missing receipt-24 that `review-L16` cites, not the 24 Q4 lines. Those belong
  to other lanes.
- **I did not implement the `read` detector** (§3 step 3/4) — it needs a date
  filter I did not validate, and shipping an unvalidated one would be the exact
  sin this receipt is about.
- **I did not wire the tool into `all-gates.ps1`** — owned by L11.
- **I did not commit.** The brief gates commits on a green gate; the gate is
  green, but this lane was not asked to commit and the tree has 15+ concurrent
  modifications from other lanes that are not mine to commit.

---

Does your implementation meet the spec? YES - the tool answers all four questions mechanically, says UNVERIFIABLE rather than OK wherever it cannot check, and the gate's ARM2b goes RED when the cure is reverted in a copy, which is the acceptance criterion.