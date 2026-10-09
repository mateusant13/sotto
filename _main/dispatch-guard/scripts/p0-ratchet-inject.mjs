#!/usr/bin/env node
// p0-ratchet-inject.mjs -- UserPromptSubmit.
//
// THE DEFECT THIS EXISTS FOR, stated by the owner on 2026-10-06: "tu tem coisa a
// fazer, e nao ta fazendo" -- there is work outstanding and it is not being done.
//
// MEASURED SHAPE OF THE DEFECT, 2026-10-06. Across one session the agent produced
// report after report, each closing with a P0 section that named the next action and
// then did not take it. The receipts show the same text recurring: "P0 AGORA -- nothing.
// This is the final continuation; the turn ends here." Repeated on consecutive turns
// while the named work stayed undone. The reports were accurate and the agent was
// correct about its own priorities; what was missing was anything that carried a
// promise from one turn into the next.
//
// WHY A HOOK. MEASURED: nothing depends on the agent waking up. There is no cron in
// the CLI (`mcode --help` has no `cron` subcommand, verified 2026-10-06), so a
// UserPromptSubmit hook is the only carrier that runs every turn and survives a cold
// start. It runs BEFORE the model sees the prompt, which is the only place a nudge can
// still change the turn.
//
// IT NEVER BLOCKS. Only `additionalContext`. The previous blocker in this project
// refused the turn for 7 consecutive turns and had to be removed; a reminder that
// costs the agent its turn is worse than no reminder. This informs. It never refuses.
//
// IT IS NOT THE TICKLE INJECTOR. `ticket-dispatch-inject.mjs` injects EXTERNAL work
// (tickets). `selfaudit-dispatch-inject.mjs` injects the agent's own self-audit items.
// THIS one injects the agent's OWN UNKEPT PROMISES -- the "what I am doing now" it
// wrote, and the reasons it gave for not doing them. Different source, different duty.
//
// rc contract: 0 inject or pass silently, never 1. This hook must never wedge a prompt.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';

const MAX_ITEMS = 3;
const MAX_SCAN = 60;             // ROWS, not turns. MEASURED 2026-10-06: this was 12,
                                 // and a turn that makes five tool calls emits several
                                 // assistant rows, so 12 rows spanned only TWO turns --
                                 // the hook was ratcheting on stale text from half an
                                 // hour earlier. The unit was wrong, not the number.
const MAX_TURNS = 3;             // how many recent TURNS to consider, newest first
const MAX_ITEM_CHARS = 260;
const MAX_CTX = 2600;

const DB_PATH = process.env.RATCHET_DB ||
  join(process.env.USERPROFILE || '', '.minimax', 'v2', 'sqlite', 'runtime-state.sqlite');

function dataDir() {
  return process.env.PLUGIN_DATA || process.env.MINIMAX_PLUGIN_ROOT || process.cwd();
}
const statePath = () => join(dataDir(), 'p0-ratchet-state.json');

function readStdin() {
  try { const raw = readFileSync(0, 'utf8'); return raw ? JSON.parse(raw) : {}; } catch { return {}; }
}

// Discover the session id by shape, never by a field name I have not observed in a
// contract document that still exists.
function sessionIdOf(payload) {
  for (const [k, v] of Object.entries(payload || {})) {
    if (/session.*id/i.test(k) && typeof v === 'string' && /^mvs_/.test(v)) return v;
  }
  return null;
}

function loadState() { try { return JSON.parse(readFileSync(statePath(), 'utf8')); } catch { return { seen: {} }; } }
function saveState(s) {
  try { mkdirSync(dataDir(), { recursive: true }); writeFileSync(statePath(), JSON.stringify(s)); }
  catch { /* a state file that cannot be written must never wedge a prompt */ }
}

const hash = (s) => createHash('sha256').update(s).digest('hex').slice(0, 16);

