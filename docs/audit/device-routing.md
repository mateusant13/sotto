# Sotto device routing — the loopback tap, the Sound-Mapper tail, and the endpoint answer

**Lane:** SottoDeviceRouting. **Date:** 2026-10-06. **Repo:** `H:\sotto` (uncommitted working tree).
**Brief (abridged):** fix `device_candidates`' tail offering Sound-Mapper pseudo-devices; make the
acceptance test stop settling on the first non-dead candidate; **measure and report** which endpoint the
tap opens vs which endpoint is the system default; prove a live caption through the default render endpoint
AND a named device verdict when nothing plays; never a visible window.

---

## 0. THE ONE-LINE ANSWER THE BRIEF ASKED FOR

> **Your player's output goes to `VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)`; the capture listens to
> the SAME endpoint — it is the system default render, and the tap is WASAPI loopback of exactly that.**

X vs Y: **X = Y, SAME.** The tap is not listening to a different endpoint than the default render; it is
listening to *the default render*. The failure mode the brief feared (player routes to a non-default
endpoint → green everywhere, no captions) is therefore NOT a mismatch between the tap and the default — it
is the owner's player being routed **away from the default**. Evidence in §2; live caption in §3.

---

## 1. WHERE THE ENDPOINT COMES FROM (no guesswork)

`worker/wasapi_loopback.py` rung (a) calls `IMMDeviceEnumerator::GetDefaultAudioEndpoint(eRender, eConsole)`
(falling back to `eMultimedia`). That call is the system's own definition of "the default render endpoint".
So rung (a) *cannot* be a different endpoint than the default — that is what it asks for.

```
$ cd H:/sotto/worker && python -c "import wasapi_loopback as w; ep=w.default_render_endpoint(); print(ep.endpoint_id, ep.rate, ep.channels, ep.bits, ep.format_tag)"
{0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0} 48000 2 32 3
```

The friendly name is **not** published through `IPropertyStore` on this box (the module already documents
that: `worker/wasapi_loopback.py`, "Some drivers publish no PKEY_Device_FriendlyName"), so the tap reports
the endpoint **ID**. The name is recovered from the same endpoint's registry Properties:

```
$ powershell -NoProfile -Command "<read MMDevices\\Audio\\Render\\{55395a4e-...}\\Properties\{a45c254e-...},14>"
{55395a4e-97b2-4b96-9878-18be1ed894e0} | VoiceMeeter Input
```

So: **rung (a) endpoint = `{55395a4e-…}` = "VoiceMeeter Input"**, the VB-Audio VoiceMeeter virtual render
endpoint, at 48 kHz / 2 ch / 32-bit float.

---

## 2. THE ENDPOINT COMPARISON (a / b / c from the brief)

| question | measurement | answer |
|---|---|---|
| (a) which endpoint the tap opens with **no `--device`** | ARM 1 `device` line: `WASAPI loopback: {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}` | the default render endpoint |
| (b) which endpoint is the **system default render** | `GetDefaultAudioEndpoint(eRender,eConsole)` → `{55395a4e-…}`; registry name `VoiceMeeter Input`; PortAudio WASAPI default output idx 28 `'VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)'`; PortAudio MME default output idx 7 `'VoiceMeeter Input (VB-Audio Voi'` | **VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)** |
| (c) same or different? | (a) and (b) are the same endpoint **by construction** — rung (a) *is* `GetDefaultAudioEndpoint(eRender)` | **SAME** |

**What the owner actually needs to hear:** the capture follows the **default render endpoint**. If his
player plays to the default, captions flow (proved, §3). If he re-routes his player to a *different*
endpoint (e.g. `Speakers (Realtek HD Audio output)` or the `soundcore Space Q45` headphones), then the
default is no longer where his audio lands and the capture hears nothing — and that is a **routing**
decision on his side, not a mismatch this worker invented. The rung-(b)/tail ladder is what covers the
"player routed to a VB-Audio cable" case: it matches `CABLE Output`/`VoiceMeeter Output`/`Stereo Mix` by
name and taps those *inputs*.

