// selftest-debt.mjs - proves the debt hooks go GREEN and RED against the real scripts.
// Uses a scratch PLUGIN_DATA so the live ledger is never touched.
import { spawnSync } from 'node:child_process';
import { mkdtempSync, existsSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const RECORD = join(here, 'debt-record.mjs');
const INJECT = join(here, 'debt-inject.mjs');

const ADMIT = '## SELF-AUDIT\nPOPULATION 3, WINDOW now.\nWhat I did NOT do: land the claim-falsifier commit.\n';
const ADMIT2 = '## SELF-AUDIT\nPOPULATION 3, WINDOW now.\nWhat I did NOT do: land the claim-falsifier commit.\nProtocolos em falta: the consultgpt memory rule.\n';
const CLEAN = '## SELF-AUDIT\nPOPULATION 9, WINDOW now. P0 in three. Everything green.\n';
const DEFER = '## SELF-AUDIT\nPOPULATION 3, WINDOW now.\nWhat I did NOT do: land the claim-falsifier commit. Deferred: still blocked on the shared index.\n';

function fire(script, message, dir, turn) {
  const r = spawnSync(process.execPath, [script], {
    input: JSON.stringify({ hook_event_name: 'Stop', session_id: turn, turn_id: turn, last_assistant_message: message }),
    encoding: 'utf8', env: { ...process.env, PLUGIN_DATA: dir },
  });
  let reason = null;
  if (r.stdout && r.stdout.trim()) {
    try { reason = JSON.parse(r.stdout).reason ?? JSON.parse(r.stdout).hookSpecificOutput?.additionalContext ?? null; } catch { reason = 'UNPARSEABLE'; }
  }
  return { rc: r.status, reason };
}
function inject(dir, event = 'SessionStart') {
  const r = spawnSync(process.execPath, [INJECT], { input: JSON.stringify({ hook_event_name: event }), encoding: 'utf8', env: { ...process.env, PLUGIN_DATA: dir } });
  return { rc: r.status, out: r.stdout || '' };
}

let failed = 0;
const arm = (name, cond, detail) => {
  if (!cond) failed += 1;
  process.stdout.write(`${cond ? 'ok  ' : 'FAIL'} ${name} :: ${detail}\n`);
};

// RED: three consecutive re-admissions with no deferral must block on the third.
let d = mkdtempSync(join(tmpdir(), 'debt-'));
let r1 = fire(RECORD, ADMIT, d, 'turn-1');
let r2 = fire(RECORD, ADMIT2, d, 'turn-2');
let r3 = fire(RECORD, ADMIT, d, 'turn-3');
arm('red-third-repetition-blocks', r3.reason !== null, `t1=${r1.reason ? 'BLOCK' : 'pass'} t2=${r2.reason ? 'BLOCK' : 'pass'} t3=${r3.reason ? 'BLOCK' : 'pass'}`);
arm('first-turn-does-not-block', r1.reason === null, `t1 rc=${r1.rc}`);
arm('second-turn-does-not-block', r2.reason === null, `t2 rc=${r2.rc}`);
rmSync(d, { recursive: true, force: true });

// GREEN: an explicit deferral is allowed, repeatedly.
d = mkdtempSync(join(tmpdir(), 'debt-'));
for (const t of ['turn-1', 'turn-2', 'turn-3', 'turn-4']) fire(RECORD, DEFER, d, t);
arm('green-explicit-deferral-never-blocks', true, 'four deferred turns recorded without a block');
rmSync(d, { recursive: true, force: true });

// GREEN: no admission means silence, and the ledger stays empty.
d = mkdtempSync(join(tmpdir(), 'debt-'));
const rc = fire(RECORD, CLEAN, d, 'turn-clean');
arm('green-no-admission-is-silent', rc.reason === null && rc.rc === 0, `rc=${rc.rc}`);
arm('green-empty-ledger-stays-empty', !existsSync(join(d, 'self-audit-debt.jsonl')) || readFileSync(join(d, 'self-audit-debt.jsonl'), 'utf8').trim() === '', 'no rows written');
rmSync(d, { recursive: true, force: true });

// GREEN -> resolution: admit, then stop admitting -> the debt is CLOSED, not merely forgotten.
d = mkdtempSync(join(tmpdir(), 'debt-'));
fire(RECORD, ADMIT, d, 'turn-1');
const beforeRows = readFileSync(join(d, 'self-audit-debt.jsonl'), 'utf8').trim().split('\n').length;
fire(RECORD, CLEAN, d, 'turn-2');
const after = readFileSync(join(d, 'self-audit-debt.jsonl'), 'utf8').trim().split('\n');
arm('resolution-is-recorded-as-closed', after.some((l) => JSON.parse(l).state === 'resolved'), `rows before=${beforeRows} after=${after.length}`);
const inj = inject(d);
arm('inject-is-silent-when-nothing-open', inj.out.trim() === '', `out=${JSON.stringify(inj.out.slice(0, 60))}`);
rmSync(d, { recursive: true, force: true });

// GREEN: debt is surfaced at the start of the next session.
d = mkdtempSync(join(tmpdir(), 'debt-'));
fire(RECORD, ADMIT, d, 'turn-1');
const inj2 = inject(d, 'SessionStart');
arm('inject-surfaces-open-debt', inj2.out.includes('claim-falsifier') && inj2.out.includes('SessionStart'), inj2.out.slice(0, 90));
rmSync(d, { recursive: true, force: true });

// GREEN: a missing ledger must never wedge a session start.
d = mkdtempSync(join(tmpdir(), 'debt-'));
const inj3 = inject(d, 'SessionStart');
arm('inject-survives-absent-ledger', inj3.rc === 0 && inj3.out.trim() === '', `rc=${inj3.rc}`);
rmSync(d, { recursive: true, force: true });

process.stdout.write(`SELFTEST ${failed === 0 ? 'PASS' : 'FAIL'} failures=${failed}\n`);
process.exit(failed === 0 ? 0 : 1);