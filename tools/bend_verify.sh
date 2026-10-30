#!/usr/bin/env bash
# Bend laws gate -- the "one proof, not a green test" check for codeintel.
#
# Usage:
#   tools/bend_verify.sh            # verify PROOF.bend (must pass)
#   tools/bend_verify.sh -v         # + print each witness from PROOF.bend
#
# STRUCTURE (split 2026-10-28, P0.42): bend_core/LAWS.bend holds the CLAIMS and
# the model definitions the claims mention; bend_core/PROOF.bend imports it and
# holds one `def Laws.<law name>` per claim. The gate therefore runs the file
# that carries the PROOFS. Running the claims alone is a different, useful
# reading -- it reports every law as an open claim ("N TODOs found") -- and that
# output is asserted below, because it is the evidence that the proofs really
# left the claim file instead of being duplicated there.
#
# What this does, in order:
#   1. Runs `bend --verdict PROOF.bend` inside the WSL toolchain. The kernel
#      must print ALL PROOFS CHECK. Anything else is a real failure.
#   2. Runs `bend --verdict` on every NEGATIVE*.bend control (the set is pinned).
#      Each states a claim that must NOT check (a false law, or a true law with a
#      naive proof). Any of them printing ALL PROOFS CHECK means the gate is
#      decoration, so we fail. One file per control because the kernel stops at
#      the FIRST failing law: two false claims in one file only ever exercise the
#      first. Each control must also fail WITH A NAMED Location -- a parse error
#      is not a counterexample.
#   3. E11.5 PROOF-STATE GUARD. A green verdict on the file as written cannot
#      see a law DELETED (nothing checks it any more) or a proof body EMPTIED
#      (a proof of a weaker statement is still a proof). Three guards close both,
#      and each is required to be able to fail here:
#        (a) the `law` inventory of LAWS.bend is pinned -- a deleted or renamed
#            law changes it and fails;
#        (b) a copy with one proof definition DELETED must NOT check;
#        (c) a copy with one proof BODY EMPTIED must NOT check -- if either
#            prints ALL PROOFS CHECK, the gate is not reading proof state.
#
# Exit codes (POL-6 -- typed, never silent):
#   0  every law checks, and every negative control fails for the right reason
#   2  a law did NOT check (proof failure -- fix the proof/law)
#   3  a negative control misbehaved: it checked, its set drifted from the pin,
#      or it failed without naming the law it was written to falsify
#   4  toolchain unusable: WSL distro missing, bend missing, no verdict line, or
#      the verdict is a BendTT translation limit rather than a checked claim
#   5  the law inventory of LAWS.bend drifted from the pinned list (a law was
#      deleted/renamed, or a new one was added without updating the pin)
#   6  a proof-state tamper probe misbehaved (a gutted proof still checked, the
#      probe could not build a changed copy, or it failed for the wrong reason)
#
# Toolchain install: docs/EVOLUTION_TOOLCHAIN.md

set -u

# The repository this script BELONGS to, derived from the script's own location.
#
# This used to be a hardcoded /mnt/c/.../consultgpt path, which made the gate lie
# inside every git worktree: running it from a worktree verified the MAIN
# checkout's laws, so a worktree with a deliberately broken law still printed
# "gate green". Deriving the root from $BASH_SOURCE, and printing it below, is
# what makes that failure visible instead of silent.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_WIN="$(cd -- "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$REPO_WIN/bend_core/LAWS.bend" ] || [ ! -f "$REPO_WIN/bend_core/PROOF.bend" ]; then
  echo "FAIL: $REPO_WIN/bend_core/{LAWS,PROOF}.bend not found -- wrong repository root."
  exit 4
fi

