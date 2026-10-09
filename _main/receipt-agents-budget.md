# Receipt — `AGENTS.md` was over the harness instruction budget; the tail section was MOVED (never edited)

Lane: instruction-budget cut. Date: 2026-10-08. Subject: `H:\sotto\AGENTS.md`.
Success criterion: **byte-identical move or it does not count.** Nothing was summarised, rewritten,
reworded or dropped; nothing was deleted.

## 1. The defect

The harness loads `AGENTS.md` as workspace instructions with a **65 536 B** budget and truncates at
the **TAIL**, silently: `truncated AGENTS.md from 76323 to 65244 bytes`. The section
`## THE SHELL'S OWN CONTRACT — strip surface, bridge, worker hot reload (measured 2026-10-08, lane
strip-surface)` began at line 645 and ran to EOF, so it **never reached any agent** — and no agent
knew it had been dropped. That is the same defect class the file itself denounces: a silent fallback.

## 2. Boundary chosen, and why

**The moved section = the old lines 645 → 853, i.e. to EOF.** Rationale: the section's `##` header sat
at line 645, immediately after the `---` (line 643) + blank (line 644) that close
`## Keeping THIS file true`; no later `##` heading and no later `---` rule exists anywhere after it,
so the section ends at EOF (old line 853, the `*(Recibo: _main/receipt-focus-timeline.md §G4 item 6,
34 799 B, 602 linhas, sha256 `5BAE4502…`.)*` line). No boundary judgement call was needed: the only
candidate boundary was the end of the file.

## 3. Before / after

| | BEFORE | AFTER |
|---|---|---|
| size | **76 323 B** | **60 765 B** |
| sha256 | `0529104427D98861E432E555B9BD96FF5CBC7C1AF088F368204DDBEB560745B5` | `FB9B37B10B4D19CED362D2943E1E3A283B4C38EDC5C0966913C4155E700E15D9` |
| CRLF | 0 | **0** |
| bare LF | 853 | **655** |
| content lines | 853 | **655** |
| vs 65 536 B budget | over by 10 787 B | **4 771 B of headroom** |

The file was already LF-only and remains LF-only; `edit` was used, never `write`. The last byte is a
single `\n` (the pointer ends `…1 line per 30 s.\n`), so no trailing newline was added or lost.

## 4. Proof the move is byte-identical

New file `H:\sotto\docs\shell-contract.md` was created by an exact byte copy of the extracted block,
not by re-typing:

- `docs\shell-contract.md`: **16 490 B**, **209 content lines**, 0 CRLF / 209 bare LF,
  sha256 `FB64D3DB5660169F9F7A61447A843CD0BAE72A67B6CC9CA801892E6C0B451AC5`.
- The extracted block `_main\_agents-tail-block.bin` (bytes 59 833 → EOF of the old file):
  **16 490 B**, sha256 `FB64D3DB5660169F9F7A61447A843CD0BAE72A67B6CC9CA801892E6C0B451AC5`.
- **Same sha256**, and a byte-by-byte comparison loop over the two files returned
  `firstDiffByte = -1`.
- Read back from disk, the new file starts on the original header line
  `## THE SHELL'S OWN CONTRACT — strip surface, bridge, worker hot reload (measured 2026-10-08, lane
  \`strip-surface\`)`, still contains its subsections (`### Alt+C opens a STRIP, not the 380×900 panel`,
  `### Focus attribution: a RULE…`) and ends on the original last line quoted in §2.
- A stray body string unique to the moved text (`MONITOR_DEFAULTTOPRARY`) now occurs **0 times in
  `AGENTS.md`** and still occurs in `docs\shell-contract.md` — the text left, it did not vanish.

**Second, independent proof that nothing else in `AGENTS.md` moved.** Reconstructing the OLD file as
`after[0..59 833] + extracted block` yields **76 323 B** with sha256
`0529104427D98861E432E555B9BD96FF5CBC7C1AF088F368204DDBEB560745B5` — **exactly the recorded BEFORE
sha256**. That proves simultaneously (a) the first 59 833 bytes of the new file are byte-identical to
the old file's first 59 833 bytes, i.e. every line above the cut is untouched, and (b) the bytes that
were removed are exactly the bytes that now live in `docs\shell-contract.md`. (The reconstruction is
kept at `_main\_agents-rebuilt-before.md`.)

