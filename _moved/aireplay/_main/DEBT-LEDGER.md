# DEBT LEDGER — every item I declared "not done", and what closed it

**Why this file exists.** Three times the P0 ratchet re-raised items I had already closed,
because it compares my prose, not the repository. A promise kept only in a chat turn is a
promise with no state. This is the state.

Rules for this ledger, which are the rules that were missing:

1. An item may only be marked `CLOSED` with a **file, a commit, or a measurement** attached.
   "Decided not to" is not a closure; it is a closure with a receipt.
2. An item may only be marked `VOID` with a **measurement that removed its precondition**.
3. Anything else stays `OPEN`, and an OPEN item past its second report is `ESCALATED`.
4. Every lane that lands MUST have a reviewer row here before it counts as done.

---

## Closed

| id | item | resolution | proof |
|---|---|---|---|
| D-RESTART | "Não reiniciei a sessão" — the owner's restart path, deferred | **VOID** — the restart was conditional on the wake being broken. It was not broken: the wake loop resumed the conversation at 12:16:14, 12:22:17, 12:31:23 and 12:39:19, POP=4 events, WINDOW 12:15→12:39. Restarting would destroy a working mechanism and this conversation to fix nothing. The owner's *procedure* is preserved anyway for a future wake that needs it. | `_main/RESTART-RUNBOOK.md`, commit `4ce26c7`; "deliver a wake to an IDLE session within 3 min" is OPEN below as the real requirement |
| D-QUEUE-PROOF | "Não observei a entrega da fila" | **CLOSED, and now the conclusion is right too.** Delivery exists — narrow census `queue_item_ids_json IS NOT NULL AND claim_source='api'`: **POP=80**, **80/80** carry a `role='user'` row, **0 counter-examples**, WINDOW 13:27:32->13:28:38 BRT (broad census `queue_item_ids_json IS NOT NULL`: 583 -> 585 -> 608 -> **618**, WINDOW 13:27:32->13:38:10 — the count MOVES, the ratio does not). **The retraction filed here was itself false and is retired:** the 12:40:54 turn is a **proven queue delivery**, POPULATION=2 resolved turns, WINDOW 12:40:54->12:55:18 BRT. | `receipts/receipt-23-cron-woke-this-session.md` §1/§2/§6; read-only query of `runtime-state.sqlite` 13:27 BRT: `queue_item_ids_json=["queue_4d760084-bc97-4edf-bef4-6dd6399a2556"]`, `claim_source='api'`, `status='completed'` |
| D-REMEASURE | "Não re-mediquei nada neste turno" | **CLOSED** — re-measured at 12:45:46 with populations stated, and again at 12:51:19 verifying the retraction commit and runbook exist on disk rather than asserting it. | two census runs, WINDOW 12:45:46 and 12:51:19 |
| D-L3-REVIEW | "Não despachei reviewer para a L3" | **CLOSED** — verifier dispatched as `bg_1d034503`. | task list at dispatch time |
| D-HEADLINE | my claim that the cron woke this session | **RETRACTED — and the retraction's stated evidence is RETIRED as false.** The text match never proved a mechanism. L16's counter-claim (`queue_item_ids_json = NULL`) is **false**: that turn names its queue item, `claim_source='api'`. **What survives:** the turn was a **queue delivery** (POP=2, WINDOW 12:40:54->12:55:18 BRT). **What does not:** that the *cron* planted it — `queue_4d760084` was hand-injected (`receipt-27` §2), and every `WAKE delivered rc=0` names the owner's session `mvs_a00662…` (POP=9, WINDOW 12:56:30->13:30:10), never this one. **Headline stays retracted; the reason it was retracted was wrong.** | `receipts/receipt-23-cron-woke-this-session.md` §1/§6, `_main/heartbeat.log`, `receipts/receipt-27-queue-delivery-latency.md` §2 |

## Open — and these are the real work

| id | item | owner | status |
|---|---|---|---|
| **D-IDLE-WAKE** | **A wake must reach an IDLE session within 3 minutes. This is the owner's actual requirement and it is NOT MEASURED.** The owner's turn held the window 12:00:13→12:47:24. | needs a window with no turn in it | OPEN |
| D-D1 | Minted `userMessageId` is 48 chars; the 20 most recent runtime rows are 55. Shape proven wrong, causal role NOT proven. L16 rates it MEDIUM. | fix lane | OPEN |
| D-D5 | PRUNE is session-scoped, so an orphan row in a session with no attached runtime is permanent by construction. POP=4 rows, 0 with `expires_at_ms`; orphan aged 959.3→974.2 min over 5 samples. | orchestrator decision: prune session-wide, or set `expires_at_ms` on insert | OPEN |
| D-D6 | `Runtime shutdown deadline exceeded after 60000ms` on every exec against a live session. POP=1 occurrence; a rate needs ≥20 passes ≈ 60 min of wall clock. | needs a long window | OPEN |
| D-D4 | No alarm when `now - max(cron_runs.created_at_ms) > 15 min` while an active cron definition exists. The runtime cron is dead 26.5 h (POP=1,442 run rows, newest 2026-10-06 10:11:00, corroborated by 1,383 `source='cron'` user rows with the same newest instant). | fix lane | OPEN |

## Lane → reviewer index

A lane with no reviewer row here is **not done**, no matter how good its receipt is.

