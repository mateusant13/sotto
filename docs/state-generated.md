# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=413 · PASS=50 · EXPECTED-RED=56 · FAIL=15 · STALE=259 · NO-VERDICT=6 · NOT RUN=27

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | STALE | 0 | 0 | 2026-11-09T08:26:47-0300 | pycompile-webview.log | deps mudaram depois da medicao (medido 2026-11-09T08:26:47-0300) |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-11-05T14:40:17-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | STALE | 0 | 0 | 2026-11-08T18:23:54-0300 | pycompile-worker.log | deps mudaram depois da medicao (medido 2026-11-08T18:23:54-0300) |
| pycompile-wasapi+lang | STALE | 0 | 0 | 2026-11-05T14:40:18-0300 | pycompile-capture.log | deps mudaram depois da medicao (medido 2026-11-05T14:40:18-0300) |
| transcript-append-oracle | STALE | 0 | 0 | 2026-11-05T15:30:25-0300 | oracle-transcript-append.log | deps mudaram depois da medicao (medido 2026-11-05T15:30:25-0300) |
| live-vs-history-source-oracle | FAIL | 1 | 0 | 2026-11-09T08:26:49-0300 | oracle-live-vs-history.log | rc=1 != esperado 0 |
| historico-vs-redux-probe | STALE | 0 | 0 | 2026-11-09T08:26:50-0300 | oracle-historico-vs-redux.log | deps mudaram depois da medicao (medido 2026-11-09T08:26:50-0300) |
| redux-transcript-path | FAIL | 1 | 0 | 2026-11-09T08:26:52-0300 | redux-transcript-path.log | rc=1 != esperado 0 |
| redux-arm-weights | STALE | 0 | 0 | 2026-11-09T08:26:53-0300 | redux-arm-weights.log | deps mudaram depois da medicao (medido 2026-11-09T08:26:53-0300) |
| history-write | STALE | 0 | 0 | 2026-11-09T08:27:03-0300 | history-write.log | deps mudaram depois da medicao (medido 2026-11-09T08:27:03-0300) |
| caption-cumulative | STALE | 0 | 0 | 2026-11-05T15:30:26-0300 | oracle-caption-cumulative.log | deps mudaram depois da medicao (medido 2026-11-05T15:30:26-0300) |
| red-as-expected-caption-cumulative | STALE | 1 | 1 | 2026-11-05T15:30:27-0300 | caption-cumulative-neg.log | deps mudaram depois da medicao (medido 2026-11-05T15:30:27-0300) |
| caption-lag-budget | FAIL | 1 | 0 | 2026-11-09T08:27:04-0300 | caption-lag-budget.log | rc=1 != esperado 0 |
| red-as-expected-caption-lag-budget | NO-VERDICT | 1 | 1 | 2026-11-09T08:27:05-0300 | caption-lag-budget-neg.log | token `NEG-ARM: PASS` ausente do log |
| caption-rollup | PASS | 0 | 0 | 2026-11-09T08:27:07-0300 | caption-rollup.log | - |
| red-as-expected-caption-rollup | EXPECTED-RED | 1 | 1 | 2026-11-09T08:27:09-0300 | caption-rollup-neg.log | - |
| paint-cost | PASS | 0 | 0 | 2026-11-09T08:28:06-0300 | paint-cost.log | - |
| red-as-expected-paint-cost | EXPECTED-RED | 1 | 1 | 2026-11-09T08:28:08-0300 | paint-cost-neg.log | - |
| shell-thread-budget | STALE | 0 | 0 | 2026-11-09T08:28:16-0300 | shell-thread-budget.log | deps mudaram depois da medicao (medido 2026-11-09T08:28:16-0300) |
| red-as-expected-shell-thread-budget | STALE | 1 | 1 | 2026-11-08T06:09:34-0300 | shell-thread-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-08T06:09:34-0300) |
| ort-spin-idle | STALE | 0 | 0 | 2026-11-08T20:38:48-0300 | ort-spin-idle.log | deps mudaram depois da medicao (medido 2026-11-08T20:38:48-0300) |
| red-as-expected-ort-spin-idle | STALE | 1 | 1 | 2026-11-08T20:39:00-0300 | ort-spin-idle-neg.log | deps mudaram depois da medicao (medido 2026-11-08T20:39:00-0300) |
| worker-thread-limit | NOT RUN | - | 0 | - | worker-thread-limit.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-worker-thread-limit | NOT RUN | - | 1 | - | worker-thread-limit-neg.log | sem registo no stepcache (o passo nao completou) |
| caption-tick-thread | PASS | 0 | 0 | 2026-11-09T08:28:20-0300 | caption-tick-thread.log | - |
| red-as-expected-caption-tick-thread | EXPECTED-RED | 1 | 1 | 2026-11-09T08:28:24-0300 | caption-tick-thread-neg.log | - |
| log-sink-dead | STALE | 0 | 0 | 2026-11-09T08:28:24-0300 | log-sink-dead.log | deps mudaram depois da medicao (medido 2026-11-09T08:28:24-0300) |
| red-as-expected-log-sink-dead | STALE | 1 | 1 | 2026-11-09T08:28:25-0300 | log-sink-dead-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:28:25-0300) |
| cdp-target-async | STALE | 0 | 0 | 2026-11-08T05:16:23-0300 | cdp-target-async.log | deps mudaram depois da medicao (medido 2026-11-08T05:16:23-0300) |
| red-as-expected-cdp-target-async | STALE | 1 | 1 | 2026-11-08T05:16:33-0300 | cdp-target-async-neg.log | deps mudaram depois da medicao (medido 2026-11-08T05:16:33-0300) |
| caption-drag | PASS | 0 | 0 | 2026-11-09T08:28:28-0300 | caption-drag.log | - |
| red-as-expected-caption-drag | EXPECTED-RED | 1 | 1 | 2026-11-09T08:28:32-0300 | caption-drag-neg.log | - |
| lag-note-cost | STALE | 0 | 0 | 2026-11-09T08:28:34-0300 | lag-note-cost.log | deps mudaram depois da medicao (medido 2026-11-09T08:28:34-0300) |
| red-as-expected-lag-note-cost | STALE | 1 | 1 | 2026-11-09T08:30:03-0300 | lag-note-cost-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:30:03-0300) |
| youtube-hidden-clock | STALE | 0 | 0 | 2026-11-09T08:30:04-0300 | youtube-hidden-clock.log | deps mudaram depois da medicao (medido 2026-11-09T08:30:04-0300) |
| red-as-expected-youtube-hidden-clock | EXPECTED-RED | 1 | 1 | 2026-11-09T08:30:06-0300 | youtube-hidden-clock-neg.log | always |
| caption-overlay-screen | PASS | 0 | 0 | 2026-11-09T08:30:06-0300 | caption-overlay-screen.log | always |
| red-as-expected-caption-overlay-screen | EXPECTED-RED | 1 | 1 | 2026-11-09T08:30:07-0300 | caption-overlay-screen-neg.log | always |
| youtube-cdp-boot | STALE | 0 | 0 | 2026-11-09T08:30:11-0300 | youtube-cdp-boot.log | deps mudaram depois da medicao (medido 2026-11-09T08:30:11-0300) |
| red-as-expected-youtube-cdp-boot | STALE | 1 | 1 | 2026-11-09T08:30:35-0300 | youtube-cdp-boot-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:30:35-0300) |
| youtube-cdp-slow | STALE | 0 | 0 | 2026-11-09T08:30:42-0300 | youtube-cdp-slow.log | deps mudaram depois da medicao (medido 2026-11-09T08:30:42-0300) |
| red-as-expected-youtube-cdp-slow | STALE | 1 | 1 | 2026-11-09T08:31:03-0300 | youtube-cdp-slow-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:31:03-0300) |
| youtube-first-at-boot | STALE | 0 | 0 | 2026-11-09T08:31:14-0300 | youtube-first-at-boot.log | deps mudaram depois da medicao (medido 2026-11-09T08:31:14-0300) |
| red-as-expected-youtube-first-at-boot | STALE | 1 | 1 | 2026-11-09T08:31:56-0300 | youtube-first-at-boot-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:31:56-0300) |
| red-as-expected-redux-transcript-path | NO-VERDICT | 1 | 1 | 2026-11-09T08:31:58-0300 | redux-transcript-path-neg.log | token `NEG-ARM: PASS` ausente do log |
| red-as-expected-history-write | STALE | 1 | 1 | 2026-11-09T08:32:05-0300 | history-write-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:05-0300) |
| control-verdict-gate-drop-redux-live | STALE | 0 | 0 | 2026-11-08T18:31:48-0300 | control-verdict-gate-drop-redux-live.log | deps mudaram depois da medicao (medido 2026-11-08T18:31:48-0300) |
| history-producer-gate | STALE | 0 | 0 | 2026-11-08T18:31:49-0300 | gate-history-producer.log | deps mudaram depois da medicao (medido 2026-11-08T18:31:49-0300) |
| panel-state-guard-gate | STALE | 0 | 0 | 2026-11-09T08:32:07-0300 | gate-panel-state-guard.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:07-0300) |
| verdict-gate | STALE | 0 | 0 | 2026-11-08T18:31:50-0300 | gate-verdict.log | deps mudaram depois da medicao (medido 2026-11-08T18:31:50-0300) |
| worker-park | STALE | 0 | 0 | 2026-11-09T08:32:40-0300 | worker-park.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:40-0300) |
| red-as-expected-worker-park | STALE | 1 | 1 | 2026-11-09T08:32:40-0300 | worker-park-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:40-0300) |
| lane2-reset-probe | STALE | 0 | 0 | 2026-11-09T08:32:41-0300 | lane2-reset.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:41-0300) |
| lane3-verdict-probe | STALE | 0 | 0 | 2026-11-08T18:32:28-0300 | lane3-verdict.log | deps mudaram depois da medicao (medido 2026-11-08T18:32:28-0300) |
| lane4-tap-stop-probe | STALE | 0 | 0 | 2026-11-05T14:46:56-0300 | lane4-tap-stop.log | deps mudaram depois da medicao (medido 2026-11-05T14:46:56-0300) |
| audit-history-dead | STALE | 0 | 0 | 2026-11-09T08:32:41-0300 | audit-history-dead.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:41-0300) |
| panel2-repeat-probe | STALE | 0 | 0 | 2026-11-09T08:32:44-0300 | panel2-repeat.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:44-0300) |
| history-gallery-oracle | PASS | 0 | 0 | 2026-11-05T14:47:02-0300 | gallery-oracle.log | - |
| panel2-dom-probe | STALE | 0 | 0 | 2026-11-09T08:32:50-0300 | panel2-dom-probe.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:50-0300) |
| panel-header-oracle | STALE | 0 | 0 | 2026-11-09T08:32:54-0300 | panel-header.log | deps mudaram depois da medicao (medido 2026-11-09T08:32:54-0300) |
| red-as-expected-panel-header-oracle | STALE | 1 | 1 | 2026-11-09T08:34:39-0300 | panel-header-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:34:39-0300) |
| panel-drag-targets | STALE | 0 | 0 | 2026-11-09T08:35:07-0300 | panel-drag-targets.log | deps mudaram depois da medicao (medido 2026-11-09T08:35:07-0300) |
| panel-history-clip | STALE | 0 | 0 | 2026-11-09T08:36:29-0300 | panel-history-clip.log | deps mudaram depois da medicao (medido 2026-11-09T08:36:29-0300) |
| panel-history-wheel | STALE | 0 | 0 | 2026-11-09T08:36:35-0300 | panel-history-wheel.log | deps mudaram depois da medicao (medido 2026-11-09T08:36:35-0300) |
| red-as-expected-panel-history-wheel | STALE | 1 | 1 | 2026-11-09T08:36:46-0300 | panel-history-wheel-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:36:46-0300) |
| theme-caption-identity | STALE | 0 | 0 | 2026-11-09T07:52:47-0300 | theme-caption-identity.log | deps mudaram depois da medicao (medido 2026-11-09T07:52:47-0300) |
| red-as-expected-theme-caption-identity | STALE | 1 | 1 | 2026-11-09T07:52:48-0300 | theme-caption-identity-neg.log | deps mudaram depois da medicao (medido 2026-11-09T07:52:48-0300) |
| caption-overlay-theme | NOT RUN | - | 0 | - | caption-overlay-theme.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-caption-overlay-theme | NOT RUN | - | 1 | - | caption-overlay-theme-neg.log | sem registo no stepcache (o passo nao completou) |
| panel-themes | STALE | 0 | 0 | 2026-11-09T08:37:28-0300 | panel-themes.log | deps mudaram depois da medicao (medido 2026-11-09T08:37:28-0300) |
| red-as-expected-panel-themes | STALE | 1 | 1 | 2026-11-09T08:38:39-0300 | panel-themes-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:38:39-0300) |
| red-as-expected-panel-history-clip | STALE | 1 | 1 | 2026-11-09T08:38:42-0300 | panel-history-clip-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:38:42-0300) |
| panel-pause-payload | STALE | 0 | 0 | 2026-11-09T08:38:43-0300 | panel-pause-payload.log | deps mudaram depois da medicao (medido 2026-11-09T08:38:43-0300) |
| red-as-expected-panel-pause-payload | STALE | 1 | 1 | 2026-11-09T08:38:44-0300 | panel-pause-payload-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:38:44-0300) |
| cost-watchdog | NOT RUN | - | 0 | - | cost-watchdog.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-cost-watchdog | NOT RUN | - | 1 | - | cost-watchdog-neg.log | sem registo no stepcache (o passo nao completou) |
| outside-click-timer | STALE | 0 | 0 | 2026-11-09T08:39:04-0300 | outside-click-timer.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:04-0300) |
| red-as-expected-outside-click-timer | STALE | 1 | 1 | 2026-11-09T08:39:24-0300 | outside-click-timer-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:24-0300) |
| panel-deps | STALE | 0 | 0 | 2026-11-09T08:39:25-0300 | panel-deps.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:25-0300) |
| red-as-expected-panel-deps | STALE | 0 | 0 | 2026-11-09T08:39:25-0300 | panel-deps-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:25-0300) |
| worker-death-trace | STALE | 0 | 0 | 2026-11-08T18:33:12-0300 | worker-death-trace.log | deps mudaram depois da medicao (medido 2026-11-08T18:33:12-0300) |
| red-as-expected-worker-death-trace | STALE | 1 | 1 | 2026-11-08T18:33:14-0300 | worker-death-trace-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:33:14-0300) |
| panel-live-box-oracle | STALE | 0 | 0 | 2026-11-09T08:39:36-0300 | panel-live-box-oracle.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:36-0300) |
| border-radius-gate | STALE | 0 | 0 | 2026-11-09T07:54:44-0300 | border-radius-gate.log | deps mudaram depois da medicao (medido 2026-11-09T07:54:44-0300) |
| red-as-expected-border-radius-gate | STALE | 1 | 1 | 2026-11-09T07:54:44-0300 | border-radius-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-09T07:54:44-0300) |
| hidden-launch | PASS | 0 | 0 | 2026-11-05T14:47:36-0300 | hidden-launch.log | - |
| red-as-expected-hidden-launch | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:37-0300 | hidden-launch-neg.log | - |
| step-deadline | PASS | 0 | 0 | 2026-11-05T14:47:49-0300 | step-deadline.log | - |
| red-as-expected-step-deadline | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:02-0300 | step-deadline-neg.log | - |
| emit-prewebview | STALE | 0 | 0 | 2026-11-09T08:39:38-0300 | emit-prewebview.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:38-0300) |
| red-as-expected-emit-prewebview | STALE | 1 | 1 | 2026-11-09T08:39:39-0300 | emit-prewebview-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:39-0300) |
| hotkey-live-edge | STALE | 0 | 0 | 2026-11-09T08:39:45-0300 | hotkey-live-edge.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:45-0300) |
| red-as-expected-hotkey-live-edge | STALE | 1 | 1 | 2026-11-09T08:39:51-0300 | hotkey-live-edge-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:51-0300) |
| lane-screen-gate | STALE | 0 | 0 | 2026-11-09T08:39:57-0300 | lane-screen-gate.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:57-0300) |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:29-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | FAIL | 1 | 0 | 2026-11-09T08:39:58-0300 | caption-dup-repro.log | rc=1 != esperado 0 |
| complaints-closure | PASS | 0 | 0 | 2026-11-05T14:48:31-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:31-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | STALE | 0 | 0 | 2026-11-09T08:39:59-0300 | youtube-paint-first.log | deps mudaram depois da medicao (medido 2026-11-09T08:39:59-0300) |
| red-as-expected-youtube-paint-first | STALE | 1 | 1 | 2026-11-09T08:40:00-0300 | youtube-paint-first-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:40:00-0300) |
| youtube-foreign-paint | STALE | 0 | 0 | 2026-11-09T08:40:02-0300 | youtube-foreign-paint.log | deps mudaram depois da medicao (medido 2026-11-09T08:40:02-0300) |
| red-as-expected-youtube-foreign-paint | STALE | 1 | 1 | 2026-11-09T08:40:03-0300 | youtube-foreign-paint-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:40:03-0300) |
| input-path | STALE | 0 | 0 | 2026-11-09T08:40:29-0300 | input-path.log | deps mudaram depois da medicao (medido 2026-11-09T08:40:29-0300) |
| red-as-expected-input-path | STALE | 1 | 1 | 2026-11-09T08:40:32-0300 | input-path-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:40:32-0300) |
| exception-hygiene | FAIL | 2 | 0 | 2026-11-09T08:40:35-0300 | exception-hygiene.log | rc=2 != esperado 0 |
| red-as-expected-exception-hygiene | STALE | 1 | 1 | 2026-11-08T06:13:00-0300 | exception-hygiene-neg.log | deps mudaram depois da medicao (medido 2026-11-08T06:13:00-0300) |
| seam-coverage | STALE | 0 | 0 | 2026-11-09T08:41:00-0300 | seam-coverage.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:00-0300) |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:13-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-05T14:50:14-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:15-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-05T19:44:31-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-05T19:44:32-0300 | tooling-intent-neg.log | - |
| external-resume | FAIL | 1 | 0 | 2026-11-09T08:41:01-0300 | external-resume.log | rc=1 != esperado 0 |
| red-as-expected-external-resume | STALE | 1 | 1 | 2026-11-09T08:41:03-0300 | external-resume-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:03-0300) |
| silence-kill | STALE | 0 | 0 | 2026-11-09T08:41:03-0300 | silence-kill.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:03-0300) |
| red-as-expected-silence-kill | STALE | 1 | 1 | 2026-11-09T08:41:04-0300 | silence-kill-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:04-0300) |
| worker-churn | STALE | 0 | 0 | 2026-11-09T08:41:07-0300 | worker-churn.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:07-0300) |
| red-as-expected-worker-churn | STALE | 1 | 1 | 2026-11-09T08:41:11-0300 | worker-churn-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:11-0300) |
| rss-trend | STALE | 0 | 0 | 2026-11-09T08:41:11-0300 | rss-trend.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:11-0300) |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:32-0300 | rss-trend-neg.log | - |
| death-cause | STALE | 0 | 0 | 2026-11-09T08:41:12-0300 | death-cause.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:12-0300) |
| red-as-expected-death-cause | STALE | 1 | 1 | 2026-11-09T08:41:13-0300 | death-cause-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:13-0300) |
| caption-seam-dedup | STALE | 0 | 0 | 2026-11-08T18:35:01-0300 | caption-seam-dedup.log | deps mudaram depois da medicao (medido 2026-11-08T18:35:01-0300) |
| red-as-expected-caption-seam-dedup | STALE | 1 | 1 | 2026-11-08T18:35:02-0300 | caption-seam-dedup-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:35:02-0300) |
| freeze-census | PASS | 0 | 0 | 2026-11-05T19:44:47-0300 | freeze-census.log | - |
| red-as-expected-caption-budget | STALE | 1 | 1 | 2026-11-09T08:41:14-0300 | caption-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:14-0300) |
| dead-app-exit | STALE | 0 | 0 | 2026-11-09T08:41:34-0300 | dead-app-exit.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:34-0300) |
| shell-priority | STALE | 0 | 0 | 2026-11-09T08:41:34-0300 | shell-priority.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:34-0300) |
| red-as-expected-shell-priority | STALE | 1 | 1 | 2026-11-09T08:41:35-0300 | shell-priority-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:35-0300) |
| tray-menu | STALE | 0 | 0 | 2026-11-09T08:41:35-0300 | tray-menu.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:35-0300) |
| red-as-expected-tray-menu | STALE | 1 | 1 | 2026-11-09T08:41:37-0300 | tray-menu-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:37-0300) |
| hotkey-panels-switch | STALE | 0 | 0 | 2026-11-09T08:41:38-0300 | hotkey-panels-switch.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:38-0300) |
| red-as-expected-hotkey-panels-switch | STALE | 1 | 1 | 2026-11-09T08:41:40-0300 | hotkey-panels-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:40-0300) |
| caption-kept-on-hide | STALE | 0 | 0 | 2026-11-09T08:41:43-0300 | caption-kept-on-hide.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:43-0300) |
| red-as-expected-caption-kept-on-hide | STALE | 1 | 1 | 2026-11-09T08:41:45-0300 | caption-kept-on-hide-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:45-0300) |
| caption-switch-race | STALE | 0 | 0 | 2026-11-09T08:41:46-0300 | caption-switch-race.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:46-0300) |
| red-as-expected-caption-switch-race | STALE | 1 | 1 | 2026-11-09T08:41:47-0300 | caption-switch-race-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:47-0300) |
| word-glue | STALE | 0 | 0 | 2026-11-08T18:36:17-0300 | word-glue.log | deps mudaram depois da medicao (medido 2026-11-08T18:36:17-0300) |
| red-as-expected-word-glue | STALE | 1 | 1 | 2026-11-08T18:36:18-0300 | word-glue-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:36:18-0300) |
| punct-prosody | PASS | 0 | 0 | 2026-11-05T19:45:18-0300 | punct-prosody.log | - |
| red-as-expected-punct-prosody | EXPECTED-RED | 1 | 1 | 2026-11-05T19:45:19-0300 | punct-prosody-neg.log | - |
| punct-model | STALE | 0 | 0 | 2026-11-08T18:36:19-0300 | punct-model.log | deps mudaram depois da medicao (medido 2026-11-08T18:36:19-0300) |
| red-as-expected-punct-model | STALE | 1 | 1 | 2026-11-08T18:36:20-0300 | punct-model-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:36:20-0300) |
| panel-prefix-row | STALE | 0 | 0 | 2026-11-09T08:41:48-0300 | panel-prefix-row.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:48-0300) |
| red-as-expected-panel-prefix-row | STALE | 1 | 1 | 2026-11-09T08:41:49-0300 | panel-prefix-row-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:49-0300) |
| fusion | PASS | 0 | 0 | 2026-11-05T14:51:09-0300 | fusion.log | - |
| red-as-expected-fusion | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:09-0300 | fusion-neg.log | - |
| agc-peak-ceiling | STALE | 0 | 0 | 2026-11-08T18:36:21-0300 | agc-peak-ceiling.log | deps mudaram depois da medicao (medido 2026-11-08T18:36:21-0300) |
| red-as-expected-agc-peak-ceiling | STALE | 1 | 1 | 2026-11-08T18:36:22-0300 | agc-peak-ceiling-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:36:22-0300) |
| reveal-park | STALE | 0 | 0 | 2026-11-09T08:41:52-0300 | reveal-park.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:52-0300) |
| red-as-expected-reveal-park | STALE | 1 | 1 | 2026-11-09T08:41:57-0300 | reveal-park-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:41:57-0300) |
| youtube-verbatim | STALE | 0 | 0 | 2026-11-09T08:42:00-0300 | youtube-verbatim.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:00-0300) |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:52-0300 | youtube-verbatim-neg.log | - |
| code-health | FAIL | 2 | 0 | 2026-11-09T08:42:01-0300 | code-health.log | rc=2 != esperado 0 |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-09T08:42:02-0300 | code-health-neg.log | always |
| undefined-names | STALE | 0 | 0 | 2026-11-09T08:42:03-0300 | undefined-names.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:03-0300) |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-09T08:42:03-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | STALE | 0 | 0 | 2026-11-09T08:42:05-0300 | battery-heavy-gate.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:05-0300) |
| red-as-expected-battery-heavy-gate | STALE | 1 | 1 | 2026-11-09T08:42:12-0300 | battery-heavy-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:12-0300) |
| task-resolver-gate | STALE | 0 | 0 | 2026-11-09T08:42:12-0300 | task-resolver-gate.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:12-0300) |
| red-as-expected-task-resolver-gate | STALE | 1 | 1 | 2026-11-09T08:42:13-0300 | task-resolver-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:13-0300) |
| claims-date | STALE | 0 | 0 | 2026-11-09T08:42:13-0300 | claims-date.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:13-0300) |
| red-as-expected-claims-date | STALE | 1 | 1 | 2026-11-09T08:42:14-0300 | claims-date-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:14-0300) |
| stall-under-load | STALE | 0 | 0 | 2026-11-09T08:42:16-0300 | stall-under-load.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:16-0300) |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-09T08:42:16-0300 | stall-under-load-neg.log | always |
| paint-live-show | STALE | 0 | 0 | 2026-11-09T08:42:35-0300 | paint-live-show.log | deps mudaram depois da medicao (medido 2026-11-09T08:42:35-0300) |
| red-as-expected-paint-live-show | EXPECTED-RED | 1 | 1 | 2026-11-09T08:42:50-0300 | paint-live-show-neg.log | always |
| panel-paint-first-measure | NOT RUN | - | 0 | - | panel-paint-first-measure.log | sem registo no stepcache (o passo nao completou) |
| panel-paint-first | PASS | 0 | 0 | 2026-11-09T08:42:51-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-09T08:42:51-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-09T08:42:52-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-09T08:42:52-0300 | receipt-provenance-neg.log | always |
| async-track-fetch | STALE | 0 | 0 | 2026-11-09T08:43:01-0300 | async-track-fetch.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:01-0300) |
| red-as-expected-async-track-fetch | STALE | 1 | 1 | 2026-11-09T08:43:10-0300 | async-track-fetch-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:10-0300) |
| batch-queue-drain | PASS | 0 | 0 | 2026-11-08T18:40:56-0300 | batch-queue-drain.log | - |
| red-as-expected-batch-queue-drain | EXPECTED-RED | 1 | 1 | 2026-11-08T18:41:07-0300 | batch-queue-drain-neg.log | - |
| batch-executor-ceiling | PASS | 0 | 0 | 2026-11-08T18:41:10-0300 | batch-executor-ceiling.log | - |
| red-as-expected-batch-executor-ceiling | EXPECTED-RED | 1 | 1 | 2026-11-08T18:41:11-0300 | batch-executor-ceiling-neg.log | - |
| hotkey-live-toggle | STALE | 0 | 0 | 2026-11-09T08:43:16-0300 | hotkey-live-toggle.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:16-0300) |
| red-as-expected-hotkey-live-toggle | STALE | 1 | 1 | 2026-11-09T08:43:33-0300 | hotkey-live-toggle-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:33-0300) |
| hotkey-spam | STALE | 0 | 0 | 2026-11-09T08:43:37-0300 | hotkey-spam.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:37-0300) |
| red-as-expected-hotkey-spam | STALE | 1 | 1 | 2026-11-09T08:43:48-0300 | hotkey-spam-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:48-0300) |
| loading-placeholder | STALE | 0 | 0 | 2026-11-09T08:43:49-0300 | loading-placeholder.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:49-0300) |
| red-as-expected-loading-placeholder | STALE | 1 | 1 | 2026-11-09T08:43:49-0300 | loading-placeholder-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:49-0300) |
| youtube-land | STALE | 0 | 0 | 2026-11-09T08:43:50-0300 | youtube-land.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:50-0300) |
| red-as-expected-youtube-land | EXPECTED-RED | 1 | 1 | 2026-11-09T08:43:51-0300 | youtube-land-neg.log | - |
| time-to-first-caption | STALE | 0 | 0 | 2026-11-09T08:43:52-0300 | time-to-first-caption.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:52-0300) |
| red-as-expected-time-to-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-05T19:46:54-0300 | time-to-first-caption-neg.log | - |
| first-capture-fast | STALE | 0 | 0 | 2026-11-09T08:43:53-0300 | first-capture-fast.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:53-0300) |
| red-as-expected-first-capture-fast | STALE | 1 | 1 | 2026-11-09T08:43:57-0300 | first-capture-fast-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:57-0300) |
| youtube-land-replay | FAIL | 1 | 0 | 2026-11-09T08:43:58-0300 | youtube-land-replay.log | rc=1 != esperado 0 |
| red-as-expected-youtube-land-replay | NO-VERDICT | 1 | 1 | 2026-11-09T08:43:59-0300 | youtube-land-replay-neg.log | token `NEG-ARM: PASS` ausente do log |
| yt-loop-uia | STALE | 0 | 0 | 2026-11-09T08:43:59-0300 | yt-loop-uia.log | deps mudaram depois da medicao (medido 2026-11-09T08:43:59-0300) |
| red-as-expected-yt-loop-uia | STALE | 1 | 1 | 2026-11-09T08:44:00-0300 | yt-loop-uia-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:44:00-0300) |
| yt-target-stale | STALE | 0 | 0 | 2026-11-09T08:44:01-0300 | yt-target-stale.log | deps mudaram depois da medicao (medido 2026-11-09T08:44:01-0300) |
| red-as-expected-yt-target-stale | STALE | 1 | 1 | 2026-11-09T08:44:02-0300 | yt-target-stale-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:44:02-0300) |
| yt-source-singleton | NOT RUN | - | 0 | - | yt-source-singleton.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-yt-source-singleton | NOT RUN | - | 1 | - | yt-source-singleton-neg.log | sem registo no stepcache (o passo nao completou) |
| cpu-tripwire | NOT RUN | - | 0 | - | cpu-tripwire.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-cpu-tripwire | NOT RUN | - | 1 | - | cpu-tripwire-neg.log | sem registo no stepcache (o passo nao completou) |
| owner-screen | STALE | 0 | 0 | 2026-11-09T08:44:07-0300 | owner-screen.log | deps mudaram depois da medicao (medido 2026-11-09T08:44:07-0300) |
| red-as-expected-owner-screen | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:38-0300 | owner-screen-neg.log | - |
| job-object | PASS | 0 | 0 | 2026-11-05T14:53:42-0300 | job-object.log | - |
| red-as-expected-job-object | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:45-0300 | job-object-neg.log | - |
| emit-pipe-dead | STALE | 0 | 0 | 2026-11-08T18:42:48-0300 | emit-pipe-dead.log | deps mudaram depois da medicao (medido 2026-11-08T18:42:48-0300) |
| red-as-expected-emit-pipe-dead | STALE | 1 | 1 | 2026-11-08T18:42:49-0300 | emit-pipe-dead-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:42:49-0300) |
| state-page-write | STALE | 0 | 0 | 2026-11-09T08:44:11-0300 | state-page-write.log | deps mudaram depois da medicao (medido 2026-11-09T08:44:11-0300) |
| state-page | STALE | 0 | 0 | 2026-11-09T08:44:19-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-09T08:44:19-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-09T08:45:01-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:45:01-0300) |
| battery-wiring | FAIL | 1 | 0 | 2026-11-09T08:45:03-0300 | battery-wiring.log | rc=1 != esperado 0 |
| red-as-expected-battery-wiring | FAIL | 2 | 1 | 2026-11-09T08:45:08-0300 | battery-wiring-neg.log | rc=2 != esperado 1 |
| battery-record-pairing | STALE | 0 | 0 | 2026-11-09T08:45:09-0300 | battery-record-pairing.log | deps mudaram depois da medicao (medido 2026-11-09T08:45:09-0300) |
| red-as-expected-battery-record-pairing | STALE | 1 | 1 | 2026-11-09T08:45:09-0300 | battery-record-pairing-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:45:09-0300) |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-09T08:45:10-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-09T08:45:13-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | STALE | 0 | 0 | 2026-11-09T08:45:15-0300 | youtube-1to1.log | deps mudaram depois da medicao (medido 2026-11-09T08:45:15-0300) |
| red-as-expected-youtube-1to1 | STALE | 1 | 1 | 2026-11-09T08:45:19-0300 | youtube-1to1-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:45:19-0300) |
| youtube-cdp-source | FAIL | 1 | 0 | 2026-11-09T08:48:23-0300 | youtube-cdp-source.log | rc=1 != esperado 0 |
| red-as-expected-youtube-cdp-source | NO-VERDICT | 1 | 1 | 2026-11-09T08:01:25-0300 | youtube-cdp-source-neg.log | log alterado depois do registo |
| caption-producer | STALE | 0 | 0 | 2026-11-09T08:01:26-0300 | caption-producer.log | deps mudaram depois da medicao (medido 2026-11-09T08:01:26-0300) |
| red-as-expected-caption-producer | STALE | 1 | 1 | 2026-11-09T08:01:26-0300 | caption-producer-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:01:26-0300) |
| caption-style | STALE | 0 | 0 | 2026-11-09T08:01:29-0300 | caption-style.log | deps mudaram depois da medicao (medido 2026-11-09T08:01:29-0300) |
| red-as-expected-caption-style | STALE | 1 | 1 | 2026-11-09T08:01:31-0300 | caption-style-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:01:31-0300) |
| panel-commit-stable | STALE | 0 | 0 | 2026-11-09T08:02:07-0300 | panel-commit-stable.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:07-0300) |
| red-as-expected-panel-commit-stable | STALE | 1 | 1 | 2026-11-09T08:02:44-0300 | panel-commit-stable-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:44-0300) |
| paint-row-seam | STALE | 0 | 0 | 2026-11-09T08:02:44-0300 | paint-row-seam.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:44-0300) |
| red-as-expected-paint-row-seam | STALE | 1 | 1 | 2026-11-09T08:02:45-0300 | paint-row-seam-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:45-0300) |
| load-bg-window | STALE | 0 | 0 | 2026-11-09T08:02:46-0300 | load-bg-window.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:46-0300) |
| red-as-expected-load-bg-window | STALE | 1 | 1 | 2026-11-09T08:02:47-0300 | load-bg-window-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:47-0300) |
| page-scan-browser | STALE | 0 | 0 | 2026-11-09T08:02:48-0300 | page-scan-browser.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:48-0300) |
| red-as-expected-page-scan-browser | STALE | 1 | 1 | 2026-11-09T08:02:49-0300 | page-scan-browser-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:49-0300) |
| paused-pace | STALE | 0 | 0 | 2026-11-09T08:02:51-0300 | paused-pace.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:51-0300) |
| red-as-expected-paused-pace | STALE | 1 | 1 | 2026-11-09T08:02:53-0300 | paused-pace-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:53-0300) |
| stutter-caption | STALE | 0 | 0 | 2026-11-09T08:02:56-0300 | stutter-caption.log | deps mudaram depois da medicao (medido 2026-11-09T08:02:56-0300) |
| red-as-expected-stutter-caption | NO-VERDICT | 1 | 1 | 2026-11-09T08:03:01-0300 | stutter-caption-neg.log | token `NEG-ARM PASS` ausente do log |
| parakeet-ultra | NOT RUN | - | 0 | - | parakeet-ultra.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-parakeet-ultra | EXPECTED-RED | 1 | 1 | 2026-11-09T08:03:02-0300 | parakeet-ultra-neg.log | always |
| hotkey-observed | STALE | 0 | 0 | 2026-11-09T08:03:08-0300 | hotkey-observed.log | deps mudaram depois da medicao (medido 2026-11-09T08:03:08-0300) |
| red-as-expected-hotkey-observed | STALE | 1 | 1 | 2026-11-09T08:03:09-0300 | hotkey-observed-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:03:09-0300) |
| youtube-reveal | STALE | 0 | 0 | 2026-11-09T08:03:11-0300 | youtube-reveal.log | deps mudaram depois da medicao (medido 2026-11-09T08:03:11-0300) |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-09T08:03:12-0300 | youtube-reveal-neg.log | always |
| youtube-rows | STALE | 0 | 0 | 2026-11-09T08:03:14-0300 | youtube-rows.log | deps mudaram depois da medicao (medido 2026-11-09T08:03:14-0300) |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-09T08:03:16-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-09T08:03:16-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-09T08:03:17-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-09T08:03:35-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-09T08:03:36-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-09T08:03:36-0300 | bend-laws-model-neg.log | always |
| bend-mirror | STALE | 0 | 0 | 2026-11-09T08:03:37-0300 | bend-mirror.log | deps mudaram depois da medicao (medido 2026-11-09T08:03:37-0300) |
| red-as-expected-bend-mirror | STALE | 1 | 1 | 2026-11-09T08:03:39-0300 | bend-mirror-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:03:39-0300) |
| bend-ledger-selftest | PASS | 0 | 0 | 2026-11-09T08:03:40-0300 | bend-ledger-selftest.log | always |
| panel-hidden-at-startup-oracle | STALE | 0 | 0 | 2026-11-09T08:04:19-0300 | panel-hidden-at-startup.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:19-0300) |
| red-as-expected-panel-hidden-at-startup | STALE | 1 | 1 | 2026-11-09T08:04:27-0300 | panel-hidden-at-startup-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:27-0300) |
| panel-nav-stall | STALE | 0 | 0 | 2026-11-09T08:04:27-0300 | panel-nav-stall.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:27-0300) |
| red-as-expected-panel-nav-stall | STALE | 1 | 1 | 2026-11-09T08:04:30-0300 | panel-nav-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:30-0300) |
| worker-start-wiring | STALE | 0 | 0 | 2026-11-09T08:04:31-0300 | wiring-worker-start.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:31-0300) |
| red-as-expected-worker-start-wiring | STALE | 1 | 1 | 2026-11-09T08:04:32-0300 | wiring-worker-start-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:32-0300) |
| embedded-js-check | STALE | 0 | 0 | 2026-11-09T08:04:33-0300 | embedded-js.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:33-0300) |
| lane1-worker-default-arms | STALE | 0 | 0 | 2026-11-09T08:04:34-0300 | lane1-arms.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:34-0300) |
| external-subs-stability | PASS | 0 | 0 | 2026-11-05T19:53:37-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | STALE | 0 | 0 | 2026-11-09T08:04:35-0300 | external-caption-chrome-census.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:35-0300) |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-11-05T19:53:38-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-05T19:53:39-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-11-08T17:04:31-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-09T08:04:37-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-11-08T14:03:49-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-11-08T17:04:33-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-11-08T17:04:35-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-11-05T14:58:09-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:12-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-11-05T15:39:14-0300 | gitattributes-verify.log | - |
| agents-md-pins | FAIL | 1 | 0 | 2026-11-09T08:04:38-0300 | agents-md-pins.log | rc=1 != esperado 0 |
| lang-id-oracle | STALE | 0 | 0 | 2026-11-08T18:48:27-0300 | lang-id-oracle.log | deps mudaram depois da medicao (medido 2026-11-08T18:48:27-0300) |
| red-as-expected-lang-id-oracle | STALE | 1 | 1 | 2026-11-08T18:49:01-0300 | lang-id-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:49:01-0300) |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-05T14:59:14-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:15-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-11-05T14:59:16-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:18-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-09T08:04:39-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:39-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-09T08:04:39-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:39-0300) |
| per-app-source-plumbing | STALE | 0 | 0 | 2026-11-08T18:49:04-0300 | per-app-source-plumbing.log | deps mudaram depois da medicao (medido 2026-11-08T18:49:04-0300) |
| red-as-expected-per-app-source-plumbing | STALE | 1 | 1 | 2026-11-08T18:49:04-0300 | per-app-source-plumbing-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:49:04-0300) |
| redux-live-contract | STALE | 0 | 0 | 2026-11-09T08:04:40-0300 | redux-live-contract.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:40-0300) |
| red-as-expected-redux-live-contract | STALE | 1 | 1 | 2026-11-09T08:04:40-0300 | redux-live-contract-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:04:40-0300) |
| word-split-oracle | STALE | 0 | 0 | 2026-11-08T18:49:05-0300 | word-split-oracle.log | deps mudaram depois da medicao (medido 2026-11-08T18:49:05-0300) |
| red-as-expected-word-split-oracle | STALE | 1 | 1 | 2026-11-08T18:49:06-0300 | word-split-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:49:06-0300) |
| vad-option-probe | STALE | 0 | 0 | 2026-11-08T18:49:20-0300 | vad-option-probe.log | deps mudaram depois da medicao (medido 2026-11-08T18:49:20-0300) |
| red-as-expected-vad-option-probe | STALE | 1 | 1 | 2026-11-08T18:49:21-0300 | vad-option-probe-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:49:21-0300) |
| youtube-track-wiring | FAIL | 1 | 0 | 2026-11-09T08:04:42-0300 | youtube-track-wiring.log | rc=1 != esperado 0 |
| tap-open-timeout | FAIL | 1 | 0 | 2026-11-09T08:05:17-0300 | tap-open-timeout.log | rc=1 != esperado 0 |
| ui-stall-oracle | STALE | 0 | 0 | 2026-11-09T08:05:22-0300 | ui-stall-oracle.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:22-0300) |
| mute-audio | NOT RUN | - | 0 | - | mute-audio.log | sem registo no stepcache (o passo nao completou) |
| device-silence | NOT RUN | - | 0 | - | device-silence.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-device-silence | NOT RUN | - | 1 | - | device-silence-neg.log | sem registo no stepcache (o passo nao completou) |
| console-window-audit | FAIL | 1 | 0 | 2026-11-09T08:05:36-0300 | console-window-audit.log | rc=1 != esperado 0 |
| red-as-expected-console-window-audit | EXPECTED-RED | 1 | 1 | 2026-11-09T08:05:37-0300 | console-window-audit-neg.log | always |
| red-as-expected-console-window-watch | EXPECTED-RED | 1 | 1 | 2026-11-09T08:05:37-0300 | console-window-watch-neg.log | always |
| shell-orphans | PASS | 0 | 0 | 2026-11-09T08:05:39-0300 | shell-orphans.log | always |
| red-as-expected-shell-orphans | EXPECTED-RED | 1 | 1 | 2026-11-09T08:05:44-0300 | shell-orphans-neg.log | always |
| capture-exclude | PASS | 0 | 0 | 2026-11-09T08:05:44-0300 | capture-exclude.log | always |
| red-as-expected-capture-exclude | EXPECTED-RED | 1 | 1 | 2026-11-09T08:05:45-0300 | capture-exclude-neg.log | always |
| history-merge | STALE | 0 | 0 | 2026-11-09T08:05:45-0300 | history-merge.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:45-0300) |
| red-as-expected-history-merge | STALE | 1 | 1 | 2026-11-09T08:05:46-0300 | history-merge-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:46-0300) |
| history-context | STALE | 0 | 0 | 2026-11-09T08:05:47-0300 | history-context.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:47-0300) |
| red-as-expected-history-context | STALE | 1 | 1 | 2026-11-09T08:05:48-0300 | history-context-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:48-0300) |
| history-route | NOT RUN | - | 0 | - | history-route.log | sem registo no stepcache (o passo nao completou) |
| history-route-long | NOT RUN | - | 0 | - | history-route-long.log | sem registo no stepcache (o passo nao completou) |
| reveal-clock | STALE | 0 | 0 | 2026-11-09T08:05:49-0300 | reveal-clock.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:49-0300) |
| red-as-expected-reveal-clock | EXPECTED-RED | 1 | 1 | 2026-11-09T08:05:49-0300 | reveal-clock-neg.log | always |
| tap-first-block | STALE | 0 | 0 | 2026-11-09T08:05:50-0300 | tap-first-block.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:50-0300) |
| red-as-expected-tap-first-block | STALE | 1 | 1 | 2026-11-09T08:05:50-0300 | tap-first-block-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:50-0300) |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-09T08:05:51-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-09T08:05:52-0300 | owner-audio-gate-neg.log | always |
| worker-providers | STALE | 0 | 0 | 2026-11-09T08:05:52-0300 | worker-providers.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:52-0300) |
| red-as-expected-worker-providers | EXPECTED-RED | 1 | 1 | 2026-11-09T08:05:53-0300 | worker-providers-neg.log | always |
| review-f1f3 | STALE | 0 | 0 | 2026-11-09T08:05:54-0300 | review-f1f3.log | deps mudaram depois da medicao (medido 2026-11-09T08:05:54-0300) |
| review-tapstop | STALE | 0 | 0 | 2026-11-05T15:00:43-0300 | review-tapstop.log | deps mudaram depois da medicao (medido 2026-11-05T15:00:43-0300) |
| strip-surface-oracle | STALE | 0 | 0 | 2026-11-09T08:06:14-0300 | strip-surface-oracle.log | deps mudaram depois da medicao (medido 2026-11-09T08:06:14-0300) |
| strip-width | STALE | 0 | 0 | 2026-11-09T08:06:15-0300 | strip-width.log | deps mudaram depois da medicao (medido 2026-11-09T08:06:15-0300) |
| red-as-expected-strip-width | STALE | 1 | 1 | 2026-11-09T08:06:16-0300 | strip-width-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:06:16-0300) |
| strip-stats-log-budget | NOT RUN | - | 0 | - | strip-stats-log.log | sem registo no stepcache (o passo nao completou) |
| strip-hot-reload | STALE | 0 | 0 | 2026-11-09T08:06:30-0300 | strip-reload.log | deps mudaram depois da medicao (medido 2026-11-09T08:06:30-0300) |
| strip-surface-runtime | NOT RUN | - | 0 | - | strip-surface.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-strip-surface | NOT RUN | - | 1 | - | strip-surface-neg.log | sem registo no stepcache (o passo nao completou) |
| strip-geometry-restore | NOT RUN | - | 0 | - | strip-restore.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-wave | NOT RUN | - | 0 | - | strip-stats.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-05T15:01:18-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-09T08:06:40-0300 | hotkey-registration.log | always |
| hotkey-delivery | STALE | 0 | 0 | 2026-11-09T08:06:42-0300 | hotkey-delivery.log | deps mudaram depois da medicao (medido 2026-11-09T08:06:42-0300) |
| open-close-stall | STALE | 0 | 0 | 2026-11-09T08:06:50-0300 | open-close-stall.log | deps mudaram depois da medicao (medido 2026-11-09T08:06:50-0300) |
| red-as-expected-open-close-stall | STALE | 1 | 1 | 2026-11-09T08:07:10-0300 | open-close-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:10-0300) |
| autostart-status | STALE | 0 | 0 | 2026-11-09T08:07:11-0300 | autostart-status.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:11-0300) |
| control-verdict-gate-unguard | STALE | 0 | 0 | 2026-11-08T18:51:47-0300 | control-verdict-gate-unguard.log | deps mudaram depois da medicao (medido 2026-11-08T18:51:47-0300) |
| control-history-producer-stamp-nvidia | STALE | 0 | 0 | 2026-11-08T18:51:48-0300 | control-history-producer-stamp-nvidia.log | deps mudaram depois da medicao (medido 2026-11-08T18:51:48-0300) |
| control-redux-flag-neg-arm | STALE | 0 | 0 | 2026-11-09T08:07:12-0300 | control-redux-flag-neg-arm.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:12-0300) |
| control-panel-exit3-neg-arm | NOT RUN | - | 0 | - | control-panel-exit3-neg-arm.log | sem registo no stepcache (o passo nao completou) |
| control-wasapi-com-init | STALE | 0 | 0 | 2026-11-05T15:01:43-0300 | control-wasapi-com-init.log | deps mudaram depois da medicao (medido 2026-11-05T15:01:43-0300) |
| control-panel2-repeat-revert | STALE | 0 | 0 | 2026-11-09T08:07:14-0300 | control-panel2-repeat-revert.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:14-0300) |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-11-05T15:01:45-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | STALE | 1 | 1 | 2026-11-09T08:07:15-0300 | control-historico-gate-off.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:15-0300) |
| search-oracle | STALE | 0 | 0 | 2026-11-09T08:07:15-0300 | search-oracle.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:15-0300) |
| red-as-expected-search-oracle | STALE | 1 | 1 | 2026-11-09T08:07:17-0300 | search-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:17-0300) |
| panel-search-keyboard | STALE | 0 | 0 | 2026-11-09T08:07:21-0300 | panel-search-keyboard.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:21-0300) |
| red-as-expected-panel-search-keyboard | STALE | 1 | 1 | 2026-11-09T08:07:25-0300 | panel-search-keyboard-neg.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:25-0300) |
| fresh-processor-probe | STALE | 0 | 0 | 2026-11-08T18:52:08-0300 | fresh-processor.log | deps mudaram depois da medicao (medido 2026-11-08T18:52:08-0300) |
| stepcache-oracle | PASS | 0 | 0 | 2026-11-08T17:45:51-0300 | stepcache-oracle.log | - |
| battery-plan | STALE | 0 | 0 | 2026-11-09T08:07:30-0300 | battery-plan.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:30-0300) |
| red-as-expected-battery-plan | EXPECTED-RED | 1 | 1 | 2026-11-09T08:07:47-0300 | battery-plan-neg.log | always |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-09T08:07:47-0300 | _skip-guard.log | always |
| altc-first-caption | NOT RUN | - | 0 | - | altc-first-caption.log | sem registo no stepcache (o passo nao completou) |
| altc-gesture | STALE | 0 | 0 | 2026-11-09T08:07:54-0300 | altc-gesture.log | deps mudaram depois da medicao (medido 2026-11-09T08:07:54-0300) |
| headphone-cut | NO-VERDICT | 0 | 0 | 2026-11-08T22:19:51-0300 | headphone-cut.log | log alterado depois do registo |
| incomplete-word | STALE | 0 | 0 | 2026-11-08T22:19:52-0300 | incomplete-word.log | deps mudaram depois da medicao (medido 2026-11-08T22:19:52-0300) |
| ladder-signal | STALE | 0 | 0 | 2026-11-08T22:19:53-0300 | ladder-signal.log | deps mudaram depois da medicao (medido 2026-11-08T22:19:53-0300) |
| launch-as-token | PASS | 0 | 0 | 2026-11-08T22:19:57-0300 | launch-as-token.log | always |
| live-code-freshness | STALE | 0 | 0 | 2026-11-08T22:19:58-0300 | live-code-freshness.log | deps mudaram depois da medicao (medido 2026-11-08T22:19:58-0300) |
| live-code-freshness-control | STALE | 0 | 0 | 2026-11-08T22:19:59-0300 | live-code-freshness-control.log | deps mudaram depois da medicao (medido 2026-11-08T22:19:59-0300) |
| red-as-expected-live-code-freshness | STALE | 1 | 1 | 2026-11-08T22:20:01-0300 | live-code-freshness-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:20:01-0300) |
| load-shedding | STALE | 0 | 0 | 2026-11-08T22:20:12-0300 | load-shedding.log | deps mudaram depois da medicao (medido 2026-11-08T22:20:12-0300) |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-08T22:20:13-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | STALE | 1 | 1 | 2026-11-08T22:20:33-0300 | altc-gesture-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:20:33-0300) |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-08T22:20:34-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-08T22:20:35-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | STALE | 1 | 1 | 2026-11-08T22:20:36-0300 | ladder-signal-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:20:36-0300) |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-08T22:20:39-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-08T22:20:39-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-08T22:20:44-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | STALE | 1 | 1 | 2026-11-08T22:21:16-0300 | load-shedding-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:16-0300) |
| red-as-expected-shell-relaunch | NOT RUN | - | 1 | - | shell-relaunch-neg.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-word-clock | STALE | 1 | 1 | 2026-11-08T22:21:18-0300 | word-clock-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:18-0300) |
| red-as-expected-youtube-monotonic | STALE | 1 | 1 | 2026-11-08T22:21:19-0300 | youtube-monotonic-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:19-0300) |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-08T22:21:20-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | STALE | 1 | 1 | 2026-11-08T22:21:22-0300 | youtube-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:22-0300) |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-08T22:21:23-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NOT RUN | - | 0 | - | shell-relaunch.log | sem registo no stepcache (o passo nao completou) |
| census-instrument | STALE | 0 | 0 | 2026-11-08T18:55:00-0300 | census-instrument.log | deps mudaram depois da medicao (medido 2026-11-08T18:55:00-0300) |
| red-as-expected-census-instrument | STALE | 1 | 1 | 2026-11-08T18:55:01-0300 | census-instrument-neg.log | deps mudaram depois da medicao (medido 2026-11-08T18:55:01-0300) |
| relaunch-ready | PASS | 0 | 0 | 2026-11-08T05:47:38-0300 | relaunch-ready.log | - |
| red-as-expected-relaunch-ready | EXPECTED-RED | 1 | 1 | 2026-11-08T05:47:52-0300 | relaunch-ready-neg.log | - |
| word-clock | STALE | 0 | 0 | 2026-11-08T22:21:26-0300 | word-clock.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:26-0300) |
| youtube-monotonic | STALE | 0 | 0 | 2026-11-08T22:21:28-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:28-0300) |
| youtube-rate | STALE | 0 | 0 | 2026-11-08T22:21:29-0300 | youtube-rate.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:29-0300) |
| red-as-expected-youtube-rate | STALE | 1 | 1 | 2026-11-08T22:21:30-0300 | youtube-rate-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:30-0300) |
| click-through-applied | STALE | 0 | 0 | 2026-11-08T22:21:31-0300 | click-through-applied.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:31-0300) |
| red-as-expected-click-through-applied | STALE | 1 | 1 | 2026-11-08T22:21:32-0300 | click-through-applied-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:32-0300) |
| topmost-keepalive | PASS | 0 | 0 | 2026-11-08T22:21:33-0300 | topmost-keepalive.log | always |
| red-as-expected-topmost-keepalive | EXPECTED-RED | 1 | 1 | 2026-11-08T22:21:34-0300 | topmost-keepalive-neg.log | always |
| webview2-args-scope | STALE | 0 | 0 | 2026-11-08T22:21:35-0300 | webview2-args-scope.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:35-0300) |
| red-as-expected-webview2-args-scope | STALE | 1 | 1 | 2026-11-08T22:21:36-0300 | webview2-args-scope-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:36-0300) |
| power-recovery | STALE | 0 | 0 | 2026-11-08T22:21:37-0300 | power-recovery.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:37-0300) |
| red-as-expected-power-recovery | STALE | 1 | 1 | 2026-11-08T22:21:42-0300 | power-recovery-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:42-0300) |
| power-recovery-live | NOT RUN | - | 0 | - | power-recovery-live.log | sem registo no stepcache (o passo nao completou) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-08T22:21:43-0300 | youtube-sotto-drift.log | always |
| youtube-switch | STALE | 0 | 0 | 2026-11-08T22:21:46-0300 | youtube-switch.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:46-0300) |
| yt-no-dub | STALE | 0 | 0 | 2026-11-08T22:21:47-0300 | yt-no-dub.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:47-0300) |
| stale-display | STALE | 0 | 0 | 2026-11-08T22:21:48-0300 | stale-display.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:48-0300) |
| red-as-expected-stale-display | STALE | 1 | 1 | 2026-11-08T22:21:50-0300 | stale-display-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:50-0300) |
| battery-class | STALE | 0 | 0 | 2026-11-08T22:21:51-0300 | battery-class.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:51-0300) |
| red-as-expected-battery-class | STALE | 1 | 1 | 2026-11-08T22:21:52-0300 | battery-class-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:52-0300) |
| live-queue | STALE | 0 | 0 | 2026-11-08T22:21:53-0300 | live-queue.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:53-0300) |
| red-as-expected-live-queue | STALE | 1 | 1 | 2026-11-08T22:21:56-0300 | live-queue-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:56-0300) |
| flat-endpoint | STALE | 0 | 0 | 2026-11-08T22:21:58-0300 | flat-endpoint.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:58-0300) |
| tap-silent-desktop | STALE | 0 | 0 | 2026-11-08T22:21:59-0300 | tap-silent-desktop.log | deps mudaram depois da medicao (medido 2026-11-08T22:21:59-0300) |
| red-as-expected-tap-silent-desktop | STALE | 1 | 1 | 2026-11-08T22:22:00-0300 | tap-silent-desktop-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:22:00-0300) |
| warm-engine | STALE | 0 | 0 | 2026-11-08T22:22:11-0300 | warm-engine.log | deps mudaram depois da medicao (medido 2026-11-08T22:22:11-0300) |
| red-as-expected-warm-engine | STALE | 1 | 1 | 2026-11-08T22:23:24-0300 | warm-engine-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:23:24-0300) |
| gaming-hotkey | STALE | 0 | 0 | 2026-11-08T22:23:32-0300 | gaming-hotkey.log | deps mudaram depois da medicao (medido 2026-11-08T22:23:32-0300) |
| red-as-expected-gaming-hotkey | STALE | 1 | 1 | 2026-11-08T22:24:11-0300 | gaming-hotkey-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:24:11-0300) |
| ctrlspace-swallow | STALE | 0 | 0 | 2026-11-08T22:24:13-0300 | ctrlspace-swallow.log | deps mudaram depois da medicao (medido 2026-11-08T22:24:13-0300) |
| red-as-expected-ctrlspace-swallow | STALE | 1 | 1 | 2026-11-08T22:24:21-0300 | ctrlspace-swallow-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:24:21-0300) |
| ctrlspace-swallow-os | PASS | 0 | 0 | 2026-11-08T22:24:22-0300 | ctrlspace-swallow-os.log | always |
| battery-budget | STALE | 0 | 0 | 2026-11-08T22:24:22-0300 | battery-budget.log | deps mudaram depois da medicao (medido 2026-11-08T22:24:22-0300) |
| red-as-expected-battery-budget | STALE | 1 | 1 | 2026-11-08T22:24:23-0300 | battery-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-08T22:24:23-0300) |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
