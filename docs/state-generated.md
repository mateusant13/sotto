# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=321 · PASS=160 · EXPECTED-RED=118 · FAIL=6 · STALE=21 · NO-VERDICT=1 · NOT RUN=15

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-05T14:40:17-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-11-05T14:40:17-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | PASS | 0 | 0 | 2026-11-05T14:40:18-0300 | pycompile-worker.log | - |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-11-05T14:40:18-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-11-05T15:30:25-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-11-05T15:30:25-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-11-05T15:30:26-0300 | oracle-historico-vs-redux.log | - |
| redux-transcript-path | PASS | 0 | 0 | 2026-11-05T14:40:23-0300 | redux-transcript-path.log | - |
| caption-cumulative | PASS | 0 | 0 | 2026-11-05T15:30:26-0300 | oracle-caption-cumulative.log | - |
| red-as-expected-caption-cumulative | EXPECTED-RED | 1 | 1 | 2026-11-05T15:30:27-0300 | caption-cumulative-neg.log | - |
| caption-lag-budget | PASS | 0 | 0 | 2026-11-05T14:40:24-0300 | caption-lag-budget.log | - |
| red-as-expected-caption-lag-budget | EXPECTED-RED | 1 | 1 | 2026-11-05T14:40:32-0300 | caption-lag-budget-neg.log | - |
| lag-note-cost | PASS | 0 | 0 | 2026-11-05T15:30:28-0300 | lag-note-cost.log | always |
| red-as-expected-lag-note-cost | EXPECTED-RED | 1 | 1 | 2026-11-05T15:30:30-0300 | lag-note-cost-neg.log | always |
| youtube-hidden-clock | PASS | 0 | 0 | 2026-11-05T15:30:31-0300 | youtube-hidden-clock.log | always |
| red-as-expected-youtube-hidden-clock | EXPECTED-RED | 1 | 1 | 2026-11-05T15:30:33-0300 | youtube-hidden-clock-neg.log | always |
| caption-overlay-screen | PASS | 0 | 0 | 2026-11-05T15:30:34-0300 | caption-overlay-screen.log | always |
| red-as-expected-caption-overlay-screen | EXPECTED-RED | 1 | 1 | 2026-11-05T15:30:35-0300 | caption-overlay-screen-neg.log | always |
| youtube-cdp-boot | PASS | 0 | 0 | 2026-11-05T15:30:38-0300 | youtube-cdp-boot.log | always |
| red-as-expected-youtube-cdp-boot | EXPECTED-RED | 1 | 1 | 2026-11-05T15:30:48-0300 | youtube-cdp-boot-neg.log | always |
| youtube-first-at-boot | PASS | 0 | 0 | 2026-11-05T15:30:59-0300 | youtube-first-at-boot.log | always |
| red-as-expected-youtube-first-at-boot | EXPECTED-RED | 1 | 1 | 2026-11-05T15:31:39-0300 | youtube-first-at-boot-neg.log | always |
| red-as-expected-redux-transcript-path | EXPECTED-RED | 1 | 1 | 2026-11-05T14:45:58-0300 | redux-transcript-path-neg.log | - |
| control-verdict-gate-drop-redux-live | PASS | 0 | 0 | 2026-11-05T14:45:59-0300 | control-verdict-gate-drop-redux-live.log | - |
| history-producer-gate | PASS | 0 | 0 | 2026-11-05T15:31:41-0300 | gate-history-producer.log | - |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-11-05T15:31:41-0300 | gate-panel-state-guard.log | - |
| verdict-gate | PASS | 0 | 0 | 2026-11-05T14:46:02-0300 | gate-verdict.log | - |
| worker-park | PASS | 0 | 0 | 2026-11-05T15:32:14-0300 | worker-park.log | always |
| red-as-expected-worker-park | EXPECTED-RED | 1 | 1 | 2026-11-05T15:32:15-0300 | worker-park-neg.log | always |
| lane2-reset-probe | PASS | 0 | 0 | 2026-11-05T15:32:15-0300 | lane2-reset.log | - |
| lane3-verdict-probe | PASS | 0 | 0 | 2026-11-05T14:46:51-0300 | lane3-verdict.log | - |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-11-05T14:46:56-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-11-05T15:32:16-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-11-05T15:32:20-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-11-05T14:47:02-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-11-05T15:32:23-0300 | panel2-dom-probe.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-11-05T15:32:31-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-11-05T14:47:29-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:29-0300 | border-radius-gate-neg.log | - |
| hidden-launch | PASS | 0 | 0 | 2026-11-05T14:47:36-0300 | hidden-launch.log | - |
| red-as-expected-hidden-launch | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:37-0300 | hidden-launch-neg.log | - |
| step-deadline | PASS | 0 | 0 | 2026-11-05T14:47:49-0300 | step-deadline.log | - |
| red-as-expected-step-deadline | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:02-0300 | step-deadline-neg.log | - |
| emit-prewebview | PASS | 0 | 0 | 2026-11-05T14:48:02-0300 | emit-prewebview.log | - |
| red-as-expected-emit-prewebview | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:03-0300 | emit-prewebview-neg.log | - |
| hotkey-live-edge | PASS | 0 | 0 | 2026-11-05T14:48:09-0300 | hotkey-live-edge.log | - |
| red-as-expected-hotkey-live-edge | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:15-0300 | hotkey-live-edge-neg.log | - |
| lane-screen-gate | PASS | 0 | 0 | 2026-11-05T14:48:29-0300 | lane-screen-gate.log | - |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:29-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-05T14:48:30-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-11-05T14:48:31-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:31-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-05T14:48:32-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:33-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | PASS | 0 | 0 | 2026-11-05T14:48:34-0300 | youtube-foreign-paint.log | - |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:35-0300 | youtube-foreign-paint-neg.log | - |
| input-path | PASS | 0 | 0 | 2026-11-05T14:48:56-0300 | input-path.log | - |
| red-as-expected-input-path | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:57-0300 | input-path-neg.log | - |
| exception-hygiene | PASS | 0 | 0 | 2026-11-05T14:49:01-0300 | exception-hygiene.log | - |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-05T14:49:11-0300 | exception-hygiene-neg.log | - |
| seam-coverage | PASS | 0 | 0 | 2026-11-05T14:49:26-0300 | seam-coverage.log | - |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:13-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-05T14:50:14-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:15-0300 | bug-ledger-neg.log | - |
| tooling-intent | FAIL | 2 | 0 | 2026-11-05T15:32:38-0300 | tooling-intent.log | rc=2 != esperado 0 |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:18-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-05T14:50:18-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:20-0300 | external-resume-neg.log | - |
| silence-kill | PASS | 0 | 0 | 2026-11-05T14:50:20-0300 | silence-kill.log | - |
| red-as-expected-silence-kill | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:21-0300 | silence-kill-neg.log | - |
| worker-churn | PASS | 0 | 0 | 2026-11-05T14:50:25-0300 | worker-churn.log | - |
| red-as-expected-worker-churn | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:30-0300 | worker-churn-neg.log | - |
| rss-trend | PASS | 0 | 0 | 2026-11-05T14:50:31-0300 | rss-trend.log | - |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:32-0300 | rss-trend-neg.log | - |
| death-cause | PASS | 0 | 0 | 2026-11-05T14:50:33-0300 | death-cause.log | - |
| red-as-expected-death-cause | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:34-0300 | death-cause-neg.log | - |
| caption-seam-dedup | PASS | 0 | 0 | 2026-11-05T14:50:35-0300 | caption-seam-dedup.log | - |
| red-as-expected-caption-seam-dedup | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:36-0300 | caption-seam-dedup-neg.log | - |
| freeze-census | PASS | 0 | 0 | 2026-11-05T14:50:40-0300 | freeze-census.log | - |
| red-as-expected-caption-budget | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:41-0300 | caption-budget-neg.log | - |
| dead-app-exit | PASS | 0 | 0 | 2026-11-05T14:51:01-0300 | dead-app-exit.log | - |
| shell-priority | PASS | 0 | 0 | 2026-11-05T14:51:02-0300 | shell-priority.log | - |
| red-as-expected-shell-priority | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:02-0300 | shell-priority-neg.log | - |
| tray-menu | PASS | 0 | 0 | 2026-11-05T14:51:03-0300 | tray-menu.log | - |
| red-as-expected-tray-menu | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:04-0300 | tray-menu-neg.log | - |
| caption-kept-on-hide | PASS | 0 | 0 | 2026-11-05T14:51:05-0300 | caption-kept-on-hide.log | - |
| red-as-expected-caption-kept-on-hide | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:07-0300 | caption-kept-on-hide-neg.log | - |
| panel-prefix-row | STALE | 0 | 0 | 2026-11-05T15:11:36-0300 | panel-prefix-row.log | deps mudaram depois da medicao (medido 2026-11-05T15:11:36-0300) |
| red-as-expected-panel-prefix-row | STALE | 1 | 1 | 2026-11-05T15:11:37-0300 | panel-prefix-row-neg.log | deps mudaram depois da medicao (medido 2026-11-05T15:11:37-0300) |
| fusion | PASS | 0 | 0 | 2026-11-05T14:51:09-0300 | fusion.log | - |
| red-as-expected-fusion | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:09-0300 | fusion-neg.log | - |
| agc-peak-ceiling | PASS | 0 | 0 | 2026-11-05T14:51:10-0300 | agc-peak-ceiling.log | - |
| red-as-expected-agc-peak-ceiling | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:11-0300 | agc-peak-ceiling-neg.log | - |
| reveal-park | PASS | 0 | 0 | 2026-11-05T14:51:13-0300 | reveal-park.log | - |
| red-as-expected-reveal-park | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:20-0300 | reveal-park-neg.log | - |
| youtube-verbatim | PASS | 0 | 0 | 2026-11-05T14:51:22-0300 | youtube-verbatim.log | - |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:23-0300 | youtube-verbatim-neg.log | - |
| code-health | FAIL | 2 | 0 | 2026-11-05T15:32:47-0300 | code-health.log | rc=2 != esperado 0 |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-05T15:32:48-0300 | code-health-neg.log | always |
| undefined-names | PASS | 0 | 0 | 2026-11-05T15:32:51-0300 | undefined-names.log | always |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-05T15:32:51-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | PASS | 0 | 0 | 2026-11-05T14:51:31-0300 | battery-heavy-gate.log | - |
| red-as-expected-battery-heavy-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:37-0300 | battery-heavy-gate-neg.log | - |
| task-resolver-gate | PASS | 0 | 0 | 2026-11-05T14:51:37-0300 | task-resolver-gate.log | - |
| red-as-expected-task-resolver-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:38-0300 | task-resolver-gate-neg.log | - |
| claims-date | PASS | 0 | 0 | 2026-11-05T14:51:39-0300 | claims-date.log | - |
| red-as-expected-claims-date | EXPECTED-RED | 1 | 1 | 2026-11-05T14:51:39-0300 | claims-date-neg.log | - |
| stall-under-load | PASS | 0 | 0 | 2026-11-05T15:32:54-0300 | stall-under-load.log | always |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-05T15:32:54-0300 | stall-under-load-neg.log | always |
| paint-live-show | PASS | 0 | 0 | 2026-11-05T15:33:16-0300 | paint-live-show.log | always |
| red-as-expected-paint-live-show | EXPECTED-RED | 1 | 1 | 2026-11-05T15:33:31-0300 | paint-live-show-neg.log | always |
| panel-paint-first-measure | NOT RUN | - | 0 | - | panel-paint-first-measure.log | sem registo no stepcache (o passo nao completou) |
| panel-paint-first | PASS | 0 | 0 | 2026-11-05T15:33:31-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-05T15:33:32-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-05T15:33:32-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-05T15:33:33-0300 | receipt-provenance-neg.log | always |
| async-track-fetch | PASS | 0 | 0 | 2026-11-05T14:52:30-0300 | async-track-fetch.log | - |
| red-as-expected-async-track-fetch | EXPECTED-RED | 1 | 1 | 2026-11-05T14:52:39-0300 | async-track-fetch-neg.log | - |
| batch-queue-drain | PASS | 0 | 0 | 2026-11-05T14:52:43-0300 | batch-queue-drain.log | - |
| red-as-expected-batch-queue-drain | EXPECTED-RED | 1 | 1 | 2026-11-05T14:52:53-0300 | batch-queue-drain-neg.log | - |
| hotkey-live-toggle | PASS | 0 | 0 | 2026-11-05T14:52:57-0300 | hotkey-live-toggle.log | - |
| red-as-expected-hotkey-live-toggle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:07-0300 | hotkey-live-toggle-neg.log | - |
| loading-placeholder | PASS | 0 | 0 | 2026-11-05T14:53:08-0300 | loading-placeholder.log | - |
| red-as-expected-loading-placeholder | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:09-0300 | loading-placeholder-neg.log | - |
| youtube-land | STALE | 0 | 0 | 2026-11-05T15:33:35-0300 | youtube-land.log | deps mudaram depois da medicao (medido 2026-11-05T15:33:35-0300) |
| red-as-expected-youtube-land | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:11-0300 | youtube-land-neg.log | - |
| time-to-first-caption | STALE | 0 | 0 | 2026-11-05T15:33:36-0300 | time-to-first-caption.log | deps mudaram depois da medicao (medido 2026-11-05T15:33:36-0300) |
| red-as-expected-time-to-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:12-0300 | time-to-first-caption-neg.log | - |
| first-capture-fast | PASS | 0 | 0 | 2026-11-05T15:33:38-0300 | first-capture-fast.log | always |
| red-as-expected-first-capture-fast | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:18-0300 | first-capture-fast-neg.log | - |
| youtube-land-replay | PASS | 0 | 0 | 2026-11-05T14:53:21-0300 | youtube-land-replay.log | - |
| red-as-expected-youtube-land-replay | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:24-0300 | youtube-land-replay-neg.log | - |
| yt-loop-uia | PASS | 0 | 0 | 2026-11-05T14:53:24-0300 | yt-loop-uia.log | - |
| red-as-expected-yt-loop-uia | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:25-0300 | yt-loop-uia-neg.log | - |
| yt-target-stale | PASS | 0 | 0 | 2026-11-05T15:13:11-0300 | yt-target-stale.log | - |
| red-as-expected-yt-target-stale | EXPECTED-RED | 1 | 1 | 2026-11-05T15:13:13-0300 | yt-target-stale-neg.log | - |
| owner-screen | PASS | 0 | 0 | 2026-11-05T14:53:32-0300 | owner-screen.log | - |
| red-as-expected-owner-screen | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:38-0300 | owner-screen-neg.log | - |
| job-object | PASS | 0 | 0 | 2026-11-05T14:53:42-0300 | job-object.log | - |
| red-as-expected-job-object | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:45-0300 | job-object-neg.log | - |
| emit-pipe-dead | PASS | 0 | 0 | 2026-11-05T14:53:46-0300 | emit-pipe-dead.log | - |
| red-as-expected-emit-pipe-dead | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:46-0300 | emit-pipe-dead-neg.log | - |
| state-page-write | NO-VERDICT | 0 | 0 | 2026-11-05T15:13:22-0300 | state-page-write.log | log alterado depois do registo |
| state-page | STALE | 0 | 0 | 2026-11-05T15:13:39-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-05T15:13:39-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-05T15:15:43-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-05T15:15:43-0300) |
| battery-wiring | PASS | 0 | 0 | 2026-11-05T14:54:23-0300 | battery-wiring.log | - |
| red-as-expected-battery-wiring | EXPECTED-RED | 1 | 1 | 2026-11-05T14:54:30-0300 | battery-wiring-neg.log | - |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-05T15:15:45-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-05T15:15:52-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | PASS | 0 | 0 | 2026-11-05T15:15:54-0300 | youtube-1to1.log | always |
| red-as-expected-youtube-1to1 | EXPECTED-RED | 1 | 1 | 2026-11-05T15:15:58-0300 | youtube-1to1-neg.log | always |
| youtube-cdp-source | PASS | 0 | 0 | 2026-11-05T15:16:04-0300 | youtube-cdp-source.log | always |
| red-as-expected-youtube-cdp-source | EXPECTED-RED | 1 | 1 | 2026-11-05T15:16:16-0300 | youtube-cdp-source-neg.log | always |
| caption-producer | PASS | 0 | 0 | 2026-11-05T15:16:17-0300 | caption-producer.log | always |
| red-as-expected-caption-producer | EXPECTED-RED | 1 | 1 | 2026-11-05T15:16:18-0300 | caption-producer-neg.log | always |
| caption-style | PASS | 0 | 0 | 2026-11-05T15:16:19-0300 | caption-style.log | always |
| red-as-expected-caption-style | EXPECTED-RED | 1 | 1 | 2026-11-05T15:16:21-0300 | caption-style-neg.log | always |
| panel-commit-stable | STALE | 0 | 0 | 2026-11-05T15:16:34-0300 | panel-commit-stable.log | deps mudaram depois da medicao (medido 2026-11-05T15:16:34-0300) |
| red-as-expected-panel-commit-stable | STALE | 1 | 1 | 2026-11-05T15:16:45-0300 | panel-commit-stable-neg.log | deps mudaram depois da medicao (medido 2026-11-05T15:16:45-0300) |
| paint-row-seam | PASS | 0 | 0 | 2026-11-05T15:16:45-0300 | paint-row-seam.log | always |
| red-as-expected-paint-row-seam | EXPECTED-RED | 1 | 1 | 2026-11-05T15:16:46-0300 | paint-row-seam-neg.log | always |
| load-bg-window | PASS | 0 | 0 | 2026-11-05T15:16:47-0300 | load-bg-window.log | always |
| red-as-expected-load-bg-window | EXPECTED-RED | 1 | 1 | 2026-11-05T15:16:48-0300 | load-bg-window-neg.log | always |
| parakeet-ultra | NOT RUN | - | 0 | - | parakeet-ultra.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-parakeet-ultra | EXPECTED-RED | 1 | 1 | 2026-11-05T15:16:49-0300 | parakeet-ultra-neg.log | always |
| hotkey-observed | PASS | 0 | 0 | 2026-11-05T15:16:55-0300 | hotkey-observed.log | always |
| red-as-expected-hotkey-observed | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:00-0300 | hotkey-observed-neg.log | always |
| youtube-reveal | PASS | 0 | 0 | 2026-11-05T15:17:01-0300 | youtube-reveal.log | always |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:03-0300 | youtube-reveal-neg.log | always |
| youtube-rows | PASS | 0 | 0 | 2026-11-05T15:17:04-0300 | youtube-rows.log | always |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:06-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-05T15:17:07-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:07-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-05T15:17:21-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-05T15:17:22-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:22-0300 | bend-laws-model-neg.log | always |
| panel-hidden-at-startup-oracle | STALE | 0 | 0 | 2026-11-05T14:57:47-0300 | panel-hidden-at-startup.log | deps mudaram depois da medicao (medido 2026-11-05T14:57:47-0300) |
| red-as-expected-panel-hidden-at-startup | STALE | 1 | 1 | 2026-11-05T14:57:50-0300 | panel-hidden-at-startup-neg.log | deps mudaram depois da medicao (medido 2026-11-05T14:57:50-0300) |
| panel-nav-stall | PASS | 0 | 0 | 2026-11-05T14:57:51-0300 | panel-nav-stall.log | - |
| red-as-expected-panel-nav-stall | EXPECTED-RED | 1 | 1 | 2026-11-05T14:57:54-0300 | panel-nav-stall-neg.log | - |
| worker-start-wiring | PASS | 0 | 0 | 2026-11-05T14:57:55-0300 | wiring-worker-start.log | - |
| embedded-js-check | PASS | 0 | 0 | 2026-11-05T14:57:56-0300 | embedded-js.log | - |
| lane1-worker-default-arms | PASS | 0 | 0 | 2026-11-05T14:57:57-0300 | lane1-arms.log | - |
| external-subs-stability | PASS | 0 | 0 | 2026-11-05T14:57:57-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | FAIL | 1 | 0 | 2026-11-05T15:17:25-0300 | external-caption-chrome-census.log | rc=1 != esperado 0 |
| external-caption-chrome-census-fixture | STALE | 0 | 0 | 2026-11-05T14:57:58-0300 | external-caption-chrome-census-fixture.log | deps mudaram depois da medicao (medido 2026-11-05T14:57:58-0300) |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-05T14:57:59-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-11-05T14:58:01-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-05T14:58:03-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-11-05T14:58:04-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-11-05T14:58:04-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:05-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-11-05T14:58:09-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:12-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | FAIL | 1 | 0 | 2026-11-05T15:17:32-0300 | gitattributes-verify.log | rc=1 != esperado 0 |
| agents-md-pins | PASS | 0 | 0 | 2026-11-05T14:58:20-0300 | agents-md-pins.log | - |
| lang-id-oracle | PASS | 0 | 0 | 2026-11-05T14:58:37-0300 | lang-id-oracle.log | - |
| red-as-expected-lang-id-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:14-0300 | lang-id-oracle-neg.log | - |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-05T14:59:14-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:15-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-11-05T14:59:16-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:18-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | PASS | 0 | 0 | 2026-11-05T14:59:19-0300 | panel-flash-contradiction.log | - |
| red-as-expected-panel-flash-contradiction | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:20-0300 | panel-flash-contradiction-neg.log | - |
| per-app-source-plumbing | PASS | 0 | 0 | 2026-11-05T14:59:20-0300 | per-app-source-plumbing.log | - |
| red-as-expected-per-app-source-plumbing | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:21-0300 | per-app-source-plumbing-neg.log | - |
| redux-live-contract | STALE | 0 | 0 | 2026-11-05T14:59:22-0300 | redux-live-contract.log | deps mudaram depois da medicao (medido 2026-11-05T14:59:22-0300) |
| red-as-expected-redux-live-contract | STALE | 1 | 1 | 2026-11-05T14:59:22-0300 | redux-live-contract-neg.log | deps mudaram depois da medicao (medido 2026-11-05T14:59:22-0300) |
| word-split-oracle | PASS | 0 | 0 | 2026-11-05T14:59:23-0300 | word-split-oracle.log | - |
| red-as-expected-word-split-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:24-0300 | word-split-oracle-neg.log | - |
| vad-option-probe | PASS | 0 | 0 | 2026-11-05T14:59:32-0300 | vad-option-probe.log | - |
| red-as-expected-vad-option-probe | EXPECTED-RED | 1 | 1 | 2026-11-05T14:59:33-0300 | vad-option-probe-neg.log | - |
| youtube-track-wiring | PASS | 0 | 0 | 2026-11-05T14:59:34-0300 | youtube-track-wiring.log | - |
| tap-open-timeout | PASS | 0 | 0 | 2026-11-05T15:00:09-0300 | tap-open-timeout.log | - |
| ui-stall-oracle | PASS | 0 | 0 | 2026-11-05T15:00:14-0300 | ui-stall-oracle.log | - |
| mute-audio | NOT RUN | - | 0 | - | mute-audio.log | sem registo no stepcache (o passo nao completou) |
| device-silence | NOT RUN | - | 0 | - | device-silence.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-device-silence | NOT RUN | - | 1 | - | device-silence-neg.log | sem registo no stepcache (o passo nao completou) |
| console-window-audit | FAIL | 1 | 0 | 2026-11-05T15:17:47-0300 | console-window-audit.log | rc=1 != esperado 0 |
| red-as-expected-console-window-audit | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:48-0300 | console-window-audit-neg.log | always |
| red-as-expected-console-window-watch | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:48-0300 | console-window-watch-neg.log | always |
| capture-exclude | PASS | 0 | 0 | 2026-11-05T15:17:49-0300 | capture-exclude.log | always |
| red-as-expected-capture-exclude | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:50-0300 | capture-exclude-neg.log | always |
| history-merge | PASS | 0 | 0 | 2026-11-05T15:17:50-0300 | history-merge.log | always |
| red-as-expected-history-merge | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:51-0300 | history-merge-neg.log | always |
| reveal-clock | PASS | 0 | 0 | 2026-11-05T15:17:52-0300 | reveal-clock.log | always |
| red-as-expected-reveal-clock | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:52-0300 | reveal-clock-neg.log | always |
| tap-first-block | PASS | 0 | 0 | 2026-11-05T15:17:53-0300 | tap-first-block.log | always |
| red-as-expected-tap-first-block | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:54-0300 | tap-first-block-neg.log | always |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-05T15:17:56-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:57-0300 | owner-audio-gate-neg.log | always |
| worker-providers | PASS | 0 | 0 | 2026-11-05T15:17:58-0300 | worker-providers.log | always |
| red-as-expected-worker-providers | EXPECTED-RED | 1 | 1 | 2026-11-05T15:17:59-0300 | worker-providers-neg.log | always |
| review-f1f3 | PASS | 0 | 0 | 2026-11-05T15:00:40-0300 | review-f1f3.log | - |
| review-tapstop | PASS | 0 | 0 | 2026-11-05T15:00:43-0300 | review-tapstop.log | - |
| strip-surface-oracle | PASS | 0 | 0 | 2026-11-05T15:01:04-0300 | strip-surface-oracle.log | - |
| strip-stats-log-budget | NOT RUN | - | 0 | - | strip-stats-log.log | sem registo no stepcache (o passo nao completou) |
| strip-hot-reload | PASS | 0 | 0 | 2026-11-05T15:01:17-0300 | strip-reload.log | - |
| strip-surface-runtime | NOT RUN | - | 0 | - | strip-surface.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-strip-surface | NOT RUN | - | 1 | - | strip-surface-neg.log | sem registo no stepcache (o passo nao completou) |
| strip-geometry-restore | NOT RUN | - | 0 | - | strip-restore.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-wave | NOT RUN | - | 0 | - | strip-stats.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-05T15:01:18-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-05T15:18:03-0300 | hotkey-registration.log | always |
| hotkey-delivery | PASS | 0 | 0 | 2026-11-05T15:18:05-0300 | hotkey-delivery.log | always |
| open-close-stall | PASS | 0 | 0 | 2026-11-05T15:01:24-0300 | open-close-stall.log | - |
| red-as-expected-open-close-stall | EXPECTED-RED | 1 | 1 | 2026-11-05T15:01:38-0300 | open-close-stall-neg.log | - |
| autostart-status | PASS | 0 | 0 | 2026-11-05T15:18:07-0300 | autostart-status.log | always |
| control-verdict-gate-unguard | PASS | 0 | 0 | 2026-11-05T15:01:40-0300 | control-verdict-gate-unguard.log | - |
| control-history-producer-stamp-nvidia | STALE | 0 | 0 | 2026-11-05T15:01:41-0300 | control-history-producer-stamp-nvidia.log | deps mudaram depois da medicao (medido 2026-11-05T15:01:41-0300) |
| control-redux-flag-neg-arm | PASS | 0 | 0 | 2026-11-05T15:01:42-0300 | control-redux-flag-neg-arm.log | - |
| control-panel-exit3-neg-arm | NOT RUN | - | 0 | - | control-panel-exit3-neg-arm.log | sem registo no stepcache (o passo nao completou) |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-11-05T15:01:43-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | FAIL | 2 | 0 | 2026-11-05T15:18:10-0300 | control-panel2-repeat-revert.log | rc=2 != esperado 0 |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-11-05T15:01:45-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | STALE | 1 | 1 | 2026-11-05T15:01:46-0300 | control-historico-gate-off.log | deps mudaram depois da medicao (medido 2026-11-05T15:01:46-0300) |
| search-oracle | PASS | 0 | 0 | 2026-11-05T15:01:46-0300 | search-oracle.log | - |
| red-as-expected-search-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T15:01:50-0300 | search-oracle-neg.log | - |
| panel-search-keyboard | PASS | 0 | 0 | 2026-11-05T15:01:53-0300 | panel-search-keyboard.log | - |
| red-as-expected-panel-search-keyboard | EXPECTED-RED | 1 | 1 | 2026-11-05T15:01:56-0300 | panel-search-keyboard-neg.log | - |
| fresh-processor-probe | PASS | 0 | 0 | 2026-11-05T15:02:03-0300 | fresh-processor.log | - |
| stepcache-oracle | PASS | 0 | 0 | 2026-11-05T15:02:16-0300 | stepcache-oracle.log | - |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-05T15:18:14-0300 | _skip-guard.log | always |
| altc-first-caption | NOT RUN | - | 0 | - | altc-first-caption.log | sem registo no stepcache (o passo nao completou) |
| altc-gesture | PASS | 0 | 0 | 2026-11-05T15:18:23-0300 | altc-gesture.log | always |
| headphone-cut | STALE | 0 | 0 | 2026-11-05T15:19:24-0300 | headphone-cut.log | deps mudaram depois da medicao (medido 2026-11-05T15:19:24-0300) |
| incomplete-word | STALE | 0 | 0 | 2026-11-05T15:19:24-0300 | incomplete-word.log | deps mudaram depois da medicao (medido 2026-11-05T15:19:24-0300) |
| ladder-signal | PASS | 0 | 0 | 2026-11-05T15:19:25-0300 | ladder-signal.log | always |
| launch-as-token | PASS | 0 | 0 | 2026-11-05T15:19:30-0300 | launch-as-token.log | always |
| live-code-freshness | PASS | 0 | 0 | 2026-11-05T15:19:31-0300 | live-code-freshness.log | always |
| load-shedding | PASS | 0 | 0 | 2026-11-05T15:19:33-0300 | load-shedding.log | always |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-05T15:19:34-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:02-0300 | altc-gesture-neg.log | always |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:03-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:03-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:04-0300 | ladder-signal-neg.log | always |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:05-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-05T15:20:06-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:09-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:26-0300 | load-shedding-neg.log | always |
| red-as-expected-shell-relaunch | NOT RUN | - | 1 | - | shell-relaunch-neg.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-word-clock | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:27-0300 | word-clock-neg.log | always |
| red-as-expected-youtube-monotonic | STALE | 1 | 1 | 2026-11-05T15:20:28-0300 | youtube-monotonic-neg.log | deps mudaram depois da medicao (medido 2026-11-05T15:20:28-0300) |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:28-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:30-0300 | youtube-switch-neg.log | always |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:30-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NOT RUN | - | 0 | - | shell-relaunch.log | sem registo no stepcache (o passo nao completou) |
| word-clock | PASS | 0 | 0 | 2026-11-05T15:20:32-0300 | word-clock.log | always |
| youtube-monotonic | STALE | 0 | 0 | 2026-11-05T15:20:32-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-11-05T15:20:32-0300) |
| youtube-rate | PASS | 0 | 0 | 2026-11-05T15:20:33-0300 | youtube-rate.log | always |
| red-as-expected-youtube-rate | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:34-0300 | youtube-rate-neg.log | always |
| click-through-applied | PASS | 0 | 0 | 2026-11-05T15:20:34-0300 | click-through-applied.log | always |
| red-as-expected-click-through-applied | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:35-0300 | click-through-applied-neg.log | always |
| topmost-keepalive | PASS | 0 | 0 | 2026-11-05T15:20:36-0300 | topmost-keepalive.log | always |
| red-as-expected-topmost-keepalive | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:36-0300 | topmost-keepalive-neg.log | always |
| webview2-args-scope | PASS | 0 | 0 | 2026-11-05T15:20:36-0300 | webview2-args-scope.log | always |
| red-as-expected-webview2-args-scope | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:37-0300 | webview2-args-scope-neg.log | always |
| power-recovery | PASS | 0 | 0 | 2026-11-05T15:20:38-0300 | power-recovery.log | always |
| red-as-expected-power-recovery | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:42-0300 | power-recovery-neg.log | always |
| power-recovery-live | NOT RUN | - | 0 | - | power-recovery-live.log | sem registo no stepcache (o passo nao completou) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-05T15:20:43-0300 | youtube-sotto-drift.log | always |
| youtube-switch | PASS | 0 | 0 | 2026-11-05T15:20:44-0300 | youtube-switch.log | always |
| yt-no-dub | PASS | 0 | 0 | 2026-11-05T15:20:45-0300 | yt-no-dub.log | always |
| stale-display | PASS | 0 | 0 | 2026-11-05T15:20:46-0300 | stale-display.log | always |
| red-as-expected-stale-display | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:47-0300 | stale-display-neg.log | always |
| battery-class | PASS | 0 | 0 | 2026-11-05T15:20:48-0300 | battery-class.log | always |
| red-as-expected-battery-class | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:48-0300 | battery-class-neg.log | always |
| live-queue | PASS | 0 | 0 | 2026-11-05T15:20:49-0300 | live-queue.log | always |
| red-as-expected-live-queue | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:49-0300 | live-queue-neg.log | always |
| flat-endpoint | PASS | 0 | 0 | 2026-11-05T15:20:50-0300 | flat-endpoint.log | always |
| tap-silent-desktop | PASS | 0 | 0 | 2026-11-05T15:20:50-0300 | tap-silent-desktop.log | always |
| red-as-expected-tap-silent-desktop | EXPECTED-RED | 1 | 1 | 2026-11-05T15:20:51-0300 | tap-silent-desktop-neg.log | always |
| warm-engine | PASS | 0 | 0 | 2026-11-05T15:21:01-0300 | warm-engine.log | always |
| red-as-expected-warm-engine | EXPECTED-RED | 1 | 1 | 2026-11-05T15:21:56-0300 | warm-engine-neg.log | always |
| gaming-hotkey | PASS | 0 | 0 | 2026-11-05T15:22:03-0300 | gaming-hotkey.log | always |
| red-as-expected-gaming-hotkey | EXPECTED-RED | 1 | 1 | 2026-11-05T15:22:32-0300 | gaming-hotkey-neg.log | always |
| ctrlspace-swallow | PASS | 0 | 0 | 2026-11-05T15:22:34-0300 | ctrlspace-swallow.log | always |
| red-as-expected-ctrlspace-swallow | EXPECTED-RED | 1 | 1 | 2026-11-05T15:22:41-0300 | ctrlspace-swallow-neg.log | always |
| ctrlspace-swallow-os | PASS | 0 | 0 | 2026-11-05T15:22:41-0300 | ctrlspace-swallow-os.log | always |
| battery-budget | STALE | 0 | 0 | 2026-11-05T15:22:42-0300 | battery-budget.log | deps mudaram depois da medicao (medido 2026-11-05T15:22:42-0300) |
| red-as-expected-battery-budget | STALE | 1 | 1 | 2026-11-05T15:22:42-0300 | battery-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-05T15:22:42-0300) |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
