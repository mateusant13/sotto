"""probe-20261007-python-twin.py — EXERCISES the Python writer `_history_provenance`.

Lane SottoProvenanceLive. Imports the REAL module (not a copy) and calls the
staticmethod with each of the three src shapes plus the fail-closed arms.
No window, no audio, no device. Read-only w.r.t. anything but stdout.
"""
import importlib.util
import json
import os
import sys

MP = r"H:/sotto/app/webview/sotto_webview.py"
sys.path.insert(0, os.path.dirname(MP))
spec = importlib.util.spec_from_file_location("sotto_webview", MP)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

prov = mod.SottoShell._history_provenance

print(json.dumps({
    "HISTORY_ROUTES": list(mod.HISTORY_ROUTES),
    "HISTORY_ROUTE_SOURCES": list(mod.HISTORY_ROUTE_SOURCES),
}))

CASES = [
    ("worker-stamped", {"route": "final", "start": 12.34,
                        "routeSource": "worker-stamped", "reason": "hold-timeout"}),
    ("panel-deadline", {"route": "provisional-draft", "start": 5.0,
                        "routeSource": "panel-deadline", "reason": "status-change"}),
    ("fallback", {"route": "final", "start": None,
                  "routeSource": "fallback", "reason": ""}),
    ("unknown-src-live", {"route": "final", "start": 1.0,
                          "routeSource": "live", "reason": ""}),
    ("absent-src", {"route": "final", "start": 1.0, "reason": "hold-timeout"}),
    ("absent-route", {"start": 1.0, "routeSource": "worker-stamped"}),
    ("unknown-route", {"route": "live", "routeSource": "worker-stamped"}),
    ("not-a-dict", None),
]
for name, options in CASES:
    out = prov(options)
    print(json.dumps({"case": name, "in": options, "out": out}))
