# RECEIPT 32 — lane 3 ring-cap defects: the six review findings, closed

**Lane:** L3 (ring-buffer budget). **Date:** 2026-10-07. **Reviewer verdict received: FAIL,
six findings.** This receipt is the fix, not a re-argument.

Files this lane changed (and only these):

| file | change |
|---|---|
| `src/capture/ring_buffer.h` | `RingBudget` gains the availability term; **`ring_budget_from()`** — the policy as a pure function of two numbers; the header now states which pool each term prices |
| `src/capture/ring_buffer.cpp` | three-term policy; the allocation is inside `try { … } catch`; `init()` logs `capacity()` after the commit |
| `src/capture/replay.cpp` | lines 128–133 and 145–162 **only** (F4 hookup, F6 honest log) |
| `receipts/receipt-16-ring-cap-from-system-ram.md` | F1 number, F3 provenance, superseded-section markers |
| `_main/_lane3-ringcap-gate.ps1` | F3 citations, ARM-B now reads the shipped source, **ARM-F synthetic machines**, ARM-G source-level regressions, N=1 statement |
| `_main/_lane3-ringcap-falsify.ps1` | unchanged in behaviour (comment-only pass) |

**Not touched:** `d3d11_ctx.*`, `main.cpp`, `_lane3_ringcap_probe.cpp`,
`_lane3_ringcap_control_budget.cpp`, and every path the brief put off-limits.

Gates, both colours, one command each (rc read from `$LASTEXITCODE`, never through a pipe):

```
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane3-ringcap-gate.ps1
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane3-ringcap-falsify.ps1
```

---

## F1 — a published number was wrong and self-contradictory · **FIXED**

`receipt-16:52` said *"25 % of RAM would be 11 934 MiB"*. The code, the probe and
`receipt-16:42` all said **12 222 MiB**. 12 222 is correct: 48 888 MiB / 4.

The error, named so it is not repeated: the 25 % was computed from **47.742 GiB** and then
written in **MiB**. Dividing GiB by 4 and calling the result MiB divides by 1024 twice — the
answer came out 11 934 instead of 12 222. Receipt-16 now carries the number **and** that one
line of explanation.

*Independent check (POPULATION: 3 computations, all agreeing):* `Get-CimInstance
Win32_ComputerSystem` 51 262 832 640 B → `GlobalMemoryStatusEx` in the probe → the log line
`RING BUDGET: 48888 MiB physical RAM … 25% = 12222 MiB` observed in three separate live runs.
All three give 12 222 MiB.

## F2 — the allocation-failure branch was dead code and the process aborted · **FIXED, BOTH HALVES**

**Half 1 — the dead branch is gone.** `arena_.assign()` now runs inside
`try { … } catch (const std::bad_alloc&)`, plus a `catch (const std::length_error&)`. On
failure `init()` returns `false` with the requested size, the budget it allowed and the
availability it saw. The old `if (arena_.size() != capacity_bytes)` line was unreachable
(`assign` throws or succeeds; it never returns short) — it is kept only as a
"came back short" assertion with a different message, and the gate asserts it exists.

**Half 2 — the budget question, answered rather than left ambiguous.** The header now says
which pool prices which term, and the code does both:

```
cap = min( 4 GiB,                     // "do not eat the machine"
           25% of TotalPhys,         // proportional to the MACHINE
           50% of AvailPhys )        // proportional to what can be COMMITTED NOW
floor at 256 MiB, MiB-aligned down
```

- **TOTAL carries the proportional rule** so a budget does not shrink every time the owner
  opens a browser.
- **AVAILABILITY carries the guard** because availability, not total, decides whether the
  commit succeeds. This is the reviewer's point, taken literally: the old code priced off
  total while success depended on availability, and the 4 096 MiB ceiling made a 4 GiB commit
  reachable on a machine that cannot honour it.

**MEASURED on this host** (`_main/build/lane3-f6-after.log`, `lane3-f6-want-over-cap.log`):
total 48 888 MiB, available **25 302 / 24 725 / 24 832 MiB** across the three runs
(POPULATION: 3 samples, one run each) → 50 % of available = 12 651 / 12 362 / 12 416 MiB, so
the availability term **does not bind here** and the cap stays **4096 MiB**, ceiling-binds.
The guard is therefore *inert on this host* — which is exactly why gate ARM-F tests it on a
synthetic machine that is not this one.

