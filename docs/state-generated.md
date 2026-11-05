# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=314 · PASS=101 · EXPECTED-RED=82 · FAIL=9 · STALE=103 · NO-VERDICT=15 · NOT RUN=4

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-05T07:52:17-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-10-30T04:23:01-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | STALE | 0 | 0 | 2026-11-05T06:31:58-0300 | pycompile-worker.log | deps mudaram depois da medicao (medido 2026-11-05T06:31:58-0300) |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-11-04T13:13:12-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-11-05T06:31:59-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-11-05T06:31:59-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-11-05T06:31:59-0300 | oracle-historico-vs-redux.log | - |
| redux-transcript-path | PASS | 0 | 0 | 2026-11-05T07:52:20-0300 | redux-transcript-path.log | - |
| caption-cumulative | PASS | 0 | 0 | 2026-11-05T06:32:01-0300 | oracle-caption-cumulative.log | - |
| red-as-expected-caption-cumulative | EXPECTED-RED | 1 | 1 | 2026-11-05T06:32:01-0300 | caption-cumulative-neg.log | - |
| caption-lag-budget | STALE | 0 | 0 | 2026-11-05T07:52:22-0300 | caption-lag-budget.log | deps mudaram depois da medicao (medido 2026-11-05T07:52:22-0300) |
| red-as-expected-caption-lag-budget | STALE | 1 | 1 | 2026-11-05T07:52:28-0300 | caption-lag-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-05T07:52:28-0300) |
| lag-note-cost | PASS | 0 | 0 | 2026-11-05T07:56:59-0300 | lag-note-cost.log | always |
| red-as-expected-lag-note-cost | EXPECTED-RED | 1 | 1 | 2026-11-05T07:57:12-0300 | lag-note-cost-neg.log | always |
| youtube-hidden-clock | PASS | 0 | 0 | 2026-11-05T07:57:23-0300 | youtube-hidden-clock.log | always |
| red-as-expected-youtube-hidden-clock | EXPECTED-RED | 1 | 1 | 2026-11-05T07:57:29-0300 | youtube-hidden-clock-neg.log | always |
| caption-overlay-screen | PASS | 0 | 0 | 2026-11-05T07:57:35-0300 | caption-overlay-screen.log | always |
| red-as-expected-caption-overlay-screen | EXPECTED-RED | 1 | 1 | 2026-11-05T07:57:46-0300 | caption-overlay-screen-neg.log | always |
| youtube-cdp-boot | PASS | 0 | 0 | 2026-11-05T07:57:57-0300 | youtube-cdp-boot.log | always |
| red-as-expected-youtube-cdp-boot | EXPECTED-RED | 1 | 1 | 2026-11-05T07:58:14-0300 | youtube-cdp-boot-neg.log | always |
| youtube-first-at-boot | PASS | 0 | 0 | 2026-11-05T07:58:38-0300 | youtube-first-at-boot.log | always |
| red-as-expected-youtube-first-at-boot | EXPECTED-RED | 1 | 1 | 2026-11-05T07:59:31-0300 | youtube-first-at-boot-neg.log | always |
| red-as-expected-redux-transcript-path | EXPECTED-RED | 1 | 1 | 2026-11-05T07:54:04-0300 | redux-transcript-path-neg.log | - |
| control-verdict-gate-drop-redux-live | STALE | 0 | 0 | 2026-11-05T06:33:12-0300 | control-verdict-gate-drop-redux-live.log | deps mudaram depois da medicao (medido 2026-11-05T06:33:12-0300) |
| history-producer-gate | STALE | 0 | 0 | 2026-11-05T06:33:13-0300 | gate-history-producer.log | deps mudaram depois da medicao (medido 2026-11-05T06:33:13-0300) |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-11-05T06:33:13-0300 | gate-panel-state-guard.log | - |
| verdict-gate | STALE | 0 | 0 | 2026-11-05T06:33:14-0300 | gate-verdict.log | deps mudaram depois da medicao (medido 2026-11-05T06:33:14-0300) |
| worker-park | STALE | 0 | 0 | 2026-11-05T08:01:22-0300 | worker-park.log | deps mudaram depois da medicao (medido 2026-11-05T08:01:22-0300) |
| red-as-expected-worker-park | STALE | 1 | 1 | 2026-11-05T08:01:25-0300 | worker-park-neg.log | deps mudaram depois da medicao (medido 2026-11-05T08:01:25-0300) |
| lane2-reset-probe | FAIL | 1 | 0 | 2026-11-05T08:01:32-0300 | lane2-reset.log | rc=1 != esperado 0 |
| lane3-verdict-probe | STALE | 0 | 0 | 2026-11-05T06:33:55-0300 | lane3-verdict.log | deps mudaram depois da medicao (medido 2026-11-05T06:33:55-0300) |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-11-04T13:14:32-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-11-05T06:33:56-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-11-05T06:33:57-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-10-20T02:22:35-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-11-05T06:34:01-0300 | panel2-dom-probe.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-11-05T06:34:10-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-11-02T19:42:24-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-11-02T19:42:24-0300 | border-radius-gate-neg.log | - |
| hidden-launch | PASS | 0 | 0 | 2026-11-04T02:55:34-0300 | hidden-launch.log | - |
| red-as-expected-hidden-launch | EXPECTED-RED | 1 | 1 | 2026-11-04T02:55:34-0300 | hidden-launch-neg.log | - |
| emit-prewebview | PASS | 0 | 0 | 2026-11-05T07:55:51-0300 | emit-prewebview.log | - |
| red-as-expected-emit-prewebview | EXPECTED-RED | 1 | 1 | 2026-11-05T07:55:52-0300 | emit-prewebview-neg.log | - |
| hotkey-live-edge | PASS | 0 | 0 | 2026-11-05T08:01:53-0300 | hotkey-live-edge.log | - |
| red-as-expected-hotkey-live-edge | EXPECTED-RED | 1 | 1 | 2026-11-05T08:02:00-0300 | hotkey-live-edge-neg.log | - |
| lane-screen-gate | PASS | 0 | 0 | 2026-11-05T06:34:28-0300 | lane-screen-gate.log | - |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-04T13:14:51-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-05T08:02:01-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-11-04T09:08:13-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-10-30T10:05:12-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-05T08:02:02-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-05T08:02:05-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | PASS | 0 | 0 | 2026-11-05T08:02:08-0300 | youtube-foreign-paint.log | - |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-05T08:02:09-0300 | youtube-foreign-paint-neg.log | - |
| input-path | PASS | 0 | 0 | 2026-11-05T08:02:34-0300 | input-path.log | - |
| red-as-expected-input-path | EXPECTED-RED | 1 | 1 | 2026-11-05T08:02:36-0300 | input-path-neg.log | - |
| exception-hygiene | STALE | 0 | 0 | 2026-11-05T08:02:38-0300 | exception-hygiene.log | deps mudaram depois da medicao (medido 2026-11-05T08:02:38-0300) |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-04T13:15:14-0300 | exception-hygiene-neg.log | - |
| seam-coverage | PASS | 0 | 0 | 2026-11-05T08:02:48-0300 | seam-coverage.log | - |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:52-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-04T02:21:41-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-04T02:21:41-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-04T02:21:42-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:56-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-05T08:02:59-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-05T08:03:08-0300 | external-resume-neg.log | - |
| silence-kill | PASS | 0 | 0 | 2026-11-05T08:03:21-0300 | silence-kill.log | - |
| red-as-expected-silence-kill | EXPECTED-RED | 1 | 1 | 2026-11-05T08:04:11-0300 | silence-kill-neg.log | - |
| worker-churn | STALE | 0 | 0 | 2026-11-05T08:04:20-0300 | worker-churn.log | deps mudaram depois da medicao (medido 2026-11-05T08:04:20-0300) |
| red-as-expected-worker-churn | STALE | 1 | 1 | 2026-11-05T08:04:36-0300 | worker-churn-neg.log | deps mudaram depois da medicao (medido 2026-11-05T08:04:36-0300) |
| rss-trend | PASS | 0 | 0 | 2026-11-05T08:04:36-0300 | rss-trend.log | - |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-04T23:58:33-0300 | rss-trend-neg.log | - |
| death-cause | PASS | 0 | 0 | 2026-11-05T08:04:38-0300 | death-cause.log | - |
| red-as-expected-death-cause | EXPECTED-RED | 1 | 1 | 2026-11-05T08:04:40-0300 | death-cause-neg.log | - |
| caption-seam-dedup | STALE | 0 | 0 | 2026-11-05T06:35:06-0300 | caption-seam-dedup.log | deps mudaram depois da medicao (medido 2026-11-05T06:35:06-0300) |
| red-as-expected-caption-seam-dedup | STALE | 1 | 1 | 2026-11-05T06:35:08-0300 | caption-seam-dedup-neg.log | deps mudaram depois da medicao (medido 2026-11-05T06:35:08-0300) |
| freeze-census | PASS | 0 | 0 | 2026-11-05T06:35:12-0300 | freeze-census.log | - |
| red-as-expected-caption-budget | STALE | 1 | 1 | 2026-11-05T08:04:42-0300 | caption-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-05T08:04:42-0300) |
| dead-app-exit | FAIL | 1 | 0 | 2026-11-05T08:05:22-0300 | dead-app-exit.log | rc=1 != esperado 0 |
| shell-priority | PASS | 0 | 0 | 2026-11-05T08:05:26-0300 | shell-priority.log | - |
| red-as-expected-shell-priority | EXPECTED-RED | 1 | 1 | 2026-11-05T08:05:28-0300 | shell-priority-neg.log | - |
| tray-menu | PASS | 0 | 0 | 2026-11-05T08:05:29-0300 | tray-menu.log | - |
| red-as-expected-tray-menu | EXPECTED-RED | 1 | 1 | 2026-11-05T08:05:30-0300 | tray-menu-neg.log | - |
| caption-kept-on-hide | PASS | 0 | 0 | 2026-11-05T08:05:31-0300 | caption-kept-on-hide.log | - |
| red-as-expected-caption-kept-on-hide | EXPECTED-RED | 1 | 1 | 2026-11-05T08:05:32-0300 | caption-kept-on-hide-neg.log | - |
| panel-prefix-row | PASS | 0 | 0 | 2026-11-05T06:35:38-0300 | panel-prefix-row.log | - |
| red-as-expected-panel-prefix-row | EXPECTED-RED | 1 | 1 | 2026-11-05T06:35:39-0300 | panel-prefix-row-neg.log | - |
| fusion | PASS | 0 | 0 | 2026-11-04T23:59:03-0300 | fusion.log | - |
| red-as-expected-fusion | EXPECTED-RED | 1 | 1 | 2026-11-04T23:59:04-0300 | fusion-neg.log | - |
| agc-peak-ceiling | STALE | 0 | 0 | 2026-11-05T06:35:40-0300 | agc-peak-ceiling.log | deps mudaram depois da medicao (medido 2026-11-05T06:35:40-0300) |
| red-as-expected-agc-peak-ceiling | STALE | 1 | 1 | 2026-11-05T06:35:42-0300 | agc-peak-ceiling-neg.log | deps mudaram depois da medicao (medido 2026-11-05T06:35:42-0300) |
| reveal-park | PASS | 0 | 0 | 2026-11-05T08:05:36-0300 | reveal-park.log | - |
| red-as-expected-reveal-park | EXPECTED-RED | 1 | 1 | 2026-11-05T08:05:43-0300 | reveal-park-neg.log | - |
| youtube-verbatim | PASS | 0 | 0 | 2026-11-05T08:05:45-0300 | youtube-verbatim.log | - |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-04T02:22:03-0300 | youtube-verbatim-neg.log | - |
| code-health | FAIL | 2 | 0 | 2026-11-05T08:05:55-0300 | code-health.log | rc=2 != esperado 0 |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-05T08:05:56-0300 | code-health-neg.log | always |
| undefined-names | STALE | 0 | 0 | 2026-11-05T08:06:02-0300 | undefined-names.log | deps mudaram depois da medicao (medido 2026-11-05T08:06:02-0300) |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-05T08:06:03-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | PASS | 0 | 0 | 2026-11-05T06:44:15-0300 | battery-heavy-gate.log | - |
| red-as-expected-battery-heavy-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T06:36:10-0300 | battery-heavy-gate-neg.log | - |
| task-resolver-gate | PASS | 0 | 0 | 2026-11-05T06:36:11-0300 | task-resolver-gate.log | - |
| red-as-expected-task-resolver-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T06:36:12-0300 | task-resolver-gate-neg.log | - |
| claims-date | PASS | 0 | 0 | 2026-11-05T06:36:12-0300 | claims-date.log | - |
| red-as-expected-claims-date | EXPECTED-RED | 1 | 1 | 2026-11-05T06:36:13-0300 | claims-date-neg.log | - |
| stall-under-load | PASS | 0 | 0 | 2026-11-05T08:06:53-0300 | stall-under-load.log | always |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-05T08:07:02-0300 | stall-under-load-neg.log | always |
| paint-live-show | PASS | 0 | 0 | 2026-11-05T08:08:20-0300 | paint-live-show.log | always |
| red-as-expected-paint-live-show | FAIL | 2 | 1 | 2026-11-05T08:08:52-0300 | paint-live-show-neg.log | rc=2 != esperado 1 |
| panel-paint-first-measure | NO-VERDICT | 0 | 0 | 2026-11-01T14:45:10-0300 | panel-paint-first-measure.log | log alterado depois do registo |
| panel-paint-first | PASS | 0 | 0 | 2026-11-05T08:08:54-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-05T08:08:54-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-05T08:08:55-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-05T08:08:55-0300 | receipt-provenance-neg.log | always |
| async-track-fetch | PASS | 0 | 0 | 2026-11-05T08:09:04-0300 | async-track-fetch.log | - |
| red-as-expected-async-track-fetch | EXPECTED-RED | 1 | 1 | 2026-11-05T08:09:14-0300 | async-track-fetch-neg.log | - |
| batch-queue-drain | PASS | 0 | 0 | 2026-11-04T08:42:38-0300 | batch-queue-drain.log | - |
| red-as-expected-batch-queue-drain | EXPECTED-RED | 1 | 1 | 2026-11-04T08:42:48-0300 | batch-queue-drain-neg.log | - |
| hotkey-live-toggle | PASS | 0 | 0 | 2026-11-05T08:09:23-0300 | hotkey-live-toggle.log | - |
| red-as-expected-hotkey-live-toggle | EXPECTED-RED | 1 | 1 | 2026-11-05T08:09:32-0300 | hotkey-live-toggle-neg.log | - |
| loading-placeholder | PASS | 0 | 0 | 2026-11-05T08:09:33-0300 | loading-placeholder.log | - |
| red-as-expected-loading-placeholder | EXPECTED-RED | 1 | 1 | 2026-11-05T08:09:33-0300 | loading-placeholder-neg.log | - |
| youtube-land | PASS | 0 | 0 | 2026-11-05T08:09:34-0300 | youtube-land.log | always |
| red-as-expected-youtube-land | EXPECTED-RED | 1 | 1 | 2026-11-04T10:57:19-0300 | youtube-land-neg.log | - |
| time-to-first-caption | PASS | 0 | 0 | 2026-11-05T08:09:35-0300 | time-to-first-caption.log | always |
| red-as-expected-time-to-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-04T12:12:56-0300 | time-to-first-caption-neg.log | - |
| first-capture-fast | STALE | 0 | 0 | 2026-11-05T08:09:39-0300 | first-capture-fast.log | deps mudaram depois da medicao (medido 2026-11-05T08:09:39-0300) |
| red-as-expected-first-capture-fast | STALE | 1 | 1 | 2026-11-05T08:09:44-0300 | first-capture-fast-neg.log | deps mudaram depois da medicao (medido 2026-11-05T08:09:44-0300) |
| youtube-land-replay | PASS | 0 | 0 | 2026-11-05T08:09:47-0300 | youtube-land-replay.log | - |
| red-as-expected-youtube-land-replay | EXPECTED-RED | 1 | 1 | 2026-11-05T08:09:51-0300 | youtube-land-replay-neg.log | - |
| yt-loop-uia | PASS | 0 | 0 | 2026-11-05T08:09:51-0300 | yt-loop-uia.log | - |
| red-as-expected-yt-loop-uia | EXPECTED-RED | 1 | 1 | 2026-11-05T08:09:52-0300 | yt-loop-uia-neg.log | - |
| yt-target-stale | PASS | 0 | 0 | 2026-11-05T08:09:53-0300 | yt-target-stale.log | - |
| red-as-expected-yt-target-stale | EXPECTED-RED | 1 | 1 | 2026-11-05T08:09:54-0300 | yt-target-stale-neg.log | - |
| owner-screen | PASS | 0 | 0 | 2026-11-05T08:09:58-0300 | owner-screen.log | - |
| red-as-expected-owner-screen | EXPECTED-RED | 1 | 1 | 2026-11-04T02:23:35-0300 | owner-screen-neg.log | - |
| job-object | PASS | 0 | 0 | 2026-11-04T09:08:46-0300 | job-object.log | - |
| red-as-expected-job-object | EXPECTED-RED | 1 | 1 | 2026-11-04T09:08:50-0300 | job-object-neg.log | - |
| emit-pipe-dead | STALE | 0 | 0 | 2026-11-05T06:38:09-0300 | emit-pipe-dead.log | deps mudaram depois da medicao (medido 2026-11-05T06:38:09-0300) |
| red-as-expected-emit-pipe-dead | STALE | 1 | 1 | 2026-11-05T06:38:10-0300 | emit-pipe-dead-neg.log | deps mudaram depois da medicao (medido 2026-11-05T06:38:10-0300) |
| state-page-write | STALE | 0 | 0 | 2026-11-05T08:10:03-0300 | state-page-write.log | deps mudaram depois da medicao (medido 2026-11-05T08:10:03-0300) |
| state-page | STALE | 0 | 0 | 2026-11-05T08:10:16-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-05T08:10:16-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-05T08:12:25-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-05T08:12:25-0300) |
| battery-wiring | PASS | 0 | 0 | 2026-11-05T06:39:27-0300 | battery-wiring.log | - |
| red-as-expected-battery-wiring | EXPECTED-RED | 1 | 1 | 2026-11-05T06:39:30-0300 | battery-wiring-neg.log | - |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-05T08:12:43-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-05T08:12:46-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | PASS | 0 | 0 | 2026-11-05T08:12:49-0300 | youtube-1to1.log | always |
| red-as-expected-youtube-1to1 | EXPECTED-RED | 1 | 1 | 2026-11-05T08:12:59-0300 | youtube-1to1-neg.log | always |
| youtube-cdp-source | PASS | 0 | 0 | 2026-11-05T08:13:09-0300 | youtube-cdp-source.log | always |
| red-as-expected-youtube-cdp-source | EXPECTED-RED | 1 | 1 | 2026-11-05T08:13:29-0300 | youtube-cdp-source-neg.log | always |
| caption-producer | PASS | 0 | 0 | 2026-11-05T08:13:31-0300 | caption-producer.log | always |
| red-as-expected-caption-producer | EXPECTED-RED | 1 | 1 | 2026-11-05T08:13:32-0300 | caption-producer-neg.log | always |
| caption-style | PASS | 0 | 0 | 2026-11-05T08:13:40-0300 | caption-style.log | always |
| red-as-expected-caption-style | EXPECTED-RED | 1 | 1 | 2026-11-05T08:13:47-0300 | caption-style-neg.log | always |
| panel-commit-stable | PASS | 0 | 0 | 2026-11-05T08:14:18-0300 | panel-commit-stable.log | always |
| red-as-expected-panel-commit-stable | EXPECTED-RED | 1 | 1 | 2026-11-05T08:14:43-0300 | panel-commit-stable-neg.log | always |
| paint-row-seam | PASS | 0 | 0 | 2026-11-05T08:14:54-0300 | paint-row-seam.log | always |
| red-as-expected-paint-row-seam | EXPECTED-RED | 1 | 1 | 2026-11-05T08:15:07-0300 | paint-row-seam-neg.log | always |
| load-bg-window | STALE | 0 | 0 | 2026-11-05T08:15:24-0300 | load-bg-window.log | deps mudaram depois da medicao (medido 2026-11-05T08:15:24-0300) |
| red-as-expected-load-bg-window | STALE | 1 | 1 | 2026-11-05T08:15:37-0300 | load-bg-window-neg.log | deps mudaram depois da medicao (medido 2026-11-05T08:15:37-0300) |
| parakeet-ultra | NOT RUN | - | 0 | - | parakeet-ultra.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-parakeet-ultra | EXPECTED-RED | 1 | 1 | 2026-11-05T08:16:03-0300 | parakeet-ultra-neg.log | always |
| hotkey-observed | PASS | 0 | 0 | 2026-11-05T08:16:15-0300 | hotkey-observed.log | always |
| red-as-expected-hotkey-observed | EXPECTED-RED | 1 | 1 | 2026-11-05T08:16:29-0300 | hotkey-observed-neg.log | always |
| youtube-reveal | PASS | 0 | 0 | 2026-11-05T08:16:53-0300 | youtube-reveal.log | always |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-05T08:17:03-0300 | youtube-reveal-neg.log | always |
| youtube-rows | PASS | 0 | 0 | 2026-11-05T08:17:18-0300 | youtube-rows.log | always |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-05T08:17:38-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-05T08:17:53-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-05T08:18:16-0300 | youtube-drift-neg.log | always |
| bend-laws | NO-VERDICT | 0 | 0 | 2026-11-05T06:52:48-0300 | bend-laws.log | log alterado depois do registo |
| bend-laws-model | PASS | 0 | 0 | 2026-11-05T06:52:49-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-05T06:52:49-0300 | bend-laws-model-neg.log | always |
| panel-hidden-at-startup-oracle | NO-VERDICT | 0 | 0 | 2026-11-05T01:06:46-0300 | panel-hidden-at-startup.log | log alterado depois do registo |
| red-as-expected-panel-hidden-at-startup | STALE | 1 | 1 | 2026-11-05T01:06:49-0300 | panel-hidden-at-startup-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:06:49-0300) |
| panel-nav-stall | NOT RUN | - | 0 | - | panel-nav-stall.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-panel-nav-stall | NOT RUN | - | 1 | - | panel-nav-stall-neg.log | sem registo no stepcache (o passo nao completou) |
| worker-start-wiring | STALE | 0 | 0 | 2026-11-05T01:06:50-0300 | wiring-worker-start.log | deps mudaram depois da medicao (medido 2026-11-05T01:06:50-0300) |
| embedded-js-check | STALE | 0 | 0 | 2026-11-05T01:06:51-0300 | embedded-js.log | deps mudaram depois da medicao (medido 2026-11-05T01:06:51-0300) |
| lane1-worker-default-arms | STALE | 0 | 0 | 2026-11-05T01:06:51-0300 | lane1-arms.log | deps mudaram depois da medicao (medido 2026-11-05T01:06:51-0300) |
| external-subs-stability | PASS | 0 | 0 | 2026-11-04T09:10:58-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | STALE | 0 | 0 | 2026-11-05T01:06:52-0300 | external-caption-chrome-census.log | deps mudaram depois da medicao (medido 2026-11-05T01:06:52-0300) |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-11-03T12:04:04-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-03T12:04:04-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-11-04T01:12:36-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-04T11:00:07-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-11-04T01:12:37-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-11-04T01:12:38-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-11-04T01:12:38-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-11-04T09:11:02-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-11-04T09:11:04-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-11-04T09:20:21-0300 | gitattributes-verify.log | - |
| agents-md-pins | STALE | 0 | 0 | 2026-11-05T01:06:55-0300 | agents-md-pins.log | deps mudaram depois da medicao (medido 2026-11-05T01:06:55-0300) |
| lang-id-oracle | STALE | 0 | 0 | 2026-11-05T01:07:03-0300 | lang-id-oracle.log | deps mudaram depois da medicao (medido 2026-11-05T01:07:03-0300) |
| red-as-expected-lang-id-oracle | STALE | 1 | 1 | 2026-11-05T01:07:27-0300 | lang-id-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:07:27-0300) |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-04T11:54:52-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-04T11:54:52-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-11-02T19:45:18-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-11-02T19:45:19-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-05T01:07:32-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-05T01:07:32-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-05T01:07:33-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:07:33-0300) |
| per-app-source-plumbing | STALE | 0 | 0 | 2026-11-05T01:07:34-0300 | per-app-source-plumbing.log | deps mudaram depois da medicao (medido 2026-11-05T01:07:34-0300) |
| red-as-expected-per-app-source-plumbing | STALE | 1 | 1 | 2026-11-05T01:07:35-0300 | per-app-source-plumbing-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:07:35-0300) |
| redux-live-contract | FAIL | 1 | 0 | 2026-11-05T01:07:36-0300 | redux-live-contract.log | rc=1 != esperado 0 |
| red-as-expected-redux-live-contract | FAIL | 0 | 1 | 2026-11-05T01:07:37-0300 | redux-live-contract-neg.log | rc=0 != esperado 1 |
| word-split-oracle | STALE | 0 | 0 | 2026-11-05T01:07:39-0300 | word-split-oracle.log | deps mudaram depois da medicao (medido 2026-11-05T01:07:39-0300) |
| red-as-expected-word-split-oracle | STALE | 1 | 1 | 2026-11-05T01:07:40-0300 | word-split-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:07:40-0300) |
| vad-option-probe | STALE | 0 | 0 | 2026-11-05T01:08:00-0300 | vad-option-probe.log | deps mudaram depois da medicao (medido 2026-11-05T01:08:00-0300) |
| red-as-expected-vad-option-probe | STALE | 1 | 1 | 2026-11-05T01:08:01-0300 | vad-option-probe-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:08:01-0300) |
| youtube-track-wiring | STALE | 0 | 0 | 2026-11-05T01:08:04-0300 | youtube-track-wiring.log | deps mudaram depois da medicao (medido 2026-11-05T01:08:04-0300) |
| tap-open-timeout | STALE | 0 | 0 | 2026-11-05T01:08:41-0300 | tap-open-timeout.log | deps mudaram depois da medicao (medido 2026-11-05T01:08:41-0300) |
| ui-stall-oracle | STALE | 0 | 0 | 2026-11-05T01:08:49-0300 | ui-stall-oracle.log | deps mudaram depois da medicao (medido 2026-11-05T01:08:49-0300) |
| mute-audio | NO-VERDICT | 0 | 0 | 2026-11-01T16:18:51-0300 | mute-audio.log | log alterado depois do registo |
| device-silence | NO-VERDICT | 0 | 0 | 2026-11-01T16:21:39-0300 | device-silence.log | log alterado depois do registo |
| red-as-expected-device-silence | NO-VERDICT | 1 | 1 | 2026-11-01T16:22:30-0300 | device-silence-neg.log | log alterado depois do registo |
| console-window-audit | FAIL | 1 | 0 | 2026-11-05T01:09:23-0300 | console-window-audit.log | rc=1 != esperado 0 |
| red-as-expected-console-window-audit | EXPECTED-RED | 1 | 1 | 2026-11-05T01:09:26-0300 | console-window-audit-neg.log | always |
| red-as-expected-console-window-watch | EXPECTED-RED | 1 | 1 | 2026-11-05T01:09:31-0300 | console-window-watch-neg.log | always |
| capture-exclude | PASS | 0 | 0 | 2026-11-05T01:09:35-0300 | capture-exclude.log | always |
| red-as-expected-capture-exclude | EXPECTED-RED | 1 | 1 | 2026-11-05T01:09:39-0300 | capture-exclude-neg.log | always |
| history-merge | STALE | 0 | 0 | 2026-11-05T01:09:45-0300 | history-merge.log | deps mudaram depois da medicao (medido 2026-11-05T01:09:45-0300) |
| red-as-expected-history-merge | STALE | 1 | 1 | 2026-11-05T01:09:49-0300 | history-merge-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:09:49-0300) |
| reveal-clock | STALE | 0 | 0 | 2026-11-05T01:09:50-0300 | reveal-clock.log | deps mudaram depois da medicao (medido 2026-11-05T01:09:50-0300) |
| red-as-expected-reveal-clock | EXPECTED-RED | 1 | 1 | 2026-11-05T01:09:54-0300 | reveal-clock-neg.log | always |
| tap-first-block | STALE | 0 | 0 | 2026-11-05T01:10:01-0300 | tap-first-block.log | deps mudaram depois da medicao (medido 2026-11-05T01:10:01-0300) |
| red-as-expected-tap-first-block | STALE | 1 | 1 | 2026-11-05T01:10:07-0300 | tap-first-block-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:10:07-0300) |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-05T01:10:14-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T01:10:17-0300 | owner-audio-gate-neg.log | always |
| worker-providers | STALE | 0 | 0 | 2026-11-05T01:10:20-0300 | worker-providers.log | deps mudaram depois da medicao (medido 2026-11-05T01:10:20-0300) |
| red-as-expected-worker-providers | EXPECTED-RED | 1 | 1 | 2026-11-05T01:10:23-0300 | worker-providers-neg.log | always |
| review-f1f3 | STALE | 0 | 0 | 2026-11-05T01:10:26-0300 | review-f1f3.log | deps mudaram depois da medicao (medido 2026-11-05T01:10:26-0300) |
| review-tapstop | PASS | 0 | 0 | 2026-11-04T13:22:34-0300 | review-tapstop.log | - |
| strip-surface-oracle | FAIL | 3 | 0 | 2026-11-05T01:10:46-0300 | strip-surface-oracle.log | rc=3 != esperado 0 |
| strip-stats-log-budget | NO-VERDICT | 0 | 0 | 2026-11-01T16:23:31-0300 | strip-stats-log.log | log alterado depois do registo |
| strip-hot-reload | FAIL | 3 | 0 | 2026-11-05T01:11:19-0300 | strip-reload.log | rc=3 != esperado 0 |
| strip-surface-runtime | NO-VERDICT | 0 | 0 | 2026-11-01T15:15:59-0300 | strip-surface.log | log alterado depois do registo |
| red-as-expected-strip-surface | NO-VERDICT | 1 | 1 | 2026-11-01T15:15:59-0300 | strip-surface-neg.log | log alterado depois do registo |
| strip-geometry-restore | NO-VERDICT | 0 | 0 | 2026-11-01T13:41:35-0300 | strip-restore.log | log alterado depois do registo |
| strip-stats-wave | NO-VERDICT | 0 | 0 | 2026-11-01T16:24:01-0300 | strip-stats.log | log alterado depois do registo |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-04T09:11:57-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-05T01:11:30-0300 | hotkey-registration.log | always |
| hotkey-delivery | STALE | 0 | 0 | 2026-11-05T01:11:34-0300 | hotkey-delivery.log | deps mudaram depois da medicao (medido 2026-11-05T01:11:34-0300) |
| open-close-stall | STALE | 0 | 0 | 2026-11-05T01:11:38-0300 | open-close-stall.log | deps mudaram depois da medicao (medido 2026-11-05T01:11:38-0300) |
| red-as-expected-open-close-stall | STALE | 1 | 1 | 2026-11-05T01:12:20-0300 | open-close-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:20-0300) |
| autostart-status | STALE | 0 | 0 | 2026-11-05T01:12:22-0300 | autostart-status.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:22-0300) |
| control-verdict-gate-unguard | STALE | 0 | 0 | 2026-11-05T01:12:23-0300 | control-verdict-gate-unguard.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:23-0300) |
| control-history-producer-stamp-nvidia | STALE | 0 | 0 | 2026-11-05T01:12:25-0300 | control-history-producer-stamp-nvidia.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:25-0300) |
| control-redux-flag-neg-arm | STALE | 0 | 0 | 2026-11-05T01:12:28-0300 | control-redux-flag-neg-arm.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:28-0300) |
| control-panel-exit3-neg-arm | NO-VERDICT | 0 | 0 | 2026-11-01T13:43:10-0300 | control-panel-exit3-neg-arm.log | log alterado depois do registo |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-11-04T13:23:35-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | STALE | 0 | 0 | 2026-11-05T01:12:35-0300 | control-panel2-repeat-revert.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:35-0300) |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-10-20T02:26:54-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | STALE | 1 | 1 | 2026-11-05T01:12:37-0300 | control-historico-gate-off.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:37-0300) |
| search-oracle | STALE | 0 | 0 | 2026-11-05T01:12:39-0300 | search-oracle.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:39-0300) |
| red-as-expected-search-oracle | STALE | 1 | 1 | 2026-11-05T01:12:42-0300 | search-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:42-0300) |
| panel-search-keyboard | STALE | 0 | 0 | 2026-11-05T01:12:48-0300 | panel-search-keyboard.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:48-0300) |
| red-as-expected-panel-search-keyboard | STALE | 1 | 1 | 2026-11-05T01:12:52-0300 | panel-search-keyboard-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:12:52-0300) |
| fresh-processor-probe | STALE | 0 | 0 | 2026-11-05T01:13:02-0300 | fresh-processor.log | deps mudaram depois da medicao (medido 2026-11-05T01:13:02-0300) |
| stepcache-oracle | PASS | 0 | 0 | 2026-11-04T09:12:07-0300 | stepcache-oracle.log | - |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-05T01:13:08-0300 | _skip-guard.log | always |
| altc-first-caption | NO-VERDICT | 0 | 0 | 2026-11-01T16:24:24-0300 | altc-first-caption.log | log alterado depois do registo |
| altc-gesture | STALE | 0 | 0 | 2026-11-05T01:13:25-0300 | altc-gesture.log | deps mudaram depois da medicao (medido 2026-11-05T01:13:25-0300) |
| headphone-cut | STALE | 0 | 0 | 2026-11-05T01:14:27-0300 | headphone-cut.log | deps mudaram depois da medicao (medido 2026-11-05T01:14:27-0300) |
| incomplete-word | STALE | 0 | 0 | 2026-11-05T01:14:27-0300 | incomplete-word.log | deps mudaram depois da medicao (medido 2026-11-05T01:14:27-0300) |
| ladder-signal | STALE | 0 | 0 | 2026-11-05T01:14:29-0300 | ladder-signal.log | deps mudaram depois da medicao (medido 2026-11-05T01:14:29-0300) |
| launch-as-token | PASS | 0 | 0 | 2026-11-05T01:14:35-0300 | launch-as-token.log | always |
| live-code-freshness | STALE | 0 | 0 | 2026-11-05T01:14:37-0300 | live-code-freshness.log | deps mudaram depois da medicao (medido 2026-11-05T01:14:37-0300) |
| load-shedding | STALE | 0 | 0 | 2026-11-05T01:14:41-0300 | load-shedding.log | deps mudaram depois da medicao (medido 2026-11-05T01:14:41-0300) |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-05T01:14:42-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | STALE | 1 | 1 | 2026-11-05T01:15:30-0300 | altc-gesture-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:15:30-0300) |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-05T01:15:31-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | STALE | 1 | 1 | 2026-11-05T01:15:34-0300 | incomplete-word-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:15:34-0300) |
| red-as-expected-ladder-signal | STALE | 1 | 1 | 2026-11-05T01:15:37-0300 | ladder-signal-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:15:37-0300) |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-05T01:15:43-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-05T01:15:44-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-05T01:15:48-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | STALE | 1 | 1 | 2026-11-05T01:17:01-0300 | load-shedding-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:01-0300) |
| red-as-expected-shell-relaunch | NO-VERDICT | 1 | 1 | 2026-11-01T13:46:03-0300 | shell-relaunch-neg.log | log alterado depois do registo |
| red-as-expected-word-clock | EXPECTED-RED | 1 | 1 | 2026-11-05T01:17:04-0300 | word-clock-neg.log | always |
| red-as-expected-youtube-monotonic | STALE | 1 | 1 | 2026-11-05T01:17:06-0300 | youtube-monotonic-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:06-0300) |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-05T01:17:09-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | STALE | 1 | 1 | 2026-11-05T01:17:11-0300 | youtube-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:11-0300) |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-05T01:17:12-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NO-VERDICT | 0 | 0 | 2026-11-01T13:46:10-0300 | shell-relaunch.log | log alterado depois do registo |
| word-clock | STALE | 0 | 0 | 2026-11-05T01:17:14-0300 | word-clock.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:14-0300) |
| youtube-monotonic | STALE | 0 | 0 | 2026-11-05T01:17:16-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:16-0300) |
| youtube-rate | STALE | 0 | 0 | 2026-11-05T01:17:17-0300 | youtube-rate.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:17-0300) |
| red-as-expected-youtube-rate | STALE | 1 | 1 | 2026-11-05T01:17:18-0300 | youtube-rate-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:18-0300) |
| click-through-applied | STALE | 0 | 0 | 2026-11-05T01:17:20-0300 | click-through-applied.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:20-0300) |
| red-as-expected-click-through-applied | STALE | 1 | 1 | 2026-11-05T01:17:21-0300 | click-through-applied-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:21-0300) |
| topmost-keepalive | PASS | 0 | 0 | 2026-11-05T01:17:23-0300 | topmost-keepalive.log | always |
| red-as-expected-topmost-keepalive | EXPECTED-RED | 1 | 1 | 2026-11-05T01:17:25-0300 | topmost-keepalive-neg.log | always |
| webview2-args-scope | STALE | 0 | 0 | 2026-11-05T01:17:28-0300 | webview2-args-scope.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:28-0300) |
| red-as-expected-webview2-args-scope | STALE | 1 | 1 | 2026-11-05T01:17:34-0300 | webview2-args-scope-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:34-0300) |
| power-recovery | STALE | 0 | 0 | 2026-11-05T01:17:35-0300 | power-recovery.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:35-0300) |
| red-as-expected-power-recovery | STALE | 1 | 1 | 2026-11-05T01:17:41-0300 | power-recovery-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:41-0300) |
| power-recovery-live | NOT RUN | - | 0 | - | power-recovery-live.log | sem registo no stepcache (o passo nao completou) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-05T01:17:49-0300 | youtube-sotto-drift.log | always |
| youtube-switch | STALE | 0 | 0 | 2026-11-05T01:17:52-0300 | youtube-switch.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:52-0300) |
| yt-no-dub | STALE | 0 | 0 | 2026-11-05T01:17:54-0300 | yt-no-dub.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:54-0300) |
| stale-display | STALE | 0 | 0 | 2026-11-05T01:17:57-0300 | stale-display.log | deps mudaram depois da medicao (medido 2026-11-05T01:17:57-0300) |
| red-as-expected-stale-display | STALE | 1 | 1 | 2026-11-05T01:18:02-0300 | stale-display-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:18:02-0300) |
| battery-class | STALE | 0 | 0 | 2026-11-05T01:18:07-0300 | battery-class.log | deps mudaram depois da medicao (medido 2026-11-05T01:18:07-0300) |
| red-as-expected-battery-class | STALE | 1 | 1 | 2026-11-05T01:18:10-0300 | battery-class-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:18:10-0300) |
| live-queue | STALE | 0 | 0 | 2026-11-05T01:18:12-0300 | live-queue.log | deps mudaram depois da medicao (medido 2026-11-05T01:18:12-0300) |
| red-as-expected-live-queue | STALE | 1 | 1 | 2026-11-05T01:18:16-0300 | live-queue-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:18:16-0300) |
| flat-endpoint | PASS | 0 | 0 | 2026-11-05T01:18:18-0300 | flat-endpoint.log | always |
| tap-silent-desktop | STALE | 0 | 0 | 2026-11-05T01:18:20-0300 | tap-silent-desktop.log | deps mudaram depois da medicao (medido 2026-11-05T01:18:20-0300) |
| red-as-expected-tap-silent-desktop | STALE | 1 | 1 | 2026-11-05T01:18:23-0300 | tap-silent-desktop-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:18:23-0300) |
| warm-engine | STALE | 0 | 0 | 2026-11-05T01:18:35-0300 | warm-engine.log | deps mudaram depois da medicao (medido 2026-11-05T01:18:35-0300) |
| red-as-expected-warm-engine | STALE | 1 | 1 | 2026-11-05T01:19:44-0300 | warm-engine-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:19:44-0300) |
| gaming-hotkey | STALE | 0 | 0 | 2026-11-05T01:19:55-0300 | gaming-hotkey.log | deps mudaram depois da medicao (medido 2026-11-05T01:19:55-0300) |
| red-as-expected-gaming-hotkey | STALE | 1 | 1 | 2026-11-05T01:20:44-0300 | gaming-hotkey-neg.log | deps mudaram depois da medicao (medido 2026-11-05T01:20:44-0300) |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
