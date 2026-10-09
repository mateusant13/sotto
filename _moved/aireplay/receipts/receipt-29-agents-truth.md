# RECEIPT 29 — AGENTS.md is the product's first instruction set, and it was lying (2026-10-07)

**Lane 21. Owner of exactly two files: `AGENTS.md` and this receipt. Nothing else was edited.**

`AGENTS.md` is auto-loaded into the context of **every** agent that touches this repo. That makes a
false sentence in it categorically worse than a false sentence in a receipt: it is not a record of
something that was once believed, it is a **standing instruction to build the wrong thing**, and it
arrives before the agent has read any code. Two such sentences had already cost real work by the
time this lane was dispatched.

Everything below was **re-measured on 2026-10-07 between 13:03 and 13:14** on this box. Every
verdict names the file and line that settles it. Claims I could not settle without executing code
are marked **UNVERIFIED as of 2026-10-07** and were **not** deleted and **not** guessed.

---

## 1. THE TWO KNOWN-FALSE CLAIMS — both corrected, and one of them was worse than stated

### 1.1 The 16 GB box (was `AGENTS.md:151`)

> was: *"The ring, not the ASR, is what breaks a **16 GB box** — consistent with law 7."*

| | |
|---|---|
| **Verdict** | **FALSE — corrected in place** |
| **Evidence** | `Get-CimInstance Win32_ComputerSystem` → **51 262 832 640 B = 47.74 GiB**, measured 2026-10-07 13:03. Not 16 GB: **2.98× the assumed machine.** |
| **Why it mattered** | It was not a typo, it was the root of a sizing error. The cap is priced from **VRAM** — `src/capture/d3d11_ctx.cpp:70` is literally `uint64_t cap = info.dedicated_vram / 16;` — while the arena it bounds is a `std::vector<uint8_t>` in **system RAM** (`ring_buffer.cpp:15`), committed in full at `init()`. On this box that yields **998.69 MiB = 2.0 % of the pool the code should be reading.** At 4K60 the ring silently keeps **46.5 s**, not the 120 s the spec promises. |

The corrected line now states the host's real RAM, names both sides of the VRAM/RAM conflation with
the two file:line that prove it, and points at receipts 14 + 16.

### 1.2 "No hotkey" — and why the brief's framing was itself half wrong

> was (elsewhere, and by omission here): *"There is no hotkey. 0 hits across `src/capture`."*

| | |
|---|---|
| **Verdict** | **FALSE since 12:12 on 2026-10-07 — corrected, with a second correction the brief did not ask for** |
| **Evidence the claim is stale** | `src/capture/trigger.h` (15 762 B, 272 lines, 12:43:09), `trigger.cpp` (24 193 B, 567 lines, 12:43:20), `trigger_selftest.cpp` / `.h`. They implement **both** paths: `RegisterHotKey` + a dedicated message-pump thread, **and** `GetAsyncKeyState` polling edge-detected against a per-binding latch (`trigger.h:12`, `:24`). |

**But correcting it to "a hotkey exists" would have been a NEW false claim, and that is the part
worth keeping.** Two things are still true, and both are verified:

1. **It is not in the product binary.** `src/capture/build.cmd` (mtime **10:41:10**) compiles
   **10 of 13** `.cpp` files. `trigger.cpp`, `trigger_selftest.cpp` and `wasapi_audio.cpp` are
   **NOT on its link line** — and `build.cmd` predates all three of them.
2. **It is not wired.** `rg -w Trigger` over `main.cpp`, `replay.cpp`, `ring_buffer.cpp`, `replay.h`
   returns **rc=1, no match**. Nothing constructs a `Trigger`. The law-6 gate runs; no key is armed.

So the truth is narrower than either sentence, and AGENTS.md law 6 now says exactly this: *the ring
is negotiated and cut by `--cut-at-s`; the key path is implemented, self-tested, unwired and
unbuilt.* An agent that read "a hotkey exists" and nothing else would build a product with a hotkey
that does not fire — the exact failure law 6 exists to prevent.

**The same shape applies to audio.** `wasapi_audio.cpp` (47 739 B, 12:56:54) exists and is also
absent from the build line. "There is no audio" is now stale in the same way, and I did not repeat
it.

### 1.3 The exact hookup, for whoever owns `src/**` (I do not)

Written out because hard rule 5 forbids me editing those files:

