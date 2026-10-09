# SHADOWPLAY PARITY MATRIX — what "a complete clone" actually means

**Lane:** online research (parity). **Written:** 2026-10-07.
**Measurement window for every "our status" claim: 2026-10-07 12:11–12:30 local.**
**Sources read:** every NVIDIA claim below was READ, not inferred from a search snippet. URLs in §1.

> **READ THIS FIRST — the brief's two headline facts are STALE, and the tree moved under me while I wrote.**
> `LANE-BRIEF.md` §3 says *"There is no hotkey. 0 hits across `src/capture`"* and *"8 of 8 sample clips have no
> audio stream."* As of **12:22 today** both are **no longer true of the source tree**, while **remaining true of
> the shipped binary**. The distinction decides the build order, so it is stated first, with evidence, in §2.
> Do not re-use the brief's numbers.

---

## 1. PROVENANCE — what I opened, and what failed

NVIDIA's own knowledge base (`nvidia.custhelp.com`) is **currently serving an Oracle "Technical Difficulties"
error page** — a bare `curl` returns **HTTP 200 carrying an error page**, so a status-code-only check would
report it healthy. It is not. Therefore every NVIDIA KB citation below is a **Wayback Machine snapshot of
NVIDIA's own KB**, with the archive timestamp named so it is reproducible. One claim comes from NVIDIA's
**live** site, which does serve normally.

| id | source | how it was retrieved | snapshot / status |
|---|---|---|---|
| **[N1]** | NVIDIA App product page — `https://www.nvidia.com/en-us/software/nvidia-app/` | **LIVE**, HTTP 200, fetched 12:20 | live, no archive needed |
| **[N2]** | NVIDIA KB a_id/4811 *What are the Highlights keyboard shortcuts?* | `https://web.archive.org/web/20260110141314/https://nvidia.custhelp.com/app/answers/detail/a_id/4811` | snapshot `20260110141314`; article's own "Updated" field = **09/29/2021** |
| **[N3]** | NVIDIA KB a_id/5084 *NVIDIA App In-Game Performance and Latency Overlay* | `https://web.archive.org/web/20250814145634/https://nvidia.custhelp.com/app/answers/detail/a_id/5084/~/nvidia-app-in-game-performance-and-latency-overlay` | snapshot `20250814145634`; article's "Updated" = **08/04/2025** |
| **[N4]** | NVIDIA KB a_id/4813 *What type of capture features does Highlights support?* | `https://web.archive.org/web/20220521021516/https://nvidia.custhelp.com/app/answers/detail/a_id/4813` | snapshot `20220521021516`; "Updated" = **09/29/2021** |
| **[N5]** | NVIDIA KB a_id/4814 *What video format does NVIDIA Highlights use?* | `https://web.archive.org/web/20251101185332/https://nvidia.custhelp.com/app/answers/detail/a_id/4814` | snapshot `20251101185332`; "Updated" = **09/29/2021** |
| **[N6]** | NVIDIA KB a_id/3328 *What resolution does ShadowPlay support?* | `https://web.archive.org/web/20220119113109/https://nvidia.custhelp.com/app/answers/detail/a_id/3328` | snapshot `20220119113109`; "Updated" = **10/19/2021** |
| **[M1]** | Microsoft Learn — *For best performance, use DXGI flip model* | `https://learn.microsoft.com/en-us/windows/win32/direct3ddxgi/for-best-performance--use-dxgi-flip-model` | LIVE, HTTP 200, fetched 12:19 |
| **[G]** | GitHub REST API `api.github.com/repos/{owner}/{repo}` | live, per-repo | see `open-source-alternatives.md` |

**Tools/versions used on this box:** `ffprobe 8.1.1-full_build-www.gyan.dev` (on PATH,
`C:\Users\Administrador\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe`).

### 1.1 What I could NOT verify — stated by name

