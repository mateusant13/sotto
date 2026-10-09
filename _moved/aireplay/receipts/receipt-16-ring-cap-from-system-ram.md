# RECEIPT — the ring cap is now priced against SYSTEM RAM (lane 3)

> **PARTLY SUPERSEDED — read `receipt-32-ring-defects-closed.md` (2026-10-07) first.**
> An independent review returned FAIL with six findings against this receipt and the code it
> describes. What changed since this file was written: the `replay.cpp:130` hookup is now
> **DELIVERED** (not "bounded"), the budget carries a **third term** (50 % of *available*
> RAM, not only of total), the arena allocation is inside a `catch`, and `--ring-mb` is now
> clamped instead of bypassing the cap. Sections below that describe the earlier state are
> marked **[SUPERSEDED]** and are kept for the record, not as current claims.

**Everything here is MEASURED on this box unless the text says DERIVED.**
Supersedes the *recommendation* of `receipt-14-ring-cap-vram-vs-ram.md`. I **agree** with
receipt-14's diagnosis and its arithmetic; the disagreement recorded below is narrow and is
about what receipt-14 did not measure.

Gate (both colours, one command each):
```
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane3-ringcap-gate.ps1
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane3-ringcap-falsify.ps1
```

## The defect

`src/capture/d3d11_ctx.cpp:70` priced the ring budget from DXGI `DedicatedVideoMemory`
(`cap = vram/16`, clamped 256 MiB..2048 MiB), while the arena it bounds is
`std::vector<uint8_t>` — **system RAM**, committed in full at `init()`
(`ring_buffer.cpp`, `arena_.assign(capacity_bytes, 0)`).

## What changed — files I own, and only these

| file | change |
|---|---|
| `src/capture/ring_buffer.h` | new `RingBudget` struct + `query_ring_budget()`, `ring_budget_cap_bytes()`, `ring_apply_budget()`; `RingBuffer::budget()`, `clamped_from()`; members `budget_`, `clamped_from_` |
| `src/capture/ring_buffer.cpp` | `query_ring_budget()` = `min(4 GiB, 25% of TotalPhysicalMemory)`, floored 256 MiB, MiB-aligned down; `init()` enforces + LOGS it |

Policy, in code:
```
cap = min(4 GiB, floor_to_MiB(TotalPhysicalMemory / 4));  if (cap < 256 MiB) cap = 256 MiB
```
**[receipt-32 §F2 — that is the policy as of THIS receipt. The shipped code now has a third
term: `cap = min(4 GiB, 25 % of TotalPhysicalMemory, 50 % of AvailPhysicalMemory)`, floored
256 MiB. TOTAL carries the proportional rule, AVAILABILITY carries the guard.]**
- **4 GiB ceiling** — do not eat the machine.
- **25% rule** — proportional.
- **256 MiB floor** — an explicit floor so a small machine still gets a usable buffer
  (distinct from `init()`'s pre-existing 16 MiB cuttability refusal, which is a different law).
- MiB-aligned **down**, because a budget is an upper bound.
- `GlobalMemoryStatusEx` failing is **not** disguised as a measurement: the floor is used and
  the log line says `[QUERY FAILED]`.

Queryable at runtime and logged by `init()` on the live path:
```
RING BUDGET: 48888 MiB physical RAM -> 25% = 12222 MiB -> cap 4096 MiB (ceiling BINDS, floor free)
RING ARENA: asked 643 MiB, holding 643 MiB of SYSTEM RAM
```

## The numbers — OLD and NEW, with the cap's share of the pool that is actually consumed

| | OLD (`d3d11_ctx.cpp:70`) | NEW (`ring_buffer.cpp`) |
|---|---|---|
| cap | **998 MiB** (15 979 MiB VRAM / 16) | **4096 MiB** |
| as a share of **system RAM** (47.74 GiB) | **2.04 %** | **8.38 %** |
| binding constraint | the VRAM pool (irrelevant to a heap vector) | the 4 GiB ceiling (25 % of RAM would be 12 222 MiB) |

**CORRECTED 2026-10-07 — the 25 % figure was wrong and self-contradictory.** This row said
**11 934 MiB** while `:42` three lines up logged **12 222 MiB**. 12 222 is right:
48 888 MiB / 4 = 12 222 MiB. The 11 934 came from dividing **47.742 GiB by 4 and writing the
result in MiB without converting** — i.e. treating the GiB figure as if it were MiB, which
scales the answer by 1/1024. A reader who only had this row would carry the wrong number.

Source of the OLD number, cross-checked two ways: DXGI `DedicatedVideoMemory` read live by the
probe (**16 755 195 904 B = 15 979 MiB**) **and** the shipped run log
`_main/logs/arm-A-gaming-default-ring.txt`, which printed `vram=15979MB` and
*"the GPU class caps at 998 MB"*. Gate ARM-B asserts the reproduction still equals that log.

## Seconds of ring — 1080p60 and 4K60, OLD vs NEW

**BASIS: DERIVED — arithmetic at the code's own law (`replay.cpp:98-102`, anchor 45 Mbps at
1080p60, 120 s window). It is NOT a measurement of a 4K run.**
**CORRECTED 2026-10-07: the reason this row is DERIVED is no longer "a literal clamp".** This
receipt cited `replay.cpp:57` pinning the capture window at 1920x1080. Lane L7 lifted that
clamp at 12:26 — `replay.cpp:38-42` now documents the lift and the window is negotiated at
runtime (`test_window.cpp: negotiate_capture_window`). The CONCLUSION still holds (**N = 0 runs
above 1080p exist on this host**) but for a different reason: this host's only monitor is
1920x1080, and WGC refuses every capture item with `0x80070005 E_ACCESSDENIED`
(`receipt-18-capture-capability-battery.md` §2). Nothing above 1080p can be captured here at
all.

