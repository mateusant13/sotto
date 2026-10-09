# Receipt 33 — the locale group separator, censused across the repo

**Lane 25 · 2026-10-07 · repo `H:\sotto\_moved\aireplay` @ `main`**
**Gate:** `_main\_lane25-locale-number-gate.ps1` → **VERDICT PASS**, `EXITCODE=0`
**Console:** `_main\_lane25-gate-console.txt`
**Regression re-run:** `durability-gate.ps1 -SelfTest` → `SELFTEST-VERDICT: PASS`, `EXITCODE=0`
(log: `_main\_lane25-regress-durability.log`)

---

## 1. The measurement that starts this

On this box, `pwsh 7.6.6`, culture `pt-BR`:

```
("{0:N0}" -f 48888)  ->  '48.888'
hex of the output:  0034 0038 002E 0038 0038 0038
                             ^^^^  U+002E, a real PERIOD
```

A period is the **decimal point**. So any gate that prints `48.888 MiB` has published a
number wrong by a factor of 1000, in a form that reads as entirely plausible. This is the
same wrong-published-number class as the reviewer's **F1** (a receipt published `11934`
where the correct figure was `12222`) and as the `"48.888 MiB for 48888 MiB"` the ring-cap
lane reported and, correctly, declined to fix in another lane's files.

## 2. CENSUS — POPULATION and WINDOW

**POPULATION = 18 composite-format placeholders carrying an `N` specifier, on 13 lines, in
6 files.**
**WINDOW = the entire working tree at the moment of the census, every file extension, read
from disk — not a sample.** Matched by `\{[0-9]*(,[0-9]+)?:[0-9]*[Nn][0-9]*\}`, then
independently cross-checked two ways: (a) ripgrep over the repo, (b) the gate's own
independent scanner. **The two agree exactly, 18 before / 13 after.**

Also present and deliberately excluded: **8 sites of `[guid]::NewGuid().ToString('N')`**
(`font-lag-probe.ps1:18`, `font-final-run.ps1:19,49`, `font-specimen-shots.ps1:15`,
`font-shots.ps1:23`, `font-measure.ps1:27`, `review-synthesis.ps1:28`,
`_hb-lock-selftest.ps1:12`). `N` there is the *no-dashes* GUID format, not a number. Listed
so the exclusion is visible rather than silent.

Python, C/C++, JS were swept too and carry **zero** sites of this class: Python's `,` group
separator (`:,0f`) and `%d` are culture-invariant, and no `printf("%',d")` exists here. The
defect class is **entirely a PowerShell `-f` phenomenon** on this tree.

### The 13 code lines, classified

| # | file:line | placeholder | operand printed | class | disposition |
|---|---|---|---|---|---|
| 1 | `_main\durability-gate.ps1:714` | `{0,9:N1}` | **MB** | **DEFECTIVE — memory** | **FIXED** |
| 2 | `_main\durability-gate.ps1:746` | `{6:N1}` | gate duration (s) | **CAN CROSS 1000** | **FIXED** |
| 3 | `_main\font-lag-probe.ps1:30` | `{1,5:N1}` | per-font elapsed (s) | **CAN CROSS 1000** | **FIXED** |
| 4 | `_main\font-lag-probe.ps1:65` | `{0:N0}` | total elapsed (s) | **CAN CROSS 1000** | **FIXED** |
| 5 | `_main\font-shots.ps1:42` | `{4:N1}` | per-shot elapsed (s) | **CAN CROSS 1000** | **FIXED** |
| 6 | `_main\font-crop-diff.ps1:60` | `{2:N3}` | percent, 0–100 | SAFE | untouched |
| 7 | `_main\_lane3-ringcap-gate.ps1:497` | `{2:N2}` | 47.74 **GiB** | SAFE (`<1024` by construction) | other lane |
| 8 | `_main\_lane3-ringcap-gate.ps1:499` | `{1:N2}` | ~24 **GiB** | SAFE (`<1024` by construction) | other lane |
| 9 | `_main\_lane3-ringcap-gate.ps1:502` | `{4:N2}` | 2.04 % | SAFE | other lane |
| 10 | `_main\_lane3-ringcap-gate.ps1:506` | `{1:N2}` | 8.38 % | SAFE | other lane |
| 11 | `_main\_lane3-ringcap-gate.ps1:515` | `{2:N2}` `{3:N2}` | 186.17 s / 763.55 s | SAFE (`<1000`) | other lane |
| 12 | `_main\_lane3-ringcap-gate.ps1:518` | `{2:N2}` `{3:N2}` | 46.54 s / 190.89 s | SAFE (`<1000`) | other lane |
| 13 | `_main\_lane3-ringcap-gate.ps1:524` | `{2:N2}` | **2574.92 MiB** | **DEFECTIVE — memory, LIVE** | **other lane — REPORTED, NOT TOUCHED** |

