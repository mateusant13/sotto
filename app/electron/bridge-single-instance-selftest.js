'use strict';

/**
 * Sotto — the SINGLE-INSTANCE self-test.
 *
 * The claim under test, in one sentence: ONE bridge never holds two live
 * workers, no matter how many times `start()` is called, and `stop()` leaves no
 * timer that can bring one back later.
 *
 * Why it needs its own file: `bridge-selftest.js` proves the bridge PARSES what
 * a worker says. This proves the bridge never AMBUSHES the operator with a
 * second ~2.1 GB python. The owner's report on 2026-10-06 was that Alt+C
 * spawned several unwanted processes, and the mechanism is not a parsing bug:
 * `start()` guarded on `this.child` while `#scheduleRestart()` armed
 * `this.timer`, so between a worker's death and the next spawn there was a
 * window where the child was null and the bridge was still armed. Every start()
 * inside that window was a second worker.
 *
 * What it measures, and why it is not the same as counting `bridge.spawns`:
 * `spawns` is a number the bridge reports about itself. The thing that hurt the
 * owner was PROCESSES ON THE MACHINE. So every worker here appends its own OS
 * pid to a file, and the test asks the OS whether each of those pids is alive.
 * The pass condition is on live processes, not on a counter.
 *
 * Two arms, because one of them is vacuous on its own:
 *   arm A `hold`  the worker stays up. `start()` x25. This is the case the old
 *                  child-only guard already handled, so it is the CONTROL.
 *   arm B `die`   the worker exits non-zero immediately, so the restart timer is
 *                  armed and `this.child` is null — the defect window. This arm
 *                  is the one that reproduces the report; arm A alone would pass
 *                  against the broken code too, which is exactly why it is
 *                  labelled a control and not called a proof.
 *
 * Run by hand:
 *   node bridge-single-instance-selftest.js
 * Exit code is a real one: 0 all steps observed, 3 at least one did not.
 *
 * `SOTTO_BRIDGE_MODULE=<path>` runs the same arms against a DIFFERENT bridge
 * module. That exists so the gate itself can be shown to go red: point it at a
 * pre-fix copy and watch the live-process steps fail.
 */

const fs = require('node:fs');
const path = require('node:path');

const BRIDGE_MODULE = process.env.SOTTO_BRIDGE_MODULE
  ? path.resolve(process.env.SOTTO_BRIDGE_MODULE)
  : path.join(__dirname, 'worker-bridge.js');
const { createBridge } = require(BRIDGE_MODULE);

/** The self-test's own step table, so a failure names itself. Same shape as
 *  bridge-selftest.js — one convention for this repo's receipts. */
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

/** Poll until the predicate holds or the ceiling fires — a real ceiling. */
async function waitFor(predicate, ceilingMs, stepMs = 10) {
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
 * The fake worker, as Python source. It appends its OWN pid to `pidfile` before
 * anything else, which is what makes "how many workers are alive" an OS
 * question rather than a self-report. Then:
 *
 *   mode 'hold'  one status, flush, sleep `seconds`, exit 0 — stays up
 *   mode 'die'   one status, flush, exit 7 — dies immediately, so the bridge's
 *                restart timer is armed while `child` is already null
 *
 * The bridge appends `workerPath` as the last argv item, which lands past the
 * args this reads; every index below is read defensively for that reason.
 */
const FAKE_WORKER_PY = [
  'import os, sys, time',
  'mode = sys.argv[1] if len(sys.argv) > 1 else "hold"',
  'pidfile = sys.argv[2] if len(sys.argv) > 2 else ""',
  'seconds = sys.argv[3] if len(sys.argv) > 3 else "20"',
  'if pidfile:',
  '    with open(pidfile, "a") as handle:',
  '        handle.write(str(os.getpid()) + "\\n")',
  'out = sys.stdout',
  'out.write(\'{"type":"status","state":"listening"}\\n\')',
  'out.flush()',
  'if mode == "die":',
  '    sys.exit(7)',
  'time.sleep(float(seconds))',
  'sys.exit(0)',
].join('\n');

/** Run artefacts live beside this file, inside the project. */
const ART_DIR = path.join(__dirname, '_single-instance');

/**
 * Is this pid still a process? `process.kill(pid, 0)` asks the OS without
 * signalling anything. EPERM means it exists and belongs to someone else, which
 * counts as alive — we never signal it either way.
 */
function isAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (err) {
    return err && err.code === 'EPERM';
  }
}

/** Every pid any worker of THIS arm has ever reported. */
function reportedPids(pidfile) {
  let text = '';
  try { text = fs.readFileSync(pidfile, 'utf8'); } catch { return []; }
  return text
    .split(/\r?\n/)
    .map((line) => Number(line.trim()))
    .filter((n) => Number.isInteger(n) && n > 0);
}

