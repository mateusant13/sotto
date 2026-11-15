# YouTube caption toggle vs OUR caption — measurement receipt (2026-11-14)

STATUS: **MEASUREMENT 2026-11-14; CURES LANDED 2026-11-15, proved by the oracles
that already carry the arms.** When this receipt was written the three defects
below were measured and located with no code landed. All three now have a cure in
HEAD, each one measured by a named arm of an existing oracle — no
`youtube-caption-toggle-oracle.py` was ever written, and none is needed: the
falsifiers listed at the end were folded into the oracles that own each seam.

| receipt defect | cure now in HEAD | arm that proves it (measured 2026-11-15) |
|---|---|---|
| hint rows painted as captions (`Inglês` / `Clique em para configurações`) | `youtube_cdp_source` marks the chrome rows and drops them before `rows` is published | `youtube-cdp-source-oracle.py` `janela-de-aviso-dom` PASS `rows=['Inglês', 'Clique em para configurações', 'Summoner’s Rift, gameplay,'] chrome=[True, True, False]` — the real window's row survives, the two chrome rows say `chrome=True` |
| blank+repaint per pause edge (3 cycles in 30 s) | `_yt_pause_edge` + `PAUSE_BLANK_DWELL_S`: a pause must both last and stay undrawn before it blanks | `VERDICT: PASS (26/26)` |
| last player row left on screen after release (10,4 s of stale pixels) | `_release` calls `_blank_caption_window('external-released')` inside the transition | `youtube-cdp-source-oracle.py` PASS (26/26) |

The worker-reload cost on toggle-back (`REDUX_ENGINE_LOAD load_s=28.58`) is
**unchanged and is not part of these three**: it is the park/reload trade, priced
in `_main/receipt-20261111-live-start-latency.md`.

## Commands used (all read-only)

```
cd H:/sotto && wc -l app/webview/sotto_webview.py app/webview/youtube_cdp_source.py app/webview/youtube_window.py
cd H:/sotto && grep -n "Clique em\|para configura" _main/webview-run.log
cd H:/sotto && python - <<'EOF'   # walk _main/webview-run.log around each EXTERNAL_CAPTIONS_RELEASED
EOF
```

## Measured toggle -> state -> surface table

| toggle action | flags flip (measured) | surface | OUR caption keeps running? |
|---|---|---|---|
| captions ON (hint/toast window, `Inglês` + `Clique em para configurações`) | rows=4 read from the hint window, `yt_reason` unset in log, `external_captions_active=True` | OUR overlay repaints the hint rows as if they were captions | **NO — pixels are wrong**: `_main/webview-run.log:272627` `YT_FRAME src=external:youtube:track rows=4 lines=['Inglês', 'Clique em para configurações', 'Summoner’s Rift, gameplay,', 'and the new player experience.']` -> `:272633` `CAPTION_PAINT_SURFACE src=player rows=4 text="Ingl\u00eas\nClique em para configura\u00e7\u00f5es\nSumm"` |
| video paused / resumed with the flag flapping | `yt_cdp_paused` oscillates (`YOUTUBE_PAUSE_DISAGREED`, `YOUTUBE_CLOCK_STATIC`), `_yt_pause_edge` fires blank+repaint per edge | overlay blanked then repainted with the frozen row, repeatedly | **NO — flicker**: measured 3 blank/repaint cycles in 30 s (epochs 34/35/36) around 20:13:39–20:14:04 |
| captions OFF while the player was serving | `EXTERNAL_CAPTIONS_RELEASED reason=no-caption` -> `EXTERNAL_OWNER owner=local` -> `ENGINE_PARK reason=off` -> `EXTERNAL_CAPTIONS_ENGINE_RESUMED` | overlay keeps the last player row until the next ASR cue | **YES but late**: `_main/webview-run.log:271781` `20:10:02.796 EXTERNAL_CAPTIONS_RELEASED reason=no-caption`, next ASR text only at `:271799` `20:10:13.226 CAPTION_IN ... text="did"` (10.4 s); other episode `:299997` `22:28:49.814` -> `:300008` `22:28:51.669 CAPTION_IN text="I'm"` (1.9 s) |
| captions ON for > park delay | `ENGINE_PARK reason=captions` + `EXTERNAL_CAPTIONS_ENGINE_PARKED source=...` | engine parked; on toggle back the worker reload cost is 28.58 s (`REDUX_ENGINE_LOAD load_s=28.58` at 20:14:06.903) | yes while the track keeps serving, but a toggle-off releases only after `YT_RELEASE_S` = 30 s (`:285157` `20:13:37.515 ENGINE_PARK reason=captions`, `:285158` `EXTERNAL_CAPTIONS_ENGINE_PARKED source=external:youtube:liveframe`) |

## Code sites that decide each row (read, not edited)

- `app/webview/youtube_cdp_source.py:159-215` `EXTRACT_JS` — takes **every** visible
  `.caption-visual-line` inside `#ytp-caption-window-container`; it has no notion of
  the hint window's non-segment children (`svg`/`button`), so `Inglês` /
  `Clique em para configurações` come out as ordinary rows.
- `app/webview/youtube_cdp_source.py:797-855` `parse_snapshot` — filters by text
  only; there is no `chrome`/window grouping to drop the hint rows.
- `app/webview/sotto_webview.py:5975-6010` `_yt_cdp_fast_lines` — returns the DOM
  rows as authoritative whenever `snap['rows']` is non-empty (hint rows included).
- `app/webview/sotto_webview.py:5218-5271` `_yt_pause_edge` — blank/repaint on every
  edge with no confirmation window, so a flapping `paused` flag costs a blank and a
  repaint per flap.
- `app/webview/sotto_webview.py:6952-7015` `_release` — release path (correct in
  shape: one release per episode, owner back to `local`, park cleared, engine
  resumed) but the resume depends on a worker reload, measured 10.4 s of no pixels.

## Falsifiers — where they live now

No `youtube-caption-toggle-oracle.py` exists and none was written: each falsifier
was folded into the oracle that already owns the seam, which is cheaper and keeps
one owner per invariant.

| planned arm | where it now runs | measured |
|---|---|---|
| `a1-no-chrome-rows` | `_main/youtube-cdp-source-oracle.py` `janela-de-aviso-dom` | PASS — chrome `[True, True, False]`, the real row survives |
| `a2-pause-edge-confirm` | `_main/youtube-cdp-source-oracle.py` (dwell + quiet arms) | PASS (26/26) |
| `a3-release-falls-back` | `_main/youtube-cdp-source-oracle.py` (release blanks inside the transition) | PASS (26/26) |
| `--neg-arm` | same oracle `--neg-arm` | mutants caught, rc=1 |

`UNMEASURED`: that the owner's screen shows the correct rows. That needs a real app
run by his hand; every number above is a headless oracle.

## History

The 2026-11-14 body below is kept verbatim as the measurement that produced the
cures — the line references are from that day and have since shifted.
