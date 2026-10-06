

## 2026-10-06 05:09Z — TAP ROTATION LANDED, AND A REGRESSION MY OWN JOIN INTRODUCED IS FIXED

### Runtime tap resolution (lane SottoAdaptiveTap — verified, not taken on trust)
Lane artifact `H:/sotto/worker/runs/adaptive-tap-acceptance.log`; files `worker/sotto_worker.py`,
`app/electron/worker-bridge.js`. Independent checks I ran:
- `node --check app/electron/worker-bridge.js` -> **rc=0**.
- Live shell: `BRIDGE_START ... device=auto` (the bridge no longer forces a device) and
  `HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true`.
- Worker alone, 14 s, from `H:/sotto`: settled on attempt 1 of 6 with
  `"device": "CABLE Output (VB-Audio Virtual Cable)"`, `peak=0.500031`, `captions=2`,
  verdict `captions-emitted` — so the ordered candidate list picks a live tap and the
  rotation was not needed on this run.
- Rotation/exhaustion branch forced by the lane (`--tap-window 2 --tap-peak-floor 99`):
  `device-rotated` x5 then `device-exhausted reason=all-flat` with the tried list, peak
  0.485291, captions 0 — the bounded-window branch is exercised, not merely present.
LIMIT: I verified the branch in the LANE's log; I did not re-run the forced exhaustion
myself. Two logs, one command each, both on disk.

### Regression MY join introduced, measured and fixed
The first live run after the join showed `text="g"`, `"gen"`, `"s"` in the log with
**0 `CAPTION_APPLIED`**: the fragments sat in the join buffer and nothing rendered them,
because no further fragment and no status arrived to trigger a flush. A sparse stream was
invisible to the owner while the log looked healthy — the worst shape of this class.

Fix: `armPhraseTimer()` schedules a flush `PHRASE_GAP_MS` (1200 ms) after each fragment,
so a phrase closes on TIME, not only on the next event. `flushPhrase()` clears the timer.

Oracle `_main/join-harness.js`, **6 arms, rc=0**, all against the REAL extracted source:
    PASS arm1 closes as one 12-word line / negative control: not 12 lines
    PASS arm2 gap closes the phrase / tail held then flushed
    PASS arm3 terminal punctuation closes immediately / tail flushed
    PASS arm4 empty and whitespace fragments ignored
    PASS arm5 length cap closes a run-on; no line exceeds the cap
    PASS arm6 nothing rendered while open / a flush WAS scheduled / timer closed the tail
arm6 is the regression arm: it stubs `setTimeout`, captures the scheduled callback, fires
it with NO further input, and asserts the line appears. Removing the timer makes it RED.

LIVE, after the fix — pid 36144, `--with-worker`, 50 s:
    HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true
    raw fragments: 2  ->  RENDERED lines: 1   ("com s")   errors: []
Before the fix the same sparse shape rendered 0 lines.

### Still not proven
- The owner pressing Alt+C. Registration is proven; the toggle is not — pressing keys on
  his desktop is not something Main may do.
- Text accuracy. The model (nemotron-3.5-asr-streaming-0.6b-int4) emits short, sometimes
  wrong words ("ressconti", "com s"). That is the model, not the plumbing. The int4 vs
  FP16 question that worker/README.md leaves open is the top accuracy candidate.
