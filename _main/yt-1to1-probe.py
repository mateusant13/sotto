"""yt-1to1-probe.py -- IS OUR CAPTION THE PLAYER'S CAPTION?

The owner's own test, verbatim (2026-10-20): *"eu quero a legenda 1:1 do
video do youtube ... eu mesmo vou comparar a nossa legenda em tempo real com
a do youtube. lembra que é pra tu simplesmente pegar a do youtube mesmo e
usar pelo app. o app só nao faz isso se nao tem a legenda disponivel."*

So the question is not "does the parser work" but "at this instant, is the
line we would show THE line the player is showing". Two independent reads at
the SAME instant:

  A) THE PAINTED CAPTION -- what the owner's EYES see, read from the YouTube
     player through UI Automation, inside the REAL video rectangle (the
     `html5-video-player` element). This is the caption YouTube itself drew.
  B) OUR TRACK -- the cue of the video's own caption track at the player's
     clock, i.e. exactly what `youtube_captions.cue_at(cues, t)` returns and
     therefore exactly what the app would put in the box.

If A == B, the answer to the owner is a number, not a promise.

READ-ONLY: opens no window, plays no audio, moves no mouse, and sends
nothing. It only READS the page the owner already has open.

USAGE
    python _main\\yt-1to1-probe.py                # 6 samples, default window
    python _main\\yt-1to1-probe.py --samples 20
    python _main\\yt-1to1-probe.py --json I:\\cc-tmp\\1to1.json
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app", "webview"))

import external_subs  # noqa: E402
import youtube_captions as yc  # noqa: E402


def norm(text):
    return " ".join(str(text or "").split()).strip().lower()


def painted_lines(hwnd, uia, UIA, root):
    """The caption the player has PAINTED, read from the real video rectangle.

    The rectangle is the `html5-video-player` element when the page has one:
    the page's own rectangle covers the WHOLE web content (measured on the
    owner's window: y from 121 to 4107), and a band over that reaches the
    COMMENT section, where a recommended video's title sits.
    """
    all_el = root.FindAll(0x4, uia.CreateTrueCondition())
    rect = None
    for i in range(all_el.Length):
        el = all_el.GetElement(i)
        try:
            cls = el.CurrentClassName or ""
        except Exception:
            continue
        if "html5-video-player" not in cls:
            continue
        r = external_subs._rect(el)
        if not r:
            continue
        if rect is None or ((r[2] - r[0]) * (r[3] - r[1]) >
                            (rect[2] - rect[0]) * (rect[3] - rect[1])):
            rect = r
    if rect is None:
        wx0, wy0, wx1, wy1 = external_subs._rect(root) or (0, 0, 0, 0)
        rect = (wx0, wy0, wx1, wy1)
    band_top = rect[1] + (rect[3] - rect[1]) * 0.62
    rows = external_subs._band_rows(all_el, rect[0], rect[1], rect[2], rect[3],
                                    band_top)
    out = []
    for key in sorted(rows):
        frags = sorted(rows[key]["frags"], key=lambda f: f[0])
        line = external_subs._join([n for _x0, _x1, n in frags])
        if line and not external_subs._joined_row_is_chrome(line):
            out.append(line)
    return out, rect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--video", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    hwnd = external_subs.find_player_window()
    if not hwnd:
        print("SEM JANELA DE PLAYER (o video do dono nao esta aberto)")
        return 2
    title = external_subs._window_title(hwnd)
    print("janela: %d | %s" % (hwnd, title))
    source = external_subs.player_source(hwnd)
    print("player_source: %r" % source)

    UIA, uia = external_subs._uia()
    root = uia.ElementFromHandle(hwnd)
    if root is None:
        print("SEM RAIZ UIA")
        return 2

    video_id = ""
    try:
        for value in external_subs.edit_values(hwnd, uia, UIA):
            try:
                vid = yc.video_id_from_url(value)
            except Exception:
                vid = None
            if vid:
                video_id = vid
                break
    except Exception as exc:  # noqa: BLE001
        print("edit_values falhou: %r" % (exc,))
    if args.video:
        video_id = args.video
    print("video_id: %r" % video_id)

    cues = []
    duration = None
    if video_id:
        try:
            doc = json.load(open(yc._cache_path(video_id), encoding="utf-8"))
            cues = doc.get("cues") or []
            duration = doc.get("duration")
            print("faixa em cache: lang=%s source=%s cues=%d dur=%s"
                  % (doc.get("lang"), doc.get("source"), len(cues), duration))
        except Exception as exc:  # noqa: BLE001
            print("sem faixa em cache: %r" % (exc,))

    rows = []
    for i in range(max(1, args.samples)):
        detail = yc.player_time_detail(uia, UIA, hwnd, duration=duration)
        t = detail.get("t")
        track_text = ""
        if cues and t is not None:
            cue = yc.cue_at(cues, t)
            track_text = str((cue or {}).get("text") or "")
        try:
            painted, rect = painted_lines(hwnd, uia, UIA, root)
        except Exception as exc:  # noqa: BLE001
            painted, rect = [], None
        page_text = " ".join(painted)
        same = bool(track_text) and norm(track_text) == norm(page_text)
        rows.append({"at": i, "t": t, "why": detail.get("why"),
                     "track": track_text, "page": page_text, "same": same,
                     "rect": rect})
        print("  #%d t=%s (%s)" % (i, t, detail.get("why")))
        print("     NOSSA FAIXA : %r" % track_text)
        print("     PINTADO     : %r" % page_text)
        print("     IGUAIS      : %s" % same)
        if i + 1 < args.samples:
            time.sleep(args.interval)

    both = [r for r in rows if r["track"] and r["page"]]
    same_n = sum(1 for r in both if r["same"])
    print()
    print("AMOSTRAS COM AS DUAS FONTES: %d" % len(both))
    print("IGUAIS (1:1): %d" % same_n)
    if both and same_n == len(both):
        print("VERDICT: 1:1 -- a nossa legenda E a legenda que o YouTube desenha")
    elif both:
        print("VERDICT: DIVERGEM -- ver as amostras acima")
    else:
        print("VERDICT: SEM AMOSTRA COMPARAVEL")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"window": title, "video_id": video_id, "rows": rows},
                      fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
