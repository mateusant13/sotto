"""YOUTUBE CAPTIONS -- the video's REAL caption track, and the video's time.

Owner, 2026-10-19: *"faz a legenda do youtube mostrar na tela em tempo real. se
precisar pegar o tempo do video, faça."* and, before that: *"youtube ta
mostrando texto burro da pagina inves da porra da legenda/transcriptino de um
video"* and *"e nao e pra tu parar de transcrever audio do chrome. é audio do
youtube CASO tenha legenda do youtube. se for um video sem legenda, vaio
transcrever ao vivo igual."*

WHAT THE OLD PATH READ, MEASURED
--------------------------------
`app/webview/external_subs.py` reads the text the YouTube page is PAINTING, via
UI Automation. What arrived in the caption box on 2026-10-19 19:14-19:21 (the
owner's own log, `_main/webview-run.log`) was page chrome, not the video's
caption: `Oferta sujeita aos termos. Cancele quando quiser.`, `há 4 sem.`,
`Principais noticias. ... ROADMAP DE PROGRAMACAO GRINGO ...`.

This module does the OTHER thing: it asks YOUTUBE for the video's own caption
track and asks the player where it is in the video. The two together are what
"real-time caption" means -- the caption text of the video, at the instant the
video is at.

THE FOUR STATES, AND THE ONE THAT MATTERS
------------------------------------------
`TRACK_STATES` is the whole contract with the caller:

    "has-track"        a caption covers the current instant -> SHOW IT
    "no-track"         the video has NO caption track    -> KEEP THE ASR RUNNING
    "no-cue-in-window" the track exists but this instant has no cue -> KEEP ASR
    "time-unknown"     the instant is not known           -> KEEP ASR

"no-track" IS THE IMPORTANT ONE. The owner's rule, verbatim: *"se for um video
sem legenda, vaio transcrever ao vivo igual."* So "no-track" must never be
confused with "has-track" -- the oracle proves that with an EXECUTED mutant.
A `None` time means "I DO NOT KNOW WHEN THE VIDEO IS"; it does NOT mean "the
video is stopped". A paused video and an unreadable player are different
things and this module never pretends to know which one it is.

MEASURED 2026-10-19 on this box (the numbers the code below is built on):

* `yt_dlp` 2026.08.19 is installed. `extract_info` on a public video took
  **5.0 s** and downloaded **no** media (`skip_download`). That is why the
  track is CACHED ON DISK: the reader polls at ~3 Hz and must never ask
  YouTube twice for the same video.
* `dQw4w9WgXcQ` (213 s) carries MANUAL subtitles in 5 languages -- `de-DE`,
  `en`, `es-419`, `ja`, `pt-BR` -- each with `json3` and `vtt`; and 160
  AUTOMATIC-caption languages. `pt-BR`/`en` are the manual ones.
* The manual `json3` (pt-BR) has **60 events**, every one of them shaped
  `('dDurationMs', 'segs', 'tStartMs')`, e.g.
  `{"tStartMs": 18640, "dDurationMs": 3240, "segs": [{"utf8": "Não somos
  estranhos ao amor"}]}`.
* The AUTOMATIC `json3` (en) has **104 events in FOUR shapes**:
  `('dDurationMs','segs','tStartMs','wWinId')` x52,
  `('aAppend','dDurationMs','segs','tStartMs','wWinId')` x43,
  `('aAppend','segs','tStartMs','wWinId')` x8, and
  `('dDurationMs','id','tStartMs','wpWinPosId','wsWinStyleId')` x1.
  The last two shapes are the player's CAPTION-WINDOW bookkeeping, not
  captions. MEASURED: every one of those 51 events carries **ZERO
  characters** (they are newline-only or have no `segs` at all), so dropping
  them loses **0%** of the text. The auto track therefore parses into 52 cues.
* Each `utf8` may hold a `"\n"`, and the auto track's segments carry their own
  leading space (`" no"`, `" strangers"`). Joining with a space would give
  `"We're  no  strangers"`, so the segments are joined as they come and the
  whitespace is normalised afterwards.
* The `vtt` entry of an AUTOMATIC track is `protocol: m3u8_native`: the URL
  returns an HLS PLAYLIST (measured: 396 B starting `#EXTM3U`), NOT a WebVTT
  document. Parsing it as VTT would yield an EMPTY track and look like "this
  video has no captions". The playlist is refused, not parsed.
* The timedtext API REFUSES some tracks with HTTP 429. MEASURED
  2026-10-19: the AUTOMATIC track of `as11Bbmgl08` answered 429 on every
  format (json3, vtt, srv3, srv1), on every User-Agent and on every retry,
  while the MANUAL track of `dQw4w9WgXcQ` answered 200 on all four. A
  refused payload is NOT a verdict about the video: it is cached only for a
  short back-off (`PAYLOAD_RETRY_TTL_S`), the retry asks for the TRACK again
  without repeating the 5 s extract, and the caller keeps the live
  transcription -- which is exactly what the owner asked for.
* The player on this box that was open while this was written (a jwplayer)
  exposes its time as ONE Text element, name `06:13 of 24:43` -- current of
  total. THAT is the shape `player_time` looks for first.

THE PLAYER'S CLOCK, MEASURED 2026-10-19 20:1x on a REAL YouTube window
-----------------------------------------------------------------------
The owner's own Chrome, a 28:33 video (`as11Bbmgl08`), UI Automation:

    SLIDER  name="Botão deslizante de busca"   class="ytp-progress-bar"
            value=407.0  min=0.0  max=1713.0
            aria-valuetext="Edição de vídeo 6 Minutos 47 Segundos de 28
                            Minutos 33 Segundos"
    SLIDER  name="Volume"                       class="ytp-volume-panel"
            value=48.0   min=0.0  max=100.0     aria-valuetext="48% volume"

So, measured and not assumed:

  * the seek bar IS a UIA **Slider**, and its RangeValue is in SECONDS --
    407.0 at 6:47 -- and its MAXIMUM IS THE DURATION (1713.0 s = 28:33);
  * the `aria-valuetext` is LOCALISED PROSE ("6 Minutos 47 Segundos de 28
    Minutos 33 Segundos"), not "6:47 of 28:33". It is not parsed: the
    numeric path is already exact, and the words are localised;
  * the VOLUME is a SECOND slider, on a 0..100 scale, and a percent scale
    must never be read as an instant. The sliders are SCORED and the seek
    bar -- the one whose maximum is the video's length -- wins;
  * the same window also paints the page chrome the old path was reading
    ("29,1 mil inscritos", "há 3 h", "513 mil", "21 mil"): the video's
    caption is NOT among them. That is the whole reason this module asks
    YouTube for the track instead of reading the page.

A player that shows only the TOTAL duration is not used as the current
time: a bare clock equal to the known duration is the total, not the
instant. And when nothing can be read with confidence, the answer is None
-- which is NOT the same as "the video is stopped".

THE CACHE
---------
`H:\sotto\_cache\youtube-captions\<video_id>.jsonl`, one JSON object per
file. The `.jsonl` extension is already covered by `.gitignore` (`*.jsonl`), so
a cached track can never enter a commit -- which matters here: the repo was
burned on 2026-10-19 by a `git add -A` that pulled runtime output in. The
folder is created on demand and may be deleted at any time; the next poll
just refetches (5 s, once).

THE 1:1 RULE -- THE TRACK THE PLAYER PAINTS IS THE TRACK THE APP SERVES
----------------------------------------------------------------------
Owner, 2026-10-20, verbatim: *"eu quero a legenda 1:1 do video do youtube.
eu mesmo vou comparar a nossa legenda em tempo real com a do youtube."*

MEASURED 2026-10-20 on the real page (headless Edge, muted playback, the
video the owner watches -- `cUeZMUGCxrw`):

* THE PLAYER SAYS WHICH TRACK IT IS PAINTING. Its caption window carries the
  language: `<div class="caption-window ytp-caption-window-bottom
  ytp-caption-window-rollup" id="caption-window-1" dir="ltr" tabindex="0"
  lang="pt" ...>` -- and the player painted Portuguese. That `lang` is the
  player's own answer, and `player_track_signal()` reads it.

* THE KEY THAT IS THAT TRACK is the `-orig` one, NOT the plain one. Read side
  by side, the player's own request and yt-dlp's two keys:

      the PLAYER (a.pt) -> ?v=..&caps=asr&kind=asr&lang=pt
      yt-dlp  `pt-orig` -> ?v=..&caps=asr&kind=asr&lang=pt   -> 200, 679 cues
      yt-dlp  `pt`      -> ?v=..&caps=asr&kind=asr&lang=ar&tlang=pt -> 429

  The plain key is a DIFFERENT request -- the original track translated on
  the fly -- which yt-dlp itself calls "damaged subtitles" and which YouTube
  refuses. So `-orig` is the track the player shows, and it is served first.

* THE FALLBACK IS A FALLBACK. Without the player's answer the language
  preference decides, and the result says so (`player_known=0` plus the
  reason) and the log says it too: a track chosen without knowing what the
  player shows is never presented as the right one.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request

#: THE CONTRACT WITH THE CALLER. Four states, no more.
TRACK_STATES = ("has-track", "no-track", "no-cue-in-window", "time-unknown")

_HERE = os.path.dirname(os.path.abspath(__file__))
#: `H:\sotto` -- the product root (this file is `<root>/app/webview/<file>`).
_ROOT = os.path.dirname(os.path.dirname(_HERE))

#: The on-disk caption cache. One file per video id.
CACHE_DIR = os.environ.get("SOTTO_YT_CACHE_DIR") or os.path.join(
    _ROOT, "_cache", "youtube-captions")
#: A video's caption track does not change. A week is generous.
TRACK_TTL_S = 7 * 24 * 3600
#: A video with NO track is re-checked sooner: the owner can switch a video
#: to another one, and the owner can turn captions on in the player.
NO_TRACK_TTL_S = 3600
#: A payload the API REFUSED is retried on this cadence. MEASURED 2026-10-19:
#: the timedtext API answers HTTP 429 for the AUTOMATIC track of one video
#: (on every format, on every User-Agent, on every retry) while the MANUAL
#: track of another serves 200 on all four. A short back-off keeps a 3 Hz
#: reader from hammering YouTube, and a real recovery is picked up within
#: the minute.
PAYLOAD_RETRY_TTL_S = 60

#: A YouTube video id is 11 URL-safe characters.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_URL_PATTERNS = (
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu(?:be\.com|\.be)/([A-Za-z0-9_-]{11})"),
    re.compile(r"/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})"),
)

#: A YouTube URL is a YouTube URL because of its HOST. `watch?v=` alone is
#: not enough: every site on earth has a `?v=` parameter, and a caption
#: track must never be asked for a video that is not on YouTube.
_YOUTUBE_HOST_RE = re.compile(
    r"(?i)(?:^|[\./])(?:www\.|m\.|music\.)?"
    r"(?:youtube\.com|youtube-nocookie\.com|youtu\.be)(?:[/:?#]|$)")

#: The payload formats this module can parse, in order.
_EXT_PREFERENCE = ("json3", "vtt")

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


# ── the pure parts ───────────────────────────────────────────────────────────

def video_id_from_url(url):
    """The 11-char video id in a YouTube URL, or None.

    `youtube.com/watch?v=ID`, `youtu.be/ID`, and the `/shorts/`, `/embed/`,
    `/live/` paths are the same id in a different place.
    """
    text = str(url or "")
    if not text or not _YOUTUBE_HOST_RE.search(text):
        return None
    for pat in _URL_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return None


#: Um segmento que COMECA por um destes NAO leva espaco antes dele. O json3 parte a
#: linha em segmentos e um `?` ou um `.` vem como segmento proprio; a regra antiga
#: ("um segmento sem espaco proprio ganha um") punha `alguem ?` e `Nao .` no ecra,
#: que e exactamente o que o YouTube NAO desenha. MEDIDO 2026-10-23 contra a janela
#: do player no Edge (`_main/yt-1to1-live-compare.py`): o YouTube pinta
#: `Você já teve que matar alguém?` e `>> Não.`.
_NO_SPACE_BEFORE = ".,;:!?…)]}»›%"
#: E um segmento DEPOIS destes tambem nao: um parentese ou aspas abertas nao separam.
_NO_SPACE_AFTER = "([{¿¡«“‘"


def _join_segs(segs):
    """The `segs` of one json3 event -> one line of text.

    MEASURED: the auto track's segments carry their OWN leading space
    (`" no"`, `" strangers"`), so joining them with a space gives
    `"We're  no  strangers"` (double spaces). They are joined as they come
    and the whitespace is normalised at the end. A segment that brings no
    space of its own gets one, so two words never fuse -- EXCEPT before
    punctuation, which is where the old rule glued a space the player never
    draws (`alguem ?` instead of `alguem?`; see `_NO_SPACE_BEFORE`).
    """
    out = ""
    for seg in segs or ():
        if not isinstance(seg, dict):
            continue
        piece = str(seg.get("utf8") or "")
        if not piece:
            continue
        if out and not piece[:1].isspace() and not out[-1:].isspace():
            first = piece[:1]
            last = out[-1:]
            attached = (first in _NO_SPACE_BEFORE or last in _NO_SPACE_AFTER
                        or (first in "'’" and last.isalnum()))
            if not attached:
                out += " "
        out += piece
    # THE WHITESPACE IS NORMALISED HERE, BUT THE LINE BREAK IS NOT (2026-10-20).
    # The auto track's segments carry their own leading space, and a segment may
    # hold a "\n" -- MEASURED on the owner's own video (2BXktpaCEN4, the
    # "How I Build AI Teammates" one): 706 of the 1414 raw json3 events carry a
    # "\n" in their own text. The old `re.sub(r"\s+", " ", out)` destroyed every
    # one of them, so the cue YouTube draws on TWO lines arrived here as ONE
    # line and our caption broke wherever the browser wanted. The owner, about
    # the caption: *"voce nao ta fazendo a legenda parecendo com como o youtube
    # da DISPLAY e quebra as linhas e etc."*
    # So: spaces and tabs collapse to one space; a "\n" STAYS a "\n"; three or
    # more newlines become two (a cue never draws more than two lines).
    out = re.sub(r"[ \t\r\f\v]+", " ", out)
    out = re.sub(r" *\n *", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = out.strip()
    # A cue that is ONLY a line break is a window-positioning event, not a
    # caption: it must not become a caption of its own.
    if not out.strip():
        return ""
    return out


def _segs_words(segs, start=0.0):
    """As palavras de um evento, cada uma com o instante ABSOLUTO dela.

    `tOffsetMs` e o relogio do proprio player: o YouTube revela a linha PALAVRA A
    PALAVRA. MEDIDO 2026-10-26 no payload de `WdaHAGRBB6s` (o das reclamacoes do
    dono): 69 dos 106 segmentos trazem `tOffsetMs`, e o primeiro evento revela
    `Have` em 0, ` you` em 240 ms, ` ever` em 400 ms. O dono pediu isso com todas as
    letras: *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou
    nao, igual o youtube."* Sem offsets nos cues nada pode ser exacto -- o Sotto
    pintava a linha inteira de uma vez.

    A regra de juncao e a MESMA de `_join_segs` (mesmas condicoes, mesma ordem), e o
    chamador CONFERE o resultado contra ele ao caractere. Quando as duas pontas nao
    batem, o cue fica sem palavras: uma revelacao inventada seria pior do que
    revelacao nenhuma.

    Um segmento sem `tOffsetMs` nao comeca palavra nova -- e a continuacao da
    anterior (o track automatico parte `palavra` de ` pontuacao`), por isso entra no
    texto da palavra que ja esta aberta. A PRIMEIRA palavra comeca com a LINHA: o
    YouTube desenha-a no instante do evento, mesmo quando o payload lhe da um offset
    positivo.
    """
    out = ""
    words = []
    for seg in segs or ():
        if not isinstance(seg, dict):
            continue
        piece = str(seg.get("utf8") or "")
        if not piece:
            continue
        if out and not piece[:1].isspace() and not out[-1:].isspace():
            first = piece[:1]
            last = out[-1:]
            attached = (first in _NO_SPACE_BEFORE or last in _NO_SPACE_AFTER
                        or (first in "'’" and last.isalnum()))
            if not attached:
                piece = " " + piece
        out += piece
        off = seg.get("tOffsetMs")
        if isinstance(off, (int, float)):
            words.append({"start": round(float(start) + float(off) / 1000.0, 3),
                          "text": piece})
        elif words:
            words[-1]["text"] += piece
        else:
            words.append({"start": round(float(start), 3), "text": piece})
    if not words:
        return []
    words[0]["start"] = round(float(start), 3)
    return words


#: Um evento cujo texto e so pontuacao nao e uma linha: e o resto da linha anterior.
_ONLY_PUNCT_RE = re.compile(r"^[.,;:!?…]+$")


def _absorb_punct(cues):
    """Junta a pontuacao solta a linha que ela continua.

    MEDIDO 2026-10-23, na faixa automatica `pt` do video `WdaHAGRBB6s`: o evento das
    16,26 s (`dDurationMs` 1060) tem um unico segmento `"."` e cai DENTRO da linha que
    comecou as 14,08 s e acaba as 17,26 s. O YouTube desenha `...crianças.` numa linha;
    o parser fazia dela DUAS -- uma delas um ponto sozinho, que e exactamente o tipo de
    lixo que o dono viu no painel (`"a legenda do youtube ta completamente bugada"`).
    A regra: pontuacao que comeca antes de a linha anterior acabar junta-se a ela e
    estende-a. Pontuacao que ja esta la nao se repete.
    """
    out = []
    for cue in cues or ():
        text = str(cue.get("text") or "").strip()
        if out and _ONLY_PUNCT_RE.match(text):
            prev = out[-1]
            try:
                inside = float(cue["start"]) <= float(prev["end"]) + 0.35
            except (KeyError, TypeError, ValueError):
                inside = False
            body = str(prev.get("text") or "").rstrip()
            if inside and body and not body.endswith(text):
                prev["text"] = body + text
                prev["end"] = max(float(prev["end"]), float(cue["end"]))
                # A revelacao acompanha a juncao: sem isto o ponto que se colou a linha
                # sumia do prefixo revelado (a palavra ficava a meio ate ao fim do cue).
                if prev.get("words"):
                    add = list(cue.get("words") or [])
                    if not add:
                        add = [{"start": round(float(cue["start"]), 3), "text": text}]
                    prev["words"] = list(prev["words"]) + add
                continue
        out.append(cue)
    return out


def parse_json3(text):
    """A json3 caption document -> cues `[{start, end, text}]`, in seconds.

    The PLAYER-WINDOW EVENTS ARE NOT CAPTIONS and are dropped: an event that
    carries `wpWinPosId` positions the auto-caption window, and an event
    that carries `aAppend` appends to it. MEASURED on the real auto track
    (104 events): all 51 of those events carry ZERO characters, so dropping
    them loses nothing -- and the `aAppend` rule is what keeps a window
    bookkeeping event out of the caption box.

    An event with no `segs`, or whose text is empty, is dropped too.
    """
    try:
        doc = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(doc, dict):
        return []
    events = [ev for ev in (doc.get("events") or []) if isinstance(ev, dict)]
    starts = []
    for ev in events:
        t = ev.get("tStartMs")
        starts.append(float(t) / 1000.0 if isinstance(t, (int, float)) else None)
    cues = []
    for i, ev in enumerate(events):
        if "wpWinPosId" in ev or ev.get("aAppend"):
            continue  # the player's window bookkeeping, not a caption
        start = starts[i]
        if start is None:
            continue
        segs = ev.get("segs")
        if not isinstance(segs, list) or not segs:
            continue
        body = _join_segs(segs)
        if not body:
            continue
        # O RELOGIO DA REVELACAO (2026-10-26). O cue leva as palavras com o instante
        # ABSOLUTO de cada uma, tirado do `tOffsetMs` do payload; o chamador confere a
        # concatenacao contra `body` e, se nao bater, o cue fica sem palavras.
        words = _segs_words(segs, start)
        if words and "".join(w["text"] for w in words).strip() != body:
            words = []
        dur = ev.get("dDurationMs")
        if isinstance(dur, (int, float)):
            end = start + float(dur) / 1000.0
        else:
            # No duration: the cue runs until the next event starts.
            nxt = next((s for s in starts[i + 1:] if s is not None), None)
            end = nxt if nxt is not None else start + 2.0
        if end <= start:
            end = start + 0.001
        cue = {"start": round(start, 3), "end": round(end, 3), "text": body}
        if words:
            # So entra quando o payload DECLARA o relogio: um cue sem `tOffsetMs` nao
            # ganha uma lista vazia, para a forma antiga continuar igual.
            cue["words"] = words
        cues.append(cue)
    cues.sort(key=lambda c: (c["start"], c["end"]))
    return _absorb_punct(cues)


_VTT_CUE_RE = re.compile(
    r"^\s*(?:(\d{1,3}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*"
    r"(?:(\d{1,3}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_VTT_TAG_RE = re.compile(r"<[^>]*>")


def _hms_to_s(hours, minutes, seconds, millis):
    return (int(hours or 0) * 3600 + int(minutes or 0) * 60 + int(seconds)
            + int(millis) / 1000.0)


def parse_vtt(text):
    """A WebVTT caption document -> cues `[{start, end, text}]`, in seconds.

    The `WEBVTT` header and the `NOTE`/`STYLE`/`REGION` blocks are skipped
    (their first line is not a timing line), and the inline markup
    (`<c>`, `<00:00:01.234>`) is stripped.
    """
    raw = str(text or "")
    if "WEBVTT" not in raw:
        return []
    blocks = []
    cur = []
    for line in raw.splitlines():
        if line.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append(cur)
    cues = []
    for block in blocks:
        timing = None
        for idx, line in enumerate(block):
            m = _VTT_CUE_RE.match(line.strip())
            if m:
                timing = (m, idx)
                break
        if timing is None:
            continue
        m, idx = timing
        g = m.groups()
        start = _hms_to_s(g[0], g[1], g[2], g[3])
        end = _hms_to_s(g[4], g[5], g[6], g[7])
        if end <= start:
            end = start + 2.0
        body = " ".join(_VTT_TAG_RE.sub("", ln) for ln in block[idx + 1:])
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        cues.append({"start": round(start, 3), "end": round(end, 3), "text": body})
    cues.sort(key=lambda c: (c["start"], c["end"]))
    return cues


def cue_at(cues, t):
    """The cue that covers the instant `t`, or None.

    A cue covers `[start, end)`. When cues OVERLAP -- and the automatic
    track's do, because its durations span whole phrases -- the one that
    STARTED LAST wins: that is the rolling caption the player is showing,
    not the phrase that started before it.
    """
    if t is None:
        return None
    try:
        t = float(t)
    except (TypeError, ValueError):
        return None
    best = None
    for cue in cues or ():
        if not isinstance(cue, dict):
            continue
        try:
            start = float(cue.get("start"))
            end = float(cue.get("end"))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        if start <= t < end:
            if best is None or start > float(best.get("start", -1)):
                best = cue
    return best


def state_for(track, t):
    """Which of the four states the caller is in.

    * `no-track`         -- there is nothing to show; KEEP THE ASR RUNNING.
    * `time-unknown`     -- the instant is not known; that is NOT "paused".
    * `has-track`        -- a cue covers the instant; show it.
    * `no-cue-in-window` -- the track exists but this instant has no cue.
    """
    if not isinstance(track, dict) or track.get("state") != "has-track":
        return "no-track"
    if t is None:
        return "time-unknown"
    if cue_at(track.get("cues") or (), t) is not None:
        return "has-track"
    return "no-cue-in-window"


def _lower_table(raw):
    """A yt-dlp language table -> (lowercased keys, original spelling).

    The key is matched case-insensitively ("PT-br" and "pt-BR" are the same
    language) but the ORIGINAL spelling is what the caller is told, because
    that is the language code YouTube itself uses.
    """
    table = {}
    case = {}
    for key, entries in (raw or {}).items():
        low = str(key).lower()
        if low not in table:
            table[low] = entries
            case[low] = str(key)
    return table, case


def _lang_keys(table, pref):
    """The keys of `table` that answer to `pref`, exact first."""
    exact = [pref] if pref in table else []
    prefixed = sorted(k for k in table
                       if k != pref and k.startswith(pref + "-"))
    return exact + prefixed


def _base_lang(lang):
    """A language code's BASE ('en-US' -> 'en', 'pt-BR' -> 'pt', 'es-419' -> 'es').

    MEASURED 2026-10-21: the languages YouTube publishes are region-qualified
    ('en-US', 'pt-BR', 'es-419') and the owner's rule is about the LANGUAGE, not
    about the region, so the comparison is made on the base.
    """
    return str(lang or '').strip().lower().split('-')[0]


#: THE TARGET LANGUAGE. The owner's rule, verbatim (2026-10-21, later the same
#: day): *"para de traduzir pra pt br do ingles e do espanhol. o resto, traduza
#: para ingles. qualquer outra lingua pra ingles."*
#:
#: So a video in a language OUTSIDE the untranslated set (below) is served in
#: **ENGLISH**: the original when the video is English, the auto-translation
#: into English when it is not.
TARGET_LANG = 'en'

#: THE ONE RULE THAT CAN NEVER BE BROKEN (owner, 2026-10-30, verbatim):
#: *"legendas nao traduzem entre ingles pt br e espanhol. so outras linguas,
#: todas pro ingles."*
#:
#: An English, Portuguese or Spanish video is served in ITS OWN language and
#: NOTHING ELSE -- no translation in either direction between those three. A
#: Spanish video with no Spanish track gets NO YouTube caption (the live
#: transcription of its own audio is the honest answer); it does NOT get the
#: English or the Portuguese one.
#:
#: This SUPERSEDES `NEVER_TRANSLATED_LANGS = ('es',)` (2026-10-21), which let a
#: Portuguese video be served in English -- measured for a `pt-BR` video, and
#: exactly what the owner now forbids. The old name is gone on purpose: a
#: second constant with the same job is a second truth.
UNTRANSLATED_LANGS = ('en', 'pt', 'es')


#: THE OWNER'S EXPLICIT TRANSLATION CHOICE (owner, 2026-10-21). `''` means the
#: POLICY above. A non-empty base code FORCES that target for EVERY video -- the
#: owner asked that the selector list every language, "inclusive as que acabei de
#: falar pra nao tocar", and that an explicit pick override the never-translate
#: rule. `set_target_language` is the ONE writer; the shell calls it from the
#: 3-dot menu's selector.
TARGET_OVERRIDE = ''


def set_target_language(code):
    """Set the explicit target, returning the base code that was applied.

    `''`/None clears it (back to the policy). The value is normalised to a BASE
    code (`pt-BR` -> `pt`) for the same reason `_base_lang` exists: the rule is
    about the language, not the region.
    """
    global TARGET_OVERRIDE
    TARGET_OVERRIDE = _base_lang(code) if code else ''
    return TARGET_OVERRIDE


def _target_langs(orig):
    """The languages this video's caption may be served in, in order.

    THE RULE THAT CAN NEVER BE BROKEN (owner, 2026-10-30, verbatim):
    *"legendas nao traduzem entre ingles pt br e espanhol. so outras linguas,
    todas pro ingles."*

    * **en / pt / es** (a video whose ORIGINAL language is one of those three):
      that language, AND NOTHING ELSE. No translation in any direction between
      those three, which is why the list has ONE element -- a fallback would be
      exactly the translation the owner forbade. A Spanish video with no Spanish
      track therefore serves NO YouTube caption, and the live transcription of
      its own audio stays the answer.
    * **any other language** (Chinese, Japanese, ...): ENGLISH -- the
      auto-translation into English -- and the video's OWN language as the last
      resort, for a video with no English track at all.

    `orig` empty means the original could not be read: the rule cannot speak,
    so the explicit pick is honoured when there is one (and nothing is asked for
    when there is not) -- that is the pre-policy behaviour, kept for the case
    where nobody can tell what the video is.
    """
    if not orig:
        # Without the video's own language the rule cannot speak at all, and the
        # explicit pick is the only thing left to honour.
        return (TARGET_OVERRIDE,) if TARGET_OVERRIDE else ()
    # THE RULE IS NOT A DEFAULT -- IT CANNOT BE BROKEN BY A PICK (owner, 2026-10-30:
    # *"regra nunca que pode ser quebrada: legendas nao traduzem entre ingles pt br
    # e espanhol"*). The 3-dot menu used to force ANY target over the policy
    # (`TARGET_OVERRIDE`, the owner's own request of 2026-10-21, when the policy
    # allowed translations between those three). Under today's order a pick that
    # would translate an en/pt/es video, or translate another language into
    # anything but English, is not a choice -- it is the forbidden translation.
    # So the pick is CLAMPED to the policy answer instead of being erased: the
    # menu keeps working, the log still records what was picked, and what reaches
    # the screen is always the rule.
    base = _base_lang(orig)
    if base in UNTRANSLATED_LANGS:
        return (base,)
    return (TARGET_LANG, orig)


def _original_language(info):
    """The video's OWN language, as a base code ('' when unknown).

    **THE `language` FIELD, NOT THE KEY THAT LOOKS ORIGINAL.** MEASURED
    2026-10-21 on the video the owner was watching (`-LODwSuymII`): yt-dlp says
    `language = 'en-US'` -- the video is ENGLISH -- and the table carries **177**
    languages. The Portuguese entry among them is an **AUTO-TRANSLATION**, and
    its URL carries **no `tlang`**, so "the key whose request has no tlang" is
    NOT proof of the original language. The field is.

    Before this was measured, the module served `pt-orig` for that English video
    and the owner saw Portuguese words on an English video -- verbatim: *"to
    vendo que o transcript atual ta sendo traduzido. nao e pra traduzir. e pra
    ser lingua original."*
    """
    lang = str((info or {}).get('language') or '').strip().lower()
    if not lang:
        return ''
    base = lang.split('-')[0]
    return base if base else ''


def _auto_lang_keys(table, pref):
    """The AUTOMATIC keys of one language, in the PLAYER's order.

    MEASURED 2026-10-20 on the video the owner watches (`cUeZMUGCxrw`),
    reading the real page's own `captionTracks` and the yt-dlp info dict of
    the SAME video side by side:

        the PLAYER's request for the track `a.pt`   ->  ?v=..&caps=asr&kind=asr&lang=pt
        yt-dlp's key `pt-orig`                      ->  ?v=..&caps=asr&kind=asr&lang=pt
        yt-dlp's key `pt`                           ->  ?v=..&caps=asr&kind=asr&lang=ar&tlang=pt

    So the track the PLAYER PAINTS is yt-dlp's `pt-orig` -- the key whose
    name ends in `-orig`, whose request carries NO `tlang`. The key `pt` is
    a DIFFERENT request: the original track translated ON THE FLY, which
    yt-dlp itself calls "damaged subtitles" ("Setting tlang=lang returns
    damaged subtitles", yt-dlp/extractor/youtube/_video.py) and which
    YouTube REFUSES -- MEASURED: HTTP 429 on every format, while
    `pt-orig` answers 200 with 679 cues of Portuguese.

    That is why `-orig` comes FIRST here: it is the track the player shows.
    """
    orig = pref + "-orig"
    keys = []
    if orig in table:
        keys.append(orig)
    if pref in table:
        keys.append(pref)
    for k in sorted(k for k in table
                    if k.startswith(pref + "-") and k not in (orig, pref)):
        keys.append(k)
    return keys


def _pick_entry(entries):
    """The best caption entry of one language, or None.

    `json3` first, `vtt` second. The `vtt` entry of an AUTOMATIC track is
    `protocol: m3u8_native` -- an HLS PLAYLIST, not a WebVTT document
    (MEASURED: 396 B starting `#EXTM3U`). Parsing that as VTT would yield an
    empty track and read as "this video has no captions", so it is refused.
    """
    by_ext = {}
    for entry in entries or ():
        if not isinstance(entry, dict):
            continue
        ext = str(entry.get("ext") or "").lower()
        if not ext or not entry.get("url"):
            continue
        by_ext.setdefault(ext, entry)
    for ext in _EXT_PREFERENCE:
        entry = by_ext.get(ext)
        if entry is None:
            continue
        if str(entry.get("protocol") or "").lower() == "m3u8_native":
            continue
        return entry
    return None


def tracks_from_info(info, lang_prefs=("pt", "en"), player_lang=None):
    """A yt-dlp info dict -> EVERY candidate track, in preference order.

    THE PLAYER'S TRACK COMES FIRST. `player_lang` is the language code the
    PLAYER says it is painting (`lang="pt"` on the player's own caption
    window -- MEASURED 2026-10-20). The owner's rule, verbatim: *"eu quero
    a legenda 1:1 do video do youtube ... o app só nao faz isso se nao tem a
    legenda disponivel."* -- so the track the player shows is the one the
    app serves, and the language preference is only the FALLBACK for when
    the player says nothing.

    The LANGUAGE wins over the source: a video with a manual German track and
    an automatic English one gives the owner the English one, because the
    owner's language is the better caption. Within one language, a MANUAL
    track wins over an automatic one -- EXCEPT that the automatic `-orig`
    track is the one the PLAYER paints when the video has no manual track
    for that language.

    WHY A LIST AND NOT ONE TRACK. MEASURED 2026-10-20, in the owner's own
    running app, on the video he was actually watching:
        YOUTUBE_TRACK_READY video_id=cUeZMUGCxrw state=no-track cues=0
            lang=pt source=auto reason=payload-failed
    The module had picked ONE track (the automatic one) and, when YouTube
    refused that payload, it reported the video as having no captions. But
    the MANUAL track of the SAME video answers 200 (MEASURED 2026-10-19:
    the automatic track of that video is HTTP 429 from the timedtext API on
    every format and user agent, and the manual one serves 200 on all
    four). So the video HAD a caption track, and the panel was empty.

    The list is tried in order until one yields cues, so a refused payload
    is a FALLBACK and never a verdict about the video.
    """
    if not isinstance(info, dict):
        return []
    manual, manual_case = _lower_table(info.get("subtitles") or {})
    auto, auto_case = _lower_table(info.get("automatic_captions") or {})
    prefs = [str(p).lower() for p in (lang_prefs or ()) if p]
    plang = str(player_lang or "").lower().strip()

    def pick(table, case, source, key):
        entry = _pick_entry(table.get(key))
        if entry is None:
            return None
        return {"lang": case.get(key, key), "source": source,
                "ext": str(entry.get("ext") or "").lower(),
                "url": entry.get("url"), "name": entry.get("name")}

    ordered = []
    seen = set()

    def take(table, case, source, key):
        if (source, key) in seen:
            return
        seen.add((source, key))
        found = pick(table, case, source, key)
        if found:
            ordered.append(found)

    # 0. THE POLICY (2026-10-21). The owner, verbatim, later the same day:
    #    *"para de traduzir pra pt br do ingles e do espanhol. o resto, traduza
    #    para ingles. qualquer outra lingua pra ingles."* -- and, earlier:
    #    *"nao e pra traduzir. e pra ser lingua original. ... ah, menos
    #    espanhol."*
    #
    #    THE SERVED LANGUAGE, owner's rule of 2026-10-30 (verbatim): *"legendas
    #    nao traduzem entre ingles pt br e espanhol. so outras linguas, todas
    #    pro ingles."* -> an EN, PT or ES video is served in ITS OWN language
    #    and NOTHING else (no fallback: a fallback between those three IS the
    #    translation he forbade); every OTHER language is served in ENGLISH.
    #
    #    MEASURED on the video the owner was watching: `language` = 'en-US'
    #    (ENGLISH) and the table carries 177 languages; the Portuguese entry
    #    was an AUTO-TRANSLATION whose URL carries NO `tlang` -- so "the key
    #    that looks original" is NOT proof of the original language. The
    #    `language` FIELD is.
    #
    #    The player's own track counts HERE ONLY in an ALLOWED language: the
    #    owner's "1:1 com o video do youtube" is about the caption being the
    #    VIDEO'S OWN caption and not a model transcription of its audio -- not
    #    about following a translation the player happens to have switched on.
    orig = _original_language(info)
    allowed = _target_langs(orig)
    if allowed:
        bases = set(_base_lang(x) for x in allowed)
        if plang and _base_lang(plang) in bases:
            for key in _lang_keys(manual, plang):
                take(manual, manual_case, "manual", key)
            for key in _auto_lang_keys(auto, plang):
                take(auto, auto_case, "auto", key)
        for lang in allowed:
            for key in _lang_keys(manual, lang):
                take(manual, manual_case, "manual", key)
            for key in _auto_lang_keys(auto, lang):
                take(auto, auto_case, "auto", key)
        if ordered:
            return ordered
        # THE POLICY FOUND NOTHING: the video has no track in any allowed
        # language. Its OWN language is then the honest answer -- and for a
        # KNOWN original the preference below does NOT apply: a Portuguese
        # translation of a Spanish video is exactly what the owner forbade,
        # and "no track" is not a verdict about the video -- it keeps the live
        # transcription running (the caller's contract).
        for key in _lang_keys(manual, orig):
            take(manual, manual_case, "manual", key)
        for key in _auto_lang_keys(auto, orig):
            take(auto, auto_case, "auto", key)
        return ordered
    # 1. THE TRACK THE PLAYER IS PAINTING. The player's own order for one
    #    language is: the MANUAL track when the video has one for that
    #    language, then the automatic `-orig` (the request without `tlang`,
    #    which is the player's request), and only then the translated one
    #    (the `tlang` request, the one YouTube refuses).
    if plang:
        for key in _lang_keys(manual, plang):
            take(manual, manual_case, "manual", key)
        for key in _auto_lang_keys(auto, plang):
            take(auto, auto_case, "auto", key)
    # 2. THE FALLBACK: the language preference, the player's own order
    #    inside one language (original first, translated second).
    for pref in prefs:
        for key in _lang_keys(manual, pref):
            take(manual, manual_case, "manual", key)
        for key in _auto_lang_keys(auto, pref):
            take(auto, auto_case, "auto", key)
    # 3. everything else, so a video is never left without a track.
    for table, case, source in ((manual, manual_case, "manual"),
                                (auto, auto_case, "auto")):
        for key in sorted(table):
            take(table, case, source, key)
    return ordered


def _rerank_reused(reused, lang_prefs, plang, older=None):
    """A LISTA REUTILIZADA E' RE-ESCOLHIDA PARA O PLAYER DE AGORA.

    MEDIDO 2026-10-30 (`_main/yt-player-track-oracle.py` braco a08): o cache da lista de
    candidatos existe para nao repetir os 5 s de `yt-dlp`, mas a lista era servida pela
    ORDEM em que a pergunta ANTERIOR a escreveu. O dono trocava a faixa no player de
    `pt` para `en` e a app servia `pt-orig` outra vez -- o `reason` dizia `ok` e o
    `cached` dizia `False`, ou seja, nada no resultado dizia que a pergunta tinha sido
    respondida com a ordem velha.

    A ORDEM E' A MESMA DE `tracks_from_info`: reconstroi-se as duas tabelas a partir dos
    candidatos (mais a lingua original guardada no cache) e pergunta-se outra vez. Um
    candidato que a re-escolha nao devolva NAO se perde: fica no fim.
    """
    cands = [c for c in (reused or []) if isinstance(c, dict) and c.get("url")]
    if not cands:
        return list(reused or [])
    manual, auto = {}, {}
    for cand in cands:
        entry = {"ext": cand.get("ext"), "url": cand.get("url"),
                 "name": cand.get("name")}
        table = manual if cand.get("source") == "manual" else auto
        table.setdefault(str(cand.get("lang") or ""), []).append(entry)
    pseudo = {"language": (older or {}).get("video_language") or None,
              "subtitles": manual, "automatic_captions": auto}
    try:
        ordered = tracks_from_info(pseudo, lang_prefs, plang)
    except Exception:  # noqa: BLE001 -- uma re-escolha que falha nao pode custar a lista
        return cands
    out = []
    used = set()
    for want in ordered:
        for index, cand in enumerate(cands):
            if index in used:
                continue
            if (str(cand.get("lang")) == str(want.get("lang"))
                    and cand.get("source") == want.get("source")):
                out.append(cand)
                used.add(index)
                break
    for index, cand in enumerate(cands):
        if index not in used:
            out.append(cand)
    return out


def track_from_info(info, lang_prefs=("pt", "en"), player_lang=None):
    """A yt-dlp info dict -> the track to use, or None.

    The FIRST of `tracks_from_info` -- the same order, the same winner.
    `None` means THE VIDEO HAS NO TRACK AT ALL -- the one verdict that must
    never be confused with "has a track".
    """
    ordered = tracks_from_info(info, lang_prefs, player_lang)
    return ordered[0] if ordered else None


# ── the disk cache ───────────────────────────────────────────────────────────

#: THE FORMAT OF A CACHE ENTRY. Bumped on 2026-10-20, when the reader
#: started trying EVERY candidate track: an entry written before that
#: knows ONE track, and the fallback cannot be done with it. MEASURED: the
#: owner's own video (`cUeZMUGCxrw`) stayed "no-track" with the new code
#: because the cache still held the old single-track entry.
#:
#: Bumped AGAIN on 2026-10-20, when the entry started to carry WHAT THE
#: PLAYER SHOWS (`player_lang`): an entry written before that does not know
#: which track the player is painting, and serving it would be serving the
#: line the owner can see is WRONG.
#: Quanto tempo a LISTA DE CANDIDATOS de um video pode ser reutilizada. As URLs
#: de legenda do YouTube sao assinadas e vivem horas; meia hora e' muito dentro
#: disso e cobre a troca de video, a recarga da pagina e um seek que mude a
#: faixa que o player pinta. Depois disso, uma extracao nova.
CANDIDATE_TTL_S = 1800.0

CACHE_SCHEMA = 3


def _cache_path(video_id):
    return os.path.join(CACHE_DIR, "%s.jsonl" % video_id)


def _ttl_for(result):
    """How long this verdict is good for."""
    if result.get("state") == "has-track":
        return TRACK_TTL_S
    if result.get("reason") == "payload-failed":
        return PAYLOAD_RETRY_TTL_S
    return NO_TRACK_TTL_S


def _cache_read(video_id, allow_stale=False):
    """The cached track for this video, or None (miss / expired / broken).

    `allow_stale` returns an EXPIRED entry too, marked with `stale`: that is
    how a refused payload is retried without repeating the 5 s extract.
    """
    try:
        with open(_cache_path(video_id), "r", encoding="utf-8") as fh:
            doc = json.loads(fh.read().strip() or "{}")
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    if doc.get("schema") != CACHE_SCHEMA:
        # AN ENTRY OF ANOTHER FORMAT. It is not a miss of the network: it is
        # a document this reader cannot use, and the extract has to run once
        # more to rebuild it in the current format.
        return None
    if not isinstance(doc, dict):
        return None
    ttl = _ttl_for(doc)
    try:
        fetched = float(doc.get("fetched_at") or 0.0)
    except (TypeError, ValueError):
        return None
    age = time.time() - fetched
    if age > ttl and not allow_stale:
        return None
    doc["cached"] = True
    doc["stale"] = age > ttl
    return doc


def _cache_write(video_id, result):
    """Write the track cache atomically. A failure here is not fatal."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = _cache_path(video_id)
        payload = {k: v for k, v in result.items()
                   if k not in ("cached", "stale")}
        # The temporary name ends in `.jsonl` too, so a crash cannot leave an
        # untracked file in the repository.
        tmp = os.path.join(CACHE_DIR, "%s.tmp.jsonl" % video_id)
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except Exception:
        pass


# ── the network ──────────────────────────────────────────────────────────────

class _NullLogger(object):
    """yt-dlp's logger, silenced. The shell must not get yt-dlp's chatter."""

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def _extract_info(video_id, timeout):
    """yt-dlp's info dict for this video, or None.

    `skip_download` + `download=False`: NO media is fetched, ever. Measured
    5.0 s for the metadata of a public video.
    """
    try:
        import yt_dlp
    except Exception:
        return None
    params = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": timeout,
        "extractor_retries": 1,
        "logger": _NullLogger(),
    }
    url = "https://www.youtube.com/watch?v=" + video_id
    try:
        with yt_dlp.YoutubeDL(params) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def _http_get(url, timeout):
    """A GET as a string, or None."""
    if not url:
        return None
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:
            return fh.read().decode("utf-8", "replace")
    except Exception:
        return None