- `src/capture/build.cmd` — append `"%SRC%\trigger.cpp"` and `"%SRC%\wasapi_audio.cpp"` to the
  existing `g++` invocation. That is the whole build-side change.
- `main.cpp` — after `replay.arm(cfg, &err)` returns true (`:265`), construct the trigger and arm it:
  `Trigger t; t.set_ring_probe(&probe); t.arm(default_binding_ladder(), default_window_s, &err);`
  `Replay` must satisfy `RingSpanProbe` with its **one** virtual `span_seconds()`
  (`trigger.h:121-126`) — deliberately one method so the two subsystems stay decoupled.
- the run loop consumes `CutRequest` via `t.take(&req, timeout_ms)` (`trigger.h:175`) and passes
  `req.t_cut_ns` to the existing `issue_cut()`; `t.disarm()` on exit.
- **Do not call `prepare_for_test()` in production** — `trigger.h:189-192` says so explicitly.

---

## 2. A THIRD FALSE CLAIM FOUND THAT THE BRIEF DID NOT NAME

> was (`AGENTS.md`, ASR budget bullet): *"**Nobody here has run `onnx-asr` yet**, and the download
> is the owner's call."*

**Verdict: FALSE — self-contradicted eight lines below it.** The very next block reads *"ASR RESULT
— the '3 GB question' bullet above has now been RUN, and the answer is YES."* Both sentences shipped
in the same file. Marked **SUPERSEDED 2026-10-07** rather than deleted, so the history stays legible.

While there, the same bullet said the export is **670.4 MB**. The five payload files on disk sum to
**670 619 803 B** (verified below). Marked.

---

## 3. A DISEASE NOBODY HAD NAMED: EVERY DATE IN THE FILE WAS IN THE FUTURE

`AGENTS.md` stamped **13 separate claims** `2026-10-08`. The machine says **2026-10-07**, and so does
everything around it:

| source | says |
|---|---|
| `Get-Date` (this box) | **2026-10-07 13:03 -03:00** |
| every `receipts/*.md` mtime | **07/10/2026** |
| `AGENTS.md`'s own pre-edit mtime | **2026-10-07 10:48:33** |
| `receipt-14` title, and all of `docs/research/` | **2026-10-07** |

A future date **can never be detected as stale**, because a staleness calculation on it returns a
*negative* age. A claim dated yesterday is obviously suspect; a claim dated tomorrow looks fresh
forever. All 13 corrected to **2026-10-07**, with the evidence recorded in the file itself so the
owner can overrule in one edit if his own calendar really was the 8th.

---

## 4. THE DATE-STAMP RULE, AND ITS GATE

**Every measurement claim in `AGENTS.md` now carries an ISO date on the same line as the word
`measured`** — measured before: **0 of 24**. The reason the rule is *line*-scoped and not
*paragraph*-scoped is that three of the fixes initially put the date on the wrapped **next** line,
which reads correctly to a human and defeats a looser check. The gate is line-scoped for that
reason, and there is **no allowlist of exempted lines**: a blanket exemption is exactly how an
undated `measured` claim would survive.

### The gate

```
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane21-agents-truth-gate.ps1
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane21-agents-truth-gate.ps1 -NegArm
pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane21-agents-truth-gate.ps1 -ShowExclusions
```

| arm | what it asserts |
|---|---|
| **ARM-1** | the two known-false claims are ABSENT (both literal forms of each) |
| **ARM-2** | the corrected truths are PRESENT — absence alone is not a cure; a **gutted** `AGENTS.md` fails here |
| **ARM-3** | every line asserting a measurement carries an ISO date on that same line |
| **ARM-4** | no measurement line carries a date later than today (the future-date disease) |
| **ARM-C** | the **CONTROL**: a COPY with the cure reverted **MUST go RED on all four** |

### Measured run, both colours, `rc=0`

```
  [LIVE]  AGENTS.md  -- POPULATION = 483 lines / 39 314 B
    ARM-1 false claims asserted          : 0
    ARM-2 corrected truths missing       : 0
    ARM-3 undated measurement lines      : 0
    ARM-4 future-dated measurement lines : 0

  [ARM-C CONTROL (cure reverted in a COPY)]
    ARM-1 false claims asserted          : 3   RED
    ARM-2 corrected truths missing       : 4   RED
    ARM-3 undated measurement lines      : 17  RED
    ARM-4 future-dated measurement lines : 1   RED
  ARM-C verdict: RED as expected -- the control CAN say NO
LANE21-AGENTS-TRUTH-GATE PASS      (rc=0)
```

