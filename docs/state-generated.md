# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=354 · PASS=136 · EXPECTED-RED=103 · FAIL=8 · STALE=89 · NO-VERDICT=1 · NOT RUN=17

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-07T13:34:03-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-11-05T14:40:17-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | PASS | 0 | 0 | 2026-11-05T19:40:42-0300 | pycompile-worker.log | - |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-11-05T14:40:18-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-11-05T15:30:25-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-11-07T10:15:27-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-11-05T20:17:27-0300 | oracle-historico-vs-redux.log | - |
| redux-transcript-path | PASS | 0 | 0 | 2026-11-07T13:34:09-0300 | redux-transcript-path.log | - |
| redux-arm-weights | PASS | 0 | 0 | 2026-11-07T13:34:10-0300 | redux-arm-weights.log | - |
| history-write | PASS | 0 | 0 | 2026-11-07T13:34:32-0300 | history-write.log | - |
| caption-cumulative | PASS | 0 | 0 | 2026-11-05T15:30:26-0300 | oracle-caption-cumulative.log | - |
| red-as-expected-caption-cumulative | EXPECTED-RED | 1 | 1 | 2026-11-05T15:30:27-0300 | caption-cumulative-neg.log | - |
| caption-lag-budget | PASS | 0 | 0 | 2026-11-07T13:34:34-0300 | caption-lag-budget.log | - |
| red-as-expected-caption-lag-budget | EXPECTED-RED | 1 | 1 | 2026-11-07T13:34:56-0300 | caption-lag-budget-neg.log | - |
| lag-note-cost | PASS | 0 | 0 | 2026-11-07T13:34:57-0300 | lag-note-cost.log | always |
| red-as-expected-lag-note-cost | EXPECTED-RED | 1 | 1 | 2026-11-07T13:35:05-0300 | lag-note-cost-neg.log | always |
| youtube-hidden-clock | PASS | 0 | 0 | 2026-11-07T13:35:07-0300 | youtube-hidden-clock.log | always |
| red-as-expected-youtube-hidden-clock | EXPECTED-RED | 1 | 1 | 2026-11-07T13:35:08-0300 | youtube-hidden-clock-neg.log | always |
| caption-overlay-screen | PASS | 0 | 0 | 2026-11-07T13:35:08-0300 | caption-overlay-screen.log | always |
| red-as-expected-caption-overlay-screen | EXPECTED-RED | 1 | 1 | 2026-11-07T13:35:09-0300 | caption-overlay-screen-neg.log | always |
| youtube-cdp-boot | PASS | 0 | 0 | 2026-11-07T13:35:12-0300 | youtube-cdp-boot.log | always |
| red-as-expected-youtube-cdp-boot | EXPECTED-RED | 1 | 1 | 2026-11-07T13:35:36-0300 | youtube-cdp-boot-neg.log | always |
| youtube-cdp-slow | PASS | 0 | 0 | 2026-11-07T13:35:43-0300 | youtube-cdp-slow.log | always |
| red-as-expected-youtube-cdp-slow | EXPECTED-RED | 1 | 1 | 2026-11-07T13:36:04-0300 | youtube-cdp-slow-neg.log | always |
| youtube-first-at-boot | PASS | 0 | 0 | 2026-11-07T13:36:14-0300 | youtube-first-at-boot.log | always |
| red-as-expected-youtube-first-at-boot | EXPECTED-RED | 1 | 1 | 2026-11-07T13:36:54-0300 | youtube-first-at-boot-neg.log | always |
| red-as-expected-redux-transcript-path | EXPECTED-RED | 1 | 1 | 2026-11-07T13:36:57-0300 | redux-transcript-path-neg.log | - |
| red-as-expected-history-write | EXPECTED-RED | 1 | 1 | 2026-11-07T13:37:03-0300 | history-write-neg.log | - |
| control-verdict-gate-drop-redux-live | PASS | 0 | 0 | 2026-11-05T19:42:46-0300 | control-verdict-gate-drop-redux-live.log | - |
| history-producer-gate | PASS | 0 | 0 | 2026-11-05T19:42:47-0300 | gate-history-producer.log | - |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-11-07T10:18:38-0300 | gate-panel-state-guard.log | - |
| verdict-gate | PASS | 0 | 0 | 2026-11-05T19:42:48-0300 | gate-verdict.log | - |
| worker-park | PASS | 0 | 0 | 2026-11-07T13:37:36-0300 | worker-park.log | always |
| red-as-expected-worker-park | EXPECTED-RED | 1 | 1 | 2026-11-07T13:37:36-0300 | worker-park-neg.log | always |
| lane2-reset-probe | PASS | 0 | 0 | 2026-11-07T10:19:13-0300 | lane2-reset.log | - |
| lane3-verdict-probe | PASS | 0 | 0 | 2026-11-05T19:43:25-0300 | lane3-verdict.log | - |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-11-05T14:46:56-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-11-05T19:43:26-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-11-07T10:44:25-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-11-05T14:47:02-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-11-07T10:44:28-0300 | panel2-dom-probe.log | - |
| panel-header-oracle | PASS | 0 | 0 | 2026-11-07T10:44:31-0300 | panel-header.log | - |
| panel-drag-targets | PASS | 0 | 0 | 2026-11-07T10:44:33-0300 | panel-drag-targets.log | - |
| panel-history-clip | PASS | 0 | 0 | 2026-11-07T10:44:36-0300 | panel-history-clip.log | - |
| panel-pause-payload | PASS | 0 | 0 | 2026-11-07T13:37:38-0300 | panel-pause-payload.log | - |
| red-as-expected-panel-pause-payload | PASS | 0 | 0 | 2026-11-07T13:37:39-0300 | panel-pause-payload-neg.log | - |
| panel-deps | PASS | 0 | 0 | 2026-11-07T13:37:39-0300 | panel-deps.log | - |
| red-as-expected-panel-deps | PASS | 0 | 0 | 2026-11-07T13:37:40-0300 | panel-deps-neg.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-11-07T10:44:47-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-11-05T14:47:29-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:29-0300 | border-radius-gate-neg.log | - |
| hidden-launch | PASS | 0 | 0 | 2026-11-05T14:47:36-0300 | hidden-launch.log | - |
| red-as-expected-hidden-launch | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:37-0300 | hidden-launch-neg.log | - |
| step-deadline | PASS | 0 | 0 | 2026-11-05T14:47:49-0300 | step-deadline.log | - |
| red-as-expected-step-deadline | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:02-0300 | step-deadline-neg.log | - |
| emit-prewebview | PASS | 0 | 0 | 2026-11-07T13:37:41-0300 | emit-prewebview.log | - |
| red-as-expected-emit-prewebview | FAIL | 0 | 1 | 2026-11-07T13:37:42-0300 | emit-prewebview-neg.log | rc=0 != esperado 1 |
| hotkey-live-edge | PASS | 0 | 0 | 2026-11-07T13:37:47-0300 | hotkey-live-edge.log | - |
| red-as-expected-hotkey-live-edge | EXPECTED-RED | 1 | 1 | 2026-11-07T13:37:54-0300 | hotkey-live-edge-neg.log | - |
| lane-screen-gate | PASS | 0 | 0 | 2026-11-07T13:38:00-0300 | lane-screen-gate.log | - |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:29-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-07T13:38:01-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-11-05T14:48:31-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:31-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-07T13:38:01-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-07T13:38:02-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | PASS | 0 | 0 | 2026-11-07T13:38:02-0300 | youtube-foreign-paint.log | - |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-07T13:38:03-0300 | youtube-foreign-paint-neg.log | - |
| input-path | PASS | 0 | 0 | 2026-11-07T13:38:23-0300 | input-path.log | - |
| red-as-expected-input-path | EXPECTED-RED | 1 | 1 | 2026-11-07T13:38:25-0300 | input-path-neg.log | - |
| exception-hygiene | PASS | 0 | 0 | 2026-11-07T13:38:27-0300 | exception-hygiene.log | - |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-05T15:48:15-0300 | exception-hygiene-neg.log | - |
| seam-coverage | PASS | 0 | 0 | 2026-11-07T13:38:52-0300 | seam-coverage.log | - |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:13-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-05T14:50:14-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:15-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-05T19:44:31-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-05T19:44:32-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-07T13:38:53-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-07T13:38:55-0300 | external-resume-neg.log | - |
| silence-kill | PASS | 0 | 0 | 2026-11-07T13:38:56-0300 | silence-kill.log | - |
| red-as-expected-silence-kill | EXPECTED-RED | 1 | 1 | 2026-11-07T13:38:56-0300 | silence-kill-neg.log | - |
| worker-churn | PASS | 0 | 0 | 2026-11-07T13:39:00-0300 | worker-churn.log | - |
| red-as-expected-worker-churn | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:03-0300 | worker-churn-neg.log | - |
| rss-trend | PASS | 0 | 0 | 2026-11-07T13:39:04-0300 | rss-trend.log | - |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:32-0300 | rss-trend-neg.log | - |
| death-cause | PASS | 0 | 0 | 2026-11-07T13:39:05-0300 | death-cause.log | - |
| red-as-expected-death-cause | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:07-0300 | death-cause-neg.log | - |
| caption-seam-dedup | PASS | 0 | 0 | 2026-11-05T19:44:42-0300 | caption-seam-dedup.log | - |
| red-as-expected-caption-seam-dedup | EXPECTED-RED | 1 | 1 | 2026-11-05T19:44:43-0300 | caption-seam-dedup-neg.log | - |
| freeze-census | PASS | 0 | 0 | 2026-11-05T19:44:47-0300 | freeze-census.log | - |
| red-as-expected-caption-budget | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:08-0300 | caption-budget-neg.log | - |
| dead-app-exit | PASS | 0 | 0 | 2026-11-07T13:39:30-0300 | dead-app-exit.log | - |
| shell-priority | PASS | 0 | 0 | 2026-11-07T13:39:30-0300 | shell-priority.log | - |
| red-as-expected-shell-priority | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:31-0300 | shell-priority-neg.log | - |
| tray-menu | PASS | 0 | 0 | 2026-11-07T13:39:31-0300 | tray-menu.log | - |
| red-as-expected-tray-menu | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:34-0300 | tray-menu-neg.log | - |
| hotkey-panels-switch | PASS | 0 | 0 | 2026-11-07T13:39:35-0300 | hotkey-panels-switch.log | - |
| red-as-expected-hotkey-panels-switch | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:36-0300 | hotkey-panels-switch-neg.log | - |
| caption-kept-on-hide | PASS | 0 | 0 | 2026-11-07T13:39:37-0300 | caption-kept-on-hide.log | - |
| red-as-expected-caption-kept-on-hide | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:38-0300 | caption-kept-on-hide-neg.log | - |
| caption-switch-race | PASS | 0 | 0 | 2026-11-07T13:39:39-0300 | caption-switch-race.log | - |
| red-as-expected-caption-switch-race | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:40-0300 | caption-switch-race-neg.log | - |
| word-glue | PASS | 0 | 0 | 2026-11-05T19:45:17-0300 | word-glue.log | - |
| red-as-expected-word-glue | EXPECTED-RED | 1 | 1 | 2026-11-05T19:45:18-0300 | word-glue-neg.log | - |
| punct-prosody | PASS | 0 | 0 | 2026-11-05T19:45:18-0300 | punct-prosody.log | - |
| red-as-expected-punct-prosody | EXPECTED-RED | 1 | 1 | 2026-11-05T19:45:19-0300 | punct-prosody-neg.log | - |
| punct-model | PASS | 0 | 0 | 2026-11-05T20:20:21-0300 | punct-model.log | - |
| red-as-expected-punct-model | EXPECTED-RED | 1 | 1 | 2026-11-05T20:20:22-0300 | punct-model-neg.log | - |
| panel-prefix-row | PASS | 0 | 0 | 2026-11-07T10:25:01-0300 | panel-prefix-row.log | - |
| red-as-expected-panel-prefix-row | EXPECTED-RED | 1 | 1 | 2026-11-07T10:25:02-0300 | panel-prefix-row-neg.log | - |
| fusion | PASS | 0 | 0 | 2026-11-05T14:51:09-0300 | fusion.log | - |
| red-as-expected-fusion | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:09-0300 | fusion-neg.log | - |
| agc-peak-ceiling | PASS | 0 | 0 | 2026-11-05T19:45:24-0300 | agc-peak-ceiling.log | - |
| red-as-expected-agc-peak-ceiling | EXPECTED-RED | 1 | 1 | 2026-11-05T19:45:25-0300 | agc-peak-ceiling-neg.log | - |
| reveal-park | PASS | 0 | 0 | 2026-11-07T13:39:43-0300 | reveal-park.log | - |
| red-as-expected-reveal-park | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:49-0300 | reveal-park-neg.log | - |
| youtube-verbatim | PASS | 0 | 0 | 2026-11-07T13:39:53-0300 | youtube-verbatim.log | - |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:23-0300 | youtube-verbatim-neg.log | - |
| code-health | PASS | 0 | 0 | 2026-11-07T13:39:55-0300 | code-health.log | always |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:58-0300 | code-health-neg.log | always |
| undefined-names | PASS | 0 | 0 | 2026-11-07T13:39:59-0300 | undefined-names.log | always |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-07T13:39:59-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | PASS | 0 | 0 | 2026-11-07T13:40:01-0300 | battery-heavy-gate.log | - |
| red-as-expected-battery-heavy-gate | EXPECTED-RED | 1 | 1 | 2026-11-07T13:40:09-0300 | battery-heavy-gate-neg.log | - |
| task-resolver-gate | PASS | 0 | 0 | 2026-11-07T13:40:09-0300 | task-resolver-gate.log | - |
| red-as-expected-task-resolver-gate | EXPECTED-RED | 1 | 1 | 2026-11-07T13:40:10-0300 | task-resolver-gate-neg.log | - |
| claims-date | PASS | 0 | 0 | 2026-11-07T13:40:10-0300 | claims-date.log | - |
| red-as-expected-claims-date | EXPECTED-RED | 1 | 1 | 2026-11-07T13:40:11-0300 | claims-date-neg.log | - |
| stall-under-load | FAIL | 1 | 0 | 2026-11-07T13:40:12-0300 | stall-under-load.log | rc=1 != esperado 0 |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-07T13:40:13-0300 | stall-under-load-neg.log | always |
| paint-live-show | FAIL | 1 | 0 | 2026-11-07T13:40:51-0300 | paint-live-show.log | rc=1 != esperado 0 |
| red-as-expected-paint-live-show | EXPECTED-RED | 1 | 1 | 2026-11-07T13:41:19-0300 | paint-live-show-neg.log | always |
| panel-paint-first-measure | NOT RUN | - | 0 | - | panel-paint-first-measure.log | sem registo no stepcache (o passo nao completou) |
| panel-paint-first | PASS | 0 | 0 | 2026-11-07T13:41:19-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-07T13:41:20-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-07T13:41:20-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-07T13:41:21-0300 | receipt-provenance-neg.log | always |
| async-track-fetch | PASS | 0 | 0 | 2026-11-07T13:41:30-0300 | async-track-fetch.log | - |
| red-as-expected-async-track-fetch | EXPECTED-RED | 1 | 1 | 2026-11-07T13:41:39-0300 | async-track-fetch-neg.log | - |
| batch-queue-drain | PASS | 0 | 0 | 2026-11-05T14:52:43-0300 | batch-queue-drain.log | - |
| red-as-expected-batch-queue-drain | EXPECTED-RED | 1 | 1 | 2026-11-05T14:52:53-0300 | batch-queue-drain-neg.log | - |
| hotkey-live-toggle | PASS | 0 | 0 | 2026-11-07T13:41:53-0300 | hotkey-live-toggle.log | - |
| red-as-expected-hotkey-live-toggle | EXPECTED-RED | 1 | 1 | 2026-11-07T13:43:09-0300 | hotkey-live-toggle-neg.log | - |
| loading-placeholder | PASS | 0 | 0 | 2026-11-07T13:43:12-0300 | loading-placeholder.log | - |
| red-as-expected-loading-placeholder | EXPECTED-RED | 1 | 1 | 2026-11-07T13:43:13-0300 | loading-placeholder-neg.log | - |
| youtube-land | STALE | 0 | 0 | 2026-11-07T13:43:14-0300 | youtube-land.log | deps mudaram depois da medicao (medido 2026-11-07T13:43:14-0300) |
| red-as-expected-youtube-land | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:11-0300 | youtube-land-neg.log | - |
| time-to-first-caption | STALE | 0 | 0 | 2026-11-07T13:43:19-0300 | time-to-first-caption.log | deps mudaram depois da medicao (medido 2026-11-07T13:43:19-0300) |
| red-as-expected-time-to-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-05T19:46:54-0300 | time-to-first-caption-neg.log | - |
| first-capture-fast | PASS | 0 | 0 | 2026-11-07T13:43:21-0300 | first-capture-fast.log | always |
| red-as-expected-first-capture-fast | EXPECTED-RED | 1 | 1 | 2026-11-07T13:43:26-0300 | first-capture-fast-neg.log | - |
| youtube-land-replay | PASS | 0 | 0 | 2026-11-07T13:43:29-0300 | youtube-land-replay.log | - |
| red-as-expected-youtube-land-replay | EXPECTED-RED | 1 | 1 | 2026-11-07T13:43:32-0300 | youtube-land-replay-neg.log | - |
| yt-loop-uia | PASS | 0 | 0 | 2026-11-07T13:43:33-0300 | yt-loop-uia.log | - |
| red-as-expected-yt-loop-uia | FAIL | 2 | 1 | 2026-11-07T13:43:33-0300 | yt-loop-uia-neg.log | rc=2 != esperado 1 |
| yt-target-stale | FAIL | 1 | 0 | 2026-11-07T13:43:34-0300 | yt-target-stale.log | rc=1 != esperado 0 |
| red-as-expected-yt-target-stale | EXPECTED-RED | 1 | 1 | 2026-11-07T13:43:36-0300 | yt-target-stale-neg.log | - |
| owner-screen | PASS | 0 | 0 | 2026-11-07T13:44:19-0300 | owner-screen.log | - |
| red-as-expected-owner-screen | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:38-0300 | owner-screen-neg.log | - |
| job-object | PASS | 0 | 0 | 2026-11-05T14:53:42-0300 | job-object.log | - |
| red-as-expected-job-object | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:45-0300 | job-object-neg.log | - |
| emit-pipe-dead | PASS | 0 | 0 | 2026-11-05T19:47:19-0300 | emit-pipe-dead.log | - |
| red-as-expected-emit-pipe-dead | EXPECTED-RED | 1 | 1 | 2026-11-05T19:47:19-0300 | emit-pipe-dead-neg.log | - |
| state-page-write | NO-VERDICT | 0 | 0 | 2026-11-07T11:13:17-0300 | state-page-write.log | log alterado depois do registo |
| state-page | STALE | 0 | 0 | 2026-11-07T11:13:24-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-07T11:13:24-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-07T11:14:49-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:14:49-0300) |
| battery-wiring | STALE | 0 | 0 | 2026-11-07T11:14:50-0300 | battery-wiring.log | deps mudaram depois da medicao (medido 2026-11-07T11:14:50-0300) |
| red-as-expected-battery-wiring | STALE | 1 | 1 | 2026-11-07T11:14:56-0300 | battery-wiring-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:14:56-0300) |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-07T11:14:57-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-07T11:15:01-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | STALE | 0 | 0 | 2026-11-07T11:15:03-0300 | youtube-1to1.log | deps mudaram depois da medicao (medido 2026-11-07T11:15:03-0300) |
| red-as-expected-youtube-1to1 | STALE | 1 | 1 | 2026-11-07T11:15:07-0300 | youtube-1to1-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:15:07-0300) |
| youtube-cdp-source | STALE | 0 | 0 | 2026-11-07T11:15:15-0300 | youtube-cdp-source.log | deps mudaram depois da medicao (medido 2026-11-07T11:15:15-0300) |
| red-as-expected-youtube-cdp-source | STALE | 1 | 1 | 2026-11-07T11:15:52-0300 | youtube-cdp-source-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:15:52-0300) |
| caption-producer | STALE | 0 | 0 | 2026-11-07T11:15:52-0300 | caption-producer.log | deps mudaram depois da medicao (medido 2026-11-07T11:15:52-0300) |
| red-as-expected-caption-producer | STALE | 1 | 1 | 2026-11-07T11:15:53-0300 | caption-producer-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:15:53-0300) |
| caption-style | STALE | 0 | 0 | 2026-11-07T11:15:56-0300 | caption-style.log | deps mudaram depois da medicao (medido 2026-11-07T11:15:56-0300) |
| red-as-expected-caption-style | STALE | 1 | 1 | 2026-11-07T11:15:58-0300 | caption-style-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:15:58-0300) |
| panel-commit-stable | STALE | 0 | 0 | 2026-11-07T11:17:33-0300 | panel-commit-stable.log | deps mudaram depois da medicao (medido 2026-11-07T11:17:33-0300) |
| red-as-expected-panel-commit-stable | STALE | 1 | 1 | 2026-11-07T11:19:20-0300 | panel-commit-stable-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:20-0300) |
| paint-row-seam | STALE | 0 | 0 | 2026-11-07T11:19:20-0300 | paint-row-seam.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:20-0300) |
| red-as-expected-paint-row-seam | STALE | 1 | 1 | 2026-11-07T11:19:20-0300 | paint-row-seam-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:20-0300) |
| load-bg-window | PASS | 0 | 0 | 2026-11-07T11:19:21-0300 | load-bg-window.log | always |
| red-as-expected-load-bg-window | EXPECTED-RED | 1 | 1 | 2026-11-07T11:19:22-0300 | load-bg-window-neg.log | always |
| page-scan-browser | STALE | 0 | 0 | 2026-11-07T11:19:23-0300 | page-scan-browser.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:23-0300) |
| red-as-expected-page-scan-browser | STALE | 1 | 1 | 2026-11-07T11:19:24-0300 | page-scan-browser-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:24-0300) |
| paused-pace | STALE | 0 | 0 | 2026-11-07T11:19:25-0300 | paused-pace.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:25-0300) |
| red-as-expected-paused-pace | STALE | 1 | 1 | 2026-11-07T11:19:26-0300 | paused-pace-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:26-0300) |
| stutter-caption | NOT RUN | - | 0 | - | stutter-caption.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-stutter-caption | NOT RUN | - | 1 | - | stutter-caption-neg.log | sem registo no stepcache (o passo nao completou) |
| parakeet-ultra | NOT RUN | - | 0 | - | parakeet-ultra.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-parakeet-ultra | EXPECTED-RED | 1 | 1 | 2026-11-07T11:19:26-0300 | parakeet-ultra-neg.log | always |
| hotkey-observed | STALE | 0 | 0 | 2026-11-07T11:19:32-0300 | hotkey-observed.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:32-0300) |
| red-as-expected-hotkey-observed | STALE | 1 | 1 | 2026-11-07T11:19:37-0300 | hotkey-observed-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:37-0300) |
| youtube-reveal | STALE | 0 | 0 | 2026-11-07T11:19:38-0300 | youtube-reveal.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:38-0300) |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-07T11:19:40-0300 | youtube-reveal-neg.log | always |
| youtube-rows | STALE | 0 | 0 | 2026-11-07T11:19:41-0300 | youtube-rows.log | deps mudaram depois da medicao (medido 2026-11-07T11:19:41-0300) |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-07T11:19:43-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-07T11:19:44-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-07T11:19:44-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-07T11:20:00-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-07T11:20:01-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-07T11:20:01-0300 | bend-laws-model-neg.log | always |
| panel-hidden-at-startup-oracle | STALE | 0 | 0 | 2026-11-07T10:53:55-0300 | panel-hidden-at-startup.log | deps mudaram depois da medicao (medido 2026-11-07T10:53:55-0300) |
| red-as-expected-panel-hidden-at-startup | STALE | 1 | 1 | 2026-11-07T10:53:58-0300 | panel-hidden-at-startup-neg.log | deps mudaram depois da medicao (medido 2026-11-07T10:53:58-0300) |
| panel-nav-stall | STALE | 0 | 0 | 2026-11-07T10:53:59-0300 | panel-nav-stall.log | deps mudaram depois da medicao (medido 2026-11-07T10:53:59-0300) |
| red-as-expected-panel-nav-stall | STALE | 1 | 1 | 2026-11-07T10:54:01-0300 | panel-nav-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:01-0300) |
| worker-start-wiring | STALE | 0 | 0 | 2026-11-07T10:54:02-0300 | wiring-worker-start.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:02-0300) |
| red-as-expected-worker-start-wiring | STALE | 1 | 1 | 2026-11-07T10:54:03-0300 | wiring-worker-start-neg.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:03-0300) |
| embedded-js-check | STALE | 0 | 0 | 2026-11-07T10:54:04-0300 | embedded-js.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:04-0300) |
| lane1-worker-default-arms | STALE | 0 | 0 | 2026-11-07T10:54:04-0300 | lane1-arms.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:04-0300) |
| external-subs-stability | PASS | 0 | 0 | 2026-11-05T19:53:37-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | STALE | 0 | 0 | 2026-11-07T11:20:02-0300 | external-caption-chrome-census.log | deps mudaram depois da medicao (medido 2026-11-07T11:20:02-0300) |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-11-05T19:53:38-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-05T19:53:39-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-11-05T14:58:01-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-05T14:58:03-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-11-05T14:58:04-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-11-05T14:58:04-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:05-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-11-05T14:58:09-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:12-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-11-05T15:39:14-0300 | gitattributes-verify.log | - |
| agents-md-pins | FAIL | 1 | 0 | 2026-11-07T11:20:04-0300 | agents-md-pins.log | rc=1 != esperado 0 |
| lang-id-oracle | PASS | 0 | 0 | 2026-11-05T19:53:51-0300 | lang-id-oracle.log | - |
| red-as-expected-lang-id-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T19:54:10-0300 | lang-id-oracle-neg.log | - |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-05T14:59:14-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:15-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-11-05T14:59:16-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:18-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-07T10:54:07-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:07-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-07T10:54:07-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:07-0300) |
| per-app-source-plumbing | PASS | 0 | 0 | 2026-11-05T19:54:13-0300 | per-app-source-plumbing.log | - |
| red-as-expected-per-app-source-plumbing | EXPECTED-RED | 1 | 1 | 2026-11-05T19:54:14-0300 | per-app-source-plumbing-neg.log | - |
| redux-live-contract | PASS | 0 | 0 | 2026-11-07T10:54:08-0300 | redux-live-contract.log | - |
| red-as-expected-redux-live-contract | EXPECTED-RED | 1 | 1 | 2026-11-07T10:54:08-0300 | redux-live-contract-neg.log | - |
| word-split-oracle | PASS | 0 | 0 | 2026-11-05T19:54:15-0300 | word-split-oracle.log | - |
| red-as-expected-word-split-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T19:54:16-0300 | word-split-oracle-neg.log | - |
| vad-option-probe | PASS | 0 | 0 | 2026-11-05T19:54:28-0300 | vad-option-probe.log | - |
| red-as-expected-vad-option-probe | EXPECTED-RED | 1 | 1 | 2026-11-05T19:54:29-0300 | vad-option-probe-neg.log | - |
| youtube-track-wiring | STALE | 0 | 0 | 2026-11-07T10:54:10-0300 | youtube-track-wiring.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:10-0300) |
| tap-open-timeout | STALE | 0 | 0 | 2026-11-07T10:54:44-0300 | tap-open-timeout.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:44-0300) |
| ui-stall-oracle | STALE | 0 | 0 | 2026-11-07T10:54:51-0300 | ui-stall-oracle.log | deps mudaram depois da medicao (medido 2026-11-07T10:54:51-0300) |
| mute-audio | NOT RUN | - | 0 | - | mute-audio.log | sem registo no stepcache (o passo nao completou) |
| device-silence | NOT RUN | - | 0 | - | device-silence.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-device-silence | NOT RUN | - | 1 | - | device-silence-neg.log | sem registo no stepcache (o passo nao completou) |
| console-window-audit | PASS | 0 | 0 | 2026-11-07T11:20:17-0300 | console-window-audit.log | always |
| red-as-expected-console-window-audit | EXPECTED-RED | 1 | 1 | 2026-11-07T11:20:17-0300 | console-window-audit-neg.log | always |
| red-as-expected-console-window-watch | EXPECTED-RED | 1 | 1 | 2026-11-07T11:20:18-0300 | console-window-watch-neg.log | always |
| capture-exclude | PASS | 0 | 0 | 2026-11-07T11:20:18-0300 | capture-exclude.log | always |
| red-as-expected-capture-exclude | EXPECTED-RED | 1 | 1 | 2026-11-07T11:20:19-0300 | capture-exclude-neg.log | always |
| history-merge | STALE | 0 | 0 | 2026-11-07T11:20:20-0300 | history-merge.log | deps mudaram depois da medicao (medido 2026-11-07T11:20:20-0300) |
| red-as-expected-history-merge | STALE | 1 | 1 | 2026-11-07T11:20:20-0300 | history-merge-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:20:20-0300) |
| reveal-clock | STALE | 0 | 0 | 2026-11-07T11:20:21-0300 | reveal-clock.log | deps mudaram depois da medicao (medido 2026-11-07T11:20:21-0300) |
| red-as-expected-reveal-clock | EXPECTED-RED | 1 | 1 | 2026-11-07T11:20:21-0300 | reveal-clock-neg.log | always |
| tap-first-block | PASS | 0 | 0 | 2026-11-07T11:20:22-0300 | tap-first-block.log | always |
| red-as-expected-tap-first-block | EXPECTED-RED | 1 | 1 | 2026-11-07T11:20:22-0300 | tap-first-block-neg.log | always |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-07T11:20:23-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-07T11:20:24-0300 | owner-audio-gate-neg.log | always |
| worker-providers | STALE | 0 | 0 | 2026-11-07T11:20:25-0300 | worker-providers.log | deps mudaram depois da medicao (medido 2026-11-07T11:20:25-0300) |
| red-as-expected-worker-providers | EXPECTED-RED | 1 | 1 | 2026-11-07T11:20:25-0300 | worker-providers-neg.log | always |
| review-f1f3 | STALE | 0 | 0 | 2026-11-07T10:55:07-0300 | review-f1f3.log | deps mudaram depois da medicao (medido 2026-11-07T10:55:07-0300) |
| review-tapstop | PASS | 0 | 0 | 2026-11-05T15:00:43-0300 | review-tapstop.log | - |
| strip-surface-oracle | FAIL | 3 | 0 | 2026-11-07T11:20:46-0300 | strip-surface-oracle.log | rc=3 != esperado 0 |
| strip-stats-log-budget | NOT RUN | - | 0 | - | strip-stats-log.log | sem registo no stepcache (o passo nao completou) |
| strip-hot-reload | STALE | 0 | 0 | 2026-11-07T10:55:43-0300 | strip-reload.log | deps mudaram depois da medicao (medido 2026-11-07T10:55:43-0300) |
| strip-surface-runtime | NOT RUN | - | 0 | - | strip-surface.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-strip-surface | NOT RUN | - | 1 | - | strip-surface-neg.log | sem registo no stepcache (o passo nao completou) |
| strip-geometry-restore | NOT RUN | - | 0 | - | strip-restore.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-wave | NOT RUN | - | 0 | - | strip-stats.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-05T15:01:18-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-07T11:20:48-0300 | hotkey-registration.log | always |
| hotkey-delivery | STALE | 0 | 0 | 2026-11-07T11:20:49-0300 | hotkey-delivery.log | deps mudaram depois da medicao (medido 2026-11-07T11:20:49-0300) |
| open-close-stall | STALE | 0 | 0 | 2026-11-07T10:55:48-0300 | open-close-stall.log | deps mudaram depois da medicao (medido 2026-11-07T10:55:48-0300) |
| red-as-expected-open-close-stall | STALE | 1 | 1 | 2026-11-07T10:56:37-0300 | open-close-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-07T10:56:37-0300) |
| autostart-status | STALE | 0 | 0 | 2026-11-07T11:20:50-0300 | autostart-status.log | deps mudaram depois da medicao (medido 2026-11-07T11:20:50-0300) |
| control-verdict-gate-unguard | PASS | 0 | 0 | 2026-11-05T19:56:55-0300 | control-verdict-gate-unguard.log | - |
| control-history-producer-stamp-nvidia | PASS | 0 | 0 | 2026-11-05T19:56:57-0300 | control-history-producer-stamp-nvidia.log | - |
| control-redux-flag-neg-arm | STALE | 0 | 0 | 2026-11-07T10:56:46-0300 | control-redux-flag-neg-arm.log | deps mudaram depois da medicao (medido 2026-11-07T10:56:46-0300) |
| control-panel-exit3-neg-arm | NOT RUN | - | 0 | - | control-panel-exit3-neg-arm.log | sem registo no stepcache (o passo nao completou) |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-11-05T15:01:43-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | PASS | 0 | 0 | 2026-11-07T10:56:57-0300 | control-panel2-repeat-revert.log | - |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-11-05T15:01:45-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | EXPECTED-RED | 1 | 1 | 2026-11-05T20:30:56-0300 | control-historico-gate-off.log | - |
| search-oracle | STALE | 0 | 0 | 2026-11-07T10:56:59-0300 | search-oracle.log | deps mudaram depois da medicao (medido 2026-11-07T10:56:59-0300) |
| red-as-expected-search-oracle | STALE | 1 | 1 | 2026-11-07T10:57:08-0300 | search-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-07T10:57:08-0300) |
| panel-search-keyboard | STALE | 0 | 0 | 2026-11-07T10:57:12-0300 | panel-search-keyboard.log | deps mudaram depois da medicao (medido 2026-11-07T10:57:12-0300) |
| red-as-expected-panel-search-keyboard | STALE | 1 | 1 | 2026-11-07T10:57:15-0300 | panel-search-keyboard-neg.log | deps mudaram depois da medicao (medido 2026-11-07T10:57:15-0300) |
| fresh-processor-probe | PASS | 0 | 0 | 2026-11-05T19:57:22-0300 | fresh-processor.log | - |
| stepcache-oracle | PASS | 0 | 0 | 2026-11-05T22:22:40-0300 | stepcache-oracle.log | - |
| battery-plan | STALE | 0 | 0 | 2026-11-07T11:20:56-0300 | battery-plan.log | deps mudaram depois da medicao (medido 2026-11-07T11:20:56-0300) |
| red-as-expected-battery-plan | EXPECTED-RED | 1 | 1 | 2026-11-07T11:21:10-0300 | battery-plan-neg.log | always |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-07T11:21:11-0300 | _skip-guard.log | always |
| altc-first-caption | NOT RUN | - | 0 | - | altc-first-caption.log | sem registo no stepcache (o passo nao completou) |
| altc-gesture | STALE | 0 | 0 | 2026-11-07T11:21:18-0300 | altc-gesture.log | deps mudaram depois da medicao (medido 2026-11-07T11:21:18-0300) |
| headphone-cut | STALE | 0 | 0 | 2026-11-07T11:22:18-0300 | headphone-cut.log | deps mudaram depois da medicao (medido 2026-11-07T11:22:18-0300) |
| incomplete-word | PASS | 0 | 0 | 2026-11-07T11:22:19-0300 | incomplete-word.log | always |
| ladder-signal | STALE | 0 | 0 | 2026-11-07T11:22:20-0300 | ladder-signal.log | deps mudaram depois da medicao (medido 2026-11-07T11:22:20-0300) |
| launch-as-token | PASS | 0 | 0 | 2026-11-07T11:22:24-0300 | launch-as-token.log | always |
| live-code-freshness | STALE | 0 | 0 | 2026-11-07T11:22:24-0300 | live-code-freshness.log | deps mudaram depois da medicao (medido 2026-11-07T11:22:24-0300) |
| live-code-freshness-control | STALE | 0 | 0 | 2026-11-07T11:22:25-0300 | live-code-freshness-control.log | deps mudaram depois da medicao (medido 2026-11-07T11:22:25-0300) |
| red-as-expected-live-code-freshness | EXPECTED-RED | 1 | 1 | 2026-11-07T11:22:26-0300 | live-code-freshness-neg.log | always |
| load-shedding | STALE | 0 | 0 | 2026-11-07T11:22:29-0300 | load-shedding.log | deps mudaram depois da medicao (medido 2026-11-07T11:22:29-0300) |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-07T11:22:29-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | STALE | 1 | 1 | 2026-11-07T11:22:51-0300 | altc-gesture-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:22:51-0300) |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-07T11:22:52-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-07T11:22:52-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | EXPECTED-RED | 1 | 1 | 2026-11-07T11:22:53-0300 | ladder-signal-neg.log | always |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-07T11:22:54-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-07T11:22:54-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-07T11:22:57-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | STALE | 1 | 1 | 2026-11-07T11:23:25-0300 | load-shedding-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:25-0300) |
| red-as-expected-shell-relaunch | NOT RUN | - | 1 | - | shell-relaunch-neg.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-word-clock | EXPECTED-RED | 1 | 1 | 2026-11-07T11:23:26-0300 | word-clock-neg.log | always |
| red-as-expected-youtube-monotonic | STALE | 1 | 1 | 2026-11-07T11:23:27-0300 | youtube-monotonic-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:27-0300) |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-07T11:23:28-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | STALE | 1 | 1 | 2026-11-07T11:23:29-0300 | youtube-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:29-0300) |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-07T11:23:30-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NOT RUN | - | 0 | - | shell-relaunch.log | sem registo no stepcache (o passo nao completou) |
| word-clock | STALE | 0 | 0 | 2026-11-07T11:23:31-0300 | word-clock.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:31-0300) |
| youtube-monotonic | STALE | 0 | 0 | 2026-11-07T11:23:32-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:32-0300) |
| youtube-rate | STALE | 0 | 0 | 2026-11-07T11:23:32-0300 | youtube-rate.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:32-0300) |
| red-as-expected-youtube-rate | STALE | 1 | 1 | 2026-11-07T11:23:33-0300 | youtube-rate-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:33-0300) |
| click-through-applied | STALE | 0 | 0 | 2026-11-07T11:23:33-0300 | click-through-applied.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:33-0300) |
| red-as-expected-click-through-applied | STALE | 1 | 1 | 2026-11-07T11:23:34-0300 | click-through-applied-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:34-0300) |
| topmost-keepalive | PASS | 0 | 0 | 2026-11-07T11:23:34-0300 | topmost-keepalive.log | always |
| red-as-expected-topmost-keepalive | EXPECTED-RED | 1 | 1 | 2026-11-07T11:23:35-0300 | topmost-keepalive-neg.log | always |
| webview2-args-scope | STALE | 0 | 0 | 2026-11-07T11:23:35-0300 | webview2-args-scope.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:35-0300) |
| red-as-expected-webview2-args-scope | STALE | 1 | 1 | 2026-11-07T11:23:36-0300 | webview2-args-scope-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:36-0300) |
| power-recovery | STALE | 0 | 0 | 2026-11-07T11:23:36-0300 | power-recovery.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:36-0300) |
| red-as-expected-power-recovery | STALE | 1 | 1 | 2026-11-07T11:23:41-0300 | power-recovery-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:41-0300) |
| power-recovery-live | NOT RUN | - | 0 | - | power-recovery-live.log | sem registo no stepcache (o passo nao completou) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-07T11:23:42-0300 | youtube-sotto-drift.log | always |
| youtube-switch | STALE | 0 | 0 | 2026-11-07T11:23:45-0300 | youtube-switch.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:45-0300) |
| yt-no-dub | STALE | 0 | 0 | 2026-11-07T11:23:45-0300 | yt-no-dub.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:45-0300) |
| stale-display | STALE | 0 | 0 | 2026-11-07T11:23:46-0300 | stale-display.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:46-0300) |
| red-as-expected-stale-display | STALE | 1 | 1 | 2026-11-07T11:23:49-0300 | stale-display-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:49-0300) |
| battery-class | STALE | 0 | 0 | 2026-11-07T11:23:49-0300 | battery-class.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:49-0300) |
| red-as-expected-battery-class | STALE | 1 | 1 | 2026-11-07T11:23:50-0300 | battery-class-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:23:50-0300) |
| live-queue | PASS | 0 | 0 | 2026-11-07T11:23:51-0300 | live-queue.log | always |
| red-as-expected-live-queue | EXPECTED-RED | 1 | 1 | 2026-11-07T11:23:52-0300 | live-queue-neg.log | always |
| flat-endpoint | PASS | 0 | 0 | 2026-11-07T11:23:53-0300 | flat-endpoint.log | always |
| tap-silent-desktop | PASS | 0 | 0 | 2026-11-07T11:23:53-0300 | tap-silent-desktop.log | always |
| red-as-expected-tap-silent-desktop | EXPECTED-RED | 1 | 1 | 2026-11-07T11:23:54-0300 | tap-silent-desktop-neg.log | always |
| warm-engine | FAIL | 1 | 0 | 2026-11-07T11:24:04-0300 | warm-engine.log | rc=1 != esperado 0 |
| red-as-expected-warm-engine | STALE | 1 | 1 | 2026-11-07T11:25:07-0300 | warm-engine-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:25:07-0300) |
| gaming-hotkey | STALE | 0 | 0 | 2026-11-07T11:25:29-0300 | gaming-hotkey.log | deps mudaram depois da medicao (medido 2026-11-07T11:25:29-0300) |
| red-as-expected-gaming-hotkey | STALE | 1 | 1 | 2026-11-07T11:26:20-0300 | gaming-hotkey-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:26:20-0300) |
| ctrlspace-swallow | STALE | 0 | 0 | 2026-11-07T11:26:24-0300 | ctrlspace-swallow.log | deps mudaram depois da medicao (medido 2026-11-07T11:26:24-0300) |
| red-as-expected-ctrlspace-swallow | STALE | 1 | 1 | 2026-11-07T11:26:36-0300 | ctrlspace-swallow-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:26:36-0300) |
| ctrlspace-swallow-os | PASS | 0 | 0 | 2026-11-07T11:26:36-0300 | ctrlspace-swallow-os.log | always |
| battery-budget | STALE | 0 | 0 | 2026-11-07T11:26:37-0300 | battery-budget.log | deps mudaram depois da medicao (medido 2026-11-07T11:26:37-0300) |
| red-as-expected-battery-budget | STALE | 1 | 1 | 2026-11-07T11:26:38-0300 | battery-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-07T11:26:38-0300) |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
