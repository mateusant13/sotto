# SottoDeviceResolution — why the live run reported SUCCESS while hearing nothing

**Lane:** device resolution + capture truthfulness. **Date:** 2026-10-06.
**Files owned and touched:** `worker/sotto_worker.py` (device/capture section only),
`worker/config.json` (read + oracle only, not modified), `AGENTS.md` (routing law),
`_main/*` (new probes/oracles — this directory was declared in AGENTS.md's layout table).

---

## 1. The headline finding CONTRADICTS the brief

The brief says the resolver "did NOT land on any of them". **That is false, and the run
artifact says so.** `worker/runs/live-smoke-main.jsonl` line 6:

```json
{"type": "status", "state": "capture-started", "device": "CABLE Output (VB-Audio Virtual Cable)", "rate": 16000, "block": 1600, "attempt": 1, "of": 6}
```

The resolver opened CABLE Output **first**, exactly as `preferred_devices` orders it. It then
found it flat and rotated (`device-rotated ... "reason": "flat"` x3). The `device` field on the
final `done` line reads `"Driver de captura de som primário"` only because that is the
**last** candidate the rotation happened to be holding when `--max-seconds 22` expired — the
rotation was mid-flight, not resolved. Reading that field as "the chosen device" is what makes
the log look like a resolver miss.

**The actual defect is narrower and worse: the run never claimed to have heard anything, and
still exited 0.** Its own line:

```json
{"verdict": "model-emitted-nothing", "peak": 0.000122, "captions": 0, "device_outcome": "run-ended"}
```

`peak=0.000122` against a floor of `0.002` is **digital silence**. Blaming the model for a
device that delivered no signal is the lie; so is exit 0.

## 2. Why CABLE Output was silent — measured, not guessed

`py -3 _main/inject-all-probe.py 8 "CABLE Input" 440` renders a known 0.5-amplitude tone and
watches every input at once:

```
MME#2            CABLE Output (VB-Audio Virtual   peak=0.499969  saw_tone=true
DirectSound#15   CABLE Output (VB-Audio Virtual Cable)  peak=0.499969  saw_tone=true
WASAPI#32        CABLE Output (VB-Audio Virtual Cable)  peak=0.499908  saw_tone=true
verdict: TONE-OBSERVED
```

**The capture path is correct.** A passive 22 s listen with nothing injected
(`_main/listen-probe.py`, verdict `NOTHING-ROUTED`) peaks at **0.000122 across every
loopback** — so the cable was simply not being fed. The system default output is
`VoiceMeeter Input`; app audio only reaches a cable if VoiceMeeter is configured to output
into it.

One measured asymmetry worth keeping: the loopback works **MME render → DirectSound capture**
(0.4999) but **DirectSound → DirectSound does not loop back** here (0.00003). My first
positive-arm attempt failed for exactly that reason and I corrected the harness — recorded in
`_main/run-live-routed.py` so the next lane does not repeat it.

**This is the owner's actual blocker and it is not in the worker.** The worker now says so
loudly instead of exiting 0.

## 3. The fix (`worker/sotto_worker.py`)

| change | why it was needed |
|---|---|
| `TAP_SILENT_BLOCKS = 20` | a candidate must deliver >= 20 callbacks before its silence is believed; below that the honest word is "no-data" |
| `device_blocks` counter, reset per candidate | peak alone cannot distinguish "400 blocks of silence" from "3 blocks then the run ended" |
| `tap_ledger` | one row per opened candidate: device, index, **host API**, peak, blocks, captions, settled |
| `proved_alive` | a tap may only be called the run's device after clearing the floor |
| `_host_api_name()` | a name does not identify what was opened — CABLE Output exists at 3 indices under 3 APIs |
| new verdict `silent-device` | fires when a candidate ran a real window below the floor and nothing proved alive |
| `state="silent-device"` + stderr `SILENT-DEVICE` line | names the device, its API, the measured peak and the floor |
| **exit 3** on silent (was 0) | 3 is distinct from 2 (setup error), so a caller can separate "never started" from "started and got nothing" |

Preserved untouched: the int8 selection (`models/…-int8`) and the decode fix. The spec oracle
from `docs/model-specs/README.md` §7 exits **0** after my edits, and `--selftest` still emits
**16 captions** — the model path is unbroken.

The WebView2 bridge already surfaces non-zero exits (`_wait()` → "Worker stopped (exit 3)" →
restart), so exit 3 is actionable on the panel rather than silent.

## 4. Acceptance — both arms, in one run

`py -3 _main/device-silence-oracle.py 18` → **exit 0**, `verdict: PASS`:

```json
{"arm": "1-silent-must-fail-loud", "rc": 3, "verdict": "silent-device", "captions": 0,
 "device": "Mapeador de som da Microsoft - Input", "api": "MME", "peak": 9.2e-05,
 "peak_floor": 0.002, "blocks": 60}
{"arm": "2-routed-must-succeed", "rc": 0, "verdict": "captions-emitted", "captions": 17,
 "device": "CABLE Output (VB-Audio Virtual Cable)", "peak": 0.274506,
 "proved_alive": true, "rotations": 0,
 "caption_words": "Today for a for He'll have to put Sunday and he can come immediately going sl Country Roads speaking to in drafty Schoolrooms Day after For He'll have to pu an At some place of"}
```

**The brief's own 22 s command, re-run unchanged** (`_main/run-live-hidden.py`, default config,
nothing routed):

