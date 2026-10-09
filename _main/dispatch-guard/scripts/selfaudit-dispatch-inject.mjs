#!/usr/bin/env node
// selfaudit-dispatch-inject.mjs -- UserPromptSubmit.
//
// WHAT THIS IS. The owner, 2026-10-06: "regra que apos self audit, voce despacha
// subagents pra resolver os self audits. voce mesmo." Not a reminder -- a dispatch
// demand aimed at the agent's OWN findings.
//
// WHY A HOOK AND NOT ONLY A RULE. A rule in AGENTS.md is instruction; it is
// followed while attention lasts and skipped when the turn is long. Retraction
// 2026-10-06 recorded the harder constraint: cron does not exist in the CLI, so
// nothing may depend on the agent waking up. UserPromptSubmit runs EVERY turn, so
// it is the only carrier that survives a cold start. This hook is that carrier;
// the rule states what to do once the hook has named the work.
//
// THE LIMIT, STATED NOT HIDDEN. A hook process cannot call `task`. There is no
// spawn API in the hook contract (SessionStart, SessionEnd, UserPromptSubmit,
// PreToolUse, PermissionRequest, PostToolUse, SubagentStart, SubagentStop, Stop,
// PreCompact, PostCompact -- none of them dispatch). So this hook does NOT dispatch.
// It makes the pending findings VISIBLE at the top of the next turn, and the agent
// dispatches them itself. Anything claiming a hook dispatches subagents is a
// design that has never been run -- third occurrence of that shape tonight was
// `deny-fail-silent` (selftest 14/14, absent from the manifest).
//
// NEVER BLOCKS. Only `additionalContext`. Owner 2026-10-06: open work must not
// interrupt the agent or divert it into a tool call. This informs; it refuses
// nothing. A prompt bridge that throws must never wedge a prompt.
//
// rc contract: 0 inject or pass silently, never 1. An rc here carries no verdict.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';

const MAX_ITEMS = 3;          // per turn. A longer list is advice nobody reads.
const MAX_SCAN = 40;          // assistant messages walked back. A BOUNDED read:
                              // scanning the 98k-row table is the unbounded shape.
const MAX_ITEM_CHARS = 220;
const MAX_CTX = 4000;
const RE_INJECT_AFTER = 10;   // turns before an unresolved item is named again.

function dataDir() {
  return process.env.PLUGIN_DATA || process.env.MINIMAX_PLUGIN_ROOT || process.cwd();
}
const statePath = () => join(dataDir(), 'selfaudit-dispatch-state.json');

