#!/usr/bin/env node
// ticket-dispatch-record.mjs - PreToolUse, matcher `task`. Observe a REAL dispatch.
//
// This hook MEASURES, it does not decide. Its only job is to turn "the agent said it dispatched"
// into a fact the Stop binder can rely on, by looking at the actual `task` payload at the moment
// the call is made. That distinction is the whole point: a report claiming a subagent exists is a
// claim, and this is the evidence.
//
// It never denies. A hook that blocks every `task` call to audit it would be turned off within a
// day, and a hook that is turned off is a hook that has stopped existing.
//
// rc contract: 0 always (silent observation).
import { readFileSync, existsSync, appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

function dataDir() {
  return process.env.PLUGIN_DATA || process.env.MINIMAX_PLUGIN_ROOT || process.cwd();
}
const queuePath = () => join(dataDir(), 'ticket-dispatch-queue.jsonl');
const donePath = () => join(dataDir(), 'ticket-dispatch-done.jsonl');

function readPayload() {
  try {
    const raw = readFileSync(0, 'utf8');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

try {
  const payload = readPayload();
  const name = String(payload.tool_name ?? payload.toolName ?? '');
  if (name.toLowerCase() !== 'task') process.exit(0);
  if (!existsSync(queuePath())) process.exit(0);

  const input = payload.tool_input ?? payload.toolInput ?? {};
  const blob = `${input.description ?? ''}\n${input.prompt ?? ''}`;

  const queued = [];
  for (const line of readFileSync(queuePath(), 'utf8').split('\n')) {
    if (!line.trim()) continue;
    try { const r = JSON.parse(line); if (r && r.id) queued.push(r); } catch { /* skip */ }
  }
  if (queued.length === 0) process.exit(0);

  const done = new Set();
  if (existsSync(donePath())) {
    for (const line of readFileSync(donePath(), 'utf8').split('\n')) {
      if (!line.trim()) continue;
      try { const r = JSON.parse(line); if (r && r.id) done.add(r.id); } catch { /* skip */ }
    }
  }

  const fresh = [];
  for (const t of queued) {
    if (done.has(t.id)) continue;
    if (blob.includes(`TICKET-${t.id}`) || blob.includes(t.id)) {
      fresh.push({ id: t.id, ts: new Date().toISOString(), agent: input.agent_name ?? null });
    }
  }
  if (fresh.length === 0) process.exit(0);

  mkdirSync(dataDir(), { recursive: true });
  appendFileSync(donePath(), fresh.map((r) => JSON.stringify(r)).join('\n') + '\n');
} catch {
  /* an observer that throws must not break the dispatch it is observing */
}
process.exit(0);
