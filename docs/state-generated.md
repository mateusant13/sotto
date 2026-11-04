# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=243 · PASS=86 · EXPECTED-RED=57 · FAIL=2 · STALE=78 · NO-VERDICT=20 · NOT RUN=0

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-04T01:05:08-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-10-30T04:23:01-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | STALE | 0 | 0 | 2026-11-04T01:05:09-0300 | pycompile-worker.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:09-0300) |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-10-20T02:22:19-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-11-03T12:00:09-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-11-03T12:00:09-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-11-03T12:00:09-0300 | oracle-historico-vs-redux.log | - |
| redux-transcript-path | PASS | 0 | 0 | 2026-11-04T01:05:11-0300 | redux-transcript-path.log | - |
| caption-cumulative | PASS | 0 | 0 | 2026-11-03T12:27:53-0300 | oracle-caption-cumulative.log | - |
| red-as-expected-caption-cumulative | EXPECTED-RED | 1 | 1 | 2026-11-03T12:27:53-0300 | caption-cumulative-neg.log | - |
| caption-lag-budget | STALE | 0 | 0 | 2026-11-04T01:05:12-0300 | caption-lag-budget.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:12-0300) |
| red-as-expected-caption-lag-budget | STALE | 1 | 1 | 2026-11-04T01:05:16-0300 | caption-lag-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:16-0300) |
| red-as-expected-redux-transcript-path | EXPECTED-RED | 1 | 1 | 2026-11-04T01:05:17-0300 | redux-transcript-path-neg.log | - |
| control-verdict-gate-drop-redux-live | STALE | 0 | 0 | 2026-11-04T01:05:18-0300 | control-verdict-gate-drop-redux-live.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:18-0300) |
| history-producer-gate | STALE | 0 | 0 | 2026-11-04T01:05:19-0300 | gate-history-producer.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:19-0300) |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-11-03T12:00:13-0300 | gate-panel-state-guard.log | - |
| verdict-gate | STALE | 0 | 0 | 2026-11-04T01:05:20-0300 | gate-verdict.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:20-0300) |
| lane2-reset-probe | PASS | 0 | 0 | 2026-11-03T12:00:14-0300 | lane2-reset.log | - |
| lane3-verdict-probe | STALE | 0 | 0 | 2026-11-04T01:05:23-0300 | lane3-verdict.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:23-0300) |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-10-20T02:22:33-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-11-03T12:00:17-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-11-02T19:10:49-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-10-20T02:22:35-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-11-03T12:00:20-0300 | panel2-dom-probe.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-11-03T12:00:25-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-11-02T19:42:24-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-11-02T19:42:24-0300 | border-radius-gate-neg.log | - |
| lane-screen-gate | STALE | 0 | 0 | 2026-11-04T01:05:26-0300 | lane-screen-gate.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:26-0300) |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:12-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-04T01:05:27-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-10-30T10:05:12-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-10-30T10:05:12-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-04T01:05:28-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-04T01:05:29-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | PASS | 0 | 0 | 2026-11-04T01:05:30-0300 | youtube-foreign-paint.log | - |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-04T01:05:30-0300 | youtube-foreign-paint-neg.log | - |
| input-path | PASS | 0 | 0 | 2026-11-04T01:05:37-0300 | input-path.log | - |
| red-as-expected-input-path | EXPECTED-RED | 1 | 1 | 2026-11-04T01:05:39-0300 | input-path-neg.log | - |
| exception-hygiene | STALE | 0 | 0 | 2026-11-04T01:05:41-0300 | exception-hygiene.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:41-0300) |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:38-0300 | exception-hygiene-neg.log | - |
| seam-coverage | PASS | 0 | 0 | 2026-11-04T01:05:49-0300 | seam-coverage.log | - |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:52-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-01T13:24:53-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:54-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-01T13:24:55-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:56-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-04T01:05:51-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-04T01:05:52-0300 | external-resume-neg.log | - |
| silence-kill | PASS | 0 | 0 | 2026-11-04T01:05:52-0300 | silence-kill.log | - |
| red-as-expected-silence-kill | EXPECTED-RED | 1 | 1 | 2026-11-04T01:05:53-0300 | silence-kill-neg.log | - |
| rss-trend | PASS | 0 | 0 | 2026-11-04T01:05:54-0300 | rss-trend.log | - |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-02T20:42:22-0300 | rss-trend-neg.log | - |
| death-cause | PASS | 0 | 0 | 2026-11-04T01:05:55-0300 | death-cause.log | - |
| red-as-expected-death-cause | EXPECTED-RED | 1 | 1 | 2026-11-04T01:05:56-0300 | death-cause-neg.log | - |
| caption-seam-dedup | STALE | 0 | 0 | 2026-11-04T01:05:56-0300 | caption-seam-dedup.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:56-0300) |
| red-as-expected-caption-seam-dedup | STALE | 1 | 1 | 2026-11-04T01:05:57-0300 | caption-seam-dedup-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:57-0300) |
| agc-peak-ceiling | STALE | 0 | 0 | 2026-11-04T01:05:58-0300 | agc-peak-ceiling.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:58-0300) |
| red-as-expected-agc-peak-ceiling | STALE | 1 | 1 | 2026-11-04T01:05:59-0300 | agc-peak-ceiling-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:05:59-0300) |
| reveal-park | PASS | 0 | 0 | 2026-11-04T01:06:01-0300 | reveal-park.log | - |
| red-as-expected-reveal-park | EXPECTED-RED | 1 | 1 | 2026-11-04T01:06:06-0300 | reveal-park-neg.log | - |
| youtube-verbatim | PASS | 0 | 0 | 2026-11-04T01:06:08-0300 | youtube-verbatim.log | - |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:11-0300 | youtube-verbatim-neg.log | - |
| code-health | PASS | 0 | 0 | 2026-11-04T01:14:53-0300 | code-health.log | always |
| red-as-expected-code-health | NO-VERDICT | 1 | 1 | 2026-11-04T01:14:54-0300 | code-health-neg.log | token `NEG-ARM PASS` ausente do log |
| undefined-names | STALE | 0 | 0 | 2026-11-04T01:14:56-0300 | undefined-names.log | deps mudaram depois da medicao (medido 2026-11-04T01:14:56-0300) |
| red-as-expected-undefined-names | NO-VERDICT | 1 | 1 | 2026-11-04T01:14:57-0300 | undefined-names-neg.log | token `NEG-ARM PASS` ausente do log |
| battery-heavy-gate | STALE | 0 | 0 | 2026-11-04T01:06:15-0300 | battery-heavy-gate.log | deps mudaram depois da medicao (medido 2026-11-04T01:06:15-0300) |
| red-as-expected-battery-heavy-gate | STALE | 1 | 1 | 2026-11-04T01:06:22-0300 | battery-heavy-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:06:22-0300) |
| task-resolver-gate | STALE | 0 | 0 | 2026-11-04T01:06:23-0300 | task-resolver-gate.log | deps mudaram depois da medicao (medido 2026-11-04T01:06:23-0300) |
| red-as-expected-task-resolver-gate | STALE | 1 | 1 | 2026-11-04T01:06:23-0300 | task-resolver-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:06:23-0300) |
| claims-date | STALE | 0 | 0 | 2026-11-04T01:06:24-0300 | claims-date.log | deps mudaram depois da medicao (medido 2026-11-04T01:06:24-0300) |
| red-as-expected-claims-date | STALE | 1 | 1 | 2026-11-04T01:06:25-0300 | claims-date-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:06:25-0300) |
| stall-under-load | PASS | 0 | 0 | 2026-11-04T01:15:02-0300 | stall-under-load.log | always |
| red-as-expected-stall-under-load | NO-VERDICT | 1 | 1 | 2026-11-04T01:15:04-0300 | stall-under-load-neg.log | token `NEG-ARM PASS` ausente do log |
| paint-live-show | PASS | 0 | 0 | 2026-11-04T01:15:06-0300 | paint-live-show.log | always |
| red-as-expected-paint-live-show | NO-VERDICT | 1 | 1 | 2026-11-04T01:15:10-0300 | paint-live-show-neg.log | token `NEG-ARM PASS` ausente do log |
| panel-paint-first-measure | NO-VERDICT | 0 | 0 | 2026-11-01T14:45:10-0300 | panel-paint-first-measure.log | log alterado depois do registo |
| panel-paint-first | PASS | 0 | 0 | 2026-11-04T01:15:12-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | NO-VERDICT | 1 | 1 | 2026-11-04T01:15:13-0300 | panel-paint-first-neg.log | token `NEG-ARM PASS` ausente do log |
| receipt-provenance | PASS | 0 | 0 | 2026-11-04T01:15:15-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | NO-VERDICT | 1 | 1 | 2026-11-04T01:15:16-0300 | receipt-provenance-neg.log | token `NEG-ARM PASS` ausente do log |
| async-track-fetch | PASS | 0 | 0 | 2026-11-04T01:06:43-0300 | async-track-fetch.log | - |
| red-as-expected-async-track-fetch | EXPECTED-RED | 1 | 1 | 2026-11-04T01:06:51-0300 | async-track-fetch-neg.log | - |
| batch-queue-drain | PASS | 0 | 0 | 2026-11-04T01:06:55-0300 | batch-queue-drain.log | - |
| red-as-expected-batch-queue-drain | EXPECTED-RED | 1 | 1 | 2026-11-04T01:07:06-0300 | batch-queue-drain-neg.log | - |
| hotkey-live-toggle | PASS | 0 | 0 | 2026-11-04T01:07:09-0300 | hotkey-live-toggle.log | - |
| red-as-expected-hotkey-live-toggle | EXPECTED-RED | 1 | 1 | 2026-11-04T01:07:17-0300 | hotkey-live-toggle-neg.log | - |
| loading-placeholder | PASS | 0 | 0 | 2026-11-04T01:07:18-0300 | loading-placeholder.log | - |
| red-as-expected-loading-placeholder | EXPECTED-RED | 1 | 1 | 2026-11-04T01:07:19-0300 | loading-placeholder-neg.log | - |
| youtube-land | STALE | 0 | 0 | 2026-11-04T01:15:22-0300 | youtube-land.log | deps mudaram depois da medicao (medido 2026-11-04T01:15:22-0300) |
| red-as-expected-youtube-land | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:56-0300 | youtube-land-neg.log | - |
| youtube-land-replay | FAIL | 1 | 0 | 2026-11-04T01:15:28-0300 | youtube-land-replay.log | rc=1 != esperado 0 |
| red-as-expected-youtube-land-replay | FAIL | 0 | 1 | 2026-11-04T01:15:31-0300 | youtube-land-replay-neg.log | rc=0 != esperado 1 |
| yt-loop-uia | PASS | 0 | 0 | 2026-11-04T01:07:26-0300 | yt-loop-uia.log | - |
| red-as-expected-yt-loop-uia | EXPECTED-RED | 1 | 1 | 2026-11-04T01:07:27-0300 | yt-loop-uia-neg.log | - |
| yt-target-stale | PASS | 0 | 0 | 2026-11-04T01:07:28-0300 | yt-target-stale.log | - |
| red-as-expected-yt-target-stale | EXPECTED-RED | 1 | 1 | 2026-11-04T01:07:28-0300 | yt-target-stale-neg.log | - |
| owner-screen | PASS | 0 | 0 | 2026-11-04T01:07:34-0300 | owner-screen.log | - |
| red-as-expected-owner-screen | EXPECTED-RED | 1 | 1 | 2026-11-04T01:07:39-0300 | owner-screen-neg.log | - |
| job-object | PASS | 0 | 0 | 2026-11-04T01:07:43-0300 | job-object.log | - |
| red-as-expected-job-object | EXPECTED-RED | 1 | 1 | 2026-11-04T01:07:46-0300 | job-object-neg.log | - |
| emit-pipe-dead | PASS | 0 | 0 | 2026-11-04T01:15:38-0300 | emit-pipe-dead.log | - |
| red-as-expected-emit-pipe-dead | NO-VERDICT | 1 | 1 | 2026-11-04T01:15:39-0300 | emit-pipe-dead-neg.log | token `NEG-ARM PASS` ausente do log |
| state-page-write | NO-VERDICT | 0 | 0 | 2026-11-04T01:07:49-0300 | state-page-write.log | log alterado depois do registo |
| state-page | STALE | 0 | 0 | 2026-11-04T01:07:55-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-04T01:07:55-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-04T01:09:08-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:09:08-0300) |
| battery-wiring | STALE | 0 | 0 | 2026-11-04T01:09:09-0300 | battery-wiring.log | deps mudaram depois da medicao (medido 2026-11-04T01:09:09-0300) |
| red-as-expected-battery-wiring | STALE | 1 | 1 | 2026-11-04T01:09:14-0300 | battery-wiring-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:09:14-0300) |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-04T01:09:15-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:19-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | PASS | 0 | 0 | 2026-11-04T01:09:22-0300 | youtube-1to1.log | always |
| red-as-expected-youtube-1to1 | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:26-0300 | youtube-1to1-neg.log | always |
| youtube-cdp-source | PASS | 0 | 0 | 2026-11-04T01:09:26-0300 | youtube-cdp-source.log | always |
| red-as-expected-youtube-cdp-source | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:27-0300 | youtube-cdp-source-neg.log | always |
| caption-producer | PASS | 0 | 0 | 2026-11-04T01:09:28-0300 | caption-producer.log | always |
| red-as-expected-caption-producer | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:28-0300 | caption-producer-neg.log | always |
| caption-style | PASS | 0 | 0 | 2026-11-04T01:09:30-0300 | caption-style.log | always |
| red-as-expected-caption-style | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:32-0300 | caption-style-neg.log | always |
| hotkey-observed | PASS | 0 | 0 | 2026-11-04T01:09:38-0300 | hotkey-observed.log | always |
| red-as-expected-hotkey-observed | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:43-0300 | hotkey-observed-neg.log | always |
| youtube-reveal | PASS | 0 | 0 | 2026-11-04T01:09:45-0300 | youtube-reveal.log | always |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:46-0300 | youtube-reveal-neg.log | always |
| youtube-rows | PASS | 0 | 0 | 2026-11-04T01:09:48-0300 | youtube-rows.log | always |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:50-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-04T01:09:51-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-04T01:09:51-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-04T01:10:10-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-04T01:10:10-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-04T01:10:11-0300 | bend-laws-model-neg.log | always |
| panel-hidden-at-startup-oracle | PASS | 0 | 0 | 2026-11-04T01:12:29-0300 | panel-hidden-at-startup.log | - |
| red-as-expected-panel-hidden-at-startup | EXPECTED-RED | 1 | 1 | 2026-11-04T01:12:31-0300 | panel-hidden-at-startup-neg.log | - |
| worker-start-wiring | PASS | 0 | 0 | 2026-11-04T01:12:31-0300 | wiring-worker-start.log | - |
| embedded-js-check | PASS | 0 | 0 | 2026-11-04T01:12:32-0300 | embedded-js.log | - |
| lane1-worker-default-arms | PASS | 0 | 0 | 2026-11-04T01:12:33-0300 | lane1-arms.log | - |
| external-subs-stability | PASS | 0 | 0 | 2026-11-03T12:04:03-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | STALE | 0 | 0 | 2026-11-04T01:12:34-0300 | external-caption-chrome-census.log | deps mudaram depois da medicao (medido 2026-11-04T01:12:34-0300) |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-11-03T12:04:04-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-03T12:04:04-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-11-04T01:12:36-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-03T12:04:13-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-11-04T01:12:37-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-11-04T01:12:38-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-11-04T01:12:38-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-10-24T00:19:34-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-10-24T00:19:41-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-10-30T07:18:56-0300 | gitattributes-verify.log | - |
| agents-md-pins | STALE | 0 | 0 | 2026-11-04T01:12:40-0300 | agents-md-pins.log | deps mudaram depois da medicao (medido 2026-11-04T01:12:40-0300) |
| lang-id-oracle | STALE | 0 | 0 | 2026-11-04T01:12:47-0300 | lang-id-oracle.log | deps mudaram depois da medicao (medido 2026-11-04T01:12:47-0300) |
| red-as-expected-lang-id-oracle | STALE | 1 | 1 | 2026-11-04T01:13:01-0300 | lang-id-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:01-0300) |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-02T10:50:13-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-02T10:50:14-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-11-02T19:45:18-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-11-02T19:45:19-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-04T01:13:02-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:02-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-04T01:13:03-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:03-0300) |
| per-app-source-plumbing | STALE | 0 | 0 | 2026-11-04T01:13:03-0300 | per-app-source-plumbing.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:03-0300) |
| red-as-expected-per-app-source-plumbing | STALE | 1 | 1 | 2026-11-04T01:13:04-0300 | per-app-source-plumbing-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:04-0300) |
| redux-live-contract | PASS | 0 | 0 | 2026-11-03T12:04:34-0300 | redux-live-contract.log | - |
| red-as-expected-redux-live-contract | EXPECTED-RED | 1 | 1 | 2026-11-03T12:04:34-0300 | redux-live-contract-neg.log | - |
| word-split-oracle | STALE | 0 | 0 | 2026-11-04T01:13:05-0300 | word-split-oracle.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:05-0300) |
| red-as-expected-word-split-oracle | STALE | 1 | 1 | 2026-11-04T01:13:06-0300 | word-split-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:06-0300) |
| vad-option-probe | STALE | 0 | 0 | 2026-11-04T01:13:13-0300 | vad-option-probe.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:13-0300) |
| red-as-expected-vad-option-probe | STALE | 1 | 1 | 2026-11-04T01:13:13-0300 | vad-option-probe-neg.log | deps mudaram depois da medicao (medido 2026-11-04T01:13:13-0300) |
| youtube-track-wiring | PASS | 0 | 0 | 2026-11-04T01:13:14-0300 | youtube-track-wiring.log | - |
| tap-open-timeout | NO-VERDICT | 0 | 0 | 2026-11-03T12:05:13-0300 | tap-open-timeout.log | log alterado depois do registo |
| ui-stall-oracle | STALE | 0 | 0 | 2026-11-03T12:05:18-0300 | ui-stall-oracle.log | deps mudaram depois da medicao (medido 2026-11-03T12:05:18-0300) |
| mute-audio | NO-VERDICT | 0 | 0 | 2026-11-01T16:18:51-0300 | mute-audio.log | log alterado depois do registo |
| device-silence | NO-VERDICT | 0 | 0 | 2026-11-01T16:21:39-0300 | device-silence.log | log alterado depois do registo |
| red-as-expected-device-silence | NO-VERDICT | 1 | 1 | 2026-11-01T16:22:30-0300 | device-silence-neg.log | log alterado depois do registo |
| console-window-gate | PASS | 0 | 0 | 2026-11-03T12:32:29-0300 | console-window-gate.log | always |
| red-as-expected-console-window-gate | EXPECTED-RED | 1 | 1 | 2026-11-03T12:32:31-0300 | console-window-gate-neg.log | always |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-03T12:32:32-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-03T12:32:33-0300 | owner-audio-gate-neg.log | always |
| worker-providers | STALE | 0 | 0 | 2026-11-03T12:32:33-0300 | worker-providers.log | deps mudaram depois da medicao (medido 2026-11-03T12:32:33-0300) |
| red-as-expected-worker-providers | EXPECTED-RED | 1 | 1 | 2026-11-03T12:32:34-0300 | worker-providers-neg.log | always |
| review-f1f3 | STALE | 0 | 0 | 2026-11-03T12:05:25-0300 | review-f1f3.log | deps mudaram depois da medicao (medido 2026-11-03T12:05:25-0300) |
| review-tapstop | PASS | 0 | 0 | 2026-10-20T02:23:24-0300 | review-tapstop.log | - |
| strip-surface-oracle | STALE | 0 | 0 | 2026-11-03T12:05:45-0300 | strip-surface-oracle.log | deps mudaram depois da medicao (medido 2026-11-03T12:05:45-0300) |
| strip-stats-log-budget | NO-VERDICT | 0 | 0 | 2026-11-01T16:23:31-0300 | strip-stats-log.log | log alterado depois do registo |
| strip-hot-reload | STALE | 0 | 0 | 2026-11-03T12:05:56-0300 | strip-reload.log | deps mudaram depois da medicao (medido 2026-11-03T12:05:56-0300) |
| strip-surface-runtime | NO-VERDICT | 0 | 0 | 2026-11-01T15:15:59-0300 | strip-surface.log | log alterado depois do registo |
| red-as-expected-strip-surface | EXPECTED-RED | 1 | 1 | 2026-11-01T15:15:59-0300 | strip-surface-neg.log | heavy |
| strip-geometry-restore | NO-VERDICT | 0 | 0 | 2026-11-01T13:41:35-0300 | strip-restore.log | log alterado depois do registo |
| strip-stats-wave | NO-VERDICT | 0 | 0 | 2026-11-01T16:24:01-0300 | strip-stats.log | log alterado depois do registo |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-01T16:13:05-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-03T12:32:38-0300 | hotkey-registration.log | always |
| hotkey-delivery | STALE | 0 | 0 | 2026-11-03T12:32:39-0300 | hotkey-delivery.log | deps mudaram depois da medicao (medido 2026-11-03T12:32:39-0300) |
| open-close-stall | STALE | 0 | 0 | 2026-11-03T12:06:00-0300 | open-close-stall.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:00-0300) |
| red-as-expected-open-close-stall | STALE | 1 | 1 | 2026-11-03T12:06:08-0300 | open-close-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:08-0300) |
| autostart-status | STALE | 0 | 0 | 2026-11-03T12:32:40-0300 | autostart-status.log | deps mudaram depois da medicao (medido 2026-11-03T12:32:40-0300) |
| control-verdict-gate-unguard | STALE | 0 | 0 | 2026-11-03T12:06:09-0300 | control-verdict-gate-unguard.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:09-0300) |
| control-history-producer-stamp-nvidia | STALE | 0 | 0 | 2026-11-03T12:06:10-0300 | control-history-producer-stamp-nvidia.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:10-0300) |
| control-redux-flag-neg-arm | STALE | 0 | 0 | 2026-11-03T12:06:10-0300 | control-redux-flag-neg-arm.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:10-0300) |
| control-panel-exit3-neg-arm | NO-VERDICT | 0 | 0 | 2026-11-01T13:43:10-0300 | control-panel-exit3-neg-arm.log | log alterado depois do registo |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-10-20T02:26:52-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | PASS | 0 | 0 | 2026-11-02T19:15:34-0300 | control-panel2-repeat-revert.log | - |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-10-20T02:26:54-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | EXPECTED-RED | 1 | 1 | 2026-11-03T12:06:12-0300 | control-historico-gate-off.log | - |
| search-oracle | STALE | 0 | 0 | 2026-11-03T12:06:12-0300 | search-oracle.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:12-0300) |
| red-as-expected-search-oracle | STALE | 1 | 1 | 2026-11-03T12:06:13-0300 | search-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:13-0300) |
| panel-search-keyboard | STALE | 0 | 0 | 2026-11-03T12:06:15-0300 | panel-search-keyboard.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:15-0300) |
| red-as-expected-panel-search-keyboard | STALE | 1 | 1 | 2026-11-03T12:06:16-0300 | panel-search-keyboard-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:16-0300) |
| fresh-processor-probe | STALE | 0 | 0 | 2026-11-03T12:06:20-0300 | fresh-processor.log | deps mudaram depois da medicao (medido 2026-11-03T12:06:20-0300) |
| stepcache-oracle | PASS | 0 | 0 | 2026-10-21T18:40:17-0300 | stepcache-oracle.log | - |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-03T12:32:46-0300 | _skip-guard.log | always |
| altc-first-caption | NO-VERDICT | 0 | 0 | 2026-11-01T16:24:24-0300 | altc-first-caption.log | log alterado depois do registo |
| altc-gesture | STALE | 0 | 0 | 2026-11-03T12:32:49-0300 | altc-gesture.log | deps mudaram depois da medicao (medido 2026-11-03T12:32:49-0300) |
| headphone-cut | STALE | 0 | 0 | 2026-11-03T12:33:50-0300 | headphone-cut.log | deps mudaram depois da medicao (medido 2026-11-03T12:33:50-0300) |
| incomplete-word | STALE | 0 | 0 | 2026-11-03T12:33:50-0300 | incomplete-word.log | deps mudaram depois da medicao (medido 2026-11-03T12:33:50-0300) |
| ladder-signal | STALE | 0 | 0 | 2026-11-03T12:33:51-0300 | ladder-signal.log | deps mudaram depois da medicao (medido 2026-11-03T12:33:51-0300) |
| launch-as-token | PASS | 0 | 0 | 2026-11-03T12:33:55-0300 | launch-as-token.log | always |
| live-code-freshness | STALE | 0 | 0 | 2026-11-03T12:33:55-0300 | live-code-freshness.log | deps mudaram depois da medicao (medido 2026-11-03T12:33:55-0300) |
| load-shedding | STALE | 0 | 0 | 2026-11-03T12:33:57-0300 | load-shedding.log | deps mudaram depois da medicao (medido 2026-11-03T12:33:57-0300) |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-03T12:33:58-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | STALE | 1 | 1 | 2026-11-03T12:34:04-0300 | altc-gesture-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:04-0300) |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-03T12:34:04-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-03T12:34:05-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | STALE | 1 | 1 | 2026-11-03T12:34:05-0300 | ladder-signal-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:05-0300) |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-03T12:34:07-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-03T12:34:07-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-03T12:34:09-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | STALE | 1 | 1 | 2026-11-03T12:34:30-0300 | load-shedding-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:30-0300) |
| red-as-expected-shell-relaunch | EXPECTED-RED | 1 | 1 | 2026-11-01T13:46:03-0300 | shell-relaunch-neg.log | heavy |
| red-as-expected-word-clock | EXPECTED-RED | 1 | 1 | 2026-11-03T12:34:31-0300 | word-clock-neg.log | always |
| red-as-expected-youtube-monotonic | STALE | 1 | 1 | 2026-11-03T12:34:32-0300 | youtube-monotonic-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:32-0300) |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-03T12:34:32-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | STALE | 1 | 1 | 2026-11-03T12:34:33-0300 | youtube-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:33-0300) |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-03T12:34:33-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NO-VERDICT | 0 | 0 | 2026-11-01T13:46:10-0300 | shell-relaunch.log | log alterado depois do registo |
| word-clock | STALE | 0 | 0 | 2026-11-03T12:34:34-0300 | word-clock.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:34-0300) |
| youtube-monotonic | STALE | 0 | 0 | 2026-11-03T12:34:35-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:35-0300) |
| youtube-sotto-drift | STALE | 0 | 0 | 2026-11-03T12:34:36-0300 | youtube-sotto-drift.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:36-0300) |
| youtube-switch | STALE | 0 | 0 | 2026-11-03T12:34:37-0300 | youtube-switch.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:37-0300) |
| yt-no-dub | STALE | 0 | 0 | 2026-11-03T12:34:37-0300 | yt-no-dub.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:37-0300) |
| stale-display | STALE | 0 | 0 | 2026-11-03T12:34:37-0300 | stale-display.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:37-0300) |
| red-as-expected-stale-display | STALE | 1 | 1 | 2026-11-03T12:34:38-0300 | stale-display-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:38-0300) |
| battery-class | STALE | 0 | 0 | 2026-11-03T12:34:39-0300 | battery-class.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:39-0300) |
| red-as-expected-battery-class | STALE | 1 | 1 | 2026-11-03T12:34:40-0300 | battery-class-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:40-0300) |
| live-queue | STALE | 0 | 0 | 2026-11-03T12:34:41-0300 | live-queue.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:41-0300) |
| red-as-expected-live-queue | STALE | 1 | 1 | 2026-11-03T12:34:43-0300 | live-queue-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:43-0300) |
| flat-endpoint | PASS | 0 | 0 | 2026-11-03T12:34:44-0300 | flat-endpoint.log | always |
| tap-silent-desktop | STALE | 0 | 0 | 2026-11-03T12:34:45-0300 | tap-silent-desktop.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:45-0300) |
| red-as-expected-tap-silent-desktop | STALE | 1 | 1 | 2026-11-03T12:34:45-0300 | tap-silent-desktop-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:34:45-0300) |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
