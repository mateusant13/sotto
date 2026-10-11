# Receipt — 'node _main/join-harness.js' RED, adjudicated: the HARNESS was stale (2026-10-11)

Lane: SottoJoinHarness. Files written by this lane: '`_main/join-harness.js`' (re-baselined) and
this receipt. '`app/panel/caption-formulation.js`' and '`app/panel/panel.js`' were READ, never
written — the module is NOT broken and was NOT touched (the brief allows that edit only if the
evidence proves the MODULE wrong; `2 proves the opposite).

Root: '`H:\sotto`'. No shell/WebView2/worker launch (owner's order, verbatim in '`AGENTS.md`'). No
git write; git was used READ-ONLY ('`git show`', '`git log`', '`git diff`'). TMPDIR='`I:\cc-tmp`'.

---

## 1. The verdict, both colours

### BEFORE (the file as it was: 10 472 B, sha256 '`3B4C96CE7F45DC23…`', mtime 2026-10-07T08:26:59.147Z)

    node _main/join-harness.js
    FAIL arm1 the whole burst is on screen as one line  got=[{"w":"w0","a":0,"b":0.56},{"w":"w1","a":0.56,"b":1.12}, … 9 more tokens … {"w":"w10","a":5.6000000000000005,"b":6.16}] want="w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11"
    FAIL arm2 the next fragment starts the next line  got=[] want="again"
    FAIL arm3 the words are still one line  got=[{"w":"this","a":0,"b":0.56}] want="this is"
    FAIL arm7 first reading is provisional  got=[{"w":"going","a":0,"b":0.56},{"w":"along","a":0.56,"b":1.12}] want="going along slush"
    FAIL arm7 the revision did not duplicate the old words  got=[] want="going along slush country"
    FAIL arm7 the second revision replaced, not appended  got=[] want="going along slushy country"
    REAL JOIN-HARNESS: 6 FAILED  impl=H:\sotto\app\panel\caption-formulation.js
    rc=1

(The arm-1 '`got=[…]`' is elided at 3 of 11 tokens with an explicit marker; the other five FAIL lines
are verbatim. The other 21 checks PASSED in the same run, every committed-path arm among them —
'`arm6 the stopped stream still landed its words got=["G gen s."]`',
'`arm7 the committed line has no garbage got="Going along slushy country."`'.)

### AFTER (this file: 24 365 B, sha256 '`5E66FF355394B9ADB7DCEC3A6216DA4CC50F4C463DE96BAADB41AE63BE08AE7F`')

    node _main/join-harness.js
    arm1 the engine reported the line once per fragment  got=12
    REAL JOIN-HARNESS: PASS (11 arms)  impl=H:\sotto\app\panel\caption-formulation.js
    rc=0        (41 checks, 0 FAILED)

### BOTH COLOURS OF THE GATE IN ONE COMMAND

    node _main/join-harness.js --neg-arm
    ── NEG-ARM (contract reverted in COPIES under I:\cc-tmp) ──
      N0 control  real module + real caller  rc=0  failing=0  (must be GREEN)
      M1 module call reverted to onProvisional(visibleText(), true)
        copy   I:\cc-tmp\join-harness-neg-arm-33232\caption-formulation-call-reverted.js  40330 B  sha256=6853380D462673BB879740D45F5990EEF611A739FB8EE7BFF05170AF0B2EB4D1
        child  rc=1  failing=11  expected-named=11/11
        child FAILING CHECKS: arm1 the whole burst is on screen as one line | arm2 the next fragment starts the next line | arm3 the words are still one line | arm7 first reading is provisional | arm7 the revision did not duplicate the old words | arm7 the second revision replaced, not appended | arm11 the callback carries two token arrays | arm11 the callback never left the array path | arm11 the callback union equals visible() | arm11 every token carries w a b | arm11 the module still calls onProvisional(committed, provisional)
      M2 caller wiring reverted to the string form
        copy   I:\cc-tmp\join-harness-neg-arm-33232\panel-caller-reverted.js  138415 B  sha256=20F0093E3E0E79A16CF4E46E04353B580568602769670E1B858E16AB2BC92824
        child  rc=1  failing=2  expected-named=2/2
        child FAILING CHECKS: arm11 the caller still passes both arrays to renderProvisional | arm11 the caller still paints only arrays
      NEG-ARM: PASS  control-green=true  M1=RED-as-required  M2=RED-as-required
    rc=0

The mutant directory name carries the pid ('`…-33232`' this run, '`…-35388`' an earlier one); the
mutant BYTES were identical across those runs, and the sha256 above are of those bytes.

---

## 2. Adjudication, ON THE BYTES: the harness's expectation was stale (case (a))

The six failing checks were EXACTLY the six that read the harness's provisional stub; nothing else
failed, and every committed-path arm passed. That stub was

    onProvisional: (text) => { provisionalText = text; }        // OLD harness, line 52

— it captured ONE argument and expected a joined STRING. The shipped contract, read from the bytes
on disk in THIS revision (fresh '`grep`' this session, not remembered):

    app/panel/caption-formulation.js:737| onProvisional(committed, provisional);
    app/panel/panel.js:676|              onProvisional: (committed, provisional) => renderProvisional(committed, provisional, key),
    app/panel/panel.js:758|  const confWords = Array.isArray(committed) ? committed.map(t => t.w) : [];
    app/panel/panel.js:759|  const provWords = Array.isArray(provisional) ? provisional.map(t => t.w) : [];

* The engine publishes TWO TOKEN ARRAYS ('`{w,a,b}`'), not a string — module '`:737`'.
* Its ONLY live caller consumes exactly those two arrays — '`panel.js:676`' — and its renderer
  REFUSES anything that is not an array ('`Array.isArray(…) ? … : []`', '`panel.js:758-759`'). A
  string first argument therefore paints ZERO words on the row. The harness's expectation described
  a renderer that no longer exists.
* Population, fresh '`grep`' this session: '`app/panel`' holds exactly TWO '`onProvisional`' code
  sites — module '`:279`' (the option) and '`:737`' (the call) — plus the caller's wiring at
  '`panel.js:676`' and two comment mentions ('`:658`', '`:668`'). '`createEngine`' under '`app/`' has
  exactly ONE live call site, '`panel.js:644`'; every other hit is under the DEAD
  '`app/_legacy-electron/`' tree (panel.html loads '`app/panel/*`' only).

### Where the stale expectation came from — the drift is ONE COMMIT (read-only git)

| revision | module's call | harness's stub | colour of this gate |
|---|---|---|---|
| '`5ffeefc`' 2026-10-06, '`app/electron/caption-formulation.js:344`' (16 802 B) | '`onProvisional(visibleText(), provisional.length > 0);`' — a STRING first argument | '`_main/join-harness.js`' 10 478 B, sha '`7885ED4C5D2A3BF85AD1DAD38FC3B82AA25C8942F6E0AB73C3B3F932413BB913`', stub '`(text)`' at '`:52`' | **GREEN**, and the green run is pasted in '`docs/caption-formulation-20261006.md:111-145`' ('`PASS arm1 the whole burst is on screen as one line got="w0 … w11"`', '`REAL JOIN-HARNESS: PASS (10 arms)`', rc=0). The 10 478 B / '`7885ED4C…`' pin also appears in '`docs/audit/tracked-durability.md:227`' |
| '`a3c288f`' 2026-10-07 10:34:39 -03 | '`app/panel/caption-formulation.js:649`' (742 lines added): '`onProvisional(committed, provisional);`' | '`_main/join-harness.js`' 10 472 B, sha '`3B4C96CE…`' — the ONLY change '`git diff 5ffeefc a3c288f -- _main/join-harness.js`' shows is the module PATH ('`app/electron`' → '`app/panel`', 4 lines); the stub at '`:52`' stays '`(text)`' | **RED from this commit on** (and '`git log -- _main/join-harness.js`' shows no later content change) — nobody re-ran it until 2026-10-11 |
| same commit, caller | '`app/panel/panel.js:400`' '`onProvisional: (committed, provisional) => renderProvisional(committed, provisional)`' with '`renderProvisional(committed, provisional)`' at '`:453`' | — | the caller moved to the arrays WITH the module; the harness did not |
| '`b121cce`' 2026-10-11 18:52:58 -03 | unchanged | unchanged | the caller's wiring gains the per-source '`key`' argument and '`renderProvisional`' gains the '`Array.isArray`' coercion — so from here a string argument paints NOTHING, and the stale stub was reading a contract the panel now actively refuses |
| 2026-10-11 | — | — | lane SottoDeadControls re-runs it: '`6 FAILED`' ('`_main/receipt-20261011-dead-controls.md:239-247`', which explicitly leaves "whether the stale expectation is the harness's or the module's" OPEN). This receipt closes that question |

### What the stale stub structurally COULD NOT see — the clincher

The engine's own comment at '`caption-formulation.js:622-632`' records that after a RE-READ "the
whole line sits in '`provisional`' (nothing has been confirmed twice yet)". So '`committed`' — the
single argument the old stub captured — is EMPTY or short exactly when the provisional line is
interesting. That is why '`arm3`' was shown ONE word of two ('`got=[{"w":"this",…}]`'), '`arm1`'
ELEVEN tokens of twelve, and '`arm2`' an EMPTY array for a buffer whose one word was entirely
provisional. That signature is a stale reader, not a broken engine: a broken engine fails the
committed arms too, and they all passed.

### Why case (b) — "the module really breaks the provisional path" — is REFUTED

If the module were the broken side, the repair would have to make the shipped panel paint what it
sends. It cannot: '`panel.js:758-759`' coerces a non-array to '`[]`', so the change that "fixed" the
harness would be a change to a panel that never asked for a string. The two-array shape is also what
the module's own public accessor asserts ('`visible()`', '`caption-formulation.js:799-800`' — "the
oracle reads this instead of the DOM"). Arm 11 measures that agreement mechanically:
'`arm11 the callback union equals visible() got="contract pin"`' — the words the callback hands the
panel ARE the string '`visible()`' returns. Independent corroboration: the two sibling oracles that
drive the SAME callback ('`_main/redux-live-contract-oracle.js:205`', and the panel replay in
'`_main/panel-row-identity-oracle.js`') have consumed '`(committed, provisional)`' for as long as this
lane can see and are GREEN today (`5).

**Verdict: (a). The harness's expected value was written from an older revision of the module; it is
re-baselined to the shipped contract, with a check that reads that contract and can fail.**

---

## 3. What changed in '`_main/join-harness.js`'

* The stub READS WHAT THE PANEL READS: it takes the two arrays and derives the painted text with
  '`panel.js:758-759`' own coercion (copied in behaviour, not invented), recording the argument kinds,
  the raw arrays and any call that left the array path.
* ARM 11 (NEW, 7 checks) PINS THE CONTRACT ON BOTH SIDES — runtime shape
  ('`arm11 the callback carries two token arrays`', '`… the callback never left the array path`',
  '`… the callback union equals visible()`', '`… every token carries w a b`') and the BYTES of both
  halves: '`arm11 the module still calls onProvisional(committed, provisional)`' counts that call in
  the loaded implementation, while '`arm11 the caller still passes both arrays to renderProvisional`'
  and '`arm11 the caller still paints only arrays`' re-read the caller's wiring and its
  '`Array.isArray`' guards from disk. Either half drifting alone is now a NAMED FAIL. The caller half
  matters because '`renderProvisional`' is defensive: a caller that stopped reading arrays would paint
  NOTHING while the module stayed correct, and no module-side instrument could see it.
* '`--neg-arm`' (NEW) builds the two revert mutants in COPIES under '`%TEMP%`' (never in the shipped
  files), runs the same arm list against each in a child process
  ('`spawnSync(process.execPath, [__filename, --impl=…, --panel=…], {windowsHide:true})`') and requires
  rc=1 WITH the expected check names. A control child (real module + real caller) must be GREEN in the
  same invocation, so the RED is attributable to the mutant rather than to the plumbing.
* '`--panel=<path>`' (NEW, defaults to '`app/panel/panel.js`') is the seam that makes the caller mutant
  possible. '`--impl=`' keeps its old meaning.
* Arms 1-10 are UNCHANGED and keep their names; the only addition among them is
  '`arm1 the engine reported the line once per fragment`' (12 of 12), which reads the counter the stub
  already kept instead of leaving it unread.
* A '`FAILING CHECKS (n): …`' line is printed whenever the gate is RED — it now names its failures
  instead of only counting them (that is the line '`--neg-arm`' parses).

---

## 4. Pins — every artefact, measured (node '`fs.statSync`' + '`crypto.createHash("sha256")`')

| artefact | bytes | sha256 | mtime (as measured) |
|---|---|---|---|
| '`_main/join-harness.js`' BEFORE | 10 472 | '`3B4C96CE7F45DC23752BEBB64504CD927F3DAF49D6DF2540AC5146F3E756A854`' | 2026-10-07T08:26:59.147Z |
| '`_main/join-harness.js`' AFTER | 24 365 | '`5E66FF355394B9ADB7DCEC3A6216DA4CC50F4C463DE96BAADB41AE63BE08AE7F`' | 2026-10-11T22:58:07.527Z |
| '`app/panel/caption-formulation.js`' (READ ONLY — unchanged) | 40 333 | '`6EB5FB8AF421FA26CDAEEF4CF6F37D49F3D0D831B16C9A1C787A9B4816159072`' | 2026-10-11T21:25:47.676Z |
| '`app/panel/panel.js`' (READ ONLY — not written by this lane; dirty vs HEAD by another lane — see below) | 138 379 | '`A14C0A96E69F759E2584BA0DB1B781B36E3F97DE00AA7989E3B9F8804ABCFC7F`' | 2026-10-11T22:53:57.474Z |
| '`_main/control/caption-formulation-pre.js`' (READ ONLY) | 4 210 | '`719A68F7B9FCB6260E0B8C6E8AB71BE171DB37BB46087EC8585F753309B9A440`' | 2026-10-06T06:02:07.759Z |
| mutant M1 (copy under '`I:\cc-tmp`') | 40 330 | '`6853380D462673BB879740D45F5990EEF611A739FB8EE7BFF05170AF0B2EB4D1`' | written 2026-10-11 ~22:58Z |
| mutant M2 (copy under '`I:\cc-tmp`') | 138 415 | '`20F0093E3E0E79A16CF4E46E04353B580568602769670E1B858E16AB2BC92824`' | written 2026-10-11 ~22:58Z |
| '`I:\cc-tmp\join-harness-HEAD.js`' (the PRE-change harness, '`git show HEAD:_main/join-harness.js`', used for the before-colour re-runs) | 10 472 | '`3B4C96CE7F45DC23752BEBB64504CD927F3DAF49D6DF2540AC5146F3E756A854`' (byte-identical to the first row, re-hashed) | written 2026-10-11 ~22:59Z |
| this receipt | see `8 (prefix pin) | see `8 | see `8 |

The module and the caller were NOT modified BY THIS LANE: their pins are the revision every run in
this receipt read. Note the working tree has BOTH `app/panel/panel.js` and `_main/join-harness.js`
MODIFIED against HEAD `4d7766c` (read-only `git status --porcelain`: ` M _main/join-harness.js`,
` M app/panel/panel.js`) — `panel.js` was made dirty by ANOTHER lane before this lane started, and
that dirty revision, sha `A14C0A96…`, is exactly what arm 11 s caller checks read. HEAD s copy of
`panel.js` was not the subject of any run here. If another lane moves '`panel.js`', arm 11's caller checks go RED BY DESIGN (`3) — intended
behaviour, not a defect.

---

## 5. Sibling gates, re-run AFTER the change (corroboration; the module was not touched)

    node _main/redux-live-contract-oracle.js
      CONTROL-VERDICT PASS  armB(wrong start)-RED=true armC(shared start)-RED=true armD(per source)-GREEN=true
      VERDICT PASS - 8/8 shipped-contract arm(s) held
    rc=0

    node _main/panel-row-identity-oracle.js
      AS-SHIPPED COLOURS: CHK-A=GREEN CHK-B=GREEN CHK-C=GREEN CHK-C2=GREEN CHK-D=GREEN CHK-E=GREEN CHK-F=GREEN
      VERDICT: PASS
    rc=0

    py -3 _main/canonical-producer-oracle.py
      SUMMARY: 47/47 checks green; failed=[]
      VERDICT: PASS
    rc=0

---

## 6. What this does NOT prove — NOT MEASURED

* **What the WebView2 panel actually PAINTS.** "A string first argument paints zero words" is a
  READING of the '`Array.isArray`' guards at '`panel.js:758-759`', not a measured paint. No launch, no
  '`--dump-dom`', no jsdom render of '`panel.js`' — the owner's order forbids opening the shell, and
  '`_main\_audit-verify-all.cmd`' was NOT run.
* **A live stream.** Nothing here observes a real '`proc:<pid>`' worker stream reaching the engine's
  provisional path end to end; every fragment in this receipt is the harness's own.
* **Pixels.** The typewriter reveal and the per-word ramp that the two arrays feed ('`paintChars`',
  '`paintWords`') were not measured visually or in a DOM.
* **The intermediate revisions.** Only HEAD's harness bytes were replayed against today's module; the
  ages of the RED between '`a3c288f`' and today are inferred from '`git log`' (no content change), NOT
  from re-running each revision.
* The two mutant copies under '`I:\cc-tmp`' are left on disk for inspection; nothing loads them, and
  no cleanup is claimed.

---

## 7. OPEN gaps this lane found and did NOT repair (outside its write scope)

1. **'`_main/caption-renderer-integration.js`' carries the SAME stale stub and is RED.** Measured:
   '`node _main/caption-renderer-integration.js`' → '`rc=1`', '`[FAIL] 1. the provisional line GROWS
   (a prefix chain, no duplicate render)`', '`caption-renderer-integration: 6 PASS / 1 FAIL`'. Its
   '`onProvisional: (text, isProvisional)`' at '`:60`' is the pre-change convention (its own "control
   provisional" dump prints '`{w,a,b}`' objects). Same diagnosis, different file — NOT repaired here.
2. **The negative CONTROL was already RED before this change.** Measured with the PRE-change harness
   (HEAD bytes) against '`_main/control/caption-formulation-pre.js`':
   '`CONTROL JOIN-HARNESS: 24 FAILED`', rc=1 — and that is exactly the number the doc itself recorded
   on 2026-10-06 ('`docs/caption-formulation-20261006.md:201`' "CONTROL JOIN-HARNESS: 24 FAILED" and
   '`:205`' "rc=1, 24 arms RED"). So the control has never separated "the mutant moved it" from "it
   was already red" for the arms beyond the six it was built to reproduce; after this change the same
   run reports '`CONTROL JOIN-HARNESS: 30 FAILED`' — +7 checks the panel-faithful stub now sees
   ('`arm3 the words are still one line`', '`arm7 first reading is provisional`', the four arm-11
   runtime checks and '`arm11 the module still calls onProvisional(committed, provisional)`') and −1
   ('`arm7 no duplicated token`', which the old stub caught on the control's real duplication and the
   new stub cannot see on a module that paints nothing). Re-baselining the control is a separate job.
3. **Arm 11's caller checks pin '`panel.js`' BYTES.** A coordinated change of module + caller will turn
   them RED until a human re-baselines this harness. That is the intended "a gate must be able to say
   NO" behaviour, named here so it is not discovered as a surprise.

---

## 8. Self-pin

The bytes ABOVE this heading are the measured artefact; the hash covers exactly them (no part of
this section is inside it), and it is re-verifiable by truncating this file at the heading:

* prefix bytes = 18164
* prefix sha256 = F9B11B9A473387E9D7365213377079CBE87FAACCE26EF0523FECAD30A960F091
* mtime of the complete file = see the lane report (a self-referential mtime cannot be embedded)

The sha256 of the COMPLETE file cannot be embedded in itself — any line quoting it changes it — so
the complete-file pin (bytes / sha256 / mtime) is quoted in this lane report, the same convention
this repo already uses for receipts that describe themselves. Nothing above this heading was
rewritten after the measurement: the prefix pin was computed from the exact bytes now on disk.
