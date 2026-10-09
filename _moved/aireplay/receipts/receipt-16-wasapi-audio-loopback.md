# receipt — 16 WASAPI audio loopback (the missing audio feature, measured not invented)

1. **The problem, as measured.** 8 of 8 sample clips in this repo carry **no audio stream**, while
   `src/asr/audio.py:53-61` (`_check`) REFUSES anything that is not 16 kHz mono PCM16. Nothing fed
   the transcript: the product's audio path did not exist. This lane builds the capture component.

2. **What was delivered — exactly three files, none of them owned by another lane.**
   - `src\capture\wasapi_audio.h` — the contract, with the provenance of every measured constant.
   - `src\capture\wasapi_audio.cpp` — enumerate · open loopback · deliver PCM · measure peak ·
     return an explicit `silent-device`.
   - `_main\_lane2-audio-gate.ps1` — the named mechanical gate.
   **NOT touched:** `main.cpp`, `replay.*`, `mp4_writer.*`, `ring_buffer.*`, `nvenc_*`, `src/asr/*`,
   `build.cmd`. The mux hookup is §7 below, as code to insert, not as an edit.

3. **Reused, not reinvented.** The Python reference `H:\sotto\worker\wasapi_loopback.py` is the
   working implementation on this box. Each piece it encodes is carried over with its line number in
   the `.cpp` header comment: the six-step open sequence (`:11-27`), COM's three outcomes (`:166-217`),
   friendly name via `OpenPropertyStore` (`:331-389`), the non-negotiable mix format (`:402-449`), the
   device meter (`:490-516`), order-by-who-is-rendering (`:519-591`), `AUDCLNT_BUFFERFLAGS_SILENT`
   handling (`:980-1002`), and the poll period that beats the ring (`:935-952`).

4. **MEASURED — a real capture, on the live device ladder, on this box.**
   `_main\build\lane2-gate\lane2-gate.json`, run 2026-10-07, **window_ms=1500, meter_ms=200**:

   | # | endpoint (`api=` on every one) | meter peak (200 ms) |
   |---|---|---|
   | 1 | `CABLE Input (VB-Audio Virtual Cable)` | 0.050553 |
   | 2 | `VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)` *(default)* | 0.000000 |
   | 3 | `Speakers (NVIDIA Broadcast)` | 0.000000 |
   | 4 | `AG251F1WG2 (NVIDIA High Definition Audio)` | 0.000000 |
   | 5 | `Alto-falantes (HyperX Quadcast)` | 0.000000 |

   **POPULATION = 5 active render endpoints. The ladder chose step 1/5** — the one carrying signal,
   not the default — which is exactly the defect the ordering exists to remove. The chosen tap over
   **WINDOW = 1500 ms** delivered: `blocks=15 packets=150 frames=72000 silent_packets=0 gaps=0
   dropped_frames=0 peak=0.807769 rms=0.195616 floor=0.001000`, `grant_frames=1056`.
   **The peak varies per run** (0.008431 / 0.130304 / 0.616773 / 0.698243 / 0.807769 / 0.819975 across
   6 runs) because it is the owner's actual audio, not a constant. `state=ok`.

5. **The format decision, justified against `src/asr/audio.py`.** Delivered: **float32 MONO at the
   endpoint MIX rate** (measured 48000 Hz, 2 ch, float32 on this box), plus `to_asr_pcm16()` to reach
   the model's 16 kHz mono PCM16. It is NOT delivered at 16 kHz because **a WASAPI loopback stream has
   no format negotiation** — it must be initialised with the mix format or `Initialize` fails (the same
   constraint `wasapi_loopback.py:22-24` documents). float32 rather than PCM16 in between because the
   endpoint already runs 16 k→48 k→16 k; one quantisation at the end beats three. `audio.py`'s refusal
   is respected by construction, not by hope.

6. **Silence is loud, not empty — and this was the lane's hardest-won defect.**
   `audio_state_for(open, frames, peak)` is the whole verdict function, factored out so it can be
   checked on a fixed table: `closed` → `no-signal` → `silent-device` (`peak <= 1e-3`) → `ok`.
   The floor `1e-3` is a bracket, not a tuning knob: **8x above** the measured digital-silence ceiling
   (0.000122, a 22 s passive listen) and **~500x below** the measured injected tone (0.4999).
   A silent window logs `WASAPI_AUDIO_SILENT … cause=nothing is routed into this render endpoint`, so
   the run says why instead of exiting 0 quietly.

