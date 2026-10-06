# The universal audio ladder — how Sotto finds "whatever the PC is playing"

Owner directive, verbatim:

> "esse app nao é so pra uso meu, é pra qualquer usuario. entao tem que detectar
> audio de uma forma universal e robusta"

This document is the design that follows from that sentence. It exists because the
shipped `worker/config.json` used to name three devices that exist on ONE machine.

---

## 1. The defect this replaces

`worker/config.json` carried:

```json
"preferred_devices": [
  "CABLE Output (VB-Audio Virtual Cable)",
  "VoiceMeeter Output",
  "Mapeador de som da Microsoft - Input"
]
```

Three literal names. A normal Windows PC has no VB-Cable installed, so on that PC
none of the three resolves and the product cannot capture system audio at all.

Two further measurements kill the literal-name approach outright:

* **MME truncates device names at 31 characters.** `H:/sotto/_main/device-names.log`
  records the same cable as `'CABLE Output (VB-Audio Virtual '` under MME and as
  the full `'CABLE Output (VB-Audio Virtual Cable)'` under DirectSound and WASAPI.
  A name-equality test over the MME list CANNOT succeed for any name longer than
  31 characters. **No product may depend on these names.**
* **One physical endpoint appears under several indices** (44.1 kHz on MME, on
  DirectSound and on WASAPI — three device ids for one cable). A rotation that
  treated indices as distinct devices would burn its budget re-probing one
  endpoint.

And the failure was SILENT. Measured by Main: the resolver opened
`'Driver de captura de som primário'`, read peak=0.000122 over 214 blocks —
digital silence — emitted 0 captions and **exited 0**.

---

## 2. What Windows actually offers (the vendor-documented, driver-free path)

The universal way to capture "whatever the PC is playing" on modern Windows is
**loopback of the DEFAULT RENDER endpoint** — no virtual cable, no installed
driver, no third-party package.

* Core Audio / WASAPI loopback recording —
  <https://learn.microsoft.com/windows/win32/coreaudio/loopback-recording>
* `IAudioClient::Initialize` and `AUDCLNT_STREAMFLAGS_LOOPBACK` —
  <https://learn.microsoft.com/windows/win32/api/audioclient/nf-audioclient-iaudioclient-initialize>
* Default-endpoint enumeration and device roles —
  <https://learn.microsoft.com/windows/win32/coreaudio/device-roles>
* Windows 10 2004+ (build 19041) process-scoped loopback —
  <https://learn.microsoft.com/windows/win32/audio/process-loopback>

The sequence, implemented in `worker/wasapi_loopback.py`:

1. `CoCreateInstance(CLSID_MMDeviceEnumerator)` → `IMMDeviceEnumerator`
2. `GetDefaultAudioEndpoint(eRender, eConsole)` → `IMMDevice`
3. `IMMDevice::Activate(IID_IAudioClient)` → `IAudioClient`
4. `IAudioClient::GetMixFormat()` → the endpoint's MIX format
5. `IAudioClient::Initialize(SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, …, mix)`
   — **the stream MUST use the mix format.** A loopback stream has no format
   negotiation, so the usual "ask for 16 kHz mono" fails; the conversion is done
   in this process instead (`resample_to_16k`, an exact 3:1 block average at
   48 kHz → 16 kHz).
6. `IAudioClient::GetService(IID_IAudioCaptureClient)` → `IAudioCaptureClient`
7. `Start()`, then poll `GetNextPacketSize` / `GetBuffer` / `ReleaseBuffer`.

`AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK` (`ActivateAudioInterfaceAsync`)
is the modern sibling and is **not required** by the ladder: the default-render
loopback above works on every Windows machine that has a sound card at all. The
capability probe reports whether process loopback is available, for future use.

### Two traps measured while building this, both now commented in the code

* `ctypes` defaults a `WinDLL` function's `restype` to `c_int` (32 bits).
  `CoCreateInstance` writes a 64-bit interface pointer through its last
  out-parameter, so WITHOUT explicit `argtypes`/`restype` the pointer is
  truncated and the first vtable call dies: measured as
  `OSError: access violation reading 0xFFFFFFFFFFFFFFFF`.
