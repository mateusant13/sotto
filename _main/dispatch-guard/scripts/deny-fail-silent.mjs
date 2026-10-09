#!/usr/bin/env node
// deny-fail-silent.mjs - PreToolUse hook on write / edit.
//
// WHY THIS EXISTS, MEASURED
// 2026-10-06, this agent wrote six instances of `except OSError: pass` / `except ValueError:
// continue` across four new files. They went unnoticed for roughly 40 minutes. Nothing complained.
// The only thing that caught them was the pre-commit T-BUG static analysis, at the moment of
// landing - one CRITICAL (T-BUG-05) and four HIGH (T-BUG-02). Every one of them was in code
// written tonight, including inside gate-verdict.py, the tool whose entire purpose is to catch a
// gate lying about its own verdict.
//
// That is the failure this hook removes: a defect that is only found at commit time has a forty
// minute window in which it is invisible, and forty minutes is exactly how long it takes to write
// the next four.
//
// WHY PREToolUse AND NOT POSTToolUse
// The MiniMax hook contract gives PostToolUse `additionalContext` only - "tool-result replacement
// is unsupported" - so it can inform but never block. PreToolUse can return
// `permissionDecision: "deny"`, which happens BEFORE the file exists. A guard that fires after
// the write has to be read, remembered and undone; a guard that fires before has nothing to undo.
//
// THE TRIGGER IS NARROW ON PURPOSE
// It fires on exactly one shape: an exception handler whose body swallows the error and carries
// on. That is T-BUG-02 and T-BUG-05 - a bare `pass`, a bare `continue`, or a `return` inside an
// `except` - and nothing else. A hook that fires on ordinary code gets switched off, and this one
// only earns its place if it is silent on real work.
//
// rc contract: 0 allow silently, 1 deny with a reason, 2 never (never crash into a verdict).
import { readFileSync } from 'node:fs';

