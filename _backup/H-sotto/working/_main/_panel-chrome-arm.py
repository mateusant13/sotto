#!/usr/bin/env python3
"""Prove that each of the five directions has its OWN face in the real panel.

WHAT THIS MEASURES, and why a grep is not enough. The owner's request changed the
contract: a theme no longer re-skins colour, type and surface over ONE shared
header and footer — *"quero que voce monte o painel super parecido com cada tema.
pode ate mudar botoes de lugar, se quiser. nao quero a cara do design que tinhamos
antes."* So the claim is: per direction, the header line, the footer line, the
state indicator, the control placement and the direction's own behaviour are
really on screen, and the theme button is still reachable on BOTH surfaces.

This runner writes a COPY of the REAL `app/panel/panel.html` (asset URLs pointed at
the real files, the audit stub bridge inserted before `panel.js`), appends
`_main/_panel-chrome-probe.js` after it, loads the copy in Chromium
(`--headless=new`, the same engine class the app runs in WebView2), and reads the
payload the probe leaves in the DOM. The probe drives the REAL `panel.js` with a
worker-shaped caption stream, so the per-line ordinal, the per-word ramp spans and
the `inst` LED are the ones the shipped renderer produced.

THE CONTROLS (both colours in ONE command, `--neg-arm`). Two copies, each with ONE
half of the mechanism reverted:
  * `markup` — the chrome blocks' class contract is renamed (`chrome` →
    `chrome-off`), so the markup is inert;
  * `css`    — the five theme stylesheets stop naming the chrome blocks
    (`.chrome--` → `.chrome-off--`), so the CSS is inert.
An instrument that cannot say no is not an instrument, and these two say WHICH half
stopped working.

Usage:
  py -3 _main\\_panel-chrome-arm.py               # the real files
  py -3 _main\\_panel-chrome-arm.py --neg-arm     # + both controls, must go RED
"""

import argparse
import html as html_mod
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir))
PANEL = os.path.join(REPO, 'app', 'panel')
OUTDIR = os.path.join(HERE, '_audit-render')
REL = '../../app/panel/'

# The console on this box is cp1252 and every direction's own labels are UTF-8
# (`▲ EM CURSO`, `· · ·`, `— escrito ao ouvido`). Without this the run dies on its
# own output, which is a failure mode worth naming: an instrument that cannot
# print what it measured is not an instrument.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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

# The five directions as the owner's `designs.ts` declares them and as the
# shipped manifest repeats them. THE EXPECTED SIDE of every comparison.
EXPECTED = {
    # `wordmark` is the name `sotto` as THIS direction paints it. theme-1's name is
    # its wordmark; the other four carry `.chrome__brand` in their own header line.
    # LOWERCASE EVERYWHERE — the owner wrote it that way and `text-transform` used
    # to overrule him on two of the five.
    'theme-1': dict(id='tele', label='Teleprompter', family='Barlow Condensed',
                    head_word='LENDO', state_word='LENDO', wordmark='sotto',
                    foot_start='HISTÓRICO', foot_end='▲ EM CURSO',
                    index=False, led=False, meter=False, ramp=False, fog=False),
    'theme-2': dict(id='bcast', label='Broadcast', family='IBM Plex Mono',
                    head_word='REC', state_word='REC', wordmark=None,
                    foot_start=None, foot_end='LIVE',
                    index=True, led=False, meter=True, ramp=False, fog=False),
    'theme-3': dict(id='mano', label='Manuscrito', family='Newsreader',
                    head_word='rascunho live', state_word=None, wordmark=None,
                    foot_start='— escrito ao ouvido', foot_end=None,
                    index=False, led=False, meter=False, ramp=True, fog=False),
    'theme-4': dict(id='cine', label='Cinema Card', family='Fraunces',
                    head_word='sotto', state_word='· live ·', wordmark=None,
                    foot_start='· · ·', foot_end=None,
                    index=False, led=False, meter=False, ramp=False, fog=True),
    'theme-5': dict(id='inst', label='Instrumento', family='Space Grotesk',
                    head_word='ON', state_word='ON', wordmark=None,
                    foot_start=None, foot_end='OUVINDO',
                    index=False, led=True, meter=True, ramp=False, fog=False),
}

# The mockups' own invented readings. `designs.ts` drives `CONF 0.93` and
# `panels.tsx` randomises a buffer from a SIMULATED script; this panel has no such
# measurement, so its chrome must not print one. Checked as a string absence.
FORBIDDEN_TEXT = ('CONF', '48K', '380×900', '380x900', 'buffer', '0.93', 'PT-BR · 48')


def find_browser(which):
    cands = CHROME_CANDIDATES if which == 'chrome' else EDGE_CANDIDATES
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit('no browser found in %r' % cands)


