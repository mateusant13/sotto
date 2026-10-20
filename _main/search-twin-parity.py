#!/usr/bin/env python
"""search-twin-parity.py -- GATE: the two search implementations must AGREE.

There are two implementations of one contract:

  LIVE   app/webview/sotto_webview.py :: history_search / search_match_rank  (Python)
  TWIN   app/panel/history-store.js   :: search / matchRank                  (JavaScript)

The JS one is not on the shipped page -- measured 2026-10-11, `panel.html` loads
eleven scripts and this is not one of them; only oracles read it. It is still fixed,
because an oracle asserting on the live search and an oracle asserting on the twin
would disagree, and whichever ran second would look broken.

THIS GATE IS WHAT KEEPS THAT HONEST. It extracts both implementations -- the Python
by `ast`, the JavaScript by locating its top-level declarations -- runs both over the
same corpus of real history lines and the same queries, and compares the RANK of
every (line, query) pair. A disagreement is not a style complaint: it means one of the
two is answering a different question than the other, and the owner only ever sees
one of them.

Soundex and Levenshtein are language-specific implementations of the same idea and
they WILL drift at the edges unless both are pinned to the same table and the same
budget -- which is what this compares, rather than comparing their source text.

THE CORPUS IS LIVE DATA, AND THIS FILE SAYS SO OUT LOUD. The corpus is the REAL
history of this machine (`history/`, under the product root -- never a worktree),
which the owner transcribes into WHILE the battery runs. It is DADO VIVO: it grows,
and its content changes between two runs of this oracle. It is therefore NOT one of
the battery's `deps` -- deps are FILES, and a directory that grows is not a file, so
a cache fingerprint over it would lie about what was judged. Every run prints the
corpus it judged: how many lines, how many bytes, and the sha256 of exactly those
bytes, so a reader of a cached log can say WHICH corpus produced that verdict.

NEGATIVE ARM (executed, not decorative)
    TWO mutants of the twin (`app/panel/history-store.js`), each a TEXTUAL patch of
    ONE UNIQUE ANCHOR in that file. A mutant whose anchor is missing or ambiguous is
    DECORATIVE -- it proves nothing -- so the oracle refuses to count it and says so.
    A mutant that loads but changes nothing is reported as SURVIVED. `--neg-arm` may
    only say `NEG-ARM PASS` when EVERY declared mutant was applied AND seen.

    BOTH mutants are needed and they test different things. Moving one soundex group
    provably changes the KEYS (`cole` goes C400 -> C100) yet provably changes NO RANK
    on this corpus, because `C100 != B100` exactly as `C400 != B400`: the comparison
    the rank makes is equality, and a mutation that changes both sides' keys equally
    is invisible to it. The budget mutant is what proves the gate can see a rank
    change at all. Asserting only on the soundex mutant would leave the gate
    untested while reporting PASS.

Usage:
    python _main/search-twin-parity.py            # the parity comparisons, rc=0 on PASS
    python _main/search-twin-parity.py --neg-arm  # the mutants only, rc=1 BY DESIGN
"""
import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, '..', 'app', 'webview', 'sotto_webview.py')
JS = os.path.join(HERE, '..', 'app', 'panel', 'history-store.js')
NODE = 'node'
NEG = '--neg-arm' in sys.argv

EXIT_PASS = 0
EXIT_FAIL = 1

PY_FUNCS = ('search_fold', 'search_soundex', 'search_edits',
            'bounded_levenshtein', 'search_match_rank')
PY_CONSTS = ('SEARCH_FUZZ_RATIO', 'FUZZY_MIN_WORD', 'SEARCH_MAX_EDITS',
             'SEARCH_SOUNDEX', 'SEARCH_LAYER_CAPS', 'SEARCH_LAYER_MIN')
JS_FUNCS = ('fold', 'soundex', 'editBudget', 'boundedLevenshtein', 'matchRank')

