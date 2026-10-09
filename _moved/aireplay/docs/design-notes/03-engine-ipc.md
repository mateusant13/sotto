# DESIGN NOTE 03 — the Engine process and its JSONL IPC

Lane `engine-ipc`. Written 2026-10-07, BEFORE the code, per the repo rule
"Do not write product code before the spec that covers it."

Covers `ROADMAP.md` §2 **P0 item 3** (Engine is the parent, UI is a reconnectable
child) and item 6 (both-colour gate on every claim).

---

## 1. Why stdin/stdout JSON Lines, and why NOT something better

**This transport is not a design choice of mine — it is already hardened in
production in this repo's own tree.** Two files, READ on 2026-10-07:

| what | where (READ) | what it does |
|---|---|---|
| the producer | `H:\sotto\worker\sotto_worker.py:374-377` | `emit(**payload)`: `json.dumps(payload, ensure_ascii=False)`, `+ "\n"`, `sys.stdout.flush()` |
| the consumer | `H:\sotto\app\webview\sotto_webview.py:6128-6183` (`_pump`) and `:6185-6201` (`_consume`) | one reader thread per stream; `for line in stream`; **re-arms a no-progress watchdog on EVERY stdout line** (`:6173` `self._arm_silence()`) |

Four properties of that bridge are inherited verbatim, because each one is a
failure this house has already paid for:

1. **One line = one JSON object, `\n`-terminated, flushed every write.**
   `emit()` flushes *inside* the function, so a publisher cannot leave a line
   sitting in a buffer — a lost clip's evidence must not be a buffer.
2. **A dead reader thread is not silently indistinguishable from a silent
   worker.** `_pump` carries a 7-line comment (`:6129-6135`) recording the
   measurement: a live run logged `statuses=0` on all 8 worker cycles because a
   reader thread died, and stderr arrived normally. So a **null stream is logged
   loudly** (`BRIDGE_PUMP_NULL`, `:6137`), never skipped silently.
3. **A malformed line increments a counter and returns — it never raises into
   the read loop.** `_consume` `:6188-6191`: `except ValueError: self.malformed
   += 1; log(BRIDGE_MALFORMED); return`. This is **already law 1's
   drop-with-a-counter, in production**, one line long. That is the precedent I
   copy.
4. **The watchdog is re-armed by progress, not by a timer tick.**
   `:6167-6171` names the bug it cured: a stream that `continue`d before
   `_arm_silence` meant the worker's own heartbeat never reached the watchdog.

### A CORRECTION to the line range in my brief

The brief cited the consumer as `sotto_webview.py:5964-5975`. **Those lines are
`snapshot()`** — a read-only dict of the bridge's own counters for the panel
state dump. It is adjacent, not the consumer. The line-by-line read with the
watchdog re-arm is `:_pump` at **`:6128-6183`**, and the malformed-counter is
`:6189`. I cite the corrected lines; the architecture is unchanged.

### What this buys, stated as the product needs it

The **Engine is the PARENT**; the UI is a **reconnectable child**. Therefore:

- The Engine's capture ring keeps running when the UI dies — the UI holds no
  handle to the ring, only to the Engine's *event stream*. That is law 6's
  pattern applied to the whole process.
- A reconnecting UI replays from the last `id` it saw and the Engine answers
  with the events it holds in its retained ring (`id`-ordered), so a UI restart
  is a `since_id`, not a rescan of the disk.
- stdout is a **one-way event channel** and stderr stays **human diagnostics** —
  the same split the production bridge already makes (`:6142` `name == 'stderr'`
  is diverted to `stderr_tail` and to `WORKER_STATS` parsing, never to the UI).
  **Never put a protocol message on stderr.**

---

## 2. The envelope (the fixed contract)

One line, one JSON object, UTF-8, `\n`-terminated:

```json
{"v":1,"type":"clip.written","id":417,"ts":1759850342123,"payload":{"clip":"clip_847.mp4"}}
```

| field | type | meaning |
|---|---|---|
| `v` | int | protocol version, currently `1`. A reader with `v != 1` **counts it as malformed**; it does not guess. |
| `type` | string | dotted, `noun.verb` (`clip.written`, `capture.armed`, `ui.hello`, `ui.resync`). |
| `id` | int | **monotonic per Engine, gapless-enough to be a resume cursor.** The UI's `ui.resync` carries `since_id`. |
| `ts` | int | **QPC-derived milliseconds** — never "seconds since the stream started" (the ASR trap already registered in `AGENTS.md`). |
| `payload` | object | type-specific, possibly empty (`{}`), never `null`. |

`id` is the one field that makes reconnect cheap, and the one field I refuse to
make optional: an id-less event cannot be resumed, so a malformed-envelope path
that keeps `v/type/ts` but loses `id` is a **reject**, not a repair.

---

## 3. THE JSON IS HAND-ROLLED — what that forbids (stated plainly)

g++ 15.2.0 here has **no JSON library and I downloaded nothing** (measured:
`src/capture/build.cmd` links only d3d11/xgi/ole32/win32 — no third-party
parser). So `src/engine/json.{h,cpp}` is a **hand-rolled writer/reader for this
fixed envelope. It is NOT a conformant JSON library.** Concretely, what that
forbids:

| forbidden | consequence for the product |
|---|---|
| **arbitrary user input** | payloads are **machine-generated only** (clip filenames the Engine itself wrote, enum-ish states, counts). A user's free text must **not** go through this writer as-is. A search box is a Tauri/WebView concern; if a transcript line must travel, it travels through the **Rust** side, which has a real serde_json. |
| **floating point** | no floats, ever, in this envelope. `score 0.89` is transmitted as **scaled int** (`score_milli: 890`) so a float can never appear and cannot round-trip lossily. |
| **`\uXXXX` escapes** | no unicode escape *emission*. UTF-8 passes through **raw**, matching the production `ensure_ascii=False` at `sotto_worker.py:376`. Bytes ≥ 0x80 are therefore opaque to the parser, which is exactly why the parser must never try to decode. |
| **control bytes in strings** | a string containing any byte < 0x20 is **REJECTED and counted** (`enc_rejected`), not escaped. This is a **framing** rule, not a cosmetic one: an unescaped `\n` inside a string would split one message into two, which is precisely the corruption ARM-B hunts. |
| **arbitrary nesting depth / arrays** | the reader reads the top-level object and keeps `payload` as **raw bytes**. It does not walk the payload. Deep parsing belongs to Rust. |

---

## 4. The three mechanisms the brief requires, and their law

### 4.1 A writer that cannot interleave partial lines from two threads

`LineWriter` takes a mutex for the **whole** `fwrite(line) + '\n' + fflush`. Not
per-field, not per-buffer — the whole record. A partial-line interleave is the
failure that makes a UI show a caption that never happened, so the lock is
coarse on purpose. **A coarse lock on a flush is cheap** (the flush is the slow
part and it must be serialized anyway); the cost is bounded by one flush.

### 4.2 A reader that tolerates a truncated last line

`LineReader::feed()` accumulates bytes; a complete line is only *delivered* when
its `\n` has arrived. `finish()` (EOF) with a **non-empty tail** means the peer
died mid-record: the tail is **rejected and counted** (`truncated_rejected`) and
**never delivered as a message**. It is *not* repaired, because a repaired line
is a fabricated message and law 2 says the clip is already written — we do not
invent evidence. ARM-B is the falsifier.

### 4.3 A bounded queue that drops WITH A COUNTER (law 1)

`Queue::push()` takes a mutex, and **never waits on a condition variable**:

```
if (unbounded) { push_back; return true; }
if (size >= bound) { dropped_++; return false; }   // the drop IS the counter
push_back; return true;
```

**The producer is never blocked**, so an AI-side message storm can never cost a
single capture frame, and **no drop is silent** — `dropped` is part of the
Engine's health event and the UI's `getStats`, exactly as the production bridge
publishes `malformed` (`:5961`).

**ARM-C is the falsifier**: 10 000 pushes into a queue bounded at 100 must give
`dropped == 9900` **exactly**. Not "about 9900". A counter that is wrong or
absent goes red.

---

## 5. The both-colour gate (`src/engine/selftest.cpp`, ONE file)

All arms live in one file and are selected by `argv[1]`. **A SKIP is never a
pass.**

| arm | colour | what it must prove | how it goes RED |
|---|---|---|---|
| **ARM-0** | GREEN | round-trip N of each message type through the queue; bounded queue never drops below its bound; **two concurrent writers produce zero interleaved partial lines**; 0 → rc 0 | any assertion fails → rc≠0 |
| **ARM-A** | **RED** | the queue check can say NO | rebuilt with `-DENGINE_SELFTEST_UNBOUNDED_QUEUE`; the arm asserts `dropped == 9900` and gets `0` → rc≠0. **If this arm is ever green, the instrument is BROKEN — that is a failure of this note's gate, not a pass.** |
| **ARM-B** | **RED** | a truncated last line is rejected, never silently accepted as a whole message | 3 good lines + 1 truncated tail → must deliver exactly 3 and count 1 rejection. A "lenient" parser that accepts the tail delivers 4 → rc≠0 |
| **ARM-C** | **RED** | drop-with-counter is exact | 10 000 pushes, bound 100 → `dropped == 9900` exactly, else rc≠0 |

ARM-A is deliberately **not** a hang: an unbounded-queue variant that "blocks
forever" would make the gate itself unreliable under a 3-minute heartbeat. It is
the same defect observed in the same 1 ms, as a wrong counter.

---

## 6. Build facts (READ, not re-derived)

- **No MSVC, no CUDA toolkit on this box.** `H:\msys64\mingw64\bin\g++.exe`
  = mingw-w64 **g++ 15.2.0** (READ from `src/capture/build.cmd:7`).
- Invocation shape copied from `src/capture/build.cmd:12`:
  `-std=c++17 -O2 -Wall -Wextra`, native `H:\` paths, output to `_main\build\`.
- The Engine links **no** d3d11/xgi — it is a transport, and keeping it free of
  the capture libs is what makes it testable on a box with no GPU work running.
- **Threads: ≤2 worker threads in the selftest**, per law 8 (the owner's machine
  outranks our throughput). The only concurrency is ARM-0's writer race, and it
  is 2 threads.
- No audio device is opened by anything in this lane. No window is ever created.

## 7. MEASURED (filled after the run — see §8 of this file, appended by the build)

See `_main/build/engine-selftest-*.txt` and the numbers recorded in §8 below.