### The DEFECTIVE one was not hypothetical

`_main\durability-gate.ps1:714` prints the "LARGE UNTRACKED ARTEFACTS (> 5 MB)" table.
Those artefacts exist on this box, right now:

```
3.094,3 MB   _main\_lane24-gate\fresh-store.sqlite
1.050,1 MB   _main\_index-store\index.db
1.044,0 MB   _main\_index-store2\C_partition_video.db
```

(the `,` above is this same pt-BR separator, in a shell one-liner — the point is the
magnitudes: 3094 MB, 1050 MB, 1044 MB.) Rendered by the **old** expression vs the **new**
one, same values:

```
MB=1024     BEFORE [    1.024,0 MB]   AFTER [     1024.0 MB]
MB=48888    BEFORE [   48.888,0 MB]   AFTER [    48888.0 MB]
```

The gate was publishing `1.024,0 MB` for a one-gigabyte file on every run it had large
artefacts to show.

## 3. The form chosen, and why — one line each

- **`durability-gate.ps1:714` (MB) → `$_.MB.ToString('F1', $inv)`, placeholder `{0,9:N1}`→`{0,9}`.**
  `InvariantCulture` + `F` removes the separator entirely rather than swapping it, so the
  number is identical on every host and has exactly one decimal point — and it is the
  precedent already in this repo at `all-gates.ps1:356`.
- **`durability-gate.ps1:746`, `font-lag-probe.ps1:30,65`, `font-shots.ps1:42` (durations) →
  same `.ToString('F1'/'F0', $inv)`.** One form for the whole lane rather than a
  per-site choice, so a later reader sees one convention and not four.

`InvariantCulture` was chosen over a thin space because a space is *also* a guess — it needs
its own reader to be interpreted correctly, whereas no-separator needs none. `F1` prints
`1024.0`; a thin space would print `1 024.0`, which a reader who has lost the thin space
silently becomes `1024.0` and a reader who has not becomes `1.048.00`. The brief asked for
the form that cannot be misread, and that is the one with no separator in it.

## 4. `_lane3_ringcap_probe.cpp` — the stale comment, corrected

Owned by lane 3's neighbourhood but **not by a running lane** (only `_lane16-wake-gate.ps1`
is in flight), and it was explicitly offered to this lane. Two defects in the header:

- it cited **`replay.cpp:57`** as pinning the capture window at 1920x1080. That clamp was
  **removed** — lane 7 lifted it at 12:26 (`replay.cpp:38-42`, `negotiate_capture_window`).
  The header was using a deleted line as the *reason* N=0 4K runs exist. The real reason is
  two-part and both parts are now stated: WGC refuses every capture item on this host
  (receipt-18 §2), and no 4K run was ever taken.
- it carried its own copy of the **superseded formula**, `min(4 GiB, 25% of
  TotalPhysicalMemory), floored` — omitting the `50% of AvailPhysicalMemory` term and the
  named 256 MiB floor. Those are precisely the two arms the gate's ARM E falsifies.

**Asserted comment-only**: the staging script proves all **87 non-comment lines are
byte-identical to HEAD**. Zero behaviour touched.

## 5. Reported, NOT touched — another lane's file

The brief's rule is that a hit in another lane's file is reported with the exact
replacement and left alone. `_lane3-ringcap-gate.ps1` is explicitly "already fixed by the L3
lane; verify, do not rewrite" — and **verification found the L3 lane's fix is incomplete by
exactly one site**:

> `_main\_lane3-ringcap-gate.ps1:524` — `{2:N2} MiB` applied to
> `$l4k.chose_with_hookup_mib`. On this host that value is **2574.92** (from
> `_main\_lane3_ringcap_probe.cpp:113-117`, `min(want, new_cap)` with `want_mib=2574.92` and
> `new_cap=4096`), so the gate prints **`2.574,92 MiB`** — wrong by 1000×, today, on the live
> path, on the line whose whole job is to state what the RAM budget buys.
>
> **Exact replacement**, if L3 applies it:
> `"{0:N2} MiB -> {1:N2} s (CLIPPED) | WITH THE RAM BUDGET = {2:N2} MiB -> {3:N2} s"`
> becomes
> `"{0:N0} MiB -> {1:N2} s (CLIPPED) | WITH THE RAM BUDGET = {2:N0} MiB -> {3:N2} s"`
>
> `{0:N0}`/`{2:N0}` is L3's *own* convention for memory — the header of the same file
> (`:172-174`) already says "Integers, not :N0/:N2. This host's locale renders the GROUP
> separator as `.`". This lane did not apply it.

`_lane3-ringcap-gate.ps1:497,499` carry the same class on **GiB** values (47.74, ~24). Those
are SAFE *today* because a GiB figure is below 1000 on any real machine — but they are
LATENT, and a host with ≥ 1 TiB of RAM would render `1.024,00 GiB`. Same file, same owner,
same fix, also reported rather than applied.

