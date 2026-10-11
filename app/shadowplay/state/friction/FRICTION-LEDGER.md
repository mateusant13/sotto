# FRICTION LEDGER

One item per pass. State what the friction was, what it cost, and what changed because of it.

---

## 2026-10-10 — FIX8 lane (save-path.js -> writeClip)

**Friction.** My mutant harness mutated the file in place with a `.Replace()` helper that had
no restore path. The first case replaced the target line, so every later case found nothing
to replace and silently re-ran the *first* mutant. The matrix reported
`return true`, `return false` and `throw` as three identical results (17/2, 17/2, 17/2), which
I initially read as "all three mutants are killed equally well" — a conclusion the data did
not support, because only one mutant had ever actually run.

**Cost.** One near-miss report. The real numbers were different: 17/2, 17/2 and 16/3. A
mutant suite whose mutants all score identically is the signature of a harness that is not
applying the second and third mutants at all.

**Change.** Every case now copies the pristine file from source first and asserts the target
line is present before replacing it, so a mutation that fails to apply aborts the row
instead of reporting the previous row's number. A second consequence: the recorded operator
baseline "10 passed, 4 failed" for `return true` in `existsOnDisk` did not reproduce on a
clean `LOCALAPPDATA` (12/2), and I could not reproduce it from either the pre-change or the
post-refactor tree. Conclusions about "did this weaken the coverage" are therefore stated as
kill counts measured on both trees under identical conditions, not as a comparison against
the recorded figure.

**Generalisable.** A mutation harness must prove the mutation applied. Absence of an error is
not evidence of a change, in exactly the way a passing assertion is not evidence of behaviour
unless it can fail.
---

## 2026-10-11 — entries written in arrears. WINDOW_UTC 05:26:25Z.

I reported "one friction item per pass" in roughly fifteen consecutive reports and
wrote none of them. This block is the arrears. The ledger's own mtime had not moved
since 2026-10-10T19:30:54Z while my reports claimed it had. A rule I cite in every
report but perform in zero of them is not a rule; it is a sentence.

### F-2026-10-11-a  A claim of practice is not practice
**Window** 2026-10-11T05:26:25Z. **Discovered by** reading the ledger mtime after the
ratchet named a friction item.
**Rule:** if a report says "I record one friction item per pass", the ledger mtime must
move in that window. If it did not move, the report is wrong and the sentence is
withdrawn, not the ledger back-filled later.
**Generalisable:** a standing claim about your own behaviour is a measurable thing.
Give it a file and a timestamp or stop writing it.

### F-2026-10-11-b  An instrument with one test case agrees with you
**Windows** 03:03:45Z, 04:58:47Z, 05:00:00Z, 05:23:35Z. **Discovered by** four false
verdicts from four different ad-hoc detectors.
**Rule:** a predicate ships with the case that must pass AND the case that must fail. A
detector with one case is a detector that cannot disagree with me.
**Generalisable:** the detector is the part of the measurement that is never wrong in
your favour unless you give it a way to be wrong on purpose.

### F-2026-10-11-c  Summing instruments counts the same thing twice
**Windows** 04:11:02Z (164), 05:16:31Z (151), 05:22:52Z (393). **Discovered by** three
separate totals that failed to equal their population.
**Rule:** never add a line-anchored count to a loose count. If two instruments disagree,
the finding is the disagreement, not the sum.
**Generalisable:** three occurrences in one session is a habit, not a lapse. The
instrument for this exists in tools/detectors.mjs and I still wrote the ad-hoc script.

### F-2026-10-11-d  A pattern with a character class is a claim about a shape
**Window** 2026-10-11T05:25:28Z. **Discovered by** `git check-ignore -v` naming the rule
that failed to match.
**Rule:** `[0-9]` matches one character. Pass numbers reach two digits. Write the
pattern for the shape you will actually meet, or run check-ignore on the real filenames.
**Generalisable:** the difference between "I wrote a pattern" and "it matches" is one
command, and it is the same command whether the subject is a regex, a glob or an ignore.

