"""The default-choice arms: lang_id 0 (en-US) vs 12 (pt-BR, what 'os' resolves to on this
box) vs 101 (the model's own autoSlot), on BOTH a known-ENGLISH sample and a known-PORTUGUESE
sample. One worker process per arm, launched hidden (CREATE_NO_WINDOW ALONE — the house rule;
adding DETACHED_PROCESS makes a child emit 0 bytes on this box, measured).

Deliverable of lane SottoLangDefault: which single literal belongs in worker/config.json.

usage: py -3 _main/lang-id-default-arms.py
"""
import json
import os
import subprocess
import sys
import time

ROOT = r"H:\sotto"
MAIN = os.path.join(ROOT, "_main")
PY = os.path.join(os.path.dirname(sys.executable), "python.exe")
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
FLAGS = 0x08000000  # CREATE_NO_WINDOW, alone.

EN = os.path.join(ROOT, "worker", "assets", "sample1.flac")   # known ENGLISH read speech
PT = os.path.join(MAIN, "pt-br-sample.wav")                   # known pt-BR (SAPI Maria TTS)

# (tag, extra-argv, extra-env)
ARMS = [
    ("en-0",       ["--audio", EN, "--lang-id", "0"],   {}),
    ("en-12",      ["--audio", EN, "--lang-id", "12"],  {}),
    ("en-101",     ["--audio", EN, "--lang-id", "101"], {}),
    ("en-default", ["--audio", EN],                     {}),   # no flag -> config 'os' -> 12
    ("pt-0",       ["--audio", PT, "--lang-id", "0"],   {}),
    ("pt-12",      ["--audio", PT, "--lang-id", "12"],  {}),
    ("pt-101",     ["--audio", PT, "--lang-id", "101"], {}),
]


def run(name, extra, env_extra):
    out_p = os.path.join(MAIN, f"langdef-arm-{name}.jsonl")
    err_p = os.path.join(MAIN, f"langdef-arm-{name}.err")
    env = dict(os.environ)
    env.update(env_extra)
    t0 = time.time()
    with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
        pr = subprocess.run(
            [PY, WORKER, "--selftest"] + extra, cwd=ROOT, stdout=fo, stderr=fe,
            env=env, creationflags=FLAGS, timeout=1200,
        )
    wall = time.time() - t0
    lang = loaded = done = None
    cap = 0
    for line in open(out_p, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("state") == "boot" and o.get("stage") == "lang":
            lang = o
        elif o.get("state") == "model-loaded":
            loaded = o
        elif o.get("state") == "selftest-done":
            done = o
        elif o.get("type") == "caption":
            cap += 1
    return {
        "tag": name, "rc": pr.returncode, "wall_s": round(wall, 1),
        "resolved": (lang or {}).get("lang_id"), "lang": (lang or {}).get("lang"),
        "source": (lang or {}).get("source"),
        "loaded_lang_id": (loaded or {}).get("lang_id"),
        "captions": cap,
        "tokens": (done or {}).get("tokens"),
        "frames": (done or {}).get("frames"),
        "blank_frac": (done or {}).get("blank_frac"),
        "empty_chunks": (done or {}).get("empty_chunks"),
        "vad_gated_chunks": (done or {}).get("vad_gated_chunks"),
        "text": (done or {}).get("text"),
    }


REPEATS = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("REPEATS", "1"))
rows = []
for rep in range(REPEATS):
    for a in ARMS:
        tag = a[0] if rep == 0 else f"{a[0]}#{rep+1}"
        rows.append(run(tag, a[1], a[2]))
with open(os.path.join(MAIN, "langdef-arms.json"), "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=2, ensure_ascii=False)

FMT = "{:<14} {:>3} {:>4} {:<7} {:<18} {:<6} {:>3} {:>4} {:>6} {:>9} {:>5} {:>5}"
print("=== lang_id default arms (REPEATS=%d) ===" % REPEATS)
print(FMT.format("arm", "rc", "id", "lang", "source", "loaded", "cap", "tok",
                 "frames", "blank", "empty", "gated"))
for r in rows:
    print(FMT.format(
        r["tag"], r["rc"], str(r["resolved"]), str(r["lang"]), str(r["source"]),
        str(r["loaded_lang_id"]), r["captions"], str(r["tokens"]), str(r["frames"]),
        str(r["blank_frac"]), str(r["empty_chunks"]), str(r["vad_gated_chunks"]),
    ))
print()
for r in rows:
    print(f"--- {r['tag']}: rc={r['rc']} text={r['text']!r}")

# Stability: for each base arm, the set of (tokens, frames, blank_frac) over repeats.
from collections import OrderedDict
byarm = OrderedDict()
for r in rows:
    base = r["tag"].split("#")[0]
    byarm.setdefault(base, []).append((r["tokens"], r["frames"], r["blank_frac"], r["captions"]))
print()
for base, vals in byarm.items():
    uniq = sorted(set(vals))
    print(f"stability {base:<11} n={len(vals)} distinct(tok,frames,blank,cap)={len(uniq)} {uniq}")
