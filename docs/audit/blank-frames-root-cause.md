# Blank frames — root cause (lane BlankFramesRootCause, 2026-10-06)

**Ticket:** #618 item 6. **Question:** why does a live run produce `blanks=35 blank_frac=1.0`
and no caption, while the same worker transcribes a file?

**Answer, in one line:** nothing in the worker is broken. The capture is alive and the model
is fine — the **audio in the default render endpoint's mix during every failing run contains
no speech** (a constant low-frequency hum/rumble), and `main()`'s verdict ladder called that
state *`model-emitted-nothing`*, which pointed four separate investigations at the model.

> **Note on code state.** `worker/sotto_worker.py` was edited by another lane *while this
> investigation ran* (an AGC was added at ~:1526, `SOTTO_AGC`, default on). Measurements
> therefore carry the hash they were taken against:
>
> | sha256[:16] of `worker/sotto_worker.py` | what it is | used for |
> |---|---|---|
> | `0bd24c2bb55a2777` | pre-AGC, as found at 08:40 | arms A / A' / C / C' / B, ambient feed, high-pass, speed, mixtures |
> | `1900bc7b1d284ee4` | + **this lane's verdict fix** | fix compile check |
> | `2bab6a7be3e12e5c` | + peer lane's AGC (= current) | arm D (live speech), fix proof |
>
> `worker/wasapi_loopback.py` = `2a2f8021d1e92fef`, unchanged throughout.

---

## 1. The decisive experiment — the two arms

### Arm A — control, known-good input (`SOTTO_AUDIO_FILE=_main/pt-br-sample.wav`, 22050 Hz)

```
pythonw.exe worker/sotto_worker.py --config worker/config.json      # SOTTO_AUDIO_FILE=...\_main\bfrc_a_22050_full.wav
```
stdout (`_main/bfrc_a_22050_full.jsonl`), verbatim:
```
{"type": "status", "state": "selftest-start", "audio_s": 15.192, "chunks": 27}
{"type": "caption", "text": "O rádio", "start": 0.56, "end": 1.12, "model": "nemotron-3.5-asr-streaming-0.6b-int8"}
{"type": "caption", "text": "Segunda-feira", "start": 6.72, "end": 7.28, ...}
{"type": "caption", "text": "Os moradores", "start": 8.96, "end": 9.52, ...}
{"type": "status", "state": "selftest-done", "text": "O rádio Segunda-feira Os moradores", "empty": false, "tokens": 18, "audio_s": 15.12, "frames": 207, "blanks": 189, "blank_frac": 0.913, "empty_chunks": 24, "vad_gated_chunks": 0}
```

### Arm B — the failing case (live capture from the device)

```
pythonw.exe worker/sotto_worker.py --config worker/config.json --stats-interval 10 --max-seconds 25
```
stdout (`_main/bfrc_b_live.jsonl`), verbatim:
```
{"type": "status", "state": "device", "device": "WASAPI loopback: {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}", "rate": 48000, "block": 4800, ...}
{"type": "status", "state": "done", "verdict": "model-emitted-nothing", "blocks": 250, "block_samples": 1200000, "nonzero_blocks": 250, "peak": 0.101929, "resampled_samples": 403200, "chunks": 44, "captions": 0, "tokens": 0, "frames": 77, "blanks": 77, "blank_frac": 1.0, "empty_chunks": 11, "vad_gated_chunks": 33, "audio_s": 24.64}
```
stderr, verbatim:
```
WORKER_STATS tag=final blocks=250 block_samples=1200000 nonzero_blocks=250 peak=0.101929 rms=0.01368419 resampled_samples=403200 chunks=44 captions=0 tokens=0 frames=77 blanks=77 blank_frac=1.0 empty_chunks=11 vad_gated_chunks=33 queue_drops=0 audio_s=24.64 infer_wall_s=1.57 rss_mb=2413.2
```

### The split
`A gives captions, B does not` → **the defect is in the LIVE path (content or resample)**.

---

## 2. Splitting "content or resample" — three more arms, all on the SAME speech

Derived inputs are built by `_main/_bfrc_make_arms.py`; the *only* variables are the sample
rate the worker sees (which selects the resample branch) and the level.

| arm | input | resample branch | caps | raw `selftest-done` |
|---|---|---|---|---|
| A' | `bfrc_a_22050_quiet.wav` — pt-br-sample attenuated to **the measured live level** (peak 0.100494, rms 0.011734) | `np.interp` | **3** | `tokens=18 frames=207 blanks=189 blank_frac=0.913 empty_chunks=24 vad_gated_chunks=0` |
| C | `bfrc_c_48000_full.wav` — same clip upsampled to 48000 | **3:1 block average** | **3** | `tokens=18 frames=207 blanks=189 blank_frac=0.913 empty_chunks=24 vad_gated_chunks=0` |
| C' | `bfrc_c_48000_quiet.wav` — 48000 **and** live level | **3:1 block average** | **3** | `tokens=18 frames=207 blanks=189 blank_frac=0.913 empty_chunks=24 vad_gated_chunks=0` |

All four file arms produce the identical transcript `O rádio Segunda-feira Os moradores`.

