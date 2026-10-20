"""EXTERNAL SUBTITLES -- read captions the player is ALREADY showing.

Owner, 2026-10-17: *"queremos introduzir legendas que ja existem, em cada app,
caso existam... detectar o video no youtube sendo assistido e pegar as legendas
do proprio youtube... tambem de filmes tipo do app stremio"*.

WHY THIS DOES NOT REIMPLEMENT A SUBTITLE SYNC ENGINE
----------------------------------------------------
YouTube (and Stremio, an Electron app) render their subtitles as TEXT in the
accessibility tree. Windows UI Automation exposes those text elements, already
synchronised by the player itself. Reading them is therefore:

  * exactly the player's own captions, not a re-download;
  * already in sync with seeks, speed changes and pauses;
  * independent of video duration, VTT/SRT formats and yt-dlp;
  * one polling loop, no second clock to drift.

MEASURED 2026-10-17 on this box, with a YouTube video playing in Chrome:
`ElementFromHandle` -> Text elements `'>> So'`, `' the'`, `' Akali'`, ...
at y=942..1001 inside a 1920x1080 player, i.e. the bottom band. The address
bar is an Edit element whose ValuePattern is `youtube.com/watch?v=...`.

`--probe` prints what it reads for N seconds and launches nothing else.

WHAT SEPARATES A CAPTION FROM PLAYER CHROME
------------------------------------------
Owner, 2026-10-17: *"a legenda ta pegando mais coisas do youtube que nao devia...
passar meu mouse encima da display em alguns textos, ou carregar esses textos,
sei la. esquisito"*. Hovering the video raises a preview card and clicking it
raises more UI, all inside the player rect and all inside the caption band,
none of it in the blocklist. So the separator here is TEMPORAL, not
vocabulary: a caption holds still while someone talks, hover UI does not.
`--probe` prints every candidate row, its streak and its verdict per poll,
so that separation is visible instead of asserted.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import sys
import time
from ctypes import wintypes as wt

#: Text elements that are player CHROME, not captions.
#:
#: THIS LIST IS NOISE-TRIMMING, NOT THE SEPARATOR. YouTube A/B-tests and
#: localises its UI strings, so any fixed list is a losing bet -- the owner
#: reported, verbatim, that hovering the mouse over the video or clicking it
#: put non-caption text into the caption, and none of the hover card's
#: strings are in this list. The real separator is TEMPORAL: `_stable`.
#:
#: It survives as a cheap first pass (it costs one regex per element) and as
#: an allowlist-in-reverse: a blocklist is safer than an allowlist here,
#: because a caption can be any word, including "Pause". Only LONG UI
#: sentences, never a single word: captions arrive as one Text element per
#: word (" play", " live", " pause") and a word blocklist silently ate them.
_UI_TEXT = re.compile(
    r"(?i)(atalho do teclado|player de v[ií]deo|legendas/legendas ocultas|"
    r"screen reader|closed captions|mais v[ií]deos)")
_TIME_TEXT = re.compile(
    r"(?i)(\d+\s*(horas?|hours?|minutos?|minutes?|segundos?|seconds?))")
#: THE VIEW COUNTER, and it is the one that got through. Measured 2026-10-18 on
#: the owner's own screenshot: the row read `17 mil há 11 h` and was pushed to
#: the caption overlay verbatim (`CAPTION_OVERLAY_PUSH text="17 mil há 11 h"`).
#: It survived BOTH regexes above for two independent reasons, and both had to
#: be closed:
#:
#: 1. `_TIME_TEXT` only knows the time words spelled OUT (`horas`, `hours`).
#:    YouTube renders the ABBREVIATION — `11 h`, not `11 horas`. The string that
#:    reached the caption carried no word the regex knew.
#: 2. There was no rule for the thousands cluster at all (`17 mil`, `4,2 mi`,
#:    `1,2K`), so the number that makes the row obviously chrome had nothing to
#:    match.
#:
#: It is deliberately a CLUSTER, not bare words: `h` alone and `há` alone are
#: ordinary Portuguese speech ("não há", "hà"), and a caption may contain a
#: digit. What no caption ever is, is a number, an abbreviated unit, and an
#: "ago" marker in one row.
_VIEW_COUNTER = re.compile(
    r"(?i)("
    r"\d[\d.,]*\s*(?:mil|mi|k)\b"                 # 17 mil / 4,2 mi / 1,2K
    r"|h[áa]\s*\d+\s*(?:h|hr|hrs|hora|horas)\b"      # há 11 h
    r"|\d+\s*(?:h|hr|hrs)\s*(?:de|atr[áa]s|antes)\b)"
)
_URL = re.compile(r"(?i)(youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})")

#: The units YouTube prints next to a video's age, in the forms this box
#: actually produces -- and it is NOT only the spelled-out ones.
#:
#: MEASURED in the owner's LIVE session (2026-10-19 19:14, the app he had
#: open): the row `ha 4 sem.` -- Portuguese for "four weeks ago" -- reached
#: the caption box, because the list only knew `semana`/`semanas` and not the
#: abbreviation `sem.`. A rule that only knows the pretty spelling is a rule
#: that loses the first time the page is in another language.
#:
#: ONE string, used by both rules below, so they cannot drift apart.
_AGE_UNITS = (r"(?:h|hr|hrs|hora|horas|dia|dias|sem|semana|semanas|"
              r"min|minuto|minutos|m[eê]s|meses|ano|anos)")

#: The "how long ago" row, ALONE on its line.
#:
#: YouTube prints the age of a video next to its view count: "ha 11 h", "ha 1
#: dia", "ha 4 sem.", "ha 3 semanas". The HOURS form was already caught,
#: inside `_VIEW_COUNTER`; the DAY form was NOT, and "ha 1 dia" reached the
#: caption box on 2026-10-18 13:44 -- the last time the owner watched a
#: video with the app running. The census is
#: `_main/external-caption-chrome-census.py`.
#:
#: It is ANCHORED on purpose. A sentence that merely mentions "ha 1 dia" is
#: a caption, not a counter, and a search-anywhere rule would eat it.
_AGO_ONLY = re.compile(
    r"(?i)^\s*h[áa]\s*\d+\s*" + _AGE_UNITS + r"\b\.?\s*$")

#: The VIEW COUNT row, ALONE on its line: "1,9 mil", "17 mil há 11 h",
#: "4,6 mi há 5 dias".
#:
#: The count form WAS caught, inside `_VIEW_COUNTER` — but only per ELEMENT,
#: and YouTube splits a row into words. A counter that arrives as "1,9" +
#: "mil" is invisible to an element-shaped rule, so the row is judged again
#: once it is whole.
#:
#: Anchored like the others, and for the same reason: "17 mil pessoas
#: ficaram na rua" is a caption, not a counter.
_COUNTER_ONLY = re.compile(
    r"(?i)^\s*\d[\d.,]*\s*(?:mil|mi|k)\b"
    r"(?:\s*h[áa]\s*\d+\s*" + _AGE_UNITS + r"\b\.?)?\s*$")

#: A row with NO LETTER in it is never a caption.
#:
#: MEASURED on the 220 external lines the owner's own app produced: "344",
#: "277", "1", "2" and "·" all reached the caption box. The temporal gate
#: cannot tell them apart — a view counter sits STILL for minutes, so it
#: earns a streak exactly like a caption does.
_NO_LETTER = re.compile(r"^[^A-Za-z]*$")

#: A chat handle alone is not a caption: "@zachw2906" reached the caption box
#: (same census).
_HANDLE = re.compile(r"^@[\w.\-]+$")


def _joined_row_is_chrome(line):
    """True when a JOINED row is player chrome, not a caption.

    THE JOINED ROW IS THE RIGHT PLACE, and the reason is not tidiness: the
    cheap per-element pass sees ONE WORD of a row at a time, so a counter
    that YouTube splits into "há 1" + "dia" is invisible to it. The row is
    what the caption is, so the row is what is judged.

    Every rule here is ANCHORED to the whole row, and that is the point: a
    sentence that happens to contain "há 1 dia", or a number, is a caption.
    """
    text = str(line or '').strip()
    if not text:
        return True
    if _AGO_ONLY.match(text) or _HANDLE.match(text):
        return True
    if _COUNTER_ONLY.match(text) or _NO_LETTER.match(text):
        return True
    return False


#: Consecutive polls a row must survive before it counts as a caption.
_CONFIRM_POLLS = 2
#: YouTube never shows more than two caption lines.
_MAX_LINES = 2
#: Rows further apart than this (px, top edge to top edge) are not one
#: two-line caption -- one caption line is roughly 40-56px on this box.
_LINE_SLACK = 96.0
#: Polls a CONFIRMED row may stay off-centre before it is dropped. This is the
#: rule that was missing, and its absence is why a wrong row lived forever.
#: Measured 2026-10-18: `17 mil há 11 h` (YouTube's view counter) entered on the
#: "first caption is exempt from the centring test" rule, was confirmed, and
#: the takeover veto below could not touch it -- the veto only blocks a row's
#: text from CHANGING, while `kept[key] = held` emitted it on every poll after.
#: So chrome that wins once is chrome until the player is closed.
#: 6 polls at INTERVAL_S=0.30 is ~1.8 s: longer than a hover card or a click
#: flash, shorter than a caption that stays put for a sentence.
_UNSHAPED_DROP_POLLS = 6
#: A caption is CENTRED in the player; chrome is not. This is the veto that
#: stops chrome SITTING ON the caption's own row from taking the row over:
#: stability alone cannot tell speech from UI when both persist. NOTE: the
#: docstring above records the caption fragments' Y range (942..1001) as
#: measured; their X range was never recorded, so centring is the one
#: discriminator in this file resting on the player convention rather than on
#: a measurement from this box. Tolerance is a fraction of the player width so
#: it scales with the window, with a floor for tiny players.
_CENTRE_TOL = 0.15
#: hwnd -> {row_key: {"text": str, "streak": int, "held": str|None}}.
#: Bounded: past _RUNS_MAX the state is dropped rather than growing forever.
_RUNS = {}
_RUNS_MAX = 32


def _reset(hwnd):
    """Forget this window's runs (no candidates, or the window went away)."""
    _RUNS.pop(hwnd, None)


