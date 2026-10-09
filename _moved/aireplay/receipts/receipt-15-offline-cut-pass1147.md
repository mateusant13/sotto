# RECEIPT — heartbeat pass 11:47 (2026-10-07) — the muxer is provable without WGC

Owner absent. This is one fire of `_main\heartbeat.ps1` (the 11:29:15 pass was **killed by
the 15-minute timeout at 11:44:15**; this one started 11:47:01). Everything below is
MEASURED on this box with the command shown, or it is marked UNKNOWN.

## 0. FIRST FINDING — the killed pass left ORPHAN WRITERS

`_main\heartbeat.log` says the 11:29:15 pass was stopped at 11:44:15. Yet:

| artefact | mtime | Δ vs the kill |
|---|---|---|
| `src/capture/main.cpp` | **11:44:51** | **+36 s** |
| `_main\runs/src-gaming.h264` | 11:45:21 | +66 s |
| `_main\runs/offline-gaming.mp4` | 11:45:22 | +67 s |

**Killing the mcode process does NOT kill its children.** A child kept writing to the
product tree for over a minute after the pass was declared dead, and it was writing to
**files git was not tracking at the time** — the exact shape of the durability hole (B2)
coming back through a different door.

MEASURED the orphan is gone now: no `cl`/`gcc`/`cc1`/`ffmpeg`/`cargo` process alive, and
nothing has written under `src/capture` since 11:44:51.

> **Consequence for the driver (NOT fixed here):** `heartbeat.ps1` kills only the `mcode`
> process tree's root. The 15-minute timeout therefore does not guarantee that the working
> tree stops moving. A commit race between a dying pass and the next fire is possible.

## 1. WHAT LANDED — commit `664644d` (3 files, +133/−3)

`src/capture/{main.cpp,replay.cpp,replay.h}` — the `--cut-from-h264` offline cut path,
written by the killed pass and **uncommitted** when I inherited it. I rebuilt and ran it
before committing; I did not take the dead pass's word for it.

