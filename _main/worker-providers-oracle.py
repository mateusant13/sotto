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

WHAT IT REFUSES, and the case is real (onnxruntime 1.30 wants cublasLt64_13.dll +
cuDNN 9; they ship inside the nvidia wheels, NOT on PATH):
  * `CUDAExecutionProvider` in `available` but NOT in `selected` -> RED. A CUDA EP
    that is registered and cannot load is the silent CPU fallback that made the
    live engine 4x slower than it should be.
  * no `WORKER_PROVIDERS` line in the log -> `VERDICT: SKIPPED`, never GREEN: an
    instance started before this line existed is not evidence either way.

`--neg-arm` feeds three synthetic lines through the SAME `judge()` that publishes
the verdict -- the good one must PASS, the silent-fallback one must be RED, and the
CPU-only box (CUDA not even available) must PASS, because on such a box CPU is the
honest engine and a gate that reds it forever is a gate nobody reads.
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "_main", "webview-run.log")

LINE_RE = re.compile(r"WORKER_PROVIDERS\s+selected=(?P<sel>[^\s]*)\s+available=(?P<avail>[^\s]*)")


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
    return {"verdict": "PASS", "why": "no GPU provider on this box: CPU is the honest engine",
            "selected": selected, "available": available}


def last_line(path: str):
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    text = data.decode("utf-8", "replace")
    found = None
    for m in LINE_RE.finditer(text):
        found = m
    if not found:
        return None
    sel = [x for x in found.group("sel").split(",") if x]
    avail = [x for x in found.group("avail").split(",") if x]
    return {"selected": sel, "available": avail, "raw": found.group(0)}


def main(argv: list[str]) -> int:
    neg = "--neg-arm" in argv
    if neg:
        good = judge(["CUDAExecutionProvider", "CPUExecutionProvider"],
                     ["CUDAExecutionProvider", "CPUExecutionProvider"])
        fallback = judge(["CPUExecutionProvider"],
                         ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
                         note="No registered plugin EP device found")
        cpu_box = judge(["CPUExecutionProvider"], ["CPUExecutionProvider"])
        cases = [
            ("cuda-selected-passes", good["verdict"] == "PASS"),
            ("silent-cpu-fallback-reds", fallback["verdict"] == "RED"),
            ("cpu-only-box-passes", cpu_box["verdict"] == "PASS"),
        ]
        caught = sum(1 for _, ok in cases if ok)
        for name, ok in cases:
            print(("PASS " if ok else "FAIL ") + name)
        print(json.dumps({"cases": len(cases), "caught": caught}))
        print("NEG-ARM: PASS" if caught == len(cases) else "NEG-ARM: FAIL")
        # `red-as-expected-*` CONVENTION: exit 1 BY DESIGN when the control
        # caught the defect (the battery demands rc=1 and the phrase).
        return 1

    row = last_line(LOG)
    if not row:
        print("no WORKER_PROVIDERS line in %s" % os.path.relpath(LOG, REPO))
        print("WORKER-PROVIDERS VERDICT: SKIPPED")
        print("\nVERDICT: SKIPPED")
        return 0
    result = judge(row["selected"], row["available"])
    print(json.dumps(result, ensure_ascii=False))
    print("line: %s" % row["raw"])
    print("WORKER-PROVIDERS VERDICT: %s" % result["verdict"])
    print("\nVERDICT: %s" % result["verdict"])
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
