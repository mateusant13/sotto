// selftest-report-binding.mjs - proves check-report-binding.mjs can go GREEN and RED.
// A guard that cannot refuse is not a guard. Every arm below is fired through the REAL script,
// as a child process, with a REAL stdin payload. Nothing is imported or mocked.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const TARGET = join(here, 'check-report-binding.mjs');

function fire(message) {
  const r = spawnSync(process.execPath, [TARGET], {
    input: JSON.stringify({ hook_event_name: 'Stop', last_assistant_message: message }),
    encoding: 'utf8',
  });
  let reason = null;
  if (r.stdout && r.stdout.trim()) {
    try {
      reason = JSON.parse(r.stdout).reason ?? null;
    } catch {
      reason = 'UNPARSEABLE';
    }
  }
  return { rc: r.status, blocked: reason !== null, reason, stderr: (r.stderr || '').slice(-200) };
}

const GOOD = `## SELF-AUDIT
POPULATION 386 guards, WINDOW 2026-10-06 02:15:36. P0: 94 reachable.
Everything is green and the check works.
Does your implementation meet the spec? YES - measured on both states.`;

const arms = [
  // GREEN arms - the guard must stay silent.
  ['green-full-compliance', GOOD, false],
  ['green-no-success-claim-is-not-accused',
    '## SELF-AUDIT\nI did not finish the census. The number is unknown.\nI will go back to it.', false],
  ['green-empty-message', '', false],
  ['green-quotes-the-rule-about-population',
    '## SELF-AUDIT\nPOPULATION is a free parameter here, so I am NOT publishing the number yet.', false],

  // RED arms - each names exactly one missing thing.
  ['red-no-self-audit',
    'POPULATION 386, WINDOW 2026-10-06 02:15. P0 done. All checks pass.\n' +
    'Does your implementation meet the spec? YES - done.', true],
  ['red-success-without-population',
    '## SELF-AUDIT\nWINDOW 2026-10-06 02:15. P0 in three. The fix works and all checks pass.', true],
  ['red-success-without-window',
    '## SELF-AUDIT\nPOPULATION 386. P0 in three. GREEN across the board.', true],
  ['red-success-without-p0',
    '## SELF-AUDIT\nPOPULATION 386, WINDOW 2026-10-06 02:15. Everything is green.', true],
  ['red-bare-green-no-evidence-at-all',
    '## SELF-AUDIT\nGREEN. All arms pass.', true],
];

let failed = 0;
for (const [name, msg, wantBlocked] of arms) {
  const res = fire(msg);
  const ok = res.blocked === wantBlocked;
  if (!ok) failed += 1;
  process.stdout.write(
    `${ok ? 'ok  ' : 'FAIL'} ${name} :: want_blocked=${wantBlocked} got=${res.blocked} rc=${res.rc}` +
      `${res.reason ? ` :: ${res.reason.slice(0, 90).replace(/\n/g, ' ')}` : ''}\n`,
  );
  if (res.stderr) process.stdout.write(`     stderr: ${res.stderr}\n`);
}

process.stdout.write(`SELFTEST ${failed === 0 ? 'PASS' : 'FAIL'} arms=${arms.length} failures=${failed}\n`);
process.exit(failed === 0 ? 0 : 1);