- **RESAMPLE FALSIFIED.** `worker/sotto_worker.py:767-781` (`resample_to_16k`) takes the 3:1
  block-average branch at 48 kHz for the live path; arm C/C' feed exactly that branch with
  known speech and it transcribes perfectly.
- **LEVEL FALSIFIED.** Arm A' is at peak 0.1005 / rms 0.0117 — the live mix's level
  (peak 0.100510 / rms 0.01474 per the dispatch, 0.101929 / 0.01368 measured here). It
  transcribes perfectly. The front-end does not need gain for *speech at that level*.
- **THE CHUNK→DECODE→EMIT PATH IS EXONERATED**: same `run_chunk` (`:494-603`) and same emit
  code in all four arms.

---

## 3. The branch landed on: the audio itself

Take the audio the live tap actually delivered, write it to a WAV, and feed it **back through
the known-good FILE path**. Same samples, same model, same chunking — only the live plumbing
is removed.

```
pythonw.exe _main/_bfrc_capture.py 20 _main/bfrc_live_capture.wav          # raw WasapiLoopbackTap -> WAV
SOTTO_AUDIO_FILE='H:\sotto\_main\bfrc_live_capture.wav' pythonw.exe worker/sotto_worker.py --config worker/config.json
```
`_main/bfrc_capfile.jsonl`, verbatim:
```
{"type": "status", "state": "selftest-start", "audio_s": 19.9, "chunks": 35}
{"type": "status", "state": "selftest-done", "text": "", "empty": true, "tokens": 0, "audio_s": 19.6, "frames": 140, "blanks": 140, "blank_frac": 1.0, "empty_chunks": 20, "vad_gated_chunks": 15}
```

**0 captions through the file path.** So the worker's live plumbing (tap → queue → buffer →
resample → chunk) is *not* what loses the audio: **the audio contains nothing the model can
transcribe**, and the model's own VAD agrees (15 of 35 chunks withheld).

### 3.1 The obverse control — the same live tap, with speech in it

Play a known speech clip out of the default output while the real worker captures the default
render endpoint (`_main/_bfrc_play_capture.py`, `_main/_bfrc_armd.py`):

```
# 1) tap fidelity, model-free: capture the played clip and cross-correlate
best lag = 29664 samples (618.0 ms)
capture peak=0.13548 rms=0.020112   played peak=0.11643 rms=0.013559
normalised cross-correlation (lag-aligned) = 0.6609
#    (equal-power played+ambient predicts ~0.71 — the tap carries the real signal)

# 2) that capture fed through the file path
{"type": "caption", "text": "O rádio", ...} {"type": "caption", "text": "Segunda-feira", ...} {"type": "caption", "text": "Os moradores", ...}
{"state": "selftest-done", "text": "O rádio Segunda-feira Os moradores", "empty": false, "tokens": 18, "vad_gated_chunks": 0}

# 3) the SAME thing live, end to end, against the CURRENT worker (AGC on)
{"type": "status", "state": "done", "verdict": "captions-emitted", "peak": 0.183473, "chunks": 32, "vad_gated_chunks": 0, "frames": 259, "blank_frac": 0.8649, "captions": 8}
CAPTIONS(8): 'Nati | Para | Para chegar | O rádio | anunciou que | Segunda-feira | Os | Rádio'
WORKER_STATS tag=final blocks=180 ... peak=0.183473 rms=0.01940694 gain_db=+11.4 ... chunks=32 captions=8 tokens=35 frames=259 blanks=224 blank_frac=0.8649 empty_chunks=24 vad_gated_chunks=0
```

**The entire live path — WASAPI loopback tap, 48k→16k boxcar, AGC, chunking, greedy walk,
emit — produces captions when the endpoint carries speech.** Blank frames are not a defect in
any of those stages.

### 3.2 What the live mix actually is

Everything below is on the *failing* content (`_main/bfrc_live_capture.wav`,
`bfrc_live_capture2.wav`, 48000 Hz, float32, mono):

```
peak=0.09807 rms=0.014684   (08:42)      peak=0.103287 rms=0.013229   (08:47)
frame rms dBFS: p5=-45.9 p50=-36.9 p95=-33.5 max=-31.0     # ~15 dB of range, no pauses
spectral centroid = 739 Hz
band shares: 0-100:18.1% 100-300:18.7% 300-1000:45.5% 1000-3000:14.8% 3000-6000:1.6% 6000-10000:0.9% 10000-16000:0.3%
top spectral peaks (Hz): 294 370 440 247 330 494 554 220 165 588 392 55
peak/median ratio = 54.1 dB
autocorrelation: best lag 773 samples = 62.1 Hz, value 0.339 (weak, quasi-periodic)
```
Speech has substantial 1–4 kHz energy (formants, fricatives); this has **~90 % below 1 kHz
and 0.3–1.3 % above 3 kHz**, is steady for hours, and is *sample-for-sample reproducible*:
`peak=0.103287` appears both in `_main/_arm-live.jsonl` (05:17) and in my capture at 08:47.

**Refutations of the alternatives, each measured:**

