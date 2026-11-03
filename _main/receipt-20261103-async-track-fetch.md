# Receipt — the track fetch is asynchronous (2026-11-03)

Lane: `AsyncTrackFetch`. Repo `H:/sotto`. Files owned: `app/webview/sotto_webview.py`
(`YouTubeTrackThread.request/current/_fetch`, the `_youtube` call site) and
`app/webview/youtube_captions.py` (`fetch_track`).

Nothing was relaunched, killed, or shown; `_main/webview-run.log` was not written;
no synthetic input was sent. The live app the owner is watching was untouched.

## 1. What the log said, and what the marks say

Ground truth (owner's live log): `EXTERNAL_CAPTIONS_READ_MS ms=46766.0
phases={'target': 0.0, 'source': 0.0}` at 02:45:11 and `ms=62234.0` at 02:46:14,
each followed by `YOUTUBE_TRACK_READY ... cues=1083`.

MEASURED, and it qualifies the attribution: with the two named phases both at
0.0 ms, the 46 s sits between `_yt_mark(self, 'source')` and
`_yt_mark(self, 'vid')` — i.e. inside `_youtube_video_id` (the UIA `edit_values`
scan, the cost `_yt_vid_cache` already addresses), not in the loop-side call to
the track thread. Checked directly against the committed revision: `git show
HEAD:app/webview/sotto_webview.py`, real `YouTubeTrackThread`, fetcher sleeping
5 s:

```
HEAD request  ms=0.0082  -> None
HEAD current  ms=0.0020  -> None
HEAD fetch reached: [('aaaaaaaaaaa', 'sotto-yt-track')]
```

So the loop never called `fetch_track` even before this lane (the only caller is
`YouTubeTrackThread._fetch`, on `sotto-yt-track`). What this lane delivers is
the rest of the property: the loop-side path is now the ONLY path into that
thread, it can never fetch, and three real defects around the async boundary are
gone — with numbers, below.

## 2. Changes

### `app/webview/sotto_webview.py`

| file:line | change |
|---|---|
| `sotto_webview.py:1934-1946` | `YouTubeTrackThread.__init__`: `paint_key` / `paint_key_for` (the QUESTION last asked), `polls` / `ask_slow_at` (the loop-side cost, as a number), `dropped` (fetches superseded). |
| `sotto_webview.py:1948-1953` | `_paint_key()` — the painted words as one key. |
| `sotto_webview.py:1955-2013` | `request()` — fire-and-forget, never calls `fetch_track`, never waits; returns a finished track or `None`; same video + same words is NOT a new question (the old rule re-armed on the clock, so the same video was re-extracted every `PAINT_SEARCH_RETRY_S`); logs `YOUTUBE_TRACK_ASK_MS` when a loop-side ask costs more than 5 ms. |
| `sotto_webview.py:2045-2076` | `_fetch()` completion — a result for a video nobody asks about anymore is DROPPED (`YOUTUBE_TRACK_DROPPED`) and does not publish `track`/`track_for`; it does not arm the 30 s `REFRESH_S` window, so the NEW video is fetched immediately instead of waiting behind it. |
| `sotto_webview.py:3031-3035` | `ExternalCaptionWatcher.DOM_FRESH_S = 1.2`. |
| `sotto_webview.py:3037-3063` | `_yt_dom_is_source()` — the freshness signal: the CDP snapshot's OWN `stamp`, within the same 1.2 s the read already uses, AND the snapshot carries rows. A fresh snapshot with NO rows is NOT a source (a video without captions must still ask, or `no-track` never reaches the ASR release). |
| `sotto_webview.py:3065-3081` | `_yt_track_poll()` — the single entry from the caption loop into the track thread: DOM primary (no request at all), never blocking, with `YOUTUBE_TRACK_ASK why=` written once per change. |
| `sotto_webview.py:3273` | `_youtube` calls `self._yt_track_poll(thread, vid, painted)` instead of `thread.request(...)` + `thread.current(...)`; the old `yt_live_paint_at >= 2.0` proxy is gone from this decision. |

### `app/webview/youtube_captions.py`

**No code change, and that is deliberate.** `fetch_track` already documents "The
first call for a video is a network call and takes ~5 s (MEASURED); every later
call is a disk read. Call it OFF the UI thread", and it is now called from
exactly one place — `YouTubeTrackThread._fetch`, on `sotto-yt-track` (asserted by
the oracle's STRUCT arm: one `fetch_track(` call site in the shell, at
`sotto_webview.py:2042`). Adding a lock or a sentinel inside `fetch_track` would
put a wait back on whoever calls it, which is the defect this lane removes.

## 3. Before / after, measured

Loop-side cost of the ask, fetcher sleeping 5 s (oracle, `perf_counter_ns`):

| | before (HEAD, measured) | after (working tree, measured) |
|---|---|---|
| `request()` with a 5 s fetch in flight | 0.008 ms (already async) | **0.025 ms** |
| worst of 200 further asks | — | **1.846 ms** (budget 50 ms) |
| reading a finished track | 0.002 ms | **0.031 ms** |
| same video, same words, 0.7 s, retry window 0.2 s | **4 fetches** | **1 fetch** |
| old video's fetch landing after the owner switched videos | window armed **30.0 s**, old result PUBLISHED for the old video, new video not fetched within 0.8 s | result **dropped**, window **0.0 s**, new video fetched **0.03 s** after |
| DOM delivering rows | request still armed by the `yt_live_paint_at` proxy | **0 requests** |
| DOM fresh but NO rows (video without captions) | n/a | **asks** — the ASR fallback stays alive |
| tick cost of the block named in the ticket | 46 766 ms / 62 234 ms in the owner's log | cannot recur through this path: the loop does not fetch (STRUCT arm) |

## 4. Oracle

`_main/async-track-fetch-oracle.py` — imports the REAL `sotto_webview.py`
headless, builds the REAL `YouTubeTrackThread` and `ExternalCaptionWatcher`,
injects `youtube_captions.fetch_track` sleeping 5 s. 7 arms: ASYNC, READY,
SUPERSEDE, DOM (3 sub-arms), DEDUPE, DEDUPE-TTL, STRUCT.

### `py -3 _main/async-track-fetch-oracle.py`

```
shell : H:\sotto\app\webview\sotto_webview.py
bytes : 888962
  STRUCT  fetch_track( call sites in the shell: 1 [2042]
  ASYNC   ask with a 5 s fetch in flight: 0.025 ms
  ASYNC   200 further asks: worst 1.846 ms; fetch_track ran 1 time(s), on ['sotto-yt-track']
  READY   finished track handed back in 0.031 ms, state=has-track
  SUPER   B dropped=1, served='ccccccccccc', C fetched 0.03 s after B would have finished, C served=True
  DOM     fresh+rows: 0.024 ms, 0 fetch(es) for ddddddddddd (must be 0)
  DOM     fresh no rows: asked=True (the ASR fallback depends on it)
  DOM     stale rows: asked=True
  DEDUPE  66 asks over 0.7 s (retry window 0.2 s, SAME words): 1 fetch(es)
VERDICT: PASS
EXIT=0
```

### `py -3 _main/async-track-fetch-oracle.py --neg-arm`

The mutant writes a copy of the shell with `self._fetch(vid)` inserted directly
after the `key = self._paint_key(painted)` line of `request` — the fetch put back
on the caller, which is the regression the ticket describes.

```
shell : H:\sotto\app\webview\sotto_webview.py
bytes : 888962
mutant: H:\sotto\app\webview\_async-track-neg-shell.py (872289 B, the fetch put back on the caller)
NEG-ARM: RED as expected
  STRUCT  fetch_track( call sites in the shell: 1 [2043]
  ASYNC   ask with a 5 s fetch in flight: 5000.510 ms
  READY   finished track handed back in 0.055 ms, state=has-track
  SUPER   B dropped=2, served='ccccccccccc', C fetched 0.00 s after B would have finished, C served=True
  DOM     fresh+rows: 0.029 ms, 0 fetch(es) for ddddddddddd (must be 0)
  DOM     fresh no rows: asked=True (the ASR fallback depends on it)
  DOM     stale rows: asked=True
  DEDUPE  66 asks over 0.7 s (retry window 0.2 s, SAME words): 66 fetch(es)
   STRUCT: YouTubeTrackThread.request can fetch -- it is the loop-side call
   ASYNC: the ask returned in 5000.5 ms with a 5 s fetch in flight (budget 50 ms) -- the loop paid the fetch
   DEDUPE: a finished track was fetched again (3 fetches)
   SUPERSEDE: asking for B took 2000.4 ms
   DEDUPE-TTL: the same video with the SAME painted words ran 66 fetches -- the clock was read as a new question
EXIT=0
```

The mutant is removed by the oracle after the run (`app/webview/_async-track-neg-shell.py`
does not survive; checked).

## 5. What the oracle cannot say

* It does not drive `_youtube` end to end: that needs a live Chrome, a UIA tree
  and a CDP port, and the owner is watching a video on the live app. What it
  exercises is the exact decision function `_youtube` calls
  (`_yt_track_poll`) plus the real thread behind it; the STRUCT arm pins that
  `_youtube` has no other route into the thread.
* The 46 s/62 s tick itself was not reproduced in a live app (that would need a
  relaunch). The measured gap between the `source` and `vid` marks says the
  remaining cost of that tick is the UIA video-id scan, not this path.

## 6. sha256 of every changed file

```
a7162abf2f005be64c0f28d2d186236ffc1191364430c7f15cce4fe38a82dc37  app/webview/sotto_webview.py
b15efe51ac010220a5be788930c01399fab898d0af16b69ce18b09d46eb95451  _main/async-track-fetch-oracle.py
f01de00091291d139286f1426e8c06920f97a6d33ae31f11263e911b4fd6f113  app/webview/youtube_captions.py  (unchanged, listed for the record)
```
