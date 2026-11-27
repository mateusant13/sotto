# Codeintel worker findings adjudication — v1 (2026-11-27)

- Source JSON: `I:/cc-tmp/ci-worker2.json`
- Exact producer command: `py -3 -m codeintel full H:/sotto --scope worker --max-population-files 4000 --json` (rc 2, 82.27 s, 319 raw findings)
- Scope: `H:/sotto/worker/**`. Dedupe key: `file,line,class` → 281 unique findings. The table below covers all 281 unique keys: 231 high/medium rows adjudicated in v1 + 50 info rows appended in this pass.
- Line numbers are the pre-edit positions reported by the JSON (code read at `H:/sotto`, edits applied only in the isolated worktree).
- EOL dialect: this artifact is written with **LF** bytes.
- `beam-exploration` skill was not installed in this session; every row was adjudicated by reading the source directly.

## Accounting (dedupe key `file,line,class`)

| Quantity | Count | Basis |
| --- | --- | --- |
| raw findings | 319 | 138 high + 97 medium + 84 info |
| unique keys (`file,line,class`) | 281 | 319 − 38 duplicate rows |
| adjudicated before this pass | 231 rows | 235 raw high/medium; 4 raw rows are duplicate keys |
| appended in this pass | 50 rows | 50 unique info keys (84 raw info findings) |
| adjudicated after this pass | 281 rows | all unique keys; 0 unadjudicated |

- Precision on **unique keys**: REAL / (REAL + NOISE) = 13 / (13 + 252) = 4.91%; denominator = 265 unique keys with a REAL or NOISE verdict (16 CANNOT-JUDGE keys excluded).
- The 4 duplicate high/medium raw rows are 3 copies each of two keys already in the table: `worker/inspect_model.py:5:DEFAULT-PATH-DRIFT`, `worker/unified_asr.py:41:DEFAULT-PATH-DRIFT`; the other 34 duplicate rows are info repeats of the 50 appended keys.