7. **THE HOOKUP INTO `mp4_writer` — CODE TO INSERT, NOT AN EDIT.**
   `mp4_writer` (`mp4_writer.h:16-24`, `mp4_writer.cpp`) is **video-only**: it builds `ftyp`/`mdat`/`moov`
   for H.264 and writes **no** audio track. Adding AAC needs `Mp4Config` to gain an audio half (a
   second `trak`, a second `stsd` entry with `esds`, and an interleaved `stco`/`stsz`/`stts`). That is
   an edit to a file this lane does not own, so it is specified here, not performed:
   - **file** `src/capture/mp4_writer.h` · **anchor** `struct Mp4Config` (line 16) · **add**
     `uint32_t audio_rate; uint16_t audio_channels; std::vector<uint8_t> asc;`
   - **file** `src/capture/mp4_writer.cpp` · **anchor** the `moov` writer in `close()`
     · **add** a `trak`/`stsd`/`esds` block using `asc` (the AAC AudioSpecificConfig), and interleave
     AAC frames written by a new `write_audio_sample(data, size, duration_ticks, err)`.
   - **file** `src/capture/replay.cpp` · **anchor** where the cut's `Mp4Writer` is opened
     · **add** an `WasapiAudio` per cut, opened on the endpoint the ladder picked, with
     `try_get_block()` feeding both `to_asr_pcm16()` (→ the ASR, at 16 kHz) and the AAC encoder (→ the
     mux, at the mix rate).
   **UNKNOWN and deliberately not claimed:** NVENC exposes H.264/HEVC video only — it is **not** an
   audio encoder. AAC needs a separate encoder (Media Foundation `MFCreateAudioEncoder` or a built-in),
   which is a lane of its own and was NOT measured here.

8. **The gate — `pwsh -NoProfile -File _main\_lane2-audio-gate.ps1` → `LANE2-GATE PASS`, exit 0.**
   - **ARM-A1** the TU compiles with the repo's OWN path: the exact compiler, flags and library list
     read from `src/capture\build.cmd:7,12`. rc=0, **warnings=0** under `-Wall -Wextra`.
   - **ARM-A2** it links with **no library beyond what `build.cmd` already links**. This arm earned its
     keep: `KSDATAFORMAT_SUBTYPE_PCM` (ksuuid) and `PropVariantClear` (propsys) both COMPILE fine in
     isolation and fail only at link time in the product. Both were removed; the subformat GUIDs and
     `CoTaskMemFree` are now spelled out locally.
   - **ARM-B** a real capture on the live ladder, printing the measured peak with POPULATION and WINDOW.
   - **ARM-C — THE CONTROL, and it goes red.** A byte copy of the `.cpp` with BOTH cures reverted
     (cure-1 the named silence verdict; cure-2 the single COM ownership handoff), rebuilt and
     re-checked: `live_table_bad=0` vs `control_table_bad=4`, `goes_red=True`.
   - **ARM-D — the second control.** Five open/close cycles, asserting `com_reference_balance()==0`.
     Live `0` (7 taken / 7 released) against the reverted copy's `−6` (7 / 13) — see §11 for why the
     crash-free "did it run" version of this arm was worthless.
   **A SILENT DEVICE IS A VALID GREEN OUTCOME** and the gate is built so it can say so: it separates
   `RUN-VERDICT` (the instrument ran and produced a NAMED verdict) from `MEASUREMENT` (peak, POPULATION,
   WINDOW). A gate that went red merely because the PC was quiet would be a gate nobody could trust.
   - **NEGATIVE TEST (the gate can say NO).** The silence floor in the live `.cpp` was temporarily
     rewritten so that EVERY peak maps to `silent-device`, and the gate re-run.
     **MEASURED: `LANE2-GATE FAIL`, rc=1** — `live_table_bad=2` (the loud `0.698243` case and the
     `0.0011` over-floor case both misclassified), `goes_red=False`. The file was then restored and
     verified **byte-identical** (sha256 `8D6585047B1A3E77…` before and after), and the gate returned to
     PASS. A gate that has only ever printed PASS has not been tested.

9. **THE CRASH, and why the control had to be rebuilt twice.** The first live run died with
   `0xC0000005` every time (3/3). gdb pinned it to `wasapi_audio.cpp:334`; the faulting address was
   `0xffffffffffffffff` and the "function pointer" held `0xbaadf00d00000001`.
   **Cause:** a COM object is a pointer to a **vtable pointer**. Declaring
   `struct { fn* QI; fn* AddRef; fn* Release; fn* GetPeakValue; }` and casting the **object** to it reads
   offset 24 **of the object** — not of the vtable. The call then jumped to a *data* address inside
   `AudioSes.dll`. **Fix:** a `Vtbl` struct plus an object holding `Vtbl* lpVtbl`, i.e. dereference
   twice. **Measured before/after on the same device:** slot 3 `0xffffffffffffffff` → `0x7ff94a6f9250`
   (a real function in the same DLL), and the meter then reads a live peak.
   **The transferable lesson, and why it is in this receipt rather than only in a comment:** the cast
   compiles just as happily against the wrong pointer, so this shape is now asserted by a gate.