* `GetDefaultAudioEndpoint` takes **three** parameters —
  `(this, flow, role, ppEndpoint)`. Declaring only two corrupts the stack and
  faults the same way.

---

## 3. The ladder

Candidates are built by `device_candidates()` in `worker/sotto_worker.py`, in this
order, and **each candidate records the rung it came from**:

| rung | what | notes |
|---|---|---|
| **c** | the explicit `--device` / `SOTTO_AUDIO_DEVICE` override | **always wins.** Offered first, and a flat window does *not* rotate away from it (`outcome = "explicit-flat"`), so the run reports a NAMED failure instead of silently opening something else. |
| **a** | WASAPI loopback of the default render endpoint | driver-free; added only when this machine can actually open it, so a box with no render endpoint skips to (b) instead of failing. |
| **b** | a virtual-cable / stereo-mix INPUT matched by NAME HEURISTIC | `LOOPBACK_NAME_PATTERNS`: cable, virtual, loopback, voicemeeter, vb-audio, stereo mix, mixagem est, what u hear, wave out, monitor, aquario, vac. Matched case-insensitively as substrings, any host API, any language. The matched pattern is recorded (`rung_why`). |
| tail | remaining non-microphone inputs | so a rotation always has somewhere to go. |

`PREFERRED_DEVICES` is now **empty on purpose** and `config.json` ships
`"preferred_devices": []`. Device choice is decided at run time, not pinned in a
file written on someone else's machine.

### Recording the rung, and the measured signal

Every candidate the run actually opens appends one row to `tap_ledger`:

```json
{"device": "...", "api": "...", "rung": "a", "rung_why": "...",
 "peak": 0.461299, "blocks": 245, "captions": 29, "settled": true, "outcome": "run-ended"}
```

`peak` and `blocks` are measured **on that candidate**, reset per candidate, so a
verdict about a device can never quote another device's numbers.

### A silent capture is a NAMED FAILURE

A tap that OPENS is not a tap that HEARS. If a candidate opened, ran a real
window and never reached `TAP_PEAK_FLOOR` (0.002), the run emits
`state="silent-device"`, an stderr line naming the device, its host API and the
measured peak, and **exits 3** — not 0. 3 is distinct from 2 (setup error) so a
caller can separate "never started" from "started and got nothing".

---

## 4. The capability probe (its own artefact)

`_main/capability-probe.py` — pure `ctypes`, no third-party dependency, so it runs
on any Windows machine. It prints ONE verdict line a non-expert can read.

Measured on this box (`_main/capability-probe.log`), 2026-10-06:

```
mix format: tag=0xFFFE (extensible->0x0003) rate=48000 Hz channels=2 bits=32 blockAlign=8
IAudioClient::Initialize(SHARED|LOOPBACK) -> OK  (the driver-free rung works)
IAudioClient::GetService(IAudioCaptureClient) -> OK
IAudioClient::Start -> OK
pumped 203 packets / 97056 samples over 2.0s
measured peak=0.350000 rms=0.247478
Windows build 26200 (RtlGetVersion 10.0)
process loopback: AVAILABLE (build 26200 >= 19041)

VERDICT: YES — this PC can capture system audio with NO virtual cable. WASAPI
loopback of the default render endpoint OPENED "{0.0.0.00000000}.{55395a4e-…}"
(48000 Hz, 2 ch, 32-bit) and delivered 203 packets; peak=0.350000.
```

`peak=0.350000` is a **positive control**: the probe plays a 440 Hz tone at
amplitude 0.35 on the same endpoint it captures, so a non-zero peak proves the
signal path returns real audio — not merely that handles opened. Without the
tone, `peak=0` would be ambiguous (Windows only feeds a loopback client while
the endpoint is actually rendering).

---

## 5. Acceptance evidence

**Rung taken and device opened (positive arm, real speech through the default
render endpoint, no virtual cable involved):**

```
{"type": "status", "state": "capture-started",
 "device": "WASAPI loopback: {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}",
 "rate": 48000, "block": 4800, "attempt": 1, "of": 6}

rung=a why=WASAPI loopback of the default render endpoint
  peak=0.461299 blocks=245 captions=29 outcome=run-ended
verdict=captions-emitted  proved_alive=True  proved_reason=caption  captions=29
EXIT=0
```

