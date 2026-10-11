# Receipt — the theme scope leak, and shipping the fix for `panel-designs.css` (2026-10-11)

**Lane:** the theme-scope lane (generator + `theme-{1..5}.css` + oracle + receipt) and the Lead
(independent verification of every number, the `panel-designs.css` ship, and a durable gate for the
whole directory). **Nothing was launched** — the owner's stop order stands; every claim below is a
reading of bytes, a parse, or an in-process Node run.

## The defect, and why it mattered

`_main/_design-lane/gen_themes.py`'s `scope()` -> `emit()` prefixed the theme scope **per prelude LINE**,
never per comma **member**: `for one in lines: parts.append('%s %s' % (scope, one))`. The template
writes the chrome group as two lines of three members, so `.panel__header` and `.chrome` came out scoped
and the other four **leaked into every theme**; the double space after each surviving comma was the
fingerprint of the same pass.

**Measured consequence, both files:** in `panel-designs.css` the leaked
`.caption__mark{display:none}` (from `pd-tele`/`pd-mano`) beat `panel.css:2278`'s `display: inline` at
equal specificity because `panel-designs.css` is the LAST stylesheet the panel loads
(`panel.html:75` vs themes `:55-59`) — so the forming line's tail marker was invisible in the shipped
build for themes 1/2/4/5 (only theme-3 survived, its own rule at `theme-3.css:672` being stronger).

## The fix (in the generator; the CSS is regenerated, never hand-edited)

1. `emit()` splits each prelude line with the existing `_split_top(one, ',')` and prefixes **every**
   member; `_merge`'s one-mark-per-rule invariant is preserved, keyframes/`@font-face` untouched.
2. New `CONSUMED_NOT_OWNED` table + `resolve_consumed()` in `build()`: it strips comments with the gate's
   own tokenizer, finds consumed-but-undeclared tokens, **fails the build** on any token not in the table,
   else declares it at the value the file already rendered with.

| file | unscoped members | undeclared tokens | before -> after (B) | sha256[0:16] after |
|---|---|---|---|---|
| `theme-1.css` | 4 -> **0** | 0 -> 0 | 26 840 -> 26 952 | `B259A5F3894CEC06` |
| `theme-2.css` | 4 -> **0** | 0 -> 0 | 27 057 -> 27 169 | `1FB154C049F19836` |
| `theme-3.css` | 4 -> **0** | 2 -> **0** | 26 466 -> 27 302 | `B8CE0CED74E57286` |
| `theme-4.css` | 4 -> **0** | 0 -> 0 | 26 123 -> 26 235 | `DD99FFD544DCFA46` |
| `theme-5.css` | 4 -> **0** | 0 -> 0 | 27 325 -> 27 437 | `BA6C8755B5526373` |
| `panel-designs.css` | **22 -> 0** (shipped by me) | 2 -> 0 | 127 368 -> **128 716** | `FD231DC5B10B2564` |

Generator pin: `_main/_design-lane/gen_themes.py` = **160 153 B**, sha256 `0F9A3B190452DB8E…`.
The two undeclared tokens are both in **theme-3** (`--font-serif`, `--w-op`), not theme-4 as the brief
said; they were declared at the values the file already rendered with — `--font-serif: var(--font-sans)`
(undeclared anywhere, so `font-family` was invalid at computed-value time and
`.chrome__brand` inherited its parent's face, `theme-3.css:99`) and `--w-op: 1` (the consumers' own
fallback). Declared in-file rather than only at the consumer because the gate counts a token as USED
however it is written.

## GENERATOR CURRENTNESS — the precondition, proven before anything was overwritten

Run in a scratch tree (`I:\cc-tmp\theme-gen`, `zips` reached by a directory junction; nothing written
into `H:\sotto`), by me, independently of the lane:

1. `py -3 I:/cc-tmp/theme-gen/_main/_design-lane/gen_themes.py` -> **rc=0**, and the scratch generator is
   **byte-identical** to the product's fixed one (`0F9A3B190452DB8E…` on both) — so it is the fixed code.
2. Re-running it changed **0 of 7 outputs** (deterministic).
3. The parked `panel-designs.css` (`FD231DC5B10B2564…`) is **byte-identical** to a fresh run — it IS
   generator output, not a hand-edit.
4. The scratch `theme-1..5.css` are **byte-identical to the shipped product files** (`B259A5F3…`,
   `1FB154C0…`, `B8CE0CED…`, `DD99FFD5…`, `BA6C8755…`) — the generator reproduces what ships.