def _uia():
    """The UI Automation root, or an exception the caller reports once."""
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    # The typelib is generated on first use; this is the supported entry.
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as UIA
    return UIA, comtypes.client.CreateObject(UIA.CUIAutomation)


def _rect(el):
    try:
        r = el.CurrentBoundingRectangle
        return (int(r.left), int(r.top), int(r.right), int(r.bottom))
    except Exception:
        return None


def _name(el):
    try:
        return str(el.CurrentName or "")
    except Exception:
        return ""


def _control_type(el):
    try:
        return int(el.CurrentControlType)
    except Exception:
        return 0


def _process_name(hwnd):
    try:
        import psutil
        pid = wt.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(wt.HWND(hwnd), ctypes.byref(pid))
        return (psutil.Process(int(pid.value)).name() or "").lower()
    except Exception:
        return ""


def _window_title(hwnd):
    b = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(wt.HWND(hwnd), b, 512)
    return b.value


def _address_bar_url(uia, UIA, root):
    """The Chromium address bar, if this window has one."""
    try:
        cond = uia.CreatePropertyCondition(
            UIA.UIA_ControlTypePropertyId, UIA.UIA_EditControlTypeId)
        edits = root.FindAll(UIA.TreeScope_Descendants, cond)
        for i in range(edits.Length):
            e = edits.GetElement(i)
            name = _name(e).lower()
            if "endere" not in name and "address" not in name and "search" not in name:
                continue
            try:
                p = e.GetCurrentPattern(
                    UIA.UIA_ValuePatternId).QueryInterface(
                        UIA.IUIAutomationValuePattern)
                value = str(p.CurrentValue or "").strip()
                if value:
                    return value
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _player_rect(uia, root, window_rect):
    """The biggest Group/Pane inside the window; the window itself if none.

    `uia` WAS NOT A PARAMETER until 2026-10-17: the name below resolved to a
    global that does not exist, so this raised NameError, the bare
    `except Exception` swallowed it, and every run fell through to the WINDOW
    rect. The x-bounds half of the player filter was therefore inert and the
    band ran to the bottom of the browser window, not the bottom of the video.
    """
    best = None
    best_area = 0
    try:
        all_el = root.FindAll(0x4, uia.CreateTrueCondition())  # Descendants
        for i in range(all_el.Length):
            e = all_el.GetElement(i)
            r = _rect(e)
            if not r:
                continue
            area = max(0, r[2] - r[0]) * max(0, r[3] - r[1])
            if area > best_area:
                best_area = area
                best = r
    except Exception:
        pass
    wx0, wy0, wx1, wy1 = window_rect
    win_area = max(0, wx1 - wx0) * max(0, wy1 - wy0)
    if best and best_area >= win_area * 0.40:
        return best
    return window_rect


