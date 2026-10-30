# Proofs of the laws declared in bend_core/LAWS.bend.
#
# THE GATE IS THIS FILE: `bend PROOF.bend --verdict` asks the proven
# (Lean 4.34 BendTT) kernel to check every law and prints ALL PROOFS CHECK with
# rc=0 only when they all hold. `tools/bend_verify.sh` runs that, then the
# negative controls, then the guard checks.
#
# ONE `def Laws.<law name>` PER LAW, aliasing the import `Laws`. That is the
# shape Bend 2 documents upstream, measured on 2.0.39: a def named
# `<alias>.<law>` DOES fill a law declared in another file, including a law
# whose name contains a dot, and bend refuses a PROOF.bend that sits beside a
# LAWS.bend it does not import. So the pairing cannot silently come apart, and
# a law with no proof fails the gate -- it cannot be skipped.
#
# Measured consequence of the split worth knowing before editing: bend reports
# a failing proof at `Location: Laws.<law name>` (the DEF name, alias included),
# not at the bare law name.
#
# WHO WRITES WHAT. The upstream convention is "a human writes LAWS.bend, an
# agent writes PROOF.bend". That is a convention, not a capability limit; an
# agent may author either side. The split exists for REVIEW SEPARATION -- a
# changed claim and a changed discharge are different diffs.
#
# Run:  bend PROOF.bend --verdict    # the proof gate (ALL PROOFS CHECK)
#       bend PROOF.bend              # + one line per witness below
#
# LAYOUT. Bend 2.0.39 has no mutual recursion and a def may only call a def
# defined EARLIER (measured: "expected : a filled definition"). So this file is
# a ladder: refutation primitives, then the Nat toolkit, then the proofs, each
# rung only calling rungs above it. Every helper has an explicit return type
# and typed parameters (a def with no return type is a law-filling def, and
# that is reserved for the `Laws.*` names).

import Base
import LAWS.bend as Laws

# ---------------------------------------------------------------------------
# Refutation primitives
#
# A branch whose hypothesis is FALSE cannot be discharged by `{==}`, and cannot
# be closed by an empty match either: `match hab:` on `{False{} == True{} : Bool}`
# is rejected with "expected : a datatype". The guide gives the recipe --
# rewrite the clash through a motive that sends the wrong side to `Empty`, then
# eliminate that `Empty` through a def, because a match cannot scrutinize a
# computed value.
# ---------------------------------------------------------------------------

def Bool.disc(b: Bool) -> Type:
  match b:
    case True{}:
      Empty
    case False{}:
      Unit

def Bool.absurd_false_true(e: {False{} == True{} : Bool}) -> Empty:
  %e : {Bool.disc(_) : Type}
  Unit{}

def Empty.elim(-A: Type, e: Empty) -> A:
  match e:

# ---------------------------------------------------------------------------
# THE NAT TOOLKIT
#
# `Nat.is_le(a, b)` does not reduce unless BOTH arguments have a known
# constructor: it is `Cmp.is_le(Nat.cmp(a, b))`, and `Nat.cmp` matches on both
# arguments at once (0n/0n, 0n/1+bp, 1+ap/0n, 1+ap/1+bp). So every lemma below
# is written as a `match` on the arguments, and each branch either computes
# (both sides land on the same term, `{==}`) or hands the neutral case to a
# lemma that matches FURTHER -- never to a match on a computed value, which
# Bend rejects ("a match cannot scrutinize a computed value").
#
# The two impossible arms of `le_trans` are the technique the rest of the file
# reuses: `is_le(1+ap, 0n)` computes to `False{}`, so a hypothesis typed
# `{is_le(1+ap, 0n) == True{} : Bool}` IS `{False{} == True{} : Bool}`, which
# `Bool.absurd_false_true` turns into `Empty`, which `Empty.elim` discharges
# into ANY goal.
# ---------------------------------------------------------------------------

# `0 <= b`, for every b. The two-constructor split is exhaustive, so the
# neutral `b` never reaches the kernel.
def le_0_l(b: Nat) -> {Nat.is_le(0n, b) == True{} : Bool}:
  match b:
    case 0n:
      {==}
    case 1n+p:
      {==}

