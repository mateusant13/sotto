# receipt — 12 audio-level contract (ONE question: can the panel get a real audio level?)

1. **What was asked:** the ONE question that decides whether a "onda de audio no painel" is real or
   decorative — which level field exists, from where, at what cadence, over what range, **and does it
   reach the panel through the bridge**. Deliverable: `docs\research\12-audio-level-contract.md`
   (written, **45 lines** ≤ 70). No code was changed anywhere.
2. **Answer, in one line:** the field is **`peak`** (linear sample peak, 0.0–1.0, mono, not dB, not
   RMS), published **only on STDERR every 10 s**, and **dropped in the shell** — `window.sotto` has no
   `getStats()`/`onStats`. The single line that would have to change is the injected bridge object
   **`app/webview/sotto_webview.py:1147–1219`**. `panel.js` needs no change: it already whitelists
   `'peak'`/`'blocks'` (`panel.js:1586`) and already paints `#hud-peak` (`:1529`).
3. **Prohibitions honoured.** **No audio device was opened and the worker was NOT run** — the owner's
   worker (pid 29008) holds an endpoint; this lane is code + log reading only. **Nothing was written
   in `H:\sotto`** (read-only; the panel, which another lane is editing, was only read). Nothing was
   written outside `H:\aireplay`. No process was started, so no kill filter and no window census were
   needed; no visible window was ever created. Budget: ≤2 threads — no compute was run at all.
4. **MEASURED** (commands on this box, no device):
   - File identity, `Get-FileHash` + `Get-Item`: `sotto_worker.py` 223 237 B / mtime 2026-10-07
     05:17:08 / sha256 `1662C251113295D2CF523BF87727E403FAE5D66F0F5FAA3AAB0C029DCB8742AB`;
     `sotto_webview.py` 239 421 B / 05:18:37 / `1B93F178DDCC1670F4EA119E627696649FDEB7C8B642527AF108C93D46220AE3`;
     `panel.js` 90 235 B / 09:15:15 / `7AEC7459ED204DFB84E5E103A03ACAE6FDEB04FECB6EE20E9A833E4363C42410`.
   - **Cadence:** three consecutive `WORKER_STATS tag=tick` entries on `_main\webview-run.log:498`
     give Δblocks **101 / 100** (× `audio_s` deltas **10.64 / 11.20 s**) → **~10 s per tick**, matching
     `--stats-interval` default 10.0 s (`sotto_worker.py:2773`) and `audio.block_ms` 100
     (`worker/config.json:6`) → block rate **10 Hz**.
   - **Value range:** regex over the logs — **118** `WORKER_STATS … peak=` samples in
     `_main\webview-run.log` span **9.2e-05 … 0.656258**; **131** `"peak"` samples across all **59**
     `worker\runs\*.jsonl` span **0.0 … 0.738586**.
   - **`peak` is a run maximum, not a window value:** all three ticks on line 498 print the identical
     `peak=0.554093` while `rms` drifts 0.06100197 → 0.06181468.
5. **READ** (source, with lines): `sotto_worker.py` `:374` `emit` (stdout JSON) vs `:380` `err`
   (stderr text); `:3327` `abs(block).max()`; `:3328` run-max only; `:3285` cumulative `rms`; `:3927`
   `err(stats_line("tick"))`; `:2773` interval; `:3146`/`:3852` block_ms; `:3915` `device_peak`.
   `sotto_webview.py` `:4060-4077` stderr parsed → `continue`; `:4071` `last_worker_stats`; `:4123-4135`
   `peak` kept only when `device` is truthy; `:4154`/`:4183` `info` discarded; `:3896`/`:2545`/`:2560`
   → text+kind only; `:3868`/`:3890` `snapshot()` (dump only). `panel.js` `:104` `bridge =
   window.sotto`; `:1574` early return; `:1586` key list; `:1529` Peak row. `panel.css:1460-1474` +
   `themes/theme-2.css:674-698`: the existing `.chrome__meter` is a **pure CSS `@keyframes`
   animation**, identical on speech, silence and a dead worker — the invented wave the owner forbade.
6. **UNKNOWN, named:** whether a per-block level at 10 Hz can be added to the stdout contract without
   perturbing the single-threaded pump that also carries captions (**not measured** — no worker was
   run); whether the panel's real WebView2 frame budget absorbs a 10 Hz canvas redraw (the 150–300 MB
   question in `AGENTS.md` is still open); and what `peak` looks like for music-only or
   multi-channel sources (all samples here are mono downmix).
7. **Cost of being wrong, stated:** if the wave were drawn from today's `peak`, it would be a
   monotone line that only rises — visually convincing and **not** the audio. That is precisely the
   failure mode the owner's "uma onda inventada é inaceitável" rule forbids.
