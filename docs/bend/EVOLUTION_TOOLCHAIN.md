# Evolution toolchain — Bend 2 laws & proofs (verified 2026-10-09)

Everything here was executed and verified on this machine. Reproduce it from scratch with the
commands below. Rationale: `EVOLUTION_SPECS.md` §11; queue cards `E11.1`–`E11.4`.

**Reusable by design.** This is the playbook for taking Bend's machine-checked proofs into any
project. If you are starting elsewhere, read §7 (friction log) and §8 (ecosystem) first — they are
the parts that are not obvious.

| § | Contents |
|---|---|
| 1 | Why a dedicated WSL distro (Windows host; musl refuses `--verdict`) |
| 2 | Install Bend + Lean, pinned versions |
| 3 | Working commands, incl. the `--check-only` ≠ proof trap |
| 4 | The negative control — mandatory per law |
| 5 | Verifier limits — what a green verdict does **not** prove |
| 6 | Python / CI invocation, and the infrastructure-vs-proof rule |
| **7** | **Friction log — every blocker, its cause, its fix, how each was verified (F-1 … F-14)** |
| **8** | **Ecosystem — BendHub, `lawcheck`/`mutate`, bend-mathlib, bend-packages, registry risk** |
| 9 | What we will *not* take from Bend |
| 10 | Upstream issue & PR tracker, URL-verified 2026-10-10 |

## 1. Why a dedicated WSL distro

Bend's prover kernel (BendTT) needs a **Lean** executable. `elan` refuses musl systems:

```
$ apk add gcompat && sh elan-init.sh -y --default-toolchain none
elan: musl-based systems are unsupported at the moment
```

So the existing Alpine distro (`bluetest`) cannot run `--verdict` even though the Bend *interpreter*
runs there. A glibc distro is required.

**Distro:** `ubuntu-bend` (Ubuntu 24.04.5 LTS, WSL2, root).

```bash
# .wsl image from the Ubuntu WSL daily-live channel
curl -sL https://cdimages.ubuntu.com/ubuntu-wsl/noble/daily-live/current/noble-wsl-amd64.wsl \
  -o C:/WSL/noble-wsl-amd64.wsl
wsl --install --from-file C:/WSL/noble-wsl-amd64.wsl --location C:/WSL/ubuntubend --name ubuntu-bend
```

> Note: pass `--location` with **forward slashes**; Git Bash eats the backslashes and WSL then fails
> with `ERROR_INVALID_NAME` on `C:WSLubuntubend\ext4.vhdx`.

## 2. Install Bend + Lean

```bash
wsl -d ubuntu-bend -e bash -lc '
  apt-get update -qq && apt-get install -y -qq curl xz-utils
  # Bend (installs to /root/.bend/bin/bend + /root/.bend/bend2)
  curl -fsSL https://bend-lang.com/install.sh | sh
  # Lean 4.34.0 — required by --verdict
  curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -o /tmp/elan-init.sh
  sh /tmp/elan-init.sh -y --default-toolchain leanprover/lean4:v4.34.0
'
export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH   # every invocation needs this
```

| Piece | Version | Verified |
|---|---|---|
| Bend | 2.0.39 (release served by bend-lang.com; 2.0.37 before 2026-10-28, 2.0.36 before 2026-10-17) | `bend version` |
| Lean | 4.34.0, `x86_64-unknown-linux-gnu` | `lean --version` |