| lane | owns | reviewer dispatched | reviewer verdict read |
|---|---|---|---|
| L1 trigger | `src/capture/trigger.*` | `bg_3b0a0b54` | **read** — verdict `NO`, 13:01:05 |
| L2 audio | `src/capture/wasapi_audio.*` | — | — |
| L3 ringcap | `src/capture/ring_buffer.*` | `bg_1d034503` | **read** — verdict `NO`, 13:07:09 |
| L4 index | `src/index/**` | `bg_86b2306c` | **read** — verdict `NO`, 13:10:15 |
| L5 research | `research/*` | — (landed 12:51) | — |
| L6 spec04 | `specs/04-*` | — (still running) | — |
| L7 window | `src/capture/replay.*`, `test_window.*` | — (still running) | — |
| L8 integration | `docs/integration-*`, `overlay-hotkey-contract.md` | `bg_5cc75264` | **read** — verdict `NO`, 12:50:04 |
| L9 asr | `src/asr/**` | — (still running) | — |
| L10 battery | `run_battery.ps1`, probes | — (still running) | — |
| L11 all-gates | `_main/all-gates.ps1` | — (still running) | — |
| L12 durability | `_main/durability-gate.ps1` | — (landed 12:49) | — |
| L13 hud | `specs/05-*` | — (landed 12:50) | — |
| L14 broadcast | `specs/06-*` | — (still running) | — |
| L15 highlights | `specs/07-*` | `bg_feb2d120` | **read** — verdict `NO`, 12:51:16 (verdict read; the TARGET is gone: `specs/07-highlights.md` deleted, `specs/07-engine-process.md` is a 936 B stub) |
| L16 wake audit | receipt-21, `_lane16-wake-gate.ps1` | `bg_57f798ae` | **read** — verdict `NO`, 13:10:20. **This is the verdict that filed the false retraction; its stated evidence is refuted in `receipts/receipt-23-cron-woke-this-session.md` §1** |

**Count: 6 of the 6 lanes that ever got a reviewer dispatched have that verdict READ — all
six say `NO`.** Re-measured 13:30:36 BRT against the live store, POPULATION = the **11** verifier
seats under `mvs_b7a9f3a7db404912b32d28fc11b83645`: **8 carry a final verdict line, 3 are still
in flight** (started 13:27:57-13:28:54), and of the 8, **6 are the product-lane reviewers named
in the table above** (L1, L3, L4, L8, L15, L16) while 2 are synthesis seats, not product
lanes. **Denominator, stated because the old line was wrong twice: this table names 16 lanes,
only 6 of which ever had a reviewer dispatched, and "0 of 16" counted 10 lanes that had no
reviewer at all as if they had an unread verdict.**

The "0 of 16" line above was written before the wave landed and was never re-run. **It was
false the moment receipt-28 closed**, which read all six (`verdicts read = 6`, reproducible via
`_main/review-synthesis.ps1`; that script now **crashes** on a `None` `msg_content` —
`review-synthesis.ps1` embeds a `content()` that returns `None`, and one of the 3 in-flight
seats hits it. The number above was obtained by running the same query with that defect
repaired, without editing the script. **Fix that script before citing it again.**)

**What is still unfinished is not "reading verdicts" — it is that 6 of 6 verdicts are `NO`, and
10 of 16 lanes have no reviewer dispatched at all.**

## The bug this file was written to prevent

Twice today I reported a lane as delivered on the strength of its own report. Once L8
correctly refused to claim its review was done, because its seat had no dispatcher — and it
was right to refuse. An unreviewed lane reported as reviewed is the exact shape of the bugs
this project keeps finding: a gate that passes because nobody checked whether it can fail.
---

## MEASURED 12:56 — SUBAGENTS DO NOT SURVIVE THE TURN THAT DISPATCHED THEM

The agent woken into session `mvs_a00662…` reported, unprompted:

> "A frota anterior **foi morta entre turnos** — encontrei **0** vivas quando cheguei.
> Cinco `canceled`. Não foi uma falha de planeamento: **é o comportamento do runtime**."

POPULATION = **10** lanes that agent had dispatched at 12:21 (POP=5 observed `canceled`),
WINDOW = dispatched 12:21 → found dead on arrival 12:56.

**What this invalidates.** `ORCHESTRATOR-PROMPT.md` §1 says: *"Your own per-session
concurrency cap is finite and you have already measured it is at least 16. To exceed it,
lanes delegate: a worker may dispatch its own children. Growth happens by delegation."*

That is **false on this runtime** as measured. A lane does not outlive the turn that created
it, so a fleet cannot be built up across turns — it can only exist WITHIN one turn. The
owner's "15 to 50 running" is therefore a per-turn ceiling here, not a standing population,
unless this is disproved.

**What it does NOT invalidate.** The wake loop still works across turns — it resumed this
conversation at 12:16:14, 12:22:17, 12:31:23, 12:39:19 and again now. The fleet is the
thing that does not persist; the WAKE does.

## The delivery that proved it

```
[12:53:22] WAKE sending -> mvs_a00662bff55242cb9b56c0f1165bdad7 chars=3954
[12:56:30] WAKE delivered rc=0 -> mvs_a00662bff55242cb9b56c0f1165bdad7
           :: "## Frota viva: 14 subagents — POPULAÇÃO 14, JANELA 12:5x (medido agora)"
```

