# SPEC 07 — THE ENGINE PROCESS

Spec 07 of the build-order specs. Subject: the **Python Engine** on branch `feat/engine-process` at commit `0e1b7f5b2806a48a92dcfbe3841cd01f812652c6` ("LANE A - THE ENGINE PROCESS", 2026-10-09 18:48:47 -0300).

Evidence tags used throughout, and only these:

* **READ** — read from the object store or a file on disk, cited as `file:line` plus blob sha and byte size. A READ is not a run.
* **MEASURED** — this lane ran it and gives the command and the ISO-2026 instant.
* **UNKNOWN** — the question is open; the settling experiment is named.
* **NOT BUILT** — the code or artifact does not exist in this checkout.

The clip/ASR arms lane specs-05-07 actually ran are recorded separately in `P4-specs-evidence-20261009.md` (commit f8cdb01). This spec does not repeat those numbers.

---

## 0 · THE DECISION

The shipped answer to "who owns the machine while nobody is looking" is a single Python supervisor process, `src/engine/engine.py`, that is simultaneously the owner of the ring buffer, the parent of the capture process, the keeper of a SQLite spine, and the door a UI child dials. It is deliberately *not* the Rust core the design notes promise — the file says so about itself (`engine.py:11-13`): the divergences from the long-term core "are listed in the receipt (accepted, not accidental)". What this spec records is the contract as it exists on `0e1b7f5`: the exit codes, the wire protocol, the row-before-bytes durability rule, the six gate arms and the red controls that make them non-vacuous. What it also records, with equal weight, is what the shipped code does **not** support: nothing here runs the real capture binary in this worktree, the WASAPI audio cutover to the ASR side is still a design document, and no engine-lane receipt has been committed — so every engine number in this file is a READ from source, never a measurement by this lane.

---

## 1 · THE SUBJECT

### 1.1 The files, as they exist on the branch

READ `git ls-tree -r -l 0e1b7f5 -- _moved/aireplay/src/engine` (2026-10-10); bytes are blob sizes, full citations in §15:

| file | bytes | lines | role |
|---|---|---|---|
| `engine.py` | 44913 | 1063 | the Engine process itself |
| `protocol.py` | 5505 | 139 | the wire rules, machine-side |
| `store.py` | 7223 | 160 | the SQLite spine |
| `schema.sql` | 3380 | 80 | the spine DDL |
| `capture_child.py` | 7872 | 224 | supervisor for the capture process |
| `asr_worker.py` | 8793 | 247 | bounded ASR worker |
| `ui_child.py` | 7427 | — | the door a UI dials (demo child) |
| `stub_capture.py` | 9394 | — | STUB capture child, labelled STUB |
| `stub_asr.py` | 2736 | — | STUB ASR child (stall and rc 2) |
| `test_engine.py` | 37621 | 854 | the gate, both colours |
| `json.h` / `json.cpp` | 2725 / 6934 | — | the C++ envelope parser (older revision, §14.1) |
| `queue.h` / `queue.cpp` | 3101 / 3467 | — | the C++ ring (older revision, §14.1) |

### 1.2 What the Engine is

READ `engine.py:1-29`. The docstring states the position:

* `:2` "THE ENGINE PROCESS -- single supervisor, owner of the ring, parent of capture".
* `:7-9` the UI is a CHILD that attaches and detaches; the ring retains the last 100 events so a reconnecting UI is made consistent by replay, not by luck.
* `:11-13` "It is NOT the long-term Rust core … the divergences are listed in the receipt (accepted, not accidental)".
* `:18-20` "It does NOT require WGC … no screen capture, no window". The Engine never puts a pixel on the owner's screen.
* `:22-28` the exit-code contract, reproduced in §2.2.

READ `engine.py:94-128`. `Ring` is a `collections.deque(maxlen=100)` (`:97`) with a `dropped` counter (`:98`), a monotonic `next_id` (`:99`) and a lock (`:100`). `append` increments `dropped` at capacity (`:104-105`) and mints the event id (`:106-107`): **the id is the order, and the order is the cursor**. `since(since_id)` (`:111-117`) returns the events with a larger id plus the oldest id still retained and the newest. `snapshot` (`:119-128`) exposes `size, capacity, dropped, oldest_id, newest_id, next_id` — the health payload's ring half.

### 1.3 What the Engine is not

* **Not the owner of the keyboard.** READ: no `RegisterHotKey`, no `VK_*` and no hook anywhere in `src/engine/*.py` on this branch — a grep over the Python files returns only prose and reason labels (`engine.py:25-26`, `:458`, `:629`, `:703`, `:752`; `stub_capture.py:172-175`; `test_engine.py:17`). The replay hotkey belongs to the capture child spawned with `--cut-session` (`engine.py:679`); `cut("hotkey")` at `:629` is the *reason label* of a timer-driven cut, the gate's "the 'hotkey' arm without a keyboard" (`:458`). An Engine that owns Alt+Shift+F10 itself is UNKNOWN (§13).
* **Not a screen capture.** `:18-20` above. The WGC block measured 2026-10-07 (`E_ACCESSDENIED` `0x80070005` on every capture item, registry policy Allow) is a capture-side fact, not an Engine one.
* **Not the index.** The Engine's spine is its own SQLite file (`engine-spine.db`), separate from lane B's index; the one thing they are required to agree on is `content_key`, the whole-file SHA-256 (`store.py:8-10`).

---

## 2 · CLI AND EXIT CODES

### 2.1 The command line as it ships

READ `engine.py:441-480`, `prog="engine.py"`. The shipped help, trimmed:

| flag | default | meaning |
|---|---|---|
| `--capture exe|stub` | `exe` | which capture child to supervise (a stub is labelled STUB everywhere) |
| `--capture-exe` | `_main/build/aireplay-capture.exe` under the repo root | the real child |
| `--capture-cmd` | `""` | full command line, overrides the two above (`capture_kind="custom"`, `:672`) |
| `--feed` / `--cut-size` | `""` | h264 source and WxH forwarded to the real child (`:680-684`) |
| `--out` | `clips` | clip directory, relative to `--workdir` |
| `--fps` | `30` | the child's frame rate; durations are DERIVED from it (§2.5) |
| `--seconds` | `0` | self-close after N seconds (0 = forever) |
| `--cut-every` | `0` | one cut every N seconds, the gate's stand-in for the hotkey |
| `--cut-count` | `0` | stop after N cuts (0 = unlimited) |
| `--asr on|off` | `off` | run the ASR side as a supervised child |
| `--asr-cmd` / `--asr-timeout` / `--asr-queue` | `""` / `900.0` / `8` | ASR overrides |
| `--ui on|off` | `on` | the UI door |
| `--port` | `0` | 0 = ephemeral, recorded in the portfile |
| `--workdir` / `--spine` / `--lock-name` / `--port-name` / `--status-name` | `.` / `engine-spine.db` / `engine-ring.lock` / `engine-port.json` / `engine-status.json` | the four outside-visible files and where they live |
| `--selftest` | off | run ONLY the LAW 6 pre-flight and exit (`:526-527`) |
| `--inject-fault` | `none` | `none|no-nvenc|tuning-undefined|skip-map`, forwarded to the child's `--selftest` |
| `--quiet` | off | suppress periodic health events |

