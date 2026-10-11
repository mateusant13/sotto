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

## 2026-10-11T08:27:12Z - the gate checks that receipt keys PRINT, not what they SAY

Chasing the one unexplained refusal from 07:14, I ran each probe alone and then compose-
probe four times with its full output. What came back is worse than a flaky probe.

  MEASURED, POPULACAO = 4 runs of compose-probe.mjs, WINDOW_UTC 2026-10-11T08:27:12Z:
    COMPOSED_OK type=Shadowplay
    CLIP_FILES_ON_DISK=0
    ZERO_BYTE_CLIPS=0
    PRODUCT_LANDS_A_NONEMPTY_CLIP=NO
    DONE                                    exit 0, every run

  The probe assembles the product, presses nothing, writes NO clip, and exits 0. Its own
  falsifying key says NO -- the product did not land a non-empty clip -- and the gate
  reports PASS, because classify() asks out.includes(key) and NO contains every key the
  receipt declares.

  So the 07:14 refusal was never a flaky probe. The refusal was RIGHT and I read it as
  noise: at 07:14 something was genuinely failing, I never identified what, and I filed
  it under contention because that was the hypothesis that let me keep going. The gate
  has since reported 4/4 clean while this probe has been reporting PRODUCT_LANDS_A_=NO.

  Two defects, and the second is the one I would have missed:
    1. compose-probe exits 0 having measured that nothing was written. It should exit
       non-zero when its own falsifying key is NO. A probe that cannot fail is the exact
       class this whole exercise exists to catch, and I wrote one.
    2. the gate checks key PRESENCE, not key VALUE. Every gate pass since 06:40 has been
       evidence that keys printed, not that the product did what they claim.

  rule: a receipt with a value of NO is not a receipt, it is a failure wearing a receipt's
  clothes. Any key whose value can be NO/YES must be compared, not merely found.

  Not fixed in this entry: both fixes are written and neither is committed here. The
  gate should read PRODUCT_LANDS_A_NONEMPTY_CLIP=YES explicitly and compose-probe should
  exit 1 when it is NO -- and until that lands, no gate result in this ledger should be
  read as a claim about the product.

## 2026-10-11T08:33:11Z - the option was dir. The probe asked for clipsDir and counted an empty directory for a day.

Closing the previous entry's open question: why was CLIP_FILES_ON_DISK 0?

  composeShadowplay destructures { dir = null, ... } -- index.js:180-195. My probe passed
  { clipsDir: dir }. An unknown key is silently dropped, the app fell back to
  ensureClipsDir(env), and the probe counted a temp directory nothing had ever been
  written to. MEASURED, POPULACAO = 1 composition, WINDOW_UTC 2026-10-11T08:31:46Z:
      capture() -> {"out":"G:\Temp\shadowplay-e3YN34\cap-32336-1.mp4",
                    "bytes":2112890,"frames":225,"firstIdr":0,"codec":"h264_nvenc"}
      CLIP_FILES_ON_DISK=0        <- counting a directory the product never wrote to
      PRODUCT_LANDS_A_NONEMPTY_CLIP=NO

  The product was writing 2 112 890 bytes of real h264 all along. The probe was reading
  the wrong directory and reporting the absence as a property of the product.

  Fixed both defects:
    - the option name: composeShadowplay({ dir })
    - the probe can now fail: process.exit(landed ? 0 : 1)
  Re-measured, 08:32:45Z: exit 0, capture() wrote 1 958 964 bytes,
  CLIP_FILES_ON_DISK=1, PRODUCT_LANDS_A_NONEMPTY_CLIP=YES, VERDICT_DIR printed.

  And the gate, which now COMPARES that key instead of only finding it:
    _nonidr PASS 6 keys · compose PASS 6 keys, 1 truth-valued key COMPARED
    cw PASS 5 keys · perf PASS 4 keys      RESULT 4 passed, 0 refused, exit 0

  So the first honest 4/4 of this gate: every key present AND the one key that can be NO
  verified as YES. Before this entry, every 4/4 in this ledger meant only that keys printed.

  rule: a measurement pointed at the wrong place is worse than no measurement, because it
  reports a property of something other than the thing under test -- and it reported NO,
  which I filed under flakiness for six turns. Check WHERE you are looking before asking
  WHY you see nothing.

## 2026-10-11T08:39:15Z - both exceptions were mine: an array where the signature wants a string

Closing the previous entry's second open question: why did deliver() and captureAndDeliver() throw?

  MEASURED, POPULACAO = 10 prototype methods on 1 composition, WINDOW_UTC 2026-10-11T08:39:15Z:
      deliver(key = "f9", nowMs = 0)          index.js:167  -> the KEY IS A STRING
      captureAndDeliver(opts = {})            index.js:170  -> opts IS AN OBJECT
      capture({source,seconds,fps,gop} = {})   index.js:143  -> opts IS AN OBJECT

  My probe loop called every method as fn.call(app, key === "deliver" ? ["f9"] : []).
  An array is not a non-empty string, so deliver() threw on a CORRECT argument, and
  captureAndDeliver() passed [] into capture()'s destructuring -- which does not throw,
  it silently yields every default. It then reached a writer whose retry loop I had
  already reported as "10 attempts exhausted", which was this same malformed call.

  Neither exception was a product defect. Both were the probe calling with the wrong shape.
  Same failure class as the clipsDir/dir mistake one entry up: I measured the product
  through an interface I had not read.

  After the fix, POPULACAO = 4 methods that do work, same window:
      capture()            -> cap-39068-1.mp4  2 078 873 B  234 frames  firstIdr 0  h264_nvenc
      deliver()            -> {action:"instant-replay", clip:0000.mp4, verdict:{...}}
      captureAndDeliver()  -> cap-39068-2.mp4  2 184 364 B  232 frames  + {action:"debounced"}
      captures()           -> 2
      CLIP_FILES_ON_DISK=1  0000.mp4  2 078 873 B  ZERO_BYTE_CLIPS=0  exit=0

  Two things I had filed as defects are actually the design working, and I should have read
  them before reporting:
    - capture() writes to the ENCODER'S staging dir (shadowplay-VjI9eL), not to clipsDir.
      Only deliver() lands bytes in clipsDir, as 0000.mp4. The staging bytes and the
      delivered bytes are EQUAL -- 2 078 873 both sides -- which is the INTEGRATION-PLAN
      invariant stated exactly: a saved clip is remuxed from already-encoded bytes, never
      re-encoded. I had assumed capture() wrote to clipsDir because that is where I
      pointed the counter.
    - the second deliver() returned {"action":"debounced"}. That is the debounce window
      doing its job on two F9 presses, not a failure to deliver.

  rule: an exception thrown by a call I shaped is information about my call, not about the
  product. Before filing any throw as a defect, read the signature the method declares.

## 2026-10-11T08:45:28Z - three more probes now carry a truth, and I proved the arm goes RED first

