# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=385 · PASS=203 · EXPECTED-RED=145 · FAIL=2 · STALE=14 · NO-VERDICT=3 · NOT RUN=18

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-08T05:14:01-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-11-05T14:40:17-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | PASS | 0 | 0 | 2026-11-08T05:14:02-0300 | pycompile-worker.log | - |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-11-05T14:40:18-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-11-05T15:30:25-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-11-08T05:14:04-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-11-05T20:17:27-0300 | oracle-historico-vs-redux.log | - |
| redux-transcript-path | PASS | 0 | 0 | 2026-11-08T05:14:08-0300 | redux-transcript-path.log | - |
| redux-arm-weights | PASS | 0 | 0 | 2026-11-08T05:14:09-0300 | redux-arm-weights.log | - |
| history-write | PASS | 0 | 0 | 2026-11-08T05:14:18-0300 | history-write.log | - |
| caption-cumulative | PASS | 0 | 0 | 2026-11-05T15:30:26-0300 | oracle-caption-cumulative.log | - |
| red-as-expected-caption-cumulative | EXPECTED-RED | 1 | 1 | 2026-11-05T15:30:27-0300 | caption-cumulative-neg.log | - |
| caption-lag-budget | PASS | 0 | 0 | 2026-11-08T05:14:19-0300 | caption-lag-budget.log | - |
| red-as-expected-caption-lag-budget | EXPECTED-RED | 1 | 1 | 2026-11-08T05:14:24-0300 | caption-lag-budget-neg.log | - |
| caption-rollup | PASS | 0 | 0 | 2026-11-08T05:14:25-0300 | caption-rollup.log | - |
| red-as-expected-caption-rollup | EXPECTED-RED | 1 | 1 | 2026-11-08T05:14:26-0300 | caption-rollup-neg.log | - |
| paint-cost | PASS | 0 | 0 | 2026-11-08T06:09:29-0300 | paint-cost.log | - |
| red-as-expected-paint-cost | EXPECTED-RED | 1 | 1 | 2026-11-08T06:09:31-0300 | paint-cost-neg.log | - |
| shell-thread-budget | PASS | 0 | 0 | 2026-11-08T06:09:33-0300 | shell-thread-budget.log | - |
| red-as-expected-shell-thread-budget | EXPECTED-RED | 1 | 1 | 2026-11-08T06:09:34-0300 | shell-thread-budget-neg.log | - |
| caption-tick-thread | PASS | 0 | 0 | 2026-11-08T05:16:16-0300 | caption-tick-thread.log | - |
| red-as-expected-caption-tick-thread | EXPECTED-RED | 1 | 1 | 2026-11-08T05:16:19-0300 | caption-tick-thread-neg.log | - |
| log-sink-dead | PASS | 0 | 0 | 2026-11-08T06:09:34-0300 | log-sink-dead.log | - |
| red-as-expected-log-sink-dead | EXPECTED-RED | 1 | 1 | 2026-11-08T06:09:35-0300 | log-sink-dead-neg.log | - |
| cdp-target-async | PASS | 0 | 0 | 2026-11-08T05:16:23-0300 | cdp-target-async.log | - |
| red-as-expected-cdp-target-async | EXPECTED-RED | 1 | 1 | 2026-11-08T05:16:33-0300 | cdp-target-async-neg.log | - |
| caption-drag | PASS | 0 | 0 | 2026-11-08T05:16:37-0300 | caption-drag.log | - |
| red-as-expected-caption-drag | NO-VERDICT | 1 | 1 | 2026-11-08T06:09:36-0300 | caption-drag-neg.log | registo com expect_rc=0 mas a bateria declara 1 |
| lag-note-cost | PASS | 0 | 0 | 2026-11-08T10:36:07-0300 | lag-note-cost.log | always |
| red-as-expected-lag-note-cost | EXPECTED-RED | 1 | 1 | 2026-11-08T10:36:11-0300 | lag-note-cost-neg.log | always |
| youtube-hidden-clock | PASS | 0 | 0 | 2026-11-08T10:36:12-0300 | youtube-hidden-clock.log | always |
| red-as-expected-youtube-hidden-clock | EXPECTED-RED | 1 | 1 | 2026-11-08T10:36:14-0300 | youtube-hidden-clock-neg.log | always |
| caption-overlay-screen | PASS | 0 | 0 | 2026-11-08T10:36:14-0300 | caption-overlay-screen.log | always |
| red-as-expected-caption-overlay-screen | EXPECTED-RED | 1 | 1 | 2026-11-08T10:36:15-0300 | caption-overlay-screen-neg.log | always |
| youtube-cdp-boot | PASS | 0 | 0 | 2026-11-08T10:36:19-0300 | youtube-cdp-boot.log | always |
| red-as-expected-youtube-cdp-boot | EXPECTED-RED | 1 | 1 | 2026-11-08T10:36:43-0300 | youtube-cdp-boot-neg.log | always |
| youtube-cdp-slow | PASS | 0 | 0 | 2026-11-08T10:36:51-0300 | youtube-cdp-slow.log | always |
| red-as-expected-youtube-cdp-slow | EXPECTED-RED | 1 | 1 | 2026-11-08T10:37:14-0300 | youtube-cdp-slow-neg.log | always |
| youtube-first-at-boot | PASS | 0 | 0 | 2026-11-08T10:37:27-0300 | youtube-first-at-boot.log | always |
| red-as-expected-youtube-first-at-boot | EXPECTED-RED | 1 | 1 | 2026-11-08T10:38:10-0300 | youtube-first-at-boot-neg.log | always |
| red-as-expected-redux-transcript-path | EXPECTED-RED | 1 | 1 | 2026-11-08T05:17:54-0300 | redux-transcript-path-neg.log | - |
| red-as-expected-history-write | EXPECTED-RED | 1 | 1 | 2026-11-08T05:18:00-0300 | history-write-neg.log | - |
| control-verdict-gate-drop-redux-live | PASS | 0 | 0 | 2026-11-08T05:18:01-0300 | control-verdict-gate-drop-redux-live.log | - |
| history-producer-gate | PASS | 0 | 0 | 2026-11-08T05:18:01-0300 | gate-history-producer.log | - |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-11-08T05:18:02-0300 | gate-panel-state-guard.log | - |
| verdict-gate | PASS | 0 | 0 | 2026-11-08T05:18:03-0300 | gate-verdict.log | - |
| worker-park | PASS | 0 | 0 | 2026-11-08T10:38:56-0300 | worker-park.log | always |
| red-as-expected-worker-park | EXPECTED-RED | 1 | 1 | 2026-11-08T10:38:59-0300 | worker-park-neg.log | always |
| lane2-reset-probe | PASS | 0 | 0 | 2026-11-08T05:18:36-0300 | lane2-reset.log | - |
| lane3-verdict-probe | PASS | 0 | 0 | 2026-11-08T05:18:39-0300 | lane3-verdict.log | - |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-11-05T14:46:56-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-11-05T19:43:26-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-11-08T05:18:42-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-11-05T14:47:02-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-11-08T05:18:49-0300 | panel2-dom-probe.log | - |
| panel-header-oracle | PASS | 0 | 0 | 2026-11-08T05:18:54-0300 | panel-header.log | - |
| panel-drag-targets | PASS | 0 | 0 | 2026-11-08T05:18:56-0300 | panel-drag-targets.log | - |
| panel-history-clip | PASS | 0 | 0 | 2026-11-08T05:18:59-0300 | panel-history-clip.log | - |
| panel-pause-payload | PASS | 0 | 0 | 2026-11-08T05:18:59-0300 | panel-pause-payload.log | - |
| red-as-expected-panel-pause-payload | PASS | 0 | 0 | 2026-11-08T05:19:00-0300 | panel-pause-payload-neg.log | - |
| outside-click-timer | PASS | 0 | 0 | 2026-11-08T05:19:20-0300 | outside-click-timer.log | - |
| red-as-expected-outside-click-timer | NO-VERDICT | 1 | 1 | 2026-11-08T06:11:49-0300 | outside-click-timer-neg.log | registo com expect_rc=0 mas a bateria declara 1 |
| panel-deps | PASS | 0 | 0 | 2026-11-08T10:39:02-0300 | panel-deps.log | - |
| red-as-expected-panel-deps | PASS | 0 | 0 | 2026-11-08T10:39:03-0300 | panel-deps-neg.log | - |
| worker-death-trace | PASS | 0 | 0 | 2026-11-08T05:19:41-0300 | worker-death-trace.log | - |
| red-as-expected-worker-death-trace | EXPECTED-RED | 1 | 1 | 2026-11-08T05:19:43-0300 | worker-death-trace-neg.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-11-08T05:19:52-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-11-05T14:47:29-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:29-0300 | border-radius-gate-neg.log | - |
| hidden-launch | PASS | 0 | 0 | 2026-11-05T14:47:36-0300 | hidden-launch.log | - |
| red-as-expected-hidden-launch | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:37-0300 | hidden-launch-neg.log | - |
| step-deadline | PASS | 0 | 0 | 2026-11-05T14:47:49-0300 | step-deadline.log | - |
| red-as-expected-step-deadline | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:02-0300 | step-deadline-neg.log | - |
| emit-prewebview | PASS | 0 | 0 | 2026-11-08T05:19:53-0300 | emit-prewebview.log | - |
| red-as-expected-emit-prewebview | EXPECTED-RED | 1 | 1 | 2026-11-08T05:19:54-0300 | emit-prewebview-neg.log | - |
| hotkey-live-edge | PASS | 0 | 0 | 2026-11-08T05:20:00-0300 | hotkey-live-edge.log | - |
| red-as-expected-hotkey-live-edge | EXPECTED-RED | 1 | 1 | 2026-11-08T05:20:06-0300 | hotkey-live-edge-neg.log | - |
| lane-screen-gate | PASS | 0 | 0 | 2026-11-08T10:39:20-0300 | lane-screen-gate.log | - |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:29-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-08T05:20:24-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-11-05T14:48:31-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:31-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-08T05:20:24-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-08T05:20:25-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | PASS | 0 | 0 | 2026-11-08T05:20:26-0300 | youtube-foreign-paint.log | - |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-08T05:20:27-0300 | youtube-foreign-paint-neg.log | - |
| input-path | PASS | 0 | 0 | 2026-11-08T06:12:51-0300 | input-path.log | - |
| red-as-expected-input-path | EXPECTED-RED | 1 | 1 | 2026-11-08T06:12:52-0300 | input-path-neg.log | - |
| exception-hygiene | PASS | 0 | 0 | 2026-11-08T06:12:54-0300 | exception-hygiene.log | - |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-08T06:13:00-0300 | exception-hygiene-neg.log | - |
| seam-coverage | PASS | 0 | 0 | 2026-11-08T06:13:20-0300 | seam-coverage.log | - |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:13-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-05T14:50:14-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:15-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-05T19:44:31-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-05T19:44:32-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-08T05:22:09-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-08T05:22:10-0300 | external-resume-neg.log | - |
| silence-kill | PASS | 0 | 0 | 2026-11-08T05:22:11-0300 | silence-kill.log | - |
| red-as-expected-silence-kill | EXPECTED-RED | 1 | 1 | 2026-11-08T05:22:12-0300 | silence-kill-neg.log | - |
| worker-churn | PASS | 0 | 0 | 2026-11-08T05:22:16-0300 | worker-churn.log | - |
| red-as-expected-worker-churn | EXPECTED-RED | 1 | 1 | 2026-11-08T05:22:19-0300 | worker-churn-neg.log | - |
| rss-trend | PASS | 0 | 0 | 2026-11-08T05:22:19-0300 | rss-trend.log | - |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:32-0300 | rss-trend-neg.log | - |
| death-cause | PASS | 0 | 0 | 2026-11-08T05:22:20-0300 | death-cause.log | - |
| red-as-expected-death-cause | EXPECTED-RED | 1 | 1 | 2026-11-08T05:22:21-0300 | death-cause-neg.log | - |
| caption-seam-dedup | PASS | 0 | 0 | 2026-11-08T05:22:22-0300 | caption-seam-dedup.log | - |
| red-as-expected-caption-seam-dedup | EXPECTED-RED | 1 | 1 | 2026-11-08T05:22:24-0300 | caption-seam-dedup-neg.log | - |
| freeze-census | PASS | 0 | 0 | 2026-11-05T19:44:47-0300 | freeze-census.log | - |
| red-as-expected-caption-budget | EXPECTED-RED | 1 | 1 | 2026-11-08T05:22:24-0300 | caption-budget-neg.log | - |
| dead-app-exit | PASS | 0 | 0 | 2026-11-08T05:22:47-0300 | dead-app-exit.log | - |
| shell-priority | PASS | 0 | 0 | 2026-11-08T05:22:48-0300 | shell-priority.log | - |
| red-as-expected-shell-priority | EXPECTED-RED | 1 | 1 | 2026-11-08T05:22:50-0300 | shell-priority-neg.log | - |
| tray-menu | PASS | 0 | 0 | 2026-11-08T05:22:51-0300 | tray-menu.log | - |
| red-as-expected-tray-menu | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:03-0300 | tray-menu-neg.log | - |
| hotkey-panels-switch | PASS | 0 | 0 | 2026-11-08T05:23:05-0300 | hotkey-panels-switch.log | - |
| red-as-expected-hotkey-panels-switch | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:06-0300 | hotkey-panels-switch-neg.log | - |
| caption-kept-on-hide | PASS | 0 | 0 | 2026-11-08T05:23:07-0300 | caption-kept-on-hide.log | - |
| red-as-expected-caption-kept-on-hide | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:08-0300 | caption-kept-on-hide-neg.log | - |
| caption-switch-race | PASS | 0 | 0 | 2026-11-08T05:23:09-0300 | caption-switch-race.log | - |
| red-as-expected-caption-switch-race | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:10-0300 | caption-switch-race-neg.log | - |
| word-glue | PASS | 0 | 0 | 2026-11-08T05:23:11-0300 | word-glue.log | - |
| red-as-expected-word-glue | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:12-0300 | word-glue-neg.log | - |
| punct-prosody | PASS | 0 | 0 | 2026-11-05T19:45:18-0300 | punct-prosody.log | - |
| red-as-expected-punct-prosody | EXPECTED-RED | 1 | 1 | 2026-11-05T19:45:19-0300 | punct-prosody-neg.log | - |
| punct-model | PASS | 0 | 0 | 2026-11-08T05:23:16-0300 | punct-model.log | - |
| red-as-expected-punct-model | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:18-0300 | punct-model-neg.log | - |
| panel-prefix-row | PASS | 0 | 0 | 2026-11-08T05:23:18-0300 | panel-prefix-row.log | - |
| red-as-expected-panel-prefix-row | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:19-0300 | panel-prefix-row-neg.log | - |
| fusion | PASS | 0 | 0 | 2026-11-05T14:51:09-0300 | fusion.log | - |
| red-as-expected-fusion | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:09-0300 | fusion-neg.log | - |
| agc-peak-ceiling | PASS | 0 | 0 | 2026-11-08T05:23:20-0300 | agc-peak-ceiling.log | - |
| red-as-expected-agc-peak-ceiling | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:21-0300 | agc-peak-ceiling-neg.log | - |
| reveal-park | PASS | 0 | 0 | 2026-11-08T05:23:23-0300 | reveal-park.log | - |
| red-as-expected-reveal-park | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:41-0300 | reveal-park-neg.log | - |
| youtube-verbatim | PASS | 0 | 0 | 2026-11-08T05:23:52-0300 | youtube-verbatim.log | - |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:52-0300 | youtube-verbatim-neg.log | - |
| code-health | PASS | 0 | 0 | 2026-11-08T10:39:37-0300 | code-health.log | always |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-08T10:39:38-0300 | code-health-neg.log | always |
| undefined-names | PASS | 0 | 0 | 2026-11-08T10:39:40-0300 | undefined-names.log | always |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-08T10:39:40-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | PASS | 0 | 0 | 2026-11-08T10:39:42-0300 | battery-heavy-gate.log | - |
| red-as-expected-battery-heavy-gate | EXPECTED-RED | 1 | 1 | 2026-11-08T10:39:50-0300 | battery-heavy-gate-neg.log | - |
| task-resolver-gate | PASS | 0 | 0 | 2026-11-08T10:39:50-0300 | task-resolver-gate.log | - |
| red-as-expected-task-resolver-gate | EXPECTED-RED | 1 | 1 | 2026-11-08T10:39:51-0300 | task-resolver-gate-neg.log | - |
| claims-date | PASS | 0 | 0 | 2026-11-08T10:39:51-0300 | claims-date.log | - |
| red-as-expected-claims-date | EXPECTED-RED | 1 | 1 | 2026-11-08T10:39:52-0300 | claims-date-neg.log | - |
| stall-under-load | PASS | 0 | 0 | 2026-11-08T10:39:54-0300 | stall-under-load.log | always |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-08T10:39:54-0300 | stall-under-load-neg.log | always |
| paint-live-show | PASS | 0 | 0 | 2026-11-08T10:40:18-0300 | paint-live-show.log | always |
| red-as-expected-paint-live-show | EXPECTED-RED | 1 | 1 | 2026-11-08T10:40:29-0300 | paint-live-show-neg.log | always |
| panel-paint-first-measure | NOT RUN | - | 0 | - | panel-paint-first-measure.log | sem registo no stepcache (o passo nao completou) |
| panel-paint-first | PASS | 0 | 0 | 2026-11-08T10:40:30-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-08T10:40:30-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-08T10:40:31-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-08T10:40:31-0300 | receipt-provenance-neg.log | always |
| async-track-fetch | PASS | 0 | 0 | 2026-11-08T05:26:24-0300 | async-track-fetch.log | - |
| red-as-expected-async-track-fetch | EXPECTED-RED | 1 | 1 | 2026-11-08T05:26:33-0300 | async-track-fetch-neg.log | - |
| batch-queue-drain | PASS | 0 | 0 | 2026-11-05T14:52:43-0300 | batch-queue-drain.log | - |
| red-as-expected-batch-queue-drain | EXPECTED-RED | 1 | 1 | 2026-11-05T14:52:53-0300 | batch-queue-drain-neg.log | - |
| hotkey-live-toggle | PASS | 0 | 0 | 2026-11-08T05:26:36-0300 | hotkey-live-toggle.log | - |
| red-as-expected-hotkey-live-toggle | EXPECTED-RED | 1 | 1 | 2026-11-08T05:27:01-0300 | hotkey-live-toggle-neg.log | - |
| hotkey-spam | PASS | 0 | 0 | 2026-11-08T06:34:20-0300 | hotkey-spam.log | - |
| red-as-expected-hotkey-spam | EXPECTED-RED | 1 | 1 | 2026-11-08T06:34:32-0300 | hotkey-spam-neg.log | - |
| loading-placeholder | PASS | 0 | 0 | 2026-11-08T05:27:20-0300 | loading-placeholder.log | - |
| red-as-expected-loading-placeholder | EXPECTED-RED | 1 | 1 | 2026-11-08T05:27:21-0300 | loading-placeholder-neg.log | - |
| youtube-land | PASS | 0 | 0 | 2026-11-08T10:40:32-0300 | youtube-land.log | always |
| red-as-expected-youtube-land | EXPECTED-RED | 1 | 1 | 2026-11-08T06:34:35-0300 | youtube-land-neg.log | - |
| time-to-first-caption | PASS | 0 | 0 | 2026-11-08T10:40:34-0300 | time-to-first-caption.log | always |
| red-as-expected-time-to-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-05T19:46:54-0300 | time-to-first-caption-neg.log | - |
| first-capture-fast | PASS | 0 | 0 | 2026-11-08T10:40:35-0300 | first-capture-fast.log | always |
| red-as-expected-first-capture-fast | EXPECTED-RED | 1 | 1 | 2026-11-08T05:27:33-0300 | first-capture-fast-neg.log | - |
| youtube-land-replay | PASS | 0 | 0 | 2026-11-08T05:27:35-0300 | youtube-land-replay.log | - |
| red-as-expected-youtube-land-replay | EXPECTED-RED | 1 | 1 | 2026-11-08T05:27:38-0300 | youtube-land-replay-neg.log | - |
| yt-loop-uia | PASS | 0 | 0 | 2026-11-08T05:27:39-0300 | yt-loop-uia.log | - |
| red-as-expected-yt-loop-uia | EXPECTED-RED | 1 | 1 | 2026-11-08T05:27:39-0300 | yt-loop-uia-neg.log | - |
| yt-target-stale | PASS | 0 | 0 | 2026-11-08T06:34:40-0300 | yt-target-stale.log | - |
| red-as-expected-yt-target-stale | EXPECTED-RED | 1 | 1 | 2026-11-08T06:34:41-0300 | yt-target-stale-neg.log | - |
| owner-screen | PASS | 0 | 0 | 2026-11-08T05:27:46-0300 | owner-screen.log | - |
| red-as-expected-owner-screen | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:38-0300 | owner-screen-neg.log | - |
| job-object | PASS | 0 | 0 | 2026-11-05T14:53:42-0300 | job-object.log | - |
| red-as-expected-job-object | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:45-0300 | job-object-neg.log | - |
| emit-pipe-dead | PASS | 0 | 0 | 2026-11-08T05:27:47-0300 | emit-pipe-dead.log | - |
| red-as-expected-emit-pipe-dead | EXPECTED-RED | 1 | 1 | 2026-11-08T05:27:47-0300 | emit-pipe-dead-neg.log | - |
| state-page-write | NO-VERDICT | 0 | 0 | 2026-11-08T07:01:11-0300 | state-page-write.log | log alterado depois do registo |
| state-page | STALE | 0 | 0 | 2026-11-08T07:01:21-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-08T07:01:21-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-08T07:02:56-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-08T07:02:56-0300) |
| battery-wiring | STALE | 0 | 0 | 2026-11-08T06:36:26-0300 | battery-wiring.log | deps mudaram depois da medicao (medido 2026-11-08T06:36:26-0300) |
| red-as-expected-battery-wiring | STALE | 1 | 1 | 2026-11-08T06:36:38-0300 | battery-wiring-neg.log | deps mudaram depois da medicao (medido 2026-11-08T06:36:38-0300) |
| battery-record-pairing | STALE | 0 | 0 | 2026-11-08T07:02:57-0300 | battery-record-pairing.log | deps mudaram depois da medicao (medido 2026-11-08T07:02:57-0300) |
| red-as-expected-battery-record-pairing | STALE | 1 | 1 | 2026-11-08T07:02:57-0300 | battery-record-pairing-neg.log | deps mudaram depois da medicao (medido 2026-11-08T07:02:57-0300) |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-08T07:02:58-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-08T07:03:15-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | PASS | 0 | 0 | 2026-11-08T07:03:22-0300 | youtube-1to1.log | always |
| red-as-expected-youtube-1to1 | EXPECTED-RED | 1 | 1 | 2026-11-08T07:03:33-0300 | youtube-1to1-neg.log | always |
| youtube-cdp-source | PASS | 0 | 0 | 2026-11-08T07:03:40-0300 | youtube-cdp-source.log | always |
| red-as-expected-youtube-cdp-source | EXPECTED-RED | 1 | 1 | 2026-11-08T07:04:49-0300 | youtube-cdp-source-neg.log | always |
| caption-producer | PASS | 0 | 0 | 2026-11-08T07:04:49-0300 | caption-producer.log | always |
| red-as-expected-caption-producer | EXPECTED-RED | 1 | 1 | 2026-11-08T07:04:50-0300 | caption-producer-neg.log | always |
| caption-style | PASS | 0 | 0 | 2026-11-08T07:04:53-0300 | caption-style.log | always |
| red-as-expected-caption-style | EXPECTED-RED | 1 | 1 | 2026-11-08T07:04:55-0300 | caption-style-neg.log | always |
| panel-commit-stable | PASS | 0 | 0 | 2026-11-08T07:07:31-0300 | panel-commit-stable.log | always |
| red-as-expected-panel-commit-stable | EXPECTED-RED | 1 | 1 | 2026-11-08T07:09:59-0300 | panel-commit-stable-neg.log | always |
| paint-row-seam | PASS | 0 | 0 | 2026-11-08T07:09:59-0300 | paint-row-seam.log | always |
| red-as-expected-paint-row-seam | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:00-0300 | paint-row-seam-neg.log | always |
| load-bg-window | PASS | 0 | 0 | 2026-11-08T07:10:00-0300 | load-bg-window.log | always |
| red-as-expected-load-bg-window | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:02-0300 | load-bg-window-neg.log | always |
| page-scan-browser | PASS | 0 | 0 | 2026-11-08T07:10:03-0300 | page-scan-browser.log | always |
| red-as-expected-page-scan-browser | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:03-0300 | page-scan-browser-neg.log | always |
| paused-pace | PASS | 0 | 0 | 2026-11-08T07:10:04-0300 | paused-pace.log | always |
| red-as-expected-paused-pace | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:05-0300 | paused-pace-neg.log | always |
| stutter-caption | PASS | 0 | 0 | 2026-11-08T07:10:09-0300 | stutter-caption.log | always |
| red-as-expected-stutter-caption | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:13-0300 | stutter-caption-neg.log | always |
| parakeet-ultra | NOT RUN | - | 0 | - | parakeet-ultra.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-parakeet-ultra | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:13-0300 | parakeet-ultra-neg.log | always |
| hotkey-observed | PASS | 0 | 0 | 2026-11-08T07:10:19-0300 | hotkey-observed.log | always |
| red-as-expected-hotkey-observed | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:24-0300 | hotkey-observed-neg.log | always |
| youtube-reveal | PASS | 0 | 0 | 2026-11-08T07:10:26-0300 | youtube-reveal.log | always |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:27-0300 | youtube-reveal-neg.log | always |
| youtube-rows | PASS | 0 | 0 | 2026-11-08T07:10:29-0300 | youtube-rows.log | always |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:31-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-08T07:10:32-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:32-0300 | youtube-drift-neg.log | always |
| bend-laws | FAIL | 5 | 0 | 2026-11-08T07:10:38-0300 | bend-laws.log | rc=5 != esperado 0 |
| bend-laws-model | PASS | 0 | 0 | 2026-11-08T07:10:38-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-08T07:10:38-0300 | bend-laws-model-neg.log | always |
| bend-mirror | NOT RUN | - | 0 | - | bend-mirror.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-bend-mirror | NOT RUN | - | 1 | - | bend-mirror-neg.log | sem registo no stepcache (o passo nao completou) |
| bend-ledger-selftest | NOT RUN | - | 0 | - | bend-ledger-selftest.log | sem registo no stepcache (o passo nao completou) |
| panel-hidden-at-startup-oracle | PASS | 0 | 0 | 2026-11-08T05:40:09-0300 | panel-hidden-at-startup.log | - |
| red-as-expected-panel-hidden-at-startup | EXPECTED-RED | 1 | 1 | 2026-11-08T05:40:18-0300 | panel-hidden-at-startup-neg.log | - |
| panel-nav-stall | PASS | 0 | 0 | 2026-11-08T05:40:18-0300 | panel-nav-stall.log | - |
| red-as-expected-panel-nav-stall | EXPECTED-RED | 1 | 1 | 2026-11-08T05:40:21-0300 | panel-nav-stall-neg.log | - |
| worker-start-wiring | PASS | 0 | 0 | 2026-11-08T05:40:27-0300 | wiring-worker-start.log | - |
| red-as-expected-worker-start-wiring | EXPECTED-RED | 1 | 1 | 2026-11-08T05:40:29-0300 | wiring-worker-start-neg.log | - |
| embedded-js-check | PASS | 0 | 0 | 2026-11-08T05:40:31-0300 | embedded-js.log | - |
| lane1-worker-default-arms | PASS | 0 | 0 | 2026-11-08T05:40:32-0300 | lane1-arms.log | - |
| external-subs-stability | PASS | 0 | 0 | 2026-11-05T19:53:37-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | PASS | 0 | 0 | 2026-11-08T05:40:32-0300 | external-caption-chrome-census.log | - |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-11-05T19:53:38-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-05T19:53:39-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-11-05T14:58:01-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-08T05:40:36-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-11-05T14:58:04-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-11-05T14:58:04-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:05-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-11-05T14:58:09-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:12-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-11-05T15:39:14-0300 | gitattributes-verify.log | - |
| agents-md-pins | STALE | 0 | 0 | 2026-11-08T06:42:03-0300 | agents-md-pins.log | deps mudaram depois da medicao (medido 2026-11-08T06:42:03-0300) |
| lang-id-oracle | PASS | 0 | 0 | 2026-11-08T05:40:52-0300 | lang-id-oracle.log | - |
| red-as-expected-lang-id-oracle | EXPECTED-RED | 1 | 1 | 2026-11-08T05:41:39-0300 | lang-id-oracle-neg.log | - |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-05T14:59:14-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:15-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-11-05T14:59:16-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:18-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-08T06:42:05-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-08T06:42:05-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-08T06:42:06-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-08T06:42:06-0300) |
| per-app-source-plumbing | PASS | 0 | 0 | 2026-11-08T05:41:40-0300 | per-app-source-plumbing.log | - |
| red-as-expected-per-app-source-plumbing | EXPECTED-RED | 1 | 1 | 2026-11-08T05:41:41-0300 | per-app-source-plumbing-neg.log | - |
| redux-live-contract | PASS | 0 | 0 | 2026-11-08T05:41:41-0300 | redux-live-contract.log | - |
| red-as-expected-redux-live-contract | EXPECTED-RED | 1 | 1 | 2026-11-08T05:41:42-0300 | redux-live-contract-neg.log | - |
| word-split-oracle | PASS | 0 | 0 | 2026-11-08T05:41:42-0300 | word-split-oracle.log | - |
| red-as-expected-word-split-oracle | EXPECTED-RED | 1 | 1 | 2026-11-08T05:41:43-0300 | word-split-oracle-neg.log | - |
| vad-option-probe | PASS | 0 | 0 | 2026-11-08T05:42:09-0300 | vad-option-probe.log | - |
| red-as-expected-vad-option-probe | EXPECTED-RED | 1 | 1 | 2026-11-08T05:42:09-0300 | vad-option-probe-neg.log | - |
| youtube-track-wiring | PASS | 0 | 0 | 2026-11-08T05:42:16-0300 | youtube-track-wiring.log | - |
| tap-open-timeout | PASS | 0 | 0 | 2026-11-08T05:42:54-0300 | tap-open-timeout.log | - |
| ui-stall-oracle | PASS | 0 | 0 | 2026-11-08T05:43:01-0300 | ui-stall-oracle.log | - |
| mute-audio | NOT RUN | - | 0 | - | mute-audio.log | sem registo no stepcache (o passo nao completou) |
| device-silence | NOT RUN | - | 0 | - | device-silence.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-device-silence | NOT RUN | - | 1 | - | device-silence-neg.log | sem registo no stepcache (o passo nao completou) |
| console-window-audit | FAIL | 1 | 0 | 2026-11-08T07:11:00-0300 | console-window-audit.log | rc=1 != esperado 0 |
| red-as-expected-console-window-audit | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:01-0300 | console-window-audit-neg.log | always |
| red-as-expected-console-window-watch | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:01-0300 | console-window-watch-neg.log | always |
| capture-exclude | PASS | 0 | 0 | 2026-11-08T07:11:02-0300 | capture-exclude.log | always |
| red-as-expected-capture-exclude | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:02-0300 | capture-exclude-neg.log | always |
| history-merge | PASS | 0 | 0 | 2026-11-08T07:11:03-0300 | history-merge.log | always |
| red-as-expected-history-merge | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:04-0300 | history-merge-neg.log | always |
| reveal-clock | PASS | 0 | 0 | 2026-11-08T07:11:04-0300 | reveal-clock.log | always |
| red-as-expected-reveal-clock | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:05-0300 | reveal-clock-neg.log | always |
| tap-first-block | PASS | 0 | 0 | 2026-11-08T07:11:05-0300 | tap-first-block.log | always |
| red-as-expected-tap-first-block | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:06-0300 | tap-first-block-neg.log | always |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-08T07:11:07-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:08-0300 | owner-audio-gate-neg.log | always |
| worker-providers | PASS | 0 | 0 | 2026-11-08T07:11:09-0300 | worker-providers.log | always |
| red-as-expected-worker-providers | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:09-0300 | worker-providers-neg.log | always |
| review-f1f3 | PASS | 0 | 0 | 2026-11-08T05:43:22-0300 | review-f1f3.log | - |
| review-tapstop | PASS | 0 | 0 | 2026-11-05T15:00:43-0300 | review-tapstop.log | - |
| strip-surface-oracle | PASS | 0 | 0 | 2026-11-08T06:21:33-0300 | strip-surface-oracle.log | - |
| strip-width | PASS | 0 | 0 | 2026-11-08T05:43:45-0300 | strip-width.log | - |
| red-as-expected-strip-width | EXPECTED-RED | 1 | 1 | 2026-11-08T05:43:45-0300 | strip-width-neg.log | - |
| strip-stats-log-budget | NOT RUN | - | 0 | - | strip-stats-log.log | sem registo no stepcache (o passo nao completou) |
| strip-hot-reload | PASS | 0 | 0 | 2026-11-08T05:44:00-0300 | strip-reload.log | - |
| strip-surface-runtime | NOT RUN | - | 0 | - | strip-surface.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-strip-surface | NOT RUN | - | 1 | - | strip-surface-neg.log | sem registo no stepcache (o passo nao completou) |
| strip-geometry-restore | NOT RUN | - | 0 | - | strip-restore.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-wave | NOT RUN | - | 0 | - | strip-stats.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-05T15:01:18-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-08T07:11:11-0300 | hotkey-registration.log | always |
| hotkey-delivery | PASS | 0 | 0 | 2026-11-08T07:11:12-0300 | hotkey-delivery.log | always |
| open-close-stall | PASS | 0 | 0 | 2026-11-08T05:44:08-0300 | open-close-stall.log | - |
| red-as-expected-open-close-stall | EXPECTED-RED | 1 | 1 | 2026-11-08T05:44:30-0300 | open-close-stall-neg.log | - |
| autostart-status | PASS | 0 | 0 | 2026-11-08T07:11:13-0300 | autostart-status.log | always |
| control-verdict-gate-unguard | PASS | 0 | 0 | 2026-11-08T05:44:31-0300 | control-verdict-gate-unguard.log | - |
| control-history-producer-stamp-nvidia | PASS | 0 | 0 | 2026-11-08T05:44:32-0300 | control-history-producer-stamp-nvidia.log | - |
| control-redux-flag-neg-arm | PASS | 0 | 0 | 2026-11-08T05:44:33-0300 | control-redux-flag-neg-arm.log | - |
| control-panel-exit3-neg-arm | NOT RUN | - | 0 | - | control-panel-exit3-neg-arm.log | sem registo no stepcache (o passo nao completou) |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-11-05T15:01:43-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | PASS | 0 | 0 | 2026-11-08T05:44:35-0300 | control-panel2-repeat-revert.log | - |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-11-05T15:01:45-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | EXPECTED-RED | 1 | 1 | 2026-11-05T20:30:56-0300 | control-historico-gate-off.log | - |
| search-oracle | PASS | 0 | 0 | 2026-11-08T05:44:36-0300 | search-oracle.log | - |
| red-as-expected-search-oracle | EXPECTED-RED | 1 | 1 | 2026-11-08T05:44:38-0300 | search-oracle-neg.log | - |
| panel-search-keyboard | PASS | 0 | 0 | 2026-11-08T05:44:40-0300 | panel-search-keyboard.log | - |
| red-as-expected-panel-search-keyboard | EXPECTED-RED | 1 | 1 | 2026-11-08T05:44:42-0300 | panel-search-keyboard-neg.log | - |
| fresh-processor-probe | PASS | 0 | 0 | 2026-11-08T05:44:48-0300 | fresh-processor.log | - |
| stepcache-oracle | PASS | 0 | 0 | 2026-11-05T22:22:40-0300 | stepcache-oracle.log | - |
| battery-plan | STALE | 0 | 0 | 2026-11-08T07:11:22-0300 | battery-plan.log | deps mudaram depois da medicao (medido 2026-11-08T07:11:22-0300) |
| red-as-expected-battery-plan | EXPECTED-RED | 1 | 1 | 2026-11-08T07:11:43-0300 | battery-plan-neg.log | always |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-08T07:11:44-0300 | _skip-guard.log | always |
| altc-first-caption | NOT RUN | - | 0 | - | altc-first-caption.log | sem registo no stepcache (o passo nao completou) |
| altc-gesture | PASS | 0 | 0 | 2026-11-08T07:11:51-0300 | altc-gesture.log | always |
| headphone-cut | PASS | 0 | 0 | 2026-11-08T07:12:52-0300 | headphone-cut.log | always |
| incomplete-word | PASS | 0 | 0 | 2026-11-08T07:12:52-0300 | incomplete-word.log | always |
| ladder-signal | PASS | 0 | 0 | 2026-11-08T07:12:53-0300 | ladder-signal.log | always |
| launch-as-token | PASS | 0 | 0 | 2026-11-08T07:12:56-0300 | launch-as-token.log | always |
| live-code-freshness | PASS | 0 | 0 | 2026-11-08T07:12:57-0300 | live-code-freshness.log | always |
| live-code-freshness-control | PASS | 0 | 0 | 2026-11-08T07:12:57-0300 | live-code-freshness-control.log | always |
| red-as-expected-live-code-freshness | EXPECTED-RED | 1 | 1 | 2026-11-08T07:12:58-0300 | live-code-freshness-neg.log | always |
| load-shedding | PASS | 0 | 0 | 2026-11-08T07:13:03-0300 | load-shedding.log | always |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-08T07:13:03-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | EXPECTED-RED | 1 | 1 | 2026-11-08T07:13:25-0300 | altc-gesture-neg.log | always |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-08T07:13:26-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-08T07:13:26-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | EXPECTED-RED | 1 | 1 | 2026-11-08T07:13:27-0300 | ladder-signal-neg.log | always |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-08T07:13:28-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-08T07:13:28-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-08T07:13:35-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | EXPECTED-RED | 1 | 1 | 2026-11-08T07:14:52-0300 | load-shedding-neg.log | always |
| red-as-expected-shell-relaunch | NOT RUN | - | 1 | - | shell-relaunch-neg.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-word-clock | EXPECTED-RED | 1 | 1 | 2026-11-08T07:14:53-0300 | word-clock-neg.log | always |
| red-as-expected-youtube-monotonic | EXPECTED-RED | 1 | 1 | 2026-11-08T07:14:57-0300 | youtube-monotonic-neg.log | always |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-08T07:14:58-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | EXPECTED-RED | 1 | 1 | 2026-11-08T07:15:39-0300 | youtube-switch-neg.log | always |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-08T07:15:40-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NOT RUN | - | 0 | - | shell-relaunch.log | sem registo no stepcache (o passo nao completou) |
| census-instrument | PASS | 0 | 0 | 2026-11-08T05:47:29-0300 | census-instrument.log | - |
| red-as-expected-census-instrument | EXPECTED-RED | 1 | 1 | 2026-11-08T05:47:30-0300 | census-instrument-neg.log | - |
| relaunch-ready | PASS | 0 | 0 | 2026-11-08T05:47:38-0300 | relaunch-ready.log | - |
| red-as-expected-relaunch-ready | EXPECTED-RED | 1 | 1 | 2026-11-08T05:47:52-0300 | relaunch-ready-neg.log | - |
| word-clock | PASS | 0 | 0 | 2026-11-08T07:15:41-0300 | word-clock.log | always |
| youtube-monotonic | PASS | 0 | 0 | 2026-11-08T07:15:42-0300 | youtube-monotonic.log | always |
| youtube-rate | PASS | 0 | 0 | 2026-11-08T07:15:43-0300 | youtube-rate.log | always |
| red-as-expected-youtube-rate | EXPECTED-RED | 1 | 1 | 2026-11-08T07:15:44-0300 | youtube-rate-neg.log | always |
| click-through-applied | PASS | 0 | 0 | 2026-11-08T07:15:44-0300 | click-through-applied.log | always |
| red-as-expected-click-through-applied | EXPECTED-RED | 1 | 1 | 2026-11-08T07:15:45-0300 | click-through-applied-neg.log | always |
| topmost-keepalive | PASS | 0 | 0 | 2026-11-08T07:15:46-0300 | topmost-keepalive.log | always |
| red-as-expected-topmost-keepalive | EXPECTED-RED | 1 | 1 | 2026-11-08T07:15:46-0300 | topmost-keepalive-neg.log | always |
| webview2-args-scope | PASS | 0 | 0 | 2026-11-08T07:15:47-0300 | webview2-args-scope.log | always |
| red-as-expected-webview2-args-scope | EXPECTED-RED | 1 | 1 | 2026-11-08T07:15:48-0300 | webview2-args-scope-neg.log | always |
| power-recovery | PASS | 0 | 0 | 2026-11-08T07:15:48-0300 | power-recovery.log | always |
| red-as-expected-power-recovery | EXPECTED-RED | 1 | 1 | 2026-11-08T07:15:53-0300 | power-recovery-neg.log | always |
| power-recovery-live | NOT RUN | - | 0 | - | power-recovery-live.log | sem registo no stepcache (o passo nao completou) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-08T07:15:54-0300 | youtube-sotto-drift.log | always |
| youtube-switch | PASS | 0 | 0 | 2026-11-08T07:15:59-0300 | youtube-switch.log | always |
| yt-no-dub | PASS | 0 | 0 | 2026-11-08T07:16:00-0300 | yt-no-dub.log | always |
| stale-display | PASS | 0 | 0 | 2026-11-08T07:16:00-0300 | stale-display.log | always |
| red-as-expected-stale-display | EXPECTED-RED | 1 | 1 | 2026-11-08T07:16:14-0300 | stale-display-neg.log | always |
| battery-class | STALE | 0 | 0 | 2026-11-08T07:16:14-0300 | battery-class.log | deps mudaram depois da medicao (medido 2026-11-08T07:16:14-0300) |
| red-as-expected-battery-class | STALE | 1 | 1 | 2026-11-08T07:16:15-0300 | battery-class-neg.log | deps mudaram depois da medicao (medido 2026-11-08T07:16:15-0300) |
| live-queue | PASS | 0 | 0 | 2026-11-08T07:16:16-0300 | live-queue.log | always |
| red-as-expected-live-queue | EXPECTED-RED | 1 | 1 | 2026-11-08T07:16:19-0300 | live-queue-neg.log | always |
| flat-endpoint | PASS | 0 | 0 | 2026-11-08T07:16:21-0300 | flat-endpoint.log | always |
| tap-silent-desktop | PASS | 0 | 0 | 2026-11-08T07:16:21-0300 | tap-silent-desktop.log | always |
| red-as-expected-tap-silent-desktop | EXPECTED-RED | 1 | 1 | 2026-11-08T07:16:24-0300 | tap-silent-desktop-neg.log | always |
| warm-engine | PASS | 0 | 0 | 2026-11-08T07:16:35-0300 | warm-engine.log | always |
| red-as-expected-warm-engine | EXPECTED-RED | 1 | 1 | 2026-11-08T07:17:38-0300 | warm-engine-neg.log | always |
| gaming-hotkey | PASS | 0 | 0 | 2026-11-08T07:18:00-0300 | gaming-hotkey.log | always |
| red-as-expected-gaming-hotkey | EXPECTED-RED | 1 | 1 | 2026-11-08T07:19:07-0300 | gaming-hotkey-neg.log | always |
| ctrlspace-swallow | PASS | 0 | 0 | 2026-11-08T07:19:12-0300 | ctrlspace-swallow.log | always |
| red-as-expected-ctrlspace-swallow | EXPECTED-RED | 1 | 1 | 2026-11-08T07:19:29-0300 | ctrlspace-swallow-neg.log | always |
| ctrlspace-swallow-os | PASS | 0 | 0 | 2026-11-08T07:19:29-0300 | ctrlspace-swallow-os.log | always |
| battery-budget | STALE | 0 | 0 | 2026-11-08T07:19:30-0300 | battery-budget.log | deps mudaram depois da medicao (medido 2026-11-08T07:19:30-0300) |
| red-as-expected-battery-budget | STALE | 1 | 1 | 2026-11-08T07:19:30-0300 | battery-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-08T07:19:30-0300) |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
