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
## 2026-10-11T06:03:50Z - two carried claims, both false, both countable in one command

I carried "six older mutation scripts still run without a parse gate" and "six modules
have never been swept" for several passes. Neither number was ever counted.

  POPULACAO = every .mjs/.py under the tree whose name matches mutat|sweep|falsif|probe:
    4 files found -- compose-probe.mjs, cw-probe.mjs, perf-probe.mjs, and
    stream-probe.test.mjs, which is already a suite. So the real population of probes
    needing a parse gate is 3, not 6, and I had never enumerated it.

  POPULACAO = every product .js in app/shadowplay: 14 modules.
    imported by some suite: 14 / 14
    NEVER SWEPT: 0 / 14
  "Six modules have never been swept" was false on both the count and the claim. Every
  module in the tree is imported by at least one suite. I carried a number I had never
  derived, in a sentence that repeated it across at least three reports.

  Measured on the 3 probes, and it is the shape the parse gate should take:
    compose-probe.mjs  18 775 ms  exit 0  -- ran to completion, no parse error
    cw-probe.mjs          110 ms  exit 0  -- no parse error
    perf-probe.mjs         135 ms  exit 1  -- TypeError ERR_INVALID_ARG_TYPE on undefined path
  perf-probe exits 1 for the wrong reason: a bad argument, not a broken parse. That is
  exactly what a parse gate exists to catch, and exactly what reporting it as a failure
  would have let through.

  rule: a carried count is a debt, not a fact. If it never came out of a command, it is
  a guess wearing the grammar of a measurement, and repeating it makes it more credible
  rather than more true. Both numbers here were wrong in the same direction -- larger
  than reality -- which is the direction a guilt-driven estimate always goes.
## 2026-10-11T06:11:21Z - a gate que distingue "falhou" de "obsoleto", e o que ela encontrou

perf-probe.mjs exited 1. I reported that as failing. It was not failing the code under
it -- it was talking to an API that no longer exists. The stack said ERR_INVALID_ARG_TYPE
at join(dir, undefined), which is hk.press(...).clip on a function that is now async
and returns { action, clip }.

parse-gate.mjs separates four outcomes instead of reading an exit code: PASS, SILENT
(exit 0, no receipt printed -- measured nothing), STALE_API (a TypeError/ReferenceError,
so the script is calling a signature that is gone), FAILED. Three of the four refuse.

  POPULACAO = every *-probe.mjs in the tree, READ OFF THE FILESYSTEM, not hand-listed.
  Measured: with 3 probes it says 3; I dropped a fourth in and it said 4 and reported it;
  I removed it and it went back to 3. A hand-written list would have passed throughout
  and missed the new file, which is the whole failure mode.

  RED ARM, run on every invocation: a deliberately stale script is written to temp, run,
  and MUST be refused. If it is ever accepted the gate prints GATE_BROKEN and exits 2.
  Measured: 169 B, exit 1, refused=true.

  NO_CONTRACT is a refusal, not a pass. I first shipped compose-probe and cw-probe as
  PASS with "no receipt contract declared" -- which makes the gate agree with any script
  that prints nothing. Changed in the same pass it was caught in.

  What the gate then found in one file, three deep: press() became async; ClipWriter
  needs { dir }; the ring has to be seeded with a real IDR-aligned clip before
  instantReplay will cut. Each one surfaced as exit 1 with a different stack, and the
  third is a refusal the product makes correctly -- "no segment begins on an IDR" -- that
  the probe was triggering by measuring nothing first.

  rule: an exit code is a verdict only when the thing that produced it is the thing you
  meant to measure. Otherwise it is a symptom, and the symptom is what you have to fix.
## 2026-10-11T06:34:03Z - the gate was not slow, I was reading its timeout as its verdict