def _fetch_payload(track, timeout):
    """The track's payload -> (cues, error)."""
    url = track.get("url")
    ext = str(track.get("ext") or "").lower()
    body = _http_get(url, timeout)
    if body is None:
        return [], "payload unreachable"
    if ext == "json3":
        if not body.lstrip().startswith("{"):
            return [], "payload is not json3"
        return parse_json3(body), None
    if ext == "vtt":
        if "WEBVTT" not in body:
            return [], "payload is not WebVTT"
        return parse_vtt(body), None
    return [], "unsupported format: %s" % ext


def _retry_payload(video_id, stale, timeout):
    """The payload the API REFUSED, asked for again -- without the extract.

    The 5 s yt-dlp extract is the expensive half; the caption track is a
    few KB. So a refused payload is retried on the track alone -- and on
    EVERY candidate, in the same order, because a refusal is a fallback
    and not a verdict about the video.
    """
    result = dict(stale)
    tracks = result.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        one = result.get("track")
        tracks = [one] if isinstance(one, dict) else []
    last_err = None
    cues = []
    for track in tracks:
        cues, err = _fetch_payload(track, timeout)
        if cues:
            result["lang"] = track.get("lang")
            result["source"] = track.get("source")
            result["ext"] = track.get("ext")
            last_err = err
            break
        last_err = err
    result["cues"] = cues
    result["error"] = last_err
    result["fetched_at"] = time.time()
    result["cached"] = False
    if cues:
        result["state"] = "has-track"
        result["reason"] = "ok"
    else:
        result["state"] = "no-track"
        result["reason"] = "payload-failed"
    _cache_write(video_id, result)
    return result