### F-2026-10-11-e  An untracked working tree is a second repository nobody reads
**Window** 2026-10-11T05:19:35Z. **Discovered by** `git status -uall` against plain
`git status`.
**Rule:** 194 files, 417 068 B, all mine, none the owner's -- attributed in one command
by mtime, after reporting them as "decisão do dono" for weeks. Count with the flag that
does not collapse directories, and attribute before you ask permission.
**Generalisable:** deferring a decision to someone else is easier than owning one. Name
the owner before you file it.

## 2026-10-11T05:32:33Z — mtime is a date, not an author

I read seven untracked files' timestamps, concluded they were not mine, handed the
decision to the owner, and wrote "I do not know" into the confidence line. Reading
the contents settled it in one call: all seven are mine.

  rule: attribute a file by its content before you route it to a human. A timestamp
  tells you WHEN, and I used it to answer WHO. The cost was a week of "decisao do
  dono" on files that were mine the whole time.

Also this pass: I reported the seven as 7 720 B. Measured: 6 720 B. I summed instead
of counting, by hand, on a number I had just measured. The ledger's first rule --
if a report says it records friction, the mtime must move in that window -- is the
one that would have caught it. It did not, because I wrote this entry after the
report, not before.

  gate: any byte total in a report must come from a command in that same window.

## 2026-10-11T05:39:36Z — "no test" and "cannot happen" are different defects

The sweep listed L301 among the GREEN guards and I carried it for fourteen passes as
"the guard at line 301 still has no constructed input" — phrased as a missing test.

