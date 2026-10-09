/* Sotto — THE PANEL GEOMETRY PROBE.
 *
 * WHAT IT IS FOR. The owner, looking at the running panel (2026-10-08): *"o painel
 * do alt c nao ta estruturado certo ... parece que ta wip mesmo, inves de
 * terminado. o layout."* A judgement about ARRANGEMENT is not answerable by
 * reading CSS: the panel is a CSS grid whose rows are assigned IN DOM ORDER, the
 * five themes re-skin the header/footer, and a drawer that is open moves every
 * box below it. So this probe publishes, from the LIVE document at the shell's own
 * 380x900, the four things that can be wrong:
 *
 *   * `blocks`  — every block's REAL x / y / w / h (`getBoundingClientRect`), its
 *                 computed `display`/`visibility`, whether it is `hidden`, and its
 *                 own `scrollHeight` vs `clientHeight` (content cut off INSIDE it);
 *   * `order`   — the direct children of `.panel` in DOCUMENT order, with the
 *                 computed display each one paints with. This is the fact the
 *                 layout rule is about: the row template is assigned in this
 *                 order, so a block moved in the markup moves in the grid;
 *   * `overlaps`— every pair of LAID-OUT top-level blocks whose rects intersect,
 *                 with the intersection AREA. Zero is the only acceptable count;
 *   * `clipped` — every laid-out block whose rect leaves the panel's own content
 *                 box, and every block whose content is taller than its box while
 *                 `overflow` is not `auto`/`scroll` (i.e. silently cut).
 *
 * IT REFUSES TO MEASURE A GEOMETRY NOBODY SEES: it asserts `innerWidth === 380`
 * and `innerHeight === 900` from inside the frame and reports both, so a wrong
 * viewport is a FAILURE in the payload and not a silent re-measurement. (The
 * previous lane measured that `--window-size=380,900` alone leaves
 * `innerWidth=492`; the frame is what makes the number real.)
 *
 * IT DRIVES THE REAL `panel.js`: a worker-shaped stream of growing partials goes
 * through the audit stub bridge, so the live box has REAL rows and the real
 * `renderProvisional`/`addCaption` paths decide the heights. `state=expanded`
 * clicks the transcript drawer's own toggle, because a drawer that is open is the
 * state in which the live box is squeezed — the state the owner is most likely
 * looking at.
 *
 * HOW IT GETS OUT. Same-origin beacon (`new Image()`) to the arm's own HTTP
 * server, plus `document.title` as a second copy so a refused beacon is still
 * visible. The document is served over `http://127.0.0.1` and NOT `file://`, for
 * the reason the cost arm already measured: a `file://` origin may not reach a
 * loopback address, and widening the CSP would mean measuring a document that
 * differs from the shipped panel.
 */