def fetch_track(video_id, lang_prefs=("pt", "en"), use_cache=True, timeout=45,
                player_lang=None, painted=None):
    """The video's caption track -- THE ONE THE PLAYER IS PAINTING.

    Returns a dict:

        {"state": "has-track", "cues": [{"start", "end", "text"}, ...],
         "lang": "pt-orig", "source": "auto", ...}

    or `{"state": "no-track", ...}` when the video has no caption track (or
    the track turned out to be empty). "no-track" is the caller's signal to
    KEEP THE ASR RUNNING. The extra keys (`reason`, `error`, `duration`,
    `cached`) say WHY, so a failure is never read as a verdict.

    `player_lang` is the language code the PLAYER is painting. `None` means
    "ask the player" (the live window is read); `""` means "the player said
    nothing" and the language preference decides. The answer is kept in the
    result (`player_lang`, `player_known`, `player_source`, `player_why`),
    because a track chosen WITHOUT knowing what the player shows is a
    FALLBACK, and the log has to say so.

    `painted` is the list of words the player is painting RIGHT NOW (see
    `painted_words`). When it is given, it DECIDES the track: the track the
    player shows is the one whose cues CONTAIN those words. MEASURED
    2026-10-20 on the owner's own video: the player painted `en-orig` while
    the language preference would have served `pt-orig`, and the owner's own
    comparison would have been Portuguese against English. With the paint,
    the served track is the one the player is REALLY showing -- and the
    result says so (`player_source="painted"`).

    The first call for a video is a network call and takes ~5 s (MEASURED);
    every later call is a disk read. Call it OFF the UI thread.
    """
    vid = str(video_id or "").strip()
    result = {
        "state": "no-track", "cues": [], "lang": None, "source": None,
        "ext": None, "video_id": vid, "duration": None, "reason": None,
        "error": None, "cached": False, "fetched_at": 0.0,
        "schema": CACHE_SCHEMA,
        # WHAT THE PLAYER SAID. `player_lang` is the language code the
        # player is painting ("" when it said nothing) and `player_known`
        # says whether it said anything at all. A fallback is a FALLBACK:
        # the log says so, and never pretends the first track that
        # answered is the one the player is showing.
        "player_lang": "", "player_known": False, "player_source": "",
        "player_why": "", "player_match": False,
    }
    if not _VIDEO_ID_RE.match(vid):
        result["reason"] = "invalid-video-id"
        result["error"] = "video id invalido: %r" % vid
        return result
    plang, psig = _resolve_player_track(vid, player_lang)
    result["player_lang"] = plang
    result["player_known"] = bool(psig.get("known"))
    result["player_source"] = psig.get("source") or ""
    result["player_why"] = psig.get("why") or ""
    cached = None
    if use_cache:
        cached = _cache_read(vid)
        if cached is not None:
            cached_lang = str(cached.get("player_lang") or "")
            # THE PAINT DECIDES WHICH TRACK THIS IS. The cached track is
            # served only when the player's own words ARE a cue of it.
            # MEASURED 2026-10-20: the cache held `pt-orig` while the player
            # painted `en-orig` -- serving the cache was serving the wrong
            # LANGUAGE to the owner.
            paint_hit = None
            paint_ok = True
            if painted:
                paint_hit = align_painted(cached.get("cues") or (), painted)
                paint_ok = paint_hit is not None
                if not paint_ok:
                    result["reason"] = "painted-other-track"
            if cached_lang == plang and paint_ok:
                cached.pop("stale", None)
                # WHAT THE PLAYER SAYS is knowledge of NOW, not of the
                # payload: the cached cues are still the right ones, but the
                # answer about the player is refreshed on every call.
                cached["player_lang"] = plang
                cached["player_known"] = bool(psig.get("known"))
                cached["player_source"] = psig.get("source") or ""
                cached["player_why"] = psig.get("why") or ""
                cached["player_match"] = _player_match(plang, cached.get("lang"))
                if paint_hit is not None:
                    # THE PLAYER'S OWN WORDS ARE IN THIS TRACK. That is a
                    # stronger answer than any language preference.
                    cached["player_source"] = "painted"
                    cached["player_known"] = True
                    cached["player_match"] = True
                    cached["paint_cue"] = paint_hit["index"]
                return cached
            # THE PLAYER CHANGED THE TRACK. The cached one is the WRONG
            # line for the owner, so it is not served: the candidates are
            # asked again, with the player's own language first. This is
            # not a verdict about the video -- it is a new question.
            if result.get("reason") != "painted-other-track":
                result["reason"] = "player-track-changed"
        else:
            # A REFUSED payload is retried WITHOUT repeating the 5 s extract:
            # the track and its signed URL are still in the cache, and only
            # the few KB of the caption track have to be asked for again.
            stale = _cache_read(vid, allow_stale=True)
            if (stale and stale.get("reason") == "payload-failed"
                    and isinstance(stale.get("track"), dict)
                    and str(stale.get("player_lang") or "") == plang):
                stale.pop("stale", None)
                return _retry_payload(vid, stale, timeout)
    # A EXTRACAO E' O CUSTO -- 5,0 s MEDIDOS por chamada de yt-dlp -- e o
    # yt-dlp nao precisa de correr duas vezes para a MESMA pergunta (dono,
    # 2026-10-30: *"trocar de video tambem demora pra caralho pra aparecer a
    # legenda"*). MEDIDO no log dele (`_main/webview-run.log`, troca das
    # 04:40:02): `EN-ORIG` pronto em 5,5 s, o pintado nao casou, e a SEGUNDA
    # resposta (`PT-ORIG`) chegou as 04:40:29 -- 27 s ate' a primeira legenda,
    # com DUAS extracoes dentro. A lista de candidatos (com as URLs) fica
    # guardada: uma re-escolha com o pintado custa as poucas KB de cada payload,
    # nao outra extracao.
    reused = None
    if use_cache:
        try:
            older = _cache_read(vid, allow_stale=True)
        except Exception:  # noqa: BLE001
            older = None
        cands = (older or {}).get("candidates")
        if isinstance(cands, list) and cands:
            try:
                age = time.time() - float((older or {}).get("fetched_at") or 0.0)
            except (TypeError, ValueError):
                age = CANDIDATE_TTL_S + 1
            if 0 <= age <= CANDIDATE_TTL_S:
                reused = _rerank_reused(cands, lang_prefs, plang, older)
                # A CONVENCAO DE LOG DESTE MODULO e' o `print` com a tag, e nao
                # um `log()` -- nao ha' `log` aqui, e a primeira versao desta
                # linha chamava-o: o oraculo apanhou o `NameError` na hora.
                if "sotto_webview" in sys.modules:
                    try:
                        print("sotto: YOUTUBE_TRACK_CANDIDATES_REUSED "
                              "video_id=%s count=%d age_s=%.0f"
                              % (vid, len(cands), age), flush=True)
                    except Exception:  # noqa: BLE001
                        pass
    info = None
    if reused is None:
        info = _extract_info(vid, timeout)
    if info is None and reused is None:
        # NOT cached: a failed extract is not a verdict about the video.
        result["reason"] = "extract-failed"
        result["error"] = "yt-dlp nao extraiu o video"
        return result
    if reused is not None:
        tracks = list(reused)
        result["duration"] = result.get("duration")
    else:
        duration = info.get("duration")
        if isinstance(duration, (int, float)):
            result["duration"] = float(duration)
        tracks = tracks_from_info(info, lang_prefs, plang)
        result["candidates"] = tracks
        # A LINGUA ORIGINAL VAI PARA O CACHE: a politica de 2026-10-21 decide a faixa a
        # partir dela, e uma re-escolha sobre `candidates` sem ela nao consegue repetir a
        # decisao -- so' a preferencia. Medido 2026-10-30 no braco a08.
        result["video_language"] = _original_language(info) or None
    if painted:
        # A BUSCA PELA PINTURA TEM UMA ORDEM MELHOR: as faixas ORIGINAIS
        # primeiro. MEASURED 2026-10-20: o pedido do player e `lang=X` SEM
        # `tlang`, que e a chave `-orig`; e num video com quatro variantes
        # de portugues (pt, pt-BR, pt-BR-orig, pt-PT) a original estava na
        # QUINTA posicao -- e a procura parava no limite antes de a ver.
        tracks = sorted(
            tracks,
            key=lambda t: 0 if str(t.get("lang") or "").endswith("-orig") else 1)
    result["fetched_at"] = time.time()
    if not tracks:
        result["reason"] = "no-tracks-listed"
        _cache_write(vid, result)
        return result
    # EVERY CANDIDATE IS TRIED, in order, until one yields cues. A refused
    # payload is a FALLBACK, never a verdict about the video.
    tried = []
    last_err = None
    fallback = None
    for track in tracks:
        if painted and len(tried) >= _PAINT_SEARCH_MAX:
            # THE BOUND IS CHECKED BEFORE THE FETCH, not after it. MEASURED
            # 2026-10-20: a search that checked the bound only after a
            # candidate with cues made TWENTY network calls (most of them
            # refused) to look for a track that was the fifth one.
            break
        cues, err = _fetch_payload(track, timeout)
        tried.append({"lang": track.get("lang"), "source": track.get("source"),
                      "ext": track.get("ext"), "url": track.get("url"),
                      "error": err, "cues": len(cues)})
        if not cues:
            last_err = err
            continue
        hit = align_painted(cues, painted) if painted else None
        if painted and hit is None:
            # THIS TRACK DOES NOT HOLD THE WORDS THE PLAYER IS PAINTING.
            # It is kept as the FALLBACK (a track is better than no track)
            # and the search goes on -- the track the player shows is the
            # one that CONTAINS its words.
            if fallback is None:
                fallback = (track, cues)
            if len(tried) >= _PAINT_SEARCH_MAX:
                break
            continue
        result["state"] = "has-track"
        result["reason"] = "ok"
        result["error"] = None
        result["cues"] = cues
        result["lang"] = track.get("lang")
        result["source"] = track.get("source")
        result["ext"] = track.get("ext")
        result["track"] = tried[-1]
        result["tracks"] = tried
        result["player_match"] = _player_match(plang, result.get("lang"))
        psig_used = psig
        if hit is not None:
            # THE PLAYER'S OWN WORDS ARE IN THIS TRACK. That is a stronger
            # answer than any language preference, and the log says so.
            result["player_match"] = True
            result["player_known"] = True
            result["player_source"] = "painted"
            result["paint_cue"] = hit["index"]
            psig_used = dict(psig)
            psig_used["known"] = True
            psig_used["source"] = "painted"
            psig_used["lang"] = result.get("lang") or ""
            psig_used["why"] = ""
        _log_player_track(psig_used, result["lang"], result["source"])
        _cache_write(vid, result)
        return result
    if fallback is not None:
        # NO CANDIDATE HELD THE PLAYER'S WORDS. The track that WAS serving
        # is KEPT -- not the language preference. A preference is a GUESS,
        # and serving a guess against the player's own words is exactly how
        # the owner ended up comparing Portuguese with English. MEASURED
        # 2026-10-20: the running app fell back to `pt-orig` and the log
        # said `player_source=painted-no-match` while the player painted
        # `en-orig`.
        if (cached is not None and cached.get("state") == "has-track"
                and cached.get("cues")):
            cues = cached.get("cues") or []
            lang = cached.get("lang")
            source = cached.get("source")
            ext = cached.get("ext")
        else:
            track, cues = fallback
            lang = track.get("lang")
            source = track.get("source")
            ext = track.get("ext")
        result["state"] = "has-track"
        result["reason"] = "ok"
        result["error"] = None
        result["cues"] = cues
        result["lang"] = lang
        result["source"] = source
        result["ext"] = ext
        result["track"] = tried[0] if tried else None
        result["tracks"] = tried
        result["player_match"] = False
        result["player_known"] = False
        result["player_source"] = "painted-no-match"
        result["player_why"] = ("as palavras pintadas nao estao em nenhum "
                                "candidato")
        psig_used = dict(psig)
        psig_used["known"] = False
        psig_used["source"] = "painted-no-match"
        psig_used["why"] = result["player_why"]
        _log_player_track(psig_used, result.get("lang"), result.get("source"))
        _cache_write(vid, result)
        return result
    result["error"] = last_err
    result["reason"] = "payload-failed" if last_err else "empty-track"
    result["track"] = tried[0] if tried else None
    result["tracks"] = tried
    # A REFUSED payload is not a verdict about the video: it is cached only
    # for the short back-off, and it keeps the tracks so the retry does not
    # repeat the extract.
    _log_player_track(psig, result.get("lang"), result.get("source"))
    _cache_write(vid, result)
    return result


