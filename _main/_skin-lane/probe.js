/* SHARED ROLE DETECTION AND FINGERPRINTING for the cinematic-2 freeze.
 *
 * Loaded by BOTH the freezer (which measures the vendor's live page) and the fidelity
 * oracle's host page (which measures the frozen fragments), so the two sides are found by
 * the SAME rules. A comparison whose two sides are located differently measures the
 * locators, not the pixels.
 *
 * Everything here is a pure function of the DOM: no globals, no timers.
 */
(function (global) {
  'use strict';

  /* Computed properties kept for every role. Chosen because each one is a thing a broken
   * Shadow-DOM rewrite actually changes: geometry (rect), the height chain (display,
   * position), the type (font*, line-height, letter-spacing), the plate (background*,
   * border*, radius, shadow, backdrop-filter), the blending/isolation (opacity,
   * mix-blend-mode, filter, isolation) and the animation (animation-name, which is how a
   * lost @keyframes shows up as a frozen or invisible plate). */
  var PROPS = [
    'display', 'position', 'zIndex', 'opacity', 'visibility', 'overflow',
    'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight', 'letterSpacing',
    'textTransform', 'textAlign', 'color', 'textShadow',
    'backgroundColor', 'backgroundImage', 'backgroundSize', 'backgroundPosition',
    'borderTopWidth', 'borderTopStyle', 'borderTopColor', 'borderLeftWidth',
    'borderRadius', 'boxShadow', 'backdropFilter', 'filter', 'mixBlendMode',
    'isolation', 'transform', 'animationName', 'animationDuration', 'animationFillMode',
    'paddingTop', 'paddingLeft', 'marginTop', 'marginLeft'
  ];

  function safeClass(c) {
    // A Tailwind arbitrary-value class (`z-[25]`, `top-[74px]`, `gap-[3px]`) needs CSS
    // escaping, so it is never used to BUILD a selector — but it is still fine to read.
    return /^[A-Za-z][A-Za-z0-9_-]*$/.test(c);
  }

  function isElement(n) {
    return n && n.nodeType === 1;
  }

  function elChildren(n) {
    return Array.prototype.filter.call(n.children, isElement);
  }

  /* A structural path that is stable under TEXT changes but not under STRUCTURE changes,
   * which is the honest trade: no class, attribute or id exists for most of these nodes. */
  function pathFrom(root, el) {
    var parts = [];
    var n = el;
    while (n && n !== root) {
      var parent = n.parentElement;
      if (!parent) return null;
      var sameTag = Array.prototype.filter.call(parent.children, function (c) {
        return c.tagName === n.tagName;
      });
      var k = sameTag.indexOf(n) + 1;
      parts.unshift(n.tagName.toLowerCase() + (sameTag.length > 1 ? ':nth-of-type(' + k + ')' : ''));
      n = parent;
    }
    if (n !== root) return null;
    return parts.length ? parts.join(' > ') : ':scope';
  }

  /* Build the most stable selector that still RESOLVES TO THIS EXACT ELEMENT inside
   * `root`, and say which strategy won. The candidate is verified, never assumed. */
  function deriveSelector(root, el) {
    var tries = [];

    // 1. a semantic class from the vendor's own stylesheet, then any safe class
    var SEMANTIC = ['quiet-scroll', 'word-in', 'caret', 'soft-in', 'fade-in', 'grain-layer',
                    'rain-streak', 'drift-mote', 'hairline', 'shimmer-text', 'breathe'];
    var classes = (el.getAttribute('class') || '').split(/\s+/).filter(Boolean);
    classes.forEach(function (c) {
      if (SEMANTIC.indexOf(c) >= 0) tries.push('.' + c);
    });
    classes.forEach(function (c) {
      if (safeClass(c)) tries.push('.' + c);
    });

    // 2. a bare attribute marker
    ['aria-hidden', 'aria-label', 'role', 'type', 'data-testid'].forEach(function (a) {
      if (el.hasAttribute(a)) tries.push('[' + a + ']');
    });

    for (var i = 0; i < tries.length; i++) {
      var sel = tries[i];
      var hits = root.querySelectorAll(sel);
      if (hits.length === 1 && hits[0] === el) {
        return { selector: sel, strategy: i < SEMANTIC.length ? 'semantic-class' : 'class' };
      }
    }

    var p = pathFrom(root, el);
    if (p) {
      try {
        var hit = root.querySelector(p);
        if (hit === el) return { selector: p, strategy: 'structural-path' };
      } catch (e) { /* an unhappy path is simply not a candidate */ }
    }
    return { selector: null, strategy: 'none' };
  }

  function byInlineBg(node, prefix) {
    if (!isElement(node)) return false;
    var bg = node.getAttribute('style') || '';
    return bg.indexOf('background: ' + prefix) >= 0 || bg.indexOf('background:' + prefix) >= 0;
  }

  /* ---------- the roles, found by the same rules on both sides ---------- */
  function detect(compRoot) {
    var R = {};
    var kids = elChildren(compRoot);

    // The caption column is identified by CONTAINING the forming marker, not by a class:
    // `.caret` and `.word-in` exist only while a line is being transcribed, which is the
    // state the freeze captures, and no other subtree contains them.
    R.caption = kids.filter(function (c) {
      return c.querySelector('.caret') || c.querySelector('.word-in') ||
        c.querySelector('.soft-in');
    })[0] || null;
    R.panel = compRoot.querySelector(':scope > aside') || null;
    R.stage = kids.filter(function (c) {
      return !R.caption || c !== R.caption;
    }).filter(function (c) {
      return c !== R.panel && c.tagName !== 'BUTTON' &&
        c.querySelector('.grain-layer') !== null;
    })[0] || null;

    /* The chrome is the RANGE of siblings between the Stage and the caption column,
     * because the vendor's `float` branch is a React fragment with several roots and no
     * single element to find. On the frozen side that range holds one wrapper
     * (`.skin-chrome`) — a single-file fragment needs one root — so the wrapper is
     * FLATTENED here. Without this the two sides compare the wrapper against the first
     * chrome node, which is how the gate reported `chrome rect.w 0 vs 380` for every
     * `float` design: a locator artefact, not a paint difference. */
    R.chromeNodes = [];
    if (R.stage && R.caption) {
      var arr = elChildren(compRoot);
      var i0 = arr.indexOf(R.stage), i1 = arr.indexOf(R.caption);
      if (i0 >= 0 && i1 > i0) {
        R.chromeNodes = arr.slice(i0 + 1, i1).filter(function (c) {
          return c.tagName !== 'BUTTON';
        });
      }
    }
    if (R.chromeNodes.length === 1 && R.chromeNodes[0].classList &&
        R.chromeNodes[0].classList.contains('skin-chrome')) {
      R.chromeNodes = elChildren(R.chromeNodes[0]);
    }
    R.chrome = R.chromeNodes[0] || null;
    R.root = compRoot;

    if (R.stage) {
      var layers = Array.prototype.filter.call(R.stage.querySelectorAll('div'), function (d) {
        return (d.getAttribute('style') || '').indexOf('background-image') >= 0;
      });
      // The vendor keeps the outgoing wallpaper layer at opacity 0 while it cross-fades;
      // the LIVE one is the last. The frozen fragment carries only the live one.
      R.wall = layers[layers.length - 1] || null;
      R.overlay = Array.prototype.filter.call(R.stage.querySelectorAll('div'), function (d) {
        return byInlineBg(d, 'linear-gradient');
      })[0] || null;
      R.vignette = Array.prototype.filter.call(R.stage.querySelectorAll('div'), function (d) {
        return byInlineBg(d, 'radial-gradient');
      })[0] || null;
      R.grain = R.stage.querySelector('.grain-layer');
      R.slate = R.stage.querySelector('[class*="select-none"]');
      R.particles = R.stage.querySelector('.rain-streak, .drift-mote');
    }

    if (R.caption) {
      R.liveBox = R.caption.querySelector('.caret') ? R.caption : null;
      var caret = R.caption.querySelector('.caret');
      var word = R.caption.querySelector('.word-in');
      R.caret = caret;
      R.word = word;
      // `live` is the element whose CHILDREN are the word spans: the deepest container
      // that holds a word. Falling back to the caret's parent keeps it defined when the
      // line has no words yet.
      R.live = word ? word.parentElement : (caret ? caret.parentElement : null);
      R.captionBox = R.live ? nearestChildOf(R.caption, R.live) : null;
      R.meter = R.caption.querySelector('[aria-hidden]');
      R.status = statusWord(R.caption);
      R.speaker = speakerLabel(R.caption);
    }

    if (R.panel) {
      R.list = R.panel.querySelector('.quiet-scroll') || R.panel.querySelector('[class*="overflow-y-auto"]');
      if (R.list) {
        var clock = findClock(R.list);
        R.time = clock;
        R.row = clock ? rowOf(R.list, clock) : null;
      }
    }
    return R;
  }

  function nearestChildOf(ancestor, node) {
    var n = node;
    while (n && n.parentElement !== ancestor) n = n.parentElement;
    return n;
  }

  function textOf(n) {
    return (n.textContent || '').replace(/\s+/g, ' ').trim();
  }

  var STATUS = /^(listening|paused|speaking now|capturing|rolling|live track|hold|read-along)$/i;

  function statusWord(root) {
    var spans = root.querySelectorAll('span');
    for (var i = 0; i < spans.length; i++) {
      if (STATUS.test(textOf(spans[i]))) return spans[i];
    }
    return null;
  }

  /* The speaker label is the element that prints a short, upper-cased name — the vendor
   * renders `speakerShort(speaker)`. It is found by SHAPE (short text, wide tracking,
   * upper-cased) rather than by a name list, because the name list belongs to the
   * simulation rather than to the skin. */
  function speakerLabel(root) {
    var cands = root.querySelectorAll('span');
    for (var i = 0; i < cands.length; i++) {
      var t = textOf(cands[i]);
      if (!t || t.length > 12) continue;
      if (STATUS.test(t)) continue;
      if (/^[\d:.·—–-]+$/.test(t)) continue;
      var cs = global.getComputedStyle(cands[i]);
      var upper = cs.textTransform === 'uppercase' || t === t.toUpperCase();
      var wide = parseFloat(cs.letterSpacing) >= 1.5;
      if (upper && wide) return cands[i];
    }
    return null;
  }

  var CLOCK = /\b\d{1,2}:\d{2}(:\d{2})?\b/;

  function findClock(root) {
    var all = root.querySelectorAll('span');
    for (var i = 0; i < all.length; i++) {
      var t = textOf(all[i]);
      if (t.length <= 12 && CLOCK.test(t)) return all[i];
    }
    return null;
  }

  /* list > group > row > … > clock  →  the row. Never assumes there is exactly one
   * wrapper level, because the vendor groups rows by session. */
  function rowOf(list, el) {
    var n = el;
    while (n && n.parentElement && n.parentElement !== list) {
      if (n.parentElement.parentElement === list) return n;
      n = n.parentElement;
    }
    return n && n.parentElement === list ? n : null;
  }

  /* ---------- the fingerprint ---------- */
  function snapshot(el) {
    if (!el) return null;
    var cs = global.getComputedStyle(el);
    var o = { tag: el.tagName.toLowerCase(), how: null, rect: null, props: {} };
    var r = el.getBoundingClientRect();
    o.rect = {
      x: Math.round(r.x * 100) / 100, y: Math.round(r.y * 100) / 100,
      w: Math.round(r.width * 100) / 100, h: Math.round(r.height * 100) / 100
    };
    o.how = (el.getAttribute('class') || '') + ' | ' + (el.getAttribute('style') || '').slice(0, 160);
    for (var i = 0; i < PROPS.length; i++) {
      var v = cs[PROPS[i]];
      o.props[PROPS[i]] = (v === null || v === undefined) ? null : String(v);
    }
    return o;
  }

  var ROLE_ORDER = ['root', 'stage', 'wall', 'overlay', 'vignette', 'grain', 'slate', 'particles',
                    'chrome', 'chrome0', 'chrome1', 'chrome2', 'caption', 'captionBox', 'live',
                    'word', 'caret', 'status', 'speaker', 'meter', 'panel', 'list', 'row', 'time'];

  function fingerprint(compRoot) {
    var roles = detect(compRoot);
    var out = {};
    ROLE_ORDER.forEach(function (k) {
      if (k === 'chrome0' || k === 'chrome1' || k === 'chrome2') {
        var i = Number(k.slice(6));
        out[k] = snapshot(roles.chromeNodes ? roles.chromeNodes[i] : null);
        return;
      }
      out[k] = snapshot(roles[k]);
    });
    return { roles: out, found: Object.keys(roles).filter(function (k) { return roles[k]; }) };
  }

  global.__sottoProbe = {
    detect: detect,
    fingerprint: fingerprint,
    snapshot: snapshot,
    deriveSelector: deriveSelector,
    pathFrom: pathFrom,
    textOf: textOf,
    ROLE_ORDER: ROLE_ORDER,
    PROPS: PROPS
  };
})(window);