`tools/bend_verify.sh` prints BOTH lines in its own `== bend: … ==` / `== lean: … ==`
header. That is not decoration: kernel-comparison releases (#1892, #1864) **widen what
`ALL PROOFS CHECK` means** with the laws unchanged, so a gate log that names only the
compiler cannot tell "the laws still hold" from "the kernel accepts more".

## 3. The working commands

```bash
# Write a law + its proof
cat > /tmp/addzero.bend <<'EOF'
import Base

law add_zero:
  for x: Nat
  {Nat.add(x, 0n) == x : Nat}

def add_zero(x):
  match x:
    case 0n:
      {==}
    case 1n+xp:
      %add_zero(xp) : {1n+Nat.add(xp, 0n) == 1n+_ : Nat}
      {==}

def main() -> Nat:
  Nat.add(7n, 0n)
EOF

bend /tmp/addzero.bend               # check + run  -> prints 7n
bend /tmp/addzero.bend --check-only  # fast internal checker (NOT a proof)
bend /tmp/addzero.bend --verdict     # rechecked by the Lean kernel -> ALL PROOFS CHECK
```

`--check-only` prints `Use --verdict for mathematical validity.` — **our gates use `--verdict`.**

`--verdict` needs `lean` on `$PATH`, or `$BENDTT` pointing at a built kernel.

## 4. Negative control (mandatory per law)

Same shape, false statement:

```bend
law bad_add_zero:
  for x: Nat
  {Nat.add(x, 1n) == x : Nat}
def bad_add_zero(x):
  match x:
    case 0n:      {==}    # <- rejected here
    case 1n+xp:   %bad_add_zero(xp) : {1n+Nat.add(xp, 1n) == 1n+_ : Nat}
                  {==}
```

```
$ bend bad2.bend --verdict
SOME PROOFS FAIL
Error:
- expected : 1n
- observed : 0n
Location: bad_add_zero
```

A law whose mutated form does **not** fail tells us nothing about the checker — ship both files.

## 5. Verifier limits to respect

From the upstream tracker (see `EVOLUTION_SPECS.md` §13):

- **#1416 (open)** — v2.0.36 `--verdict` can certify a *different* program than it checked/ran
  (let-convoy value leak; fix merged on main `f1a69ec`, **not released**). Trigger: lambdas captured
  inside `match` arms. → avoid that shape in our Bend port, and keep running the program.
- **#1417 (open)** — one term accepted at two different types.
- **#1418 (open)** — claim inventory + one claim-text gap in the kernel's statement.
- **#1423 / #1424** — backends can diverge (F32 NaN); parser and kernel translation are unproven.
- **#1408 (open)** — separate proof failures from infrastructure failures in any gate that runs bend.

## 6. Invocation from Python/CI

```python
subprocess.run(
    ["wsl", "-d", "ubuntu-bend", "-e", "bash", "-lc",
     "export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH; cd /mnt/c/path/to/laws && bend file.bend --verdict"],
    timeout=..., capture_output=True, text=True)
```

`/mnt/c/...` is how WSL sees the Windows checkout. A missing distro, a timeout, or a nonzero exit
with no verdict line must be classified as **infrastructure**, never as a proof result.

---

## 7. Friction log — every blocker hit while proving these laws

This is the part that transfers to another project. Each entry is *cause → fix → how it was
verified*; "verified" always means a command that was actually run, not a reasoning chain.
Add a row whenever a new blocker appears.

### F-1 · Bend does not exist on this Windows host

`Get-Command bend` → nil; `Get-ChildItem -Path C:\ -Filter bend.exe -Recurse -Depth 5` → nil;
`$env:LOCALAPPDATA\bend\bin`, `$env:USERPROFILE\.bend\bin`, `C:\bend\bin`, `$env:USERPROFILE\.cargo\bin`,
`$env:USERPROFILE\scoop\shims` all empty. **This was not a PATH gap — there is no `bend.exe` on `C:`.**
No amount of PATH editing fixes it; Bend ships no Windows binaries. ⇒ §1.

*Consequence for any project:* on Windows, Bend law/proof work is WSL-only from the first command.
Budget for it before promising a gate, not after.

### F-2 · Alpine distro can run the interpreter but not `--verdict`

`bluetest` (musl) runs `bend file.bend` fine and dies on the prover: `sh elan-init.sh -y
--default-toolchain none` → `elan: musl-based systems are unsupported at the moment`. `--verdict`
needs a **glibc** host for Lean 4.34.0. ⇒ distro `ubuntu-bend` (§1).

*Trap:* the interpreter working is the misleading signal. Only `--verdict` needs Lean, so a
smoke test with plain `bend file.bend` proves nothing about the prover path.

### F-3 · `--location C:\WSL\…` under Git Bash → `ERROR_INVALID_NAME`

WSL receives `C:WSLubuntubend\ext4.vhdx`. The backslashes were eaten before the argument reached
`wsl.exe`. **Fix: forward slashes in `--location` and every `wsl --install` path.** Verified by
re-running with `C:/WSL/noble-wsl-amd64.wsl` and `C:/WSL/ubuntubend` — install completed.

### F-4 · every invocation needs an explicit PATH

`elan` and `bend` land in `~/.elan/bin` and `/root/.bend/bin`, which a plain
`wsl -d ubuntu-bend -e command` does not put on PATH. Verified: `wsl -d ubuntu-bend -e bend version`
fails, while `wsl -d ubuntu-bend -e bash -lc 'export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH;
bend version'` succeeds. **Fix: the one canonical incantation in §6, used everywhere —
no exceptions, no "it worked once".**

### F-5 · `--check-only` is NOT a proof (and reads like one)

`bend PROOF.bend --check-only` type-checks and prints *"Use --verdict for mathematical validity."*
A gate built on `--check-only` is green on a file whose proofs are garbage. `--verdict` re-checks
with the Lean kernel and prints `ALL PROOFS CHECK`. **Verified by side-by-side run on the same
file: identical `--check-only` output, different verdict.** Our gates use `--verdict` only.

### F-6 · ★ THE big one: a green verdict can be vacuous

**Measured, not theorized.** `bend_core/LAWS.bend` (133 lines) shipped a `def` body that states only
**one of the four terms** its `law Row.span_end_within_file` requires. `bend file.bend --verdict`
was green — because a proof of a weaker statement is a proof.

It was caught by **reading the proof terms against the law's quantifiers, one by one** — not by a
test. No automated check catches this yet (see F-14). The only reliable pattern, and the one to
build: **produce the artifact you intend to ship AND a deliberately tampered artifact, and assert
the verdict differs.** A green verdict on both means the gate is not verifying anything.

*Trap for the next project:* "ALL PROOFS CHECK" certifies that *the terms in the file* check. It
certifies nothing about whether those terms are the terms you meant. **A law without a negative
control and without a proof-state tampering check is decoration.** ⇒ §4 and `E11.3`.

#### F-6b · same class, second shape: a Boolean helper in the model can go vacuous

**Measured 2026-10-28 on bend 2.0.39, in THIS repo.** `lists_stale` (the disclosure union of the
trust-block merge) was hardwired to the constant `True{}` in `bend_core/LAWS.bend` — the pre-fix
DROP inverted, a model that discloses everything unconditionally. **All eleven laws still printed
`ALL PROOFS CHECK`, rc=0.** The reason is structural and not specific to us: a `Bool`-valued claim
of the form `f(...) == True{}` is satisfied by the constant `True{}`, and the proof's
impossible-premise arm (`Empty.elim`, which returns any type) still typechecks. Upstream issue
**#1904** is the same mechanism in their own demo (an edit that lets the player reach the flag,
proofs untouched, still green).

