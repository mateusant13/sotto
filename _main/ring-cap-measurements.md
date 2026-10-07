# Ring cap — measured RAM/VRAM for the owner ceiling decision

Measured 2026-10-07, host = the machine that runs this repo. **No cap was changed.** This is
input to an open owner decision, not a decision.

---

## 0. Premise correction — read this first

The brief said the live clamp is `clamp(0.25 * TotalPhysicalMemory, 256 MiB, 4096 MiB)` and pointed at
`d3d11_ctx.cpp`. **Both parts of that are wrong for the current tree**, and it changes what the
measurements decide:

1. The RAM-based 4 GiB clamp does not live in `d3d11_ctx.cpp`. It lives in
   `capture/ring_buffer.cpp`, in `ring_budget_from()`.
2. The clamp in `d3d11_ctx.cpp` that *does* exist is `clamp(VRAM/16, 256 MiB, 2048 MiB)` — and it is
   **dead code with no callers**. It is not the live cap.

So the measured facts below are still the right facts, but the decision is not "is 4 GiB the right
RAM ceiling" in isolation — it is "which of the two policies should price the arena, and if the RAM
one, is 4 GiB the right ceiling". `ring_buffer.h:31-36` already argues the VRAM one is wrong; §3
gives the numbers behind that argument.

---

## 1. STEP 1 — where the clamp actually is

### 1a. The LIVE policy (three terms, then a floor)

`capture/ring_buffer.cpp:51-54`, inside `ring_budget_from()`:

```cpp
uint64_t cap = b.quarter_bytes;
if (cap > RING_CAP_CEILING) { cap = RING_CAP_CEILING; b.ceiling_binds = true; }
if (b.half_avail_bytes < cap) { cap = b.half_avail_bytes; b.availability_binds = true; }
if (cap < RING_CAP_FLOOR) { cap = RING_CAP_FLOOR; b.floor_applied = true; }
```

with the terms computed at `ring_buffer.cpp:48-49` and the constants at `ring_buffer.cpp:23-25`:

```cpp
b.quarter_bytes    = align_down_mib(total_physical_bytes / 4ull);   // :48  25% of TOTAL
b.half_avail_bytes = align_down_mib(avail_physical_bytes / 2ull);   // :49  50% of AVAILABLE
static const uint64_t RING_CAP_CEILING = 4ull << 30;   // :23  4 GiB
static const uint64_t RING_CAP_FLOOR   = 256ull << 20; // :24  256 MiB
```

So the real expression is **`min(4 GiB, 25% of total RAM, 50% of available RAM)`, floored at
256 MiB** — a three-term policy, not the two-term one in the brief.

### 1b. Where the two numbers come from

`ring_buffer.cpp:59-66` — `GlobalMemoryStatusEx`, one call, no caching:

```cpp
const bool ok = (GlobalMemoryStatusEx(&ms) != 0);
return ring_budget_from((uint64_t)ms.ullTotalPhys, (uint64_t)ms.ullAvailPhys, ok);
```

### 1c. The call path that actually sizes the arena

- `capture/replay.cpp:133` — `uint64_t cap = ring_budget_cap_bytes();`
- `capture/replay.cpp:152` — `ring_cap_ = ring_apply_budget(chose, rbudget);`
- `capture/replay.cpp:190` — `ring_.init((size_t)ring_cap_, err);`
- `capture/ring_buffer.cpp:86` — re-clamped inside `init()`, then committed at `:112`

### 1d. The DEAD policy in `d3d11_ctx.cpp`

`capture/d3d11_ctx.cpp:66-75`:

```cpp
uint64_t D3d11Context::ring_cap_bytes() const
{
    // Law 7: budget the ring from the measured hardware class, then derive seconds.
    // clamp(VRAM/16, 256 MiB, 2048 MiB).
    uint64_t cap = info.dedicated_vram / 16;              // :70
    const uint64_t lo = 256ull << 20, hi = 2048ull << 20; // :71
    ...
}
```

Declaration at `d3d11_ctx.h:35`. A repo-wide grep for `ring_cap_bytes` returns **only** the
declaration, the definition, and one prose mention inside a comment at `replay.cpp:131`. **There is
no call site.** Editing `d3d11_ctx.cpp:70` would change nothing observable.

---

## 2. STEP 2 — every measurement, with source, population and window

Population for rows 1-8 is: **this host, this session, 2026-10-07 ~13:43-13:45 ART**. These are
point-in-time queries against live kernel/driver state, not a survey of other machines.

