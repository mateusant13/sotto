# Discord per-speaker capture — 2026-11-04

Owner ask: *"implementa agora. testa, aprova, troca toda nossa stack por essa"* — with
per-participant audio as the whole point, **no speaker diarization** ("só o core").
This lane delivers the Discord ingress: a bot joins one voice channel and writes one
continuous 16 kHz mono PCM stream per Discord user id, sized for the ASR stack.

## What landed

| path | role |
|---|---|
| `discord/package.json` | isolated service, **pinned** deps; `app/package.json` untouched |
| `discord/src/receiver-core.js` | the receiving core: `SsrcMap` + `PcmTap` (decoder, files, index) |
| `discord/src/live.js` | bot join, `receiver.speaking` → `subscribe` → same tap |
| `discord/src/index.js` | CLI (`--guild`, `--channel`, `--out`, `--segment-ms`, `--gap-ms`) |
| `discord/harness/two-speakers.js` | synthetic two-SSRC proof, no Discord needed |
| `discord/README.md` | 4 run commands + smallest bot permission set |
| `discord/.gitignore` | `out/` — captured audio is the owner's voice, never committed |
| `_main/discord-per-user.py` | census + WAV (16 kHz mono) export per speaker for the ASR stack |

Pinned exactly (`discord/node_modules` only, `npm install` = 50 packages):

```
@discordjs/voice 0.19.2   @snazzah/davey 0.1.9   discord.js 14.28.1
@discordjs/opus  0.11.0   opusscript     0.1.1   @noble/ciphers 2.4.0
```

`generateDependencyReport()` confirms the runtime sees them all: DAVE
`@snazzah/davey 0.1.9`, Opus `@discordjs/opus 0.11.0`, encryption
`@noble/ciphers 2.4.0`, native `aes-256-gcm` yes.

## Design, and why the split is exact

`@discordjs/voice` `VoiceReceiver.subscribe(userId)` yields **raw Opus packets** — the
library does not decode (`AudioReceiveStream` doc: "A readable stream of Opus packets";
`onUdpMessage` pushes the decrypted packet straight into the subscription). So:

1. SSRC → user id is learned from Discord's SPEAKING opcode
   (`receiver.ssrcMap.on('create'|'update')`, fed into `PcmTap.map`, the only mapping).
2. One `PcmTap.ingest({ssrc, opus})` call per packet. `PcmTap` keeps **one decoder per
   speaker stream** — never per packet, never a second copy — constructed once:
   `new OpusEncoder(16000, 1)`. libopus resamples 48 kHz → 16 kHz and downmixes to
   mono inside `decode()` (measured: a 20 ms 48 kHz stereo packet decodes to exactly
   320 samples = 640 B; 60 ms → 2880 samples).
3. Writer: `<out>/<user_id>/<epoch_ms>.pcm` (s16le, 16 kHz, mono) + same-name `.jsonl`
   (`segment` header, one `packet` row, `close` row with duration/packets).
4. DAVE/E2E: negotiated by `@discordjs/voice` 0.19.2 itself; `davey` is its DAVE
   implementation and the packet is decrypted by the library before reaching the tap.

## Proof without a live call — synthetic two-speaker harness

`node discord/harness/two-speakers.js` encodes 440 Hz (ssrc 111111 → user
`900000000000000001`, 2.000 s) and 660 Hz (ssrc 222222 → user `900000000000000002`,
2.500 s) as **real Opus packets**, interleaves them frame-by-frame, and pushes them
through the same `PcmTap`. Assertions read the bytes back with an independent reader.

Verbatim output (rc=0). The harness deletes and recreates `discord/out/harness`
on every run, so the `epoch_ms` names below belong to that run and reproduce:


```
SSRC_MAP ssrc=111111 user=900000000000000001 source=harness previous=none
SSRC_MAP ssrc=222222 user=900000000000000002 source=harness previous=none
SPEAKER_OPEN user=900000000000000001 ssrc=111111 decoder=opus/16000Hz/1ch
SEGMENT_OPEN user=900000000000000001 ssrc=111111 file=900000000000000001\1793811474096.pcm
SPEAKER_OPEN user=900000000000000002 ssrc=222222 decoder=opus/16000Hz/1ch
SEGMENT_OPEN user=900000000000000002 ssrc=222222 file=900000000000000002\1793811474096.pcm
SEGMENT_CLOSE user=900000000000000001 file=900000000000000001\1793811474096.pcm duration_ms=2000 packets=100
SEGMENT_CLOSE user=900000000000000002 file=900000000000000002\1793811474096.pcm duration_ms=2500 packets=125
HARNESS map ssrc=111111 -> user=900000000000000001
HARNESS map ssrc=222222 -> user=900000000000000002
HARNESS stats packets=225 decoders_created=2 segments=2 bytes=144000 unknown_ssrc=0 decode_errors=0
HARNESS file=discord\out\harness\900000000000000001\1793811474096.pcm duration_ms=2000.00 bytes=64000 samples=32000 rms=8405.9 zero_cross_hz=450.3
HARNESS file=discord\out\harness\900000000000000002\1793811474096.pcm duration_ms=2500.00 bytes=80000 samples=40000 rms=6394.3 zero_cross_hz=649.4
HARNESS: PASS (2 speakers, 2 files, durations exact, RMS above floor, distinct tones)
```

