#!/usr/bin/env node
// selftest-selfaudit-dispatch.mjs
//
// WHY THIS ENDS ON A WIRING ASSERTION. Three tools passed their own selftest
// tonight and were unreachable: optchat-view, deny-fail-silent (14/14, absent
// from the manifest), ticket-dispatch-record. A selftest that only exercises the
// component proves the component. The defect was never the component.
//
// So arm 6 reads hooks.json and fails if this hook is not bound to a real event.
// A green here means "built AND named by the runtime's own config".
//
// rc 0 all arms pass, 1 a real RED, 2 no verdict.
import { readFileSync, existsSync, writeFileSync, rmSync, mkdtempSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';

const HERE = dirname(new URL(import.meta.url).pathname.replace(/^\//, '').replace(/^(.)/, (m, c) => c.toUpperCase()));
const SCRIPT = join(HERE, 'selfaudit-dispatch-inject.mjs');
const HOOKS_JSON = join(HERE, '..', 'hooks', 'hooks.json');
const MY_SESSION = 'mvs_ea552229fe164f9e8856fcca8589c41a';

let pass = 0, fail = 0;
function arm(name, ok, detail) {
  if (ok) { pass++; console.log(`  PASS  ${name}${detail ? '  -- ' + detail : ''}`); }
  else { fail++; console.log(`  FAIL  ${name}${detail ? '  -- ' + detail : ''}`); }
}

function run(payload, dataDir) {
  const dd = dataDir || mkdtempSync(join(tmpdir(), 'sa-'));
  const res = execFileSync(process.execPath, [SCRIPT], {
    input: JSON.stringify(payload), encoding: 'utf8', env: { ...process.env, PLUGIN_DATA: dd },
  });
  return { out: res, dataDir: dd };
}

console.log('selftest: selfaudit-dispatch-inject.mjs');

// 1 - a FIXTURE store with a crafted SELF-AUDIT. NOT the live session.
//
// MEASURED 2026-10-06: this arm originally ran against the agent's real session and
// asserted that markers came back. It passed at 06:05 and failed at 07:0x with NO
// code change, because it was asserting against whatever had been said in the last
// 40 turns. That is a time-dependent assertion, not an assertion. The fixture below
// makes the arm deterministic: the same input yields the same verdict forever.
{
  const tmp = mkdtempSync(join(tmpdir(), 'sa-db-'));
  const dbPath = join(tmp, 'fixture.sqlite');
  execFileSync(process.execPath, ['-e', `
    const { DatabaseSync } = require('node:sqlite');
    const db = new DatabaseSync(process.argv[1]);
    db.exec('CREATE TABLE local_runtime_message_rows (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, created_at_ms INTEGER, data_json TEXT)');
    const audit = [
      '## SELF-AUDIT',
      '1. Protocols missing: none.',
      '3. **New checkboxes (named, mechanical).** (a) run the census on every durable store; (b) assert intended == persisted.',
      '4. **Review by another subagent.** not run - recorded as skipped.',
      '7. **Gate-doubt.** gate-melhor: add a mutation arm so the suite can be shown to fail.\\n   falta-no-gate: a new state the vocabulary does not know.',
    ].join('\\n');
    const stmt = db.prepare('INSERT INTO local_runtime_message_rows (session_id, role, created_at_ms, data_json) VALUES (?,?,?,?)');
    stmt.run('mvs_fixturesession0000000000000000', 'assistant', 1, JSON.stringify({ msg_content: audit }));
    db.close();
  `, dbPath], { encoding: 'utf8' });

  const dd = mkdtempSync(join(tmpdir(), 'sa-'));
  const res = execFileSync(process.execPath, [SCRIPT], {
    input: JSON.stringify({ session_id: 'mvs_fixturesession0000000000000000' }),
    encoding: 'utf8',
    env: { ...process.env, PLUGIN_DATA: dd, SELFAUDIT_DB: dbPath },
  });
  let ctx = '';
  try { ctx = JSON.parse(res).hookSpecificOutput?.additionalContext || ''; } catch {}
  const markers = (ctx.match(/SA-[0-9a-f]{16}/g) || []).length;
  const kinds = ['gate-melhor', 'new checkbox', 'review seat']
    .filter((k) => ctx.includes('[' + k + ']'));
  arm('fixture SELF-AUDIT yields SA- markers', markers >= 3, `markers=${markers}`);
  arm('fixture SELF-AUDIT yields the named work kinds', kinds.length === 3,
    `kinds found: ${kinds.join(',') || 'none'}`);
  arm('fixture injection is capped at MAX_ITEMS', markers <= 3, `markers=${markers} (cap 3)`);
  rmSync(tmp, { recursive: true, force: true });
  rmSync(dd, { recursive: true, force: true });
}

// 2 - no session id in the payload: exit quietly. A bridge that guesses which
//     session it is in would carry another workspace's audit.
{
  const r = run({ hook_event_name: 'UserPromptSubmit', cwd: 'I:\\!manager' });
  arm('no session id -> silent pass', r.out.trim() === '', JSON.stringify(r.out.slice(0, 120)));
}

// 3 - a real session that has no SELF-AUDIT in the window.
{
  const r = run({ session_id: 'mvs_0000000000000000000000000000000' });
  arm('unknown session -> silent pass', r.out.trim() === '', JSON.stringify(r.out.slice(0, 120)));
}

// 4 - malformed stdin must not wedge a prompt.
{
  let crashed = false, out = '';
  try {
    const r = execFileSync(process.execPath, [SCRIPT], { input: '{not json', encoding: 'utf8',
      env: { ...process.env, PLUGIN_DATA: mkdtempSync(join(tmpdir(), 'sa-')) } });
    out = r;
  } catch (e) { crashed = true; out = String(e.stderr || e.message); }
  arm('malformed stdin -> exit 0, no crash', !crashed && out.trim() === '', out.slice(0, 160));
}

// 5 - dedup: the same state dir twice, the second must stay silent or the hook
//     would nag the same finding every single turn.
{
  const dd = mkdtempSync(join(tmpdir(), 'sa-'));
  const first = run({ session_id: MY_SESSION }, dd);
  const second = run({ session_id: MY_SESSION }, dd);
  arm('second identical turn is silent (dedup)', second.out.trim() === '',
    `first=${first.out.trim() ? 'injected' : 'silent'} second=${second.out.trim() ? 'injected' : 'silent'}`);
  rmSync(dd, { recursive: true, force: true });
}

// 6 - THE WIRING ARM. Built is not wired.
{
  let hooks = null;
  try { hooks = JSON.parse(readFileSync(HOOKS_JSON, 'utf8')); } catch {}
  const raw = hooks ? JSON.stringify(hooks) : '';
  const named = raw.includes('selfaudit-dispatch-inject.mjs');
  let bound = false;
  if (hooks && hooks.hooks) {
    for (const [event, arr] of Object.entries(hooks.hooks)) {
      for (const h of (Array.isArray(arr) ? arr : [arr])) {
        if (JSON.stringify(h).includes('selfaudit-dispatch-inject.mjs') && event === 'UserPromptSubmit') bound = true;
      }
    }
  }
  arm('hook is NAMED in hooks.json', named);
  arm('hook is BOUND to UserPromptSubmit', bound,
    bound ? '' : 'built but unreachable - the deny-fail-silent shape');
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);