
(function () {
  'use strict';
  if (window.sotto) return;   // a second injection must not replace a live bridge

  var subs = { caption: [], status: [], geometry: [] };
  var queue = [];
  var infoSeq = 0;
  var infoPending = {};

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
    //  2. The middle slot is `JSON.stringify(arguments)` ÔÇö an ARRAY of
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
    // This host has no synchronous return values to hand back ÔÇö main -> page
    // is ExecuteScriptAsync and page -> main is fire-and-forget ÔÇö so a sink
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

  window.__sotto_emit = function (kind, json) {
    var payload = null;
    try { payload = JSON.parse(json); } catch (err) { payload = null; }
    emit(kind, payload);
  };

  window.__sotto_info = function (id, json) {
    var resolve = infoPending[id];
    if (!resolve) return;
    delete infoPending[id];
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
    onStatus: function (cb) { return subscribe('status', cb); },
    onGeometry: function (cb) { return subscribe('geometry', cb); },

    hide: function () { post('hide', null); },
    toggle: function () { post('toggle', null); },
    quit: function () { post('quit', null); },

    setPointerInteractive: function (active) {
      post('pointer', { active: Boolean(active) });
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

  // ÔöÇÔöÇ PAGE ERRORS MUST REACH THE LOG, OR A BROKEN PANEL LOOKS LIKE A QUIET ONE ÔöÇÔöÇ
  // Measured 2026-10-07, on the owner's screen with a video playing: the worker
  // transcribed for 20+ s at peak 0.44 and the shell logged thousands of
  // `BRIDGE_CAPTION_SENT delivered=true` lines, while the panel kept showing
  // "Starting the worker" and `#caption-list` stayed `display:none`. NOTHING in
  // the log said why: a throw inside panel.js is invisible to Python, because
  // `evaluate_js` reports the CALL, not the page's own JavaScript. This hook runs
  // from document start (before the panel's scripts), so an init-time throw ÔÇö the
  // case that silently kills every subscription ÔÇö is reported with its source
  // position and stack.
  function reportPageError(detail) {
    // A BARE resource event is not a panel error: a favicon or stylesheet that
    // 404s fires `error` with no message, no position and no stack, and reporting
    // it would put a fake `PAGE_ERROR` in every launch's log ÔÇö which is how a
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
