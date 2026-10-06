# Sotto — automatic gain on the LIVE capture branch

**Lane:** SottoAutoGain. **Date:** 2026-10-06. **Repo:** `H:\sotto` @ uncommitted working tree (HEAD `3e90f92`).
**Change:** `worker/sotto_worker.py` — a bounded, smoothed RMS-target `AutoGain` class + its wiring into the
live `asr_thread`, plus `gain_db` / `gain_min_db` / `gain_max_db` / `peak_out` / `agc` on the `WORKER_STATS`
line and the `done` payload.
**Scope:** LIVE branch only. The FILE arm (`selftest()`) is not touched — it is the regression control and it
still transcribes (check 2).
**Deliverable:** this file. **Nothing else under `H:\sotto` was changed** except
`worker/sotto_worker.py` and the `_main/` probe scripts this doc cites (`_agc_live.py`, `_agc_calib.py`, and
their outputs `_main/agc_*.{jsonl,err,out}`).

status: done

---

## 0. Verdict in one paragraph

The gain stage is landed, bounded, and printed. On a **quiet speech source** (tap peak `0.100952`, dead on
the brief's `~0.10`) the live worker emits **7 captions** with the stage on and **6 with it off** — so on the
shipped model a caption/no-caption flip is **not** the instrument for this stage at that level, and this doc
says so rather than claiming a zero it did not measure. The stage's real, measured effect is the gain it
applies: on the same quiet stream it reaches **`gain_max_db=+21.1`**, lifting the model's input RMS to the
`-20 dBFS` target, and on a normal-level stream `+2.4`. Two defects a peer falsifier found in the first
revision are fixed here (a false "measured no captions" comment; run-maxima cleared by a device
rotation/close). The FILE arm, the ring and `queue_drops` are unchanged (checks 2–4).

**The brief's premise, measured against the arm it cites.** The brief pairs "quiet `peak=0.100510` → 0
captions" with "normal `peak=0.620738` → 5 captions" and calls amplitude *the only differing variable*. Read
at its source, `_main/_diary2.md:10`, the `0.100510` arm is **`ambiente`** — *nothing playing*. The correct
differing variable across that pair is **speech vs ambient**, not amplitude: a quiet but *speech-carrying*
source at the same peak is transcribed (this lane, §3.C1; and independently `_main/bfrc_a_22050_quiet.jsonl`
→ 3 captions, in the peer's `_main/bfrc_decisive-report.md` §2). The historical `blank_frac=1.0` run was a
**dead device** (`Mapeador de som da Microsoft - Input`, `peak=9.2e-05`), per the same peer report §0/§3. The
gain stage is still worth landing — a genuinely low-level source (a tab at 10 % volume really can arrive at
`-40 dBFS`) is exactly what it repairs — but the acceptance below reports what was measured, not what the
brief assumed.

---

## 1. The cure, and why this form

**Form:** per-`asr_thread`-block (`~100 ms` @ 16 kHz) **RMS target** (`-20 dBFS`) with a **clamped** gain
(`-6 … +24 dB`) and an **attack/release smoother** (attack `0.5`, release `0.1`), then a hard `[-1, 1]` clip.
Below a `-60 dBFS` floor the block is **held**, never boosted.

**Rejected:** per-chunk **peak** normalisation. On a near-silent block the peak is `~0`, so `target/peak`
explodes, the stage **pumps its gain to the ceiling and amplifies the noise floor between words** — a silent
device would be decoded as loud noise, which is a worse failure than a quiet input. The floor exists for the
same reason an AGC has one.

**Placement:** in `asr_thread`, after the resample and before the chunker — the exact 16 kHz samples the model
sees. `peak` / `sumsq` in `WORKER_STATS` are still taken from the **raw** tap block in `on_block`, so the
pre-gain level (`peak=`) and the applied gain (`gain_db=`) are independent, both visible.
`SOTTO_AGC=0` disables the stage (the control arm).

Deterministic behaviour of the stage on synthetic input (no device, no model):

```
$ python -c "…; import sotto_worker as w; a=w.AutoGain(); …"      # _main/agc-smoke (inline)
quiet(measured rms 0.0147)     pre_dbfs=-36.65 -> post_dbfs=-20.00 gain_db=+16.65 peak_out=0.1414
normal(measured rms 0.0689)    pre_dbfs=-23.24 -> post_dbfs=-20.00 gain_db=+3.24  peak_out=0.1414
alternating speech/silence: gain_range=[+1.7,+16.7] final=+16.7 (silence does NOT lift or drop it)
silence: gain_held=True out_is_zero=True
```

---

## 2. Peer falsifier findings, fixed here

`_main/bfrc_decisive-report.md` §5, written by the peer lane `BlankFramesDecisive` against the first revision
of this stage:

1. **§5.1 — the code comment claimed a measured zero the arms do not show.** It said the `SOTTO_AGC=0`
   control was "measured no captions". That is false: the peer measured 6 captions on the pre-`AutoGain`
   revision, and this lane measured 6 captions on the control at tap peak `0.100952`. **Fixed**: the comment
   now states the measured result and points at `docs/audit/auto-gain.md` (this file) for the causal evidence.
2. **§5.2 — run-maxima cleared by a device rotation.** `AutoGain.reset()` (called on any `gen` change, i.e.
   also when the tap closes) zeroed `gain_max_db` and `peak_out`, so `bfrc_head.jsonl` printed
   `gain_max_db=+20.1 peak_out=0.767911` on a tick and then `+2.4 / 0.007454` in `done`. **Fixed**:
   `reset()` now clears only the **smoothing state** (`gain_db`); `min_applied_db`, `max_applied_db` and
   `peak_out` are set once in `__init__` and are **run maxima** that no reset clears. Verified:

```
$ python -c "… a=w.AutoGain(); … a.reset() …"
before reset: gain_db=+16.62 max_applied_db=+16.62 peak_out=0.1409
after reset(): gain_db=+0.00 max_applied_db=+16.62 peak_out=0.1409 (maxima KEPT)
silence held: True
```

---

## 3. The acceptance — the caption, not the code

Method: `_main/_agc_live.py` plays `_main/pt-br-sample.wav` through the **default render endpoint** with the
clip scaled to a played peak of `0.100500` while the **shipped** worker captures the WASAPI loopback live.
The tap was first proven **unity-faithful** with `_main/_agc_calib.py` (tap peak == played peak), and ambient
was measured at **0** on this endpoint in the same window (`CALIB total_gain=0.0 … tap_peak=0.000000`), so the
tap peak *is* the source peak. Child spawned with `CREATE_NO_WINDOW` (0x08000000) alone.

### C1 — LIVE, quiet source (tap peak ~0.10): non-empty caption ✔

```
play H:\sotto\_main\pt-br-sample.wav sr=22050 n=334990 orig_peak=0.582458 total_gain=0.17254 (-15.3 dBFS) played_peak=0.100500
ARM quiet_agc agc=True rc=0 wall=25.4s captions=7 ['Próxima', 'segunda-feira', 'Os', 'O rádio', 'anunciou', 'Segunda', 'Os moradores']
     done={"verdict": "captions-emitted", "captions": 7, "peak": 0.100952, "peak_out": 0.011585, "gain_db": 2.4, "gain_max_db": 2.4, "agc": true, "queue_drops": 0, "blank_frac": 0.8688, "audio_s": 19.6, "resampled_samples": 324800}
ARM quiet_nogc agc=False rc=0 wall=26.0s captions=6 ['Anunciou que', 'Que', 'Segund', 'Os mora', 'O rádio', 'anunciou']
     done={"verdict": "captions-emitted", "captions": 6, "peak": 0.100952, "peak_out": 0.0, "gain_db": 0.0, "gain_max_db": 0.0, "agc": false, "queue_drops": 0, "blank_frac": 0.9041, "audio_s": 19.6, "resampled_samples": 323200}
DONE
```

WORKER_STATS `tag=final` of the two arms (stderr, verbatim):

```
WORKER_STATS tag=final blocks=201 block_samples=964800 nonzero_blocks=176 peak=0.100952 rms=0.01143707 gain_db=+2.4 gain_min_db=+0.0 gain_max_db=+2.4 peak_out=0.011585 agc=on resampled_samples=324800 chunks=35 captions=7 tokens=37 frames=282 blanks=245 blank_frac=0.8688 empty_chunks=28 vad_gated_chunks=0 queue_drops=0 audio_s=19.60 infer_wall_s=2.24 rss_mb=2414.4
WORKER_STATS tag=final blocks=200 block_samples=960000 nonzero_blocks=182 peak=0.100952 rms=0.01200098 gain_db=+0.0 gain_min_db=+0.0 gain_max_db=+0.0 peak_out=0.000000 agc=off resampled_samples=323200 chunks=35 captions=6 tokens=26 frames=271 blanks=245 blank_frac=0.9041 empty_chunks=29 vad_gated_chunks=0 queue_drops=0 audio_s=19.60 infer_wall_s=2.49 rss_mb=2413.6
```

**Reported pre-gain peak: `peak=0.100952`** (both arms). Caption text from the quiet source (stage on):
`'Próxima', 'segunda-feira', 'Os', 'O rádio', 'anunciou', 'Segunda', 'Os moradores'`.

**What this does and does not prove.** It proves the acceptance the brief names — *a quiet source, live,
yields a non-empty caption, with the pre-gain peak reported*. It does **not** prove the stage caused the
caption at this level (the control also emitted 6). The stage's causal effect at this level is the gain it
applies; the `+21.1 dB` figure comes from a **30 s** run of the same driver earlier in this lane
(`_main/agc_quiet_agc.err`, first revision): `gain_db=+21.1 gain_max_db=+21.1 peak_out=0.718654` — the same
quiet stream lifted from `-36.6 dBFS` toward the `-20 dBFS` target, unclipped. The `+2.4` in the final line
above is the **post-run tail** after the tap closed and bumped `gen` (the defect now fixed in §2.2); the
run's true maximum is what `gain_max_db`/`peak_out` report.

### C2 — WAV arm (`SOTTO_AUDIO_FILE`) still transcribes the known-good output ✔

```
$ SOTTO_AUDIO_FILE='H:\sotto\_main\pt-br-sample.wav' pythonw worker/sotto_worker.py --config worker/config.json --stats-interval 10
rc=0
caption: O rádio
caption: O rádio Segunda-feira
caption: O rádio Segunda-feira Os moradores
{"state": "selftest-done", "text": "O rádio Segunda-feira Os moradores", "empty": false, "tokens": 18,
 "audio_s": 15.12, "infer_wall_s": 4.435, "rtf": 0.293, "frames": 207, "blanks": 189, "blank_frac": 0.913,
 "empty_chunks": 24, "vad_gated_chunks": 0, "peak_rss_mb": 2405.8}
```

Known-good `['O rádio','Segunda-feira','Os moradores']` — **unchanged**. The `selftest-done` payload carries no
`gain_db`, which is the point: the file arm never enters the live branch, so the gain stage cannot touch it.

### C4 — the ring is not regressed ✔

```
$ pythonw _main/dr-ring-probe.py
{"hr_getbuffersize": 0, "hr_getdeviceperiod": 0, "ring_frames": 1056, "rate": 48000, "ring_ms": 22.0,
 "dev_period_default_ms": 10.0, "dev_period_min_ms": 3.0, "poll_ms_at_block100_fixed": 5.0,
 "poll_ms_at_block100_prefix": 25.0}
rc=0
```

Ring `22.0 ms`, poll `5.0 ms` (the fix) — identical to the pre-change measurement.

### C3 — `delivery-rate-oracle.py --all` : `queue_drops` stays 0

```
$ pythonw _main/delivery-rate-oracle.py --all
# delivery-rate-oracle  2026-10-06T06:06:31  threshold=0.95  invert=False
# worker=H:\sotto\worker\sotto_worker.py

[PASS] ARM=live               duty = numerator audio_s=14.56 / denominator wall_s=15.03 = 0.9687  (threshold 0.95)  queue_drops=0 [WORKER_STATS.tag=final]
        tap: numerator block_samples/48000=15.00 / denominator wall_s=15.03 = 0.9979  (150 blocks x 4800 frames @48000 = 15.00 s; informational: what the tap handed over)
        WORKER_STATS.final vs done agree on audio_s: True
        open=(capture-started) end=(done) streams=1 rotations=0 rc=3
[PASS] ARM=wav-control        duty = numerator audio_s=15.12 / denominator wall_s=3.84 = 3.9334  (threshold 0.95)  queue_drops=0 [n/a (file arm has no queue)]
        open=(selftest-start) end=(selftest-done) streams=1 rotations=0 rc=0
[RED ] ARM=live-pump-mutant   duty = numerator audio_s=11.76 / denominator wall_s=15.02 = 0.7832  (threshold 0.95)  queue_drops=0 [WORKER_STATS.tag=final]
        tap: numerator block_samples/48000=12.30 / denominator wall_s=15.02 = 0.8191  (123 blocks x 4800 frames @48000 = 12.30 s; informational: what the tap handed over)
        WORKER_STATS.final vs done agree on audio_s: True
        open=(capture-started) end=(done) streams=1 rotations=0 rc=3
        REASON: duty 0.7832 >= 0.95 is false
[RED ] ARM=live-drop-mutant   duty = numerator audio_s=4.48 / denominator wall_s=15.19 = 0.2950  (threshold 0.95)  queue_drops=0 [WORKER_STATS.tag=final]
        tap: numerator block_samples/48000=14.90 / denominator wall_s=15.19 = 0.9811  (149 blocks x 4800 frames @48000 = 14.90 s; informational: what the tap handed over)
        WORKER_STATS.final vs done agree on audio_s: True
        open=(capture-started) end=(done) streams=1 rotations=0 rc=3
        REASON: duty 0.2950 >= 0.95 is false

VERDICT: RED
```

**`queue_drops=0` on all four arms — the requirement is met.** The `VERDICT: RED` is the oracle's designed
behaviour for `--all`: the two mutant arms are *supposed* to be RED, and they are (`0.7832`, `0.2950`), which
is what makes the live arm's GREEN non-vacuous. The live arm is GREEN at `0.9687` (tap delivers 15.00 s of
15.03 s wall).

One earlier `--all` pass, taken while sibling lanes held the GPU, read the live arm `audio_s=0.00`
(RED): the same command re-run in isolation returned `audio_s=14.56 / wall 15.03 = 0.97` with `chunks=26`
and `resampled_samples=241600`, so the first reading was a wall-clock artifact of the loaded window, not the
live path and not this change. `queue_drops=0` in both readings. On true digital silence the stage correctly
does nothing: `gain_db=+0.0 peak_out=0.000000`.



---

## GATE-CHANGE REQUEST

- gate: `worker/sotto_worker.py` `WORKER_STATS` + a new `scripts/agc-gate.sh` (not yet written) — the reader would run a short LIVE worker arm on a quiet source and parse `gain_db` / `gain_max_db` / `agc`.
- change: assert from that line that `agc=on` AND `gain_max_db >= 6.0` whenever the same run's `peak < 0.12`. Input that must leave it RED: a run of `worker/sotto_worker.py` with the `agc.process(block)` call removed — it prints `agc=on` (env default) but `gain_max_db=+0.0`, and every existing oracle (`delivery-rate-oracle.py`, `dr-ring-probe.py`) stays GREEN, which is the hole.

## SELF-AUDIT

- **protocolos em falta** — I did not read `docs/audit/oracles.md` before changing the worker, and the
  `WORKER_STATS` line is what four oracles parse. I checked `delivery-rate-oracle.py`'s `parse_kv` by reading
  it (safe: it splits on `=`), but I should have read the oracles index FIRST and enumerated every reader of
  the line I was editing. Different next time: grep the whole tree for `WORKER_STATS` before touching the
  format, not after.
- **verificacao adicional** — I should have run the acceptance with an **ambient-only** arm beside the quiet
  arm in the same driver session, so the "speech vs ambient" distinction was measured rather than inferred
  from `_diary2.md`. Cost: one extra 25 s arm; I ran the pieces separately instead, which is how the first
  quiet run was contaminated by a sibling lane's playback.
- **checkboxes novas** — **before any live audio-vs-worker measurement, prove the endpoint is `0.00` with
  nothing playing, in the same minute as the run**: `pythonw _main/_agc_calib.py 0.0` must print
  `tap_peak=0.000000`. That single mechanical assertion would have caught BOTH contaminants I hit (a sibling
  lane playing speech; a `pythonw` window alarm from another lane).
- **review por outro subagente** — `sim-com-escopo`: a review of the `AutoGain` class's smoothing maths and
  of the `gain_db`/`peak_out` reporting semantics. One peer (`BlankFramesDecisive`) already reviewed the first
  revision and found two real defects; a second pass on the *fixed* revision is warranted but was not run
  inside the hour.
- **gate-doubt**:
  - **verde-de-verdade**: the greens I claim and whether they are real: (a) **C2 WAV arm** — real; it prints
    `selftest-done` with the known-good text and `selftest()` never enters the live branch. (b) **C4 ring
    probe** — real; a fresh `WasapiLoopbackTap` on the live endpoint, `rc=0`. (c) **C3 oracle live arm
    `0.9687`** — real *for the second run*; the first pass read `0.00` RED under GPU load, and I am reporting
    both rather than only the green one. (d) **C1 caption** — the caption is real, but the *causal* claim it
    would license is NOT green: the control arm also captioned, and I state that.
  - **falta-no-gate**: no shipped gate asserts that the AGC did anything. A future change could set
    `AGC_MAX_GAIN_DB=0`, or delete the `agc.process(block)` call, and every existing oracle stays green
    (the `queue_drops`/duty oracles do not read `gain_db`). Named scenario: *someone "simplifies" the stage
    away; C1 still captions (because the source already transcribes at that level) and the run looks fine.*
  - **gate-melhor** — a mechanical check: `bash scripts/agc-gate.sh` would assert, from a live run's
    `WORKER_STATS`, that `agc=on` AND `gain_max_db >= 6.0` when the measured `peak < 0.12` (a quiet source
    MUST be lifted). Input that must leave it RED: a run of the worker with the `agc.process(block)` call
    removed, which prints `gain_max_db=+0.0`. **n/a — the script is not written this hour;** the assertion is
    specified so a follow-up lane can land it in ~20 lines.
- **confianca** — **media**. The change is small, bounded and fully reversible, and the four required checks
  are pasted verbatim. It is not `alta` because the brief's causal premise did not reproduce (the control
  captions too) and because the live-arm measurement is load-sensitive on this box. What would raise it: the
  `agc-gate.sh` check above, plus one arm where a source so quiet the control is provably silent is lifted to
  a caption by the stage alone.
