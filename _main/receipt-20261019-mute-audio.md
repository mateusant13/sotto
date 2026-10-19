# Sotto receipt — the MUTE: the rule the owner asked for, in one place

Owner, 2026-10-19, verbatim:

> "se tu vai usar audio padrao pra testar qualquer coisa, muta. nao quero ficar ouvindo."

## The problem, stated plainly

What existed on 2026-10-19 was a **REFUSAL**, not a mute.

`_main/inject-all-probe.py:54-70` and `_main/_audio-tone-inject.py` (the
refusal, ~lines 97-100) compare the resolved render endpoint with the
system default output and walk away with `rc=4` (`"refused":"AUDIBLE-DEVICE"`)
**without playing anything**, unless `SOTTO_ALLOW_AUDIBLE=1` is set in the
environment. The refusal is correct and it stays (it is not my file, and I did
not touch it).

But a refusal is a dead end for the lane that needs the measurement: the test
does not run, and the only ways forward are to ask the owner to listen to a
tone, or to invent a private workaround per probe. The owner asked for the
OTHER door — a **mute**: the test runs on the default endpoint and the owner
hears nothing. This lane builds that door, once, in a single module that any
lane can call.

## What was measured (2026-10-19, on this box)

Instrument: `pycaw` against the Windows audio engine, via
`AudioUtilities.GetDeviceEnumerator()`; every number below is a value the
device itself reported.

| what | measured |
|---|---|
| default RENDER endpoint, role **eConsole** | `VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)`, id `{0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}` |
| default RENDER endpoint, role **eMultimedia** | the SAME device and the SAME id |
| default RENDER endpoint, role **eCommunications** | a DIFFERENT device: `Headset (soundcore Space Q45 Hands-Free)`, id `{0.0.0.00000000}.{686fb05d-82f7-4a21-8449-a04db7086a69}` |
| master volume unit | a **SCALAR 0..1** (`Get/SetMasterVolumeLevelScalar`) |
| `Get/SetMasterVolumeLevel` unit | **DECIBELS**, not 0..100: scalar 1.0 → `0.0 dB`, scalar 0.37 → `-15.06622314453125 dB`, scalar 0.0 → `-96.0 dB` |
| `SetMasterVolumeLevel(50)` on this endpoint | `COMError -2147024809` ("parametro incorreto") — +50 dB is not a legal level |
| scalar round trip, float32 quantised | set `0.37` → reads back **`0.3700000047683716`**; set `0.5` → `0.5`; `0.0` → `0.0`; `1.0` → `1.0` |
| owner master volume before/after every run of the gate | `1.0` before, `1.0` after (measured, see below) |

## The decisions, and why each one

**1. The saved value is the value that was READ, never the value that was
SET.** The device quantises to float32 (0.37 → 0.3700000047683716). A mute
that saves "0.37" and restores "0.37" restores `0.3700000047683716` — not the
same float, and an exactness check against the written value fails forever.
So `mute_default_output` READS the volume, stores that float, and the gate
compares the restored value against the value read after the write. This is
the whole reason the arm says "guardado=0.3700000047683716 restaurado=
0.3700000047683716 igual=True".

**2. The mute is verified, not assumed.** After writing 0, the library READS
the volume back and refuses to call it a mute if it is not 0.0 — it rolls the
volume back and raises `MuteError`. A write that does not take effect is a
mute that did not happen, and the owner has no way to tell.

**3. The state file is written AFTER the volume is really at 0.** If the
state write fails, the volume is rolled back and `MuteError` is raised: a mute
that nobody can undo is worse than no mute at all.

**4. The restore keeps the state file if it fails.** The saved volume is the
only copy of the owner's setting; a failed restore must be retryable, not
final.

**5. A second mute does NOT overwrite the saved value.** Two mutes in a row
leave ONE saved value (the first one). Otherwise the second mute would save
`0` and the unmute would restore silence.

**6. An unmute with nothing to undo touches nothing.** It returns
`{"state":"not-muted"}` and leaves the owner's volume alone.

