#!/usr/bin/env python
"""search-oracle.py -- GATE for the history search's three layers.

Owner, 2026-10-18, verbatim: *"quando eu procurar uma coisa no historico, eu quero
que ele ache"*. What shipped was one `in`:

    needle = str(query or '').strip().lower()
    if needle in entry['text'].lower():

Byte equality, against a pt-BR store, typed by a pt-BR owner: `maca` could not find
`maçã`, `cabeleireiro` could not find `cabeleireira`, `fales` could not find `falés`.
The owner's keyboard has a key the comparison does not.

The predicate is EXTRACTED FROM THE SHELL BY `ast` and executed here, not
re-implemented and not imported. Two reasons, both earned in this repo: an oracle
that copies the logic tests the copy, and importing `sotto_webview` to test five
pure functions would drag in pywebview, the hot-reload watcher and the whole
windowing layer. If the shell's predicate changes, THIS gate changes verdict with
it, because it is reading the same bytes.

The claims under test, each one a thing the owner would notice:

   1  LITERAL still wins. The exact phrase, with accents folded, is found, and it is
      ranked ABOVE the phonetic and fuzzy hits. A search that cannot find the exact
      thing is not smarter, it is broken.
   2  ACCENTS FOLD. `maca` finds `maçã`. This is the pt-BR bug itself.
   3  PHONETIC works. `casa` finds `casso`; `fales` finds `falés`.
   4  FUZZY is bounded and PER WORD. `preco` finds `preços` and `precoo`, but a
      90-character line does not become a match for anything: a distance budget
      that grew with the sentence would make the layer meaningless.
   5  THE LATER LAYERS CAN SAY NO. Every-word, not any-word. A three-word query
      where only one word is present must NOT match -- otherwise the feature is a
      slot machine that ranks its own noise.

THE CORPUS IS LIVE DATA, AND THIS FILE SAYS SO OUT LOUD. The last arm judges the
REAL history of this machine (`history/`, under the product root -- never a
worktree). That corpus is DADO VIVO: the owner transcribes into it while the
battery runs, so it grows and its content changes between two runs of this very
oracle. It is therefore NOT one of the battery's `deps` -- deps are FILES, and a
directory that grows is not a file, so a cache fingerprint over it would be a lie
about what was judged. Instead EVERY run prints the corpus it judged: how many
lines, how many bytes, and the sha256 of exactly those bytes. A reader of a
cached log can therefore say WHICH corpus produced that verdict. Nothing here is
remembered between runs.

NEGATIVE ARM (executed, not decorative)
    Seven mutants of the LIVE SEARCH (`app/webview/sotto_webview.py`), each a
    TEXTUAL patch of ONE UNIQUE ANCHOR in that file. A mutant whose anchor is
    missing or ambiguous is DECORATIVE -- it proves nothing -- so the oracle
    refuses to count it and says so. A mutant that loads but changes nothing is
    reported as SURVIVED (the gate is blind there). A mutant is CAUGHT only when
    the gate's own arms go RED on the broken copy, and `--neg-arm` may only say
    `NEG-ARM PASS` when EVERY declared mutant was applied AND seen.

    The mutant that breaks the phonetic test is deliberately NOT of the shape
    the shell's own comment at `sotto_webview.py:586-590` warns about: the test
    that is meant is "each query word's key is present among the entry's keys",
    and no mutant here rewrites it into "every query word sounds like every
    other one" -- that would be testing a shape the product never had.

Usage:
    python _main/search-oracle.py            # the arms, rc=0 on PASS
    python _main/search-oracle.py --neg-arm  # the mutants only, rc=1 BY DESIGN
"""
import ast
import hashlib
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(HERE, '..', 'app', 'webview', 'sotto_webview.py')
NEG = '--neg-arm' in sys.argv

FUNCS = ('search_fold', 'search_soundex', 'search_edits',
         'bounded_levenshtein', 'search_match_rank', 'search_layer_cap')
CONSTS = ('SEARCH_FUZZ_RATIO', 'FUZZY_MIN_WORD', 'SEARCH_MAX_EDITS',
          'SEARCH_LAYER_CAPS', 'SEARCH_LAYER_MIN')

EXIT_PASS = 0
EXIT_FAIL = 1