# ── the player's clock ───────────────────────────────────────────────────────

_CLOCK_RE = re.compile(r"^\s*(?:(\d{1,3}):)?(\d{1,2}):(\d{2})\s*$")


def _parse_clock(text):
    """'M:SS' or 'H:MM:SS' -> seconds, or None."""
    m = _CLOCK_RE.match(str(text or ""))
    if not m:
        return None
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    if minutes > 59 or seconds > 59:
        return None
    return int(m.group(1) or 0) * 3600 + minutes * 60 + seconds


def _parse_time_pair(text):
    """'M:SS of M:SS' (or '/') -> (current, total) in seconds, or None."""
    raw = str(text or "").strip()
    for sep in (" of ", "/"):
        if sep in raw:
            left, _, right = raw.partition(sep)
            a = _parse_clock(left)
            b = _parse_clock(right)
            if a is not None and b is not None:
                return (a, b) if a <= b else (b, a)
    return None


def _uia():
    """The UI Automation root, or an exception the caller reports once."""
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as UIA
    return UIA, comtypes.client.CreateObject(UIA.CUIAutomation)


def _name(el):
    try:
        return str(el.CurrentName or "")
    except Exception:
        return ""


def _class_name(el):
    try:
        return str(el.CurrentClassName or "")
    except Exception:
        return ""


