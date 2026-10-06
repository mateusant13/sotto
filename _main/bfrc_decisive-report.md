# BlankFramesDecisive — decisive experiment, branch, root cause (full receipt)

**Lane:** BlankFramesDecisive. **Date:** 2026-10-06. **Repo:** `H:\sotto`, uncommitted working tree.
**Why this file exists:** `docs/audit/blank-frames-root-cause.md` is the briefed deliverable, but the lane
`BlankFramesRootCause` writes the same path concurrently and had overwritten it once during this run. This is
my own copy, at a path no other lane writes; the shared doc carries a short addendum.

## 0. VERDICT — the branch

**NEITHER branch the brief proposed. "live-only blank" is false; "BOTH blank" is false. The live branch is
FUNCTIONAL and the product's acceptance test PASSES on the shipped revision.**

| arm | source | captions | vad_gated | peak |
|---|---|---|---|---|
| **A** file control | `_main/pt-br-sample.wav` (22050, `np.interp`) | **3** `['O rádio','Segunda-feira','Os moradores']` | 0 | — |
| **B** live, real speech | WASAPI loopback of the default render endpoint, clip played at gain 0.30 | **6** `['precisam','O rá','anunciou que','Seg','Os mora','O']` | 0 | 0.192619 |
| **B'** HEAD acceptance (post-`AutoGain`) | same driver, current `worker/sotto_worker.py` | **5** `['Trabalhos','Moradores','O rá','Segunda','O rá']` | 0 | 0.187114 |

**Root cause of the reported `frames=35 blanks=35 blank_frac=1.0`:** `worker/runs/census-own-worker.jsonl:10`
— a run whose tap opened **`Mapeador de som da Microsoft - Input` [MME]** and delivered **peak=9.2e-05**,
`nonzero_blocks=0`. The worker's own verdict is `"silent-device"` / `device_outcome:"all-flat"`, and stderr
says `SILENT-DEVICE ... peak=9.2e-05 < floor=0.002 over 34 blocks (1/1 opened candidates silent)`.
It is a **dead-device** run, not a model run and not a delivery-rate run.

## 1. Raw arms

### ARM A (control)
```
$ cd H:/sotto && SOTTO_AUDIO_FILE='H:\sotto\_main\pt-br-sample.wav' \
    "C:/Program Files/Python311/pythonw.exe" worker/sotto_worker.py --config worker/config.json --stats-interval 10
rc=0
{"type":"status","state":"selftest-start","audio":"pt-br-sample.wav","audio_s":15.192,"chunks":27}
{"type":"caption","text":"O rádio","start":0.56,"end":1.12}
{"type":"caption","text":"Segunda-feira","start":6.72,"end":7.28}
{"type":"caption","text":"Os moradores","start":8.96,"end":9.52}
{"type":"status","state":"selftest-done","text":"O rádio Segunda-feira Os moradores","empty":false,"tokens":18,
 "audio_s":15.12,"infer_wall_s":3.139,"rtf":0.208,"frames":207,"blanks":189,"blank_frac":0.913,
 "empty_chunks":24,"vad_gated_chunks":0,"peak_rss_mb":2406.0}
stderr: RECOGNISED   : 'O rádio Segunda-feira Os moradores'
```

### ARM B (failing case, done properly — `_main/_bfrc_armB.py`, clip PLAYING through the device)
```
H:\sotto> pythonw _main/_bfrc_armB.py
play H:\sotto\_main\pt-br-sample.wav sr=22050 n=334990 gain=0.3 peak=0.1747
ARM B rc=0 wall=34.7s
{"type":"status","state":"capture-started","rate":48000,"block":4800,"attempt":1,"of":6}
{"type":"caption","text":"precisam","start":1.12,"end":1.68}
{"type":"caption","text":"O rá","start":6.72,"end":7.28}
{"type":"caption","text":"anunciou que","start":7.84,"end":8.4}
{"type":"caption","text":"Seg","start":12.88,"end":13.44}
{"type":"caption","text":"Os mora","start":15.12,"end":15.68}
{"type":"caption","text":"O","start":21.84,"end":22.4}
{"type":"status","state":"done","verdict":"captions-emitted","blocks":250,"nonzero_blocks":240,"peak":0.192619,
 "chunks":44,"captions":6,"tokens":19,"queue_drops":0,"frames":327,"blanks":308,"blank_frac":0.9419,
 "empty_chunks":38,"vad_gated_chunks":0,"audio_s":24.64,"device_outcome":"run-ended"}
```
`blank_frac=0.9419` **with 6 captions** — this model is blank-heavy by design; `blank_frac=1.0` is the
boundary case and it has a cause.

### ARM B' (HEAD acceptance, current file with `AutoGain`)
```
H:\sotto> pythonw _main/_bfrc_head.py        # same body, writes _main/bfrc_head.jsonl
ARM B rc=0 wall=38.7s
{"type":"caption","text":"Trabalhos","start":0.56,"end":1.12}
{"type":"caption","text":"Moradores","start":1.12,"end":1.68}
{"type":"caption","text":"O rá","start":2.24,"end":2.8}
{"type":"caption","text":"Segunda","start":8.4,"end":8.96}
{"type":"caption","text":"O rá","start":17.36,"end":17.92}
{"type":"status","state":"done","verdict":"captions-emitted","peak":0.187114,"peak_out":0.007454,"gain_db":2.4,
 "gain_max_db":2.4,"agc":true,"captions":5,"chunks":44,"vad_gated_chunks":0,"blank_frac":0.9362,"audio_s":24.64}
```

