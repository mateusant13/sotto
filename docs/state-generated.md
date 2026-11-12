# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=501 · PASS=252 · EXPECTED-RED=200 · FAIL=2 · STALE=27 · NO-VERDICT=1 · NOT RUN=19

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-12T04:02:21-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-11-05T14:40:17-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | PASS | 0 | 0 | 2026-11-12T02:53:25-0300 | pycompile-worker.log | - |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-11-12T02:53:26-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-11-09T20:43:51-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-11-11T02:58:45-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-11-11T11:29:42-0300 | oracle-historico-vs-redux.log | - |
| redux-transcript-path | PASS | 0 | 0 | 2026-11-12T04:02:25-0300 | redux-transcript-path.log | - |
| redux-arm-weights | PASS | 0 | 0 | 2026-11-12T04:02:26-0300 | redux-arm-weights.log | - |
| history-write | PASS | 0 | 0 | 2026-11-12T04:02:40-0300 | history-write.log | - |
| caption-cumulative | PASS | 0 | 0 | 2026-11-09T20:44:12-0300 | oracle-caption-cumulative.log | - |
| red-as-expected-caption-cumulative | EXPECTED-RED | 1 | 1 | 2026-11-09T20:44:13-0300 | caption-cumulative-neg.log | - |
| caption-lag-budget | PASS | 0 | 0 | 2026-11-12T04:02:41-0300 | caption-lag-budget.log | - |
| red-as-expected-caption-lag-budget | EXPECTED-RED | 1 | 1 | 2026-11-12T04:02:53-0300 | caption-lag-budget-neg.log | - |
| caption-rollup | PASS | 0 | 0 | 2026-11-12T02:54:41-0300 | caption-rollup.log | - |
| red-as-expected-caption-rollup | EXPECTED-RED | 1 | 1 | 2026-11-12T02:54:46-0300 | caption-rollup-neg.log | - |
| paint-cost | PASS | 0 | 0 | 2026-11-12T02:55:00-0300 | paint-cost.log | - |
| red-as-expected-paint-cost | EXPECTED-RED | 1 | 1 | 2026-11-12T02:55:07-0300 | paint-cost-neg.log | - |
| shell-thread-budget | PASS | 0 | 0 | 2026-11-12T04:02:57-0300 | shell-thread-budget.log | - |
| red-as-expected-shell-thread-budget | EXPECTED-RED | 1 | 1 | 2026-11-11T11:30:20-0300 | shell-thread-budget-neg.log | - |
| tree-cost | PASS | 0 | 0 | 2026-11-12T04:03:01-0300 | tree-cost.log | - |
| red-as-expected-tree-cost | EXPECTED-RED | 1 | 1 | 2026-11-11T11:30:23-0300 | tree-cost-neg.log | - |
| engine-serialization | PASS | 0 | 0 | 2026-11-12T02:55:21-0300 | engine-serialization.log | - |
| red-as-expected-engine-serialization | EXPECTED-RED | 1 | 1 | 2026-11-12T02:55:50-0300 | engine-serialization-neg.log | - |
| ort-spin-idle | PASS | 0 | 0 | 2026-11-12T02:56:04-0300 | ort-spin-idle.log | - |
| red-as-expected-ort-spin-idle | EXPECTED-RED | 1 | 1 | 2026-11-12T02:56:32-0300 | ort-spin-idle-neg.log | - |
| worker-thread-limit | PASS | 0 | 0 | 2026-11-12T04:03:05-0300 | worker-thread-limit.log | - |
| red-as-expected-worker-thread-limit | EXPECTED-RED | 1 | 1 | 2026-11-12T04:03:07-0300 | worker-thread-limit-neg.log | - |
| caption-tick-thread | PASS | 0 | 0 | 2026-11-11T11:30:28-0300 | caption-tick-thread.log | - |
| red-as-expected-caption-tick-thread | EXPECTED-RED | 1 | 1 | 2026-11-11T11:30:32-0300 | caption-tick-thread-neg.log | - |
| log-sink-dead | PASS | 0 | 0 | 2026-11-12T04:03:07-0300 | log-sink-dead.log | - |
| red-as-expected-log-sink-dead | EXPECTED-RED | 1 | 1 | 2026-11-12T04:03:29-0300 | log-sink-dead-neg.log | - |
| cdp-target-async | PASS | 0 | 0 | 2026-11-12T04:03:32-0300 | cdp-target-async.log | - |
| red-as-expected-cdp-target-async | EXPECTED-RED | 1 | 1 | 2026-11-12T04:03:45-0300 | cdp-target-async-neg.log | - |
| caption-drag | PASS | 0 | 0 | 2026-11-11T11:31:14-0300 | caption-drag.log | - |
| red-as-expected-caption-drag | EXPECTED-RED | 1 | 1 | 2026-11-11T11:31:20-0300 | caption-drag-neg.log | - |
| lag-note-cost | PASS | 0 | 0 | 2026-11-12T14:35:17-0300 | lag-note-cost.log | always |
| red-as-expected-lag-note-cost | EXPECTED-RED | 1 | 1 | 2026-11-12T14:35:19-0300 | lag-note-cost-neg.log | always |
| youtube-hidden-clock | PASS | 0 | 0 | 2026-11-12T14:35:25-0300 | youtube-hidden-clock.log | always |
| red-as-expected-youtube-hidden-clock | EXPECTED-RED | 1 | 1 | 2026-11-12T14:35:28-0300 | youtube-hidden-clock-neg.log | always |
| caption-overlay-screen | PASS | 0 | 0 | 2026-11-12T14:35:29-0300 | caption-overlay-screen.log | always |
| red-as-expected-caption-overlay-screen | EXPECTED-RED | 1 | 1 | 2026-11-12T14:35:30-0300 | caption-overlay-screen-neg.log | always |
| youtube-cdp-boot | PASS | 0 | 0 | 2026-11-12T14:35:37-0300 | youtube-cdp-boot.log | always |
| red-as-expected-youtube-cdp-boot | EXPECTED-RED | 1 | 1 | 2026-11-12T14:36:06-0300 | youtube-cdp-boot-neg.log | always |
| youtube-cdp-slow | PASS | 0 | 0 | 2026-11-12T14:36:12-0300 | youtube-cdp-slow.log | always |
| red-as-expected-youtube-cdp-slow | EXPECTED-RED | 1 | 1 | 2026-11-12T14:36:33-0300 | youtube-cdp-slow-neg.log | always |
| youtube-first-at-boot | PASS | 0 | 0 | 2026-11-12T14:36:48-0300 | youtube-first-at-boot.log | always |
| red-as-expected-youtube-first-at-boot | EXPECTED-RED | 1 | 1 | 2026-11-12T14:37:32-0300 | youtube-first-at-boot-neg.log | always |
| red-as-expected-redux-transcript-path | EXPECTED-RED | 1 | 1 | 2026-11-12T04:05:54-0300 | redux-transcript-path-neg.log | - |
| red-as-expected-history-write | EXPECTED-RED | 1 | 1 | 2026-11-12T04:05:59-0300 | history-write-neg.log | - |
| control-verdict-gate-drop-redux-live | PASS | 0 | 0 | 2026-11-12T03:00:20-0300 | control-verdict-gate-drop-redux-live.log | - |
| history-producer-gate | PASS | 0 | 0 | 2026-11-12T03:00:22-0300 | gate-history-producer.log | - |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-11-11T02:55:56-0300 | gate-panel-state-guard.log | - |
| verdict-gate | PASS | 0 | 0 | 2026-11-12T03:00:23-0300 | gate-verdict.log | - |
| worker-park | PASS | 0 | 0 | 2026-11-12T14:38:08-0300 | worker-park.log | always |
| red-as-expected-worker-park | EXPECTED-RED | 1 | 1 | 2026-11-12T14:38:09-0300 | worker-park-neg.log | always |
| lane2-reset-probe | PASS | 0 | 0 | 2026-11-11T02:56:37-0300 | lane2-reset.log | - |
| lane3-verdict-probe | PASS | 0 | 0 | 2026-11-12T03:01:07-0300 | lane3-verdict.log | - |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-11-12T03:01:10-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-11-11T02:56:48-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-11-11T02:56:53-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-11-05T14:47:02-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-11-11T02:57:08-0300 | panel2-dom-probe.log | - |
| panel-header-oracle | PASS | 0 | 0 | 2026-11-11T02:57:14-0300 | panel-header.log | - |
| red-as-expected-panel-header-oracle | EXPECTED-RED | 1 | 1 | 2026-11-11T03:05:56-0300 | panel-header-neg.log | - |
| panel-drag-targets | PASS | 0 | 0 | 2026-11-11T03:05:58-0300 | panel-drag-targets.log | - |
| panel-history-clip | PASS | 0 | 0 | 2026-11-12T04:06:40-0300 | panel-history-clip.log | - |
| window-drag | PASS | 0 | 0 | 2026-11-12T04:07:10-0300 | window-drag.log | - |
| red-as-expected-window-drag | EXPECTED-RED | 1 | 1 | 2026-11-12T04:08:03-0300 | window-drag-neg.log | - |
| panel-history-wheel | PASS | 0 | 0 | 2026-11-11T03:07:05-0300 | panel-history-wheel.log | - |
| red-as-expected-panel-history-wheel | EXPECTED-RED | 1 | 1 | 2026-11-11T03:07:10-0300 | panel-history-wheel-neg.log | - |
| theme-caption-identity | PASS | 0 | 0 | 2026-11-11T11:38:20-0300 | theme-caption-identity.log | - |
| caption-plate | PASS | 0 | 0 | 2026-11-12T04:08:05-0300 | caption-plate.log | - |
| red-as-expected-caption-plate | EXPECTED-RED | 1 | 1 | 2026-11-12T04:08:08-0300 | caption-plate-neg.log | - |
| caption-visual-dom | PASS | 0 | 0 | 2026-11-11T03:07:17-0300 | caption-visual-dom.log | - |
| red-as-expected-caption-visual-dom | EXPECTED-RED | 1 | 1 | 2026-11-11T03:07:19-0300 | caption-visual-dom-neg.log | - |
| youtube-cdp-latency | PASS | 0 | 0 | 2026-11-12T04:08:12-0300 | youtube-cdp-latency.log | - |
| red-as-expected-youtube-cdp-latency | EXPECTED-RED | 1 | 1 | 2026-11-12T04:08:29-0300 | youtube-cdp-latency-neg.log | - |
| caption-noise | PASS | 0 | 0 | 2026-11-12T03:03:29-0300 | caption-noise.log | - |
| red-as-expected-theme-caption-identity | EXPECTED-RED | 1 | 1 | 2026-11-11T11:38:31-0300 | theme-caption-identity-neg.log | - |
| caption-overlay-theme | PASS | 0 | 0 | 2026-11-12T04:08:38-0300 | caption-overlay-theme.log | - |
| red-as-expected-caption-overlay-theme | EXPECTED-RED | 1 | 1 | 2026-11-12T04:08:59-0300 | caption-overlay-theme-neg.log | - |
| panel-themes | PASS | 0 | 0 | 2026-11-11T03:08:31-0300 | panel-themes.log | - |
| red-as-expected-panel-themes | EXPECTED-RED | 1 | 1 | 2026-11-11T03:10:04-0300 | panel-themes-neg.log | - |
| red-as-expected-panel-history-clip | EXPECTED-RED | 1 | 1 | 2026-11-12T04:09:09-0300 | panel-history-clip-neg.log | - |
| panel-pause-payload | PASS | 0 | 0 | 2026-11-12T04:09:11-0300 | panel-pause-payload.log | - |
| red-as-expected-panel-pause-payload | EXPECTED-RED | 1 | 1 | 2026-11-12T04:09:12-0300 | panel-pause-payload-neg.log | - |
| measurement-flags | PASS | 0 | 0 | 2026-11-12T14:38:19-0300 | measurement-flags.log | - |
| red-as-expected-measurement-flags | EXPECTED-RED | 1 | 1 | 2026-11-12T14:38:57-0300 | measurement-flags-neg.log | - |
| measurement-isolation | PASS | 0 | 0 | 2026-11-12T04:09:55-0300 | measurement-isolation.log | - |
| red-as-expected-measurement-isolation | EXPECTED-RED | 1 | 1 | 2026-11-12T03:05:04-0300 | measurement-isolation-neg.log | - |
| caption-wanted-default | PASS | 0 | 0 | 2026-11-12T03:05:05-0300 | caption-wanted-default.log | - |
| red-as-expected-caption-wanted-default | EXPECTED-RED | 1 | 1 | 2026-11-12T03:05:09-0300 | caption-wanted-default-neg.log | - |
| live-ack | PASS | 0 | 0 | 2026-11-12T04:10:05-0300 | live-ack.log | - |
| red-as-expected-live-ack | EXPECTED-RED | 1 | 1 | 2026-11-12T04:11:07-0300 | live-ack-neg.log | - |
| live-route | PASS | 0 | 0 | 2026-11-12T03:05:26-0300 | live-route.log | - |
| red-as-expected-live-route | EXPECTED-RED | 1 | 1 | 2026-11-12T03:05:28-0300 | live-route-neg.log | - |
| device-ladder-cost | PASS | 0 | 0 | 2026-11-12T03:05:29-0300 | device-ladder-cost.log | - |
| red-as-expected-device-ladder-cost | EXPECTED-RED | 1 | 1 | 2026-11-12T03:05:34-0300 | device-ladder-cost-neg.log | - |
| youtube-first-cue | PASS | 0 | 0 | 2026-11-12T03:05:37-0300 | youtube-first-cue.log | - |
| red-as-expected-youtube-first-cue | EXPECTED-RED | 1 | 1 | 2026-11-12T03:05:45-0300 | youtube-first-cue-neg.log | - |
| yt-clock-static | PASS | 0 | 0 | 2026-11-12T03:05:50-0300 | yt-clock-static.log | - |
| red-as-expected-yt-clock-static | EXPECTED-RED | 1 | 1 | 2026-11-12T03:05:54-0300 | yt-clock-static-neg.log | - |
| startup-ui-thread-block | PASS | 0 | 0 | 2026-11-12T14:39:16-0300 | startup-ui-thread-block.log | - |
| red-as-expected-startup-ui-thread-block | EXPECTED-RED | 1 | 1 | 2026-11-12T14:39:36-0300 | startup-ui-thread-block-neg.log | - |
| cost-watchdog | PASS | 0 | 0 | 2026-11-12T03:06:12-0300 | cost-watchdog.log | - |
| red-as-expected-cost-watchdog | EXPECTED-RED | 1 | 1 | 2026-11-12T03:06:19-0300 | cost-watchdog-neg.log | - |
| warm-evidence | PASS | 0 | 0 | 2026-11-12T03:06:26-0300 | warm-evidence.log | - |
| red-as-expected-warm-evidence | EXPECTED-RED | 1 | 1 | 2026-11-12T03:06:31-0300 | warm-evidence-neg.log | - |
| ui-watchdog | PASS | 0 | 0 | 2026-11-12T03:06:38-0300 | ui-watchdog.log | - |
| red-as-expected-ui-watchdog | EXPECTED-RED | 1 | 1 | 2026-11-12T03:06:45-0300 | ui-watchdog-neg.log | - |
| outside-click-timer | PASS | 0 | 0 | 2026-11-12T03:07:06-0300 | outside-click-timer.log | - |
| red-as-expected-outside-click-timer | EXPECTED-RED | 1 | 1 | 2026-11-12T03:07:27-0300 | outside-click-timer-neg.log | - |
| panel-deps | STALE | 0 | 0 | 2026-11-12T14:39:39-0300 | panel-deps.log | deps mudaram depois da medicao (medido 2026-11-12T14:39:39-0300) |
| red-as-expected-panel-deps | STALE | 0 | 0 | 2026-11-12T14:39:39-0300 | panel-deps-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:39:39-0300) |
| worker-death-trace | PASS | 0 | 0 | 2026-11-12T03:07:38-0300 | worker-death-trace.log | - |
| red-as-expected-worker-death-trace | EXPECTED-RED | 1 | 1 | 2026-11-12T03:07:42-0300 | worker-death-trace-neg.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-11-11T03:11:41-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-11-11T03:11:41-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-11-11T03:11:42-0300 | border-radius-gate-neg.log | - |
| hidden-launch | PASS | 0 | 0 | 2026-11-05T14:47:36-0300 | hidden-launch.log | - |
| red-as-expected-hidden-launch | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:37-0300 | hidden-launch-neg.log | - |
| step-deadline | PASS | 0 | 0 | 2026-11-12T04:11:51-0300 | step-deadline.log | - |
| red-as-expected-step-deadline | EXPECTED-RED | 1 | 1 | 2026-11-12T04:12:04-0300 | step-deadline-neg.log | - |
| emit-prewebview | PASS | 0 | 0 | 2026-11-12T03:07:47-0300 | emit-prewebview.log | - |
| red-as-expected-emit-prewebview | EXPECTED-RED | 1 | 1 | 2026-11-12T03:07:51-0300 | emit-prewebview-neg.log | - |
| hotkey-live-edge | PASS | 0 | 0 | 2026-11-12T03:07:59-0300 | hotkey-live-edge.log | - |
| red-as-expected-hotkey-live-edge | EXPECTED-RED | 1 | 1 | 2026-11-12T03:08:08-0300 | hotkey-live-edge-neg.log | - |
| lane-screen-gate | STALE | 0 | 0 | 2026-11-12T14:39:56-0300 | lane-screen-gate.log | deps mudaram depois da medicao (medido 2026-11-12T14:39:56-0300) |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:29-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-12T03:08:25-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-11-05T14:48:31-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:31-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-12T03:08:27-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-12T03:08:28-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | PASS | 0 | 0 | 2026-11-12T03:08:32-0300 | youtube-foreign-paint.log | - |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-12T03:08:35-0300 | youtube-foreign-paint-neg.log | - |
| input-path | PASS | 0 | 0 | 2026-11-12T03:09:12-0300 | input-path.log | - |
| red-as-expected-input-path | EXPECTED-RED | 1 | 1 | 2026-11-12T03:09:17-0300 | input-path-neg.log | - |
| exception-hygiene | PASS | 0 | 0 | 2026-11-12T04:12:19-0300 | exception-hygiene.log | - |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-12T04:13:00-0300 | exception-hygiene-neg.log | - |
| seam-coverage | PASS | 0 | 0 | 2026-11-12T03:10:10-0300 | seam-coverage.log | - |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:13-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-05T14:50:14-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:15-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-05T19:44:31-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-05T19:44:32-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-12T03:10:12-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-12T03:10:16-0300 | external-resume-neg.log | - |
| external-resume-latch | PASS | 0 | 0 | 2026-11-12T03:10:17-0300 | external-resume-latch.log | - |
| red-as-expected-external-resume-latch | EXPECTED-RED | 1 | 1 | 2026-11-12T03:10:19-0300 | external-resume-latch-neg.log | - |
| silence-kill | PASS | 0 | 0 | 2026-11-12T03:10:21-0300 | silence-kill.log | - |
| red-as-expected-silence-kill | EXPECTED-RED | 1 | 1 | 2026-11-12T03:10:22-0300 | silence-kill-neg.log | - |
| worker-churn | PASS | 0 | 0 | 2026-11-12T03:10:28-0300 | worker-churn.log | - |
| red-as-expected-worker-churn | EXPECTED-RED | 1 | 1 | 2026-11-12T03:10:37-0300 | worker-churn-neg.log | - |
| worker-silence-grace | PASS | 0 | 0 | 2026-11-12T03:10:41-0300 | worker-silence-grace.log | - |
| red-as-expected-worker-silence-grace | EXPECTED-RED | 1 | 1 | 2026-11-12T03:10:42-0300 | worker-silence-grace-neg.log | - |
| rss-trend | PASS | 0 | 0 | 2026-11-12T03:10:43-0300 | rss-trend.log | - |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:32-0300 | rss-trend-neg.log | - |
| death-cause | PASS | 0 | 0 | 2026-11-12T03:10:45-0300 | death-cause.log | - |
| red-as-expected-death-cause | EXPECTED-RED | 1 | 1 | 2026-11-12T03:10:48-0300 | death-cause-neg.log | - |
| caption-seam-dedup | PASS | 0 | 0 | 2026-11-12T03:10:50-0300 | caption-seam-dedup.log | - |
| red-as-expected-caption-seam-dedup | EXPECTED-RED | 1 | 1 | 2026-11-12T03:10:56-0300 | caption-seam-dedup-neg.log | - |
| freeze-census | PASS | 0 | 0 | 2026-11-11T03:14:20-0300 | freeze-census.log | - |
| red-as-expected-caption-budget | EXPECTED-RED | 1 | 1 | 2026-11-12T03:11:02-0300 | caption-budget-neg.log | - |
| dead-app-exit | PASS | 0 | 0 | 2026-11-12T03:11:27-0300 | dead-app-exit.log | - |
| exit-backstop | PASS | 0 | 0 | 2026-11-12T03:11:34-0300 | exit-backstop.log | - |
| red-as-expected-exit-backstop | NO-VERDICT | 1 | 1 | 2026-11-12T03:11:56-0300 | exit-backstop-neg.log | registo com expect_rc=0 mas a bateria declara 1 |
| shell-priority | PASS | 0 | 0 | 2026-11-12T03:11:58-0300 | shell-priority.log | - |
| red-as-expected-shell-priority | EXPECTED-RED | 1 | 1 | 2026-11-12T03:11:59-0300 | shell-priority-neg.log | - |
| tray-menu | PASS | 0 | 0 | 2026-11-12T03:12:01-0300 | tray-menu.log | - |
| red-as-expected-tray-menu | EXPECTED-RED | 1 | 1 | 2026-11-12T03:12:11-0300 | tray-menu-neg.log | - |
| hotkey-panels-switch | PASS | 0 | 0 | 2026-11-12T03:12:13-0300 | hotkey-panels-switch.log | - |
| red-as-expected-hotkey-panels-switch | EXPECTED-RED | 1 | 1 | 2026-11-12T03:12:17-0300 | hotkey-panels-switch-neg.log | - |
| caption-kept-on-hide | PASS | 0 | 0 | 2026-11-12T04:13:26-0300 | caption-kept-on-hide.log | - |
| red-as-expected-caption-kept-on-hide | EXPECTED-RED | 1 | 1 | 2026-11-12T04:13:37-0300 | caption-kept-on-hide-neg.log | - |
| caption-switch-race | PASS | 0 | 0 | 2026-11-12T04:13:40-0300 | caption-switch-race.log | - |
| red-as-expected-caption-switch-race | EXPECTED-RED | 1 | 1 | 2026-11-12T04:13:41-0300 | caption-switch-race-neg.log | - |
| word-glue | PASS | 0 | 0 | 2026-11-12T03:12:30-0300 | word-glue.log | - |
| red-as-expected-word-glue | EXPECTED-RED | 1 | 1 | 2026-11-12T03:12:31-0300 | word-glue-neg.log | - |
| punct-prosody | PASS | 0 | 0 | 2026-11-05T19:45:18-0300 | punct-prosody.log | - |
| red-as-expected-punct-prosody | EXPECTED-RED | 1 | 1 | 2026-11-05T19:45:19-0300 | punct-prosody-neg.log | - |
| punct-model | PASS | 0 | 0 | 2026-11-12T03:12:35-0300 | punct-model.log | - |
| red-as-expected-punct-model | EXPECTED-RED | 1 | 1 | 2026-11-12T03:12:38-0300 | punct-model-neg.log | - |
| panel-prefix-row | PASS | 0 | 0 | 2026-11-11T03:14:55-0300 | panel-prefix-row.log | - |
| red-as-expected-panel-prefix-row | EXPECTED-RED | 1 | 1 | 2026-11-11T03:14:55-0300 | panel-prefix-row-neg.log | - |
| fusion | PASS | 0 | 0 | 2026-11-05T14:51:09-0300 | fusion.log | - |
| red-as-expected-fusion | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:09-0300 | fusion-neg.log | - |
| agc-peak-ceiling | PASS | 0 | 0 | 2026-11-12T03:12:40-0300 | agc-peak-ceiling.log | - |
| red-as-expected-agc-peak-ceiling | EXPECTED-RED | 1 | 1 | 2026-11-12T03:12:43-0300 | agc-peak-ceiling-neg.log | - |
| reveal-park | PASS | 0 | 0 | 2026-11-12T03:12:46-0300 | reveal-park.log | - |
| red-as-expected-reveal-park | EXPECTED-RED | 1 | 1 | 2026-11-12T03:12:53-0300 | reveal-park-neg.log | - |
| youtube-verbatim | PASS | 0 | 0 | 2026-11-12T03:12:57-0300 | youtube-verbatim.log | - |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:52-0300 | youtube-verbatim-neg.log | - |
| code-health | PASS | 0 | 0 | 2026-11-12T14:40:10-0300 | code-health.log | always |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-12T14:40:13-0300 | code-health-neg.log | always |
| undefined-names | PASS | 0 | 0 | 2026-11-12T14:40:15-0300 | undefined-names.log | always |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-12T14:40:16-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | STALE | 0 | 0 | 2026-11-12T14:40:21-0300 | battery-heavy-gate.log | deps mudaram depois da medicao (medido 2026-11-12T14:40:21-0300) |
| red-as-expected-battery-heavy-gate | STALE | 1 | 1 | 2026-11-12T14:40:36-0300 | battery-heavy-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:40:36-0300) |
| task-resolver-gate | STALE | 0 | 0 | 2026-11-12T14:40:38-0300 | task-resolver-gate.log | deps mudaram depois da medicao (medido 2026-11-12T14:40:38-0300) |
| red-as-expected-task-resolver-gate | STALE | 1 | 1 | 2026-11-12T14:40:39-0300 | task-resolver-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:40:39-0300) |
| claims-date | STALE | 0 | 0 | 2026-11-12T14:40:40-0300 | claims-date.log | deps mudaram depois da medicao (medido 2026-11-12T14:40:40-0300) |
| red-as-expected-claims-date | STALE | 1 | 1 | 2026-11-12T14:40:42-0300 | claims-date-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:40:42-0300) |
| stall-under-load | PASS | 0 | 0 | 2026-11-12T14:40:43-0300 | stall-under-load.log | always |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-12T14:40:44-0300 | stall-under-load-neg.log | always |
| paint-live-show | PASS | 0 | 0 | 2026-11-12T14:40:45-0300 | paint-live-show.log | always |
| boot-interaction | PASS | 0 | 0 | 2026-11-12T14:40:46-0300 | boot-interaction.log | always |
| red-as-expected-boot-interaction | EXPECTED-RED | 1 | 1 | 2026-11-12T14:40:47-0300 | boot-interaction-neg.log | always |
| boot-interaction-paint-arm | EXPECTED-RED | 1 | 1 | 2026-11-12T14:40:48-0300 | boot-interaction-paint-arm.log | always |
| red-as-expected-paint-live-show | EXPECTED-RED | 1 | 1 | 2026-11-12T14:41:39-0300 | paint-live-show-neg.log | always |
| content-gate-probe | EXPECTED-RED | 1 | 1 | 2026-11-12T14:41:44-0300 | content-gate-probe-neg.log | always |
| panel-paint-first-measure | NOT RUN | - | 0 | - | panel-paint-first-measure.log | sem registo no stepcache (o passo nao completou) |
| panel-paint-first | PASS | 0 | 0 | 2026-11-12T14:41:46-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-12T14:41:47-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-12T14:41:48-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-12T14:41:49-0300 | receipt-provenance-neg.log | always |
| async-track-fetch | PASS | 0 | 0 | 2026-11-12T03:15:16-0300 | async-track-fetch.log | - |
| red-as-expected-async-track-fetch | EXPECTED-RED | 1 | 1 | 2026-11-12T03:15:25-0300 | async-track-fetch-neg.log | - |
| batch-queue-drain | PASS | 0 | 0 | 2026-11-12T14:41:54-0300 | batch-queue-drain.log | - |
| red-as-expected-batch-queue-drain | EXPECTED-RED | 1 | 1 | 2026-11-12T14:42:05-0300 | batch-queue-drain-neg.log | - |
| batch-executor-ceiling | PASS | 0 | 0 | 2026-11-12T14:42:10-0300 | batch-executor-ceiling.log | - |
| red-as-expected-batch-executor-ceiling | EXPECTED-RED | 1 | 1 | 2026-11-12T14:42:12-0300 | batch-executor-ceiling-neg.log | - |
| hotkey-live-toggle | PASS | 0 | 0 | 2026-11-12T03:15:33-0300 | hotkey-live-toggle.log | - |
| red-as-expected-hotkey-live-toggle | EXPECTED-RED | 1 | 1 | 2026-11-12T03:16:13-0300 | hotkey-live-toggle-neg.log | - |
| hotkey-spam | PASS | 0 | 0 | 2026-11-12T03:16:19-0300 | hotkey-spam.log | - |
| red-as-expected-hotkey-spam | EXPECTED-RED | 1 | 1 | 2026-11-12T03:16:33-0300 | hotkey-spam-neg.log | - |
| loading-placeholder | PASS | 0 | 0 | 2026-11-12T03:16:34-0300 | loading-placeholder.log | - |
| red-as-expected-loading-placeholder | EXPECTED-RED | 1 | 1 | 2026-11-12T03:16:35-0300 | loading-placeholder-neg.log | - |
| youtube-land | PASS | 0 | 0 | 2026-11-12T14:42:14-0300 | youtube-land.log | always |
| red-as-expected-youtube-land | EXPECTED-RED | 1 | 1 | 2026-11-11T03:16:17-0300 | youtube-land-neg.log | - |
| time-to-first-caption | PASS | 0 | 0 | 2026-11-12T14:42:15-0300 | time-to-first-caption.log | always |
| red-as-expected-time-to-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-11T03:16:18-0300 | time-to-first-caption-neg.log | - |
| first-capture-fast | PASS | 0 | 0 | 2026-11-12T14:42:16-0300 | first-capture-fast.log | always |
| red-as-expected-first-capture-fast | EXPECTED-RED | 1 | 1 | 2026-11-12T03:16:47-0300 | first-capture-fast-neg.log | - |
| youtube-land-replay | PASS | 0 | 0 | 2026-11-12T04:15:57-0300 | youtube-land-replay.log | - |
| red-as-expected-youtube-land-replay | EXPECTED-RED | 1 | 1 | 2026-11-12T04:16:02-0300 | youtube-land-replay-neg.log | - |
| yt-loop-uia | PASS | 0 | 0 | 2026-11-12T03:16:51-0300 | yt-loop-uia.log | - |
| red-as-expected-yt-loop-uia | EXPECTED-RED | 1 | 1 | 2026-11-12T03:16:53-0300 | yt-loop-uia-neg.log | - |
| yt-target-stale | PASS | 0 | 0 | 2026-11-12T04:16:09-0300 | yt-target-stale.log | - |
| red-as-expected-yt-target-stale | EXPECTED-RED | 1 | 1 | 2026-11-12T04:16:14-0300 | yt-target-stale-neg.log | - |
| yt-source-singleton | PASS | 0 | 0 | 2026-11-12T03:17:01-0300 | yt-source-singleton.log | - |
| red-as-expected-yt-source-singleton | EXPECTED-RED | 1 | 1 | 2026-11-12T03:17:04-0300 | yt-source-singleton-neg.log | - |
| cpu-tripwire | PASS | 0 | 0 | 2026-11-11T03:16:27-0300 | cpu-tripwire.log | - |
| red-as-expected-cpu-tripwire | EXPECTED-RED | 1 | 1 | 2026-11-11T03:16:27-0300 | cpu-tripwire-neg.log | - |
| owner-screen | PASS | 0 | 0 | 2026-11-12T03:17:12-0300 | owner-screen.log | - |
| red-as-expected-owner-screen | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:38-0300 | owner-screen-neg.log | - |
| job-object | PASS | 0 | 0 | 2026-11-05T14:53:42-0300 | job-object.log | - |
| red-as-expected-job-object | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:45-0300 | job-object-neg.log | - |
| emit-pipe-dead | PASS | 0 | 0 | 2026-11-12T03:17:13-0300 | emit-pipe-dead.log | - |
| red-as-expected-emit-pipe-dead | EXPECTED-RED | 1 | 1 | 2026-11-12T03:17:14-0300 | emit-pipe-dead-neg.log | - |
| state-page-write | STALE | 0 | 0 | 2026-11-12T14:42:21-0300 | state-page-write.log | deps mudaram depois da medicao (medido 2026-11-12T14:42:21-0300) |
| state-page | STALE | 0 | 0 | 2026-11-12T14:42:26-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-12T14:42:26-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-12T14:43:03-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:43:03-0300) |
| battery-wiring | STALE | 0 | 0 | 2026-11-12T14:43:05-0300 | battery-wiring.log | deps mudaram depois da medicao (medido 2026-11-12T14:43:05-0300) |
| red-as-expected-battery-wiring | STALE | 1 | 1 | 2026-11-12T14:43:17-0300 | battery-wiring-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:43:17-0300) |
| battery-record-pairing | STALE | 0 | 0 | 2026-11-12T14:43:18-0300 | battery-record-pairing.log | deps mudaram depois da medicao (medido 2026-11-12T14:43:18-0300) |
| red-as-expected-battery-record-pairing | STALE | 1 | 1 | 2026-11-12T14:43:18-0300 | battery-record-pairing-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:43:18-0300) |
| cage-rc | STALE | 0 | 0 | 2026-11-12T14:43:19-0300 | cage-rc.log | deps mudaram depois da medicao (medido 2026-11-12T14:43:19-0300) |
| red-as-expected-cage-rc | STALE | 1 | 1 | 2026-11-12T14:43:20-0300 | cage-rc-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:43:20-0300) |
| battery-run | PASS | 0 | 0 | 2026-11-12T14:43:21-0300 | battery-run.log | - |
| red-as-expected-battery-run | EXPECTED-RED | 1 | 1 | 2026-11-12T14:43:22-0300 | battery-run-neg.log | - |
| spec-citations | NOT RUN | - | 0 | - | spec-citations.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-spec-citations | NOT RUN | - | 1 | - | spec-citations-neg.log | sem registo no stepcache (o passo nao completou) |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-12T14:43:35-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-12T14:43:38-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | PASS | 0 | 0 | 2026-11-12T14:43:41-0300 | youtube-1to1.log | always |
| red-as-expected-youtube-1to1 | EXPECTED-RED | 1 | 1 | 2026-11-12T14:43:45-0300 | youtube-1to1-neg.log | always |
| youtube-cdp-source | PASS | 0 | 0 | 2026-11-12T14:43:53-0300 | youtube-cdp-source.log | always |
| red-as-expected-youtube-cdp-source | EXPECTED-RED | 1 | 1 | 2026-11-12T14:45:47-0300 | youtube-cdp-source-neg.log | always |
| caption-producer | PASS | 0 | 0 | 2026-11-12T14:45:48-0300 | caption-producer.log | always |
| red-as-expected-caption-producer | EXPECTED-RED | 1 | 1 | 2026-11-12T14:45:49-0300 | caption-producer-neg.log | always |
| caption-style | PASS | 0 | 0 | 2026-11-12T14:45:50-0300 | caption-style.log | always |
| red-as-expected-caption-style | EXPECTED-RED | 1 | 1 | 2026-11-12T14:45:52-0300 | caption-style-neg.log | always |
| panel-commit-stable | PASS | 0 | 0 | 2026-11-12T14:46:04-0300 | panel-commit-stable.log | always |
| red-as-expected-panel-commit-stable | EXPECTED-RED | 1 | 1 | 2026-11-12T14:46:27-0300 | panel-commit-stable-neg.log | always |
| paint-row-seam | PASS | 0 | 0 | 2026-11-12T14:46:28-0300 | paint-row-seam.log | always |
| red-as-expected-paint-row-seam | EXPECTED-RED | 1 | 1 | 2026-11-12T14:46:28-0300 | paint-row-seam-neg.log | always |
| load-bg-window | PASS | 0 | 0 | 2026-11-12T14:46:29-0300 | load-bg-window.log | always |
| red-as-expected-load-bg-window | EXPECTED-RED | 1 | 1 | 2026-11-12T14:46:31-0300 | load-bg-window-neg.log | always |
| page-scan-browser | PASS | 0 | 0 | 2026-11-12T14:46:32-0300 | page-scan-browser.log | always |
| red-as-expected-page-scan-browser | EXPECTED-RED | 1 | 1 | 2026-11-12T14:46:33-0300 | page-scan-browser-neg.log | always |
| paused-pace | PASS | 0 | 0 | 2026-11-12T14:46:37-0300 | paused-pace.log | always |
| red-as-expected-paused-pace | EXPECTED-RED | 1 | 1 | 2026-11-12T14:46:46-0300 | paused-pace-neg.log | always |
| stutter-caption | PASS | 0 | 0 | 2026-11-12T14:46:50-0300 | stutter-caption.log | always |
| red-as-expected-stutter-caption | EXPECTED-RED | 1 | 1 | 2026-11-12T14:47:05-0300 | stutter-caption-neg.log | always |
| parakeet-ultra | NOT RUN | - | 0 | - | parakeet-ultra.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-parakeet-ultra | EXPECTED-RED | 1 | 1 | 2026-11-12T14:47:07-0300 | parakeet-ultra-neg.log | always |
| hotkey-observed | PASS | 0 | 0 | 2026-11-12T14:47:13-0300 | hotkey-observed.log | always |
| red-as-expected-hotkey-observed | EXPECTED-RED | 1 | 1 | 2026-11-12T14:47:14-0300 | hotkey-observed-neg.log | always |
| youtube-reveal | PASS | 0 | 0 | 2026-11-12T14:47:17-0300 | youtube-reveal.log | always |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-12T14:47:19-0300 | youtube-reveal-neg.log | always |
| youtube-rows | PASS | 0 | 0 | 2026-11-12T14:47:21-0300 | youtube-rows.log | always |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-12T14:47:23-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-12T14:47:25-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-12T14:47:25-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-12T14:47:48-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-12T14:47:49-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-12T14:47:49-0300 | bend-laws-model-neg.log | always |
| bend-mirror | PASS | 0 | 0 | 2026-11-12T14:47:50-0300 | bend-mirror.log | always |
| red-as-expected-bend-mirror | EXPECTED-RED | 1 | 1 | 2026-11-12T14:47:52-0300 | bend-mirror-neg.log | always |
| bend-ledger-selftest | PASS | 0 | 0 | 2026-11-12T14:47:52-0300 | bend-ledger-selftest.log | always |
| panel-hidden-at-startup-oracle | PASS | 0 | 0 | 2026-11-12T14:48:56-0300 | panel-hidden-at-startup.log | - |
| red-as-expected-panel-hidden-at-startup | EXPECTED-RED | 1 | 1 | 2026-11-12T14:48:59-0300 | panel-hidden-at-startup-neg.log | - |
| panel-nav-stall | PASS | 0 | 0 | 2026-11-12T03:27:55-0300 | panel-nav-stall.log | - |
| red-as-expected-panel-nav-stall | EXPECTED-RED | 1 | 1 | 2026-11-12T03:27:58-0300 | panel-nav-stall-neg.log | - |
| app-target | PASS | 0 | 0 | 2026-11-12T14:49:08-0300 | app-target.log | always |
| red-as-expected-app-target | EXPECTED-RED | 1 | 1 | 2026-11-12T14:49:10-0300 | app-target-neg.log | always |
| worker-start-wiring | PASS | 0 | 0 | 2026-11-12T03:28:05-0300 | wiring-worker-start.log | - |
| red-as-expected-worker-start-wiring | EXPECTED-RED | 1 | 1 | 2026-11-12T03:28:07-0300 | wiring-worker-start-neg.log | - |
| embedded-js-check | PASS | 0 | 0 | 2026-11-12T03:28:10-0300 | embedded-js.log | - |
| lane1-worker-default-arms | PASS | 0 | 0 | 2026-11-12T03:28:11-0300 | lane1-arms.log | - |
| external-subs-stability | PASS | 0 | 0 | 2026-11-05T19:53:37-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | PASS | 0 | 0 | 2026-11-12T03:28:12-0300 | external-caption-chrome-census.log | - |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-11-05T19:53:38-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-05T19:53:39-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-11-11T03:21:00-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-11T03:21:01-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-11-08T14:03:49-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-11-08T17:04:33-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-11-08T17:04:35-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-11-05T14:58:09-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:12-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-11-12T14:49:24-0300 | gitattributes-verify.log | - |
| mutant-tracking | PASS | 0 | 0 | 2026-11-12T14:49:26-0300 | mutant-tracking.log | - |
| red-as-expected-mutant-tracking | EXPECTED-RED | 1 | 1 | 2026-11-12T14:49:27-0300 | mutant-tracking-neg.log | - |
| agents-md-pins | STALE | 0 | 0 | 2026-11-12T14:49:28-0300 | agents-md-pins.log | deps mudaram depois da medicao (medido 2026-11-12T14:49:28-0300) |
| lang-id-oracle | PASS | 0 | 0 | 2026-11-12T03:28:45-0300 | lang-id-oracle.log | - |
| red-as-expected-lang-id-oracle | EXPECTED-RED | 1 | 1 | 2026-11-12T03:28:56-0300 | lang-id-oracle-neg.log | - |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-11T03:21:23-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-11T03:21:24-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-11-05T14:59:16-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:18-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-12T14:49:29-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-12T14:49:29-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-12T14:49:29-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:49:29-0300) |
| panel-flash-read | PASS | 0 | 0 | 2026-11-12T04:23:33-0300 | panel-flash-read.log | - |
| red-as-expected-panel-flash-read | EXPECTED-RED | 1 | 1 | 2026-11-12T04:23:34-0300 | panel-flash-read-neg.log | - |
| per-app-source-plumbing | PASS | 0 | 0 | 2026-11-12T03:28:58-0300 | per-app-source-plumbing.log | - |
| red-as-expected-per-app-source-plumbing | EXPECTED-RED | 1 | 1 | 2026-11-12T03:28:59-0300 | per-app-source-plumbing-neg.log | - |
| redux-live-contract | PASS | 0 | 0 | 2026-11-11T03:21:26-0300 | redux-live-contract.log | - |
| red-as-expected-redux-live-contract | EXPECTED-RED | 1 | 1 | 2026-11-11T03:21:26-0300 | redux-live-contract-neg.log | - |
| word-split-oracle | PASS | 0 | 0 | 2026-11-12T03:28:59-0300 | word-split-oracle.log | - |
| red-as-expected-word-split-oracle | EXPECTED-RED | 1 | 1 | 2026-11-12T03:29:00-0300 | word-split-oracle-neg.log | - |
| vad-option-probe | PASS | 0 | 0 | 2026-11-12T03:29:05-0300 | vad-option-probe.log | - |
| red-as-expected-vad-option-probe | EXPECTED-RED | 1 | 1 | 2026-11-12T03:29:05-0300 | vad-option-probe-neg.log | - |
| youtube-track-wiring | PASS | 0 | 0 | 2026-11-12T04:23:40-0300 | youtube-track-wiring.log | - |
| tap-open-timeout | PASS | 0 | 0 | 2026-11-12T03:29:40-0300 | tap-open-timeout.log | - |
| ui-stall-oracle | PASS | 0 | 0 | 2026-11-12T03:29:44-0300 | ui-stall-oracle.log | - |
| mute-audio | NOT RUN | - | 0 | - | mute-audio.log | sem registo no stepcache (o passo nao completou) |
| device-silence | NOT RUN | - | 0 | - | device-silence.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-device-silence | NOT RUN | - | 1 | - | device-silence-neg.log | sem registo no stepcache (o passo nao completou) |
| console-window-audit | FAIL | 1 | 0 | 2026-11-12T14:49:47-0300 | console-window-audit.log | rc=1 != esperado 0 |
| red-as-expected-console-window-audit | EXPECTED-RED | 1 | 1 | 2026-11-12T14:49:47-0300 | console-window-audit-neg.log | always |
| red-as-expected-console-window-watch | EXPECTED-RED | 1 | 1 | 2026-11-12T14:49:47-0300 | console-window-watch-neg.log | always |
| shell-orphans | PASS | 0 | 0 | 2026-11-12T14:49:49-0300 | shell-orphans.log | always |
| red-as-expected-shell-orphans | EXPECTED-RED | 1 | 1 | 2026-11-12T14:49:54-0300 | shell-orphans-neg.log | always |
| capture-exclude | PASS | 0 | 0 | 2026-11-12T14:49:54-0300 | capture-exclude.log | always |
| red-as-expected-capture-exclude | EXPECTED-RED | 1 | 1 | 2026-11-12T14:49:54-0300 | capture-exclude-neg.log | always |
| history-merge | PASS | 0 | 0 | 2026-11-12T14:49:55-0300 | history-merge.log | always |
| red-as-expected-history-merge | EXPECTED-RED | 1 | 1 | 2026-11-12T14:49:56-0300 | history-merge-neg.log | always |
| fusion-wire | PASS | 0 | 0 | 2026-11-12T14:50:02-0300 | fusion-wire.log | always |
| red-as-expected-fusion-wire | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:06-0300 | fusion-wire-neg.log | always |
| fusion-audio | PASS | 0 | 0 | 2026-11-12T14:50:07-0300 | fusion-audio.log | always |
| red-as-expected-fusion-audio | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:09-0300 | fusion-audio-neg.log | always |
| history-context | PASS | 0 | 0 | 2026-11-12T14:50:10-0300 | history-context.log | always |
| red-as-expected-history-context | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:17-0300 | history-context-neg.log | always |
| history-via-filter | PASS | 0 | 0 | 2026-11-12T14:50:18-0300 | history-via-filter.log | always |
| red-as-expected-history-via-filter | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:18-0300 | history-via-filter-neg.log | always |
| history-route | PASS | 0 | 0 | 2026-11-12T14:50:19-0300 | history-route.log | always |
| history-route-long | PASS | 0 | 0 | 2026-11-12T14:50:20-0300 | history-route-long.log | always |
| prose-punct | PASS | 0 | 0 | 2026-11-12T14:50:21-0300 | prose-punct.log | always |
| red-as-expected-prose-punct | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:23-0300 | prose-punct-neg.log | always |
| text-normalize | PASS | 0 | 0 | 2026-11-12T14:50:26-0300 | text-normalize.log | always |
| red-as-expected-text-normalize | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:28-0300 | text-normalize-neg.log | always |
| reveal-clock | PASS | 0 | 0 | 2026-11-12T14:50:28-0300 | reveal-clock.log | always |
| red-as-expected-reveal-clock | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:29-0300 | reveal-clock-neg.log | always |
| tap-first-block | PASS | 0 | 0 | 2026-11-12T14:50:29-0300 | tap-first-block.log | always |
| red-as-expected-tap-first-block | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:30-0300 | tap-first-block-neg.log | always |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-12T14:50:30-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:31-0300 | owner-audio-gate-neg.log | always |
| worker-providers | PASS | 0 | 0 | 2026-11-12T14:50:32-0300 | worker-providers.log | always |
| red-as-expected-worker-providers | EXPECTED-RED | 1 | 1 | 2026-11-12T14:50:32-0300 | worker-providers-neg.log | always |
| review-f1f3 | PASS | 0 | 0 | 2026-11-12T03:31:25-0300 | review-f1f3.log | - |
| review-tapstop | PASS | 0 | 0 | 2026-11-12T03:31:30-0300 | review-tapstop.log | - |
| strip-surface-oracle | PASS | 0 | 0 | 2026-11-12T03:31:52-0300 | strip-surface-oracle.log | - |
| strip-width | PASS | 0 | 0 | 2026-11-12T03:31:53-0300 | strip-width.log | - |
| red-as-expected-strip-width | EXPECTED-RED | 1 | 1 | 2026-11-12T03:31:55-0300 | strip-width-neg.log | - |
| strip-stats-log-budget | NOT RUN | - | 0 | - | strip-stats-log.log | sem registo no stepcache (o passo nao completou) |
| strip-hot-reload | PASS | 0 | 0 | 2026-11-12T03:32:12-0300 | strip-reload.log | - |
| strip-surface-runtime | NOT RUN | - | 0 | - | strip-surface.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-strip-surface | NOT RUN | - | 1 | - | strip-surface-neg.log | sem registo no stepcache (o passo nao completou) |
| engine-commit-cycles | NOT RUN | - | 0 | - | engine-commit-cycles.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-engine-commit-cycles | NOT RUN | - | 1 | - | engine-commit-cycles-neg.log | sem registo no stepcache (o passo nao completou) |
| strip-geometry-restore | NOT RUN | - | 0 | - | strip-restore.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-wave | NOT RUN | - | 0 | - | strip-stats.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-05T15:01:18-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-12T14:50:34-0300 | hotkey-registration.log | always |
| hotkey-delivery | PASS | 0 | 0 | 2026-11-12T14:50:34-0300 | hotkey-delivery.log | always |
| open-close-stall | PASS | 0 | 0 | 2026-11-12T03:32:27-0300 | open-close-stall.log | - |
| red-as-expected-open-close-stall | EXPECTED-RED | 1 | 1 | 2026-11-12T03:32:58-0300 | open-close-stall-neg.log | - |
| autostart-status | PASS | 0 | 0 | 2026-11-12T14:50:36-0300 | autostart-status.log | always |
| control-verdict-gate-unguard | PASS | 0 | 0 | 2026-11-12T03:33:02-0300 | control-verdict-gate-unguard.log | - |
| control-history-producer-stamp-nvidia | PASS | 0 | 0 | 2026-11-12T03:33:03-0300 | control-history-producer-stamp-nvidia.log | - |
| control-redux-flag-neg-arm | PASS | 0 | 0 | 2026-11-12T04:25:14-0300 | control-redux-flag-neg-arm.log | - |
| control-panel-exit3-neg-arm | NOT RUN | - | 0 | - | control-panel-exit3-neg-arm.log | sem registo no stepcache (o passo nao completou) |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-11-12T03:33:05-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | PASS | 0 | 0 | 2026-11-11T03:23:47-0300 | control-panel2-repeat-revert.log | - |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-11-05T15:01:45-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | EXPECTED-RED | 1 | 1 | 2026-11-11T11:52:10-0300 | control-historico-gate-off.log | - |
| search-oracle | PASS | 0 | 0 | 2026-11-12T03:33:08-0300 | search-oracle.log | - |
| red-as-expected-search-oracle | EXPECTED-RED | 1 | 1 | 2026-11-12T03:33:12-0300 | search-oracle-neg.log | - |
| panel-search-keyboard | PASS | 0 | 0 | 2026-11-12T03:33:14-0300 | panel-search-keyboard.log | - |
| red-as-expected-panel-search-keyboard | EXPECTED-RED | 1 | 1 | 2026-11-12T03:33:16-0300 | panel-search-keyboard-neg.log | - |
| fresh-processor-probe | PASS | 0 | 0 | 2026-11-12T03:33:25-0300 | fresh-processor.log | - |
| stepcache-oracle | PASS | 0 | 0 | 2026-11-11T14:37:17-0300 | stepcache-oracle.log | - |
| battery-plan | STALE | 0 | 0 | 2026-11-12T14:50:43-0300 | battery-plan.log | deps mudaram depois da medicao (medido 2026-11-12T14:50:43-0300) |
| red-as-expected-battery-plan | EXPECTED-RED | 1 | 1 | 2026-11-12T14:51:29-0300 | battery-plan-neg.log | always |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-12T14:51:29-0300 | _skip-guard.log | always |
| altc-first-caption | NOT RUN | - | 0 | - | altc-first-caption.log | sem registo no stepcache (o passo nao completou) |
| altc-gesture | PASS | 0 | 0 | 2026-11-12T14:51:48-0300 | altc-gesture.log | always |
| headphone-cut | PASS | 0 | 0 | 2026-11-12T14:52:49-0300 | headphone-cut.log | always |
| incomplete-word | PASS | 0 | 0 | 2026-11-12T14:52:50-0300 | incomplete-word.log | always |
| ladder-signal | PASS | 0 | 0 | 2026-11-12T14:52:50-0300 | ladder-signal.log | always |
| ladder-try-instrument | PASS | 0 | 0 | 2026-11-12T14:52:51-0300 | ladder-try-instrument.log | always |
| red-as-expected-ladder-try-instrument | EXPECTED-RED | 1 | 1 | 2026-11-12T14:52:51-0300 | ladder-try-instrument-neg.log | always |
| audio-back-detector | PASS | 0 | 0 | 2026-11-12T14:52:54-0300 | audio-back-detector.log | always |
| red-as-expected-audio-back-detector | EXPECTED-RED | 1 | 1 | 2026-11-12T14:53:19-0300 | audio-back-detector-neg.log | always |
| boot-profile | PASS | 0 | 0 | 2026-11-12T03:36:49-0300 | boot-profile.log | - |
| red-as-expected-boot-profile | EXPECTED-RED | 1 | 1 | 2026-11-12T14:53:20-0300 | boot-profile-neg.log | always |
| launch-as-token | PASS | 0 | 0 | 2026-11-12T14:53:25-0300 | launch-as-token.log | always |
| live-code-freshness | PASS | 0 | 0 | 2026-11-12T14:53:26-0300 | live-code-freshness.log | always |
| live-code-freshness-control | PASS | 0 | 0 | 2026-11-12T14:53:28-0300 | live-code-freshness-control.log | always |
| red-as-expected-live-code-freshness | EXPECTED-RED | 1 | 1 | 2026-11-12T14:53:28-0300 | live-code-freshness-neg.log | always |
| load-shedding | STALE | 0 | 0 | 2026-11-12T14:53:31-0300 | load-shedding.log | deps mudaram depois da medicao (medido 2026-11-12T14:53:31-0300) |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-12T14:53:31-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | EXPECTED-RED | 1 | 1 | 2026-11-12T14:54:38-0300 | altc-gesture-neg.log | always |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-12T14:54:39-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-12T14:54:40-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | EXPECTED-RED | 1 | 1 | 2026-11-12T14:54:41-0300 | ladder-signal-neg.log | always |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-12T14:54:44-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-12T14:54:45-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-12T14:54:49-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | FAIL | 0 | 1 | 2026-11-12T14:55:59-0300 | load-shedding-neg.log | rc=0 != esperado 1 |
| red-as-expected-shell-relaunch | NOT RUN | - | 1 | - | shell-relaunch-neg.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-word-clock | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:04-0300 | word-clock-neg.log | always |
| red-as-expected-youtube-monotonic | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:05-0300 | youtube-monotonic-neg.log | always |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:06-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:13-0300 | youtube-switch-neg.log | always |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:13-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NOT RUN | - | 0 | - | shell-relaunch.log | sem registo no stepcache (o passo nao completou) |
| census-instrument | PASS | 0 | 0 | 2026-11-12T03:39:19-0300 | census-instrument.log | - |
| red-as-expected-census-instrument | EXPECTED-RED | 1 | 1 | 2026-11-12T03:39:21-0300 | census-instrument-neg.log | - |
| relaunch-ready | PASS | 0 | 0 | 2026-11-11T11:57:36-0300 | relaunch-ready.log | - |
| red-as-expected-relaunch-ready | EXPECTED-RED | 1 | 1 | 2026-11-11T11:57:50-0300 | relaunch-ready-neg.log | - |
| word-clock | PASS | 0 | 0 | 2026-11-12T14:56:15-0300 | word-clock.log | always |
| youtube-monotonic | PASS | 0 | 0 | 2026-11-12T14:56:16-0300 | youtube-monotonic.log | always |
| youtube-rate | PASS | 0 | 0 | 2026-11-12T14:56:17-0300 | youtube-rate.log | always |
| red-as-expected-youtube-rate | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:18-0300 | youtube-rate-neg.log | always |
| click-through-applied | PASS | 0 | 0 | 2026-11-12T14:56:19-0300 | click-through-applied.log | always |
| red-as-expected-click-through-applied | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:19-0300 | click-through-applied-neg.log | always |
| topmost-keepalive | PASS | 0 | 0 | 2026-11-12T14:56:20-0300 | topmost-keepalive.log | always |
| red-as-expected-topmost-keepalive | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:21-0300 | topmost-keepalive-neg.log | always |
| webview2-args-scope | PASS | 0 | 0 | 2026-11-12T14:56:23-0300 | webview2-args-scope.log | always |
| red-as-expected-webview2-args-scope | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:24-0300 | webview2-args-scope-neg.log | always |
| webview2-runtime | PASS | 0 | 0 | 2026-11-12T14:56:25-0300 | webview2-runtime.log | always |
| red-as-expected-webview2-runtime | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:26-0300 | webview2-runtime-neg.log | always |
| power-recovery | PASS | 0 | 0 | 2026-11-12T14:56:27-0300 | power-recovery.log | always |
| red-as-expected-power-recovery | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:32-0300 | power-recovery-neg.log | always |
| power-recovery-live | NOT RUN | - | 0 | - | power-recovery-live.log | sem registo no stepcache (o passo nao completou) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-12T14:56:33-0300 | youtube-sotto-drift.log | always |
| youtube-switch | PASS | 0 | 0 | 2026-11-12T14:56:34-0300 | youtube-switch.log | always |
| yt-no-dub | PASS | 0 | 0 | 2026-11-12T14:56:35-0300 | yt-no-dub.log | always |
| stale-display | PASS | 0 | 0 | 2026-11-12T14:56:37-0300 | stale-display.log | always |
| red-as-expected-stale-display | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:40-0300 | stale-display-neg.log | always |
| battery-class | STALE | 0 | 0 | 2026-11-12T14:56:41-0300 | battery-class.log | deps mudaram depois da medicao (medido 2026-11-12T14:56:41-0300) |
| red-as-expected-battery-class | STALE | 1 | 1 | 2026-11-12T14:56:41-0300 | battery-class-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:56:41-0300) |
| live-queue | PASS | 0 | 0 | 2026-11-12T14:56:42-0300 | live-queue.log | always |
| red-as-expected-live-queue | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:43-0300 | live-queue-neg.log | always |
| flat-endpoint | PASS | 0 | 0 | 2026-11-12T14:56:45-0300 | flat-endpoint.log | always |
| tap-silent-desktop | PASS | 0 | 0 | 2026-11-12T14:56:46-0300 | tap-silent-desktop.log | always |
| red-as-expected-tap-silent-desktop | EXPECTED-RED | 1 | 1 | 2026-11-12T14:56:46-0300 | tap-silent-desktop-neg.log | always |
| warm-engine | PASS | 0 | 0 | 2026-11-12T14:56:58-0300 | warm-engine.log | always |
| red-as-expected-warm-engine | EXPECTED-RED | 1 | 1 | 2026-11-12T14:58:17-0300 | warm-engine-neg.log | always |
| warm-engine-task | PASS | 0 | 0 | 2026-11-12T14:58:19-0300 | warm-engine-task.log | always |
| red-as-expected-warm-engine-task | EXPECTED-RED | 1 | 1 | 2026-11-12T14:58:21-0300 | warm-engine-task-neg.log | always |
| gaming-hotkey | PASS | 0 | 0 | 2026-11-12T14:58:39-0300 | gaming-hotkey.log | always |
| red-as-expected-gaming-hotkey | EXPECTED-RED | 1 | 1 | 2026-11-12T14:59:58-0300 | gaming-hotkey-neg.log | always |
| ctrlspace-swallow | PASS | 0 | 0 | 2026-11-12T15:00:03-0300 | ctrlspace-swallow.log | always |
| red-as-expected-ctrlspace-swallow | EXPECTED-RED | 1 | 1 | 2026-11-12T15:00:18-0300 | ctrlspace-swallow-neg.log | always |
| ctrlspace-swallow-os | PASS | 0 | 0 | 2026-11-12T15:00:19-0300 | ctrlspace-swallow-os.log | always |
| process-target | PASS | 0 | 0 | 2026-11-12T15:00:23-0300 | process-target.log | always |
| red-as-expected-process-target | EXPECTED-RED | 1 | 1 | 2026-11-12T15:00:28-0300 | process-target-neg.log | always |
| audio-ring | PASS | 0 | 0 | 2026-11-12T03:43:35-0300 | audio-ring.log | - |
| red-as-expected-audio-ring | EXPECTED-RED | 1 | 1 | 2026-11-12T03:43:39-0300 | audio-ring-neg.log | - |
| spec-coverage | PASS | 0 | 0 | 2026-11-12T05:01:43-0300 | spec-coverage.log | - |
| red-as-expected-spec-coverage | EXPECTED-RED | 1 | 1 | 2026-11-12T05:01:43-0300 | spec-coverage-neg.log | - |
| external-owner | PASS | 0 | 0 | 2026-11-12T04:32:43-0300 | external-owner.log | - |
| red-as-expected-external-owner | EXPECTED-RED | 1 | 1 | 2026-11-12T04:32:44-0300 | external-owner-neg.log | - |
| red-as-expected-youtube-track-wiring | EXPECTED-RED | 1 | 1 | 2026-11-12T04:32:45-0300 | youtube-track-wiring-neg.log | - |
| battery-budget | STALE | 0 | 0 | 2026-11-12T15:00:29-0300 | battery-budget.log | deps mudaram depois da medicao (medido 2026-11-12T15:00:29-0300) |
| red-as-expected-battery-budget | STALE | 1 | 1 | 2026-11-12T15:00:30-0300 | battery-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-12T15:00:30-0300) |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
