# RECEIPT 18 — what this box can ACTUALLY encode and capture, measured now

**Lane:** capture capability battery (`src/capture/run_battery.ps1`)
**Box:** Win11 26200 · i5-13600K (14C/20T) · **RTX 5080** `0x2C02` 16303 MiB · driver **617.14** /
`nvEncodeAPI64.dll` 32.0.16.1714 · **47.74 GiB** RAM · display 1920×1080 · mingw-w64 g++ 15.2.0 ·
ffmpeg 8.1.1 (gyan.dev).

**Binaries this receipt's rows were measured against** (`_main\build\aireplay-capture.exe`, 566 906 B):

| when | sha256 | produced by |
|---|---|---|
| 12:12 (exploratory measurements, §2/§3a/§4) | `E7B40DAF921105B71F5DB9DE6D29F627671DEBA40C657B82914B77B8A733D026` · 517 901 B · mtime 11:50:17 | the tree as I inherited it |
| 12:28:11 (**battery run 1**) | `9697896D7FC7CC11CE8F2135029AA38415411E814C9E777D1A6CF7E922B37D64` | `run_battery.ps1` rebuilt it |
| 12:34:21 (**battery run 2**) | `253020D9F412A1B4D42F5CAB95B9906427835500C07B2A9F430CCF08B28C2AC0` | `run_battery.ps1` rebuilt it again |
| 12:40:45 (**battery run 3**, parse guard live) | `6A0FBB9F6EE19642D8CC1214ADAA62A45BB43781A93C4CFCB40E403F09EF8E94` | `run_battery.ps1` rebuilt it a third time |
| 12:52:58 (**battery run 4**, after the §7/§5 corrections) | `4735EDC303D91D0982CC7A5EF10DB7795EF6716D6D0BB1BE81B0EFDFBB73FB4A` | `run_battery.ps1` rebuilt it a fourth time |

> **The hash differs between runs, and that is not a defect in the battery — it is a fact about this
> tree.** Other lanes (L1/L2/L3/L7) were editing `src/capture/*.cpp` **continuously while this lane
> worked** — `replay.cpp` 12:26:28, `trigger_selftest.cpp` 12:28:46, `wasapi_audio.cpp` 12:22:16,
> `ring_buffer.cpp` 12:17:36, and more after. `run_battery.ps1` rebuilds from that moving tree, so
> **four runs produced four different binaries**. That is the strongest possible demonstration of why
> every number here carries its provenance: **all four binaries, built from four different states of a
> tree other people were actively editing, produced identical verdicts on every qualitative row.**
> Only the timing figures moved — and they moved because **the machine was busier**, which is exactly
> why §8 reports ranges instead of points.

---

## 0. THE ONE-PARAGRAPH VERDICT

**NVENC is real and healthy. WGC is dead on this box. The muxer is the only half that can be
proven end-to-end right now, and it hides a container defect that `ffprobe` cannot see.**

Three findings a derived number would have got wrong:

1. **NVENC is not a fallback story.** A real NVIDIA encoder initialises, H.264 High at 1920×1080,
   **2 engines, 4096×4096 max**, zero-copy input **registered AND mapped**, and it survives three
   deliberately broken configurations by refusing them with exit 3.
2. **WGC refuses every capture item** — `0x80070005 E_ACCESSDENIED` on all five, process-wide and
   window-independent. This is a **measurement**, not a failure of the battery: the capture half of
   this product **cannot run on this box at the time of writing**, so every "how fast does capture
   run" number in the project is DERIVED, and this lane says so instead of restating it.
3. **The muxer writes the size you TOLD it, not the size of the stream — and `ffprobe` hides it.**
   A 4K stream muxed with `--cut-size 1920x1080` produced a file whose `tkhd`/`avc1` say
   **1920×1080** while its coded stream is **3840×2160**. `ffprobe` reports 3840×2160, so every
   verification in receipt-03 would have passed. Only a byte-level box read shows the contradiction.

---

## 1. NVENC — MEASURED, and the gate is not vacuous

Five arms, one command, exit codes read from `$LASTEXITCODE` with stdout/stderr redirected to file
(never a pipe — see §7).