Closing the entry that opened with "before this entry, every 4/4 meant only that keys printed".

  VALUED gained the three keys whose values are booleans, not counts. Measured by RUNNING
  each probe, POPULACAO = 3 probes, WINDOW_UTC 2026-10-11T08:43:58Z (cw, perf) and
  08:44:25Z (_nonidr, against the same ffmpeg-built 14526 B annex-B stream):
      cw-probe       BYTES_LANDED=YES
      perf-probe     SEQUENCE_MONOTONIC=true
      _nonidr-probe  NEGATIVE_ARM_REACHABLE: false

  I read these values out of real runs rather than out of the file, on the strength of the
  two mistakes earlier today, both of which were a shape I assumed instead of one I read.

  THEN I PROVED THE ARM BEFORE CREDITING ANY PASS, which is the part that is new. First
  attempt failed: I substituted the literal BYTES_LANDED=YES -> NO and the replacement did
  not match, because cw-probe.mjs:42 interpolates:
      console.log(BYTES_LANDED=);
  So the first injection was a NO-OP, not a RED -- which is the same shape as the 9f91d89
  injection that proved nothing and got committed anyway. Caught it because I printed the
  file hash before and after and compared.

  Second attempt replaced the whole line at L42 with console.log("BYTES_LANDED=NO"):
      cw-probe.mjs  RECEIPT_FALSE  all keys printed but BYTES_LANDED=NO
                    -- the probe reported a failure and still exited 0
      RESULT 3 passed, 1 refused     gate exit=1
  restored cw-probe.mjs from a copy taken beforehand:
      sha256 73F46B3A9A27 before, 73F46B3A9A27 after -- EQUAL

  Clean run, POPULACAO = 4 probes, 08:44:53Z and again after the restore:
      RED ARM exit=1 refused=true
      _nonidr  PASS  6 keys, 1 truth-valued key compared
      compose  PASS  6 keys, 1 truth-valued key compared
      cw       PASS  5 keys, 1 truth-valued key compared
      perf     PASS  4 keys, 1 truth-valued key compared
      RESULT 4 passed, 0 refused   exit 0

  KNOWN LIMIT, stated rather than hidden: the RED arm was executed on ONE of the four
  probes (cw). All four share the identical comparison at parse-gate.mjs:142, so the
  code path is the same, but only one is measured. Three of four are reasoned, not shown.

  rule: an injection that does not change the file is not a RED arm, it is a no-op that
  looks like one. Hash the artifact before and after the injection, every time, or you
  will credit a falsifying arm that never fired -- which is exactly what 9f91d89 did.

## 2026-10-11T08:52:28Z - four RED arms, and the fifth attempt was the same lie as 9f91d89 wearing a new hat

Closing the limit I stated one entry up: "the RED arm was executed on ONE of the four".
It is now executed on all four, and the attempt that failed first is the useful part.

  POPULACAO = 4 probe scripts, WINDOW_UTC 2026-10-11T08:49:37Z .. 08:52:28Z. Each arm
  replaces the probe's real print line with one that prints the opposite truth, runs the
  gate, and restores the file from a copy taken beforehand:

    compose-probe.mjs  L79  RECEIPT_FALSE  PRODUCT_LANDS_A_NONEMPTY_CLIP=NO   exit=1
    cw-probe.mjs       L42  RECEIPT_FALSE  BYTES_LANDED=NO                   exit=1
    perf-probe.mjs     L76  RECEIPT_FALSE  SEQUENCE_MONOTONIC=false          exit=1
    _nonidr-probe.mjs  L98  RECEIPT_FALSE  NEGATIVE_ARM_REACHABLE: true     exit=1
    clean run          RESULT 4 passed, 0 refused                          exit=0
    every restore verified by sha256 equal: compose 57614A45DB27, cw 73F46B3A9A27,
    perf 6F0D52A81D1A, _nonidr AFDB25D98BCF

  THE FAILED ATTEMPT. My first perf injection reported "ficheiro ALTERADO=True" and the
  gate returned PASS. Both of those are true and together they were a lie:

      perf-probe.mjs:13  // The receipt is SEQUENCE_MONOTONIC, which 200 presses ...
      perf-probe.mjs:76  console.log("SEQUENCE_MONOTONIC=" + (Number(last.slice(0, 4)) === N));

  Select-String matched the COMMENT at L13, not the print at L76. I replaced a comment with
  console.log("SEQUENCE_MONOTONIC=false") -- so the probe printed false AND true. The gate
  PASSed, and it was right to: the key still said true somewhere in the output.

  This is 9f91d89's exact shape. "The file changed" is not "the claim changed". Hashing
  the file caught the first no-op; hashing the file did NOT catch this one, because the
  bytes DID change. What caught it was reading the original line back -- which I only did
  because the injection printed the line it was replacing, and that line was a comment.

  FINDING, NOT YET FIXED: parse-gate.mjs:142 tests truth keys with out.includes(key + want).
  A probe that prints the same key twice, once with the wanted value and once without, PASSES.
  The honest form is to require that the key's value is UNAMBIGUOUS -- every occurrence of
  key + value, and at least one occurrence. Not done; recorded rather than claimed.

  rule: an injection proves something only if it removes the claim, not the bytes. Print the
  line you replaced and ask whether it was the line that carried the claim -- and if the
  gate can be satisfied by one good copy among contradictory ones, the gate is weaker than
  the arm that is supposed to be testing it.

## 2026-10-11T08:57:35Z - the gate now refuses a probe that contradicts itself, and says why honestly

Closing the finding from the last entry. It was recorded, not claimed fixed. Now it is.

  THE DEFECT. parse-gate.mjs:142 tested truth keys with out.includes(k + want). That asks
  "does the wanted value appear SOMEWHERE", not "is every value the wanted one".

  THE COUNTEREXAMPLE WAS ALREADY MEASURED, by me, one entry up, 08:49:37Z: perf-probe
  printed SEQUENCE_MONOTONIC=false AND SEQUENCE_MONOTONIC=true and the old gate returned
  PASS. I filed that as "the gate was right to pass" -- it was not right to pass, the probe
  was self-contradictory -- and I filed it under my own injection error rather than under
  the gate's tolerance. Both were true and only one was the instrument's fault.

  THE FIX. Collect every value the key was printed with; the key must be printed at least
  once AND every occurrence must equal the wanted value.

  THE RED ARM, POPULACAO = 1 probe, WINDOW_UTC 2026-10-11T08:56:01Z and 08:57:09Z.
  This time the injection APPENDS a line rather than replacing one, so the probe carries
  both values in one run:
      BYTES_LANDED=YES
      BYTES_LANDED=NO     <- injected, the real print at L42 untouched
      BYTES_LANDED=YES
      -> cw-probe.mjs RECEIPT_FALSE, RESULT 3 passed, 1 refused, gate exit=1
      cw-probe.mjs restored from a copy taken beforehand, sha256 73F46B3A9A27 equal.
  Under the old check this exact output was a PASS. It is measured, not argued.

  SECOND DEFECT, FOUND BY THE FIRST. The RECEIPT_FALSE message printed only the FIRST
  occurrence, so it said "all keys printed but BYTES_LANDED=YES" -- which reads as "the
  value was wrong" when the value was YES and the problem was the NO beside it. The
  verdict was right; the reason it gave was wrong about its own reason. It now prints the
  distinct values and what it wanted:
      cw-probe.mjs RECEIPT_FALSE all keys printed but BYTES_LANDED=YES | NO (wanted YES)
  measured 08:57:09Z, same injection.

  Clean run after both restores, POPULACAO = 4 probes, 08:57:35Z:
      RED ARM exit=1 refused=true · _nonidr/compose/cw/perf PASS, 1 truth-valued key each
      RESULT 4 passed, 0 refused   exit 0

  rule: "some occurrence matches" is not a claim, it is a coincidence. An instrument that
  accepts one good copy among contradictory ones is weaker than the arm meant to test it,
  and a receipt that misdescribes why it failed is worse than silence.

## 2026-10-11T09:02:15Z - the never-printed branch is reachable only for a key that is not in RECEIPTS, and I stopped guessing which

