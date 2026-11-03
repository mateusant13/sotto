"""Oracle: the caption loop NEVER waits for the YouTube track fetch.

INSTRUMENT, IN PROCESS. It imports app/webview/sotto_webview.py (headless: no
window, no worker, no WebView2), builds the REAL `YouTubeTrackThread` and the
REAL `ExternalCaptionWatcher`, and injects a fetcher that SLEEPS 5 s. The two
calls the caption loop makes are the ones measured:

  * `YouTubeTrackThread.request(vid, painted=...)` -- the ask;
  * `ExternalCaptionWatcher._yt_track_poll(thread, vid, painted)` -- the ask,
    with the DOM-primary decision in front of it (`_youtube` calls only this).

THE CLAIM, from the owner's own log (`_main/webview-run.log`, 2026-11-03):
`EXTERNAL_CAPTIONS_READ_MS ms=46766.0 phases={'target': 0.0, 'source': 0.0}`
immediately followed by `YOUTUBE_TRACK_READY video_id=... cues=1083`, and again
`ms=62234.0`. A tick that costs 46 s while its two cheap phases are both named
is the `yt-dlp` of the track running INSIDE the caption loop.

ARMS
  1. ASYNC    -- with a 5 s fetch in flight, the loop call returns in < 50 ms,
                 and the fetch IS running (on another thread) -- so the arm
                 proves "moved", not "removed";
  2. DEDUPE   -- the same video with the same painted words is asked once;
  3. READY    -- a finished track is handed to the loop without any wait;
  4. SUPERSEDE-- a new video does not wait behind the old fetch and does not
                 inherit its result;
  5. DOM      -- a fresh CDP snapshot WITH rows: the track is not requested at
                 all; a fresh snapshot WITH NO rows still requests it (a video
                 without captions must keep falling back to the ASR);
  6. STRUCT   -- the real source: `fetch_track` has exactly one caller, and it
                 is `YouTubeTrackThread._fetch`, never the loop.

Usage:
  py -3 _main/async-track-fetch-oracle.py             # the working tree
  py -3 _main/async-track-fetch-oracle.py --neg-arm   # the fetch put back on
                                                      # the caller -> must be RED
"""
import argparse
import importlib.util
import inspect
import os
import sys
import threading
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
MUTANT = os.path.join(os.path.dirname(SHELL), '_async-track-neg-shell.py')

#: The one line the neg arm appends to: the ask, before it touches any state.
ANCHOR = "        key = self._paint_key(painted)\n"
INJECT = "        self._fetch(vid)          # MUTANT: the fetch on the caller\n"

#: The loop-side budget. One tick of the caption loop is the caption's latency;
#: a lock, a dict read and a comparison cost microseconds, so 50 ms is already
#: three orders of magnitude of slack.
BUDGET_MS = 50.0
SLOW_S = 5.0

NOTES = []


def note(fmt, *a):
    NOTES.append(fmt % a if a else fmt)


VID_A, VID_B, VID_C, VID_D, VID_E, VID_F = (
    'aaaaaaaaaaa', 'bbbbbbbbbbb', 'ccccccccccc', 'ddddddddddd', 'eeeeeeeeeee',
    'fffffffffff')
PAINT = ['hello', 'world']


def load_shell(path, name):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Fetcher:
    """The injected `youtube_captions.fetch_track`: records, and can sleep."""

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = []          # (video_id, thread name, monotonic)
        self.delays = {}         # video_id -> seconds

    def __call__(self, video_id, **kwargs):
        with self.lock:
            self.calls.append((video_id, threading.current_thread().name,
                               time.monotonic()))
            delay = self.delays.get(video_id, 0.0)
        if delay:
            time.sleep(delay)
        return {'state': 'has-track', 'cues': [{'start': 0.0, 'end': 1.0,
                                                'text': ' '.join(PAINT)}],
                'lang': 'en', 'source': 'oracle', 'reason': None, 'error': None,
                'cached': False, 'video_id': video_id}

    def count(self, video_id=None):
        with self.lock:
            if video_id is None:
                return len(self.calls)
            return sum(1 for c in self.calls if c[0] == video_id)

    def names(self, video_id=None):
        with self.lock:
            return [c[1] for c in self.calls
                    if video_id is None or c[0] == video_id]

    def first_at(self, video_id):
        with self.lock:
            for vid, _name, at in self.calls:
                if vid == video_id:
                    return at
        return None


