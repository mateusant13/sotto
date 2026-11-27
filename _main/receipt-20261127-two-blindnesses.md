# Receipt 2026-11-27 — the two blind readings that froze his screen

Owner complaint (verbatim, ground truth): *"i just opened sotto, went to youtube,
subtitles from youtube worked for like 2 seconds and then froze, when i unpaused
it still did not work"*.

Both defects were found in his own session log (`_main/webview-run.log`,
`SHELL_STARTUP_STAGE` pid 53752 at 2026-11-26 11:45:10). Neither is the 4 Hz loop:
each is **a verdict written too early and read too late**.

## Defect 1 — an empty track list on a booting page became a one-hour verdict

Measured sequence:

|line time|what the log says|
|---|---|
|11:45:11.189|`YOUTUBE_TRACK_ASK why=pending video_id=RaxpCkJgBnQ ready=0 dom_fresh=1.2s`|
|11:45:18.627|`YOUTUBE_TRACK_READY ... state=no-track cues=0 reason=no-tracks-listed cached=False`|
|11:45:49.177|**the same verdict, `cached=True`** — 31 s later|

`ready=0` is `video.readyState == 0`: the element exists with no media yet. The
caption list read at that instant describes the page boot, not the video — and
`NO_TRACK_TTL_S = 3600` stored it as a property of the video for an hour. This is
the class `payload-failed` already fixed on 2026-10-19 (`PAYLOAD_RETRY_TTL_S = 60`,
and `extract-failed` is deliberately never cached): **a transient answer is not a
verdict about the video**.

### The mechanism

`page_ready` travels the whole path and is recorded, never assumed:

- `SottoShell._yt_page_ready()` reads `rs` from the live CDP snapshot
  (`youtube_cdp_source.parse_snapshot` publishes `"rs": data.get("rs")`).
  `True` when `rs > 0`; `False` when `rs == 0`; **`None`** when the source cannot
  answer (no source, no snapshot, `rs` absent or not a number).
- `YoutubeTrackThread.request(video_id, painted=None, page_ready=None)` stores it.
- `YoutubeTrackThread._fetch` passes it to
  `youtube_captions.fetch_track(..., page_ready=...)`.
- `fetch_track` sets `result["transient"] = page_ready is not None and not page_ready`.
- `_ttl_for` returns `NO_TRACK_TRANSIENT_TTL_S = 20` for `transient`, keeps
  `NO_TRACK_TTL_S = 3600` for a real verdict, and `page_ready=None` keeps the old
  behaviour — **an unmeasured readiness is never a verdict**.

The stall-ask path (`_yt_paint_stall`, where `snap` is already in hand) passes the
same readiness off the snapshot it just used, so no second CDP read is paid.

### Gate

`_main/youtube-captions-oracle.py`, arm `a65`, three readiness values through the
**real** `_ttl_for` and the real cache, with three distinct video ids so each is a
real fetch (a reused id answers from cache and the third line never executes — the
arm's own first draft measured the cache instead of the rule; the arm now asserts
`not cached` on all three).

Mutants (`--neg-arm`):

- `a-transient-empty-list-becomes-a-verdict` — removing the short-TTL branch.
- `an-unknown-readiness-loses-the-long-ttl` — `transient = not page_ready`, which
  turns an unknown readiness into a verdict.

Result: `VERDICT: PASS arms 67/67 mutants 20/20`, rc 0; `--neg-arm` rc 1.

## Defect 2 — the shell mirror carried the raw pause flag, not the proven pause

`youtube_clock.pause_proven(clock_static, clock_moving, photo_fresh)` is the single
owner of the rule and the site's own comment mandates it: *"A PAUSA QUE APAGA E'
A PROVADA, e so' ela (2026-11-16)"*. `_now_paused = bool(_paused_proven)` was
computed correctly — and the mirror was assigned the raw flag:

```
shell.yt_source_paused = self.yt_cdp_paused
```

Two consumers read that mirror: `external_caption` refuses pixels while it is
true, and `_caption_idle_hide` blanks on it. Measured in the same session:

- 11:46:32.634 `CAPTION_WINDOW_BLANKED reason=video-changed`;
- the tab went `dead-tab` (`YOUTUBE_SNAPSHOT_STALE ... note=dead-tab (1WnKCj1_5rI)`),
  `t` stopped arriving, `yt_cdp_paused` stayed `True` with no proof at all;
- 11:46:44.747 `CAPTION_WINDOW_BLANKED reason=youtube-paused-or-ended` — the screen
  stayed empty **84 s** while the track held **667 cues**;
- 11:48:08.370 the first frame of the new video, `RESUMED pause_s=90.4`.

This is the exact defect class the module docstring already records
(`t` read `True` and never read `False` again). The cure is the one witness:

```
shell.yt_source_paused = bool(_now_paused)
```

### Gate

`_main/yt-pause-disagreement-oracle.py`, arm `b-ligacao`, which now **refuses the
raw form by name** (`yt_source_paused = self.yt_cdp_paused` via regex) and
**requires the proven form** (`yt_source_paused = bool(_now_paused)`); both
directions, so neither a silent revert nor a silent rewrite passes.

Mutant `b-espelho` reintroduces the raw assignment. Mutant count corrected 9 → 10
in the tally.

