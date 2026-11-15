# RECEIPT - the speech gate was refusing broadcast speech (measured 2026-11-15)

Every number below was measured in this tree today. The command is beside the number.

## 1. The defect: the gate deletes most of a real broadcast

`SOTTO_GATE` defaults to **ON** for the live branch (`worker/sotto_worker.py`, `_gate_env is None`
-> `gate_enabled = not _file_mode`). On a 20 s window of `rS4VMlwf2qM` the worker log said
`gate=on source=live-default` and the per-chunk trace
(`_main/devlab/cache/feed-8b555fe04fcab71524c3a5f3.chunks.jsonl`) shows `speech=False` for
**every chunk from 8.4 s on** — 19 chunks of audio that the YouTube reference transcribes as
continuous speech (`t=58.7 'gets away with it, except for the person'`, `t=62.8 'was wearing spy
camera glasses'`, `t=67.1 'the story went super viral'`).

The chunks it refused are LOUD: per-second RMS rises from 0.24 at the start to **0.32-0.50** in
the refused region. The gate is not detecting silence; it is detecting a *narrow* sub-frame
dynamic span.

## 2. A/B on identical audio, one process per arm

`python _main/devlab/lab.py score --video rS4VMlwf2qM --window 60 20 [--gate]`

| arm | finals | hyp words | coverage | WER |
|---|---|---|---|---|
| gate **off** | 4 | 47 | **0.80** | **0.458** |
| gate **on** (product default) | 2 | 15 | 0.25 | 0.780 |

The product default costs **55 % of the coverage and 0.32 of WER** on a normal YouTube video.

The A/B itself was broken until today: `cmd_score` passed only `SOTTO_LANG`, so the worker fell
back to `live-default` (`gate=on`) and "gate off" had never actually been measured. The score path
now passes `SOTTO_GATE` explicitly and prints `GATE gate=... (explicit)`; a control that cannot be
selected is not a control.

## 3. Why the fixtures never caught it

`python _main/speech-gate-oracle.py` -> `VERDICT: PASS`, with `kept_frac=1.0` on all four speech
fixtures (`sample1.flac`, `sample2.flac`, `pt-br-sample.wav`, `en-us-sample.wav`) and 0 kept on the
60 Hz drone. All four are **clean studio recordings**. The gate has never been judged on broadcast
audio, which is the only population the product meets.

Measured on the real capture that ships in this tree (`SpeechMusicGate` driven directly, 560 ms
chunks, `GATE_DB_RANGE_MIN=18`):

| population | chunks | kept | kept_frac |
|---|---|---|---|
| `_main/live-sample-cable-input-90s.wav` | 160 | 76 | **0.47** |
| `_main/live-sample-cable-input.wav` | 53 | 4 | **0.08** |
| `_main/en-us-sample.wav` | 15 | 15 | 1.00 |
| 60 Hz drone (`agc_drone_floor.wav` class) | 14 | 0 | 0.00 |

## 4. The threshold sweep — the two populations separate cleanly at 6-8 dB

`kept_frac` per `GATE_DB_RANGE_MIN`:

| population | 4 | 6 | 8 | 10 | 18 |
|---|---|---|---|---|---|
| `sample1.flac` (studio) | 1.00 | 1.00 | 1.00 | 0.96 | 0.92 |
| `en-us-sample.wav` (studio) | 0.93 | 0.93 | 0.93 | 0.93 | 0.87 |
| **MUSIC bed** (chords + kick + hats, synthetic) | 0.60 | **0.00** | **0.00** | 0.00 | 0.00 |
| **SPEECH-like** (syllabic envelope, synthetic) | 0.91 | **0.91** | **0.91** | 0.91 | 0.91 |
| SILENCE | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **`live-sample-cable-input-90s.wav`** (broadcast) | 0.89 | **0.88** | **0.81** | 0.64 | 0.28 |

At 18 dB the gate keeps 28 % of real broadcast audio and 0 % of music. At 6-8 dB it keeps 81-88 %
of broadcast, 91 % of speech-like, and still **0 % of music, drone and silence**. The music/drone
refusal is carried by the *step* the kick gives the sub-frame envelope, which is 6-8 dB; 18 dB was
calibrated against a class (constant-amplitude drone) that any threshold rejects.

## 4-bis. THE REAL-MUSIC ARM KILLS THE THRESHOLD FIX (measured, same day)