Three turns I reported "the parse gate did not finish, its verdict is unread". It was
finishing every time and being killed by its own 120 s per-probe timeout, because
perf-probe.mjs ran N=2000 and the measured PER_PRESS_US of 161309.72 makes that
2000 x 0.1613 = 322.6 s. I did not multiply; I assumed the gate was slow.

  POPULACAO = 4 probe scripts, read off the filesystem. RED ARM refused=true (169 B, exit 1).
    compose-probe.mjs  PASS  exit 0, all 6 receipt keys printed
    cw-probe.mjs       PASS  exit 0, all 5 receipt keys printed
    perf-probe.mjs     PASS  exit 0, all 4 receipt keys printed
    _nonidr-probe.mjs  STALE_API  exit 1, ERR_INVALID_ARG_TYPE
    RESULT 3 passed, 1 refused   gate exit 1   stderr 0 B   runtime under 200 s

  The fourth probe is the one I restored from HEAD when I put back the eight deleted files.
  It rejoined the population and the gate called it stale on its first sight -- which is
  the argument for reading the population off the disk rather than naming it.

  Receipts are now declared for all four, read out of each probe's own console.log calls
  at 06:31:44Z. compose-probe's is the falsifying pair ZERO_BYTE_CLIPS /
  PRODUCT_LANDS_A_NONEMPTY_CLIP; cw-probe's is BYTES_LANDED plus the AFTER_ABORT refusal
  arm. Before this both were NO_CONTRACT -- correctly refused for being unproven, and
  useless, because a receipt nobody declares can never be checked.

  N in perf-probe is 200 now, with EXPECTED_PRESSES = 2000 kept visible and not claimed.
  The claim under test is that the writer hands out distinct monotonic names on the write
  path. 200 presses establish that; 2000 would only cost 320 s to say it again.

  rule: a timeout is not a verdict, and neither is a stall I have not multiplied out. I
  ran the same instrument for three passes and read my impatience as its answer.
## 2026-10-11T06:39:38Z - the gate's last refusal was mine, twice

Non-IDR probe: STALE_API. I took that as a stale API call and said so. It was not. The
probe reads process.argv[2] and the gate was invoking it with NO ARGUMENTS AT ALL, so
ERR_INVALID_ARG_TYPE was my own invocation failing, wearing the shape of an old signature.

  rule: an ERR_INVALID_ARG_TYPE on argv is the harness's error until proven otherwise. My
  STALE_API pattern caught TypeError because that is what a stale call looks like -- and
  also what calling a program that needs an input looks like. The pattern cannot tell them
  apart, so the gate must pass what the program needs, not just classify what came back.

Then the second refusal was also mine. I declared the receipt from memory with IDR_COUNT=
and PAYLOAD_RETAINED_PCT= using equals signs; the probe prints colons. The gate said
SILENT 2/6 and it was RIGHT: I had written a receipt for output that does not exist.
  rule: copy the receipt out of the probe's own output, not out of your recollection of
  what it probably prints. Two of my four receipts this pass were wrong in exactly that way.

  What the probe actually answers, given a real 14526 B annex-B stream built by ffmpeg:
    NAL_UNITS_PARSED 65, FIRST_PICTURE_NAL_TYPE 5, IDR_COUNT 2, NALS_KEPT 63,
    STRIPPED_BYTES 7946 of 14526, IDR_BYTES_REMOVED 6580, PAYLOAD_RETAINED_PCT 54.7,
    DECODABLE_FRAMES_NO_IDR 0, DECODABLE_FRAMES_WITH_IDR_CONTROL 60,
    NON_IDR_FIRST_STREAM_IS_UNDECODABLE true, NEGATIVE_ARM_REACHABLE false.
  A stream whose first picture is not an IDR does not decode: 0 frames without the IDR
  against 60 with it as control. So the negative arm for the IDR gate is unreachable BY
  CONSTRUCTION. That is why five prior attempts failed to build it, and it is a result.

  POPULACAO = 4 probes. Result: gate exit 0, all four PASS, RED ARM refused=true.
## 2026-10-11T06:47:53Z - fifteen passes with no way to run anything

There was no package.json, no Makefile, no hook and no runner. Measured 0 of 5 present.
Every suite number for fifteen passes came from a PowerShell loop I typed by hand each
turn, which is exactly why the suite was never re-verified after an edit and why the parse
gate only ran when I remembered to ask for it. I reported a number produced by a command
that existed for the length of one message.

