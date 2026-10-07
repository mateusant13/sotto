'use strict';

/**
 * AUDIT HARNESS — the driver. Runs AFTER `panel.js`, drives the panel through
 * the stub bridge, and publishes a hidden JSON receipt into `#__audit`.
 *
 * Every sequence below is the WIRE ORDER the real shell produces, read from
 * `app/webview/sotto_webview.py` / `worker/sotto_worker.py`:
 *
 *   boot   `_bridge_status('Starting worker... (sotto_worker.py)', ...)` then the
 *          worker's own `model-loading` status.
 *   live   the worker's partial captions (`final:false`) followed by the ONE
 *          `final:true` line its second pass closed; the `done` status flushes
 *          the held line; a last `final:false` fragment is left OPEN so the
 *          provisional tail is on screen.
 *   dead   what the shell paints for a worker that died on a silent device —
 *          `applyShellState(text, 'error', {title:'Not transcribing', body:...})`,
 *          whose text/body come from `worker_status_text`/`worker_status_body`.
 *
 * ── THE STATES (2026-10-08) ──────────────────────────────────────────────────
 * THE STATE IS PICKED BY THE URL HASH and the simulated shell by `?wired=1`:
 *
 *   #idle            the LIVE box empty, on the PANEL surface (the shipped DOM)
 *   #live            the PANEL surface with a caption, a provisional tail, Done
 *   #dead            the PANEL surface showing a silent-device death
 *   #dead-panel-only the same status with no shell follow-up
 *   #strip           the STRIP surface, empty (what Alt+C opens cold)
 *   #strip-live      the STRIP surface with a committed line and live status
 *   #pause-confirm   the PAUSE CONFIRMATION open (default focus on Cancel)
 *   #pause-confirmed the confirmation pressed, through to the paused state
 *
 * ── THE FIVE THEMES (2026-10-08, added by the theme lane) ────────────────────
 *   #themes          FIVE REAL PANELS, ONE PER THEME, side by side, all driven
 *                    with the same #live caption sequence. Open this ONE file
 *                    and the five designs are on screen at once.
 *
 * `?wired=1` adds `pause()` / `setLiveEnabled()` / `setPanelSurface()` to the
 * stub — the calls `panel.js` asks for and neither shipped shell has yet — so
 * the wired path can be seen, not just described. WITHOUT it the page shows what
 * the repo actually IS: both pause buttons painted inert and a confirm button
 * that says the shell cannot pause yet.
 *
 * ── A PREVIEW IS A REAL PANEL, NOT A DRAWING ─────────────────────────────────
 * Each themed panel in `#themes` is an `<iframe>` loading THIS SAME FILE with
 * `?state=<sequence>&theme=theme-N`. That is what makes the comparison honest:
 * the iframe's document is `panel.html` plus `panel.css` plus the real
 * `panel.js`, dressed with the theme applied THE SHIPPED WAY — an attribute on
 * the iframe document's own root:
 *
 *     document.documentElement.dataset.theme = 'theme-3'
 *
 * Five theme files all load into one document and every rule in each is scoped
 * to `:root[data-theme='…']`, so this is the documented mechanism and not an
 * approximation of it.
 */