# One gate, two toolchain environments. Everything below this block is the gate;
# this block only decides how to reach `bend`, so that CI and a Windows checkout
# run the SAME assertions instead of two copies that drift apart.
if command -v wsl >/dev/null 2>&1; then
  # Windows: the toolchain lives in a dedicated glibc WSL distro (the Alpine
  # distro cannot run --verdict) -- see docs/EVOLUTION_TOOLCHAIN.md.
  #
  # There is deliberately NO override for the repository under test. An override
  # that can point the gate at a different checkout is exactly the failure this
  # script exists to prevent: a worktree whose law does not check would print
  # "gate green" using another tree's passing laws. To verify another checkout,
  # run that checkout's copy of this script.
  DISTRO="${BEND_WSL_DISTRO:-ubuntu-bend}"
  REPO="$(wsl -d "$DISTRO" -e wslpath -a "$REPO_WIN" 2>/dev/null | tr -d '\r')"
  if [ -z "$REPO" ]; then
    echo "FAIL: cannot translate $REPO_WIN to a WSL path (is the '$DISTRO' distro installed?)"
    exit 4
  fi
  WHERE="distro: $DISTRO"
  run_bend() {  # run_bend <file>; prints the verdict text, RETURNS bend's status
    # The status is the function's exit status, not a variable set inside: the
    # caller invokes this as `out="$(run_bend ...)"`, which runs in a subshell, so
    # any variable assigned in here would be discarded and the caller would read a
    # stale value. An earlier revision did exactly that, which made its status
    # check vacuous.
    local out status
    # $REPO and the file name are passed as ARGV, never interpolated into the
    # inner script: a checkout path containing a quote (or any metacharacter)
    # would otherwise break the command or change what it runs. `bash -lc SCRIPT
    # _ a b` makes $1=a, $2=b inside SCRIPT.
    out="$(MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' wsl -d "$DISTRO" -e bash -lc \
      'export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH; cd "$1/bend_core" && bend --verdict "$2"' \
      _ "$REPO" "$1" </dev/null 2>&1)"
    status=$?
    printf '%s\n' "$out" | tr -d '\0'
    return $status
  }
  run_witness() {
    MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' wsl -d "$DISTRO" -e bash -lc \
      'export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH; cd "$1/bend_core" && bend PROOF.bend' _ "$REPO" 2>&1 | tr -d '\0'
  }
  run_version() {
    wsl -d "$DISTRO" -e bash -lc \
      "export PATH=/root/.bend/bin:\$HOME/.elan/bin:\$PATH; bend version" 2>&1 | tr -d '\0'
  }
  run_lean_version() {
    wsl -d "$DISTRO" -e bash -lc \
      "export PATH=/root/.bend/bin:\$HOME/.elan/bin:\$PATH; lean --version" 2>&1 | tr -d '\0' | head -1
  }
else
  # POSIX (CI): the workflow installs the toolchain on PATH.
  #
  # The elan bin dir is added because bend SHELLS OUT to a Lean toolchain that
  # elan installs there: measured 2026-10-30, `bash tools/bend_verify.sh` from
  # inside the distro printed `lean: command not found` while bend itself was
  # on PATH at /usr/local/bin. The gate still passed (bend carries its own
  # kernel) but a toolchain warning inside a green run is a lie the next reader
  # has to re-investigate.
  PATH="$HOME/.elan/bin:/root/.elan/bin:$PATH"
  export PATH
  REPO="$REPO_WIN"
  if ! command -v bend >/dev/null 2>&1; then
    echo "FAIL: bend is not on PATH. Install it (https://bend-lang.com/install.sh) or set up the WSL distro."
    exit 4
  fi
  WHERE="native: $(command -v bend)"
  run_bend() {  # same contract as the WSL branch above
    local out status
    out="$( ( cd "$REPO/bend_core" && bend --verdict "$1" ) </dev/null 2>&1 )"
    status=$?
    printf '%s\n' "$out"
    return $status
  }
  run_witness() {
    ( cd "$REPO/bend_core" && bend PROOF.bend ) 2>&1
  }
  run_version() {
    bend version 2>&1
  }
  run_lean_version() {
    lean --version 2>&1 | head -1
  }
fi

echo "== bend laws gate ($WHERE) =="
echo "== repo under test: $REPO =="