| claim | status | why |
|---|---|---|
| Instant Replay buffer **range** (the widely-quoted "default 5 min, max 20 min") | **`NOT VERIFIED`** | NVIDIA's KB has no archived page stating the range. DDG/Bing both degraded to unusable during this lane (Bing served a pt-BR generic result set ignoring the query; DDG returned 14 KB anti-bot stubs). **No number is asserted below.** |
| The widely-quoted defaults **`Alt+F9` = record, `Alt+F10` = broadcast** | **`NOT VERIFIED from NVIDIA's own docs today** | NVIDIA's KB does not publish the current NVIDIA App default table. [N2] says verbatim: *"You can find a complete list of keyboard shortcuts by opening the in-game overlay and navigating to Settings > Keyboard shortcuts."* They are probably right; **they are not cited, because I did not read them from NVIDIA.** `docs/overlay-hotkey-contract.md` reached the same conclusion independently and also marked NVIDIA's key set `NOT VERIFIED`. |
| NVIDIA's **Capture Card** / external-input behaviour | **`NOT VERIFIED`** | Searched the full enumerated NVIDIA KB inventory (3336 archived articles, §4) — **zero** articles on Elgato/capture-card/secondary-PC input. NVIDIA's live product page does not describe one. **NVIDIA does not publicly document this path.** |
| NVIDIA's behaviour on **fullscreen exclusive** | **`NOT VERIFIED from NVIDIA** | No NVIDIA article in the inventory addresses it. The **mechanism** is documented by Microsoft and is cited instead ([M1]) — this is the part that actually decides our architecture. |
| NVIDIA Broadcast **streaming destinations** (YouTube/Twitch/Facebook) | **`NOT VERIFIED today** | [N1] describes Broadcast's *audio/video effects* only. A Twitch-specific article (a_id/3460) exists in the inventory but has **no archived snapshot** — CDX returns zero rows. |

---

## 2. THE TWO BRIEF CLAIMS, RE-VERIFIED — **THE BRIEF IS WRONG**

### 2.1 "There is no hotkey. 0 hits across `src/capture`." → **FALSE as of 12:22**

The brief was true when written. A parallel lane wrote `src/capture/trigger.cpp` (**17 745 B, mtime
2026-10-07 12:22:03**) — *during this lane's run*. My first listing at **12:11** did not contain it.

```
$ Get-ChildItem src\capture -File          # 12:22:18
trigger.cpp          17745  07/10/2026 12:22:03
trigger.h            12900  07/10/2026 12:13:32
trigger_selftest.cpp 13864  07/10/2026 12:16:11
wasapi_audio.cpp     43734  07/10/2026 12:22:16
wasapi_audio.h       14734  07/10/2026 12:18:03
```

The hotkey machinery is **real**, not a stub — `grep -E 'RegisterHotKey|GetAsyncKeyState|WM_HOTKEY|MOD_NOREPEAT' src/capture`
returns **24 occurrences across 4 files**, including a genuine registration at
**`src/capture/trigger.cpp:163`**:

```cpp
const uint32_t m = b.mods | MOD_NOREPEAT;
if (hwnd_) {
    if (RegisterHotKey(hwnd_, (int)id, m, b.vk)) {      // trigger.cpp:163
        st.registered = true;
```
plus a real message pump at **`trigger.cpp:292`** (`if (msg.message == WM_HOTKEY)`) and a
`GetAsyncKeyState` polling fallback at **`trigger.cpp:30`**.

**But it is NOT in the shipped product.** Three independent proofs, 12:22–12:26:

```
# (a) nothing includes it — main.cpp does not
$ Select-String -Path src\capture\*.cpp,src\capture\*.h -Pattern '#include\s+"(trigger|wasapi_audio)\.h"'
  trigger.cpp:5             #include "trigger.h"
  wasapi_audio.cpp:27       #include "wasapi_audio.h"
  trigger_selftest.h:27     #include "trigger.h"       <-- no main.cpp, no replay.cpp

# (b) the build does not compile it
$ Get-Content src\capture\build.cmd | Select-String 'trigger|wasapi'
  (no output)              # compile list is: main common d3d11_ctx nv12_convert wgc_capture
                           #                   nvenc_encoder ring_buffer mp4_writer selftest test_window replay

# (c) the shipped binary does not contain it  <-- decisive
$ [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes(...aireplay-capture.exe)).Contains("TRIGGER arm:")
  aireplay-capture.exe          (520 005 B, 12:18:06)  contains 'TRIGGER arm:' = False
  aireplay-trigger-selftest.exe (778 152 B, 12:18:32)  contains 'TRIGGER arm:' = True
```

> **CORRECTED STATUS, in one sentence: the hotkey trigger EXISTS as source and is unit-tested in its own
> binary, but it is absent from `build.cmd`, absent from `main.cpp`, and absent from the shipped
> `aireplay-capture.exe` — so the owner still cannot press a key to save a replay.**
> `AGENTS.md:293-295` independently confirms the intended end state: *"THE HOTKEY IS ARMED ONLY IF AN ENCODER
> REALLY INITIALISED — the capture lane's design carries a start-up self-test that **refuses to arm the replay
> hotkey** when no encoder opened."*

### 2.2 "8 of 8 sample clips have no audio stream." → **STALE POPULATION, and 4 clips DO have audio**

```
$ ffprobe -v error -show_entries stream=codec_type -of json -- <every *.mp4/*.mkv/*.mov under _moved\aireplay>
POPULATION: all *.mp4/*.mkv/*.mov under H:\sotto\_moved\aireplay (recursive)   → 46 clips
  clips with >=1 audio stream: 4          (all AAC)
  audio_streams=0 count=42
```

**"8 of 8" is false today and must not be quoted.** But the four clips that *do* carry audio are **not ours** —
they are ffmpeg-made control/reference material, proven by encoder provenance rather than by filename:

```
$ ffprobe -show_entries format=format_name:format_tags=encoder:stream_tags=encoder -of json
  _main\_census09-ctl\ctl-faststart.mp4      Lavf62.12.101   Lavc62.28.101 libx264,   audio=aac   <-- ffmpeg control
  _main\_import-bench\synth-180s-1080p30.mp4 Lavf62.12.101   Lavc62.28.101 libx264,   audio=aac   <-- ffmpeg control
  _main\runs\clip-20261007-110729.mp4        (no stream encoder tag)          audio=NONE        <-- OURS
```

Partition by provenance: **39 clips are ours** (30 in `_main\runs\`, 9 ffmpeg-**remuxed** from ours in
`_main\logs\`), and **39/39 of ours have ZERO audio streams.** The 4 with audio are 3 `ctl-*.mp4` + 1
`synth-*.mp4`, all built by libx264/libx265/h264_qsv — i.e. the reference clips our own clips are compared
against.

**And the gap is deeper than "the capture side has no audio":** even with a working WASAPI tap, the muxer
**cannot write an audio track at all**.

```
$ Select-String -Path src\capture\mp4_writer.cpp,src\capture\mp4_writer.h -Pattern '(?i)audio|esds|mp4a|soun'
  mp4_writer.cpp:119:  Box stsd("stsd");
  mp4_writer.cpp:120:  put_full_box_header(stsd.b, 0, 0);
  mp4_writer.cpp:121:  put_u32be(stsd.b, 1);   // entry_count      <-- ONE entry, and it is avc1
  mp4_writer.cpp:165:  stsd.b.insert(stsd.b.end(), avc1.begin(), avc1.end());
```

`stsd` is the sample-description box and `entry_count = 1` is the **only** sample it declares — the H.264 video.
No `mp4a` entry, no `esds` decoder-config box, no `trak` for audio, and no `mp4_writer` mtime later than
**10:32:51** (before `wasapi_audio.cpp` existed at 12:22). **The audio muxing work has not been started.**

Also newly true: the brief's "0 hits across `src/capture`" for the word *hotkey* was never literally right
either — there were 11 textual hits at 12:11 (`selftest.cpp:63`, `main.cpp:5,230,279`, `ring_buffer.h:3`,
`replay.cpp:188`, `selftest.h:4`), **all comments or log strings saying the hotkey is NOT armed**. The
meaningful count is the API count, which was genuinely **0** at 12:11 and is **24** at 12:22.

---

## 3. THE MATRIX

Legend for **our status**: ✅ shipped & wired · 🟡 source exists, NOT in the shipped build · ❌ absent.
Every ❌/🟡 carries its own evidence.

| # | capability | what NVIDIA actually does (cited) | our status TODAY (file:line) | the gap | who closes it |
|---|---|---|---|---|---|
| **1** | **Instant Replay** (ring buffer) | "**DVR-style Instant Replay**, enabling users to instantly save the **last 30 seconds** of gameplay" [N1]. Hotkey row: "**Save last [user defined] mins/seconds recorded**" [N2] — i.e. the ring length is **user-configurable**, and saving writes the *tail* of a continuously-encoded ring. | 🟡 Ring is real: `ring_buffer.cpp` (8238 B) with a pure, testable clamp fn (`ring_buffer.h:51,84,91`). Trigger exists (`trigger.cpp:163` `RegisterHotKey`) but is **not in `build.cmd` and not in the exe** (§2.1). Cut is **time-based** (`cut_at_s`), not key-triggered. | **1 line of build + 1 call site.** The ring and the trigger both exist; nothing joins them. Ring length is not user-exposed. | **capture lane** (`src/capture/`): add `trigger.cpp` to `build.cmd`, instantiate in `main.cpp`, honour the AGENTS.md:293 encoder-arming gate |
| **2** | **Overlay HUD** | `Alt+Z` opens the in-game overlay; "An overlay will appear on the **top right** of your screen"; content is "**frame rates, clock speeds, GPU temperatures**" [N3]. Live page: "**GPU and CPU utilization, FPS 1% Low, and PC and system latency** with integrated **NVIDIA Reflex Analyzer** support" [N1]. Opacity and metric set are user-configurable: "Alt+Z > Statistics > **Configure heads up display**" [N3]. | ❌ **Absent entirely.** `grep -i 'overlay\|composit' src/` → only 2 comment hits (`test_window.h:17`, `test_window.cpp:215`) and the vendored `nvEncodeAPI.h`. `src/ui/` has **no files** (dir listing: `src\capture`, `src\asr`, `src\engine` only). | The entire capability. It is also the **only** surface through which every other ShadowPlay feature is driven. | **NEW lane — OverlayLane** (no owner exists) |
| **3** | **Manual record + recording HUD** | Hotkey row "**Toggle Record on/off**" [N2]; live page: manual record "at up to **8K HDR at 30 fps**, or **4K HDR at 120 fps**" [N1]. | 🟡 A time-based cut + write exists (`replay.cpp`, `mp4_writer.cpp`), but the capture window is **hard-fixed**: `src/capture/replay.cpp:57` `tw_.create(1920, 1080, ...)` and `replay.cpp:61` `*w = 1920; *h = 1080;`. No record-state HUD. | Native resolution is impossible; **every** 1440p/4K number is arithmetic. NVIDIA's list is 8K/4K/1440p/1080p/720p/480p/360p and "if the gameplay aspect ratio is different, **black bars are added**" [N6]. | **capture lane** |
| **4** | **Highlights / auto clip capture** | "Games that support Highlights **automatically capture key moments, clutch kills, and match-winning plays**" [N4]; repeated verbatim on the live page [N1]. Format: "**H.264 and saved as MP4 files**" [N5]. | ❌ Absent. `grep -i 'highlight' src/` → **0**. | Entire capability. **But read the trigger correctly:** the trigger is **game-supplied events** (a per-title SDK telling NVIDIA "a multi-kill happened"), *not* CV or audio analysis of the video. A clone that tries to infer moments from pixels is building the wrong thing. | **NEW lane — HighlightsLane**, gated on per-title event integration |
| **5** | **Broadcast** (2nd display, camera, mic, streaming) | NVIDIA splits this: the in-app **Broadcast** button, and a separate **NVIDIA Broadcast** app that "transforms any room into a home studio… with powerful AI effects like **noise and room echo removal, virtual background**, and more" [N1]. | ❌ Absent. `grep -i 'broadcast\|webcam\|camera\|second.?display\|mic\|directshow' src/` → **0 real hits** (only `nvEncodeAPI.h`'s unrelated `overlayFrameFlag` and `test_window.h:17`). | Entire capability, and it is **three** capabilities (second display / webcam+mic composite / RTMP push), each large. | **NEW lane — BroadcastLane** |
| **6** | **Capture Card / external input** | **`NOT VERIFIED`** — see §1.1. No NVIDIA KB article in 3336 enumerated archived articles, and nothing on the live product page. | ❌ Absent. Capture is Windows Graphics Capture on a display only (`wgc_capture.cpp`); no external-device path (no DirectShow/Media Foundation device enumeration). | Entire capability. **Do not scope it from NVIDIA** — scope it from the hardware (Elgato-class UYVY over USB) or drop it. | **NEW lane — deferred**, needs an owner decision first |
| **7** | **Fullscreen exclusive vs borderless** | NVIDIA does not document it publicly. **The mechanism does, from Microsoft** [M1]: *"Depending on window and buffer configuration, it is possible to **bypass desktop composition entirely** and directly send application frames to the screen, **in the same way that exclusive fullscreen does**"*; and for DirectFlip: *"**Instead of using the DWM swapchain to display on the screen, the application swapchain is used.**"* Also: *"you may want to reconsider whether your application actually needs a fullscreen exclusive mode, since the benefits of a flip model **borderless** window include faster Alt-Tab switching."* | ❌ Two-sided gap. Capture is **WGC**, and `src/capture/test_window.h:17` already states the consequence in its own words: *"WGC captures **composition surfaces, not screen pixels**."* There is no overlay at all (row 2). | **This is an architectural constraint, not a bug.** When a game runs Independent-Flip / exclusive fullscreen there is **no DWM composition to draw on**, so (a) a **separate top-level overlay window cannot appear**, and (b) **WGC cannot see the surface**. Only an **in-process overlay drawn into the game's own swapchain** — which is what ShadowPlay does — survives. A Tauri/`tao` top-level overlay is structurally incapable of matching NVIDIA here. | **OverlayLane**, and it decides the stack: injection, not a webview overlay |
| **8** | **Hotkey list** | See the verified table in §5. | 🟡 Source exists, not shipped (§2.1). `docs/overlay-hotkey-contract.md:59-76` (READ from `trigger.cpp`) already fixes a 9-binding ladder and a `Ctrl+Alt+R` primary. | Not a gap in design — a gap in **wiring**. | **capture lane** |

---

## 4. TOP 5 GAPS, ranked by (user-visible impact ÷ effort)

| rank | gap | impact | effort | why it ranks here |
|---|---|---|---|---|
| **1** | **Ship the hotkey** (`build.cmd` + one call site in `main.cpp`) | **Total.** Instant Replay *is* the product; today the owner cannot trigger a save at all. | **Minutes.** `trigger.cpp` is written, `MOD_NOREPEAT`-correct and unit-tested. | Highest ratio in the whole matrix by a wide margin. Everything else is blocked behind having a way to say "now". |
| **2** | **An audio track in the muxer** (`mp4_writer` `stsd.entry_count` 1 → 2) | **High.** Sotto is a *transcription* app; `wasapi_audio.cpp` exists but nothing can carry the samples to disk, so the ASR index stays empty. | **Medium** — it is a real ISO-BMFF change (second `trak`, `mp4a`, `esds`), not a flag. | The capture-side tap is already written; the missing half is the container. Cheapest fix that unblocks an entire downstream subsystem. |
| **3** | **An overlay of any kind** | **High** — and it is the only surface that makes the rest of the product usable. | **High**, and row 7 forces **injection**, which is the expensive kind. | Cannot be a webview panel. Must draw in the game's process to survive fullscreen. Do not start before #1. |
| **4** | **Stop hard-fixing 1920×1080** (`replay.cpp:57,61`) | **Medium-high.** Blocks 1440p/4K outright and makes any resolution claim unmeasurable. | **Low-medium** — but touches the encode/convert sizing throughout. | Cheap relative to its blast radius. Every fidelity claim is currently an assumption. |
| **5** | **Size the ring from RAM, not VRAM** (`d3d11_ctx.cpp:70`) | **Medium.** The ring lives in system RAM but is budgeted from `dedicated_vram`, clamped 256 MiB–2048 MiB — while `AGENTS.md:151` sizes the box for "a 16 GB box" and this host has **47.74 GiB**. | **Low** — a one-function change with an existing receipt. | Cheap and self-contained; do it while waiting on #3. |

---

## 5. THE HOTKEY LIST — only what NVIDIA actually documents

Reproduced from **[N2]** (NVIDIA KB a_id/4811, article "Updated 09/29/2021"). This is the **2021 GeForce
Experience** table, kept by NVIDIA as the Highlights hotkey reference:

| action | Windows | macOS |
|---|---|---|
| Open/Close the Share In-Game Overlay (IGO) | `Ctrl+G` | `⌘+G` |
| Save a screenshot | `Ctrl+1` | `⌘+1` |
| **Toggle Instant Replay on/off** | `Ctrl+Shift+0` | `⌘+shift+0` |
| **Save last [user defined] mins/seconds recorded** | `Ctrl+0` | `⌘+0` |
| Toggle Record on/off | `Ctrl+9` | `⌘+9` |
| Toggle Microphone on/off | `Ctrl+M` | `⌘+M` |

From **[N3]** (NVIDIA KB a_id/5084, "Updated 08/04/2025" — the newest NVIDIA documentation I could read):

| action | key |
|---|---|
| Toggle the **statistics overlay** on/off | `Alt+R` |
| **Cycle** through different metrics | `Alt+Shift+R` |
| Open the in-game overlay / settings (`Alt+Z` > Settings Cog > "Shortcuts") | `Alt+Z` |

**Three consequences for our ladder:**

1. **NVIDIA's own docs do not publish the current NVIDIA App default table.** [N2] sends you to the in-app
   Settings screen for that. Any document claiming the "real" current list is going beyond NVIDIA's own
   published evidence — including the popular `Alt+F9`/`Alt+F10` pair, which this lane **could not verify**
   and therefore does not assert.
2. **`Ctrl+0` is the Instant Replay save key, and it saves "last [user defined] mins/seconds"** — the ring
   length is a *user setting*, not a constant. Our ladder currently hard-codes a per-binding window
   (`docs/overlay-hotkey-contract.md` §2.1); that window should become one user-configurable ring length.
3. **[M1]-adjacent hazard:** a system-wide `RegisterHotKey` hotkey must survive games that grab input.
   `docs/overlay-hotkey-contract.md` §1 already carries the load-bearing Win32 fact (**press only, no
   release, no hold** — `WM_HOTKEY` has one message type, emitted on the press). Reuse it; do not re-derive.

---

## 6. BUILD ORDER — what to do next, in sequence

1. **Ship the trigger.** Add `trigger.cpp` to `src/capture/build.cmd`'s compile list; instantiate the
   trigger in `main.cpp`; gate arming on the encoder self-test (`AGENTS.md:293`). **Re-run the §2.1 binary
   probe** — `aireplay-capture.exe` must flip to `contains 'TRIGGER arm:' = True`. That single string check
   is the gate for this step.
2. **Audio end-to-end.** Finish `mp4_writer` for a second `trak` (`mp4a` + `esds`), then wire
   `wasapi_audio.cpp` in. Gate: `ffprobe -show_entries stream=codec_type` on a fresh clip returns **2** streams.
3. **Ring sizing.** `d3d11_ctx.cpp:70` VRAM → system RAM, clamp re-derived from the box's real 47.74 GiB.
4. **Resolution.** Remove the 1920×1080 constant; read the WGC frame's real size. Add black-bar padding to
   match [N6]'s documented aspect-ratio behaviour.
5. **Overlay — decide injection vs. window BEFORE writing any UI.** Row 7 is the decision: only an
   in-process overlay survives fullscreen exclusive. A Tauri/`tao` top-level window cannot. This is a stack
   decision and should be made explicitly, not discovered late.
6. **Highlights / Broadcast / Capture Card** — each needs an owner decision first (rows 4–6).

---

## 7. SELF-AUDIT

- **Every NVIDIA behaviour claim above carries a URL I opened and read.** The five KB citations are Wayback
  snapshots with named timestamps; [N1] and [M1] are live and were fetched today.
- **Every "our status" claim carries a command and its output**, all re-run inside the 12:11–12:30 window.
- **Confidence:** *high* for the four local measurements (§2, rows 1/3/7) — each is a command whose output I
  read, not an inference. *High* for [N1], [M1], [N2], [N3], [N4], [N5], [N6] — quoted text is reproduced
  verbatim from a page I fetched. *Low/zero* for the §1.1 items, which are labelled as such rather than
  filled in.
- **The biggest risk in this document is that the tree moved under me.** `trigger.cpp` and `wasapi_audio.cpp`
  were written *during* this lane. Every line number here is a **hint**; re-run §2's commands before acting.
- **No separate verifier seat was dispatched — I do not have an agent-spawn tool.** My tool set is
  `bash / read / write / edit / grep / glob / web_fetch / task_query / task_output / task_stop`; there is no
  `task(...)` agent dispatcher, so the brief's §6 step **could not be performed as written**. This is a real
  gap in this lane's process, not an omission.
- **In its place I ran the substance of the audit myself, as a named gate: `CITATION-AUDIT`.**
  `_main/_citation-audit.ps1` re-opens **every** URL cited in `research/*.md` and asserts the exact quoted
  string is present in the fetched bytes. **25 cases, 25 PASS, 0 FAIL** — run 2,
  `_main/_citation-audit-run2.txt`. Re-run it with
  `pwsh -NoProfile -File _main\_citation-audit.ps1`.
  - **The first run FAILED 4 of 25** (`_main/_citation-audit.txt`), and the cause was **my needles, not the
    citations**: GitHub pretty-prints JSON (`"spdx_id": "Apache-2.0"`, with a space), and tag-stripping
    `ffmpeg.org/legal.html` collapses `GNU Lesser General Public License` → `LesserGeneral`. Each was confirmed
    by hand before the needle was corrected. **Recorded because a green gate that was green the first time you
    ran it is worth less than one that survived a red run.**
- **What `CITATION-AUDIT` does NOT cover:** it proves the page contains the quoted string. It does not prove
  the string is the *whole* story, and it cannot judge whether NVIDIA's 2021-era defaults still hold in 2026 —
  only NVIDIA can answer that, and their own KB points at the in-app settings screen instead.