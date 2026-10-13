/* caption-float.js — the FLOATED caption: an INDEPENDENT overlay.
 *
 * owner, 2026-10-12, verbatim: *"e ele tem um botao de linhar a legenda, que liga ela NA
 * TELA, igual um overlay, EXATAMENTE IGUAL os .zip fazem."*
 * and, the same day, after using it: *"a porra da legenda, e pra ser independente do
 * painel, nao acoplado."* — *"e eu to vendo div com cor solida inves de invisivel."*
 *
 * WHAT CHANGED IN THIS REVISION, AND WHY (lane: caption, 2026-10-12).
 * The first revision of this module was a VIEW of the panel: it resolved five nodes by
 * the panel's ids, read the panel's own attribute (`body[data-float]`) as its state,
 * and was painted only while the document was on the strip surface — so with no panel
 * mounted it did nothing at all. That is the coupling the owner named. This revision
 * gives the overlay its own state, its own DOM, its own stylesheet and its own feed:
 *
 *   * OWN STATE. The host carries `data-float`; the module owns `on` and exposes
 *     show()/hide()/toggle()/setFloat(). `body[data-float]` is still READ (an older
 *     panel.js, or the shell, still writes it) but never depended on, and the state is
 *     mirrored onto <html> because the shell reads it there
 *     (sotto_webview.py:6527/:6579 — it sized the floated caption by the strip's rules
 *     while the attribute lived only on <body>).
 *   * OWN DOM. If #caption-float is not in the document, the module builds it (same
 *     classes and ids the panel.css rules and the probes already use) and appends it to
 *     the body. A document with no panel at all still gets a caption.
 *   * OWN STYLES. caption-float.css is linked by this module when the document does not
 *     already link it, so the overlay's independence travels with the overlay.
 *   * OWN FEED. With no panel in the document the module subscribes to the shell bridge
 *     itself (window.sotto.onCaption) — the same `{text, meta}` shape panel.js pushes.
 *     With a panel present it subscribes to NOTHING: panel.js is the single source of
 *     the text, so one caption can never be painted twice.
 *
 * WHAT IT STILL DOES NOT OWN, on purpose: the button (#strip-float-button) and the
 * window height, which belong to panel.js and the shell. The module is a call away from
 * both and a dependency on neither.
 *
 * DEFERRED, like letter-swap.js: it registers itself and nothing else, so a caption that
 * lands before it executes is picked up the moment this module runs. */
