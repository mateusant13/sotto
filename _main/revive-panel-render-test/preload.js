/* Sotto — the FAKE SHELL BRIDGE for the revive instrument.
 *
 * The page under test is the REAL `app/panel/panel.html`, with the REAL
 * `panel.js` and the real stylesheets, because the feature being measured is a
 * LISTENER that panel.js installs — a stand-in page would have to re-implement
 * the wiring it is supposed to be testing. So `panel.js` must find a bridge
 * rich enough to reach the end of its own init block; anything missing throws
 * inside `wireStatus`/`wireControls` and the init aborts BEFORE `wireRevive`,
 * which would show up as "the click does nothing" for the wrong reason.
 *
 * `contextIsolation: false` in main.js is what lets this file put the object on
 * the PAGE's `window`; the members below are the ones panel.js touches on the
 * way in, plus a spy for `revive`.
 *
 * TWO SWITCHES, both from the environment:
 *   SOTTO_REVIVE_ABSENT=1  -> no `revive` member at all: the honesty arm (a
 *                             shell that has not ported the repair control must
 *                             SAY so, not fake a revive).
 */
'use strict';

const calls = {
  revive: [],
  statusApplied: [],
  ready: 0,
  statusCb: null,
  captionCb: null,
};

const noop = function () {};
const subscribe = function () { return noop; };

const bridge = {
  HOTKEY: 'Alt+C',
  platform: 'win32',

  ready: function () { calls.ready += 1; },
  pushCaption: function () { return true; },
  setStatus: function () { return true; },

  // The two subscriptions the panel needs at init. The callbacks are KEPT so the
  // instrument can drive the panel with the shell's own payload shape
  // (`{text, kind}`, see `wireStatus`) instead of reaching into panel.js.
  onCaption: function (cb) { calls.captionCb = cb; return noop; },
  onStatus: function (cb) { calls.statusCb = cb; return noop; },
  onGeometry: subscribe,
  onStats: subscribe,

  hide: noop,
  toggle: noop,
  quit: noop,
  setPointerInteractive: noop,
  setPanelSurface: noop,
  captionApplied: noop,
  statusApplied: function (t) { calls.statusApplied.push(String(t)); },
  clearApplied: noop,
  getInfo: function () { return Promise.resolve({}); },
  getStats: function () { return Promise.resolve({ peak: 0, blocks: 0 }); },
  // The transcript half. It is here because a MISSING `history` is not a neutral
  // difference: the panel's own "no writer produces the transcript yet" path
  // reaches `applyTranscriptMode` SYNCHRONOUSLY, which is the path that exposed
  // the TDZ in `panel.js` this instrument found (see the comment beside
  // `let transcriptExpanded`). The fake must behave like the real shell so the
  // arm measures the wiring, not the harness.
  history: {
    tail: function () { return Promise.resolve({ entries: [] }); },
    search: function () { return Promise.resolve({ hits: [] }); },
    root: function () { return Promise.resolve(''); },
    append: function () { return Promise.resolve({}); },
    reveal: function () { return Promise.resolve(true); },
  },

  // NOTE, deliberately absent: `pause`. `applyPauseAvailability` reads its
  // absence and says so, which is the same honesty rule the revive follows.
};

if (process.env.SOTTO_REVIVE_ABSENT !== '1') {
  bridge.revive = function (reason) { calls.revive.push(String(reason)); };
}

window.sotto = bridge;
window.__reviveProbe = calls;

/* THE EARLY ERROR CHANNEL, and it has to live HERE. A `panel.js` that threw at
 * INIT would do it while the document is still parsing — long before the driver
 * in main.js is evaluated — so a listener installed by the driver sees an empty
 * list and the run reports "the wiring is missing" with no cause. This file runs
 * before every page script, which is the same reason the real shell injects its
 * hook at document start. */
window.__reviveProbeErrors = [];
window.addEventListener('error', function (e) {
  window.__reviveProbeErrors.push(
    String(e.message) + ' @ ' + String(e.filename || '') + ':'
    + String(e.lineno || 0) + ':' + String(e.colno || 0));
});
window.addEventListener('unhandledrejection', function (e) {
  window.__reviveProbeErrors.push('rejection: ' + String(e.reason));
});

// Which modules actually ran: a `file://` 404 is NOT a window error, so absence
// of an error is not evidence that a script loaded.
window.__reviveProbeDiag = function () {
  return {
    hasSotto: typeof window.sotto === 'object' && window.sotto !== null,
    hasRevive: !!(window.sotto && typeof window.sotto.revive === 'function'),
    hasStatusCb: typeof calls.statusCb === 'function',
    scripts: document.scripts.length,
    themeManifest: typeof window.SottoThemeManifest,
    themeSwitcher: typeof window.SottoTheme,
    themeTune: typeof window.SottoThemeTune,
    surfaces: typeof window.SottoSurfaces,
    formulation: typeof window.SottoCaptionFormulation,
    bridgeMissingPainted: document.body.textContent.indexOf('Preload bridge missing') >= 0,
  };
};
