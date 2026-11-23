# Estado gerado — Sotto

> **GERADO por `_main/sotto-state-page.py`. NÃO EDITAR À MÃO.**
> `--check` recusa uma página que não seja byte-idêntica a uma renderização fresca.
> Um passo que não correu é `NOT RUN` — nunca um verde.
>
> Fonte: `_main/_audit-verify-all.cmd` (que passos existem) · `_cache/battery-steps.json`
> (o que o `_stepcache` registou) · `_main/_audit-verify/*.log` (as saídas). Nada aqui é
> escrito por uma pessoa, e nada aqui é um número escolhido: cada célula vem de um desses
> três ficheiros, e `--check` é o portão que o prova.

Resumo: passos=546 · PASS=48 · EXPECTED-RED=52 · FAIL=0 · STALE=402 · NO-VERDICT=2 · NOT RUN=42

| passo | estado | rc | esperado | quando | log | nota |
| --- | --- | --- | --- | --- | --- | --- |
| pycompile-sotto_webview | STALE | 0 | 0 | 2026-11-15T17:15:16-0300 | pycompile-webview.log | deps mudaram depois da medicao (medido 2026-11-15T17:15:16-0300) |
| pycompile-webview-helpers | STALE | 0 | 0 | 2026-11-15T11:38:31-0300 | pycompile-webview-helpers.log | deps mudaram depois da medicao (medido 2026-11-15T11:38:31-0300) |
| pycompile-sotto_worker | STALE | 0 | 0 | 2026-11-15T12:39:01-0300 | pycompile-worker.log | deps mudaram depois da medicao (medido 2026-11-15T12:39:01-0300) |
| pycompile-wasapi+lang | PASS | 0 | 0 | 2026-11-12T02:53:26-0300 | pycompile-capture.log | - |
| transcript-append-oracle | STALE | 0 | 0 | 2026-11-09T20:43:51-0300 | oracle-transcript-append.log | deps mudaram depois da medicao (medido 2026-11-09T20:43:51-0300) |
| live-vs-history-source-oracle | STALE | 0 | 0 | 2026-11-15T11:38:33-0300 | oracle-live-vs-history.log | deps mudaram depois da medicao (medido 2026-11-15T11:38:33-0300) |
| historico-vs-redux-probe | STALE | 0 | 0 | 2026-11-11T11:29:42-0300 | oracle-historico-vs-redux.log | deps mudaram depois da medicao (medido 2026-11-11T11:29:42-0300) |
| redux-transcript-path | STALE | 0 | 0 | 2026-11-15T17:15:20-0300 | redux-transcript-path.log | deps mudaram depois da medicao (medido 2026-11-15T17:15:20-0300) |
| redux-arm-weights | STALE | 0 | 0 | 2026-11-15T17:15:21-0300 | redux-arm-weights.log | deps mudaram depois da medicao (medido 2026-11-15T17:15:21-0300) |
| history-write | STALE | 0 | 0 | 2026-11-15T17:15:43-0300 | history-write.log | deps mudaram depois da medicao (medido 2026-11-15T17:15:43-0300) |
| caption-cumulative | STALE | 0 | 0 | 2026-11-09T20:44:12-0300 | oracle-caption-cumulative.log | deps mudaram depois da medicao (medido 2026-11-09T20:44:12-0300) |
| red-as-expected-caption-cumulative | STALE | 1 | 1 | 2026-11-09T20:44:13-0300 | caption-cumulative-neg.log | deps mudaram depois da medicao (medido 2026-11-09T20:44:13-0300) |
| caption-lag-budget | STALE | 0 | 0 | 2026-11-15T17:15:45-0300 | caption-lag-budget.log | deps mudaram depois da medicao (medido 2026-11-15T17:15:45-0300) |
| red-as-expected-caption-lag-budget | STALE | 1 | 1 | 2026-11-15T17:15:57-0300 | caption-lag-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:15:57-0300) |
| caption-rollup | STALE | 0 | 0 | 2026-11-15T11:39:00-0300 | caption-rollup.log | deps mudaram depois da medicao (medido 2026-11-15T11:39:00-0300) |
| red-as-expected-caption-rollup | STALE | 1 | 1 | 2026-11-15T11:39:02-0300 | caption-rollup-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:39:02-0300) |
| paint-cost | STALE | 0 | 0 | 2026-11-15T11:39:07-0300 | paint-cost.log | deps mudaram depois da medicao (medido 2026-11-15T11:39:07-0300) |
| red-as-expected-paint-cost | STALE | 1 | 1 | 2026-11-15T11:39:10-0300 | paint-cost-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:39:10-0300) |
| shell-thread-budget | STALE | 0 | 0 | 2026-11-15T17:16:05-0300 | shell-thread-budget.log | deps mudaram depois da medicao (medido 2026-11-15T17:16:05-0300) |
| red-as-expected-shell-thread-budget | EXPECTED-RED | 1 | 1 | 2026-11-11T11:30:20-0300 | shell-thread-budget-neg.log | - |
| tree-cost | STALE | 0 | 0 | 2026-11-15T17:16:08-0300 | tree-cost.log | deps mudaram depois da medicao (medido 2026-11-15T17:16:08-0300) |
| red-as-expected-tree-cost | EXPECTED-RED | 1 | 1 | 2026-11-11T11:30:23-0300 | tree-cost-neg.log | - |
| engine-serialization | STALE | 0 | 0 | 2026-11-15T12:39:30-0300 | engine-serialization.log | deps mudaram depois da medicao (medido 2026-11-15T12:39:30-0300) |
| red-as-expected-engine-serialization | STALE | 1 | 1 | 2026-11-15T12:39:47-0300 | engine-serialization-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:39:47-0300) |
| batch-silence-gate | NOT RUN | - | 0 | - | batch-silence-gate.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-batch-silence-gate | NOT RUN | - | 1 | - | batch-silence-gate-neg.log | sem registo no stepcache (o passo nao completou) |
| ort-spin-idle | STALE | 0 | 0 | 2026-11-15T12:39:59-0300 | ort-spin-idle.log | deps mudaram depois da medicao (medido 2026-11-15T12:39:59-0300) |
| red-as-expected-ort-spin-idle | STALE | 1 | 1 | 2026-11-15T12:40:08-0300 | ort-spin-idle-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:40:08-0300) |
| worker-thread-limit | STALE | 0 | 0 | 2026-11-15T17:16:15-0300 | worker-thread-limit.log | deps mudaram depois da medicao (medido 2026-11-15T17:16:15-0300) |
| red-as-expected-worker-thread-limit | STALE | 1 | 1 | 2026-11-15T17:16:17-0300 | worker-thread-limit-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:16:17-0300) |
| caption-tick-thread | STALE | 0 | 0 | 2026-11-15T11:39:52-0300 | caption-tick-thread.log | deps mudaram depois da medicao (medido 2026-11-15T11:39:52-0300) |
| red-as-expected-caption-tick-thread | STALE | 1 | 1 | 2026-11-15T11:39:55-0300 | caption-tick-thread-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:39:55-0300) |
| caption-timeline | STALE | 0 | 0 | 2026-11-15T17:16:19-0300 | caption-timeline.log | deps mudaram depois da medicao (medido 2026-11-15T17:16:19-0300) |
| red-as-expected-caption-timeline | EXPECTED-RED | 1 | 1 | 2026-11-15T17:16:21-0300 | caption-timeline-neg.log | always |
| caption-status-hide | STALE | 0 | 0 | 2026-11-15T17:16:24-0300 | caption-status-hide.log | deps mudaram depois da medicao (medido 2026-11-15T17:16:24-0300) |
| red-as-expected-caption-status-hide | STALE | 1 | 1 | 2026-11-15T17:16:28-0300 | caption-status-hide-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:16:28-0300) |
| clr-warm | STALE | 0 | 0 | 2026-11-15T17:16:42-0300 | clr-warm.log | deps mudaram depois da medicao (medido 2026-11-15T17:16:42-0300) |
| red-as-expected-clr-warm | STALE | 1 | 1 | 2026-11-15T17:17:19-0300 | clr-warm-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:19-0300) |
| log-sink-dead | STALE | 0 | 0 | 2026-11-15T17:17:21-0300 | log-sink-dead.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:21-0300) |
| red-as-expected-log-sink-dead | STALE | 1 | 1 | 2026-11-15T17:17:42-0300 | log-sink-dead-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:42-0300) |
| cdp-target-async | STALE | 0 | 0 | 2026-11-15T11:40:47-0300 | cdp-target-async.log | deps mudaram depois da medicao (medido 2026-11-15T11:40:47-0300) |
| red-as-expected-cdp-target-async | STALE | 1 | 1 | 2026-11-15T11:40:59-0300 | cdp-target-async-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:40:59-0300) |
| caption-drag | STALE | 0 | 0 | 2026-11-15T11:41:04-0300 | caption-drag.log | deps mudaram depois da medicao (medido 2026-11-15T11:41:04-0300) |
| red-as-expected-caption-drag | STALE | 1 | 1 | 2026-11-15T11:41:15-0300 | caption-drag-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:41:15-0300) |
| lag-note-cost | STALE | 0 | 0 | 2026-11-15T17:17:46-0300 | lag-note-cost.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:46-0300) |
| red-as-expected-lag-note-cost | STALE | 1 | 1 | 2026-11-15T17:17:48-0300 | lag-note-cost-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:48-0300) |
| youtube-hidden-clock | STALE | 0 | 0 | 2026-11-15T17:17:50-0300 | youtube-hidden-clock.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:50-0300) |
| red-as-expected-youtube-hidden-clock | STALE | 1 | 1 | 2026-11-15T17:17:51-0300 | youtube-hidden-clock-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:51-0300) |
| caption-overlay-screen | STALE | 0 | 0 | 2026-11-15T17:17:51-0300 | caption-overlay-screen.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:51-0300) |
| red-as-expected-caption-overlay-screen | STALE | 1 | 1 | 2026-11-15T17:17:52-0300 | caption-overlay-screen-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:52-0300) |
| youtube-cdp-boot | STALE | 0 | 0 | 2026-11-15T17:17:56-0300 | youtube-cdp-boot.log | deps mudaram depois da medicao (medido 2026-11-15T17:17:56-0300) |
| red-as-expected-youtube-cdp-boot | STALE | 1 | 1 | 2026-11-15T17:18:34-0300 | youtube-cdp-boot-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:18:34-0300) |
| youtube-cdp-slow | STALE | 0 | 0 | 2026-11-15T17:18:41-0300 | youtube-cdp-slow.log | deps mudaram depois da medicao (medido 2026-11-15T17:18:41-0300) |
| red-as-expected-youtube-cdp-slow | STALE | 1 | 1 | 2026-11-15T17:19:04-0300 | youtube-cdp-slow-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:19:04-0300) |
| youtube-first-at-boot | STALE | 0 | 0 | 2026-11-15T17:19:22-0300 | youtube-first-at-boot.log | deps mudaram depois da medicao (medido 2026-11-15T17:19:22-0300) |
| red-as-expected-youtube-first-at-boot | STALE | 1 | 1 | 2026-11-15T17:20:12-0300 | youtube-first-at-boot-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:20:12-0300) |
| red-as-expected-redux-transcript-path | STALE | 1 | 1 | 2026-11-15T17:20:14-0300 | redux-transcript-path-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:20:14-0300) |
| red-as-expected-history-write | STALE | 1 | 1 | 2026-11-15T17:20:38-0300 | history-write-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:20:38-0300) |
| control-verdict-gate-drop-redux-live | STALE | 0 | 0 | 2026-11-15T12:43:21-0300 | control-verdict-gate-drop-redux-live.log | deps mudaram depois da medicao (medido 2026-11-15T12:43:21-0300) |
| history-producer-gate | STALE | 0 | 0 | 2026-11-15T12:43:23-0300 | gate-history-producer.log | deps mudaram depois da medicao (medido 2026-11-15T12:43:23-0300) |
| panel-state-guard-gate | STALE | 0 | 0 | 2026-11-15T11:43:27-0300 | gate-panel-state-guard.log | deps mudaram depois da medicao (medido 2026-11-15T11:43:27-0300) |
| verdict-gate | STALE | 0 | 0 | 2026-11-15T12:43:28-0300 | gate-verdict.log | deps mudaram depois da medicao (medido 2026-11-15T12:43:28-0300) |
| worker-park | STALE | 0 | 0 | 2026-11-15T17:21:15-0300 | worker-park.log | deps mudaram depois da medicao (medido 2026-11-15T17:21:15-0300) |
| red-as-expected-worker-park | STALE | 1 | 1 | 2026-11-15T17:21:15-0300 | worker-park-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:21:15-0300) |
| lane2-reset-probe | STALE | 0 | 0 | 2026-11-15T11:44:03-0300 | lane2-reset.log | deps mudaram depois da medicao (medido 2026-11-15T11:44:03-0300) |
| lane3-verdict-probe | STALE | 0 | 0 | 2026-11-15T12:44:53-0300 | lane3-verdict.log | deps mudaram depois da medicao (medido 2026-11-15T12:44:53-0300) |
| lane4-tap-stop-probe | PASS | 0 | 0 | 2026-11-12T03:01:10-0300 | lane4-tap-stop.log | - |
| audit-history-dead | STALE | 0 | 0 | 2026-11-11T02:56:48-0300 | audit-history-dead.log | deps mudaram depois da medicao (medido 2026-11-11T02:56:48-0300) |
| red-as-expected-audit-history-dead | NOT RUN | - | 1 | - | audit-history-dead-neg.log | sem registo no stepcache (o passo nao completou) |
| panel2-repeat-probe | STALE | 0 | 0 | 2026-11-15T11:44:09-0300 | panel2-repeat.log | deps mudaram depois da medicao (medido 2026-11-15T11:44:09-0300) |
| history-gallery-oracle | PASS | 0 | 0 | 2026-11-05T14:47:02-0300 | gallery-oracle.log | - |
| panel2-dom-probe | STALE | 0 | 0 | 2026-11-15T11:44:13-0300 | panel2-dom-probe.log | deps mudaram depois da medicao (medido 2026-11-15T11:44:13-0300) |
| panel-header-oracle | STALE | 0 | 0 | 2026-11-15T11:44:18-0300 | panel-header.log | deps mudaram depois da medicao (medido 2026-11-15T11:44:18-0300) |
| red-as-expected-panel-header-oracle | STALE | 1 | 1 | 2026-11-15T11:44:48-0300 | panel-header-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:44:48-0300) |
| panel-drag-targets | STALE | 0 | 0 | 2026-11-15T11:44:49-0300 | panel-drag-targets.log | deps mudaram depois da medicao (medido 2026-11-15T11:44:49-0300) |
| panel-history-clip | STALE | 0 | 0 | 2026-11-15T17:21:35-0300 | panel-history-clip.log | deps mudaram depois da medicao (medido 2026-11-15T17:21:35-0300) |
| window-drag | STALE | 0 | 0 | 2026-11-15T17:21:41-0300 | window-drag.log | deps mudaram depois da medicao (medido 2026-11-15T17:21:41-0300) |
| red-as-expected-window-drag | STALE | 1 | 1 | 2026-11-15T17:21:51-0300 | window-drag-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:21:51-0300) |
| panel-history-wheel | STALE | 0 | 0 | 2026-11-15T11:45:08-0300 | panel-history-wheel.log | deps mudaram depois da medicao (medido 2026-11-15T11:45:08-0300) |
| red-as-expected-panel-history-wheel | STALE | 1 | 1 | 2026-11-15T11:45:14-0300 | panel-history-wheel-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:45:14-0300) |
| theme-caption-identity | STALE | 0 | 0 | 2026-11-11T11:38:20-0300 | theme-caption-identity.log | deps mudaram depois da medicao (medido 2026-11-11T11:38:20-0300) |
| caption-plate | STALE | 0 | 0 | 2026-11-15T17:21:58-0300 | caption-plate.log | deps mudaram depois da medicao (medido 2026-11-15T17:21:58-0300) |
| red-as-expected-caption-plate | STALE | 1 | 1 | 2026-11-15T17:22:03-0300 | caption-plate-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:22:03-0300) |
| caption-visual-dom | STALE | 0 | 0 | 2026-11-15T11:45:22-0300 | caption-visual-dom.log | deps mudaram depois da medicao (medido 2026-11-15T11:45:22-0300) |
| red-as-expected-caption-visual-dom | STALE | 1 | 1 | 2026-11-15T11:45:24-0300 | caption-visual-dom-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:45:24-0300) |
| youtube-cdp-latency | STALE | 0 | 0 | 2026-11-15T11:45:27-0300 | youtube-cdp-latency.log | deps mudaram depois da medicao (medido 2026-11-15T11:45:27-0300) |
| red-as-expected-youtube-cdp-latency | STALE | 1 | 1 | 2026-11-15T11:45:44-0300 | youtube-cdp-latency-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:45:44-0300) |
| caption-noise | STALE | 0 | 0 | 2026-11-15T11:45:45-0300 | caption-noise.log | deps mudaram depois da medicao (medido 2026-11-15T11:45:45-0300) |
| speech-gate | STALE | 0 | 0 | 2026-11-15T12:45:06-0300 | speech-gate.log | deps mudaram depois da medicao (medido 2026-11-15T12:45:06-0300) |
| red-as-expected-speech-gate | STALE | 1 | 1 | 2026-11-15T12:45:12-0300 | speech-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:45:12-0300) |
| red-as-expected-theme-caption-identity | STALE | 1 | 1 | 2026-11-11T11:38:31-0300 | theme-caption-identity-neg.log | deps mudaram depois da medicao (medido 2026-11-11T11:38:31-0300) |
| caption-overlay-theme | STALE | 0 | 0 | 2026-11-15T17:22:10-0300 | caption-overlay-theme.log | deps mudaram depois da medicao (medido 2026-11-15T17:22:10-0300) |
| red-as-expected-caption-overlay-theme | STALE | 1 | 1 | 2026-11-15T17:22:44-0300 | caption-overlay-theme-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:22:44-0300) |
| panel-themes | STALE | 0 | 0 | 2026-11-15T11:47:03-0300 | panel-themes.log | deps mudaram depois da medicao (medido 2026-11-15T11:47:03-0300) |
| red-as-expected-panel-themes | STALE | 1 | 1 | 2026-11-15T11:48:03-0300 | panel-themes-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:48:03-0300) |
| red-as-expected-panel-history-clip | STALE | 1 | 1 | 2026-11-15T17:22:58-0300 | panel-history-clip-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:22:58-0300) |
| panel-pause-payload | STALE | 0 | 0 | 2026-11-15T17:22:58-0300 | panel-pause-payload.log | deps mudaram depois da medicao (medido 2026-11-15T17:22:58-0300) |
| red-as-expected-panel-pause-payload | STALE | 1 | 1 | 2026-11-15T17:22:59-0300 | panel-pause-payload-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:22:59-0300) |
| devlab-captions | STALE | 0 | 0 | 2026-11-15T11:48:12-0300 | devlab-captions.log | deps mudaram depois da medicao (medido 2026-11-15T11:48:12-0300) |
| red-as-expected-devlab-captions | STALE | 1 | 1 | 2026-11-15T11:48:17-0300 | devlab-captions-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:48:17-0300) |
| devlab-chaos | STALE | 0 | 0 | 2026-11-15T11:48:19-0300 | devlab-chaos.log | deps mudaram depois da medicao (medido 2026-11-15T11:48:19-0300) |
| red-as-expected-devlab-chaos | STALE | 1 | 1 | 2026-11-15T11:48:24-0300 | devlab-chaos-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:48:24-0300) |
| concurrent-workers | NOT RUN | - | 0 | - | concurrent-workers.log | sem registo no stepcache (o passo nao completou) |
| devlab-crosstalk | NOT RUN | - | 0 | - | devlab-crosstalk.log | sem registo no stepcache (o passo nao completou) |
| measurement-flags | STALE | 0 | 0 | 2026-11-15T17:23:02-0300 | measurement-flags.log | deps mudaram depois da medicao (medido 2026-11-15T17:23:02-0300) |
| red-as-expected-measurement-flags | STALE | 1 | 1 | 2026-11-15T17:23:51-0300 | measurement-flags-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:23:51-0300) |
| measurement-isolation | STALE | 0 | 0 | 2026-11-15T17:23:53-0300 | measurement-isolation.log | deps mudaram depois da medicao (medido 2026-11-15T17:23:53-0300) |
| red-as-expected-measurement-isolation | STALE | 1 | 1 | 2026-11-15T17:24:00-0300 | measurement-isolation-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:24:00-0300) |
| caption-wanted-default | STALE | 0 | 0 | 2026-11-15T17:24:01-0300 | caption-wanted-default.log | deps mudaram depois da medicao (medido 2026-11-15T17:24:01-0300) |
| red-as-expected-caption-wanted-default | STALE | 1 | 1 | 2026-11-15T17:24:03-0300 | caption-wanted-default-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:24:03-0300) |
| live-ack | STALE | 0 | 0 | 2026-11-15T17:24:06-0300 | live-ack.log | deps mudaram depois da medicao (medido 2026-11-15T17:24:06-0300) |
| red-as-expected-live-ack | STALE | 1 | 1 | 2026-11-15T17:24:55-0300 | live-ack-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:24:55-0300) |
| live-route | STALE | 0 | 0 | 2026-11-15T17:24:56-0300 | live-route.log | deps mudaram depois da medicao (medido 2026-11-15T17:24:56-0300) |
| red-as-expected-live-route | STALE | 1 | 1 | 2026-11-15T12:45:18-0300 | live-route-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:45:18-0300) |
| device-ladder-cost | STALE | 0 | 0 | 2026-11-15T12:45:19-0300 | device-ladder-cost.log | deps mudaram depois da medicao (medido 2026-11-15T12:45:19-0300) |
| red-as-expected-device-ladder-cost | STALE | 1 | 1 | 2026-11-15T12:45:25-0300 | device-ladder-cost-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:45:25-0300) |
| youtube-first-cue | STALE | 0 | 0 | 2026-11-15T17:24:58-0300 | youtube-first-cue.log | deps mudaram depois da medicao (medido 2026-11-15T17:24:58-0300) |
| red-as-expected-youtube-first-cue | STALE | 1 | 1 | 2026-11-15T17:25:01-0300 | youtube-first-cue-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:01-0300) |
| yt-clock-static | STALE | 0 | 0 | 2026-11-15T17:25:01-0300 | yt-clock-static.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:01-0300) |
| red-as-expected-yt-clock-static | STALE | 1 | 1 | 2026-11-15T17:25:03-0300 | yt-clock-static-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:03-0300) |
| startup-ui-thread-block | STALE | 0 | 0 | 2026-11-15T17:25:08-0300 | startup-ui-thread-block.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:08-0300) |
| red-as-expected-startup-ui-thread-block | STALE | 1 | 1 | 2026-11-15T17:25:28-0300 | startup-ui-thread-block-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:28-0300) |
| cost-watchdog | STALE | 0 | 0 | 2026-11-15T17:25:29-0300 | cost-watchdog.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:29-0300) |
| red-as-expected-cost-watchdog | STALE | 1 | 1 | 2026-11-15T17:25:38-0300 | cost-watchdog-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:38-0300) |
| warm-evidence | STALE | 0 | 0 | 2026-11-15T17:25:46-0300 | warm-evidence.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:46-0300) |
| red-as-expected-warm-evidence | STALE | 1 | 1 | 2026-11-15T17:25:49-0300 | warm-evidence-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:49-0300) |
| ui-watchdog | STALE | 0 | 0 | 2026-11-15T17:25:55-0300 | ui-watchdog.log | deps mudaram depois da medicao (medido 2026-11-15T17:25:55-0300) |
| red-as-expected-ui-watchdog | STALE | 1 | 1 | 2026-11-15T17:26:02-0300 | ui-watchdog-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:26:02-0300) |
| outside-click-timer | STALE | 0 | 0 | 2026-11-15T17:26:34-0300 | outside-click-timer.log | deps mudaram depois da medicao (medido 2026-11-15T17:26:34-0300) |
| red-as-expected-outside-click-timer | STALE | 1 | 1 | 2026-11-15T17:26:55-0300 | outside-click-timer-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:26:55-0300) |
| panel-deps | STALE | 0 | 0 | 2026-11-15T11:51:58-0300 | panel-deps.log | deps mudaram depois da medicao (medido 2026-11-15T11:51:58-0300) |
| red-as-expected-panel-deps | STALE | 0 | 0 | 2026-11-15T11:51:59-0300 | panel-deps-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:51:59-0300) |
| worker-death-trace | STALE | 0 | 0 | 2026-11-15T12:45:55-0300 | worker-death-trace.log | deps mudaram depois da medicao (medido 2026-11-15T12:45:55-0300) |
| red-as-expected-worker-death-trace | STALE | 1 | 1 | 2026-11-15T12:46:00-0300 | worker-death-trace-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:46:00-0300) |
| panel-live-box-oracle | STALE | 0 | 0 | 2026-11-15T11:52:10-0300 | panel-live-box-oracle.log | deps mudaram depois da medicao (medido 2026-11-15T11:52:10-0300) |
| border-radius-gate | STALE | 0 | 0 | 2026-11-11T03:11:41-0300 | border-radius-gate.log | deps mudaram depois da medicao (medido 2026-11-11T03:11:41-0300) |
| red-as-expected-border-radius-gate | STALE | 1 | 1 | 2026-11-11T03:11:42-0300 | border-radius-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-11T03:11:42-0300) |
| hidden-launch | PASS | 0 | 0 | 2026-11-05T14:47:36-0300 | hidden-launch.log | - |
| red-as-expected-hidden-launch | EXPECTED-RED | 1 | 1 | 2026-11-05T14:47:37-0300 | hidden-launch-neg.log | - |
| step-deadline | PASS | 0 | 0 | 2026-11-12T04:11:51-0300 | step-deadline.log | - |
| red-as-expected-step-deadline | EXPECTED-RED | 1 | 1 | 2026-11-12T04:12:04-0300 | step-deadline-neg.log | - |
| emit-prewebview | STALE | 0 | 0 | 2026-11-15T17:26:57-0300 | emit-prewebview.log | deps mudaram depois da medicao (medido 2026-11-15T17:26:57-0300) |
| red-as-expected-emit-prewebview | STALE | 1 | 1 | 2026-11-15T17:26:58-0300 | emit-prewebview-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:26:58-0300) |
| hotkey-live-edge | STALE | 0 | 0 | 2026-11-15T17:27:04-0300 | hotkey-live-edge.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:04-0300) |
| red-as-expected-hotkey-live-edge | STALE | 1 | 1 | 2026-11-15T17:27:10-0300 | hotkey-live-edge-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:10-0300) |
| lane-screen-gate | STALE | 0 | 0 | 2026-11-15T12:46:08-0300 | lane-screen-gate.log | deps mudaram depois da medicao (medido 2026-11-15T12:46:08-0300) |
| red-as-expected-lane-screen-gate | EXPECTED-RED | 1 | 1 | 2026-11-05T14:48:29-0300 | lane-screen-gate-neg.log | - |
| caption-dup-repro | STALE | 0 | 0 | 2026-11-15T17:27:11-0300 | caption-dup-repro.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:11-0300) |
| complaints-closure | PASS | 0 | 0 | 2026-11-15T11:52:28-0300 | complaints-closure.log | - |
| red-as-expected-complaints-closure | EXPECTED-RED | 1 | 1 | 2026-11-15T11:52:28-0300 | complaints-closure-neg.log | - |
| youtube-paint-first | STALE | 0 | 0 | 2026-11-15T17:27:12-0300 | youtube-paint-first.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:12-0300) |
| red-as-expected-youtube-paint-first | STALE | 1 | 1 | 2026-11-15T17:27:13-0300 | youtube-paint-first-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:13-0300) |
| youtube-foreign-paint | STALE | 0 | 0 | 2026-11-15T17:27:14-0300 | youtube-foreign-paint.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:14-0300) |
| red-as-expected-youtube-foreign-paint | STALE | 1 | 1 | 2026-11-15T17:27:15-0300 | youtube-foreign-paint-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:15-0300) |
| input-path | STALE | 0 | 0 | 2026-11-15T17:27:52-0300 | input-path.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:52-0300) |
| red-as-expected-input-path | STALE | 1 | 1 | 2026-11-15T17:27:54-0300 | input-path-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:54-0300) |
| exception-hygiene | STALE | 0 | 0 | 2026-11-15T17:27:57-0300 | exception-hygiene.log | deps mudaram depois da medicao (medido 2026-11-15T17:27:57-0300) |
| red-as-expected-exception-hygiene | EXPECTED-RED | 1 | 1 | 2026-11-15T11:53:15-0300 | exception-hygiene-neg.log | - |
| seam-coverage | STALE | 0 | 0 | 2026-11-15T17:28:47-0300 | seam-coverage.log | deps mudaram depois da medicao (medido 2026-11-15T17:28:47-0300) |
| red-as-expected-seam-coverage | EXPECTED-RED | 1 | 1 | 2026-11-12T17:17:32-0300 | seam-coverage-neg.log | - |
| bug-ledger | PASS | 0 | 0 | 2026-11-05T14:50:14-0300 | bug-ledger.log | - |
| red-as-expected-bug-ledger | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:15-0300 | bug-ledger-neg.log | - |
| tooling-intent | PASS | 0 | 0 | 2026-11-05T19:44:31-0300 | tooling-intent.log | - |
| red-as-expected-tooling-intent | EXPECTED-RED | 1 | 1 | 2026-11-05T19:44:32-0300 | tooling-intent-neg.log | - |
| external-resume | STALE | 0 | 0 | 2026-11-15T17:28:48-0300 | external-resume.log | deps mudaram depois da medicao (medido 2026-11-15T17:28:48-0300) |
| red-as-expected-external-resume | STALE | 1 | 1 | 2026-11-15T17:28:51-0300 | external-resume-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:28:51-0300) |
| external-resume-latch | STALE | 0 | 0 | 2026-11-15T17:28:52-0300 | external-resume-latch.log | deps mudaram depois da medicao (medido 2026-11-15T17:28:52-0300) |
| red-as-expected-external-resume-latch | STALE | 1 | 1 | 2026-11-15T17:28:52-0300 | external-resume-latch-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:28:52-0300) |
| silence-kill | STALE | 0 | 0 | 2026-11-15T17:28:53-0300 | silence-kill.log | deps mudaram depois da medicao (medido 2026-11-15T17:28:53-0300) |
| red-as-expected-silence-kill | STALE | 1 | 1 | 2026-11-15T17:28:54-0300 | silence-kill-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:28:54-0300) |
| worker-churn | STALE | 0 | 0 | 2026-11-15T17:28:57-0300 | worker-churn.log | deps mudaram depois da medicao (medido 2026-11-15T17:28:57-0300) |
| red-as-expected-worker-churn | STALE | 1 | 1 | 2026-11-15T17:29:01-0300 | worker-churn-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:01-0300) |
| worker-silence-grace | STALE | 0 | 0 | 2026-11-15T17:29:01-0300 | worker-silence-grace.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:01-0300) |
| red-as-expected-worker-silence-grace | STALE | 1 | 1 | 2026-11-15T17:29:02-0300 | worker-silence-grace-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:02-0300) |
| rss-trend | STALE | 0 | 0 | 2026-11-15T17:29:03-0300 | rss-trend.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:03-0300) |
| red-as-expected-rss-trend | EXPECTED-RED | 1 | 1 | 2026-11-05T14:50:32-0300 | rss-trend-neg.log | - |
| death-cause | STALE | 0 | 0 | 2026-11-15T17:29:04-0300 | death-cause.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:04-0300) |
| red-as-expected-death-cause | STALE | 1 | 1 | 2026-11-15T17:29:05-0300 | death-cause-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:05-0300) |
| caption-seam-dedup | STALE | 0 | 0 | 2026-11-15T12:46:30-0300 | caption-seam-dedup.log | deps mudaram depois da medicao (medido 2026-11-15T12:46:30-0300) |
| red-as-expected-caption-seam-dedup | STALE | 1 | 1 | 2026-11-15T12:46:31-0300 | caption-seam-dedup-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:46:31-0300) |
| freeze-census | PASS | 0 | 0 | 2026-11-11T03:14:20-0300 | freeze-census.log | - |
| red-as-expected-caption-budget | STALE | 1 | 1 | 2026-11-15T17:29:06-0300 | caption-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:06-0300) |
| dead-app-exit | STALE | 0 | 0 | 2026-11-15T17:29:26-0300 | dead-app-exit.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:26-0300) |
| exit-backstop | STALE | 0 | 0 | 2026-11-15T17:29:34-0300 | exit-backstop.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:34-0300) |
| red-as-expected-exit-backstop | STALE | 1 | 1 | 2026-11-15T17:29:43-0300 | exit-backstop-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:43-0300) |
| shell-priority | STALE | 0 | 0 | 2026-11-15T17:29:43-0300 | shell-priority.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:43-0300) |
| red-as-expected-shell-priority | STALE | 1 | 1 | 2026-11-15T17:29:44-0300 | shell-priority-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:44-0300) |
| tray-menu | STALE | 0 | 0 | 2026-11-15T17:29:45-0300 | tray-menu.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:45-0300) |
| red-as-expected-tray-menu | STALE | 1 | 1 | 2026-11-15T17:29:56-0300 | tray-menu-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:56-0300) |
| hotkey-panels-switch | STALE | 0 | 0 | 2026-11-15T17:29:57-0300 | hotkey-panels-switch.log | deps mudaram depois da medicao (medido 2026-11-15T17:29:57-0300) |
| red-as-expected-hotkey-panels-switch | STALE | 1 | 1 | 2026-11-15T17:30:00-0300 | hotkey-panels-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:00-0300) |
| caption-kept-on-hide | STALE | 0 | 0 | 2026-11-15T17:30:09-0300 | caption-kept-on-hide.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:09-0300) |
| red-as-expected-caption-kept-on-hide | STALE | 1 | 1 | 2026-11-15T17:30:19-0300 | caption-kept-on-hide-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:19-0300) |
| caption-switch-race | STALE | 0 | 0 | 2026-11-15T17:30:22-0300 | caption-switch-race.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:22-0300) |
| red-as-expected-caption-switch-race | STALE | 1 | 1 | 2026-11-15T17:30:22-0300 | caption-switch-race-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:22-0300) |
| word-glue | STALE | 0 | 0 | 2026-11-15T12:46:46-0300 | word-glue.log | deps mudaram depois da medicao (medido 2026-11-15T12:46:46-0300) |
| red-as-expected-word-glue | STALE | 1 | 1 | 2026-11-15T12:46:47-0300 | word-glue-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:46:47-0300) |
| punct-prosody | PASS | 0 | 0 | 2026-11-05T19:45:18-0300 | punct-prosody.log | - |
| red-as-expected-punct-prosody | EXPECTED-RED | 1 | 1 | 2026-11-05T19:45:19-0300 | punct-prosody-neg.log | - |
| punct-model | STALE | 0 | 0 | 2026-11-15T12:46:50-0300 | punct-model.log | deps mudaram depois da medicao (medido 2026-11-15T12:46:50-0300) |
| red-as-expected-punct-model | STALE | 1 | 1 | 2026-11-15T12:46:52-0300 | punct-model-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:46:52-0300) |
| panel-prefix-row | STALE | 0 | 0 | 2026-11-15T11:55:06-0300 | panel-prefix-row.log | deps mudaram depois da medicao (medido 2026-11-15T11:55:06-0300) |
| red-as-expected-panel-prefix-row | STALE | 1 | 1 | 2026-11-15T11:55:07-0300 | panel-prefix-row-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:55:07-0300) |
| panel-row-identity | STALE | 0 | 0 | 2026-11-15T11:55:11-0300 | panel-row-identity.log | deps mudaram depois da medicao (medido 2026-11-15T11:55:11-0300) |
| red-as-expected-panel-row-identity | STALE | 1 | 1 | 2026-11-15T11:55:35-0300 | panel-row-identity-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:55:35-0300) |
| history-classify | NOT RUN | - | 0 | - | history-classify.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-history-classify | EXPECTED-RED | 1 | 1 | 2026-11-15T12:47:01-0300 | history-classify-neg.log | - |
| fusion | PASS | 0 | 0 | 2026-11-15T11:55:38-0300 | fusion.log | - |
| red-as-expected-fusion | EXPECTED-RED | 1 | 1 | 2026-11-15T11:55:38-0300 | fusion-neg.log | - |
| agc-peak-ceiling | STALE | 0 | 0 | 2026-11-15T12:47:03-0300 | agc-peak-ceiling.log | deps mudaram depois da medicao (medido 2026-11-15T12:47:03-0300) |
| red-as-expected-agc-peak-ceiling | STALE | 1 | 1 | 2026-11-15T12:47:05-0300 | agc-peak-ceiling-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:47:05-0300) |
| reveal-park | STALE | 0 | 0 | 2026-11-15T17:30:27-0300 | reveal-park.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:27-0300) |
| red-as-expected-reveal-park | STALE | 1 | 1 | 2026-11-15T17:30:33-0300 | reveal-park-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:33-0300) |
| youtube-verbatim | STALE | 0 | 0 | 2026-11-15T17:30:35-0300 | youtube-verbatim.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:35-0300) |
| red-as-expected-youtube-verbatim | EXPECTED-RED | 1 | 1 | 2026-11-08T05:23:52-0300 | youtube-verbatim-neg.log | - |
| code-health | PASS | 0 | 0 | 2026-11-15T17:30:37-0300 | code-health.log | always |
| red-as-expected-code-health | EXPECTED-RED | 1 | 1 | 2026-11-15T17:30:39-0300 | code-health-neg.log | always |
| undefined-names | STALE | 0 | 0 | 2026-11-15T17:30:41-0300 | undefined-names.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:41-0300) |
| red-as-expected-undefined-names | EXPECTED-RED | 1 | 1 | 2026-11-15T17:30:41-0300 | undefined-names-neg.log | always |
| gaming-watcher-surface | NOT RUN | - | 0 | - | gaming-watcher-surface.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-gaming-watcher-surface | NOT RUN | - | 1 | - | gaming-watcher-surface-neg.log | sem registo no stepcache (o passo nao completou) |
| battery-heavy-gate | STALE | 0 | 0 | 2026-11-15T11:55:57-0300 | battery-heavy-gate.log | deps mudaram depois da medicao (medido 2026-11-15T11:55:57-0300) |
| red-as-expected-battery-heavy-gate | STALE | 1 | 1 | 2026-11-15T11:56:05-0300 | battery-heavy-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:56:05-0300) |
| task-resolver-gate | STALE | 0 | 0 | 2026-11-15T12:47:16-0300 | task-resolver-gate.log | deps mudaram depois da medicao (medido 2026-11-15T12:47:16-0300) |
| red-as-expected-task-resolver-gate | STALE | 1 | 1 | 2026-11-15T12:47:18-0300 | task-resolver-gate-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:47:18-0300) |
| claims-date | STALE | 0 | 0 | 2026-11-15T12:47:19-0300 | claims-date.log | deps mudaram depois da medicao (medido 2026-11-15T12:47:19-0300) |
| red-as-expected-claims-date | STALE | 1 | 1 | 2026-11-15T12:47:22-0300 | claims-date-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:47:22-0300) |
| stall-under-load | STALE | 0 | 0 | 2026-11-15T17:30:43-0300 | stall-under-load.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:43-0300) |
| red-as-expected-stall-under-load | EXPECTED-RED | 1 | 1 | 2026-11-15T17:30:43-0300 | stall-under-load-neg.log | always |
| paint-live-show | STALE | 0 | 0 | 2026-11-15T17:30:45-0300 | paint-live-show.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:45-0300) |
| boot-interaction | STALE | 0 | 0 | 2026-11-15T17:30:46-0300 | boot-interaction.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:46-0300) |
| red-as-expected-boot-interaction | EXPECTED-RED | 1 | 1 | 2026-11-15T17:30:46-0300 | boot-interaction-neg.log | always |
| boot-interaction-paint-arm | STALE | 1 | 1 | 2026-11-15T17:30:47-0300 | boot-interaction-paint-arm.log | deps mudaram depois da medicao (medido 2026-11-15T17:30:47-0300) |
| red-as-expected-paint-live-show | EXPECTED-RED | 1 | 1 | 2026-11-15T17:31:41-0300 | paint-live-show-neg.log | always |
| content-gate-probe | STALE | 1 | 1 | 2026-11-15T17:31:44-0300 | content-gate-probe-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:31:44-0300) |
| panel-paint-first-measure | NOT RUN | - | 0 | - | panel-paint-first-measure.log | sem registo no stepcache (o passo nao completou) |
| panel-paint-first | PASS | 0 | 0 | 2026-11-15T17:31:44-0300 | panel-paint-first.log | always |
| red-as-expected-panel-paint-first | EXPECTED-RED | 1 | 1 | 2026-11-15T17:31:45-0300 | panel-paint-first-neg.log | always |
| receipt-provenance | PASS | 0 | 0 | 2026-11-15T17:31:46-0300 | receipt-provenance.log | always |
| red-as-expected-receipt-provenance | EXPECTED-RED | 1 | 1 | 2026-11-15T17:31:46-0300 | receipt-provenance-neg.log | always |
| async-track-fetch | STALE | 0 | 0 | 2026-11-15T17:31:55-0300 | async-track-fetch.log | deps mudaram depois da medicao (medido 2026-11-15T17:31:55-0300) |
| red-as-expected-async-track-fetch | STALE | 1 | 1 | 2026-11-15T17:32:04-0300 | async-track-fetch-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:32:04-0300) |
| batch-queue-drain | STALE | 0 | 0 | 2026-11-12T14:41:54-0300 | batch-queue-drain.log | deps mudaram depois da medicao (medido 2026-11-12T14:41:54-0300) |
| red-as-expected-batch-queue-drain | STALE | 1 | 1 | 2026-11-12T14:42:05-0300 | batch-queue-drain-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:42:05-0300) |
| batch-executor-ceiling | STALE | 0 | 0 | 2026-11-12T14:42:10-0300 | batch-executor-ceiling.log | deps mudaram depois da medicao (medido 2026-11-12T14:42:10-0300) |
| red-as-expected-batch-executor-ceiling | STALE | 1 | 1 | 2026-11-12T14:42:12-0300 | batch-executor-ceiling-neg.log | deps mudaram depois da medicao (medido 2026-11-12T14:42:12-0300) |
| hotkey-live-toggle | STALE | 0 | 0 | 2026-11-15T17:32:15-0300 | hotkey-live-toggle.log | deps mudaram depois da medicao (medido 2026-11-15T17:32:15-0300) |
| red-as-expected-hotkey-live-toggle | STALE | 1 | 1 | 2026-11-15T17:33:14-0300 | hotkey-live-toggle-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:14-0300) |
| hotkey-spam | STALE | 0 | 0 | 2026-11-15T17:33:18-0300 | hotkey-spam.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:18-0300) |
| red-as-expected-hotkey-spam | STALE | 1 | 1 | 2026-11-15T17:33:29-0300 | hotkey-spam-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:29-0300) |
| loading-placeholder | STALE | 0 | 0 | 2026-11-15T17:33:30-0300 | loading-placeholder.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:30-0300) |
| red-as-expected-loading-placeholder | STALE | 1 | 1 | 2026-11-15T17:33:30-0300 | loading-placeholder-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:30-0300) |
| youtube-land | STALE | 0 | 0 | 2026-11-15T17:33:31-0300 | youtube-land.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:31-0300) |
| red-as-expected-youtube-land | STALE | 1 | 1 | 2026-11-15T11:58:18-0300 | youtube-land-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:58:18-0300) |
| time-to-first-caption | STALE | 0 | 0 | 2026-11-15T17:33:33-0300 | time-to-first-caption.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:33-0300) |
| red-as-expected-time-to-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-11T03:16:18-0300 | time-to-first-caption-neg.log | - |
| first-capture-fast | STALE | 0 | 0 | 2026-11-15T17:33:34-0300 | first-capture-fast.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:34-0300) |
| red-as-expected-first-capture-fast | STALE | 1 | 1 | 2026-11-15T17:33:38-0300 | first-capture-fast-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:38-0300) |
| youtube-land-replay | STALE | 0 | 0 | 2026-11-15T17:33:41-0300 | youtube-land-replay.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:41-0300) |
| red-as-expected-youtube-land-replay | STALE | 1 | 1 | 2026-11-15T17:33:44-0300 | youtube-land-replay-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:44-0300) |
| yt-loop-uia | STALE | 0 | 0 | 2026-11-15T17:33:45-0300 | yt-loop-uia.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:45-0300) |
| red-as-expected-yt-loop-uia | STALE | 1 | 1 | 2026-11-15T17:33:46-0300 | yt-loop-uia-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:46-0300) |
| yt-target-stale | STALE | 0 | 0 | 2026-11-15T17:33:50-0300 | yt-target-stale.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:50-0300) |
| red-as-expected-yt-target-stale | STALE | 1 | 1 | 2026-11-15T17:33:55-0300 | yt-target-stale-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:55-0300) |
| yt-source-singleton | STALE | 0 | 0 | 2026-11-15T17:33:55-0300 | yt-source-singleton.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:55-0300) |
| red-as-expected-yt-source-singleton | STALE | 1 | 1 | 2026-11-15T17:33:56-0300 | yt-source-singleton-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:33:56-0300) |
| cpu-tripwire | PASS | 0 | 0 | 2026-11-11T03:16:27-0300 | cpu-tripwire.log | - |
| red-as-expected-cpu-tripwire | EXPECTED-RED | 1 | 1 | 2026-11-11T03:16:27-0300 | cpu-tripwire-neg.log | - |
| owner-screen | STALE | 0 | 0 | 2026-11-15T17:34:03-0300 | owner-screen.log | deps mudaram depois da medicao (medido 2026-11-15T17:34:03-0300) |
| red-as-expected-owner-screen | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:38-0300 | owner-screen-neg.log | - |
| job-object | PASS | 0 | 0 | 2026-11-05T14:53:42-0300 | job-object.log | - |
| red-as-expected-job-object | EXPECTED-RED | 1 | 1 | 2026-11-05T14:53:45-0300 | job-object-neg.log | - |
| emit-pipe-dead | STALE | 0 | 0 | 2026-11-15T12:48:28-0300 | emit-pipe-dead.log | deps mudaram depois da medicao (medido 2026-11-15T12:48:28-0300) |
| red-as-expected-emit-pipe-dead | STALE | 1 | 1 | 2026-11-15T12:48:28-0300 | emit-pipe-dead-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:48:28-0300) |
| battery-wiring | STALE | 0 | 0 | 2026-11-15T11:58:53-0300 | battery-wiring.log | deps mudaram depois da medicao (medido 2026-11-15T11:58:53-0300) |
| red-as-expected-battery-wiring | STALE | 1 | 1 | 2026-11-15T11:59:03-0300 | battery-wiring-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:59:03-0300) |
| battery-record-pairing | STALE | 0 | 0 | 2026-11-15T11:59:04-0300 | battery-record-pairing.log | deps mudaram depois da medicao (medido 2026-11-15T11:59:04-0300) |
| red-as-expected-battery-record-pairing | STALE | 1 | 1 | 2026-11-15T11:59:04-0300 | battery-record-pairing-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:59:04-0300) |
| cage-once | STALE | 0 | 0 | 2026-11-15T11:59:06-0300 | cage-once.log | deps mudaram depois da medicao (medido 2026-11-15T11:59:06-0300) |
| red-as-expected-cage-once | STALE | 1 | 1 | 2026-11-15T11:59:06-0300 | cage-once-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:59:06-0300) |
| cage-rc | STALE | 0 | 0 | 2026-11-15T11:59:07-0300 | cage-rc.log | deps mudaram depois da medicao (medido 2026-11-15T11:59:07-0300) |
| red-as-expected-cage-rc | STALE | 1 | 1 | 2026-11-15T11:59:08-0300 | cage-rc-neg.log | deps mudaram depois da medicao (medido 2026-11-15T11:59:08-0300) |
| battery-run | PASS | 0 | 0 | 2026-11-12T14:43:21-0300 | battery-run.log | - |
| red-as-expected-battery-run | EXPECTED-RED | 1 | 1 | 2026-11-12T14:43:22-0300 | battery-run-neg.log | - |
| spec-citations | NOT RUN | - | 0 | - | spec-citations.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-spec-citations | NOT RUN | - | 1 | - | spec-citations-neg.log | sem registo no stepcache (o passo nao completou) |
| complaints-reconcile | PASS | 0 | 0 | 2026-11-15T17:34:15-0300 | complaints-reconcile.log | always |
| red-as-expected-complaints-reconcile | EXPECTED-RED | 1 | 1 | 2026-11-15T17:34:22-0300 | complaints-reconcile-neg.log | always |
| youtube-1to1 | STALE | 0 | 0 | 2026-11-15T17:34:23-0300 | youtube-1to1.log | deps mudaram depois da medicao (medido 2026-11-15T17:34:23-0300) |
| red-as-expected-youtube-1to1 | STALE | 1 | 1 | 2026-11-15T17:34:28-0300 | youtube-1to1-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:34:28-0300) |
| youtube-cdp-source | STALE | 0 | 0 | 2026-11-15T17:34:38-0300 | youtube-cdp-source.log | deps mudaram depois da medicao (medido 2026-11-15T17:34:38-0300) |
| red-as-expected-youtube-cdp-source | STALE | 1 | 1 | 2026-11-15T17:34:55-0300 | youtube-cdp-source-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:34:55-0300) |
| caption-producer | STALE | 0 | 0 | 2026-11-15T17:34:56-0300 | caption-producer.log | deps mudaram depois da medicao (medido 2026-11-15T17:34:56-0300) |
| red-as-expected-caption-producer | STALE | 1 | 1 | 2026-11-15T17:34:56-0300 | caption-producer-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:34:56-0300) |
| caption-style | STALE | 0 | 0 | 2026-11-15T17:34:57-0300 | caption-style.log | deps mudaram depois da medicao (medido 2026-11-15T17:34:57-0300) |
| red-as-expected-caption-style | STALE | 1 | 1 | 2026-11-15T17:35:01-0300 | caption-style-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:01-0300) |
| panel-commit-stable | STALE | 0 | 0 | 2026-11-15T17:35:19-0300 | panel-commit-stable.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:19-0300) |
| red-as-expected-panel-commit-stable | STALE | 1 | 1 | 2026-11-15T17:35:34-0300 | panel-commit-stable-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:34-0300) |
| paint-row-seam | STALE | 0 | 0 | 2026-11-15T17:35:35-0300 | paint-row-seam.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:35-0300) |
| red-as-expected-paint-row-seam | STALE | 1 | 1 | 2026-11-15T17:35:35-0300 | paint-row-seam-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:35-0300) |
| load-bg-window | STALE | 0 | 0 | 2026-11-15T17:35:36-0300 | load-bg-window.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:36-0300) |
| red-as-expected-load-bg-window | STALE | 1 | 1 | 2026-11-15T17:35:37-0300 | load-bg-window-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:37-0300) |
| page-scan-browser | STALE | 0 | 0 | 2026-11-15T17:35:38-0300 | page-scan-browser.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:38-0300) |
| red-as-expected-page-scan-browser | STALE | 1 | 1 | 2026-11-15T17:35:39-0300 | page-scan-browser-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:39-0300) |
| paused-pace | STALE | 0 | 0 | 2026-11-15T17:35:41-0300 | paused-pace.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:41-0300) |
| red-as-expected-paused-pace | STALE | 1 | 1 | 2026-11-15T17:35:43-0300 | paused-pace-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:43-0300) |
| stutter-caption | STALE | 0 | 0 | 2026-11-15T17:35:55-0300 | stutter-caption.log | deps mudaram depois da medicao (medido 2026-11-15T17:35:55-0300) |
| red-as-expected-stutter-caption | STALE | 1 | 1 | 2026-11-15T17:36:15-0300 | stutter-caption-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:15-0300) |
| parakeet-ultra-gpu-policy | NOT RUN | - | 0 | - | parakeet-ultra-gpu-policy.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-parakeet-ultra-gpu-policy | NOT RUN | - | 1 | - | parakeet-ultra-gpu-policy-neg.log | sem registo no stepcache (o passo nao completou) |
| speaker-sidecar-gpu-policy | NOT RUN | - | 0 | - | speaker-sidecar-gpu-policy.log | sem registo no stepcache (o passo nao completou) |
| parakeet-ultra | NOT RUN | - | 0 | - | parakeet-ultra.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-parakeet-ultra | STALE | 1 | 1 | 2026-11-15T17:36:15-0300 | parakeet-ultra-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:15-0300) |
| hotkey-observed | STALE | 0 | 0 | 2026-11-15T17:36:21-0300 | hotkey-observed.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:21-0300) |
| red-as-expected-hotkey-observed | STALE | 1 | 1 | 2026-11-15T17:36:22-0300 | hotkey-observed-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:22-0300) |
| youtube-reveal | STALE | 0 | 0 | 2026-11-15T17:36:24-0300 | youtube-reveal.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:24-0300) |
| red-as-expected-youtube-reveal | EXPECTED-RED | 1 | 1 | 2026-11-15T17:36:26-0300 | youtube-reveal-neg.log | always |
| youtube-rows | STALE | 0 | 0 | 2026-11-15T17:36:29-0300 | youtube-rows.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:29-0300) |
| red-as-expected-youtube-rows | STALE | 1 | 1 | 2026-11-15T17:36:31-0300 | youtube-rows-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:31-0300) |
| youtube-drift | PASS | 0 | 0 | 2026-11-15T17:36:32-0300 | youtube-drift.log | always |
| red-as-expected-youtube-drift | EXPECTED-RED | 1 | 1 | 2026-11-15T17:36:32-0300 | youtube-drift-neg.log | always |
| bend-laws | PASS | 0 | 0 | 2026-11-15T17:36:52-0300 | bend-laws.log | always |
| bend-laws-model | PASS | 0 | 0 | 2026-11-15T17:36:52-0300 | bend-laws-model.log | always |
| red-as-expected-bend-laws-model | EXPECTED-RED | 1 | 1 | 2026-11-15T17:36:53-0300 | bend-laws-model-neg.log | always |
| bend-mirror | STALE | 0 | 0 | 2026-11-15T17:36:54-0300 | bend-mirror.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:54-0300) |
| red-as-expected-bend-mirror | STALE | 1 | 1 | 2026-11-15T17:36:55-0300 | bend-mirror-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:36:55-0300) |
| bend-ledger-selftest | PASS | 0 | 0 | 2026-11-15T17:36:55-0300 | bend-ledger-selftest.log | always |
| panel-hidden-at-startup-oracle | STALE | 0 | 0 | 2026-11-15T17:37:41-0300 | panel-hidden-at-startup.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:41-0300) |
| red-as-expected-panel-hidden-at-startup | STALE | 1 | 1 | 2026-11-15T17:37:44-0300 | panel-hidden-at-startup-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:44-0300) |
| panel-nav-stall | STALE | 0 | 0 | 2026-11-15T17:37:44-0300 | panel-nav-stall.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:44-0300) |
| red-as-expected-panel-nav-stall | STALE | 1 | 1 | 2026-11-15T17:37:50-0300 | panel-nav-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:50-0300) |
| app-target | STALE | 0 | 0 | 2026-11-15T17:37:54-0300 | app-target.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:54-0300) |
| red-as-expected-app-target | STALE | 1 | 1 | 2026-11-15T17:37:55-0300 | app-target-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:55-0300) |
| worker-start-wiring | STALE | 0 | 0 | 2026-11-15T17:37:56-0300 | wiring-worker-start.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:56-0300) |
| red-as-expected-worker-start-wiring | STALE | 1 | 1 | 2026-11-15T17:37:58-0300 | wiring-worker-start-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:58-0300) |
| embedded-js-check | STALE | 0 | 0 | 2026-11-15T17:37:58-0300 | embedded-js.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:58-0300) |
| lane1-worker-default-arms | STALE | 0 | 0 | 2026-11-15T17:37:59-0300 | lane1-arms.log | deps mudaram depois da medicao (medido 2026-11-15T17:37:59-0300) |
| external-subs-stability | PASS | 0 | 0 | 2026-11-05T19:53:37-0300 | external-subs-stability.log | - |
| external-caption-chrome-census | STALE | 0 | 0 | 2026-11-15T17:38:00-0300 | external-caption-chrome-census.log | deps mudaram depois da medicao (medido 2026-11-15T17:38:00-0300) |
| external-caption-chrome-census-fixture | PASS | 0 | 0 | 2026-11-05T19:53:38-0300 | external-caption-chrome-census-fixture.log | - |
| external-subs-geometry-window | PASS | 0 | 0 | 2026-11-05T19:53:39-0300 | external-subs-geometry-window.log | - |
| youtube-captions | STALE | 0 | 0 | 2026-11-12T22:33:19-0300 | youtube-captions.log | deps mudaram depois da medicao (medido 2026-11-12T22:33:19-0300) |
| caption-native-wrap | STALE | 0 | 0 | 2026-11-15T12:03:16-0300 | caption-native-wrap.log | deps mudaram depois da medicao (medido 2026-11-15T12:03:16-0300) |
| yt-player-track | PASS | 0 | 0 | 2026-11-08T14:03:49-0300 | yt-player-track.log | - |
| yt-mirror-align | PASS | 0 | 0 | 2026-11-08T17:04:33-0300 | yt-mirror-align.log | - |
| red-as-expected-yt-mirror-align | EXPECTED-RED | 1 | 1 | 2026-11-08T17:04:35-0300 | yt-mirror-align-neg.log | - |
| shots-delta-oracle | PASS | 0 | 0 | 2026-11-05T14:58:09-0300 | shots-delta-oracle.log | - |
| red-as-expected-shots-delta-oracle | EXPECTED-RED | 1 | 1 | 2026-11-05T14:58:12-0300 | shots-delta-oracle-neg.log | - |
| gitattributes-verify | STALE | 0 | 0 | 2026-11-15T12:03:24-0300 | gitattributes-verify.log | deps mudaram depois da medicao (medido 2026-11-15T12:03:24-0300) |
| gitattributes-verify-arm | STALE | 0 | 0 | 2026-11-15T12:03:24-0300 | gitattributes-verify-arm.log | deps mudaram depois da medicao (medido 2026-11-15T12:03:24-0300) |
| mutant-tracking | PASS | 0 | 0 | 2026-11-15T12:03:25-0300 | mutant-tracking.log | - |
| red-as-expected-mutant-tracking | EXPECTED-RED | 1 | 1 | 2026-11-15T12:03:26-0300 | mutant-tracking-neg.log | - |
| agents-md-pins | STALE | 0 | 0 | 2026-11-15T12:52:35-0300 | agents-md-pins.log | deps mudaram depois da medicao (medido 2026-11-15T12:52:35-0300) |
| lang-id-oracle | STALE | 0 | 0 | 2026-11-15T12:53:14-0300 | lang-id-oracle.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:14-0300) |
| red-as-expected-lang-id-oracle | STALE | 1 | 1 | 2026-11-15T12:53:25-0300 | lang-id-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:25-0300) |
| model-spec-oracle | STALE | 0 | 0 | 2026-11-11T03:21:23-0300 | model-spec-oracle.log | deps mudaram depois da medicao (medido 2026-11-11T03:21:23-0300) |
| red-as-expected-model-spec-oracle | STALE | 1 | 1 | 2026-11-11T03:21:24-0300 | model-spec-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-11T03:21:24-0300) |
| scope-leak | STALE | 0 | 0 | 2026-11-05T14:59:16-0300 | scope-leak.log | deps mudaram depois da medicao (medido 2026-11-05T14:59:16-0300) |
| red-as-expected-scope-leak | STALE | 1 | 1 | 2026-11-05T14:59:18-0300 | scope-leak-neg.log | deps mudaram depois da medicao (medido 2026-11-05T14:59:18-0300) |
| panel-flash-contradiction | STALE | 0 | 0 | 2026-11-15T12:53:26-0300 | panel-flash-contradiction.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:26-0300) |
| red-as-expected-panel-flash-contradiction | STALE | 1 | 1 | 2026-11-15T12:53:26-0300 | panel-flash-contradiction-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:26-0300) |
| panel-flash-read | PASS | 0 | 0 | 2026-11-12T04:23:33-0300 | panel-flash-read.log | - |
| red-as-expected-panel-flash-read | EXPECTED-RED | 1 | 1 | 2026-11-12T04:23:34-0300 | panel-flash-read-neg.log | - |
| per-app-source-plumbing | STALE | 0 | 0 | 2026-11-15T12:53:27-0300 | per-app-source-plumbing.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:27-0300) |
| red-as-expected-per-app-source-plumbing | STALE | 1 | 1 | 2026-11-15T12:53:28-0300 | per-app-source-plumbing-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:28-0300) |
| redux-live-pending-cap | NOT RUN | - | 0 | - | redux-live-pending-cap.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-redux-live-pending-cap | NOT RUN | - | 1 | - | redux-live-pending-cap-neg.log | sem registo no stepcache (o passo nao completou) |
| redux-live-contract | STALE | 0 | 0 | 2026-11-15T12:03:44-0300 | redux-live-contract.log | deps mudaram depois da medicao (medido 2026-11-15T12:03:44-0300) |
| red-as-expected-redux-live-contract | STALE | 1 | 1 | 2026-11-15T12:03:44-0300 | redux-live-contract-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:03:44-0300) |
| stream-asr-gpu-census-lie | NOT RUN | - | 0 | - | stream-asr-gpu-census-lie.log | sem registo no stepcache (o passo nao completou) |
| stream-asr-gpu-only-policy | NOT RUN | - | 0 | - | stream-asr-gpu-only-policy.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-stream-asr-gpu-census | NOT RUN | - | 1 | - | stream-asr-gpu-census-neg.log | sem registo no stepcache (o passo nao completou) |
| word-split-oracle | STALE | 0 | 0 | 2026-11-15T12:53:28-0300 | word-split-oracle.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:28-0300) |
| red-as-expected-word-split-oracle | STALE | 1 | 1 | 2026-11-15T12:53:29-0300 | word-split-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:29-0300) |
| vad-option-probe | STALE | 0 | 0 | 2026-11-15T12:53:34-0300 | vad-option-probe.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:34-0300) |
| red-as-expected-vad-option-probe | STALE | 1 | 1 | 2026-11-15T12:53:35-0300 | vad-option-probe-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:53:35-0300) |
| youtube-track-wiring | STALE | 0 | 0 | 2026-11-15T17:38:06-0300 | youtube-track-wiring.log | deps mudaram depois da medicao (medido 2026-11-15T17:38:06-0300) |
| tap-open-timeout | STALE | 0 | 0 | 2026-11-15T17:38:40-0300 | tap-open-timeout.log | deps mudaram depois da medicao (medido 2026-11-15T17:38:40-0300) |
| ui-stall-oracle | STALE | 0 | 0 | 2026-11-15T17:38:47-0300 | ui-stall-oracle.log | deps mudaram depois da medicao (medido 2026-11-15T17:38:47-0300) |
| mute-audio | NOT RUN | - | 0 | - | mute-audio.log | sem registo no stepcache (o passo nao completou) |
| device-silence | NOT RUN | - | 0 | - | device-silence.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-device-silence | NOT RUN | - | 1 | - | device-silence-neg.log | sem registo no stepcache (o passo nao completou) |
| console-window-audit | PASS | 0 | 0 | 2026-11-15T17:39:38-0300 | console-window-audit.log | always |
| red-as-expected-console-window-audit | EXPECTED-RED | 1 | 1 | 2026-11-15T17:39:38-0300 | console-window-audit-neg.log | always |
| red-as-expected-console-window-watch | EXPECTED-RED | 1 | 1 | 2026-11-15T17:39:38-0300 | console-window-watch-neg.log | always |
| shell-orphans | PASS | 0 | 0 | 2026-11-15T17:39:43-0300 | shell-orphans.log | always |
| red-as-expected-shell-orphans | EXPECTED-RED | 1 | 1 | 2026-11-15T17:39:47-0300 | shell-orphans-neg.log | always |
| capture-exclude | STALE | 0 | 0 | 2026-11-15T17:39:47-0300 | capture-exclude.log | deps mudaram depois da medicao (medido 2026-11-15T17:39:47-0300) |
| red-as-expected-capture-exclude | STALE | 1 | 1 | 2026-11-15T17:39:48-0300 | capture-exclude-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:39:48-0300) |
| history-merge | STALE | 0 | 0 | 2026-11-15T17:39:48-0300 | history-merge.log | deps mudaram depois da medicao (medido 2026-11-15T17:39:48-0300) |
| red-as-expected-history-merge | STALE | 1 | 1 | 2026-11-15T17:39:50-0300 | history-merge-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:39:50-0300) |
| fusion-wire | STALE | 0 | 0 | 2026-11-15T17:39:54-0300 | fusion-wire.log | deps mudaram depois da medicao (medido 2026-11-15T17:39:54-0300) |
| red-as-expected-fusion-wire | STALE | 1 | 1 | 2026-11-15T17:39:57-0300 | fusion-wire-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:39:57-0300) |
| fusion-audio | STALE | 0 | 0 | 2026-11-15T17:39:57-0300 | fusion-audio.log | deps mudaram depois da medicao (medido 2026-11-15T17:39:57-0300) |
| red-as-expected-fusion-audio | STALE | 1 | 1 | 2026-11-15T17:39:59-0300 | fusion-audio-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:39:59-0300) |
| nemotron-preload | NOT RUN | - | 0 | - | nemotron-preload.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-nemotron-preload | NOT RUN | - | 1 | - | nemotron-preload-neg.log | sem registo no stepcache (o passo nao completou) |
| history-context | STALE | 0 | 0 | 2026-11-15T17:40:00-0300 | history-context.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:00-0300) |
| red-as-expected-history-context | STALE | 1 | 1 | 2026-11-15T17:40:06-0300 | history-context-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:06-0300) |
| history-via-filter | STALE | 0 | 0 | 2026-11-15T17:40:06-0300 | history-via-filter.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:06-0300) |
| red-as-expected-history-via-filter | STALE | 1 | 1 | 2026-11-15T17:40:07-0300 | history-via-filter-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:07-0300) |
| history-route | STALE | 0 | 0 | 2026-11-15T17:40:07-0300 | history-route.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:07-0300) |
| history-route-long | STALE | 0 | 0 | 2026-11-15T17:40:10-0300 | history-route-long.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:10-0300) |
| prose-punct | STALE | 0 | 0 | 2026-11-15T17:40:16-0300 | prose-punct.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:16-0300) |
| red-as-expected-prose-punct | STALE | 1 | 1 | 2026-11-15T17:40:18-0300 | prose-punct-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:18-0300) |
| text-normalize | STALE | 0 | 0 | 2026-11-15T17:40:20-0300 | text-normalize.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:20-0300) |
| red-as-expected-text-normalize | STALE | 1 | 1 | 2026-11-15T17:40:22-0300 | text-normalize-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:22-0300) |
| reveal-clock | STALE | 0 | 0 | 2026-11-15T17:40:24-0300 | reveal-clock.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:24-0300) |
| red-as-expected-reveal-clock | STALE | 1 | 1 | 2026-11-15T17:40:26-0300 | reveal-clock-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:26-0300) |
| tap-first-block | STALE | 0 | 0 | 2026-11-15T17:40:27-0300 | tap-first-block.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:27-0300) |
| red-as-expected-tap-first-block | STALE | 1 | 1 | 2026-11-15T17:40:28-0300 | tap-first-block-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:28-0300) |
| owner-audio-gate | PASS | 0 | 0 | 2026-11-15T17:40:29-0300 | owner-audio-gate.log | always |
| red-as-expected-owner-audio-gate | EXPECTED-RED | 1 | 1 | 2026-11-15T17:40:30-0300 | owner-audio-gate-neg.log | always |
| worker-providers | STALE | 0 | 0 | 2026-11-15T17:40:31-0300 | worker-providers.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:31-0300) |
| red-as-expected-worker-providers | STALE | 1 | 1 | 2026-11-15T17:40:32-0300 | worker-providers-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:32-0300) |
| review-f1f3 | STALE | 0 | 0 | 2026-11-15T17:40:33-0300 | review-f1f3.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:33-0300) |
| review-tapstop | PASS | 0 | 0 | 2026-11-12T03:31:30-0300 | review-tapstop.log | - |
| strip-surface-oracle | STALE | 0 | 0 | 2026-11-15T17:40:55-0300 | strip-surface-oracle.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:55-0300) |
| strip-width | STALE | 0 | 0 | 2026-11-15T17:40:56-0300 | strip-width.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:56-0300) |
| red-as-expected-strip-width | STALE | 1 | 1 | 2026-11-15T17:40:59-0300 | strip-width-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:40:59-0300) |
| strip-stats-log-budget | NOT RUN | - | 0 | - | strip-stats-log.log | sem registo no stepcache (o passo nao completou) |
| strip-hot-reload | STALE | 0 | 0 | 2026-11-15T17:41:13-0300 | strip-reload.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:13-0300) |
| strip-surface-runtime | NOT RUN | - | 0 | - | strip-surface.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-strip-surface | NOT RUN | - | 1 | - | strip-surface-neg.log | sem registo no stepcache (o passo nao completou) |
| engine-commit-cycles | NOT RUN | - | 0 | - | engine-commit-cycles.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-engine-commit-cycles | NOT RUN | - | 1 | - | engine-commit-cycles-neg.log | sem registo no stepcache (o passo nao completou) |
| strip-geometry-restore | NOT RUN | - | 0 | - | strip-restore.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-wave | NOT RUN | - | 0 | - | strip-stats.log | sem registo no stepcache (o passo nao completou) |
| strip-stats-load-oracle | PASS | 0 | 0 | 2026-11-05T15:01:18-0300 | strip-stats-load-oracle.log | - |
| hotkey-registration | PASS | 0 | 0 | 2026-11-15T17:41:15-0300 | hotkey-registration.log | always |
| hotkey-delivery | STALE | 0 | 0 | 2026-11-15T17:41:15-0300 | hotkey-delivery.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:15-0300) |
| open-close-stall | STALE | 0 | 0 | 2026-11-15T17:41:20-0300 | open-close-stall.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:20-0300) |
| red-as-expected-open-close-stall | STALE | 1 | 1 | 2026-11-15T17:41:32-0300 | open-close-stall-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:32-0300) |
| autostart-status | STALE | 0 | 0 | 2026-11-15T17:41:38-0300 | autostart-status.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:38-0300) |
| control-verdict-gate-unguard | STALE | 0 | 0 | 2026-11-15T13:00:35-0300 | control-verdict-gate-unguard.log | deps mudaram depois da medicao (medido 2026-11-15T13:00:35-0300) |
| control-history-producer-stamp-nvidia | STALE | 0 | 0 | 2026-11-15T13:00:35-0300 | control-history-producer-stamp-nvidia.log | deps mudaram depois da medicao (medido 2026-11-15T13:00:35-0300) |
| control-redux-flag-neg-arm | STALE | 0 | 0 | 2026-11-15T17:41:40-0300 | control-redux-flag-neg-arm.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:40-0300) |
| control-panel-exit3-neg-arm | NOT RUN | - | 0 | - | control-panel-exit3-neg-arm.log | sem registo no stepcache (o passo nao completou) |
| control-wasapi-com-init | PASS | 0 | 0 | 2026-11-12T03:33:05-0300 | control-wasapi-com-init.log | - |
| control-panel2-repeat-revert | STALE | 0 | 0 | 2026-11-15T12:06:28-0300 | control-panel2-repeat-revert.log | deps mudaram depois da medicao (medido 2026-11-15T12:06:28-0300) |
| control-history-gallery-neg-arm | PASS | 0 | 0 | 2026-11-05T15:01:45-0300 | control-history-gallery-neg-arm.log | - |
| red-as-expected-historico-gate-off | STALE | 1 | 1 | 2026-11-11T11:52:10-0300 | control-historico-gate-off.log | deps mudaram depois da medicao (medido 2026-11-11T11:52:10-0300) |
| search-oracle | STALE | 0 | 0 | 2026-11-15T17:41:43-0300 | search-oracle.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:43-0300) |
| red-as-expected-search-oracle | STALE | 1 | 1 | 2026-11-15T17:41:48-0300 | search-oracle-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:48-0300) |
| panel-search-keyboard | STALE | 0 | 0 | 2026-11-15T17:41:50-0300 | panel-search-keyboard.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:50-0300) |
| red-as-expected-panel-search-keyboard | STALE | 1 | 1 | 2026-11-15T17:41:52-0300 | panel-search-keyboard-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:41:52-0300) |
| fresh-processor-probe | STALE | 0 | 0 | 2026-11-15T13:00:41-0300 | fresh-processor.log | deps mudaram depois da medicao (medido 2026-11-15T13:00:41-0300) |
| stepcache-oracle | PASS | 0 | 0 | 2026-11-12T17:26:28-0300 | stepcache-oracle.log | - |
| battery-plan | STALE | 0 | 0 | 2026-11-15T17:42:04-0300 | battery-plan.log | deps mudaram depois da medicao (medido 2026-11-15T17:42:04-0300) |
| red-as-expected-battery-plan | EXPECTED-RED | 1 | 1 | 2026-11-15T17:42:41-0300 | battery-plan-neg.log | always |
| skip-verdict-guard | PASS | 0 | 0 | 2026-11-15T17:42:42-0300 | _skip-guard.log | always |
| altc-first-caption | NOT RUN | - | 0 | - | altc-first-caption.log | sem registo no stepcache (o passo nao completou) |
| altc-gesture | STALE | 0 | 0 | 2026-11-15T17:42:44-0300 | altc-gesture.log | deps mudaram depois da medicao (medido 2026-11-15T17:42:44-0300) |
| headphone-cut | STALE | 0 | 0 | 2026-11-15T17:43:45-0300 | headphone-cut.log | deps mudaram depois da medicao (medido 2026-11-15T17:43:45-0300) |
| incomplete-word | STALE | 0 | 0 | 2026-11-15T17:43:46-0300 | incomplete-word.log | deps mudaram depois da medicao (medido 2026-11-15T17:43:46-0300) |
| ladder-signal | STALE | 0 | 0 | 2026-11-15T17:43:46-0300 | ladder-signal.log | deps mudaram depois da medicao (medido 2026-11-15T17:43:46-0300) |
| ladder-try-instrument | STALE | 0 | 0 | 2026-11-15T17:43:47-0300 | ladder-try-instrument.log | deps mudaram depois da medicao (medido 2026-11-15T17:43:47-0300) |
| red-as-expected-ladder-try-instrument | STALE | 1 | 1 | 2026-11-15T17:43:48-0300 | ladder-try-instrument-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:43:48-0300) |
| audio-back-detector | STALE | 0 | 0 | 2026-11-15T17:43:51-0300 | audio-back-detector.log | deps mudaram depois da medicao (medido 2026-11-15T17:43:51-0300) |
| red-as-expected-audio-back-detector | STALE | 1 | 1 | 2026-11-15T17:44:19-0300 | audio-back-detector-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:44:19-0300) |
| boot-profile | STALE | 0 | 0 | 2026-11-15T17:44:21-0300 | boot-profile.log | deps mudaram depois da medicao (medido 2026-11-15T17:44:21-0300) |
| red-as-expected-boot-profile | STALE | 1 | 1 | 2026-11-15T17:44:22-0300 | boot-profile-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:44:22-0300) |
| launch-as-token | PASS | 0 | 0 | 2026-11-15T17:44:36-0300 | launch-as-token.log | always |
| live-code-freshness | STALE | 0 | 0 | 2026-11-15T17:44:38-0300 | live-code-freshness.log | deps mudaram depois da medicao (medido 2026-11-15T17:44:38-0300) |
| live-code-freshness-control | STALE | 0 | 0 | 2026-11-15T17:44:39-0300 | live-code-freshness-control.log | deps mudaram depois da medicao (medido 2026-11-15T17:44:39-0300) |
| red-as-expected-live-code-freshness | EXPECTED-RED | 1 | 1 | 2026-11-15T17:44:39-0300 | live-code-freshness-neg.log | always |
| load-shedding | STALE | 0 | 0 | 2026-11-15T17:44:47-0300 | load-shedding.log | deps mudaram depois da medicao (medido 2026-11-15T17:44:47-0300) |
| red-as-expected-altc-first-caption | EXPECTED-RED | 1 | 1 | 2026-11-15T17:44:47-0300 | altc-first-caption-neg.log | always |
| red-as-expected-altc-gesture | STALE | 1 | 1 | 2026-11-15T17:45:13-0300 | altc-gesture-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:45:13-0300) |
| red-as-expected-headphone-cut | EXPECTED-RED | 1 | 1 | 2026-11-15T17:45:14-0300 | headphone-cut-neg.log | always |
| red-as-expected-incomplete-word | EXPECTED-RED | 1 | 1 | 2026-11-15T17:45:15-0300 | incomplete-word-neg.log | always |
| red-as-expected-ladder-signal | STALE | 1 | 1 | 2026-11-15T17:45:16-0300 | ladder-signal-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:45:16-0300) |
| red-as-expected-launch-as-token | EXPECTED-RED | 1 | 1 | 2026-11-15T17:45:18-0300 | launch-as-token-neg.log | always |
| nemotron-weights | PASS | 0 | 0 | 2026-11-15T17:45:19-0300 | nemotron-weights.log | always |
| red-as-expected-nemotron-weights | EXPECTED-RED | 1 | 1 | 2026-11-15T17:45:29-0300 | nemotron-weights-neg.log | always |
| red-as-expected-load-shedding | STALE | 1 | 1 | 2026-11-15T17:46:43-0300 | load-shedding-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:46:43-0300) |
| red-as-expected-shell-relaunch | NOT RUN | - | 1 | - | shell-relaunch-neg.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-word-clock | STALE | 1 | 1 | 2026-11-15T17:46:46-0300 | word-clock-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:46:46-0300) |
| red-as-expected-youtube-monotonic | STALE | 1 | 1 | 2026-11-15T17:46:47-0300 | youtube-monotonic-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:46:47-0300) |
| red-as-expected-youtube-sotto-drift | EXPECTED-RED | 1 | 1 | 2026-11-15T17:46:49-0300 | youtube-sotto-drift-neg.log | always |
| red-as-expected-youtube-switch | STALE | 1 | 1 | 2026-11-15T17:46:53-0300 | youtube-switch-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:46:53-0300) |
| red-as-expected-yt-no-dub | EXPECTED-RED | 1 | 1 | 2026-11-15T17:46:54-0300 | yt-no-dub-neg.log | always |
| shell-relaunch | NOT RUN | - | 0 | - | shell-relaunch.log | sem registo no stepcache (o passo nao completou) |
| census-instrument | STALE | 0 | 0 | 2026-11-15T17:46:55-0300 | census-instrument.log | deps mudaram depois da medicao (medido 2026-11-15T17:46:55-0300) |
| red-as-expected-census-instrument | STALE | 1 | 1 | 2026-11-15T17:46:56-0300 | census-instrument-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:46:56-0300) |
| relaunch-ready | PASS | 0 | 0 | 2026-11-11T11:57:36-0300 | relaunch-ready.log | - |
| red-as-expected-relaunch-ready | EXPECTED-RED | 1 | 1 | 2026-11-11T11:57:50-0300 | relaunch-ready-neg.log | - |
| word-clock | STALE | 0 | 0 | 2026-11-15T17:47:04-0300 | word-clock.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:04-0300) |
| youtube-monotonic | STALE | 0 | 0 | 2026-11-15T17:47:08-0300 | youtube-monotonic.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:08-0300) |
| youtube-rate | STALE | 0 | 0 | 2026-11-15T17:47:11-0300 | youtube-rate.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:11-0300) |
| red-as-expected-youtube-rate | STALE | 1 | 1 | 2026-11-15T17:47:14-0300 | youtube-rate-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:14-0300) |
| click-through-applied | STALE | 0 | 0 | 2026-11-15T17:47:16-0300 | click-through-applied.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:16-0300) |
| red-as-expected-click-through-applied | STALE | 1 | 1 | 2026-11-15T17:47:18-0300 | click-through-applied-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:18-0300) |
| topmost-keepalive | PASS | 0 | 0 | 2026-11-15T17:47:19-0300 | topmost-keepalive.log | always |
| red-as-expected-topmost-keepalive | EXPECTED-RED | 1 | 1 | 2026-11-15T17:47:20-0300 | topmost-keepalive-neg.log | always |
| z-order | STALE | 0 | 0 | 2026-11-15T17:47:24-0300 | z-order.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:24-0300) |
| red-as-expected-z-order | STALE | 1 | 1 | 2026-11-15T17:47:39-0300 | z-order-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:39-0300) |
| webview2-args-scope | STALE | 0 | 0 | 2026-11-15T17:47:40-0300 | webview2-args-scope.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:40-0300) |
| red-as-expected-webview2-args-scope | STALE | 1 | 1 | 2026-11-15T17:47:42-0300 | webview2-args-scope-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:42-0300) |
| webview2-runtime | PASS | 0 | 0 | 2026-11-15T17:47:46-0300 | webview2-runtime.log | always |
| red-as-expected-webview2-runtime | EXPECTED-RED | 1 | 1 | 2026-11-15T17:47:48-0300 | webview2-runtime-neg.log | always |
| power-recovery | STALE | 0 | 0 | 2026-11-15T17:47:53-0300 | power-recovery.log | deps mudaram depois da medicao (medido 2026-11-15T17:47:53-0300) |
| red-as-expected-power-recovery | STALE | 1 | 1 | 2026-11-15T17:48:01-0300 | power-recovery-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:01-0300) |
| power-recovery-live | NOT RUN | - | 0 | - | power-recovery-live.log | sem registo no stepcache (o passo nao completou) |
| youtube-sotto-drift | PASS | 0 | 0 | 2026-11-15T17:48:05-0300 | youtube-sotto-drift.log | always |
| youtube-switch | STALE | 0 | 0 | 2026-11-15T17:48:08-0300 | youtube-switch.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:08-0300) |
| yt-no-dub | STALE | 0 | 0 | 2026-11-15T17:48:10-0300 | yt-no-dub.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:10-0300) |
| stale-display | STALE | 0 | 0 | 2026-11-15T17:48:14-0300 | stale-display.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:14-0300) |
| red-as-expected-stale-display | STALE | 1 | 1 | 2026-11-15T17:48:18-0300 | stale-display-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:18-0300) |
| battery-class | STALE | 0 | 0 | 2026-11-15T17:48:23-0300 | battery-class.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:23-0300) |
| red-as-expected-battery-class | STALE | 1 | 1 | 2026-11-15T17:48:29-0300 | battery-class-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:29-0300) |
| live-queue | STALE | 0 | 0 | 2026-11-15T17:48:35-0300 | live-queue.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:35-0300) |
| red-as-expected-live-queue | STALE | 1 | 1 | 2026-11-15T17:48:40-0300 | live-queue-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:40-0300) |
| flat-endpoint | PASS | 0 | 0 | 2026-11-15T17:48:44-0300 | flat-endpoint.log | always |
| tap-silent-desktop | STALE | 0 | 0 | 2026-11-15T17:48:46-0300 | tap-silent-desktop.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:46-0300) |
| red-as-expected-tap-silent-desktop | STALE | 1 | 1 | 2026-11-15T17:48:48-0300 | tap-silent-desktop-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:48:48-0300) |
| warm-engine | STALE | 0 | 0 | 2026-11-15T17:49:10-0300 | warm-engine.log | deps mudaram depois da medicao (medido 2026-11-15T17:49:10-0300) |
| red-as-expected-warm-engine | STALE | 1 | 1 | 2026-11-15T17:49:32-0300 | warm-engine-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:49:32-0300) |
| warm-engine-task | STALE | 0 | 0 | 2026-11-15T17:49:38-0300 | warm-engine-task.log | deps mudaram depois da medicao (medido 2026-11-15T17:49:38-0300) |
| red-as-expected-warm-engine-task | STALE | 1 | 1 | 2026-11-15T17:49:44-0300 | warm-engine-task-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:49:44-0300) |
| gaming-hotkey | STALE | 0 | 0 | 2026-11-15T17:50:06-0300 | gaming-hotkey.log | deps mudaram depois da medicao (medido 2026-11-15T17:50:06-0300) |
| red-as-expected-gaming-hotkey | STALE | 1 | 1 | 2026-11-15T17:51:23-0300 | gaming-hotkey-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:51:23-0300) |
| ctrlspace-swallow | STALE | 0 | 0 | 2026-11-15T17:51:28-0300 | ctrlspace-swallow.log | deps mudaram depois da medicao (medido 2026-11-15T17:51:28-0300) |
| red-as-expected-ctrlspace-swallow | STALE | 1 | 1 | 2026-11-15T17:52:18-0300 | ctrlspace-swallow-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:52:18-0300) |
| ctrlspace-swallow-os | PASS | 0 | 0 | 2026-11-15T17:52:19-0300 | ctrlspace-swallow-os.log | always |
| process-target | STALE | 0 | 0 | 2026-11-15T17:52:27-0300 | process-target.log | deps mudaram depois da medicao (medido 2026-11-15T17:52:27-0300) |
| red-as-expected-process-target | STALE | 1 | 1 | 2026-11-15T17:52:34-0300 | process-target-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:52:34-0300) |
| audio-ring | STALE | 0 | 0 | 2026-11-15T13:09:27-0300 | audio-ring.log | deps mudaram depois da medicao (medido 2026-11-15T13:09:27-0300) |
| red-as-expected-audio-ring | STALE | 1 | 1 | 2026-11-15T13:09:28-0300 | audio-ring-neg.log | deps mudaram depois da medicao (medido 2026-11-15T13:09:28-0300) |
| audio-ring-loss | NOT RUN | - | 0 | - | audio-ring-loss.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-audio-ring-loss | NOT RUN | - | 1 | - | audio-ring-loss-neg.log | sem registo no stepcache (o passo nao completou) |
| tap-delivery-stall | NOT RUN | - | 0 | - | tap-delivery-stall.log | sem registo no stepcache (o passo nao completou) |
| red-as-expected-tap-delivery-stall | NOT RUN | - | 1 | - | tap-delivery-stall-neg.log | sem registo no stepcache (o passo nao completou) |
| tap-stall-watchdog | NOT RUN | - | 0 | - | tap-stall-watchdog.log | sem registo no stepcache (o passo nao completou) |
| spec-coverage | NO-VERDICT | 0 | 0 | 2026-11-12T19:28:25-0300 | spec-coverage.log | log alterado depois do registo |
| red-as-expected-spec-coverage | NO-VERDICT | 1 | 1 | 2026-11-12T19:28:26-0300 | spec-coverage-neg.log | log alterado depois do registo |
| external-owner | STALE | 0 | 0 | 2026-11-15T17:52:41-0300 | external-owner.log | deps mudaram depois da medicao (medido 2026-11-15T17:52:41-0300) |
| red-as-expected-external-owner | STALE | 1 | 1 | 2026-11-15T17:52:44-0300 | external-owner-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:52:44-0300) |
| red-as-expected-youtube-track-wiring | STALE | 1 | 1 | 2026-11-15T17:52:46-0300 | youtube-track-wiring-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:52:46-0300) |
| state-page-write | STALE | 0 | 0 | 2026-11-15T17:52:55-0300 | state-page-write.log | deps mudaram depois da medicao (medido 2026-11-15T17:52:55-0300) |
| state-page | STALE | 0 | 0 | 2026-11-15T17:53:06-0300 | state-page.log | deps mudaram depois da medicao (medido 2026-11-15T17:53:06-0300) |
| red-as-expected-state-page | STALE | 1 | 1 | 2026-11-15T17:54:20-0300 | state-page-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:54:20-0300) |
| battery-budget | STALE | 0 | 0 | 2026-11-15T17:54:21-0300 | battery-budget.log | deps mudaram depois da medicao (medido 2026-11-15T17:54:21-0300) |
| red-as-expected-battery-budget | STALE | 1 | 1 | 2026-11-15T17:54:22-0300 | battery-budget-neg.log | deps mudaram depois da medicao (medido 2026-11-15T17:54:22-0300) |
| battery-launch | STALE | 0 | 0 | 2026-11-15T12:14:26-0300 | battery-launch.log | deps mudaram depois da medicao (medido 2026-11-15T12:14:26-0300) |
| red-as-expected-battery-launch | STALE | 1 | 1 | 2026-11-15T12:14:26-0300 | battery-launch-neg.log | deps mudaram depois da medicao (medido 2026-11-15T12:14:26-0300) |

## Como ler

| estado | significa |
| --- | --- |
| `PASS` | rc igual ao esperado, log com o sha256 registado, deps inalteradas |
| `EXPECTED-RED` | rc de braço negativo como esperado **e** o token exigido está no log |
| `FAIL` | rc diferente do esperado — inclui um braço negativo que ficou verde |
| `STALE` | correu bem, mas as deps mudaram depois: o verde é sobre bytes que já não existem |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo: o passo não correu, ou não completou |
