# audio-escopo — WHICH render endpoint the tap must read, and the cure

Lane `SottoAudioEscopo`, 2026-10-06. Target `H:/sotto`. Owner's words, verbatim:

> *"eu to com o youtube fazendo som e nao tem nada sendo transcrito"* — and
> *"o audio nao ta pegando em tudo do meu pc"*.

**VERDICT: the hypothesis is CONFIRMED, and the answer to the one binary question
is NO.**

> **Does the tap read audio when the sound comes out of the REAL speakers?**
> **NO.**  Playing the fixture to a real-speaker endpoint lit that endpoint's
> loopback at **peak 0.429398 (49 of 49 blocks)**, while the endpoint the tap
> actually opens — the DEFAULT — read **peak 0.000000, 0 blocks**.

Root cause, in one line: `WasapiLoopbackTap` opened **`default_render_endpoint()`
and nothing else**, while the owner's audio rendered on a **different** endpoint.

---

## 1. Every ACTIVE render endpoint on this machine

`IMMDeviceEnumerator::EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE)` — 6
endpoints (`_main/audio-escopo-probe.py`, `_main/audio-escopo-sessions.py`). The
code path publishes **no** `PKEY_Device_FriendlyName` on this box (measured: the
property store returns nothing — `wasapi_loopback.py`'s own comment records it),
so the names below come from the registry
`HKLM\...\MMDevices\Audio\Render\<guid>\Properties\{a45c254e-…},2`, matched to the
GUID the API returns.

| # | endpoint id (GUID) | name (registry) | DEFAULT? | live meter peak | loopback: blocks / nonzero / peak |
|---|---|---|---|---|---|
| 0 | `{1aee4592-2e18-4248-bf54-2fa14af8315c}` | Speakers (NVIDIA Broadcast) | no | **0.000000** | 0 / 0 / 0.000000 |
| 1 | `{2f1295af-8529-4f15-b00d-7b9bba575ac0}` | **CABLE Input (VB-Audio Virtual Cable)** | no | **0.204729** → **0.264260** | **43 / 43 / 0.372408** |
| 2 | `{55395a4e-97b2-4b96-9878-18be1ed894e0}` | **VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)** | **YES** | **0.000000** | **0 / 0 / 0.000000** |
| 3 | `{6780e74d-2f7e-42e0-bcb4-ee85911b5259}` | Fones de ouvido (soundcore Space Q45) | no | 0.000000 | *capture failed* `Initialize(LOOPBACK) failed` |
| 4 | `{7d427fc9-5cff-431f-ae0c-c1abd1229f8b}` | AG251F1WG2 (NVIDIA High Definition Audio) | no | 0.000000 | 0 / 0 / 0.000000 |
| 5 | `{b1e02bd0-0cc2-40b4-8eb8-7827f979ff73}` | Alto-falantes (HyperX Quadcast) | no | 0.000000 | 0 / 0 / 0.000000 |

**The DEFAULT is `VoiceMeeter Input` (endpoint 2) and it is IDLE. The endpoint
that is RENDERING is `CABLE Input` (endpoint 1).** They are different devices.

Raw evidence: `_main/audio-escopo.json`, `_main/audio-escopo.log`,
`_main/audio-escopo-sessions.log`.

### 1.1 WHO was rendering, by pid (not by guess)

`IAudioSessionManager2` on each endpoint (`_main/audio-escopo-sessions.py`), while
the owner's audio was playing:

```
[       ] {…{2f1295af…}  meter_peak=0.264260  sessions=3
      pid=22932 state=0 proc='steam.exe'
      pid=9736  state=1 proc='chrome.exe'      <-- ACTIVE (AudioSessionStateActive)
      pid=0     state=0 proc='?' display='@%SystemRoot%\System32\AudioSrv.Dll,-202'

[DEFAULT] {…{55395a4e…}  meter_peak=0.000000  sessions=8
      pid=20668 state=0 proc='Discord.exe'
      pid=21464 state=0 proc='chatterino.exe'
      pid=22932 state=0 proc='steam.exe'
      pid=21440 state=0 proc='Discord.exe'
      pid=14340 state=1 proc='nvcontainer.exe'
      pid=0     state=0 proc='?'
      pid=29604 state=0 proc='WindowsTerminal.exe'
      pid=46832 state=1 proc='python.exe'      <-- Sotto's OWN loopback client
```

