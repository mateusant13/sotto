# Receipt — theme scope + token resolution (2026-10-11)

Lane: theme-scope (delegated by `session-b4dd3d3d-3632-4b10-b337-5fbe44d33595`). Repo `H:\sotto`.
**Owner order in force for this whole lane: NEVER LAUNCH SOTTO.** Nothing here starts the app, the
shell, the worker, WebView2 or `_main\_audit-verify-all.cmd`; every python/node launch ran with
`windowsHide` and `TMPDIR=TEMP=TMP=I:\cc-tmp`. Two of the three instruments are pure text arithmetic
over bytes and spawn nothing at all. The owner instruction on the DESIGN also stands, verbatim:
*"os temas tao encaixados errados... cada tema encontrado dentro dos .zip, fiquem com o design IGUAL,
e so muda a posicao dos botoes. e pra realmente ser um revamp, cada zip diferente/tema, nao
simplesmente uma skin por cima ou recolor."* — no colour, type, spacing, geometry or ordering value
was changed anywhere; the only bytes that moved are a scope prefix, a line break inside one selector
list, and two token DECLARATIONS whose values are the ones the file already rendered with.

## The two defects, as measured (not as reported)

| # | defect | measured, on the pre-fix bytes |
|---|---|---|
| 1 | only the FIRST member of each comma group in a prelude was scoped, so the rest leaked into every theme | **4 unscoped selectors in EACH of the five files** — `.panel__header *`, `.status`, `.status *`, `.chrome *` |
| 2 | tokens consumed with no declaration anywhere and no fallback | **theme-3.css only, 2**: `--font-serif` (no fallback) and `--w-op` (consumed as `var(--w-op, 1)`) |

Two corrections to the brief I was given, both re-measured: the gate prints only THREE of the four
unscoped selectors (the lib slices `problems` to 3), and **both** undeclared tokens are in `theme-3.css`,
**not** theme-4. `--w-op` DOES carry a fallback (`var(--w-op, 1)`), and it is stamped at runtime by
`app/panel/panel.js` (`paintWords`); `--font-serif` has no fallback and is declared nowhere in the repo.

## Root cause, read out of the generator

`gen_themes.py` `scope()` -> `emit()` prefixed the theme scope **per PRELUDE LINE**, never per member:

```python
scope = ("%s body" % ROOT % n) if mark == 'B' else (ROOT % n)
for one in lines:                       # <- one entry per SOURCE LINE, not per selector
    parts.append('%s %s' % (scope, one))
```

The template writes that group as two lines of three members each
(`gen_themes.py:1425-1426` before the fix), so `.panel__header` and `.chrome` came out scoped, the other
four did not, and the double space after each surviving comma was the fingerprint of the same pass.

## The fix (two hunks in `_main/_design-lane/gen_themes.py`)

1. **Per-member scoping.** `emit()` now splits every prelude line with the existing `_split_top(one, ',')`
   (depth-0, quote-aware, so `:is(a, b)` and `[x="a,b"]` stay whole) and prefixes **each member**.
   `_merge()` still fixes ONE mark per rule, so every member of a list keeps the same scope — the
   invariant its own docstring states. `emit_plain()` (keyframes / `@font-face`) is untouched: it adds
   no scope, so it never had this defect.
2. **Token resolution, with the rule now enforced at generation time.** A new `CONSUMED_NOT_OWNED` table
   plus `resolve_consumed(text, sel)`, called from `build()`: it strips comments (the same tokenizer the
   gate uses, so a token named in prose is not a declaration), finds every consumed-but-undeclared token,
   **fails the build** if one is not in the table, and otherwise appends a scoped `:root` block declaring
   it. Both lanes call `build()`, so the rule now holds for `theme-1..5` AND for the `pd-*` designs.
   Post-fix pins: the per-member loop at `gen_themes.py:2321`, the table at `:2369`, `resolve_consumed` at
   `:2377`, the call at `:2475`; the four hunk headers are `@@ -2310,8 +2310,20 @@`, `@@ -2328,0 +2341,72 @@`,
   `@@ -2386 +2470 @@` and `@@ -2390,0 +2475 @@`. Template line numbers cited in this receipt are
   unchanged by the fix (`SKIN` group `:1425`, `CHROME[3]` `var(--font-serif)` `:1812`, `var(--w-op`
   `:701`/`:1876`) unless the text says otherwise.

