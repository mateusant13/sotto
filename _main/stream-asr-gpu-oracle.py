#!/usr/bin/env python3
"""Model-free gate: a CUDA-less live ASR engine degrades to the CPU EP and SAYS so.

THE DEFECT THIS PINS (measured on the owner's box, 2026-11-17 19:18 ->
2026-11-18): `_main/webview-run.log` carries 736 `BRIDGE_EXIT ... rc=2` in 25 h
and 735 `BRIDGE_STATUS_ERROR ... stage=model-load`, every one with the same text:

    Fail: [ONNXRuntimeError] : 1 : FAIL : This session contains graph nodes that
    are assigned to the default CPU EP, but fallback to CPU EP has been
    explicitly disabled by the user.

The same file carries 738 warnings that name the cause:

    No registered plugin EP device found for 'CUDAExecutionProvider' with
    device_id=0

i.e. onnxruntime 1.30 still LISTS `CUDAExecutionProvider` while its plugin EP
registered no DEVICE. `StreamAsr` built every graph with `disable_cpu_ep_fallback`
and `main()` turned the resulting exception into `return 2`: the whole worker
died, the shell respawned it ~29 times an hour, and the owner got 25 hours of
silence. A provider is a preference; the job is to transcribe.

WHAT THIS FILE JUDGES, with a fake ORT and NO model (the 747 MB export is never
opened, no ORT session is created, no audio device is touched):

  A1 cuda-absent    -> device=cpu, ONE `ASR_CUDA_UNAVAILABLE` line carrying the
                       runtime's own ORT text, `attempted=[CUDAExecutionProvider]`
                       and every graph read back as CPU; the failing CUDA probe is
                       paid on `joint.onnx` ONLY (2 KB), never on the 747 MB.
  A2 cuda-works     -> device=cuda, ZERO degradation lines, the GPU-only guard
                       kept (`disable_cpu_ep_fallback=1`) on all three graphs, and
                       every graph read back as CUDA (the opposite defect).
  A3 control-nodes  -> CUDA present but the strict guard rejects a graph: the
                       guard is relaxed, the encoder readback STILL lists CUDA,
                       and the transition is named `ASR_CUDA_CONTROL_FALLBACK`
                       (not "CUDA unavailable" -- that would be a false claim).
  A4 silent-fallback-> the relaxed attempt succeeds with a CPU-only readback: that
                       is NOT a GPU run, so it is reported as `ASR_CUDA_UNAVAILABLE`
                       with device=cpu.
  A5 lying-readback -> the device census says "no CUDA device" while the probe
                       session still lists CUDA first (the exact measurement of
                       2026-11-19): a readback is not a device, so the run is still
                       device=cpu and the line quotes the census.
  A6 explicit-cpu   -> a caller that asked for the CPU EP gets it, with no
                       degradation line and no guard.
  A7 cpu-also-fails -> ONE line, then the CPU failure propagates (a genuinely
                       unusable model keeps its own error; nothing is swallowed).
  A8 missing-graph  -> a missing/unreadable graph raises its own named error and
                       prints no degradation line.
  --neg-arm         -> the SAME A1 against a mutant of `worker/sotto_worker.py`
                       whose `_asr_cpu_fallback_allowed` returns False. It must go
                       RED (the ORT text propagates); rc=1 means caught.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import types
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
              "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
sys.path.insert(0, str(WORKER))

WORKER_SOURCE = WORKER / "sotto_worker.py"

#: The runtime's own message, byte-for-byte as it reached the owner's log.
ORT_FAILURE_TEXT = (
    "[ONNXRuntimeError] : 1 : FAIL : This session contains graph nodes that are "
    "assigned to the default CPU EP, but fallback to CPU EP has been explicitly "
    "disabled by the user."
)
CPU_FAILURE_TEXT = (
    "[ONNXRuntimeError] : 1 : FAIL : CPU execution provider session creation "
    "failed (injected)"
)
GRAPHS = ("encoder.onnx", "decoder.onnx", "joint.onnx")
#: The mutant's anchor: ONE line, so "remove the CPU fallback" cannot mean
#: anything else than what this oracle tests.
MUTANT_ANCHOR = "    return bool(gpu_requested)"
MUTANT_REPLACEMENT = "    return False"


# ── the fakes ────────────────────────────────────────────────────────────────
class FakeSessionOptions:
    def __init__(self):
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.graph_optimization_level = None
        self.log_severity_level = 3
        self.log_verbosity_level = 0
        self._config = {}

    def add_session_config_entry(self, key, value):
        self._config[key] = str(value)

    def get_session_config_entry(self, key):
        return self._config.get(key, "")


class FakeInput:
    name = "audio_signal"
    shape = (1, 128, 17)


class FakeSession:
    def __init__(self, providers):
        self._providers = list(providers)
        self.closed = False

    def get_providers(self):
        return list(self._providers)

    def get_inputs(self):
        return [FakeInput()]

    def close(self):
        self.closed = True


class FakeOrt:
    """ORT 1.30-shaped: a provider can be LISTED while no device is registered."""

    def __init__(self, mode, cuda_device):
        import onnxruntime as ort

        self.ExecutionMode = ort.ExecutionMode
        self.GraphOptimizationLevel = ort.GraphOptimizationLevel
        self.__version__ = ort.__version__
        self.mode = mode
        self.cuda_device = bool(cuda_device)
        self.calls = []

    def get_ep_devices(self):
        devices = [types.SimpleNamespace(ep_name="CPUExecutionProvider")]
        if self.cuda_device:
            devices.append(types.SimpleNamespace(ep_name="CUDAExecutionProvider"))
        return devices

    def SessionOptions(self):
        return FakeSessionOptions()

    def InferenceSession(self, path, sess_options=None, providers=None):
        names = [str(item[0] if isinstance(item, (tuple, list)) else item)
                 for item in (providers or ())]
        guard = (sess_options.get_session_config_entry(
            "session.disable_cpu_ep_fallback") if sess_options is not None else "")
        graph = Path(path).name
        self.calls.append((graph, list(names), guard))
        cuda = "CUDAExecutionProvider" in names
        if cuda:
            if self.mode == "cuda-works":
                return FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])
            if self.mode in ("cuda-absent", "cpu-also-fails"):
                raise RuntimeError(ORT_FAILURE_TEXT)
            if self.mode == "lying-readback":
                if graph == "joint.onnx":
                    # MEASURED 2026-11-19: this is not a GPU session; the readback
                    # lists CUDA first anyway because the guard option, not the
                    # provider, is what would have failed.
                    return FakeSession(["CUDAExecutionProvider",
                                        "CPUExecutionProvider"])
                raise RuntimeError(ORT_FAILURE_TEXT)
            if self.mode == "control-nodes":
                if guard == "1":
                    raise RuntimeError(ORT_FAILURE_TEXT)
                return FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])
            if self.mode == "silent-fallback":
                if guard == "1":
                    raise RuntimeError(ORT_FAILURE_TEXT)
                return FakeSession(["CPUExecutionProvider"])
            raise AssertionError("unexpected CUDA mode %r" % (self.mode,))
        if names == ["CPUExecutionProvider"]:
            if self.mode == "cpu-also-fails":
                raise RuntimeError(CPU_FAILURE_TEXT)
            return FakeSession(["CPUExecutionProvider"])
        raise AssertionError("unexpected provider request: %r" % (names,))


def make_model_dir(root: Path, graphs=GRAPHS) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in graphs:
        (root / name).write_bytes(b"fixture")
    return root


SHARE = {"total": 2, "live": 2, "small": 1, "batch": 2}


def run_arm(mode: str, cuda_device: bool, temp: Path, providers=None, emulated=None):
    module = emulated or __import__("sotto_worker")
    ort = FakeOrt(mode, cuda_device)
    logs = []
    model_dir = make_model_dir(temp)
    try:
        result = module.open_asr_sessions(
            ort, str(model_dir), providers or ["CUDAExecutionProvider"],
            ab="", share=dict(SHARE), log=logs.append)
    except Exception as exc:  # noqa: BLE001 -- the arm decides what a raise means
        return {"raised": exc, "logs": logs, "ort": ort, "result": None}
    return {"raised": None, "logs": logs, "ort": ort, "result": result}


# ── the arms ─────────────────────────────────────────────────────────────────
def arm_cuda_absent(temp: Path) -> None:
    out = run_arm("cuda-absent", False, temp)
    assert out["raised"] is None, (
        "the CUDA-less run did not survive: %r" % (out["raised"],))
    assert len(out["logs"]) == 1, (
        "expected ONE degradation line, got %r" % (out["logs"],))
    line = out["logs"][0]
    assert line.startswith("ASR_CUDA_UNAVAILABLE "), line
    assert 'reason="RuntimeError: %s"' % ORT_FAILURE_TEXT in line, line
    assert "device=cpu" in line, line
    assert "attempted=[CUDAExecutionProvider]" in line, line
    assert "readback=CPUExecutionProvider" in line, line
    assert "\n" not in line, "the degradation line spans lines: %r" % (line,)
    res = out["result"]
    assert res["device"] == "cpu", res["device"]
    assert res["cpu_ep_fallback_disabled"] is False, res
    assert res["providers"] == ["CPUExecutionProvider"], res["providers"]
    for graph, actual in res["readback"].items():
        assert actual == ["CPUExecutionProvider"], (graph, actual)
    # The failing CUDA attempt was paid on the 2 KB joiner ONLY; the 747 MB
    # encoder is never opened with a CUDA request on an absent device.
    cuda_graphs = [graph for graph, names, _guard in out["ort"].calls
                   if "CUDAExecutionProvider" in names]
    assert cuda_graphs == ["joint.onnx"], cuda_graphs
    cpu_calls = [(graph, guard) for graph, names, guard in out["ort"].calls
                 if names == ["CPUExecutionProvider"]]
    # An absent entry is "the guard is off" (`session_options` only writes the
    # key when it means to disable the fallback).
    assert cpu_calls == [("encoder.onnx", ""), ("decoder.onnx", ""),
                         ("joint.onnx", "")], cpu_calls
    print("LINE: %s" % line)


def arm_cuda_works(temp: Path) -> None:
    out = run_arm("cuda-works", True, temp)
    assert out["raised"] is None, out["raised"]
    assert out["logs"] == [], (
        "a working GPU printed a degradation line: %r" % (out["logs"],))
    res = out["result"]
    assert res["device"] == "cuda", res["device"]
    assert res["cpu_ep_fallback_disabled"] is True, res
    assert res["gpu_failure"] is None, res["gpu_failure"]
    assert res["providers"][0] == "CUDAExecutionProvider", res["providers"]
    for graph, actual in res["readback"].items():
        assert "CUDAExecutionProvider" in actual, (graph, actual)
    assert [(names, guard) for _graph, names, guard in out["ort"].calls] == [
        (["CUDAExecutionProvider"], "1")] * 3, out["ort"].calls
    assert res["load_phases_s"]["sessions_total"] >= 0.0, res["load_phases_s"]


def arm_control_nodes(temp: Path) -> None:
    out = run_arm("control-nodes", True, temp)
    assert out["raised"] is None, out["raised"]
    assert len(out["logs"]) == 1, out["logs"]
    line = out["logs"][0]
    assert line.startswith("ASR_CUDA_CONTROL_FALLBACK "), line
    assert 'reason="RuntimeError: %s"' % ORT_FAILURE_TEXT in line, line
    assert "device=cuda" in line, line
    res = out["result"]
    assert res["device"] == "cuda", res["device"]
    assert res["cpu_ep_fallback_disabled"] is False, res
    assert res["readback"]["encoder"][0] == "CUDAExecutionProvider", res["readback"]
    assert res["note"] == "cuda-control-fallback", res["note"]
    # the strict attempt ran first, with the guard, and died on the ENCODER (the
    # graph that carries the expensive compute); the relaxed build then opened
    # all three graphs with the key absent.
    guards = [(graph, guard) for graph, _names, guard in out["ort"].calls]
    assert guards == [("encoder.onnx", "1"),
                      ("encoder.onnx", ""), ("decoder.onnx", ""),
                      ("joint.onnx", "")], guards
    print("LINE: %s" % line)


def arm_silent_fallback(temp: Path) -> None:
    out = run_arm("silent-fallback", True, temp)
    assert out["raised"] is None, out["raised"]
    assert len(out["logs"]) == 1, out["logs"]
    line = out["logs"][0]
    assert line.startswith("ASR_CUDA_UNAVAILABLE "), line
    assert "device=cpu" in line, line
    assert "readback=CPUExecutionProvider" in line, line
    res = out["result"]
    assert res["device"] == "cpu", (
        "a CPU-only readback was reported as device=%r" % (res["device"],))
    assert res["note"] == "cuda-unavailable", res["note"]


def arm_lying_readback(temp: Path) -> None:
    """A readback that lists CUDA while no device is registered is NOT a GPU run."""
    out = run_arm("lying-readback", False, temp)
    assert out["raised"] is None, out["raised"]
    assert len(out["logs"]) == 1, out["logs"]
    line = out["logs"][0]
    assert line.startswith("ASR_CUDA_UNAVAILABLE "), (
        "a lying readback was reported as a working GPU: %r" % (line,))
    assert "no CUDA EP device registered" in line, line
    assert "device census: only the CPU EP" in line, line
    assert "a readback is not a device" in line, line
    res = out["result"]
    assert res["device"] == "cpu", res["device"]
    assert res["readback"]["encoder"] == ["CPUExecutionProvider"], res["readback"]


def arm_explicit_cpu(temp: Path) -> None:
    out = run_arm("cuda-absent", False, temp, providers=["CPUExecutionProvider"])
    assert out["raised"] is None, out["raised"]
    assert out["logs"] == [], (
        "an explicit CPU request printed a degradation line: %r" % (out["logs"],))
    res = out["result"]
    assert res["device"] == "cpu", res["device"]
    assert res["cpu_ep_fallback_disabled"] is False, res
    assert [(names, guard) for _g, names, guard in out["ort"].calls] == [
        (["CPUExecutionProvider"], "")] * 3, out["ort"].calls


def arm_cpu_also_fails(temp: Path) -> None:
    out = run_arm("cpu-also-fails", False, temp)
    assert out["raised"] is not None, (
        "a CPU failure was swallowed and the run kept a dead engine")
    assert CPU_FAILURE_TEXT in str(out["raised"]), out["raised"]
    assert len(out["logs"]) == 1 and out["logs"][0].startswith(
        "ASR_CUDA_UNAVAILABLE "), out["logs"]


def arm_missing_graph(temp: Path) -> None:
    make_model_dir(temp)
    (temp / "decoder.onnx").unlink()
    try:
        module = __import__("sotto_worker")
        module.open_asr_sessions(FakeOrt("cuda-absent", False), str(temp),
                                 ["CUDAExecutionProvider"], ab="",
                                 share=dict(SHARE), log=lambda _l: None)
    except RuntimeError as exc:
        assert "missing graph(s)" in str(exc), exc
        assert "decoder.onnx" in str(exc), exc
        return
    raise AssertionError("a model with no decoder.onnx did not raise")


def positive() -> int:
    checks = 0
    with tempfile.TemporaryDirectory(prefix="sotto-stream-asr-gpu-") as temp:
        root = Path(temp)
        for index, arm in enumerate((
                arm_cuda_absent, arm_cuda_works, arm_control_nodes,
                arm_silent_fallback, arm_lying_readback, arm_explicit_cpu,
                arm_cpu_also_fails, arm_missing_graph)):
            where = root / ("arm-%d" % index)
            where.mkdir()
            arm(where)
            checks += 1
    return checks


# ── the negative arm: the fallback REMOVED must make the gate go red ─────────
def mutant_module():
    source = WORKER_SOURCE.read_text(encoding="utf-8")
    if source.count(MUTANT_ANCHOR) != 1:
        raise AssertionError(
            "the mutant anchor is not unique in worker/sotto_worker.py (%d hits)"
            % source.count(MUTANT_ANCHOR))
    mutated = source.replace(MUTANT_ANCHOR, MUTANT_REPLACEMENT)
    module = types.ModuleType("sotto_worker_no_cpu_fallback")
    module.__file__ = str(WORKER_SOURCE)
    exec(compile(mutated, str(WORKER_SOURCE), "exec"), module.__dict__)  # noqa: S102
    return module


def negative_control() -> int:
    mutant = mutant_module()
    assert mutant._asr_cpu_fallback_allowed(True) is False, (
        "the mutant still allows the fallback: the mutation did not take")
    with tempfile.TemporaryDirectory(prefix="sotto-stream-asr-neg-") as temp:
        out = run_arm("cuda-absent", False, Path(temp), emulated=mutant)
    if out["raised"] is None:
        print("NEG-ARM FAIL -- the fallback was removed and the gate stayed green")
        return 0
    if ORT_FAILURE_TEXT not in str(out["raised"]):
        print("NEG-ARM FAIL -- red for the wrong reason: %r" % (out["raised"],))
        return 0
    if out["logs"]:
        print("NEG-ARM FAIL -- the mutant still printed a degradation line: %r"
              % (out["logs"],))
        return 0
    print("NEG-ARM PASS -- fallback removed, the CUDA-less load raised: %s"
          % type(out["raised"]).__name__)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neg-arm", action="store_true")
    parser.add_argument("--selftest", action="store_true",
                        help="run the positive arms and the negative control in-process")
    args = parser.parse_args()
    try:
        if args.neg_arm:
            return negative_control()
        checks = positive()
        if checks != 8:
            raise AssertionError("positive coverage changed: %d" % checks)
        if args.selftest:
            neg_rc = negative_control()
            if neg_rc == 1:
                print("SELFTEST: PASS (positive 8/8; fallback-removal mutant caught)")
                return 0
            print("SELFTEST: FAIL (negative_rc=%d)" % neg_rc)
            return 1
    except Exception as exc:  # noqa: BLE001
        print("VERDICT: FAIL (%s: %s)" % (type(exc).__name__, exc))
        return 1
    print("VERDICT: PASS (8/8) no model load, no ORT session, no audio device")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