Closing the one item I had filed as "code I read but did not exercise".

  MEASURED FIRST, before building the injection, because the branch may not be reachable:
  every VALUED key is also declared in RECEIPTS.
      PRODUCT_LANDS_A_NONEMPTY_CLIP=   in RECEIPTS  True
      BYTES_LANDED=                    in RECEIPTS  True
      SEQUENCE_MONOTONIC=              in RECEIPTS  True
      NEGATIVE_ARM_REACHABLE:          in RECEIPTS  True

  So with today's tables seen.length === 0 CANNOT fire: if a VALUED key is missing from
  the output, the earlier RECEIPTS check at parse-gate.mjs:137 has already returned SILENT
  first. It is defensive code, not dead code -- reachable the moment anyone declares a
  VALUED key without also declaring it as a receipt. That is a real configuration, not a
  thought experiment, and it is exactly what I injected.

  RED ARM, POPULACAO = 1 probe, WINDOW_UTC 2026-10-11T09:01:50Z. Added to cw-probe's
  VALUED block one key no probe can print:
      "A_CHAVE_NUNCA_IMPRESSA=": "YES"
      -> cw-probe.mjs RECEIPT_FALSE
         all keys printed but A_CHAVE_NUNCA_IMPRESSA= (wanted YES)
      RESULT 3 passed, 1 refused    gate exit=1
      parse-gate.mjs restored from a copy taken beforehand, sha256 D8D55794726E equal.
  Clean run 09:02:15Z: RESULT 4 passed, 0 refused, exit 0.

  The receipt text is right here too: the distinct value list is EMPTY, so it prints the
  bare key with no value after it, which is exactly what "printed nothing" should look
  like. The fix I made last entry to the message made this branch legible for free.

  My first attempt at this experiment exited 1 with NO OUTPUT: PowerShell parse error from
  nested escaped quotes inside a "$(...)" in a double-quoted string. Re-ran without the
  nesting. Worth recording because the symptom -- an empty result -- looks like the
  experiment produced nothing to measure, when it never started.

  AND THEN I DID IT AGAIN, in the very next command, writing this entry: the ledger text
  above is inside an expandable here-string, so the "$(...)" I was describing was EVALUATED
  as a subexpression, errored, and left a bare "" where the example should be. Caught by
  reading the tail back before trusting the commit. A here-string that explains an
  interpolation bug will interpolate the example it quotes unless you escape it.

  rule: before proving a defensive branch reachable, check whether the configuration that
  reaches it is one you could actually ship. Half of "defence in depth" is unreachable by
  construction, and an unreachable guard is indistinguishable from a working one until you
  try to fire it.

## 2026-10-11T09:07:30Z - the 07:14 refusal is unrecoverable, its only hypothesis is REFUTED, and the log I added to prevent a repeat found a live defect on its first run

Closing the escalation. I could not recover the cause, and I am not going to write one down
as if I had.

  WHAT IS NOW KNOWN, POPULACAO = 13 gate executions on 2026-10-11, WINDOW 06:42Z..07:22Z.
    .git/hooks/pre-commit is a 150 B shim -> scripts/pre-commit -> run-all.mjs ->
    parse-gate.mjs with spawnSync timeout 300000. So every commit DOES run the gate.
    The 07:14Z refusal sits between c32e565 (07:08:26Z) and e387e8b (07:22:24Z).

  THE HYPOTHESIS I HAD, REFUTED BY MEASUREMENT. I had written "it happened inside a
  commit whose pre-commit also runs the gate; hypothesis of host contention, not
  measured." Two gates in parallel, WINDOW_UTC 2026-10-11T09:05:04Z:
      porta A exit=0 in 27.5 s      porta B exit=0 in 27.6 s
      both RESULT 4 passed, 0 refused
  They ran concurrently, took the same time as one, and both passed. 27.5 s against a
  300 s timeout is 9 percent of the budget, so contention is not a mechanism that could
  have produced a refusal. The hypothesis is false, not merely unproven.

  THE CAUSE ITSELF IS GONE. The last surviving log of that window, g-now.txt, is the
  07:20:24Z run -- AFTER the refusal. Nothing retained the 07:14 output: the verdict went
  to a terminal that had scrolled away, and the commit it would have blocked never
  happened, so there was no second copy anywhere. Same shape as the two unrecoverable
  CRITICAL findings from the document pass: untracked bytes and no backup.

  SO I FIXED THE CLASS INSTEAD OF THE INCIDENT. Every gate run now appends its full
  verdict to state/gate/gate-log.txt: timestamp, population, red arm, every probe with
  its verdict and reason, RESULT and GATE_EXIT. Evidence recording is wrapped in try/catch
  so it can never change the verdict.

  AND IT PAID FOR ITSELF ON THE FIRST RUN. Three runs, 09:06:41Z / 09:07:05Z / 09:07:30Z:
      run 1  RESULT 4 passed, 0 refused          GATE_EXIT 0
      run 2  RESULT 2 passed, 2 refused          GATE_EXIT 1
      run 3  RESULT 4 passed, 0 refused          GATE_EXIT 0
  Run 2 carried the manufactured _nonidr refusal, and beside it the log recorded something
  I had never seen and had been running clean past all day:
      compose-probe.mjs FAILED  exit 1: deliver() -> THREW Error: instant replay refused:
        G:\Temp\shadowplay-e2e-4FYBFS\0000.mp4 holds 28 contiguous d...
  The gate truncates its error line at 110 chars, so that tail is all that survived.

  CORRECTION, 09:12Z, and it is the same failure class this whole day is about. I wrote
  above that the message reads "holds 28 contiguous decodable frames". It does not. The
  source is replay-ring.js:340-346:
      instant replay refused: ${source} holds ${verdict.longestUniqueRun} contiguous
        distinct frames but covers ${verdict.expectedFrames} frame slots; the clock is
        there and the content is not
  The word is DISTINCT, not "decodable", and the sentence continues past where the gate cut
  it. I supplied a plausible-sounding word inside quotation marks. I have spent this day
  catching exactly this in other people's documents and did it to myself here.

  AND THE CHARACTERISATION WAS WRONG TOO. "That is a PRODUCT failure -- deliver() refusing
  a clip it had just written" is not established. What replay-ring.js:340 does is refuse
  when verdict.contentSufficientToCoverClock is not true, which frame-accounting.js:367
  defines as longestUniqueRun >= oneSecondOfClock. 28 unique frames is under one second at
  30 fps, so the refusal is the guard WORKING on the content it was given. What is
  unexplained is not the refusal but why that run's clip carried 28 unique frames when the
  same probe carries 219-234 all day.

  REPRODUCTION ATTEMPTED, POPULACAO = 6 direct runs, WINDOW_UTC 2026-10-11T09:11:10Z:
      run 1..6   exit=0, no throw
      6 passed, 0 failed
  So: 1 occurrence in the 7 runs I have observed. That does not support the word
  "intermittent" as a rate, and I am not writing one down. It does not reproduce on demand,
  and GATE_FORCE_REFUSE=1 has no path to the probe -- compose-probe never reads it.

  My own log line was wrong on the first run and I fixed it before committing:
  RED_ARM exit=undefined, because I guessed the property name. Exactly the failure class
  this whole day is about -- a field I had not read. Now it prints only arm.refused.

  rule: an instrument that cannot say WHY it said NO last time will re-diagnose the same
  refusal from scratch forever. And a refuted hypothesis is worth more than an open one:
  "contention" was comforting and it was wrong.

## 2026-10-11T09:17:07Z - the ring holds ONE segment every time, which makes 28 a logical consequence rather than a mystery

