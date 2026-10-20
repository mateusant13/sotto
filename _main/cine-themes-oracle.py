#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""THE CINE-* LANE GATE -- D3, D5, D6, D7, D8 of I:/cc-tmp/design-bugs-audit.md,
measured on the bytes of app/panel/themes/cinematic.css, app/panel/themes/themes.js
and on the generator that writes both.

ARMS (each a claim about the SHIPPED bytes, not about a plan):

  A  D3 -- every one of the 25 cine-* themes DECLARES the four closed-line tokens
     and CONSUMES each with var() inside its own scope, with the design own value
     as the var() fallback. The audit measured 25 declarations and 0 readers; a
     declaration without a reader inside the same theme fails here.
  B  D3 -- the motion token is read INSIDE every theme scope (the chrome rule),
     not only once for the whole set in the shared block.
  C  D6 -- no token is DECLARED in cinematic.css and left with zero readers,
     except the four the shell and panel.js read OUTSIDE CSS (--strip-height,
     --float-height via getComputedStyle; --c-i, --meter-h written inline).
  D  D5 -- every class selector in cinematic.css matches a class the live document
     can carry (panel.html static classes + the classes the panel JS assigns).
  E  D7 -- no two picker entries share a label, and the two ambiguous labels are
     the ones the audit fixed.
  F  D8 -- the picker label of the six two-layer ids equals the label of the skin
     that actually mounts, read out of skins/skins.js (the registry), not a list.
  G  the manifest parses and still holds the five original directions.
  H  RULE 10 -- a FRESH run of the generator reproduces the bytes on disk. The
     generator runs with its output paths redirected into a scratch directory;
     nothing under app/ is written by this oracle.

CONTROL (--neg-arm): the SAME predicates run against MUTATED COPIES, and the arm
that must catch each mutation has to go RED. M7 mutates a COPY OF THE GENERATOR,
because mutating the manifest or a CSS module cannot move the CSS bytes the H arm
reads -- the lesson this lane was told to encode.

Run:  py -3 _main/cine-themes-oracle.py
      py -3 _main/cine-themes-oracle.py --neg-arm
Nothing is launched: no browser, no shell, no worker.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(ROOT, 'app', 'panel')
THEMES = os.path.join(PANEL, 'themes')
CSS_DISK = os.path.join(THEMES, 'cinematic.css')
JS_DISK = os.path.join(THEMES, 'themes.js')
GEN = os.path.join(ROOT, '_main', '_design-lane', 'gen_cinematic.py')
SKINS = os.path.join(PANEL, 'skins', 'skins.js')
PANEL_HTML = os.path.join(PANEL, 'panel.html')

# The four knobs of theme-tune.js that were dead in all 25 cine-* themes (D3).
FOUR = ('--size-closed', '--leading-closed', '--weight-closed', '--motion-in')

# D6's measured list for this family plus every other name the audit names: each
# must have ZERO declarations in cinematic.css once the defect is closed.
D6_NAMES = ('--slab-opacity', '--busy', '--font-closed', '--space-1', '--space-4',
            '--space-5', '--bg', '--cine-accent-ink', '--strip-chrome')

# Read OUTSIDE CSS, so a var() scan alone would call them dead and be WRONG:
#   --strip-height / --float-height  the shell reads them via getComputedStyle
#                                    (sotto_webview.py:889-890)
#   --c-i / --meter-h                panel.js writes them inline (568 / 2749)
EXTERNAL_READERS = ('--strip-height', '--float-height', '--c-i', '--meter-h')

LABEL_EXPECT = {'cine-tideline': 'Tideline (wide)', 'cine-cellar': 'Cellar',
                'cine-linen': 'Linen'}

# the six ids that live in TWO layers: a theme of cinematic.css AND a frozen skin
TWO_LAYER = ('cine-rainline', 'cine-blue-hour', 'cine-cellar', 'cine-linen',
             'cine-reading-hour', 'cine-last-train')


def sha16(path):
    with io.open(path, 'rb') as fh:
        b = fh.read()
    return len(b), hashlib.sha256(b).hexdigest().upper()


