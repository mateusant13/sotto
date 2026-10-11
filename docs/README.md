# Sotto — planning foundation

Real-time transcription of everything the computer says, docked to the right
edge of the screen. Press <kbd>Alt</kbd>+<kbd>C</kbd>.

## What exists today

**A working application, not a plan** (re-measured 2026-10-11): the transcriber
(`worker/sotto_worker.py`), the shell (`app/webview/sotto_webview.py`, pywebview 6.2.1 + WebView2) and the
panel (`app/panel/*`) all exist and run, and `Alt+C` toggles the overlay. (`docs/roadmap.md`'s milestone
plan is marked SUPERSEDED there.) This paragraph said *"Planning only. No application code has been
written."* until 2026-10-11: it was TRUE when this file was written and was left stale for days.
Corrected rather than deleted, so the record of what this directory was for survives.

What is in THIS directory:

- `brand/logo.svg` — the mark, and the two accent colours the UI uses.
- `docs/roadmap.md` — milestones M0..M6, the idle contract, the risk register,
  and the protocol these specs have to survive before they are allowed to open.
- `README.md` — what is verified about the model stack, with the numbers.

## The one thing to know first

The source brief describes a microphone-to-caption pipeline. **That is not the
product.** Sotto transcribes *any audio on the PC*, which on Windows means
**WASAPI loopback** on the render endpoint — no virtual device, no manual
routing. That, and the promise that an idle Sotto costs almost nothing, are the
two constraints the architecture exists to satisfy.

## Honest status of the stack

**What SHIPS (re-measured 2026-10-11):** the transcriber is a **Python 3.11** worker
(`worker/sotto_worker.py`) that runs the models through **`onnxruntime`** and prints JSONL captions; the
shell is **Python + pywebview 6.2.1 / WebView2** (`app/webview/sotto_webview.py`) serving `app/panel/*`
unmodified; **`Alt+C`** is the only control. There is **no Rust, no Tauri and no `transcribe.cpp`** in
the live path: `transcribe.cpp` was evaluated as a C++ runtime and **not adopted**, and the
Tauri/Rust/CPAL plan is marked SUPERSEDED in `docs/roadmap.md`. (This paragraph used to present
`transcribe.cpp` as "the C++ runtime that loads both without a resident Python" -- that was the PLAN,
read as the product; corrected 2026-10-11.)

`nvidia/nemotron-3.5-asr-streaming-0.6b` and `moondream/parakeet-redux` were both
confirmed to exist against the Hugging Face API on 2026-10-05.
Sizes, licences and terms are in the README, and the licence question is
treated as a gate rather than a footnote: this repository is public from the
first commit, so a licence nobody has read is a shipping blocker.

See `docs/roadmap.md` for what is verified and what is not.