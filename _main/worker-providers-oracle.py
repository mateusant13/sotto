# NO-BUG: worker-providers-oracle — is the Sotto engine running on the GPU, or on the CPU? -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""worker-providers-oracle — is the Sotto engine running on the GPU, or on the CPU?

BORN FROM A MEASURED QUESTION (owner, 2026-11-02): *"1,7x realtime? ta certo isso?
pesquisa o modelo e veja se tua implementacao ta errada"*.

THE ANSWER, MEASURED ON THIS BOX with the same file and the same code:
    RTX 5080, CUDAExecutionProvider   13,44 s de audio em 1,25 s   10,75x   52 ms/chunk
    CPUExecutionProvider              13,44 s de audio em 5,92 s    2,27x  247 ms/chunk
    o selftest durante a bateria      13,44 s de audio em 7,91 s    0,59x   (contenda)
So the number I first reported was a BUSY-MACHINE number, not the model's. But it
took a separate probe to answer, because the shell's log kept only the STATE
(`STATUS_APPLIED text="model-loaded"`) and never the payload -- `providers_selected`
was invisible. The shell now logs `WORKER_PROVIDERS selected=.. available=..`
(`sotto_webview.py`, the `stage=providers` branch), and this file judges that line.

THE CPU FIGURE ABOVE IS NOT A CONSTANT, AND THAT IS THE POINT (MEASURED 2026-11-09,
`_main/receipt-20261109-live-engine-gpu.md`, `_main/live-engine-provider-ab.py`). Same
clip (`_main/fixtures/stack-compare/ptbr-radio-14s.wav`), same code, same 4-thread plan,
three paired runs on this desktop while the owner used it:
    arm    chunk p50 (ms)   p95 (ms)   RTF (wall/audio)   x realtime
    cpu    487 / 865 / 228  773 / 1248 / 294   0.93 / 1.59 / 0.42   1.1 / 0.6 / 2.4
    cuda    37 /  35 /  42   54 /   48 /  52   0.076 / 0.066 / 0.077   13.2 / 15.1 / 12.9
The CPU engine is 228-865 ms per 560 ms chunk -- 5.5x to 24x slower than CUDA, and
UNDER real time in two of three runs. So "2,27x on CPU" is the good end of a range whose
bad end is "the desktop is busy and captions fall behind", and no reading of this gate
may treat the CPU arm as a safe equivalent: the only green it accepts is the one where a
GPU provider is AVAILABLE and SELECTED.

WHAT IT REFUSES, and the case is real (onnxruntime 1.30 wants cublasLt64_13.dll +
cuDNN 9; they ship inside the nvidia wheels, NOT on PATH):
  * `CUDAExecutionProvider` in `available` but NOT in `selected` -> RED. A CUDA EP
    that is registered and cannot load is the silent CPU fallback that made the
    live engine 4x slower than it should be.
  * a `WORKER_GPU_POLICY` readback but NO `WORKER_PROVIDERS` line -> RED: the
    worker from this code announced its policy and then lost the providers
    line. That is an instrumentation regression, not a missing session, and it
    must not sit in `skipped=` run after run.
  * neither kind of line in the log -> `VERDICT: SKIPPED reason=no-provider-line`,
    never GREEN: an instance that wrote neither is not evidence either way.

`--neg-arm` feeds synthetic policy records through the SAME judge that publishes
the verdict -- the GPU-only configuration must PASS, while CPU fallback, an
incomplete CUDA graph set, a CPU GenAI frontend, and a CPU-only host must be RED.
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "_main", "webview-run.log")

LINE_RE = re.compile(
    r"WORKER_PROVIDERS\s+pid=(?P<pid>[^\s]+)\s+"
    r"selected=(?P<sel>[^\s]*)\s+available=(?P<avail>[^\s]*)"
)
GPU_POLICY_RE = re.compile(
    r"WORKER_GPU_POLICY\s+pid=(?P<pid>[^\s]+)\s+"
    r"asr_request=(?P<asr>[^\s]+)\s+"
    r"ort_cpu_fallback=(?P<ort_fallback>[^\s]+)\s+"
    r"ort_cuda_dlls_preloaded=(?P<cuda_dlls_preloaded>[^\s]+)\s+"
    r"ort_cuda_graphs=(?P<ort_graphs>[^\s]+)\s+"
    r"genai_request=(?P<genai>[^\s]+)\s+genai_device=(?P<device>[^\s]+)\s+"
    r"genai_vad_configured=(?P<vad_configured>[^\s]+)\s+"
    r"genai_vad_enabled=(?P<vad_enabled>[^\s]+)\s+"
    r"genai_vad_request=(?P<vad_request>[^\s]+)\s+"
    r"genai_vad_cpu_fallback=(?P<vad_fallback>[^\s]+)"
)


