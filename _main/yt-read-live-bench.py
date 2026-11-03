"""Bench: the REAL caption reader against the REAL Chrome, tick by tick.

WHAT IT MEASURES. `ExternalCaptionWatcher._read()` is the function whose cost IS
the caption's latency: while it runs, nothing on screen changes. This bench runs
it headless -- a stub window instead of the caption overlay -- so it can measure
the reader without putting a single pixel on the owner's screen, and prints
p50/p95/max per tick.

WHY IT EXISTS. The owner's session of 2026-11-03 logged
`EXTERNAL_CAPTIONS_READ_MS ms=46766.0` and `ms=62234.0`, and the same instance
ran at 1.2 Hz where the same Python code, unblocked, ran at 24 Hz. The claim
"the loop is faster now" needs numbers from the same instrument on both builds,
so this bench accepts a `--shell` path and can be pointed at HEAD's file.

THE TWO COUNTERS. `_youtube_video_id` (UIA `edit_values`) and `_youtube_painted`
(UIA word scan) are wrapped, NOT replaced: they are counted and then the real
function runs. A tick that calls them is a tick that could have cost seconds.

Usage:
  py -3 _main/yt-read-live-bench.py --ticks 200
  py -3 _main/yt-read-live-bench.py --shell <copia-do-HEAD> --ticks 200
"""
import argparse
import importlib.util
import os
import statistics
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')


def load_shell(path, name):
    directory = os.path.dirname(os.path.abspath(path))
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class StubShell:
    """Everything `_read` touches on the shell, and nothing that draws."""

    def __init__(self, mod):
        self.log = mod.log
        self.youtube_track_thread = None
        self.painted = []
        self.blanks = 0
        self.yt_source_paused = False
        self.external_caption_calls = 0

    def _blank_caption_window(self, reason):
        self.blanks += 1

    def external_caption(self, *a, **k):
        self.external_caption_calls += 1


def window_title(hwnd):
    import ctypes
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(int(hwnd), buf, 512)
    return buf.value


def find_youtube_window():
    """A janela de topo que diz YouTube no titulo (0 se nao houver)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = window_title(hwnd)
        if 'youtube' in title.lower():
            found.append(int(hwnd))
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shell', default=SHELL)
    ap.add_argument('--ticks', type=int, default=200)
    ap.add_argument('--interval', type=float, default=0.05)
    ap.add_argument('--hwnd', type=int, default=0)
    args = ap.parse_args()

    mod = load_shell(args.shell, '_bench_shell')
    mod.log = lambda *a, **k: None          # silence the app's own log
    shell = StubShell(mod)
    watcher = mod.ExternalCaptionWatcher(shell)
    watcher.shell = shell
    # A JANELA DO PLAYER E' O PONTO DE PARTIDA (senao `_read` sai no
    # `_target_window` vazio e mede nada): procura-se, por titulo, uma janela
    # de topo que diga YouTube, e ela e' injetada como `target_hwnd`.
    hwnd = args.hwnd or find_youtube_window()
    if not hwnd:
        print('SEM JANELA DO YOUTUBE: abre o video (o bench nao inventa alvo)')
        return 3
    watcher.target_hwnd = int(hwnd)
    print('hwnd=%d titulo=%r' % (hwnd, window_title(hwnd)))

    counters = {'vid': 0, 'painted': 0}
    real_vid = watcher._youtube_video_id
    real_painted = watcher._youtube_painted

    def vid(*a, **k):
        counters['vid'] += 1
        return real_vid(*a, **k)

    def painted(*a, **k):
        counters['painted'] += 1
        return real_painted(*a, **k)

    watcher._youtube_video_id = vid
    watcher._youtube_painted = painted

    try:
        import external_subs
        UIA, uia = external_subs._uia()
    except Exception as exc:                # noqa: BLE001
        print('SEM UIA: %r' % (exc,))
        return 2

    samples = []
    for i in range(args.ticks):
        t0 = time.perf_counter()
        try:
            watcher._read(uia, UIA)
        except Exception as exc:            # noqa: BLE001
            print('TICK %d levantou %r' % (i, exc))
        samples.append((time.perf_counter() - t0) * 1000.0)
        time.sleep(args.interval)

    samples.sort()
    def p(q):
        return samples[min(len(samples) - 1, int(len(samples) * q))]

    print('ticks=%d  p50=%.1f ms  p95=%.1f ms  max=%.1f ms  >200ms=%d'
          % (len(samples), p(0.50), p(0.95), samples[-1],
             sum(1 for s in samples if s > 200.0)))
    print('uia_vid=%d uia_painted=%d  (chamadas que podem custar segundos)'
          % (counters['vid'], counters['painted']))
    print('media=%.1f ms  total=%.1f s'
          % (statistics.mean(samples), sum(samples) / 1000.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
