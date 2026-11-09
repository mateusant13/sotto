# OMP handoff — Sotto remaining work

Prepared 2026-11-09 for the owner to continue in OMP. This is a handoff, not a claim that the full goal is done.

## Owner's goal

Finish the Sotto work consistently across all 59 themes:

- Ctrl+Space controls caption display independently of Alt+C.
- YouTube captions can appear before local model startup finishes; stale captions clear on pause, end, or silence.
- Panel and caption styling preserve each theme's identity. Remove portrait/demo circles; keep search closed until its button is pressed; keep folder/history controls reachable; remove unused lower space; retain scrolling and useful drag targets.
- Panel and caption windows can be dragged; 240 Hz is the polling ceiling, with repaint bounded by measured paint cost.
- History stores source-app and screen context, avoids duplicate lines without swallowing genuine repeats, supports search/export, and retains at least two months. Current code is configured for 180 days.
- Reduce model reload/startup stutter while honoring the rule that hiding captions only hides their display: worker, model, transcription, and history continue.

## Start from these existing records

Use the current tree and the five editable worklists; do not rely on lane transcripts:

- Panel: .agent-work/TODO-omp-panel-all-themes-20261109.md and TODO-omp-panel-all-themes-20261109.md
- Caption overlay/drag: .agent-work/TODO-omp-caption-overlay-design-drag-20261109.md and TODO-omp-caption-overlay-design-drag-20261109.md
- Ctrl+Space/YouTube: .agent-work/TODO-omp-ctrlspace-youtube-readiness-20261109.md
- History: .agent-work/TODO-omp-history-dedupe-recall-20261109.md
- Reload/CPU: .agent-work/TODO-omp-sotto-performance-20261109.md and _main/receipt-20261109-reload-floor.md
- Worker cost watchdog: _main/receipt-20261109-worker-cost-and-commit.md

The owner authorized searching their own OMP main-session complaints. Relevant message IDs previously identified: 615bf1f3, 52e29ca6, 130125f7, fc4f49a6, 5d36f388. Search only the owner's messages; do not read another lane's private transcript or reasoning.

## What already has source-level evidence

- Panel: all 59 theme entries pass the panel oracle; its negative arm catches 10/10. Header and drag-target gates pass with negative controls. Offscreen DOM evidence shows search/folder controls reachable, no lower void, 60-day history visible/searchable with stored context, and 200-day history excluded; retention negative control catches 6/6. Renders show distinct theme identities. Live window dragging and collapsed-history behavior are still open.
- Caption overlay: all 59 theme payloads pass the plate/face oracle; negative control catches 3/3. Drag plan passes 14/14, tick-thread gate 10/10, and hide/keep-model/history gate 14 arms; relevant negative controls catch their mutations. Offscreen renders were inspected. Delivered drag polling varied from 128–196 Hz in ordinary runs and fell to 27 Hz during heavy unrelated load; 240 Hz is a ceiling, not a guaranteed rate.
- Ctrl+Space/YouTube: source review and gates support independence from Alt+C, YouTube captions before WebView/model readiness, and clearing stale pixels on idle/pause/end without unloading the model or stopping history. The lane fixed gate defects. No live runtime claim is verified.
- History: merge, write, codec/context, retention/export gates pass; latest history-context result recorded after minimization is 102/102, negative 11/11, merge 32/32 with negative 2/2, write positive/negative pass, and the fixture confirms 60-day export with context. The panel's real-DOM retention probe passed under heavy lease 230bfe41f0ea4c84b2c631f0b5a06791.
- Reload/thread policy: load-shedding positive gate passes 252/252; its negative arm catches 25/25. Worker-thread limit passes 15/15; negative catches 11/11. Implemented policy is release only after 120 seconds of sustained memory pressure (emergency at 94%, 4-point hysteresis, 15-second reading-gap guard) and reload floor max(60 seconds, 10 x measured load time). CPU-only pressure keeps the engine loaded.
- Worker cost watchdog: receipt records a static/mechanism gate and negative control; it targets high CPU with no recognized work. Check the receipt and current oracle before claiming its final state.

## Work still to finish, in order