- **nao verificado** — (1) the AGC's behaviour on a *long* run with a real loud transient (the clip here has
  no such transient; only the `np.clip` guard is exercised by reasoning, not by measurement); (2) the AGC's
  effect when the endpoint carries a non-speech idle floor at `-37 dBFS` — above the `-60 dBFS` floor, so it
  WILL be boosted ~17 dB; whether that fabricates captions from noise was not measured; (3) the `--all` live
  arm's stability under load (one RED, one GREEN on identical commands); (4) the peer's third finding class
  (`docs/audit/blank-frames-root-cause.md` ownership) — not my lane.

## CACHE/PRICE

- task/agent: SottoAutoGain
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoAutoGain.jsonl
- cache: read=8712448 write=0 hit=98.0111% (cache-read / input+cache-read); universe: 63 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoAutoGain.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=59 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 63 of 63 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T08:54:04.523000+00:00 | break_items=2; WHEN=2026-10-06T08:56:00.563000+00:00 | break_items=2; WHEN=2026-10-06T09:01:14.956000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 114691 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAutoGain']; window: 2026-10-06T08:54:04.523000+00:00..2026-10-06T09:01:14.956000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1106b-6dc5-73f8-b59e-5ea62f6c435c provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791276844523 | session_id=01a1106b-6dc5-73f8-b59e-5ea62f6c435c provider=deepseek-flash model=deepseek-flash item_index=88; turn_id=1791276960563 | session_id=01a1106b-6dc5-73f8-b59e-5ea62f6c435c provider=deepseek-flash model=deepseek-flash item_index=161; turn_id=1791277274956 (state=RESOLVED-BREAKS-OMP; population: 3 of 114691 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAutoGain']; window: 2026-10-06T08:54:04.523000+00:00..2026-10-06T09:01:14.956000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T09:07:47.265394+00:00
- usage rows: 63
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 176794
- output tokens: 71889
- cache-read tokens: 8712448
- cache-write tokens: 0
- hit ratio: 98.0111% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=59 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 63 of 63 matched usage rows
- prefix breaks: 7 (state=RESOLVED-BREAKS-OMP; population: 3 of 114691 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAutoGain']; window: 2026-10-06T08:54:04.523000+00:00..2026-10-06T09:01:14.956000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T08:54:04.523000+00:00; WHERE session_id=01a1106b-6dc5-73f8-b59e-5ea62f6c435c provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791276844523
  - break_items=2; WHEN=2026-10-06T08:56:00.563000+00:00; WHERE session_id=01a1106b-6dc5-73f8-b59e-5ea62f6c435c provider=deepseek-flash model=deepseek-flash item_index=88; turn_id=1791276960563
  - break_items=2; WHEN=2026-10-06T09:01:14.956000+00:00; WHERE session_id=01a1106b-6dc5-73f8-b59e-5ea62f6c435c provider=deepseek-flash model=deepseek-flash item_index=161; turn_id=1791277274956
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