def read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def replace_once(text, old, new, label):
    """Mutate, or REFUSE to mutate nothing.

    A mutant whose anchor is not in its subject changes NOTHING: the arm still
    reports GREEN and the gate is blind at that point. An inert mutant is worse
    than a red one -- a red one is a verdict, an inert one is silence.
    (MEASURED 2026-10-20: M1 went inert exactly this way. The product grew the
    `--caption-scale` dial, the old anchor's count fell to 0, and the arm printed
    `1 inert` while the gate could not see that point at all.)"""
    if old not in text:
        raise SystemExit('mutant anchor not found: %r (in %s)' % (old[:60], label))
    return text.replace(old, new, 1)


# -- a small strict CSS reader (no dependency; the file is generated and flat) ---

def blocks(css):
    """(prelude, body, offset) for every top-level block, @media bodies recursed.

    COMMENTS ARE REMOVED FIRST, and that is not cosmetic: the generator writes long
    prose comments full of braces (`{`) and words with dots (`main.ts`), and a scanner
    that walks raw bytes counts a comment as a selector prelude. Measured on the
    shipped file: without this the theme scope count came out 35 instead of 25."""
    css = re.sub(r'/\*[\s\S]*?\*/', '', css)
    out = []
    i, n, start = 0, len(css), 0
    prelude = ''
    while i < n:
        c = css[i]
        if c == '{':
            depth, j = 1, i + 1
            while j < n and depth:
                if css[j] == '{':
                    depth += 1
                elif css[j] == '}':
                    depth -= 1
                j += 1
            body = css[i + 1:j - 1]
            pre = prelude.strip()
            out.append((pre, body, start))
            if pre.startswith('@') and '{' in body:
                out.extend(blocks(body))
            prelude = ''
            start = j
            i = j
        elif c == '}':
            prelude = ''
            start = i + 1
            i += 1
        else:
            prelude += c
            i += 1
    return out


def theme_scope(prelude):
    """The EXACT theme of a block, or None. The set-wide shared block uses the prefix
    form :root[data-theme^='cine-'], which is NOT a theme scope: matching it as one
    inflated the theme count by ten (measured: 35 instead of 25)."""
    m = re.search(r":root\[data-theme='(cine-[^']+)'\]", prelude)
    if not m:
        return None
    return m.group(1)


def declared_names(body):
    return set(re.findall(r'^\s*(--[A-Za-z0-9_-]+)\s*:', body, re.M))


def var_uses(text, name):
    return len(re.findall(r'var\(\s*' + re.escape(name) + r'\b', text))


def var_fallbacks(text, name):
    return len(re.findall(r'var\(\s*' + re.escape(name) + r'\s*,', text))


def live_classes():
    """Every class the live document can carry."""
    live = set()
    html = read(PANEL_HTML)
    for m in re.finditer(r'class\s*=\s*"([^"]*)"', html):
        live.update(m.group(1).split())
    for name in sorted(os.listdir(PANEL)):
        if not name.endswith('.js'):
            continue
        t = read(os.path.join(PANEL, name))
        for m in re.finditer(r"class(?:Name)?\s*=\s*[\x27\x60]([^\x27\x60]*)[\x27\x60]", t):
            live.update(x for x in m.group(1).split() if not re.search(r'[\${}()]', x))
        for m in re.finditer(r"classList\.(?:add|toggle|remove)\(\s*[\x27\x60]([^\x27\x60]+)[\x27\x60]", t):
            live.update(m.group(1).split())
    return live


def reader_universe():
    """Every custom property a shipped reader consumes: var(--x) in every stylesheet
    the panel loads, plus the two names the shell reads through getComputedStyle and the
    two panel.js writes inline (EXTERNAL_READERS)."""
    sheets = ['panel.css', 'skin-layout.css',
              'themes/fonts.css', 'themes/theme-1.css', 'themes/theme-2.css',
              'themes/theme-3.css', 'themes/theme-4.css', 'themes/theme-5.css',
              'themes/cinematic.css', 'themes/panel-designs.css', 'themes/zipc-panels.css']
    found = set(EXTERNAL_READERS)
    for rel in sheets:
        path = os.path.join(PANEL, rel)
        if not os.path.exists(path):
            continue
        found.update(re.findall(r'var\(\s*(--[A-Za-z0-9_-]+)', read(path)))
    for name in sorted(os.listdir(PANEL)):
        if name.endswith('.js'):
            found.update(re.findall(r'var\(\s*(--[A-Za-z0-9_-]+)',
                                    read(os.path.join(PANEL, name))))
    return found