def _control_type_id(UIA, name, fallback):
    """The control-type id, from the typelib when it has it.

    MEASURED 2026-10-19 on this box's `UIAutomationClient`: the Slider is
    `UIA_SliderControlTypeId` = **50015**. 50013 is the RADIO BUTTON, and a
    query written with the wrong number returns an empty collection instead
    of raising -- which would have made the seek-bar path silently dead.
    """
    try:
        return int(getattr(UIA, name))
    except Exception:
        return fallback


def _find_by_type(uia, UIA, root, control_type):
    """The descendants of `root` with this control type."""
    try:
        cond = uia.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId,
                                           control_type)
        return root.FindAll(UIA.TreeScope_Descendants, cond)
    except Exception:
        return None


def _elements(coll):
    if coll is None:
        return
    try:
        length = int(coll.Length)
    except Exception:
        return
    for i in range(length):
        try:
            yield coll.GetElement(i)
        except Exception:
            continue


def _range_value(el, UIA):
    """(value, minimum, maximum) of a RangeValue element, or (None,)*3."""
    try:
        pattern = el.GetCurrentPattern(UIA.UIA_RangeValuePatternId)
        rp = pattern.QueryInterface(UIA.IUIAutomationRangeValuePattern)
        return float(rp.CurrentValue), float(rp.CurrentMinimum), float(rp.CurrentMaximum)
    except Exception:
        return None, None, None


def _value_text(el, UIA):
    """The element's `aria-valuetext` (Chrome exposes it as ValueValue)."""
    try:
        return str(el.GetCurrentPropertyValue(UIA.UIA_ValueValuePropertyId) or "")
    except Exception:
        return ""


def _slider_seconds(value, vmin, vmax, duration):
    """The seek bar's value -> seconds, or None when the unit is unknowable.

    The unit is DECIDED, not assumed:

    * a span of 1.0 is a FRACTION of the video -> `value * duration`;
    * a span of 100.0 is a PERCENT of the video -> `value/100 * duration`
      (and only when the video is longer than the span, otherwise a seconds
      reading is just as plausible and the honest answer is None);
    * any other span is a SECONDS scale -> the value itself.

    A candidate that lands outside the video is rejected: a wrong instant is
    worse than no instant.
    """
    if value is None or vmin is None or vmax is None:
        return None
    span = vmax - vmin
    if span <= 0:
        return None
    candidates = []
    if duration:
        d = float(duration)
        if abs(span - 1.0) < 1e-6:
            candidates.append((value - vmin) * d)
        if abs(span - 100.0) < 1e-6 and d > 100.0:
            candidates.append((value - vmin) / 100.0 * d)
        candidates.append(value - vmin)
    else:
        if abs(span - 1.0) < 1e-6:
            return None  # a fraction with no duration is not an instant
        candidates.append(value - vmin)
    for t in candidates:
        if t < 0:
            continue
        if duration and t > float(duration) * 1.05:
            continue
        return t
    return None


