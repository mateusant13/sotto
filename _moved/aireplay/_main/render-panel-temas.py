#!/usr/bin/env python3
"""SOTTO — THE THEME CAPTURE RENDERER. Five designs, photographed, with their numbers.

WHAT IT IS FOR
--------------
Give the owner eyes on each of the five panel themes WITHOUT Alt+C and WITHOUT
opening a window. It builds a GENERATED FIXTURE COPY of the panel document, puts
a realistic PT-BR caption state in it, and takes one Chrome-headless screenshot
per theme plus a five-up comparison sheet. For every shot it also records the
COMPUTED STYLE that defines the theme, so the owner can read what he is looking
at instead of judging by impression.

WHAT IT IS NOT
--------------
It does not change the panel, the themes, or the design. It does not touch
`worker/**` or `app/webview/**`. It never opens a visible window and never opens
an audio device. It only READS `H:\\sotto` and only WRITES under `H:\\aireplay`.

THE FOUR MEASURED FACTS THIS FILE IS BUILT ON (each was probed, not assumed)
--------------------------------------------------------------------------
1. THE PANEL'S REAL GEOMETRY IS 380x900, NOT 1920x1080.
   `app/webview/sotto_webview.py` PANEL_WIDTH=380 / PANEL_HEIGHT=900, and the
   display here is 96 dpi (scale 1.0, `_viewport-probe.py` / `_dpi`), so the
   WebView2 client area really is 380x900 CSS px. A 1920-wide shot is a picture
   of a panel nobody sees; it is kept here only as a labelled control.

2. `--window-size` DOES NOT CONTROL THE VIEWPORT AT LOAD — BUT IT DOES CONTROL
   THE CAPTURE. Measured (`_reflow-probe.py`): at load, `innerWidth` is clamped
   (500 for a 380 request, `W-16` for wider ones) and `innerHeight` is `H-95`;
   `--dump-dom` sees THAT size and never sees a resize. The screenshot path
   RESIZES the window to `--window-size` first, so the PNG is a true WxH layout.
   Consequence, and it is the trap this file exists to avoid: a metrics pass run
   with `--dump-dom` measures a DIFFERENT layout than the shot shows.
   The cure is `fixture-geometry.css`, a FIXTURE-ONLY stylesheet that pins the
   layout box to 380x900 so both passes agree; `metrics.panelRect` is asserted
   against 380x900 and the run FAILS if it is anything else.

3. THE DRIVER MUST NOT RE-PUSH A CUMULATIVE FRAGMENT. `ingest()` duplicates the
   words when the same fragment arrives twice with a live buffer (the re-cover
   guard needs `start < emittedEnd`, which is false for a new segment). So the
   stream is held open by extending the panel's OWN hold deadline
   (`SottoFormulation.COMMIT_MAX_HOLD_MS`), a documented fixture knob — the
   shipped 1500 ms constant is untouched in the repo.

4. `--dump-dom` PIPED THROUGH POWERSHELL `-Command` RETURNS EMPTY on this box.
   Everything here runs Chrome through `subprocess.Popen`, never a shell.

BUDGET (the owner's machine must not stutter)
---------------------------------------------
One Chrome at a time, strictly sequential; `OMP/OPENBLAS/MKL_NUM_THREADS=2` in
the child environment; one shared Chrome profile deleted at the end; a hard disk
check that refuses to finish above 200 MB; and a 100 ms window census that proves
no visible window appeared (the house census samples once per 60 s and cannot).

USAGE
-----
    py -3 H:\\aireplay\\_main\\render-panel-temas.py
    py -3 ... --themes 1,5          only these themes
    py -3 ... --no-wide             skip the 1920x1080 control arm
    py -3 ... --attempts 3          re-capture passes when the panel moves

Exit code 0 = every verdict passed. Anything else = a failure, and the reason is
printed. A failure never answers as success.
"""

import argparse
import ctypes
import ctypes.wintypes as wintypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

try:
    import psutil
except ImportError:  # pragma: no cover
    print('FATAL: psutil is required (exact-PID process-tree handling)')
    raise

# The console on this box is not UTF-8, and the measured strings carry "·" and
# Portuguese accents; without this the log mangles them and a reader cannot tell
# a real character from a broken one.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ---------------------------------------------------------------------------
# paths and constants
# ---------------------------------------------------------------------------

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
SOTTO = r'H:\sotto'
PANEL_DIR = os.path.join(SOTTO, 'app', 'panel')
HISTORY_DIR = os.path.join(SOTTO, 'history', '2026-10-06')
STUB_SRC = os.path.join(SOTTO, '_main', '_audit-render', 'stub.js')
OUT_DIR = r'H:\aireplay\_main'
FIXTURE_DIR = os.path.join(OUT_DIR, 'panel-temas-fixture')
PROFILE_DIR = os.path.join(FIXTURE_DIR, '_chrome-profile')
MANIFEST = os.path.join(OUT_DIR, 'panel-temas-manifest.json')
TABLES = os.path.join(OUT_DIR, 'panel-temas-tabela.md')

PANEL_W, PANEL_H = 380, 900
CAPTURE_SCALE = 2
WIDE_W, WIDE_H = 1920, 1080
COMPARE_W, COMPARE_H = 1980, 1080
BUDGET_MS = 5000
CENSUS_MS = 100
DISK_BUDGET_BYTES = 200 * 1024 * 1024
CREATE_NO_WINDOW = 0x08000000

THEMES = [
    (1, 'theme-1', 'teleprompter', 'Teleprompter'),
    (2, 'theme-2', 'broadcast', 'Broadcast'),
    (3, 'theme-3', 'manuscrito', 'Manuscrito'),
    (4, 'theme-4', 'cinema-card', 'Cinema Card'),
    (5, 'theme-5', 'instrumento', 'Instrumento'),
]

# The panel document and every asset it loads. `themes/fonts.css` is the
# @font-face sheet and `fonts/*.woff2` are the bundled typefaces: without them
# every theme paints a fallback and the design is a colour change.
ASSETS = [
    'panel.html', 'panel.css', 'panel.js',
    'caption-formulation.js', 'history-source.js', 'surface.js', 'theme-switcher.js',
    'themes/themes.js', 'themes/fonts.css',
    'themes/theme-1.css', 'themes/theme-2.css', 'themes/theme-3.css',
    'themes/theme-4.css', 'themes/theme-5.css',
]

BASE_FLAGS = [
    '--headless=new',            # never a visible window; the only mode allowed
    '--disable-gpu',
    '--hide-scrollbars',
    '--mute-audio',              # no audio, ever
    '--disable-audio-output',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--disable-sync',
    '--disable-background-networking',
    '--disable-component-update',
    '--disable-client-side-phishing-detection',
    '--disable-default-apps',
    '--disable-features=Translate,MediaRouter,OptimizationHints,AcceptCHFrame',
    '--disk-cache-size=1048576',
]
# Deliberately NOT set: `--window-position=-32000,-32000`. It is a documented
# hang for the WebView2 shell and buys nothing here — `--headless=new` never maps
# a window, and `windowCensus` in the manifest is the evidence rather than a flag.

# ---------------------------------------------------------------------------
# THE FIXTURE'S CAPTION SCRIPT — REAL PT-BR, FROM THE OWNER'S OWN TRANSCRIPT
# ---------------------------------------------------------------------------
# Not "lorem ipsum" and not one line. Every string below is a line the worker
# really closed in the owner's own history, quoted with its file and line so the
# renderer can PROVE the text still exists there (it refuses to run otherwise).
# The panel's own cap is SENTENCE_MAX_CHARS=90, so a "real size" line is <= ~90
# chars — that is what the app itself can hold.
#
# `closed`: [prefix partial, full line]. The prefix is what the worker sends
# first (a growing hypothesis); the full line arrives with `final:true` and the
# NEXT segment's arrival (>= SENTENCE_GAP_S=8 s later in audio time) closes it as
# `route=final`. The prefix must be short enough that the panel's own lookahead
# (`len(buffer) + 1 + len(fragment) > 90`) does not split the line in two.
#
# `forming`: the line still in formation. Two cumulative partials with the SAME
# `start` and no `final` give LocalAgreement-2 its two hypotheses, so the panel
# paints a `.caption__confirmed` part AND a `.caption__provisional` tail — the
# two states four of the five themes style differently.
SCRIPT = {
    'closed': [
        {'file': '15.md', 'line': 88,
         'prefix': 'Porque aqui vou jogar',
         'text': 'Porque aqui vou jogar um machismo será porque aqui a gente.'},
        {'file': '15.md', 'line': 424,
         'prefix': 'Qual servidor que',
         'text': 'Qual servidor que vocês estão jogando vou meter uma gameplay desse.'},
        {'file': '16.md', 'line': 43,
         'prefix': 'Possível se chegad',
         'text': 'Possível se chegad o antes eu tinha esmi tado cara esse cara tá de.'},
        {'file': '16.md', 'line': 431,
         'prefix': 'Um streamer mano',
         'text': 'Um streamer mano traba dele mano a justar o da mira é isso aqui não né.'},
    ],
    'forming': {
        'file': '15.md', 'line': 61,
        'prefix': 'Essa galera que estuda vinte',
        'text': 'Essa galera que estuda vinte e quatro horas eu não estu dei.',
    },
}
# WHY THESE LENGTHS, and it is a measurement rather than a preference: the first
# fixture used four 76-88 char lines, and in themes 3 (Manuscrito) and 4 (Cinema
# Card) the rendered list came out TALLER than the live box — `scrollH` 550 vs
# `clientH` 533, and 626 vs 552 — so the box followed the newest line and the
# oldest closed line scrolled out of the picture. Four lines of 59-71 chars plus
# one forming line fit in every theme, so the five captures show the SAME content
# and the only variable left is the design. The measured numbers are in
# `panel-temas-manifest.json` under `themes[].metrics.geometry`.

