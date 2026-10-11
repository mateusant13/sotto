#!/usr/bin/env python3
"""Sotto -- the REDUX ARM GATE, both colours, IN PROCESS (nothing is launched).

TWO DEFECTS, ONE INSTRUMENT.

DEFECT A -- worker/sotto_worker.py, class ReduxHiddenSwitch (the
--redux-when-hidden switch, DEFAULT OFF). Until 2026-10-11 the gate was ONE fact:

    self.runner_available = os.path.exists(self.runner)
    self.armed = bool(self.enabled and self.runner_available)

THE RUNNER FILE IS NOT THE ENGINE. _run_runner invokes the runner with NO
--model-dir, so the runner resolves its own models/parakeet-redux-ternary
(worker/redux_batch.py: DEFAULT_MODEL_DIR) and load_runtime raises SystemExit on
the first missing manifest. With that checkpoint absent -- measured on this box
today: worker/models/ holds ONE directory, nemotron-3.5-asr-streaming-0.6b-int8
-- an armed switch cuts the streaming decode while the panel is hidden (asr_thread
skips streaming in batch mode) and every batch pass dies at load: the owner is
left with NO transcriber, silently. The gate is now TWO facts, and a refusal is
LOUD, ONCE, and names the missing path.

DEFECT B -- app/panel/history-store.js, ROUTE_SOURCES (the src= allow-list). It
omitted 'worker-stamped-producer', a token caption-formulation.js
routeSourceFor() declares (:501). A line carrying it was written with no src=
marker at all.

WHAT THIS RUNS (all in process; the only child process is node, invisible):
  ARM G (default): the REAL bytes as shipped.
    W: worker/sotto_worker.py imported by path. GREEN colour: a %TEMP% runner
       plus the checkpoint it derives arms the switch, the mode machine still
       switches stream -> batch -> stream, and the armed boot line keeps its
       shape. RED colour: the REAL runner with the REAL (absent) checkpoint
       refuses -- one line, reason=checkpoint-missing, naming the directory and
       every missing manifest -- and stays inert.
    J: app/panel/history-store.js required by node with SOTTO_HISTORY_ROOT in
       %TEMP%. Every token caption-formulation.js declares is appended through
       the store's OWN append() and must carry its src= marker.
  --neg-arm: MUTANTS of the real bytes, built in memory and written to %TEMP%.
    Every mutant must make the arms that should notice go RED, and no other arm
    may move; a comment-only control mutant must move NOTHING (an instrument
    that reddens on any diff proves nothing). An unbuildable mutant is a SETUP
    ERROR (rc=2), never a silent pass.

Exit codes: 0 PASS, 1 FAIL, 2 SETUP ERROR.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WORKER = REPO / "worker" / "sotto_worker.py"
RUNNER = REPO / "worker" / "redux_batch.py"
STORE = REPO / "app" / "panel" / "history-store.js"
FORMULATION = REPO / "app" / "panel" / "caption-formulation.js"
MODELS_DIR = REPO / "worker" / "models"
REAL_CHECKPOINT = MODELS_DIR / "parakeet-redux-ternary"

MANIFESTS = ("config.json", "model.safetensors", "ternary.json")
DECLARED_SOURCES = ("worker-stamped", "worker-stamped-producer", "panel-deadline", "fallback")
CREATE_NO_WINDOW = 0x08000000
NODE_EXE = shutil.which("node") or "node"

SUBJECTS = (WORKER, RUNNER, STORE, FORMULATION)


class SetupError(Exception):
    """An arm could not be built. rc=2 -- NEVER a silent pass."""


class Run:
    def __init__(self, label):
        self.label = label
        self.rows = []

    def check(self, cid, ok, detail=""):
        ok = bool(ok)
        self.rows.append((cid, ok, detail))
        print(f"  {'GREEN' if ok else 'RED  '} {cid}" + (f" -- {detail}" if detail else ""))
        return ok

    def red(self):
        return [cid for cid, ok, _ in self.rows if not ok]

    def summary(self):
        return f"{len(self.rows) - len(self.red())}/{len(self.rows)} checks green; red={self.red()}"


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def pin_line(path: Path) -> str:
    data = path.read_bytes()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime))
    return (f"PIN {path.relative_to(REPO).as_posix()} bytes={len(data)} "
            f"sha256={sha256_of(data)} mtime={stamp}")


def make_temp_root() -> Path:
    base = (os.environ.get("SOTTO_ORACLE_TMP") or os.environ.get("TMPDIR")
            or tempfile.gettempdir())
    os.makedirs(base, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="redux-arm-weights-", dir=base))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise SetupError(f"cannot build an import spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 -- a broken import is a setup failure
        raise SetupError(f"importing {path} raised {type(exc).__name__}: {exc}")
    return mod


class FakeReader:
    """The smallest thing ReduxHiddenSwitch accepts as a visibility channel."""

    def __init__(self, visible, why="oracle", age=0.0):
        self.visible = bool(visible)
        self.why = why
        self.age = age
        self.path = "<oracle-fake-visibility>"

    def read(self):
        return self.visible, self.why, self.age


def make_runner_and_checkpoint(root, name, manifests=MANIFESTS):
    """A %TEMP% tree shaped the way the worker's own derivation expects it."""
    box = Path(root) / name
    box.mkdir(parents=True, exist_ok=True)
    runner = box / "redux_batch.py"
    runner.write_text("# oracle stand-in runner: the gate never executes it\n", encoding="utf-8")
    ckpt = box / "models" / "parakeet-redux-ternary"
    ckpt.mkdir(parents=True, exist_ok=True)
    for manifest in manifests:
        (ckpt / manifest).write_text("oracle\n", encoding="utf-8")
    return runner, ckpt