#: O ELEMENTO DO RELOGIO, por janela (2026-11-02). A busca por ControlType e'
#: SERVER-SIDE mas ainda percorre a arvore inteira do Chrome: MEDIDO no dono,
#: com a legenda calada, a leitura do laco externo custava 844-3547 ms por tick.
#: O relogio e' o MESMO elemento durante todo o video -- guarda-se e le-se o
#: valor por ele (2 chamadas), com a busca de volta quando ele morre.
_TIME_TEXT_CACHE = {}
_TIME_SLIDER_CACHE = {}


def _cached_el(cache, hwnd):
    if not hwnd:
        return None
    return cache.get(int(hwnd))


def _clock_from_text_el(el, duration):
    """O instante desta Text element, ou None quando ela nao e' o relogio."""
    name = _name(el).strip()
    if not name:
        return None
    cls = _class_name(el).lower()
    pair = _parse_time_pair(name)
    if pair is not None:
        current, total = pair
        return {"t": float(current), "source": "text", "raw": name,
                "total": float(total), "cls": cls}
    one = _parse_clock(name)
    if one is None:
        return None
    if "time" not in cls:
        return None
    # A BARE clock is the current time only if it is NOT the total
    # duration: the modern YouTube player shows ONLY the duration
    # ('ytp-time-duration'), and a bare clock equal to the duration is
    # the total, not the instant.
    if duration is None:
        return None
    if abs(one - float(duration)) < 1.0:
        return None
    return {"t": float(one), "source": "text", "raw": name, "cls": cls}


def _time_from_text(uia, UIA, root, duration, hwnd=None):
    """The player's own clock, read from the Text elements."""
    best = None
    cached = _cached_el(_TIME_TEXT_CACHE, hwnd)
    if cached is not None:
        try:
            hit = _clock_from_text_el(cached, duration)
            if hit is not None:
                return hit
        except Exception:  # noqa: BLE001
            pass
        if hwnd:
            _TIME_TEXT_CACHE.pop(int(hwnd), None)
    text_type = _control_type_id(UIA, "UIA_TextControlTypeId", 50020)
    for el in _elements(_find_by_type(uia, UIA, root, text_type)):
        hit = _clock_from_text_el(el, duration)
        if hit is not None:
            if hwnd:
                _TIME_TEXT_CACHE[int(hwnd)] = el
            return hit
    return best


def _slider_hit(el, UIA, duration):
    """`(score, hit)` para UMA Slider element. `hit` e' None se nao for relogio."""
    value, vmin, vmax = _range_value(el, UIA)
    valuetext = _value_text(el, UIA)
    pair = _parse_time_pair(valuetext)
    cls = _class_name(el).lower()
    score = 0
    if duration and vmax:
        d = float(duration)
        if abs(vmax - d) <= max(1.0, 0.02 * d):
            score += 4  # the seek bar: its maximum IS the video's length
    if "progress" in cls:
        score += 2  # MEASURED: YouTube's seek bar is `ytp-progress-bar`
    if vmax and vmax > 100.0:
        score += 1  # a video's length; the volume slider stops at 100
    if pair is not None:
        score += 1
    if pair is not None:
        return score, {"t": float(pair[0]), "source": "valuetext",
                       "raw": valuetext, "slider": [value, vmin, vmax]}
    t = _slider_seconds(value, vmin, vmax, duration)
    if t is None:
        return score, None
    return score, {"t": t, "source": "slider", "raw": valuetext,
                   "slider": [value, vmin, vmax]}


def _time_from_slider(uia, UIA, root, duration, hwnd=None):
    """The player's clock, read from the seek bar.

    MEASURED 2026-10-19 on a real YouTube window (the owner's own, a
    28:33 video): the seek bar is a UIA **Slider**, name "Botão deslizante de
    busca", class `ytp-progress-bar`, `value=407.0`, `min=0.0`,
    `max=1713.0` -- 1713 s IS the length of that video, so the RangeValue is
    in SECONDS and its maximum is the duration.

    The page has a SECOND slider -- the volume, class `ytp-volume-panel`,
    `value=48.0`, `max=100.0` -- and a percent scale must never be read as
    an instant. So the sliders are SCORED and the seek bar is the one whose
    maximum IS the video's length.
    """
    cached = _cached_el(_TIME_SLIDER_CACHE, hwnd)
    if cached is not None:
        try:
            _score, hit = _slider_hit(cached, UIA, duration)
            if hit is not None:
                return hit
        except Exception:  # noqa: BLE001
            pass
        if hwnd:
            _TIME_SLIDER_CACHE.pop(int(hwnd), None)
    slider_type = _control_type_id(UIA, "UIA_SliderControlTypeId", 50015)
    best = None
    for el in _elements(_find_by_type(uia, UIA, root, slider_type)):
        score, hit = _slider_hit(el, UIA, duration)
        if hit is None:
            continue
        if best is not None and score <= best[0]:
            continue
        best = (score, hit)
        if hwnd:
            _TIME_SLIDER_CACHE[int(hwnd)] = el
    return best[1] if best else None


#: O logger do shell, posto por ele (`youtube_captions` nao tem log proprio).
PROF_HOOK = None


def _yt_prof(stage, t0):
    """`YT_PROF stage=.. ms=..` no log do shell, so' com `SOTTO_YT_PROFILE=1`.

    MEDIDO 2026-11-02 no dono: o relogio do player custava 375-4859 ms por
    tick, e o desenho custava 47-172 ms. O gargalo tem de ser um numero.
    """
    if os.environ.get("SOTTO_YT_PROFILE") != "1":
        return
    hook = PROF_HOOK
    if hook is None:
        return
    try:
        hook('YT_PROF stage=%s ms=%.1f' % (stage, (time.monotonic() - t0) * 1000.0))
    except Exception:  # noqa: BLE001
        pass

def player_time_detail(uia, UIA, hwnd, duration=None):
    """Where the video is, and how that was decided.

    `duration` is the video's length in seconds (from `fetch_track`). It is
    what turns a percentage into an instant, and it is what tells a bare
    clock (the player's TOTAL duration) from the current time.

    Returns `{"t": float|None, "source": ..., "why": ...}`. `t` is None when
    the instant is not known -- which is NOT the same as "the video is
    stopped".
    """
    out = {"t": None, "source": None, "why": "", "raw": None, "total": None,
           "slider": None}
    try:
        root = uia.ElementFromHandle(hwnd)
    except Exception as exc:
        out["why"] = "no-root (%s)" % type(exc).__name__
        return out
    if root is None:
        out["why"] = "no-root"
        return out
    _t_dbg = time.monotonic()
    text_hit = _time_from_text(uia, UIA, root, duration, hwnd=hwnd)
    _yt_prof("clock-text", _t_dbg)
    _t_dbg = time.monotonic()
    slider_hit = _time_from_slider(uia, UIA, root, duration, hwnd=hwnd)
    _yt_prof("clock-slider", _t_dbg)
    if text_hit is not None:
        out.update(text_hit)
        if slider_hit is not None and slider_hit.get("t") is not None:
            if abs(float(text_hit["t"]) - float(slider_hit["t"])) > 1.5:
                out["why"] = ("text and slider disagree: text=%s slider=%s"
                              % (text_hit["t"], slider_hit["t"]))
            else:
                out["why"] = "text (the slider agrees: %s)" % slider_hit["t"]
        else:
            out["why"] = "text"
        return out
    if slider_hit is not None and slider_hit.get("t") is not None:
        out.update(slider_hit)
        out["why"] = slider_hit.get("source") or "slider"
        return out
    out["why"] = "no clock found (text and seek bar unreadable)"
    return out


def player_time(uia, UIA, hwnd, duration=None):
    """The video's current instant in seconds, or None when it is unknown."""
    detail = player_time_detail(uia, UIA, hwnd, duration=duration)
    t = detail.get("t")
    return None if t is None else float(t)


# ── the player's track: WHICH track the player is painting ──────────────────

#: The class of the PLAYER'S OWN caption window, and the attribute that
#: carries the track it is painting.
#:
#: MEASURED 2026-10-20 on the real page (headless Edge, muted playback, the
#: video the owner watches -- `cUeZMUGCxrw`):
#:
#:     <div class="caption-window ytp-caption-window-bottom
#:          ytp-caption-window-rollup" id="caption-window-1" dir="ltr"
#:          tabindex="0" lang="pt" draggable="true" style="...">
#:
#: and the player PAINTED Portuguese (">> Configurar leva 1 minuto.
#: Conecte o Discord e é só mandar mensagem. [música]"). So the `lang`
#: attribute is the player's own answer to "which track am I painting",
#: and the answer is a YouTube language code.
_CAPTION_WINDOW_CLASS = "ytp-caption-window"
#: The container carries the same prefix and NO language: it must not win.
_CAPTION_WINDOW_CONTAINER = "ytp-caption-window-container"

#: UIA's language property. The comtypes typelib does not export the name.
_UIA_LANGUAGE_ID = 30007

#: Windows language id -> the language code YouTube writes in `lang=`.
#: The player's own tag is BCP-47 ("pt"); the accessibility tree reports a
#: Windows language id, so the id is mapped back to the code. The regions
#: collapse onto their language ("pt-BR" and "pt-PT" are both "pt"), which
#: is what the player's own `lang` says too.
_LCID_LANG = {
    1025: "ar", 1026: "bg", 1027: "ca", 1028: "zh", 1029: "cs", 1030: "da",
    1031: "de", 1032: "el", 1033: "en", 1034: "es", 1035: "fi", 1036: "fr",
    1037: "he", 1038: "hi", 1039: "hu", 1040: "it", 1041: "ja", 1042: "ko",
    1043: "nl", 1044: "nb", 1045: "pl", 1046: "pt", 1048: "ro", 1049: "ru",
    1050: "hr", 1051: "sk", 1052: "sq", 1053: "sl", 1054: "sr", 1055: "sv",
    1057: "id", 1058: "uk", 1059: "be", 1060: "sl", 1061: "et", 1062: "lv",
    1063: "lt", 1065: "ms", 1066: "my", 1068: "az", 1069: "eu", 1071: "mk",
    1078: "af", 1079: "ka", 1080: "mn", 1081: "mr", 1084: "km", 1086: "ne",
    1087: "fa", 1089: "am", 1091: "kk", 1093: "kn", 1095: "ps", 1097: "si",
    1104: "km", 1110: "gl", 1140: "gom", 2052: "zh", 2057: "en", 2058: "es",
    2070: "pt", 2074: "sr", 3076: "zh", 3081: "en", 3082: "es",
}

#: The last (player language, served track) pair that was logged. The line
#: is written when the ANSWER CHANGES: a log that repeats the same state
#: every 30 s is noise, and a state that is never written is a lie.
_LAST_PLAYER_TRACK = [""]


def _all_elements(uia, root):
    """Every descendant of `root`, or None when the tree refuses."""
    try:
        return root.FindAll(0x4, uia.CreateTrueCondition())  # Descendants
    except Exception:
        return None


def _language_of(el):
    """The element's language as a YouTube code -> (code, source)."""
    try:
        raw = el.GetCurrentPropertyValue(_UIA_LANGUAGE_ID)
    except Exception:
        raw = None
    if isinstance(raw, int) and raw > 0:
        code = _LCID_LANG.get(raw)
        if code:
            return code, "uia-language-id:%d" % raw
    return "", ""


def player_caption_window(uia, UIA, root):
    """The player's caption window element -> (element, code, source).

    The element that carries the language is the one INSIDE the container
    (`caption-window ytp-caption-window-bottom ...`); the container itself
    (`ytp-caption-window-container`) has no language and must not win.
    """
    best = None
    for el in _elements(_all_elements(uia, root)):
        cls = _class_name(el).lower()
        if _CAPTION_WINDOW_CLASS not in cls:
            continue
        if _CAPTION_WINDOW_CONTAINER in cls:
            continue
        code, source = _language_of(el)
        if code:
            return el, code, source
        if best is None:
            best = el
    if best is None:
        return None, "", ""
    return best, "", ""