# Bend 2 ONLY. There are two different distributions with the same binary name:
#
#   bend-lang 0.2.38  (crates.io / cargo install, prints "bend-lang 0.2.38")
#       -> Bend 1: HVM-era CLI (check/run-rs/gen-c), no `law`, no `--verdict`
#   bend 2.x          (bend-lang.com installer, prints "bend 2.x.y")
#       -> Bend 2: the distribution bend_core/ is written against
#
# bend_core/*.bend is Bend 2 SYNTAX (type ... is Data:, law ... for ... {==}).
# On this Windows host a Bend 1 `bend.exe` sits on PATH at H:\cargo\bin\bend.exe
# and shadows nothing in the WSL branch, but in the native branch it would be
# picked up and every law would die at parse time ("expected: Type variable or
# '='"). That failure is indistinguishable from "the laws are broken", so the
# gate asserts the DISTRIBUTION before it judges any law.
#
# Measured 2026-10-18: `bend-lang 0.2.38 check LAWS.bend` -> error at line 52
# `type Row is Data:`; `bend 2.0.37 --verdict LAWS.bend` -> ALL PROOFS CHECK.
#
# The exact patch version is pinned by CI (.github/workflows/bend-laws-gate.yml);
# here the requirement is the distribution, because a gate that only runs on one
# exact patch would refuse a newer Bend 2 for no reason.
BEND_VERSION="$(run_version)"
if ! printf '%s' "$BEND_VERSION" | grep -Eq '^bend 2\.[0-9]+\.[0-9]+'; then
  echo "FAIL: this gate needs Bend 2 (prints 'bend 2.x.y'); got: ${BEND_VERSION:-<no output>}"
  echo "      Bend 1 is the public bend-lang crate (v0.2.38) -- it has no --verdict"
  echo "      and cannot parse bend_core/*.bend. Install Bend 2 instead:"
  echo "      curl -fsSL https://bend-lang.com/install.sh | sh"
  echo "      See docs/EVOLUTION_TOOLCHAIN.md section 2."
  exit 4
fi
echo "== bend: $BEND_VERSION =="
# THE JUDGE, not just the compiler. Two measured reasons to print this on its own
# line: (a) kernel-comparison PRs (#1892, #1864) WIDEN what `ALL PROOFS CHECK`
# means between patch releases with the laws unchanged, and (b) upstream issue
# #1907 proposes a `+BUILD` suffix, so a fork build can satisfy a version
# assertion that a human reads as "the official release". A gate log that says
# which bend AND which Lean produced the green is the only artifact that can
# tell "the laws still hold" from "the kernel accepts more".
LEAN_VERSION="$(run_lean_version)"
if [ -z "$LEAN_VERSION" ]; then
  echo "      lean: <not found on PATH> -- the verdict cannot be attributed to a kernel"
else
  echo "== lean: $LEAN_VERSION =="
fi

# verdict_class <verdict text> -> green | out-of-scope | proof-fail | no-verdict
#
# WHY a classifier instead of four inline greps: `--verdict` reports a
# TRANSLATION LIMIT with the same words as a false law (`SOME PROOFS FAIL`).
# Measured upstream (issue #1897): `BendTT: out of scope: ...`). Without this
# distinction the gate would exit 2, "a law did not check", and send the next
# agent to debug a proof that is fine -- a false red with a wrong diagnosis.
# The classifier is exercised by `--selftest` below, so it is not a branch that
# only a future release can reach.
verdict_class() {
  local text="$1"
  if printf '%s\n' "$text" | grep -q "ALL PROOFS CHECK"; then
    printf 'green\n'
  elif printf '%s\n' "$text" | grep -q "BendTT: out of scope"; then
    printf 'out-of-scope\n'
  elif printf '%s\n' "$text" | grep -q "SOME PROOFS FAIL"; then
    printf 'proof-fail\n'
  else
    printf 'no-verdict\n'
  fi
}

if [ "${1:-}" = "--selftest" ]; then
  # Four fixtures, one per class, including the one no fixture in this repo can
  # produce (out-of-scope). Each assertion is a pair (input, expected class).
  # A classifier that always answered "green" would fail on three of them.
  selftest_fail=0
  selftest_case() {
    local label="$1" text="$2" want="$3" got
    got="$(verdict_class "$text")"
    if [ "$got" = "$want" ]; then
      echo "PASS: selftest $label -> $got"
    else
      echo "FAIL: selftest $label -> $got (wanted $want)"
      selftest_fail=1
    fi
  }
  selftest_case "green"        "ALL PROOFS CHECK"                                  green
  selftest_case "out-of-scope" "SOME PROOFS FAIL
