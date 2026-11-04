# Discord per-speaker audio capture

A **bot** that joins one voice channel and writes **one continuous 16 kHz mono PCM
stream per participant**. It never uses a user token, never logs into the owner's
account, and never opens a browser window. No speaker diarization: Discord already
tells us *who* each audio SSRC belongs to, so the split is exact, not estimated.

```
out/
  <user_id>/
    <epoch_ms>.pcm     raw PCM, signed 16-bit little-endian, 16 kHz, mono
    <epoch_ms>.jsonl   segment header, one row per packet, close row
```

Each speaker stream owns **one** Opus decoder (`decoders_created` in the harness
output proves it: 2 decoders for 225 packets, not one per packet and not a copy per
participant). A `discord/out/` tree is owner audio: it is gitignored.

## The 4 commands

```powershell
# 1. install (isolated: discord/node_modules only, app/package.json untouched)
cd discord; npm install

# 2. bot token (Create Application -> Bot -> Reset Token; scope "bot" only)
$env:DISCORD_BOT_TOKEN = "<BOT_TOKEN>"

# 3. join and capture (Ctrl+C to stop; one directory per speaker appears under out/)
node src/index.js --guild <GUILD_ID> --channel <VOICE_CHANNEL_ID>

# 4. prove the receiving core locally, without Discord or a live call
node harness/two-speakers.js
```

`--guild` / `--channel` can also come from `DISCORD_GUILD_ID` / `DISCORD_CHANNEL_ID`.
Optional: `--out <dir>` (default `out`), `--segment-ms N` (roll a file every N ms),
`--gap-ms N` (roll after N ms of silence). Defaults: one continuous file per speaker.

## Smallest bot setup

- OAuth2 scopes: **`bot`** (nothing else; no `applications.commands`).
- Channel permissions: **View Channel** (`1024`) + **Connect** (`1048576`) = `1050624`.
  `Speak` is not needed (the bot joins self-muted). Do **not** assign it a role that
  server-mutes it; receiving is unaffected by self-mute but **self-deafen must stay
  off** (`selfDeaf: false` is set in `src/live.js`; a deafened client gets no audio).
- Privileged intents: **none**. It requests only `Guilds` + `GuildVoiceStates`, both
  non-privileged. Do not enable Message Content / Members.
- Invite it to the guild, then run command 3 while the owner is in the target channel.

## How it works (and why it is not a reimplementation)

- `@discordjs/voice@0.19.2` joins and negotiates DAVE/E2E itself; `@snazzah/davey@0.1.9`
  is the DAVE implementation, pinned to the version the voice library resolves.
- `VoiceReceiver.subscribe(userId)` yields **raw Opus packets** (it does not decode);
  `src/live.js` feeds those packets into the shared tap.
- `src/receiver-core.js` owns the SSRC → user id map, one decoder per speaker
  (`@discordjs/opus@0.11.0` decoding straight to 16 kHz mono — libopus resamples and
  downmixes), and the `.pcm` + `.jsonl` writer.
- `Receiver.speaking.on('start')` is where a user is subscribed; the library learns the
  SSRC from the SPEAKING opcode, so the map is exact from the first packet.
- `@noble/ciphers@2.4.0` is present because the voice gateway selects
  `aead_xchacha20_poly1305_rtpsize`; without a sodium-class library the receive path
  throws `Cannot play audio as no valid encryption package is installed`.

## Harness

`node harness/two-speakers.js` encodes two distinct sines (440 Hz, 660 Hz) into real
Opus packets, tags them with SSRC `111111` and `222222`, and pushes them through the
same `PcmTap` the live path uses. It then reads the bytes back with an independent
reader and asserts: exactly two speaker directories, one file each, exact durations,
RMS above the silence floor, and each file's dominant frequency matching its speaker
(cross-talk would fail it). Expected tail:

```
HARNESS: PASS (2 speakers, 2 files, durations exact, RMS above floor, distinct tones)
```

`node harness/two-speakers.js --neg-arm` collapses both SSRCs onto one user; the
two-speaker assertion must fail (`NEG-ARM: PASS`, rc=1), proving the harness detects
the defect instead of always printing green.
