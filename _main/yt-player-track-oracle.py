"""ORACLE for the 1:1 RULE -- the track the PLAYER paints is the track the app
serves.

Owner, 2026-10-20, verbatim: *"eu quero a legenda 1:1 do video do youtube. eu
mesmo vou comparar a nossa legenda em tempo real com a do youtube. lembra que
é pra tu simplesmente pegar a do youtube mesmo e usar pelo app. o app só nao
faz isso se nao tem a legenda disponivel."*

WHAT THIS PINS
--------------
The rule has two halves, and both are measured:

  1. THE PLAYER'S OWN ANSWER. The real page (headless Edge, muted playback,
     the video the owner watches -- `cUeZMUGCxrw`) paints its caption in
        <div class="caption-window ytp-caption-window-bottom
             ytp-caption-window-rollup" id="caption-window-1" dir="ltr"
             tabindex="0" lang="pt" ...>
     and the player painted PORTUGUESE. So the `lang` attribute is the
     player's own statement of the track it is showing.

  2. THE KEY THAT IS THAT TRACK. MEASURED, the player's request for the
     track `a.pt` and the yt-dlp keys of the SAME video:
        the PLAYER   ->  ?v=..&caps=asr&kind=asr&lang=pt
        yt-dlp      ->  `pt-orig` : ?v=..&caps=asr&kind=asr&lang=pt
        yt-dlp      ->  `pt`      : ?v=..&caps=asr&kind=asr&lang=ar&tlang=pt
     So the track the player paints is the `-orig` key -- the one whose
     request carries NO `tlang`. The plain `pt` key is a DIFFERENT request
     (the original translated on the fly), which yt-dlp itself calls
     "damaged subtitles" and which YouTube REFUSES: MEASURED HTTP 429 on
     every format, while `pt-orig` answers 200 with 679 cues.
     **The mapping `a.pt` -> `pt` is therefore WRONG, and this gate pins
     the measured one.**

ARMS (pure: fixtures, no network, no browser, no app)
    The player's signal wins over the language preference; the fallback
    keeps the order AND says it does not know; a refused payload is a
    FALLBACK and never a verdict; the served track's REQUEST is the
    player's request; the log says what was known.

NEGATIVE ARM (executed, not decorative)
    Four mutants of the module, each a TEXTUAL patch of a unique anchor. A
    mutant whose anchor is missing or ambiguous is DECORATIVE -- it proves
    nothing -- so the oracle refuses to count it.

Usage:
    python _main/yt-player-track-oracle.py            # arms + mutants, rc=0 on PASS
    python _main/yt-player-track-oracle.py --neg-arm  # mutants only, rc=1 BY DESIGN
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import types
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODULE_PATH = os.path.join(REPO, "app", "webview", "youtube_captions.py")

EXIT_PASS = 0
EXIT_FAIL = 1


# ── the fixtures ─────────────────────────────────────────────────────────────
#: The MEASURED shape of the owner's video (`cUeZMUGCxrw`, 2026-10-20): 21
#: automatic tracks, all `kind=asr`, and the yt-dlp keys below with the
#: query that MEASURED the difference between the player's request and the
#: `tlang` one.
FIXTURE_INFO = {
    "id": "cUeZMUGCxrw",
    "duration": 1315,
    "subtitles": {},
    "automatic_captions": {
        "pt": [
            {"ext": "json3", "name": "Portuguese",
             "url": "https://example.invalid/timedtext?v=cUeZMUGCxrw&caps=asr"
                    "&kind=asr&lang=ar&tlang=pt"},
        ],
        "pt-orig": [
            {"ext": "json3", "name": "Portuguese (Original)",
             "url": "https://example.invalid/timedtext?v=cUeZMUGCxrw&caps=asr"
                    "&kind=asr&lang=pt"},
        ],
        "pt-PT": [
            {"ext": "json3", "name": "Portuguese (Portugal)",
             "url": "https://example.invalid/timedtext?v=cUeZMUGCxrw&caps=asr"
                    "&kind=asr&lang=pt-pt"},
        ],
        "en": [
            {"ext": "json3", "name": "English",
             "url": "https://example.invalid/timedtext?v=cUeZMUGCxrw&caps=asr"
                    "&kind=asr&lang=ar&tlang=en"},
        ],
        "en-orig": [
            {"ext": "json3", "name": "English (Original)",
             "url": "https://example.invalid/timedtext?v=cUeZMUGCxrw&caps=asr"
                    "&kind=asr&lang=en"},
        ],
    },
}

#: A real json3, trimmed: two cues of Portuguese (the `pt-orig` payload) and
#: two of English (the `en-orig` payload).
FIXTURE_PT = json.dumps({
    "wireMagic": "pb3",
    "events": [
        {"tStartMs": 140, "dDurationMs": 1748,
         "segs": [{"utf8": "Pessoal , temos um novo gerador de"}]},
        {"tStartMs": 1888, "dDurationMs": 2000,
         "segs": [{"utf8": "imagens de código aberto , e este é ,"}]},
    ],
}, ensure_ascii=False)

FIXTURE_EN = json.dumps({
    "wireMagic": "pb3",
    "events": [
        {"tStartMs": 320, "dDurationMs": 2480,
         "segs": [{"utf8": "Folks, we have a new open-source image"}]},
        {"tStartMs": 2800, "dDurationMs": 2000,
         "segs": [{"utf8": "generator, and this is by far the best"}]},
    ],
}, ensure_ascii=False)


# ── the fakes ────────────────────────────────────────────────────────────────

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
                                 or getattr(e, "CurrentControlType", None) == wanted])


class _FakeAutomation(object):
    def __init__(self, elements):
        self._root = _FakeRoot(elements)

    def CreatePropertyCondition(self, prop, value):
        return (prop, value)

    def CreateTrueCondition(self):
        return ("true", None)

    def ElementFromHandle(self, _hwnd):
        return self._root


class _FakeUIAModule(object):
    UIA_ControlTypePropertyId = 30003
    TreeScope_Descendants = 4
    UIA_SliderControlTypeId = 50015
    UIA_TextControlTypeId = 50020


class _FakeElement(object):
    """One element of the fake accessibility tree."""

    def __init__(self, name="", cls="", control_type=50020, lang=None):
        self.CurrentName = name
        self.CurrentClassName = cls
        self.CurrentControlType = control_type
        self._lang = lang

    def GetCurrentPropertyValue(self, prop_id):
        # 30007 is UIA's language property; anything else is not set.
        if prop_id == 30007 and self._lang is not None:
            return self._lang
        return None


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_fetch(mod, info, payload_for):
    """`fetch_track` runs the WHOLE pipeline without the network.

    `payload_for(url)` returns the body for that request, or None to REFUSE
    it (which is what YouTube does with HTTP 429).
    """
    calls = {"extract": 0, "http": 0, "urls": []}

    def _extract(_vid, _timeout):
        calls["extract"] += 1
        return info

    def _http(url, _timeout):
        calls["http"] += 1
        calls["urls"].append(url)
        return payload_for(url)

    mod._extract_info = _extract
    mod._http_get = _http
    return calls


def _query(url):
    """The significant query parameters of a timedtext request."""
    out = {}
    for part in re.split(r"[?&]", str(url or ""))[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key in ("lang", "kind", "tlang", "caps", "v"):
            out[key] = value
    return out


# ── the battery ──────────────────────────────────────────────────────────────

def battery(mod, path, workdir, source):
    """The arms. Every one of them is pure: no network, no browser, no app."""
    rows = []

    def attempt(name, fn):
        try:
            ok, detail = fn()
        except Exception as exc:                            # noqa: BLE001
            ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
        rows.append((bool(ok), name, detail))

    # -- 1. the player's signal wins over the language preference ----------
    def a01():
        ordered = mod.tracks_from_info(FIXTURE_INFO, ("pt", "en"),
                                        player_lang="en")
        got = [str(t.get("lang")).lower() for t in ordered]
        ok = got and got[0] == "en-orig"
        return ok, "ordem=%r" % (got[:4],)
    attempt("a01 o sinal do PLAYER manda: com o player em 'en' a primeira "
            "faixa e 'en-orig' (nao a preferencia 'pt')", a01)

    # -- 2. the player's track is the `-orig` key, NOT the `tlang` key ------
    def a02():
        ordered = mod.tracks_from_info(FIXTURE_INFO, ("pt", "en"),
                                        player_lang="pt")
        first = ordered[0]
        q = _query(first.get("url"))
        ok = (str(first.get("lang")).lower() == "pt-orig"
              and q.get("lang") == "pt" and "tlang" not in q)
        return ok, "faixa=%r pedido=%r" % (first.get("lang"), q)
    attempt("a02 a faixa do player e a chave '-orig': o pedido dela e "
            "lang=pt SEM tlang (o pedido do player)", a02)

    # -- 3. the served REQUEST is the player's request ----------------------
    def a03():
        # The request the PLAYER makes for the track it paints, MEASURED on
        # the real page: ?v=..&caps=asr&kind=asr&lang=pt
        player_request = {"v": "cUeZMUGCxrw", "caps": "asr", "kind": "asr",
                          "lang": "pt"}
        cache = os.path.join(workdir, "cache03")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            calls = _fake_fetch(mod, FIXTURE_INFO,
                                lambda u: FIXTURE_PT if "lang=pt" in u
                                and "tlang" not in u else None)
            got = mod.fetch_track("cUeZMUGCxrw", player_lang="pt")
            served = _query((got.get("track") or {}).get("url"))
            ok = (got.get("state") == "has-track"
                  and str(got.get("lang")).lower() == "pt-orig"
                  and served == player_request)
            return ok, "servida=%r pedido=%r player=%r" % (
                got.get("lang"), served, player_request)
        finally:
            mod.CACHE_DIR = old
    attempt("a03 o pedido que a APP faz e o MESMO pedido que o PLAYER faz "
            "(1:1 ao nivel do pedido)", a03)

    # -- 4. without a signal the order is the fallback AND it says so ------
    def a04():
        cache = os.path.join(workdir, "cache04")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            calls = _fake_fetch(mod, FIXTURE_INFO,
                                lambda u: FIXTURE_PT if "lang=pt" in u
                                and "tlang" not in u else None)
            got = mod.fetch_track("cUeZMUGCxrw", player_lang="")
            ok = (got.get("player_known") is False
                  and bool(got.get("player_why"))
                  and str(got.get("lang")).lower() == "pt-orig")
            return ok, "lang=%r known=%r why=%r" % (
                got.get("lang"), got.get("player_known"), got.get("player_why"))
        finally:
            mod.CACHE_DIR = old
    attempt("a04 SEM sinal do player: a preferencia manda E o resultado diz "
            "que nao sabe (player_known=0 + motivo)", a04)

    # -- 5. the log says what was known -------------------------------------
    def a05():
        # The line is the APP's log. The gate puts a stand-in shell in
        # sys.modules (the module only writes the line when the shell is
        # the one running) and reads what was written.
        cache = os.path.join(workdir, "cache05")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        stub = types.ModuleType("sotto_webview")
        had = "sotto_webview" in sys.modules
        sys.modules["sotto_webview"] = stub
        try:
            _fake_fetch(mod, FIXTURE_INFO,
                        lambda u: FIXTURE_PT if "lang=pt" in u
                        and "tlang" not in u else None)
            # The line is written when the ANSWER CHANGES, so the state the
            # previous arm left behind is cleared first.
            try:
                mod._LAST_PLAYER_TRACK[0] = ""
            except Exception:                                  # noqa: BLE001
                pass
            buf = io.StringIO()
            with redirect_stdout(buf):
                mod.fetch_track("cUeZMUGCxrw", player_lang="")
            text = buf.getvalue()
            ok = ("YOUTUBE_PLAYER_TRACK" in text and "known=0" in text
                  and "served=pt-orig" in text)
            return ok, "log=%r" % (text.strip()[:200],)
        finally:
            if had:
                sys.modules["sotto_webview"] = sys.modules["sotto_webview"]
            else:
                sys.modules.pop("sotto_webview", None)
            mod.CACHE_DIR = old
    attempt("a05 o LOG diz o que se sabe: known=0 e a faixa servida", a05)

    # -- 6. a refused payload is a FALLBACK, never a verdict ----------------
    def a06():
        cache = os.path.join(workdir, "cache06")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            # The player's own track (`pt-orig`) is REFUSED (HTTP 429) and
            # the next one answers: the video HAS captions.
            _fake_fetch(mod, FIXTURE_INFO,
                        lambda u: None if "lang=pt" in u and "tlang" not in u
                        else (FIXTURE_EN if "lang=en" in u else None))
            got = mod.fetch_track("cUeZMUGCxrw", player_lang="pt")
            ok = (got.get("state") == "has-track"
                  and str(got.get("lang")).lower() == "en-orig"
                  and got.get("player_lang") == "pt"
                  and got.get("player_match") is False)
            return ok, "lang=%r known=%r match=%r" % (
                got.get("lang"), got.get("player_known"),
                got.get("player_match"))
        finally:
            mod.CACHE_DIR = old
    attempt("a06 o payload RECUSADO (429) da faixa do player e um FALLBACK: "
            "a seguinte responde e o video TEM legenda", a06)

    # -- 7. the refusal is not a verdict about the video --------------------
    def a07():
        cache = os.path.join(workdir, "cache07")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            _fake_fetch(mod, FIXTURE_INFO, lambda u: None)
            got = mod.fetch_track("cUeZMUGCxrw", player_lang="pt")
            ok = (got.get("state") == "no-track"
                  and got.get("reason") == "payload-failed")
            return ok, "state=%r reason=%r" % (got.get("state"),
                                                got.get("reason"))
        finally:
            mod.CACHE_DIR = old
    attempt("a07 tudo recusado: 'payload-failed' (o ASR continua), nunca "
            "'no-tracks-listed'", a07)

    # -- 8. the player switching the track invalidates the cache -----------
    def a08():
        cache = os.path.join(workdir, "cache08")
        old = mod.CACHE_DIR
        mod.CACHE_DIR = cache
        try:
            _fake_fetch(mod, FIXTURE_INFO,
                        lambda u: FIXTURE_PT if "lang=pt" in u
                        and "tlang" not in u else
                        (FIXTURE_EN if "lang=en" in u else None))
            first = mod.fetch_track("cUeZMUGCxrw", player_lang="pt")
            second = mod.fetch_track("cUeZMUGCxrw", player_lang="en")
            ok = (str(first.get("lang")).lower() == "pt-orig"
                  and str(second.get("lang")).lower() == "en-orig")
            return ok, "1o=%r 2o=%r" % (first.get("lang"), second.get("lang"))
        finally:
            mod.CACHE_DIR = old
    attempt("a08 o PLAYER muda de faixa: o cache da faixa antiga NAO e "
            "servido (a linha seria a errada)", a08)

    # -- 9. the signal is read from the player's own caption window --------
    def a09():
        # MEASURED 2026-10-20: the player's caption window carries the
        # language it is painting (`lang="pt"`).
        element = _FakeElement(
            name="Pessoal , temos um novo gerador de",
            cls="caption-window ytp-caption-window-bottom "
                "ytp-caption-window-rollup",
            lang=1046)  # pt-BR in Windows' language ids
        container = _FakeElement(name="", cls="ytp-caption-window-container")
        uia = _FakeAutomation([container, element])
        el, code, source = mod.player_caption_window(uia, _FakeUIAModule,
                                                      uia._root)
        ok = (code == "pt" and el is element and source.startswith("uia-"))
        return ok, "code=%r source=%r" % (code, source)
    attempt("a09 o sinal vem da JANELA DE LEGENDA do player (a `lang` que o "
            "proprio player escreveu)", a09)

    # -- 10. a player that says nothing says nothing -----------------------
    def a10():
        element = _FakeElement(name="texto", cls="caption-window")
        uia = _FakeAutomation([element])
        el, code, source = mod.player_caption_window(uia, _FakeUIAModule,
                                                      uia._root)
        ok = code == "" and source == ""
        return ok, "code=%r" % (code,)
    attempt("a10 um player que nao diz a lingua NAO e um player que nao tem "
            "legenda: o codigo vem vazio", a10)

    return rows


# ── the mutants ──────────────────────────────────────────────────────────────
# The anchors are EXACT strings of `app/webview/youtube_captions.py`. A
# mutant whose anchor is missing or ambiguous is DECORATIVE -- it proves
# nothing -- so the oracle refuses to count it.

MUTANTS = [
    # THE PLAYER'S SIGNAL IS IGNORED: the language preference decides again,
    # and the line the owner compares is the wrong one from the first frame.
    ("the-player-signal-is-ignored",
     "    tracks = tracks_from_info(info, lang_prefs, plang)",
     "    tracks = tracks_from_info(info, lang_prefs)"),
    # THE PLAYER'S TRACK IS MAPPED TO THE `tlang` KEY. This is THE bug the
    # owner is comparing against the screen: `a.pt` is served as `pt`, whose
    # request carries `&tlang=pt` -- a DIFFERENT request from the player's,
    # the one YouTube refuses with HTTP 429.
    ("the-players-track-is-mapped-to-the-tlang-key",
     "    if orig in table:\n        keys.append(orig)\n"
     "    if pref in table:\n        keys.append(pref)",
     "    if pref in table:\n        keys.append(pref)\n"
     "    if orig in table:\n        keys.append(orig)"),
    # THE SWITCH IS NOT LOGGED: the app changes the track (or keeps the wrong
    # one) and the log never says what it knew.
    ("the-switch-is-not-logged",
     '        _log_player_track(psig_used, result["lang"], result["source"])',
     '        pass'),
    # A REFUSED PAYLOAD IS READ AS "THIS VIDEO HAS NO CAPTIONS": the
    # refusal stops being a fallback and becomes a verdict.
    ("a-refused-payload-is-a-verdict",
     '    result["reason"] = "payload-failed" if last_err else "empty-track"',
     '    result["reason"] = "no-tracks-listed"'),
]


def main() -> int:
    neg_only = "--neg-arm" in sys.argv[1:]
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
        print("ARMS (pure: fixtures, no network, no browser, no app)")
        workdir = tempfile.mkdtemp(prefix="yt-player-track-oracle-")
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
    workdir = tempfile.mkdtemp(prefix="yt-player-track-oracle-mut-")
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
            sub = tempfile.mkdtemp(prefix="yt-player-track-oracle-mut-run-")
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
    if neg_only:
        print("\nVERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por desenho: o braco "
              "negativo tem de falhar)" % ("PASS" if caught == total else "FAIL",
                                           caught, total))
        return EXIT_FAIL if caught == total else EXIT_PASS
    ok = arms_green == arms_total and caught == total and weak == 0
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", arms_green, arms_total, caught, total))
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
