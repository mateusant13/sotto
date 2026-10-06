# Sotto — planning foundation

Real-time transcription of everything the computer says, docked to the right
edge of the screen. Press <kbd>Alt</kbd>+<kbd>C</kbd>.

## What exists today

Planning only. No application code has been written. What is here:

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

`nvidia/nemotron-3.5-asr-streaming-0.6b` and `moondream/parakeet-redux` were both
confirmed to exist against the Hugging Face API on 2026-10-05, along with
`transcribe.cpp` as the C++ runtime that loads both without a resident Python.
Sizes, licences and terms are in the README, and the licence question is
treated as a gate rather than a footnote: this repository is public from the
first commit, so a licence nobody has read is a shipping blocker.

See `docs/roadmap.md` for what is verified and what is not.