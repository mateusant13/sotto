#!/usr/bin/env node
// ticket-dispatch-inject.mjs - UserPromptSubmit. Detect NEW tickets and demand a subagent for each.
//
// WHY A HOOK AT ALL, MEASURED. The repo already carries ~250 KB of ticket machinery
// (ticket-autodispatch.sh 89 KB, ticket-dispatchable.sh 62 KB, ticket-stage2-dispatch.py 53 KB)
// and state/tickets/tickets.jsonl was 7.5 MB and still growing. The system works. What it cannot
// do is dispatch a subagent OF THIS SESSION: those scripts drive the old shell/cron path, and a
// hook process cannot call the `task` tool at all. So the only honest bridge is three hooks that
// use the events the contract actually gives us:
//
//   UserPromptSubmit  this file - read new tickets, queue them, inject the dispatch spec
//   PreToolUse(task)  ticket-dispatch-record.mjs - observe a REAL dispatch, not a claim of one
//   Stop              ticket-dispatch-bind.mjs  - refuse to end the turn with work queued
//
// A hook CANNOT call `task`. Anything that claims otherwise is a design that has not been run.
//
// NEW ONLY. The first run seeds the watermark to the current end of tickets.jsonl and dispatches
// nothing historical. The owner said "a partir de agora, nao os antigos". Replaying a 7.5 MB
// backlog into subagents would be a denial of service wearing a feature.
//
// rc contract: 0 inject or pass silently, 1 never, 2 usage. This hook must never wedge a prompt.
import { readFileSync, writeFileSync, existsSync, mkdirSync, appendFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const LEDGER = 'I:\\!manager\\state\\tickets\\tickets.jsonl';
const MAX_NEW_PER_TURN = 3;   // the Desktop child-agent concurrency limit is 4 by default
const MAX_LEDGER_BYTES = 64 * 1024 * 1024;
const MAX_CTX = 12000;

function dataDir() {
  return process.env.PLUGIN_DATA || process.env.MINIMAX_PLUGIN_ROOT || process.cwd();
}
const wmPath = () => join(dataDir(), 'ticket-dispatch-watermark.json');
const queuePath = () => join(dataDir(), 'ticket-dispatch-queue.jsonl');
const donePath = () => join(dataDir(), 'ticket-dispatch-done.jsonl');

function readWatermark() {
  try {
    return JSON.parse(readFileSync(wmPath(), 'utf8'));
  } catch {
    return null;
  }
}
function writeWatermark(w) {
  try {
    mkdirSync(dataDir(), { recursive: true });
    writeFileSync(wmPath(), JSON.stringify(w));
  } catch { /* a watermark that cannot be written must never wedge a prompt */ }
}

// Read only the bytes appended since the watermark. The ledger is 7.5 MB and re-reading it whole
// on every prompt would be the exact unbounded-read shape the threshold gate refuses.
function readNewRows(fromOffset) {
  const size = statSync(LEDGER).size;
  if (size < fromOffset) return { rows: [], offset: size, truncated: true };
  if (size > MAX_LEDGER_BYTES) return { rows: [], offset: fromOffset, truncated: true };
  const fd = readFileSync(LEDGER, { encoding: 'utf8' });
  const slice = Buffer.from(fd, 'utf8').subarray(fromOffset).toString('utf8');
  const rows = [];
  for (const line of slice.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    try {
      const r = JSON.parse(t);
      if (r && r.id && r.summary) rows.push(r);
    } catch { /* a torn line is skipped, and the offset still advances past it */ }
  }
  return { rows, offset: size, truncated: false };
}

try {
  if (!existsSync(LEDGER)) process.exit(0);

  let wm = readWatermark();
  if (!wm) {
    // FIRST RUN: seed to the current end and dispatch nothing historical.
    writeWatermark({ offset: statSync(LEDGER).size, seeded_at: new Date().toISOString(), queued_total: 0 });
    process.exit(0);
  }

  // Already dispatched ids never re-enter the queue, even across a watermark rewind.
  const done = new Set();
  if (existsSync(donePath())) {
    for (const line of readFileSync(donePath(), 'utf8').split('\n')) {
      if (!line.trim()) continue;
      try { const r = JSON.parse(line); if (r && r.id) done.add(r.id); } catch { /* skip */ }
    }
  }

  const { rows, offset } = readNewRows(Number(wm.offset) || 0);
  const fresh = rows.filter((r) => !done.has(r.id)).slice(0, MAX_NEW_PER_TURN);

  writeWatermark({ ...wm, offset, queued_total: (wm.queued_total || 0) + fresh.length,
                   last_seen_at: new Date().toISOString() });
  if (fresh.length === 0) process.exit(0);

  mkdirSync(dataDir(), { recursive: true });
  const stamped = fresh.map((r) => ({ ...r, queued_at: new Date().toISOString() }));
  appendFileSync(queuePath(), stamped.map((r) => JSON.stringify(r)).join('\n') + '\n');

  const lines = [
    `${fresh.length} ticket(s) arrived. They are QUEUED, not urgent.`,
    'Nothing here requires a tool call, a dispatch, or a turn spent on it.',
    'You will find them when you run the ticket queue yourself, or when an agent reports back.',
    'Owner directive 2026-10-06: open tickets must NOT interrupt the agent. No tool call,',
    'no dispatch, no turn spent on them. This hook informs; it never blocks.',
    '',
  ];
  for (const t of stamped) {
    lines.push(
      `TICKET ${t.id}  [${t.severity ?? '?'}/${t.kind ?? '?'}]  ${String(t.summary).slice(0, 300)}`,
      `  Seat: worker (it must be able to WRITE its receipt).`,
      `  Put the literal string TICKET-${t.id} in the dispatch prompt so it can be matched.`,
      `  Evidence is on the ticket; read it before forming a view.`,
      '',
    );
  }
  let ctx = lines.join('\n').trim();
  if (ctx.length > MAX_CTX) ctx = `${ctx.slice(0, MAX_CTX - 60)}\n[ticket-dispatch] TRUNCATED.`;

  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: ctx } }));
} catch {
  process.exit(0); // a ticket bridge that throws must never wedge a prompt
}
process.exit(0);