# ---------------------------------------------------------------------------
# the window census — proves NO visible window appeared, at our own cadence
# ---------------------------------------------------------------------------


class WindowCensus(threading.Thread):
    """Sample the visibility of every top-level window owned by OUR Chrome trees.

    The house census runs once per 60 s, which cannot prove the absence of a
    short-lived window; this one samples at 100 ms and only ever looks at the
    exact PIDs we spawned and their descendants. The owner's own 47 chrome.exe
    processes are never inspected, never counted, never touched.
    """

    def __init__(self, interval=0.1):
        super().__init__(daemon=True)
        self.interval = interval
        self._lock = threading.Lock()
        self._roots = set()
        self._stop = threading.Event()
        self.samples = 0
        self.visible = []
        self.errors = []
        self.first_ts = None

    def track(self, pid):
        with self._lock:
            self._roots.add(int(pid))

    def untrack(self, pid):
        with self._lock:
            self._roots.discard(int(pid))

    def stop(self):
        self._stop.set()

    def _pids(self):
        with self._lock:
            roots = list(self._roots)
        out = set()
        for r in roots:
            out.add(r)
            try:
                for c in psutil.Process(r).children(recursive=True):
                    out.add(c.pid)
            except Exception:
                pass
        return out

    def run(self):
        user32 = ctypes.windll.user32
        proto = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        while not self._stop.is_set():
            pids = self._pids()
            if pids:
                self.samples += 1
                if self.first_ts is None:
                    self.first_ts = time.time()
                found = []

                def cb(hwnd, _lparam):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in pids and user32.IsWindowVisible(hwnd):
                        cls = ctypes.create_unicode_buffer(256)
                        title = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(hwnd, cls, 256)
                        user32.GetWindowTextW(hwnd, title, 256)
                        found.append({
                            'pid': int(pid.value),
                            'hwnd': int(hwnd or 0),
                            'class': cls.value,
                            'title': title.value,
                        })
                    return True

                try:
                    user32.EnumWindows(proto(cb), 0)
                except Exception as exc:  # pragma: no cover
                    self.errors.append(repr(exc))
                for f in found:
                    if len(self.visible) < 500:
                        self.visible.append(f)
            self._stop.wait(self.interval)


def kill_tree(root_pid, reason):
    """Terminate ONLY the exact PIDs in this process's own tree.

    A kill filter that names an artifact is the house rule; a name filter once
    killed unrelated processes of the owner's other projects. This walks the tree
    from a PID WE spawned and terminates those PIDs and no others.
    """
    killed = []
    try:
        root = psutil.Process(root_pid)
        procs = root.children(recursive=True) + [root]
    except Exception:
        return killed
    for p in reversed(procs):
        try:
            if p.is_running():
                p.terminate()
                killed.append(p.pid)
        except Exception:
            pass
    gone, alive = psutil.wait_procs(procs, timeout=5)
    for p in alive:
        try:
            p.kill()
            killed.append(p.pid)
        except Exception:
            pass
    if killed:
        print('      kill(%s): exact pids %s' % (reason, killed))
    return killed


# ---------------------------------------------------------------------------
# reading the sources, with the revision stamped
# ---------------------------------------------------------------------------


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest().upper()