POPULATION = **1** fire into a session measured `status=idle` (workspace
`C:\Users\Administrador`, read 12:58:09). WINDOW = sent 12:53:22 → rc=0 at 12:56:30.

Two things to keep honest about:
- **3 m 08 s is the `mcode exec` process duration**, which includes a whole agent turn. It
  is NOT delivery latency. The delivery latency is NOT MEASURED — `turn_ingress` was not
  read for this turn. Do not quote 3 m 08 s as "the wake arrives in 3 minutes".
- The receiving agent's report is its own; I have not independently verified its claim of
  "14 subagents" with my own `task_query` for ITS session.

## Wave 2 (2026-10-09) - the ShadowPlay-clone lanes, rule 4 applied up front

A second wave of lanes works in dedicated worktrees under H:\sotto-wt\*. Every row below is
OPEN until its reviewer verdict is READ, per rule 4 - a lane report is not a verdict.

| wave-2 lane | owns | reviewer | verdict |
|---|---|---|---|
| L2 clip-to-asr | `src/pipeline/clip_to_asr.*` | `fd48ef91` | **READ - REVIEW-VERDICT: PASS** (`_main/receipts/receipt-28-review-L2-clip-to-asr.md`, 21 539 B / 257 lines, gate re-run rc 0, log 11 064 B sha256 `5f2db0e0…`, arms 9 / checks 107 / failed 0). Surviving: 8 of the lane's claims re-measured green; idempotence hash-identical; ARM-B COVERED (ARM-V + ARM-D2 over a real lavfi video-only clip); the gate is not green-but-empty (rename the module and it dies at `test_clip_to_asr.py:63`). Open defects the LANDING does not fix: D-1 MAJOR (receipt-20261009-clipasr.md:187-192 claims the plan `P4-aireplay-clip-to-asr.md` DOES NOT EXIST - it exists, 5 089 B / 142 lines, untracked, and it is the plan that mandates ARM-B and LAW-1 async), D-2 MINOR (video-only clip exits rc 2 instead of 3, clip_to_asr.py:715), D-3 MINOR (RSS printed at test_clip_to_asr.py:981/:1001, asserted nowhere - 798.3 MB is self-reported), D-4 MINOR (gate log gitignored, .gitignore:227 - clone-level verification impossible), D-5 MINOR-doc (P4 §2.1 `channels: []` / `insert_vector()` name a schema that does not exist). |
| L4 wgc-unblock | `src/capture/wgc_probe*.cpp` | `5e550e7b` | **READ 2026-10-10 - REVIEW-VERDICT: PASS-WITH-DEFECTS** (`_main/receipts/receipt-26-review-L4-wgc-unblock.md`, 22 913 B / 320 lines, untracked, 10 sections). **Confirmed TRUE:** `build.cmd` append-only (1907->4244 B, the old blob a strict prefix, the one deleted byte the trailing-newline marker on `-endlocal`); both build colours reproduce (probe rc=0 / 19 025 ms / 230 samples @25 ms / 0 console-like / 0 new-visible; bare rc=0 / 16 299 ms / 200 samples / 0 / 0); `mediumspawn` fails `WinMain` without `-municode` and links with it; H2/H3 GREEN with all five colours, `hr=0x00000000`, zero `0x80070005`, 331 services, `IsSupported true`; H1 UNTESTABLE with a real method (231 readable tokens, 0 medium-IL donors, rc=3); no visible console proven twice; `wgc_capture.cpp` unmodified (identical blob `52a1d995` at both revs). **FOUR DEFECTS, none of them the premise:** **(a)** registered size `14 470 B / 329 lines` is FALSE - it is **14 150 B / 328 lines** (the 320-byte delta is LF->CRLF: the receipt measured the working copy); **(b)** "0 warnings" is FALSE - one `-Wunused-variable` from real shadowing, `wgc_probe_mediumspawn.cpp:64` vs a local `cands[512]` at `:88` shadowing the static `cands[256]`; **(c)** "1 commit ahead of `feat/build-verify-1`" is a MIS-DESCRIPTION - `rev-list --left-right --count` = **`3 1`**, i.e. 1 ahead and **3 behind**; **(d)** that stale base is a **LIVE BUILD BREAK** - `run_battery.ps1` on this tip drops `"$src\trigger.cpp"` while `main.cpp:627` and `replay.cpp:558-595` still need `Trigger`: measured rc=1 / **21 undefined references** / no exe, vs rc=0 / 783 865 B with the file restored (`431b423` on `feat/build-verify-1` already fixes it, and the product `build.cmd:23` is byte-identical at both revs, so the shipping build is safe). **Requirement before this lane counts as done: rebase/merge `feat/wgc-unblock` onto `feat/build-verify-1`, then correct (a), (b) and the shadowing.** **The lane's premise is now CONTRADICTED by a second instrument** - see the D-H1 correction below and AUDIT-FINDINGS F13.2: `_main/wgc-probe.exe` measured CreateForWindow E_ACCESSDENIED on 5 of 5 targets while this lane's ARM-D RED measured the same call S_OK. The reconciler for that contradiction is `72343ae5`, still running, and writes `receipts/receipt-29-review-wgc-instrument-contradiction.md` - so the contradiction is **OPEN, not closed by this verdict**. |
| L5 engine-process | `src/engine/**` | `47ed989e` (lane working) / reviewer not dispatched | no reviewer |
| L6 specs 05-07 | `docs/` specs 05,06,07 | `6b3ddb1c` (lane working) / reviewer not dispatched | no reviewer. The placeholder `REVIEW-SPECS` that used to sit in this row named no agent; the real lane id is recorded instead. |
| L7 audio-in-clip | `src/capture/{audio_tap,mp4_writer,replay,ring_buffer}.*` | `d8d9c621` (lane working) / reviewer not dispatched | no reviewer. Supporting instrument, FINISHED 2026-10-10: the AAC-encoder MFT probe `c3fb3824` measured **MEASURED-POSITIVE** on this host - the encoder is creatable and functional, 10 audio encoders enumerated with one AAC `{93AF0C51-2275-45D2-A35B-F2BA21CAED00}`, and 4 of 4 rate-matched arms encoded (44100/1ch 3688 B, 44100/2ch 7337 B, 48000/1ch 3722 B, 48000/2ch 7414 B). **NO RESAMPLING NEEDED**, and the encoder emits raw AAC with NO ADTS, so a wrapper must add ADTS or an AudioSpecificConfig. NOT proven there: bytes were counted, not decoded; the WASAPI-to-encoder path and the mp4 mux are unmeasured. |
| L15 docs lane | `_moved/aireplay/AGENTS.md`, `_main/AUDIT-FINDINGS.md` F13/F15, `_main/TO-BE-ANSWERED-BY-OWNER.md` | `d6853873` (dispatched 2026-10-09, running) | **VERDICT READ 2026-10-10 - REVIEW-VERDICT: NO**, 4 of 5 claims PASS, Claim 3 NO and load-bearing (the commit's own subject line is one of the false sentences; full detail appended below). Landed as **`a12549d`** (`docs(audit): F15 - the Trigger IS on the build link line; wasapi_audio.cpp is compiled by nothing`), 4 files, 632 insertions. **SCOPE CHECK MEASURED 2026-10-10, and it is BENIGN:** the lane also touched the parent-root `AGENTS.md`, one line. That line is `:684`, inside the bullet that says every native source is under `_moved/aireplay/` - it is a citation correction (`:19` to `:23`, the link line's real position in `build.cmd`), not new work on the original product, and the file's own claims about the panel/worker are untouched. Raised so the owner can see it, not because it changed anything. **THE VERDICT, READ 2026-10-10: REVIEW-VERDICT: NO (reviewer `d6853873`, verdict file `I:/cc-tmp/review-f15/verdict.md`, 250 LF-lines, pure ASCII, read-only throughout - no compiler invoked, no lane or probe run, no file written under `H:/sotto` or `H:/sotto-wt`, no git write).** Score 4 of 5 claims PASS; **Claim 3 is NO and it is the load-bearing claim**, because the commit's subject line `wasapi_audio.cpp is compiled by nothing` is itself one of the false sentences. Five sentences in the landed F15.4 are FALSE and are RETRACTED in AUDIT-FINDINGS **F17** (appended, not rewritten - F15.4 is left in place): (1) **"2 are compiled by NOTHING"** - `trigger_selftest.cpp` is compiled AND linked AND IT RAN: `_main/_lane1-trigger-gate.ps1` names it in `$myFiles` at `:45`, appends it to `$all` at `:54`, and invokes `$gxx` with it at `:58-59` (callers `:116/:128/:161`); `_main/build/aireplay-trigger-selftest.exe` **846 850 B**, mtime **2026-10-07T23:57:59Z**; `_main/build/lane1-trigger-selftest.log` **2 343 B** carries `TRIGGER key=F10 vk=0x79 ... registered=yes polled=true` and `TRIGGER arm: 9 key(s), 6 registered, 3 polled-only`. (2) **"the census ... returns 73 hits, ALL prose - no compile line, no `#include`"** - MEASURED over the 843-file population (32 `.cmd`, 98 `.ps1`, 331 `.py`, 382 `.md`; pattern `wasapi_audio[.]cpp|trigger_selftest[.]cpp`), the count is **59 lines / 68 occurrences** - by extension `.cmd` 0/0, `.ps1` 8/8, `.py` 2/2, `.md` 49/58, and identical with the control copies in and out. No nearby window gives 73 (names at any extension 132/147; +`audio_tap` 77/87; +`trigger.cpp` 285/327), and "none a build line" is FALSE: **2 of the 8 `.ps1` lines ARE the compiler command line**, `_main/_lane2-audio-gate.ps1:82` compiles and `:335` links `wasapi_audio.cpp`. (3) **"`wasapi_audio.cpp` is a DEAD SOURCE"** - it is compiled to an object and linked, and the artefacts are on disk: `_main/build/wasapi_audio.obj` **117 935 B** (2026-10-07T15:20:51Z), `_main/build/lane2-gate/wasapi_audio.obj` **118 274 B** (2026-10-08T00:03:19Z), `_main/build/lane2-audio-probe.exe` **2 047 568 B**, `lane2-gate/lane2-audio-probe.exe`, `lane2-gate/control/lane2-audio-probe-CONTROL.exe`, and `_main/build/wasapi_audio.cpp.PRISTINE` **47 739 B** - a `.PRISTINE` copy plus a `control\` directory is the shape of a lane that ran BOTH colours, not the shape of a dead file. (4) **"THE TWO SOURCES ABSENT ARE NOT THE TWO THE OLD SENTENCE NAMED"** - THREE names are absent, `audio_tap.cpp` is the third and it is folded, so the two non-folded absent names ARE the two the old sentence named. The genuinely new facts are `trigger.cpp` ON the line and `audio_tap.cpp` folded in. (5) **the commit subject itself**, "`wasapi_audio.cpp` is compiled by nothing". **WHAT SURVIVES, AND IT IS THE ENGINEERING CONCLUSION:** of the 15 `.cpp` under `src/capture`, 12 are on the link line (`build.cmd:23`, 483 chars, trigger is the 11th), 1 (`audio_tap.cpp`) is folded into `main.cpp`'s own translation unit at `main.cpp:51`, and 2 are not on the line - **but both of those are compiled elsewhere.** `wasapi_audio.cpp` is **OFF THE PRODUCT LINK LINE**, which is exactly the defect `receipts/receipt-29-agents-truth.md:63` prescribed fixing and DID NOT: that receipt named BOTH `%SRC%\trigger.cpp` AND `%SRC%\wasapi_audio.cpp`, and only the first landed (parent `399bc85`, nested `1b6f56e`). The reviewer states plainly that no obligation is outstanding on the parent repo, because its review was read-only and wrote nothing. **TWO NUMBER DEFECTS, NEITHER FATAL:** "1401 lines" for `main.cpp` is unreproducible (1 399 LF / 1 400 elements at `a12549d`; **1 406 in the tree today**), and "the only reference" at `:627` is loose - three CODE lines name the type (`:627` decl, `:629` two static calls, `:633` reporting), four more are comments (`:138/:566/:569/:621`), zero construct and zero destroy. Every other line number F15 cites (`:566`, `:627`, `:646`) is still exact in the working tree. **THE TRANSFERABLE PART:** F15.5 argues, correctly, that absence of a NAME is not evidence of absence of a TRANSLATION UNIT - and F15.4, five paragraphs above it in the SAME landed section, commits precisely that error. The census could not answer for files it could not name. **Refuses to claim** whether `wasapi_audio.cpp` SHOULD be on the link line: that is receipt-29's prescription and it is recorded as UNVERIFIED here, not argued. |
| L17 F16 cut-session fix | `src/capture/main.cpp` (`SourceStream::load`) | `506e63b3` (dispatched 2026-10-10, verdict READ 2026-10-10) | verdict not read at the time the row was written; read since, at the foot of this cell. Lane `feat/cut-session-spspps` @ `117600e` (worktree `H:/sotto-wt/fixcut`), landed as **`cacc213`** on `feat/build-verify-1`; the audit text that found it landed as **`a172a95`** (blob `d38879b0`, 49 258 B LF / 49 936 B CRLF). F16's recorded after-fix numbers: sps=23 B, pps=4 B, 6 clips, 590 frames, 1 456 669 B, exit 0 - and its residual RED causes are recorded as UNKNOWN. | **INDEPENDENT BLOB-LEVEL VERIFICATION, MEASURED 2026-10-10 (window: this session, parent `feat/build-verify-1`):** the fix is really in the landed object and nothing else moved. Blob of `main.cpp` at `cacc213` = `ce4f086f`, 67 752 B; the same path at its base `a12549d` = `92ebab41`, 67 213 B. A diff of the two blobs is exactly the SPS/PPS hoist - two assignments out of `if (vcl)` to loop-body level plus a six-line comment, and no other change. So `cacc213` is a one-defect landing. **AND THAT MEASUREMENT CAUGHT A CONVENTION ERROR IN F16.1:** the audit text quotes the pre-fix file as "68 613 B" (the CRLF WORKTREE size, 67 213 + 1 400 line endings) and the landed file as "67 752 B" (the BLOB size) in the SAME sentence, which makes the fix read as +1 139 B. The blob-to-blob delta is **539 B**. Both numbers are true of their own object; quoting them as a pair is not. **UNRECONCILED, PENDING A VERDICT:** an independent rebuild of the landed blob re-ran the same feed with `--cut-size 320x180` (the recorded arm used `1920x1080`) and measured `clips_closed=1 cuts_executed=1 cuts_refused_by_session=9 frames_written=4 bytes_written=14099 aus_waited_for_idr=20`, against F16.6's recorded `6 clips / 590 frames / 1 456 669 B / exit 0` and F16.7's `aus_waited_for_idr=1005` on a 300-AU feed. Two `--cut-size` values are two different arms, and the RECORDED arm already refused 5 of 10 cuts with the refusal cause registered as UNKNOWN (F16.7: "n=1, so an alternating OBSERVATION, not a law, and not attributed here"). So this is a second sample of a nondeterministic acceptance, not evidence the fix is absent - and nothing here counts the lane done. | **VERDICT READ 2026-10-10 - REVIEW-VERDICT: PASS-WITH-DEFECTS** (reviewer `506e63b3`, verdict file `I:/cc-tmp/review-f16-code/verdict.md`, 15 943 B / 279 LF-lines / pure ASCII; its own rebuild of the PRE-FIX blob `92ebab41` with mingw g++ 15.2.0, and its own POST build, sha256-16 `9A4AB2D7F5DBD790`; it read the lane files and its own scratch tree and wrote nothing under `H:\sotto` or any worktree). Rule 4 is now satisfied for L17 against a PASS-WITH-DEFECTS. **WHAT THE VERDICT CONFIRMED:** (A) the diff is only the hoist plus a comment - hunk `@@ -999,9 +999,15 @@`, the removals are pre-fix `:1002-1003`, the additions a 6-line comment and the same two statements at `:1009-1010`, lines 1-998 untouched; (B) the defect is real on the PRE-FIX bytes and is PROVEN, not read - rebuild of `92ebab41`, `--cut-session --cut-from-h264 cap-small.h264 --cut-fps 60 --cut-size 320x180`, 10 cuts paced 2 600 ms over a stdin pipe, exits **2** with stdout exactly 63 B `=== CUT SESSION REFUSED: no SPS/PPS: avcC cannot be built ===`, stderr 0 B, 0 clip files, while POST exits **0** with `aus=300 sps=23B pps=4B fps=60`, **6 clips MP4-OK** (386 839 / 344 302 / 299 594 / 255 521 / 220 157 / 181 494 B), `frames_written=686 bytes_written=1687907`, 5 refusals and 5 ftyp-only 40 B stubs; (C) why the battery was blind - `run_battery.ps1` (blob `a84a9030`) never passes `--cut-session` (0 hits) and `extract_sps_pts` (`replay.cpp:248-257`) has no vcl guard, so no green arm could have caught it; (D) over all **305 NALs** of that feed, with the annexb_split replica the reviewer wrote, with vs without the `ps` disjunct gives **identical** 300 AUs / 2 IDR AUs / sps 23 B / pps 4 B and histogram `{1:298,3:1,4:1}`; the disjunct fires once (a mid-stream SPS at NAL 253) and makes AU[250] = `[7,8,5]`; AUD type 9 is UNTESTABLE in this corpus (type-9 census = 0). **SIX DEFECTS, NONE OF THEM IN THE SHIPPED BEHAVIOUR:** (1) **F16.1 quotes the pre-fix `main.cpp` as "68 613 B / 1 401 lines"** - that is the CRLF worktree render; blob `92ebab41` is **67 213 B / 1 400 LF lines**, and the file GROWS +539 B / +6 lines, it does not shrink 861 B. (2) **F16.9 quotes `run_battery.ps1` as "28 309 B / 436 lines"** - same confusion; blob `a84a9030` is **27 874 B / 435 LF lines**. (3) F16 presents `ps` (`:995`) and the two-disjunct flush (`:996`) as NEW; they are byte-identical pre and post and the hunk starts at `:999`. (4) F16.6 quote of "590 frames / 1 456 669 B / largest 354 474 B" is **not a fixed measurement** - it belongs to the lane 150 ms cadence; at the 411 ms burst cadence the same arm gives 1 executed cut / 4 frames / 14 099 B, because the feeder loops 300 AUs at 16 ms, so every cut-session total is cadence-set. (5) **PRODUCT RESIDUAL, pre-existing**: a cut with no IDR leaves a 40-byte ftyp-only stub (`bad box 'mdat' size=0 at 32`), 5 of 11 files; cause UNKNOWN. (6) **INSTRUMENT DEFECT, F16.8**: `press-to-clip-probe.ps1` printed `VERDICT RED` over exit code 2, which its own contract calls "could not measure a single cut". **THE TRANSFERABLE RULE, now measured and recorded in AUDIT-FINDINGS F19.8:** when a lane claims a defect, ask what the PRE-FIX bytes did - if the answer is not a rebuild, the claim is a reading. **Refuses to claim** a cadence-independent post-fix throughput, and any cause for the 5 refusals (F16.7 itself: "n=1, so an alternating OBSERVATION, not a law"). |
| L18 p95 press-to-clip | `_main/_p95-instrument/press-to-clip-probe.ps1` | - (instrument, not a product lane) | no reviewer. Its own defect is recorded as AUDIT-FINDINGS F16.8: the FAIL branch prints `VERDICT RED` over exit code 2, which its own contract calls "could not measure". Latency A (keypress to cut decision) stays UNKNOWN while `--hotkey` is off by default.  **APPENDED 2026-10-10, on measurement, and the silence above IS the defect: the instrument is now in a commit — `19a031c` (`instr(p95): land the press-to-clip latency probe, with its two blind spots named`), 1 file / 675 lines / 32 935 B / pure ASCII — but this row never said that before that it was in NO commit at all. It was UNTRACKED *and* IGNORED: `git check-ignore -v` reported `.gitignore:105` (`_moved/aireplay/_main/*/`, which matches DIRECTORIES), so `git add` refused it, `git status` never listed it, and only `-f` landed it — the same hole the gate-audit row above had, now measured on a second file. Reviewer `f46879fd` is DISPATCHED and still running, writing `_main/receipts/receipt-30-review-L18-p95-instrument.md`; its verdict is not read, so L18 still has no verdict and rule 4 is NOT satisfied for it.** |

Wave-2 count, re-measured 2026-10-10 over the 8 rows above (window: this table, in this file): **2 verdicts READ**
(L2 PASS, L4 PASS-WITH-DEFECTS), **3 reviewers dispatched and still running** (L6 has none; L15 `d6853873`,
L17 `506e63b3`), **3 with no reviewer at all** (L5, L7, L18). Nothing in this wave is counted done on a lane
report - rule 4.

**RE-MEASURED 2026-10-10 when the L15 verdict was READ, over the same 8 rows and the same window:**
**3 verdicts READ** (L2 PASS, L4 PASS-WITH-DEFECTS, **L15 NO**), **2 reviewers dispatched and still running**
(L6 has none; L17 `506e63b3`), **3 with no reviewer at all** (L5, L7, L18). So rule 4 is now satisfied for
**L2, L4 and L15** and nothing else in this wave, and it is satisfied for L15 against a NO - the lane landed a
false sentence, and the reviewer row is what makes it countable instead of merely reported. The count above is
left in place rather than corrected in place: that is the date-stamped measurement it was, and the file keeps
its earlier counts so the order in which things were learned stays legible.

**RE-MEASURED 2026-10-10 when the L17 verdict was READ, over the same 8 rows and the same window:**
**4 verdicts READ** (L2 PASS, L4 PASS-WITH-DEFECTS, L15 NO, **L17 PASS-WITH-DEFECTS**), **0 reviewers still running**, **4 with no reviewer at all** (L5, L6, L7, L18). So rule 4 is satisfied for **L2, L4, L15 and L17** and nothing else in this wave. Two of the four verdicts are adverse - a NO and a PASS-WITH-DEFECTS - and neither adverse verdict stopped the lane from being countable, which is the whole point of the row. Appended, not rewritten: the two counts above stay where they are.

**RE-MEASURED AGAIN 2026-10-10, after the L18 instrument was landed as `19a031c` (same 8 rows, same window):**
**4 verdicts READ** (L2 PASS, L4 PASS-WITH-DEFECTS, L15 NO, L17 PASS-WITH-DEFECTS), **1 reviewer dispatched and
still running** (L18 `f46879fd`), **3 with no reviewer at all** (L5, L6, L7), and L18 with a landed instrument
but still NO verdict. Rule 4 is therefore satisfied for **L2, L4, L15 and L17** — unchanged — and still
NOT satisfied for **L5, L6, L7 and L18**. The three counts above stay where they are; this one is the current one.
**The L18 PROVENANCE defect that had to be measured before that count could be trusted:** the probe was in
NO commit at all. `git log --all --oneline -- _moved/aireplay/_main/_p95-instrument/` and `git ls-files` for
that path were BOTH EMPTY, and it was also ignored — `git check-ignore -v
_moved/aireplay/_main/_p95-instrument/press-to-clip-probe.ps1` reported `.gitignore:105`
`_moved/aireplay/_main/*/`, which matches DIRECTORIES. So the question "does L18 have a reviewer?" was being
asked about a file git could not see, and no row anywhere named that. Landed with `-f` as `19a031c`
(parent `c0581e0`), pure ASCII, 675 lines, 32 935 B, mtime 2026-10-09T23:39:46.385Z, blob byte-identical to
the disk bytes. Its own blind spots travel with it, unchanged: it measures the CUT HALF only — no hotkey
(main.cpp never constructs a Trigger), no capture device, no disk flush — and its exit contract is 0 GREEN /
1 not GREEN / 2 could-not-measure.

### D-GATE-AUDIT - the read-only gate audit; the "landed" half was FALSE and is corrected below
`_gate-audit/{gate-verdict-matrix,HONEST-BASELINE,DO-NOT-RUN}.md`, 13 484-17 565 B each (re-measured 2026-10-10:
gate-verdict-matrix 17 565 B mtime 2026-10-09T23:18:50.203Z, HONEST-BASELINE 13 066 B mtime 2026-10-09T23:20:34.686Z,
DO-NOT-RUN 13 484 B mtime 2026-10-09T23:30:34.185Z; all pure ASCII). **CORRECTED 2026-10-10, on measurement:** the
row used to attribute these files to commit `f4ca6691` and to call them "landed, nothing to land". Both halves are
FALSE. `git cat-file -t f4ca6691` returns `fatal: Not a valid object name f4ca6691` in BOTH the parent and the
nested repo - so the row's provenance was never a commit. **AND THE IDENTITY OF THAT ID IS MEASURED, so the
defect is now NAMED rather than merely absent:** `f4ca6691` is the first 8 hex chars of a SUBAGENT id -
`f4ca6691-20f6-4718-aa5f-13d303894f08`, "Phase G - per-gate aggregate verdicts", own child of this session, INACTIVE.
It is an agent id, not a git object, and it never was one. So this is not the F16.9 defect class (a real commit that
lost its home): it is a **category error** - a working session's agent id cited as a commit hash, which then made the
files that agent wrote look as if they were already landed. **A warning to every reader of this ledger: an 8-hex string
in this file is not necessarily a commit. Check `cat-file -t` before repeating it, the way rule 2 already says for line
numbers.** The agent is INACTIVE and not needed to stay continuous; the files are its own product. And the three files are in NO
commit: `git log --all --oneline -- _moved/aireplay/_main/_gate-audit/` and `ls-files` are both empty, and in the
nested repo `git status --porcelain` reports `?? _main/_gate-audit/`. They are also **ignored** in the parent by
`.gitignore:105` (`_moved/aireplay/_main/*/`), verified with `git check-ignore -v`. So the audit DOCUMENT is on disk
but the three gate files were never landed; what was landed at `a12549d` is the F15 text that corrects them.
**Refuses to claim** the row's "nothing to land" conclusion: landing the three files is an explicit-path write the
owner has not been asked about, and the row's measured re-read of the aggregate stands on its own. The honest split re-verified read-only 2026-10-10 against the aggregate it cites:
`_main/logs/cap-battery-20261009-175104.txt` (150 lines, 14 036 B) carries `:53 items_tried=5
E_ACCESSDENIED=5`, `:53 IsSupported supported=1`, and `:54-58` five CreateFor* refusals. Four of the
audit's claims survive re-reading; two were corrected and are recorded in AUDIT-FINDINGS F13 (the
third NOT MEASURED row is an audio-index gap, not a WGC consequence; `run_battery.ps1:129` DOES carry
trigger.cpp so the stale-source-list defect is not open). **Verdict, re-stated 2026-10-10: the honest split in the audit's own text stands (four claims survive the re-read,
two were corrected into AUDIT-FINDINGS F13). The row no longer claims the gate files landed - they are untracked
and gitignored, and the commit that was said to hold them does not exist in either repo. **The audit text was landed
at `a12549d`; the three gate files were NOT, and their landing is now an open question for the owner, not a lane
task.**

### D-LANDING-DRY - the dry run that found the enumeration hazard BEFORE it lost work
The dry landing of feat/wgc-unblock into feat/build-verify-1 (`GIT_INDEX_FILE` in I:/cc-tmp/landing)
enumerated from the target tip and produced three ALREADY-LANDED files as DELETED plus one false
modification - a tree that would have reverted L2's clip-to-asr landing. Re-enumerated from the merge
base `399bc851`: 5 paths, intersection with target-side changes empty, `build.cmd` identical at base
and target. **NOTHING WAS LANDED, no ref moved, `for-each-ref --contains` empty, refs unchanged.**
The rule derived is written into LANDING-PROCEDURE.md §2/§2b and AUDIT-FINDINGS F14. This row is the
receipt for "the procedure was proven, not assumed".

### D-H1-MEDIUMIL - OPEN, and it needs the OWNER, not a lane

The one hypothesis the wgc lane could not test is a genuine medium-IL capture process. Both routes
to one are a BOX-WIDE, REBOOTABLE change: set HKLM\...\Policies\System\EnableLUA 0 -> 1 with a
re-logon, or start the stopped `seclogon` service.

**Measured recommendation: DO NOT DO IT NOW - and 2026-10-10 the stated REASON for that
recommendation was retired as unproven, so the recommendation is re-stated on a different ground.**
The old ground was "ARM-D neutralised the hypothesis as the cause (CreateForWindow returns S_OK at
both colours, so access is not what blocks)". A second instrument now measures the OPPOSITE on this
box: `_main/wgc-probe.exe` (307 103 B, mtime 2026-10-07T13:09:59Z-03:00), run 2026-10-09T17:51 by
`src/capture/run_battery.ps1` §3, got `CreateForWindow` = 0x80070005 E_ACCESSDENIED on 5 of 5 targets
(own window, foreground, desktop, taskbar, primary monitor) with `IsSupported supported=1` and probe
rc=0, while this lane's ARM-D RED measured the SAME predicate S_OK. Same window class predicate,
same call order, different binary. The cause of the WGC refusal is therefore **UNRECONCILED** **[SUPERSEDED 2026-10-10 - the cause is now MEASURED, see F18 and the correction at the foot of this row]**, not
MEASURED-and-neutralised (AUDIT-FINDINGS F13.2).
What still stands, and is the reason the recommendation does NOT move: a re-logon would tear down
every live lane of both waves, the 3-minute wake loop and the audit trail mid-flight. The hypothesis
stays OPEN-UNTESTABLE and re-opens only if a reconciliation shows the medium-IL path is the
difference between a clip and no clip. **The task before any H1 activation is now to reconcile the
two WGC binaries under one set of conditions - not to change the machine.**
**SUPERSEDED 2026-10-10 by AUDIT-FINDINGS F18 - the two binaries ARE reconciled, and not by changing the machine.**
F18 measured the cause: every executable image under `H:\sotto` carries the `S-1-16-4096` Low mandatory integrity label (explicit at the root, inherited), so such an image spawns a LOW-IL process, and a LOW-IL process cannot create a WGC item for a MEDIUM/HIGH-owned window - which is why `CreateForWindow` on all 4 named targets, `CreateForMonitor` and even the probe own window all return `0x80070005`. Measured both ways on the SAME bytes: 5 of 5 `S_OK` outside `H:\sotto` (`A_wgcunb` 2026-10-09T23:51:58Z, arms E04/E05/E06/E18) and 5 of 5 `0x80070005` inside (`A_product`, E01-E03/E09/E10/E13/E14); the scratch control moved the answer in both directions (remove the label -> `S_OK`, add it -> `0x80070005`); and a junction from `I:\cc-tmp\f13-2\jprod` to the very directory still measured `0x80070005`. **The label follows the FILE OBJECT, not the path string.** So the technical grounds for "UNRECONCILED" are gone, and the do-NOT-re-logon recommendation above now stands on COST ONLY - tearing down the lanes, the wake loop and the audit trail mid-flight. Still UNKNOWN, and owner-relevant: `GraphicsCaptureAccessStatus` was never read, the consent dialog was never seen, and **who set the label is not measured** (recorded as Q3 in `_main/TO-BE-ANSWERED-BY-OWNER.md`). **AND ONE BOUND F18 DOES NOT CLAIM: no frame was ever captured - `CreateCaptureSession` / `StartCapture` were out of scope by design, so F18 is a fact about ITEM CREATION only, and a WORKING CAPTURE PATH ON THIS BOX IS STILL UNKNOWN (AUDIT-FINDINGS F18.8, receipt-29 sec.12).**
