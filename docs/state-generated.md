# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=233 · PASS=126 · EXPECTED-RED=79 · FAIL=7 · STALE=9 · NO-VERDICT=12 · NOT RUN=0

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-03T12:00:08-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-10-30T04:23:01-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | PASS | 0 | 0 | 2026-11-03T12:00:08-0300 | pycompile-worker.log | - |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-10-20T02:22:19-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-11-03T12:00:09-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-11-03T12:00:09-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-11-03T12:00:09-0300 | oracle-historico-vs-redux.log | - |
| redux-transcript-path | PASS | 0 | 0 | 2026-11-03T12:00:10-0300 | redux-transcript-path.log | - |
| caption-cumulative | PASS | 0 | 0 | 2026-11-03T12:27:53-0300 | oracle-caption-cumulative.log | - |
| red-as-expected-caption-cumulative | EXPECTED-RED | 1 | 1 | 2026-11-03T12:27:53-0300 | caption-cumulative-neg.log | - |
| red-as-expected-redux-transcript-path | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:12-0300 | redux-transcript-path-neg.log | - |
| control-verdict-gate-drop-redux-live | PASS | 0 | 0 | 2026-11-03T12:00:12-0300 | control-verdict-gate-drop-redux-live.log | - |
| history-producer-gate | PASS | 0 | 0 | 2026-11-03T12:00:13-0300 | gate-history-producer.log | - |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-11-03T12:00:13-0300 | gate-panel-state-guard.log | - |
| verdict-gate | PASS | 0 | 0 | 2026-11-03T12:00:14-0300 | gate-verdict.log | - |
| lane2-reset-probe | PASS | 0 | 0 | 2026-11-03T12:00:14-0300 | lane2-reset.log | - |
| lane3-verdict-probe | PASS | 0 | 0 | 2026-11-03T12:00:16-0300 | lane3-verdict.log | - |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-10-20T02:22:33-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-11-03T12:00:17-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-11-02T19:10:49-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-10-20T02:22:35-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-11-03T12:00:20-0300 | panel2-dom-probe.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-11-03T12:00:25-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-11-02T19:42:24-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-11-02T19:42:24-0300 | border-radius-gate-neg.log | - |
| lane-screen-gate | PASS | 0 | 0 | 2026-11-03T12:00:26-0300 | lane-screen-gate.log | - |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:12-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-03T12:00:27-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-10-30T10:05:12-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-10-30T10:05:12-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-03T12:28:00-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:00-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | PASS | 0 | 0 | 2026-11-03T12:28:01-0300 | youtube-foreign-paint.log | - |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:02-0300 | youtube-foreign-paint-neg.log | - |
| input-path | PASS | 0 | 0 | 2026-11-03T12:00:33-0300 | input-path.log | - |
| red-as-expected-input-path | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:34-0300 | input-path-neg.log | - |
| exception-hygiene | PASS | 0 | 0 | 2026-11-03T12:00:35-0300 | exception-hygiene.log | - |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:38-0300 | exception-hygiene-neg.log | - |
| seam-coverage | PASS | 0 | 0 | 2026-11-03T12:00:43-0300 | seam-coverage.log | - |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:52-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-01T13:24:53-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:54-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-01T13:24:55-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:56-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-03T12:00:44-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:45-0300 | external-resume-neg.log | - |
| silence-kill | PASS | 0 | 0 | 2026-11-03T12:00:45-0300 | silence-kill.log | - |
| red-as-expected-silence-kill | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:46-0300 | silence-kill-neg.log | - |
| rss-trend | PASS | 0 | 0 | 2026-11-03T12:00:46-0300 | rss-trend.log | - |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-02T20:42:22-0300 | rss-trend-neg.log | - |
| death-cause | PASS | 0 | 0 | 2026-11-03T12:00:47-0300 | death-cause.log | - |
| red-as-expected-death-cause | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:48-0300 | death-cause-neg.log | - |
| caption-seam-dedup | PASS | 0 | 0 | 2026-11-03T12:00:48-0300 | caption-seam-dedup.log | - |
| red-as-expected-caption-seam-dedup | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:49-0300 | caption-seam-dedup-neg.log | - |
| agc-peak-ceiling | PASS | 0 | 0 | 2026-11-03T12:00:49-0300 | agc-peak-ceiling.log | - |
| red-as-expected-agc-peak-ceiling | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:50-0300 | agc-peak-ceiling-neg.log | - |
| reveal-park | PASS | 0 | 0 | 2026-11-03T12:00:52-0300 | reveal-park.log | - |
| red-as-expected-reveal-park | EXPECTED-RED | 1 | 1 | 2026-11-03T12:00:57-0300 | reveal-park-neg.log | - |
| youtube-verbatim | PASS | 0 | 0 | 2026-11-03T12:28:10-0300 | youtube-verbatim.log | - |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:11-0300 | youtube-verbatim-neg.log | - |
| code-health | PASS | 0 | 0 | 2026-11-03T12:28:12-0300 | code-health.log | always |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:13-0300 | code-health-neg.log | always |
| undefined-names | PASS | 0 | 0 | 2026-11-03T12:28:14-0300 | undefined-names.log | always |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:14-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | PASS | 0 | 0 | 2026-11-03T12:01:01-0300 | battery-heavy-gate.log | - |
| red-as-expected-battery-heavy-gate | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:06-0300 | battery-heavy-gate-neg.log | - |
| task-resolver-gate | PASS | 0 | 0 | 2026-11-03T12:01:07-0300 | task-resolver-gate.log | - |
| red-as-expected-task-resolver-gate | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:07-0300 | task-resolver-gate-neg.log | - |
| claims-date | PASS | 0 | 0 | 2026-11-03T12:01:07-0300 | claims-date.log | - |
| red-as-expected-claims-date | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:08-0300 | claims-date-neg.log | - |
| stall-under-load | PASS | 0 | 0 | 2026-11-03T12:28:17-0300 | stall-under-load.log | always |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:17-0300 | stall-under-load-neg.log | always |
| paint-live-show | PASS | 0 | 0 | 2026-11-03T12:28:18-0300 | paint-live-show.log | always |
| red-as-expected-paint-live-show | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:20-0300 | paint-live-show-neg.log | always |
| panel-paint-first-measure | NO-VERDICT | 0 | 0 | 2026-11-01T14:45:10-0300 | panel-paint-first-measure.log | log alterado depois do registo |
| panel-paint-first | PASS | 0 | 0 | 2026-11-03T12:28:21-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:22-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-03T12:28:22-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-03T12:28:23-0300 | receipt-provenance-neg.log | always |
| async-track-fetch | PASS | 0 | 0 | 2026-11-03T12:01:23-0300 | async-track-fetch.log | - |
| red-as-expected-async-track-fetch | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:32-0300 | async-track-fetch-neg.log | - |
| batch-queue-drain | PASS | 0 | 0 | 2026-11-03T12:01:36-0300 | batch-queue-drain.log | - |
| red-as-expected-batch-queue-drain | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:46-0300 | batch-queue-drain-neg.log | - |
| hotkey-live-toggle | PASS | 0 | 0 | 2026-11-03T12:01:48-0300 | hotkey-live-toggle.log | - |
| red-as-expected-hotkey-live-toggle | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:53-0300 | hotkey-live-toggle-neg.log | - |
| loading-placeholder | PASS | 0 | 0 | 2026-11-03T12:01:54-0300 | loading-placeholder.log | - |
| red-as-expected-loading-placeholder | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:55-0300 | loading-placeholder-neg.log | - |
| youtube-land | STALE | 0 | 0 | 2026-11-03T12:28:26-0300 | youtube-land.log | deps mudaram depois da medicao (medido 2026-11-03T12:28:26-0300) |
| red-as-expected-youtube-land | EXPECTED-RED | 1 | 1 | 2026-11-03T12:01:56-0300 | youtube-land-neg.log | - |
| youtube-land-replay | PASS | 0 | 0 | 2026-11-03T12:01:59-0300 | youtube-land-replay.log | - |
| red-as-expected-youtube-land-replay | EXPECTED-RED | 1 | 1 | 2026-11-03T12:02:02-0300 | youtube-land-replay-neg.log | - |
| yt-loop-uia | PASS | 0 | 0 | 2026-11-03T12:02:02-0300 | yt-loop-uia.log | - |
| red-as-expected-yt-loop-uia | EXPECTED-RED | 1 | 1 | 2026-11-03T12:02:03-0300 | yt-loop-uia-neg.log | - |
| state-page-write | NO-VERDICT | 0 | 0 | 2026-11-03T12:02:05-0300 | state-page-write.log | log alterado depois do registo |
| state-page | STALE | 0 | 0 | 2026-11-03T12:02:10-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-03T12:02:10-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-03T12:03:08-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:03:08-0300) |
| battery-wiring | PASS | 0 | 0 | 2026-11-03T12:03:09-0300 | battery-wiring.log | - |
| red-as-expected-battery-wiring | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:11-0300 | battery-wiring-neg.log | - |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-03T12:03:12-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:14-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | PASS | 0 | 0 | 2026-11-03T12:03:16-0300 | youtube-1to1.log | always |
| red-as-expected-youtube-1to1 | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:18-0300 | youtube-1to1-neg.log | always |
| youtube-cdp-source | PASS | 0 | 0 | 2026-11-03T12:03:19-0300 | youtube-cdp-source.log | always |
| red-as-expected-youtube-cdp-source | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:19-0300 | youtube-cdp-source-neg.log | always |
| caption-producer | PASS | 0 | 0 | 2026-11-03T12:03:20-0300 | caption-producer.log | always |
| red-as-expected-caption-producer | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:20-0300 | caption-producer-neg.log | always |
| caption-style | PASS | 0 | 0 | 2026-11-03T12:03:21-0300 | caption-style.log | always |
| red-as-expected-caption-style | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:23-0300 | caption-style-neg.log | always |
| hotkey-observed | PASS | 0 | 0 | 2026-11-03T12:03:29-0300 | hotkey-observed.log | always |
| red-as-expected-hotkey-observed | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:33-0300 | hotkey-observed-neg.log | always |
| youtube-reveal | PASS | 0 | 0 | 2026-11-03T12:03:34-0300 | youtube-reveal.log | always |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:35-0300 | youtube-reveal-neg.log | always |
| youtube-rows | PASS | 0 | 0 | 2026-11-03T12:03:36-0300 | youtube-rows.log | always |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:37-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-03T12:03:37-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:37-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-03T12:03:50-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-03T12:03:51-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-03T12:03:51-0300 | bend-laws-model-neg.log | always |
| panel-hidden-at-startup-oracle | FAIL | 1 | 0 | 2026-11-03T12:04:00-0300 | panel-hidden-at-startup.log | rc=1 != esperado 0 |
| red-as-expected-panel-hidden-at-startup | STALE | 1 | 1 | 2026-11-03T12:04:01-0300 | panel-hidden-at-startup-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:04:01-0300) |
| worker-start-wiring | PASS | 0 | 0 | 2026-11-03T12:04:01-0300 | wiring-worker-start.log | - |
| embedded-js-check | PASS | 0 | 0 | 2026-11-03T12:04:02-0300 | embedded-js.log | - |
| lane1-worker-default-arms | PASS | 0 | 0 | 2026-11-03T12:04:02-0300 | lane1-arms.log | - |
| external-subs-stability | PASS | 0 | 0 | 2026-11-03T12:04:03-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | STALE | 0 | 0 | 2026-11-03T12:04:03-0300 | external-caption-chrome-census.log | deps mudaram depois da medicao (medido 2026-11-03T12:04:03-0300) |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-11-03T12:04:04-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-03T12:04:04-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-11-03T12:04:12-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-03T12:04:13-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-11-03T12:04:13-0300 | yt-player-track.log | - |
| yt-mirror-align | FAIL | 1 | 0 | 2026-11-03T12:04:14-0300 | yt-mirror-align.log | rc=1 != esperado 0 |
| red-as-expected-yt-mirror-align | FAIL | 0 | 1 | 2026-11-03T12:04:14-0300 | yt-mirror-align-neg.log | rc=0 != esperado 1 |
| shots-delta-oracle | PASS | 0 | 0 | 2026-10-24T00:19:34-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-10-24T00:19:41-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-10-30T07:18:56-0300 | gitattributes-verify.log | - |
| agents-md-pins | PASS | 0 | 0 | 2026-11-03T12:04:15-0300 | agents-md-pins.log | - |
| lang-id-oracle | PASS | 0 | 0 | 2026-11-03T12:04:20-0300 | lang-id-oracle.log | - |
| red-as-expected-lang-id-oracle | EXPECTED-RED | 1 | 1 | 2026-11-03T12:04:31-0300 | lang-id-oracle-neg.log | - |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-02T10:50:13-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-02T10:50:14-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-11-02T19:45:18-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-11-02T19:45:19-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | PASS | 0 | 0 | 2026-11-03T12:04:32-0300 | panel-flash-contradiction.log | - |
| red-as-expected-panel-flash-contradiction | EXPECTED-RED | 1 | 1 | 2026-11-03T12:04:33-0300 | panel-flash-contradiction-neg.log | - |
| per-app-source-plumbing | PASS | 0 | 0 | 2026-11-03T12:04:33-0300 | per-app-source-plumbing.log | - |
| red-as-expected-per-app-source-plumbing | EXPECTED-RED | 1 | 1 | 2026-11-03T12:04:34-0300 | per-app-source-plumbing-neg.log | - |
| redux-live-contract | PASS | 0 | 0 | 2026-11-03T12:04:34-0300 | redux-live-contract.log | - |
| red-as-expected-redux-live-contract | EXPECTED-RED | 1 | 1 | 2026-11-03T12:04:34-0300 | redux-live-contract-neg.log | - |
| word-split-oracle | PASS | 0 | 0 | 2026-11-03T12:04:35-0300 | word-split-oracle.log | - |
| red-as-expected-word-split-oracle | EXPECTED-RED | 1 | 1 | 2026-11-03T12:04:35-0300 | word-split-oracle-neg.log | - |
| vad-option-probe | PASS | 0 | 0 | 2026-11-03T12:04:38-0300 | vad-option-probe.log | - |
| red-as-expected-vad-option-probe | EXPECTED-RED | 1 | 1 | 2026-11-03T12:04:38-0300 | vad-option-probe-neg.log | - |
| youtube-track-wiring | FAIL | 1 | 0 | 2026-11-03T12:04:40-0300 | youtube-track-wiring.log | rc=1 != esperado 0 |
| tap-open-timeout | PASS | 0 | 0 | 2026-11-03T12:05:13-0300 | tap-open-timeout.log | - |
| ui-stall-oracle | PASS | 0 | 0 | 2026-11-03T12:05:18-0300 | ui-stall-oracle.log | - |
| mute-audio | NO-VERDICT | 0 | 0 | 2026-11-01T16:18:51-0300 | mute-audio.log | log alterado depois do registo |
| device-silence | NO-VERDICT | 0 | 0 | 2026-11-01T16:21:39-0300 | device-silence.log | log alterado depois do registo |
| red-as-expected-device-silence | NO-VERDICT | 1 | 1 | 2026-11-01T16:22:30-0300 | device-silence-neg.log | log alterado depois do registo |
| console-window-gate | PASS | 0 | 0 | 2026-11-03T12:05:20-0300 | console-window-gate.log | always |
| red-as-expected-console-window-gate | EXPECTED-RED | 1 | 1 | 2026-11-03T12:05:22-0300 | console-window-gate-neg.log | always |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-03T12:05:23-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-03T12:05:23-0300 | owner-audio-gate-neg.log | always |
| worker-providers | PASS | 0 | 0 | 2026-11-03T12:05:24-0300 | worker-providers.log | always |
| red-as-expected-worker-providers | EXPECTED-RED | 1 | 1 | 2026-11-03T12:05:24-0300 | worker-providers-neg.log | always |
| review-f1f3 | PASS | 0 | 0 | 2026-11-03T12:05:25-0300 | review-f1f3.log | - |
| review-tapstop | PASS | 0 | 0 | 2026-10-20T02:23:24-0300 | review-tapstop.log | - |
| strip-surface-oracle | PASS | 0 | 0 | 2026-11-03T12:05:45-0300 | strip-surface-oracle.log | - |
| strip-stats-log-budget | NO-VERDICT | 0 | 0 | 2026-11-01T16:23:31-0300 | strip-stats-log.log | log alterado depois do registo |
| strip-hot-reload | PASS | 0 | 0 | 2026-11-03T12:05:56-0300 | strip-reload.log | - |
| strip-surface-runtime | NO-VERDICT | 0 | 0 | 2026-11-01T15:15:59-0300 | strip-surface.log | log alterado depois do registo |
| red-as-expected-strip-surface | EXPECTED-RED | 1 | 1 | 2026-11-01T15:15:59-0300 | strip-surface-neg.log | heavy |
| strip-geometry-restore | NO-VERDICT | 0 | 0 | 2026-11-01T13:41:35-0300 | strip-restore.log | log alterado depois do registo |
| strip-stats-wave | NO-VERDICT | 0 | 0 | 2026-11-01T16:24:01-0300 | strip-stats.log | log alterado depois do registo |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-01T16:13:05-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-03T12:05:58-0300 | hotkey-registration.log | always |
| hotkey-delivery | PASS | 0 | 0 | 2026-11-03T12:05:59-0300 | hotkey-delivery.log | always |
| open-close-stall | PASS | 0 | 0 | 2026-11-03T12:06:00-0300 | open-close-stall.log | - |
| red-as-expected-open-close-stall | EXPECTED-RED | 1 | 1 | 2026-11-03T12:06:08-0300 | open-close-stall-neg.log | - |
| autostart-status | PASS | 0 | 0 | 2026-11-03T12:06:09-0300 | autostart-status.log | always |
| control-verdict-gate-unguard | PASS | 0 | 0 | 2026-11-03T12:06:09-0300 | control-verdict-gate-unguard.log | - |
| control-history-producer-stamp-nvidia | PASS | 0 | 0 | 2026-11-03T12:06:10-0300 | control-history-producer-stamp-nvidia.log | - |
| control-redux-flag-neg-arm | PASS | 0 | 0 | 2026-11-03T12:06:10-0300 | control-redux-flag-neg-arm.log | - |
| control-panel-exit3-neg-arm | NO-VERDICT | 0 | 0 | 2026-11-01T13:43:10-0300 | control-panel-exit3-neg-arm.log | log alterado depois do registo |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-10-20T02:26:52-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | PASS | 0 | 0 | 2026-11-02T19:15:34-0300 | control-panel2-repeat-revert.log | - |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-10-20T02:26:54-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | EXPECTED-RED | 1 | 1 | 2026-11-03T12:06:12-0300 | control-historico-gate-off.log | - |
| search-oracle | PASS | 0 | 0 | 2026-11-03T12:06:12-0300 | search-oracle.log | - |
| red-as-expected-search-oracle | EXPECTED-RED | 1 | 1 | 2026-11-03T12:06:13-0300 | search-oracle-neg.log | - |
| panel-search-keyboard | PASS | 0 | 0 | 2026-11-03T12:06:15-0300 | panel-search-keyboard.log | - |
| red-as-expected-panel-search-keyboard | EXPECTED-RED | 1 | 1 | 2026-11-03T12:06:16-0300 | panel-search-keyboard-neg.log | - |
| fresh-processor-probe | PASS | 0 | 0 | 2026-11-03T12:06:20-0300 | fresh-processor.log | - |
| stepcache-oracle | PASS | 0 | 0 | 2026-10-21T18:40:17-0300 | stepcache-oracle.log | - |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-03T12:06:20-0300 | _skip-guard.log | always |
| altc-first-caption | NO-VERDICT | 0 | 0 | 2026-11-01T16:24:24-0300 | altc-first-caption.log | log alterado depois do registo |
| altc-gesture | PASS | 0 | 0 | 2026-11-03T12:06:23-0300 | altc-gesture.log | always |
| headphone-cut | STALE | 0 | 0 | 2026-11-03T12:07:24-0300 | headphone-cut.log | deps mudaram depois da medicao (medido 2026-11-03T12:07:24-0300) |
| incomplete-word | PASS | 0 | 0 | 2026-11-03T12:07:24-0300 | incomplete-word.log | always |
| ladder-signal | PASS | 0 | 0 | 2026-11-03T12:07:25-0300 | ladder-signal.log | always |
| launch-as-token | PASS | 0 | 0 | 2026-11-03T12:07:28-0300 | launch-as-token.log | always |
| live-code-freshness | PASS | 0 | 0 | 2026-11-03T12:07:29-0300 | live-code-freshness.log | always |
| load-shedding | PASS | 0 | 0 | 2026-11-03T12:07:31-0300 | load-shedding.log | always |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-03T12:07:31-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | EXPECTED-RED | 1 | 1 | 2026-11-03T12:07:36-0300 | altc-gesture-neg.log | always |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-03T12:07:36-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-03T12:07:36-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | EXPECTED-RED | 1 | 1 | 2026-11-03T12:07:38-0300 | ladder-signal-neg.log | always |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-03T12:07:39-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-03T12:07:40-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-03T12:07:42-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | EXPECTED-RED | 1 | 1 | 2026-11-03T12:08:00-0300 | load-shedding-neg.log | always |
| red-as-expected-shell-relaunch | EXPECTED-RED | 1 | 1 | 2026-11-01T13:46:03-0300 | shell-relaunch-neg.log | heavy |
| red-as-expected-word-clock | EXPECTED-RED | 1 | 1 | 2026-11-03T12:08:01-0300 | word-clock-neg.log | always |
| red-as-expected-youtube-monotonic | STALE | 1 | 1 | 2026-11-03T12:08:02-0300 | youtube-monotonic-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:08:02-0300) |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-03T12:08:02-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | STALE | 1 | 1 | 2026-11-03T12:08:03-0300 | youtube-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-03T12:08:03-0300) |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-03T12:08:03-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NO-VERDICT | 0 | 0 | 2026-11-01T13:46:10-0300 | shell-relaunch.log | log alterado depois do registo |
| word-clock | PASS | 0 | 0 | 2026-11-03T12:08:04-0300 | word-clock.log | always |
| youtube-monotonic | STALE | 0 | 0 | 2026-11-03T12:08:05-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-11-03T12:08:05-0300) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-03T12:08:05-0300 | youtube-sotto-drift.log | always |
| youtube-switch | FAIL | 1 | 0 | 2026-11-03T12:08:06-0300 | youtube-switch.log | rc=1 != esperado 0 |
| yt-no-dub | PASS | 0 | 0 | 2026-11-03T12:08:06-0300 | yt-no-dub.log | always |
| stale-display | FAIL | 1 | 0 | 2026-11-03T12:08:06-0300 | stale-display.log | rc=1 != esperado 0 |
| red-as-expected-stale-display | FAIL | 2 | 1 | 2026-11-03T12:08:07-0300 | stale-display-neg.log | rc=2 != esperado 1 |
| battery-class | PASS | 0 | 0 | 2026-11-03T12:08:07-0300 | battery-class.log | always |
| red-as-expected-battery-class | EXPECTED-RED | 1 | 1 | 2026-11-03T12:08:08-0300 | battery-class-neg.log | always |
| live-queue | PASS | 0 | 0 | 2026-11-03T12:08:08-0300 | live-queue.log | always |
| red-as-expected-live-queue | EXPECTED-RED | 1 | 1 | 2026-11-03T12:08:08-0300 | live-queue-neg.log | always |
| flat-endpoint | PASS | 0 | 0 | 2026-11-03T12:08:09-0300 | flat-endpoint.log | always |
| tap-silent-desktop | PASS | 0 | 0 | 2026-11-03T12:08:09-0300 | tap-silent-desktop.log | always |
| red-as-expected-tap-silent-desktop | EXPECTED-RED | 1 | 1 | 2026-11-03T12:08:10-0300 | tap-silent-desktop-neg.log | always |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
