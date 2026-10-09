# CAP2PANEL — does a REAL caption reach the REAL panel?

Lane: `lane/cap2panel`
Product root: `H:\sotto` (weights + real worker)
Worktree: `H:\sotto-wt\cap2panel` (copy, NO weights — by design)

## P0 under test
The render path is proven (14-method bridge, pywebview/WebView2).
The DELIVERY of a caption has never been observed. This lane closes that gap.

## Status
- [ ] 1. env TMPDIR=I:\cc-tmp
- [ ] 2. worktree created
- [ ] 3. receipt created
- [ ] 4. first commit
- [ ] A. trace caption -> panel.js (file:line)
- [ ] B. OBSERVE delivery (PROVEN vs SOURCE-ONLY)
- [ ] C. index collision facts (do NOT resolve)
- [ ] D. clip-to-search verdict

## Discipline
- every number carries POPULATION + WINDOW
- exit codes: redirect to file, read $LASTEXITCODE (never pipe into Select-Object -First N)
- never `git add -A`
- never commit to main