function readStdin() {
  try {
    const raw = readFileSync(0, 'utf8');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

// The session id field name has NOT been observed in the contract (that reference
// doc is gone from disk). So discover it rather than guess: any key shaped like
// *session*id carrying an mvs_ value. No such key -> exit silently, never guess.
function sessionIdOf(payload) {
  for (const [k, v] of Object.entries(payload || {})) {
    if (/session.*id/i.test(k) && typeof v === 'string' && /^mvs_/.test(v)) return v;
  }
  return null;
}

function loadState() {
  try { return JSON.parse(readFileSync(statePath(), 'utf8')); } catch { return { seen: {} }; }
}
function saveState(s) {
  try { mkdirSync(dataDir(), { recursive: true }); writeFileSync(statePath(), JSON.stringify(s)); }
  catch { /* a state file that cannot be written must never wedge a prompt */ }
}

const hash = (s) => createHash('sha256').update(s).digest('hex').slice(0, 16);

// Pull the newest assistant message that carries a SELF-AUDIT, then harvest the
// two items that name WORK rather than opinion:
//   item 3 - "New checkboxes (named, mechanical)"  -> a check that does not exist yet
//   item 7 - "gate-melhor:" / "falta-no-gate:"     -> a gate the lane itself asked for
// Item 4 (review by another subagent) is harvested too: it is the one the agent
// keeps skipping.
function harvest(auditText) {
  const out = [];
  const lines = auditText.split('\n');
  let section = '';
  for (const raw of lines) {
    const line = raw.trim();
    const h = /^#{2,3}\s*(?:\d+\.\s*)?(.+)$/.exec(line);
    const numbered = /^(\d+)\.\s*(.+)$/.exec(line);
    if (h && /^##/.test(raw)) {
      section = h[1].toLowerCase();
      continue;
    }
    // A SELF-AUDIT item is a NUMBERED LINE, not a heading. MEASURED 2026-10-06:
    // this hook only recognised `##` headings, so items 3 and 4 were never treated
    // as sections and it harvested only gate-melhor/falta-no-gate -- silently missing
    // half of what it exists to find. Caught by a FIXTURE arm, not by reading: the
    // live-session arm had been passing with the bug present.
    if (numbered) {
      section = numbered[2].toLowerCase();
      // The item line ITSELF is the work. A real SELF-AUDIT writes
      // "3. **New checkboxes (named, mechanical).** (a) run the census; (b) ..." all
      // on ONE line -- there is no body line underneath. MEASURED 2026-10-06: the
      // first fix harvested only the following body line and therefore returned
      // nothing at all against a realistic audit, while a fixture that had put each
      // item's text on its own line made it look correct.
      if (/new checkboxes|review by another/.test(section)) {
        const body = numbered[2].replace(/^\**|\**$/g, '').trim();
        if (body.length > 8) {
          out.push({
            kind: /new checkboxes/.test(section) ? 'new checkbox' : 'review seat',
            text: body,
          });
        }
        continue;
      }
    }
    if (!line) continue;

    const gm = /`?gate-melhor:`?\s*(.+)/i.exec(line);
    if (gm && gm[1].trim().length > 8) {
      out.push({ kind: 'gate-melhor', text: gm[1].trim() });
      continue;
    }
    const fn = /`?falta-no-gate:`?\s*(.+)/i.exec(line);
    if (fn && fn[1].trim().length > 8) {
      out.push({ kind: 'falta-no-gate', text: fn[1].trim() });
      continue;
    }
    // The item's own body line IS the work: under "New checkboxes" it is a check
    // that does not exist yet, under "Review by another subagent" it is the review
    // that keeps getting skipped. Both are harvested whole.
    if (/new checkboxes|review by another/.test(section) && line.length > 12
        && !/^\d+\./.test(line)) {
      out.push({
        kind: /new checkboxes/.test(section) ? 'new checkbox' : 'review seat',
        text: line.replace(/^\(?[a-d0-9ivx]+\)?[.)\s]*/i, ''),
      });
    }
  }
  return out;
}

// The DB path is overridable so a selftest can point the hook at a FIXTURE store.
// Measured 2026-10-06: the first version of this hook derived the path from
// USERPROFILE only, so its selftest arm asserted against whatever the agent had
// actually said in the last 40 turns. That arm passed at 06:05 and failed at 07:0x
// with no code change — a time-dependent assertion is not an assertion, it is a coin
// toss that happens to be green often. The fixture makes it deterministic.
const DB_PATH = process.env.SELFAUDIT_DB ||
  join(process.env.USERPROFILE || '', '.minimax', 'v2', 'sqlite', 'runtime-state.sqlite');

try {
  const payload = readStdin();
  const sid = sessionIdOf(payload);
  if (!sid) process.exit(0);

  if (!existsSync(DB_PATH)) process.exit(0);
  const db = new DatabaseSync('file:' + DB_PATH.replace(/\\/g, '/') + '?mode=ro', { readOnly: true });
  const rows = db.prepare(
    "SELECT data_json FROM local_runtime_message_rows WHERE session_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT ?"
  ).all(sid, MAX_SCAN);
  db.close();

  let items = [];
  let ageTurns = 0;
  for (const row of rows) {
    let text = '';
    try { text = JSON.parse(row.data_json || '{}').msg_content || ''; } catch { continue; }
    ageTurns++;
    if (text.includes('## SELF-AUDIT')) { items = harvest(text); break; }
  }
  if (items.length === 0) process.exit(0);

  const state = loadState();
  const fresh = [];
  for (const it of items) {
    const h = hash(it.kind + '|' + it.text);
    const prev = state.seen[h];
    const lastTurn = Number(state.turn || 0);
    if (prev && lastTurn - prev.turn < RE_INJECT_AFTER) continue;   // already named, recently
    fresh.push({ ...it, h });
    if (fresh.length >= MAX_ITEMS) break;
  }
  if (fresh.length === 0) process.exit(0);

  const turn = Number(state.turn || 0) + 1;
  for (const f of fresh) state.seen[f.h] = { turn, kind: f.kind, text: f.text.slice(0, MAX_ITEM_CHARS) };
  state.turn = turn;
  state.last_inject_at = new Date().toISOString();
  state.last_session = sid;
  saveState(state);

  const lines = [
    `[self-audit carry-over] ${fresh.length} item(s) from your own last SELF-AUDIT`,
    `(${ageTurns} assistant message(s) back in session ${sid.slice(0, 12)}; window = this session only.)`,
    '',
    'These are YOUR findings, not an interruption and not a ticket backlog.',
    'Nothing here requires a tool call to acknowledge and nothing blocks your turn.',
    'The rule you are holding: after a SELF-AUDIT, YOU dispatch the subagents that close it.',
    'Fold these into your next dispatch batch. A worker seat (not explore/verifier) for anything',
    'that must WRITE a receipt. Put the literal marker SA-<hash> in each dispatch prompt.',
    '',
  ];
  for (const f of fresh) {
    lines.push(`SA-${f.h}  [${f.kind}]  ${f.text.slice(0, MAX_ITEM_CHARS)}`);
  }
  lines.push('');
  let ctx = lines.join('\n');
  if (ctx.length > MAX_CTX) ctx = ctx.slice(0, MAX_CTX - 40) + '\n[self-audit carry-over] TRUNCATED.';

  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: ctx },
  }));
} catch {
  process.exit(0);   // an audit bridge that throws must never wedge a prompt
}
process.exit(0);