| # | Measurement | Value | Source | Population | Window |
|---|---|---|---|---|---|
| 1 | Total physical RAM | **48,888.05 MiB** (47.742 GiB) | `GlobalMemoryStatusEx.ullTotalPhys` via P/Invoke — **this is the field the code reads** (`ring_buffer.cpp:65`) | this host | 1 sample (stable; identical across all reads) |
| 2 | Available physical RAM | **24,412.86 – 25,058.61 MiB** | `GlobalMemoryStatusEx.ullAvailPhys` | this host | **7 samples over 30.1 s, 5 s apart** |
| 3 | Total physical RAM (CIM cross-check) | 48,888.05 MiB | `Win32_OperatingSystem.TotalVisibleMemorySize` = 50,061,360 KB | this host | 2 samples — identical |
| 4 | Free physical RAM (CIM cross-check) | 24,681.07 MiB (and 25,191.88 MiB earlier) | `Win32_OperatingSystem.FreePhysicalMemory` | this host | 2 samples ~60 s apart — moved 510 MiB, i.e. availability drifts |
| 5 | Commit limit (RAM + pagefile) | 66,296.05 MiB | `GlobalMemoryStatusEx.ullTotalPageFile` | this host | 1 sample |
| 6 | **Commit headroom** | **26,959.50 – 27,924.91 MiB** | `GlobalMemoryStatusEx.ullAvailPageFile` | this host | 7 samples over 30.1 s |
| 7 | Memory load | 48 – 50 % | `GlobalMemoryStatusEx.dwMemoryLoad` | this host | 7 samples over 30.1 s |
| 8 | Pagefiles | `C:\pagefile.sys` 1,024 MiB (14 used); `H:\pagefile.sys` 16,384 MiB (366 used, peak 384) | `Win32_PageFileUsage` | this host | 1 sample |
| 9 | **GPU total VRAM** | **16,303 MiB** | **`nvidia-smi` — TRUSTED** (`C:\WINDOWS\system32\nvidia-smi.exe`, driver 617.14, CUDA 13.4) | this host, GPU 0 | 2 samples ~90 s apart — identical both times |
| 10 | GPU free VRAM | **11,375 MiB** (later 11,385 MiB) | **`nvidia-smi`** — TRUSTED | this host, GPU 0 | 2 samples ~90 s apart |
| 11 | GPU used VRAM | 4,605 MiB (later 4,595 MiB) | `nvidia-smi` — TRUSTED | this host, GPU 0 | 2 samples ~90 s apart |
| 12 | Adapter name | **NVIDIA GeForce RTX 5080** (also present: Intel UHD Graphics 770, Virtual Display Driver) | `nvidia-smi` + `Win32_VideoController.Name` | all 3 adapters | 1 sample |
| 13 | GPU total VRAM (CIM) | **4,095 MiB — GARBAGE, DO NOT USE** | `Win32_VideoController.AdapterRAM` = 4,293,918,720 B | NVIDIA adapter | 1 sample |

**On row 13.** The brief's warning is confirmed, and the mechanism is visible: `AdapterRAM` is a
32-bit field, and 16,384 MiB does not fit — the driver wraps to 4,293,918,720 B = 4,095 MiB, i.e.
**3.98x under-report**. Any ceiling priced from `Win32_VideoController.AdapterRAM` on this machine is
wrong by nearly a factor of 4. **All GPU numbers in this document are `nvidia-smi`.**

### 2c. Where the ring physically lives: **RAM, not VRAM**

| Fact | Citation |
|---|---|
| The arena is a `std::vector<uint8_t>` member — heap, system RAM | `capture/ring_buffer.h:126` — `std::vector<uint8_t> arena_;` |
| The allocation itself | `capture/ring_buffer.cpp:112` — `arena_.assign(capacity_bytes, 0);` (in `RingBuffer::init()`) |
| Stated rationale: budgeting from `DedicatedVideoMemory` prices a pool the buffer never draws from | `capture/ring_buffer.h:31-36` |
| Same rationale at the call site, naming this exact bug | `capture/replay.cpp:130-132` — *"The cap is SYSTEM RAM (ring_buffer.h), not VRAM: the arena it bounds is a heap vector, and d3d_.ring_cap_bytes() priced it from a pool the ring never draws from"* |

There is **no D3D12, no `CreateCommittedResource`, no staging heap, and no mapped buffer** in the
ring path. The only VRAM objects in the capture tree are the NV12/BGRA textures used for encoding
(`replay.cpp:166-176`, `main.cpp:410-415`, `wgc_capture.cpp:277-283`) — none of them is the ring.

One consequence worth stating: `assign(capacity_bytes, 0)` **zero-fills**, so every page of the arena
is written at init and is genuinely committed and resident. This is a real charge against the commit
limit (rows 5-6), not a reserve. `main.cpp:544-547` already logs RSS at arm and peak RSS, so the
effect is observable at runtime.

---

## 3. STEP 3 — what each candidate ceiling yields on these numbers

Inputs: total RAM **48,888.05 MiB**; available RAM **24,412.86 – 25,058.61 MiB**;
VRAM total **16,303 MiB**; VRAM free **11,375 MiB**. All terms MiB-aligned DOWN.

### Candidate A — `min(4 GiB, 25% of TOTAL RAM)`

```
25% x 48,888.05 = 12,222.01 MiB  -> align down = 12,222 MiB
min(4,096, 12,222) = 4,096 MiB          CEILING BINDS
```
**Yields 4,096 MiB.** The 25% term sits 8,126 MiB (3.0x) above the ceiling — it is inert.
Binds the ceiling for any machine with **>= 16,384 MiB (16 GiB)** of RAM.

