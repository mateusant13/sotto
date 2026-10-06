"""Run the SHIPPED worker selftest against one audio file, hidden, and dump JSONL.

Exists because the brief's hard rule forbids a visible console: the child is a
real `worker/sotto_worker.py` process launched with CREATE_NO_WINDOW, capturing
stdout (the JSONL contract) and stderr separately. No device is opened --
`--selftest` is file mode.

usage: py -3 _main/vad-arm-run.py <tag> <config.json> <audio path>
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CREATE_NO_WINDOW = 0x08000000

tag, cfg, audio = sys.argv[1], sys.argv[2], sys.argv[3]
out_path = os.path.join(HERE, f"vad-arm-{tag}.jsonl")
err_path = os.path.join(HERE, f"vad-arm-{tag}.err.txt")

with open(out_path, "w", encoding="utf-8") as out, open(err_path, "w", encoding="utf-8") as err:
    rc = subprocess.call(
        [sys.executable, "worker/sotto_worker.py", "--config", cfg,
         "--selftest", "--audio", audio],
        cwd=ROOT, stdout=out, stderr=err, creationflags=CREATE_NO_WINDOW,
    )

rows = []
for line in open(out_path, encoding="utf-8"):
    line = line.strip()
    if line:
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"_malformed": line})

captions = [r for r in rows if r.get("type") == "caption"]
done = [r for r in rows if r.get("state") == "selftest-done"]
summary = {
    "tag": tag,
    "config": cfg,
    "audio": audio,
    "rc": rc,
    "non_json_lines": sum(1 for r in rows if "_malformed" in r),
    "caption_count": len(captions),
    "captions": captions,
    "done": done[0] if done else None,
    "states": sorted({r.get("state") for r in rows if r.get("state")}),
}
with open(os.path.join(HERE, f"vad-arm-{tag}.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2, ensure_ascii=False)
print(json.dumps({k: summary[k] for k in ("tag", "rc", "caption_count", "non_json_lines")}))
