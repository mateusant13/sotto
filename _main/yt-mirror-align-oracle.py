"""ORACLE for the MIRRORED PATH -- the line the player PAINTS is the line the
app serves, and the track is found BY THE TEXT THE PLAYER PAINTS.

Owner, 2026-10-20, verbatim: *"eu quero a legenda 1:1 do video do youtube. eu
mesmo vou comparar a nossa legenda em tempo real com a do youtube. lembra que
é pra tu simplesmente pegar a do youtube mesmo e usar pelo app."*

WHAT THIS PINS
--------------
The old path read the player's CLOCK. MEASURED 2026-10-20 on the owner's own
Chrome, with the player PLAYING (video `h5zkzon0gM4`):

  * the seek bar's RangeValue AND the player's own clock text
    (`ytp-time-contents`) are **FROZEN**: **+0.00 s in 8.35 s** of wall
    clock, while the painted line advanced **+8.96 s** in the track. The
    clock the app read said t=2.0 when the video was at t=530 -- eight
    minutes of wrong;
  * the caption window exposes **NO language**: **0 of 448 elements** carry
    the UIA language property (30007), so the app served the track by
    LANGUAGE PREFERENCE (`pt-orig`) while the player was painting `en-orig`.
    The owner was comparing Portuguese against English.

=> THE PAINT IS THE SOURCE. The caption window exposes **one word per UIA
child**, and the words CHANGE while the video plays. So the app reads the
words the player is painting, and finds the track **BY THE TEXT IT PAINTS**.

The alignment has to survive three shapes of paint, all measured:

  1. THE ROLLUP IS CUT AT THE FRONT: the first painted word is often in the
     MIDDLE of a cue -- the rollup drops the oldest line;
  2. the LAST painted word may be a PREFIX of the track's word, because the
     player types a cue word by word: MEASURED '...click anywhere on t'
     against '...anywhere on the', and '...connect the output ba' against
     '...the output back' -- even a ONE LETTER prefix ('t' for 'the');
  3. anything else is a mismatch. The WRONG track (the Portuguese one on the
     SAME video) aligns with **ZERO** words -- that is exactly what
     identifies the track -- and fewer than `_ALIGN_MIN_EXACT` (= 3) exact
     words do not align.

THE FIXTURES ARE MEASURED, NOT INVENTED
---------------------------------------
`EN_CUES` / `PT_CUES` are the two tracks of the SAME video (`h5zkzon0gM4`) at
the SAME instants: the English one the player was painting and the Portuguese
one the app was serving by preference. `PAINTED` is the 12 words read from
the player's caption-window on that video: the first 6 are the TAIL of cue 2
and the next 6 the BEGINNING of cue 3 -- the rollup cuts the front.

MEASURED HERE (this oracle, 2026-10-20, the real module):

    align_painted(EN_CUES, PAINTED)  -> index=3 exact=12 aligned=12
                                        partial=False
    align_painted(PT_CUES, PAINTED)  -> None
    align_painted(EN_CUES, CUT)      -> index=3 exact=8  aligned=8
                                        (the paint starts MID-CUE)
    align_painted(EN_CUES, ["click","anywhere","on","t"])
                                     -> index=0 exact=3  aligned=4
                                        partial=True

**`exact` is 12, not 11.** The cue's text is `'combining it with a Minecraft
world. So,'` and the cue's WORDS are split on whitespace, so 'Minecraft' IS a
whole word of the cue: the painted 'Minecraft' matches it EXACTLY, and
`partial` stays False. The number 11 would be right only if the cue's word
were 'Minecraft world.' as one word -- it is not. The gate pins the number
this run MEASURED (12), because a gate that pins a number nobody ran is a
gate that lies.

ARMS (pure: fixtures, no network, no browser, no app, no audio)
    the real paint lands on the right cue of the right track; the SAME paint
    lands on NOTHING in the wrong track (the paint identifies the track); a
    paint cut in the middle of a cue still aligns; a paint caught MID-WORD
    aligns and says `partial`; invented words do not align; one or two words
    do not align (below the minimum); `painted_words` picks the caption window
    with the MOST words and says why when there is none; `fetch_track`
    serves the track that CONTAINS the paint, and the CACHE never serves a
    track that does not contain it.

NEGATIVE ARM (executed, not decorative)
    Five mutants of `app/webview/youtube_captions.py`, each a TEXTUAL patch
    of a UNIQUE anchor. A mutant whose anchor is missing or ambiguous is
    DECORATIVE -- it proves nothing -- so the oracle refuses to count it, and
    a mutant that loads but changes nothing is reported as SURVIVED (the
    gate is blind there).

Usage:
    python _main/yt-mirror-align-oracle.py            # arms + mutants, rc=0 on PASS
    python _main/yt-mirror-align-oracle.py --neg-arm  # mutants only, rc=1 BY DESIGN
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODULE_PATH = os.path.join(REPO, "app", "webview", "youtube_captions.py")

EXIT_PASS = 0
EXIT_FAIL = 1


# ── the fixtures ─────────────────────────────────────────────────────────────
#: The video the owner's Chrome was playing when the paint was measured.
VIDEO_ID = "h5zkzon0gM4"

#: MEASURED 2026-10-20: 7 consecutive cues of the `en-orig` track of
#: `h5zkzon0gM4` -- the track the player was PAINTING.
EN_CUES = [
    {"start": 479.92, "end": 483.92, "text": "cool example of this would be like"},
    {"start": 481.60, "end": 485.64, "text": "rebuilding Call of Duty: Modern Warfare"},
    {"start": 483.92, "end": 488.64, "text": "in the new Rust engine and then"},
    {"start": 485.64, "end": 491.08, "text": "combining it with a Minecraft world. So,"},
    {"start": 488.64, "end": 493.16, "text": "you can shoot mobs, destroy blocks with"},
    {"start": 491.08, "end": 494.52, "text": "guns, and blow them up with grenades,"},
    {"start": 493.16, "end": 496.44, "text": "which is pretty crazy. Now, if you're"},
]

#: MEASURED 2026-10-20: the SAME instants in the `pt-orig` track of the SAME
#: video -- the track the app served by LANGUAGE PREFERENCE, and the track the
#: player was NOT painting.
PT_CUES = [
    {"start": 438.579, "end": 441.124, "text": "reutilizáveis que encadeiam várias"},
    {"start": 440.167, "end": 443.087, "text": "ferramentas de IA . Então , depois de"},
    {"start": 442.129, "end": 444.710, "text": "encontrar um processo que você gosta ,"},
    {"start": 443.752, "end": 446.125, "text": "você pode automatizá - lo e gerar"},
    {"start": 445.167, "end": 447.499, "text": "conteúdo consistente em escala ."},
    {"start": 446.939, "end": 449.202, "text": "Portanto , esteja você criando"},
    {"start": 448.244, "end": 450.887, "text": "anúncios , conteúdo para redes sociais"},
]

#: MEASURED 2026-10-20: the 12 words the player's caption-window was painting.
#: The first 6 are the TAIL of cue 2 and the next 6 the BEGINNING of cue 3 --
#: the rollup cuts the FRONT of the oldest line.
PAINTED = ["in", "the", "new", "Rust", "engine", "and",
           "then", "combining", "it", "with", "a", "Minecraft"]

#: The same paint, cut in the MIDDLE of cue 2 (it starts at its 4th word) --
#: the alignment has to accept a paint that starts inside a cue.
PAINT_CUT = ["Rust", "engine", "and", "then", "combining", "it", "with", "a"]

#: MEASURED 2026-10-20: the player caught mid-word ('t' for 'the').
PAINT_PARTIAL = ["click", "anywhere", "on", "t"]
CUE_PARTIAL = [{"start": 0.0, "end": 2.0, "text": "click anywhere on the interface"}]

#: Words that are in NO cue of either track.
PAINT_INVENTED = ["quux", "zibble", "frobnicate", "mumble"]

#: The yt-dlp info dict of the SAME video, with the three automatic tracks
#: that were measured: the original Portuguese (`pt-orig`), the translated
#: one (`pt` -- the request YouTube REFUSES with HTTP 429) and the original
#: English (`en-orig` -- the one the player paints).
FIXTURE_INFO = {
    "id": VIDEO_ID,
    "duration": 900,
    "subtitles": {},
    "automatic_captions": {
        "pt-orig": [
            {"ext": "json3", "name": "Portuguese (Original)",
             "url": "https://example.invalid/timedtext?v=%s&caps=asr&kind=asr&lang=pt"
                    % VIDEO_ID},
        ],
        "pt": [
            {"ext": "json3", "name": "Portuguese",
             "url": "https://example.invalid/timedtext?v=%s&caps=asr&kind=asr&lang=ar&tlang=pt"
                    % VIDEO_ID},
        ],
        "en-orig": [
            {"ext": "json3", "name": "English (Original)",
             "url": "https://example.invalid/timedtext?v=%s&caps=asr&kind=asr&lang=en"
                    % VIDEO_ID},
        ],
    },
}


def _json3(cues):
    """The cues -> the json3 document the timedtext API would answer."""
    events = []
    for cue in cues:
        start = float(cue["start"])
        events.append({
            "tStartMs": int(round(start * 1000)),
            "dDurationMs": int(round((float(cue["end"]) - start) * 1000)),
            "segs": [{"utf8": cue["text"]}],
        })
    return json.dumps({"wireMagic": "pb3", "events": events}, ensure_ascii=False)


FIXTURE_EN = _json3(EN_CUES)
FIXTURE_PT = _json3(PT_CUES)


# ── the fakes ────────────────────────────────────────────────────────────────

class _FakeCollection(object):
    def __init__(self, elements):
        self._elements = list(elements)
        self.Length = len(self._elements)

    def GetElement(self, i):
        return self._elements[i]


class _FakeElement(object):
    """One element of the fake accessibility tree (the caption window, or one
    of its word children)."""

    def __init__(self, name="", cls="", children=()):
        self.CurrentName = name
        self.CurrentClassName = cls
        self._children = list(children)

    def FindAll(self, _scope, _cond):
        # The scope is ignored: a window's children ARE its words.
        return _FakeCollection(self._children)


class _FakeRoot(object):
    """The root of the fake tree: its descendants are the top-level nodes."""

    def __init__(self, elements):
        self._elements = list(elements)

    def FindAll(self, _scope, _cond):
        return _FakeCollection(self._elements)


class _FakeAutomation(object):
    def __init__(self, elements):
        self._root = _FakeRoot(elements)

    def CreateTrueCondition(self):
        return ("true", None)

    def ElementFromHandle(self, _hwnd):
        return self._root


class _FakeUIAModule(object):
    """`painted_words` does not read the typelib; it is passed anyway."""

    UIA_ControlTypePropertyId = 30003
    TreeScope_Descendants = 4


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_net(mod):
    """`fetch_track` runs the WHOLE pipeline without the network.

    The info dict is the fixture one; the payloads are the two json3
    documents. The TRANSLATED key (`tlang=`) is REFUSED, exactly as YouTube
    refused it with HTTP 429 on 2026-10-19/20.
    """
    calls = {"extract": 0, "http": []}

    def _extract(_vid, _timeout):
        calls["extract"] += 1
        return FIXTURE_INFO

    def _http(url, _timeout):
        calls["http"].append(url)
        if "tlang=" in url:
            return None                      # HTTP 429, MEASURED
        if "lang=en" in url:
            return FIXTURE_EN
        if "lang=pt" in url:
            return FIXTURE_PT
        return None

    mod._extract_info = _extract
    mod._http_get = _http
    return calls


def _with_cache(mod, workdir, name, fn):
    """`fn` with the module's cache redirected OUT of the repository.

    The cache is a directory of `.jsonl` files under the product root; a gate
    that wrote there would be writing runtime output into the repo.
    """
    old = mod.CACHE_DIR
    mod.CACHE_DIR = os.path.join(workdir, name)
    try:
        return fn()
    finally:
        mod.CACHE_DIR = old


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

    # -- 1. the real paint lands on the right cue of the right track -------
    def a01():
        hit = mod.align_painted(EN_CUES, PAINTED)
        if hit is None:
            return False, "align_painted devolveu None"
        ok = (hit.get("index") == 3
              and hit.get("text") == "combining it with a Minecraft world. So,"
              and hit.get("exact") == 12
              and hit.get("aligned") == 12
              and hit.get("partial") is False)
        return ok, "index=%r exact=%r aligned=%r partial=%r text=%r" % (
            hit.get("index"), hit.get("exact"), hit.get("aligned"),
            hit.get("partial"), hit.get("text"))

    attempt("a01 a pintura REAL alinha na cue certa da faixa 'en-orig' "
            "(indice 3, 12 palavras exactas)", a01)

    # -- 2. the SAME paint lands on NOTHING in the wrong track -------------
    def a02():
        hit = mod.align_painted(PT_CUES, PAINTED)
        painted_low = set(w.lower() for w in PAINTED)
        pt_words = set()
        for cue in PT_CUES:
            pt_words.update(w.lower() for w in str(cue["text"]).split())
        shared = sorted(painted_low & pt_words)
        ok = hit is None and not shared
        return ok, "alinhamento=%r palavras_em_comum=%r" % (hit, shared)
    attempt("a02 a MESMA pintura NAO alinha na faixa 'pt-orig' (ZERO palavras "
            "em comum: e a pintura que identifica a faixa)", a02)

    # -- 3. a paint cut in the MIDDLE of a cue still aligns ----------------
    def a03():
        hit = mod.align_painted(EN_CUES, PAINT_CUT)
        if hit is None:
            return False, "align_painted devolveu None"
        ok = (hit.get("index") == 3
              and hit.get("exact") == 8
              and hit.get("aligned") == 8)
        return ok, "index=%r exact=%r aligned=%r" % (
            hit.get("index"), hit.get("exact"), hit.get("aligned"))
    attempt("a03 o rollup CORTADO (a pintura comeca a MEIO de uma cue) "
            "alinha na mesma cue", a03)

    # -- 4. the paint caught MID-WORD aligns and says so --------------------
    def a04():
        hit = mod.align_painted(CUE_PARTIAL, PAINT_PARTIAL)
        if hit is None:
            return False, "align_painted devolveu None"
        ok = (hit.get("index") == 0
              and hit.get("exact") == 3
              and hit.get("aligned") == 4
              and hit.get("partial") is True)
        return ok, "index=%r exact=%r aligned=%r partial=%r" % (
            hit.get("index"), hit.get("exact"), hit.get("aligned"),
            hit.get("partial"))
    attempt("a04 a palavra a MEIO ('t' para 'the') alinha e a pintura e "
            "marcada como parcial", a04)

    # -- 5. invented words do not align -------------------------------------
    def a05():
        hit = mod.align_painted(EN_CUES, PAINT_INVENTED)
        ok = hit is None
        return ok, "alinhamento=%r" % (hit,)
    attempt("a05 palavras INVENTADAS nao alinham (divergencia e divergencia)",
            a05)

    # -- 6. one or two words do not align (below the minimum) ---------------
    def a06():
        one = mod.align_painted(EN_CUES, ["in"])
        two = mod.align_painted(EN_CUES, ["in", "the"])
        ok = one is None and two is None
        return ok, "1palavra=%r 2palavras=%r min=%r" % (
            one, two, getattr(mod, "_ALIGN_MIN_EXACT", None))
    attempt("a06 uma ou duas palavras NAO alinham (abaixo do minimo de "
            "exactas)", a06)

    # -- 7. `painted_words` picks the window with the MOST words -----------
    def a07():
        # The real tree has a container and more than one caption window;
        # the one that is painting is the one with the words.
        container = _FakeElement(cls="ytp-caption-window-container")
        few = _FakeElement(
            cls="caption-window ytp-caption-window-bottom",
            children=[_FakeElement(name="hello"), _FakeElement(name="there")])
        many = _FakeElement(
            cls="caption-window ytp-caption-window-bottom "
                "ytp-caption-window-rollup",
            children=[_FakeElement(name=w) for w in PAINTED])
        uia = _FakeAutomation([container, few, many])
        got = mod.painted_words(uia, _FakeUIAModule, root=uia._root)
        ok = (got.get("words") == PAINTED
              and got.get("why") == "painted"
              and "caption-window" in str(got.get("cls") or ""))
        return ok, "why=%r cls=%r palavras=%r" % (
            got.get("why"), got.get("cls"), got.get("words"))
    attempt("a07 `painted_words` devolve a janela que tem MAIS palavras (a "
            "que o player esta a pintar)", a07)

    # -- 8. no caption window is said, not guessed --------------------------
    def a08():
        other = _FakeElement(name="1,9 mil", cls="ytp-title")
        uia = _FakeAutomation([other])
        got = mod.painted_words(uia, _FakeUIAModule, root=uia._root)
        ok = (got.get("words") == [] and got.get("why") == "no-painted-caption")
        return ok, "why=%r palavras=%r" % (got.get("why"), got.get("words"))
    attempt("a08 sem caption-window: `painted_words` diz "
            "'no-painted-caption' (e nao inventa palavras)", a08)

    # -- 9. no window at all is said, not guessed ---------------------------
    def a09():
        got = mod.painted_words(_FakeAutomation([]), _FakeUIAModule)
        ok = got.get("words") == [] and got.get("why") == "no-window"
        return ok, "why=%r" % (got.get("why"),)
    attempt("a09 sem janela: `painted_words` diz 'no-window'", a09)

    # -- 10. the track served is the one that CONTAINS the paint ------------
    def a10():
        def _run():
            _fake_net(mod)
            got = mod.fetch_track(VIDEO_ID, lang_prefs=("pt", "en"),
                                  player_lang="", painted=PAINTED)
            return got
        got = _with_cache(mod, workdir, "cache10", _run)
        ok = (got.get("state") == "has-track"
              and str(got.get("lang")).lower() == "en-orig"
              and got.get("player_source") == "painted"
              and got.get("player_match") is True
              and got.get("paint_cue") == 3)
        return ok, "lang=%r source=%r match=%r paint_cue=%r" % (
            got.get("lang"), got.get("player_source"),
            got.get("player_match"), got.get("paint_cue"))
    attempt("a10 `fetch_track(painted=...)` serve a faixa que CONTEM a "
            "pintura (en-orig, nao a pt-orig da preferencia)", a10)

    # -- 11. the CACHE never serves a track that does not hold the paint ----
    def a11():
        def _run():
            _fake_net(mod)
            # The first read has no paint: the preference decides, and the
            # Portuguese track is cached.
            first = mod.fetch_track(VIDEO_ID, player_lang="")
            # The second read HAS the paint: the cached Portuguese track does
            # not hold it, so it must NOT be served.
            second = mod.fetch_track(VIDEO_ID, player_lang="", painted=PAINTED)
            return first, second
        first, second = _with_cache(mod, workdir, "cache11", _run)
        ok = (str(first.get("lang")).lower() == "pt-orig"
              and str(second.get("lang")).lower() == "en-orig"
              and second.get("player_source") == "painted"
              and second.get("paint_cue") == 3)
        return ok, "1o=%r 2o=%r source=%r paint_cue=%r" % (
            first.get("lang"), second.get("lang"),
            second.get("player_source"), second.get("paint_cue"))
    attempt("a11 o CACHE nao serve a faixa que NAO contem a pintura (o cache "
            "com a pt-orig e reescrito)", a11)

    return rows


# ── the mutants ──────────────────────────────────────────────────────────────
# The anchors are EXACT strings of `app/webview/youtube_captions.py`. A
# mutant whose anchor is missing or ambiguous is DECORATIVE -- it proves
# nothing -- so the oracle refuses to count it.

MUTANTS = [
    # THE MID-WORD RULE IS GONE: the player caught writing 'the' as 't' no
    # longer aligns, and the line the owner is comparing against DISAPPEARS
    # from the panel for the fraction of a second it is written.
    ("a-palavra-a-meio-nao-e-aceite",
     "            if last and i == take - 1 and len(b) >= 1 and a.startswith(b):\n"
     "                partial = True\n"
     "                continue\n"
     "            return None",
     "            return None"),
    # THE CUT ROLLUP IS NOT ACCEPTED: the alignment only tries the FIRST
    # word of each cue, so a paint that starts in the middle of a cue -- the
    # normal shape of the rollup -- matches nothing at all.
    ("o-rollup-cortado-nao-e-aceite",
     "        for off0 in range(len(cwords)):",
     "        for off0 in range(1):"),
    # THE MINIMUM OF EXACT WORDS FALLS TO ONE: two words of the wrong track
    # are enough to call it the right track, and the app serves the wrong
    # LANGUAGE to the owner.
    ("o-minimo-de-palavras-exactas-desce",
     "_ALIGN_MIN_EXACT = 3",
     "_ALIGN_MIN_EXACT = 1"),
    # THE PAINT IS NOT CHECKED ON THE CACHED PATH: the cached track is
    # served even when the player's own words are in ANOTHER track -- the
    # Portuguese against the English, silently.
    ("a-verificacao-da-pintura-no-cache-e-removida",
     "                paint_ok = paint_hit is not None",
     "                paint_ok = True"),
    # THE FIRST CAPTION WINDOW WINS, NOT THE ONE WITH THE WORDS: the tree
    # carries more than one, and the container (no words) can come first.
    ("a-primeira-janela-ganha-em-vez-da-mais-palavras",
     "        if len(words) > len(best):",
     "        if not best:"),
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
        print("ARMS (pure: fixtures, no network, no browser, no app, no audio)")
        workdir = tempfile.mkdtemp(prefix="yt-mirror-align-oracle-")
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
    workdir = tempfile.mkdtemp(prefix="yt-mirror-align-oracle-mut-")
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
            sub = tempfile.mkdtemp(prefix="yt-mirror-align-oracle-mut-run-")
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
