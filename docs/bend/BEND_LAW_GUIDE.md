# Proving intent — Bend 2 laws and proofs

> Moved verbatim from the root `AGENTS.md` (P0.43b split, 2026-10-28).
> The original heading is kept unchanged so `AGENTS.md §Section`
> citations resolve; `AGENTS.md` keeps a stub at the original position.
> Nothing in this file was reworded, shortened or deleted.

## Proving intent — Bend 2 laws and proofs (MANDATORY when a claim matters)

A green test says "these inputs passed". A law says "this holds for EVERY input,
and here is the proof the kernel accepted". This repo prefers the second whenever
a promise is load-bearing, because its historical failure mode is *tests green,
product promise broken*. `bend_core/` is that evidence, not a toy.

**Toolchain.** `bend_core/LAWS.bend` (**claims only** — 12 `law` declarations plus
the three defs the claims mention: `type Row`, `Row.clamp_end`, `lists_stale`),
`bend_core/PROOF.bend` (`import LAWS.bend as Laws`, one `def Laws.<law name>` per
claim — dotted names included — plus the refutation helpers and the runtime
witnesses), `NEGATIVE*.bend` (claims that MUST NOT check), `bend_core/model.py`
(Python mirror for hosts without Bend). **The gate is `bend PROOF.bend
--verdict`**, wrapped by `bash tools/bend_verify.sh` (runs Bend 2 inside the
`ubuntu-bend` WSL distro; POSIX/CI branch runs a native `bend`); `bend LAWS.bend`
alone reports every law as an open claim (`N TODOs found`) and the gate asserts
that output, so proofs cannot quietly move back into the claim file. Docs:
`docs/EVOLUTION_TOOLCHAIN.md` (install, friction log incl. F-6b, limits),
`docs/codeintel-completion/BEND2_SOURCE_AUDIT_2026-10-28.md` (the measured
contract, six probes, and the split's execution record); the older
"candidate-law table" pointer into `EVOLUTION_SPECS.md` §11 was **wrong** — §11
is *Definition of Success* and has nothing to do with laws.

**Never `--check-only` as a gate.** It runs **no proof** (`bend --help`: "run
nothing") and prints `ALL PROOFS CHECK` on a file the kernel rejects (upstream
#1897, #1896). `--verdict` is the only mode this repo gates on, and the gate
prints both `bend version` and `lean --version` because kernel acceptance
widens between patch releases (#1892): a log must name which kernel said green.

**The gate checks six things, and each has been watched failing** (typed exit
codes, POL-6): (1) `ALL PROOFS CHECK` on `PROOF.bend` → else 2; (2) every negative
control fails **and names the law it was written to falsify** (`Location:
<LawName>`; a parse error prints `Location:` empty) → else 3; (3) the
negative-**control set** matches a pinned list → else 3; (4) the `law`
**inventory** of `LAWS.bend` matches a pinned list → else 5; (5) `LAWS.bend`
**alone** must NOT check — it must report its laws as open claims → else 2
(this is what keeps the claim file free of proofs); (6) two **tampered copies of
`PROOF.bend`** — one with a proof definition deleted, one with a proof body
replaced by `{==}` — do NOT check → else 6. 4 is unusable (missing
distro/binary/no verdict, **or a BendTT translation limit**, which #1897 prints
with the same words as a false law and which the gate classifies as
infrastructure rather than blaming the proof). Checks 3–6 exist because "green
as written" is blind to a law being *deleted* (nobody checks it any more), a
proof being *gutted* (a proof of a weaker statement is still a proof), the
proofs quietly moving back into the claim file, or a control failing for the
*wrong reason* (measured: a control with a syntax error still prints `SOME
PROOFS FAIL`, so the verdict alone would have passed it).

**Law-writing contract (each rule was learned the hard way):**
1. **Closure is compile-time.** An unfilled `law` is a *dead claim*; there is no
   "skipped law" state to drift into. Use that: state the law, then prove it.
2. **Every law ships a negative control that MUST fail,** and **one claim per
   file** — the kernel stops at the FIRST failing law, so two false claims in one
   file leave the second unexercised (a control that is not a control).
3. **A law is half the evidence; the mirror is the other half.** Laws prove the
   *pure model*; a `tests/` mirror binds that model to the *real production
   function* (build the model mutation from production source, run the actual
   function). Neither substitutes for the other.
4. **Reachability (the vacuity trap, F-6).** A law whose premise production
   cannot satisfy certifies nothing about production. Before trusting a law,
   name the production input that reaches it; if none does, do not ship it as
   evidence. E11.5 hit this from the honest side: a `Tier.meet` lattice was
   proven and then **deleted** — a live counterexample showed the two merged
   sources are not peers (carrier `trusted` vs search lane `caution` +
   `identity_only_rows` is intentional: the carrier sees the emitted spans, the
   search verdict predates the profile rollback). The law was TRUE about a merge
   production must not perform, so it was recorded as prose, not shipped as dead
   proof.
5. **Make the mirror load-bearing.** Neutralize the fix and assert the SAME grid
   now VIOLATES the law. A suite that never watched the defect fail is
   decoration. (F-6 protocol: build the artifact and a tampered artifact, assert
   the verdict differs.)

**What a proof CANNOT show — the essentials that prove *intent*.** A proof
certifies a *statement over a model*, never the intent behind it. To claim intent
you need, additionally: (a) **the artifact** — assert on the real emitted payload
(not a reconstructed envelope); (b) **the falsifier** — the negative control /
mutation above; (c) **an honest scope block** — what is proven, what remains a
premise, what is unchecked, written where the next reader will hit it; (d)
**reachability** (rule 4); (e) a **latency/behaviour invariant** where the intent
is a budget — none exists yet for latency, so `within_latency_budget=false` is
observable but unproven (recorded as an open gap, not hidden).

**Worked example — the trust-disclosure law (E11.5).** Two independent sources
build one emitted trust block: the *carrier* (`context_pack._pack_trust_block`:
emitted rows + inner verification, NO freshness arm) and the *search* lane
(`agent_trust.assess_agent_trust`: freshness + disclosure). The emit seam
(`envelope_profiles._slim_single_trust`) took the verdict from the carrier and
backfilled scalars from the search lane without its `issues`, so a live payload
read `trust_tier=trusted`, `agent_action=act_on_results`, `issues=[]`,
`index_stale=true`, `index_age_hours=64.26` — one object claiming both "no
caveats" and "the index is stale". The law (`keeps_the_evidence_stale_issue`:
never drop the evidence lane's stale issue) + its mirror
(`tests/evolution/test_law_mirror_trust.py`, which rebuilds the pre-fix merge and
shows it violating the law) + the fix in `_merge_single_trust` are the whole
argument. Two design lessons are pinned there rather than re-litigated: the
merge is **disclosure-only** (the carrier is authoritative for the verdict — a
proven `Tier.meet` was deleted after a live counterexample showed the sources are
not peers), and it copies only the **freshness-disclosure** issue set (not the
search lane's row-verdict issues like `identity_only_rows`, which the carrier may
have legitimately superseded).

---

