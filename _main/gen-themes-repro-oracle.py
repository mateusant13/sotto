"""REGRA 10 for gen_themes.py: are theme-1..5.css and panel-designs.css reproducible?

This is the check the --size-meta fix needs BEFORE it touches anything: panel-designs.css
is generated, and a fix that edits the generator must be provably reproducible or the
next lane cannot tell its own change from drift.

Redirects ROOT (which drives OUT and the two _OUT paths) to a temp tree, keeps HERE
pointing at the real lane so any SOURCE resolves, and compares every output byte for
byte with the shipped file.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

LANE = r'H:/sotto/_main/_design-lane'
GEN = os.path.join(LANE, 'gen_themes.py')
SHIPPED_DIR = r'H:/sotto/app/panel/themes'
TMP = r'I:/cc-tmp/themegencheck'
# ONLY what gen_themes.py writes. themes.js belongs to gen_cinematic.py and fonts.css to
# build_fonts.py -- listing them here made the first run report two MISSING files that
# were never this generator's to produce, and a gate that fails for the wrong reason is
# as bad as one that cannot fail.
WATCH = ['theme-1.css', 'theme-2.css', 'theme-3.css', 'theme-4.css', 'theme-5.css',
         'panel-designs.css', 'panel-designs.js']


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


ap = argparse.ArgumentParser()
ap.add_argument('--neg-arm', action='store_true')
ARGS = ap.parse_args()

if os.path.exists(TMP):
    shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(os.path.join(TMP, 'app', 'panel', 'themes'), exist_ok=True)

with open(GEN, encoding='utf-8') as fh:
    src = fh.read()
old_root = re.search(r'^ROOT = .*$', src, re.M)
old_here = re.search(r'^HERE = .*$', src, re.M)
if not old_root or not old_here:
    print('SETUP ERROR: ROOT/HERE not found -- refusing')
    sys.exit(2)

if ARGS.neg_arm:
    # THE FIRST MUTANT WAS INERT: '13px' -> '13.5px' changed NOTHING in any output, so
    # the neg-arm reported FAIL with did NOT break (INERT mutant) -- which is the guard
    # working. An inert mutant is an ABSENT control, not a passed one. This mutates a
    # token NAME, which is certainly written into every theme it belongs to.
    before = src
    src = src.replace("--size-meta", "--size-metaX", 1)
    if src == before:
        print('SETUP ERROR: the mutation anchor is absent -- refusing') 
        sys.exit(2)
    print('NEG-ARM: one token name mutated (--size-meta -> --size-metaX)')

src2 = src.replace(old_root.group(0), 'ROOT = ' + repr(TMP), 1)
src2 = src2.replace(old_here.group(0), 'HERE = ' + repr(LANE), 1)
out = os.path.join(TMP, 'gen_redirected.py')
with open(out, 'w', encoding='utf-8') as fh:
    fh.write(src2)

r = subprocess.run([sys.executable, out], capture_output=True, text=True)
print('generator rc=%d' % r.returncode)
for line in (r.stdout or "").strip().splitlines()[-3:]:
    print('   ' + line[:100])
if r.returncode != 0:
    print((r.stderr or '')[-500:])

bad = []
seen = 0
for name in WATCH:
    ship = os.path.join(SHIPPED_DIR, name)
    fresh = os.path.join(TMP, 'app', 'panel', 'themes', name)
    if not os.path.exists(ship):
        continue
    seen += 1
    if not os.path.exists(fresh):
        print('  %-22s SHIPPED %8d B  %s   FRESH: MISSING' % (name, os.path.getsize(ship), sha(ship)))
        bad.append(name)
        continue
    same = sha(ship) == sha(fresh)
    print('  %-22s %s  shipped %8d B %s  fresh %8d B %s'
          % (name, 'OK  ' if same else 'DIFF', os.path.getsize(ship), sha(ship),
             os.path.getsize(fresh), sha(fresh)))
    if not same:
        bad.append(name)

print('')
print('compared %d file(s); differing: %d %s' % (seen, len(bad), bad or ''))
ok = not bad
if ARGS.neg_arm:
    print('NEG-ARM VERDICT: %s -- the mutation %s the reproduction'
          % ('PASS' if not ok else 'FAIL', 'BROKE' if not ok else 'did NOT break (INERT mutant)'))
    sys.exit(0 if not ok else 1)
print('VERDICT: %s -- the shipped files %s reproduced by a fresh run'
      % ('PASS' if ok else 'FAIL', 'ARE' if ok else 'ARE NOT'))
sys.exit(0 if ok else 1)