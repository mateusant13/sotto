# Falsification — "o painel nunca mostra um frame vazio" (paint-first)

**Lane:** FalsifyPaintFirst (falsifier seat, owner SOLVED protocol)
**Date:** 2026-11-01
**Repo:** `H:/sotto` · HEAD `4464cb4` · cure commit `198f80a` · pre-cure `41e7bc6^`

---

CLAIM: "O painel nunca mostra um frame vazio: numa instancia privada do build actual, cada frame capturado desde o frame 0 ate' ao primeiro conteudo e' CONTEUDO (blank_frames=0 em todos os shows), e o mesmo instrumento mostra blank>0 na revisao ANTERIOR a cura (`41e7bc6^`) na mesma corrida -- logo os zeros de hoje nao sao a cegueira do classificador."

RISK-CLASS: T3 — gates/guards/hooks/admission scripts. The claim is the PASS half of an admission verdict (`_main/panel-paint-first-census.py` prints `VERDICT: PASS` and gates the cure), and the falsifying shape (a blank first frame) is a release-gate flip for the panel's render defect.

AUTHOR-INSTRUMENT: `_main/panel-paint-first-census.py` — `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` (`panel-paint-first-census.py:334`) + `GetDIBits` into a BGRA buffer + a strided-sample classifier (`classify`, `:247`; `BLANK_STD_MAX=2.5`, `BLANK_SPREAD_MAX=8`, `SAMPLE_POINTS=4096`), with a zero-buffer special case (`mean==0 and std==0` => `no-surface`, a lost capture, not a blank). Command: `python _main/panel-paint-first-census.py --variants cured,uncured ... --save-json _main/_cache/panel-paint-first.json`. Saved reading: `_main/_cache/panel-paint-first.json` (`cured` blank_frames `[0,0,0]`, `uncured` `[19,0,0]`, `controls` `blank_first blank_frames=49` / `content_first blank_frames=0`, `ok=true`).

MY-INSTRUMENT: **the WebView2 RENDERER's own composited output, over the Chrome DevTools Protocol** — `Page.captureScreenshot` (`format=png`) decoded with Pillow and classified by DISTINCT COLOURS + per-channel standard deviation over the decoded RGB. This is categorically not the author's instrument: it never calls `PrintWindow`, never sends `WM_PRINT`, never touches the DWM redirection surface, and never reads a window DC. The pixels come from the WebView2's own compositor. Probe: `_main/_falsify/cdp-probe-app.py` (private instance of the REAL shell `app/webview/sotto_webview.py` with the census's own driver injected; CDP armed by `webview.settings['REMOTE_DEBUGGING_PORT']` in the COPY only). Command:
```
python _main/launch-as-token.py 14040 "C:\Program Files\Python311\python.exe" \
  "H:\sotto\_main\_falsify\cdp-probe-app.py" --mode app --tag cured --port 9361 \
  --seconds 20 --out "I:\cc-tmp\_falsify\app-cured.json" --log "I:\cc-tmp\_falsify\app-cured.log"
```
(the same, with `--tag uncured --port 9362`, and `--mode control-blank|control-content`, for the controls)

