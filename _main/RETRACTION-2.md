# RETRACTION 2 -- the first retraction was right about counts and wrong about structure

Written 2026-10-07 15:58:24 -03:00 at HEAD 9e958cd.
Supersedes part of RETRACTION.md (commit 47d424a).

## 1. WHY THIS FILE EXISTS
RETRACTION.md said "the project is not empty" and proved it with file counts. File counts
were correct and the conclusion was too weak. A lane then MEASURED the product
(_main/PANEL-RUN-VERDICT.md, 978da0d) and found something file counts cannot express:
**the app runs.** Counting receipts corrected a false claim and still pointed at the wrong
question.

## 2. WHAT IS ACTUALLY TRUE (measured, with POPULATION and WINDOW)
Source: _main/PANEL-RUN-VERDICT.md. WINDOW = 2026-10-07 15:51-15:55.

| Fact | POPULATION | Evidence |
|---|---|---|
| Entry point is app/webview/run.cmd | 1 file | AGENTS.md:76 |
| Shell = pywebview 6.2.1 on WebView2 154, python 3.11.8 | 1 execution | --help rc=0, 4048 B |
| Window created 380x900, transparent, alwaysOnTop, skipTaskbar | 1 window creation | shell's own log |
| panel.html reaches readyState complete | 1 execution | --dump-dom rc=0, 7272 B |
| 14-method JS bridge binds | 14 methods listed | BRIDGEPROBE |
| Window icon applied, sha256 d3442cfc32c96e33 | 1 hash | WINDOW_ICON_APPLIED |
| Five themes GREEN | 5 arms | browser real, headless |
| Three RED controls | 3 arms | --neg-arm rc=0 |
| Panel refuses to show without --show | 1 run | PANEL_SHOW_REFUSED |

**There is no build step, and no C++ in the panel path.** This is the correction that
matters: for three turns I hunted compiler recipes, a rejected -j flag, and merge-tip
compiles against a C++ capture pipeline that is NOT the product.

## 3. THE THREE ERROR CLASSES, and the durable rule for each
(a) I counted _main/ receipts and called that the project's size.
    RULE: a count of artefacts is not a census of capability. Ask what runs.
(b) I framed the product as a C++ capture pipeline.
    RULE: identify the entry point before instrumenting anything. Read AGENTS.md first.
    It existed the whole time and I read it after three turns of the wrong hunt.
(c) I read commit messages as evidence. "verified" in a3c288f was a claim.
    RULE: a commit message is a hypothesis. Only an executed process with an rc is evidence.

## 4. STILL UNKNOWN -- POPULATION = 0 for every item below
- What the panel DOES when it runs: are the 14 bridge methods wired to anything real?
- Does Alt+C DELIVER? Registration is not delivery.
- Does the transcription worker emit real captions, or a placeholder forever?
  _main/_audit-fake-worker.py (67 lines) suggests this was already suspected.
- Which ShadowPlay capabilities still have no implementation at all.

**A green panel is not a green product.** The shell starting is the first measured fact
about this product that was ever true. It is not the last.

## 5. WHAT THIS FILE DOES NOT CLAIM
No claim here is carried forward from an earlier report without its own evidence. Where
the population is unknown, it says so rather than estimating.
