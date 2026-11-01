# Receipt — receipt provenance: the route is measured, not declared

Task `TC-20261025-cross-project-continuity` · lane `sotto-lane-task-resolver-continuation` · role `worker`
· **route measured**, not claimed: `providerID=opencode-go-3`, `session=ses_e8d744284ffeIm41qK8k2PXU0C`
(`opencode.db` / `session_v2.model`, read-only) · date 2026-10-26 · **no commit, no push** ·
**no app launch, nothing on the owner's screen**.

State claimed: `doing -> done` for W-10 (shared worklist). `FIXED, NOT VERIFIED`: the product never ran
for this work and no independent reviewer read it. The two rows that could not be exercised say so (§6).

---

## 1. The defect, and why the previous correction was not enough

`state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md:4` said:

    route: owner-authorized OpenCode Go 1 (DeepSeek V4.1 Flash)

The process that produced that receipt ran on **`opencode-go-3/deepseek-v4.1-flash`**. The declared slot is
the one the routing policy *probes first* (`.agents/skills/task-resolver/references/model-routing.md` §2:
*"probe DeepSeek V4.1 Flash through `opencode-go-1`, then … `opencode-go-6`"*) — an **intention** written
where a **measurement** belonged. That is the class: *declaring what should have been instead of measuring
what was*.

§11 of that receipt already corrected the prose, and `CA21124B…` was the digest bound to all 24 `done`
rows. So the correction existed and was honest — **and nothing stopped the next receipt from repeating the
defect**, because the only thing guarding a route claim was a paragraph a human had to remember to read.
W-10 asks for the closure to be produced by a gate, so this receipt adds the gate.

## 2. The instrument that settles a route — and the one that cannot

**The manager's instrument is not decisive, and this is measured, not argued.** `opencode.exe` does not
carry the provider in its argv:

```
> Get-CimInstance Win32_Process -Filter "Name='opencode.exe'" | select ProcessId, CommandLine
30156  H:\env\npm-global\node_modules\@opencode\cli\bin\opencode.exe serve --service
41556  "H:\env\npm-global\node_modules\@opencode\cli\bin\opencode.exe"
25692  "…\opencode.exe" --continue
44720  "…\opencode.exe"
```

