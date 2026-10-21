/* probe-panel.js -- WHAT THE OWNER'S 380 px PANEL ACTUALLY MEASURES.
 *
 * Run by cdp.mjs at the emulated 380x900 layout viewport (see cdp.mjs for why
 * headless Edge's own --screenshot cannot be used for this).
 *
 * It answers four questions with numbers:
 *   1. how wide is the column the caption text actually gets, after the time
 *      column, the grid gap and the two paddings;
 *   2. how big is the caption text there (the resolved px of the theme's clamp);
 *   3. does the line OVERFLOW its cell (scrollWidth > clientWidth) or does it
 *      WRAP (number of line boxes) -- the two are different failures and the
 *      owner said both ("nao encaixam direito OU truncam");
 *   4. does anything in the panel stick out past the panel's right edge.
 */
(() => {
  const q = (s) => document.querySelector(s);
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const r2 = (n) => Math.round(n * 100) / 100;

  const rect = (el) => {
    const r = el.getBoundingClientRect();
    return { x: r2(r.x), y: r2(r.y), w: r2(r.width), h: r2(r.height),
             right: r2(r.right), bottom: r2(r.bottom) };
  };

  const out = {
    viewport: [window.innerWidth, window.innerHeight],
    theme: document.documentElement.dataset.theme || null,
    surface: document.body.dataset.surface || null,
  };

  /* THE DESIGN, AS THE NATIVE OVERLAY MUST WEAR IT. `brand-bridge.js` measures
     the off-screen probe with the SAME cascade the screenshot shows, so this is
     the value the real caption receives -- not a hand-written copy of it. The
     native stills (`native-caption-shot.py --from-json`) read this object. */
  try {
    out.brand = (window.SottoBrand &&
      typeof window.SottoBrand.snapshot === 'function')
      ? window.SottoBrand.snapshot() : null;
  } catch (err) {
    out.brand = null;
  }

  const panel = q('main.panel');
  out.panel = panel ? rect(panel) : null;
  const panelRight = panel ? panel.getBoundingClientRect().right : window.innerWidth;

  const rows = qa('#caption-list > li.caption');
  out.captions = rows.map((li) => {
    const t = li.querySelector('.caption__text');
    const tm = li.querySelector('.caption__time');
    const cs = t ? getComputedStyle(t) : null;
    const cstm = tm ? getComputedStyle(tm) : null;
    const tr = t ? t.getBoundingClientRect() : null;
    /* THE WRAPPED LINE COUNT. `getClientRects()` on a grid item returns ONE rect
       (the item is a block box), so the count has to come from the box height
       divided by the line box -- which is what the eye sees. */
    let lines = null;
    if (tr && cs) {
      const lh = parseFloat(cs.lineHeight);
      if (lh > 0) lines = Math.round((tr.height / lh) * 100) / 100;
    }
    return {
      cls: String(li.className),
      text: t ? t.textContent : null,
      row: rect(li),
      textBox: t ? rect(t) : null,
      timeBox: tm ? rect(tm) : null,
      fontSize: cs ? cs.fontSize : null,
      lineHeight: cs ? cs.lineHeight : null,
      letterSpacing: cs ? cs.letterSpacing : null,
      fontFamily: cs ? cs.fontFamily : null,
      fontWeight: cs ? cs.fontWeight : null,
      textTransform: cs ? cs.textTransform : null,
      whiteSpace: cs ? cs.whiteSpace : null,
      overflowWrap: cs ? cs.overflowWrap : null,
      hyphens: cs ? cs.hyphens : null,
      clientW: t ? t.clientWidth : null,
      scrollW: t ? t.scrollWidth : null,
      overflowX: t ? Math.round(t.scrollWidth - t.clientWidth) : null,
      lineBoxes: t ? t.getClientRects().length : null,
      wrappedLines: lines,
      textH: tr ? r2(tr.height) : null,
      timeFontSize: cstm ? cstm.fontSize : null,
      timeW: tm ? r2(tm.getBoundingClientRect().width) : null,
      /* THE PLATE AND THE RAIL. The owner's two complaints -- "o texto comeca no
         primeiro pixel" and "sem borda esquerda" -- are exactly these numbers. */
      box: (() => {
        const s = getComputedStyle(li);
        return {
          padding: [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft].map(r2),
          background: s.backgroundColor,
          backgroundImage: s.backgroundImage,
          borderLeftWidth: r2(parseFloat(s.borderLeftWidth) || 0),
          borderLeftStyle: s.borderLeftStyle,
          borderLeftColor: s.borderLeftColor,
          borderRadius: s.borderRadius,
          textInsetX: tr && li ? r2(tr.left - li.getBoundingClientRect().left) : null,
          textInsetY: tr && li ? r2(tr.top - li.getBoundingClientRect().top) : null,
        };
      })(),
    };
  });

  const body = q('.captions__body');
  out.rail = body ? {
    rect: rect(body), clientW: body.clientWidth, scrollW: body.scrollWidth,
    overflowX: body.scrollWidth - body.clientWidth,
    clientH: body.clientHeight, scrollH: body.scrollHeight,
    overflowY: body.scrollHeight - body.clientHeight,
  } : null;

  const list = q('#caption-list');
  out.list = list ? { rect: rect(list), clientW: list.clientWidth, scrollW: list.scrollWidth,
                      overflowX: list.scrollWidth - list.clientWidth } : null;

  const h = q('.panel__header');
  out.header = h ? { rect: rect(h), clientW: h.clientWidth, scrollW: h.scrollWidth,
                     overflowX: h.scrollWidth - h.clientWidth } : null;

  const btns = qa('.panel__controls button');
  out.controls = {
    panel_right: r2(panelRight), viewport_w: window.innerWidth,
    buttons: btns.map((b) => {
      const r = b.getBoundingClientRect();
      return { id: b.id || null,
               label: (b.textContent || '').trim().slice(0, 20),
               left: r2(r.left), right: r2(r.right), w: r2(r.width),
               past_by: r2(Math.max(0, r.right - panelRight)),
               onscreen: r.right <= panelRight + 0.5 && r.left >= -0.5 };
    }),
  };

  /* EVERYTHING THAT STICKS OUT. The owner's "nao encaixam direito" is this. */
  out.overflowing = qa('main.panel *')
    .filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && r.right > panelRight + 0.5;
    })
    .slice(0, 25)
    .map((el) => {
      const r = el.getBoundingClientRect();
      return { tag: el.tagName, cls: String(el.className || '').slice(0, 60),
               right: r2(r.right), past_by: r2(r.right - panelRight) };
    });

  /* AND EVERYTHING THAT STICKS OUT **VERTICALLY**. A caption that is 4 lines
     long in a 380x900 panel pushes the rows past the rail and the panel's own
     bottom edge, and the last line of the live caption is what disappears. */
  const panelBottom = panel ? panel.getBoundingClientRect().bottom : window.innerHeight;
  out.overflowingBottom = qa('main.panel *')
    .filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && r.bottom > panelBottom + 0.5;
    })
    .slice(0, 25)
    .map((el) => {
      const r = el.getBoundingClientRect();
      return { tag: el.tagName, cls: String(el.className || '').slice(0, 60),
               bottom: r2(r.bottom), past_by: r2(r.bottom - panelBottom) };
    });

  /* THE RAIL vs ITS OWN CONTENT: the caption list's bottom against the rail's
     bottom. A negative number is content hanging below the rail. */
  if (list && body) {
    out.railVsContent = {
      railBottom: r2(body.getBoundingClientRect().bottom),
      listBottom: r2(list.getBoundingClientRect().bottom),
      past_by: r2(list.getBoundingClientRect().bottom - body.getBoundingClientRect().bottom),
      railClientH: body.clientHeight, railScrollH: body.scrollHeight,
    };
  }

  /* THE SKINS. A `cine-*` theme is not the stock panel: `skin-host.js` mounts
     the vendor design in a SHADOW ROOT and `skin-layout.css` hides our own
     caption box and transcript drawer. So for those themes the numbers that
     matter live inside the shadow root: the skin's own panel column, and the
     skin's own caption -- the one the demos put in the MIDDLE of the stage. */
  const skinEl = document.getElementById('skin');
  const shadow = skinEl && skinEl.shadowRoot;
  out.skin = null;
  if (shadow) {
    const s = { mounted: true, bodySkin: document.body.dataset.skin || null };
    const panelRoot = shadow.querySelector('.skin__panel');
    const capRoot = shadow.querySelector('.skin__caption');
    s.panel = panelRoot ? rect(panelRoot) : null;
    s.caption = capRoot ? rect(capRoot) : null;
    if (capRoot) {
      /* THE LIVE LINE: the element that carries the design's caption type. */
      const line = capRoot.querySelector('div[style*="font-size"]') ||
                   capRoot.querySelector('div');
      if (line) {
        const cs = getComputedStyle(line);
        s.live = {
          fontSize: cs.fontSize, lineHeight: cs.lineHeight,
          fontFamily: cs.fontFamily.split(',')[0].replace(/["']/g, ''),
          fontWeight: cs.fontWeight, letterSpacing: cs.letterSpacing,
          textTransform: cs.textTransform, whiteSpace: cs.whiteSpace,
          overflowWrap: cs.overflowWrap,
          rect: rect(line), clientW: line.clientWidth, scrollW: line.scrollWidth,
          overflowX: Math.round(line.scrollWidth - line.clientWidth),
        };
      }
      /* THE WORDS: the demo's caption is a sequence of per-word spans with
         `white-space: pre`, so a word is never cut in half. Count them and
         measure the widest one against the column. */
      const words = Array.from(capRoot.querySelectorAll('span[style*="inline-block"]'))
        .filter((sp) => sp.textContent.trim().length);
      s.words = {
        count: words.length,
        widest: words.length ? Math.max.apply(null, words.map((sp) =>
          Math.round(sp.getBoundingClientRect().width))) : 0,
        perWord: words.length ? words.slice(0, 3).map((sp) => sp.textContent.trim()) : [],
        whiteSpace: words.length ? getComputedStyle(words[0]).whiteSpace : null,
      };
    }
    /* THE COLUMN the caption has: the max-width wrapper inside the caption. */
    const wrap = capRoot ? capRoot.querySelector('div[style*="max-width"]') : null;
    s.captionColumn = wrap ? { w: r2(wrap.getBoundingClientRect().width),
                               maxWidth: getComputedStyle(wrap).maxWidth } : null;
    out.skin = s;
  }

  return out;
})()
