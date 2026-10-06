"""Which import hangs? One line per step, flushed, so a hang names itself.

The previous run produced an empty log after 240 s, which locates the hang
somewhere between interpreter start and the first print. This prints BEFORE and
AFTER each import so the last line printed is the step that hung.
"""

import sys
import time

t0 = time.time()


def mark(label):
    print(f"{time.time() - t0:8.2f}s  {label}", flush=True)


mark("interpreter up")
mark("importing ctranslate2")
import ctranslate2  # noqa: E402

mark(f"ctranslate2 OK version={ctranslate2.__version__}")

mark("importing huggingface_hub")
import huggingface_hub  # noqa: E402

mark(f"huggingface_hub OK version={huggingface_hub.__version__}")

mark("importing tokenizers")
import tokenizers  # noqa: E402

mark(f"tokenizers OK version={tokenizers.__version__}")

mark("importing onnxruntime")
import onnxruntime  # noqa: E402

mark(f"onnxruntime OK version={onnxruntime.__version__}")

mark("importing faster_whisper")
from faster_whisper import WhisperModel  # noqa: E402

mark("faster_whisper OK")
mark("constructing WhisperModel(tiny, cpu, int8)")
model = WhisperModel("tiny", device="cpu", compute_type="int8")
mark("MODEL LOADED")
print("ALL_IMPORTS_OK", flush=True)