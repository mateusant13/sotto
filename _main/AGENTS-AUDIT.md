# AGENTS.md audit — lane/docs

Subject: `AGENTS.md`, **588 lines / 54105 B / all-CRLF** (brief said ~337 — stale).
Method: enumerate every claim about entry points, paths, toolchain, commands;
re-measure each on the real filesystem. Corrections **appended** to `AGENTS.md`
(54105 B → 60758 B, 666 CRLF / 0 bare LF). No history deleted.

## Verdicts (20 claims)

CORRECT: `run.cmd` is THE APP (9928 B/185 lines); `sotto_webview.py` is
pywebview/WebView2; `config.json` model dir; `app/electron/` gone, `_legacy-electron/`
present & dead; `--worker`/`--with-worker` alias; 5-panel module set exists;
Python 3.11.8; docs paths (`model-specs/README.md`, `original/`, `audit/`,
`tools/consultgpt.md`).

WRONG/STALE — 8, each corrected in-file:
1. `worker/models/` path **cannot exist in any worktree** (`.gitignore:64`).
2. `app/package.json` still carries `electron .`/`vite`/`tauri` — unmentioned; live
   path has **0** npm/vite matches.
3. `AGENTS.md:67` electron path exists but contradicts ":82/:186 DEAD, not a fallback".
4. 28 native sources exist — **all** under `_moved/aireplay/` (346 tracked).
5. `--audio` silently ignored — `worker:3299` `args.audio if args.selftest else None`.
6. Five fake workers, only **one** named generically at :245.
7. `TMPDIR=I:\cc-tmp` (G: → ENOSPC) undocumented.
8. `parakeet-redux-onnx-int4/` "APAGADO" — **re-downloaded**, byte counts match.

Stale-metadata: worker 173388→**236802 B**, shell 4326→**5679 lines**, battery
18595/337/sha `9DA38E…`→**26692 B/456 CRLF/0 LF/sha `038B5167…`**.

## The real fix (C): YES, the doc leads a lane into "weights absent"

`H:\sotto\worker\models` = **9 dirs**; `H:\sotto-wt\ArbV8\worker\models` =
**0 dirs, `Test-Path` False**. Weights/history are git-ignored, so absence in a
worktree is **structural**, not a finding. §0 now forbids concluding it.

## Counts carry population + window

model dirs `Get-ChildItem -Directory` / `H:\sotto`, N=9. Fake workers
`_main/*fake*.py` / this worktree, N=5. Native sources `-Recurse -Include` minus
`node_modules|.git` / this worktree, N=28. Line endings: byte scan of the whole file.

## Commits

`2944e71` receipt stub · `AUDIT1` corrections appended to `AGENTS.md` (lane/docs).
Never committed to `main`; `git add` one path at a time, no `-A`.

## Not done / out of scope

No claim about device routing, language ids or the panel DOM was re-litigated —
out of scope. `_moved/aireplay` build.cmd **not** rebuilt (no MSVC/CUDA on host).