No `--model` anywhere. **A `process-info` observation of `opencode run` cannot settle a slot** — it is
consistent with any of the six. (The earlier receipt's Evidence (c) argued the opposite from four processes
that *did* show `--model`; both are true and they are different launch shapes: `opencode run` carries
`--model`, the TUI `serve`/`--continue` does not. Recorded because the difference is what makes the
manager's observation *sometimes* decisive and sometimes silent.)

**The harness's own record is decisive.** `opencode.db`, table `session_v2`, columns
`id`/`model`/`time_created`/`time_updated` — read-only, metadata only, no message content. The join is
*containment of an instant*:

| fact | value | instrument |
|---|---|---|
| this lane receipt's creation instant | `2026-10-25 07:07:32` local (`10:07:32Z`) | `Get-Item …receipt.md` `.CreationTime` |
| the session window containing it | `ses_e8d811684ffe1TrRQxUW83QVPI`, `06:58:02 -> 07:08:15` (`613.3 s`) | `time_created <= t <= time_updated` |
| that session's model, verbatim | `{"id":"deepseek-v4.1-flash","providerID":"opencode-go-3"}` | `session_v2.model` |
| the Go 1 candidate | `ses_e8d8193edffeqK5CZTlnQ6e9zt`, `06:57:30 -> 06:57:32` (`2.4 s`) | closed before the write |
| the Go 2 candidate | `ses_e8d812b16ffexbvYjxgbie3r2Q`, `06:57:57 -> 06:57:58` (`0.9 s`) | closed before the write |

**Exactly one** Sotto session window contains `07:07:32`, and it is Go 3. This is a second instrument that
shares no code path with the launcher log §11 used, and it dates Go 1's death to `2.4 s` — what a launch
dying on an expired key looks like.

**The falsifier.** Containment discriminates **only because every competing window had closed**. Had a
Go 1 window still been open at that instant, this instrument would be silent and the route would stay
`REPORTED`. It also proves the *harness's* attribution, never which weights answered a token.

## 3. The gate, and the two defects it found in itself

`_main/receipt-provenance-oracle.py` — four checks, population `state/work/**/receipt*.md`:

| check | refuses |
|---|---|
| `header-route-measured` | a header that names a paid slot with no `providerID=` **and** `session=ses_...` |
| `header-route-agrees` | a `route:` line that disagrees with the measurement and does not declare itself `SUPERSEDED` **and** name the measured slot |
| `measurement-cites-tool` | a `providerID=` with no instrument named (`opencode.db` / `opencode.log` / `CommandLine` / `process-info`) |
| `population-nonempty` | zero receipts — rc=2, because *a skip is not a gate that passed* |

**Red first, on the real defect.** Reconstructing the pre-cure header (`I:\cc-tmp\receipt-original-header.md`)
and judging it:

```
CHECK header-route-measured  FAIL  … header names slot(s) opencode-go-1 with no measurement
                                   (missing providerID=+session=ses_) -- a declared route is not a measured route
VERDICT: FAIL
```

**Two defects in this gate, found by its own negative arm before it shipped:**

1. the slot pattern was token-only (`opencode-go-1`) and therefore **blind to the exact string the defect
   used** (`OpenCode Go 1`, with a space). The first RED was firing on a `opencode-go-3` mention later in
   the header, not on the declaration. The pattern was widened to both forms and the arm re-proved.
2. the agreement rule ("last slot named must be the measured one") was **tautological**, because the
   `providerID=` token introduces a slot itself. Replaced by: read the declaration from the `route:` line,
   neutralise the measurement tokens, and allow a difference **only** when `SUPERSEDED` is declared and the
   measured slot is named in the same header.

Four arms, each refused by its **named** check, plus the `COPY-BROKEN` guard (an intact copy must be green,
or a red mutation proves nothing):

```
mutation claim-without-measurement   -> PASS (refused by header-route-measured)
mutation supersession-removed        -> PASS (refused by header-route-agrees)
mutation decorative-measurement      -> PASS (refused by measurement-cites-tool)
mutation empty-population            -> PASS (expected population-nonempty to refuse)
NEG-ARM PASS mutations=4 named-arm-fail=0        (rc=1 by design)
```

## 4. Curing the receipt, and the price of editing a receipt

`receipt.md` gained, inside the header block (so the gate can see it) and as `§11(d)` (so a human can):

- the measurement tokens (`providerID=opencode-go-3`, `session=ses_e8d811684…`, `opencode.db`);
- a new `### Evidence (d)` with the containment table, its instrument, and its falsifier.

Line 4 was **kept**: it is what was dispatched, and rewriting history is not a cure. It is marked
`SUPERSEDED`, which is the only licence the gate accepts for a disagreement.

Editing a receipt breaks every `@sha256:` binding, so the 24 `done` rows were rebound in one pass
(`ca21124b…` → `fce08d3a…`), each with its own numbered `status` revision `r64..r87`. Historical
`r25..r48` entries keep the old digest — **the change log is append-only and was not rewritten**.

## 5. Commands and exit codes (all from `H:\sotto`)

| # | command | rc | verdict |
|---|---|---|---|
| 1 | `python _main\receipt-provenance-oracle.py` (**before the cure**) | **1** | `header-route-measured` FAIL — the real defect |
| 2 | same, `--path I:\cc-tmp\receipt-original-header.md` | **1** | the reconstructed original header, same check |
| 3 | `python _main\receipt-provenance-oracle.py` (after the cure) | 0 | 4 checks PASS |
| 4 | `python _main\receipt-provenance-oracle.py --neg-arm` | **1 by design** | `NEG-ARM PASS mutations=4 named-arm-fail=0` |
| 5 | `python I:\cc-tmp\sotto-wire-provenance.py` | 0 | battery `120822 -> 122461 B`, `1593 -> 1611 CRLF`, bare LF `0 -> 0` |
| 6 | `python _main\agents-md-pins-oracle.py` (before the pin cure) | **1** | EXPECTED-RED on my own battery edit: `122461 B false`, `1611 CRLF false` |
| 7 | `python _main\agents-md-pins-oracle.py` (after) | 0 | `AGENTS-PINS PASS -- 2 pin(s) checked live` |
| 8 | `python _main\claims-date-oracle.py` | 0 | `BATTERY-VERDICT claims-date PASS checks=4 fail=0` |
| 9 | `python _main\sotto-state-page.py --write` then `--check` | 0 / 0 | `passos=132`, my two steps `NOT RUN` (never a green) |
| 10 | `python _main\battery-wiring-oracle.py` | **1** | **PRE-EXISTING**: `sem_passo=125` vs `ceiling=124` (§6) |
| 11 | `python _main\tooling-intent-oracle.py` | 0 | `declaradas: 15 | baseline 160 | vermelhas: 0` |
| 12 | `python I:\cc-tmp\sotto-rebind.py` | 0 | `rows rebound: 24  new=24  stale=0`; `r64..r87` |
| 13 | `worklist-replay.py --r0 … --final … --require-receipt-digests` | 0 | PASS, quoted in the hand-back (§9 explains why it is not embedded) |

## 6. What is NOT verified

- **The battery never ran.** `performance-gate.py` was not asked for a heavy lease for this work and the
  full battery is heavy class. So `receipt-provenance` and `red-as-expected-receipt-provenance` are
  **`NOT RUN` as steps**: their argv is exercised by hand (§5 rows 1–4) and their bytes are wired, but no
  `steps=` line carries them. A skip is not a gate that passed.
- **`battery-wiring` is RED and it is not mine.** `sem_passo=125` against `ceiling=124`. Arithmetic on two
  measured counter pairs: **before** this oracle existed, population `174` and `ligados 49` → `125`;
  **after**, `175` and `50` → `125`. My file added one tool **and wired it**, so the debt is unchanged;
  the ceiling was already exceeded by one. Named, not rounded up.
- **No independent verifier** read this. Every `PASS` here means *measured by the author*.
- **`code-health`** is still RED on three pre-existing dirty product files (`app/webview/sotto_webview.py`,
  `app/webview/youtube_window.py`, `worker/sotto_worker.py`) — untouched by this lane, same owner.
- **The gate's population is one file.** One receipt exists under `state/work` today. A population of one
  is a real gate only because the check is per-file and the empty-population arm is red by test.

## 7. A defect this lane created and caught in its own script

The first run of `sotto-rebind.py` reported `rows now carrying the new digest: 0` — its own verification
counter — because it reused a stale `line` variable and wrote the file's last line over 24 table rows.
The file was **restored** from `I:\cc-tmp\todo-before-rebind.md` (78810 B,
`80AD79EF…`, replay confirming `rows=32` intact) before anything else ran. The second run then reported
`stale=24`, which was the check being wrong, not the file: those 24 were the *historical* `r25..r48`
entries, which keep the old digest by design. Both corrections are in the script, and the script now
**refuses to write** unless `new == rebound` and `stale == 0` over the table rows only.

## SELF-AUDIT

1. **claimed-state:** `doing -> done` for W-10. No `verified`: no independent verifier, the app never ran.
2. **what-changed:** `_main/receipt-provenance-oracle.py` (new), `_main/_audit-verify-all.cmd` (+18 lines,
   `120822 -> 122461 B`), `AGENTS.md` (pin row), `docs/state-generated.md` (regenerated),
   `state/…/sotto-lane/receipt.md` (header measurement + `§11(d)`), `state/…/sotto-lane/todo.md`
   (24 rebinds `r64..r87`, plus the T-14 row), this receipt.
3. **commands-run:** §5, 13 rows, each with its rc; every green has its command, every red has its owner.
4. **what-I-did-not-do:** no commit, no push, no battery run, no heavy process, no app launch, no pane
   created or moved, no write in `app/` or `worker/`.
5. **refuted-mine:** three times, §3 and §7 — the token-only regex, the tautological agreement rule, and
   the clobbering rebind script. Each was refuted by my own instrument, not by a reviewer.
6. **red-I-did-not-cause:** `battery-wiring` (ceiling exceeded by one before this oracle existed, proved by
   counter arithmetic) and `code-health` (three pre-existing dirty product files). Named, not hidden.
7. **gate-doubt:**
   - *verde-de-verdade:* the oracle was RED on the real bytes before the cure (§5 row 1), GREEN after, and
     each of its four arms was refused by its **named** check with an intact-copy guard — so the green is a
     repair of a measured red, not a fresh colour.
   - *falta-no-gate:* the gate reads **headers only**. A route claim buried in `§8` or in a `_main/receipt-*`
     body is invisible to it; and it has no way to tell a `providerID=` that was copied from the routing
     policy instead of measured from `session_v2`. The `measurement-cites-tool` check is the weakest of the
     four: it asserts an instrument is *named*, not that the instrument *agrees*.
   - *gate-melhor:* read the instrument instead of trusting its name — when `opencode.db` is reachable,
     look up the named `session=ses_…` and compare its `model` to the claimed `providerID=`. That turns
     `measurement-cites-tool` from a citation check into a re-execution, and it is the obvious next step.

## INTENT-PROGRESS

helps: the owner's final intention is a caption he can trust to be 1:1 with YouTube's. Every gate in this
repo is only worth what its *provenance* is worth — and this lane found that the lane's own receipt
declared the route it was told to prefer while a different route did the work. A receipt that misreports
who produced the evidence makes every green downstream unauditable, which is exactly how "the caption is
fixed" can be said for four days while the owner still sees the wrong thing. This turn makes the route a
measured fact with a re-executable instrument (`session_v2` containment) and a gate that goes red on the
mismatch, so the next claim about the caption is attached to an identity that can be checked.

todo: W-10

next: **the 1:1 comparison the owner actually asked for, executed once with both captures kept** — brief
acceptance 1 and 2: play one named YouTube video, capture YouTube's own caption track and Sotto's rendered
caption in the same run, keep both artefacts, and state which element still fails (words, line-break
position, or timing). That is the big step because the 1:1 machinery is now measured green on the payload
(677/677 reveal) while the *live* half has never been compared side by side — and that comparison, not
another gate, is what closes his complaint.
