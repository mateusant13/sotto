/* geon probe: measures the SHIPPED panel's geometry and writes it into the DOM.
   Injected by geom.py into a scratch copy of panel.html.

   WHY A PROBE AND NOT A SCREENSHOT: a PNG can be looked at by the OWNER, it
   cannot be read by this model. So the same document is rendered once more
   with a measuring script injected, its numbers written into the DOM, and
   --dump-dom prints them back.
*/
(function () {
  var out = {};

  /* Which theme was MEASURED? geom.py stamps it on this tag, because
     theme-switcher.js re-applies the STORED theme (empty here -> the theme-1
     fallback) from <head> and would otherwise hide the theme under test. */
  try {
    out.forcedTheme = (document.currentScript
      && document.currentScript.getAttribute('data-measured-theme')) || null;
  } catch (e) {}

  var list = document.getElementById('caption-list');
  var body = document.getElementById('captions-body');

  /* THE RAIL STARTS OUT EMPTY, AND THE EMPTY STATE IS A PLACEHOLDER OVER IT:
     `#caption-list` ships `hidden` and `#placeholder` is the box that shows in
     its place, cleared on the first real caption (`panel.js addCaption`:
     `dom.placeholder.hidden = true; dom.list.hidden = false`). Filling the list
     WITHOUT that swap left it `display:none` -- measured: 26 rows in the DOM and
     a rail that reported `clientHeight == scrollHeight == 413`, i.e. the box
     was sized by the placeholder plus the theme's padding, and every row was
     in a list with no layout at all. So the probe does the swap the first
     caption does, by hand. */
  try {
    if (list) list.hidden = false;
    var ph = document.getElementById('placeholder');
    if (ph) ph.hidden = true;
  } catch (e) {}

  /* fill the rail so it overflows */
  var filler = '';
  for (var i = 1; i <= 26; i++) {
    filler += '<li class="caption"><span class="caption__time">10:24:'
      + ('0' + (i % 60)).slice(-2) + '</span><span class="caption__text">'
      + 'Linha de ensaio numero ' + i + ', para medir o trilho e a sua rolagem.'
      + '</span></li>';
  }
  if (list) { list.insertAdjacentHTML('afterbegin', filler); }

  /* a synthetic live row carrying the real class names, as renderProvisional
     would build it -- the row the mid-rail/bottom rules act on */
  if (list) {
    list.insertAdjacentHTML('beforeend',
      '<li class="caption caption--provisional">'
      + '<span class="caption__mark" aria-hidden="true"></span>'
      + '<span class="caption__provisional"><span class="caption__text">'
      + 'esta e a linha ao vivo que esta a crescer'
      + '</span></span></li>');
  }

  function rect(el) {
    var r = el.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height),
      top: Math.round(r.top), bot: Math.round(r.bottom) };
  }

  function describe(el) {
    var cs = getComputedStyle(el);
    return { sel: el.tagName.toLowerCase() + '#' + (el.id || '') + '.' +
        (typeof el.className === 'string' ? el.className : ''),
      h: Math.round(el.getBoundingClientRect().height),
      top: Math.round(el.getBoundingClientRect().top),
      disp: cs.display, hidden: !!el.hidden };
  }

  function settle() {
    var root = window;
    try {
      if (out.forcedTheme && root.SottoTheme) {
        root.SottoTheme.set(out.forcedTheme, { persist: false });
      }
      out.theme = document.documentElement.dataset.theme || null;
      out.surface = document.body.dataset.surface || null;
    } catch (e) { out.surface = 'ERR ' + e.message; }

    /* the bar, named, measured on the strip surface (0x0 on the panel) */
    var bar = document.querySelector('.stripbar');
    if (bar) {
      var rb = rect(bar);
      var vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
      var vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
      var bcs = getComputedStyle(bar);
      out.bar = { w: rb.w, h: rb.h, viewport: vw + 'x' + vh,
        leftInset: Math.round(bar.getBoundingClientRect().left),
        rightInset: Math.round(vw - bar.getBoundingClientRect().right),
        bottomInset: Math.round(vh - bar.getBoundingClientRect().bottom),
        radius: bcs.borderTopLeftRadius,
        dots: bar.querySelectorAll('.stripbar__dot').length,
        wordmark: (bar.querySelector('.stripbar__word') || {}).textContent || null };
    }

    /* what followNewestLine() does, verbatim in effect: the rail follows the
       newest line by scrolling to the bottom, unconditionally. */
    if (body) { body.scrollTop = body.scrollHeight; }
    var live = document.querySelector('.caption--provisional');
    if (body && live) {
      var br = body.getBoundingClientRect();
      var lr = live.getBoundingClientRect();
      out.rail = {
        scrollTop: Math.round(body.scrollTop),
        scrollHeight: Math.round(body.scrollHeight),
        clientHeight: Math.round(body.clientHeight),
        fromBottom: Math.round((br.bottom - lr.bottom) * 10) / 10,
        fromTop: Math.round((lr.top - br.top) * 10) / 10,
        liveTopWindow: Math.round(lr.top),
        liveBottomWindow: Math.round(lr.bottom),
        railTopWindow: Math.round(br.top),
        liveH: Math.round(lr.height) };
    }
    if (body) {
      var bs = getComputedStyle(body);
      out.paddingBottom = bs.paddingBottom;
      out.maskImage = (bs.maskImage || bs.webkitMaskImage || 'none').slice(0, 90);
    }
    if (list) { out.list = { children: list.children.length }; }

    /* the strip's own buttons: what the minimalism rules are fighting for */
    out.buttons = Array.prototype.map.call(
      document.querySelectorAll('.stripbar .strip-button'),
      function (b) {
        var cs = getComputedStyle(b);
        var lbl = b.querySelector('.strip-button__label');
        var lblcs = lbl ? getComputedStyle(lbl) : null;
        var r = rect(b);
        return { id: b.id || '(anon)', w: r.w, h: r.h,
          radius: cs.borderTopLeftRadius,
          label: lbl ? (lblcs.display === 'none' ? 'HIDDEN' : 'SHOWN:' + lbl.textContent) : null,
          title: (b.title || '').slice(0, 24) };
      });

    /* THE BOXES, so a number means something: which box owns the rail's
       height, and what grows when the window grows. */
    out.boxes = [];
    ['panel', 'captions', 'captions-body', 'caption-list', 'history',
      'history-body', 'history-list', 'status'].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      out.boxes.push(Object.assign(describe(el), { id: id }));
    });
    try { out.gridRows = getComputedStyle(document.getElementById('panel')).gridTemplateRows; } catch (e) {}
    try { out.capRows = getComputedStyle(document.getElementById('captions')).gridTemplateRows; } catch (e) {}

    /* the top-level chrome, to see what the panel spends its height on */
    out.chrome = Array.prototype.map.call(
      document.querySelectorAll('body > *, .panel > *'), describe);

    /* every child of the collapsed `#history`, named: the ≈50 px claim in the
       panel.css comment above `.history` is being held to the numbers. */
    out.hist = Array.prototype.map.call(
      document.querySelectorAll('#history > *'), describe);
    out.histBar = (function () {
      var b = document.querySelector('.history__bar');
      return b ? [describe(b), rect(b)] : null;
    })();
    /* inside the bar: what is 343px tall? */
    out.barKids = Array.prototype.map.call(
      document.querySelectorAll('.history__bar > *'),
      function (el) { return Object.assign(describe(el), rect(el)); });
    var pre = document.createElement('pre');
    pre.id = 'geom-out';
    try { pre.textContent = JSON.stringify(out); }
    catch (e) { pre.textContent = 'PROBE-STRINGIFY-ERROR ' + e.message; }
    document.body.appendChild(pre);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(settle, 400); });
  } else { setTimeout(settle, 400); }
})();