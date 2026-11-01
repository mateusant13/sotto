#!/usr/bin/env python3
"""THE CAPTION PUNCTUATION ORACLE -- a line does not end on a comma.

WHY THIS EXISTS (owner, 2026-10-21, verbatim):
    *"legenda que termina em vírgula"*

and, from the live box in the same session, the seam: `… enfim,.`

MECHANISM: the model emits a comma as the LAST token of a chunk while it is still
unsure whether the sentence continues. The line then closes -- on the `max_chars`
cap, on a silence, or on the model's own period arriving in the NEXT chunk -- and
the published text carries both marks: the comma from the chunk that ended and the
terminal from the chunk that began. Nothing here rewrites a word; it removes a
separator the adjacent mark has already overruled.

TWO CLAIMS ABOUT THE CODE AND ONE ABOUT THE TEXT:

  C1 `LineFormer.line()` tidies -- every partial goes through `tidy_line`, so the
     live box stops showing `,.` while the sentence is still growing.
  C2 `LineFormer._close()` FINALISES -- a closed line goes through `tidy_final`,
     which additionally drops a trailing `,` / `;` / `:`. A partial may end on a
     comma (a growing clause really is mid-sentence); a CLOSED line may not, and
     the closed line is the one the transcript keeps.
  C3 THE BEHAVIOUR, arm by arm, including the three things this must NOT do:
     never touch a lone comma, never touch an ellipsis, never add a character.

STRUCTURE IS CHECKED IN THE AST, NOT BY GREPPING A STRING: a docstring that says
"tidy" and a call that does it are different facts, and only the second one changes
what the owner reads.

FILES ONLY: lifts `tidy_line` / `tidy_final` out of `worker/sotto_worker.py` with
`ast` and drives them. No model, no audio device, no app -- so it belongs in a
battery. What the model DICTATES is not this gate's claim.

`--neg-arm` empties the `,.` entry of `LINE_TIDY_FIX` (the owner's own example) and
demands C3 go RED.
"""
from __future__ import annotations

import argparse
import ast
import io
import sys
import textwrap

WORKER = "worker/sotto_worker.py"
FUNCTIONS = ("tidy_line", "tidy_final")
CONSTANTS = ("LINE_TIDY_FIX", "LINE_TRAILING_JUNK")


def read_source(path=WORKER):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def lift(src):
    """The two pure functions and their tables, out of the real file."""
    tree = ast.parse(src)
    ns = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            exec(compile(textwrap.dedent(ast.get_source_segment(src, node)), node.name, "exec"), ns)
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(n in CONSTANTS for n in names):
                exec(compile(ast.get_source_segment(src, node), names[0], "exec"), ns)
    missing = [n for n in FUNCTIONS + CONSTANTS if n not in ns]
    if missing:
        raise SystemExit("not found in %s: %s" % (WORKER, ", ".join(missing)))
    return ns


def _method(src, name):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "LineFormer":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return item
    return None


def claim_line_tidies(src):
    fn = _method(src, "line")
    if fn is None:
        return False, "LineFormer.line() was not found"
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tidy_line":
            return True, "LineFormer.line() returns tidy_line(join_fragments(...))"
    return False, "LineFormer.line() does NOT call tidy_line -- partials still show the seam"


def claim_close_finalises(src):
    fn = _method(src, "_close")
    if fn is None:
        return False, "LineFormer._close() was not found"
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tidy_final":
            return True, "LineFormer._close() finalises through tidy_final()"
    return False, "LineFormer._close() does NOT call tidy_final -- closed lines keep the comma"


ARMS = (
    ("the owner's own seam", "final", "enfim,.", "enfim."),
    ("comma + ellipsis (char)", "final", "enfim,…", "enfim,…"),
    ("doubled comma", "partial", "a,,b", "a,b"),
    ("comma + question mark", "partial", "e entao,?", "e entao?"),
    ("closed line ends on a comma", "final", "isto e uma frase,", "isto e uma frase"),
    ("closed line ends on a semicolon", "final", "e depois;", "e depois"),
    ("a PARTIAL keeps its comma", "partial", "isto e uma frase,", "isto e uma frase,"),
    ("three dots are not an ellipsis to us", "partial", "espera...", "espera..."),
    ("a lone comma is left alone", "partial", "um, dois", "um, dois"),
    ("empty stays empty", "final", "", ""),
)


def claim_behaviour(ns):
    problems = []
    rows = []
    for name, mode, got_in, want in ARMS:
        got = ns["tidy_final"](got_in) if mode == "final" else ns["tidy_line"](got_in)
        ok = got == want
        rows.append((ok, name, got, want))
        if not ok:
            problems.append("%s: %r != %r" % (name, got, want))
    if problems:
        return False, " | ".join(problems)
    return True, "%d arm(s) hold, including the owner's `enfim,.` -> `enfim.`" % len(ARMS)


def run(src, label):
    ns = lift(src)
    rows = [
        ("C1", "LineFormer.line() tidies every partial", claim_line_tidies(src)),
        ("C2", "LineFormer._close() finalises the line", claim_close_finalises(src)),
        ("C3", "the punctuation arms hold", claim_behaviour(ns)),
    ]
    failed = 0
    print(label)
    for key, what, (ok, detail) in rows:
        print("  %s %s %-40s %s" % ("ok  " if ok else "FAIL", key, what, detail))
        if not ok:
            failed += 1
    print("")
    print("%d check(s), %d failed" % (len(rows), failed))
    print("VERDICT: %s" % ("PASS" if failed == 0 else "FAIL"))
    return failed


def mutate_drop_the_seam(src):
    """Take `,.` out of the table: the owner's example comes back.

    Anchored WITHOUT the line ending on purpose: this file is CRLF, and a mutation
    that only matches LF would report "anchor spent" against a file that is fine
    (measured: the first version of this neg-arm did exactly that).
    """
    marker = '",.": ".",'
    if marker not in src:
        raise SystemExit("the `,.` entry was not found -- the mutation anchor is spent")
    return src.replace(marker, "", 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description="does a caption line end on a comma?")
    ap.add_argument("--file", default=WORKER)
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    src = read_source(args.file)
    if not args.neg_arm:
        print("CAPTION PUNCTUATION ORACLE -- PRISTINE")
        return 0 if run(src, "") == 0 else 1

    print("CAPTION PUNCTUATION ORACLE -- CONTROL")
    ctrl = run(src, "  CONTROL (the file as it stands) must be GREEN")
    print("")
    broken = mutate_drop_the_seam(src)
    if broken == src:
        print("  MUTATION DID NOT APPLY -- the anchor is spent")
        return 1
    mut = run(broken, "  M1 the `,.` rule removed (his seam restored) must be RED")
    ok = (ctrl == 0 and mut > 0)
    print("")
    print("NEG-ARM VERDICT: %s -- control %s, mutant %s"
          % ("PASS" if ok else "FAIL",
             "GREEN" if ctrl == 0 else "RED",
             "RED" if mut > 0 else "GREEN (INERT MUTANT)"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