class FakeCdp:
    """Stands in for `youtube_cdp_source.CdpCaptionSource`: snapshot only."""

    def __init__(self, rows, age=0.0):
        self.rows = list(rows)
        self.stamp = time.monotonic() - age

    def snapshot(self, max_age=0.6):
        if time.monotonic() - self.stamp > max_age:
            return None
        return {'rows': list(self.rows), 'items': [], 'stamp': self.stamp,
                'videoId': 'whatever'}


def timed(fn):
    """(milliseconds, value). `perf_counter_ns` so a microsecond is a number.

    The loop side of the ask is a lock, a dict read, a string join and a
    comparison -- with `monotonic` alone it reads 0.000 ms and proves nothing.
    """
    t0 = time.perf_counter_ns()
    value = fn()
    return (time.perf_counter_ns() - t0) / 1e6, value


def wait_until(pred, timeout, step=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(step)
    return pred()


def arm_async(mod, fetcher, failures):
    """ARM 1 + 2: the ask while a 5 s fetch is in flight."""
    shell = SimpleNamespace()
    thread = mod.YouTubeTrackThread(shell)
    thread.POLL_S = 0.02
    thread.start()
    fetcher.delays[VID_A] = SLOW_S
    try:
        ms, got = timed(lambda: thread.request(VID_A, painted=PAINT))
        note('ASYNC   ask with a %.0f s fetch in flight: %.3f ms', SLOW_S, ms)
        if ms >= BUDGET_MS:
            failures.append('ASYNC: the ask returned in %.1f ms with a %.0f s fetch '
                            'in flight (budget %.0f ms) -- the loop paid the fetch'
                            % (ms, SLOW_S, BUDGET_MS))
            # The claim is already refuted, and a regression that fetches on the
            # caller would pay `SLOW_S` on every one of the 200 asks below: the
            # control stops here instead of hanging for a quarter of an hour.
            return thread
        if got is not None:
            failures.append('ASYNC: an unfinished video answered with %r' % (got,))
        # The fetch must ACTUALLY be running, or "fast" would just mean "never".
        if not wait_until(lambda: fetcher.count(VID_A) >= 1, 2.0):
            failures.append('ASYNC: the ask never reached fetch_track -- the arm '
                            'would pass with the fetch REMOVED, which is not the cure')
        else:
            names = fetcher.names(VID_A)
            if any(n == threading.current_thread().name for n in names):
                failures.append('ASYNC: fetch_track ran on the CALLER thread (%s)'
                                % names[:1])
        # 200 more asks during the same in-flight fetch: still no wait, and no
        # second fetch (the same video with the same words is the same question).
        worst = 0.0
        for _ in range(200):
            ms, _ = timed(lambda: thread.request(VID_A, painted=PAINT))
            worst = max(worst, ms)
        if worst >= BUDGET_MS:
            failures.append('ASYNC: a repeated ask took %.1f ms (budget %.0f ms)'
                            % (worst, BUDGET_MS))
        note('ASYNC   200 further asks: worst %.3f ms; fetch_track ran %d time(s), '
             'on %s', worst, fetcher.count(VID_A), fetcher.names(VID_A)[:1])
        if fetcher.count(VID_A) != 1:
            failures.append('DEDUPE: 202 asks for the same video ran %d fetches'
                            % fetcher.count(VID_A))
        # ARM 3 runs while the fetch is still in flight: the result is not here.
        ms, ready = timed(lambda: thread.current(VID_A))
        if ms >= BUDGET_MS:
            failures.append('READY: reading a pending track took %.1f ms' % ms)
        if ready is not None:
            failures.append('READY: a pending track was returned as finished')
    finally:
        fetcher.delays.pop(VID_A, None)
    return thread


def arm_ready(mod, thread, fetcher, failures):
    """ARM 3: when the fetch lands, the loop reads it without any wait."""
    if not wait_until(lambda: thread.current(VID_A) is not None, SLOW_S + 5.0):
        failures.append('READY: the 5 s fetch never landed for %s' % VID_A)
        return
    ms, track = timed(lambda: thread.request(VID_A, painted=PAINT))
    note('READY   finished track handed back in %.3f ms, state=%s',
         ms, (track or {}).get('state'))
    if ms >= BUDGET_MS:
        failures.append('READY: reading the finished track took %.1f ms' % ms)
    if not track or track.get('state') != 'has-track':
        failures.append('READY: the finished track was not handed to the loop: %r'
                        % (track,))
    if fetcher.count(VID_A) != 1:
        failures.append('DEDUPE: a finished track was fetched again (%d fetches)'
                        % fetcher.count(VID_A))


def arm_supersede(mod, fetcher, failures):
    """ARM 4: a new video neither waits behind the old fetch nor inherits it."""
    thread = mod.YouTubeTrackThread(SimpleNamespace())
    thread.POLL_S = 0.02
    thread.start()
    fetcher.delays[VID_B] = 2.0
    try:
        ms, _ = timed(lambda: thread.request(VID_B, painted=PAINT))
        if ms >= BUDGET_MS:
            failures.append('SUPERSEDE: asking for B took %.1f ms' % ms)
        if not wait_until(lambda: fetcher.count(VID_B) >= 1, 2.0):
            failures.append('SUPERSEDE: B was never fetched')
        # While B sleeps, the owner switches to C.
        ms, _ = timed(lambda: thread.request(VID_C, painted=PAINT))
        if ms >= BUDGET_MS:
            failures.append('SUPERSEDE: the switch to C took %.1f ms' % ms)
        if thread.current(VID_C) is not None:
            failures.append('SUPERSEDE: C answered with a track nobody fetched')
        if not wait_until(lambda: thread.current(VID_B) is not None
                          or getattr(thread, 'dropped', 0) >= 1, 3.0):
            failures.append('SUPERSEDE: B neither landed nor was dropped')
        if getattr(thread, 'dropped', 0) < 1:
            failures.append('SUPERSEDE: B\'s result was PUBLISHED after the owner '
                            'moved to C (dropped=%d)' % getattr(thread, 'dropped', 0))
        if thread.current(VID_B) is not None:
            failures.append('SUPERSEDE: the old video\'s track is still served')
        # C must be fetched NOW, not one REFRESH_S window later.
        t_b = fetcher.first_at(VID_B)
        if not wait_until(lambda: fetcher.count(VID_C) >= 1, 2.0):
            failures.append('SUPERSEDE: C was NOT fetched within 2 s of B finishing '
                            '(the old fetch armed the 30 s window)')
        else:
            t_c = fetcher.first_at(VID_C)
            lag = (t_c or 0.0) - (t_b + 2.0 if t_b else 0.0)
            if lag > 2.0:
                failures.append('SUPERSEDE: C waited %.1f s behind B' % lag)
        if not wait_until(lambda: thread.current(VID_C) is not None, 3.0):
            failures.append('SUPERSEDE: C never became the served track')
        note('SUPER   B dropped=%d, served=%r, C fetched %.2f s after B would '
             'have finished, C served=%r',
             getattr(thread, 'dropped', 0), thread.track_for, lag,
             thread.current(VID_C) is not None)
    finally:
        fetcher.delays.pop(VID_B, None)
    return thread


def arm_dom(mod, fetcher, failures):
    """ARM 5: the DOM decides whether the track is asked for at all."""
    watcher = mod.ExternalCaptionWatcher(SimpleNamespace())
    thread = mod.YouTubeTrackThread(SimpleNamespace())
    thread.POLL_S = 0.02
    thread.start()
    try:
        # 5a: a FRESH snapshot WITH rows -- the DOM is the caption; ask nothing.
        watcher._yt_cdp_source = FakeCdp(rows=PAINT, age=0.0)
        before = fetcher.count(VID_D)
        ms, got = timed(lambda: watcher._yt_track_poll(thread, VID_D, PAINT))
        if ms >= BUDGET_MS:
            failures.append('DOM: the poll with a fresh DOM took %.1f ms' % ms)
        if got is not None:
            failures.append('DOM: a track nobody fetched was returned: %r' % (got,))
        time.sleep(0.3)
        if fetcher.count(VID_D) != before:
            failures.append('DOM: the track was FETCHED while the DOM was '
                            'delivering rows (%d new fetch(es))'
                            % (fetcher.count(VID_D) - before))
        note('DOM     fresh+rows: %.3f ms, %d fetch(es) for %s (must be 0)',
             ms, fetcher.count(VID_D) - before, VID_D)
        # 5b: a FRESH snapshot with NO rows -- a video without captions must
        # still ask, or `no-track` never reaches the ASR release.
        watcher._yt_cdp_source = FakeCdp(rows=[], age=0.0)
        before = fetcher.count(VID_D)
        ms, _ = timed(lambda: watcher._yt_track_poll(thread, VID_D, PAINT))
        if ms >= BUDGET_MS:
            failures.append('DOM: the poll with an empty DOM took %.1f ms' % ms)
        if not wait_until(lambda: fetcher.count(VID_D) > before, 2.0):
            failures.append('DOM: a video with NO DOM rows was never asked for its '
                            'track -- the ASR fallback is dead')
        note('DOM     fresh no rows: asked=%s (the ASR fallback depends on it)',
             fetcher.count(VID_D) > before)
        # 5c: a STALE snapshot -- not a source either.
        watcher._yt_cdp_source = FakeCdp(rows=PAINT, age=watcher.DOM_FRESH_S + 4.0)
        before = fetcher.count(VID_E)
        watcher._yt_track_poll(thread, VID_E, PAINT)
        if not wait_until(lambda: fetcher.count(VID_E) > before, 2.0):
            failures.append('DOM: a stale snapshot suppressed the ask entirely')
        note('DOM     stale rows: asked=%s', fetcher.count(VID_E) > before)
    finally:
        thread.POLL_S = 0.02
    return watcher


def arm_dedupe_ttl(mod, fetcher, failures):
    """ARM 2b: the SAME words are not a new question, however long you wait.

    The retry window is shortened to 0.2 s so a 0.7 s run covers several of
    them. A retry gate that re-arms on the CLOCK (the old rule) asks again
    every window even though the painted words never changed -- 5 s of `yt-dlp`
    per video for an answer already on disk.
    """
    thread = mod.YouTubeTrackThread(SimpleNamespace())
    thread.POLL_S = 0.02
    thread.PAINT_SEARCH_RETRY_S = 0.2
    thread.start()
    before = fetcher.count(VID_F)
    deadline = time.monotonic() + 0.7
    asks = 0
    while time.monotonic() < deadline:
        thread.request(VID_F, painted=PAINT)
        asks += 1
        time.sleep(0.01)
    time.sleep(0.1)
    runs = fetcher.count(VID_F) - before
    note('DEDUPE  %d asks over 0.7 s (retry window 0.2 s, SAME words): %d fetch(es)',
         asks, runs)
    if runs != 1:
        failures.append('DEDUPE-TTL: the same video with the SAME painted words ran '
                        '%d fetches -- the clock was read as a new question' % runs)


def arm_struct(mod, failures):
    """ARM 6: the real source says who may call fetch_track."""
    source = inspect.getsource(mod)
    hits = [i + 1 for i, line in enumerate(source.splitlines())
            if 'fetch_track(' in line and not line.lstrip().startswith('#')]
    note('STRUCT  fetch_track( call sites in the shell: %d %s', len(hits), hits)
    if len(hits) != 1:
        failures.append('STRUCT: %d call(s) to fetch_track in the shell (%s); the '
                        'loop must have none' % (len(hits), hits))
    else:
        fetch_line = source.splitlines()[hits[0] - 1]
        if 'youtube_captions.fetch_track(video_id' not in fetch_line:
            failures.append('STRUCT: the only fetch_track call is not the thread\'s: '
                            '%r' % fetch_line.strip())
    loop = inspect.getsource(mod.ExternalCaptionWatcher._youtube)
    if '_yt_track_poll(' not in loop:
        failures.append('STRUCT: _youtube does not go through _yt_track_poll')
    if 'thread.request(' in loop or 'thread.current(' in loop:
        failures.append('STRUCT: _youtube still talks to the track thread directly')
    if 'fetch_track' in loop:
        failures.append('STRUCT: _youtube mentions fetch_track')
    if "urgent=True" not in loop:
        failures.append('STRUCT: the no-track -> ASR release is gone from _youtube')
    ask = inspect.getsource(mod.YouTubeTrackThread.request)
    if 'fetch_track(' in ask or 'self._fetch(' in ask:
        failures.append('STRUCT: YouTubeTrackThread.request can fetch -- it is the '
                        'loop-side call')


def run(mod, fetcher):
    failures = []
    arm_struct(mod, failures)
    thread = arm_async(mod, fetcher, failures)
    arm_ready(mod, thread, fetcher, failures)
    arm_supersede(mod, fetcher, failures)
    arm_dom(mod, fetcher, failures)
    arm_dedupe_ttl(mod, fetcher, failures)
    return failures


def install_fetcher(fetcher):
    directory = os.path.dirname(os.path.abspath(SHELL))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    import youtube_captions
    youtube_captions.fetch_track = fetcher


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()
    print('shell : %s' % SHELL)
    print('bytes : %d' % os.path.getsize(SHELL))
    fetcher = Fetcher()
    install_fetcher(fetcher)

    if args.neg_arm:
        with open(SHELL, encoding='utf-8') as fh:
            text = fh.read()
        if ANCHOR not in text:
            print('NEG-ARM: the ask line was not found -- the control is DEAD')
            return 1
        mutant = text.replace(ANCHOR, ANCHOR + INJECT, 1)
        with open(MUTANT, 'w', encoding='utf-8', newline='') as fh:
            fh.write(mutant)
        print('mutant: %s (%d B, the fetch put back on the caller)'
              % (MUTANT, os.path.getsize(MUTANT)))
        try:
            mod = load_shell(MUTANT, 'sotto_shell_async_mutant')
            mod.log = lambda *a, **k: None
            got = run(mod, fetcher)
        finally:
            try:
                os.remove(MUTANT)
            except OSError:
                pass
        slow = [f for f in got if f.startswith(('ASYNC', 'DEDUPE', 'READY',
                                                'SUPERSEDE', 'DOM'))]
        print('NEG-ARM: %s' % ('PASS' if slow else
                               'FAIL -- STILL GREEN: the oracle cannot say no'))
        for line in NOTES:
            print('  ' + line)
        for line in got:
            print('   ' + line)
        # CONTRATO DA BATERIA (2026-11-03): rc=1 significa "O MUTANTE FOI
        # APANHADO" -- o `:expectred` recusa rc=0 com "the control did NOT go
        # red", e um braco que devolve 0 ao apanhar o defeito nao pode ser
        # declarado como controlo.
        return 1 if slow else 0

    mod = load_shell(SHELL, 'sotto_shell_async_live')
    mod.log = lambda *a, **k: None
    failures = run(mod, fetcher)
    for line in NOTES:
        print('  ' + line)
    for line in failures:
        print('   FAIL ' + line)
    print('VERDICT: ' + ('FAIL' if failures else 'PASS'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
