# Receipt - the Alt+C strip still shows a blank window: P0(a) REFUTED

Date: 2026-10-10. Subject: `app/webview/sotto_webview.py`
sha256 `557A2B0D4CA43752EAE48E371E6B25C5CB76189179A3E2D2960C6FBE77FACB1A`
(326796 B, 6583 lines) - the file the app IS. Instrument:
`_main/strip-first-frame.py` (new here, not previously committed).

## 1. The claim that was tested (P0(a))

`docs/handoff-2026-10-09-transparent-panel.md` section 4 named P0(a) as the next
step: the shell maps the form and only THEN re-runs the compositing hack
(`transparency_hack`, pywebview `edgechromium.py:348`), so the first frame
presented is the FORM background rather than the panel. Hypothesis: swapping the
order (composite first, map second) removes the blank.

That hypothesis is FALSE, and it is measured false by the runs below. The three
edits that implemented the swap were reverted byte-exact from HEAD at the end of
this measurement; no code change ships from P0(a).

## 2. The instrument

`_main/strip-first-frame.py` launches the REAL shell
(`pythonw.exe sotto_webview.py --no-worker --exit-after 90 --log ...`, so the run
owns Alt+C) and, from a second thread, BitBlts a 16x7 grid of screen pixels over
the strip rect every ~1 ms. Per sample it records: the window at the strip centre
(`WindowFromPoint`), whether that window is the shell (`GetAncestor(hwnd,
GA_ROOT) == the form hwnd`, or its pid is the shell pid), the window rect, the
number of DISTINCT colours in the grid (`distinct`), and `flat` = every grid point
within +/-2 of the first one, i.e. the whole 1040x150 strip is ONE colour.

`flat` is deliberately NOT keyed to the form BackColor: a separate `slab` flag
reports whether that one colour is `rgb(11,15,20)`. Reason, measured: the blank is
NOT always the slab colour (see the three runs below - `(32,32,32)` twice,
`(18,18,18)`, `(12,16,21)`). A verdict keyed to one exact colour was wrong twice
before this flag existed.

Arms: `--arm flat` (exit 0 iff the blank IS seen - the sensitivity control, run on
HEAD bytes) and `--arm clean` (exit 0 iff the blank is NOT seen - the arm the swap
was supposed to win). A missing observation is `EXIT 2` / NO-CONFIDENCE, never a
pass.

## 3. What was measured

Three runs of the SAME bytes, two orders. The blank is present in all three; only
its duration and colour move.

| run | file order | first owned sample | blank held | colours of the blank | cadence median / max | verdict |
|---|---|---|---|---|---|---|
| A | HEAD (map, then hack) | +15.9 ms | **216.3 ms** | (32,32,32), (18,18,18) | 0.04 / 21.77 ms | FLAT-FRAME SEEN, EXIT 0 |
| B | swapped (hack, then map) | +25.3 ms | **205.1 ms** | (18,18,18) then (12,16,21) | 0.02 / 20.20 ms | RED (clean arm), EXIT 1 |
| C | HEAD (map, then hack) | +14.4 ms | **191.8 ms** | (32,32,32) | 0.04 / 23.14 ms | FLAT-FRAME SEEN, EXIT 0 |

Run B is the swap under test. Runs A and C are the same committed bytes as each
other; C was taken AFTER the revert, on the exact HEAD file
(`557A2B0D...`, COMPILE_OK). Run A's report file was overwritten by a later run of
the same fixed report path, so only its numbers survive in the working notes; B
and C are archived with hashes (section 6).

Per-run detail, from the archived reports:

- B: `samples=27 owned+classified=27 flat-single-colour=13`, panel first painted at
  row 5376 with `distinct=16`, `FIRST FLAT FRAME at +0.0 ms (1040x150)`.
- C: `samples=23 owned+classified=22 flat-single-colour=9`, painted at row 3741
  `distinct=16`, `FIRST FLAT FRAME at +2.9 ms`.

## 4. Why the swap did not work - the mechanism, from the live log

The swap DID take effect; the log of run B proves it (archived, section 6):

    44 sotto: WEBVIEW_CHILD shown=2 already=3 failed=0
    45 sotto: FORM_SHOW_TRANSPARENCY_HACK ran (pywebview edgechromium.py:348 ...)
    46 sotto: PANEL_FOREGROUND_UNLOCK ok=true hwnd=1704672
    47 sotto: PANEL_SHOWN reason=hotkey mode=strip visible=true show=SW_SHOW+FOREGROUND

So on the Alt+C path the composite ran BEFORE the explicit map, exactly as the
swap intended - and the blank still held 205.1 ms. The premise is what is wrong:
`transparency_hack` calls `form.Show()` on the UI thread, and **that call is
itself a map**. There is no order in which "map the form" can happen after "make
WebView2 composite", because the composite only exists once the window is mapped.
The measured 191.8-216.3 ms is therefore the latency between "the strip window is
visible" and "WebView2 delivers its first composited frame" - the renderer's
first present, not a call-ordering artifact.