def declared_sources():
    """The src= tokens caption-formulation.js routeSourceFor() can return."""
    text = FORMULATION.read_text(encoding="utf-8")
    marker = "function routeSourceFor"
    if marker not in text:
        raise SetupError(f"no {marker!r} in {FORMULATION.name}")
    rest = text[text.index(marker):]
    end = rest.find("\n  }")
    if end < 0:
        raise SetupError("cannot find the end of routeSourceFor")
    body = rest[:end]
    toks = re.findall(r"return\s+'([^']+)'", body)
    for match in re.finditer(r"\?\s*'([^']+)'\s*:\s*'([^']+)'", body):
        toks.extend(match.groups())
    if set(toks) != set(DECLARED_SOURCES) or len(set(toks)) != len(DECLARED_SOURCES):
        raise SetupError(f"routeSourceFor declares {sorted(set(toks))!r}, expected "
                         f"{sorted(DECLARED_SOURCES)!r} -- the extraction or the file moved")
    return tuple(DECLARED_SOURCES)


NODE_DRIVER = r"""
const fs = require('node:fs');
const path = require('node:path');
const out = { ok: false, error: null, rows: [], files: {}, unknownWritten: false,
              provisional: 'unset', root: null };
try {
  const store = require(process.env.ORACLE_STORE);
  const tokens = JSON.parse(process.env.ORACLE_TOKENS);
  out.root = store.ROOT;
  let n = 0;
  for (const tok of tokens) {
    n += 1;
    const entry = store.append('oracle line ' + n,
      { route: 'final', start: 1.5, routeSource: tok, reason: 'oracle' });
    out.rows.push({ token: tok, written: !!entry, file: entry ? entry.path : null });
  }
  const unknown = store.append('oracle unknown token',
    { route: 'final', start: 2.5, routeSource: 'not-a-real-source', reason: 'oracle' });
  out.unknownWritten = !!unknown;
  const prov = store.append('oracle provisional line',
    { route: 'provisional-draft', start: 3.5, routeSource: tokens[0], reason: 'oracle' });
  out.provisional = prov === null ? 'null' : 'entry';
  const walk = (dir) => {
    let names = [];
    try { names = fs.readdirSync(dir); } catch (err) { return; }
    for (const name of names) {
      const full = path.join(dir, name);
      if (fs.statSync(full).isDirectory()) walk(full);
      else out.files[path.relative(process.env.ORACLE_ROOT, full)] = fs.readFileSync(full, 'utf8');
    }
  };
  walk(process.env.ORACLE_ROOT);
  out.ok = true;
} catch (err) {
  out.error = String((err && err.message) || err);
}
process.stdout.write(JSON.stringify(out));
"""


