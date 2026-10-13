#!/usr/bin/env python3
"""THE PAGE-TO-SHELL HANDLER MAP MUST BUILD. A gate for the defect that cost 2.5 h.

MEASURED 2026-10-13: `SottoHost.dispatch` built its handler map as a bare dict
literal, and a dict literal evaluates EVERY value -- so ONE entry naming a method
the class does not have raised AttributeError while BUILDING the map, before
`.get(kind)` ran, and dispatch died for EVERY kind. The page-to-shell channel was
dead for two and a half hours (last RECEIVER_READY 22:12:54, first one back
04:47:31) and the shell own log said NOTHING: the exception went to pywebview own
logger.

This gate calls the REAL `dispatch` with a kind nobody knows. Building the map is
the whole test: if it raises, or if BRIDGE_HANDLER_MAP_FAILED is logged, the gate
is RED. No window, no WebView2, nothing launched -- `dispatch` only needs a shell
object and a JSON string.

--neg-arm loads a COPY with one bogus entry added and requires it to go RED.
"""
import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append((label, bool(ok), str(detail)))
    print(('  ok   ' if ok else '  FAIL ') + label
          + ('  -- ' + str(detail) if detail else ''))


def load(path, name):
    here = os.path.dirname(os.path.abspath(path))
    if here not in sys.path:
        sys.path.insert(0, here)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeShell(object):
    """Enough of SottoShell for the map to build. Every attribute the map
    references is supplied, so a MISSING one is the module own fault."""

    def __init__(self):
        self.transparent = False

    def __getattr__(self, name):
        # A callable for anything the map reaches for. The map only READS the
        # attributes while building; it does not call them.
        return lambda *a, **k: None


def run(sw, tag):
    seen = []

    def fake_log(line):
        seen.append(str(line))

    sw.log = fake_log
    host = sw.SottoHost.__new__(sw.SottoHost)
    host._shell = FakeShell()
    wire = json.dumps({"kind": "a-kind-nobody-knows-xyz", "payload": {}})
    raised = None
    try:
        host.dispatch(wire)
    except Exception as exc:  # noqa: BLE001
        raised = repr(exc)
    map_failed = [s for s in seen if "BRIDGE_HANDLER_MAP_FAILED" in s]
    unknown = [s for s in seen if "BRIDGE_UNKNOWN_KIND" in s]
    check(tag + "dispatch does not raise while BUILDING the handler map",
          raised is None, raised or "no exception")
    check(tag + "and the map did NOT report itself unbuildable",
          not map_failed, map_failed[0][:90] if map_failed else "no MAP_FAILED")
    check(tag + "and an unknown kind still reaches the normal path",
          bool(unknown), unknown[0][:90] if unknown else "no BRIDGE_UNKNOWN_KIND")


MUTANT = ("            'lazy-asset': self._lazy_asset,",
          "            'lazy-asset': self._lazy_asset,\n"
          "            'bogusmutant': self._no_such_method_at_all,")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    sw = load(SHELL, 'sotto_shell_map_live')
    print('live shell %s  (%d B)' % (SHELL, os.path.getsize(SHELL)))
    print('-- control: the shipped handler map --')
    run(sw, '')
    control = list(RESULTS)

    if args.neg_arm:
        print('-- neg-arm: ONE bogus entry added to a COPY --')
        tmp = tempfile.mkdtemp(prefix='sotto-handler-map-')
        try:
            src = open(SHELL, 'r', encoding='utf-8').read()
            old, new = MUTANT
            if old not in src:
                check('neg-arm anchor found', False, 'anchor missing -- mutant would be INERT')
            else:
                path = os.path.join(tmp, 'mutant.py')
                open(path, 'w', encoding='utf-8').write(src.replace(old, new, 1))
                m = load(path, 'sotto_shell_map_mut')
                before = len(RESULTS)
                run(m, '  mutant: ')
                red = [r for r in RESULTS[before:] if not r[1]]
                check('neg-arm the bogus entry goes RED',
                      any('unbuildable' in r[0] for r in red),
                      'red=%s' % [r[0].strip()[:60] for r in red])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    control_failed = [r for r in control if not r[1]]
    if args.neg_arm:
        red_checks = [r for r in RESULTS if r[0].startswith('neg-arm ')]
        failed = control_failed + [r for r in red_checks if not r[1]]
        total = len(control) + len(red_checks)
    else:
        failed = control_failed
        total = len(control)
    print('')
    print('VERDICT: %s -- %d check(s), %d fail'
          % ('PASS' if not failed else 'FAIL', total, len(failed)))
    for r in failed:
        print('   FAILED: ' + r[0] + '  -- ' + r[2])
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