```
EXIT_CODE = 3   captions = 0
state  = silent-device
device = Mapeador de som da Microsoft - Input [MME]
peak   = 0.000122  < floor 0.002  over 60 blocks
stderr: SILENT-DEVICE Mapeador de som da Microsoft - Input [MME] peak=0.000122 < floor=0.002
        over 60 blocks (4/4 opened candidates silent, captions=0)
```

That is the loud-failure branch the brief asked for, not the captions branch — because nothing
is routed. The brief accepts either ("or the new loud failure naming why"), and reporting
captions here would have meant manufacturing audio and calling it the owner's PC.

**NEGATIVE arm (the required red).** Config naming ONLY a permanently silent device
(`Mixagem estéreo …`): first candidate is that device, and the run still ends
`rc=3 verdict=silent-device`, naming `Mapeador de som da Microsoft - Input [MME] peak=0.000122
over 60 blocks, proved_alive=false`. The gate cannot go vacuously green: ARM2 asserts
`rc=0 ∧ captions>0 ∧ device==CABLE ∧ proved_alive`, ARM1 asserts `rc=3 ∧ verdict=silent-device
∧ blocks>=20 ∧ device+peak named`, and they cannot both pass by accident.

## 5. House rules honoured

- Every worker spawn went through `_main/run-live-hidden.py` /
  `_main/device-silence-oracle.py` with `creationflags=CREATE_NO_WINDOW`. Post-run census:
  **0** `sotto_worker\.py` processes alive. The `ALERTA-JANELA … nome=pythonw` lines in the
  window census belong to *other* lanes (BrandOps tray, uvicorn, a sibling
  `sotto_webview.py`) — verified by reading each pid's command line, not assumed.
- Kill filters, where used, matched `sotto_worker\.py`; nothing matched the bare word `sotto`.
- No sibling lane's work was reverted.

## 6. What I did NOT do, and why

I did **not** change `config.json`. `preferred_devices` was never the fault — it was consulted
and honoured on the first candidate. Reordering it would have hidden the real problem.

## SELF-AUDIT

- **protocolos em falta:** the AGENTS.md rule "a name is no longer trusted for longer than one
  bounded window" told me to *rotate*; nothing told me a rotation that ends on the time budget
  must distinguish "the last device I happened to hold" from "the device I chose", and that a
  rotation's terminal state needs its own verdict. I would add a rule that every status naming
  a device also names its host API, after being bitten by the DirectSound/MME asymmetry.
- **verificacao adicional:** I ran the positive arm alone **3x** (rc=0, 17/14/15 captions) to
  prove the ARM2 result is not a single lucky run. Cheap, and it is what let me attribute the
  two oracle failures to contention rather than to my change.
- **checkboxes novas:** (a) assert `proved_alive` in the `done` record — a run that never proved
  a device must not be able to report `captions-emitted`; (b) assert `len(tap_ledger) == 1` on a
  success, so a silent first candidate can never again hide behind later ones.
- **review por outro subagente:** sim-com-escopo *the routing-law section of `AGENTS.md` and the
  `silent-device` verdict branch* — I would accept it for those, because those are the two
  places where a wrong sentence outlives this lane. I do **not** accept review of the measured
  numbers: they came from probes whose output is on disk and re-runnable.
