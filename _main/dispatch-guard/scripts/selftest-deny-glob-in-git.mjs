// selftest-deny-glob-in-git.mjs - a deny hook that cannot deny is a no-op.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const TARGET = join(here, 'deny-glob-in-git.mjs');

function fire(command) {
  const r = spawnSync(process.execPath, [TARGET], {
    input: JSON.stringify({ hook_event_name: 'PreToolUse', tool_input: { command } }),
    encoding: 'utf8',
  });
  let denied = false;
  if (r.stdout && r.stdout.trim()) {
    try { denied = JSON.parse(r.stdout).hookSpecificOutput?.permissionDecision === 'deny'; } catch { denied = null; }
  }
  return { denied, rc: r.status };
}

const arms = [
  // RED: index-writing git with a wildcard.
  ['red-git-add-glob', 'git add state/*.md', true],
  ['red-git-commit-glob', 'git commit -m x -- scripts/*.sh', true],
  ['red-git-add-question-mark', 'git add scripts/guard-?.sh', true],
  ['red-git-add-charclass', 'git add scripts/[ab].sh', true],
  ['red-git-rm-glob', 'git rm --cached runs/*.md', true],
  ['red-git-reset-glob', 'git reset HEAD state/*.json', true],
  // GREEN: index-writing git with explicit paths.
  ['green-git-add-explicit', 'git add scripts/commit-owned.sh', false],
  ['green-git-commit-explicit', 'git commit -m fix -- scripts/a.sh scripts/b.sh', false],
  // GREEN: read-only git is never affected, even with a wildcard.
  ['green-git-status-glob', 'git status -- scripts/*.sh', false],
  ['green-git-log-glob', 'git log --oneline -- state/*.md', false],
  ['green-git-diff-glob', 'git diff --stat -- scripts/*.sh', false],
  ['green-git-ls-files-glob', 'git ls-files "theory-2026-10-*.md"', false],
  // GREEN: wildcards outside index-writing git are not this hook's business.
  ['green-ls-glob', 'ls -la scripts/*.sh', false],
  ['green-grep-glob', 'grep -r "jev" state/*', false],
  // GREEN: compound commands are out of scope by design, not by accident.
  ['green-compound-out-of-scope', 'git add a.sh && echo done', false],
];

let failed = 0;
for (const [name, cmd, want] of arms) {
  const res = fire(cmd);
  const ok = res.denied === want;
  if (!ok) failed += 1;
  process.stdout.write(`${ok ? 'ok  ' : 'FAIL'} ${name} :: want_denied=${want} got=${res.denied} rc=${res.rc} :: ${cmd}\n`);
}
process.stdout.write(`SELFTEST ${failed === 0 ? 'PASS' : 'FAIL'} arms=${arms.length} failures=${failed}\n`);
process.exit(failed === 0 ? 0 : 1);