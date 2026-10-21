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
    query: '',
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

  /** The panel's own TOP/BOTTOM chrome also carries invented figures.
   *
   * `silence()` works on the theme's mute word list and the number patterns in the
   * zip manifest; it does not reach "12 lines · 39 wpm" or "Tonight · 6:02 AM" in
   * Linen/Blue Hour's footer, because those are not a speaker name or a confidence
   * figure. This panel has ONE stream and no words-per-minute meter, so both are
   * lies. Only leaves OUTSIDE the transcript scroller are touched: the row clock we
   * wrote must survive.
   */
  function silenceChrome(root, scroller) {
    var leaves = root.querySelectorAll('*');
    var touched = 0;
    for (var i = 0; i < leaves.length; i += 1) {
      var el = leaves[i];
      if (el.children.length) continue;
      if (scroller && scroller.contains(el)) continue;
      var text = (el.textContent || '').trim();
      if (!text) continue;
      var hit = /\b\d+\s*(lines?|wpm)\b/i.test(text) ||
                /\b\d{1,2}:\d{2}\s*(am|pm)\b/i.test(text) ||
                /^Tonight\s*[·-]/i.test(text);
      if (!hit) continue;
      el.textContent = '';
      el.hidden = true;
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

  /* THE TRANSCRIPT IS ONE ROW DEEP, NOT ONE SECTION DEEP.
   *
   * Measured 2026-10-21 on `cinematic-2/rainline.panel.html`: `.quiet-scroll` has
   * FIVE children and every one of them is a DAY SECTION - `div` (no class) with a
   * sticky heading plus four to six line rows. The old rule took the FIRST CHILD as
   * the row template, so each fed line cloned an entire section: the mock transcript
   * ("Every week. Twelve to two...") rode along in every clone, the sticky heading
   * was repeated for every line, and the owner's panel read as a wall of simulated
   * dialogue with one real sentence buried in it. The repeated sibling INSIDE the
   * first section is the row.
   *
   * The row's class is the identity: the same `div.group.grid...` repeats across all
   * sections. `purge` lists every one of them so `mount()` can remove the simulated
   * session without taking the day headings (the design's own chrome) with it. */
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

    // A single anonymous wrapper around the sections is not the list.
    var container = scroller;
    while (container.children.length === 1) {
      var only = container.children[0];
      if (!only.children || only.children.length < 2) break;
      container = only;
    }

    function rowOf(box) {
      var groups = {};
      var order = [];
      for (var c = 0; c < box.children.length; c += 1) {
        var child = box.children[c];
        if (!child.children || child.children.length === 0) continue;
        var key = child.tagName + '|' + (child.className || '');
        if (!groups[key]) { groups[key] = []; order.push(key); }
        groups[key].push(child);
      }
      var best = null;
      for (var k = 0; k < order.length; k += 1) {
        var group = groups[order[k]];
        if (group.length < 2) continue;
        // Prefer a row that carries a time or a paragraph: that is the line slot.
        var score = group.length + (group[0].querySelector('time, p') ? 100 : 0);
        if (!best || score > best.score) best = { row: group[0], score: score, key: order[k] };
      }
      return best;
    }

    // THE DEEPEST REPEATED GROUP IS THE ROW. At the top the repeated siblings are
    // the DAY SECTIONS (five of them, also a repeated group); one level down the
    // repeated siblings are the lines. Descending while a candidate still contains
    // a repeated group of its own lands on the line, never on a section.
    function deepRow(box, depth) {
      var here = rowOf(box);
      if (!here) return null;
      if (depth < 6) {
        var inner = deepRow(here.row, depth + 1);
        if (inner) return inner;
      }
      return here;
    }

    var found = deepRow(container, 0);
    if (!found && container !== scroller) found = deepRow(scroller, 0);
    if (!found) {
      // Last resort: the old rule, one level down only.
      for (var t = 0; t < container.children.length; t += 1) {
        if (container.children[t].querySelector && container.children[t].querySelector('*')) {
          found = { row: container.children[t], key: '' };
          break;
        }
      }
    }
    if (!found) return null;

    var template = found.row;
    var list = template.parentNode;
    // The remaining DAY SECTIONS lose every row above; a heading with no lines under
    // it is a false claim ("This afternoon, 4") and takes space from the real ones.
    var sectionPurge = [];
    if (list && list.parentNode) {
      var sibs = list.parentNode.children;
      for (var sp = 0; sp < sibs.length; sp += 1) {
        var sib = sibs[sp];
        if (sib !== list && sib.tagName === list.tagName && (sib.className || '') === (list.className || '')) {
          sectionPurge.push(sib);
        }
      }
    }
    var purge = [];
    if (found.key) {
      var all = scroller.querySelectorAll('*');
      for (var n = 0; n < all.length; n += 1) {
        var el = all[n];
        if (el.tagName + '|' + (el.className || '') === found.key) purge.push(el);
      }
    } else {
      purge = list === scroller ? [] : [template];
    }
    return { list: list, rows: [], template: template, purge: purge, sectionPurge: sectionPurge, scroller: scroller };
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
        found.historySlots = history;
        found.historyList = history.list;
        found.historyTemplate = history.template;
      }
    }
    var chromeRoot = shadow.querySelector('.skin__chrome');
    if (chromeRoot) found.chromeRoot = chromeRoot;
    return found;
  }

  /* THE OWNER'S RULE OUTRANKS THE ZIP'S ONE LIGHT DESIGN.
   *
   * `cinematic-2/linen` is the only design in the five zips built on a cream page
   * (`--page:#efe7da`, `--surface:rgba(251,247,240,.86)`, ink text). The owner's
   * standing rule (2026-10-14) is that every theme is dark; the audit of 2026-10-21
   * shipped Linen as the declared exception instead of fixing it. This is the dark
   * VARIANT: the same warm linen identity (paper ink, serif, tan accent #c98a4b,
   * green live dot) re-based on a charcoal page. Only the palette changes; the
   * vendor's markup, fonts, spacing and caption plate geometry are untouched.
   */
  var DARK_VARIANTS = {
    'cine-linen': {
      '--page': '#14110d',
      '--surface': 'rgba(28,24,19,.86)',
      '--surface-2': 'rgba(240,230,215,.06)',
      '--text': '#ece4d6',
      '--cap-bg': 'rgba(24,20,16,.9)',
      '--cap-edge': 'rgba(214,194,164,.18)',
      '--cap-text': '#f2e9da',
      '--dim': '#a99c89',
      '--line': 'rgba(220,205,182,.16)',
      '--accent': '#c98a4b',
      '--accent-2': '#7f9a88',
      '--live': '#9cba88',
      '--shadow': '0 22px 60px -34px rgba(0,0,0,.9)'
    }
  };

  function varsFor(id, entry) {
    var base = entry.vars || {};
    var dark = DARK_VARIANTS[id];
    if (!dark) return base;
    var out = {};
    for (var k in base) if (Object.prototype.hasOwnProperty.call(base, k)) out[k] = base[k];
    for (var d in dark) if (Object.prototype.hasOwnProperty.call(dark, d)) out[d] = dark[d];
    return out;
  }

  function mount(id) {
    var entry = entryFor(id);
    if (!entry) return false;
    var frag = fragmentsFor(entry);
    if (!frag) return false;
    var root = ensureShadow();
    if (!root) return false;
    var vars = varsFor(id, entry);

    while (root.firstChild) root.removeChild(root.firstChild);
    hostEl.hidden = false;

    var zip = zipEntries()[entry.zip] || {};
    root.appendChild(linkSheet('skins/skin-shim.css'));
    if (zip.css) root.appendChild(linkSheet(zip.css));

    var wrap = document.createElement('div');
    // A DARK VARIANT ALSO DARKENS THE VENDOR'S STAGE. Linen's wallpaper is the
    // cream page itself; recolouring only the vars left a light 48 px strip beside
    // the 332 px panel. The scrim sits above the stage and below the column.
    wrap.className = 'skin' + (DARK_VARIANTS[id] ? ' skin--dark' : '');
    wrap.setAttribute('data-skin-theme', id);
    var applied = applyVars(wrap, vars);
    // AND ON `<body>`, so OUR floating chrome (the control cluster and the status
    // line, which live in the panel document and not in the shadow tree) wears the
    // design's own `--surface`, `--line`, `--text` and `--accent`: the owner's rule
    // is that the buttons are the one thing of ours that stays, and they read as
    // part of the design instead of as a sticker on top of it.
    applied += applyVars(document.body, vars);
    var varNames = Object.keys(vars);
    wrap.innerHTML = ''
      + '<div class="skin__stage">' + (frag.stage || '') + '</div>'
      + (DARK_VARIANTS[id] ? '<div class="skin__scrim"></div>' : '')
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
    // SILENCE THE FICTION, NOT THE DESIGN'S OWN LABELS. The zip manifest's mute
    // list is built from the mock's whole visible vocabulary, so running it over
    // the whole tree also blanked structural chrome the design needs: the
    // "TRANSCRIPT HISTORY" eyebrow, the day headings and every filter pill. That
    // is the owner's "coisas espalhadas": borders and gap remain, the words that
    // explained them are gone. The panel's own header is now left alone; its dead
    // controls are removed by `markDeadControls()`. The scroller and the caption
    // still get the full mute list, because those DO carry the script's fiction.
    refs.silenced = 0;
    if (refs.historySlots && refs.historySlots.scroller) {
      refs.silenced += silence(refs.historySlots.scroller, entry);
    }
    if (refs.captionRoot) refs.silenced += silence(refs.captionRoot, entry);
    if (refs.chromeRoot) refs.silenced += silence(refs.chromeRoot, entry);
    refs.chromeSilenced = silenceChrome(wrap, refs.historySlots && refs.historySlots.scroller);
    // OUR STREAM HAS NO DAYS. The vendor groups a simulated multi-day session
    // under sticky day headings; our lines are one continuous run, so the day
    // heading is not chrome we can honour. Hiding it whole is honest; leaving it
    // blanked (the old `silence` did) left two rules and a gap.
    var dayHead = refs.historyList && refs.historyList.firstElementChild;
    if (dayHead) dayHead.hidden = true;
    // THE MOCKUP'S OWN ROWS GO, AND THE CLONE ABOVE BECOMES THEIR REPLACEMENT. The
    // frozen list holds a SIMULATED session (six scripts, dozens of invented lines);
    // ours is fed by the worker, line by line, in the design's own row. Only the
    // ROWS are purged - the day headings above them are the design's own chrome.
    if (refs.historySlots && refs.historySlots.purge) {
      for (var pr = 0; pr < refs.historySlots.purge.length; pr += 1) {
        var old = refs.historySlots.purge[pr];
        if (old && old.parentNode) old.parentNode.removeChild(old);
      }
      for (var sr = 0; sr < refs.historySlots.sectionPurge.length; sr += 1) {
        var sec = refs.historySlots.sectionPurge[sr];
        if (sec && sec.parentNode) sec.parentNode.removeChild(sec);
      }
      // THE SECTION'S OWN "IN PROGRESS" ROW is a second, differently-classed mock
      // row ("June in progress / You're on the night"). It survived the class-keyed
      // purge and sat under the real lines. Keep the day heading (the first child)
      // and nothing else; our lines are appended after it.
      var list = refs.historyList;
      while (list && list.children.length > 1) {
        list.removeChild(list.lastElementChild || list.lastChild);
      }
      // AND EVERY SIBLING OF THE LIST. The designs put the "in progress" mock row
      // and the footer spacer NEXT TO the day section, not inside it; the class-keyed
      // purge and the trim above both miss them, and they leaked through as a second,
      // italic transcript under the real lines. Keep the list, drop the rest.
      var sc = refs.historySlots.scroller;
      if (sc && list && list.parentNode === sc) {
        for (var ci = sc.children.length - 1; ci >= 0; ci -= 1) {
          if (sc.children[ci] !== list) sc.removeChild(sc.children[ci]);
        }
      }
      // The heading's "5" was the mock session's count, not ours.
      if (list && list.children.length) {
        var head = list.children[0];
        var leaves = head.querySelectorAll('span');
        for (var hn = 0; hn < leaves.length; hn += 1) {
          if (/^\s*\d+\s*$/.test(leaves[hn].textContent || '')) leaves[hn].textContent = '';
        }
      }
      if (refs.historyTemplate && refs.historyTemplate.parentNode) {
        refs.historyTemplate.parentNode.removeChild(refs.historyTemplate);
      }
    } else if (refs.historyList) {
      while (refs.historyList.firstChild) refs.historyList.removeChild(refs.historyList.firstChild);
    } else if (refs.historyTemplate && refs.historyTemplate.parentNode) {
      refs.historyTemplate.parentNode.removeChild(refs.historyTemplate);
    }
    markDeadControls();
    wireSearch();
    makeEmptyState();
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

  /** A dead vendor control must not look alive.
   *
   * The drawer's HIDE button and its footer (EXPORT .TXT / FOLLOW ON / CLEAR)
   * are React handlers that do not exist in a frozen tree. The footer is where
   * the live caption plate now sits; the HIDE button is the one control in the
   * panel's own header, and it does nothing. Mark both so `skin-shim.css` can
   * remove them without depending on a class name the vendor may rename.
   */
  function markDeadControls() {
    if (!refs.panelRoot) return;
    var aside = refs.panelRoot.firstElementChild;
    if (!aside) return;
    var foot = aside.lastElementChild;
    var scroller = refs.historySlots && refs.historySlots.scroller;
    if (foot && foot !== aside.firstElementChild && foot !== scroller) {
      foot.setAttribute('data-skin-footer', '1');
    }
    var headerBlock = aside.firstElementChild;
    if (!headerBlock) return;
    // Every button in the panel's header is dead in a frozen tree: the HIDE
    // control and the speaker filter chips (the mock's invented people). Removing
    // the whole chips row — not just its buttons — also removes its margin, which
    // was the empty band under the search.
    var buttons = headerBlock.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i += 1) {
      buttons[i].setAttribute('data-skin-hide', '1');
    }
    var kids = headerBlock.children;
    for (var k = 1; k < kids.length; k += 1) {
      if (kids[k].querySelector && kids[k].querySelector('button')) {
        kids[k].setAttribute('data-skin-dead-row', '1');
      }
    }
  }

  /** The vendor's search field is part of the design. Make it true.
   *
   * It used to be frozen decoration: typing filtered nothing. `renderLines()`
   * now filters `state.lines` by this query; an empty result is the designed
   * empty state, not a silent no-op.
   */
  function wireSearch() {
    if (!refs.panelRoot) return;
    var input = refs.panelRoot.querySelector('input[type="search"]') ||
                refs.panelRoot.querySelector('input');
    if (!input) return;
    refs.searchInput = input;
    input.addEventListener('input', function () {
      state.query = String(input.value || '');
      renderLines();
    });
  }

  /** With no closed line there is no transcript, and the vendor's mock rows are
   *  gone on purpose. One sentence, in the design's own dim colour, says why the
   *  list is empty. It is ours and it is true; the first real line removes it. */
  function makeEmptyState() {
    var scroller = refs.historySlots && refs.historySlots.scroller;
    if (!scroller) return;
    var el = document.createElement('div');
    el.setAttribute('data-skin-empty', '1');
    el.textContent = 'No transcript yet.';
    scroller.appendChild(el);
    refs.emptyEl = el;
  }

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

  /* THE CAPTION PLATE IS ABSOLUTE, SO IT DOES NOT CLAIM HEIGHT IN THE COLUMN.
   *
   * `skin-shim.css` composes stage / transcript / caption as a column, but every
   * caption fragment's own root is `position:absolute; bottom:6.5rem`, positioned
   * against `.skin__caption`. That box has no in-flow content, so it is 0 px tall
   * and the plate floats OVER the last transcript rows (measured 2026-10-21: the
   * live line covered the three newest rows on a full `cine-rainline` panel). The
   * reserve is the distance from the plate's TOP to the window's bottom, plus a
   * small gap, applied as the transcript's bottom margin. Recomputed on every
   * live word: the plate grows with the line.
   */
  function reserveCaption() {
    var scroller = refs.historySlots && refs.historySlots.scroller;
    if (!refs.captionRoot || !hostEl || !scroller) return;
    var plate = refs.captionRoot.firstElementChild;
    if (!plate || refs.captionRoot.hidden) {
      scroller.style.paddingBottom = '';
      return;
    }
    var hostRect = hostEl.getBoundingClientRect();
    var plateRect = plate.getBoundingClientRect();
    if (!hostRect.height || !plateRect.height) return;
    var reserve = Math.round(hostRect.bottom - plateRect.top + 12);
    if (reserve < 0) reserve = 0;
    if (reserve > hostRect.height * 0.62) reserve = Math.round(hostRect.height * 0.62);
    // PAD THE SCROLLER, DO NOT SHRINK THE PANEL. The old code set a bottom
    // margin on the panel itself, which cut the vendor's drawer short and left
    // the stage as a void (the owner's 2026-10-21 photograph). The panel is the
    // window now; the caption floats over it, and the rows get room to scroll
    // above the plate.
    scroller.style.paddingBottom = reserve + 'px';
  }

  function renderLive() {
    if (!current || !refs.wordHost) return;
    var live = wordsOf(state.committed).concat(wordsOf(state.provisional));
    // NO PREVIOUS-LINE FALLBACK (owner, 2026-10-21). The vendor's own source
    // shows the last line when there is no partial (`partial?.words ??
    // previous.text.split(' ')`), and copying that into THIS composition
    // duplicated the sentence: the closed line lives in the transcript list,
    // and the plate painted it a second time at the foot. It also made the
    // forming sentence SHRINK -- the plate swapped from the long live line to
    // the shorter previous one the instant the line committed. The plate is
    // the FORMING line, full stop; when nothing is forming it is hidden and
    // the line lives only in the list.
    var forming = wordsOf(state.committed).length + wordsOf(state.provisional).length > 0;
    // THE PLATE APPEARS WITH WORDS, NOT BEFORE THEM. The vendor's mock line is
    // silenced on mount; an empty glass plate over the panel's bottom is not a
    // design, it is a leftover. With no forming words the plate is hidden and
    // the row scroller keeps its full height.
    if (refs.captionRoot) refs.captionRoot.hidden = live.length === 0;
    renderWords(refs.wordHost, refs.wordTemplate, live, forming ? live.length : 0,
      forming ? refs.caret : null);
    if (refs.caret) refs.caret.hidden = !forming;
    if (refs.stateWord) {
      var short = statusWord();
      if (short) refs.stateWord.textContent = short;
    }
    reserveCaption();
    var sb = refs.historySlots && refs.historySlots.scroller;
    if (sb) sb.scrollTop = sb.scrollHeight;
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
    var query = String(state.query || '').trim().toLowerCase();
    var shown = 0;
    for (var n = 0; n < state.lines.length; n += 1) {
      var entry = state.lines[n];
      var text = String(entry.text || '');
      if (query && text.toLowerCase().indexOf(query) < 0) continue;
      var row = template.cloneNode(true);
      var painted = paintRow(row, entry);
      // THE MOCKUP'S OWN NAME AND CLOCK COME OFF THE ROW WE JUST BUILT: the row
      // template is the mockup's row, so it arrives carrying a speaker this panel
      // does not have (`June`, `Sofia`) and a time that belongs to a simulated room.
      // THE SECOND PAINT IS THE FIX FOR THE CLOCK. `silence()`'s number patterns also
      // match OUR "10:23:58"; with only the paint above, the time leaf was blanked
      // right after it was written (measured: every skin row had an empty 74 px time
      // column). Silence the fiction first, then write ours again and unhide it.
      silence(row, themeEntry);
      if (painted) paintRow(row, entry);
      row.setAttribute('data-skin-line', '1');
      row.hidden = false;
      var slots = row.querySelectorAll('[data-skin-slot]');
      for (var s = 0; s < slots.length; s += 1) slots[s].removeAttribute('data-skin-slot');
      if (painted) { list.appendChild(row); shown += 1; }
    }
    // THE EMPTY STATE IS OURS AND IT IS HONEST. No lines yet is the normal state
    // of a listening panel, not a rendering failure; a search with no matches is
    // the same slot with a different sentence.
    if (refs.emptyEl) {
      var empty = shown === 0;
      refs.emptyEl.hidden = !empty;
      refs.emptyEl.textContent = query && state.lines.length
        ? 'No lines match this search.'
        : 'No transcript yet.';
    }
    // A DAY HEADING WITH NO LINES UNDER IT IS A FALSE CLAIM. The vendor's section
    // is sticky chrome; with every row filtered out or none received, it is two
    // rules and a blank count. Hide the whole section and let the sentence stand.
    if (refs.historyList) refs.historyList.hidden = shown === 0;
    // THE SCROLLER IS `.quiet-scroll`, NOT THE SECTION WE APPEND TO. Setting
    // `list.scrollTop` moved nothing and every screenshot showed the OLDEST rows
    // while the newest were clipped under the footer.
    var scrollBox = (refs.historySlots && refs.historySlots.scroller) || list;
    scrollBox.scrollTop = scrollBox.scrollHeight;
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
    // Most of the twenty designs print the clock in a plain <span>; only a few use
    // <time>. Without this, the fixture's time never reached the row and the design's
    // own "05:21:18" survived in the left column. Match the SHAPE, then overwrite.
    if (!times.length) {
      var tl = row.querySelectorAll('span');
      var hit = [];
      for (var ti = 0; ti < tl.length; ti += 1) {
        if (/^\s*\d{1,2}:\d{2}(:\d{2})?\s*(am|pm)?\s*$/i.test(tl[ti].textContent || '')) {
          // MARK IT. The second paint (after `silence`) runs when the leaf is already
          // blank, so the SHAPE it was found by no longer exists; the attribute does,
          // and it puts the node back in the grid's first column (measured: without
          // it, the hidden clock let the sentence auto-place into the 74 px column).
          tl[ti].setAttribute('data-skin-time', '1');
          hit.push(tl[ti]);
        }
      }
      times = hit;
    }
    for (var t = 0; t < times.length; t += 1) {
      if (entry.time) {
        times[t].textContent = entry.time;
        times[t].hidden = false;
      }
    }
    // NO SPEAKER, NO INITIALS. Several designs print the vendor's invented person
    // as a circular avatar (`JU`, `MA`, `SO`…) inside the row. The mute list only
    // knew the full names, so the initials survived on every row (measured:
    // cine-linen showed `JU` nine times). The avatar is a column of the design;
    // keep the circle, empty it, and mark it so CSS can neutralise its speaker
    // colour. A dot is honest about one stream; a stranger's initials are not.
    var avatars = row.querySelectorAll('span, div');
    for (var a = 0; a < avatars.length; a += 1) {
      var cls = String(avatars[a].className || '');
      if (cls.indexOf('rounded-full') < 0) continue;
      if (avatars[a].children.length) continue;
      var initials = (avatars[a].textContent || '').trim();
      if (/^[A-Z]{1,3}$/.test(initials)) {
        avatars[a].textContent = '';
        avatars[a].setAttribute('data-skin-avatar', '1');
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
