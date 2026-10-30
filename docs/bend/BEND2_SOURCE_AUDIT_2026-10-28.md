# Bend 2 — source audit, and how we are using it wrong (measured)

**Date:** 2026-10-28. **Owner's ask, verbatim:** *"quero que tu faça full audit sobre [bend2 e suas laws
and proofs]. nao no que ja sabemos, mas na fonte original, e como OUTRAS pessoas usam. e tambem veja se
devemos atualizar bend2 pra nova versao, e faça caso sim."*

**Method (so the next reader can re-run it):** `git clone --depth 1 https://github.com/HigherOrderCO/Bend`
→ `G:\Temp\opencode\bend-src` (redirects to `bendlang/bend`); `README.md` (11 365 B), `AGENTS.md` (3 333 B),
`WONTFIX.txt` (7 111 B), `LICENSE`, `CHANGELOG.md`, `guide/GUIDE.md` (**677 lines, read in full**),
`demos/*/LAWS.bend` + `demos/app_win_is_bug_2d/PROOF.bend` (**484 lines, read in full**), and six
purpose-built probes under `G:\Temp\opencode\bend-probe\` run through `wsl -d ubuntu-bend`. Everything
below marked *(measured)* is a command I ran; nothing is quoted from memory.

---

## 1. Version — **no update; we are already on the newest release** *(measured)*

| Question | Answer |
|---|---|
| installed | `bend version` → **`bend 2.0.39`** |
| newest release | GitHub `releases/latest` → **`v2.0.39`**, published **2026-10-23** |
| newest commit | clone HEAD `ad64477` (2026-10-28) — **ahead of the release tag, unreleased** |
| `bend update` | would re-install 2.0.39 → **no-op. Not run** (it is `curl \| sh`; a no-op install is still a write) |

**Decision: do not update.** There is nothing to update to. The gate's own rule ("a gate that only runs on
one exact patch would refuse a newer Bend 2 for no reason") stays right: it asserts `^bend 2\.` — the
distribution — not the patch.

**The two-distribution trap is real and our gate already handles it** (`tools/bend_verify.sh:129-157`):
`bend-lang 0.2.38` (crates.io, Bend 1, HVM-era, **no `law`, no `--verdict`**) versus `bend 2.x` (installer).
A Bend-1 binary sits on this host at `H:\cargo\bin\bend.exe`; our gate asserts the distribution **before**
judging any law, which is why a Bend-1 shadow cannot look like "the laws are broken".

---

## 2. What Bend 2 actually is (from the source, not from our AGENTS.md)

Dependently typed, **affine** (values used at most once; `Data` may be copied), **pure** with an `IO` monad,
**termination mandatory**, **no mutual recursion**, **no `if`** (a branch is `match` on `True{}`/`False{}`),
**no tactics and no proof search** — a proposition is a type and a proof is a `def` of it.

`--verdict` = *"check it, then recheck it with the proven kernel"*: the terms are elaborated to **BendTT**
and checked by **`bend2/bendtt.lean`**, a Lean kernel (v4.34.0) with a proof that no def it accepts has type
`Empty` and that live code halts. `-o PROOF.bendtt` writes the translation.

Limits that bind *our* use of it, quoted from the upstream files:

| Source | Limit | Consequence for us |
|---|---|---|
| README "Limitations" | *"Laws are proven about Bend's semantics. The backends can still differ, for example in F32 NaN. See WONTFIX."* | a law never certifies the C/JS output — the mirror test is mandatory, not optional |
| README | *"`--verdict` checks the translated terms, the parser and translation into the kernel are not proven."* | the gate certifies the *checker*, not the text→term step |
| README | *"The checker has no proof and may have bugs; `--verdict` uses a proven kernel."* | plain check is the weaker mode; **always `--verdict`** |
| README | *"The compiler (not kernel) is 99% AI-written and not yet fully audited."* | we trust the kernel, not the compiler |
| `WONTFIX.txt` | *"The checker skips dead code"* (#820/#878/#973/#1091) | **a law about an unreachable branch is vacuous** — the upstream form of our vacuity trap |
| `WONTFIX.txt` | *"The checker is not optimal: some terms are exponential or overflow"* (#993/#1075) — *"a law keeps its large constants and depths abstract"* | keep law constants/depths abstract or the check explodes |
| `WONTFIX.txt` | *"A fallback arm does not refine a dependent goal"* (#1091) | write the constructor arms out |
| `WONTFIX.txt` | *"Windows is not supported. Use WSL."* | our `ubuntu-bend` distro is the only supported path |
| `WONTFIX.txt` | *"`!` runs on the CPU on WSL2 GPUs"* (#1066) | irrelevant to us — we use no GPU lane |

`LICENSE` = **Apache-2.0** (we consume the binary and write our own `.bend` files; no vendoring involved).

---

## 3. The law/proof contract — authoritative, and **our repo diverges from it**

From `guide/GUIDE.md:319-341` and the canonical docs page:

1. **`LAWS.bend`** states the laws. Upstream's *convention* is *"the human writes it, the AI does not touch
   it"* — **a convention, not a capability limit**: nothing in Bend checks who wrote a file, and an agent
   can author either side (owner, 2026-10-28: *"you, ai agent, can also"*). What the convention buys is
   review separation, and that is the part worth keeping. A law with no proof is an **open claim**.
2. **`PROOF.bend`** imports `LAWS.bend` and proves each law with a `def` **of the same name** as
   `<alias>.<law name>` (`law sorted` → `def Laws.sorted`).
3. **`bend PROOF.bend` is the gate:** `SOME PROOFS FAIL` while any law is open or false, `ALL PROOFS CHECK`
   once every law holds. Exit 0/1.
4. **`bend` refuses a `PROOF.bend` that sits beside a `LAWS.bend` without importing it`** *(measured: P3)*.
5. Review `LAWS.bend` **separately** from implementation: *"An agent that deletes a requirement can make the
   remaining proofs pass without satisfying the original request."*

