/* THE BROADCAST HEADER PROBE -- is the clock on ONE line, and does the row fit?

 * WHY THIS EXISTS (owner, 2026-10-22, with a crop of the Broadcast header):
 *     *"tu vai consertar essa coisa feia que nao faz sentido"*
 *
 * The crop showed `--:--:--:--` collapsed into a COLUMN of dashes, one character
 * per line. `_main/_design-lane/gen_themes.py` now emits `white-space: nowrap;
 * flex: none` for `.chrome__tc`; this file proves the browser agrees, because the
 * claim is about the LAYOUT, not about the CSS text.
 *
 * It measures, per themed chrome row:
 *   * the clock's box height vs its own single-line height -- if it wrapped, the box
 *     is a multiple of the line height and the ratio says how many lines;
 *   * every cell's box, so an overlap can be seen instead of guessed;
 *   * whether the row's content is wider than the row (overflow).
 *
 * And it writes a 2x crop of that row, so the screenshot shows the same pixels the
 * owner photographed.
 *
 * RUN: node _main/broadcast-header-probe.mjs
 */
import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';

const PANEL = 'file:///H:/sotto/app/panel/panel.html';
const OUT = 'H:/sotto/_main/shots/20261022-theme-matrix';
const THEMES = ['theme-2', 'pd-bcast'];

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: 'msedge' });
const ctx = await browser.newContext({ viewport: { width: 380, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto(PANEL, { waitUntil: 'load' });
await page.waitForTimeout(700);

let worst = 0;
for (const theme of THEMES) {
  await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme);
  await page.waitForTimeout(150);

  const m = await page.evaluate(() => {
    const tc = document.querySelector('.chrome--bcast .chrome__tc');
    if (!tc) return null;
    const cs = getComputedStyle(tc);
    const r = tc.getBoundingClientRect();
    const rowEl = tc.closest('.chrome');
    const rr = rowEl.getBoundingClientRect();
    const cells = [...rowEl.children].map((el) => {
      const b = el.getBoundingClientRect();
      return { cls: (el.className || '').toString().slice(0, 34), left: +b.left.toFixed(1), right: +b.right.toFixed(1), w: +b.width.toFixed(1) };
    });
    return {
      text: tc.textContent.trim(),
      w: +r.width.toFixed(1),
      h: +r.height.toFixed(1),
      lineHeight: cs.lineHeight,
      fontSize: cs.fontSize,
      whiteSpace: cs.whiteSpace,
      flex: cs.flex,
      rowW: +rr.width.toFixed(1),
      rowScrollW: rowEl.scrollWidth,
      cells,
    };
  });
  if (!m) { console.log(`${theme}: NO .chrome--bcast .chrome__tc`); continue; }

  const fs = parseFloat(m.fontSize);
  const lines = Math.round((m.h / (parseFloat(m.lineHeight) || fs * 1.2)) * 10) / 10;
  worst = Math.max(worst, lines);
  console.log(`\n=== ${theme} @380px ===`);
  console.log(`  clock "${m.text}" box=${m.w}x${m.h} font=${m.fontSize} line-height=${m.lineHeight} -> ${lines} line(s)  white-space=${m.whiteSpace} flex=${m.flex}`);
  console.log(`  row width=${m.rowW} scrollWidth=${m.rowScrollW} ${m.rowScrollW > m.rowW + 0.5 ? 'OVERFLOWS by ' + (m.rowScrollW - m.rowW).toFixed(1) + 'px' : 'fits'}`);
  for (const c of m.cells) console.log(`    ${c.cls.padEnd(34)} left=${String(c.left).padStart(6)} right=${String(c.right).padStart(6)} w=${String(c.w).padStart(6)}`);
  const file = `${OUT}/header-${theme}.png`;
  const el = await page.$('.chrome--bcast');
  if (el) await el.screenshot({ path: file });
  console.log(`  crop: ${file}`);
}

console.log(`\nWORST: the clock occupies ${worst} line(s). ${worst <= 1 ? 'PASS -- one line.' : 'FAIL -- it wrapped.'}`);
console.log(`page errors: ${errors.length}${errors.length ? ' -> ' + errors.join(' | ') : ''}`);
await browser.close();
process.exit(0);
