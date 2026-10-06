'use strict';

/**
 * Sotto — hot reload: edit a source file, see it in the RUNNING app.
 *
 * WHAT THIS IS
 * ------------
 * Two watchers, one module, no dependencies, no child process:
 *
 *   app/electron/panel.{html,css,js}  -> the caller reloads the live renderer
 *   worker/*.py                        -> the caller restarts the one worker
 *
 * The module NEVER decides what "reload" means. It watches directories, decides
 * WHEN a burst has settled, and hands the caller the list of files that changed.
 * main.js owns the consequences (it is the only thing that knows about the
 * BrowserWindow and the worker bridge). Keeping the policy out of here is what
 * lets the same watcher drive both a renderer reload and a worker restart.
 *
 * WHY DIRECTORIES AND NOT FILES
 * -----------------------------
 * An editor save is not a write: most editors write a temp file and rename it
 * over the original. A watch on the FILE DIES at that rename (Windows reports
 * ERROR_OPERATION_ABORTED and the handle is never valid again), which is the
 * classic "hot reload works twice then stops" bug. A watch on the DIRECTORY
 * survives every replacement of its contents, so the watcher here is armed on
 * the two directories and filters by file name.
 *
 * WHY THE DEBOUNCE EXISTS
 * -----------------------
 * One save is three to five filesystem events (write, attribute change, rename
 * of the temp, rename over, close). Without a settling window the panel would
 * reload three to five times for one keystroke-driven save, and a worker
 * restart is not idempotent — it kills a process and spawns another. The
 * constant is DEBOUNCE_MS: 250 ms of quiet, which is above the tens of
 * milliseconds a rename takes and below the second a human notices. A burst
 * therefore produces exactly ONE call per kind.
 *
 * THE DEBOUNCE IS PER KIND, NOT PER EVENT
 * A panel edit and a worker edit inside the same 250 ms window produce one
 * reload AND one restart — two calls, one for each thing that changed, and
 * still not four.
 *
 * WHAT IT DELIBERATELY DOES NOT WATCH
 * -----------------------------------
 *   main.js   — the running main process cannot hot-reload itself.
 *   preload.js— a renderer reload does not guarantee a fresh preload; a silent
 *               half-applied change is worse than a restart prompt.
 *   __pycache__ / anything not *.py in worker/ — imports and caches are not
 *               the source of truth the worker is restarted for.
 */

const fs = require('node:fs');
const path = require('node:path');

/** Quiet period that must pass after the LAST event of a burst. See above. */
const DEBOUNCE_MS = 250;

/** The renderer assets that reload in place. */
const PANEL_ASSETS = new Set(['panel.html', 'panel.css', 'panel.js']);

/**
 * @param {object} opts
 * @param {(line:string)=>void} opts.log                     receipt sink
 * @param {(files:string[])=>unknown} [opts.onPanelAssetsChanged]
 * @param {(files:string[])=>unknown} [opts.onWorkerChanged]
 * @param {number} [opts.debounceMs]
 * @param {string} [opts.panelDir]
 * @param {string} [opts.workerDir]
 */