// What counts as a promise the agent made about ITS OWN next action.
//   - "P0 AGORA", "P0 que vou fazer agora", "what I am doing now"
//   - the closing spec line when it says NO
// A ticket is NOT a promise: external work arrives with a ticket id and is injected by
// a different hook. Mixing them would blame the agent for work it was handed.
// Normalise a line BEFORE matching it. MEASURED 2026-10-06: the first version stripped
// only LEADING list/quote markers, so a real report's `**P0 que vou fazer AGORA:** nada`
// arrived as `*P0 que vou fazer AGORA:** ...`, failed the `^P0` anchor, and the hook
// stayed silent on exactly the shape it was written for. Markdown emphasis is markup,
// not content: strip it, and match the words.
function norm(raw) {
  return String(raw)
    .replace(/[*_`]/g, '')            // emphasis and code marks carry no meaning here
    .replace(/^\s*[-+>|#]+\s*/, '')    // list bullets, quotes, table pipes
    .replace(/^\s*\d+\.\s*/, '')      // numbered item marker
    .trim();
}

function harvest(text) {
  const out = [];
  const lines = text.split('\n');

  // 1. The spec line. "NO - <reason>" is the agent telling the reader it did not finish.
// MEASURED 2026-10-06, two bugs here on the first cut:
//   (a) it matched /:\s*NO\b/, but the line reads "...spec? NO - ..." -- there is no
//       colon before NO, so the arm never fired on the string the law mandates;
//   (b) it took the last line CONTAINING the marker, which in a report that QUOTES
//       the marker (a code block, a SELF-AUDIT reciting the rule) is the quotation,
//       not the verdict. It harvested the text "<motivo>`** -> `unfinished-spec`".
// Fence-awareness is the fix: a line inside ``` is an example, not a promise.
const NO_FENCE = (text) => {
  const out = [];
  let fenced = false;
  for (const l of text.split('\n')) {
    if (/^\s*```/.test(l)) { fenced = !fenced; continue; }
    if (!fenced) out.push(l);
  }
  return out;
};
const clean = NO_FENCE(text);
// The spec line is the agent's CLOSING line, so it must be near the end. Taking the
// last line that merely CONTAINS the marker harvests the agent's own quotation of the
// rule -- MEASURED 2026-10-06: a report that cites the required closing line inline
// (in backticks, mid-prose) yielded "<motivo>`** -> `unfinished-spec`" as the promise.
// Fence-stripping did not help: an inline quotation is not fenced. Proximity does.
const nonEmpty = clean.filter((l) => l.trim());
const tail = nonEmpty.slice(-3);
// BOTH separators. MEASURED 2026-10-06, third bug in this one function: the law
// mandates "spec? YES/NO", so the regex keyed on the question mark. The agent has been
// writing "spec:" -- a colon -- for most of its reports. The hook therefore could not
// see a single real promise, and kept re-arming a stale item harvested from a QUOTED
// copy of the rule in an older turn. A hook that watches for the exact punctuation of
// the contract rather than the MEANING of the sentence is a hook that watches the
// contract, not the agent.
let last = [...tail].reverse().find((l) => /Does your implementation meet the spec[?:]/i.test(l));
if (!last) last = [...nonEmpty].reverse().find((l) => /Does your implementation meet the spec[?:]/i.test(l));
if (last && /spec[?:]\s*NO\b/i.test(last)) {
  const why = last.replace(/^.*spec[?:]\s*NO\s*[-—:]?\s*/i, '').trim();
  if (why.length > 15) out.push({ kind: 'unfinished-spec', text: why });
}

// 2. The "doing NOW" line. Its CONTENT is what comes after the label on the SAME
// line -- a real report writes "**P0 que vou fazer AGORA:** nada. This is the final
// continuation", so treating the whole line as a header threw away the very sentence
// this hook exists to notice.
for (const raw of clean) {
  const line = norm(raw);
  const m = /^(?:P0\b.*?(?:agora|doing now)|what i am doing now)\s*[:—-]?\s*(.*)$/i.exec(line);
  if (!m) continue;
  const body = (m[1] || '').trim();
  // "nada", "nothing", "the turn ends here": a turn that closes by deferring itself.
  if (!body) continue;
  if (/^(nada|nothing)\b/i.test(body) || /final continuation|turn ends here|nao faco nada|não faço nada/i.test(body)) {
    out.push({ kind: 'deferred-self', text: body });
  } else if (/^(vou|i will|i'll|next:|then )/i.test(body)) {
    out.push({ kind: 'promised-next', text: body });
  } else if (body.length > 15) {
    out.push({ kind: 'promised-next', text: body });
  }
}

  // 3. "What I did NOT do, and why" -- each refusal is a promise deferred.
  let inNot = false;
  for (const raw of clean) {
    if (/^#{2,3}\s/.test(raw.trim())) {
      inNot = /what i did not do|o que (nao|não) fiz|N[ÃA]O FIZ/i.test(norm(raw));
      continue;
    }
    const line = norm(raw);
    if (!inNot || line.length < 15) continue;
    if (/^(nao|não|did not|not)\b/i.test(line)) out.push({ kind: 'declared-not-done', text: line });
  }
  return out;
}

try {
  const sid = sessionIdOf(readStdin());
  if (!sid) process.exit(0);
  if (!existsSync(DB_PATH)) process.exit(0);

  const db = new DatabaseSync('file:' + DB_PATH.replace(/\\/g, '/') + '?mode=ro', { readOnly: true });
  const rows = db.prepare(
    "SELECT data_json, turn_id FROM local_runtime_message_rows WHERE session_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT ?"
  ).all(sid, MAX_SCAN);
  db.close();

  // Group rows into TURNS, newest turn first, and concatenate each turn's text. A turn
  // is the unit a person means by "what I said last turn"; rows are not.
  const turns = [];
  const byTurn = new Map();
  for (const r of rows) {
    let t = '';
    try { t = JSON.parse(r.data_json || '{}').msg_content || ''; } catch { continue; }
    const key = r.turn_id || 'n/a';
    if (!byTurn.has(key)) { byTurn.set(key, []); turns.push(key); }
    byTurn.get(key).push(t);
  }

  let items = [], back = 0;
  for (const key of turns.slice(0, MAX_TURNS)) {
    const text = byTurn.get(key).join('\n');
    back++;
    if (/Does your implementation meet the spec\?|P0/i.test(text)) { items = harvest(text); if (items.length) break; }
  }
  if (items.length === 0) process.exit(0);

  const state = loadState();
  const turn = Number(state.turn || 0) + 1;
  const fresh = [];
  for (const it of items) {
    const h = hash(it.kind + '|' + it.text);
    // Re-arm after 3 turns. Not forever: a promise the agent has genuinely dropped
    // should stop being carried, or the ratchet becomes the very noise it replaces.
    if (state.seen[h] && turn - state.seen[h] < 3) continue;
    fresh.push({ ...it, h });
    if (fresh.length >= MAX_ITEMS) break;
  }
  if (fresh.length === 0) process.exit(0);

  for (const f of fresh) state.seen[f.h] = turn;
  state.turn = turn;
  state.last_inject_at = new Date().toISOString();
  state.last_session = sid;
  saveState(state);

  const lines = [
    '[p0 ratchet] you wrote a promise last turn and it is still open.',
    `(${back} assistant message(s) back in this session. This is YOUR own text, not an external queue.)`,
    '',
  ];
  for (const f of fresh) lines.push(`P0-${f.h}  [${f.kind}]  ${f.text.slice(0, MAX_ITEM_CHARS)}`);
  lines.push(
    '',
    'Do the first one NOW, with a tool call, before writing another report.',
    'This hook never blocks and never fails you. It only says out loud what you said.',
  );
  let ctx = lines.join('\n');
  if (ctx.length > MAX_CTX) ctx = ctx.slice(0, MAX_CTX - 40) + '\n[p0 ratchet] TRUNCATED.';

  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: ctx },
  }));
} catch {
  process.exit(0);   // a ratchet that throws must never wedge a prompt
}
process.exit(0);