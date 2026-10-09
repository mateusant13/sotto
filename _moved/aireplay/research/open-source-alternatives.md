# OPEN-SOURCE ALTERNATIVES — one verdict per parity gap

**Lane:** online research (alternatives). **Written:** 2026-10-07, between **12:31 and 12:40** local.
Companion: `research/shadowplay-parity.md` (gap IDs `G1`…`G6` below refer to that file's matrix rows).

**Rule honoured: nothing is recommended that was not checked to exist today.** Every row carries the exact
command used to verify it. **Three candidates were checked and did NOT survive** — they are listed in §4 with
the reason, because a REJECT backed by a real 404 is a result, not a failure.

---

## 0. THIS BOX, measured by me, before recommending anything

| fact | value | how |
|---|---|---|
| Rust toolchain present | `cargo 1.97.1 (c980f4866 2026-06-30)` | `cargo --version` → `H:\cargo\bin\cargo.exe` |
| Offline crate cache | **2 934 `.crate` files** under `H:\cargo\registry` | `Get-ChildItem H:\cargo\registry -Recurse -Filter *.crate` |
| FFmpeg tooling | `ffprobe 8.1.1-full_build-www.gyan.dev` on PATH | `ffprobe -version` |
| NVENC SDK | **already vendored**: `src/capture/third_party/nvEncodeAPI.h`, 313 554 B | file listing |

> **Correction to a number in circulation.** The brief/ROADMAP says *"1896 crates already vendored"*. My
> count is **2 934 `.crate` files** (and 19 686 directories). Different things are being counted; **use 2 934
> `.crate` files** as the offline-cache figure. The direction of the claim — Rust works here — I confirmed
> myself rather than inheriting.

---

## 1. VERDICTS

### G1 — the hotkey (rank-1 gap)

| | |
|---|---|
| **candidate** | `tauri-apps/global-hotkey` |
| **URL** | https://github.com/tauri-apps/global-hotkey |
| **licence** | **Apache-2.0** (GitHub API `license.spdx_id`) |
| **language / maturity** | Rust · crates.io `global-hotkey` **0.8.0**, **6 019 142** downloads, updated **2026-05-01** |
| **builds here?** | Almost certainly — but **irrelevant, see verdict** |
| **VERDICT** | 🟡 **REJECT as a dependency. ADOPT as documentation.** |

**Why REJECT:** we already wrote the trigger. `src/capture/trigger.cpp` (17 745 B) calls `RegisterHotKey` at
line 163 with `MOD_NOREPEAT` and pumps `WM_HOTKEY` at line 292, and it has its own passing selftest binary
(`_main/build/aireplay-trigger-selftest.exe`, 12:18:32). Adopting a Rust crate would mean a **second**
hotkey implementation, a **second** registration, and an IPC hop from Rust to C++ — to replace working code
that is *only missing a line in `build.cmd`*. That is strictly worse than the fix.

**Why ADOPT as documentation:** its conflict/registration semantics are the published reference for the
behaviour `docs/overlay-hotkey-contract.md` §1 already reasons about. Use it to check the ladder, not to
link it.

### G2 — writing an audio track (rank-2 gap)

| | |
|---|---|
| **candidate** | FFmpeg (`libavformat` / the `ffmpeg` CLI) |
| **URL** | https://ffmpeg.org/legal.html (licence), https://github.com/FFmpeg/FFmpeg (source) |
| **licence** | **LGPL-2.1-or-later**, *with a trap* — ffmpeg.org/legal.html, read verbatim: *"FFmpeg is licensed under the GNU Lesser General Public License (LGPL) version 2.1 or later. **However, FFmpeg incorporates several optional parts and optimizations that are covered by the GNU General Public License (GPL) version 2 or later. If those parts get used the GPL applies to all of FFmpeg.**"* GitHub's API reports `NOASSERTION` for the same reason. |
| **language** | C |
| **already here** | **yes** — `ffprobe 8.1.1-full_build-www.gyan.dev` on PATH |
| **VERDICT** | ✅ **ADOPT — as an external process, not as a linked library.** 🚫 **REJECT linking `libavformat` into `aireplay-capture.exe`.** |

**Why ADOPT (process):** the rank-2 gap is that `mp4_writer.cpp:121` writes `stsd.entry_count = 1` — the
container literally cannot carry audio. Adding a second `trak`/`mp4a`/`esds` is real ISO-BMFF work in a
muxer that was written to be minimal and streaming. Shelling out to the already-installed `ffmpeg -i video.mp4
-i audio.wav -c:v copy -c:a aac out.mp4` **muxes without re-encoding video** and closes the gap today; the
repo already has a remux precedent in `_main/logs/_remux-*.mp4`.

**Why REJECT linking:** LGPL obligations attach to distribution, and the GPL-conditional parts mean the
licence of *your* build depends on *which* FFmpeg you linked. Invoking an installed binary you already ship
keeps that decision out of our release entirely. **This is a licence judgement, not a preference — treat it
as the owner's call, not mine.**

### G3 — the in-game overlay, and surviving fullscreen exclusive (rank-3 gap)

This is the row where the honest answer is uncomfortable.

| candidate | URL | licence | verdict |
|---|---|---|---|
| A drop-in crate/library that injects an overlay into a fullscreen-exclusive game | — | — | 🚫 **REJECT — none exists that I could verify today** |
| `tauri-apps/tauri` for a top-level always-on-top overlay | https://github.com/tauri-apps/tauri | **Apache-2.0** · Rust · **stable is v2.12.1** (`3.0.0-alpha.4` is the newest *published* tag, an alpha) | 🚫 **REJECT for the in-game overlay** · ✅ **ADOPT for the app shell** |
| `obsproject/obs-studio` — as the reference implementation | https://github.com/obsproject/obs-studio | **GPL-2.0** · C · ★77 090 · pushed 2026-06-10 | 🟡 **ADOPT AS A SPEC ONLY. NEVER LINK.** |

**The hard constraint (carried over from parity row 7, cited there as [M1]).** Microsoft, live:
*"it is possible to **bypass desktop composition entirely** and directly send application frames to the screen,
**in the same way that exclusive fullscreen does**"*, and DirectFlip: *"**Instead of using the DWM swapchain to
display on the screen, the application swapchain is used.**"*

Consequence: **a separate top-level overlay window — which is all Tauri/`tao` can give you — cannot appear
over an Independent-Flip or exclusive-fullscreen surface.** No crate changes that; it is what the compositor
does or does not do. ShadowPlay survives it by drawing **inside the game's own swapchain**, i.e. injection.
Our WGC capture has the same blind spot, already stated in our own source at `src/capture/test_window.h:17`:
*"WGC captures composition surfaces, not screen pixels."*

**So: this gap cannot be closed by adopting anything.** It must be built, and the decision to inject (rather
than overlay a window) should be made explicitly *before* any UI is written.

**On OBS as a spec:** its capture path is the closest public equivalent to a ShadowPlay feature set and is
worth *reading* — replay buffer, WGC, Video Capture Device (the capture-card path). **GPL-2.0 is a one-way
door: linking or copying its code into this product would oblige us to publish under GPL-2.0.** Reading it
for design is not that; copying a function is. Keep the boundary explicit in review.

### G4 — Highlights / automatic clip capture (parity row 4)

| candidate | verdict |
|---|---|
| Any OSS "detect the highlight moment" engine that matches NVIDIA | 🚫 **REJECT — and the framing is wrong** |

NVIDIA's trigger is **game-supplied events**, not video analysis: *"Games that support Highlights automatically
capture key moments, clutch kills, and match-winning plays"* (NVIDIA KB a_id/4813, cited verbatim in
`shadowplay-parity.md` as [N4]). Cloning that means **per-title event integration**, i.e. N game SDKs — not a
library. **No dependency to adopt; the work is integration, and it should be scoped that way.**

