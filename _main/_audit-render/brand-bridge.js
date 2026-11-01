/* brand-bridge.js -- the panel wears a design, and the REAL overlay wears it too
 * ===========================================================================
 * THE DEFECT THIS FILE CLOSES (owner, 2026-10-21): *"a legenda ao vivo tem que
 * aparecer no overlay real com o design"*. The panel has 45 themes; the caption
 * the owner reads across the room is NOT the panel and NOT `caption.html` -- it
 * is the native layered window in `app/webview/caption_overlay.py`, painted by
 * GDI+. A theme that only restyles `app/panel/` therefore reaches half the
 * product, and the half the owner actually watches keeps Segoe UI.
 *
 * WHAT THIS FILE DOES. It measures the theme's OWN forming row -- the real
 * computed values, after the cascade, the `--caption-scale` dial and the
 * webfont -- and posts them as one `brand-tokens` message. The shell hands the
 * object to `NativeCaptionOverlay.set_theme`; the overlay's defaults reproduce
 * the pre-brand caption exactly, so a missing message is not a regression.
 *
 * WHY A PROBE AND NOT THE LIVE ROW. At the moment a theme changes the caption
 * list may be empty (`#caption-list` starts `hidden` and is only filled when a
 * caption arrives), and the overlay must already be branded for the first line.
 * `#brand-probe` in `panel.html` carries the same nodes as a real row
 * (`.caption__led`, `.caption__time`, `.caption__text`) and is measured off
 * screen. It is never in the caption list, so `:first-child`/`:last-child` and
 * the list's own counters do not see it.
 *
 * WHY THE STRIP CAN MEASURE THE PANEL'S DESIGN. Several theme volumes scope
 * their rules to `body[data-surface="panel"]`. In the strip surface those rules
 * do not apply, so `snapshot()` flips the attribute to `panel`, forces one
 * synchronous style/layout read, and puts it back BEFORE the task yields. No
 * frame is painted in between, so nothing flickers.
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var RETRY_MS = 900;
  var timer = 0;
  var retryTimer = 0;
  var last = null;
  var lastJson = '';

  function num(value, fallback) {
    var n = parseFloat(value);
    return isFinite(n) ? n : (fallback || 0);
  }

  function alphaOf(colour) {
    var c = parseColour(colour);
    if (c) return c.a;
    return String(colour || '').trim() === 'transparent' ? 0 : 1;
  }

  function parseColour(text) {
    var s = String(text || '').trim();
    var m = /^rgba?\(([^)]*)\)/.exec(s);
    if (m) {
      var p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat);
      if (p.length < 3 || !isFinite(p[0]) || !isFinite(p[1]) || !isFinite(p[2])) {
        return null;
      }
      return {
        r: p[0], g: p[1], b: p[2],
        a: p.length > 3 ? (p[3] <= 1 ? p[3] : p[3] / 255) : 1
      };
    }
    /* CHROMIUM'S `color-mix()` COMPUTED FORM IS `color(srgb r g b / a)`, NOT
     * rgba (measured 2026-10-21: Quotes' 8% accent row resolved to
     * `color(srgb 0.909804 0.776471 0.607843 / 0.08)`). The rgba-only parser
     * returned null, `alphaOf` fell through to 1, and the native overlay drew
     * the raw accent as a SOLID TAN PLATE -- the exact "bright slab" the
     * compositing in `effectiveBg` exists to prevent. Channels here are 0..1. */
    m = /^color\(srgb\s+([^)]*)\)/.exec(s);
    if (m) {
      var q = m[1].split(/[\s\/]+/).filter(Boolean);
      if (q.length < 3) return null;
      var ch = [parseFloat(q[0]), parseFloat(q[1]), parseFloat(q[2])];
      if (!isFinite(ch[0]) || !isFinite(ch[1]) || !isFinite(ch[2])) {
        return null;
      }
      var a = 1;
      if (q.length > 3) {
        a = parseFloat(q[3]);
        if (q[3].indexOf('%') >= 0) a /= 100;
        if (!isFinite(a)) a = 1;
      }
      return { r: ch[0] * 255, g: ch[1] * 255, b: ch[2] * 255, a: a };
    }
    if (s === 'transparent') return { r: 0, g: 0, b: 0, a: 0 };
    return null;
  }

  /* THE ROW'S BACKGROUND IS A GESTURE OVER THE PANEL, NOT A COLOUR. GlassCards
   * paints `rgba(255,222,180,0.07)` -- a 7% warm wash. Handing those RGB
   * numbers to GDI+ with a legibility floor produced a BRIGHT TAN SLAB, which is
   * the opposite of what the panel shows (the wash over a near-black column is
   * a very dark brown). So the bridge composites the row over the panel's own
   * background and sends the RESULT; the alpha travels separately as the
   * overlay's own opacity. */
  function panelBase() {
    var el = document.querySelector('main.panel') || document.body;
    var c = el ? parseColour(window.getComputedStyle(el).backgroundColor) : null;
    return (c && c.a > 0.5) ? [c.r, c.g, c.b] : [16, 11, 8];
  }

  function effectiveBg(colour, base) {
    var c = parseColour(colour);
    if (!c) return colour;
    var out = [];
    var channels = [c.r, c.g, c.b];
    for (var i = 0; i < 3; i += 1) {
      out.push(Math.round(channels[i] * c.a + base[i] * (1 - c.a)));
    }
    return 'rgb(' + out.join(', ') + ')';
  }

  function leadingOf(cs) {
    var size = num(cs.fontSize, 1) || 1;
    var line = cs.lineHeight;
    if (!line || line === 'normal') return 1.35;
    var px = num(line, 0);
    if (!px) return 1.35;
    return Math.max(0.9, Math.min(2.6, px / size));
  }

  function readText(row) {
    if (!row) return null;
    var text = row.querySelector('.caption__text');
    if (!text) return null;
    var ts = window.getComputedStyle(text);
    var style = ts.fontStyle || 'normal';
    return {
      fontFamily: ts.fontFamily,
      px: num(ts.fontSize, 13),
      leading: leadingOf(ts),
      weight: parseInt(ts.fontWeight, 10) || 400,
      italic: style.indexOf('italic') >= 0 || style.indexOf('oblique') >= 0,
      upper: (ts.textTransform || '') === 'uppercase',
      colour: ts.color,
      align: ts.textAlign || 'start',
      tracking: (ts.letterSpacing && ts.letterSpacing !== 'normal') ?
        ts.letterSpacing : 'normal'
    };
  }

  function readRow(row) {
    if (!row) return null;
    var cs = window.getComputedStyle(row);
    var led = row.querySelector('.caption__led');
    var ledState = { visible: false, colour: '' };
    if (led) {
      var ls = window.getComputedStyle(led);
      var w = num(ls.width, 0);
      var h = num(ls.height, 0);
      var bg = ls.backgroundColor || '';
      ledState = {
        visible: ls.display !== 'none' && ls.visibility !== 'hidden' &&
          num(ls.opacity, 1) > 0.05 && w > 0.5 && h > 0.5 && alphaOf(bg) > 0.02,
        colour: bg
      };
    }
    return {
      text: readText(row),
      bg: cs.backgroundColor,
      bgImage: cs.backgroundImage || 'none',
      radius: num(cs.borderTopLeftRadius, 0),
      pad: [num(cs.paddingTop), num(cs.paddingRight),
            num(cs.paddingBottom), num(cs.paddingLeft)],
      ruleW: (cs.borderLeftStyle === 'none' ? 0 : num(cs.borderLeftWidth, 0)),
      ruleColour: cs.borderLeftColor,
      led: ledState
    };
  }

  function measure() {
    var probe = document.getElementById('brand-probe');
    if (!probe) return null;
    var body = document.body;
    var original = body && body.getAttribute('data-surface');
    var flipped = !!(body && original && original !== 'panel');
    if (flipped) body.setAttribute('data-surface', 'panel');
    var liveRow = probe.querySelector('.caption--provisional');
    var prevRow = probe.querySelector('.caption--latest');
    var live = readRow(liveRow);
    var prev = readRow(prevRow);
    /* THE BASE IS READ WHILE THE PANEL SURFACE IS ACTIVE: in the strip the
     * panel's background is styled by a different rule, and compositing the row
     * over the strip's colours would give the overlay a plate the panel never
     * wears. */
    var panelEl = document.querySelector('main.panel');
    var panelStyle = panelEl ? window.getComputedStyle(panelEl) : null;
    /* CSSStyleDeclaration IS LIVE. Reading `panelStyle.background` after the
     * surface is restored returns the STRIP's slab, which is the very rule this
     * measurement exists to see past (measured 2026-10-21: the bridge copied
     * the base gradient back onto the bar, so every theme still shipped with the
     * same dark strip while the panel was themed). Snapshot the strings while
     * the panel surface is still active. */
    var panelBg = panelStyle ? panelStyle.background : '';
    var panelBgColor = panelStyle ? panelStyle.backgroundColor : '';
    var panelBgImage = panelStyle ? panelStyle.backgroundImage : 'none';
    var base = panelBase();
    if (flipped) body.setAttribute('data-surface', original);
    if (!live || !live.text) return null;
    var prevText = prev && prev.text;
    var liveAlpha = alphaOf(live.bg);
    var tokens = {
      theme: (root.dataset && root.dataset.theme) || '',
      fontFamily: live.text.fontFamily,
      panelLivePx: live.text.px,
      liveLeading: live.text.leading,
      liveWeight: live.text.weight,
      liveItalic: live.text.italic,
      liveUpper: live.text.upper,
      liveColor: live.text.colour,
      liveTracking: live.text.tracking,
      textAlign: live.text.align,
      panelPrevPx: prevText ? prevText.px : live.text.px * 0.72,
      prevLeading: prevText ? prevText.leading : 1.35,
      prevWeight: prevText ? prevText.weight : live.text.weight,
      prevItalic: prevText ? prevText.italic : false,
      prevUpper: prevText ? prevText.upper : false,
      prevColor: prevText ? prevText.colour : live.text.colour,
      prevTracking: prevText ? prevText.tracking : 'normal',
      rowBg: liveAlpha > 0.02 ? effectiveBg(live.bg, base) : live.bg,
      rowBgAlpha: liveAlpha > 0.02 ? Math.max(liveAlpha, 0.55) : 0,
      rowBgImage: live.bgImage,
      rowRadius: live.radius,
      panelPad: live.pad,
      panelRuleW: live.ruleW,
      ruleColor: live.ruleColour,
      ledVisible: live.led.visible,
      ledColor: live.led.colour,
      /* THE SLAB ITSELF, so the strip bar can wear the same background the
       * right panel wears. Captured in the panel surface (above) because the
       * strip rule paints its own slab. */
      panelBgColor: panelBgColor,
      panelBgImage: panelBgImage,
      panelBg: panelBg
    };
    return tokens;
  }

  function px(value, fallback) {
    return (isFinite(value) ? value : (fallback || 0)) + 'px';
  }

  /* THE SAME DESIGN ON THE BOTTOM SURFACES. The native overlay is the shell's
   * window; this paint is the page's own float and strip bar. Tokens are
   * resolved here once, so `caption-float.css` and the strip rules never
   * re-derive a size the panel already decided. */
  function paint(tokens) {
    var s = root.style;
    /* THE FLOAT IS READ FROM 1-2 m AT A 1040 px BOTTOM BAND, NOT FROM THE 1920 px
     * SCREEN. The native overlay uses 1.85x the panel; the float used 2.2x and
     * clamped at 44, and the fresh 2026-10-21 sheet showed `cine-reading-hour`
     * wrapping its 58-character line to THREE lines at 44 px in a 220 px window,
     * with the last line under the plate. 1.8x (clamp 20-38) keeps the same
     * hierarchy as the native renderer and fits two lines plus the credits. */
    var live = Math.max(20, Math.min(38, tokens.panelLivePx * 1.8));
    var prev = Math.max(13, Math.min(30, tokens.panelPrevPx * 1.5));
    var pad = tokens.panelPad || [10, 12, 10, 12];
    var ruleW = Math.max(0, tokens.panelRuleW * 2);
    var plate = 'transparent';
    var c = parseColour(tokens.rowBg);
    if (c && tokens.rowBgAlpha > 0.02) {
      plate = 'rgba(' + Math.round(c.r) + ', ' + Math.round(c.g) + ', ' +
        Math.round(c.b) + ', ' + Number(tokens.rowBgAlpha).toFixed(3) + ')';
    }
    if (tokens.theme) root.dataset.brand = tokens.theme;
    s.setProperty('--brand-font', tokens.fontFamily);
    s.setProperty('--brand-live-size', px(live));
    s.setProperty('--brand-live-weight', String(tokens.liveWeight || 400));
    s.setProperty('--brand-live-leading', String(tokens.liveLeading || 1.35));
    s.setProperty('--brand-live-tracking', tokens.liveTracking || 'normal');
    s.setProperty('--brand-live-style', tokens.liveItalic ? 'italic' : 'normal');
    s.setProperty('--brand-live-color', tokens.liveColor || '#fff');
    s.setProperty('--brand-live-upper', tokens.liveUpper ? 'uppercase' : 'none');
    s.setProperty('--brand-prev-size', px(prev));
    s.setProperty('--brand-prev-weight', String(tokens.prevWeight || 400));
    s.setProperty('--brand-prev-leading', String(tokens.prevLeading || 1.35));
    s.setProperty('--brand-prev-tracking', tokens.prevTracking || 'normal');
    s.setProperty('--brand-prev-style', tokens.prevItalic ? 'italic' : 'normal');
    s.setProperty('--brand-prev-color', tokens.prevColor || 'rgba(255,255,255,.7)');
    s.setProperty('--brand-prev-upper', tokens.prevUpper ? 'uppercase' : 'none');
    s.setProperty('--brand-align', tokens.textAlign === 'center' ? 'center' : 'left');
    s.setProperty('--brand-plate', plate);
    s.setProperty('--brand-rule', tokens.ruleColor || 'transparent');
    s.setProperty('--brand-rule-w', px(ruleW));
    s.setProperty('--brand-radius', px(Math.max(0, tokens.rowRadius || 0) * 1.5));
    s.setProperty('--brand-pad-top', px(Math.max(8, pad[0] * 1.5)));
    s.setProperty('--brand-pad-right', px(Math.max(10, pad[1] * 1.5)));
    s.setProperty('--brand-pad-bottom', px(Math.max(8, pad[2] * 1.5)));
    s.setProperty('--brand-pad-left', px(Math.max(10, pad[3] * 1.5)));
    s.setProperty('--brand-panel-color', tokens.panelBgColor || '#0b0f14');
    s.setProperty('--brand-panel-image', tokens.panelBgImage || 'none');
    s.setProperty('--brand-panel', tokens.panelBg ||
      'rgba(11, 15, 20, 0.98)');
    s.setProperty('--brand-led', (tokens.ledVisible && tokens.ledColor) ?
      tokens.ledColor : 'transparent');
  }

  function snapshot() {
    try {
      return skinTokens() || measure();
    } catch (err) {
      return null;
    }
  }

  /* THE CINEMATIC SKINS OWN THE VISIBLE LIVE LINE. `skin-host.js` hides the stock
   * caption list (`body[data-skin]`) and mounts the zip's own caption fragment in
   * a shadow root; the stock probe then measures a HIDDEN row and the native
   * overlay gets the base Segoe UI instead of the design (measured 2026-10-21:
   * cine-blue-hour native still was Segoe UI 24 px while the skin's live line was
   * Inter 300 at 22.5 px). When a skin is active, read the forming word and its
   * containing caption fragment instead. The surface (`--surface`, applied to
   * body by skin-host) is what the bottom strip must wear. */
  function skinTokens() {
    var skin = window.SottoSkin;
    if (!skin || !skin.active || typeof skin.slots !== 'function') return null;
    var slots = skin.slots() || {};
    var host = slots.wordHost;
    if (!host) return null;
    var word = host.querySelector('.word-in') || host.querySelector('span');
    if (!word) return null;
    var ws = window.getComputedStyle(word);
    var hs = window.getComputedStyle(host);
    var style = ws.fontStyle || 'normal';
    var livePx = num(ws.fontSize, 22);
    var bg = 'transparent';
    var bgImage = 'none';
    var ruleW = 0;
    var ruleColour = 'transparent';
    var radius = 0;
    var pad = [0, 0, 0, 0];
    /* THE CAPTION FRAGMENT'S OWN PLATE/RULE. Most cinematic captions paint only
     * ink over the stage, but a few carry a translucent card; walk up to the
     * first ancestor that actually paints and take its computed values. */
    var box = host;
    for (var i = 0; i < 4 && box; i += 1) {
      var bs = window.getComputedStyle(box);
      if (alphaOf(bs.backgroundColor) > 0.02 ||
          (bs.backgroundImage && bs.backgroundImage !== 'none') ||
          num(bs.borderLeftWidth, 0) > 0) {
        bg = bs.backgroundColor;
        bgImage = bs.backgroundImage || 'none';
        ruleW = (bs.borderLeftStyle === 'none' ? 0 : num(bs.borderLeftWidth));
        ruleColour = bs.borderLeftColor;
        radius = num(bs.borderTopLeftRadius, 0);
        pad = [num(bs.paddingTop), num(bs.paddingRight),
               num(bs.paddingBottom), num(bs.paddingLeft)];
        break;
      }
      box = box.parentElement;
    }
    var base = panelBase();
    var alpha = alphaOf(bg);
    var surface = window.getComputedStyle(document.body)
      .getPropertyValue('--surface').trim();
    return {
      theme: (root.dataset && root.dataset.theme) || '',
      fontFamily: ws.fontFamily,
      panelLivePx: livePx,
      liveLeading: leadingOf(ws),
      liveWeight: parseInt(ws.fontWeight, 10) || 400,
      liveItalic: style.indexOf('italic') >= 0 || style.indexOf('oblique') >= 0,
      liveUpper: (ws.textTransform || '') === 'uppercase',
      liveColor: ws.color,
      liveTracking: (ws.letterSpacing && ws.letterSpacing !== 'normal') ?
        ws.letterSpacing : 'normal',
      textAlign: ws.textAlign || 'start',
      panelPrevPx: livePx * 0.72,
      prevLeading: leadingOf(hs),
      prevWeight: parseInt(ws.fontWeight, 10) || 400,
      prevItalic: false,
      prevUpper: false,
      prevColor: ws.color,
      prevTracking: 'normal',
      rowBg: alpha > 0.02 ? effectiveBg(bg, base) : bg,
      rowBgAlpha: alpha > 0.02 ? Math.max(alpha, 0.55) : 0,
      rowBgImage: bgImage,
      rowRadius: radius,
      panelPad: pad,
      panelRuleW: ruleW,
      ruleColor: ruleColour,
      ledVisible: false,
      ledColor: 'transparent',
      panelBg: surface || '',
      panelBgColor: surface || '',
      panelBgImage: 'none'
    };
  }

  function push() {
    timer = 0;
    var tokens = snapshot();
    if (!tokens) return;
    var json = JSON.stringify(tokens);
    /* A theme repaint that resolves to the same values must not repaint the
     * overlay; `_update` is cheap but it is still a layered-window blit. */
    if (json === lastJson) return;
    last = tokens;
    lastJson = json;
    paint(tokens);
    var bridge = window.sotto;
    if (!bridge || typeof bridge.dispatch !== 'function') {
      schedule(RETRY_MS);
      return;
    }
    try {
      bridge.dispatch('brand-tokens', tokens);
    } catch (err) {
      schedule(RETRY_MS);
    }
  }

  function schedule(delay) {
    var ms = typeof delay === 'number' ? delay : 120;
    if (timer) clearTimeout(timer);
    timer = setTimeout(push, ms);
  }

  /* A theme change can be a two-step fact: the attribute flips now, and a lazy
   * theme sheet (or a webfont) arrives 100-600 ms later. One early read catches
   * the fast volumes; one late read catches the deferred ones.
   *
   * THE LATE READS ARE NOT OPTIONAL (measured 2026-10-21 in the audit harness,
   * boot theme `theme-1`, runtime theme `pd-tele`): the attribute flipped at
   * 500 ms, the 120 ms read still resolved `theme-1` (the lazy sheet had not
   * arrived), so the tokens equaled `lastJson` and `push` returned WITHOUT a
   * paint. The single 900 ms retry fired before the sheet too. At 6.5 s the
   * snapshot was correctly `pd-tele` (Barlow Condensed, 600, upright) while the
   * float still wore `theme-1`'s Segoe UI italic -- the native overlay would
   * have kept the previous design for the same reason. A local stylesheet can
   * land after either probe, and a sheet insertion fires no attribute
   * mutation, so the bridge schedules its own two later reads. */
  var lateTimers = [];

  function scheduleTheme() {
    schedule(120);
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = setTimeout(push, RETRY_MS);
    for (var i = 0; i < lateTimers.length; i += 1) clearTimeout(lateTimers[i]);
    lateTimers = [setTimeout(push, 1800), setTimeout(push, 3600),
                  setTimeout(push, 5200)];
  }

  if (window.MutationObserver) {
    new window.MutationObserver(scheduleTheme).observe(root, {
      attributes: true,
      attributeFilter: ['data-theme', 'style', 'class']
    });
  }
  window.addEventListener('resize', scheduleTheme);
  window.addEventListener('load', scheduleTheme);
  if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
    document.fonts.ready.then(scheduleTheme);
  }

  window.SottoBrand = {
    snapshot: snapshot,
    push: scheduleTheme,
    last: function () { return last; }
  };

  /* Boot: after the first paint, and once more after the deferred sheets. */
  schedule(0);
  scheduleTheme();
}());