### 2.2 The five exits

READ `engine.py:22-28` and the constants at `:56-60` (`EXIT_OK`, `EXIT_USAGE`, `EXIT_NVENC`, `EXIT_SECOND`, `EXIT_FATAL` = 0, 2, 3, 4, 5):

| code | when | words on stderr |
|---|---|---|
| `0` | clean shutdown | `shutdown: SIGINT`, or the stop reason |
| `2` | usage or config refused, including a pre-flight refused for a non-encoder reason (`:745-746`) | `CAPTURE-PREFLIGHT-REFUSED rc=2` plus the child's own words |
| `3` | "the capture side refused to arm: NO encoder (LAW 6)" (`:25`) | `CAPTURE-PREFLIGHT-REFUSED rc=3` plus the child's DECISION line verbatim (`:743-744`) |
| `4` | a second Engine instance, ring lock already held (`:546-551`) | `ENGINE-SECOND-INSTANCE path=%s` and the diag "another Engine owns the ring lock" |
| `5` | fatal internal (`:511-520`) | `FATAL(5): unhandled internal error` plus a traceback |

The gloss the docstring puts on exit 3 is the load-bearing sentence (`:25-26`): "A dead hotkey that says why beats a live hotkey that does nothing."

### 2.3 The boot order, and why it is that order

READ `engine.py:507-608`. `run()` installs the stdout guard and then `_run()` executes a strict sequence:

1. `:526-527` — `--selftest` short-circuits to the pre-flight only.
2. `:536-542` — **LAW 6 pre-flight**, before the Engine owns a ring, opens a spine or spawns anything. A refusal writes the status file for the operator and returns with "the Engine never owned a ring".
3. `:546-552` — the **ring lock**. One Engine, one owner; a second instance exits 4.
4. `:555-556` — the **spine**.
5. `:559-567` — the **capture child**, then a bounded `ping` handshake (20 s); a failed handshake is fatal 5.
6. `:570-577` — the **ASR side**, behind a bounded queue, if asked for.
7. `:580-597` — the **UI door**; the portfile is written only after the bind is observed (§5.4).

The consequence for failure accounting is exact: a pre-flight refusal leaves NO spine, NO lock and NO clips directory behind. That is not a comment, it is a checked property of the gate (`test_engine.py:597-600`).

### 2.4 stdout is empty, and that is enforced

READ `engine.py:491-504`: `_silence_stdout()` replaces `sys.stdout` with a guard whose `write` raises `AssertionError("engine stdout is EMPTY by contract; refused %r")`. The argparse description says the same (`:446`). This is the Python mirror of the C++ rule: diagnostics on stderr only, the bus is the socket.

### 2.5 The four files the outside world reads

READ `engine.py:975-1013`. `_atomic_write_json` writes `<path>.tmp`, fsyncs, and `os.replace` (`:981`) — a reader never sees a half-written JSON.

* **portfile** (`--port-name`, `:983-993`): protocol version, host `127.0.0.1`, the LISTENING port, pid, boot_ts, capture kind, workdir, clip dir, spine path, and a `transport` field that names its own divergence — "localhost TCP JSONL (production target: a named pipe; accepted divergence, see receipt)".
* **status file** (`--status-name`, `:995-1013`): rewritten every 0.5 s from the main loop (`:634-636`) and once more with `final=True` at exit (`:523`). It carries health, the ring snapshot, the spine path and `"stdout_bytes": 0` (`:1007`) — the empty-stdout contract made observable.
* **spine**: §4. **ring lock**: §2.3 step 3 and §5.5.

READ `:612-638` for the loop that keeps them current: a 0.02 s sleep, `--seconds` deadline, a dead capture child as its own stop reason (`:619-626`, `capture-child-died` — the Engine cannot own a ring without a capture side, and it explicitly does NOT wait for the ASR side), the timer cut (`:627-629`), a health event every 1 s (`:630-633`), the status file every 0.5 s, and `_drain_asr()` on every pass.
READ `:640-651` for shutdown: results already in flight are applied before the exit, bounded by `ASR_EXIT_GRACE_S` = 12.0 (`:70`) — "a stalled ASR child cannot hold the Engine hostage", and the comment adds that capture is already closed by then.


---

## 3 · THE PROTOCOL

READ `protocol.py`, 139 lines. The docstring names the law in two sentences that govern the whole file (`:17-20`): "The rules mirror the C++ Msg::parse in src/engine/json.{h,cpp}" and "STDIO IS NOT THE PROTOCOL … the Engine's own stdout is EMPTY by contract".

### 3.1 The envelope

READ `:5-15`. Every frame in either direction is exactly `{"v":1,"type":<str>,"id":<int>,"ts":<num>,"payload":<obj>}`. `V = 1` (`:33`). `id` "IS the replay cursor" (`:13`) — the monotonic event number the ring mints (`engine.py:106-107`). Machine payloads only: no floats, no `XU`, and any byte below 0x20 anywhere is refused and counted.

### 3.2 The rules, and what each one refuses

READ `:34-99`, enforced by `parse_line` (`:108-131`) and `_check_envelope`:

| rule | source | refusal |
|---|---|---|
| `v` must be the integer 1 | `:69-72` | not a version negotiation; anything else is rejected |
| `type` matches `^[a-z][a-z0-9_]*$` | `:34`, `:75` | no camelCase, no capitals, no spaces |
| `id` an integer >= 0 | `:77` | the cursor cannot be negative or fractional |
| `ts` a number >= 0 | `:78` | wall time, never a device clock |
| `payload` a dict, its keys free of control characters | `:79-86` | no control byte may ride in a key |
| no duplicate keys in the JSON object | `:52-58` (`_pairs_hook`) | a repeated key is a parse refusal, not a last-wins merge |
| line at most 64 KiB | `MAX_LINE = 64 * 1024`, `:35`, `:108-112` | a huge frame is cut, not buffered |
| a line that is empty or only whitespace | `:108-109`, `:115` | silent, refused |
| control character anywhere in the line | `:61-62` (`has_control_chars`), `:113` | refused |
| leading or trailing whitespace | `:116` | trimmed is not the protocol |
| anything that is not JSON | `:117-118` | `ProtocolError`, which is "Never re-emitted, never applied" (`:48-49`) |

READ `:38-45`. The vocabularies are closed and small — EVENTS: `hello, replay, capture_started, clip_written, asr_partial, asr_final, index_updated, health, error, cut_ack, status, search, detach, bye`; COMMANDS: `attach, detach, cut, status, search, bye`. A command outside the set answers `make("error", {"error": "unknown command %r"})` (`engine.py:953`) and the connection stays open. `encode` "Validates first, always" (`:102-105`): a payload the rules reject cannot leave this process.

### 3.3 What travels, and what does not

