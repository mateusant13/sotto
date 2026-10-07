"""ocr-score-02.py — score RapidOCR vs Windows OCR against the synthetic ground truth.

Metrics per arm and engine:
  recall   = fraction of the 7 ground-truth strings that were recovered (exact or
             as a substring of a returned box), which tolerates a line being split
  exact    = fraction recovered by an exactly-equal box
  cer      = character error rate against the concatenated ground truth (best
             assignment is not attempted; the whole GT block is the reference and
             the whole output block is the hypothesis, both normalised to letters
             and digits, which is the number that matters for "can I find this
             phrase later")
  boxes    = number of returned text boxes (false-positive pressure)

Inputs:  _main/ocr-bench-02.json       (RapidOCR, written by ocr-bench-02.py)
         _main/ocr-winocr-raw.txt      (Windows OCR, written by _winocr-probe.ps1)
Writes:  _main/ocr-score-02.json
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
GT = json.load(open(os.path.join(HERE, "ocr-frames", "_ground_truth.json"), encoding="utf-8"))
RAPID = json.load(open(os.path.join(HERE, "ocr-bench-02.json"), encoding="utf-8"))

NORM = re.compile(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ\u0400-\u04FF\u3040-\u30FF\u4E00-\u9FFF]+")


def norm(s):
    return NORM.sub("", s).lower()


def levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def score(gt_list, boxes):
    got = [norm(b) for b in boxes]
    exact = 0
    recalled = 0
    for g in gt_list:
        ng = norm(g)
        if not ng:
            continue
        if any(ng == x for x in got):
            exact += 1
            recalled += 1
        elif any(ng in x or x in ng for x in got if len(x) > 2):
            recalled += 1
    ref = norm(" ".join(gt_list))
    hyp = norm(" ".join(boxes))
    cer = levenshtein(ref, hyp) / max(1, len(ref))
    return {"gt_count": len(gt_list), "exact": exact, "recalled": recalled,
            "recall": round(recalled / len(gt_list), 3), "exact_rate": round(exact / len(gt_list), 3),
            "cer": round(cer, 3), "boxes": len(boxes)}


# ---- parse the Windows OCR raw log into per-frame boxes ----
WINDOWS = {}
cur = None
for line in open(os.path.join(HERE, "ocr-winocr-raw.txt"), encoding="utf-8", errors="replace"):
    line = line.rstrip("\n")
    m = re.match(r"--- FRAME (\S+)", line)
    if m:
        cur = m.group(1)
        WINDOWS[cur] = {"texts": [], "ms": None}
        continue
    m = re.match(r"MS (\d+)", line)
    if m and cur:
        WINDOWS[cur]["ms"] = int(m.group(1))
        continue
    m = re.match(r"LINE \d+ \| (.*) \| words=\d+$", line)
    if m and cur:
        WINDOWS[cur]["texts"].append(m.group(1))

out = {"rapidocr": [], "windows_ocr": []}
for f in RAPID["frames"]:
    name = f["arm"]
    gt = f["ground_truth"]
    arm = {"arm": name, "latency_min_s": f.get("latency_min_s")}
    arm.update(score(gt, f.get("texts", [])))
    out["rapidocr"].append(arm)

for arm in RAPID["frames"]:
    key = [k for k in WINDOWS if arm["arm"] in k]
    if not key:
        continue
    k = key[0]
    res = {"arm": arm["arm"], "engine_ms": WINDOWS[k]["ms"]}
    res.update(score(arm["ground_truth"], WINDOWS[k]["texts"]))
    out["windows_ocr"].append(res)

with open(os.path.join(HERE, "ocr-score-02.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)

for key in ("rapidocr", "windows_ocr"):
    print("==", key)
    for r in out[key]:
        print("  {arm:24s} recall={recall:.2f} exact={exact_rate:.2f} cer={cer:.3f} boxes={boxes:2d} "
              "lat={latency_min_s} ms={engine_ms}".format(
                  arm=r["arm"], recall=r["recall"], exact_rate=r["exact_rate"], cer=r["cer"],
                  boxes=r["boxes"], latency_min_s=r.get("latency_min_s"), engine_ms=r.get("engine_ms")))
