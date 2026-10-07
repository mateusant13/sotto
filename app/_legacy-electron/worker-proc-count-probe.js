'use strict';

/**
 * Sotto — the process-COUNT probe for the single-worker claim.
 *
 * The self-test (`bridge-single-instance-selftest.js`) counts processes from
 * inside the test process, using the pids the workers report themselves. This
 * probe answers the same question from OUTSIDE, the way the owner would: it asks
 * Windows which `python.exe` processes have `worker_probe.py` — this probe's own
 * worker script — in their command line.
 *
 * Why a separate instrument: a count taken from inside the process that owns the
 * bridge is a self-report, and the whole defect was a bridge that believed
 * something its caller did not. The filter is the WORKER SCRIPT PATH, never the
 * image name: `python.exe` on this box also runs probes belonging to other
 * lanes, and killing one of those because it was called `python` is exactly the
 * mistake this probe exists to avoid.
 *
 * Why it SAMPLES instead of taking two snapshots. A first version counted twice
 * and printed `0` and `0`: both moments landed between a worker dying and the
 * next one starting, which is true and proves nothing about the peak. The claim
 * is about the MAXIMUM number of workers that ever existed at once, so the
 * sampler runs continuously (one PowerShell, sampling every 100 ms) and the
 * verdict is the maximum over each window.
 *
 * Two windows are reported, both from the same series:
 *   BEFORE  the first backoff window — from the moment the restart timer is
 *           armed to the longest backoff this bridge could wait (1600 ms). This
 *           is the window the defect lived in.
 *   AFTER   everything past that window, where a superseded or surviving timer
 *           would have produced its extra worker by now.
 *
 * Run by hand:
 *   node worker-proc-count-probe.js
 * Exit 0 when both maxima are <= 1, 3 otherwise.
 */

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

const { createBridge } = require('./worker-bridge');

const ART_DIR = path.join(__dirname, '_single-instance');
const PROBE_WORKER = path.join(ART_DIR, 'worker_probe.py');
const PIDFILE = path.join(ART_DIR, 'proc-count.pid');

/** Longest backoff this probe's bridge can arm — the width of the BEFORE
 *  window. Kept next to the bridge options below so the two cannot drift. */
const BACKOFF_MAX = 1600;

const PROBE_WORKER_PY = [
  '"""Throwaway worker for the process-count probe. Writes its own pid, then',
  'dies immediately so the bridge arms a restart."""',
  'import os, sys, time',
  'with open(sys.argv[1], "a") as handle:',
  '    handle.write(str(os.getpid()) + "\\n")',
  'print(\'{"type":"status","state":"listening"}\', flush=True)',
  'time.sleep(float(sys.argv[2]))',
  'sys.exit(9)',
  '',
].join('\n');

/**
 * How long each probe worker stays alive before it dies.
 *
 * A worker that exits instantly is a poor instrument here: one WMI sample costs
 * ~250 ms on this box, so a 70 ms worker is invisible to the sampler and the
 * AFTER window reads "max 0" — true, and saying nothing about the peak. 350 ms
 * puts every worker squarely inside at least one sample, so a run that kept two
 * workers alive cannot hide between samples.
 */
const WORKER_HOLD_S = 0.35;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * One PowerShell, sampling for `durationMs`, printing `<epoch ms>,<count>` every
 * 100 ms. Started once and left running: a per-sample PowerShell costs ~1.5 s,
 * which is longer than the whole defect window, so sampling by process restart
 * would step straight over the thing being measured.
 */
function startSampler(durationMs) {
  const script = [
    `$deadline = (Get-Date).AddMilliseconds(${durationMs})`,
    'while ((Get-Date) -lt $deadline) {',
    '  $c = 0',
    '  Get-CimInstance Win32_Process -Filter "Name = \'python.exe\'" |',
    '    Where-Object { $_.CommandLine -like "*worker_probe.py*" } |',
    '    ForEach-Object { $c = $c + 1 }',
    '  Write-Output ("{0},{1}" -f [DateTimeOffset]::Now.ToUnixTimeMilliseconds(), $c)',
    '  Start-Sleep -Milliseconds 100',
    '}',
  ].join('\n');
  const child = spawn('powershell', ['-NoProfile', '-NonInteractive', '-Command', script], {
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'ignore'],
  });
  const samples = [];
  let buf = '';
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', (chunk) => {
    buf += chunk;
    let nl = buf.indexOf('\n');
    while (nl !== -1) {
      const [ts, count] = buf.slice(0, nl).split(',');
      buf = buf.slice(nl + 1);
      const at = Number(ts);
      if (Number.isInteger(at) && Number.isFinite(Number(count))) {
        samples.push({ at, count: Number(count) });
      }
      nl = buf.indexOf('\n');
    }
  });
  return { child, samples, done: new Promise((r) => child.on('close', r)) };
}

/** Pids this probe's workers reported. The only pids it will ever signal. */
function ourPids() {
  try {
    return fs.readFileSync(PIDFILE, 'utf8')
      .split(/\r?\n/)
      .map((l) => Number(l.trim()))
      .filter((n) => Number.isInteger(n) && n > 0);
  } catch {
    return [];
  }
}