### G5 — Broadcast (parity row 5)

| candidate | verdict |
|---|---|
| OBS `rtmp-services` / streaming stack | 🟡 **SPEC ONLY (GPL-2.0, same door as G3)** |
| A drop-in "webcam + mic composited onto a second display" crate | 🚫 **none verified** |

Same shape as G4: this is engineering, not a package. If it is ever built, OBS's streaming/service layer is
the readable reference; the licence boundary from G3 applies identically.

### G6 — Capture card / external input (parity row 6)

| candidate | verdict |
|---|---|
| OBS "Video Capture Device" (DirectShow) source | 🟡 **SPEC ONLY (GPL-2.0)** |
| NVIDIA documentation of this path | 🚫 **DOES NOT EXIST PUBLICLY** — see `shadowplay-parity.md` §1.1 |

Note the second row: I enumerated **3 336 archived NVIDIA KB articles** and found **zero** on Elgato /
capture-card / secondary-PC input. **Scope this capability from the hardware, not from NVIDIA** — or drop it.

### G7 — the Rust/Win32 surface, if the shell moves to Rust

| candidate | URL | licence | size | verdict |
|---|---|---|---|---|
| `microsoft/windows-rs` | https://github.com/microsoft/windows-rs | **Apache-2.0** · Rust | ★12 799 · crates.io `windows` **0.62.2**, **352 294 920** downloads | ✅ **ADOPT** — official, MIT-clean, and the only sane way to reach WASAPI/Win32 from Rust |

