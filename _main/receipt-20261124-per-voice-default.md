# Receipt -- per-voice captions ON BY DEFAULT (2026-11-24)

Owner order, verbatim: *"sotto é pra conseguir distinguir cada voz/camada de audio e saber
transcrever corretamente cada uma em paralelo. faz isso de algum jeito usando o que o discord
proporciona ou entao com modelo que separa vozes. vai"*, and, when asked for a bot token,
*"tu nao precisa de nada disso ai. faz direito."*

## What was actually broken (four defects, in the order they kill the feature)

1. **The sidecar never started at all.** `_load_sherpa_diarizer` demanded
   `create_gpu_only_offline_speaker_diarizer`, which sherpa-onnx 1.13.4 does not expose for
   `OfflineSpeakerDiarization`. Every start ended in
   `RuntimeError: speaker GPU-only policy cannot be proven: installed sherpa-onnx has no strict
   diarization adapter ...`. A feature that cannot start is dead, not slow.
2. **`--speakers` was opt-in.** The owner opens the app by double-click; a capability behind a flag
   he never types does not exist.
3. **The two halves tapped different endpoints.** `_open_endpoint` read `spec["default"]` while
   `loopback_device_specs()` writes `is_default`, so the default branch never matched and the picker
   fell back to the rank, which is `VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)`. MEASURED in the
   live join: the sidecar reported `fala 3-9 %` on a window where the worker transcribed speech.
4. **A sparse window was thrown away instead of being made dense.** MEASURED in the live join: his
   speech occupies 2-8 % of a 20 s window, the 30 % gate declined almost every tick, and 7 real
   captions came out with `speaker: null`.

## What changed

| file | change |
|---|---|
| `worker/speaker_sidecar.py` | `DIARIZER_PROVIDER = "cpu"` (explicit, measured); `_open_endpoint` honours `is_default` then `wasapi_loopback.default_render_endpoint()`; `speech_span()` returns the voiced span; `tick` crops to it (`SPARSE_PAD_S=0.5`, `MIN_TRIMMED_S=1.2`) and declines **without calling the model** when there is no speech; the diarize log line prints the real provider |
| `app/webview/sotto_webview.py` | `--speakers` default ON, `--no-speakers` opts out |
| `worker/speaker_bridge.py` | a payload stamped `"fake": true` is refused by name, not by age |
| `_main/speaker-sidecar-oracle.py` | +8 arms: endpoint picker (3), sparse trim + absolute offset (3), decline-without-inference (2) |
| `_main/sidecar-wiring-oracle.py` | +2 arms: `--speakers` default True read from the AST, `--no-speakers` present |
| `_main/speakers-live-join.py` | the join instrument: sidecar + worker, `CREATE_NO_WINDOW`, bounded life, verifies identity before stopping |

The GPU-only guard is untouched: a `cuda` request is still refused, because sherpa cannot attest
placement there. What changed is that CPU is *asked for by name* -- no accelerator to fall back from,
and the measured path (DER 0.03 %, RTF 0.416, 277 MB, 0.9 s load at 2 threads, `_main/_diar-run.py`).

## Evidence

- `_main/speaker-sidecar-oracle.py` -- `VERDICT: PASS arms 95/95 mutants 8/8`.
- `_main/sidecar-wiring-oracle.py` -- `arms 26/26`, neg-arm `CAIU` (BELOW_NORMAL mutant caught).
- Real audio, real model, real `tick`: `_main/_sidecar-replay-real.py` on 60 s of the owner's
  Discord call (`_main/bench/windows/w60-t0360.wav`) → **2 slots for 2 people, 6 windows, 0 empty**,
  `DIARIZER_PLACEMENT provider=cpu`, 94.4 s CPU. The trim did not change this (dense windows are
  not trimmed).
- Real payload → real caption lines: the payload written by that replay, read through
  `speaker_bridge.payload_if_fresh` + `apply_to_lines`, stamped `device:test/voice:speaker-1` on the
  line inside the segment and left the line 30 s outside it unattributed.
- **The live join, which had never passed**: `_main/speakers-live-join.py --seconds 110` under the
  40 % cage → `PASS ... real payload (2 segments, speaker(s) [3, 5]) and 6/6 captions attributed
  (speaker-1)`, `speech_fraction 0.0551` on the published window. That 5.5 % window is exactly the
  one the old 30 % gate refused; the crop is what turned it into a published, named voice. Before
  the crop the same instrument reported `7 captions, 0 attributed`.
- `_main/agents-md-pins-oracle.py` -- PASS (the `run.cmd --help` pin re-measured after `--no-speakers`
  appeared in the help: 9380 B, 144 lines, 144 CRLF, sha256 `C949E51C...`).
- `_main/owner-screen-gate.py` -- PASS, 0 findings. My own instrument had to gain
  `-WindowStyle Hidden` on its `powershell` identity probe; the gate caught it.
- `_main/console-window-audit.py` -- PASS, 0 sites.
- `_main/_make-gitattributes.py --verify` -- PASS.

## UNMEASURED, and named

- **The panel painting N live coloured voices from the owner's own call.** Launching the shell on his
  screen is forbidden (`SOTTO_NEVER_ON_OWNER_SCREEN`), and he must restart it himself to load this
  code (`UNMEASURED` until then, per the "cure in the file is not the cure in the process" rule).
- **Overlapping speech.** Diarization assigns a span to the dominant voice; neither the diarizer nor
  the ASR splits two people talking over each other. The separator route stays refuted
  (MossFormer2_SS_16K: 1335.1 s for 60 s, RTF 22.25).
- **Slot identity across a long call** (does speaker-1 stay the same person for an hour). The horizon
  is unit-tested, not lived.
