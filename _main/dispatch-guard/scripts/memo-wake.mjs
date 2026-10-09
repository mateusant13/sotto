#!/usr/bin/env node
// memo-wake.mjs - SessionStart hook. Makes `memo wake` the DEFAULT rather than a thing to remember.
//
// WHY A PORT AND NOT `memo wake`
// `~/.optmem/memo` is a Python program (measured 2026-10-06: shebang `#!/usr/bin/env python3`,
// 31,022 bytes). A hook that shelled out to it would be a subprocess on the session-start path,
// which this Plugin's contract forbids. So the wake ALGORITHM is ported here to node and reads
// the store files directly. The store stays authoritative for note/nap/recall; this file only
// reads, and only reads through the same fixed-width record layout the tool defines.
//
// THE STORE, verbatim from the tool (memo:50-73, :224-289):
//   LOG_REC = 320  TREE_REC = 288   records are FIXED WIDTH; position IS identity
//   memory i lives at i*320 of LOG.txt; block [lo,hi) lives at (lo//size)*288 of TREE/<size>
//   WAKE_LINES = 96 (overridable in <store>/config; clamped below)
//
// THE WAKE, faithful to cmd_wake (memo:584-651): detail DECAYS WITH AGE. Blocks are kept whole
// iff size <= alpha * age, and alpha is binary-searched for the finest tiling that still fits the
// line budget. Recent memories stay verbatim; ancient ones collapse to a summary line. When
// everything fits, nothing is compressed at all.
//
// WHERE THE OWNER/SUBAGENT LINE IS, AND WHY IT IS HERE
// The runtime runs a subagent session's first turn through beginTurn with the SUBAGENT's handler
// scope (measured 2026-10-06 in @minimax-ai/code/chunks/chunk-EL5XOH23.js: handlersForTurn returns
// `this.subagents.get(sessionId)?.handlers ?? handlers`, and beginTurn admits every not-yet-seen
// plugin and runs `SessionStart` for it). So a SessionStart hook in this Plugin DOES fire inside
// subagent sessions - registering only on SessionStart is NOT by itself the guard.
// Two measured discriminators, both checked, because one of them is absent on one of the paths:
//   1. `source: "fork"` - the runtime passes sessionStartSource:"fork" for any session that has a
//      parentSessionId, and that is what reaches the SessionStart payload.
//   2. `agent_id` / `agent_type` - the subagent dispatch path (runEvent) injects both.
// "subagents never run memo" is the store's own documented rule; this hook is where it is enforced.
//
// FAILS OPEN, ALWAYS. A store that cannot be read emits nothing and exits 0. This hook must never
// wedge a session start, and a session that starts without a wake is a far smaller failure than a
// session that does not start.
import { existsSync, readFileSync, statSync, openSync, readSync, closeSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { fingerprint, parsePayload, readStdin, record } from './ledger.mjs';

// The wedge ceiling. The runner contract caps additionalContext at 65,536 characters; the memo's
// own comment (memo:58-61) says dense text costs ~4 chars/token, so this ceiling is ~2k tokens of
// a 32k window. Published so the number is checkable rather than implied.
const MAX_CTX = 8192;
const DEFAULT_WAKE_LINES = 96;
const MAX_WAKE_LINES = 128;
const LOG_REC = 320;
const TREE_REC = 288;

function storeDir() {
  const fromEnv = process.env.MEMORY_DIR;
  if (fromEnv) return fromEnv;
  return join(homedir(), '.optmem', 'memory');
}

/** Read `n` bytes at `off`. Returns null on any failure - a missing record is normal here. */
function readAt(path, off, n) {
  let fd;
  try {
    fd = openSync(path, 'r');
    const buf = Buffer.alloc(n);
    const got = readSync(fd, buf, 0, n, off);
    if (got <= 0) return null;
    return buf.subarray(0, got).toString('utf8').replace(/\s+$/, '');
  } catch {
    return null;
  } finally {
    if (fd !== undefined) {
      try {
        closeSync(fd);
      } catch {
        /* a failed close must not change the verdict */
      }
    }
  }
}

function fileSize(path) {
  try {
    return statSync(path).isFile() ? statSync(path).size : 0;
  } catch {
    return 0;
  }
}

/** `#12 2026-10-06 text` -> [12, '2026-10-06', 'text'] */
function parseRecord(raw) {
  const sp1 = raw.indexOf(' ');
  if (sp1 < 0) return null;
  const id = Number.parseInt(raw.slice(1, sp1), 10);
  if (!Number.isFinite(id)) return null;
  const rest = raw.slice(sp1 + 1);
  const sp2 = rest.indexOf(' ');
  if (sp2 < 0) return [id, rest, ''];
  return [id, rest.slice(0, sp2), rest.slice(sp2 + 1)];
}

/** Memories in the log, read by seek. Floor division ignores a partial trailing record. */
function logLen(d) {
  return Math.floor(fileSize(join(d, 'LOG.txt')) / LOG_REC);
}

/** WAKE_LINES from <store>/config, clamped. A comment line or a bad value is the default. */
function wakeLines(d) {
  try {
    const txt = readFileSync(join(d, 'config'), 'utf8');
    for (const line of txt.split(/\r?\n/)) {
      const t = line.trim();
      if (!t || t.startsWith('#')) continue;
      const m = t.match(/^WAKE_LINES\s*=\s*(\d+)$/);
      if (m) return Math.min(MAX_WAKE_LINES, Math.max(1, Number.parseInt(m[1], 10)));
    }
  } catch {
    /* no config is the common case; the default is the tool's own default */
  }
  return DEFAULT_WAKE_LINES;
}

/** Tile [0,T) with aligned power-of-two blocks, keeping a block whole iff size <= alpha*age. */
function coverAt(T, alpha) {
  let root = 1;
  while (root < T) root *= 2;
  const out = [];
  const stack = [[0, root]];
  while (stack.length) {
    const [lo, hi] = stack.pop();
    if (lo >= T) continue;
    const size = hi - lo;
    if (size > 1 && (hi > T || size > alpha * (T - lo))) {
      const mid = Math.floor((lo + hi) / 2);
      stack.push([mid, hi]);
      stack.push([lo, mid]);
    } else {
      out.push([lo, hi]);
    }
  }
  out.sort((a, b) => a[0] - b[0]);
  return out;
}

/** The blocks wake prints: at most `budget` of them, finest near T. */
function cover(T, budget) {
  if (T <= 0) return [];
  if (T <= budget) return Array.from({ length: T }, (_, i) => [i, i + 1]);
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (coverAt(T, mid).length > budget) lo = mid;
    else hi = mid;
  }
  const out = coverAt(T, hi);
  // Block sizes jump in powers of two, so alpha alone can undershoot the budget. Spend what is
  // left on the present, where detail is worth most.
  // `memo` picks `max(...)` of the splittable blocks - the LAST one, nearest T. Picking the first
  // instead produces the same LINE COUNT with different block boundaries, which a count-only check
  // would have passed. Measured 2026-10-06: at population 300 the first-block version emitted
  // `#0-3 ...` where the tool emits `#0-7 ...`.
  while (out.length < budget) {
    let idx = -1;
    for (let i = out.length - 1; i >= 0; i--) {
      if (out[i][1] - out[i][0] > 1) {
        idx = i;
        break;
      }
    }
    if (idx < 0) break;
    const [a, b] = out[idx];
    const mid = Math.floor((a + b) / 2);
    out.splice(idx, 1, [a, mid], [mid, b]);
  }
  return out;
}