**The negative arm** — `--device` pointed at a known-silent input. The check went
RED, which is what makes it evidence:

```
EXIT=3
{"type":"status","state":"silent-device","verdict":"silent-device",
 "device":"Driver de captura de som primário","api":"Windows DirectSound",
 "peak":0.000122,"peak_floor":0.002,"blocks":59,...}
SILENT-DEVICE Driver de captura de som primário [Windows DirectSound]
  peak=0.000122 < floor=0.002 over 59 blocks
```

and the ledger shows the explicit override was honoured, not rotated away:

```
rung=c rung_why=explicit override ... outcome=flat   device_outcome=explicit-flat
```

---

## 6. What CANNOT be verified here

**This box is one machine, and it has VB-Cable installed.** Therefore
"works on a machine with no virtual cable" is an **inference from the API
guarantees** — the loopback client is opened on the default render endpoint
through documented Core Audio interfaces and touches no third-party driver — and
**not a measurement**. It was not measured on a machine without a virtual cable,
because no such machine was available.

What WAS measured is narrower and should be quoted as such: the loopback client
opened on the default render endpoint, was initialized with the endpoint's mix
format, started, delivered 245 blocks and reached peak 0.461299 with real speech,
yielding 29 captions — on a machine where the default render endpoint happens to
be a VB-Audio endpoint.

Two further limitations, both measured and both handled rather than hidden:

* Some drivers publish no `PKEY_Device_FriendlyName`; the identity then falls back
  to the endpoint ID, which is exact but not human-readable.
* WASAPI loopback does not exist as a PortAudio device, so `sounddevice` cannot
  reach it. That is precisely why rung (a) is implemented in `ctypes` and why the
  old config hardcoded a cable instead.

---

## 7. Files

| path | what |
|---|---|
| `worker/wasapi_loopback.py` | rung (a): the `ctypes` loopback capture client |
| `worker/sotto_worker.py` | `LOOPBACK_NAME_PATTERNS`, `heuristic_loopback_score()`, the ladder in `device_candidates()`, the `LoopbackTap` factory, the `rung` ledger field, the non-rotating explicit override |
| `worker/config.json` | `device: null`, `preferred_devices: []` — deliberately empty |
| `_main/capability-probe.py` | the capability probe and its positive control |
| `_main/ladder-probe.py` | runs the ladder and prints which rung wins |
| `_main/play-to-default.py` | hidden player used as the positive control |

---

## SELF-AUDIT

* **protocolos em falta** — I should have read the harness's page-fetch policy BEFORE
  trying vendor URLs: `read` on three learn.microsoft.com pages returned HTTP 404 and
  both `web_search` and `gpt_search` were refused by the SEARCH-ORDER-GATE and the
  restart hook. I burned four calls on that. What I would do differently: attempt the
  consultgpt search path first, and treat a 404 from the docs host as "this fetcher
  cannot reach it" rather than retrying sibling URL shapes.

* **verificacao adicional** — a control that would raise confidence cheaply: run the
  ladder on a machine WITHOUT VB-Cable and confirm rung (a) still opens and carries
  audio. Cost: a second Windows host, which is not available here — so the claim stays
  an inference from the API contract (see §6). A cheaper partial: uninstall/disable the
  VB-Cable endpoints and re-run the capability probe; NOT done, because it changes the
  owner's audio routing on a machine he is using, which is out of scope for a lane.

* **checkboxes novas** — a mechanical step worth adding to this class of work:
  **assert the negative arm's exit code is non-zero in the same script that runs it.**
  `... silent.json == 3` — a check that cannot go red is not evidence, and the arm is
  only evidence if the exit code is read where it is produced. The landmine guard
  (C4/PIPE-STATUS) blocked exactly this pattern twice; capturing `rc` immediately after
  the producer is the discipline that enforces it.