Corollary, worth keeping: the two `PANEL_SHOW_REFUSED` lines (28, 32) are the
pre-hotkey navigation-time Shows correctly refused by `_gate_form_show`; they do
NOT make the hotkey path blank, and the gate is not the cause here.

## 5. What the blank IS, and what it is NOT

IS: a single uniform colour over the whole 1040x150 strip, for 191.8-216.3 ms,
after which the panel paints (`distinct=16`) and stays painted.

IS NOT the desktop showing through a transparent window. The sampling grid is
1040x150 at a FIXED screen rect (`place_panel` is deterministic), and it read one
exact colour in every run - but the colour CHANGED between runs of identical bytes
towards the same rect: `(32,32,32)`, `(18,18,18)`, `(12,16,21)`. A wallpaper pixel
at a fixed point cannot change colour between runs, so the uniform surface is
Sotto's own window presenting an opaque-ish rectangle, not the owner's desktop.
The `(12,16,21)` case is exactly the form BackColor slab `#0B0F14` that
`_on_before_show` sets for this failure mode; the other two are the pre-composite
surface before that slab/panel is presented. Which of the two dominates is
run-dependent, which is why the verdict is "one colour", not "this colour".

NOT FIXED. The owner still gets a ~0.2 s dark block instead of the panel. Severity
is bounded by the fact that it is dark-on-dark and lasts under a quarter second,
and this receipt does not claim more than that.

## 6. Artifacts (size and sha256)

    C36D4D3C3E725D7D2FDC6C24333C46736309D7B80F913E32CB1CC6C40D1AAC96  1968  I:\cc-tmp\first-frame-report-head.txt        (run C)
    38A71246003E420811392DEB501B9953E35D9472CDD78D03D57D815113B860B7  1912  I:\cc-tmp\first-frame-report-swapped.txt   (run B)
    5C27BB308BEF095942E933B12F22A3E00EBD3210D3DC47359AD393A0A4799E58  5440  I:\cc-tmp\first-frame-log-head.txt         (run C log)
    29692A8188EF784B86777E0900AF68FB7A129C70FF79AB81049F53407A05E939  5668  I:\cc-tmp\first-frame-log-swapped.txt      (run B log)

Reproduce (no worker, real Alt+C, ~40 s per arm):

    py -3 H:\sotto\_main\strip-first-frame.py --arm flat --report I:\cc-tmp\r.txt

Exit 0 = the blank was seen, 1 = it was not (or, for `--arm clean`, that it was),
2 = NO-CONFIDENCE (never a pass). Verified before each arm: no
`sotto_webview.py` / `sotto_worker.py` process live, so the run owns Alt+C.

## 7. What was NOT tried, and why each is not free

1. **Map the form at startup with `Opacity=0`** so WebView2 composites early and
   Alt+C only moves/opacity-flips a warm window. This is what pywebview's own
   creation dance does briefly, and it is the only cure that plausibly removes the
   190+ ms entirely. NOT taken: it means the panel is MAPPED at startup, which
   `_gate_form_show` exists to refuse and which the startup-flash oracles and the
   battery count. Trading a measured startup map for a 0.2 s post-hotkey blank is
   an owner decision, not an instrument tweak.
2. **Delay the map until a first-paint signal** from the panel (a bridge message,
   with a timeout fallback). Also plausible; risks bricking the app's only control
   if the message never comes, and costs the same 190+ ms of "nothing at all"
   instead of 190+ ms of "dark strip". Needs the owner's call on which he prefers.
3. **`--opaque`** removes the transparency the panel look depends on. Already ruled
   out by the 2026-10-07 startup-flash work.

## 8. The next cheap measurement (not run here)

Press Alt+C a SECOND time after the panel has painted once (hide, then show with
the renderer warm) and measure the same window. If the second show has no blank,
the cost is specifically FIRST-VISIBILITY renderer warm-up - which is what makes
cure (1) the only one that can work, and it would also tell us whether the owner
actually sees it on every press or only on the first. `strip-first-frame.py` only
presses once today; that is a small, additive arm.

**RUN 2026-10-10, both colours, and the answer is CLEAN - see section 10.**

## 9. Decision recorded

- The three-swap working-tree change (`git diff` was 17 insertions / 10 deletions,
  working-tree blob `f7415a3`) was REVERTED with `git checkout HEAD --
  app/webview/sotto_webview.py`. The file is byte-identical to HEAD: sha256
  `557A2B0D4CA43752EAE48E371E6B25C5CB76189179A3E2D2960C6FBE77FACB1A` / 326796 B,
  `py_compile` COMPILE_OK, `git status --porcelain` clean for that path.
- Rationale for reverting rather than keeping: the in-code comments justifying the
  swap assert a cure that measurement refutes. A comment that lies is worse than no
  change, and the order is measurably neutral (191.8 / 205.1 / 216.3 ms).
- P0(a) is closed as a NEGATIVE result. The residual defect stays OPEN and is now
  named: "the strip presents a uniform colour for ~190-216 ms before WebView2's
  first frame", cause = renderer first-present latency, not call order.

