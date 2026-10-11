# Process loopback PROVEN by an independent instrument (2026-10-11)

Second, independent proof of the owner's hard requirement (per-app audio separation), from a lane
that shares no code with the earlier gate: `_main/process-loopback-probe.py` — **79 361 B, 1 757
lines, sha256 `63D73610104F0666A88F07F4C51E4C40D2A39DA7435F5D7A80B71377BDF9C213`**, stdlib `ctypes`
only (no comtypes, no pycaw, no sounddevice, no numpy).

## What I verified myself (I did NOT re-run it: it plays an audible 440 Hz tone)

- **Pin MATCHES**: 79 361 B and the sha256 above, measured on the bytes.
- `py -3 -m py_compile _main/process-loopback-probe.py` → **rc=0**.
- The lane's own stdout artefact is real and carries the deciding lines:
  `I:\cc-tmp\plp-stdout4.txt` 7 867 B, mtime 2026-10-11T22:32:45Z, containing
  `POSITIVE … peak=0.400000`, `NEGATIVE-A … peak=0.000000`, `VERDICT: PROCESS LOOPBACK PROVEN`,
  `EXIT: 0`; JSON `I:\cc-tmp\plp-result4.json` 6 198 B.
- **No stray child left behind**: the render child `pid 40572` is not in the process table.
- `git status` names exactly one untracked artefact: `_main/process-loopback-probe.py`.

## The deciding numbers (run 4; run 3 identical)

| arm | target | packets / frames | peak | rms | nonzero |
|---|---|---|---|---|---|
| **POSITIVE** | our render child, 440 Hz @ 0.4 into the NON-default `CABLE Input` | 299 / 143 520 | **0.400000** | 0.281361 | 296 |
| **NEGATIVE-A** | a live non-rendering `cmd.exe`, tone STILL playing | 199 / 95 520 | **0.000000** | 0.000000 | **0** |
| EXCLUDE | the same child, `EXCLUDE_TARGET_PROCESS_TREE` | 199 / 95 520 | 0.000000 | 0.000000 | 0 |
| NEG-B (informational) | invalid pid | — | pid `0` → `0x80070057` REJECTED; pid `0xFFFFFFFE` → `0x00000000` ACCEPTED | | |

This is a stronger form of the earlier gate: **same API, same endpoint, same instant**, the tone
audible to the first target and provably absent for the second. `rms/peak = 1.4213 = sqrt(2)` on the
positive arm — a clean sine at exactly the rendered amplitude, not noise and not a leak. The EXCLUDE
arm reads 0.000000, so the mode field is honoured.

## The activation recipe (the reusable answer, and what the worker already does)

`ActivateAudioInterfaceAsync(L"VAD\\Process_Loopback", IID_IAudioClient, &pv, handler, &op)` from
`Mmdevapi.dll` — NOT `CoCreateInstance`. `pv.vt = VT_BLOB(65)`, `blob.cbSize = 12`
(`sizeof(AUDIOCLIENT_ACTIVATION_PARAMS)`) and `blob.pBlobData` pointing **straight at** the params;
the leading-DWORD wrapper (`cbSize=16`) is REFUSED with `0x80070057`. Params =
`{int ActivationType = 1; union { DWORD TargetProcessId; int ProcessLoopbackMode; } }`, mode 0 =
`INCLUDE_TARGET_PROCESS_TREE`. The handler is `IUnknown + ActivateCompleted(op)` (4 vtbl slots) and
the stack QueryInterfaces it for `{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}` ONLY — refuse that one and
the call itself returns `0x8000000E`. `GetMixFormat` is `E_NOTIMPL` on this device, so `Initialize`
with a DECLARED format: float32 48 000 2 ch, `LOOPBACK|AUTOCONVERTPCM` (`0x88020000`), `hns=0`.

## Two defects the lane found in its OWN instrument — one of them had faked a negative

1. **`WAVEFORMATEXTENSIBLE` was declared with a NESTED `WAVEFORMATEX`**, so ctypes padded it to 44
   bytes (real: 40, `SubFormat` at offset 24) and `SubFormat.Data1` was read 4 bytes past the struct.
   A float32 endpoint was therefore reported as int32, the render arm wrote int32 PCM into a float32
   stream, and every sample re-read as ~5e-8 — **digital silence**. That is why an earlier run showed
   "the plumbing works but the positive control is silent". Fixed with a flat declaration and a hard
   ABI gate (`sizeof==40`, `SubFormat@24`, `dwChannelMask@20`, exit 2 on drift).
   **Lesson worth more than the numbers: a mis-declared struct turned a WORKING path into a negative
   control that looked like evidence.**
2. **NEG-B over-claimed.** It asserted "an invalid `TargetProcessId` must be refused"; measured, pid
   `0` IS refused but `0xFFFFFFFE` is ACCEPTED. The API is not fail-closed against garbage pids and no
   shipped contract promises it is, so NEG-B is now a loud DEVIATION that does NOT decide the exit
   code. This is the same weakness the earlier gate recorded; NEGATIVE-A carries the proof.

## Correction to the record: `_main/listen-probe.py` cannot be run today

The lane reported it, and **I measured it myself**: `_main/listen-probe.py:18` is
`import sounddevice as sd`, and in the interpreter every lane uses (`py -3` →
`C:\Program Files\Python311`) `import sounddevice` → `ModuleNotFoundError`. (`numpy` 1.26.4 imports
fine; `comtypes` is also absent.) So the routing-law bullet's "a passive 22 s listen across all of
them peaked at 0.000122 (`_main/listen-probe.py`, verdict `NOTHING-ROUTED`)" is a HISTORICAL
measurement whose instrument is currently undrivable — it must not be cited as a re-runnable one.
That bullet is closed and is not re-litigated here; what is recorded is that its instrument is dead.

## NOT MEASURED

- One PID, one endpoint, one machine, one Windows build (26200). Not proven sample-accurate or
  gapless, not measured against an audiosrv-hosted or protected process, and a child rendering into a
  DIFFERENT endpoint under INCLUDE was not measured. EXCLUDE and ambient readings are informational
  (run 2 saw 0.0385 ambient on `CABLE Input`; runs 3-4 saw exactly 0.0 — unexplained, not load-bearing).
- **The shipped path is not measured end to end**: `worker/sotto_worker.py`'s `ProcessLoopbackTap`
  (`source=proc:<pid>`) uses exactly this activation, so it is sound in principle — but no real
  `proc:<pid>` caption has ever reached the panel (the owner's stop order forbids launching the app).