**Falsification of the guard, ARM-F `availability_guard_binds`:** the same 48 888 MiB machine
with 2 GiB free yields **cap 1024 MiB** with `availability_binds=1` — the cap falls instead of
committing 4 GiB that cannot be committed.

## F3 — stale provenance citation · **FIXED**

`receipt-16:63` and the gate (`_lane3-ringcap-gate.ps1:17-18,187-188,305` in the pre-fix file)
claimed `replay.cpp:57` pins the window at 1920×1080. **Lane L7 lifted that clamp at 12:26**;
`replay.cpp:38-42` documents the lift and the window is negotiated at runtime
(`test_window.cpp: negotiate_capture_window`).

**The conclusion survives — N = 0 runs above 1080p exist here — but the reason changed:**
this host's only monitor is 1920×1080 and **WGC refuses every capture item**
(`0x80070005 E_ACCESSDENIED`, `receipt-18` §2). Nothing above 1080p can be captured here at
all. Receipt-16, the gate header, the ARM-C description and the gate's own output line now
say that, and explicitly record that the old reason was the removed clamp.

## F4 — the live path was still priced from VRAM · **DELIVERED**

`replay.cpp:130` now reads `ring_budget_cap_bytes()` (system RAM) instead of
`d3d_.ring_cap_bytes()` (VRAM). The user-visible defect — 4K60 clipped to ~46.5 s — is no
longer live.

**MEASURED, same binary, same run** (`_main/build/lane3-f6-after.log`):
`the system-RAM budget caps at 4096 MB` where the pre-fix binary printed
`the GPU class caps at 998 MB`.

Gate ARM-E now asserts `hookup_is_applied_in_replay_cpp` (and ARM-G
`live_path_does_not_read_the_vram_cap` / `live_path_reads_the_ram_budget`). The earlier arm
deliberately did **not** assert which side of the line the tree was on, because that would have
punished the fix; now that the fix is in, a revert is a regression and is asserted.

**What is still DERIVED, and labelled as such:** the 4K60 row (120.00 s restored) is
arithmetic at the code's own bitrate law. It cannot be measured on this host (F3).

## F6 — the log line lied · **EXECUTED, and it did lie**

The reviewer marked this a hypothesis at N=0 executions and asked for the run rather than a
fix on trust. **The hypothesis is CONFIRMED, N=1 execution, pre-fix binary.**

`_main/build/_lane3-before/replay.cpp` is the live file with only this lane's block reverted,
compiled to `_main/build/lane3-ringapp-before.exe`; the fixed tree compiled to
`lane3-ringapp.exe`. Both were run `--run --ring-mb 8192 --seconds 1`.

**BEFORE** (`_main/build/lane3-f6-before.log`) — the log and the arena disagree by 2×:
```
  RING DECISION … the GPU class caps at 998 MB; CHOSE 8192 MB = 1527.1 s     <-- the lie
  RING ARENA:     asked 8192 MiB, holding 4096 MiB of SYSTEM RAM [CLAMPED …]
  RING ARENA COMMITTED: capacity() = 4096 MiB (4294967296 bytes)
```

**AFTER** (`_main/build/lane3-f6-after.log`) — the log now prints the committed size:
```
  RING DECISION … the system-RAM budget caps at 4096 MB; CHOSE 4096 MB = 763 s  [CLAMPED …]
  RING ARENA COMMITTED: capacity() = 4096 MiB (4294967296 bytes)
```

The second branch was executed too (`lane3-f6-want-over-cap.log`, `--bitrate 400000000
--ring-seconds 120`, which is the path 4K60 would take):
`would need 5722 MB; the system-RAM budget caps at 4096 MB; CHOSE 4096 MB = 85 s
[SHORTENED to fit the RAM budget]`, `capacity() = 4096 MiB`.

