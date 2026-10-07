#!/usr/bin/env python3
"""Prove that the five design directions REALLY apply to the live panel document.

WHAT THIS MEASURES, and why it is not a grep. The claim "theme 1 is the
Teleprompter direction" is a claim about what a browser COMPUTED for the caption
element — its family, its size, its weight, its leading, its ALIGNMENT, its halo,
the accent actually painted, and whether the direction's own FACE loaded. A class
or an attribute changing proves only that something wrote a string. So this runner
loads a COPY of the REAL `app/panel/panel.html` in Chromium, runs
`_main/_theme-probe.js` inside it (which injects the three real caption rows
`panel.js` builds and then reads `getComputedStyle` for each theme in turn), and
reads the values back out of the DOM the browser dumps.

WHY A COPY, AND WHAT IS REWRITTEN IN IT. Three things, and nothing else:

  * `<script src="_theme-probe.js">` is appended (the shipped panel never loads a
    probe);
  * in the CONTROL arms, the five `themes/theme-N.css` links are DELETED, or the
    bundled font files are hidden. That is the control: the same instrument, on a
    copy with the mechanism (or the fonts) taken out, has to go RED. An instrument
    that cannot say no is not an instrument;
  * in the PERSISTENCE arms, a `#theme-probe-op=set|read` hash. Those two arms are
    what make "does the choice survive a restart" a measurement instead of a hope:
    one document CHOOSES a theme, a second, independent document is loaded against
    the SAME profile directory and must COME UP already wearing it. The control for
    that pair is a third load against a VIRGIN profile, which must come up in the
    fallback.

THE BROWSER IS Chromium (Edge by default — the same engine class the app runs in
WebView2 — or Chrome with `--browser chrome`), in `--headless=new`, with
`--virtual-time-budget` so the font loads and the `document.fonts.ready` wait
finish before the dump. It is NOT a visible window: the headless flag is asserted
before anything runs.

WHAT IT PRINTS. One row per theme with the computed family, size, weight, leading,
alignment, halo and the accent decision, then a VERDICT. `--neg-arm` runs the
control arms too and requires them RED. Exit code is the verdict: 0 GREEN, 1 RED.

Usage:
  py -3 _main\\_theme-probe-arm.py                  # real files, real DOM
  py -3 _main\\_theme-probe-arm.py --neg-arm        # + controls, must go RED
  py -3 _main\\_theme-probe-arm.py --browser chrome
"""

import argparse
import html as html_mod
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir))
PANEL = os.path.join(REPO, 'app', 'panel')

EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
CHROME_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]

ASSETS = ('panel.css', 'caption-formulation.js', 'history-source.js', 'surface.js',
          'panel.js', 'theme-switcher.js', 'themes/themes.js', 'themes/fonts.css',
          'themes/theme-1.css', 'themes/theme-2.css', 'themes/theme-3.css',
          'themes/theme-4.css', 'themes/theme-5.css')

# The five directions, as the owner's `designs.ts` declares them and as the
# shipped manifest repeats them. Kept here as the EXPECTED side of the
# comparison: a probe that reads the expectation out of the thing it is testing
# cannot fail.
EXPECTED = [
    ('theme-1', 'Teleprompter', 'Barlow Condensed', '#f2e9d8'),
    ('theme-2', 'Broadcast', 'IBM Plex Mono', '#ff6a55'),
    ('theme-3', 'Manuscrito', 'Newsreader', '#a9c1d9'),
    ('theme-4', 'Cinema Card', 'Fraunces', '#e4b363'),
    ('theme-5', 'Instrumento', 'Space Grotesk', '#5fd3a7'),
]

# The direction whose live line is marked by SIZE + WEIGHT + A HALO instead of a
# rail. Named once, so the two branches below cannot drift apart.
NO_RAIL_DIRECTION = 'theme-1'


