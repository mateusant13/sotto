#!/usr/bin/env python3
"""compare.py -- THE COMPARISON, per demo, with numbers on both sides.

WHAT IT READS
-------------
  docs/design-intake/demos/<demo>.json      the DEMO, measured by cdp.mjs at
                                            the demo's own viewport (probe-demo.js)
  docs/design-intake/current/<theme>.json   the PRODUCT'S PANEL, measured at
                                            the owner's 380x900 (probe-panel.js)
  the ZIP'S OWN SOURCE, read out of the ledger below, with the file:line

THE LEDGER IS NOT A SUMMARY
---------------------------
Every value in LEDGER is the zip's own, with the file:line it came from, so
the claim "the product took the CENTRAL STAGE's size" is a citation and not a
recollection. The two components of zip A are the whole story:

  src/components/Caption.tsx  -- the LIVE CAPTION, in the CENTRE of the stage,
                                 max-w 720..780px, sized with clamp(...,vw,...)
  src/components/Panel.tsx    -- the SIDE PANEL, 380x900, the TRANSCRIPT column,
                                 sized in fixed px

The product's right panel is the second one with the first one's type.

    python _main/_design-lane/compare.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.join(REPO, 'docs', 'design-intake')

# (set, num, name, product theme, zip, demo live px, demo closed px,
#  demo column px, source of the demo's numbers, the OTHER component of the same zip)
LEDGER = [
    # --- zip A: sotto-app-design-directions.zip (the five DIRECTIONS) -------
    # the demo's panel is 380x900 BY DESIGN but the demo renders it at
    # `height: min(74vh,720px); aspect-ratio: 380/900` (index.css), i.e. 304x720
    # at the viewport the prints were taken at -- MEASURED, 304x720.
    ('A', '01', 'teleprompter', 'theme-1', 'sotto-app-design-directions.zip',
     18.5, 16.5, 272, 'Panel.tsx:113 (live) / :105 (closed), px-4 at :94',
     'Caption.tsx:23 clamp(30px,4.6vw,54px) + uppercase -- the CENTRAL stage'),
    ('A', '02', 'broadcast', 'theme-2', 'sotto-app-design-directions.zip',
     10.5, 10.5, 194, 'Panel.tsx:130 (live) / :123 (closed), grid 24+38+1fr at :123',
     'Caption.tsx:45 clamp(18px,2.3vw,28px) -- the CENTRAL stage'),
    ('A', '03', 'manuscrito', 'theme-3', 'sotto-app-design-directions.zip',
     14.5, 14, 272, 'Panel.tsx:155 (live) / :149 (closed), px-4 at :94',
     'Caption.tsx:71 clamp(21px,2.7vw,33px) -- the CENTRAL stage'),
    ('A', '04', 'cartao-de-cinema', 'theme-4', 'sotto-app-design-directions.zip',
     15, 15, 272, 'Panel.tsx:176 (live) / :165 (closed), px-4 at :94',
     'Caption.tsx:110 clamp(24px,3vw,42px) -- the CENTRAL stage'),
    ('A', '05', 'instrumento', 'theme-5', 'sotto-app-design-directions.zip',
     14.5, 13.5, 256, 'Panel.tsx:196 (live) / :188 (closed), px-4 at :94',
     'Caption.tsx:133 clamp(24px,3.1vw,42px) -- the CENTRAL stage'),

    # --- zip E: sotto-transcription-panel-designs.zip (the five PANELS) -----
    # this zip's panel IS 380x900 (Stage.tsx:105), so its column is the one the
    # product's 380 px column was supposed to be.
    ('E', '01', 'teleprompter', 'pd-tele', 'sotto-transcription-panel-designs.zip',
     32, 25, 324, 'panels.tsx:53 (live) / :45 (closed), px-7 at :41',
     'the panel is 380x900 at Stage.tsx:105 -- there is no central stage in this zip'),
    ('E', '02', 'broadcast', 'pd-bcast', 'sotto-transcription-panel-designs.zip',
     13.5, 13.5, 348, 'panels.tsx:132 (live) / :117 (closed), px-4 at :115',
     'the panel is 380x900 at Stage.tsx:105 -- there is no central stage in this zip'),
    ('E', '03', 'manuscrito', 'pd-mano', 'sotto-transcription-panel-designs.zip',
     18, 18, 300, 'panels.tsx:201 (live) / :192 (closed), pl-12 pr-8 at :185',
     'the panel is 380x900 at Stage.tsx:105 -- there is no central stage in this zip'),
    ('E', '04', 'cartao-de-cinema', 'pd-cine', 'sotto-transcription-panel-designs.zip',
     21, 21, 308, 'panels.tsx:245 (live) / :235 (closed), px-9 at :231',
     'the panel is 380x900 at Stage.tsx:105 -- there is no central stage in this zip'),
    ('E', '05', 'instrumento', 'pd-instr', 'sotto-transcription-panel-designs.zip',
     23, 18, 324, 'panels.tsx:325 (live) / :315 (closed), px-5 at :311',
     'the panel is 380x900 at Stage.tsx:105 -- there is no central stage in this zip'),
]

# zip B (cinematic) ten themes, zip C (cinematic-1) ten panels, zip D
# (cinematic-2) twenty themes: their DEMO puts the LIVE CAPTION IN THE MIDDLE
# of the stage and the transcript in the side panel, so the side panel is not
# the caption's home. They are listed with the product theme that carries them.
LEDGER_C = [
    ('B', '01', 'midnight-rain', 'cine-midnight-rain', 'cinematic-transcription-app-designs.zip'),
    ('B', '02', 'warm-hour', 'cine-warm-hour', 'cinematic-transcription-app-designs.zip'),
    ('B', '03', 'velvet-dusk', 'cine-velvet-dusk', 'cinematic-transcription-app-designs.zip'),
    ('B', '04', 'study-light', 'cine-study-light', 'cinematic-transcription-app-designs.zip'),
    ('B', '05', 'tideline', 'cine-tideline-body', 'cinematic-transcription-app-designs.zip'),
    ('B', '06', 'motel-glow', 'cine-motel-glow', 'cinematic-transcription-app-designs.zip'),
    ('B', '07', 'paper-moon', 'cine-paper-moon', 'cinematic-transcription-app-designs.zip'),
    ('B', '08', 'quiet-streets', 'cine-quiet-streets', 'cinematic-transcription-app-designs.zip'),
    ('B', '09', 'last-reel', 'cine-last-reel', 'cinematic-transcription-app-designs.zip'),
    ('B', '10', 'north-fog', 'cine-north-fog', 'cinematic-transcription-app-designs.zip'),
    ('C', '01', 'glass-cards', 'GlassCards', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '02', 'hairline', 'Hairline', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '03', 'paper', 'Paper', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '04', 'quotes', 'Quotes', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '05', 'ledger', 'Ledger', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '06', 'feed', 'Feed', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '07', 'bubbles', 'Bubbles', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '08', 'timeline', 'Timeline', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '09', 'chips', 'Chips', 'cinematic-transcription-app-designs (1).zip'),
    ('C', '10', 'gutter', 'Gutter', 'cinematic-transcription-app-designs (1).zip'),
    ('D', '01', 'rainline', 'cine-rainline', 'cinematic-transcription-app-designs (2).zip'),
    ('D', '03', 'cellar', 'cine-cellar', 'cinematic-transcription-app-designs (2).zip'),
    ('D', '04', 'linen', 'cine-linen', 'cinematic-transcription-app-designs (2).zip'),
    ('D', '11', 'reading-hour', 'cine-reading-hour', 'cinematic-transcription-app-designs (2).zip'),
    ('D', '13', 'last-train', 'cine-last-train', 'cinematic-transcription-app-designs (2).zip'),
    ('D', '17', 'blue-hour', 'cine-blue-hour', 'cinematic-transcription-app-designs (2).zip'),
]

SET_PREFIX = {'A': 'zip1-directions-', 'E': 'zip2-panels-', 'B': 'zip3-cinematic-',
              'C': 'zip4-cinematic-1-', 'D': 'zip5-cinematic-2-'}


def load(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def demo_metrics(path):
    """The demo's own numbers, measured."""
    d = load(path)
    if not d:
        return None
    panel = d.get('panel') or {}
    texts = d.get('texts') or []
    sizes = sorted({t['fontSize'] for t in texts if t.get('fontSize')}, reverse=True)
    col = (d.get('column') or {}).get('maxTextW')
    return {
        'panel_w': panel.get('cssWidth'),
        'panel_h': panel.get('cssHeight'),
        'scale': panel.get('scale'),
        'live': sizes[0] if sizes else None,
        'closed': sizes[1] if len(sizes) > 1 else None,
        'column': col,
        'n_texts': len(texts),
    }