Fix: the clamp is now applied **before** anything is printed —
`ring_cap_ = ring_apply_budget(chose, query_ring_budget())` — and `seconds_kept` is printed
instead of discarded at the old `(void)seconds_kept;`. `ring_cap_` is what `init()` receives,
so `init()`'s internal clamp is now the backstop rather than the only one. `init()` also logs
`capacity()` after the commit, which is what made this comparison possible at all.

**What the runs do NOT prove:** both runs exit **2** at `CreateForWindow failed 0x80070005` —
the WGC refusal from receipt-18 §2, downstream of the ring. The ring-decision and arena lines
are from the real live path (`arm()`), not a probe; the capture half never ran and could not
on this host.

## Gate blindness — two of three policy terms were unobservable here · **CLOSED**

`min(4 GiB, 25 % × 47.74 GiB) = 4 GiB` for any fraction ≥ 8.38 %, and the 256 MiB floor binds
only below 1 GiB of RAM, so ARM A could only ever observe **the ceiling**. The lane had already
built the right seam (`ring_apply_budget`, pure) and then only exercised it against the real
machine.

**New ARM-F — SYNTHETIC MACHINES.** The policy is now a pure function,
`ring_budget_from(total, avail, ok)`, and ARM-F runs the shipped code against machines that are
not this one (instrument generated into `_main/build/_lane3_synth_probe.cpp` on every run, so
no other lane's probe file is edited and the expectations cannot drift):

| synthetic machine | cap | binding term |
|---|---|---|
| 64 GiB | 4096 MiB | **ceiling** (25 % would be 16 GiB) |
| 16 GiB | 4096 MiB | the **25 % term lands exactly on the ceiling** (`quarter_mib=4096`, `ceiling_binds=0`) |
| 8 GiB | 2048 MiB | 25 % term, alone |
| 2 GiB | 512 MiB | 25 % term, floor free |
| 1 GiB | 256 MiB | 25 % term == the floor, `floor_applied=0` |
| 512 MiB | 256 MiB | **floor binds** (`quarter_mib=128`) |
| 48 888 MiB, 2 GiB free | 1024 MiB | **availability guard** |
| query failed | 256 MiB | floor, `query_ok=0` reported |

Plus the clamp itself on synthetic machines: `ring_apply_budget(8 GiB)` = 2048 MiB on the
8 GiB machine, 1024 MiB on the low-availability machine, and 512 MiB passed through untouched.
**15 checks, POPULATION: 1 compile + 1 execution.**

**ARM-B now READS the shipped source.** It used to re-implement `d3d11_ctx.cpp:70`'s formula
inside the probe, so an edit to that line left the arm green forever — it measured the probe,
not the code. The gate now parses the divisor and both clamps out of
`D3d11Context::ring_cap_bytes()` and recomputes from the **parsed** values (`/16`, 256 MiB,
2048 MiB → 998 MiB). Change `/16` to `/8` and the expected value becomes 1997 MiB against the
probe's 998 and the arm goes RED. If the parse fails, the arm fails loudly.

**New ARM-G — source-level regressions** (10 checks) hold without running anything: the call
site reads the RAM budget and not the VRAM cap, the CHOSE log prints `ring_cap_`, the
discarded `seconds_kept` is gone, the allocation is inside a `catch`, and the header names
both memory pools.

## N = 1 — stated plainly, because the reviewer asked

**Every PASS in `_lane3-ringcap-gate.ps1` is N = 1: one compile, one execution, one host, one
moment. NO FLAKINESS CLAIM IS MADE FOR ANY ARM — including the ones that have been green
repeatedly (A–D).** The gate now prints that on every run instead of leaving it to be
remembered.

Two arms carry a genuine race: the probe reads availability at its moment and ARM A's
independent recompute reads it at another. Rather than tolerate the difference or report a
phantom defect, the gate **refuses with exit 2 and names the reason** when free memory drops
below 8 GiB (`LANE3-GATE REFUSED: only N MiB of RAM is free … (The ring is not implicated.)`).
Measured free memory across this session: 23.5 / 24.7 / 24.8 / 24.9 GiB — POPULATION 5 reads,
WINDOW: one afternoon. That is a margin, not a flakiness measurement.

A second defect I found **in the gate's own output** and fixed: this host's locale renders the
thousands separator as `.`, so `{0:N0}` printed `48.888 MiB` where it meant 48 888 MiB — the
same class of wrong number F1 was about, one layer down. The gate now prints plain integers.

## What is NOT verified, by name

- **The working control is intact and was exercised.** ARM-D still goes RED under
  `_lane3-ringcap-falsify.ps1` (gate rc=1, evidence restored and SHA-256 verified) —
  `FALSIFY VERDICT PASS`. The reviewer confirmed this arm genuinely fails; this lane re-ran it.
- **A real allocation failure has NOT been provoked.** The `catch` is present and compiles,
  but forcing `std::bad_alloc` for a 4 GiB arena would mean consuming this host's RAM, and
  ARM-F tests the *guard* (which lowers the cap on a low-availability machine) rather than the
  throw. The `catch` path is UNVERIFIED at runtime.
- **4K60 remains DERIVED**, for the F3 reason. Nothing changed about that.
- **A clamp returns no RAM.** receipt-14 arm C measured it: the arena is committed in full at
  `init()`, so shrinking the window does not give memory back. Three 4 096 MiB arenas were
  committed by this lane's runs, sequentially, and released at exit.
- **No soak.** `entries_` compaction and sustained eviction remain UNVERIFIED past 40 s.
- **Concurrent lanes.** `replay.cpp` and `run_battery.ps1` moved under lane 3 at ~12:26 and
  again at ~13:09 (test-window/hotkey work). This lane's edits are confined to the ring budget
  block; another lane's `git commit -a` has already swept these bytes into a commit attributed
  to it (`066005d`) — **do not read that sha as a ring-cap commit.** This lane made **no
  commit**: the brief for this lane did not ask for one.
- **Window disclosure.** Each of the three `--run` executions mapped the app's own capture
  test window for its lifetime (`WINDOW CENSUS: visible_samples_peak=1`; `test_window.cpp`
  places only a 4×4 px corner of a 1920×1080 window on the desktop). That window is the
  capture path's own design, it is not a console, and the launches used
  `CreateNoWindow = true` + `UseShellExecute = false`. No `python`/console window was created.

## Named verification boxes created by this lane

1. **ARM-F / synthetic machines** — the three policy terms on machines that are not this host.
2. **ARM-B / shipped-source parse** — the OLD cap recomputed from `d3d11_ctx.cpp` itself.
   **Falsified, so it is not vacuous:** re-running the gate's own parse against a *doctored
   copy* of `d3d11_ctx.cpp` (divisor `/16` → `/8`) yields an expected cap of **1997 MiB**
   while the probe still prints 998 — ARM-B would go RED. The other lane's file was not
   modified to prove this; the copy was written to `_main\build` and deleted.
3. **ARM-G / source-level regressions** — hookup, honest log, caught allocation, stated basis.
4. **F6 pre-fix vs post-fix pair** — the same `--ring-mb 8192` run on two binaries, compared
   against `capacity()`.
5. **ARM-A race refusal** — the gate exits 2 with a named reason instead of a phantom FAIL.

## Verification status of this lane

- **Gate: `LANE3-GATE PASS`, rc=0.** Falsify: `FALSIFY VERDICT PASS`, rc=0 (ARM-D red,
  gate rc=1, evidence restored, SHA-256 `h=True c=True`).
- **App build from the current tree: rc=0, zero bytes of compiler output** (no warnings).
- **NO INDEPENDENT REVIEWER WAS DISPATCHED — this session exposes no dispatch tool.** The
  brief asked for a verifier and this lane cannot produce one: the only task tools available
  here are `task_query` / `task_output` / `task_stop`, which can read background tasks but
  cannot start one. **Everything above is this lane's own measurement and self-audit, exactly
  as receipt-16 was.** The smallest thing the parent has to do: dispatch a verifier with this
  receipt, the six findings, and the files above; the two arms most worth its attention are
  **F2's runtime `catch` path** (present, compiled, never provoked) and **F6's N=1 execution**
  (one run per branch, no repetition).