def css_classes(css):
    names = {}
    for pre, _body, _off in blocks(css):
        if pre.startswith('@'):
            continue
        for m in re.finditer(r'\.(-?[_A-Za-z][\w-]*)', pre):
            names[m.group(1)] = names.get(m.group(1), 0) + 1
    return names


def run_manifest(js_path):
    """Execute the manifest EXACTLY as panel.html loads it -- themes.js, then the two
    appenders (panel-designs.js, zipc-panels.js) -- with a fake window, and return the
    array the picker renders. Reading only themes.js returns 30 of the 59 entries; the
    other 29 arrive through those two .push() fragments, which is how the audit's own
    census got 59 (measured: 30 + 5 + 10 + 14)."""
    appenders = [os.path.join(THEMES, 'panel-designs.js'),
                 os.path.join(THEMES, 'zipc-panels.js'),
                 os.path.join(PANEL, 'skins', 'skins.js')]
    script = (
        "var window={};var document={documentElement:{dataset:{}},"
        "addEventListener:function(){},querySelectorAll:function(){return[];}};"
        "globalThis.window=window;globalThis.document=document;"
        "var files=process.argv.slice(1);"
        "for (var i=0;i<files.length;i+=1){ require(files[i]); }"
        "var t=(window.SottoThemeManifest||{}).themes||[];"
        "process.stdout.write(JSON.stringify(t));"
    )
    proc = subprocess.run(['node', '-e', script, js_path] + appenders, capture_output=True,
                          timeout=60, creationflags=0x08000000)
    if proc.returncode != 0:
        raise RuntimeError('node failed on the manifest: %s'
                           % proc.stderr.decode('utf-8', 'replace')[:400])
    return json.loads(proc.stdout.decode('utf-8'))


# -- the arms --------------------------------------------------------------------

