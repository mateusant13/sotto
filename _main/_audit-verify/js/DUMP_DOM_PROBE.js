
(() => {
  const sels = ['html', 'body', '#panel', '.panel__header', '.wordmark', '.captions', '#placeholder',
                '#caption-list', '.status', '.wordmark__name', '#clear-button', '#status',
                '.stripbar', '.captions__body'];
  const out = { viewport: [innerWidth, innerHeight],
                zoom: (window.devicePixelRatio || 1),
                body: [document.body.scrollWidth, document.body.scrollHeight],
                sheets: document.styleSheets.length, els: {},
                // WHICH SURFACE the document is actually wearing, and whether a
                // skin is still recorded on it. Both decide whether the strip
                // paints at all: `data-skin` is set by `skin-host.js` when a
                // skin mounts and removed only when it UNMOUNTS, so it survives
                // the shell's own surface switch - and a skin rule that is not
                // surface-scoped strips the strip's slab and hides its captions
                // while `#skin` is hidden there. Measured 2026-10-09 as a 100%
                // white strip; every DOMDump before this key printed "the DOM is
                // fine" while it was blank.
                surface: (document.body && document.body.dataset) ? (document.body.dataset.surface || null) : null,
                skin: !!(document.body && document.body.hasAttribute('data-skin')) };
  for (const s of sels) {
    const el = document.querySelector(s);
    if (!el) { out.els[s] = null; continue; }
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out.els[s] = { rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                   color: cs.color, display: cs.display, position: cs.position,
                   visibility: cs.visibility, opacity: cs.opacity,
                   // THE RENDER PROTECTION'S OWN EVIDENCE (owner, 2026-10-09).
                   // The window is WS_EX_LAYERED, so anything the page does not
                   // paint shows the compositor's default - WHITE. Every prior
                   // DOMDump reported only color/display/position, i.e. NOT the
                   // one property that decides whether the panel is white, and
                   // the owner was told the DOM was fine while he was looking at
                   // a blank slab. Additive on purpose: no key above was removed,
                   // so the two arms still diff on the keys they already shared.
                   bgc: cs.backgroundColor, bgi: cs.backgroundImage.slice(0, 160) };
  }
  /* THE CONTROL CLUSTER AGAINST THE PANEL'S OWN RIGHT EDGE. Added 2026-10-18.
   *
   * WHY IT IS HERE AND NOT IN A PROBE SCRIPT. Every measurement of "does the
   * header fit" taken outside this shell has been wrong on this box: headless
   * Edge clamps the layout viewport to 492px in BOTH --screenshot and --dump-dom
   * (measured 2026-10-18: `--headless=new` and `--headless=old` produce
   * BYTE-IDENTICAL 62 570-byte PNGs at `--window-size=380,900`, and the outline
   * probe reports `header r=478` in a 380-wide PNG, i.e. the 492 layout cropped
   * to 380). `shot.py`'s docstring claims --screenshot is exempt; on this
   * machine it is not. Only the WebView2 window the shell actually creates has
   * the owner's 380px, and this is the only place that asks.
   *
   * WHAT IT ANSWERS. One number per control: how far its RIGHT edge is past the
   * panel's right edge. `.panel__controls` is `flex: 0 1 auto` and the cluster
   * is 250px of six fixed-width buttons inside a 352px header row, so whether
   * the last ones are reachable is a fact, not a style opinion -- and on
   * 2026-10-18 the answer was that Hide, Pause and the caption-size button were
   * past the edge, which is three controls the owner cannot click.
   *
   * ADDITIVE, like `bgc` above: no key above is removed, so the two arms still
   * diff on the keys they already shared. */
  out.controls = (function () {
    const panel = document.querySelector('main.panel');
    const right = panel ? panel.getBoundingClientRect().right : innerWidth;
    const ctl = document.querySelector('.panel__controls');
    const list = [];
    const btns = document.querySelectorAll('.panel__controls button');
    for (let i = 0; i < btns.length; i += 1) {
      const b = btns[i];
      const r = b.getBoundingClientRect();
      const cs = getComputedStyle(b);
      list.push({ id: b.id || null,
                  left: Math.round(r.left), right: Math.round(r.right),
                  w: Math.round(r.width),
                  past_by: Math.round(Math.max(0, r.right - right)),
                  onscreen: r.right <= right + 0.5 && r.left >= -0.5,
                  display: cs.display, visibility: cs.visibility });
    }
    return { panel_right: Math.round(right), viewport_w: innerWidth,
             cluster: ctl ? (function () {
               const r = ctl.getBoundingClientRect();
               const cs = getComputedStyle(ctl);
               return { left: Math.round(r.left), right: Math.round(r.right),
                        w: Math.round(r.width), computed_w: cs.width,
                        flex: cs.flex, min_width: cs.minWidth,
                        justify_self: cs.justifySelf };
             })() : null,
             buttons: list };
  })();
  return out;
})()