def run_node_store(store_path: Path, root: Path, tokens):
    env = dict(os.environ)
    env["ORACLE_STORE"] = str(store_path)
    env["ORACLE_ROOT"] = str(root)
    env["ORACLE_TOKENS"] = json.dumps(list(tokens))
    env["SOTTO_HISTORY_ROOT"] = str(root)
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.run([NODE_EXE, "-e", NODE_DRIVER], capture_output=True,
                              timeout=120, creationflags=flags, env=env)
    except FileNotFoundError:
        raise SetupError(f"node not found at {NODE_EXE}")
    except subprocess.TimeoutExpired:
        raise SetupError("the node store driver timed out after 120 s")
    if proc.returncode != 0:
        raise SetupError(f"node exited {proc.returncode}: "
                         f"{proc.stderr.decode('utf-8', 'replace')[:400]}")
    try:
        out = json.loads(proc.stdout.decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        raise SetupError(f"node output was not JSON ({exc}): {proc.stdout[:200]!r}")
    if not out.get("ok"):
        raise SetupError(f"the store driver failed: {out.get('error')}")
    return out


def arm_worker(run, mod, tag, runner_mod, temp_root, worker_text):
    relpath = getattr(mod, "REDUX_CHECKPOINT_RELPATH", None)
    manifests = tuple(getattr(mod, "REDUX_CHECKPOINT_FILES", ()) or ())
    run.check(f"{tag}W1-checkpoint-constants",
              relpath == os.path.join("models", "parakeet-redux-ternary")
              and manifests == MANIFESTS,
              f"REDUX_CHECKPOINT_RELPATH={relpath!r} REDUX_CHECKPOINT_FILES={manifests!r}")

    derived = str(mod.redux_checkpoint_dir(str(RUNNER)))
    runner_default = str(runner_mod.DEFAULT_MODEL_DIR)
    run.check(f"{tag}W2-runner-own-default-agrees",
              os.path.normcase(os.path.abspath(derived))
              == os.path.normcase(os.path.abspath(runner_default)),
              f"worker derives {derived} | redux_batch.DEFAULT_MODEL_DIR {runner_default}")

    runner_text = RUNNER.read_text(encoding="utf-8")
    if "def load_runtime(" in runner_text:
        body = runner_text.split("def load_runtime(", 1)[1].split("\n    import torch", 1)[0]
    else:
        body = ""
    # ONLY the manifest predicate -- (model_dir / "NAME") -- so a default like
    # load_runtime's own device="cpu" can never be read as a checkpoint file.
    order = re.findall(r'\(model_dir / "([^"]+)"\)', body)
    run.check(f"{tag}W3-manifest-order-matches-load_runtime",
              tuple(order) == MANIFESTS and tuple(order) == manifests,
              f"load_runtime tests for {order!r} in that order; the gate demands "
              f"{list(manifests)!r}")

    run.check(f"{tag}W4-flag-default-and-producer-literal",
              getattr(mod, "REDUX_WHEN_HIDDEN_DEFAULT", None) is False
              and getattr(mod, "REDUX_PRODUCER", None) == "redux",
              f"REDUX_WHEN_HIDDEN_DEFAULT={getattr(mod, 'REDUX_WHEN_HIDDEN_DEFAULT', None)!r} "
              f"REDUX_PRODUCER={getattr(mod, 'REDUX_PRODUCER', None)!r}")

    # -- GREEN colour: the checkpoint IS there ------------------------------
    runner, ckpt = make_runner_and_checkpoint(temp_root, "green-derived")
    logs = []
    sw = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                               runner=str(runner), log_fn=logs.append)
    run.check(f"{tag}W5-arms-when-the-checkpoint-is-there",
              sw.armed is True and list(sw.model_missing) == []
              and os.path.normcase(sw.model_dir) == os.path.normcase(str(ckpt)),
              f"armed={sw.armed} model_dir={sw.model_dir} missing={list(sw.model_missing)}")
    sw.boot_line()
    armed_line = logs[0] if logs else ""
    print(f"  EVIDENCE {tag}armed-line={armed_line}")
    run.check(f"{tag}W6-armed-line-shape-unchanged",
              bool(re.match(r"^REDUX_SWITCH armed=true by=--redux-when-hidden "
                            r"hidden_after_s=[\d.]+ batch_interval_s=[\d.]+ "
                            r"max_audio_s=[\d.]+ min_free_mb=[\d.]+ runner=.+ "
                            r"visibility=.+$", armed_line)),
              armed_line)

    other = Path(temp_root) / "explicit-ckpt"
    other.mkdir(parents=True, exist_ok=True)
    for manifest in MANIFESTS:
        (other / manifest).write_text("oracle\n", encoding="utf-8")
    logs_explicit = []
    sw_explicit = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                                        runner=str(RUNNER), log_fn=logs_explicit.append,
                                        model_dir=str(other))
    run.check(f"{tag}W7-explicit-model-dir-wins-over-the-derivation",
              sw_explicit.armed is True
              and os.path.normcase(sw_explicit.model_dir) == os.path.normcase(str(other)),
              f"armed={sw_explicit.armed} model_dir={sw_explicit.model_dir}")

    reader = FakeReader(True, "oracle-visible")
    sw_modes = mod.ReduxHiddenSwitch(enabled=True, reader=reader, runner=str(runner),
                                     log_fn=[].append)
    t0 = 1000.0
    m1 = sw_modes.tick(now=t0)
    reader.visible = False
    sw_modes.tick(now=t0 + 0.1)
    m2 = sw_modes.tick(now=t0 + sw_modes.hidden_after_s + 1.0)
    reader.visible = True
    m3 = sw_modes.tick(now=t0 + sw_modes.hidden_after_s + 2.0)
    run.check(f"{tag}W8-mode-machine-still-switches",
              (m1, m2, m3) == ("stream", "batch", "stream") and sw_modes.switches == 2,
              f"tick sequence={(m1, m2, m3)} switches={sw_modes.switches}")

    # -- RED colour: the REAL runner, the REAL (absent) checkpoint ----------
    logs_real = []
    sw_real = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                                    runner=str(RUNNER), log_fn=logs_real.append)
    run.check(f"{tag}W9-real-disk-refuses",
              sw_real.armed is False and list(sw_real.model_missing) == list(MANIFESTS)
              and os.path.normcase(sw_real.model_dir) == os.path.normcase(str(REAL_CHECKPOINT)),
              f"armed={sw_real.armed} model_dir={sw_real.model_dir} "
              f"missing={list(sw_real.model_missing)}")
    sw_real.boot_line()
    refusal_line = logs_real[0] if logs_real else ""
    print(f"  EVIDENCE {tag}refusal-line={refusal_line}")
    run.check(f"{tag}W10-refusal-names-reason-and-path",
              "REDUX_SWITCH_REFUSED armed=false" in refusal_line
              and "reason=checkpoint-missing" in refusal_line
              and os.path.normcase(f"model_dir={REAL_CHECKPOINT}") in os.path.normcase(refusal_line)
              and f"missing={','.join(MANIFESTS)}" in refusal_line,
              refusal_line)

    before = len(logs_real)
    for step in range(10):
        sw_real.tick(now=t0 + step)
    kick = sw_real.maybe_kick("oracle")
    after = len(logs_real)
    run.check(f"{tag}W11-refusal-is-one-line-and-inert",
              before == 1 and after == 1 and kick is False and sw_real.mode == "stream",
              f"lines_after_boot={before} lines_after_10_ticks={after} "
              f"maybe_kick={kick} mode={sw_real.mode}")

    partial_runner, partial_ckpt = make_runner_and_checkpoint(
        temp_root, "partial", manifests=("config.json",))
    logs_partial = []
    sw_partial = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                                       runner=str(partial_runner), log_fn=logs_partial.append)
    sw_partial.boot_line()
    partial_line = logs_partial[0] if logs_partial else ""
    run.check(f"{tag}W12-partial-checkpoint-names-what-is-missing",
              sw_partial.armed is False
              and list(sw_partial.model_missing) == ["model.safetensors", "ternary.json"]
              and "reason=checkpoint-missing" in partial_line
              and os.path.normcase(f"model_dir={partial_ckpt}") in os.path.normcase(partial_line)
              and "missing=model.safetensors,ternary.json" in partial_line,
              f"missing={list(sw_partial.model_missing)} line={partial_line}")

    missing_runner = Path(temp_root) / "not-here" / "redux_batch.py"
    logs_norun = []
    sw_norun = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                                     runner=str(missing_runner), log_fn=logs_norun.append,
                                     model_dir=str(ckpt))
    sw_norun.boot_line()
    norun_line = logs_norun[0] if logs_norun else ""
    run.check(f"{tag}W13-runner-missing-reason-still-distinct",
              sw_norun.armed is False and "reason=runner-missing" in norun_line
              and "checkpoint-missing" not in norun_line,
              norun_line)

    logs_off = []
    sw_off = mod.ReduxHiddenSwitch(enabled=False, reader=FakeReader(True),
                                   runner=str(runner), log_fn=logs_off.append,
                                   model_dir=str(ckpt))
    sw_off.boot_line()
    run.check(f"{tag}W14-flag-off-is-still-gate-1",
              sw_off.armed is False and logs_off == [] and sw_off.tick(now=t0) == "stream",
              f"armed={sw_off.armed} log_lines={len(logs_off)}")

    call_count = len(re.findall(r"switch = ReduxHiddenSwitch\(", worker_text))
    call_window = ""
    if call_count:
        start = worker_text.index("switch = ReduxHiddenSwitch(")
        call_window = worker_text[start:start + 1000]
    run.check(f"{tag}W15-call-site-uses-the-derivation",
              call_count == 1
              and "runner=args.redux_batch" in call_window
              and "model_dir=" not in call_window
              and "switch.boot_line()" in worker_text
              and "reduxArmed=switch.armed" in worker_text,
              f"call sites={call_count} "
              f"runner=args.redux_batch={'runner=args.redux_batch' in call_window} "
              f"model_dir-in-call={'model_dir=' in call_window}")