def _external_subs():
    """The sibling module, imported BY PATH.

    The gates load this file by path (`importlib`), so its own directory is
    not on `sys.path` and a plain `import external_subs` fails there. The
    app imports both as siblings, so this is only a safety net -- but a
    failed import must not look like "the player said nothing".
    """
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    import external_subs
    return external_subs


_WINDOW_VID_TTL_S = 5.0
_window_vid_memo = {}


def _window_video_id(hwnd, uia, UIA):
    """The video id playing in this window, or "" when it cannot be read.

    MEMOIZED FOR `_WINDOW_VID_TTL_S` (MEDIDO 2026-11-03): a varredura da arvore
    de acessibilidade custa 60-140 ms e uma vez 6,8 s nesta maquina, e esta
    funcao corre no caminho da LEITURA da legenda -- `EXTERNAL_CAPTIONS_READ_MS`
    publicou `phases={'vid': 1125.0}` com as outras fases a 0,0. O id so' serve
    para recusar um player que mostra OUTRO video: cinco segundos de atraso nessa
    recusa nao custa nada, e um segundo por leitura custa tudo.
    """
    key = int(hwnd or 0)
    now = time.monotonic()
    hit = _window_vid_memo.get(key)
    if hit is not None and 0.0 <= now - hit[1] <= _WINDOW_VID_TTL_S:
        return hit[0]
    vid = ""
    try:
        es = _external_subs()
        for value in es.edit_values(hwnd, uia, UIA):
            vid = video_id_from_url(value)
            if vid:
                break
    except Exception:
        vid = ""
    _window_vid_memo[key] = (vid, now)
    return vid


def player_track_signal(video_id=None, hwnd=None):
    """WHAT THE PLAYER SAYS, read from the live window (READ-ONLY).

    Returns a dict:

        {"lang": "pt", "known": True, "source": "uia-language-id:1046",
         "why": "", "painted": ">> Configurar leva 1 minuto..."}

    `known` is False when the player did not say -- and `why` says why. A
    player that says NOTHING is not a player that is showing nothing: the
    caller falls back to the language preference AND says so in the log.

    `SOTTO_YT_PLAYER_TRACK=0` turns the live read OFF (the escape hatch for
    a gate that must not touch the owner's browser).
    """
    if str(os.environ.get("SOTTO_YT_PLAYER_TRACK") or "1").strip() in ("0", "off", "false"):
        return {"lang": "", "known": False, "source": "disabled",
                "why": "SOTTO_YT_PLAYER_TRACK=0", "painted": ""}
    if not hwnd:
        try:
            es = _external_subs()
            hwnd = es.find_player_window()
        except Exception as exc:  # noqa: BLE001
            return {"lang": "", "known": False, "source": "player-window-error",
                    "why": repr(exc), "painted": ""}
    if not hwnd:
        return {"lang": "", "known": False, "source": "no-player-window",
                "why": "janela do player nao encontrada", "painted": ""}
    try:
        UIA, uia = _uia()
        root = uia.ElementFromHandle(hwnd)
    except Exception as exc:  # noqa: BLE001
        return {"lang": "", "known": False, "source": "uia-error",
                "why": repr(exc), "painted": ""}
    if root is None:
        return {"lang": "", "known": False, "source": "no-uia-root",
                "why": "a janela nao devolveu a raiz", "painted": ""}
    # THE VIDEO. A player showing ANOTHER video says nothing about this one.
    if video_id:
        shown = _window_video_id(hwnd, uia, UIA)
        if shown and shown != str(video_id):
            return {"lang": "", "known": False, "source": "other-video",
                    "why": "o player esta a mostrar %s" % shown, "painted": ""}
    el, code, source = player_caption_window(uia, UIA, root)
    painted = _name(el) if el is not None else ""
    if not code:
        return {"lang": "", "known": False,
                "source": "no-caption-window-lang",
                "why": "a janela de legenda do player nao disse a lingua",
                "painted": painted}
    return {"lang": code, "known": True, "source": source, "why": "",
            "painted": painted}


def _resolve_player_track(video_id=None, player_lang=None):
    """(lang, signal) -- the player's track, and HOW it was known.

    `player_lang=None` means "ask the player". `""` means "the player said
    nothing" and the language preference decides.
    """
    if player_lang is not None:
        code = str(player_lang or "").lower().strip()
        if code:
            return code, {"lang": code, "known": True, "source": "caller",
                          "why": "", "painted": ""}
        return "", {"lang": "", "known": False, "source": "caller",
                    "why": "o player nao disse", "painted": ""}
    sig = player_track_signal(video_id)
    return str(sig.get("lang") or "").lower(), sig


def _player_match(plang, served):
    """Is the served track THE ONE the player is painting?

    The player's track of the language `pt` is the yt-dlp key `pt` (a manual
    track) or `pt-orig` (the automatic one, whose request carries no `tlang`
    -- MEASURED 2026-10-20). Anything else is a FALLBACK, and the log says
    so.
    """
    p = str(plang or "").lower().strip()
    s = str(served or "").lower().strip()
    if not p or not s:
        return False
    return s in (p, p + "-orig")


def _log_player_track(signal, served_lang, served_source):
    """THE LINE THAT SAYS WHETHER THE APP KNOWS THE PLAYER'S TRACK.

    The repo's rule, and the owner's: a refused payload is a FALLBACK,
    never a verdict. So when the player did not say which track it is
    showing, the log says THAT -- with the reason -- instead of pretending
    that the first track that answered is the right one.
    """
    known = bool(signal.get("known"))
    lang = signal.get("lang") or ""
    served = served_lang or "-"
    sig = "%s|%s|%s" % (lang, served, "1" if known else "0")
    if sig == _LAST_PLAYER_TRACK[0]:
        return
    _LAST_PLAYER_TRACK[0] = sig
    # THE APP'S LOG. The shell prints every line to its own stdout (the
    # `sotto: ` tag is what every consumer in this repo reads), so the line
    # is written when the shell is the one running -- a gate reads the
    # RETURNED DICT (`player_known`, `player_why`), which is the same
    # information without the noise.
    if "sotto_webview" not in sys.modules:
        return
    try:
        print("sotto: YOUTUBE_PLAYER_TRACK known=%s lang=%s source=%s "
              "served=%s served_source=%s why=%s"
              % (1 if known else 0, lang or "-", signal.get("source") or "-",
                 served, served_source or "-", signal.get("why") or "-"),
              flush=True)
    except Exception:  # noqa: BLE001 -- a log line must never break a read
        pass


# ── the probe ────────────────────────────────────────────────────────────────

def _foreground_hwnd():
    import ctypes
    return int(ctypes.windll.user32.GetForegroundWindow() or 0)


# ── THE LINE THE PLAYER IS PAINTING (the 1:1 source) ────────────────────────
#
# MEASURED 2026-10-20 on the owner's own Chrome, on the video he was
# watching (`cUeZMUGCxrw`, 21:55), with the player PLAYING:
#
#   * the caption window is `caption-window ytp-caption-window-bottom
#     ytp-caption-window-rollup ytp-rollup-mode`, and its UIA children are
#     ONE PER WORD (15 children, 15 words, no class, no children of their
#     own);
#   * those words CHANGE while the video plays: 'with this one. So, let me
#     click on this. Here's what the workflow looks like. If you' ->
#     'over here. Now one thing to note is that some of you might see this',
#     8 s later;
#   * and the words ARE a cue of the track: 'further. And in theory, this
#     should help you generate a' is the cue 426.64-430.72 of `en-orig`.
#
# SO THE PAINT IS THE TRUTH about the two things the UIA could not answer:
#
#   1. WHICH TRACK the player is showing. MEASURED: the caption window has
#      NO language property (0 of 448 elements expose UIA 30007), so the
#      app fell back to the preference and served `pt-orig` while the player
#      painted `en-orig` -- the owner would have compared Portuguese against
#      English and called it broken.
#   2. WHERE THE VIDEO IS. MEASURED: the seek bar's RangeValue AND the
#      player's own clock text are FROZEN: +0.00 s in 8.35 s of wall clock,
#      while the painted line advanced +8.96 s in the track. The clock the
#      app read (t=2.0) was 8 minutes away from the truth (t=530).
#
# ⇒ THE PAINT IS THE SOURCE, AND THE TRACK IS FOUND BY MATCHING IT.

#: The class of the PLAYER'S OWN caption window. The container
#: (`ytp-caption-window-container`) carries the same prefix and NO words: it
#: must not win.
_CAPTION_WINDOW_WORDS = "caption-window"

#: The minimum number of words that must match EXACTLY for an alignment to
#: count. MEASURED: the WRONG track (Portuguese, on the same video) aligns
#: with ZERO words, while the right track aligns with the whole cue.
_ALIGN_MIN_EXACT = 3

#: HOW MANY CANDIDATE TRACKS are fetched while looking for the one that
#: holds the player's words. MEASURED 2026-10-20 on the owner's own video:
#: the paint is in `en-orig`, which is the THIRD candidate (`pt-orig`, `pt`,
#: `en-orig`), so three payload fetches find it. The bound keeps a video
#: with a hundred automatic translations from costing a hundred requests.
_PAINT_SEARCH_MAX = 6


def _painted_children(el, uia):
    """The words of ONE caption-window element, in reading order."""
    out = []
    try:
        kids = el.FindAll(0x2, uia.CreateTrueCondition())  # TreeScope_Children
    except Exception:
        return out
    for k in range(kids.Length):
        c = kids.GetElement(k)
        try:
            name = str(c.CurrentName or "").strip()
        except Exception:
            continue
        if name:
            out.append(name)
    return out


def _painted_items(el, uia, with_rect=True):
    """Os filhos de UMA janela de legenda: [{"text", "left", ...}].

    `with_rect=False` NAO le o rectangulo de cada filho, e isso e' a diferenca
    entre uma leitura barata e uma cara (2026-11-02). MEDIDO no dono: com o
    rectangulo de cada filho, uma leitura custa 62-125 ms (cada `CurrentName` e
    `CurrentBoundingRectangle` e' uma chamada fora do processo, ~4 ms cada, e uma
    cue tem 12-18 filhos); sem o rectangulo, custa os nomes.

    O rectangulo continua a ser lido -- mas quando o TEXTO MUDA, nao a cada tick:
    o container da legenda sobrevive a' cue e so' os filhos mudam. Ver
    `painted_words(with_rect=)` e `sotto_webview._yt_rows`.
    """
    out = []
    try:
        kids = el.FindAll(0x2, uia.CreateTrueCondition())  # TreeScope_Children
    except Exception:
        return out
    for k in range(kids.Length):
        c = kids.GetElement(k)
        try:
            name = str(c.CurrentName or "").strip()
        except Exception:
            continue
        if not name:
            continue
        item = {"text": name, "left": 0, "top": 0, "right": 0, "bottom": 0}
        # O RECT DE UM FILHO QUE NAO MUDOU NAO SE LE OUTRA VEZ (2026-11-02).
        # Ordem do dono, verbatim: *"as legendas tao flickando. tao bugadas. ficam
        # sumindo e aperecendo ou trocando a atual e a antiga ao mesmo tempo"*. O
        # defeito era MISTURAR snapshots: o tick lia so' NOMES e `painted_rows`
        # montava as linhas com os RECTS da leitura ANTERIOR -- a linha nova saia
        # com a geometria da velha, e as duas apareciam trocadas. Agora o tick faz
        # UMA leitura que ja' traz rects: os que este filho ja' tinha na posicao em
        # que ele esta' (mesmo indice, mesma palavra) sao reaproveitados, e o resto
        # e' lido. Uma foto por tick, nunca duas.
        # O RECT REAPROVEITADO POR INDICE FOI APAGADO EM 2026-11-03, e a razao e'
        # MEDIDA, nao estetica. Ele existia para poupar uma chamada por filho que
        # "nao mudou" (mesmo indice, mesma palavra) -- mas numa ROLAGEM o player
        # mantem as mesmas palavras em indices diferentes, e uma palavra que
        # sobreviveu no mesmo indice pode ter mudado de LINHA. As linhas do Sotto
        # saiam com a geometria do instante anterior, agrupadas pelo `left`:
        #   player: ['conseguiu entrar. mas vamos ver, viper', 'ainda esta viva, da para']
        #   sotto : ['conseguiu ainda esta entrar. viva, da para']
        # -- palavras certas, ordem trocada, e no pior caso a mesma palavra duas
        # vezes (`'ainda esta viva, da para da para'`). MEDIDO com
        # `_main/_yt-live-latency.py` sobre a legenda viva (45 s): 20 quadros
        # errados deste tipo em 32. Uma foto por tick continua a ser a regra; o que
        # sai e' reaproveitar a geometria de OUTRA foto.
        if not with_rect:
            out.append(item)
            continue
        try:
            rect = c.CurrentBoundingRectangle
            item["left"] = int(rect.left)
            item["top"] = int(rect.top)
            item["right"] = int(rect.right)
            item["bottom"] = int(rect.bottom)
        except Exception:  # noqa: BLE001
            pass
        out.append(item)
    return out


