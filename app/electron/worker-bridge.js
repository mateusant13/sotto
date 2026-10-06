'use strict';

/**
 * Sotto — the worker bridge.
 *
 * The panel shell (main.js) and the Python ASR worker are built by two
 * different milestones and neither one could see the other, which is why the
 * caption area said "Waiting for audio" forever: nothing was feeding it, and
 * nothing was able to say so. This module is the missing wire. It owns exactly
 * three responsibilities:
 *
 *   1. spawn the Python worker as a child process,
 *   2. read STDOUT line by line, parse each line as one JSON object, and hand
 *      captions to the caption receiver and `status` lines to the status line,
 *   3. survive the worker dying and restart it with exponential backoff.
 *
 * It does NOT know about Electron. `onCaption` / `onStatus` are injected, so
 * the same bridge is driven by the panel (main.js) and by the self-test
 * (bridge-selftest.js) with no second implementation to drift.
 *
 * ── the STDOUT contract ───────────────────────────────────────────────────
 * One JSON object per line, flushed, nothing else on STDOUT:
 *
 *   {"type":"caption","text":"...","start":<float>,"end":<float>,"model":"..."}
 *   {"type":"status","state":"..."}
 *
 * `start` / `end` are audio seconds relative to the capture and travel as
 * caption `meta`; the panel renders the wall clock, not them. `model` is the
 * model's identity at the time of the line. A `state` of unknown spelling is
 * humanised rather than dropped, because a dropped status is a status the
 * panel cannot distinguish from silence.
 *
 * Two rules the parser holds even when the worker misbehaves:
 *   - a line that is not JSON is counted and skipped. A warning printed to
 *     STDOUT (which is exactly what a Python traceback is) must not take the
 *     caption stream down with it;
 *   - the buffer is line-split, so a caption split across two reads — or a
 *     last line with no trailing newline — is still delivered whole.
 *
 * ── why the status line matters more than the captions ───────────────────
 * panel.js ignores an empty status (`setStatus` returns early on `!text`), so
 * an empty string from the worker would leave whatever was on screen — the
 * stale "Waiting for audio" — in place. Every status emitted here is therefore
 * non-empty by construction, and `bridge-selftest.js` asserts it.
 */

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

/** Where the worker lane is expected to land the entrypoint. */
const DEFAULT_WORKER_PATH = path.resolve(__dirname, '..', '..', 'worker', 'sotto_worker.py');

/** Python launcher. Overridable so a venv interpreter can be pinned later. */
const DEFAULT_COMMAND = 'python';

/**
 * The system-audio tap, measured on this host by opening a real stream and
 * reading amplitude — not by listing device names (probe/tap_probe.py):
 *
 *   "Mapeador de som da Microsoft - Input"  CAPTURED  peak=0.883270
 *   "VoiceMeeter Output (VB-Audio Vo...)"   CAPTURED  peak=1.000000  rms=0.205321
 *
 * System audio IS present on this machine. Anything that says "waiting for
 * audio" is making a claim about a capture that may not have started yet.
 *
 * THIS IS A HINT, NOT AN OVERRIDE. It was previously exported unconditionally
 * as `SOTTO_AUDIO_DEVICE`, which made the shell's guess outrank
 * `worker/config.json` — measured same minute, one arm read silence from the
 * configured device while the other produced 29 captions from the forced one,
 * and the name that actually carries audio flips with the owner's routing, so
 * neither name is stable enough to pin. The worker now resolves the tap at
 * runtime and rotates off any device that stays flat (sotto_worker.py
 * `device_candidates` / the rotation loop), which is the only thing that can
 * be right when the right answer changes between runs. Exported for callers
 * that want to name a device explicitly and for the self-test's contract line.
 */
const DEFAULT_AUDIO_DEVICE = 'Mapeador de som da Microsoft - Input';

/**
 * Capture shape. PortAudio's BLOCKING read API does not work on this host —
 * every device, including the Microsoft Sound Mapper, raises
 * `PaErrorCode -9999: Blocking API not supported yet` (Windows WDM-KS -9999),
 * and sounddevice's `Stream.read()` rejects its `timeout` kwarg. The verified
 * working shape is a CALLBACK stream (`sd.InputStream(callback=cb)`) that
 * accumulates peak/RMS while the stream stays open. Preferred by default; the
 * worker lane owns whether it can honour it.
 */