- **gate-doubt:**
  - *verde-de-verdade:* the oracle's PASS was real — both arms executed in the same invocation
    and ARM2 asserted positive facts (captions, device, peak) that a vacuous gate could not
    manufacture. The one green I do NOT trust is my first positive-arm run, which was green
    only in the sense that it "worked"; it was actually a **false negative** caused by my
    harness picking the DirectSound render. That is the race I nearly reported as a product bug.
  - *falta-no-gate:* the oracle does not check that the **panel** renders `silent-device` as an
    error, only that the worker emits it and exits 3. A future change could keep the worker
    honest and let the shell swallow the code.
  - *gate-melhor:* `py -3 _main/device-silence-oracle.py 18` already goes RED on the input that
    matters (a silent device). For the shell gap, the check would be an end-to-end arm asserting
    `BRIDGE_EXIT … rc=3` and an error-state panel — cost ~1 lane; not built here because
    `app/webview/` is not my file.
- **confianca:** alta on the diagnosis and on the worker's new behaviour (measured, re-runnable,
  two arms). **media** on one thing I could not test: whether the owner's real audio, once
  routed, survives the full VoiceMeeter→CABLE path — I proved the cable carries injected audio,
  not that his routing carries his apps.
- **nao verificado:** (1) the WebView2 panel's *rendered* state on exit 3 — read the code, did
  not run the shell; (2) behaviour when the owner DOES have audio routed and the first
  candidate is briefly quiet before speech starts — the 6 s window would rotate a device that
  was about to work, and that window is unchanged from before; (3) `lang_id: 0` (en-US) against
  Portuguese audio remains the open deviation already listed in AGENTS.md.

## GATE-CHANGE REQUEST

n/a — this lane owns no gate under `I:/!manager` and changed none. The one gate-relevant
observation (the oracle's two arms must run in a single invocation because back-to-back int8
loads can kill the second process at `model-loading`, exit 4294967295, empty stderr) is
documented in `_main/device-silence-oracle.py` as a 20 s settle gap. It is a property of this
oracle, not a defect in a shared gate, so there is nothing for Main to merge.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoDeviceResolution
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoDeviceResolution.jsonl
- cache: read=14043008 write=0 hit=98.2346% (cache-read / input+cache-read); universe: 83 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoDeviceResolution.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-zen/space-bunny-free: calls=83 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 83 of 83 matched usage rows
- when-failed: break_items=2; WHEN=2026-10-06T06:05:48.225000+00:00 | break_items=2; WHEN=2026-10-06T06:10:41.021000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 111792 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoDeviceResolution']; window: 2026-10-06T06:05:48.225000+00:00..2026-10-06T06:10:41.021000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10fcf-6eea-71b3-9552-be048f239b45 provider=space-bunny-free model=space-bunny-free item_index=47; turn_id=1791266748225 | session_id=01a10fcf-6eea-71b3-9552-be048f239b45 provider=space-bunny-free model=space-bunny-free item_index=137; turn_id=1791267041021 (state=RESOLVED-BREAKS-OMP; population: 2 of 111792 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoDeviceResolution']; window: 2026-10-06T06:05:48.225000+00:00..2026-10-06T06:10:41.021000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T06:19:41.436741+00:00
- usage rows: 83
- model + route: opencode-zen/space-bunny-free
- input tokens: 252372
- output tokens: 44955
- cache-read tokens: 14043008
- cache-write tokens: 0
- hit ratio: 98.2346% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-zen/space-bunny-free: calls=83 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 83 of 83 matched usage rows
- prefix breaks: 4 (state=RESOLVED-BREAKS-OMP; population: 2 of 111792 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoDeviceResolution']; window: 2026-10-06T06:05:48.225000+00:00..2026-10-06T06:10:41.021000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=2; WHEN=2026-10-06T06:05:48.225000+00:00; WHERE session_id=01a10fcf-6eea-71b3-9552-be048f239b45 provider=space-bunny-free model=space-bunny-free item_index=47; turn_id=1791266748225
  - break_items=2; WHEN=2026-10-06T06:10:41.021000+00:00; WHERE session_id=01a10fcf-6eea-71b3-9552-be048f239b45 provider=space-bunny-free model=space-bunny-free item_index=137; turn_id=1791267041021
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```
