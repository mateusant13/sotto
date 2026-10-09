// selftest-deny-fail-silent.mjs - a guard that cannot refuse is off by default.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const TARGET = join(here, 'deny-fail-silent.mjs');

function fire(tool, content, path = 'x.py') {
  const r = spawnSync(process.execPath, [TARGET], {
    input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_name: tool, tool_input: { path, content } }),
    encoding: 'utf8',
  });
  let denied = false;
  let reason = null;
  if (r.stdout && r.stdout.trim()) {
    try {
      const d = JSON.parse(r.stdout).hookSpecificOutput ?? {};
      denied = d.permissionDecision === 'deny';
      reason = d.permissionDecisionReason ?? null;
    } catch { denied = null; }
  }
  return { denied, reason, rc: r.status };
}

const arms = [
  // RED: the exact shapes the pre-commit gate found tonight, at real line numbers.
  ['red-except-oserror-pass', 'write',
   'def f():\n    try:\n        open(p)\n    except OSError:\n        pass\n', 'probes/guard-reachability.py', true],
  ['red-except-valueerror-continue', 'write',
   'for ln in rows:\n    try:\n        row = json.loads(ln)\n    except ValueError:\n        continue\n', 'scripts/gate-verdict.py', true],
  ['red-one-line-except-pass', 'write',
   'try:\n    x = 1\nexcept: pass\n', 'probes/pain-guard-gap.py', true],
  ['red-js-catch-brace', 'edit',
   'try {\n  readFileSync(p);\n} catch {\n  pass;\n}\n', 'server/x.mjs', true],
  // LIMIT ARM, not a RED arm. The guard declares python+javascript coverage and this pins that
  // claim so nobody later assumes Rust is covered. Before this was written the header said
  // "python and javascript only" while the regex still matched `rescue` - two false statements at
  // once, one of them mine.
  ['green-rust-NOT-covered-by-declared-limit', 'write',
   'fn f() {\n    match r {\n        Err(_) => continue,\n    }\n}\n', 'x.rs', false],
  ['red-three-in-one-write', 'write',
   'a\ntry:\n    pass\nexcept A:\n    pass\nb\ntry:\n    pass\nexcept B:\n    continue\nc\n', 'multi.py', true],

  // GREEN: the handler must do real work, or fail loudly. These are the REPLACES.
  ['green-handler-writes-a-diagnostic', 'write',
   'try:\n    open(p)\nexcept OSError as e:\n    print(f"could not read: {e}", file=sys.stderr)\n', 'x.py', false],
  ['green-handler-raises', 'write',
   'try:\n    int(s)\nexcept ValueError:\n    raise\n', 'x.py', false],
  ['green-handler-returns-a-value', 'write',
   'def g():\n    try:\n        return 1\n    except Exception:\n        return None\n', 'x.py', false],
  ['green-no-exception-at-all', 'write',
   'def add(a, b):\n    return a + b\n', 'x.py', false],
  ['green-prose-mentions-except', 'write',
   'The handler will except on this, but this is a markdown file.\n', 'README.md', false],
  ['green-json-with-fail-key', 'write',
   '{"result": "fail", "note": "except never happened"}\n', 'x.json', false],
  ['green-pass-inside-a-loop-not-a-handler', 'write',
   'while True:\n    try:\n        step()\n    finally:\n        pass\n', 'x.py', false],

  // GREEN: the guard only applies to content-writing tools.
  ['green-not-a-write-tool', 'read', 'try:\n    x\nexcept:\n    pass\n', 'x.py', false],
];

let failed = 0;
for (const [name, tool, content, path, want] of arms) {
  const res = fire(tool, content, path);
  const ok = res.denied === want;
  if (!ok) failed += 1;
  process.stdout.write(`${ok ? 'ok  ' : 'FAIL'} ${name} :: want_denied=${want} got=${res.denied} rc=${res.rc}\n`);
}

// THE REAL FIXTURES: the six shapes actually found by the gate tonight.
const REAL = [
  ['probes/guard-reachability.py', 'try:\n    open(p)\nexcept OSError:\n    pass\n'],
  ['probes/pain-guard-gap.py', 'try:\n    json.loads(s)\nexcept OSError:\n    continue\n'],
  ['scripts/gate-verdict.py', 'try:\n    fh.write(s)\nexcept OSError:\n    pass\n'],
  ['scripts/gate-verdict.py', 'try:\n    json.loads(ln)\nexcept ValueError:\n    continue\n'],
  ['probes/jev-abstain-probe.py', 'try:\n    urllib.request.urlopen(req)\nexcept Exception as e:\n    pass\n'],
];
let realMissed = 0;
for (const [p, content] of REAL) {
  const res = fire('write', content, p);
  if (res.denied !== true) realMissed += 1;
  process.stdout.write(`real ${res.denied ? 'CAUGHT ' : 'MISSED '} ${p}\n`);
}
if (realMissed > 0) failed += 1;
process.stdout.write(`real-fixtures missed=${realMissed} of ${REAL.length}\n`);

process.stdout.write(`SELFTEST ${failed === 0 ? 'PASS' : 'FAIL'} arms=${arms.length} failures=${failed}\n`);
process.exit(failed === 0 ? 0 : 1);