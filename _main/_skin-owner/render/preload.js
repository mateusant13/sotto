/* THE PANEL'S OWN BRIDGE CONTRACT, STUBBED, for the skin render instrument.
 *
 * `contextIsolation: false` on purpose: this file must define the PAGE's
 * `window.sotto`, not an isolated-world copy. It implements exactly the members
 * `panel.js` reads (see `app/webview/sotto_webview.py`'s injected bridge for the
 * real thing) and nothing more — a stub with extra powers would hide a defect.
 *
 * The instrument drives the panel through `pushCaption`/`setStatus`, which is the
 * same pair the real shell uses, so what this harness renders is what the app
 * renders and not a second renderer.
 */
(function () {
  var subs = { caption: [], status: [], stats: [], geometry: [] };
  var captured = [];

  function subscribe(kind, cb) {
    if (typeof cb !== 'function') return function () {};
    subs[kind].push(cb);
    return function () {
      var i = subs[kind].indexOf(cb);
      if (i >= 0) subs[kind].splice(i, 1);
    };
  }

  function emit(kind, payload) {
    var list = subs[kind].slice();
    for (var i = 0; i < list.length; i += 1) {
      try { list[i](payload); } catch (err) { /* a listener's throw is its own */ }
    }
  }

  window.sotto = {
    HOTKEY: 'Alt+C',
    platform: 'win32',
    pushCaption: function (text, meta) {
      var caption = { text: String(text == null ? '' : text), meta: meta || {} };
      captured.push(caption.text);
      emit('caption', caption);
      return true;
    },
    setStatus: function (text) {
      emit('status', String(text == null ? '' : text));
      return true;
    },
    onCaption: function (cb) { return subscribe('caption', cb); },
    onStatus: function (cb) { return subscribe('status', cb); },
    onStats: function (cb) { return subscribe('stats', cb); },
    onGeometry: function (cb) { return subscribe('geometry', cb); },
    getInfo: function () { return Promise.resolve({ worker: null, panel: null }); },
    getStats: function () { return Promise.resolve({}); },
    hide: function () {}, toggle: function () {}, quit: function () {},
    setPointerInteractive: function () {},
    setPanelSurface: function () { return true; },
    captionApplied: function () {}, statusApplied: function () {}, ready: function () {},
    clearApplied: function () {},
    history: {
      append: function (text, meta) {
        return Promise.resolve({ entry: { id: String(text), text: String(text), meta: meta || {}, at: Date.now(), path: '' } });
      },
      tail: function () { return Promise.resolve({ entries: [], root: 'H:\\\\sotto\\\\history', canonical: false }); },
      search: function () { return Promise.resolve({ hits: [] }); },
      root: function () { return Promise.resolve({ root: 'H:\\\\sotto\\\\history', canonical: false }); },
      reveal: function () {},
    },
    __captured: function () { return captured.slice(); },
  };
}());