## 6. The gate, and both of its colours

`_main\_lane25-locale-number-gate.ps1`. Four arms:

1. **HOST** — asserts 48888 renders with a period group separator. If it does not, the gate
   **fails loudly** ("cannot go red here") rather than passing vacuously.
2. **RENDER PROOF** — computes the defective and fixed forms of 48888 and asserts the fixed
   form is separator-free. Ties the static rule to what this host actually prints.
3. **CENSUS + VERDICT** — scans the tree, prints every site with its classification, and
   fails on any memory/duration site **in the files this lane owns**. Other lanes' sites are
   printed as `DEFERRED` with the owner named, every run — never absorbed into this lane's
   green, never invisible.
4. **FALSIFY** (`-Falsify`) — copies the owned files, reverts **only this lane's fix**,
   re-runs the same detector, and requires RED.

```
EXITCODE=0
  owned DEFECTIVE sites      : 0
  VERDICT PASS

  FALSIFY ARM
  reverts applied: 5 of 5
    _main\durability-gate.ps1  :721  {0,9:N1}  MEMORY    'MB'
    _main\durability-gate.ps1  :753  {6:N1}    DURATION  's'
    _main\font-lag-probe.ps1   :35   {1,5:N1}  DURATION  's'
    _main\font-shots.ps1       :47   {4:N1}    DURATION  's'
  FALSIFY RED - 4 defective site(s) on the reverted copy.
```

**The first falsify run was a false green and it is worth recording.** The revert table
initially restored only the operand (`$_.MB`), leaving the placeholder as `{0,9}` — which the
detector correctly calls SAFE. The arm went red on 3 duration sites and **never exercised
the one site this whole lane exists for**. The revert is now two steps: give the
placeholder back its `:N1` *and* restore the raw operand. The reverts are keyed on exact
strings and each must match exactly once or the arm reports
`REVERT DID NOT MATCH` and refuses to call itself a gate.

## 7. Existing gate re-run after the fix

`durability-gate.ps1` is the file carrying the headline defect, so it is the one whose
regression matters most, and it has a built-in both-colours self-test:

```
DURABILITY SELF-TEST (synthetic, touches nothing on disk)
  arm CLEAN  (in-flight excused)          : PASS  rows failing = 0
  arm STALE  (a 2-day-old hole must fail): PASS  rows failing = 1  [src/engine/queue.cpp]
  SELFTEST-VERDICT: PASS - both colours proven
EXITCODE=0
```

## 8. What this receipt does NOT claim

- **Green is scoped.** `VERDICT PASS` means *no memory or duration quantity in lane 25's
  three files* is published through a locale-dependent separator. It does **not** mean the
  repository is clean — `_lane3-ringcap-gate.ps1:524` is defective right now (§5) and is
  printed as `DEFERRED` on every run of this gate so that fact cannot rot.
- **The unit classifier is lexical.** It reads the literal unit token immediately after the
  placeholder. It leaks slightly past a `%` sign, so `_lane3-ringcap-gate.ps1:502,506` are
  labelled unit `'of'` — they are percentages, the SAFE verdict is correct, but the label is
  cosmetic noise rather than a precise read. A value-aware classifier would need each
  operand's runtime type, which is not statically available.
- **The tree was moving.** `git status` showed live edits from several lanes at census
  time; mtimes were checked before each file was touched. No flakiness claim is made for any
  arm, including repeatedly-green ones.

---

### Files this lane changed

| path | change |
|---|---|
| `_main\durability-gate.ps1` | `:714` MB, `:746` duration → `InvariantCulture` |
| `_main\font-lag-probe.ps1` | `:30`, `:65` durations → `InvariantCulture` |
| `_main\font-shots.ps1` | `:42` duration → `InvariantCulture` |
| `_main\_lane3_ringcap_probe.cpp` | header comment only (verified: 87 code lines byte-identical) |
| `_main\_lane25-locale-number-gate.ps1` | **new** — the gate |
| `receipts\receipt-33-locale-number-census.md` | **new** — this file |

### Staging note — two of those files already carried another lane's uncommitted work

`durability-gate.ps1` was **30 759 B at HEAD and 45 739 B in the working tree** when this
lane started: ~15 KB that is not mine. `_lane3_ringcap_probe.cpp` likewise, whose diff
carries lane 3's `livepath` block alongside my comment. A plain `git add` on either path
would have committed another lane's work under this lane's name.

So both were staged by **index plumbing**: `_main\_lane25-stage-durability.ps1` and
`_main\_lane25-stage-probe.ps1` rebuild each file as **HEAD + only this lane's edits**,
assert every replacement matched exactly once, assert the durability blob **parses**, assert
the cpp's **non-comment lines are byte-identical to HEAD**, and only then stage that blob.
The working tree was not modified by this step — the other lane's work stays unstaged and
untouched, exactly where it was.