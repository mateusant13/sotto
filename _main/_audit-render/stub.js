'use strict';

/**
 * AUDIT HARNESS — `window.sotto`, the stub.
 *
 * This is NOT the app. It is the bridge surface `app/webview/sotto_webview.py`
 * installs (its `BOOTSTRAP_JS`: `pushCaption`, `setStatus`, `onCaption`,
 * `onStatus`, `onGeometry`, `hide`, `toggle`, `quit`, `setPointerInteractive`,
 * `getInfo`, `captionApplied`, `statusApplied`, `ready`, `clearApplied`,
 * `history.{append,tail,search,root,reveal}`), with the same payload shapes, so
 * `app/panel/panel.js` runs UNMODIFIED against it.
 *
 * What it is FOR: photographing the panel's own files in states the real shell
 * can only reach with a model loaded and an audio device open. Every visual
 * claim in the audit is about `panel.html` / `panel.css` / `panel.js`, which are
 * the SAME bytes here as in the app.
 *
 * What it is NOT evidence for: anything the SHELL does (the window, the click-
 * through style, the ordering between its own `exec_js` writes and the status
 * event). `applyShellState` below is a COPY of the shell's `apply_panel_state`
 * JS, kept verbatim so the two writes happen in the shell's order; it is marked
 * as a copy wherever its result is cited.
 *
 * ── THE TWO SURFACES (2026-10-08) ────────────────────────────────────────────
 * `?wired=1` ADDS the three calls the panel now asks for and the shell does not
 * implement yet — `pause()`, `setLiveEnabled()`, `setPanelSurface()` — so the
 * PAUSE CONFIRMATION and the LIVE toggle can be driven to their wired state. The
 * calls are recorded in `#__audit` exactly as they arrive, because "the button
 * said it paused" and "the panel called `pause()`" are different facts and this
 * harness must be able to tell them apart.
 *
 * WITHOUT `?wired=1` the stub is the app as it IS: no pause, no live switch. That
 * is the default on purpose — a harness that silently upgraded to a shell this
 * repo does not have would make every screenshot a picture of an imaginary app.
 *
 * The audit trail is appended to a HIDDEN `#__audit` div, so it is readable
 * with `--dump-dom` and invisible in the screenshots.
 */