def arm_store(run, store_text, tag, temp_root, declared):
    allow = re.search(r"const ROUTE_SOURCES = \[(.*?)\];", store_text, re.S)
    if not allow:
        raise SetupError(f"{tag}: no const ROUTE_SOURCES = [...] in the store bytes")
    allowed = re.findall(r"'([^']+)'", allow.group(1))
    missing = [tok for tok in declared if tok not in allowed]
    print(f"  EVIDENCE {tag}declared-sources={list(declared)}")
    print(f"  EVIDENCE {tag}allow-list={allowed}")
    run.check(f"{tag}J1-allow-list-covers-every-declared-token",
              not missing, f"missing={missing}")
    run.check(f"{tag}J2-allow-list-has-no-extras",
              len(allowed) == len(declared) and set(allowed) == set(declared),
              f"allow-list={allowed} declared={list(declared)}")

    box = Path(temp_root) / f"store-{tag.strip(':') or 'green'}"
    box.mkdir(parents=True, exist_ok=True)
    store_file = box / "history-store.js"
    store_file.write_text(store_text, encoding="utf-8")
    root = box / "history-root"
    root.mkdir(parents=True, exist_ok=True)
    out = run_node_store(store_file, root, declared)
    text = "\n".join(out["files"].values())
    print(f"  EVIDENCE {tag}history-root={out['root']}")
    for line in text.splitlines():
        print(f"  EVIDENCE {tag}written: {line}")

    expected = {tok: f"<!-- route=final start=1.50 src={tok} reason=oracle -->"
                for tok in declared}
    bad = [tok for tok, want in expected.items() if want not in text]
    run.check(f"{tag}J3-every-token-writes-its-src-marker",
              not bad and len(out["rows"]) == len(declared)
              and all(row["written"] for row in out["rows"]),
              f"tokens_without_their_exact_marker={bad} "
              f"rows={[(row['token'], row['written']) for row in out['rows']]}")
    run.check(f"{tag}J4-unknown-token-is-still-refused",
              out["unknownWritten"] and "src=not-a-real-source" not in text
              and "<!-- route=final start=2.50 reason=oracle -->" in text,
              f"unknown_written={out['unknownWritten']}")
    run.check(f"{tag}J5-provisional-draft-is-still-refused",
              out["provisional"] == "null" and "oracle provisional line" not in text,
              f"append(provisional-draft) -> {out['provisional']}")


