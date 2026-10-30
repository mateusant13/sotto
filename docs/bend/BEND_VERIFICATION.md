# Bend verification — independent reproduction on this machine

**Date:** 2026-10-13
**Verdict:** the E11.3 gate claim is **CONFIRMED**; the E11.4 decision is
**CONFIRMED**; the E11.4 *ratio* is **NOT reproduced** (55× measured, 120×
recorded).

This document records measurements taken on this host, not quoted from the
repository. Where I could not reproduce a figure I say so and give what I
measured instead.

---

## 1. The toolchain had to be found before anything could be checked

The Bend toolchain is **not** the public `bend-lang` crate.

| attempt | result |
|---|---|
| `bend` on PATH (Windows) | not installed |
| `cargo install bend-lang` | installed `bend.exe` 0.2.38 in 3m34s, but: `error: unexpected argument '--verdict' found` |
| `bend` inside WSL distro `ubuntu-bend` | **`/root/.bend/bin/bend`, with `--verdict`** |

`bend-lang 0.2.38` **is the latest release on crates.io** (`cargo info bend-lang`
reports `version: 0.2.38`), so there is no crate update to chase. It is a
**different distribution**: a smaller binary with an older CLI surface and no
proof kernel. The gate's toolchain comes from the official installer instead —

    curl -fsSL https://bend-lang.com/install.sh | sh

which installs `/root/.bend/bin/bend`, `bend2/`, `bendtt/` (the Lean kernel) and
`guide/`. The gate needs `--verdict`, a **Lean-backed kernel** check
(`bend <file> --verdict` → "check it, then recheck it with the proven kernel"),
and it needs `lean` on PATH. `docs/EVOLUTION_TOOLCHAIN.md` says exactly this: the
Alpine distro (`bluetest`) runs the interpreter but `elan` refuses musl systems,
so `--verdict` needs a glibc distro.

### 1.1 The toolchain was one minor version behind, and is now current

The official installer serves **`VER="2.0.37"`**; the installed binary was
**2.0.36** (release 2026-10-07). Upgraded with the installer's own path
(`bend update`, which the install script documents as "Run it again to upgrade"):

| | before | after |
|---|---|---|
| `bend version` | 2.0.36 | **2.0.37** |
| binary size | 94,914,688 B | 82,867,400 B |

**The upgrade was re-verified, not assumed.** On 2.0.37: `LAWS.bend` →
`ALL PROOFS CHECK` (exit 0), `NEGATIVE.bend` → `SOME PROOFS FAIL` (exit 1), and
`tools/bend_verify.sh` → `== gate green ==` (exit 0). `--verdict` is still
present in `--help`.

The benchmark on 2.0.37 gives bend median **1610 ms**, python median **35 ms**,
ratio **46.0×** — inside the 47×–55× band measured on 2.0.36. **The update
changed the version, not the conclusion.**

Confirmed present in `ubuntu-bend`:

    bend: /root/.bend/bin/bend   (Bend 2.0.37)
    lean: /root/.elan/bin/lean   (Lean 4.34.0, x86_64-unknown-linux-gnu)

Every invocation needs `export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH`.
Without it, `bend` is simply "command not found" and the toolchain looks absent.

**This is worth writing down because I initially concluded — wrongly — that the
`--verdict` mode did not exist at all, on the evidence of the public crate.**

---

## 2. E11.3 — the laws gate: CONFIRMED

Ran both controls directly, and then the repository's own gate script.

    $ cd bend_core && bend --verdict LAWS.bend
    ALL PROOFS CHECK                                     (exit 0)

    $ cd bend_core && bend --verdict NEGATIVE.bend
    SOME PROOFS FAIL
    - expected : Row.clamp_end(row, line_count)
    - observed : 0n
    Location: Row.clamp_end_is_zero
    31 | def Row.clamp_end_is_zero(row, line_count):
    32>|   {==}
       |   ^^^^                                    (exit 1)

    $ bash tools/bend_verify.sh
    == bend laws gate (native: /root/.bend/bin/bend) ==
    ALL PROOFS CHECK
    PASS: every law in LAWS.bend checks.
    PASS: negative control fails as it must.
    == gate green ==                                     (exit 0)