Two things fixed it, and both are cheap:

1. **Specify the model extensionally, not just use it** — `law lists_stale_is_or` proves
   `lists_stale(p, e) == Bool.or(p, e)`, which the constant `True{}` violates at (False, False) and
   the shipped pre-fix projection violates at (False, True). Both mutations were watched failing
   before the law was added; `tests/evolution/test_e113_law_invariants.py` now carries the
   projection as a permanent control.
2. **Know which mutations this does NOT need to catch.** The same probe on
   `Row.clamp_end` (mutated to return `0n`) went RED immediately — a `Nat`-valued model def is
   pinned by the general law, because the proof term no longer types against the widened goal.
   The vacuity hole is specific to **2-element codomains** (`Bool`), not to "model code".

⇒ rule for this repo: a `Bool`-returning model function needs an **extensional** law
(`f(...) == Bool.or(...)`), because an implication-shaped law cannot see it go constant.

### F-7 · `--verdict` may certify a program other than the one it ran (#1416)

Let-convoy value leak; trigger shape is *lambdas captured inside `match` arms*. Fixed on main, **not
in any release** — including our pinned 2.0.36. Mitigation recorded in `EVOLUTION_SPECS.md` §11.5:
pin the version, avoid that shape in the port, and never let a green verdict replace *running* the
program. This is why the E11 plan keeps Python as the official backend.

