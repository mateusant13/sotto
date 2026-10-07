# SPEC 05 — CLIP TO ASR: THE CONTRACT FROM A FILE ON DISK TO A ROW IN THE INDEX

Status: **DRAFT — stub committed first (abort-safety), being deepened now.**

Scope: only the path from "a clip file exists" to "a transcript is in the index". Capture is
`specs/01`, the encode/mux step is `specs/03`, the ASR engine itself is `specs/02`, the index is
`specs/04`.

Number policy: every constant carries a `file:line`. Anything not verified on this box is written
**UNKNOWN — not measured**.

## 1. THE AUDIO FORMAT CONTRACT

From `src/capture/audio_contract.h`:

| property | value | provenance |
|---|---|---|
| sample rate | 16 000 Hz | `src/asr/constants.py:91` |
| channels | 1 (mono) | `src/asr/audio.py:57-58` |
| sample width | 2 bytes, PCM16 | `src/asr/audio.py:54-55` |

(Full text pending.)