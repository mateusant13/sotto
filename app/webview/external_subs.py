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
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import sys
import time
from ctypes import wintypes as wt

#: Text elements that are player CHROME, not captions. A blocklist is safer
#: than an allowlist here: a caption can be any word, including "Pause".
#: Only LONG UI sentences, never a single word: captions are split into
#: individual Text elements (" play", " live", " pause") and a word blocklist
#: silently ate them. The lower-band + player-rect filter is the real separator.
_UI_TEXT = re.compile(
    r"(?i)(atalho do teclado|player de v[ií]deo|legendas/legendas ocultas|"
    r"screen reader|closed captions|mais v[ií]deos)")
_TIME_TEXT = re.compile(
    r"(?i)(\d+\s*(horas?|hours?|minutos?|minutes?|segundos?|seconds?))")
_URL = re.compile(r"(?i)(youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})")


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


def _player_rect(root, window_rect):
    """The biggest Group/Pane inside the window; the window itself if none."""
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


def caption_lines(hwnd, uia, UIA):
    """[(source, [line1, line2])] for the window, or []."""
    root = uia.ElementFromHandle(hwnd)
    if root is None:
        return []
    title = _window_title(hwnd)
    proc = _process_name(hwnd)
    url = _address_bar_url(uia, UIA, root) if ("chrome" in proc or "msedge" in proc
                                               or "firefox" in proc) else ""
    source = None
    if "youtube" in title.lower() or _URL.search(url or ""):
        source = "external:youtube"
    elif "stremio" in title.lower() or "stremio" in proc:
        source = "external:stremio"
    else:
        # ONLY a recognised player. A generic browser window has arbitrary
        # text at the bottom (a stream overlay read "600200M" as a caption);
        # claiming it would replace real speech with UI noise.
        return []

    wx0, wy0, wx1, wy1 = _rect(root) or (0, 0, 0, 0)
    if wx1 <= wx0 or wy1 <= wy0:
        return []
    px0, py0, px1, py1 = _player_rect(root, (wx0, wy0, wx1, wy1))
    band_top = py0 + (py1 - py0) * 0.62
    try:
        all_el = root.FindAll(0x4, uia.CreateTrueCondition())
    except Exception:
        return []
    rows = {}
    for i in range(all_el.Length):
        e = all_el.GetElement(i)
        if _control_type(e) != 50020:  # UIA_TextControlTypeId
            continue
        name = _name(e)
        if not name.strip():
            continue
        if _UI_TEXT.match(name.strip()) or _TIME_TEXT.search(name):
            continue
        r = _rect(e)
        if not r:
            continue
        x0, y0, x1, y1 = r
        if y0 < band_top or y1 > py1 + 2:
            continue
        if x0 < px0 - 2 or x1 > px1 + 2:
            continue
        key = round(y0 / 8.0)
        rows.setdefault(key, []).append((x0, name))
    if not rows:
        return []
    lines = []
    for key in sorted(rows):
        words = [n for _, n in sorted(rows[key], key=lambda t: t[0])]
        line = "".join(words)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return [(source, lines[-2:])] if lines else []


def foreground_captions(uia, UIA):
    hwnd = int(ctypes.windll.user32.GetForegroundWindow() or 0)
    if not hwnd:
        return []
    title = _window_title(hwnd)
    # Never read Sotto's own panel as if it were a video.
    if title.strip().lower().startswith("sotto"):
        return []
    return caption_lines(hwnd, uia, UIA)


def probe(seconds=10.0, interval=0.25):
    UIA, uia = _uia()
    started = time.monotonic()
    last = None
    while time.monotonic() - started < seconds:
        try:
            got = foreground_captions(uia, UIA)
        except Exception as exc:
            print("PROBE_ERROR", repr(exc), flush=True)
            got = []
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