Reading the cut before theorising about it. replay-ring.js:182-188:

    #cutFromLastKeyframe() {
      for (let i = this.#segments.length - 1; i >= 0; i--) {
        if (!this.#segments[i].keyframe) continue;
        return Buffer.concat(this.#segments.slice(i).map((s) => s.bytes));
      }
      return null;
    }

It walks BACKWARDS and cuts from the LAST keyframe to the end. So the clip length is the
frames deposited AFTER the last keyframe. With one segment that segment is itself the
keyframe and the cut is the whole capture -- the 206-234 frame case. To land on 28, the
ring must have held AT LEAST TWO segments with the last of them a keyframe sitting ~28
frames from the end. At 30 fps that is under oneSecondOfClock, frame-accounting.js:367 sets
contentSufficientToCoverClock false, and replay-ring.js:340 refuses.

  MEASURED, POPULACAO = 5 captures, WINDOW_UTC 2026-10-11T09:17:07Z, new probe
  keyframe-shape-probe.mjs (3335 B), which composes for real, captures, and reads the ring
  through the public getter:
      run 1  frames 215  RING_SEGMENTS 1  threw=no
      run 2  frames 220  RING_SEGMENTS 1  threw=no
      run 3  frames 215  RING_SEGMENTS 1  threw=no
      run 4  frames 206  RING_SEGMENTS 1  threw=no
      run 5  frames 214  RING_SEGMENTS 1  threw=no
      5 passed, 0 failed

  So the precondition is measured in the passing case and its absence is measured: every
  successful run is a single-segment ring, and with one segment 28 is not reachable. The
  failing run therefore held 2+ segments. That is arithmetic on the code I read, not a
  guess about NVENC.

  WHAT THE PROBE DELIBERATELY DID NOT DO. segments() returns a COUNT and the segment list
  is a private field. I did not reach past it to enumerate which segments are keyframes,
  because a probe that reads the internals it is measuring is no longer evidence about the
  product. The probe therefore cannot confirm the second keyframe; it can only show that
  the ordinary case is one segment.

  STATUS: mechanism sharpened and partly measured, NOT confirmed. 0 of 5 reproductions,
  1 occurrence in 8 runs I have run today. I am not writing a failure rate.

  THE DESIGN QUESTION THIS RAISES, which I am not acting on without evidence: if the ring
  holds a keyframe 28 frames from the end, "cut from the last keyframe" and "must cover a
  second" are in tension, and the product resolves it by refusing. Walking back to the
  EARLIEST keyframe that still covers a second would deliver instead. That is a behaviour
  change to a delivery rule I have not verified against the design documents, and three
  errors today came from changing a rule before reading what it says.

  rule: a precondition measured in the passing case can make a failure arithmetic. Five
  one-segment runs turn "what could produce 28" into "the failing run had two segments" --
  which is a narrower, testable claim than the one I started with.

## 2026-10-11T09:19:41Z - the ring never looks for an IDR; the caller asserts one and the caller is always right

I went to the design document instead of weighing the behaviour against my own intuition.
The document answered, and it did not say what I assumed.

  WHAT THE DOCUMENT SAYS. SHADOWPLAY-INSTANT-REPLAY.md:166-168, verbatim:
      The correctness trap that makes remux non-trivial: you cannot start an MP4 at an
      arbitrary byte offset. The clip must start at an IDR/keyframe. So the encoder is
      configured with a short GOP (~ 1 s at 60 fps) precisely so the clip boundary is
      within one second of the user's press.
  So a SHORT clip cut at the nearest keyframe is the DESIGNED behaviour, not an accident.
  My earlier note that the two rules were "in tension" was me grading the product against
  my own preference for longer clips. The document says the opposite.

  WHAT THE CODE DOES, measured not inferred:
      index.js:107-111   CAPTURE_DEFAULTS { seconds: 8, fps: CAPTURE_FPS, gop: 60 }
      index.js:158       this.#ring.push(bytes, { frames, keyframe: true });
      replay-ring.js:149 this.#segments.push({ bytes: payload, frames, keyframe: ... })

  THREE THINGS FALL OUT OF THOSE FOUR LINES.

  1. ONE PUSH PER CAPTURE. capture() pushes the whole 8-second buffer as a single segment.
     With gop 60 at 30 fps that buffer contains roughly four IDRs, and the ring is told
     about NONE of them. Measured: RING_SEGMENTS was 1 on every run.

  2. THEREFORE THE DESIGNS "within one second" IS NOT IMPLEMENTED ON THIS PATH. With one
     segment, #cutFromLastKeyframe() returns the entire buffer -- which is why every
     delivered clip is 206-234 frames, not the ~1 second the document specifies. The cut
     is not landing near the press; it is landing at the head of the whole buffer.

  3. `keyframe: true` IS AN ASSERTION BY THE CALLER, NOT A MEASUREMENT. The ring stores the
     flag it is handed and never inspects the bytes for NAL type 5. Nothing in replay-ring
     can contradict the caller. The document is explicit that the boundary is located
     "by NAL type 5 within the ring range" -- that scan does not exist on this path.
     This is the same rule as the rest of this day applied to my own code: presence is not
     correctness, and a flag somebody set is not a fact about the bytes.

  WHAT THIS DOES AND DOES NOT EXPLAIN ABOUT THE 28 FRAMES. With one push per capture, two
  segments arise only when capture() runs twice without an intervening cut clearing them --
  which is exactly what compose-probe does, since it calls capture() then deliver() then
  captureAndDeliver(). So 2+ segments is reachable in the probe after all. It does NOT
  yet explain why a second segment ever appeared as a 28-frame remainder, and I am not
  claiming it does. That stays open, still 0 reproductions.

  rule: read what the document says before deciding a behaviour is wrong. I nearly logged
  a preference as a finding, and the sentence that refuted me was in the file the whole
  time -- quoted above, in the section about the very clip that failed.

## 2026-10-11T09:22:41Z - the ring is cleared: my drain hypothesis was false, and only ONE capture can be short

I wrote last entry: "if the extraction removes bytes from the ring, the second delivery cuts
what the first left". Read it. It is false.

  MEASURED BY READING, POPULACAO = every mutation of #segments in replay-ring.js:
      L87   #segments = []          constructor only
      L149  push into #segments     push()
      L152-154  while (heldFrames > capacity) { heldFrames -= segments[0].frames; shift() }
  That is the complete set. #cutFromLastKeyframe() concatenates and returns; it does not
  mutate. instantReplay() L200-292 never touches #segments. So a delivery leaves the ring
  exactly as it found it, and eviction only ever removes WHOLE segments from the oldest end,
  never a partial one.

  CONSEQUENCE, and it kills the theory I was about to build on. With two captures the ring
  holds segment A then segment B, both pushed with keyframe:true (index.js:158). The backward
  walk lands on B, the whole of B. There is no remainder for a second delivery to find. 28 is
  NOT reachable from the ring's own arithmetic with segments of 200-240 frames -- there is no
  subtraction that yields 28, because nothing is ever subtracted.

  WHICH NARROWS IT TO ONE THING. The only way a 28-frame cut exists is a segment that was
  PUSHED as 28 frames, which means capture() returned frames: 28 that time. index.js:158
  pushes { frames, keyframe: true } with frames taken from the capture result, so the
  suspect moves from the ring to the encoder: a capture that produced about 28 frames instead
  of about 220.

  AND THAT IS ALSO UNSEEN. keyframe-shape-probe.mjs measured CAPTURED_FRAMES at
  215, 220, 215, 206, 214 across 5 runs (09:17:07Z). The spread is 14 frames. A 28 is not a
  tail of that distribution, it is a different regime. So either the encoder can return a
  near-empty capture and I have never caught it, or 28 came from somewhere I have not looked.

  STATUS: one hypothesis refuted with evidence, the suspect space narrowed from "the ring"
  to "the encoder produced a short capture", and the observation still missing. I have not
  confirmed the encoder theory and am not writing it down as the cause.

  rule: read the mutation sites before theorising about what a data structure hands back. I
  had a tidy theory -- deliver, drain, deliver again, cut the remainder -- and it was wrong
  in the first line of the code I should have opened.

## 2026-10-11T09:27:19Z - 28 was a STILL SCREEN, not a short capture, and the guard was right

Last entry I moved the suspect to the encoder: "the only way a 28-frame cut exists is a
segment pushed as 28 frames, which means capture() returned frames: 28". That is wrong, and
the number that kills it is not 28 at all -- it is that I had been reading 28 as a frame
COUNT when it is a count of DISTINCT frames in the longest contiguous run.

  The chain, now read. index.js:157-159:
      const frames = await countFrames(out);   // REAL frame count, not seconds*fps
      this.#ring.push(bytes, { frames, keyframe: true });
  frames is measured off the file, not derived from seconds*fps, so a capture really can
  come back short -- but that was never what 28 was.

  MEASURED, POPULACAO = 4 captures, WINDOW_UTC 2026-10-11T09:27:19Z, with the probe now
  printing the three numbers that decide the refusal:
      run 1  frames 213  RING_SEGMENTS 1  LONGEST_UNIQUE_RUN 213  EXPECTED_FRAMES 240  sufficient true
      run 2  frames 220  RING_SEGMENTS 1  LONGEST_UNIQUE_RUN 220  EXPECTED_FRAMES 240  sufficient true
      run 3  frames 220  RING_SEGMENTS 1  LONGEST_UNIQUE_RUN 220  EXPECTED_FRAMES 240  sufficient true
      run 4  frames 218  RING_SEGMENTS 1  LONGEST_UNIQUE_RUN 218  EXPECTED_FRAMES 240  sufficient true

  longestUniqueRun EQUALS the frame count in all four: every frame differed from its
  neighbour, because the screen was busy. Against that, the recorded failure said
  "holds 28 contiguous distinct frames". 28 distinct does NOT mean 28 captured -- it means
  the picture stopped changing for over a second. The clip held ~220 frames of which only
  28 consecutive ones were new.

  So the encoder theory is REFUTED: captures land at 213-220 against an expected 240, a
  ~9 percent gdigrab shortfall that is present in EVERY run including the passing ones, and
  nothing about the failing run's frame count needed to be different.

  AND THE PRODUCT WAS CORRECT. frame-accounting.js states why this guard exists -- "a
  transcriber does not care that some frame somewhere was new; it cares whether the picture
  kept changing". A clip of a still desktop cannot stand in for its own clock, so
  replay-ring.js:340 refused it, and the refusal is the guard doing its job on the content
  it was handed.

  WHICH RETRACTS BOTH OF MY OWN THEORIES IN ONE MEASUREMENT: the drain theory (refuted by
  reading the mutation sites) and the short-capture theory (refuted by the equality above).
  What remains is not a defect at all. It is a gate meeting a still screen.

  MY OWN TOOLING FAILED TWICE IN THIS ENTRY. The first run of this measurement exited 1
  with six MethodInvocationExceptions -- my formatter called $th.Substring(0, 20) on a
  value of "?". The six captures ran; the data was destroyed by the reporting line. Second
  attempt fixed the formatter and the data came back. Same lesson as the injection that
  changed bytes but not the claim: the measuring apparatus is part of what can be wrong.

  rule: a number without its UNIT is a number you will eventually misread. 28 was always a
  count of distinct frames and I read it as a count of frames, then spent two hypotheses
  and a whole turn on an encoder that was never involved.

## 2026-10-11T09:31:55Z - two arms prove distinctness drives the number, and the still arm gives 1, NOT 28

Last entry called the still-screen explanation "inferred from a measured equality rather
than reproduced". Right. So I built the two arms, including the arm that would refute me.

  WHAT I COULD NOT DO, stated first. nvenc.js:68 hardwires the input:
      "-f", "gdigrab", "-framerate", String(fps), "-i", source
  so I cannot hand the product a still screen through its own capture path without opening
  a real window on this desktop. What decides the refusal is frame-accounting's
  contentSufficientToCoverClock, and that takes a FILE. So the two arms probe the decision,
  not the capture.

  MEASURED, POPULACAO = 2 clips, both 60 frames at 30 fps, WINDOW_UTC 2026-10-11T09:31:55Z,
  same assessDelivery call, same 30 fps and 2 seconds:
      still.mp4  3 088 B    DELIVERED 60  DISTINCT 1   LONGEST_UNIQUE_RUN 1   SUFFICIENT false
      busy.mp4   256 088 B  DELIVERED 60  DISTINCT 60  LONGEST_UNIQUE_RUN 60  SUFFICIENT true

  THE ARM THAT WAS MEANT TO REFUTE ME DID NOT, and that is the result: distinctness is what
  longestUniqueRun tracks, and a still clip is refused. Had the still arm produced a long
  distinct run, my explanation would have been wrong and I would have said so.

  BUT THE STILL ARM GIVES 1, AND NOT 28. I am not going to round that away. A completely
  frozen picture collapses the run to 1; the recorded failure said 28, which is a screen
  still for roughly a second and then moving again -- a terminal sitting idle between my
  own commands, not a frozen frame. The mechanism is reproduced; the EXACT VALUE IS NOT.
  28 is consistent with the mechanism and not yet explained by it.

  rule: a reproduction that lands on a different number than the failure is a partial
  reproduction, and calling it a reproduction is the same move as the invented citation.
  This one confirms the mechanism and leaves the magnitude open, and both halves belong in
  the report.

## 2026-10-11T09:34:41Z - LONGEST_UNIQUE_RUN 29 on 28 moving frames. The magnitude is reproduced, off by exactly one.

Last entry left the magnitude open: the still arm gave 1, not 28, so I had the mechanism and
not the number. Built the intermediate arm I said I would.

  MEASURED, POPULACAO = 1 clip built to a known shape, WINDOW_UTC 2026-10-11T09:34:41Z:
      2 s of black at 30 fps = 60 identical frames, concatenated with
      0.9333 s of testsrc at 30 fps = 28 changing frames
      -> DELIVERED_FRAMES 88  DISTINCT_FRAMES 29  LONGEST_UNIQUE_RUN 29
         EXPECTED_FRAMES 60  CONTENT_SUFFICIENT false

  29, not 28, and the extra one is not slop: the first frame of the run counts as distinct
  because nothing precedes it to be identical to. So a run of N changing frames preceded by
  stillness reports N+1. The recorded failure said 28, which is 27 changing frames -- about
  0.9 seconds of movement.

  WHICH IS THE WHOLE EXPLANATION, and it took a clip with a KNOWN shape to see it: the
  failing capture was an 8-second desktop recording in which the picture changed for roughly
  0.9 seconds and stood still for the rest. Not a frozen frame -- an idle desktop with one
  brief change. longestUniqueRun 28 fell under the 30-frame one-second clock,
  contentSufficientToCoverClock went false, and replay-ring.js:340 refused. The guard was
  right, the product was right, and nothing was broken.

  WHAT THIS IS AND IS NOT. The magnitude is now reproduced to within one frame, on a clip
  whose shape I chose. That is evidence for the explanation, not a capture of the original
  event -- that recording does not exist anywhere, and 27 frames of movement on this host is
  a number I inferred from a formula, not one I read off the failure. I am recording it as
  reproduced-magnitude and not as reproduced-event.

  rule: when a partial reproduction misses by a small amount, find out WHY it misses before
  you accept the miss. 29 against 28 looked like noise and was actually the first frame of a
  run counting as distinct. The discrepancy was the explanation.

## 2026-10-11T09:37:28Z - I over-claimed. The keyframe assertion is backed by a real measurement, and there is exactly one caller

Last report I named this "a real and demonstrated defect" and said the ring "accepts
keyframe:true from the caller" as an unverified flag. Reading the call site says otherwise,
and I am retracting the strength of the claim rather than restating it.

  MEASURED, POPULACAO = every ring.push call site in the product, comments EXCLUDED:
      index.js:158   this.#ring.push(bytes, { frames, keyframe: true });
  One. Not several. Every other .push( in the tree is a different object -- captions, encoder,
  hotkeys logs, nvenc logs, save-path's own written/blocked lists.

  AND THE ONE CALLER MEASURES BEFORE IT ASSERTS. index.js:145-158:
      147  encoded = this.#encoder.captureAndEncode(out, {...});
      148  const firstIdr = this.#encoder.firstKeyframeSec(out);
      149  if (firstIdr === null || Math.abs(firstIdr) > KEYFRAME_TOLERANCE_SEC) {
      150    throw new ClipNotKeyframed(source, ...);
      156  const bytes = readFileSync(out);
      157  const frames = await countFrames(out);
      158  this.#ring.push(bytes, { frames, keyframe: true });

  firstKeyframeSec (nvenc.js:86-99) is not a lookup in a table:
      execFileSync("ffprobe", ["-v","error","-select_streams","v:0",
        "-skip_frame","nokey","-show_entries","frame=pts_time","-of","csv=p=0", file])
      -> parseKeyframes(raw.split("\n")) -> pts.length === 0 ? null : pts[0]
  ffprobe is asked for the NON-key frames and the first surviving pts_time IS the first
  keyframe, read from the encoded file. An unreadable file, a non-video, or a stream with no
  keyframe all return null, and null is refused at :149. KEYFRAME_TOLERANCE_SEC is
  1/CAPTURE_FPS (nvenc.js:31), one frame at 30 fps.

  So the sequence is: encode, MEASURE the first IDR in the real file, refuse if it is absent
  or more than one frame late, and only then tell the ring keyframe:true. The flag is
  asserted downstream of a measurement with a refusal arm on both sides of it. That is not
  an unverified assertion, and I named it one.

  WHAT SURVIVES, stated narrowly and no wider. replay-ring itself does not re-read the bytes.
  Its flag is whatever it is handed. With one caller that measures first, the system is
  correct today; a SECOND caller added later could assert without measuring and nothing in
  the ring would contradict it. That is a latent risk in the shape of the API, not a defect
  in the running product, and it does not deserve the sentence I gave it last turn.

  rule: "X does not verify" is not the same claim as "nothing verifies". I proved the first
  and reported the second, and the second was the one that mattered to the reader.

## 2026-10-11T09:40:41Z - the ClipNotKeyframed guard has been made to say NO, on a measured 1.0 s against a 0.0333 s tolerance

The guard I read for three turns without ever provoking. index.js:149 is:
    if (firstIdr === null || Math.abs(firstIdr) > KEYFRAME_TOLERANCE_SEC) {
      throw new ClipNotKeyframed(source, ...);
    }

  MEASURED, POPULACAO = 2 clips, both real h264 from h264_nvenc, WINDOW_UTC 2026-10-11T09:40:41Z,
  same firstKeyframeSec call, same literal guard condition re-evaluated in the probe:
      TOLERANCE_SEC 0.03333333333333333   CAPTURE_FPS 30
      good.mp4  584 110 B  FIRST_IDR_SEC 0     GUARD_WOULD_REFUSE false
      bad.mp4   449 229 B  FIRST_IDR_SEC 1     GUARD_WOULD_REFUSE true

  1.0 s is THIRTY TIMES the tolerance, so this is not a marginal boundary: the refusal branch
  is reached by a wide margin, and the accept branch is reached at exactly 0. The guard can
  say NO. That is what three turns of reading had not established.

  THE LIMITS, stated rather than buried. I exercised the guard's DECISION, evaluated from the
  same two values the guard reads -- not the product's capture() throwing. I did not make
  capture() throw, because I could not: the encoder always begins a fresh h264 stream with an
  IDR at pts 0, so the bad arm is unreachable through the product's own capture path without
  hand-crafting the encoded file. The probe re-evaluates index.js:149 literally, so if that
  line changed the printout would disagree with the guard rather than agree with it by
  accident. What is proven is that the condition discriminates; what is not proven is that
  the product has ever hit it.

  rule: a guard read three times and never provoked is three reads, not evidence. The cheap
  way to make a guard say NO is to feed the function the value it exists to reject -- but
  say afterwards whether you made the PRODUCT refuse or only the CONDITION.

## 2026-10-11T09:43:24Z - the ring does not verify by CONTRACT, with a reason written, and it verifies anyway at delivery

I have now called this claim three times and been wrong twice. Reading the contract before
touching anything, as I said I would, closes it properly.

  WHAT push() DECLARES, replay-ring.js:141-143, verbatim:
      `keyframe` says the segment BEGINS on an IDR. The ring does not decide this by
      arithmetic: backToNearestIdr already refused to guess (see its "fewer than one
      GOP" branch), and an encoder is the only thing that knows where its IDRs are.

  So the ring trusting its caller is not an omission I stumbled on. It is a stated design
  decision with a stated reason: a sibling function already refused to guess, and the
  encoder is the only party that knows its own IDR positions. I was describing a DELIBERATE
  contract as a latent risk, which is the same move as describing a guard as unverified.

  AND THERE IS A THIRD CHECK I HAD NOT FOUND. replay-ring.js:278 runs inside instantReplay,
  before the delivery measurement:
      this.#assertStoredClipStartsOnKeyframe(source);
  and :305-306 implements it as:
      #assertStoredClipStartsOnKeyframe(stored) {
        new NvencEncoder().assertStartsOnKeyframe(stored);
      }
  So the STORED clip is verified by the real encoder at delivery time, after it exists on
  disk. That is what closes the "second caller lies" worry: a caller that asserted a
  keyframe it did not have would produce a stored clip whose first keyframe is wrong, and
  :278 would refuse it there. The invariant is checked by measurement at push time by the
  caller AND at delivery time by the ring, through the same encoder.

  THREE CHECKS IN THE CHAIN, all read, all in this file or the one it calls:
      index.js:148   caller measures the capture's first IDR and refuses if late
      replay-ring L141  contract: the ring trusts the caller, on purpose, with a reason
      replay-ring L278  the ring re-verifies the STORED clip with NvencEncoder
  So "unverified assertion" was wrong, and my second-order "latent risk" was smaller than I
  wrote it: even a lying second caller is caught at delivery.

  WHAT I DID NOT DO, which is the honest end of this. I did not exercise :278 either. It is
  read, not provoked, and I am not going to open a third probe to light it up tonight: the
  claim that needs changing is now read from three places instead of two, and the remaining
  work on it is a test, not a design question.

  rule: before calling a contract a defect, read the contract. It may be a decision with a
  reason in it, and the reason may be the answer I was about to argue against.

## 2026-10-11T09:46:46Z - the delivery-time check at :278 is now driven through the product's own ring, on both arms

The last thing left on the keyframe chain, and the one I said was a test rather than a design
question. It is now exercised, not read.

  MEASURED, POPULACAO = 2 arms through ReplayRing.instantReplay(), WINDOW_UTC
  2026-10-11T09:46:46Z. Each arm pushes real encoded bytes with keyframe: true -- which the
  ring BELIEVES, by the contract at :141 -- and then lets the ring cut and save exactly as a
  real delivery would. Nothing was injected and no private field was read.
      good.mp4  584 110 B  first IDR at pts 0
      bad.mp4   449 229 B  first IDR at pts 1.0, built with -copyts so the timestamp survives

    ARM POSITIVE_first_idr_at_0
      OUTCOME delivered
      DETAIL {"name":"0000.mp4","path":"...","verdict":{"path":"...}}
      FILES_LEFT_AFTER 1   0000.mp4
    ARM NEGATIVE_first_idr_at_1
      OUTCOME REFUSED
      DETAIL ClipNotKeyframed: stored clip ...\0000.mp4 does not begin on a keyframe:
             first IDR at pts 1.000000s exceeds to[lerance]
      FILES_LEFT_AFTER 0

  So :278 is real. The ring believed keyframe: true about a clip whose first IDR is a second
  in, the cut was made, the file was written -- and :278 caught it on the stored file and
  refused. FILES_LEFT_AFTER 0 also confirms #discardRefused runs on this path, so a refused
  delivery leaves no 0-byte clip behind, which is the contract instantReplay's own header
  claims at :262-263.

  The claim that would have been refuted: if the negative arm had DELIVERED, :278 would be
  decoration and the three-check chain would be one check wearing three hats. It delivered
  false, so the chain stands on a measurement rather than on three readings.

  The whole keyframe invariant now has: two checks MEASURED (:148's condition on two clips,
  :278 through the real ring) and one contract READ (:141). That is a stronger state than I
  had any reason to claim six turns ago, when I called it a demonstrated defect.

  rule: a check that fires only on the path nobody walks is not a check until something walks
  it. Pushing a segment the ring is told to believe, and watching the delivery refuse it, is
  the shortest distance between "the guard exists" and "the guard works".

## 2026-10-11T09:49:43Z - capture()'s own refusal is measured UNREACHABLE, and gdigrab's title= needs a real window

The last item on this thread. I set out to make capture() hit ClipNotKeyframed and, failing
that, to say honestly why not. It is the second.

  FIRST, THE ROUTE I HOPED FOR. gdigrab takes a window title as a source, which would have
  let me point the product at a still window. Measured, WINDOW_UTC 2026-10-11T09:49:43Z:
      ffmpeg -f gdigrab -framerate 30 -i title=DefinitelyNotAWindow_694214321 -t 1 ...
      [in#0] Can't find window 'DefinitelyNotAWindow_694214321', aborting.
      [in#0] Error opening input: I/O error      exit non-zero, no file created
  So title= is a real gdigrab source, but it needs a window that EXISTS. Producing one means
  opening a window on the owner's desktop and leaving it there for the capture to see. That
  is a visible change to his screen, it is not mine to make for a test, and I am not going to
  buy one measurement by rearranging his desktop. Declared instead of forced.

  SECOND, THE INVIANT MEASURED. The guard at index.js:149 refuses when firstIdr is null or
  beyond KEYFRAME_TOLERANCE_SEC, which nvenc.js:31 sets to 1/CAPTURE_FPS = 0.0333 s. So the
  branch is reachable only if a capture ever produces a first keyframe later than 33 ms.
  Printed FIRST_IDR_SEC on 4 real captures:
      run 1  firstIdr 0  frames 212  segs 1  sufficient true
      run 2  firstIdr 0  frames 216  segs 1  sufficient true
      run 3  firstIdr 0  frames 219  segs 1  sufficient true
      run 4  firstIdr 0  frames 226  segs 1  sufficient true
  4 of 4 at exactly 0, against a tolerance of 0.0333. An h264 encoder starts a fresh stream
  with an IDR at pts 0, so this is expected -- but it is now a MEASUREMENT, and I have said
  so, instead of "unreachable" being something I asserted.

  SO THE HONEST END STATE. capture()'s own refusal branch is measured unreachable through the
  product's capture path on this host, and reachable in principle only if the encoder ever
  started mid-GOP or a capture began without an IDR. The OTHER two checks in the chain are
  measured firing (:148's condition on two clips, :278 through the real ring). A branch that
  no run reaches is not a defect and not dead code; it is insurance, and the thing to record
  is WHERE its coverage comes from, which now is the other two checks rather than itself.

  rule: "I could not make it fire" and "it cannot fire" are different sentences and only one
  of them is a measurement. I have the second for the branch and the first for the product,
  and the ledger now says which is which.

## 2026-10-11T09:52:50Z - the design documents say nothing about a still desktop. The guard's reason is a transcriber's, and the refusal is unspecified.

Checked the explanation against the documents instead of against my own reasoning, which is
what I should have done two turns before I had two theories to throw away.

  MEASURED, POPULACAO = the 8 SHADOWPLAY-*.md product documents in I:\!manager\runs, grepped
  for static | still desktop | idle | frozen | no motion | unchanged | identical frame |
  distinct | transcriber | caption, WINDOW_UTC 2026-10-11T09:52:50Z.
      SHADOWPLAY-CAPTURE-PIPELINE.md:47-53 is the only substantive hit and it is about
      desktop DUPLICATION: desktop switches, DWM toggles, and the Ctrl+Alt+Del secure desktop
      where "a recorder must therefore pause, not spin". Nothing anywhere in the set
      describes what the product should do when the captured picture does not change.

  So the still-screen case is UNSPECIFIED. Not wrong, not specified: absent. And the product
  has a behaviour there -- replay-ring.js:340 refuses -- whose stated justification lives
  only in a code comment in frame-accounting.js, and that justification is a transcriber's:
  "a transcriber does not care that some frame somewhere was new; it cares whether the picture
  kept changing". That is the reasoning of the captions and highlights path being applied to
  instant replay, where the user pressed a key asking for the last few seconds of their
  screen and gets nothing back if they happened to be idle.

  I am not calling that a defect, because I have no specification saying it should deliver.
  I am recording that the specification does not exist, that the behaviour is real, and that
  the reason on record belongs to a different feature. Whether instant replay should refuse a
  still desktop is a PRODUCT DECISION and it belongs to the owner, not to me.

  THIS THREAD, END TO END. It began with me calling a working guard a defect. It went through
  a fabricated quotation of a message that does not exist, two refuted theories of mine
  (drain, short capture), one reproduction that landed a frame off, and a fourth correction
  after reading the contract. What survived: three keyframe checks with two MEASURED and one
  contract READ, a capture refusal branch measured unreachable on this host, and an
  explanation of the 28 frames that is reproduced in magnitude and now shown to rest on a
  case the design never addresses.

  rule: an unspecified case with real behaviour is not a bug report and not a green light.
  It is a question for whoever owns the product, written down where the answer will be found.

## 2026-10-11T09:53:41Z - POPULATION was 9, not 8, and the "nothing in any of them" claim was never enumerated until now

The owner caught this: the previous report stated a population and a window for the grep but
carried the DOCUMENT COUNT from an older window. Re-measured, and the claim was wrong in the
number and unbacked in its absence.

  MEASURED, WINDOW_UTC 2026-10-11T09:53:32Z .. 09:53:41Z, root I:\!manager\runs:
      POPULATION_PROD    9 documents, 142 277 B   (*-REVIEW.md excluded)
      POPULATION_REVIEWS 8 documents, 301 984 B
  The 9 product documents are AUDIO, BROADCAST-OBS, CAPTURE-PIPELINE, HIGHLIGHTS-AI,
  INSTANT-REPLAY, INTEGRATION-PLAN, OVERLAY-HOTKEYS, SCREENSHOTS-RECORDINGS and
  SHADOWPLAY-QUOTATION-ADJUDICATION-2026-10-10.md. I said 8. The ninth is an adjudication
  file I never counted.

  THE COUNT WAS STALE, NOT WRONG AT THE TIME. An earlier window measured 8 documents at
  91 966 B. Today the same directory holds 9 at 142 277 B. Both numbers are true of their own
  windows; I reported the older one against a newer measurement. 50 311 B of difference is
  documents edited since, and one document added.

  AND THE ABSENCE CLAIM WAS NOT ENUMERATED. I wrote "nothing, in any of the 8, says what the
  product should do when the captured picture does not change". I had read the substantive
  hits in one file and generalised. Counted per file today, same WINDOW:
      AUDIO 1 · BROADCAST-OBS 1 · CAPTURE-PIPELINE 1 · HIGHLIGHTS-AI 1 · INSTANT-REPLAY 4
      INTEGRATION-PLAN 1 · OVERLAY-HOTKEYS 3 · SCREENSHOTS-RECORDINGS 2
      QUOTATION-ADJUDICATION 0        TOTAL 14
  Read one by one at 09:53:41Z. All 14 are incidental word usage -- "unchanged" meaning
  unaffected, "distinct" meaning separate, "frozen" describing a corrupt first second, "idle"
  naming a state in a screenshot state machine. NOT ONE of them addresses the picture failing
  to change. So the conclusion survives, and it survives on enumeration rather than on a
  sample I liked.

  rule: a population you counted in an earlier window is not a population you measured now,
  even when the directory is the same. Count it in the window of the claim, or say which
  window the count belongs to.

## 2026-10-11T09:55:28Z - the fleet, recounted in THIS window, and a vocabulary finding

The owner corrected me for carrying a count from an older window, so: recounted now.

  MEASURED, WINDOW_UTC 2026-10-11T09:55:27Z, store read mode=ro, never copied:
      POPULATION_ALL_SESSIONS 5907
      MINE_TOTAL (parent_session_id = mvs_a00662bff55242cb9b56c0f1165bdad7)  1107
      MINE_BY_STATUS   aborted 731 · error 20 · idle 337 · interrupted 19
      GLOBAL_BY_STATUS aborted 1121 · error 681 · idle 3747 · interrupted 357 · started 1
      GLOBAL_RUNNING (status in running|queued)   0

  So 1107 is confirmed, and it now has a window instead of being an inherited number. And a
  vocabulary finding I should have stated long ago: THE STORE HAS NO "running" STATUS. The
  values are aborted, error, idle, interrupted, started. Every report I have written said
  "0 running" as though there were a status to count; what I was counting was the absence of
  "started", which is 1 globally and 0 under my parent id. The mandate asks for 15-50
  running; the field that would express that does not exist in this store.

  AND THE PRODUCT DECISION IS NOW WRITTEN WHERE THE OWNER FINDS IT, not left inside a report:
  app/shadowplay/state/DECISION-instant-replay-still-desktop.md. Four options, what each
  costs, the measured evidence with its population and window, and the explicit statement
  that the guard's only justification belongs to the captions path.

  rule: re-count in the window of the claim, and check that the field you are counting exists.

## 2026-10-11T09:58:41Z - the whole status vocabulary, and what the mandate would have to ask to be measurable

  MEASURED, WINDOW_UTC 2026-10-11T09:58:41Z, POPULATION = every row in
  local_runtime_sessions, store mode=ro:
      idle 3747 · aborted 1121 · error 681 · interrupted 357 · started 1 · TOTAL 5907
      session_type branch 5903 root 4 · session_kind task 3612 conversation 2160 cron 135
      archived 5897 no / 10 yes · runtime pi-agent 5907 · purpose_kind EMPTY on all 5907

  Five status values, and none of them is running, queued or succeeded. The mandate's aside
  "'succeeded' is not 'running'" is satisfied trivially here: there is no succeeded to
  confuse it with. What I have printed as "0 running" is the started count.

  LIVENESS BY RECENCY, the only thing the store can express, same window:
      last 5 / 15 / 60 / 360 min   global 1, mine 0
      MAX_UPDATED_AT_MS 2026-10-11T09:58:28Z -- which is this session
  So the proxy works and it names exactly one live thing: me. There are 0 subagents running
  under any reading this runtime offers, and now that is a measurement with a window rather
  than an absence of measurement.

  purpose_kind is EMPTY on all 5907 rows. Worth recording because a rule I hold is keyed on
  purpose; in THIS store that column carries nothing, so such a rule would match nothing.

  rule: before counting a thing, look up the field it lives in. I reported "running" for
  several turns against a column that has five values and none of them is that.

## 2026-10-11T10:01:29Z - assessDelivery has ONE product call site, and there is a duplicated module nobody has measured

  MEASURED, POPULATION = every .js under app/shadowplay, comments excluded,
  WINDOW_UTC 2026-10-11T10:01:29Z:
      defined once  frame-accounting.js:322
      called        replay-ring.js:330   verdict = await assessDelivery(source, fps, seconds)
      called        replay-ring.CURRENT.js:275   the same line, in a COPY of the module
      imported      replay-ring.js:9 and replay-ring.CURRENT.js:9

  So the gate has exactly one product consumer, and the second call site is the duplicate.
  Nothing in captions or highlights calls it, despite the reasoning inside frame-accounting
  being a transcriber's. A gate written for one consumer reached exactly one consumer, and
  it is not the consumer the comment argues for.

  THE DUPLICATION IS ITS OWN FINDING. replay-ring.CURRENT.js duplicates replay-ring.js. I
  have NOT measured which one the product loads and I have not touched either. It is
  recorded because a duplicated module means an edit to one of them may not reach the
  running product, and that is the same shape as the clipsDir/dir mistake from earlier
  today: two things that look like the thing, and only one of which is it.

  Written for the owner as state/DECISION-assessDelivery-scope.md, with three positions and
  what each costs. Not decided here.

  rule: count the call sites before deciding what a guard is protecting. One caller makes
  "a transcriber's rule" a rule with a single non-transcriber user, which is a design fact
  rather than a style question.

## 2026-10-11T10:06:13Z - retracted: there is no duplicated module in the product path. I printed a name and read it as a location.

  I reported last entry that replay-ring.CURRENT.js duplicated replay-ring.js and that an
  edit to the wrong copy might not reach the running product. The second half was unfounded
  and I put it in a commit message and a decision file.

  HOW IT HAPPENED, exactly. The measurement ran Select-String over a RECURSIVE *.js search
  and printed $_.Filename -- the NAME, never the directory. A file inside _fix9/ printed
  exactly like a sibling in the product directory. I read a name as a location. POPULATION
  was never wrong; the column I displayed was.

  MEASURED, WINDOW_UTC 2026-10-11T10:06:13Z, POPULATION = every .js under app/shadowplay:
      replay-ring.js                19 458 B  sha E8499478C754D8F3  mtime 2026-10-11T01:20:32Z
      _fix9/replay-ring.CURRENT.js  16 145 B  sha F8FBF11319942417  mtime 2026-10-10T19:34:43Z
      *.CURRENT.js in the tree: 1, inside _fix9, a folder of 6 files
      index.js:58 and :76 both import from "./replay-ring.js"; index.js never mentions _fix

  So the product loads replay-ring.js, the file I edited today. The _fix9 copy is a stale
  snapshot, a day older and 3 313 B smaller, not on the product path. Nothing I changed in
  the ring today failed to reach the product. The alarm is withdrawn.

  THE STALE COPY IS STILL A REAL THING, smaller than the alarm. A snapshot in a fix folder
  can be edited by someone who thinks it is live. It is recorded, not acted on, and nothing
  was deleted -- arquivar, nunca apagar.

  rule: a filename is not a location. If a claim depends on WHERE a file is, print the path;
  a name plus a directory assumption is how a fix folder becomes a production incident in a
  report.