## 2. Refutations (the brief's named hypotheses, each killed by an arm)

| file (`_main/`) | what it isolates | result |
|---|---|---|
| `bfrc_a_22050_quiet.jsonl` | **level**: same clip at `peak=0.100510 rms=0.0147` — the live tap level | **3 captions**, `vad_gated=0` → level REFUTED |
| `bfrc_c_48000_full.jsonl`, `_quiet` | **resample**: 3:1 boxcar branch, the live capture's own path | **3 captions** both → resample REFUTED |
| `bfrc_playedfile.jsonl` | **tap**: real loopback capture of the clip, replayed | **3 captions** → tap faithful |
| `bfrc_capfile.jsonl` | **content vs branch**: the failing live capture fed through the FILE path | **0 captions**, `vad_gated=15`, `frames=140 blanks=140` → the failing capture is CONTENT, not the live branch |
| `bfrc_mixout_0060.jsonl` | SNR: known speech @0.06 + real ambient | **3 captions** → low SNR alone does not blank |
| `bfrc_b_live.jsonl` | live, **nothing playing** | 0 captions, `vad_gated=33/44`, `peak=0.101929` |

`_main/_bfrc_flags.py` (`bfrc_flags.out`) — the tap's only un-audited hole
(`AUDCLNT_BUFFERFLAGS_SILENT`, docs: buffer contents undefined when set) — measured on this endpoint:

```
packets: 800
flag histogram (value -> count):
   flags=0x0 (0b0000) count=799  normal data
   flags=0x1 (0b0001) count=1  DATA_DISCONTINUITY
packets flagged SILENT: 0/800
  normal   packets: peak min=0.004700 med=0.028282 max=0.101929
total samples=384000 (8.00s) peak=0.10193 rms=0.013828
```
`0/800` flagged, packet peaks **varying** (`0.0047 → 0.1019`) → the tap delivers real changing data;
the SILENT-flag defect is **latent, not active** on this box.

Envelope modulation (`_main/_bfrc_endpoint.py`): the failing capture is 66.9% sub-4 Hz (47.6% in 0.3–2 Hz)
against 60.0% for the known-speech capture — the idle floor of a virtual render endpoint.

## 3. `file:line` of the root cause

- **`worker/sotto_worker.py:762-767`** — `device_candidates`' tail offers **every** non-microphone input,
  including Windows' Sound-Mapper pseudo-device, which **opens, delivers blocks, and is digital silence**
  (measured `peak=9.2e-05`). On a host where it is the only candidate the run ends `1/1 opened candidates
  silent`.
- **`worker/sotto_worker.py:159`** — `TAP_PEAK_FLOOR = 0.002` — correctly rejects it (verdict
  `silent-device`), but only after **`:158`** `TAP_WINDOW_S = 6.0` is spent, and with nothing left to rotate to.
- **`worker/sotto_worker.py:158-159`** — the floor was calibrated against a *dead* tap (`peak=0.000031`) and
  cannot separate "carrying speech" from "carrying a virtual endpoint's idle floor" (`peak≈0.102`), which
  **passes** it and is then `vad_gated` to death (`bfrc_b_live`: 33/44 chunks).

## 4. The proving caption

ARM B' (§1) — shipped worker, shipped config, live, no `--device`, `verdict="captions-emitted"`, 5 captions.
The product's acceptance test (`play audio → captions`) passes on the current revision. Fragments
(`O rá`, `Seg`) are thinner than the file arm's words because the capture carries the endpoint's idle floor at
roughly +5.7 dB SNR — a quality gap, not a broken path.

## 5. Falsifier findings on the peer lane's `AutoGain` (reported, not fixed)

1. The stage's own causal claim (`sotto_worker.py:1426-1429`: "the CONTROL arm: the same quiet source,
   **no gain, and (measured) no captions**") is **falsified by ARM B**: 6 captions on the pre-`AutoGain`
   revision. On a speech-carrying source the captions do not depend on the gain. A `SOTTO_AGC=0` control is
   only isolating if both arms are fed a source that carries speech.
2. **Run-maxima are published wrong.** In ONE run (`bfrc_head.jsonl`):
   `WORKER_STATS tag=tick blocks=200 ... gain_max_db=+20.1 peak_out=0.767911`, then 50 blocks later the
   `done` payload says `"peak_out":0.007454,"gain_db":2.4,"gain_max_db":2.4`. Both fields are run maxima by
   construction (`:880-881`), so the run's loudest gain is unreportable — the same class the file's own
   comment at `:1426` was written to prevent.

## 6. The one line I would change