10. **TWO MORE BUGS FOUND BY SELF-AUDIT AFTER THE GATE WAS ALREADY GREEN.** Recording them because a
    green gate that had not found them is exactly the thing this repo keeps warning about.
    - **A double `CoUninitialize`.** `com_ref_taken_ = com.took()` was set while a local `ComScope`
      destructor *also* uninitialised COM on return, and `close()` uninitialised a third time: **three
      releases for one initialise**, walking the apartment count negative.
    - **A leak on every failed open.** `enumerator_`/`device_`/`client_`/`capture_` were filled in but
      nothing released them when `open_common` returned false — so a ladder walking six endpoints and
      failing five would leak five COM reference sets per pass.
    **Fixes:** `com.take()` hands the reference to the object exactly once and disarms the scope; a
    `FailGuard` releases whatever a failed open acquired. `armD` in the gate is what holds both honest.

11. **A BALANCE BEATS A CRASH, and this is the arm's real lesson.** `CoUninitialize` is
    reference-counted, so the double release **does not crash** — MEASURED, the reverted copy ran
    **5 of 5 open/close cycles reporting `bad=0`** and looked perfectly healthy. Only an explicit
    counter names it: `com_reference_balance()`.
    **MEASURED, live vs reverted, same gate run:**

    | | taken | released | balance |
    |---|---|---|---|
    | live build | 7 | 7 | **0** |
    | cure-2 reverted in a COPY | 7 | **13** | **−6** |

    A generic lesson: a "did it crash / did it run" check is not a check. It passed on the broken build.

12. **A CONTROL THAT COULD NOT SAY NO — caught and fixed twice.** ARM-C v1 checked the *live* capture
    states. MEASURED: `live_state=ok control_state=ok disagrees=False` on a host with audio playing:
    the cure under test was never exercised and the arm passed **vacuously**. **Fix:** a
    **deterministic verdict table** (8 fixed cases, no audio device opened), so the control fails
    whenever the cure is reverted, regardless of what is playing. It fails **4/8**, as it must.
    The same trap then appeared in ARM-D and was fixed the same way (§11).

13. **A SILENT NO-OP, caught.** With `pwsh -File`, a `--window-ms 1200` argument does **not** bind and
    does **not** error — the script silently ran on its defaults and looked green while measuring a
    different window than the one asked for (MEASURED: requested 800/120, ran 1200/150). The gate now
    prints the window it **actually used** on every run, and documents `-WindowMs` (single dash).

14. **House rules.** **No visible console window:** the gate spawns only console exes writing to
    redirected handles; a census filtered on the ARTIFACT names (`lane2-audio-probe`, not the bare word
    `sotto`) found **0 live probe processes** after the run. The `g++.exe`/`cc1plus.exe` seen alive at
    that moment belong to **lane 7** (`aireplay-capture-PRE-lane7.exe` in their command line), not to
    this lane. **No pipe to read an exit code:** every build and run goes to a file, then `$LASTEXITCODE`
    (law 2). **Native `H:\` paths only.** **Line endings** verified LF-only, matching every existing
    file in `src/capture`. **Git: nothing committed by this lane** — and note that an automated
    "wake" daemon (`mateusant13`) commits this repo periodically and swept these two files into commit
    `066005d` mid-lane; the content committed was my own work-in-progress, not another lane's.

15. **Cost of being wrong, stated.** If the loopback silently delivered the DEFAULT endpoint instead of
    the one carrying audio, the product would transcribe silence while the owner hears sound — the exact
    defect the meter ordering removes, and the reason `api=` and `endpoint_id=` ride on every line.

16. **REVIEWER: NOT DISPATCHED, and why.** The brief requires a `verifier` subagent. **This session has
    no `task(...)` dispatch tool** — its entire toolset is Bash/Edit/Glob/Grep/Read/Write/WebFetch/
    WebsiteDeploy/Task{Output,Query,Stop}. I did **not** fake a dispatch and did **not** report a verdict
    I never received. In its place I ran the adversarial self-audit of §10, which found **two real
    defects that the then-green gate had passed** (§11), and I built the arm that now holds both honest.
    **The seat was never handed a file to write**, so the seat constraint is not violated by its
    absence — but the reviewer step itself is genuinely OUTSTANDING and needs dispatching from a session
    that has the tool.