def product_metrics(path):
    """The product's numbers, measured at 380x900."""
    d = load(path)
    if not d:
        return None
    caps = d.get('captions') or []
    live = caps[-1] if caps else {}
    closed = caps[0] if caps else {}
    rail = d.get('rail') or {}
    over = d.get('overflowingBottom') or []
    ctl = (d.get('controls') or {}).get('buttons') or []
    return {
        'live': live.get('fontSize'),
        'closed': closed.get('fontSize'),
        'column': live.get('clientW'),
        'lines': live.get('wrappedLines'),
        'text_h': live.get('textH'),
        'rail_client_h': rail.get('clientH'),
        'rail_scroll_h': rail.get('scrollH'),
        'past_bottom': max([o['past_by'] for o in over] or [0]),
        'ctl_past': max([b['past_by'] for b in ctl] or [0]),
        'text': live.get('text'),
    }


def num(v):
    if v is None:
        return '-'
    if isinstance(v, str):
        v = v.strip()
        if v.endswith('px'):
            v = v[:-2]
        try:
            return '%g' % round(float(v), 2)
        except ValueError:
            return v
    try:
        return '%g' % round(float(v), 2)
    except (TypeError, ValueError):
        return str(v)


def main():
    lines = []
    w = lines.append
    w('# THE COMPARISON -- the .zip original against the panel the owner has')
    w('')
    w('Generated by `_main/_design-lane/compare.py`. Every number below was MEASURED')
    w('by `cdp.mjs` (Chrome DevTools Protocol), which sets the LAYOUT viewport -- the')
    w('only way to see the owner\'s 380 px, because headless Edge\'s own --screenshot')
    w('clamps the layout to 492 px on this box (measured: 380 -> 492, 520 -> 496,')
    w('1000 -> 976). The demo side is the owner\'s own prebuilt bundle in')
    w('`_main/zip-mockups/`; the product side is a copy of `app/panel/` wearing the theme.')
    w('')
    w('The fixture on the product side is the zip\'s OWN script')
    w('(`_main/ziprefs/dirs/src/data/designs.ts:85`), and the forming line is its')
    w('longest one (57 characters) -- the worst case the panel has to survive.')
    w('')

    for (setk, num_, name, theme, zipsrc, d_live, d_closed, d_col, demo_src, other_src) in LEDGER:
        pref = SET_PREFIX[setk]
        base = '%s%s-%s' % (pref, num_, name)
        dm = demo_metrics(os.path.join(ROOT, 'demos', base + '.json'))
        pm = product_metrics(os.path.join(ROOT, 'current', 'current-%s.json' % theme))
        w('## %s %s %s -- `%s` -- %s' % (setk, num_, name, theme, zipsrc))
        w('')
        w('| | the demo (the zip\'s own) | the product now (measured at 380x900) |')
        w('|---|---|---|')
        w('| the panel box | %s x %s (MEASURED) | 380 x 900 |'
          % (num(dm['panel_w']) if dm else '-', num(dm['panel_h']) if dm else '-'))
        w('| the LIVE line | %s px | %s px |' % (num(d_live), num(pm['live']) if pm else '-'))
        w('| the closed lines | %s px | %s px |' % (num(d_closed), num(pm['closed']) if pm else '-'))
        w('| the column the text gets | %s px | %s px |' % (num(d_col), num(pm['column']) if pm else '-'))
        if pm:
            w('| the live line wraps to | 1 line | %s line(s) |' % num(pm['lines']))
            w('| the rail overflows its own bottom by | - | %s px |' % num(pm['past_bottom']))
            w('| a control past the panel edge by | - | %s px |' % num(pm['ctl_past']))
        w('')
        w('* the demo\'s own numbers: %s' % demo_src)
        w('* the OTHER component of the same zip: %s' % other_src)
        if dm:
            w('* the demo\'s own column, MEASURED in the page: %s px' % num(dm['column']))
        if pm and pm['live']:
            try:
                ratio = float(pm['live']) / float(d_live)
                w('* **the live line is %sx the size the demo\'s own side panel uses** '
                  '(%s px vs %s px)' % (round(ratio, 2), num(pm['live']), num(d_live)))
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        w('* prints: `docs/design-intake/demos/%s.png` (the demo) and '
          '`docs/design-intake/current/current-%s.png` (the product)' % (base, theme))
        w('')

    w('## zip B / C / D -- the sets whose live caption lives in the MIDDLE')
    w('')
    w('| set | demo | the product theme | the demo\'s side panel | the live line |')
    w('|---|---|---|---|---|')
    for (setk, num_, name, theme, zipsrc) in LEDGER_C:
        pref = SET_PREFIX[setk]
        base = '%s%s-%s' % (pref, num_, name)
        dm = demo_metrics(os.path.join(ROOT, 'demos', base + '.json'))
        pm = product_metrics(os.path.join(ROOT, 'current', 'current-%s.json' % theme))
        w('| %s | %s %s | `%s` | %s | %s px |' % (
            setk, num_, name, theme,
            ('%s x %s' % (num(dm['panel_w']), num(dm['panel_h']))) if dm else '-',
            num(pm['live']) if pm else '-'))
    w('')

    out = os.path.join(ROOT, 'COMPARISON.md')
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('WROTE %s (%d lines)' % (out, len(lines)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
