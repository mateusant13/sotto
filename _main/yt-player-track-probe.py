"""yt-player-track-probe.py -- THE PLAYER'S TRACK vs THE APP'S TRACK, side by
side, with a number.

The owner's own test, verbatim (2026-10-20): *"eu quero a legenda 1:1 do
video do youtube. eu mesmo vou comparar a nossa legenda em tempo real com a
do youtube."*

So this instrument answers three questions, and answers them with numbers:

  1. WHICH TRACK IS THE PLAYER PAINTING? The player's own answer: the
     `lang` of its caption window (MEASURED 2026-10-20 on the real page:
     `<div class="caption-window ytp-caption-window-bottom
     ytp-caption-window-rollup" id="caption-window-1" ... lang="pt">`), and
     the request that track is -- `?v=..&caps=asr&kind=asr&lang=pt`, with NO
     `tlang`.
  2. WHICH TRACK DOES THE APP SERVE? What `youtube_captions.fetch_track`
     returns with the new rule, and the request it makes.
  3. ARE THEY THE SAME? The cues of the two payloads, compared POSITION BY
     POSITION: how many are identical, and what the verdict is.

READ-ONLY: opens no window, plays no audio, moves no mouse and sends nothing.
It only READS the page the owner already has open.

USAGE
    python _main\\yt-player-track-probe.py                 # the open window
    python _main\\yt-player-track-probe.py --video cUeZMUGCxrw
    python _main\\yt-player-track-probe.py --json I:\\cc-tmp\\1to1.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "app", "webview"))

import youtube_captions as yc  # noqa: E402


def _query(url):
    """The significant query parameters of a timedtext request."""
    import re
    out = {}
    for part in re.split(r"[?&]", str(url or ""))[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key in ("lang", "kind", "tlang", "caps", "v"):
            out[key] = value
    return out


def _same_cue(a, b):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    try:
        return (abs(float(a.get("start")) - float(b.get("start"))) < 0.001
                and abs(float(a.get("end")) - float(b.get("end"))) < 0.001
                and " ".join(str(a.get("text") or "").split())
                == " ".join(str(b.get("text") or "").split()))
    except (TypeError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="", help="the video id (default: read "
                    "from the open window)")
    ap.add_argument("--player-lang", default="",
                    help="the language the PLAYER is painting (default: read "
                         "from the player's own caption window)")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--json", default="", help="write the result here")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                           # noqa: BLE001
        pass

    video_id = args.video
    signal = yc.player_track_signal(video_id or None)
    if args.player_lang:
        # The owner can DICTATE what his player is showing, so the 1:1 can
        # be measured even when the window is not open right now.
        signal = {"lang": str(args.player_lang).lower(), "known": True,
                  "source": "ditado", "why": "", "painted": ""}
    print("SINAL DO PLAYER  lang=%r known=%s source=%r why=%r"
          % (signal.get("lang") or "-", signal.get("known"),
             signal.get("source"), signal.get("why")))
    painted = str(signal.get("painted") or "").strip()
    if painted:
        print("LINHA PINTADA PELO PLAYER: %r" % painted)

    if not video_id:
        try:
            import external_subs
            hwnd = external_subs.find_player_window()
            if hwnd:
                UIA, uia = yc._uia()
                for value in external_subs.edit_values(hwnd, uia, UIA):
                    vid = yc.video_id_from_url(value)
                    if vid:
                        video_id = vid
                        break
        except Exception as exc:                                # noqa: BLE001
            print("nao consegui ler o video da janela: %r" % (exc,))
    print("VIDEO: %r" % (video_id or "-"))
    if not video_id:
        print("VERDICT: SEM VIDEO -- o probe precisa do video aberto no "
              "browser do dono (ou de --video)")
        return 2

    # WHAT THE APP SERVES, with the new rule.
    served = yc.fetch_track(video_id, player_lang=(signal.get("lang") or ""))
    print()
    print("FAIXA QUE A APP SERVE")
    print("   chave=%r source=%r state=%r cues=%d"
          % (served.get("lang"), served.get("source"), served.get("state"),
             len(served.get("cues") or ())))
    print("   pedido=%r" % (_query((served.get("track") or {}).get("url")),))
    print("   player_known=%r player_match=%r player_why=%r"
          % (served.get("player_known"), served.get("player_match"),
             served.get("player_why")))

    # THE PLAYER'S OWN TRACK: the key whose request has NO `tlang`, i.e.
    # the one the player's caption window asks for.
    player_key = ""
    if signal.get("lang"):
        code = str(signal.get("lang")).lower()
        player_key = code + "-orig"
    print()
    print("FAIXA QUE O PLAYER MOSTRA")
    print("   chave=%r (o pedido do player: lang=%s SEM tlang)"
          % (player_key or "-", signal.get("lang") or "-"))
    print("   linha pintada=%r" % (painted or "-"))

    # THE NUMBER: the cues of both payloads, compared position by position.
    info = yc._extract_info(video_id, args.timeout)
    ordered = yc.tracks_from_info(info, ("pt", "en"),
                                   player_lang=(signal.get("lang") or ""))
    player_cues = []
    served_cues = list(served.get("cues") or ())
    for track in ordered:
        if str(track.get("lang")).lower() == player_key:
            player_cues, _err = yc._fetch_payload(track, args.timeout)
            break
    identical = 0
    compared = min(len(player_cues), len(served_cues))
    for i in range(compared):
        if _same_cue(player_cues[i], served_cues[i]):
            identical += 1
    print()
    print("CUES COMPARADOS: %d (player=%d app=%d)"
          % (compared, len(player_cues), len(served_cues)))
    print("IDENTICOS POS-A-POS: %d" % identical)
    first_player = (player_cues or [{}])[0].get("text")
    first_served = (served_cues or [{}])[0].get("text")
    print("PRIMEIRO CUE  player=%r" % first_player)
    print("PRIMEIRO CUE  app   =%r" % first_served)
    if player_key and str(served.get("lang")).lower() == player_key \
            and compared and identical == compared:
        verdict = "1:1 -- a app serve a MESMA faixa que o player pinta"
    elif not signal.get("known"):
        verdict = ("INDECIDIDO -- o player nao disse a faixa (known=0, "
                   "why=%r); a app usou a preferencia" % signal.get("why"))
    else:
        verdict = ("DIVERGEM -- o player pinta %r e a app serve %r"
                   % (player_key, served.get("lang")))
    print("VERDICT: %s" % verdict)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"video_id": video_id, "signal": signal,
                       "served": {k: v for k, v in served.items()
                                  if k != "cues"},
                       "player_key": player_key,
                       "cues_compared": compared, "identical": identical,
                       "verdict": verdict}, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
