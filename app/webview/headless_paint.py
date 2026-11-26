"""A paint destination that makes REAL caption pixels without a window.

THE SEAM THIS REUSES (no layout is copied here). The product decides what to
paint in `app/webview/caption_overlay.py`:

  * `CaptionOverlay._update` asks `_display()` for the text of this frame
    (`caption_overlay.py:1624`); on the player path `_display` -> `_cue_texts`
    (`:1918-1929`, `:1960-1979`) asks the cue's own clock for its marks;
  * `_update` hands that text to `overlay_paint._layout` (`:1648`, defined at
    `overlay_paint.py:604-677`) and the resulting lines to
    `overlay_paint._premultiplied_bitmap` (`:1657`, defined at
    `overlay_paint.py:789-814`).

`_main/overlay-ink-oracle.py:123-131` already reads those same two functions
off-screen. This module extends that idea from ONE string to a CUE SEQUENCE and
a sequence of wall instants: for each instant it selects the cue the product
would have, asks the product's `_PlayerCue` for the frame, lays it out with the
product's `_layout`, paints it with the product's `_premultiplied_bitmap`, and
reads the pixels through `LockBits`. There is no `CreateWindowExW`, no
`UpdateLayeredWindow`, no timer and no message loop. A GDI+ Bitmap is created,
read and disposed per frame.

WHAT IT PROVES AND WHAT IT DOES NOT. It proves that the product's own layout
and style code produces the expected ink at a DECLARED instant, compared to the
product's cue clock. It does not measure a compositor, a screen, a YouTube feed
or the owner's audio; those need a different instrument.

Usage (normally through `_main/yt-headless-paint-oracle.py`):

    import headless_paint
    product = headless_paint.load_product()
    cue = headless_paint.make_cue(product, 'A', ['one', 'two'], 100.0)
    frame = headless_paint.render_frame(product, [cue], 0.5)
"""
from __future__ import annotations

import hashlib
import os
import sys
from types import SimpleNamespace

