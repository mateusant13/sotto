/* Sotto — THE PER-THEME CHROME PROBE.
 *
 * WHAT IT IS FOR. The contract changed on 2026-10-08. Until then a theme
 * re-skinned colour, type and surface and shared ONE header and ONE footer with
 * the other four; the owner asked for the opposite, verbatim: *"quero que voce
 * monte o painel super parecido com cada tema. pode ate mudar botoes de lugar, se
 * quiser. nao quero a cara do design que tinhamos antes."* So the claim under
 * test is no longer "the theme applied" (that is `_main/_theme-probe.js`) but
 * "EACH DIRECTION HAS ITS OWN HEADER, ITS OWN FOOTER, ITS OWN INDICATOR, AND ITS
 * OWN PLACE FOR THE CONTROLS — and the theme button is still reachable in all
 * five, on BOTH surfaces."
 *
 * A class changing proves nothing here, so every assertion is read from
 * `getComputedStyle` and `getBoundingClientRect` of the LIVE document after the
 * REAL `panel.js` has rendered REAL captions through the stub bridge
 * (`_main/_audit-render/stub.js`, the same one the audit harness uses). That
 * matters for three of the four behaviours this lane added:
 *
 *   * the per-line ORDINAL is written by `panel.js` (`pad3(lineOrdinal)`), so it
 *     can only be measured by driving the real renderer;
 *   * the per-word CONTRAST RAMP is `--w-op` on spans `panel.js` creates, so a
 *     hand-built fixture would be testing the probe's own arithmetic;
 *   * the `inst` LED is an element `panel.js` appends to the forming row.
 *
 * THE MOCKUPS ARE THE EXPECTED SIDE, and they are quoted from
 * `H:\aireplay\docs\design\sotto-app-design-directions\src\components\Panel.tsx`
 * and `...\sotto-transcription-panel-designs\src\components\panels.tsx`:
 *
 *   tele  SOTTO / LENDO              footer HISTÓRICO … ▲ EM CURSO
 *   bcast ● REC  CH·01   HH:MM:SS    footer meter … AO VIVO      + per-line index
 *   mano  rascunho ao vivo / pág. 1  footer — escrito ao ouvido   + contrast ramp
 *   cine  SOTTO / · ao vivo ·        footer · · ·                + forming fog
 *   inst  ■ ON / ALT+C               footer meter OUVINDO …      + breathing LED
 *
 * ── HOW IT GETS OUT, WITHOUT TOUCHING THE SHELL ──────────────────────────────
 * `app/webview/sotto_webview.py` is NOT edited (this lane's brief forbids it) and
 * it owns the `--dump-dom` probe, so the payload is written into the DOM as
 * ATTRIBUTES on a probe element (`data-chrome-probe-count` / `data-chrome-probe-N`,
 * one JSON document per theme) and read back out of the DOM the run dumps. That
 * is the pattern `_main/_theme-probe.js` already established.
 *
 * WHERE IT LOADS. Never in the shipped panel: `_main/_panel-chrome-arm.py` writes
 * a COPY of `app/panel/panel.html` into a temp directory, points every asset URL
 * at the real files, inserts the stub bridge before `panel.js` and appends THIS
 * file after it. `app/panel/panel.html` does not mention it.
 *
 * THE OPS (via `location.hash`):
 *   #mode=chrome            all five directions, both surfaces (the real arm)
 *   #mode=chrome&theme=theme-3   one theme only (used by the control arm)
 *
 * ── WHY IT IS LOADED BEFORE `panel.js`, AND WHAT IT DOES WITH THAT ───────────
 * `data-state` is what lights a direction's state word, and the only code that
 * writes it is `panel.js`'s `setStatus`. In the app the shell drives that with
 * `{text, kind:'live'}`; the audit stub emits a BARE STRING, which the panel
 * correctly reads as a neutral state. So the probe CAPTURES the panel's own
 * `onStatus` callback on its way in (the stub's `onStatus` is wrapped at parse
 * time, before `panel.js` subscribes) and later hands that callback the payload
 * the REAL shell sends. The panel's own handler then does everything it does in
 * the app — including the `engine.flush('status-change')` that commits the held
 * line, which is how a committed row exists to carry the ordinal. Nothing here
 * writes `data-state` itself.
 */

