# 12 — The audio-level contract: what the panel can receive, and whether it arrives

**Question (ONE):** what audio-level datum can the panel receive — which field, from where, at what cadence, over what range — **and does it reach the panel through the bridge?**
**Answer: the field is `peak`** (linear sample peak, 0.0–1.0, mono; not dB, not RMS). It is published **only on STDERR, every 10 s**, and it is **DROPPED in the shell**: `window.sotto` never carries it. The panel already has the row and the key list; the shell has no `getStats()`.

`MEASURED` = a command here produced it · `READ` = source read, file+line · `UNKNOWN` = nobody has shown it. Revisions: `worker/sotto_worker.py` 223 237 B, mtime 2026-10-07 05:17:08, sha256 `1662C251…` · `app/webview/sotto_webview.py` 239 421 B, 05:18:37, `1B93F178…` · `app/panel/panel.js` 90 235 B, 09:15:15, `7AEC7459…`.
**No audio device was opened and the worker was NOT run** (the owner's worker, pid 29008, holds one) — this is code + log reading only.
`panel.js` **moved while this lane ran** (another lane owns it): 90 235 B / 09:15:15 / `7AEC7459…` → 90 252 B / 09:59:16 / `B002B7C1…`. Every `panel.js` line cited below was **re-checked against the NEW revision and is unchanged**: `:104`, `:1529`, `:1574`, `:1586`. `sotto_worker.py` and `sotto_webview.py` did not move.

## 1. The field, its range, and how many levels there are

- **The field is `peak`.** `READ` `sotto_worker.py:3327` `p = float(abs(block).max())` — the loudest SINGLE SAMPLE of one block: **linear amplitude 0.0–1.0, NOT dB, NOT RMS**.
- **Range, MEASURED over the owner's own logs:** 118 `WORKER_STATS … peak=` samples in `_main/webview-run.log` span **9.2e-05 … 0.656258**; 131 `"peak"` samples across all 59 `worker/runs/*.jsonl` span **0.0 … 0.738586** (regex over both; counts as stated).
- **`peak` is a RUN MAXIMUM, not a window value.** `READ` `:3328` — only ever raised. MEASURED proof: three consecutive ticks on `_main/webview-run.log:498` all print **`peak=0.554093`** while `rms` drifts 0.06100197 → 0.06181468 — a wave drawn from it can only go up.
- **Other level fields, same stderr line:** `rms` (linear, also cumulative — `:3285`), `peak_out` (post-AGC run max, `:1260`), `gain_db`/`gain_min_db`/`gain_max_db` (dB); in `status` events `run_peak` and `peak_floor` (= 0.002).
- **More than one level? Not per channel.** `READ` — mono downmix to 16 kHz; no per-channel level exists anywhere. Per BLOCK a level exists (`:3327`) but is never emitted. The only per-window level is `device_peak` (reset per candidate, `:3915`), emitted **only** inside `device-rotated` / `device-exhausted` / `silent-device`.

## 2. The cadence — the number

- **Native block rate 10 Hz.** `READ` `worker/config.json:6` `"block_ms": 100`, read at `:3146`, given to the tap at `:3852`.
- **Published cadence 0.1 Hz.** `READ` `:2773` `--stats-interval` default **10.0 s**; the tick fires at `:3926-3928` (`err(stats_line("tick"))`).
- **MEASURED:** on `_main/webview-run.log:498`, consecutive ticks differ by **Δblocks 101 and 100** (× 100 ms = **10.0–10.1 s**), Δ`audio_s` **10.64 / 11.20 s**.
- **So the panel gets 1 point per 10 s today** — and it is the run's high-water mark. A real wave needs **10 points/s**, which is exactly the worker's block rate.

## 3. Does it reach the panel? NO — it is dropped in the shell

- Two channels, two shapes: `READ` `:374` `emit()` = JSON on **stdout**; `:380` `err()` = plain text on **stderr**. The periodic level takes `err(...)` at `:3927`.
- **stderr is parsed and then discarded.** `READ` `sotto_webview.py:4060-4077` — the stderr branch builds `self.last_worker_stats` (`:4071`) and then **`continue`s**, so it never enters `_consume`. Its only two readers are the watchdog (`_note_progress`, `:4224`) and the **text dump** (`snapshot()` `:3868` → `workerStats` in `_main/panel-state.json`, `:3890`). The page cannot read a file.
- **stdout `peak` reaches shell memory, then is dropped.** `READ` `:4123-4135` — kept in `self.last_device_status` **only when `message.get('device')` is truthy** (`capture-started`, `silent-device`, `music-only-capture`, `no-speech-in-capture`, `device-exhausted`) — never periodically. Then `:4183` calls `self._status(text, severity, {'title':…, 'body':…})`, so the rest of the message (`info`, built `:4154`) **is discarded**; `_status` (`:3896`) → `send_status` (`:2545`) → `emit('status', {'text':…, 'kind':…})` (`:2560`) → JS `emit('status', value)` (`:1159`) carries **text and kind only**.
- **The panel is already built for it and waits.** `READ` `panel.js:104` `const bridge = window.sotto;`; `:1574` `wireStatsSource()` returns immediately because neither `bridge.getStats` nor `bridge.onStats` is a function; `:1586` already whitelists **`'peak'` and `'blocks'`**; `:1529` already paints `#hud-peak` from `stats.peak`.
- **THE EXACT LINE THAT WOULD HAVE TO CHANGE:** the injected bridge object **`window.sotto`** in `app/webview/sotto_webview.py` **`:1147`–`:1219`** — it defines `getInfo` (`:1178`), `onCaption`, `onStatus`, `history.*` and has **no `getStats`/`onStats` member**. One member returning `self.last_worker_stats` (served like the `'info'` round trip at `:1689`) is the whole shell-side change. **`panel.js` needs no change at all** — that is what the `:1586` key list is for.

## 4. Real evidence that the values arrive — not just that the code has the field

- `_main/webview-run.log:4656` — `"WORKER_STATS tag=tick blocks=35 block_samples=168000 nonzero_blocks=33 peak=0.436974 rms=0.06090129 gain_db=+5.0 … peak_out=0.751897 … audio_s=3.36"`
- `_main/webview-run.log:13251` — digital silence: `"WORKER_STATS tag=tick blocks=120 block_samples=192000 nonzero_blocks=0 peak=0.000092 rms=0.00002148 … audio_s=11.20"`
- `worker/runs/gate-live-speech.jsonl:22` — a `done` **stdout status** carrying `"peak": 0.418693, "peak_out": 0.827263, "gain_db": 4.6` (16.24 s of speech, 13 captions).
- `worker/runs/gate-live-silence.jsonl:9` — `{"type": "status", "state": "device-rotated", … "peak": 0.0, "run_peak": 0.0, …}`; `:11` — `"state": "silent-device" … "peak": 9.2e-05, "peak_floor": 0.002`.

## 5. What is missing before a wave can be drawn

1. **A per-window (or per-block) level in the STDOUT contract — it does not exist today.** Both published figures are run-cumulative, so a wave drawn from them is monotone, i.e. decorative. Cheapest honest shape: the worker already computes `p` per block at `:3327`; a `peak_window` reset each tick, or a 10 Hz `meter` event, is the missing datum.
2. **Cadence: `--stats-interval` must fall from 10 s to ~0.1 s** for the tick channel to carry a wave — but that line is ~600 B, so 10 Hz ≈ **6 KB/s on a channel that is a diagnostic today**, and the stdout pump is the ONE channel that also carries captions. A separate, smaller event is the alternative; that is a design decision, not a measurement.
3. **History in the panel: yes, and none exists** — there is no level ring buffer in `panel.js`. **Suggested N = 128** at 10 Hz = **12.8 s** of visible wave: a power of two, ~1 KB of floats, and the smallest ring that shows speech rhythm rather than a twitch (300 if a 30 s window is wanted).
4. **Smoothing is required, not optional.** A raw per-block sample peak at 10 Hz is spiky; standard meter behaviour — instant attack, ~150–250 ms release/EMA — is what makes it legible.
5. **Do not mistake the existing meter for this.** `panel.css:1460-1474` `.chrome__meter` is five 2.5 px bars driven by a pure CSS `@keyframes sotto-2-meter 0.9s … infinite` (`themes/theme-2.css:674-698`, staggered by `animation-delay`). It animates identically on speech, silence and a dead worker. **It is exactly the invented wave the owner forbade.**