#: THE MUTANTS. `(label, old, new, expected_claim)` -- `old` is a TEXTUAL anchor
#: that must occur EXACTLY ONCE in the judged file (`app/webview/sotto_webview.py`),
#: `new` is the replacement, and `expected_claim` is the substring of the arm
#: name that the mutation is supposed to break. The expectation is a CROSS-CHECK,
#: not the pass condition: the pass condition is "at least one arm went RED".
MUTANTS = (
    ('a-dobra-de-acentos-e-removida',
     "stripped = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))",
     "stripped = ''.join(ch for ch in decomposed)",
     'accents folded'),
    ('o-grupo-do-c-sai-do-soundex-do-dois',
     "**{c: '2' for c in 'cgjkqsxz'},",
     "**{c: '2' for c in 'gjkqsxz'},\n    **{c: '3' for c in 'c'},",
     'a homophone pair is owned by the SOUND layer'),
    ('o-orcamento-de-edicoes-desce-para-zero',
     'SEARCH_MAX_EDITS = 2',
     'SEARCH_MAX_EDITS = 0',
     'edit budget is capped at 2'),
    ('o-minimo-de-palavras-fuzzy-sobe-para-9',
     'FUZZY_MIN_WORD = 4',
     'FUZZY_MIN_WORD = 9',
     "'mercado' in"),
    ('o-limite-por-camada-deixa-de-ser-uma-fracao',
     'SEARCH_LAYER_CAPS = (1.0, 0.25, 0.05)',
     'SEARCH_LAYER_CAPS = (1.0, 1.0, 1.0)',
     'phonetic gets a quarter'),
    ('o-piso-por-camada-desaparece',
     'SEARCH_LAYER_MIN = (1, 8, 4)',
     'SEARCH_LAYER_MIN = (1, 1, 1)',
     'a loose layer is never floored into uselessness'),
    ('a-guarda-de-todas-as-palavras-vira-qualquer-uma',
     'if query_keys and all(k and k in entry_keys for k in query_keys):',
     'if query_keys and any(k and k in entry_keys for k in query_keys):',
     'one word present out of three must NOT match'),
)


def load_source():
    with open(SHELL, 'r', encoding='utf-8') as handle:
        return handle.read()