| hypothesis | test | result |
|---|---|---|
| silent-flag garbage (`AUDCLNT_BUFFERFLAGS_SILENT`) | `_main/_bfrc_flags.py` read GetBuffer's `flags` for 8 s | `flags=0x0 x798`, `flags=0x1[DISC] x2`, **0 SILENT** → real data |
| idle-endpoint packets | `_main/_bfrc_all_endpoints.py`, all 6 active render endpoints | only the default endpoint returns packets (`n=96000 peak=0.099838`); the other 5 return **n=0** |
| it is a capture artefact | re-capture at 08:54, unmodified worker | loopback packet peak **0.0** — the drone had stopped → it is *content that starts and stops*, not an artefact |
| it is slowed speech | `_main/bfrc_speed{2,4,6,8}.wav` (speed up 2/4/6/8×) through the model | `captions=0` on all four |
| it is LF rumble masking speech | FFT high-pass at 120 Hz (`bfrc_live_highpass.wav`) through the model | `text="" tokens=0 frames=168 blanks=168 blank_frac=1.0 vad_gated_chunks=11` |
| it is a microphone monitor path | `_main/_bfrc_mic.py` — mic vs loopback, 10 s simultaneous, in-memory | best \|corr\| = **0.0134** (control −0.0079) → refuted |
| the model cannot work at this level | mixtures of the clip + the **real** ambient (`_main/_bfrc_mix.py`) | +1.0 dB → 3 caps; −5.1 dB → 3 caps; −11.1 dB → 0; −17.1 dB → 0 (**floor ≈ −8 dB speech-to-ambient**) |

### 3.3 Who is putting audio into the default endpoint

`_main/_bfrc_endpoints.py` — every ACTIVE render endpoint, its master peak meter, and the
audio sessions on the default one (read-only; no stream started but the captures, nothing
played):

```
DEFAULT RENDER ENDPOINT id = {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}
active render endpoints: 6
  [       ] peak= 0.000000  {0.0.0.00000000}.{1aee4592-...}
  [       ] peak= 0.000000  {0.0.0.00000000}.{2f1295af-...}
  [DEFAULT] peak= 0.039307  {0.0.0.00000000}.{55395a4e-...}
  [       ] peak= 0.000000  ... (3 more, all 0)
SESSIONS on the default render endpoint:  count = 7
  session[0] pid=30076    state=1 ACTIVE   proc='MiiChan.exe'      display=''
  session[1] pid=20668    state=0          proc='Discord.exe'
  session[2] pid=21464    state=0          proc='chatterino.exe'
  session[3] pid=22932    state=0          proc='steam.exe'
  session[4] pid=21440    state=0          proc='Discord.exe'
  session[5] pid=14340    state=1 ACTIVE   proc='nvcontainer.exe'
  session[6] pid=0        state=0          proc='System Idle Process' display='@%SystemRoot%\System32\AudioSrv.Dll,-202'
```
`MiiChan.exe` = `I:\Games\RJ01722990 Fureai Mii-chan 1.0.4\MiiChan_1.0.4\MiiChan.exe`
(DLsite RJ01722990, a Japanese voice/ASMR work). **It is the only active application session
on the default render endpoint while the drone is playing**, and its audio is the drone:
no speech-grade energy above 3 kHz, no pauses, identical amplitude 3½ hours apart.

---

## 4. Root cause

**The blank frames are an honest transcription of an endpoint mix that contains no speech.**
There is no model, decode, resample, chunking or level defect — each was falsified above with
the *same* speech through the *same* stages, and the live path was proven end-to-end with
speech in it (§3.1.3).

The *defect* — the thing that made this take four investigations and that this lane was
opened for — is **the verdict the run emitted for that state**, plus two real robustness gaps
on the way to it:

1. **`worker/sotto_worker.py:1794` (was `:1671`, pre-fix) — `verdict = "model-emitted-nothing"`.**
   The failing live run reached this branch (`_main/bfrc_b_live.jsonl`:
   `verdict=model-emitted-nothing peak=0.101929 chunks=44 captions=0 frames=77 blanks=77
   vad_gated_chunks=33`). The tap was measurably ALIVE (peak 0.102 against a 0.002 floor),
   and the model's own front-end had withheld **33 of 44 chunks (75 %) as non-speech** — the
   run had the evidence to say "this mix is not speech" and instead said "the model emitted
   nothing". Every reader was sent to the model.
2. **`worker/wasapi_loopback.py:474-501`** — the pump reads `GetBuffer`'s `flags`
   (`:489`) and **discards it**. It never tests `AUDCLNT_BUFFERFLAGS_SILENT` (0x2), whose
   documented contract is that the buffer contents are *undefined*, nor
   `AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY` (0x1). Measured here: a `0x1` packet really
   occurs (`flags=0x0 x798, 0x1[DISC] x2`), and its contents are counted as audio in
   `nonzero_blocks`, `peak` and `rms`.
3. **`worker/wasapi_loopback.py:189`** — `if hr not in (0, RPC_E_CHANGED_MODE)` **rejects
   `S_FALSE` (1)**, which is a *success* code meaning "COM was already initialised on this
   thread". Every second call in the same thread raises
   `WasapiError: CoInitializeEx failed: Função incorreta. (0x00000001)`. Measured twice today
   (my own scripts) — this makes the module unusable from any process that already initialised
   COM in that apartment, e.g. a probe that asks for the endpoint and then builds the tap.

---

## 5. The fix (landed)

`worker/sotto_worker.py`, two edits, verdict ladder only. Nothing in capture, resample,
chunking, VAD, or config is touched.