function readPayload() {
  try {
    const raw = readFileSync(0, 'utf8');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

// COVERAGE IS python and javascript. That is the whole claim, and the selftest pins it.
//
// Two defects were found in this file by its own selftest, both mine, both of the same shape - a
// fix that asserted the shape without proving the code path still ran:
//
//   1. The first version used ONE regex that required the line to END immediately after `except`,
//      so it matched `except:` and missed `except OSError:` - the overwhelmingly common form. All
//      six RED arms passed, which is the worst possible failure mode: a guard that never fires
//      still looks green when you only read the exit code.
//   2. The repair split that regex into two FUNCTIONS but left the call site as
//      `HANDLER_START.test(...)`. A function has no `.test`, so every write containing the word
//      `except` raised an uncaught TypeError and exited rc=1 with no stdout - the hook silently
//      stopped deciding anything. The selftest reported "rc=1, got=false" on every RED arm and that
//      was the only clue. Fixing a guard by editing its regexes is not evidence the guard runs.
//
// Rust is NOT covered: `Err(_) => continue` is a match arm, not a handler head, and pretending
// otherwise is exactly the untested claim this selftest exists to kill. The `rescue` keyword is
// absent from every regex below for that reason. If Rust coverage is wanted later it needs its own
// arm and its own measurement, not a word added to this comment.
function isHandlerStart(raw) {
  const t = raw.trim();
  if (/^except\b[^:]*:\s*$/.test(t)) return true;       // python, with a spec
  if (/^except\s*:\s*$/.test(t)) return true;           // python, bare
  if (/^}\s*catch\b/.test(t)) return true;              // js, catch after a closing brace
  if (/^catch\s*[({]/.test(t)) return true;             // js, catch on its own line
  if (/^catch\s*$/.test(t)) return true;                // js, `catch` then `{`
  return false;
}
function isOneLineSwallow(raw) {
  const t = raw.trim();
  return /^except\b[^:]*:\s*(pass|continue)\s*(#|\/\/|;)?\s*$/.test(t);
}
const SWALLOW = /^(pass|continue|\.{3})\s*;?\s*$/;
const SWALLOW_WITH_COMMENT = /^(pass|continue)\s*;?\s*(#|\/\/)/;
const RETURN = /^return\s*;?\s*$/;

/**
 * Find handlers whose entire body is one of {pass, continue, ..., bare return}, or which swallow
 * and immediately continue. Walks forward from the handler and stops at the first statement that
 * is not the swallow, so a handler with real work after the pass is not accused.
 *
 * The one-line shape is tested FIRST and independently. It used to sit behind `if
 * (!isHandlerStart(line)) continue`, which meant `except: pass` - the single most common spelling
 * of this defect - was skipped by the guard that exists to catch it. Order is load-bearing here.
 */
function findSwallows(text) {
  const lines = text.split(/\r?\n/);
  const hits = [];
  for (let i = 0; i < lines.length; i += 1) {
    if (isOneLineSwallow(lines[i])) {
      hits.push({ line: i + 1, text: lines[i].trim(), body: 'pass/continue, same line' });
      continue;
    }
    if (!isHandlerStart(lines[i])) continue;
    // The body of a handler is what follows until dedent below the handler's own indent.
    const handlerIndent = lines[i].match(/^\s*/)[0].length;
    for (let j = i + 1; j < lines.length; j += 1) {
      const line = lines[j];
      const body = line.trim();
      if (body === '') continue;
      const indent = line.match(/^\s*/)[0].length;
      if (indent <= handlerIndent) break; // dedented out of the handler
      // Test the TRIMMED body. Testing `line` against these anchors never matched anything,
      // because a handler body is always indented - which is why every multi-line RED arm was
      // green before it. Depth is compared on the raw line, matched on the trimmed one.
      if (SWALLOW.test(body) || SWALLOW_WITH_COMMENT.test(body) || RETURN.test(body)) {
        hits.push({ line: j + 1, text: lines[i].trim(), body });
        break;
      }
      break; // a real statement first means this handler does real work
    }
  }
  return hits;
}

const payload = readPayload();
const input = payload.tool_input ?? payload.toolInput ?? {};
const name = String(payload.tool_name ?? payload.toolName ?? '');
const path = String(input.path ?? input.file_path ?? input.filePath ?? '<unknown>');

// Only gate the tools that create or change file content.
if (!/^(write|edit|create|update|notebookedit)$/i.test(name)) process.exit(0);

const content = input.content ?? input.new_string ?? input.newString ?? '';
if (typeof content !== 'string' || content.length === 0) process.exit(0);

// Cheap gate first: most writes are prose, markdown, JSON. `rescue` is deliberately absent - see
// the coverage claim above; this hook does not read Rust.
if (!/\b(except|catch)\b/.test(content)) process.exit(0);

const hits = findSwallows(content);
if (hits.length === 0) process.exit(0);

const listing = hits
  .slice(0, 6)
  .map((h) => `  ${path}:${h.line}  ${h.text}  ->  ${h.body}`)
  .join('\n');
const more = hits.length > 6 ? `\n  ... and ${hits.length - 6} more` : '';

process.stdout.write(
  JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason:
        `This write would create ${hits.length} exception handler(s) that swallow the error and carry on: ` +
        `${listing}${more}\n\n` +
        'That is T-BUG-02 / T-BUG-05, and it is how a failure becomes invisible: the handler runs, ' +
        'the error is discarded, and the program reports a result as if nothing happened.\n\n' +
        'Make the swallow LOUD instead of deleting it. Choose one:\n' +
        '  - print a diagnostic to stderr and keep the degraded path (probes that must not die);\n' +
        '  - record the failure in a counter the caller can assert on;\n' +
        '  - re-raise, if the failure genuinely invalidates the result.\n\n' +
        'If this really is a deliberate best-effort path, that is allowed - but say so in a comment ' +
        'on the SAME line stating what is lost when the error fires, so the next reader can audit it.',
    },
  }),
);
process.exit(1);