def _rendered(el):
    """Is this element actually being DRAWN, or is it a leftover in the tree?

    MEASURED (2026-10-22, the owner's own tab): the browser painted NOT ONE caption
    line for 30.5 s of playback -- 400 samples of the caption window, all empty --
    and `painted_words` still returned EIGHT words. Eight is exactly
    `"Have you ever had to kill a man?"`, the line that had been painted before the
    captions were turned off: the element stays in the accessibility tree once it
    stops being drawn, and `_painted_children` reads its children happily.

    That ghost is the desync: the app believed YouTube was painting a line, aligned
    it to a cue, and showed it -- at the wrong second, over and over. So an element
    counts only when the OS says it is on-screen AND it has a real rectangle.
    """
    try:
        if bool(el.CurrentIsOffscreen):
            return False
    except Exception:  # noqa: BLE001
        return False
    try:
        rect = el.CurrentBoundingRectangle
        if int(rect.right) - int(rect.left) <= 0 or int(rect.bottom) - int(rect.top) <= 0:
            return False
    except Exception:  # noqa: BLE001
        return False
    return True


#: A ultima janela de legenda que serviu, por janela do sistema (`hwnd`). E' o
#: cache que evita varrer a arvore de acessibilidade do Chrome inteira a cada
#: leitura -- ver a nota em `painted_words`.
_CAPTION_WINDOW_CACHE = {}


def _caption_windows(uia, root, hwnd=None):
    """[(elemento, classname_lower)] das janelas de legenda DESTA raiz.

    Duas metades, e a ordem importa:

      1. A JANELA CACHEADA, quando ela ainda desenha (o container sobrevive a'
         troca de cue -- medido: o mesmo `ytp-caption-window-container` serve
         todas as cues de um video). Custa os filhos, nao a arvore.
      2. A VARREDURA, quando nao ha' cache, quando o elemento morreu (excepcao
         da UIA) ou quando ele deixou de desenhar. A varredura e' a unica coisa
         que acha uma janela NOVA (outro video, outro player), por isso nunca sai.

    O cache e' por `hwnd` porque o dono troca de janela: um `root` de outro
    processo nao pode herdar o elemento do anterior.
    """
    key = int(hwnd or 0)
    cached = _CAPTION_WINDOW_CACHE.get(key)
    if cached is not None:
        el, cls = cached
        try:
            # NAO SE TESTA `_rendered` AQUI (2026-11-02). Entre duas cues o
            # container existe mas nao desenha, e testar isso jogava o cache fora
            # a cada buraco -- a varredura da arvore INTEIRA voltava a' cada tick
            # (medido: 94 ms de leitura com a legenda calada). Quem decide se
            # desenha e' `painted_words`, elemento a elemento; aqui o cache so'
            # cai quando o elemento MORRE (excepcao da UIA).
            el.CurrentBoundingRectangle
            return [(el, cls)]
        except Exception:  # noqa: BLE001 - elemento morto: cai para a varredura
            _CAPTION_WINDOW_CACHE.pop(key, None)
    out = []
    for el in _elements(_all_elements(uia, root)):
        cls = _class_name(el).lower()
        if _CAPTION_WINDOW_WORDS not in cls:
            continue
        out.append((el, cls))
    if out and key:
        # O maior primeiro: e' o que `painted_words` escolhe de qualquer forma.
        try:
            out.sort(key=lambda pair: -len(_painted_children(pair[0], uia)))
        except Exception:  # noqa: BLE001
            pass
        _CAPTION_WINDOW_CACHE[key] = out[0]
    return out

def painted_words(uia, UIA, hwnd=None, root=None, with_rect=True):
    """The words the player is painting NOW -> {"words": [...], "why": ...}.

    READ-ONLY: it opens nothing, clicks nothing, moves nothing.

    `why` says what happened, so an empty answer is never read as "the
    player has no caption": `no-window`, `no-root`, `no-painted-caption`
    (the captions are OFF, or the player is between cues) or `painted`.
    """
    if root is None:
        if not hwnd:
            return {"words": [], "cls": "", "why": "no-window"}
        try:
            root = uia.ElementFromHandle(hwnd)
        except Exception as exc:  # noqa: BLE001
            return {"words": [], "cls": "",
                    "why": "no-root (%s)" % type(exc).__name__}
    if root is None:
        return {"words": [], "cls": "", "why": "no-root"}
    best = []
    best_cls = ""
    best_items = []
    # A JANELA DE LEGENDA E' CACHEADA POR HWND (2026-11-02). A varredura antiga
    # pedia `FindAll(Descendants, TrueCondition)` do Chrome INTEIRO a cada 0,30 s
    # -- milhares de elementos, cada um uma leitura de propriedade cross-process.
    # MEDIDO no log do dono: as decisoes de pintura saem a 1,6-3 s de distancia
    # (`YOUTUBE_CAPTION` 22:36:16.265, :17.632, :19.221, :22.161) enquanto a
    # legenda do player muda muito mais depressa -- e a imagem dele mostra o
    # YouTube em `Larocache...` com o Sotto ainda no cue anterior. O container da
    # legenda NAO muda quando a cue muda (so' os filhos mudam), por isso ele e'
    # achado uma vez e reaproveitado; a varredura volta quando ele deixa de servir
    # (`_caption_windows` explica a regra de saida).
    for el, cls in _caption_windows(uia, root, hwnd=hwnd):
        if _CAPTION_WINDOW_WORDS not in cls:
            continue
        # A CAPTION WINDOW THAT IS NOT ON SCREEN IS NOT A CAPTION (2026-10-22).
        # Without this, the window that stopped being drawn keeps handing over its
        # last line, and the app shows it as if the player were painting it now.
        if not _rendered(el):
            continue
        items = _painted_items(el, uia, with_rect=with_rect)
        words = [it["text"] for it in items]
        if len(words) >= len(best):
            best = words
            best_cls = _class_name(el)
            best_items = items
    if not best:
        return {"words": [], "cls": "", "why": "no-painted-caption", "items": []}
    # AS QUEBRAS DE LINHA SAO DO PLAYER, E ESTAO' NO RECT (2026-11-02). As
    # palavras da legenda automatica chegam soltas; o que diz em que LINHA cada
    # uma cai e' o rectangulo de cada filho. `items` leva-os a quem desenha.
    return {"words": best, "cls": best_cls, "why": "painted", "items": best_items}


def _align_from(cue_words, low, j0, off0):
    """Walk the cues from (j0, off0) against the painted words.

    Returns `{"index", "painted_from", "aligned", "exact", "partial"}` or
    None. `partial` is True when the painted words stop INSIDE the cue --
    the player types a cue word by word and we may catch it mid-word.
    """
    n = len(low)
    pos = 0
    idx = j0
    off = off0
    cur = None
    cur_start = 0
    exact = 0
    partial = False
    while pos < n and idx < len(cue_words):
        cwords = cue_words[idx]
        if not cwords:
            idx += 1
            off = 0
            continue
        take = min(len(cwords) - off, n - pos)
        last = (pos + take) >= n
        for i in range(take):
            a = cwords[off + i].lower()
            b = low[pos + i]
            if a == b:
                exact += 1
                continue
            # THE PLAYER IS MID-WORD. MEASURED 2026-10-20: the rollup showed
            # '...click anywhere on t' while the track says '...anywhere on
            # the', and '...connect the output ba' while the track says
            # '...the output back'. The LAST word may be a prefix of the
            # track's word -- even a ONE LETTER prefix ('t' for 'the') --
            # and any other mismatch is a mismatch.
            if last and i == take - 1 and len(b) >= 1 and a.startswith(b):
                partial = True
                continue
            return None
        pos += take
        cur = idx
        cur_start = pos - take
        if off + take < len(cwords):
            break
        idx += 1
        off = 0
    if pos != n or cur is None:
        return None
    return {"index": cur, "from_index": j0, "painted_from": cur_start,
            "aligned": pos, "exact": exact, "partial": partial}


def _align_tokens(tokens):
    """Tokens de fala, sem o marcador `>>` do player -- os dois lados da comparacao."""
    out = []
    for tok in tokens or ():
        text = str(tok)
        while text.startswith(">>"):
            text = text[2:].strip()
        text = text.strip()
        if text:
            out.append(text)
    return out


def align_painted(cues, painted):
    """Which cue is the player painting? -> dict or None.

    The rollup holds the last few cues and the player types the current one
    word by word, so the painted words are the CONCATENATION of the last
    cues' texts, cut at the word being typed -- and cut at the FRONT too,
    because the rollup drops the oldest line. MEASURED: the rollup's first
    word is often in the middle of a cue.

    So the alignment walks the track's cues and accepts a run that matches
    the painted words from ANY point of any cue.

    Returns:
        `{"index", "from_index", "painted_from", "cue", "text", "exact",
        "aligned", "partial"}` -- `text` is the FULL text of the cue being
        painted (the app shows the whole line; the player shows it a word at
        a time), or None when no cue matches (the paint belongs to ANOTHER
        track, or is empty). `from_index` is the FIRST cue of the matched
        run and `painted_from` is the word offset of the last chunk inside
        `index`, so `aligned - painted_from` is how many words of `index`
        the player has already painted. The rollup window is that run.
    """
    if isinstance(painted, str):
        painted = painted.split()
    # O MARCADOR DE FALA NAO ALINHA (2026-11-02). MEDIDO nesta box: o player
    # pintava `[\'>> Nossa.\', \'>> ta\', \'segurando\', ...]` -- linhas e
    # palavras MISTURADAS na mesma lista, com `>>` colado ao primeiro token de
    # cada linha --, as cues da faixa `pt-orig` tambem trazem `>>`, e o
    # alinhamento dava `match=0` numa faixa que era a nossa. O ecra caia no ramo
    # do relogio, e e\' desse ramo que vinham as tres imagens do dono. A
    # comparacao passa a ser feita em PALAVRAS, com o marcador removido dos dois
    # lados; o `>>` continua a existir no texto servido (e\' dele, nao nosso).
    painted = _align_tokens(" ".join(str(w) for w in (painted or ())).split())
    if not painted:
        return None
    low = [w.lower() for w in painted]
    cue_words = [_align_tokens(str((c or {}).get("text") or "").split())
                 for c in (cues or ())]
    best = None
    for j0, cwords in enumerate(cue_words):
        if not cwords:
            continue
        for off0 in range(len(cwords)):
            if cwords[off0].lower() != low[0]:
                continue
            hit = _align_from(cue_words, low, j0, off0)
            if hit is None or hit["exact"] < _ALIGN_MIN_EXACT:
                continue
            if best is None or hit["exact"] > best["exact"]:
                best = hit
            break
    if best is None:
        return None
    cue = (cues or ())[best["index"]]
    return {"index": best["index"], "cue": cue,
            "text": str((cue or {}).get("text") or "").strip(),
            "exact": best["exact"], "aligned": best["aligned"],
            "from_index": best["from_index"], "painted_from": best["painted_from"],
            "partial": best["partial"]}


def probe(seconds=8.0, interval=0.4, duration=None):
    """Print what the player's clock says, poll by poll. Launches nothing."""
    UIA, uia = _uia()
    hwnd = _foreground_hwnd()
    print("PROBE hwnd=%d" % hwnd, flush=True)
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        detail = player_time_detail(uia, UIA, hwnd, duration=duration)
        print("PROBE t=%-10s source=%-9s raw=%-22r why=%s"
              % (detail.get("t"), detail.get("source"), detail.get("raw"),
                 detail.get("why")), flush=True)
        time.sleep(interval)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="YouTube's real caption track")
    ap.add_argument("--probe", action="store_true",
                    help="print the player's clock, poll by poll")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--duration", type=float, default=None,
                    help="the video's length in seconds (from fetch_track)")
    ap.add_argument("--track", default=None,
                    help="print the track of this video id")
    ap.add_argument("--url", default=None, help="the video id from a URL")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if args.track:
        vid = args.track
        if args.url:
            vid = video_id_from_url(args.url) or vid
        track = fetch_track(vid)
        summary = {k: v for k, v in track.items() if k != "cues"}
        summary["n_cues"] = len(track.get("cues") or ())
        summary["first_cues"] = (track.get("cues") or ())[:3]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.probe:
        return probe(seconds=args.seconds, duration=args.duration)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