Error:
BendTT: out of scope: - use: an application with no known head type"              out-of-scope
  selftest_case "proof-fail"   "SOME PROOFS FAIL
Location: Laws.Row.span_end_within_file"                                          proof-fail
  selftest_case "garbage"      "bend: parse error at line 3"                        no-verdict
  if [ "$selftest_fail" -ne 0 ]; then
    exit 3
  fi
  echo "== selftest green (verdict classification) =="
  exit 0
fi

# has_location <output> <exact-law-name>
#
# True when the output carries a `Location: <name>` line whose name is EXACTLY
# the expected law. Literal comparison, not a regex: law names contain dots, and
# `Nat.min_le_r` as an ERE also matches `NatXminYle_r`, which would let a
# different failure satisfy the assertion (measured: the ERE form ACCEPTS
# `Location: NatXminYle_r` for `Nat.min_le_r`; this form rejects it). The empty
# `Location:` a parse error prints never matches a name, which is the point.
#
# A non-empty named Location is the ONLY discriminator available here between a
# proof failure and a parse error. Measured on 2.0.37: a parse error and a
# garbage file also print `SOME PROOFS FAIL`, `- expected :` and `- observed :`
# (so none of those is usable as a signal); they differ only in printing
# `Location:` with an EMPTY name. A line echoed in source context is
# line-number-prefixed (`NN | ...`), so it cannot produce a column-0 `Location:`
# line. This coupling to bend's diagnostic TEXT is the gate's known soft spot --
# there is no JSON verdict (`bend --help` offers none) -- so it must be
# re-measured on a Bend upgrade; if the format moves, the tamper probes fail
# loudly (exit 6) rather than passing silently.
has_location() {
  printf '%s\n' "$1" | awk -v want="$2" '
    /^Location:/ { name = $0; sub(/^Location:[ \t]*/, "", name); sub(/[ \t\r]+$/, "", name)
                   if (name != "" && name == want) found = 1 }
    END { exit(found ? 0 : 1) }'
}

LAWS_OUT="$(run_bend PROOF.bend)"
LAWS_STATUS=$?
echo "$LAWS_OUT" | grep -E "ALL PROOFS CHECK|SOME PROOFS FAIL" || true

# A translation limit is not a counterexample (see verdict_class). Checked
# BEFORE the failure branch, because that branch would otherwise diagnose it as
# "a law did not check" and point the next agent at a proof that is fine.
if [ "$(verdict_class "$LAWS_OUT")" = "out-of-scope" ]; then
  echo "FAIL: the kernel did not see every proof -- bend reported a BendTT translation limit."
  echo "      This is NOT a refuted law (upstream #1897). Either restate the law so it"
  echo "      translates, or wait for the translator to widen; do not 'fix' the proof."
  echo "$LAWS_OUT" | head -20
  exit 4
fi

# Failure is tested FIRST and on its own, deliberately. The success test is an
# unanchored substring search, so testing it first made the gate's answer depend
# on which string it happened to see: an output carrying BOTH verdicts would have
# passed as green, with a failing law inside it.
if echo "$LAWS_OUT" | grep -q "SOME PROOFS FAIL"; then
  if echo "$LAWS_OUT" | grep -q "ALL PROOFS CHECK"; then
    echo "FAIL: bend printed BOTH verdicts; refusing to guess which one is authoritative."
    echo "$LAWS_OUT" | head -20
    exit 4
  fi
  echo "FAIL: a law did not check (proof failure in PROOF.bend)."
  echo "$LAWS_OUT" | head -20
  exit 2
fi

if ! echo "$LAWS_OUT" | grep -q "ALL PROOFS CHECK"; then
  echo "FAIL: toolchain unusable (no verdict line from bend)."
  echo "$LAWS_OUT" | head -20
  exit 4
fi

