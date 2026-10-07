# PUSH PREP — origin/main

**Status: prepared, NOT pushed. No `git push` was executed by this lane.**

Repo: `H:\sotto-wt\ArbV8` · branch `main` · HEAD `f9e38d6` · 206 commits
Prepared by lane `lane/pushprep` on worktree `H:\sotto-wt\pushprep`.

---

## 1. Fetch

```
git -C H:\sotto-wt\ArbV8 remote -v
origin  https://github.com/mateusant13/sotto.git (fetch)
origin  https://github.com/mateusant13/sotto.git (push)

git -C H:\sotto-wt\ArbV8 fetch origin
FETCH_RC = 0
```

**fetch rc = 0** (clean, instrument confirmed to run).

## 2. Ahead / behind

| Measure | Command | Value |
|---|---|---|
| ahead  | `rev-list --count origin/main..main` | **196** |
| behind | `rev-list --count main..origin/main` | **0** |
| left-right | `rev-list --left-right --count origin/main...main` | `0	196` |

`origin/main` = `a3c288fba2712c805c13d9df0a4daa4595cb51bd`
`main`        = `f9e38d6cc8d3fd1307d87740769091e21d079f75`

Diff scale: **434 files changed, 96 549 insertions(+), 11 deletions(-)**

## 3. Fast-forwardable?

**YES.** `git merge-base --is-ancestor origin/main main` → rc **0**.

`origin/main` is a direct ancestor of `main`. A normal `git push origin main`
advances the remote ref — **no force-push, no `--force`, no `--force-with-lease`
needed. Merge-instead is NOT required.

> Correction to the briefing: it predicted "~156 commits behind". Measured
> behind is **0**. The 156 figure was wrong in direction — local is not behind
> at all, it is 196 ahead.

## 4. The 20 most recent commits about to become public

```
f9e38d6 cron: VERDICT - the cron fires and delivers (POPULATION=1442 runs, 1433
          delivered, 99.4 pct) and stopped ~31h ago; all 4 active crons halted
          within an 11-minute window, so the fault is the scheduler not a job.
          Retracts 3 root claims that came from the briefing rather than the table.
a296318 merge: 10 lane branches via lane/mergeall (altc, asrq, audiofix, cap2panel,
          docs, e2e, gatecheck, idx16, integrity, parity)
7242a69 Merge branch 'lane/parity' into lane/mergeall
b5ba39b Merge branch 'lane/integrity' into lane/mergeall
d36f180 Merge branch 'lane/idx16' into lane/mergeall
ac8b7e1 Merge branch 'lane/gatecheck' into lane/mergeall
87e1163 Merge branch 'lane/e2e' into lane/mergeall
74acde5 Merge branch 'lane/docs' into lane/mergeall
dbb0f55 Merge branch 'lane/cap2panel' into lane/mergeall
2200d8e Merge branch 'lane/audiofix' into lane/mergeall
cb197cc Merge branch 'lane/asrq' into lane/mergeall
f32c560 Merge branch 'lane/altc' into lane/mergeall
4416fb1 mergeall: integration receipt scaffold (15 lanes, merge-tree gate before
          every merge)
dad108f integrity: trim receipt to the 400-word brief limit
caa8187 asrq: tighten receipt under the 400-word budget
ea63eae A: 16ms is a misquote (spec budget <=25ms @211200, :673); 211200 is
          arithmetic, 0 clips observed; my 20k p50=47.82ms CONTAMINATED by lane
          gatecheck PID 19996 at 100% CPU. B: real 3x redundant scan
          (search.py:68 inside per-channel loop :101-106)
8a543e9 integrity: contamination re-proof over 149 receipts - 0 contaminated,
          9 indeterminate; disclosure has drifted to 8 stand-in workers
04affb3 measure: FINDING 1 -- stale parity doc is DISLOCATED, not fictional;
          C++ tree lives in _moved/aireplay, zero refs from live app/worker
748e710 asrq: section D (3 of 9 dirs usable) + E (README 94/80-token table is stale)
e8c4bf0 docs: audit AGENTS.md against the filesystem; append 8 corrections
```

## 5. Secret scan of `origin/main..main`

Scanned all **96 549 added lines**.

