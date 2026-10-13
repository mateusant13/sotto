# The zip-D "ambiguity" is FALSE: the two candidates are the THEME and the SKIN

Measured 2026-10-13, `node docs/design-intake/gap-oracle.mjs --json` + the filesystem.

## What the oracle reports

`gap-oracle.mjs` returns, of 50 designs in the 5 zips: **35 strictHit, 44 aliasedHit**,
and SIX rows marked `strictAmbiguous` with NO `aliasedHit` at all. All six are zip D:

```
Rainline · Cellar Sessions · Linen Hours · Reading Hour · Last Train · Blue Hour
```

and each is printed with two candidates -- `cine-X OR X` -- so the oracle counts the
design as UNIMPLEMENTED. `TRANSLATION-SHEET.md` carries the same reading ("46 de 50
implementados, 4 em falta", "ambiguos 5"), which is a DIFFERENT count again.

## What is actually on disk

Every one of the six has BOTH halves, and they are not rivals:

| zip D design | theme | skin |
|---|---|---|
| Rainline | `cine-rainline` in `themes/cinematic.css` | `skins/cinematic-2/rainline.{caption,chrome,panel,stage}.html` |
| Cellar Sessions | `cine-cellar` | `skins/cinematic-2/cellar.*` |
| Linen Hours | `cine-linen` | `skins/cinematic-2/linen.*` |
| Reading Hour | `cine-reading-hour` | `skins/cinematic-2/reading-hour.*` |
| Last Train | `cine-last-train` | `skins/cinematic-2/last-train.*` |
| Blue Hour | `cine-blue-hour` | `skins/cinematic-2/blue-hour.*` |

A zip-D design being implemented as a THEME *and* a SKIN is the intended shape, not a
choice between two. The oracle looks for ONE live id per design, finds two, and calls it
ambiguous; the ambiguity is in the MATCHING RULE, not in the repository.

## The count this implies

**44 matched by name + 6 whose two candidates are both present = 50 of 50.** The "4 em
falta" (or 14, depending on which line of the sheet you read) is not a list of designs
waiting to be built.

## What this does NOT claim, and it matters

* **This is a NAME and PRESENCE count, not a visual one.** The sheet says it plainly and
  it stays true: *"A equivalencia visual nao foi medida. O gap-oracle e uma matriz de
  NOMES."* A design having a theme and a skin says nothing about whether it LOOKS like the
  zip.
* The oracle is NOT changed here. Resolving the six means changing its matching rule, and
  a gate edited to produce the answer someone wants is worth less than one that disagrees
  with them. Whoever changes it should add an arm that still catches a genuinely missing
  design -- otherwise the edit is indistinguishable from lowering the bar.

## The rule this leaves

The oracle control arm PASSES (3 mutations, all regress), so it is a working instrument.
**A working instrument with a wrong matching rule still reports a wrong number**, and the
control arm cannot see that: its mutations test whether the matrix NOTICES a deletion, not
whether the rule classifies a present design correctly.
