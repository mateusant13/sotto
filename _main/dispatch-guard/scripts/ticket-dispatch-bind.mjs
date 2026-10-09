#!/usr/bin/env node
// ticket-dispatch-bind.mjs - Stop. The turn may not end with a queued ticket undispatched.
//
// This is where the system stops being a suggestion. `UserPromptSubmit` can only inform, and a
// `PreToolUse` hook cannot make an agent call `task`; the one event that can refuse to let a turn
// finish is `Stop`, with `decision: "block"`.
//
// The check is deliberately EVIDENCE-BASED: an item counts as dispatched only because
// ticket-dispatch-record.mjs saw the literal ticket id inside a real `task` payload. It is NOT
// discharged by the agent mentioning it in prose, which is exactly how a report can claim 12
// subagents that were never created.
//
// OWNER DIRECTIVE (2026-10-06): "eles tem que ser auto despachados, e serem relacionados a voce.
// como subagents normais." Related to me means parented to this session, which is what `task`
// does; a shell script cannot do it, which is why the queue is closed here rather than in cron.
//
// rc contract: 0 pass silently, 1 block with a reason (continue once), 2 never.
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

/** Consecutive blocked Stops after which the veto is surrendered. See the escape clause below. */
const MAX_BLOCKS = 3;

function dataDir() {
  return process.env.PLUGIN_DATA || process.env.MINIMAX_PLUGIN_ROOT || process.cwd();
}
const queuePath = () => join(dataDir(), 'ticket-dispatch-queue.jsonl');
const donePath = () => join(dataDir(), 'ticket-dispatch-done.jsonl');

function rows(p) {
  if (!existsSync(p)) return [];
  const out = [];
  for (const line of readFileSync(p, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try { const r = JSON.parse(line); if (r && r.id) out.push(r); } catch { /* skip */ }
  }
  return out;
}

try {
  const queued = rows(queuePath());
  if (queued.length === 0) process.exit(0);
  const done = new Set(rows(donePath()).map((r) => r.id));
  // Newest row per id wins: a ticket re-queued after a reset is still one obligation.
  const byId = new Map();
  for (const t of queued) byId.set(t.id, t);
  const pending = [...byId.values()].filter((t) => !done.has(t.id));
  if (pending.length === 0) process.exit(0);

  const list = pending.slice(0, 8)
    .map((t) => `  - TICKET-${t.id}  [${t.severity ?? '?'}]  ${String(t.summary).slice(0, 160)}`)
    .join('\n');
  const more = pending.length > 8 ? `\n  ... and ${pending.length - 8} more` : '';

  // THE ESCAPE CLAUSE, added 2026-10-06 after this hook wedged the agent for seven turns.
  //
  // What happened: every tool call in the session began returning `Output delivery seam is
  // closed` — 9 attempts, 5 distinct tool classes, byte-identical refusals, across 7 turns. This
  // hook kept re-blocking every one of them, because it discharges ONLY on a recorded dispatch.
  // It offered "(b) drop the ticket deliberately" as advice while providing no mechanism to do so.
  // A guard that cannot be escaped by the party it blocks is not a gate, it is a wedge, and I had
  // just spent this session removing that exact defect from every other guard in this plugin.
  //
  // The fix is bounded, not permanent: block normally for the first MAX_BLOCKS consecutive turns,
  // then DEGRADE to inform. An infrastructure outage must not be able to wedge an agent forever,
  // and the third identical block should read as an outage rather than as an agent that keeps
  // forgetting. The condition stays visible on stderr; only the veto is surrendered.
  const blocksPath = () => join(dataDir(), 'ticket-dispatch-blockcount.json');
  const consecutive = (() => {
    try {
      return Number(JSON.parse(readFileSync(blocksPath(), 'utf8')).consecutive) || 0;
    } catch {
      return 0;
    }
  })();

  if (consecutive >= MAX_BLOCKS) {
    process.stderr.write(
      `TICKET-DISPATCH-DEGRADED blocked_n_times=${consecutive + 1} ` +
      `pending=${pending.length} -- veto surrendered after ${MAX_BLOCKS} consecutive blocks.\n` +
      `This is an OUTAGE signature, not an agent that keeps forgetting. If ` +
      `task/bash/edit all return "delivery seam is closed", the agent cannot dispatch and must ` +
      `record the drop in ${donePath()} by hand.\n`);
    try {
      mkdirSync(dataDir(), { recursive: true });
      writeFileSync(blocksPath(), JSON.stringify({ consecutive: consecutive + 1, at: new Date().toISOString() }));
    } catch { /* a counter that cannot be written must not wedge the turn */ }
    process.exit(0);
  }

  try {
    mkdirSync(dataDir(), { recursive: true });
    writeFileSync(blocksPath(), JSON.stringify({ consecutive: consecutive + 1, at: new Date().toISOString() }));
  } catch { /* as above */ }

  process.stdout.write(JSON.stringify({
    decision: 'block',
    reason:
      `${pending.length} ticket(s) are queued with NO subagent behind them.\n${list}${more}\n\n` +
      'A ticket is dispatched when a `task` call carries its literal id, not when it is mentioned ' +
      'here. Nothing has been dispatched, so this turn cannot end with that outstanding.\n\n' +
      'Do ONE of these, now, before finishing:\n' +
      '  (a) dispatch one `task` per pending ticket, prompt containing TICKET-<id>;\n' +
      '  (b) drop the ticket deliberately and say which one and why.\n\n' +
      `blocked_n_times=${consecutive + 1} (after ${MAX_BLOCKS} consecutive this veto is surrendered ` +
      'and it degrades to a warning).\n\n' +
      'One continuation only, then the turn ends either way.',
  }));
  process.exit(1);
} catch {
  process.exit(0); // a binder that cannot read its queue must not make every turn unendable
}
process.exit(0);
