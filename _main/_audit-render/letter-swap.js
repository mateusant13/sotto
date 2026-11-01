/**
 * Sotto -- letter-swap.js: the caption swap that animates BY LETTER.
 *
 * WHY: the history/transcript line gets REPLACED when the quality hand-off happens
 * (nemotron live -> parakeet redux batch, the `--redux-when-hidden` arm of the worker).
 * The old line is on screen and the new one is BETTER, so the owner should SEE which
 * letters moved instead of watching the whole row blink.
 *
 * THE RULE (from the owner's brief): character-by-character diff between the old line and
 * the new one, animating ONLY the letters that CHANGED or were INSERTED. Equal letters
 * stay exactly where they are. The inverse -- animating everything -- is the mutant the
 * oracle (`_main/letter-swap-oracle.js`) must be able to say NO to.
 *
 * WHAT IT DOES NOT DO, declared up front because a paint claim is not a byte claim:
 *   - it does NOT prove what the real WebView2 paints (nothing in this repo may launch the
 *     shell; the app is the Lead's single instance);
 *   - it does NOT touch history or routing -- it only repaints an element it is handed;
 *   - it does NOT animate ordinary provisional revisions: the swap is animated ONLY when
 *     the incoming line DECLARES a producer and the line being replaced declared another
 *     one (`producerSwap`). A live->live revision swaps silently. That gate is the point:
 *     the animation means "the batch pass just improved this line", nothing else.
 *
 * COST: ONE mutation (`replaceChildren`) per swap, and after it only compositor-cheap
 * properties (opacity + transform). No reflow of the row, no layout thrash, no work in the
 * panel's render path -- the animation is declared once and the compositor does the rest.
 * `prefers-reduced-motion: reduce` swaps the text with ZERO animation, and so does a
 * caller that cannot name both producers. An element whose children are not ours (a search
 * <mark>) is NOT rewritten at all: { skipped: true, textUnchanged: true }.
 *
 * API (the hook the panel calls):
 *   letterSwap.apply(el, oldText, newText, opts) -> stats   opts: { producer, prevProducer }
 *   letterSwap.diff(oldText, newText)             -> { segments, changedNew, ... } (DOM-free)
 *   letterSwap.changedNew(oldText, newText)       -> [newTextIndex, ...] (which letters animate)
 *   letterSwap.finish(el)                         -> unwraps the animation, back to plain text
 *   letterSwap.producerSwap({ producer, prevProducer }) -> boolean
 *
 * `prevProducer` is optional: when the caller does not know it, the module remembers the
 * last text and producer it painted INTO THAT ELEMENT (a WeakMap keyed by the element),
 * which is what makes the panel's call site a single line. An explicit `prevProducer` wins.
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.SottoLetterSwap = api;
  if (root && root.SottoLetterSwap === undefined) root.SottoLetterSwap = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /** Myers bounded by cells: past this the diff degrades to "one changed run" instead of
      exploding combinatorially on two long lines that share nothing. Degradation is
      REPORTED (`degraded: true` on the result), never silent. */
  var MYERS_MAX_CELLS = 250000;
  /** One letter's fade/rise cost, and the stagger between consecutive letters. */
  var STEP_MS = 34;
  var STAGGER_MS = 16;
  /** Hard ceiling on animated nodes per swap, so a pathological line cannot paint 900 spans. */
  var DEFAULT_MAX_ANIMATED = 72;
  /** Hard ceiling on the total stagger, so a long run cannot stretch the swap out. */
  var DEFAULT_MAX_STAGGER_MS = 420;

  var CH_CLASS = 'letter-swap__ch--new';
  var ROOT_CLASS = 'letter-swap--swapped';
  var STYLE_ID = 'sotto-letter-swap-styles';

  /** The whole animation is these two rules. Nothing here touches layout: no width, no
      margin, no font-size, no position -- only opacity and transform. */
  var STYLE_TEXT =
    '.letter-swap__ch--new{display:inline-block;' +
    'animation:sotto-letter-swap-in var(--ls-dur,34ms) cubic-bezier(.2,.8,.2,1) var(--ls-delay,0ms) both}\n' +
    '@keyframes sotto-letter-swap-in{from{opacity:0;transform:translate3d(0,-.22em,0) scale(.86)}' +
    'to{opacity:1;transform:translate3d(0,0,0) scale(1)}}\n' +
    '@media (prefers-reduced-motion: reduce){' +
    '.letter-swap__ch--new{animation:none!important;opacity:1;transform:none!important}}';

  /** The module's own memory of what it painted into an element, keyed by the element. */
  var painted = new WeakMap();
  var pending = new WeakMap();

  function prefersReducedMotion(doc) {
    try {
      var w = doc && doc.defaultView ? doc.defaultView : (typeof window !== 'undefined' ? window : null);
      if (!w || typeof w.matchMedia !== 'function') return false;
      return !!w.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) { return false; }
  }

  function positiveInt(v, fallback) {
    var n = typeof v === 'number' ? Math.floor(v) : parseInt(v, 10);
    return n > 0 ? n : fallback;
  }

  /* ------------------------------------------------------------------ *
   * The diff. Myers greedy O(ND) over the middle, prefix/suffix stripped
   * first, then a run-level re-sync so a letter that is UNCHANGED is never
   * animated just because Myers' own tie-break paired it with another one.
   * Deterministic: no map iteration order, no set order, no Date, no random.
   * ------------------------------------------------------------------ */

  /** Classic greedy Myers. Ops: -1 delete old[i], +1 insert new[j], 0 equal. */
  function myersMiddle(a, b) {
    var n = a.length, m = b.length, max = n + m;
    if (n === 0) return b.split('').map(function (c) { return [1, c]; });
    if (m === 0) return a.split('').map(function (c) { return [-1, c]; });
    var off = max, v = new Int32Array(2 * max + 1), trace = [];
    var d, k, x, y, found;
    for (d = 0; d <= max; d += 1) {
      trace.push(Int32Array.from(v));
      for (k = -d; k <= d; k += 2) {
        if (k === -d || (k !== d && v[off + k - 1] < v[off + k + 1])) x = v[off + k + 1];
        else x = v[off + k - 1] + 1;
        y = x - k;
        while (x < n && y < m && a.charCodeAt(x) === b.charCodeAt(y)) { x += 1; y += 1; }
        v[off + k] = x;
        if (x >= n && y >= m) { found = d; d = max + 1; break; }
      }
      if (found !== undefined) break;
    }
    var ops = [], px = n, py = m;
    for (d = found; d > 0; d -= 1) {
      var vd = trace[d], kk = px - py;
      var prevK = (kk === -d || (kk !== d && vd[off + kk - 1] < vd[off + kk + 1])) ? kk + 1 : kk - 1;
      var prevX = vd[off + prevK], prevY = prevX - prevK;
      while (px > prevX && py > prevY) { px -= 1; py -= 1; ops.push([0, a.charAt(px)]); }
      if (px !== prevX) { px -= 1; ops.push([-1, a.charAt(px)]); }
      else { py -= 1; ops.push([1, b.charAt(py)]); }
    }
    while (px > 0 && py > 0) { px -= 1; py -= 1; ops.push([0, a.charAt(px)]); }
    while (px > 0) { px -= 1; ops.push([-1, a.charAt(px)]); }
    while (py > 0) { py -= 1; ops.push([1, b.charAt(py)]); }
    return ops.reverse();
  }

  /**
   * diff(oldText, newText) -> the segmentation the painter consumes.
   *   segments:   [{same,text}] in NEW-text order; changed segments carry `del` = how many
   *               deletions their run held (so replaced vs inserted is exact, not a guess)
   *   changedNew: indices into newText that are changed/inserted -- the letters that animate
   *   replaced:   how many of those replace a letter that was there before
   *   inserted:   how many are genuinely new
   *   degraded:   true when the middle was too big and it fell back to one changed run
   */
  function diff(oldText, newText) {
    var oldS = typeof oldText === 'string' ? oldText : '';
    var newS = typeof newText === 'string' ? newText : '';
    var pMax = oldS.length < newS.length ? oldS.length : newS.length;
    var p = 0;
    while (p < pMax && oldS.charCodeAt(p) === newS.charCodeAt(p)) p += 1;
    var sMax = (oldS.length - p) < (newS.length - p) ? (oldS.length - p) : (newS.length - p);
    var s = 0, si = oldS.length - 1, sj = newS.length - 1;
    while (s < sMax && oldS.charCodeAt(si) === newS.charCodeAt(sj)) { s += 1; si -= 1; sj -= 1; }

    var oldMid = oldS.slice(p, oldS.length - s);
    var newMid = newS.slice(p, newS.length - s);
    var segments = [], changedNew = [], ops, degraded = false;

    if (!oldMid.length && !newMid.length) {
      segments.push({ same: true, text: newS.slice(0) });
    } else {
      // The stripped common prefix is unchanged text too: it must be painted, or the row
      // would lose its first words. (Caught by the oracle's "segments join to newText".)
      if (p > 0) segments.push({ same: true, text: newS.slice(0, p) });
      if (oldMid.length * newMid.length > MYERS_MAX_CELLS) {
        degraded = true;
        ops = [];
        for (var oi = 0; oi < oldMid.length; oi += 1) ops.push([-1, oldMid.charAt(oi)]);
        for (var ni = 0; ni < newMid.length; ni += 1) ops.push([1, newMid.charAt(ni)]);
      } else {
        ops = myersMiddle(oldMid, newMid);
      }
      // Walk the edit script in NEW-text order. A change run may contain UNCHANGED
      // letters: Myers can leave a 0 between two non-zero ops ("ro"->"com" is
      // [-1 r, +1 c, 0 o, +1 m]). Those letters are painted but NOT animated, and they must
      // keep their position, so the run is SPLIT around them instead of being reordered.
      var newIndex = p, sameBuf = '', runText = '', runDel = 0, inRun = false;
      var flushRun = function () {
        if (inRun) { segments.push({ same: false, text: runText, del: runDel }); runText = ''; runDel = 0; inRun = false; }
      };
      for (var i = 0; i < ops.length; i += 1) {
        if (ops[i][0] === 0) {
          if (inRun) { flushRun(); segments.push({ same: true, text: ops[i][1] }); inRun = true; }
          else sameBuf += ops[i][1];
          newIndex += 1;
        } else {
          if (!inRun) { inRun = true; runText = ''; runDel = 0; }
          if (ops[i][0] < 0) runDel += 1;
          else { runText += ops[i][1]; changedNew.push(newIndex); newIndex += 1; }
        }
      }
      flushRun();
      if (sameBuf) segments.push({ same: true, text: sameBuf });
      if (s > 0) segments.push({ same: true, text: newS.slice(newS.length - s) });
    }

    var replaced = 0, inserted = 0;
    for (var q = 0; q < segments.length; q += 1) {
      if (!segments[q].same) {
        var take = segments[q].text.length < (segments[q].del || 0) ? segments[q].text.length : (segments[q].del || 0);
        replaced += take;
        inserted += segments[q].text.length - take;
      }
    }
    return {
      segments: segments,
      changedNew: changedNew,
      changedChars: changedNew.length,
      replaced: replaced,
      inserted: inserted,
      degraded: degraded
    };
  }

  function changedNew(oldText, newText) {
    return diff(oldText, newText).changedNew;
  }

  /**
   * The gate. Only a line that DECLARES a producer replacing a line that declared a
   * DIFFERENT one is the quality hand-off; anything else (a provisional revision, a
   * re-commit of the same producer) swaps silently. Fail-closed on both sides.
   */
  function producerSwap(pair) {
    var a = pair && typeof pair.producer === 'string' ? pair.producer.trim() : '';
    var b = pair && typeof pair.prevProducer === 'string' ? pair.prevProducer.trim() : '';
    return !!a && !!b && a !== b;
  }

  function remember(el, text, producer) {
    if (!el) return;
    painted.set(el, { text: text, producer: producer || '' });
  }
  function rememberedProducer(el) {
    var e = el && painted.get(el);
    return e ? e.producer : '';
  }
  function clearPending(el) {
    var t = pending.get(el);
    if (t) { clearTimeout(t); pending.delete(el); }
  }

  /** Refuse the animation when something ELSE owns the children of this element (a mark,
      a bold, a search highlight). Our own letter spans are not foreign: they are exactly
      what a repeat swap replaces. Fails closed into "swap the text, animate nothing". */
  function hasForeignChild(el) {
    var kids = el.childNodes;
    for (var i = 0; i < kids.length; i += 1) {
      var node = kids[i];
      if (node.nodeType === 1 && node.className !== CH_CLASS) return true;
    }
    return false;
  }

  function ensureStyle(doc) {
    var head = doc.head;
    if (!head || typeof doc.createElement !== 'function') return;
    if (doc.getElementById(STYLE_ID)) return;
    var style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = STYLE_TEXT;
    head.appendChild(style);
  }

  function setStats(el, changed, animated) {
    el.setAttribute('data-swap-changed', String(changed));
    el.setAttribute('data-swap-animated', String(animated));
  }

  /**
   * apply(el, oldText, newText, opts). Reads the element, never assumes its shape; swaps the
   * text no matter what; animates only a producer swap, with the animation permitted.
   *
   * Returns the measured stats of what it did, which the oracle reads directly:
   * { text, changed, animated, inserted, replaced, sameChars, degraded, unchanged,
   *   reduced, skipped, swap }
   */
  function apply(el, oldText, newText, opts) {
    var options = opts || {};
    var oldS = typeof oldText === 'string' ? oldText : (el && el.textContent) || '';
    var newS = typeof newText === 'string' ? newText : '';
    var producer = typeof options.producer === 'string' ? options.producer.trim() : '';
    var explicitPrev = typeof options.prevProducer === 'string' ? options.prevProducer.trim() : '';
    var prevProducer = explicitPrev !== '' ? explicitPrev : rememberedProducer(el);
    var reduced = prefersReducedMotion(el ? el.ownerDocument : null);
    var d = diff(oldS, newS);

    if (oldS === newS) {
      remember(el, newS, producer);
      return { text: newS, changed: 0, animated: 0, inserted: 0, replaced: 0, sameChars: newS.length,
        degraded: false, unchanged: true, reduced: reduced, skipped: false, swap: false };
    }

    var isElement = !!(el && el.nodeType === 1 && el.ownerDocument && typeof el.ownerDocument.createElement === 'function');
    var isSwap = producerSwap({ producer: producer, prevProducer: prevProducer });
    var foreign = isElement && hasForeignChild(el);
    var mayAnimate = isElement && isSwap && !reduced && d.changedNew.length > 0 && !foreign;

    if (!mayAnimate) {
      // Fail closed: when something else owns the children (a search <mark>), the module
      // does NOT rewrite the element at all. It never destroys content it does not own and
      // never paints a half-correct line; the caller is told via skipped + textUnchanged.
      if (foreign) {
        return { text: el.textContent, changed: d.changedNew.length, animated: 0, inserted: d.inserted,
          replaced: d.replaced, sameChars: newS.length - d.changedNew.length, degraded: d.degraded,
          unchanged: false, reduced: reduced, skipped: true, textUnchanged: true, swap: isSwap };
      }
      if (isElement) {
        if (typeof el.replaceChildren === 'function') el.replaceChildren();
        else el.textContent = '';
        el.textContent = newS;
        setStats(el, d.changedNew.length, 0);
        el.classList.remove(ROOT_CLASS);
      }
      remember(el, newS, producer);
      return { text: newS, changed: d.changedNew.length, animated: 0, inserted: d.inserted,
        replaced: d.replaced, sameChars: newS.length - d.changedNew.length, degraded: d.degraded,
        unchanged: false, reduced: reduced, skipped: isElement ? false : true, swap: isSwap };
    }

    ensureStyle(el.ownerDocument);
    var doc = el.ownerDocument;
    var frag = doc.createDocumentFragment();
    var maxAnimated = positiveInt(options.maxAnimated, DEFAULT_MAX_ANIMATED);
    var maxStagger = positiveInt(options.maxStaggerMs, DEFAULT_MAX_STAGGER_MS);
    var animIndex = 0;
    for (var si = 0; si < d.segments.length; si += 1) {
      var seg = d.segments[si];
      // An unchanged run is ONE text node, not one per letter: fewer nodes, same paint.
      if (seg.same) { frag.appendChild(doc.createTextNode(seg.text)); continue; }
      for (var ci = 0; ci < seg.text.length; ci += 1) {
        var letter = seg.text.charAt(ci);
        if (animIndex < maxAnimated) {
          var span = doc.createElement('span');
          span.textContent = letter;
          span.className = CH_CLASS;
          span.setAttribute('data-anim-index', String(animIndex));
          span.style.setProperty('--ls-delay', Math.min(animIndex * STAGGER_MS, maxStagger) + 'ms');
          frag.appendChild(span);
          animIndex += 1;
        } else {
          frag.appendChild(doc.createTextNode(letter));
        }
      }
    }
    if (typeof el.replaceChildren === 'function') el.replaceChildren(frag);
    else { el.textContent = ''; el.appendChild(frag); }
    el.classList.add(ROOT_CLASS);
    el.style.setProperty('--ls-dur', STEP_MS + 'ms');
    setStats(el, d.changedNew.length, animIndex);
    remember(el, newS, producer);

    var total = STEP_MS + (animIndex > 0 ? Math.min((animIndex - 1) * STAGGER_MS, maxStagger) : 0);
    clearPending(el);
    if (typeof setTimeout === 'function') {
      pending.set(el, setTimeout(function () { finish(el); }, total + 120));
    }
    return { text: newS, changed: d.changedNew.length, animated: animIndex, inserted: d.inserted,
      replaced: d.replaced, sameChars: newS.length - d.changedNew.length, degraded: d.degraded,
      unchanged: false, reduced: reduced, skipped: false, swap: true };
  }

  /**
   * finish(el): drop the animation and leave PLAIN TEXT (a single text node), exactly the
   * shape the element had before the swap. Returns the number of letter spans unwrapped.
   */
  function finish(el) {
    if (!el || el.nodeType !== 1) return 0;
    clearPending(el);
    var kids = el.childNodes, spans = 0, text = '';
    for (var i = 0; i < kids.length; i += 1) {
      if (kids[i].nodeType === 1) { spans += 1; text += kids[i].textContent || ''; }
      else text += kids[i].data || '';
    }
    var doc = el.ownerDocument;
    if (doc && doc.createTextNode && typeof el.replaceChildren === 'function') {
      el.replaceChildren(doc.createTextNode(text));
    } else el.textContent = text;
    el.classList.remove(ROOT_CLASS);
    return spans;
  }

  return {
    apply: apply,
    diff: diff,
    changedNew: changedNew,
    producerSwap: producerSwap,
    finish: finish,
    prefersReducedMotion: prefersReducedMotion,
    CH_CLASS: CH_CLASS,
    ROOT_CLASS: ROOT_CLASS,
    STEP_MS: STEP_MS,
    STAGGER_MS: STAGGER_MS,
    MAX_ANIMATED: DEFAULT_MAX_ANIMATED,
    VERSION: 'letter-swap 1.0 (2026-10-12)'
  };
}));