def mutate(text, find, replace, name):
    if find not in text:
        raise SetupError(f"{name}: anchor NOT FOUND in the real bytes: {find!r}")
    out = text.replace(find, replace, 1)
    if out == text:
        raise SetupError(f"{name}: the mutation changed nothing")
    return out


MUTANTS = (
    {
        "slug": "m1",
        "name": "M1-gate-reverted-to-the-runner-file",
        "kind": "worker",
        "find": ("        self.armed = bool(\n"
                 "            self.enabled and self.runner_available and self.model_available)"),
        "replace": ("        self.armed = bool(\n"
                    "            self.enabled and self.runner_available)"),
        "expect_red": ("W9-real-disk-refuses",
                       "W10-refusal-names-reason-and-path",
                       "W12-partial-checkpoint-names-what-is-missing"),
    },
    {
        "slug": "m2",
        "name": "M2-refusal-loses-the-missing-path",
        "kind": "worker",
        "find": 'f"runner={self.runner} model_dir={self.model_dir} "',
        "replace": 'f"runner={self.runner} "',
        "expect_red": ("W10-refusal-names-reason-and-path",
                       "W12-partial-checkpoint-names-what-is-missing"),
    },
    {
        "slug": "m3",
        "name": "M3-store-allow-list-reverted",
        "kind": "store",
        "find": ("const ROUTE_SOURCES = ['worker-stamped', 'worker-stamped-producer', "
                 "'panel-deadline', 'fallback'];"),
        "replace": "const ROUTE_SOURCES = ['worker-stamped', 'panel-deadline', 'fallback'];",
        "expect_red": ("J1-allow-list-covers-every-declared-token",
                       "J2-allow-list-has-no-extras",
                       "J3-every-token-writes-its-src-marker"),
    },
    {
        "slug": "m4",
        "name": "M4-control-comment-only-must-move-nothing",
        "kind": "control",
        "find": None,
        "replace": None,
        "expect_red": (),
    },
)