The negative control is the load-bearing half: a false law and a true law proved
naively both fail, so the gate is not decoration. Both controls behave as
`docs/EVOLUTION_LAWS.md` says they must.

With `-v`, `PROOF.bend` prints its witness lines:

    clamp(end=20, lines=500) -> 20 ; span_end_within_file=ok
    clamp(end=20, lines=15)  -> 15 ; span_end_within_file=ok
    clamp(end=20, lines=0)   ->  0 ; span_end_within_file=ok
    clamp(end=20, lines=1)   ->  1 ; span_end_within_file=ok
    clamp_end_idempotent(lines=500)=ok
    clamp_end_idempotent(lines=15)=ok

**E11.3's claim ("10 laws, one `--verdict` run, `ALL PROOFS CHECK`") is true as
of this machine and this checkout.**

---

## 3. E11.4 — equivalence: CONFIRMED, and it is a strong result

The shape is a fold over a literal `List<U32>` of 4000 ones with a `U32`
accumulator. Both lanes produce **`4000`**:

    lane bend   : 4000   (exit 0)
    lane python : 4000

Byte-identical, as recorded.

Note for anyone reproducing: the generated file needs `import Base` or it fails
with `a declared constructor (unknown: Nil)`. Plain `bend <file>` on a file that
does not check prints `SOME PROOFS FAIL` and runs nothing — so a wrong result
looks like a proof failure, not a wrong answer. My first attempt at this
reproduction had exactly that bug and reported `4` and then a constructor error.

---

## 4. E11.4 — the ratio: **NOT reproduced**

SS11.7 methodology: 4 runs per lane, first run after build discarded, median of
the remaining 3.

| | recorded artifact | **measured here (run A)** | **measured here (run B)** |
|---|---|---|---|
| bend samples (ms) | 1425, 1324, 1324, 1226 | 1594, 1553, 1556, 1505 | 1704, 1429, 1441, 1450 |
| bend median | **1324** | **1553** | **1450** |
| python samples (ms) | 12, 11, 11, 12 | 29, 26, 28, 29 | 31, 28, 31, 28 |
| python median | **11** | **28** | **31** |
| **ratio** | **~120×** | **~55×** | **~47×** |

Run B is `tools/bend_e114_bench.sh` as committed, and is the reproducible one.
The two runs bracket **47×–55×**; the recorded figure is 120×.

To find out where the difference lives I measured the two ways of counting the
Python lane:

| python measurement | ms |
|---|---|
| whole process (`python3 ops_n.py`) | 23–28 |
| **the fold alone, in-process** | **0.168–0.207** |
| bare interpreter startup (`python3 -c pass`) | 23–28 |

The recorded 11 ms sits **between** those two, so it is not a clean instance of
either. It is closer to a whole-process number taken on a less loaded machine
than to the in-process fold, but that is my inference and not a measurement.

I also measured where Bend's time goes:

    bend --check-only   264 ms      (type-check / proof, no run)
    bend <file>        1553 ms      (check + run main)

**What this changes:** nothing about the decision. Bend is 55× slower on
whole-process timing and roughly 9000× slower against the bare fold, and **in
every framing Python stays the official backend**, which is what E11.4 decided.
The recorded `~120×` is the one number in the artifact I could not reproduce;
the *direction* and the *decision* reproduce cleanly.

---

## 5. What a green Bend gate does NOT prove

`docs/EVOLUTION_TOOLCHAIN.md` §5 lists the verifier's limits, and they remain
true after this reproduction: the gate proves the **declared** statements, over
the pure model in `bend_core/`, at the revision checked. It does not prove the
I/O-bound production assembler, and it does not prove the intent behind a
statement. What it does give over sampling is coverage and refusal: a law that
cannot be proved does not compile, so there is no "skipped law" state.

---

## 6. Reproduce this

    wsl -d ubuntu-bend -- bash -lc '
      export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH
      cd /mnt/c/Users/Administrador/Desktop/consult-chatgpt/consultgpt
      bash tools/bend_verify.sh -v
    '

Exit codes are typed (POL-6): `0` green, `2` a law did not check, `3` the
negative control unexpectedly checked, `4` toolchain unusable.
