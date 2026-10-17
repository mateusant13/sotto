/* The theme matrix: what the owner actually looks at when he says the panel is ugly.
 *
 * There are THIRTY-TWO themes, not five (measured from the shipped dropdown in
 * `_main/panel-caption-button-probe.mjs`: 5 named directions + 10 named looks +
 * 17 `... · painel` designs). Judging "which themes look like theme 1" by reading
 * CSS is how a redesign goes wrong, so this renders the SHIPPED panel.html
 * unmodified in Edge, once per theme, with a real caption in the live box, and
 * reports the COMPUTED border and corner of `.panel` per theme.
 *
 * The computed style is the point. "No white border, rounded corners" is a claim
 * about what the browser ends up with, not about what a generator wrote, and the
 * owner is the one being shown the result.
 */
import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';

const PANEL = 'file:///H:/sotto/app/panel/panel.html';
const OUT = 'I:/cc-tmp/theme-matrix';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: 'msedge' });
const ctx = await browser.newContext({ viewport: { width: 380, height: 900 }, deviceScaleFactor: 1 });
await ctx.addInitScript(() => {
  const calls = [];
  const listeners = {};
  const cap = [];
  const target = {
    setLiveEnabled(v) { calls.push(['setLiveEnabled', v]); return { liveEnabled: v }; },
    getStats() { return { stats: { peak: 0.41, blocks: 128 } }; },
    onStats(cb) { listeners.stats = cb; return () => {}; },
    onCaption(cb) {
      listeners.caption = cb;
      // Three closed lines and one live one, so the design under review is the one
      // that will be on screen all day: a filled column, not an empty placeholder.
      queueMicrotask(() => {
        cb({ text: 'esta e a legenda que o dono esta a ler agora', meta: { source: 'device:VB-Audio' } });
        cb({ text: 'e a linha anterior, ja confirmada pelo worker', meta: { source: 'device:VB-Audio' } });
        cb({ text: 'e uma terceira linha para encher a coluna', meta: { source: 'device:VB-Audio' } });
      });
      return () => {};
    },
    onStatus() { return () => {}; },
    setPanelSurface() {},
    replyInfo() {},
    setTheme() {},
    getTheme() { return 'theme-1'; },
    setPause() {},
    pointerInteractive() {},
    externalCaptions() { return []; },
    onExternalCaptions() { return () => {}; },
    history: {
      append() {}, reveal() {}, search() { return Promise.resolve([]); },
      tail() { return Promise.resolve([]); }, root() { return Promise.resolve([]); },
    },
  };
  window.sotto = new Proxy(target, {
    get(t, k) { if (k in t) return t[k]; return (...a) => { calls.push([String(k), ...a]); }; },
  });
  window.__probe = { calls, listeners };
});

const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto(PANEL, { waitUntil: 'load' });
await page.waitForTimeout(1000);

const themes = await page.evaluate(() =>
  [...document.querySelectorAll('.theme-dropdown__option')]
    .map((b) => b.dataset.themeChoice)
    .filter(Boolean));
console.log(`themes in the shipped dropdown: ${themes.length}`);
console.log(themes.join('  '));
console.log('');

const rows = [];
for (const t of themes) {
  const info = await page.evaluate((theme) => {
    document.documentElement.setAttribute('data-theme', theme);
    const el = document.querySelector('.panel');
    if (!el) return null;
    const cs = getComputedStyle(el);
    return {
      theme,
      borderColor: cs.borderTopColor,
      borderWidth: cs.borderTopWidth,
      radius: cs.borderTopLeftRadius,
      boxShadow: cs.boxShadow,
    };
  }, t);
  if (!info) { console.log(`  ${t}: NO .panel`); continue; }
  rows.push(info);
  await page.waitForTimeout(160);
  await page.screenshot({ path: `${OUT}/${t}.png` });
}

/* What the owner would call a white border. A first version of this test flagged
   all 45 themes, and every flag was wrong: it asked only "is there an rgba() in the
   box-shadow", and the panel's own black DROP SHADOW is rgba(). The white ring it
   was written to catch is a layer with a spread and a LIGHT colour. So a layer
   counts only when the three channels are all above 200 AND it has a spread. */
function ringLayers(boxShadow) {
  if (!boxShadow || boxShadow === 'none') return [];
  const out = [];
  for (const layer of boxShadow.split(/,(?![^(]*\))/)) {
    const m = layer.match(/rgba?\(([^)]+)\)/);
    if (!m) continue;
    const parts = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    const [rr, gg, bb, aa = 1] = parts;
    const nums = layer.match(/-?\d+(?:\.\d+)?px/g) || [];
    const spread = nums.length >= 4 ? Number(nums[3]) : 0;
    if (spread > 0 && rr > 200 && gg > 200 && bb > 200 && aa > 0) out.push(layer.trim());
  }
  return out;
}

const white = rows.filter((r) => {
  const bc = r.borderColor.match(/[\d.]+/g) || [];
  const [, , , aa = 1] = bc.map(Number);
  const borderVisible = r.borderWidth !== '0px' && aa !== 0;
  return borderVisible || ringLayers(r.boxShadow).length > 0;
});
const square = rows.filter((r) => r.radius === '0px');

console.log(`rendered: ${rows.length}`);
console.log('');
console.log(`themes whose panel still paints a VISIBLE edge (border or shadow): ${white.length}`);
for (const r of white) console.log(`   ${r.theme}  border=${r.borderWidth} ${r.borderColor}  radius=${r.radius}`);
console.log(`themes whose panel corner is still SQUARE: ${square.length}`);
for (const r of square) console.log(`   ${r.theme}  radius=${r.radius}`);
console.log('');
const shadows = [...new Set(rows.map((r) => r.boxShadow))];
console.log(`distinct box-shadow values across ${rows.length} themes: ${shadows.length}`);
for (const s of shadows) console.log(`   ${s}`);
console.log('');
console.log(`page errors: ${errors.length}`);
for (const e of errors.slice(0, 5)) console.log('   ' + e);
console.log(`shots: ${OUT}`);
await browser.close();
process.exit(errors.length ? 1 : 0);