**Which of the two allowed repairs, and why.** The brief allowed either an honest fallback at the consumer
or a declaration inside the theme file — and since the gate’s rule 3 counts a token as USED however it is
written (`var(--x, fallback)` included), only a DECLARATION can clear it. Both tokens are therefore
declared, at the value the file already rendered with:

| token | declared value | why that value changes no pixel |
|---|---|---|
| `--font-serif` | `var(--font-sans)` | Declared nowhere, `font-family: var(--font-serif)` was **invalid at computed-value time**, so `font-family` (an inherited property) fell back to `inherit` and `.chrome__brand` took its PARENT’s face — `.chrome--mano[data-chrome="head"]`, which this same theme sets to `var(--font-sans)` (rule at `theme-3.css:625`, its `font-family: var(--font-sans)` at `:631`, the value at `:99`). Pointing the token at `--font-sans` is that same stack, stated instead of inherited. |
| `--w-op` | `1` | The consumers already read `var(--w-op, 1)`, so 1 IS the value they paint with before `panel.js` stamps a per-span value; the inline stamp still wins. |

`--font-serif`’s value references `--font-sans`, which **is declared in the same file** (`theme-3.css:99`),
so the declaration resolves; verified statically (the appended block references no token the file does not
declare). **This is reasoned from the cascade, not measured in a browser** — see *What was NOT measured*.

## Generator currentness, BEFORE and AFTER (the required proof)

**BEFORE** — the pre-fix generator was run into a scratch tree (`I:\cc-tmp\theme-gen`, `zips` reached
through a directory junction to the repo, nothing written into `H:\sotto`) and byte-diffed against the
shipped files: **all 7 outputs byte-identical** (`theme-1..5.css`, `panel-designs.css`, `panel-designs.js`).
The generator WAS current, so the shipped CSS was safe to overwrite with generated output.

**AFTER** — the patched generator, run the same way, reproduces the five shipped stylesheets
**byte-for-byte**, and still reproduces `panel-designs.js`:

| output | shipped | regeneration | verdict |
|---|---|---|---|
| `theme-1.css` | 26952 B | 26952 B | IDENTICAL |
| `theme-2.css` | 27169 B | 27169 B | IDENTICAL |
| `theme-3.css` | 27302 B | 27302 B | IDENTICAL |
| `theme-4.css` | 26235 B | 26235 B | IDENTICAL |
| `theme-5.css` | 27437 B | 27437 B | IDENTICAL |
| `panel-designs.js` | 2998 B | 2998 B | IDENTICAL |
| `panel-designs.css` | 127368 B / `7e740abf…` | 128716 B / `fd231dc5…` | **DIFFERS — out of write scope, see RESIDUAL** |

The complete line diff of the five shipped files is 2 removed + 6 added lines each (theme-3: 2 + 19),
`git diff --numstat` = `6 2` x4 and `19 2` for theme-3 — i.e. one 2-line prelude became 6 lines, plus the
token block in theme-3. Nothing else in any of the five files differs, including every declaration body.

## Per file: before -> after

