#!/usr/bin/env python3
"""measurement-flags-oracle -- UMA tabela de flags de medicao, e ela e' a unica.

THE DEFECT THIS EXISTS FOR (measured 2026-11-12, `app/webview/sotto_webview.py`).

A launch that only MEASURES must not behave like the app: it must not take the
owner's `Local\\SottoShell` mutex, must not load 1,9 GB of model, must not paint
a caption on his screen, and must not arm Alt+C. That rule had FIVE owners, each
a hand-written copy of one list:

  1. `MEASUREMENT_FLAGS`      (module)        -- 8 entries, no `--probe-v2`
  2. `_measurement_flag`      (inline branch) -- table 1 PLUS a `probe_v2` special case
  3. `_MEASUREMENT_LOCK_FLAGS`(module)        -- 6 entries, `--probe-v2`, no `probe_*`
  4. `SottoShell.MEASUREMENT_FLAGS` (class)   -- 8 entries, no `--probe-v2`
  5. the `elif` chain in `main()`             -- 5 entries, and it is the one that DECIDES

The chain is what took the lock, and it did not know `--exit-after`,
`--probe-stats`, `--probe-outside-click` or `--probe-edit-mode`. Two outcomes,
both measured as failures the repo has paid for before:

  * owner's app up   -> the probe is refused by the APP'S mutex, logs
                        "Sotto is already running", and `return 0` -- a
                        measurement that measured nothing, answering SUCCESS;
  * owner's app down -> the probe owns the app's mutex, `args.no_hotkey` is never
                        coerced, and it arms Alt+C on his desktop -- the
                        `HOTKEY_UNAVAILABLE alert=messagebox` wedge recorded in
                        the shell's own comment as cured on 2026-10-11.

WHAT IT MEASURES (each a separate arm; each fails on its own):
  A1 the one table exists at module level and its shape is (attr, '--label');
  A2 every label in the table has a matching `parser.add_argument('--label')`;
  A3 every argparse flag of the measurement FAMILY is in the table -- the arm
     that catches "a new probe flag was added and nobody told the table";
  A4 `measurement_lock_name` builds the label from `MEASUREMENT_FLAGS` and the
     second table is gone;
  A5 `SottoShell` carries no copy, and `_is_measurement_run` delegates;
  A6 `main()` decides the lock with `_measurement_flag(args)` and no attribute
     `elif` chain is back;
  A7 `_measurement_flag` has no inline special case;
  A8 the REAL function still answers: `probe_stats=True` -> '--probe-stats',
     `exit_after=25.0` -> '--exit-after', all-off -> None (executed, not read).

  --neg-arm plants FOUR mutations and requires each to be caught by ITS OWN arm:
  M1 drop `probe_stats` from the table (A3), M2 restore an `elif args.dump_dom`
  chain (A6), M3 give `_is_measurement_run` its own list (A5), M4 add a new
  `--probe-*` argument the table does not know (A3).

NO LAUNCH. This reads and executes pure functions only: no window, no audio
device, no thread, no model.
"""
# NO-BUG: o defeito e' uma MEDICAO comportar-se como a app (mutex, 1,9 GB de modelo, pintura na tela dele) com a regra em CINCO donos, medido 2026-11-12; nao e' bug do ledger

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")

FAMILY = re.compile(
    r"^(dump_dom|selftest|memory|no_hotkey|exit_after|probe_[a-z0-9_]+)$")
SECOND_TABLE = "_MEASUREMENT_LOCK_FLAGS"


def source() -> str:
    with open(SHELL, encoding="utf-8") as handle:
        return handle.read()


def module_function(tree, name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def class_node(tree, name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def table_pairs(tree):
    """[(attr, label)] read from the module-level MEASUREMENT_FLAGS tuple."""
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "MEASUREMENT_FLAGS"
                        for t in node.targets)):
            if not isinstance(node.value, ast.Tuple):
                return None
            pairs = []
            for elt in node.value.elts:
                if not (isinstance(elt, ast.Tuple) and len(elt.elts) == 2):
                    return None
                attr, label = elt.elts
                if not (isinstance(attr, ast.Constant) and isinstance(label, ast.Constant)):
                    return None
                pairs.append((attr.value, label.value))
            return pairs
    return None


def argparse_flags(tree):
    """Every `parser.add_argument('--name' ...)` option string in the file."""
    flags = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "add_argument"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                    and arg.value.startswith("--"):
                flags[arg.value] = True
    return flags


