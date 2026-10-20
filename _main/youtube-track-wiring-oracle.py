"""ORACLE: the YOUTUBE REAL TRACK, and the rule that the ASR is the BASE.

Owner, 2026-10-19, verbatim:
  *"faz a legenda do youtube mostrar na tela em tempo real. se precisar pegar
  o tempo do video, faça."*
  *"youtube ta mostrando texto burro da pagina inves da porra da
  legenda/transcriptino de um video"*
  *"e nao e pra tu parar de transcrever audio do chrome. é audio do youtube
  CASO tenha legenda do youtube. se for um video sem legenda, vaio transcrever
  ao vivo igual."*

THIS GATE TESTS THE WIRING, NOT THE PAGE READER. The page reader's own
filters have their own gate (`_main/_external-subs-stability-oracle.py` and
`_main/external-caption-chrome-census.py`). What is decided HERE is the
question the owner actually asked:

  1. does the PAGE's text ever reach the caption box for a YouTube window?
  2. does the PAGE's text ever STOP the live transcription?
  3. does a video WITHOUT a caption track give the microphone back?

The real `app/webview/sotto_webview.py` is loaded and its REAL methods run
(`external_caption`, `_park_worker_for_external`, `on_external_captions_released`).
Only the three seams that need a screen are stubbed: which window is in front
(`GetForegroundWindow`/`IsWindow`), what the page reader finds
(`external_subs.caption_lines`), and where the player is
(`youtube_captions.player_time`).

THE NEGATIVE ARMS ARE MUTANTS, not git history: a copy of the shell with ONE
rule broken, loaded from a temp file and put through the same arms. A gate
that cannot say "no" is a promise.

ARMS (10)
  a1  a real cue at this instant        -> the track's text, and the ASR stops
  a2  a gap between the cues             -> nothing, and the ASR keeps running
  a3  the video has NO track             -> nothing, and the ASR comes back
  a4  the page has chrome + a real cue   -> only the track's text, NEVER chrome
  a5  the page has chrome + NO track     -> nothing, NEVER chrome
  a6  a Stremio window                   -> the page line still arrives
  a7  a browser window that is not a player -> nothing
  a8  the video id cannot be read        -> nothing, the ASR keeps running
  a9  the track is still being fetched   -> nothing, the ASR keeps running
  a10 the player's clock cannot be read  -> nothing, the ASR keeps running

MUTANTS (5)
  m1  the YouTube page is NOT demoted    -> a4, a5 RED
  m2  a video without a track does not give the microphone back -> a3 RED
  m3  the real track releases the ASR as fast as the page reader -> a2 RED
  m4  the real cue is never emitted       -> a1 RED
  m5  the Stremio path is demoted too     -> a6 RED

It launches nothing: no browser, no player, no Sotto shell, no worker, no
audio, no network.

    python _main\\youtube-track-wiring-oracle.py            # arms + mutants, rc=0 on PASS
    python _main\\youtube-track-wiring-oracle.py --neg-arm  # mutants only, rc=1 BY DESIGN

The exit convention is the one of `_main/mute-audio-oracle.py`: the default
mode runs the arms AND the mutants and exits 0 only if every arm held and
every mutant was caught; `--neg-arm` runs the mutants alone and exits 1 on
purpose, because a battery step that expects that rc is the proof that this
gate can say "no".
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import threading
import time
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(REPO, "app", "webview")
TARGET = os.path.join(WEBVIEW, "sotto_webview.py")

if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)

import external_subs  # noqa: E402
import youtube_captions  # noqa: E402

#: The window the scenario pretends to watch. It only has to be a number:
#: `IsWindow` is stubbed.
HWND = 0x00A1B2C3
#: A YouTube video id, and the address bar that carries it.
VIDEO_ID = "dQw4w9WgXcQ"
PAGE_URL = "https://www.youtube.com/watch?v=" + VIDEO_ID

#: THE PAGE'S OWN TEXT -- what reached the caption box on 2026-10-19 19:14,
#: in the owner's own log. This is the thing that must NEVER appear again.
CHROME_1 = "Oferta sujeita aos termos. Cancele quando quiser."
CHROME_2 = "há 4 sem."
CHROME_3 = "Thre's a small problem ."

#: A real cue of the real track of `dQw4w9WgXcQ` (MEASURED 2026-10-19 by
#: `_main/youtube-captions-oracle.py --live`: 60 cues, the first at 18.64 s).
CUES = [
    {"start": 18.64, "end": 21.88, "text": "Não somos estranhos ao amor"},
    {"start": 22.10, "end": 25.40, "text": "Nunca vou mentir nem te magoar"},
]
T_IN = 19.50          # inside the first cue
T_GAP = 30.00         # between the two cues: the player shows nothing here

TRACK_OK = {
    "state": "has-track", "cues": CUES, "lang": "pt-BR", "source": "manual",
    "ext": "json3", "duration": 213.0, "reason": "ok", "error": None,
}
TRACK_NONE = {
    "state": "no-track", "cues": [], "lang": None, "source": None,
    "ext": None, "duration": 213.0, "reason": "no-tracks-listed",
    "error": None,
}


# ── the clock ───────────────────────────────────────────────────────────────

class _Clock(object):
    """A clock the gate owns, so "30 s later" is a number, not a wait."""

    now = 1000.0


CLOCK = _Clock()
_REAL_MONOTONIC = time.monotonic


def _fake_monotonic():
    return CLOCK.now


# ── the fakes ───────────────────────────────────────────────────────────────

class FakeWindow(object):
    """One window the scenario pretends is on screen."""

    def __init__(self, source="", page_lines=(), edits=(), title="Sotto"):
        self.source = source
        self.page_lines = list(page_lines)
        self.edits = list(edits)
        self.title = title


class FakeBridge(object):
    """The worker, as the shell sees it."""

    def __init__(self):
        self.child = types.SimpleNamespace(pid=4242)
        self.stops = []

    def stop(self, reason):
        self.stops.append(reason)


class FakePolicy(object):
    def __init__(self):
        self.boundaries = []

    def boundary(self, closed=False, why=""):
        self.boundaries.append((closed, why))


class FakeShell(object):
    """The shell, with the REAL methods bound to it.

    `external_caption`, `_park_worker_for_external` and
    `on_external_captions_released` are the real functions of the real shell:
    what the caption box shows and whether the worker is parked are decided
    by the product, not by this gate.
    """

    def __init__(self, mod, track):
        self.visible = True
        self._caption_window_shown = False
        self.external_captions_active = False
        self.external_captions_available = False
        self.external_lines = 0
        self.external_suppressed = 0
        self._external_parked = False
        self._paused = False
        self._external_last_text = ''
        self._last_external_resume = 0.0
        self._bridge = FakeBridge()
        self.bridge = self._bridge
        self._reload_policy = FakePolicy()
        #: THE SHELL'S "I AM DYING" FLAG. The real `on_external_captions_
        #: released` reads it (2026-10-20: a worker spawned while the shell
        #: was closing was an ORPHAN, because `os._exit` does not kill a
        #: child). Without it the fake raised AttributeError and the arm
        #: said nothing about why.
        self.exiting = threading.Event()
        self.emitted = []
        self.window_lines = []
        self.releases = 0
        self.resumes = []
        self.youtube_track_thread = FakeTrackThread(track)
        self.external_caption = types.MethodType(
            mod.SottoShell.external_caption, self)
        self._park_worker_for_external = types.MethodType(
            mod.SottoShell._park_worker_for_external, self)
        # THE RELEASE IS COUNTED HERE, and the REAL method still decides
        # whether the worker comes back. The two are different facts: the
        # release is REQUESTED by the reader, and the resume is GRANTED by
        # the shell (which has a 45 s debounce and a "was it parked?" test).
        self._real_released = types.MethodType(
            mod.SottoShell.on_external_captions_released, self)

        def on_external_captions_released():
            self.releases += 1
            return self._real_released()

        self.on_external_captions_released = on_external_captions_released

    # the bits the real methods call
    def emit(self, kind, payload):
        self.emitted.append((kind, payload))

    def push_caption_to_window(self, text):
        self.window_lines.append(text)

    def start_worker(self, reason):
        self.resumes.append(reason)
        return True

    def _release(self, reason):
        self.releases += 1
        self.on_external_captions_released()
        return True

    def text(self):
        """What the caption box got, in order."""
        return [p['text'] for kind, p in self.emitted
                if kind == 'external-caption']


class FakeTrackThread(object):
    """The track thread, with the real contract."""

    def __init__(self, track):
        self.track = track
        self.track_for = VIDEO_ID if track is not None else ''
        self.requested = []
        #: THE WORDS THE PLAYER WAS PAINTING when the track was asked for
        #: (2026-10-20: the track the player shows is decided by the words
        #: it paints). A fake that does not know about them is not the real
        #: contract.
        self.painted = []

    def current(self, video_id):
        if self.track is None or self.track_for != video_id:
            return None
        return self.track

    def request(self, video_id, painted=None):
        self.requested.append(video_id)
        self.painted = list(painted or [])
        if self.track is None or self.track_for != video_id:
            return None
        return self.track


# ── the scenario ────────────────────────────────────────────────────────────

class Scenario(object):
    """One situation, and what must be true about it.

    `steps` is a list of moments: each one says what the clock said, where
    the player was, and which track (if any) the video had. A scenario with
    two steps is a situation that CHANGES -- the track arriving, the track
    going away -- and that is the shape the owner actually lives in.
    """

    def __init__(self, name, window, steps, expect_text=(), expect_parked=False,
                 expect_releases=0, expect_resumes=0, expect_page_reads=None,
                 why=""):
        self.name = name
        self.window = window
        self.steps = steps
        self.expect_text = list(expect_text)
        self.expect_parked = expect_parked
        self.expect_releases = expect_releases
        self.expect_resumes = expect_resumes
        self.expect_page_reads = expect_page_reads
        self.why = why


def _yt_window(page_lines=(), with_id=True):
    return FakeWindow(
        source="external:youtube",
        page_lines=page_lines,
        edits=[PAGE_URL] if with_id else [],
        title="Um video - YouTube - Google Chrome")


def scenarios():
    out = []
    out.append(Scenario(
        "a1", _yt_window(), [{"at": 1000.0, "t": T_IN, "track": TRACK_OK}],
        expect_text=["Não somos estranhos ao amor"], expect_parked=True,
        expect_releases=0, expect_resumes=0, expect_page_reads=0,
        why="a real cue at this instant: the track's text, and the ASR stops"))
    out.append(Scenario(
        "a2", _yt_window(),
        [{"at": 1000.0, "t": T_IN, "track": TRACK_OK},
         {"at": 1002.0, "t": T_GAP, "track": TRACK_OK}],
        expect_text=["Não somos estranhos ao amor"], expect_parked=True,
        expect_releases=0, expect_resumes=0, expect_page_reads=0,
        why="a gap between the cues: nothing new, and the ASR keeps running"))
    out.append(Scenario(
        "a3", _yt_window(), [{"at": 1000.0, "t": T_IN, "track": TRACK_NONE}],
        expect_text=[], expect_parked=False,
        expect_releases=1, expect_resumes=0, expect_page_reads=0,
        why="a video with NO track: the ASR comes back"))
    out.append(Scenario(
        "a4", _yt_window([CHROME_1]), [{"at": 1000.0, "t": T_IN, "track": TRACK_OK}],
        expect_text=["Não somos estranhos ao amor"], expect_parked=True,
        expect_releases=0, expect_resumes=0, expect_page_reads=0,
        why="the page has chrome and there IS a real cue: only the cue"))
    out.append(Scenario(
        "a5", _yt_window([CHROME_1, CHROME_2]),
        [{"at": 1000.0, "t": T_IN, "track": TRACK_NONE}],
        expect_text=[], expect_parked=False,
        expect_releases=1, expect_resumes=0, expect_page_reads=0,
        why="the page has chrome and there is NO track: never the chrome"))
    out.append(Scenario(
        "a6", FakeWindow(source="external:stremio", page_lines=["Fala, mundo"],
                         title="Stremio"),
        [{"at": 1000.0, "t": T_IN, "track": TRACK_OK}],
        expect_text=["Fala, mundo"], expect_parked=True,
        expect_releases=0, expect_resumes=0, expect_page_reads=1,
        why="a Stremio window: the player paints the caption, so the page IS it"))
    out.append(Scenario(
        "a7", FakeWindow(source="", page_lines=["qualquer coisa"],
                         title="Uma pagina"),
        [{"at": 1000.0, "t": T_IN, "track": TRACK_OK}],
        expect_text=[], expect_parked=False,
        expect_releases=0, expect_resumes=0, expect_page_reads=1,
        why="a window that is not a player: nothing"))
    out.append(Scenario(
        "a8", _yt_window(with_id=False),
        [{"at": 1000.0, "t": T_IN, "track": TRACK_OK}],
        expect_text=[], expect_parked=False,
        expect_releases=0, expect_resumes=0, expect_page_reads=0,
        why="the video id cannot be read: nothing, and the ASR keeps running"))
    out.append(Scenario(
        "a9", _yt_window(), [{"at": 1000.0, "t": T_IN, "track": None}],
        expect_text=[], expect_parked=False,
        expect_releases=0, expect_resumes=0, expect_page_reads=0,
        why="the track is still being fetched: nothing, the ASR keeps running"))
    out.append(Scenario(
        "a10", _yt_window(), [{"at": 1000.0, "t": None, "track": TRACK_OK}],
        expect_text=[], expect_parked=False,
        expect_releases=0, expect_resumes=0, expect_page_reads=0,
        why="the player's clock cannot be read: nothing, the ASR keeps running"))
    out.append(Scenario(
        "a12", _yt_window(),
        [{"at": 1000.0, "t": T_IN, "track": TRACK_OK},
         {"at": 1000.0 + 120.0, "t": T_IN, "track": TRACK_OK}],
        # A PAUSED video: the clock is readable and the cue is there, so the
        # caption stays and the ASR is NOT released -- not even after the
        # 30 s grace. MEASURED 2026-10-20 on the owner's own video: `t=1241.0`
        # fixed across three reads, and with the release on a timer every
        # 30 s of paused video cost a 1.2 GB model load.
        # THE LINE APPEARS TWICE: the caption channel emits a line OPEN
        # (final=false) and then CLOSED (final=true), which is the contract.
        expect_text=["Não somos estranhos ao amor", "Não somos estranhos ao amor"],
        expect_parked=True,
        expect_releases=0, expect_resumes=0, expect_page_reads=0,
        why="a PAUSED video keeps the caption and does NOT release the ASR"))
    out.append(Scenario(
        "a11", _yt_window(),
        [{"at": 1000.0, "t": T_IN, "track": TRACK_OK},
         {"at": 1005.0, "t": T_IN, "track": TRACK_NONE}],
        # THE LINE IS EMITTED TWICE, AND THAT IS THE CONTRACT: once OPEN
        # (final=false, the panel is still forming it) and once CLOSED
        # (final=true, the panel commits it). The close is what the reader
        # does when the line it was forming ends.
        expect_text=["Não somos estranhos ao amor", "Não somos estranhos ao amor"],
        expect_parked=True,
        expect_releases=1, expect_resumes=1, expect_page_reads=0,
        why="the track was there and then it is gone: the ASR comes BACK"))
    return out


# ── the driver ──────────────────────────────────────────────────────────────

class Sandbox(object):
    """The stubs, installed and removed around one arm."""

    def __init__(self, mod, window):
        self.mod = mod
        self.window = window
        self.current_t = None
        self.page_reads = 0
        self._saved = {}

    def __enter__(self):
        import ctypes
        user32 = ctypes.windll.user32
        self._saved['fg'] = user32.GetForegroundWindow
        self._saved['iw'] = user32.IsWindow
        user32.GetForegroundWindow = lambda: 0
        user32.IsWindow = lambda hwnd: 1
        self._saved['monotonic'] = time.monotonic
        time.monotonic = _fake_monotonic
        self._saved['player_source'] = external_subs.player_source
        self._saved['caption_lines'] = external_subs.caption_lines
        self._saved['edit_values'] = external_subs.edit_values
        self._saved['window_title'] = external_subs._window_title
        self._saved['player_time'] = youtube_captions.player_time
        self._saved['log'] = self.mod.log

        window = self.window

        def player_source(hwnd, uia=None, UIA=None, root=None, url=None):
            return window.source if int(hwnd) == HWND else ''

        def caption_lines(hwnd, uia, UIA, trace=None):
            self.page_reads += 1
            # THE REAL READER REFUSES A WINDOW THAT IS NOT A PLAYER (it is
            # what keeps a browser's bottom bar from being read as speech).
            if not window.source or not window.page_lines:
                return []
            return [(window.source, list(window.page_lines))]

        def edit_values(hwnd, uia, UIA):
            return list(window.edits)

        def window_title(hwnd):
            return window.title

        def player_time(uia, UIA, hwnd, duration=None):
            return self.current_t

        external_subs.player_source = player_source
        external_subs.caption_lines = caption_lines
        external_subs.edit_values = edit_values
        external_subs._window_title = window_title
        youtube_captions.player_time = player_time
        self.mod.log = lambda *a, **k: None
        return self

    def __exit__(self, *exc):
        import ctypes
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow = self._saved['fg']
        user32.IsWindow = self._saved['iw']
        time.monotonic = self._saved['monotonic']
        external_subs.player_source = self._saved['player_source']
        external_subs.caption_lines = self._saved['caption_lines']
        external_subs.edit_values = self._saved['edit_values']
        external_subs._window_title = self._saved['window_title']
        youtube_captions.player_time = self._saved['player_time']
        self.mod.log = self._saved['log']
        return False


def run_scenario(mod, scen):
    """Drive the real watcher through the scenario. Returns what happened."""
    shell = FakeShell(mod, scen.steps[0].get("track"))
    watcher = mod.ExternalCaptionWatcher(shell)
    watcher.target_hwnd = HWND
    with Sandbox(mod, scen.window) as box:
        for step in scen.steps:
            CLOCK.now = step["at"]
            box.current_t = step.get("t")
            shell.youtube_track_thread = FakeTrackThread(step.get("track"))
            got, yt_mode = watcher._read(None, None)
            watcher._tick(got, yt_mode)
        page_reads = box.page_reads
    return {
        "text": shell.text(),
        "window_lines": list(shell.window_lines),
        "parked": bool(shell._bridge.stops) or shell.external_captions_active,
        "worker_stops": list(shell._bridge.stops),
        "releases": shell.releases,
        "resumes": list(shell.resumes),
        "page_reads": page_reads,
    }


def check(scen, seen):
    """The expectations, as a list of failures (empty = the arm passed)."""
    bad = []
    if list(seen["text"]) != list(scen.expect_text):
        bad.append("text %r != %r" % (seen["text"], scen.expect_text))
    if bool(seen["parked"]) != bool(scen.expect_parked):
        bad.append("parked %r != %r (stops=%r)"
                   % (seen["parked"], scen.expect_parked, seen["worker_stops"]))
    if seen["releases"] != scen.expect_releases:
        bad.append("releases %r != %r" % (seen["releases"], scen.expect_releases))
    if len(seen["resumes"]) != scen.expect_resumes:
        bad.append("resumes %r != %d" % (seen["resumes"], scen.expect_resumes))
    if (scen.expect_page_reads is not None
            and seen["page_reads"] != scen.expect_page_reads):
        bad.append("page_reads %r != %r"
                   % (seen["page_reads"], scen.expect_page_reads))
    return bad


# ── the mutants ─────────────────────────────────────────────────────────────

MUTANTS = (
    ("m1", "the YouTube page is NOT demoted",
     "        if source == 'external:youtube':",
     "        if False:"),
    ("m2", "a video without a track does not give the microphone back",
     "            return [], self._yt_forget('no-track:%s' % reason, urgent=True)",
     "            return [], self._yt_forget('no-track:%s' % reason, urgent=False)"),
    ("m3", "the real track releases the ASR as fast as the page reader",
     "        if (not yt_mode and self.last_line\n"
     "                and (now - self.last_seen) >= self.RELEASE_S):",
     "        if (self.last_line\n"
     "                and (now - self.last_seen) >= self.RELEASE_S):"),
    ("m4", "the real cue is never emitted",
     "        self.yt_reason = 'has-cue'\n"
     "        return [('external:youtube:track', [text])], False",
     "        self.yt_reason = 'has-cue'\n"
     "        return [], False"),
    ("m5", "the Stremio path is demoted too",
     "        if source == 'external:youtube':",
     "        if source:"),
)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_mutants():
    """A copy of the shell per mutant, in a temp dir. Returns (name, mod).

    THE SHELL IS READ WITH UNIVERSAL NEWLINES. It is CRLF (a hard rule of
    this repo), and an anchor written with "\\n" would never match a
    "\\r\\n" in the file -- the mutant would then be reported as a missing
    anchor and the gate would ABORT instead of testing it. The mutant copy
    is written with LF, which Python does not care about.
    """
    with io.open(TARGET, "r", encoding="utf-8") as fh:
        source = fh.read()
    out = []
    tmpdir = tempfile.mkdtemp(prefix="yt-wiring-")
    for name, _why, old, new in MUTANTS:
        if source.count(old) != 1:
            print("ABORT: the mutant %s anchor occurs %d times in the shell."
                  % (name, source.count(old)))
            return None
        mutated = source.replace(old, new)
        path = os.path.join(tmpdir, "sotto_webview_%s.py" % name)
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(mutated)
        out.append((name, load_module(path, "sotto_webview_mutant_%s" % name)))
    return out


# ── the run ─────────────────────────────────────────────────────────────────

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    neg_only = "--neg-arm" in argv

    if not os.path.exists(TARGET):
        print("ABORT: %s is missing." % TARGET)
        return 2

    all_scen = scenarios()
    failures = 0
    if not neg_only:
        live = load_module(TARGET, "sotto_webview_live")
        print("=== the LIVE shell: %s" % os.path.basename(TARGET))
        for scen in all_scen:
            seen = run_scenario(live, scen)
            bad = check(scen, seen)
            if bad:
                failures += 1
                print("  RED  %-4s %s" % (scen.name, scen.why))
                for b in bad:
                    print("        %s" % b)
            else:
                print("  ok   %-4s %s" % (scen.name, scen.why))

    # ── the negative arm: the mutants ──
    print("")
    print("=== the MUTANTS: each one must turn an arm RED")
    mutants = build_mutants()
    if mutants is None:
        return 2
    caught = 0
    by_name = dict(mutants)
    for name, why, _old, _new in MUTANTS:
        mod = by_name[name]
        reds = []
        for scen in all_scen:
            try:
                seen = run_scenario(mod, scen)
            except Exception as exc:  # noqa: BLE001
                reds.append("%s (raised %r)" % (scen.name, exc))
                continue
            if check(scen, seen):
                reds.append(scen.name)
        if reds:
            caught += 1
            print("  ok   %-4s caught by %s -- %s" % (name, ",".join(reds), why))
        else:
            failures += 1
            print("  RED  %-4s NOT CAUGHT -- %s" % (name, why))

    if neg_only:
        # rc=1 BY DESIGN, the same convention as `_main/mute-audio-oracle.py`:
        # the negative arm REPROVES on purpose, and a battery step that
        # expects this rc is the proof that this gate can say "no".
        print("")
        print("VERDICT: NEG-ARM %s  mutants %d/%d  (rc=1 por desenho: o braco "
              "negativo REPROVA de proposito)" % ("PASS" if caught == len(MUTANTS)
                                                  else "FAIL", caught, len(MUTANTS)))
        return 1

    print("")
    ok = not failures
    print("VERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", len(all_scen) - failures, len(all_scen),
             caught, len(MUTANTS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