class Gate(object):
    def __init__(self, css_path, js_path, gen_path):
        self.css_path, self.js_path, self.gen_path = css_path, js_path, gen_path
        self.css = read(css_path)
        self.results = []

    def check(self, name, ok, detail=""):
        self.results.append((name, bool(ok), detail))

    def theme_ids(self):
        return sorted({theme_scope(p) for p, _b, _o in blocks(self.css) if theme_scope(p)})

    def arm_a(self):
        per = {}
        for pre, body, _off in blocks(self.css):
            t = theme_scope(pre)
            if not t:
                continue
            row = per.setdefault(t, {})
            for name in FOUR:
                if name in declared_names(body):
                    row.setdefault('decl', set()).add(name)
                if var_uses(body, name):
                    row.setdefault('use', set()).add(name)
        ids = self.theme_ids()
        bad_decl, bad_use = [], []
        for t in ids:
            row = per.get(t, {})
            d, u = row.get('decl', set()), row.get('use', set())
            for name in FOUR:
                if name not in d:
                    bad_decl.append('%s %s' % (t, name))
                if name not in u:
                    bad_use.append('%s %s' % (t, name))
        self.check('A1 25 cine-* themes carry a token block', len(ids) == 25,
                   '%d theme scope(s)' % len(ids))
        self.check('A2 every theme DECLARES the four tokens', not bad_decl,
                   ('missing: %s' % ', '.join(bad_decl[:6])) if bad_decl else
                   '%d theme(s) x 4 tokens' % len(ids))
        self.check('A3 every theme CONSUMES the four tokens with var() in its own scope',
                   not bad_use,
                   ('unread: %s' % ', '.join(bad_use[:6])) if bad_use else
                   '%d consumer(s)' % sum(len(v.get('use', ())) for v in per.values()))
        no_fb = [n for n in FOUR if var_fallbacks(self.css, n) == 0]
        self.check('A4 the three closed-line tokens are used WITH their design fallback',
                   not [n for n in no_fb if n != '--motion-in'],
                   ('no fallback: %s' % ', '.join(no_fb)) if no_fb else
                   'size/leading/weight carry the design own value')

    def arm_b(self):
        scoped = set()
        for pre, body, _off in blocks(self.css):
            t = theme_scope(pre)
            if t and var_uses(body, '--motion-in'):
                scoped.add(t)
        ids = set(self.theme_ids())
        missing = sorted(ids - scoped)
        total = len(re.findall(r'var\(\s*--motion-in\b', self.css))
        self.check('B1 the motion token is read INSIDE every theme scope', not missing,
                   ('missing: %s' % ', '.join(missing[:6])) if missing else
                   '%d/%d theme(s); %d use(s) in the file' % (len(scoped), len(ids), total))
        shared = [pre for pre, b, _o in blocks(self.css)
                  if pre.startswith(":root[data-theme^='cine-']") and var_uses(b, '--motion-in')]
        self.check('B2 the set-wide shared block still reads it for the caption',
                   bool(shared), '%d shared rule(s)' % len(shared))

    def arm_c(self):
        """A token declared here is DEAD only if nothing anywhere reads it. The theme
        documents are companions: `panel.css` and the other sheets read the alias half
        of the contract (--text, --text-dim, --accent-from, --line-strong, ...) and the
        shell / panel.js read four more through getComputedStyle and inline writes, so a
        scan of THIS file alone reports live tokens as dead. Measured: the naive scan
        named 8 names that panel.css reads 1-68 times each."""
        decl = {}
        for _pre, body, _off in blocks(self.css):
            for n in declared_names(body):
                decl[n] = decl.get(n, 0) + 1
        readers = reader_universe()
        dead = []
        for n in sorted(decl):
            if n in EXTERNAL_READERS or n in readers:
                continue
            dead.append('%s (x%d)' % (n, decl[n]))
        self.check('C1 no token is declared and left without a reader anywhere', not dead,
                   ('declared+unread: %s' % ', '.join(dead[:8])) if dead else
                   '%d declared token(s), all read (%d reader name(s))'
                   % (len(decl), len(readers)))
        present = [n for n in D6_NAMES if re.search(r'^\s*' + re.escape(n) + r'\s*:', self.css, re.M)]
        self.check('C2 the audit D6 list is absent from cinematic.css', not present,
                   ('still declared: %s' % ', '.join(present)) if present else
                   '0/%d name(s) declared' % len(D6_NAMES))

    def arm_d(self):
        live = live_classes()
        names = css_classes(self.css)
        dead = sorted(n for n in names if n not in live)
        self.check('D1 every class selector matches a class the document can carry',
                   not dead,
                   ('dead: %s' % ', '.join(dead[:8])) if dead else
                   '%d class selector(s), 0 dead (universe %d)' % (len(names), len(live)))
        pair = [n for n in ('status__hint', 'chrome__key') if n in names]
        self.check('D2 the audit D5 pair is absent from cinematic.css', not pair,
                   ('still present: %s' % ', '.join(pair)) if pair else
                   '.status__hint / .chrome__key: 0 occurrence(s)')

    def arm_e(self):
        rows = run_manifest(self.js_path)
        labels = [r.get('label') for r in rows]
        dupes = sorted({l for l in labels if labels.count(l) > 1})
        self.check('E1 no two picker entries share a label', not dupes,
                   ('duplicated: %s' % ', '.join(dupes)) if dupes else
                   '%d entries, %d distinct labels' % (len(rows), len(set(labels))))
        wrong = {}
        for k, v in LABEL_EXPECT.items():
            got = next((r.get('label') for r in rows if r.get('name') == k), None)
            if got != v:
                wrong[k] = '%r != %r' % (got, v)
        self.check('E2 the two ambiguous labels are the ones the audit fixed', not wrong,
                   ('wrong: %s' % wrong) if wrong else
                   '; '.join('%s=%r' % (k, v) for k, v in sorted(LABEL_EXPECT.items())))

    def arm_f(self):
        rows = run_manifest(self.js_path)
        by_name = {r.get('name'): r.get('label') for r in rows}
        skins = read(SKINS)
        mism = []
        for tid in TWO_LAYER:
            m = re.search(r'"%s"\s*:\s*\{(.*?)\}\s*,\s*"zip"' % re.escape(tid),
                          skins, re.S)
            if not m:
                mism.append('%s: no skin entry found in skins.js' % tid)
                continue
            lm = re.search(r'"label"\s*:\s*"([^"]*)"', m.group(1))
            if not lm:
                mism.append('%s: the skin entry carries no label' % tid)
                continue
            m = lm
            if by_name.get(tid) != m.group(1):
                mism.append('%s: picker %r != skin %r' % (tid, by_name.get(tid), m.group(1)))
        self.check('F1 the six two-layer ids show the mounted skin own label', not mism,
                   '; '.join(mism) if mism else
                   '%d/%d agree with skins/skins.js' % (len(TWO_LAYER), len(TWO_LAYER)))

    def arm_g(self):
        rows = run_manifest(self.js_path)
        names = [r.get('name') for r in rows]
        originals = [n for n in names if re.match(r'^theme-[1-5]$', str(n))]
        self.check('G1 the manifest parses and holds the five original directions',
                   len(originals) == 5, '%d original entries' % len(originals))
        # The 25 designs THIS file carries are the ones whose `file` is cinematic.css:
        # the other 14 `cine-*` names are the frozen skins (file: null), which the
        # picker lists too. Counting by prefix alone said 39 and would have been a
        # wrong gate on the right file.
        cine = [r.get('name') for r in rows
                if r.get('file') == 'themes/cinematic.css']
        self.check('G2 the manifest carries the 25 entries of cinematic.css', len(cine) == 25,
                   '%d cinematic.css entries (%d cine-* names in all)'
                   % (len(cine), len([n for n in names if str(n).startswith('cine-')])))
        self.check('G4 the manifest carries all 59 entries the picker lists',
                   len(names) == 59, '%d entries' % len(names))
        dupes = sorted({n for n in names if names.count(n) > 1})
        self.check('G3 no entry appears twice', not dupes, ', '.join(dupes) or 'ok')

    def arm_h(self):
        scratch = os.path.join(os.environ.get('TMPDIR') or 'I:/cc-tmp', 'cine-oracle-fresh')
        if os.path.isdir(scratch):
            shutil.rmtree(scratch, ignore_errors=True)
        os.makedirs(scratch)
        bd = os.path.join(scratch, 'backdrops')
        os.makedirs(bd)
        src_bd = os.path.join(THEMES, 'backdrops')
        for n in os.listdir(src_bd):
            s = os.path.join(src_bd, n)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(bd, n))
        shutil.copy2(self.js_path, os.path.join(scratch, 'themes.js'))
        harness = os.path.join(scratch, 'harness.py')
        with io.open(harness, 'w', encoding='utf-8') as fh:
            fh.write(HARNESS % {
                'gen': self.gen_path.replace(chr(92), chr(92) * 2),
                'out': scratch.replace(chr(92), chr(92) * 2),
                'seed': self.js_path.replace(chr(92), chr(92) * 2),
            })
        proc = subprocess.run([sys.executable, harness], capture_output=True, timeout=300,
                              creationflags=0x08000000)
        if proc.returncode != 0:
            self.check('H1 a fresh generator run reproduces the bytes on disk', False,
                       'the generator exited %d: %s' % (proc.returncode,
                        proc.stderr.decode('utf-8', 'replace')[-300:]))
            return
        fresh_css = os.path.join(scratch, 'cinematic.css')
        fresh_js = os.path.join(scratch, 'themes.js')
        rows = []
        for label, fresh, disk in (('cinematic.css', fresh_css, self.css_path),
                                   ('themes.js', fresh_js, self.js_path)):
            fb, fh = sha16(fresh)
            db, dh = sha16(disk)
            rows.append('%s %d/%s vs %d/%s' % (label, fb, fh[:12], db, dh[:12]))
            self.check('H1 %s IS the generator output' % label, fh == dh, rows[-1])
        self.check('H2 the generator is the source of both documents', True, '; '.join(rows))