| file:line | class | verdict | one-line reason |
| --- | --- | --- | --- |
| `worker/_prefix_audioflag.py:292` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_prefix_audioflag.py:297` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_prefix_audioflag.py:303` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_prefix_audioflag.py:499` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_prefix_audioflag.py:1542` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_prefix_audioflag.py:2122` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/_prefix_audioflag.py:2180` | TYPED-FIELD-GUARD | NOISE | isinstance(int,float) guard precedes the float() coercion |
| `worker/_prefix_audioflag.py:2182` | TYPED-FIELD-GUARD | NOISE | isinstance(int,float) guard precedes the float() coercion |
| `worker/_prefix_audioflag.py:3038` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_prefix_audioflag.py:4244` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_probe/boot-control.py:39` | SUBPROCESS-NO-TIMEOUT | REAL | subprocess.run() has no timeout= ceiling for a hung child |
| `worker/_probe/boot-control.py:50` | SUBPROCESS-NO-TIMEOUT | REAL | subprocess.run() has no timeout= ceiling for a hung child |
| `worker/_probe/diag.py:35` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/_probe/idle-cpu-genai.py:109` | SUBPROCESS-NO-TIMEOUT | REAL | subprocess.run() has no timeout= ceiling for a hung child |
| `worker/_probe/idle-cpu-parakeet.py:54` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/_probe/idle-cpu-spin.py:151` | SUBPROCESS-NO-TIMEOUT | REAL | subprocess.run() has no timeout= ceiling for a hung child |
| `worker/_sotto_worker_agcinert.py:280` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_sotto_worker_agcinert.py:285` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_sotto_worker_agcinert.py:291` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_sotto_worker_agcinert.py:487` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_sotto_worker_agcinert.py:1242` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_sotto_worker_agcinert.py:1601` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_sotto_worker_agcinert.py:2102` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/_sotto_worker_agcinert.py:2297` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/audio_recorder.py:66` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/audio_ring.py:400` | SUBPROCESS-NO-CONSOLE | NOISE | **_hidden_kwargs() supplies creationflags=0x08000000 and STARTF_USESHOWWINDOW |
| `worker/audio_ring.py:450` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/audio_ring.py:457` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/audio_ring.py:771` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/engine_switch.py:474` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/engine_switch.py:576` | TYPED-FIELD-GUARD | NOISE | isinstance(int,float) guard precedes the float() coercion |
| `worker/engine_switch.py:578` | TYPED-FIELD-GUARD | NOISE | isinstance(int,float) guard precedes the float() coercion |
| `worker/engine_switch.py:1759` | TYPED-FIELD-GUARD | NOISE | isinstance guard precedes the subtraction/float() coercion |
| `worker/inspect_model.py:5` | DEFAULT-PATH-DRIFT | REAL | hardcoded host-specific absolute default; target absent on this host |
| `worker/inspect_model.py:35` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/inspect_model.py:37` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/inspect_model.py:66` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/inspect_model.py:113` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/lang_prompt.py:181` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/lang_prompt.py:193` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/live_queue.py:681` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/live_queue.py:717` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/live_route.py:190` | TYPED-FIELD-GUARD | NOISE | isinstance(tap,(int,float)) guard precedes the coercion |
| `worker/live_route.py:193` | TYPED-FIELD-GUARD | NOISE | isinstance guard precedes the float() coercion; None falls through |
| `worker/live_route.py:196` | TYPED-FIELD-GUARD | NOISE | isinstance guard precedes the subtraction/float() coercion |
| `worker/live_route.py:332` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/mic_tap.py:106` | TYPED-FIELD-GUARD | NOISE | display-only %r/str() of a possibly missing field; no coercion crash |
| `worker/mic_tap.py:122` | TYPED-FIELD-GUARD | NOISE | display-only %r/str() of a possibly missing field; no coercion crash |
| `worker/mic_tap.py:207` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/mic_tap.py:214` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/mic_tap.py:303` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/mic_tap.py:311` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/mic_tap.py:425` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/base.py:1979` | SUBPROCESS-NO-CONSOLE | REAL | vendored subprocess.run() lacks creationflags/startupinfo; hidden parent can paint a console |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/base.py:1979` | SUBPROCESS-NO-TIMEOUT | REAL | subprocess.run() has no timeout= ceiling for a hung child |
| `worker/models/parakeet-redux-onnx-int4/transcribe.py:53` | SUBPROCESS-NO-CONSOLE | REAL | vendored subprocess.run() lacks creationflags/startupinfo; hidden parent can paint a console |
| `worker/models/parakeet-redux-onnx-int4/transcribe.py:53` | SUBPROCESS-NO-TIMEOUT | REAL | subprocess.run() has no timeout= ceiling for a hung child |
| `worker/ort_cuda_runtime.py:74` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/ort_cuda_runtime.py:79` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/ort_cuda_runtime.py:85` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/parakeet_ultra.py:80` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/redux_live.py:3297` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/redux_live.py:3730` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/redux_live.py:3740` | SILENT-ENOENT-FALLBACK | REAL | missing config returns {} with no diagnostic while other read errors log |
| `worker/redux_live.py:3843` | TYPED-FIELD-GUARD | NOISE | display-only str() in an f-string; None is harmless here |
| `worker/runs/_delivery-rate-mutant/lang_prompt.py:181` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/lang_prompt.py:193` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/runs/_delivery-rate-mutant/sotto_worker.py:280` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/sotto_worker.py:285` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/sotto_worker.py:291` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/sotto_worker.py:487` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/sotto_worker.py:1242` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/sotto_worker.py:1601` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/sotto_worker.py:2123` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/sotto_worker.py:2318` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/wasapi_loopback.py:142` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/wasapi_loopback.py:519` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_delivery-rate-mutant/wasapi_loopback.py:534` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/runs/_verdict-order-mutant.py:648` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:653` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:659` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:714` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:1009` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:1444` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:2147` | TYPED-FIELD-GUARD | NOISE | if peak: truthiness guard precedes % formatting |
| `worker/runs/_verdict-order-mutant.py:2768` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:3521` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:3709` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:3713` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:4054` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:5444` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:5843` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/runs/_verdict-order-mutant.py:7740` | TYPED-FIELD-GUARD | NOISE | display-only %r/str() of a possibly missing field; no coercion crash |
| `worker/runs/_verdict-order-mutant.py:7945` | SUPPRESS-BROAD-EXCEPT | NOISE | diagnostic/probe path deliberately skips unreadable optional state |
| `worker/sotto_worker.py:933` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:1019` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:1056` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:1208` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/sotto_worker.py:1227` | TYPED-FIELD-GUARD | NOISE | isinstance(str) and value.strip() guard precedes str() |
| `worker/sotto_worker.py:1439` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:2055` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:2359` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:3253` | TYPED-FIELD-GUARD | NOISE | if peak: truthiness guard precedes % formatting |
| `worker/sotto_worker.py:3874` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:4651` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:4658` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:4663` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:4897` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:4901` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:5320` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:5325` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:6044` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:6937` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:7448` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:9630` | TYPED-FIELD-GUARD | NOISE | display-only %r/str() of a possibly missing field; no coercion crash |
| `worker/sotto_worker.py:9851` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:9869` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:10247` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/sotto_worker.py:10252` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/speaker_sidecar.py:763` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/speaker_sidecar.py:1460` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/speaker_sidecar.py:1587` | TYPED-FIELD-GUARD | NOISE | want is not None guard; (want or 0.0) only inside the message |
| `worker/speaker_sidecar.py:1589` | TYPED-FIELD-GUARD | NOISE | want is not None guard; (want or 0.0) only inside the message |
| `worker/speaker_sidecar.py:1590` | TYPED-FIELD-GUARD | NOISE | want is not None guard; (want or 0.0) only inside the message |
| `worker/speaker_sidecar.py:1873` | TYPED-FIELD-GUARD | NOISE | display-only %r/str() of a possibly missing field; no coercion crash |
| `worker/speaker_sidecar.py:1881` | TYPED-FIELD-GUARD | NOISE | display-only %r/str() of a possibly missing field; no coercion crash |
| `worker/unified_asr.py:41` | DEFAULT-PATH-DRIFT | REAL | hardcoded host-specific absolute default; target absent on this host |
| `worker/unified_asr.py:224` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/wasapi_loopback.py:228` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/wasapi_loopback.py:241` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/wasapi_loopback.py:1209` | SUPPRESS-BROAD-EXCEPT | NOISE | best-effort optional operation; suppression is deliberate, no caller value depends on it |
| `worker/wasapi_loopback.py:1567` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/wasapi_loopback.py:1579` | SUPPRESS-BROAD-EXCEPT | NOISE | None is the documented unavailable/fallback result; caller already branches on it |
| `worker/wasapi_loopback.py:1626` | TYPED-FIELD-GUARD | NOISE | if peak: truthiness guard precedes % formatting |
| `worker/_prefix_audioflag.py:77` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:111` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:144` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:218` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:219` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:232` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:233` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:244` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1138` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1139` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1140` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1141` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1142` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1143` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1144` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1314` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1388` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1389` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1390` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1391` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1785` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1789` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1792` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:1801` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:2072` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:2075` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:2078` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:2092` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:2095` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:2106` | DUPLICATED-CONSTANT | NOISE | frozen snapshot/mutant copy; independent constants are intentional |
| `worker/_prefix_audioflag.py:2122` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/_prefix_audioflag.py:3593` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/_probe/diag.py:48` | DUPLICATED-CONSTANT | NOISE | standalone probe script with local constants; no shared module contract |
| `worker/_probe/fp16_io.py:4` | DUPLICATED-CONSTANT | NOISE | standalone probe script with local constants; no shared module contract |
| `worker/_probe/gate_features.py:14` | DUPLICATED-CONSTANT | NOISE | standalone probe script with local constants; no shared module contract |
| `worker/_probe/gate_features.py:15` | DUPLICATED-CONSTANT | NOISE | standalone probe script with local constants; no shared module contract |
| `worker/_probe/idle-cpu-parakeet.py:63` | DEAD-IMPORT | NOISE | transcribe is found via inserted sys.path dir; imported `reference` is used below |
| `worker/_probe/probe2.py:5` | DUPLICATED-CONSTANT | NOISE | standalone probe script with local constants; no shared module contract |
| `worker/audio_recorder.py:66` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/capture_share.py:54` | DUPLICATED-CONSTANT | NOISE | independent module constants with identical current values; no drift observed |
| `worker/discord_streams.py:93` | DUPLICATED-CONSTANT | NOISE | independent module constants with identical current values; no drift observed |
| `worker/discord_streams.py:121` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/discord_streams.py:306` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/engine_switch.py:474` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/lang_prompt.py:202` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/live_queue.py:294` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/live_queue.py:717` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/live_route.py:209` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builder.py:19` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builder.py:122` | DEAD-IMPORT | NOISE | optional adapter dependency; imported PeftConfig/PeftModel is used below |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builder.py:122` | HALLUCINATED-IMPORT | NOISE | optional peft adapter import guarded by adapter_path; imported symbol is used |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/base.py:19` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/base.py:4854` | DEAD-IMPORT | NOISE | optional LoRA path; imported LoraLayer is used in this method |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/base.py:4854` | HALLUCINATED-IMPORT | NOISE | optional peft adapter import guarded by adapter_path; imported symbol is used |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/base.py:4980` | DEAD-IMPORT | NOISE | optional LoRA path; imported LoraLayer is used in this method |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/base.py:6093` | DEAD-IMPORT | NOISE | optional adapter dependency; imported PeftConfig/PeftModel is used below |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/block_drafter.py:11` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/dflash2.py:40` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/dspark.py:41` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/expansions/trt_rtx.py:6` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/expansions/webgpu.py:6` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/gptoss.py:6` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/lfm2.py:10` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/mtp.py:10` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/phi.py:6` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/qwen.py:14` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/builders/whisper.py:12` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/loaders/gptoss.py:10` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/loaders/modelopt.py:11` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/models/.sotto-runtime/genai-cuda/onnxruntime_genai/models/quantization/quant_config.py:26` | HALLUCINATED-IMPORT | CANNOT-JUDGE | onnx_ir absent here and not vendored; runtime dependency set cannot be judged statically |
| `worker/punctuation_prosody.py:90` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/redux_live.py:711` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/redux_live.py:727` | ENV-VAR-WITHOUT-PRODUCER | NOISE | producer at _main/fleurs-nemotron-stream-runner.py:1148 |
| `worker/redux_live.py:728` | ENV-VAR-WITHOUT-PRODUCER | NOISE | COMPUTERNAME is OS-provided on Windows |
| `worker/redux_live.py:756` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/redux_live.py:2838` | DEAD-IMPORT | NOISE | transcribe is found via inserted sys.path dir; imported `reference` is used below |
| `worker/redux_live.py:4083` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/runs/_delivery-rate-mutant/lang_prompt.py:202` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/runs/_delivery-rate-mutant/wasapi_loopback.py:534` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/runs/_verdict-order-mutant.py:1872` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/runs/_verdict-order-mutant.py:6636` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/sotto_worker.py:1208` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/sotto_worker.py:1225` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/sotto_worker.py:2882` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/sotto_worker.py:5300` | ENV-VAR-WITHOUT-PRODUCER | NOISE | producer at _main/fleurs-nemotron-stream-runner.py:89,1151 |
| `worker/sotto_worker.py:8375` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/sotto_worker.py:8958` | ENV-VAR-WITHOUT-PRODUCER | NOISE | documented external opt-out SOTTO_FUSE_HISTORY=0; no in-tree producer by design |
| `worker/speaker_bridge.py:52` | DUPLICATED-CONSTANT | NOISE | independent module constants with identical current values; no drift observed |
| `worker/speaker_bridge.py:75` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/speaker_bridge.py:79` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/speaker_bridge.py:88` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/speaker_bridge.py:219` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/speaker_bridge.py:223` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/speaker_bridge.py:232` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/speaker_sidecar.py:763` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/wasapi_loopback.py:1567` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/wasapi_loopback.py:1579` | RETURN-NONE-EXCEPT | NOISE | None is the documented unavailable/invalid-input fallback; handler validates the value |
| `worker/_probe/diag.py:48` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/diag.py:48` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/diag.py:86` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/fp16_io.py:4` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/fp16_io.py:4` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/idle-cpu-parakeet.py:63` | HALLUCINATED-IMPORT | NOISE | `sys.path.insert(0, MODEL_DIR)` precedes `import transcribe`; runtime import root, not a missing module |
| `worker/_probe/probe2.py:4` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe2.py:4` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe2.py:5` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe3.py:4` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe3.py:4` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe4.py:4` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe4.py:4` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe5.py:5` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe5.py:5` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe5.py:6` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe6.py:5` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe6.py:5` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe6.py:6` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_api.py:3` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_api.py:3` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe_enc.py:7` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_enc.py:7` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe_enc.py:16` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_genai.py:3` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_genai.py:3` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe_genai.py:4` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_graphs.py:5` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_graphs.py:5` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe_rnnt.py:10` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_rnnt.py:10` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe_rnnt.py:11` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_rnnt2.py:10` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_rnnt2.py:10` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/probe_rnnt2.py:42` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_vocab.py:3` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/probe_vocab.py:3` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/quant_cmp.py:16` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/quant_cmp.py:16` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/quant_cmp.py:17` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/quant_cmp.py:17` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/quant_cmp.py:18` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/variants.py:17` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/_probe/variants.py:17` | DEFAULT-PATH-DRIFT | NOISE | gitignored `worker/_probe/` diagnostic snapshot constant; hardcoded fixture path is probe-local |
| `worker/_probe/variants.py:48` | ABSOLUTE-DEFAULT-PATH | NOISE | gitignored `worker/_probe/` one-off diagnostic; hardcoded snapshot fixture path has no product consumer |
| `worker/audio_queue_consumer.py:179` | SILENT-TRUNCATION | NOISE | explicit `limit` from `--limit` CLI flag drives `queue[:limit]`; caller-requested cap |
| `worker/inspect_model.py:5` | ABSOLUTE-DEFAULT-PATH | REAL | module-level absolute model default; target absent on this host |
| `worker/redux_live.py:2838` | HALLUCINATED-IMPORT | NOISE | `sys.path.insert(0, MODEL_DIR)` precedes `import transcribe`; runtime import root, not a missing module |
| `worker/unified_asr.py:41` | ABSOLUTE-DEFAULT-PATH | REAL | module-level `DEFAULT_MODEL` absolute NeMo path; target absent on this host |
| `worker/wasapi_loopback.py:742` | SILENT-TRUNCATION | NOISE | `if len(current) > JOURNAL_MAX_ROWS` guard with declared cap constant bounds journal retention |