(function () {
  'use strict';

  /* ── THE CAPTURE, at parse time, before `panel.js` subscribes ───────────── */
  var statusCallbacks = [];
  (function captureStatus() {
    var bridge = window.sotto;
    if (!bridge || typeof bridge.onStatus !== 'function') return;
    var original = bridge.onStatus;
    bridge.onStatus = function (cb) {
      if (typeof cb === 'function') statusCallbacks.push(cb);
      return original.call(bridge, cb);
    };
  }());

  /** Hand the panel's OWN status handler the payload the REAL shell sends. */
  function emitStatus(text, kind) {
    if (!statusCallbacks.length) return false;
    for (var i = 0; i < statusCallbacks.length; i += 1) {
      statusCallbacks[i]({ text: text, kind: kind });
    }
    return true;
  }

  /* The five directions, in the owner's order, with the theme each one is.
   * Kept here as the EXPECTED side: a probe that reads its expectation out of
   * the thing it is testing cannot fail.
   *
   * UPDATED 2026-10-08 WITH THE OWNER'S OWN WORDS, and the reason this table had
   * to move TWICE is worth keeping: the ARM (`_panel-chrome-arm.py`) keeps its own
   * `EXPECTED` table, and this probe kept a second copy. Updating only the arm left
   * four RED problems whose messages named the PANEL while the disagreement was
   * between two copies of the expectation — the probe matched `'AO VIVO'`,
   * `'rascunho ao vivo'` and `'SOTTO'`, all three of which the owner had changed.
   *   * `bcast`'s footer says `LIVE` (was `AO VIVO`);
   *   * `mano`'s header says `rascunho live` (was `rascunho ao vivo`);
   *   * `cine`'s header says `sotto`, LOWERCASE (was `SOTTO`), and its state word
   *     is `· live ·` (was `· ao vivo ·`).
   * `headWord` for `cine` is the NAME now, not a state word: the direction's header
   * leads with the brand, so that is what the header check must find there. */
  var DIRS = [
    { id: 'tele', theme: 'theme-1', label: 'Teleprompter', headWord: 'LENDO', stateWord: 'LENDO', foot: '▲ EM CURSO' },
    { id: 'bcast', theme: 'theme-2', label: 'Broadcast', headWord: 'REC', stateWord: 'REC', foot: 'LIVE' },
    { id: 'mano', theme: 'theme-3', label: 'Manuscrito', headWord: 'rascunho live', stateWord: 'rascunho live', foot: '— escrito ao ouvido' },
    { id: 'cine', theme: 'theme-4', label: 'Cinema Card', headWord: 'sotto', stateWord: '· live ·', foot: '· · ·' },
    { id: 'inst', theme: 'theme-5', label: 'Instrumento', headWord: 'ON', stateWord: 'ON', foot: 'OUVINDO' }
  ];

  var REPORT = { errors: [], themes: [], surface: {}, viewport: [innerWidth, innerHeight] };

  function hashParam(name) {
    var m = new RegExp('[#&]' + name + '=([^&]*)').exec(String(location.hash || ''));
    return m ? decodeURIComponent(m[1]) : '';
  }

  function err(message) {
    REPORT.errors.push(String(message));
    try {
      throw new Error('SOTTO_CHROME_PROBE ' + message);
    } catch (e) {
      /* The only way a page can push to the shell's `page-error` channel. */
      setTimeout(function () { throw e; }, 0);
    }
  }

  function rect(el) {
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)];
  }

  function cs(el) { return el ? getComputedStyle(el) : null; }

  /* "Shown" is THREE facts, not one: `display` is not `none`, nothing up the tree
   * hides it, and it occupies a real box. A rule that sets `display: flex` on an
   * element whose parent is `display: none` has changed a class, not a pixel. */
  function shown(el) {
    if (!el) return false;
    var c = cs(el);
    if (c.display === 'none' || c.visibility === 'hidden' || parseFloat(c.opacity) === 0) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function overlap(a, b) {
    if (!a || !b) return false;
    return !(a[0] + a[2] <= b[0] || b[0] + b[2] <= a[0] ||
      a[1] + a[3] <= b[1] || b[1] + b[3] <= a[1]);
  }

  function push(text, start, end, final) {
    if (!window.sotto || typeof window.sotto.pushCaption !== 'function') return;
    window.sotto.pushCaption(text, { start: start, end: end, final: Boolean(final) });
  }

  function setTheme(name) {
    if (window.SottoTheme && typeof window.SottoTheme.set === 'function') {
      window.SottoTheme.set(name, { persist: false });
    }
    document.documentElement.setAttribute('data-theme', name);
  }

  /** Alpha of a computed colour, or null when it is not a colour at all.
   *
   * THREE SYNTAXES, and the first version only knew one of them: `rgba(r, g, b, a)`,
   * the modern `rgb(r g b / a)` (and `color(srgb … / a)`, `oklab(… / a)`, which is
   * what this Chromium actually computes for `color-mix()`), and the bare
   * `transparent`. The first run reported `alphaBody could not be read` for a
   * value that was plainly 0.55 — the instrument was blind, not the panel opaque.
   */
  function alpha(color) {
    var s = String(color == null ? '' : color).trim();
    if (!s) return null;
    if (s === 'transparent') return 0;
    var slash = /\/(\s*[\d.]+%?\s*)\)\s*$/.exec(s);
    if (slash) {
      var v = parseFloat(slash[1]);
      return /%\s*$/.test(slash[1]) ? v / 100 : v;
    }
    var commas = /^(?:rgba|hsla)\(([^)]+)\)$/.exec(s);
    if (commas) {
      var parts = commas[1].split(',');
      return parts.length < 4 ? 1 : parseFloat(parts[3]);
    }
    if (/^(?:rgb|hsl|oklab|oklch|lab|lch|color)\(/.test(s)) return 1;
    return null;
  }

  /** The RGB triple, so "is this yellow" can be answered without guessing.
   *  `color(srgb …)` and `oklab(…)` are converted from their own components; the
   *  probe must not claim "not yellow" for a colour it could not parse. */
  function rgb(color) {
    var s = String(color == null ? '' : color).trim();
    var m = /^rgba?\(([^)]+)\)$/.exec(s);
    if (m) {
      var p = m[1].split(/[,\s\/]+/).filter(function (x) { return x !== ''; });
      return [parseFloat(p[0]), parseFloat(p[1]), parseFloat(p[2])];
    }
    m = /^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/.exec(s);
    if (m) return [parseFloat(m[1]) * 255, parseFloat(m[2]) * 255, parseFloat(m[3]) * 255];
    return null;
  }

  /** Every button the PANEL surface shows, and whether it sits in the header. */
  function buttonReport() {
    var out = [];
    /* TWO GROUPS, and the difference is the owner's own wording: "move todos os
     * botoes la pra cima" is about the PANEL'S CONTROLS (Clear, Quit, Hide, Pause
     * and the theme button). The transcript DRAWER's own tools (its toggle, the
     * folder path, the search buttons) belong to the drawer and stay in it — a
     * search field dragged into the title bar would be a worse panel, not a
     * cleaner one. Both groups are reported; only the first is asserted. */
    var cluster = document.querySelectorAll('.panel__controls button');
    var others = document.querySelectorAll('.panel button, .panel__header button');
    var seen = [];
    for (var i = 0; i < others.length; i += 1) {
      if (seen.indexOf(others[i]) >= 0) continue;
      seen.push(others[i]);
      var r = others[i].getBoundingClientRect();
      out.push({
        id: others[i].id || others[i].className,
        shown: r.width > 0 && r.height > 0,
        inCluster: Boolean(others[i].closest('.panel__controls')),
        inHeader: Boolean(others[i].closest('.panel__header')),
        top: Math.round(r.top),
        appRegion: cs(others[i]).webkitAppRegion || cs(others[i]).getPropertyValue('-webkit-app-region')
      });
    }
    out.clusterCount = cluster.length;
    return out;
  }

  /** Does ANY visible text or tooltip in the document name the shortcut? */
  function shortcutMentions() {
    var hits = [];
    var re = /alt\s*\+\s*c/i;
    var walker = document.createTreeWalker(document.body, 4 /* TEXT_NODE */, null, false);
    var node;
    while ((node = walker.nextNode())) {
      if (re.test(node.nodeValue || '')) hits.push('text:' + String(node.nodeValue).trim().slice(0, 40));
    }
    var titled = document.querySelectorAll('[title]');
    for (var i = 0; i < titled.length; i += 1) {
      if (re.test(titled[i].getAttribute('title') || '')) {
        hits.push('title:' + (titled[i].id || titled[i].className));
      }
    }
    if (re.test(document.body.innerHTML || '')) hits.push('markup');
    return hits;
  }

  /* ── ONE THEME, MEASURED ────────────────────────────────────────────────── */
  function measure(dir, base) {
    var heads = document.querySelectorAll('.chrome--' + dir.id + '[data-chrome="head"]');
    var head = heads[0] || null;
    var headC = cs(head);

    /* WHICH HEADER IS SHOWN, and how many. "Exactly one" is the contract: five
     * blocks coexist in one document, and two visible headers would mean two
     * directions are claiming the same slab. */
    var shownHeads = [];
    for (var i = 0; i < DIRS.length; i += 1) {
      var el = document.querySelector('.chrome--' + DIRS[i].id + '[data-chrome="head"]');
      if (shown(el)) shownHeads.push(DIRS[i].id);
    }

    var footStart = document.querySelector('.chrome--' + dir.id + '[data-chrome="foot"][data-slot="start"]');
    var footEnd = document.querySelector('.chrome--' + dir.id + '[data-chrome="foot"][data-slot="end"]');
    var shownFeet = [];
    var feet = document.querySelectorAll('.chrome[data-chrome="foot"]');
    for (var f = 0; f < feet.length; f += 1) {
      if (shown(feet[f])) shownFeet.push(String(feet[f].className));
    }

    var stateOn = head ? head.querySelector('.chrome__on') : null;
    var stateOff = head ? head.querySelector('.chrome__off') : null;
    var stateShown = shown(stateOn) ? String(stateOn.textContent) : (shown(stateOff) ? String(stateOff.textContent) : null);

    /* The line `panel.js` really rendered: the forming row and the LAST row the
     * panel closed. The ordinals of every row in the box are read too, because
     * the claim "the ordinal is monotonic and the forming row is the next one" is
     * about the whole list, not about one row. */
    var forming = document.querySelector('#caption-list .caption--provisional');
    var allRows = document.querySelectorAll('#caption-list .caption');
    var committed = null;
    var ordinals = [];
    for (var r = 0; r < allRows.length; r += 1) {
      ordinals.push(String(allRows[r].getAttribute('data-index') || ''));
      if (!allRows[r].classList.contains('caption--provisional')) committed = allRows[r];
    }
    var lastCommitted = null;
    for (var q = ordinals.length - 1; q >= 0; q -= 1) {
      if (!allRows[q].classList.contains('caption--provisional')) {
        lastCommitted = ordinals[q];
        break;
      }
    }
    var index = forming ? forming.querySelector('.caption__index') : null;
    var liveTime = forming ? forming.querySelector('.caption__time') : null;
    var pastTime = committed ? committed.querySelector('.caption__time') : null;
    var meterBar = document.querySelector('.chrome--' + dir.id + ' .chrome__meter i');
    var buttons = buttonReport();
    var led = forming ? forming.querySelector('.caption__led') : null;
    var ledC = cs(led);
    var textEl = forming ? forming.querySelector('.caption__text') : null;
    var tailEl = forming ? forming.querySelector('.caption__provisional') : null;
    var confirmedEl = forming ? forming.querySelector('.caption__confirmed') : null;

    var words = [];
    var wordSpans = forming ? forming.querySelectorAll('.caption__word') : [];
    for (var w = 0; w < wordSpans.length; w += 1) {
      words.push({
        text: String(wordSpans[w].textContent),
        op: String(wordSpans[w].style.getPropertyValue('--w-op') || ''),
        i: String(wordSpans[w].style.getPropertyValue('--w-i') || ''),
        n: String(wordSpans[w].style.getPropertyValue('--w-n') || ''),
        computedOpacity: cs(wordSpans[w]).opacity,
        transitionProperty: cs(wordSpans[w]).transitionProperty,
        transitionDuration: cs(wordSpans[w]).transitionDuration
      });
    }

    /* THE RAMP, AS A PROPERTY: the newest word carries the most contrast and no
     * word is brighter than the one after it. Read from the numbers `panel.js`
     * wrote, so this cannot be satisfied by a probe's own arithmetic. */
    var ops = words.map(function (x) { return parseFloat(x.op); }).filter(function (v) { return isFinite(v); });
    var rampMonotonic = true;
    for (var k = 1; k < ops.length; k += 1) if (ops[k] < ops[k - 1] - 1e-6) rampMonotonic = false;
    var rampTop = ops.length ? Math.max.apply(null, ops) : null;
    var rampBottom = ops.length ? Math.min.apply(null, ops) : null;

    /* THE NAME, COUNTED OVER RENDERED ELEMENTS ONLY — computed here so the report
     * below can use it twice (the text and the count) without an IIFE that cannot
     * see its own sibling. */
    var headerTextPainted = (function () {
      var h = document.querySelector('.panel__header');
      if (!h) return '';
      var out = '';
      (function walk(node) {
        var kids = node.childNodes;
        for (var z = 0; z < kids.length; z += 1) {
          var nd = kids[z];
          if (nd.nodeType === 3) { out += nd.data; continue; }
          if (nd.nodeType !== 1) continue;
          if (!shown(nd)) continue;
          walk(nd);
        }
      }(h));
      return out.replace(/\s+/g, ' ').trim();
    }());
    var brandEl = document.querySelector('.panel__header .chrome__brand')
      || document.querySelector('.panel__header .wordmark__name');

    var meterBars = head ? [] : [];
    var meters = document.querySelectorAll('.chrome--' + dir.id + ' .chrome__meter i');
    for (var b = 0; b < meters.length; b += 1) {
      meterBars.push(String(cs(meters[b]).animationName));
    }

    var controls = document.querySelector('.panel__controls');
    var statusText = document.getElementById('status-text');
    var hudActions = document.querySelector('.hud__actions');
    var themeButton = document.getElementById('theme-button');
    var wordmark = document.querySelector('.wordmark');

    return {
      id: dir.id,
      theme: dir.theme,
      label: dir.label,
      rootAttribute: String(document.documentElement.getAttribute('data-theme')),
      bodyState: String(document.body.getAttribute('data-state') || ''),

      headShown: shown(head),
      headCount: heads.length,
      shownHeads: shownHeads,
      headRect: rect(head),
      headFamily: headC ? headC.fontFamily.replace(/["']/g, '').split(',')[0].trim() : null,
      headSize: headC ? headC.fontSize : null,
      headLetterSpacing: headC ? headC.letterSpacing : null,
      headTransform: headC ? headC.textTransform : null,
      headText: head ? String(head.textContent).replace(/\s+/g, ' ').trim() : null,
      headHasExpectedWord: head ? String(head.textContent).indexOf(dir.headWord) >= 0 : false,
      stateWordShown: stateShown,
      stateWordIsExpected: stateShown === dir.stateWord,

      /* The wordmark: `tele` and `cine` keep it (the direction's header is
       * `SOTTO` + a state word, split between the brand and the chrome line);
       * `bcast`, `mano` and `inst` replace it with their own line. */
      wordmarkShown: shown(wordmark),
      wordmarkText: wordmark ? String(wordmark.textContent).replace(/\s+/g, ' ').trim() : null,

      footStartShown: shown(footStart),
      footEndShown: shown(footEnd),
      footStartText: footStart ? String(footStart.textContent).replace(/\s+/g, ' ').trim() : null,
      footEndText: footEnd ? String(footEnd.textContent).replace(/\s+/g, ' ').trim() : null,
      footEndHasExpectedWord: footEnd ? String(footEnd.textContent).indexOf(dir.foot) >= 0 : false,
      footStartOrder: footStart ? cs(footStart).order : null,
      footEndOrder: footEnd ? cs(footEnd).order : null,
      shownFeet: shownFeet,

      /* WHERE THE CONTROLS SIT, and the two boxes they must not sit on. */
      controlsRect: rect(controls),
      controlsShown: shown(controls),
      controlsOverlapsStatus: overlap(rect(controls), rect(statusText)),
      controlsOverlapsHud: overlap(rect(controls), rect(hudActions)),
      statusTextRect: rect(statusText),
      hudActionsRect: rect(hudActions),

      /* THE THEME BUTTON, on the surface this measurement runs on. */
      themeButtonPresent: Boolean(themeButton),
      themeButtonShown: shown(themeButton),
      themeButtonRect: rect(themeButton),
      themeButtonLabel: themeButton ? String((themeButton.querySelector('.theme-button__label') || {}).textContent || '') : null,
      /* ── THE CLIPPING MEASUREMENT ─────────────────────────────────────────
       * MEASURED 2026-10-08: `clientWidth=26` against `scrollWidth=36-43` in all
       * five themes, so the label painted as `oadca`/`nuscr`/`ema C`/`rume`/
       * `epromp`. The fix is in `panel.css`; THIS is the number that proves it,
       * per theme, and it is a comparison of the box against its own content —
       * not a claim about a rule. `labelClipped` must be false and the visible
       * label must equal the theme's own name. */
      themeButtonClientWidth: themeButton ? themeButton.clientWidth : null,
      themeButtonScrollWidth: themeButton ? themeButton.scrollWidth : null,
      themeButtonLabelClipped: themeButton
        ? (themeButton.scrollWidth > themeButton.clientWidth + 1)
        : null,
      themeButtonLabelScrollWidth: themeButton
        ? (function () {
          var l = themeButton.querySelector('.theme-button__label');
          return l ? l.scrollWidth : null;
        }())
        : null,
      stripThemeButtonPresent: Boolean(document.getElementById('strip-theme-button')),
      stripThemeButtonShown: shown(document.getElementById('strip-theme-button')),

      /* THE GEOMETRY THIS MEASUREMENT HAPPENED IN. The real panel is 380x900
       * (the shell's own PANEL_WIDTH/HEIGHT at 96 dpi); a measurement taken in a
       * differently sized frame describes a layout nobody sees. */
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      headerWidth: Math.round(rect(document.querySelector('.panel__header'))[2]),
      controlsWidth: Math.round(rect(document.querySelector('.panel__controls'))[2]),
      headFlex: head ? (cs(head).flexGrow + ' ' + cs(head).flexShrink + ' ' + cs(head).flexBasis) : null,
      headDisplay: head ? cs(head).display : null,

      /* THE LINE'S OWN CLOCK: yellow while it is being said, grey once past. */
      liveTimeColor: liveTime ? cs(liveTime).color : null,
      pastTimeColor: pastTime ? cs(pastTime).color : null,
      liveTimeRgb: liveTime ? rgb(cs(liveTime).color) : null,
      pastTimeRgb: pastTime ? rgb(cs(pastTime).color) : null,
      liveTimeShown: shown(liveTime),
      pastTimeShown: shown(pastTime),

      /* THE HUD IS GONE, AND THE SHORTCUT IS NOT ADVERTISED. */
      hudPresent: Boolean(document.getElementById('hud')),
      hudStyles: document.querySelectorAll('.hud, .hud__row, .hud__actions').length,
      shortcutMentions: shortcutMentions(),

      /* ALL CONTROLS ON THE TOP ROW, AND THE DRAG REGION UNDER THEM. */
      buttons: buttons,
      buttonCount: buttons.length,
      clusterCount: buttons.clusterCount,
      clusterInHeader: buttons.filter(function (b) { return b.inCluster && b.inHeader; }).length,
      clusterNoDrag: buttons.filter(function (b) { return b.inCluster && b.appRegion === 'no-drag'; }).length,
      clusterOffRow: buttons.filter(function (b) {
        if (!b.inCluster || !b.shown) return false;
        var hr = rect(document.querySelector('.panel__header'));
        return b.top > hr[1] + hr[3] / 2;
      }).length,
      headerAppRegion: (function () {
        var h = document.querySelector('.panel__header');
        return h ? (cs(h).webkitAppRegion || cs(h).getPropertyValue('-webkit-app-region')) : null;
      }()),
      stripbarAppRegion: (function () {
        var sb = document.getElementById('strip-controls');
        return sb ? (cs(sb).webkitAppRegion || cs(sb).getPropertyValue('-webkit-app-region')) : null;
      }()),
      noDragButtons: buttons.filter(function (b) { return b.appRegion === 'no-drag'; }).length,
      /* THE BACKGROUNDS: the owner asked for TRANSPARENCY, so the alpha of every
       * surface that could paint an opaque fill is read, not assumed. */
      alphaPanel: alpha(cs(document.querySelector('.panel')).backgroundColor),
      alphaCaptions: alpha(cs(document.querySelector('.captions')).backgroundColor),
      alphaBody: alpha(cs(document.getElementById('captions-body')).backgroundColor),
      alphaCaption: alpha(cs(forming || committed).backgroundColor),
      /* The RAW strings, so an unreadable value is reported instead of passing. */
      bgPanel: cs(document.querySelector('.panel')).backgroundColor,
      bgCaptions: cs(document.querySelector('.captions')).backgroundColor,
      bgBody: cs(document.getElementById('captions-body')).backgroundColor,
      bgCaption: cs(forming || committed).backgroundColor,

      /* THE LEVEL BARS: mounted, and NOT moving without a measurement. */
      meterShown: shown(meterBar),
      meterAnimation: meterBar ? cs(meterBar).animationName : null,
      meterTransform: meterBar ? cs(meterBar).transform : null,
      meterCustom: meterBar ? meterBar.style.getPropertyValue('--meter-h') : null,
      levelAttr: String(document.body.dataset.level || ''),

      /* THE FOUR BEHAVIOURS THIS LANE ADDED. */
      indexShown: shown(index),
      indexText: index ? String(index.textContent) : null,
      committedIndex: committed ? String((committed.querySelector('.caption__index') || {}).textContent || '') : null,
      lastCommittedIndex: lastCommitted,
      rowOrdinals: ordinals,
      rowCount: allRows.length,
      formingIndex: index ? String(index.textContent) : null,

      /* ── THE ORDINAL IS NOT PAINTED ANY MORE (owner, 2026-10-08) ─────────────
       * `indexShown`/`indexText`/`formingIndex` above still read `.caption__index`,
       * and they are kept so a probe can see the element come BACK — but the claim
       * has inverted, and an inverted claim is where an oracle starts lying: "the
       * element is absent" is also true when the whole caption line has vanished.
       * So the absence is paired with the thing that must still be there: the
       * CLOCK, on a committed row and on the forming one, with the forming row's
       * clock a DIFFERENT colour (the owner described it as yellow against grey).
       * `paintedIndexCount` counts the element anywhere in the list, and the
       * ordinal's survival as STATE is read through `rowOrdinals` (`data-index`).
       */
      paintedIndexCount: document.querySelectorAll('#caption-list .caption__index').length,
      paintedIndexTexts: (function () {
        var els = document.querySelectorAll('#caption-list .caption__index');
        var out = [];
        for (var z = 0; z < els.length; z += 1) out.push(String(els[z].textContent));
        return out;
      }()),
      committedTimeText: pastTime ? String(pastTime.textContent) : null,
      committedTimeColor: pastTime ? cs(pastTime).color : null,
      formingTimeText: liveTime ? String(liveTime.textContent) : null,
      formingTimeColor: liveTime ? cs(liveTime).color : null,
      timesDiffer: Boolean(pastTime && liveTime && cs(pastTime).color !== cs(liveTime).color),

      /* ── THE NAME `sotto`, IN THIS DIRECTION'S PAINTED HEADER ───────────────
       * Counted over RENDERED elements only: the four chrome blocks that are not
       * this direction's are `display: none` and their text is still in the DOM,
       * so a naive read would find five names where the eye sees one.
       */
      headerText: headerTextPainted,
      brandCount: (headerTextPainted.match(/sotto/gi) || []).length,
      brandTextTransform: brandEl ? cs(brandEl).textTransform : null,
      brandText: brandEl ? String(brandEl.textContent).trim() : null,
      ledShown: shown(led),
      ledAnimation: ledC ? ledC.animationName : null,
      ledWidth: ledC ? ledC.width : null,
      ledBackground: ledC ? ledC.backgroundColor : null,
      ledLeft: ledC ? ledC.left : null,
      wordCount: words.length,
      words: words,
      rampMonotonic: rampMonotonic,
      rampTop: rampTop,
      rampBottom: rampBottom,
      rampUsesVars: words.length ? (words[0].i !== '' && words[0].n !== '') : false,
      wordTransitionProperty: words.length ? words[0].transitionProperty : null,
      wordTransitionDuration: words.length ? words[0].transitionDuration : null,
      textFilter: textEl ? cs(textEl).filter : null,
      tailFilter: tailEl ? cs(tailEl).filter : null,
      tailOpacity: tailEl ? cs(tailEl).opacity : null,
      confirmedWordCount: confirmedEl ? confirmedEl.querySelectorAll('.caption__word').length : 0,
      tailWordCount: tailEl ? tailEl.querySelectorAll('.caption__word').length : 0,
      meterAnimations: meterBars,

      /* The mockups' own invented numbers, so the probe can assert their ABSENCE
       * from a live panel. `designs.ts` drives `CONF 0.93` / `buffer 38ms` from a
       * simulated script; printing one here would be inventing a measurement. */
      statusTextContent: statusText ? String(statusText.textContent) : null,
      chromeTextAll: Array.prototype.map.call(
        document.querySelectorAll('.chrome'),
        function (e) { return String(e.textContent).replace(/\s+/g, ' ').trim(); }
      ).join(' | ')
    };
  }

  /* ── THE CAPTION STREAM, through the REAL renderer ────────────────────────
   * Three partials of one segment (same `start`, growing `end`), then a LIVE
   * status — which is what the shell sends while captions flow and which is also
   * what makes `panel.js` flush the held line into a COMMITTED row — then the
   * first partials of the NEXT segment, so a forming row exists to measure. That
   * is the worker's own wire order.
   *
   * ── SYNCHRONOUS ON PURPOSE, AND THAT IS A MEASURED CORRECTION ────────────
   * The first version of this driver spaced the pushes with `setTimeout(…, 40)`,
   * which is correct in the app and WRONG here: this arm runs under
   * `--virtual-time-budget`, so the renderer fast-forwards timers and the
   * engine's OWN hold deadline (`COMMIT_MAX_HOLD_MS`) fires between two pushes
   * that are 40 ms apart in virtual time. That committed the second segment
   * early and the probe then read a forming row numbered `003` against a
   * committed `001` — a REAL failure of the driver, not of the panel. Every push
   * below therefore happens in ONE synchronous turn, so no timer can interleave,
   * and the ordinal assertion (`forming = committed + 1`) is about the panel.
   */
  function driveCaptions(base) {
    push('o rato roeu', base + 0, base + 0.5, false);
    push('o rato roeu a roupa', base + 0, base + 1.0, false);
    push('o rato roeu a roupa do rei', base + 0, base + 1.6, false);
    push('o rato roeu a roupa do rei de roma', base + 0, base + 2.1, true);
    /* The shell's own live status: `{text, kind:'live'}` — the shape
     * `statusPayload` accepts and the shape that lights `data-state`. */
    emitStatus('Receiving captions', 'live');
    push('e a segunda linha comeca', base + 3, base + 0.6, false);
    push('e a segunda linha comeca aqui', base + 3, base + 1.1, false);
  }

  function finish() {
    var el = document.createElement('div');
    el.id = '__chrome_probe';
    el.hidden = true;
    el.setAttribute('data-chrome-probe-count', String(REPORT.themes.length));
    for (var i = 0; i < REPORT.themes.length; i += 1) {
      el.setAttribute('data-chrome-probe-' + i, JSON.stringify(REPORT.themes[i]));
    }
    el.setAttribute('data-chrome-probe-errors', JSON.stringify(REPORT.errors));
    el.setAttribute('data-chrome-probe-surface', JSON.stringify(REPORT.surface));
    document.body.appendChild(el);
    if (REPORT.errors.length) err(REPORT.errors.join(' ; '));
  }

  function main() {
    if (!document.getElementById('caption-list')) { err('no #caption-list in this document'); return; }
    var only = hashParam('theme');
    var list = only ? DIRS.filter(function (d) { return d.theme === only || d.id === only; }) : DIRS;
    if (!list.length) { err('unknown theme ' + only); return; }

    var i = 0;
    (function nextTheme() {
      if (i >= list.length) { stripCheck(); return; }
      var dir = list[i];
      var themeIdx = DIRS.map(function (d) { return d.id; }).indexOf(dir.id);
      i += 1;
      setTheme(dir.theme);
      try {
        /* ONE synchronous turn per theme: switch, drive, read. `getComputedStyle`
         * forces the style recalc, so the values read below are the theme's own.
         *
         * THE `base` OFFSET IS NOT COSMETIC. `panel.js` identifies a line by its
         * `start` (`committedByStart`), so driving all five themes with the SAME
         * audio seconds made the second theme's commit a REVISION of the first
         * theme's row — the list never grew, `lineOrdinal` never moved, and the
         * ordinal assertion read `001` against `003`. That was the PROBE
         * collapsing five lines into one, not the panel losing an ordinal; each
         * direction now gets its own span of audio seconds. */
        driveCaptions(themeIdx * 100);
        REPORT.themes.push(measure(dir, themeIdx * 100));
      } catch (e) {
        err('measure(' + dir.id + ') threw: ' + e.message);
      }
      setTimeout(nextTheme, 20);
    }());

    /* ── THE STRIP SURFACE, where the theme button used to be unreachable ────
     * `.panel__header` is `display: none` there and the header's theme button
     * lives inside it, so the strip carries its OWN control
     * (`#strip-theme-button`). This is the half the previous lane flagged and
     * left standing. */
    function stripCheck() {
      var api = window.SottoSurfaces;
      if (!api || typeof api.set !== 'function') { err('SottoSurfaces missing'); finish(); return; }
      var results = [];
      var idx = 0;
      (function nextStrip() {
        if (idx >= DIRS.length) {
          REPORT.surface = { strip: results };
          finish();
          return;
        }
        var dir = DIRS[idx];
        idx += 1;
        setTheme(dir.theme);
        api.set('strip');
        var head = document.querySelector('.chrome--' + dir.id + '[data-chrome="head"]');
        var foot = document.querySelector('.chrome--' + dir.id + '[data-chrome="foot"]');
        var btn = document.getElementById('strip-theme-button');
        var header = document.querySelector('.panel__header');
        results.push({
          id: dir.id,
          theme: dir.theme,
          surface: String(document.body.getAttribute('data-surface')),
          headerShown: shown(header),
          headChromeShown: shown(head),
          footChromeShown: shown(foot),
          stripThemeButtonShown: shown(btn),
          stripThemeButtonRect: rect(btn),
          stripThemeButtonLabel: btn ? String((btn.querySelector('.theme-button__label') || {}).textContent || '') : null,
          stripThemeButtonSwatch: btn ? cs(btn.querySelector('.strip-theme__swatch')).backgroundColor : null
        });
        setTimeout(nextStrip, 20);
      }());
    }
  }

  if (document.readyState === 'complete') {
    setTimeout(main, 0);
  } else {
    /* THIS FILE LOADS BEFORE `panel.js` (it has to, to capture the status
     * subscription), so it waits for `load`: by then `panel.js` has run its init
     * block, the theme switcher has mounted its buttons and the first paint has
     * happened. */
    window.addEventListener('load', function () { setTimeout(main, 0); });
  }
}());