def read_sources():
    """Every byte this fixture is built from, with its sha256/size/mtime."""
    out = {}
    for rel in ASSETS:
        p = os.path.join(PANEL_DIR, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            raise SystemExit('FATAL: panel.html references %r and it is missing' % rel)
        st = os.stat(p)
        out[rel] = {'sha256': sha256_file(p), 'bytes': st.st_size,
                    'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
                    'path': p}
    fonts_dir = os.path.join(PANEL_DIR, 'fonts')
    for name in sorted(os.listdir(fonts_dir)):
        p = os.path.join(fonts_dir, name)
        if not os.path.isfile(p):
            continue
        st = os.stat(p)
        out['fonts/' + name] = {'sha256': sha256_file(p), 'bytes': st.st_size,
                                'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                                       time.localtime(st.st_mtime)),
                                'path': p}
    for label, p in (('_harness/stub.js', STUB_SRC),):
        st = os.stat(p)
        out[label] = {'sha256': sha256_file(p), 'bytes': st.st_size,
                      'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                             time.localtime(st.st_mtime)),
                      'path': p}
    for name in sorted({s['file'] for s in SCRIPT['closed']} | {SCRIPT['forming']['file']}):
        p = os.path.join(HISTORY_DIR, name)
        st = os.stat(p)
        out['history/' + name] = {'sha256': sha256_file(p), 'bytes': st.st_size,
                                  'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                                         time.localtime(st.st_mtime)),
                                  'path': p}
    return out


def verify_script_text(sources):
    """The fixture's PT-BR must still be IN the history files it claims.

    An instrument that cannot say NO is worthless: if the transcript moves, the
    caption text would become a silent invention. This refuses to run instead.
    """
    for item in SCRIPT['closed'] + [SCRIPT['forming']]:
        rel = 'history/' + item['file']
        p = sources[rel]['path']
        with open(p, encoding='utf-8') as fh:
            lines = fh.read().splitlines()
        idx = item['line'] - 1
        if idx < 0 or idx >= len(lines):
            raise SystemExit('FATAL: %s has no line %d' % (p, item['line']))
        if item['text'] not in lines[idx]:
            raise SystemExit(
                'FATAL: %s:%d no longer contains the fixture line %r'
                % (p, item['line'], item['text'][:60]))
        for key in ('prefix',):
            if item[key] and item[key] not in item['text']:
                raise SystemExit('FATAL: prefix %r is not a prefix of %r'
                                 % (item[key], item['text'][:40]))
        # the panel's own cap: a prefix long enough to split the line is a bug
        if len(item['prefix']) + 1 + len(item['text']) > 90:
            raise SystemExit(
                'FATAL: %s:%d would be split by the panel\'s own SENTENCE_MAX_CHARS'
                % (p, item['line']))
    print('  fixture text verified against %s (5 lines, all still present)'
          % os.path.basename(HISTORY_DIR))


# ---------------------------------------------------------------------------
# the generated fixture
# ---------------------------------------------------------------------------

GEOMETRY_CSS = """/* GENERATED FIXTURE COPY — do not hand-edit.
 *
 * Written by H:\\aireplay\\_main\\render-panel-temas.py.
 *
 * WHY THIS FILE EXISTS. Measured on this box: `--dump-dom` sees the window at a
 * CLAMPED size (500x805 for a 380x900 request) and never sees a resize, while
 * `--screenshot` resizes to `--window-size` first. So a metrics pass and a shot
 * run with the same flags would describe TWO DIFFERENT LAYOUTS. Pinning the
 * layout box to the panel's real window (PANEL_WIDTH x PANEL_HEIGHT, 380x900)
 * makes both passes describe the same one, and `metrics.panelRect` is asserted
 * against 380x900 so a failure to pin is LOUD rather than silent.
 *
 * It changes nothing the owner sees: with `--window-size=380,900` the viewport
 * is already 380x900, and `body{position:relative}` gives `.panel`
 * (`position:absolute; inset:0`) a containing block of exactly the same box.
 */
html,
body {
  width: 380px;
  height: 900px;
  overflow: hidden;
}

body {
  position: relative;
}
"""

DRIVER_JS = r"""/* GENERATED FIXTURE COPY — do not hand-edit.
 *
 * Written by H:\aireplay\_main\render-panel-temas.py.
 *
 * Runs AFTER panel.js. It (1) applies the theme the documented way — one
 * attribute write on <html>, which is the whole shipped mechanism — (2) drives
 * the REAL panel.js through the REAL bridge stub with a realistic PT-BR caption
 * state, and (3) writes the COMPUTED STYLE that defines this theme into a hidden
 * <pre id="fixture-metrics">, so the capture carries its own numbers and the
 * receipt cannot be written from impression.
 *
 * It writes NO caption DOM itself. Every caption line, span, rail and LED in the
 * picture was built by the panel's own `panel.js` — which matters here, because
 * another lane is changing that file while this runs.
 */
(function () {
  'use strict';

  var SOURCES = __SOURCES__;
  var SCRIPT = __SCRIPT__;
  var params = new URLSearchParams(location.search || '');
  var theme = params.get('theme') || 'theme-1';
  var wanted = __THEMES__;
  var label = wanted[theme] || theme;

  /* ── 1. THE THEME, THE SHIPPED WAY ─────────────────────────────────────────
   * `data-theme` on <html> IS the mechanism (`theme-switcher.js` writes it, all
   * five stylesheets are scoped to it). `SottoTheme.set` is used when present so
   * the module's own bookkeeping (the picker button's swatch and label) follows;
   * the raw attribute write is the fallback. */
  function applyTheme() {
    if (window.SottoTheme && typeof window.SottoTheme.set === 'function') {
      window.SottoTheme.set(theme, { persist: false });
    }
    document.documentElement.dataset.theme = theme;
  }
  applyTheme();

  /* ── 2. HOLD THE STREAM OPEN, WITHOUT CHANGING THE PANEL ───────────────────
   * A live stream never stops, so the panel's 1500 ms hold deadline never fires
   * mid-sentence. The fixture cannot keep pushing fragments — `ingest()`
   * DUPLICATES the words when the same cumulative fragment arrives twice with a
   * live buffer — so it extends the deadline instead. This is a FIXTURE KNOB on
   * one exported number; the shipped constant is untouched in the repo. */
  if (window.SottoFormulation) {
    window.SottoFormulation.COMMIT_MAX_HOLD_MS = 10 * 60 * 1000;
  }

  /* ── 3. THE CAPTION STATE ──────────────────────────────────────────────────
   * Segments are 12 s apart in AUDIO time, which is more than the panel's own
   * SENTENCE_GAP_S=8 s, so each segment is closed by an `audio-gap` commit —
   * the same route a real pause produces. The forming segment is last and is
   * never closed.
   *
   * The feed runs on DOMContentLoaded, not at parse time: `panel.js` subscribes
   * `bridge.onCaption` in its own init block and the stub is a plain event bus,
   * so a fragment pushed before that subscription would simply be lost. It is
   * pushed ONCE — a second push of a cumulative fragment duplicates words. */
  var GAP = 12.0;
  function push(text, meta) { window.sotto.pushCaption(text, meta); }

  var scriptRows = [];
  var lastMeta = null;
  function feed() {
    var t = 0.0;
    for (var i = 0; i < SCRIPT.closed.length; i += 1) {
      var c = SCRIPT.closed[i];
      push(c.prefix, { start: t, end: t + 1.4, final: false });
      push(c.text, { start: t, end: t + 3.6, final: true });
      scriptRows.push({ kind: 'closed', text: c.text, source: c.file + ':' + c.line });
      t += GAP;
    }
    var f = SCRIPT.forming;
    push(f.prefix, { start: t, end: t + 1.6, final: false });
    push(f.text, { start: t, end: t + 3.9, final: false });
    scriptRows.push({ kind: 'forming', text: f.text, source: f.file + ':' + f.line,
                      confirmed: f.prefix });
    lastMeta = { start: t, end: t + 3.9, final: false };
  }

  var fed = false;
  function feedOnce() {
    if (fed) return;
    if (!window.sotto || typeof window.sotto.pushCaption !== 'function') return;
    if (!document.getElementById('caption-list')) return;
    fed = true;
    feed();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', feedOnce);
  } else {
    feedOnce();
  }
  /* One safety net, never a re-feed: if the panel had not subscribed yet, try
   * again shortly. `fed` is set before the push, so this cannot double-push. */
  setTimeout(function () {
    if (!document.querySelector('#caption-list .caption')) {
      fed = false;
      feedOnce();
    }
  }, 700);

  /* ── 3b. FORCE THE BUNDLED TYPEFACES TO LOAD ───────────────────────────────
   * `document.fonts.check()` answers about faces that are LOADED, and a face
   * only loads when some text uses it — so an unchecked bundle would look like
   * five missing families. Loading all five explicitly makes the check a real
   * question ("is the bundled file present and usable?"), and it paints nothing
   * the theme did not already ask for. */
  var FAMILIES = ['Barlow Condensed', 'IBM Plex Mono', 'Newsreader', 'Fraunces',
                  'Space Grotesk'];
  if (document.fonts && document.fonts.load) {
    FAMILIES.forEach(function (f) {
      try {
        document.fonts.load('400 16px "' + f + '"');
        document.fonts.load('700 16px "' + f + '"');
      } catch (e) {}
    });
  }

  /* ── 4. THE NUMBERS ────────────────────────────────────────────────────────
   * Only computed style, geometry and font-loading facts. Nothing is inferred
   * and nothing is defaulted: a selector that is not in this revision comes back
   * as null and is NAMED in `missing`, so an absent element is visible rather
   * than silently reported as a style. */
  var FONT_PROPS = ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'color',
                    'lineHeight', 'letterSpacing', 'textTransform', 'textShadow',
                    'textAlign', 'fontVariantNumeric', 'wordSpacing'];
  var BOX_PROPS = ['display', 'width', 'height', 'backgroundColor', 'backgroundImage',
                   'borderColor', 'borderLeftWidth', 'borderLeftStyle', 'borderLeftColor',
                   'borderRadius', 'boxShadow', 'padding', 'paddingLeft', 'marginTop',
                   'opacity', 'gap', 'flexDirection', 'gridTemplateColumns', 'position'];

  function pick(el, props) {
    if (!el) return null;
    var cs = getComputedStyle(el);
    var o = {};
    for (var i = 0; i < props.length; i += 1) o[props[i]] = cs[props[i]];
    return o;
  }
  function q(sel) { try { return document.querySelector(sel); } catch (e) { return null; } }
  function qa(sel) { try { return document.querySelectorAll(sel); } catch (e) { return []; } }
  function rect(el) {
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
             x: Math.round(r.left * 10) / 10, y: Math.round(r.top * 10) / 10,
             clientW: el.clientWidth, clientH: el.clientHeight,
             scrollW: el.scrollWidth, scrollH: el.scrollHeight };
  }
  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function classesOf(el) {
    if (!el) return null;
    var out = [];
    for (var i = 0; i < el.children.length; i += 1) {
      out.push({ tag: el.children[i].tagName,
                 cls: String(el.children[i].className || ''),
                 text: String(el.children[i].textContent || '').slice(0, 80) });
    }
    return out;
  }

  var TOKENS = ['--accent', '--accent-soft', '--accent-from', '--accent-to',
                '--accent-gradient', '--font-sans', '--font-mono', '--font',
                '--size-caption', '--size-closed', '--size-time', '--leading-caption',
                '--leading-closed', '--weight-caption', '--weight-closed',
                '--tracking-caption', '--caption-upper', '--radius', '--space-3',
                '--line', '--line-strong', '--text-primary', '--text-secondary',
                '--text-muted', '--text-provisional', '--ok', '--error'];

  function measure() {
    var missing = [];
    function need(sel) {
      var el = q(sel);
      if (!el) missing.push(sel);
      return el;
    }

    var closedRow = need('#caption-list .caption:not(.caption--provisional)');
    var latestRow = q('#caption-list .caption--latest');
    var formingRow = need('#caption-list .caption--provisional');
    var panel = need('.panel');
    var statusDot = q('.status__dot');
    var themeButton = q('#theme-button');

    var tokens = {};
    for (var i = 0; i < TOKENS.length; i += 1) tokens[TOKENS[i]] = token(TOKENS[i]);

    /* DID THE BUNDLED TYPEFACE ACTUALLY LOAD? A computed `fontFamily` still
     * NAMES a family that failed to load and is painting a fallback, so the
     * stack is checked with the Font Loading API as well. */
    var fonts = { status: (document.fonts && document.fonts.status) || 'no-api', check: {} };
    for (var j = 0; j < FAMILIES.length; j += 1) {
      fonts.check[FAMILIES[j]] = {
        w400: document.fonts ? document.fonts.check('400 16px "' + FAMILIES[j] + '"') : null,
        w700: document.fonts ? document.fonts.check('700 16px "' + FAMILIES[j] + '"') : null
      };
    }

    var rowsOut = [];
    var list = q('#caption-list');
    if (list) {
      for (var k = 0; k < list.children.length; k += 1) {
        var li = list.children[k];
        rowsOut.push({
          cls: String(li.className || ''),
          text: String(li.textContent || ''),
          children: classesOf(li)
        });
      }
    }

    return {
      fixture: 'generated-copy',
      generator: 'H:\\aireplay\\_main\\render-panel-temas.py',
      generatorNotice: 'GENERATED FIXTURE COPY of the Sotto panel document — not the app, '
                     + 'not hand-edited. Rendered by Chrome headless; no window was opened.',
      builtFrom: SOURCES,
      theme: document.documentElement.dataset.theme,
      themeLabel: label,
      surface: document.body.getAttribute('data-surface'),
      viewport: { innerW: innerWidth, innerH: innerHeight, dpr: devicePixelRatio },
      panelRect: rect(panel),
      geometryPin: { expected: [380, 900], ok: null },
      tokens: tokens,
      fonts: fonts,
      header: {
        panel: pick(panel, BOX_PROPS),
        panelBefore: (function () {
          try { return panel ? pick2(getComputedStyle(panel, '::before')) : null; }
          catch (e) { return null; }
        })(),
        header: pick(q('.panel__header'), BOX_PROPS),
        wordmarkName: pick(q('.wordmark__name'), FONT_PROPS),
        wordmarkTag: pick(q('.wordmark__tag'), FONT_PROPS),
        controls: pick(q('.panel__controls'), BOX_PROPS),
        themeButton: pick(themeButton, FONT_PROPS.concat(['backgroundColor', 'borderColor'])),
        themeButtonRect: rect(themeButton)
      },
      chrome: {
        bars: qa('.chrome').length,
        meter: pick(q('.chrome__meter i'), BOX_PROPS),
        headerChrome: pick(q('.panel__header .chrome'), BOX_PROPS),
        footerChrome: pick(q('.status .chrome'), BOX_PROPS)
      },
      liveBar: {
        label: pick(q('#live-label'), FONT_PROPS),
        bar: pick(q('.captions__bar'), BOX_PROPS),
        hint: pick(q('#captions-hint'), FONT_PROPS)
      },
      closed: {
        count: qa('#caption-list .caption:not(.caption--provisional)').length,
        row: pick(closedRow, BOX_PROPS),
        text: pick(closedRow ? closedRow.querySelector('.caption__text') : null, FONT_PROPS),
        time: pick(closedRow ? closedRow.querySelector('.caption__time') : null, FONT_PROPS),
        index: pick(closedRow ? closedRow.querySelector('.caption__index') : null, FONT_PROPS),
        led: pick(closedRow ? closedRow.querySelector('.caption__led') : null, BOX_PROPS)
      },
      latest: {
        present: Boolean(latestRow),
        text: pick(latestRow ? latestRow.querySelector('.caption__text') : null, FONT_PROPS),
        row: pick(latestRow, BOX_PROPS)
      },
      forming: {
        present: Boolean(formingRow),
        row: pick(formingRow, BOX_PROPS),
        text: pick(formingRow ? formingRow.querySelector('.caption__text') : null, FONT_PROPS),
        confirmed: pick(formingRow ? formingRow.querySelector('.caption__confirmed') : null,
                        FONT_PROPS),
        provisional: pick(formingRow ? formingRow.querySelector('.caption__provisional') : null,
                          FONT_PROPS),
        led: pick(formingRow ? formingRow.querySelector('.caption__led') : null, BOX_PROPS),
        index: pick(formingRow ? formingRow.querySelector('.caption__index') : null, FONT_PROPS),
        mark: pick(formingRow ? formingRow.querySelector('.caption__mark') : null, FONT_PROPS),
        word: pick(formingRow ? formingRow.querySelector('.caption__word') : null, FONT_PROPS),
        wordCount: formingRow ? formingRow.querySelectorAll('.caption__word').length : 0,
        railPresent: formingRow
          ? parseFloat(getComputedStyle(formingRow).borderLeftWidth) > 0 : null,
        haloPresent: formingRow
          ? getComputedStyle(formingRow.querySelector('.caption__text') || formingRow).textShadow
            !== 'none' : null
      },
      status: {
        block: pick(q('.status'), BOX_PROPS),
        dot: pick(statusDot, BOX_PROPS),
        text: pick(q('#status-text'), FONT_PROPS),
        textValue: (q('#status-text') || {}).textContent || null,
        hint: pick(q('.status__hint'), FONT_PROPS)
      },
      hud: {
        source: (q('#hud-source') || {}).textContent || null,
        state: (q('#hud-state') || {}).textContent || null,
        rows: qa('#hud-rows .hud__row').length,
        label: pick(q('#hud-rows dt'), FONT_PROPS),
        value: pick(q('#hud-rows dd'), FONT_PROPS)
      },
      history: {
        cls: (q('#history') || {}).className || null,
        note: (q('#history-status') || {}).textContent || null,
        barNote: (q('#transcript-note') || {}).textContent || null,
        rows: qa('#history-list .hist').length
      },
      geometry: {
        captions: rect(q('.captions')),
        captionsBody: rect(q('.captions__body')),
        list: rect(q('#caption-list')),
        history: rect(q('#history')),
        hud: rect(q('.hud')),
        status: rect(q('.status')),
        header: rect(q('.panel__header'))
      },
      script: scriptRows,
      missing: missing,
      measuredAt: new Date().toISOString()
    };
  }

  /* getComputedStyle(el, '::before') returns a read-only declaration; copy the
   * handful of properties worth reporting out of it. */
  function pick2(cs) {
    return { backgroundImage: cs.backgroundImage, backgroundColor: cs.backgroundColor,
             height: cs.height, opacity: cs.opacity, content: cs.content };
  }

  var out = document.createElement('pre');
  out.id = 'fixture-metrics';
  out.hidden = true;
  out.textContent = '';
  document.body.appendChild(out);

  function publish() {
    try {
      var m = measure();
      m.geometryPin.ok = Boolean(m.panelRect && m.panelRect.w === 380 && m.panelRect.h === 900);
      out.textContent = JSON.stringify(m, null, 1);
    } catch (err) {
      out.textContent = JSON.stringify({ fixture: 'generated-copy',
        error: String(err && err.stack || err) });
    }
  }

  /* The metrics are republished on a timer, so whatever instant Chrome dumps the
   * DOM at, the numbers describe THAT layout and not an earlier one. */
  publish();
  setInterval(publish, 250);
  window.addEventListener('resize', publish);
  setTimeout(applyTheme, 0);
  setTimeout(applyTheme, 300);

  window.__fixtureMetrics = function () { return out.textContent; };

  __PUBLISH__

  console.log('FIXTURE COPY (generated) theme=' + theme + ' label=' + label);
}());
"""

COMPARE_HTML = """<!doctype html>
<!-- GENERATED FIXTURE COPY — do not hand-edit.
     Written by H:\\aireplay\\_main\\render-panel-temas.py.
     A contact sheet of FIVE REAL PANEL DOCUMENTS, one per theme, each rendered
     by Chrome in its own <iframe> at the panel's real 380x900 geometry. The
     per-column numbers under each panel are the ones THAT IFRAME MEASURED and
     posted back — not a transcription. -->
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="generator" content="H:\\aireplay\\_main\\render-panel-temas.py — GENERATED FIXTURE COPY" />
    <title>Sotto — os cinco temas lado a lado (FIXTURE COPY)</title>
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      html, body { background: #07090c; color: #e8edf4;
        font: 13px/1.4 "Segoe UI", system-ui, sans-serif; }
      header { padding: 10px 14px 6px; }
      header h1 { font-size: 15px; font-weight: 600; letter-spacing: .02em; }
      header p { color: #93a1b5; font-size: 11.5px; margin-top: 3px; }
      .row { display: flex; gap: 10px; padding: 8px 14px 14px; align-items: flex-start; }
      .col { width: 380px; flex: none; }
      .meta { height: 78px; padding: 6px 8px; background: #0d1117;
        border: 1px solid #1d2530; border-radius: 6px; margin-bottom: 6px; }
      .meta h2 { font-size: 13px; font-weight: 700; margin-bottom: 3px; }
      .meta .kv { color: #93a1b5; font-size: 11px; font-family: Consolas, monospace;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .meta .accent { display: inline-block; width: 9px; height: 9px; border-radius: 99px;
        margin-right: 5px; vertical-align: -1px; }
      iframe { width: 380px; height: 900px; border: 1px solid #1d2530; border-radius: 6px;
        display: block; background: #0b0f14; }
    </style>
  </head>
  <body>
    <header>
      <h1>Os cinco temas do painel — cinco documentos REAIS lado a lado</h1>
      <p>GENERATED FIXTURE COPY · Chrome headless, 380×900 por tema (a geometria real do
         painel) · os números de cada coluna foram medidos pelo próprio iframe</p>
    </header>
    <div class="row" id="row"></div>
    <script src="compare-driver.js"></script>
  </body>
</html>
"""

COMPARE_DRIVER_JS = r"""/* GENERATED FIXTURE COPY — do not hand-edit.
 *
 * Written by H:\aireplay\_main\render-panel-temas.py.
 * Builds the five columns and collects each iframe's OWN metrics over
 * postMessage (a file:// parent cannot read a file:// child's DOM). A column
 * whose metrics never arrive says so out loud instead of showing a blank.
 */
(function () {
  'use strict';
  var THEMES = __THEMES_LIST__;
  var row = document.getElementById('row');
  var got = {};

  function kv(label, value) {
    var d = document.createElement('div');
    d.className = 'kv';
    d.textContent = label + ': ' + value;
    return d;
  }

  THEMES.forEach(function (t) {
    var col = document.createElement('div');
    col.className = 'col';
    col.dataset.themeName = t.name;

    var meta = document.createElement('div');
    meta.className = 'meta';
    var h = document.createElement('h2');
    h.textContent = t.index + ' · ' + t.label;
    meta.appendChild(h);
    var pending = kv('medido', 'a aguardar o iframe…');
    pending.dataset.pending = '1';
    meta.appendChild(pending);
    col.appendChild(meta);

    var f = document.createElement('iframe');
    f.src = 'panel-fixture.html?theme=' + t.name;
    f.title = t.label + ' — o documento real do painel com este tema';
    f.setAttribute('data-theme-name', t.name);
    col.appendChild(f);
    row.appendChild(col);
    t.meta = meta;
  });

  window.addEventListener('message', function (ev) {
    var d = ev.data;
    if (!d || d.sottoFixture !== true) return;
    got[d.theme] = d.metrics;
    paint(d.theme);
  });

  function paint(name) {
    var t = null;
    for (var i = 0; i < THEMES.length; i += 1) if (THEMES[i].name === name) t = THEMES[i];
    if (!t) return;
    var m = got[name];
    if (!m) return;
    var tok = m.tokens || {};
    var fm = m.forming || {};
    var cf = fm.confirmed || {};
    var cl = (m.closed || {}).text || {};
    while (t.meta.childNodes.length > 1) t.meta.removeChild(t.meta.lastChild);
    var head = document.createElement('div');
    head.className = 'kv';
    var dot = document.createElement('span');
    dot.className = 'accent';
    dot.style.background = tok['--accent'] || '#888';
    head.appendChild(dot);
    head.appendChild(document.createTextNode(
      (tok['--accent'] || '?') + '  ·  ' + String(cf.fontFamily || '?').split(',')[0].replace(/"/g, '')));
    t.meta.appendChild(head);
    t.meta.appendChild(kv('fechada', String(cl.fontSize || '?') + ' / ' + String(cl.fontWeight || '?')
      + '  ' + String(cl.fontFamily || '?').split(',')[0].replace(/"/g, '')));
    t.meta.appendChild(kv('em formação', String((fm.text || {}).fontSize || '?')
      + '  rail=' + (fm.railPresent ? String((fm.row || {}).borderLeftWidth || 'sim') : 'não')
      + '  halo=' + (fm.haloPresent ? 'sim' : 'não')));
    t.meta.appendChild(kv('painel', (m.panelRect ? m.panelRect.w + '×' + m.panelRect.h : '?')
      + '  linhas=' + (m.closed ? m.closed.count : '?') + '+1'
      + '  pin=' + (m.geometryPin && m.geometryPin.ok ? 'ok' : 'FALHOU')));
  }

  /* Each child republishes on a timer; the parent answers with its own summary
   * so the dump of THIS page also carries the five sets. */
  window.__compareReport = function () {
    var out = { fixture: 'generated-copy', received: Object.keys(got) };
    out.themes = {};
    for (var k in got) if (Object.prototype.hasOwnProperty.call(got, k)) {
      var m = got[k];
      out.themes[k] = { accent: (m.tokens || {})['--accent'],
        fontSans: (m.tokens || {})['--font-sans'],
        closedCount: (m.closed || {}).count,
        formingPresent: (m.forming || {}).present,
        rail: (m.forming || {}).railPresent, halo: (m.forming || {}).haloPresent,
        panelRect: m.panelRect, pinOk: m.geometryPin && m.geometryPin.ok };
    }
    return out;
  };
  setInterval(function () {
    var pre = document.getElementById('fixture-compare-metrics');
    if (!pre) {
      pre = document.createElement('pre');
      pre.id = 'fixture-compare-metrics';
      pre.hidden = true;
      document.body.appendChild(pre);
    }
    pre.textContent = JSON.stringify(window.__compareReport(), null, 1);
  }, 250);
}());
"""

# the child republishes its metrics to the parent, so the contact sheet can label
# each column with what that iframe really measured.
PUBLISH_JS = r"""
  /* postMessage to the comparison sheet: a file:// parent cannot read a file://
   * child's DOM, and the column labels must be MEASURED, not transcribed. */
  if (window.parent && window.parent !== window) {
    setInterval(function () {
      try {
        window.parent.postMessage({ sottoFixture: true, theme: theme,
          metrics: JSON.parse(out.textContent) }, '*');
      } catch (e) {}
    }, 300);
  }
"""


def build_fixture(sources):
    """Write the GENERATED FIXTURE COPY. Every file here is produced, none edited."""
    if os.path.isdir(FIXTURE_DIR):
        shutil.rmtree(FIXTURE_DIR)
    os.makedirs(os.path.join(FIXTURE_DIR, 'themes'), exist_ok=True)
    os.makedirs(os.path.join(FIXTURE_DIR, 'fonts'), exist_ok=True)

    for rel in ASSETS:
        src = os.path.join(PANEL_DIR, rel.replace('/', os.sep))
        dst = os.path.join(FIXTURE_DIR, rel.replace('/', os.sep))
        if os.path.abspath(src) == os.path.abspath(dst):
            raise SystemExit('FATAL: refusing to copy a file onto itself: %s' % src)
        shutil.copy2(src, dst)
    for name in sorted(os.listdir(os.path.join(PANEL_DIR, 'fonts'))):
        src = os.path.join(PANEL_DIR, 'fonts', name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(FIXTURE_DIR, 'fonts', name))
    shutil.copy2(STUB_SRC, os.path.join(FIXTURE_DIR, 'stub.js'))

    # ---- the generated document -------------------------------------------------
    src_html = os.path.join(PANEL_DIR, 'panel.html')
    with open(src_html, encoding='utf-8') as fh:
        html = fh.read()

    digest = hashlib.sha256()
    for rel in sorted(sources):
        digest.update(rel.encode('utf-8'))
        digest.update(sources[rel]['sha256'].encode('ascii'))
    combined = digest.hexdigest().upper()

    banner = (
        '<!-- ===================================================================\n'
        '     GENERATED FIXTURE COPY — DO NOT HAND-EDIT.\n'
        '     Produced by H:\\aireplay\\_main\\render-panel-temas.py from the LIVE\n'
        '     Sotto panel document. It is a COPY, taken at the revision recorded\n'
        '     in `fixture-driver.js` (builtFrom) and in\n'
        '     H:\\aireplay\\_main\\panel-temas-manifest.json.\n'
        '     Combined source sha256: %s\n'
        '     It is NOT the app: the shell bridge is the audit harness stub, the\n'
        '     captions are a fixture, and `fixture-geometry.css` pins the layout\n'
        '     to 380x900 so the metrics pass and the capture describe one layout.\n'
        '     =================================================================== -->\n'
        % combined)
    html = banner + html

    anchors = [
        ('<link rel="stylesheet" href="panel.css" />',
         '<link rel="stylesheet" href="panel.css" />\n'
         '    <link rel="stylesheet" href="fixture-geometry.css" />'),
        ('<script src="surface.js"></script>',
         '<script src="stub.js"></script>\n    <script src="surface.js"></script>'),
        ('<script src="panel.js"></script>',
         '<script src="panel.js"></script>\n    <script src="fixture-driver.js"></script>'),
    ]
    for needle, replacement in anchors:
        if needle not in html:
            raise SystemExit(
                'FATAL: panel.html no longer contains %r — the panel document changed '
                'shape and this fixture generator must be updated' % needle)
        html = html.replace(needle, replacement, 1)

    if '<title>Sotto</title>' not in html:
        raise SystemExit('FATAL: panel.html no longer has <title>Sotto</title>')
    html = html.replace('<title>Sotto</title>', '<title>Sotto — FIXTURE COPY</title>', 1)
    html = html.replace(
        '<html lang="en" data-theme="theme-1">',
        '<html lang="en" data-theme="theme-1" data-fixture="generated-copy" '
        'data-fixture-source-sha256="%s">' % combined, 1)
    if 'data-fixture="generated-copy"' not in html:
        raise SystemExit('FATAL: could not mark <html> as a generated copy')

    with open(os.path.join(FIXTURE_DIR, 'panel-fixture.html'), 'w',
              encoding='utf-8', newline='\n') as fh:
        fh.write(html)

    # the 1920x1080 control arm: the same document WITHOUT the geometry pin, so
    # the brief's literal flag can be seen doing what it really does.
    wide = html.replace('    <link rel="stylesheet" href="fixture-geometry.css" />\n', '', 1)
    with open(os.path.join(FIXTURE_DIR, 'panel-fixture-wide.html'), 'w',
              encoding='utf-8', newline='\n') as fh:
        fh.write(wide)

    # ---- the generated fixture CSS / JS ----------------------------------------
    with open(os.path.join(FIXTURE_DIR, 'fixture-geometry.css'), 'w',
              encoding='utf-8', newline='\n') as fh:
        fh.write(GEOMETRY_CSS)

    driver = DRIVER_JS.replace('__SOURCES__', json.dumps(
        {k: {'sha256': v['sha256'], 'bytes': v['bytes'], 'mtime': v['mtime']}
         for k, v in sorted(sources.items())}, indent=1))
    driver = driver.replace('__SCRIPT__', json.dumps(SCRIPT, indent=1))
    driver = driver.replace('__THEMES__', json.dumps(
        {name: label for _, name, _, label in THEMES}))
    if '__PUBLISH__' not in driver:
        raise SystemExit('FATAL: the driver template lost its __PUBLISH__ anchor')
    driver = driver.replace('__PUBLISH__', PUBLISH_JS.strip('\n'), 1)
    for leftover in ('__SOURCES__', '__SCRIPT__', '__THEMES__', '__PUBLISH__'):
        if leftover in driver:
            raise SystemExit('FATAL: %s was not substituted in the driver' % leftover)
    with open(os.path.join(FIXTURE_DIR, 'fixture-driver.js'), 'w',
              encoding='utf-8', newline='\n') as fh:
        fh.write(driver)

    with open(os.path.join(FIXTURE_DIR, 'compare.html'), 'w',
              encoding='utf-8', newline='\n') as fh:
        fh.write(COMPARE_HTML)
    with open(os.path.join(FIXTURE_DIR, 'compare-driver.js'), 'w',
              encoding='utf-8', newline='\n') as fh:
        fh.write(COMPARE_DRIVER_JS.replace('__THEMES_LIST__', json.dumps(
            [{'index': i, 'name': n, 'label': l} for i, n, _, l in THEMES], indent=1)))

    return combined


# ---------------------------------------------------------------------------
# running Chrome
# ---------------------------------------------------------------------------


class Runner:
    def __init__(self, census):
        self.census = census
        self.log = []
        self.timeouts = 0

    def run(self, extra, tag, timeout=180):
        cmd = [CHROME] + BASE_FLAGS + ['--user-data-dir=' + PROFILE_DIR] + extra
        env = os.environ.copy()
        env.update({'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
                    'MKL_NUM_THREADS': '2', 'NUMBER_OF_PROCESSORS': '2'})
        t0 = time.time()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding='utf-8', errors='replace',
                             env=env, creationflags=CREATE_NO_WINDOW)
        self.census.track(p.pid)
        timed_out = False
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self.timeouts += 1
            kill_tree(p.pid, 'timeout:' + tag)
            out, err = p.communicate()
        finally:
            kill_tree(p.pid, 'cleanup:' + tag)
            self.census.untrack(p.pid)
        entry = {'tag': tag, 'rc': p.returncode, 'seconds': round(time.time() - t0, 2),
                 'timed_out': timed_out, 'stderr_tail': (err or '')[-400:]}
        self.log.append(entry)
        return out or '', entry


