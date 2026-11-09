# Review 2026-11-09 - panel/UI + pipeline surfaces

Scope: working-tree diff for `app/panel/*` (panel.html, panel.js, panel-unified.css, panel.css) and
`app/webview/*` (youtube_cdp_source.py, youtube_clock.py, gaming_mode.py, space_swallow.py,
caption-formulation.js), plus the committed `011e196` clock/source refactor and the modified
oracles under `_main/`. Read against `receipt-20261106-panel-owner-round.md`,
`receipt-20261108-panel-history-legibility.md`, `receipt-20261108-caption-clock-and-marker.md`,
`receipt-20261109-worker-cost-and-commit.md`, `receipt-20261109-reload-floor.md` and
`receipt-20261109-thread-bench-stutter.md`.

Verdict: **not correct as-is** - one P2 correctness gap plus three P3s.

| # | Subject | Severity | Location | Finding |
|---|---------|----------|----------|---------|
| 1 | B pipeline | P2 | `app/panel/caption-formulation.js:837-845` | `fileText` is set only for `route !== 'final'`, but both stores refuse `provisional-draft`; the field never reaches the only route that is written, so the M8 "file without the invented mark" fix is inert. The engine-only oracle arm 4 does not exercise the store. |
| 2 | A UI | P3 | `app/panel/panel.html:368-374` | Moving `#menu-button` into the fixed control row widens it by 32px (left edge 102 -> 70), overlapping the wordmark (right edge 71) by 1px. The old 31px header gap is no longer gated; the replacement arm only checks `left >= 0`. |
| 3 | B pipeline | P3 | `app/webview/youtube_cdp_source.py:1004-1010` | `live_source_set` (commit `011e196`) has no caller; production builds through `live_source()` and no oracle references the `set` adoption API. Dead path, untested. |
| 4 | A UI | P3 | `app/panel/history-store.js:294-300` | The Node twin's `replace` branch drops the previous line's `ctx1=` context; the Python twin merges `_prev_ctx`. The two implementations disagree on the same merge decision (probe-only store). |

Not run (house rules): no app launch, no battery, no popup. The dirty tree and all
other lanes' files were left untouched; only this review pair was written.