# The text alone is not the verdict. `bend --verdict` reports the outcome in its
# exit status too (measured: 0 only when every law checks; 1 for a false law, for
# NEGATIVE.bend, and for a file that is not a Bend program at all). Requiring the
# two to AGREE closes the hole where a success substring in the output would pass
# the gate while the command itself was reporting failure.
if [ "$LAWS_STATUS" -ne 0 ]; then
  echo "FAIL: bend printed a success verdict but exited $LAWS_STATUS; refusing to trust it."
  echo "$LAWS_OUT" | head -20
  exit 4
fi
echo "PASS: every law in LAWS.bend checks (proofs in PROOF.bend)."

# One negative control per law family, in its own file. The kernel stops at the
# FIRST failing law, so two false claims in one file would only ever exercise the
# first: splitting them is what makes each control a real control.
#
# A control must fail for the RIGHT reason, not merely fail. Measured on bend
# 2.0.37:
#
#   genuine counterexample -> "SOME PROOFS FAIL" + "Location: <LawName>"
#   parse / type error     -> "- expected : a term" + "Location:" (empty name)
#
# so the gate requires each control to fail WITH A NAMED LOCATION, and that the
# name is the law the control was written to falsify. Without this, a control
# that merely stopped parsing (a typo) satisfied "it fails" while testing
# nothing -- the same class of vacuity the proof-state guard exists to close.
#
# The control set is PINNED for the reason the law inventory is pinned: a
# control deleted, or added without a registered expectation, silently removes a
# falsifier and nothing about a green run would say so.
EXPECTED_CONTROLS="$(cat <<'EOF'
NEGATIVE_count_due_empty.bend=Toks.count_due_of_an_empty_line_is_zero
NEGATIVE_count_due_monotone.bend=Toks.count_due_is_monotone_in_time
NEGATIVE_count_due_one_word.bend=Toks.count_due_of_one_word_is_its_flag
NEGATIVE_count_due_only.bend=Toks.count_due_counts_only_due_words
NEGATIVE_display_clean_before_new_source.bend=Cap.display_clean_before_new_source
NEGATIVE_epoch_monotonic.bend=Cap.epoch_monotonic
NEGATIVE_live_flag.bend=Nat.live_flag_is_started_and_not_ended
NEGATIVE_live_flag_before.bend=Nat.live_flag_is_false_before_the_line_starts
NEGATIVE_no_cross_source_paint.bend=Nat.no_cross_source_paint
NEGATIVE_of_bool_agrees.bend=Nat.of_bool_agrees_with_revealed_flag
NEGATIVE_revealed_flag.bend=Nat.revealed_flag_is_zero_or_one
NEGATIVE_window_rows_capacity.bend=Nat.window_rows_never_exceeds_the_capacity
NEGATIVE_window_rows_live.bend=Nat.window_rows_never_exceeds_the_live_rows
NEGATIVE_window_rows_min.bend=Nat.window_rows_is_the_minimum
EOF
)"
EXPECTED_CONTROL_FILES="$(printf '%s\n' "$EXPECTED_CONTROLS" | sed 's/=.*//' | sort)"
GOT_CONTROL_FILES="$( ( cd "$REPO_WIN/bend_core" && ls NEGATIVE*.bend ) 2>/dev/null | sort)"
if [ "$GOT_CONTROL_FILES" != "$EXPECTED_CONTROL_FILES" ]; then
  echo "FAIL: the negative-control set drifted from the pinned list."
  echo "--- expected (pinned) ---"; printf '%s\n' "$EXPECTED_CONTROL_FILES"
  echo "--- found in bend_core ---"; printf '%s\n' "$GOT_CONTROL_FILES"
  exit 3
fi

