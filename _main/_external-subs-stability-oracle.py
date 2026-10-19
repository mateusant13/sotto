"""ORACLE: hover/click UI must never reach the external-caption output.

Owner, 2026-10-17: *"a legenda ta pegando mais coisas do youtube que nao devia...
passar meu mouse encima da display em alguns textos, ou carregar esses textos,
sei la. esquisito"*.

This drives the REAL `app/webview/external_subs.py:caption_lines` against a
synthetic sequence of UI Automation polls. Only `_window_title` and
`_process_name` are stubbed (both are ctypes calls); the band filter, the
join, the stability gate and the bottom-run cap all run for real.

FIXTURE GEOMETRY (measured shape from the module docstring: captions at
y=942..1001 inside a 1920x1080 player). Window (0,0,1920,1080), player
(0,100,1920,1000), so band_top = 100 + 900*0.62 = 658.

ARMS
  live     the shipped module                         -> noise must NOT appear
  nogate   copy with the stability gate disabled      -> noise MUST appear
  head     the module as committed (OPT-IN, see below)
  chrome   the REAL chrome out of the owner's log     -> it must NOT appear
  nochrome copy with the chrome rule removed          -> it MUST appear

THE NEGATIVE ARMS are MUTANTS, not git history, and that is deliberate: the
`head` arm used to mean "the module before the fix", and it STOPPED meaning
that the day the fix was committed -- it kept running, it just stopped
proving anything, and a gate that cannot fail is a promise. It is still
available with `--arms live,nogate,head`, but it is not part of the default
set and it is not what says no. The two mutants are.

THE CHROME SCENARIO uses the chrome the owner's own app actually produced --
the view counter, the age of the video, a chat handle, a separator glyph, and
the counter SPLIT IN TWO WORDS, which is the case an element-shaped rule
cannot see. The census is `_main/external-caption-chrome-census.py`.

It launches nothing: no browser, no player, no Sotto shell, no worker.

    python _main\_external-subs-stability-oracle.py
    python _main\_external-subs-stability-oracle.py --arms live,nogate,head
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(REPO, "app", "webview", "external_subs.py")
HWND = 0x00A1B2C3
WINDOW = (0, 0, 1920, 1080)
PLAYER = (0, 100, 1920, 1000)

CAPTION_1 = (936, [(">> So", 915), (" the", 965)])
CAPTION_1_MORE = (936, [(">> So", 885), (" the", 935), (" Akali", 975)])
CAPTION_2 = (976, [(" Brothers", 895), (" and", 985)])
CAPTION_2_MORE = (976, [(" Brothers", 875), (" and", 965), (" the", 1005)])
# Hover preview card: mid-player, left-aligned, persistent while the pointer
# rests on the video. INSIDE the band and INSIDE the player rect, and far
# enough above the caption that the bottom-run cap rejects it on its own.
CARD_ROW = (700, [("AKALI BROTHERS - FULL MOVIE", 120), ("1.2M views", 430)])
# Click feedback: the controls bar raises "Pause" beside the caption, one poll,
# and it lands in the same bottom run as the caption -- only the gate stops it.
CLICK_ROW = (958, [("Pause", 1600)])
# Chrome welded onto the caption's OWN row, left of it. This is the case
# stability alone cannot settle: the text persists, so it earns a streak. The
# centring veto is what stops it taking the row over.
FUSED_ROW = (936, [("AKALI BROTHERS - FULL MOVIE", 120), (">> So", 915), (" the", 965)])


def _els(spec_rows):
    """Honour each fragment's own x0 at ~10px/char: captions are centred at
    x=960 in this 1920-wide player, chrome is not."""
    out = []
    for y0, pairs in spec_rows:
        for name, x0 in pairs:
            out.append(_El(name, (x0, y0, x0 + 10 * len(name), y0 + 20)))
    return out


def caption_row(which):
    if which.startswith("chrome:"):
        spec = CHROME_ROWS[which.split(":", 1)[1]]
        return _els([spec])
    spec = {"c1": CAPTION_1, "c1m": CAPTION_1_MORE, "c2": CAPTION_2,
            "c2m": CAPTION_2_MORE, "card": CARD_ROW, "click": CLICK_ROW,
            "fused": FUSED_ROW}[which]
    return _els([spec])


def POLLS_CHROME():
    """Three polls of each chrome row -- it HOLDS, which is exactly why the
    temporal gate cannot tell a counter apart from a caption."""
    polls = []
    for kind in sorted(CHROME_ROWS):
        polls.append(("chrome %s appears" % kind, ["chrome:" + kind]))
        polls.append(("chrome %s holds" % kind, ["chrome:" + kind]))
        polls.append(("chrome %s holds" % kind, ["chrome:" + kind]))
    return polls


def POLLS_CHROME_WITH_CAPTION():
    """A real caption beside the chrome: the caption must SURVIVE and the
    chrome must not take the row."""
    return [
        ("caption arrives", ["c1m"]),
        ("caption holds + chrome", ["c1m", "chrome:split_count"]),
        ("caption holds + chrome", ["c1m", "chrome:split_count"]),
    ]


def POLLS():
    """(label, [row ids]) per poll -- the whole owner-visible story."""
    return [
        ("caption arrives",        ["c1"]),
        ("caption holds",          ["c1"]),
        ("caption grows, L2 new",  ["c1m", "c2"]),
        ("TWO-LINE caption solid", ["c1m", "c2m"]),
        ("MOUSE HOVERS -> card",   ["c1m", "c2m", "card"]),
        ("mouse rests (card 2x)",  ["c1m", "c2m", "card"]),
        ("mouse leaves",           ["c1m", "c2m"]),
        ("CLICK -> Pause appears", ["c1m", "c2m", "click"]),
        ("click feedback gone",    ["c1m", "c2m"]),
        ("chrome fused in-row",    ["fused", "c2m"]),
        ("chrome fused in-row",    ["fused", "c2m"]),
        ("back to caption",        ["c1m", "c2m"]),
    ]


NOISE = ("AKALI BROTHERS", "1.2M", "views", "Pause", "FULL MOVIE")

#: THE REAL CHROME, taken from the owner's own log (the 220 external lines of
#: 2026-10-17/18 -- the census is `_main/external-caption-chrome-census.py`):
#: the view counter, the age of the video, a chat handle, a separator glyph,
#: and the counter SPLIT IN TWO WORDS.
#:
#: The last two are the case an element-shaped rule CANNOT see: the per-
#: element pass looks at one word at a time, so "1,9" + " mil" and "há 1" +
#: " dia" are each invisible to it. The row is judged once it is whole.
#:
#: Every one of these is CENTRED, so the geometry veto cannot be what stops
#: it: the chrome rule is the only thing that can.
CHROME_ROWS = {
    "count":       (960, [("344", 940)]),
    "ago":         (960, [("há 1 dia", 930)]),
    "ago_pt":      (960, [("há 4 sem.", 930)]),
    "handle":      (960, [("@zachw2906", 920)]),
    "dot":         (960, [("·", 955)]),
    "split_count": (960, [("1,9", 930), (" mil", 960)]),
    "split_ago":   (960, [("há 1", 935), (" dia", 975)]),
}

#: What the joined row of each chrome row is. The chrome must NOT be here.
CHROME_TEXT = {
    "count": "344",
    "ago": "há 1 dia",
    "ago_pt": "há 4 sem.",
    "handle": "@zachw2906",
    "dot": "·",
    "split_count": "1,9 mil",
    "split_ago": "há 1 dia",
}

#: Set per module in run_polls: the pre-fix caption_lines takes no trace arg.
HAS_TRACE = True


# --- fake UIA ------------------------------------------------------------
class _Rect(object):
    def __init__(self, t):
        (self.left, self.top, self.right, self.bottom) = t


class _El(object):
    def __init__(self, name, rect, ctype=50020):
        self.CurrentName = name
        self.CurrentBoundingRectangle = _Rect(rect)
        self.CurrentControlType = ctype


class _Coll(object):
    def __init__(self, items):
        self._items = items

    @property
    def Length(self):
        return len(self._items)

    def GetElement(self, i):
        return self._items[i]


class _Root(object):
    def __init__(self, items):
        self._items = items
        self.CurrentBoundingRectangle = _Rect(WINDOW)

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


# --- harness ------------------------------------------------------------
def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    mod._window_title = lambda hwnd: "AKALI BROTHERS - YouTube"
    mod._process_name = lambda hwnd: "chrome.exe"
    if hasattr(mod, "_RUNS"):
        mod._RUNS.clear()
    return mod


def run_polls(mod, verbose=False, polls=None):
    """[(poll label, output, trace)] -- state carried across polls on purpose."""
    global HAS_TRACE
    HAS_TRACE = len(inspect.signature(mod.caption_lines).parameters) >= 4
    out = []
    for label, rows in (POLLS() if polls is None else polls):
        items = []
        for rid in rows:
            items.extend(caption_row(rid))
        items.append(_El("AKALI BROTHERS - FULL MOVIE", (0, 100, 1920, 1000), 50004))
        trace = []
        if HAS_TRACE:
            got = mod.caption_lines(HWND, _Uia(items), _UIA, trace)
        else:
            got = mod.caption_lines(HWND, _Uia(items), _UIA)  # pre-fix: no trace
        if verbose:
            print("   -- %s" % label)
            for key, text, verdict, why in trace:
                print("      row=%-5s %-8s %-46r %s" % (key, verdict, text, why))
        out.append((label, got, trace))
    return out


def line_texts(got):
    return [ln for _src, lines in got for ln in lines]


def check_live(results):
    fails = []
    two_line = None
    for i, (label, got, _trace) in enumerate(results):
        texts = line_texts(got)
        for t in texts:
            for n in NOISE:
                if n in t:
                    fails.append("NOISE LEAKED on poll %r: %r contains %r" % (label, t, n))
            if ">>" in t and re.search(r"[a-z0-9]\S*>>", t):
                fails.append("FUSED onto the caption on poll %r: %r" % (label, t))
        if i == 0:
            # The first poll of a new caption is DELIBERATELY empty: that is
            # the confirmation latency, and it is what makes the gate work.
            if texts:
                fails.append("first poll emitted %r without confirmation" % (texts,))
            continue
        if not texts:
            fails.append("CAPTION LOST on poll %r: empty output" % label)
        if len(texts) == 2 and two_line is None:
            two_line = (label, texts)
    if two_line is None:
        fails.append("two-line caption never emitted intact")
    if two_line and two_line[1] != [">> So the Akali", "Brothers and the"]:
        fails.append("two-line caption mangled: %r" % (two_line[1],))
    return fails, two_line


# --- negative arms ------------------------------------------------------
def _mutate_gate(src):
    """Copy with BOTH temporal/geometric gates disabled -> pre-fix behaviour.

    Two single-token mutations, each count-asserted, so a stale anchor fails
    loudly instead of silently testing the shipped code a second time.
    """
    out, n1 = re.subn(r"(?m)^_CONFIRM_POLLS = 2$", "_CONFIRM_POLLS = 1", src)
    out, n2 = re.subn(r"(?m)^_CENTRE_TOL = 0\.15$", "_CENTRE_TOL = 10.0", out)
    if (n1, n2) != (1, 1):
        raise SystemExit("MUTANT INVALID: anchors matched %d/%d, want 1/1" % (n1, n2))
    return out


def _mutate_chrome(src):
    """Copy with the JOINED-ROW chrome rule neutered -> the pre-fix behaviour.

    ONE mutation, count-asserted, so a stale anchor fails loudly instead of
    silently measuring the shipped code a second time. The temporal and
    geometric gates are left ALONE on purpose: this arm has to show that the
    chrome rule is the thing that stops the chrome, not the gates.
    """
    out, n = re.subn(r"(?m)^    text = str\(line or ''\)\.strip\(\)$",
                     "    return False\n    text = str(line or '').strip()",
                     src)
    if n != 1:
        raise SystemExit("MUTANT INVALID: anchor matched %d times, want 1" % n)
    return out


def _head_source():
    r = subprocess.run(["git", "-C", REPO, "show", "HEAD:app/webview/external_subs.py"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout.decode("utf-8")


def check_negative(results, arm):
    """Noise MUST appear here, or the oracle cannot say no."""
    leaked = []
    for label, got, _trace in results:
        for t in line_texts(got):
            if any(n in t for n in NOISE):
                leaked.append("%s: %r" % (label, t))
    if not leaked:
        return ["NEGATIVE ARM %r PRODUCED NO NOISE -> the oracle cannot say no" % arm]
    return []


def check_chrome(results, with_caption_results=None):
    """The chrome must NOT reach the caption box; the caption must survive.

    The chrome rows are stable AND centred, so neither the temporal gate nor
    the centring veto can be what stops them -- only the chrome rule can.
    """
    fails = []
    chrome_seen = []
    for label, got, _trace in results:
        want = None
        for kind, ctext in CHROME_TEXT.items():
            if kind in label:
                want = ctext
                break
        for t in line_texts(got):
            if want and (want in t or t.strip() == want):
                chrome_seen.append("%s: %r" % (label, t))
        for t in line_texts(got):
            if t.strip() in CHROME_TEXT.values():
                chrome_seen.append("%s: %r" % (label, t))
    if chrome_seen:
        fails.append("CHROME REACHED THE CAPTION: %s" % (chrome_seen[:6],))
    if with_caption_results is not None:
        survived = False
        for label, got, _trace in with_caption_results:
            texts = line_texts(got)
            if any("Akali" in t for t in texts):
                survived = True
            for t in texts:
                if t.strip() in CHROME_TEXT.values():
                    fails.append("chrome took the row next to a caption: %r" % (t,))
        if not survived:
            fails.append("the real caption did NOT survive next to the chrome")
    return fails


def check_chrome_negative(results):
    """The chrome MUST appear here, or the oracle cannot say no."""
    leaked = []
    for label, got, _trace in results:
        for t in line_texts(got):
            if t.strip() in CHROME_TEXT.values():
                leaked.append("%s: %r" % (label, t))
    if not leaked:
        return ["NEGATIVE ARM (chrome rule removed) PRODUCED NO CHROME -> "
                "the oracle cannot say no"]
    return []


def check_entrypoints(mod):
    """The player gate must be untouched: Stremio in, URL in, browser out."""
    fails = []
    els = (caption_row("c1m") + caption_row("c2m")
           + [_El("AKALI BROTHERS - FULL MOVIE", (0, 100, 1920, 1000), 50004)])

    def source_for(title, proc, extra=()):
        mod._window_title = lambda h, t=title: t
        mod._process_name = lambda h, p=proc: p
        mod._RUNS.clear()
        got = []
        # Two polls: the first is PENDING by design, the second confirms.
        for _ in range(2):
            got = mod.caption_lines(HWND, _Uia(list(els) + list(extra)), _UIA, [])
        return got[0][0] if got else None

    if source_for("Stremio 1.0", "stremio.exe") != "external:stremio":
        fails.append("stremio title/proc no longer detected")
    if source_for("algo nao laco - YouTube", "chrome.exe") != "external:youtube":
        fails.append("youtube title no longer detected")
    bar = _EditEl("Address and search bar", (0, 0, 800, 30),
                  "https://www.youtube.com/watch?v=aqz-KE-bpKQ")
    if source_for("sem titulo nenhum", "chrome.exe", [bar]) != "external:youtube":
        fails.append("youtube URL no longer detected")
    # The generic-browser fallback must NOT come back: an unrecognised window
    # with a caption-looking Text element at the bottom claims nothing.
    if source_for("algum site qualquer", "chrome.exe") is not None:
        fails.append("an unrecognised window is being claimed again")
    return fails


def main(argv=None):
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--arms", default="live,nogate")
    ap.add_argument("--no-chrome", action="store_true",
                    help="skip the chrome scenario")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    with open(TARGET, "r", encoding="utf-8") as fh:
        src = fh.read()
    if "_CONFIRM_POLLS" not in src:
        print("VERDICT: FAIL -- target has no stability gate; this oracle is stale")
        return 1

    failures = []
    tmp = tempfile.mkdtemp(prefix="extsubs-oracle-")
    live = load_module(TARGET, "extsubs_live")
    results = run_polls(live, args.verbose and "live" in arms)
    if "live" in arms:
        fails, two_line = check_live(results)
        entry = check_entrypoints(live)
        fails = fails + entry
        print("ARM live")
        print("   two-line caption: %r" % (two_line[1] if two_line else None))
        print("   player gate: stremio/youtube-title/youtube-url=%s generic-browser=%s"
              % ("OK" if not entry else "RED", "refused" if not entry else "RED"))
        print("   emitted per poll: %s"
              % [line_texts(g) for _l, g, _t in results])
        for f in fails:
            print("   RED %s" % f)
        failures += ["live: " + f for f in fails]

    for arm, source in (("nogate", _mutate_gate(src)), ("head", _head_source())):
        if arm not in arms:
            continue
        if source is None:
            print("ARM %s  SKIPPED (no git HEAD copy of the pre-fix module)" % arm)
            continue
        if source == src:
            # The HEAD copy IS the working copy: there is nothing to compare
            # against, and pretending otherwise would make this arm rot in
            # silence the day the fix is committed. The `nogate` arm is the
            # one that says no.
            print("ARM %s  SKIPPED (HEAD is the working copy -- nothing to "
                  "compare; the `nogate` arm is the negative one)" % arm)
            continue
        path = os.path.join(tmp, "extsubs_%s.py" % arm)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(source)
        res = run_polls(load_module(path, "extsubs_%s" % arm), args.verbose)
        fails = check_negative(res, arm)
        noise = [t for _l, g, _t in res for t in line_texts(g)
                 if any(n in t for n in NOISE)]
        print("ARM %s" % arm)
        print("   noise that reached the output: %d line(s) %s"
              % (len(noise), noise[:4]))
        for f in fails:
            print("   RED %s" % f)
        failures += fails

    # --- THE CHROME SCENARIO: the real noise out of the owner's own log ----
    if not args.no_chrome:
        # A FRESH module instance: `check_entrypoints` above leaves the
        # window title stubbed as an UNRECOGNISED window ("algum site
        # qualquer"), and with that stub the player gate refuses the window
        # and every caption comes back empty. A scenario must not inherit
        # another scenario's stubs.
        chrome_mod = load_module(TARGET, "extsubs_chrome")
        chrome_res = run_polls(chrome_mod, args.verbose, POLLS_CHROME())
        chrome_mod._RUNS.clear()
        cap_res = run_polls(chrome_mod, args.verbose, POLLS_CHROME_WITH_CAPTION())
        cfails = check_chrome(chrome_res, cap_res)
        print("ARM chrome")
        print("   chrome rows tried: %d   output lines produced: %d"
              % (len(CHROME_ROWS),
                 sum(len(line_texts(g)) for _l, g, _t in chrome_res)))
        print("   a real caption beside the chrome: %r"
              % ([line_texts(g) for _l, g, _t in cap_res],))
        for f in cfails:
            print("   RED %s" % f)
        failures += ["chrome: " + f for f in cfails]

        path2 = os.path.join(tmp, "extsubs_nochrome.py")
        with open(path2, "w", encoding="utf-8", newline="") as fh:
            fh.write(_mutate_chrome(src))
        broken = load_module(path2, "extsubs_nochrome")
        broken._RUNS.clear()
        nres = run_polls(broken, False, POLLS_CHROME())
        nfails = check_chrome_negative(nres)
        leaked = [t for _l, g, _t in nres for t in line_texts(g)
                  if t.strip() in CHROME_TEXT.values()]
        print("ARM nochrome (negative)")
        print("   chrome that reached the output: %d line(s) %s"
              % (len(leaked), leaked[:6]))
        for f in nfails:
            print("   RED %s" % f)
        failures += nfails

    print("VERDICT: %s" % ("PASS" if not failures else "FAIL"))
    for f in failures:
        print("  - %s" % f)
    return 0 if not failures else 1

if __name__ == "__main__":
    sys.exit(main())