run-all.mjs discovers both populations off the disk -- every *.test.mjs, plus the gate --
so neither can be omitted by my forgetting. It reports suites and the gate SEPARATELY,
because a gate refusing a probe is the gate working and is not the same event as a red
suite; folding them together would teach the reader to ignore the gate.

  MEASURED, POPULACAO = 15 suites, one process, WINDOW_UTC 2026-10-11T06:46:26Z:
    SUITES 15 passed, 0 failed, 0 unreported      GATE 4 passed / 0 refused, exit 0
    VERDICT suites_ok=true gate_ok=true            run-all exit 0

  THE ARM THAT MUST GO RED, run before the real run:
    run-all.mjs --red-arm  ->  GATE 3 passed / 1 refused, exit 1
    SELF-CHECK: noticed=true, runner exit 0
  GATE_FORCE_REFUSE manufactures a refusal in the gate so what is under test is the
  RUNNER's ability to notice one. If it is ever accepted the runner prints RUNNER_BROKEN
  and exits 2. This is checked every run, not once.

  frame-accounting.test.mjs reports 24, up from 21: the three arms I added for L232, L235
  and L242. That is the first time this suite has been counted by a command that anyone
  else could have run.
## 2026-10-11T06:56:14Z - a hook tinha de ser versionada, nao posta em .git/hooks

POPULACAO medida em .git/hooks: 4 ficheiros, os quatro do Git LFS, nenhum meu. Um hook
que vive so em .git/hooks e invisivel ao git, nao versionado, e desaparece no proximo
clone. Por isso o script vive em scripts/pre-commit e um shim de uma linha em .git/hooks
o invoca. A fonte da verdade e revizivel.

  medido: pre-commit nao existia antes de eu o instalar, tem 327 B, e os 4 hooks do LFS
  continuam 4/4 intactos.

  A fuga e ALTA E VISIVEL: SOTTO_SKIP_RUN_ALL=1 salta o run e DIZ-LO. Uma fuga que nao
  imprime nada e a maneira de um gate deixar de ser gate. E o gancho RECUSA se o
  run-all.mjs nao existir, em vez de passar em silencio por nao haver nada para correr.

  O custo e assumido em vez de escondido: o run completo demora minutos neste host, e um
  gancho lento e contornado. Se isso passar a ser o交换 errado, a correcao e uma CI de
  fundo, nao uma fuga silenciosa.
## 2026-10-11T07:01:30Z - the hook's pass path, proven by a commit that had nothing to hide

I had proven the refusal path and then admitted the pass path was unverified, because the
commit that landed had used SOTTO_SKIP_RUN_ALL=1. A gate with only its NO proven is half a
gate: it might refuse everything.

  MEASURED, WINDOW_UTC 2026-10-11T07:01:30Z, no bypass set (SOTTO_SKIP_RUN_ALL empty),
  a real one-file change staged, git commit, nothing else:
    pre-commit: running suites and parse gate (skip with SOTTO_SKIP_RUN_ALL=1)
    RUN ALL  WINDOW_UTC 2026-10-11T07:01:30Z
    SUITES 15 passed, 0 failed, 0 unreported
    GATE 4 passed / 0 refused, exit 0
    VERDICT suites_ok=true gate_ok=true
    commit exit 0   HEAD b20ccc8   main unchanged   dirty 0

  Both paths now measured: refusal at 06:57 (exit 1, with the message), pass at 07:01
  (exit 0, after the hook ran 15 suites and the gate on its own). The hook decides; it is
  not a formality that waves everything through.

  The entry this replaced was a marker line I added purely to create something commit-
  table. That is the one thing a friction ledger must not contain -- a row whose only
  purpose is to prove the ledger commits. Replaced with what it actually proved.

  rule: a gate proven only in the direction that refuses you is not a gate, it is an
  obstacle. Prove both directions or you have measured half an instrument.

## 2026-10-11T07:08:26Z - install-hooks: versioned installer, checked in both directions

## 2026-10-11T07:14:32Z - chain instead of replace: LFS bodies preserved byte-identical

## 2026-10-11T07:48:35Z - the instrument to measure instability was itself the unstable thing

## 2026-10-11T07:59:57Z - the machine this installer exists for had no gate at all