(function () {
  'use strict';

  var params = {};
  String(location.hash || '').replace(/^#/, '').split('&').forEach(function (kv) {
    var i = kv.indexOf('=');
    if (i > 0) params[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1));
  });

  var THEME = params.theme || 'theme-1';
  var PORT = params.port || '';
  var STATE = params.state || 'live';
  var ARM = params.arm || 'real';
  var ROWS = Number(params.rows || 10);
  var HOLD = params.hold === '1' || params.hold === 'true';
  var SURFACE = params.surface || '';
  var beacon = null;

  /* AN INSTRUMENT THAT CANNOT SAY "I CRASHED" IS NOT AN INSTRUMENT. The first
   * version of this probe died silently: every asset loaded, the probe was
   * served, and the arm reported NO BEACON with nothing anywhere saying why. The
   * crash channel is what turned that into a readable line. */
  function beaconRaw(obj) {
    try {
      beacon = new Image();
      beacon.src = 'http://127.0.0.1:' + PORT + '/report?payload='
        + encodeURIComponent(JSON.stringify(obj));
    } catch (e) { /* nothing left to do: the title still carries it */ }
    try { document.title = 'geom ' + JSON.stringify(obj); } catch (e) {}
  }
  window.addEventListener('error', function (ev) {
    beaconRaw({
      arm: ARM, theme: THEME, state: STATE, crashed: true,
      message: String(ev.message || ''),
      at: String(ev.filename || '') + ':' + ev.lineno + ':' + ev.colno,
      stack: String((ev.error && ev.error.stack) || '')
    });
  });

  /** Every block the arrangement claim is made of. */
  var BLOCKS = [
    ['panel', '#panel'],
    ['header', '.panel__header'],
    ['controls', '.panel__controls'],
    ['live', '#captions'],
    ['liveBar', '.captions__bar'],
    ['liveBody', '#captions-body'],
    ['liveList', '#caption-list'],
    ['placeholder', '#placeholder'],
    ['stripbar', '#strip-controls'],
    ['history', '#history'],
    ['historyBar', '.history__bar'],
    ['historyNote', '#transcript-note'],
    ['historyBody', '#history-body'],
    ['historyList', '#history-list'],
    ['status', '#status'],
    ['statusText', '#status-text']
  ];

  /** The blocks that share the panel's column — the ones that can overlap. */
  var TOP = ['header', 'live', 'stripbar', 'history', 'status'];

  function r(n) { return Math.round(n * 10) / 10; }

  function rectOf(el) {
    var b = el.getBoundingClientRect();
    return { x: r(b.left), y: r(b.top), w: r(b.width), h: r(b.height),
             right: r(b.right), bottom: r(b.bottom) };
  }

  function measureBlock(name, sel) {
    var el = document.querySelector(sel);
    if (!el) return { missing: true };
    var cs = getComputedStyle(el);
    var laidOut = cs.display !== 'none' && cs.visibility !== 'hidden'
      && el.getBoundingClientRect().width > 0 && el.getBoundingClientRect().height > 0;
    return {
      sel: sel,
      rect: rectOf(el),
      display: cs.display,
      visibility: cs.visibility,
      opacity: cs.opacity,
      hiddenAttr: el.hasAttribute('hidden') ? el.getAttribute('hidden') : null,
      laidOut: laidOut,
      overflowY: cs.overflowY,
      clientH: el.clientHeight,
      scrollH: el.scrollHeight,
      // Content taller than the box while the box cannot scroll = silently cut.
      cutInside: (el.scrollHeight > el.clientHeight + 1)
        && (cs.overflowY !== 'auto' && cs.overflowY !== 'scroll'),
      scrolls: (el.scrollHeight > el.clientHeight + 1)
        && (cs.overflowY === 'auto' || cs.overflowY === 'scroll'),
      childCount: el.children ? el.children.length : null
    };
  }

  /** Direct children of a container, so an overflowing box can be attributed. */
  function childrenOf(sel) {
    var el = document.querySelector(sel);
    if (!el) return null;
    return Array.prototype.map.call(el.children, function (c) {
      var cs = getComputedStyle(c);
      var b = c.getBoundingClientRect();
      return {
        tag: c.tagName.toLowerCase(),
        cls: String(c.className || ''),
        display: cs.display,
        rect: { x: r(b.left), y: r(b.top), w: r(b.width), h: r(b.height) }
      };
    });
  }

  function overlaps(blocks, panelRect) {    var out = [];
    var names = TOP.filter(function (n) { return blocks[n] && blocks[n].laidOut; });
    for (var i = 0; i < names.length; i += 1) {
      for (var j = i + 1; j < names.length; j += 1) {
        var a = blocks[names[i]].rect;
        var b = blocks[names[j]].rect;
        var w = Math.min(a.right, b.right) - Math.max(a.x, b.x);
        var h = Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y);
        if (w > 0.5 && h > 0.5) {
          out.push({ a: names[i], b: names[j], area: r(w * h), w: r(w), h: r(h) });
        }
      }
    }
    return out;
  }

  function clipped(blocks, panelRect) {
    var out = [];
    // ONLY THE BLOCKS THAT SHARE THE PANEL'S OWN COLUMN. A caption row inside
    // `#captions-body` leaves the panel's box BY DESIGN — that box is
    // `overflow-y: auto` and a caption list is SUPPOSED to be taller than it. The
    // claim here is about the panel's rows overlapping or being cut, so the
    // content of a scroll container is not evidence either way. (The first
    // version flagged `liveList` and reported a defect that was the product
    // working.)
    TOP.forEach(function (name) {
      var b = blocks[name];
      if (!b || !b.laidOut) return;
      var r2 = b.rect;
      var over = [];
      if (r2.x < panelRect.x - 0.5) over.push('left');
      if (r2.y < panelRect.y - 0.5) over.push('top');
      if (r2.right > panelRect.right + 0.5) over.push('right');
      if (r2.bottom > panelRect.bottom + 0.5) over.push('bottom');
      if (over.length) out.push({ block: name, edges: over, rect: r2 });
    });
    return out;
  }

  /* ── the caption stream, on REAL timers ─────────────────────────────────── */
  var WORDS = ('o som chega antes da imagem e a legenda nasce enquanto a frase ainda '
    + 'esta em formacao cada palavra provisoria carrega uma pequena duvida quando a '
    + 'frase fecha ela ganha peso e fica ninguem le uma legenda as pessoas apenas '
    + 'acompanham o painel escuta tudo mas nao interrompe nada e a linha viva cresce '
    + 'debaixo do historico').split(' ');

  var base = 0;
  var word = 0;
  var lines = 0;
  var held = false;

  function tick() {
    if (lines >= ROWS) return;
    // ── HOLD: STOP WITH A LINE STILL FORMING ────────────────────────────────
    // The screenshot the owner's item 1 owes has to show a LIVE line beside a
    // CLOSED one — that is the pair that proves the clock survived while the
    // ordinal went. A stream that closes every line leaves nothing forming, so
    // this mode closes ROWS-1 lines and then pushes ONE partial on a NEW `start`
    // (a partial on a committed `start` would REVISE the closed row instead of
    // forming a new one) and stops the timer, leaving it forming.
    if (HOLD && lines >= ROWS - 1) {
      if (!held) {
        held = true;
        base += 4;
        word += 4;
        window.sotto.pushCaption(WORDS.slice(0, word).join(' '),
          { start: base, end: base + word * 0.3, final: false });
      }
      return;
    }
    if (word >= WORDS.length) { word = 0; base += 4; }
    word += 4;
    var text = WORDS.slice(0, word).join(' ');
    window.sotto.pushCaption(text, { start: base, end: base + word * 0.3, final: false });
    if (word >= WORDS.length) {
      // close the line so the next one APPENDS a row instead of rewriting this one
      window.sotto.pushCaption(text + '.', { start: base, end: base + word * 0.3, final: true });
      lines += 1;
      word = 0;
      base += 4;
    }
    setTimeout(tick, 16);
  }

  function setTheme(name) {
    if (window.SottoTheme && typeof window.SottoTheme.set === 'function') {
      window.SottoTheme.set(name, { persist: false });
    }
    document.documentElement.setAttribute('data-theme', name);
  }

  function report() {
    var panel = document.querySelector('#panel');
    var panelRect = panel ? rectOf(panel) : { x: 0, y: 0, w: 0, h: 0, right: 0, bottom: 0 };
    var blocks = {};
    BLOCKS.forEach(function (pair) { blocks[pair[0]] = measureBlock(pair[0], pair[1]); });

    var order = [];
    if (panel) {
      Array.prototype.forEach.call(panel.children, function (el) {
        order.push({
          tag: el.tagName.toLowerCase(),
          id: el.id || null,
          cls: el.className || null,
          display: getComputedStyle(el).display
        });
      });
    }

    var laid = TOP.filter(function (n) { return blocks[n] && blocks[n].laidOut; });
    var flex = laid.slice().sort(function (a, b) {
      return blocks[b].rect.h - blocks[a].rect.h;
    })[0] || null;

    var liveIdx = -1;
    var histIdx = -1;
    order.forEach(function (o, i) {
      if (o.id === 'captions') liveIdx = i;
      if (o.id === 'history') histIdx = i;
    });

    var controlsInHeader = (function () {
      var c = document.querySelector('.panel__controls');
      var h = document.querySelector('.panel__header');
      if (!c || !h) return null;
      var cr = c.getBoundingClientRect();
      var hr = h.getBoundingClientRect();
      return {
        insideHeader: h.contains(c),
        // THE CLAIM IS "THE CONTROLS ARE ON THE HEADER ROW", i.e. the cluster's
        // box sits inside the header's box. The first version of this check
        // compared the cluster's BOTTOM to the header's MIDLINE — which a
        // vertically centred 28 px cluster can never satisfy, so it went RED on a
        // correct layout. An instrument that cannot go green on a right layout is
        // as useless as one that cannot go red on a wrong one.
        onHeaderRow: cr.top >= hr.top - 0.5 && cr.bottom <= hr.bottom + 0.5
          && cr.left >= hr.left - 0.5 && cr.right <= hr.right + 0.5,
        rect: { x: r(cr.left), y: r(cr.top), w: r(cr.width), h: r(cr.height) }
      };
    }());

    // ── WHICH HEADER BLOCK IS ON SCREEN, AND HOW MANY LINES ITS ROW TOOK ─────
    // TWO DEFECTS THIS CLOSES, both found while costing the owner's name `sotto`.
    // (1) The brand table read the FIRST `.chrome__brand` IN THE DOCUMENT — theme-2's
    // `chrome--bcast` block — on ALL FIVE THEMES, so four of the five `carrierRect`s
    // came back 0x0 (a `display:none` block) and `carrierColor` described a block that
    // was not on screen. The table LOOKED measured and was not: it agreed with the
    // one theme whose block happened to be first in the markup.
    // (2) A header that grows by 13.5 px shows up in the header's own height and
    // nowhere says WHY. An inline box that WRAPS has one client rect PER LINE, so the
    // line count of each header child is the number that names the cause.
    function isShown(el) {
      if (!el) return false;
      var cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      var b = el.getBoundingClientRect();
      return Boolean(b.width || b.height);
    }
    function headBlock() {
      var all = Array.prototype.slice.call(
        document.querySelectorAll('.panel__header .chrome[data-chrome="head"]'));
      for (var i = 0; i < all.length; i++) { if (isShown(all[i])) return all[i]; }
      return null;
    }
    // The element that CARRIES the name, on the surface that is actually up: the
    // shown header block's brand, else the wordmark (theme-1), else the strip's own
    // brand (the strip surface has no header at all).
    function shownCarrier() {
      var blk = headBlock();
      var c = blk ? blk.querySelector('.chrome__brand') : null;
      if (isShown(c)) return c;
      var wm = document.querySelector('.panel__header .wordmark__name');
      if (isShown(wm)) return wm;
      var sb = document.querySelector('.stripbar .stripbar__brand');
      return isShown(sb) ? sb : null;
    }
    function boxOf(el) {
      if (!el) return null;
      var b = el.getBoundingClientRect();
      var cs = getComputedStyle(el);
      return {
        cls: el.className, text: (el.textContent || '').trim(),
        rect: { x: r(b.left), y: r(b.top), w: r(b.width), h: r(b.height) },
        lines: el.getClientRects().length,
        display: cs.display, fontSize: cs.fontSize, lineHeight: cs.lineHeight,
        whiteSpace: cs.whiteSpace, flexWrap: cs.flexWrap, overflow: cs.overflow
      };
    }
    var headerReport = (function () {
      var blk = headBlock();
      var h = document.querySelector('.panel__header');
      var hcs = h ? getComputedStyle(h) : null;
      return {
        blockCls: blk ? blk.className : null,
        block: boxOf(blk),
        kids: blk ? Array.prototype.slice.call(blk.children).map(boxOf) : [],
        header: boxOf(h),
        headerColumns: hcs ? hcs.gridTemplateColumns : null,
        headerRows: hcs ? hcs.gridTemplateRows : null,
        headerChildCount: h ? h.childElementCount : null
      };
    }());

    var payload = {
      arm: ARM,
      theme: THEME,
      state: STATE,
      surfaceRequested: SURFACE || null,
      url: location.href,
      viewport: {
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        dpr: window.devicePixelRatio,
        exact: window.innerWidth === 380 && window.innerHeight === 900
      },
      surface: document.body.getAttribute('data-surface'),
      bodyScroll: { scrollH: document.body.scrollHeight, clientH: document.body.clientHeight },
      panelRect: panelRect,
      blocks: blocks,
      order: order,
      orderIds: order.map(function (o) { return o.id || ('<' + o.tag + '>'); }),
      derived: {
        liveIndexDom: liveIdx,
        historyIndexDom: histIdx,
        // THE OWNER'S RULE, both ways: DOM order AND the y axis.
        historyAboveLiveDom: (histIdx >= 0 && liveIdx >= 0) ? histIdx < liveIdx : null,
        historyAboveLiveY: (blocks.history && blocks.live && blocks.history.laidOut && blocks.live.laidOut)
          ? (blocks.history.rect.bottom <= blocks.live.rect.y + 0.5) : null,
        gapHistoryToLive: (blocks.history && blocks.live && blocks.history.laidOut && blocks.live.laidOut)
          ? r(blocks.live.rect.y - blocks.history.rect.bottom) : null,
        flexibleBlock: flex,
        liveHeight: blocks.live ? blocks.live.rect.h : null,
        liveBodyHeight: blocks.liveBody ? blocks.liveBody.rect.h : null,
        historyHeight: blocks.history ? blocks.history.rect.h : null,
        liveRows: blocks.liveList ? blocks.liveList.childCount : null,
        historyExpanded: (function () {
          var h = document.querySelector('#history');
          return h ? !h.classList.contains('history--collapsed') : null;
        }()),
        controlsInHeader: controlsInHeader,
        topBlocks: laid,
        sumTopHeights: r(laid.reduce(function (a, n) { return a + blocks[n].rect.h; }, 0))
      },
      overlaps: overlaps(blocks, panelRect),
      clipped: clipped(blocks, panelRect),
      // ── THE NAME `sotto`, COUNTED IN THE PAINTED DOM ────────────────────────
      // The owner asked for the name in every theme and on both surfaces, and a
      // screenshot cannot prove "all five" — this can. PAINTED means only elements
      // that are actually rendered: a `display: none` chrome block still holds its
      // text in the DOM, and counting that would report five names where the eye
      // sees one. So the walk skips anything with no layout box.
      brand: (function () {
        function visibleText(root) {
          if (!root || !root.getBoundingClientRect().width) return '';
          var out = '';
          (function walk(node) {
            Array.prototype.forEach.call(node.childNodes, function (nd) {
              if (nd.nodeType === 3) { out += nd.data; return; }
              if (nd.nodeType !== 1) return;
              var cs = getComputedStyle(nd);
              if (cs.display === 'none' || cs.visibility === 'hidden') return;
              if (!nd.getBoundingClientRect().width && !nd.getBoundingClientRect().height) return;
              walk(nd);
            });
          }(root));
          return out.replace(/\s+/g, ' ').trim();
        }
        function count(text) { return (text.match(/sotto/gi) || []).length; }
        var h = document.querySelector('.panel__header');
        var s = document.querySelector('.stripbar');
        var ht = visibleText(h);
        var st = visibleText(s);
        var el = shownCarrier();
        var r2 = el ? el.getBoundingClientRect() : null;
        return {
          headerText: ht,
          headerCount: count(ht),
          stripText: st,
          stripCount: count(st),
          // The element that CARRIES it, and its own colour/transform, so a probe
          // can prove the theme drew it (and that nothing upper-cased it).
          carrier: el ? (el.className + ' :: ' + (el.textContent || '').trim()) : null,
          carrierColor: el ? getComputedStyle(el).color : null,
          carrierTransform: el ? getComputedStyle(el).textTransform : null,
          carrierLines: el ? el.getClientRects().length : null,
          carrierFontSize: el ? getComputedStyle(el).fontSize : null,
          carrierRect: r2 ? { x: r(r2.left), y: r(r2.top), w: r(r2.width), h: r(r2.height) } : null
        };
      }()),
      // The header row, its own children, and the LINE COUNT of each — the numbers
      // that make a header that grew by 13.5 px explain itself.
      header: headerReport,
      // The owner's item 1 is a claim about the SCREEN, so it needs a paint
      // channel and not a source read: the count of ordinal elements must be ZERO
      // and the clock must still be there — the pair is the proof. `timeColors`
      // is the positive control's second half: the forming line's clock is the
      // one the owner described as YELLOW and the closed lines' as GREY, so a
      // "removed the index" that also removed the clock cannot pass.
      paint: (function () {
        var rows = Array.prototype.slice.call(document.querySelectorAll('#caption-list .caption'));
        var idx = document.querySelectorAll('#caption-list .caption__index').length;
        var times = Array.prototype.slice.call(document.querySelectorAll('#caption-list .caption__time'));
        return {
          rows: rows.length,
          indexElements: idx,
          indexTexts: Array.prototype.map.call(
            document.querySelectorAll('#caption-list .caption__index'),
            function (e) { return e.textContent; }),
          timeElements: times.length,
          timeTexts: times.map(function (e) { return e.textContent; }),
          timeColors: times.map(function (e) { return getComputedStyle(e).color; }),
          liveRowTimeColor: (function () {
            var p = document.querySelector('#caption-list .caption--provisional .caption__time');
            return p ? getComputedStyle(p).color : null;
          }()),
          closedRowTimeColor: (function () {
            var c = document.querySelector('#caption-list .caption:not(.caption--provisional) .caption__time');
            return c ? getComputedStyle(c).color : null;
          }()),
          liveRowHasLeftRail: (function () {
            var p = document.querySelector('#caption-list .caption--provisional');
            if (!p) return null;
            var cs = getComputedStyle(p);
            return cs.borderLeftStyle + ' ' + cs.borderLeftWidth + ' ' + cs.borderLeftColor;
          }()),
          // The ordinal must survive as STATE: the rows still carry it.
          dataIndex: rows.map(function (x) { return x.dataset ? x.dataset.index : null; }),
          // THE LAST ROW, named, because the screenshot's bottom line is the one a
          // reader looks at: its class says whether it is the FORMING row and its
          // colour is the positive control for that same row.
          lastRowClass: rows.length ? rows[rows.length - 1].className : null,
          lastRowTimeColor: (function () {
            var t = rows.length ? rows[rows.length - 1].querySelector('.caption__time') : null;
            return t ? getComputedStyle(t).color : null;
          }()),
          lastRowRail: (function () {
            if (!rows.length) return null;
            var cs = getComputedStyle(rows[rows.length - 1]);
            return cs.borderLeftStyle + ' ' + cs.borderLeftWidth + ' ' + cs.borderLeftColor;
          }()),
          rowTextSample: rows.slice(-2).map(function (x) {
            return (x.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 90);
          })
        };
      }()),
      diag: {
        panel: (function () {
          var el = document.querySelector('#panel');
          if (!el) return null;
          var cs = getComputedStyle(el);
          return {
            position: cs.position, inset: cs.inset, left: cs.left, top: cs.top,
            right: cs.right, bottom: cs.bottom, width: cs.width, height: cs.height,
            display: cs.display, gridTemplateRows: cs.gridTemplateRows,
            gridTemplateColumns: cs.gridTemplateColumns, overflow: cs.overflow,
            clientW: el.clientWidth, clientH: el.clientHeight,
            scrollW: el.scrollWidth, scrollH: el.scrollHeight
          };
        }()),
        root: {
          clientW: document.documentElement.clientWidth,
          clientH: document.documentElement.clientHeight,
          bodyClientW: document.body.clientWidth
        },
        headerChildren: childrenOf('.panel__header'),
        liveChildren: childrenOf('#captions'),
        historyChildren: childrenOf('#history'),
        statusChildren: childrenOf('#status'),
        // THE ROW-SIZING EXPERIMENT. When a row is sized to something none of its
        // items explains, the way to attribute it is to vary the template and
        // watch the row. Each entry sets `grid-template-rows` on the LIVE panel,
        // reads the resulting track sizes and the header's own box, and puts the
        // original back. Nothing here is a fix; it is how the anomaly was named.
        rowExperiments: (function () {
          var el = document.querySelector('#panel');
          if (!el) return null;
          var original = el.style.gridTemplateRows;
          var out = [];
          ['auto 140px auto auto', 'auto auto auto auto',
           'auto minmax(140px, 1fr) auto auto',
           'auto auto minmax(140px, 1fr) auto'].forEach(function (tpl) {
            el.style.gridTemplateRows = tpl;
            var cs = getComputedStyle(el);
            var h = document.querySelector('.panel__header');
            out.push({
              tpl: tpl,
              used: cs.gridTemplateRows,
              headerH: h ? r(h.getBoundingClientRect().height) : null,
              liveH: (function () {
                var l = document.querySelector('#captions');
                return l ? r(l.getBoundingClientRect().height) : null;
              }()),
              histH: (function () {
                var x = document.querySelector('#history');
                return x ? r(x.getBoundingClientRect().height) : null;
              }())
            });
          });
          el.style.gridTemplateRows = original;
          return out;
        }()),
        // WHY THE HEADER ROW IS 742.5 px TALL. Measured: the row is that size
        // under EVERY template tried above, so it is the HEADER's own max-content
        // height and not a track-sizing choice. These two probes turn off, one at
        // a time, the two declarations in `panel.css` that are unusual for a flex
        // bar, and re-read the row. Nothing here is a fix.
        headerHeightProbes: (function () {
          var el = document.querySelector('#panel');
          var h = document.querySelector('.panel__header');
          if (!el || !h) return null;
          var read = function () { return r(h.getBoundingClientRect().height); };
          var out = { asShipped: read(), rows: getComputedStyle(el).gridTemplateRows };
          h.style.webkitAppRegion = 'none';
          h.style.appRegion = 'none';
          out.appRegionNone = read();
          out.rowsAppRegionNone = getComputedStyle(el).gridTemplateRows;
          h.style.webkitAppRegion = '';
          h.style.appRegion = '';
          // and with the header taken out of the flex game entirely
          var kids = Array.prototype.slice.call(h.children);
          kids.forEach(function (k) { k.style.display = 'none'; });
          out.emptyHeader = read();
          out.rowsEmptyHeader = getComputedStyle(el).gridTemplateRows;
          kids.forEach(function (k) { k.style.display = ''; });
          // AND, DECISIVELY: out of the grid entirely, so its height is its OWN
          // content and not a track size it is stretched into.
          h.style.position = 'absolute';
          h.style.left = '0';
          h.style.right = '0';
          out.contentHeightAbsolute = read();
          out.contentScrollHeight = h.scrollHeight;
          out.childrenWhenAbsolute = childrenOf('.panel__header');
          // both unusual declarations off at once, still out of the grid
          h.style.webkitAppRegion = 'none';
          h.style.appRegion = 'none';
          out.contentHeightAbsoluteNoDrag = read();
          h.style.webkitAppRegion = '';
          h.style.appRegion = '';
          out.dataTheme = document.documentElement.getAttribute('data-theme');
          // AND WITH THE CHILDREN DETACHED FROM THE DOCUMENT ENTIRELY, still out
          // of the grid: the last distinction between "a child causes it" and
          // "the box itself is cursed".
          var saved = kids.map(function (k) {
            return { node: k, next: k.nextSibling };
          });
          kids.forEach(function (k) { h.removeChild(k); });
          out.emptyAbsoluteHeight = read();
          // WHAT IS LEFT INSIDE IT once the elements are gone: the node census is
          // the difference between "an empty box is 360 px tall" (impossible) and
          // "something non-element is generating line boxes".
          out.emptyNodeCensus = (function () {
            var kinds = {};
            Array.prototype.forEach.call(h.childNodes, function (nd) {
              var k = nd.nodeType === 3
                ? ('text:' + (String(nd.data).trim() ? 'NONWHITESPACE' : 'whitespace'))
                : ('type' + nd.nodeType);
              kinds[k] = (kinds[k] || 0) + 1;
            });
            return {
              kinds: kinds,
              textLen: h.textContent.length,
              textTrimLen: h.textContent.trim().length,
              innerTextLen: (h.innerText || '').trim().length,
              // THE LEAK ITSELF, verbatim, so it can be found in the source.
              leakText: (function () {
                var t = '';
                Array.prototype.forEach.call(h.childNodes, function (nd) {
                  if (nd.nodeType === 3 && String(nd.data).trim()) t += String(nd.data);
                });
                return t.slice(0, 500);
              }()),
              comments: (function () {
                var c = [];
                Array.prototype.forEach.call(h.childNodes, function (nd) {
                  if (nd.nodeType === 8) c.push(String(nd.data).slice(0, 60));
                });
                return c;
              }()),
              lineHeight: getComputedStyle(h).lineHeight,
              fontSize: getComputedStyle(h).fontSize,
              whiteSpace: getComputedStyle(h).whiteSpace
            };
          }());
          out.emptyAbsoluteOffsetH = h.offsetHeight;
          out.emptyAbsoluteClientH = h.clientHeight;
          out.emptyAbsoluteScrollH = h.scrollHeight;
          h.style.display = 'block';
          out.emptyAbsoluteBlock = read();
          h.style.display = '';
          saved.forEach(function (s) { h.insertBefore(s.node, s.next); });
          // SANITY: an explicit height must win. If it does not, the element is
          // NOT actually out of the grid and every number above is a track size.
          h.style.height = '10px';
          out.forcedTenPx = read();
          h.style.height = '';
          out.headerComputed = (function () {
            var cs = getComputedStyle(h);
            return {
              display: cs.display, height: cs.height, minHeight: cs.minHeight,
              maxHeight: cs.maxHeight, boxSizing: cs.boxSizing,
              gridRow: cs.gridRow, alignSelf: cs.alignSelf,
              webkitAppRegion: cs.webkitAppRegion
            };
          }());
          h.style.position = '';
          h.style.left = '';
          h.style.right = '';
          out.flexWrap = getComputedStyle(h).flexWrap;
          out.flexDirection = getComputedStyle(h).flexDirection;
          out.alignItems = getComputedStyle(h).alignItems;
          return out;
        }()),
        // WHICH ITEM OWNS THE 742.5 px ROW. One top-level child is hidden at a
        // time and the used track sizes are re-read, so the row can be attributed
        // to the item that produced it rather than guessed from the CSS.
        rowOwners: (function () {
          var el = document.querySelector('#panel');
          if (!el) return null;
          var out = { asShipped: getComputedStyle(el).gridTemplateRows };
          Array.prototype.forEach.call(el.children, function (c) {
            var was = c.style.display;
            c.style.display = 'none';
            var key = (c.id || c.className || c.tagName).toString().trim();
            out[key] = getComputedStyle(el).gridTemplateRows;
            c.style.display = was;
          });
          return out;
        }()),
        tallest: (function () {
          var all = document.querySelectorAll('#panel *');
          var list = [];
          Array.prototype.forEach.call(all, function (el) {
            var b = el.getBoundingClientRect();
            if (b.height > 40) {
              list.push({
                tag: el.tagName.toLowerCase(),
                cls: String(el.className || ''),
                h: r(b.height), w: r(b.width), y: r(b.top),
                display: getComputedStyle(el).display,
                minH: getComputedStyle(el).minHeight
              });
            }
          });
          list.sort(function (a, b) { return b.h - a.h; });
          return list.slice(0, 14);
        }())
      },
      cutInside: Object.keys(blocks).filter(function (n) {
        return blocks[n] && blocks[n].cutInside;
      }),
      scrollsInside: Object.keys(blocks).filter(function (n) {
        return blocks[n] && blocks[n].scrolls;
      }),
      // The strip's own height, as the shell has to set it: the custom property
      // the panel exposes for that number, and what it resolves to.
      stripVar: (function () {
        var v = getComputedStyle(document.documentElement).getPropertyValue('--strip-height');
        return v ? v.trim() : null;
      }())
    };

    var url = 'http://127.0.0.1:' + PORT + '/report?payload='
      + encodeURIComponent(JSON.stringify(payload));
    /* Held in a module-scope variable on purpose: the cost arm measured that a
     * local `Image()` is collected before the request is issued. */
    beacon = new Image();
    beacon.src = url;
    document.title = 'geom ' + JSON.stringify(payload);
  }

  function main() {
    setTheme(THEME);
    /* WHICH SURFACE. `panel` is the default and the attribute the markup ships;
     * `strip` is what the shell writes when its one control opens the short
     * surface. Setting it here is the SAME single attribute write the shell does
     * (`app/panel/surface.js` is the definition), so the strip's own geometry is
     * measured on the real document rather than on a stylesheet read. */
    if (SURFACE) document.body.setAttribute('data-surface', SURFACE);
    /* The stream first, on real timers, so the rows are the renderer's own. */
    try {
      tick();
    } catch (e) {
      beaconRaw({ arm: ARM, theme: THEME, state: STATE, crashed: true,
        message: 'tick(): ' + e.message, stack: String(e.stack || '') });
      return;
    }
    var settle = 900 + ROWS * 40;
    setTimeout(function () {
      if (STATE === 'expanded') {
        var t = document.getElementById('history-toggle');
        if (t) t.click();
      }
      /* One more frame after the click so the drawer's own transition is done
       * (the chevron rotates 140 ms; nothing else animates). */
      setTimeout(function () {
        try {
          report();
        } catch (e) {
          beaconRaw({ arm: ARM, theme: THEME, state: STATE, crashed: true,
            message: 'report(): ' + e.message, stack: String(e.stack || '') });
        }
      }, STATE === 'expanded' ? 400 : 150);
    }, settle);
  }

  if (document.readyState === 'complete') setTimeout(main, 0);
  else window.addEventListener('load', function () { setTimeout(main, 0); });
}());
