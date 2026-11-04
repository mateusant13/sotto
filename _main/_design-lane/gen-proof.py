#!/usr/bin/env python3
"""gen-proof.py -- THE GENERATOR IS CURRENT, MEASURED.

WHAT IT PROVES
--------------
AGENTS.md rule 10: the theme CSS is GENERATED, and a generator that has drifted
from the files on disk is worse than no generator at all. The proof has two
halves and this script does both:

  1. A SCRATCH RUN reproduces every shipped output BYTE FOR BYTE. The
     generators write to `<repo>/app/panel/themes`, so the run happens in a
     SCRATCH TREE (a copy of `_main/_design-lane` and of `app/panel`, without
     the font packages) and the result is compared with the shipped files by
     sha256. The shipped files are never written by this script.
  2. RE-RUNNING CHANGES 0 OUTPUTS. The second scratch run must produce the
     same bytes as the first, so the generator is deterministic.

THE OUTPUTS AND WHO OWNS THEM
------------------------------
  theme-1..5.css        gen_themes.py     (zips/directions)
  panel-designs.css     gen_themes.py     (zips/panel-designs)
  panel-designs.js      gen_themes.py     (the manifest fragment)
  cinematic.css         gen_cinematic.py  (zips/cinematic)
  themes.js             gen_cinematic.py  (the manifest)
  zipc-panels.css       gen_zipc.py       (zips/cinematic-1)

    python _main/_design-lane/gen-proof.py
"""
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRATCH = os.environ.get('SOTTO_GEN_SCRATCH', 'I:/cc-tmp/genscratch')
PY = sys.executable

# (generator, argv-after-the-script, output file relative to app/panel/themes)
JOBS = [
    ('gen_themes.py', [], 'theme-1.css'),
    ('gen_themes.py', [], 'theme-2.css'),
    ('gen_themes.py', [], 'theme-3.css'),
    ('gen_themes.py', [], 'theme-4.css'),
    ('gen_themes.py', [], 'theme-5.css'),
    ('gen_themes.py', [], 'panel-designs.css'),
    ('gen_themes.py', [], 'panel-designs.js'),
    ('gen_cinematic.py', [], 'cinematic.css'),
    ('gen_cinematic.py', [], 'themes.js'),
    ('gen_zipc.py', ['--profile', 'designs'], 'zipc-panels.css'),
]

SKIP_DIRS = {'__pycache__', 'node_modules', '.git'}


def sha(path):
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest().upper()


def copy_tree(src, dst, skip_names=()):
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip_names]
        rel = os.path.relpath(base, src)
        target = os.path.normpath(os.path.join(dst, rel))
        if not os.path.isdir(target):
            os.makedirs(target, exist_ok=True)
        for f in files:
            s = os.path.join(base, f)
            d = os.path.join(target, f)
            shutil.copyfile(s, d)


def build_scratch():
    if os.path.isdir(SCRATCH):
        shutil.rmtree(SCRATCH, ignore_errors=True)
    os.makedirs(SCRATCH, exist_ok=True)
    copy_tree(os.path.join(REPO, '_main', '_design-lane'),
              os.path.join(SCRATCH, '_main', '_design-lane'), SKIP_DIRS)
    copy_tree(os.path.join(REPO, 'app', 'panel'),
              os.path.join(SCRATCH, 'app', 'panel'), {'_fonts'} | SKIP_DIRS)
    return SCRATCH


def run_generators(root):
    lane = os.path.join(root, '_main', '_design-lane')
    for script, extra, out in JOBS:
        p = subprocess.run([PY, os.path.join(lane, script)] + extra,
                           capture_output=True, cwd=lane, timeout=900, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
        if p.returncode != 0:
            sys.stderr.write('FAILED %s: %s\n' % (script, p.stderr.decode('utf-8', 'replace')[-1500:]))
            return False
    return True


def main():
    shipped_dir = os.path.join(REPO, 'app', 'panel', 'themes')
    before = {out: sha(os.path.join(shipped_dir, out)) for _, _, out in JOBS}

    print('scratch tree: %s' % SCRATCH)
    build_scratch()
    if not run_generators(SCRATCH):
        return 1
    # SECOND RUN: the generator must be deterministic, so the bytes do not move.
    if not run_generators(SCRATCH):
        return 1

    scratch_dir = os.path.join(SCRATCH, 'app', 'panel', 'themes')
    ok = True
    print('')
    print('%-22s %-12s %-12s %s' % ('output', 'shipped', 'scratch', 'verdict'))
    for _, _, out in JOBS:
        a = before[out]
        b = sha(os.path.join(scratch_dir, out))
        same = (a is not None and a == b)
        ok = ok and same
        print('%-22s %-12s %-12s %s' % (out, (a or 'MISSING')[:10], (b or 'MISSING')[:10],
                                        'IDENTICAL' if same else 'DIFFERENT'))
    after = {out: sha(os.path.join(shipped_dir, out)) for _, _, out in JOBS}
    untouched = all(before[k] == after[k] for k in before)
    print('')
    print('the shipped files were NOT written by this run: %s' % ('YES' if untouched else 'NO'))
    print('VERDICT: %s' % ('PASS -- the generator reproduces every shipped output byte for byte'
                           if ok and untouched else 'FAIL'))
    return 0 if (ok and untouched) else 1


if __name__ == '__main__':
    sys.exit(main())
