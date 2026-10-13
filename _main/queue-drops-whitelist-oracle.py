import importlib.util, sys, time
import os
ROOT = r'H:/sotto'
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
sys.path.insert(0, os.path.dirname(SHELL))
spec = importlib.util.spec_from_file_location('swq', SHELL)
m = importlib.util.module_from_spec(spec)
sys.modules['swq'] = m
spec.loader.exec_module(m)
print('import ok')
ok = True

class FakeBridge:
    def __init__(self, stats):
        self.last_meter = None
        self.last_worker_stats = stats


def run(fields, label, want):
    global ok
    sh = m.SottoShell.__new__(m.SottoShell)
    sh.bridge = FakeBridge({"tag": "tick", "fields": fields,
                            "line": "WORKER_STATS " + " ".join(k + "=" + str(v) for k, v in fields.items())})
    p = sh.stats()
    good = (p.get("queue_drops") == want)
    if not good:
        ok = False
    print(("  ok   " if good else "  FAIL ") + label + " -> payload=" + repr(p)[:110])


# the worker prints it on EVERY WORKER_STATS line
run({"peak": "0.5", "blocks": "7", "queue_drops": "12"}, "queue_drops printed by the worker", 12.0)
run({"peak": "0.5", "blocks": "7", "queue_drops": "0"}, "zero drops stays zero", 0.0)
# an older worker that does not print it -> the key stays ABSENT, never zero
run({"peak": "0.5", "blocks": "7"}, "absent -> absent (not zero)", None)
print("VERDICT: " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