/**
 * The wake document. Returns { text, complete, blocks }.
 * A block whose summary has not been compressed yet is reported as a pending `memo nap`, never
 * invented: this hook cannot compress (that writes), so it says so and keeps the rest.
 */
function renderWake(d) {
  const T = logLen(d);
  if (T === 0) {
    return { text: 'Your memory is empty. Record one with: memo note "<one line>"', complete: true, blocks: 0 };
  }
  const budget = wakeLines(d);
  const chosen = cover(T, budget);
  const lines = [];
  let pending = [];
  for (const [lo, hi] of chosen) {
    if (hi - lo === 1) {
      const raw = readAt(join(d, 'LOG.txt'), lo * LOG_REC, LOG_REC);
      const rec = raw === null ? null : parseRecord(raw);
      if (rec === null) {
        lines.push(`#${lo} (record unreadable)`);
      } else {
        lines.push(`#${rec[0]} ${rec[1]} ${rec[2]}`);
      }
    } else {
      const size = hi - lo;
      const s = readAt(join(d, 'TREE', String(size)), (lo / size) * TREE_REC, TREE_REC);
      if (s === null || s === '') {
        pending.push(`${lo}-${hi - 1}`);
      } else {
        lines.push(`#${lo}-${hi - 1} ${s}`);
      }
    }
  }
  const head = `Your memory, oldest first, ${T} ${T === 1 ? 'memory' : 'memories'} (window: all ${T}).`;
  const body = [head, ...lines];
  if (pending.length) {
    // The store's own rule: a block that is not compressed yet cannot be summarised without
    // inventing it. Say which, hand over the work, and keep the rest of the read.
    body.push(
      '',
      `Not compressed yet: ${pending.join(', ')}. Run: memo nap <lo-hi> "<one line>" - or \`memo nap\` to list them.`,
    );
  } else {
    // The tool's completion contract (memo:648): an agent is given "run parts until one says
    // awake", so the line has to arrive even for a short memory. Omitted when pending work remains,
    // because then the read is NOT finished.
    body.push('You are awake.');
  }
  return { text: body.join('\n'), complete: pending.length === 0, blocks: chosen.length, T };
}