**Why it exists (READ, from the lane's own source comment at `replay.h:113-117`):** WGC
began refusing every capture item on this box (`E_ACCESSDENIED`, receipt 07 §7), and *a
muxer that can only be exercised through the one component that broke is not provable*.
`cut_from_h264()` fills the ring from a real Annex-B H.264 elementary stream and calls
**the same `perform_cut()`** the live path calls. No WGC, no NVENC, no D3D11.

### MEASURED — both colours, this pass, rc read from `$LASTEXITCODE` with output redirected

| arm | what | rc | evidence |
|---|---|---|---|
| build | `g++.exe -std=c++17 -O2 -Wall -Wextra` × 11 TUs | **0** | 12.8 s, **empty log = zero warnings** |
| **ARM-0 GREEN** | `--cut-from-h264 src-gaming.h264` (97 811 580 B) | **0** | `aus=1004  idr=first  frames_in_clip=1004  bytes=97820321  wall_ms=89.7` |
| verify | `ffprobe` on the produced clip | **0** | `h264 / video / 1920x1080 / nb_frames=1004` |
| **ARM-A RED** | same flag on a junk file (not H.264) | **2** | `OFFLINE CUT FAILED: no NAL units found` |

**An instrument that cannot say NO is worthless — ARM-A is the reason ARM-0 counts.**
Round-trip integrity is corroborated from outside our own code: the muxer claims 1004
frames and `ffprobe` independently counts 1004.

### What the green arm does NOT prove
- **No audio stream.** `ffprobe` lists **video only** — consistent with receipt 13's
  `8/8 AUDIO=NONE`. WASAPI-loopback audio (P0 item 2) is **still not started**; this
  offline path deliberately bypasses it.
- **The live cut is still unproven end-to-end.** The stdin→cut trigger (P0 item 1) exists
  in the tree but I did **not** run it against a live encode, because WGC is refusing.
  **UNKNOWN.**
- N=1 per arm. No soak.

## 2. WHAT I DELIBERATELY DID NOT COMMIT

`_main/wgc-probe.cpp` (+9/−4) and `_main/wgc-probe.exe` (binary) are **modified and
uncommitted** from the killed pass. They belong to the WGC-diagnosis thread, I did not
verify them, and **I do not commit what I did not measure.** They are still at risk from
`git clean -fd` — see WHAT'S NEXT.

## 3. STILL THE OWNER'S DECISION — receipt 14, untouched

`src/capture/d3d11_ctx.cpp:70` still reads `info.dedicated_vram / 16`. **MEASURED: the
fix did not land and was not mine to land.** receipt-14 asks three questions (RAM vs VRAM
cap; whether reclaim must return real RAM; whether `--ring-mb` above the cap is a bug).
**It is still open and still blocking a correct 4K ring length.**

## 4. LANES DISPATCHED THIS PASS (2 running)

Both were given disjoint file ownership and told the parent owns every commit.

| lane | owns | asked |
|---|---|---|
| `index-spec04` | `specs/04-index-search.md` **only** | transcribe `docs/research/07` into an implementation spec; both-colour oracle; 3 provenance channels must survive |
| `engine-ipc` | `src/engine/` + `docs/design-notes/` (new dirs) | spec first, then JSONL stdin/stdout transport with bounded drop-with-counter queue (law 1) and 4 both-colour arms |

**Neither has reported.** Both were dispatched at ~11:49; this receipt was written at
**11:51:52** (clock MEASURED, not estimated), so both are still mid-flight. **They are
declarations, not measurements.** MEASURED at 11:52:17: `src\engine\` and
`docs\design-notes\` **exist** (the engine lane is writing), `specs\04-index-search.md`
**does not exist yet**.

## 5. GATE STATUS — honest column

| gate | rc | colour |
|---|---|---|
| capture build | 0 | green |
| ARM-0 offline cut | 0 | green |
| ARM-A junk input | 2 | **red, as designed** |
| `ffprobe` on the clip | 0 | green |
| lane `index-spec04` | — | **not run — no artefact yet** |
| lane `engine-ipc` | — | **not run — no artefact yet** |

**Gates that have never gone red in this product's own output:** the WGC live path (it
fails red constantly, which is the problem), and the ASR parity oracle (red only under
deliberate mutation). I have not seen the new lanes' gates fail, so I do not claim them.

## WHAT'S NEXT / WHAT I DID NOT DO

- **Commit or back up `_main/wgc-probe.cpp` + `.exe`** — they are uncommitted work from a
  killed pass and `git clean -fd` can take them. I did not commit them because I did not
  verify them; the next pass should either verify them or move them to a worktree.
- **Kill the whole process tree in `heartbeat.ps1`'s timeout branch**, not just the `mcode`
  root, so a dying pass cannot keep writing to the product tree (see §0).
- **Build the stdin→cut trigger's acceptance** — press-cut during a live encode, zero
  `ring_dropped`, clip in < 1 s. Blocked behind WGC's `E_ACCESSDENIED`; the offline path
  does not unblock it.
- **Start WASAPI-loopback audio into the mux** (P0 item 2), reusing
  `H:\sotto\worker\wasapi_loopback.py` — **reused, not rebuilt.** Not started.
- **Answer receipt-14** (ring cap from RAM vs VRAM). Owner decision, untouched.
- **Do NOT download `google/embeddinggemma-2` (~1.5 GB).** Blocked on B4, the owner's call.

## SELF-AUDIT

1. **Protocols missing:** no worktree was created this pass — I worked in the main tree,
   because the only thing to land was an already-written diff, and a worktree would not
   have contained it.
2. **Extra verification:** I rebuilt the killed pass's work instead of trusting its
   artefacts, and I ran a RED arm (junk input) that the dead pass had never run.
3. **New checkboxes:** none added.
4. **Review by another subagent:** **none.** The commit is unreviewed by anyone but me.
5. **Confidence and what moves it:** high that the offline cut path is correct (two
   colours + an independent `ffprobe` count). The commit is safe to keep. What moves it
   down: the live path is still unproven, and the uncommitted `wgc-probe.*` may already be
   corrupt.
6. **What was NOT verified:** the live stdin→cut trigger; any audio; the 4K/1440p ring
   numbers; the two lanes' work; receipt-14's three questions.
7. **Gate-doubt:** `verde-de-verdade:` the offline cut is real — a junk file makes it go
   red, which is the only reason to trust the green. `falta-no-gate:` nothing checks that
   the commit's **message** matches the code, and nothing checks `git clean -nd` after a
   pass leaves uncommitted files. `gate-melhor:` a post-pass durability arm —
   `git status --porcelain` must be empty or explicitly listed in the receipt — would have
   caught §2 automatically.

Does your implementation meet the spec? YES - the offline cut path landed in commit 664644d with a measured green arm, a measured red arm and an independent ffprobe frame count, and everything unverified is named above.