# Receipt — per-app audio separation gate: BUILD (2026-10-11)

**Provenance.** This is the verbatim verdict file produced by the gate lane (subagent
`820db366-adbc-44d0-af81-18dc1a7867e3`), copied into the repo so the decision survives outside
`I:\cc-tmp`. Original: `I:\cc-tmp\per-app-tap-gate-VERDICT.md` = **19 700 B, sha256
`222412A545ECF18815A0A68536329046CAF1B92DDD977A37D7700B306BDB5108`** — re-verified BY ME with
`node` + `crypto.createHash('sha256')` over the same bytes, and it MATCHED the lane's own corrected
pin (its first message carried a stale `2e59fd55…` for a 18 972 B revision; the lane withdrew one
unmeasured assertion and re-issued the pin above — the withdrawal is in §1 of the file below).
**Evidence status: measured by the lane, not re-measured by the Lead.** I did not re-run the gate:
re-running it means rendering a tone and opening endpoints on the owner's live box, and the owner's
standing order (top of `AGENTS.md`) forbids me from opening Sotto — the gate lane's own instruments
were separate hidden processes under `I:\cc-tmp` and it never launched the shell, `run.cmd` or the
worker.

**What it decides.** The Windows process-loopback API (`ActivateAudioInterfaceAsync` +
`AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK` on `VAD\Process_Loopback`) WORKS on this build and
DISCRIMINATES BY PID: INCLUDE on a separate renderer's pid read peak 0.399993 while an independent
capture of the same endpoint read the same tone at 0.399834, and the SAME activation on a live,
non-rendering pid read **exactly 0.0** while that endpoint still carried the tone. Therefore the
owner's hard requirement — *"audios de diferentes apps tem que ser separados e processados
separadamente"* — has a working mechanism, and `ProcessLoopbackTap` beside `WasapiLoopbackTap` is
justified. Implementation proceeds; every step that needs a LAUNCH (device open, real capture, panel
integration) stays UNMEASURED until the owner lifts his order.