- **`:1794-1806`** — new branch before `captions == 0 → model-emitted-nothing`:
  ```python
  elif counters["captions"] == 0 and asr.vad_gated_chunks > 0:
      verdict = "captured-signal-has-no-speech"
  ```
- **`:1856-1874`** — a loud status naming the device, the peak vs the floor, the chunks, how
  many the shipped VAD withheld and the blank fraction, plus an `err()` line. The state token
  `no-speech-in-capture` is safe for both shells: `app/electron/worker-bridge.js:150-166`
  (`describeState`/`humaniseState`) turns any unknown token into the sentence
  *"Worker: No speech in capture"*, and `FAILURE_WORDS` does not match it, so it is not
  coloured as an error.

**Command that proves it** (deterministic, no dependence on what the owner is playing —
`_main/_bfrc_proof.py` plays a known non-speech signal into the default output and runs the
real worker live against it):

```
pythonw.exe _main/_bfrc_proof.py
```
stdout, verbatim:
```
drone: n=720000 sr=48000 peak=0.0362
worker rc = 0
capture-started {"device": "WASAPI loopback: {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}"}
no-speech-in-capture {"verdict": "captured-signal-has-no-speech", "peak": 0.036133, "chunks": 31, "vad_gated_chunks": 26, "frames": 35, "blank_frac": 1.0, "captions": 0, "device": "WASAPI loopback: {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}", "detail": "the tap is alive (peak 0.036133 >= floor 0.002, 180 blocks) and 31 chunks reached the encoder, but 26 of them were withheld by the shipped VAD and every frame the model walked was blank -- the capture carries signal, it does not carry speech. This is not a model fault: re-route the app to this endpoint, or capture the endpoint the audio is actually on."}
done {"verdict": "captured-signal-has-no-speech", "peak": 0.036133, "chunks": 31, "vad_gated_chunks": 26, "frames": 35, "blank_frac": 1.0, "captions": 0}
```
stderr: `NO-SPEECH-IN-CAPTURE WASAPI loopback: {…55395a4e…} peak=0.036133 chunks=31 vad_gated=26 frames=35 captions=0 -- the endpoint carries signal that is not speech, not a model fault`

Negative control for the same code path — with speech playing, arm D returns
`verdict=captions-emitted captions=8` (raw output in §3.1.3), so the new branch is not a
catch-all that swallows success.

**Not changed, deliberately:** the exit code is still `return 3 if ran_but_silent else 0`, so a
"signal present, no speech" run still exits 0. Whether the shell should treat that as failure is
a product decision and belongs to whoever owns the bridge contract — flagging it rather than
deciding it here.

---

## 6. What this does NOT establish

- **Why the owner sees nothing is only answered for the audio that was there.** During every
  live run I could observe, the default endpoint carried MiiChan's non-speech audio and, at
  08:54, nothing at all. I did not observe a moment where the endpoint carried *speech* and
  Sotto still produced nothing — arm D shows that case works. If the owner's complaint comes
  from a moment when speech *was* playing, that moment was not reproducible from here and the
  new verdict is what will name it.