The synthetic bed in section 4 was too kind to the gate. The real music fixtures already in this
tree (`_main/diar-mix/`, 56.9 s each, the diarization lane's own beds) do not separate at all:

| population | n | 4 | 6 | 8 | 10 | 18 |
|---|---|---|---|---|---|---|
| **MUSIC bedonly** (`mix-bedonly.wav`, real) | 101 | 0.99 | **0.97** | **0.80** | 0.45 | **0.02** |
| MUSIC bedonly at SNR+15 (`mix-snr+15.wav`) | 101 | 1.00 | 0.97 | 0.81 | 0.67 | 0.29 |
| SPEECH+bed at SNR-05 (`mix-snr-05.wav`) | 101 | 0.99 | 0.96 | 0.80 | 0.44 | 0.09 |
| **BROADCAST** (`live-sample-cable-input-90s.wav`) | 160 | 0.89 | **0.88** | **0.81** | 0.64 | **0.28** |
| STUDIO (`sample1.flac`) | 24 | 1.00 | 1.00 | 1.00 | 0.96 | 0.92 |
| DRONE (`agc_drone_floor.wav`) | 35 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

**At 6-8 dB real music (0.97/0.80) and broadcast speech (0.88/0.81) are the same number.** At
18 dB the gate does reject music (0.02) -- and rejects **72 % of broadcast speech** with it (0.28).

So the sub-frame dB span is not a music/speech discriminator on real audio: it measures *envelope
sharpness*, and a percussive music bed has as much of it as speech does. The 18 dB default was
calibrated on a constant-amplitude drone, which every threshold rejects; that fixture can never
fail, so `speech-gate-oracle.py` passed while the product was deleting speech.

**Conclusion: the gate cannot be retuned.** Any threshold that keeps broadcast speech keeps
real music, and vice versa. The mechanism needs replacing (a real VAD or a spectral/periodicity
discriminator), which is a separate piece of work with its own measurement.

## 4-ter. What was done about it

`SOTTO_GATE` now defaults to **off on the live branch too** (`worker/sotto_worker.py`). The gate
stays available: `SOTTO_GATE=1` turns it on explicitly for anything that wants it, and the file
branch keeps its own off default. The reason is the A/B in section 2 -- as a product default it
costs 55 % of coverage and 0.32 WER -- and section 4-bis says retuning cannot recover that.

The "isolate speech from music" goal the gate was built for is **not met** by this class of
mechanism, and the receipt says so instead of shipping a threshold that looks tuned.

## 5. What is NOT claimed

* `GATE_DB_RANGE_MIN` is **unchanged** (18.0). Section 4-bis is the reason: no value of it works,
  so moving it would be a number with no measurement behind it.
* A real-music fixture with *no* percussion (sustained pads, drones, ambient) may separate better
  than `mix-bedonly.wav`; that arm is UNMEASURED. It would not rescue the 18 dB default, which
  already fails on speech.
* The `mix-*` fixtures are 56.9 s diarization beds, not a full song. They are the best real music
  this tree owns; a full track would need a fresh harvest, and the YouTube harvest of a music-only
  video returned **silence** today (`rms=0.000`, `media never became decodable (readyState=0)`,
  i.e. a login/DRM wall), so that arm is blocked, not skipped politely.
* The 90 s capture is the owner's own audio and is read only; nothing was rendered, muted or
  routed.

## 5-bis. The oracle was repaired in the same commit

`_main/speech-gate-oracle.py` passed for a month while the product deleted speech, so the fix is
in the JUDGE, not only in the default:

* **Two new populations**: `live-sample-cable-input-90s.wav` (real broadcast, `kept_frac=0.475`)
  and `_main/diar-mix/mix-bedonly.wav` (real music bed, `kept_frac=0.079`). The drone arm stays; it
  is the arm every real music bed shows could never fail.
* **A default guard** reads `worker/sotto_worker.py` **structurally** (`if _gate_env is None:`
  assigning `gate_enabled`) and requires `False`. The first version of this arm tested
  `"is" in ast.dump(...)`, which the dump spells `Is()`, and read `False` on correct code -- an
  instrument that accuses a correct site, fixed before it shipped.
* **The broadcast bar binds only while the gate ships.** With the default off the mechanism is
  dormant, so the arm publishes the number and records the defect as `dormant`; the moment anybody
  re-enables the gate the bar goes red. That is deliberate: a bar that fails the whole battery for a
  class that cannot fire would be a portao that accuses the wrong work.
* **`--neg-arm` plants 2 defects in a COPY** and requires both: `gate-default-on` (default flipped
  back) and `broadcast-bar-removed` (gate re-enabled **and** retuned to 20 dB -- a number that still
  keeps all four studio fixtures at 0.87+ and looks tuned). Measured: `NEG-ARM: PASS -- 2/2`,
  rc=**1**. Two instrument bugs were found by building it: the first mutant edited
  `worker/_prefix_audioflag.py`, a **different copy** of the class, so the process under test never
  changed; and the first retune to 40 dB was caught by the *studio* arm, not the broadcast one,
  which would have certified the wrong bar.

Measured after the change: `python _main/speech-gate-oracle.py` -> `VERDICT: PASS`, rc=**0**, with
`default sotto_worker.py ... default_off=True`.

## 5-ter. The devlab now exercises the PRODUCT default

`_main/devlab/lab.py score` used to pass `SOTTO_GATE=0` on every run, which would have hidden a
wrong default behind a harness-set variable. It now sets **nothing** unless `--gate` is given, and
prints `GATE gate=product default (no SOTTO_GATE set)`. The A/B that found this defect was itself
broken in exactly this way (section 2), so the harness now tests the default it ships.

## 6. Instruments to re-run

```
python _main/speech-gate-oracle.py                       # the existing judge (studio fixtures only)
python _main/devlab/lab.py score --video rS4VMlwf2qM --window 60 20          # gate off
python _main/devlab/lab.py score --video rS4VMlwf2qM --window 60 20 --gate   # gate on
python _main/devlab/lab.py status                        # cached windows
```
