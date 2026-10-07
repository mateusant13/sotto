# INTEGRITY AUDIT — receipt contamination re-proof

Lane: `lane/integrity` (worktree `H:\sotto-wt\integrity`, from `main` @ 8d33896)
Date: 2026-10-07 · HEAD `54730e1`

## POPULATION and WINDOW

POPULATION = **149** `.md` files claiming to be a measurement receipt, out of **233**
tracked `.md` (233 on disk, none untracked), whole repo, no directory excluded.
Rule (mechanical): filename or top-level heading matches
`receipt|recibo|verdict|report|audit|auditoria|anchor|probe|censo|profile|gate|medido|measurement`.
WINDOW = HEAD `54730e1` on `lane/integrity`, branched from `main` @ `8d33896`, 2026-10-07.

## A — the five still exist (size = git blob bytes; worktree is CRLF, +1 B/line)

| file | blob B | path |
|---|---|---|
| `_armE-fake-worker.py` | 2792 | `_main/` |
| `_audit-fake-worker.py` | 2544 | `_main/` |
| `_fake-worker-stdout.py` | 1703 | `_main/` |
| `_restart-30s-fake-worker.py` | 3725 | `_main/` |
| `_tap-restart-fake-worker.py` | 5074 | `_main/` |

The 2866/5190 seen on disk are CRLF checkouts of the same blobs — **not** content drift.

## B/C — classification of the 149

CONTAMINATED **0** · CLEAN **140** · INDETERMINATE **9**.

Contamination criterion, stated: *a receipt advancing a claim about the REAL
worker's output whose supporting number was produced by a fake.* No receipt meets
it. The fakes are only ever spawned by five instruments, and in every case the
**subject under test is the shell/bridge/panel**, declared at the point of use
(`panel-exit3-armE-receipt.md:81-83`, `reinicio-30s.md:148-149`,
`tap-restart-loop.md:90`, `auditoria-completa-20261007.md:524`). Audio `.flac`
fixtures and mutant copies are inputs, not fake workers.

INDETERMINATE (9) — receipts whose own line says the fixture cannot carry the claim:
`route-stamp-gate-20261006.md:50,61`, `receipt-20261007-src-required.md:83,87`,
`panel-live-vs-history-20261006.md:309`, `receipt-panel-five-designs.md:124`,
`receipt-housekeeping-20261008.md:176`, `speech-separation.md:295,301`,
`receipt-07-index-search.md:78,80`, `historico-vs-redux.md:384`,
`receipt-rename-panel.md:129,148`.

**This audit COULD have concluded CONTAMINATED.** The criterion was available and
was applied; zero receipts meet it.

## D — drift check: the disclosure HAS drifted

1. `_fake-worker-stdout.py` is named by **no receipt**. Its only consumer,
   `_main/tray-quit-probe.py:44`, is cited by zero `.md`.
2. `AGENTS.md:245` does not name any of the five; it describes the *pattern*.
3. `auditoria-completa-20261007.md:34,525` says the render harness is
   "pronto, **NÃO executado**". It **was** executed: `_main/_audit-render/` now
   holds `panel-chrome-real.html`, `panel-cost-{on,reduced,relayout,dbg}.html`,
   `chrome-css-neg/` — outputs of the chrome/cost arms, same commit `a3c288f`.

## E — NEW stand-in workers since that disclosure

Not five. **Eight**, plus one bridge stub:

| # | artifact | introduced |
|---|---|---|
| 6 | `_main/_redux-batch-stub.py` (4091 B) — emits `{"type":"caption"}` | `a3c288f` 2026-10-07 |
| 7 | `app/_legacy-electron/bridge-selftest.js:76` `FAKE_WORKER_PY` | legacy tree |
| 8 | `app/_legacy-electron/bridge-single-instance-selftest.js:90` `FAKE_WORKER_PY` | legacy tree |
| — | `_main/_audit-render/stub.js` (12119 B) — browser bridge stub, `?wired=1` drives a shell this repo does not have | `a3c288f` |

#6 is disclosed in its own receipt (`receipt-redux-visibility.md:325`, "a stand-in
that says so in every line"). **#7 and #8 are undisclosed in any receipt** and live
in the app tree, not `_main/`.

## Recommendation

Amend the disclosure to eight, add a receipt for `_fake-worker-stdout.py`, correct
the "NÃO executado" line, and resolve the nine INDETERMINATE claims by naming the
real instrument for each number.