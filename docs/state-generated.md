# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=173 · PASS=62 · EXPECTED-RED=31 · FAIL=9 · STALE=65 · NO-VERDICT=6 · NOT RUN=0

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | PASS | 0 | 0 | 2026-11-01T11:01:34-0300 | pycompile-webview.log | - |
| pycompile-webview-helpers | PASS | 0 | 0 | 2026-10-30T04:23:01-0300 | pycompile-webview-helpers.log | - |
| pycompile-sotto_worker | PASS | 0 | 0 | 2026-11-01T11:01:35-0300 | pycompile-worker.log | - |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-10-20T02:22:19-0300 | pycompile-capture.log | - |
| transcript-append-oracle | PASS | 0 | 0 | 2026-10-30T01:55:01-0300 | oracle-transcript-append.log | - |
| live-vs-history-source-oracle | PASS | 0 | 0 | 2026-10-30T03:24:06-0300 | oracle-live-vs-history.log | - |
| historico-vs-redux-probe | PASS | 0 | 0 | 2026-10-30T01:55:02-0300 | oracle-historico-vs-redux.log | - |
| control-verdict-gate-drop-redux-live | PASS | 0 | 0 | 2026-11-01T11:01:37-0300 | control-verdict-gate-drop-redux-live.log | - |
| history-producer-gate | PASS | 0 | 0 | 2026-11-01T11:01:38-0300 | gate-history-producer.log | - |
| panel-state-guard-gate | PASS | 0 | 0 | 2026-10-30T03:24:07-0300 | gate-panel-state-guard.log | - |
| verdict-gate | PASS | 0 | 0 | 2026-11-01T11:01:39-0300 | gate-verdict.log | - |
| lane2-reset-probe | PASS | 0 | 0 | 2026-10-30T03:24:08-0300 | lane2-reset.log | - |
| lane3-verdict-probe | PASS | 0 | 0 | 2026-11-01T11:02:15-0300 | lane3-verdict.log | - |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-10-20T02:22:33-0300 | lane4-tap-stop.log | - |
| audit-history-dead | PASS | 0 | 0 | 2026-10-30T01:55:14-0300 | audit-history-dead.log | - |
| panel2-repeat-probe | PASS | 0 | 0 | 2026-10-30T09:42:28-0300 | panel2-repeat.log | - |
| history-gallery-oracle | PASS | 0 | 0 | 2026-10-20T02:22:35-0300 | gallery-oracle.log | - |
| panel2-dom-probe | PASS | 0 | 0 | 2026-10-30T09:42:31-0300 | panel2-dom-probe.log | - |
| panel-live-box-oracle | PASS | 0 | 0 | 2026-10-30T09:42:35-0300 | panel-live-box-oracle.log | - |
| border-radius-gate | PASS | 0 | 0 | 2026-10-30T09:42:35-0300 | border-radius-gate.log | - |
| red-as-expected-border-radius-gate | EXPECTED-RED | 1 | 1 | 2026-10-30T09:42:35-0300 | border-radius-gate-neg.log | - |
| lane-screen-gate | PASS | 0 | 0 | 2026-11-01T11:02:19-0300 | lane-screen-gate.log | - |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-10-24T00:05:28-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | PASS | 0 | 0 | 2026-11-01T11:02:20-0300 | caption-dup-repro.log | - |
| complaints-closure | PASS | 0 | 0 | 2026-10-30T10:05:12-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-10-30T10:05:12-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | PASS | 0 | 0 | 2026-11-01T11:02:22-0300 | youtube-paint-first.log | - |
| red-as-expected-youtube-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-01T11:02:22-0300 | youtube-paint-first-neg.log | - |
| youtube-foreign-paint | FAIL | 2 | 0 | 2026-11-01T11:02:24-0300 | youtube-foreign-paint.log | rc=2 != esperado 0 |
| red-as-expected-youtube-foreign-paint | EXPECTED-RED | 1 | 1 | 2026-11-01T11:02:24-0300 | youtube-foreign-paint-neg.log | - |
| input-path | FAIL | 2 | 0 | 2026-11-01T11:02:28-0300 | input-path.log | rc=2 != esperado 0 |
| red-as-expected-input-path | NO-VERDICT | 1 | 1 | 2026-11-01T11:02:29-0300 | input-path-neg.log | token `NEG-ARM PASS` ausente do log |
| exception-hygiene | PASS | 0 | 0 | 2026-11-01T11:02:31-0300 | exception-hygiene.log | - |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-01T11:02:36-0300 | exception-hygiene-neg.log | - |
| seam-coverage | FAIL | 2 | 0 | 2026-11-01T11:02:40-0300 | seam-coverage.log | rc=2 != esperado 0 |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-10-30T04:23:36-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-10-30T04:23:36-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-10-23T20:51:34-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-10-23T20:53:01-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-10-23T20:43:48-0300 | tooling-intent-neg.log | - |
| external-resume | PASS | 0 | 0 | 2026-11-01T11:02:42-0300 | external-resume.log | - |
| red-as-expected-external-resume | EXPECTED-RED | 1 | 1 | 2026-11-01T11:02:44-0300 | external-resume-neg.log | - |
| code-health | FAIL | 2 | 0 | 2026-11-01T11:02:46-0300 | code-health.log | rc=2 != esperado 0 |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-01T11:02:47-0300 | code-health-neg.log | always |
| undefined-names | PASS | 0 | 0 | 2026-11-01T11:02:48-0300 | undefined-names.log | always |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-01T11:02:49-0300 | undefined-names-neg.log | always |
| battery-heavy-gate | PASS | 0 | 0 | 2026-11-01T11:02:51-0300 | battery-heavy-gate.log | - |
| red-as-expected-battery-heavy-gate | EXPECTED-RED | 1 | 1 | 2026-11-01T11:03:00-0300 | battery-heavy-gate-neg.log | - |
| task-resolver-gate | PASS | 0 | 0 | 2026-11-01T11:03:01-0300 | task-resolver-gate.log | - |
| red-as-expected-task-resolver-gate | EXPECTED-RED | 1 | 1 | 2026-11-01T11:03:02-0300 | task-resolver-gate-neg.log | - |
| claims-date | PASS | 0 | 0 | 2026-11-01T11:03:02-0300 | claims-date.log | - |
| red-as-expected-claims-date | EXPECTED-RED | 1 | 1 | 2026-11-01T11:03:03-0300 | claims-date-neg.log | - |
| receipt-provenance | PASS | 0 | 0 | 2026-11-01T11:03:04-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-01T11:03:05-0300 | receipt-provenance-neg.log | always |
| state-page-write | NO-VERDICT | 0 | 0 | 2026-11-01T10:46:37-0300 | state-page-write.log | log alterado depois do registo |
| state-page | STALE | 0 | 0 | 2026-11-01T10:46:43-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-01T10:46:43-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-01T10:47:54-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:47:54-0300) |
| battery-wiring | STALE | 0 | 0 | 2026-10-30T12:26:01-0300 | battery-wiring.log | deps mudaram depois da medicao (medido 2026-10-30T12:26:01-0300) |
| red-as-expected-battery-wiring | STALE | 1 | 1 | 2026-10-30T12:26:02-0300 | battery-wiring-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:26:02-0300) |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-01T10:47:56-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-01T10:48:00-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | STALE | 0 | 0 | 2026-11-01T10:48:04-0300 | youtube-1to1.log | deps mudaram depois da medicao (medido 2026-11-01T10:48:04-0300) |
| red-as-expected-youtube-1to1 | STALE | 1 | 1 | 2026-11-01T10:48:08-0300 | youtube-1to1-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:48:08-0300) |
| youtube-reveal | STALE | 0 | 0 | 2026-11-01T10:48:10-0300 | youtube-reveal.log | deps mudaram depois da medicao (medido 2026-11-01T10:48:10-0300) |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-01T10:48:11-0300 | youtube-reveal-neg.log | always |
| youtube-rows | STALE | 0 | 0 | 2026-11-01T10:48:15-0300 | youtube-rows.log | deps mudaram depois da medicao (medido 2026-11-01T10:48:15-0300) |
| red-as-expected-youtube-rows | STALE | 1 | 1 | 2026-11-01T10:48:18-0300 | youtube-rows-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:48:18-0300) |
| youtube-drift | PASS | 0 | 0 | 2026-11-01T10:48:19-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-01T10:48:20-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-01T10:48:58-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-01T10:49:00-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-01T10:49:00-0300 | bend-laws-model-neg.log | always |
| panel-hidden-at-startup-oracle | FAIL | 1 | 0 | 2026-11-01T10:49:08-0300 | panel-hidden-at-startup.log | rc=1 != esperado 0 |
| red-as-expected-panel-hidden-at-startup | STALE | 1 | 1 | 2026-11-01T10:49:10-0300 | panel-hidden-at-startup-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:10-0300) |
| worker-start-wiring | STALE | 0 | 0 | 2026-11-01T10:49:10-0300 | wiring-worker-start.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:10-0300) |
| embedded-js-check | STALE | 0 | 0 | 2026-11-01T10:49:12-0300 | embedded-js.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:12-0300) |
| lane1-worker-default-arms | STALE | 0 | 0 | 2026-11-01T10:49:12-0300 | lane1-arms.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:12-0300) |
| external-subs-stability | PASS | 0 | 0 | 2026-10-20T02:35:09-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | STALE | 0 | 0 | 2026-11-01T10:49:14-0300 | external-caption-chrome-census.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:14-0300) |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-10-24T00:15:07-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-10-24T00:15:08-0300 | external-subs-geometry-window.log | - |
| youtube-captions | PASS | 0 | 0 | 2026-10-30T10:13:23-0300 | youtube-captions.log | - |
| caption-native-wrap | STALE | 0 | 0 | 2026-11-01T10:49:17-0300 | caption-native-wrap.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:17-0300) |
| yt-player-track | PASS | 0 | 0 | 2026-10-30T10:13:24-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-10-30T10:13:24-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-10-30T10:13:25-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-10-24T00:19:34-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-10-24T00:19:41-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | PASS | 0 | 0 | 2026-10-30T07:18:56-0300 | gitattributes-verify.log | - |
| agents-md-pins | FAIL | 1 | 0 | 2026-11-01T10:49:20-0300 | agents-md-pins.log | rc=1 != esperado 0 |
| lang-id-oracle | STALE | 0 | 0 | 2026-11-01T10:49:27-0300 | lang-id-oracle.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:27-0300) |
| red-as-expected-lang-id-oracle | STALE | 1 | 1 | 2026-11-01T10:49:39-0300 | lang-id-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:39-0300) |
| model-spec-oracle | PASS | 0 | 0 | 2026-10-24T00:21:34-0300 | model-spec-oracle.log | - |
| red-as-expected-model-spec-oracle | EXPECTED-RED | 1 | 1 | 2026-10-24T00:21:35-0300 | model-spec-oracle-neg.log | - |
| scope-leak | PASS | 0 | 0 | 2026-10-30T10:06:22-0300 | scope-leak.log | - |
| red-as-expected-scope-leak | EXPECTED-RED | 1 | 1 | 2026-10-30T10:06:24-0300 | scope-leak-neg.log | - |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-01T10:49:42-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:42-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-01T10:49:42-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:42-0300) |
| per-app-source-plumbing | STALE | 0 | 0 | 2026-11-01T10:49:43-0300 | per-app-source-plumbing.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:43-0300) |
| red-as-expected-per-app-source-plumbing | STALE | 1 | 1 | 2026-11-01T10:49:44-0300 | per-app-source-plumbing-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:44-0300) |
| redux-live-contract | PASS | 0 | 0 | 2026-10-30T03:25:50-0300 | redux-live-contract.log | - |
| red-as-expected-redux-live-contract | EXPECTED-RED | 1 | 1 | 2026-10-30T03:25:51-0300 | redux-live-contract-neg.log | - |
| word-split-oracle | STALE | 0 | 0 | 2026-11-01T10:49:46-0300 | word-split-oracle.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:46-0300) |
| red-as-expected-word-split-oracle | STALE | 1 | 1 | 2026-11-01T10:49:47-0300 | word-split-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:47-0300) |
| vad-option-probe | STALE | 0 | 0 | 2026-11-01T10:49:53-0300 | vad-option-probe.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:53-0300) |
| red-as-expected-vad-option-probe | STALE | 1 | 1 | 2026-11-01T10:49:54-0300 | vad-option-probe-neg.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:54-0300) |
| youtube-track-wiring | STALE | 0 | 0 | 2026-11-01T10:49:55-0300 | youtube-track-wiring.log | deps mudaram depois da medicao (medido 2026-11-01T10:49:55-0300) |
| tap-open-timeout | STALE | 0 | 0 | 2026-11-01T10:50:30-0300 | tap-open-timeout.log | deps mudaram depois da medicao (medido 2026-11-01T10:50:30-0300) |
| ui-stall-oracle | FAIL | 1 | 0 | 2026-11-01T10:50:32-0300 | ui-stall-oracle.log | rc=1 != esperado 0 |
| mute-audio | PASS | 0 | 0 | 2026-11-01T10:50:51-0300 | mute-audio.log | always/heavy |
| review-f1f3 | STALE | 0 | 0 | 2026-11-01T10:50:52-0300 | review-f1f3.log | deps mudaram depois da medicao (medido 2026-11-01T10:50:52-0300) |
| review-tapstop | PASS | 0 | 0 | 2026-10-20T02:23:24-0300 | review-tapstop.log | - |
| strip-surface-oracle | STALE | 0 | 0 | 2026-11-01T10:51:12-0300 | strip-surface-oracle.log | deps mudaram depois da medicao (medido 2026-11-01T10:51:12-0300) |
| strip-stats-log-budget | PASS | 0 | 0 | 2026-11-01T10:52:23-0300 | strip-stats-log.log | always/heavy |
| strip-hot-reload | PASS | 0 | 0 | 2026-11-01T10:52:38-0300 | strip-reload.log | - |
| strip-surface-runtime | FAIL | 3 | 0 | 2026-11-01T10:57:19-0300 | strip-surface.log | rc=3 != esperado 0 |
| strip-geometry-restore | PASS | 0 | 0 | 2026-11-01T10:59:34-0300 | strip-restore.log | heavy |
| strip-stats-wave | NO-VERDICT | 0 | 0 | 2026-10-22T02:42:29-0300 | strip-stats.log | log alterado depois do registo |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-10-30T07:24:49-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-10-30T12:54:25-0300 | hotkey-registration.log | always |
| hotkey-delivery | STALE | 0 | 0 | 2026-10-30T12:54:26-0300 | hotkey-delivery.log | deps mudaram depois da medicao (medido 2026-10-30T12:54:26-0300) |
| open-close-stall | STALE | 0 | 0 | 2026-10-30T12:26:44-0300 | open-close-stall.log | deps mudaram depois da medicao (medido 2026-10-30T12:26:44-0300) |
| red-as-expected-open-close-stall | STALE | 1 | 1 | 2026-10-30T12:26:51-0300 | open-close-stall-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:26:51-0300) |
| autostart-status | STALE | 0 | 0 | 2026-10-30T12:54:27-0300 | autostart-status.log | deps mudaram depois da medicao (medido 2026-10-30T12:54:27-0300) |
| control-verdict-gate-unguard | STALE | 0 | 0 | 2026-10-30T12:12:06-0300 | control-verdict-gate-unguard.log | deps mudaram depois da medicao (medido 2026-10-30T12:12:06-0300) |
| control-history-producer-stamp-nvidia | STALE | 0 | 0 | 2026-10-30T12:12:07-0300 | control-history-producer-stamp-nvidia.log | deps mudaram depois da medicao (medido 2026-10-30T12:12:07-0300) |
| control-redux-flag-neg-arm | STALE | 0 | 0 | 2026-10-30T12:12:07-0300 | control-redux-flag-neg-arm.log | deps mudaram depois da medicao (medido 2026-10-30T12:12:07-0300) |
| control-panel-exit3-neg-arm | NO-VERDICT | 0 | 0 | 2026-10-22T02:42:33-0300 | control-panel-exit3-neg-arm.log | log alterado depois do registo |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-10-20T02:26:52-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | PASS | 0 | 0 | 2026-10-30T09:47:16-0300 | control-panel2-repeat-revert.log | - |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-10-20T02:26:54-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | EXPECTED-RED | 1 | 1 | 2026-10-30T01:58:24-0300 | control-historico-gate-off.log | - |
| search-oracle | STALE | 0 | 0 | 2026-10-30T12:12:09-0300 | search-oracle.log | deps mudaram depois da medicao (medido 2026-10-30T12:12:09-0300) |
| red-as-expected-search-oracle | STALE | 1 | 1 | 2026-10-30T12:12:11-0300 | search-oracle-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:12:11-0300) |
| panel-search-keyboard | STALE | 0 | 0 | 2026-10-30T12:12:13-0300 | panel-search-keyboard.log | deps mudaram depois da medicao (medido 2026-10-30T12:12:13-0300) |
| red-as-expected-panel-search-keyboard | STALE | 1 | 1 | 2026-10-30T12:12:14-0300 | panel-search-keyboard-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:12:14-0300) |
| fresh-processor-probe | STALE | 0 | 0 | 2026-10-30T12:27:01-0300 | fresh-processor.log | deps mudaram depois da medicao (medido 2026-10-30T12:27:01-0300) |
| stepcache-oracle | PASS | 0 | 0 | 2026-10-21T18:40:17-0300 | stepcache-oracle.log | - |
| skip-verdict-guard | PASS | 0 | 0 | 2026-10-30T12:54:33-0300 | _skip-guard.log | always |
| altc-first-caption | FAIL | 1 | 0 | 2026-10-30T12:12:22-0300 | altc-first-caption.log | rc=1 != esperado 0 |
| altc-gesture | STALE | 0 | 0 | 2026-10-30T12:54:36-0300 | altc-gesture.log | deps mudaram depois da medicao (medido 2026-10-30T12:54:36-0300) |
| headphone-cut | STALE | 0 | 0 | 2026-10-30T12:55:37-0300 | headphone-cut.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:37-0300) |
| incomplete-word | STALE | 0 | 0 | 2026-10-30T12:55:37-0300 | incomplete-word.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:37-0300) |
| ladder-signal | STALE | 0 | 0 | 2026-10-30T12:55:37-0300 | ladder-signal.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:37-0300) |
| launch-as-token | PASS | 0 | 0 | 2026-10-30T12:55:41-0300 | launch-as-token.log | always |
| live-code-freshness | STALE | 0 | 0 | 2026-10-30T12:55:42-0300 | live-code-freshness.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:42-0300) |
| load-shedding | STALE | 0 | 0 | 2026-10-30T12:55:42-0300 | load-shedding.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:42-0300) |
| red-as-expected-altc-first-caption | STALE | 1 | 1 | 2026-10-30T12:55:43-0300 | altc-first-caption-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:43-0300) |
| red-as-expected-altc-gesture | STALE | 1 | 1 | 2026-10-30T12:55:45-0300 | altc-gesture-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:45-0300) |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-10-30T12:55:46-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-10-30T12:55:46-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | STALE | 1 | 1 | 2026-10-30T12:55:47-0300 | ladder-signal-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:47-0300) |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-10-30T12:55:48-0300 | launch-as-token-neg.log | always |
| red-as-expected-load-shedding | STALE | 1 | 1 | 2026-10-30T12:55:49-0300 | load-shedding-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:49-0300) |
| red-as-expected-shell-relaunch | NO-VERDICT | 1 | 1 | 2026-10-30T11:13:20-0300 | shell-relaunch-neg.log | log alterado depois do registo |
| red-as-expected-word-clock | STALE | 1 | 1 | 2026-10-30T12:55:50-0300 | word-clock-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:50-0300) |
| red-as-expected-youtube-monotonic | STALE | 1 | 1 | 2026-10-30T12:55:51-0300 | youtube-monotonic-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:51-0300) |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-10-30T12:55:51-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | STALE | 1 | 1 | 2026-10-30T12:55:52-0300 | youtube-switch-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:52-0300) |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-10-30T12:55:52-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NO-VERDICT | 0 | 0 | 2026-10-30T11:12:59-0300 | shell-relaunch.log | log alterado depois do registo |
| word-clock | STALE | 0 | 0 | 2026-10-30T12:55:53-0300 | word-clock.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:53-0300) |
| youtube-monotonic | STALE | 0 | 0 | 2026-10-30T12:55:54-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:54-0300) |
| youtube-sotto-drift | STALE | 0 | 0 | 2026-10-30T12:55:54-0300 | youtube-sotto-drift.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:54-0300) |
| youtube-switch | STALE | 0 | 0 | 2026-10-30T12:55:55-0300 | youtube-switch.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:55-0300) |
| yt-no-dub | STALE | 0 | 0 | 2026-10-30T12:55:55-0300 | yt-no-dub.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:55-0300) |
| stale-display | STALE | 0 | 0 | 2026-10-30T12:55:56-0300 | stale-display.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:56-0300) |
| red-as-expected-stale-display | STALE | 1 | 1 | 2026-10-30T12:55:56-0300 | stale-display-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:56-0300) |
| battery-class | STALE | 0 | 0 | 2026-10-30T12:55:57-0300 | battery-class.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:57-0300) |
| red-as-expected-battery-class | STALE | 1 | 1 | 2026-10-30T12:55:57-0300 | battery-class-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:57-0300) |
| live-queue | STALE | 0 | 0 | 2026-10-30T12:55:58-0300 | live-queue.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:58-0300) |
| red-as-expected-live-queue | STALE | 1 | 1 | 2026-10-30T12:55:58-0300 | live-queue-neg.log | deps mudaram depois da medicao (medido 2026-10-30T12:55:58-0300) |
| flat-endpoint | PASS | 0 | 0 | 2026-10-30T12:55:59-0300 | flat-endpoint.log | always |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