QUERIES = ['maca', 'mais', 'massa', 'casa', 'casso', 'preco', 'precos', 'precoo',
           'legenda', 'audio', 'historico', 'painel', 'gato', 'cao', 'mercado',
           'merdado', 'bola', 'cole', 'viagem', 'biagem', 'a', 'o preco do acucar',
           'sem audio', 'nao ha nada', 'so o akali', 'falés', 'fales', 'ZZZQQQ']

#: THE MUTANTS: `(label, old, new)`. `old` is a TEXTUAL anchor that must occur
#: EXACTLY ONCE in the judged file (`app/panel/history-store.js`); `new` replaces
#: it. An anchor that is missing or ambiguous makes the mutant DECORATIVE.
MUTANTS = (
    ('A: MAX_EDITS 2 -> 0 in the twin (deletes the fuzzy layer)',
     'const MAX_EDITS = 2;',
     'const MAX_EDITS = 0;'),
    ("B: soundex group 4 -> 1 for l (changes the KEYS)",
     "'l'.split('').forEach((c) => { map[c] = '4'; });",
     "'l'.split('').forEach((c) => { map[c] = '1'; });"),
)


def extract_python():
    with open(PY, encoding='utf-8') as handle:
        tree = ast.parse(handle.read())
    out, found = [], set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in PY_FUNCS:
            out.append(ast.unparse(node))
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in PY_CONSTS:
                    out.append('%s = %s' % (t.id, ast.unparse(node.value)))
                    found.add(t.id)
    missing = set(PY_FUNCS) | set(PY_CONSTS)
    missing -= found
    if missing:
        raise SystemExit('python side is missing %s' % sorted(missing))
    ns = {'math': math, 'unicodedata': unicodedata, 're': re}
    exec(compile('\n'.join(out), '<py>', 'exec'), ns)
    return ns


def read_js():
    with open(JS, encoding='utf-8') as handle:
        return handle.read()


def extract_js(src):
    """Pull the twin's functions and its SOUNDEX table out of history-store.js.

    The table is an IIFE; grab it verbatim so both sides read the same grouping.
    """
    out = []
    table = re.search(r'const SOUNDEX = \(\(\) => \{[\s\S]*?\}\)\(\);', src)
    if not table:
        raise SystemExit('SOUNDEX table not found in history-store.js')
    out.append(table.group(0))
    for name in JS_FUNCS:
        m = re.search(r'function %s\([\s\S]*?\n\}' % name, src)
        if not m:
            raise SystemExit('%s not found in history-store.js' % name)
        out.append(m.group(0))
    for const in ('FUZZ_RATIO', 'FUZZY_MIN_WORD', 'MAX_EDITS'):
        m = re.search(r'const %s = [^;]+;' % const, src)
        if not m:
            raise SystemExit('%s not found in history-store.js' % const)
        out.append(m.group(0))
    return '\n'.join(out)


def patch_or_report(label, src, old, new):
    """Patch ONE unique anchor. Returns the patched source, or None (and says why).

    An anchor that does not exist, or that exists more than once, makes the mutant
    DECORATIVE: it proves nothing about the gate. A patch that changes nothing is
    decorative too, and is reported as such rather than counted.
    """
    hits = src.count(old)
    if hits != 1:
        print('  RED   mutant %-46s ANCHOR %s -- the oracle is stale'
              % (label, 'MISSING' if hits == 0 else 'AMBIGUOUS (%d hits)' % hits))
        return None
    patched = src.replace(old, new, 1)
    if patched == src:
        print('  RED   mutant %-46s DECORATIVO: the patch changed nothing' % label)
        return None
    return patched


JS_HARNESS = r'''
const fs = require('fs');
%s
const corpus = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
for (const [key, q] of Object.entries(corpus.queries)) {
  const folded = fold(q).trim();
  const words = folded ? folded.split(/\s+/) : [];
  out[key] = corpus.lines.map((line) => matchRank(line, folded, words));
}
process.stdout.write(JSON.stringify(out));
'''


