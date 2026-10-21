/* probe-demo.js -- THE ZIP DEMO'S OWN PANEL, MEASURED.
 *
 * Run by cdp.mjs against the OWNER'S OWN prebuilt demo bundle (the .zip
 * original, built by Vite and shipped in the zip as a single-file dist).
 *
 * The demos show their panel SCALED DOWN inside a stage (the zip2 stage prints
 * "PAINEL 380x900 . ESCALA 78%"), so every number here is reported in the
 * panel's OWN LAYOUT pixels, not in the stage's scaled pixels: the scale is
 * read from the transform matrix and divided out. The computed font-size is
 * unaffected by the transform anyway, and the layout width is the panel's own.
 *
 * WHAT IT ANSWERS:
 *   1. the panel's own box (the zip says 380x900 -- measured, not trusted);
 *   2. the LIVE line's font-size, the CLOSED lines' font-size, and the
 *      available column width for the text;
 *   3. whether the demo's line fits its own column (it must -- the demo is
 *      the reference), so the product can be compared against it.
 */
(() => {
  const q = (s) => document.querySelector(s);
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const r2 = (n) => Math.round(n * 100) / 100;

  /* THE PANEL ROOT, in the two demos that have one. */
  const root = q('.panel-in') || q('.sotto-panel') || q('.panel');
  const out = {
    url: location.href,
    viewport: [window.innerWidth, window.innerHeight],
    doc: { scrollW: document.documentElement.scrollWidth,
           scrollH: document.documentElement.scrollHeight },
    hasRoot: !!root,
  };
  if (!root) return out;

  const b = root.getBoundingClientRect();
  const m = new DOMMatrixReadOnly(getComputedStyle(root).transform === 'none'
    ? 'matrix(1,0,0,1,0,0)' : getComputedStyle(root).transform);
  const scale = m.a || 1;
  out.panel = {
    cssWidth: root.offsetWidth, cssHeight: root.offsetHeight,
    onScreen: { w: r2(b.width), h: r2(b.height), x: r2(b.x), y: r2(b.y) },
    scale: r2(scale),
    cls: String(root.className || '').slice(0, 80),
  };

  /* EVERY TEXT RUN inside the panel, with the size it is set at and the width
     it has to live in. The live line is the biggest; the closed ones recede. */
  const texts = [];
  for (const el of qa('p, span, h1, h2, h3, li')) {
    if (!root.contains(el)) continue;
    const t = (el.textContent || '').trim();
    if (!t) continue;
    const cs = getComputedStyle(el);
    const fs = parseFloat(cs.fontSize) || 0;
    if (!fs) continue;
    const r = el.getBoundingClientRect();
    texts.push({
      tag: el.tagName,
      cls: String(el.className || '').slice(0, 70),
      text: t.slice(0, 70),
      fontSize: r2(fs),
      fontFamily: cs.fontFamily.split(',')[0].replace(/["']/g, ''),
      fontWeight: cs.fontWeight,
      letterSpacing: cs.letterSpacing,
      textTransform: cs.textTransform,
      lineHeight: cs.lineHeight,
      whiteSpace: cs.whiteSpace,
      overflowWrap: cs.overflowWrap,
      /* UNSCALED width: the layout width, in the panel's own pixels. */
      w: r2(r.width / scale),
      h: r2(r.height / scale),
      scrollW: el.scrollWidth, clientW: el.clientWidth,
      lineBoxes: el.getClientRects().length,
    });
  }
  out.texts = texts;

  /* THE COLUMN: the widest text run is the panel's content width; the narrowest
     is the live line's own column. */
  const ws = texts.map((t) => t.w).filter((x) => x > 0);
  out.column = { minTextW: ws.length ? Math.min.apply(null, ws) : null,
                 maxTextW: ws.length ? Math.max.apply(null, ws) : null };

  return out;
})()
