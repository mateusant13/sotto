You are a VERIFIER subagent. Your seat is **READ-ONLY**: edit nothing, write nothing, create no
files. Report findings as text in your final message.

Your full brief is in the file:

    H:\sotto\_moved\aireplay\_main\lane-spec04-reviewer-prompt.md

Read it IN FULL first, then carry it out exactly. Do not paraphrase it away — it names the
artifact, the ground-truth files, the ten checks in priority order, and the required output
format (which begins with a single line `VERDICT: PASS` or `VERDICT: FAIL`).

Two constraints that come from this repository's house rules and are not negotiable:

- **Write no file anywhere under `H:\sotto`.** If you need scratch space for a SQLite or numpy
  experiment, use an in-memory database (`sqlite3.connect(":memory:")`) or a temp directory
  outside the workspace. If you cannot get scratch space, run the check in memory and say so.
- **Never open an audio device and never launch a GUI or a visible console window.**

Start now by reading the brief, then read `H:\sotto\_moved\aireplay\specs\04-index-search.md`
and the ground-truth source files it lists, and do the work.