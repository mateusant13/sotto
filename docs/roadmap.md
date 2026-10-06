# Sotto — roadmap

Written 2026-10-05. Every claim in here is either measured or marked
UNVERIFIED. A milestone that cannot be proved by a command does not close.

---

## The thing the source brief got wrong

The brief describes a mic-to-caption pipeline:

```
microfone -> CPAL -> PCM 16 kHz -> speech
```

**That is not the product.** The product is *"transcription of any audio on
the PC"*. On Windows that means **WASAPI loopback** — capturing the render
endpoint, so a Zoom call, a YouTube video, a game, a music player, all land in
the same stream without routing any of them to a virtual device.

This changes the stack:

- CPAL alone is **not sufficient**. It can open a loopback stream on Windows,
  but the device-selection and format-negotiation behaviour needs to be
  measured before it is trusted.
- A microphone stream and a loopback stream have **different lifetimes**. A mic
  is always present; a render endpoint can be muted, reconfigured, or
  replaced by a headset being plugged in mid-session.
- **No audio is a normal state, not an error.** The app must sit at near-zero
  cost when the endpoint is silent, and must not spin a model on silence.

So milestone M1 is "prove loopback capture", not "capture audio".

## The idle contract

This is the requirement most likely to be quietly violated, because violating
it is invisible: nothing breaks, the app just got fat.

| state | resident |
|---|---|
| idle, no audio | shell + SQLite, nothing else |
| recording | Nemotron streaming + capture |
| recording, speakers resolved | the above + diarization, off the caption path |
| after stop | Parakeet + diarization + title/summary, then **all unloaded** |
| searching | embedding model, only while indexing |

Each row needs a **measurement**, not an assertion: resident RSS and commit,
sampled. The claim "it unloads" is proved by the number dropping, not by the
code path existing.

## Milestones

**M0 — Foundation.** Tauri 2 + Rust + Svelte. Dark theme, empty overlay docked
right, `Alt+C` toggles it, no model, no audio. Proves the shell, the hotkey,
the window behaviour, and the idle baseline. Exit: the app opens, toggles, and
a sampled idle RSS number exists.

**M1 — Loopback capture.** WASAPI render-endpoint capture through CPAL, PCM to
a sink, written to a file. No ASR. Proves that system audio actually arrives,
and that silence is distinguishable from a dead stream. Exit: a known sample
plays, the captured file is non-empty and matches, and a silent period produces
zero non-zero samples.

**M2 — First transcription.** Parakeet Redux through `transcribe.cpp` over an
M1 file. Batch, not streaming. Exit: real words out of the sample, with the
model's actual resident cost measured. This is the earliest point where the
CC-BY-4.0 attribution obligation bites.

**M3 — Streaming captions.** Nemotron 3.5 streaming into the overlay.
Exit: a partial hypothesis appears within a stated latency budget, measured.

**M4 — Store and search.** SQLite schema, day→hour organisation, FTS5 lexical
search. Exit: a query finds a phrase that was actually spoken.

**M5 — Semantic search.** Embeddings + sqlite-vec. Exit: a query with no shared
keywords still finds the segment, and a query with shared keywords still works.

**M6 — Panel complete.** Day/hour navigation, "show in folder", the disk-usage
button split into models and transcripts. Exit: the button's number is
computed from the filesystem, not from a cache.

## Risk register

| risk | severity | what would settle it |
|---|---|---|
| Nemotron `license:other` forbids this use, or requires terms we cannot meet | **fatal** | reading the licence. First gate, before M2 |
| Loopback capture behaves differently per audio endpoint | high | M1 across three endpoint types |
| `transcribe.cpp` has no stable embedding API we can call from Rust | high | a hello-world binding, before M2 |
| Diarization has no C++ path and drags Python back in | medium | find the native export, or cut diarization from v1 |
| Two ASR models is one too many for a first release | medium | M2's measurements decide |
| Idle contract erodes as features land | **silent** | a sampled RSS test in CI, not a code review |

## How these specs get approved

This roadmap is my own proposal, so it does not get to approve itself. The
protocol, applied to every milestone before it starts:

1. **Pass one — attack.** A reviewer whose only job is to refute the milestone.
   It must name a concrete way the milestone's exit condition can be satisfied
   while the product is broken. A missed objection is a defect in the pass.
2. **Pass two — respond.** Rewrite the milestone to survive the objection, and
   record the objection and the change side by side.
3. **A milestone whose exit condition cannot be made falsifiable does not
   open.**

The first milestone to go through this is M1, because the loopback assumption
is the one thing in this document that has not been measured at all.

## Open questions being answered by measurement, not by asking

- Does CPAL's WASAPI loopback negotiate a format we can use directly, or does
  it hand us something we must resample?
- What is Parakeet Redux's real resident cost through `transcribe.cpp` on this
  machine, with the app idle?
- Is there a diarization model with a C++ or ONNX path that does not need
  PyTorch resident?
- Which embedding model has the smallest honest footprint here, given that
  embeddings must not be resident during recording?