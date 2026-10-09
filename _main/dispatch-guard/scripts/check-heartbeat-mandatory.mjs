#!/usr/bin/env node
// check-heartbeat-mandatory.mjs -- the self-audit's own gate-melhor, turned mechanical.
//
// SA-9bb4c8398d5d9bc1, raised in the agent's own SELF-AUDIT on 2026-10-06 and carried
// over by selfaudit-dispatch-inject.mjs:
//   "o batimento devia ser OBRIGATORIO num dispatcher -- sem ele, uma excepcao e
//    indistinguivel de um hook morto."
//
// MEASURED WHY IT IS NOT OPTIONAL. The p0-ratchet hook and the self-audit injector were
// both fully built, both fully green in their own selftests, both NAMED in hooks.json,
// and both BOUND to UserPromptSubmit. They never fired once. The reason was one line in
// hook-dispatch.mjs: the manager's own session was on the exemption list, so the
// dispatcher skipped every handler and emitted nothing. The agent reported "it is
// wired" three separate times over several hours. A heartbeat line per invocation,
// written BEFORE the exemption check, is the only thing that distinguishes
// "wired but exempt" from "wired and running" -- so it is required, not decorative.
//
// WHAT THIS CHECKS, mechanically:
//   1. every dispatcher in this plugin tree appends to a heartbeat file
//   2. it writes it BEFORE any early exit that skips a handler
//   3. it records the decision (SKIP or RUN), not merely that it woke up
//
// rc 0 every dispatcher heartbeats | 1 a real violation | 2 nothing to check
import { readFileSync, readdirSync, statSync, existsSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

const HERE = dirname(new URL(import.meta.url).pathname.replace(/^\//, '').replace(/^(.)/, (c) => c.toUpperCase()));
const GUARD_ROOT = join(HERE, '..');

let pass = 0, fail = 0;
function arm(name, ok, detail) {
  if (ok) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name}${detail ? '  -- ' + detail : ''}`); }
}

// Find every file that LOOKS like an exemption dispatcher: it decides whether to skip a
// handler before running it. Pattern is behavioural, not a hard-coded filename, so a
// second dispatcher added later is covered too.
function findDispatchers(dir, out = []) {
  let entries;
  try { entries = readdirSync(dir); } catch { return out; }
  for (const e of entries) {
    const p = join(dir, e);
    let st;
    try { st = statSync(p); } catch { continue; }
    if (st.isDirectory()) { findDispatchers(p, out); continue; }
    if (!/\.(mjs|js|cjs)$/.test(e)) continue;
    let s;
    try { s = readFileSync(p, 'utf8'); } catch { continue; }
    // A dispatcher is not "something that mentions exempt". It is a file that
    // RECEIVES a handler path as an argument and decides whether to execute it.
    // MEASURED 2026-10-06: the first version of this gate matched three unrelated
    // files (run-gates.mjs, two selftests) purely because they mentioned "exempt"
    // and used spawnSync -- a gate with false positives trains the reader to ignore it,
    // which is the defect it was written to prevent.
    const receivesTarget = /process\.argv\s*\[\s*2\s*\]/.test(s);
    const hasExemptList = /(exemptSessions|ALWAYS_RUN|FALLBACK_EXEMPT)/.test(s);
    if (!receivesTarget || !hasExemptList) continue;

    out.push({ path: p, src: s });
  }
  return out;
}

console.log('check-heartbeat-mandatory: every dispatcher must heartbeat before skipping');

const dispatchers = findDispatchers(GUARD_ROOT);
arm('at least one dispatcher was found', dispatchers.length > 0,
  `population=${dispatchers.length}`);

let violations = 0;
for (const d of dispatchers) {
  const name = d.path.replace(/^.*[\\/]/, '');
  const writes = /appendFileSync|writeFileSync/.test(d.src);
  const logs = /heartbeat/i.test(d.src);
  const decides = /SKIP|RUN/.test(d.src);

  arm(`${name}: writes a heartbeat file`, writes && logs);
  arm(`${name}: records the SKIP/RUN decision, not just liveness`, decides);

  // The ORDER matters and is the whole point: a heartbeat written after the skip
  // early-exit is blind to exactly the case it exists to catch.
  const hbIdx = d.src.search(/appendFileSync|heartbeat/i);
  const skipIdx = d.src.search(/process\.exit\(0\)[^\n]*\/\/\s*exempt|if \(_isExempt/);
  if (hbIdx >= 0 && skipIdx >= 0) {
    const before = hbIdx < skipIdx;
    arm(`${name}: heartbeats BEFORE the skip decision`, before,
      before ? '' : `heartbeat@${hbIdx} skip@${skipIdx}`);
  } else if (skipIdx >= 0) {
    violations++;
  }

  // READING SOURCE IS NOT RUNNING IT.
  // MEASURED 2026-10-06: with only the text checks above, this gate reported
  // "4 passed, 0 failed" for a dispatcher that did not even PARSE -- `node --check` on
  // the mutated file returned rc=1 SyntaxError. A gate that greps source can be
  // satisfied by text in a file the runtime can never load. A green you cannot turn red
  // is not green, and this one was green on a broken artefact.
  const parses = spawnSync(process.execPath, ['--check', d.path], { encoding: 'utf8' });
  arm(`${name}: the dispatcher actually PARSES`, parses.status === 0,
    parses.status === 0 ? '' : `node --check rc=${parses.status}: ${(parses.stderr || '').slice(0, 120)}`);

  // And RUNS: invoke it for real against a probe handler in an exempt session and
  // assert a heartbeat line appeared. This arm cannot be faked by source text.
  const tmp = mkdtempSync(join(tmpdir(), 'hb-'));
  // The dispatcher names its own file `hook-dispatch-heartbeat.log`. MEASURED 2026-10-06:
  // this arm first looked for `hb.log`, so it failed even on a healthy dispatcher --
  // and a gate that fails when the thing is FINE is a gate that gets switched off.
  const log = join(tmp, 'hook-dispatch-heartbeat.log');
  const probe = join(tmp, 'probe.mjs');
  writeFileSync(probe, 'process.stdout.write("PROBE_RAN");\n');
  try {
    spawnSync(process.execPath, [d.path, probe], {
      input: JSON.stringify({ session_id: 'mvs_ea552229fe164f9e8856fcca8589c41a' }),
      encoding: 'utf8',
      env: { ...process.env, MINIMAX_HOME: tmp },
      timeout: 20000,
    });
    const content = existsSync(log) ? readFileSync(log, 'utf8') : '';
    arm(`${name}: a real invocation leaves a heartbeat line`, content.trim().length > 0,
      existsSync(log) ? 'log exists but is empty' : `no heartbeat file at ${log}`);
    arm(`${name}: the heartbeat records a SKIP or RUN decision`,
      /action=(SKIP|RUN)/.test(content), content.trim().slice(0, 120));
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);