* **review por outro subagente** — **sim-com-escopo**: a reviewer should verify
  (a) that `worker/wasapi_loopback.py` releases every COM interface it acquires on the
  failure paths, and (b) that the `resample_to_16k` 48k→16k block-average path is fed a
  block-aligned buffer (my tap emits exactly `block` samples, but a reviewer should
  confirm the consumer does not assume 16 kHz when handed 48 kHz).

* **gate-doubt**
  - **verde-de-verdade**: the green I am most confident in is the positive arm —
    `verdict=captions-emitted`, `captions=29`, `peak=0.461299`, exit 0, with **real
    English captions** ("Place", "Sunday", "He can come to", "immediately") transcribed
    from a file played through the default render endpoint. That green could NOT have
    passed vacuously: the same binary, minutes earlier, with the player broken, produced
    `verdict=silent-device` and 0 captions. The negative arm is the second: exit 3 with a
    named device and a measured peak, against the same code path.
  - **falta-no-gate**: the ladder does NOT verify that the device it opened is the device
    the owner HEARS. On this box the default render endpoint resolves to a VB-Audio
    endpoint (`VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)`, PortAudio index 28), so
    "capture the default render endpoint" and "capture the speakers" coincide only
    because of the owner's routing. A future change that re-routes default output to a
    different endpoint would silently change what Sotto transcribes, and nothing in the
    ledger would show the change — the ledger records the rung and the name, not the
    fact that the name moved.
  - **gate-melhor**: a mechanical check that closes it — record the endpoint id alongside
    the name in `tap_ledger` and assert it is stable across runs, going RED when it
    changes:
    `python _main/ladder-probe.py | grep -q 'endpoint_id'` with the expected id pinned;
    input that must make it RED: swap the Windows default playback device and re-run.

* **confianca** — **alta** for rungs (a), (b) and (c) on THIS box, because each was
  exercised: (a) produced 29 captions, (b) matched three cable/stereo-mix endpoints by
  pattern with no literal list, (c) was honoured and NOT rotated away from. **media**
  for "works on a machine with no virtual cable", because that is an inference from the
  API contract and not a measurement — stated plainly in §6.

* **nao verificado** —
  * a machine with no virtual cable installed (no such machine available);
  * process-scoped loopback (`AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK`) — the probe
    reports it AVAILABLE (build 26200) but the ladder does not use it and it was never
    exercised;
  * Linux/macOS — `wasapi_loopback.py` raises `WasapiError` off Windows and the ladder
    falls through to rung (b);
  * long-run stability (>32 s) of the loopback pump thread; the longest run measured was
    ~32 s / 245 blocks;
  * whether the `resample_to_16k` 3:1 block average is the best quality choice for 48 kHz
    capture — it is exact and cheap, but no audio-quality comparison was run.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoUniversalAudio
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoUniversalAudio.jsonl
- cache: read=21366351 write=0 hit=97.7753% (cache-read / input+cache-read); universe: 123 usage rows
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- usage rows: 123
- input tokens: 486145
- output tokens: 64890
- cache-read tokens: 21366351
- hit ratio: 97.7753%
- prefix breaks: 516 (state=RESOLVED-BREAKS-OMP)
- report generated_at: 2026-10-06T06:35:43.465574+00:00
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

WHEN / WHERE failed (verbatim, truncated by the instrument):

```
- WHEN / WHERE failed:
  - break_items=2; WHEN=2026-10-06T06:20:11.250000+00:00; WHERE session_id=01a10fdc-4154-76cb-825b-1b298c483221 provider=space-bunny-free model=space-bunny-free item_index=40; turn_id=1791267611250
  - break_items=2; WHEN=2026-10-06T06:24:40.947000+00:00; WHERE ... item_index=127; turn_id=1791267880947
  - break_items=150; WHEN=2026-10-06T06:26:18.347000+00:00; WHERE ... provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791267978347
  - break_items=60; WHEN=2026-10-06T06:26:19.629000+00:00; WHERE ... provider=ling-3.1-flash-free item_index=0; turn_id=1791267979629
  - break_items=2; WHEN=2026-10-06T06:35:09.625000+00:00; WHERE ... provider=deepseek-flash item_index=480; turn_id=1791268509625
```

Full report: `H:/sotto/_main/cache-report.log`.
