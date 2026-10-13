"""Run gen_cinematic.py with its OUTPUTS redirected, and compare with the shipped file.

This is the regra 10 check: a generated file must be reproducible. Redirecting ROOT
alone is not enough -- BACKDROPS lives under ROOT, and fetch_backdrop() treats an
already-packaged photo as INPUT, so an empty directory makes the run DOWNLOAD and the
bytes move. So the backdrops are seeded first.
"""
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
print('VERDICT: %s -- the shipped file %s reproduced by a fresh run'
      % ('PASS' if ok else 'FAIL', 'IS' if ok else 'IS NOT'))
sys.exit(0 if ok else 1)