READ `capture_child.py:1-22`. The classify rule is the load-bearing one: a line that parses as a JSON **object** is a PROTOCOL reply; everything else — a JSON array, a bare scalar, stray ASCII — is a DIAGNOSTIC and is written to the Engine's stderr behind a `[capture]` tag (`classify`, `:40-56`). The file records why in its own words (`:14-18`): the real child (the C++ `main.cpp`'s `log_line`) writes its `=== CUT SESSION ===` headers to **stdout**, not stderr, "measured while gating LAW 6" — so a stdout-based reply channel needed a rule that survives a chatty child.

READ `:88`: the child is spawned with `stderr=None`, i.e. **inherit — the child's stderr IS the engine's stderr**, and always with `CREATE_NO_WINDOW = 0x08000000` (`:33`, `:20-21`: "the owner's screen must never gain a console window"). `request` (`:152-172`) raises on `ok:false` with the child's own words; `close` (`:212-223`) is "Graceful shutdown: stdin EOF, wait, then kill. Never leave a child", with the measured fallback "child ignored stdin EOF after %.1fs -- TerminateProcess" (`:217`).

READ `protocol.py:102-105` and `engine.py:812-813` — every `emit` goes through `Ring.append`, so a wire frame is also a retained record, and the two are the same object.

---

## 4 · THE SPINE (WHAT SURVIVES A KILL)

READ `store.py`, 160 lines. The docstring (`:1-11`) states three claims that the rest of the file is built to keep:

* `:1-2` "the Engine's durable spine (SQLite, committed-before-ack)".
* `:5` `synchronous=FULL + WAL` is what buys that — "NORMAL (the index's choice) does not". A durability choice, made explicitly and described as one.
* `:8-10` `content_key` "is the whole-file SHA-256 computed at commit time FROM THE FILE … the anchor the Engine shares with lane B's index (src/index/schema.sql, video.content_key)".

### 4.1 The measurement of a key

READ `:23-35`: `CHUNK = 1 << 20` and `content_key_of(path)` streams the file in 1 MiB chunks. A `content_key` is never a guess, never a path, and never a timestamp: it is a hash of bytes that are on disk at the moment of the commit.

### 4.2 The two commits, and their order

READ `:50-59` (`anchor`) and `:61-84` (`commit_clip`):

* `anchor` writes the ROW BEFORE THE BYTES, with the docstring's own reasoning: it "Mirrors the capture child's 'cutting' anchor … a crash can orphan a ROW (findable, repairable) and never a FILE" (`:52-56`). `content_key` is `NULL` while `state='cutting'` (`schema.sql:21`).
* `commit_clip` hashes the file and fills the key. It raises `FileNotFoundError` if the file is missing, and the comment is a refusal in prose (`:73-75`): "an engine that acked a clip whose bytes are not on disk would be lying".
* `mark_failed` (`:86-88`) and `set_asr_state` (`:90-91`) give a clip a stated failure and a stated ASR state instead of an unanswered question.

READ `engine.py:755-800` for the order in the live cut: `spine.anchor()` → `child.cut(timeout=120.0)` → `spine.commit_clip(...)`, each with its own `except` that marks the row `refused` or `commit-failed`, increments `cuts_refused`, and emits `error where=…`. A cut that fails leaves a `cutting` row — never a silent success.

### 4.3 The schema, and the divergences it records against the index

READ `schema.sql`, 80 lines. Pragmas (`:3-6`): `journal_mode=WAL; synchronous=FULL; foreign_keys=ON; busy_timeout=5000`.

| table | key | note |
|---|---|---|
| `clip` | `clip_id`, `content_key UNIQUE` | `state` `cutting|done|failed` (`:27`), `asr_state` `pending|ok|dropped|dead` (`:28`), `committed_at` (`:30`) |
| `speech_segment` | PK `(clip_id, seg_index)`, ON DELETE CASCADE | `:36-46` |
| `ocr` | — | `:49-55` |
| `visual` | — | carries `score REAL` (`:57-64`) — REAL here, on disk, unlike the bus |
| `clip_text` | — | `:69-73` "This is NOT lane B's text_fts … search is a LIKE over it" |
| `engine_meta` | `k` PK | `opened_at` and friends (`:76-79`), written at open (`store.py:46-47`) |

The file states the reason SQLite is the spine and not the bus itself (`:8-12`): "the bus (JSONL over the pipe/socket) is allowed to DROP … TerminateProcess is the test (ARM-F)". And it records its own divergence in a comment (`:14-17`): "this table is engine/in/clip_named, the index's is video" — a difference the comment says is "recorded in the receipt", i.e. known and accepted.

### 4.4 Search: provenance-carrying, and deliberately not FTS

READ `store.py:144-152`. `search` is a `LIKE` over `clip_text` with the `%` and `_` wildcards stripped from the query (`:146`) — a deliberate choice, and its docstring requires the property that matters: "Provenance-carrying search: every hit names its clip and content_key". There is no FTS table and no trigger here; the index's `text_fts` is the other file's problem (see spec 05 §4 for its FTS5 hazards).

READ `store.py:134-142` (`counts`) — the per-table census the health payload and the gate both read: `clip, speech_segment, ocr, visual, clip_text, clip_done, clip_cutting`. `close` (`:154-159`) runs `PRAGMA optimize` before closing — the comment there is "a closed spine answers no question".
---

## 5 · THE RING, THE DOOR, AND THE LOCK

### 5.1 The ring is the only lossy component

READ `engine.py:94-128` (cited in full at §1.2). Two properties decide everything the UI can promise. The ring is bounded — `deque(maxlen=RING_CAPACITY)` with `RING_CAPACITY = 100` (`:62`, `:97`) — and the identifiers never rewind, because `next_id` is a plain monotone counter (`:99`, `:106`). So "what you missed" is always expressible as a count and a number: `since(since_id)` returns `(events, oldest_id_retained, newest_id)` (`:111-117`), and `snapshot()` (`:119-128`) exposes `dropped` — the number of events the bound threw away. Overflow is a fact in the health payload, not a failure state.

### 5.2 The connection is bounded, and the Engine never waits for it

READ `UiConnection` `:134-149`: the outbound queue is `deque(maxlen=256)` (`:149`). `UiHub.publish_now` (`:177-189`) carries the exchangeable-status objects — health, status — and the comment states the reason: "health is a pollable state … retaining it in the ring would EVICT clip_written events". `offer` (`:191-200`) pushes into a bounded queue, counts the drops, and never backpressures its producer. A UI that reads slowly therefore loses its own recent frames and none of the Engine's.

### 5.3 The door: bind, accept, survive a bad line

READ `UiServer` `:213-259`: the bind/accept loop runs on its own thread, and a malformed line is answered with an `error` event while the connection stays alive (`:278-282`). A client cannot kill the door by sending junk, and cannot be killed by the door either: `_cleanup` shuts the hub and the server before it closes the spine (`:1030-1031`).

**Port-file race, and why it is a hazard worth naming.** READ `:584-589`: "Writing the portfile before the bind was measured twice: it carried "port": 0, the UI child dialled 127.0.0.1:0 and died with WinError 10049 …". The shipped code therefore waits for the socket with `UI_BIND_WAIT_S = 5.0` (`:76`, loop `:590-596`) and only then calls `_write_portfile()` (`:597`). The portfile is the address; an address file written before the address exists is a lie with a JSON extension.

