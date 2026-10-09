"""Negative control for _diar-der.py -- does the DER meter actually MOVE?

A DER of 0.03% is only meaningful if a WRONG hypothesis scores higher. This
drives the real `der()` function (imported from _diar-der.py, not reimplemented)
on the vendor's published 4-speaker ground truth against deliberately broken
hypotheses. Every perturbation must push DER UP; the identity must stay at 0.

  A identity                 -> DER 0.00   (GREEN: the meter is not stuck high)
  B shift all boundaries +0.5 -> miss and false alarm appear
  C swap two speaker labels   -> must be INVARIANT (the mapping absorbs it)
  C2 merge two hyp speakers   -> speaker error appears, boundaries untouched
  D drop the last 3 segments  -> miss
  E invent a segment in silence -> false alarm
  F collapse to ONE speaker   -> massive speaker error
  G permute the label mapping -> must be INVARIANT (the mapping is optimal)

C and G test the OTHER direction, and C was written as a RED arm first and came
back 0.00 -- the EXPECTATION was wrong, not the meter: because the DER uses an
optimal one-to-one mapping, a pure relabelling is exactly what the mapping
absorbs. That is the property we want (the meter scores who-spoke-when, not
label NAMES). C2 is the arm that isolates speaker error while leaving every
boundary intact.
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("diar_der", os.path.join(HERE, "_diar-der.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

REF = list(m.VENDOR_4SPK)
DUR = 56.8606875
SILENT_GAP = (18.5, 21.5)          # between the 17.041 and 22.137 ref segments


def relabel(seg, fn):
    return [(a, b, fn(s)) for (a, b, s) in seg]


ARMS = [
    ("A identity", REF, "GREEN", 0.0),
    ("B shift +0.5s", [(a + 0.5, b + 0.5, s) for (a, b, s) in REF], "RED", None),
    ("C swap s00/s01", relabel(REF, lambda s: {"s00": "s01", "s01": "s00"}.get(s, s)), "INVARIANT", None),
    ("C2 merge s00+s01 in hyp", relabel(REF, lambda s: "s00" if s in ("s00", "s01") else s), "RED", None),
    ("D drop last 3", REF[:-3], "RED", None),
    ("E false alarm in silence", REF + [(SILENT_GAP[0], SILENT_GAP[1], "s00")], "RED", None),
    ("F collapse to one speaker", relabel(REF, lambda s: "s00"), "RED", None),
    ("G permute all labels", relabel(REF, lambda s: {"s00": "s03", "s01": "s02",
                                                     "s02": "s01", "s03": "s00"}[s]),
     "INVARIANT", None),
]

print("instrument: _diar-der.py der()  frame=%.0f ms  collar=%d ms  ref=vendor 4spk/10seg"
      % (m.FRAME * 1000, 0))
print("%-28s %8s %8s %8s %8s   %s" % ("arm", "DER%", "miss%", "fa%", "spk%", "expectation"))
rows = []
ok = True
for name, hyp, expect, want in ARMS:
    r = m.der(REF, hyp, DUR)
    rows.append({"arm": name, "expectation": expect, **{k: (v if not hasattr(v, "item") else v.item())
                                                        for k, v in r.items()}})
    print("%-28s %8.2f %8.2f %8.2f %8.2f   %s"
          % (name, r["DER_pct"], r["miss_pct"], r["false_alarm_pct"],
             r["speaker_error_pct"], expect))

by = {r["arm"]: r for r in rows}
ident = by["A identity"]["DER_pct"]
checks = []
checks.append(("A identity is exactly 0.00", bool(ident == 0.0), "DER=%.2f" % ident))
for name in ("B shift +0.5s", "C2 merge s00+s01 in hyp", "D drop last 3",
             "E false alarm in silence", "F collapse to one speaker"):
    r = by[name]
    checks.append(("%s moves DER up" % name, bool(r["DER_pct"] > ident + 1.0),
                   "DER %.2f%% -> %.2f%%" % (ident, r["DER_pct"])))
checks.append(("C2 isolates speaker error (miss=fa=0)",
               bool(by["C2 merge s00+s01 in hyp"]["miss_pct"] == 0.0
                    and by["C2 merge s00+s01 in hyp"]["false_alarm_pct"] == 0.0),
               "miss=%.2f fa=%.2f spk=%.2f" % (by["C2 merge s00+s01 in hyp"]["miss_pct"],
                                               by["C2 merge s00+s01 in hyp"]["false_alarm_pct"],
                                               by["C2 merge s00+s01 in hyp"]["speaker_error_pct"])))
checks.append(("C2 keeps the boundaries (spk>0 only)",
               bool(by["C2 merge s00+s01 in hyp"]["speaker_error_pct"] > 0.0),
               "spk=%.2f" % by["C2 merge s00+s01 in hyp"]["speaker_error_pct"]))
checks.append(("D isolates miss (fa=spk=0)",
               bool(by["D drop last 3"]["false_alarm_pct"] == 0.0
                    and by["D drop last 3"]["speaker_error_pct"] == 0.0),
               "miss=%.2f fa=%.2f spk=%.2f" % (by["D drop last 3"]["miss_pct"],
                                               by["D drop last 3"]["false_alarm_pct"],
                                               by["D drop last 3"]["speaker_error_pct"])))
checks.append(("E isolates false alarm (miss=spk=0)",
               bool(by["E false alarm in silence"]["miss_pct"] == 0.0
                    and by["E false alarm in silence"]["speaker_error_pct"] == 0.0),
               "miss=%.2f fa=%.2f spk=%.2f" % (by["E false alarm in silence"]["miss_pct"],
                                               by["E false alarm in silence"]["false_alarm_pct"],
                                               by["E false alarm in silence"]["speaker_error_pct"])))
checks.append(("C relabelling is INVARIANT (optimal mapping)",
               bool(abs(by["C swap s00/s01"]["DER_pct"] - ident) < 1e-9),
               "DER %.2f%% vs identity %.2f%%" % (by["C swap s00/s01"]["DER_pct"], ident)))
checks.append(("G relabelling is INVARIANT (optimal mapping)",
               bool(abs(by["G permute all labels"]["DER_pct"] - ident) < 1e-9),
               "DER %.2f%% vs identity %.2f%%" % (by["G permute all labels"]["DER_pct"], ident)))

print()
for name, good, detail in checks:
    print("  %-46s %-4s  %s" % (name, "PASS" if good else "FAIL", detail))
    ok = ok and good

out = os.path.join(HERE, "_diar-der-selftest.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump({"arms": rows, "checks": [{"name": n, "pass": g, "detail": d} for n, g, d in checks],
               "verdict": "PASS" if ok else "FAIL"}, fh, indent=1)
print("\nSELFTEST-VERDICT: %s   (%d/%d checks)   wrote %s"
      % ("PASS" if ok else "FAIL", sum(1 for _, g, _ in checks if g), len(checks), out))
sys.exit(0 if ok else 1)