def _join(names):
    """One row's fragments -> one line, respecting each one's own spacing.

    YouTube emits one Text element per word and each carries its own leading
    space (' the'), which is why the old "".join() worked for captions. A
    hover-card fragment carries NO leading space, so a bare "".join() welded
    a card's title straight onto the words: ' the' + 'Akali Brothers' became
    ' theAkali Brothers'. Keep each fragment's own whitespace and insert one
    space only where the fragment brings none, so chrome can be separated
    from a caption but can never fuse onto one.
    """
    out = ""
    for frag in names:
        if not out:
            out = frag
        elif frag[:1].isspace() or out[-1:].isspace():
            out += frag
        else:
            out += " " + frag
    return re.sub(r"\s+", " ", out).strip()


def _band_rows(all_el, px0, py0, px1, py1, band_top):
    """{row_key: {"y0": px, "frags": [(x0, x1, name)]}} for Text in the band.

    The rect is passed as the four bounds in reading order, then band_top.
    Cheap first pass only: control type, the blocklist and the lower band.
    """
    rows = {}
    for i in range(all_el.Length):
        e = all_el.GetElement(i)
        if _control_type(e) != 50020:  # UIA_TextControlTypeId
            continue
        name = _name(e)
        if not name.strip():
            continue
        if _UI_TEXT.match(name.strip()) or _TIME_TEXT.search(name) \
                or _VIEW_COUNTER.search(name):
            continue
        r = _rect(e)
        if not r:
            continue
        x0, y0, x1, y1 = r
        if y0 < band_top or y1 > py1 + 2:
            continue
        if x0 < px0 - 2 or x1 > px1 + 2:
            continue
        rows.setdefault(round(y0 / 8.0), {"y0": y0, "frags": []})["frags"].append((x0, x1, name))
    return rows