def exempt_pairs(tree):
    """[(attr, label)] from the module-level MEASUREMENT_EXEMPT tuple."""
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "MEASUREMENT_EXEMPT"
                        for t in node.targets)):
            if not isinstance(node.value, ast.Tuple):
                return None
            pairs = []
            for elt in node.value.elts:
                if not (isinstance(elt, ast.Tuple) and len(elt.elts) == 2):
                    return None
                attr, label = elt.elts
                if not (isinstance(attr, ast.Constant) and isinstance(label, ast.Constant)):
                    return None
                pairs.append((attr.value, label.value))
            return pairs
    return None


def second_table_bindings(tree):
    """Lines where `_MEASUREMENT_LOCK_FLAGS` is ASSIGNED (a comment cannot bind)."""
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if getattr(target, "id", None) == SECOND_TABLE:
                lines.append(getattr(node, "lineno", 0))
            elif isinstance(target, ast.Tuple) and any(
                    getattr(x, "id", None) == SECOND_TABLE for x in target.elts):
                lines.append(getattr(node, "lineno", 0))
    return sorted(lines)


def main_node(tree):
    return module_function(tree, "main")


def segment(text, node):
    try:
        return ast.get_source_segment(text, node) or ""
    except Exception:  # noqa: BLE001 -- an unreadable node is a failure, below
        return ""