const DEFAULT_CAPTURE_MODE = 'callback';

/**
 * Sentences that assert audio is absent. On this host that assertion is false
 * by measurement, and it is the exact conflation the owner was misled by:
 * "no audio" and "no worker" are different states and the panel must be able
 * to tell them apart. Any status matching this is rewritten to the factual
 * version — see `#status`.
 */
const FALSE_AUDIO_ABSENT = /\bwait(?:ing)?\s+for\s+audio\b|\bno\s+audio\b/i;

const CAPTURE_NOT_STARTED =
  'Capture not started - the worker has not opened the audio device';

/** Trailing STDOUT lines kept to explain a death on the status line. */
const STDERR_TAIL_LINES = 3;
const STDERR_TAIL_CHARS = 240;

/**
 * Known worker states. Unknown states fall through to `humaniseState`, so a
 * worker that invents a new state name still produces a truthful status.
 *
 * `kind` is the panel's own vocabulary: `busy` (working), `live` (captions
 * will arrive), `error` (no captions will arrive until something changes).
 */
const STATE_MAP = {
  boot: { kind: 'busy', status: 'Worker booting - starting onnxruntime...', title: 'Booting the ASR worker' },
  loading_model: { kind: 'busy', status: 'Model loading...', title: 'Loading the ASR model' },
  // The LIVE worker emits `model-loading`; it normalises to `model_loading`.
  // A live run caught this key missing and the status falling through to the
  // humaniser as "Worker: Model loading" — mapped states are the whole point.
  model_loading: { kind: 'busy', status: 'Model loading...', title: 'Loading the ASR model' },
  loading: { kind: 'busy', status: 'Model loading...', title: 'Loading the ASR model' },
  model_loaded: { kind: 'busy', status: 'Model loaded - opening the audio device...', title: 'Opening the audio device' },
  ready: { kind: 'busy', status: 'Model ready - opening the audio device...', title: 'Opening the audio device' },
  device: { kind: 'busy', status: CAPTURE_NOT_STARTED, title: 'Audio device opened' },
  capture_starting: { kind: 'busy', status: CAPTURE_NOT_STARTED, title: 'Opening the audio device' },
  opening_device: { kind: 'busy', status: CAPTURE_NOT_STARTED, title: 'Opening the audio device' },
  // The worker resolves the tap at runtime and rotates off a device that stays
  // flat. These are NOT failure words and must not be coloured as failure: the
  // worker is doing exactly the right thing and the run continues on the next
  // candidate. `device_exhausted` IS the failure — every candidate was flat, so
  // no captions will arrive and the operator has to change the routing.
  device_rotated: { kind: 'busy', status: 'Audio tap carried no signal - trying the next device', title: 'Switching audio tap' },
  device_exhausted: { kind: 'error', status: 'No audio tap carried signal - every candidate device was silent', title: 'No working audio tap' },
  listening: { kind: 'live', status: 'Listening - captions appear as speech is transcribed', title: 'Listening' },
  capturing: { kind: 'live', status: 'Listening - captions appear as speech is transcribed', title: 'Listening' },
  running: { kind: 'live', status: 'Listening - captions appear as speech is transcribed', title: 'Listening' },
  // Not "no audio reaching it": that is a claim about audio, measured false on
  // this host. This is a claim about the worker, which is what we can see.
  idle: { kind: 'busy', status: CAPTURE_NOT_STARTED, title: 'Capture not started' },
  // A finished worker is not a failed one. The panel says so, and the bridge
  // still schedules a restart, because a session that ended is a session that
  // should still be running.
  done: { kind: 'busy', status: 'Worker finished its run - no further captions', title: 'Worker finished' },
  stopping: { kind: 'busy', status: 'Worker stopping...', title: 'Worker stopping' },
  stopped: { kind: 'error', status: 'Worker stopped - captions stopped', title: 'Worker stopped' },
  error: { kind: 'error', status: 'Worker reported an error', title: 'Worker reported an error' },
};

/** A state that reads like a failure must not be coloured as health. */
const FAILURE_WORDS = /(error|fail|fatal|dead|stopped|crash|denied|missing)/i;