| arm | fault injected | exit | what the product said |
|---|---|---|---|
| **normal** | none | **0** | `DECISION: ARMED - codec=H.264 engines=2 max=4096x4096`; zero-copy input **registered AND mapped** |
| tuning-undefined | `tuningInfo = 0` | **3** | `REFUSED at INITIALIZE: NvEncInitializeEncoder -> 8 (NV_ENC_ERR_INVALID_PARAM)` |
| no-nvenc | dll treated as absent | **3** | `REFUSED at OPEN: INJECTED FAULT: nvEncodeAPI64.dll treated as absent` |
| skip-map | registered, skipped `NvEncMapInputResource` | **3** | `REFUSED at REGISTER+MAP: …skipped NvEncMapInputResource` |
| **MUTANT control** | `-DAIREPLAY_GATE_OFF` | **0** | reports ARMED with **no working encoder** — `engines=0 max=0x0` |

**What the green row is worth.** The MUTANT arm is the reason the other four mean anything: with
the gate compiled out, a broken encoder reports ARMED. The four green arms are not green because the
test is vacuous.

**Independently corroborated, not self-reported:** `ffmpeg -encoders` on this box lists
`h264_nvenc`, `hevc_nvenc` and `av1_nvenc`, and §5 encodes 300 frames through `h264_nvenc` at two
resolutions with `rc=0`. A third, unrelated binary reaches the same hardware.

**Profile / size / fps actually measured, not quoted from a spec:**

| property | value | provenance |
|---|---|---|
| codec / profile | **H.264 High** (avcC profile_idc read from the muxed file) | MEASURED |
| max width × height | **4096 × 4096** | MEASURED (product selftest + prior `nvenc-probe.exe` caps) |
| encoder engines | **2** | MEASURED |
| input path | **D3D11 texture → `NvEncRegisterResource` + `NvEncMapInputResource`, both rc=0** | MEASURED |
| 1080p60 / 2160p60 real encodes | `rc=0`, see §5 | MEASURED |

---

## 2. WGC — MEASURED REFUSAL, and it is the whole capture half