# Transitivity. `Nat.cmp` strips one successor from BOTH sides at once, which is
# why the step case recurses on `ap bp cp` and the goal lands exactly on the
# induction hypothesis.
def le_trans(a: Nat, b: Nat, c: Nat, hab: {Nat.is_le(a, b) == True{} : Bool}, hbc: {Nat.is_le(b, c) == True{} : Bool}) -> {Nat.is_le(a, c) == True{} : Bool}:
  match a b c:
    case 0n _ _:
      le_0_l(c)
    case 1n+ap 0n _:
      Empty.elim({Nat.is_le(1n+ap, c) == True{} : Bool}, Bool.absurd_false_true(hab))
    case 1n+ap 1n+bp 0n:
      Empty.elim({Nat.is_le(1n+ap, 0n) == True{} : Bool}, Bool.absurd_false_true(hbc))
    case 1n+ap 1n+bp 1n+cp:
      le_trans(ap, bp, cp, hab, hbc)

# `a <= 1 + a`. This is the "the other side is one bigger" step that closes
# every `0 + c <= 1 + l` arm below.
def le_1_r(a: Nat) -> {Nat.is_le(a, Nat.add(1n, a)) == True{} : Bool}:
  match a:
    case 0n:
      {==}
    case 1n+ap:
      le_1_r(ap)

# `Bool.pick` commutes with a successor on both arms. Neutral in `b` -- the
# match is on the PARAMETER, so the kernel sees the two cases and `{==}` closes
# each one.
def pick_succ(b: Bool, x: Nat, y: Nat) -> {Bool.pick(Nat, b, Nat.add(1n, x), Nat.add(1n, y)) == Nat.add(1n, Bool.pick(Nat, b, x, y)) : Nat}:
  match b:
    case True{}:
      {==}
    case False{}:
      {==}

# THE INDICATOR IS MONOTONE IN THE CLOCK: if `t1 <= t2`, the flag of a word at
# `at` can only go 0 -> 1, never 1 -> 0.
#
# Eight arms, because `is_le(at, t)` needs BOTH sides known to compute, and
# three arguments give 2x2x2. The only arms that are not pure computation are:
#   - `1+ap / 0n / 1+tp2`: the flag at t1 is 0 (1+ap <= 0 is false), so the
#     goal is `0 <= anything` -- `le_0_l` closes it against the neutral flag.
#   - `1+ap / 1+tp1 / 0n`: the hypothesis says `1+tp1 <= 0`, which computes to
#     False, so it refutes the branch.
#   - `1+ap / 1+tp1 / 1+tp2`: both flags lose their common successor and the
#     goal IS the induction hypothesis.
def flag_mono(at: Nat, t1: Nat, t2: Nat, h: {Nat.is_le(t1, t2) == True{} : Bool}) -> {Nat.is_le(Laws.Nat.revealed_flag(Nat.is_le(at, t1)), Laws.Nat.revealed_flag(Nat.is_le(at, t2))) == True{} : Bool}:
  match at t1 t2:
    case 0n 0n 0n:
      {==}
    case 0n 0n 1n+tp2:
      {==}
    case 0n 1n+tp1 0n:
      {==}
    case 0n 1n+tp1 1n+tp2:
      {==}
    case 1n+ap 0n 0n:
      {==}
    case 1n+ap 0n 1n+tp2:
      le_0_l(Laws.Nat.revealed_flag(Nat.is_le(ap, tp2)))
    case 1n+ap 1n+tp1 0n:
      Empty.elim({Nat.is_le(Laws.Nat.revealed_flag(Nat.is_le(1n+ap, 1n+tp1)), Laws.Nat.revealed_flag(Nat.is_le(1n+ap, 0n))) == True{} : Bool}, Bool.absurd_false_true(h))
    case 1n+ap 1n+tp1 1n+tp2:
      flag_mono(ap, tp1, tp2, h)

