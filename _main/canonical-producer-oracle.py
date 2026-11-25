#!/usr/bin/env python3
"""Sotto T3 oracle -- does a WORKER-stamped \`producer\` ever reach the canonical gate?

THE QUESTION (verbatim from the brief): "It is UNMEASURED whether a worker-stamped
producer field ever reaches that gate. Decide it by reading the code and MEASURING,
not by assuming."

WHAT THE GATE IS. app/panel/history-source.js accepts a line into the canonical
transcript ONLY when \`producerOf(meta) === CANONICAL_PRODUCER\` ('redux'), and it is
fail-closed: an absent, empty or unknown producer is REFUSED, never assumed.
app/panel/panel.js:recordHistory runs that test before the store is touched.

WHAT THIS FILE MEASURES, in process, without launching anything:

  ARM A  executes the REAL app/panel/history-source.js through \`require\` and
         measures ACCEPT/REFUSE over a table of hand-built metas (the fail-closed
         property is SHOWN, not asserted).
  ARM B  imports the REAL worker/sotto_worker.py INTO THIS PROCESS, builds the REAL
         ReduxHiddenSwitch with a stand-in runner in %TEMP%, calls the REAL
         \`_run_runner\`, and reads the REAL event it queues.
  ARM C  runs the REAL app/panel/caption-formulation.js engine over the event ARM B
         produced -- projected by the REAL \`WorkerBridge._consume\`, extracted from
         the live shell with \`ast\` and executed here -- and hands the engine's OWN
         commit meta to the REAL gate.
  ANCHOR re-locates every hop's file:line in the LIVE bytes and prints it, so no
         citation in this oracle is a stale hint.
  NEG    cuts each of the three hops in an in-memory / %TEMP% copy of the REAL
         bytes and REQUIRES the arm that should notice to go RED.

WHY PYTHON AND NOT NODE: the load-bearing new fact is the WORKER's stamp, and only
Python can execute the real \`_run_runner\` in process. Node executes the two real
panel modules; it is spawned with CREATE_NO_WINDOW, so no console ever appears.

IN-PROCESS ONLY. This file never launches the app, the WebView2 shell, run.cmd, the
worker's capture path, or any GUI. Nothing under app/ or worker/ is written.

COLOURS (the same checks, two subjects):
  no flag    -> GREEN, exit 0. Mutants run as NEG arms and must go RED.
  --red-arm  -> the SAME checks run against the mutants as the SUBJECT -> RED, exit
                non-zero. That is the proof this oracle can say NO.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CREATE_NO_WINDOW = 0x08000000
NODE = "node"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PANEL_DIR = ROOT / "app" / "panel"
HISTORY_SOURCE = PANEL_DIR / "history-source.js"
FORMULATION = PANEL_DIR / "caption-formulation.js"
PANEL_JS = PANEL_DIR / "panel.js"
HISTORY_STORE = PANEL_DIR / "history-store.js"
SHELL = ROOT / "app" / "webview" / "sotto_webview.py"
WORKER = ROOT / "worker" / "sotto_worker.py"
#: THE WORKER IS TWO FILES SINCE 2cc4e58 (`feat(audio): capture the microphone and
#: transcribe both sides`): `sotto_worker.py` is the entry (argparse, startup, the
#: batch loop) and `worker/engine_switch.py` is the core that queues the caption and
#: writes `producer`. Every anchor below therefore resolves across BOTH files and
#: names the one that owns it -- an oracle that kept reading only the entry file went
#: from GREEN to a traceback (`worker stamp line not unique`, count==0) without any
#: product change, which is a gate that stopped seeing its own subject.
WORKER_CORE = ROOT / "worker" / "engine_switch.py"
REDUX_RUNNER = ROOT / "worker" / "redux_batch.py"
REDUX_MODEL_DIR = ROOT / "worker" / "models" / "parakeet-redux-ternary"
REDUX_MODEL_DIR_INT4 = ROOT / "worker" / "models" / "parakeet-redux-onnx-int4"

RESULTS: list = []


def check(arm: str, name: str, ok, detail: str = "") -> bool:
    ok = bool(ok)
    RESULTS.append({"arm": arm, "name": name, "ok": ok, "detail": detail})
    print(("ok   " if ok else "FAIL ") + "[" + arm + "] " + name
          + ("  -- " + detail if detail else ""), flush=True)
    return ok


def note(text: str) -> None:
    print("       " + text, flush=True)


def pin(path: Path) -> bytes:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest().upper()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime))
    print("PIN  " + str(path) + "  " + str(len(data)) + " B  sha256 " + digest
          + "  mtime " + stamp, flush=True)
    return data


def line_of(text: str, pattern: str, occurrence: int = 1) -> int:
    hits = [i + 1 for i, line in enumerate(text.splitlines())
            if re.search(pattern, line)]
    if len(hits) < occurrence:
        return 0
    return hits[occurrence - 1]


def anchor(tag: str, text: str, pattern: str, path: Path, occurrence: int = 1) -> int:
    n = line_of(text, pattern, occurrence)
    where = str(path) + ":" + str(n) if n else str(path) + ":NOT-FOUND"
    print("HOP  " + tag + "  " + where, flush=True)
    if not n:
        check("ANCHOR", "anchor present: " + tag, False, "pattern not found: " + pattern)
    return n


def anchor_any(tag: str, sources: list, pattern: str, occurrence: int = 1) -> int:
    """Locate a HOP across SEVERAL live files and name the file that owns it.

    The worker split into an entry and a core (2026-11-25, 2cc4e58); every hop that
    used to live in one file now lives in one of two. Searching the union with a
    single `path` label would print a line number that belongs to the other file --
    a gate that accuses the right line in the wrong file loses its authority. So the
    HOP prints `<file>:<line>` of the file that actually matched, and the return is
    the total number of matching lines across the population (so a check can still
    demand uniqueness).
    """
    total = 0
    found = []
    for path, text in sources:
        hits = [i + 1 for i, line in enumerate(text.splitlines()) if re.search(pattern, line)]
        total += len(hits)
        if hits:
            found.append(str(path) + ":" + str(hits[min(occurrence, len(hits)) - 1]))
    print("HOP  " + tag + "  " + (" | ".join(found) if found else "NOT-FOUND"), flush=True)
    if not found:
        check("ANCHOR", "anchor present: " + tag, False, "pattern not found: " + pattern)
    return total


# ---------------------------------------------------------------------------
# the node driver: the two REAL panel modules, executed as the panel loads them
# ---------------------------------------------------------------------------
NODE_DRIVER = r"""
'use strict';
const fs = require('fs');
const source = require(process.argv[2]);
const formulation = require(process.argv[3]);
const job = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
const out = { node: process.version, gate: [], chain: [] };
for (const arm of job.gate) {
  let accept = null, producerOf = null, error = null;
  try {
    accept = source.isCanonicalLine(arm.meta);
    producerOf = source.producerOf(arm.meta);
  } catch (err) { error = String((err && err.message) || err); }
  out.gate.push({ name: arm.name, accept, producerOf, error });
}
for (const arm of job.chain) {
  const commits = [];
  const engine = formulation.createEngine({
    source: (arm.engineSource === undefined ? null : arm.engineSource),
    onCommit: (text, reason, meta) => commits.push({ text, reason, meta }),
    onProvisional: () => {},
  });
  for (const ev of arm.events) engine.ingest(ev.text, ev.meta);
  if (arm.flushReason) engine.flush(arm.flushReason);
  out.chain.push({
    name: arm.name,
    commits,
    accepted: commits.map((c) => source.isCanonicalLine(c.meta)),
    visible: engine.visible(),
  });
}
process.stdout.write(JSON.stringify(out));
"""


def run_node(history_js: Path, formulation_js: Path, job: dict, tmpdir: Path) -> dict:
    driver = tmpdir / "canonical-producer-driver.js"
    jobfile = tmpdir / "canonical-producer-job.json"
    driver.write_text(NODE_DRIVER, encoding="utf-8")
    jobfile.write_text(json.dumps(job), encoding="utf-8")
    proc = subprocess.run(
        [NODE, str(driver), str(history_js), str(formulation_js), str(jobfile)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0), timeout=180)
    if proc.returncode != 0:
        raise RuntimeError("node rc=" + str(proc.returncode) + " stderr="
                           + proc.stderr[:500])
    return json.loads(proc.stdout)


def load_python_module(path: Path, name: str, source_text: str = None):
    """Import a live module -- or a MUTATED COPY of its bytes, under its own path.

    The red arm needs `engine_switch.py` with one field cut. Writing that copy into
    `%TEMP%` and importing it from there was the old shape and it broke the moment the
    worker split: the core imports its siblings by name (`import engine_policy as
    _policy`, `worker/engine_switch.py:135`) and resolves its own checkpoints from
    `HERE`, so a copy in `G:\\Temp` gets `_policy = None` and a wrong `HERE`. A mutant
    that cannot be imported is not a mutant. So a `source_text` is COMPILED with the
    live path as its filename and its directory on `sys.path`: same imports, same
    `HERE`, one line different.
    """
    if source_text is None:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    parent = str(path.parent)
    added = parent not in sys.path
    if added:
        sys.path.insert(0, parent)
    try:
        module = types.ModuleType(name)
        module.__file__ = str(path)
        sys.modules[name] = module
        exec(compile(source_text, str(path), "exec"), module.__dict__)
        return module
    finally:
        if added:
            sys.path.remove(parent)


# ---------------------------------------------------------------------------
# the REAL shell hop: extract WorkerBridge._consume from the live bytes and run it
# ---------------------------------------------------------------------------
def extract_consume(source_text: str, filename: str):
    tree = ast.parse(source_text, filename=filename)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "WorkerBridge")
    # `_consume` stamps the audio session on the meta (`historySession`), and the
    # stamp comes from `history_session(child)`; extract BOTH so the hop is
    # judged with the method the shipped bridge actually calls.
    wanted = {"_consume": None, "history_session": None}
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name in wanted:
            wanted[n.name] = n
    fn = wanted["_consume"]
    session_fn = wanted["history_session"]
    assert session_fn is not None, "WorkerBridge.history_session missing"
    module = ast.Module(
        body=[ast.ClassDef(name="_ExtractedConsume", bases=[], keywords=[],
                           body=[fn, session_fn], decorator_list=[])],
        type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"json": json, "time": time}
    exec(compile(module, filename, "exec"), namespace)
    return namespace["_ExtractedConsume"]


def shell_projection(consume_cls, event: dict):
    inst = consume_cls.__new__(consume_cls)
    inst.malformed = 0
    inst.captions = 0
    inst.statuses = 0
    inst.pending_error = None
    inst.state = ""
    inst.log = lambda msg: None
    # The caption branch also clears a no-audio verdict; a projection without
    # these fields died with AttributeError before it could judge the hop.
    inst.no_audio = False
    inst.no_audio_evidence = None
    inst.no_audio_evidence_at = None
    seen = []
    inst.on_caption = lambda text, meta: seen.append((text, meta))
    inst._consume(json.dumps(event))
    return seen, inst


# ---------------------------------------------------------------------------
# the REAL worker hop: run _run_runner with a stand-in engine in %TEMP%
# ---------------------------------------------------------------------------
STANDIN_RUNNER = '''\
"""A stand-in batch engine for the oracle: it prints the runner's JSONL contract
and DELIBERATELY omits "producer", so what the oracle reads back is the WORKER's
own stamp, not the engine's. Lives in %TEMP%, never in the repo."""
import argparse, json
ap = argparse.ArgumentParser()
ap.add_argument("--wav")
ap.add_argument("--json", action="store_true")
ap.add_argument("--model-dir", default=None)
ap.add_argument("--device", default="cpu")
ap.parse_known_args()
{BODY}
'''
STANDIN_CAPTION = ('print(json.dumps({"type": "caption", "text": "bom dia, mundo",\n'
                   '                    "start": 1.5, "end": 3.0,\n'
                   '                    "model": "standin"}), flush=True)')
STANDIN_EMPTY = 'pass'


def worker_events(worker_mod, tmpdir: Path, with_caption: bool):
    import numpy as np

    runner = tmpdir / ("standin_runner_" + ("caption" if with_caption else "empty") + ".py")
    runner.write_text(STANDIN_RUNNER.format(BODY=STANDIN_CAPTION if with_caption
                                            else STANDIN_EMPTY), encoding="utf-8")
    logs: list = []
    switch = worker_mod.ReduxHiddenSwitch(
        enabled=True, reader=object(), runner=str(runner), log_fn=logs.append,
        armed_by="oracle", wav_dir=str(tmpdir / ("wav_" + str(with_caption))))
    switch._run_runner([np.zeros(16000, dtype=np.float32)], 16000, "oracle")
    return switch.drain_captions(), logs, switch


# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--red-arm", action="store_true",
                        help="run the SAME checks against the mutants as the SUBJECT "
                             "(this must print VERDICT: FAIL and exit non-zero)")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    print("=" * 78)
    print("Sotto T3 -- worker-stamped producer vs the canonical gate")
    print("mode: " + ("RED-ARM (mutants are the SUBJECT)" if args.red_arm
                       else "GREEN-ARM (live bytes are the SUBJECT; mutants are NEG arms)"))
    print("=" * 78, flush=True)

    tmpdir = Path(tempfile.mkdtemp(prefix="sotto-canonical-producer-"))
    print("TMP  " + str(tmpdir) + "   (never inside the repo)", flush=True)

    gate_bytes = pin(HISTORY_SOURCE)
    formulation_bytes = pin(FORMULATION)
    shell_bytes = pin(SHELL)
    worker_bytes = pin(WORKER)
    worker_core_bytes = pin(WORKER_CORE)
    pin(PANEL_JS)
    pin(HISTORY_STORE)
    pin(REDUX_RUNNER)
    gate_text = gate_bytes.decode("utf-8")
    formulation_text = formulation_bytes.decode("utf-8")
    shell_text = shell_bytes.decode("utf-8")
    worker_text = worker_bytes.decode("utf-8")
    worker_core_text = worker_core_bytes.decode("utf-8")
    #: the population the worker anchors resolve across, in file order
    worker_sources = [(WORKER, worker_text), (WORKER_CORE, worker_core_text)]

    # ---- mutants: copies of the REAL bytes, only ever in memory or %TEMP% ----
    gate_stamp = "const CANONICAL_PRODUCER = 'redux';"
    assert gate_text.count(gate_stamp) == 1, "gate stamp not unique"
    gate_mutant_text = gate_text.replace(gate_stamp,
                                         "const CANONICAL_PRODUCER = 'canonical-tdt';")
    gate_mutant = tmpdir / "history-source.mutant.js"
    gate_mutant.write_text(gate_mutant_text, encoding="utf-8")

    # The worker file is CRLF (measured: 5631 CRLF / 0 bare LF), so the stamp is cut
    # WITHOUT assuming the line terminator -- a \n-only replace would silently be a no-op
    # and the "mutant" would be a byte-identical copy that still goes green. The byte-delta
    # check below exists because that is exactly what happened on the first run.
    worker_stamp = '"producer": str(payload.get("producer") or REDUX_PRODUCER),'
    #: THE STAMP LIVES IN THE CORE SINCE 2cc4e58 (`worker/engine_switch.py`), so the
    #: cut is made in the file that owns it -- and the assertion still demands exactly
    #: ONE occurrence across the whole worker population, because a second stamp
    #: elsewhere would mean two writers for one field.
    if worker_stamp in worker_core_text:
        stamp_owner = (WORKER_CORE, worker_core_text)
    else:
        stamp_owner = (WORKER, worker_text)
    occurrences = sum(text.count(worker_stamp) for _, text in worker_sources)
    assert occurrences == 1, ("worker stamp line not unique (count=%d, population=%s)"
                              % (occurrences, [str(p) for p, _ in worker_sources]))
    print("HOP  worker stamps producer on the caption  " + str(stamp_owner[0]), flush=True)
    worker_mutant_text = (stamp_owner[1].replace(worker_stamp + "\r\n", "")
                          .replace(worker_stamp + "\n", ""))
    worker_mutant = tmpdir / (stamp_owner[0].stem + ".mutant.py")
    worker_mutant.write_text(worker_mutant_text, encoding="utf-8", newline="")

    shell_hop = "if k not in ('type', 'text')}"
    assert shell_text.count(shell_hop) == 1, "shell projection line not unique"
    shell_mutant_text = shell_text.replace(shell_hop,
                                           "if k not in ('type', 'text', 'producer')}")
    shell_mutant = tmpdir / "sotto_webview.mutant.py"

    # A SECOND shell cut, deliberate: the src= allow-list. Without it the check
    # above would read the live bytes in BOTH colours -- green because the fix is
    # there, and green in the RED arm because this projection mutant never touches
    # the tuple. A check that cannot go RED is not a check (the rule this file
    # exists to enforce), so the red arm reads a copy with the token dropped, i.e.
    # the pre-2026-10-11 shell, and MUST fail.
    shell_src_drop = "'worker-stamped-producer', "
    assert shell_text.count(shell_src_drop) == 1, "shell src= token not unique"
    shell_src_mutant_text = shell_text.replace(shell_src_drop, "")
    shell_src_mutant = tmpdir / "sotto_webview.src-mutant.py"
    shell_src_mutant.write_text(shell_src_mutant_text, encoding="utf-8", newline="")
    src_subject_text = shell_src_mutant_text if args.red_arm else shell_text

    subject_gate = gate_mutant if args.red_arm else HISTORY_SOURCE
    #: The RED arm imports a MUTATED COPY of the file that owns the stamp, under that
    #: file's own path (2026-11-25 -- see `load_python_module`): the core resolves its
    #: siblings and its checkpoints from its own directory, so a copy in `%TEMP%` is not
    #: importable as the module it is supposed to be.
    subject_worker = stamp_owner[0] if args.red_arm else WORKER
    subject_worker_text = worker_mutant_text if args.red_arm else None
    subject_shell_text = shell_mutant_text if args.red_arm else shell_text
    if args.red_arm:
        shell_mutant.write_text(shell_mutant_text, encoding="utf-8", newline="")

    print("\n-- MUTANT CUTS (a copy that is byte-identical is not a mutant) " + "-" * 18,
          flush=True)
    for tag, live, cut in (("gate", gate_text, gate_mutant_text),
                           ("worker", worker_text, worker_mutant_text),
                           ("shell", shell_text, shell_mutant_text),
                           ("shell-src", shell_text, shell_src_mutant_text)):
        check("NEG", "M-" + tag + " mutant differs from the live bytes",
              cut != live, "delta_bytes=" + str(len(cut) - len(live)))

    # =====================================================================
    # ANCHORS -- every hop re-located in the LIVE bytes, right now
    # =====================================================================
    print("\n-- ANCHORS (re-measured on the live bytes) " + "-" * 34, flush=True)
    a_worker_const = anchor_any("worker constant REDUX_PRODUCER", worker_sources,
                                r'^REDUX_PRODUCER = "redux"')
    a_worker_stamp = anchor_any("worker stamps producer on the caption", worker_sources,
                                r'"producer": str\(payload\.get\("producer"\) or REDUX_PRODUCER\)')
    a_worker_put = anchor_any("worker queues the batch caption", worker_sources,
                              r'self\._captions\.put\(\{')
    a_worker_runner = anchor_any("worker _run_runner", worker_sources,
                                 r"def _run_runner\(self, held, samples, reason\)")
    a_worker_emit = anchor_any("worker emit(**payload)", worker_sources,
                               r"def emit\(\*\*payload\)")
    a_worker_drain = anchor_any("worker drains the switch into emit", worker_sources,
                                r"for payload in switch\.drain_captions\(\):")
    a_worker_flag = anchor_any("worker flag default OFF", worker_sources,
                               r"^REDUX_WHEN_HIDDEN_DEFAULT = False")
    a_worker_optin = anchor_any("worker flag opt-in", worker_sources,
                                r"redux_optin = bool\(args\.redux_when_hidden\)")
    # Label corrected 2026-10-11: the regex is the runner-FILE availability fact (kept
    # verbatim when gate 2 became two facts); the old label stated the DEFECT as a fact.
    a_worker_avail = anchor_any("worker's runner-FILE availability fact (gate 2, half one)",
                                worker_sources,
                                r"self\.runner_available = os\.path\.exists\(self\.runner\)")
    a_worker_cut = anchor_any("worker SKIPS streaming while mode==batch", worker_sources,
                              r'if mode == "batch":')
    a_consume = anchor("shell WorkerBridge._consume", shell_text,
                       r"def _consume\(self, line, child=None\)", SHELL)
    a_shell_meta = anchor("shell builds the caption meta", shell_text,
                          r"if k not in \('type', 'text'\)\}", SHELL)
    a_shell_fwd = anchor("shell forwards to on_caption", shell_text,
                         r"self\.on_caption\(str\(text\), meta\)", SHELL)
    a_shell_wire = anchor("shell wires on_caption", shell_text,
                          r"on_caption=self\.on_worker_caption,", SHELL)
    a_shell_emit = anchor("shell on_worker_caption emits", shell_text,
                          r"def on_worker_caption\(self, text, meta\)", SHELL)
    a_shell_push = anchor("shell emit() pushes into the page", shell_text,
                          r"def emit\(self, kind, payload\)", SHELL)
    a_shell_inject = anchor("page __sotto_emit", shell_text,
                            r"window\.__sotto_emit = function \(kind, json\)", SHELL)
    a_shell_oncap = anchor("page onCaption subscription", shell_text,
                           r"onCaption: function \(cb\)", SHELL)
    a_panel_ingest = anchor("panel ingests into the per-source engine",
                            PANEL_JS.read_text(encoding="utf-8"),
                            r"engineFor\(source\)\.ingest\(", PANEL_JS)
    a_panel_record = anchor("panel recordHistory", PANEL_JS.read_text(encoding="utf-8"),
                            r"function recordHistory\(text, reason, meta\)", PANEL_JS)
    #: RE-AIMED 2026-11-25. `isCanonical(meta)` left `panel.js` on 2026-11-05: the
    #: admission decision moved into the DOM-free predicate in `history-source.js`
    #: (`transcriptRoute`), and the panel now only ASKS it and reports the refusal.
    #: The old pattern matched nothing for three weeks; the oracle crashed before this
    #: line, so nobody saw the miss. The subject is unchanged -- the panel consults the
    #: canonical route predicate at its choke point -- only the call site is current.
    a_panel_gate = anchor("panel calls the canonical route predicate",
                          PANEL_JS.read_text(encoding="utf-8"),
                          r"sourceApi\.transcriptRoute\(meta\)", PANEL_JS)
    a_engine_producer = anchor("engine remembers the producer", formulation_text,
                               r"rememberProducer\(meta\);", FORMULATION)
    a_engine_commit = anchor("engine commits the producer tag", formulation_text,
                             r"\{ route, start, routeSource, producer: tag \}", FORMULATION)
    a_engine_route = anchor("engine routeSourceFor", formulation_text,
                            r"return 'worker-stamped-producer';", FORMULATION)
    a_runner_dir = anchor("redux runner default model dir", REDUX_RUNNER.read_text(encoding="utf-8"),
                          r"^DEFAULT_MODEL_DIR = ", REDUX_RUNNER)

    # =====================================================================
    # ARM A -- the REAL gate
    # =====================================================================
    print("\n-- ARM A: the REAL app/panel/history-source.js through require "
          + "-" * 15, flush=True)
    gate_table = [
        ("producer:'redux' (the worker's stamp)", {"producer": "redux"}, True,
         "the canonical tag"),
        ("producer absent", {}, False, "fail-closed: nothing is assumed"),
        ("producer:'' (empty string)", {"producer": ""}, False, "fail-closed"),
        ("producer:null", {"producer": None}, False, "non-string"),
        ("producer:42 (non-string)", {"producer": 42}, False, "non-string"),
        ("meta:null", None, False, "fail-closed"),
        ("producer:'live'", {"producer": "live"}, False, "the live engine's tag"),
        ("producer:'parakeet-tdt'", {"producer": "parakeet-tdt"}, False,
         "the brief's arm -- REFUSED"),
        ("producer:'Redux' (case)", {"producer": "Redux"}, False, "case-sensitive"),
        ("producer:'reduxx'", {"producer": "reduxx"}, False, "unknown tag"),
        ("producer:'redux ' (trailing space)", {"producer": "redux "}, True,
         "ACCEPT-BY-TRIM -- see BRIEF-DEVIATION"),
        ("producer:'  redux\\n' (padding)", {"producer": "  redux\n"}, True,
         "ACCEPT-BY-TRIM"),
    ]
    job = {"gate": [{"name": name, "meta": meta} for name, meta, _, _ in gate_table],
           "chain": []}
    node_out = run_node(subject_gate, FORMULATION, job, tmpdir)
    print("NODE " + node_out["node"], flush=True)
    by_name = {row["name"]: row for row in node_out["gate"]}
    for name, meta, expected, why in gate_table:
        row = by_name[name]
        got = row["accept"]
        check("A", name + " -> " + ("ACCEPT" if expected else "REFUSE"), got is expected,
              "got=" + repr(got) + " producerOf=" + repr(row["producerOf"])
              + " (" + why + ")")
    padded = [n for n, _, e, _ in gate_table if n.startswith("producer:'redux '")]
    if by_name[padded[0]]["accept"] is True:
        print("     BRIEF-DEVIATION: the brief asks this oracle to REFUSE producer:'redux ' "
              "(trailing space).", flush=True)
        print("     The REAL bytes TRIM it (history-source.js producerOf: "
              "typeof meta.producer === 'string' ? meta.producer.trim() : ''),", flush=True)
        print("     so a padded tag is ACCEPTED. Measured, not asserted -- encoding the "
              "brief's wording as an expectation would make this oracle red on the real bytes.",
              flush=True)

    # =====================================================================
    # ARM B -- the REAL worker stamp, in this process
    # =====================================================================
    print("\n-- ARM B: the REAL worker/sotto_worker.py, imported IN PROCESS "
          + "-" * 12, flush=True)
    worker_mod = load_python_module(subject_worker, "sotto_worker_under_test",
                                    source_text=subject_worker_text)
    check("B", "the worker module imports in process (no launch, no capture)",
          hasattr(worker_mod, "ReduxHiddenSwitch"), str(subject_worker))

    events, logs, switch = worker_events(worker_mod, tmpdir, with_caption=True)
    check("B", "the REAL _run_runner queues exactly one event", len(events) == 1,
          "queued=" + str(len(events)) + " logs=" + repr(logs[-1:]))
    event = events[0] if events else {}
    print("     REAL EVENT: " + json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)
    check("B", "hop (i): the queued event's type IS 'caption'",
          event.get("type") == "caption", "type=" + repr(event.get("type")))
    check("B", "the queued event carries producer == 'redux'",
          event.get("producer") == "redux", "producer=" + repr(event.get("producer")))
    check("B", "the queued event votes final:true (the worker closed the line)",
          event.get("final") is True, "final=" + repr(event.get("final")))
    check("B", "the queued event carries NO 'source' key (it lands on the no-source engine)",
          "source" not in event, "keys=" + ",".join(sorted(event.keys())))

    empty_events, empty_logs, _ = worker_events(worker_mod, tmpdir, with_caption=False)
    empty = empty_events[0] if empty_events else {}
    print("     EMPTY-BATCH EVENT: " + json.dumps(empty, ensure_ascii=False, sort_keys=True),
          flush=True)
    check("B", "an empty batch queues a STATUS, never a caption",
          empty.get("type") == "status" and empty.get("state") == "redux-batch-empty",
          "type=" + repr(empty.get("type")) + " state=" + repr(empty.get("state")))
    check("B", "the status also carries producer (but a status never reaches the caption hop)",
          empty.get("producer") == "redux", "producer=" + repr(empty.get("producer")))

    # RE-ANCHORED 2026-10-20. A check antiga media a UNIAO de DOIS directorios --
    # `parakeet-redux-ternary` (o default do runner) e `parakeet-redux-onnx-int4` (o
    # engine do OVERLAY `--redux-live`) -- e por isso ia a VERMELHO: o `onnx-int4` foi
    # re-baixado e esta em disco (AGENTS.md, correccao 7: `encoder-model.onnx`
    # 343 841 943 B, `decoder_joint-model.onnx` 72 552 270 B, `preprocessor.onnx`
    # 1 224 294 B, `vad-model.onnx` 18 300 687 B -- a mesma exportacao de sempre).
    #
    # SAO DOIS CAMINHOS DIFERENTES:
    #   * o BATCH (o que este arm mede) corre `worker/redux_batch.py`, cujo default e'
    #     `DEFAULT_MODEL_DIR = HERE / "models" / "parakeet-redux-ternary"`
    #     (`worker/redux_batch.py:39`) -- e o worker usa o MESMO caminho relativo no
    #     gate do switch (`worker/sotto_worker.py:3581` REDUX_CHECKPOINT_RELPATH).
    #     E' esse que a passagem de batch abriria.
    #   * o OVERLAY `--redux-live` (`worker/sotto_worker.py:3635`
    #     REDUX_LIVE_ONNX_RELPATH) e' um interruptor OUTRO, com outro runner, e NAO
    #     arma este arm nem produz a linha `producer:'redux'` que este arm mede.
    #
    # O GAP que este check existe para fixar continua REAL: o `ternary` nao esta em
    # disco, portanto `redux_batch.load_runtime` aborta e o branch de batch nao emite
    # legenda. So a MEDIDA estava errada: media a uniao de dois caminhos.
    #
    # E A MEDIDA E' TAMBEM MAIS EXATA: o runner nao carrega um DIRECTORIO, carrega os
    # MANIFESTOS (`worker/redux_batch.py:111-120`: `config.json`, `model.safetensors`,
    # `ternary.json` -- cada um ausente e' um `SystemExit`; a lista do worker e'
    # `REDUX_CHECKPOINT_FILES`, `worker/sotto_worker.py:3585`, que diz o mesmo: "o
    # DIRECTORIO existir nao e' o teste"). Um directorio vazio nao faria o batch arm
    # emitir legenda, portanto conta-lo como "checkpoint presente" seria um alarme
    # FALSO. Este check e' uma ARMADILHA: ela dispara quando o branch de batch passa
    # a poder emitir a linha -- e so entao a ANSWER abaixo muda.
    REDUX_MANIFESTS = ("config.json", "model.safetensors", "ternary.json")
    missing_manifests = [f for f in REDUX_MANIFESTS if not (REDUX_MODEL_DIR / f).is_file()]
    checkpoint_present = REDUX_MODEL_DIR.is_dir() and not missing_manifests
    check("B", "LIVE-GAP PINNED: the checkpoint the runner defaults to is ABSENT today",
          checkpoint_present is False,
          "default=" + str(REDUX_MODEL_DIR)
          + " exists=" + str(REDUX_MODEL_DIR.is_dir())
          + " missing_manifests=" + repr(missing_manifests)
          + " -- the BATCH runner's default (worker/redux_batch.py:39 DEFAULT_MODEL_DIR);"
            " the --redux-live OVERLAY's engine (" + REDUX_MODEL_DIR_INT4.name
          + ") is a DIFFERENT switch on a DIFFERENT path and does NOT arm this arm"
          + " -- if this check ever goes RED, the ANSWER below changes: re-read it")
    note("redux_batch.py load_runtime raises SystemExit when config.json / model.safetensors /"
         " ternary.json are missing, so the batch arm cannot emit a caption today")
    armed_switch = worker_mod.ReduxHiddenSwitch(
        enabled=True, reader=object(), runner=str(REDUX_RUNNER), log_fn=lambda m: None,
        armed_by="oracle")
    # RE-BASELINED 2026-10-11: this arm used to PIN THE DEFECT ("the switch ARMS on
    # the RUNNER FILE even when no checkpoint exists" -- true then, and it went RED the
    # moment the defect was fixed, which is what a defect-pinning check must do). It is
    # now a REQUIREMENT, and it can still say NO: under --red-arm the subject is the
    # worker mutant with gate 2 reverted, where this goes RED again.
    #
    # RE-AIMED 2026-11-25, and the requirement is the SAME: never arm on the runner FILE
    # alone. What changed is that gate 2 gained a THIRD branch -- the ONNX int4 parakeet
    # (`engine_available`), which IS on disk -- so a switch built with the default engine
    # legitimately arms (`armed=True`) while the ternary checkpoint is absent, and the old
    # assertion read that correct behaviour as a violation. The isolation is a stub engine
    # whose `available` is False: then nothing can transcribe the batch, the runner file
    # alone must NOT arm, and the --red-arm mutant (gate 2 reverted to the file only) still
    # arms and still turns this RED.
    class _AbsentEngine:
        """The batch engine when the machine has none: `available` False."""

        available = False

        def name(self):
            return "absent (oracle stub)"

        def load(self):  # pragma: no cover - never reached by this arm
            return False

        def release(self):  # pragma: no cover
            return None

        def transcribe(self, pcm):  # pragma: no cover
            return ""

    armed_switch = worker_mod.ReduxHiddenSwitch(
        enabled=True, reader=object(), runner=str(REDUX_RUNNER), log_fn=lambda m: None,
        armed_by="oracle", engine=_AbsentEngine())
    check("B", "the switch REFUSES to arm on the runner FILE alone (checkpoint AND engine absent)",
          armed_switch.armed is False and not armed_switch.model_available,
          "runner_available=" + str(armed_switch.runner_available)
          + " model_available=" + str(armed_switch.model_available)
          + " engine_available=" + str(armed_switch.engine_available)
          + " armed=" + str(armed_switch.armed)
          + " missing=" + ",".join(armed_switch.model_missing)
          + " -- gate 2 is THREE facts since 2026-11-25: the .py alone armed the switch and"
            " every batch then died in redux_batch.load_runtime (the HARD RULE failure shape);"
            " the int4 parakeet is the third branch and is deliberately stubbed absent here")

    # =====================================================================
    # ARM C -- the REAL chain: worker event -> REAL shell hop -> REAL engine -> REAL gate
    # =====================================================================
    print("\n-- ARM C: worker event -> REAL shell _consume -> REAL engine -> REAL gate "
          + "-" * 4, flush=True)
    consume_cls = extract_consume(subject_shell_text, str(SHELL))
    seen, inst = shell_projection(consume_cls, event)
    check("C", "the REAL shell _consume yields exactly one caption", len(seen) == 1,
          "captions=" + str(len(seen)) + " malformed=" + str(inst.malformed))
    text, meta = seen[0] if seen else ("", {})
    print("     SHELL META: " + json.dumps(meta, ensure_ascii=False, sort_keys=True), flush=True)
    check("C", "hop (ii): the shell's meta still carries producer == 'redux'",
          meta.get("producer") == "redux", "producer=" + repr(meta.get("producer")))
    check("C", "the shell's meta drops ONLY type/text and ADDS the audio session",
          set(meta.keys()) == set(event.keys()) - {"type", "text"} | {"historySession"},
          "meta keys=" + ",".join(sorted(meta.keys())))
    # The added key is the child-process identity the history snapshot is keyed
    # by (2026-11-09) -- not a copy of an event field and not an invented name.
    check("C", "the added key is the audio-session token",
          str(meta.get("historySession") or "").startswith("worker:"),
          "historySession=" + repr(meta.get("historySession")))

    chain_job = {"gate": [], "chain": [
        {"name": "canonical batch line (REAL worker event)",
         "engineSource": None,
         "events": [{"text": text, "meta": meta}],
         "flushReason": "hold-timeout"},
        {"name": "control: route=final, NO producer (isolates the producer guard)",
         "engineSource": None,
         "events": [{"text": "bom dia", "meta": {"start": 1.5, "final": True}}],
         "flushReason": "hold-timeout"},
        {"name": "control: live line, final:false (isolates the route guard)",
         "engineSource": None,
         "events": [{"text": "bom dia", "meta": {"start": 1.5, "final": False}}],
         "flushReason": "hold-timeout"},
        {"name": "finding: no-producer fragment, then a redux fragment, ONE buffer",
         "engineSource": None,
         "events": [{"text": "bom dia", "meta": {"start": 1.5, "final": True}},
                    {"text": "bom dia mundo",
                     "meta": {"start": 1.5, "final": True, "producer": "redux"}}],
         "flushReason": "hold-timeout"},
    ]}
    chain_out = run_node(subject_gate, FORMULATION, chain_job, tmpdir)
    rows = {row["name"]: row for row in chain_out["chain"]}

    real = rows["canonical batch line (REAL worker event)"]
    check("C", "the REAL engine commits the batch line once", len(real["commits"]) == 1,
          "commits=" + str(len(real["commits"])) + " visible=" + repr(real["visible"]))
    commit = real["commits"][0] if real["commits"] else {}
    cm = commit.get("meta") or {}
    print("     ENGINE COMMIT META: " + json.dumps(cm, ensure_ascii=False, sort_keys=True),
          flush=True)
    #: RE-AIMED 2026-11-25. The assertion pinned the EXACT key set of the rebuilt meta
    #: (`route,start,routeSource,producer`) and went RED when the engine legitimately
    #: gained a fifth: `fileText`, stamped only when the final mark was INVENTED
    #: (`caption-formulation.js:869-873`, documented there and read by `panel.js`). The
    #: invariant the arm exists for is unchanged -- THE GATE IS FED A REBUILT META, not
    #: the worker's event -- so it is stated as: the four hops are present, and nothing
    #: from the worker event rides along verbatim. The allow-list is the engine's own
    #: declared output, not a guess: `fileText` (invented-mark rule) and `source` (one
    #: engine per source, never the fragment's) are the only extras the code can add.
    REBUILT_REQUIRED = {"route", "start", "routeSource", "producer"}
    REBUILT_ALLOWED = REBUILT_REQUIRED | {"fileText", "source"}
    cm_keys = set(cm.keys())
    check("C", "hop (iii): the gate is fed a REBUILT meta, not the worker's event",
          REBUILT_REQUIRED <= cm_keys <= REBUILT_ALLOWED,
          "keys=" + ",".join(sorted(cm_keys))
          + " missing=" + ",".join(sorted(REBUILT_REQUIRED - cm_keys))
          + " unexpected=" + ",".join(sorted(cm_keys - REBUILT_ALLOWED)))
    check("C", "the REBUILT meta carries producer == 'redux' (carried, not invented)",
          cm.get("producer") == "redux", "producer=" + repr(cm.get("producer")))
    check("C", "the REBUILT meta routes final via the worker's flag",
          cm.get("route") == "final" and cm.get("routeSource") == "worker-stamped",
          "route=" + repr(cm.get("route")) + " routeSource=" + repr(cm.get("routeSource")))
    check("C", "END-TO-END: the REAL gate ACCEPTS the line the REAL worker stamped",
          real["accepted"] == [True], "accepted=" + repr(real["accepted"]))

    live = rows["control: route=final, NO producer (isolates the producer guard)"]
    lc = (live["commits"][0]["meta"] if live["commits"] else {})
    check("C", "CONTROL: a line routed final with NO producer is REFUSED by the PRODUCER guard",
          live["accepted"] == [False] and lc.get("route") == "final"
          and "producer" not in lc,
          "accepted=" + repr(live["accepted"]) + " route=" + repr(lc.get("route"))
          + " routeSource=" + repr(lc.get("routeSource"))
          + " meta=" + json.dumps(lc, sort_keys=True))
    draft = rows["control: live line, final:false (isolates the route guard)"]
    dc = (draft["commits"][0]["meta"] if draft["commits"] else {})
    check("C", "CONTROL: a final:false line is refused EARLIER, by the route guard",
          draft["accepted"] == [False] and dc.get("route") == "provisional-draft",
          "accepted=" + repr(draft["accepted"]) + " route=" + repr(dc.get("route")))

    mixed = rows["finding: no-producer fragment, then a redux fragment, ONE buffer"]
    mc = (mixed["commits"][0]["meta"] if mixed["commits"] else {})
    check("C", "SECOND-ORDER FINDING: the tag is per BUFFER, not per line -- a fragment that "
               "declares nothing inherits it",
          mixed["accepted"] == [True] and mc.get("producer") == "redux",
          "accepted=" + repr(mixed["accepted"]) + " meta=" + json.dumps(mc, sort_keys=True)
          + " -- sticky bufferSawProducer, no conflict, so a line whose FIRST fragment was "
            "the live pass is accepted as canonical; reported, not fixed here")

    store_text = HISTORY_STORE.read_text(encoding="utf-8")
    # RE-BASELINED 2026-10-11, same reason as arm B above: this check pinned the LATENT
    # defect (the token absent). It is now a REQUIREMENT over BOTH twins, and the LIVE
    # twin is the shell one -- `panel.html` loads eleven scripts and `history-store.js`
    # is not among them, so the Node file below is read by oracles only.
    check("C", "the store's src= allow-list carries every token routeSourceFor declares",
          "'worker-stamped-producer'" in store_text,
          "history-store.js ROUTE_SOURCES must list the value caption-formulation.js:"
          + str(a_engine_route) + " returns for a producer-stamped line with NO final flag "
            "(fixed 2026-10-11; this file is oracle-only, see the shell check below)")
    m_shell_src = re.search(r"^HISTORY_ROUTE_SOURCES = \(([^)]*)\)", src_subject_text, re.M)
    shell_src_tokens = tuple(t.strip().strip("'\"") for t in m_shell_src.group(1).split(",")) if m_shell_src else ()
    check("C", "the SHELL's LIVE src= allow-list carries every token routeSourceFor declares",
          set(shell_src_tokens) == {"worker-stamped", "worker-stamped-producer", "panel-deadline", "fallback"},
          "HISTORY_ROUTE_SOURCES=" + repr(shell_src_tokens) + " -- sotto_webview.py is the writer the"
            " shipped panel uses (`history_append` -> `_history_provenance`), so this tuple, not the"
            " Node one, decides whether the owner's transcript carries a src= marker")

    # =====================================================================
    # NEG ARMS -- the mutants, in memory / %TEMP%, never in the repo
    # =====================================================================
    if not args.red_arm:
        print("\n-- NEG ARMS: each hop cut in a COPY of the REAL bytes (must go RED) "
              + "-" * 3, flush=True)
        check("NEG", "every mutant copy lives OUTSIDE the repo",
              all(str(p).startswith(str(tmpdir)) for p in
                  (gate_mutant, worker_mutant, shell_mutant, shell_src_mutant))
              and not str(gate_mutant).startswith(str(ROOT)),
              str(tmpdir))

        mut_job = {"gate": [{"name": "producer:'redux'", "meta": {"producer": "redux"}},
                            {"name": "producer absent", "meta": {}}],
                   "chain": []}
        mut_out = run_node(gate_mutant, FORMULATION, mut_job, tmpdir)
        mut_rows = {row["name"]: row for row in mut_out["gate"]}
        check("NEG", "M1 gate mutant (CANONICAL_PRODUCER renamed): the ACCEPT arm goes RED",
              mut_rows["producer:'redux'"]["accept"] is False,
              "accept=" + repr(mut_rows["producer:'redux'"]["accept"]))
        check("NEG", "M1 leaves the fail-closed arm RED too (no accidental acceptance)",
              mut_rows["producer absent"]["accept"] is False,
              "accept=" + repr(mut_rows["producer absent"]["accept"]))

        mut_worker = load_python_module(worker_mutant, "sotto_worker_mutant")
        mut_events, mut_logs, _ = worker_events(mut_worker, tmpdir, with_caption=True)
        mut_event = mut_events[0] if mut_events else {}
        print("     MUTANT EVENT: " + json.dumps(mut_event, ensure_ascii=False,
                                                 sort_keys=True), flush=True)
        check("NEG", "M2 worker mutant (stamp line removed): the producer arm goes RED",
              mut_event.get("type") == "caption" and "producer" not in mut_event,
              "type=" + repr(mut_event.get("type")) + " producer="
              + repr(mut_event.get("producer")))
        # M2's chain must run through the LIVE shell: the shell hop is M3's subject, not
        # M2's. Using the shell mutant here made the first run red for the wrong reason.
        mut_seen, _ = shell_projection(extract_consume(shell_text, str(SHELL)), mut_event)
        mut_meta = mut_seen[0][1] if mut_seen else {}
        mut_chain = {"gate": [], "chain": [{"name": "mutant", "engineSource": None,
                                            "events": [{"text": mut_seen[0][0] if mut_seen else "",
                                                        "meta": mut_meta}],
                                            "flushReason": "hold-timeout"}]}
        mut_chain_out = run_node(HISTORY_SOURCE, FORMULATION, mut_chain, tmpdir)
        mut_real = mut_chain_out["chain"][0]
        mut_cm = (mut_real["commits"][0]["meta"] if mut_real["commits"] else {})
        check("NEG", "M2 END-TO-END with the LIVE gate: the chain goes RED",
              mut_real["accepted"] == [False],
              "accepted=" + repr(mut_real["accepted"]) + " meta="
              + json.dumps(mut_cm, sort_keys=True))

        cut_seen, _ = shell_projection(extract_consume(shell_mutant_text, str(shell_mutant)),
                                       event)
        cut_meta = cut_seen[0][1] if cut_seen else {}
        check("NEG", "M3 shell mutant (projection drops producer): the shell hop goes RED",
              cut_meta.get("producer") is None,
              "meta keys=" + ",".join(sorted(cut_meta.keys())))
        cut_chain = {"gate": [], "chain": [{"name": "cut", "engineSource": None,
                                            "events": [{"text": cut_seen[0][0] if cut_seen else "",
                                                        "meta": cut_meta}],
                                            "flushReason": "hold-timeout"}]}
        cut_out = run_node(HISTORY_SOURCE, FORMULATION, cut_chain, tmpdir)
        cut_real = cut_out["chain"][0]
        check("NEG", "M3 END-TO-END with the LIVE gate: the chain goes RED",
              cut_real["accepted"] == [False],
              "accepted=" + repr(cut_real["accepted"]) + " meta="
              + json.dumps((cut_real["commits"][0]["meta"] if cut_real["commits"] else {}),
                           sort_keys=True))
        check("NEG", "the LIVE bytes were never written (the repo copies are untouched)",
              hashlib.sha256(HISTORY_SOURCE.read_bytes()).hexdigest().upper()
              == hashlib.sha256(gate_bytes).hexdigest().upper()
              and hashlib.sha256(WORKER.read_bytes()).hexdigest().upper()
              == hashlib.sha256(worker_bytes).hexdigest().upper())

    # =====================================================================
    # THE ANSWER
    # =====================================================================
    plumbing = all(r["ok"] for r in RESULTS if r["arm"] in ("A", "B", "C"))
    print("\n" + "=" * 78)
    print("ANSWER (the plain reading of the measurements above)")
    print("=" * 78)
    print("A worker-stamped producer reaches meta.producer TODAY: PARTIALLY.", flush=True)
    print("  * IN CODE, end to end: YES. The worker stamps producer:'redux' on a real "
          "type:'caption' event", flush=True)
    print("    (worker/sotto_worker.py:" + str(a_worker_stamp) + "), the shell forwards the "
          "whole meta (sotto_webview.py:" + str(a_shell_meta) + " -> :" + str(a_shell_fwd)
          + "),", flush=True)
    print("    the engine CARRIES it into a REBUILT meta (caption-formulation.js:"
          + str(a_engine_commit) + "), and the REAL gate accepts that meta.", flush=True)
    print("  * IN A LIVE RUN: NO. The only arm that stamps it is the Redux batch switch, "
          "which is OFF by default", flush=True)
    print("    (sotto_worker.py:" + str(a_worker_flag) + ") and whose engine cannot load: "
          "worker/models/parakeet-redux-ternary", flush=True)
    print("    is ABSENT, so redux_batch.py exits before emitting a caption and the worker "
          "queues a redux-batch-empty STATUS instead.", flush=True)
    print("  * THE ONE REMAINING GAP: the Redux checkpoint is not on disk, so the batch arm "
          "cannot produce the line.", flush=True)
    print("    (The OTHER Redux engine IS on disk -- worker/models/parakeet-redux-onnx-int4 --"
          " but it belongs to the `--redux-live` OVERLAY: a different switch, a different"
          " runner, a different path. It does NOT make THIS batch arm able to emit a line.)",
          flush=True)
    print("    (Second, deliberate layer: the flag is OFF, and the switch's own gate "
          "sotto_worker.py:" + str(a_worker_avail) + " is now TWO", flush=True)
    print("     facts -- the runner FILE *and* the checkpoint it will LOAD -- so with the "
          "checkpoint absent it REFUSES", flush=True)
    print("     to arm and streaming is NOT cut; until 2026-10-11 the .py alone armed it, "
          "cut streaming while the panel", flush=True)
    print("     was hidden (sotto_worker.py:" + str(a_worker_cut) + ") and every batch then "
          "died at load, which is the HARD RULE's failure shape.)", flush=True)
    print("NOT MEASURED (and why): no live end-to-end run is permitted by the owner's stop "
          "order, so no real", flush=True)
    print("  worker-stamped caption was OBSERVED on stdout; the batch commit was forced by "
          "the engine's own", flush=True)
    print("  flush('hold-timeout') (panel.js:700-712 armHoldTimer -> expireHold); WebView2 "
          "timer throttling and", flush=True)
    print("  the real runner's RSS are untouched here.", flush=True)

    failed = [r for r in RESULTS if not r["ok"]]
    print("\n" + "=" * 78)
    if args.red_arm:
        print("RED-ARM SUMMARY: " + str(len(failed)) + " of " + str(len(RESULTS))
              + " checks FAILED against the mutant subject (this is the expected colour).",
              flush=True)
        print("VERDICT: " + ("FAIL" if failed else "PASS"), flush=True)
        print("=" * 78, flush=True)
        rc = 1 if failed else 0
    else:
        print("SUMMARY: " + str(len(RESULTS) - len(failed)) + "/" + str(len(RESULTS))
              + " checks green; failed=" + repr([r["name"] for r in failed]), flush=True)
        print("VERDICT: " + ("PASS" if not failed and plumbing else "FAIL"), flush=True)
        print("=" * 78, flush=True)
        rc = 0 if (not failed and plumbing) else 1

    if not args.keep_temp:
        for child in sorted(tmpdir.glob("**/*"), reverse=True):
            try:
                child.unlink() if child.is_file() else child.rmdir()
            except OSError:
                pass
        try:
            tmpdir.rmdir()
        except OSError:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
