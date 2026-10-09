#!/usr/bin/env node
// debt-record.mjs - Stop hook.
//
// THE PAIN, MEASURED. In one session (POPULATION 3 consecutive turns, WINDOW 2026-10-06
// 02:2x-02:38) the agent wrote a SELF-AUDIT admitting the same two obligations three times
// running - "the claim-falsifier commit is still not landed" and "the consultgpt rule is still
// not written to memory" - and resolved ZERO of them. Each report re-admitted them. Each report
// was honest. Honesty is not the failure; AMNESIA is.
//
// WHY A WRITTEN SECTION CANNOT FIX THIS. A SELF-AUDIT is a section inside a message. It is
// delivered, the turn ends, and the text goes nowhere. The next turn starts with no memory that
// anything was ever owed, so the same admission is re-derived from scratch - or, worse, quietly
// dropped. The obligation has no store, no owner and no expiry, so it cannot bind anything.
//
// WHAT THIS DOES. The admissions are lifted OUT of the message and into a durable ledger under
// ${PLUGIN_DATA}, which survives the turn. A SessionStart sibling (debt-inject.mjs) reads that
// ledger and puts the unpaid debt back in front of the agent at the start of the next turn. This
// script then REFUSES a turn that opens new debt while older debt is still unpaid, unless the
// report explicitly re-defers the older items - so admitting is never free.
//
// rc contract: 0 pass silently, 1 block with a reason, 2 never (never crash into a verdict).
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const MAX_LEDGER_BYTES = 512 * 1024;
const STALL_LIMIT = 2; // consecutive turns an item may be re-admitted before the hook pushes

// An admission is a sentence that says work is NOT done. Narrow on purpose: this fires on every
// turn, and a hook that fires on everything is a hook that gets ignored.
const ADMISSION = [
  /what i did not do/i,
  /what was not verified/i,
  /protocolos? em falta/i,
  /protocols? missing/i,
  /\bnot verified\b/i,
  /\bnao verifiquei\b/i,
  /\bnao fiz\b/i,
  /\bn[aã]o fiz\b/i,
  /\bP0\s+NAO\s+FEITO\b/i,
  /\bcontinua por\b/i,
  /\bainda n[aã]o\b/i,
  /\bpendente\b/i,
  /\bremains? (?:unlanded|unwritten|pending|outstanding)\b/i,
  /\bnot landed\b/i,
  /\bnot done\b/i,
];

// An explicit deferral is the ONLY lawful way to carry debt into another turn: name it again and
// say why it is still open. Re-saying it silently is how the three-turn loop above happened.
const DEFERRAL = /\b(?:deferred|adiado|carry(?:ing)? (?:this )?(?:over|forward)|still open|next turn|amanh[aã]|blocked (?:on|by)|waiting (?:on|for)|porqu[e]|porque)\b/i;