def run_js(js_src, lines, queries):
    with tempfile.TemporaryDirectory() as tmp:
        js_path = os.path.join(tmp, 'twin.js')
        json_path = os.path.join(tmp, 'corpus.json')
        with open(js_path, 'w', encoding='utf-8') as handle:
            handle.write(JS_HARNESS % js_src)
        with open(json_path, 'w', encoding='utf-8') as handle:
            handle.write(json.dumps({'lines': lines, 'queries': queries}))
        proc = subprocess.run([NODE, js_path, json_path], capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit('node failed: %s' % proc.stderr.strip()[:400])
        return json.loads(proc.stdout)


def real_history():
    root = os.path.join(HERE, '..', 'history')
    out = []
    if not os.path.isdir(root):
        return out
    for day in sorted(os.listdir(root)):
        dd = os.path.join(root, day)
        if not os.path.isdir(dd):
            continue
        for hour in sorted(os.listdir(dd)):
            p = os.path.join(dd, hour)
            if not os.path.isfile(p):
                continue
            with open(p, encoding='utf-8', errors='replace') as handle:
                for line in handle:
                    m = re.match(r'^-\s+\[\d{2}:\d{2}:\d{2}\]\s+(.*)$', line)
                    if m:
                        out.append(re.sub(r'\s*<!--.*?-->\s*$', '', m.group(1)).strip())
    return out


def python_ranks(ns, lines, queries):
    out = {}
    fold = ns['search_fold']
    rank = ns['search_match_rank']
    for key, q in queries.items():
        folded = fold(q).strip()
        words = folded.split() if folded else []
        out[key] = [rank(line, folded, words) for line in lines]
    return out


def corpus_digest(lines):
    """(lines, bytes, sha256) of EXACTLY the corpus judged -- printed every run."""
    blob = '\n'.join(lines).encode('utf-8')
    return len(lines), len(blob), hashlib.sha256(blob).hexdigest()


FAILURES = []


def check(name, ok, detail=''):
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name, (' -- ' + detail) if detail else ''))
    if not ok:
        FAILURES.append(name)


