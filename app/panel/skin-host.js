/* ── THE SKIN HOST — a FROZEN vendor panel, mounted and driven with live data ──
 *
 * WHAT THIS IS. The owner rejected the token-only theming of the previous lane,
 * verbatim: *"eu nao quero que os outros sejam um 'bandaid' por cima. uma roupa. eu
 * quero que cada painel dos .zip que eu te mandei … sejam IGUAIS aos deles. a UNICA
 * coisa que vai mudar, e os botoes adicionais que temos."* So a skin is the
 * vendor's OWN markup for one design (`skins/<zip>/<design>.html`, bytes captured
 * from the built mockup in a real browser) plus the vendor's OWN compiled CSS,
 * mounted in a SHADOW ROOT so nothing of ours can leak in and nothing of theirs can
 * leak out. This module is the only thing that is ours: it finds the slots in the
 * frozen tree and writes audio into them.
 *
 * THE CONTRACT WITH THE REST OF THE PANEL IS ONE-WAY: `panel.js` calls in, this
 * module never calls out. `panel.js` keeps its own DOM, its own engine, its own
 * history store and its own gates — all of it hidden by `skin-layout.css` when a
 * skin is active — so a broken skin cannot take the transcription down with it, and
 * every existing oracle keeps reading the DOM it has always read.
 *
 * WHY A SHADOW ROOT. The vendor's CSS is a full Tailwind build plus their own
 * sheet: it resets `*`, styles `::-webkit-scrollbar`, and defines 9 `@keyframes`.
 * Namespacing that by hand is not possible and not desirable. Measured first
 * (`_main/_skin-owner/csp/`): an external <link> inside a shadow root loads, the
 * vendor's @keyframes resolve in that tree, an inline `style` attribute applies,
 * and a `body{}` rule does NOT reach the host — which is exactly the isolation we
 * want, and the reason `gen_skins.py` rewrites the two `html,body,#root` rules to
 * `:host`.
 *
 * WHAT IS BOUND, AND WHAT IS SILENCED. Bound: the live line (word by word, with the
 * design's own reveal class on the newest word), the accent caret, the closed lines
 * in the design's own history list, the state word, the level bars and the clock.
 * SILENCED: every number and name the mockup invented — `6 SPEAKERS`, `94% CONF`,
 * `39 wpm`, `LATER`, and the fake speaker names (`June`, `Sofia`, the per-row
 * speaker label). This panel has ONE stream, no diarization and no confidence
 * figure, so printing any of them would be a lie in the owner's own panel; the
 * design keeps the slot and loses the fiction. `panel.js` still tells the truth in
 * full in its own status line, which floats over the skin.
 */
