/* DOES THE WHEEL SCROLL THE TRANSCRIPT? — measured on the shipped panel, in real
 * Chromium, with a real wheel.
 *
 * OWNER, 2026-11-08, verbatim: *"eu nao consigo usar meu scroll pra scrollar as
 * legendas no historico."*
 *
 * WHAT IT DOES. Loads `app/panel/panel.html` exactly as it ships (its own sheets,
 * its own scripts), stubs `window.sotto` with a history tail of 60 lines, and
 * then:
 *
 *   W1  prints the scroll chain of the transcript — `overflow-y`, `clientHeight`
 *       and `scrollHeight` for `.panel`, `.history`, `.history__body` and
 *       `.history__list` — so "which box would scroll, and is its content taller
 *       than it" is a number, not an opinion.
 *   W2  parks the pointer on a VISIBLE row and turns a real wheel (and W2b
 *       repeats it on the far-right column of the rows)
 *       (`page.mouse.wheel`, i.e. a trusted `Input.dispatchMouseEvent` of type
 *       `mouseWheel`). Then it reads the `scrollTop` of every ancestor: the arm
 *       passes when the transcript's scroller moved and the document did not.
 *   M   the config menu: `Traduzir para:` + the translation selector, and `fr`
 *       posted to the bridge exactly once.
 *   R   prints the computed row style (`font-family`, `font-size`,
 *       `line-height`, `padding`) for comparison with the pre-2026-11-05 values.
 *
 * A synthetic (`dispatchEvent`) wheel is ALSO sent, and its result is printed —
 * untrusted events are not consumed by the browser's scroll logic by spec, so it
 * is the reason `page.mouse.wheel` is the instrument here and not a shortcut.
 *
 * HEADLESS. No window on the owner's screen, no app launch, no audio, no network.
 *
 *   node _main/panel-history-wheel-probe.mjs [--theme theme-2] [--json <path>]
 *
 * Exit 0 = both arms pass; 1 = an arm failed; 2 = setup error.
 */