/** How many of THIS arm's workers are alive right now, per the OS. */
function liveCount(pidfile) {
  return reportedPids(pidfile).filter(isAlive).length;
}

/**
 * A continuous sampler. The pass condition is a MAXIMUM over time, not a
 * snapshot: a second worker that lived 40 ms and then died would still be the
 * bug the owner reported, and a snapshot taken after it died would call the run
 * clean. Every sample above 1 is kept with its pids so a failure names the
 * processes it actually saw.
 */
function sampler(pidfile, bridge, stepMs = 5) {
  const state = { maxLive: 0, maxBridgeChild: 0, samples: 0, over: [], stop: false };
  const loop = async () => {
    while (!state.stop) {
      const live = liveCount(pidfile);
      state.samples += 1;
      if (live > state.maxLive) state.maxLive = live;
      const own = typeof bridge.liveChildCount === 'number' ? bridge.liveChildCount : 0;
      if (own > state.maxBridgeChild) state.maxBridgeChild = own;
      if (live > 1) {
        state.over.push({
          at: Date.now(),
          live,
          pids: reportedPids(pidfile).filter(isAlive),
        });
      }
      await sleep(stepMs);
    }
  };
  return {
    state,
    run: loop,
    end() { state.stop = true; },
  };
}

/** Kill only the pids THIS run's workers reported. Never by name. */
function cleanupOurPids(pidfiles) {
  let killed = 0;
  for (const file of pidfiles) {
    for (const pid of reportedPids(file)) {
      if (!isAlive(pid)) continue;
      try { process.kill(pid); killed += 1; } catch { /* gone between check and kill */ }
    }
  }
  return killed;
}