# SUMS OF INDICATORS: `flag(b1) + c1 <= flag(b2) + c2` from the two parts.
#
# `c2` is ERASED (`+c2`): it appears twice in the `False{}/True{}` arm (once as
# the middle of the transitivity chain, once inside `1 + c2`), and Bend is
# affine -- measured: "expected : c2, observed : c2 (consumed more than once)".
# The annotation is what makes the second mention legal; the value is only ever
# read inside types and proofs, never at runtime.
def flag_add_mono(b1: Bool, b2: Bool, c1: Nat, +c2: Nat, hf: {Nat.is_le(Laws.Nat.revealed_flag(b1), Laws.Nat.revealed_flag(b2)) == True{} : Bool}, hc: {Nat.is_le(c1, c2) == True{} : Bool}) -> {Nat.is_le(Nat.add(Laws.Nat.revealed_flag(b1), c1), Nat.add(Laws.Nat.revealed_flag(b2), c2)) == True{} : Bool}:
  match b1 b2:
    case True{} True{}:
      hc
    case True{} False{}:
      Empty.elim({Nat.is_le(Nat.add(Laws.Nat.revealed_flag(True{}), c1), Nat.add(Laws.Nat.revealed_flag(False{}), c2)) == True{} : Bool}, Bool.absurd_false_true(hf))
    case False{} True{}:
      le_trans(c1, c2, Nat.add(1n, c2), hc, le_1_r(c2))
    case False{} False{}:
      hc

# THE HEAD STEP OF THE BOUND: one more indicator in front of a count.
#
# `l` is erased for the same affine reason: the `False{}` arm mentions it twice.
# The arms are the indicator's two values:
#   - `True{}`: the goal is `1 + c <= 1 + l`, which is `c <= l` after the
#     successor cancels -- exactly `hcl`.
#   - `False{}`: the goal is `c <= 1 + l`, one step of slack over `hcl`.
def flag_add_le(b: Bool, c: Nat, +l: Nat, hcl: {Nat.is_le(c, l) == True{} : Bool}) -> {Nat.is_le(Nat.add(Laws.Nat.revealed_flag(b), c), Nat.add(1n, l)) == True{} : Bool}:
  match b:
    case True{}:
      hcl
    case False{}:
      le_trans(c, l, Nat.add(1n, l), hcl, le_1_r(l))

# `flag(b) + 0 == flag(b)`. Written as a lemma on the Bool PARAMETER so the
# kernel can see the indicator's two values; a `match` on the computed
# `is_le(at, t)` itself is rejected.
def add_flag_zero(b: Bool) -> {Nat.add(Laws.Nat.revealed_flag(b), 0n) == Laws.Nat.revealed_flag(b) : Nat}:
  match b:
    case True{}:
      {==}
    case False{}:
      {==}

# `min(a, b) <= a` and `min(a, b) <= b`. `Nat.min` strips a successor from both
# sides together, so the step case is the induction hypothesis on `ap bp`.
def min_le_l(a: Nat, b: Nat) -> {Nat.is_le(Nat.min(a, b), a) == True{} : Bool}:
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+bp:
      {==}
    case 1n+ap 0n:
      {==}
    case 1n+ap 1n+bp:
      min_le_l(ap, bp)

def min_le_r(a: Nat, b: Nat) -> {Nat.is_le(Nat.min(a, b), b) == True{} : Bool}:
  match a b:
    case 0n 0n:
      {==}
    case 0n 1n+bp:
      {==}
    case 1n+ap 0n:
      {==}
    case 1n+ap 1n+bp:
      min_le_r(ap, bp)

# ---------------------------------------------------------------------------
# LEMMA: `Nat.revealed_flag` is the `Nat.min(1, ...)`-shaped indicator, i.e. it
# is 1 on `True{}` and 0 on `False{}`. Written as an EXTENSIONAL law on the
# two values of `Bool`, because `Bool` has exactly two constructors.
#
# MEDIDO: the `Bool` type of Base is `True{}`/`False{}` only, so the two-arm
# case split below is exhaustive by construction, not by judgement.
# ---------------------------------------------------------------------------

def Laws.Nat.revealed_flag_is_zero_or_one(due):
  match due:
    case True{}:
      {==}
    case False{}:
      {==}

# ---------------------------------------------------------------------------
# LEMMA: `Nat.of_bool` agrees with `Nat.revealed_flag`. The two are the two
# shapes the production uses (a `match` on a value, and a `Bool.pick` on a
# computed condition); the law says they compute the same indicator.
# ---------------------------------------------------------------------------

def Laws.Nat.of_bool_agrees_with_revealed_flag(due):
  match due:
    case True{}:
      {==}
    case False{}:
      {==}

