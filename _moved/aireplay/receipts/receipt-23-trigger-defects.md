# receipt 23 — two concrete defects in the instant-replay trigger, re-measured, fixed, and gated

**Lane:** 23. **Files I own and edited (and ONLY these):**
`src/capture/trigger.h`, `src/capture/trigger.cpp`, `src/capture/trigger_selftest.h`,
`src/capture/trigger_selftest.cpp` (comments only), this receipt, and the gate below.

**Gate:** `_main\_lane23-trigger-defects-gate.ps1` → `LANE23-GATE PASS`, exit **0**.
**Regression gate (not mine, run to prove I broke nothing):** `_main\_lane1-trigger-gate.ps1`
→ `LANE1-GATE PASS`, exit **0**, 5/5 arms.

**Population / window (lane brief hard rule 6).** 1 host, 1 desktop session, 1 gate run each,
measured 2026-10-07 between 12:26 and 12:45 local. Every count below is from that run or from a
build whose sha256 is printed by the gate itself. **NOT MEASURED:** which path fires inside a
fullscreen game (no game was run, and this lane did not run one); anything about a second host.

---

## 0. The conflict warning was acted on, not ignored

`trigger.{h,cpp}` showed as ` M` in `git status --porcelain` and their mtimes were **12:24:50 /
12:25:31 / 12:25:46**, against a wall clock of **12:26:47** — L1 was landing writes seconds
before I looked. I did not edit immediately. I sampled all four files' mtimes six times over
**75 seconds** (12:27:10 → 12:28:25): byte-identical every sample, so L1's work had settled and
the files were safe to take. All my edits are after that window. Two writers on one file would
have lost both.

---

## 1. Defect 1 — `poll_once` never compared the bound modifier mask. **CONFIRMED, and worse than reported.**

### The measurement, before the fix

`_main\_lane23-modprobe.cpp` links the real `trigger.cpp` and drives `Trigger::poll_once()`
through a **synthetic** key-state function (no real keystroke is ever injected into the owner's
session — that would type into whatever window he has focused). Two bindings, copied verbatim
from the shipped ladder: `F10` (mods 0) and `Alt+F10` (`MOD_ALT`).

```
LANE23-MOD altf10_cuts=2  altf10_bound=F10,Alt+F10
LANE23-MOD plainf10_cuts=2 plainf10_bound=F10,Alt+F10
```

Reading: **one `Alt+F10` press produced TWO `CutRequest`s**, bound `F10` *and* `Alt+F10`. The
report was right about that. The report was **incomplete** in a way that matters: the second
line shows a **bare `F10` press, with no modifier held at all, ALSO produced both requests**,
including one claiming the `Alt+F10` binding. The defect is not "extra modifiers leak
into a match"; it is that the poll path ignored `HotkeyBinding::mods` **entirely**, in both
directions. Every binding for a given key fired on every press of that key.

### Why, in code

`poll_once()` computed only the key bit:

```cpp
const bool down = (ksf((int)bindings_[i].vk) & 0x8000) != 0;   // the whole test
```

`bindings_[i].mods` was read nowhere in the function. In the shipped ladder that made six
bindings for three keys (`F10`, `F9`, `F11`, `F12`, …) mutually indistinguishable on the poll
path, so a press of `F9` fired `F9`, `Ctrl+F9` and `Alt+F9` — three clips from one keystroke.

### The cure

`trigger.cpp` now measures the held modifier mask **once per tick** and compares by **EQUALITY**:

```cpp
constexpr uint32_t kModifierBits = MOD_ALT | MOD_CONTROL | MOD_SHIFT | MOD_WIN;

uint32_t live_modifier_mask(KeystateFn ksf)
{
    uint32_t m = 0;
    if (ksf(VK_CONTROL) & 0x8000) m |= MOD_CONTROL;
    if (ksf(VK_MENU)    & 0x8000) m |= MOD_ALT;
    if (ksf(VK_SHIFT)   & 0x8000) m |= MOD_SHIFT;
    if ((ksf(VK_LWIN) & 0x8000) || (ksf(VK_RWIN) & 0x8000)) m |= MOD_WIN;
    return m;
}
```

and in `poll_once()`:

