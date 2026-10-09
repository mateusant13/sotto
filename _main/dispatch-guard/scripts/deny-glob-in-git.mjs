#!/usr/bin/env node
// deny-glob-in-git.mjs - PreToolUse hook on Bash.
//
// THE DAMAGE, MEASURED. Twice, in one session, an unexpanded shell glob in a git invocation
// expanded far past the intended file and staged another lane's work:
//   "the commit began staging all of them before I killed it - 720 staged against a 313 baseline"
//   "my `theory-2026-10-*.md` glob became 388 files"
// POPULATION 2 incidents, WINDOW 2026-09-28. Both times the fix was written as a to-do ("Ban
// glob-expanded paths in commit invocations") and never built. A to-do is not a guard.
//
// WHY PreToolUse. PostToolUse cannot help: the MiniMax contract gives it `additionalContext` only
// ("tool-result replacement is unsupported"), so by the time it fires the index is already
// contaminated. PreToolUse can `deny`, and denial happens BEFORE the process starts. This is the
// only seam where the damage is still preventable.
//
// SCOPE, DELIBERATELY NARROW. It denies only when a SINGLE bash command contains BOTH a git
// index-mutating subcommand AND an unexpanded wildcard. It does not touch `git status`,
// `git log`, `git show`, `git diff`, or any read-only command, and it does not object to `*` in
// ordinary non-git commands. A guard that fires on ordinary work is a guard that gets disabled.
//
// rc contract: 0 allow silently, 1 deny with a reason, 2 never.
import { readFileSync } from 'node:fs';

// Commands that WRITE the shared index. Read-only git is left alone on purpose.
const INDEX_WRITING = /\bgit\s+(?:add|commit|rm|rm\s+--cached|mv|restore|checkout|reset|update-index)\b/;
// Wildcards that the shell would expand. The first version required a whitespace, quote or equals
// sign immediately before the wildcard, which MISSED the commonest case of all: `state/*.md`,
// where a slash precedes it. The selftest arms `red-git-add-glob` and `red-git-add-question-mark`
// are exactly that miss. A wildcard is a wildcard wherever it sits in a path.
const WILDCARD = /(^|[^\\])[*?]|\[[^\]]*\]/;

function readPayload() {
  try {
    const raw = readFileSync(0, 'utf8');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

const payload = readPayload();
const input = payload.tool_input ?? payload.toolInput ?? {};
const command = String(input.command ?? input.cmd ?? '');

// Only a single command. A compound `a && b` is out of scope on purpose: at that point the rule
// is guesswork about which half did the damage, and a wrong deny costs more than a missed one.
if (/(&&|\|\||;|\n)/.test(command)) process.exit(0);
if (!/\bgit\b/.test(command)) process.exit(0);
if (!INDEX_WRITING.test(command)) process.exit(0);
if (!WILDCARD.test(command)) process.exit(0);

process.stdout.write(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason:
        'This git command contains an unexpanded wildcard in a path, and it WRITES the index.\n\n' +
        'Measured twice in one session: an unexpanded glob staged 720 paths against a 313 baseline, ' +
        'and another became 388 files. Both contaminated another lane\'s staged work before the ' +
        'command could be killed.\n\n' +
        'Name every path explicitly, or expand it yourself first and pass the resulting paths. ' +
        'If you genuinely want a pattern, list the matches with `git ls-files "<pattern>"`, read ' +
        'the list, and pass those paths one by one.\n\n' +
        'Read-only git commands are not affected by this rule.',
    },
  }),
);
process.exit(1);