# ---------------------------------------------------------------------------
# PROOF: the count of revealed words never exceeds the number of words.
#
# Induction on the word list. The step case is ONE indicator in front of the
# tail's count, and `Toks.length` is one successor in front of the tail's
# length -- `flag_add_le` is exactly that step, with the induction hypothesis
# as its `c <= l`.
#
# The law binder is `for +toks` and `for +t_ms`: the Cons arm mentions `tail`
# twice (its count and its length) and `t_ms` three times (head's flag, the
# tail's count, the recursive call). Bend is affine, and a `+` on the LAW's
# binder erases the proof def's parameter AND the variables bound by the match
# on it -- measured: with the binder erased the match still refines, and the
# pattern variables may be mentioned more than once.
# ---------------------------------------------------------------------------

def Laws.Toks.count_due_counts_only_due_words(toks, t_ms):
  match toks:
    case Laws.ToksNil{}:
      {==}
    case Laws.ToksCon{head, tail}:
      flag_add_le(Laws.Tok.due(head, t_ms), Laws.Toks.count_due(tail, t_ms), Laws.Toks.length(tail), Laws.Toks.count_due_counts_only_due_words(tail, t_ms))

# ---------------------------------------------------------------------------
# PROOF: an empty line reveals nothing. Both sides are the `ToksNil{}` arm of
# `count_due`, so they are the same term before the kernel looks.
# ---------------------------------------------------------------------------

def Laws.Toks.count_due_of_an_empty_line_is_zero(t_ms):
  {==}

# ---------------------------------------------------------------------------
# PROOF: a one-word line's count is that word's indicator. This is the law that
# catches both degenerate models (always 0 and always 1) -- it pins the count
# to the word's own clock.
#
# The count of `[tok]` is `flag(at <= t) + 0`, and `add_flag_zero` drops the
# `+ 0`. Nothing else is left, because `Tok.due` unfolds to exactly the
# `is_le(at_ms(tok), t_ms)` the law writes on the right.
# ---------------------------------------------------------------------------

def Laws.Toks.count_due_of_one_word_is_its_flag(tok, t_ms):
  add_flag_zero(Nat.is_le(Laws.Tok.at_ms(tok), t_ms))

# ---------------------------------------------------------------------------
# PROOF: the count is monotone in time.
#
# Induction on the word list, not on the hypothesis: a `match` cannot
# scrutinize a hypothesis of type `{Nat.is_le(t1, t2) == True{} : Bool}`
# ("expected : a datatype"), so every derived fact about it comes from a def
# that takes it as a parameter (`flag_mono`).
#
# The step case has exactly two parts, and both are consumed once:
#   - the head's flag does not go backwards: `flag_mono` at `at_ms(head)`;
#   - the tail's count does not go backwards: the induction hypothesis.
# `flag_add_mono` then adds them.
#
# The law binder erases all four parameters: the Cons arm mentions `head` twice
# (t1 and t2), `tail` twice, and both instants and the hypothesis twice.
# ---------------------------------------------------------------------------

def Laws.Toks.count_due_is_monotone_in_time(toks, t1_ms, t2_ms, h):
  match toks:
    case Laws.ToksNil{}:
      {==}
    case Laws.ToksCon{head, tail}:
      flag_add_mono(Laws.Tok.due(head, t1_ms), Laws.Tok.due(head, t2_ms), Laws.Toks.count_due(tail, t1_ms), Laws.Toks.count_due(tail, t2_ms), flag_mono(Laws.Tok.at_ms(head), t1_ms, t2_ms, h), Laws.Toks.count_due_is_monotone_in_time(tail, t1_ms, t2_ms, h))

# ---------------------------------------------------------------------------
# PROOF: a line's liveness is "started and not ended".
#
# The four cases of the two facts. `Bool.and` in Base is defined as
# `match a: case False{}: False{}; case True{}: b`, so `and(started, not
# ended)` is `started` when `started` is false and `not ended` otherwise --
# which is exactly `live_flag`.
# ---------------------------------------------------------------------------

def Laws.Nat.live_flag_is_started_and_not_ended(started, ended):
  match started ended:
    case True{} True{}:
      {==}
    case True{} False{}:
      {==}
    case False{} True{}:
      {==}
    case False{} False{}:
      {==}

