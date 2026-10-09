#!/usr/bin/env node
// debt-inject.mjs - SessionStart hook. The other half of debt-record.mjs.
//
// Its sibling writes obligations into a durable ledger because a SELF-AUDIT section dies with
// the message. This one puts the unpaid obligations back in front of the agent at the START of
// the next turn, so the first thing read is what is owed, not what is new.
//
// SessionStart supports `additionalContext` (references/local-plugin-hooks.md), which the runtime
// appends into the turn. Emitting nothing when there is no debt is the normal case.
//
// rc contract: 0 pass silently (including on any internal failure - this hook must never wedge a
// session start), 1 only when it emits a decision block, which SessionStart does not need.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const MAX_LEDGER_BYTES = 512 * 1024;
const MAX_ITEMS = 10;
const MAX_CTX = 65536;

function dataDir() {
  if (process.env.PLUGIN_DATA) return process.env.PLUGIN_DATA;
  if (process.env.MINIMAX_PLUGIN_ROOT) return process.env.MINIMAX_PLUGIN_ROOT;
  return process.cwd();
}

try {
  const p = join(dataDir(), 'self-audit-debt.jsonl');
  if (!existsSync(p)) process.exit(0);
  if (readFileSync(p).length > MAX_LEDGER_BYTES) process.exit(0);

  const rows = readFileSync(p, 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return null;
      }
    })
    .filter(Boolean);

  // Collapse to the newest state per key: a later row for the same key supersedes an earlier one.
  const byKey = new Map();
  for (const r of rows) if (r && r.key) byKey.set(r.key, r);
  const open = [...byKey.values()].filter((r) => r.state === 'open').slice(0, MAX_ITEMS);
  if (open.length === 0) process.exit(0);

  const lines = [
    'UNPAID DEBT FROM YOUR OWN EARLIER SELF-AUDITS. You admitted these in previous reports and',
    'have not resolved them. They are not new work and not the owner\'s request; they are yours.',
    'Resolve one, or name its blocker explicitly, before opening anything new.',
    '',
  ];
  for (const o of open) lines.push(`- ${o.text}`);
  let ctx = lines.join('\n').trim();
  if (ctx.length > MAX_CTX) ctx = `${ctx.slice(0, MAX_CTX - 60)}\n[debt-inject] TRUNCATED.`;
  process.stdout.write(
    JSON.stringify({ hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: ctx } }),
  );
} catch {
  process.exit(0); // a debt ledger that cannot be read must never wedge a session start
}
process.exit(0);