### 5.4 Attach, detach, replay: the reconnect contract

READ `ui_command` `:915-953`. A UI that attaches with `{"v":1,"type":"attach","id":…#,"ts":…,"payload":{"since":<id>}}` receives, in one frame, `{"events":[…], "from":<id>, "to":<id>, "oldest_retained":<id>, "replayed":<n>}`, where `replayed` is the count and `truncated` is the honest flag — true exactly when `since > 0 and since < oldest_id_retained`, i.e. when the client asked for something the bound already threw away (`:918-925`). The hub then offers the `env` health frame `{"ui_ready":…,"since":…,"replayed":…,"truncated":…,"oldest_retained":…,"to":…}` (`:927`), the connection is marked attached (`:928`), and the Engine's stderr says `ui %s ATTACH since=%d replay=%d truncated=%s` (`:929`).

Detach is the mirror image and it is deliberate that it is cheap (`:932-937`): `make("detach", {"reply_to": <mid>})`, then the diag line `ui %s DETACH -- recording continues`. **A UI that goes away does not take the recording with it.** That single line is the whole answer to "what happens when the owner closes the panel mid-session".

The other commands (`:939-953`): `cut` calls `self.cut("ui")` — the same path the timer takes, with a different reason label — and answers `cut_ack`; `status` answers a `status` event carrying `health_payload()`; `search` runs `self.spine.search(q, limit=50)` when a spine exists, answers `[]` on any exception rather than raising, and logs `search failed: %r` (`:947-950`); `bye` closes politely; anything else answers `error` with `unknown command %r` (`:953`).

### 5.5 Health is a state, not a log line

READ `health_payload()` `:955-972`. The published state is `{pid, uptime_s, capture, ring, cuts, clips, asr, child, ui, stop_reason}`, with `ring` the `snapshot()` of §5.1, `cuts` the five-element `stats` dict `{cuts_requested, cuts_ok, cuts_refused, asr_dead, asr_failed}` (`:436-439`), `clips` the spine's `counts()`, `asr` the worker's `snapshot()`, `child` `{alive, pid, diag_lines, exit_code}`, and `ui` `{connected, attached}`. It is written to the status file every 0.5 s and offered to any attached UI as an `env` frame on attach — the ring does not have to remember it (the `:177-189` comment).

### 5.6 One owner, and the lock proves it

READ `RingLock` `:297-374`. The docstring calls it an "Exclusive, self-cleaning lock file holding pid + boot time". The lock is taken at `:546-552`, before the spine or any child exists, and a refusal prints `ENGINE-SECOND-INSTANCE path=%s` to stderr, the diag "another Engine owns the ring lock", and exits `EXIT_SECOND` (4). `_cleanup` releases it (`:1052`). The boot-time value in the file is what makes the lock robust against a pid reuse; a failure to acquire prints `ENGINE-RINGLOCK-ERROR path=%s err=%s` (`:372`) rather than falling through to a shared ring.

### 5.7 The main loop, and what "stop" means

READ `:612-651`. One pass is: the `--seconds` deadline (`stop_reason="seconds-elapsed"`, `:613-618`), a dead capture child (`capture-child-died`, `:619-626`), the timer cut (`:627-629`), a health event each 1.0 s (`:630-633`), the status file each 0.5 s (`:634-636`), `_drain_asr()` (`:637`, results already in flight are applied here), and 0.02 s of sleep (`:638`). Signals (`SIGINT`, `SIGTERM`, `SIGBREAK`, `:653-666`) set the stop flag with `stop_reason="signal-%d"` (`:661-663`).

Shutdown is ordered, not best-effort (`:640-651`, `:1015-1053`): stop the main loop, drain `_drain_asr()`, then a bounded grace loop of `ASR_EXIT_GRACE_S = 12.0` (`:70`) for results already in flight — the comment names the property it protects: "a stalled ASR child cannot hold the Engine hostage". `close(grace=8.0)` on the capture child (`:1015-1021`) is described as "Graceful shutdown: stdin EOF -> finalise -> wait", with `asr.stop(join_timeout=2.0)` (`:1034`), `spine.close()` (`:1035`, whose trailing comment is "a closed spine answers no question"), the portfile unlinked (`:1044-1046`), the lock released (`:1052`), and the final status written (`:523`). A failure inside any of this logs `ENGINE-CLEANUP-ERROR capture: %r` (`:1040`) instead of being swallowed.
---

## 6 · THE CAPTURE SIDE

### 6.1 How the child is chosen and spawned

READ `engine.py:670-696`. `_capture_argv` builds the command for three shapes: `custom` (the `--capture-cmd` string split by `shlex`, `:673-676`), `stub`, and `exe` — `[capture_exe, "--cut-session"]` plus `--cut-from-h264`, `--cut-dir`, `--cut-fps` and, when a size is given, `--cut-size WxH` (`:679-684`). `_spawn_capture` (`:687-690`) tags the child `capture` or `capture-STUB` so the Engine's own stderr says which of the two arms is running, `_clip_ext` (`:692-693`) returns `.wav` for the stub and `.mp4` for the real child, and `_predicted_clip_path` (`:695-696`) is the name a cut is expected to produce.

The default `--capture-exe` is `_main/build/aireplay-capture.exe` resolved under the repo root, not under the worktree I can read from this lane's position. The binary does exist in the product root: MEASURED 2026-10-10, `stat` on `H:/sotto/_moved/aireplay/_main/build/aireplay-capture.exe` = 783865 bytes, mtime 2026-10-09T20:51:21Z — the same size the gate's docstring quotes. It is **not tracked** (`git ls-files _moved/aireplay/_main/build` returns no tracked files) and the `_main/build` directory is absent from the worktree I am allowed to look at, so this spec's arm D citation is a READ of the DEFAULT path resolution in the source above plus the root census above — never a run of the binary from my worktree.

### 6.2 LAW 6, and the exit codes it can produce

READ `_preflight(self, exit_on_refusal=True)` `:699-749`. The sequence is: argv = the child's `--selftest` (plus `--inject-fault` if any), a stub or exe variant accordingly (`:704-711`); the diag line `"pre-flight (LAW 6): %s"` (`:713`); `subprocess.run(..., input="", stdout=PIPE, stderr=PIPE, text=True, encoding="utf-8", errors="replace", timeout=300, cwd=REPO_ROOT, CREATE_NO_WINDOW on nt)` (`:715-720`); `TimeoutExpired` → `EngineFatal(EXIT_FATAL, "pre-flight timed out after 300s: ...")` (`:722-723`) and `OSError` → `EngineFatal(EXIT_USAGE, "pre-flight cannot run %s: %s")` (`:724-725`); the `decision` is the first stdout line containing `DECISION` (`:727-728`); the diag `"pre-flight rc=%d decision=%r wall=%.1fs"` (`:730`); rc 0 returns EXIT_OK; a refusal prints `CAPTURE-PREFLIGHT-REFUSED rc=%d argv=%s` and then the child's stdout and stderr verbatim (`:732-738`) before mapping rc 3 → `EXIT_NVENC`, rc 2 → `EXIT_USAGE`, anything else → `ENGINE-PREFLIGHT-UNEXPECTED rc=%d -> treated as fatal internal` and `EXIT_FATAL` (`:740-748`).

