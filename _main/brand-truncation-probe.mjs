/* THE BRAND TRUNCATION PROBE -- is `sotto` wider than the box it is given?

 * WHY THIS EXISTS (owner, verbatim):
 *     *"muitas vezes a logo do sotto tá truncada ou tem algo por cima"*
 *
 * `runs/TC-20261022-c18-logo-truncada.md` derived the mechanism from the CSS
 * (`white-space: nowrap` + `min-width: 32px`, no `flex: none`, no `overflow: hidden`)
 * and produced a LOWER BOUND on the text width. A bound is not a measurement. This
 * file measures the LIVE document -- the shipped `panel.html`, in Edge, per theme and
 * under three widths -- because "truncated" is a claim about what the browser did.
 *
 * WHAT IT READS, per theme x surface x viewport:
 *   * `clientWidth`  -- the box the flex row actually gave the brand;
 *   * `scrollWidth`  -- what the text needs;
 *   * `overflow`     -- scrollWidth - clientWidth (positive = the text does not fit);
 *   * `overlap`      -- how far the brand's painted text runs under its NEXT SIBLING
 *                       (positive = the neighbour is on top of the word, which is the
 *                       "tem algo por cima" half of the complaint).
 *
 * It does NOT judge. It prints. A verdict that hides the numbers is how a gate goes
 * green over a broken panel.
 *
 * RUN: node _main/brand-truncation-probe.mjs
 */
import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs';

const PANEL = 'file:///H:/sotto/app/panel/panel.html';
const THEMES = ['theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5'];
const WIDTHS = [900, 420, 380, 320];  // 380 = a largura REAL do painel (owner: "380x900 px")

const browser = await chromium.launch({ channel: 'msedge' });

async function measure(width) {
  const ctx = await browser.newContext({ viewport: { width, height: 700 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(PANEL, { waitUntil: 'load' });
  await page.waitForTimeout(700);

  const rows = await page.evaluate((themes) => {
    const out = [];
    for (const theme of themes) {
      document.documentElement.setAttribute('data-theme', theme);
      for (const surface of ['panel', 'strip']) {
        document.body.setAttribute('data-surface', surface);
        // the brand lives in the chrome row that this surface actually shows
        const brands = [...document.querySelectorAll('.chrome__brand, .stripbar__brand')]
          .filter((el) => {
            const row = el.parentElement;
            if (!row) return false;
            const cs = getComputedStyle(row);
            return cs.display !== 'none' && el.getClientRects().length > 0;
          });
        for (const el of brands) {
          const box = el.getBoundingClientRect();
          const next = el.nextElementSibling;
          const nbox = next ? next.getBoundingClientRect() : null;
          // where the TEXT actually ends: the brand is `nowrap`, so the painted
          // text runs past `clientWidth` when it does not fit.
          const textEnd = box.left + el.scrollWidth;
          out.push({
            theme,
            surface,
            row: (el.parentElement.className || '').trim().split(/\s+/).slice(0, 2).join('.'),
            cls: el.className,
            clientWidth: Math.round(el.clientWidth * 10) / 10,
            scrollWidth: Math.round(el.scrollWidth * 10) / 10,
            overflow: Math.round((el.scrollWidth - el.clientWidth) * 10) / 10,
            nextLeft: nbox ? Math.round(nbox.left * 10) / 10 : null,
            overlap: nbox ? Math.round((textEnd - nbox.left) * 10) / 10 : null,
            overflowHidden: getComputedStyle(el).overflow,
            flex: getComputedStyle(el).flex,
            minWidth: getComputedStyle(el).minWidth,
          });
        }
        document.body.setAttribute('data-surface', 'panel');
      }
    }
    return out;
  }, THEMES);

  await ctx.close();
  return rows;
}

let bad = 0;
let total = 0;
for (const w of WIDTHS) {
  const rows = await measure(w);
  const flagged = rows.filter((r) => r.overflow > 0);
  const covered = rows.filter((r) => r.overlap !== null && r.overlap > 0);
  total += rows.length;
  bad += flagged.length;
  console.log(`\n=== viewport ${w}px -- ${rows.length} brand box(es), ${flagged.length} with overflow > 0, ${covered.length} with the neighbour over the text ===`);
  for (const r of rows) {
    const mark = r.overflow > 0 ? (r.overlap > 0 ? 'COVERED' : 'OVERFLOW') : 'fit';
    console.log(`  ${mark.padEnd(8)} ${r.theme} ${r.surface.padEnd(5)} ${r.row.padEnd(22)} box=${String(r.clientWidth).padStart(5)} need=${String(r.scrollWidth).padStart(5)} over=${String(r.overflow).padStart(5)} overlap=${String(r.overlap).padStart(6)} overflow=${r.overflowHidden} flex=${r.flex} min-width=${r.minWidth}`);
  }
}

console.log(`\nTOTAL: ${total} brand measurement(s) across ${WIDTHS.length} widths; ${bad} with the text wider than its box.`);
await browser.close();
process.exit(0);
