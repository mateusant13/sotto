"""ctranslate2 hangs at import. Does the OTHER native path work?

ctranslate2 is a .pyd that never finishes loading on this host. Two escape
routes exist and both are already installed:

  onnxruntime  - the ONNX path. NVIDIA ships Parakeet / Nemotron streaming ASR
                 as ONNX, so this route needs no ctranslate2 at all.
  torch        - the PyTorch path, cu128 build against the RTX 5080.

Each import is timed and flushed individually, so a hang names itself and does
not take the others down with it. A hang is caught by running each import in a
CHILD process with a ceiling, because a hung DLL in this process kills the
measurement of everything after it.
"""

import subprocess
import sys
import time

CASES = [
    ("onnxruntime", "import onnxruntime; print('VER', onnxruntime.__version__)"),
    ("torch", "import torch; print('VER', torch.__version__); print('CUDA', torch.cuda.is_available())"),
    ("numpy", "import numpy; print('VER', numpy.__version__)"),
    ("sounddevice", "import sounddevice; print('VER', sd_version := sounddevice.__version__)"),
    ("soundfile", "import soundfile; print('VER', soundfile.__version__)"),
    ("ctranslate2", "import ctranslate2; print('VER', ctranslate2.__version__)"),
]

CEILING_S = 45
results = {}

for name, code in CASES:
    t0 = time.time()
    try:
        r = subprocess.run(
            [sys.executable, "-u", "-c", code],
            capture_output=True,
            text=True,
            timeout=CEILING_S,
        )
        dt = time.time() - t0
        if r.returncode == 0:
            results[name] = {"state": "OK", "s": round(dt, 2), "out": r.stdout.strip()[:200]}
        else:
            results[name] = {
                "state": "ERROR",
                "s": round(dt, 2),
                "rc": r.returncode,
                "err": r.stderr.strip()[-300:],
            }
    except subprocess.TimeoutExpired:
        results[name] = {"state": "HANG", "s": CEILING_S}

    print(f"{name:14s} {results[name]['state']:6s} {results[name].get('s')}s "
          f"{results[name].get('out') or results[name].get('err', '')}", flush=True)

ok = [k for k, v in results.items() if v["state"] == "OK"]
hang = [k for k, v in results.items() if v["state"] == "HANG"]
print(f"\nSUMMARY ok={ok} hang={hang}", flush=True)
sys.exit(0 if ok else 1)