import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs';
import { readFileSync, writeFileSync, mkdtempSync, cpSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const REPO = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\//, '')), '..');
/* `SOTTO_PANEL_DIR` points the whole probe at a COPY of `app/panel`, which is how
 * the red-before run is made: copy the directory, put the previous `panel.js`
 * back in the copy, and run the same arms against it. */
const argOf = (flag, fallback) => {
  const i = process.argv.indexOf(flag);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
/* THE NEGATIVE ARM (--neg-arm). The arms below are only worth their output if a
 * wheel that moves NOTHING is reported as RED, and the answer has to survive the
 * day this fix is committed -- a control that reintroduces "the previous
 * `panel.js`" rots the moment HEAD carries the cure (the trap `paint-cost`
 * measured). So the control is a SURGICAL MUTATION of the cure itself, in a COPY
 * of the panel: `wireHistoryWheel();` is deleted and nothing else is, which is
 * exactly the state the owner reported. The arm must then go RED.
 * Exit 1 = the mutant was caught (this battery's red-by-design convention). */
const NEG_ARM = process.argv.includes('--neg-arm');
let MUTATION = '';
function negArmDir() {
  const dir = mkdtempSync(path.join(tmpdir(), 'sotto-wheel-neg-'));
  const src = path.join(REPO, 'app/panel');
  cpSync(src, dir, { recursive: true });
  const js = path.join(dir, 'panel.js');
  const before = readFileSync(js, 'utf8');
  if (!before.includes('wireHistoryWheel();')) {
    console.log('NEG-ARM: IMPOSSIBLE -- `wireHistoryWheel();` is not in the copy, so there is '
      + 'nothing to remove and this control proves nothing.');
    process.exit(2);
  }
  writeFileSync(js, before.replace('wireHistoryWheel();',
    '/* neg-arm: the wheel wiring removed */ void 0;'), 'utf8');
  MUTATION = 'panel.js: `wireHistoryWheel();` removed in a copy';
  return dir;
}
const PANEL_DIR = NEG_ARM
  ? negArmDir()
  : (process.env.SOTTO_PANEL_DIR
    ? path.resolve(process.env.SOTTO_PANEL_DIR)
    : path.join(REPO, 'app/panel'));
const PANEL = 'file:///' + path.join(PANEL_DIR, 'panel.html').replace(/\\/g, '/');
const THEME = argOf('--theme', 'theme-1');
const JSON_OUT = argOf('--json', '');

const ROWS = 60;
const MIN = 60 * 1000;
function at(msAgo, text) {
  const d = new Date(Date.now() - msAgo);
  const p = (n) => String(n).padStart(2, '0');
  return {
    date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`,
    time: `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`,
    text,
    path: null,
  };
}
const WORDS = 'banana pera manga uva abacaxi morango goiaba pitanga carambola jabuticaba caju';
const entries = Array.from({ length: ROWS }, (_, i) => at((ROWS - i) * MIN, `${WORDS} ${i + 1}`));

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await browser.newContext({ viewport: { width: 380, height: 900 } });
await ctx.addInitScript((rows) => {
  const calls = [];
  window.__translationCalls = calls;
  const target = {
    setLiveEnabled(v) { return { liveEnabled: v }; },
    setTranslationTarget(lang) { calls.push(lang); },
    getStats() { return { stats: { peak: 0.4, blocks: 128 } }; },
    onStats() { return () => {}; },
    onCaption() { return () => {}; },
    onStatus() { return () => {}; },
    setPanelSurface() {}, replyInfo() {}, setTheme() {},
    getTheme() { return 'theme-1'; }, setPause() {}, pointerInteractive() {},
    externalCaptions() { return []; }, onExternalCaptions() { return () => {}; },
    history: {
      append() {},
      reveal() {},
      search() { return Promise.resolve({ hits: [] }); },
      tail() { return Promise.resolve({ entries: rows, root: 'H:/sotto/history' }); },
      root() { return Promise.resolve({ root: 'H:/sotto/history', canonicalProducer: 'test' }); },
    },
  };
  window.sotto = new Proxy(target, { get: (t, k) => (k in t ? t[k] : () => {}) });
  try { window.localStorage.setItem('sotto.theme', 'theme-1'); } catch (err) { void err; }
}, entries);

const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto(PANEL, { waitUntil: 'load' });
await page.waitForFunction(
  (n) => document.querySelectorAll('#history-list .hist').length >= n,
  ROWS,
  { timeout: 20000 },
);
/* The theme switch appends its own sheet asynchronously; make sure the design
 * under test is the one on screen before measuring anything. */
await page.evaluate((id) => { document.documentElement.dataset.theme = id; void document.body.offsetWidth; }, THEME);
/* A theme switch is observed by `theme-tune.js`/`lazy-assets.js`, which APPEND a
 * sheet of their own; it lands after the first frame. Measuring the row before it
 * arrives reads a different design than the one on screen. */
await page.waitForTimeout(600);

/* THE ARM STARTS AT THE TOP. On load the feed is pinned to its newest line (the
 * owner's 2026-10-12 rule), and a down-notch over a box already at its end has
 * nowhere to go — that measurement would say RED about a working wheel. The claim
 * under test is "a notch moves the transcript", so the wheel is turned from the
 * top, which is also where the owner is after scrolling up to read. */
await page.evaluate(() => {
  const b = document.querySelector('.history__body');
  if (b) b.scrollTop = 0;
  const l = document.querySelector('.history__list');
  if (l) l.scrollTop = 0;
});

const chain = await page.evaluate(() => {
  const read = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      sel,
      overflowY: cs.overflowY,
      overflow: cs.overflow,
      display: cs.display,
      clientHeight: el.clientHeight,
      scrollHeight: el.scrollHeight,
      scrollTop: el.scrollTop,
      top: Math.round(r.top),
      bottom: Math.round(r.bottom),
      height: Math.round(r.height),
    };
  };
  return {
    viewportH: window.innerHeight,
    docScroll: { clientHeight: document.documentElement.clientHeight, scrollHeight: document.documentElement.scrollHeight, scrollTop: document.documentElement.scrollTop },
    nodes: ['.panel', '.history', '.history__body', '.history__list'].map(read),
  };
});

/* W2 — A REAL WHEEL OVER A VISIBLE ROW.
 * The pointer is parked on the row at the vertical centre of the region the
 * transcript actually paints (its intersection with the viewport), so the arm
 * cannot pass by scrolling while pointing at an off-screen row. */
const target = await page.evaluate(() => {
  const list = document.querySelector('#history-list');
  const lr = list.getBoundingClientRect();
  const top = Math.max(0, lr.top);
  const bottom = Math.min(window.innerHeight, lr.bottom);
  const x = Math.round(Math.min(window.innerWidth - 2, Math.max(1, lr.left + Math.min(60, lr.width / 2))));
  const y = Math.round((top + bottom) / 2);
  const hit = document.elementFromPoint(x, y);
  return {
    x,
    y,
    listTop: Math.round(lr.top),
    listBottom: Math.round(lr.bottom),
    visible: bottom - top,
    hit: hit ? (hit.id || hit.className || hit.tagName) : null,
    hitRow: Boolean(hit && hit.closest && hit.closest('.hist')),
  };
});

/* THE BOX THAT SCROLLS IS ASKED, NEVER ASSUMED (measured 2026-11-09: the design
 * pass moved the scroller -- `.history__body` is `overflow-y:hidden` and does not
 * scroll any more, `#history-list` is the box with content taller than itself).
 * Every arm below reads THIS node, so a CSS change cannot turn an arm into a
 * measurement of a dead element -- which is exactly how W2b went RED once. */
const scrollBox = () => page.evaluate(() => {
  const list = document.querySelector('#history-list');
  let best = null;
  for (let node = list; node && node !== document.body; node = node.parentElement) {
    const y = getComputedStyle(node).overflowY;
    if (y !== 'auto' && y !== 'scroll' && y !== 'overlay') continue;
    if (!best) best = node.id ? `#${node.id}` : `.${String(node.className).split(' ')[0]}`;
    if (node.scrollHeight > node.clientHeight + 1) {
      return { sel: node.id ? `#${node.id}` : `.${String(node.className).split(' ')[0]}`,
        clientHeight: node.clientHeight, max: node.scrollHeight - node.clientHeight };
    }
  }
  return { sel: best, clientHeight: 0, max: 0 };
});
const BOX = await scrollBox();
const boxTop = () => page.evaluate((sel) => {
  const el = document.querySelector(sel);
  return el ? el.scrollTop : null;
}, BOX.sel);
const resetBox = () => page.evaluate((sel) => {
  const el = document.querySelector(sel);
  if (el) el.scrollTop = 0;
  const b = document.querySelector('.history__body');
  if (b) b.scrollTop = 0;
  return el ? el.scrollTop : null;
}, BOX.sel);

const scrollTops = () => page.evaluate(() => {
  const el = (sel) => document.querySelector(sel);
  const pick = (n) => (n ? { clientHeight: n.clientHeight, scrollHeight: n.scrollHeight, scrollTop: n.scrollTop } : null);
  return {
    panel: pick(el('.panel')),
    history: pick(el('.history')),
    body: pick(el('.history__body')),
    list: pick(el('.history__list')),
    doc: { scrollTop: document.documentElement.scrollTop },
  };
});

const wheelOnce = async () => {
  const before = await scrollTops();
  await page.mouse.move(target.x, target.y);
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(250);
  const after = await scrollTops();
  return { before, after };
};

/* E0 — the shipped state. */
const e0 = await wheelOnce();
const before = e0.before;
const afterReal = e0.after;

/* W2b — THE SAME WHEEL AT THE FAR RIGHT OF THE ROWS. The owner's rule is that
 * the whole row area scrolls, not a strip: the far-right column is where a
 * scrollbar would live, and it is the point most likely to be owned by a
 * different node than the text. */
const targetRight = await page.evaluate(() => {
  const body = document.querySelector('.history__body');
  const br = body.getBoundingClientRect();
  const list = document.querySelector('#history-list');
  const lr = list.getBoundingClientRect();
  const top = Math.max(0, lr.top);
  const bottom = Math.min(window.innerHeight, lr.bottom);
  const x = Math.round(Math.min(window.innerWidth - 2, br.right - 3));
  const y = Math.round((top + bottom) / 2);
  const hit = document.elementFromPoint(x, y);
  return {
    x,
    y,
    hit: hit ? (hit.id || hit.className || hit.tagName) : null,
    hitRow: Boolean(hit && hit.closest && hit.closest('.hist')),
  };
});
const rightEdge = await (async () => {
  await resetBox();
  const t0 = await boxTop();
  await page.mouse.move(targetRight.x, targetRight.y);
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(250);
  const t1 = await boxTop();
  return { before: t0, after: t1, moved: t1 - t0 };
})();

/* THE ARM THAT CAN FAIL. MEASURED 2026-11-09: the real wheel is NOT an isolated
 * probe any more. Once the design pass made `#history-list` the scroller with
 * `overflow-y:auto` and no `overscroll-behavior:contain`, the BROWSER scrolls it
 * by itself -- so the real-wheel arms stayed GREEN with `wireHistoryWheel()`
 * removed, i.e. they certified the mechanism without looking at it. An untrusted
 * `dispatchEvent` is the isolated instrument: the browser does not scroll for a
 * synthetic wheel (by spec), so every pixel that moves is OUR listener's, and
 * `defaultPrevented` says whether it took the event. That is why W2/W3 are
 * synthetic and only W2b (real wheel, far-right column) is kept as a smoke arm.
 */
const syntheticWheel = async (count, deltaY, gapMs) => page.evaluate(async (opts) => {
  const el = document.querySelector(opts.sel);
  const row = document.querySelector('#history-list .hist');
  if (el) el.scrollTop = 0;
  const b = document.querySelector('.history__body');
  if (b) b.scrollTop = 0;
  const prevented = [];
  for (let i = 0; i < opts.count; i += 1) {
    const ev = new WheelEvent('wheel', { deltaY: opts.deltaY, bubbles: true, cancelable: true });
    row.dispatchEvent(ev);
    prevented.push(ev.defaultPrevented);
    if (opts.gapMs) await new Promise((r) => setTimeout(r, opts.gapMs));
  }
  return { top: el ? el.scrollTop : null, prevented, steps: window.__wheelSteps || [] };
}, { count, deltaY, gapMs, sel: BOX.sel });

/* Count the steps the REAL arithmetic returned, without touching the product:
 * `historyWheelStep` is a plain function declaration, so a wrapper around it sees
 * every call the listener makes. */
await page.evaluate(() => {
  window.__wheelSteps = [];
  const orig = window.historyWheelStep;
  window.historyWheelStep = function stepped(...args) {
    const r = orig.apply(this, args);
    window.__wheelSteps.push({ step: r.step, burst: r.burst, gain: r.gain });
    return r;
  };
});

const lone = await syntheticWheel(1, 400, 0);
const burstRun = await syntheticWheel(5, 400, 0);
const capPx = BOX.clientHeight * 0.75;

/* W2/W3 — ONE NOTCH IS 1:1, A BURST MULTIPLIES (owner, 2026-11-09, verbatim:
 * *"eu quero APERTAR meu scroll e descer rapidamente pra cima ou pra baixo no
 * historico"*). Both halves on the same instrument: the lone notch must move the
 * box by the wheel's own delta (no surprise for a reader), and five notches inside
 * the window must cross a screen's worth -- measured as a MULTIPLE of the lone
 * one, never as an absolute number that a viewport change could fake. */
const loneStep = lone.steps.length ? Math.abs(lone.steps[0].step) : 0;
/* The LAST five steps are this arm's: the burst counter CONTINUES across a gap
 * shorter than the window, which is the honest reading of a real burst (`lone`
 * ran immediately before it, so the first burst notch is already #2). The
 * per-event step is compared EXCLUDING the cap -- a 400 px tick is clamped at
 * 0.75 viewport by design, so what proves the gain is that the clamped step still
 * exceeds the lone step, and that five of them cross the screen. */
const burstSteps = burstRun.steps.slice(-5);
const burstStep = burstSteps.length ? Math.abs(burstSteps[burstSteps.length - 1].step) : 0;
const armW2 = lone.top > 0 && Math.abs(lone.top - 400) <= 2 && lone.prevented.every(Boolean);
const armW3 = lone.top > 0 && burstRun.top >= lone.top * 2.5 && burstStep > loneStep * 1.2;
const stats = { loneTop: lone.top, burstTop: burstRun.top, loneStep, burstStep,
  burst: burstSteps.map((x) => x.burst), gain: burstSteps.map((x) => x.gain) };

console.log('--- W2/W3 the wheel, isolated (synthetic: only our listener can move it) ---');
console.log(`  box ${BOX.sel} client=${BOX.clientHeight}px max=${BOX.max}px cap=${Math.round(capPx)}px`);
console.log(`  lone notch deltaY=400 -> top=${lone.top} step=${loneStep} prevented=${JSON.stringify(lone.prevented)}`);
console.log(`  burst of 5 deltaY=400 -> top=${burstRun.top} steps=${JSON.stringify(stats.burst)} `
  + `gains=${JSON.stringify(stats.gain)}`);
console.log(`  W2 ${armW2 ? 'GREEN' : 'RED'} — one notch is 1:1 and the listener takes the event`);
console.log(`  W3 ${armW3 ? 'GREEN' : 'RED'} — a burst of 5 moves x${lone.top ? (burstRun.top / lone.top).toFixed(2) : 'n/a'} `
  + `(per-event step x${loneStep ? (burstStep / loneStep).toFixed(2) : 'n/a'})`);

/* W4 — MIDDLE-BUTTON PRESS-AND-PULL. 200 px of pointer is half a screen at the
 * declared gain; the press must be consumed (no autoscroll widget, no paste). */
await resetBox();
await page.mouse.move(target.x, target.y);
await page.mouse.down({ button: 'middle' });
for (const dy of [40, 80, 120, 160, 200]) await page.mouse.move(target.x, target.y - dy);
await page.mouse.up({ button: 'middle' });
await page.waitForTimeout(120);
const dragged = await boxTop();
const armW4 = dragged >= 200 && dragged >= BOX.clientHeight * 0.5 && dragged <= BOX.max;
console.log(`  middle press + 200 px pull: top 0->${dragged}`);
console.log(`  W4 ${armW4 ? 'GREEN' : 'RED'} — a 200 px pull moves ${dragged} tex px `
  + `(piso ${Math.round(BOX.clientHeight * 0.5)} = meia caixa)`);

/* THE CAUSES ARE FALSIFIED ONE AT A TIME, each on the SAME document, by changing
 * exactly one property and repeating the SAME wheel. A probe that only prints
 * RED leaves the fix to intuition; these arms say WHICH rule is responsible. */
const probeWith = async (label, css) => {
  await page.evaluate((pairs) => {
    for (const [sel, prop, value] of pairs) {
      const el = document.querySelector(sel);
      if (el) el.style.setProperty(prop, value, 'important');
    }
    const b = document.querySelector('.history__body');
    if (b) b.scrollTop = 0;
  }, css);
  const r = await wheelOnce();
  return {
    label,
    bodyTop: r.before.body.scrollTop,
    afterBodyTop: r.after.body.scrollTop,
    listTop: r.before.list.scrollTop,
    afterListTop: r.after.list.scrollTop,
    docTop: r.after.doc.scrollTop,
    moved: r.after.body.scrollTop - r.before.body.scrollTop
      || r.after.list.scrollTop - r.before.list.scrollTop,
  };
};

const e1 = await probeWith('E1 .history__list overscroll-behavior:auto (overflow untouched)', [
  ['.history__list', 'overscroll-behavior', 'auto'],
]);
const e2 = await probeWith('E2 .history__list overflow:visible (overscroll restored)', [
  ['.history__list', 'overscroll-behavior', 'contain'],
  ['.history__list', 'overflow', 'visible'],
]);
const e3 = await probeWith('E3 .history__body overflow:hidden (control)', [
  ['.history__body', 'overflow', 'hidden'],
]);
/* Programmatic control: if THIS cannot move, the box is not scrollable at all and
 * no wheel rule could ever help. */
const programmatic = await page.evaluate(() => {
  const b = document.querySelector('.history__body');
  b.scrollTop = 0;
  b.scrollBy(0, 200);
  return { scrollTop: b.scrollTop };
});

/* The synthetic control: same element, `dispatchEvent`. Kept because it names
 * why the instrument is a real wheel. The inline overrides of the cause arms are
 * cleared first so this measures the shipped cascade. */
await page.evaluate(() => {
  for (const sel of ['.history__list', '.history__body']) {
    const el = document.querySelector(sel);
    if (el) el.removeAttribute('style');
  }
  const b = document.querySelector('.history__body');
  if (b) b.scrollTop = 0;
});
const beforeSynthetic = await scrollTops();
await page.evaluate(() => {
  const list = document.querySelector('#history-list');
  const row = list.querySelector('.hist');
  list.scrollTop = 0;
  row.dispatchEvent(new WheelEvent('wheel', { deltaY: 120, bubbles: true, cancelable: true }));
  return true;
});
await page.waitForTimeout(120);
const afterSynthetic = await scrollTops();

const rowStyle = await page.evaluate(() => {
  const row = document.querySelector('#history-list .hist');
  const text = row.querySelector('.hist__text');
  const time = row.querySelector('.hist__time');
  const rs = getComputedStyle(row);
  const ts = getComputedStyle(text);
  return {
    display: rs.display,
    padding: `${rs.paddingTop} ${rs.paddingRight} ${rs.paddingBottom} ${rs.paddingLeft}`,
    rowLineHeight: rs.lineHeight,
    fontFamily: ts.fontFamily,
    fontSize: ts.fontSize,
    lineHeight: ts.lineHeight,
    timeFontSize: getComputedStyle(time).fontSize,
    gap: rs.gap,
    background: rs.backgroundColor,
    borderRadius: rs.borderRadius,
  };
});

const moved = (a, b, key) => {
  const pick = (s) => {
    if (!s) return 0;
    if (key === 'doc') return s.doc && s.doc.scrollTop != null ? s.doc.scrollTop : 0;
    return s[key] && s[key].scrollTop != null ? s[key].scrollTop : 0;
  };
  return pick(b) - pick(a);
};
const scrollers = [
  ['body', moved(before, afterReal, 'body')],
  ['list', moved(before, afterReal, 'list')],
  ['history', moved(before, afterReal, 'history')],
  ['panel', moved(before, afterReal, 'panel')],
  ['doc', moved(before, afterReal, 'doc')],
];
const scrolledIdx = moved(before, afterReal, 'body') > 0
  ? 'body'
  : moved(before, afterReal, 'list') > 0 ? 'list' : null;

const overflowOk = (n) => n && (n.overflowY === 'auto' || n.overflowY === 'scroll');
const scrollable = chain.nodes.find((n) => n && overflowOk(n) && n.scrollHeight > n.clientHeight + 1);

const armW1 = Boolean(scrollable);
const armRealWheel = Boolean(scrolledIdx) || rightEdge.moved > 0;

console.log(`THEME ${THEME} · ${ROWS} rows · viewport ${chain.viewportH}px`);
console.log('--- D1 scroll chain (diagnostic) ---');
for (const n of chain.nodes) {
  if (!n) { console.log('  (missing node)'); continue; }
  console.log(`  ${n.sel}: overflow-y=${n.overflowY} display=${n.display} client=${n.clientHeight} scroll=${n.scrollHeight} top=${n.scrollTop} box=${n.top}..${n.bottom}`);
}
console.log(`  document: client=${chain.docScroll.clientHeight} scroll=${chain.docScroll.scrollHeight}`);
console.log(`  D1 chain (diagnostic, GREEN both sides) — a transcript scroller with overflow-y auto|scroll and content taller than its box: ${scrollable ? `${scrollable.sel} (scroll ${scrollable.scrollHeight} > client ${scrollable.clientHeight})` : 'NONE'}`);

console.log('--- W2 wheel (the arm) ---');
console.log(`  pointer (${target.x},${target.y}) over=${target.hit} onRow=${target.hitRow} visible=${target.visible}px list=${target.listTop}..${target.listBottom}`);
console.log(`  scrollTop deltas: ${scrollers.map(([k, d]) => `${k}=${d}`).join(' ')}`);
console.log(`  W2r ${armRealWheel ? 'GREEN' : 'RED'} — a real wheel over the rows moved ${scrolledIdx || `nothing in the doc chain (right edge ${rightEdge.moved})`} (smoke, not the arm)`);
const armW2b = rightEdge.moved > 0;   /* smoke: this one the browser alone can satisfy */
console.log(`  W2b pointer (${targetRight.x},${targetRight.y}) over=${targetRight.hit} onRow=${targetRight.hitRow} moved body=${rightEdge.moved}`);
console.log(`  W2b ${armW2b ? 'GREEN' : 'RED'} — the far-right column of the rows scrolls too`);
console.log(`  control: synthetic dispatchEvent moved body=${moved(beforeSynthetic, afterSynthetic, "body")} list=${moved(beforeSynthetic, afterSynthetic, "list")} (untrusted events are not consumed by browser scroll by spec)`);
console.log('--- causes, one property at a time, same wheel ---');
for (const r of [e1, e2, e3]) {
  console.log(`  ${r.label}: body ${r.bodyTop}->${r.afterBodyTop} list ${r.listTop}->${r.afterListTop} moved=${r.moved}`);
}
console.log(`  programmatic scrollBy(0,200) on .history__body: scrollTop=${programmatic.scrollTop}`);

console.log('--- R row style ---');
for (const [k, v] of Object.entries(rowStyle)) console.log(`  ${k}: ${v}`);

/* M — THE CONFIG MENU (owner, 2026-11-08: *"e faz o botao de config pra eu
 * escolher pra qual lingua traduzir"*). The popover must exist in the SHIPPED
 * document, its row must be labelled `Traduzir para:`, the auto entry must name
 * the default (`Auto (Português BR)`), and choosing `fr` must reach the bridge
 * EXACTLY ONCE. */
const menu = await page.evaluate(() => {
  const button = document.getElementById('menu-button');
  const panel = document.getElementById('panel-menu');
  const select = document.getElementById('translation-select');
  const label = document.querySelector('#panel-menu .tune-row__label');
  const before = window.__translationCalls.length;
  if (button) button.click();
  const opened = Boolean(panel && !panel.hidden);
  if (select) {
    select.value = 'fr';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return {
    hasButton: Boolean(button),
    opened,
    label: label ? label.textContent.trim() : null,
    auto: select
      ? [...select.options].map((o) => o.textContent).find((t) => t === 'Auto (Português BR)') || null
      : null,
    options: select ? select.options.length : 0,
    calls: window.__translationCalls.slice(before),
  };
});
const armM = menu.hasButton && menu.opened && menu.label === 'Traduzir para:'
  && menu.auto === 'Auto (Português BR)'
  && menu.calls.length === 1 && menu.calls[0] === 'fr';
console.log('--- M config menu ---');
console.log(`  button=${menu.hasButton} opened=${menu.opened} label=${JSON.stringify(menu.label)} auto=${JSON.stringify(menu.auto)} options=${menu.options}`);
console.log(`  setTranslationTarget calls on change: ${JSON.stringify(menu.calls)}`);
console.log(`  M ${armM ? 'GREEN' : 'RED'} — selector with the new label, and fr posted exactly once`);

if (NEG_ARM) {
  /* W2b/W2r are SMOKE: the browser's own scroll satisfies them, so they cannot
   * catch a missing listener -- only the isolated arms can. */
  const caught = !armW2 || !armW3 || !armW4;
  console.log(`PROBE ${caught ? 'RED (the mutant)' : 'GREEN (THE MUTANT WAS NOT CAUGHT)'}   `
    + `(${MUTATION})`);
  console.log(`NEG-ARM: ${caught ? 'PASS' : 'FAIL -- the arm is GREEN with the wheel wiring removed, '
    + 'so it cannot see the defect the owner reported'}`);
  await browser.close();
  process.exit(caught ? 1 : 0);
}
console.log(`PROBE ${armW2 && armW2b && armW3 && armW4 && armM ? 'GREEN' : 'RED'}   (arms: W2 1:1, W3 burst, W4 middle press, M config menu; W2r/W2b real-wheel smoke, D1/D causes diagnostic)`);
if (errors.length) {
  console.log(`PAGE ERRORS: ${errors.length}`);
  for (const e of errors.slice(0, 5)) console.log('  ' + e);
}
if (JSON_OUT) {
  writeFileSync(JSON_OUT, JSON.stringify({ theme: THEME, chain, target, before, afterReal, afterSynthetic, rowStyle, errors }, null, 2));
}
await browser.close();
process.exit(armW2 && armW2b && armW3 && armW4 && armM && !errors.length ? 0 : 1);
