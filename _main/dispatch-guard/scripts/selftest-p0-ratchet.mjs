#!/usr/bin/env node
// selftest-p0-ratchet.mjs
//
// The arms are driven by a FIXTURE store, never by the agent's live session.
// MEASURED 2026-10-06, twice now: a live-session arm passes at 06:05 and fails at
// 07:0x with no code change, because it was asserting against whatever the agent had
// said lately. A time-dependent assertion is not an assertion.
//
// Arm W1-W3 are WIRING arms: they read the manifest the runtime actually loads.
// Three tools in this project passed their own component tests and were unreachable.
// rc 0 all pass | 1 a real RED | 2 the plugin is not installed (NO VERDICT)
import { readFileSync, existsSync, mkdtempSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';

const HERE = dirname(new URL(import.meta.url).pathname.replace(/^\//, '').replace(/^(.)/, (c) => c.toUpperCase()));
const SCRIPT = join(HERE, 'p0-ratchet-inject.mjs');
const HOOKS_JSON = join(HERE, '..', 'hooks', 'hooks.json');
const SID = 'mvs_ratchetfixture00000000000000';

let pass = 0, fail = 0;
function arm(name, ok, detail) {
  if (ok) { pass++; console.log(`  PASS  ${name}${detail ? '  -- ' + detail : ''}`); }
  else { fail++; console.log(`  FAIL  ${name}${detail ? '  -- ' + detail : ''}`); }
}

// A report shaped exactly like the one the owner complained about.
const DEFERRING = [
  '# Work',
  'Here is what happened.',
  '',
  '## P0 - IN THREE',
  '',
  '**P0 que vou fazer AGORA:** nada. This is the final continuation; the turn ends here.',
  '',
  '**P0 que JA FIZ:** the ledger fix.',
  '',
  '**P0 que NAO FIZ, e porquê:** read the receipts of the closed lanes.',
  '',
  '## SELF-AUDIT',
  '1. fine',
  '',
  'Does your implementation meet the spec? NO - the AGENTS.md is still uncommitted because seven laws block it',
].join('\n');

const DONE = [
  '## P0 - IN THREE',
  '**P0 que vou fazer AGORA:** shipped it.',
  '',
  'Does your implementation meet the spec? YES - everything landed',
].join('\n');

function fixtureDb(name, body) {
  const tmp = mkdtempSync(join(tmpdir(), 'ratchet-'));
  const dbPath = join(tmp, 'fixture.sqlite');
  execFileSync(process.execPath, ['-e', `
    const { DatabaseSync } = require('node:sqlite');
    const db = new DatabaseSync(process.argv[1]);
    // turn_id IS PART OF THE SCHEMA. The fixture originally omitted it, so the hook's
    // query for the newest TURN failed and 4 arms went red for a reason that had
    // nothing to do with what the fixture was meant to prove. A fixture that does not
    // match the real schema tests a schema, not the behaviour.
    db.exec('CREATE TABLE local_runtime_message_rows (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, turn_id TEXT, created_at_ms INTEGER, data_json TEXT)');
    db.prepare('INSERT INTO local_runtime_message_rows (session_id, role, turn_id, created_at_ms, data_json) VALUES (?,?,?,?,?)')
      .run(process.argv[2], 'assistant', 'turn_fixture01', 1, JSON.stringify({ msg_content: process.argv[3] }));
    db.close();
  `, dbPath, SID, body], { encoding: 'utf8' });
  return { tmp, dbPath };
}

function run(dbPath, tag) {
  const dd = mkdtempSync(join(tmpdir(), 'ratchet-data-'));
  const out = execFileSync(process.execPath, [SCRIPT], {
    input: JSON.stringify({ session_id: SID }),
    encoding: 'utf8',
    env: { ...process.env, PLUGIN_DATA: dd, RATCHET_DB: dbPath },
  });
  let ctx = '';
  try { ctx = JSON.parse(out).hookSpecificOutput?.additionalContext || ''; } catch {}
  rmSync(dd, { recursive: true, force: true });
  void tag;
  return ctx;
}

console.log('selftest: p0-ratchet-inject.mjs');

// 1 - a deferring report MUST produce ratchet items. This is the exact defect.
{
  const f = fixtureDb('deferring', DEFERRING);
  const ctx = run(f.dbPath, 'deferring');
  arm('a deferring report yields ratchet items', /P0-[0-9a-f]{16}/.test(ctx),
    ctx ? `${(ctx.match(/P0-[0-9a-f]{16}/g) || []).length} item(s)` : 'ctx empty');
  arm('it names the unfinished spec line', /unfinished-spec/.test(ctx));
  arm('it names the self-deferral', /deferred-self/.test(ctx));
  rmSync(f.tmp, { recursive: true, force: true });
}

// 2 - a report that says YES and shipped MUST NOT ratchet. A ratchet that fires on
//     finished work is noise, and noise is what this replaced.
{
  const f = fixtureDb('done', DONE);
  const ctx = run(f.dbPath, 'done');
  arm('a YES report yields nothing', ctx.trim() === '', JSON.stringify(ctx.slice(0, 120)));
  rmSync(f.tmp, { recursive: true, force: true });
}

// 3 - no session id: silent pass, never a guess at which session this is.
{
  const out = execFileSync(process.execPath, [SCRIPT], {
    input: JSON.stringify({ cwd: 'I:\\!manager' }), encoding: 'utf8',
    env: { ...process.env, PLUGIN_DATA: mkdtempSync(join(tmpdir(), 'ratchet-data-')) },
  });
  arm('no session id -> silent pass', out.trim() === '', JSON.stringify(out.slice(0, 120)));
}

// 4 - malformed stdin must not wedge a prompt.
{
  let crashed = false, out = '';
  try {
    out = execFileSync(process.execPath, [SCRIPT], {
      input: '{not json', encoding: 'utf8',
      env: { ...process.env, PLUGIN_DATA: mkdtempSync(join(tmpdir(), 'ratchet-data-')) },
    });
  } catch (e) { crashed = true; out = String(e.stderr || e.message); }
  arm('malformed stdin -> exit 0, no crash', !crashed && out.trim() === '', out.slice(0, 140));
}

// 5 - it NEVER blocks. A blocker refused this project for 7 consecutive turns and had
//     to be removed; the reminder must not become the thing it replaced.
{
  const f = fixtureDb('deferring2', DEFERRING);
  const res = execFileSync(process.execPath, [SCRIPT], {
    input: JSON.stringify({ session_id: SID }), encoding: 'utf8',
    env: { ...process.env, PLUGIN_DATA: mkdtempSync(join(tmpdir(), 'ratchet-data-')), RATCHET_DB: f.dbPath },
  });
  let parsed = null;
  try { parsed = JSON.parse(res); } catch {}
  const onlyContext = parsed && parsed.hookSpecificOutput &&
    parsed.hookSpecificOutput.hookEventName === 'UserPromptSubmit' &&
    Object.keys(parsed).length === 1 && !('decision' in parsed);
  arm('output carries additionalContext only, never a decision', !!onlyContext,
    onlyContext ? '' : JSON.stringify(parsed || res).slice(0, 160));
  rmSync(f.tmp, { recursive: true, force: true });
}

// 6 - THE WIRING ARM. Built is not wired; three tools tonight passed their own tests
//     and were unreachable from the runtime.
{
  let hooks = null;
  try { hooks = JSON.parse(readFileSync(HOOKS_JSON, 'utf8')); } catch {}
  const named = hooks ? JSON.stringify(hooks).includes('p0-ratchet-inject.mjs') : false;
  let bound = false;
  if (hooks && hooks.hooks) {
    const ups = hooks.hooks.UserPromptSubmit || [];
    for (const g of (Array.isArray(ups) ? ups : [ups])) {
      if (JSON.stringify(g).includes('p0-ratchet-inject.mjs')) bound = true;
    }
  }
  arm('hook is NAMED in hooks.json', named);
  arm('hook is BOUND to UserPromptSubmit', bound, bound ? '' : 'built but unreachable');
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);