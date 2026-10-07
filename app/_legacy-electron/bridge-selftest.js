'use strict';

/**
 * Sotto — the bridge self-test.
 *
 * Proves the whole bridge path end to end WITHOUT a model, a worker lane, or a
 * microphone: a throwaway Python child process is asked to print a canned JSONL
 * sequence on STDOUT, and the test asserts that each line came back out the
 * other end of the real pipe — spawn, line-split, JSON.parse, receiver.
 *
 * Why a real child and not a fake stream: a stubbed `stdout` would test this
 * file's parser against itself. The failure that matters is a worker that
 * flushes in chunks, or dies mid-line, or prints a traceback — none of which a
 * stub can reproduce. So the canned lines are deliberately hostile:
 *
 *   - one line is not JSON at all (a Python traceback on STDOUT),
 *   - the child exits non-zero, to exercise restart-with-backoff,
 *   - the child writes each line with an explicit flush, because a buffered
 *     writer that "emits JSONL" but flushes at exit would prove nothing.
 *
 * The same harness runs two ways:
 *   - `node bridge-selftest.js`          — sink is a local collector (fast)
 *   - `electron . --bridge-selftest`    — sink is the panel: every caption and
 *     status goes through IPC -> preload -> DOM -> ack, and an extra step
 *     asserts the MAIN PROCESS's caption log really contains each line. That
 *     is the only run that proves the DOM, not just the parser.
 *
 * Exit code is a real one: 0 all steps observed, 3 at least one did not.
 */

const { createBridge, CANNED_JSONL, DEFAULT_AUDIO_DEVICE, DEFAULT_CAPTURE_MODE } =
  require('./worker-bridge');