def find_browser(name):
    cands = EDGE_CANDIDATES if name == 'edge' else CHROME_CANDIDATES
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def build_arm(root, mode):
    """A copy of the REAL panel, in `root`, with the probe appended.

    `mode`:
      real            — the shipped files, untouched
      control-theme   — the five theme stylesheets REMOVED (control)
      control-fonts   — the bundled woff2 files hidden by name (control)
      control-weight  — the Barlow Condensed 400 @font-face removed from the COPY
                        (control for the `historyWeightCovered` assertion)
    """
    os.makedirs(os.path.join(root, 'themes'), exist_ok=True)
    os.makedirs(os.path.join(root, 'fonts'), exist_ok=True)

    with open(os.path.join(PANEL, 'panel.html'), encoding='utf-8') as fh:
        html = fh.read()

    for asset in ASSETS:
        if f'"{asset}"' not in html:
            raise SystemExit(f'panel.html no longer references {asset!r}')

    if mode == 'control-theme':
        for n in range(1, 6):
            tag = f'<link rel="stylesheet" href="themes/theme-{n}.css" />'
            if tag in html:
                html = html.replace(tag, f'<!-- CONTROL: {tag} removed -->')
        # …and the base theme attribute goes too, so nothing else can carry the
        # direction: the control must fail for the reason it is supposed to.
        html = html.replace('data-theme="theme-1"', 'data-theme=""')
        for token in ('themes/themes.js', 'theme-switcher.js'):
            tag = f'<script src="{token}"></script>'
            html = html.replace(tag, f'<!-- CONTROL: {tag} removed -->')

    html = html.replace('</body>', '    <script src="_theme-probe.js"></script>\n  </body>')

    with open(os.path.join(root, 'panel.html'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)

    # The assets the page needs, by real name, so nothing in the copy is a stand-in.
    for name in ('panel.css', 'caption-formulation.js', 'history-source.js',
                 'surface.js', 'panel.js', 'theme-switcher.js'):
        shutil.copyfile(os.path.join(PANEL, name), os.path.join(root, name))
    shutil.copyfile(os.path.join(PANEL, 'themes', 'themes.js'),
                    os.path.join(root, 'themes', 'themes.js'))
    shutil.copyfile(os.path.join(PANEL, 'themes', 'fonts.css'),
                    os.path.join(root, 'themes', 'fonts.css'))
    if mode != 'control-theme':
        for n in range(1, 6):
            shutil.copyfile(os.path.join(PANEL, 'themes', f'theme-{n}.css'),
                            os.path.join(root, 'themes', f'theme-{n}.css'))
    shutil.copyfile(os.path.join(HERE, '_theme-probe.js'), os.path.join(root, '_theme-probe.js'))
    for fn in os.listdir(os.path.join(PANEL, 'fonts')):
        if mode == 'control-fonts' and fn.endswith('.woff2'):
            continue
        shutil.copyfile(os.path.join(PANEL, 'fonts', fn), os.path.join(root, 'fonts', fn))

    if mode == 'control-weight':
        # THE CONTROL FOR THE NEW ASSERTION, and the exact defect it was written
        # for: theme 1's settled history asks for Barlow Condensed 400, and the
        # bundle used to ship only 700. Removing that ONE `@font-face` from the
        # copy must turn `historyWeightCovered` RED for theme-1 and leave the
        # other four themes untouched — which is what makes it a control rather
        # than a second way to fail everything.
        #
        # The removal is a `.replace()` of the ONE matched block, NOT a slice up
        # to the first `@font-face`: the generated header mentions `@font-face` in
        # prose, so slicing there cut the file INSIDE its own `/* … */` comment and
        # commented out all fourteen rules — measured: that first version reported
        # `fontSourceWoff2: 0` and turned every theme red, which is a blunt control
        # that proves much less.
        css_path = os.path.join(root, 'themes', 'fonts.css')
        with open(css_path, encoding='utf-8') as fh:
            css = fh.read()
        blocks = re.findall(r'@font-face\s*\{.*?\}', css, re.DOTALL)
        targets = [b for b in blocks
                   if "font-family: 'Barlow Condensed'" in b and 'font-weight: 400' in b]
        if len(targets) != 1:
            raise SystemExit(f'control-weight: expected exactly 1 Barlow Condensed 400 '
                             f'@font-face to drop, matched {len(targets)} of {len(blocks)} blocks')
        css = css.replace(targets[0], '/* CONTROL: Barlow Condensed 400 @font-face removed */')
        remaining = len(re.findall(r'@font-face\s*\{.*?\}', css, re.DOTALL))
        if remaining != len(blocks) - 1:
            raise SystemExit(f'control-weight: {remaining} @font-face block(s) left, '
                             f'expected {len(blocks) - 1} of {len(blocks)}')
        with open(css_path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(css)
    return html


def run_browser(exe, root, extra_hash='', profile=None, allow_file_access=True):
    url = 'file:///' + os.path.join(root, 'panel.html').replace('\\', '/') + extra_hash
    profile = profile or os.path.join(root, '_profile')
    cmd = [
        exe, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
        '--virtual-time-budget=6000',
        f'--user-data-dir={profile}', '--dump-dom', url,
    ]
    if allow_file_access:
        cmd.insert(4, '--allow-file-access-from-files')
    proc = subprocess.run(cmd, capture_output=True, timeout=180)
    out = proc.stdout.decode('utf-8', 'replace')
    err = proc.stderr.decode('utf-8', 'replace')
    return out, err, proc.returncode, url


ATTR_RE = re.compile(r'data-theme-probe-(\d+|summary)="([^"]*)"')


def parse(dom):
    found = {}
    for key, value in ATTR_RE.findall(dom):
        try:
            found[key] = json.loads(html_mod.unescape(value))
        except Exception as exc:      # noqa: BLE001 - reported, never swallowed
            found[key] = {'_parse_error': str(exc), '_raw': value[:200]}
    return found


def rgb(hexcol):
    h = hexcol.lstrip('#')
    return 'rgb(%d, %d, %d)' % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def judge(found, label):
    """The verdict for one arm. Returns (green: bool, rows: list[str], problems: list[str])."""
    rows, problems = [], []
    control_family_resolved = False
    themes = [found.get(str(i)) for i in range(5)]
    summary = found.get('summary') or {}

    if not themes[0]:
        problems.append(f'{label}: the probe produced NO theme rows '
                        f'(summary={json.dumps(summary)[:300]})')
        return False, rows, problems

    for i, (name, label_dir, family, accent) in enumerate(EXPECTED):
        m = themes[i]
        if not m:
            problems.append(f'{label}: {name} row missing')
            continue
        forming = m.get('forming') or {}
        history = m.get('history') or {}
        latest = m.get('latest') or {}
        sheet = m.get('sheet') or {}
        # The RAIL belongs to the LINE (`<li>`), not to the text span: the theme
        # paints `.caption--provisional`'s left border. The TYPE belongs to the
        # span. Two elements, two reads, one row.
        fam = (forming.get('family') or '').replace('"', '')
        tokens = [t.strip() for t in fam.split(',')]
        resolved = family in tokens
        rows.append(
            '%-9s %-13s family=%-19s live=%s/%s/%s align=%-5s halo=%-5s '
            'hist=%s rail(live/hist/latest)=%s/%s/%s accent-token=%-9s sheet=%s/%s '
            'faces=%s'
            % (name, label_dir, tokens[0][:19], forming.get('size'), forming.get('weight'),
               forming.get('lineHeight'), forming.get('textAlign'),
               'glow' if forming.get('textShadow') not in (None, 'none') else 'flat',
               history.get('size'), m.get('liveRailVisible'), m.get('historyRailVisible'),
               m.get('latestRailVisible'), m.get('accentToken'),
               sheet.get('rootScoped'), sheet.get('captionTextRules'), m.get('facesLoadedByApi')))
        rows.append('          bundle weights for %s = %s ; live %s covered=%s ; settled %s '
                    'covered=%s'
                    % (family, m.get('bundleWeights'), forming.get('weight'),
                       m.get('liveWeightCovered'), history.get('weight'),
                       m.get('historyWeightCovered')))

        if not resolved:
            problems.append(f'{label}: {name} ({label_dir}) computed family is {fam!r} — '
                            f'the direction\'s own {family!r} is NOT the first token')
        if m.get('rootAttribute') != name:
            problems.append(f'{label}: {name} measured while <html data-theme> was '
                            f'{m.get("rootAttribute")!r}')

        # ── THE ACCENT: the token the theme declares, and the pixel it paints ──
        if not m.get('accentTokenIsDirection'):
            problems.append(f'{label}: {name} ({label_dir}) declares --accent '
                            f'{m.get("accentToken")!r}, the direction says {accent!r}')
        if not (m.get('liveAccentPainted') or m.get('wordmarkPaintedAccent')
                or m.get('liveTextIsAccent')):
            problems.append(f'{label}: {name} ({label_dir}) the accent is painted NOWHERE: '
                            f'rail={m.get("liveRailVisible")} wordmark={m.get("wordmarkColor")!r} '
                            f'live-text={forming.get("color")!r} — expected {rgb(accent)}')

        # ── "the history recedes": settled text is SMALLER and FLAT ────────────
        if not m.get('liveBiggerThanHistory'):
            problems.append(f'{label}: {name} the live line is not larger than the settled '
                            f'history ({forming.get("size")} vs {history.get("size")})')
        if not m.get('liveBiggerThanLatest'):
            problems.append(f'{label}: {name} the live line is not larger than the line that '
                            f'just closed ({forming.get("size")} vs {latest.get("size")})')
        if history.get('textShadow') not in (None, 'none'):
            problems.append(f'{label}: {name} the settled history carries a halo '
                            f'({history.get("textShadow")!r}) — settled text must not shine')
        # A SETTLED line must not wear the live line's mark. `0px solid` paints
        # nothing, so the WIDTH is the fact and the style keyword is not — the
        # page computes the boolean from the box, and the box is quoted in the
        # message so a failing row says WHICH border it saw.
        if m.get('historyRailVisible'):
            problems.append(f'{label}: {name} the SETTLED history line kept a visible rail '
                            f'({(m.get("historyLineBox") or {}).get("borderLeftWidth")} '
                            f'{(m.get("historyLineBox") or {}).get("borderLeftStyle")} '
                            f'{(m.get("historyLineBox") or {}).get("borderLeftColor")})')
        if m.get('latestRailVisible'):
            problems.append(f'{label}: {name} the NEWEST CLOSED line kept a visible rail '
                            f'({(m.get("latestLineBox") or {}).get("borderLeftWidth")} '
                            f'{(m.get("latestLineBox") or {}).get("borderLeftStyle")} '
                            f'{(m.get("latestLineBox") or {}).get("borderLeftColor")}) — a '
                            f'settled line wearing the live mark reads as still live')

        # ── the LIVE line's own mark, which differs BY DIRECTION ──────────────
        if name == NO_RAIL_DIRECTION:
            if m.get('liveRailVisible'):
                problems.append(f'{label}: {name} the Teleprompter live line carries a rail — '
                                f'the direction forbids it ("nothing is boxed")')
            if not m.get('liveShines'):
                problems.append(f'{label}: {name} the Teleprompter live line does NOT shine: '
                                f'text-shadow is {forming.get("textShadow")!r} — the direction '
                                f'says the live line is the one that glows')
            if not m.get('leftAligned'):
                problems.append(f'{label}: {name} the Teleprompter line is not left-aligned '
                                f'(text-align={forming.get("textAlign")!r}) — the direction says '
                                f'RIGIDLY LEFT-ALIGNED')
        else:
            if not m.get('liveRailVisible'):
                problems.append(f'{label}: {name} the LIVE line has no visible rail '
                                f'({(m.get("lineBox") or {}).get("borderLeftWidth")} '
                                f'{(m.get("lineBox") or {}).get("borderLeftStyle")})')
        if forming.get('style') != 'normal' and name != 'theme-4':
            problems.append(f'{label}: {name} the live line computed font-style '
                            f'{forming.get("style")!r} — panel.css\'s italic is leaking through')

        # ── THE FACE and THE SHEET: named is not loaded, present is not parsed ─
        if m.get('facesLoadedByApi') in (0, 'error:NotFoundError', 'error:NetworkError'):
            problems.append(f'{label}: {name} family {family!r} did not load as a webfont '
                            f'(facesLoadedByApi={m.get("facesLoadedByApi")!r})')
        if not m.get('faceKnown'):
            problems.append(f'{label}: {name} `document.fonts.check()` says {family!r} is unknown '
                            f'to the document')
        # THE WEIGHT THE THEME ASKS FOR MUST BE A FACE THE BUNDLE CARRIES. A
        # `font-weight` in getComputedStyle is the author's number; CSS font
        # matching silently substitutes the nearest face, which is how theme 1's
        # settled history painted the live line's 700 strokes while its computed
        # weight said 400. `document.fonts` is where the faces are.
        if not m.get('liveWeightCovered'):
            problems.append(f'{label}: {name} the bundle carries NO {family!r} face at the LIVE '
                            f'line\'s weight {forming.get("weight")!r} (it carries '
                            f'{m.get("bundleWeights")}) — the browser will substitute another '
                            f'weight silently')
        if not m.get('historyWeightCovered'):
            problems.append(f'{label}: {name} the bundle carries NO {family!r} face at the '
                            f'SETTLED line\'s weight {history.get("weight")!r} (it carries '
                            f'{m.get("bundleWeights")}) — so "the history recedes" is being '
                            f'carried by size and hue alone, with the live weight\'s strokes')
        if m.get('faceKnownControl'):
            # NOT a failure, and the reason is a measured fact about the engine:
            # `document.fonts.check()` answers TRUE for a family name that does
            # not exist anywhere (measured on this box: it returned True for
            # "Sotto No Such Family"). The check is not a usable falsifier, so it
            # is REPORTED once per arm rather than asserted, and the falsifiable
            # half of the face claim is `document.fonts.load()` below —
            # `control-fonts` goes RED on exactly that, which is what makes it a
            # control.
            control_family_resolved = True
        if not sheet.get('found'):
            problems.append(f'{label}: {name} {sheet.get("file")} is not among the parsed '
                            f'stylesheets')
        elif not sheet.get('rules'):
            problems.append(f'{label}: {name} {sheet.get("file")} parsed to 0 rules '
                            f'(error={sheet.get("error")!r})')
        elif not sheet.get('rootScoped'):
            problems.append(f'{label}: {name} {sheet.get("file")} carries no rule scoped to '
                            f"':root[data-theme={name!r}]'")
        elif not sheet.get('captionTextRules'):
            problems.append(f'{label}: {name} {sheet.get("file")} carries no rule reaching '
                            f'`.caption__text`')

        # ── THE SWITCHER'S OWN BUTTON, which is how the owner changes theme ────
        if m.get('buttonLabel') != label_dir:
            problems.append(f'{label}: {name} the switcher button reads '
                            f'{m.get("buttonLabel")!r}, expected {label_dir!r}')
        if not m.get('buttonSwatchIsAccent'):
            problems.append(f'{label}: {name} the switcher swatch is {m.get("buttonSwatch")!r}, '
                            f'expected {rgb(accent)!r}')

    # ── the document-level inventory ──────────────────────────────────────────
    if control_family_resolved:
        rows.append('NOTE: document.fonts.check("Sotto No Such Family") answered TRUE, so '
                    'check() cannot falsify a family name on this Chromium; the falsifiable '
                    'half of the face claim is document.fonts.load() (see the faces= column, '
                    'and the control-fonts arm going RED on it)')
    if summary.get('themeCountLinked') != 5:
        problems.append(f'{label}: {summary.get("themeCountLinked")} theme stylesheets linked, '
                        f'expected 5')
    if not summary.get('fontsLinked'):
        problems.append(f'{label}: themes/fonts.css not linked')
    if not (summary.get('fontSourceWoff2') or 0) >= 14:
        problems.append(f'{label}: only {summary.get("fontSourceWoff2")} @font-face rule(s) with '
                        f'woff2 were reachable from the document, expected >= 14 (the bundle: '
                        f'Barlow Condensed 400/700, IBM Plex Mono 400/500/600/700, Newsreader '
                        f'400/600, Fraunces 400/500/600, Space Grotesk 400/500/700)')
    manifest = summary.get('manifest')
    if not manifest:
        problems.append(f'{label}: `window.SottoThemeManifest` is absent — themes/themes.js did '
                        f'not run')
    else:
        if manifest.get('names') != [e[0] for e in EXPECTED]:
            problems.append(f'{label}: manifest order is {manifest.get("names")} — the owner\'s '
                            f'order is {[e[0] for e in EXPECTED]}')
        if manifest.get('labels') != [e[1] for e in EXPECTED]:
            problems.append(f'{label}: manifest labels are {manifest.get("labels")} — expected '
                            f'{[e[1] for e in EXPECTED]}')
        if [s.lower() for s in manifest.get('swatches', [])] != [e[3] for e in EXPECTED]:
            problems.append(f'{label}: manifest swatches are {manifest.get("swatches")} — expected '
                            f'{[e[3] for e in EXPECTED]}')
        if manifest.get('fallback') != EXPECTED[0][0]:
            problems.append(f'{label}: manifest fallback is {manifest.get("fallback")!r}')
    for e in summary.get('errors') or []:
        problems.append(f'{label}: probe error: {e}')
    return (not problems), rows, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', choices=('edge', 'chrome'), default='edge')
    ap.add_argument('--neg-arm', action='store_true',
                    help='also run the control arms and REQUIRE them RED')
    ap.add_argument('--keep', action='store_true', help='keep the temp arm directories')
    args = ap.parse_args()

    exe = find_browser(args.browser)
    if not exe:
        print(f'NO BROWSER: {args.browser} not found', file=sys.stderr)
        return 2
    print(f'browser: {exe}')
    print('HEADLESS ONLY: --headless=new on every arm; no window is created.')

    base = tempfile.mkdtemp(prefix='sotto-theme-probe-')
    all_ok = True

    arms = [('real', 'REAL panel.html')]
    if args.neg_arm:
        arms += [('control-theme', 'CONTROL: five theme stylesheets removed'),
                 ('control-fonts', 'CONTROL: bundled woff2 files removed'),
                 ('control-weight', 'CONTROL: Barlow Condensed 400 @font-face removed')]

    results = {}
    for mode, label in arms:
        root = os.path.join(base, mode)
        os.makedirs(root, exist_ok=True)
        build_arm(root, mode)
        dom, err, rc, url = run_browser(exe, root)
        with open(os.path.join(base, f'dom-{mode}.html'), 'w', encoding='utf-8') as fh:
            fh.write(dom)
        found = parse(dom)
        green, rows, problems = judge(found, label)
        results[mode] = (green, rows, problems)
        print()
        print(f'-- arm {mode}: {label}  (rc={rc}, dom={len(dom)} B, url={url})')
        print('   summary: ' + json.dumps(found.get('summary'), ensure_ascii=True)[:700])
        for r in rows:
            print('   ' + r)
        if err.strip():
            interesting = [l for l in err.strip().splitlines()
                           if 'error' in l.lower() or 'warn' in l.lower()]
            if interesting:
                print('   browser stderr (first 5): ' + ' | '.join(interesting[:5])[:300])

    real_green, _, real_problems = results['real']
    all_ok = real_green
    if not real_green:
        print()
        print('REAL-ARM PROBLEMS:')
        for p in real_problems:
            print('   - ' + p)

    if args.neg_arm:
        for mode in ('control-theme', 'control-fonts', 'control-weight'):
            green, _, problems = results.get(mode, (True, [], []))
            print()
            if green:
                print(f'CONTROL {mode}: GREEN — that is a FAILING control '
                      f'(the instrument passed with the mechanism removed)')
                all_ok = False
            else:
                print(f'CONTROL {mode}: RED-as-expected ({len(problems)} problem(s)); '
                      f'first: {problems[0][:150] if problems else "-"}')

        # ── PERSISTENCE, as three independent page loads ─────────────────────
        root = os.path.join(base, 'persist')
        os.makedirs(root, exist_ok=True)
        build_arm(root, 'real')
        prof = os.path.join(base, 'persist-profile')

        dom1, _, _, _ = run_browser(
            exe, root, '#theme-probe-op=set&theme-probe-theme=theme-3', profile=prof, )
        s1 = (parse(dom1).get('summary') or {})
        open(os.path.join(base, 'dom-persist-set.html'), 'w', encoding='utf-8').write(dom1)
        p1 = []
        if s1.get('themeAfterSet') != 'theme-3':
            p1.append(f"set arm: asked for theme-3, document wears {s1.get('themeAfterSet')!r}")
        st = s1.get('store') or {}
        if not st.get('writable'):
            p1.append(f"set arm: localStorage is NOT writable here ({st.get('error')!r})")
        elif st.get('roundTrip') != 'ok':
            p1.append(f"set arm: localStorage round-trip returned {st.get('roundTrip')!r}")

        dom2, _, _, _ = run_browser(exe, root, '#theme-probe-op=read', profile=prof)
        s2 = (parse(dom2).get('summary') or {})
        open(os.path.join(base, 'dom-persist-read.html'), 'w', encoding='utf-8').write(dom2)
        p2 = []
        if s2.get('themeAtLoad') != 'theme-3':
            p2.append(f"read arm: a NEW document in the SAME profile came up wearing "
                      f"{s2.get('themeAtLoad')!r}, not the stored 'theme-3'")
        if ((s2.get('store') or {}).get('sottoThemeLast')) != 'theme-3':
            p2.append(f"read arm: SottoTheme.last() is "
                      f"{(s2.get('store') or {}).get('sottoThemeLast')!r}")

        # THE CONTROL FOR PERSISTENCE: a VIRGIN profile must NOT come up in theme-3.
        virgin = os.path.join(base, 'persist-virgin-profile')
        dom3, _, _, _ = run_browser(exe, root, '#theme-probe-op=read', profile=virgin)
        s3 = (parse(dom3).get('summary') or {})
        open(os.path.join(base, 'dom-persist-virgin.html'), 'w', encoding='utf-8').write(dom3)
        virgin_ok = s3.get('themeAtLoad') == 'theme-1'

        # THE STORAGE DISCLOSURE: the shipped shell passes NO --allow-file-access
        # flag, so the same document is loaded WITHOUT it and the verdict reported.
        dom4, _, _, _ = run_browser(exe, root, '#theme-probe-op=read',
                                    profile=os.path.join(base, 'noflag-profile'),
                                    allow_file_access=False)
        s4 = (parse(dom4).get('summary') or {})
        open(os.path.join(base, 'dom-persist-noflag.html'), 'w', encoding='utf-8').write(dom4)
        st4 = s4.get('store') or {}

        print()
        print('-- arm persist-set: CHOOSE theme-3 in the shipped switcher')
        print(f"   themeAfterSet={s1.get('themeAfterSet')!r} store={json.dumps(st)[:200]}")
        print('-- arm persist-read: a SECOND document, SAME profile directory')
        print(f"   themeAtLoad={s2.get('themeAtLoad')!r} "
              f"SottoTheme.last()={(s2.get('store') or {}).get('sottoThemeLast')!r}")
        print('-- arm persist-virgin: the CONTROL — a profile that never chose')
        print(f"   themeAtLoad={s3.get('themeAtLoad')!r} (fallback required)")
        print('-- arm no-file-access: the shipped shell passes NO file-access flag')
        print(f"   localStorage writable={st4.get('writable')!r} error={st4.get('error')!r} "
              f"themeAtLoad={s4.get('themeAtLoad')!r}")

        if p1 or p2:
            print()
            print('PERSISTENCE PROBLEMS:')
            for p in p1 + p2:
                print('   - ' + p)
            all_ok = False
        else:
            print('PERSISTENCE: GREEN — the choice chosen in one document came back in the next')
        if not virgin_ok:
            print(f'CONTROL persist-virgin: GREEN — that is a FAILING control (a profile that '
                  f'never chose came up in {s3.get("themeAtLoad")!r})')
            all_ok = False
        else:
            print('CONTROL persist-virgin: RED-as-expected — the virgin profile fell back to '
                  'theme-1, so the persistence arm is not vacuous')

    print()
    print('VERDICT: %s' % ('GREEN — all five directions apply to the real panel document'
                           if all_ok else 'RED'))
    print('artifacts: %s' % base)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
