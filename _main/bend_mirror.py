#!/usr/bin/env python3
"""Bind the DECISAO 6/7 laws to the REAL production functions.

`bend_core/LAWS.bend` is the proof-carrying artifact: `bend PROOF.bend
--verdict` hands every law to the Lean-backed kernel, which either checks it or
refuses to compile. `bend_core/model.py` mirrors the model on hosts without the
toolchain, over an explicit sample. **Neither connects a law to `app/panel/`.**
This file does, and it does so by EXECUTING the production modules (through
`node`), never by re-reading their text.

The two decision cores bound here
---------------------------------
* DECISAO 6 -- `app/panel/history-source.js`: `historyDecision(meta)` decides
  whether a caption line may enter the canonical transcript, and under which
  route. Bound over the WHOLE input domain (4 routes x 5 producer spellings +
  a non-object `meta`): every law in the `Hist.*` family is asserted against
  the function's real answer.
* DECISAO 7 -- `app/panel/caption-formulation.js`: `routeFor(reason)` and
  `routeSourceFor(route)` decide the `route`/`routeSource` a commit stamps.
  Bound by DRIVING A REAL ENGINE -- `createEngine(...).ingest(...)` then
  `flush`/`expireHold` -- and reading the `meta` the engine hands to
  `onCommit`. No internal function is reachable from outside the closure, so
  the engine is the honest seam.

What this file is NOT
---------------------
* It is a FINITE behavioural check over the grids below. It does not establish
  the theorem -- that is the kernel's job -- and a green run here says nothing
  about the formal artifact's validity. The two are complements.
* The 14 pre-existing `Nat.*`/`Toks.*`/`Cap.*` laws are bound elsewhere and
  already: `_main/youtube-1to1-oracle.py`, `_main/youtube-reveal-oracle.py`,
  `_main/youtube-rows-oracle.py` (the reveal/window laws, against
  `app/webview/youtube_window.py` and `youtube_reveal.py`) and the epoch
  oracles (the `Cap.*` trio, against `app/webview/sotto_webview.py`).

Run:  python _main/bend_mirror.py          # green: laws hold of production
      python _main/bend_mirror.py --red    # the mirror can FAIL (a NEG-ARM)

`--red` is a NEGATIVE ARM no sentido da casa: **rc=1 quando apanha** todos os
mutantes (e imprime `NEG-ARM PASS`), **rc=0 quando deixa um passar** -- assim o
passo `:expectred` da bateria reprova o braco que nao morde. Medido 2026-11-08:
a primeira versao devolvia 0 ao apanhar, que e' a inversao que ja' tinha sido
curada no `hotkey-spam`. E o mirror NAO e' decoracao: ele patcheia cada
production module with the defect class the law exists to prevent, and
requires the named checks to go red. If a mutant passes, this file is blind.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _hidden_launch():
    """O largador DA CASA (`_main/hidden-launch.py`).

    Um `subprocess` cru sem `CREATE_NO_WINDOW` herda a consola do pai e, largado
    de um `pythonw`, da' ao filho uma consola NOVA -- uma janela na tela do dono
    (medido 2026-11-04). O `console-window-audit` le' cada `Popen` por AST e
    reprovou este ficheiro por isso mesmo (`:134 NO-FLAG larga node sem guarda`).
    """
    path = Path(__file__).resolve().parent / "hidden-launch.py"
    spec = importlib.util.spec_from_file_location("sotto_hidden_launch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HISTORY_JS = REPO / "app" / "panel" / "history-source.js"
FORMULATION_JS = REPO / "app" / "panel" / "caption-formulation.js"

#: The reasons `caption-formulation.js` treats as the PANEL's own close
#: (`PANEL_CLOSED_REASON`). Named here so the oracle can classify a real
#: `commit` reason exactly as the production regex does.
PANEL_CLOSED_PREFIXES = ("hold-timeout", "status-change", "flush", "stable")


def panel_closed(reason: str) -> bool:
    """`PANEL_CLOSED_REASON.test(reason)`."""
    return str(reason or "").startswith(PANEL_CLOSED_PREFIXES)


# ---------------------------------------------------------------------------
# Node harnesses.
# ---------------------------------------------------------------------------

HISTORY_HARNESS = r"""
const H = require(process.argv[1]);
const routes = ['final', 'provisional-draft', 'weird', ''];
const producers = [null, 'redux', 'live', 'other', ''];
const out = [];
for (const route of routes) {
  for (const producer of producers) {
    const meta = {};
    if (route !== '') meta.route = route;
    if (producer !== null) meta.producer = producer;
    const decision = H.historyDecision(meta);
    const refusal = H.historyRefusal(meta);
    out.push({
      route, producer,
      route_out: decision.route,
      reason: decision.reason,
      refused: refusal !== null,
      refusal_reason: refusal === null ? null : refusal.reason,
    });
  }
}
const nul = H.historyDecision(null);
out.push({route: null, producer: null, route_out: nul.route, reason: nul.reason,
          refused: H.historyRefusal(null) !== null,
          refusal_reason: H.historyRefusal(null) === null ? null : H.historyRefusal(null).reason});