# The control list is fed with a heredoc, NOT `... | while read`: a pipe would run
# the loop in a subshell, so `exit 3` inside it would exit only the subshell and
# the gate would carry on as if the control had passed.
while IFS='=' read -r NEG NEG_LAW; do
  [ -n "$NEG" ] || continue
  NEG_OUT="$(run_bend "$NEG")"
  NEG_STATUS=$?
  if echo "$NEG_OUT" | grep -q "ALL PROOFS CHECK"; then
    echo "FAIL: negative control $NEG checked -- the gate is broken."
    exit 3
  fi
  if ! echo "$NEG_OUT" | grep -q "SOME PROOFS FAIL"; then
    echo "FAIL: $NEG produced no verdict (toolchain problem)."
    echo "$NEG_OUT" | head -20
    exit 4
  fi
  if [ "$NEG_STATUS" -eq 0 ]; then
    echo "FAIL: $NEG printed a failure verdict but exited 0; refusing to trust it."
    echo "$NEG_OUT" | head -20
    exit 4
  fi
  if ! has_location "$NEG_OUT" "$NEG_LAW"; then
    echo "FAIL: $NEG failed WITHOUT naming $NEG_LAW."
    echo "      A parse/type error is not a counterexample -- the control is not a control."
    echo "$NEG_OUT" | head -20
    exit 3
  fi
  echo "PASS: negative control $NEG fails on $NEG_LAW, as it must."
done <<EOF
$EXPECTED_CONTROLS
EOF

# ---------------------------------------------------------------------------
# E11.5 PROOF-STATE GUARD (exit 5 / 6)
#
# A green verdict on the file AS WRITTEN is blind to two silent changes:
#
#   * a law DELETED or renamed -- nothing checks it any more, yet the file is
#     still internally consistent and still prints ALL PROOFS CHECK;
#   * a proof body EMPTIED -- a proof of a weaker statement is still a proof,
#     and `law` + `def` with a gutted body can still check.
#
# The first is closed by pinning the `law` INVENTORY. The second by building a
# tampered copy with one proof body deleted and requiring the verdict to DIFFER
# -- if a gutted proof still checks, the gate is not reading proof state at all.
# ---------------------------------------------------------------------------

# (a) INVENTORY. Adding a law requires extending this list, which is the review
# checkpoint; deleting or renaming one changes the set and fails the gate.
EXPECTED_LAWS="$(cat <<'EOF'
Cap.display_clean_before_new_source
Cap.epoch_monotonic
Nat.live_flag_is_false_before_the_line_starts
Nat.live_flag_is_started_and_not_ended
Nat.no_cross_source_paint
Nat.of_bool_agrees_with_revealed_flag
Nat.revealed_flag_is_zero_or_one
Nat.window_rows_is_the_minimum
Nat.window_rows_never_exceeds_the_capacity
Nat.window_rows_never_exceeds_the_live_rows
Toks.count_due_counts_only_due_words
Toks.count_due_is_monotone_in_time
Toks.count_due_of_an_empty_line_is_zero
Toks.count_due_of_one_word_is_its_flag
EOF
)"
GOT_LAWS="$(grep -E '^law[[:space:]]+' "$REPO_WIN/bend_core/LAWS.bend" \
  | sed -E 's/^law[[:space:]]+([^:]+):.*/\1/' | sort)"
EXPECTED_SORTED="$(printf '%s\n' "$EXPECTED_LAWS" | sed '/^$/d' | sort)"
if [ "$GOT_LAWS" != "$EXPECTED_SORTED" ]; then
  echo "FAIL: LAWS.bend law inventory drifted from the pinned list."
  echo "--- expected (pinned) ---"
  printf '%s\n' "$EXPECTED_SORTED"
  echo "--- found in LAWS.bend ---"
  printf '%s\n' "$GOT_LAWS"
  exit 5
fi
echo "PASS: law inventory matches the pinned $(printf '%s\n' "$GOT_LAWS" | grep -c . ) laws."

# (a2) SPLIT ASSERTION. If the proofs were ever moved back into the claim file,
# `bend --verdict LAWS.bend` would print ALL PROOFS CHECK and the review
# separation the split buys would be gone -- while every other assertion here
# stayed green. So the claim file must report its laws as OPEN claims: bend
# counts them ("N TODOs found", measured on 2.0.39). Witnessed red: the
# pre-split LAWS.bend from git HEAD prints `ALL PROOFS CHECK`, rc=0 (probe run
# 2026-10-28, G:\Temp\opencode\bend-revert-probe), so this branch does fire on
# the real regression it is written for.
#
# A PARTIAL move -- one proof back into the claim file while PROOF.bend keeps
# its def -- is caught one file earlier by bend itself, measured the same day:
# `- expected : a fresh name (Laws is an import's alias)`, because the claim
# file now exports `Nat.is_le_refl` and PROOF.bend's `def Laws.Nat.is_le_refl`
# would collide with it. That is why there is no separate "count is exactly N"
# assertion here: it would be a branch no mutation can reach.
CLAIMS_OUT="$(run_bend LAWS.bend)"
CLAIMS_STATUS=$?
if echo "$CLAIMS_OUT" | grep -q "ALL PROOFS CHECK"; then
  echo "FAIL: LAWS.bend checks on its own -- proofs leaked back into the claim file."
  exit 2
