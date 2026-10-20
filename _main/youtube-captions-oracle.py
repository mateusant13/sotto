"""ORACLE for `app/webview/youtube_captions.py` -- the REAL YouTube caption track.

Owner, 2026-10-19: *"youtube ta mostrando texto burro da pagina inves da porra
da legenda/transcriptino de um video"* and *"e nao e pra tu parar de transcrever
audio do chrome. é audio do youtube CASO tenha legenda do youtube. se for um
video sem legenda, vaio transcrever ao vivo igual."*

WHAT THIS PINS
--------------
`external_subs.py` reads the text the YouTube PAGE is painting, and what
reached the owner's caption box on 2026-10-19 19:14-19:21 was page chrome
(`Oferta sujeita aos termos. ...`, `há 4 sem.`, recommended-video titles).
This module does the other thing: it asks YOUTUBE for the video's own caption
track and asks the player where it is in the video.

So the gate has to hold three things at once:

  1. THE PARSE. A json3 event that is the player's caption-WINDOW bookkeeping
     (`aAppend` / `wpWinPosId`) is NOT a caption and must be discarded -- the
     owner's brief called it "o evento de palavra automatico". A WebVTT track
     is parsed too, and a payload that is not WebVTT (the automatic track's
     `vtt` entry is an HLS PLAYLIST, `protocol: m3u8_native`, measured: 396 B
     starting `#EXTM3U`) must NOT be mistaken for an empty track.
  2. THE INSTANT. `cue_at` is `[start, end)`; the boundaries are the edges.
     `player_time` reads the player's own clock; when it cannot know the
     instant it says None, and None is NOT "the video is stopped".
  3. THE "no-track" VERDICT. A video with no caption track must say
     `no-track` and the caller must KEEP THE ASR RUNNING. `no-track` must
     NEVER be confused with `has-track` -- that is the whole point of the
     owner's second sentence, and it is what the executed mutant below
     breaks on purpose.

ARMS (pure: no network, no browser, no app)
    The parse, the boundaries, the four states, the URL shapes, the track
    choice, the cache, and the player's clock -- the last one through a FAKE
    UI Automation tree, so the unit of the seek bar is decided by the code and
    not by whether a YouTube window happens to be open.

NEGATIVE ARM (executed, not decorative)
    Ten mutants of the module, each a TEXTUAL patch of a unique anchor. A
    mutant whose anchor is missing or ambiguous is DECORATIVE -- it proves
    nothing -- so the oracle refuses to count it. Each mutant is loaded and
    the SAME battery runs; the checks that go RED name it.

LIVE ARM (optional, `--live`)
    The real path: yt-dlp against two public videos. `dQw4w9WgXcQ` (manual
    pt-BR + en) must give a real track with real cues; `aqz-KE-bpKQ` (Big
    Buck Bunny -- MEASURED: `subtitles=0`, `automatic_captions=0`) must give
    `no-track`. It is OFF by default so the gate stays green on a machine
    with no network.

Usage:
    python _main/youtube-captions-oracle.py            # arms + mutants, rc=0 on PASS
    python _main/youtube-captions-oracle.py --neg-arm  # mutants only, rc=1 BY DESIGN
    python _main/youtube-captions-oracle.py --live     # + the network arm
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODULE_PATH = os.path.join(REPO, "app", "webview", "youtube_captions.py")

EXIT_PASS = 0
EXIT_FAIL = 1

#: The real video with NO caption track at all. MEASURED 2026-10-19:
#: `subtitles=0`, `automatic_captions=0` (Big Buck Bunny 60fps 4K, 635 s).
LIVE_NO_TRACK_VIDEO = "aqz-KE-bpKQ"
#: The real video WITH a track. MEASURED 2026-10-19: 5 manual languages
#: (de-DE, en, es-419, ja, pt-BR) + 160 automatic ones; 213 s.
LIVE_HAS_TRACK_VIDEO = "dQw4w9WgXcQ"
#: MEASURED on the manual pt-BR json3 of that video: 60 events.
LIVE_MANUAL_CUES = 60


# ── the fixtures ─────────────────────────────────────────────────────────────
# They are EMBEDDED here (this lane owns exactly two files), and they are the
# REAL shapes measured on 2026-10-19 -- the event keys, the `utf8` values, the
# `aAppend`/`wpWinPosId` bookkeeping, the `tOffsetMs` word offsets.

#: A real json3, trimmed. The FIRST event is the player's window-position
#: marker (real: `{'dDurationMs','id','tStartMs','wpWinPosId','wsWinStyleId'}`,
#: no `segs`). The SECOND is the automatic "word" event the owner's brief
#: named -- an `aAppend` event that carries TEXT, which is exactly the thing
#: that must never reach the caption box. The rest are real caption events.
FIXTURE_JSON3 = json.dumps({
    "wireMagic": "pb3",
    "pens": [{"wsWinStyleId": 1, "penId": 1}],
    "wsWinStyles": [{"wsWinStyleId": 1, "penId": 1}],
    "wpWinPositions": [{"wpWinPosId": 1, "wsWinStyleId": 1}],
    "events": [
        # the window position: no segs, no text. MUST be discarded.
        {"tStartMs": 0, "dDurationMs": 211879, "id": 1, "wpWinPosId": 1,
         "wsWinStyleId": 1},
        # the automatic WORD event: it carries text. MUST be discarded.
        {"tStartMs": 18790, "wWinId": 1, "aAppend": 1,
         "segs": [{"utf8": "strangers"}]},
        # a real automatic caption event, with per-word offsets.
        {"tStartMs": 18800, "dDurationMs": 7160, "wWinId": 1,
         "segs": [{"utf8": "We're", "acAsrConf": 0},
                  {"utf8": " no", "tOffsetMs": 239, "acAsrConf": 0},
                  {"utf8": " strangers", "tOffsetMs": 559, "acAsrConf": 0}]},
        # a real MANUAL caption event, with the newline inside one segment.
        {"tStartMs": 22640, "dDurationMs": 4320,
         "segs": [{"utf8": "Você conhece as regras,\ne eu também"}]},
        # a line-break event: its text is EMPTY, so it must not become a cue.
        # MEASURED: the real auto track carries 8 of these (`aAppend` with
        # `segs: [{"utf8": "\n"}]`).
        {"tStartMs": 30000, "dDurationMs": 500, "wWinId": 1,
         "segs": [{"utf8": "\n"}]},
    ],
}, ensure_ascii=False)

#: A real WebVTT, trimmed from the manual pt-BR track of `dQw4w9WgXcQ`.
FIXTURE_VTT = (
    "WEBVTT\nKind: captions\nLanguage: pt-BR\n"
    "\n00:00:18.640 --> 00:00:21.880\nNão somos estranhos ao amor\n"
    "\n00:00:22.640 --> 00:00:26.960\nVocê conhece as regras,\ne eu também\n"
    "\n00:00:27.040 --> 00:00:31.040\nEstou pensando\nem um relacionamento sério\n"
)

#: What the automatic track's `vtt` entry really returns. MEASURED: 396 B
#: starting `#EXTM3U` -- an HLS PLAYLIST, not a WebVTT document.
FIXTURE_M3U8 = (
    "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-TARGETDURATION:600\n"
    "#EXTINF:213,\nhttps://www.youtube.com/api/timedtext?caps=asr&v=dQw4w9WgXcQ"
    "&lang=en\n"
)

#: A yt-dlp info dict, shaped like the MEASURED one.
FIXTURE_INFO = {
    "id": "dQw4w9WgXcQ",
    "duration": 213,
    "subtitles": {
        "pt-BR": [
            {"ext": "json3", "url": "https://example.invalid/ptbr.json3",
             "name": "Portuguese (Brazil)"},
            {"ext": "vtt", "url": "https://example.invalid/ptbr.vtt"},
            {"ext": "srv3", "url": "https://example.invalid/ptbr.xml"},
        ],
        "de-DE": [
            {"ext": "json3", "url": "https://example.invalid/de.json3"},
        ],
    },
    "automatic_captions": {
        "en": [
            {"ext": "vtt", "url": "https://example.invalid/en.m3u8",
             "protocol": "m3u8_native"},
            {"ext": "json3", "url": "https://example.invalid/en.json3"},
        ],
        "pt-BR": [
            {"ext": "vtt", "url": "https://example.invalid/ptbr_auto.m3u8",
             "protocol": "m3u8_native"},
        ],
    },
}


#: The real shape of a language whose ONLY caption entry is the HLS playlist.
#: MEASURED: `automatic_captions['pt-BR']` of `dQw4w9WgXcQ` has exactly one
#: entry -- `{'ext': 'vtt', 'protocol': 'm3u8_native'}` -- and no json3.
FIXTURE_INFO_PLAYLIST_ONLY = {
    "id": "dQw4w9WgXcQ",
    "duration": 213,
    "subtitles": {},
    "automatic_captions": {
        "pt-BR": [
            {"ext": "vtt", "url": "https://example.invalid/ptbr_auto.m3u8",
             "protocol": "m3u8_native"},
        ],
    },
}


# ── a fake UI Automation tree ────────────────────────────────────────────────
# The player's clock is measured through this, so the gate does not depend on
# a YouTube window being open (it was NOT open on this box on 2026-10-19, and
# opening a browser is not this lane's business).

class _FakePattern(object):
    def __init__(self, value, vmin, vmax):
        self.CurrentValue = value
        self.CurrentMinimum = vmin
        self.CurrentMaximum = vmax

    def QueryInterface(self, _cls):
        return self


class _FakeElement(object):
    def __init__(self, name="", cls="", control_type=50020, value=None,
                 vmin=None, vmax=None, valuetext=""):
        self.CurrentName = name
        self.CurrentClassName = cls
        self.CurrentControlType = control_type
        self._value = value
        self._vmin = vmin
        self._vmax = vmax
        self._valuetext = valuetext

    def GetCurrentPattern(self, pid):
        if self._value is None:
            raise RuntimeError("pattern %s not supported" % pid)
        return _FakePattern(self._value, self._vmin, self._vmax)

    def GetCurrentPropertyValue(self, _pid):
        return self._valuetext


class _FakeCollection(object):
    def __init__(self, elements):
        self._elements = list(elements)
        self.Length = len(self._elements)

    def GetElement(self, i):
        return self._elements[i]


class _FakeRoot(object):
    def __init__(self, elements):
        self._elements = list(elements)

    def FindAll(self, _scope, cond):
        wanted = cond[1] if isinstance(cond, tuple) else None
        return _FakeCollection([e for e in self._elements
                                 if wanted is None
                                 or e.CurrentControlType == wanted])


class _FakeAutomation(object):
    def __init__(self, elements):
        self._root = _FakeRoot(elements)

    def CreatePropertyCondition(self, prop, value):
        return (prop, value)

    def ElementFromHandle(self, _hwnd):
        return self._root


class _FakeUIAModule(object):
    UIA_ControlTypePropertyId = 30003
    UIA_ValuePatternId = 10002
    UIA_RangeValuePatternId = 10003
    UIA_ValueValuePropertyId = 30045
    TreeScope_Descendants = 4
    # MEASURED on this box's UIAutomationClient: the Slider is 50015 (50013
    # is the RADIO BUTTON), the Text is 50020.
    UIA_SliderControlTypeId = 50015
    UIA_TextControlTypeId = 50020
    IUIAutomationRangeValuePattern = object
    IUIAutomationValuePattern = object


def _slider(value, vmin, vmax, valuetext="", name="Progress bar",
            cls="ytp-progress-bar"):
    return _FakeElement(name=name, cls=cls, control_type=50015,
                         value=value, vmin=vmin, vmax=vmax, valuetext=valuetext)


def _text(name, cls="ytp-time-duration"):
    return _FakeElement(name=name, cls=cls, control_type=50020)


# ── the battery ──────────────────────────────────────────────────────────────

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_fetch(mod, info, payload):
    """Make `fetch_track` run the WHOLE pipeline without the network."""
    calls = {"extract": 0, "http": 0}

    def _extract(_vid, _timeout):
        calls["extract"] += 1
        return info

    def _http(_url, _timeout):
        calls["http"] += 1
        return payload

    mod._extract_info = _extract
    mod._http_get = _http
    return calls


def battery(mod, path, workdir, source):
    """The arms. Every one of them is pure: no network, no browser, no app."""
    rows = []

    def attempt(name, fn):
        try:
            ok, detail = fn()
        except Exception as exc:                            # noqa: BLE001
            ok, detail = False, "EXCEPTION %s: %s" % (type(exc).__name__, exc)
        rows.append((ok, name, detail))

    # -- the URL shapes ----------------------------------------------------
    def a01():
        vid = mod.video_id_from_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s")
        return vid == "dQw4w9WgXcQ", "got %r" % vid
    attempt("a01 video_id_from_url tira o id de watch?v=", a01)

    def a02():
        vid = mod.video_id_from_url("https://youtu.be/dQw4w9WgXcQ?t=10")
        return vid == "dQw4w9WgXcQ", "got %r" % vid
    attempt("a02 video_id_from_url tira o id de youtu.be/", a02)

    def a03():
        vid = mod.video_id_from_url("https://example.com/watch?v=dQw4w9WgXcQ")
        return vid is None, "got %r" % vid
    attempt("a03 video_id_from_url NAO inventa um id de outra pagina", a03)

    # -- the json3 parse ---------------------------------------------------
    def a04():
        cues = mod.parse_json3(FIXTURE_JSON3)
        texts = [c["text"] for c in cues]
        ok = texts == ["We're no strangers",
                       "Você conhece as regras, e eu também"]
        return ok, "cues=%r" % (texts,)
    attempt("a04 parse_json3 tira os cues REAIS e nada mais", a04)

    def a05():
        cues = mod.parse_json3(FIXTURE_JSON3)
        texts = [c["text"] for c in cues]
        ok = "strangers" not in texts and len(texts) == 2
        return ok, "texts=%r" % (texts,)
    attempt("a05 parse_json3 DESCARTA o evento de palavra automatico "
            "(aAppend)", a05)

    def a06():
        cues = mod.parse_json3(FIXTURE_JSON3)
        ok = all(c["text"].strip() for c in cues)
        return ok, "cues=%r" % (cues,)
    attempt("a06 parse_json3 nao devolve nenhum cue com texto vazio", a06)

    def a07():
        cues = mod.parse_json3(FIXTURE_JSON3)
        by = {c["text"]: c for c in cues}
        cue = by.get("We're no strangers")
        ok = cue is not None and abs(cue["start"] - 18.8) < 0.01 \
            and abs(cue["end"] - 25.96) < 0.01
        return ok, "cue=%r" % (cue,)
    attempt("a07 parse_json3 converte tStartMs/dDurationMs em segundos", a07)

    def a08():
        cues = mod.parse_json3(FIXTURE_JSON3)
        cue = [c for c in cues if "regras" in c["text"]]
        ok = bool(cue) and "  " not in cue[0]["text"] \
            and "\n" not in cue[0]["text"]
        return ok, "cue=%r" % (cue,)
    attempt("a08 parse_json3 junta os segmentos sem espaco duplo", a08)

    def a09():
        cues = mod.parse_json3("not json at all")
        return cues == [], "cues=%r" % (cues,)
    attempt("a09 parse_json3 de um payload que nao e json devolve []", a09)

    # -- the vtt parse -----------------------------------------------------
    def a10():
        cues = mod.parse_vtt(FIXTURE_VTT)
        ok = len(cues) == 3 and cues[0]["text"] == "Não somos estranhos ao amor"
        return ok, "cues=%r" % (cues[:2],)
    attempt("a10 parse_vtt le a faixa WebVTT", a10)

    def a11():
        cues = mod.parse_vtt(FIXTURE_VTT)
        cue = cues[1]
        ok = abs(cue["start"] - 22.64) < 0.01 and abs(cue["end"] - 26.96) < 0.01
        return ok, "cue=%r" % (cue,)
    attempt("a11 parse_vtt converte o tempo do WebVTT em segundos", a11)

    def a12():
        cues = mod.parse_vtt(FIXTURE_M3U8)
        return cues == [], "cues=%r" % (cues,)
    attempt("a12 parse_vtt de uma PLAYLIST HLS devolve [] "
            "(nao e 'video sem legenda')", a12)

    # -- the boundaries ----------------------------------------------------
    def a13():
        cues = [{"start": 10.0, "end": 20.0, "text": "A"},
                {"start": 30.0, "end": 40.0, "text": "B"}]
        got = mod.cue_at(cues, 10.0)
        return got is not None and got["text"] == "A", "got %r" % (got,)
    attempt("a13 cue_at no INICIO: o comeca entra (start inclusivo)", a13)

    def a14():
        cues = [{"start": 10.0, "end": 20.0, "text": "A"}]
        got = mod.cue_at(cues, 15.0)
        return got is not None and got["text"] == "A", "got %r" % (got,)
    attempt("a14 cue_at no MEIO: o cue que cobre o instante", a14)

    def a15():
        cues = [{"start": 10.0, "end": 20.0, "text": "A"}]
        got = mod.cue_at(cues, 20.0)
        return got is None, "got %r" % (got,)
    attempt("a15 cue_at no FIM: o cue acabou (end exclusivo)", a15)

    def a16():
        cues = [{"start": 10.0, "end": 20.0, "text": "A"}]
        got = mod.cue_at(cues, 99.0)
        return got is None, "got %r" % (got,)
    attempt("a16 cue_at FORA da janela: None", a16)

    def a17():
        cues = [{"start": 10.0, "end": 30.0, "text": "A"},
                {"start": 20.0, "end": 40.0, "text": "B"}]
        got = mod.cue_at(cues, 25.0)
        return got is not None and got["text"] == "B", "got %r" % (got,)
    attempt("a17 cue_at com cues sobrepostos: ganha o que comecou depois", a17)

    # -- the four states ---------------------------------------------------
    def a18():
        track = {"state": "has-track",
                 "cues": [{"start": 10.0, "end": 20.0, "text": "A"}]}
        got = mod.state_for(track, 15.0)
        return got == "has-track", "got %r" % (got,)
    attempt("a18 state_for: ha-track quando o cue cobre o instante", a18)

    def a19():
        track = {"state": "has-track",
                 "cues": [{"start": 10.0, "end": 20.0, "text": "A"}]}
        got = mod.state_for(track, 99.0)
        return got == "no-cue-in-window", "got %r" % (got,)
    attempt("a19 state_for: no-cue-in-window fora de qualquer cue", a19)

    def a20():
        track = {"state": "has-track",
                 "cues": [{"start": 10.0, "end": 20.0, "text": "A"}]}
        got = mod.state_for(track, None)
        return got == "time-unknown", "got %r" % (got,)
    attempt("a20 state_for: time-unknown quando o instante nao se sabe "
            "(NAO e 'pausado')", a20)

    def a21():
        track = {"state": "no-track", "cues": []}
        got = mod.state_for(track, 15.0)
        return got == "no-track" and got != "has-track", "got %r" % (got,)
    attempt("a21 state_for: um video SEM legenda da no-track, "
            "e NUNCA has-track", a21)

    def a22():
        ok = tuple(mod.TRACK_STATES) == ("has-track", "no-track",
                                         "no-cue-in-window", "time-unknown")
        return ok, "TRACK_STATES=%r" % (mod.TRACK_STATES,)
    attempt("a22 TRACK_STATES tem os quatro estados do contrato", a22)

    # -- the track choice --------------------------------------------------
    def a23():
        track = mod.track_from_info(FIXTURE_INFO)
        ok = track is not None and track["lang"] == "pt-BR" \
            and track["source"] == "manual" and track["ext"] == "json3"
        return ok, "track=%r" % (track,)
    attempt("a23 track_from_info escolhe a legenda MANUAL de pt", a23)

    def a24():
        track = mod.track_from_info(FIXTURE_INFO, lang_prefs=("en",))
        ok = track is not None and track["lang"] == "en" \
            and track["source"] == "auto" and track["ext"] == "json3"
        return ok, "track=%r" % (track,)
    attempt("a24 track_from_info recusa a entrada 'vtt' que e uma PLAYLIST "
            "HLS e usa o json3", a24)

    def a25():
        empty = {"subtitles": {}, "automatic_captions": {}}
        got = mod.track_from_info(empty)
        return got is None, "got %r" % (got,)
    attempt("a25 track_from_info de um video SEM faixas da None "
            "(nao-track, nao has-track)", a25)

    def a40():
        # A language whose ONLY entry is the HLS playlist is not a caption
        # track at all: the playlist is refused, so this video has no track.
        got = mod.track_from_info(FIXTURE_INFO_PLAYLIST_ONLY,
                                  lang_prefs=("pt-BR",))
        return got is None, "got %r" % (got,)
    attempt("a40 uma faixa 'vtt' que e so uma PLAYLIST HLS nao e uma faixa: "
            "o video fica sem legenda", a40)

    def a26():
        info = {"subtitles": {"de-DE": [{"ext": "json3", "url": "u"}]},
                "automatic_captions": {"en": [{"ext": "json3", "url": "u"}]}}
        track = mod.track_from_info(info, lang_prefs=("pt", "en"))
        ok = track is not None and track["lang"] == "en" \
            and track["source"] == "auto"
        return ok, "track=%r" % (track,)
    attempt("a26 track_from_info prefere a LINGUAGEM a fonte "
            "(en automatico, nao de manual)", a26)

    # -- the whole pipeline, with the network cut --------------------------
    def a27():
        cache = os.path.join(workdir, "cache27")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            calls = _fake_fetch(mod, FIXTURE_INFO, FIXTURE_JSON3)
            track = mod.fetch_track("dQw4w9WgXcQ")
            ok = track["state"] == "has-track" and track["lang"] == "pt-BR" \
                and track["source"] == "manual" and len(track["cues"]) == 2
            return ok, "track=%r calls=%r" % (
                {k: v for k, v in track.items() if k != "cues"}, calls)
        finally:
            mod.CACHE_DIR = old
    attempt("a27 fetch_track monta a faixa real a partir da info do yt-dlp",
            a27)

    def a28():
        cache = os.path.join(workdir, "cache28")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            calls = _fake_fetch(mod, FIXTURE_INFO, FIXTURE_JSON3)
            mod.fetch_track("dQw4w9WgXcQ")
            again = mod.fetch_track("dQw4w9WgXcQ")
            ok = again.get("cached") is True and calls["extract"] == 1 \
                and calls["http"] == 1 and again["state"] == "has-track"
            return ok, "calls=%r cached=%r" % (calls, again.get("cached"))
        finally:
            mod.CACHE_DIR = old
    attempt("a28 fetch_track usa o CACHE: a segunda chamada nao vai a rede",
            a28)

    def a29():
        cache = os.path.join(workdir, "cache29")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            _fake_fetch(mod, {"subtitles": {}, "automatic_captions": {}},
                        FIXTURE_JSON3)
            track = mod.fetch_track("aqz-KE-bpKQ")
            ok = track["state"] == "no-track" and track["cues"] == [] \
                and track["reason"] == "no-tracks-listed" \
                and mod.state_for(track, 12.0) == "no-track" \
                and mod.state_for(track, 12.0) != "has-track"
            return ok, "track=%r" % ({k: v for k, v in track.items()
                                      if k != "cues"},)
        finally:
            mod.CACHE_DIR = old
    attempt("a29 fetch_track de um video SEM legenda da no-track, "
            "e o chamador continua a transcrever ao vivo", a29)

    def a30():
        cache = os.path.join(workdir, "cache30")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            _fake_fetch(mod, FIXTURE_INFO, FIXTURE_JSON3)
            mod.fetch_track("dQw4w9WgXcQ")
            path = os.path.join(cache, "dQw4w9WgXcQ.jsonl")
            exists = os.path.isfile(path)
            ignored = False
            try:
                with open(os.path.join(REPO, ".gitignore"), "r",
                          encoding="utf-8") as fh:
                    ignored = any(line.strip() == "*.jsonl"
                                  for line in fh)
            except Exception:
                ignored = False
            return exists and ignored, "ficheiro=%r .gitignore tem '*.jsonl'=%r" % (
                exists, ignored)
        finally:
            mod.CACHE_DIR = old
    attempt("a30 o cache fica em disco e num ficheiro que o .gitignore "
            "ja ignora (nunca entra num commit)", a30)

    def a45():
        # MEASURED 2026-10-19: the timedtext API answers HTTP 429 for the
        # AUTOMATIC track of a video (every format, every User-Agent, every
        # retry) while the MANUAL track of another serves 200. A refused
        # payload must NOT become a 3 Hz hammer on YouTube, and it must not
        # be read as a verdict about the video.
        cache = os.path.join(workdir, "cache45")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            calls = _fake_fetch(mod, FIXTURE_INFO, None)  # the payload fails
            # ONE HTTP CALL PER CANDIDATE (2026-10-20): a refused payload is
            # a FALLBACK, so every candidate is asked once, and the SECOND
            # poll asks for NOTHING (the cache holds the refusal).
            n_tracks = len(mod.tracks_from_info(FIXTURE_INFO))
            first = mod.fetch_track("dQw4w9WgXcQ")
            second = mod.fetch_track("dQw4w9WgXcQ")
            ok = (first["state"] == "no-track"
                  and first["reason"] == "payload-failed"
                  and second["state"] == "no-track"
                  and calls["extract"] == 1 and calls["http"] == n_tracks
                  and n_tracks > 1)
            return ok, "1o=%r 2o=%r calls=%r" % (
                {k: first.get(k) for k in ("state", "reason")},
                {k: second.get(k) for k in ("state", "reason", "cached")},
                calls)
        finally:
            mod.CACHE_DIR = old
    attempt("a45 um payload REFUSADO (429) da no-track e nao repete a rede "
            "no poll seguinte", a45)

    def a46():
        # After the short back-off, the retry asks for the TRACK again and
        # NOT for the whole video: the 5 s extract is not repeated.
        cache = os.path.join(workdir, "cache46")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            calls = _fake_fetch(mod, FIXTURE_INFO, None)
            mod.fetch_track("dQw4w9WgXcQ")
            # age the cache entry past the short back-off
            path = os.path.join(cache, "dQw4w9WgXcQ.jsonl")
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.loads(fh.read())
            doc["fetched_at"] = time.time() - 3600
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
            calls["http"] = 0
            calls["extract"] = 0
            again = mod.fetch_track("dQw4w9WgXcQ")
            n_tracks = len(mod.tracks_from_info(FIXTURE_INFO))
            ok = (again["state"] == "no-track"
                  and calls["extract"] == 0 and calls["http"] == n_tracks)
            return ok, "state=%r calls=%r" % (again.get("state"), calls)
        finally:
            mod.CACHE_DIR = old
    attempt("a46 passado o back-off, so a FAIXA e pedida de novo -- o extract "
            "de 5 s nao se repete", a46)

    def a47():
        # THE FALLBACK (2026-10-20). MEASURED in the owner's own running app,
        # on the video he was watching (`cUeZMUGCxrw`): the AUTOMATIC track's
        # payload is refused by YouTube (HTTP 429 on the timedtext API) while
        # the MANUAL track of the SAME video answers 200 (MEASURED 2026-10-19
        # by the lane that built the reader).
        #
        # A module that tries ONE track and gives up when the payload is
        # refused reports "this video has no captions" for a video that HAS
        # them -- and the owner watches an empty panel. THIS ARM IS THE GATE
        # OF THAT FIX: it fails on the old behaviour and passes on the new.
        cache = os.path.join(workdir, "cache47")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            calls = {"extract": 0, "http": 0}

            def _extract(_vid, _timeout):
                calls["extract"] += 1
                return FIXTURE_INFO

            def _http(url, _timeout):
                calls["http"] += 1
                # THE FIRST CANDIDATE IS REFUSED. The second one answers.
                if "ptbr.json3" in str(url):
                    return None
                return FIXTURE_JSON3

            mod._extract_info = _extract
            mod._http_get = _http
            got = mod.fetch_track("dQw4w9WgXcQ")
            ok = (got["state"] == "has-track"
                  and got["reason"] == "ok"
                  and got.get("cues")
                  and calls["extract"] == 1
                  and calls["http"] == 2)
            return ok, "state=%r source=%r cues=%d calls=%r" % (
                got.get("state"), got.get("source"),
                len(got.get("cues") or ()), calls)
        finally:
            mod.CACHE_DIR = old
    attempt("a47 o payload recusado e um FALLBACK: a faixa seguinte responde e "
            "o video TEM legenda", a47)

    # -- the player's clock ------------------------------------------------
    def a31():
        uia = _FakeAutomation([_text("06:13 of 24:43", "ytp-time-duration")])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1)
        return got.get("t") == 373.0, "detail=%r" % (got,)
    attempt("a31 player_time le o relogio do player: 'M:SS of M:SS'", a31)

    def a32():
        uia = _FakeAutomation([_slider(50.0, 0.0, 213.0)])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=213)
        return got.get("t") == 50.0, "detail=%r" % (got,)
    attempt("a32 player_time: uma barra em SEGUNDOS da o proprio valor", a32)

    def a33():
        uia = _FakeAutomation([_slider(50.0, 0.0, 100.0)])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=213)
        return got.get("t") == 106.5, "detail=%r" % (got,)
    attempt("a33 player_time: uma barra em PERCENT da valor/duracao", a33)

    def a34():
        uia = _FakeAutomation([_slider(0.25, 0.0, 1.0)])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=213)
        return got.get("t") == 53.25, "detail=%r" % (got,)
    attempt("a34 player_time: uma barra em FRACAO da fracao*duracao", a34)

    def a35():
        # The modern player shows ONLY the total duration. It is NOT the
        # current time, so it must not be used as one.
        uia = _FakeAutomation([_text("24:43", "ytp-time-duration")])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=1483)
        return got.get("t") is None, "detail=%r" % (got,)
    attempt("a35 player_time NAO usa a duracao total como se fosse o instante",
            a35)

    def a36():
        uia = _FakeAutomation([])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=213)
        ok = got.get("t") is None and got.get("source") is None
        return ok, "detail=%r" % (got,)
    attempt("a36 player_time sem relogio legivel devolve None "
            "(e NAO inventa um instante)", a36)

    def a37():
        uia = _FakeAutomation([_slider(9999.0, 0.0, 10000.0)])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=213)
        return got.get("t") is None, "detail=%r" % (got,)
    attempt("a37 player_time rejeita um instante fora do video", a37)

    def a38():
        uia = _FakeAutomation([_slider(50.0, 0.0, 100.0, valuetext="0:50 of 3:33")])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=213)
        return got.get("t") == 50.0, "detail=%r" % (got,)
    attempt("a38 player_time le o aria-valuetext da barra antes de calcular",
            a38)

    def a41():
        # MEASURED on this box's UIAutomationClient: the Slider is 50015.
        # 50013 is the RADIO BUTTON, and a query with the wrong number
        # returns an EMPTY collection instead of raising -- the seek-bar path
        # would have been silently dead.
        radio = _FakeElement(name="Option", cls="radio", control_type=50013,
                             value=50.0, vmin=0.0, vmax=100.0)
        uia = _FakeAutomation([radio])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=213)
        return got.get("t") is None, "detail=%r" % (got,)
    attempt("a41 a barra e procurada como SLIDER (50015), nao como um botao "
            "de radio (50013)", a41)

    def _real_youtube_sliders():
        # MEASURED 2026-10-19 20:1x on the owner's own YouTube window, a
        # 28:33 video (`as11Bbmgl08`):
        #   seek bar  'ytp-progress-bar'  value=407.0 min=0.0 max=1713.0
        #   volume    'ytp-volume-panel'  value=48.0  min=0.0 max=100.0
        seek = _slider(407.0, 0.0, 1713.0,
                       valuetext="Edição de vídeo 6 Minutos 47 Segundos de "
                                 "28 Minutos 33 Segundos",
                       name="Botão deslizante de busca",
                       cls="ytp-progress-bar")
        volume = _slider(48.0, 0.0, 100.0, valuetext="48% volume",
                         name="Volume", cls="ytp-volume-panel")
        return seek, volume

    def a42():
        seek, volume = _real_youtube_sliders()
        uia = _FakeAutomation([seek, volume])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=1713)
        return got.get("t") == 407.0, "detail=%r" % (got,)
    attempt("a42 a barra de BUSCA real do YouTube da o instante em SEGUNDOS "
            "(407.0 de uma barra 0..1713)", a42)

    def a43():
        seek, volume = _real_youtube_sliders()
        uia = _FakeAutomation([volume, seek])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1, duration=1713)
        return got.get("t") == 407.0, "detail=%r" % (got,)
    attempt("a43 o slider de VOLUME (0..100) nunca e lido como um instante, "
            "mesmo que venha antes", a43)

    def a44():
        # Without the duration the seek bar is still told apart by its
        # class and by its maximum; a percent scale is still not an instant.
        seek, volume = _real_youtube_sliders()
        uia = _FakeAutomation([volume, seek])
        got = mod.player_time_detail(uia, _FakeUIAModule, 1)
        return got.get("t") == 407.0, "detail=%r" % (got,)
    attempt("a44 sem a duracao do video a barra de busca ainda da o instante",
            a44)

    # -- the module is cheap to import -------------------------------------
    def a39():
        import ast
        top = []
        for node in ast.parse(source).body:
            if isinstance(node, ast.Import):
                top.extend(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                top.append(node.module.split(".")[0])
        heavy = [m for m in top if m in ("yt_dlp", "requests", "uiautomation",
                                         "comtypes")]
        return heavy == [], "imports de topo=%r" % (top,)
    attempt("a39 o modulo nao importa yt_dlp no topo "
            "(a shell paga so o que precisa)", a39)

    return rows


# ── the mutants ──────────────────────────────────────────────────────────────
# The anchors are EXACT strings of `app/webview/youtube_captions.py`. A
# mutant whose anchor is missing or ambiguous is DECORATIVE -- it proves
# nothing -- so the oracle refuses to count it.

MUTANTS = [
    # THE ONE THE OWNER'S ORDER IS ABOUT: treat "no-track" as "has-track".
    # Then a video with no legend would STOP the live transcription and show
    # nothing at all.
    ("no-track-trated-as-has-track",
     '    if not isinstance(track, dict) or track.get("state") != "has-track":\n'
     '        return "no-track"',
     '    if not isinstance(track, dict):\n'
     '        return "no-track"\n'
     '    if track.get("state") == "no-track":\n'
     '        return "has-track"\n'
     '    if track.get("state") != "has-track":\n'
     '        return "no-track"'),
    # The end of a cue becomes inclusive: a caption stays on screen for one
    # poll too long, and the NEXT caption's first frame is swallowed.
    ("cue-end-becomes-inclusive",
     "        if start <= t < end:",
     "        if start <= t <= end:"),
    # The player's window bookkeeping reaches the caption box: the automatic
    # "word" event is shown as a caption of its own.
    ("the-automatic-word-event-is-kept",
     '        if "wpWinPosId" in ev or ev.get("aAppend"):\n'
     '            continue  # the player\'s window bookkeeping, not a caption',
     '        if False:\n'
     '            continue  # the player\'s window bookkeeping, not a caption'),
    # An empty cue is emitted (a blank line in the caption box).
    ("an-empty-cue-is-emitted",
     "        body = _join_segs(segs)\n        if not body:\n            continue",
     "        body = _join_segs(segs)\n        if not body:\n            body = ''"),
    # The unknown instant is reported as "there is a caption here".
    ("the-unknown-instant-becomes-has-track",
     '    if t is None:\n        return "time-unknown"',
     '    if t is None:\n        return "has-track"'),
    # A video with NO track at all is given one: the live transcription stops
    # and an empty caption box is left on the screen.
    ("a-video-with-no-track-gets-one",
     '    for table, case, source in ((manual, manual_case, "manual"),\n'
     '                                (auto, auto_case, "auto")):\n'
     '        for key in sorted(table):\n'
     '            take(table, case, source, key)\n'
     '    return ordered',
     '    for table, case, source in ((manual, manual_case, "manual"),\n'
     '                                (auto, auto_case, "auto")):\n'
     '        for key in sorted(table):\n'
     '            take(table, case, source, key)\n'
     '    return ordered or [{"lang": "xx", "source": "auto", "ext": "json3",\n'
     '                          "url": "https://example.invalid/fake.json3",\n'
     '                          "name": "fake"}]'),
    # THE FALLBACK IS NOT TRIED: only the first candidate is asked, so a
    # refused payload ends the search and the video reads as "no captions".
    ("the-fallback-is-not-tried",
     '    for track in tracks:\n'
     '        if painted and len(tried) >= _PAINT_SEARCH_MAX:\n',
     '    for track in tracks[:1]:\n'
     '        if painted and len(tried) >= _PAINT_SEARCH_MAX:\n'),
    # The HLS playlist is parsed as WebVTT: the track reads as EMPTY, and an
    # empty track reads as "this video has no legend".
    ("the-hls-playlist-is-accepted-as-vtt",
     '        if str(entry.get("protocol") or "").lower() == "m3u8_native":\n'
     '            continue',
     '        if False:\n'
     '            continue'),
    # Overlapping cues: the OLD caption wins over the one the player is
    # showing now.
    ("cue_at-returns-the-first-overlapping-cue",
     '            if best is None or start > float(best.get("start", -1)):\n'
     '                best = cue',
     '            if best is None:\n'
     '                best = cue'),
    # The line break inside a segment reaches the caption box: the caption
    # shows a hard newline instead of a space.
    ("the-newline-inside-a-segment-is-kept",
     '    out = re.sub(r"\\s+", " ", out).strip()',
     '    out = re.sub(r" +", " ", out).strip()'),
    # The percent scale is read as seconds: the caption is 56 seconds late.
    ("the-percent-scale-is-read-as-seconds",
     "        if abs(span - 100.0) < 1e-6 and d > 100.0:\n"
     "            candidates.append((value - vmin) / 100.0 * d)",
     "        if False:\n"
     "            candidates.append((value - vmin) / 100.0 * d)"),
]


def main() -> int:
    neg_only = "--neg-arm" in sys.argv[1:]
    live = "--live" in sys.argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                           # noqa: BLE001
        pass
    if not os.path.isfile(MODULE_PATH):
        print("RED   module missing: %s" % MODULE_PATH)
        return EXIT_FAIL
    with open(MODULE_PATH, "r", encoding="utf-8", newline="") as fh:
        source = fh.read()

    arms_total = arms_green = 0
    if not neg_only:
        print("ARMS (pure: no network, no browser, no app)")
        workdir = tempfile.mkdtemp(prefix="yt-caps-oracle-")
        try:
            mod = load_module(MODULE_PATH, "youtube_captions_live")
            rows = battery(mod, MODULE_PATH, workdir, source)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        for ok, name, detail in rows:
            print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                                 ("  " + detail) if detail else ""))
        arms_green = sum(1 for ok, _, _ in rows if ok)
        arms_total = len(rows)
        print("\n  %d/%d" % (arms_green, arms_total))

    print("\nNEGATIVE ARM (broken copies must go RED)")
    caught = 0
    weak = 0
    workdir = tempfile.mkdtemp(prefix="yt-caps-oracle-mut-")
    try:
        for idx, (label, old, new) in enumerate(MUTANTS):
            hits = source.count(old)
            if hits != 1:
                print("  RED   mutant %-46s ANCHOR %s -- oracle is stale"
                      % (label, "MISSING" if hits == 0 else "AMBIGUOUS"))
                weak += 1
                continue
            path = os.path.join(workdir, "mutant_%d.py" % idx)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(source.replace(old, new, 1))
            try:
                bad = load_module(path, "youtube_captions_mut_%d" % idx)
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-46s DECORATIVO: nao carregou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            sub = tempfile.mkdtemp(prefix="yt-caps-oracle-mut-run-")
            try:
                res = battery(bad, path, sub, source.replace(old, new, 1))
            except Exception as exc:                            # noqa: BLE001
                print("  RED   mutant %-46s a bateria rebentou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            finally:
                shutil.rmtree(sub, ignore_errors=True)
            reds = [name for ok, name, _ in res if not ok]
            if reds:
                print("  GREEN mutant %-46s caught by: %s"
                      % (label, "; ".join(reds[:3])))
                caught += 1
            else:
                print("  RED   mutant %-46s SURVIVED -- the gate is blind here"
                      % label)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    total = len(MUTANTS)

    live_ok = True
    if live:
        print("\nLIVE ARM (the network: yt-dlp against two public videos)")
        live_ok = _live_arm()

    if neg_only:
        print("\nVERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por desenho: o braco "
              "negativo REPROVA de proposito)" % ("PASS" if caught == total else "FAIL",
                                                  caught, total))
        return EXIT_FAIL

    ok = (arms_green == arms_total and caught == total and weak == 0
          and live_ok)
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d%s"
          % ("PASS" if ok else "FAIL", arms_green, arms_total, caught, total,
             "  live %s" % ("ok" if live_ok else "FAILED") if live else ""))
    if weak:
        print("  %d mutante(s) DECORATIVO(S): nao carregaram, logo nao provaram "
              "nada." % weak)
    return EXIT_PASS if ok else EXIT_FAIL


def _live_arm():
    """The real network path. Optional: the gate stays green without it."""
    rows = []

    def attempt(name, fn):
        try:
            ok, detail = fn()
        except Exception as exc:                                # noqa: BLE001
            ok, detail = False, "EXCEPTION %s: %s" % (type(exc).__name__, exc)
        rows.append((ok, name, detail))

    mod = load_module(MODULE_PATH, "youtube_captions_live_net")
    cache = tempfile.mkdtemp(prefix="yt-caps-oracle-live-")
    old_cache = mod.CACHE_DIR
    mod.CACHE_DIR = cache
    try:
        def l01():
            t0 = time.monotonic()
            track = mod.fetch_track(LIVE_HAS_TRACK_VIDEO)
            took = time.monotonic() - t0
            cues = track.get("cues") or []
            times_ok = all(cues[i]["start"] < cues[i + 1]["start"]
                           for i in range(len(cues) - 1))
            texts_ok = all((c.get("text") or "").strip() for c in cues)
            ok = (track.get("state") == "has-track" and len(cues) == LIVE_MANUAL_CUES
                  and times_ok and texts_ok)
            return ok, ("lang=%r source=%r cues=%d primeiro=%r ultimo=%r "
                        "crescente=%r textos=%r %.1fs"
                        % (track.get("lang"), track.get("source"), len(cues),
                           cues[0]["text"] if cues else None,
                           cues[-1]["text"] if cues else None,
                           times_ok, texts_ok, took))
        attempt("l01 a faixa REAL de %s tem cues com tempos crescentes e "
                "texto nao vazio" % LIVE_HAS_TRACK_VIDEO, l01)

        def l02():
            track = mod.fetch_track(LIVE_NO_TRACK_VIDEO)
            ok = (track.get("state") == "no-track" and not track.get("cues")
                  and mod.state_for(track, 12.0) == "no-track"
                  and mod.state_for(track, 12.0) != "has-track")
            return ok, "state=%r reason=%r cues=%d" % (
                track.get("state"), track.get("reason"),
                len(track.get("cues") or ()))
        attempt("l02 o video SEM legenda (%s) da no-track de verdade"
                % LIVE_NO_TRACK_VIDEO, l02)

        def l03():
            t0 = time.monotonic()
            track = mod.fetch_track(LIVE_HAS_TRACK_VIDEO)
            took = time.monotonic() - t0
            ok = track.get("cached") is True and took < 2.0
            return ok, "cached=%r em %.2fs" % (track.get("cached"), took)
        attempt("l03 a segunda leitura vem do CACHE (sem rede)", l03)
    finally:
        mod.CACHE_DIR = old_cache
        shutil.rmtree(cache, ignore_errors=True)
    for ok, name, detail in rows:
        print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                             ("  " + detail) if detail else ""))
    return all(ok for ok, _, _ in rows)


if __name__ == "__main__":
    sys.exit(main())