def build_copy(arm, control):
    """Write the arm's copy of `panel.html`. Returns its path."""
    with open(os.path.join(PANEL, 'panel.html'), encoding='utf-8') as fh:
        src = fh.read()

    for asset in ASSETS:
        if '"%s"' % asset not in src:
            raise SystemExit('panel.html no longer references %r' % asset)
        src = src.replace('"%s"' % asset, '"%s%s"' % (REL, asset))

    marker = '<script src="%ssurface.js"></script>' % REL
    assert marker in src, 'surface.js tag not found'
    # The probe goes in BEFORE `panel.js` on purpose: it captures the panel's own
    # `onStatus` subscription on the way past (see the probe's header), which is
    # how the panel is later handed the REAL shell payload shape
    # (`{text, kind:'live'}`) instead of the stub's bare string. It waits for
    # `load` before it measures anything.
    src = src.replace(marker,
                      '<script src="stub.js"></script>\n'
                      '    <script src="../_panel-chrome-probe.js"></script>\n    ' + marker)

    if control == 'markup':
        # The markup half reverted: the class contract the five stylesheets key
        # on is renamed, so every chrome block stays `display: none`.
        src = src.replace('class="chrome', 'class="chrome-off')

    out = os.path.join(OUTDIR, 'panel-chrome-%s.html' % arm)
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)
    return out