`chrome.exe` (pid 9736) is the owner's YouTube, and it renders to **`CABLE Input`**.
The DEFAULT endpoint's only ACTIVE session is **Sotto's own loopback client** —
i.e. the tap was listening to a device nothing was playing into.

## 2. The controlled measurement — per endpoint, one stimulus at a time

`_main/audio-escopo-probe.py --seconds 5 --play-index <i>` renders the bundled
speech fixture (`worker/assets/sample1.flac`, 13.7 s) into ONE endpoint through
the WASAPI host API while a loopback capture runs on **all six** endpoints at
once. Every arm lit up **exactly one** endpoint and **nothing else** — which is
what makes the table a control and not a coincidence.

| played to | endpoint that lit up | blocks / nonzero / **peak** | DEFAULT (VoiceMeeter Input) |
|---|---|---|---|
| `Alto-falantes (HyperX Quadcast)` — a REAL speaker | `{b1e02bd0…}` | 49 / 49 / **0.429398** | **0 / 0 / 0.000000** |
| `CABLE Input` | `{2f1295af…}` | 50 / 50 / **0.429398** | **0 / 0 / 0.000000** |
| `VoiceMeeter Input` (= the DEFAULT) | `{55395a4e…}` | 50 / 50 / **0.429398** | **0.429398** (50 / 50) |

`_main/audio-escopo-play-{hyperx,cable,voicemeeter}.{json,log}`.

**This is the answer to the one question the brief asked, with the number:
the tap reads NOTHING (0 blocks, peak 0.000000) when the sound comes out of a real
speaker, because it only ever opened the DEFAULT — and on this box the DEFAULT is
not where anything is being played.**

## 3. The cure — rung (a) is generalised to EVERY active endpoint

Requirement: *"o tap tem de assentar no endpoint QUE RENDERIZA, nao no 'default'…
manter a rung (a) mas GENERALIZA-LA a todos os endpoints ACTIVE, e ordenar por
quem tem sinal."* Exactly that, and nothing else: **the ASR was not touched.**

### `worker/wasapi_loopback.py`
* `list_render_endpoints()` (new) — every ACTIVE render endpoint with its **live**
  `IAudioMeterInformation::GetPeakValue`, sorted by signal: `meter_peak`
  descending, DEFAULT breaking the tie.
* `loopback_device_specs()` (new) — one candidate dict per endpoint, each carrying
  its `endpoint_id` and a `rung_why` that names whether it is the default and
  whether it is rendering now (`"…(rendering now, meter peak 0.237)"`).
* `endpoint_spec(id)` / `_device_by_id(enum, id)` (new) — open a CHOSEN endpoint
  (`IMMDeviceEnumerator::GetDevice`, vtable index 5).
* `WasapiLoopbackTap(on_block, block_ms, role, endpoint_id=None)` — `endpoint_id`
  `None` keeps the historical behaviour (the DEFAULT); a value opens THAT
  endpoint, in `_open()`.
* `_make_enumerator` / `_friendly_name` / `_endpoint_id` / `_mix_spec` extracted so
  a second endpoint cannot be described by a second, drifting copy of the
  mix-format parsing. `default_render_endpoint()` and `loopback_device_spec()`
  keep their signatures and behaviour.

### `worker/sotto_worker.py`
* `device_candidates()` — rung (a) now iterates `loopback_device_specs()` instead
  of offering the default alone. The default stays in the list (dropping it would
  break the historical driver-free path and a silent endpoint costs one bounded
  tap window); it is simply **no longer first when it is idle**.
* `offer()` — a WASAPI candidate is de-duplicated on its **endpoint id**, because
  two active endpoints may publish the same friendly name (two identical
  monitors) and a name collision would silently drop one.
