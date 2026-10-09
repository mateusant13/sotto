// selftest-memo-wake.mjs - three arms, and each one must be able to FAIL.
//
//   A1 owner-yes      the owner session receives the wake
//   A2 subagent-no    a subagent session receives NOTHING (the "subagents never run memo" rule)
//   A3 ceiling-red    an oversized store is TRUNCATED at the published ceiling, and the check that
//                     would catch the absence of truncation is itself proven to be able to fail
//
// The store is a fixture written here, byte for byte in the layout `memo` defines: LOG.txt records
// are 320 bytes, TREE/<size> records are 288, and position IS identity. A fixture in the wrong
// layout would make every arm pass for the wrong reason, so arm A1 asserts on real content, not on
// "something was printed".
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';

const here = dirname(fileURLToPath(import.meta.url));
const TARGET = join(here, 'memo-wake.mjs');

const LOG_REC = 320;
const TREE_REC = 288;
const MAX_CTX = 8192; // must equal the constant in memo-wake.mjs

/** One LOG record, padded to the fixed width the tool defines. */
function logRec(id, date, text) {
  const s = `#${id} ${date} ${text}`;
  if (Buffer.byteLength(s, 'utf8') > LOG_REC) throw new Error(`record too wide: ${s}`);
  return s.padEnd(LOG_REC, ' ');
}

/** One TREE record, padded to the fixed width the tool defines. */
function treeRec(text) {
  const s = text;
  if (Buffer.byteLength(s, 'utf8') > TREE_REC) throw new Error(`summary too wide: ${s}`);
  return s.padEnd(TREE_REC, ' ');
}

/**
 * Build a store. When `summarizeTo` is given, every TREE/<size> up to it is pre-compressed, so the
 * wake renders whole blocks instead of reporting pending naps.
 */
function buildStore(dir, { memories, bigText = null, summarizeTo = 2 }) {
  mkdirSync(join(dir, 'TREE'), { recursive: true });
  let log = '';
  for (let i = 0; i < memories; i++) {
    log += logRec(i, '2026-10-06', bigText ? bigText(i) : `memory number ${i} about the fleet`);
  }
  writeFileSync(join(dir, 'LOG.txt'), log, 'latin1');
  for (let size = 2; size <= summarizeTo; size *= 2) {
    const blocks = Math.ceil(memories / size);
    let tree = '';
    for (let k = 0; k < blocks; k++) {
      tree += treeRec(`summary of ${k * size}-${Math.min((k + 1) * size, memories) - 1}`);
    }
    writeFileSync(join(dir, 'TREE', String(size)), tree, 'latin1');
  }
}

function fire(payload, storeDir) {
  const r = spawnSync(process.execPath, [TARGET], {
    input: JSON.stringify(payload),
    encoding: 'utf8',
    env: { ...process.env, MEMORY_DIR: storeDir, PLUGIN_DATA_OVERRIDE: join(storeDir, '_data') },
  });
  let ctx = null;
  if (r.stdout && r.stdout.trim()) {
    try {
      ctx = JSON.parse(r.stdout).hookSpecificOutput?.additionalContext ?? null;
    } catch {
      ctx = 'UNPARSEABLE';
    }
  }
  return { ctx, raw: r.stdout || '', rc: r.status };
}

const arms = [];
function arm(name, want, got, detail) {
  const ok = want === got;
  arms.push(ok);
  process.stdout.write(`${ok ? 'ok  ' : 'FAIL'} ${name} :: want=${want} got=${got} :: ${detail}\n`);
}

