# Bend 2 — laws and proofs, and how to implement them correctly

> **What this is.** A standalone reference for using Bend 2 as a *proof harness*, extracted
> from a working installation in this repository (`bend_core/LAWS.bend`,
> `bend_core/PROOF.bend`, `tools/bend_verify.sh`). It is written so that another project can
> copy this file, install the toolchain, and get to a green proof gate without repeating the
> mistakes this repository paid for. Every command and number below was measured on this host
> on **2026-10-28** unless it is explicitly labelled as a claim.
>
> **What this is not.** A Bend language tutorial for writing programs. Bend is a
> massively-parallel HVM language; this document uses exactly one of its modes — the
> **theorem mode** where a `law` is checked by the Lean kernel through BendTT.

---

## 0. The one-paragraph version

Bend 2 can carry `law` declarations. A `law` is a statement over types; it is discharged by a
`def` of the same name (through an import alias) that inhabits it. `bend <file> --verdict`
translates the file to Lean 4 and calls the kernel: green means **every law checked for every
input in its domain**, not "these tests passed". That is the whole value: a test samples, a
proof quantifies. The whole risk is the mirror image of that value — a proof certifies *the
statement you wrote over the model you wrote*, and it will happily certify a statement that is
true, vacuous, or unreachable by production. Sections 8–11 are about that risk; they are not
optional reading.

---

## 1. Toolchain, verified

| Component | This host, measured 2026-10-28 | Notes |
|---|---|---|
| `bend` | **2.0.39** (`bend version`, **not** `--version`) | bumped often; pin the exact string in CI |
| `lean` | **4.34.0**, `x86_64-unknown-linux-gnu` | `--verdict` needs Lean on `PATH` |
| WSL distro | **`ubuntu-bend`** | Alpine cannot run `--verdict` (glibc) |
| Windows entry point | `H:\env\tools\bend.cmd` → `wsl.exe -d ubuntu-bend --cd "%CD%" -- env BEND_NO_TELEMETRY=1 /usr/local/bin/bend %*` | makes `%CD%` the WSL cwd, so relative paths work |
| Gate wall time | **5.47 s** end-to-end for 12 laws + 2 negative controls + 4 structural probes | cheap enough to gate a PR |

Install inside the distro (the shape that worked here):

```bash
wsl -d ubuntu-bend                       # Debian/Ubuntu
curl -fsSL https://sh.rustup.rs | sh -s -- -y
# bend ships prebuilt; if you build from source you need Rust + a Lean toolchain
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y
# verify the only two things the gate cares about:
bend version    # -> bend 2.0.39
lean --version  # -> Lean (version 4.34.0, ...)
```

Do not trust a green without printing both identities. Kernel acceptance widens between Lean
patch releases, and a BendTT translation limit is reported with *the same words* as a refuted
law — see §11.

---

## 2. The four kinds of artifact

| File | Holds | Rule |
|---|---|---|
| `LAWS.bend` | `law` **declarations** + the model (`type`, `def`) the statements mention | contains **no proofs**; `bend LAWS.bend` must report `N TODOs found` |
| `PROOF.bend` | `import LAWS.bend as Laws` + one `def Laws.<law name>` per law + refutation helpers + witnesses | the gate; `bend PROOF.bend --verdict` must print `ALL PROOFS CHECK` |
| `NEGATIVE*.bend` | a **false** claim that MUST fail | one false claim per file |
| `tools/bend_verify.sh` | the six structural checks around the kernel | must be able to go red |

The split is not cosmetic. It gives **review separation**: a diff that changes a *claim* is a
different diff from one that changes *how that claim is discharged*, so neither can ride in
unreviewed behind the other. It also makes "unproven" visible: the claim file alone is a list
of open TODOs.

---

## 3. Language surface you actually need

Only this much Bend is needed to run a proof harness. Everything below is from the working
files in `bend_core/`.

### 3.1 Data types

```bend
import Base

type Row is Data:
  Row{path: String, start: Nat, end: Nat}
```