function readPayload() {
  try {
    const raw = readFileSync(0, 'utf8');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function dataDir() {
  return process.env.PLUGIN_DATA || process.env.MINIMAX_PLUGIN_ROOT
    ? process.env.PLUGIN_DATA || process.env.MINIMAX_PLUGIN_ROOT
    : process.cwd();
}

function ledgerPath() {
  return join(dataDir(), 'self-audit-debt.jsonl');
}

function loadLedger() {
  const p = ledgerPath();
  if (!existsSync(p)) return [];
  try {
    if (readFileSync(p).length > MAX_LEDGER_BYTES) return [];
    return readFileSync(p, 'utf8')
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
  } catch {
    return [];
  }
}

function append(items) {
  if (items.length === 0) return;
  try {
    mkdirSync(dataDir(), { recursive: true });
    const body = items.map((i) => JSON.stringify(i)).join('\n') + '\n';
    writeFileSync(ledgerPath(), body, { flag: 'a' });
  } catch {
    /* a debt ledger that cannot be written must not wedge the turn */
  }
}

function block(reason) {
  process.stdout.write(JSON.stringify({ decision: 'block', reason }));
  process.exit(1);
}

// MEASURED 2026-10-06: this hook was DEAD and had been for turns, and the ledger is why.
//
// The matching used to be `new RegExp(item.key, 'i').test(message)`. The key is built as
//     line.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').slice(0, 120)
// ESCAPING RUNS FIRST and the 120-char slice runs SECOND, so the slice can cut an escape
// sequence in half. `\\*` becomes a lone `\` and `new RegExp` throws:
//
//     SyntaxError: Invalid regular expression: ... nao prova nada\
//     bad escape (end of pattern) at position 119
//
// That throw happens at line 124, BEFORE `append(fresh)` at the end. So the failure was not only
// that the hook stopped ENFORCING - it stopped RECORDING. New self-audit debt was no longer
// captured either, and the hook still exited 1, the same code as a deliberate block. The rc
// carried a CAUSE where a VERDICT belonged.
//
// CENSUS: 2 of 49 distinct keys in the durable ledger would not compile, both still OPEN, both
// failing at position 119. One of them is a line this same agent wrote in its own SELF-AUDIT.
// An agent's honest admission about paths containing `*` was enough to switch the mechanism off.
//
// A substring match cannot throw, and "the item is still named" is a substring question, not a
// pattern question. Old malformed keys keep working with no migration: `text` holds the RAW
// line, unescaped and untruncated apart from the 280-char cap.
function isNamed(item, message) {
  const needle = String(item.text ?? '').trim();
  if (!needle) return false;
  return message.toLowerCase().includes(needle.toLowerCase());
}

const payload = readPayload();
const message = String(payload.last_assistant_message ?? '');
if (!message.trim()) process.exit(0);

const admitsDebt = ADMISSION.some((rx) => rx.test(message));
const ledger = loadLedger();

// open = an item admitted in an EARLIER turn that this message has not closed.
const open = ledger.filter((i) => i.state === 'open' && i.turn !== payload.session_id);

// RESOLUTION RUNS FIRST, ALWAYS. An earlier version exited on `!admitsDebt` before this block,
// which made debt UNCLOSABLE: a turn that simply stopped admitting an item could never close it,
// so the item stayed open forever and the ledger grew a phantom tail. The selftest arm
// `resolution-is-recorded-as-closed` is exactly this bug; it is why the arm exists.
const stillNamed = [];
for (const item of open) {
  if (isNamed(item, message)) stillNamed.push(item);
}
const silentlyDropped = open.filter((i) => !stillNamed.includes(i));

if (silentlyDropped.length > 0) {
  append(silentlyDropped.map((i) => ({ ...i, state: 'resolved', closed_turn: payload.session_id })));
}

if (!admitsDebt) process.exit(0); // nothing new owed; resolutions above are already recorded

const carried = stillNamed.filter((i) => !DEFERRAL.test(message));

if (open.length > 0 && carried.length >= STALL_LIMIT) {
  const list = carried.map((i) => `  - ${i.text}`).join('\n');
  block(
    `You are re-admitting debt you have already admitted ${carried.length + 1} times without ` +
      `resolving it and without saying why it is still open:\n${list}\n\n` +
      `An admission that repeats is not an admission, it is a ritual. Do ONE of these now, in ` +
      `this turn, before anything else:\n` +
      `  (a) DO the item, and stop listing it;\n` +
      `  (b) RE-DEFER it by naming it AND the blocker ("still blocked on X");\n` +
      `  (c) DROP it deliberately and say you are dropping it.\n` +
      `The same obligation has now survived ${carried.length + 1} reports. One continuation ` +
      `only, then the turn ends either way.`,
  );
}

// Record this turn's admissions so the next SessionStart can surface them.
const fresh = [];
for (const m of message.matchAll(/^[^\n]{10,300}$/gm)) {
  const line = m[0].trim();
  // A Markdown HEADING is structure, not an obligation. Measured defect, 2026-10-06:
  // `## P0 - o que NAO FIZ` matched the admission pattern and became a permanent debt item. A
  // heading that reappears in every report can never be resolved, because resolution is defined
  // as "the next report stops naming it" - so the item lived forever and was injected into every
  // later SessionStart. A bullet UNDER that heading is a real admission and is still captured.
  if (/^#{1,6}\s/.test(line)) continue;
  if (!ADMISSION.some((rx) => rx.test(line))) continue;
  if (fresh.some((f) => f.text === line)) continue;
  fresh.push({
    turn: payload.session_id,
    ts: payload.turn_id ?? '',
    text: line.slice(0, 280),
    // Slice FIRST, escape SECOND. Escaping then slicing is what produced two uncompilable keys:
    // the 120-char cut landed between a backslash and the character it was escaping.
    key: line.slice(0, 120).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
    state: 'open',
  });
  if (fresh.length >= 12) break;
}
append(fresh);
process.exit(0);