**7. A mute left on a device that is no longer the default is restored
first.** If the default output changed while the mute was in place, the OLD
device is put back before the NEW one is muted, so no device is ever left at
0 without a way back.

**8. Role eConsole by default.** It is what Windows' Sound settings shows,
and it is the role under which the owner's speakers are the default. eConsole
and eMultimedia resolve to the same device here; eCommunications does not
(and it is the role a phone call would use, so muting it would silence the
wrong thing).

**9. `QueryInterface`, not `ctypes.cast`.** The canonical pycaw snippet
casts the activated `IUnknown` to `POINTER(IAudioEndpointVolume)`. That
builds a SECOND wrapper around the same COM identity and both release it at
exit — comtypes then prints `access violation reading 0xFFFFFFFFFFFFFFFF` on
shutdown. Measured: with `cast` the oracle's stderr was full of those
tracebacks; with `QueryInterface` (which carries its own reference) stderr is
**0 bytes**. Same volume, same device, no noise.

**10. Nothing is written outside `_main/`.** The state file is
`_main/mute-audio-state.json`, already covered by `.gitignore`'s
`_main/*-state.json`. The oracle writes only under `TMPDIR`
(`I:\cc-tmp`) and only the state file inside its own state directory — the
arm "o mute escreve SO o ficheiro de estado e apaga-o no unmute" measures
exactly that (`durante=['state.json'] depois=[]`).

**11. The "50" of the order is `0.5`.** The scalar API is 0..1, so "50" is
50% — `0.5`. The raw-level API on this endpoint is decibels and +50 dB is an
invalid parameter, so a literal 50 cannot even be written. Both mutations are
in the gate: one restores 50%, one writes the literal 50, one restores the
system default.

## The gate — `_main/mute-audio-oracle.py`

    python _main/mute-audio-oracle.py            -> rc=0, VERDICT: PASS arms 21/21 mutants 8/8
    python _main/mute-audio-oracle.py --neg-arm  -> rc=1 BY DESIGN (prints the catching check of every mutant)

Measured output of the last full run (stderr = 0 bytes):

    21/21
    VERDICT: PASS  arms 21/21  mutants 8/8

The arms cover: the endpoint resolves; the mute puts the volume at 0; the
unmute restores EXACTLY the saved value; the unmute restores MY value and
not the system default; two mutes do not cancel each other; an unmute with
nothing to undo is harmless; the state file disappears after the unmute; the
CLI does the full `--mute/--status/--unmute` cycle; the CLI `--status`
prints the default output and the volume; the `--mute` that waits restores
the volume when it is interrupted; the state file lives next to the module
(and, for the real file, in `_main/`); a mute that does not take effect
raises and leaves the volume alone; a device that blows up raises and leaves
nothing half done; a failed restore keeps the state and a second attempt
succeeds; a changed default is handled both ways; only the state file is
written; and the module imports NO audio library (it cannot render audio —
it only moves a volume).

The negative arm is 8 behavioural mutants, each caught by the check that owns
the defect (this is what the `--neg-arm` run prints):

| mutant | caught by |
|---|---|
| `mute-does-not-zero-the-volume` | *mute põe o volume a 0* |
| `mute-swallows-the-failure` | *se o dispositivo rebenta a meio do mute, o erro e explicito* |
| `second-mute-overwrites-the-saved-value` | *duas chamadas de mute nao se anulam* |
| `unmute-without-mute-touches-the-volume` | *unmute sem mute previo e inofensivo* |
| `unmute-restores-50-percent-not-the-saved-value` | *unmute restaura EXACTAMENTE o valor guardado* |
| `unmute-restores-the-literal-50-not-the-saved-value` | *unmute restaura EXACTAMENTE o valor guardado* |
| `unmute-restores-the-system-default-not-the-saved-value` | *unmute restaura EXACTAMENTE o valor guardado* |
| `unmute-deletes-the-state-before-restoring` | *se o restore falhar, o estado SOBREVIVE e a segunda tentativa restaura* |