# PROOF: a line that has not started is not alive.
def Laws.Nat.live_flag_is_false_before_the_line_starts(ended):
  match ended:
    case True{}:
      {==}
    case False{}:
      {==}

# ---------------------------------------------------------------------------
# PROOF: the window shows the minimum of the live rows and the capacity.
#
# `Bool.pick(Nat, is_le(capacity, live_rows), capacity, live_rows)` is
# `capacity` when `capacity <= live_rows` and `live_rows` otherwise -- and
# `Nat.min(capacity, live_rows)` is the same function, because Base's `min`
# compares the first argument with the second. Four arms, and only the last one
# is not pure computation:
#
#   `0n 0n`, `0n 1+cp`, `1+lp 0n` -- the comparison is decided, so `pick`
#   reduces to a numeral and `min` reduces to the same numeral.
#
#   `1+lp 1+cp` -- `is_le(1+cp, 1+lp)` is neutral (`cmp` strips one successor
#   from both sides and stops at `cmp(cp, lp)`), and `min(1+cp, 1+lp)` is
#   `1 + min(cp, lp)`. Two equations do it:
#     `pick_succ`  : pick(b, 1+cp, 1+lp) == 1 + pick(b, cp, lp), with
#                    b := is_le(cp, lp);
#     `Equal.cong` : a successor on both sides of the induction hypothesis
#                    `window_rows(lp, cp) == min(cp, lp)`.
#   `Equal.trans` chains them. The induction hypothesis is the def itself at
#   `(lp, cp)` -- legal because a law-filling def may call itself (a helper may
#   not be defined later, but "itself" is always in scope).
#
# The law binder erases both parameters: `lp` and `cp` appear in the goal, in
# `pick_succ`, in the congruence lambda, and in the recursive call.
# ---------------------------------------------------------------------------

def Laws.Nat.window_rows_is_the_minimum(live_rows, capacity):
  match live_rows capacity:
    case 0n 0n:
      {==}
    case 0n 1n+cp:
      {==}
    case 1n+lp 0n:
      {==}
    case 1n+lp 1n+cp:
      Equal.trans(Nat, Bool.pick(Nat, Nat.is_le(cp, lp), Nat.add(1n, cp), Nat.add(1n, lp)), Nat.add(1n, Bool.pick(Nat, Nat.is_le(cp, lp), cp, lp)), Nat.add(1n, Nat.min(cp, lp)), pick_succ(Nat.is_le(cp, lp), cp, lp), Equal.cong(Nat, Nat, z => Nat.add(1n, z), Bool.pick(Nat, Nat.is_le(cp, lp), cp, lp), Nat.min(cp, lp), Laws.Nat.window_rows_is_the_minimum(lp, cp)))

# ---------------------------------------------------------------------------
# PROOF: the window never shows more rows than the capacity.
#
# From the `min` lemma proved above: the law is stated over `window_rows`, the
# lemma states it is `min`, and `min(capacity, live_rows) <= capacity` is
# `min_le_l`. The rewrite direction matters: `%e : P` replaces an occurrence of
# e's RIGHT side with e's left side, so the equation is used through
# `Equal.sym` to turn `window_rows(...)` INTO `Nat.min(...)` in the goal.
# ---------------------------------------------------------------------------

def Laws.Nat.window_rows_never_exceeds_the_capacity(live_rows, capacity):
  %Equal.sym(Nat, Laws.Nat.window_rows(live_rows, capacity), Nat.min(capacity, live_rows), Laws.Nat.window_rows_is_the_minimum(live_rows, capacity)) : {Nat.is_le(_, capacity) == True{} : Bool}
  min_le_l(capacity, live_rows)

# PROOF: the window never shows more rows than the live ones. The same rewrite,
# with `min(capacity, live_rows) <= live_rows` as `min_le_r`.
def Laws.Nat.window_rows_never_exceeds_the_live_rows(live_rows, capacity):
  %Equal.sym(Nat, Laws.Nat.window_rows(live_rows, capacity), Nat.min(capacity, live_rows), Laws.Nat.window_rows_is_the_minimum(live_rows, capacity)) : {Nat.is_le(_, live_rows) == True{} : Bool}
  min_le_r(capacity, live_rows)