Reading: two independent files under two user-id directories; durations exact
(32 000 and 40 000 samples at 16 kHz); RMS 8405.9 and 6394.3 (floor 500, silence would
be ~0); dominant frequencies 450.3 Hz / 649.4 Hz against the encoded 440/660 Hz
(zero-crossing estimator bias, ≤2.8 %), so neither file leaked the other speaker.
`decoders_created=2` for 225 packets is the "one decoder per stream" claim.

### Negative control (the harness must be able to fail)

`node discord/harness/two-speakers.js --neg-arm` binds **both SSRCs to one user id**;
it must collapse to one file and die on the two-speaker assertion (rc=1, house
convention: the negative returns 1 when it catches the mutant):

```
SSRC_MAP ssrc=111111 user=900000000000000001 source=harness previous=none
SSRC_MAP ssrc=222222 user=900000000000000001 source=harness-neg-arm previous=none
SPEAKER_OPEN user=900000000000000001 ssrc=111111 decoder=opus/16000Hz/1ch
SEGMENT_OPEN user=900000000000000001 ssrc=111111 file=900000000000000001\1793811446004.pcm
SEGMENT_CLOSE user=900000000000000001 file=900000000000000001\1793811446004.pcm duration_ms=4500 packets=225
HARNESS map ssrc=111111 -> user=900000000000000001
HARNESS map ssrc=222222 -> user=900000000000000001
HARNESS stats packets=225 decoders_created=1 segments=1 bytes=144000 unknown_ssrc=0 decode_errors=0
HARNESS file=discord\out\harness\900000000000000001\1793811446004.pcm duration_ms=4500.00 bytes=144000 samples=72000 rms=5853.4 zero_cross_hz=561.7
HARNESS neg-arm collapsed both SSRCs into one speaker directory as designed
NEG-ARM: PASS (the two-speaker assertion caught it)
```

## Bridge to the Sotto pipeline

`python _main/discord-per-user.py --wav` reads the same tree and exports one WAV per
speaker segment (`wave`: 16 kHz mono, 16-bit), plus a census read from the bytes:

```
discord-per-user user=900000000000000001 ssrc=111111 pcm=harness/900000000000000001/1793811474096.pcm duration_ms=2000.00 rms=8405.9 peak=13080 packets=100 bytes=64000 silent=no wav=harness/900000000000000001/1793811474096.wav
discord-per-user user=900000000000000002 ssrc=222222 pcm=harness/900000000000000002/1793811474096.pcm duration_ms=2500.00 rms=6394.3 peak=9219 packets=125 bytes=80000 silent=no wav=harness/900000000000000002/1793811474096.wav
discord-per-user TOTAL users=2 segments=2 duration_ms=4500.00 silent_segments=0
```

WAV checked with `wave.open`: `1 ch, 2 B, 16000 Hz, 32000 frames` (= 2.000 s).

## Live join — UNMEASURED

No bot token exists in this environment (`DISCORD_BOT_TOKEN` / `DISCORD_TOKEN` absent,
no `.env`), and this lane will not use the owner's Discord account or a selfbot. So the
real-join arm is **UNMEASURED**, not green. The one command the owner must run:

```
cd H:\sotto\discord; $env:DISCORD_BOT_TOKEN="<BOT_TOKEN>"; node src/index.js --guild <GUILD_ID> --channel <VOICE_CHANNEL_ID>
```

Expected observation, in order: `BOT_READY user=…`, `VOICE_STATE status=ready`,
`VOICE_READY guild=… channel=…`, then `SSRC_MAP ssrc=… user=…`,
`SPEAKER_OPEN user=… decoder=opus/16000Hz/1ch`, `SEGMENT_OPEN …`, and per speaker a
`<user_id>/<epoch_ms>.pcm` appearing under `discord/out/`. Ctrl+C writes `SEGMENT_CLOSE`
and `CAPTURE_TOTAL packets=… decoders=… segments=…`.

## Findings / risks that are not claims

- **Encryption lib is mandatory for receive, not optional.** The voice gateway selects
  `aead_xchacha20_poly1305_rtpsize`; `@discordjs/voice` 0.19.2 ships a fallback whose
  encrypt/decrypt throw *"Cannot play audio as no valid encryption package is
  installed"* when no sodium-class lib is present. `@noble/ciphers` 2.4.0 is pinned for
  exactly that; dependency report lists it as found. Without it the receive path would
  be broken by configuration, not by the library.
- `@discordjs/opus` 0.11.0 is named "Encoder" but its instance also exposes
  `decode(buf)` returning PCM of the packet's true frame length — used as the single
  per-stream decoder. `opusscript` 0.1.1 is only the harness encoder (pure JS).
- `prism-media` resolves inside `node_modules/@discordjs/voice/node_modules`; the tap
  does not depend on it.
- Nothing here was run against a real guild; nothing here opens a browser, logs into a
  Discord account, or touches the owner's audio endpoint.