5. Its stdout sizes are the LF sizes; the files are CRLF, and the arithmetic closes exactly
   (125 028 + 3 688 = 128 716 B for `panel-designs.css`; 2 922 + 76 = 2 998 B for `panel-designs.js`),
   which is the pin for `panel-designs.css` = 3 688 CRLF / **0 bare LF**.

## The `panel-designs.css` ship — the one file the theme lane was not allowed to write

`app/panel/themes/panel-designs.css`: `7E740ABFCE9B720E…` (127 368 B) -> `FD231DC5B10B2564…`
(128 716 B, 3 688 CRLF / 0 bare LF), a copy of the freshly generated file. Its diff is
**47 insertions / 12 deletions** and mechanical: each comma member of the two leaked prelude groups gains
its `data-theme` prefix, and the two tokens are declared. No declaration body changed — the only
changed line carrying a design value is `+  --font-serif: var(--font-sans);`, i.e. the token declaration
itself.

## Gates, all re-run by me (not taken on report)

```
node _main/_design-lane/assert-themes.js                     rc=0  VERDICT PASS (0 unscoped, 0 undeclared x5)
node _main/_design-lane/assert-themes.js --dir theme-before   rc=1  VERDICT FAIL (4 unscoped x5 + theme-3 2 undeclared)
node _main/_design-lane/assert-themes-neg.js                 rc=0  NEG-ARM PASS (pristine GREEN + 5/5 mutants RED)
node _main/theme-scope-oracle.js                             rc=0  VERDICT PASS (per member, 148-152 members/file)
node _main/theme-scope-oracle.js --neg-arm                   rc=0  PASS, 6/6 mutants RED, each naming its violation
node _main/theme-scope-oracle.js --dir theme-before           rc=1  RED (A: 4 unscoped/file, C: packed prelude, T: theme-3 tokens)
node _main/scope-leak-oracle.js                              rc=0  PASS, 8 stylesheets, 0 leaked members
node _main/scope-leak-oracle.js --neg-arm                    rc=0  PASS, 4/4 mutants RED + control GREEN
```

`assert-themes.js` (`f63d7b76…`), `assert-themes-neg.js` (`3b3323e4…`) and `theme-assert-lib.js`
(`ee495aeb…`) are byte-identical to HEAD: the green was not bought by loosening a checker.

## A durable gate for the DIRECTORY (this is mine, and it closes a real hole)

Both theme gates cover `theme-{1..5}.css` only, so the file that actually leaked — a generated stylesheet
that loads LAST — had no gate at all. `_main/scope-leak-oracle.js` closes that: it block-parses every
`*.css` in `app/panel/themes/` (`cinematic.css`, `fonts.css`, `panel-designs.css`, `theme-{1..5}.css`),
ignores at-rules and keyframe step lists, and requires **every member of every selector prelude** to be
rooted at a theme scope. Negative arm: 4 mutants (a member loses its scope, and the real global
`.caption__mark{display:none}` rule appended, in `panel-designs.css` and `theme-1.css`) — all 4 RED, with
an untouched control copy staying GREEN. It honours `TMPDIR` and removes its scratch.

**Two defects in MY OWN first scanner, found and repaired rather than shipped:**
(a) a line-based scan that only looked at `{`-terminated lines **under-counted** continuation lines
(7 lines vs the 22 real members) — replaced with a block parser;
(b) it required `startsWith(':root[data-theme=')` and so flagged
`:root[data-theme^='cine-']` — the legitimate **prefix** form `cinematic.css` uses — as a leak. With the
fixed pattern, `cinematic.css` is GREEN (548 preludes, 0 leaked). Under the repaired instrument, the
pre-fix file measures **22 leaked members** and the shipped file **0**: the instrument discriminates.

## NOT MEASURED

- **What WebView2 actually paints.** No launch (owner's order), so every "renders identically" claim here
  is a cascade argument, not a screenshot or a computed style. In particular the two declared token values
  are the values the file ALREADY rendered with, argued from the cascade.
- The visual delta of the leak in the shipped build for the five theme files (the leaked declarations
  they carried are `transition-*` and `var(--motion-in)` resolves on the element).
- `_main/_theme-backup-113556/theme-3.css` and `_main/_audit-render/chrome-css-neg/themes/theme-3.css`
  still carry the old defect: a backup and a deliberate negative fixture, neither generated nor on the page.
- `_main/_tmp-panel-noreveal/themes/theme-*.css` hash-equal the NEW bytes; some instrument syncs that
  temp tree from `app/panel/themes/`. Not written by this lane — named here so the next reader is not
  surprised by the coincidence.
