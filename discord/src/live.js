// Live path: a BOT (never a selfbot) joins a voice channel, subscribes to each
// speaker's raw Opus packets, and feeds them through PcmTap (the same core the
// synthetic harness drives).
import { Client, GatewayIntentBits } from 'discord.js';
import {
  EndBehaviorType,
  VoiceConnectionStatus,
  entersState,
  joinVoiceChannel,
} from '@discordjs/voice';
import { PcmTap } from './receiver-core.js';

export function log(line) {
  process.stdout.write(`${new Date().toISOString()} ${line}\n`);
}

export async function capture({ token, guildId, channelId, outDir, segmentMs = 0, gapMs = 0 }) {
  const tap = new PcmTap({ outDir, segmentMs, gapMs, log });

  const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
  const closing = { done: false, shutdown: null };

  const shutdown = async (reason) => {
    if (closing.done) return;
    closing.done = true;
    log(`SHUTDOWN reason=${reason}`);
    tap.closeAll();
    try {
      connection?.destroy();
    } catch {
      /* already gone */
    }
    try {
      await client.destroy();
    } catch {
      /* already gone */
    }
    const { packets, decoders, segments, unknownSsrc, decodeErrors, bytes } = tap.stats;
    log(
      `CAPTURE_TOTAL packets=${packets} decoders=${decoders} segments=${segments} ` +
        `bytes=${bytes} unknown_ssrc=${unknownSsrc} decode_errors=${decodeErrors}`,
    );
  };
  closing.shutdown = shutdown;

  let connection;

  client.once('clientReady', async (readyClient) => {
    log(`BOT_READY user=${readyClient.user.id} tag=${readyClient.user.tag}`);
    try {
      const guild = await readyClient.guilds.fetch(guildId);
      const channel = await guild.channels.fetch(channelId);
      if (!channel || !channel.isVoiceBased()) {
        throw new Error(`channel ${channelId} is not a voice channel`);
      }
      connection = joinVoiceChannel({
        channelId,
        guildId,
        adapterCreator: guild.voiceAdapterCreator,
        selfDeaf: false, // REQUIRED to receive: a deafened client gets no audio
        selfMute: true, // we never transmit
      });
      connection.on('stateChange', (_old, next) => log(`VOICE_STATE status=${next.status}`));
      await entersState(connection, VoiceConnectionStatus.Ready, 30_000);
      log(`VOICE_READY guild=${guildId} channel=${channelId}`);

      const receiver = connection.receiver;

      // SSRC -> user id. The library learns this from SPEAKING opcodes; we feed
      // it into the tap's map, which is the ONLY place the mapping lives.
      const onVoiceUser = (data, source) => {
        if (!data || !data.audioSSRC || !data.userId) return;
        tap.map.bind(data.audioSSRC, data.userId, source);
      };
      receiver.ssrcMap.on('create', (data) => onVoiceUser(data, 'ssrc-create'));
      receiver.ssrcMap.on('update', (_old, data) => onVoiceUser(data, 'ssrc-update'));

      receiver.speaking.on('start', (userId) => {
        const data = receiver.ssrcMap.get(userId);
        if (!data) {
          log(`SPEAK_START user=${userId} ssrc=unknown (waiting for mapping)`);
          return;
        }
        tap.map.bind(data.audioSSRC, userId, 'speaking');
        const existing = receiver.subscriptions.get(userId);
        if (existing) return;

        const stream = receiver.subscribe(userId, { end: { behavior: EndBehaviorType.Manual } });
        log(`SUBSCRIBE user=${userId} ssrc=${data.audioSSRC} end=manual`);
        stream.on('data', (opus) => {
          const mapped = receiver.ssrcMap.get(userId);
          if (!mapped) return;
          tap.ingest({ ssrc: mapped.audioSSRC, opus, tMs: Date.now() });
        });
        stream.on('error', (err) => log(`RECEIVE_ERROR user=${userId} error=${err.message}`));
        stream.on('end', () => log(`RECEIVE_END user=${userId}`));
      });

      receiver.speaking.on('end', (userId) => log(`SPEAK_END user=${userId}`));
    } catch (err) {
      log(`JOIN_FAILED error=${err.message}`);
      await shutdown('join-failed');
      process.exitCode = 1;
    }
  });

  client.on('error', (err) => log(`GATEWAY_ERROR error=${err.message}`));

  const onSignal = (signal) => {
    shutdown(`signal-${signal}`).then(() => process.exit(0));
  };
  process.once('SIGINT', () => onSignal('SIGINT'));
  process.once('SIGTERM', () => onSignal('SIGTERM'));

  await client.login(token);
  // Keep the process alive until a signal or a fatal join failure.
  await new Promise((resolve) => {
    const tick = setInterval(() => {
      if (closing.done) {
        clearInterval(tick);
        resolve();
      }
    }, 250);
  });
  return tap.stats;
}
