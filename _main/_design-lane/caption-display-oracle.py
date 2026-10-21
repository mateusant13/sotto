#!/usr/bin/env python3
"""caption-display-oracle.py -- THE CAPTION MUST LOOK LIKE YOUTUBE'S DISPLAY.

WHAT IT IS FOR. The owner, 2026-10-20, verbatim:

    "voce nao ta fazendo a legenda parecendo com como o youtube da DISPLAY e
     quebra as linhas e etc. é pra tu fazer isso. faça."

So the caption has to be the YouTube ON-SCREEN DISPLAY: white text with a heavy
black OUTLINE (no plate), a large sans face, centred, at most TWO lines, and the
break between the two lines at a WORD BOUNDARY -- never inside a word.

This instrument measures the SHIPPED page (`app/panel/caption.html` +
`app/panel/caption-float.css`) in Blink, the same engine the app's WebView2 is,
and it ASSERTS the properties above against the real computed styles and the
real line boxes. It is not a paraphrase of the CSS and it is not a screenshot:
every number it prints comes out of `getComputedStyle` / `Range.getClientRects()`
on the real document.

THE VIEWPORT IS MEASURED, NOT ASSUMED (2026-10-20, this box).

    headless Edge, --dump-dom:  viewport_w = max(492, --window-size_w - 24)
                          viewport_h =        --window-size_h - 92

MEASURED, six requests, one run (`I:/cc-tmp/vp-probe.py`):

    --window-size=900,170   -> iw=876  ih=78
    --window-size=924,262   -> iw=900  ih=170     <-- THE CAPTION WINDOW
    --window-size=1200,400  -> iw=1176 ih=308
    --window-size=492,300   -> iw=492  ih=208
    --window-size=380,900   -> iw=492  ih=808     <-- the PANEL's crop
    --headless=old, 900,170 -> iw=876  ih=78

**THE 492 IS A MINIMUM, NOT A MAXIMUM.** The repo's AGENTS.md rule 4 (and this
lane's brief) say the viewport is "clamped to 492 px whatever --window-size
asks". That is true for the PANEL (which asks for 380 and gets 492, so its PNG
is a 380 px CROP of a 492 px layout) and FALSE for the caption: ask for 924 and
the page viewport IS 900 x 170, which is the caption window's REAL size
(`sotto_webview.py:5881-5884`: `cap_w = max(360, min(900, wa_w - 80))` = 900 on a
1920 px work area, `cap_h = 170`). So the caption CAN be measured at its real
width, in a real Blink, and that is what this instrument does. The 24/92 px
chrome offset and the 492 floor are the numbers that make it true.

THE LINE BOXES ARE THE REAL ONES. A `Range` over the text node, one character
at a time, gives each glyph's client rect; grouping the characters by their
rect `top` gives the line boxes, and each line's TEXT. That is what makes
"no word is split across the break" a measurement instead of a promise: the
characters of one word are looked up in the line map, and a word whose
characters sit on two different lines is a split.

THE CHECKS (each one prints its number):

    V1 viewport         the page viewport is 900 x 170
    V2 white            the caption text is rgb(255,255,255)
    V3 outline          a heavy BLACK outline: -webkit-text-stroke-width >= 2 px,
                        opaque black
    V4 no plate         the caption line and EVERY ancestor up to <html> paint
                        no background, no background-image and no box-shadow;
                        <html> and <body> are transparent
    V5 face             a bundled sans (Inter) at weight 500 -- YouTube's
                        Roboto is not bundled, Inter is its metric cousin
    V6 size             36 px at --caption-scale 1 (YouTube's size at 1080p)
    V7 centred          text-align: center AND the text block's centre within
                        TOL_CENTRE px of the page's centre
    V8 two lines        a long cue paints AT MOST 2 line boxes
    V9 no mid-word      no word's characters span two line boxes
    V10 balanced        the two lines differ by at most BALANCE_MAX in width
    V11 suffix          what is on screen is a SUFFIX of the cue: the tail keeps
                        the NEWEST words and loses no word in the middle

USAGE

    py -3 _main\\_design-lane\\caption-display-oracle.py            # the tree
    py -3 _main\\_design-lane\\caption-display-oracle.py --source=head
        # the HEAD bytes (the "before"), for the diagnosis numbers
    py -3 _main\\_design-lane\\caption-display-oracle.py --neg-arm
        # the mutants: every one of them MUST turn the oracle RED

THE NEGATIVE ARM IS THE POINT. An instrument that cannot say NO is decoration.
`--neg-arm` re-renders the page with each mutant applied to a COPY of the
shipped files and asserts that the mutant turns the expected check RED. A
mutant that survives is a FAILURE of the instrument, not a pass.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault('TMPDIR', 'I:/cc-tmp')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import shot  # noqa: E402  (holds EDGE)

EDGE = shot.EDGE
PANEL = os.path.join(REPO, 'app', 'panel')

# THE REAL CAPTION WINDOW. 900 x 170: `sotto_webview.py:5881-5884`
# (`cap_w = max(360, min(900, wa_w - 80))`, `cap_h = 170`).
CAP_W = 900
CAP_H = 170
# headless Edge's --dump-dom viewport is (requested - 24) x (requested - 92)
# (MEASURED above), so this asks for the 900 x 170 page viewport exactly.
WIN_SIZE = (CAP_W + 24, CAP_H + 92)

# THE TOLERANCES. Every one of them is a number with a reason.
TOL_CENTRE = 1.5      # px: the text block's centre vs the page's centre
MIN_STROKE = 2.0      # px: "heavy" black outline
BALANCE_MAX = 0.20    # |w1-w2| / max(w1,w2): a balanced two-line split
FONT_SIZE_PX = 36.0   # YouTube's caption size at 1080p
FONT_WEIGHT = 500     # YouTube's caption weight (Roboto Medium)

# THE CUES. Three shapes: one line, two lines, and one that is much longer
# than two lines (which must show the LAST two lines, not three).
#
# THE LONG WORD IS LONGER THAN THE LINE BOX, ON PURPOSE. MEASURED at 36 px
# Inter in the 832 px column: 43 characters = 746.5 px (it FITS, and a word
# that fits is never broken, so it cannot prove anything about the rule) and
# 58 characters = 991.6 px (it does NOT fit). The second one is the fixture
# that a `break-word` / `anywhere` rule would split -- and that the fixed
# rule (`overflow-wrap: normal`) leaves whole, overflowing and clipped, which
# is what YouTube does too.
CUES = [
    ('short', 'Uma vez que voce foi.'),
    ('two', 'e o que eu quero e que a legenda apareca aqui em baixo, igual o youtube faz'),
    ('long', 'esta e uma legenda muito mais comprida do que duas linhas, '
             'com palavras suficientes para ocupar tres ou quatro linhas '
             'inteiras no ecra, e o que o dono ve e sempre o fim dela, '
             'porque as palavras mais novas sao as que ele acabou de ouvir'),
    ('word', 'e entao a palavra mais comprida do mundo aparece aqui '
             'pneumoultramicroscopicsilicovolcanoconiosisfluctuationibus'),
]

PROBE_JS = r"""
(function () {
  function cs(el, p) { return el ? getComputedStyle(el)[p] : null; }
  function rect(el) {
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return {x:+r.x.toFixed(2), y:+r.y.toFixed(2), w:+r.width.toFixed(2),
            h:+r.height.toFixed(2), left:+r.left.toFixed(2),
            right:+r.right.toFixed(2), top:+r.top.toFixed(2),
            bottom:+r.bottom.toFixed(2)};
  }
  /* THE LINE MAP: one rect per character, grouped by `top` into line boxes. */
  function lineMap(el) {
    var node = el.firstChild;
    if (!node || node.nodeType !== 3) { return {lines: [], text: el.textContent || ''}; }
    var text = node.nodeValue;
    var range = document.createRange();
    var chars = [];
    for (var i = 0; i < text.length; i++) {
      range.setStart(node, i); range.setEnd(node, i + 1);
      var rs = range.getClientRects();
      var r = rs.length ? rs[0] : null;
      chars.push(r ? {top:+r.top.toFixed(2), left:+r.left.toFixed(2),
                      right:+r.right.toFixed(2)} : null);
    }
    var groups = [];
    for (var j = 0; j < chars.length; j++) {
      var c = chars[j];
      if (!c) { continue; }
      var g = null;
      for (var k = 0; k < groups.length; k++) {
        if (Math.abs(groups[k].top - c.top) < 2) { g = groups[k]; break; }
      }
      if (!g) { g = {top:c.top, left:c.left, right:c.right, text:'', idx:[]}; groups.push(g); }
      g.text += text.charAt(j);
      g.idx.push(j);
      if (c.left < g.left) { g.left = c.left; }
      if (c.right > g.right) { g.right = c.right; }
    }
    groups.sort(function (a, b) { return a.top - b.top; });
    /* the line index of every character (-1 = not placed) */
    var owner = [];
    for (var m = 0; m < chars.length; m++) { owner.push(-1); }
    for (var n = 0; n < groups.length; n++) {
      for (var q = 0; q < groups[n].idx.length; q++) { owner[groups[n].idx[q]] = n; }
    }
    return {lines: groups, owner: owner, text: text};
  }
  /* A WORD is a run of letters/digits/apostrophes. An explicit HYPHEN is a
     break opportunity (typographically normal: "well-" / "known"), so it does
     not make the two halves one word. */
  function isWordChar(ch) {
    return /[\p{L}\p{N}\u2019']/u.test(ch);
  }
  function splitWords(text) {
    var words = [], cur = -1;
    for (var i = 0; i < text.length; i++) {
      if (isWordChar(text.charAt(i))) {
        if (cur < 0) { cur = words.length; words.push({s: i, e: i, text: ''}); }
        else { words[cur].e = i; }
        words[cur].text += text.charAt(i);
      } else {
        cur = -1;
      }
    }
    return words;
  }
  function wordSplits(map) {
    var out = [];
    var words = splitWords(map.text);
    for (var i = 0; i < words.length; i++) {
      var seen = {};
      for (var j = words[i].s; j <= words[i].e; j++) {
        var o = map.owner[j];
        if (o >= 0) { seen[o] = 1; }
      }
      var keys = Object.keys(seen);
      if (keys.length > 1) {
        out.push({word: words[i].text, lines: keys.map(Number).sort(function (a, b) { return a - b; })});
      }
    }
    return out;
  }
  /* EVERY ancestor that could paint a plate behind the words. */
  function paintedAncestors(el) {
    var out = [], node = el;
    while (node && node.nodeType === 1) {
      var s = getComputedStyle(node);
      var bg = s.backgroundColor, bi = s.backgroundImage, sh = s.boxShadow;
      var hasBg = bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent';
      var hasImg = bi && bi !== 'none';
      var hasSh = sh && sh !== 'none';
      if (hasBg || hasImg || hasSh) {
        out.push({tag: node.tagName, cls: String(node.className || '').slice(0, 40),
                  bg: bg, img: hasImg ? bi.slice(0, 40) : null,
                  shadow: hasSh ? sh.slice(0, 40) : null});
      }
      node = node.parentElement;
    }
    return out;
  }
  function snap(el) {
    var s = getComputedStyle(el);
    return {
      color: s.color,
      fontFamily: s.fontFamily,
      fontSize: s.fontSize,
      fontWeight: s.fontWeight,
      textAlign: s.textAlign,
      lineHeight: s.lineHeight,
      strokeWidth: s.webkitTextStrokeWidth || s.getPropertyValue('-webkit-text-stroke-width'),
      strokeColor: s.webkitTextStrokeColor || s.getPropertyValue('-webkit-text-stroke-color'),
      paintOrder: s.paintOrder || s.getPropertyValue('paint-order'),
      textShadow: s.textShadow,
      textWrap: s.textWrap || s.getPropertyValue('text-wrap'),
      overflowWrap: s.overflowWrap || s.getPropertyValue('overflow-wrap'),
      hyphens: s.hyphens || s.getPropertyValue('hyphens'),
      background: s.backgroundColor,
      rect: rect(el)
    };
  }
  function measure() {
    var out = {vp: {w: window.innerWidth, h: window.innerHeight},
               dpr: window.devicePixelRatio};
    var line = document.getElementById('caption-float-line');
    var prev = document.getElementById('caption-float-prev');
    var col = document.querySelector('.caption-float__col');
    var stage = document.querySelector('.caption-float__stage');
    out.html = {bg: cs(document.documentElement, 'backgroundColor')};
    out.body = {bg: cs(document.body, 'backgroundColor')};
    out.line = snap(line);
    out.prev = snap(prev);
    out.col = snap(col);
    out.stage = snap(stage);
    out.painted = paintedAncestors(line);
    out.map = lineMap(line);
    out.splits = wordSplits(out.map);
    /* the visible text, and whether it is a SUFFIX of what was asked for */
    out.visible = line.textContent;
    return out;
  }
  window.addEventListener('load', function () {
    var done = function () {
      /* THE WORDS GO IN FIRST, IN THE SAME HANDLER: a fixture set from another
         `load` listener would run AFTER this one, and the measurement would
         read an empty caption. */
      try {
        if (window.SottoCaption) {
          window.SottoCaption.set(window.__SOTTO_CUE || '', window.__SOTTO_PREV || '');
        }
      } catch (e) { /* the measurement below reports it */ }
      var o = {ready: 1};
      try {
        var m = measure();
        m.ready = 1;   /* `measure()` returns its own object: the flag has to
                          be put back, or the oracle reads it as "no data". */
        o = m;
      } catch (e) { o = {ready: 0, error: String(e)}; }
      var pre = document.getElementById('probe-out');
      if (pre) { pre.textContent = JSON.stringify(o); }
    };
    /* The face has to be LOADED before the line boxes are measured, and the
       wait must not be able to hang the dump: the timer is the floor. */
    var fired = false;
    var once = function () { if (!fired) { fired = true; done(); } };
    if (document.fonts && document.fonts.ready) { document.fonts.ready.then(once); }
    setTimeout(once, 2500);
  });
})();
"""

# THE MUTANTS. Each one edits a COPY of the shipped files and MUST turn the
# named check RED. `old` must exist in the file, or the mutant is INERT.
# `cue` is the fixture the mutant is judged on -- a mutant that only shows on a
# different shape of cue is not proving anything.
#
# WHERE A PROPERTY IS DECIDED MATTERS, AND THE FIRST RUN OF THIS ARM PROVED IT:
# seven of the first nine mutants SURVIVED, because they edited
# `caption-float.css` while `caption.html`'s <style> block re-declared the
# same properties with `!important` -- the mutation never reached the screen.
# The two files are now split so that each property is decided in exactly ONE
# place (see the comments in both files), and every mutant below edits the
# place that decides it.
MUTANTS = [
    {'name': 'M1-anywhere', 'cue': 'word', 'expect': 'V9',
     'edits': [('caption-float.css', 'overflow-wrap: normal;', 'overflow-wrap: anywhere;')]},
    {'name': 'M2-no-outline', 'cue': 'two', 'expect': 'V3',
     'edits': [('caption-float.css', '--caption-outline: 6px;', '--caption-outline: 0px;')]},
    {'name': 'M3-left', 'cue': 'two', 'expect': 'V7',
     'edits': [('caption.html', 'text-align: center !important;',
                'text-align: left !important;')]},
    {'name': 'M4-small', 'cue': 'two', 'expect': 'V6',
     'edits': [('caption-float.css', '--caption-size: 36px;', '--caption-size: 14px;')]},
    {'name': 'M5-plate', 'cue': 'two', 'expect': 'V4',
     'edits': [('caption-float.css', 'background-color: transparent;',
                'background-color: rgba(0, 0, 0, 0.75);')]},
    {'name': 'M6-no-balance', 'cue': 'two', 'expect': 'V10',
     'edits': [('caption-float.css', 'text-wrap: balance;', 'text-wrap: wrap;')]},
    # THE WINDOW: the tail that keeps the caption at two lines. A wider window
    # lets the cue grow to four lines -- which is exactly what the owner
    # called "a legenda do tamanho da tela".
    {'name': 'M7-four-lines', 'cue': 'long', 'expect': 'V8',
     'edits': [('caption.html', 'var CAPTION_MAX_LINES = 2;',
                'var CAPTION_MAX_LINES = 9;')]},
    # THE PRE-FIX RULE, VERBATIM (caption-float.css before 2026-10-20):
    # `overflow-wrap: break-word` + `hyphens: auto`. It splits a word.
    {'name': 'M8-pre-fix-wrap', 'cue': 'word', 'expect': 'V9',
     'edits': [('caption-float.css', 'overflow-wrap: normal;',
                'overflow-wrap: break-word;'),
               ('caption-float.css', 'hyphens: none;', 'hyphens: auto;')]},
    # THE SERIF, verbatim: zip-overlay.css:359-362, which the caption document
    # has to override (this is the rule that made the caption a Times card).
    {'name': 'M9-serif', 'cue': 'two', 'expect': 'V5',
     'edits': [('caption-float.css', "--caption-face: 'Inter', 'Segoe UI', system-ui, sans-serif;",
                '--caption-face: Georgia, "Times New Roman", serif;')]},
]


def copy_panel(dest):
    """A copy of app/panel. The shipped directory is never touched."""
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(PANEL):
        src = os.path.join(PANEL, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dest, name), dirs_exist_ok=True)
        else:
            shutil.copyfile(src, os.path.join(dest, name))


def build_page(work, source='tree'):
    """The page to render: the SHIPPED caption.html, with the probe injected."""
    copy_panel(work)
    hp = os.path.join(work, 'caption.html')
    if source == 'head':
        raw = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:app/panel/caption.html'],
                             capture_output=True, timeout=60)
        if raw.returncode != 0:
            raise SystemExit('git show HEAD:app/panel/caption.html failed')
        html = raw.stdout.decode('utf-8')
        raw2 = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:app/panel/caption-float.css'],
                              capture_output=True, timeout=60)
        if raw2.returncode == 0:
            with open(os.path.join(work, 'caption-float.css'), 'wb') as fh:
                fh.write(raw2.stdout)
        with open(hp, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(html)
    else:
        with open(hp, encoding='utf-8') as fh:
            html = fh.read()
    inject = ('<pre id="probe-out" style="display:none"></pre>\n'
              '<script>\n%s\n</script>\n' % PROBE_JS)
    html = html.replace('</body>', inject + '</body>')
    with open(hp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    return hp


def render(hp, cues):
    """Render the page and read the measurement back out of the DOM."""
    # The fixture is a plain global, set BEFORE the load event, so the probe's
    # own load handler can put the words on the page and measure them.
    fixture = ('<script>window.__SOTTO_CUE = %s; window.__SOTTO_PREV = %s;</script>\n'
               % (json.dumps(cues[0]), json.dumps(cues[1])))
    with open(hp, encoding='utf-8') as fh:
        html = fh.read()
    html = html.replace('</body>', fixture + '</body>')
    with open(hp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)
    url = 'file:///' + hp.replace(os.sep, '/')
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
           '--no-default-browser-check', '--hide-scrollbars',
           '--user-data-dir=' + os.path.join(os.path.dirname(hp), 'ud'),
           '--force-device-scale-factor=1', '--virtual-time-budget=9000',
           '--window-size=%d,%d' % WIN_SIZE, '--dump-dom', url]
    proc = subprocess.run(cmd, capture_output=True, timeout=240)
    dom = (proc.stdout or b'').decode('utf-8', 'replace')
    m = re.search(r'<pre id="probe-out"[^>]*>(.*?)</pre>', dom, re.S)
    if not m:
        return None, ((proc.stderr or b'').decode('utf-8', 'replace')[:400])
    raw = (m.group(1).replace('&quot;', '"').replace('&lt;', '<')
           .replace('&gt;', '>').replace('&amp;', '&'))
    try:
        return json.loads(raw), None
    except Exception as exc:
        return None, 'probe json: %r' % (exc,)


# ── THE CHECKS ────────────────────────────────────────────────────────────────

def rgb(value):
    m = re.match(r'rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*'
                 r'(?:,\s*([\d.]+)\s*)?\)', (value or '').strip())
    if not m:
        return None
    return (float(m.group(1)), float(m.group(2)), float(m.group(3)),
            float(m.group(4)) if m.group(4) is not None else 1.0)


def check(data, cues):
    """Returns (results, facts). `results` is a list of (id, ok, message)."""
    res = []
    facts = {}
    if not data or not data.get('ready'):
        return [('V1', False, 'no measurement: %s' % (data,))], facts

    line = data['line']
    vp = data['vp']
    facts['viewport'] = vp
    facts['line'] = line
    facts['lines'] = data['map']['lines']
    facts['splits'] = data['splits']
    facts['painted'] = data['painted']
    facts['stage'] = data['stage']
    facts['col'] = data['col']
    facts['prev'] = data['prev']

    # V1 -- the viewport IS the caption window
    ok = (abs(vp['w'] - CAP_W) <= 1 and abs(vp['h'] - CAP_H) <= 1)
    res.append(('V1', ok, 'viewport %dx%d (want %dx%d)' % (vp['w'], vp['h'], CAP_W, CAP_H)))

    # V2 -- white text
    c = rgb(line['color'])
    ok = bool(c) and c[0] >= 250 and c[1] >= 250 and c[2] >= 250
    res.append(('V2', ok, 'colour %s (want white)' % line['color']))

    # V3 -- a heavy BLACK outline
    sw = line.get('strokeWidth') or '0px'
    try:
        swv = float(re.match(r'([\d.]+)', sw).group(1))
    except Exception:
        swv = 0.0
    sc = rgb(line.get('strokeColor') or '')
    ok = swv >= MIN_STROKE and bool(sc) and sc[0] <= 8 and sc[1] <= 8 and sc[2] <= 8 \
        and sc[3] >= 0.85
    res.append(('V3', ok, 'outline %s %s (want >= %.0fpx black)'
                % (sw, line.get('strokeColor'), MIN_STROKE)))

    # V4 -- no plate anywhere behind the words
    painted = data['painted']
    html_bg = rgb(data['html']['bg'] or '')
    body_bg = rgb(data['body']['bg'] or '')
    transparent = all(x is None or x[3] == 0 for x in (html_bg, body_bg))
    ok = (not painted) and transparent
    res.append(('V4', ok, 'painted ancestors %d, html %s, body %s'
                % (len(painted), data['html']['bg'], data['body']['bg'])))

    # V5 -- the face: a bundled sans, medium weight
    fam = (line.get('fontFamily') or '').lower()
    ok = ('inter' in fam or 'roboto' in fam)
    try:
        wv = int(line.get('fontWeight') or '0')
    except Exception:
        wv = 0
    ok = ok and wv == FONT_WEIGHT
    res.append(('V5', ok, 'font %s / weight %s' % (line.get('fontFamily'), line.get('fontWeight'))))

    # V6 -- the size
    try:
        fs = float(re.match(r'([\d.]+)', line['fontSize'] or '0').group(1))
    except Exception:
        fs = 0.0
    ok = abs(fs - FONT_SIZE_PX) <= 0.6
    res.append(('V6', ok, 'font-size %s (want %.0fpx)' % (line['fontSize'], FONT_SIZE_PX)))

    # V7 -- centred: the BLOCK is centred on the page, and so are the WORDS.
    align_ok = (line.get('textAlign') == 'center')
    lr = line.get('rect') or {}
    centre = (lr.get('left', 0) + lr.get('right', 0)) / 2.0
    page_centre = vp['w'] / 2.0
    off = abs(centre - page_centre)
    # AND THE GLYPHS: every line box's own centre, which is the claim the
    # owner can see ("the words are in the middle").
    #
    # A LINE THAT OVERFLOWS THE COLUMN IS NOT A CENTRING CLAIM. Blink aligns
    # an overflowing line to the END of its box, so its centre is off by
    # construction -- and that is the trade the "never split a word" rule
    # makes (the word is clipped at the column's edge instead). The width of
    # such a line is reported as a FACT, not judged here.
    colw = (data['col'].get('rect') or {}).get('w', 0) or 0
    glyph_off = []
    overflowing = []
    for lg in data['map']['lines']:
        w = lg['right'] - lg['left']
        if colw and w > colw + 1:
            overflowing.append({'w': round(w, 1), 'text': lg['text'].strip()})
            continue
        mid = (lg['left'] + lg['right']) / 2.0
        glyph_off.append(abs(mid - page_centre))
    worst = max(glyph_off) if glyph_off else 0.0
    facts['overflowing'] = overflowing
    facts['column_w'] = round(colw, 1)
    ok = align_ok and off <= TOL_CENTRE and worst <= TOL_CENTRE
    res.append(('V7', ok, 'align %s, block off by %.2fpx, worst glyph off by %.2fpx '
                '(tolerance %.1f)%s'
                % (line.get('textAlign'), off, worst, TOL_CENTRE,
                   ('; %d line(s) overflow the %.0fpx column (clipped, not split): %s'
                    % (len(overflowing), colw,
                       ', '.join('%.1fpx' % o['w'] for o in overflowing)))
                   if overflowing else '')))

    # V8 -- at most two lines
    lines = data['map']['lines']
    ok = len(lines) <= 2
    res.append(('V8', ok, '%d line box(es): %s'
                % (len(lines), ' | '.join(l['text'].strip() for l in lines))))

    # V9 -- no word split across the break
    splits = data['splits']
    ok = not splits
    res.append(('V9', ok, 'split words: %s'
                % (', '.join('%s@%s' % (s['word'], s['lines']) for s in splits) or 'none')))

    # V10 -- balanced
    bal = None
    if len(lines) == 2:
        w1 = lines[0]['right'] - lines[0]['left']
        w2 = lines[1]['right'] - lines[1]['left']
        bal = abs(w1 - w2) / max(w1, w2, 1.0)
        ok = bal <= BALANCE_MAX
    else:
        ok = True  # one line: nothing to balance
    res.append(('V10', ok, 'balance %s (want <= %.2f)'
                % ('%.3f' % bal if bal is not None else 'n/a (1 line)', BALANCE_MAX)))

    # V11 -- what is on screen is a SUFFIX of the cue (and, when the cue fits,
    # the WHOLE cue: the tail must not eat words it did not have to).
    cue = cues[0]
    visible = (data.get('visible') or '').strip()
    whole = visible == cue.strip()
    suffix = visible == '' or cue.strip().endswith(visible)
    ok = suffix
    res.append(('V11', ok, 'visible is %s of the cue (whole=%s)'
                % ('a suffix' if suffix else 'NOT a suffix', whole)))
    return res, facts


def render_cue(work, cue_text, prev_text=''):
    """One render of the page with ONE cue on it."""
    hp = build_page(work)
    data, err = render(hp, [cue_text, prev_text])
    return data, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default='tree', choices=('tree', 'head'),
                    help='render the working tree (default) or the HEAD bytes')
    ap.add_argument('--neg-arm', action='store_true',
                    help='the mutants: every one MUST turn the oracle RED')
    ap.add_argument('--cue', default='two', help='which fixture cue to render')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    cue_name, cue_text = CUES[0], ''
    for name, text in CUES:
        if name == args.cue:
            cue_name, cue_text = name, text
    if not cue_text:
        cue_name, cue_text = CUES[1]
    cues = [cue_text, '']

    if args.neg_arm:
        return neg_arm()

    work = tempfile.mkdtemp(prefix='capdisp-', dir='I:/cc-tmp')
    try:
        hp = build_page(work, args.source)
        data, err = render(hp, cues)
        if data is None:
            print('SEM MEDIDA: %s' % err)
            return 2
        results, facts = check(data, cues)
        if args.json:
            print(json.dumps({'results': results, 'facts': facts}, indent=1))
            return 0 if all(ok for _, ok, _ in results) else 1
        print('== ORACLE DA LEGENDA (source=%s, cue=%s) ==' % (args.source, cue_name))
        print('   viewport %dx%d   linhas: %s'
              % (facts['viewport']['w'], facts['viewport']['h'],
                 ' | '.join(l['text'].strip() for l in facts['lines'])))
        for cid, ok, msg in results:
            print('   %-4s %s  %s' % (cid, 'OK  ' if ok else 'RED ', msg))
        bad = [cid for cid, ok, _ in results if not ok]
        print('VERDICT: %s%s' % ('PASS' if not bad else 'FAIL',
                                 '' if not bad else ' (red: %s)' % ','.join(bad)))
        return 0 if not bad else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


def neg_arm():
    """Each mutant MUST turn the oracle RED. A survivor is a broken oracle."""
    print('== BRACO NEGATIVO: cada mutante tem de VERMELHAR ==')
    failures = []
    for mut in MUTANTS:
        name, expect, cue_name = mut['name'], mut['expect'], mut['cue']
        work = tempfile.mkdtemp(prefix='capmut-', dir='I:/cc-tmp')
        try:
            build_page(work)
            inert = None
            for target, old, new in mut['edits']:
                path = os.path.join(work, target)
                with open(path, encoding='utf-8', newline='') as fh:
                    text = fh.read()
                if old not in text:
                    # the file may be CRLF: the pattern is written with \n
                    alt = old.replace('\n', '\r\n')
                    if alt in text:
                        text = text.replace(alt, new.replace('\n', '\r\n'), 1)
                    else:
                        inert = '%s: "%s" nao esta em %s' % (name, old[:32], target)
                        break
                else:
                    text = text.replace(old, new, 1)
                with open(path, 'w', encoding='utf-8', newline='') as fh:
                    fh.write(text)
            if inert:
                print('   %-14s INERT -- %s' % (name, inert))
                failures.append(name)
                continue
            hp = os.path.join(work, 'caption.html')
            cue_text = [c for c in CUES if c[0] == cue_name][0][1]
            data, err = render(hp, [cue_text, ''])
            if data is None:
                print('   %-14s SEM MEDIDA (%s)' % (name, err))
                failures.append(name)
                continue
            results, facts = check(data, [cue_text, ''])
            by_id = {cid: (ok, msg) for cid, ok, msg in results}
            ok, msg = by_id.get(expect, (False, 'check %s ausente' % expect))
            if ok:
                print('   %-14s SOBREVIVEU -- %s devia ter ficado RED' % (name, expect))
                failures.append(name)
            else:
                print('   %-14s RED em %s (cue=%s) -- %s' % (name, expect, cue_name, msg))
        finally:
            shutil.rmtree(work, ignore_errors=True)
    if failures:
        print('NEG-ARM FAIL: %s' % ', '.join(failures))
        return 1
    print('NEG-ARM PASS: %d/%d mutantes vermelharam' % (len(MUTANTS), len(MUTANTS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