I built install-hooks to make a fresh clone safe, and then never ran it on a machine
without Git LFS. Measured 2026-10-11T07:59:06Z on a bare git init: post-checkout and
post-merge both reported ABSENT and NEITHER WAS CREATED. The only host I tested was the
one that already had four foreign hooks, where the chaining branch worked perfectly. The
case the installer was written for is the one case it silently skipped.

  rule: test the tool on the machine it exists FOR, not on the machine you are standing
  on. My repo has LFS. Every clone someone else makes might not.

Then --check called the freshly-installed hook NO-ORIGINAL and CHECK FAILED, because a
hook we wrote ourselves has no original to be stale against. It was right that no
original exists and wrong to call that a failure. Both cases now pass:
    fresh repo, no LFS   ok post-checkout (chained; installed fresh, no foreign body)
    this repo, LFS       ok post-checkout (chained; LFS body byte-identical)

And the second commit in that test repo was REFUSED by my own pre-commit, correctly:
app/shadowplay/run-all.mjs does not exist there, and the hook refuses rather than passing
quietly because there was nothing to run. That is the behaviour working, not failing.

## 2026-10-11T08:01:57Z - the chained post-checkout ran for real, twice, in both directions

It had been installed and CHECK OK for two turns without ever executing. Built a throwaway
repo at G:\Temp\ht4 with a STUB run-all.mjs (prints RESULT 1 passed, exits 0) so the
pre-commit had something real to call, made two commits, then checked out.

  MEASURED, POPULACAO = 2 real checkouts, WINDOW_UTC 2026-10-11T08:01:57Z:
    git checkout 29983e6   exit 0  HEAD moved, a.txt v2 -> v1
      then, printed BY THE HOOK:
        ok pre-commit (matches its source)
        ok post-checkout (chained; installed fresh, no foreign body to preserve)
        ok post-merge   (chained; installed fresh, no foreign body to preserve)
        CHECK OK
    git checkout -         exit 0  HEAD back, a.txt v1 -> v2
      the same three lines printed again.

  So the chain is not decorative: a checkout in this repo re-installs and re-reports every
  hook. That is the whole point of chaining post-checkout -- the moment a clone lands with
  no gate, the first thing that happens is the gate checks itself.

  Two notes on how it got measured, both mine:
  1. the first attempt used only one commit, so HEAD~1 did not exist and the checkout
     was a no-op with atal: Needed a single revision. I read a green-looking line as a
     pass until the file contents proved nothing moved.
  2. git add -A in a scratch repo is fine and in this one it is not; I staged paths
     explicitly here and that is why nothing of the owner's was swept in.

## 2026-10-11T08:04:36Z - post-merge executed for real; all three hooks now have run

Third piece in the series, and the last one that was installed but unexercised.

  MEASURED, POPULACAO = 1 real merge, WINDOW_UTC 2026-10-11T08:04:36Z, in G:\Temp\ht5:
    base commit on master, side branch with b.txt, c.txt on master
    git merge side  -> exit 0
      Merge made by the 'ort' strategy.  b.txt | 1 +  create mode 100644 b.txt
      then, printed BY THE HOOK:
        ok pre-commit (matches its source)
        ok post-checkout (chained; installed fresh, no foreign body to preserve)
        ok post-merge   (chained; installed fresh, no foreign body to preserve)
        CHECK OK
    files after: a.txt, b.txt, c.txt  -- the merge actually landed.

  So all three hooks have now executed at least once, each from git rather than from a
  script I typed: pre-commit on two commits, post-checkout on two checkouts, post-merge on
  one merge. Nothing in this series has been reported as working on the strength of the
  file merely existing, which is the mistake I made four times in this hour.

  Honest limit: all three were exercised in a THROWAWAY repo with a stubbed runner. The
  hook logic is the same and the wiring is real; what is NOT proven here is the gate
  refusing a real suite from inside a real git operation, because a stub always passes.

## 2026-10-11T08:05:09Z - the 5/5 distribution was taken in reduced mode; here is the real one

