#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sotto - VERDICT GATE: `captions-emitted` must never be emitted with zero captions.

THE DEFECT CLASS THIS GATE EXISTS FOR.
`worker/sotto_worker.py` decides its closing verdict with a chain of `elif`s and
a bare `else: verdict = "captions-emitted"`. Every no-audio word in that chain is
guarded on its own counters (`blocks == 0`, `nonzero_blocks == 0`,
`resampled_samples == 0`, `chunks == 0`, the music gate, the VAD gate) - and the
FINAL word was guarded by NOTHING. So the one state a caller most needs named -
the tap is ALIVE, chunks reached the encoder, and NOT ONE caption was ever
emitted - fell through every branch into `captions-emitted`: a claim about
captions that do not exist. A `done` carrying it is painted by the shells as a
HEALTHY finish, and the exit code is 0. The audit
(`docs/audit/auditoria-completa-20261007.md`) found this class exactly: a word
emitted without the fact it names.

WHAT IT EXECUTES, never re-implements.
It imports `worker.sotto_worker` (guarded on `__main__`, so `main()` is NOT run)
and drives the REAL `decide_verdict(counters, outcome, ran_but_silent)` - the
contract the sibling worker lane is landing. The arms:

  (a) `captions > 0`                      -> `captions-emitted`
  (b) `captions == 0`, tap ALIVE, and NO no-audio evidence (blocks > 0,
      nonzero_blocks > 0, resampled_samples > 0, chunks > 0, the music gate did
      NOT withhold every chunk, the VAD gated nothing, no silent device, no
      exhausted ladder) -> NOT `captions-emitted`. `want` is printed as "not
      captions-emitted": this gate refuses to invent the new word for that state.
  (c) every PRE-EXISTING no-audio verdict word is still produced BY ITS OWN
      COUNTERS. The predicates are COPIED from `worker/sotto_worker.py` (each
      arm prints the source line its word lives on, and a word that has vanished
      from the source is a SETUP ERROR, never a pass) - nothing is invented here.
  (d) the wiring: `main()` actually CALLS `decide_verdict`. A decision function
      the pipeline never calls fixes nothing, and a gate that cannot say so is
      the same defect class one level up.

   cmd /c "python _main\\verdict-gate.py > _main\\_lane6-verdict.log 2>&1"
   cmd /c "python _main\\verdict-gate.py --control-unguard-captions-zero ..."
       NEGATIVE CONTROL, both colours in ONE command: a COPY of
       `worker/sotto_worker.py` (`_main/_lane6-worker-copy.py`) with ONLY the
       `captions == 0` branch removed - the pre-F3 chain, where the fall-through
       announces captions it never emitted. The gate must go RED, on arm (b)
       alone. Exits 0 only when the control really went RED. The copy is deleted
       before exit.

Exit codes: 0 every arm holds (or the control behaved as expected) | 1 an arm
does not hold | 2 setup error (the contract is absent, the module has no
`__main__` guard, the arm table does not cover a counter the predicate reads, or
the vocabulary has been renamed). No window, no audio, no device: the module is
imported and one pure function is called; nothing else runs.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import io
import os
import re
import sys
import textwrap
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(REPO, "worker", "sotto_worker.py")
COPY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lane6-worker-copy.py")
CONTRACT = "def decide_verdict(counters, outcome, ran_but_silent) -> str"

# ---------------------------------------------------------------------------
# The arm inputs. COPIES of the shipped predicates, keyed by the word they
# produce. `outcome` values are the real ones the ladder sets ("all-flat",
# "open-failed", "run-ended", "flat", "explicit-flat"); the chain tests only
# `outcome in ("all-flat", "open-failed")`, so "run-ended" is the neutral choice.
# ---------------------------------------------------------------------------
HEALTHY = {
    "blocks": 10,
    "nonzero_blocks": 10,
    "block_samples": 16000,
    "resampled_samples": 16000,
    "chunks": 5,
    "captions": 3,
    # The batch engine's counter (`worker/sotto_worker.py` sums it with `captions`
    # into `emitted`). 0 is the SHIPPED value: with the light path off it is always
    # 0, so every arm that does not name it below behaves exactly as it did before
    # the key existed.
    "redux_captions": 0,
    "peak": 0.1,
    "queue_drops": 0,
    "music_gated_chunks": 0,
    "vad_gated_chunks": 0,
}

NOT_CAPTIONS_EMITTED = "<not captions-emitted>"