```cpp
const uint32_t held_mods = live_modifier_mask(ksf);
...
const bool down = key_down && held_mods == (bindings_[i].mods & kModifierBits);
```

Three decisions inside that, each deliberate:

- **Equality, not intersection.** An intersection test is what let `Alt+F10` satisfy a binding
  that declared no modifiers. A press carrying modifiers the binding never declared must not
  match it — that is the whole requirement.
- **`MOD_NOREPEAT` is excluded from the comparison space.** It is a kernel autorepeat switch,
  not a key a human holds; comparing against it would mean no binding could ever match. The
  binding mask is masked with `kModifierBits` so a caller who sets it anyway is tolerated.
- **Read once per tick, not once per binding.** Six extra `GetAsyncKeyState` calls per tick is
  the cost, not per binding, and re-reading mid-loop could hand two bindings two different views
  of a single tick.

**Cost:** 5 extra `GetAsyncKeyState` calls per 8 ms tick when the poll path is live. This is
disclosed in `trigger.h` under the poll path's bullet list.

### After

```
LANE23-MOD altf10_cuts=1  altf10_bound=Alt+F10
LANE23-MOD plainf10_cuts=1 plainf10_bound=F10
```

### A semantic this lane chose, stated so it can be disagreed with

The latch tracks the **whole chord** (key + modifiers), so releasing `Alt` while still holding
`F10` presents the bare-`F10` chord as a fresh rising edge and fires it. That mirrors Windows'
own combination-state model for `RegisterHotKey` — the combination becoming true generates the
message — so it is a deliberate match to the OS rather than an accident. If the owning lane
prefers one press to mean one cut regardless of modifier juggling, the change is to latch on
the raw key bit instead; that is a one-line change and is NOT what this lane shipped.

---

## 2. Defect 2 — bare F12 first in the default ladder. **CONFIRMED as ordering; the "it fails" framing is REFUTED.**

### What I verified, and where

`trigger.cpp`'s `default_binding_ladder()` did have bare `F12` first, and the justifying comment
claimed: *"F12 first is deliberate: NVIDIA's own overlay and most screen recorders default away
from it, and it is the one key that is on every keyboard."*

Two separate claims there, treated separately:

- **The ordering claim was an unmeasured assertion about other companies' products.** I have no
  evidence about NVIDIA's or any recorder's defaults. It is deleted, not restated.
- **The MS reservation is real, and I read it rather than trusting the report.** From
  <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey>
  (fetched 2026-10-07, Remarks section), verbatim:

  > "The F12 key is reserved for use by the debugger at all times, so it should not be registered
  > as a hot key. Even when you are not debugging an application, F12 is reserved in case a
  > kernel-mode debugger or a just-in-time debugger is resident."

### The nuance the reviewing lane flagged is correct, and it changed the fix

MS Learn says F12 **"should not be registered"**. It does **not** say `RegisterHotKey(VK_F12)`
*fails*; the page's own failure list is an unregistered `hWnd`/`id` pair and a combination
already registered, and F12 is in neither. **So "F12-first breaks hotkeys" is false and is not
the argument used here.** Claiming it would have been adopting a claim I had not read.

### What shipped, and the weaker honest argument for it

Bare `F12` is now **LAST** in the ladder. Still bound, still polled, never primary. The
reasoning: the vendor reserves F12 for a debugger that may be resident whether or not the owner
is debugging, which makes it the **least reliable key to promote** — not a forbidden one.
Because every binding is polled regardless of order, demoting it costs the owner nothing, while
`Ctrl+F12` (F12-family, not the reserved bare key) now sits above it as the promoted option.
The full argument, with the quoted sentence and URL, is in the comment at
`trigger.cpp:default_binding_ladder()`.

### An independent measurement that supports the demotion, offered as evidence not as proof

Running L1's gate after the change logged, on this host:

```
TRIGGER key=F12          vk=0x7B mods=         registered=NO polled=true err=ERROR_HOTKEY_ALREADY_REGISTERED
TRIGGER key=PrintScreen  vk=0x2C mods=         registered=NO polled=true err=ERROR_HOTKEY_ALREADY_REGISTERED
TRIGGER key=Alt+F9       vk=0x78 mods=Alt+     registered=NO polled=true err=ERROR_HOTKEY_ALREADY_REGISTERED
TRIGGER arm: 9 key(s), 6 registered, 3 polled-only, ... integrity=LOW(0x1000)
```