| file | unscoped before | unscoped after | undeclared before | undeclared after | size before | size after | sha256 after |
|---|---|---|---|---|---|---|---|
| `theme-1.css` | 4 | **0** | 0 | 0 | 26840 | 26952 | `b259a5f3894cec06f326aad9487c7b4d75e1eddf6def23b84b161e4f5b581a5b` |
| `theme-2.css` | 4 | **0** | 0 | 0 | 27057 | 27169 | `1fb154c049f19836c5a6f736ff28257c0a93c9b999b232560bca237af2cf7742` |
| `theme-3.css` | 4 | **0** | 2 | **0** | 26466 | 27302 | `b8ce0ced74e57286e977ba20bedc4264bc5e8c1eef72de329a6593f7226ee458` |
| `theme-4.css` | 4 | **0** | 0 | 0 | 26123 | 26235 | `dd99ffd544dcfa46700a82e777f91ac38ee3d65d55bae856d9100b59aa035c25` |
| `theme-5.css` | 4 | **0** | 0 | 0 | 27325 | 27437 | `ba6c8755b5526373eec343329ccfe9944fca21ba0c818a587ff1d64f59bfcafa` |

Pre-fix sha256 (measured on the working tree before the edit, and independently reconstructed from
`git show HEAD:` + LF->CRLF, which reproduced size and hash exactly for all five):
`theme-1 67b6aa34…`, `theme-2 0b52fb20…`, `theme-3 d9101d72…`, `theme-4 ee07536d…`, `theme-5 2d4104fb…`.
All five are 0 bare LF, CRLF throughout, as before (706/740/719/700/777 CRLF pairs).

### Artefacts created or changed by THIS lane

| path | state | bytes | sha256 |
|---|---|---|---|
| `_main/_design-lane/gen_themes.py` | modified (4 hunks, 94+/9-) | 160153 | `0f9a3b190452db8e1ada84c1b6a83c8f57448377600e3b95677e1f8e939cb313` |
| `app/panel/themes/theme-1.css` | regenerated | 26952 | `b259a5f3894cec06f326aad9487c7b4d75e1eddf6def23b84b161e4f5b581a5b` |
| `app/panel/themes/theme-2.css` | regenerated | 27169 | `1fb154c049f19836c5a6f736ff28257c0a93c9b999b232560bca237af2cf7742` |
| `app/panel/themes/theme-3.css` | regenerated | 27302 | `b8ce0ced74e57286e977ba20bedc4264bc5e8c1eef72de329a6593f7226ee458` |
| `app/panel/themes/theme-4.css` | regenerated | 26235 | `dd99ffd544dcfa46700a82e777f91ac38ee3d65d55bae856d9100b59aa035c25` |
| `app/panel/themes/theme-5.css` | regenerated | 27437 | `ba6c8755b5526373eec343329ccfe9944fca21ba0c818a587ff1d64f59bfcafa` |
| `_main/theme-scope-oracle.js` | NEW | 14423 | `bddb22395b44883f2c72dd6a8cdf261b8944272b01a3724c53d577a258edb257` |
| `_main/receipt-20261011-theme-scope.md` | NEW (this file) | — | — |

Pre-fix pin for the generator, reconstructed from `HEAD` (`155011 B / 3180 CRLF / 0 bare LF`, exactly the
triple measured on the working tree before the edit): `289a1f14278cd8e5269e9a6f18ddd7416599506de61613fb830aa0d5116a1c9f`.
Note the generator prints the LF length of its text (`26246 bytes` for a 26952-byte file); the file itself
is written with `newline='\r\n'`, so the on-disk size exceeds the printed number by the line count. That
is pre-existing behaviour, not a regression.

## Instruments, both colours, rcs