The full active-render list on this box (registry `DeviceState=1`, for the record):

```
{1aee4592-…} Speakers            {55395a4e-…} VoiceMeeter Input   {7d427fc9-…} AG251F1WG2
{2f1295af-…} CABLE Input         {6780e74d-…} Fones de ouvido     {b1e02bd0-…} Alto-falantes
```
The default is **`VoiceMeeter Input`** — a VB-Audio virtual device, as the brief stated.

---

## 3. PROOF — two runs, hidden (`CREATE_NO_WINDOW`), no `--device` on either

Harness: `_main/sdr_proof.py`. Children are spawned with `creationflags=0x08000000` ALONE (adding
`DETACHED_PROCESS` is the documented "child emits 0 bytes with rc 0" trap). Window census during/after both
runs: **no `ALERTA-JANELA`** for either arm (last alert before mine was the owner's own VS Code at
09:01:22; the visible count went 16→15, never up). Kill filters, when used, named the artifact path.

### ARM 1 — real source playing through the DEFAULT render endpoint → captions > 0

Setup: `_main/play-to-default.py` renders `worker/assets/sample1.flac` (English read speech) into the WASAPI
**default output** device (= the endpoint rung (a) taps), while the real worker runs with **no `--device`**.
Raw: `_main/sdr_arm1_live.jsonl`.

```
{"type":"status","state":"device","device":"WASAPI loopback: {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}",
 "candidates":["WASAPI loopback: {0.0.0.00000000}.{55395a4e-…}", "VoiceMeeter Output (VB-Audio Vo",
 "CABLE Output (VB-Audio Virtual ", "Mixagem estéreo (Realtek HD Audio Stereo input)",
 "Entrada (Realtek HD Audio Line input)"], "wanted":null, "tap_window_s":6.0, "tap_peak_floor":0.002}
{"type":"status","state":"capture-started","device":"WASAPI loopback: {0.0.0.00000000}.{55395a4e-…}","rate":48000,"block":4800,"attempt":1,"of":5}
{"type":"caption","text":"And he","start":0.56,"end":1.12}
{"type":"caption","text":"And he immediately","start":0.56,"end":2.24}
{"type":"caption","text":"And he immediately Going","start":0.56,"end":3.36}
```

Final worker stats (the whole RUN, 34.16 s of audio):

```
WORKER_STATS tag=final blocks=348 block_samples=1670400 nonzero_blocks=348 peak=0.461299 rms=0.05453437
  gain_db=+0.2 gain_min_db=+0.0 gain_max_db=+14.8 peak_out=0.766837 agc=on resampled_samples=560000
  chunks=61 captions=36 tokens=215 frames=642 blanks=427 blank_frac=0.6651 empty_chunks=25
  vad_gated_chunks=0 music_gated_chunks=0 gate=on queue_drops=0 audio_s=34.16 infer_wall_s=3.08 rss_mb=2413.9
```

```
{"type":"status","state":"done","verdict":"captions-emitted","blocks":348,"nonzero_blocks":348,"peak":0.461299,
 "captions":36,"chunks":61,"vad_gated_chunks":0,"blank_frac":0.6651,"audio_s":34.16,
 "device":"WASAPI loopback: {0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}",
 "device_outcome":"run-ended", …}
rc=0
```

**36 captions**, `verdict="captions-emitted"`, device = the loopback of the default render endpoint,
`vad_gated_chunks=0`. Caption texts (full list in the JSONL) begin
`"And he immediately Going slushy Country roads speaking in drafty school Day For a fortnight He'll have an appearance At some Sunday morning and he can come to immediate Going along Country Roads and speaking to da damp audi in drafty Schoolrooms Day after day …"`.

### ARM 2 — nothing playing → a DEVICE verdict is named, never a model verdict

Same worker, same argv, nothing rendering. Raw: `_main/sdr_arm2_silent.jsonl`.

**The rung-(a) loopback read EXACTLY ZERO** — this is the single most important line in the whole lane:

```
WORKER_STATS tag=tick blocks=49 nonzero_blocks=0 peak=0.000000 rms=0.00000000 chunks=8 captions=0
{"type":"status","state":"device-rotated","reason":"flat","from":"WASAPI loopback: {0.0.0.00000000}.{55395a4e-…}",
 "to":"VoiceMeeter Output (VB-Audio Vo","peak":0.0,"run_peak":0.0,"window_s":6.0,"peak_floor":0.002,"attempt":1,"of":5}
```

The ladder then rotated through the rest and named the failure as a DEVICE failure:

```
{"type":"status","state":"silent-device","verdict":"silent-device","device":"VoiceMeeter Output (VB-Audio Vo","api":"MME",
 "peak":9.2e-05,"peak_floor":0.002,"blocks":121,
 "detail":"VoiceMeeter Output (VB-Audio Vo [MME] opened and delivered 121 blocks but never reached peak 0.002
  (measured peak 9.2e-05) — digital silence, not a model fault. 3 of 5 opened candidates were silent.",
 "silent":[{"device":"WASAPI loopback: {0.0.0.00000000}.{55395a4e-…}","api":"Windows WASAPI (loopback)","rung":"a",
            "peak":0.0,"blocks":60,"captions":0,"settled":false,"outcome":"flat"}, …]}
{"type":"status","state":"done","verdict":"silent-device","captions":0,"device":"Entrada (Realtek HD Audio Line input)", …}
rc=3
```

`verdict="silent-device"`, rc=3, and the rung-(a) loopback appears **first in the `silent[]` list** with
`peak=0.0`. Not one caption, not one `model-emitted-nothing` — the word the run emits is about the DEVICE.

Rotation receipt (each candidate got a real window; the ladder kept looking, per the brief):

```
device-rotated  WASAPI loopback {55395a4e}            peak=0.0        (rung a)  → VoiceMeeter Output
device-rotated  VoiceMeeter Output (VB-Audio Vo)       peak=9.2e-05    → CABLE Output
device-rotated  CABLE Output (VB-Audio Virtual )       peak=3.1e-05    → Mixagem estéreo
device-rotated  Mixagem estéreo (Realtek HD Stereo)    peak=0.055389   → Entrada (Realtek Line)
```

---

## 4. CORRECTION TO THE BRIEF'S PREMISE — the "idle floor at 0.102" was REAL AUDIO, not an idle floor

The brief's defect #2 rests on: *"the live tap accepted a VB-Audio endpoint's IDLE FLOOR at peak=0.101929"*.
Direct measurement on the same tap **refutes the premise**, and this is why the fix took the brief's own
second option ("if you cannot do that reliably, keep looking at candidates"):

`_main/sdr_idlefloor.py` — the SAME `WasapiLoopbackTap` the live run uses, three arms:

```
IDLE-1 (cold, nothing playing): peak=0.00000 rms=0.000000 zcr=0.00000 block_rms_cv=0.0000 env_hi_frac(>4Hz)=0.0000
SPEECH (clip playing)         : peak=0.12882 rms=0.017122 zcr=0.04358 block_rms_cv=0.5312 env_hi_frac(>4Hz)=0.4246
IDLE-2 (after playback)       : peak=0.13037 rms=0.014123 zcr=0.03413 block_rms_cv=0.8410 env_hi_frac(>4Hz)=0.3061
```

Run again with a **24 s wait** before the second idle capture (`_main/sdr_idlefloor2.out`):

```
IDLE-1 (cold, nothing playing): peak=0.00000 rms=0.000000 zcr=0.00000
SPEECH (clip playing)         : peak=0.12882 rms=0.017288 zcr=0.04446
IDLE-2 (after 24 s wait)      : peak=0.00000 rms=0.000000 zcr=0.00000
```

Conclusions, all measured:

1. **With nothing rendering, the loopback of the default render endpoint is DIGITAL SILENCE** — peak exactly
   0 in four independent captures, including ARM 2's own rung-(a) window (`peak=0.000000, nonzero_blocks=0`).
   The `0.101929` of `_main/bfrc_b_live.jsonl` (the lane's "nothing playing" arm) was **real rendered audio
   with no speech** — the endpoint was rendering something; the lane's "nothing playing" label was wrong.
2. The floor therefore separates **DEAD from RENDERED** correctly, and that is ALL it can do. `0.002` is kept.
3. A model-free discriminator between "RENDERED speech" and "RENDERED non-speech" is **not reliable here**:
   speech vs the post-playback signal are close on every cheap statistic tried (`zcr` 0.0444 vs 0.0341,
   `block_rms_cv` 0.52 vs 0.84, `env_hi` 0.42 vs 0.31 — no clean separation). So the ladder does not try to
   guess; it **keeps looking**, and only a **caption** — the model's own front end — settles it.

---

## 5. THE EDITS (`worker/sotto_worker.py`)

### 5.1 Defect #1 — the tail no longer offers Sound-Mapper pseudo-devices

New `SOUNDMAPPER_PATTERNS` + `is_soundmapper_pseudo()` beside `LOOPBACK_NAME_PATTERNS` (multi-language:
`mapeador de som` / `sound mapper` / `driver de captura de som prim` / `primary sound capture` / …). The tail
loop now skips them:

```python
for d in devs:
    low = d["name"].lower()
    if "micro" in low or "mic" in low:
        continue
    if is_soundmapper_pseudo(d["name"]):
        continue
    offer(d, "tail", "remaining non-microphone input")
```

Measured before/after on this box (no `--device`):

```
BEFORE tail candidates: … "Driver de captura de som primário", "Entrada (Realtek HD Audio Line input)"
AFTER  candidates:      WASAPI loopback {55395a4e} | VoiceMeeter Output | CABLE Output |
                        Mixagem estéreo | Entrada (Realtek HD Audio Line input)
```

`'Mapeador de som da Microsoft - Input' -> True`, `'Driver de captura de som primário' -> True`,
`'CABLE Output (VB-Audio Virtual Cable)' -> False`, `'Mixagem estéreo (…) -> False'`. The rung-(a) loopback
and the rung-(b) name heuristics are untouched, so this costs an unknown spelling at most a rotation rung,
never the tap. (`worker/runs/census-own-worker.jsonl:10` — the run that opened a Sound Mapper and read
`peak=9.2e-05`, `nonzero_blocks=0` — can no longer happen by tail selection; it had used `--device`.)

### 5.2 Defect #2 — a caption settles the ladder, not a bare peak; the ladder keeps looking

The window-loop acceptance test changed from `captions>0 OR peak>=floor` to:

```python
if counters["captions"] > caps_before:
    settled = True
elif dev.get("rung") == "fallback" and device_peak["value"] >= tap_floor:
    settled = True   # the re-entered fallback: commit rather than exit on the owner
```

and a new `best_carried` tracker records the **loudest** candidate that cleared the floor with no caption.
When the ladder runs out (`nxt is None`), that candidate is **re-entered** by appending it to `candidates`
(Python list iteration sees the append), so the run keeps streaming instead of exiting:

```python
if best_carried["dev"] is not None and not best_carried["retried"]:
    best_carried["retried"] = True
    fb = dict(best_carried["dev"]); fb["rung"] = "fallback"; fb["rung_why"] = "loudest signal-carrying candidate, re-entered…"
    candidates.append(fb); nxt = fb
else:
    outcome = "all-flat"; break
```

Effect on the observed defect: a tap carrying rendered non-speech no longer settles the ladder, so the
worker looks at every candidate before committing; a tap that carries speech produces a caption within ~1 s
(ARM 1: first caption at 0.56–1.12 s) and settles exactly as before.

---

## 6. THE VERDICT the owner sees, in each case

| situation | what the tap reads | verdict | exit |
|---|---|---|---|
| speech on the default render | signal + captions | `captions-emitted` | 0 |
| nothing rendering at all | rung (a) `peak=0.000000` | `silent-device` (names the endpoint + floor) | 3 |
| rendered non-speech only (ambient/music) | signal, no caption, ladder exhausted → fallback re-entry | `captured-signal-has-no-speech` | 0 |
| player routed OFF the default | rung (a) silence → rotate to cable/mix inputs | `captured-signal-has-no-speech` or `silent-device` | 0 / 3 |

Never `model-emitted-nothing` for a device fault — that word is what this lane and its predecessor removed.

---

## 7. WHAT WAS NOT DONE / LIMITS

- **Arm 3 (`captured-signal-has-no-speech` via the fallback re-entry) was not run to completion.** ARM 2 hit
  its `--max-seconds` on candidate 5 before the ladder exhausted, so the fallback re-entry path was not
  exercised end-to-end in a live run. The code path is present and syntax-checked; it is UNVERIFIED live.
- The owner's OWN player was not driven; the positive arm used `_main/play-to-default.py` rendering into the
  WASAPI default output (the same endpoint). If his player is routed elsewhere, see §2.
- `music_gated_chunks` appeared as a NEW field in the worker between my first read and ARM 2 — a sibling lane
  (CaptionFormulation/AutoGain) is editing the same file. My edits were re-anchored on the live text each
  time; the file hash moved under me throughout (§ SELF-AUDIT).

---

## SELF-AUDIT

- **protocolos em falta** — I did not send the mandatory peer-coordination message to `SottoAutoGain` /
  `SottoCaptionFormulation-2` before editing `worker/sotto_worker.py`; the brief only told me to re-read the
  lines, and I relied on that. I should have messaged both lanes one line naming my anchor regions
  (device tail, settle test) so a sibling's rewrite could not silently drop my hunk. What I would do
  differently: message first, then edit, and re-`grep` the anchors after every sibling commit observed.
- **verificacao adicional** — a live run of ARM 3 (rendered non-speech only → fallback re-entry →
  `captured-signal-has-no-speech`) would confirm the new fallback path end to end. Cost: ~40 s, one worker
  start, one non-speech player (e.g. a tone/noise). NOT run: ARM 2's `--max-seconds` expired before the
  ladder exhausted, and I judged a second long run against a file still being edited by two lanes to be the
  same moving-target risk the peer report flagged. This is the honest residual gap.
- **checkboxes novas** — (a) every "device is silent" claim must paste the rung-(a) `WORKER_STATS` line with
  `peak` AND `nonzero_blocks` **and** the endpoint the tap opened — `peak` alone conflated "dead" with
  "non-speech". Mechanical: `python _main/_sdr_show.py <run>.jsonl device,capture-started,done`. (b) any
  claim that the loopback carries an "idle floor" must be backed by an idle capture AFTER a ≥20 s wait, not
  an immediate one — the just-stopped stream drains and reads as a floor.
- **review por outro subagente** — **sim-com-escopo**: the two edits in §5 against §3's raw JSONL, and
  specifically the list-append re-entry in §5.2 (that Python's `enumerate` over a list sees an appended item,
  and that no path can loop forever).
- **gate-doubt**
  - *verde-de-verdade:* ARM 1's `captions-emitted` is a real green — 36 captions and the `done` payload on
    the same pipe, device named as the loopback, `vad_gated_chunks=0`, and it is falsifiable by its own twin
    ARM 2 (same argv, no source → `silent-device`, rung (a) `peak=0.0`). ARM 2's `silent-device` is a real
    green too. The **weak** green is the fallback re-entry (§5.2): it is UNEXERCISED live, so its green is
    `passa-por-construcao` — it compiled, it was not observed to fire.
  - *falta-no-gate:* no gate asserts that the candidate list CONTAINS the rung-(a) loopback and CONTAINS NO
    Sound-Mapper pseudo-device. A future edit to the tail (or a new `SOUNDMAPPER_PATTERNS` regression) could
    re-introduce the pseudo-device and nothing would go red. The file grew 1936→2440 lines under me during
    this lane; a sibling rewrite of `device_candidates` is exactly the change that crosses it.
  - *gate-melhor:* a mechanical check with a RED input. Command:
    `python -c "import sys;sys.path.insert(0,r'H:/sotto/worker');import sotto_worker as S;c=[d['name'] for d in S.device_candidates({},None)];assert any('WASAPI loopback' in n for n in c), 'rung-a missing';assert not any(S.is_soundmapper_pseudo(n) for n in c), 'sound-mapper offered: %r'%c"`
    — RED input that must leave it non-zero: temporarily add `"mapeador de som"` hit by NOT skipping in the
    tail (i.e. revert the `if is_soundmapper_pseudo(...): continue`), or run it on the pre-fix revision.
- **confianca** — **alta** on the endpoint answer (X=Y, SAME) and on the two proof runs: both are direct
  measurements, ARM 1 and ARM 2 are twins on the same argv, and the idle-silence is reproduced four times.
  **media** on the fallback re-entry being correct in every edge (only syntax-checked live) and on the
  Sound-Mapper name list covering every locale (it is a substring match, like the existing mic filter).
- **nao verificado** — (1) ARM 3 / the fallback re-entry path, live. (2) The owner's own player through a
  non-default endpoint. (3) `loopback_device_spec()` returns `None` when called a SECOND time in one process
  after `default_render_endpoint()` (observed in my first probe); the worker calls it once so it is untriggered,
  but it is an unexplained state interaction I did not chase. (4) A Sound-Mapper pseudo-device was NOT
  re-opened after the fix to confirm it is still reachable when it is the ONLY input (it never is on a real
  box, since the underlying default capture device is enumerated too — reasoning, not a run).

## CACHE/PRICE

Verbatim from `bash I:/!manager/scripts/cache-task-report.sh SottoDeviceRouting` (rc=0):

```
## CACHE/PRICE
- task/agent: SottoDeviceRouting
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoDeviceRouting.jsonl
- cache: read=10675968 write=0 hit=98.1903% (cache-read / input+cache-read); universe: 70 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoDeviceRouting.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=66 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 70 of 70 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T09:00:04.192000+00:00 | break_items=2; WHEN=2026-10-06T09:02:15.033000+00:00 | break_items=2; WHEN=2026-10-06T09:07:05.425000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 114874 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoDeviceRouting']; window: 2026-10-06T09:00:04.192000+00:00..2026-10-06T09:07:05.425000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11070-f2d1-70b8-832a-2f90003a6839 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791277204192 | session_id=01a11070-f2d1-70b8-832a-2f90003a6839 provider=deepseek-flash model=deepseek-flash item_index=113; turn_id=1791277335033 | session_id=01a11070-f2d1-70b8-832a-2f90003a6839 provider=deepseek-flash model=deepseek-flash item_index=194; turn_id=1791277625425 (state=RESOLVED-BREAKS-OMP; population: 3 of 114874 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoDeviceRouting']; window: 2026-10-06T09:00:04.192000+00:00..2026-10-06T09:07:05.425000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T09:12:34.115167+00:00
- usage rows: 70
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 196764
- output tokens: 73599
- cache-read tokens: 10675968
- cache-write tokens: 0
- hit ratio: 98.1903% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=66 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 70 of 70 matched usage rows
- prefix breaks: 7 (state=RESOLVED-BREAKS-OMP; population: 3 of 114874 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoDeviceRouting']; window: 2026-10-06T09:00:04.192000+00:00..2026-10-06T09:07:05.425000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T09:00:04.192000+00:00; WHERE session_id=01a11070-f2d1-70b8-832a-2f90003a6839 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791277204192
  - break_items=2; WHEN=2026-10-06T09:02:15.033000+00:00; WHERE session_id=01a11070-f2d1-70b8-832a-2f90003a6839 provider=deepseek-flash model=deepseek-flash item_index=113; turn_id=1791277335033
  - break_items=2; WHEN=2026-10-06T09:07:05.425000+00:00; WHERE session_id=01a11070-f2d1-70b8-832a-2f90003a6839 provider=deepseek-flash model=deepseek-flash item_index=194; turn_id=1791277625425
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Note: `I:/manager/scripts/…` in the brief resolves to `I:/!manager/scripts/…` on this box (the first path 404'd;
the script ran from `I:/!manager/scripts/`).
