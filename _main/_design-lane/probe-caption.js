/* probe-caption.js -- WHAT THE LIVE CAPTION OVERLAY MEASURES, per theme.
 *
 * The overlay is its own document (`app/panel/caption.html`) in its own window.
 * A print of it is COLOUR TRUTH only (AGENTS.md rule 4); this probe is the
 * number that says whether the theme reached it at all.
 *
 * The four questions, in the order the audit needs them:
 *   1. DID A THEME ARRIVE? `theme` attribute, the sheet hrefs the document
 *      actually loaded, and the resolved `--accent` / `--font` it is wearing.
 *      Today the answer is expected to be NO for every theme: caption.html
 *      loads no theme sheet. The probe exists so that is a measurement.
 *   2. HOW BIG is the live line, and how many line boxes does its box hold?
 *      `fontSize`, `lineHeight`, `lineBoxes`, `clientH`, `scrollH`.
 *   3. WHAT IS THE PLATE? background, border-left, padding, radius of the
 *      line's own box and of the column behind it. The owner's complaint --
 *      "o texto comeca no primeiro pixel" -- is a padding of 0.
 *   4. WHAT IS THE TYPE? family, weight, tracking, colour, shadow, stroke.
 *
 * Every value is computed, never read from the source: the point is what Blink
 * resolved, not what a stylesheet claims.
 */
(() => {
  const r2 = (n) => Math.round(n * 100) / 100;
  const px = (v) => {
    const n = parseFloat(v);
    return Number.isFinite(n) ? r2(n) : v;
  };
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r2(r.x), y: r2(r.y), w: r2(r.width), h: r2(r.height),
             right: r2(r.right), bottom: r2(r.bottom) };
  };
  const style = (el) => {
    if (!el) return null;
    const s = getComputedStyle(el);
    return {
      fontFamily: s.fontFamily,
      fontSize: px(s.fontSize),
      fontWeight: s.fontWeight,
      lineHeight: px(s.lineHeight),
      letterSpacing: s.letterSpacing,
      wordSpacing: s.wordSpacing,
      color: s.color,
      background: s.backgroundColor,
      backgroundImage: s.backgroundImage,
      borderLeft: s.borderLeftWidth + ' ' + s.borderLeftStyle + ' ' + s.borderLeftColor,
      borderRadius: s.borderRadius,
      padding: [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft].map(px),
      margin: [s.marginTop, s.marginRight, s.marginBottom, s.marginLeft].map(px),
      textShadow: s.textShadow,
      textTransform: s.textTransform,
      webkitTextStroke: s.webkitTextStrokeWidth + ' ' + s.webkitTextStrokeColor,
      paintOrder: s.paintOrder,
      overflowWrap: s.overflowWrap,
      wordBreak: s.wordBreak,
      whiteSpace: s.whiteSpace,
      textAlign: s.textAlign,
      display: s.display,
      opacity: s.opacity,
    };
  };
  /* Line boxes are counted from the resolved line-height and the content
     height; clientHeight includes padding, so the padding is subtracted. */
  const lineBoxes = (el) => {
    if (!el) return 0;
    const s = getComputedStyle(el);
    const lh = parseFloat(s.lineHeight);
    if (!Number.isFinite(lh) || lh <= 0) return 0;
    const content = el.scrollHeight - parseFloat(s.paddingTop) - parseFloat(s.paddingBottom);
    return Math.max(0, Math.round(content / lh));
  };
  const q = (s) => document.querySelector(s);
  const cs = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const line = q('#caption-float-line') || q('.caption-float__line');
  const prev = q('#caption-float-prev') || q('.caption-float__prev');
  const col = q('.caption-float__col');
  const stage = q('.caption-float__stage');
  const float = q('#caption-float') || q('.caption-float');

  const sheets = Array.from(document.styleSheets).map((s) => {
    try { return s.href ? s.href.split('/').slice(-2).join('/') : '(inline)'; }
    catch (e) { return '(blocked)'; }
  });

  return {
    viewport: [window.innerWidth, window.innerHeight],
    /* THE SAME TOKENS THE SHELL RECEIVES, measured from the panel's own probe.
       The float doc is one document with the panel (`surface.js`), so the brand
       bridge is present here too. */
    brand: (window.SottoBrand &&
      typeof window.SottoBrand.snapshot === 'function')
      ? window.SottoBrand.snapshot() : null,
    doc: {
      theme: document.documentElement.dataset.theme || null,
      themeExplicit: document.documentElement.getAttribute('data-theme'),
      captionDoc: document.documentElement.getAttribute('data-caption-doc'),
      float: document.documentElement.getAttribute('data-float'),
      visibility: getComputedStyle(document.documentElement).visibility,
      htmlBackground: getComputedStyle(document.documentElement).backgroundColor,
      bodyBackground: document.body ? getComputedStyle(document.body).backgroundColor : null,
    },
    sheets,
    themeLoaded: sheets.some((h) => /themes\/(theme-|cinematic|panel-designs|zipc-panels|brand)/.test(h)),
    themeSheets: sheets.filter((h) => /themes\/(theme-|cinematic|panel-designs|zipc-panels|brand)/.test(h)),
    vars: {
      accent: cs('--accent'),
      font: cs('--font'),
      sizeCaption: cs('--size-caption'),
      leadingCaption: cs('--leading-caption'),
      weightCaption: cs('--weight-caption'),
      captionScale: cs('--caption-scale'),
      captionPrevSize: cs('--caption-prev-size'),
      surface: cs('--surface'),
      plate: cs('--plate'),
      rule: cs('--rule'),
    },
    text: {
      line: line ? line.textContent : null,
      prev: prev ? prev.textContent : null,
      characters: line ? line.textContent.length : 0,
    },
    line: { rect: rect(line), style: style(line), lineBoxes: lineBoxes(line),
            clientW: line ? line.clientWidth : null,
            scrollW: line ? line.scrollWidth : null,
            clientH: line ? line.clientHeight : null,
            scrollH: line ? line.scrollHeight : null },
    prevLine: { rect: rect(prev), style: style(prev), lineBoxes: lineBoxes(prev) },
    col: { rect: rect(col), style: style(col) },
    stage: { rect: rect(stage), style: style(stage) },
    float: { rect: rect(float), style: style(float) },
  };
})()