def check(text):
    failures = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return ["the shell does not parse: %s" % exc]

    pairs = table_pairs(tree)
    if not pairs:
        failures.append("A1 no module-level MEASUREMENT_FLAGS tuple of (attr, '--label') pairs")
        pairs = []
    else:
        bad = [p for p in pairs if not str(p[1]).startswith("--")]
        if bad:
            failures.append("A1 table entries whose label is not a '--flag': %s" % bad[:3])
        if len(pairs) < 9:
            failures.append("A1 the table has %d entries -- the nine measurement flags are the "
                            "population" % len(pairs))
    attrs = [a for a, _ in pairs]
    if len(set(attrs)) != len(attrs):
        failures.append("A1 the table names the same attribute twice")

    declared = argparse_flags(tree)
    for attr, label in pairs:
        if label not in declared:
            failures.append("A2 table label %r has no parser.add_argument in the shell" % label)

    exempt = exempt_pairs(tree)
    if exempt is None:
        failures.append("A3 no module-level MEASUREMENT_EXEMPT tuple: a family flag whose "
                        "default is already truthy, or that returns before the window, has "
                        "nowhere to be declared")
        exempt = []
    family = sorted(f for f in declared if FAMILY.match(f.lstrip("-").replace("-", "_")))
    declared_labels = set(label for _, label in pairs) | set(label for _, label in exempt)
    orphans = [f for f in family if f not in declared_labels]
    if orphans:
        failures.append("A3 measurement-family flags that neither the table nor the "
                        "exemption list knows: %s" % orphans)
    for attr, label in exempt:
        if label not in declared:
            failures.append("A3 exemption %r has no parser.add_argument in the shell" % label)
    both = [label for _, label in pairs if label in set(l for _, l in exempt)]
    if both:
        failures.append("A3 %s is declared BOTH as a measurement flag and as an exemption: "
                        "a truthy default would mark every run a measurement" % both)

    lockfn = module_function(tree, "measurement_lock_name")
    if lockfn is None:
        failures.append("A4 measurement_lock_name is gone")
    else:
        body = segment(text, lockfn)
        if "MEASUREMENT_FLAGS" not in body:
            failures.append("A4 measurement_lock_name does not build its label from "
                            "MEASUREMENT_FLAGS")
        if SECOND_TABLE in body:
            failures.append("A4 measurement_lock_name still reads the second table %s"
                            % SECOND_TABLE)
    if second_table_bindings(tree):
        failures.append("A4 the second flag table %s is ASSIGNED again at %s (a comment that "
                        "names it is documentation, not a table)"
                        % (SECOND_TABLE, second_table_bindings(tree)))

    shell_cls = class_node(tree, "SottoShell")
    if shell_cls is None:
        failures.append("A5 SottoShell class not found")
    else:
        for node in shell_cls.body:
            if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", None) == "MEASUREMENT_FLAGS" for t in node.targets):
                failures.append("A5 SottoShell carries its OWN MEASUREMENT_FLAGS copy again")
        run = None
        for node in shell_cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == "_is_measurement_run":
                run = node
        if run is None:
            failures.append("A5 SottoShell._is_measurement_run is gone")
        elif "_measurement_flag" not in segment(text, run):
            failures.append("A5 _is_measurement_run does not delegate to _measurement_flag")

    main = main_node(tree)
    if main is None:
        failures.append("A6 main() not found")
    else:
        body = segment(text, main)
        if "_measurement_flag(args)" not in body:
            failures.append("A6 main() does not take its lock excuse from _measurement_flag(args)")
        assigns = [n for n in ast.walk(main)
                   if isinstance(n, ast.Assign)
                   and any(getattr(x, "id", None) == "lock_excuse" for x in n.targets)]
        if not assigns:
            failures.append("A6 no `lock_excuse = ...` in main()")
        decided = [n for n in assigns
                   if isinstance(n.value, ast.Call)
                   and getattr(n.value.func, "id", None) == "_measurement_flag"]
        if not decided:
            failures.append("A6 lock_excuse is never decided by _measurement_flag(args)")
        # A reset to None is an initialisation; any OTHER value is a second owner.
        for node in assigns:
            val = node.value
            if isinstance(val, ast.Constant) and val.value is None:
                continue
            if node in decided:
                continue
            failures.append("A6 lock_excuse has a second owner besides "
                            "_measurement_flag(args): %s" % segment(text, val)[:60])

    flagfn = module_function(tree, "_measurement_flag")
    if flagfn is None:
        failures.append("A7 _measurement_flag is gone")
    else:
        body = segment(text, flagfn)
        if "probe_v2" in body:
            failures.append("A7 _measurement_flag carries an inline probe_v2 special case again")
        if "MEASUREMENT_FLAGS" not in body:
            failures.append("A7 _measurement_flag does not read the table")

    # A8: EXECUTE the real functions. A gate that only reads text cannot tell a
    # function that returns the right answer from one that returns None.
    if flagfn is not None and pairs:
        namespace = {}
        table_src = ["MEASUREMENT_FLAGS = ("] + [
            "    (%r, %r)," % (a, l) for a, l in pairs] + [")"]
        try:
            exec("\n".join(table_src), namespace)          # noqa: S102
            exec(segment(text, flagfn), namespace)          # noqa: S102
        except Exception as exc:                            # noqa: BLE001
            failures.append("A8 the table or _measurement_flag does not execute: %s" % exc)
        else:
            probe = namespace["_measurement_flag"]
            cases = (
                (dict(probe_stats=True), "--probe-stats"),
                (dict(exit_after=25.0, probe_stats=True), "--exit-after"),
                (dict(probe_edit_mode=True), "--probe-edit-mode"),
                (dict(probe_v2=12.0), "--probe-v2"),
                (dict(), None),
            )
            for kwargs, want in cases:
                got = probe(argparse.Namespace(**kwargs))
                if got != want:
                    failures.append("A8 _measurement_flag(%s) = %r, wanted %r"
                                    % (kwargs, got, want))

    # A9: A FILA DO BATCH E' ESTADO DO DONO. A medicao que importa a shell
    # constroi a `BatchQueue` e o executor drena `batch_queue.queue_dir()` --
    # o MESMO directorio da app viva. Medido 2026-11-12 (DM do watcher): a
    # sonda a transcrever `I:\cc-tmp\sotto-batch-queue\*.f32` a 69,1 MB/s com
    # 56,8 criacoes/s, no episodio de stutter do dono. A cura e' a mesma forma
    # do `isolated_state_file`: uma largada de medicao ganha fila propria, e a
    # app do dono fica byte-identica (`None`).
    qfn = module_function(tree, "isolated_queue_dir")
    if qfn is None:
        failures.append("A9 isolated_queue_dir is gone: a measurement launch drains the "
                        "owner's batch queue")
    else:
        namespace = {"os": os, "sys": sys, "re": re, "argparse": argparse,
                     "DEFAULT_MUTEX_NAME": "Local\\\\SottoShell"}
        try:
            namespace["MEASUREMENT_FLAGS"] = tuple(pairs)
            for name in ("measurement_lock_name", "_measurement_flag",
                         "is_measurement_launch", "measurement_state_tag",
                         "isolated_queue_dir"):
                fn = module_function(tree, name)
                if fn is None:
                    raise LookupError(name)
                exec(segment(text, fn), namespace)      # noqa: S102
            fake = types.ModuleType("batch_queue")
            fake.queue_dir = lambda: os.path.join("X:", "q")
            saved = sys.modules.get("batch_queue")
            sys.modules["batch_queue"] = fake
            try:
                again = {}
                for name in ("measurement_lock_name", "_measurement_flag",
                             "is_measurement_launch", "measurement_state_tag",
                             "isolated_queue_dir"):
                    again[name] = namespace[name]
                owner = again["isolated_queue_dir"](argparse.Namespace())
                probe = again["isolated_queue_dir"](
                    argparse.Namespace(probe_stats=True))
                # UM HOST SEM `args` E' UM INSTRUMENTO, nunca a app do dono.
                noargs = again["isolated_queue_dir"](None)
            finally:
                if saved is None:
                    sys.modules.pop("batch_queue", None)
                else:
                    sys.modules["batch_queue"] = saved
        except Exception as exc:                            # noqa: BLE001
            failures.append("A9 the queue-isolation functions do not execute: %s" % exc)
        else:
            if owner is not None:
                failures.append("A9 the OWNER's app gets an isolated queue (%r): his batch "
                                "queue must stay byte-identical" % (owner,))
            if not probe or probe == os.path.join("X:", "q"):
                failures.append("A9 a measurement launch still resolves the owner's queue "
                                "(%r)" % (probe,))
            elif "probe_stats" not in probe:
                failures.append("A9 the isolated queue is not tagged with the launch (%r)"
                                % (probe,))
            if not noargs:
                failures.append("A9 a host built WITHOUT `args` (an instrument) resolves the "
                                "owner's queue: the belt only works if the tag does")

    la = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_open_load_action":
            la = node
    if la is None:
        failures.append("A9 _open_load_action is gone")
    else:
        body = segment(text, la)
        if "isolated_queue_dir(" not in body:
            failures.append("A9 _open_load_action does not ask isolated_queue_dir -- the "
                            "helper alone changes nothing")
        if "queue_dir=queue_dir" not in body:
            failures.append("A9 _open_load_action does not pass `queue_dir=` into open_action")
    return failures