`_main\wgc-probe.exe` (built from another lane's `wgc-probe.cpp`; **run, not edited**), one run at
**12:13:08.912 → 12:13:09.140** (228 ms), re-confirmed by battery run 2 at **12:37**:

```
GraphicsCaptureSession::IsSupported -> 0x00000000 supported=1
CreateForWindow(our own window        ) -> 0x80070005 E_ACCESSDENIED  pid=32352
CreateForWindow(foreground window     ) -> 0x80070005 E_ACCESSDENIED  pid=1628
CreateForWindow(desktop window        ) -> 0x80070005 E_ACCESSDENIED  pid=1796
CreateForWindow(shell taskbar         ) -> 0x80070005 E_ACCESSDENIED  pid=13748
CreateForMonitor(primary monitor     ) -> 0x80070005 E_ACCESSDENIED
```

**POPULATION:** **5 of 5** capture items refused (own window, foreground window, desktop window,
shell taskbar, primary monitor), in 2 independent probe runs ~24 minutes apart, **both all-refused**.
**WINDOW:** 228 ms at 12:13:09; 5 items per run.

> **The battery's first run got this wrong and the fix is in the shipped script.** Run 1 printed
> *"PARTIAL: 5 of 6 items refused"* — implying one item had been captured — because the item-count
> regex had no `(` requirement and therefore matched the banner line
> `=== WGC CreateForWindow probe ===` as a sixth capture item, while the refusal regex was strict.
> A headline that says "partial" when the truth is "total" is exactly the kind of defect this lane
> exists to remove. Both patterns now share one predicate, and the script prints
> `WGC-COUNT INCONSISTENT` and downgrades the row to NOT MEASURED if the numerator ever exceeds the
> denominator again. Run 2 prints **"REFUSED on 5 of 5"**.

**What this measurement proves, stated as a result:**

- WGC is **supported** (`IsSupported` → true). The API surface is present.
- The refusal is **process-wide and window-independent**: our own window, somebody else's foreground
  window, a system window, the taskbar and the monitor are all refused with the same code.
- Therefore **there is no capture leg to time, at 1080p or at 4K** — see §5.
- It does **not** prove *why*. Receipt-03 §7 carries the hypothesis work (no TDR, no policy value,
  consent store says Allow, `RequestAccessAsync` returns S_OK and does not restore access). This
  lane re-measured the *effect*, not the cause, and does not restate the cause as fact.

---

## 3. THE MUXER — proven end to end, and one MP4 you can check

`--cut-from-h264` fills the ring from a real Annex-B elementary stream and runs the **same
`perform_cut()`** the live path runs. No WGC, no NVENC, no D3D11 — which is the only reason it is
provable at all today.

### 3a. The reference MP4 (the pre-existing 97.8 MB NVENC stream)

| property | value | provenance |
|---|---|---|
| path | `_main\runs\cap-offline-gaming.mp4` | MEASURED |
| size | **97 820 321 B** | MEASURED (`Get-Item`) |
| duration | **16.733333 s** | MEASURED (`ffprobe format=duration`) |
| codec | **h264 High, yuv420p, 1920×1080, r_frame_rate 60/1** | MEASURED (`ffprobe`) |
| frames | **1004 claimed by the product, `nb_read_frames=1004`** | MEASURED, independently |
| bit rate | 46 762 512 | MEASURED |
| null decode | `ffmpeg -f null -` → **rc=0, stderr 0 bytes** | MEASURED |
| cut wall clock | **135.5 ms** (product's own counter) / 489 ms whole process | MEASURED, N=1 |

The product claims 1004 frames and `ffprobe` independently counts 1004. That agreement is the whole
verification: a muxer that reported a frame count nothing else checked would be worthless.

### 3b. Two resolutions, freshly encoded by NVENC, muxed at both

Fixtures are produced by **`h264_nvenc`**, so building them also measures the encoder.
30 s / 1800 frames each (they must clear the ring floor — see §4).

| arm | stream | declared `--cut-size` | rc | aus | clip bytes | cut wall_ms (process) | ffprobe | null decode |
|---|---|---|---|---|---|---|---|---|
| **1080p** | 1920×1080 146 606 044 B | 1920×1080 | **0** | 1800 | 146 621 246 | run1 **783.8** / run2 **983.5** | `h264 Main 1920×1080 nb_read_frames=1800 duration=30.000000` | **rc=0, 0 B** |
| **4K** | 3840×2160 149 720 741 B | 3840×2160 | **0** | 1800 | 149 735 942 | run1 **841.0** / run2 **779.8** | `h264 Main 3840×2160 nb_read_frames=1800 duration=30.000000` | **rc=0, 0 B** |

**POPULATION:** 2 cut runs per arm per battery run (median reported), 2 battery runs, 1 ffprobe and
1 null-decode per arm. **WINDOW:** 1800 frames / 30.000 s of container time per arm.

**I am not claiming a 4K/1080p write-time ratio from these numbers, and the reason matters.** The
process wall clock here is dominated by **reading a 146–150 MB file into RAM and splitting 1800
access units**, not by writing the clip, and that read is I/O-bound and noisy: run 1 put 4K *slower*
than run 2 did, and the two runs disagree on which resolution is faster (run1 1080p=783.8 < 4K=841.0;
run2 4K=779.8 < 1080p=983.5). **The honest reading is that at this size the two are indistinguishable
on this box**, and any "4K costs 1.51× the write time" claim — which a single-run table invites — is
**DERIVED from noise**. The number that *is* stable is the **whole-process** figure, because it
includes the read: **~780–985 ms for a 146 MB, 1800-frame, 30 s clip**, i.e. **~150–190 MB/s
end-to-end through file read → ring → mux → file write**. The product's own internal `wall_ms`
(cut only, excluding the read) was **153.3 ms at 1080p / 231.5 ms at 4K** in the exploratory run at
12:19, which is the figure to quote for the cut itself and is labelled as *one run, one binary*.

---

## 4. A MEASURED REFUSAL that explains itself: the 16 MiB ring floor

The first attempt to mux anything failed, **all three arms, `rc=2`**, with:

```
OFFLINE CUT FAILED: ring capacity below 16 MiB - that cannot hold a cuttable window
```

**This is a result, not a broken battery**, and it is the clearest example in this project of a
failed row that still proves something:

- `ring_buffer.cpp:57` (was `:11` at 12:19 — the file moved) refuses any arena `< 16 MiB`, and `cut_from_h264` sizes the arena from the
  input (`replay.cpp:419-421` as of 12:52: `need = Σ(AU) + 4096 × aus`).
- MEASURED arithmetic: my first fixtures were 1 428 578 B / 300 frames → need **2.53 MiB**, and
  2 380 009 B / 300 frames → need **3.44 MiB**. Both are below the floor. The refusal was correct.
- Regenerating at 1800 frames gave needs of **146.85 MiB** and **149.82 MiB**, which clear it, and
  both then muxed (§3b).
- **The message is misleading and that is the actionable defect**: it blames a "cuttable window",
  which is not the reason. The reason is an unconditional floor. Anyone debugging this by the
  message will go looking for a window problem that does not exist.

**Consequence the owner should know:** on the product's own default settings the ring is hundreds of
MB, so the floor never bites in production. It bites on **short clips**, which is exactly what
someone testing the cut path will try first.

---

## 5. THE DEFECT: the muxer writes the size you told it, and ffprobe cannot see it

### 5a. How it was found

I expected the container to contradict the stream and I ran a **control**: a real 4K stream muxed
with a deliberately wrong `--cut-size`, and its mirror. Both exited **0**.

| arm | real stream | declared | rc | `ffprobe` (SPS-derived) | container `tkhd` | container `avc1` |
|---|---|---|---|---|---|---|
| 4K honest | 3840×2160 | 3840×2160 | 0 | 3840×2160 | **3840×2160** | **3840×2160** |
| **4K lied** | 3840×2160 | **1920×1080** | **0** | **3840×2160** | **1920×1080** | **1920×1080** |
| 1080p lied | 1920×1080 | **3840×2160** | **0** | 1920×1080 | **3840×2160** | **3840×2160** |

**`cap-mux-4k-lied.mp4` is a file that decodes at 3840×2160 and is declared as 1920×1080.**

### 5b. Where it comes from

| line | writes |
|---|---|
| `replay.cpp:422-423` (was `:398-399`) | `w_ = w; h_ = h;` — takes the size from **`--cut-size`**, not from the stream's SPS |
| `mp4_writer.cpp:132-133` | `avc1` sample-entry width/height = `cfg_.width/height` (the **declared** value) |
| `mp4_writer.cpp:282-283` | `tkhd` width/height = `cfg_.width/height` (the **declared** value) |
| `mp4_writer.cpp:147-153` | `avcC` profile/level/SPS/PPS = the **real** bytes from the stream |

So the file carries **two different truths**: the geometry boxes say what the caller claimed, and
the codec configuration says what the pictures actually are.

### 5c. Why nothing in the project's existing verification caught it

- `ffprobe` reports **3840×2160** — it reads the SPS. The contradiction is invisible to it.
- `ffmpeg -f null -` returns **rc=0 with 0 bytes of stderr** on the lied file. It decodes fine.
- `ffmpeg -i` prints `3840x2160`. It follows the SPS.
- `ffmpeg -vf scale=1920:1080` on the lied file returns **rc=0** — a player asked to present the
  track as 1080p will happily scale a 4K picture down and never know.

I extracted a frame from the lied clip and `ffprobe` reports **3840,2160**: the pixels really are 4K
while every geometry box in the container says 1080p.

### 5d. Severity — stated, not inflated

- **The live path was not measured, and I am not going to pretend otherwise** (§2: WGC refuses every
  item, so no live run happened). What I can say is bounded: `replay.cpp:422-423` is fed from the
  capture size, and on this box the display is 1920×1080, so a live run would most likely write a
  self-consistent file — **but that is an inference about a run I did not perform.** It becomes
  wrong the moment the negotiated capture size and the real stream disagree, which is precisely the
  condition `negotiate_capture_window` was just introduced to make *more* likely to vary (§7).
- **The defect is reachable** the moment anything sets the declared size without it matching the
  stream: the offline path's `--cut-size` is a free-standing flag with no validation against the
  SPS, and `replay.cpp:422-423` cannot tell the difference.
- **The fix belongs to the lane that owns `replay.cpp`/`mp4_writer.cpp`**, not to this lane. The
  minimal shape: parse the width/height out of the SPS already carried in `cfg_.sps` and **reject**
  a `--cut-size` that disagrees, the way the muxer already rejects a short stream (§4). Failing
  loudly is what §6's red arm is for.

---

## 6. RED ARMS — an instrument that cannot say NO proves nothing

| arm | input | rc | what it said |
|---|---|---|---|
| **junk file** | 2 816 B of ASCII, not H.264 | **2** | `OFFLINE CUT FAILED: no NAL units found` |
| **below floor** | 0.32 MiB real H.264 | **2** | `ring capacity below 16 MiB` |

Both refusals are MEASURED with `rc` read from `$LASTEXITCODE` after redirecting output to file.
Without these two arms, §3's greens would prove nothing — a muxer that silently produced a file for
any input would score identically.

---

## 7. TIMING — what was measured, and what could not be

| leg | 1080p | 4K | provenance |
|---|---|---|---|
| **capture (WGC)** | **NOT MEASURABLE** | **NOT MEASURABLE** | WGC refuses every item (§2). Any number here would be DERIVED from receipt-03 battery-2 (2026-10-07 11:14–11:18) and **was not reproduced**. |
| **NVENC encode** (external tool, 300 frames) | **1349.3 ms** (run2) | **3786.1 ms** (run2) | §8, 2 runs × 2 reps |
| **mux / cut — product's internal counter** | **153.3 ms** (1 run) | **231.5 ms** (1 run) | §3b exploratory run, one binary |
| **whole process** (read + ring + cut + write) | **983.5 ms** (run2) | **779.8 ms** (run2) | §3b, 2 reps median; run1 gave the opposite ordering |

**4K capture — this claim CHANGED UNDER ME, and the correction matters more than the original.**

At 12:19 `replay.cpp:57` read `tw_.create(1920, 1080, …)` unconditionally and `:61` set
`*w = 1920; *h = 1080`, so I recorded **"4K capture is not reachable from the flag surface"** as
DERIVED-from-source. **At 12:51 that is no longer true.** A sibling lane (L1/L2/L3/L7) landed a
window-negotiation path while this lane was running:

- `replay.cpp:71` — `negotiate_capture_window(cfg_.capture_w, cfg_.capture_h, desk)` now decides the
  capture size, with a `WINDOW NEGOTIATION:` log line carrying `source=`, `clamped=` and `auto=`.
- `replay.cpp:80` — `tw_.create(dec.w, dec.h, …)`; `replay.cpp:85` — `*w = dec.w; *h = dec.h`.

**So the hard-coded 1920×1080 clamp is GONE from the source.** However, the flag surface of the
binary this lane measured still exposes **no `--width`/`--height`** (`--help` re-read at 12:51), so
the honest statement is:

> **The 1080p clamp has been lifted in the source by another lane, but I did not measure a 4K
> capture, and I could not**: WGC refuses every capture item (§2), so no capture leg runs at any
> resolution. Whether `cfg_.capture_w/h` is reachable from the CLI is **UNVERIFIED by this lane** —
> check `main.cpp`'s parser for a `--width`/`--height`/`--capture-w` flag.

This is recorded rather than quietly rewritten because **it is the second time in this project that
a line-number citation from another lane's file went stale mid-measurement** (the first was the
16 MiB floor, §4). Cite the code, not the line, and re-verify before relying on it.

**Where the time goes** (the part that is measurable):

- **Encode is the expensive leg, and it is the only leg with usable numbers.** 300 frames cost
  **1152–1462 ms at 1080p** and **3619–4213 ms at 4K** — a ratio of **2.8–3.1×** for **4.0×** the
  pixels, so the scaling is **sub-linear** (§8 has the full stability analysis). Even at 14.0 ms/frame
  for 4K in the busiest run, the encoder stays under a 16.7 ms 60 fps budget — but only just, and
  that is one arm of a range, not a guarantee.
- **The muxer is not the bottleneck**, and the two-run spread is why I will not put a ratio on it:
  the internal cut counter says 153–232 ms for a 30 s clip, but the whole-process figure swings
  780–985 ms because a 146 MB **file read** dominates it. That read is an artefact of the offline
  test path (the live path never re-reads a file), so **it must not be quoted as product latency**.
- **The capture leg cannot be priced at all today**, and no amount of arithmetic fixes that. Any
  end-to-end "ShadowPlay-style capture" number for this box is currently fiction.

---

## 8. NVENC encode throughput (external tool, clearly labelled)

Measured with `ffmpeg -c:v h264_nvenc -preset p5 -tune ull -zerolatency 1` over **300 frames of
lavfi `testsrc2`**, wall clock including source generation **and** muxing — so it is an upper bound
on the encode itself, and is labelled as such rather than presented as encoder-only cost.

| resolution | frames | wall_ms med (run1 / run2 / run3 / run4) | ms/frame (incl. source+demux) |
|---|---|---|---|
| 1920×1080 | 300 | **1293.0 / 1349.3 / 1151.6 / 1461.6** | **4.310 / 4.498 / 3.839 / 4.872** |
| 3840×2160 | 300 | **3654.2 / 3786.1 / 3619.3 / 4213.4** | **12.181 / 12.620 / 12.064 / 14.045** |

**POPULATION:** 2 successful runs per resolution per battery run, **4 battery runs (8 samples per
resolution)**. **WINDOW:** 300 frames of synthetic `testsrc2` each — real GPU-generated pixels, but
**not** real capture content, so these numbers do not transfer to noisy game footage.

**What is stable, and what is not — measured across all four runs:**

| quantity | 4 observed values | spread | verdict |
|---|---|---|---|
| **4K** ms/frame | 12.181 / 12.620 / 12.064 / 14.045 | **±7.6 %** | usable as a range only |
| **1080p** ms/frame | 4.310 / 4.498 / 3.839 / 4.872 | **±11.9 %** | usable as a range only |
| the 4K/1080p **ratio** | **2.826 / 2.806 / 3.143 / 2.886** | **±5.8 %** | **NOT STABLE — quote no single value** |

**I originally wrote "2.81×, stable, two runs agree within 1 %". That was wrong, and my own
re-check is what caught it.** Across four runs the ratio is **2.81–3.14** (11.3 % spread on the first
three, tightening to 5.8 % with run 4). Both arms move together as the machine's load changes — run 4
was the busiest (many sibling lanes building) and both encode figures rose ~15 % while the ratio held
— so **the ratio is the more robust of the two numbers, but it is not a constant.**

**The defensible statement is a range: 4K encoding costs roughly 2.8–3.1× what 1080p costs on this
box, for 4.0× the pixels — i.e. sub-linear scaling** (every observed ratio is below 4). For a
planning number use **3×**, not 2.81×, and re-measure with more repetitions before depending on it.
**No encode figure here should be quoted as a single number**, and none is a ShadowPlay-clone
performance claim in any case, because it comes from an external tool (§ below).

**This is the ENCODER on this box, measured with an EXTERNAL tool. It is NOT the product's encoder
path**, which cannot run while WGC is refused. Anyone reading a "ms/frame" from this table as a
ShadowPlay-clone performance number would be reading a different machine's number.

---

## 9. AUDIO — every status carries an API, because a name is not an identity

The governing fact for this box: `CABLE Output (VB-Audio Virtual Cable)` exists at **MME #2,
DirectSound #15 and WASAPI #32**, and those three are **not interchangeable**; the loopback is
asymmetric across them; and the system default output is `VoiceMeeter Input`.

| row | value | provenance |
|---|---|---|
| `Win32_SoundDevice` census | N rows, each printed as `api=Win32_SoundDevice name=… state=…` | MEASURED, 1 CIM query |
| **per-API endpoint indices (MME / DirectSound / WASAPI)** | **NOT ENUMERATED** | **NOT MEASURED** |

**This battery deliberately does not claim a CABLE index.** `Win32_SoundDevice` does not report
per-API indices, so a row saying "CABLE at #15" from this script would be a DERIVED number wearing a
MEASURED label — exactly the defect this lane exists to remove. Producing a real per-API census needs
an `IMMDeviceEnumerator` walk per API, which is a C++ probe and not a PowerShell script.

---

## 10. HOW TO RE-RUN THIS WITHOUT ME

```
pwsh -File H:\sotto\_moved\aireplay\src\capture\run_battery.ps1
pwsh -File H:\sotto\_moved\aireplay\src\capture\run_battery.ps1 -Reps 5 -SkipBuild
```

- Exit **0** means the battery **ran**; it does **not** mean every row passed. Rows carry their own
  provenance and their own verdict.
- Every row prints `PROVENANCE | claim`, the result, and `POPULATION=…`.
- Output: `_main\logs\cap-battery-<timestamp>.txt`, plus one log per arm.
### Re-runnability was proven by running it twice, not asserted

| | run 1 | run 2 | run 3 | run 4 |
|---|---|---|---|---|
| started | 12:28:11 | 12:34:21 | 12:40:45 | 12:52:58 |
| **exit code** | **0** | **0** | **0** | **0** |
| binary sha256 it measured | `9697896D…` | `253020D9…` | `6A0FBB9F…` | `4735EDC3…` |
| build | `rc=0`, **0 warnings** | `rc=0`, **0 warnings** | `rc=0`, **0 warnings** | `rc=0`, **0 warnings** |
| law-6 gate arms | 5/5 **MATCH** | 5/5 **MATCH** | 5/5 **MATCH** | 5/5 **MATCH** |
| WGC | 5/5 refused *(mis-counted "5 of 6" — see below)* | **5 of 5** | **5 of 5** | **5 of 5** |
| muxer 1080p / 4K | rc=0 both | rc=0 both | rc=0 both | rc=0 both |
| LIED arm | `3840x2160` real / `1920x1080` declared | identical | identical | **identical** |
| red arms | rc=2, rc=2 | rc=2, rc=2 | rc=2, rc=2 | rc=2, rc=2 |
| **row census** | **M=15 D=1 NM=2** | **M=15 D=1 NM=2** | **M=15 D=1 NM=2** | **M=15 D=0 NM=3** |
| untagged rows | **0** | **0** | **0** | **0** |
| parse self-check | not shipped | not shipped | **passed** | **passed** |

**Four runs, four different binaries, identical verdicts on every qualitative row.** Each was
executed by me, unassisted. The only differences are the defects earlier runs exposed and later ones
fixed (below) — which is the point of running it more than once: a battery that has only ever been run
once by its author has never been tested as an instrument.

**The DERIVED→NOT_MEASURED change in run 4's census is deliberate and is the receipt improving, not
regressing.** Run 4 retires §7's "4K capture is NOT REACHABLE (DERIVED from source)" row, because a
sibling lane lifted the 1080p clamp at 12:26 — see §7 for the full before/after.

### Three defects the battery found IN ITSELF (all fixed, all in the shipped script)

1. **Run 1 reported "PARTIAL: 5 of 6 items refused" when WGC refused 5 of 5.** The item regex had no
   `(` requirement and matched the probe's own banner line. A headline that says "partial" when the
   truth is "total" is precisely the failure this lane exists to prevent — and it was **mine**.
   Fixed by making both counts share one predicate, plus a `WGC-COUNT INCONSISTENT` guard that
   downgrades the row rather than printing a nonsense ratio.
2. **Wall clocks printed `783,8` instead of `783.8`.** `CurrentCulture` on this box is pt-BR, whose
   decimal separator is `,`. A measurement whose *text* depends on the machine's locale invites a
   reader (or a CSV parse) to misread the value. Fixed: every number now formats through
   `InvariantCulture`, defined once.
3. **The summary table truncated the result column to 46 chars**, printing
   `wall_ms med=7..` — hiding the exact number the row exists to report. Fixed: the claim column may
   be trimmed, the result column may not.

Plus one more from authoring, before run 1: the script **did not parse** (a backtick after a closed
`)`, `Unexpected token`) and wrote a 252-byte log while exiting 1. A silent parse failure is
indistinguishable from a battery that ran and found nothing, so the syntax is now verified with
`[Parser]::ParseFile` before execution.

### Hard rules the script keeps (and one it had to learn)

- **No piped native command.** Every native call is `Start-Process … -RedirectStandardOutput` then
  `$LASTEXITCODE`. A closed pipe hid a real exit code behind a green report in this repo already.
- **No visible console window.** Children are launched with `-NoNewWindow`; nothing is spawned
  detached.
- **Native `H:\` paths only.**
- **It parses before it runs.** The first version died with a `ParserError` and wrote a 252-byte
  log. A silent parse failure is indistinguishable from a battery that ran and found nothing, so the
  script is now checked with `[Parser]::ParseFile` before execution and that check is part of the
  re-run evidence.
- **A backtick cannot continue an argument list after a closed `)`.** `Row ("x") ` on a continuation
  is `Unexpected token` in PowerShell. Every multi-argument call assigns its arguments to variables
  first and calls on one line. Reproduced in isolation, not guessed at.

---

## SELF-AUDIT

1. **Confidence per claim.**
   - *NVENC arms / §1*: **high**. Four arms plus a MUTANT control, `rc` from `$LASTEXITCODE`, and a
     third-party binary (`ffmpeg h264_nvenc`) reaching the same hardware. Moves down only if the
     binary hash changes.
   - *WGC refusal / §2*: **high for the effect, zero for the cause.** Five items, one run, 228 ms.
     This lane re-measured the effect and deliberately did **not** restate receipt-03's hypotheses
     as causes.
   - *Muxer green / §3*: **high**. Product frame count and `ffprobe` `nb_read_frames` agree, null
     decode clean, and a red arm proves the instrument can refuse.
   - *Container defect / §5*: **high.** Byte-level reads of four files, two of them controls, plus an
     extracted frame proving the pixels are 4K while the boxes say 1080p. Moves down only if
     `mp4_writer.cpp` changes.
   - *Timing / §7–8*: **medium by construction** — the capture leg is unmeasurable today, which is
     the honest answer, not a gap I papered over. Encode figures are external-tool and labelled so.
2. **Protocols missing.** No per-API audio census (§9) — needs C++, not a script. No live-capture arm,
   because there is none to run (§2). §3b's product-internal `wall_ms` is **N=1** from the
   exploratory run and is labelled as such; the battery's own figures are N=2 per arm per run.
3. **Extra verification I ran beyond the brief.**
   - **Two lie-controls** (4K-as-1080p and 1080p-as-4K) — these are what turned "the muxer might
     write the wrong size" into a measured, bounded defect, and the mirror control is what showed
     the defect is the *declared* value winning rather than the flag being ignored.
   - **The 16 MiB floor found by arithmetic**, not by reading the error message: I computed
     `need = Σ(AU) + 4096 × aus` for my own fixtures and confirmed both were under the floor
     before regenerating them.
   - **`ffmpeg -vf scale=1920:1080` on the lied file** (rc=0) and **frame extraction** (`3840,2160`),
     to establish that a player is not forced into an error and is therefore never told anything.
   - **A red arm for the NVENC gate itself** is not possible without a non-product binary, so the
     corroboration is a *third-party* one: `ffmpeg -encoders` lists `h264_nvenc`, and §5/§8 reach the
     same hardware with it. Two unrelated binaries, one hardware encoder.
4. **Named verification boxes I created.**
   - `probe-cap-tkhd.ps1` — container box reader (`tkhd`, `avc1`, `avcC`). **It lied three times
     before it worked**, all three false negatives on files `ffprobe` reads perfectly, and all three
     are documented in its header: PowerShell array unrolling, an ambiguous box offset, and —
     the instructive one — `$type` vs `$Type` being **the same variable**, because PowerShell names
     are case-insensitive, which made every comparison a tautology and the function returned the
     `ftyp` box while appearing to search. It prints a `SELFCHECK` line with the offsets it walked,
     so the next reader can see it walked a real chain rather than trusting the verdict.
   - `run_battery.ps1` — the battery, with a provenance tag on every row, an `untagged=` count in
     the summary, a parse self-check, and an inconsistent-count guard.
5. **Reviewer.** **NOT DISPATCHED — and that is a gap I am reporting rather than papering over.**
   The lane brief makes a verifier subagent mandatory, but **this seat has no `task`/dispatch tool**
   (`task_query` lists only local `bash` background tasks; a `task(agent_name="verifier", …)` call
   returns "Task not found"). So the provenance audit below was performed by **me, on my own
   numbers**, which is strictly weaker: an author auditing their own claims is exactly the reader
   whose blind spot the reviewer exists to catch. **A verifier must still audit this receipt.**
   To make that cheap, the evidence is pre-assembled at
   `_main\logs\cap-review-bundle.txt` (run 1 / run 3 summaries + independent `ffprobe` of all four
   products), and `_main\logs\cap-battery-RUN{1,2,3}.txt` hold the raw output.
6. **What that self-audit already caught** (which is the argument for dispatching one anyway):
   - **The "2.81× stable" claim in §8 was an overclaim.** It rested on two runs agreeing within 1 %;
     the third run gave **3.14**, an 11.3 % spread. Corrected to a **2.8–3.1× range** with the
     stability table, and §7 was corrected to match. *This is precisely the DERIVED-dressed-as-
     MEASURED failure the reviewer was supposed to catch, and it was in my own draft.*
   - Every MEASURED number was traced back to a log line or an independent tool reading; the
     byte counts and the 4K/1080p ratios were recomputed from the raw run logs.
   - §7 was confirmed to contain **no capture timing number at all** — the capture leg appears only
     as `NOT MEASURABLE`.
6. **Gate doubts.**
   - `verde-de-verdade:` the muxer and the NVENC gate. Both have red arms that actually go red, and
     the muxer greens are corroborated by `ffprobe` counting frames independently.
   - `falta-no-gate:` **the container `tkhd`/`avc1` geometry has no gate at all** — that is §5, and it
     is why the defect survived every existing verification in this project. A `tkhd-vs-SPS`
     assertion belongs in the battery the moment the owning lane fixes it; `probe-cap-tkhd.ps1` is
     already wired into the LIED arm and **will turn it red** when `replay.cpp:422-423` starts
     validating `--cut-size` against the SPS.
   - `gate-melhor:` a **run-level guard that the binary hash matches the hash this receipt names**.
     The hash already changed twice in 24 minutes (§ header) because other lanes were editing the
     source tree, so a receipt read next week could be quoting a binary that no longer exists.
     The battery prints its hash every run; what is missing is a check that someone *reads* it.