**What it does NOT decide (the lane's own UNMEASURED list, verbatim in the file):** sample-exactness
vs the endpoint's own loopback; DRM-protected audio; UWP/AppContainer/audiosrv targets;
multi-endpoint and exclusive-mode targets; start/stop mid-window as a contract; CPU/RAM cost and the
`worker/sotto_worker.py` integration. NEG-B is weak on this build (pid 0 rejected but
`0xFFFFFFFE` accepted) so discrimination rests on NEG-A alone.

---

# Per-app audio separation — GATE VERDICT (ARM 1a / ARM 1b / ARM 2)

Box: this Windows host, 2026-10-11. Workspace: H:\sotto (READ-ONLY this lane). All new artefacts
under I:\cc-tmp. Every number below was produced by a live run in this session unless it is
explicitly labelled *cited* (the predecessor's ARM 1a).

---

## 0. DECISION — ONE LINE

**BUILD** — deciding measurement: **INCLUDE-mode process loopback on the renderer's own pid
(26724, a SEPARATE process) received peak 0.399993 / rms 0.281701 (394 packets, 189120 frames,
391 nonzero) while an INDEPENDENT capture of CABLE Output measured the same 440 Hz tone at
0.399834 inside the same 4.0 s window, and the same INCLUDE activation on a live, non-rendering
pid read EXACTLY 0.0 while that endpoint still carried 0.399834.**

Scope of the decision: the WASAPI application-loopback API (`ActivateAudioInterfaceAsync` +
`AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK` + `PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE`)
DOES deliver a single process's render audio on this build/host, for a target on a NON-default
endpoint (ARM 1b) and for a real third-party application on the DEFAULT endpoint (ARM 2), with a
negative control that reads exactly zero in the same window. The `ProcessLoopbackTap` beside
`WasapiLoopbackTap` is justified. What this decision does NOT cover is listed in section 6.

---

## 1. Instrument discipline (what would have made this refuse)

Pre-registered before the arms ran, all inside `I:\cc-tmp\plp-target.py` / `gate-arm1b.py`:

* **Baseline first, always** — the endpoint is captured with NOTHING of ours rendering, so ambient
  audio is a measured number, not an assumption. On this box the ambient is REAL: a 100 s passive
  listen read **CABLE Output 0.127411** (MME#2) and **VoiceMeeter Output 1.0** (MME#1) at 17:0x,
  and VoiceMeeter Input still clips at **1.0** at 17:21. A bare "peak >= 0.05" assertion would have
  been vacuous; hence the tone gate below.
* **Tone gate (ARM 1b)** — the INCLUDE arm is only allowed a verdict if the 440 Hz tone was
  demonstrably AT the endpoint inside that same window, at >= max(0.05, 2 x ambient tone).
  Otherwise exit 5, `refused-endpoint-not-carrying-tone`, no verdict.
* **Peak gate (ARM 2, a real app is not a tone)** — the endpoint must have carried audio at a
  broadband peak >= 0.05 inside the INCLUDE window, else exit 5, `refused-endpoint-silent`.
* **NEG-A in every run** — the SAME activation, INCLUDE mode, on a live pid that renders nothing
  (the probe's own), in the same window as the target's arm. If NEG-A is not silent the run cannot
  be read as per-app capture at all.
* **Timestamps on every arm window** — so an independent instrument can be compared against the
  arm's window on the clock rather than on the hope that two runs overlapped.

---

## 2. ARM 1a — *cited*, predecessor (not re-measured by this lane)

`python _main/inject-all-probe.py 8 "CABLE Input"` → tone injected into CABLE Input, captured
independently: **MME#2 0.499969 / DirectSound#15 0.5 / WASAPI#32 0.499916**. This is what proves the
endpoint-capture instrument itself can see a tone at CABLE Output, and that the three host APIs of
that endpoint are NOT interchangeable.

---

## 3. ARM 1b — GREEN (tone target = a separate process; INCLUDE / EXCLUDE / NEG-A)

Command (one run, ~37 s of renderer life):

    python I:\cc-tmp\gate-arm1b.py --mode arm1b --seconds 4 --cross-check 30 --json I:\cc-tmp\gate-arm1b.json

| step | command (exact) | measured |
|---|---|---|
| 1 BASELINE | `tone-cross-check.py 8.0 --label baseline --needle "cable output" --tone-hz 440 --floor 0.05` | MME#2 peak **3.1e-05** tone **2e-06**; DS#15 peak **3.1e-05** tone **2e-06**; WASAPI#32 peak **0.0** tone **0.0** → verdict `NOTHING` |
| 2 RENDERER | `arm1b-cross2-render.py I:\cc-tmp\gate-arm1b.stop 180.0` (child pid **26724**, `CREATE_NO_WINDOW`) | `render=CABLE Input (VB-Audio Virtual C)`, `render_api=MME`, index 9, amp 0.4, 440 Hz, rate 44100; final `frames_written=1627290 seconds_rendered=37.177 own_peak=0.4`, rc 0 |
| 3 CONTROL | `tone-cross-check.py 8.0 --label control --needle "cable output" ...` | MME#2 peak **0.400269** tone **0.399834**; DS#15 peak **0.410889** tone **0.399833**; WASAPI#32 peak **0.399925** tone **0.399834** → verdict **TONE-PRESENT** (floor 0.05) |
| 4a TAP INCLUDE | `plp-target.py --target-pid 26724 --arm-mode both --seconds 4 --cross-check 30 --cross-check-needle "cable output" --baseline-seconds 2 --require-tone` | packets **394** frames **189120** nonzero **391** silent 0, peak **0.399993**, rms **0.281701**, 48000 Hz 2 ch; endpoint in the SAME window peak **0.399963**, tone **0.399834** |
| 4b TAP EXCLUDE | same run, EXCLUDE_TREE on 26724 | packets **194** frames 93120 nonzero 191, peak **0.035214**, rms **0.002004**; endpoint in that window peak 0.399963 tone 0.399834 → the target's tone was NOT in the excluded arm (8.8 % of the tone level, i.e. other apps' audio) |
| 4c NEG-A | same run, INCLUDE_TREE on the probe's own pid (live, renders nothing) | packets **199** frames 95520, nonzero **0**, peak **0.0**, rms **0.0**; endpoint in that window peak 0.399963 tone 0.399834 |
| 5 STOP | stop file `gate-arm1b.stop`; only the child this script started | renderer rc 0; nothing of ours left rendering |

**Verdict of the run:** `target-loopback-proven`, exit **0**. The 440 Hz amplitude arrived at the
tap essentially unchanged (0.399993 vs 0.399834 at the endpoint; the renderer's own amplitude 0.4).

ABI facts measured in the same run (they are what the tap must implement):

* `PROPVARIANT` blob, **direct** layout, `blob.cbSize=12` → `hr_activate=0x00000000` ACCEPTED;
  **wrapped** layout (`cbSize=16`) → `0x80070057` REFUSED. Sizes: process_loopback_params 8,
  activation_params 12, PROPVARIANT 24, blob offset 8.
* `GetMixFormat` on the application-loopback client → **0x80004001 (E_NOTIMPL)**; the working
  initialisation is the DECLARED format **float32 48000 2 ch + LOOPBACK|AUTOCONVERTPCM**
  (`flags=0x88020000`, `hns=0`), `GetBufferSize` → 480 frames.
* NEG-B deviation: pid 0 is rejected (`0x80070057`) but **pid 0xFFFFFFFE is ACCEPTED** by this
  build. The discriminating power therefore rests on NEG-A, which is measured at exactly 0.0.

---

## 4. ARM 2 — a REAL application (Discord.exe pid 19524), run twice

Target selection, measured: `audio-sessions.py --all` at 17:17 → **Discord.exe 19524 state=1
(ACTIVE)** and nvcontainer 17240 / League of Legends 33336 active on **VoiceMeeter Input**, which is
the SYSTEM DEFAULT render endpoint (`is_default=true`). No GUI app was launched; nothing was killed.

### 4.1 Run 1 — 17:18:08 — INCLUDE loud, corroboration REFUSED (honest refusal)

    python I:\cc-tmp\gate-arm1b.py --mode arm2 --target-pid 19524 --needle "voicemeeter output" --seconds 4 --cross-check 20 --json I:\cc-tmp\gate-arm2-discord.json

| arm | packets | frames | nonzero | peak | rms | endpoint in window |
|---|---|---|---|---|---|---|
| INCLUDE (19524) | 398 | 191040 | 253 | **0.985046** | 0.112595 | peak **0.026306** (< 0.05 floor) |
| EXCLUDE (19524) | 198 | 95040 | 195 | 0.004775 | 0.001035 | peak 0.000229 |
| NEG-A (probe pid) | 199 | 95520 | **0** | **0.0** | 0.0 | peak 0.000362 |

Verdict: **`refused-endpoint-silent`, exit 5** — the pre-registered gate refused because the
corroboration endpoint (VoiceMeeter Output) read 0.026306 in that window. This refusal is KEPT in
the record: it is the instrument working, not a result to be quietly re-run away. Its cause was
measured afterwards (section 4.3): the owner's audio is BURSTY (VoiceMeeter Input per-second maxima
at 17:21: 0.018, 0.018, 1.0, 1.0, 0.021, 0.971, 1.0) and the arm landed in a gap, and VoiceMeeter
Output is a different bus from the default render endpoint.

### 4.2 Run 2 — 17:22:35 to 17:22:46 — GREEN, with a concurrent independent instrument

    python I:\cc-tmp\arm2-metered.py 19524 --tag arm2-discord-metered --needle "voicemeeter output"
      (spawns: plp-target.py --target-pid 19524 --arm-mode both --seconds 4 --cross-check 25
               --cross-check-needle "voicemeeter output" --baseline-seconds 2
       and, CONCURRENTLY, endpoint-meter.py 45 --hz 20 --json endpoint-meter-arm2-discord-metered.json)

| instrument | INCLUDE window | EXCLUDE window | NEG-A window |
|---|---|---|---|
| tap INCLUDE (Discord tree) | **peak 0.986503**, rms 0.183664, 394 packets, 189120 frames, **385 nonzero**, 48000/2ch | — | — |
| tap EXCLUDE (everything BUT Discord) | — | **peak 0.000080**, rms 0.000015, 198 packets, 195 nonzero | — |
| tap NEG-A (probe's own pid, INCLUDE) | — | — | **peak 0.0**, rms 0.0, 199 packets, **0 nonzero** |
| sounddevice capture, VoiceMeeter Output (MME#1 / DS#14 / WASAPI#32) | peak **0.226166** | peak 0.037106 | peak 0.163822 |
| **IAudioMeterInformation, VoiceMeeter Input (default render)**, 20 Hz, epoch-aligned | **max 1.0** (75 samples) | max 0.412937 (38 samples) | max 0.994824 (39 samples) |

**Verdict of the run:** `target-loopback-proven`, exit **0**. Discord's pid was alive at start and
at end (`alive_at_end=true`).

Why the two loud rows are consistent and why they matter: the meter measures the endpoint MIX
(it cannot attribute), and the EXCLUDE tap measures everything EXCEPT Discord's tree. The endpoint
was loud (meter 0.41-1.0) in the very windows where the tap could only hear Discord (INCLUDE
0.986503) and where everything-else was silent (EXCLUDE 0.000080, four orders below the INCLUDE
arm and below the 0.05 floor). So the audio the endpoint was carrying in those windows IS Discord's
tree's audio, and the per-app tap captured it. NEG-A is the instrument's NO: the same activation on
a live non-rendering pid read exactly 0.0 while the meter read 0.994824.

Also measured, and it widens the decision: Discord renders into the **default** endpoint
(VoiceMeeter Input) and was captured at 0.986503, while ARM 1b's renderer wrote into a **non-default**
endpoint (CABLE Input) and was captured at 0.399993. In the two configurations measured, the tap is
**endpoint-agnostic**.

### 4.3 The instrument that settled run 1's refusal

`endpoint-meter.py 6 --hz 20` at 17:21 standalone: **VoiceMeeter Input** per-second maxima
0.017725, 0.017821, **1.0**, **1.0**, 0.021197, 0.970775, **1.0** (every other render endpoint
0.0). The default render endpoint is carrying the owner's audio at CLIPPING level in bursts, and
the gap level (~0.018) is exactly the order of the 0.026306 that run 1's corroboration read.

---

## 5. WHAT WAS REFUTED

1. **"The process-loopback API is refused / unusable on this build"** — REFUTED. INCLUDE activated
   (`hr_activate=0x00000000`) and captured the target's audio in both ARM 1b and ARM 2.
2. **The predecessor's own falsifier ("own render child silent at CABLE Output, so the gate is
   blocked on the instrument")** — REFUTED as a claim about the API. The API was never the problem:
   with a renderer that provably puts a tone at the endpoint (separate process, MME), INCLUDE
   captures it. The predecessor's `int32 vs float32` render-buffer hypothesis for its own child
   remains UNRESOLVED and is now IRRELEVANT to this gate (it was never needed to close it).
3. **"A silent INCLUDE arm means the endpoint was silent"** — REFUTED by my own run 1. The endpoint
   was carrying audio; the corroboration instrument was pointed at the wrong endpoint, in a gap.
   Fixed by the concurrent, timestamped endpoint meter.
4. **The per-session `IAudioMeterInformation` as an attribution instrument on this box** — REFUTED
   (measured earlier, 303 census passes: every session on an endpoint returns the identical peak;
   Discord / nvcontainer / python all 0.263306 at 17:17). Session enumeration gives PIDs and states;
   it does NOT attribute loudness. Attribution comes from the tap.
5. **"The tap might be capturing the endpoint mix instead of the target"** — REFUTED. NEG-A read
   exactly 0.0 while the endpoint carried 0.399834 (ARM 1b) and while the default endpoint meter
   read 0.994824 (ARM 2). A mix-capture could not read zero in those windows.
6. **The "wrapped" PROPVARIANT blob layout** — REFUTED as the working layout (`0x80070057`);
   `direct` (cbSize 12) is the one this build accepts.
7. **`GetMixFormat` on an application-loopback client** — REFUTED as a usable path
   (`0x80004001 E_NOTIMPL`). The format must be declared.

---

## 6. WHAT REMAINS UNMEASURED / OPEN (no claim is made)

* **Sample-exactness.** The tap's waveform was compared to the endpoint's by peak and rms inside
  the same window, NOT sample-by-sample. Whether the captured stream is bit-identical to the
  endpoint's own loopback is UNMEASURED.
* **DRM / protected audio** (e.g. protected media paths) — never tested; a protected target may be
  excluded by the OS. UNMEASURED.
* **UWP / AppContainer / system sounds (audiosrv) targets** — UNMEASURED.
* **Targets rendering to more than one endpoint at once**, and **exclusive-mode** targets —
  UNMEASURED.
* **A target that starts or stops rendering mid-window** — the audio bursts were observed
  (the meter's 1.0 / 0.02 alternation) but the arms do not gate on it. UNMEASURED as a contract.
* **CPU/RAM cost and worker integration** of a `ProcessLoopbackTap` in `worker/sotto_worker.py`
  (chunking, resampling to the model's 16 kHz, device-ladder interaction) — UNMEASURED; this gate
  measured the API, not the product integration.
* **NEG-B deviation**: this build ACCEPTS `TargetProcessId=0xFFFFFFFE`. The instrument's
  discriminating power therefore rests on NEG-A alone (measured exactly 0.0). Not a defect of the
  tap; a disclosed weakness of the pid-validation control.
* **The 0.035214 EXCLUDE reading in ARM 1b and the 8e-05 in ARM 2** are attributed to other
  processes' audio / residual, NOT measured as such (no tone detector was run on the arms' own
  buffers for EXCLUDE). Stated as unattributed low-level audio, which is exactly why the INCLUDE
  result rests on the tone gate and on NEG-A.
* **Audibility side effect (disclosed)**: ARM 1b injected a 440 Hz tone into CABLE Input for 37 s.
  The owner's default output is VoiceMeeter Input, so this was not audible to him by routing. Whether
  that tone entered ANY capture path of the owner's is NOT MEASURED: the session census at 17:17 listed
  `python.exe` pid 37196 with an INACTIVE render session on VoiceMeeter Input, and no instrument in
  this lane established whether that process was alive-and-capturing during those 37 s. The earlier
  wording of this bullet asserted that it was — an assertion this lane never backed with a
  measurement, withdrawn here. Nothing of the owner's was launched, killed or reconfigured.
* **Owner's standing order of 2026-10-11 honoured (no Sotto launch)**: no Sotto shell
  (`sotto_webview.py`), no `run.cmd`, no worker, and no shell-opening probe
  (`_main\_audit-verify-all.cmd` included) was launched by this lane at any point; H:\sotto stayed
  read-only. Every process this lane started was its own instrument under I:\cc-tmp, hidden
  (`CREATE_NO_WINDOW`) and stopped by its own stop file.

---

## 7. Reproduction (exact commands, in order)

    python I:\cc-tmp\audio-sessions.py --all
    python H:\sotto\_main\listen-probe.py 6
    python I:\cc-tmp\gate-arm1b.py --mode arm1b --seconds 4 --cross-check 30 --json I:\cc-tmp\gate-arm1b.json
    python I:\cc-tmp\gate-arm1b.py --mode arm2 --target-pid 19524 --needle "voicemeeter output" --seconds 4 --cross-check 20 --json I:\cc-tmp\gate-arm2-discord.json
    python I:\cc-tmp\arm2-metered.py 19524 --tag arm2-discord-metered --needle "voicemeeter output"
    python I:\cc-tmp\endpoint-meter.py 6 --hz 20 --json I:\cc-tmp\endpoint-meter-now.json

Instrument defect, disclosed: `gate-arm1b.py` writes the probe JSON to a FIXED path
(`gate-arm1b-probe.json`), so the ARM 2 run overwrote the ARM 1b probe JSON. The ARM 1b results
survive verbatim inside `gate-arm1b.json` (`probe_json`) and in `gate-arm1b-run.log`; every ARM 1b
number in section 3 was read from there.

---

## 8. LEDGER (size in bytes, sha256 over those bytes)

| bytes | sha256 | artefact |
|---|---|---|
| 15032 | 7329e66354b2e93b6d68a9d39abb0aecacbe9873af2494deaa0013d42307fffc | I:\cc-tmp\per-app-tap-gate-findings-arm1b.md (predecessor receipt, read in full) |
| 74889 | ca97269ba28f25831e5120f7674b127b002cfe7af9effe7542deb2379624115a | H:\sotto\_main\process-loopback-probe.py (ORIGINAL, untouched — hash unchanged from the receipt) |
| 3290 | 9cbf9901484c576eec796397b23bf3d25916d40a6e3b6e6d4c57d6a7d99802a8 | H:\sotto\_main\listen-probe.py (untouched) |
| 94768 | 4cbde21474d5c4a58c045825b5eae5c6b75c1320370ad70d8e77dae826ee282b | I:\cc-tmp\plp-target.py (the probe COPY, modified: --target-pid, tone gate, cross-check, NEG-A) |
| 4289 | ad9e841ed0a15f2771093915c2a2a8a4c9a56b49301a68d35d137fd514f709a6 | I:\cc-tmp\tone-cross-check.py (independent endpoint tone instrument) |
| 11673 | 00022d6da2933390fc1044e42286263b588cb8dc6fab1f39d64e4a1c92597a44 | I:\cc-tmp\gate-arm1b.py (orchestrator: baseline → renderer → control → arms → stop) |
| 6106 | 722910bb7ab9286455cd54ca39736b597f607266ea9857cd8411792521e8dca1 | I:\cc-tmp\endpoint-meter.py (IAudioMeterInformation sampler, 20 Hz, timestamped) |
| 3024 | 484e054f79934a6b25f52ecf66f7e1f3827eae6359ff1e6a85423d858d04e5a7 | I:\cc-tmp\arm2-metered.py (tap + meter concurrently, epoch-aligned) |
| 1880 | 20ada5eb2179fde187917c0a130576044bdfb3f0ef0c6f805b80fa3aad27acad | I:\cc-tmp\arm1b-cross2-render.py (separate-process MME tone renderer) |
| 2466 | b6b122069a2c1890e30a50bb8e8423cb2b52377a70986d477e13ad2a5c309533 | I:\cc-tmp\arm1b-cross-check.py |
| 6313 | 473e2a34c4c4b1eb139a3003ab3614bebf3c423422ec7b4fa1d92cd755e08b61 | I:\cc-tmp\audio-sessions.py (session census: pid + state + meter) |
| 13428 | fffcf63d73c4fb2125277ccec26c71270135678ce46670b141f62edebcceb77e | I:\cc-tmp\gate-arm1b-run.log (ARM 1b full log) |
| 12198 | 80d4e98c44cdbaa5dda3668a1a8e23653d9d4c58f0719f9385a414b0139582ed | I:\cc-tmp\gate-arm1b.json (ARM 1b structured results incl. the preserved probe_json) |
| 7523 | 435267b523edb939569255bc90bcd20c62a9b2d9d4341164ebc05ebe016427f7 | I:\cc-tmp\gate-arm1b-probe.json (OVERWRITTEN by ARM 2 run 1 — see the disclosed defect) |
| 12267 | 4b771c98cd3cc19c4c3db37e69d6bd00f13ce020a8a8b10cb7284ad0ca62bc59 | I:\cc-tmp\gate-arm2-discord.log (ARM 2 run 1 log, refused) |
| 11176 | 0dfe96381015f10ac8896a59f78000a35098aba3de61543bb9e5b3094140135f | I:\cc-tmp\gate-arm2-discord.json (ARM 2 run 1 structured, refused exit 5) |
| 9880 | a29f4becc9fb7808ea704ad2dbdb6d1dd0d75342a89049dc4312798175fa1be4 | I:\cc-tmp\arm2-metered-run.log (ARM 2 run 2 log, GREEN exit 0) |
| 7538 | 816b7cb7ccd116bd670206ad95d0bb7b863e29879452fd1fdb523ae741826a1d | I:\cc-tmp\arm2-discord-metered-probe.json (ARM 2 run 2 structured) |
| 241933 | db9c7aca55d2e8341948f0927a841f9bebbac6548d1946574fd769236e45c43a | I:\cc-tmp\endpoint-meter-arm2-discord-metered.json (20 Hz meter series, epoch timestamps) |
| 7312 | 5dfb3ebb023a856c32399fa175acd5c80219f203997213e7680b109841872b60 | I:\cc-tmp\endpoint-meter-arm2-discord-metered.log |
| 35324 | 066512c6d1cf0b060b2df10ad19daf4683528c3fa725ddfa377549442b888f07 | I:\cc-tmp\endpoint-meter-now.json (17:21 standalone meter sample) |
| 1880 | c405814443558c755fcc5ade3660a28b520a21f5f795097ce2d0c601285c1e68 | I:\cc-tmp\listen-baseline.log (100 s passive listen, 17:0x) |
| 480966 | a24b1d755fda21b8c448f7252c570c5bb869a380b94a18c0ca121e843a73f9b3 | I:\cc-tmp\session-monitor.log (303 session-census passes) |

This file's own size and sha256 are reported in the reply, not embedded here (embedding them would
change them).