`Data` (not `type ... is Type`) is what makes a constructor usable as a value in a law's
domain. `Nat` literals are `0n`, `1n+ap` in patterns (`n` suffix = unboxed natural).

### 3.2 Definitions, with the two constraints that bite

```bend
def Row.clamp_end(row: Row, +line_count: Nat) -> Nat:
  match row:
    case Row{path, start, end}:
      Nat.min(end, line_count)
```

* **`+line_count`** marks an erased/`+` parameter. A def that *fills a law* may not carry
  `+` arithmetic in its own body beyond what the law's shape allows — in practice, model defs
  are kept to a single `match` + one library call.
* **A def with a proposition return type may not carry a typed parameter list**; a
  law-filling def may not use a value twice. That is why a 3-part conjunction is written as
  **three laws**, not one.

### 3.3 Law syntax

```bend
law Row.span_end_within_file:
  for row: Row
  for line_count: Nat
  {Nat.is_le(Row.clamp_end(row, line_count), line_count) == True{} : Bool}
```

* `for <name>: <Type>` binds a universally-quantified variable.
* `for h: {<prop> : Bool}` binds a **hypothesis** (implication).
* The body is `{<proposition> : <Type>}`. `{a == b : Nat}` is an equality goal; `{p == True{} : Bool}` is a proof-irrelevant boolean goal.
* Law names may be dotted (`Row.span_end_within_file`, `Nat.le_trans`).

### 3.4 Proof syntax

```bend
import Base
import LAWS.bend as Laws

def Laws.Nat.is_le_refl(a):
  match a:
    case 0n:
      {==}
    case 1n+p:
      Laws.Nat.is_le_refl(p)
```

* **The def must be named `<alias>.<law name>`** where `<alias>` is the import alias
  (`import LAWS.bend as Laws` ⇒ `def Laws.Row.span_end_within_file`). Measured: this works for
  dotted law names, and Bend **refuses** a `PROOF.bend` that sits beside a `LAWS.bend` it does
  not import — so the pairing cannot silently come apart.
* `{==}` closes a goal that is definitionally equal after the match specialised it.
* Recursion on the structural argument *is* the induction hypothesis.
* A failing proof reports `Location: Laws.<law name>` — the **def** name, alias included.
  Assert on that form in any probe.

### 3.5 Refutation (impossible hypotheses)