**Literal keyword hits: 131 — all false positives.**

| Pattern | Hits | Verdict |
|---|---|---|
| `api[_-]?key` | 0 | — |
| `secret` | 1 | FP — `__import__("secrets").choice(` (Python stdlib RNG) |
| `token` | 126 | FP — ASR/LLM token counts, MP4 `mvex`/`moof` atom "token", FTS5 tokenizer |
| `password` / `passwd` | 4 | FP — prose about password managers in a UI exclusion list |
| `BEGIN ... PRIVATE KEY` | 0 | — |

**High-confidence credential shapes: 2 — both false positives.**

| Shape | Hits | Verdict |
|---|---|---|
| `sk-…` (OpenAI) | 0 | — |
| `ghp_/gho_/ghu_/ghs_/ghr_` | 0 | — |
| `github_pat_…` | 0 | — |
| `AKIA…` (AWS) | 0 | — |
| `Authorization: Bearer …` | 0 | — |
| `-----BEGIN` | 0 | — |
| `X = "<8+ chars>"` on a credential-ish name | 2 | FP — `GAME_TOKEN = "ERRO 0x80070005: ACESSO NEGADO"` (a Windows error string) and `tokenize = 'unicode61 remove_diacritics 2'` (SQLite FTS5 config) |

### REAL SECRETS FOUND: **0**

### Disclosure (not secrets) — READ BEFORE APPROVING

**594 absolute-path hits** leak local machine topology:

| Pattern | Hits | Example |
|---|---|---|
| `H:\` | 536 | `H:\sotto`, `H:\jcode-target-gnu\debug\sotto.exe` |
| `I:\` | 28 | `I:\cc-tmp` |
| `C:\Users\` | **13** | `C:\Users\Administrador\...` |
| `cc-tmp` | 17 | `TMPDIR=I:\cc-tmp` |

`C:\Users\Administrador` discloses the **owner's Windows account name**, and the
`H:`/`I:` paths disclose drive layout. This is information disclosure, not
credential compromise.

## 6. The remote is PUBLIC — confirmed

```
gh repo view mateusant13/sotto --json name,visibility,isPrivate,defaultBranchRef,pushedAt
{"defaultBranchRef":{"name":"main"},"isPrivate":false,"name":"sotto",
 "pushedAt":"2026-10-07T13:34:49Z","visibility":"PUBLIC"}
```

`mateusant13/sotto` is **PUBLIC**. These 196 commits are not going to a private
repo. Combined with §5, that means the owner username and drive layout above
become world-readable on approval. No credential exposure was found.

## 7. Push command (run ONLY on explicit owner approval)

```
git -C H:\sotto-wt\ArbV8 push origin main
```

Fast-forward; no force flag. Expected ref movement:
`origin/main a3c288f -> f9e38d6`.

## 8. Rollback command

```
git -C H:\sotto-wt\ArbV8 push --force-with-lease=main:a3c288fba2712c805c13d9df0a4daa4595cb51bd origin f9e38d6cc8d3fd1307d87740769091e21d079f75:main
```

This restores `origin/main` to `a3c288f`, but ONLY if the remote has not moved
past `f9e38d6` — the `--force-with-lease` guard makes it fail closed otherwise.
It is itself a force-push and needs owner consent just like the original.

**Rollback is not erasure.** GitHub retains unreachable commits via caches,
forks and PR refs. Nothing in this push set contains a secret, so retention is
not a confidentiality problem — but restoring the ref does not un-publish
content. True removal would require GitHub Support.

## 9. Other findings

- **The briefing said the working tree was clean. It is not.**
  `H:\sotto-wt\ArbV8` has 1 modified (`_main/CRON-VERDICT.md`) and 8 untracked
  paths (`FRICTION-LEDGER.md`, `_main/cron-*.py`, `_main/pos.bat`,
  `_main/spawn2.bat`, `control/`). `git push` only sends committed history, so
  these are **not** included in the push — but they are unbacked-up local work.
- Payload is modest: `_moved/` tree totals 22.9 MB on disk; largest single added
  PNG is 69 KB; no added file exceeds 20 000 lines.

---

PUSH PREP: READY (not pushed)