def _caption_shaped(frags, px0, px1):
    """True when the row sits centred in the player, the way a caption does.

    Decided on the CENTROID of the row, not its extent: a hover card grafted
    onto the caption's own line still spans the centre, so "does it cross the
    middle" would wave it through, while the centroid of a mostly-chrome row
    sits far to the side where a caption's never does.
    """
    mid = (px0 + px1) / 2.0
    tol = max(24.0, (px1 - px0) * _CENTRE_TOL)
    lo = min(f[0] for f in frags)
    hi = max(f[1] for f in frags)
    return abs((lo + hi) / 2.0 - mid) <= tol


def _extends(old, new):
    """True when `new` is `old` plus more -- a caption growing mid-sentence."""
    return bool(old) and new.startswith(old)


def _stable(hwnd, cand):
    """{row: text} to emit as caption this poll, plus a per-row trace.

    `cand` is {row: (text, caption_shaped)} from `_caption_shaped`.

    THIS IS THE REAL SEPARATOR, and it is temporal, not vocabulary-based. A
    caption stays put while a speaker talks -- many polls. A hover card or
    click feedback appears on one poll and is gone on the next. So a row's
    text has to look the same, or grow into itself, for _CONFIRM_POLLS
    consecutive polls before it is emitted as caption; a row that vanished
    on this poll is dropped at once.

    A row whose text changed to something that is NOT an extension of its
    own run resets its streak and emits NOTHING of the new text -- it keeps
    HOLDING the last confirmed caption, unless the newcomer is centred like a
    caption (`_caption_shaped`). Chrome therefore cannot reach the caption
    output, and cannot displace the caption either.
    """
    if len(_RUNS) > _RUNS_MAX:
        _RUNS.clear()
    runs = _RUNS.setdefault(hwnd, {})
    trace = []
    for key in list(runs):
        if key not in cand:
            trace.append((key, runs[key]["text"], "DROPPED", "vanished on this poll"))
            del runs[key]
    kept = {}
    for key in sorted(cand):
        text, shaped = cand[key]
        slot = runs.get(key)
        if slot is None:
            runs[key] = {"text": text, "streak": 1, "held": None, "unshaped": 0}
            trace.append((key, text, "PENDING", "first sight of this row"))
            continue
        held = slot["held"]
        slot["unshaped"] = 0 if shaped else slot.get("unshaped", 0) + 1
        # THE EXIT THAT DID NOT EXIST. A row that was confirmed and has now sat
        # off-centre for _UNSHAPED_DROP_POLLS is chrome that got in on the
        # first-caption exemption; it is DELETED, not merely vetoed. Before this,
        # `held` was assigned once and `kept[key] = held` ran on every poll
        # forever after, so no sequence of later polls could ever retract it.
        if held is not None and slot["unshaped"] >= _UNSHAPED_DROP_POLLS:
            trace.append((key, text, "DROPPED",
                          "not centred like a caption for %d polls (chrome that "
                          "won the first-caption exemption)" % slot["unshaped"]))
            del runs[key]
            continue
        if text == slot["text"]:
            slot["streak"] += 1
            why = "identical to the previous poll"
        elif _extends(slot["text"], text):
            slot["streak"] += 1
            why = "prefix-extension of the previous poll"
        else:
            slot["streak"] = 1
            why = "NOT an extension of %r" % (slot["text"],)
        slot["text"] = text
        # An established caption is only ever handed over to text shaped like
        # a caption. Chrome grafted onto the caption's own row is off-centre,
        # so it cannot take the row -- not on its first poll and not after the
        # user leaves it parked there for ten. A row with NO caption yet is
        # exempt, so a left-aligned player still reads its first caption.
        if slot["streak"] >= _CONFIRM_POLLS and held is not None and not shaped:
            why += ", not centred like a caption: takeover vetoed"
        elif slot["streak"] >= _CONFIRM_POLLS:
            held = slot["held"] = text
        if held is None:
            trace.append((key, text, "PENDING",
                          "%s, streak=%d < %d" % (why, slot["streak"], _CONFIRM_POLLS)))
        elif held == text:
            kept[key] = held
            trace.append((key, text, "STABLE", "%s, streak=%d" % (why, slot["streak"])))
        else:
            kept[key] = held
            trace.append((key, text, "HELD",
                          "new text not confirmed (%s); still showing %r" % (why, held)))
    return kept, trace