| mode | bitrate | wants (120 s) | OLD keeps | NEW keeps |
|---|---|---|---|---|
| gaming 1080p60 | 45.00 Mbps | 643.73 MiB | 186.17 s — fits | 763.55 s — fits |
| gaming 4K60 | 180.00 Mbps | 2 574.92 MiB | **46.54 s — CLIPPED** | 190.89 s — 120 s restored |

The 1080p60 *want* (643 MiB) is corroborated by a MEASURED run (arm-A log: `CHOSE 643 MB =
120.0 s`). The seconds-under-a-cap are still DERIVED for both rows.

## THE PART THAT MATTERS: the fix is bounded, NOT yet delivered end-to-end

**[SUPERSEDED by receipt-32 §F4 — the hookup IS now applied. `replay.cpp:130` reads
`ring_budget_cap_bytes()`, so the app asks for the RAM budget. The paragraph below describes
the state BEFORE that, and is kept because receipt-32's measurement is easier to read against
it. What it says about "ceiling the caller never reaches" is no longer true.]**

`replay.cpp:130` still calls `d3d_.ring_cap_bytes()` — the VRAM cap — and passes
`min(want, cap)` into `ring_.init()`. So the new 4 096 MiB cap is today a **ceiling the
caller never reaches**: the old 998 MiB value passes straight through the new clamp untouched.
Gate ARM-E measures this rather than hiding it:

| 4K60 | chosen today | seconds |
|---|---|---|
| with `replay.cpp` as it stands | 998.69 MiB | **46.54 s (still clipped)** |
| with the hookup applied | 2 574.92 MiB | **120.00 s** |

**The exact hookup for the owner of `replay.cpp` (I do not own that file and did not edit it):**
```cpp
// replay.cpp:130
-    uint64_t cap  = d3d_.ring_cap_bytes();
+    uint64_t cap  = ring_budget_cap_bytes();   // ring_buffer.h — system RAM, not VRAM
```
Nothing else changes: `min(want, cap)` then selects 2 574.92 MiB at 4K60 and 643.73 MiB at
1080p60, both ≤ the 4 096 MiB cap, so `init()`'s clamp stays inert on the normal path.

## Where I disagree with receipt-14

Receipt-14 recommended `min(4096 MiB, 0.25 × TotalPhysicalMemory)` and I implemented it, but it
stated the recommendation **before** any run measured the new policy, and its "4K60 → 120 s
restored" table row was written as if the change were already in effect. It was not: with
`replay.cpp` untouched the app still asks for the VRAM cap. Receipt-14's arithmetic is right;
its framing of the outcome was one step ahead of the code. ARM-E now measures that gap every
run so the claim cannot be inherited unexamined.

