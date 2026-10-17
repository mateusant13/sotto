/* Where the panel's pixels actually go, and which of them are nobody's.
 *
 * The owner says the panel is ugly, and the screenshots show a large empty band
 * between the header and the captions. Before drawing anything, MEASURE the band:
 * the panel is `grid-template-rows: auto auto minmax(140px, 1fr) auto`, so one row
 * absorbs every spare pixel of a 900px-tall window, and which element that is
 * decides whether the emptiness is a layout bug or an intentional empty history.
 *
 * This reports, per element: the grid row it lands in, its box, and whether it has
 * any content. It also reports the header's children boxes, because the second
 * defect in the screenshots is the EQ meter colliding with the wordmark, and a
 * collision is only a fact once two rectangles overlap.
 */
import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs';

const PANEL = 'file:///H:/sotto/app/panel/panel.html';

const browser = await chromium.launch({ channel: 'msedge' });
const ctx = await browser.newContext({ viewport: { width: 380, height: 900 } });
await ctx.addInitScript(() => {
  const target = {
    setLiveEnabled(v) { return { liveEnabled: v }; },
    getStats() { return { stats: { peak: 0.4, blocks: 128 } }; },
    onStats() { return () => {}; },
    onCaption(cb) {
      queueMicrotask(() => {
        cb({ text: 'esta e a legenda que o dono esta a ler agora', meta: { source: 'device:VB-Audio' } });
        cb({ text: 'e a linha anterior, ja confirmada pelo worker', meta: { source: 'device:VB-Audio' } });
      });
      return () => {};
    },
    onStatus() { return () => {}; },
    setPanelSurface() {}, replyInfo() {}, setTheme() {},
    getTheme() { return 'theme-1'; }, setPause() {}, pointerInteractive() {},
    externalCaptions() { return []; }, onExternalCaptions() { return () => {}; },
    history: { append() {}, reveal() {}, search() { return Promise.resolve([]); },
      tail() { return Promise.resolve([]); }, root() { return Promise.resolve([]); } },
  };
  window.sotto = new Proxy(target, { get: (t, k) => (k in t ? t[k] : () => {}) });
});
const page = await ctx.newPage();
await page.goto(PANEL, { waitUntil: 'load' });
await page.waitForTimeout(900);

const report = await page.evaluate(() => {
  const panel = document.querySelector('.panel');
  const rows = [...panel.children].map((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(),
      cls: el.className || '(none)',
      id: el.id || '',
      top: Math.round(r.top), bottom: Math.round(r.bottom),
      h: Math.round(r.height), w: Math.round(r.width),
      display: cs.display,
      children: el.children.length,
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40),
    };
  });
  // The header, and whether any two of its children overlap.
  const hdr = document.querySelector('.panel__header') || document.querySelector('.chrome');
  const kids = hdr ? [...hdr.children].map((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(), cls: el.className || '',
      id: el.id || '', x: Math.round(r.x), y: Math.round(r.y),
      w: Math.round(r.width), h: Math.round(r.height),
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 18),
      position: cs.position,
      flex: cs.flex,
      gridCol: `${cs.gridColumnStart}/${cs.gridColumnEnd}`,
      gridRow: `${cs.gridRowStart}/${cs.gridRowEnd}`,
      minWidth: cs.minWidth,
    };
  }) : [];
  const overlaps = [];
  for (let i = 0; i < kids.length; i++) {
    for (let j = i + 1; j < kids.length; j++) {
      const a = kids[i], b = kids[j];
      const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (ox > 0 && oy > 0) overlaps.push({ a: a.id || a.cls, b: b.id || b.cls, ox, oy });
    }
  }
  const hcs = hdr ? getComputedStyle(hdr) : null;
  const panelBox = panel.getBoundingClientRect();
  // What is actually rendered in the caption column, row by row. A stray mark
  // under the last line is a real element with a real class; guessing at it from
  // a screenshot is how a cosmetic bug survives three redesigns.
  const list = document.querySelector('.captions__list') || document.querySelector('.captions');
  const captionKids = list ? [...list.querySelectorAll(':scope > *')].map((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(), cls: el.className || '',
      x: Math.round(r.x), y: Math.round(r.y),
      w: Math.round(r.width), h: Math.round(r.height),
      display: cs.display, text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30),
    };
  }) : [];
  // The header cannot fit 380px: measure what each control costs, because the fix
  // has to be "something gets narrower", not "something moves" -- the owner's rule
  // is that a button never changes place between themes.
  const ctl = document.querySelector('.panel__controls');
  const ctlKids = ctl ? [...ctl.children].map((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(), cls: el.className || '',
      id: el.id || '', x: Math.round(r.x), w: Math.round(r.width),
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 14),
      padding: `${cs.paddingLeft}/${cs.paddingRight}`,
    };
  }) : [];
  return {
    panel: { w: Math.round(panelBox.width), h: Math.round(panelBox.height) },
    gridRows: getComputedStyle(panel).gridTemplateRows,
    rows, header: {
      cls: hdr ? hdr.className : null, kids, overlaps,
      display: hcs ? hcs.display : null,
      columns: hcs ? hcs.gridTemplateColumns : null,
      gap: hcs ? hcs.gap : null,
      padding: hcs ? `${hcs.paddingLeft}/${hcs.paddingRight}` : null,
    },
    controls: { w: ctl ? Math.round(ctl.getBoundingClientRect().width) : 0, kids: ctlKids },
    captions: captionKids,
  };
});

