#!/usr/bin/env python3
"""SCRATCH: verify the two harness-survey traps EMPIRICALLY, on the installed wheel.

  1. does `set_search_options` accept `max_new_tokens` at all?
  2. is `max_length` the TOTAL sequence bound (so max_length == prompt_len must produce ZERO
     generated tokens, and max_length < prompt_len must fail or refuse)?
Deleted after the receipt quotes it. One model load, no window, no audio device.
"""
import sys
from pathlib import Path

import numpy as np
import onnxruntime_genai as og

MODEL_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else
                 r"H:\sotto\worker\models\qwen3.5-0.8b-ortgenai-cpu")

cfg = og.Config(str(MODEL_DIR))
cfg.clear_providers()
cfg.append_provider("cpu")
model = og.Model(cfg)
tokenizer = og.Tokenizer(model)

print("== trap 1: is there a max_new_tokens search option? ==")
params = og.GeneratorParams(model)
try:
    params.set_search_options(max_length=100, max_new_tokens=16, do_sample=False)
    print("  max_new_tokens ACCEPTED (silently ignored?) -> options:",
          {k: v for k, v in params.get_search_options().items()
           if k in ("max_length", "min_length", "max_new_tokens")})
except Exception as exc:  # noqa: BLE001
    print(f"  max_new_tokens REJECTED: {type(exc).__name__}: {exc}")

print("\n== trap 2: is max_length the TOTAL sequence bound? ==")
prompt = "<|im_start|>user\nSay the single word: hello<|im_end|>\n<|im_start|>assistant\n"
ids = np.asarray(tokenizer.encode(prompt), dtype=np.int32)
n = int(ids.shape[0])
print(f"  prompt_tokens={n}")
for label, max_length in (("== prompt+64", n + 64), ("== prompt", n),
                          ("== prompt-1", n - 1), ("== prompt+1", n + 1)):
    try:
        p = og.GeneratorParams(model)
        p.set_search_options(max_length=max_length, do_sample=False)
        g = og.Generator(model, p)
        g.append_tokens(ids)
        steps = 0
        while not g.is_done() and steps < 200:
            g.generate_next_token()
            steps += 1
        seq = list(g.get_sequence(0))
        print(f"  max_length{label:>12} ({max_length:>5}): steps={steps} "
              f"seq_len={len(seq)} generated={max(0, len(seq) - n)} "
              f"is_done={g.is_done()}")
    except Exception as exc:  # noqa: BLE001
        print(f"  max_length{label:>12} ({max_length:>5}): FAILED {type(exc).__name__}: {exc}")

print("\n== trap 3: does context_length cap max_length? (export says context_length) ==")
import json
ctx = json.loads((MODEL_DIR / "genai_config.json").read_text(encoding="utf-8"))["model"]["context_length"]
print(f"  export context_length={ctx}")
try:
    p = og.GeneratorParams(model)
    p.set_search_options(max_length=ctx + 1, do_sample=False)
    print("  max_length=context_length+1 ACCEPTED (no validation at set time)")
except Exception as exc:  # noqa: BLE001
    print(f"  max_length=context_length+1 REFUSED: {type(exc).__name__}: {exc}")