(function () {
  var params = new URLSearchParams(location.search || '');
  /* `state=` is how a themed PREVIEW passes the sequence: an iframe cannot
   * change its own hash without navigating, and `hashchange` is not delivered
   * for a hash set in the parent. Both spellings select the same arm. */
  var hash = (params.get('state') || (location.hash || '#idle').slice(1));
  var theme = params.get('theme') || '';
  /* `inert=1` = a THEMED PREVIEW: apply the theme and nothing else. The child
   * must not mount the theme button (that lives in the big panel above) and must
   * not re-read the stored choice, or five iframes would fight over the key. */
  var inert = params.get('inert') === '1';

  function caption(text, start, end, isFinal) {
    window.sotto.pushCaption(text, { start: start, end: end, final: Boolean(isFinal) });
  }

  /** The `live` sequence, shared by both surfaces so they cannot drift apart. */
  function playLiveStream() {
    window.applyShellState('Starting worker... (sotto_worker.py)', 'busy', {
      title: 'Starting the worker',
      body: 'The transcription worker is being launched. No audio is being read yet.',
    });
    window.sotto.setStatus('model-loading');
    caption('o rato roeu', 0.0, 1.2, false);
    caption('o rato roeu a rolha', 0.0, 2.4, false);
    caption('O rato roeu a rolha da garrafa do rei da Russia.', 0.0, 4.0, true);
    window.sotto.setStatus('done');
    caption('a prova dos nove', 5.0, 6.4, false);
  }

  if (hash === 'idle') {
    // The panel's own shipped initial DOM, untouched.
  }

  if (hash === 'live') {
    playLiveStream();
  }

  if (hash === 'dead') {
    window.applyShellState(
      'Silent audio device - Mapeador de som da Microsoft - Input [MME] peaked 0.000122 < floor 0.002',
      'error',
      {
        title: 'Not transcribing',
        body: 'verdict=silent-device device=Mapeador de som da Microsoft - Input '
          + 'peak=0.000122 peak_floor=0.002 blocks=34 captions=0',
      });
  }

  if (hash === 'dead-panel-only') {
    // The SAME status text with NO shell follow-up: what `panel.js` alone paints.
    window.sotto.setStatus(
      'Audio tap carried no signal - every candidate device was flat');
  }

  // ── the strip surface ──────────────────────────────────────────────────────
  function goStrip() {
    if (window.SottoSurfaces) window.SottoSurfaces.set('strip');
  }

  if (hash === 'strip') {
    goStrip();
    // Cold, exactly as Alt+C finds it: no caption yet, so the strip shows its
    // empty state and the placeholder is what carries the height.
  }

  if (hash === 'strip-live') {
    goStrip();
    playLiveStream();
  }

  // ── the pause confirmation ─────────────────────────────────────────────────
  function openConfirm() {
    var trigger = document.getElementById('strip-pause-button');
    if (trigger) {
      trigger.click();
      return true;
    }
    return false;
  }

  if (hash === 'pause-confirm') {
    goStrip();
    playLiveStream();
    openConfirm();
  }

  if (hash === 'pause-confirmed') {
    goStrip();
    playLiveStream();
    openConfirm();
    var confirm = document.getElementById('pause-confirm-button');
    // The button is disabled when the stub has no `pause()` — the honest state
    // of this repo — so this arm presses it only when the shell under test
    // really implements the call (i.e. under `?wired=1`).
    if (confirm && !confirm.disabled) confirm.click();
  }

  // ── the theme lane ─────────────────────────────────────────────────────────
  var THEMES = [
    { name: 'theme-1', label: '1 · Teleprompter' },
    { name: 'theme-2', label: '2 · Broadcast' },
    { name: 'theme-3', label: '3 · Manuscrito' },
    { name: 'theme-4', label: '4 · Cinema Card' },
    { name: 'theme-5', label: '5 · Instrumento' },
  ];

  if (theme) {
    // A themed preview: the theme is applied BEFORE panel.js paints.
    document.documentElement.dataset.theme = theme;
  } else if (!inert && window.SottoTheme && window.SottoTheme.current) {
    /* The BIG panel (no `theme=` in its URL) applies the STORED choice the
     * shipped way, through the module — and a five-up preview never does, so the
     * five iframes cannot each rewrite the stored key. */
    var stored = window.SottoTheme.last && window.SottoTheme.last();
    window.SottoTheme.set(stored || 'theme-1', { persist: false });
  }

  if (hash === 'themes' && !inert) {
    buildThemesPage();
  }

  /**
   * The five-up page: a toolbar that switches the LIVE panel (one attribute,
   * the real mechanism) and a row of five iframes, each a real panel wearing one
   * theme. Nothing here changes panel.js: the toolbar only ever calls
   * `window.SottoTheme.set()` or writes `documentElement.dataset.theme`, which is
   * what the shipped switcher does anyway.
   */
  function buildThemesPage() {
    document.body.dataset.surface = 'themes';

    // The HUD is the one section this page does not need, and it is panel-rendered
    // (panel.js fills it), so taking its slot is the only DOM the harness touches.
    var slot = document.getElementById('hud');

    var wrap = document.createElement('div');
    wrap.className = 'themes-wrap';

    var bar = document.createElement('div');
    bar.className = 'themes-bar';
    bar.innerHTML = '<span class="themes-bar__title">Sotto themes — five real panels</span>';

    THEMES.forEach(function (t) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'themes-bar__button';
      b.dataset.themeName = t.name;
      b.innerHTML = '<span class="themes-bar__swatch"></span><span>' + t.label + '</span>';
      b.addEventListener('click', function () { pick(t.name); });
      bar.appendChild(b);
    });

    var hint = document.createElement('span');
    hint.className = 'themes-bar__hint';
    hint.textContent = 'click a button, or press 1-5 — the big panel below switches live';
    bar.appendChild(hint);

    var row = document.createElement('div');
    row.className = 'themes-compare';

    THEMES.forEach(function (t) {
      var f = document.createElement('iframe');
      f.className = 'themes-card';
      f.title = t.label + ' — the real panel, this theme applied';
      // THE SAME DOCUMENT, the same driver, the same caption sequence: only the
      // theme differs. `inert=1` keeps the child from mounting its own picker.
      f.src = 'panel-harness.html?state=live&theme=' + t.name + '&inert=1';
      f.setAttribute('data-theme-name', t.name);
      row.appendChild(f);
    });

    wrap.appendChild(bar);
    wrap.appendChild(row);
    if (slot && slot.parentNode) {
      slot.parentNode.replaceChild(wrap, slot);
    } else {
      document.body.appendChild(wrap);
    }

    function paintBar() {
      var cur = (window.SottoTheme && window.SottoTheme.current)
        ? window.SottoTheme.current()
        : (document.documentElement.dataset.theme || '');
      var buttons = bar.querySelectorAll('.themes-bar__button');
      for (var i = 0; i < buttons.length; i += 1) {
        if (buttons[i].dataset.themeName === cur) buttons[i].setAttribute('aria-current', 'true');
        else buttons[i].removeAttribute('aria-current');
      }
    }

    function pick(name) {
      if (window.SottoTheme && window.SottoTheme.set) window.SottoTheme.set(name);
      else document.documentElement.dataset.theme = name;
      paintBar();
    }

    paintBar();
    document.addEventListener('click', function () { setTimeout(paintBar, 0); }, true);
    document.addEventListener('keydown', function (ev) {
      if (ev.target && /INPUT|TEXTAREA/.test(ev.target.tagName || '')) return;
      var i = '12345'.indexOf(ev.key);
      if (i >= 0) { pick(THEMES[i].name); return; }
      if (ev.key === 't') {
        var cur = (window.SottoTheme && window.SottoTheme.current)
          ? window.SottoTheme.current() : 'theme-1';
        var n = THEMES.map(function (x) { return x.name; });
        pick(n[(n.indexOf(cur) + 1) % n.length]);
      }
    });
  }

  // The feed/warm-up writes are asynchronous in panel.js (`history.tail()`
  // resolves a Promise); one microtask turn is enough for a deterministic shot.
  setTimeout(function () { window.__auditPublish(); }, 50);

  // ── the theme lane's machine-readable receipt ─────────────────────────────
  // A themed preview publishes what it actually applied, so the parent cannot
  // claim a theme without the child having worn it.
  setTimeout(function () {
    var el = document.createElement('div');
    el.id = '__themes';
    el.hidden = true;
    el.textContent = JSON.stringify({
      state: hash,
      askedTheme: theme || null,
      appliedTheme: document.documentElement.dataset.theme || null,
      surface: document.body.dataset.surface,
      captionLines: document.querySelectorAll('#caption-list .caption').length,
      formingLine: document.querySelectorAll('.caption--provisional').length,
      canSeeTop: true,
    });
    document.body.appendChild(el);
    if (window.parent && window.parent !== window) {
      try { window.parent.postMessage({ sottoHarness: true, receipt: JSON.parse(el.textContent) }, '*'); } catch (e) {}
    }
  }, 120);
})();