- The drone is attributed to `MiiChan.exe` by **elimination** (it is the only active
  application session on that endpoint, and the endpoint has no speech energy), not by an
  isolation test (muting that session's `ISimpleAudioVolume`), which I did not do because it
  mutates the owner's audio state.
- The negative claims about `resample_to_16k` cover the 48 k→16 k branch actually used and the
  22050→16000 `np.interp` branch. Other rates are not covered.
- Everything was measured on this box, on the endpoints listed in §3.3.

---

## SELF-AUDIT

- **protocolos em falta —** the one I should have followed and did not: I ran the *whole*
  experiment suite (15 runs) before checking whether another lane was holding the file I was
  measuring. `worker/sotto_worker.py` gained an AGC during the run (`:1526`, peer lane), which
  silently changed the front-end under a measurement set that was already "done" — I only
  noticed it because the stats line grew new fields. What I would do differently: **hash the
  target file before and after every measurement run and print the pair next to the result**;
  a measurement without its hash is not reproducible, and the prompt's own warning about stale
  artifacts applies to the *file under measurement* too, not just to my artifacts. (I did hash
  at the start, which is why I caught it — but I did not re-hash per run, so I cannot say which
  individual arm predates the AGC edit beyond "all of them, since they all lack `gain_db=`".)
- **verificacao adicional —** run the arm-D live control **before** the drone investigation, as
  a single gate. Cost: ~35 s. It is the cheapest possible falsifier of "the live path is
  broken" and it would have collapsed §2 and §3.1 into one step. Second one I did run and would
  keep: the mixture series (§3.2) at **−11.1 dB → 0 captions, −5.1 dB → 3 captions** turns "the
  speech is buried" from a guess into a number; without it, "no speech in the capture" and
  "speech too quiet under the hum" are the same observation.
- **checkboxes novas —**
  1. `MECANICO:` before any measurement run, record `sha256(worker/*.py)` and paste it beside
     the result. One-liner:
     `python -c "import hashlib;print(hashlib.sha256(open('worker/sotto_worker.py','rb').read()).hexdigest()[:16])"`.
  2. `MECANICO:` every "the worker is broken" claim must be paired with the **obverse control**
     — the same real path with known content — in the same run set. Gate: if no caption is
     produced in the control, no conclusion may be drawn from the failing arm.
  3. `MECANICO:` assert the run's `verdict` word against the counters that produced it, in the
     run itself: a run with `captions==0`, `peak >= tap_floor` and `vad_gated_chunks > 0` must
     never emit a verdict containing `model-emitted-nothing`. That is the checkbox this lane
     added to the code, so it should exist as a test too — see `gate-melhor`.
- **review por outro subagente —** **sim-com-escopo**: hand the *fix* (the two hunks in
  `sotto_worker.py`, :1794-1806 and :1856-1874) to a reviewer that owns the bridge contract,
  because the only thing I am unsure about is whether an unknown `state` token is truly inert
  end-to-end in the Electron renderer — I read `describeState`/`humaniseState` and believe it
  is (unknown tokens become "Worker: <Sentence>"), but I did not run the renderer. The
  *measurements* do not need review: every arm is raw output pasted above and re-runnable from
  `_main/_bfrc_*.py`.
- **gate-doubt:**
  - **verde-de-verdade:** the greens I used — can they be vacuous?
    - `rc=0` from the arms: **yes, vacuous by construction** — the same code returned `rc=0`
      for arm B, which produced zero captions. That is exactly why I never used rc as evidence
      and quoted the counters instead.
    - `selftest-done empty=false tokens=18`: **real**, and genuinely non-vacuous because the
      *same* four arms produce byte-identical counters (`frames=207 blanks=189 empty_chunks=24
      vad_gated_chunks=0`) from four different inputs — a vacuous path would not be
      input-insensitive at that level of detail. Naming the run: `_main/bfrc_a_22050_full.jsonl`
      / `bfrc_a_22050_quiet.jsonl` / `bfrc_c_48000_full.jsonl` / `bfrc_c_48000_quiet.jsonl`.
    - The fix proof is the strongest green and the one I checked for vacuity: the *same* branch
      must NOT fire when speech is present. It does not — arm D returns
      `verdict=captions-emitted captions=8`. A catch-all would have failed that. Run named:
      `_main/bfrc_armd.jsonl` vs `_main/bfrc_proof2.jsonl`.
    - `python -m py_compile` green — **vacuous**, it only proves importability.
    - The `bfrc_played_capture.wav` correlation 0.66 — I nearly read this as a weak green; it is
      *expected* under a ~50/50 played/ambient mix (predicts ~0.71), so it is evidence, not
      noise. But I did not bound it precisely, so I treat it as supporting, not decisive.
  - **falta-no-gate:** the gate does not verify that a *verdict word describes the counters of
    the run that emitted it*. A future change can reintroduce exactly today's bug: any run that
    reaches `captions==0` with a live tap and VAD-gated chunks, emitted under a word that names
    the model, passes every existing check (rc, JSON well-formedness, caption count). Concrete
    traversal: a later lane removes or reorders the `elif counters["captions"] == 0 and
    asr.vad_gated_chunks > 0` branch and re-runs the live smoke — the run stays green, the
    word goes back to `model-emitted-nothing`, and the next reader follows it to the model
    again. Second gap in the same place: nothing asserts that the two `worker/*.py` files'
    hashes are recorded with a measurement, so a concurrent lane's edit (which happened today)
    cannot be detected from the artifacts.
  - **gate-melhor:** a mechanical check with a RED arm, runnable now:
    ```
    # RED arm (must fail): force the old word by re-mapping the branch, then assert
    python - <<'PY'   # assert_verdict_matches_counters
    run = json.loads(last_jsonl_line_with_state_done)
    if run["verdict"] == "model-emitted-nothing" and run["peak"] >= 0.002 and run["vad_gated_chunks"] > 0:
        raise SystemExit("RED: verdict names the model for a run whose capture the VAD gated")
    PY
    ```
    Input that MUST leave it RED: `_main/bfrc_b_live.jsonl` (the pre-fix doneline, still on
    disk: `verdict=model-emitted-nothing peak=0.101929 vad_gated_chunks=33`) — asserted against
    this rule it exits non-zero. Input that must leave it GREEN: `_main/bfrc_armd.jsonl`
    (`verdict=captions-emitted`) and `_main/bfrc_proof2.jsonl`
    (`verdict=captured-signal-has-no-speech`). Same shape as this repo's existing
    `_main/verdict-order-oracle.py` red/green pair, which is where the pattern comes from.
- **confianca —** **alta** for "the live path, the resample, the level and the model are not
  the cause", and **alta** for "the capture in the observed runs contained no speech" (raw
  audio analyses, all six alternatives refuted, and the obverse control succeeds). **media**
  for "`MiiChan.exe` is the drone" — elimination + one active session, not an isolation test.
  What would move it to alta: mute via `ISimpleAudioVolume` and re-measure the endpoint meter,
  or observe one live run where the endpoint carries speech and Sotto still emits nothing.