(function () {
  'use strict';

  var MANIFEST = window.SOTTO_SKINS || null;
  var FRAGMENTS = window.SOTTO_SKIN_HTML || {};
  var hostEl = document.getElementById('skin');
  var shadow = null;
  var current = null;          // the mounted theme id
  var refs = {};               // discovered slots
  var state = {                // the last thing panel.js told us
    speaker: '',
    committed: [],
    provisional: [],
    lines: [],
    status: { word: '', state: '' },
    level: 0,
    elapsed: null,
  };
  var MAX_ROWS = 60;

  /* ── the manifest ─────────────────────────────────────────────────────── */

  function themeEntries() {
    return (MANIFEST && MANIFEST.themes) || {};
  }

  function zipEntries() {
    return (MANIFEST && MANIFEST.zips) || {};
  }

  function entryFor(id) {
    var entry = themeEntries()[id];
    return entry && typeof entry === 'object' ? entry : null;
  }

  function fragmentsFor(entry) {
    return FRAGMENTS[entry.zip + '/' + entry.design] || null;
  }

  function has(id) {
    var entry = entryFor(id);
    if (!entry) return false;
    var frag = fragmentsFor(entry);
    return !!(frag && (frag.caption || frag.panel));
  }

  /* ── mount / unmount ──────────────────────────────────────────────────── */

  function ensureShadow() {
    if (!hostEl) return null;
    if (!shadow) {
      shadow = hostEl.attachShadow ? hostEl.attachShadow({ mode: 'open' }) : null;
    }
    return shadow;
  }

  function linkSheet(href) {
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    return link;
  }

  function applyVars(node, vars) {
    if (!vars) return 0;
    var n = 0;
    for (var key in vars) {
      if (!Object.prototype.hasOwnProperty.call(vars, key)) continue;
      if (key.slice(0, 2) !== '--') continue;
      node.style.setProperty(key, String(vars[key]));
      n += 1;
    }
    return n;
  }

  /** Blank every node the mockup filled with a number or a name this panel cannot know.
   *
   * THE MOCKUP'S FICTION IS REMOVED, NOT TRANSLATED. A frozen design arrives with
   * `6 SPEAKERS`, `94% CONF`, `39 wpm`, a fake clock, eleven fake speaker names and
   * a simulated transcript — all of it true of a simulated room and none of it true
   * of this one. This panel has ONE stream, no diarization and no confidence figure,
   * so the vocabulary comes from the mockup's own `lib/scripts.ts` (packed by
   * `pack_skins.py`) and a match is blanked, plus a short list of anchored patterns
   * for the numbers. A matched BUTTON is hidden whole: an empty pill reads as a
   * broken control, and the filter chips are exactly that once the names are gone.
   */
  function silence(root, entry) {
    var zip = zipEntries()[entry.zip] || {};
    var words = {};
    var list = zip.mute || [];
    for (var i = 0; i < list.length; i += 1) words[String(list[i]).toLowerCase()] = true;
    var patterns = [];
    var raw = zip.mutePatterns || [];
    for (var p = 0; p < raw.length; p += 1) {
      try { patterns.push(new RegExp(raw[p], 'i')); } catch (err) { /* a bad pattern is skipped */ }
    }
    var brandFrom = String(zip.brandFrom || '').toLowerCase();
    var brandTo = zip.brandTo || 'sotto';
    var touched = 0;
    var all = root.querySelectorAll('*');
    for (var n = 0; n < all.length; n += 1) {
      var el = all[n];
      if (el.children.length) continue;
      var text = (el.textContent || '').trim();
      if (!text) continue;
      var low = text.toLowerCase();
      if (brandFrom && low === brandFrom) {
        // The design keeps its brand slot and wears OUR name in it: a mockup's
        // product name on the owner's screen would be the one lie he would notice.
        el.textContent = brandTo;
        touched += 1;
        continue;
      }
      var hit = words[low] === true;
      if (!hit) {
        for (var q = 0; q < patterns.length; q += 1) {
          if (patterns[q].test(text)) { hit = true; break; }
        }
      }
      if (!hit) continue;
      var button = el.closest ? el.closest('button') : null;
      if (button) {
        button.hidden = true;
      } else {
        el.textContent = '';
        el.hidden = true;
      }
      touched += 1;
    }
    return touched;
  }

  /** The word spans of the live line: the design renders them with `display:inline-block`. */
  function findWordSlots(root) {
    var best = null;
    var bestCount = 0;
    var all = root.querySelectorAll('*');
    for (var i = 0; i < all.length; i += 1) {
      var el = all[i];
      var kids = el.children;
      var count = 0;
      for (var j = 0; j < kids.length; j += 1) {
        var style = kids[j].getAttribute ? (kids[j].getAttribute('style') || '') : '';
        if (style.indexOf('inline-block') >= 0) count += 1;
      }
      if (count > bestCount) { bestCount = count; best = el; }
    }
    if (!best && bestCount === 0) return null;
    var template = null;
    var children = best.children;
    for (var k = 0; k < children.length; k += 1) {
      var st = children[k].getAttribute('style') || '';
      if (st.indexOf('inline-block') < 0) continue;
      if (!template || children[k].className.indexOf('word-in') < 0) template = children[k];
      if (children[k].className.indexOf('word-in') < 0) break;
    }
    return { host: best, template: template };
  }

  function findHistorySlots(root) {
    var scroller = root.querySelector('.quiet-scroll');
    if (!scroller) {
      var candidates = root.querySelectorAll('*');
      for (var i = 0; i < candidates.length; i += 1) {
        var cs = getComputedStyle(candidates[i]);
        if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && candidates[i].children.length > 1) {
          scroller = candidates[i];
          break;
        }
      }
    }
    if (!scroller) return null;
    var rows = [];
    for (var r = 0; r < scroller.children.length; r += 1) {
      var child = scroller.children[r];
      rows.push(child);
    }
    // A row is the repeated sibling; a lone heading is not a template.
    var template = null;
    for (var t = 0; t < rows.length; t += 1) {
      if (rows[t].querySelector && rows[t].querySelector('*')) { template = rows[t]; break; }
    }
    return { list: scroller, rows: rows, template: template };
  }

  function discover(entry) {
    var found = {};
    var captionRoot = shadow.querySelector('.skin__caption');
    if (captionRoot) {
      var slots = findWordSlots(captionRoot);
      if (slots) {
        found.captionRoot = captionRoot;
        found.wordHost = slots.host;
        found.wordTemplate = slots.template;
      }
      found.caret = captionRoot.querySelector('.caret') || null;
      found.stateWord = captionRoot.querySelector('.uppercase') || null;
    }
    var panelRoot = shadow.querySelector('.skin__panel');
    if (panelRoot) {
      var history = findHistorySlots(panelRoot);
      if (history) {
        found.panelRoot = panelRoot;
        found.historyList = history.list;
        found.historyTemplate = history.template;
      }
    }
    var chromeRoot = shadow.querySelector('.skin__chrome');
    if (chromeRoot) found.chromeRoot = chromeRoot;
    return found;
  }

  function mount(id) {
    var entry = entryFor(id);
    if (!entry) return false;
    var frag = fragmentsFor(entry);
    if (!frag) return false;
    var root = ensureShadow();
    if (!root) return false;

    while (root.firstChild) root.removeChild(root.firstChild);
    hostEl.hidden = false;

    var zip = zipEntries()[entry.zip] || {};
    root.appendChild(linkSheet('skins/skin-shim.css'));
    if (zip.css) root.appendChild(linkSheet(zip.css));

    var wrap = document.createElement('div');
    wrap.className = 'skin';
    wrap.setAttribute('data-skin-theme', id);
    var applied = applyVars(wrap, entry.vars);
    // AND ON `<body>`, so OUR floating chrome (the control cluster and the status
    // line, which live in the panel document and not in the shadow tree) wears the
    // design's own `--surface`, `--line`, `--text` and `--accent`: the owner's rule
    // is that the buttons are the one thing of ours that stays, and they read as
    // part of the design instead of as a sticker on top of it.
    applied += applyVars(document.body, entry.vars);
    var varNames = Object.keys(entry.vars || {});
    wrap.innerHTML = ''
      + '<div class="skin__stage">' + (frag.stage || '') + '</div>'
      + '<div class="skin__col">'
      + '  <div class="skin__panel">' + (frag.panel || '') + '</div>'
      + '  <div class="skin__caption">' + (frag.caption || '') + '</div>'
      + '</div>'
      + '<div class="skin__chrome">' + (frag.chrome || '') + '</div>';
    root.appendChild(wrap);

    refs = discover(entry);
    // THE ROW TEMPLATE IS TAKEN BEFORE THE FICTION IS REMOVED, and that order is the
    // whole reason it works: `silence()` blanks the mockup's own sentences and hides
    // their leaves, and a template taken afterwards has no visible text node left for
    // `paintRow` to write our line into (measured: rows=0 while our own list had the
    // line). The mock's words are removed from the ROWS we build, one row at a time.
    if (refs.historyTemplate) refs.historyTemplate = refs.historyTemplate.cloneNode(true);
    refs.vars = applied;
    refs.varNames = varNames;
    refs.silenced = silence(wrap, entry);
    // THE MOCKUP'S OWN ROWS GO, AND THE CLONE ABOVE BECOMES THEIR REPLACEMENT. The
    // frozen list holds a SIMULATED session (six scripts, dozens of invented lines);
    // ours is fed by the worker, line by line, in the design's own row.
    if (refs.historyList) {
      while (refs.historyList.firstChild) refs.historyList.removeChild(refs.historyList.firstChild);
    } else if (refs.historyTemplate && refs.historyTemplate.parentNode) {
      refs.historyTemplate.parentNode.removeChild(refs.historyTemplate);
    }
    current = id;
    document.body.setAttribute('data-skin', '1');
    document.body.setAttribute('data-skin-theme', id);
    renderLines();
    renderLive();
    renderStatus();
    renderLevel();
    return true;
  }

  function unmount() {
    if (shadow) {
      while (shadow.firstChild) shadow.removeChild(shadow.firstChild);
    }
    if (refs.varNames) {
      for (var i = 0; i < refs.varNames.length; i += 1) {
        document.body.style.removeProperty(refs.varNames[i]);
      }
    }
    if (hostEl) hostEl.hidden = true;
    refs = {};
    current = null;
    document.body.removeAttribute('data-skin');
    document.body.removeAttribute('data-skin-theme');
  }

  /* ── the live line ────────────────────────────────────────────────────── */

  function wordsOf(list) {
    var out = [];
    for (var i = 0; i < list.length; i += 1) {
      var w = list[i];
      out.push(typeof w === 'string' ? w : String((w && w.w) || ''));
    }
    return out;
  }

  function renderWords(container, template, words, liveCount, caret) {
    if (!container || !template) return 0;
    while (container.firstChild) container.removeChild(container.firstChild);
    for (var i = 0; i < words.length; i += 1) {
      if (!words[i]) continue;
      var span = template.cloneNode(true);
      span.className = i === liveCount - 1 ? 'word-in' : '';
      span.textContent = i < words.length - 1 ? words[i] + ' ' : words[i];
      container.appendChild(span);
    }
    if (caret && container.parentNode) container.parentNode.appendChild(caret);
    return words.length;
  }

  function renderLive() {
    if (!current || !refs.wordHost) return;
    var live = wordsOf(state.committed).concat(wordsOf(state.provisional));
    var lastLine = state.lines.length ? state.lines[state.lines.length - 1] : null;
    // The vendor's own fallback: with no live partial it shows the PREVIOUS line and
    // no caret (`words = partial?.words ?? previous.text.split(' ')`). Same rule here.
    if (!live.length && lastLine && lastLine.text) live = String(lastLine.text).split(' ').filter(Boolean);
    var forming = wordsOf(state.committed).length + wordsOf(state.provisional).length > 0;
    renderWords(refs.wordHost, refs.wordTemplate, live, forming ? live.length : 0,
      forming ? refs.caret : null);
    if (refs.caret) refs.caret.hidden = !forming;
    if (refs.stateWord) {
      var short = statusWord();
      if (short) refs.stateWord.textContent = short;
    }
  }

  function statusWord() {
    var word = (state.status && state.status.word) || '';
    return word;
  }

  /* ── closed lines ─────────────────────────────────────────────────────── */

  function renderLines() {
    if (!current || !refs.historyList || !refs.historyTemplate) return;
    var list = refs.historyList;
    var rows = list.querySelectorAll('[data-skin-line]');
    for (var i = rows.length - 1; i >= 0; i -= 1) rows[i].parentNode.removeChild(rows[i]);

    var template = refs.historyTemplate;
    // THE MUTE LIST LIVES ON THE THEME ENTRY, NOT ON THE LINE. `silence()`
    // reads `zipEntries()[entry.zip]`, and a closed line is `{text, time}` — it
    // carries no `zip`, so passing it resolved to `{}` and the whole word list
    // (`Sofia`, `June`, …) never applied to live rows; only the number patterns
    // did. That is how the mockup's speaker name survived into the frozen rows.
    // Resolve the theme entry once, per render, and pass THAT.
    var themeEntry = entryFor(current) || {};
    for (var n = 0; n < state.lines.length; n += 1) {
      var entry = state.lines[n];
      var row = template.cloneNode(true);
      var painted = paintRow(row, entry);
      // THE MOCKUP'S OWN NAME AND CLOCK COME OFF THE ROW WE JUST BUILT: the row
      // template is the mockup's row, so it arrives carrying a speaker this panel
      // does not have (`June`, `Sofia`) and a time that belongs to a simulated room.
      // `silence()` runs AFTER the paint, so it can never blank our own sentence.
      silence(row, themeEntry);
      row.setAttribute('data-skin-line', '1');
      row.hidden = false;
      var slots = row.querySelectorAll('[data-skin-slot]');
      for (var s = 0; s < slots.length; s += 1) slots[s].removeAttribute('data-skin-slot');
      if (painted) list.appendChild(row);
    }
    list.scrollTop = list.scrollHeight;
    if (refs.panelRoot) refs.panelRoot.setAttribute('data-skin-lines', String(state.lines.length));
  }

  /** Write one line into a cloned row: the sentence, and every number we do measure. */
  function paintRow(row, entry) {
    var text = String(entry.text || '');
    if (!text) return false;
    var target = row.querySelector('p') || row.querySelector('[data-skin-text]');
    if (!target) {
      // No paragraph: the row paints the sentence in a div/span. Take the deepest
      // element that has text and no element children.
      var all = row.querySelectorAll('*');
      var best = null;
      for (var i = 0; i < all.length; i += 1) {
        if (all[i].children.length) continue;
        if (!(all[i].textContent || '').trim()) continue;
        if (!best || (all[i].textContent || '').length > (best.textContent || '').length) best = all[i];
      }
      target = best;
    }
    if (!target) return false;
    target.textContent = text;
    // AND UNHIDE IT, WITH ITS ANCESTORS: a row the mockup had hidden (or a leaf the
    // silence pass hid) would take our line with it — the text would be there and
    // nothing would be on screen.
    var node = target;
    while (node && node !== row) {
      node.hidden = false;
      node = node.parentNode;
    }
    var times = row.querySelectorAll('time, [data-skin-time]');
    for (var t = 0; t < times.length; t += 1) {
      if (entry.time) {
        times[t].textContent = entry.time;
        times[t].hidden = false;
      }
    }
    return true;
  }

  /* ── status, level, clock ─────────────────────────────────────────────── */

  function renderStatus() {
    if (!current) return;
    var word = statusWord();
    var nodes = [];
    if (refs.captionRoot) nodes.push(refs.captionRoot);
    if (refs.chromeRoot) nodes.push(refs.chromeRoot);
    for (var i = 0; i < nodes.length; i += 1) {
      var marks = nodes[i].querySelectorAll('[data-skin-state]');
      for (var m = 0; m < marks.length; m += 1) marks[m].textContent = word;
    }
  }

  /* The vendor's own bar formula (LiveCaptions.LevelBars): five bars whose height
     and opacity are the level times a fixed multiplier. Same numbers, so the design's
     meter behaves exactly as its own mockup does. */
  var BAR_MULT = [0.5, 0.8, 1, 0.66, 0.4];

  function renderLevel() {
    if (!current || !refs.captionRoot) return;
    var meter = refs.captionRoot.querySelector('[data-skin-meter]') || refs.captionRoot.querySelector('[aria-hidden="true"]');
    if (!meter) return;
    var bars = meter.children;
    var level = Math.max(0, Math.min(1, Number(state.level) || 0));
    for (var i = 0; i < bars.length && i < BAR_MULT.length + 1; i += 1) {
      var mult = BAR_MULT[i % BAR_MULT.length];
      var height = Math.max(3, level * 13 * mult);
      bars[i].style.height = height + 'px';
      bars[i].style.opacity = String(0.35 + level * 0.6 * mult);
    }
  }

  /* ── the API panel.js uses ────────────────────────────────────────────── */

  var api = {
    get active() { return !!current; },
    get theme() { return current; },
    has: has,
    slots: function () { return refs; },
    /** The forming line. `committed` and `provisional` are arrays of tokens or strings. */
    live: function (payload) {
      payload = payload || {};
      state.speaker = payload.speaker || '';
      state.committed = payload.committed || [];
      state.provisional = payload.provisional || [];
      renderLive();
    },
    /** A line the worker closed. */
    line: function (payload) {
      payload = payload || {};
      if (!payload.text) return;
      state.lines.push({ text: payload.text, time: payload.time || '' });
      while (state.lines.length > MAX_ROWS) state.lines.shift();
      renderLines();
      renderLive();
    },
    lines: function (list) {
      state.lines = Array.isArray(list) ? list.slice(-MAX_ROWS) : [];
      renderLines();
      renderLive();
    },
    /** Short state word, and the raw state for anything the design wants to tint. */
    status: function (payload) {
      payload = payload || {};
      state.status.word = payload.word || '';
      state.status.state = payload.state || '';
      renderLive();
      renderStatus();
    },
    level: function (value) {
      state.level = value;
      renderLevel();
    },
    elapsed: function (seconds) {
      state.elapsed = seconds;
    },
    refresh: function () {
      if (!current) return false;
      renderLines();
      renderLive();
      renderStatus();
      renderLevel();
      return true;
    },
    mount: mount,
    unmount: unmount,
  };

  window.SottoSkin = api;

  /* WHICH THEME IS ON. `theme-switcher.js` writes `data-theme` on <html> and knows
     nothing about skins — one attribute is the whole interface, exactly as it is
     between the switcher and the five direction stylesheets. */
  function follow() {
    var id = document.documentElement.getAttribute('data-theme') || '';
    if (!has(id)) {
      if (current) unmount();
      return;
    }
    if (id === current) return;
    if (mount(id)) return;
    unmount();
  }

  if (hostEl) {
    hostEl.hidden = true;
    if (window.MutationObserver) {
      new MutationObserver(follow).observe(document.documentElement, {
        attributes: true, attributeFilter: ['data-theme'],
      });
    }
    follow();
  }
})();
