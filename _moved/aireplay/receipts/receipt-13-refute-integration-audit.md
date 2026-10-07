# RECEIPT — the refute pass on the integration audit (2026-10-07)

The audit lane delivered findings that CONTRADICT this morning's roadmap in two
load-bearing places, and it flagged its own two strongest claims as resting on a
single grep and a single ffprobe. Per the mission contract — *the second pass
must try to refute the first* — both were re-measured here, on the WHOLE
population rather than one sample.

## The three claims that decide P0's scope

| # | claim | how re-measured | verdict |
|---|---|---|---|
| 1 | **No hotkey anywhere in capture** | `Select-String` for `RegisterHotKey\|GetAsyncKeyState\|WM_HOTKEY\|SetWindowsHookEx\|GetKeyState\|VK_` across **ALL** of `src/capture/*.cpp` and `*.h` | **UPHELD — 0 hits.** The cut is time-triggered (`cfg.cut_at_s`), so the "instant replay" trigger does not exist yet. |
| 2 | **Clips have no audio stream** | `ffprobe -select_streams a` on **8** clips (not 1), spanning 3.0 s to 30.0 s, the largest 165 MB | **UPHELD — 8/8 `AUDIO=NONE`, all h264 video-only.** |
| 3 | **"The Tauri Rust has never compiled"** | **REFUTED — and the auditor retracted it itself.** | **FALSE.** `cargo build` → **rc=0 in 19.32 s**, producing a valid **215 707 515 B** PE `MZ` executable at `H:\jcode-target-gnu\debug\sotto.exe`, with 48 980 files / 24.5 GB of compiled dependencies. |

## Claim 3 is the interesting one — and the reason matters

The auditor inferred "never compiled" from the **absence of
`app/src-tauri/target/`**. That inference was wrong for a mundane, mechanical
reason, and it is worth recording because it is the same trap twice:

> `H:\cargo\config.toml` sets `target-dir = "H:/jcode-target-gnu"` globally
> (an owner policy from 2026-09-14 to stop build lanes stuttering the box).
> **The build output was never going to appear in `src-tauri\`.**

This very trap caught ME first: right after the successful `rc=0` I ran
`Test-Path H:\sotto\app\src-tauri\target\debug\sotto.exe` → **False** — and the
empty target dir looked like a failed build. **A missing artefact is not a
verdict.** The `rc` and the byte counts were the evidence; the path I guessed
was the assumption. Correct move: read `H:\cargo\config.toml` before concluding.

**The real blocker was never the toolchain.** It was **2 lines** in our own
`geometry.rs`, written against the Tauri 1 API (`Option<Rect>`) while Tauri 2
returns `&PhysicalRect`. Fixed and committed: **`5eca648`** (+16/−7, one file).

## Why this changes the roadmap, not just its confidence

P0 was written as *"wire four subsystems together"*. The measurement says two of
them are missing **features**, not glue:

- capture cannot be triggered on demand (**no hotkey**), and
- capture emits **no audio at all**, while ASR consumes WAV.

So the honest first slice is not an integration. It is a **vertical slice that
creates the two missing capabilities** — stdin-driven cut + WASAPI-loopback audio
muxed beside the video — because without them there is nothing to integrate:
no "instant replay" (no trigger) and no "searchable memory" (nothing is ever
spoken into the index).

## What was NOT verified
- Whether the ring's real overhead matches the payload-only table (needs a live
  capture run — long CPU work, deliberately skipped).
- Whether the existing `app/panel` works when hosted by Tauri rather than
  pywebview (`tauri.conf.json` currently points at `../dist`, i.e. neither panel).
- The ASR oracle's red arms were not re-run by me; that claim is READ.