def _bottom_run(kept, band, max_lines=_MAX_LINES):
    """The rows nearest the player's bottom edge, whole, at most `max_lines`.

    Captions sit in the lowest band, so the bottom row is the caption and a
    row far above it cannot displace it. Two rows within _LINE_SLACK are one
    two-line caption and are kept together -- a real two-line caption is
    never split, and never silently truncated to one line.
    """
    def y0(key):
        return band[key]["y0"] if key in band else float(key) * 8.0

    keys = sorted(kept, key=y0, reverse=True)
    if not keys:
        return []
    out = [keys[0]]
    base = y0(keys[0])
    for key in keys[1:]:
        if len(out) >= max_lines:
            break
        if base - y0(key) <= _LINE_SLACK:
            out.append(key)
    return sorted(out)  # top line first, so the caption reads in order


def _is_browser(proc):
    """Is this process name a browser with an address bar?"""
    p = str(proc or "").lower()
    return ("chrome" in p or "msedge" in p or "firefox" in p)


def player_source(hwnd, uia=None, UIA=None, root=None, url=None):
    """Which player this window is -- or "" for a window that is not one.

    THE SOURCE IS A PROPERTY OF THE WINDOW, not of the lines found in it.
    `caption_lines` decides the source and then looks for captions, so a
    YouTube page whose lower band holds nothing but chrome returns NO lines
    and the caller never learns it was looking at YouTube. The real-track
    path needs exactly that: the WINDOW, not its text.

    THE FOUR STATES OF THE CALLER ARE NOT THIS FUNCTION's BUSINESS. This one
    only says WHICH PLAYER it is; whether that player has a caption track,
    and what the caption is at this instant, is `youtube_captions`' work.
    """
    title = _window_title(hwnd)
    proc = _process_name(hwnd)
    if url is None:
        url = ""
        if uia is not None and UIA is not None:
            if root is None:
                try:
                    root = uia.ElementFromHandle(hwnd)
                except Exception:
                    root = None
            if root is not None and _is_browser(proc):
                url = _address_bar_url(uia, UIA, root)
    if "youtube" in title.lower() or _URL.search(url or ""):
        return "external:youtube"
    if "stremio" in title.lower() or "stremio" in proc:
        return "external:stremio"
    return ""


def edit_values(hwnd, uia, UIA):
    """Every Edit control's value in this window, in tree order.

    WHY A LIST AND NOT "THE ADDRESS BAR". A Chromium window has SEVERAL Edit
    controls: the address bar, the YouTube page's own search box, and
    whatever else the page put on screen. `_address_bar_url` takes the first
    one whose accessible name mentions an address and falls back to "search"
    -- and in a Portuguese Chrome the address bar is called *"Pesquisar ou
    digitar URL"*, so that fallback can land on the YouTube SEARCH BOX
    instead. A video id must come from the address bar, so the caller wants
    to see every value and pick the one that parses.

    This function does not change `_address_bar_url`: the source detection
    in `caption_lines` keeps the behaviour it was measured with.
    """
    out = []
    try:
        root = uia.ElementFromHandle(hwnd)
    except Exception:
        return out
    if root is None:
        return out
    try:
        cond = uia.CreatePropertyCondition(
            UIA.UIA_ControlTypePropertyId, UIA.UIA_EditControlTypeId)
        edits = root.FindAll(UIA.TreeScope_Descendants, cond)
        for i in range(edits.Length):
            e = edits.GetElement(i)
            try:
                p = e.GetCurrentPattern(
                    UIA.UIA_ValuePatternId).QueryInterface(
                        UIA.IUIAutomationValuePattern)
                value = str(p.CurrentValue or "").strip()
            except Exception:
                continue
            if value:
                out.append(value)
    except Exception:
        pass
    return out


