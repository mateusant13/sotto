# RECEIPT — the ring cap prices system RAM against VRAM (2026-10-07)

**This is the decision I am asking the owner to make, and it is his call, not mine.**
Everything here is MEASURED on this box unless marked otherwise.

## The defect, in one line of code

`src/capture/d3d11_ctx.cpp:66-75`:

```cpp
uint64_t D3d11Context::ring_cap_bytes() const
{
    // Law 7: budget the ring from the measured hardware class, then derive seconds.
    // clamp(VRAM/16, 256 MiB, 2048 MiB).
    uint64_t cap = info.dedicated_vram / 16;      // <-- line 70
    ...
}
```

**The arena is system RAM. The budget divisor is video RAM.**

MEASURED: the ring arena is a `std::vector<uint8_t>` (`ring_buffer.cpp:15`,
`arena_.assign(capacity_bytes, 0)`) — one heap allocation on system RAM, committed
in full at `init()`. Nothing in the ring path allocates VRAM. So the cap prices
bytes from a pool the ring never draws from.

## What it costs, measured

| | value | source |
|---|---|---|
| **System RAM on this box** | **51 262 832 640 B = 47.74 GiB** | `Get-CimInstance Win32_ComputerSystem` |
| DXGI `DedicatedVideoMemory` (what the code reads) | 15 979 MiB | `d3d11_ctx.cpp:70` |
| Cap that produces | 15 979/16 = **998.69 MiB** | arithmetic |
| **Cap as a fraction of the pool actually being consumed** | **2.0% of 47.74 GiB** | arithmetic |

**The cap is simultaneously too tight for the job and absurdly loose as a fraction
of the resource.** It binds at 2% of RAM.

### The user-visible consequence (this is the part that matters)

MEASURED log evidence — `arm-A-gaming-default-ring.txt:12` prints
*"the GPU class caps at 998 MB"*. The arithmetic, at the code's own bitrate law
(`replay.cpp:98-102`):

| mode | resolution | wants (120 s) | kept | |
|---|---|---|---|---|
| gaming | 1080p60 | 643.7 MiB | **120 s** | fits |
| gaming | 1440p60 | 1 144.4 MiB | **104.7 s** | **clipped** |
| gaming | 4K60 | 2 574.9 MiB | **46.5 s** | **clipped** |

**At 4K60 the ring silently keeps 46.5 s, not the 120 s the spec promises.**
And `AGENTS.md:151` reasons about "what breaks a **16 GB box**" — **this box has
47.74 GiB.** That single sentence is the root of the sizing error.

Two corroborating code defects, both MEASURED by reading the source:
- `replay.cpp:112-115` computes `seconds_kept` correctly, then `replay.cpp:125`
  is literally `(void)seconds_kept;` — the corrected number is **thrown away**.
- `main.cpp:232` lets `--ring-mb` override the cap with **no clamp**
  (`replay.cpp:109-111`); `arm-E-ring-1024.txt` prints "the GPU class caps at 998 MB;
  **CHOSE 1024 MB**" — it announces the cap it just exceeded.

## The recommendation (a judgement, wrapped in arithmetic)

> **Derive the cap from system RAM, not VRAM: `cap = min(4096 MiB, 0.25 × TotalPhysicalMemory)`.**
> On this box the 4 GiB ceiling binds (25% would be 11.9 GiB).

| resolution | today | with a 4 GiB cap |
|---|---|---|
| 1080p60 gaming | 643.7 MiB → 120 s | **unchanged — 120 s** |
| 1440p60 gaming | 104.7 s (clipped) | **120 s restored** |
| 4K60 gaming | 46.5 s (clipped) | **120 s restored** (1 521 MiB spare) |

Worst case peak RSS = `48 MB + ≈1.02 × 4 GiB` ≈ **4.13 GiB = 8.6% of 47.74 GiB.**
The casual-user path is untouched: 1080p60 still selects 643.7 MiB.
**VRAM remains the right constraint for the encode path** — that is the one place
it legitimately belongs.

## What is NOT verified, by name
- **N=0 executions at 1440p or 4K.** `replay.cpp:57` hard-codes the test window to
  1920×1080, so every 4K/1440p number above is **arithmetic, not measurement**.
  Only the 1080p60 row is corroborated by a run.
- **The owner's real content bitrate is unmeasured** (`specs/03:277-278`). The
  45/80/180 Mbps inputs are judgement, and the synthetic desktop harness
  overshoots its target by a measured **2.00×**, so desktop 600 s may really be ~300 s.
- **No soak past 40 s.** `entries_` compaction and sustained eviction are UNVERIFIED.
- **A logical ring shrink returns ZERO RAM to the OS**, because the arena is
  committed in full at `init()` (arm C: 572 MiB arena, only 69 MB of real content at
  the cut, yet peak RSS 634 MB). "Reclaim ring budget when busy" as a *memory*
  lever therefore requires re-allocating the arena — a design change, not a knob.
- **The C++ builds (rc=0, 23 s, zero warnings) and arms (rc=0, 0.3 s, NV12 texture
  registered AND mapped).** That is N=1 each. **It does not need a rewrite** —
  these are localised policy/arithmetic fixes.

## THE DECISION FOR THE OWNER
1. Cap from **system RAM** (4 GiB) or keep **VRAM** (998.69 MiB)?
2. Must "reclaim ring budget" return actual RAM, or may it only shorten the window?
3. Is `--ring-mb` above the cap a bug or an intended override?
