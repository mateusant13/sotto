#!/usr/bin/env python3
"""THE HANDLER MAP MUST BUILD, AND ONE BAD ENTRY MUST COST ONLY ITS OWN KIND.

MEASURED 2026-10-13, defect #1: `SottoHost.dispatch` built its handler map as a
bare dict literal, and a dict literal evaluates EVERY value -- so ONE entry naming
a method the class does not have (`self._set_strip_offset`, a SottoShell method)
raised AttributeError while BUILDING the map, before `.get(kind)` ran, and
dispatch died for EVERY kind. The page-to-shell channel was dead for two and a
half hours (last RECEIVER_READY 22:12:54, first one back 04:47:31) and the shell
own log said NOTHING: the exception went to pywebview own logger.

Defect #2, and the reason this gate has a second arm: the guard committed in
`9c8649f` made that failure LOUD but did not ISOLATE it -- the fallback was an
EMPTY map, so every kind still died. The fix builds the table as NAME -> NAME and
resolves each entry with `getattr`, one at a time, so a bad entry costs ONLY its
own kind and names itself:

    BRIDGE_HANDLER_MAP_FAILED kind=... name=... error=...

ARMS -- no window, no WebView2, nothing launched: `dispatch` needs a shell object
and a JSON string.
  control    the shipped table: builds, holds exactly the kinds the page sends,
             EVERY one of them reaches a handler, an unknown kind still lands in
             BRIDGE_UNKNOWN_KIND, and NOT ONE entry reports itself unresolvable.
  isolation  ONE entry naming a method `SottoHost` does not have, injected into a
             COPY: it must be SKIPPED and NAMED, and a good kind must still
             dispatch. This arm must PASS on the live shell.
  --neg-arm  M1: an ATTRIBUTE ACCESS written in the table (defect #1 exact
             shape) -- the whole table fails to build and the last-resort net is
             loud about it.
             M3: the isolation arm bad entry with the per-entry guard NEUTERED
             -- the good kind must DIE.
             Both mutants must go RED, for the RIGHT reason, or this gate is not
             saying NO to anything.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

#: THE PAGE -> SHELL VOCABULARY, pinned. A RENAMED entry kills the page call
#: silently (the page posts a kind nobody answers) -- the 2026-10-13 outage, one
#: entry at a time. The table is a LOCAL inside `dispatch`, so this is read from
#: the source text; a shape that drifts returns fewer kinds and the arm says so.
EXPECTED_KINDS = (
    'caption-observed', 'status-observed', 'caption-applied', 'status-applied',
    'caption-cleared', 'renderer-ready', 'page-error', 'pointer', 'transparency',
    'sotto:transparency', 'setStripOffset', 'sotto:setStripOffset',
    'history-append', 'history-tail', 'history-search', 'history-root',
    'history-reveal', 'hide', 'toggle', 'quit', 'revive', 'info',
    'panel-surface', 'stats', 'lazy-asset',
)
KIND_LINE = re.compile(r"^            '([^']+)': \('(?:host|shell|shell-call)', ", re.M)
#: The page own senders, inside the preload JS this shell injects. `lazy-asset`
#: is NOT here -- it is posted by app/panel/lazy-assets.js -- and is pinned by
#: name in EXPECTED_KINDS.
POST_KIND = re.compile(r"(?:post|historyCall)\('([^']+)'", re.M)
UNKNOWN_KIND = 'a-kind-nobody-knows-xyz'

#: M1 -- defect #1 shape: an attribute ACCESS inside the table.
M1_ANCHOR = "            'lazy-asset': ('host', '_lazy_asset'),"
M1_TEXT = ("            'lazy-asset': self._lazy_asset,\n"
           "            'bogusmutant': self._no_such_method_at_all,")
#: The isolation arm bad entry: the SHAPE the table uses now, naming a method
#: `SottoHost` does not have.
ISOLATION_ANCHOR = M1_ANCHOR
ISOLATION_TEXT = ("            'lazy-asset': ('host', '_lazy_asset'),\n"
                  "            'bogusmutant': ('host', '_no_such_method_at_all'),")
#: M3 -- the per-entry guard NEUTERED (`except ()` catches nothing).
GUARD_ANCHOR = ("            except Exception as exc:  # noqa: BLE001 -- one dead kind, not all\n")
GUARD_TEXT = ("            except () as exc:  # NEUTERED by --neg-arm: this catches nothing\n")

BAD_KIND = 'bogusmutant'
BAD_NAME = '_no_such_method_at_all'

RESULTS = []
UNCOUNTED = set()
_TMP = []


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
    """Enough of SottoShell for EVERY entry to RESOLVE. Every attribute the table
    reaches for is supplied, so an entry that does not resolve is the shell own
    fault and not this stub."""

    def __init__(self):
        self.transparent = False

    def __getattr__(self, name):
        return lambda *a, **k: None


def new_host(sw, seen):
    sw.log = seen.append
    host = sw.SottoHost.__new__(sw.SottoHost)
    host._shell = FakeShell()
    return host


def send(host, kind, payload=None):
    """One wire, exactly as the page sends it. Returns the exception text, if any."""
    raised = None
    try:
        host.dispatch(json.dumps({'kind': kind, 'payload': payload or {}}))
    except Exception as exc:  # noqa: BLE001
        raised = repr(exc)
    return raised


def kinds_in(src):
    return KIND_LINE.findall(src)


def build_arm(sw, tag):
    """Does the map build, is it quiet, does an unknown kind still land?"""
    seen = []
    host = new_host(sw, seen)
    raised = send(host, UNKNOWN_KIND)
    check(tag + 'dispatch does not raise while BUILDING the handler map',
          raised is None, raised or 'no exception')
    failed = [s for s in seen if 'BRIDGE_HANDLER_MAP_FAILED' in s]
    check(tag + 'and NOT ONE entry reports itself unresolvable',
          not failed, failed[0][:110] if failed else 'no MAP_FAILED')
    unknown = [s for s in seen if 'BRIDGE_UNKNOWN_KIND' in s]
    check(tag + 'and an unknown kind still reaches the normal path',
          bool(unknown), unknown[0][:90] if unknown else 'no BRIDGE_UNKNOWN_KIND')
    return host, seen


def run_control(sw, src):
    host, seen = build_arm(sw, '')
    found = kinds_in(src)
    missing = sorted(set(EXPECTED_KINDS) - set(found))
    extra = sorted(set(found) - set(EXPECTED_KINDS))
    check('and the shipped table holds the page vocabulary (%d kind(s))'
          % len(EXPECTED_KINDS),
          not missing and not extra,
          ('missing=%s extra=%s' % (missing, extra)) if (missing or extra) else 'exact')
    posted = sorted(set(POST_KIND.findall(src)))
    unhandled = [k for k in posted if k not in set(found)]
    check('and every kind the injected preload can post has a handler (%d)'
          % len(posted), not unhandled,
          ('unhandled=%s' % unhandled) if unhandled else 'all handled')
    dead = []
    for kind in sorted(found):
        mark = len(seen)
        raised = send(host, kind)
        tail = seen[mark:]
        if (raised or any('BRIDGE_HANDLER_MAP_FAILED' in s for s in tail)
                or any('BRIDGE_UNKNOWN_KIND' in s for s in tail)):
            dead.append('%s%s' % (kind, ' raised=%s' % raised if raised else ''))
    check('and EVERY shipped kind reaches a handler (none lands in '
          'BRIDGE_UNKNOWN_KIND)', not dead,
          ('dead=%s' % dead[:4]) if dead else 'all live')


def run_isolation(sw, tag):
    """ONE bad entry in a COPY: named, skipped, and the other kinds still work."""
    seen = []
    host = new_host(sw, seen)
    raised = send(host, UNKNOWN_KIND)
    check(tag + 'dispatch does not raise while ONE entry is unresolvable',
          raised is None, raised or 'no exception')
    named = [s for s in seen if 'BRIDGE_HANDLER_MAP_FAILED' in s]
    whole = [s for s in named if ' kind=' not in s]
    right = [s for s in named
             if ("kind='%s'" % BAD_KIND) in s and ("name='%s'" % BAD_NAME) in s]
    check(tag + 'the bad entry NAMES ITSELF (kind= and name=) and the map is NOT '
          'reported unbuildable',
          bool(named) and not whole and len(right) == len(named),
          (named[0][:130] if named else 'no MAP_FAILED at all')
          + (' | whole-map=%s' % whole[:1] if whole else ''))
    mark = len(seen)
    raised = send(host, 'renderer-ready')
    tail = seen[mark:]
    check(tag + 'and a GOOD kind still dispatches (the isolation is real)',
          raised is None and any('RECEIVER_READY' in s for s in tail)
          and not any('BRIDGE_UNKNOWN_KIND' in s for s in tail),
          'raised=%s tail=%s' % (raised, [s[:60] for s in tail[:3]]))


def mutant(src, edits, name):
    """Write the mutated COPY and return its module; None (with a RED check) when
    any anchor is not there exactly once -- a mutant that cannot be built must
    never be reported as a mutant that went RED. `edits` is a list of
    (anchor, replacement) PAIRS: M3 needs TWO (the bad entry AND the neutered
    guard), and applying only one of them is how this arm first went wrong."""
    out = src
    for i, (anchor, replacement) in enumerate(edits, 1):
        n = out.count(anchor)
        if n != 1:
            check('neg-arm %s: anchor #%d appears exactly once' % (name, i), False,
                  'found %d time(s) in the live shell -- the mutant would be INERT '
                  'or would mutate the wrong thing' % n)
            return None
        out = out.replace(anchor, replacement, 1)
    tmp = tempfile.mkdtemp(prefix='sotto-handler-map-')
    _TMP.append(tmp)
    path = os.path.join(tmp, 'mutant_%s.py' % name)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    return load(path, 'sotto_shell_map_%s' % name)


def arm_failures(runner, *a):
    """Run an arm on a MUTANT: its checks are the evidence, not the verdict."""
    before = len(RESULTS)
    runner(*a)
    UNCOUNTED.update(range(before, len(RESULTS)))
    return [r for r in RESULTS[before:] if not r[1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    src = open(SHELL, encoding='utf-8').read()
    sw = load(SHELL, 'sotto_shell_map_live')
    print('live shell %s  (%d B)' % (SHELL, os.path.getsize(SHELL)))
    print('-- control: the shipped handler table --')
    run_control(sw, src)

    print('-- isolation: ONE bad entry in a COPY must cost only its own kind --')
    iso = mutant(src, [(ISOLATION_ANCHOR, ISOLATION_TEXT)], 'isolation')
    if iso is not None:
        iso_red = arm_failures(run_isolation, iso, '  isolation: ')
        check('isolation: the bad entry costs ONLY its own kind (this arm must '
              'PASS on the live shell)', not iso_red,
              'failures=%s' % [r[0].strip()[:70] for r in iso_red])

    if args.neg_arm:
        print('-- neg-arm M1: an ATTRIBUTE ACCESS in the table (defect #1 shape) --')
        m1 = mutant(src, [(M1_ANCHOR, M1_TEXT)], 'm1')
        if m1 is not None:
            red = arm_failures(build_arm, m1, '  mutant M1: ')
            check('neg-arm M1: the whole table fails to build and the net says '
                  'so (RED on the unresolvable check)',
                  any('unresolvable' in r[0] for r in red),
                  'red=%s' % [r[0].strip()[:70] for r in red])

        print('-- neg-arm M3: the isolation entry, per-entry guard NEUTERED --')
        m3 = mutant(src, [(ISOLATION_ANCHOR, ISOLATION_TEXT),
                    (GUARD_ANCHOR, GUARD_TEXT)], 'm3')
        if m3 is not None:
            red = arm_failures(run_isolation, m3, '  mutant M3: ')
            check('neg-arm M3: the good kind DIES with the guard removed (RED on '
                  'the isolation check)',
                  any('GOOD kind still dispatches' in r[0] for r in red),
                  'red=%s' % [r[0].strip()[:70] for r in red])

    for tmp in _TMP:
        shutil.rmtree(tmp, ignore_errors=True)

    counted_failed = [r for i, r in enumerate(RESULTS)
                      if not r[1] and i not in UNCOUNTED]
    total = len([r for i, r in enumerate(RESULTS) if i not in UNCOUNTED])
    print('')
    print('VERDICT: %s -- %d check(s), %d fail'
          % ('PASS' if not counted_failed else 'FAIL', total, len(counted_failed)))
    for r in counted_failed:
        print('   FAILED: ' + r[0] + '  -- ' + r[2])
    return 0 if not counted_failed else 1


if __name__ == '__main__':
    sys.exit(main())