(function () {
  'use strict';

  var CSS_FILE = 'caption-float.css';
  var SCRIPT_FILE = 'caption-float.js';

  var host = null;
  var stage = null;
  var col = null;
  var line = null;
  var prev = null;
  var meter = null;
  var meterFill = null;
  var credits = null;
  var led = null;
  var current = null;
  var previous = null;
  var listening = false;

  /* THE OVERLAY'S OWN SWITCH. Never read off the panel's state. */
  var on = false;
  /* WHO FEEDS THE TEXT: 'panel' (panel.js pushes), 'self' (this module listens to the
     shell bridge because no panel is mounted), 'none' (nobody yet). */
  var feed = 'none';
  var unsubscribe = null;
  var watching = false;

  function doc() { return typeof document === 'undefined' ? null : document; }

  function el(name, className, id) {
    var d = doc();
    var node = d.createElement(name);
    if (className) node.className = className;
    if (id) node.id = id;
    return node;
  }

  /* ── THE STYLESHEET THIS OVERLAY CARRIES ────────────────────────────────────
   * Idempotent: a document that already links caption-float.css (the Lead's
   * <link>, or a previous run of this function) gets nothing added. The href is
   * derived from this module's own <script src>, so the two files travel together;
   * a document that loads the module without a script tag (a probe, a host page)
   * falls back to the bare file name, which resolves against the document. */
  function linkedHref() {
    var d = doc();
    if (!d || !d.querySelectorAll) return null;
    var links = d.querySelectorAll('link[rel="stylesheet"]');
    for (var i = 0; i < links.length; i++) {
      var href = String(links[i].getAttribute('href') || '');
      if (href.indexOf(CSS_FILE) >= 0) return href;
    }
    return null;
  }

  function ensureStyles() {
    var d = doc();
    if (!d || !d.head) return false;
    if (linkedHref()) return false;
    var src = null;
    if (d.querySelector) {
      var script = d.querySelector('script[src$="' + SCRIPT_FILE + '"]');
      if (script) src = String(script.getAttribute('src') || '');
    }
    var href = src ? src.replace(/[^/]*$/, CSS_FILE) : CSS_FILE;
    var link = el('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.setAttribute('data-sotto-caption-float', '1');
    d.head.appendChild(link);
    return true;
  }

  /* ── THE OVERLAY'S OWN DOM ──────────────────────────────────────────────────
   * The markup is the panel's own (#caption-float + the five ids the probes and
   * panel.js already use), so building it here is not a second design: it is the
   * same contract, created when the document does not carry it. */
  function build(hostEl) {
    while (hostEl.firstChild) hostEl.removeChild(hostEl.firstChild);
    var stageEl = el('div', 'caption-float__stage');
    var ledEl = el('span', 'caption-float__led');
    ledEl.setAttribute('aria-hidden', 'true');
    var colEl = el('div', 'caption-float__col');
    var prevEl = el('p', 'caption-float__prev', 'caption-float-prev');
    prevEl.setAttribute('aria-hidden', 'true');
    var lineEl = el('p', 'caption-float__line', 'caption-float-line');
    var meterEl = el('div', 'caption-float__meter', 'caption-float-meter');
    meterEl.setAttribute('aria-hidden', 'true');
    var fillEl = el('span', 'caption-float__meter-fill', 'caption-float-meter-fill');
    var creditsEl = el('p', 'caption-float__credits', 'caption-float-credits');
    creditsEl.setAttribute('aria-hidden', 'true');
    meterEl.appendChild(fillEl);
    colEl.appendChild(prevEl);
    colEl.appendChild(lineEl);
    colEl.appendChild(meterEl);
    colEl.appendChild(creditsEl);
    stageEl.appendChild(ledEl);
    stageEl.appendChild(colEl);
    hostEl.appendChild(stageEl);
    return true;
  }

  function resolve() {
    var d = doc();
    if (!d || !host) return false;
    stage = host.querySelector('.caption-float__stage');
    col = host.querySelector('.caption-float__col');
    line = d.getElementById('caption-float-line') || host.querySelector('.caption-float__line');
    prev = d.getElementById('caption-float-prev') || host.querySelector('.caption-float__prev');
    meter = d.getElementById('caption-float-meter') || host.querySelector('.caption-float__meter');
    meterFill = d.getElementById('caption-float-meter-fill') || host.querySelector('.caption-float__meter-fill');
    credits = d.getElementById('caption-float-credits') || host.querySelector('.caption-float__credits');
    led = host.querySelector('.caption-float__led');
    return !!(stage && col && line && prev && meter && meterFill && credits && led);
  }

  function mount() {
    var d = doc();
    if (!d || !d.body) return false;
    if (host && !d.body.contains(host)) host = null;   // a re-parsed document
    if (!host) host = d.getElementById('caption-float');
    if (!host) {
      host = el('div', 'caption-float', 'caption-float');
      host.setAttribute('data-float', on ? 'on' : 'off');
      host.setAttribute('aria-hidden', 'true');
      d.body.appendChild(host);
    }
    if (!resolve()) build(host);
    return resolve();
  }

  function nodes() {
    if (host && line) return true;
    return mount();
  }

  /* ── INDEPENDENCE, AND THE ONE CONTEXT RULE ─────────────────────────────────
   * The overlay is painted from its OWN state. The single thing it still respects
   * is a panel that IS mounted: the full panel already shows the same words, so the
   * overlay must not paint over it (the design rule panel.css used to express by
   * scoping the overlay to the strip surface). With no panel in the document there
   * is nothing to respect and the caption is free. */
  function panelMounted() {
    var d = doc();
    return !!(d && d.querySelector && d.querySelector('.panel'));
  }

  function surface() {
    var d = doc();
    return d && d.body && d.body.getAttribute ? d.body.getAttribute('data-surface') : null;
  }

  function shouldPaint() {
    if (!on) return false;
    if (!panelMounted()) return true;
    return surface() !== 'panel';
  }

  function paint() {
    if (!nodes()) return false;
    var want = shouldPaint();
    host.setAttribute('data-float', on ? 'on' : 'off');
    host.style.display = want ? 'block' : 'none';
    host.setAttribute('aria-hidden', want ? 'false' : 'true');
    /* THE SHELL READS IT HERE. sotto_webview.py:6527 (strip width) and :6579
       (strip/float height) both read documentElement[data-float]; the panel wrote
       it on <body> only, so the floated caption was measured as if it were not
       floated. One writer for this attribute: this module. */
    var d = doc();
    if (d && d.documentElement && d.documentElement.setAttribute) {
      d.documentElement.setAttribute('data-float', on ? 'on' : 'off');
    }
    return want;
  }

  /* ── THE PUBLIC STATE, ONE WRITE ────────────────────────────────────────── */
  function setFloat(next) {
    var want = !!next;
    var changed = want !== on;
    on = want;
    paint();
    /* TELL THE SHELL, OR THE CAPTION IS CLIPPED TO THE STRIP'S HEIGHT.
     *
     * `paint()` mirrors `data-float` onto the host, `body` AND
     * `documentElement` -- but the shell reads `--float-height` inside
     * `refresh_strip_height`, which runs at the TOP of `set_panel_surface`
     * (sotto_webview.py:6801), BEFORE the surface script that would set the
     * attribute. Mirroring the attribute is therefore necessary and NOT
     * sufficient: something has to ask the shell to look again.
     *
     * MEASURED 2026-10-12, before this fix: with `data-float="on"` written and
     * no re-application, the floated window stayed 380x148 -- the strip's size --
     * while the CSS laid the caption out for `--float-height`. The owner's
     * "legenda solta na tela" would have been cut off at the strip's height.
     *
     * `setPanelSurface` is the shell member that switches the document surface
     * AND resizes the window in the same breath, which is exactly what is owed
     * here. Called only on a REAL change, so a repeated show() costs nothing. */
    if (changed) {
      try {
        var b = window.sotto;
        if (b && typeof b.setPanelSurface === 'function') {
          b.setPanelSurface('strip', want ? 'float-on' : 'float-off');
        }
      } catch (err) { /* a shell that cannot resize must not break the toggle */ }
    }
    return changed;
  }
  function show() { return setFloat(true); }
  function hide() { return setFloat(false); }
  function toggle() { return setFloat(!on); }
  function isOn() { return on; }

  /**
   * Push one caption. panel.js calls this from its own caption choke points, so the
   * overlay shows exactly what the panel shows — same text, same producer, same
   * instant. The previous line is kept one back, which is what makes the live line
   * read as LIVE.
   */
  function push(text, meta) {
    if (!nodes()) return;
    var value = typeof text === 'string' ? text : '';
    if (value && value !== current) {
      previous = current;
      current = value;
    }
    line.textContent = value;
    // THE ZIP EMPTY STATE (Caption.tsx, the inst design): while the engine is
    // listening and no line has closed, the line node wears is-empty and reads
    // OUVINDO... — 13px, tracking 0.3em, white at 30%. The class is the whole
    // switch, so the live line and the empty state can never both paint.
    var empty = !value && listening;
    line.classList.toggle('is-empty', empty);
    if (empty) line.textContent = 'OUVINDO\u2026';
    prev.textContent = previous || '';
    // The credits are only rewritten when a meta ARRIVES. A provisional push carries
    // no producer, and erasing the line on every partial would make the overlay
    // flicker between the speaker's name and nothing.
    if (meta && typeof meta === 'object') {
      var who = [];
      if (meta.producer) who.push(String(meta.producer));
      if (meta.source) who.push(String(meta.source));
      credits.textContent = who.length ? who.join(' · ') : '';
    }
  }

  /** The listening meter. panel.js feeds it the same smoothed level its own bars use. */
  function setMeter(level) {
    if (!nodes() || !meterFill) return;
    var v = Number(level);
    if (!Number.isFinite(v)) v = 0;
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    meterFill.style.transform = 'scaleX(' + v.toFixed(4) + ')';
    if (listening) meter.classList.add('is-on');
  }

  /** Whether the meter is on at all — the zip shows it only while audio is arriving. */
  function setListening(next) {
    if (!nodes() || !meter) return;
    listening = !!next;
    meter.classList.toggle('is-on', listening);
    // The bar breathes only while the engine is LISTENING. The zip drives the same
    // class from the forming-or-empty condition; here the listening flag is the
    // same fact, and a stopped engine leaves the bar at rest rather than pulsing
    // over a dead window.
    if (led) led.classList.toggle('is-on', listening);
  }

  /* ── THE FEED, WHEN THERE IS NO PANEL TO FEED IT ────────────────────────────
   * The shell's bridge is window.sotto (sotto_webview.py:2867) and its caption
   * events are {text, meta}. This is the SAME subscription panel.js takes; it is
   * taken here ONLY when no panel is in the document, so the two can never both
   * paint one caption. */
  function bridgeObject() {
    var w = typeof window === 'undefined' ? null : window;
    if (!w) return null;
    if (w.sotto && typeof w.sotto.onCaption === 'function') return w.sotto;
    if (w.SottoCaptionSource && typeof w.SottoCaptionSource.onCaption === 'function') return w.SottoCaptionSource;
    return null;
  }

  function selfFeed() {
    if (panelMounted()) {
      // A panel IS here: it owns the text. If we had subscribed before it appeared,
      // let go of the subscription — two feeders would paint one caption twice.
      if (feed === 'self') own();
      else feed = 'panel';
      return false;
    }
    if (feed === 'panel') return false;
    if (unsubscribe) return true;
    var b = bridgeObject();
    if (!b) return false;
    try {
      unsubscribe = b.onCaption(function (payload) {
        if (!payload) return;
        push(payload.text, payload.meta || null);
      });
    } catch (err) {
      unsubscribe = null;
      return false;
    }
    feed = 'self';
    return true;
  }

  /** A panel is here: it owns the text, so the module stops feeding itself. */
  function own() {
    feed = 'panel';
    if (typeof unsubscribe === 'function') {
      try { unsubscribe(); } catch (err) { /* a broken remover must not throw here */ }
    }
    unsubscribe = null;
    return true;
  }

  /* ── THE PANEL'S WRITES ARE ADOPTED, NEVER DEPENDED ON ──────────────────────
   * panel.js (this revision, and every older one) writes body[data-float] and
   * body[data-surface]. The overlay follows both, so the two can never disagree —
   * but if neither ever arrives the module is already correct on its own. */
  function watch() {
    var d = doc();
    if (watching || !d || !d.body || typeof MutationObserver !== 'function') return false;
    var observer = new MutationObserver(function () {
      var attr = d.body.getAttribute('data-float');
      if (attr === 'on' || attr === 'off') on = attr === 'on';
      selfFeed();
      paint();
    });
    observer.observe(d.body, { attributes: true, attributeFilter: ['data-float', 'data-surface'] });
    watching = true;
    return true;
  }

  function state() {
    return {
      on: on,
      painted: !!(host && host.style && host.style.display === 'block'),
      standalone: !panelMounted(),
      feed: feed,
      mounted: !!(host && line),
      text: current,
      prev: previous,
      listening: listening
    };
  }

  window.SottoCaptionFloat = {
    push: push,
    setMeter: setMeter,
    setListening: setListening,
    state: state,
    show: show,
    hide: hide,
    toggle: toggle,
    setFloat: setFloat,
    isOn: isOn,
    mount: mount,
    own: own
  };

  function boot() {
    ensureStyles();
    mount();
    var d = doc();
    if (d && d.body && d.body.getAttribute && d.body.getAttribute('data-float') === 'on') on = true;
    watch();
    selfFeed();
    paint();
    return true;
  }

  // A body that already exists is a document this module can build in NOW; only a
  // document still parsing waits for DOMContentLoaded. (A host page that loads the
  // module at the end of <body> used to wait for an event that had already fired.)
  if (doc() && !doc().body && doc().readyState === 'loading' && doc().addEventListener) {
    doc().addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