def main():
    parser = argparse.ArgumentParser(
        description="Sotto redux arm gate -- both colours, in process.")
    parser.add_argument("--neg-arm", "--red-arm", dest="neg_arm", action="store_true",
                        help="also run MUTANTS of the real bytes; the arms that should "
                             "notice must go RED and the control must not move")
    args = parser.parse_args()

    print("SOTTO redux-arm-weights-oracle -- in process; the app, the shell and the worker "
          "are NEVER launched")
    try:
        for path in SUBJECTS:
            print(pin_line(path))
        print(f"node={NODE_EXE}")

        if os.path.isdir(REAL_CHECKPOINT):
            raise SetupError(
                f"the RED colour is unbuildable: {REAL_CHECKPOINT} EXISTS today, so the "
                f"real-disk arm has no absent checkpoint to refuse")
        listing = sorted(p.name for p in MODELS_DIR.iterdir() if p.is_dir()) \
            if MODELS_DIR.is_dir() else []
        print(f"REAL_DISK worker/models dirs={listing}")
        print(f"REAL_DISK checkpoint {REAL_CHECKPOINT} exists={os.path.isdir(REAL_CHECKPOINT)}")

        declared = declared_sources()
        worker_text = WORKER.read_text(encoding="utf-8")
        store_text = STORE.read_text(encoding="utf-8")

        runner_mod = load_module(RUNNER, "redux_batch_oracle_real")
        if not isinstance(getattr(runner_mod, "DEFAULT_MODEL_DIR", None), Path):
            raise SetupError("worker/redux_batch.py has no Path DEFAULT_MODEL_DIR to cross-check "
                             "the worker's derivation against")

        temp_root = make_temp_root()
        print(f"TEMP_ROOT {temp_root}")

        print("== ARM G: the REAL bytes, as shipped ==")
        green = Run("GREEN")
        real_mod = load_module(WORKER, "sotto_worker_oracle_real")
        arm_worker(green, real_mod, "G:", runner_mod, temp_root, worker_text)
        arm_store(green, store_text, "G:", temp_root, declared)
        print(f"GREEN ARM SUMMARY: {green.summary()}")

        failures = []
        if args.neg_arm:
            print("== NEG ARM: mutants of the real bytes (in memory, written to %TEMP%) ==")
            for spec in MUTANTS:
                tag = spec["slug"].upper() + ":"
                print(f"-- MUTANT {spec['name']}")
                if spec["kind"] == "control":
                    worker_mutant = worker_text + "\n# oracle control mutant: comment only\n"
                    store_mutant = store_text + "\n// oracle control mutant: comment only\n"
                elif spec["kind"] == "worker":
                    worker_mutant = mutate(worker_text, spec["find"], spec["replace"],
                                           spec["name"])
                    store_mutant = store_text
                else:
                    worker_mutant = worker_text
                    store_mutant = mutate(store_text, spec["find"], spec["replace"],
                                          spec["name"])

                run = Run(spec["name"])
                worker_path = Path(temp_root) / f"{spec['slug']}-sotto_worker.py"
                worker_path.write_text(worker_mutant, encoding="utf-8")
                mod = load_module(worker_path, f"sotto_worker_mutant_{spec['slug']}")
                arm_worker(run, mod, tag, runner_mod, temp_root, worker_mutant)
                arm_store(run, store_mutant, tag, temp_root, declared)

                expected = {tag + cid for cid in spec["expect_red"]}
                observed = set(run.red())
                missing_red = sorted(expected - observed)
                extra_red = sorted(observed - expected)
                ok = not missing_red and not extra_red
                print(f"  MUTANT VERDICT {spec['name']}: "
                      f"expect_red={sorted(expected)} observed_red={sorted(observed)} "
                      f"missing={missing_red} extra={extra_red} -> {'OK' if ok else 'BAD'}")
                if not ok:
                    failures.append(f"{spec['name']}: missing={missing_red} extra={extra_red}")

        if green.red() or failures:
            print(f"VERDICT: FAIL -- green_red={green.red()} mutant_failures={failures}")
            return 1
        print("VERDICT: PASS")
        return 0
    except SetupError as exc:
        print(f"SETUP ERROR: {exc}")
        print("VERDICT: SETUP ERROR")
        return 2


if __name__ == "__main__":
    sys.exit(main())