Result: `YT-PAUSE-DISAGREEMENT VERDICT: GREEN (5 arms)` rc 0; `--neg-arm`
`NEG-ARM VERDICT: PASS` (10/10 CAUGHT) rc 1; `--log _main/webview-run.log` →
`families=PROVEN=27 DISAGREED=20 UNWITNESSED=28 BLANK_DEFERRED=1`,
`YT-PAUSE-LOG VERDICT: CLEAN` rc 0.

## The fakes that had to follow the signature

Adding `page_ready=` to the live shell's call sites broke three oracles whose
`FakeThread.request` still had the old signature — and the breakage was **inside
the tick**, so the arm measured the stub, not the law:

|oracle|before|after|
|---|---|---|
|`youtube-track-wiring-oracle`|`arms 5/12` rc 1|`arms 12/12 mutants 5/5` rc 0|
|`youtube-hidden-clock-oracle`|`RED -- 11 PASS / 1 FAIL` rc 1 (`A9` saw 0 asks in 745 ticks)|`GREEN -- 12 PASS / 0 FAIL` rc 0|
|`youtube-foreign-paint-oracle`|`VERDICT FAIL (4)` rc 2, `TypeError` per tick|`VERDICT PASS` rc 0|

All three fakes now accept `page_ready=None`. The three frozen shell copies
(`_panel-clear-lifted-mutant.py`, `_panel-verdict-benign-mutant.py`,
`_restart-30s-prefix-mutant.py`) are deliberate RED fixtures and stay as they are:
their call site and their method carry the same old signature, so they remain
internally consistent.

## Verification run

```
_main/youtube-captions-oracle.py            67/67 arms, 20/20 mutants, rc 0
_main/youtube-captions-oracle.py --neg-arm  rc 1
_main/yt-pause-disagreement-oracle.py       GREEN (5 arms), rc 0
_main/yt-pause-disagreement-oracle.py --neg-arm  PASS, rc 1
_main/yt-pause-disagreement-oracle.py --log  CLEAN, rc 0
_main/battery-launch.py --verify            VERIFY: PASS (pins/wiring/pairing/class/undefined-names)
_main/dead-unwired-oracle.py                PASS (arms=4 fail=0)
_main/multi-monitor-oracle.py               PASS
_main/claims-date-oracle.py                 PASS checks=4 fail=0
_main/_gitattributes-verify.py              PASS, 0 divergent
_main/agents-md-pins-oracle.py              PASS, 2 pins, 0 failures
_main/yt-lane-session-oracle.py              PASS, rc 0 (network arm a named HOLE)
_main/yt-lane-session-oracle.py --neg-arm    NEG-ARM: PASS -- 3/3, rc 1
_main/yt-lane-session.py --video ... --port 9340  LANE-YT FAIL why=teardown-leak -> gone after the drain
_main/youtube-paint-first-oracle.py          PASS, rc 0 / NEG-ARM PASS, rc 1
```

EOL after the edits: `app/webview/sotto_webview.py` **1 543 481 B, 28 378 CRLF /
0 bare LF**; `app/webview/youtube_captions.py` LF only; every `_main/*.py` touched
stays LF.

## Status

`fixed, NOT verified`. The owner's loaded instance predates this tree
(`_main/live-code-freshness-oracle.py` still names pid 53752 @ 2026-11-26 11:45:10),
so the two fixes are `UNMEASURED` at the product until he restarts Sotto. What a
lane can prove — the rule, the wiring, both directions, and the whole
YouTube-oracle family — is proven above.

## Defect 3 — a killed process is not a gone process (found by the family sweep)

The first full sweep of the 41 YouTube-family oracles showed `yt-lane-session-oracle`
red with `rc=1 (expected 0 with playback or 3 with a named refusal)`. The instrument
itself had already named the real defect:

```
LANE-YT teardown pid=35388 exited=1 lane_chrome_left=3 profile_removed=1
LANE-YT FAIL why=teardown-leak survivors=18228,29708,32588
```

Those three pids were **`NoSuchProcess` seconds later**, measured directly with
`psutil.Process(pid)`. `terminate()`/`kill()` returns before the kernel reaps, and
`teardown()` re-scanned `profile_pids()` in the same breath — so a reap in flight was
reported as a leak and **failed the whole oracle**, hiding three green arms behind it.

### The mechanism

`_main/yt-lane-session.py`: `TEARDOWN_DRAIN_S = 3.0`, `TEARDOWN_DRAIN_TICK_S = 0.1`,
and the survivor re-scan is repeated while it is non-empty and the window has not
closed. The window is small on purpose: a real survivor is still there after 3 s, so
a leak still fails — it simply is not confused with the reap.

### The second half: the oracle could not read its own instrument

`_main/yt-lane-session-oracle.py` judged only `rc`, and `yt-lane-session.py` answers
rc 0 even when its own line says `LANE-YT FAIL why=...`. The arm now has an `rc == 1`
branch that accepts a **named** defect line (`why=` present) and still refuses a
bare one.

Result: `VERDICT: PASS` rc 0, with the network arm honestly named
`HOLE real-chrome-signed-out: why=player-not-decided ... why=not-playing delta_ms=195
readyState=4` — the bench did not load media, so the pure arms judged the instrument
and the network half is a HOLE, never a PASS. `--neg-arm`: `NEG-ARM: PASS -- 3/3`,
rc 1.

## The lesson, stated for the next reader

A cached value is an assertion about the instant it was measured, and a TTL is the
assertion about how long that assertion holds. A long TTL is justified only when the
thing measured is a property of the **object** (this video has these cues), never
when it is a property of the **attempt** (this page answered this now).