1. **Resolve the instruction/routing correction.** The owner objected to Herdr being treated as the default and asked to remove the behavior that made AGENTS.md update/routing happen this way. Trace the exact skill or instruction that caused it, then make the smallest justified correction. The current project instructions include a mandatory Herdr-pane section, while the owner's direction is to stay in the current harness and use Herdr only when cross-project coordination is actually needed. Do not use Herdr for this Sotto handoff. Do not make broad shared-skill edits without evidence of which skill caused the behavior.
2. **Close the cross-session history-context leak.** In app/webview/sotto_webview.py, _history_ctx_last and _history_ctx_last_start can be reused for a line from a new audio session when its start is within the 8-second near-match window. Add a session/time identity or clear the snapshot at the real session boundary. This file is primarily owned by the YouTube lane; coordinate the exact seam before editing. Extend the focused history oracle with a new-session negative case.
3. **Decide codec edge parity.** Python and Node differ on malformed percent escapes and whitespace U+0085/U+FEFF. Writers do not emit these today, but hand-edited records can. Either align both readers and add parity cases, or explicitly document why these inputs are outside the supported contract.
4. **Close code-health without hiding the regression.** Latest run this turn was CODE-HEALTH FAIL (exit 2), with 7 red metrics across app/webview/sotto_webview.py and worker/sotto_worker.py. The history minimization removed its earlier red growth. Inspect the current _main/code-health-baseline.json diff because it is already dirty. Prefer reducing growth in the owning files; do not refresh the baseline merely to turn the gate green without owner authorization. Also inspect the dirty exception baseline and undeclared worker/wasapi_loopback.py changes before closure.
5. **Finish integration and independent review.** No independent reviewer is recorded for the panel, caption, YouTube, history, or the latest performance-oracle edits. Review distinct subjects once each, after combining overlapping findings. Re-run each affected focused positive and negative gate against final bytes. If history-context-store.js is ever made cacheable in the battery, add it to the history-context dependencies first; those steps currently run always.
6. **Verify runtime only after a fresh owner-launched instance exists.** The latest strict freshness check was STALE (PID/start unresolved); older receipts identify PID 50452 as stale. Do not launch, restart, show, or synthesize input to the app. Once the owner opens a fresh instance, use the project's freshness and Watcher instruments to verify the same process/window: actual theme/search/drag behavior, caption hide/resume with model/history continuing, worker CPU/thread ceiling, startup and reload counts, and stutter before/after. Until then label runtime claims fixed, NOT verified.
7. **Close with a scoped receipt.** Recheck all 59 themes, history retention/context/search/export, caption and YouTube behavior, reload policy, code-health, battery wiring, current dirty-state attribution, and the freshness/runtime limitation. Preserve all existing dirty work; never reset/revert others' files.

## Performance facts that must remain accurate

The owner's DMs identify 82 model loads / 70 releases as the reload cycle. The “47 episodes” were 47 rankings, not 47 measured DMs; six DMs were measured. The 26 MB/s observation was associated with model reloads, not ordinary app I/O. Herdr's 900-second warning cooldown is not Sotto's reload floor. Do not change Sotto to a 15-minute floor based on that number.

Treat any freeze/stutter report as an order to make the work cheaper while it continues. The owner explicitly challenged an arbitrary five-minute timeout; no instruction here authorizes one. Do not idle or stop the work because of a self-invented timeout. Use the project's progress signal, Watcher governance, and declared per-stage budgets. Any runtime optimization claim needs the same process/thread and instrument before and after, plus evidence that useful work continued.

## Operating constraints

- Owner is using OMP directly. Do not create Luna/OMP relay work or start another agent lane as part of this handoff.
- Preserve every dirty file. The current tree has many concurrent edits, including AGENTS.md, code-health/exception baselines, panel, webview, worker, and oracle files; establish ownership from diffs/receipts before editing.
- No visible terminal, popup, browser, Sotto window, or foreground process. Do not launch/restart the Sotto app or inject input.
- Before any build, full battery, benchmark, indexing, or mutation campaign, check the central performance gate, obtain its exclusive heavy lease, and run the project artifact census. Reuse existing light focused gates where sufficient.
- Do not treat a skipped gate as a pass, or a source-level fix as runtime verification.