## The control (arm D) and its falsification

- ARM-D restores the **pre-change** `ring_buffer.{h,cpp}` in a COPY
  (`_main/_lane3-ringcap-control/*.prefix`, sha256 `D6EA739A…` / `989F7CC3…`) and compiles the
  **same** control source against it. The old ring has no budget API, so it **must fail to
  link**; the same source **must** link against the current code. Both directions are asserted,
  because a control that cannot fail proves nothing.
- `_lane3-ringcap-falsify.ps1` plants the **current** code over the pre-change copy and re-runs
  the gate: ARM-D goes **RED**, the gate exits **1**, and the evidence is restored and verified
  byte-identical by SHA-256 (`FALSIFY VERDICT PASS`).

## Gate bugs this lane found in its OWN gate (recorded because they were masked greens)

1. `$b = Invoke-Native ... + $Libs` appended the link libraries to the **return value**, not to
   `Argv` → probe build rc=1.
2. `Get-ProbeField` anchored every key to the literal prefix `"PROBE "`, but the probe prints
   several pairs per line — every field except the first silently returned `$null`, and `$null`
   compares as a value.
3. A missing field then failed as *three arm checks* rather than as *the parser is blind*; a
   strict "did the probe print these fields" guard now exits 2 before any comparison.
4. Unit confusion: the probe prints MiB, the gate recompute was in bytes; and the OLD cap is
   998.6875 MiB, which the C++ truncates via `>> 20` to 998 — the recompute must truncate too.
5. The falsify script redirected its own stdout into the file it was writing: `pwsh` deadlocked
   and the script fell off the end as an implicit **exit 0**. A masked green on a run that
   proved nothing. Fixed, and every path now exits explicitly.
6. ARM-E originally asserted the `replay.cpp` gap *persists*, which would turn the gate RED the
   day someone applies the hookup. Now informational.

## What is NOT verified, by name

- **The reviewer was NOT dispatched.** This session exposes no `task(...)` tool, so the
  mandatory review in LANE-BRIEF §6 could not be performed. Everything above is my own
  self-audit. **No independent subagent reviewed this.**
- **The full app build is currently RED — not from this lane.** `test_window.cpp:276,288`
  (`'lParam' was not declared in this scope`) belongs to the concurrent hotkey/trigger lane,
  edited minutes before that build. `ring_buffer.cpp` compiles standalone with **rc=0 and zero
  warnings**, and the app built **rc=0** earlier in this lane, before those files changed.
- **N=0 end-to-end runs of the new cap.** No capture run was executed after the change: the
  live path still asks for the VRAM cap (see above), so such a run would measure the old
  number. The 4 GiB arena has never been committed by this code on this box.
  **[SUPERSEDED by receipt-32 §F6 — a 4 096 MiB arena WAS committed by this code on this box,
  three times, by `--ring-mb 8192` and by a 400 Mbps run. Logs in `_main\build\lane3-f6-*.log`.]**
- **No soak.** `entries_` compaction and sustained eviction remain UNVERIFIED past 40 s.
- **A clamp returns no RAM.** As receipt-14 measured (arm C: 572 MiB arena, 69 MB of content,
  634 MB peak RSS), the arena is committed in full at `init()`, so shrinking the window does
  not return memory to the OS.
- **`--ring-mb` still bypasses the cap unclamped** (`replay.cpp:133-135`; `main.cpp:247`). My
  clamp is a backstop inside `init()`, not a replacement for that policy — the owner's
  decision #3 in receipt-14 stands unanswered. **[SUPERSEDED by receipt-32 §F6 — the call
  site now applies `ring_apply_budget()` to the `--ring-mb` value too, EXECUTED with
  `--ring-mb 8192`: the log prints `CHOSE 4096 MB` and `capacity()` is 4096 MiB.]**

## Concurrent-lane collision (recorded so nobody misreads the git history)

Another lane's `git commit -a` at 12:23 swept **my** `ring_buffer.{h,cpp}` into commit
`066005d` ("wake v4: …"), and `replay.cpp`/`run_battery.ps1` moved under me at ~12:26. I made
**no commit** of my own. My bytes are intact and are in HEAD, but they are attributed to
another lane's commit — **do not read `066005d` as a ring-cap commit.**