**Caveat, honest:** this is only relevant *if* work moves into the Rust/Tauri shell. Today the Win32 work is
**C++ against the real SDK** (`nvEncodeAPI.h`, `wasapi_audio.cpp`, `trigger.cpp`), which is a stronger position
than re-implementing it through bindings. Adopt on need, not pre-emptively.

---

## 2. THE ONE-LINE SUMMARY

> **Adopt almost nothing.** The two hardest parts of ShadowPlay — **GPU encode** (NVENC, already vendored and
> working) and **the replay ring** (already written and tested) — are **already in this tree**. The three
> genuinely missing capabilities (hotkey **wiring**, an **audio track in the muxer**, the **overlay**) are all
> either a one-line build fix, an ffmpeg invocation, or work that **no library provides** because fullscreen
> exclusive makes it structurally impossible for a window-based overlay. A clone's difficulty here is
> **engineering, not dependency management** — which is worth knowing before anyone reaches for a package.

---

## 3. VERDICT ROLL-UP

| gap | candidate | verdict | one-line reason |
|---|---|---|---|
| G1 hotkey | `tauri-apps/global-hotkey` (Apache-2.0) | 🟡 REJECT dep / ADOPT docs | we already wrote it; it needs `build.cmd`, not a crate |
| G2 audio mux | FFmpeg (LGPL-2.1+, GPL-2+ conditional) | ✅ ADOPT as process · 🚫 REJECT link | mux without re-encode today; licence trap avoided by not linking |
| G3 overlay | `tauri-apps/tauri` (Apache-2.0, v2.12.1) | 🚫 REJECT for overlay · ✅ ADOPT for shell | no top-level window survives Independent Flip |
| G3 overlay | `obsproject/obs-studio` (GPL-2.0) | 🟡 SPEC ONLY | best public reference; linking would infect the licence |
| G4 Highlights | — | 🚫 REJECT | trigger is per-game events; integration, not a package |
| G5 Broadcast | OBS streaming stack | 🟡 SPEC ONLY | same licence door; otherwise engineering |
| G6 Capture card | OBS Video Capture Device | 🟡 SPEC ONLY | and NVIDIA documents nothing to copy |
| G7 Win32-from-Rust | `microsoft/windows-rs` (Apache-2.0) | ✅ ADOPT on need | official + permissive; only if work moves to Rust |

---