ARMS = [
    dict(
        name="a  captions > 0",
        counters={"captions": 3},
        outcome="run-ended",
        ran_but_silent=False,
        want="captions-emitted",
        src_word="captions-emitted",
    ),
    dict(
        name="b  captions == 0, tap ALIVE, no no-audio evidence",
        counters={"captions": 0, "music_gated_chunks": 0, "vad_gated_chunks": 0},
        outcome="run-ended",
        ran_but_silent=False,
        want=NOT_CAPTIONS_EMITTED,
        src_word=None,
    ),
    dict(
        name="c1 ran_but_silent (a silent device, measured) - tested FIRST, before the ladder outcome",
        counters={"blocks": 214, "nonzero_blocks": 214, "resampled_samples": 16000, "chunks": 5, "captions": 0},
        outcome="all-flat",
        ran_but_silent=True,
        want="silent-device",
        src_word="silent-device",
    ),
    dict(
        name="c2 outcome in (all-flat, open-failed) - the weaker ladder statement",
        counters={"blocks": 0, "nonzero_blocks": 0, "resampled_samples": 0, "chunks": 0, "captions": 0},
        outcome="all-flat",
        ran_but_silent=False,
        want="all-candidate-taps-flat",
        src_word="all-candidate-taps-flat",
    ),
    dict(
        name="c3 counters['blocks'] == 0",
        counters={"blocks": 0, "nonzero_blocks": 0, "resampled_samples": 0, "chunks": 0, "captions": 0},
        outcome="run-ended",
        ran_but_silent=False,
        want="no-callback-blocks",
        src_word="no-callback-blocks",
    ),
    dict(
        name="c4 counters['nonzero_blocks'] == 0",
        counters={"blocks": 10, "nonzero_blocks": 0, "resampled_samples": 0, "chunks": 0, "captions": 0},
        outcome="run-ended",
        ran_but_silent=False,
        want="silent-capture",
        src_word="silent-capture",
    ),
    dict(
        name="c5 counters['resampled_samples'] == 0",
        counters={"blocks": 10, "nonzero_blocks": 10, "resampled_samples": 0, "chunks": 0, "captions": 0},
        outcome="run-ended",
        ran_but_silent=False,
        want="resample-produced-nothing",
        src_word="resample-produced-nothing",
    ),
    dict(
        name="c6 counters['chunks'] == 0",
        counters={"blocks": 10, "nonzero_blocks": 10, "resampled_samples": 16000, "chunks": 0, "captions": 0},
        outcome="run-ended",
        ran_but_silent=False,
        want="buffer-never-reached-chunk-size",
        src_word="buffer-never-reached-chunk-size",
    ),
    dict(
        name="c7 captions == 0 AND chunks > 0 AND music_gated >= chunks",
        counters={"blocks": 10, "nonzero_blocks": 10, "resampled_samples": 16000, "chunks": 5, "captions": 0,
                  "music_gated_chunks": 5, "vad_gated_chunks": 0},
        outcome="run-ended",
        ran_but_silent=False,
        want="captions-all-music-gated",
        src_word="captions-all-music-gated",
    ),
    dict(
        name="c8 captions == 0 AND vad_gated_chunks > 0",
        counters={"blocks": 10, "nonzero_blocks": 10, "resampled_samples": 16000, "chunks": 5, "captions": 0,
                  "music_gated_chunks": 0, "vad_gated_chunks": 3},
        outcome="run-ended",
        ran_but_silent=False,
        want="captured-signal-has-no-speech",
        src_word="captured-signal-has-no-speech",
    ),
    # ---------------------------------------------------------------------
    # THE BATCH ENGINE'S COUNTER (`redux_captions`) — added 2026-10-08 with the
    # light path. It has NO verdict word of its own and must never get one: it is
    # only SUMMED into `emitted = counters["captions"] + counters["redux_captions"]`
    # (sotto_worker.py, `emitted = …` / `elif emitted <= 0:` / the music and chunk
    # predications' `and emitted == 0`). So it is not a counter to "provide" — it is
    # an INPUT to three existing predicates, and the two arms below are the pair
    # that shows it: d1 alone would only prove the sum is read, d2 proves the sum
    # still goes the OTHER way, so neither arm is a gate that can only say yes.
    # The gate also REFUSES to let a future revision invent a word for it (see
    # `redux_word_lines` in `analyse`).
    # ---------------------------------------------------------------------
    dict(
        name="d1 redux_captions > 0 alone, chunks == 0 (the light path)",
        # The app comes up HIDDEN, so a run can spend its whole life on the batch
        # path and cut not one 560 ms chunk. Every no-audio counter is non-zero
        # here (the tap was alive); only the CHUNK counter is 0, and with
        # `emitted == 0` that alone means `buffer-never-reached-chunk-size`.
        counters={"blocks": 214, "nonzero_blocks": 214, "resampled_samples": 16000, "chunks": 0,
                  "captions": 0, "redux_captions": 4,
                  "music_gated_chunks": 0, "vad_gated_chunks": 0},
        outcome="run-ended",
        ran_but_silent=False,
        want="captions-emitted",
        src_word="captions-emitted",
    ),
    dict(
        name="d2 chunks == 0 AND redux_captions == 0 (the same input, nothing emitted)",
        # d1's exact arm with ONE counter moved: `redux_captions` 4 -> 0. The word
        # must go back to naming the measured fact, which is what makes d1's
        # `captions-emitted` a reading of the counter and not a fall-through.
        counters={"blocks": 214, "nonzero_blocks": 214, "resampled_samples": 16000, "chunks": 0,
                  "captions": 0, "redux_captions": 0,
                  "music_gated_chunks": 0, "vad_gated_chunks": 0},
        outcome="run-ended",
        ran_but_silent=False,
        want="buffer-never-reached-chunk-size",
        src_word="buffer-never-reached-chunk-size",
    ),
    dict(
        name="d3 ran_but_silent=True while redux_captions > 0 (the device word is tested FIRST)",
        # The ORDER is the contract: a silent device is the MEASURED,
        # device-attributable fact, and the exit code is built from it
        # (`return 3 if ran_but_silent else 0`), so a batch caption arriving during
        # an otherwise silent run must not talk the run out of naming the device.
        counters={"blocks": 214, "nonzero_blocks": 214, "resampled_samples": 16000, "chunks": 0,
                  "captions": 0, "redux_captions": 4,
                  "music_gated_chunks": 0, "vad_gated_chunks": 0},
        outcome="all-flat",
        ran_but_silent=True,
        want="silent-device",
        src_word="silent-device",
    ),
]