### 3.1 The six probes *(all measured on 2.0.39, artifacts in `G:\Temp\opencode\bend-probe\`)`*

| Probe | Question | Result |
|---|---|---|
| **P1** | two **false** laws, no proofs, one file | `SOME PROOFS FAIL`, `Error: 2 TODOs found`, **rc=1** — open claims are **counted, all of them** |
| **P2** | law in `LAWS.bend`, proof as `def Laws.refl_probe` in `PROOF.bend` | **`ALL PROOFS CHECK`, rc=0** — **cross-file filling works** |
| **P3** | `PROOF.bend` beside a `LAWS.bend` it does not import | refused: *"`a def with no return type fills a law; no law named t3 is in scope`"*, rc=1 |
| **P4** | two laws, each with a **wrong** proof present | reports **one** location (`Location: wrong_one`), rc=1 → a failing proof stops the report at the first |
| **P5** | `@unsafe def` used to inhabit a **false** law | **`SOME PROOFS FAIL`, rc=1** in plain, `--check-only` **and** `--verdict` — *"1 def relies on unsafe or foreign code"* |
| **P6** | law named `Box.refl` (a dot in the name), proof as `def Laws.Box.refl` elsewhere | **`ALL PROOFS CHECK`, rc=0** → the split is mechanical for **our** dotted names too |

**Two of our repo's own statements are falsified by P2/P6:**

- `bend_core/PROOF.bend:5-7` says *"Bend refuses a def in one file from filling a law declared in another
  ("a def with no return type fills a law"), so PROOF.bend cannot restate the proofs."* — **false.** P2 and
  P6 both fill a law from another file and check. The real rule is that the def must be named
  `<alias>.<law name>` where `<alias>` is the import alias. (P3 is the *different* rule: a `PROOF.bend`
  beside a `LAWS.bend` it does not import is refused.)
- `AGENTS.md` describes the law gate as `bend <file>.bend --check-only` and gives `--verdict` as "recheck
  with the proven kernel" — the second half is right, the first is not the contract: **the gate is
  `bend PROOF.bend`**, and `--check-only` runs no proof at all. `AGENTS.md` is another lane's dirty file;
  the correction is recorded here and ticketed.

### 3.2 Correction to a community claim *(this is why the audit was worth doing)*