* `LoopbackTap()` — passes `endpoint_id=device.get("endpoint_id")` into the tap.

## 4. Verification (commands and their real output)

```
py -3 _main/flat-endpoint-oracle.py            -> LIVE: PASS   CONTROL: RED as required   VERDICT PASS   rc=0
py -3 _main/flat-endpoint-oracle.py --with-tap -> LIVE: PASS   CONTROL: RED as required   VERDICT PASS   rc=0
```
The control arm is the frozen pre-fix copy (sha256 `2A2F8021…`) and it is RED on 5
arms: the refactor did not weaken the COM gate it guards.
(`_main/audio-escopo-oracle-flat-{plain,withtap}.out`)

**Ladder order, with audio actually playing** (`_main/ladder-probe.py`,
`_main/ladder-probe.log`):

```
  [0] rung=a  name='WASAPI loopback: {0.0.0.00000000}.{2f1295af-…}'
      why=WASAPI loopback of an active render endpoint (rendering now, meter peak 0.237)
  [1] rung=a  name='WASAPI loopback: {0.0.0.00000000}.{55395a4e-…}'
      why=WASAPI loopback of the DEFAULT render endpoint
```

**The shipped worker, end to end** (`_main/audio-escopo-worker-run.py`, fixture
rendered into `CABLE Input` for 55 s; `--max-seconds 55`):

```
{"state": "capture-started", "device": "WASAPI loopback: {…{2f1295af…}", "attempt": 1, "of": 10}
{"state": "done", "verdict": "captions-emitted", "blocks": 550, "nonzero_blocks": 550,
 "peak": 0.465224, "captions": 48, "queue_drops": 0, "audio_s": 54.88, "rtf": 0.1,
 "device": "WASAPI loopback: {…{2f1295af…}", "device_outcome": "run-ended"}
WORKER_STATS tag=final blocks=550 … nonzero_blocks=550 peak=0.465224 rms=0.05524085 … captions=48 …
EXIT_CODE 0
```

It settles on **attempt 1 of 10** — the endpoint that is rendering — and captions
the fixture's own words.

### 4.1 The owner's symptom, reproduced, and its cure — in the app's own log

`_main/webview-run.log`. **BEFORE** (worker pid 46832, the pre-fix code):

```
sotto: BRIDGE_SILENT_BENIGN ms=15000 pid=46832 state=no-audio because="device-rotated reason=flat peak=0.250364 floor=0.002" restarts=0
sotto: STATUS_APPLIED text="Audio tap silent - nothing to transcribe"
sotto: PLACEHOLDER_APPLIED title="No audio to transcribe"
```
…repeated for hundreds of lines, with **zero captions**.

**AFTER** (the app restarted onto the fixed worker — see §5):

```
sotto: STATUS_APPLIED text="Receiving captions"
sotto: CAPTION_APPLIED text="…" count=10
sotto: BRIDGE_CAPTION_SENT delivered=true text="…"
sotto: HISTORY_APPEND path="H:\sotto\history\2026-10-06\09.md"
```

`Audio tap silent - nothing to transcribe` last occurs before the fix at **log
line 2393**; the fix-bearing worker spawns at **line 2422**. **It does come back
twice afterwards** — and that is recorded here rather than rounded off:

```
sotto: BRIDGE_SILENT_BENIGN ms=15000 pid=27084 state=no-audio because="device-rotated reason=flat peak=0.0 floor=0.002" restarts=1
sotto: STATUS_APPLIED text="Audio tap silent - nothing to transcribe"
...
sotto: BRIDGE_CAPTION_SENT delivered=true text="…"     <- the very next caption clears it
sotto: STATUS_APPLIED text="Receiving captions"
```

Both flashes are the shell's 15 s benign-silence watchdog firing **during the
ladder's OWN walk** past an idle endpoint (`reason=flat peak=0.0` — a genuinely
idle endpoint, not the old `peak=0.250364`), and each is cleared by the next
caption. The run was captioning continuously: `CAPTION_APPLIED … count=25` by
09:33:14, `HISTORY_APPEND` to `H:\sotto\history\2026-10-06\09.md` throughout, 9 of
the last 40 log lines `BRIDGE_CAPTION_SENT delivered=true`. Contrast the BEFORE
state, where the same line repeated for **~20 minutes with zero captions ever**.