## 10. The second show is CLEAN - the blank is a per-process FIRST map (measured 2026-10-10)

The experiment section 8 asked for was run. The instrument gained two flags in the
same change: `--shows` (default 1; 2 sends press 1 SHOW, press 2 HIDE, press 3 SHOW
again) and `--gap` (default 2.2 s, which must exceed `HOTKEY_DOUBLE_MS` = 1500 ms or
press 2 is read as the SIDE gesture instead of a hide). All three presses in both runs
below were 2253-2271 ms apart, i.e. three distinct presses, and the run exercises the
full hide/show round trip.

### 10.1 The first attempt was an INSTRUMENT defect, and it is recorded because it
### would have produced a false NO-CONFIDENCE

`Sampler` self-stops when its row budget is spent. Sampling the strip when it is
HIDDEN costs ~0.06 ms/row (16 000 rows/s: the grid `BitBlt` is skipped) but ~18 ms/row
(~55 rows/s) when it is on screen. So the single-show budget of 40 000 rows was spent
inside press 1's 2.5 s, the sampler stopped, and the report said

    sampler stopped: 40000 rows in 2.50s (16000 rows/s)
    SECOND-SHOW VERDICT NO-CONFIDENCE -- no owned sample after the second show; Alt+C mapped nothing there

Nothing was wrong with the second show - it was never sampled. The budget is now
`40000` for `--shows 1` (unchanged, so the committed first-show numbers keep their
instrument) and `150000` for `--shows 2`; the report prints `sampler budget=N row(s)`.
Any future multi-show arm has to re-check this line before it believes a NO-CONFIDENCE.

### 10.2 Run 2, --arm flat --shows 2 --gap 2.2 --span 2.5 --secs 5.0, budget 150000

    SUBJECT H:\sotto\app\webview\sotto_webview.py   pid=35276   --no-worker --exit-after 90
    sampler budget=150000 row(s)
    Alt+C sent (press 1: SHOW the strip)
    Alt+C sent (press 2: HIDE, 2259 ms after press 1)
    Alt+C sent (press 3: SHOW again, 2253 ms after press 2)

FIRST show (press 1, renderer cold):

    first pixel owned by the shell at row 2509 (+27.7 ms after the press)
    samples=23  owned+classified=22  flat-single-colour=11
    BLANK HELD for 216.4 ms after the map: the panel first painted at row 2521,
      distinct=16, after 11 single-colour owned sample(s)
    FIRST FLAT FRAME at +1.7 ms after the map (distinct=1, 1040x150)
    colours seen: [(32, 32, 32)]; 0 of them were the form BackColor slab rgb(11,15,20)+/-2
    VERDICT FLAT-FRAME SEEN   EXIT 0

SECOND show (press 3, same process, renderer warm):

    first pixel owned by the shell at row 32115 (+11.6 ms after press 3)
    samples=24  owned+classified=23  flat-single-colour=0
    SECOND-SHOW VERDICT CLEAN -- 0 of 23 classified sample(s) after the second map
      were blank; the blank is specific to the first map of a process

The 216.4 ms first-show figure sits inside the 191.8 / 205.1 / 216.3 ms band the
earlier runs measured, so run 2 is not an outlier of the instrument. (32,32,32) again,
again not the slab.

### 10.3 What this closes, and what it does NOT

- CLOSED: the blank is a FIRST-MAP property of the process, not a cost of every press.
  Once the renderer has composited one frame, the very next show presents a painted
  window from its first owned sample (+11.6 ms, and that sample is already
  multi-colour). Cure (1) - one pre-composite at startup with `Opacity=0` - is
  therefore the ONLY candidate that can remove the cost, and this run is the
  measurement that makes that statement falsifiable rather than rhetorical.
- NOT closed: the owner still sees a ~200 ms uniform rectangle on the FIRST Alt+C
  after a launch. That is a real, visible defect and it is unchanged.
- NOT claimed: that no sub-frame blank can hide inside the 25.69 ms worst-case row
  gap of the second window. The claim is narrow and is exactly what the data shows:
  0 of 23 classified owned samples in the 400 ms window after press 3 were a
  single-colour window, against 11 of 22 after press 1 in the same run.
- NOT tested: `--arm clean` (0 flat samples expected on the FIRST show). It has never
  returned EXIT 0 on either call order, before or after this change.

### 10.4 Repro

    set TMPDIR=I:\cc-tmp
    pythonw.exe _main\strip-first-frame.py --arm flat --shows 2 --gap 2.2 \
      --span 2.5 --secs 5.0 --report I:\cc-tmp\second-show-report.txt

Launch it the way the other arms are launched (`Start-Process -PassThru -WindowStyle
Hidden`, then `WaitForExit`, then read `ExitCode`) - a GUI-subsystem pythonw gives no
stdout. The report file is the only channel. No Sotto shell or worker may be live when
the arm starts: the arm registers Alt+C and must own it.