def caption_lines(hwnd, uia, UIA, trace=None):
    """[(source, [line1, line2])] for the window, or []."""
    root = uia.ElementFromHandle(hwnd)
    if root is None:
        _reset(hwnd)
        return []
    source = player_source(hwnd, uia, UIA, root=root)
    if not source:
        # ONLY a recognised player. A generic browser window has arbitrary
        # text at the bottom (a stream overlay read "600200M" as a caption);
        # claiming it would replace real speech with UI noise.
        _reset(hwnd)
        return []

    wx0, wy0, wx1, wy1 = _rect(root) or (0, 0, 0, 0)
    if wx1 <= wx0 or wy1 <= wy0:
        _reset(hwnd)
        return []
    px0, py0, px1, py1 = _player_rect(uia, root, (wx0, wy0, wx1, wy1))
    band_top = py0 + (py1 - py0) * 0.62
    try:
        all_el = root.FindAll(0x4, uia.CreateTrueCondition())
    except Exception:
        _reset(hwnd)
        return []
    band = _band_rows(all_el, px0, py0, px1, py1, band_top)
    cand = {}
    for key, row in band.items():
        frags = sorted(row["frags"], key=lambda f: f[0])
        line = _join([n for _x0, _x1, n in frags])
        # THE JOINED ROW IS JUDGED AS A ROW. The per-element pass above is a
        # cheap first pass and it cannot see a row that YouTube split into
        # pieces ("há 1" + "dia"). See `_joined_row_is_chrome`.
        if line and not _joined_row_is_chrome(line):
            cand[key] = (line, _caption_shaped(row["frags"], px0, px1))
    if not cand:
        _reset(hwnd)
        if trace is not None:
            trace.append(("-", "", "DROPPED", "no candidate in the lower band"))
        return []
    kept, decisions = _stable(hwnd, cand)
    if trace is not None:
        trace.extend(decisions)
    keys = _bottom_run(kept, band)
    if trace is not None:
        for key in sorted(cand):
            if key not in keys:
                trace.append((key, cand[key][0], "SKIPPED",
                              "not in the bottom %d lines (%s)" % (
                                  _MAX_LINES,
                                  "stable, further from the player bottom"
                                  if key in kept else "not confirmed")))
    lines = [kept[k] for k in keys]
    return [(source, lines)] if lines else []


def foreground_captions(uia, UIA, trace=None):
    hwnd = int(ctypes.windll.user32.GetForegroundWindow() or 0)
    if not hwnd:
        return []
    title = _window_title(hwnd)
    # Never read Sotto's own panel as if it were a video.
    if title.strip().lower().startswith("sotto"):
        return []
    return caption_lines(hwnd, uia, UIA, trace)


def probe(seconds=10.0, interval=0.25):
    UIA, uia = _uia()
    started = time.monotonic()
    last = None
    poll = 0
    while time.monotonic() - started < seconds:
        poll += 1
        trace = []
        try:
            got = foreground_captions(uia, UIA, trace)
        except Exception as exc:
            print("PROBE_ERROR", repr(exc), flush=True)
            got = []
        # Per poll: every candidate row, which one is STABLE, and why each
        # other one was rejected. The owner can watch hover noise arrive,
        # sit at streak=1 and disappear without ever reaching PROBE.
        for key, text, verdict, why in trace:
            print("POLL %-4d row=%-6s %-8s %-52r %s"
                  % (poll, key, verdict, text, why), flush=True)
        if got != last:
            print("PROBE", time.strftime("%H:%M:%S"), got, flush=True)
            last = got
        time.sleep(interval)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read captions a player already shows")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--seconds", type=float, default=10.0)
    args = ap.parse_args(argv)
    if args.probe:
        return probe(args.seconds)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