**App left running**, hidden, exactly as the brief requires — final state after the
last of the steps below: shell `pythonw.exe` pid **44264**, worker `python.exe` pid
**43532** (interpreter PINNED — see §6.3), exactly ONE instance, captions flowing on
the FIXED code and re-proved against known speech in §4.2.

### 4.2 The surviving app re-proved with KNOWN speech, and a duplicate removed

Two full app instances were briefly up at once — this lane's relaunch (shell
`39556` / worker `27084`, started 09:30) and a second, independent `run.cmd`
launch (shell `37684` / worker `38560`, started 09:35, distinct `ready-file`
random). Both ran the same on-disk code (`wasapi_loopback.py` 09:27,
`sotto_worker.py` 09:26), so removing one changed nothing about which code the
owner runs. **This lane removed only its OWN instance** (`_main/audio-escopo-dedupe-app.ps1`,
which re-verifies the artifact path in the command line before each kill and
refuses anything that does not name `sotto_webview.py` / `sotto_worker.py`); a
sibling's subject was never touched. One app remained: `37684` / `38560` — which a
later launch then replaced with a BROKEN instance, cured in §6.3.

Then, rather than trust earlier captions, the running app was re-proved against
audio of KNOWN content: the bundled speech fixture was rendered into `CABLE Input`
for 16 s and the surviving app transcribed it, verbatim:

```
sotto: BRIDGE_CAPTION_SENT delivered=true text="Going alo slas Country Roads and Speaking to"
sotto: CAPTION_APPLIED text="Going alo slas Country Roads and Speaking to." count=148
sotto: HISTORY_APPEND path="H:\\sotto\\history\\2026-10-06\\10.md" time=10:02:12
sotto: BRIDGE_CAPTION_SENT delivered=true text="… He'll have an appearance"
sotto: CAPTION_APPLIED text="An appearance." count=150
sotto: CAPTION_APPLIED text="Sunday morning and he he can come to immediate." count=151
sotto: CAPTION_APPLIED text="Roads." count=152
sotto: STATUS_APPLIED text="Receiving captions"
```

The captions are the fixture's own English words, so the surviving app is not
merely "running" — it is reading the endpoint that is rendering and decoding it.

### 4.3 The owner's OWN audio, transcribed — the acceptance, not a fixture

The strongest reading of the fix is not a fixture at all. On the restored instance
(shell `24756` / worker `39948`, interpreter pinned to
`C:\Program Files\Python311\python.exe` per `WORKER_COMMAND`), the app captioned the
owner's **live Portuguese speech**:

```
sotto: BRIDGE_CAPTION_SENT delivered=true text="minha camisa inte ira agora"
sotto: CAPTION_APPLIED text="Minha camisa inte ira agora." count=1
sotto: STATUS_APPLIED text="Receiving captions"
sotto: HISTORY_APPEND path="H:\\sotto\\history\\2026-10-06\\14.md" time=14:42:50 bytes=28
sotto: BRIDGE_CAPTION_SENT delivered=true text="minha camisa inte ira agora caralho"
sotto: CAPTION_APPLIED text="Minha camisa inte ira agora caralho." count=2
```

This supersedes the earlier caution in §7 about the language of the captions: with
the tap on the endpoint that was actually rendering, the model decoded the owner's
own audio into recognisable Portuguese. The ASR was still never touched — this is
the SAME model, finally being fed.

The oracle was re-run against the tree as the other lanes left it (`sotto_worker.py`
had grown again, 149 856 B at 10:51) and is still green:
`LIVE: PASS  CONTROL: RED as required  VERDICT PASS  rc=0`
(`_main/audio-escopo-oracle-current.out`).

## 5. Why the app had to be RESTARTED (it would not have self-healed)

The shell's hot-reload saw the edits and then **held them forever**:

```
sotto: HOT_RELOAD_EVENT kind=worker file=wasapi_loopback.py action=3 events=2
sotto: HOT_RELOAD_WORKER_QUEUED files=["wasapi_loopback.py"] debounce_ms=2000 min_interval_ms=180000
sotto: HOT_RELOAD_WORKER_DEFERRED files=["wasapi_loopback.py"] reason=capturing -- applies at the next boundary
```

`boundary()` (`app/webview/sotto_webview.py:2452`) only lands a held reload when
the worker is **not** `is_capturing()`. A worker stuck streaming a silent device
never leaves the capturing state, so the deferral is permanent: **the reload is
queued, deferred, and never applied.** Restarting the app was therefore required,
not cosmetic. Reported as a ticket.

## 6. The residual loss points, named

Two further ways the audio is lost on this box, both measured:

1. **Rung (b) API asymmetry — a name-only match picks the SILENT index.**
   With the audio rendering into `CABLE Input`, the cable's paired capture device
   reads (`_main/audio-escopo-capture-inputs.log`):
   ```
   'CABLE Output (VB-Audio Virtual '   api=MME          peak=0.000031
   'CABLE Output (VB-Audio Virtual Cable)' api=Windows DirectSound  peak=0.117035
   'CABLE Output (VB-Audio Virtual Cable)' api=Windows WASAPI       peak=0.169575
   ```
   The ladder matches a cable INPUT by **name**, and `device_candidates()`
   `break`s on the first index — on this box that is the **MME** one, which is
   silent. (Same family as the `AGENTS.md` law "the loopback is asymmetric across
   APIs".) Rung (a) sidesteps it, because a WASAPI loopback has no host-API
   choice; a host with no render endpoint would still walk into it.
2. **The hot-reload deferral deadlock** of §5.
3. **The worker's interpreter is resolved from PATH, so the app can be launched
   into a state where it can NEVER transcribe.** Measured on this box while
   finishing this lane: an app shell started at 10:03:14 (pid 20656, itself
   correctly launched under `C:\Program Files\Python311\pythonw.exe`) spawned its
   worker with the **manager venv's** interpreter and the worker died on every
   restart:

   ```
   sotto: BRIDGE_SPAWNED pid=15236 argv=["I:\\!manager\\.venv\\Scripts\\python.EXE", "H:\\sotto\\worker\\sotto_worker.py"]
   sotto: BRIDGE_EXIT pid=15236 rc=1 spawns=5 captions=0 … stderr_tail=["  File \"H:\\sotto\\worker\\sotto_worker.py\", line 1307, in choose_providers", "    import onnxruntime as ort", "ModuleNotFoundError: No module named 'onnxruntime'"]
   sotto: BRIDGE_DEATH rc=1 deaths=5 last="worker exit 1" …
   sotto: STATUS_APPLIED text="Worker stopped (exit 1) - worker exit 1"
   ```

   Mechanism: `app/webview/sotto_webview.py` → `def default_python() -> str:
   return shutil.which('python') or sys.executable`, used by
   `self.command = command or default_python()`. The tell that this is an
   ENVIRONMENT bug and not a missing dependency: the branch launched minutes
   earlier on the same host spawned `C:\Program Files\Python311\python.EXE` and
   captioned normally. Filed as ticket `6066795547cdc5a35b014563`. **The durable
   cure is the shell's to make** (resolve the worker interpreter relative to
   `sys.executable`, not PATH); it is not this lane's file, and this lane instead
   pinned the interpreter at launch with the shell's own flag,
   `run.cmd --with-worker --python "C:\Program Files\Python311\python.exe"`.

   The pin works and the app is healthy on it (`_main/audio-escopo-restore.log`,
   `_main/webview-run.log`):

   ```
   sotto: WORKER_COMMAND C:\Program Files\Python311\python.exe
   sotto: BRIDGE_SPAWNED pid=42700 argv=["C:\\Program Files\\Python311\\python.exe", "H:\\sotto\\worker\\sotto_worker.py"]
   … (one worker death: Initialize(SHARED|LOOPBACK) failed 0x8889000A, respawned)
   sotto: BRIDGE_DEATH_LIFTED reason=caption captions=1
   sotto: BRIDGE_CAPTION_SENT delivered=true text="Immediately after Going along slas"
   sotto: CAPTION_APPLIED text="Immediately after Going along slas." count=1
   sotto: STATUS_APPLIED text="Receiving captions"
   ```

   `BRIDGE_DEATH_LIFTED reason=caption` is the shell's own rule satisfied: the
   held error state is cleared only by a real caption, and the pinned instance
   produced one.

