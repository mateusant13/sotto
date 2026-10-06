

## 2026-10-06 04:55Z — FRAGMENTS ARE JOINED, AND THE TAP CONTRADICTION IS RESOLVED

### (b) The device contradiction, measured both arms in the same minute
| arm | device the worker opened | result |
|---|---|---|
| worker ALONE (reads `worker/config.json`) | `CABLE Output (VB-Audio Virtual Cable)` | `nonzero_blocks=0 peak=0.000031 captions=0` — silence |
| via the bridge (`--with-worker`) | `Mapeador de som da Microsoft - Input` | **29 captions with text** |

Cause, one line: `app/electron/worker-bridge.js:67` hardcodes
`DEFAULT_AUDIO_DEVICE = 'Mapeador de som da Microsoft - Input'` and line 381 forces it
into the child env as `SOTTO_AUDIO_DEVICE`, so `worker/config.json` is IGNORED whenever
the shell launches the worker. **Neither name is stable** — which device carries the
audio flips with the owner's routing. That is the case for runtime tap resolution, and
lane `SottoAdaptiveTap` owns it (dispatched 04:53Z via `agent()` inside `eval`; the
`task` tool is retired on this box and returns 0 lanes).

### (c) Fragment joining — DONE and proven (`app/electron/panel.js`)
The model emits 1-2 words per hop, so the raw stream read "checked / has / under / o".
`ingestFragment()` now accumulates and `flushPhrase()` emits ONE line when the phrase
closes: terminal punctuation, a silence gap > 1200 ms, or the 6000 ms / 90-char cap.
Nothing is invented — a line is the fragments concatenated in arrival order.

Oracle: `_main/join-harness.js` runs the REAL extracted source text of those functions
with a stubbed clock and a recording `addCaption` (5 arms, rc=0):
    PASS arm1 closes as one 12-word line
    PASS arm1 negative control: not 12 lines      <-- RED if the join were absent
    PASS arm2 gap closes the phrase / tail held then flushed
    PASS arm3 terminal punctuation closes immediately / tail flushed
    PASS arm4 empty and whitespace fragments ignored
    PASS arm5 length cap closes a run-on; no line exceeds the cap
    JOIN-HARNESS: PASS (5 arms)
First run of this harness was 3-FAILED and the faults were the TEST's expectations
(the 12x560 ms arm closes as ONE line at the cap; arm 3 inherited arm 2's un-flushed
tail, which is correct by design). The arms were corrected and the negative control
added; the code was not changed to make a wrong expectation pass.

END TO END, live shell, pid 23484, `--with-worker`, 45 s:
    HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true
    raw BRIDGE_CAPTION fragments: 38  ->  CAPTION_APPLIED rendered lines: 9
    "how t how t n t s how ' se they make in they actually"
    "for i b co se s dly do"
    errors: [] (zero)

### What is still NOT proven
- The TEXT is still garbled ("le flo how t", "for i b co se s dly do"). That is the
  MODEL's accuracy on this audio (nemotron-3.5-asr-streaming-0.6b-int4), not the join:
  the join only groups what the model produced. The `int4` vs `FP16` question that
  worker/README.md leaves open is now the top accuracy candidate.
- The owner pressing Alt+C has still never been observed: registration is proven, the
  toggle is not (pressing keys on his desktop is not something Main may do).
- Runtime tap resolution is IN FLIGHT (lane SottoAdaptiveTap), not landed.