Pointer bookkeeping: `## THE SHELL'S OWN CONTRACT` occurs **exactly once** in `AGENTS.md`; the old
section's own header text (`strip surface, bridge, worker hot reload`) occurs **0 times** there.

## 5. The pointer, exactly as it now stands in `AGENTS.md` (lines 645–655, 932 B, 11 lines)

```markdown
## THE SHELL'S OWN CONTRACT — moved to `docs/shell-contract.md` (2026-10-08)

The `strip-surface` measurements (strip geometry, `SetWindowPos` argtypes, edit mode, the meter
branch and its log budget, worker hot reload) were moved **verbatim, byte for byte**, to
`docs/shell-contract.md` **by instruction budget, NOT because they were wrong** — 16 490 B, sha256
`FB64D3DB5660169F9F7A61447A843CD0BAE72A67B6CC9CA801892E6C0B451AC5`. Anchors: strip `1040×150`,
height read from `--strip-height` in the CSS (never hard-coded; `STRIP_HEIGHT_FALLBACK = 148` logs
every use); `SetWindowPos` without declared `argtypes` fails SILENTLY with `last_error=1400`;
`BRIDGE_PROBE.methods` = 17; hot reload = DEBOUNCE 2000 ms → GUARD `capture-started` → BOUNDARY at
the first closed line (`final:true`) → CEILING 25 000 ms forced → FLOOR 180 000 ms; the meter
delivers EVERY sample to the page and limits only the LOG, 1 line per 30 s.
```

It carries the title, the by-budget-not-because-wrong sentence, the new file's size + sha256, and the
five anchors (strip geometry; `SetWindowPos` argtypes; `BRIDGE_PROBE.methods`; the hot-reload
DEBOUNCE/GUARD/BOUNDARY/CEILING/FLOOR chain; the meter delivering all samples while limiting only the
log).

## 6. Still over budget? No — and therefore no second removal was executed

60 765 B is **4 771 B below** the 65 536 B budget, a comfortable margin, so per instruction no further
structural removal was made. Candidates identified but **NOT executed**, if a future lane needs room:

1. **The `_main\_audit-verify-all.cmd` battery bullet** (the long `MUST STAY CRLF, AND ITS EXIT CODE IS
   ITS VERDICT` bullet, ~4.6 KB). Recommended if room is needed: it is the most self-contained, has its
   own receipt (`_main\receipt-battery-red.md`), and the file it describes already carries the same
   warning in its own header — but it must be moved with `edit`, never `write`.
2. The historical narratives explicitly marked HISTORICAL / CLOSED / REFUTED — the F5
   `chrome-error://chromewebdata/` panel-reload story, the panel startup-flash saga, and the historical
   word-split description. Each already has a receipt (`_main\receipt-20261007-panel-startup-flash.md`,
   `_main\receipt-word-split-fix.md`), but each is interleaved with the *current* rule in the same
   bullet, so cutting them cleanly is harder than candidate 1.

## 7. Reported, NOT fixed (the move does not edit text)

In the moved text, left exactly as it was:

- **`MONITOR_DEFAULTTOPRARY`** — almost certainly meant to be `MONITOR_DEFAULTTOPRIMARY` (a Win32
  constant name). Left verbatim; a fix would be an edit, and this lane only moves.
- **`\\.\DISPLAY1`** — the device-path spelling in the moved text; left verbatim.

## 8. Files

- `H:\sotto\AGENTS.md` — edited in place (section replaced by the pointer). `edit` only.
- `H:\sotto\docs\shell-contract.md` — **created**, the moved section, byte-identical.
- Auxiliary, under `_main\`, `_`-prefixed: `_agents-tail-block.bin` (the extracted bytes),
  `_agents-tail-old.txt` (the verified transcription used as the edit's `old_string`),
  `_agents-rebuilt-before.md` (the BEFORE reconstruction used as proof).
- Untouched: `_main\_audit-verify-all.cmd` (still 32 203 B / CRLF / sha256 `EBF715E9…`), and no process
  was killed — the owner's shell 28428 and worker 29008 were left alone.