def extract(src):
    """Pull the six functions and their constants out of the shell, by `ast`."""
    tree = ast.parse(src)
    found_funcs, found_consts = {}, {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCS:
            found_funcs[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in CONSTS:
                    found_consts[target.id] = node.value
    missing = [n for n in FUNCS if n not in found_funcs] + \
              [c for c in CONSTS if c not in found_consts]
    if missing:
        raise SystemExit(f'search-oracle: shell no longer defines {missing}')
    out = []
    for name in CONSTS:
        out.append(f'{name} = ' + ast.unparse(found_consts[name]))
    # The soundex table is a dict display built from comprehensions; keep it too.
    for node in tree.body:
        if (isinstance(node, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == 'SEARCH_SOUNDEX' for t in node.targets)):
            out.append('SEARCH_SOUNDEX = ' + ast.unparse(node.value))
    for name in FUNCS:
        out.append(ast.unparse(found_funcs[name]))
    return '\n'.join(out)


def build(src):
    ns = {'math': math, 'unicodedata': unicodedata, 're': re}
    exec(compile(extract(src), '<extracted>', 'exec'), ns)
    return ns


# ── the store this box actually has, so the oracle is not testing fiction ────────
def real_history_sample():
    root = os.path.join(HERE, '..', 'history')
    out = []
    for day in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        day_dir = os.path.join(root, day)
        if not os.path.isdir(day_dir):
            continue
        for hour in sorted(os.listdir(day_dir)):
            path = os.path.join(day_dir, hour)
            if not os.path.isfile(path):
                continue
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                for line in handle:
                    m = re.match(r'^-\s+\[\d{2}:\d{2}:\d{2}\]\s+(.*)$', line)
                    if m:
                        out.append(re.sub(r'\s*<!--.*?-->\s*$', '', m.group(1)).strip())
    return out


def corpus_digest(lines):
    """(lines, bytes, sha256) of EXACTLY the corpus judged -- printed every run.

    The corpus is live data, so this is the only way a reader of a cached log
    can tell WHICH corpus produced the verdict it is looking at.
    """
    blob = '\n'.join(lines).encode('utf-8')
    return len(lines), len(blob), hashlib.sha256(blob).hexdigest()


def run_arms(ns, store, verbose=True):
    """Every arm of this gate, as a list of `(name, ok, detail)`.

    The SAME function judges the live shell and every mutant: a mutant is caught
    only when the arms this gate really runs go RED on it.
    """
    results = []

    def check(name, ok, detail=''):
        results.append((name, bool(ok), detail))
        if verbose:
            print(f'  [{"PASS" if ok else "FAIL"}] {name}' + (f' -- {detail}' if detail else ''))
        return ok

    def rank(text, query):
        folded = ns['search_fold'](query).strip()
        words = folded.split()
        return ns['search_match_rank'](text, folded, words)

    def fold_of(text):
        return ns['search_fold'](text).strip()

    soundex = ns['search_soundex']

    def expected_layer(query, entry):
        # The key-vs-key comparison is the whole point: an earlier version compared the
        # query WORD against the entry's sound KEYS, which is a category error that
        # silently returned "not a homophone" for real homophones (`bianda`/`biandu` are
        # both B530 -- Soundex ignores the trailing vowel) and then demanded a layer the
        # code never claimed.
        qw = fold_of(query)
        qkey = soundex(qw)
        ekeys = {soundex(w) for w in fold_of(entry).split() if w}
        if qw in fold_of(entry):
            return 0
        return 1 if qkey in ekeys else 2

    if verbose:
        print('ARM 1 -- LITERAL, and it outranks the rest')
    check('exact phrase found', rank('o preco do acucar e cinco reais', 'preco do acucar') == 0)
    check('accents folded: maca finds maçã', rank('comprei uma maçã no mercado', 'maca') == 0)
    check('literal beats phonetic on the same text',
          rank('casa', 'casa') == 0 and rank('casa', 'casso') >= 1)
    check('case-insensitive', rank('Preco Do Acucar', 'preco do acucar') == 0)
    check('empty query matches nothing', rank('qualquer frase', '') == -1)
    check('unrelated query rejected', rank('o gato dormiu no sofa', 'helicoptero') == -1)
    if verbose:
        print()

    if verbose:
        print('ARM 2 -- PHONETIC (layer 1)')
    check('casa ~ casso', rank('o casso estava frio', 'casa') == 1)
    check('fales ~ falés (accent AND sound)', rank('ele está falés demais', 'fales') in (0, 1))
    check('multi-word phonetic is all-words',
          rank('a casa grande e velha', 'casa velha') == 1)
    if verbose:
        print()

    if verbose:
        print('ARM 3 -- FUZZY is bounded and PER WORD')
    # THE RANK IS DERIVED, NOT PREDICTED. Twice in this file's history a hand-computed
    # Soundex key was wrong and the test asserted a layer the code never claims:
    # `preco`/`preço`/`precoo` are ALL P620, so the sound layer owns every one of them,
    # and a test demanding rank 2 was demanding the fuzzy layer steal another layer's
    # work. So the oracle asks the extracted `search_soundex` which layer SHOULD own a
    # pair, and asserts that. What is fixed is the invariant -- literal beats phonetic
    # beats fuzzy, and a match is a match -- not a number guessed at a terminal.
    FUZZY_PAIRS = [
        # c<->d crosses no soundex group, so the two words sound ALIKE -- a homophone.
        ('mercado', 'fui no merdado hoje'),
        # b(1) <-> c(2) crosses a group, so `bola` and `cole` do NOT sound alike and only
        # the edit distance can connect them (2 substitutions, budget 2).
        ('bola', 'ele usou a cole preta'),
        # v(1) <-> b(1) is INSIDE one group, so these collide on sound.
        ('viagem', 'a biagem do anno'),
    ]
    for query, entry in FUZZY_PAIRS:
        want = expected_layer(query, entry)
        got = rank(entry, query)
        check(f'{query!r} in {entry!r}: layer {want} '
              f'(sound keys {soundex(query)} vs entry)',
              got == want, f'got {got}')

    check('a homophone pair is owned by the SOUND layer, not the fuzzy one',
          rank('ele comeu mais fruta', 'maca') == expected_layer('maca', 'ele comeu mais fruta') == 1,
          f"maca={soundex('maca')} mais={soundex('mais')} -- same key, and the query is "
          f"NOT a substring, so layer 0 cannot be what answered")
    check('a prefix is a LITERAL match, not a homophone match',
          rank('os preços subiram', 'preco') == 0,
          "'preco' is a substring of 'precos' -- substring beats sound")
    check('a short word is NOT fuzzed into everything',
          rank('um gato', 'cao') == -1)
    check('a whole sentence does not become a match for anything',
          rank('x' * 90, 'x' * 90) == 0 and rank('x' * 90, 'y' * 90) == -1)
    check('edit budget is capped at 2 even on a long word',
          ns['search_edits']('abcdefghij') == 2,
          f"ceil(0.34*10)=4, capped to {ns['SEARCH_MAX_EDITS']}")
    check('the fuzzy layer is REACHABLE at all (at least one pair lands on 2)',
          any(expected_layer(q, e) == 2 for q, e in FUZZY_PAIRS),
          'if this fails the fuzzy arm above is vacuous')
    if verbose:
        print()

    if verbose:
        print('ARM 4 -- THE LATER LAYERS CAN SAY NO (all-words, not any-words)')
    check('one word present out of three must NOT match',
          rank('o gato dormiu', 'o preco do acucar') == -1)
    check('but if every word IS present it matches',
          rank('o preco do acucar', 'o preco do acucar') == 0)
    if verbose:
        print()

    if verbose:
        print('ARM 5 -- PER-LAYER CAPS (measured, not tasteful)')
    check('literal gets the whole limit', ns['search_layer_cap'](0, 200) == 200)
    check('phonetic gets a quarter', ns['search_layer_cap'](1, 200) == 50)
    check('fuzzy gets a twentieth', ns['search_layer_cap'](2, 200) == 10)
    check('a loose layer is never floored into uselessness',
          ns['search_layer_cap'](1, 4) >= 8 and ns['search_layer_cap'](2, 1) >= 4)
    if verbose:
        print()

    if verbose:
        print('ARM 6 -- MEASURED ON THE REAL STORE')
    if store:
        # Every literal hit must still be found: the feature may ADD, never remove.
        sample = store[0]
        check('the newest stored line is still findable by its own words',
              rank(sample, ' '.join(sample.split()[:3])) in (0, 1, 2),
              f'"{sample[:48]}"')
        literal_hits = sum(1 for line in store if rank(line, 'a') == 0)
        if verbose:
            print(f'  [note] {literal_hits}/{len(store)} lines contain the letter "a" -- '
                  f'this is why layers 1-2 are all-words')
    elif verbose:
        print('  [skip] no history/ on this box; arms 1-4 still ran on synthetic text')
    if verbose:
        print()

    return results


def run_mutants(src, store):
    """Apply every declared mutant and report what the gate saw. (caught, weak)"""
    caught = 0
    weak = 0
    for label, old, new, expected in MUTANTS:
        hits = src.count(old)
        if hits != 1:
            print('  RED   mutant %-46s ANCHOR %s -- the oracle is stale'
                  % (label, 'MISSING' if hits == 0 else 'AMBIGUOUS (%d hits)' % hits))
            weak += 1
            continue
        mutated = src.replace(old, new, 1)
        if mutated == src:
            print('  RED   mutant %-46s DECORATIVO: the patch changed nothing' % label)
            weak += 1
            continue
        try:
            ns = build(mutated)
        except Exception as exc:                                # noqa: BLE001
            print('  RED   mutant %-46s DECORATIVO: nao carregou (%s) -- '
                  'NAO foi testado' % (label, type(exc).__name__))
            weak += 1
            continue
        try:
            results = run_arms(ns, store, verbose=False)
        except Exception as exc:                                # noqa: BLE001
            print('  RED   mutant %-46s a bateria rebentou (%s) -- '
                  'NAO foi testado' % (label, type(exc).__name__))
            weak += 1
            continue
        reds = [name for name, ok, _detail in results if not ok]
        if not reds:
            print('  RED   mutant %-46s SURVIVED -- the gate is blind here' % label)
            continue
        caught += 1
        ordered = list(reds)
        if expected in reds:
            ordered = [expected] + [r for r in reds if r != expected]
        note = ''
        if expected not in reds:
            note = ' (NOTE: the expected claim %r stayed GREEN -- something else broke)' % expected
        print('  GREEN mutant %-46s the mutation WAS APPLIED and the gate SAW it: %s%s'
              % (label, '; '.join(ordered[:3]), note))
    return caught, weak


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:                                           # noqa: BLE001
        pass

    src = load_source()
    store = real_history_sample()
    nlines, nbytes, digest = corpus_digest(store)
    src_bytes = len(src.encode('utf-8'))
    src_sha = hashlib.sha256(src.encode('utf-8')).hexdigest()

    if NEG:
        print('search-oracle -- NEGATIVE ARM: seven mutants of the live search\n')
        print('  shell     : %s (%d B, sha256 %s)'
              % (os.path.basename(SHELL), src_bytes, src_sha))
        print('  corpus    : %d real history line(s) from history/ (%d B, sha256 %s)'
              % (nlines, nbytes, digest))
        print('  note      : the corpus is LIVE DATA (the owner transcribes into it), so it')
        print('              is not one of the battery deps; the digest above says WHICH')
        print('              corpus this verdict was taken over.\n')
        caught, weak = run_mutants(src, store)
        total = len(MUTANTS)
        ok = caught == total and weak == 0
        print()
        print('VERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por design: the negative arm has '
              'to fail)' % ('PASS' if ok else 'FAIL', caught, total))
        return EXIT_FAIL if ok else EXIT_PASS

    print('search-oracle -- history search, three layers\n')
    print('  shell     : %s (%d B, sha256 %s)'
          % (os.path.basename(SHELL), src_bytes, src_sha))
    print('  corpus    : %d real history line(s) from history/ (%d B, sha256 %s)'
          % (nlines, nbytes, digest))
    print('  note      : LIVE DATA, not source -- the owner transcribes into it, so the')
    print('              numbers above MOVE between runs. The digest says which corpus.')
    print()

    results = run_arms(build(src), store, verbose=True)
    failures = [name for name, ok, _detail in results if not ok]
    print('VERDICT: %s' % ('PASS' if not failures else 'FAIL -- ' + json.dumps(failures)))
    return EXIT_PASS if not failures else EXIT_FAIL


if __name__ == '__main__':
    sys.exit(main())
