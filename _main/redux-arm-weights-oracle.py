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
    W: worker/sotto_worker.py imported by path (the switch class itself lives in
       worker/engine_switch.py and is pinned as a subject too). GREEN colour: a
       %TEMP% runner plus the checkpoint it derives arms the switch, the mode
       machine still switches (the 2026-11-03 design: a hidden panel alone no
       longer unloads -- the SHED channel drives batch/shed/stream, and the
       hidden-dwell path is measured with `unload_when_hidden=True`), and the
       armed boot line keeps its shape. RED colour: the REAL ternary derivation
       with the parakeet engine forced unavailable REFUSES -- one line,
       reason=checkpoint-missing, naming the directory and every missing
       manifest -- and stays inert. The real disk carries the ONNX parakeet today
       (2026-11-05), so the default derivation arms; that fact is measured, and
       the refusal branch is taken through the constructor's `engine=` seam
       rather than by pretending the ONNX export is absent.
    J: app/panel/history-store.js required by node with SOTTO_HISTORY_ROOT in
       %TEMP%. Every token caption-formulation.js declares is appended through
       the store's OWN append() and must carry its src= marker.
  --neg-arm: MUTANTS of the real bytes, built in memory and written to %TEMP%.
    Switch mutants are compiled with the REAL module path as `__file__` and
    registered as `engine_switch`, which is the name sotto_worker.py imports, so
    the worker mutant binds the mutated bytes and nothing is redirected to %TEMP%.
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
import types
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
SWITCH = REPO / "worker" / "engine_switch.py"
RUNNER = REPO / "worker" / "redux_batch.py"
STORE = REPO / "app" / "panel" / "history-store.js"
FORMULATION = REPO / "app" / "panel" / "caption-formulation.js"
MODELS_DIR = REPO / "worker" / "models"
REAL_CHECKPOINT = MODELS_DIR / "parakeet-redux-ternary"

MANIFESTS = ("config.json", "model.safetensors", "ternary.json")
DECLARED_SOURCES = ("worker-stamped", "worker-stamped-producer", "panel-deadline", "fallback")
CREATE_NO_WINDOW = 0x08000000
NODE_EXE = shutil.which("node") or "node"

SUBJECTS = (WORKER, SWITCH, RUNNER, STORE, FORMULATION)


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


def load_switch_module(text: str, name: str = "engine_switch"):
    """A `worker/engine_switch.py` built from `text`, where the worker will find it.

    THE MUTATED BYTES ARE THE ONLY DIFFERENCE FROM THE SHIPPED MODULE.
    `engine_switch` derives `HERE` from its own `__file__`, and everything the
    switch resolves -- `worker/models/`, the shedding table, the visibility file
    -- hangs off it. A mutant written to %TEMP% would resolve all of those
    against %TEMP% and go RED for the wrong reason (an instrument that reddens on
    relocation proves nothing about the mutation). Compiling the bytes with the
    REAL path as `__file__` keeps that surface identical, and registering the
    module under the name `sotto_worker.py` imports (`from engine_switch import
    ...`) is what makes the worker mutant actually run these bytes.
    """
    mod = types.ModuleType(name)
    mod.__file__ = str(SWITCH)
    mod.__package__ = ""
    sys.modules[name] = mod
    try:
        exec(compile(text, str(SWITCH), "exec"), mod.__dict__)
    except Exception as exc:  # noqa: BLE001 -- an unbuildable mutant is a setup error
        raise SetupError(f"executing the mutated engine_switch raised "
                         f"{type(exc).__name__}: {exc}")
    return mod


class FakeReader:
    """The smallest thing ReduxHiddenSwitch accepts as a visibility channel."""

    def __init__(self, visible, why="oracle", age=0.0, shed='leve'):
        self.visible = bool(visible)
        self.why = why
        self.age = age
        self.shed_level = shed
        self.path = "<oracle-fake-visibility>"

    def read(self):
        return self.visible, self.why, self.age

    def shed(self, default='leve'):
        """O canal de CARGA que o `tick` le desde 2026-11-01 (`REDUX_SHEDDING`).

        Sem este metodo o oraculo morria em `AttributeError` no primeiro `tick`
        -- instrumento em atraso, nao defeito do motor. `leve` e' o valor que a
        leitura real devolve quando o ficheiro nao diz nada: NAO DESLIGO nada.
        """
        return self.shed_level if self.shed_level in ('leve', 'alta', 'muito-alta') else default