function createHotReload(opts = {}) {
  const log = typeof opts.log === 'function' ? opts.log : () => {};
  const onPanelAssetsChanged =
    typeof opts.onPanelAssetsChanged === 'function' ? opts.onPanelAssetsChanged : () => false;
  const onWorkerChanged =
    typeof opts.onWorkerChanged === 'function' ? opts.onWorkerChanged : () => false;
  const debounceMs = Number.isFinite(opts.debounceMs) && opts.debounceMs >= 0
    ? opts.debounceMs
    : DEBOUNCE_MS;
  const panelDir = opts.panelDir || __dirname;
  const workerDir = opts.workerDir || path.resolve(panelDir, '..', '..', 'worker');

  /** @type {import('node:fs').FSWatcher[]} */
  const watchers = [];
  /** @type {NodeJS.Timeout|null} */
  let timer = null;
  let pending = { panel: new Set(), worker: new Set(), events: 0 };
  let stopped = false;

  /** Fire the settled burst: at most one call per kind. */
  function flush() {
    timer = null;
    const panel = [...pending.panel].sort();
    const worker = [...pending.worker].sort();
    const events = pending.events;
    pending = { panel: new Set(), worker: new Set(), events: 0 };

    // One call per kind, each carrying its own files. A caller that throws or
    // rejects must not take the app down: this code runs inside the main
    // process, and a failed reload is a bug report, not a reason to lose the
    // panel. The async arm is not decoration — the worker restart returns a
    // promise, and an unhandled rejection here would take the main process
    // down, which is exactly the failure this module exists to prevent.
    const call = (label, files, fn) => {
      let result;
      try {
        result = fn(files);
      } catch (err) {
        log(
          `HOT_RELOAD_${label}_THREW files=${JSON.stringify(files)} ` +
            `error=${JSON.stringify(err && err.message ? err.message : String(err))}`,
        );
        return;
      }
      if (result && typeof result.then === 'function') {
        result.then(undefined, (err) => {
          log(
            `HOT_RELOAD_${label}_REJECTED files=${JSON.stringify(files)} ` +
              `error=${JSON.stringify(err && err.message ? err.message : String(err))}`,
          );
        });
      }
    };
    if (panel.length) {
      log(`HOT_RELOAD_PANEL files=${JSON.stringify(panel)} events=${events} debounce_ms=${debounceMs}`);
      call('PANEL', panel, onPanelAssetsChanged);
    }
    if (worker.length) {
      log(`HOT_RELOAD_WORKER files=${JSON.stringify(worker)} events=${events} debounce_ms=${debounceMs}`);
      call('WORKER', worker, onWorkerChanged);
    }
  }

  function schedule(kind, file) {
    if (stopped) return;
    pending[kind].add(file);
    pending.events += 1;
    if (timer) clearTimeout(timer);
    timer = setTimeout(flush, debounceMs);
    // Never hold the event loop open for a pending reload: the app's own loop
    // keeps it alive, and on quit a half-settled burst must not resurrect work.
    if (timer.unref) timer.unref();
  }

  /**
   * Arm one directory. Returns the watcher, or null when the directory is not
   * there — a missing worker directory must not be a fatal error in the main
   * process, it must be a line in the log.
   */
  function watchDir(dir, kind, accept) {
    try {
      const watcher = fs.watch(dir, { persistent: true }, (event, name) => {
        if (stopped) return;
        // Windows hands the name over as a Buffer under some conditions.
        const file = name === null || name === undefined ? '' : String(name);
        const base = path.basename(file);
        if (base === '' || !accept(base)) return;
        schedule(kind, file);
      });
      watcher.on('error', (err) => {
        log(`HOT_RELOAD_WATCH_ERROR dir=${JSON.stringify(dir)} error=${JSON.stringify(String(err))}`);
      });
      watchers.push(watcher);
      log(`HOT_RELOAD_WATCH kind=${kind} dir=${JSON.stringify(dir)} debounce_ms=${debounceMs}`);
      return watcher;
    } catch (err) {
      log(`HOT_RELOAD_WATCH_FAILED kind=${kind} dir=${JSON.stringify(dir)} error=${JSON.stringify(String(err))}`);
      return null;
    }
  }

  return {
    /** Arm both directories. Safe to call once; logs what it got. */
    start() {
      if (stopped) return false;
      watchDir(panelDir, 'panel', (base) => PANEL_ASSETS.has(base));
      watchDir(workerDir, 'worker', (base) => base.endsWith('.py') && !base.startsWith('.'));
      return true;
    },
    /** Close the watchers and drop a burst that has not settled yet. */
    stop(reason = 'quit') {
      if (stopped) return false;
      stopped = true;
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      const dropped = pending.events;
      pending = { panel: new Set(), worker: new Set(), events: 0 };
      while (watchers.length) {
        const w = watchers.pop();
        try {
          w.close();
        } catch { /* already closed */ }
      }
      log(`HOT_RELOAD_STOPPED reason=${reason} watchers=0 droppedUnsettledEvents=${dropped}`);
      return true;
    },
    /** The constant this instance actually uses — the doc must match the run. */
    debounceMs,
  };
}

module.exports = { createHotReload, DEBOUNCE_MS, PANEL_ASSETS };