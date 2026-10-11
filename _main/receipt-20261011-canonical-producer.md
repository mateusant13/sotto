# Receipt -- T3: does a worker-stamped `producer` ever reach the canonical gate?

Date: 2026-10-11 (America/Sao_Paulo). Lane: T3 (canonical/HISTORY gap).
Owner stop order IN FORCE the whole time: *"para de abrir o sotto, ta travando meu pc quando ele abre."*
Nothing was launched: no `sotto_webview.py`, no `run.cmd`, no worker, no WebView2/GUI probe, no
`_main\_audit-verify-all.cmd`. Every measurement below is static (bytes, parse, grep, sha256) or
in-process (Python `import`, Node `require`, `ast` extraction). Product files were READ ONLY.

## 1. The question, verbatim

> "It is UNMEASURED whether a worker-stamped producer field ever reaches that gate. Decide it by
> reading the code and MEASURING, not by assuming."

**The gate** is `app/panel/history-source.js`: `CANONICAL_PRODUCER = 'redux'` (:51) and
`isCanonicalLine(meta) { return producerOf(meta) === CANONICAL_PRODUCER; }` (:61-63), with
`producerOf` (:54-58) returning a **trimmed** non-empty string or `null` -- fail-closed, nothing is
assumed. `panel.js:recordHistory` (:1298) calls it at :1344-1346 before the store is touched.

## 2. Verdict

**A real worker-stamped producer reaches `meta.producer` TODAY: PARTIALLY.**

* **In code, end to end: YES -- and it is now measured, not assumed.** The REAL worker's batch arm
  stamps `"producer": "redux"` on a REAL `{"type": "caption", ...}` event
  (`worker/sotto_worker.py:3505`); the REAL shell's `WorkerBridge._consume` forwards every key
  except `type`/`text` as `meta` (`app/webview/sotto_webview.py:7457` -> `:7466`); the REAL
  engine CARRIES the tag into a **rebuilt** commit meta (`caption-formulation.js:585`); and the REAL
  gate ACCEPTS that meta. Executed in-process with the live bytes, ARM A/B/C below.
* **In a live run: NO.** The only arm that stamps the field is the Redux batch switch, which is OFF by
  default (`sotto_worker.py:3035`, `REDUX_WHEN_HIDDEN_DEFAULT = False`; nothing in the shell or
  `run.cmd` sets `SOTTO_REDUX_WHEN_HIDDEN` -- grep over the shell returned only doc hits), and whose
  engine cannot load: `worker/models/parakeet-redux-ternary` is **ABSENT** (measured: the only
  directory under `worker/models/` is `nemotron-3.5-asr-streaming-0.6b-int8`). `redux_batch.py`
  (`DEFAULT_MODEL_DIR` at :39, `load_runtime` raising `SystemExit` at :112-119) therefore exits
  before emitting a caption, and the worker queues a `redux-batch-empty` **STATUS** instead
  (`sotto_worker.py:3540-3550`), which never reaches the caption hop at all.

**THE ONE REMAINING GAP: the Redux checkpoint is not on disk, so the batch arm cannot produce the
line that would carry the tag.** Everything downstream of the stamp is provably intact.