/** Max and sample count over a time window of the series. */
function over(samples, fromMs, toMs) {
  const inWindow = samples.filter((s) => s.at >= fromMs && s.at < toMs);
  return {
    max: inWindow.reduce((m, s) => Math.max(m, s.count), 0),
    samples: inWindow.length,
  };
}

async function main() {
  fs.mkdirSync(ART_DIR, { recursive: true });
  fs.writeFileSync(PROBE_WORKER, PROBE_WORKER_PY);
  try { fs.unlinkSync(PIDFILE); } catch { /* first run */ }

  console.log(`sotto: PROCCOUNT worker_script=${PROBE_WORKER}`);
  console.log(`sotto: PROCCOUNT filter = python.exe whose CommandLine contains "worker_probe.py"`);

  // Sampler first: it has to be watching before the first worker exists, or the
  // peak would be measured from the second spawn onwards.
  const sampler = startSampler(14000);
  await sleep(1500); // let the first WMI sample land before anything is spawned

  const bridge = createBridge({
    command: 'python',
    args: ['-u', PROBE_WORKER, PIDFILE, String(WORKER_HOLD_S)],
    workerPath: PROBE_WORKER,
    requireExists: true, // this one IS a real file
    log: (line) => console.log(`sotto: ${line}`),
    silenceMs: 60000,
    backoff: { base: 400, factor: 2, max: BACKOFF_MAX },
  });

  const t0 = Date.now();
  bridge.start('probe-1');
  while (!bridge.hasPendingRestart) await sleep(5); // first death processed
  const armedAt = Date.now();
  console.log(
    `sotto: PROCCOUNT window armed at t+${armedAt - t0}ms: liveChildCount=${bridge.liveChildCount} isActive=${bridge.isActive} pendingRestart=${bridge.hasPendingRestart}`,
  );

  // Alt+C, pressed hard, from inside the window — the owner's exact gesture.
  let accepted = 0;
  for (let i = 2; i <= 21; i += 1) {
    if (bridge.start(`probe-${i}`)) accepted += 1;
    await sleep(5);
  }
  console.log(`sotto: PROCCOUNT startsAcceptedInsideWindow=${accepted} of 20`);

  await sleep(9000);
  const spawns = bridge.spawns;
  const restarts = bridge.restarts;
  bridge.stop('probe-done');
  const stoppedAt = Date.now();

  await sampler.done;

  // Strictly BEFORE the first spawn (t0). A first version measured this up to
  // `armedAt`, which INCLUDES the first worker — it printed "baseline 1" next
  // to a claim of "before anything was spawned", which is the kind of number
  // that makes a receipt lie without anybody editing it.
  const baseline = over(sampler.samples, t0 - 60000, t0);
  const beforeWindow = over(sampler.samples, armedAt, armedAt + BACKOFF_MAX);
  const afterWindow = over(sampler.samples, armedAt + BACKOFF_MAX, stoppedAt);
  const afterStop = over(sampler.samples, stoppedAt, Number.MAX_SAFE_INTEGER);

  console.log(
    `sotto: PROCCOUNT BEFORE the backoff window  = max ${beforeWindow.max} over ${beforeWindow.samples} samples (t+${armedAt - t0}ms .. t+${armedAt - t0 + BACKOFF_MAX}ms)`,
  );
  console.log(
    `sotto: PROCCOUNT AFTER the backoff window   = max ${afterWindow.max} over ${afterWindow.samples} samples (t+${armedAt - t0 + BACKOFF_MAX}ms .. t+${stoppedAt - t0}ms)`,
  );
  console.log(
    `sotto: PROCCOUNT AFTER stop()               = max ${afterStop.max} over ${afterStop.samples} samples | maxBeforeFirstSpawn=${baseline.max} (${baseline.samples} samples) bridgeSpawns=${spawns} restarts=${restarts}`,
  );
  const series = sampler.samples
    .filter((s) => s.at >= t0 - 200)
    .map((s) => `${s.at - t0}:${s.count}`)
    .join(' ');
  console.log(`sotto: PROCCOUNT_SERIES ms:count ${series}`);

  let killed = 0;
  for (const pid of ourPids()) {
    try { process.kill(pid, 0); process.kill(pid); killed += 1; } catch { /* already gone */ }
  }
  console.log(`sotto: PROCCOUNT cleanup killedOurOwnPids=${killed}`);

  const ok = beforeWindow.max <= 1 && afterWindow.max <= 1 && afterStop.max === 0;
  console.log(
    `sotto: PROCCOUNT_RESULT ${ok ? 'PASS' : 'FAIL'} baselineMax=${baseline.max} beforeMax=${beforeWindow.max} afterMax=${afterWindow.max} afterStopMax=${afterStop.max} rc=${ok ? 0 : 3}`,
  );
  process.exit(ok ? 0 : 3);
}

main().catch((err) => {
  console.error(`sotto: PROCCOUNT threw: ${err && err.stack ? err.stack : err}`);
  process.exit(3);
});