async function main() {
  const payload = parsePayload(await readStdin());
  const source = typeof payload.source === 'string' ? payload.source : null;
  const agentId = typeof payload.agent_id === 'string' ? payload.agent_id : null;
  const agentType = typeof payload.agent_type === 'string' ? payload.agent_type : null;

  // THE GUARD. A subagent session gets the parent's plugin scope, so SessionStart fires there too.
  // `fork` is the source the runtime passes for any session with a parentSessionId; the subagent
  // dispatch path additionally injects agent_id/agent_type. Either one means: do not wake.
  if (source === 'fork' || agentId || agentType) {
    record({
      event: 'SessionStart',
      verdict: 'SUPPRESSED',
      action: 'subagent_scope',
      source,
      agent_type: agentType,
      agent_id_sha: fingerprint(agentId || ''),
      session: payload.session_id || 'unknown',
    });
    process.exit(0);
  }

  let rendered = null;
  let store = null;
  try {
    store = storeDir();
    if (!existsSync(join(store, 'LOG.txt'))) {
      process.exit(0); // no store: nothing to wake, and `memo init` is the owner's deliberate act
    }
    rendered = renderWake(store);
  } catch {
    process.exit(0); // an unreadable store must never wedge a session start
  }

  let text = rendered.text;
  let truncated = false;
  if (text.length > MAX_CTX) {
    truncated = true;
    const foot =
      `\n\n[TRUNCATED at ${MAX_CTX} characters of ${text.length}. Not the whole memory. ` +
      `Run \`memo wake\` for the full document, oldest first.]`;
    text = `${text.slice(0, Math.max(0, MAX_CTX - foot.length))}${foot}`;
  }

  record({
    event: 'SessionStart',
    verdict: 'WOKEN',
    action: truncated ? 'truncated' : 'complete',
    blocks: rendered.blocks ?? 0,
    chars: text.length,
    ceiling: MAX_CTX,
    source: source || 'unknown',
    session: payload.session_id || 'unknown',
  });

  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: text },
    }),
  );
  process.exit(0);
}

await main();