console.log(`panel ${report.panel.w}x${report.panel.h}`);
console.log(`grid-template-rows: ${report.gridRows}`);
console.log('');
console.log('DIRECT CHILDREN OF .panel (grid rows, top to bottom)');
console.log('  row  id/class                     top    h   kids  text');
report.rows.forEach((r) => {
  console.log(`        ${(r.id || r.cls).padEnd(30).slice(0, 30)} ${String(r.top).padStart(4)} ${String(r.h).padStart(4)} ${String(r.children).padStart(5)}  ${r.text}`);
});
const totalH = report.panel.h;
const biggest = report.rows.reduce((a, b) => (b.h > a.h ? b : a), report.rows[0]);
console.log('');
console.log(`tallest row: ${biggest.id || biggest.cls} = ${biggest.h}px of ${totalH}px (${Math.round(100 * biggest.h / totalH)}% of the panel)`);
console.log(`  children it actually holds: ${biggest.children}  | text: "${biggest.text}"`);
console.log('');
console.log('HEADER');
console.log(`  computed display: ${report.header.display}   columns: ${report.header.columns}   gap: ${report.header.gap}   padding: ${report.header.padding}`);
console.log(`  ${'id/class'.padEnd(28)}      x    y      w    h  position     flex                 grid          min-width`);
for (const k of report.header.kids) {
  console.log(`  ${(k.id || k.cls).padEnd(28).slice(0, 28)} ${String(k.x).padStart(4)} ${String(k.y).padStart(4)} ${String(k.w).padStart(5)} ${String(k.h).padStart(4)}  ${k.position.padEnd(11)} ${(k.flex || '-').padEnd(20).slice(0, 20)} ${(k.gridCol + ' ' + k.gridRow).padEnd(13)} ${k.minWidth}`);
}
console.log(`  overlapping pairs: ${report.header.overlaps.length}`);
for (const o of report.header.overlaps) console.log(`     ${o.a}  x  ${o.b}   overlap ${o.ox}x${o.oy}px`);
console.log('');
console.log(`CONTROLS: ${report.controls.w}px wide, ${report.controls.kids.length} children`);
console.log('  id/class                      x    w  pad');
for (const k of report.controls.kids) {
  console.log(`  ${(k.id || k.cls).padEnd(28).slice(0, 28)} ${String(k.x).padStart(3)} ${String(k.w).padStart(4)}  ${k.padding}`);
}
const avail = report.panel.w - 28; // padding 14 each side, measured from the grid
const need = 57 + 12 + report.controls.w;
console.log('');
console.log(`content box ~= ${avail}px; wordmark 57 + gap 12 + controls ${report.controls.w} = ${need}px`);
console.log(`OVER by ${need - avail}px -- which is why they overlap rather than sit apart.`);
console.log('');
console.log('CAPTION COLUMN');
console.log(`  ${'class'.padEnd(42).slice(0, 42)}      x      y      w      h  display  text`);
for (const c of report.captions) {
  console.log(`  ${(c.cls || c.tag).padEnd(42).slice(0, 42)} ${String(c.x).padStart(5)} ${String(c.y).padStart(6)} ${String(c.w).padStart(6)} ${String(c.h).padStart(6)}  ${c.display.padEnd(8)} ${c.text}`);
}
const emptyish = report.captions.filter((c) => c.h < 24 && !(c.text || '').trim());
console.log(`  rows under 24px tall AND with no text: ${emptyish.length}`);
for (const c of emptyish) console.log(`     .${c.cls}  ${c.w}x${c.h} at (${c.x},${c.y})  display=${c.display}`);

// The stray vertical bar under the last line. A screenshot shows it; this says
// what it is. Narrow AND tall AND no text of its own = a mark, a caret or a
// stray border, and each of those is a different bug.
const slivers = await page.evaluate(() => [...document.querySelectorAll('.panel *')]
  .map((el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return (r.width > 0 && r.width <= 26 && r.height >= 12 && r.top > 740)
      ? {
        cls: (el.className && el.className.baseVal !== undefined ? el.tagName : el.className)
          || el.tagName.toLowerCase(),
        tag: el.tagName.toLowerCase(),
        x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
        bg: cs.backgroundColor, border: `${cs.borderLeftWidth}/${cs.borderTopWidth}`,
        text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 20),
      }
      : null;
  })
  .filter(Boolean));
console.log('');
console.log(`NARROW TALL ELEMENTS IN THE CAPTION AREA (w<=20, h>=16, below y=700): ${slivers.length}`);
for (const s of slivers) {
  console.log(`  .${String(s.cls).slice(0, 46).padEnd(46)} ${s.w}x${s.h} at (${s.x},${s.y})  bg=${s.bg}  border=${s.border}  "${s.text}"`);
}
await browser.close();