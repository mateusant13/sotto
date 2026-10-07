'use strict';

/**
 * Sotto — WHICH SURFACE the one document is wearing.
 *
 * THE PRODUCT DECISION (owner, 2026-10-08): the global hotkey must NOT open the whole
 * 380x900 panel. It opens a SHORT STRIP holding only the live captions, and the
 * full panel is a place the owner goes on purpose. That is ONE document wearing
 * TWO layouts, so the shell switches surfaces by setting ONE attribute — it does
 * not navigate, and it does not have a second HTML file to keep in sync:
 *
 *     document.body.dataset.surface = 'strip' | 'panel'
 *
 * Everything visual about the difference lives in `panel.css`
 * (`body[data-surface="pair"] ...`). Everything behavioural lives in `panel.js`,
 * which asks `window.SottoSurfaces.current()` instead of reading the attribute
 * itself, so the contract has exactly one definition and a grep for
 * `data-surface` finds every place it matters.
 *
 * WHY IT IS A SEPARATE FILE FROM `panel.js`. The audit harness loads the REAL
 * `panel.js` against the REAL markup with a stub bridge, and it has to be able to
 * pick a surface too — otherwise the owner cannot see the strip by opening one
 * file in a browser. A copy of this logic inside `make-harness.py` would be a
 * SECOND definition of the contract, which is exactly how the harness starts
 * documenting a panel the app does not have. It is loaded by `panel.html` and by
 * the harness, and by nothing else.
 *
 * NOTHING HERE TOUCHES A WINDOW. Sizing the window to the strip is the SHELL's
 * job (it owns the HWND and the work area); this file only says which layout the
 * page is in. The wire contract for the shell is in
 * `_main/receipt-panel-two-surfaces.md`.
 */

(function () {
  var SURFACES = ['strip', 'panel'];
  var DEFAULT_SURFACE = 'panel';

  /** Sane default so the page is never layout-less: the full panel. */
  function normalise(name) {
    var value = String(name == null ? '' : name).trim().toLowerCase();
    // Tolerate the CSS-ish spellings a caller might reach for instead of the
    // bare word (`surface--strip`, `strip-surface`), so a shell that copied a
    // class name out of the stylesheet still gets its surface.
    value = value.replace(/^surface-+/, '').replace(/^surface--/, '');
    return SURFACES.indexOf(value) >= 0 ? value : null;
  }

  var listeners = [];

  function current() {
    var attr = document.body && document.body.dataset ? document.body.dataset.surface : null;
    return normalise(attr) || DEFAULT_SURFACE;
  }

  /**
   * Set the surface and tell whoever is listening.
   *
   * Returns the surface actually applied. An unknown name is REFUSED (the
   * current surface stays), rather than silently becoming the panel: a shell
   * that sends `'strip '` and gets a 900 px window would look like a layout bug.
   */
  function set(name) {
    var value = normalise(name);
    if (!value) return current();
    var previous = current();
    document.body.dataset.surface = value;
    if (value !== previous) {
      for (var i = 0; i < listeners.length; i += 1) {
        try { listeners[i](value, previous); } catch (err) { /* one listener cannot break the switch */ }
      }
    }
    return value;
  }

  /** Subscribe to surface changes. Returns an unsubscribe function. */
  function onChange(callback) {
    if (typeof callback !== 'function') return function () {};
    listeners.push(callback);
    return function () {
      var i = listeners.indexOf(callback);
      if (i >= 0) listeners.splice(i, 1);
    };
  }

  function boot() {
    var fromHash = decodeURIComponent(String(location.hash || '').replace(/^#/, '')).trim();
    var wanted = normalise(fromHash);
    // A hash is a HARNESS affordance, not the app's: `panel.html` is loaded over
    // `file://` with no query string, and a stray `#` in the app's own URL can
    // therefore never put the app in the wrong surface. Without one, the
    // attribute already in the markup stands (`panel`), which is the pre-change
    // behaviour byte for byte.
    if (wanted) set(wanted);
    return current();
  }

  window.SottoSurfaces = {
    SURFACES: SURFACES,
    DEFAULT_SURFACE: DEFAULT_SURFACE,
    current: current,
    set: set,
    onChange: onChange,
    boot: boot,
    normalise: normalise,
  };

  if (document.readyState === 'loading' && document.addEventListener) {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