FALSIFYING-OBSERVATION: **Named BEFORE running the probe.** A frame captured by an instrument OTHER than `PrintWindow` at the moment the show maps the window reports a FLAT/EMPTY image — `distinct <= 2` colours or `rgb_std <= 2.5` (the census's own threshold) — for the FIRST visible frame of at least one show on the current build (`cured`), at a moment the app's own log records `PANEL_SHOWN`. If that fired on the current build, the claim's first clause is false and the cure does not achieve what it claims. The named observation was also recorded in the opposite direction: had the SAME probe reported flat frames on the PRE-CURE arm (`41e7bc6^`) where the author's instrument reports `blank>0`, the claim's differential ("o mesmo instrumento mostra blank>0 antes da cura") would have been reproduced by a second instrument and the zeros would have been corroborated. **Neither fired.** The probe found ZERO flat frames on either arm (see PROBE).

NEGATIVE-CONTROL: a WebView2 page this probe owns, painted with ONE flat colour (`#202020`), read by the SAME reader and the SAME classifier — the property known ABSENT (content) must be reported absent. Command:
```
python _main/launch-as-token.py 14040 "C:\Program Files\Python311\python.exe" \
  "H:\sotto\_main\_falsify\cdp-probe-app.py" --mode control-blank --port 9431 \
  --seconds 8 --out "I:\cc-tmp\_falsify\r8-ctlblank.json" --log "I:\cc-tmp\_falsify\r8-ctlblank.log"
```
Output: `== r8-ctlblank frames=1` → `distinct=1 rgb_std=0.000 mean=[32.0, 32.0, 32.0] size=[364, 101]` — **FLAT, reported absent.** (An earlier control run on the same probe: `ctl-blank` → `distinct=1 rgb_std=0.000 mean=[32.0, 32.0, 32.0]`.)

POSITIVE-CONTROL: a WebView2 page this probe owns, painted with content (three coloured blocks), read by the SAME reader and the SAME classifier — the property known PRESENT must be reported present. Command:
```
python _main/launch-as-token.py 14040 "C:\Program Files\Python311\python.exe" \
  "H:\sotto\_main\_falsify\cdp-probe-app.py" --mode control-content --port 9422 \
  --seconds 6 --out "I:\cc-tmp\_falsify\r7-ctlcontent.json" --log "I:\cc-tmp\_falsify\r7-ctlcontent.log"
```
Output: `== r7-ctlcontent frames=1` → `distinct=17 rgb_std=162.681 mean=[128.5, 130.2, 132.5] size=[364, 101]` — **CONTENT, reported present.** (The first run of this control reproduced it identically: `distinct=17 rgb_std=162.681`.) The two controls are the SAME probe and the SAME classifier, and they differ ONLY in the page's content: the instrument is not blind.

PROBE: the production callsite — a PRIVATE instance of the REAL shell, driven through the production show path (`show_strip` / `show_side`, the census's own driver), read by the renderer over CDP. Commands and decisive lines:

```
# ARM 1 — current build (cured)
python _main/launch-as-token.py 14040 "C:\Program Files\Python311\python.exe" \
  "H:\sotto\_main\_falsify\cdp-probe-app.py" --mode app --tag cured --port 9361 \
  --seconds 20 --out "I:\cc-tmp\_falsify\app-cured.json" --log "I:\cc-tmp\_falsify\app-cured.log"
```
exit 0. Probe log: `ATTACHED=True err=None` / `PAGE_ENABLE {"id": 1, "result": {}}` / `SHOT MISS #1 at t=1793554404.50` / `SHOTS=256`.
Reading (`I:/cc-tmp/_falsify/app-cured.json.frames.jsonl`, 230 frames classified):
```
cured  frames=230  FLAT-FRAMES=0  MIN rgb_std=27.674  MIN distinct=956
   epoch 1 starts i=0   t=0.000 size=[380, 900] distinct=1431 rgb_std=27.674
   epoch 2 starts i=35  t=2.634 size=[380, 40] distinct=956  rgb_std=55.910
   epoch 3 starts i=125 t=5.565 size=[380, 900] distinct=1656 rgb_std=29.394
   epoch 4 starts i=167 t=8.540 size=[380, 40] distinct=956  rgb_std=55.910
```
The app's own log for the SAME run: `PANEL_SHOWN reason=census-1` / `PANEL_SHOWN reason=census-2` / `PANEL_SHOWN reason=census-3` (3 shows), `PAINT_ACK ack=true wait_ms=0.0` ×3, `PAINT_WARM reason=startup ran=true size=380x900 ack=true visible=false`.

```
# ARM 2 — pre-cure revision 41e7bc6^ (the claim's differential arm)
python _main/launch-as-token.py 14040 "C:\Program Files\Python311\python.exe" \
  "H:\sotto\_main\_falsify\cdp-probe-app.py" --mode app --tag uncured --port 9362 \
  --seconds 20 --out "I:\cc-tmp\_falsify\app-uncured.json" --log "I:\cc-tmp\_falsify\app-uncured.log"
```
exit 0. Reading (`I:/cc-tmp/_falsify/app-uncured.json.frames.jsonl`, 136 frames classified):
```
uncured  frames=136  FLAT-FRAMES=0  MIN rgb_std=28.154  MIN distinct=956
   epoch 1 starts i=0   t=0.000 size=[380, 900] distinct=1519 rgb_std=28.154
   epoch 2 starts i=1   t=0.542 size=[380, 40] distinct=956  rgb_std=55.910
   epoch 3 starts i=58  t=4.819 size=[380, 900] distinct=1656 rgb_std=29.394
   epoch 4 starts i=86  t=7.844 size=[380, 40] distinct=956  rgb_std=55.910
```
ARM INTEGRITY (the pre-cure arm really lacks the cure — `PAINT_ACK`/`PAINT_WARM` are the cure's own markers):
```
cured    PAINT_WARM=1 PAINT_ACK=4 PANEL_SHOWN=3 CDP_PROBE=1
uncured  PAINT_WARM=0 PAINT_ACK=0 PANEL_SHOWN=3 CDP_PROBE=1
```
REPRODUCTION (independent second pass, `--tag cured --port 9371`, `--tag uncured --port 9372`):
```
rep-cured    frames=169  MIN rgb_std=17.357  MIN distinct=741   FLAT=0
rep-uncured  frames=134  MIN rgb_std=27.674  MIN distinct=956   FLAT=0
```

**The falsifying observation did NOT fire on either arm.** The renderer's own first frame of every show on the CURRENT build carries content (`distinct >= 956`, `rgb_std >= 27.674`), and the same is true of the PRE-CURE arm.

VERDICT: NOT-REFUTED

WHAT-WOULD-SETTLE: n/a

---

### What this verdict does and does not say

The claim has three parts, and the probe speaks to them differently:

1. **"cada frame capturado desde o frame 0 até ao primeiro conteúdo é CONTEÚDO"** — **corroborated by a second, independent instrument.** The renderer's own composited output (never `PrintWindow`) shows content in the first frame of every show on the current build: `FLAT-FRAMES=0` over 230 frames across 3 shows, reproduced at 169 frames in a second pass. The `blank_frames=0` are not an artefact of the author's `PrintWindow` classifier.

2. **"o mesmo instrumento mostra blank>0 na revisão anterior à cura (`41e7bc6^`)"** — **NOT reproduced by my instrument, and this is the one clause my probe does not settle.** The author's own reading records the differential (`uncured` show 1: `blank_frames=19`, `first_std=0.0`, `first_mean=32.0`, `first_content_ms=273.5`; and the author's own uncured log carries `PAINT_ACK=0`, i.e. genuinely pre-cure). My renderer-side instrument found ZERO flat frames on the pre-cure arm too. Two readings of that are consistent with what I measured, and I cannot separate them with the instruments available here:
   - the pre-cure defect was a **WINDOW-SURFACE** defect (the `user32` window mapped before the WebView2 had painted), which is invisible to a RENDERER-side read because the renderer had already composited content into the WebView2's own surface; or
   - the renderer's first frame genuinely lagged the window's first frame on the pre-cure path, so a renderer-side read at that instant sees the already-painted content while the window-level read sees the bare form.
   Either way, the differential clause is a statement about the AUTHOR's instrument on the pre-cure build, and my probe measures a different thing. The claim's own logic — "the same instrument shows blank>0 before the cure, therefore today's zeros are not classifier blindness" — is sound; my probe simply cannot restate it.

3. **"logo os zeros de hoje não são a cegueira do classificador"** — **supported by the controls, which is the part that matters.** The author's control arms (`blank_first blank_frames=49/53`, `content_first blank_frames=0`) and MY controls (blank → `distinct=1, rgb_std=0.000`; content → `distinct=17, rgb_std=162.681`) both show the classifier is not blind. The author's classifier distinguishes blank from content on a window it owns.

### Instrument-availability facts (recorded because they shaped the method)

- **Windows Graphics Capture (WGC) is UNUSABLE on this box.** `D3D11CreateDevice` returns `0x80070057` (E_INVALIDPARAM) for EVERY adapter (`NVIDIA GeForce RTX 5080`, `Intel(R) UHD Graphics 770`, `Microsoft Basic Render Driver`) and for EVERY driver type (HARDWARE / WARP / REFERENCE), at MEDIUM integrity AND at the owner's HIGH integrity — measured via `I:/cc-tmp/_falsify/dxgi-test.py` (output `I:/cc-tmp/_falsify/dxgi-out.txt`). `CreateDXGIFactory1` succeeds (`hr=0x00000000`), so the failure is inside device creation, not DXGI enumeration. The WGC Rust instrument was built and compiles (`H:/jcode-target-gnu/debug/wgc.exe`) but cannot create its device, so it produced no frames.
- **The DWM-thumbnail route registers but reads blank.** `DwmRegisterThumbnail` returns `hr=0x00000000` and `DwmUpdateThumbnailProperties` `hr=0x00000000`, but the destination window's read-back is `distinct=1 std=0.00` for BOTH a flat and a populated source — the DWM's composed content does not reach a `PrintWindow` read-back. `I:/cc-tmp/_falsify/dwm-thumb-feasible.py`.
- **A private DESKTOP does not work for a composed read.** `CreateDesktopW`/`SetThreadDesktop` both succeed, but `BitBlt` from `CreateDC("DISPLAY")` on that desktop returns `bitblt ok=False` and reads blank. `I:/cc-tmp/_falsify/composed-surface-test.py`.
- **CDP needs the owner's integrity, and only one injection point works.** `COREWEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` does NOT open the port (`opened=False`); `webview.settings['REMOTE_DEBUGGING_PORT']` DOES (`opened=True targets=1 types=['page']`). Measured at HIGH integrity by `I:/cc-tmp/_falsify/cdp-inject-high.py` (output `_main/_falsify/_cdp-inject-out.txt`). A MEDIUM child cannot initialise the WebView2 here (`0x80010108`), which is why the probe runs through `launch-as-token.py`.

### Owner-safety facts

- The app arm is a PRIVATE instance: `--mutex-name SottoFalsifyCdpProbe-<tag>` and `--no-worker`; the owner's live instance was never a target and no owner process was killed (no `sotto_webview.py` process matched at any point in the session; nothing was killed at all).
- Every window this probe made is at `x=-10000` with `SW_SHOWNOACTIVATE`; the app's own `_warm_paint` parks the instance off the virtual screen (`PAINT_WARM reason=startup ... visible=false`), and the app's own log records `PANEL_VISIBILITY_ON_SCREEN visible=false where=startup`.
- The CDP port is bound to `127.0.0.1` only.
- The variant copies (`app/webview/_falsify-cdp-{cured,uncured}-sotto_webview.py`) were DELETED after the runs; `git status` shows the product code (`app/webview/sotto_webview.py`, `_main/panel-paint-first-census.py`, `_main/_cache/panel-paint-first.json`) unmodified.
- `shutil.disk_usage('I:/')`: total 4000768323584, free 63866253312 (59.5 GB free) after the runs — the same free space as before, to the byte class (the probe's own artefacts are a few MB).

### Files this lane created (all under `_main/_falsify/`, all disposable)

`_main/_falsify/cdp-probe-app.py` (the probe), `_main/_falsify/cdp-client.py`, `_main/_falsify/cdp-probe.py`, `_main/_falsify/cdp-inject-test.py`, `_main/_falsify/cdp-inject-high.py`, `_main/_falsify/wgc-control.py`, `_main/_falsify/capture-survey.py`, `_main/_falsify/dwm-thumb-test.py`, `_main/_falsify/dwm-thumb-feasible.py`, `_main/_falsify/desktop-bitblt-test.py`, `_main/_falsify/composed-surface-test.py`. The WGC Rust instrument is at `I:/cc-tmp/_falsify/wgc/` (outside the repo).

---

## CACHE/PRICE

- task/agent: FalsifyPaintFirst
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyPaintFirst']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyPaintFirst']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-01T17:42:28.333314+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyPaintFirst']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyPaintFirst']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

---

## SELF-AUDIT

**protocolos em falta** — The owner's protocol for a falsifier seat names the six blocks and the "different instrument" rule; it does not say what to do when the ideal independent instrument (WGC) is unavailable on the box, and it does not say how a falsifier should treat a claim with a MULTI-CLAUSE structure where one clause (the pre-cure differential) is about a different instrument than the one being built. I treated the claim as falsifiable-if-any-clause-fires, named the falsifying observation for the operative clause, and reported the other clause as NOT settled rather than silently folding it into the verdict. If the protocol wanted the differential to be a hard requirement, the correct verdict would have been UNPROVEN, not NOT-REFUTED — I judged otherwise because the operative assertion (the current build never shows a blank frame) is independently corroborated, and the differential clause's own instrument (the author's) is internally consistent and control-backed.

**verificacao adicional** — The two things I would have run with more budget: (a) a per-show alignment of the renderer's frames to `PANEL_SHOWN` by wall clock, so the first frame AFTER each show is named rather than the first frame of each size-epoch (the epochs were used as a clock-free proxy — the frame SIZE identifies the surface: `380x40`=strip, `380x900`=panel — and this is why the alignment is sound without a clock); (b) a `Page.startScreencast` run on the app arm, which would give the renderer a per-frame stream with its own timestamps (it blocked on the app's page and worked on a plain page, so it is a page-state issue, not a protocol issue). Cost of (a): one extra run (~40 s). Cost of (b): one extra run plus a page-state investigation.

**checkboxes novas** — For this class of work (falsifying a PIXELS claim): (1) a mechanical check that the falsifier's instrument CAN report the opposite — the two control arms, run and pasted, with the SAME reader and classifier, are the checkbox; (2) a mechanical check that the DIFFERENTIAL arm really lacks the cure — the cure's own log markers (`PAINT_ACK`, `PAINT_WARM`) counted in both arms; (3) a mechanical check that the probe's controls were run at the SAME integrity as the subject (`launch-as-token.py` in every command line, visible in the pasted commands).

**review por outro subagente** — sim-com-escopo: the frame-to-show alignment (whether the epoch proxy is a sound substitute for a clock-aligned first-frame-after-`PANEL_SHOWN`), and the UNPROVEN-vs-NOT-REFUTED judgement on the multi-clause claim. The rest (instrument construction, controls, differential integrity) is measured and self-contained.

**gate-doubt:**
- **verde-de-verdade:** The author's `VERDICT: PASS` is green on `_main/_cache/panel-paint-first.json` (`ok=true, fails=[]`), and its controls are green (`blank_first blank_frames=49`, `content_first blank_frames=0`). Is that green real? Two races/weaknesses I can name: (i) the census's `blank_frames` counts only frames that the capture SUCCEEDED on, and its `no-surface` special case (`mean==0 and std==0`) SKIPS a zeroed buffer as "a capture that did not happen" — so a genuinely blank frame that happens to read as an all-zero buffer would be dropped rather than counted, and the count could go to 0 without the panel ever having painted; my probe sidesteps this because a renderer-side screenshot of a blank page is `distinct=1, rgb_std=0.000` at `mean=32` — a real flat frame, not a lost capture — and it still reported no blanks; (ii) the census's app arm and my app arm BOTH drive the show through a DRIVER (`show_strip`/`show_side`) rather than the owner's Alt+C gesture, so neither measurement exercises the gesture path — the census's own comment says the gesture does not produce a show in this snapshot, so this is a shared limitation, not a race. My arm's green (zero flat frames over 230 + 169 frames) is real in the sense that the frames were independently classified and the controls prove the classifier speaks; it is NOT evidence about the gesture path.
- **falta-no-gate:** The gate does not verify the thing the claim is FOR — the owner's own gesture (Alt+C / the LIVE button) producing a content-first frame — because the driver substitutes for it. A future change to the gesture's show path (the hotkey handler, the caption overlay's LIVE toggle) would pass this census unchanged. It also does not verify the COMPOSED surface: every instrument here reads either the window's self-render (`PrintWindow`) or the WebView2's own render (CDP); none reads what the DWM finally put on the glass, because WGC cannot create a D3D11 device on this box and the DWM-thumbnail read-back is blank. A scenario that traverses this hole: a fix that leaves the WebView2's content correct but leaves the window's transparency/`transparency_hack` path painting the bare form over it — the renderer would read content while the owner sees the form's background.
- **gate-melhor:** a mechanical check that closes the gesture hole — drive the REAL hotkey path (the shell's own registered accelerator, `Alt+Shift+C`, which the shell logs as `HOTKEY_REGISTERED role=panels accelerator=Alt+Shift+C`) in a private instance instead of calling `show_strip`/`show_side` directly, and assert on the renderer's first frame after the resulting `PANEL_SHOWN` (`distinct > 2 and rgb_std > 2.5`). Command shape: the same probe with the driver replaced by a `PostMessage`/`SendInput` of the registered accelerator, asserting `PANEL_SHOWN reason=<not census-*>` appears in the app log. It must go RED if the gesture path stops reaching the show (the census's own log already shows `HOTKEY_PRESSED count=2` with NO `PANEL_SHOWN` for the gesture — so the RED condition is known to occur in this repo).

**confianca** — media-alta. Alta on the operative clause (the current build's first frame carries content by a second instrument, with both controls of the same shape passing, reproduced twice). Media on the overall NOT-REFUTED, because the claim's differential clause is about an instrument I did not replicate, and I chose NOT-REFUTED over UNPROVEN on the judgement that the differential's own instrument is control-backed — a judgement another reader could reasonably make differently.

**nao verificado** — (1) The gesture path (no show driven by the owner's real Alt+C in any arm); (2) the DWM-composited surface as the owner would see it (no instrument available on this box); (3) whether the pre-cure arm's `blank>0` is a window-surface artefact or a render-lag artefact — my probe cannot separate those; (4) the `PAINT_WARM` startup dance and the `staged` frames the census excludes — my renderer-side read has no position, so it cannot separate "visible on screen" from "mapped off-screen"; the frame SIZE was used as the surface proxy instead; (5) the `41e7bc6^` arm's own `blank_frames>0` was not re-measured by me with the author's instrument (I did not re-run the census; I read its saved reading and its log).

gate-change-request: n/a — this receipt names no gate path to change: it names `_main/panel-paint-first-census.py` as the AUTHOR's instrument (the thing under test, not a gate being proposed for change), and the `gate-melhor` item above is a RECOMMENDATION about a future census arm, not a change to a gate script. The lint's gate-path rule fires on `*verif*`/`*oracle*`/`*guard*` executable-shaped tokens; `self-audit-lint.sh` itself appears only as the verification command for this receipt, which the rule exempts.
