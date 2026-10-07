# AudioEscopo — receipt

status: done

Deliverable: `H:/sotto/docs/audit/audio-escopo.md` (PRESENT, ~18 KB).
Code: `worker/wasapi_loopback.py`, `worker/sotto_worker.py`. App left running:
shell `pythonw.exe` pid **24756**, worker `python.exe` pid **39948** (interpreter
PINNED to `C:\Program Files\Python311\python.exe`, confirmed by `WORKER_COMMAND`),
exactly ONE instance. The app was found DOWN at 14:42 (the churn had killed it) and
relaunched; it then captioned the OWNER'S OWN live Portuguese speech —
`"minha camisa inte ira agora caralho"`, `count=2`, `Receiving captions`,
`HISTORY_APPEND 14.md` — which is the acceptance itself, not a fixture (doc §4.3).
The oracle was re-run against the tree as other lanes left it
(`sotto_worker.py` 149 856 B at 10:51) and is still `LIVE: PASS / CONTROL: RED /
VERDICT PASS rc=0`.

VERDICT: hypothesis CONFIRMED — the tap read the DEFAULT render endpoint
(`VoiceMeeter Input`, idle, meter 0.000000, loopback 0 blocks / peak 0.000000)
while the owner's Chrome (pid 9736, session state=ACTIVE) rendered to `CABLE Input`
(meter 0.264260, loopback 43/43, peak 0.372408). Answer to the binary question:
**NO** — playing the fixture to a real-speaker endpoint lit THAT endpoint at peak
0.429398 (49/49) and left the default at 0.000000 (0 blocks).

## SELF-AUDIT

- **protocolos em falta** — three, all found by refusal rather than by reading.
  (1) "native `H:\` paths only / do not mix MSYS and native call forms": `cd /d`,
  `tasklist /FI`, `grep -E`, and a `cmd | head; echo $?` whose status was the
  FILTER's (`C4/PIPE-STATUS`). Different: run
  `scripts/hygiene/landmine-lint.py --list-classes` BEFORE the first shell call of a
  lane and keep the class list open — the brief names the classes and I read that as
  advice instead of as rules. (2) I did not census app instances after my relaunch,
  so two apps ran ~30 min (§extra a). (3) I relaunched the app without pinning the
  worker's interpreter, so the app churn produced a permanently-broken instance
  (§extra b). Different for (2)+(3): after ANY relaunch of a long-lived service,
  assert exactly one instance AND assert the interpreter/dependency the child
  actually needs.
