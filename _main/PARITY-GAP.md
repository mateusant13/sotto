# ShadowPlay Parity Gap — verified against source

WINDOW: this lane (`lane/parity`). Every claim below is checked against code in
`app/panel/*`, `worker/sotto_worker.py`, `app/webview/*`. The pre-existing
`SHADOWPLAY-PARITY.md` is treated as an untrusted starting point, not evidence.

Status is exactly one of IMPLEMENTED (code exists AND was seen running),
SOURCE-ONLY (code exists, never observed running), ABSENT (named paths searched,
listed), UNSEARCHED (not searched — never counted as ABSENT).

Table and counts: filled in below as the search completes.

## FINDING 1 — the stale doc (landed BEFORE the feature matrix; do not re-derive)

Doc: `H:\sotto\_moved\aireplay\research\shadowplay-parity.md` (24 692 B, mtime 2026-10-07 12:39).
It cites a C++ tree at `src/capture/*.cpp` and a `src/capture/build.cmd`, and every row of its
"our status TODAY" column is a line number inside that tree.

### I independently re-measured the dead lane's claim. It is TRUE for the live product
and FALSE as stated about the filesystem. Both halves recorded:

| Claim | Measurement | Verdict |
|---|---|---|
| "ZERO C++ files" | 529 `*.cpp/*.cc/*.h/*.hpp` under `H:\sotto` — but 526 are third-party numpy headers inside `_main\_epvenvs\*`. Excluding `_epvenvs` and `_moved`: **3** files, all stray droppings: `_main\_47bb_main.cpp`, `_main\_head_main.cpp`, `_main\src\chromium-audio_session_event_listener_win.cc`. | TRUE for the live product |
| "no `src/`" | 35 `src` dirs under `H:\sotto`, **29** of them numpy internals. Real ones: `app\src` (JS), `app\src-tauri\src` (Rust), `app\verify\src`, `_main\src` (1 stray `.cc`). No `src/capture` in the live product. | TRUE for the live product |
| "no `build.cmd`" | 2 hits, BOTH under `_moved`: `_moved\aireplay\src\capture\build.cmd` and `_moved\aireplay-wt\wip\laneH-contract\src\capture\build.cmd`. Zero in `app\`, `worker\`, `control\`, `scripts\`, `probe\`. | TRUE for the live product |
| live product references the C++ tree? | `git -C H:\sotto grep -n -- 'src/capture|_moved/aireplay' -- app worker` → **exit 1, 0 lines**. Nothing in `app/` or `worker/` includes, builds or runs it. | NOTHING IS WIRED |

### The correction that matters: the tree is not fictional, it is DISLOCATED
`_moved/aireplay/src/capture/` really does hold a complete capture engine — `wgc_capture.cpp`,
`replay.cpp`, `ring_buffer.cpp`, `trigger.cpp`, `wasapi_audio.cpp`, `nvenc_encoder.cpp`,
`mp4_writer.cpp`, `nvenc`/`nvEncodeAPI.h`, and the `build.cmd`. 344 files under `_moved` are
tracked by git. So the doc is not lying; it is measuring a tree that was **moved out from under
the live product** (`H:\aireplay` → `H:\sotto\_moved\aireplay`) and then left in place, still
current, still cited.

That is more dangerous than "the doc is wrong", and it is why I am recording the shape of the
failure and not a verdict. The doc's numbers are internally consistent — every one of them is
true *of `_moved/aireplay`* — so a fresh lane reading it has no internal signal to distrust it.
It reads as a live audit of a capture engine that this product does not currently contain.

### Verdict: DO NOT DELETE. APPEND A CORRECTION BANNER, then mark the doc superseded.
The measurements are real and are the only written record of what the C++ engine achieved
(hotkey `RegisterHotKey` at `trigger.cpp:163`, `WM_HOTKEY` pump at `trigger.cpp:292`, the
one-entry `stsd` video-only muxer at `mp4_writer.cpp:119-165`). Deleting it destroys evidence and
invites the next lane to rebuild it from scratch. Two additive steps instead:

1. **Prepend a banner** to `research/shadowplay-parity.md` stating: SCOPE `H:\sotto\_moved\aireplay\src\capture`, NOT the live product; live product is Python (`worker/sotto_worker.py`) + pywebview panel (`app\webview\run.cmd`), no build step, no C++; every `file:line` below is valid only inside `_moved/aireplay`.
2. **Append a `SUPERSEDED` section** at the end recording which of its claims still hold for the live product, from the matrix below.

Owner call required on step 1 (it edits a doc owned by the moved tree, not by this lane).
This lane writes only its own receipt, `_main/PARITY-GAP.md`.