A mutant whose anchor is missing or ambiguous is counted as **DECORATIVE**
and fails the VERDICT — it is not counted as "caught". That distinction is
not decoration: the first version of this gate reported 4/8 mutants caught
when 4 of them had not run a single check (their anchor matched `_try_restore`
instead of the unmute), and the fix was to make the anchor unique and to stop
counting a mutant as caught for the wrong reason.

**Cost on the owner's screen: nothing is rendered, ever.** The gate changes a
volume; it never opens an audio stream. During a full run the owner's master
volume is moved to 0 and back a few times (each move is a single COM write,
milliseconds), and it is restored to `1.0` in a `finally` whatever happens.
Measured after the last full run: `{"state":"unmuted","muted":false,
"volume":1.0}` and no state file at the default path.

## What was NOT measured — declared

1. **That this mute covers EVERY path to the owner's ears.** It covers the
   **default render endpoint** (`VoiceMeeter Input`): that device is at 0
   while the mute is in place. But the 2026-10-07 receipt
   (`_main/receipt-20261007-audible-stimulus.md`) measured that the CABLE
   path put real sound in the ROOM (room microphone 0.24–0.77) while
   `VoiceMeeter Output` read digital silence — i.e. that sound reached the
   room by a path that was NOT identified. If that path does not pass through
   the muted endpoint, this mute does not silence it. **Not measured**, and
   measuring it means rendering audio and pointing a microphone at the room —
   exactly what the owner asked not to happen.
2. **The pendency `DONO-20261007-sotto-nunca-audivel` stays OPEN.** This lane
   adds a second, independent guarantee; it does not close that one. The
   refusal in `inject-all-probe.py` / `_audio-tone-inject.py` remains the
   primary protection and was not modified.
3. **The OS-level Ctrl+C delivery** was not exercised: the arm injects the
   `KeyboardInterrupt` itself (the branch this code owns). Whether the
   keypress reaches a `pythonw.exe` console on this box was not measured.
4. **A second machine, a different default endpoint, or an endpoint whose
   volume is owned by the vendor app** (VoiceMeeter refusing a write) were
   not tested. The failure paths are tested with a deterministic fake device
   (a write that silently does not take effect, a device that raises), not
   with those boxes.
5. **The mute does not mute a per-application session volume.** Windows lets
   an app set its own session volume above the device's master volume; that
   path was not measured and is not controlled here.

## The rule, for any lane that renders audio

    from mute_audio import mute_default_output, unmute_default_output   # or:
    python _main/mute-audio.py --mute          # waits; Ctrl+C restores
    python _main/mute-audio.py --mute --no-wait  # leaves the mute in place
    python _main/mute-audio.py --unmute
    python _main/mute-audio.py --status

Prefer the CABLE (`CABLE Input`) when the measurement allows it: it is
inaudible BY CONSTRUCTION (the audio emerges at `CABLE Output`, a capture
endpoint). The mute is for the cases where the default endpoint is the thing
under test. It is fail-safe: if it cannot mute, it says so loudly and leaves
the volume alone — it never leaves a half mute and never mutes by accident.

## Files (mine, and only mine)

| file | bytes | CRLF | bare LF | sha256 (16) |
|---|---|---|---|---|
| `_main/mute-audio.py` | 15687 | 0 | 410 | `E5A94A4FE746B54E` |
| `_main/mute-audio-oracle.py` | 27108 | 0 | 583 | `F7A8C65AA200EB9E` |
| `_main/receipt-20261019-mute-audio.md` | this file | 0 | — | — |

`_main/*.py` is LF-pure in this repo and these two are too (0 CRLF, 0 mixed).
Nothing was committed: the index carries ~764 foreign entries and the Lead
commits.

Not touched: `app/webview/sotto_webview.py`, `app/panel/*`, `worker/*`,
`_main/inject-all-probe.py`, `_main/_audio-tone-inject.py`, `AGENTS.md`,
`.gitignore`.