A practitioner post (`nohzafk.github.io`, 2026-09-27) warns: *"An unsafe definition can prove anything... the
checker still prints 'All terms check', with a warning next to it. The gate has to reject that warning, not
just look for the success line."* **On 2.0.39 that is no longer true** *(P5)*: `@unsafe` yields `SOME PROOFS
FAIL` with **rc=1** in every mode. So:
- our gate is safe **by construction** — it fails on `SOME PROOFS FAIL` *and* requires `rc=0`, so a
  regression to the old behaviour would be caught twice;
- I added **no** guard for it: a check whose outcome is already guaranteed is decoration, and dead guards
  are what this repo's no-unjustified-fallback rule forbids.

---

## 4. How *other* people use it

**Adoption, measured today:** 24 488 stars · 778 forks · 113 open issues · last push 2026-10-28 ·
**8 625 downloads** of `bend-2.0.39-linux-x64.tar.gz` in 5 days (release published 2026-10-23). Community
tooling listed by the README: `don2e4/bend2-lsp` (community language server) and the *Bend 2 pocket workshop*
(`np.github.io/bend-workshop/`), plus Discord and r/bendlang.

**Canonical usage — the upstream `demos/`.** Every demo has `LAWS.bend` (claims only, importing the app) and
`PROOF.bend` (proofs, importing the claims as `Laws`). `demos/app_win_is_bug_2d/PROOF.bend` is **484 lines
of proof scaffolding for 2 laws** (a `T(b: Bool)` reflection kit, `and_split`, `imp_elim`, `le_split`,
`chk_all` certificates…). That is the honest cost datum: **the proof, not the law, is the expensive artifact.**

**Third-party write-ups (both real projects, both recent):**
- `franzramadhan.dev` (2026-10-23), *Law-Driven Development* — an authorization table; states the split as
  *"the human writes `LAWS.bend`; the AI writes `PROOF.bend`"* and uses `bend PROOF.bend` as the gate.
- `nohzafk.github.io` (2026-09-27), *A Proved Core Inside a TypeScript App* — the most useful account, because
  it names the four ways a proof misleads, and **three of them are already in our registry**:
  1. *"A law written in terms of a helper says nothing about bugs in that helper"* → the laws must cover the
     helper, or the guarantee has a hole exactly where the bug is;
  2. *"Proofs can't see run time"* → our open gap (`within_latency_budget` unprovable);
  3. *"The host isn't proved"* → the mirror-test argument;
  4. the `@unsafe` warning — **corrected above by measurement**.
  And his three habits map onto ours: *give every law a mutant* (= our tamper probes), *check the falsifier
  can fail*, *recognise equivalent mutants* (= our "fail for the right reason").

**Official docs site** `bend2.dev` (last updated 2026-10-26, compiler `a3efe8a` — the 2.0.39 commit) carries
a page that is almost our own design doc: *"Idempotence alone would also accept a no-op implementation"* — it
pairs `cancel_idempotent` with `cancels_queued` / `cancels_running` / `preserves_finished` so that a no-op
cannot pass. **That is our `REJECTS:` rule, stated upstream with a worked example.** It also says: check
`LAWS.bend` alone → *"4 TODOs found. Exit status 1"* (matches P1 exactly), and `PROOF.bend` → `ALL PROOFS
CHECK`, *"Use `--verdict` for mathematical validity"*.

---

## 5. Our repo against the contract

| Practice | Verdict |
|---|---|
| `--verdict` (proven kernel), never plain check | **correct**, and cheap: **0.2 s** plain vs **0.2 s** verdict *(measured; the Lean CLI is already built)* |
| negative control in its **own** file, must fail **with a named Location** | **correct**, and P4 shows the reason is real: a failing proof reports only the first location |
| law **inventory pinned** | **correct** — and it is upstream's own advice ("an agent that deletes a requirement…") |
| tamper probes (proof deleted / proof gutted) | **correct** — same as the community "give every law a mutant" |
| no `@unsafe`, no foreign imports in `bend_core` | **correct** — makes `--verdict` eligible to certify at all |
| whole gate cost | **5.2 s** *(measured)* → **it can be a PR gate**, not nightly |
| proofs live in **`LAWS.bend`** beside the laws | **diverges**: Bend allows it, but it erases the human/AI boundary and the separate-review property upstream insists on |
| `PROOF.bend` holds *witnesses*, not proofs (because of the false claim above) | **diverges**, and the divergence is justified by a false sentence |
| `AGENTS.md`'s CLI description (`--check-only` as the law gate) | **wrong**; another lane's dirty file |

---

## 6. Decisions (and what I did)

1. **Do not update Bend.** 2.0.39 is the newest release *(measured)*. Nothing else is warranted.
2. **Keep `--verdict` as the only mode.** It costs nothing over plain check *(0.2 s vs 0.2 s)* and it is the
   only mode backed by a proven kernel.
3. **Fix the false claim** in `bend_core/PROOF.bend` — done in this turn; a proof artifact must not carry a
   sentence that a probe refutes.
4. **Ticket the `LAWS`/`PROOF` split** (`P0.42`) rather than perform it here: it is *proven mechanical* (P2,
   P6) but it invalidates both tamper probes (their awk patterns are keyed to `def` blocks in `LAWS.bend`)
   and the naming rule for the 5 helper defs must be applied by hand (helpers keep their names; only the 11
   law-filling defs take the `Laws.` prefix). That is a verified change with its own gate run — not a
   "declare and continue". **Executed later the same day — see §9.**
5. **Ticket the AGENTS.md correction** (`P0.43`) — blocked by the other lane's dirty file.
6. **No guard for `@unsafe`** — closed by construction on 2.0.39 *(P5)*; adding one would be dead code.
7. **Anchor the CI version pin** (`bend-laws-gate.yml`) to `^bend 2\.0\.39$` and record the judge (`bend` +
   `lean --version`) in the gate's own output: kernel acceptance measurably widens between patches (#1892),
   and an unanchored `grep -q "2.0.37"` accepts a fork build printed as `2.0.37+win` (#1907).
8. **Name a translation limit as infrastructure, not as a refutation.** `--verdict` prints a BendTT
   translation limit with the words `SOME PROOFS FAIL` (#1897), so the gate classifies the verdict text
   (`verdict_class`, exercised by `tools/bend_verify.sh --selftest`) and exits 4 instead of blaming a proof
   that is fine.

---

## 7. What a Bend law cannot prove (upstream + community, consolidated)

1. **Runtime**: time, memory, stack depth, liveness.
2. **The host/foreign layer**: any C or JS effect, the parser, and the text→term translation `--verdict` reads.
3. **The backends**: laws hold for Bend's semantics; C/JS may differ (F32 NaN is the documented case).
4. **Dead code**: the checker skips it, so a law about an unreachable branch is vacuous.
5. **Anything the laws did not say** — including bugs in the helper a law is written with.
6. **A no-op implementation** — unless a second law excludes it (upstream's `cancel_idempotent` +
   `cancels_queued` example).

## 8. What this audit does not establish

- I read `GUIDE.md`, `README`, `WONTFIX`, `CHANGELOG` head, `LICENSE`, `AGENTS.md` and one full `PROOF.bend`;
  I did **not** read `bend2/bend.ts` (the checker) or the BendTT Lean kernel — so "the kernel is sound" is
  **their** claim, not my measurement.
- The 848-instance corpus is not involved; nothing here says anything about retrieval quality.
- `bend update` was not executed (no-op by design), so the install path itself is unexercised on this host.
- The `LAWS`/`PROOF` split is proven **feasible** (P2, P6) but not proven **complete** for our 11 laws and
  5 helpers until it is actually performed and the gate re-runs green. *(Performed; §9 records the run.)*

---

## 9. Execution record — the split, and the vacuity probe *(2026-10-28, same day)*

**The split is done and the gate is green.** `bend_core/LAWS.bend` now holds the 12 claims plus the three
definitions the claims *mention* (`type Row`, `Row.clamp_end`, `lists_stale`); `bend_core/PROOF.bend`
imports it and holds the 3 refutation helpers, the 11 law-filling `def Laws.<law>` proofs (dotted names
included), and the runtime witnesses. `bend PROOF.bend --verdict` → `ALL PROOFS CHECK`, rc=0, and
`bend LAWS.bend` alone → `Error: 12 TODOs found`, rc=1 — the second output is now **asserted** by the gate,
because it is the evidence that the proofs really left the claim file.

Cost of the change, measured, all in `tools/bend_verify.sh`: the two tamper probes are rebuilt from
`PROOF.bend` and their expected `Location:` names gained the alias (`Laws.Row.span_end_within_file`) —
bend names the **def**, not the bare law, once the proof lives elsewhere. Gate wall time 11.8 s (was ~5 s;
the extra run is `bend LAWS.bend`), and `--selftest` covers the verdict classifier in 0 extra runs.

**Three probes that the subagent audit specified but could not run, run here:**

| Probe | Question | Result |
|---|---|---|
| **P8** | mutate the **model** — `Row.clamp_end` returns `0n`, laws and proofs untouched | **RED** (`SOME PROOFS FAIL`, `Location: Laws.Row.span_end_within_file`). A `Nat`-valued model def cannot go vacuous: the proof term stops typing against the widened goal. |
| **P9** | mutate the **model** — `lists_stale` hardwired to `True{}` | **GREEN, rc=0 — a false green.** All 11 laws still checked. This is upstream #1904's mechanism reproduced in our tree. |
| **P9b** | add `law lists_stale_is_or` (`lists_stale(p,e) == Bool.or(p,e)`), then repeat P9 | **RED** at (False, False), and the pre-fix projection is RED at (False, True). Both watched before the law was added; both are now permanent controls (`test_e113_law_invariants.py`). |

⇒ the audit's strongest claim is **half confirmed, half falsified**, and the falsifier is the interesting
half: model tampering is *not* a general hazard, it is a hazard **specific to 2-element codomains**. An
implication-shaped law cannot see a `Bool` helper go constant, so a `Bool` model function needs an
**extensional** law. That is now F-6b in `docs/EVOLUTION_TOOLCHAIN.md`, and `LAWS.bend` carries the
`REJECTS:` block that names both degenerate models.

**Not established by §9:** the `PROOF.bend`/`LAWS.bend` pairs upstream's demo uses may still differ from
ours in ways the kernel treats differently (their #1904 report is about their layout); and none of this says
anything about whether a law's *premise* is reachable from production — that is F-6 proper and stays a
reading, not a check.