## Counts

- adjudicated N: **281** (231 prior rows + 50 appended info rows; all unique keys under dedupe key `file,line,class`)
- REAL: **13**
- NOISE: **252**
- CANNOT-JUDGE: **16**
- unadjudicated: **0** unique keys (all 84 raw info findings are represented by the 50 appended rows; 4 duplicate high/medium raw rows were already represented)
- fixed: **1** (only a REAL ≤3-line change with an obvious correct form)
- precision on unique keys: **13 / (13 + 252) = 4.91%** (denominator 265 = REAL + NOISE unique keys; 16 CANNOT-JUDGE keys excluded)

## Code edit

- File/line: `worker/redux_live.py:3741` (`load_config`, after dedupe row #64, high, SILENT-ENOENT-FALLBACK). The `FileNotFoundError` branch returned `{}` with no diagnostic while every other read error logged through `err()`; added one logging line before the same `return {}`. Return values and all other branches are unchanged. No sampling/decode logic, threshold, or assertion was touched.
- Syntax check: `python -m py_compile worker/redux_live.py` → rc 0 (no output).
- Behaviour proof (one command, run in the worktree):

```bash
python -m py_compile worker/redux_live.py && python - <<'PY'
import ast, json
src = open('worker/redux_live.py', encoding='utf-8').read()
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'load_config')
msgs = []
ns = {'json': json, 'err': msgs.append}
exec(compile(ast.fix_missing_locations(ast.Module([fn], [])), '<load_config>', 'exec'), ns)
f = ns['load_config']
assert f('worker/__missing__.json') == {} and msgs == ['config worker/__missing__.json not found; using defaults'], msgs
assert f('worker/config.json') == json.load(open('worker/config.json', encoding='utf-8')) and len(msgs) == 1, msgs
print('PROOF: missing -> {} + err diagnostic; existing -> unchanged parsed config; msgs =', msgs)
PY
```

Observed output: `PROOF: missing -> {} + err diagnostic; existing -> unchanged parsed config; msgs = ['config worker/__missing__.json not found; using defaults']`.

## Why the remaining REAL rows were not edited

- 6 × `SUBPROCESS-NO-TIMEOUT`: no timeout ceiling is real, but no repo-derived timeout value exists; picking one would be a design change, not an obvious 1-line fix.
- 2 × `SUBPROCESS-NO-CONSOLE` and 2 `DEFAULT-PATH-DRIFT` (plus the same two lines reclassified as `ABSOLUTE-DEFAULT-PATH`): vendored/ignored `worker/models/**` trees and host-specific defaults need a runtime-owned root or window policy; no safe ≤3-line form. `DEFAULT-PATH-DRIFT` also affects `worker/inspect_model.py` and `worker/unified_asr.py`, whose intended model locations are absent on this host.

## CANNOT-JUDGE rows

All 16 are `HALLUCINATED-IMPORT` for `onnx_ir` in the vendored `onnxruntime_genai` model builder tree. `onnx_ir` is absent from this interpreter and not vendored; whether the target runtime installs it is a runtime fact, not a static one. The imported symbols are used, so no import was deleted.
