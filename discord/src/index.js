#!/usr/bin/env node
// CLI: join a Discord voice channel as a bot and capture one PCM stream per speaker.
//
//   node src/index.js --guild <GUILD_ID> --channel <VOICE_CHANNEL_ID> [--out out] [--segment-ms N] [--gap-ms N]
//
// Token comes from DISCORD_BOT_TOKEN (or --token). See README.md.
import path from 'node:path';
import { capture } from './live.js';

function arg(name, fallback = undefined) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

function need(value, name) {
  if (!value) {
    process.stderr.write(`missing ${name}: pass --${name} or set ${name.toUpperCase()}\n`);
    process.exit(2);
  }
  return value;
}

const token = need(arg('token', process.env.DISCORD_BOT_TOKEN), 'token (DISCORD_BOT_TOKEN)');
const guildId = need(arg('guild', process.env.DISCORD_GUILD_ID), 'guild');
const channelId = need(arg('channel', process.env.DISCORD_CHANNEL_ID), 'channel');
const outDir = arg('out', 'out');
const segmentMs = Number(arg('segment-ms', '0'));
const gapMs = Number(arg('gap-ms', '0'));

process.stderr.write(
  `capture start guild=${guildId} channel=${channelId} out=${path.resolve(outDir)} ` +
    `segment_ms=${segmentMs} gap_ms=${gapMs}\n`,
);

capture({ token, guildId, channelId, outDir, segmentMs, gapMs }).catch((err) => {
  process.stderr.write(`fatal: ${err.stack || err.message}\n`);
  process.exit(1);
});
