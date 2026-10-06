# The language-prompt arms, RUN. One process per arm, launched hidden.
#
# Hard rule (H:/sotto/AGENTS.md): never leave a console on the owner's screen.
# CREATE_NO_WINDOW (0x08000000) ALONE — measured today: adding DETACHED_PROCESS
# (0x8) makes a PowerShell child emit 0 bytes, which would look like a silent arm.
#
# Arms:
#   A-lang0     --lang-id 0            the OLD behaviour, explicit
#   B-default   (no flag)              the shipped default: config 'os' -> host locale
#   C-config13  --config lang-id-config-13.json   proves the CONFIG rung is live
#   D-env13     SOTTO_LANG_ID=13       proves the ENV rung is live
#   E-neg999    --lang-id 999          must be REFUSED, loudly, before model load
#   F-pt-0 / G-pt-12  pt-BR audio, English vs Portuguese prompt
import json
import os
import re
import subprocess
import sys
import time

ROOT = r"H:\sotto"
MAIN = os.path.join(ROOT, "_main")
PY = os.path.join(os.path.dirname(sys.executable), "python.exe")
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
FLAGS = 0x08000000  # CREATE_NO_WINDOW, alone.
PT_WAV = os.path.join(MAIN, "pt-br-sample.wav")
CFG13 = os.path.join(MAIN, "lang-id-config-13.json")

if not os.path.exists(CFG13):
    cfg = json.load(open(os.path.join(ROOT, "worker", "config.json"), encoding="utf-8"))
    cfg["model"]["lang_id"] = 13  # a value that is NOT the default, NOT the host locale
    json.dump(cfg, open(CFG13, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

ARMS = [
    ("A-lang0", ["--selftest", "--lang-id", "0"], {}),
    ("B-default", ["--selftest"], {}),
    ("C-config13", ["--selftest", "--config", CFG13], {}),
    ("D-env13", ["--selftest"], {"SOTTO_LANG_ID": "13"}),
    ("E-neg999", ["--selftest", "--lang-id", "999"], {}),
    ("F-pt-0", ["--selftest", "--audio", PT_WAV, "--lang-id", "0"], {}),
    ("G-pt-12", ["--selftest", "--audio", PT_WAV, "--lang-id", "12"], {}),
]

rows = []
for name, args, extra_env in ARMS:
    if PT_WAV in args and not os.path.exists(PT_WAV):
        rows.append((name, "SKIP", "no pt-BR sample yet", None, None, None))
        continue
    out_p = os.path.join(MAIN, f"lang-id-arm-{name}.jsonl")
    err_p = os.path.join(MAIN, f"lang-id-arm-{name}.err")
    env = dict(os.environ)
    env.update(extra_env)
    t0 = time.time()
    with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
        pr = subprocess.run(
            [PY, WORKER] + args, cwd=ROOT, stdout=fo, stderr=fe, env=env,
            creationflags=FLAGS, timeout=900,
        )
    wall = time.time() - t0
    lang = loaded = done = None
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
    rows.append((name, pr.returncode, f"{wall:.1f}s", lang, loaded, done))

print("=== lang-id arms ===")
fmt = "{:<11} rc={:<3} {:>6}  lang={:<4} ({:<6}) src={:<18} loaded.lang_id={:<5} text={}"
for name, rc, wall, lang, loaded, done in rows:
    if rc == "SKIP":
        print(f"{name:<11} SKIP  {wall}")
        continue
    txt = (done or {}).get("text", "")
    txt = (txt[:70] + "...") if txt and len(txt) > 70 else txt
    print(fmt.format(
        name, rc, wall,
        (lang or {}).get("lang_id", "-"), (lang or {}).get("lang", "-"),
        (lang or {}).get("source", "-"), (loaded or {}).get("lang_id", "-"),
        (f"tokens={(done or {}).get('tokens')} {txt!r}" if done else "(no selftest-done)"),
    ))
print()
for name, rc, wall, lang, loaded, done in rows:
    if rc in ("SKIP",):
        continue
    p = os.path.join(MAIN, f"lang-id-arm-{name}.err")
    head = open(p, encoding="utf-8", errors="replace").read()
    first = [ln for ln in head.splitlines() if ln.strip()][:2]
    print(f"--- {name} rc={rc} stderr head: " + (" | ".join(first) if first else "(empty)"))
