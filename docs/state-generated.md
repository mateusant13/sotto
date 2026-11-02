# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=187 · PASS=82 · EXPECTED-RED=51 · FAIL=0 · STALE=42 · NO-VERDICT=12 · NOT RUN=0

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-02T13:34:04-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-10-30T04:23:01-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | PASS | 0 | 0 | 2026-11-01T13:23:14-0300 | pycompile-worker.log | - |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-10-20T02:22:19-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-10-30T01:55:01-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-11-02T01:27:11-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-10-30T01:55:02-0300 | oracle-historico-vs-redux.log | - |
| redux-transcript-path | PASS | 0 | 0 | 2026-11-02T13:34:11-0300 | redux-transcript-path.log | - |
| red-as-expected-redux-transcript-path | EXPECTED-RED | 1 | 1 | 2026-11-02T13:34:13-0300 | redux-transcript-path-neg.log | - |
| control-verdict-gate-drop-redux-live | PASS | 0 | 0 | 2026-11-01T13:23:17-0300 | control-verdict-gate-drop-redux-live.log | - |
| history-producer-gate | PASS | 0 | 0 | 2026-11-01T13:23:18-0300 | gate-history-producer.log | - |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-11-02T01:27:13-0300 | gate-panel-state-guard.log | - |
| verdict-gate | PASS | 0 | 0 | 2026-11-01T13:23:19-0300 | gate-verdict.log | - |
| lane2-reset-probe | PASS | 0 | 0 | 2026-11-02T01:27:14-0300 | lane2-reset.log | - |
| lane3-verdict-probe | PASS | 0 | 0 | 2026-11-01T13:23:47-0300 | lane3-verdict.log | - |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-10-20T02:22:33-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-11-02T01:27:15-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-11-02T01:27:16-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-10-20T02:22:35-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-11-02T01:27:20-0300 | panel2-dom-probe.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-11-02T01:27:25-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-11-01T13:24:09-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:09-0300 | border-radius-gate-neg.log | - |
| lane-screen-gate | PASS | 0 | 0 | 2026-11-02T13:34:27-0300 | lane-screen-gate.log | - |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:12-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-02T13:34:31-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-10-30T10:05:12-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-10-30T10:05:12-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-02T13:34:34-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-02T13:34:36-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | PASS | 0 | 0 | 2026-11-02T13:34:38-0300 | youtube-foreign-paint.log | - |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-02T13:34:40-0300 | youtube-foreign-paint-neg.log | - |
| input-path | PASS | 0 | 0 | 2026-11-02T13:34:56-0300 | input-path.log | - |
| red-as-expected-input-path | EXPECTED-RED | 1 | 1 | 2026-11-02T13:35:00-0300 | input-path-neg.log | - |
| exception-hygiene | PASS | 0 | 0 | 2026-11-02T13:35:03-0300 | exception-hygiene.log | - |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-01T11:02:36-0300 | exception-hygiene-neg.log | - |
| seam-coverage | PASS | 0 | 0 | 2026-11-02T13:35:24-0300 | seam-coverage.log | - |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:52-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-01T13:24:53-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:54-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-01T13:24:55-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-01T13:24:56-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-02T13:35:32-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-02T13:35:34-0300 | external-resume-neg.log | - |
| code-health | PASS | 0 | 0 | 2026-11-02T13:35:37-0300 | code-health.log | always |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-02T13:35:39-0300 | code-health-neg.log | always |
| undefined-names | PASS | 0 | 0 | 2026-11-02T13:35:42-0300 | undefined-names.log | always |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-02T13:35:43-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | PASS | 0 | 0 | 2026-11-02T10:54:09-0300 | battery-heavy-gate.log | - |
| red-as-expected-battery-heavy-gate | EXPECTED-RED | 1 | 1 | 2026-11-02T10:54:20-0300 | battery-heavy-gate-neg.log | - |
| task-resolver-gate | PASS | 0 | 0 | 2026-11-02T13:35:47-0300 | task-resolver-gate.log | - |
| red-as-expected-task-resolver-gate | EXPECTED-RED | 1 | 1 | 2026-11-02T13:35:49-0300 | task-resolver-gate-neg.log | - |
| claims-date | PASS | 0 | 0 | 2026-11-02T13:35:50-0300 | claims-date.log | - |
| red-as-expected-claims-date | EXPECTED-RED | 1 | 1 | 2026-11-02T13:35:52-0300 | claims-date-neg.log | - |
| stall-under-load | PASS | 0 | 0 | 2026-11-02T13:35:55-0300 | stall-under-load.log | always |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-02T13:35:58-0300 | stall-under-load-neg.log | always |
| paint-live-show | PASS | 0 | 0 | 2026-11-02T13:36:01-0300 | paint-live-show.log | always |
| red-as-expected-paint-live-show | EXPECTED-RED | 1 | 1 | 2026-11-02T13:36:04-0300 | paint-live-show-neg.log | always |
| panel-paint-first-measure | NO-VERDICT | 0 | 0 | 2026-11-01T14:45:10-0300 | panel-paint-first-measure.log | log alterado depois do registo |
| panel-paint-first | PASS | 0 | 0 | 2026-11-02T13:36:07-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-02T13:36:10-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-02T13:36:12-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-02T13:36:14-0300 | receipt-provenance-neg.log | always |
| state-page-write | NO-VERDICT | 0 | 0 | 2026-11-02T13:24:46-0300 | state-page-write.log | log alterado depois do registo |
| state-page | STALE | 0 | 0 | 2026-11-02T13:24:53-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-02T13:24:53-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-02T13:26:56-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:26:56-0300) |
| battery-wiring | PASS | 0 | 0 | 2026-11-02T10:58:02-0300 | battery-wiring.log | - |
| red-as-expected-battery-wiring | EXPECTED-RED | 1 | 1 | 2026-11-02T10:58:04-0300 | battery-wiring-neg.log | - |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-02T13:26:58-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-02T13:27:02-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | STALE | 0 | 0 | 2026-11-02T13:27:04-0300 | youtube-1to1.log | deps mudaram depois da medicao (medido 2026-11-02T13:27:04-0300) |
| red-as-expected-youtube-1to1 | STALE | 1 | 1 | 2026-11-02T13:27:08-0300 | youtube-1to1-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:27:08-0300) |
| youtube-reveal | STALE | 0 | 0 | 2026-11-02T13:27:09-0300 | youtube-reveal.log | deps mudaram depois da medicao (medido 2026-11-02T13:27:09-0300) |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-02T13:27:10-0300 | youtube-reveal-neg.log | always |
| youtube-rows | STALE | 0 | 0 | 2026-11-02T13:27:13-0300 | youtube-rows.log | deps mudaram depois da medicao (medido 2026-11-02T13:27:13-0300) |
| red-as-expected-youtube-rows | EXPECTED-RED | 1 | 1 | 2026-11-02T13:27:16-0300 | youtube-rows-neg.log | always |
| youtube-drift | PASS | 0 | 0 | 2026-11-02T13:27:16-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-02T13:27:17-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-02T13:27:47-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-02T13:27:48-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-02T13:27:49-0300 | bend-laws-model-neg.log | always |
| panel-hidden-at-startup-oracle | STALE | 0 | 0 | 2026-11-02T13:28:00-0300 | panel-hidden-at-startup.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:00-0300) |
| red-as-expected-panel-hidden-at-startup | STALE | 1 | 1 | 2026-11-02T13:28:02-0300 | panel-hidden-at-startup-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:02-0300) |
| worker-start-wiring | STALE | 0 | 0 | 2026-11-02T13:28:03-0300 | wiring-worker-start.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:03-0300) |
| embedded-js-check | STALE | 0 | 0 | 2026-11-02T13:28:04-0300 | embedded-js.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:04-0300) |
| lane1-worker-default-arms | STALE | 0 | 0 | 2026-11-02T13:28:05-0300 | lane1-arms.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:05-0300) |
| external-subs-stability | PASS | 0 | 0 | 2026-10-20T02:35:09-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | PASS | 0 | 0 | 2026-11-02T00:57:13-0300 | external-caption-chrome-census.log | - |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-10-24T00:15:07-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-10-24T00:15:08-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-10-30T10:13:23-0300 | youtube-captions.log | - |
| caption-native-wrap | PASS | 0 | 0 | 2026-11-01T11:05:49-0300 | caption-native-wrap.log | - |
| yt-player-track | PASS | 0 | 0 | 2026-10-30T10:13:24-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-10-30T10:13:24-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-10-30T10:13:25-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-10-24T00:19:34-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-10-24T00:19:41-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-10-30T07:18:56-0300 | gitattributes-verify.log | - |
| agents-md-pins | STALE | 0 | 0 | 2026-11-02T11:10:15-0300 | agents-md-pins.log | deps mudaram depois da medicao (medido 2026-11-02T11:10:15-0300) |
| lang-id-oracle | PASS | 0 | 0 | 2026-11-02T10:50:02-0300 | lang-id-oracle.log | - |
| red-as-expected-lang-id-oracle | EXPECTED-RED | 1 | 1 | 2026-11-02T10:50:13-0300 | lang-id-oracle-neg.log | - |
| model-spec-oracle | PASS | 0 | 0 | 2026-11-02T10:50:13-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-11-02T10:50:14-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-10-30T10:06:22-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-10-30T10:06:24-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-02T11:10:17-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-02T11:10:17-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-02T11:10:18-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-02T11:10:18-0300) |
| per-app-source-plumbing | PASS | 0 | 0 | 2026-11-01T13:29:56-0300 | per-app-source-plumbing.log | - |
| red-as-expected-per-app-source-plumbing | EXPECTED-RED | 1 | 1 | 2026-11-01T13:29:56-0300 | per-app-source-plumbing-neg.log | - |
| redux-live-contract | PASS | 0 | 0 | 2026-11-02T01:29:43-0300 | redux-live-contract.log | - |
| red-as-expected-redux-live-contract | EXPECTED-RED | 1 | 1 | 2026-11-02T01:29:44-0300 | redux-live-contract-neg.log | - |
| word-split-oracle | PASS | 0 | 0 | 2026-11-02T10:50:16-0300 | word-split-oracle.log | - |
| red-as-expected-word-split-oracle | EXPECTED-RED | 1 | 1 | 2026-11-02T10:50:17-0300 | word-split-oracle-neg.log | - |
| vad-option-probe | PASS | 0 | 0 | 2026-11-02T10:50:20-0300 | vad-option-probe.log | - |
| red-as-expected-vad-option-probe | EXPECTED-RED | 1 | 1 | 2026-11-02T10:50:20-0300 | vad-option-probe-neg.log | - |
| youtube-track-wiring | STALE | 0 | 0 | 2026-11-02T13:28:17-0300 | youtube-track-wiring.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:17-0300) |
| tap-open-timeout | STALE | 0 | 0 | 2026-11-02T13:28:52-0300 | tap-open-timeout.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:52-0300) |
| ui-stall-oracle | STALE | 0 | 0 | 2026-11-02T13:28:57-0300 | ui-stall-oracle.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:57-0300) |
| mute-audio | NO-VERDICT | 0 | 0 | 2026-11-01T16:18:51-0300 | mute-audio.log | log alterado depois do registo |
| device-silence | NO-VERDICT | 0 | 0 | 2026-11-01T16:21:39-0300 | device-silence.log | log alterado depois do registo |
| red-as-expected-device-silence | NO-VERDICT | 1 | 1 | 2026-11-01T16:22:30-0300 | device-silence-neg.log | log alterado depois do registo |
| review-f1f3 | STALE | 0 | 0 | 2026-11-02T13:28:59-0300 | review-f1f3.log | deps mudaram depois da medicao (medido 2026-11-02T13:28:59-0300) |
| review-tapstop | PASS | 0 | 0 | 2026-10-20T02:23:24-0300 | review-tapstop.log | - |
| strip-surface-oracle | STALE | 0 | 0 | 2026-11-02T13:29:20-0300 | strip-surface-oracle.log | deps mudaram depois da medicao (medido 2026-11-02T13:29:20-0300) |
| strip-stats-log-budget | NO-VERDICT | 0 | 0 | 2026-11-01T16:23:31-0300 | strip-stats-log.log | log alterado depois do registo |
| strip-hot-reload | STALE | 0 | 0 | 2026-11-02T13:29:36-0300 | strip-reload.log | deps mudaram depois da medicao (medido 2026-11-02T13:29:36-0300) |
| strip-surface-runtime | NO-VERDICT | 0 | 0 | 2026-11-01T15:15:59-0300 | strip-surface.log | log alterado depois do registo |
| red-as-expected-strip-surface | EXPECTED-RED | 1 | 1 | 2026-11-01T15:15:59-0300 | strip-surface-neg.log | heavy |
| strip-geometry-restore | NO-VERDICT | 0 | 0 | 2026-11-01T13:41:35-0300 | strip-restore.log | log alterado depois do registo |
| strip-stats-wave | NO-VERDICT | 0 | 0 | 2026-11-01T16:24:01-0300 | strip-stats.log | log alterado depois do registo |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-01T16:13:05-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-02T13:29:39-0300 | hotkey-registration.log | always |
| hotkey-delivery | STALE | 0 | 0 | 2026-11-02T13:29:39-0300 | hotkey-delivery.log | deps mudaram depois da medicao (medido 2026-11-02T13:29:39-0300) |
| open-close-stall | STALE | 0 | 0 | 2026-11-02T13:29:42-0300 | open-close-stall.log | deps mudaram depois da medicao (medido 2026-11-02T13:29:42-0300) |
| red-as-expected-open-close-stall | STALE | 1 | 1 | 2026-11-02T13:29:56-0300 | open-close-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:29:56-0300) |
| autostart-status | STALE | 0 | 0 | 2026-11-02T13:29:58-0300 | autostart-status.log | deps mudaram depois da medicao (medido 2026-11-02T13:29:58-0300) |
| control-verdict-gate-unguard | PASS | 0 | 0 | 2026-11-01T13:43:06-0300 | control-verdict-gate-unguard.log | - |
| control-history-producer-stamp-nvidia | PASS | 0 | 0 | 2026-11-01T13:43:07-0300 | control-history-producer-stamp-nvidia.log | - |
| control-redux-flag-neg-arm | STALE | 0 | 0 | 2026-11-02T13:30:00-0300 | control-redux-flag-neg-arm.log | deps mudaram depois da medicao (medido 2026-11-02T13:30:00-0300) |
| control-panel-exit3-neg-arm | NO-VERDICT | 0 | 0 | 2026-11-01T13:43:10-0300 | control-panel-exit3-neg-arm.log | log alterado depois do registo |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-10-20T02:26:52-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | PASS | 0 | 0 | 2026-11-02T01:31:14-0300 | control-panel2-repeat-revert.log | - |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-10-20T02:26:54-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | EXPECTED-RED | 1 | 1 | 2026-10-30T01:58:24-0300 | control-historico-gate-off.log | - |
| search-oracle | STALE | 0 | 0 | 2026-11-02T13:30:04-0300 | search-oracle.log | deps mudaram depois da medicao (medido 2026-11-02T13:30:04-0300) |
| red-as-expected-search-oracle | STALE | 1 | 1 | 2026-11-02T13:30:06-0300 | search-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:30:06-0300) |
| panel-search-keyboard | STALE | 0 | 0 | 2026-11-02T13:30:09-0300 | panel-search-keyboard.log | deps mudaram depois da medicao (medido 2026-11-02T13:30:09-0300) |
| red-as-expected-panel-search-keyboard | STALE | 1 | 1 | 2026-11-02T13:30:12-0300 | panel-search-keyboard-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:30:12-0300) |
| fresh-processor-probe | PASS | 0 | 0 | 2026-11-02T10:50:32-0300 | fresh-processor.log | - |
| stepcache-oracle | PASS | 0 | 0 | 2026-10-21T18:40:17-0300 | stepcache-oracle.log | - |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-02T13:30:16-0300 | _skip-guard.log | always |
| altc-first-caption | NO-VERDICT | 0 | 0 | 2026-11-01T16:24:24-0300 | altc-first-caption.log | log alterado depois do registo |
| altc-gesture | STALE | 0 | 0 | 2026-11-02T13:30:22-0300 | altc-gesture.log | deps mudaram depois da medicao (medido 2026-11-02T13:30:22-0300) |
| headphone-cut | PASS | 0 | 0 | 2026-11-02T13:31:23-0300 | headphone-cut.log | always |
| incomplete-word | PASS | 0 | 0 | 2026-11-02T13:31:25-0300 | incomplete-word.log | always |
| ladder-signal | STALE | 0 | 0 | 2026-11-02T13:31:27-0300 | ladder-signal.log | deps mudaram depois da medicao (medido 2026-11-02T13:31:27-0300) |
| launch-as-token | PASS | 0 | 0 | 2026-11-02T13:31:37-0300 | launch-as-token.log | always |
| live-code-freshness | STALE | 0 | 0 | 2026-11-02T13:31:38-0300 | live-code-freshness.log | deps mudaram depois da medicao (medido 2026-11-02T13:31:38-0300) |
| load-shedding | STALE | 0 | 0 | 2026-11-02T13:31:40-0300 | load-shedding.log | deps mudaram depois da medicao (medido 2026-11-02T13:31:40-0300) |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-02T13:31:42-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | STALE | 1 | 1 | 2026-11-02T13:31:57-0300 | altc-gesture-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:31:57-0300) |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-02T13:31:59-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:00-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:01-0300 | ladder-signal-neg.log | always |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:07-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-02T13:32:07-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:09-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | STALE | 1 | 1 | 2026-11-02T13:32:13-0300 | load-shedding-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:32:13-0300) |
| red-as-expected-shell-relaunch | EXPECTED-RED | 1 | 1 | 2026-11-01T13:46:03-0300 | shell-relaunch-neg.log | heavy |
| red-as-expected-word-clock | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:15-0300 | word-clock-neg.log | always |
| red-as-expected-youtube-monotonic | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:17-0300 | youtube-monotonic-neg.log | always |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:19-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | STALE | 1 | 1 | 2026-11-02T13:32:21-0300 | youtube-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:32:21-0300) |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:22-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NO-VERDICT | 0 | 0 | 2026-11-01T13:46:10-0300 | shell-relaunch.log | log alterado depois do registo |
| word-clock | STALE | 0 | 0 | 2026-11-02T13:32:25-0300 | word-clock.log | deps mudaram depois da medicao (medido 2026-11-02T13:32:25-0300) |
| youtube-monotonic | STALE | 0 | 0 | 2026-11-02T13:32:27-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-11-02T13:32:27-0300) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-02T13:32:29-0300 | youtube-sotto-drift.log | always |
| youtube-switch | STALE | 0 | 0 | 2026-11-02T13:32:31-0300 | youtube-switch.log | deps mudaram depois da medicao (medido 2026-11-02T13:32:31-0300) |
| yt-no-dub | STALE | 0 | 0 | 2026-11-02T13:32:32-0300 | yt-no-dub.log | deps mudaram depois da medicao (medido 2026-11-02T13:32:32-0300) |
| stale-display | STALE | 0 | 0 | 2026-11-02T13:32:33-0300 | stale-display.log | deps mudaram depois da medicao (medido 2026-11-02T13:32:33-0300) |
| red-as-expected-stale-display | STALE | 1 | 1 | 2026-11-02T13:32:36-0300 | stale-display-neg.log | deps mudaram depois da medicao (medido 2026-11-02T13:32:36-0300) |
| battery-class | PASS | 0 | 0 | 2026-11-02T13:32:37-0300 | battery-class.log | always |
| red-as-expected-battery-class | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:39-0300 | battery-class-neg.log | always |
| live-queue | PASS | 0 | 0 | 2026-11-02T13:32:42-0300 | live-queue.log | always |
| red-as-expected-live-queue | EXPECTED-RED | 1 | 1 | 2026-11-02T13:32:44-0300 | live-queue-neg.log | always |
| flat-endpoint | PASS | 0 | 0 | 2026-11-02T13:32:46-0300 | flat-endpoint.log | always |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
