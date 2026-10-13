"""Run gen_cinematic.py with its OUTPUTS redirected, and compare with the shipped file.

This is the regra 10 check: a generated file must be reproducible. Redirecting ROOT
alone is not enough -- BACKDROPS lives under ROOT, and fetch_backdrop() treats an
already-packaged photo as INPUT, so an empty directory makes the run DOWNLOAD and the
bytes move. So the backdrops are seeded first.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

LANE = r'H:/sotto/_main/_design-lane'
GEN = os.path.join(LANE, 'gen_cinematic.py')
SHIPPED = r'H:/sotto/app/panel/themes/cinematic.css'
SHIPPED_JS = r'H:/sotto/app/panel/themes/themes.js'
TMP = r'I:/cc-tmp/gencheck'


def sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


ap = argparse.ArgumentParser()
ap.add_argument('--neg-arm', action='store_true')
ARGS = ap.parse_args()

if os.path.exists(TMP):
    shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(os.path.join(TMP, 'app', 'panel', 'themes'), exist_ok=True)

# seed the backdrops so the run cannot download
src_bd = r'H:/sotto/app/panel/themes/backdrops'
dst_bd = os.path.join(TMP, 'app', 'panel', 'themes', 'backdrops')
if os.path.isdir(src_bd):
    shutil.copytree(src_bd, dst_bd)
    print('seeded backdrops: %d file(s)' % len(os.listdir(dst_bd)))
# AND themes.js: the generator READS the manifest it replaces, so a fresh run needs it
src_js = r'H:/sotto/app/panel/themes/themes.js'
dst_js = os.path.join(TMP, 'app', 'panel', 'themes', 'themes.js')
if os.path.exists(src_js):
    shutil.copyfile(src_js, dst_js)
    print('seeded themes.js')
else:
    print('WARNING: no backdrops to seed')

with open(GEN, encoding='utf-8') as fh:
    src = fh.read()

# redirect the OUTPUT root, keep HERE pointing at the real lane so SOURCE resolves
old_root = re.search(r'^ROOT = .*$', src, re.M)
old_here = re.search(r'^HERE = .*$', src, re.M)
if not old_root or not old_here:
    print('SETUP ERROR: could not find ROOT/HERE -- refusing')
    sys.exit(2)
# THE NEG-ARM MUTATES THE GENERATOR, so the fresh run CANNOT reproduce the shipped
# bytes. Without it this oracle is a green check that has never been shown able to
# fail -- and an arm that cannot say NO is not evidence.
if ARGS.neg_arm:
    src = src.replace("'150ms'", "'151ms'", 1)
    print('NEG-ARM: one generator constant mutated (150ms -> 151ms)')

src2 = src.replace(old_root.group(0), 'ROOT = ' + repr(TMP), 1)
src2 = src2.replace(old_here.group(0), 'HERE = ' + repr(LANE), 1)
out = os.path.join(TMP, 'gen_redirected.py')
with open(out, 'w', encoding='utf-8') as fh:
    fh.write(src2)
print('redirected generator written')

r = subprocess.run([sys.executable, out], capture_output=True, text=True)
print('generator rc=%d' % r.returncode)
tail = (r.stdout or '').strip().splitlines()
for line in tail[-3:]:
    print('   ' + line[:100])
if r.returncode != 0:
    print((r.stderr or '')[-600:])

gen_css = os.path.join(TMP, 'app', 'panel', 'themes', 'cinematic.css')
gen_js = os.path.join(TMP, 'app', 'panel', 'themes', 'themes.js')
if not os.path.exists(gen_css):
    print('VERDICT: FAIL -- the generator produced no cinematic.css')
    sys.exit(1)

s_shipped = sha(SHIPPED)
s_fresh = sha(gen_css)
print('')
print('  cinematic.css shipped %8d B  %s' % (os.path.getsize(SHIPPED), s_shipped))
print('  cinematic.css fresh   %8d B  %s' % (os.path.getsize(gen_css), s_fresh))
ok = s_shipped == s_fresh
if os.path.exists(SHIPPED_JS) and os.path.exists(gen_js):
    print('  themes.js     shipped %8d B  %s' % (os.path.getsize(SHIPPED_JS), sha(SHIPPED_JS)))
    print('  themes.js     fresh   %8d B  %s' % (os.path.getsize(gen_js), sha(gen_js)))
    ok = ok and sha(SHIPPED_JS) == sha(gen_js)
print('')
verdict = 'PASS' if ok else 'FAIL'
print('VERDICT: %s -- the shipped file %s reproduced by a fresh run'
      % (verdict, 'IS' if ok else 'IS NOT'))
if ARGS.neg_arm:
    # In neg-arm mode FAIL is the REQUIRED outcome: the mutated generator must not
    # reproduce the shipped bytes. A PASS here would mean the mutation was INERT.
    wanted = not ok
    print('NEG-ARM VERDICT: %s -- the mutation %s the reproduction'
          % ('PASS' if wanted else 'FAIL',
             'BROKE' if wanted else 'did NOT break (INERT mutant)'))
    sys.exit(0 if wanted else 1)
sys.exit(0 if ok else 1)