- **verificacao adicional** — RUN, three times, and it changed the record each time.
  (a) A second app instance (37684/38560, an independent `run.cmd` launch at 09:35)
  was found; this lane removed ONLY its own (39556/27084) — never a sibling's subject.
  (b) The surviving app was re-proved against KNOWN content: the speech fixture
  rendered into `CABLE Input` produced the fixture's own English words, `count=148 →
  152`. (c) After a later launch replaced the app with a BROKEN instance (wrong
  interpreter, worker dying with `ModuleNotFoundError: onnxruntime`), this lane killed
  that instance and relaunched with the interpreter PINNED, then re-proved with the
  fixture again: `BRIDGE_DEATH_LIFTED reason=caption captions=1`,
  `CAPTION_APPLIED … count=1`, `Receiving captions`. Still NOT run: a second
  repetition per §2 arm (the controlled trio is one run each); cost ~45 s per arm.
- **checkboxes novas** — (a) **"a fixture player must prove it opened"**: my first two
  play arms were silent because `sd.OutputStream` raised inside a thread and the error
  printed BEFORE the thread ran — three arms of "no signal" that looked like evidence.
  The probe now asserts `open_ok` + `frames_written` and prints `!! PLAYER NEVER
  OPENED -- this arm is INVALID`. (b) **"after any relaunch, assert exactly ONE
  instance"** — one census line matching `sotto_webview\.py` must return exactly one
  shell and one worker. (c) **"after any relaunch, assert the child's OWN
  interpreter"** — `grep WORKER_COMMAND` must show an interpreter that has the
  worker's dependencies; a wrong one is silent until the worker dies. (d) "a
  generalised candidate list must print its length" — `attempt 1 of 10`.
- **review por outro subagente** — sim-com-escopo: (1) run
  `py -3 _main/flat-endpoint-oracle.py --with-tap`, then break the control by restoring
  `default_render_endpoint()`'s old single-call body into a copy, to confirm the gate
  can still go RED; (2) take the worker to a host whose DEFAULT is the rendering
  endpoint and confirm the ordering degrades to "default first" without loss; (3) try
  to make §2's arms light two endpoints at once (they should not); (4) re-derive the
  §4.2 duplicate analysis and §6.3 interpreter analysis from
  `_main/audio-escopo-{dedupe,restore}.log` + `webview-run.log`.
- **gate-doubt**:
  - **verde-de-verdade**: `py -3 _main/flat-endpoint-oracle.py` → `VERDICT PASS` is
    real, not vacuous: the SAME command runs the frozen pre-fix copy as a control and
    that control went **RED on 5 arms**. Caveat checked and accepted: the oracle pins
    the MUTANT's sha, NOT the live file's, so it cannot detect "the live file did not
    change" — exactly what I wanted, having edited the live file by design. Second and
    third, plus a RE-RUN: the driver run's `captions=48`, the shipped
    app's `count=148→152` (both carry the fixture's own words, `queue_drops=0`), and
    then — because `worker/wasapi_loopback.py` was edited by ANOTHER lane mid-flight
    (37 793 B at 09:27 → 43 415 B at 10:08), which makes my earlier green STALE — the
    oracle was re-run against the CURRENT file: `LIVE: PASS  CONTROL: RED as required
    VERDICT PASS rc=0`, both plain and `--with-tap`. My cure survived that edit
    (`loopback_device_specs` still present in both files; `endpoint_id` still threaded
    at sotto_worker.py:794 and :1287) and so did the gate.
  - **falta-no-gate**: nothing in the repo gates *which endpoint the tap opens*, and
    nothing gates *which interpreter the worker runs under*. Two independent future
    changes each re-create a total failure while every existing gate stays green:
    reverting `WasapiLoopbackTap.__init__` to default-only (owner sees "no audio"),
    and reverting `default_python()` to `shutil.which('python')` (owner sees "Worker
    stopped"). Concrete scenario for the first: a lane "simplifies" rung (a) back to
    one candidate to shorten the walk cost in the doc's §7.
  - **gate-melhor**: two mechanical checks, each with the input that must leave it RED.
    (i) `py -3 -c "import sys;sys.path.insert(0,'worker');import wasapi_loopback as W;s=W.loopback_device_specs();assert s and all('endpoint_id' in c for c in s),'NO-ENDPOINT-ID';print('specs',len(s))"`
    — RED input: a `wasapi_loopback.py` whose `loopback_device_specs()` omits
    `endpoint_id`. (ii) assert the worker interpreter has the worker's own
    dependencies before the bridge relies on it — RED input: launch with
    `--python I:\!manager\.venv\Scripts\python.exe` (no onnxruntime), which must fail
    loudly at spawn instead of as a death loop.
- **confianca** — alta for the AUDIO deliverable (three independent greens on the
  shipped app, plus a red-capable control). Media for the APP-STATE story: the box is
  being relaunched by someone else while this lane works (three distinct instances seen
  at 09:30, 09:35, 10:03), so "one healthy app is running" is a statement about THIS
  minute, not a guarantee. What would move it higher: knowing WHO relaunches the app,
  and a second run per §2 arm.
- **nao verificado** — (1) a second run per §2 arm. (2) The residual rung-(b) MME
  asymmetry is measured but NOT fixed (policy, out of scope). (3) Whether the owner's
  specific YouTube content is speech — the ASR was deliberately untouched and I claim
  nothing about the language/accuracy of the captions shown for HIS audio; both proofs
  use the bundled speech fixture. (4) Endpoint #3 (`Fones de ouvido`) could not be
  loopback-captured, so its row is empty rather than zero. (5) I never established WHO
  launched the second (09:35) or the broken (10:03) instance. (6) The one worker death
  with `Initialize(SHARED|LOOPBACK) failed 0x8889000A` after the pinned relaunch is
  unexplained beyond "it respawned and then captioned"; I did not root-cause it.
  (7) The two shell defects (hot-reload deadlock; PATH-resolved worker interpreter) are
  filed but NOT fixed — they are `app/webview/sotto_webview.py`'s, not this lane's.
  (8) `worker/wasapi_loopback.py` is being edited CONCURRENTLY by another lane (43 415 B
  at 10:08 vs my 37 793 B at 09:27) while this ticket claimed it. I verified my cure and
  the oracle survived that edit, but I did NOT read the other lane's 5.6 KB of additions,
  so I cannot state what they do or whether they interact with mine — and the file may
  change again after this receipt is written.

Tickets filed by this lane (both `app/webview/sotto_webview.py`, neither fixed here):
- `4eaa5e223979bcf1d48f4ced` — hot-reload QUEUED→DEFERRED(capturing) never lands.
- `6066795547cdc5a35b014563` — worker interpreter resolved from PATH.

## CACHE/PRICE
- task/agent: SottoAudioEscopo
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoAudioEscopo.jsonl
- cache: read=20523875 write=0 hit=94.7537% (cache-read / input+cache-read); universe: 98 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoAudioEscopo.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=86 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=12 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 98 of 98 matched usage rows
- when-failed: break_items=15; WHEN=2026-10-06T12:18:18.840000+00:00 | break_items=1; WHEN=2026-10-06T12:19:58.553000+00:00 | break_items=2; WHEN=2026-10-06T12:25:20.228000+00:00 | break_items=239; WHEN=2026-10-06T13:01:04.209000+00:00 | break_items=244; WHEN=2026-10-06T13:01:25.636000+00:00 (state=RESOLVED-BREAKS-OMP; population: 5 of 117683 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoAudioEscopo']; window: 2026-10-06T12:18:18.840000+00:00..2026-10-06T13:01:25.636000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791289098840 | session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=92; turn_id=1791289198553 | session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=194; turn_id=1791289520228 | session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791291664209 | session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=26; turn_id=1791291685636 (state=RESOLVED-BREAKS-OMP; population: 5 of 117683 OMP prefix-ledger rows attributable to keys…
- report generated_at: 2026-10-06T13:02:46.425077+00:00
- usage rows: 98
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 1136363
- output tokens: 107747
- cache-read tokens: 20523875
- cache-write tokens: 0
- hit ratio: 94.7537% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=86 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=12 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 98 of 98 matched usage rows
- prefix breaks: 501 (state=RESOLVED-BREAKS-OMP; population: 5 of 117683 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoAudioEscopo']; window: 2026-10-06T12:18:18.840000+00:00..2026-10-06T13:01:25.636000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=15; WHEN=2026-10-06T12:18:18.840000+00:00; WHERE session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791289098840
  - break_items=1; WHEN=2026-10-06T12:19:58.553000+00:00; WHERE session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=92; turn_id=1791289198553
  - break_items=2; WHEN=2026-10-06T12:25:20.228000+00:00; WHERE session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=194; turn_id=1791289520228
  - break_items=239; WHEN=2026-10-06T13:01:04.209000+00:00; WHERE session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791291664209
  - break_items=244; WHEN=2026-10-06T13:01:25.636000+00:00; WHERE session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=26; turn_id=1791291685636
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

(full report also written to `H:/sotto/_main/audio-escopo-cache.out`)

## CACHE/PRICE (re-run at close, 2026-10-06T18:33:28Z — supersedes the block above)
- task/agent: SottoAudioEscopo
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoAudioEscopo.jsonl
- cache: read=45975737 write=0 hit=93.7936% (cache-read / input+cache-read); universe: 161 usage rows; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=136 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=25 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 161 of 161 matched usage rows
- when-failed: break_items=15; WHEN=2026-10-06T12:18:18.840000+00:00 | break_items=1; WHEN=2026-10-06T12:19:58.553000+00:00 | break_items=2; WHEN=2026-10-06T12:25:20.228000+00:00 | break_items=239; WHEN=2026-10-06T13:01:04.209000+00:00 | break_items=244; WHEN=2026-10-06T13:01:25.636000+00:00 | break_items=339; WHEN=2026-10-06T17:41:51.590000+00:00 | break_items=350; WHEN=2026-10-06T17:42:04.072000+00:00 | break_items=385; WHEN=2026-10-06T18:32:42.295000+00:00 | break_items=398; WHEN=2026-10-06T18:32:52.094000+00:00 (state=RESOLVED-BREAKS-OMP; population: 9 of 121160 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoAudioEscopo']; window: 2026-10-06T12:18:18.840000+00:00..2026-10-06T18:32:52.094000+00:00)
- where-failed: session_id=01a11126-1859-733e-aae9-d201156d9836 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791289098840 | item_index=92; turn_id=1791289198553 | item_index=194; turn_id=1791289520228 | item_index=0; turn_id=1791291664209 | item_index=26; turn_id=1791291685636 | item_index=0; turn_id=1791308511590 | item_index=26; turn_id=1791308524072 | item_index=0; turn_id=1791311562295 | item_index=26; turn_id=1791311572094
- report generated_at: 2026-10-06T18:33:28.804168+00:00
- usage rows: 161
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 3042252
- output tokens: 162476
- cache-read tokens: 45975737
- cache-write tokens: 0
- hit ratio: 93.7936% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 1973 (state=RESOLVED-BREAKS-OMP; population: 9 of 121160 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoAudioEscopo']; window: 2026-10-06T12:18:18.840000+00:00..2026-10-06T18:32:52.094000+00:00)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

(full report also written to `H:/sotto/_main/audio-escopo-cache.out`)