**The control reddened twice on the way here, and both are worth recording:**

1. **The gate reported FAIL on its own control, rc=1, and it was right.** My first revert stripped
   the date stamps *before* re-stamping a future date, so the strip consumed it and ARM-4 saw
   nothing. A gate that had defaulted ARM-C to "fine" would have shipped green over a dead arm. The
   message it printed — `DID NOT GO RED -- THE CONTROL IS WORTHLESS` — is the gate grading itself.
2. **The reverter's regex used `--` where the file has an em-dash `—`**, so ARM-4 stayed at 0. Found
   only because ARM-C was a hard requirement, not a warning.

**Window rule:** the gate **spawns no child process at all** (zero `Start-Process` / `Process` /
`Start-Job` — verified by grep), so it cannot leave a console window on the owner's screen. Exit
codes come from the script itself; nothing is piped to `Select-Object -First N`.

---

## 5. EVERY FACTUAL CLAIM CHECKED, WITH ITS VERDICT

`V` = verified by reading files/registry on this box, 2026-10-07.
`U` = **UNVERIFIED as of 2026-10-07** — needs code execution; left in place, not guessed.

| # | claim | verdict | evidence |
|---|---|---|---|
| 1 | `docs/brief-pesquisarsobre.txt` is 210 127 B | **V true** | `Get-Item` → 210127 |
| 2 | the brief's final turn is **lines 8357–8682** | **V true** | Python `splitlines()` = **8682**, 8681 CRLF, max line 531 B |
| 3 | mingw **g++ 15.2.0**, no MSVC | **V true (compiler)** | `g++.exe --version` rc=0 → "15.2.0". MSVC/CUDA absence not re-checked |
| 4 | `transformers 5.15.0` has **NO** `EmbeddingGemma2Model` | **V true** | `hasattr` → `False`, `C:\Program Files\Python311\...` |
| 5 | `sentence-transformers`, `torchcodec` absent | **V true** | both `ModuleNotFoundError` |
| 6 | torch 2.7 cu128, CUDA + bf16 True | **V true** | `2.7.0+cu128`, `is_available()=True`, `is_bf16_supported()=True` |
| 7 | ONNX export: 652 183 999 / 18 202 004 / 139 764 / 93 939 / 97 B | **V true, all five exact** | `models/parakeet-tdt-0.6b-v3-onnx\` |
| 8 | the five sum to **670 619 803 B** and `05-onnx-asr.md:25` slips by 30 000 B | **V true** | sum on disk = 670 619 803 exactly |
| 9 | `src/asr/` has 10 modules | **V true** | 10 `.py` |
| 10 | ring sized for "a 16 GB box" | **V FALSE → corrected** | host = 47.74 GiB |
| 11 | cap priced from VRAM at `d3d11_ctx.cpp:70` | **V true, STILL LIVE** | `cap = info.dedicated_vram / 16` |
| 12 | `seconds_kept` computed then discarded | **V true, STILL LIVE** | `replay.cpp:149` = `(void)seconds_kept;` |
| 13 | `--ring-mb` bypasses the cap unclamped | **V true, STILL LIVE** | `main.cpp:247` → `replay.cpp:133-135`, no clamp |
| 14 | "no hotkey in src/capture" | **V FALSE → corrected** | `trigger.{h,cpp}` since 12:12 |
| 15 | the hotkey is in the product | **V FALSE → corrected** | 3 of 13 `.cpp` off the build line; `rg -w Trigger` rc=1 |
| 16 | law 6's gate really refuses to arm | **V true (gate half)** | `replay.cpp:168-173` `do_gate()`; `main.cpp:265-268` exits on false |
| 17 | "nobody has run `onnx-asr` yet" | **V FALSE → corrected** | contradicted by the ASR RESULT block in the same file |
| 18 | capture window hardcoded 1920×1080 | **V FALSE in code** (not in AGENTS.md) | `replay.cpp:71` calls `negotiate_capture_window()`. **LANE-BRIEF §3 still asserts it** |
| 19 | `src/index` is EMPTY | **V FALSE** (not in AGENTS.md) | 5 `.py` incl. a 42 745 B selftest. **LANE-BRIEF §2 still asserts it** |
| 20 | `specs/*.md` exists | **V true, 7 of them** | `01`..`07`; the brief says 3 |
| 21 | the 7 "Proven material" paths exist | **V true, all 7** | each `Test-Path`ed; sizes recorded in the file |
| 22 | the panel has **5 themes** | **V true** | `themes\theme-1..5.css` |
| 23 | Redux weights are **179 MB** ternary | **V true** | 17 files, **179 020 262 B** (179.0 MB / 170.7 MiB) |
| 24 | receipt numbers are unique | **V FALSE → added to Layout** | **-15, -16, -23 each exist twice.** Cite full filenames |
| 25 | NVENC opens/initialises; 10 sessions; refusal is status 21 | **U** | needs an encoder run |
| 26 | adapter is an RTX 5080, vendor `0x10DE` | **U** | needs a DXGI run |
| 27 | EmbeddingGemma-2 = 1 488 915 288 B / 744 371 488 params | **U** | **no copy on disk**; `models/` holds only the ONNX export |
| 28 | ternary runner peaks at 3.90 GB RSS, 7–14× RTFx | **U** | needs a 3.9 GB process; weights re-measured instead |
| 29 | ASR thread sweeps (2.82 / 4.93 / 7.29 / 7.34 …) | **U** | needs a re-run; the knee is the shipped claim |
| 30 | 1 488 MB / 3.90 GB / 47.74 GiB unit convention | **V — inconsistency found** | the file mixes decimal MB and MiB: "622 MB" = 652 183 999 B = **622.1 MiB**; "179 MB" = **170.7 MiB**. Not rewritten (would change meaning); flagged |

### One false refutation I nearly filed, and did not

Claim 2 was **nearly refuted**. PowerShell's `Get-Content | Measure-Object -Line` reported **6 146
lines** for the brief, against AGENTS.md's "lines 8357–8682" — a clean, confident, wrong finding.
Python's `splitlines()` says **8 682**, and 8681 CRLF terminators corroborate it: **AGENTS.md was
right and the shell was wrong.** This is recorded because it is the same failure mode the whole
receipt is about — a measurement from the wrong instrument, filed as fact. The caveat is now in the
Layout table so the next agent does not repeat it.

---

## 6. WHAT I DID NOT DO, and why

- **I did not fix `d3d11_ctx.cpp:70`, `replay.cpp:149`, `main.cpp:247`, `build.cmd` or `main.cpp`'s
  wiring.** They are `src/**`, owned by other lanes that are writing right now (hard rule 5). The
  exact one-line change for each is in §1.2 and §4.
- **I did not touch the other files carrying stale claims** — `_main/LANE-BRIEF.md:46`,
  `specs/07-highlights.md:392`, `receipts/receipt-13-refute-integration-audit.md` row 1, and
  `research/shadowplay-parity.md`. `docs/integration-sotto-app.md:263` **already says the right
  thing** ("STALE — overtaken by new code … **Do not cite receipt-13 row 1 as current**"), which is
  the receipt that should have been the model. Not mine to edit; named so they can be dispatched.
- **I did not re-run the ASR or NVENC measurements** (rows 25–29). They need a 3.9 GB process and an
  encoder run on the owner's machine. Marked UNVERIFIED rather than repeated as fact — that is the
  whole point of the lane.
- **I did not commit.** Rule 7: the gate is green but the commit was not requested by the parent.
  Working tree only; the sha is below so a later lane can attribute this revision.

---

## 7. RECEIPT

| | |
|---|---|
| **File edited** | `H:\sotto\_moved\aireplay\AGENTS.md` — **32 400 → 39 851 B**, 483 lines |
| **sha256 (after)** | `13345A5FAAC0B2EEE438AADC86B7FC9382E0F23AF11650394CDCCA19017CEBDF` |
| **sha256 (before)** | `07E077C679E9D942ED6B5E06C4DA7385ADDB1D0CCC0FB92B4A6611317973DBA7` (32 400 B, mtime 10:48:33) |
| **Gate** | `_main\_lane21-agents-truth-gate.ps1` → `PASS`, **rc=0**, control RED on all four arms |
| **Encoding** | read/written as explicit UTF-8; 42 `→`, 15 `·`, 88 `—` intact after every edit. `Get-Content` was never used to write this file — its cp1252 console rendering mangles those glyphs |
| **Not verified** | rows 25–30 above, and the *content* of every `docs/research/` figure, which this lane read but did not re-derive |