class SetupError(Exception):
    """The contract this gate is written against is not there. Never a pass."""


def code_only(fsrc: str) -> str:
    """The function's CODE, without its docstring or its comments.

    The docstring of `decide_verdict` NAMES every counter it reads (deliberately),
    so a scan that included it would report reads that are only prose - it would
    also inject an `asr` stub for a mention of `asr.labels` in a sentence. The
    docstring is located through the AST (not by string search: `getdoc` dedents,
    so the text no longer matches the source), then comments are removed.
    """
    text = textwrap.dedent(fsrc)
    try:
        ftree = ast.parse(text)
        head = ftree.body[0]
        stmts = getattr(head, "body", [])
        if stmts and isinstance(stmts[0], ast.Expr) and isinstance(stmts[0].value, ast.Constant) \
                and isinstance(stmts[0].value.value, str):
            lines = text.splitlines()
            del lines[stmts[0].lineno - 1: stmts[0].end_lineno]
            text = "\n".join(lines)
    except (SyntaxError, IndexError):
        pass
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def analyse(worker_path: str, module_name: str, as_package: bool, label: str):
    """Everything the arms need, or a SetupError. Never runs main()."""
    if not os.path.isfile(worker_path):
        raise SetupError("SETUP ERROR: %s does not exist" % worker_path)
    with io.open(worker_path, encoding="utf-8") as fh:
        src = fh.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        raise SetupError(
            "SETUP ERROR: %s does not parse (%s) - the worker lane may be mid-edit, and a gate must not "
            "read a green from a file it cannot parse" % (worker_path, exc)
        )

    fn = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "decide_verdict":
            fn = node
            break
    if fn is None:
        top = sorted({n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))})
        raise SetupError(
            "SETUP ERROR: decide_verdict absent in worker/sotto_worker.py\n"
            "  file actually read: %s\n"
            "  looked for: %s\n"
            "  module-level functions present : %s\n"
            "  this gate drives the REAL predicate and refuses to re-implement it: a green here\n"
            "  without the function would be exactly the false green this lane removes."
            % (worker_path, CONTRACT, ", ".join(top))
        )

    guarded = False
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        t = node.test
        if (
            isinstance(t, ast.Compare)
            and isinstance(t.left, ast.Name)
            and t.left.id == "__name__"
            and len(t.comparators) == 1
            and isinstance(t.comparators[0], ast.Constant)
            and t.comparators[0].value == "__main__"
        ):
            guarded = True
            break
    if not guarded:
        raise SetupError(
            'SETUP ERROR: %s has no `if __name__ == "__main__"` guard - importing it in-process would run '
            "the pipeline, which this gate must never do" % worker_path
        )

    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    captured = io.StringIO()
    real_stdout = sys.stdout
    try:
        sys.stdout = captured
        if as_package:
            mod = importlib.import_module("worker.sotto_worker")
        else:
            spec = importlib.util.spec_from_file_location(module_name, worker_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001 - any import fault is a setup error here
        raise SetupError("SETUP ERROR: cannot import %s without running main(): %r" % (worker_path, exc))
    finally:
        sys.stdout = real_stdout
    leaked = captured.getvalue()
    if leaked.strip():
        raise SetupError(
            "SETUP ERROR: importing %s wrote %d byte(s) to stdout - the __main__ guard did not hold, so this "
            "import was a RUN:\n%s" % (worker_path, len(leaked), leaked[:2000])
        )

    func = getattr(mod, "decide_verdict", None)
    if func is None:
        raise SetupError(
            "SETUP ERROR: decide_verdict is in %s but is not importable from the module object - stale bytecode "
            "or a nested definition" % worker_path
        )
    sig = str(inspect.signature(func))
    fsrc = inspect.getsource(func)
    body = code_only(fsrc)
    asr_attrs = sorted(set(re.findall(r"\basr\.(\w+)", body)))
    counter_keys = sorted(
        set(re.findall(r"counters\[[\"'](\w+)[\"']\]", body))
        | set(re.findall(r"counters\.get\(\s*[\"'](\w+)[\"']", body))
    )

    word_lines: dict[str, list[int]] = {}
    for m in re.finditer(r"^\s*verdict\s*=\s*[\"']([a-z0-9-]+)[\"']", src, re.M):
        word_lines.setdefault(m.group(1), []).append(src[: m.start()].count("\n") + 1)

    call_lines = [
        i + 1
        for i, line in enumerate(src.splitlines())
        if re.search(r"\bdecide_verdict\s*\(", line) and not line.strip().startswith("def ")
    ]
    call_sites = [ln for ln in call_lines if ln > (fn.end_lineno or fn.lineno)]

    print("--- %s ---" % label)
    print("worker   : %s%s" % (os.path.relpath(worker_path, REPO), "" if as_package else "  (a COPY)"))
    print("import   : %s, main() NOT run (%s: __main__ guard present, 0 bytes on stdout)"
          % ("worker.sotto_worker" if as_package else "spec_from_file_location", os.path.basename(worker_path)))
    print("contract : %s" % CONTRACT)
    print("real sig : decide_verdict%s" % sig)
    print("reads    : counters[...] = %s" % (counter_keys or "(none)"))
    print("           asr.<attr>    = %s" % (asr_attrs or "(none)"))

    missing = [k for k in counter_keys if k not in HEALTHY]
    if missing:
        raise SetupError(
            "SETUP ERROR: decide_verdict reads counters[%s], which this gate's arm table does not provide.\n"
            "  Extend HEALTHY in %s with those keys (and give each arm a value realistic for it) - an arm that\n"
            "  cannot supply an input the predicate reads is not evidence."
            % (", ".join(repr(m) for m in missing), os.path.basename(__file__))
        )

    words_needed = sorted({a["want"] for a in ARMS if a["want"] != NOT_CAPTIONS_EMITTED} | {"captions-emitted"})
    missing_words = [w for w in words_needed if w not in word_lines]
    if missing_words:
        raise SetupError(
            "SETUP ERROR: these verdict words are COPIED from %s by this gate's arm table and are no longer\n"
            "  assigned there: %s\n  words found: %s"
            % (os.path.basename(worker_path), ", ".join(missing_words), word_lines)
        )

    # `redux_captions` IS COUNTED, NOT NAMED — and this is the check that keeps
    # that a measured fact rather than an assumption. The counter has no word of
    # its own; it is an input to the SHARED predicates (`emitted`). If a future
    # revision ever makes a verdict word rest on it ALONE, that word is a word this
    # gate's arm table has no arm for, and the arms above would be proving a table
    # the function no longer follows. Fail closed: extension must be stated, never
    # inherited.
    redux_word_lines = sorted(
        ln for ln, text in enumerate(src.splitlines(), 1)
        if re.search(r"^\s*verdict\s*=\s*[\"']", text)
        and "redux_captions" in text and "captions-emitted" not in text
    )
    if redux_word_lines:
        raise SetupError(
            "SETUP ERROR: %s now assigns a verdict word FROM `redux_captions` alone (line(s) %s).\n"
            "  This gate's arm table has no arm for that word, and it must not inherit one: give the word an\n"
            "  arm of its own in ARMS (both colours) before reading any green here."
            % (os.path.basename(worker_path), ", ".join(str(n) for n in redux_word_lines))
        )

    # NO ARM INPUT MAY BE A KEY THE FUNCTION DOES NOT READ. An arm whose input key
    # was renamed upstream would still PASS — silently, because the function would
    # read its default 0 and the arm would be asserting a value it never set. The
    # arm that would catch it is the arm itself, so the check belongs here: an
    # unread input key is a SETUP ERROR, never a green.
    named = sorted({k for a in ARMS for k in a["counters"]})
    unread = [k for k in named if k not in counter_keys]
    if unread:
        raise SetupError(
            "SETUP ERROR: this gate's arm table drives counters[%s], which decide_verdict never READS.\n"
            "  counter keys the predicate really reads: %s\n"
            "  Either the key was renamed upstream (then the arm asserting it is proving nothing) or the arm\n"
            "  table is wrong. An arm that cannot supply an input the predicate reads is not evidence."
            % (", ".join(repr(m) for m in unread), ", ".join(counter_keys) or "(none)")
        )

    stub_injected = False
    asr_obj = getattr(mod, "asr", None)
    if asr_attrs and asr_obj is None:
        asr_obj = types.SimpleNamespace()
        setattr(mod, "asr", asr_obj)
        stub_injected = True
    if asr_attrs:
        print(
            "NOTE     : decide_verdict reads asr.%s: %s"
            % (
                ", ".join(asr_attrs),
                "a stub was injected as the module-global `asr` (the real one is a local in main()) - the stub's "
                "values are what the arms below drive." if stub_injected
                else "the module-global `asr` was set per arm.",
            )
        )

    print("copied predicates, and the source line each word lives on:")
    for a in ARMS:
        if a["src_word"]:
            print("  %-24s <- %s:%s"
                  % (a["src_word"], os.path.basename(worker_path), ",".join(str(n) for n in word_lines[a["src_word"]])))

    results = []
    print("\n--- arms ---")
    for a in ARMS:
        counters = dict(HEALTHY)
        counters.update(a["counters"])
        for attr in asr_attrs:
            value = a["counters"].get(attr, HEALTHY.get(attr, 0))
            if asr_obj is not None:
                setattr(asr_obj, attr, value)
            counters.setdefault(attr, value)
        try:
            real = func(counters, a["outcome"], a["ran_but_silent"])
        except Exception as exc:  # noqa: BLE001
            print("[FAIL] %s" % a["name"])
            print("       decide_verdict raised %r on counters=%s outcome=%r ran_but_silent=%r"
                  % (exc, counters, a["outcome"], a["ran_but_silent"]))
            results.append(False)
            continue
        if a["want"] == NOT_CAPTIONS_EMITTED:
            ok = real != "captions-emitted"
            want_display = '"not captions-emitted" (this gate does not invent the new word)'
        else:
            ok = real == a["want"]
            want_display = repr(a["want"])
        results.append(ok)
        print("[%s] %s" % ("PASS" if ok else "FAIL", a["name"]))
        print("       real = %r" % (real,))
        print("       want = %s" % want_display)
        if not ok and a["want"] == NOT_CAPTIONS_EMITTED:
            print("       ^ THE DEFECT: captions == 0 and the tap is ALIVE, yet the run announces it emitted captions.")

    print("\n--- the wiring: does the pipeline actually call it? ---")
    ok_wired = bool(call_sites)
    results.append(ok_wired)
    print("[%s] main() calls decide_verdict" % ("PASS" if ok_wired else "FAIL"))
    print("       real = %s" % (("call site line(s) %s" % call_sites) if ok_wired else "DECIDE_VERDICT IS NEVER CALLED"))
    print("       want = a call site outside the definition")
    if not ok_wired:
        print("       All definition-site line(s): %s - a decision nobody calls changes no verdict." % call_lines)

    real_verdict = "GREEN" if all(results) else "RED"
    print("RESULT (%s): %s - %d/%d arm(s)" % (label, real_verdict, sum(1 for r in results if r), len(results)))
    return all(results), results


def unguarded_copy() -> str:
    """A COPY of the worker with the `captions == 0` guard NEUTRALISED.

    WHAT THE CONTROL IS, and what it is not. The control must be "the pre-F3
    chain: the fall-through announces captions it never emitted", and it must
    still be a file that PARSES — the gate imports it and calls the real
    `decide_verdict` out of it.

    It used to DELETE the guard block by regex, and that regex was written
    against a spelling the worker has since left behind. Measured 2026-10-08:
    `python _main\\verdict-gate.py --control-unguard-captions-zero` printed
    `SETUP ERROR: the control arm needs the 'elif counters.get("captions", 0) == 0:
    ... verdict = "captions-zero"' block ...; it is not there` and exited 2 — the
    block is now `elif emitted <= 0:` (the batch engine's counter joined `captions`
    into `emitted`, and the predicate was deliberately widened from `== 0` to
    `<= 0`). A control that misses its anchor does not report "the gate is fine";
    it reports a setup error, which is the honest outcome — but it also means the
    negative half of this gate had silently stopped running.

    Neutralising beats deleting for three reasons: it cannot produce a file whose
    INDENTATION does not parse (deleting a branch leaves the following `else:`
    dangling under a `for`/`if` that may not tolerate it), it touches exactly ONE
    line so the control cannot drift away from "only this guard changed", and the
    anchor is the GUARD ITSELF rather than its body. The copy still ASSIGNS
    `verdict = "captions-zero"`; it just makes that branch unreachable, which is
    precisely the pre-F3 shape: nothing catches `captions == 0` and the `else:`
    below announces `captions-emitted`.
    """
    with io.open(WORKER, encoding="utf-8") as fh:
        src = fh.read()
    pattern = re.compile(r"^(    elif )emitted <= 0:$", re.M)
    m = pattern.search(src)
    if not m:
        raise SetupError(
            "SETUP ERROR: the control arm needs the `elif emitted <= 0:` guard branch in "
            "worker/sotto_worker.py to neutralise, and it is not there (the predicate has been\n"
            "  renamed or refactored again). Re-anchor this control on the guard itself before\n"
            "  reading any green from the control half of this gate."
        )
    with io.open(COPY, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src[: m.start()] + "    elif False:  # CONTROL: the captions == 0 guard neutralised\n"
                 + src[m.end():])
    return COPY


def main() -> int:
    control = "--control-unguard-captions-zero" in sys.argv[1:]
    target = WORKER
    as_package = True
    label = "worker/sotto_worker.py (as shipped)"
    if "--worker" in sys.argv[1:]:
        i = sys.argv.index("--worker")
        if i + 1 < len(sys.argv):
            target = os.path.abspath(sys.argv[i + 1])
            as_package = False
            label = "%s (--worker override)" % os.path.relpath(target, REPO)
    try:
        ok, results = analyse(target, "_lane6_worker_override", as_package, label)
    except SetupError as exc:
        print(str(exc))
        return 2

    if not control:
        print("\nRESULT: %s" % ("GREEN" if ok else "RED"))
        return 0 if ok else 1

    print("")
    try:
        path = unguarded_copy()
        print("control  : %s - a COPY of worker/sotto_worker.py with ONLY the `captions == 0` branch removed"
              % os.path.relpath(path, REPO))
        print("           (the pre-F3 chain: the fall-through announced captions it never emitted)")
        print("")
        cok, _ = analyse(path, "_lane6_worker_copy", False, "the unguarded COPY (control)")
    except SetupError as exc:
        print(str(exc))
        return 2
    finally:
        try:
            if os.path.isfile(COPY):
                os.remove(COPY)
        except OSError:
            pass

    print("\nCONTROL-ARM (only the `captions == 0` branch removed, nothing else)")
    print("  verdict real = %s" % ("GREEN" if cok else "RED"))
    print("  verdict want = RED")
    passed = not cok
    print("  CONTROL %s - %s" % ("PASS" if passed else "FAIL",
                                 "arm (b) fails on the copy exactly as it should"
                                 if passed else "THE GATE STAYED GREEN WITH `captions-emitted` UNGUARDED"))
    print("\nRESULT: %s (control satisfied: gate RED on the unguarded copy, gate %s on the shipped worker)"
          % ("GREEN" if passed else "RED", "GREEN" if ok else "RED"))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