### F-8 · upstream lemma names do not match ours

bend-mathlib spells the order predicate `le(a, b)` (a `Prop`); `LAWS.bend` uses `Nat.is_le(a, b)` (a
`Bool`). Not a drop-in import — it needs a bridge law, or a hand-proved restatement. Also
`is_le_refl`, `is_le_0_l`, `min_min_r` have **no upstream equivalent under those names**, so those
helpers stay hand-proved even after adopting `le_refl` / `min_le_left` / `min_le_right`.

*Verified:* the bend-mathlib lemma index in the fetched README lists `le_refl` (`:442`),
`min_le_left` (`:459`), `min_le_right` (`:464`) — all inside its `## nat` section, which bendlib
reports as `--verdict`-clean.

### F-9 · bend-mathlib is not on GitHub — it is a BendHub package

Earlier notes in this session said "bend-mathlib@0.7.2.0" as if it were a repo. **Corrected:** there
is no `bend-mathlib` GitHub repository (`HigherOrderCO/bend-mathlib` → 404). It is a BendHub registry
package whose listed "repo" is `bendlib/bendlib`. Practical consequence: **you cannot read its source
locally** without pulling it through the registry, and pulling it is a network operation. ⇒ §8.

### F-10 · lawcheck has no Windows binary, and its exit code 2 is not a law result

`tools/lawcheck/install.sh:17-21` hard-dies on any OS that is not Linux/Darwin, with the fallback
"run it from source: `bun tools/lawcheck/cli.ts`". A Windows-only CI lane therefore cannot run
lawcheck at all. Its exit codes: **0** = no counterexample found, **1** = counterexample found (a
*law* result — rejection is correct), **2** = usage error / file does not load / does not type-check /
tool error (an *infrastructure* result). A gate that treats every nonzero exit as "law rejected"
silently converts a broken tool into a failing law — exactly the conflation #1408 asks us to avoid.

lawcheck is **tested only on bend 2.0.36**, which is our pin. Its first run downloads the matching
`bend.ts` from the network, so an air-gapped lane needs that documented.

### F-11 · `bend gen-types > Kernel.bend` was wrong

An earlier session note recorded the lawcheck setup as `bend gen-types > Kernel.bend` then
`lawcheck LAWS.bend`. **Retracted.** The real invocation is `lawcheck LAWS.bend` (or
`bun tools/lawcheck/cli.ts LAWS.bend`); it loads laws through `@bendlib/reader`, the official
`bend.ts` parser, and there is no `gen-types` step anywhere in its README, CLI or sources.

### F-12 · `bend run-cu` does not exist

No CUDA verb in Bend 2.0.36 (`no such file: run-cu`), despite the RTX 5080. Documented so nobody
re-litigates it: **Bend is a parallel interaction-combinator reducer, not a numeric compute engine.**
The GPU path this project mandates is ONNX with `CUDAExecutionProvider` for embeddings and the
cross-encoder (`AGENTS.md` §System specs). Bend's GPU ambitions and ours do not overlap.

### F-13 · doc drift found while writing this

- `LAWS.bend:11-14` promises *"`tests/evolution/test_law_mirror.py` checks the same properties
  against the real builder"* — that file does not exist. Either write it (P1) or delete the promise
  before ship. A law file that cites a nonexistent test is a half-finished feature.