Something on this host already owned bare F12 at that moment. That is **one observation of one
host at one moment** and it does not establish that F12 registration generally fails; it is
reported because it is the direction the documentation already points. Note this was measured
*after* the demotion, so it does not tell us what the pre-fix ladder returned — **NOT MEASURED
for the pre-fix ordering.**

---

## 3. The header's evidence citation. **I DELETED it, and it later turned out to have been written in the meantime.**

`trigger.h` claimed its evidence was `_main\_lane1-trigger-gate.ps1` (arms A/B/C/E) plus
`receipts\receipt-15-instant-replay-trigger.md`.

| cited artefact | at 12:27 | at 12:42 | verdict |
|---|---|---|---|
| `_main\_lane1-trigger-gate.ps1` | **exists**, 8553 B, mtime 12:27:05 | exists | citation was and is **true**; kept |
| `receipts\receipt-15-instant-replay-trigger.md` | **DOES NOT EXIST** — `Test-Path` False, and `receipts\` held only `receipt-15-offline-cut-pass1147.md` | **exists**, 12259 B, **created 12:40:02** | citation was **false** when verified |

So: **I deleted the receipt citation**, because at the moment I measured it the file was not
there and a header citing a measurement that never happened is worse than one admitting it has
none. Thirteen minutes later L1 wrote that file. The citation is therefore **restored**, and
both facts are now recorded in a CITATION HISTORY block at `trigger.h` rather than one quietly
overwriting the other — the next reader needs to know the reference was once false, so "the
receipt exists" is never again mistaken for "the receipt was there when the claim was written."

`trigger.h` also said "arms A/B/C/E" where the gate runs A–E with D as its control; corrected.

---

## 4. NOT FIXED HERE — `replay.{h,cpp}` single-slot cut queue. **This is another lane's file. Re-measured, then the fix written out.**

I did not edit `replay.{h,cpp}`. I re-measured the claim rather than repeating it, and the
finding is **narrower and sharper** than the report.

### What is true

- `replay.cpp:501` `bool cut_issued = false;` — local to `Replay::run()`; set true at `:592`;
  **never reset**. TRUE.
- The slot is genuinely single: `replay.h:168-171` — `cut_has_job_`, `cut_busy_`, one
  `cut_job_`, one `last_cut_`. TRUE.
- `Replay::issue_cut` **does not check `cut_has_job_` before overwriting**. `replay.cpp:241-248`
  assigns unconditionally:
  ```cpp
  { std::lock_guard<std::mutex> lk(cut_mu_);
    cut_job_ = job;  cut_job_.note = job.note;  cut_has_job_ = true;  cut_busy_ = true; }
  ```
  TRUE, and this is the actual bug.

### What the report got wrong, and why the correction changes the fix

**`cut_issued` is not itself the defect.** It is the latch for the *timer* cut
(`elapsed >= cut_ns`), and a timer that fires once per run is correct. The defect is that it is
the **only** cut path in the run loop. A lane that "fixes" it by resetting `cut_issued` would
re-arm the timer and cut every frame after `cut_at_s` — a worse bug than the one reported.

**A second press is not wholly overwritten — it is half-honoured, which is worse.** The cut
thread clears `cut_has_job_` under the lock *before* running `perform_cut` outside it
(`replay.cpp:475-481`), so a job posted during the write window **is** picked up on the next
loop iteration. What is genuinely broken:

1. **`wait_cut_done()` lies under a second press.** `replay.cpp:489` sets `cut_busy_ = false`
   when job 1 finishes even though job 2 is already queued, so `wait_cut_done()`
   (`:251-255`, waits on `!cut_busy_`) returns **true while job 2 has not been written**.
2. **The ring pin is corrupted.** `issue_cut` calls `ring_.pin(base.abs_off)` at `:240` for job 2
   while job 1 is still reading its pinned range; job 1's `ring_.unpin()` at `:483` then unpins
   the base that job 2 pinned.
3. **`last_cut_` is one slot** (`:488`): job 2's result overwrites job 1's.
4. **Both cuts write `cfg_.out_path`** (`:198`) — a single path, so the second clip overwrites
   the first on disk. Two presses, one file.

### Code to insert — for the lane that owns `replay.{h,cpp}`

**(a) Refuse to overwrite a slot that already holds a job — `replay.cpp`, function
`Replay::issue_cut`, anchor: the block at `replay.cpp:240-248`.** Replace:

```cpp
    ring_.pin(base.abs_off);
    {
        std::lock_guard<std::mutex> lk(cut_mu_);
        cut_job_ = job;
        cut_job_.note = job.note;
        cut_has_job_ = true;
        cut_busy_ = true;
    }
    cut_cv_.notify_one();