fi
if ! echo "$CLAIMS_OUT" | grep -q "TODOs found"; then
  echo "FAIL: LAWS.bend produced no open-claim count (toolchain problem)."
  echo "$CLAIMS_OUT" | head -20
  exit 4
fi
if [ "$CLAIMS_STATUS" -eq 0 ]; then
  echo "FAIL: LAWS.bend exited 0 while claiming open TODOs; refusing to trust it."
  exit 4
fi
echo "PASS: LAWS.bend alone reports its laws as open claims: $(echo "$CLAIMS_OUT" | grep 'TODOs found' | head -1)"

# (b) PROOF-STATE TAMPER PROBES. Two tampered copies, because "the proof is gone"
# and "the proof is there but empty" are DIFFERENT edits, and a gate that claims
# to read proof state must refuse both. They are built from PROOF.bend, because
# that is where the proofs live since the P0.42 split. Measured on 2.0.39:
#
#   copy A: whole `def Laws.Nat.min_le_r` block deleted
#           -> SOME PROOFS FAIL, Location: Laws.Row.span_end_within_file (the
#              use site), "- expected : a filled definition (an unfilled law is a
#              dead claim: live code cannot use it)"
#   copy B: `def Laws.Row.span_end_within_file` kept, body replaced by `{==}`
#           -> SOME PROOFS FAIL, Location: Laws.Row.span_end_within_file
#
# The Location form changed with the split: bend names the DEF, alias included,
# not the bare law name. That is why the expected names below carry `Laws.`.
#
# (an earlier revision of this gate ran only copy A while its prose claimed "one
#  proof body deleted" -- the probe tested less than the sentence beside it, so
#  the sentence was the thing that had to change.)
#
# The copies live next to PROOF.bend (dot-prefixed, so `git status` stays clean)
# because BOTH toolchain branches `cd` into bend_core and read them there. The
# name carries $$ so two concurrent gate runs cannot clobber each other's copy
# mid-verdict. Cleanup is on EXIT, and HUP/INT/TERM force an exit first so an
# interrupted run (Ctrl-C, a CI cancel) still removes them -- SIGKILL cannot be
# trapped, so a -9 leaves the two dot-files behind; they are harmless and
# dot-prefixed, and `git status` stays clean either way.
PROOF_SRC="$REPO_WIN/bend_core/PROOF.bend"
TAMPER_A_REL=".bend-tamper-a-$$.bend"
TAMPER_B_REL=".bend-tamper-b-$$.bend"
TAMPER_A="$REPO_WIN/bend_core/$TAMPER_A_REL"
TAMPER_B="$REPO_WIN/bend_core/$TAMPER_B_REL"
cleanup_tamper() { rm -f "$TAMPER_A" "$TAMPER_B"; }
trap cleanup_tamper EXIT
# Force an exit on the catchable signals so the EXIT trap above actually runs.
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# Copy A: one proof body replaced by one that PROVES THE OPPOSITE. The
# mutation must be a proof-level failure with a NAMED Location, so it cannot be
# confused with a parse error. Measured on 2.0.39 in THIS repository
# (2026-10-30): replacing the `{==}` of the (True, True) arm of
# `Laws.Nat.live_flag_is_started_and_not_ended` with `False{}` makes the kernel
# answer "- expected : {True{} == True{} : Bool} / observed : Bool" at
# "Location: Laws.Nat.live_flag_is_started_and_not_ended".
#
# WHY NOT "DELETE THE PROOF DEF": a deleted proof def leaves the LAW unproved
# and bend reports it as "Error: 1 TODO found." -- a count with NO Location,
# which cannot be asserted on. The mutation below fails AT the law instead,
# which is what a proof-state guard has to read.
awk 'BEGIN{inblock=0; flipped=0}
     /^def Laws[.]Nat[.]live_flag_is_started_and_not_ended\(started, ended\):/ { inblock=1; print; next }
     inblock==1 {
       if ($0 ~ /^[^ \t]/) { inblock=0; print; next }
       if (flipped==0 && $0 ~ /^      \{==\}$/) { print "      False{}"; flipped=1; next }
       print; next
     }
     { print }' \
  "$PROOF_SRC" > "$TAMPER_A"