| instrument | colour | command | rc | verdict |
|---|---|---|---|---|
| `assert-themes.js` (the gate, UNCHANGED) | BEFORE, on the sha-verified pre-fix copy | `node _main/_design-lane/assert-themes.js --dir I:\cc-tmp\theme-before` | **1** | `VERDICT FAIL — 5 file(s) violated the contract`; 4 unscoped each, `theme-3` +2 undeclared |
| `assert-themes.js` (the gate, UNCHANGED) | AFTER | `node _main/_design-lane/assert-themes.js` | **0** | `VERDICT PASS`, 0 unscoped / 0 undeclared in all five |
| `assert-themes-neg.js` (UNCHANGED) | AFTER | `node _main/_design-lane/assert-themes-neg.js` | **0** | `NEG-ARM VERDICT PASS` — pristine copy GREEN, all 5 mutants RED naming their own violation |
| `theme-scope-oracle.js` (NEW) | BEFORE, same pre-fix copy | `node _main/theme-scope-oracle.js --dir I:\cc-tmp\theme-before` | **1** | RED: `A:` 4 members unscoped per file, `C:` 1 packed prelude per file, `T:` `--font-serif, --w-op` in theme-3 |
| `theme-scope-oracle.js` (NEW) | AFTER | `node _main/theme-scope-oracle.js` | **0** | `VERDICT PASS` |
| `theme-scope-oracle.js` (NEW) | AFTER + `--neg-arm` | `node _main/theme-scope-oracle.js --neg-arm` | **0** | `VERDICT PASS` — pristine GREEN and all **6** mutants RED, each naming its own violation |

**The gate was not weakened.** `assert-themes.js` (1470 B, `f63d7b76…`), `assert-themes-neg.js`
(3967 B, `3b3323e4…`) and `theme-assert-lib.js` (5110 B, `ee495aeb…`) are **byte-identical to `HEAD`** —
`git status` lists none of them as modified. The neg-arm’s pristine arm was RED only because defect 1 was
real; fixing the subject turned the whole neg-arm green with the five mutants still RED.

### What the new oracle claims, and why it can say NO

It is not a copy of the gate. It asks the question the defect turned on — is the scope applied **per
member of a selector list** or once per **source line** — and checks four things:
**A** every member of every list carries this file’s own scope; **B** the six selectors that used to leak
are still ONE rule of six members in the template’s order (the fix re-scopes the list, it does not
fragment it into six rules, which would be a different cascade); **C** no prelude still PACKS members onto
one line (comma + spaces, the pre-fix emission shape); **T** every consumed token is declared in the file.
`--neg-arm` mutates an **in-memory copy** — an in-memory copy is the only copy made; nothing is written —
and requires RED from each of six mutants: reverted scoping in theme-1 and theme-5 (naming that theme),
the token block removed, each token dropped **alone** (so the check must name the right one), and one
group re-scoped to a foreign theme. It also re-hashes all five shipped files at the end and prints
`shipped files unchanged by this run: yes`.

## NOT MEASURED — named, not implied

* **What WebView2 actually paints.** Launching is forbidden by the owner’s standing order, so nothing here
  is a screenshot, a pixel diff or a computed-style read. Every "renders identically" claim above is a
  cascade argument, and the two instruments are byte/selector instruments.
* **The cross-theme blast radius of the leak in the shipped build** is argued from the cascade, not
  observed: the leaked declarations in the theme files are `transition-*` only, and `var(--motion-in)`
  resolves on the element, so the five duplicate copies resolve to the same value and the visually
  identical result is expected — but a browser was not run to confirm it.
* **`_main/_theme-backup-113556/theme-3.css` and `_main/_audit-render/chrome-css-neg/themes/theme-3.css`**
  still carry the old defect. They are a backup and a deliberately-broken negative fixture, are not
  generated and are not on the page; they were NOT touched and were NOT re-measured beyond the token grep.
* **UNDECLARED-TOKEN RE-CHECK for the rest of the page.** The "declared nowhere in the repo" claim for
  `--font-serif`/`--w-op` was re-run this session over `app/`, `_main/`, `worker/`, `docs/` (excluding
  `.git`, `node_modules`, `__pycache__`, `zips/`): **0 declarations, 5 consumers** (theme-3.css x3,
  panel-designs.css x2). Nothing outside those four roots was searched.

## RESIDUAL RED — honest, out of write scope, with the fix already generated

**`app/panel/themes/panel-designs.css` carries the SAME defect and I was forbidden to write it.** My write
scope was `theme-*.css` only, so the shipped file is untouched and `git status` shows it unmodified.
Measured, both revisions:

| revision | bytes | sha256 | selectors | unscoped | undeclared |
|---|---|---|---|---|---|
| **shipped (live)** | 127368 | `7e740abfce9b720e1ed74441e66427ab9660155e8872b7d6aece9518856c47d8` | 787 | **22** | `--font-serif`, `--w-op` |
| **regeneration (parked)** | 128716 | `fd231dc5b10b2564f459443c555e4e9e6264bb328f0ba9376e25f4690e01b4a1` | 788 | **0** | none |

The parked file is at `I:\cc-tmp\theme-gen\app\panel\themes\panel-designs.css`; shipping it is one copy.
The 22 unscoped selectors are 5 designs x 4 (`.panel__header *`, `.status`, `.status *`, `.chrome *`) plus
`.caption__mark` twice (pd-tele and pd-mano). Because the generator is now FIXED, `panel-designs.css` is
the one file the generator no longer reproduces byte-for-byte — the regeneration is *ahead* of the shipped
copy, never behind it.

**A VISIBLE consequence, measured statically.** `gen_themes.py:2806` and `:2830` (post-fix numbering;
`:2721`/`:2745` in the pre-fix revision, +85) write
`@S@ .caption__time, @S@ .caption__mark { display: none; }` — both members marked `@S@`, so both were
meant to be scoped — and the per-line bug emitted `.caption__mark { display: none; }` unscoped. The base
rule `panel.css:2278` says `display: inline` at the same specificity, and `panel-designs.css` is the LAST
stylesheet on the page (`panel.html:75`, after the five themes at `:55-59`), so the leaked declaration
wins: **`.caption__mark` is `display: none` for theme-1, theme-2, theme-4 and theme-5 in the shipped
build** — the forming line’s tail marker that `panel.js:807` creates and `panel.css:2276` documents is
invisible there. Only `theme-3` survives, because its own rule (`theme-3.css:672`, declaration at
`:675`) sets `display: inline-block` at higher specificity. Fixing this needs the `panel-designs.css` regeneration
above; the theme files cannot fix it from their side.

## Write scope, proven

`git status --porcelain` for this lane’s paths lists exactly: `M _main/_design-lane/gen_themes.py`,
`M app/panel/themes/theme-1.css` … `theme-5.css`, and `?? _main/theme-scope-oracle.js`. **Nothing else.**
`worker/**`, `app/panel/panel.js`, `app/panel/panel.css`, `app/panel/history-store.js`,
`app/webview/**`, `AGENTS.md`, `docs/audit/**`, `cinematic.css`, `themes.js`, `fonts.css`,
`panel-designs.css` and `panel-designs.js` are all untouched by me (`app/panel/panel.js` does appear as
`M` in the working tree — that is another lane’s work, not mine). The scratch tree lives in `I:\cc-tmp`;
nothing was written to `G:`. No git write command was issued (the Lead commits): only `git status`,
`git show`, `git diff`, `git log`, `git cat-file` reads.

Incidental, not mine: `_main/_tmp-panel-noreveal/themes/theme-*.css` now hash-equal the NEW shipped bytes,
i.e. some instrument synchronises that temp panel tree from `app/panel/themes/`. I did not write it.

## Appendix — the AFTER colour, verbatim