def judge(selected: list[str], available: list[str], note: str = "") -> dict:
    """The single decision function. `--neg-arm` drives it directly."""
    cuda_ok = "CUDAExecutionProvider" in available or "TensorrtExecutionProvider" in available
    cuda_used = "CUDAExecutionProvider" in selected or "TensorrtExecutionProvider" in selected
    if cuda_used:
        return {"verdict": "PASS", "why": "the live engine is on the GPU",
                "selected": selected, "available": available}
    if cuda_ok:
        return {"verdict": "RED",
                "why": "a GPU provider is AVAILABLE and NOT selected: the engine fell back to "
                       "the CPU. This is the measured silent fallback (missing cublasLt64_13/"
                       "cuDNN 9 in the DLL search path before onnxruntime loads).",
                "selected": selected, "available": available, "note": note}
    return {"verdict": "RED", "why": "GPU-only ASR cannot run without a GPU provider",
            "selected": selected, "available": available}


def judge_gpu_only(selected: list[str], available: list[str], policy: dict | None) -> dict:
    """Pass only when production readbacks prove GPU inference with CPU fallback disabled."""
    base = judge(selected, available)
    checks = {
        "cuda_selected": "CUDAExecutionProvider" in selected,
        "cuda_available": "CUDAExecutionProvider" in available,
        "same_worker_process": bool(policy and policy.get("same_process")),
        "asr_requested_cuda_only": bool(policy and policy.get("asr") == "CUDAExecutionProvider"),
        "ort_cpu_fallback_disabled": bool(policy and policy.get("ort_fallback") == "disabled"),
        "ort_cuda_dlls_preloaded": bool(policy and policy.get("cuda_dlls_preloaded", "").lower() == "true"),
        "all_ort_graphs_cuda": bool(policy and policy.get("ort_graphs") == "3"),
        "genai_requested_cuda_only": bool(policy and policy.get("genai") == "CUDAExecutionProvider"),
        "genai_device_cuda": bool(policy and policy.get("device", "").lower() in ("cuda", "gpu")),
        "genai_vad_configured": bool(policy and policy.get("vad_configured", "").lower() == "true"),
        "genai_vad_enabled": bool(policy and policy.get("vad_enabled", "").lower() == "true"),
        "genai_vad_requested_cuda_only": bool(policy and policy.get("vad_request") == "CUDAExecutionProvider"),
        "genai_vad_cpu_fallback_disabled": bool(policy and policy.get("vad_fallback") == "disabled"),
    }
    passed = all(checks.values())
    return {
        "verdict": "PASS" if passed else "RED",
        "why": "GPU-only ASR policy was read back from the real worker" if passed else
               "GPU-only ASR requirement missing or contradicted",
        "selected": selected,
        "available": available,
        "policy": policy,
        "checks": checks,
        "base": base,
    }


def last_readback(path: str):
    provider_row = None
    policy_match = None
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                line = raw.decode("utf-8", "replace")
                provider = LINE_RE.search(line)
                if provider:
                    provider_row = {
                        "pid": provider.group("pid"),
                        "selected": [x for x in provider.group("sel").split(",") if x],
                        "available": [x for x in provider.group("avail").split(",") if x],
                        "raw": provider.group(0),
                    }
                policy = GPU_POLICY_RE.search(line)
                if policy:
                    policy_match = policy
    except OSError:
        return None, None
    return provider_row, policy_match


