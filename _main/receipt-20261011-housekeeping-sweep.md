# Housekeeping sweep — 2026-10-11

Every item the register carried as "housekeeping" was re-measured on this revision instead of being
acted on. **Six of them turned out not to be defects at all**, and one was a real stray artefact.
Nothing was launched: the owner's stop order (*"para de abrir o sotto, ta travando meu pc quando ele
abre."*) is in force, so this sweep touched no runtime behaviour — the only executed code was the
Lead's own read/grep/`statSync` calls.

## Adjudication

| # | flagged as | measured on this revision | verdict |
|---|---|---|---|
| 1 | stray `app/webview/_tmp-revert.py` | untracked (`git status --porcelain` -> `??`), `git ls-files --error-unmatch` -> *pathspec did not match any file(s) known to git*, **415 959 B** — a mutant COPY of the shell left inside the PRODUCT tree | **DELETED** |
| 2 | dead `ensure_webview_shown` | `app/webview/sotto_webview.py:983`. Repo-wide grep = 27 hits, and every one is either the definition, its own docstring, the comment at `:8387`, a mutant copy of the shell under `_main/`, or a docstring that describes it (`_main/webview-child-gate.py:25`, `docs/handoff-2026-10-09-transparent-panel.md`). **No caller.** But the docstring (`:984-993`) says it is *"the composed form kept for every caller that logs one line"* and that it carries the **OLD order**, telling callers to prefer `show_webview_children` + `transparency_hack` | **NOT dead code — uncalled BY DESIGN, documented. No deletion** (removing it would also require rewriting that docstring, the comment at `:8387` and the probe docstring) |
| 3 | stale CSS comment `app/panel/panel.css:2276` | the comment claims the tail marker is *"its own element so the word spans stay countable by `paintWords`"*. `paintWords` is defined at `app/panel/panel.js:449` and CALLED at `:821` and `:827` | **NOT stale — the claim holds. No edit** |
| 4 | add `self.code_state_log('worker-reloaded')` | the reload path already emits it: `_do_worker_restart` (`:6427`) -> `self.start_worker('hot-reload')` (`:6433`) -> `if started: self.code_state_log(f'worker-started-{reason}')` (`:5477-5478`) -> `CODE_STATE reason=worker-started-hot-reload ... worker_stale=...`. The `reason=` suffix names the reload and `worker_stale` answers "is the running code the code on disk" | **ALREADY SATISFIED — a second call would be a duplicate line. No edit** |
| 5 | stale docstring `sotto_webview.py:3162-3171` | it cites pywebview's public-attribute walk as `util.py:190-206`. Read on the INSTALLED package (`C:/Program Files/Python311/Lib/site-packages/webview/util.py`, 543 lines): `:190 for name in dir(obj):`, `:193 if name.startswith('_'): continue`, `:202-206` the recursive call into a non-callable object | **EXACT — not stale. No edit** |
| 6 | `healSeams` fate | already adjudicated and DISCLOSED in `_main/receipt-20261011-audit-battery-repair.md:42-51` (*"exported and uncalled"*, exactly 2 repo hits) and listed in the module's agreed surface at `_main/_lane2-reset-probe.js:148` | **CLOSED-BY-EVIDENCE (already disclosed). No edit** |
| 7 | `tideline-body` provenance | answered by the shipped bytes themselves: `app/panel/themes/cinematic.css:898` carries *"SHIPPED AS `cine-tideline-body`: the id `tideline` names an UNRELATED design of the ..."*, with the theme live at `:901`/`:971`/`:989` and declared at `app/panel/themes/themes.js:109` | **CLOSED-BY-EVIDENCE. No edit** |

## The one real artefact, and the temp instruments

`app/webview/_tmp-revert.py` was **415 959 B** of untracked mutant shell sitting in the directory the
app is served from. Deleted. The kill filter is unaffected and still correct:
`_main/_kill-sotto-now.ps1:7` names the ARTEFACT pattern `sotto_worker\.py|sotto_webview\.py|_tmp-revert\.py|hot_reload\.py`
— it matches a copy wherever one reappears, which is the point of it.

Eight throwaway instruments were removed from `I:\cc-tmp` (probe scripts and commit-message files):
`dsh-team-error-probe.mjs` 475 B, `dsh-import-probe.mjs` 634 B, `mutant-agent-team.js` 75 077 B,
`guard-sotto-procs.ps1` 335 B, `commit-msg-step4.txt` 1 814 B, `commit-msg-step5.txt` 2 098 B,
`commit-msg-probe.txt` 875 B, `commit-msg-agents.txt` 1 132 B. **Kept on purpose**, because `AGENTS.md`
cites them as evidence: `wv-cleanup.txt`/`.ps1`, `wedge-fresh.log`/`.rc.txt`, `hotfix-test.log`/`.rc.txt`,
`clean-dump.log`/`.rc.txt`.

## Pins on this revision (measured, not inherited)

- `app/webview/sotto_webview.py` = **439 498 B**, sha256 `E5B4ADE733BC356294F669E518A50CC0125F163D034242BBBD96229C7FD11E3F` — **unchanged by this sweep**, and no byte of it was edited.
- `app/panel/panel.js` = **137 352 B** / `A0BE0694...`, `app/panel/caption-formulation.js` = **40 333 B** / `6EB5FB8A...` — read only.
- `app/panel/panel.css` — read only.

## OPEN, named (cosmetic, no product effect)

- *rename ARM T title* — not located in this sweep; a label inside an instrument, not a defect.
- *probe 889-vs-888 off-by-one* — not located in this sweep; an instrument-count question.

## NOT MEASURED

- Nothing was launched, so **no claim here is about runtime behaviour**. Every finding above is bytes,
  line text or a static citation.
- The deleted file was never executed by this sweep and its provenance (which lane wrote it) is
  unattributed — it was untracked, so git holds no record of it.