Three properties of that are the LAW 6 contract and not implementation detail: (a) the pre-flight runs **before** the Engine owns a ring (`:536-542`), so a refusal leaves no artifacts at all; (b) the child's own words are reprinted unedited, so the operator sees the encoder status the way the child wrote it; (c) an unexpected rc is fatal rather than silently armed.

### 6.3 Why every session arm in the gate is a STUB, in one sentence each

READ `stub_capture.py:11-13` (measured in the gate's docstring against revision `399bc851`, 2026-10-09): the real child refuses an offline feed with `=== CUT SESSION REFUSED: no SPS/PPS: avcC cannot be built ===`. READ `main.cpp:1008` on branch `feat/engine-process`: the check is literally `if (sps.empty() || pps.empty()) { *err = "no SPS/PPS: avcC cannot be built"; return false; }`.

The cause is inside `SourceStream::load` (`src/capture/main.cpp`, read-only to the engine lane), where SPS/PPS are captured only inside `if (vcl)` and NAL types 7/8 are never VCL (`test_engine.py:32-36`). The stub therefore exists (`stub_capture.py:1`: "A STUB capture child. A STUB, NOT THE REAL THING.") with an explicit statement of what it cannot claim (`:22`: that the C++ capture device works, that WGC works). **A stub arm is never reported as a PASS of the real capture path** (`test_engine.py:36`).

---

## 7 · THE ASR SIDE

### 7.1 A bounded worker that never applies backpressure

READ `asr_worker.py:1-16`. The docstring states the design in four lines: it is "a BOUNDED worker that never applies backpressure … when it is full the job is DROPPED -- counted, and reported in every health event"; "The Engine's ring keeps writing while the ASR side stalls or dies; the proof is one of the gate's arms (ARM-C: a stalled child must not stop a single frame)"; and each job is "a FRESH subprocess of the ASR side's own CLI (`python -m asr.transcribe`) in EVENT mode (no `--json`)". The queue is `queue_size=32, timeout=900.0` (`:105` — the gate passes `--asr-queue 8` as its own bound).

The drop is visible in the live path, not only in the counter. READ `engine.py:803-807`: after a cut, when `self.asr.submit(cid, path)` returns a false value the Engine marks the spine row `set_asr_state(cid, "dropped")` and logs `clip %s: ASR queue FULL -- job dropped (capture never waited)`. The parenthetical is the law being asserted at the moment it is applied. The worker's own tail (`:229-246`) reports state `ok|failed|dead` plus metrics `n_segments, audio_s, rtfx_infer, model_load_s, rss_after_load_mb`.

### 7.2 The stub ASR child, and what it proves

READ `stub_asr.py` (2736 B): it exists to be wrong in two specific ways — `--stall 25` (a child that accepts a job and stops) and `--rc 2` (a child that fails immediately). Those are the two halves of ARM-C, registered as separate arms at `test_engine.py:761-762` (`arm("C1", … "stall")`, `arm("C2", … "dead")`). A STUB ASR is never a PASS of the real ASR path.

### 7.3 Where the audio is supposed to go (design, not shipped)

READ `docs/integration-sotto-app.md` §1.4 and §5.1 (2026-10-08, 413 lines, 32542 B). The document's answer to "who opens the WASAPI endpoint" is unambiguous: "exactly ONE owner of a WASAPI loopback endpoint — The CAPTURE CORE owns the endpoint. The ASR never opens it", and the Engine→ASR audio is a **PCM tee**, 16 kHz mono s16le, length-prefixed, over the child's stdin — explicitly NOT JSON (§1.4), with §5.1 adding that "STEP 3 IS AN ATOMIC CUTOVER".

**The shipped Python Engine does not implement that tee.** Its ASR side is a separate supervised process invoked on the finished clip file (`asr_worker.py:9-15`), not a live PCM stream through a pipe. The tee, the one-owner constraint at the endpoint level, and the atomic cutover are therefore **DESIGNED, not shipped** in this subject: a future state where the Engine supplies the tap itself is UNKNOWN (§13), and no arm in `test_engine.py` measures audio delivery at all.

---

## 8 · THE GATE: SIX ARMS, EACH WITH ITS OWN RED CONTROL

READ `test_engine.py`, 854 lines. The docstring (`:1-36`) states the rules that make the gate more than a list of checks: GREEN is the real subject (and the REAL capture binary where it can be used), RED is the same subject with ONE property removed, and "a red control that does NOT go red is a FAILURE" — its own name for that is `RED-CONTROL-SILENT`, described as "the arm was measuring nothing". Also `:13-14`: "A SKIPPED arm is a FAILURE. Nothing is printed as PASS unless it ran and met its threshold."

| arm | claim | where |
|---|---|---|
| `A` | the engine starts, arms the hotkey path, holds the ring with the ui absent | `:17` |
| `B` | UI attach/detach mid-run, last-100-event replay by `since_id` | `:18-19` |
| `C1` / `C2` | ASR child stalls, then dies; capture continues unbroken — "no dropped ring, no lost clip, no cut ever waited for the AI side" | `:20-21` |
| `D` | NVENC failure exits 3 and the message names the encoder status | `:22` |
| `E` | a second Engine instance is refused loudly (no double ownership) | `:23` |
| `F` | TerminateProcess mid-session, every clip row committed before the kill and content_key survives | `:24-25` |

The docstring's own honesty about the capture binary (`:27-36`) is part of the spec, not a caveat: ARM-D's pre-flight DOES run the real binary (`_main/build/aireplay-capture.exe`, 783,865 B), while every arm that needs a capture SESSION runs against `stub_capture.py` and says so, "because this checkout's C++ child refuses every offline h264 feed".

### 8.1 The five red controls, and the single property each one removes

READ `test_engine.py:738-747`. A red control is the green subject with ONE property deleted, and each entry names the failure it is supposed to expose:

| control | against arm | the property removed | the failure it exposes |
|---|---|---|---|
| `replay-empty` | B | the ring retains events but a reconnecting UI gets an empty replay | a reconnect that silently forgets |
| `capture-waits` | C1 | the cut path waits for the AI side, so capture stalls behind ASR | the ring stops being the owner of the deadline |
| `preflight-ok` | D | a dead encoder is treated as ARMED instead of exit 3 | law 6 inverted: a dead hotkey that works |
| `no-lock` | E | a second Engine is never refused, so two owners share the ring | double ownership |
| `commit-nokey` | F | `content_key` is claimed, never measured from the file | a key that is a guess |

Each is an `engine.py` or `store.py` text substitution applied to a COPY (the MUTANTS tuple's dict maps a file to `[(old, new)]` pairs), so the red run is the same program minus one sentence. The default invocation runs green and red in ONE command (`:778-782`) and prints the censuses under "CENSUS (own cadence, full artifact path):" (`:830`), removes `GATE_ROOT = I:\cc-tmp\engine-gate-<pid>` unless `--keep` (`:833`), and answers `GATE-VERDICT: GREEN|RED total Ns` with exit 0 or 1 (`:839-840`).

One instrument property is worth stating because it is the one most easily lost: a control that does NOT go red is itself a gate failure — `"   <<< CONTROL DID NOT GO RED (%s)"` (`:819`) — because an arm whose mutant still passes was never measuring the property it claims to. That is the difference between a gate and a checklist.

### 8.2 Arm D in detail: the real binary, and the artifacts it must NOT leave

READ `arm_d` `:581-608`. `wd = fresh("d-%s" % colour)`, the subject is the repo's own `_main/build/aireplay-capture.exe`, and the run is `run_engine(subject, wd, ["--capture","exe","--capture-exe",exe,"--selftest","--inject-fault","no-nvenc","--seconds","1"], 180)` (`:586-588`). The checks (`:590-601`) are: `rc == 3`; stdout is empty; `"CAPTURE-PREFLIGHT-REFUSED rc=3" in err`; a decision line containing `"NO ENCODER INITIALISED"`; a line naming either `"nvEncode"` or `"H.264"`; the status file's `exit_code == 3`; the spine does NOT exist; the ring lock does NOT exist; the clips directory does NOT exist; no capture-child file exists.

That set is the LAW 6 claim in the strongest form the gate can make: an Engine that cannot initialise the encoder refuses to be one, and refuses **before** it owns anything — no ring, no spine, no directory. `--inject-fault no-nvenc` is how the arm gets a deterministic refusal without depending on the host's encoder.

### 8.3 Arm E in detail: the second instance is refused by a FILE

READ `arm_e` `:614-641`. Two Engines on the SAME working directory: the first `--capture stub --ui off --asr off --cut-every 0 --seconds 14`, then — after waiting for the lock file and a 1.0 s settle — the second with `--seconds 4` (`:619-627`). The checks (`:629-639`): first rc 0 and empty stdout; second rc `4`, empty stdout, `"ENGINE-SECOND-INSTANCE" in err2`, and the explanatory line `"another Engine owns the ring lock" in err2`; after both exits the lock file is gone (`lock_after is False`) and the clips directory exists (`:638-639`). The arm proves both halves: the refusal, and the self-cleaning.

### 8.4 Arm F in detail: the kill is the durability test

READ `arm_f` `:647-737`. The Runner starts the Engine as `--capture stub --ui off --asr off --cut-every 1 --seconds 0`, `poll_committed(wd, 3, 60)` waits for three committed clips, `child_pid` is read from the health payload, `t_kill = time.time()` is stamped, then `eng.terminate()` + `p.wait(15)` and `spine_audit(wd)` (`:654-668`), and the capture child is force-killed afterwards with `taskkill /F /PID <child_pid>` (`:735`).

The checks (`:676-688`) are the durability contract in seven propositions: the Engine published at least three clips before the kill; the spine still holds them all after it; at least three rows are committed; `integrity_check` is ok; at most one row is `cutting`; no `cutting` row carries a `content_key`; no row has an unknown state; every key is 64 hex characters; every key equals the file's sha256; every committed clip is still on disk; and every `committed_at` is `<= t_kill` (`committed_before`). The comment above them (`:670-675`) states why "at most one cutting row, with no key" is the best possible answer rather than a weak one: the row-before-bytes order (`store.py:50-59`, `:61-84`) means a kill can orphan a ROW or lose a FILE, never both — and an orphaned row is findable and repairable.

---

## 9 · FAILURE MODES OF THE ENGINE ITSELF

| what can fail | what the Engine does | tagged |
|---|---|---|
| a second instance | `ENGINE-SECOND-INSTANCE path=%s` + "another Engine owns the ring lock" → exit 4, self-cleaning | READ `:546-552`, `:297-374` |
| the ring lock cannot be taken | `ENGINE-RINGLOCK-ERROR path=%s err=%s` → `EXIT_FATAL`, never a shared ring | READ `:372` |
| the capture child fails pre-flight | `CAPTURE-PREFLIGHT-REFUSED rc=%d argv=%s` + the child's own stdout and stderr → exit 3 (or 2) | READ `:732-748` |
| pre-flight times out (300 s) or cannot be spawned | `"pre-flight timed out after 300s: ..."` → 5; `"pre-flight cannot run %s: %s"` → 2 | READ `:722-725` |
| an unexpected pre-flight rc | `ENGINE-PREFLIGHT-UNEXPECTED rc=%d -> treated as fatal internal` → 5 | READ `:744-748` |
| the capture child dies mid-session | `emit("error", {"where": "capture_child", …})`, `stop_reason="capture-child-died"` | READ `:619-626` |
| the spine anchor or commit raises | `cuts_refused++`, `spine.mark_failed(cid, …)`, `error where=spine_anchor` / `spine_commit` | READ `:757-762`, `:786-795` |
| a cut is refused by the child | `mark_failed(clip_id, "refused")`, `error where=cut` | READ `:769-773` |
| the ASR queue is full | spine row `set_asr_state(cid, "dropped")`, diag "job dropped (capture never waited)", `stats` keeps the count | READ `:803-807` |
| the ASR child dies | `stats["asr_dead"]`/`asr_failed`, the worker state `dead` in every health frame | READ `:436-439`, `:229-246` |
| SIGINT / SIGTERM / SIGBREAK | `stop_reason="signal-%d"`, then the ordered cleanup, then a final status file | READ `:653-666`, `:640-651` |
| anything not caught | `FATAL(5)` + traceback on stderr, final status still written | READ `:507-523` |

Two of these are the laws wearing clothes. The `asr` ones are law 1 ("capture never waits for AI" — `src/engine/queue.h:1-5` carries the same sentence in the C++ revision). The ring-lock one is law 6's other half: a duplicate owner is a hotkey that lies.
---

## 10 · THE PLAN OF RECORD, AND WHAT HAPPENED TO IT

READ the plan of record at `H:/sotto/_moved/aireplay/runs/P4-aireplay-engine-process.md` (5908 B, sha256 `511651EC…`, untracked, dated before this spec). It is READ here, never re-measured: every number in this section is the plan's, and the shipped column is a READ of the source at `0e1b7f5`.

| the plan said | what the shipped Engine does |
|---|---|
| a single supervisor owning the ring, parent of the capture process | exactly that, and the docstring says so in one line (`engine.py:2`) |
| health `{ring_fill_pct, dropped, asr_rss_mb}` (§3.2) | `health_payload()` (`:955-972`) publishes `ring.snapshot()` with `size/capacity/dropped/oldest_id/newest_id/next_id` and `asr` with the worker's own metrics — `ring_fill_pct` appears as `size/capacity`, and `asr_rss_mb` appears as `rss_after_load_mb` (`asr_worker.py:229-246`). Same information, different names. |
| NVENC fails → exit 3 (§4.1) | shipped, exactly, via the pre-flight rc mapping (`:740-743`) and gated by arm D |
| ARM-A..E (§6) | all five shipped, plus ARM-F (the kill test) and the C1/C2 split of C |
| §7 FILES TO CREATE: `engine.py`, `protocol.py`, `test_engine.py` | shipped, plus seven more: `store.py`, `schema.sql`, `capture_child.py`, `asr_worker.py`, `ui_child.py`, `stub_capture.py`, `stub_asr.py` |

Two honest notes. (1) The over-delivery above is recorded as such in §14, not written off as "the plan's table was incomplete". (2) The plan's framing of health as `{ring_fill_pct, dropped, asr_rss_mb}` describes a three-number payload; the shipped payload carries eleven keys and a nested ring snapshot. A spec that only said "matches the plan" would lose that.

**The plan's ARM-B and ARM-E are NOT this spec's arms.** The plan's ARM-B (cut → clip → ffprobe h264) belongs to the capture/index specs, and its ARM-E (search provenance chips) belongs to the index/search specs — the shipped Engine's `search` is a LIKE over `clip_text` (`store.py:144-152`) with the channel `WEIGHTS` living in the index's own `src/index/search.py:32`. Writing those two rows here would be an over-statement the source does not support.

---

## 11 · WHAT THE EVIDENCE FILE COVERS, AND WHAT IT DOES NOT

READ `runs/P4-specs-evidence-20261009.md` (this branch, commit `f8cdb01d`). It records the clip-to-ASR arms that were actually RUN on 2026-10-09: real ASR, video-only, the two-track arm run with `--expect no-audio-stream`, and the no-ASR arm, with their population counts, ISO timestamps, exit codes and exact commands.

**It is not an engine-lane receipt, and this spec must not pretend otherwise.** Consequences, stated plainly:

* every engine number in this document is a **READ of the source at `0e1b7f5`** or a READ of the plan of record from an older tree — never a MEASUREMENT taken on this machine by this lane;
* `test_engine.py`'s gate output (its `GATE-VERDICT`, its per-arm counts, its census sizes) is cited as what the program prints, from the source, and is tagged **NOT RUN HERE**;
* the one census this lane DID measure is the real binary's presence in the product root — 783865 B, mtime 2026-10-09T20:51:21Z, untracked, absent from this worktree (§6.1) — and that is a statement about a FILE, not about the Engine running.

The reason is structural, not cautious: `src/engine/*` sits on branch `feat/engine-process`, there is no committed engine-lane receipt in this repository, and a run of `test_engine.py` would need `I:/cc-tmp` scratch space, a working capture child and a 180 s budget per arm. Recording green words for a run that did not happen is exactly the failure this spec exists to avoid.
---

## 12 · THE CONSTANTS, AS THE SHIPMENT DEFINES THEM

Every value below is a READ from the named file at `0e1b7f5`. None of them is a tuning recommendation; each is what the code says today.

| constant | value | where |
|---|---|---|
| `ENGINE_VERSION` | 1 | `engine.py:63` |
| `RING_CAPACITY` | 100 | `:62` |
| `EXIT_OK` / `EXIT_USAGE` / `EXIT_NVENC` / `EXIT_SECOND` / `EXIT_FATAL` | 0 / 2 / 3 / 4 / 5 | `:56-60` |
| `ASR_EXIT_GRACE_S` | 12.0 s | `:70` |
| `UI_BIND_WAIT_S` | 5.0 s | `:76` |
| capture child `ping` timeout | 20.0 s | `:560` |
| `cut` → `child.cut(timeout=…)` | 120.0 s | `:766` |
| pre-flight subprocess timeout | 300 s | `:718` |
| health cadence / status-file cadence | 1.0 s / 0.5 s | `:630-634` |
| main-loop sleep | 0.02 s | `:638` |
| `UiConnection` outbound queue bound | 256 | `:149` |
| ASR worker `queue_size` / `timeout` (as shipped; the gate passes 8) | 32 / 900.0 | `asr_worker.py:105` |
| `spine.search` limit | 50 | `store.py:148`, `engine.py:947` |
| `Spine` connect `timeout` | 10.0 s, `isolation_level=None` | `store.py:41` |
| `content_key_of` chunk | 1 MiB | `store.py:23` |
| `protocol.V` / `MAX_LINE` | 1 / 64 KiB | `protocol.py:33`, `:35` |
| spine pragmas | `WAL`, `synchronous=FULL`, `foreign_keys=ON`, `busy_timeout=5000` | `schema.sql:3-6` |

### 12.1 CLI defaults, as `parse_args` declares them

| flag | default | where |
|---|---|---|
| `--capture exe|stub|custom` | `exe` | `:441-447` |
| `--capture-exe` | `_main/build/aireplay-capture.exe` | `:448` |
| `--fps`, `--cut-every`, `--cut-count`, `--seconds` | 30 / 0 / 0 / 0 | `:450-462` |
| `--asr off|on`, `--asr-timeout`, `--asr-queue` | `off` / 900.0 / 8 | `:463-470` |
| `--ui off|on`, `--port`, `--workdir` | `on` / 0 / `.` | `:471-474` |
| `--spine`, `--lock-name`, `--port-name`, `--status-name` | `engine-spine.db` / `engine-ring.lock` / `engine-port.json` / `engine-status.json` | `:475-478` |
| `--inject-fault none|no-nvenc|tuning-undefined|skip-map` | `none` | `:479` |

---

## 13 · UNKNOWN

These are open on purpose, each with the experiment that would settle it. Nothing below is a claim; the list is the honest part of this document.

| # | open question | the settling experiment |
|---|---|---|
| 1 | does the Engine, as shipped, own the global hotkey? A search of `src/engine/*.py` (all 14 files) finds no `RegisterHotKey`, no `VK_*` and no window or hook code at all — the hits for the word "hotkey" are comments and strings (engine.py:25-26, :458, :629, :703, :752; stub_capture.py:172-175; test_engine.py:17), and `cut("hotkey")` (`:629`) is a reason label on a cut, not a registration. | run a session with no UI and `--cut-every 0`, press Alt+Shift+F10 on the owner's machine, and look for a `clip_written` row in the spine plus a stderr line naming it. Absent one, the key belongs to the capture child spawned with `--cut-session` (`:679`). READ today, not measured |
| 2 | which process actually receives that key. The capture child is a separate process, and `src/capture/main.cpp` is read-only to this lane — so "the Engine is the only parent of capture" (`engine.py:2`) and "the Engine owns the key" are two different claims, and only one of them is settled. | repeat the experiment with the capture child's own log open and note which pid registers the hotkey |
| 3 | does `RingLock` survive an abnormal kill? The file holds pid + boot time (`:297-374`), but no code path reads the boot time back to detect a dead owner and refresh it. | `taskkill /F` the Engine without its cleanup, start it again, and see whether `ENGINE-SECOND-INSTANCE` names a dead owner |
| 4 | the real bound of the UI replay at scale. The ring holds 100 events and arm D-style arms prove `truncated` is said true when it should be, but not what 30 minutes does to `UiHub.offer` drop counts. | run `--ui on` with a deliberately slow client for 30 min and census `conn.dropped` and `ring.dropped` |
| 5 | the real capture binary on this box: 783865 B in the product root (MEASURED 2026-10-10, untracked, absent from this worktree), its offline feed refused (`no SPS/PPS: avcC cannot be built`, §6.3), and `--inject-fault no-nvenc` a synthetic refusal. | repair `SourceStream::load` (out of this lane's ownership) and re-run the gate's arm D without an injected fault |
| 6 | the audio tee. `docs/integration-sotto-app.md` §1.4 says the Engine should feed ASR 16 kHz mono s16le PCM over a pipe and §5.1 says the cutover is atomic; the shipped Engine runs a supervised `python -m asr.transcribe` on the clip file instead (`asr_worker.py:9-15`). No arm measures a live audio path. | build the tap, feed both consumers from the one endpoint, and read the `BRIDGE_DEATH` `0x8889000A` counts on each side |
| 7 | two UIs at once: `since(since_id)` is per connection, but is `oldest_retained` the same answer for a second attach that arrives later? | attach two `ui_child.py` instances at different wall times and compare both replay frames |
| 8 | the Engine's own RAS profile: `health_payload` carries pid, uptime and counters, but no RSS. | run a session for 30 min and read `rss` out of the process tree at health cadence |
---

## 14 · OVER-STATEMENTS THIS SPEC REFUSES, AND WHAT IT DID NOT DO

### 14.1 The plan's health table is narrower than the shipped payload
The plan (§3.2) describes health as `{ring_fill_pct, dropped, asr_rss_mb}`. The shipment carries `{pid, uptime_s, capture, ring, cuts, clips, asr, child, ui, stop_reason}` (`:955-972`) with the ring snapshot nested inside. The plan is not "wrong" — it is a smaller contract, delivered under a different name. Recording the divergence in §10 instead of writing "matches the plan" is the whole reason this section exists.

### 14.2 The Engine did not just create three files
The plan's §7 lists `engine.py`, `protocol.py`, `test_engine.py`. The commit delivered 14 files, including a durable SQLite spine (`store.py` + `schema.sql`), a child supervisor (`capture_child.py`), a bounded ASR worker (`asr_worker.py`), a reference UI child (`ui_child.py`) and two stubs (`stub_capture.py`, `stub_asr.py`). Over-delivery is a fact, not a criticism — but a spec that quietly narrowed the list to match the plan would be inventing history.

### 14.3 A green gate word here would be a fabrication
This lane ran NO engine arm. Every number in this document is a READ of the source at `0e1b7f5`, or a READ of the plan of record from an older tree. `test_engine.py`'s own docstring says a SKIPPED arm is a failure and nothing is printed as PASS unless it ran; the same bar applies to this spec.

### 14.4 The spine is not the index, and this spec does not merge them
The Engine keeps `engine-spine.db` (`schema.sql:18-31`) and the index keeps `video` (`src/index/schema.sql:41-63`). They agree on exactly one field, `content_key`, by contract (`store.py:8-10`). `clip_text` is NOT the index's `text_fts` (`schema.sql:69-73`) and is not described as such anywhere in this document. The divergence is named in the schema's own comment (:14-17) and here.

### 14.5 No WASAPI measurement was made or implied
§7.3 records the tee as DESIGN (a READ of `docs/integration-sotto-app.md` §1.4/§5.1) and states that the shipped Python Engine does not implement it. The domain `BRIDGE_DEATH` `0x8889000A` in AGENTS.md belongs to the worker's WASAPI endpoint and is quoted as the shape of the cost of a cutover, never as an engine measurement.

### 14.6 Deliberately NOT done in this spec

* Not run: `py -3 src/engine/test_engine.py`, any arm, any red control, the census, the `rmtree` — all cited as source lines only.
* Not written: a rewrite of `docs/design-notes/03-engine-ipc.md` (2026-10-07), which describes the C++ `Msg` envelope and a substantially older wire shape; it is not superseded by this document and its staleness is someone else's decision.
* Not touched: `src/engine/json.{h,cpp}` and `src/engine/queue.h` in this worktree — an older C++ revision, never built or run here, mentioned only so the reader knows both exist.
* Not claimed: that the Engine arms the hotkey (UNKNOWN 1), that the capture device works (UNKNOWN 5), that the ASR side hears the live endpoint (UNKNOWN 6), or that the WASAPI cutover happened (UNKNOWN 6).

---

## 15 · SUBJECT CITATION

**Subject:** `_moved/aireplay/src/engine/` on branch `feat/engine-process`, commit `0e1b7f5b2806a48a92dcfbe3841cd01f812652c6` (2026-10-09 18:48:47 -0300, "LANE A - THE ENGINE PROCESS: single supervisor, owner of the ring, parent of capture"), 14 files, +3289 lines.

| file | blob | bytes |
|---|---|---|
| `asr_worker.py` | `35a7f3d59900d371b415ca21c02555792dde9f69` | 8793 |
| `capture_child.py` | `9765e741f256b29bead8e1e65c891e7969a29582` | 7872 |
| `engine.py` | `d0893dcb8e1334e172daee456f2855aa148a8f67` | 44913 |
| `json.cpp` | `710c9217..` | 6934 |
| `json.h` | `de2e69c6..` | 2725 |
| `protocol.py` | `fa043ae9863ac43ff6375257af924bc2f3f4964b` | 5505 |
| `queue.cpp` | `617c0b84..` | 3467 |
| `queue.h` | `3a4a598e..` | 3101 |
| `schema.sql` | `bdefc490615c56a2c7f9307894a91b3f0390e992` | 3380 |
| `store.py` | `388d366ea521cfc6ef0e1aa5ecad9d2c5e3d4b38` | 7223 |
| `stub_asr.py` | `8a15a4e2..` | 2736 |
| `stub_capture.py` | `9a79698624194c36c2c42ca9680437a34dcb5347` | 9394 |
| `test_engine.py` | `356e21a12ef45c25697b8b98d19bb61e35199539` | 37621 |
| `ui_child.py` | `fdf9c42257eee1e09dff093d0a91343451fa9494` | 7427 |

Read into scratch as `I:/cc-tmp/spec05/engine/` with `git show 0e1b7f5:<path>`; every byte count above is the blob size reported by `git ls-tree -r -l 0e1b7f5 -- _moved/aireplay/src/engine`, and the extracted files were byte-identical to those blobs. Blob sizes are LF content; this repository has no `.gitattributes` and `core.autocrlf` is unset, so on-disk sizes in a Windows checkout carry CRLF and are larger.

**Other archives read, and their revisions:** `git show 399bc851cea30e99e7c1fe8ccb1928b22bc1b1e3:_moved/aireplay/src/capture/main.cpp` (LAW 6 refusal text, `:1008`, read on `feat/engine-process`); `P4-aireplay-engine-process.md` (5908 B, sha256 `511651EC5CD1BA1E…`, untracked, product root `H:/sotto/_moved/aireplay/runs/`, absent from this worktree); `docs/design-notes/03-engine-ipc.md` 10462 B (2026-10-07); `docs/integration-sotto-app.md` 32542 B.

**The capture binary:** `H:/sotto/_moved/aireplay/_main/build/aireplay-capture.exe`, 783865 B, mtime 2026-10-09T20:51:21Z, MEASURED 2026-10-10 by census — untracked and ABSENT from this worktree (`_main/build` does not exist under `H:/sotto-wt/specs57/_moved/aireplay/`), so the `--capture-exe` default cannot resolve here and every statement about that binary in this spec is a READ, not a run.