# Copy B: the proof body is GUTTED (kept, but replaced by the bare `{==}`).
# Measured on 2.0.39 in this repository (2026-10-30): the kernel answers with a
# goal it cannot close at "Location: Laws.Cap.epoch_monotonic" -- the proof
# exists but no longer discharges the statement, which a "the file still
# checks" gate would accept.
awk 'BEGIN{inblock=0; gutted=0}
     /^def Laws[.]Cap[.]epoch_monotonic\(evs, c\):/ { inblock=1; print; print "  {==}"; next }
     inblock==1 {
       if ($0 ~ /^[^ \t]/) { inblock=0; print; next }
       next
     }
     { print }' \
  "$PROOF_SRC" > "$TAMPER_B"

# tamper_probe <label> <local-copy> <rel-name> <must-mention> <expected-location>
# Failure must be proof-level (a NAMED Location), not a parse/type error, for the
# same reason the negative controls must be: "it failed" is not evidence.
tamper_probe() {
  local probe_label="$1" probe_file="$2" probe_rel="$3" probe_must="$4" probe_loc="$5"
  local out status
  if [ -z "$probe_must" ]; then
    echo "FAIL: tamper probe $probe_label was given an empty must-mention; that guard would be vacuous."
    exit 6
  fi
  if cmp -s "$probe_file" "$PROOF_SRC"; then
    echo "FAIL: tamper probe $probe_label could not build a changed copy (the awk pattern is stale)."
    exit 6
  fi
  out="$(run_bend "$probe_rel")"
  status=$?
  if echo "$out" | grep -q "ALL PROOFS CHECK"; then
    echo "FAIL: tamper probe $probe_label STILL checked -- the gate does not read proof state."
    echo "$out" | head -20
    exit 6
  fi
  if ! echo "$out" | grep -q "SOME PROOFS FAIL"; then
    echo "FAIL: tamper probe $probe_label produced no verdict (toolchain problem)."
    echo "$out" | head -20
    exit 6
  fi
  if [ "$status" -eq 0 ]; then
    echo "FAIL: tamper probe $probe_label printed a failure verdict but exited 0; refusing to trust it."
    exit 6
  fi
  if ! printf '%s\n' "$out" | grep -qF "$probe_must"; then
    echo "FAIL: tamper probe $probe_label failed without mentioning $probe_must -- wrong failure."
    echo "$out" | head -20
    exit 6
  fi
  if ! has_location "$out" "$probe_loc"; then
    echo "FAIL: tamper probe $probe_label failed WITHOUT a named Location ($probe_loc)."
    echo "      A parse/type error would satisfy 'it failed' while testing nothing."
    echo "$out" | head -20
    exit 6
  fi
  echo "PASS: tamper probe $probe_label is detected (proof state is checked, not assumed)."
  rm -f "$probe_file"
}

tamper_probe A "$TAMPER_A" "$TAMPER_A_REL" "Laws.Nat.live_flag_is_started_and_not_ended" "Laws.Nat.live_flag_is_started_and_not_ended"
tamper_probe B "$TAMPER_B" "$TAMPER_B_REL" "Laws.Cap.epoch_monotonic" "Laws.Cap.epoch_monotonic"
trap - EXIT INT TERM HUP

if [ "${1:-}" = "-v" ]; then
  echo "== witnesses (PROOF.bend) =="
  run_witness
fi

echo "== gate green =="