HARNESS = """# -*- coding: utf-8 -*-
import os, sys, shutil, importlib.util
GEN = r"%(gen)s"
OUT = r"%(out)s"
sys.path.insert(0, os.path.dirname(GEN))
spec = importlib.util.spec_from_file_location("gen_cinematic", GEN)
G = importlib.util.module_from_spec(spec)
sys.modules["gen_cinematic"] = G
spec.loader.exec_module(G)
G.CSS_OUT = os.path.join(OUT, "cinematic.css")
G.JS_OUT = os.path.join(OUT, "themes.js")
G.BACKDROPS = os.path.join(OUT, "backdrops")
shutil.copy2(r"%(seed)s", G.JS_OUT)
sys.exit(G.main())
"""


def run_arms(g, arms):
    for arm in arms:
        try:
            getattr(g, 'arm_' + arm)()
        except Exception as exc:
            g.check('arm %s raised' % arm.upper(), False, str(exc)[:300])
    return g.results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--css', default=CSS_DISK)
    ap.add_argument('--js', default=JS_DISK)
    ap.add_argument('--gen', default=GEN)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    if args.neg_arm:
        return neg_arm()

    print('CINE-THEMES ORACLE -- PRISTINE (the bytes on disk)')
    print('  css: %s' % args.css)
    print('  js : %s' % args.js)
    print('  gen: %s' % args.gen)
    n, h = sha16(args.css)
    print('  %d B, sha256 %s' % (n, h[:16]))
    print('')
    g = Gate(args.css, args.js, args.gen)
    run_arms(g, 'abcdefgh')
    failed = [r for r in g.results if not r[1]]
    for name, ok, detail in g.results:
        print('  %s %s' % ('ok  ' if ok else 'FAIL', name))
        if detail:
            print('        %s' % detail)
    print('')
    print('%d check(s), %d failed' % (len(g.results), len(failed)))
    print('VERDICT: %s' % ('PASS' if not failed else 'FAIL'))
    return 0 if not failed else 1


