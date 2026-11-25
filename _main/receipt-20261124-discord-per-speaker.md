# Discord: one transcript per speaker, in parallel (2026-11-24)

> **SUPERSEDED as the default route (2026-11-24).** The owner rejected the bot
> (`"tu nao precisa de nada disso ai. faz direito."`). The shipped route is the in-repo chain,
> default ON: `worker/speaker_sidecar.py` -> `_main/diar-live.json` -> `worker/speaker_bridge.py`.
> See `_main/receipt-20261124-per-voice-default.md`. What follows describes the exact per-user split,
> which stays available as an alternative when a bot token is on the table.

Owner order, verbatim: *"sotto é pra conseguir distinguir cada voz/camada de audio e saber
transcrever corretamente cada uma em paralelo. faz isso de algum jeito usando o que o discord
proporciona ou entao com modelo que separa vozes. vai."*

## What was wrong / missing

1. **The live Redux path could not start.** `worker/redux_live.py` served its ORT-format cache
   (`.sotto-ort-cache/*.ort`) on the second start; ORT 1.30's ORT-format initialization skips the
   EP-assignment callback, so `get_provider_graph_assignment_info()` returns **zero rows** and the
   loader refused the session. The owner's log, `_main/webview-run.log:214254`:
   `2026-11-24 07:55:08 BRIDGE_DEATH_CAUSE REDUX_BATCH_FAILED ... RuntimeError('Redux ORT
   graph/node assignment readback is empty or unbo...')`.
2. **No path consumed a Discord call.** `discord/` decoded one Opus stream per participant into
   `discord/out/<user_id>/*.pcm`, and nothing transcribed it.

## Change

| file | what |
|---|---|
| `worker/redux_live.py` | `_placement_attestation_required(sess_options)` + `_cache_identity` returns `None` when the session must publish the census; `_create_session` records `session_cache_readback[graph] = {"mode": "bypass-placement-attestation", ...}`; `load_preflight_cache_pair` refuses an empty plan. Stale store `worker/models/parakeet-redux-onnx-int4/.sotto-ort-cache` (**327 MB**) deleted. |
| `worker/discord_streams.py` (new, 703 lines) | tails `<pcm-dir>/<user_id>/*.pcm` + `.jsonl`, one independent `redux_live.LiveSegmenter` per speaker, one shared decode thread, JSONL captions with `speaker`, `speakerId`, `source="discord/voice:speaker-N"`, `producer="redux"`, `route="final"\|"provisional-draft"`, wall-clock `start`/`end` from per-packet `t_ms`. Accepts the shell's uniform argv (`--preload-only`, `--speakers`, `--panel-visibility`, `--threads`) and honours `START_CAPTURE`. |
| `_main/discord-streams-oracle.py` (new) | builds a real-format fixture tree (PT speaker 100 with a 6.0 s wall gap, EN speaker 200), runs the worker, asserts two ids, no crosstalk, per-voice sources, post-gap start ≥ 13.5−0.4 s. `--neg-arm` merges both voices under one id and requires the catch. |
| `_main/redux-gpu-unavailable-oracle.py` | cached-reopen arm now requires `bypass-placement-attestation` and no `.ort` published; new arm `cache-bypass` proves both directions (attested → refused; non-attested → identity exists) and that the fake reproduces ORT 1.30's empty census. |
| `AGENTS.md` | new section `DISCORD: A DIVISAO POR FALANTE E' EXATA` (route, clock law, refusal of separation, cache law). |

## Measured

- Engine: `LOAD onnx-int4 load_s 5.33 providers ['CPUExecutionProvider','CUDAExecutionProvider']`;
  RTF 0.57 cold / 0.02–0.03 warm. GPU RTX 5080, 16303 MiB total.
- Positive oracle: speaker 100 → 4 lines, first 0.0, `pt_post_gap_starts [14.3, 19.3]`; speaker 200
  → 2 lines, first 2.0; zero cross-language words. `POS_RC=0`.
- `--neg-arm`: `caught-by: expected 2 speaker ids, got 1: ['100']`, `NEG_RC=1` (caught).
- Separation model **refuted** on this box, not preferred:
  MossFormer2_SS_16K, 60 s of the real 2026-11-16 Discord call → **1335.107 s (RTF 22.25)**, 210 words
  on stream 0 / 2 on stream 1 vs 211 in the mix (`_main/bench/logs/moss-after.log`).
- Gates: `redux-gpu-unavailable-oracle` PASS (4/4 + 3/3 mutations), `console-window-audit` PASS
  (0 window-opening sites), `owner-screen-gate` PASS (1300 files, 0 findings),
  `_make-gitattributes.py --verify` PASS (0 non-canonical blobs), `agents-md-pins-oracle` PASS.
- Preload path: `START_CAPTURE` on stdin activates; model-loaded in 2.17 s warm; `RC=0`.
- Engine transcription errors observed on the synthetic voice ("na práxima", "chegar É o trabalho")
  are model accuracy, not a wiring fault: the two languages never crossed speakers.

## How to run

```
app\webview\run.cmd --worker worker\discord_streams.py
```

(the bot in `discord/` writes `discord/out`; see `discord/README.md` for the bot token, OAuth2
`bot`, perms View Channel + Connect = `1050624`, `selfDeaf:false`).

## UNMEASURED

- **A real live Discord call**: no `DISCORD_BOT_TOKEN`/guild/channel on this host and
  `discord/out` holds only `harness/`. The worker's behaviour against a live SFU, and the panel's
  rendering of N simultaneous voices, are `UNMEASURED` until the owner provides a bot token.
- **The owner's running shell** loading the fixed `redux_live` is `UNMEASURED` (a lane does not put
  the app on his screen): `fixed, NOT verified` until he restarts it.