- **nao verificado —**
  - no isolation test of the drone's producer (no `SetMute` on `ISimpleAudioVolume`);
  - no run through the Electron renderer, so the `no-speech-in-capture` token is verified by
    reading `worker-bridge.js` only, not by rendering;
  - `resample_to_16k` branches other than 22050→16000 and 48000→16000 (44100, 32000, 8000…);
  - the model was never exercised against a *different* ASR (e.g. sherpa-onnx) on the drone, so
    "not speech" rests on one model plus six signal-level analyses;
  - the `ALERTA-JANELA` the window census raised at 08:58:22 (`nome=pythonw pid=29500
    hwnd=5380366`) is **not mine**, and I did not chase it further: pid 29500 is
    `pythonw.exe H:\sotto\app\webview\sotto_webview.py --with-worker --log
    H:\sotto\_main\_live_owner.log`, created 05:57:22 — the product's own panel process,
    already running before this lane started. It belongs to whoever owns the window
    prohibition, not to this lane;
  - `git` state of `worker/sotto_worker.py` is dirty with at least two lanes' edits
    (mine + the AGC); I did not run `git diff` beyond hashing.

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh BlankFramesRootCause` — verbatim (rc=0):

```
## CACHE/PRICE
- task/agent: BlankFramesRootCause
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\BlankFramesRootCause.jsonl
- cache: read=12840576 write=0 hit=98.2925% (cache-read / input+cache-read); universe: 80 usage rows from ...\BlankFramesRootCause.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=76 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 80 of 80 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T08:40:06.445000+00:00 | break_items=2; WHEN=2026-10-06T08:42:24.797000+00:00 | break_items=3; WHEN=2026-10-06T08:46:58.361000+00:00 | break_items=2; WHEN=2026-10-06T08:57:29.242000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 114362 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'BlankFramesRootCause']; window: 2026-10-06T08:40:06.445000+00:00..2026-10-06T08:57:29.242000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1105e-7ac8-7321-bced-1e7c113cb232 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791276006445 | session_id=01a1105e-7ac8-7321-bced-1e7c113cb232 ... item_index=77; turn_id=1791276144797 | ... item_index=162; turn_id=1791276418361 | ... item_index=278; turn_id=1791277049242
- report generated_at: 2026-10-06T08:58:34.950993+00:00
- usage rows: 80
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 223065
- output tokens: 93098
- cache-read tokens: 12840576
- cache-write tokens: 0
- hit ratio: 98.2925% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: (as above — both routes report $0.00000000)
- prefix breaks: 10 (state=RESOLVED-BREAKS-OMP; population: 4 of 114362 ... keys ['01a10f72-...', 'BlankFramesRootCause'])
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T08:40:06.445000+00:00; WHERE session_id=01a1105e-... provider=deepseek-flash item_index=0; turn_id=1791276006445
  - break_items=2; WHEN=2026-10-06T08:42:24.797000+00:00; WHERE ... item_index=77; turn_id=1791276144797
  - break_items=3; WHEN=2026-10-06T08:46:58.361000+00:00; WHERE ... item_index=162; turn_id=1791276418361
  - break_items=2; WHEN=2026-10-06T08:57:29.242000+00:00; WHERE ... item_index=278; turn_id=1791277049242
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

(Source truncation in this document is marked with `...`; the verbatim full block is the tool output
in `artifact://2130`.) **Price is $0.00000000 because the source records no per-model rates —
reported as the instrument reports it, not as a claim that the work was free.**

---

## Evidence index (all under `H:/sotto/_main/`)

| file | what it is |
|---|---|
| `_bfrc_make_arms.py`, `bfrc_a_22050_{full,quiet}.wav`, `bfrc_c_48000_{full,quiet}.wav` | arms A/A'/C/C' inputs |
| `_bfrc_run_arms.py`, `bfrc_{a_22050_full,a_22050_quiet,c_48000_full,c_48000_quiet,b_live}.{jsonl,err}` | the arm runs |
| `_bfrc_capture.py`, `bfrc_live_capture.wav`, `bfrc_live_capture2.wav` | raw loopback → WAV |
| `_bfrc_play_capture.py`, `bfrc_played_capture.wav`, `bfrc_playedfile.jsonl` | tap fidelity + transcript of a played clip |
| `_bfrc_armd.py`, `bfrc_armd.jsonl` | live end-to-end control with speech (current worker) |
| `_bfrc_flags.py` | GetBuffer flag histogram |
| `_bfrc_all_endpoints.py` | every render endpoint: flags, packets, peak |
| `_bfrc_endpoints.py` | default endpoint, meters, session → process census |
| `_bfrc_content2.py`, `bfrc_live_highpass.wav`, `bfrc_hp.jsonl` | spectrum / modulation / high-pass |
| `_bfrc_mix.py`, `bfrc_mix_*.wav`, `bfrc_mixout_*.jsonl` | the speech-to-ambient detection floor |
| `bfrc_speed{2,4,6,8}.wav`, `bfrc_speedout_*.jsonl` | slowed-speech refutation |
| `_bfrc_mic.py` | microphone-vs-loopback correlation (mic in memory only, never written) |
| `_bfrc_proof.py`, `bfrc_proof2.jsonl`, `bfrc_proof2.err` | the fix's proving run |
| `bfrc_capfile.jsonl` | captured live audio fed back through the file path |

---

# ADDENDUM — lane BlankFramesDecisive (2026-10-06)