/** Turn an unrecognised state token into a sentence a human can act on. */
function humaniseState(state) {
  const words = String(state || '')
    .replace(/[_\-.]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (words === '') return 'Worker sent an unnamed status';
  const sentence = words.charAt(0).toUpperCase() + words.slice(1);
  return FAILURE_WORDS.test(words) ? `Worker: ${sentence}` : `Worker: ${sentence}`;
}

/** Placeholder copy for the states the BRIDGE owns (worker-side states get
 *  their own title/body from `describeState`). The caption area's "Waiting for
 *  audio" is replaced by these, which is what makes "no worker" and "no audio"
 *  visibly different claims. */
const BRIDGE_PLACEHOLDER = {
  starting: {
    title: 'Starting the ASR worker',
    body: 'The Python worker is being spawned. Loading a model can take a while.',
  },
  spawning: {
    title: 'Starting the ASR worker',
    body: 'Spawned - waiting for the worker to report its first status line.',
  },
  missing: {
    title: 'Worker not found',
    body: 'There is no Python worker at this path, so nothing can transcribe until one exists.',
  },
  dead: {
    title: 'Worker not running',
    body: 'The worker exited. A restart with backoff is scheduled.',
  },
  silent: {
    title: 'Worker not answering',
    body: 'The worker opened but produced no output before the first-output ceiling fired.',
  },
  stopped: {
    title: 'Worker stopped',
    body: 'The bridge was stopped.',
  },
};

/** How a restart reads in one clause, so the reason is never lost. */
function restartPhrase(reason, workerPath) {
  switch (reason) {
    case 'missing':
      return `no worker at ${workerPath}`;
    case 'exit':
      return 'the worker exited';
    case 'silent':
      return 'the worker produced no output';
    case 'spawn-threw':
    case 'child-error':
      return 'the worker failed to start';
    default:
      return reason;
  }
}

/**
 * @returns {{kind:string,status:string,title:string,body:string}} */
function describeState(state) {
  // Separator-insensitive lookup. The live worker emits `model-loading` with a
  // HYPHEN; an earlier draft of this map only had `model_loading`, so a real
  // worker state fell through to the catch-all and the panel said "Worker:
  // Model loading" instead of the mapped sentence. One worker, one spelling
  // rule: -, _ and space all mean the same state token.
  const key = String(state == null ? '' : state)
    .trim()
    .toLowerCase()
    .replace(/[\s\-.]+/g, '_');
  const mapped = STATE_MAP[key];
  if (mapped) {
    const live = key === 'listening' || key === 'capturing' || key === 'running';
    return {
      kind: mapped.kind,
      status: mapped.status,
      title: mapped.title,
      body: live
        ? 'The Python worker is running and captions land here as speech is transcribed.'
        : 'The Python worker is running and has not reached a listening state yet.',
    };
  }
  return {
    kind: FAILURE_WORDS.test(key) ? 'error' : 'busy',
    status: humaniseState(key),
    title: 'Worker status',
    body: 'The Python worker reported a state this build does not name.',
  };
}

/** Exponential backoff, clamped. `base` doubles per attempt up to `max`. */
function resolveBackoff(over) {
  const b = { base: 500, factor: 2, max: 8000, ...(over || {}) };
  return {
    base: Math.max(0, Number(b.base) || 0),
    factor: Math.max(1, Number(b.factor) || 1),
    max: Math.max(0, Number(b.max) || 0),
  };
}

class WorkerBridge {
  /**
   * @param {object} opts
   * @param {(text:string, meta:object)=>void} opts.onCaption caption receiver
   * @param {(text:string, kind:string)=>void} opts.onStatus  status line sink
   * @param {string} [opts.command]    interpreter to spawn (default `python`)
   * @param {string[]} [opts.args]     argv after the interpreter
   * @param {string} [opts.workerPath] the worker's entrypoint
   * @param {object} [opts.backoff]    {base, factor, max} in ms
   * @param {number} [opts.silenceMs]  first-output ceiling before the worker is
   *                                   declared silent and restarted
   * @param {(line:string)=>void} [opts.log]
   */
  constructor(opts = {}) {
    this.onCaption = typeof opts.onCaption === 'function' ? opts.onCaption : () => {};
    this.onStatus = typeof opts.onStatus === 'function' ? opts.onStatus : () => {};
    this.command = opts.command || DEFAULT_COMMAND;
    this.args = Array.isArray(opts.args) ? opts.args.slice() : [];
    /**
     * Flags the WORKER itself declares, passed only when the owner explicitly
     * asked for something (`--device=...`). Deliberately empty by default: the
     * live worker already lists the measured-best tap first in its own
     * `preferred` order, so imposing a flag it might not have would risk
     * killing a worker over a default that is already right.
     */
    this.extraArgs = Array.isArray(opts.extraArgs) ? opts.extraArgs.slice() : [];
    this.workerPath = opts.workerPath || DEFAULT_WORKER_PATH;
    /**
     * Audio tap, or null when the owner did not name one. null is the honest
     * value for "the worker decides": it is what keeps SOTTO_AUDIO_DEVICE out
     * of the child env, so the worker resolves the tap itself and rotates off
     * a dead one. DEFAULT_AUDIO_DEVICE stays exported as a HINT for callers
     * that want to name a device — passing it here is a real choice, not a
     * default that arrives whether you asked for it or not.
     */
    this.device = typeof opts.device === 'string' && opts.device.trim() !== ''
      ? opts.device.trim()
      : null;
    this.captureMode = opts.captureMode || DEFAULT_CAPTURE_MODE;
    this.log = typeof opts.log === 'function' ? opts.log : () => {};
    this.backoff = resolveBackoff(opts.backoff);
    this.silenceMs = Number.isFinite(opts.silenceMs) ? opts.silenceMs : 15000;
    /**
     * Production always checks the file exists before spawning (the check is
     * what makes the status name the WORKER instead of the shell's ENOENT).
     * The self-test drives a `python -c` script that is a JS string, not a file,
     * so it turns the check off for its own two child-process steps. Only
     * `bridge-selftest.js` ever passes this.
     */
    this.requireExists = opts.requireExists !== false;

    /** @type {import('node:child_process').ChildProcess|null} */
    this.child = null;
    this.state = 'idle';
    this.restarts = 0;
    this.spawns = 0;
    this.captions = 0;
    this.statuses = 0;
    this.malformed = 0;
    this.stopped = false;
    this.timer = null;
    this.silenceTimer = null;
    this.tail = '';
    this.sawOutput = false;
    this.lastStatus = '';
    /** Last emitted status, kept so a renderer that paints late can be caught up. */
    this.lastKind = 'busy';
    this.lastInfo = null;
    this.stderrTail = [];
    this.lastExit = null;
  }

  // --- status ------------------------------------------------------------

  /**
   * The one place a status reaches the panel, and it holds two invariants:
   *
   *   - never empty, because panel.js drops empty statuses and the previous
   *     (stale) text would stay on screen;
   *   - never "waiting for audio" / "no audio", because that is a claim about
   *     audio and it is measured false on this host (system tap CAPTURED,
   *     peak=0.883270). The truthful version of that state is that the
   *     CAPTURE has not started, which is a different fact with a different
   *     fix. This applies to states the worker invents too, not just ours.
   */
  #status(text, kind = 'busy', info = null) {
    let value = String(text == null ? '' : text).trim();
    if (value === '') {
      value = 'Worker status unavailable';
      kind = 'error';
    } else if (FALSE_AUDIO_ABSENT.test(value)) {
      this.log(`BRIDGE_STATUS_FALSIFIED text=${JSON.stringify(value)}`);
      value = CAPTURE_NOT_STARTED;
      kind = 'busy';
    }
    const shaped = info || {};
    this.lastStatus = value;
    this.lastKind = kind;
    this.lastInfo = { title: shaped.title || null, body: shaped.body || null, state: this.state };
    this.onStatus(value, kind, this.lastInfo);
  }

  /** A status the BRIDGE owns: sets `state` and carries placeholder copy. */
  #bridgeStatus(text, kind, placeholderKey, state) {
    this.state = state;
    this.#status(text, kind, BRIDGE_PLACEHOLDER[placeholderKey] || {});
  }

  // --- lifecycle ---------------------------------------------------------

  /**
   * Is a restart already ARMED inside this bridge?
   *
   * This is the fact a caller cannot see any other way. Between a worker's
   * death and the next `#spawn()` there is a window where `child` is null and
   * the bridge is still very much alive — it is holding a `setTimeout` that
   * will bring a new python up on its own. A caller that guards on the child
   * reads that window as "nothing is running, I may start one", which is the
   * exact reading that produced two workers per Alt+C. MEASURED 2026-10-06;
   * receipt: docs/worker-single-instance-20261006.md.
   */
  get hasPendingRestart() {
    return this.timer !== null;
  }

  /** 0 or 1. One bridge owns at most one live child, and this says so. */
  get liveChildCount() {
    return this.child === null ? 0 : 1;
  }

  /**
   * True while this bridge owns the worker lifecycle: a live child OR an armed
   * restart. Neither-yet-started is NOT this — a caller must still be able to
   * bring an idle bridge up. Idempotency for a caller has to be decided on the
   * BRIDGE, because the BRIDGE is what owns both the child and the timer.
   */
  get isActive() {
    return !this.stopped && (this.child !== null || this.timer !== null);
  }

  /**
   * Bring the worker up. Idempotent on the BRIDGE, not on the child.
   *
   * The old guard was `if (this.child) return false`, which is false in the
   * armed-restart window, so a second `#spawn()` joined the one the timer was
   * already going to make — and the first child was then orphaned with nothing
   * holding a handle to it. Same bridge, two live pythons, ~2.1 GB each.
   */
  start(reason = 'start') {
    if (this.stopped) return false;
    if (this.isActive) {
      this.log(`BRIDGE_START_REFUSED reason=${reason} live=${this.liveChildCount} pendingRestart=${this.hasPendingRestart}`);
      return false;
    }
    // `device=auto` is the honest spelling when nobody named one: the worker
    // resolves the tap itself and may rotate off a dead one, so a name here
    // would be a claim about a device the bridge never opened.
    this.log(`BRIDGE_START reason=${reason} command=${this.command} worker=${this.workerPath} device=${this.device === null ? 'auto' : JSON.stringify(this.device)} capture=${this.captureMode}`);
    // basename() is only meaningful for a real file; the self-test's `-c`
    // inline worker is not one, and a status naming a wall of Python is a
    // status nobody can read.
    const label = this.requireExists ? path.basename(this.workerPath) : 'inline worker';
    this.#bridgeStatus(`Starting worker... (${label})`, 'busy', 'starting', 'starting');
    return this.#spawn('start');
  }

  /**
   * Cancel the armed restart, if any. ONE code path for both callers that need
   * it (`stop()` and the double-spawn guard), so "a cancelled restart can
   * never fire later" is a property of one function rather than of two blocks
   * that can drift apart.
   * @returns {boolean} true when a timer was actually cancelled
   */
  #cancelRestart(why) {
    if (this.timer === null) return false;
    clearTimeout(this.timer);
    this.timer = null;
    this.log(`BRIDGE_RESTART_CANCELLED why=${why}`);
    return true;
  }

  /**
   * Bring one python up. Returns true when a child was spawned.
   *
   * ONE BRIDGE, ONE CHILD — asserted here, in the one function that can break
   * it. Every legitimate respawn path (`close`, `error`, the silence ceiling,
   * `stop`) clears `this.child` BEFORE it schedules, so a non-null child on
   * entry means this spawn would orphan a live worker: `this.child` is about
   * to be overwritten, the old process keeps running, and nothing holds a
   * handle to it again. That is the shape of the 2026-10-06 multi-worker
   * report, so it is refused rather than spawned.
   *
   * The refusal also cancels any restart that is armed, because the timer that
   * got us here is now redundant: a worker is alive, and when THAT one dies its
   * own `close` will schedule the next retry.
   */
  #spawn(why = 'spawn') {
    if (this.child !== null) {
      this.#cancelRestart(`double-spawn-refused-${why}`);
      this.log(`BRIDGE_DOUBLE_SPAWN_REFUSED why=${why} pid=${this.child.pid}`);
      // No status on purpose: the panel is already describing the worker that
      // is running, and an error line about a refusal would be a claim about a
      // failure that did not happen.
      return false;
    }
    // The missing-file check is not an optimisation: spawning a nonexistent
    // path fails asynchronously and reports a message that names the shell,
    // not the worker. This names the worker, which is the whole point.
    if (this.requireExists && !fs.existsSync(this.workerPath)) {
      this.log(`BRIDGE_WORKER_MISSING path=${this.workerPath}`);
      this.#bridgeStatus(`Worker not found - ${this.workerPath} does not exist`, 'error', 'missing', 'missing');
      this.#scheduleRestart('missing');
      return false;
    }

    this.state = 'spawning';
    this.spawns += 1;
    this.tail = '';
    this.sawOutput = false;
    this.stderrTail = [];

    let child = null;
    // SOTTO_AUDIO_DEVICE is exported ONLY when the owner named a device. It
    // used to be exported unconditionally from DEFAULT_AUDIO_DEVICE, which
    // made the shell's guess outrank worker/config.json on every run that did
    // not ask for a device — and that guess is not stable, because the
    // endpoint carrying system audio flips with the owner's routing. Absent,
    // the variable is the correct value: the worker resolves the tap itself,
    // reads config.json, and rotates off any candidate that stays flat.
    const childEnv = {
      ...process.env,
      SOTTO_CAPTURE_MODE: this.captureMode,
    };
    if (this.device !== null) childEnv.SOTTO_AUDIO_DEVICE = this.device;
    try {
      child = spawn(this.command, [...this.args, ...this.extraArgs, this.workerPath], {
        cwd: fs.existsSync(path.dirname(this.workerPath))
          ? path.dirname(this.workerPath)
          : process.cwd(),
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
        // Capture preferences travel by ENVIRONMENT, never by argv: a worker
        // built with `argparse` and strict parsing dies on an argument it does
        // not know, but silently ignores an environment variable it does not
        // read. A preference must never be able to kill the worker.
        env: childEnv,
      });
    } catch (err) {
      const message = err && err.message ? err.message : String(err);
      this.log(`BRIDGE_SPAWN_THREW error="${message}"`);
      this.#bridgeStatus(`Worker could not be started: ${message}`, 'error', 'dead', 'dead');
      this.#scheduleRestart('spawn-threw');
      return false;
    }

    this.child = child;
    this.#bridgeStatus('Worker starting - waiting for its first status...', 'busy', 'spawning', 'spawning');
    this.log(`BRIDGE_SPAWNED pid=${child.pid} attempt=${this.restarts + 1}`);

    child.stdout.setEncoding('utf8');
    child.stdout.on('data', (chunk) => this.#consume(chunk));
    child.stderr.setEncoding('utf8');
    child.stderr.on('data', (chunk) => this.#rememberStderr(chunk));

    child.on('error', (err) => {
      const message = err && err.message ? err.message : String(err);
      this.log(`BRIDGE_CHILD_ERROR error="${message}"`);
      this.child = null;
      this.#bridgeStatus(`Worker failed to start: ${message}`, 'error', 'dead', 'dead');
      this.#scheduleRestart('child-error');
    });

    child.on('close', (code, signal) => {
      // A worker that dies before saying anything is silence, not a state.
      // Distinguish it here so the panel can say which it was.
      this.#flush();
      this.#clearSilence();
      this.child = null;
      this.lastExit = { code, signal };
      if (this.stopped) {
        this.state = 'stopped';
        this.log(`BRIDGE_STOPPED code=${code} signal=${signal}`);
        return;
      }
      const how = signal ? `signal ${signal}` : `code ${code}`;
      const because = this.sawOutput ? '' : ' without producing a single line';
      const tail = this.stderrTail.length ? ` - ${this.stderrTail.slice(-1)[0]}` : '';
      // A clean exit is not a death. The live worker returns 0 after a `done`
      // state, and "Worker died (code 0)" would be a lie about a worker that
      // did exactly what it was asked.
      const clean = !signal && code === 0;
      const verb = clean ? 'exited cleanly' : 'died';
      this.log(`BRIDGE_WORKER_EXIT code=${code} signal=${signal} clean=${clean} captions=${this.captions} statuses=${this.statuses} malformed=${this.malformed}`);
      this.#bridgeStatus(`Worker ${verb} (${how})${because}${tail}`, 'error', clean ? 'stopped' : 'dead', clean ? 'stopped' : 'dead');
      this.#scheduleRestart('exit');
    });

    // Fail-fast: a worker that opens its stdout and then says nothing is the
    // real failure mode on this host (a model import can wedge for minutes).
    // A wall-clock ceiling alone would hide *where* the time went, so the
    // first-output ceiling names the failure as silence.
    this.silenceTimer = setTimeout(() => {
      if (this.sawOutput || !this.child) return;
      this.log(`BRIDGE_WORKER_SILENT after=${this.silenceMs}ms path=${this.workerPath}`);
      this.#bridgeStatus(
        `Worker silent - no output for ${Math.round(this.silenceMs / 1000)}s`,
        'error',
        'silent',
        'silent',
      );
      try { this.child.kill(); } catch { /* already gone */ }
      this.child = null;
      this.#scheduleRestart('silent');
    }, this.silenceMs);
    if (this.silenceTimer.unref) this.silenceTimer.unref();
    return true;
  }

  #clearSilence() {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }

  #scheduleRestart(why) {
    if (this.stopped) return;
    // ONE ARMED RESTART PER BRIDGE. A spawn that never starts emits BOTH
    // `error` and `close` on the same child, and each handler schedules its own
    // retry. Without this cancel the second `setTimeout` overwrites `this.timer`
    // while the first is STILL ARMED — one death, two timers, and the surviving
    // one is invisible to `stop()`. MEASURED 2026-10-06, fixed here.
    this.#cancelRestart(`superseded-by-${why}`);
    // Counted BEFORE the delay is computed, because the delay is the backoff
    // for THIS attempt. A bridge that restarts forever has to back off, and the
    // counter is the only thing that makes the delay grow. (A version of this
    // line went missing during the 2026-10-06 edit and the self-test caught it:
    // every retry came back at the base delay, and `arm-die-restart-still-
    // happens` read `restarts=0`.)
    this.restarts += 1;
    const delay = Math.min(
      this.backoff.max,
      this.backoff.base * Math.pow(this.backoff.factor, Math.max(0, this.restarts - 1)),
    );
    this.log(
      `BRIDGE_RESTART attempt=${this.restarts} in=${delay}ms why=${why}`,
    );
    // The waiting time is shown too: a panel that says "dead" with no hint
    // that a retry is in flight reads as a hang. The phrase names the worker
    // and the reason — never "waiting for audio", which is a different claim
    // and is measured false on this host.
    this.#status(
      `Worker not running - ${restartPhrase(why, this.workerPath)}; restart ${this.restarts} in ${(delay / 1000).toFixed(1)}s`,
      'error',
      BRIDGE_PLACEHOLDER[why] || BRIDGE_PLACEHOLDER.dead,
    );
    this.timer = setTimeout(() => {
      this.timer = null;
      if (this.stopped) return;
      this.#spawn(`restart-${this.restarts}`);
    }, delay);
    if (this.timer.unref) this.timer.unref();
  }

  /**
   * Stop for good: kill the child, cancel EVERY timer, say so.
   *
   * "Every timer" is not decoration. A restart that outlives `stop()` fires a
   * `#spawn()` on a bridge nobody owns any more, and that python has no parent
   * to kill it — the exact shape of the multi-worker report, arrived at from the
   * other direction. Both timers go through the one cancel path, and the log
   * line names what was still armed, so "nothing was left armed" is a receipt
   * rather than an intention.
   */
  stop(reason = 'quit') {
    this.stopped = true;
    this.#clearSilence();
    const pendingBefore = {
      restart: this.timer !== null,
      silence: this.silenceTimer !== null,
    };
    this.#cancelRestart(reason);
    if (this.child) {
      const child = this.child;
      this.child = null;
      try { child.kill(); } catch { /* already gone */ }
    }
    this.state = 'stopped';
    this.#status('Worker stopped', 'error', BRIDGE_PLACEHOLDER.stopped);
    this.log(`BRIDGE_STOP reason=${reason} spawns=${this.spawns} captions=${this.captions} malformed=${this.malformed} armedAtStop=restart:${pendingBefore.restart} silence:${pendingBefore.silence} stillArmed=restart:${this.hasPendingRestart} silence:${this.silenceTimer !== null}`);
    return true;
  }

  // --- stdout parsing ----------------------------------------------------

  #consume(chunk) {
    this.sawOutput = true;
    this.#clearSilence();
    this.tail += chunk;
    let nl = this.tail.indexOf('\n');
    while (nl !== -1) {
      const line = this.tail.slice(0, nl);
      this.tail = this.tail.slice(nl + 1);
      this.#handleLine(line);
      nl = this.tail.indexOf('\n');
    }
  }

  /** A last line with no trailing newline is still a line. */
  #flush() {
    if (this.tail.trim() === '') {
      this.tail = '';
      return;
    }
    const line = this.tail;
    this.tail = '';
    this.#handleLine(line);
  }

  #handleLine(rawLine) {
    const line = String(rawLine == null ? '' : rawLine).replace(/\r/g, '').trim();
    if (line === '') return;

    let message = null;
    try {
      message = JSON.parse(line);
    } catch {
      this.malformed += 1;
      // Counted and skipped, never fatal: a traceback on STDOUT must not take
      // the caption stream down with it.
      this.log(`BRIDGE_MALFORMED line=${JSON.stringify(line.slice(0, 120))}`);
      return;
    }
    if (!message || typeof message !== 'object') {
      this.malformed += 1;
      return;
    }

    const type = String(message.type || '').toLowerCase();
    if (type === 'caption') {
      this.#onCaptionMessage(message);
    } else if (type === 'status') {
      this.#onStatusMessage(message);
    } else {
      this.malformed += 1;
      this.log(`BRIDGE_UNKNOWN_TYPE type=${JSON.stringify(type)} line=${JSON.stringify(line.slice(0, 120))}`);
    }
  }

  #onCaptionMessage(message) {
    const text = typeof message.text === 'string' ? message.text : '';
    if (text.trim() === '') {
      this.log('BRIDGE_CAPTION_EMPTY dropped=1');
      return;
    }
    const meta = {
      source: 'worker',
      start: Number.isFinite(message.start) ? message.start : null,
      end: Number.isFinite(message.end) ? message.end : null,
      model: message.model == null ? null : String(message.model),
    };
    this.captions += 1;
    this.log(
      `BRIDGE_CAPTION text=${JSON.stringify(text.trim())} start=${meta.start} end=${meta.end} model=${JSON.stringify(meta.model)}`,
    );
    this.onCaption(text.trim(), meta);
  }

  #onStatusMessage(message) {
    this.statuses += 1;
    const shaped = describeState(message.state);
    this.log(`BRIDGE_STATUS state=${JSON.stringify(String(message.state))} kind=${shaped.kind}`);
    this.lastStatus = shaped.status;
    this.lastKind = shaped.kind;
    this.lastInfo = { title: shaped.title, body: shaped.body, state: this.state };
    this.onStatus(shaped.status, shaped.kind, this.lastInfo);
  }

  #rememberStderr(chunk) {
    const text = String(chunk || '').replace(/\r/g, '').trim();
    if (text === '') return;
    for (const line of text.split('\n')) {
      if (line.trim() === '') continue;
      this.stderrTail.push(line.trim().slice(-STDERR_TAIL_CHARS));
    }
    while (this.stderrTail.length > STDERR_TAIL_LINES) this.stderrTail.shift();
  }
}

/** Convenience factory — the shape main.js and the self-test both use. */
function createBridge(opts) {
  return new WorkerBridge(opts);
}

module.exports = {
  WorkerBridge,
  createBridge,
  describeState,
  humaniseState,
  restartPhrase,
  DEFAULT_WORKER_PATH,
  DEFAULT_COMMAND,
  DEFAULT_AUDIO_DEVICE,
  DEFAULT_CAPTURE_MODE,
  CAPTURE_NOT_STARTED,
  FALSE_AUDIO_ABSENT,
  /** Exported so the self-test asserts the contract it claims to implement. */
  CANNED_JSONL: [
    '{"type":"status","state":"loading_model","model":"selftest-model"}',
    '{"type":"caption","text":"hello from the worker","start":0.0,"end":1.25,"model":"selftest-model"}',
    '{"type":"status","state":"listening"}',
    '{"type":"caption","text":"second caption line","start":1.25,"end":2.5,"model":"selftest-model"}',
    'this line is not json and must not kill the bridge',
    '{"type":"caption","text":"third line after the malformed one","start":2.5,"end":3.0,"model":"selftest-model"}',
    '{"type":"status","state":"idle"}',
  ],
};