MUTANTS = (
    ("M1-A3", "    ('probe_stats', '--probe-stats'),\n", "", "A3"),
    ("M2-A6",
     "    else:\n        # ONE TABLE DECIDES.",
     "    elif args.dump_dom:\n        lock_excuse = '--dump-dom'\n    else:\n        # ONE TABLE DECIDES.",
     "A6"),
    ("M3-A5", "        return _measurement_flag(args) or ''",
     "        for name in ('dump_dom', 'selftest', 'memory'):\n"
     "            if getattr(args, name, False):\n"
     "                return name\n        return ''", "A5"),
    ("M4-A3", "    parser.add_argument('--exit-after', type=float, default=0.0,",
     "    parser.add_argument('--probe-new-thing', action='store_true',\n"
     "                        help='a measurement flag nobody told the table about')\n"
     "    parser.add_argument('--exit-after', type=float, default=0.0,", "A3"),
    # A FILA: M5 faz a sonda resolver a fila DO DONO outra vez (o defeito
    # medido no stutter de 2026-11-12), M6 desliga a fiacao -- um helper
    # correcto que ninguem chama nao muda um byte.
    ("M5-A9", "    return _queue_dir() + '.' + tag", "    return _queue_dir()", "A9"),
    ("M6-A9", "                self, monitor=monitor, log_fn=log, queue_dir=queue_dir)",
     "                self, monitor=monitor, log_fn=log)", "A9"),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    text = source()
    normalized = text.replace("\r\n", "\n")
    failures = check(normalized)
    say("measurement-flags-oracle -- one table for the measurement flags (no launch)")
    if parsed.neg_arm:
        if failures:
            say("NEG-ARM SETUP ERROR: the file already fails, so a mutation proves nothing:")
            for item in failures:
                say("  base: " + item)
            say("")
            say("NEG-ARM FAIL -- not counted")
            return 2
        missed = []
        caught = []
        for tag, old, new, arm in MUTANTS:
            hits = normalized.count(old)
            if hits != 1:
                say("NEG-ARM SETUP ERROR: mutation %s anchor occurs %d time(s) -- %s"
                    % (tag, hits, "stale" if hits == 0 else "ambiguous"))
                say("")
                say("NEG-ARM FAIL -- a decorative mutant proves nothing")
                return 2
            mutant = normalized.replace(old, new, 1)
            got = [f for f in check(mutant) if f.startswith(arm)]
            if got:
                caught.append("%s->%s" % (tag, arm))
                say("  caught %s by %s: %s" % (tag, arm, got[0][:86]))
            else:
                missed.append(tag)
                say("  MISSED %s: no %s failure (got %s)"
                    % (tag, arm, [f[:38] for f in check(mutant)]))
        say("")
        if missed:
            say("NEG-ARM FAIL: mutants that escaped = %s" % missed)
            return 0
        say("NEG-ARM: PASS -- %d/%d mutants, each caught by its own arm (%s)"
            % (len(MUTANTS), len(MUTANTS), ", ".join(caught)))
        return 1

    say("")
    say("VERDICT: " + ("PASS" if not failures else "FAIL")
        + " -- one table feeds the lock name, the model-load refusal, the caption refusal, the "
          "hotkey refusal and the decision in main()")
    for item in failures:
        say("  wrong: " + item)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
