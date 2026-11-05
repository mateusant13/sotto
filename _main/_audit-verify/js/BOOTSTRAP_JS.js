
(function () {
  'use strict';
  if (window.sotto) return;   // a second injection must not replace a live bridge

  var subs = { caption: [], 'external-caption': [], status: [], geometry: [], stats: [] };
  var queue = [];
  var infoSeq = 0;
  var infoPending = {};
  // THE STATS ROUND-TRIP (ported 2026-10-11 from the 55c422b reference, its
  // lines 2336-2349 + 2227-2233). Measured gap in the live shell: Python
  // `reply_stats` already calls `window.__sotto_stats(id, json)` (this file,
  // `reply_stats`) and `emit_async('stats', ...)` already pushes -- but the
  // page defined NO `__sotto_stats`, NO `getStats` and NO `onStats`, and
  // `subs` had no `stats` topic, so every push went into `subs[kind] || []`
  // and every poll had nothing to resolve. The meter therefore stayed at the
  // floor with the whole channel apparently present on the Python side.
  var statsSeq = 0;
  var statsPending = {};

  function emit(kind, payload) {
    var list = subs[kind] || [];
    for (var i = 0; i < list.length; i++) {
      try { list[i](payload); }
      catch (err) {
        console.error('sotto: a ' + kind + ' listener threw: ' +
          (err && err.message ? err.message : err));
      }
    }
  }

  function channelOpen() {
    return !!(window.pywebview && window.pywebview._returnValuesCallbacks &&
              window.chrome && window.chrome.webview);
  }

  function wire(kind, payload) {
    // Three rules, all measured against pywebview 6.2.1 on this host:
    //  1. The message is an ARRAY. Its pump does
    //     `func_name, func_param, value_id = json.loads(get_WebMessageAsJson())`
    //     (edgechromium.py:244); posting a string hands it one long string and
    //     it raises "too many values to unpack (expected 3)".
    //  2. The middle slot is `JSON.stringify(arguments)` — an ARRAY of
    //     POSITIONAL arguments, because pywebview then does
    //     `func(*func_params)` (util.py:255). Posting a bare object made Python
    //     unpack its KEYS: `ready({captions, placeholder, hasBridge})` arrived
    //     as three positional strings ("SottoHost.dispatch() takes 2
    //     positional arguments but 3 were given").
    //  3. Each element is encoded ONCE. pywebview json.loads()s the slot and
    //     hands the element to Python as-is, so the element must already be
    //     the STRING `dispatch` expects. Encoding the object twice handed
    //     Python a dict instead ("the JSON object must be str, bytes or
    //     bytearray, not dict").
    return ['dispatch',
            JSON.stringify([JSON.stringify({ kind: kind, payload: payload })]),
            '0'];
  }

  function post(kind, payload) {
    var message = wire(kind, payload);
    if (!channelOpen()) { queue.push(message); return; }
    window.chrome.webview.postMessage(message);
  }

  function ensureSink() {
    // pywebview answers every message it dispatched by calling
    // `_returnValuesCallbacks[funcName][valueId]` (util.py:264-266). That slot
    // is normally created by `_createApi` when the page calls the api THROUGH
    // pywebview; we post on the raw channel, so nothing created it and every
    // message raised
    // "window.pywebview._returnValuesCallbacks.dispatch.0 is not a function".
    // This host has no synchronous return values to hand back — main -> page
    // is ExecuteScriptAsync and page -> main is fire-and-forget — so a sink
    // that drops the value is the whole truthfulness of the situation.
    var slots = window.pywebview._returnValuesCallbacks;
    if (!slots.dispatch) slots.dispatch = {};
    if (typeof slots.dispatch['0'] !== 'function') {
      slots.dispatch['0'] = function (returnObj) {
        if (returnObj && returnObj.isError) {
          console.error('sotto: host dispatch returned an error: ' +
            returnObj.value);
        }
      };
    }
  }

  function flush() {
    if (!channelOpen()) return false;
    ensureSink();
    while (queue.length) window.chrome.webview.postMessage(queue.shift());
    return true;
  }

  // `bridge.ready()` is called while panel.js is still parsing, long before
  // pywebview has injected its api. Buffering until the channel opens is what
  // lets panel.js run unmodified instead of being special-cased.
  window.addEventListener('pywebviewready', flush);
  if (!flush()) setInterval(flush, 50);

  function normalise(text, meta) {
    if (text == null) return null;
    var value = String(text).replace(/\s+/g, ' ').trim();
    if (value === '') return null;
    return { text: value, meta: (meta && typeof meta === 'object') ? meta : {} };
  }

  // A COUNT OF WHAT ARRIVED, per kind (reference 2227-2233). The panel's
  // level meter is fed BOTH by a poll and by this push, so a reader that only
  // saw `data-level=live` could not tell a working push from a poll doing all
  // the work. `_main/_strip-stats-probe.py` reads this counter and requires
  // the PUSH to have landed more than once.
  window.__sotto_emit = function (kind, json) {
    var payload = null;
    try { payload = JSON.parse(json); } catch (err) { payload = null; }
    window.__sotto_emit.counts[kind] = (window.__sotto_emit.counts[kind] || 0) + 1;
    emit(kind, payload);
  };
  window.__sotto_emit.counts = {};
  // `__sotto_emit` fala com os SUBSCRITORES DA PAGINA (`emit`), nao com o Python.
  // Um medidor que chega antes de `panel.js` nao tem subscritor nenhum: o
  // resultado dele morria aqui. Este e' o caminho que ENTREGA (`post`), exposto
  // com nome por isso mesmo -- 2026-11-04, medido: o perfil de arranque ficou
  // 24 h a recolher e a descartar (0 `PANEL_BOOT_PROFILE` em 469 587 linhas).
  window.__sotto_post = function (kind, payload) { post(kind, payload); };
  // O INSTANTE DA PINTURA PROVISORIA ENTRA NO LOG (2026-11-04). A metrica do
  // painel era `commit`, que e' o fim do que o olho ja' tinha visto: medido pela
  // lane PanelCommitOnStable, `push` -> `CAPTION_PROVISIONAL_PAINT` esta' em 0 ms
  // e `paint` -> `commit` pagava a espera toda (p50 839, p95 1 500 ms). O
  // `panel.js` ja' produz a linha e o gancho (`SottoPaintLine`/`SottoPaintSink`);
  // faltava o shell instalar o gancho, e sem isso a perna do OLHO so' existia
  // para sondas de DOM. A linha e' a do painel, cortada em 400 B: um gancho que
  // deixa a pagina escrever o log sem limite e' um gancho que o log paga.
  window.SottoPaintSink = function (row) {
    try {
      post('paint-row', { line: window.SottoPaintLine(row) });
    } catch (err) { /* a probe must not break the paint */ }
  };


  window.__sotto_info = function (id, json) {
    var resolve = infoPending[id];
    if (!resolve) return;
    delete infoPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };

  // Same id round-trip as `__sotto_info`, for `getStats`. Without this the
  // shell's own `window.__sotto_stats(...)` call is a silent no-op and the
  // Promise from `getStats()` never resolves -- which is exactly what the
  // owner's log showed: 595 BRIDGE_STATS_REPLY lines and a dead meter.
  window.__sotto_stats = function (id, json) {
    var resolve = statsPending[id];
    if (!resolve) return;
    delete statsPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };

  // The history store round-trip. Same shape as getInfo's id round-trip, so
  // `history.tail()`/`search()`/`append()` really resolve with disk data
  // instead of handing back a synchronous guess.
  var histSeq = 0;
  var histPending = {};
  window.__sotto_history = function (id, json) {
    var resolve = histPending[id];
    if (!resolve) return;
    delete histPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };
  function historyCall(kind, payload) {
    return new Promise(function (resolve) {
      var id = 'h' + (++histSeq);
      histPending[id] = resolve;
      var msg = payload || {};
      msg.id = id;
      post(kind, msg);
    });
  }

  function subscribe(kind, callback) {
    if (typeof callback !== 'function') return function () {};
    subs[kind].push(callback);
    return function () {
      var i = subs[kind].indexOf(callback);
      if (i >= 0) subs[kind].splice(i, 1);
    };
  }

  window.sotto = {
    pushCaption: function (text, meta) {
      var caption = normalise(text, meta);
      if (!caption) return false;
      post('caption-observed', caption);
      emit('caption', caption);
      return true;
    },

    setStatus: function (text) {
      var value = String(text == null ? '' : text);
      post('status-observed', { text: value });
      emit('status', value);
      return true;
    },

    onCaption: function (cb) { return subscribe('caption', cb); },
    // THE PLAYER'S OWN CAPTIONS (YouTube/Stremio). A separate channel because
    // each line REPLACES the live box instead of joining the ASR hypothesis.
    onExternalCaption: function (cb) { return subscribe('external-caption', cb); },
    onStatus: function (cb) { return subscribe('status', cb); },
    onGeometry: function (cb) { return subscribe('geometry', cb); },
    onStats: function (cb) { return subscribe('stats', cb); },

    hide: function () { post('hide', null); },
    toggle: function () { post('toggle', null); },
    quit: function () { post('quit', null); },

    // THE REPAIR CONTROL (panel.js:2045). reviveSupported() (:2007) gates the
    // status click on typeof bridge.revive === 'function', so this entry is
    // what turns the panel's only recovery path from a dead click into a
    // request the shell answers (SottoShell.revive_worker).
    revive: function (reason) {
      post('revive', { reason: String(reason == null ? 'panel' : reason) });
    },

    setPointerInteractive: function (active) {
      post('pointer', { active: Boolean(active) });
    },

    // Strip lane: panel asks the shell for click-through chrome while it
    // keeps painting captions. Documented shell message `sotto:transparency`
    // with `{ on: bool }`. No-op honest when the shell has no window yet.
    setTransparency: function (on) {
      post('transparency', { on: Boolean(on) });
    },

    // THE MISSING CHANNEL, AND IT IS WHY THE DEFERRED ASSETS NEVER LOADED.
    //
    // MEASURED 2026-10-13. `lazy-assets.js:144` asks for a deferred asset with
    //     if (s && typeof s.dispatch === 'function') { s.dispatch('lazy-asset', ...); return; }
    //     if (window.pywebview && window.pywebview.api && window.pywebview.api.dispatch) { ... }
    // and `window.sotto.dispatch` DID NOT EXIST -- grep over this file returned ZERO.
    // So the loader fell through to `window.pywebview.api.dispatch`, which is NOT the
    // channel this shell listens on: `post()` (:2805-2808) publishes on
    // `window.chrome.webview.postMessage`. RESULT, measured on a `cine-cellar` theme:
    //     PANEL_LAZY_ALLOW 0    the page NEVER asked
    //     PANEL_LAZY_EMPTY 4    the gate answered 4 requests with EMPTY 200s
    // so `cinematic.css`, `panel-designs.css`, `skins/skins.js`, `skin-host.js` and
    // `skin-layout.css` loaded as EMPTY BODIES. The designs and their fonts never
    // arrived, which is the owner's *"pouquissimas fontes"* and *"varios designs
    // estao bugados"* -- measured, not guessed.
    //
    // ONE LINE, and it is the same class of defect as `setStripOffset` below: this
    // object is hand-written, not generated from the Python API, so a method the page
    // probes for has to be declared here or the probe is false and the caller skips it
    // in silence.
    dispatch: function (kind, payload) {
      post(String(kind == null ? '' : kind), payload == null ? null : payload);
      return true;
    },

    // THE OWNER'S STRIP DRAG (panel.html:1087). `window.sotto` is THIS object,
    // hand-written here and not generated from the Python API, so without this
    // entry the page's `typeof bridge.setStripOffset === 'function'` probe is
    // FALSE and the whole shell half is skipped in silence -- the bar then moves
    // only INSIDE the window, which after the content-width fix is exactly the
    // pill, so it cannot move at all. `x`/`y` are CUMULATIVE DIP from the dock,
    // not deltas; `phase` is `"move"` during the drag and `"end"` on release.
    setStripOffset: function (x, y, phase) {
      post('setStripOffset', {
        x: Number(x) || 0,
        y: Number(y) || 0,
        phase: String(phase == null ? 'move' : phase),
      });
    },

    // THE NATIVE WINDOW DRAG (2026-10-17). ONE call per drag: the shell enters
    // Windows' own modal move loop (`ReleaseCapture` + `WM_NCLBUTTONDOWN` /
    // `HTCAPTION`) and persists the final rect when the owner releases the
    // mouse. There is no per-move message and no per-move `SetWindowPos`, which
    // is what the old JS drag was made of -- see `strip-drag.js`.
    beginWindowDrag: function (surface) {
      post('beginWindowDrag', { surface: surface == null ? '' : String(surface) });
    },

    // THE LIVE PILL (2026-10-17). It existed in the page but the shell had no
    // method, so `applyLiveEnabled` painted it `aria-disabled` and its own
    // title said the switch could not reach the engine. The shell now owns the
    // second window: `true` shows the independent caption overlay, `false`
    // hides it. Resolved synchronously because the visibility change is local.
    setLiveEnabled: function (on) {
      var want = !!on;
      post('setLiveEnabled', { on: want });
      return Promise.resolve({ liveEnabled: want });
    },

    // THE TRANSLATION TARGET (owner, 2026-10-21). The 3-dot menu's selector sends
    // the chosen language here; `''` means the DEFAULT POLICY (English for every
    // video, Spanish stays Spanish). A non-empty code forces that target for
    // EVERY video. The shell stores it and the caption fetcher reads it.
    setTranslationTarget: function (lang) {
      var want = String(lang == null ? '' : lang);
      post('translation-target', { lang: want });
      return Promise.resolve({ lang: want });
    },

    // PAUSE = UNLOAD (owner, 2026-10-17). The panel's pause controls have
    // always called `bridge.pause()`; the shell never had it, so the dialog
    // said "este shell ainda não consegue pausar". The shell now stops the
    // worker (which releases the CUDA context and its VRAM) and keeps the
    // process paused until the owner revives it.
    pause: function (payload) {
      post('pause', payload || {});
      return Promise.resolve({ paused: true, text: 'Paused - engines unloaded' });
    },

    // preload.js resolves a Promise here (ipcRenderer.invoke). The WebView2
    // transport has no invoke, so the id round-trip below is what makes this a
    // real resolved Promise rather than a synchronous object.
    getInfo: function () {
      return new Promise(function (resolve) {
        var id = 'i' + (++infoSeq);
        infoPending[id] = resolve;
        post('info', { id: id });
      });
    },

    // THE PANEL'S OWN PULL, once a second (`panel.js:2478`). The numbers are
    // the worker's own counters, whitelisted by `stats()`; a field the worker
    // did not print stays ABSENT rather than arriving as a zero this shell
    // invented.
    getStats: function () {
      return new Promise(function (resolve) {
        var id = 's' + (++statsSeq);
        statsPending[id] = resolve;
        post('stats', { id: id });
      });
    },

    // ── THE SURFACE CONTRACT (the shell resizes; the page only wears it) ─────
    // `app/panel/panel.js:1239-1243` calls THIS member and nothing else:
    //
    //     bridge.setPanelSurface('panel', reason)
    //
    // Its absence is not cosmetic. Without it `openFullPanel` falls through to
    // `panel.js:1245-1247` — "switch the layout here ... The strip is NOT short
    // until the window is" — so the strip's own "Open panel" button left the
    // window strip-sized. The shell answers by setting the document surface
    // (`window.SottoSurfaces.set`, the API `surface.js` defines) AND moving the
    // HWND to that surface's geometry, in the same breath.
    setPanelSurface: function (surface, reason) {
      post('panel-surface', {
        surface: String(surface == null ? '' : surface),
        reason: String(reason == null ? '' : reason)
      });
      return true;
    },
    captionApplied: function (text) {
      post('caption-applied', { text: String(text == null ? '' : text) });
    },
    statusApplied: function (text) {
      post('status-applied', { text: String(text == null ? '' : text) });
    },
    ready: function (payload) { post('renderer-ready', payload || {}); },
    clearApplied: function (remaining) {
      post('caption-cleared', { remaining: Number(remaining) || 0 });
    },

    // The transcript history ("redux"). The SHELL owns the disk: it names the
    // file, appends the line, reads it back and reveals it in the file manager.
    // `append` resolves with the entry as written (real path included), so the
    // panel never has to guess the folder layout.
    history: {
      append: function (text, meta) {
        return historyCall('history-append',
          { text: String(text == null ? '' : text), meta: meta || {} });
      },
      tail: function (limit) {
        return historyCall('history-tail', { limit: Number(limit) || 400 });
      },
      search: function (query, limit) {
        return historyCall('history-search',
          { query: String(query == null ? '' : query), limit: Number(limit) || 200 });
      },
      root: function () { return historyCall('history-root', {}); },
      reveal: function (path) {
        post('history-reveal', { path: String(path == null ? '' : path) });
      }
    },

    HOTKEY: 'Alt+C',
    platform: 'win32'
  };

  // ── PAGE ERRORS MUST REACH THE LOG, OR A BROKEN PANEL LOOKS LIKE A QUIET ONE ──
  // Measured 2026-10-07, on the owner's screen with a video playing: the worker
  // transcribed for 20+ s at peak 0.44 and the shell logged thousands of
  // `BRIDGE_CAPTION_SENT delivered=true` lines, while the panel kept showing
  // "Starting the worker" and `#caption-list` stayed `display:none`. NOTHING in
  // the log said why: a throw inside panel.js is invisible to Python, because
  // `evaluate_js` reports the CALL, not the page's own JavaScript. This hook runs
  // from document start (before the panel's scripts), so an init-time throw — the
  // case that silently kills every subscription — is reported with its source
  // position and stack.
  function reportPageError(detail) {
    // A BARE resource event is not a panel error: a favicon or stylesheet that
    // 404s fires `error` with no message, no position and no stack, and reporting
    // it would put a fake `PAGE_ERROR` in every launch's log — which is how a
    // word that matters gets trained out of the next reader. Only a real script
    // error (message, position or stack) is reported.
    if (!detail.text || (detail.text === 'error' && !detail.source && !detail.stack)) return;
    try { post('page-error', detail); } catch (e) { /* nothing left to report with */ }
  }
  window.addEventListener('error', function (event) {
    reportPageError({
      text: String((event && (event.message || (event.error && event.error.message))) || 'error'),
      source: String((event && event.filename) || ''),
      line: Number((event && event.lineno) || 0),
      col: Number((event && event.colno) || 0),
      stack: String((event && event.error && event.error.stack) || '')
    });
  }, true);
  window.addEventListener('unhandledrejection', function (event) {
    var reason = event && event.reason;
    reportPageError({
      text: 'unhandledrejection: ' + String((reason && reason.message) || reason || ''),
      source: 'promise',
      line: 0,
      col: 0,
      stack: String((reason && reason.stack) || '')
    });
  });
})();
