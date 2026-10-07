#!/usr/bin/env python3
"""SCRATCH probe: WHY is the 0.8B export's output degenerate?

Four questions, one process, one load:
  1. what search options does the runtime actually default to?  (the determinism question)
  2. can the model answer a TRIVIAL prompt at all?  (is the export/quant sane)
  3. does my hand-built prompt work, or does it need the export's own convention?
  4. the export's chat_template.jinja writes an EMPTY think block to disable reasoning
     (`<|im_start|>assistant\\n<think>\\n\\n</think>\\n\\n`) -- does that change the output?
Also times each phase (init / append / first token) so the 67 s the real run did not account
for can be attributed, and tests the two ctypes instruments that returned null/false.
Deleted after the receipt quotes it. No window, no audio device, no download.
"""
import ctypes
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime_genai as og

MODEL_DIR = Path(r"H:\sotto\worker\models\qwen3.5-0.8b-ortgenai-cpu")
TRANSCRIPT = (
    "O streamer falou que vai botar os moderadores VIP porque os moderadores não trabalham. "
    "Depois comentou sobre o jogo, que o adversário roubou, e pediu o link do Discord no chat. "
    "Também reclamou que a stream não está liberada e que a galera está pedindo comandos antigos."
)
INSTRUCTIONS = (
    "You are given a transcript of speech from one hour of a person's computer audio. "
    "Reply in the SAME language as the transcript.\n"
    "Answer with exactly two things and nothing else:\n"
    "TITLE: a title of at most 12 words.\n"
    "SUMMARY: a summary of exactly 3 sentences.\n"
    "Do not explain, do not add notes, do not show your reasoning."
)
USER_MY_STYLE = (
    "The transcript is mostly Portuguese. Write the TITLE and the SUMMARY in Portuguese.\n\n"
    f"TRANSCRIPT:\n{TRANSCRIPT}"
)


def config(force_cpu=True):
    cfg = og.Config(str(MODEL_DIR))
    if force_cpu:
        cfg.clear_providers()
        cfg.append_provider("cpu")
    return cfg


def chatml_my_style():
    return (f"<|im_start|>system\n{INSTRUCTIONS}<|im_end|>\n"
            f"<|im_start|>user\n{USER_MY_STYLE}<|im_end|>\n"
            f"<|im_start|>assistant\n")


def chatml_no_think():
    return (f"<|im_start|>system\n{INSTRUCTIONS}<|im_end|>\n"
            f"<|im_start|>user\n{USER_MY_STYLE}<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n\n</think>\n\n")


def run(model, prompt, max_new=200, label=""):
    tokenizer = og.Tokenizer(model)
    t0 = time.perf_counter()
    ids = np.asarray(tokenizer.encode(prompt), dtype=np.int32)
    t_enc = time.perf_counter() - t0
    params = og.GeneratorParams(model)
    params.set_search_options(max_length=int(ids.shape[0]) + max_new, do_sample=False)
    t0 = time.perf_counter()
    generator = og.Generator(model, params)
    t_init = time.perf_counter() - t0
    t0 = time.perf_counter()
    generator.append_tokens(ids)
    t_append = time.perf_counter() - t0
    t0 = time.perf_counter()
    generator.generate_next_token()
    t_first = time.perf_counter() - t0
    t0 = time.perf_counter()
    steps = 1
    while not generator.is_done():
        generator.generate_next_token()
        steps += 1
    t_rest = time.perf_counter() - t0
    seq = list(generator.get_sequence(0))
    out = seq[int(ids.shape[0]):]
    text = tokenizer.decode(np.asarray(out, dtype=np.int32))
    print(f"\n--- {label}")
    print(f"    prompt_tokens={int(ids.shape[0])} new={steps} encode={t_enc:.3f}s "
          f"init={t_init:.3f}s append={t_append:.3f}s first_token={t_first:.3f}s "
          f"rest={t_rest:.3f}s ({steps - 1 / max(t_rest, 1e-9):.1f} tok/s)")
    print(f"    RAW: {text!r}")
    return text


def main():
    print("== ctypes instruments ==")
    try:
        counters = ctypes.c_ulong * 2
        print("  ctypes.windll present:", hasattr(ctypes, "windll"))
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        print("  psapi loaded:", bool(psapi), "kernel32 loaded:", bool(k32))
        print("  GetCurrentProcess:", k32.GetCurrentProcess())
    except Exception as exc:  # noqa: BLE001
        print("  ctypes FAILED:", type(exc).__name__, exc)
    sys.path.insert(0, r"H:\sotto\worker")
    import qwen_summary as qs
    print("  qs.peak_rss_mb() =", qs.peak_rss_mb())
    print("  qs.set_priority('below-normal') =", qs.set_priority("below-normal"))

    print("\n== load ==")
    t0 = time.perf_counter()
    model = og.Model(config())
    print(f"  loaded in {time.perf_counter() - t0:.2f}s device_type={model.device_type!r}")
    tokenizer = og.Tokenizer(model)
    print(f"  og.Tokenizer(model) ok; eos={tokenizer.eos_token_ids}")

    params = og.GeneratorParams(model)
    print("  search options BEFORE set:", json.dumps(params.get_search_options(), default=str))
    params.set_search_options(max_length=256, do_sample=False)
    print("  search options AFTER  set:", json.dumps(params.get_search_options(), default=str))

    # 1. Trivial prompt: can this export generate coherent text at all?
    run(model, "<|im_start|>user\nResponda apenas com a palavra: olá<|im_end|>\n"
               "<|im_start|>assistant\n<think>\n\n</think>\n\n", max_new=20,
        label="A: trivial prompt (empty think block)")

    # 2. My hand-built prompt, exactly as the CLI builds it today.
    run(model, chatml_my_style(), max_new=200, label="B: CLI prompt as shipped (no think block)")

    # 3. Same prompt + the empty think block the export's own template writes.
    run(model, chatml_no_think(), max_new=200,
        label="C: same prompt + empty think block (the template's convention)")

    # 4. The export's own chat template, verbatim, via apply_chat_template.
    try:
        template = (MODEL_DIR / "chat_template.jinja").read_text(encoding="utf-8")
        messages = json.dumps([
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": USER_MY_STYLE},
        ])
        prompt = tokenizer.apply_chat_template(messages, template_str=template,
                                               add_generation_prompt=True)
        print(f"\n--- D: apply_chat_template tail: ...{prompt[-80:]!r}")
        run(model, prompt, max_new=200, label="D: export's own chat template")
    except Exception as exc:  # noqa: BLE001
        print(f"\n--- D: apply_chat_template FAILED: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