class UnavailableEngine:
    """An engine the switch must treat as NOT ON DISK, through its own seam.

    WHY THIS EXISTS (instrument repair, 2026-11-05). `ReduxHiddenSwitch.__init__`
    accepts `engine=` and falls back to a real `ParakeetEngine` over
    `worker/models/parakeet-redux-onnx-int4`. Since that ONNX export was fetched
    and verified on the real disk (2026-11-05: 416 MB, sha256 ade2c65c/97ae0cb0),
    every switch built with the DEFAULT engine derives `engine=parakeet` and
    ARMS -- so the ternary REFUSAL branches (`reason=runner-missing`,
    `reason=checkpoint-missing`) stopped being reached by default derivation.
    The refusal behaviour still ships and must still be MEASURED; this object is
    how the oracle takes the branch without pretending the ONNX export is gone.
    It offers exactly the surface `engine_policy.ParakeetEngine` offers and says
    `available=False`, so gate 2 sees "no engine on disk" -- the honest reading
    of the ternary-only tree these checks describe.
    """

    available = False
    dir = "<oracle-unavailable-engine>"
    missing = ["<oracle-engine-not-installed>"]
    loaded = False

    def name(self):
        return "oracle-unavailable"

    def load(self):
        raise AssertionError("the oracle's unavailable engine must never be loaded")

    def release(self, reason="idle"):
        return False

    def transcribe(self, pcm):
        raise AssertionError("the oracle's unavailable engine must never transcribe")


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
                              timeout=120, creationflags=flags, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0), env=env)
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

    # ── W8: THE MODE MACHINE AS IT SHIPS TODAY (2026-11-03 design) ─────────
    # RETIRED EXPECTATION, in this file's own words: until 2026-11-03 a hidden
    # panel ALONE switched stream -> batch. `worker/engine_switch.py::tick`
    # changed that deliberately -- `unload_when_hidden` now defaults to False,
    # because unloading the live model on every panel open paid a 1.9 GB reload
    # and the owner's law is "legenda ao vivo desligada nao e' modelo desligado".
    # The batch now switches on the SHED CHANNEL (`alta` -> batch,
    # `muito-alta` -> shed, `leve` -> whatever visibility says). The check keeps
    # all of its teeth: it measures (1) the shipped default refusing to switch
    # on a hidden panel alone, (2) the hidden-dwell machinery still working when
    # the flag is explicitly on, and (3) the shed channel driving batch/shed/
    # stream. None of the three is "whatever the code returns": each sequence and
    # its switch count is exact.
    t0 = 1000.0
    reader_keep = FakeReader(True, "oracle-visible")
    logs_keep = []
    sw_keep = mod.ReduxHiddenSwitch(enabled=True, reader=reader_keep, runner=str(runner),
                                    log_fn=logs_keep.append)  # unload_when_hidden ships False
    keep_seq = [sw_keep.tick(now=t0)]
    reader_keep.visible = False
    keep_seq.append(sw_keep.tick(now=t0 + 0.1))
    keep_seq.append(sw_keep.tick(now=t0 + sw_keep.hidden_after_s + 1.0))
    keep_seq = tuple(keep_seq)

    reader_dwell = FakeReader(True, "oracle-visible")
    logs_dwell = []
    sw_dwell = mod.ReduxHiddenSwitch(enabled=True, reader=reader_dwell, runner=str(runner),
                                     log_fn=logs_dwell.append, unload_when_hidden=True)
    dwell_seq = [sw_dwell.tick(now=t0)]
    reader_dwell.visible = False
    dwell_seq.append(sw_dwell.tick(now=t0 + 0.1))
    dwell_seq.append(sw_dwell.tick(now=t0 + sw_dwell.hidden_after_s + 1.0))
    reader_dwell.visible = True
    dwell_seq.append(sw_dwell.tick(now=t0 + sw_dwell.hidden_after_s + 2.0))
    dwell_seq = tuple(dwell_seq)

    reader_shed = FakeReader(True, "oracle-visible", shed="leve")
    logs_shed = []
    sw_shed = mod.ReduxHiddenSwitch(enabled=True, reader=reader_shed, runner=str(runner),
                                    log_fn=logs_shed.append)
    shed_seq = [sw_shed.tick(now=t0)]
    reader_shed.shed_level = "alta"
    shed_seq.append(sw_shed.tick(now=t0 + 0.1))
    reader_shed.shed_level = "muito-alta"
    shed_seq.append(sw_shed.tick(now=t0 + 0.2))
    reader_shed.shed_level = "leve"
    shed_seq.append(sw_shed.tick(now=t0 + 0.3))
    shed_seq = tuple(shed_seq)

    run.check(f"{tag}W8-mode-machine-still-switches",
              keep_seq == ("stream", "stream", "stream") and sw_keep.switches == 0
              and dwell_seq == ("stream", "stream", "batch", "stream")
              and sw_dwell.switches == 2
              and shed_seq == ("stream", "batch", "shed", "stream")
              and sw_shed.switches == 3
              and any("reason=hidden-" in line for line in logs_dwell)
              and any("reason=shed-alta" in line for line in logs_shed)
              and any("reason=shed-muito-alta" in line for line in logs_shed),
              f"shipped(unload=False)={keep_seq} switches={sw_keep.switches} | "
              f"dwell(unload=True)={dwell_seq} switches={sw_dwell.switches} | "
              f"shed={shed_seq} switches={sw_shed.switches}")

    # -- RED colour: the TERNARY branch, on the REAL disk paths -------------
    # WHY THE ENGINE IS NAMED EXPLICITLY (2026-11-05). The real disk now holds
    # `worker/models/parakeet-redux-onnx-int4` (verified today, 416 MB), so the
    # DEFAULT engine derives `engine=parakeet` and the switch ARMS -- which is
    # the shipped machine being correct, not a defect. The retired expectation
    # was "the real disk refuses" because the ternary checkpoint is what the
    # real derivation used to find nothing of. The refusal code still ships and
    # is still the thing that stops the worker from cutting the only
    # transcriber, so these checks build the switch through the constructor's
    # documented `engine=` seam with an engine that is NOT on disk: gate 2 then
    # sees exactly the ternary facts, which are still read FROM THE REAL DISK BY
    # NAME (`model_dir` derived from the real runner -> the real checkpoint).
    # Nothing here is redirected to a %TEMP% tree to buy a green.
    sw_default = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                                       runner=str(RUNNER), log_fn=[].append)
    print(f"  EVIDENCE {tag}real-disk-default engine_available="
          f"{sw_default.engine_available} batch_kind={sw_default.batch_kind} "
          f"armed={sw_default.armed} model_dir={sw_default.model_dir}")

    logs_real = []
    sw_real = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                                    runner=str(RUNNER), log_fn=logs_real.append,
                                    engine=UnavailableEngine())
    run.check(f"{tag}W9-real-disk-refuses",
              sw_default.engine_available is True
              and sw_default.batch_kind == "parakeet"
              and sw_default.armed is True
              and sw_real.armed is False
              and sw_real.runner_available is True
              and sw_real.model_available is False
              and list(sw_real.model_missing) == list(MANIFESTS)
              and os.path.normcase(sw_real.model_dir) == os.path.normcase(str(REAL_CHECKPOINT)),
              f"default: engine_available={sw_default.engine_available} "
              f"batch_kind={sw_default.batch_kind} armed={sw_default.armed} | "
              f"ternary-only: armed={sw_real.armed} model_dir={sw_real.model_dir} "
              f"missing={list(sw_real.model_missing)}")
    sw_real.boot_line()
    refusal_line = logs_real[0] if logs_real else ""
    print(f"  EVIDENCE {tag}refusal-line={refusal_line}")
    run.check(f"{tag}W10-refusal-names-reason-and-path",
              len(logs_real) == 1
              and "REDUX_SWITCH_REFUSED armed=false" in refusal_line
              and "reason=checkpoint-missing" in refusal_line
              and os.path.normcase(f"runner={RUNNER}") in os.path.normcase(refusal_line)
              and os.path.normcase(f"model_dir={REAL_CHECKPOINT}") in os.path.normcase(refusal_line)
              and f"missing={','.join(MANIFESTS)}" in refusal_line
              and "\n" not in refusal_line,
              refusal_line)

    before = len(logs_real)
    modes = [sw_real.tick(now=t0 + step) for step in range(10)]
    kick = sw_real.maybe_kick("oracle")
    after = len(logs_real)
    # The ONE-LINE half of this claim is pinned exactly by W10 (`len(logs_real)
    # == 1`); here the distinct claim is INERTNESS -- the refusal never grows a
    # line, never leaves `stream`, never counts a switch, never kicks a pass.
    run.check(f"{tag}W11-refusal-is-one-line-and-inert",
              before == after and kick is False
              and set(modes) == {"stream"} and sw_real.mode == "stream"
              and sw_real.switches == 0 and sw_real.batches_kicked == 0
              and sw_real.enabled is True,
              f"lines_after_boot={before} lines_after_10_ticks={after} "
              f"modes={sorted(set(modes))} maybe_kick={kick} mode={sw_real.mode} "
              f"switches={sw_real.switches} batches_kicked={sw_real.batches_kicked}")

    partial_runner, partial_ckpt = make_runner_and_checkpoint(
        temp_root, "partial", manifests=("config.json",))
    logs_partial = []
    sw_partial = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                                       runner=str(partial_runner), log_fn=logs_partial.append,
                                       engine=UnavailableEngine())
    sw_partial.boot_line()
    partial_line = logs_partial[0] if logs_partial else ""
    run.check(f"{tag}W12-partial-checkpoint-names-what-is-missing",
              len(logs_partial) == 1
              and sw_partial.armed is False
              and list(sw_partial.model_missing) == ["model.safetensors", "ternary.json"]
              and "REDUX_SWITCH_REFUSED armed=false" in partial_line
              and "reason=checkpoint-missing" in partial_line
              and os.path.normcase(f"runner={partial_runner}") in os.path.normcase(partial_line)
              and os.path.normcase(f"model_dir={partial_ckpt}") in os.path.normcase(partial_line)
              and "missing=model.safetensors,ternary.json" in partial_line
              and "\n" not in partial_line,
              f"missing={list(sw_partial.model_missing)} line={partial_line}")

    missing_runner = Path(temp_root) / "not-here" / "redux_batch.py"
    logs_norun = []
    sw_norun = mod.ReduxHiddenSwitch(enabled=True, reader=FakeReader(True),
                                     runner=str(missing_runner), log_fn=logs_norun.append,
                                     model_dir=str(ckpt), engine=UnavailableEngine())
    sw_norun.boot_line()
    norun_line = logs_norun[0] if logs_norun else ""
    run.check(f"{tag}W13-runner-missing-reason-still-distinct",
              len(logs_norun) == 1
              and sw_norun.armed is False
              and "REDUX_SWITCH_REFUSED armed=false reason=runner-missing" in norun_line
              and "checkpoint-missing" not in norun_line
              and "model_dir=" not in norun_line
              and os.path.normcase(f"runner={missing_runner}") in os.path.normcase(norun_line)
              and "\n" not in norun_line,
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
        "kind": "switch",
        "find": ("        self.armed = bool(\n"
                 "            self.enabled and self.runner_available and self.model_available\n"
                 "            or (self.enabled and self.engine_available))"),
        "replace": ("        self.armed = bool(\n"
                    "            self.enabled and self.runner_available)"),
        "expect_red": ("W9-real-disk-refuses",
                       "W10-refusal-names-reason-and-path",
                       "W12-partial-checkpoint-names-what-is-missing"),
    },
    {
        "slug": "m2",
        "name": "M2-refusal-loses-the-missing-path",
        "kind": "switch",
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
        switch_text = SWITCH.read_text(encoding="utf-8")
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
                    switch_mutant = switch_text + "\n# oracle control mutant: comment only\n"
                    worker_mutant = worker_text + "\n# oracle control mutant: comment only\n"
                    store_mutant = store_text + "\n// oracle control mutant: comment only\n"
                elif spec["kind"] == "switch":
                    switch_mutant = mutate(switch_text, spec["find"], spec["replace"],
                                           spec["name"])
                    worker_mutant = worker_text
                    store_mutant = store_text
                else:
                    switch_mutant = switch_text
                    worker_mutant = worker_text
                    store_mutant = mutate(store_text, spec["find"], spec["replace"],
                                          spec["name"])

                run = Run(spec["name"])
                # The switch bytes are registered under the name `sotto_worker.py`
                # imports, so the worker mutant below binds THESE bytes (not the
                # shipped module already in `sys.modules` from ARM G). `__file__`
                # is the REAL path, so only the mutation can move an arm.
                load_switch_module(switch_mutant, "engine_switch")
                worker_path = Path(temp_root) / f"{spec['slug']}-sotto_worker.py"
                worker_path.write_text(worker_mutant, encoding="utf-8")
                mod = load_module(worker_path, f"sotto_worker_mutant_{spec['slug']}")
                arm_worker(run, mod, tag, runner_mod, temp_root, worker_text)
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