(function () {
  var subs = { caption: [], status: [], geometry: [], stats: [] };
  var audit = {
    appendCalls: [],
    appendedText: [],
    statusText: null,
    pauseCalls: [],
    liveCalls: [],
    surfaceCalls: [],
  };

  /** The harness URL decides which SHELL this page is pretending to run on. */
  var query = String(location.search || '');
  var wired = /(^|[?&])wired=1(&|$)/.test(query);

  function subscribe(kind, cb) {
    if (typeof cb !== 'function') return function () {};
    subs[kind].push(cb);
    return function () {};
  }
  function emit(kind, payload) {
    for (var i = 0; i < subs[kind].length; i += 1) subs[kind][i](payload);
  }

  var bridge = {
    pushCaption: function (text, meta) { emit('caption', { text: text, meta: meta || {} }); return true; },
    setStatus: function (text) { emit('status', String(text == null ? '' : text)); return true; },
    onCaption: function (cb) { return subscribe('caption', cb); },
    onStatus: function (cb) { return subscribe('status', cb); },
    onGeometry: function (cb) { return subscribe('geometry', cb); },
    onStats: function (cb) { return subscribe('stats', cb); },
    hide: function () {}, toggle: function () {}, quit: function () {},
    setPointerInteractive: function () {},
    // The REAL shape (`sotto_webview.py::SottoShell.info`): hotkey, versions,
    // geometry, visible, rendererReady, panel. A stub returning `{}` would leave
    // the HUD's Hotkey and Host rows reading "not reported" — which is the honest
    // rendering of a shell that does not answer, but it is not this shell.
    getInfo: function () {
      return Promise.resolve({
        hotkey: 'Alt+C',
        versions: { shell: 'webview2/pywebview (audit stub)', python: '3.11' },
        geometry: null,
        visible: false,
        rendererReady: true,
        panel: 'panel.html',
      });
    },
    captionApplied: function (text) { audit.appendedText.push(String(text)); },
    statusApplied: function () {},
    ready: function () {},
    clearApplied: function () {},
    history: {
      append: function (text, meta) {
        audit.appendCalls.push({ text: String(text), meta: meta || {} });
        // The REAL panel refuses a live line before it ever gets here
        // (`recordHistory` -> `isCanonicalLine`), so in the app this stub's
        // method is not reached at all. The count is kept so the harness can
        // SHOW that, rather than assume it.
        return Promise.resolve({ entry: null });
      },
      tail: function () {
        // The shipped app's disk state: `history/` holds nothing any more (the
        // transcript accepts only a `producer:'redux'` line and no code
        // produces one), so the feed is empty and says so.
        return Promise.resolve({
          entries: [],
          root: 'H:\\sotto\\history',
          // The shell publishes the CAPABILITY, not a count (F2): `null` while
          // no engine stamps `producer:'redux'`. The panel collapses the drawer
          // and disables the search on this field, so the harness must carry it
          // or it would render a state the app cannot produce.
          canonicalProducer: null,
        });
      },
      search: function (q) { return Promise.resolve({ query: q, hits: [] }); },
      root: function () {
        // The FROZEN interface the shell now implements (`sotto_webview.py`
        // `history_root`, audit F2): the panel reads `canonicalProducer` from
        // HERE and nowhere else — `null` means "no engine in this repo stamps
        // `producer:'redux'`", which is what collapses the drawer.
        return Promise.resolve({
          root: 'H:\\sotto\\history',
          canonicalProducer: null,
        });
      },
      reveal: function (path) { audit.revealCalls = (audit.revealCalls || []).concat([path || null]); },
    },
    HOTKEY: 'Alt+C',
    platform: 'win32',
  };

  if (wired) {
    // THE SHELL THIS REPO DOES NOT HAVE YET. Present only under `?wired=1`.
    bridge.pause = function (options) {
      audit.pauseCalls.push(options || {});
      emit('status', 'Paused — engines unloaded (audit stub)');
      return Promise.resolve({ paused: true, text: 'Paused — engines unloaded (audit stub)' });
    };
    bridge.setLiveEnabled = function (enabled) {
      audit.liveCalls.push(Boolean(enabled));
      return Promise.resolve({ liveEnabled: Boolean(enabled) });
    };
    bridge.setPanelSurface = function (name, reason) {
      audit.surfaceCalls.push({ surface: String(name), reason: String(reason || '') });
      // The real shell resizes the WINDOW and then sets the attribute; here the
      // attribute is all there is to set.
      if (window.SottoSurfaces) window.SottoSurfaces.set(String(name));
    };
    // A stats payload, so the HUD's four NOT-YET-WIRED rows can be SEEN working
    // against the shape the receipt specifies. Nothing emits it unless `?stats=1`.
    if (/(^|[?&])stats=1(&|$)/.test(query)) {
      bridge.__emitStats = function (payload) { emit('stats', payload); };
    }
  }

  window.__sottoStubWired = wired;
  window.sotto = bridge;

  /**
   * The shell's OWN placeholder write, copied VERBATIM from
   * `sotto_webview.py::apply_panel_state` (the JS string at lines 2002-2015),
   * minus the return value. In the real shell it runs AFTER `send_status`, so
   * the shell's text and severity are what the owner finally sees.
   */
  window.applyShellState = function (text, kind, info) {
    window.sotto.setStatus(text);
    info = info || {};
    var title = info.title || '';
    var body = info.body || '';
    var t = document.querySelector('.captions__placeholder-title');
    var b = document.querySelector('.captions__placeholder-body');
    if (t && title) t.textContent = title;
    if (b && body) b.textContent = body;
    var s = document.getElementById('status');
    if (s) {
      s.classList.toggle('status--live', kind === 'live');
      s.classList.toggle('status--error', kind === 'error');
    }
  };

  window.__auditHook = function (note) { audit.note = note; };

  window.__auditReport = function () {
    var root = document.querySelector('.panel');
    var list = document.getElementById('caption-list');
    var ph = document.getElementById('placeholder');
    var st = document.getElementById('status-text');
    var hist = document.getElementById('history-list');
    var hud = document.getElementById('hud');
    var stripbar = document.getElementById('strip-controls');
    var dialog = document.getElementById('pause-dialog');
    var liveBtn = document.getElementById('strip-live-button');
    var confirmBtn = document.getElementById('pause-confirm-button');
    return {
      url: location.href,
      surface: document.body.getAttribute('data-surface'),
      stripWired: window.__sottoStubWired,
      panel: root ? Math.round(root.getBoundingClientRect().width) + 'x'
        + Math.round(root.getBoundingClientRect().height) : null,
      statusText: st ? st.textContent : null,
      statusClass: document.getElementById('status')
        ? document.getElementById('status').className : null,
      stripWord: (document.getElementById('strip-word') || {}).textContent || null,
      stripStateClass: (document.getElementById('strip-state') || {}).className || null,
      placeholderHidden: ph ? ph.hidden : null,
      placeholderTitle: ph ? (ph.querySelector('.captions__placeholder-title') || {}).textContent : null,
      placeholderBody: ph ? (ph.querySelector('.captions__placeholder-body') || {}).textContent : null,
      liveLines: list ? list.childElementCount : null,
      liveText: list ? Array.prototype.map.call(list.children, function (li) {
        return { cls: li.className, text: li.textContent };
      }) : null,
      historyRows: hist ? hist.childElementCount : null,
      historyText: hist ? hist.textContent.slice(0, 200) : null,
      historyNote: (document.getElementById('history-status') || {}).textContent || null,
      // THE TWO SURFACES, as the page really paints them: the class plus the
      // computed display of each surface-only block.
      display: {
        stripbar: stripbar ? getComputedStyle(stripbar).display : null,
        hud: hud ? getComputedStyle(hud).display : null,
        header: getComputedStyle(document.querySelector('.panel__header')).display,
        history: getComputedStyle(document.getElementById('history')).display,
      },
      liveToggle: liveBtn ? { pressed: liveBtn.getAttribute('aria-pressed'),
        wired: liveBtn.dataset.wired, label: (document.getElementById('strip-live-label') || {}).textContent } : null,
      pauseDialog: dialog ? { open: dialog.open, confirmDisabled: confirmBtn.disabled,
        confirmLabel: confirmBtn.textContent, shellNote: (document.getElementById('pause-dialog-shell') || {}).textContent,
        activeElement: document.activeElement ? document.activeElement.id : null } : null,
      hudText: hud ? hud.textContent.replace(/\s+/g, ' ').trim().slice(0, 400) : null,
      // THE WIRE: what the panel actually asked the shell to do.
      pauseCalls: audit.pauseCalls,
      liveCalls: audit.liveCalls,
      surfaceCalls: audit.surfaceCalls,
      revealCalls: audit.revealCalls || [],
      appendCalls: audit.appendCalls,
      appliedTexts: audit.appendedText,
      numberAuditMarkers: (document.body.textContent.match(/Preload bridge missing/g) || []).length,
    };
  };

  function publishAudit() {
    var div = document.createElement('div');
    div.id = '__audit';
    div.style.display = 'none';
    div.textContent = JSON.stringify(window.__auditReport());
    document.body.appendChild(div);
  }
  window.__auditPublish = publishAudit;
})();