def main(argv: list[str]) -> int:
    neg = "--neg-arm" in argv
    path = LOG
    if "--log" in argv:
        at = argv.index("--log")
        if at + 1 >= len(argv):
            print("usage: worker-providers-oracle.py [--neg-arm] [--log PATH]")
            return 2
        path = argv[at + 1]
    if neg:
        selected = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        available = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        good_policy = {
            "asr": "CUDAExecutionProvider", "ort_fallback": "disabled",
            "cuda_dlls_preloaded": "true", "ort_graphs": "3",
            "genai": "CUDAExecutionProvider", "device": "cuda",
            "vad_configured": "true", "vad_enabled": "true",
            "vad_request": "CUDAExecutionProvider", "vad_fallback": "disabled",
            "same_process": True,
        }
        cases = [
            ("cuda-selected-passes", judge_gpu_only(selected, available, good_policy)["verdict"] == "PASS"),
            ("cpu-ep-fallback-reds", judge_gpu_only(selected, available, {**good_policy, "ort_fallback": "enabled"})["verdict"] == "RED"),
            ("missing-cuda-dll-preload-reds", judge_gpu_only(selected, available, {**good_policy, "cuda_dlls_preloaded": "false"})["verdict"] == "RED"),
            ("cpu-genai-frontend-reds", judge_gpu_only(selected, available, {**good_policy, "device": "cpu"})["verdict"] == "RED"),
            ("missing-cuda-graph-reds", judge_gpu_only(selected, available, {**good_policy, "ort_graphs": "2"})["verdict"] == "RED"),
            ("different-worker-readbacks-red", judge_gpu_only(selected, available, {**good_policy, "same_process": False})["verdict"] == "RED"),
            ("cpu-vad-fallback-reds", judge_gpu_only(selected, available, {**good_policy, "vad_fallback": "enabled"})["verdict"] == "RED"),
            ("disabled-live-vad-reds", judge_gpu_only(selected, available, {**good_policy, "vad_enabled": "false", "vad_request": "disabled"})["verdict"] == "RED"),
            ("cpu-only-box-reds", judge_gpu_only(["CPUExecutionProvider"], ["CPUExecutionProvider"], {
                **good_policy, "asr": "CPUExecutionProvider", "ort_fallback": "enabled",
                "ort_graphs": "0", "genai": "CPUExecutionProvider", "device": "cpu",
                "cuda_dlls_preloaded": "false", "vad_configured": "false",
                "vad_enabled": "false", "vad_request": "disabled", "vad_fallback": "not-active",
            })["verdict"] == "RED"),
        ]
        caught = sum(1 for _, ok in cases if ok)
        for name, ok in cases:
            print(("PASS " if ok else "FAIL ") + name)
        print(json.dumps({"cases": len(cases), "caught": caught}))
        print("NEG-ARM: PASS" if caught == len(cases) else "NEG-ARM: FAIL")
        # `red-as-expected-*` CONVENTION: exit 1 BY DESIGN when the control
        # caught the defect (the battery demands rc=1 and the phrase).
        return 1

    row, policy_match = last_readback(path)
    if not row:
        if policy_match:
            print("WORKER_GPU_POLICY present but no WORKER_PROVIDERS line in %s"
                  % os.path.relpath(path, REPO))
            print("WORKER-PROVIDERS VERDICT: RED")
            print("\nVERDICT: RED")
            return 1
        print("no WORKER_PROVIDERS line in %s" % os.path.relpath(path, REPO))
        print("WORKER-PROVIDERS VERDICT: SKIPPED reason=no-provider-line")
        print("\nVERDICT: SKIPPED reason=no-provider-line")
        return 0
    policy = ({
        "asr": policy_match.group("asr"),
        "same_process": bool(row and row["pid"] == policy_match.group("pid")),
        "ort_fallback": policy_match.group("ort_fallback"),
        "cuda_dlls_preloaded": policy_match.group("cuda_dlls_preloaded"),
        "ort_graphs": policy_match.group("ort_graphs"),
        "genai": policy_match.group("genai"),
        "device": policy_match.group("device"),
        "vad_configured": policy_match.group("vad_configured"),
        "vad_enabled": policy_match.group("vad_enabled"),
        "vad_request": policy_match.group("vad_request"),
        "vad_fallback": policy_match.group("vad_fallback"),
    } if policy_match else None)
    result = judge_gpu_only(row["selected"], row["available"], policy)
    print(json.dumps(result, ensure_ascii=False))
    print("line: %s" % row["raw"])
    print("WORKER-PROVIDERS VERDICT: %s" % result["verdict"])
    print("\nVERDICT: %s" % result["verdict"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
