# LANE BRIEF — shared context and hard rules for every subagent on this project

**READ THIS FILE FIRST.** You have no parent conversation history. Everything you
need to work safely is here. Do not guess paths: verify them.

---

## 1. What we are building

A **complete NVIDIA ShadowPlay clone**:

| ShadowPlay capability | what it means |
|---|---|
| Instant Replay | a rolling ring buffer; press a key, the last N seconds become a clip |
| In-game overlay | hotkey + on-screen HUD while a game has focus |
| Manual record | record now, stop, save |
| Highlights | automatic clip extraction from gameplay moments |
| Broadcast | second screen / camera / mic composite + streaming |
| Capture Card | external device input path |

Everything lands in ONE app, under Sotto, frontend LAST.

## 2. Repos and paths

| path | what |
|---|---|
| `H:\sotto` | parent repo. Sotto = real-time transcription overlay, Alt+C, WebView2 shell |
| `H:\sotto\_moved\aireplay` | **this project** (the ShadowPlay clone). A git repo |
| `H:\sotto\worker\wasapi_loopback.py` | WORKING WASAPI loopback capture in Python — reuse, do not reinvent |
| `H:\sotto\_moved\aireplay\ROADMAP.md` | the plan |
| `H:\sotto\_moved\aireplay\receipts\` | evidence receipts (17 exist). One per load-bearing claim |
| `H:\sotto\_moved\aireplay\specs\` | `01-capture-modes-and-scheduling.md`, `02-asr.md`, `03-capture-encode.md` |
| `H:\sotto\_moved\aireplay\src\capture\` | C++ capture: WGC, NVENC, ring_buffer, mp4_writer, replay, d3d11_ctx |
| `H:\sotto\_moved\aireplay\src\asr\` | Python ASR (audio, engine, runner, segment, transcribe, parity, level) |
| `H:\sotto\_moved\aireplay\src\index\` | **EMPTY — this is a missing feature, not a bug** |
| `H:\sotto\_moved\aireplay\src\ui\`, `src\engine\` | UI and a C++ json/queue lib |

`H:\aireplay` is a **junction** to `H:\sotto\_moved\aireplay`. Old receipts resolve
through it. Do not delete it; do not treat it as a separate tree.

## 3. Measured facts — rely on these, do not re-litigate, do not re-derive

- `cargo build` **works on this host**: rc=0, 215.7 MB PE binary (MZ header verified),
  221 crates. The old belief "Tauri/Rust is abandoned here" was **false** and has
  already cost a stack decision.
- **There is no hotkey.** 0 hits across `src/capture`. The cut is by time (`cut_at_s`).
  The central product promise — instant replay — does not exist yet.
- **There is no audio.** 8 of 8 sample clips have no audio stream, while the ASR
  consumes WAV. Nothing feeds the index.
- `replay.cpp:57` fixes the capture window at **1920×1080**, so any 1440p/4K60 number
  is arithmetic, not measurement. Written up in a receipt.
- The ring cap is derived from **VRAM** (`d3d11_ctx.cpp:70`) but the ring lives in
  **system RAM**. This host has **47.74 GiB** RAM. `AGENTS.md:151` sizes everything
  for "a 16 GB box". Receipt `receipt-14-ring-cap-vram-vs-ram.md` has the analysis.
- `CUDAExecutionProvider` is requested but **not loadable** on this box: ORT returns
  `['CPUExecutionProvider']` silently. The box runs on CPU.
- `src/capture/build.cmd` exists — find how it builds before inventing a build path.

## 4. HARD RULES — violating these wastes a lane

1. **Never leave a visible console window on the owner's screen.** He has been shown a
   stray `python` console twice and complained. Launch with `pythonw.exe`, or
   `creationflags 0x08000000|0x00000008` for subprocess launches. A window census runs
   every 60 s and logs `ALERTA-JANELA` with the pid — it will name you.
2. **Never pipe a native command when you need its exit code.** Do
   `cmd > file 2>&1` and then read `$LASTEXITCODE`. Never `cmd | Select-Object -First N`.
   A closed pipe hides the real status — this repo has a receipt of a gate that
   reported green over exit 2.
3. **Native `H:\` paths only.** `./node_modules/.bin/electron` does not execute here
   (rc=127, measured). Shell is PowerShell 7 (pwsh).
4. **Never grep for `AGENTS.md` or context files** — they are auto-loaded.
5. **Edit only the files you own.** If you need a file another lane owns, do NOT edit
   it: write the exact hookup (function signature, line, call site) into your receipt.
6. **Every count carries POPULATION and WINDOW.** "It works" without them is not a
   claim, it is a vibe. If you did not measure it, say `NOT MEASURED`.
7. **Do not `git commit` unless your gate is green.** Report the sha you produced.
8. **Windows paths only.** Never invent a Linux path.

## 5. Reporting — this is enforced, not optional

Your final message must end with the literal line:

```
Does your implementation meet the spec? YES - <one sentence>
```
or
```
Does your implementation meet the spec? NO - <which part and why>
```

And it must contain:

- **P0 — what I did NOW**
- **P0 — what I ALREADY did**
- **P0 — what I did NOT do, and why**
- **SELF-AUDIT**: confidence per claim and what would move it; which protocols are
  missing; which extra verification you ran; new named verification boxes you created
  (name them — an unnamed check is not a check); whether another subagent reviewed
  this (if not, say so); your gate doubts.
- Anything you report as P0 or as a self-audit finding **will be dispatched to another
  subagent to fix**. Write it so it can be acted on: name the file, the line, the fix.

## 6. Your reviewer is mandatory

When your implementation is done, dispatch a reviewer subagent:

```
task(agent_name="verifier", description="review <your lane>",
     prompt="<your receipt + the files you changed + the acceptance criteria.
              Audit for concrete defects. Edit NOTHING. Report findings only.>")
```

Then read its report. If it found a defect, fix it and re-run your gate. If you
disagree, say why with evidence. Report the reviewer's verdict verbatim in your
final message — including when it is unfavourable.

## 7. You may spawn your own lanes

If your lane parallelises, dispatch your own workers on **disjoint files** (you own
those files exclusively afterwards) or your own verifiers. Budget: up to 3 children.
Report their ids. This is how the fleet grows — the orchestrator's per-session
concurrency cap is finite, so the fleet is built by delegation.

## 8. Emergency tool fallback

If a dedicated tool call fails (a "delivery seam" error, a `write` refusal, a hang),
you are NOT softlocked: fall back to `bash`. Everything is reachable from PowerShell:

```powershell
# read a file
Get-Content <path> -Raw -Encoding UTF8
# write a file (UTF8, no BOM)
Set-Content -Path <p> -Value $text -Encoding UTF8 -NoNewline
# search file contents (the dedicated grep is ripgrep)
& "H:\env\npm-global\node_modules\@minimax-ai\code\node_modules\@vscode\ripgrep-win32-x64\bin\rg.exe" -n "pattern" <path>
# native sqlite, for the runtime store
py -3 -c "import sqlite3; c=sqlite3.connect(r'file:C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite?mode=ro', uri=True); print(c.execute('select count(*) from local_runtime_sessions').fetchone())"
```

Set `$env:PYTHONIOENCODING='utf-8'` before `py -3` or non-ASCII output dies with
`UnicodeEncodeError` on cp1252 — that has bitten two lanes today.

If a tool fails, say so and retry via the fallback. Never report a step as done
because you could not verify it.