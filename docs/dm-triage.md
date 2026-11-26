# DM triage — one command instead of a conversation

## Why this exists (MEASURED)

`DRIFT:DM_STORM` was measured this session: **7 of 19 owner turns (37 %)** were
automated Herdr/watcher DMs. Each one cost the owner three turns — read the
measurement, write a reply, close the record — and each interruption displaced
the task in flight. The work those turns did is mechanical: read one DM file,
parse its structured fields, re-measure the claim, name the ceiling and the
owner, write a reply. `_main/dm-triage.py` does that as one deterministic job.

The tool writes **only** the reply body to stdout and machine facts to stderr.
It never sends a DM, never writes under `I:/!watcher/state/`, and never edits
`AGENTS.md`.

## The four classes

| class | detected from | claim parsed from | re-measurement |
|---|---|---|---|
| `STUTTER-io` | subject starts `STUTTER` and mentions `MB/s`, `ops/s` or logical I/O | `io <n>MB/s` in the subject (firing tick), e.g. `22.8MB/s` | psutil `io_counters` deltas: read/write MB/s, ops/s, bytes/op, cumulative whole-life counters |
| `STUTTER-cpu` | subject starts `STUTTER` without an I/O mark | `cpu <n>%` in the subject, e.g. `153.5%` | psutil `cpu_times` delta as % of one core, plus per-thread CPU by `tid` |
| `COMMIT-pressure` | subject starts `COMMIT` / body has `PRIVATE-COMMIT RESERVATION` | `numbers = private=<n> GB rss=<n> GB` | psutil `memory_info().private` and `.rss` in GiB |
| `RELIEF/refutation` | subject starts `RELIEF`, `RE:`, `MEASURED:`, contains `REFUTED`, or the body has `## Answer: REFUTED` / `## Advisory` | first `MB/s` or `% of (one core\|machine)` in the subject | the matching I/O or CPU re-measurement |

Classes not in this table (window reports, artefact-budget alerts) are refused
by name, not guessed into one of the four.

## The mandatory sections of every reply

1. **IDENTITY** — the accused pid and its parent chain walked live with
   psutil, cwd per node, the owning predicate (cwd/cmdline contains the
   declared project root), and the pid I do own.
2. **CEILING** — the DM's `ceiling =` text quoted **with its source line**.
   If the DM has no ceiling line (COMMIT and cooperative RELIEF cards often
   have none), the tool quotes the strongest cap token it actually finds with
   that line number, or says `NOT DECLARED in this DM`. It never invents a cap.
3. **MEASURED PAIR** — the DM's number **and** mine, with units and the
   declared measurement window (`--window`, default 5 s), plus cumulative
   whole-life counters. A reply that only restates the DM's number is not a
   re-measurement.
4. **MECHANISM** — derived from the measurement: bytes/op for I/O (small-op
   traffic is page-cache/pipe traffic, not a disk copy), top thread CPU for
   CPU claims, private/rss ratio for commit.
5. **WHAT I DID ABOUT IT** — no lever applied by the tool; what the ceiling
   already enforces, and what the owning lane must decide.
6. **VERDICT** — exactly one of `REFUTE`, `ACCEPT`, `MISATTRIBUTED`, with the
   pid I own.

`REFUTE` is issued only with an arithmetic basis: a quoted rate cannot require
more bytes than the live tree has ever moved (`quoted_MB_s * quoted_window_s <=
cumulative_bytes`), or the chain is foreign. `ACCEPT` means ownership is mine
and the claim is not impossible — *not* that a past spike was reproduced now.
A dead or foreign culprit is `MISATTRIBUTED` only when it is still alive and
can be measured; a dead culprit is a hard refusal.

## One-command flow

```sh
# 1. Triage ONE record. Reply on stdout, machine facts on stderr. Nothing is sent.
python _main/dm-triage.py I:/!watcher/state/herdr-inbox/dm-<id>.md > reply.md

# 2. Send that exact body (use --body-file: a shell-quoted --body executes backticks).
python I:/!watcher/tools/herdr-dm.py --from <lane> --subject "RE: <id>" --body-file reply.md

# 3. Close the record you answered.
python I:/!watcher/tools/herdr-mail.py close <id>
```

Step 1 exits `0` with a body, `3` with a named refusal and no body. Do not run
steps 2–3 on a refusal — route it to the lane that owns the pid instead.

Useful arms:

```sh
python _main/dm-triage.py <dm-file> --window 5           # declared window (default 5 s)
python _main/dm-triage.py <dm-file> --facts-only         # parse-derived facts, no sampling
python _main/dm-triage.py <dm-file> --root H:\\sotto      # override owning root
```

## Refusals

The tool refuses by name, with the line that failed; it does not improvise a
reply:

```
DM-TRIAGE CANNOT-MEASURE why=dead-pid       line=<n> text='culprit = ...' pid=<pid>
DM-TRIAGE CANNOT-MEASURE why=unparsed-section line=<n> text='...'
DM-TRIAGE CANNOT-MEASURE why=counters-unreadable pid=<pid> exception=<type>
```