```

with:

```cpp
    {
        std::lock_guard<std::mutex> lk(cut_mu_);
        // A SECOND PRESS MUST NOT SILENTLY REPLACE THE FIRST.  This slot holds ONE job; taking
        // it while another is queued or in flight drops the owner's first clip and mis-pins the
        // ring for the job already reading it.  Say so, count it, keep the one in progress.
        if (cut_has_job_) {
            const char* where = cut_busy_ ? "being written" : "queued";
            ++stats_.cuts_refused;
            log_line("  REPLAY REFUSED cut at %llu ns: a cut is already %s.  This press was "
                     "DROPPED (single-slot cut queue) - this line is the only thing that says so.",
                     (unsigned long long)t_cut_ns, where);
            job.ok    = false;
            job.note  = std::string("a cut is already ") + where +
                        ": this press was DROPPED (single-slot cut queue)";
            last_cut_ = job;
            return;
        }
        ring_.pin(base.abs_off);        // ONLY an accepted job may pin the ring
        cut_job_ = job;
        cut_job_.note = job.note;
        cut_has_job_ = true;
        cut_busy_    = true;
    }
    cut_cv_.notify_one();
```

**Locking note, for whoever applies this:** this moves `ring_.pin()` inside `cut_mu_`. That is
required for correctness — a refused press must not leave a stray pin — but it inverts the
current order (`pin` outside, lock inside), so **check it against `ring_.pin`'s own locking**
before committing. If that inverts a lock order, the alternative is to keep `pin` outside and
`ring_.unpin()` explicitly on the refusal path.

**(b) Honour every press, not one per run — `replay.cpp`, function `Replay::run`, anchor: the
timer cut at `replay.cpp:590-593`.** Replace:

```cpp
        if (!cut_issued && elapsed >= cut_ns) {
            issue_cut(f.qpc_ns);
            cut_issued = true;
        }
```

with:

```cpp
        // A PRESS IS A CUT.  The timer stays as the fallback for a run with no trigger attached;
        // once a trigger IS attached every press is honoured, so the press is serviced first and
        // the timer only fires if no press has.  `cut_issued` records "a cut happened", NOT
        // "no further cuts are allowed" — do NOT reset it per frame, that re-arms the timer.
        CutRequest press_req;
        if (trigger_ && trigger_->take(&press_req, 0)) {
            issue_cut(press_req.t_cut_ns);
            ++stats_.cuts_from_hotkey;
            cut_issued = true;
        }
        if (!cut_issued && elapsed >= cut_ns) {
            issue_cut(f.qpc_ns);
            cut_issued = true;
        }