It is not a missing test. Measured, POPULATION = 5 fixture classes driven through
`countDistinctContent` itself with the module's own arguments: a real clip exits 0 with
3 hashes; audio-only and zero-frame containers make ffmpeg exit non-zero ("Output file
does not contain any stream"); zero-byte and whitespace files are refused at open.
**0 of 5** give exit 0 with zero hashes, `runTool` rejects non-zero exits, and
`summarizeFrames` therefore never returns `total === 0`. Deleting L301 leaves the suite
at **21 passed / 0 failed, exit 0** — byte-identical to the control.

  rule: when a guard has no constructed input, the first question is whether an input
  CANNOT exist, not whether I failed to build one. Fourteen passes of "untested" were a
  tooling fact wearing a discipline's clothes.

  second rule, from the same work: my first probe reported `hash_lines = 3` on a fixture
  that produced none, because ffmpeg's stderr was counted as payload. I read the wrong
  stream before I read the right one. A counter fed the wrong field is worse than no
  counter, and it was the field I was measuring.

  third rule, about this entry itself: `Add-Content` with a here-string reported success
  and wrote nothing — the ledger was 5 727 B before and after. I only noticed because I
  re-measured instead of trusting the exit code. Measure the artefact, not the command.

## 2026-10-11T05:48:01Z - I retracted a green that was green, because my own instrument lied

Last turn I reported "the suite is not green, there is 1 failure in nvenc.test.mjs" and
retracted a correct 167 / 0. Both came from ONE bug: I read $mb.Groups[2].Value as the
passed count when group 2 is the FAILED count. So "9 vs 0" printed as 15/15 divergent,
ARMA2 summed a phantom failure, and nvenc appeared to declare 4 instead of 5.

  Measured now, POPULACAO = 15 suites, N = 2, 30 execucoes:
    IDENTICO N=2       15 / 15
    FALHAS declaradas   0
    EXIT != 0           0 / 15
    DIVERGENTES         0 / 15
    SOMA dos passed   167   <- labelled: MY sum, not a declared total
  nvenc.test.mjs alone, N=3: RESULT 5 passed, 0 failed, exit 0, three times.

  rule: a retraction generated by an instrument is not evidence. I retracted a true claim
  with a bug already visible in the same run's output -- "9 vs 0" is not a plausible pair
  of pass counts, and I read it as variance rather than as my own error.

  second rule, same lineage: a sum of other parties' declarations is my arithmetic, not
  their measurement. 167 is labelled a sum in every table from here on.

  third rule, from the same hour: Add-Content and then [IO.File]::AppendAllText both
  reported success and wrote nothing -- 5 727 B before and after, and 7 358 B before and
  after. The second failed with a path error I did not read, because I trusted the
  pipeline instead of re-measuring. Measure the artefact, not the command's mood.
## 2026-10-11T05:52:55Z - a divergencia -47 era a minha ancora

I reported a -47 gap between registrations counted in the source and the passed count
the suites declare, and I blamed four suites. All four were fine.

My extractor anchored on ^\s*(ta|t|test|it)\s*\( at the start of a line. Four suites
register with 	( or ok( NOT at column zero. Corrected to count INVOCATIONS whose
first argument is a string literal, regardless of indentation:

  POPULACAO = 15 suites
  source = 167   declared = 167   delta = 0
  suites with delta != 0 = 0 / 15

  rule: when a counter disagrees with a number another party declares, the counter is the
  prime suspect until proven otherwise. I had the arithmetic -47 and I went looking for a
  defect in the suites instead of a defect in the pattern. Four suites were accused of
  being wrong by a regex I had not tested against them.

  the test that would have caught it in one command: run the extractor against one file
  whose true count I already knew. I knew frame-accounting was 21 and my first anchored
  extractor reported 21 for it -- which is why I believed it, and why I never checked a
  file where it returned 0. Zero is the one number an extractor should never be trusted
  without a second opinion.

  third entry in this family, same hour: stderr counted as payload, Groups[2] read as
  passed, and now an anchor read as an identity. Three different instruments, one shape:
  the number looked fine and nobody asked what produced it.
## 2026-10-11T06:00:37Z - three guards, three different inputs, and I nearly guessed the classes

L232, L235 and L242 were carried as "no reachability analysis, and I refused to assume they
resemble L301 or L215". That refusal was right, and the three turned out to be a FOURTH
class: reachable, and each needing an input the other two do not reach.

  POPULACAO = 22 fixture specs, 9 container/codec shapes, 05:59:01Z-05:59:33Z
    L232  empty output   4/14   audio-only m4a, audio-only mkv, flac, zero-frame mp4
    L235  >1 field       1/14 in the first scan, then 5/8 in the second -- ONLY MPEG-TS
    L242  non-numeric    0/14, then 1/1 once the codec fourcc was rewritten to N/A
    numeric              9/14

  Proved by deletion, N=1 per arm, 06:00:37Z, against a 24/0 control:
    L232 mutant -> 22 passed / 2 failed, exit 1
    L235 mutant -> 23 passed / 1 failed, exit 1
    L242 mutant -> 23 passed / 1 failed, exit 1

  rules, in order of how much they cost:
  1. Container, not stream count. A 3-video-stream mkv prints ONE field under v:0 and
     THREE under v. Only MPEG-TS prints two under v:0. I would have guessed "multiple
     streams" and been wrong, because the intuitive fixture is the one that cannot work.
  2. To reach a non-numeric token, make the stream LISTABLE but not DECODABLE: rewrite
     avc1 -> zzzz in the sample entry. The container stays valid, so ffprobe exits 0 and
     prints N/A. No valid encode produces N/A; only a corrupted-but-listed stream does.
  3. A guard that "cannot be reached" and a guard reached by an input nobody has built yet
     look identical until someone enumerates container shapes. L301 and L235 are both
     about ffprobe refusing to emit what the guard wants. Same shape, opposite verdicts.

  and the honest limit: 22 specs is not an exhaustive enumeration of containers. It is the
  set I could build with the encoders on this host. A codec I cannot mux here may reach
  L235 or L242 by a route this scan never saw, and the header says so.