Lane `BlankFramesDecisive` ran the same decisive experiment independently and reaches the **same branch**
(neither "live-only blank" nor "BOTH blank": the live path is functional). Full receipt, raw arms and
self-audit: **`H:/sotto/_main/bfrc_decisive-report.md`** (this path is written concurrently by two lanes —
this addendum is append-only so neither doc can eat the other's text).
Only findings that are **not** already in the sections above are recorded here.

**1. The FAILING case, run properly — an obverse control with a real source.** The failing live run
(`bfrc_b_live`) was taken with no controlled source, so "the live path is broken" and "nothing decodable was
playing" were indistinguishable in it. Playing the clip through the default render endpoint *while* the
shipped worker captured the loopback separates them (`_main/_bfrc_armB.py`, worker child spawned with
`CREATE_NO_WINDOW` alone):

```
play H:\sotto\_main\pt-br-sample.wav sr=22050 n=334990 gain=0.3 peak=0.1747    # ARM B rc=0 wall=34.7s
{"type":"caption","text":"precisam","start":1.12,"end":1.68}
{"type":"caption","text":"O rá","start":6.72,"end":7.28}
{"type":"caption","text":"anunciou que","start":7.84,"end":8.4}
{"type":"caption","text":"Seg","start":12.88,"end":13.44}
{"type":"caption","text":"Os mora","start":15.12,"end":15.68}
{"type":"caption","text":"O","start":21.84,"end":22.4}
{"type":"status","state":"done","verdict":"captions-emitted","blocks":250,"nonzero_blocks":240,
 "peak":0.192619,"chunks":44,"captions":6,"vad_gated_chunks":0,"frames":327,"blanks":308,
 "blank_frac":0.9419,"audio_s":24.64}
```
`blank_frac=0.9419` **with 6 captions**, against the file arm's `0.913` with 3. High `blank_frac` is this
streaming RNN-T's normal state; `1.0` is the boundary. This is on the **pre-`AutoGain`** revision
(no `gain_db=` field in its `WORKER_STATS` line) — the live path captions with no gain stage at all.

**2. The tap's last un-audited hole, MEASURED (not assumed).** `worker/wasapi_loopback.py` reads
`GetBuffer`'s `flags` and discards them; Microsoft documents the contents are **undefined** when
`AUDCLNT_BUFFERFLAGS_SILENT` (0x2) is set. `_main/_bfrc_flags.py` re-reads the same endpoint with its own
COM plumbing and **keeps** the flags:

```
packets: 800
flag histogram (value -> count):
   flags=0x0 (0b0000) count=799  normal data
   flags=0x1 (0b0001) count=1  DATA_DISCONTINUITY
packets flagged SILENT: 0/800
  normal   packets: peak min=0.004700 med=0.028282 max=0.101929
total samples=384000 (8.00s) peak=0.10193 rms=0.013828
```
`0/800`, and the packet peaks **vary** (`0.0047 → 0.1019`) — the tap hands over real changing data. The
SILENT-flag defect is **latent, not the cause today**; the code path that turns undefined contents into
"audio" is still open.

**3. `frames=35 blanks=35` — which artifact it actually came from.** The brief quoted that number; it is
byte-identical to **`worker/runs/census-own-worker.jsonl:10`**, a run whose tap opened
**`Mapeador de som da Microsoft - Input` [MME]** and delivered **`peak=9.2e-05`, `nonzero_blocks=0`**. The
worker's own verdict on it is `"silent-device"` / `device_outcome:"all-flat"`, and stderr says
`SILENT-DEVICE ... peak=9.2e-05 < floor=0.002 over 34 blocks (1/1 opened candidates silent)`. So the number
in the brief is a **dead-device** run, not a model run and not a delivery-rate run. The `file:line` for the
two states that end a live run with zero captions:

- `worker/sotto_worker.py:762-767` — `device_candidates`' tail offers **every** non-microphone input,
  including Windows' Sound-Mapper pseudo-devices, which open, deliver blocks and are digital silence.
- `worker/sotto_worker.py:158-159` — `TAP_WINDOW_S = 6.0` / `TAP_PEAK_FLOOR = 0.002`: the floor rejects the
  dead device **correctly** (verdict `silent-device`) but only after the window is spent; and it **accepts**
  a virtual endpoint's idle floor (`peak≈0.102`) that is then `vad_gated` to death (`bfrc_b_live`: 33/44
  chunks gated, `captions=0`). The floor was calibrated against a dead tap (`peak=0.000031`) and cannot
  separate "carrying speech" from "carrying idle hum".

**4. Falsifier findings on the peer lane's `AutoGain` — reported, not fixed.**
*(a)* The stage's own comment (`sotto_worker.py:1426-1429`) claims *"the CONTROL arm: the same quiet source,
no gain, and (measured) no captions"*. Finding **2** above falsifies it as a causal claim: the live path
emitted 6 captions on the pre-`AutoGain` revision. A `SOTTO_AGC=0` control isolates the gain only if both
arms are fed a source that **carries speech**; on the endpoint's idle floor neither arm can caption, and on
the clip both do.
*(b)* **Run-maxima are published wrong, inside one run.** HEAD acceptance (`_main/_bfrc_head.py` →
`_main/bfrc_head.jsonl`), current revision, unmodified worker:

```
{"type":"caption","text":"Trabalhos","start":0.56,"end":1.12}
{"type":"caption","text":"Moradores","start":1.12,"end":1.68}
{"type":"caption","text":"O rá","start":2.24,"end":2.8}
{"type":"caption","text":"Segunda","start":8.4,"end":8.96}
{"type":"caption","text":"O rá","start":17.36,"end":17.92}
{"type":"status","state":"done","verdict":"captions-emitted","peak":0.187114,"peak_out":0.007454,
 "gain_db":2.4,"gain_max_db":2.4,"agc":true,"captions":5,"chunks":44,"frames":329,"blanks":308,
 "blank_frac":0.9362,"vad_gated_chunks":0,"audio_s":24.64}
WORKER_STATS tag=tick blocks=200 block_samples=960000 peak=0.187114 rms=0.02057661 gain_db=+12.5
  gain_min_db=+0.0 gain_max_db=+20.1 peak_out=0.767911 agc=on chunks=35 captions=5 ...
```
50 blocks later the `done` payload publishes `peak_out=0.007454 gain_max_db=2.4` where the run's own last
stats line published `0.767911` / `+20.1`. Both fields are **run maxima by construction**
(`sotto_worker.py:880-881`), so the run's loudest gain is unreportable — the same class the file's own
comment at `:1426` was written to prevent.

**5. The line I would change (not landed).** `worker/sotto_worker.py:159` (`TAP_PEAK_FLOOR`) together with the
tail at `:762-767`. Not landed: the Sound-Mapper name is localized (`Mapeador de som da Microsoft` /
`Driver de captura de som primário` / `Microsoft Sound Mapper`), so a name test is exactly the
non-universal detector this ladder was rebuilt to avoid, and no language-free predicate was derivable inside
the hour. `worker/sotto_worker.py` was also being written by another lane for the whole of this run.

## SELF-AUDIT (addendum)

- **protocolos em falta** — I did not read `history://BlankFramesRootCause` first: its arms were already on
  disk and I re-derived two of them (`bfrc_capfile`, `bfrc_playedfile`) by inspection instead of re-running
  them. My peer message was refused by the owner-screen guard (`agent://…` resolved as a filesystem path
  under `I:\!manager`), so coordination travelled only through this addendum and
  `_main/bfrc_decisive-report.md`.
- **verificacao adicional** — a `SOTTO_AGC=0` run on ARM B's own live source would settle §4(a) causally:
  ~40 s, one worker start, one playback. Not run: the file was mid-edit by the peer lane, so the receipt
  would be against a revision that no longer exists when read.
- **checkboxes novas** — (a) every "blank/zero-output" claim must print its run's own `verdict` beside
  `blank_frac` (`grep -o '"verdict": "[a-z-]*"' <run>.jsonl`); (b) blaming the model requires
  `nonzero_blocks > 0`, because a run with `nonzero_blocks=0` has nothing to transcribe by construction.
- **review por outro subagente** — **sim-com-escopo**: §1's raw files against the branch decision,
  specifically that ARM B had a real playing source.
- **gate-doubt** — *verde-de-verdade:* ARM B is a real green, falsifiable by its own twin `bfrc_b_live`
  (same command, nothing playing, `captions=0`); the weak green is `0/800 SILENT`, which is green today on
  this endpoint only. *falta-no-gate:* nothing compares `done.peak_out` / `gain_max_db` against the run's own
  `WORKER_STATS` maxima. *gate-melhor:* assert `done.peak_out == max(tick.peak_out)` per run — RED input as
  it stands today is `_main/bfrc_head.jsonl` (`0.007454` vs `0.767911`).
- **confianca** — **alta** on the branch; **media** on attributing the brief's exact number (matched by
  value against `census-own-worker.*`, not observed being produced).
- **nao verificado** — the owner's own player was never driven (I used `sd.play`, default output PortAudio
  device 7 `VoiceMeeter Input (VB-Audio Voi` [MME]); the default render endpoint `{55395a4e-…}` could not be
  named (property store returned `hr=-2147467261`); `bfrc_speed2/4/6/8` were recorded, not re-derived.

## CACHE/PRICE (addendum)

```
## CACHE/PRICE
- task/agent: BlankFramesDecisive
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\BlankFramesDecisive.jsonl
- cache: read=2703488 write=0 hit=95.2244% (cache-read / input+cache-read); universe: 31 usage rows; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP; window 2026-10-06T08:52:04.860000+00:00..2026-10-06T08:54:15.670000+00:00)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T08:52:04.860000+00:00; WHERE provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0
  - break_items=1; WHEN=2026-10-06T08:52:05.668000+00:00; WHERE provider=space-bunny-free item_index=0
  - break_items=1; WHEN=2026-10-06T08:52:06.119000+00:00; WHERE provider=ling-3.1-flash-free item_index=0
  - break_items=3; WHEN=2026-10-06T08:52:06.480000+00:00; WHERE provider=deepseek-flash item_index=0
  - break_items=2; WHEN=2026-10-06T08:54:15.670000+00:00; WHERE provider=deepseek-flash item_index=50
- input tokens: 135582 · output tokens: 38815 · cache-read 2703488 · cache-write 0
- verdict: UNKNOWN — no task-level acceptance verdict is stored; the ratio is descriptive, not a prefix-stability decision
```
(First attempt blocked by the C4/PIPE-STATUS landmine guard — the command was piped to `head`; rerun as
`cmd > log 2>&1; rc=$?; cat log` → rc=0.)
