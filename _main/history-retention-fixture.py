"""A REAL 60-DAY-OLD TRANSCRIPT LINE, WRITTEN AND SEARCHED BY THE SHIPPED CODE.

The DOM gate (`_main/panel-history-clip-probe.mjs`) must prove that a line the
retention window admits reaches the real panel and is findable BY ITS CONTEXT.
Inventing that line in JavaScript would prove nothing about the store, so this
fixture produces it from the product's own functions:

  1. `SottoShell.history_append` (the shipped writer) appends each line with an
     explicit five-field context, so the `ctx1=` token on disk is the writer's;
  2. the hour file is MOVED into a day folder 60 days back -- and a second line
     200 days back -- which is exactly the on-disk shape `_history_files()`
     reads: the entry's DATE comes from the folder, its TIME from the line;
  3. `history_tail` and `history_search` answer from the shipped methods, over
     that root.

The two queries are exported in the JSON so the probe cannot drift from them.
Each line's TEXT deliberately does not contain either query, so a hit proves the
search reached the CONTEXT and not the words.

Output: one JSON object on stdout. No window, no app, no audio, no network.
Exit 0 = fixture built; 2 = a setup fact did not hold.
"""
import importlib.util
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WEBVIEW = os.path.join(os.path.dirname(HERE), 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
#: The shell imports its siblings by bare name (`hot_reload`, `history_context`),
#: so the directory has to be importable before the module executes.
sys.path.insert(0, WEBVIEW)
DAY = 86400.0
SIXTY = 60
TWO_HUNDRED = 200
#: A line INSIDE the window the shell keeps, one day short of its edge. Its age
#: is DERIVED from `HISTORY_RETENTION_H`, so the panel must agree with the
#: shell's own constant to within a day: a panel window that silently shrank
#: (the 48 h defect this gate was born from) or that lagged a widened store
#: turns the `feedNear` arm RED. Without this line the gate only says "the
#: window is somewhere between 60 and 200 days", which a 90-day regression
#: would satisfy.
NEAR_MARGIN_DAYS = 1.0
#: The queries the DOM gate types. The first matches the 60-day line by its
#: CONTEXT (its words do not contain it); the second matches ONLY the 200-day
#: line, which is how the gate sees that row if the panel lets it leak. A
#: short query such as `Code` is NOT usable here: the phonetic/fuzzy layers
#: return every line for it, and a hit that matches everything cannot tell
#: "found by context" from "found by accident".
QUERY_ONE = 'main.py'
QUERY_LEAK = 'other.py'
TEXT_60 = 'RETENCAO-60D linha antiga que o painel tem de mostrar'
TEXT_NEAR = 'RETENCAO-PERTO linha no limite da janela que o painel tem de mostrar'
TEXT_200 = 'RETENCAO-200D linha fora da janela que o painel nao pode mostrar'
TEXT_RECENT = 'RETENCAO-RECENTE linha de hoje'
CTX_60 = {'sourceApp': 'chrome.exe', 'audioSource': 'device:mic',
          'viewingApp': 'Code', 'viewingTitle': 'main.py',
          'viewingUrl': 'https://example.com/watch'}
CTX_NEAR = {'sourceApp': 'chrome.exe', 'audioSource': 'device:mic',
            'viewingApp': 'Code', 'viewingTitle': 'near.py',
            'viewingUrl': 'https://example.com/near'}
CTX_200 = {'sourceApp': 'chrome.exe', 'audioSource': 'device:mic',
           'viewingApp': 'Code', 'viewingTitle': 'other.py',
           'viewingUrl': 'https://example.com/other'}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def fail(message):
    print(json.dumps({'error': message}))
    sys.exit(2)


def main():
    shell = load_module(SHELL, 'sotto_webview_ret60')
    root = tempfile.mkdtemp(prefix='sotto-ret60-')
    shell.HISTORY_ROOT = root
    shell.log = lambda *_a, **_k: None
    shell.warn = shell.log
    shim = shell.SottoShell.__new__(shell.SottoShell)
    #: THE STORE'S PRUNE IS NOT WHAT THIS FIXTURE MEASURES. It is owned by
    #: `_main/history-context-oracle.py` (s19-s21), and letting it run here
    #: would delete the 200-day folder the panel must be proven to HIDE -- the
    #: folder would then survive only because `_history_prune` memoises its hour
    #: stamp and the run happened inside one hour (measured: it does survive,
    #: but by luck, not by design). Pinning the stamp makes the no-op explicit.
    shim._history_pruned_stamp = time.strftime('%Y-%m-%dT%H', time.localtime())
    #: The near-edge age is DERIVED from the shell's own window, so the panel's
    #: window is compared to the store's constant instead of to a second literal.
    near_days = max(2.0, float(shell.HISTORY_RETENTION_H) / 24.0 - NEAR_MARGIN_DAYS)

    def line(text, ctx, days_ago):
        entry = shim.history_append(text, {
            'route': 'final', 'routeSource': 'worker-stamped',
            'start': float(days_ago) + 0.5, 'context': ctx})
        if not entry or not entry.get('path'):
            fail('history_append returned no path for %r' % text)
        day = time.strftime('%Y-%m-%d', time.localtime(time.time() - days_ago * DAY))
        folder = os.path.join(root, day)
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, os.path.basename(entry['path']))
        os.replace(entry['path'], dest)
        with open(dest, 'r', encoding='utf-8', errors='replace') as handle:
            raw = handle.read()
        if 'ctx1=' not in raw:
            fail('the writer did not stamp ctx1= on %r' % text)
        return {'day': day, 'path': dest, 'raw': raw.strip(), 'entry': dict(entry, date=day)}

    old60 = line(TEXT_60, CTX_60, SIXTY)
    near = line(TEXT_NEAR, CTX_NEAR, near_days)
    old200 = line(TEXT_200, CTX_200, TWO_HUNDRED)
    #: An EXPLICIT context, so the writer never takes a fresh foreground reading
    #: on the owner's desktop (that is a live sample, and this fixture is not
    #: allowed to look at his screen). It also keeps `QUERY_LEAK` off this line.
    recent = line(TEXT_RECENT, {'viewingTitle': 'recent.py'}, 0.0)

    for item in (old60, near, old200):
        text = str(item['entry'].get('text') or '').lower()
        for q in (QUERY_ONE, QUERY_LEAK):
            if q.lower() in text:
                fail('the line text contains the context query %r' % q)

    tail = shim.history_tail(50).get('entries') or []
    one = shim.history_search(QUERY_ONE, 200).get('hits') or []
    leak = shim.history_search(QUERY_LEAK, 200).get('hits') or []

    if not any(e.get('date') == old60['day'] for e in tail):
        fail('history_tail lost the 60-day entry')
    if not any(e.get('date') == near['day'] for e in tail):
        fail('history_tail lost the near-edge entry (age %.1f d)' % near_days)
    if not any(e.get('date') == old200['day'] for e in tail):
        fail('history_tail lost the 200-day entry (the panel, not the store, '
             'is what must exclude it)')
    if not one or one[0].get('date') != old60['day']:
        fail('history_search(%r) did not find the 60-day line by its context' % QUERY_ONE)
    if len(leak) != 1 or leak[0].get('date') != old200['day']:
        fail('history_search(%r) did not return exactly the 200-day line: %r'
             % (QUERY_LEAK, [h.get('date') for h in leak]))

    # THE LINE MUST BE EXPORTABLE TOO, CONTEXT INCLUDED (owner, 2026-11-09:
    # months-later recall). Tail and search prove the store can READ it; this
    # proves the EXPORT carries it, which is the path that leaves the app.
    exported = shim.history_export('txt', 50)
    exported_text = exported.get('text') or ''
    if old60['day'] not in exported_text:
        fail('history_export lost the 60-day entry')
    if 'view=Code "main.py"' not in exported_text:
        fail('history_export lost the 60-day context')

    print(json.dumps({
        'root': root,
        'retention_h': int(shell.HISTORY_RETENTION_H),
        'queries': {'one': QUERY_ONE, 'both': QUERY_LEAK},
        'expected': {
            'day60': old60['day'], 'day200': old200['day'],
            'dayNear': near['day'], 'nearDays': round(near_days, 2),
            'dayRecent': recent['day'],
            # 60-day + near-edge + recent; the 200-day must be filtered. Three
            # rows, not two: the near-edge row is what constrains the panel's
            # window to the shell's own constant, not merely to [60, 200).
            'feedRows': 3,
            'searchOne': 1,         # only the 60-day line matches the context
            'searchLeak': len(leak),  # the store returns the 200-day line
        },
        'tail': tail,
        'searches': {QUERY_ONE: one, QUERY_LEAK: leak},
        'export': {
            'entries': exported.get('entries'),
            'has60': old60['day'] in exported_text,
            'hasContext': 'view=Code "main.py"' in exported_text,
        },
        'lines': {'sixty': old60['raw'], 'near': near['raw'],
                  'twoHundred': old200['raw']},
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