const scratch = mkdtempSync(join(tmpdir(), 'memo-wake-'));
try {
  // ---------------------------------------------------------------- A1 owner-yes
  {
    const d = join(scratch, 'owner');
    buildStore(d, { memories: 6, summarizeTo: 2 });
    const res = fire({ hook_event_name: 'SessionStart', session_id: 'mvs_owner', source: 'startup' }, d);
    const isStr = typeof res.ctx === 'string' && res.ctx.length > 0;
    arm('A1-owner-receives-wake', true, isStr, `rc=${res.rc} ctx_chars=${typeof res.ctx === 'string' ? res.ctx.length : 'null'}`);
    // Not "it printed something": the wake must carry REAL content from the fixture store.
    const carriesContent = isStr && res.ctx.includes('memory number') && res.ctx.includes('6 memories');
    arm('A1b-wake-carries-store-content', true, carriesContent, 'fixture memories present with population');
    arm('A1c-owner-rc-zero', 0, res.rc, 'a session start is never wedged');
  }

  // ---------------------------------------------------------------- A2 subagent-no
  {
    const d = join(scratch, 'subagent');
    buildStore(d, { memories: 6, summarizeTo: 2 });
    // Arm 2a: the runtime's own discriminator - a session with a parentSessionId is source "fork".
    const fork = fire({ hook_event_name: 'SessionStart', session_id: 'mvs_child', source: 'fork' }, d);
    arm('A2a-fork-session-silent', '', fork.raw, `rc=${fork.rc} raw=${JSON.stringify(fork.raw.slice(0, 40))}`);
    // Arm 2b: the subagent dispatch path also injects agent_id/agent_type.
    const withAgent = fire(
      { hook_event_name: 'SessionStart', session_id: 'mvs_child', source: 'startup', agent_id: 'a1', agent_type: 'worker' },
      d,
    );
    arm('A2b-subagent-payload-silent', '', withAgent.raw, `rc=${withAgent.rc} raw=${JSON.stringify(withAgent.raw.slice(0, 40))}`);
    // Arm 2c: the store HAS content, so silence is the guard working and not an empty store.
    const owner = fire({ hook_event_name: 'SessionStart', session_id: 'mvs_owner', source: 'startup' }, d);
    arm('A2c-same-store-wakes-owner', true, typeof owner.ctx === 'string' && owner.ctx.length > 0, 'the guard discriminates, it does not disable');
  }

  // ---------------------------------------------------------------- A3 ceiling-red
  {
    const d = join(scratch, 'oversized');
    // 400 memories whose summaries are wide, so the document cannot fit under the ceiling.
    buildStore(d, {
      memories: 400,
      summarizeTo: 512,
      bigText: (i) => `memory ${i} ` + 'detail '.repeat(38).trim(),
    });
    const res = fire({ hook_event_name: 'SessionStart', session_id: 'mvs_owner', source: 'startup' }, d);
    const len = typeof res.ctx === 'string' ? res.ctx.length : -1;
    arm('A3a-ceiling-fires', true, len > 0 && len <= MAX_CTX, `chars=${len} ceiling=${MAX_CTX}`);
    const marked = typeof res.ctx === 'string' && res.ctx.includes('[TRUNCATED');
    arm('A3b-truncation-is-declared', true, marked, 'a bounded read must say it is bounded');

    // THE MUTATION. An assertion that cannot go RED is not evidence. Remove the ceiling clamp and
    // the very same arms must FAIL; that is what proves A3a is testing the ceiling and not the
    // store happening to be small.
    const src = readFileSync(TARGET, 'utf8');
    const mutated = src
      .replace('const MAX_CTX = 8192;', 'const MAX_CTX = 1e9;')
      .replace(/if \(text\.length > MAX_CTX\) \{/, 'if (false) {');
    if (mutated === src) {
      arm('A3c-mutation-applies', true, false, 'MUTATION DID NOT APPLY - the clamp is not where the ceiling comes from');
    } else {
      const mPath = join(scratch, 'memo-wake-mutated.mjs');
      writeFileSync(mPath, mutated, 'utf8');
      // The mutant imports ./ledger.mjs relative to itself, so the module graph has to travel with
      // it. Without this the mutant dies on a missing import and A3c goes red for the wrong reason -
      // which is exactly the failure this arm exists to avoid.
      writeFileSync(join(scratch, 'ledger.mjs'), readFileSync(join(here, 'ledger.mjs'), 'utf8'), 'utf8');
      const r2 = spawnSync(process.execPath, [mPath], {
        input: JSON.stringify({ hook_event_name: 'SessionStart', session_id: 'mvs_owner', source: 'startup' }),
        encoding: 'utf8',
        env: { ...process.env, MEMORY_DIR: d, PLUGIN_DATA_OVERRIDE: join(d, '_data') },
      });
      let mutatedLen = -1;
      try {
        mutatedLen = JSON.parse(r2.stdout).hookSpecificOutput?.additionalContext?.length ?? -1;
      } catch {
        mutatedLen = -1;
      }
      // The mutant must EXCEED the ceiling: that is the RED the ceiling prevents.
      arm('A3c-mutation-goes-red', true, mutatedLen > MAX_CTX, `mutant_chars=${mutatedLen} vs ceiling=${MAX_CTX}`);
    }
  }

  // ---------------------------------------------------------------- A4 fail-open
  {
    const missing = join(scratch, 'does-not-exist');
    const res = fire({ hook_event_name: 'SessionStart', session_id: 'mvs_owner', source: 'startup' }, missing);
    arm('A4-missing-store-fails-open', 0, res.rc, 'no store is not a wedged session');
    const res2 = fire({ hook_event_name: 'SessionStart', session_id: 'mvs_owner', source: 'startup' }, '');
    arm('A4b-empty-memdir-fails-open', 0, res2.rc, 'an unusable MEMORY_DIR is not a wedged session');
  }

  // ------------------------------------------------------- A5 fidelity vs the real tool
  // The port re-implements `memo wake`, so agreeing with itself proves nothing. This arm runs the
  // ACTUAL tool against the SAME store and diffs the memory lines.
  //
  // It is here because it caught a real divergence on 2026-10-06 that every other arm passed:
  // `memo`'s budget-refinement loop splits the LAST splittable block (`max(...)`, nearest T), and
  // the port originally split the first. Both emitted 96 lines, so a count-only assertion was
  // green on a wrong answer. Populations above 96 are the only ones that reach that loop, which is
  // why the fixture is deliberately over WAKE_LINES.
  {
    const MEMO = join(homedir(), '.optmem', 'memo');
    const havePython = spawnSync('python', ['--version'], { encoding: 'utf8' }).error === undefined;
    if (!existsSync(MEMO) || !havePython) {
      process.stdout.write(
        `SKIP A5-differential-vs-memo :: python=${havePython} memo_present=${existsSync(MEMO)} (SKIPPED, not passed)\n`,
      );
    } else {
      for (const pop of [97, 300, 1000]) {
        const d = join(scratch, `fidelity-${pop}`);
        buildStore(d, { memories: pop, summarizeTo: 4096, bigText: (i) => `memory ${i} about topic ${i % 17}` });
        let truth = '';
        let truthErr = null;
        try {
          truth = spawnSync('python', [MEMO, 'wake'], { encoding: 'utf8', env: { ...process.env, MEMORY_DIR: d } }).stdout || '';
        } catch (e) {
          truthErr = String(e);
        }
        const port = fire({ hook_event_name: 'SessionStart', session_id: 'mvs_diff', source: 'startup' }, d);
        const lines = (s) =>
          String(s)
            .split(/\r?\n/)
            .filter((l) => /^#\d/.test(l.trim()));
        const a = lines(truth);
        const b = lines(typeof port.ctx === 'string' ? port.ctx : '');
        const same = !truthErr && a.length === b.length && a.every((l, i) => l === b[i]);
        arm(
          `A5-differential-vs-memo-T${pop}`,
          true,
          same,
          truthErr ? `tool failed: ${truthErr}` : `truth_lines=${a.length} port_lines=${b.length}${same ? ' identical' : ' DIVERGED'}`,
        );
      }
    }
  }
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

const failed = arms.filter((a) => !a).length;
process.stdout.write(`SELFTEST ${failed === 0 ? 'PASS' : 'FAIL'} arms=${arms.length} failures=${failed}\n`);
process.stdout.write('ceiling: MAX_CTX=8192 chars (of the 65536 runner cap) - published, and A3c proves it binds.\n');
process.exit(failed === 0 ? 0 : 1);