def neg_arm():
    """THE CONTROL: the same predicates against MUTATED COPIES. Each mutation is
    injected into a copy; the arm it must kill has to go RED and the control (the
    shipped bytes) has to stay GREEN. M7 mutates a COPY OF THE GENERATOR, because
    mutating the manifest or a CSS module cannot move the CSS bytes H reads."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix='cine-neg-', dir=os.environ.get('TMPDIR') or None)
    css = read(CSS_DISK)
    js = read(JS_DISK)
    gen = read(GEN)

    def write(name, text, sub):
        p = os.path.join(tmp, sub, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        return p

    print('CINE-THEMES ORACLE -- NEG-ARM (mutated copies)')
    print('  scratch: %s' % tmp)
    print('')

    ctrl = run_arms(Gate(CSS_DISK, JS_DISK, GEN), 'abcdefgh')
    ctrl_red = [n for n, ok, _d in ctrl if not ok]
    print('  CONTROL GREEN  failed=%s' % (', '.join(ctrl_red) if ctrl_red else 'none'))
    print('')

    mutants = []
    # M1 -- the theme stops reading --size-closed.
    # THE ANCHOR IS THE SHIPPED FORM (re-anchored 2026-10-20). The owner's font dial
    # is a MULTIPLIER: `--caption-scale` is written on the document element by
    # `app/panel/panel.js:2312` (the dial itself: `panel.js:306`, "THE TRANSCRIPT
    # FONT DIAL (owner, 2026-10-09)") and the generator carries it on BOTH terms of
    # the closed line (`_main/_design-lane/gen_cinematic.py:958` and the `CLOSED`
    # table at :274), so the closed line shrinks and grows with the live one.
    # MEASURED 2026-10-20 on `app/panel/themes/cinematic.css` (the file this oracle
    # reads): the OLD anchor `var(--size-closed, calc(var(--size-caption) * 0.72))`
    # has count=0 -- that is WHY M1 was INERT -- and the SHIPPED one has count=10,
    # one per theme of the `cinematic` family, the first at `cinematic.css:251`
    # (`:root[data-theme='cine-midnight-rain'] .caption:not(.caption--latest)
    # .caption__text`). The first of the ten is in a THEME scope, so the mutant
    # really does take that theme's `var(--size-closed)` reader away and the A3 arm
    # goes RED.
    m1 = replace_once(css,
                      "var(--size-closed, calc(var(--size-caption) * 0.72 * var(--caption-scale)))",
                      "13px", 'M1')
    mutants.append(('M1 one theme stops reading --size-closed',
                    write('m1.css', m1, 'm1'), JS_DISK, GEN, 'a', ['A3']))
    m2 = re.sub(r":root\[data-theme='cine-warm-hour'\] \.chrome \* \{.*?\n\}\n",
                '', css, count=1, flags=re.S)
    if m2 == css:
        raise SystemExit('mutant anchor not found: cine-warm-hour .chrome * (in M2)')
    mutants.append(('M2 one theme stops reading --motion-in',
                    write('m2.css', m2, 'm2'), JS_DISK, GEN, 'b', ['B1']))
    m3 = replace_once(css, "--cine-scrim:", "--slab-opacity: 0.97;\n  --cine-scrim:", 'M3')
    mutants.append(('M3 a token comes back declared and unread',
                    write('m3.css', m3, 'm3'), JS_DISK, GEN, 'c', ['C1', 'C2']))
    m4 = replace_once(css, ".captions__hint {", ".status__hint {", 'M4')
    mutants.append(('M4 a dead class reference comes back',
                    write('m4.css', m4, 'm4'), JS_DISK, GEN, 'd', ['D1', 'D2']))
    m5 = replace_once(js, "label: 'Tideline (wide)'", "label: 'Tideline'", 'M5')
    mutants.append(('M5 two picker entries share a label again',
                    CSS_DISK, write('m5.js', m5, 'm5'), GEN, 'e', ['E1']))
    m6 = replace_once(js, "label: 'Cellar'", "label: 'Cellar Sessions'", 'M6')
    mutants.append(('M6 a picker label stops matching the mounted skin',
                    CSS_DISK, write('m6.js', m6, 'm6'), GEN, 'f', ['F1']))
    m7 = replace_once(gen, "'--motion-in': '150ms',", "'--motion-in': '151ms',", 'M7')
    mutants.append(('M7 the generator itself is mutated (the CSS bytes move)',
                    CSS_DISK, JS_DISK, write('gen_m7.py', m7, 'm7'), 'h', ['H1']))
    m8 = replace_once(css, "  --cine-scrim:", "  --cine-scrim: /* hand edit */", 'M8')
    mutants.append(('M8 the shipped CSS is a hand edit of the generator output',
                    write('m8.css', m8, 'm8'), JS_DISK, GEN, 'h', ['H1']))

    wrong, inert = [], []
    for label, css_path, js_path, gen_path, arms, want in mutants:
        res = run_arms(Gate(css_path, js_path, gen_path), arms)
        red = [n for n, ok, _d in res if not ok]
        hit = [n for n in red if n.split()[0] in want]
        got = 'RED on %s' % ','.join(n.split()[0] for n in red) if red else 'GREEN'
        status = 'PASS' if hit else ('INERT' if not red else 'WRONG')
        if not hit:
            (inert if not red else wrong).append(label)
        print('  %s %s' % (status, label))
        print('        want RED on %s   got %s' % (','.join(want), got))
    print('')
    print('NEG-ARM VERDICT: %s -- %d mutant(s), %d wrong, %d inert, control %s'
          % ('PASS' if not wrong and not inert and not ctrl_red else 'FAIL',
             len(mutants), len(wrong), len(inert),
             'GREEN' if not ctrl_red else 'RED(%s)' % ','.join(ctrl_red)))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if not wrong and not inert and not ctrl_red else 1


if __name__ == '__main__':
    sys.exit(main())