You cannot close a `False{}` hypothesis with `{==}` or an empty `match` ("expected: a
datatype"). The recipe, as shipped:

```bend
def Bool.disc(b: Bool) -> Type:
  match b:
    case True{}:  Empty
    case False{}: Unit

def Bool.absurd_false_true(e: {False{} == True{} : Bool}) -> Empty:
  %e : {Bool.disc(_) : Type}
  Unit{}

def Empty.elim(-A: Type, e: Empty) -> A:
  match e
```

`Empty.elim(goal_type, absurd_false_true(h))` is how a branch whose hypothesis is impossible
is discharged. Copy these three defs verbatim into every new proof file; without them no law
with an impossible premise can be checked at all.

---

## 4. Worked example: the smallest honest harness

```bend
# LAWS.bend — claims only
import Base

type Row is Data:
  Row{path: String, start: Nat, end: Nat}

def Row.clamp_end(row: Row, +line_count: Nat) -> Nat:
  match row:
    case Row{path, start, end}:
      Nat.min(end, line_count)

# REJECTS: `end` unchanged at (end=5, line_count=3).
law Row.span_end_within_file:
  for row: Row
  for line_count: Nat
  {Nat.is_le(Row.clamp_end(row, line_count), line_count) == True{} : Bool}
```

```bend
# PROOF.bend — one def per law, plus the three refutation helpers from §3.5
import Base
import LAWS.bend as Laws

def Laws.Nat.min_le_r(a, b):
  match a b:
    case 0n _:        Laws.Nat.is_le_0_l(b)
    case 1n+ap 0n:    {==}
    case 1n+ap 1n+bp: Laws.Nat.min_le_r(ap, bp)

def Laws.Row.span_end_within_file(row, line_count):
  match row:
    case Laws.Row{path, start, end}:
      Laws.Nat.min_le_r(end, line_count)
```

```bash
cd bend_core
bend PROOF.bend --verdict   # -> ALL PROOFS CHECK, rc=0
bend LAWS.bend              # -> Error: 1 TODOs found, rc=1   (the split, asserted)
```

---

## 5. The gate: six checks, four exit codes

`--verdict` alone is not a gate. It answers one question ("do the proofs check?"). A green
gate must also answer: *was the law deleted? was the proof gutted? did the control fail for the
right reason? did the proofs drift back into the claim file?*

| # | Check | Fails with |
|---|---|---|
| 1 | `bend PROOF.bend --verdict` prints `ALL PROOFS CHECK` | exit 2 |
| 2 | each `NEGATIVE*.bend` **fails**, and names the law it falsifies (`Location: <LawName>`; a parse error prints `Location:` empty) | exit 3 |
| 3 | the negative-control **set** matches a pinned list | exit 3 |
| 4 | the `law` **inventory** of `LAWS.bend` matches a pinned list | exit 5 |
| 5 | `LAWS.bend` **alone** does NOT check — it reports its laws as open claims | exit 2 |
| 6 | two tampered copies of `PROOF.bend` — one proof definition deleted, one body replaced by `{==}` — do NOT check | exit 6 |

Exit **4** is reserved for *infrastructure*: missing distro, missing binary, no verdict line, or
a BendTT translation limit (upstream #1897 prints a translation limit with the same words as a
refuted law). Classifying that as a refutation is how a gate starts lying.

Checks 3–6 exist because "green as written" is blind to the four most likely corruptions. They
were each watched failing before they were trusted.

```bash
bash tools/bend_verify.sh              # the gate (5.47 s measured)
bash tools/bend_verify.sh --selftest   # gate fixtures: RED fixtures must fail, GREEN must pass
```

---

## 6. Writing a law that means something

1. **Name the counterexample first.** Write a `# REJECTS:` line immediately above the law,
   naming the implementation the law excludes. If you cannot name one, the law is too weak.
   A law that passes a no-op implementation is true and useless — e.g. identity is idempotent,
   so `clamp_end_idempotent` alone accepts a clamp that does nothing; it ships *paired with*
   `span_end_within_file`.
2. **Extensional, not implicational, for `Bool`-codomain models.** See §8 — the single most
   expensive trap found here.
3. **One claim per negative-control file.** The kernel stops at the first failing law, so two
   false claims in one file leave the second unexercised: a control that is not a control.
4. **State the domain.** Which inputs are in the modelled domain and which are conventions the
   caller supplies (`1 <= start`, `line_count > 0`)? A true law over a domain production never
   enters certifies nothing. Put the premise in the law as a `for h:` binder, or state it in
   the header and pin the production side with a test.
5. **Ship a mirror.** Laws prove the pure model; a test binds that model to the real function.
   The mirror must be able to fail: neutralize the fix and assert the same grid now violates
   the law.
6. **Do not ship a law whose premise production cannot satisfy** (§9, F-6). Record it as prose.

---

## 7. What a proof can and cannot establish

**Can.** A universally-quantified statement over the declared model, checked by an external
kernel (Lean), independent of your test runner, your sampling, and your mocking.

**Cannot.**

* **Intent.** It proves the statement, not that the statement is the requirement.
* **Reachability.** A true statement about an unreachable configuration certifies nothing.
* **The production binding.** That is the mirror test's job.
* **Timing / liveness / "the agent did the right thing".** Outside its reach; say so in the
  scope block instead of implying coverage.
* **That a model edit was caught.** This is the one that surprises people — §8.

Every law book should carry a header with four things: **scope**, **premises supplied by the
caller**, **mirror path**, and **what is unchecked**. `bend_core/LAWS.bend` lines 29–79 are the
model for this and are worth copying.

---

## 8. F-6b — the false green that `Bool` codomains allow (measured)

An implication-shaped law over a `Bool`-valued helper cannot see the helper go constant:

```bend
law keeps_the_evidence_stale_issue:
  for pack_issue: Bool
  for evidence_issue: Bool
  for h: {evidence_issue == True{} : Bool}
  {lists_stale(pack_issue, evidence_issue) == True{} : Bool}
```

With `lists_stale` **hardwired to `True{}`**, this law still checks: the premise makes the
interesting arm impossible, and `Empty.elim` returns *any* type, including the goal. Measured
here: all **eleven** laws printed `ALL PROOFS CHECK`, rc=0, against a model that disclosed
everything unconditionally. Upstream issue **#1904** describes the same mechanism.

**The fix is an extensional law that pins the function itself:**

```bend
law lists_stale_is_or:
  for pack_issue: Bool
  for evidence_issue: Bool
  {lists_stale(pack_issue, evidence_issue) == Bool.or(pack_issue, evidence_issue) : Bool}
```

The constant `True{}` now fails at `(False, False)`; the shipped pre-fix projection
(`pack_issue` alone) fails at `(False, True)`. Both mutations were watched failing before the
law was added, and the pre-fix projection stays as a permanent negative control.

**Scope of the hazard:** the same probe on a `Nat`-valued model def (`Row.clamp_end → 0n`) went
**red by itself**. The hazard is the **2-element codomain**, not model code in general. Rule:
*a `Bool`-returning model def needs an extensional law; a `Nat`-returning one is pinned by its
own general law.*

---

## 9. F-6 — the vacuity trap (reachability)

A law whose premise production cannot satisfy certifies nothing about production. This
repository hit it from the honest side: a `Tier.meet` lattice (`meet_le_left`,
`meet_le_right`, `idempotent`, `commutative`) was fully proven and then **deleted**, because a
live counterexample showed the two merged trust sources are not peers — the carrier sees the
emitted rows, the search lane's verdict predates a rollback. The meet was a true statement
about a merge production must not perform.

**Discipline:** before trusting a law, name the production input that reaches it. If there is
none, do not ship it as evidence — record the finding as prose. A deleted law that was
honestly evaluated is worth more than a dead proof that looks like coverage.

---

## 10. Version control for laws and proofs — what to do, and why

Short answer: **git alone is not enough, and a new VCS is not the answer.** Use git for the
text and a **proof ledger** (append-only JSONL) for the run. Below is the reasoning, then the
implemented instrument.

### 10.1 Why git alone is insufficient

Git versions *the claim and the proof text*. A proof result is not a function of that text
alone. It is a function of:

| Input | In git? |
|---|---|
| `LAWS.bend`, `PROOF.bend`, `NEGATIVE*.bend` | yes |
| the **kernel** (`lean --version`) and the **translator** (`bend version`) | **no** |
| the gate script's six checks and their pinned lists | yes, but only as text |
| the import closure (`Base`, `LAWS.bend as Laws`, Bend stdlib version) | **no** |
| env that changes the verdict (WSL distro, `BEND_NO_TELEMETRY`, PATH, cwd) | **no** |
| which negative control was expected to fail, and on which `Location:` | **no** |
| the fact that a check was **skipped** (no verdict line, translation limit) | **no** |

So "it was green on the commit" is not reproducible from the commit. That is the gap the owner
asked about, and it is real: the implicit inputs are exactly the ones that flip a green to a
red without touching the tree.

### 10.2 Why not a specialized VCS

A separate VCS for proofs would duplicate content addressing that git already does well, and it
would still not capture the kernel — a *binary outside the repo*. What is missing is not
versioning of text; it is **a record of one run, with its inputs hashed and its judge named.**
That is a ledger, not a VCS.

### 10.3 The design: a proof ledger

One JSONL line per gate run, append-only, in `.bend-ledger/runs.jsonl` (repo-local; a
`git blame` on the laws plus a `grep` on the ledger answers "when did this become green, with
which kernel?"):

```jsonc
{
  "ts": "2026-10-28T18:22:41Z",
  "verdict": "green",                 // green | red | infrastructure
  "gate_version": "2",                // bumped when a check is added/removed
  "judge": {"bend": "2.0.39", "lean": "4.34.0 x86_64-unknown-linux-gnu"},
  "distro": "ubuntu-bend",
  "git": {"commit": "…", "dirty": true, "branch": "…"},
  "files": [{"path": "bend_core/LAWS.bend", "sha256": "…"}, …],
  "imports": ["Base", "LAWS.bend"],
  "checks": [{"name": "verdict", "rc": 0, "expect": "ALL PROOFS CHECK"},
             {"name": "negative:NEGATIVE.bend", "rc": 3, "location": "Row.clamp_end_is_zero"}, …],
  "laws": ["Row.span_end_within_file", …],   // inventory actually observed
  "env": {"cwd": "…", "BEND_NO_TELEMETRY": "1"},
  "wall_ms": 5470,
  "stderr_tail": "…"                   // bounded, for the red case
}
```

Why each field earns its place: `judge` names who decided; `files` pins the text; `imports`
pins the closure that git does not show; `checks` records the *expectation* alongside the rc,
so a control that failed for the wrong reason is visible; `laws` catches a deletion that the
pinned inventory would catch only next run; `git.dirty` prevents "green on a commit that never
existed".

**Implemented:** `tools/bend_proof_ledger.py` (this commit). It runs the gate, parses every
check line, hashes the law files, reads the judge identities, and appends one record.
`budget_run`-style: it never rewrites, never deletes, and a missing judge is
`infrastructure`, not `red`.

```bash
python tools/bend_proof_ledger.py               # run gate + append ledger line
python tools/bend_proof_ledger.py --no-run      # record the last gate output only
python tools/bend_proof_ledger.py --verify      # re-check every recorded green is reproducible
```

### 10.4 What the ledger does NOT solve

It records *that* a run happened with *these* inputs. It cannot prove the kernel binary was
unmodified — hash it (`sha256(which lean)`) if that adversary is in your model. It does not
replace the mirror test: laws still certify the model, not production.

---

## 11. Operating rules that keep the gate honest

1. **`--verdict` only.** `--check-only` runs no proof (upstream: *"run nothing"*) and prints
   `ALL PROOFS CHECK` on a file the kernel rejects (#1896, #1897). Never gate on it.
2. **Print the judge.** A log that does not say which Lean said green is not evidence.
3. **Classify translation limits as infrastructure** (exit 4), never as refutation.
4. **Pin the versions** in CI with an anchored regex: `^bend 2\.0\.39$`, not `2.0.37` (which
   `2.0.37+win` also satisfies).
5. **Assert the split** (`LAWS.bend` alone must fail) and the **inventory** on every run.
6. **Tamper probes must be rebuilt from the current file**, not from a stale fixture.
7. **Review `LAWS.bend` separately from `PROOF.bend`.** Same-commit edits of claim and
   discharge are the one hole the gate cannot close by construction.
8. **A law is never weakened to make a proof pass.** Leave a named hole (`?finished`) and
   report the open claim.

---

## 12. Checklist before you trust a green

- [ ] `bend version` and `lean --version` printed in the log
- [ ] `bend PROOF.bend --verdict` → `ALL PROOFS CHECK`, rc=0
- [ ] `bend LAWS.bend` → `N TODOs found`, rc=1 (the split holds)
- [ ] every law has a `# REJECTS:` line naming a real implementation
- [ ] every `Bool`-codomain model def has an **extensional** law (§8)
- [ ] every negative control is alone in its file and names its law in `Location:`
- [ ] the law inventory is pinned and matches
- [ ] two tamper probes (deleted proof, gutted proof) still fail
- [ ] a mirror test binds the model to production and **was watched failing**
- [ ] the header states scope, premises, mirror path, and what is unchecked
- [ ] a ledger line exists for this run, with judge + file hashes