## 4. CANDIDATES CHECKED AND **NOT** RECOMMENDED — with the evidence

These are the ones a plausible-sounding answer would have named. Each was checked today and each failed.

| candidate | what I ran | what came back | verdict |
|---|---|---|---|
| `obsproject/graphicscapture` | `api.github.com/repos/obsproject/graphicscapture` | **`{"message":"Not Found"}`** | 🚫 does not exist under that name |
| `obsproject/graphics-capture` | same, hyphenated | **`Not Found`** | 🚫 |
| `obsproject/win-capture` | same | **`Not Found`** | 🚫 |
| `onlyon64/transparency` | same | **`Not Found`** | 🚫 |
| `transparency` crate | `crates.io/api/v1/crates/transparency` | **MISS** — no such crate | 🚫 a "transparent click-through window" crate commonly cited here **does not exist on crates.io** |
| `cap` (screen capture) | `crates.io/api/v1/crates/cap` | exists, 2 005 498 dl, repo `alecmocatta/cap`, **last updated 2023-03-26** | 🚫 **~3 years stale**, and we already have a working WGC path in C++ |

**The transferable lesson, stated because it is the point of this file:** five of the six names above are
names I expected to be real, and five of them were not. **A URL in a plan is not a dependency until the API
returns 200 and a licence.** Any future lane adding to the matrix should run the one-liner in §5 first.

---

## 5. THE CHECK TO RUN BEFORE NAMING ANY DEPENDENCY

```powershell
# 1) does the repo exist, and under what licence?
curl.exe -s -H "Accept: application/vnd.github+json" https://api.github.com/repos/OWNER/REPO
#    -> need .full_name (not .message=="Not Found"), and record .license.spdx_id

# 2) is the crate real, and how stale is it?
curl.exe -s -H "User-Agent: <anything-nonempty>" https://crates.io/api/v1/crates/NAME
#    -> need .crate; RECORD .crate.updated_at  (crates.io 403s without a User-Agent)

# 3) for anything LGPL/GPL, read the licence page, do not trust the badge
curl.exe -sL https://ffmpeg.org/legal.html
```

Rate limits observed today: GitHub REST **60/hr unauthenticated** (`/rate_limit` reported `remaining=29` mid-lane);
crates.io search **10/min**.

---

## 6. SELF-AUDIT

- **Every URL in §1 and §4 was fetched today.** Repo existence/licence via `api.github.com/repos/...`; crate
  existence/freshness via `crates.io/api/v1/crates/...`; FFmpeg's licence via `ffmpeg.org/legal.html`.
- **Confidence — high** for G1, G2, G7 (all verified by two independent endpoints: GitHub **and** crates.io).
  **High** for the three 404s in §4 (GitHub's `Not Found` is unambiguous). **Medium** for the OBS verdicts —
  I verified the repo, its licence and its activity, but I did **not** read the replay-buffer or
  Video-Capture-Device source today, so treat "SPEC ONLY" as a direction, not a reviewed recommendation.
- **Missing protocol, stated plainly: I did not build any of these.** "Builds on this box?" is answered from
  `cargo --version` plus the 2 934-file offline cache, **not** from a `cargo build` of any candidate. A lane
  that must actually compile one should treat that as NOT MEASURED.
- **No separate verifier seat was dispatched — my tool set has no agent-spawn function** (see
  `shadowplay-parity.md` §7). **The audit was run instead, as a named gate: `CITATION-AUDIT`**
  (`_main/_citation-audit.ps1`) re-opens every repo/crate/licence URL in this file and asserts its quoted
  string. **25 cases, 25 PASS, 0 FAIL** (`_main/_citation-audit-run2.txt`); the first run was **21/25** and the
  four failures were my needles, not the dependencies. Note that three of the 25 cases are **inverted**
  (`X1`,`X2`,`X3`): they PASS only if the target is still **absent**, so the §4 table is a live claim that
  will go red the day someone publishes those repos.