console.log(JSON.stringify(out));
"""

FORMULATION_HARNESS = r"""
const F = require(process.argv[1]);
const cases = [
  {label: 'worker-final',   meta: {start: 0, end: 1, final: true},  closer: 'flush',  reason: 'flush'},
  {label: 'worker-partial', meta: {start: 0, end: 1, final: false}, closer: 'flush',  reason: 'flush'},
  {label: 'panel-hold',     meta: {start: 0, end: 1},               closer: 'flush',  reason: 'hold-timeout'},
  {label: 'panel-status',   meta: {start: 0, end: 1},               closer: 'flush',  reason: 'status-change'},
  {label: 'audio-gap',      meta: {start: 0, end: 1},               closer: 'flush',  reason: 'audio-gap 9.00s'},
  {label: 'audio-chars',    meta: {start: 0, end: 1},               closer: 'flush',  reason: 'chars 90'},
  {label: 'producer-redux', meta: {start: 0, end: 1, producer: 'redux'}, closer: 'flush', reason: 'audio-gap 9.00s'},
  {label: 'producer-live',  meta: {start: 0, end: 1, producer: 'live'},  closer: 'flush', reason: 'audio-gap 9.00s'},
  {label: 'stable',         meta: {start: 0, end: 1, stable: true}, closer: 'none',   reason: null},
  {label: 'expire-hold',    meta: {start: 0, end: 1},               closer: 'expire', reason: null},
];
const out = [];
for (const c of cases) {
  const commits = [];
  const engine = F.createEngine({
    onCommit: (text, reason, meta) => commits.push({
      text, reason, route: meta.route, routeSource: meta.routeSource, producer: meta.producer,
    }),
    onProvisional: () => {},
    now: () => 0,
  });
  engine.ingest('hello brave world', c.meta);
  if (c.closer === 'flush') engine.flush(c.reason);
  else if (c.closer === 'expire') engine.expireHold();
  out.push({label: c.label, meta: c.meta, closer: c.closer, reason: c.reason, commits});
}
console.log(JSON.stringify(out));
"""


def run_node(harness: str, module_path: Path) -> list[dict]:
    rc, out, err = _hidden_launch().run(
        ["node", "-e", harness, str(module_path)],
        cwd=str(REPO), capture=True, timeout=120,
    )
    if rc != 0:
        raise RuntimeError("node failed (%d) for %s:\n%s" % (rc, module_path, err))
    return json.loads(out)


# ---------------------------------------------------------------------------
# The model, re-stated in Python EXACTLY as `bend_core/LAWS.bend` states it.
# The mirror compares this model's answer with production, so a drift on
# either side is visible.
# ---------------------------------------------------------------------------


def model_hist_route(route, producer):
    if route == "final":
        return "final"
    if route is not None:
        return None
    return "batch" if producer == "redux" else None


def model_hist_accepted(route, producer):
    return model_hist_route(route, producer) is not None


def model_hist_accepted_reference(route, producer):
    if route == "final":
        return True
    if route is not None:
        return False
    return producer == "redux"


def model_fmt_is_final(buffer_final, saw_final, panel_closed_flag):
    if buffer_final:
        return True
    if saw_final:
        return False
    return not panel_closed_flag


def model_fmt_is_final_reference(buffer_final, saw_final, panel_closed_flag):
    return True if buffer_final else (False if saw_final else (not panel_closed_flag))


def model_fmt_source(buffer_final, saw_final, has_producer, panel_closed_flag):
    if buffer_final or saw_final:
        return "worker-stamped"
    if has_producer:
        return "worker-stamped-producer"
    return "panel-deadline" if panel_closed_flag else "fallback"


# ---------------------------------------------------------------------------
# The checks. Each one names the law it is the witness of; `(ok, detail)`.
# ---------------------------------------------------------------------------


def check_history(rows: list[dict]) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    def norm_producer(value):
        # `producerOf` trims and treats empty/absent as null.
        return value if value else None

    def add(law, ok, detail):
        checks.append((law, bool(ok), detail))

    # Law 1: a worker-CLOSED line is accepted.
    bad = [r for r in rows if r["route"] == "final" and r["route_out"] != "final"]
    add("Hist.final_route_is_accepted", not bad, "refused: %r" % (bad[:3],))

    # Law 2: the live caption's route never enters.
    bad = [r for r in rows if r["route"] == "provisional-draft" and r["route_out"] is not None]
    add("Hist.provisional_route_is_refused", not bad, "entered: %r" % (bad[:3],))

    # Law 3: producer 'live' with no route never enters.
    bad = [r for r in rows
           if norm_producer(r["producer"]) == "live"
           and r["route"] in (None, "")
           and r["route_out"] is not None]
    add("Hist.live_producer_is_never_canonical", not bad, "entered: %r" % (bad[:3],))

    # Law 4: with no route the answer IS the canonical-producer predicate.
    bad = [r for r in rows
           if r["route"] in (None, "")
           and (r["route_out"] == "batch") != (norm_producer(r["producer"]) == "redux")]
    add("Hist.absent_claim_is_accepted_only_from_the_canonical_producer",
        not bad, "mismatch: %r" % (bad[:3],))

    # Law 5: an unknown route is refused.
    bad = [r for r in rows if r["route"] == "weird" and r["route_out"] is not None]
    add("Hist.unknown_route_is_refused", not bad, "entered: %r" % (bad[:3],))

    # Law 6: only the `redux` producer can ever be the batch route.
    bad = [r for r in rows
           if r["route_out"] == "batch" and norm_producer(r["producer"]) != "redux"]
    add("Hist.canonical_producer_is_exactly_the_redux_code",
        not bad, "non-redux batch: %r" % (bad[:3],))

    # Law 7 + the model binding: the projection and the written rule agree,
    # and both predict the function's real answer.
    bad = []
    for r in rows:
        route = None if r["route"] in (None, "") else r["route"]
        producer = norm_producer(r["producer"])
        accepted = model_hist_accepted(route, producer)
        reference = model_hist_accepted_reference(route, producer)
        if accepted != reference or accepted != (r["route_out"] is not None):
            bad.append((r, accepted, reference))
    add("Hist.accepted_agrees_with_its_two_forms", not bad, "drift: %r" % (bad[:3],))

    # Law 8: a refusal always names itself.
    bad = []
    for r in rows:
        if r["refused"] != (r["route_out"] is None):
            bad.append(("accept/refusal disagree", r))
        if r["refused"] and not r["refusal_reason"]:
            bad.append(("refusal without a reason", r))
        if not r["refused"] and r["refusal_reason"]:
            bad.append(("accepted with a refusal", r))
    add("Hist.refusal_names_itself", not bad, "silent: %r" % (bad[:3],))

    return checks


def check_formulation(cases: list[dict]) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    def add(law, ok, detail):
        checks.append((law, bool(ok), detail))

    observations = []
    for case in cases:
        commits = case["commits"]
        if len(commits) != 1:
            add("Fmt.commit_happened", False,
                "%s produced %d commits" % (case["label"], len(commits)))
            continue
        commit = commits[0]
        meta = case["meta"]
        buffer_final = meta.get("final") is True
        saw_final = isinstance(meta.get("final"), bool)
        has_producer = bool(str(meta.get("producer") or "").strip())
        closed = panel_closed(commit["reason"])
        observations.append({
            "label": case["label"], "meta": meta, "commit": commit,
            "buffer_final": buffer_final, "saw_final": saw_final,
            "has_producer": has_producer, "panel_closed": closed,
        })

    # Law 1: the worker's final vote wins over the reason.
    bad = [o for o in observations if o["buffer_final"] and o["commit"]["route"] != "final"]
    add("Fmt.worker_final_vote_is_final", not bad, "downgraded: %r" % (bad[:3],))

    # Law 2: the worker's open vote is never promoted.
    bad = [o for o in observations
           if o["saw_final"] and not o["buffer_final"] and o["commit"]["route"] == "final"]
    add("Fmt.worker_partial_vote_is_never_final", not bad, "promoted: %r" % (bad[:3],))

    # Law 3: the panel's own close never manufactures a final route.
    bad = [o for o in observations
           if o["panel_closed"] and not o["buffer_final"] and not o["saw_final"]
           and o["commit"]["route"] == "final"]
    add("Fmt.panel_close_never_manufactures_final", not bad, "manufactured: %r" % (bad[:3],))

    # Law 4: the deliberate fallback still emits `final`.
    bad = [o for o in observations
           if not o["buffer_final"] and not o["saw_final"] and not o["has_producer"]
           and not o["panel_closed"] and o["commit"]["route"] != "final"]
    add("Fmt.audio_close_without_a_vote_is_final", not bad, "missing final: %r" % (bad[:3],))

    # Law 5: both forms of the decision agree with the engine's real answer.
    bad = []
    for o in observations:
        model = model_fmt_is_final(o["buffer_final"], o["saw_final"], o["panel_closed"])
        reference = model_fmt_is_final_reference(
            o["buffer_final"], o["saw_final"], o["panel_closed"])
        actual = o["commit"]["route"] == "final"
        if model != reference or model != actual:
            bad.append((o["label"], model, reference, actual))
    add("Fmt.route_agrees_with_its_two_forms", not bad, "drift: %r" % (bad[:3],))

    # Law 6: `fallback` appears exactly on the silent default, nowhere else.
    bad = []
    for o in observations:
        expected = (not o["buffer_final"] and not o["saw_final"]
                    and not o["has_producer"] and not o["panel_closed"])
        actual = o["commit"]["routeSource"] == "fallback"
        if actual != expected:
            bad.append((o["label"], o["commit"]["routeSource"], expected))
        model = model_fmt_source(o["buffer_final"], o["saw_final"],
                                 o["has_producer"], o["panel_closed"])
        if model != o["commit"]["routeSource"]:
            bad.append((o["label"], "source", model, o["commit"]["routeSource"]))
    add("Fmt.fallback_is_exactly_the_silent_default", not bad, "label drift: %r" % (bad[:3],))

    return checks


# ---------------------------------------------------------------------------
# The red run: each mutation is the defect class its law exists to prevent.
# ---------------------------------------------------------------------------

MUTANTS = (
    # (label, module, old, new, laws that MUST go red)
    (
        "history accepts the live producer",
        HISTORY_JS,
        "  if (route === 'final') return { route: 'final', reason: '' };",
        "  if (route === 'final') return { route: 'final', reason: '' };\n"
        "  if (producerOf(meta) === LIVE_PRODUCER) return { route: BATCH_ROUTE, reason: '' };",
        ("Hist.live_producer_is_never_canonical",
         "Hist.absent_claim_is_accepted_only_from_the_canonical_producer"),
    ),
    (
        "history accepts the live caption's route",
        HISTORY_JS,
        "      route: null,\n"
        "      reason: route === 'provisional-draft' ? 'provisional-draft' : 'unknown-route',",
        "      route: 'batch',\n"
        "      reason: route === 'provisional-draft' ? 'provisional-draft' : 'unknown-route',",
        ("Hist.provisional_route_is_refused",),
    ),
    (
        "formulation lets the panel's timer manufacture a final",
        FORMULATION_JS,
        "      ? 'provisional-draft'\n      : 'final';",
        "      ? 'final'\n      : 'final';",
        ("Fmt.panel_close_never_manufactures_final",
         "Fmt.fallback_is_exactly_the_silent_default"),
    ),
    (
        "formulation downgrades the worker's final vote",
        FORMULATION_JS,
        "    if (bufferFinal) return 'final';",
        "    if (bufferFinal) return 'provisional-draft';",
        ("Fmt.worker_final_vote_is_final",),
    ),
)


def run_checks(history_rows, formulation_cases):
    return check_history(history_rows) + check_formulation(formulation_cases)


def red_run() -> int:
    failures = 0
    with tempfile.TemporaryDirectory(prefix="bend-mirror-") as tmp:
        for index, (label, module, old, new, expected) in enumerate(MUTANTS):
            source = module.read_text(encoding="utf-8")
            if source.count(old) != 1:
                print("RED-RUN FAIL: [%s] pattern matched %d times in %s"
                      % (label, source.count(old), module.name))
                failures += 1
                continue
            mutant = Path(tmp) / ("mutant-%d%s" % (index, module.suffix))
            mutant.write_text(source.replace(old, new), encoding="utf-8")
            try:
                if module is HISTORY_JS:
                    rows = run_node(HISTORY_HARNESS, mutant)
                    cases = run_node(FORMULATION_HARNESS, FORMULATION_JS)
                else:
                    rows = run_node(HISTORY_HARNESS, HISTORY_JS)
                    cases = run_node(FORMULATION_HARNESS, mutant)
            except RuntimeError as exc:
                print("RED-RUN FAIL: [%s] mutant did not load: %s" % (label, exc))
                failures += 1
                continue
            red = {law for law, ok, _detail in run_checks(rows, cases) if not ok}
            missing = [law for law in expected if law not in red]
            if missing:
                print("RED-RUN FAIL: [%s] the mutant passed %s"
                      % (label, ", ".join(missing)))
                failures += 1
            else:
                print("RED-RUN PASS: [%s] caught by %s" % (label, ", ".join(expected)))
    if failures:
        print("RED-RUN VERDICT FAIL (%d mutant(s) not caught) -- NEG-ARM did not catch"
              % failures)
        return 0
    print("RED-RUN NEG-ARM PASS -- %d/%d mutant(s) caught; the mirror can fail"
          % (len(MUTANTS), len(MUTANTS)))
    return 1


def green_run() -> int:
    rows = run_node(HISTORY_HARNESS, HISTORY_JS)
    cases = run_node(FORMULATION_HARNESS, FORMULATION_JS)
    checks = run_checks(rows, cases)
    failed = 0
    for law, ok, detail in checks:
        if ok:
            print("PASS %s" % law)
        else:
            failed += 1
            print("FAIL %s -- %s" % (law, detail))
    if failed:
        print("MIRROR VERDICT FAIL (%d check(s) red)" % failed)
        return 1
    print("MIRROR VERDICT GREEN (%d checks, %d history rows, %d engine cases)"
          % (len(checks), len(rows), len(cases)))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--red", action="store_true",
                        help="run the mutants; the named laws MUST go red")
    args = parser.parse_args(argv)
    if args.red:
        return red_run()
    return green_run()


if __name__ == "__main__":
    sys.exit(main())