/** The self-test's own step table, so a failure names itself. */
function steps() {
  const out = [];
  return {
    push(name, ok, detail) {
      out.push({ name, ok: Boolean(ok), detail: detail == null ? '' : String(detail) });
      return out[out.length - 1];
    },
    all: () => out,
  };
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Poll a predicate until it holds or the ceiling fires — a real ceiling, not a hope. */
async function waitFor(predicate, ceilingMs, stepMs = 25) {
  const deadline = Date.now() + ceilingMs;
  for (;;) {
    let hit = false;
    try { hit = predicate(); } catch { hit = false; }
    if (hit) return true;
    if (Date.now() >= deadline) return false;
    await sleep(stepMs);
  }
}

/**
 * The fake worker, as Python source. The canned JSONL travels as an argv item,
 * never through a shell: `spawn` passes argv directly, so there is no
 * PowerShell quoting layer that could rewrite a quote inside a caption and make
 * a parser bug look like a pass.
 *
 * `python -c <script> mode data` puts `sys.argv = ['-c', mode, data]`, and the
 * bridge appends `workerPath` as the last argv item — which lands at
 * `sys.argv[3]` and is ignored here.
 *
 *   mode 'canned'  print every data line, flush each, exit 0
 *   mode 'crash'   print data, flush, exit 3 — to prove restart
 *
 * `import json` is deliberately absent: the bridge must forward a line it was
 * never taught, and printing it verbatim is the honest way to do that.
 */
const FAKE_WORKER_PY = [
  'import sys',
  'mode = sys.argv[1] if len(sys.argv) > 1 else "canned"',
  'data = sys.argv[2] if len(sys.argv) > 2 else ""',
  'out = sys.stdout',
  'if mode == "crash":',
  '    out.write(data + "\\n")',
  '    out.flush()',
  '    sys.exit(3)',
  'for line in data.splitlines():',
  '    if line == "":',
  '        continue',
  '    out.write(line + "\\n")',
  '    out.flush()',
  'sys.exit(0)',
].join('\n');

/** The canned sequence, as one newline-joined blob for argv. */
const CANNED_DATA = CANNED_JSONL.join('\n');

/** The last canned status: the `idle` state, i.e. capture not started. */
const IDLE_STATUS = 'Capture not started - the worker has not opened the audio device';

/**
 * A worker path that does not exist, in a directory that does not exist.
 * Deliberately outside H:\\sotto\\worker: this lane does not write there.
 */
const MISSING_WORKER = 'H:\\sotto\\_bridge-selftest-absent\\no_such_worker.py';

/**
 * @param {object} [opts]
 * @param {(text:string, meta:object)=>void} [opts.onCaption] panel sink
 * @param {(text:string, kind:string, info:object)=>void} [opts.onStatus] panel sink
 * @param {boolean} [opts.isPanel]  true under Electron: add the IPC-ack step
 * @param {()=>string[]} [opts.acked] main process's caption log, for that step
 * @param {(line:string)=>void} [opts.log]
 * @returns {Promise<{rc:number, steps:Array}>}
 */
async function runBridgeSelfTest(opts = {}) {
  const step = steps();
  const log = typeof opts.log === 'function' ? opts.log : () => {};
  const isPanel = Boolean(opts.isPanel);
  const onCaption =
    typeof opts.onCaption === 'function' ? opts.onCaption : () => {};
  const onStatus =
    typeof opts.onStatus === 'function' ? opts.onStatus : () => {};

  // --- the receiver under test --------------------------------------------
  // Local collector ALWAYS runs, even under Electron. The panel sink is a
  // second observer of the same stream, not a replacement for it: the
  // collector is what proves the bridge parsed correctly, and the panel is
  // what proves it reached a human.
  const captions = [];
  const statuses = [];
  const ackedLines = [];
  const sink = (text, meta) => {
    captions.push(String(text));
    ackedLines.push(meta);
    onCaption(text, meta);
  };
  const statusSink = (text, kind, info) => {
    statuses.push({ text: String(text), kind, info: info || {} });
    onStatus(text, kind, info);
  };

  // --- 1. the canned JSONL sequence --------------------------------------
  const bridge = createBridge({
    command: 'python',
    // `python -u` so the child's writes are flushed line by line; a buffered
    // writer that only flushes at exit would prove nothing about the reader.
    args: ['-u', '-c', FAKE_WORKER_PY, 'canned', CANNED_DATA],
    workerPath: FAKE_WORKER_PY,
    requireExists: false, // a `-c` script is not a file; see WorkerBridge
    log,
    backoff: { base: 120, factor: 2, max: 400 },
    silenceMs: 4000,
    onCaption: sink,
    onStatus: statusSink,
  });

  const expectedCaptions = [
    'hello from the worker',
    'second caption line',
    'third line after the malformed one',
  ];

  log(`SELFTEST contract device=${JSON.stringify(DEFAULT_AUDIO_DEVICE)} capture=${DEFAULT_CAPTURE_MODE}`);
  log(`SELFTEST lines=${CANNED_JSONL.length}`);
  for (const line of CANNED_JSONL) log(`SELFTEST canned ${line}`);

  bridge.start('bridge-selftest');
  await sleep(0);

  // The `idle` status is the LAST canned line, so seeing it means all three
  // captions have already been parsed. Stopping on that is deterministic —
  // waiting for the exit instead would let the backoff restart re-emit the
  // whole sequence and double the caption count.
  const sawAll = await waitFor(
    () =>
      captions.length >= expectedCaptions.length &&
      statuses.some((s) => s.text === IDLE_STATUS),
    10000,
  );

  const gotCaptions = captions.map((t) => t);
  const captionsOk =
    sawAll &&
    expectedCaptions.every((want, i) => gotCaptions[i] === want);
  step.push(
    'canned-jsonl-captions',
    captionsOk,
    `want=${JSON.stringify(expectedCaptions)} got=${JSON.stringify(gotCaptions)}`,
  );

  // 1b. the status lines the worker reported, in order, rendered for a human.
  const statusTexts = statuses.map((s) => s.text);
  const wantsModelLoading = statusTexts.some((t) => t === 'Model loading...');
  const wantsListening = statusTexts.some((t) => t.startsWith('Listening - '));
  const wantsIdle = statusTexts.some((t) => t === IDLE_STATUS);
  const statusesOk = wantsModelLoading && wantsListening && wantsIdle;
  step.push(
    'canned-jsonl-statuses',
    statusesOk,
    `model-loading=${wantsModelLoading} listening=${wantsListening} idle=${wantsIdle} all=${JSON.stringify(statusTexts)}`,
  );

  // 1c. the non-JSON line was counted and skipped, and the caption AFTER it
  //     still landed. A traceback on STDOUT must not end the stream.
  const malformedOk = bridge.malformed === 1 && gotCaptions[2] === expectedCaptions[2];
  step.push('malformed-line-survived', malformedOk, `malformed=${bridge.malformed} after=${JSON.stringify(gotCaptions[2])}`);

  // 1d. no status was ever empty. panel.js drops empty statuses, so one would
  //     silently leave the stale "Waiting for audio" on screen — the exact bug.
  const noEmpty = statuses.length > 0 && statuses.every((s) => s.text.trim() !== '');
  step.push('no-empty-status', noEmpty, `statuses=${statuses.length}`);

  // 1e. the falsification guard: on this host audio IS present (system tap
  //     peak=0.883270), so no status may claim otherwise.
  const neverFalse = statuses.every(
    (s) => !/wait(?:ing)?\s+for\s+audio|\bno\s+audio\b/i.test(s.text),
  );
  step.push('no-false-waiting-for-audio', neverFalse, JSON.stringify(statusTexts));

  bridge.stop('selftest-done');
  await sleep(150);

  // --- 2. restart after a crash ------------------------------------------
  const crashCaptions = [];
  const crashStatuses = [];
  const crash = createBridge({
    command: 'python',
    args: [
      '-u', '-c', FAKE_WORKER_PY, 'crash',
      '{"type":"caption","text":"boot caption","start":0,"end":1}',
    ],
    workerPath: FAKE_WORKER_PY,
    requireExists: false,
    log,
    backoff: { base: 120, factor: 2, max: 400 },
    silenceMs: 4000,
    onCaption: (text) => crashCaptions.push(String(text)),
    onStatus: (text, kind, info) =>
      crashStatuses.push({ text: String(text), kind, info: info || {} }),
  });

  crash.start('crash-selftest');
  // Two boots must happen: the first crashes, the backoff restarts it, and the
  // second boot's caption lands too. One boot would prove nothing about restart.
  const restarted = await waitFor(() => crash.restarts >= 1 && crashCaptions.length >= 2, 8000);
  const diedStatus = crashStatuses.some((s) => /Worker died/.test(s.text));
  const backoffSeen = crashStatuses.some((s) => /restart \d+ in [\d.]+s/.test(s.text));
  crash.stop('crash-selftest-done');
  await sleep(100);
  const crashOk = restarted && diedStatus && backoffSeen;
  step.push(
    'restart-after-crash',
    crashOk,
    `restarts=${crash.restarts} captions=${crashCaptions.length} died=${diedStatus} backoff=${backoffSeen}`,
  );

  // --- 3. the worker that does not exist ----------------------------------
  // This is the owner's bug: a panel that says "Waiting for audio" when the
  // real problem is that there is no worker. The status must name the worker.
  const missingStatuses = [];
  const missing = createBridge({
    command: 'python',
    args: ['-u'],
    workerPath: MISSING_WORKER,
    log,
    backoff: { base: 120, factor: 2, max: 400 },
    silenceMs: 4000,
    onCaption: () => {},
    onStatus: (text, kind, info) =>
      missingStatuses.push({ text: String(text), kind, info: info || {} }),
  });
  missing.start('missing-selftest');
  await sleep(400);
  const lastMissing = missingStatuses[missingStatuses.length - 1] || { text: '', info: {} };
  const namesWorker = /Worker not found/i.test(missingStatuses.map((s) => s.text).join(' | '));
  const namesPath = missingStatuses.some((s) => s.text.includes(MISSING_WORKER));
  const notWaiting = !/wait(?:ing)?\s+for\s+audio/i.test(lastMissing.text);
  const placeholderFalsy =
    lastMissing.info.title === 'Worker not found' ||
    /not found/i.test(String(lastMissing.info.title || ''));
  missing.stop('missing-selftest-done');
  await sleep(100);
  const missingOk = namesWorker && namesPath && notWaiting && placeholderFalsy;
  step.push(
    'missing-worker-status',
    missingOk,
    `names-worker=${namesWorker} names-path=${namesPath} not-waiting=${notWaiting} last=${JSON.stringify(lastMissing.text)} placeholder=${JSON.stringify(lastMissing.info.title)}`,
  );

  // --- 4. the panel ack (Electron only) -----------------------------------
  if (isPanel && typeof opts.acked === 'function') {
    const acked = opts.acked();
    const allAcked = expectedCaptions.every((want) => acked.includes(want));
    step.push(
      'ipc-ack-captions-applied',
      allAcked,
      `acked=${JSON.stringify(acked)}`,
    );
  }

  const all = step.all();
  const failed = all.filter((s) => !s.ok);
  return { rc: failed.length === 0 ? 0 : 3, steps: all };
}

/** Print the receipt. The PASS/FAIL line names every step, per the brief. */
function printResult(result, prefix = 'BRIDGE_SELFTEST') {
  const names = result.steps.map((s) => `${s.name}=${s.ok ? 'ok' : 'FAIL'}`).join(' ');
  for (const s of result.steps) {
    console.log(
      `sotto: ${prefix}_STEP ${s.name}=${s.ok ? 'ok' : 'FAIL'}` +
        (s.detail ? ` detail=${s.detail}` : ''),
    );
  }
  console.log(
    `sotto: ${prefix}_RESULT ${result.rc === 0 ? 'PASS' : 'FAIL'} steps=${result.steps.length}`,
  );
  console.log(
    `${prefix} ${result.rc === 0 ? 'PASS' : 'FAIL'} ` +
      `steps=${result.steps.map((s) => s.name).join(',')} rc=${result.rc}`,
  );
  return result.rc;
}

module.exports = { runBridgeSelfTest, printResult, FAKE_WORKER_PY, MISSING_WORKER };

// Self-execute only when run directly by node (`node bridge-selftest.js`). Under
// Electron, main.js imports this module and calls runBridgeSelfTest itself so
// the app can exit with the returned rc.
if (typeof require !== 'undefined' && require.main === module) {
  runBridgeSelfTest({ log: (line) => console.log(`sotto: ${line}`) })
    .then((result) => {
      const rc = printResult(result);
      process.exit(rc);
    })
    .catch((err) => {
      console.error(`sotto: BRIDGE_SELFTEST threw: ${err && err.stack ? err.stack : err}`);
      process.exit(3);
    });
}