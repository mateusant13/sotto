# Review — stdin control channel, `main.cpp`

Reviewer: read-only pass. No source file was modified.
Subject: `H:\sotto\_moved\aireplay\src\capture\main.cpp` (621 lines), branch `main`.

Code under review: `stdin_read_line` (287-303), `stdin_write_reply` (305-313), `struct StdinCtl`
(315-381), `StdinCtl::handle` (383-392), call site `arm_run` (465-500).

Headline: the merged lane is 108 lines, not 207, and the channel is a
**single-verb stub** — `handle()` implements exactly one command, `ping`. Several risks asked
about (encoder stop, cut, stats) have no handler yet, so those questions are answered against
code that does not exist yet.

---

## 1. THREAD SAFETY — NO-DEFECT-FOUND (latent; the hazard is armed but untriggered)

`StdinCtl` holds one pointer to engine state:

- `const Replay* rep = nullptr;` — `main.cpp:318`
- assigned in `start()` **before** the thread is created — `main.cpp:324`, `main.cpp:325`

That ordering is the thing that makes it safe: the write to `rep` at 324 happens-before
`std::thread` construction at 325, so the reader thread cannot observe a torn/half-set pointer.
No lock is needed for that field because there is no concurrent writer.

**`rep` is never dereferenced anywhere.** A whole-file search for `rep` in `main.cpp` returns
only the declaration (318), the assignment (324), and an unrelated local `Replay rep;` in a
different function (602). `handle()` (383-392) references `line` and `too_long` only — it never
touches `rep`, and therefore never touches `Replay`/`Stats`/`RingBuffer`.

So there is **no lock anywhere in the stdin path**, and none is needed *today*, because the
shared state is not shared yet. Fields a future verb would reach and their actual protection:

| Field the thread would touch | Lock? | Evidence |
|---|---|---|
| `Stats.*` (`frames_captured` … `cpu_kernel_100ns`) | none needed — all `std::atomic` | `common.h:53-70` |
| `Census.*` counters | none needed — `std::atomic` | `main.cpp:37-41` |
| `StdinCtl::stop` | none needed — `std::atomic<bool>` | `main.cpp:317` |
| `Replay::cfg()`, `armed_codec()`, `width()`, `height()` | **no lock in `Replay`** | `replay.h:164` shows only `cut_mu_`; the accessors are plain getters |
| `Replay::ring_used()` / `ring_evictions()` | **locked** — `ring_buffer.h:125` `mutable std::mutex mu_` | `ring_buffer.cpp:159-280` take `std::lock_guard` |
| `Replay` last-cut state | **locked** — `cut_mu_` | `replay.h:164`, `replay.cpp:221-266` |

Verdict: not a defect today. The first handler added that reads a plain `Replay` accessor while
`replay.run()` is live (498) becomes a data race with **no lock in place to catch it**.

## 2. SHUTDOWN — mixed; two real defects

**The `_WIN32_WINNT` claim is TRUE.** `main.cpp:13-15` defines `0x0601` before
`#include "common.h"` at `main.cpp:16`, and `windows.h` arrives transitively at
`common.h:16`. The ordering is correct — `CancelSynchronousIo` is declared. Not a defect.

Destructor path, traced:

- `~StdinCtl() { shutdown(); }` — `main.cpp:320`
- `shutdown()` — `main.cpp:331-338`: `stop = true`, then if `th.joinable()`,
  `CancelSynchronousIo(th.native_handle())` then `th.join()`
- explicit call site: `ctl.shutdown();` — `main.cpp:500`, right after `replay.run()` returns
  and before `replay.stats()` / `replay.last_cut()` are read (502-503)

Double-call is safe: after the first `join()`, `th.joinable()` is false, so the destructor's
second `shutdown()` (320) is a no-op. Object ordering is also correct — `StdinCtl ctl;` is
declared after `Replay replay;` (465, 468), so `ctl` is destroyed first, and the comment at
466-467 says exactly that. The thread is genuinely joinable, not abandoned.

Two defects:

- **DEFECT 2a — shutdown can cancel a reply mid-write and truncate the parent's JSON.**
  `shutdown()` (335) cancels *all* pending synchronous I/O on the reader thread. That includes
  the `WriteFile` in `stdin_write_reply` (311), not just the stdin `ReadFile`. A shutdown racing
  an in-flight reply kills it mid-line; the parent sees a line with no `\n` and blocks on a
  half-JSON reply. The comment at 328-330 only justifies cancelling the read.
- **DEFECT 2b — `stop` is dead.** It is set at 333 and read only inside a log message at 374.
  The loop (369-379) never tests it; termination depends entirely on `ReadFile` failing. That is
  consistent as written, but the flag gives a false impression of a cooperative stop.

**Process exit while blocked in `ReadFile`: not reachable through this path**, because 335
cancels first and 336 joins. It *would* be reachable if `handle()` ever blocked — see §5.

## 3. PROTOCOL — CONFIRMED-DEFECT (two, both on the reply/parse side)

Wire format, from the code: a client writes one line, terminated by `\n`, optional trailing
`\r` stripped at `main.cpp:297`. The line must be a JSON object whose first non-blank character
is `{` (386-387). Replies are a single line + `\n` (309), built by `probe_json` (233).

**Accepted command verbs — exhaustive. There is exactly one:**

| Verb | Result | Evidence |
|---|---|---|
| `ping` | `{"ok":true}` | `main.cpp:390` |
| *(anything else)* | `{"ok":false,"error":"unknown-cmd"}` | `main.cpp:391` |