- `docs/EVOLUTION_TOOLCHAIN.md:263` (pre-rewrite line numbering) carried the same stale claim.
- The upstream repo is no longer `HigherOrderCO/Bend`: that path **redirects** to
  **`bendlang/bend`** (23.5k stars, Apache-2.0, branch `main`). Cite the canonical path.
- Issue *numbers* in `EVOLUTION_SPECS.md` §13 were verified against the tracker on 2026-10-10; all
  resolve, but several have since **closed** (#1423/#1424, #1431/#1436) and some titles have drifted.
  Treat numbers as stable and titles as snapshot-only.

### F-14 · ★ I almost shipped a third false citation, minutes after documenting the first two

Worth recording because it is the failure mode of *documentation about a codebase*, and because it
happened while writing this very section.

A session note asserted that `tests/test_actionpack_proof_states.py` exists and contains a
"3-way proof-state harness pattern". It does not exist — **in this worktree, or in the main checkout
on `main`.** It was a false premise carried forward from an earlier condensed summary. Writing F-6,
I copied that citation into the new doc as evidence that the vacuous-proof trap was caught by a test.

It was caught by one check: `scripts/run_relevant_tests.py tests/test_actionpack_proof_states.py` →
`ERROR: file or directory not found`. No reasoning chain would have found it; the claim was
*plausible* and self-consistent.

**Rules that follow from this, for any doc that names code:**

1. **A doc citation is a claim about the filesystem. Verify it with `ls`/`glob`, never with "this
   was established earlier."** Both citations (§7 F-6 and `LAWS.bend`'s header) were corrected in
   the same session before commit.
2. **The defect classes in F-6 and F-13 are the same defect class.** A false promise about a test is
   indistinguishable, to a reader, from a false proof. Both are "a source file asserts something the
   repo does not contain."
3. **The methodology survives even though the artifact did not.** The tampering protocol (build the
   shipped artifact and a tampered one; assert the verdict differs) is still the right remedy for
   F-6. What was false was the claim that *it already ran here.* → tracked as `E11.3`.

**A condensed session summary is a hypothesis generator, not evidence.** Every factual claim in one
— file existence, line ranges, test identities, upstream issue states — must be re-read against the
working tree before it is written down as fact. This section exists because I violated that rule
while writing the section that says to obey it.

---

## 8. Ecosystem — BendHub, lawcheck, mathlib, bend-packages

Snapshot taken 2026-10-09/10 from the live registry and the fetchable READMEs. Treat counts as a
dated snapshot, never as a fact.

### 8.1 The registry (BendHub) and how imports resolve

Registry: <https://hub.bend-lang.com>. Two import forms, and the difference matters:

```python
import bend-mathlib@0.7.2.0/nat.bend as MNat          # by name+version, cached under ~/.bend/lib/names
import 0x53dde92df75268075f1bc6c33ecbb079/bend_ml.bend   # by content hash — always the same code
```

**The registry is network-resolving.** For anything that must be auditable or reproducible — a CI
gate above all — **pin by hash**, not by name. A name+version pin is only as good as the registry's
willingness to keep serving that name; a hash pin *is* the content. Publishing needs
`bend <file>.bend --publish <name>@<version>` and `bend login` (public and permanent).

Curated third-party overview: <https://github.com/lilalittle/bend-packages> — snapshot 2026-10-05
reported **490 packages: 94 named, 243 hash-only**. Unusually useful because it tracks which packages
have *no public source*.

### 8.2 lawcheck / lawcheck mutate — the machine-checked mutation layer

Lives in <https://github.com/bendlib/bendlib> (`tools/lawcheck`), **not** published as a BendHub
package; install with the curl installer (§8.3) or run from source with `bun tools/lawcheck/cli.ts`.

What it does: instantiates every `law` with generated values (exhaustive small-scope to a depth, then
seeded random), runs each instance through `bend --check-only`, and **shrinks counterexamples**.
It never proves anything — a ✓ only means no counterexample turned up.

Operationally important flags:

| Flag | Effect |
|---|---|
| `--law NAME` | check one law |
| `--json` | `schema: 1` + the exact `seed`/`size`/`maxInstances`/`maxNat` used |
| `--impl other.bend` | **swap the file's local import for another implementation** — run the laws against a different one |
| `--size N` / `--max-nat N` / `--seed S` | search depth / random `Nat` bound / seed (reproducible, default 1) |
| `--jobs N` | parallel `bend` processes |
| `--native` | also evaluate with a compiled program, report disagreement with the checker |
| `--strict --allow-skip a,b,c` | a skipped law (`~`) fails the gate unless allow-listed |

`--strict --allow-skip` is how the **mathlib's own gate** is run, and the allow-list is honest about
the tool's current limits: it cannot yet decide a handful of laws.

Why `--impl` matters to us: it is precisely the mechanism that binds a law to an implementation.
Point it at `bend_core/model.py`'s equivalent, and the law is checked against the real thing rather
than against a self-consistent copy. That is the shape of P1's `test_law_mirror.py`.

**`lawcheck mutate LAWS.bend`** classifies every small mutant of the target's defs:

- **killed** — some law finds a counterexample on it (the laws pin that change);
- **survived** — every law that passed on the unmutated code still passes (**the laws do not pin it**);
- **unknown** — a law is no longer evaluated on the mutant (skipped/errored), so neither killed nor survivor;
- **invalid** — the mutant does not type-check; discarded, never counted as a kill.

A survivor may also be a genuinely equivalent mutant, so it needs a human read. In `--impl` mode the
proof defs are stripped before each run, so behaviour change is classified by *running the laws*,
not by breaking a proof.

**This is the missing half of F-6.** The tampering protocol catches "my proof no-ops"; `mutate`
answers the harder question *"which of my defs does this law actually pin?"* Our P0 fix is exactly
the kind of change `mutate` would have flagged as an unpinned one had a disclosure law existed.

### 8.3 Install (Linux/macOS only)

```sh
curl -fsSL https://raw.githubusercontent.com/bendlib/bendlib/main/tools/lawcheck/install.sh | sh
# LAWCHECK_VERSION=0.3.0 pins a release; LAWCHECK_DIR=/usr/local/bin relocates it (default ~/.local/bin)
```

The installer verifies the asset against the release's `SHA256SUMS` before moving it into place, and
warns when `bend` is absent. On macOS clear the quarantine attribute first. On Windows it exits with
`no lawcheck binary for …` — the gate needs Linux (the `ubuntu-bend` distro, a container, or a CI
Linux runner).

### 8.4 bend-mathlib, and the two other useful findings

- **bend-mathlib@0.7.2.0** (`bendlib/bendlib`) — the report is **231 machine-checked lemmas** (Nat,
  Bool, List, equality, algebra, order, sorting), zero `@unsafe`. Adopting it removes the need to
  hand-prove `le_refl`, `min_le_left`, `min_le_right` — see the F-8 bridge caveat. A secondhand count
  of 445 lemmas appeared in another snapshot; **the number is unresolved, so this doc does not
  assert one**.
- **lawcheck** (§8.2) — the reason we can do machine-checked mutation testing at all.
- **`bend-kit-*`** (`paymog/bend-kit`) — the de-facto standard library, most-depended-on packages on
  the hub (`bend-kit-bytes` has 53 dependents). Not our domain, but useful when sizing the ecosystem.

### 8.5 Registry risk — read before depending on anything

From the curated registry snapshot and verified against the hub:

- **Publisher concentration.** One publisher (`paymog`) accounts for roughly **half of all named
  packages** (all 39 `bend-kit-*` via two monorepos). High velocity, genuine bus-factor risk.
- **Sourceless packages.** Many of the most interesting ones — `bend-tensors`, `bolt` (linter +
  LSP), `ezx` (the package manager), `bend-ml` — have **no public repository**. You cannot audit
  them, contribute to them, or fully rely on them. For a correctness-first project this is
  disqualifying for anything in a gate.
- **No lockfile story**, no audit/vulnerability tooling, no test runner, no formatter. The publish
  flow (`ezx`) is tribal knowledge with no public docs.
- **No editor support** — `bolt` ships an LSP server with no client to talk to, and there is no
  tree-sitter grammar. Writing Bend by hand on this repo is plain-text editing.

Verdict for our use: **`--verdict`, negative controls, and `lawcheck` are the adoptable core.** The
package ecosystem is not yet something a gate should depend on. Vendored law files, pinned by hash,
are the reproducible choice.

---

## 9. What we will NOT take from Bend

- The ML/tensor/autodiff battery on BendHub (`bend-ml-tensor`, `bend-ml-autograd`, `bend-blas-lapack`)
  is tempting on paper and irrelevant here: this project's numeric path is ONNX + CUDA
  (`CUDAExecutionProvider`), it already works, and Bend's HVM is not a numeric engine (F-12).
- `bend-schema-lib`, `qasim-bend-kit` — sourceless, and schema validation is not our invariant
  surface.
- `bend-collections-laws`, `wordlib`, `bend-lawful-stdlib` — wrong domain for codeintel spans.
- `bend run-cu` / GPU anything — F-12.

---

## 10. Upstream issue & PR tracker (verified 2026-10-10)

Every row was resolved against the canonical repo <https://github.com/bendlang/bend>. Note that
`HigherOrderCO/Bend` redirects there. Several have **closed** since `EVOLUTION_SPECS.md` §13 was
written; the numbers are stable, the titles are a snapshot.

| # | State | Kind | Why it matters here |
|---|---|---|---|
| [#1408](https://github.com/bendlang/bend/pull/1408) | open | PR | Separate **proof failures** from **infrastructure failures** — a crashed runner must never read as a proof rejection. Directly shapes our CI gate. |
| [#1416](https://github.com/bendlang/bend/issues/1416) | open | issue | v2.0.36 `--verdict` can certify a *different* program than it checked/ran (let-convoy; also nested shapes). Fix merged as [#1368](https://github.com/bendlang/bend/pull/1368) (`f1a69ec`), **unreleased**. Pin the version, avoid lambdas captured in `match` arms, keep running the program. |
| [#1417](https://github.com/bendlang/bend/issues/1417) | open | issue | One term accepted at two types, every gate green — presentation-dependent double typing (from the #1190 shared-cell merge). |
| [#1418](https://github.com/bendlang/bend/issues/1418) | open | issue | What BendTT *precisely* proves: claim inventory, the Sigma-over-`<>` claim-text gap. Say what is proven, not "Bend proved it". |
| [#1421](https://github.com/bendlang/bend/pull/1421) | closed | PR | A perf cell is timed by `tm`; under 2 s grade the **median of three**; `--pin` pins the median of five; discard the first run after a build. Adopted as §11.7. |
| [#1423](https://github.com/bendlang/bend/issues/1423) | closed | issue | README Limitations: note that backends can diverge. |
| [#1424](https://github.com/bendlang/bend/pull/1424) | closed | PR | Backend divergence and the **unproven** parser/kernel translation. `--verdict` checks translated terms. |
| [#1431](https://github.com/bendlang/bend/pull/1431) | closed | PR | `Array.q4mv` affine 4-bit matvec (3.2-3.6x CPU, **bit-identical**). Evidence that upstream treats bit-identity across backends as the bar. |
| [#1436](https://github.com/bendlang/bend/pull/1436) | closed | PR | `Array.q4mv` sums in a fixed tree order so SIMD lanes keep the body's bits — stacked on #1431. |

**Net position:** a green Bend verdict is strong evidence, not a substitute for tests. Pin Bend
2.0.36 + Lean 4.34.0, ship a negative control per law, run the proof-state tampering check, and keep
Python as the official backend unless Bend wins on equivalence *and* measured performance.