def build_css_control(arm):
    """Write the five theme stylesheets with the chrome CSS half reverted.

    Returns the directory the copy's `panel.html` must be pointed at — the copy
    lives in `_audit-render/chrome-css-<arm>/` with `themes/` beside it, and the
    five files are the real ones with `.chrome--` renamed.
    """
    base = os.path.join(OUTDIR, 'chrome-css-%s' % arm)
    themes = os.path.join(base, 'themes')
    os.makedirs(themes, exist_ok=True)
    for n in range(1, 6):
        with open(os.path.join(PANEL, 'themes', 'theme-%d.css' % n), encoding='utf-8') as fh:
            text = fh.read()
        text = text.replace('.chrome--', '.chrome-off--')
        with open(os.path.join(themes, 'theme-%d.css' % n), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    return base


def build_frame(page_name, width=380, height=900):
    """A 380x900 frame around the arm copy.

    WHY THE MEASUREMENT IS NOT TAKEN IN A FULL-BROWSER WINDOW: the real panel is
    **380x900** — the shell's own `PANEL_WIDTH`/`PANEL_HEIGHT` at 96 dpi — and a
    measurement at `innerWidth=756` describes a layout the owner never sees. It
    is not a cosmetic difference: the header is a flex row, so at 756 px the
    controls and the direction's own line both fit, while at 380 px the same row
    is 350 px and a `flex: 1` item with `flex-basis: 0` can be squeezed to ZERO
    width. That is exactly how the `cine` header was caught here after being
    reported on screen. The frame reproduces the real geometry, and the probe
    asserts `innerWidth === 380` from inside it.
    """
    out = os.path.join(OUTDIR, 'panel-chrome-frame.html')
    doc = """<!doctype html>
<html><head><meta charset="utf-8"><title>Sotto panel arm frame</title>
<style>
  html,body{margin:0;padding:0;background:#000}
  iframe{width:%dpx;height:%dpx;border:0;display:block}
</style></head><body>
<iframe id="arm" src="%s#mode=chrome"></iframe>
<script>
/* THE MIRROR. The payload is written INSIDE the frame (that is where the panel
   lives, at its real 380 px width), and a `file://` iframe is a cross-origin
   frame, so the outer `--dump-dom` cannot see it. With
   `--allow-file-access-from-files` this poll can read it and copy the attributes
   onto a node of the OUTER document, which is the document the dump captures.
   It polls rather than firing once, because the probe finishes on its own
   schedule; it gives up after ~25 s and says so in the title instead of
   reporting a false absence. */
(function () {
  var tries = 0;
  var timer = setInterval(function () {
    tries += 1;
    var frame = document.getElementById('arm');
    var inner = null;
    try { inner = frame.contentDocument; } catch (e) {
      document.title = 'mirror blocked: ' + e.message;
      clearInterval(timer);
      return;
    }
    var src = inner && inner.getElementById('__chrome_probe');
    var done = src && (src.hasAttribute('data-chrome-probe-1') || src.hasAttribute('data-chrome-probe-errors'));
    if (done) {
      var mine = document.createElement('div');
      mine.id = '__chrome_probe';
      for (var i = 0; i < src.attributes.length; i += 1) {
        mine.setAttribute(src.attributes[i].name, src.attributes[i].value);
      }
      document.body.appendChild(mine);
      document.title = 'mirrored';
      clearInterval(timer);
      return;
    }
    if (tries > 125) {
      document.title = 'mirror timed out; probe payload ' + (src ? 'partial' : 'absent');
      clearInterval(timer);
    }
  }, 200);
}());
</script>
</body></html>
""" % (width, height, page_name)
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(doc)
    return out


def load_report(browser, page, wait_ms, motion=False):
    prof = os.path.join(os.environ.get('TEMP', '.'),
                        'sotto-chrome-probe-prof-%s' % ('motion' if motion else 'reduce'))
    shutil.rmtree(prof, ignore_errors=True)
    cmd = [browser, '--headless=new', '--disable-gpu', '--no-first-run',
           '--user-data-dir=' + prof,
           # THE REAL PANEL GEOMETRY. The shell's own `PANEL_WIDTH`/`PANEL_HEIGHT`
           # at 96 dpi is 380x900. `--window-size=380,900` was tried FIRST and is
           # NOT enough: measured, it leaves `innerWidth=492` (this box's headless
           # Chromium clamps the window), and the probe asserts `innerWidth === 380`
           # from inside the page, so the wrong geometry is caught rather than
           # quietly measured. The frame below reproduces it exactly, and
           # `--allow-file-access-from-files` is what lets the frame's mirror read
           # the payload out of the cross-origin `file://` iframe.
           '--window-size=380,900',
           '--allow-file-access-from-files',
           '--virtual-time-budget=%d' % wait_ms]
    if motion:
        # ── THE MOTION ARM, AND WHY IT NEEDS A FLAG ──────────────────────────
        # THIS BOX HAS WINDOWS ANIMATIONS DISABLED, measured directly:
        # `SystemParametersInfo(SPI_GETCLIENTAREAANIMATION)` returns **false**
        # (`_main/_panel-motion-env.txt`). Chromium derives
        # `prefers-reduced-motion` from exactly that API on Windows, and headless
        # Chromium agrees: `matchMedia('(prefers-reduced-motion: reduce)').matches
        # === true` with no flags. So the default arm measures the REDUCED path —
        # which is the path the owner's own app is on — and the animations can
        # only be seen by asking Blink for the other answer:
        # `--blink-settings=prefersReducedMotion=false`. It is an EMULATION of a
        # box with animations on, and it is labelled as one wherever its numbers
        # are quoted. Nothing here changes the machine's setting.
        cmd.append('--blink-settings=prefersReducedMotion=false')
    cmd += ['--dump-dom', 'file:///' + page.replace('\\', '/') + '#mode=chrome']
    proc = subprocess.run(cmd, capture_output=True, encoding='utf-8',
                          errors='replace', timeout=240)
    return proc.stdout or ''


def parse_report(dom):
    """Pull the probe payload out of the dumped DOM."""
    m = re.search(r'data-chrome-probe-errors="([^"]*)"', dom)
    errors = json.loads(html_mod.unescape(m.group(1))) if m else None
    m = re.search(r'data-chrome-probe-surface="([^"]*)"', dom)
    surface = json.loads(html_mod.unescape(m.group(1))) if m else None
    themes = []
    for mm in re.finditer(r'data-chrome-probe-(\d+)="([^"]*)"', dom):
        themes.append(json.loads(html_mod.unescape(mm.group(2))))
    return errors, surface, themes


def check_theme(t, exp, problems, motion):
    def bad(msg):
        problems.append('%s(%s): %s' % (exp['id'], t.get('theme'), msg))

    # ── A1: THE HUD IS GONE, and it left no CSS behind ──────────────────────
    if t.get('hudPresent'):
        bad('the HUD element is still in the document')
    if t.get('hudStyles'):
        bad('%r .hud* elements are still on screen' % t.get('hudStyles'))
    # ── A3: THE SHORTCUT IS NOT ADVERTISED (and still works: this is the copy) ──
    if t.get('shortcutMentions'):
        bad('the panel still names the shortcut: %r' % t.get('shortcutMentions'))
    # ── A2: EVERY CONTROL OF THE PANEL IS ON THE TOP ROW ────────────────────
    # The CLUSTER is `.panel__controls` (Clear, Quit, Hide, Pause + the theme
    # button). The transcript drawer's own tools are a different thing and stay
    # in the drawer; the probe reports both and only the cluster is asserted.
    if t.get('clusterCount', 0) < 5:
        bad('the control cluster has %r button(s); Clear/Quit/Hide/Pause and the '
            'theme button are expected' % t.get('clusterCount'))
    if t.get('clusterInHeader') != t.get('clusterCount'):
        bad('%r of %r cluster controls are OUTSIDE the header — the owner asked for '
            'all of them at the top'
            % (t.get('clusterCount', 0) - t.get('clusterInHeader', 0), t.get('clusterCount')))
    if t.get('clusterOffRow'):
        bad('%r cluster control(s) sit below the header\'s first row: %r'
            % (t.get('clusterOffRow'),
               [b for b in (t.get('buttons') or []) if b.get('inCluster')]))
    # ── F: THE DRAG REGION, both halves, in every direction ─────────────────
    if t.get('headerAppRegion') != 'drag':
        bad('the header is not a drag region (computed -webkit-app-region=%r)'
            % t.get('headerAppRegion'))
    if t.get('clusterNoDrag') != t.get('clusterCount'):
        bad('%r of %r cluster controls are NOT `no-drag`: inside a drag region they '
            'would stop being clickable'
            % (t.get('clusterCount', 0) - t.get('clusterNoDrag', 0), t.get('clusterCount')))
    # ── E: THE LINE'S CLOCK, YELLOW WHILE LIVE AND GREY ONCE PAST ───────────
    live, past = t.get('liveTimeRgb'), t.get('pastTimeRgb')
    if not t.get('liveTimeShown'):
        bad('the live line carries no timecode')
    if not t.get('pastTimeShown'):
        bad('a closed line carries no timecode')
    if live:
        if not (live[0] > 200 and live[1] > 160 and live[2] < 140):
            bad('the LIVE timecode is %r, which is not yellow' % (t.get('liveTimeColor'),))
    if past and live:
        # "GREY" is read as the owner means it: DIMMED AND DESATURATED RELATIVE TO
        # THE LIVE ONE. A strict r==g==b test would fail `theme-4`, whose whole
        # palette is warm and whose own muted grey is `#A4947F`; what the owner is
        # asking for is that the eye can tell the current line from the ones left
        # behind, and that is what is asserted.
        lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        if lum(past) >= lum(live) * 0.9:
            bad('a PAST timecode (%r) is not dimmer than the live one (%r)'
                % (t.get('pastTimeColor'), t.get('liveTimeColor')))
        if past[0] > 200 and past[1] > 160 and past[2] < 140:
            bad('a PAST timecode (%r) is painted YELLOW — the yellow belongs to the '
                'current line only' % (t.get('pastTimeColor'),))
    if live and past and live == past:
        bad('the live and the past timecodes paint the SAME colour (%r): the owner '
            'asked for yellow on the current line and grey on the ones left behind'
            % (t.get('liveTimeColor'),))
    # ── B: TRANSPARENCY, measured as alpha ─────────────────────────────────
    for name in ('alphaPanel', 'alphaCaptions', 'alphaBody', 'alphaCaption'):
        a = t.get(name)
        if a is None:
            # `alpha()` returns None when the computed colour is not an `rgb()`
            # string at all (Chromium now emits `color(srgb …)` for some values).
            # "No colour I can parse" is reported, not silently passed.
            bad('%s could not be read (raw=%r)' % (name, t.get(name.replace('alpha', 'bg'))))
        elif a >= 1:
            bad('%s = %r: an OPAQUE background (the owner asked for transparency)' % (name, a))
    # ── THE LEVEL BARS: mounted, and NOT moving without a measurement ───────
    if exp['meter']:
        if not t.get('meterShown'):
            bad('the level bars are not on screen')
        if str(t.get('meterAnimation') or 'none') != 'none':
            bad('the level bars still ANIMATE (%r). The keyframe loop was a lie: it '
                'moved the same with speech, with silence and with a dead worker'
                % t.get('meterAnimation'))
        if t.get('levelAttr') != 'none':
            bad('body[data-level]=%r with no stats feed; it must say "none"'
                % t.get('levelAttr'))
    elif t.get('meterShown'):
        bad('this direction must not carry level bars')

    # ── THE GEOMETRY: 380 px is the panel the owner sees (the shell's own
    #    PANEL_WIDTH at 96 dpi). A narrower frame would describe another layout.
    if t.get('innerWidth') is not None and t['innerWidth'] != 380:
        bad('measured at innerWidth=%r, not the real panel width 380' % t.get('innerWidth'))
    if t.get('headShown') and t.get('headRect') and t['headRect'][2] <= 0:
        bad('its own header line has ZERO width (flex %r, header %r px, controls %r px)'
            % (t.get('headFlex'), t.get('headerWidth'), t.get('controlsWidth')))

    if not t.get('headShown'):
        bad('its own header line is NOT on screen (display/box)')
    if t.get('headCount') != 1:
        bad('expected exactly ONE header block for this direction, found %r' % t.get('headCount'))
    if t.get('shownHeads') != [exp['id']]:
        bad('shown header blocks = %r, expected exactly [%r]' % (t.get('shownHeads'), exp['id']))
    if not t.get('headHasExpectedWord'):
        bad('header text %r does not carry %r' % (t.get('headText'), exp['head_word']))
    if t.get('headFamily') != exp['family']:
        bad('header paints %r, expected the direction family %r' % (t.get('headFamily'), exp['family']))
    if exp['state_word'] is not None and t.get('stateWordShown') != exp['state_word']:
        bad('state word is %r, expected %r while captions are live'
            % (t.get('stateWordShown'), exp['state_word']))
    if exp['state_word'] is None and t.get('stateWordShown') is not None:
        bad('this direction has no state word, but %r is on screen' % t.get('stateWordShown'))
    if exp['wordmark'] is not None:
        if not t.get('wordmarkShown'):
            bad('the wordmark (which carries %r for this direction) is not on screen'
                % exp['wordmark'])
        elif exp['wordmark'].lower() not in (t.get('wordmarkText') or '').lower():
            bad('the wordmark reads %r, expected %r' % (t.get('wordmarkText'), exp['wordmark']))
    elif t.get('wordmarkShown'):
        bad('this direction replaces the wordmark with its own line, but the wordmark is '
            'on screen (%r)' % t.get('wordmarkText'))

    if exp['foot_start'] is not None:
        if not t.get('footStartShown'):
            bad('its own footer label is NOT on screen')
        elif exp['foot_start'] not in (t.get('footStartText') or ''):
            bad('footer label is %r, expected %r' % (t.get('footStartText'), exp['foot_start']))
    if exp['foot_end'] is not None:
        if not t.get('footEndShown'):
            bad('its own footer state label is NOT on screen')
        elif not t.get('footEndHasExpectedWord'):
            bad('footer state label is %r, expected %r' % (t.get('footEndText'), exp['foot_end']))

    if not t.get('controlsShown'):
        bad('the control cluster (with the theme button in it) is NOT on screen')
    if t.get('controlsOverlapsStatus'):
        bad('the control cluster OVERLAPS the status text (rects %r / %r)'
            % (t.get('controlsRect'), t.get('statusTextRect')))
    if t.get('controlsOverlapsHud'):
        bad('the control cluster OVERLAPS the HUD action row (rects %r / %r)'
            % (t.get('controlsRect'), t.get('hudActionsRect')))
    if not t.get('themeButtonShown'):
        bad('the theme button is not reachable on the panel surface')
    # ── THE CLIPPED LABEL (measured by the renderer lane, fixed in panel.css) ──
    # `clientWidth=26` against `scrollWidth=36-43` in all five themes painted the
    # owner's own control as `oadca`/`nuscr`/`ema C`/`rume`/`epromp`. The fix is
    # proven HERE, per theme, as the box against its own content.
    cw, sw = t.get('themeButtonClientWidth'), t.get('themeButtonScrollWidth')
    if cw is None or sw is None:
        bad('the theme button carries no measurable box (%r / %r)' % (cw, sw))
    elif sw > cw + 1:
        bad('THE THEME LABEL IS CLIPPED: clientWidth=%s < scrollWidth=%s'
            % (cw, sw))
    label = str(t.get('themeButtonLabel') or '')
    if label.strip().lower() != exp['label'].lower():
        bad('the theme button reads %r, expected the theme name %r'
            % (label, exp['label']))

    # ── THE ORDINAL IS NOT PAINTED (owner, 2026-10-08) ─────────────────────────
    # This block asserted the OPPOSITE until today: "the per-line ORDINAL is shown
    # on the forming row" plus a `\d{3,}` match on the painted element. The owner
    # had it removed TWICE — *"tira esse numero de 033 11:21:03"*, then *"to falando
    # desse numero a esquerda. o vermelho. nao é pra ter mais ele"* — so the claim
    # INVERTS, and that is exactly where an oracle starts lying: "the element is
    # absent" is ALSO TRUE when the entire caption line has vanished. THE PAIR IS
    # THE PROOF, and it is the owner's own pair: the ordinal must be absent from
    # the paint AND the clock must still be there, on a committed row and on the
    # forming one, with the forming row's clock a DIFFERENT colour (yellow against
    # grey in his screenshot). The ordinal itself must survive as STATE, which is
    # what `rowOrdinals` reads from `data-index`.
    if exp['index']:
        if t.get('paintedIndexCount'):
            bad('the per-line ORDINAL IS STILL PAINTED: %d element(s) %r'
                % (t['paintedIndexCount'], t.get('paintedIndexTexts')))
        # THE STATE HALF, READ FROM `data-index` AND NOT FROM THE PAINT. The first
        # version of this assertion reused `indexShown`, which the probe computes
        # from the `.caption__index` ELEMENT — so after the element was removed it
        # could never be true, and the oracle would have demanded the very thing the
        # owner had deleted. The ordinal's survival is a claim about `data-index`.
        rows_state = [x for x in (t.get('rowOrdinals') or []) if str(x).isdigit()]
        if not rows_state:
            bad('the ordinal left the paint, but it must survive as STATE: no row '
                'in the box carries a numeric data-index (%r)' % (t.get('rowOrdinals'),))
        for name in ('committedTimeText', 'formingTimeText'):
            v = t.get(name)
            if not (isinstance(v, str) and re.fullmatch(r'\d{2}:\d{2}:\d{2}', v)):
                bad('%s = %r, expected an HH:MM:SS clock beside the missing ordinal'
                    % (name, v))
        if not t.get('timesDiffer'):
            bad("the forming row's clock is the SAME colour as the committed row's "
                '(%r) — the owner\'s yellow-against-grey pair is gone'
                % t.get('formingTimeColor'))
        # MONOTONIC ACROSS THE WHOLE BOX: trimming `MAX_CAPTIONS` must never
        # renumber what was said, so the ordinals of the rows on screen must rise.
        rows = [int(x) for x in (t.get('rowOrdinals') or []) if str(x).isdigit()]
        if len(rows) >= 2 and any(rows[k] <= rows[k - 1] for k in range(1, len(rows))):
            bad('the ordinals on screen are not strictly increasing: %r' % rows)
    elif t.get('paintedIndexCount'):
        bad('the per-line ordinal is PAINTED, but this direction does not print one')

    # ── THE NAME `sotto`, IN EVERY DIRECTION (owner, 2026-10-08) ───────────────
    # *"e bota o nome 'sotto' em todos os temas."* Counted over RENDERED elements
    # only — the four chrome blocks that are not this direction's hold their own
    # text in the DOM and would otherwise read as five names where the eye sees one.
    # Lowercase is the point: `text-transform` is the one property that silently
    # overrules his spelling, so it is asserted separately from the count.
    if t.get('brandCount') != 1:
        bad('the header paints the name %r time(s), expected exactly once: %r'
            % (t.get('brandCount'), t.get('headerText')))
    if str(t.get('brandTextTransform') or 'none') != 'none':
        bad('the name is being text-transformed (%r) — the owner wrote it lowercase'
            % t.get('brandTextTransform'))
    if t.get('brandText') != 'sotto':
        bad('the name reads %r, expected the lowercase %r'
            % (t.get('brandText'), 'sotto'))

    if exp['led']:
        if not t.get('ledShown'):
            bad('the live-line LED is not on screen')
        if motion:
            if 'sotto-5-led-live' not in str(t.get('ledAnimation') or ''):
                bad('the LED animation is %r, expected sotto-5-led-live' % t.get('ledAnimation'))
        else:
            # The box's own setting: reduced motion must really stop it.
            if str(t.get('ledAnimation') or 'none') != 'none':
                bad('reduced motion is NOT honoured: the LED still animates (%r)'
                    % t.get('ledAnimation'))
            if str(t.get('ledBackground') or '') in ('', 'rgba(0, 0, 0, 0)'):
                bad('the LED is invisible with the animation off (background=%r)'
                    % t.get('ledBackground'))
    elif t.get('ledShown'):
        bad('the LED element is visible, but only `inst` has one')

    if exp['ramp']:
        if not t.get('rampUsesVars'):
            bad('the word spans carry no --w-i/--w-n')
        if not t.get('rampMonotonic'):
            bad('the contrast ramp is NOT monotonic: %r'
                % [w.get('op') for w in (t.get('words') or [])])
        if not t.get('rampTop') or abs(float(t['rampTop']) - 1.0) > 1e-6:
            bad('the newest word is not at full contrast (top=%r)' % t.get('rampTop'))
        if t.get('rampBottom') is None or float(t['rampBottom']) < 0.449:
            bad('the oldest word is below the ramp floor 0.45 (bottom=%r)' % t.get('rampBottom'))
        painted = [w.get('computedOpacity') for w in (t.get('words') or [])]
        if len(set(painted)) < 2:
            bad('every word paints the same opacity (%r): the ramp is not applied' % painted)
        if motion:
            if 'opacity' not in str(t.get('wordTransitionProperty') or ''):
                bad('the ramp is not transitioned on opacity (property=%r)'
                    % t.get('wordTransitionProperty'))
            if t.get('wordTransitionDuration') in (None, '0s'):
                bad('the ramp transition has no duration (%r)' % t.get('wordTransitionDuration'))
        elif str(t.get('wordTransitionDuration') or '0s') != '0s':
            bad('reduced motion is NOT honoured: the ramp still transitions (%r)'
                % t.get('wordTransitionDuration'))
    elif exp['fog']:
        if 'blur' not in str(t.get('textFilter') or ''):
            bad('the forming line carries no fog (filter=%r)' % t.get('textFilter'))
        if 'blur' not in str(t.get('tailFilter') or ''):
            bad('the rewriteable tail carries no fog (filter=%r)' % t.get('tailFilter'))
    else:
        if 'blur' in str(t.get('textFilter') or ''):
            bad('this direction must not carry the forming fog (filter=%r)' % t.get('textFilter'))

    # THE LEVEL BARS MUST NOT ANIMATE — IN EITHER ARM. The old `@keyframes`
    # loop is deleted, and this assertion is the one that keeps it deleted: a
    # CSS animation on the bars is a wave that moves without a measurement, which
    # is the lie `docs/research/12-audio-level-contract.md` measured and the owner
    # forbade. `meterShown`/`meterAnimation` are asserted above.
    live_meters = [a for a in (t.get('meterAnimations') or []) if a and a != 'none']
    if live_meters:
        bad('the level bars ANIMATE in the %s arm (%r) — the wave must be driven by '
            'the worker\'s own level, never by a keyframe loop'
            % ('motion' if motion else 'reduced', t.get('meterAnimations')))

    # No invented measurement: the mockups' simulated numbers must not be painted.
    blob = str(t.get('chromeTextAll') or '')
    for word in FORBIDDEN_TEXT:
        if word in blob:
            bad('the chrome prints a SIMULATED mockup reading (%r): %r' % (word, blob))


def check_strip(surface, problems):
    rows = (surface or {}).get('strip') or []
    if len(rows) != 5:
        problems.append('strip: expected 5 rows, got %d' % len(rows))
        return
    for r in rows:
        if r.get('surface') != 'strip':
            problems.append('strip(%s): surface attribute is %r' % (r.get('id'), r.get('surface')))
        if r.get('headerShown'):
            problems.append('strip(%s): the panel header is on screen on the strip surface' % r.get('id'))
        if r.get('headChromeShown'):
            problems.append('strip(%s): the direction header chrome is on screen on the strip' % r.get('id'))
        if r.get('footChromeShown'):
            problems.append('strip(%s): the direction footer chrome leaked onto the strip' % r.get('id'))
        if not r.get('stripThemeButtonShown'):
            problems.append('strip(%s): THE THEME BUTTON IS NOT REACHABLE on the strip surface'
                            % r.get('id'))
        label = str(r.get('stripThemeButtonLabel') or '')
        if not label:
            problems.append('strip(%s): the strip theme button carries no theme label' % r.get('id'))
        rect = r.get('stripThemeButtonRect') or [0, 0, 0, 0]
        if rect[2] <= 0 or rect[3] <= 0:
            problems.append('strip(%s): the strip theme button has no box %r' % (r.get('id'), rect))


def run_arm(browser, arm, page, wait_ms, problems, motion=False):
    dom = load_report(browser, page, wait_ms, motion=motion)
    errors, surface, themes = parse_report(dom)
    if errors is None:
        problems.append('%s: the probe left NO payload in the DOM (page did not run)' % arm)
        return
    if errors:
        problems.append('%s: probe errors: %s' % (arm, ' ; '.join(errors)))
    if len(themes) != 5:
        problems.append('%s: expected 5 theme rows, got %d' % (arm, len(themes)))
        return
    for t in themes:
        exp = EXPECTED.get(t.get('theme'))
        if not exp:
            problems.append('%s: unknown theme %r in the payload' % (arm, t.get('theme')))
            continue
        check_theme(t, exp, problems, motion)
    check_strip(surface, problems)
    print('  %-28s rows=%d errors=%d motion=%s'
          % (arm, len(themes), len(errors or []), 'ON' if motion else 'REDUCED'))
    if arm.startswith('real'):
        # THE VERIFICATION TABLE — the numbers behind the verdict, per direction,
        # so the receipt quotes what was measured rather than what was intended.
        print('     %-6s %-22s %-22s %-16s %-9s %s'
              % ('theme', 'own header', 'own footer (end)', 'theme button', 'ordinal',
                 'indicator'))
        for t in themes:
            exp = EXPECTED.get(t.get('theme'), {})
            btn = '%s/%s%s' % (t.get('themeButtonClientWidth'),
                               t.get('themeButtonScrollWidth'),
                               '' if not t.get('themeButtonLabelClipped') else ' CLIPPED')
            ind = []
            if exp.get('index'):
                ind.append('data-index=%s' % (t.get('rowOrdinals') or [])[-1:])
            if exp.get('led'):
                ind.append('led=%s' % (t.get('ledAnimation') or 'static'))
            if exp.get('ramp'):
                ind.append('ramp %s..%s' % (t.get('rampBottom'), t.get('rampTop')))
            if exp.get('fog'):
                ind.append('fog=%s' % t.get('tailFilter'))
            print('     %-6s %-22s %-22s %-16s %-9s %s'
                  % (t.get('theme'), (t.get('headText') or '')[:22],
                     (t.get('footEndText') or t.get('footStartText') or '')[:22],
                     btn,
                     # THE COLUMN NO LONGER SAYS "yes" FOR A DIRECTION THAT PRINTS
                     # ONE — nothing prints one any more, and a summary column that
                     # still answers `yes` beside `index=None` is the same class of
                     # lie this whole pass is about. It reports what is PAINTED.
                     ('%d painted' % t['paintedIndexCount']) if t.get('paintedIndexCount') else 'none',
                     ' '.join(ind) or '-'))
        for r in (surface or {}).get('strip') or []:
            print('     strip %-6s button=%sx%s label=%r'
                  % (r.get('theme'),
                     (r.get('stripThemeButtonRect') or [0, 0, 0, 0])[2],
                     (r.get('stripThemeButtonRect') or [0, 0, 0, 0])[3],
                     r.get('stripThemeButtonLabel')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--browser', default='edge', choices=('edge', 'chrome'))
    ap.add_argument('--neg-arm', action='store_true',
                    help='also run the two controls; each MUST go RED')
    ap.add_argument('--wait-ms', type=int, default=30000)
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()

    browser = find_browser(args.browser)
    os.makedirs(OUTDIR, exist_ok=True)

    real_page = build_copy('real', None)
    frame_page = build_frame(os.path.basename(real_page))
    print('arm copies:')
    print('  ', real_page)
    print('  ', frame_page, '(the 380x900 frame the real panel is measured in)')

    print()
    print('=== REAL ARM A — the box AS IT IS (Windows animations disabled → '
          'prefers-reduced-motion: reduce) ===')
    real_problems = []
    run_arm(browser, 'real-reduced', frame_page, args.wait_ms, real_problems, motion=False)
    real_ok = not real_problems
    for p in real_problems:
        print('   RED  ' + p)
    print('   %s — %d problem(s)' % ('GREEN' if real_ok else 'RED', len(real_problems)))

    print()
    print('=== REAL ARM B — the same page with motion EMULATED on '
          '(--blink-settings=prefersReducedMotion=false) ===')
    motion_problems = []
    run_arm(browser, 'real-motion', frame_page, args.wait_ms, motion_problems, motion=True)
    motion_ok = not motion_problems
    for p in motion_problems:
        print('   RED  ' + p)
    print('   %s — %d problem(s)' % ('GREEN' if motion_ok else 'RED', len(motion_problems)))

    neg_ok = True
    if args.neg_arm:
        print()
        print('=== CONTROLS — one half of the mechanism reverted in each ===')

        css_base = build_css_control('neg')
        with open(real_page, encoding='utf-8') as fh:
            html = fh.read()
        # The copy lives in `_audit-render/` (so `stub.js` and the probe resolve
        # beside it) and the reverted stylesheets live in `chrome-css-neg/themes/`
        # — also beside it. Only the five theme URLs move; the skin and the fonts
        # stay the real ones, so the control reverts the CHROME CSS and nothing
        # else.
        for n in range(1, 6):
            html = html.replace(REL + 'themes/theme-%d.css' % n,
                                'chrome-css-neg/themes/theme-%d.css' % n)
        css_page = os.path.join(OUTDIR, 'panel-chrome-css-neg.html')
        with open(css_page, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(html)
        print('  ', css_page, '(themes →', css_base + ')')

        markup_page = build_copy('markup-neg', 'markup')
        print('  ', markup_page)

        for arm, page in (('control-css', css_page), ('control-markup', markup_page)):
            problems = []
            # The controls are measured in the SAME 380x900 frame as the real
            # arms, so a control that goes RED goes red for the MECHANISM and not
            # for the geometry.
            run_arm(browser, arm, build_frame(os.path.basename(page)),
                    args.wait_ms, problems, motion=False)
            if problems:
                print('   RED-as-expected — %d problem(s); first three:' % len(problems))
                for p in problems[:3]:
                    print('     - ' + p)
            else:
                neg_ok = False
                print('   GREEN — THAT IS A FAILING CONTROL: reverting the mechanism '
                      'changed nothing the probe can see')

    print()
    verdict_ok = real_ok and motion_ok and neg_ok
    print('VERDICT: %s' % (
        'GREEN — each direction has its own header, footer, indicator and control '
        'placement; reduced motion is honoured on this box; and the theme button is '
        'reachable on BOTH surfaces'
        if verdict_ok else 'RED'))
    return 0 if verdict_ok else 1


if __name__ == '__main__':
    sys.exit(main())
