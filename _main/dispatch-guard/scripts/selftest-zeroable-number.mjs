// selftest-zeroable-number.mjs - proves check-zeroable-number.mjs can go GREEN and RED.
// A guard that cannot refuse is not a guard. Every arm is fired through the REAL script,
// as a child process, with a REAL stdin payload. Nothing is imported or mocked.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const TARGET = join(here, 'check-zeroable-number.mjs');

/** Fire the real hook with a JSON payload built from `message` plus `extra`. */
function fire(message, extra = {}) {
  return fireRaw(JSON.stringify({ hook_event_name: 'Stop', last_assistant_message: message, ...extra }));
}

/** Fire the real hook with a byte-for-byte stdin payload (for the malformed arm). */
function fireRaw(raw) {
  const r = spawnSync(process.execPath, [TARGET], { input: raw, encoding: 'utf8' });
  let reason = null;
  if (r.stdout && r.stdout.trim()) {
    try {
      reason = JSON.parse(r.stdout).reason ?? null;
    } catch {
      reason = 'UNPARSEABLE';
    }
  }
  return { rc: r.status, blocked: reason !== null, reason, stdout: r.stdout || '', stderr: (r.stderr || '').slice(-200) };
}

const arms = [
  // GREEN arms - the guard must stay silent. A guard that always fires gets disabled.
  ['green-peak-level-and-duration',
    'The audio device is detected; peak level -3.2 dBFS sustained for 120 s.', false],
  ['green-fraction-of-arms',
    'All 9/9 arms pass and the plugin is recognised by the loader.', false],
  ['green-bytes-files-and-zero-errors',
    'The extractor works: 1,204 bytes read, 3 files processed, 0 errors.', false],
  ['green-percentage-and-duration',
    'The census is green: 100% of the enumerated set resolved in 12.4 s.', false],
  ['green-negative-claim-is-not-accused',
    'Nothing is green. The device is not detected and the extractor does not work.', false],
  ['green-decoration-plus-one-real-measurement',
    'On 2026-10-06 at 02:15:36, hooks.json:42 recorded peak 0.98 for the device.', false],
  ['green-empty-message', '', false],
  ['green-no-success-claim-at-all',
    'I have not finished the census. The next step is the extractor wiring.', false],
  ['green-population-binding-is-a-measurement',
    'POPULATION 386 guards, WINDOW 2026-10-06. Everything is green and works.', false],
  ['green-stop-hook-active-one-shot-guard',
    'The plugin is recognised and all arms pass.', false, { stop_hook_active: true }],

  // RED arms - a success claim with nothing that could have been zero.
  ['red-device-detected-no-quantity',
    'The audio device is detected on port 3. Everything is wired and the extractor works.', true],
  ['red-all-arms-pass-no-count',
    'All arms pass. The plugin is recognised and the report binding is green.', true],
  ['red-healthy-with-no-quantity',
    'The census is healthy and the extractor works end to end.', true],
  ['red-only-decorative-numbers',
    'On 2026-10-06 at 02:15:36 the plugin v1.2.3 was recognised; see hooks.json:42 and rules 5 and 7. Everything is green.', true],
  ['red-verified-with-no-measurement',
    'The fallback chain is verified and the lane completes. Healthy.', true],
  ['red-only-a-year',
    'In 2026 the extractor works and the device is detected.', true],

  // ROBUSTNESS arms - an internal error must never become a verdict.
  ['robust-malformed-stdin', null, false, null, 'not json at all {'],
  ['robust-empty-stdin', null, false, null, ''],
  ['robust-type-confused-field', null, false, null, '{"hook_event_name":"Stop","last_assistant_message":42}'],
  ['robust-oversized-message-windowed',
    `${'The extractor works and the plugin is recognised. '.repeat(3000)}` +
      'Closing with no measurement at all.', true],
];

let failed = 0;
let red = 0;
let green = 0;

for (const [name, msg, wantBlocked, extra, rawOverride] of arms) {
  const res = rawOverride === undefined ? fire(msg, extra ?? {}) : fireRaw(rawOverride);
  const ok = res.blocked === wantBlocked && (wantBlocked ? res.rc === 1 : res.rc === 0);
  if (!ok) failed += 1;
  if (wantBlocked) red += 1;
  else green += 1;
  process.stdout.write(
    `${ok ? 'ok  ' : 'FAIL'} ${name} :: want_blocked=${wantBlocked} got=${res.blocked} rc=${res.rc}` +
      `${res.reason ? ` :: ${res.reason.slice(0, 80).replace(/\n/g, ' ')}` : ''}\n`,
  );
  if (res.stderr) process.stdout.write(`     stderr: ${res.stderr}\n`);
}

process.stdout.write(`SELFTEST ${failed === 0 ? 'PASS' : 'FAIL'} arms=${arms.length} failures=${failed} red_arms=${red} green_arms=${green}\n`);
process.exit(failed === 0 ? 0 : 1);