def parse_metrics(dom):
    """Pull the JSON out of <pre id="fixture-metrics"> in a --dump-dom dump."""
    m = re.search(r'<pre id="fixture-metrics"[^>]*>(.*?)</pre>', dom, re.S)
    if not m:
        return None, 'no <pre id="fixture-metrics"> in the DOM dump'
    raw = m.group(1)
    for a, b in (('&quot;', '"'), ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                 ('&#39;', "'")):
        raw = raw.replace(a, b)
    try:
        return json.loads(raw), None
    except ValueError as exc:
        return None, 'metrics JSON did not parse: %s' % exc


def png_size(path):
    try:
        with open(path, 'rb') as fh:
            head = fh.read(33)
        if head[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        import struct
        w, h = struct.unpack('>II', head[16:24])
        return (w, h)
    except OSError:
        return None


def dir_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


# ---------------------------------------------------------------------------
# one theme
# ---------------------------------------------------------------------------

PAGE = 'file:///' + os.path.join(FIXTURE_DIR, 'panel-fixture.html').replace('\\', '/')
PAGE_WIDE = 'file:///' + os.path.join(FIXTURE_DIR, 'panel-fixture-wide.html').replace('\\', '/')
PAGE_COMPARE = 'file:///' + os.path.join(FIXTURE_DIR, 'compare.html').replace('\\', '/')


def capture_theme(runner, index, name, slug, label):
    """Metrics pass + capture pass for one theme. Returns a result dict."""
    res = {'index': index, 'theme': name, 'slug': slug, 'label': label, 'problems': []}

    dom, entry = runner.run(
        ['--window-size=%d,%d' % (PANEL_W, PANEL_H),
         '--force-device-scale-factor=%d' % CAPTURE_SCALE,
         '--virtual-time-budget=%d' % BUDGET_MS,
         '--dump-dom', PAGE + '?theme=' + name],
        'metrics-%s' % name)
    res['metrics_run'] = entry
    metrics, why = parse_metrics(dom)
    if metrics is None:
        res['problems'].append('metrics: ' + why)
    res['metrics'] = metrics

    png = os.path.join(OUT_DIR, 'panel-tema-%d-%s.png' % (index, slug))
    if os.path.exists(png):
        os.remove(png)
    _dom2, entry2 = runner.run(
        ['--window-size=%d,%d' % (PANEL_W, PANEL_H),
         '--force-device-scale-factor=%d' % CAPTURE_SCALE,
         '--virtual-time-budget=%d' % BUDGET_MS,
         '--default-background-color=FF0B0F14',
         '--screenshot=' + png, PAGE + '?theme=' + name],
        'shot-%s' % name)
    res['shot_run'] = entry2
    res['png'] = png
    res['png_size'] = png_size(png)
    res['png_sha256'] = sha256_file(png) if os.path.exists(png) else None

    # ---- the verdicts -------------------------------------------------------
    want = (PANEL_W * CAPTURE_SCALE, PANEL_H * CAPTURE_SCALE)
    if res['png_size'] != want:
        res['problems'].append('png is %s, expected %s' % (res['png_size'], want))
    if metrics:
        if metrics.get('theme') != name:
            res['problems'].append('applied theme is %r, asked for %r'
                                   % (metrics.get('theme'), name))
        pin = metrics.get('geometryPin') or {}
        if not pin.get('ok'):
            res['problems'].append('layout pin failed: panelRect=%s (expected 380x900)'
                                   % (metrics.get('panelRect'),))
        closed = (metrics.get('closed') or {}).get('count')
        if not closed:
            res['problems'].append('no closed caption line was rendered')
        if not (metrics.get('forming') or {}).get('present'):
            res['problems'].append('no provisional (forming) caption line was rendered')
        if not (metrics.get('forming') or {}).get('wordCount'):
            res['problems'].append('the forming line has no .caption__word spans')
        fonts = metrics.get('fonts') or {}
        if fonts.get('status') != 'loaded':
            res['problems'].append('document.fonts.status=%r (the bundled typeface may '
                                   'not have loaded)' % fonts.get('status'))
        if metrics.get('missing'):
            res['problems'].append('selectors absent in this revision: %s'
                                   % ', '.join(metrics['missing']))
    return res


def capture_wide(runner, index, name, slug):
    """The brief's literal --window-size=1920,1080, WITHOUT the geometry pin."""
    png = os.path.join(OUT_DIR, 'panel-tema-%d-%s-1920x1080.png' % (index, slug))
    if os.path.exists(png):
        os.remove(png)
    _dom, entry = runner.run(
        ['--window-size=%d,%d' % (WIDE_W, WIDE_H),
         '--virtual-time-budget=%d' % BUDGET_MS,
         '--default-background-color=FF0B0F14',
         '--screenshot=' + png, PAGE_WIDE + '?theme=' + name],
        'wide-%s' % name)
    return {'theme': name, 'png': png, 'png_size': png_size(png),
            'png_sha256': sha256_file(png) if os.path.exists(png) else None,
            'run': entry}


def capture_compare(runner):
    res = {'problems': []}
    dom, entry = runner.run(
        ['--window-size=%d,%d' % (COMPARE_W, COMPARE_H),
         '--virtual-time-budget=%d' % (BUDGET_MS + 2000),
         '--dump-dom', PAGE_COMPARE],
        'metrics-compare')
    res['metrics_run'] = entry
    m = re.search(r'<pre id="fixture-compare-metrics"[^>]*>(.*?)</pre>', dom, re.S)
    if m:
        raw = m.group(1)
        for a, b in (('&quot;', '"'), ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>')):
            raw = raw.replace(a, b)
        try:
            res['received'] = json.loads(raw)
        except ValueError as exc:
            res['problems'].append('compare metrics did not parse: %s' % exc)
    else:
        res['problems'].append('no <pre id="fixture-compare-metrics"> in the compare dump')

    png = os.path.join(OUT_DIR, 'panel-temas-comparacao.png')
    if os.path.exists(png):
        os.remove(png)
    _d, entry2 = runner.run(
        ['--window-size=%d,%d' % (COMPARE_W, COMPARE_H),
         '--virtual-time-budget=%d' % (BUDGET_MS + 2000),
         '--default-background-color=FF07090C',
         '--screenshot=' + png, PAGE_COMPARE],
        'shot-compare')
    res['shot_run'] = entry2
    res['png'] = png
    res['png_size'] = png_size(png)
    res['png_sha256'] = sha256_file(png) if os.path.exists(png) else None
    if res['png_size'] != (COMPARE_W, COMPARE_H):
        res['problems'].append('comparison png is %s, expected %s'
                               % (res['png_size'], (COMPARE_W, COMPARE_H)))
    recv = (res.get('received') or {}).get('received') or []
    if len(recv) != 5:
        res['problems'].append('the comparison sheet received metrics from %d of 5 '
                               'iframes (%s)' % (len(recv), recv))
    for k, v in ((res.get('received') or {}).get('themes') or {}).items():
        if not v.get('pinOk'):
            res['problems'].append('iframe %s did not pin its geometry' % k)
        if not v.get('formingPresent'):
            res['problems'].append('iframe %s rendered no forming line' % k)
    return res


# ---------------------------------------------------------------------------
# the measurement tables (so the receipt is not transcribed by hand)
# ---------------------------------------------------------------------------


def fam(v):
    if not v:
        return '-'
    return str(v.get('fontFamily', '-')).split(',')[0].strip().strip('"')


def short(v, keys):
    if not v:
        return '-'
    return ' · '.join('%s=%s' % (k, v.get(k)) for k in keys if v.get(k) is not None)


def write_tables(results, compare, sources, census, runner, wide, combined, attempts,
                 drift=None):
    lines = []
    add = lines.append
    add('# Panel theme captures — measured tables (generated)\n')
    add('Generated by `H:\\aireplay\\_main\\render-panel-temas.py`. '
        'Every number below was read out of the live document by the fixture\'s own '
        '`getComputedStyle` pass; none of it is transcribed by hand.\n')
    add('Fixture source revision: combined sha256 `%s`\n' % combined)

    add('\n## 1. What each theme IS, per capture\n')
    add('| # | tema | captura | família (linha fechada) | px | peso | cor de destaque | '
        'linha em formação: família/px/peso | rail (border-left) | halo (text-shadow) |')
    add('|---|---|---|---|---|---|---|---|---|---|')
    for r in results:
        m = r.get('metrics') or {}
        tok = m.get('tokens') or {}
        cl = (m.get('closed') or {}).get('text') or {}
        fm = (m.get('forming') or {})
        ft = fm.get('text') or {}
        row = fm.get('row') or {}
        rail = 'não'
        if fm.get('railPresent'):
            rail = '%s %s %s' % (row.get('borderLeftWidth'), row.get('borderLeftStyle'),
                                 row.get('borderLeftColor'))
        add('| %d | %s | `%s` | %s | %s | %s | `%s` | %s / %s / %s | %s | %s |' % (
            r['index'], r['label'], os.path.basename(r.get('png') or ''),
            fam(cl), cl.get('fontSize', '-'), cl.get('fontWeight', '-'),
            tok.get('--accent', '-'),
            fam(ft), ft.get('fontSize', '-'), ft.get('fontWeight', '-'),
            rail, 'sim' if fm.get('haloPresent') else 'não'))

    add('\n## 2. The three caption states, per theme\n')
    add('| # | tema | fechada: cor/px/peso | em formação — parte CONFIRMADA: cor/px/peso/estilo | '
        'em formação — cauda PROVISÓRIA: cor/px/peso/estilo | a mais recente (`.caption--latest`): cor/px |')
    add('|---|---|---|---|---|---|')
    for r in results:
        m = r.get('metrics') or {}
        cl = (m.get('closed') or {}).get('text') or {}
        fm = m.get('forming') or {}
        cf = fm.get('confirmed') or {}
        pv = fm.get('provisional') or {}
        lt = (m.get('latest') or {}).get('text') or {}
        add('| %d | %s | %s / %s / %s | %s / %s / %s / %s | %s / %s / %s / %s | %s / %s |' % (
            r['index'], r['label'],
            cl.get('color', '-'), cl.get('fontSize', '-'), cl.get('fontWeight', '-'),
            cf.get('color', '-'), cf.get('fontSize', '-'), cf.get('fontWeight', '-'),
            cf.get('fontStyle', '-'),
            pv.get('color', '-'), pv.get('fontSize', '-'), pv.get('fontWeight', '-'),
            pv.get('fontStyle', '-'),
            lt.get('color', '-'), lt.get('fontSize', '-')))

    add('\n## 3. Tokens the theme declares (`:root[data-theme]`)\n')
    add('| # | tema | `--font-sans` | `--font-mono` | `--size-caption` | `--size-closed` | '
        '`--leading-caption` | `--weight-caption` | `--tracking-caption` | `--caption-upper` |')
    add('|---|---|---|---|---|---|---|---|---|---|')
    for r in results:
        tok = ((r.get('metrics') or {}).get('tokens') or {})
        add('| %d | %s | `%s` | `%s` | %s | %s | %s | %s | %s | %s |' % (
            r['index'], r['label'], tok.get('--font-sans', '-'), tok.get('--font-mono', '-'),
            tok.get('--size-caption', '-'), tok.get('--size-closed', '-'),
            tok.get('--leading-caption', '-'), tok.get('--weight-caption', '-'),
            tok.get('--tracking-caption', '-'), tok.get('--caption-upper', '-')))

    add('\n## 4. Header, footer and indicators\n')
    add('| # | tema | wordmark: família/px/peso | botão de tema: px (cliente/conteúdo) | '
        'rodapé (`.status__dot`): px/cor/sombra | barras `.chrome` encontradas | `#hud-source` |')
    add('|---|---|---|---|---|---|---|')
    for r in results:
        m = r.get('metrics') or {}
        wm = ((m.get('header') or {}).get('wordmarkName') or {})
        tb = ((m.get('header') or {}).get('themeButtonRect') or {})
        dot = ((m.get('status') or {}).get('dot') or {})
        clip = ''
        if tb.get('clientW') is not None and tb.get('scrollW') is not None:
            clip = ' (conteúdo %s)' % tb.get('scrollW')
        add('| %d | %s | %s / %s / %s | %s×%s%s | %s×%s / %s / %s | %s | %s |' % (
            r['index'], r['label'], fam(wm), wm.get('fontSize', '-'), wm.get('fontWeight', '-'),
            tb.get('w', '-'), tb.get('h', '-'), clip,
            dot.get('width', '-'), dot.get('height', '-'), dot.get('backgroundColor', '-'),
            dot.get('boxShadow', '-'),
            (m.get('chrome') or {}).get('bars', '-'),
            (m.get('hud') or {}).get('source', '-')))

    add('\n## 5. Geometry and fonts (the instrument checking itself)\n')
    add('| # | tema | `.panel` | viewport visto pelo dump | pin 380×900 | `document.fonts.status` | '
        'famílias que carregaram | linhas fechadas | linha em formação | '
        'lista (`scrollH`) vs caixa (`clientH`) |')
    add('|---|---|---|---|---|---|---|---|---|---|')
    for r in results:
        m = r.get('metrics') or {}
        pr = m.get('panelRect') or {}
        vp = m.get('viewport') or {}
        fonts = m.get('fonts') or {}
        loaded = [f for f, v in (fonts.get('check') or {}).items()
                  if v.get('w400') or v.get('w700')]
        geo = m.get('geometry') or {}
        lst = geo.get('list') or {}
        box = geo.get('captionsBody') or {}
        fits = '-'
        if lst.get('scrollH') is not None and box.get('clientH') is not None:
            fits = '%s vs %s %s' % (lst.get('scrollH'), box.get('clientH'),
                                    'coube' if lst['scrollH'] <= box['clientH'] else 'ROLANDO')
        add('| %d | %s | %s×%s | %s×%s dpr=%s | %s | %s | %s | %s | %s | %s |' % (
            r['index'], r['label'], pr.get('w', '-'), pr.get('h', '-'),
            vp.get('innerW', '-'), vp.get('innerH', '-'), vp.get('dpr', '-'),
            'ok' if (m.get('geometryPin') or {}).get('ok') else 'FALHOU',
            fonts.get('status', '-'), ', '.join(loaded) or '-',
            (m.get('closed') or {}).get('count', '-'),
            'sim' if (m.get('forming') or {}).get('present') else 'NÃO', fits))

    add('\n## 6. The fixture script (real PT-BR, with its provenance)\n')
    add('| linha | proveniência | caracteres | prefixo da parcial | texto |')
    add('|---|---|---|---|---|')
    for item in SCRIPT['closed']:
        add('| fechada | `history/2026-10-06/%s:%d` | %d | `%s` | %s |'
            % (item['file'], item['line'], len(item['text']), item['prefix'], item['text']))
    f = SCRIPT['forming']
    add('| em formação | `history/2026-10-06/%s:%d` | %d | `%s` | %s |'
        % (f['file'], f['line'], len(f['text']), f['prefix'], f['text']))

    add('\n## 7. Revisions read (sha256 of every byte the fixture is built from)\n')
    add('| ficheiro | bytes | mtime | sha256 |')
    add('|---|---|---|---|')
    for rel in sorted(sources):
        v = sources[rel]
        add('| `%s` | %d | %s | `%s` |' % (rel, v['bytes'], v['mtime'], v['sha256']))

    add('\n## 8. The wide control arm (the brief\'s literal `--window-size=1920,1080`)\n')
    add('| # | tema | ficheiro | px | sha256 |')
    add('|---|---|---|---|---|')
    for w in wide:
        add('| %s | %s | `%s` | %s | `%s` |' % (
            next((r['index'] for r in results if r['theme'] == w['theme']), '?'),
            w['theme'], os.path.basename(w['png']), w['png_size'],
            (w['png_sha256'] or '')[:16]))

    add('\n## 9. The comparison sheet\n')
    recv = compare.get('received') or {}
    add('- file: `%s` (%s, sha256 `%s`)' % (os.path.basename(compare.get('png') or ''),
                                           compare.get('png_size'),
                                           (compare.get('png_sha256') or '')[:16]))
    add('- iframes that posted their own metrics: %s' % (recv.get('received') or []))
    for k, v in sorted((recv.get('themes') or {}).items()):
        add('  - `%s` accent `%s` font `%s` closed=%s forming=%s rail=%s halo=%s panel=%s pin=%s'
            % (k, v.get('accent'), v.get('fontSans'), v.get('closedCount'),
               v.get('formingPresent'), v.get('rail'), v.get('halo'),
               v.get('panelRect'), v.get('pinOk')))

    add('\n## 10. Chrome runs, the window census, and the budget\n')
    add('- passes (a pass is 5 themes + comparison + 5 wide controls): %d' % attempts)
    add('- Chrome runs: %d, timeouts: %d' % (len(runner.log), runner.timeouts))
    add('- window census: %d samples at %d ms, **%d visible-window samples**, errors=%d'
        % (census.samples, CENSUS_MS, len(census.visible), len(census.errors)))
    if census.visible:
        for v in census.visible[:10]:
            add('  - VISIBLE pid=%s hwnd=%s class=%r title=%r'
                % (v['pid'], v['hwnd'], v['class'], v['title']))
    add('- disk: fixture %d B, whole `_main` output of this run below 200 MB: see manifest'
        % dir_bytes(FIXTURE_DIR))
    add('')
    if drift:
        add('- **DRIFT AFTER THE PASS:** %d file(s) changed between the capture and the '
            'writing of this table. The pictures are of the revision in section 7, not of '
            'what is on disk now: %s' % (len(drift), ', '.join('`%s`' % d for d in drift)))
    else:
        add('- no file read for this fixture changed between the capture and this table: '
            'the revision in section 7 is what the pictures show.')

    with open(TABLES, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    return TABLES


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description='Render one capture per panel theme.')
    ap.add_argument('--themes', default='1,2,3,4,5',
                    help='comma-separated theme numbers to capture (default all five)')
    ap.add_argument('--no-wide', action='store_true',
                    help='skip the 1920x1080 control arm')
    ap.add_argument('--attempts', type=int, default=3,
                    help='max capture passes; a pass is redone if the panel moved')
    args = ap.parse_args()

    want = [int(x) for x in args.themes.split(',') if x.strip()]
    themes = [t for t in THEMES if t[0] in want]
    if not themes:
        raise SystemExit('FATAL: --themes selected nothing')

    if not os.path.isfile(CHROME):
        raise SystemExit('FATAL: Chrome not found at %s' % CHROME)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)

    print('Sotto theme capture renderer')
    print('  chrome   %s' % CHROME)
    print('  panel    %s  (%dx%d CSS px, dpr %d for the captures)'
          % (PANEL_DIR, PANEL_W, PANEL_H, CAPTURE_SCALE))
    print('  output   %s' % OUT_DIR)

    census = WindowCensus(CENSUS_MS / 1000.0)
    census.start()
    runner = Runner(census)

    attempts = 0
    result = None
    while attempts < max(1, args.attempts):
        attempts += 1
        print('\n=== pass %d ===' % attempts)
        sources = read_sources()
        verify_script_text(sources)
        combined = build_fixture(sources)
        print('  fixture built; combined source sha256 %s' % combined[:16])

        results = []
        for index, name, slug, label in themes:
            print('  [%d/%d] %s (%s)...' % (index, len(themes), name, label))
            r = capture_theme(runner, index, name, slug, label)
            for p in r['problems']:
                print('      PROBLEM: %s' % p)
            results.append(r)

        wide = []
        if not args.no_wide:
            for index, name, slug, label in themes:
                wide.append(capture_wide(runner, index, name, slug))
            print('  wide control arm: %d captures' % len(wide))

        compare = capture_compare(runner)
        for p in compare['problems']:
            print('      PROBLEM: %s' % p)

        # ---- did the panel move while we were shooting? --------------------
        after = read_sources()
        moved = [k for k in sources if sources[k]['sha256'] != after.get(k, {}).get('sha256')]
        added = [k for k in after if k not in sources]
        if moved or added:
            print('  THE PANEL MOVED DURING THE PASS:')
            for k in moved:
                print('    changed  %-28s %s -> %s' % (k, sources[k]['sha256'][:12],
                                                       after[k]['sha256'][:12]))
            for k in added:
                print('    appeared %s' % k)
            if attempts < args.attempts:
                print('  RE-CAPTURING: the captures above are of a revision that no '
                      'longer exists.')
                continue
            print('  attempts exhausted; reporting the LAST pass and saying so.')
        result = {'sources': sources, 'after': after, 'moved': moved, 'added': added,
                  'combined': combined, 'results': results, 'wide': wide,
                  'compare': compare}
        break

    census.stop()
    time.sleep(0.3)

    # ---- did the panel move AFTER the pass? --------------------------------
    # The in-pass check above compares the read at build time with the read right
    # after the last capture. A lane editing the panel can still land a change
    # between that second read and this manifest, and a capture of a revision
    # that no longer exists is a fact the reader must be told, not spared. This is
    # reported as DRIFT, not as a failure: the capture is still a true picture of
    # the revision whose sha256 is written down.
    final = read_sources()
    drift = sorted(k for k in final
                   if result['sources'].get(k, {}).get('sha256') != final[k]['sha256'])
    result['driftAfterPass'] = drift

    # ---- cleanup: our own profile only, by exact path ------------------------
    if os.path.isdir(PROFILE_DIR):
        shutil.rmtree(PROFILE_DIR, ignore_errors=True)

    # ---- disk budget --------------------------------------------------------
    total = dir_bytes(FIXTURE_DIR)
    for r in result['results']:
        for k in ('png',):
            if r.get(k) and os.path.exists(r[k]):
                total += os.path.getsize(r[k])
    for w in result['wide']:
        if w.get('png') and os.path.exists(w['png']):
            total += os.path.getsize(w['png'])
    if result['compare'].get('png') and os.path.exists(result['compare']['png']):
        total += os.path.getsize(result['compare']['png'])
    manifest_bytes = 0
    if os.path.exists(MANIFEST):
        manifest_bytes = os.path.getsize(MANIFEST)
    total += manifest_bytes

    # ---- verdicts -----------------------------------------------------------
    problems = []
    for r in result['results']:
        problems.extend('%s: %s' % (r['theme'], p) for p in r['problems'])
    problems.extend('compare: %s' % p for p in result['compare']['problems'])
    if result['moved'] or result['added']:
        problems.append('the panel moved during the pass and %d attempt(s) did not '
                        'settle it: %s' % (attempts, result['moved'] + result['added']))
    if census.visible:
        problems.append('the window census saw %d VISIBLE window sample(s)'
                        % len(census.visible))
    if runner.timeouts:
        problems.append('%d Chrome run(s) timed out' % runner.timeouts)
    if total > DISK_BUDGET_BYTES:
        problems.append('disk: %d B is over the 200 MB budget' % total)

    tables = write_tables(result['results'], result['compare'], result['sources'],
                          census, runner, result['wide'], result['combined'], attempts,
                          result['driftAfterPass'])

    manifest = {
        'generator': 'H:\\aireplay\\_main\\render-panel-temas.py',
        'fixtureNotice': 'GENERATED FIXTURE COPY of the Sotto panel document.',
        'panelGeometry': {'width': PANEL_W, 'height': PANEL_H, 'captureScale': CAPTURE_SCALE,
                          'why': 'app/webview/sotto_webview.py PANEL_WIDTH/PANEL_HEIGHT; '
                                 'display is 96 dpi (scale 1.0)'},
        'attempts': attempts,
        'combinedSourceSha256': result['combined'],
        'sources': result['sources'],
        'sourcesAfter': result['after'],
        'panelMovedDuringPass': {'changed': result['moved'], 'appeared': result['added']},
        'panelMovedAfterPass': result['driftAfterPass'],
        'themes': [dict(r, metrics=r.get('metrics')) for r in result['results']],
        'wideControl': result['wide'],
        'comparison': result['compare'],
        'chromeRuns': runner.log,
        'windowCensus': {'samples': census.samples, 'interval_ms': CENSUS_MS,
                         'visibleSamples': len(census.visible),
                         'visible': census.visible[:20], 'errors': census.errors},
        'diskBytes': total,
        'diskBudgetBytes': DISK_BUDGET_BYTES,
        'problems': problems,
        'verdict': 'PASS' if not problems else 'FAIL',
        'tables': tables,
    }
    with open(MANIFEST, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)

    # ---- report -------------------------------------------------------------
    print('\n================ RESULT ================')
    for r in result['results']:
        m = r.get('metrics') or {}
        tok = m.get('tokens') or {}
        fm = m.get('forming') or {}
        print('  %-14s %-24s %s  accent=%s  rail=%-4s halo=%-4s closed=%s'
              % (r['theme'], os.path.basename(r.get('png') or ''), r.get('png_size'),
                 tok.get('--accent'), fm.get('railPresent'), fm.get('haloPresent'),
                 (m.get('closed') or {}).get('count')))
    print('  comparison     %s %s' % (os.path.basename(result['compare'].get('png') or ''),
                                      result['compare'].get('png_size')))
    print('  window census  %d samples / %d visible' % (census.samples, len(census.visible)))
    print('  disk           %d B of %d B budget' % (total, DISK_BUDGET_BYTES))
    if result['driftAfterPass']:
        print('  DRIFT AFTER THE PASS: %d file(s) changed since these captures were '
              'taken — the pictures are of the revision in `sources`, not of what is '
              'on disk now:' % len(result['driftAfterPass']))
        for k in result['driftAfterPass']:
            print('    changed  %-28s %s -> %s' % (k, result['sources'][k]['sha256'][:12],
                                                   final[k]['sha256'][:12]))
    print('  manifest       %s' % MANIFEST)
    print('  tables         %s' % tables)
    if problems:
        print('  VERDICT: FAIL')
        for p in problems:
            print('    - %s' % p)
        return 1
    print('  VERDICT: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
