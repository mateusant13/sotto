# Sotto

Real-time transcription of everything your computer says, docked to the right
edge of the screen. Press <kbd>Alt</kbd>+<kbd>C</kbd>.

Sotto listens to **system audio**, not just the microphone. It writes a live
caption into an overlay while you play, call, or stream, and turns the result
into a searchable archive organised by day, then by hour.

---

## What is verified and what is not

Everything in this section was measured against the Hugging Face API on
2026-10-05, not taken from a description. Numbers are downloads and likes at
that instant.

| component | repo | status | notes |
|---|---|---|---|
| streaming ASR | `nvidia/nemotron-3.5-asr-streaming-0.6b` | **verified** | 1,272,450 downloads ┬À 1,169 likes ┬À `nemo` ┬À cache-aware ┬À 35 locales incl. `pt` ┬À `license:other` |
| batch ASR | `moondream/parakeet-redux` | **verified** | 10,187 downloads ┬À 231 likes ┬À `ternary` ┬À `1.58-bit` ┬À 25 languages incl. `pt` ┬À **CC-BY-4.0** |
| inference runtime | `transcribe.cpp` | **verified** | runs **both** models as GGUF ┬À `tq1_g128` ternary ┬À the Nemotron GGUF has **1,835,919 downloads** |

`transcribe.cpp` is the answer to "what engine runs Parakeet Redux". It is a
C++ runtime, which is what makes the no-resident-Python constraint reachable
from a Tauri/Rust process. The Nemotron checkpoint's native format is
PyTorch/NeMo, so without this runtime the heaviest component would have
dragged a Python environment into the app.

Alternative paths that exist and are not yet chosen: ONNX
(`eschmidbauer/parakeet-redux-onnx`, `soniqo/Nemotron-ÔÇª-ONNX-FP16`), CoreML for
Apple silicon, and `sherpa-onnx`.

Not yet verified: diarization model, embedding model, the small LLM, sqlite-vec
version, and whether any of them have a C++ path as clean as `transcribe.cpp`.

---

## Licence posture

`parakeet-redux` is **CC-BY-4.0** and attribution is required.
`nemotron-3.5-asr-streaming-0.6b` is `license:other` and must be read before
this ships. A public repository cannot ship under a licence whose terms have
not been read. That reading is the first gate on the roadmap, not a footnote.

---

## Stack

- **Shell** ÔÇö Tauri 2, Rust, Svelte 5 + TypeScript. No Electron.
- **Capture** ÔÇö CPAL, WASAPI loopback on Windows. Loopback, not microphone: the
  product is "any audio on the PC".
- **Hotkey** ÔÇö Tauri global shortcut, `Alt+C`.
- **ASR** ÔÇö Nemotron 3.5 streaming while recording; Parakeet Redux for the
  canonical transcript afterwards.
- **Diarization** ÔÇö TBD, needs a non-Python path.
- **Search** ÔÇö SQLite + FTS5 + sqlite-vec, so lexical and semantic search share
  one database and one file.
- **Idle policy** ÔÇö every model worker is on demand. With no audio, nothing is
  resident but the shell and the database.

## Status

Planning. See `docs/roadmap.md`.