`dead-pid` and `unparsed-section` are hard refusals (exit 3, no body): the
claim was a spike and the pid is gone, so no current reading can confirm or
refute it. `foreign-tree` is a **soft** refusal (exit 0): the tool cannot
accept the claim as mine, so the body starts with
`DM-TRIAGE CANNOT-MEASURE why=foreign-tree line=<n> pid=<pid> root=<root>` and
re-measures the pid read-only for the census, ending `MISATTRIBUTED` with the
pid I do own. It never caps, trims or kills a foreign tree.

## Determinism

`--facts-only` prints only parse-derived facts (id, class, culprit, claim,
ceiling with source, DM chain, live chain, stable owned pid). Two consecutive
runs on the same file are byte-identical and can be diffed. The full body
carries a **live** psutil measurement over a declared window, so its numbers
change between runs by design; its classification, identity and verdict are
stable for the same live pid.

## Measured receipts (this box, 2026-11-26)

| DM file | class | DM number vs mine | verdict |
|---|---|---|---|
| `dm-b235d8a6f6f6be15b629.md` | `STUTTER-cpu` | `cpu 85 %` vs `0.00 %` of one core over 5 s, chrome.exe(61752), foreign chain | `MISATTRIBUTED`, own pid 93064 |
| `dm-3bfb9eec70a298d69eaa.md` | `COMMIT-pressure` | `private 1.08 GB / rss 0.16 GB` vs `0.857 GiB / 0.171 GiB` over 5 s | `MISATTRIBUTED` |
| `dm-39c0024fd4665535bc9c.md` | `RELIEF/refutation` | `9.7 % of machine` vs `1.88 %` of one core over 5 s (`=194 %` of one core after machine-to-core conversion); foreign cmd.exe(72184) | `MISATTRIBUTED`, own pid 93064 |
| `dm-09bac6bff44345aeb5f7.md` | `RELIEF/refutation` | `9.4 % of machine = 188.0 %` of one core vs `150.00 %` of one core over 4 s, live pwsh.exe(93064), top thread tid=96684 at 113.67 % | `ACCEPT`, own pid 93064 |
| `dm-62a363448a9b46ef11c4.md` | `STUTTER-io` | no reading: culprit cmd.exe(32908) is gone | hard refusal `why=dead-pid` |

An owned tree with an impossible quote (temp fixture, live python.exe(56360),
3.6 MB ever moved) produces `76 MB/s x 60 s = 4,560 MB required against 3.6 MB
ever moved` and verdict `REFUTE`.

## What this tool still cannot decide

- Whether a past CPU spike was real: the DM's `measured =` is a firing-tick
  spike; a low current rate is printed, never used alone to refute the tick.
- The rate inside a kernel Job Object: the DMs themselves say it is
  unreadable from outside; the tool quotes the DM's ceiling line and does not
  claim to have read the cap.
- Whether a plausible-looking rate came from a recycled pid inheriting a
  carried counter (`_io_last` keyed by pid): the cumulative bound catches an
  impossible rate, not a plausible stale one.
- Friendly thread names: psutil exposes `tid` only, so per-thread CPU is
  reported by `tid`.
- Ownership when cwd and cmdline are both `AccessDenied`: it is reported as
  unreadable and treated as **not mine**, never guessed mine.
- The source-level fix: the tool yields measured facts for the owning lane;
  which file:line to change remains a lane decision.

## Invariants

- One DM file in, one reply body out; no mailbox writes by the triage tool.
- One owning predicate (project root in cwd/cmdline) shared by identity and
  verdict; no per-class exception.
- One comparator for refutation (cumulative counters bound the quoted rate).
- A ceiling is quoted with its source line or declared `NOT DECLARED`; never
  fabricated.

## A DM that declares itself CANNOT-MEASURE has no rate to judge (measured 2026-11-26)

`dm-81956decf09eec356bb0` arrived with the watcher's own honest refusal inside the subject:

    STUTTER (owner): python.exe(72760) is the top measured pressure, signals: tick-gap,
    not-scheduled — CANNOT-MEASURE this tree's rate: the governor's tick was stalled
    (tick-gap, not-scheduled), so the sampled number is a queue position, not the culprit's CPU

and the tool answered `DM-TRIAGE CANNOT-MEASURE why=unparsed-section line=4` — honest, because it
invented no number, and useless, because the checkable half of that DM is its **identity and chain**.

- **Class `STUTTER-unmeasured`** (subject contains `stutter` and `cannot-measure`) yields a
  `Claim(metric="identity")`. The rate is then refused **by name**
  (`DM-TRIAGE CANNOT-MEASURE why=no-rate-in-claim`) and never printed as a `0.0` dressed as a
  measurement.
- **A dead culprit is not a foreign culprit.** With no live pid, ownership is still provable from
  the DM's own declared ancestors (`proof=ancestor-pid=<p>`), because a battery step routinely ends
  before the question arrives; when neither the pid nor any declared ancestor is alive and mine,
  the verdict is `UNKNOWN`, not `MISATTRIBUTED` (which asserts that the tree belongs to someone
  else).
- `--facts-only` wins over the identity short-circuit, so parsing can be inspected with no live
  sampling at all.
- Oracle: `_main/dm-triage-oracle.py` — arms a–f and three module mutants
  (`NEG-ARM: PASS -- 3 caught, 0 missed of 3`, rc 1). Battery row `dm-triage` +
  `red-as-expected-dm-triage` is owed: the `.cmd` must not be edited while a run is in flight.
