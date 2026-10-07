# Sotto receipt — the test stimulus was AUDIBLE to the owner; default moved off his speakers + a refusal added

Owner, verbatim (2026-10-07): "ouvi um som de parece que de chamada. nao gostei. se e necessario,
nao faz EU ouvir. nao quero ouvir"

## Root cause (measured, not inferred)
`_main/inject-all-probe.py:27` defaulted its RENDER endpoint to `"VoiceMeeter Input"`. AGENTS.md
itself records that `VoiceMeeter Input` IS this box's **system default output** (line 44-45), i.e. the
owner's speakers — and the tone was rendered at `AMP = 0.5` (half scale, 440 Hz, 8 s).
Every OTHER stimulus script here already targets the cable: `device-silence-oracle.py:42`,
`run-live-routed.py:44`, `_join-play.py:18`, `audio-escopo-capture-inputs.py`, `_ordem-arm.py`.
This one file was the outlier, and it was the audible one.

## Change 1 — default render moved to the cable
`RENDER = sys.argv[2] if len(sys.argv) > 2 else "CABLE Input"` (was `"VoiceMeeter Input"`).
`CABLE Input` is a RENDER endpoint whose audio emerges at `CABLE Output`, a CAPTURE endpoint, so the
worker hears it and the speakers are not the intended sink.
`AMP` also became argv[4] (default still 0.5) so a caller can dial it without editing the file.

## Change 2 — a hard REFUSAL, so it cannot be audible by accident again
If the resolved device IS the system default output, the probe now prints
`{"refused":"AUDIBLE-DEVICE", ...}` and returns 4 WITHOUT PLAYING, unless `SOTTO_ALLOW_AUDIBLE=1`
is set explicitly in the environment. The refusal is the guarantee; the default is only the convenience.

## Measured before/after (sha256)
* inject-all-probe.py  817b10b505ecfe9b  -> 3ce5d6b222f26d59 (default moved)  -> 584327776890eee1 (refusal added), 6025 B
* `py -3 -m py_compile _main/inject-all-probe.py` -> rc=0 (at both steps)

## THE NUMBER THAT FORBIDS CLAIMING SILENCE — read this before closing the pendency
probe output, render = CABLE Input:
| amp | CABLE Output | VoiceMeeter Output | webcam mic (C920) |
|---|---|---|---|
| 0.5  | 0.499939 | 0.000118 | 0.735515 |
| 0.01 | 0.010040 | 0.000118 | 0.770061 |
| 0.02 | 0.020020 | 0.000118 | 0.237803 |

* On the cable the amplitude scales 1:1 (0.5 -> 0.01004 at 1%). It is a digital path, so **1% keeps the
  signal intact** — the owner's "se 1% ainda transcreve igual" is answered on the SIGNAL side.
* `VoiceMeeter Output` reads digital silence (0.000118) at every amplitude.
* **BUT the room microphone read 0.24-0.77 in every run, including the cable runs.** Real acoustic
  sound reached the room. So the cable IS reaching a physical output on this box (VoiceMeeter patch),
  and this receipt therefore does NOT claim the stimulus is inaudible to the owner.

## What is NOT proven, and who owns it
1. That the cable path is inaudible to the owner — NOT proven; the microphone contradicts it.
   Owner: a routing change in VoiceMeeter / Windows Sound (stop monitoring CABLE to the speakers).
   AGENTS.md already names this as the owner's fix.
2. UNTESTED CANDIDATE, deliberately not tested because testing it plays sound: there is a SECOND,
   separate virtual device — `CABLE Output (VB-Audio Point)` (sd index 39) — distinct from
   `VB-Audio Virtual Cable`. If Point is not patched to the speakers it is the silent path.
   One guarded run answers it; it needs the owner's word first.

## Standing rule
dono-pendencias.jsonl id `DONO-20261007-sotto-nunca-audivel`, state OPEN — and it stays OPEN until item 1
or item 2 above is measured, because an assertion is not a proof.

## Revert
`git checkout -- _main/inject-all-probe.py` (the file is tracked; verify with `git status` first).