```
$ node _main/_design-lane/assert-themes.js
dir: H:\sotto\app\panel\themes
GREEN  theme-1.css  selectors=148 scoped=148 foreign=0 @import=false url()=false remote=false tokens=39 undeclared=0
GREEN  theme-2.css  selectors=152 scoped=152 foreign=0 @import=false url()=false remote=false tokens=39 undeclared=0
GREEN  theme-3.css  selectors=150 scoped=150 foreign=0 @import=false url()=false remote=false tokens=41 undeclared=0
GREEN  theme-4.css  selectors=149 scoped=149 foreign=0 @import=false url()=false remote=false tokens=39 undeclared=0
GREEN  theme-5.css  selectors=148 scoped=148 foreign=0 @import=false url()=false remote=false tokens=39 undeclared=0
VERDICT PASS — all five theme files are scoped to their own theme, load no remote content, and declare every token they use.
$ echo $?   ->   0

$ node _main/theme-scope-oracle.js
ARM 1  PRISTINE (the shipped bytes)
  GREEN theme-1.css    members=148 scoped=148 multi-member-groups=14 tokens=39 undeclared=0 sha256[0:16]=b259a5f3894cec06
  GREEN theme-2.css    members=152 scoped=152 multi-member-groups=13 tokens=39 undeclared=0 sha256[0:16]=1fb154c049f19836
  GREEN theme-3.css    members=150 scoped=150 multi-member-groups=13 tokens=41 undeclared=0 sha256[0:16]=b8ce0ced74e57286
  GREEN theme-4.css    members=149 scoped=149 multi-member-groups=13 tokens=39 undeclared=0 sha256[0:16]=dd99ffd544dcfa46
  GREEN theme-5.css    members=148 scoped=148 multi-member-groups=13 tokens=39 undeclared=0 sha256[0:16]=ba6c8755b5526373
  the group the defect leaked, as re-scoped by the fix (6 members, ONE rule):
    .panel__header / .panel__header * / .status / .status * / .chrome / .chrome *
VERDICT PASS -- every member of every selector list is scoped to its own theme, the leaked group is intact,
no prelude packs members onto one line, and every consumed token is declared.

$ node _main/theme-scope-oracle.js --neg-arm
  PASS  revert-scoping theme-1           want=RED naming "NOT scoped to theme-1"  got=RED  touched~4 lineDelta=4
  PASS  revert-scoping theme-5           want=RED naming "NOT scoped to theme-5"  got=RED  touched~4 lineDelta=4
  PASS  revert-token-block theme-3       want=RED naming "--font-serif"           got=RED  touched~13 lineDelta=13
  PASS  drop-only---font-serif theme-3   want=RED naming "--font-serif"           got=RED  touched~1 lineDelta=0
  PASS  drop-only---w-op theme-3         want=RED naming "--w-op"                 got=RED  touched~1 lineDelta=0
  PASS  foreign-scope theme-2            want=RED naming "ANOTHER theme"          got=RED  touched~6 lineDelta=0
  shipped files unchanged by this run: yes (all 5 sha256 identical before/after)
VERDICT PASS -- pristine GREEN and all 6 mutant(s) RED, each naming its own violation.
```

## Appendix — the BEFORE colour, verbatim (same instruments, sha-verified pre-fix bytes)

```
$ node _main/theme-scope-oracle.js --dir I:\cc-tmp\theme-before
  RED   theme-1.css    members=148 scoped=144 tokens=39 undeclared=0 sha256[0:16]=67b6aa34b97eb541
        A: 4 member(s) NOT scoped to theme-1: .panel__header * | .status | .status * | .chrome *
        C: 1 prelude(s) PACK members onto one line (comma + spaces), the pre-fix emission shape
  RED   theme-2.css    members=152 scoped=148 ...   (same two reasons)
  RED   theme-3.css    members=149 scoped=145 tokens=41 undeclared=2 sha256[0:16]=d9101d72124f5baf
        A: 4 member(s) NOT scoped to theme-3: ...
        C: 1 prelude(s) PACK members onto one line ...
        T: consumed and declared nowhere in this file: --font-serif, --w-op
  RED   theme-4.css    members=149 scoped=145 ...   (A and C)
  RED   theme-5.css    members=148 scoped=144 ...   (A and C)
VERDICT FAIL -- 5 file(s) did not hold the contract.   rc=1
```

This receipt is itself the claim under audit: re-run the three commands in *Instruments, both colours*
and the numbers above must come back. If they do not, the receipt is the thing that is wrong.
