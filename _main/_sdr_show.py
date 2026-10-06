import json
import sys


def show(path, states, caps=0, stats=1):
    print("=====", path, "=====")
    ncap = 0
    for ln in open(path, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("WORKER_STATS"):
            if stats:
                print(ln)
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if o.get("type") == "caption" and ncap < caps:
            ncap += 1
            print("CAPTION", json.dumps(o, ensure_ascii=False))
        if o.get("type") == "status" and o.get("state") in states:
            print(json.dumps(o, ensure_ascii=False)[:600])


show(sys.argv[1], set(sys.argv[2].split(",")), caps=int(sys.argv[3] if len(sys.argv) > 3 else 0))