async function main() {
  const log = (line) => console.log(`sotto: ${line}`);
  const step = steps();
  fs.mkdirSync(ART_DIR, { recursive: true });

  const pidA = path.join(ART_DIR, 'arm-hold.pid');
  const pidB = path.join(ART_DIR, 'arm-die.pid');
  for (const f of [pidA, pidB]) {
    try { fs.unlinkSync(f); } catch { /* first run */ }
  }

  log(`SINGLEINSTANCE module=${BRIDGE_MODULE}`);
  log(`SINGLEINSTANCE worker_pid_files=${pidA} | ${pidB}`);

  // --- arm A (CONTROL): a worker that stays up --------------------------
  const hold = createBridge({
    command: 'python',
    args: ['-u', '-c', FAKE_WORKER_PY, 'hold', pidA, '20'],
    workerPath: FAKE_WORKER_PY,
    requireExists: false, // a `-c` script is not a file; see WorkerBridge
    log,
    // Long enough that the silence ceiling cannot fire during this arm: this
    // arm is about start() idempotency, not about the fail-fast path.
    silenceMs: 60000,
    backoff: { base: 250, factor: 2, max: 800 },
  });

  const samplerA = sampler(pidA, hold);
  const samplingA = samplerA.run();

  const firstStart = hold.start('alt+c-1');
  const startsA = [firstStart];
  for (let i = 2; i <= 25; i += 1) {
    startsA.push(hold.start(`alt+c-${i}`));
    await sleep(5);
  }
  const onlyOneAccepted = startsA.filter(Boolean).length === 1;
  await sleep(900); // let any timer that was wrongly armed have fired
  samplerA.end();
  await samplingA;

  step.push(
    'arm-hold-one-start-accepted',
    onlyOneAccepted && firstStart === true,
    `calls=${startsA.length} accepted=${startsA.filter(Boolean).length} spawns=${hold.spawns}`,
  );
  step.push(
    'arm-hold-live-processes-never-exceed-one',
    samplerA.state.maxLive <= 1 && samplerA.state.maxBridgeChild <= 1,
    `maxLive=${samplerA.state.maxLive} maxBridgeChild=${samplerA.state.maxBridgeChild} samples=${samplerA.state.samples} pidsSeen=${reportedPids(pidA).length}`,
  );
  step.push(
    'arm-hold-accessors-report-active',
    hold.liveChildCount === 1 && hold.isActive === true && hold.hasPendingRestart === false,
    `live=${hold.liveChildCount} isActive=${hold.isActive} pendingRestart=${hold.hasPendingRestart}`,
  );
  const spawnsBeforeStopA = hold.spawns;
  hold.stop('arm-hold-done');
  await sleep(200);
  step.push(
    'arm-hold-stop-kills-the-only-worker',
    hold.spawns === spawnsBeforeStopA && liveCount(pidA) === 0,
    `spawnsBefore=${spawnsBeforeStopA} spawnsAfter=${hold.spawns} liveAfterStop=${liveCount(pidA)}`,
  );

  // --- arm B (the defect): a worker that dies, so the timer is armed -----
  const die = createBridge({
    command: 'python',
    args: ['-u', '-c', FAKE_WORKER_PY, 'die', pidB, '0'],
    workerPath: FAKE_WORKER_PY,
    requireExists: false,
    log,
    silenceMs: 60000,
    backoff: { base: 250, factor: 2, max: 800 },
  });

  const samplerB = sampler(pidB, die);
  const samplingB = samplerB.run();

  die.start('alt+c-1');
  // Wait for the death to be processed. This is the defect window: `child` is
  // null and `timer` is armed. If the bridge cannot report that window, it
  // cannot be made idempotent by its caller either.
  const armed = await waitFor(() => die.hasPendingRestart === true, 5000, 5);
  const childAtWindow = die.liveChildCount;
  step.push(
    'arm-die-restart-timer-is-armed-while-child-is-null',
    armed && childAtWindow === 0 && die.isActive === true,
    `armed=${armed} liveChildCount=${childAtWindow} isActive=${die.isActive} pendingRestart=${die.hasPendingRestart}`,
  );

  // The hammer: Alt+C pressed hard, inside the window, exactly as an owner
  // pressing it several times would. On the pre-fix bridge each of these was a
  // fresh spawn, and the armed timer was a THIRD one nobody could see.
  const startsB = [];
  for (let i = 2; i <= 25; i += 1) {
    startsB.push(die.start(`alt+c-${i}`));
    await sleep(5);
  }
  step.push(
    'arm-die-start-refused-while-armed',
    startsB.every((r) => r === false),
    `calls=${startsB.length} accepted=${startsB.filter(Boolean).length} spawns=${die.spawns}`,
  );

  // Sit through several backoff windows. The bridge SHOULD keep bringing a
  // worker back — that is what it is for — so this window is where a surviving
  // timer fires alongside a live child.
  const restartsBeforeWindow = die.restarts;
  await sleep(2600);
  samplerB.end();
  await samplingB;
  step.push(
    'arm-die-live-processes-never-exceed-one',
    samplerB.state.maxLive <= 1 && samplerB.state.maxBridgeChild <= 1,
    `maxLive=${samplerB.state.maxLive} maxBridgeChild=${samplerB.state.maxBridgeChild} samples=${samplerB.state.samples} pidsSeen=${reportedPids(pidB).length} over=${JSON.stringify(samplerB.state.over)} restarts=${restartsBeforeWindow}->${die.restarts}`,
  );
  step.push(
    'arm-die-restart-still-happens',
    die.restarts > restartsBeforeWindow && die.spawns > 1,
    `restarts=${die.restarts} spawns=${die.spawns} (a bridge that stops restarting would pass the count above by doing nothing)`,
  );

  // --- stop() cancels EVERY timer ---------------------------------------
  const restartsAtStop = die.restarts;
  const spawnsAtStop = die.spawns;
  const liveAtStop = liveCount(pidB);
  die.stop('arm-die-done');
  const stillArmed = die.hasPendingRestart;
  // Past the longest backoff this bridge could ever arm (max 800 ms), with
  // room to spare. A cancelled restart that fires late shows up here as a new
  // spawn and a new pid line.
  await sleep(1500);
  const liveAfterStopWindow = liveCount(pidB);
  step.push(
    'stop-cancels-every-timer',
    stillArmed === false && die.spawns === spawnsAtStop && die.restarts === restartsAtStop && liveAfterStopWindow === 0,
    `armedAtStop=${liveAtStop > 0} stillArmed=${stillArmed} spawns ${spawnsAtStop}->${die.spawns} restarts ${restartsAtStop}->${die.restarts} live ${liveAtStop}->${liveAfterStopWindow} pidsSeen=${reportedPids(pidB).length}`,
  );

  const killed = cleanupOurPids([pidA, pidB]);
  log(`SINGLEINSTANCE cleanup killed_our_pids=${killed}`);

  const all = step.all();
  const failed = all.filter((s) => !s.ok);
  for (const s of all) {
    console.log(
      `sotto: SINGLEINSTANCE_STEP ${s.name}=${s.ok ? 'ok' : 'FAIL'}` +
        (s.detail ? ` detail=${s.detail}` : ''),
    );
  }
  console.log(
    `sotto: SINGLEINSTANCE_RESULT ${failed.length === 0 ? 'PASS' : 'FAIL'} steps=${all.length} rc=${failed.length === 0 ? 0 : 3}`,
  );
  console.log(
    `SINGLEINSTANCE ${failed.length === 0 ? 'PASS' : 'FAIL'} steps=${all.map((s) => `${s.name}=${s.ok ? 'ok' : 'FAIL'}`).join(' ')} rc=${failed.length === 0 ? 0 : 3}`,
  );
  process.exit(failed.length === 0 ? 0 : 3);
}

main().catch((err) => {
  console.error(`sotto: SINGLEINSTANCE threw: ${err && err.stack ? err.stack : err}`);
  process.exit(3);
});