def keys_of(src):
    """The soundex keys of four probe words, read out of the TWIN itself."""
    probe = src + "\nprocess.stdout.write(JSON.stringify(['cole','bola','legenda','fala'].map(soundex)));"
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'k.js')
        with open(p, 'w', encoding='utf-8') as h:
            h.write(probe)
        r = subprocess.run([NODE, p], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit('probe failed: ' + r.stderr[:300])
        return r.stdout


def run_mutants(js_src, lines, queries, py_r):
    """The negative arm: two mutants, two different things to see. (caught, weak)"""
    caught = 0
    weak = 0

    label_a, old_a, new_a = MUTANTS[0]
    patched_a = patch_or_report(label_a, js_src, old_a, new_a)
    if patched_a is None:
        weak += 1
    else:
        try:
            mut = run_js(extract_js(patched_a), lines, queries)
        except Exception as exc:                                # noqa: BLE001
            print('  RED   mutant %-46s DECORATIVO: nao carregou (%s) -- '
                  'NAO foi testado' % (label_a, type(exc).__name__))
            weak += 1
        else:
            mut_mismatch = sum(1 for key in queries
                               for a, b in zip(py_r[key], mut[key]) if a != b)
            if mut_mismatch > 0:
                print('  GREEN mutant %-46s the mutation WAS APPLIED and the gate SAW it: '
                      '%d (line, query) pair(s) disagree once the twin has no edit budget'
                      % (label_a, mut_mismatch))
                caught += 1
            else:
                print('  RED   mutant %-46s SURVIVED -- the gate is blind here' % label_a)

    label_b, old_b, new_b = MUTANTS[1]
    patched_b = patch_or_report(label_b, js_src, old_b, new_b)
    if patched_b is None:
        weak += 1
    else:
        try:
            mut_src_b = extract_js(patched_b)
            before, after = keys_of(extract_js(js_src)), keys_of(mut_src_b)
        except Exception as exc:                                # noqa: BLE001
            print('  RED   mutant %-46s DECORATIVO: nao carregou (%s) -- '
                  'NAO foi testado' % (label_b, type(exc).__name__))
            weak += 1
        else:
            if before != after:
                print('  GREEN mutant %-46s the mutation WAS APPLIED and the gate SAW it: '
                      'the KEYS moved -- plain=%s  mutant=%s' % (label_b, before, after))
                caught += 1
            else:
                print('  RED   mutant %-46s SURVIVED -- the gate is blind here' % label_b)
            mut_b = run_js(mut_src_b, lines, queries)
            mb = sum(1 for key in queries for a, b in zip(py_r[key], mut_b[key]) if a != b)
            print('  [note] mutant B changes %d ranks on this corpus -- expected 0:' % mb)
            print('         both sides of every comparison move together, so a rank-blind')
            print('         gate and a correct one look identical here. That is why A exists.')
    return caught, weak


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:                                           # noqa: BLE001
        pass

    real = real_history()
    # Cap the corpus so the gate stays fast; the FIRST lines are the newest, and the
    # queries above are the ones the owner actually types.
    # SYNTHETIC PAIRS, appended to the real corpus. Not filler: the negative arm needs
    # lines it KNOWS are sensitive to the predicate, and the real two-day store happens
    # to contain none of them -- with the corpus alone, moving one soundex group changed
    # 0 of 11 200 pairs and the arm reported "mutant undetected", which reads exactly
    # like a healthy gate. These four are the pairs whose classification depends on the
    # table itself: same key for different sounds, different key for one edit.
    SYNTHETIC = [
        'fui no merdado hoje',
        'ele usou a cole preta',
        'ele comeu mais fruta',
        'os preços subiram',
        'o preco do acucar e cinco reais',
        'ele está falés demais',
    ]
    lines = real[:400] + SYNTHETIC
    nlines, nbytes, digest = corpus_digest(lines)
    js_src = read_js()
    js_sha = hashlib.sha256(js_src.encode('utf-8')).hexdigest()

    print('search-twin-parity -- the live search and its JS twin must agree\n')
    print('  corpus    : %d real history line(s) read from history/; %d kept + %d '
          'synthetic = %d judged (%d B, sha256 %s)'
          % (len(real), min(len(real), 400), len(SYNTHETIC), nlines, nbytes, digest))
    print('  twin      : %s (%d B, sha256 %s)'
          % (os.path.basename(JS), len(js_src.encode('utf-8')), js_sha))
    print('  note      : LIVE DATA, not source -- the owner transcribes into history/')
    print('              while the battery runs, so the numbers above MOVE between runs.')
    print('              The digest says WHICH corpus this verdict was taken over.\n')

    queries = {str(i): q for i, q in enumerate(QUERIES)}
    py = extract_python()
    py_r = python_ranks(py, lines, queries)

    if NEG:
        print('NEGATIVE ARM -- two mutants, because they test different things\n')
        caught, weak = run_mutants(js_src, lines, queries, py_r)
        total = len(MUTANTS)
        ok = caught == total and weak == 0
        print()
        print('VERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por design: the negative arm has '
              'to fail)' % ('PASS' if ok else 'FAIL', caught, total))
        return EXIT_FAIL if ok else EXIT_PASS

    print('  queries   : %d' % len(queries))
    js_r = run_js(extract_js(js_src), lines, queries)

    pairs = mismatches = 0
    examples = []
    for key in queries:
        for idx, (a, b) in enumerate(zip(py_r[key], js_r[key])):
            pairs += 1
            if a != b:
                mismatches += 1
                if len(examples) < 5:
                    examples.append('%r vs %r on %r -> py=%d js=%d'
                                    % (queries[key], lines[idx][:44], lines[idx][:60], a, b))

    check(f'all {pairs} (line, query) pairs agree', mismatches == 0,
          '%d mismatch(es)' % mismatches)
    for e in examples:
        print('        %s' % e)
    print()

    print('VERDICT: %s' % ('PASS' if not FAILURES else 'FAIL -- ' + json.dumps(FAILURES)))
    return EXIT_PASS if not FAILURES else EXIT_FAIL


if __name__ == '__main__':
    sys.exit(main())