```

`trigger_` is a borrowed `Trigger*` member with a `set_trigger(Trigger*)` setter (mirroring
`Trigger::set_ring_probe`, which is the existing precedent for a borrowed pointer in this repo);
`stats_.cuts_from_hotkey` is a new `std::atomic<uint64_t>`. **Today no such member exists**: a
grep for `Trigger|trigger\.h|CutRequest|default_binding_ladder` across `src\` outside the four
trigger files returns **zero** matches, so the trigger is not wired into the app at all. This
is the first hookup, not a patch to an existing one.

**(c) One file per cut — `replay.cpp:198`, `job.path = cfg_.out_path;`.** Two presses currently
write the same path. Derive a per-cut name, e.g. insert a sequence after the base name. This one
touches output-path policy, so the owning lane should decide the scheme rather than have it
imposed from here.

---

## 5. The gate, and why it cannot pass on a broken binary

`_main\_lane23-trigger-defects-gate.ps1` → **`LANE23-GATE PASS`, exit 0.** It builds the same
probe twice — once against the real `trigger.cpp`, once against a COPY whose cure line is
reverted — and prints both sides, so arm D compares like with like.

| arm | asserts | result on the fixed build |
|---|---|---|
| **A** | one `Alt+F10` press ⇒ exactly **one** `CutRequest`, bound to `Alt+F10` | `cuts=1 bound=Alt+F10` |
| **B**-plain | trace `down,down,down,up,down,down,up` ⇒ **2** cuts, both bound `F10` | `cuts=2 bound=F10,F10` |
| **B**-alt | the same trace with `Alt` held ⇒ **2** cuts, both bound `Alt+F10` | `cuts=2 bound=Alt+F10,Alt+F10` |
| **C** | a key owned by another app: `arm()` still returns true, and the refusal **names the key** and carries Win32 `1409` | `squatter=1 arm_rc=1 registered=0 owned=1 err=1409 key=F23`, `summary_names_key=1` |
| **D — CONTROL** | arm A's assertion must **go red** on the reverted copy | `cuts=2 bound=F10,Alt+F10` → red, as required |
| **D2** | the revert must change **only** arm A — arm C byte-identical on both sides | identical |

Arm C is a **real** ownership failure, not a description: the probe calls `RegisterHotKey` on
`VK_F23` itself, *then* arms the trigger on the same key, so the OS returns a genuine
`ERROR_HOTKEY_ALREADY_REGISTERED`. It asserts two different claims — that `arm()` **still
succeeds** (the poll path is live for a key we cannot register, which is the documented contract
in `trigger.h`) and that the refusal **says which key**, because with nine bindings a bare
"registered=0" leaves the owner unable to tell which key is missing.

**D2 exists because a control can be green for the wrong reason.** A reverted copy that merely
crashed would also make arm A fail. D2 pins that the revert isolates the modifier cure and
nothing else.

### Three times this gate caught a mistake in this lane, recorded rather than hidden

1. It **failed on a `-Wformat` warning** in my own probe (`DWORD` into `%u`) — a warning the
   gate treats as a finding, and the house rule says a warning is not a warning.
2. It **failed arm B** because the expected value I wrote down was `F10,Alt+F10` — which is the
   **broken** behaviour. Each chord was firing two bindings. I had written the bug into the
   test. The assertion is now per-chord and strictly stronger.
3. It **failed arm D** because I inverted the control's logic — recording "red" for the mutant
   *passing*. The gate refused to print `PASS` over an incoherent test, which is the only
   reason the inversion was caught before it was shipped.

---

## 6. What was NOT done, and why

- **`replay.{h,cpp}` was not edited.** Rule 5. The fix is written out in §4 with file, function,
  line anchor and code so the owning lane can apply it without re-deriving it.
- **`trigger_selftest.{h,cpp}` got comment edits only, and one of them corrected a false claim.**
  `trigger_selftest.h:15` described arm C as asserting "4 suppressed holds" while the code
  asserts **5** — and L1's gate prints `suppressed=5 (want 5)`. The code was right and the
  comment was wrong; it now says 5 and derives the 5 from the trace. `trigger_selftest.cpp` was
  **not** edited by this lane at all: it shows as ` M` in `git status` because the L1 lane wrote
  it at 12:25:46, mid-flight. No behaviour changed anywhere in the self-test; L1's gate still
  passes 5/5.
- **No commit.** Hard rule 7 permits it only on a green gate, and while both gates are green the
  tree also carries another lane's untracked work, so committing here risks capturing it.
- **In-game behaviour was not measured.** No game was run. The trigger's own machinery is
  measured on this desktop session only.
- **The pre-fix F12 registration result was not measured** — the `ERROR_HOTKEY_ALREADY_REGISTERED`
  reading in §2 postdates the demotion.
- **The chord-change semantic** (releasing `Alt` while holding `F10` fires the bare binding) is
  shipped deliberately; §1 states it so it can be overridden.