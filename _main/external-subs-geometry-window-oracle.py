"""ORACLE: the external-caption reader must read the VIDEO, and must adopt
the VIDEO's window.

Owner, 2026-10-20, verbatim: *"eu ja mandei tu resolver o negocio de que por
algum motivo texto de outras coisas que nao sao o transcript do video do youtube
fica vazando pro nosso app"*.

TWO HOLES, BOTH MEASURED ON THE OWNER'S OWN MACHINE (2026-10-20).

A) THE READER READ THE PAGE, NOT THE VIDEO.
   `app/webview/external_subs.py:_player_rect` answered "the biggest element
   in the window", and on a YouTube page that answer is the PAGE. Measured in
   the owner's real window (Chrome, hwnd 1710572, title "New top local AI
   image generator is here! - YouTube - Google Chrome"):

       window            (-8, -8, 1928, 1040)
       player_rect       (0, 121, 1905, 4107)   <- the WHOLE PAGE, y=4107 is
                                                   BELOW the window's own
                                                   bottom edge (1040): the
                                                   tree carries the whole
                                                   scrolled document
       band_top          121 + (4107-121)*0.62 = 2592.32   <- the COMMENTS

   The real video element was in the SAME tree the whole time:

       class="html5-video-player ytp-trans"  name="Player de video do YouTube"
       rect=(16, 189, 1354, 942)
       band_top = 189 + (942-189)*0.62 = 655.86  .. 942  <- where YouTube
                                                            PAINTS the caption

   With the wrong band the reader collected, in the reality, 20 pending rows
   of page chrome: comments and recommended-video titles. None of them was a
   caption. A recommended-video title is a perfectly normal sentence, so NO
   vocabulary rule can take it without eating a real caption -- the GEOMETRY
   is what separates the video from the page.

B) A WINDOW THAT IS NOT A PLAYER WAS ADOPTED AS ONE.
   The owner's File Explorer was titled
   "kicktwitchyoutube_instagram - Explorador de Arquivos": "youtube" was a
   FOLDER NAME. The title-only test called it a YouTube player, and the
   census of the 19 visible windows had exactly ONE false positive -- that
   one. Adopting it meant reading the file list as if it were a caption, and
   the video id never came (`edit_values` returned ['_tools', <dates>,
   'Pasta de arquivos', 'cookie-extension']), so the app LOST the real
   YouTube caption.

   A TITLE IS EVIDENCE ONLY IN A BROWSER: a player's title is the TAB's
   title, and a tab only exists in a browser. The URL is the stronger proof
   and it counts whatever the process is.

WHAT THIS PINS (synthetic fixtures, no real window, no browser, no app)
   (a) page rect AND video element present -> the band is inside the video
       and the comments are NOT collected;
   (b) no video element -> the old fallback still reads the window;
   (c) a "youtube" title in a NON-BROWSER is not a player;
   (d) the measured real window (chrome.exe) is still external:youtube;
   (e) a YouTube URL beats the title, whatever the process is;
   (f) find_player_window skips the non-browser and returns the browser's
       window -- and adopts NOTHING when the only candidate is the Explorer;
   (g) the measured real window still yields its video id.

NEGATIVE ARM (executed, not decorative)
   Six textual mutants of the module, each a patch of a unique anchor. A
   mutant whose anchor is missing or ambiguous is DECORATIVE -- it proves
   nothing -- so the oracle refuses to count it. Each mutant is loaded and
   the SAME battery runs; the checks that go RED name it.

It opens nothing, plays nothing, renders no audio, and touches no state of
the owner's app. Its scratch space is a temporary directory of its own.

    python _main/external-subs-geometry-window-oracle.py
    python _main/external-subs-geometry-window-oracle.py --neg-arm
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODULE_PATH = os.path.join(REPO, "app", "webview", "external_subs.py")
VIDEO_CAPTIONS_PATH = os.path.join(REPO, "app", "webview", "youtube_captions.py")

EXIT_PASS = 0
EXIT_FAIL = 1

HWND = 0x00A1B2C3

# ── the fixtures: the owner's own numbers, measured 2026-10-20 ──────────────
#: The owner's real window (Chrome, hwnd 1710572).
WINDOW = (-8, -8, 1928, 1040)
#: What `_player_rect` used to return: the PAGE (the biggest element).
PAGE_RECT = (0, 121, 1905, 4107)
#: The real video element, in the same tree.
VIDEO_RECT = (16, 189, 1354, 942)
#: The band the PAGE rect produces -- inside the COMMENTS.
PAGE_BAND_TOP = 121 + (4107 - 121) * 0.62
#: The band the VIDEO rect produces -- where the caption is painted.
VIDEO_BAND_TOP = 189 + (942 - 189) * 0.62

#: The owner's real window title, and the real File Explorer's.
REAL_TITLE = "New top local AI image generator is here! - YouTube - Google Chrome"
EXPLORER_TITLE = "kicktwitchyoutube_instagram - Explorador de Arquivos"
#: A File Explorer whose folder does NOT say "youtube" -- the case where the
#: URL has to be the only proof there is.
EXPLORER_OTHER_TITLE = "Documentos - Explorador de Arquivos"
#: A window that is not a player at all.
SOTTO_TITLE = "Sotto"

#: The real video id of the owner's window.
REAL_URL = "https://www.youtube.com/watch?v=cUeZMUGCxrw"
REAL_VIDEO_ID = "cUeZMUGCxrw"

#: THE CHROME THE OWNER MEASURED IN THE REALITY (2026-10-20): comments and
#: recommended-video titles. Their y is inside the OLD band (2592.32 ..) and
#: far outside the video's (655.86 .. 942).
#:
#: FIVE of the six survive every vocabulary rule in the module -- they are
#: ordinary sentences -- so ONLY the geometry can keep them out. The sixth
#: ("há 8 dias") is already taken by `_AGO_ONLY`, and it is here to prove
#: that the two mechanisms do not fight each other.
CHROME = [
    (2600, "This is the first time I heard about a model before you posted the video lol"),
    (2640, "REAÇÕES dos GRINGOS com A FURIA CAMPEÃ da THUNDER! (LEGENDADO)"),
    (2680, "@GeeLambo Ludwin"),
    (2720, "há 8 dias"),
    (2760, "Dublagem automática"),
    (2800, "Big A Bonus"),
]
#: A real caption, inside the video, where YouTube paints it.
CAPTION = [(">> So", 600), (" the Akali", 660)]
CAPTION_Y = 900
#: A row that only the OLD band could see: it lives at y=3000, inside the
#: page's band and far below the video's.
OLD_BAND_ROW_Y = 3000
OLD_BAND_ROW = "a linha que a janela antiga ainda le"


# ── the fake UI Automation tree ─────────────────────────────────────────────
class _Rect(object):
    def __init__(self, t):
        (self.left, self.top, self.right, self.bottom) = t


class _El(object):
    def __init__(self, name, rect, ctype=50020, cls=""):
        self.CurrentName = name
        self.CurrentBoundingRectangle = _Rect(rect)
        self.CurrentControlType = ctype
        self.CurrentClassName = cls


class _ValuePattern(object):
    def __init__(self, value):
        self.CurrentValue = value

    def QueryInterface(self, _i):
        return self


class _EditEl(_El):
    """An address-bar Edit, so the URL branch can be exercised for real."""

    def __init__(self, name, rect, value):
        _El.__init__(self, name, rect, 50004)
        self._value = value

    def GetCurrentPattern(self, _pid):
        return _ValuePattern(self._value)


class _Coll(object):
    def __init__(self, items):
        self._items = items

    @property
    def Length(self):
        return len(self._items)

    def GetElement(self, i):
        return self._items[i]


class _Root(object):
    def __init__(self, items, rect=WINDOW):
        self._items = items
        self.CurrentBoundingRectangle = _Rect(rect)

    def FindAll(self, scope, cond):
        return _Coll(self._items)


class _Uia(object):
    def __init__(self, items):
        self._items = items

    def CreateTrueCondition(self):
        return True

    def CreatePropertyCondition(self, *a):
        return True

    def ElementFromHandle(self, hwnd):
        return _Root(self._items)


class _UIA(object):
    UIA_ControlTypePropertyId = 1
    UIA_EditControlTypeId = 2
    UIA_ValuePatternId = 3
    IUIAutomationValuePattern = 4
    TreeScope_Element = 1
    TreeScope_Descendants = 4


def _text_row(y, text, centre):
    """One Text element, centred on `centre` (the centring rule must not be
    what keeps it out -- only the geometry may)."""
    w = 10 * len(text)
    x0 = int(centre - w / 2)
    return _El(text, (x0, y, x0 + w, y + 20))


def _caption_els():
    out = []
    for name, x0 in CAPTION:
        w = 10 * len(name)
        out.append(_El(name, (x0, CAPTION_Y, x0 + w, CAPTION_Y + 20)))
    return out


def _chrome_els(centre=950):
    return [_text_row(y, t, centre) for y, t in CHROME]


#: The measured tree: the PAGE (the biggest element) and, next to it, the
#: REAL video element.
#: The MINI-PLAYER is synthetic: YouTube's page can carry a second element
#: with the same class, and the rule is that the BIGGEST one is the one
#: playing. It is here so that rule is observable.
MINI_RECT = (1500, 200, 1900, 500)


def _page_els(with_video=True):
    """The measured tree: the PAGE (the biggest element) and, next to it, the
    REAL video element."""
    els = [
        _El("", PAGE_RECT, 50026, "ytd-page-manager"),
        _El("ytd-watch-flexy", PAGE_RECT, 50026, "ytd-watch-flexy"),
    ]
    if with_video:
        els.append(_El("Player de video do YouTube", VIDEO_RECT, 50026,
                       "html5-video-player ytp-trans"))
        els.append(_El("", VIDEO_RECT, 50026, "html5-video-container"))
        els.append(_El("Mini player", MINI_RECT, 50026,
                       "html5-video-player ytp-miniplayer"))
    return els


# ── the harness ─────────────────────────────────────────────────────────────
def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stub_window(mod, title, proc):
    mod._window_title = lambda hwnd, t=title: t
    mod._process_name = lambda hwnd, p=proc: p


def _read(mod, els, polls=2):
    """caption_lines over N polls -> [(output, trace), ...].

    Two polls, because the confirmation gate is two polls by design.
    """
    if hasattr(mod, "_RUNS"):
        mod._RUNS.clear()
    out = []
    for _ in range(polls):
        trace = []
        got = mod.caption_lines(HWND, _Uia(els), _UIA, trace)
        out.append((got, trace))
    return out


def _lines(reads):
    return [ln for got, _t in reads for _src, lines in got for ln in lines]


def _band_top(rect):
    x0, y0, x1, y1 = rect
    return y0 + (y1 - y0) * 0.62


# ── the arms ────────────────────────────────────────────────────────────────
def battery(mod):
    """[(ok, name, detail)] -- the claims, on synthetic fixtures only."""
    rows = []

    def check(ok, name, detail=""):
        rows.append((bool(ok), name, detail))

    # The window the whole file is about: the owner's REAL Chrome window.
    # `player_source` reads the title and the process off the window, and a
    # window that is not a player is REFUSED by the reader -- so the caption
    # arms below need it stubbed before they run.
    _stub_window(mod, REAL_TITLE, "chrome.exe")

    # ── (a) the video element wins, and the comments stay out ──────────────
    els = _page_els(True) + _caption_els() + _chrome_els()
    rect = mod._player_rect(_Uia(els), _Root(els), WINDOW)
    check(rect == VIDEO_RECT,
          "a1 the video element's rect wins over the page's",
          "player_rect=%r (want %r)" % (rect, VIDEO_RECT))
    top = _band_top(rect)
    check(abs(top - VIDEO_BAND_TOP) < 0.01 and abs(top - PAGE_BAND_TOP) > 1.0,
          "a2 the band is inside the video, not inside the comments",
          "band_top=%.2f (video %.2f, page %.2f)"
          % (top, VIDEO_BAND_TOP, PAGE_BAND_TOP))
    reads = _read(mod, els)
    out = _lines(reads)
    joined = ">> So the Akali"
    check(joined in out, "a3 the real caption is read",
          "emitted=%r" % (out,))
    leaked = [t for t in out if t in [c[1] for c in CHROME]]
    check(not leaked, "a4 the page chrome does NOT reach the caption box",
          "leaked=%r" % (leaked,))

    # ── (b) no video element -> the old fallback still reads the window ───
    els2 = _page_els(False) + [_text_row(OLD_BAND_ROW_Y, OLD_BAND_ROW, 950)]
    rect2 = mod._player_rect(_Uia(els2), _Root(els2), WINDOW)
    check(rect2 == PAGE_RECT,
          "b1 without a video element the old heuristic still holds",
          "player_rect=%r (want the page %r)" % (rect2, PAGE_RECT))
    top2 = _band_top(rect2)
    check(abs(top2 - PAGE_BAND_TOP) < 0.01,
          "b2 the old band is the old band",
          "band_top=%.2f (want %.2f)" % (top2, PAGE_BAND_TOP))
    out2 = _lines(_read(mod, els2))
    check(OLD_BAND_ROW in out2,
          "b3 the fallback still reads a row inside that band",
          "emitted=%r" % (out2,))

    # ── (c) a "youtube" title in a NON-BROWSER is not a player ────────────
    _stub_window(mod, EXPLORER_TITLE, "explorer.exe")
    src = mod.player_source(HWND)
    check(src == "", "c1 the File Explorer is not a YouTube player",
          "player_source=%r (want '')" % (src,))

    # ── (d) the measured real window is still a YouTube player ─────────────
    _stub_window(mod, REAL_TITLE, "chrome.exe")
    src = mod.player_source(HWND)
    check(src == "external:youtube", "d1 the owner's real window is still a player",
          "player_source=%r" % (src,))

    # ── (e) the URL beats the title, whatever the process is ───────────────
    # The title here says NOTHING about YouTube: the URL has to be proof on
    # its own, or a window that is not a browser can never be recognised.
    _stub_window(mod, EXPLORER_OTHER_TITLE, "explorer.exe")
    src = mod.player_source(HWND, url=REAL_URL)
    check(src == "external:youtube", "e1 the YouTube URL is proof on its own",
          "player_source=%r" % (src,))

    # ── (f) find_player_window picks the BROWSER, and adopts nothing when
    #        the only candidate is the Explorer ────────────────────────────
    mod._visible_windows = lambda: [
        (0x1111, EXPLORER_TITLE, "explorer.exe"),
        (0x2222, REAL_TITLE, "chrome.exe"),
        (0x3333, SOTTO_TITLE, "pythonw.exe"),
    ]
    found = mod.find_player_window()
    check(found == 0x2222, "f1 the browser's window is returned, not the Explorer's",
          "find_player_window=%r (want 0x2222)" % (found,))
    mod._visible_windows = lambda: [(0x1111, EXPLORER_TITLE, "explorer.exe")]
    found2 = mod.find_player_window()
    check(found2 == 0, "f2 a File Explorer alone is adopted as nothing",
          "find_player_window=%r (want 0)" % (found2,))

    # ── (g) the measured real window still yields its video id ─────────────
    _stub_window(mod, REAL_TITLE, "chrome.exe")
    bar = _EditEl("Pesquisar ou digitar URL", (0, 0, 800, 30), REAL_URL)
    values = mod.edit_values(HWND, _Uia([bar]), _UIA)
    vid = _video_id(mod, values)
    check(vid == REAL_VIDEO_ID, "g1 the real window still yields its video id",
          "edit_values=%r -> video_id=%r (want %r)"
          % (values, vid, REAL_VIDEO_ID))
    return rows


def _video_id(mod, values):
    """The video id out of the Edit values, the way the shell gets it."""
    for value in values:
        try:
            sys.path.insert(0, os.path.dirname(VIDEO_CAPTIONS_PATH))
            import youtube_captions
            got = youtube_captions.video_id_from_url(value)
        except Exception:
            got = None
        finally:
            try:
                sys.path.remove(os.path.dirname(VIDEO_CAPTIONS_PATH))
            except Exception:
                pass
        if got:
            return got
        m = mod._URL.search(str(value or ""))
        if m:
            return m.group(2)
    return None


# ── the mutants ─────────────────────────────────────────────────────────────
# The anchors are EXACT strings of `app/webview/external_subs.py`. A mutant
# whose anchor is missing or ambiguous is DECORATIVE -- it proves nothing --
# so the oracle refuses to count it.
MUTANTS = [
    # THE PAGE IS USED INSTEAD OF THE VIDEO: the band goes back to 2592.32 and
    # the comments come in.
    ("the-page-is-used-instead-of-the-video",
     "    video = _video_player_rect(uia, root, window_rect, all_el)\n"
     "    if video:\n"
     "        return video",
     "    video = None\n"
     "    if video:\n"
     "        return video"),
    # THE VIDEO'S RECT IS IGNORED: the window's own rect is used instead.
    ("the-video-rect-is-ignored",
     "    video = _video_player_rect(uia, root, window_rect, all_el)\n"
     "    if video:\n"
     "        return video",
     "    video = _video_player_rect(uia, root, window_rect, all_el)\n"
     "    if video:\n"
     "        return window_rect"),
    # THE SMALLEST VIDEO ELEMENT WINS: a mini-player on the page would take
    # the band away from the video that is playing.
    ("the-smallest-video-element-wins",
     "            area = w * h\n"
     "            if area > best_area:\n"
     "                best_area = area\n"
     "                best = r",
     "            area = w * h\n"
     "            if best is None or area < best_area:\n"
     "                best_area = area\n"
     "                best = r"),
    # A "youtube" TITLE IN A NON-BROWSER IS A PLAYER: the File Explorer with
    # a folder called "youtube" is adopted as the YouTube window.
    ("a-youtube-title-in-a-non-browser-is-a-player",
     '    if "youtube" in t and _is_browser(p):\n'
     '        return "external:youtube"',
     '    if "youtube" in t:\n'
     '        return "external:youtube"'),
    # THE URL ONLY COUNTS WHEN THE TITLE ALSO MATCHES: the URL stops being
    # proof on its own.
    ("the-url-only-counts-when-the-title-matches-too",
     '    if _URL.search(str(url or "")):\n'
     '        return "external:youtube"',
     '    if _URL.search(str(url or "")) and "youtube" in t:\n'
     '        return "external:youtube"'),
    # FIND_PLAYER_WINDOW ACCEPTS ANY "youtube" TITLE: the first one wins,
    # browser or not.
    ("find-player-window-accepts-any-youtube-title",
     "        if _window_is_player(title, proc):\n"
     "            return int(hwnd)",
     "        if (_window_is_player(title, proc)\n"
     '                or "youtube" in str(title or "").lower()):\n'
     "            return int(hwnd)"),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neg-arm", action="store_true",
                    help="mutants only; rc=1 BY DESIGN")
    ap.add_argument("--state", default="",
                    help="file to write this run's verdict to")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                           # noqa: BLE001
        pass
    if not os.path.isfile(MODULE_PATH):
        print("RED   module missing: %s" % MODULE_PATH)
        return EXIT_FAIL
    with open(MODULE_PATH, "r", encoding="utf-8", newline="") as fh:
        source = fh.read()

    started = time.time()
    arms_total = arms_green = 0
    caught = 0
    weak = 0
    tmpdir = tempfile.mkdtemp(prefix="extsubs-geo-", dir=os.environ.get("TMPDIR") or None)
    try:
        if not args.neg_arm:
            print("ARMS (synthetic fixtures: no window, no browser, no app, no audio)")
            mod = load_module(MODULE_PATH, "extsubs_geo_live")
            rows = battery(mod)
            for ok, name, detail in rows:
                print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                                     ("  " + detail) if detail else ""))
            arms_green = sum(1 for ok, _, _ in rows if ok)
            arms_total = len(rows)
            print("\n  %d/%d" % (arms_green, arms_total))

        print("\nNEGATIVE ARM (broken copies must go RED)")
        for idx, (label, old, new) in enumerate(MUTANTS):
            hits = source.count(old)
            if hits != 1:
                print("  RED   mutant %-52s ANCHOR %s -- oracle is stale"
                      % (label, "MISSING" if hits == 0 else "AMBIGUOUS"))
                weak += 1
                continue
            path = os.path.join(tmpdir, "mutant_%d.py" % idx)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(source.replace(old, new, 1))
            try:
                bad = load_module(path, "extsubs_geo_mut_%d" % idx)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-52s DECORATIVO: nao carregou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            try:
                res = battery(bad)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-52s a bateria rebentou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            reds = [name for ok, name, _ in res if not ok]
            if reds:
                print("  GREEN mutant %-52s caught by: %s"
                      % (label, "; ".join(reds[:3])))
                caught += 1
            else:
                print("  RED   mutant %-52s SURVIVED -- the gate is blind here"
                      % label)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    total = len(MUTANTS)
    verdict_ok = (not args.neg_arm and arms_green == arms_total
                  and caught == total and weak == 0)
    if args.neg_arm:
        ok = (caught == total and weak == 0)
        print("\nVERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por desenho: o braco "
              "negativo REPROVA de proposito)" % ("PASS" if ok else "FAIL",
                                                  caught, total))
        _write_state(args.state, ok, arms_green, arms_total, caught, total,
                     weak, started, verdict_ok)
        return EXIT_FAIL

    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if verdict_ok else "FAIL", arms_green, arms_total,
             caught, total))
    if weak:
        print("  %d mutante(s) DECORATIVO(S): nao carregaram, logo nao provaram "
              "nada." % weak)
    _write_state(args.state, verdict_ok, arms_green, arms_total, caught, total,
                 weak, started, verdict_ok)
    return EXIT_PASS if verdict_ok else EXIT_FAIL


def _write_state(path, ok, arms_green, arms_total, caught, total, weak,
                 started, verdict_ok):
    """The run's own receipt, in the state file the caller points at."""
    if not path:
        return
    try:
        with open(MODULE_PATH, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
    except Exception:                                           # noqa: BLE001
        sha = ""
    data = {
        "oracle": "external-subs-geometry-window-oracle",
        "verdict": "PASS" if ok else "FAIL",
        "arms_green": arms_green,
        "arms_total": arms_total,
        "mutants_caught": caught,
        "mutants_total": total,
        "decorative": weak,
        "module": MODULE_PATH,
        "module_sha256": sha,
        "seconds": round(time.time() - started, 2),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    except Exception:                                           # noqa: BLE001
        pass


if __name__ == "__main__":
    sys.exit(main())