# A scratch copy of this module (negative arm) lives in a temp directory, so
# the repo root is pinned by the caller before that copy is imported.
ROOT = (os.environ.get('SOTTO_ROOT')
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

#: The real strip is painted at scale 2.0 in a 1920 px work area (ink oracle).
SCALE = 2.0
WORK_WIDTH = 1920
#: Pixel sampling step for the ink extent; the digest covers the FULL raster.
PIXEL_STEP = 2

_DISPOSED = 0


def _load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_product():
    """The product modules whose functions the paint path calls."""
    # `caption_overlay._PlayerCue.frame` does `import youtube_reveal` inside the
    # function; the canonical name keeps a scratch overlay on the same engine.
    if 'youtube_reveal' not in sys.modules:
        _load(os.path.join(WEBVIEW, 'youtube_reveal.py'), 'youtube_reveal')
    return SimpleNamespace(
        paint=_load(os.path.join(WEBVIEW, 'overlay_paint.py'),
                    'overlay_paint_headless_paint'),
        overlay=_load(os.path.join(WEBVIEW, 'caption_overlay.py'),
                      'caption_overlay_headless_paint'),
        reveal=sys.modules['youtube_reveal'],
    )


def dispose_count():
    """How many bitmaps this module has closed -- the teardown receipt."""
    return int(_DISPOSED)


def make_cue(product, label, words, start, at=0.0, rate=1.0, gap=0.25,
             end=None, word_starts=None):
    """A cue in the product's own `rows_from_cues` shape.

    `at` is the WALL instant when the shell publishes the cue; `start` is the
    VIDEO time it covers. Wall and video time are different clocks on purpose:
    the whole point of the oracle is to compare them.
    """

    words = [str(w) for w in words]
    starts = ([float(s) for s in word_starts] if word_starts is not None
              else [float(start) + i * float(gap) for i in range(len(words))])
    text = ' '.join(words)
    rows = product.reveal.rows_from_cues([{
        'text': text,
        'start': float(start),
        'end': float(end if end is not None else start + gap * len(words)),
        'words': [{'text': w, 'start': s} for w, s in zip(words, starts)],
    }])
    return {'label': label, 'text': text, 'rows': rows, 't': float(start),
            'at': float(at), 'rate': float(rate), 'start': float(start),
            'end': float(end if end is not None else start + gap * len(words)),
            'word_starts': starts}


def select_cue(windows, now):
    """The cue the product would hold after the last publish at/before now."""
    live = [cue for cue in windows or () if float(cue['at']) <= now + 1e-9]
    return live[-1] if live else None


def expected_text(product, cue, now):
    """Independent expectation from the cue clock and the word instants.

    This does NOT call `frame()`: it recomputes the clock (`PLAYER_HOLD_S`,
    rate) and asks the reveal engine for the word count at that video time. The
    rendered frame is then compared against it, so a frozen or invented clock
    shows up as a text mismatch instead of agreeing with its own caller. The
    result goes through the product's `rows_text` channel, whose trailing
    newline is the marker `_layout` uses to keep an already-broken line.
    """
    if cue is None:
        return ''
    gap = max(0.0, float(now) - float(cue['at']))
    clock = float(cue['t']) + min(gap, float(product.overlay.PLAYER_HOLD_S)) * float(cue['rate'])
    row = cue['rows'][0]
    if clock >= float(row.get('end')) + float(product.reveal.EXIT_S):
        return ''
    count = product.reveal.word_clock_count(row, clock)
    body = product.reveal.first_words(cue['text'], int(count or 0))
    return '' if not body else product.reveal.rows_text([body])


def _ink(bmp, width, height, step=PIXEL_STEP):
    """Read the real GDI+ raster: (sampled ink px, box, full-raster digest)."""
    global _DISPOSED
    import clr  # noqa: F401 -- pythonnet must be loaded before System.Drawing
    clr.AddReference('System.Drawing')
    clr.AddReference('System')
    from System import Array, Byte
    from System.Drawing import Rectangle
    from System.Drawing.Imaging import ImageLockMode, PixelFormat
    from System.Runtime.InteropServices import Marshal
    digest = hashlib.sha256()
    if int(bmp.Width) != int(width) or int(bmp.Height) != int(height):
        return -1, (0, 0, 0, 0), 'SIZE-MISMATCH-%dx%d-want-%dx%d' % (
            int(bmp.Width), int(bmp.Height), width, height)
    data = bmp.LockBits(Rectangle(0, 0, int(width), int(height)),
                        ImageLockMode.ReadOnly, PixelFormat.Format32bppPArgb)
    try:
        stride = abs(int(data.Stride))
        buffer = Array.CreateInstance(Byte, stride * int(height))
        Marshal.Copy(data.Scan0, buffer, 0, len(buffer))
        raw = bytes(bytearray(buffer))
    finally:
        bmp.UnlockBits(data)
    digest.update(raw)
    count = 0
    min_x = min_y = None
    max_x = max_y = None
    for y in range(0, int(height), step):
        row = raw[y * stride:y * stride + int(width) * 4]
        for x in range(0, int(width), step):
            if row[4 * x + 3]:
                count += 1
                min_x = x if min_x is None else min(min_x, x)
                max_x = x if max_x is None else max(max_x, x)
                min_y = y if min_y is None else min(min_y, y)
                max_y = y if max_y is None else max(max_y, y)
    box = (0, 0, 0, 0) if min_x is None else (min_x, min_y, max_x, max_y)
    return count, box, digest.hexdigest()


def render_frame(product, windows, now, theme=None, scale=SCALE,
                 work_width=WORK_WIDTH, step=PIXEL_STEP):
    """One declared wall instant -> one off-screen frame and its real ink."""
    global _DISPOSED
    cue = select_cue(windows, now)
    if cue is None:
        text = ''
        clock = None
    else:
        player = product.overlay._PlayerCue(
            cue['rows'], cue['t'], at=cue['at'], rate=cue['rate'],
            log=lambda _message: None)
        clock = player.clock(now)
        marks = player.frame(now)
        texts = product.overlay._clamp_rows(
            [mark.get('text') for mark in marks],
            product.overlay.PLAYER_ROWS + 1)
        text = product.reveal.rows_text(texts)
    # The same theme and the same tight plate as the ink oracle: no plate, so
    # every pixel with alpha is GLYPH ink, never a background rectangle.
    style = dict(theme or product.paint._THEME_DEFAULT)
    for key in ('plate', 'background'):
        style.pop(key, None)
    lines, previous, width, height, _scrolled = product.paint._layout(
        text, '', scale, work_width, style, plate_mode='tight')
    bmp = product.paint._premultiplied_bitmap(
        lines, previous, int(width), int(height), scale, style, None, 0.0,
        plate_mode='tight')
    try:
        ink_px, box, digest = _ink(bmp, int(width), int(height), step)
    finally:
        bmp.Dispose()
        _DISPOSED += 1
    return {
        'instant': float(now),
        'cue': None if cue is None else cue['label'],
        'text': text,
        'clock': clock,
        'ink_px': int(ink_px),
        'width': int(width),
        'height': int(height),
        'box': box,
        'ink_span': (0, 0) if ink_px <= 0 else (box[2] - box[0] + 1,
                                               box[3] - box[1] + 1),
        'digest': digest,
    }