**Second, deliberate layer (not the gap, but the reason the gap is dangerous if the flag is flipped):**
the switch's own gate 2 checks the RUNNER FILE, not the weights -- `self.runner_available =
os.path.exists(self.runner)` (`sotto_worker.py:3213`), and `redux_batch.py` DOES exist, so
`armed = True`. With `--redux-when-hidden` the worker then SKIPS the streaming decode while the panel
is hidden (`sotto_worker.py:4836-4842`, `continue`) and every batch fails on the missing checkpoint:
the panel is closed, the only transcriber has been cut, and the failure arrives as a status. That is
verbatim the failure shape the HARD RULE in AGENTS.md was written after. Today the default-OFF flag is
what keeps this from happening.

## 3. The three hops, with file:line re-measured on the live bytes

| hop | what it must do | file:line (re-measured by the oracle, not a hint) | state |
|---|---|---|---|
| (i) | the batch arm queues a `type:"caption"` event with `producer` | `worker/sotto_worker.py:3499` (put) / `:3505` (stamp) / `:3057` (`REDUX_PRODUCER = "redux"`) / `:3440` (`_run_runner`) | **INTACT** |
| (i) | it reaches stdout as one JSON line | `sotto_worker.py:4792` (`for payload in switch.drain_captions()`) -> `:384` (`def emit(**payload)`) | **INTACT** |
| (ii) | the shell forwards it as a caption | `app/webview/sotto_webview.py:7439` (`_consume`) / `:7457` (meta = every key but type/text) / `:7466` (`on_caption(str(text), meta)`) / `:5466` (wired) / `:5552` (`on_worker_caption` -> `emit('caption', {'text','meta'})`) / `:4352` (`SottoShell.emit`) / `:2518` (page `__sotto_emit`) / `:2590` (`onCaption`) | **INTACT** |
| (iii) | the panel passes it through as meta | `app/panel/panel.js:884` (`engineFor(source).ingest(text, meta)`) -> `caption-formulation.js:713` (`rememberProducer(meta)`) -> `:585` (commit literal `{route,start,routeSource,producer:tag}`) -> `panel.js:1298` (`recordHistory`) -> `:1346` (`isCanonical(meta)`) | **INTACT, with a correction (below)** |

**Correction to the brief's hop (iii) wording.** The panel does **not** pass the meta through: the
engine **REBUILDS** it. The object the gate reads is a fresh literal
`{route, start, routeSource, producer}` (`caption-formulation.js:582-588`); the worker's `type`,
`text`, `end`, `producerModel`, `route` and `model` keys are gone. `producer` survives the
rebuild because `rememberProducer`/`committedProducer` (:400-415) carry it when the whole buffer
agreed on one value -- it is **carried, never invented and never defaulted**. The measured commit meta
for the real event is exactly
`{"producer": "redux", "route": "final", "routeSource": "worker-stamped", "start": 1.5}`.

**Correction to the brief's ARM expectation (measured, not assumed).** The brief asks the oracle to
REFUSE `producer:"redux "` (trailing space). The real bytes **TRIM** it
(`history-source.js:56`: `typeof meta.producer === 'string' ? meta.producer.trim() : ''`), so a
padded tag is **ACCEPTED**. The oracle prints this as `BRIEF-DEVIATION` and marks the padded arm
`ACCEPT-BY-TRIM`; encoding the brief's wording as an expectation would have made the oracle red on
the real bytes. The arms that ARE refused, measured: absent, `""`, `null`, non-string,
`"live"`, `"parakeet-tdt"`, `"Redux"`, `"reduxx"`, and `meta:null`.

## 4. Commands run (every one)

Both oracle runs were launched from Node with `windowsHide: true` -- no console was ever shown:

```js
spawnSync("py", ["-3", "H:/sotto/_main/canonical-producer-oracle.py"],           { windowsHide: true, cwd: "H:/sotto" })  // rc 0
spawnSync("py", ["-3", "H:/sotto/_main/canonical-producer-oracle.py", "--red-arm"], { windowsHide: true, cwd: "H:/sotto" })  // rc 1
```

The oracle itself spawns `node` once per arm with `creationflags = CREATE_NO_WINDOW` (0x08000000)
and its stand-in runner is launched by the worker's own `subprocess.run`, which already passes the
same flag. Nothing else was executed.

Static instruments used for the hop trace (all read-only):

| instrument | target | result |
|---|---|---|
| `node` over the bytes + `crypto.createHash("sha256")` | every file in section 7 | the pins below |
| grep `^class ` | `app/webview/sotto_webview.py` | `WorkerBridge` at :6972 |
| grep `def _consume` | `app/webview/sotto_webview.py` | :7439 `def _consume(self, line, child=None)` |
| grep `def emit\|__sotto_emit\|def normalise` | `app/webview/sotto_webview.py` | :2518, :4352, :5948, :1146 |
| grep `isCanonical` | `app/panel/panel.js` | :1344-1346 |
| grep `expireHold\|holdTimer` | `app/panel/panel.js` | :700-712 (`armHoldTimer` -> `engine.expireHold()`) |
| grep `SOTTO_REDUX_WHEN_HIDDEN\|redux-when-hidden` | `app/webview/sotto_webview.py` | doc/comment hits only -- the shell never arms the switch |
| grep `def _write_wav` / `def drain_captions` / `def _run_runner` | `worker/sotto_worker.py` | :3426 / :3568 / :3440 |
| read ranges | `sotto_worker.py` 1-60, 57-115, 3175-3260, 3426-3462, 3476-3560, 4810-4850; `sotto_webview.py` 2505-2600, 4345-4362, 5455-5470, 7439-7580; `caption-formulation.js` 245-300, 380-420, 485-510, 576-600, 660-720, 780-840; `history-store.js` 40-100 | the anchors above |
| `git status --porcelain` (read-only; no git write command was run) | `H:/sotto` | only `?? _main/canonical-producer-oracle.py` is new from this lane; no `app/**` or `worker/**` entry is mine |

## 5. Raw oracle output -- GREEN (`py -3 _main/canonical-producer-oracle.py`, rc=0)

```text
==============================================================================
Sotto T3 -- worker-stamped producer vs the canonical gate
mode: GREEN-ARM (live bytes are the SUBJECT; mutants are NEG arms)
==============================================================================
TMP  G:\Temp\sotto-canonical-producer-5vw17fg1   (never inside the repo)
PIN  H:\sotto\app\panel\history-source.js  3708 B  sha256 75D175863C286A7AA6C105C7E0258A93D4D8EC078208D18438651981C02BD915  mtime 2026-10-07 02:34:30
PIN  H:\sotto\app\panel\caption-formulation.js  40333 B  sha256 6EB5FB8AF421FA26CDAEEF4CF6F37D49F3D0D831B16C9A1C787A9B4816159072  mtime 2026-10-11 18:25:47
PIN  H:\sotto\app\webview\sotto_webview.py  439498 B  sha256 E5B4ADE733BC356294F669E518A50CC0125F163D034242BBBD96229C7FD11E3F  mtime 2026-10-11 18:37:29
PIN  H:\sotto\worker\sotto_worker.py  291873 B  sha256 EFDFB09851CC2BAD2AA344D8C40DBE26FB0EB4FABD93AC39D1C743D898C1DED3  mtime 2026-10-11 18:02:41
PIN  H:\sotto\app\panel\panel.js  137352 B  sha256 A0BE06942EEA066A19E04677DF52D200F858CBBC7B514C88193AEE24224B3928  mtime 2026-10-11 18:33:58
PIN  H:\sotto\app\panel\history-store.js  9150 B  sha256 F13A843C42972AFDE17AC8DE23E052384B34A4413EC94542EC7B4C3EBB0AF6F3  mtime 2026-10-07 02:01:27
PIN  H:\sotto\worker\redux_batch.py  8559 B  sha256 C5D44F93C4AA3DA7905FEF5A40A61464E3D165BEABF3C57A139D9AA0C9DEA989  mtime 2026-10-07 04:39:45

-- MUTANT CUTS (a copy that is byte-identical is not a mutant) ------------------
ok   [NEG] M-gate mutant differs from the live bytes  -- delta_bytes=8
ok   [NEG] M-worker mutant differs from the live bytes  -- delta_bytes=-61
ok   [NEG] M-shell mutant differs from the live bytes  -- delta_bytes=12

-- ANCHORS (re-measured on the live bytes) ----------------------------------
HOP  worker constant REDUX_PRODUCER  H:\sotto\worker\sotto_worker.py:3057
HOP  worker stamps producer on the caption  H:\sotto\worker\sotto_worker.py:3505
HOP  worker queues the batch caption  H:\sotto\worker\sotto_worker.py:3499
HOP  worker _run_runner  H:\sotto\worker\sotto_worker.py:3440
HOP  worker emit(**payload)  H:\sotto\worker\sotto_worker.py:384
HOP  worker drains the switch into emit  H:\sotto\worker\sotto_worker.py:4792
HOP  worker flag default OFF  H:\sotto\worker\sotto_worker.py:3035
HOP  worker flag opt-in  H:\sotto\worker\sotto_worker.py:4960
HOP  worker arms on the RUNNER FILE only  H:\sotto\worker\sotto_worker.py:3213
HOP  worker SKIPS streaming while mode==batch  H:\sotto\worker\sotto_worker.py:4836
HOP  shell WorkerBridge._consume  H:\sotto\app\webview\sotto_webview.py:7439
HOP  shell builds the caption meta  H:\sotto\app\webview\sotto_webview.py:7457
HOP  shell forwards to on_caption  H:\sotto\app\webview\sotto_webview.py:7466
HOP  shell wires on_caption  H:\sotto\app\webview\sotto_webview.py:5466
HOP  shell on_worker_caption emits  H:\sotto\app\webview\sotto_webview.py:5552
HOP  shell emit() pushes into the page  H:\sotto\app\webview\sotto_webview.py:4352
HOP  page __sotto_emit  H:\sotto\app\webview\sotto_webview.py:2518
HOP  page onCaption subscription  H:\sotto\app\webview\sotto_webview.py:2590
HOP  panel ingests into the per-source engine  H:\sotto\app\panel\panel.js:884
HOP  panel recordHistory  H:\sotto\app\panel\panel.js:1298
HOP  panel calls the canonical gate  H:\sotto\app\panel\panel.js:1346
HOP  engine remembers the producer  H:\sotto\app\panel\caption-formulation.js:713
HOP  engine commits the producer tag  H:\sotto\app\panel\caption-formulation.js:585
HOP  engine routeSourceFor  H:\sotto\app\panel\caption-formulation.js:501
HOP  redux runner default model dir  H:\sotto\worker\redux_batch.py:39

-- ARM A: the REAL app/panel/history-source.js through require ---------------
NODE v24.8.0
ok   [A] producer:'redux' (the worker's stamp) -> ACCEPT  -- got=True producerOf='redux' (the canonical tag)
ok   [A] producer absent -> REFUSE  -- got=False producerOf=None (fail-closed: nothing is assumed)
ok   [A] producer:'' (empty string) -> REFUSE  -- got=False producerOf=None (fail-closed)
ok   [A] producer:null -> REFUSE  -- got=False producerOf=None (non-string)
ok   [A] producer:42 (non-string) -> REFUSE  -- got=False producerOf=None (non-string)
ok   [A] meta:null -> REFUSE  -- got=False producerOf=None (fail-closed)
ok   [A] producer:'live' -> REFUSE  -- got=False producerOf='live' (the live engine's tag)
ok   [A] producer:'parakeet-tdt' -> REFUSE  -- got=False producerOf='parakeet-tdt' (the brief's arm -- REFUSED)
ok   [A] producer:'Redux' (case) -> REFUSE  -- got=False producerOf='Redux' (case-sensitive)
ok   [A] producer:'reduxx' -> REFUSE  -- got=False producerOf='reduxx' (unknown tag)
ok   [A] producer:'redux ' (trailing space) -> ACCEPT  -- got=True producerOf='redux' (ACCEPT-BY-TRIM -- see BRIEF-DEVIATION)
ok   [A] producer:'  redux\n' (padding) -> ACCEPT  -- got=True producerOf='redux' (ACCEPT-BY-TRIM)
     BRIEF-DEVIATION: the brief asks this oracle to REFUSE producer:'redux ' (trailing space).
     The REAL bytes TRIM it (history-source.js producerOf: typeof meta.producer === 'string' ? meta.producer.trim() : ''),
     so a padded tag is ACCEPTED. Measured, not asserted -- encoding the brief's wording as an expectation would make this oracle red on the real bytes.

-- ARM B: the REAL worker/sotto_worker.py, imported IN PROCESS ------------
ok   [B] the worker module imports in process (no launch, no capture)  -- H:\sotto\worker\sotto_worker.py
ok   [B] the REAL _run_runner queues exactly one event  -- queued=1 logs=['REDUX_BATCH_DONE reason=oracle audio_s=1.0 lines=1 rc=0 segments=1 wall_s=0.06 timeout_s=180.0']
     REAL EVENT: {"end": 3.0, "final": true, "producer": "redux", "producerModel": "standin", "route": "redux-batch", "start": 1.5, "text": "bom dia, mundo", "type": "caption"}
ok   [B] hop (i): the queued event's type IS 'caption'  -- type='caption'
ok   [B] the queued event carries producer == 'redux'  -- producer='redux'
ok   [B] the queued event votes final:true (the worker closed the line)  -- final=True
ok   [B] the queued event carries NO 'source' key (it lands on the no-source engine)  -- keys=end,final,producer,producerModel,route,start,text,type
     EMPTY-BATCH EVENT: {"audio_s": 1.0, "detail": "the batch engine ran over 1.0s of accumulated audio and emitted no caption (rc=0); the panel is hidden and this is the only transcriber running", "producer": "redux", "state": "redux-batch-empty", "type": "status"}
ok   [B] an empty batch queues a STATUS, never a caption  -- type='status' state='redux-batch-empty'
ok   [B] the status also carries producer (but a status never reaches the caption hop)  -- producer='redux'
ok   [B] LIVE-GAP PINNED: the checkpoint the runner defaults to is ABSENT today  -- default=H:\sotto\worker\models\parakeet-redux-ternary exists=False -- if this ever goes green the ANSWER below changes: re-read it
       redux_batch.py load_runtime raises SystemExit when config.json / model.safetensors / ternary.json are missing, so the batch arm cannot emit a caption today
ok   [B] the switch ARMS on the RUNNER FILE even when no checkpoint exists  -- runner_available=True armed=True -- gate 2 checks the .py, not the weights

-- ARM C: worker event -> REAL shell _consume -> REAL engine -> REAL gate ----
ok   [C] the REAL shell _consume yields exactly one caption  -- captions=1 malformed=0
     SHELL META: {"end": 3.0, "final": true, "producer": "redux", "producerModel": "standin", "route": "redux-batch", "start": 1.5}
ok   [C] hop (ii): the shell's meta still carries producer == 'redux'  -- producer='redux'
ok   [C] the shell's meta drops ONLY type/text (the worker's event keys survive)  -- meta keys=end,final,producer,producerModel,route,start
ok   [C] the REAL engine commits the batch line once  -- commits=1 visible=''
     ENGINE COMMIT META: {"producer": "redux", "route": "final", "routeSource": "worker-stamped", "start": 1.5}
ok   [C] hop (iii): the gate is fed a REBUILT meta, not the worker's event  -- keys=producer,route,routeSource,start
ok   [C] the REBUILT meta carries producer == 'redux' (carried, not invented)  -- producer='redux'
ok   [C] the REBUILT meta routes final via the worker's flag  -- route='final' routeSource='worker-stamped'
ok   [C] END-TO-END: the REAL gate ACCEPTS the line the REAL worker stamped  -- accepted=[True]
ok   [C] CONTROL: a line routed final with NO producer is REFUSED by the PRODUCER guard  -- accepted=[False] route='final' routeSource='worker-stamped' meta={"route": "final", "routeSource": "worker-stamped", "start": 1.5}
ok   [C] CONTROL: a final:false line is refused EARLIER, by the route guard  -- accepted=[False] route='provisional-draft'
ok   [C] SECOND-ORDER FINDING: the tag is per BUFFER, not per line -- a fragment that declares nothing inherits it  -- accepted=[True] meta={"producer": "redux", "route": "final", "routeSource": "worker-stamped", "start": 1.5} -- sticky bufferSawProducer, no conflict, so a line whose FIRST fragment was the live pass is accepted as canonical; reported, not fixed here
ok   [C] FINDING (latent): the store's src= allow-list omits 'worker-stamped-producer'  -- history-store.js ROUTE_SOURCES does not list the value caption-formulation.js:501 returns for a producer-stamped line with NO final flag, so such a line would be written with NO src= marker; LATENT today because panel.js:1330 stops a non-final route before the store is reached

-- NEG ARMS: each hop cut in a COPY of the REAL bytes (must go RED) ---
ok   [NEG] the three mutant copies live OUTSIDE the repo  -- G:\Temp\sotto-canonical-producer-5vw17fg1
ok   [NEG] M1 gate mutant (CANONICAL_PRODUCER renamed): the ACCEPT arm goes RED  -- accept=False
ok   [NEG] M1 leaves the fail-closed arm RED too (no accidental acceptance)  -- accept=False
     MUTANT EVENT: {"end": 3.0, "final": true, "producerModel": "standin", "route": "redux-batch", "start": 1.5, "text": "bom dia, mundo", "type": "caption"}
ok   [NEG] M2 worker mutant (stamp line removed): the producer arm goes RED  -- type='caption' producer=None
ok   [NEG] M2 END-TO-END with the LIVE gate: the chain goes RED  -- accepted=[False] meta={"route": "final", "routeSource": "worker-stamped", "start": 1.5}
ok   [NEG] M3 shell mutant (projection drops producer): the shell hop goes RED  -- meta keys=end,final,producerModel,route,start
ok   [NEG] M3 END-TO-END with the LIVE gate: the chain goes RED  -- accepted=[False] meta={"route": "final", "routeSource": "worker-stamped", "start": 1.5}
ok   [NEG] the LIVE bytes were never written (the repo copies are untouched)

==============================================================================
ANSWER (the plain reading of the measurements above)
==============================================================================
A worker-stamped producer reaches meta.producer TODAY: PARTIALLY.
  * IN CODE, end to end: YES. The worker stamps producer:'redux' on a real type:'caption' event
    (worker/sotto_worker.py:3505), the shell forwards the whole meta (sotto_webview.py:7457 -> :7466),
    the engine CARRIES it into a REBUILT meta (caption-formulation.js:585), and the REAL gate accepts that meta.
  * IN A LIVE RUN: NO. The only arm that stamps it is the Redux batch switch, which is OFF by default
    (sotto_worker.py:3035) and whose engine cannot load: worker/models/parakeet-redux-ternary
    is ABSENT, so redux_batch.py exits before emitting a caption and the worker queues a redux-batch-empty STATUS instead.
  * THE ONE REMAINING GAP: the Redux checkpoint is not on disk, so the batch arm cannot produce the line.
    (Second, deliberate layer: the flag is OFF, and the switch's own gate sotto_worker.py:3213 checks
     the RUNNER FILE, not the weights -- armed with --redux-when-hidden it cuts streaming while the panel is hidden
     (sotto_worker.py:4836) and then fails every batch, which is the HARD RULE's failure shape.)
NOT MEASURED (and why): no live end-to-end run is permitted by the owner's stop order, so no real
  worker-stamped caption was OBSERVED on stdout; the batch commit was forced by the engine's own
  flush('hold-timeout') (panel.js:700-712 armHoldTimer -> expireHold); WebView2 timer throttling and
  the real runner's RSS are untouched here.

==============================================================================
SUMMARY: 45/45 checks green; failed=[]
VERDICT: PASS
==============================================================================
```

## 6. Raw oracle output -- RED (`py -3 _main/canonical-producer-oracle.py --red-arm`, rc=1)

The SAME checks, with the mutants as the SUBJECT: the gate renamed, the worker stamp removed, the
shell projection cut. 9 of 37 checks fail and the verdict flips -- the proof the oracle can say NO.

```text
==============================================================================
Sotto T3 -- worker-stamped producer vs the canonical gate
mode: RED-ARM (mutants are the SUBJECT)
==============================================================================
TMP  G:\Temp\sotto-canonical-producer-b90ehjyr   (never inside the repo)
PIN  H:\sotto\app\panel\history-source.js  3708 B  sha256 75D175863C286A7AA6C105C7E0258A93D4D8EC078208D18438651981C02BD915  mtime 2026-10-07 02:34:30
PIN  H:\sotto\app\panel\caption-formulation.js  40333 B  sha256 6EB5FB8AF421FA26CDAEEF4CF6F37D49F3D0D831B16C9A1C787A9B4816159072  mtime 2026-10-11 18:25:47
PIN  H:\sotto\app\webview\sotto_webview.py  439498 B  sha256 E5B4ADE733BC356294F669E518A50CC0125F163D034242BBBD96229C7FD11E3F  mtime 2026-10-11 18:37:29
PIN  H:\sotto\worker\sotto_worker.py  291873 B  sha256 EFDFB09851CC2BAD2AA344D8C40DBE26FB0EB4FABD93AC39D1C743D898C1DED3  mtime 2026-10-11 18:02:41
PIN  H:\sotto\app\panel\panel.js  137352 B  sha256 A0BE06942EEA066A19E04677DF52D200F858CBBC7B514C88193AEE24224B3928  mtime 2026-10-11 18:33:58
PIN  H:\sotto\app\panel\history-store.js  9150 B  sha256 F13A843C42972AFDE17AC8DE23E052384B34A4413EC94542EC7B4C3EBB0AF6F3  mtime 2026-10-07 02:01:27
PIN  H:\sotto\worker\redux_batch.py  8559 B  sha256 C5D44F93C4AA3DA7905FEF5A40A61464E3D165BEABF3C57A139D9AA0C9DEA989  mtime 2026-10-07 04:39:45

-- MUTANT CUTS (a copy that is byte-identical is not a mutant) ------------------
ok   [NEG] M-gate mutant differs from the live bytes  -- delta_bytes=8
ok   [NEG] M-worker mutant differs from the live bytes  -- delta_bytes=-61
ok   [NEG] M-shell mutant differs from the live bytes  -- delta_bytes=12

-- ANCHORS (re-measured on the live bytes) ----------------------------------
HOP  worker constant REDUX_PRODUCER  H:\sotto\worker\sotto_worker.py:3057
HOP  worker stamps producer on the caption  H:\sotto\worker\sotto_worker.py:3505
HOP  worker queues the batch caption  H:\sotto\worker\sotto_worker.py:3499
HOP  worker _run_runner  H:\sotto\worker\sotto_worker.py:3440
HOP  worker emit(**payload)  H:\sotto\worker\sotto_worker.py:384
HOP  worker drains the switch into emit  H:\sotto\worker\sotto_worker.py:4792
HOP  worker flag default OFF  H:\sotto\worker\sotto_worker.py:3035
HOP  worker flag opt-in  H:\sotto\worker\sotto_worker.py:4960
HOP  worker arms on the RUNNER FILE only  H:\sotto\worker\sotto_worker.py:3213
HOP  worker SKIPS streaming while mode==batch  H:\sotto\worker\sotto_worker.py:4836
HOP  shell WorkerBridge._consume  H:\sotto\app\webview\sotto_webview.py:7439
HOP  shell builds the caption meta  H:\sotto\app\webview\sotto_webview.py:7457
HOP  shell forwards to on_caption  H:\sotto\app\webview\sotto_webview.py:7466
HOP  shell wires on_caption  H:\sotto\app\webview\sotto_webview.py:5466
HOP  shell on_worker_caption emits  H:\sotto\app\webview\sotto_webview.py:5552
HOP  shell emit() pushes into the page  H:\sotto\app\webview\sotto_webview.py:4352
HOP  page __sotto_emit  H:\sotto\app\webview\sotto_webview.py:2518
HOP  page onCaption subscription  H:\sotto\app\webview\sotto_webview.py:2590
HOP  panel ingests into the per-source engine  H:\sotto\app\panel\panel.js:884
HOP  panel recordHistory  H:\sotto\app\panel\panel.js:1298
HOP  panel calls the canonical gate  H:\sotto\app\panel\panel.js:1346
HOP  engine remembers the producer  H:\sotto\app\panel\caption-formulation.js:713
HOP  engine commits the producer tag  H:\sotto\app\panel\caption-formulation.js:585
HOP  engine routeSourceFor  H:\sotto\app\panel\caption-formulation.js:501
HOP  redux runner default model dir  H:\sotto\worker\redux_batch.py:39

-- ARM A: the REAL app/panel/history-source.js through require ---------------
NODE v24.8.0
FAIL [A] producer:'redux' (the worker's stamp) -> ACCEPT  -- got=False producerOf='redux' (the canonical tag)
ok   [A] producer absent -> REFUSE  -- got=False producerOf=None (fail-closed: nothing is assumed)
ok   [A] producer:'' (empty string) -> REFUSE  -- got=False producerOf=None (fail-closed)
ok   [A] producer:null -> REFUSE  -- got=False producerOf=None (non-string)
ok   [A] producer:42 (non-string) -> REFUSE  -- got=False producerOf=None (non-string)
ok   [A] meta:null -> REFUSE  -- got=False producerOf=None (fail-closed)
ok   [A] producer:'live' -> REFUSE  -- got=False producerOf='live' (the live engine's tag)
ok   [A] producer:'parakeet-tdt' -> REFUSE  -- got=False producerOf='parakeet-tdt' (the brief's arm -- REFUSED)
ok   [A] producer:'Redux' (case) -> REFUSE  -- got=False producerOf='Redux' (case-sensitive)
ok   [A] producer:'reduxx' -> REFUSE  -- got=False producerOf='reduxx' (unknown tag)
FAIL [A] producer:'redux ' (trailing space) -> ACCEPT  -- got=False producerOf='redux' (ACCEPT-BY-TRIM -- see BRIEF-DEVIATION)
FAIL [A] producer:'  redux\n' (padding) -> ACCEPT  -- got=False producerOf='redux' (ACCEPT-BY-TRIM)

-- ARM B: the REAL worker/sotto_worker.py, imported IN PROCESS ------------
ok   [B] the worker module imports in process (no launch, no capture)  -- G:\Temp\sotto-canonical-producer-b90ehjyr\sotto_worker.mutant.py
ok   [B] the REAL _run_runner queues exactly one event  -- queued=1 logs=['REDUX_BATCH_DONE reason=oracle audio_s=1.0 lines=1 rc=0 segments=1 wall_s=0.06 timeout_s=180.0']
     REAL EVENT: {"end": 3.0, "final": true, "producerModel": "standin", "route": "redux-batch", "start": 1.5, "text": "bom dia, mundo", "type": "caption"}
ok   [B] hop (i): the queued event's type IS 'caption'  -- type='caption'
FAIL [B] the queued event carries producer == 'redux'  -- producer=None
ok   [B] the queued event votes final:true (the worker closed the line)  -- final=True
ok   [B] the queued event carries NO 'source' key (it lands on the no-source engine)  -- keys=end,final,producerModel,route,start,text,type
     EMPTY-BATCH EVENT: {"audio_s": 1.0, "detail": "the batch engine ran over 1.0s of accumulated audio and emitted no caption (rc=0); the panel is hidden and this is the only transcriber running", "producer": "redux", "state": "redux-batch-empty", "type": "status"}
ok   [B] an empty batch queues a STATUS, never a caption  -- type='status' state='redux-batch-empty'
ok   [B] the status also carries producer (but a status never reaches the caption hop)  -- producer='redux'
ok   [B] LIVE-GAP PINNED: the checkpoint the runner defaults to is ABSENT today  -- default=H:\sotto\worker\models\parakeet-redux-ternary exists=False -- if this ever goes green the ANSWER below changes: re-read it
       redux_batch.py load_runtime raises SystemExit when config.json / model.safetensors / ternary.json are missing, so the batch arm cannot emit a caption today
ok   [B] the switch ARMS on the RUNNER FILE even when no checkpoint exists  -- runner_available=True armed=True -- gate 2 checks the .py, not the weights

-- ARM C: worker event -> REAL shell _consume -> REAL engine -> REAL gate ----
ok   [C] the REAL shell _consume yields exactly one caption  -- captions=1 malformed=0
     SHELL META: {"end": 3.0, "final": true, "producerModel": "standin", "route": "redux-batch", "start": 1.5}
FAIL [C] hop (ii): the shell's meta still carries producer == 'redux'  -- producer=None
ok   [C] the shell's meta drops ONLY type/text (the worker's event keys survive)  -- meta keys=end,final,producerModel,route,start
ok   [C] the REAL engine commits the batch line once  -- commits=1 visible=''
     ENGINE COMMIT META: {"route": "final", "routeSource": "worker-stamped", "start": 1.5}
FAIL [C] hop (iii): the gate is fed a REBUILT meta, not the worker's event  -- keys=route,routeSource,start
FAIL [C] the REBUILT meta carries producer == 'redux' (carried, not invented)  -- producer=None
ok   [C] the REBUILT meta routes final via the worker's flag  -- route='final' routeSource='worker-stamped'
FAIL [C] END-TO-END: the REAL gate ACCEPTS the line the REAL worker stamped  -- accepted=[False]
ok   [C] CONTROL: a line routed final with NO producer is REFUSED by the PRODUCER guard  -- accepted=[False] route='final' routeSource='worker-stamped' meta={"route": "final", "routeSource": "worker-stamped", "start": 1.5}
ok   [C] CONTROL: a final:false line is refused EARLIER, by the route guard  -- accepted=[False] route='provisional-draft'
FAIL [C] SECOND-ORDER FINDING: the tag is per BUFFER, not per line -- a fragment that declares nothing inherits it  -- accepted=[False] meta={"producer": "redux", "route": "final", "routeSource": "worker-stamped", "start": 1.5} -- sticky bufferSawProducer, no conflict, so a line whose FIRST fragment was the live pass is accepted as canonical; reported, not fixed here
ok   [C] FINDING (latent): the store's src= allow-list omits 'worker-stamped-producer'  -- history-store.js ROUTE_SOURCES does not list the value caption-formulation.js:501 returns for a producer-stamped line with NO final flag, so such a line would be written with NO src= marker; LATENT today because panel.js:1330 stops a non-final route before the store is reached

==============================================================================
ANSWER (the plain reading of the measurements above)
==============================================================================
A worker-stamped producer reaches meta.producer TODAY: PARTIALLY.
  * IN CODE, end to end: YES. The worker stamps producer:'redux' on a real type:'caption' event
    (worker/sotto_worker.py:3505), the shell forwards the whole meta (sotto_webview.py:7457 -> :7466),
    the engine CARRIES it into a REBUILT meta (caption-formulation.js:585), and the REAL gate accepts that meta.
  * IN A LIVE RUN: NO. The only arm that stamps it is the Redux batch switch, which is OFF by default
    (sotto_worker.py:3035) and whose engine cannot load: worker/models/parakeet-redux-ternary
    is ABSENT, so redux_batch.py exits before emitting a caption and the worker queues a redux-batch-empty STATUS instead.
  * THE ONE REMAINING GAP: the Redux checkpoint is not on disk, so the batch arm cannot produce the line.
    (Second, deliberate layer: the flag is OFF, and the switch's own gate sotto_worker.py:3213 checks
     the RUNNER FILE, not the weights -- armed with --redux-when-hidden it cuts streaming while the panel is hidden
     (sotto_worker.py:4836) and then fails every batch, which is the HARD RULE's failure shape.)
NOT MEASURED (and why): no live end-to-end run is permitted by the owner's stop order, so no real
  worker-stamped caption was OBSERVED on stdout; the batch commit was forced by the engine's own
  flush('hold-timeout') (panel.js:700-712 armHoldTimer -> expireHold); WebView2 timer throttling and
  the real runner's RSS are untouched here.

==============================================================================
RED-ARM SUMMARY: 9 of 37 checks FAILED against the mutant subject (this is the expected colour).
VERDICT: FAIL
==============================================================================
```

## 7. Second-order findings (measured, reported, NOT fixed here)

1. **The switch arms on the runner FILE, not the weights** (`sotto_worker.py:3213`, measured:
   `runner_available=True armed=True` with the checkpoint absent). Consequence in section 2.
2. **The producer tag is per BUFFER, not per line** (`caption-formulation.js:400-415`): a fragment
   that declares NOTHING does not block the tag -- `bufferSawProducer` is sticky and there is no
   conflict when only one fragment speaks. Measured: a live fragment (`{start:1.5, final:true}`, no
   producer) followed by a `redux` fragment of the same line commits as `producer:"redux"` and the
   gate ACCEPTS the line, although its first fragment came from the live pass. Reported, not fixed:
   whether this can happen in a live run depends on the batch/live interleaving, which is exactly what
   the stop order forbids measuring.
3. **The store's `src=` allow-list omits `'worker-stamped-producer'`** --
   `history-store.js:51` `ROUTE_SOURCES = ['worker-stamped', 'panel-deadline', 'fallback']` vs
   `caption-formulation.js:501` which returns `'worker-stamped-producer'` for a producer-stamped
   line with NO final flag. **Latent today**: `panel.js:1330` stops a non-`final` route before the
   store is reached, and a final line gets `'worker-stamped'`, which IS listed. It becomes live the
   day a canonical line reaches the store without `final`.
4. **The batch caption carries NO `source` key** (measured on the real event: keys are
   `end,final,producer,producerModel,route,start,text,type`), so it lands on the panel's no-source
   engine, not on a per-app engine.

## 8. The owner fork (evidence for both exits; the Lead decides, this lane does not)

* **Keep the literal `"redux"`** -- truthful only while the finisher IS `moondream/parakeet-redux`.
  Evidence for: the worker's own constant is `REDUX_PRODUCER = "redux"` (`sotto_worker.py:3057`),
  the runner's is `PRODUCER = "redux"` (`redux_batch.py:40`), and the batch route is named
  `"redux-batch"` (`sotto_worker.py:3508`).
* **Rename to `"canonical-tdt"`** -- `redux_batch.py`'s own docstring (:4-7) says it runs the ternary
  re-quantisation of `nvidia/parakeet-tdt-0.6b-v3`, i.e. the tag would name a model the finisher is
  not. A rename must land in ONE edit: `history-source.js:51`, `panel.js:1359` (`source:'redux'`),
  `sotto_worker.py:3057`, `redux_batch.py:40`, and this oracle. Simulated, not performed: the
  M-gate mutant renames only `history-source.js:51` and the ACCEPT arm goes RED -- measured evidence
  that a half-rename is caught by this instrument.

## 9. Artefacts (size / sha256 / mtime)

| what | path | size | sha256 | mtime (UTC) |
|---|---|---|---|---|
| T3 oracle (NEW) | `H:/sotto/_main/canonical-producer-oracle.py` | 37969 B | `3EE12D05CCF3D2C49A04757744A04F5F7E52A36E43961FB68F2AE897F743844A` | 2026-10-11T22:13:55.216Z |
| gate under test | `H:/sotto/app/panel/history-source.js` | 3708 B | `75D175863C286A7AA6C105C7E0258A93D4D8EC078208D18438651981C02BD915` | 2026-10-07T05:34:30.467Z |
| engine under test | `H:/sotto/app/panel/caption-formulation.js` | 40333 B | `6EB5FB8AF421FA26CDAEEF4CF6F37D49F3D0D831B16C9A1C787A9B4816159072` | 2026-10-11T21:25:47.676Z |
| panel choke point | `H:/sotto/app/panel/panel.js` | 137352 B | `A0BE06942EEA066A19E04677DF52D200F858CBBC7B514C88193AEE24224B3928` | 2026-10-11T21:33:58.762Z |
| store (finding 3) | `H:/sotto/app/panel/history-store.js` | 9150 B | `F13A843C42972AFDE17AC8DE23E052384B34A4413EC94542EC7B4C3EBB0AF6F3` | 2026-10-07T05:01:27.339Z |
| shell hop | `H:/sotto/app/webview/sotto_webview.py` | 439498 B | `E5B4ADE733BC356294F669E518A50CC0125F163D034242BBBD96229C7FD11E3F` | 2026-10-11T21:37:29.904Z |
| worker under test | `H:/sotto/worker/sotto_worker.py` | 291873 B | `EFDFB09851CC2BAD2AA344D8C40DBE26FB0EB4FABD93AC39D1C743D898C1DED3` | 2026-10-11T21:02:41.872Z |
| batch runner | `H:/sotto/worker/redux_batch.py` | 8559 B | `C5D44F93C4AA3DA7905FEF5A40A61464E3D165BEABF3C57A139D9AA0C9DEA989` | 2026-10-07T07:39:45.586Z |
| raw GREEN output | `G:/Temp/oracle-green.txt` | 12551 B | `6D11D0CD6747AD29F6021B7C03E010D83450FCD1D5BCDBE782148CBCAA8EA09A` | 2026-10-11T22:14:03.633Z |
| raw RED output | `G:/Temp/oracle-red.txt` | 10985 B | `E652096F6B16BAB64BA8689547B1DF9CECC6D02AEB47B22F872D7F317B83C661` | 2026-10-11T22:14:07.402Z |

`worker/models/` measured contents: **exactly one** entry, `nemotron-3.5-asr-streaming-0.6b-int8`.
`parakeet-redux-ternary` and `parakeet-redux-onnx-int4` are both ABSENT.
Repo HEAD at measurement time: `36cffbd5330a011e9fc1d9adc9e2530e9244b60c` (2026-10-11 19:11:36 -03:00).

## 10. NOT MEASURED (explicit)

* **No live end-to-end run was performed** (owner stop order). No worker-stamped caption was OBSERVED
  on a real stdout; the end-to-end arm is in-process, with the REAL `_run_runner` and a stand-in
  runner in `%TEMP%` that deliberately omits `producer`, so what was read back is the worker's own
  stamp.
* The commit in ARM C is forced by the engine's own `flush('hold-timeout')` (the panel's real
  deadline path, `panel.js:700-712` -> `expireHold`), not by a real fragment arriving.
* WebView2 timer throttling of a hidden panel's hold timer; the real `redux_batch.py` runtime (RSS,
  RTF, its own `producer` stamp at :189); whether the missing checkpoint is recoverable by
  re-download; the live interleaving behind finding 2; whether `history/` ever received a
  producer-stamped line (the archive's `src=` markers are a DIFFERENT field and were not read as
  `producer`).
* Whether the panel PAINTS any of this: the DOM was not touched.

## 11. Rules compliance

* `app/**` and `worker/**`: READ ONLY -- no edit, and the oracle re-verifies their sha256 before it
  exits (last NEG check: "the LIVE bytes were never written").
* No `.cmd` file was written; `_main\_audit-verify-all.cmd` was not run; no git write command was
  run (`git status --porcelain` only).
* Mutants live in memory or in `%TEMP%` (`sotto-canonical-producer-*`) and are deleted at the end of
  the run; the repo never held one.
* Two files delivered: this receipt and `_main/canonical-producer-oracle.py`.

**Self-pin.** A file cannot contain the sha256 of itself, so this receipt's own size / sha256 / mtime
is reported in the lane's delivery message to the Lead, measured AFTER this line was written; re-measure
it with `node -e "const c=require('crypto'),f=require('fs');const b=f.readFileSync('H:/sotto/_main/receipt-20261011-canonical-producer.md');console.log(b.length,c.createHash('sha256').update(b).digest('hex').toUpperCase(),f.statSync('H:/sotto/_main/receipt-20261011-canonical-producer.md').mtime.toISOString())"`.
