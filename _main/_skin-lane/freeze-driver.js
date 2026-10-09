/* THE FREEZER, in the page. Injected with `executeJavaScript` by freeze.js.
 *
 * Two exported calls, deliberately separate so the Electron side owns the screenshot order:
 *   __freeze_run(args)      — force the design, wait until a line is FORMING, slice the
 *                             four fragments, rewrite them, derive+verify the bindings.
 *                             Touches nothing on the live page.
 *   __freeze_compose_live() — apply to the LIVE page the same rewrites the frozen
 *                             fragments carry, stop the simulation's clock and kill the
 *                             animations, so a capturePage of it is the reference still.
 *
 * The bindings are derived on a DETACHED parse of the frozen bytes and verified with
 * `querySelector` against that same detached tree — so "it resolves" is a statement about
 * the artifact, not about the page it came from.
 */
(function (global) {
  'use strict';

  var P = global.__sottoProbe;
  var wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  function appRoot() {
    var container = document.getElementById('root');
    return container ? container.firstElementChild : null;
  }

  function kids(n) { return Array.prototype.slice.call(n.children); }

  /* ---------- 1. force design `index` ---------- */
  function forceDesign(index, expectN) {
    // The default is THEMES[2] and `cycle` uses a FUNCTIONAL state updater, so N
    // synchronous dispatches compose into exactly N steps (analysis §2, recipe A).
    var k = (index - 2 + 20) % 20;
    for (var n = 0; n < k; n++) {
      global.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    }
    return k;
  }

  function showsDesign(expectN) {
    var best = null;
    var els = document.querySelectorAll('button, span, div');
    for (var i = 0; i < els.length; i++) {
      var t = (els[i].textContent || '').replace(/\s+/g, ' ').trim();
      if (t.indexOf(expectN + ' ·') === 0) { best = t.slice(0, 24); break; }
    }
    return best;
  }

  /* A line is FORMING when the caret is in the DOM: `isLive = partial && running`, and
   * the caret renders only then. Asserting on it is the difference between capturing the
   * design in its live state and capturing an idle one. */
  function isLive() {
    return document.querySelector('.caret') !== null;
  }

  function hasWords() {
    return document.querySelector('.word-in') !== null;
  }

  /* ---------- 2. slice the four fragments out of the live tree ---------- */
  function sliceFragments() {
    var root = appRoot();
    if (!root) throw new Error('no App root: #root has no element child');
    var children = kids(root);
    var stage = children.filter(function (c) { return c.querySelector('.grain-layer'); })[0];
    var caption = children.filter(function (c) {
      return c.querySelector('.caret') || c.querySelector('.word-in');
    })[0];
    var panel = children.filter(function (c) { return c.tagName === 'ASIDE'; })[0];
    if (!stage) throw new Error('the Stage subtree was not found (no .grain-layer descendant)');
    if (!caption) throw new Error('the caption column was not found (no .caret/.word-in descendant)');
    if (!panel) throw new Error('the HistoryPanel <aside> was not found');

    var iStage = children.indexOf(stage);
    var iCaption = children.indexOf(caption);
    // The vendor renders Stage, then TopChrome (1..n siblings — the `float` branch is a
    // React fragment with no single root), then the caption column, then the panel.
    // The chrome is therefore the RANGE between the stage and the caption. Taking it as a
    // range is what makes the `float` branch freezable at all.
    var chromeNodes = children.slice(iStage + 1, iCaption)
      .filter(function (c) { return c.tagName !== 'BUTTON'; });

    return {
      stageEl: stage,
      chromeEls: chromeNodes,
      captionEl: caption,
      panelEl: panel,
      order: ['stage', 'chrome', 'caption', 'panel'],
      appRootEl: root
    };
  }

  /* ---------- 3. rewrite the frozen bytes ---------- */
  function localWall(url, wallMap) {
    var m = /pexels-photo-?(\d+)?[^/]*/.exec(url) || /photos\/(\d+)\//.exec(url);
    var id = null;
    var m2 = /\/photos\/(\d+)\//.exec(url);
    if (m2) id = m2[1];
    if (!id) return null;
    return wallMap && wallMap[id] ? wallMap[id] : null;
  }

  function rewriteStage(html, wallMap, log) {
    var doc = new DOMParser().parseFromString('<div id="fx">' + html + '</div>', 'text/html');
    var root = doc.getElementById('fx');
    var layers = Array.prototype.filter.call(root.querySelectorAll('div'), function (d) {
      return (d.getAttribute('style') || '').indexOf('background-image') >= 0;
    });
    // The vendor keeps the OUTGOING wallpaper alive at opacity 0 while it cross-fades
    // (`Stage.tsx:22-24` keeps two layers forever). That layer belongs to the PREVIOUS
    // design, so it is dropped from the freeze — a transition artefact, not the design.
    var dropped = 0;
    if (layers.length > 1) {
      for (var i = 0; i < layers.length - 1; i++) {
        layers[i].parentNode.removeChild(layers[i]);
        dropped++;
      }
      layers = [layers[layers.length - 1]];
    }
    var rep = 0;
    layers.forEach(function (d) {
      var before = d.getAttribute('style') || '';
      var after = before.replace(/url\((['"]?)(https?:\/\/[^)'"]+)\1\)/g, function (all, q, url) {
        var local = localWall(url, wallMap);
        if (!local) { log.push({ kind: 'wall-unmapped', url: url }); return all; }
        log.push({ kind: 'wall-url', before: url, after: local });
        return 'url(' + local + ')';
      });
      if (after !== before) { d.setAttribute('style', after); rep++; }
    });
    return { html: root.innerHTML, droppedLayers: dropped, rewritten: rep };
  }

  /* The caption column's `right` is `theme.panel.width + 34` (e.g. 402 px): in a 380 px
   * column the vendor's own layout gives the caption ZERO width and every word wraps into
   * a sliver. The column is frozen at the full 380 with `right: 0`, which is a targeted,
   * reported edit — and the same edit is applied to the live page before the reference
   * screenshot, so the two sides of the gate are composed identically. */
  function rewriteCaption(html, log) {
    var doc = new DOMParser().parseFromString('<div id="fx">' + html + '</div>', 'text/html');
    var root = doc.getElementById('fx');
    var el = root.firstElementChild;
    var style = el.getAttribute('style') || '';
    var m = /right:\s*([-\d.]+)px/.exec(style);
    if (m) {
      var after = style.replace(/right:\s*[-\d.]+px/, 'right: 0px');
      el.setAttribute('style', after);
      log.push({ kind: 'caption-right', before: 'right: ' + m[1] + 'px', after: 'right: 0px' });
    }
    return { html: root.innerHTML, hadRight: Boolean(m) };
  }

  function serializeChrome(els, log) {
    if (els.length === 1) {
      var only = els[0];
      var style = only.getAttribute('style') || '';
      var m = /right:\s*([-\d.]+)px/.exec(style);
      if (m && parseFloat(m[1]) > 100) {
        // The header's `right: rightInset` collapses it just as the caption's does. Same
        // defect class, same targeted rewrite, reported separately.
        only.setAttribute('style', style.replace(/right:\s*[-\d.]+px/, 'right: 0px'));
        log.push({ kind: 'chrome-right', before: 'right: ' + m[1] + 'px', after: 'right: 0px',
                   where: 'single chrome node' });
      }
      return { html: only.outerHTML, nodes: 1, wrapped: false };
    }
    var out = [];
    els.forEach(function (el) {
      var style = el.getAttribute('style') || '';
      var m = /right:\s*([-\d.]+)px/.exec(style);
      if (m && parseFloat(m[1]) > 100) {
        el.setAttribute('style', style.replace(/right:\s*[-\d.]+px/, 'right: 0px'));
        log.push({ kind: 'chrome-right', before: 'right: ' + m[1] + 'px', after: 'right: 0px',
                   where: 'one of ' + els.length + ' chrome nodes' });
      }
      out.push(el.outerHTML);
    });
    // A React fragment has several roots. The wrapper is `position: static` on purpose: a
    // static box is NOT a containing block, so the `absolute` chrome children keep
    // resolving against the host's positioned root exactly as they did against the App
    // root, and the wrapper itself occupies no space.
    return {
      html: '<div class="skin-chrome">' + out.join('') + '</div>',
      nodes: els.length, wrapped: true
    };
  }

  /* ---------- 4. the bindings, derived and PROVED on the frozen bytes ---------- */
  function deriveBindings(frag, varStyle) {
    // One detached composition, assembled exactly as the host will assemble it, so the
    // role rules run on the artifact instead of on the page.
    var html = '<div id="compose">' + frag.stage.html + frag.chrome.html +
      frag.caption.html + frag.panel.html + '</div>';
    var doc = new DOMParser().parseFromString(html, 'text/html');
    var compose = doc.getElementById('compose');

    /* A DETACHED TREE HAS NO COMPUTED STYLES, and that is not a detail: the speaker
     * label is found by SHAPE (`text-transform: uppercase`, wide `letter-spacing`), and
     * `getComputedStyle` on a node outside a document returns empty strings for both — so
     * the rule silently found nothing and reported `speaker: null` for all 20 designs
     * while the DOM census showed `span.mr-3.align-middle` sitting in the live line. The
     * tree is therefore attached to the page (off-screen, invisible, carrying the same
     * 15 variables) while it is measured, then removed. */
    var host = document.createElement('div');
    host.setAttribute('style',
      'position:absolute;left:-99999px;top:0;width:380px;height:900px;' +
      'visibility:hidden;pointer-events:none;contain:strict;' + (varStyle || ''));
    document.body.appendChild(host);
    var mounted = document.importNode(compose, true);
    host.appendChild(mounted);

    var roles, parts = { stage: null, chrome: null, caption: null, panel: null };
    try {
      roles = P.detect(mounted);
      Array.prototype.forEach.call(mounted.children, function (c) {
        if (c.querySelector('.grain-layer')) parts.stage = c;
        else if (c.tagName === 'ASIDE') parts.panel = c;
        else if (c.querySelector('.caret') || c.querySelector('.word-in') || c.querySelector('.soft-in')) parts.caption = c;
        else parts.chrome = c;
      });

    var WANT = [
      ['live', 'live', 'caption'], ['wordTemplate', 'word', 'caption'],
      ['caret', 'caret', 'caption'], ['speaker', 'speaker', 'caption'],
      ['statusWord', 'status', 'caption'], ['meter', 'meter', 'caption'],
      ['historyList', 'list', 'panel'], ['historyRow', 'row', 'panel'],
      ['historyTime', 'time', 'panel']
    ];

    var out = {};
    var proof = {};
    WANT.forEach(function (w) {
      var key = w[0], role = w[1], fragName = w[2];
      var el = roles[role];
      var fragRoot = parts[fragName];
      if (!el && roles[role + 'El']) el = roles[role + 'El'];
      if (!el) {
        out[key] = null;
        proof[key] = { key: key, resolved: false, fragment: fragName,
                       reason: 'the role "' + role + '" has no element in the ' + fragName + ' fragment' };
        return;
      }
      if (!fragRoot) {
        out[key] = null;
        proof[key] = { key: key, resolved: false, reason: 'no ' + fragName + ' fragment root' };
        return;
      }
      if (!fragRoot.contains(el) && fragRoot !== el) {
        out[key] = null;
        proof[key] = { key: key, resolved: false, fragment: fragName,
                       reason: 'the element is outside the ' + fragName + ' fragment' };
        return;
      }
      var d = P.deriveSelector(fragRoot, el);
      if (!d.selector) {
        out[key] = null;
        proof[key] = { key: key, resolved: false, fragment: fragName,
                       reason: 'no candidate selector resolved to this exact element' };
        return;
      }
      // THE PROOF: re-query the frozen bytes and demand the same node back.
      var back = fragRoot.querySelector(d.selector);
      proof[key] = {
        key: key, resolved: back === el, strategy: d.strategy, fragment: fragName,
        unique: fragRoot.querySelectorAll(d.selector).length === 1,
        text: P.textOf(el).slice(0, 40)
      };
      out[key] = d.selector;
    });

    // A candid record of what the live line actually is, so a null binding is a measured
    // statement about the vendor's markup and not a shrug.
    var live = roles.live;
    var census = null;
    if (live) {
      census = {
        tag: live.tagName.toLowerCase(),
        cls: live.getAttribute('class') || '',
        children: Array.prototype.map.call(live.children, function (c) {
          return c.tagName.toLowerCase() + '.' + (c.getAttribute('class') || '').replace(/\s+/g, '.');
        }),
        childCount: live.children.length,
        speakerCandidates: Array.prototype.filter.call(
          mounted.querySelectorAll('span'), function (s) {
            var cs = global.getComputedStyle(s);
            return cs.textTransform === 'uppercase' && parseFloat(cs.letterSpacing) >= 1.5;
          }).slice(0, 6).map(function (s) {
            return P.textOf(s).slice(0, 14) + ' :: ' + (s.getAttribute('class') || '(no class)');
          })
      };
    }
    return { bindings: out, proof: proof, census: census, rolesFound: roles };
    } finally {
      // The measuring copy never outlives the measurement: the live page is left exactly
      // as the fingerprint and the fragments found it.
      if (host.parentNode) host.parentNode.removeChild(host);
    }
  }

  /* ---------- the entry points ---------- */
  global.__freeze_run = async function (args) {
    var log = [];
    var root = appRoot();
    if (!root) throw new Error('no App root after load');

    var k = forceDesign(args.index, args.n);
    await wait(220);
    // Assert the design actually changed instead of sleeping and hoping: the chrome
    // prints `<n> ·` and the design numbers are unique.
    var shown = null;
    for (var t = 0; t < 40 && !shown; t++) {
      shown = showsDesign(args.n);
      if (!shown) await wait(100);
    }
    if (!shown) throw new Error('design ' + args.n + ' (' + args.id + ') never appeared in the chrome');

    await wait(1300);   // the cross-fade, the slate and the caption column transitions

    var liveWait = 0;
    while (!isLive() && liveWait < 12000) { await wait(150); liveWait += 150; }
    if (!isLive()) throw new Error('no forming line within 12 s: .caret never appeared');
    while (!hasWords() && liveWait < 13000) { await wait(150); liveWait += 150; }

    var frags = sliceFragments();
    var wallRewrite = rewriteStage(frags.stageEl.outerHTML, args.wallMap, log);
    var capRewrite = rewriteCaption(frags.captionEl.outerHTML, log);
    var chromeOut = serializeChrome(frags.chromeEls, log);
    var chromeRewrite = chromeOut.wrapped ? chromeOut : { html: chromeOut.html, nodes: 1, wrapped: false };

    var frozen = {
      stage: { html: wallRewrite.html },
      chrome: { html: chromeRewrite.html, nodes: chromeRewrite.nodes, wrapped: chromeRewrite.wrapped },
      caption: { html: capRewrite.html },
      panel: { html: frags.panelEl.outerHTML }
    };

    var derived = deriveBindings(frozen, frags.appRootEl.getAttribute('style') || '');

    // `vars` verbatim off the App root's inline style — the 15 design variables, in the
    // order the vendor wrote them.
    var varStyle = frags.appRootEl.getAttribute('style') || '';
    var vars = {};
    varStyle.split(';').forEach(function (pair) {
      var i = pair.indexOf(':');
      if (i < 0) return;
      var k2 = pair.slice(0, i).trim();
      if (k2.indexOf('--') === 0) vars[k2] = pair.slice(i + 1).trim();
    });

    var ids = Array.prototype.map.call(document.querySelectorAll('.grain-layer'), function () { return 1; });

    var post = null;
    /* The oracle's atomicity: the slice above captured text T, but the timers are still
     * running — every IPC round trip back to Electron is a window in which the
     * simulation reveals another word, moving the caret the reference is measured
     * against. Measured, cellar: `.word-in` was "Egyptian" in the slice and "the" one
     * reference later, which is how the gate reported `word rect.x 80 vs 238`. With
     * this flag the clock is stopped and the reference composed SYNCHRONOUSLY in the
     * same page task as the slice, so the fragments and the reference are the same
     * text by construction, not by luck. freeze.js does NOT pass it (it wants the
     * vendor page untouched); the oracle does. */
    if (args.composeAfterSlice) {
      var composed = global.__freeze_compose_live();
      var postRoot = appRoot();
      var postRoles = P.detect(postRoot);
      // The vendor's wallpaper URL is remote (Pexels) and unreachable from this box's
      // file:// page load; what paints is whatever the browser managed to decode. Record
      // the computed URL plus a decode probe of the same file, so the gate can tell a
      // painting difference from a loading difference.
      var wallBg = postRoles.wall ? global.getComputedStyle(postRoles.wall).backgroundImage : '';
      var wi = (wallBg || '').indexOf('url(');
      var wallURL = wi < 0 ? null :
        wallBg.slice(wi + 4, wallBg.indexOf(')', wi)).replace(/["' ]/g, '');
      post = {
        rewrites: composed.rewrites,
        fingerprint: P.fingerprint(postRoot),
        listScrollTop: postRoles.list ? postRoles.list.scrollTop : null,
        wordText: postRoles.word ? postRoles.word.textContent : null,
        wallURL: wallURL
      };
    }

    return {
      id: args.id, index: args.index, n: args.n,
      arrows: k, liveAfterMs: liveWait, chromeShownAs: shown,
      vars: vars,
      fragments: frozen,
      bindings: derived.bindings,
      bindingProof: derived.proof,
      liveCensus: derived.census,
      rewrites: log,
      stageStats: { droppedTransitionLayers: wallRewrite.droppedLayers,
                    wallpaperLayersRewritten: wallRewrite.rewritten },
      captionStats: { hadRight: capRewrite.hadRight },
      // The fingerprint is taken from the LIVE tree at the same instant as the slice, so
      // text and geometry agree by construction rather than by luck.
      vendorFingerprint: P.fingerprint(frags.appRootEl),
      post: post
    };
  };

  /* Apply the SAME rewrites to the live page and stop time, so the reference still shows
   * the same text the frozen fragment carries. */
  global.__freeze_compose_live = function () {
    var root = appRoot();
    var frags = sliceFragments();
    var log = [];

    // 1. the caption column gets the same `right: 0`
    var style = frags.captionEl.getAttribute('style') || '';
    var m = /right:\s*([-\d.]+)px/.exec(style);
    if (m) {
      frags.captionEl.setAttribute('style', style.replace(/right:\s*[-\d.]+px/, 'right: 0px'));
      log.push({ kind: 'live-caption-right', before: m[1] + 'px', after: '0px' });
    }
    // 2. the chrome nodes likewise
    frags.chromeEls.forEach(function (el) {
      var s = el.getAttribute('style') || '';
      var mm = /right:\s*([-\d.]+)px/.exec(s);
      if (mm && parseFloat(mm[1]) > 100) {
        el.setAttribute('style', s.replace(/right:\s*[-\d.]+px/, 'right: 0px'));
        log.push({ kind: 'live-chrome-right', before: mm[1] + 'px', after: '0px' });
      }
    });
    // 3. keep only the ACTIVE wallpaper layer, exactly as the frozen stage does
    var layers = Array.prototype.filter.call(frags.stageEl.querySelectorAll('div'), function (d) {
      return (d.getAttribute('style') || '').indexOf('background-image') >= 0;
    });
    if (layers.length > 1) {
      for (var i = 0; i < layers.length - 1; i++) layers[i].parentNode.removeChild(layers[i]);
      log.push({ kind: 'live-dropped-transition-layers', count: layers.length - 1 });
    }
    // 4. stop the simulation: the update loop is timer-driven, so with the timers gone
    //    the DOM is a still frame and the screenshot cannot disagree with the slice.
    global.setTimeout = function () { return 0; };
    global.setInterval = function () { return 0; };
    // 5. kill the animations on both sides of the gate (the oracle's host does the same):
    //    a blinking caret or a drifting particle would otherwise differ frame by frame.
    var st = document.createElement('style');
    st.textContent = '*, *::before, *::after { animation: none !important; transition: none !important; }';
    document.head.appendChild(st);
    log.push({ kind: 'animations-disabled', where: 'vendor reference' });
    return { rewrites: log, caretStillThere: document.querySelector('.caret') !== null };
  };

  global.__freeze_done = true;
})(window);
