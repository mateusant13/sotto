"""ram_gate.py -- the ENFORCEMENT. Reads the two soak receipts and says PASS/FAIL.

The gate is allowed to say NO. Three ways it can:

  * if the uncapped arm did NOT grow, the premise is refuted -- the cap is not
    what is bounding memory, and this gate says NO rather than passing a
    measurement that proves nothing;
  * if the capped arm DID grow, the cap does not hold and the gate says NO;
  * if the cap is not actually the reason (capped ~= uncapped), the cap does
    NOTHING and the gate says NO and names that as the finding.

Usage:
  python ram_gate.py --uncapped soak-uncapped.json --capped soak-capped.json
                     --uncapped-limit-mib 8 --capped-limit-mib 96

Exit 0 = PASS, 1 = FAIL (red). Print the reason either way.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(p: str) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))["soak"]


def arm_summary(a: dict) -> dict:
    """Reduce a soak receipt to the facts the gate reasons about."""
    c = a["curve"]
    ws = [s["ws_mib"] for s in c]
    pv = [s["private_mib"] for s in c]
    iv = a["interval_s"]
    n1 = max(1, int(60.0 / iv))
    n5 = max(1, int(300.0 / iv))
    first1 = ws[:n1]
    last5 = ws[-n5:] if len(ws) >= n5 else ws
    return {
        "arm": a["arm"],
        "samples": a["samples"],
        "interval_s": iv,
        "window_s": a["window_s"],
        "rows_ingested": a["rows_ingested"],
        "cap": a["max_rows_cap"],
        "ws_first1_mean_mib": sum(first1) / len(first1) if first1 else 0.0,
        "ws_last5_mean_mib": sum(last5) / len(last5) if last5 else 0.0,
        "ws_growth_mib": (sum(last5) / len(last5) - sum(first1) / len(first1))
        if first1 and last5 else 0.0,
        "ws_max_mib": max(ws) if ws else 0.0,
        "private_max_mib": max(pv) if pv else 0.0,
        "ws_slope_mib_per_hour": a["ws_slope_mib_per_hour"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uncapped", required=True)
    ap.add_argument("--capped", required=True)
    ap.add_argument("--uncapped-limit-mib", type=float, default=8.0,
                    help="uncapped arm MUST grow at least this much")
    ap.add_argument("--capped-limit-mib", type=float, default=96.0,
                    help="capped arm MUST stay under this")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    u = arm_summary(load(a.uncapped))
    k = arm_summary(load(a.capped))
    same_population = u["rows_ingested"] == k["rows_ingested"]
    findings: list[str] = []
    verdict = "PASS"

    if not same_population:
        verdict = "FAIL"
        findings.append(
            f"arms are NOT the same population: uncapped ingested "
            f"{u['rows_ingested']} rows, capped ingested {k['rows_ingested']} -- "
            "the comparison would be meaningless")

    if u["ws_growth_mib"] < a.uncapped_limit_mib:
        verdict = "FAIL"
        findings.append(
            f"UNCAPPED DID NOT GROW ({u['ws_growth_mib']:.1f} MiB over the window, "
            f"need >= {a.uncapped_limit_mib} MiB). The cap is NOT what bounds this "
            "workload, so keeping it proves nothing. THIS IS THE FINDING, not a pass.")

    if k["ws_max_mib"] > a.capped_limit_mib:
        verdict = "FAIL"
        findings.append(
            f"CAPPED EXCEEDED ITS BOUND: peak WS {k['ws_max_mib']:.1f} MiB > "
            f"{a.capped_limit_mib} MiB. The cap does not hold.")

    if k["ws_growth_mib"] >= a.uncapped_limit_mib:
        verdict = "FAIL"
        findings.append(
            f"CAPPED GREW LIKE THE UNCAPPED ARM ({k['ws_growth_mib']:.1f} MiB). "
            "The cap is inert -- it does not flatten the curve.")

    if verdict == "PASS":
        findings.append(
            f"uncapped grew {u['ws_growth_mib']:.1f} MiB "
            f"(slope {u['ws_slope_mib_per_hour']:.1f} MiB/h) while capped moved "
            f"{k['ws_growth_mib']:.1f} MiB "
            f"(slope {k['ws_slope_mib_per_hour']:.1f} MiB/h) at the same row count; "
            f"capped peak {k['ws_max_mib']:.1f} MiB under a "
            f"{k['cap']}-row cap.")

    rec = {
        "verdict": verdict,
        "uncapped": u,
        "capped": k,
        "thresholds": {"uncapped_min_growth_mib": a.uncapped_limit_mib,
                       "capped_max_ws_mib": a.capped_limit_mib},
        "findings": findings,
    }
    txt = json.dumps(rec, indent=2)
    print(txt)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    print(f"RESULT: {'PASS' if verdict == 'PASS' else 'FAIL'} -- ram cap "
          f"{'holds' if verdict == 'PASS' else 'does NOT hold'}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())