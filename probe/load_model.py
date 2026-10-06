"""Does faster_whisper actually LOAD a model here, and how long does it take?

faster_whisper is CTranslate2, so no Rust compilation is involved. This only
proves the model loads and says how long it took; it does not claim the
transcription works, which is a separate measurement.
"""

import json
import sys
import time

out = {"model": None, "loaded": False, "load_s": None, "error": None}
name = sys.argv[1] if len(sys.argv) > 1 else "tiny"

try:
    t0 = time.time()
    from faster_whisper import WhisperModel

    model = WhisperModel(name, device="cpu", compute_type="int8")
    out["model"] = name
    out["load_s"] = round(time.time() - t0, 2)
    out["loaded"] = True
except Exception as exc:
    out["error"] = f"{type(exc).__name__}: {exc}"

print(json.dumps(out))
sys.exit(0 if out["loaded"] else 1)