### Candidate B — `min(4 GiB, 25% of AVAILABLE RAM)`

```
25% x 25,058.61 = 6,264.65 MiB  -> align down = 6,264 MiB   (best case in the window)
25% x 24,412.86 = 6,103.21 MiB  -> align down = 6,103 MiB   (worst case in the window)
min(4,096, 6,264) = 4,096 MiB                                CEILING BINDS
min(4,096, 6,103) = 4,096 MiB                                CEILING BINDS
```
**Yields 4,096 MiB at every one of the 7 samples.** Still inert here, by 2,021-2,168 MiB.
Binds the ceiling for any machine with **>= 16,384 MiB (16 GiB) available**.

### Candidate C — VRAM-relative

```
VRAM total / 16 = 16,303 / 16 = 1,018.94  -> 1,018 MiB   (the dead d3d11_ctx.cpp:70 policy)
VRAM free  / 16 = 11,375 / 16 =   710.94  ->   710 MiB
25% of VRAM free  = 11,375 / 4  = 2,843.75 -> 2,843 MiB
50% of VRAM free  = 11,375 / 2  = 5,687.50 -> 5,687 MiB
```
**Yields 1,018 MiB** on the `/16` form — and lands *inside* the dead policy's own
`[256, 2048]` range, so on this machine it would never have clamped at all.

### The SHIPPED three-term policy, evaluated on the measured window

```
quarter_bytes    = 25% of total  = 12,222 MiB          (ring_buffer.cpp:48)
half_avail_bytes = 50% of avail  = 12,206 .. 12,529 MiB (ring_buffer.cpp:49)
cap = min(4,096, 12,222, 12,206..12,529) = 4,096 MiB
     ceiling_binds      = true
     availability_binds = false     <- SLACK BY ~8,138 MiB (3.0x) AT EVERY SAMPLE
     floor_applied      = false
```
The 50%-of-available guard would only start binding once available RAM fell below
**8,192 MiB (8 GiB)**. It is 3x away from doing anything on this host.

### The risk term the policy does NOT contain

```
commit headroom (ullAvailPageFile) = 26,959 .. 27,924 MiB
a 4,096 MiB arena = 4,096 / 27,924 = 14.7% of the commit headroom (best case)
                   4,096 / 26,959 = 15.2% of the commit headroom (worst case)
```
At 47.7 GiB total / 48-50% load, **a 4 GiB arena is not tight on this machine.** The term that would
actually catch a bad day is the commit headroom, and it is not in the policy — which is why the
`std::bad_alloc` catch at `ring_buffer.cpp:113-119` (added for exactly this) is the real backstop,
not the cap.

---

## 4. What the measurements say (facts only — the call is the owner's)

1. **The brief's stated expression does not exist in the tree.** The live cap is a three-term
   `min(4 GiB, 25% total, 50% available)` at `ring_buffer.cpp:51-54`.
2. **The VRAM policy is dead code.** `d3d11_ctx.cpp:66-75` has no callers. That matters for the
   decision: "switch to a VRAM-derived number" is not a retune, it is a resurrection of code whose
   own header says it is wrong (`ring_buffer.h:31-36`).
3. **The ceiling is the only term doing any work on this host.** Both the 25%-of-total term (12,222
   MiB) and the 50%-of-available guard (12,206-12,529 MiB) sit ~3x above 4,096 MiB. So the brief's
   core observation — *"the clamp is pinned at its 4096 MiB ceiling and the RAM term does nothing"* —
   **is correct about the shipped policy**, just not about the expression it attributed to the file.
4. **VRAM does not support a larger ceiling.** Total VRAM is 16,303 MiB and 4,605 MiB of it is already
   in use. Any VRAM-relative ceiling is *smaller* than 4 GiB (1,018 MiB on `/16`), not larger.
5. **The real bound is commit headroom (26,959-27,924 MiB), not total RAM.** A 4 GiB arena is ~15% of
   it. On this host 4 GiB is affordable; the ceiling's value here is about *worst-case days*, which
   these idle-window measurements cannot speak to.
6. **`Win32_VideoController.AdapterRAM` is unusable on this GPU** — 4,095 MiB vs the true 16,303 MiB
   (3.98x under). If any policy is ever priced from CIM, this is the trap.

### Not measured (deliberately out of scope, flagged so it is not mistaken for a clean result)

- No capture run was performed, so there is **no measured RSS/peak-RSS delta** attributable to a
  4 GiB arena — that is the number that would actually price the ceiling, and it needs
  `--ring-mb 4096` with a real session. `main.cpp:544-547` already prints it.
- No second host. Population = this machine only; the thresholds in §3 are arithmetic, not tested
  on other hardware.
- The 30.1 s availability window is idle-ish. The guard that would bind at 8 GiB available is
  untested because the machine never went near it.