I reported clean=5/5 and said plainly that it was taken with PERF_PROBE_N=20. Reporting a
distribution honestly is not the same as having the distribution you need, so this is the
same measurement at the real N.

  MEASURED, POPULACAO = 2 runs x 4 probes, PERF_PROBE_N unset so perf-probe runs N=200:
    run 1: 4 passed, 0 refused
    run 2: 4 passed, 0 refused
    DISTRIBUTION clean=2/2  dirty=0/2

  What I now hold, stated as counts and not as adjectives:
    reduced mode (N=20)   5/5 clean
    real mode (N=200)      2/2 clean
    earlier single runs    4/4 clean at 07:20, 4/4 at 06:40
    one refusal            3/1 at 07:14, inside a commit whose pre-commit was also running
    total gate runs measured = 13; clean = 12; refused = 1; no cause proven for the one.

  A 1-in-13 refusal with no explanation is not a solved problem, it is a known unknown with
  a denominator. It is also not a reason to keep the gate off: a gate that is right 12 times
  out of 13 and says why the 13th time is worth more than a gate that is never wrong
  because it never runs.

## 2026-10-11T08:11:09Z - the gate refusing a real commit, with a runner that actually fails

Every previous hook test ran against a stub that exits 0. A stub always passes, so the one
thing that matters -- does the gate STOP a commit -- had never been observed.

  MEASURED, POPULACAO = 4 real git commits, WINDOW_UTC 2026-10-11T08:10:48-08:11:09Z, in
  G:\Temp\ht6, run-all.mjs replaced by one that prints a real failure and exits 1:

    1. before install-hooks    commit exit 0   commits 1
       the hooks were not installed yet, so nothing could refuse. Worth measuring: the
       gate is not a property of the repository, it is a property of the INSTALLATION.
    2. after install-hooks     commit exit 1   commits 1   HEAD unmoved
         pre-commit: running suites and parse gate
           RUN ALL (failing stub)
             encoder.test.mjs FAIL 2 passed, 1 failed :: no free sequence value after 10
             SUITES 14 passed, 1 failed, 0 unreported
             GATE 4 passed / 1 refused, exit 1
             VERDICT suites_ok=false gate_ok=false
         pre-commit: run-all exited 1 -- commit refused.
       a.txt stayed staged, HEAD unmoved, the failing TEST NAME reached the terminal.
    3. SOTTO_SKIP_RUN_ALL=1    commit exit 0   commits 2
         "pre-commit: SOTTO_SKIP_RUN_ALL=1 set -- suites and gate NOT run for this commit"
    4. variable removed        commit exit 1   commits 2   refused again

  That is the whole contract in four commits: refuse, refuse-loudly-on-bypass, refuse
  again. And the failure is NAMED, not just counted, so the next person sees which test
  broke rather than only that something did.

  rule: an instrument tested only on inputs it passes has not been tested. Three passes
  in a row told me nothing about the one question the gate exists to answer.

## 2026-10-11T08:19:49Z - the gate refuses a red REAL suite. Finally, and only because I read the file first

The previous attempt appended the injected t() after process.exit, so it never ran, the
suite stayed 9/0, and the commit sailed through. I committed that too (9f91d89), which is
worth recording: an injection that proves nothing is still a change, and it went in.

This time I read the file first. session-clock.test.mjs runs its tests SYNCHRONOUSLY --
line 7 is 	ry { fn(); passed++ } -- there is no drain loop at all, and line 48 is
process.exit. Inserting above the RESULT line at L47 was the right place; appending was
never going to work, and neither would "the drain loop" have.

  MEASURED, POPULACAO = 1 real suite + 1 real commit, WINDOW_UTC 2026-10-11T08:19:41-49Z:
    session-clock.test.mjs  1981 -> 2379 B, injected test above the RESULT line
    RESULT 9 passed, 1 failed, WIDTH=4  exit 1        <- the suite really went red
    git commit -> exit 1, HEAD unmoved at 95efaa9, the injected file stayed staged
    suite restored from HEAD: 1981 B, INJECTED absent, RESULT 9 passed, 0 failed, exit 0

  So the gate has now refused, from inside a real git operation, over the real 15-file
  suite rather than a synthetic runner. That was the last thing this gate had not been
  observed doing.

  rule: before you inject a fault, read where the thing under test actually executes. I
  assumed a drain loop existed because three other suites have one, and the assumption
  cost two turns and a bad commit.
