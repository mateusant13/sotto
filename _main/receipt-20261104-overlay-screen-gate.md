# Receipt -- `caption-overlay-screen` gate (2026-11-04)

P0 card "a janela da legenda diz `visible=true` mas ele nao ve" is now closed by a GATE, not a log
line: `_main/caption-overlay-screen-oracle.py` executes the REAL
`caption_overlay.NativeCaptionOverlay._screen_proof()` and judges its four response classes, with the
arms split between real Win32 and a stub, per arm -- A1 `real-win32-rect-and-alpha` and A2
`real-win32-on_screen-cross-check` run against `user32` for real, on a `WS_EX_LAYERED` window this
oracle creates at `-4000,-4000` and never shows (no `WS_VISIBLE`, no `ShowWindow` anywhere in the
file), where `rect == (-4000,-4000,400,90)` proves `GetWindowRect` was actually read and `alpha ==
255` is the value `SetLayeredWindowAttributes` wrote and `GetLayeredWindowAttributes` read back,
while A2 requires the returned `on_screen` to agree with an INDEPENDENT recomputation of the same
predicate in the oracle; A3 `stub-inside-true`, A4 `stub-outside-false`, A5 `stub-alpha-zero-reported`
and A6 `stub-failure-logged` run against a `StubUser32` that answers by arithmetic (the real window
still exists; only geometry/alpha/flags come from the stub), with A5 the one that matters here -- a
window `ShowWindow`'d and reported `visible=true` whose layered alpha reads 0 is REPORTED as `alpha=0`
and the oracle's own `judge()` returns `RED ... invisible: alpha=0`, so the exact "visible=true, saw
nothing" class can never pass; A6 requires a throwing read to leave `CAPTION_OVERLAY_GEOMETRY_FAILED`
in the log and return `(None, None, -1)`; and A7 `measured-in-show` keeps `_screen_proof()` wired into
the shipped `show()` with `on_screen=`/`alpha=` published. `--neg-arm` mutates a COPY of
`caption_overlay.py` four ways -- `work-area-inverted` (the work-area containment test negated),
`alpha-ignored` (`alpha_v = 255` instead of the read value), `closure-discarded` (the failure handler
narrowed so an OSError escapes instead of logging and returning the failure tuple) and
`rect-from-self.visible` (the rect computed from the flag instead of `GetWindowRect`) -- and requires
rc=1 with `NEG-ARM cases=4 caught=4`; measured 4/4 caught, each on its named arm. The gate is wired in
`_main/_audit-verify-all.cmd` as `always caption-overlay-screen` + `:record` +
`always red-as-expected-caption-overlay-screen ... --neg-arm` + `:expectred ... "NEG-ARM"`, the same
run also wired the orphan `lag-note-cost` oracle the perf merge left out, and AGENTS.md's battery pin
was re-measured to 212764 B / 2644 CRLF / sha256 `BBED658D...F4EF62` (`agents-md-pins-oracle` PASS).
WHAT THIS STILL DOES NOT PROVE: `_screen_proof` can be correct and the caption still be invisible --
the gate reads geometry and layered alpha, not composited pixels; it cannot prove the compositor put
the glyphs on the owner's monitor (a transparent bitmap, a wrong monitor's DPI, or a topmost z-order
loss would all pass here), and it does not exercise `UpdateLayeredWindow`/GDI+ at all. That last mile
needs the owner's screen, not this oracle.
