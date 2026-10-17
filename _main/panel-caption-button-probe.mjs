/* Why the caption button is dead, proved and unproved, in a real browser.
 *
 * The shell exposes no CDP port (measured: no `remote-debugging-port` anywhere in
 * `sotto_webview.py`, and the only listening ports on this host belong to other
 * processes), so the live panel cannot be poked from outside. This runs the SHIPPED
 * `app/panel/panel.html` unmodified in Chromium with a recording stub in place of
 * the preload bridge, which is enough to answer the two questions that matter:
 *
 *   Q1 does the page throw at load, and if so where?
 *   Q2 does one click on the caption button reach the shell, and does the shell's
 *      answer (the `data-caption-window` attribute) repaint the button?
 *
 * Q2 is the owner's complaint verbatim -- "o botao de ativar a legenda nao funciona".
 * A page that does not throw is NOT evidence that the button works, and that is
 * the difference this harness exists to close.
 *
 * Read-only: nothing is written into H:\sotto. Screenshots go to I:\cc-tmp.
 */
import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';

const PANEL = 'file:///H:/sotto/app/panel/panel.html';
const OUT = 'I:/cc-tmp/panel-shots';
mkdirSync(OUT, { recursive: true });

/* The installed Playwright is 1.60.0 and its default download
 * (`chromium_headless_shell-1223`) is NOT on this host -- the cache holds
 * `chromium-1228` only, measured. Rather than download 150 MB, drive the Edge
 * that is already installed: same engine family as the WebView2 the product
 * actually runs on. */
const browser = await chromium.launch({ channel: 'msedge' });
const ctx = await browser.newContext({ viewport: { width: 380, height: 900 } });

// The recording stub. A Proxy so every bridge member exists and every call is
// captured, without hard-coding the nineteen names the preload publishes.
await ctx.addInitScript(() => {
  const calls = [];
  const target = {
    setLiveEnabled(v) { calls.push(['setLiveEnabled', v]); return { liveEnabled: v }; },
    getStats() { calls.push(['getStats']); return { stats: { peak: 0, blocks: 0 } }; },
    onStats() { calls.push(['onStats']); return () => {}; },
    onCaption() { calls.push(['onCaption']); return () => {}; },
    onStatus() { calls.push(['onStatus']); return () => {}; },
    setPanelSurface() { calls.push(['setPanelSurface']); },
    revive() { calls.push(['revive']); return true; },
    replyInfo() {},
    externalCaptions() { return []; },
    onExternalCaptions() { return () => {}; },
    setTheme() {},
    getTheme() { return 'theme-1'; },
    setPause() {},
    pointerInteractive() {},
    /* `bridge.history` is an OBJECT, not a function: `panel.js:156` reads it as
     * `bridge.history ? bridge.history : null` and then calls `.append/.reveal/
     * .search/.tail/.root` on it. A bare Proxy member made the first version of
     * this stub answer `historyApi.root is not a function`, which is a defect in
     * the HARNESS and must never be reported as a defect in the panel. */
    history: {
      append() { calls.push(['history.append']); },
      reveal() { calls.push(['history.reveal']); },
      search() { calls.push(['history.search']); return Promise.resolve([]); },
      tail() { calls.push(['history.tail']); return Promise.resolve([]); },
      /* The panel CHAINS on what these return: `historyApi.root(...).then`. So every
       * member answers with a promise. Answering with a plain array produced
       * `historyApi.root(...).then is not a function` in the harness twice before
       * this line was correct. */
      root() { calls.push(['history.root']); return Promise.resolve([]); },
    },
  };
  window.sotto = new Proxy(target, {
    get(t, k) {
      if (k === '__calls') return calls;
      if (k in t) return t[k];
      return (...a) => { calls.push([String(k), ...a]); return undefined; };
    },
  });
  window.__probe = { calls };
});

const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

await page.goto(PANEL, { waitUntil: 'load' });
await page.waitForTimeout(1200);

const boot = await page.evaluate(() => ({
  hasBridge: typeof window.sotto === 'object' && window.sotto !== null,
  attr: document.documentElement.getAttribute('data-caption-window'),
  liveEnabled: window.__liveEnabled ?? null,
  buttons: [...document.querySelectorAll('button')].map((b) => ({
    id: b.id || null,
    cls: b.className,
    pressed: b.getAttribute('aria-pressed'),
    label: (b.textContent || '').trim().slice(0, 24),
  })),
}));

console.log('=== Q1: did the page throw at load? ===');
console.log(`   errors: ${errors.length}`);
for (const e of errors.slice(0, 6)) console.log('   ' + e);
console.log(`   bridge present: ${boot.hasBridge}`);
console.log(`   data-caption-window: ${JSON.stringify(boot.attr)}`);
console.log(`   buttons: ${boot.buttons.length}`);
for (const b of boot.buttons) {
  console.log(`     #${b.id ?? '-'} [${b.cls}] aria-pressed=${b.pressed} "${b.label}"`);
}

// Q2: click the caption button and watch the bridge.
const before = await page.evaluate(() => window.__probe.calls.length);
const target = boot.buttons.find((b) => /live|caption|legenda/i.test(b.id || '') || /live|caption/i.test(b.cls))
  || boot.buttons[0];
console.log('');
console.log('=== Q2: does one click reach the shell? ===');
console.log(`   clicking #${target.id ?? '-'} [${target.cls}]`);
/* Click through `evaluate`, not `page.click`: this button lives on the strip
 * surface, which is off screen while the panel surface is up, and Playwright's
 * real-input click waits for visibility and times out. The owner's complaint is
 * about the handler, and the handler runs on a synthetic click too. */
await page.evaluate((id) => {
  const el = document.getElementById(id) || document.querySelector('button');
  el.click();
}, target.id);
await page.waitForTimeout(500);

const after = await page.evaluate(() => ({
  calls: window.__probe.calls.slice(),
  attr: document.documentElement.getAttribute('data-caption-window'),
}));
const newCalls = after.calls.slice(before);
console.log(`   bridge calls caused by the click: ${newCalls.length}`);
for (const c of newCalls) console.log(`     ${JSON.stringify(c)}`);

// The shell's answer. This is the half that was broken: the page must paint from
// the ATTRIBUTE the shell writes, not from the value it requested.
await page.evaluate(() => document.documentElement.setAttribute('data-caption-window', 'on'));
await page.waitForTimeout(400);
const painted = await page.evaluate((id) => {
  const el = document.querySelector(`#${id}`) || document.querySelector('button');
  return { pressed: el.getAttribute('aria-pressed'), dataState: document.body.dataset.state };
}, target.id);
console.log(`   after the shell writes data-caption-window=on -> aria-pressed=${painted.pressed} body[data-state]=${painted.dataState}`);

await page.screenshot({ path: `${OUT}/caption-button-on.png` });
console.log('');
console.log(`screenshot: ${OUT}/caption-button-on.png`);
await browser.close();
process.exit(errors.length ? 1 : 0);