## 7. Limits of this report, stated

* The three play arms are **one run each**; the two live/demonstration tables
  agree with them, which is why the arms are reported as a controlled trio and
  not as a distribution.
* The endpoint **names** come from the registry, not from the code path: on this
  box `PKEY_Device_FriendlyName` via the property store returns nothing, so a run
  can only name an endpoint by its GUID.
* The meter-based ordering is sampled for 0.4 s per endpoint. If the owner's audio
  has a longer digital-zero gap at that instant the order falls back to
  "default first" — the ladder then still **walks all candidates** (a silent one
  rotates, it does not abort), so the audio is found later rather than never; it
  is a latency effect, not a correctness one.
* Whether the owner's particular YouTube content is speech is **outside this
  lane**: the ASR and the language choice were deliberately untouched. The
  captions the fixed app now emits are the model's decode of real loopback audio;
  nothing here asserts their language or accuracy is right.
* **Cost of generalising rung (a): the ladder is longer.** Offering every active
  endpoint took the candidate list from 5 to 10 on this box, so a walk that
  produces no caption is up to ~60 s of rotation instead of ~30 s (`tap_window`
  × candidates), and a rotation now has 5 idle rung-(a) endpoints to pass before
  `best_carried` re-enters the loudest signal-carrying one. Measured consequence
  in the live app: two `BRIDGE_SILENT_BENIGN … peak=0.0` flashes during walks,
  each cleared by the next caption. This is a **latency** cost, not a correctness
  one — the ordering puts the rendering endpoint first, so the normal case
  settles on attempt 1 of 10 — and it is strictly better than the state before,
  which produced zero captions. A future change could shrink the walk (e.g. skip
  rung-(a) candidates whose meter peak is 0 once one has signal), but that is a
  policy change this brief did not ask for and it is NOT made here.
* The HyperX endpoint's loopback is used as the "real speaker" arm because it is
  the answering endpoint among the ACTIVE real-speaker candidates on this box
  (`Alto-falantes (HyperX Quadcast)`, `Speakers (NVIDIA Broadcast)`); the Realtek
  `Alto-falantes` is `DeviceState=8` (UNPLUGGED) and therefore not an ACTIVE
  endpoint at all.

## 8. Artifacts

| path | what |
|---|---|
| `_main/audio-escopo-probe.py` | per-endpoint meter + all-endpoint loopback capture, with `--play-index` |
| `_main/audio-escopo-probe.json` / `.log` | §1 census (idle + live) |
| `_main/audio-escopo-play-{hyperx,cable,voicemeeter}.{json,log}` | §2 controlled arms |
| `_main/audio-escopo-sessions.py` / `.json` / `.log` | §1.1 pid-per-endpoint |
| `_main/audio-escopo-capture-inputs.py` / `.log` | §6.1 MME/DirectSound/WASAPI cable inputs |
| `_main/audio-escopo-worker-run.py` + `audio-escopo-worker-cable.{jsonl,err,summary}` | §4 shipped-worker run |
| `_main/audio-escopo-oracle-flat-{plain,withtap}.out` | §4 oracle, both variants |
| `_main/ladder-probe.log` | §4 candidate order |
| `_main/audio-escopo-restart-app.ps1` / `audio-escopo-restart.log` | §5 artifact-named restart |
| `_main/audio-escopo-dedupe-app.ps1` / `audio-escopo-dedupe.log` | §4.2 removal of THIS lane's duplicate instance |