`worker/sotto_worker.py:159` (`TAP_PEAK_FLOOR`) and the candidate tail at `:762-767`: the acceptance test is
absolute-peak only, so a quiet virtual endpoint's idle floor passes it, and the tail offers devices that can
never carry loopback audio. **Not landed:** the Sound-Mapper name is localized, so a name test is not the
universal detector this ladder was rebuilt to be, and I could not derive a language-free predicate inside the
hour. The file was also being written by another lane throughout.

## SELF-AUDIT

- **protocolos em falta** — I did not read `history://BlankFramesRootCause` before running: its arms
  (`bfrc_capfile`, `bfrc_playedfile`, the mixtures) were already on disk, and I re-derived two of them by
  inspection rather than by running them myself. The peer message I sent was refused by the owner-screen
  guard (`agent://…` resolved as a filesystem path under `I:\!manager`), so the coordination travelled only
  through §5 of this file.
- **verificacao adicional** — a `SOTTO_AGC=0` run on ARM B's own source (live, clip playing) would settle
  §5.1 causally. Cost: ~40 s, one worker start, one playback. Not run: the file was being rewritten by the
  peer lane, so any receipt would be against a revision that no longer exists when read.
- **checkboxes novas** — (a) every "blank/zero-output" claim must print the run's own
  `verdict` next to `blank_frac`: `grep -o '"verdict": "[a-z-]*"' <run>.jsonl`. `silent-device` and
  `model-emitted-nothing` were conflated in the brief, and that one field separates them.
  (b) before blaming the model, require `nonzero_blocks > 0` — a run with `nonzero_blocks=0` has nothing to
  transcribe by construction.
- **review por outro subagente** — **sim-com-escopo**: the branch decision in §0/§2 against §1's raw files,
  specifically that ARM B had a real, playing source and that `bfrc_a_22050_quiet.jsonl` really is
  `peak=0.100510`.
- **gate-doubt**
  - *verde-de-verdade:* ARM A and ARM B are real greens — fresh runs today, captions and the `done` payload
    on the same pipe, and ARM B is falsifiable by its own twin `bfrc_b_live.jsonl` (same command, no source
    playing, `captions=0`). The **weak** green is `0/800 SILENT`: it is green *now*, on this endpoint; with
    an idle endpoint and a driver that marks packets, the same code path turns undefined contents into
    "audio". ARM B' is a green whose *cause* is contested — the captions appear with and without the AGC.
  - *falta-no-gate:* no gate compares a run's `verdict` against its counters, so
    `frames=35 blanks=35 blank_frac=1.0` was read as a model failure while the run said `silent-device`.
  - *gate-melhor:* assert per live run that `blank_frac == 1.0` implies `nonzero_blocks == 0` or
    `verdict == "silent-device"`; and assert `done.peak_out == max(tick.peak_out)` within a run. RED input
    for the second: `_main/bfrc_head.jsonl` as it stands today (`done.peak_out=0.007454` vs
    `tick.peak_out=0.767911`).
- **confianca** — **alta** on the branch: the live path captions, and level + resample are each refuted by
  two independent arms. **media** on attributing the brief's exact number: I matched
  `frames=35 blanks=35` to `census-own-worker.*` by value, not by observing the brief's author produce it.
- **nao verificado** — the owner's own player was never driven (I used `sd.play`, whose default output is
  PortAudio device 7 `VoiceMeeter Input (VB-Audio Voi` [MME]); the default render endpoint
  `{55395a4e-…}` could not be named (property-store read returned `hr=-2147467261` E_FAIL);
  `bfrc_speed2/4/6/8` (`captions=0`, `vad_gated=21`) were recorded but not re-derived; and the current
  `AutoGain` revision was executed only once (ARM B').

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: BlankFramesDecisive
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\BlankFramesDecisive.jsonl
- cache: read=2703488 write=0 hit=95.2244% (cache-read / input+cache-read); universe: 31 usage rows; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP; population: 5 of 114317 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'BlankFramesDecisive']; window: 2026-10-06T08:52:04.860000+00:00..2026-10-06T08:54:15.670000+00:00)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T08:52:04.860000+00:00; WHERE session_id=01a11069-7e12-7011-ad50-909c7482d980 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0
  - break_items=1; WHEN=2026-10-06T08:52:05.668000+00:00; WHERE provider=space-bunny-free item_index=0
  - break_items=1; WHEN=2026-10-06T08:52:06.119000+00:00; WHERE provider=ling-3.1-flash-free item_index=0
  - break_items=3; WHEN=2026-10-06T08:52:06.480000+00:00; WHERE provider=deepseek-flash item_index=0
  - break_items=2; WHEN=2026-10-06T08:54:15.670000+00:00; WHERE provider=deepseek-flash item_index=50
- input tokens: 135582 · output tokens: 38815 · cache-read tokens: 2703488 · cache-write tokens: 0
- verdict: UNKNOWN — no task-level acceptance verdict is stored; the ratio is descriptive, not a
  prefix-stability decision
```
Command: `bash I:/!manager/scripts/cache-task-report.sh BlankFramesDecisive` → rc=0 (first attempt was
blocked by the C4/PIPE-STATUS landmine guard because it was piped to `head`; rerun with `> log 2>&1; rc=$?`).
