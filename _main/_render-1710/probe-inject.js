/* SCRATCH PROBE -- injected into the RENDER COPY only, never the product.
 * Writes the computed facts that decide what paints the window edge. */
(function () {
  function box(el) {
    if (!el) return null;
    var s = getComputedStyle(el);
    return {
      sel: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).trim().replace(/\s+/g, '.') : ''),
      borderTop: s.borderTopWidth + ' ' + s.borderTopStyle + ' ' + s.borderTopColor,
      borderRadius: s.borderTopLeftRadius,
      background: s.backgroundColor,
      boxShadow: s.boxShadow,
      overflow: s.overflow,
      rect: (function (r) { return [r.x, r.y, r.width, r.height].join(','); })(el.getBoundingClientRect()),
    };
  }
  function run() {
    var theme = document.documentElement.getAttribute('data-theme');
    var surface = document.body.getAttribute('data-surface');
    var state = document.body.getAttribute('data-state');
    var radius = getComputedStyle(document.documentElement).getPropertyValue('--radius').trim();
    var radiusLg = getComputedStyle(document.documentElement).getPropertyValue('--radius-lg').trim();
    var accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    var gradient = getComputedStyle(document.documentElement).getPropertyValue('--accent-gradient').trim().slice(0, 60);
    var out = {
      theme: theme, surface: surface, state: state,
      radius: radius, radiusLg: radiusLg, accent: accent, accentGradient: gradient,
      html: box(document.documentElement),
      body: box(document.body),
      panel: box(document.getElementById('panel')),
      controls: box(document.querySelector('.panel__controls')),
      wordmark: box(document.querySelector('.wordmark')),
      wordmarkName: box(document.querySelector('.wordmark__name')),
      chromeTele: box(document.querySelector('.chrome--tele[data-chrome="head"]')),
      chromeState: box(document.querySelector('.chrome__state')),
      stripWord: box(document.getElementById('strip-word')),
      grip: box(document.getElementById('strip-drag-handle')),
      gripBg: getComputedStyle(document.getElementById('strip-drag-handle') || document.body).backgroundImage.slice(0, 90),
      stripState: box(document.getElementById('strip-state')),
      liveBtn: box(document.getElementById('strip-live-button')),
      dpr: window.devicePixelRatio,
    };
    var pre = document.createElement('pre');
    pre.id = 'PROBE-OUT';
    pre.textContent = JSON.stringify(out, null, 1);
    document.body.appendChild(pre);
  }
  function emit(txt) {
    var pre = document.createElement('pre');
    pre.id = 'PROBE-OUT';
    pre.textContent = txt;
    (document.body || document.documentElement).appendChild(pre);
  }
  function guarded() {
    try { emit(JSON.stringify(run(), null, 1)); }
    catch (err) { emit('PROBE-ERROR ' + (err && err.stack ? err.stack : String(err))); }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', guarded);
    window.addEventListener('load', guarded);
  } else {
    guarded();
  }
})();