Error codes emitted, exhaustive: `line-too-long` (385), `not-a-json-object` (387),
`no-cmd-field` (389), `unknown-cmd` (391). `{"ok":false,"error":"..."}` shape at 349-355.
There is **no** `stop`, `cut`, `stats`, `selftest` or `encoder` verb — the file's comment at 258
and the `rep` member at 318 imply they were planned.

**Length limit: yes, 4096 bytes** — `kMaxLine` at `main.cpp:289`.

**Escape handling in the reader: yes and it is correct.** `json_find_string` refuses any value
containing a backslash (278) rather than guessing, and the writer escapes properly
(`json_escape`, 216-227). No mangling.

**Stream desync from over-long lines: NO.** At 300, once the cap is hit the buffer is cleared,
`too_long` is set, and the loop *keeps reading until `\n`* — the remainder is drained, so the next
command still starts at a line boundary. `handle()` then refuses the whole line (385) instead of
executing the surviving fragment. This is the correct design.

- **DEFECT 3a — the parser is a substring matcher, not a JSON parser.** `json_find_string` does
  `s.find("\"" + key + "\"")` (`main.cpp:264-267`) on the raw line, with no depth tracking and
  no "first key wins at top level" rule. The comment at 258-261 admits it is "NOT a json parser",
  but the consequence is not stated: a line such as `{"x":"cmd":"ping"}` matches the pattern
  `"cmd"`, the next char is `:`, and `ping` executes. A value can forge a command. Same class of
  bug: `{"cmd":"a","cmd":"ping"}` resolves to the first occurrence, and a nested
  `{"a":{"cmd":"x"}}` resolves as if it were top-level. First-match-wins on a raw `find` is not
  a safe way to authorise a control verb.
- **DEFECT 3b — a short write is silently accepted.** `stdin_write_reply` ignores the `wrote`
  count returned at `main.cpp:311`. A pipe whose buffer is nearly full returns a partial write;
  the parent then reads a truncated JSON object as one full reply line. That *is* a stream
  desync, on the output side, and it is exactly the case the 1-byte-at-a-time reader was built to
  avoid on the input side.

## 4. ATOMICITY — NO-DEFECT-FOUND

One line = one command, guaranteed. Trace:

- `stdin_read_line` accumulates into a fresh local `std::string line;` declared per iteration
  (`main.cpp:370`), cleared at 290.
- It reads 1 byte per `ReadFile` (295) and returns `true` **only** at `\n` (296-298). No byte
  before the newline can escape the loop.
- `handle()` is called once, after the function returned a complete line (`main.cpp:378`).

So a long command cannot be split across reads and executed twice: the split bytes sit in the
local buffer and are only parsed after the terminating newline. There is a single consumer
thread, so no two fragments can interleave. The over-long path (300 + 385) discards the whole
line rather than executing the tail. A command split across two TCP segments, or delivered in
two pipe writes, is reassembled correctly.

The only cost is throughput: one syscall per byte (`main.cpp:295`). Not a correctness defect.

## 5. DEADLOCK — CONFIRMED-DEFECT (latent)

`handle()` runs **inline on the reader thread** (`main.cpp:378` → 383). There is no work queue,
no second thread, no handoff. Therefore:

- If a handler blocks (e.g. stopping the encoder, or taking `cut_mu_` at `replay.cpp:266` while
  the capture thread holds it), the reader **stops reading** immediately. Bytes accumulate in the
  pipe. No further command is parsed, including the one that would unblock it.
- The reply for the blocking command is only sent *after* `handle()` returns
  (`main.cpp:340` → 305-313). So the parent sees a **hang**, not a desync — one command
  outstanding, nothing half-written. That part is correct.
- **The defect is at shutdown.** `CancelSynchronousIo` (335) cancels pending *synchronous I/O*.
  A thread blocked in a handler is not in synchronous I/O, so the cancel is a no-op and
  `th.join()` at 336 waits for a handler that will not return. `shutdown()` hangs the same way
  at 500 and 320. The claim at 328-330 — "the read has to be CANCELLED or shutdown() would wait
  for ever" — is only true for the read; it does not cover the handler.

Not currently triggerable: the only verb is `ping` (390), which returns immediately. The moment a
blocking verb is added, the destructor at 320 can no longer guarantee the join completes, and
`Replay replay;` (465) then outlives a thread that never stopped.

---

## Summary

| # | Question | Verdict |
|---|---|---|
| 1 | Thread safety | NO-DEFECT-FOUND (latent: `rep` never dereferenced; first accessor-touching verb races with no lock) |
| 2 | Shutdown | PARTIAL — `_WIN32_WINNT` ordering correct and join is real; **DEFECT 2a** cancel can truncate a reply, **DEFECT 2b** `stop` is dead |
| 3 | Protocol | CONFIRMED-DEFECT — **3a** `find()` substring auth, **3b** unchecked short write; only `ping` accepted; 4096 cap drains correctly |
| 4 | Atomicity | NO-DEFECT-FOUND |
| 5 | Deadlock | CONFIRMED-DEFECT (latent) — blocking handler halts the reader, and `join()` at 336 then hangs |

Highest-value fixes, in order: `json_find_string` must key off structure or be restricted to a
verified top-level `cmd` (3a); `handle()` must not run inline on the reader thread, or
`shutdown()` needs a bounded join with an escape hatch (5); `stdin_write_reply` must check `wrote`
(3b); `shutdown()` must cancel only the stdin read (2a).