/* DOES THE TRANSCRIPT CLIP ITS OWN WORDS? — measured, per design, in real Chromium.
 *
 * OWNER, 2026-11-06, verbatim: *"o historico CORTA no meio da frase. imagina uma
 * frase com 10 palavras. a cada 3 ou de forma aleatoria, palavras NO meio de
 * outras palavras, somem. entao 'banana pera manga' do nada vira 'banana manga'.
 * a logica ta extremamente errada, tu vai ter que fazer full audit."*
 *
 * THE AUDIT FOUND THE STORE CLEAN AND THE RENDER GUESSED AT. Measured on the
 * owner's own transcript (`history/<day>/<hh>.md`, 33 files / 3 321 lines): ZERO
 * lines whose later neighbour is a shorter prefix of the previous one, and the only
 * "middle word dropped" pairs in the whole store are four `Mmm Mmm Mmm` lines. The
 * file does not lose words. So the question this probe answers is the OTHER half:
 * does the ROW lose words on the way to the glass — a `white-space: nowrap` with
 * `overflow: hidden` clips the tail mid-word, a `-webkit-line-clamp` eats the rest
 * of a long line, a grid `auto` column can shrink the text below its own content.
 *
 * WHAT IT DOES: loads the SHIPPED `app/panel/panel.html` in headless Chromium, stubs
 * the bridge with a history tail that holds three deliberately long lines, then for
 * EVERY theme id in the manifest sets `data-theme`, forces a reflow and measures each
 * row: `scrollWidth` vs `clientWidth` (horizontal clip), `scrollHeight` vs
 * `clientHeight` (vertical clip), and the computed `white-space`, `overflow`,
 * `text-overflow`, `-webkit-line-clamp` and `display` of `.hist__text`.
 *
 * A row is CLIPPED when its text box scrolls wider or taller than its own client
 * box. That is not an opinion about the design: it is the definition of a box
 * whose content does not fit, and the words past the edge are exactly what the
 * owner cannot read.
 *
 * HEADLESS ONLY. No window on the owner's screen, no app launch: this drives a
 * browser, not Sotto.
 *
 *   node _main/panel-history-clip-probe.mjs [--json <path>]
 */
import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const REPO = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\//, '')), '..');
const PANEL = 'file:///' + path.join(REPO, 'app/panel/panel.html').replace(/\\/g, '/');
const jsonFlag = process.argv.indexOf('--json');
const JSON_OUT = jsonFlag > 0 ? process.argv[jsonFlag + 1] : '';

/* THE SENTENCES ARE LONG ON PURPOSE. The owner's example is ten words; these are
 * twenty to forty, which is what a line looks like when the worker closes a whole
 * sentence, and it is past every sane column width at 380 px. */
const LINES = [
  'banana pera manga uva abacaxi morango goiaba pitanga carambola jabuticaba caju '
    + 'graviola acerola araçá buriti pequi cupuaçu bacuri taperebá murici',
  'esta e uma linha longa o suficiente para que qualquer coluna estreita tenha de '
    + 'decidir entre quebrar em varias linhas e esconder o que nao cabe nela',
  'a terceira linha existe para que a lista tenha rolagem e para que a medicao nao '
    + 'dependa de uma unica altura de conteudo nem de um unico caso de quebra',
];

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

const entries = LINES.map((text, i) => at((LINES.length - i) * MIN, text));

/* EVERY DESIGN THE PICKER OFFERS. Four manifests, because the page loads four:
 * `themes.js` (the five base designs + the cinematic set), `panel-designs.js`,
 * `zipc-panels.js` and `skins.js`. The `name:'…'` key is the id the picker writes
 * into `data-theme`; the skins are excluded because they no longer paint a panel
 * of their own (they are palette + backdrop now, `skin-layout.css`). */
const themeIds = (() => {
  const ids = new Set();
  for (const file of ['themes/themes.js', 'themes/panel-designs.js', 'themes/zipc-panels.js']) {
    const src = readFileSync(path.join(REPO, 'app/panel', file), 'utf8');
    for (const m of src.matchAll(/name:\s*'([^']+)'/g)) ids.add(m[1]);
  }
  return [...ids];
})();

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const ctx = await browser.newContext({ viewport: { width: 380, height: 900 } });
await ctx.addInitScript((rows) => {
  const target = {
    setLiveEnabled(v) { return { liveEnabled: v }; },
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
  window.sotto = new Proxy(target, {
    get: (t, k) => (k in t ? t[k] : () => {}),
  });
  /* THE THEME MODULE READS localStorage; a design switch in this probe must not
   * depend on the owner's stored choice. */
  try { window.localStorage.setItem('sotto.theme', 'theme-1'); } catch (err) { void err; }
}, entries);

const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
await page.goto(PANEL, { waitUntil: 'load' });
await page.waitForFunction(
  () => document.querySelectorAll('#history-list .hist').length >= 3,
  null,
  { timeout: 15000 },
);

const report = await page.evaluate((ids) => {
  /* WCAG CONTRASTE, COMPOSTO SOBRE O FUNDO DA PROPRIA LINHA.
   *
   * OWNER: *"tem que ter contraste bom, TODOS os textos no historico vs o horario
   * do texto. de preferencia deixa o horario mais escuro/cinza, e o texto mais
   * 'aceso'."* A primeira versao desta conta comparava as duas cores CRUAS e
   * dizia 1.00 em cinco temas -- porque o horario E' a mesma cor com outro alpha,
   * e duas cores de mesmo RGB tem razao 1 seja qual for o alpha. O alpha e'
   * exatamente o que o dono ve, logo cada cor tem de ser composta sobre o fundo.
   *
   * DOIS VEREDITOS, porque um so' mente:
   *   STAMP UNREADABLE -- horario abaixo de 3:1 contra o fundo: existe e nao se
   *   le (era o `theme-1` a 1.69:1 com o corpo do texto a 19.22:1).
   *   STAMP LOUDER THAN TEXT -- o horario com mais contraste que o texto, a
   *   direcao que o dono pediu ao contrario.
   */
  /* `getComputedStyle` does not always answer in `rgb()`. A `color-mix()` comes
   * back as `color(srgb 1 1 1 / 0.663)` on this engine -- MEASURED, and the first
   * version of this parser returned null for it, which turned every stamp into a
   * silent zero population instead of a failure. Both forms are read here, and a
   * colour that is neither RAISES rather than being skipped. */
  function parse(str) {
    const raw = String(str || '').trim();
    let m = raw.match(/rgba?\(([^)]+)\)/);
    if (m) {
      const p = m[1].split(',').map((x) => parseFloat(x));
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    }
    m = raw.match(/^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)$/);
    if (m) {
      return {
        r: parseFloat(m[1]) * 255,
        g: parseFloat(m[2]) * 255,
        b: parseFloat(m[3]) * 255,
        a: m[4] == null ? 1 : parseFloat(m[4]),
      };
    }
    throw new Error('cor ilegivel: ' + raw);
  }
  function over(c, bg) {
    const a = c.a == null ? 1 : c.a;
    return {
      r: c.r * a + bg.r * (1 - a),
      g: c.g * a + bg.g * (1 - a),
      b: c.b * a + bg.b * (1 - a),
      a: 1,
    };
  }
  function lum(c) {
    const f = (v) => {
      const x = v / 255;
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function ratio(x, y) {
    const l1 = lum(x);
    const l2 = lum(y);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  function backdrop(el) {
    let node = el;
    while (node && node.nodeType === 1) {
      const c = parse(getComputedStyle(node).backgroundColor);
      if (c && c.a > 0.5) return c;
      node = node.parentElement;
    }
    return { r: 10, g: 12, b: 15, a: 1 };
  }
  const out = [];
  const rows = [...document.querySelectorAll('#history-list .hist')];
  const measure = () => rows.map((row) => {
    const text = row.querySelector('.hist__text');
    const time = row.querySelector('.hist__time');
    const cs = getComputedStyle(text);
    const rs = getComputedStyle(row);
    return {
      clippedX: text.scrollWidth - text.clientWidth > 1,
      clippedY: text.scrollHeight - text.clientHeight > 1,
      overflowX: text.scrollWidth - text.clientWidth,
      overflowY: text.scrollHeight - text.clientHeight,
      whiteSpace: cs.whiteSpace,
      overflow: cs.overflow,
      textOverflow: cs.textOverflow,
      lineClamp: cs.webkitLineClamp,
      display: cs.display,
      // The row itself clipping is the same defect one level up.
      rowClippedX: row.scrollWidth - row.clientWidth > 1,
      rowClippedY: row.scrollHeight - row.clientHeight > 1,
      rowDisplay: rs.display,
      rowAlign: rs.textAlign,
      // Alignment and the stamp's contrast, measured rather than eyeballed.
      textAlign: cs.textAlign,
      timeColor: getComputedStyle(time).color,
      textColor: cs.color,
      timeOpacity: getComputedStyle(time).opacity,
      timeWidth: Math.round(time.getBoundingClientRect().width),
      // The two ratios, each colour composited over the row's own background.
      stamp: (() => {
        const bgt = backdrop(row);
        const c = parse(getComputedStyle(time).color);
        if (!c) return null;
        const o = parseFloat(getComputedStyle(time).opacity || '1');
        return Number(ratio(over({ ...c, a: (c.a == null ? 1 : c.a) * o }, bgt), bgt).toFixed(2));
      })(),
      body: (() => {
        const bgt = backdrop(row);
        const c = parse(cs.color);
        if (!c) return null;
        const o = parseFloat(cs.opacity || '1');
        return Number(ratio(over({ ...c, a: (c.a == null ? 1 : c.a) * o }, bgt), bgt).toFixed(2));
      })(),
    };
  });
  for (const id of ids) {
    document.documentElement.dataset.theme = id;
    // Force a style recalc before reading.
    void document.body.offsetWidth;
    out.push({ theme: id, rows: measure() });
  }
  return out;
}, themeIds);

/* O LOGOTIPO, MEDIDO EM TODOS OS DESENHOS (owner: *"sotto tem que ter o MESMO
 * TAMANHO de logo/letra, na MESMA LINHA/PIXEL"*). O que se le' e' o elemento que
 * PINTA as letras, nao o wrapper: medir o wrapper foi o erro que deixou 17 px e
 * 13 px passarem por `14px !important`. */
/* OS BOTOES, MEDIDOS: a coordenada de cada controlo do painel em todos os
 * desenhos (owner: *"se em 20 paineis o botao de trocar pro proximo tema esta na
 * coordenada x, TODOS os temas tem que ficar na coordenada x, o mesmo botao.
 * FIXO."*). O que se publica e' o CONJUNTO de valores por controlo: um so'
 * elemento no conjunto significa que nenhum tema o move. */
const controls = await page.evaluate((ids) => {
  const out = [];
  const cluster = document.querySelector('.panel__controls');
  if (!cluster) return [{ theme: 'none', note: 'sem .panel__controls' }];
  const seen = () => [...cluster.children].map((el) => {
    const r = el.getBoundingClientRect();
    return {
      id: el.id || el.className || el.tagName.toLowerCase(),
      left: Math.round(r.left),
      top: Math.round(r.top),
      w: Math.round(r.width),
      h: Math.round(r.height),
    };
  });
  for (const id of ids) {
    document.documentElement.dataset.theme = id;
    void document.body.offsetWidth;
    out.push({ theme: id, items: seen() });
  }
  return out;
}, themeIds);
const byControl = new Map();
for (const t of controls) {
  for (const it of t.items || []) {
    const row = byControl.get(it.id) || { left: new Set(), top: new Set(), w: new Set(), h: new Set(), themes: 0 };
    row.left.add(it.left);
    row.top.add(it.top);
    row.w.add(it.w);
    row.h.add(it.h);
    row.themes += 1;
    byControl.set(it.id, row);
  }
}
console.log(`CONTROL GEOMETRY across ${controls.length} theme(s):`);
for (const [id, r] of byControl) {
  const drift = (set) => (set.size === 1 ? String([...set][0]) : `DRIFT ${[...set].join('/')}`);
  console.log(`  ${id}: left=${drift(r.left)} top=${drift(r.top)} w=${drift(r.w)} h=${drift(r.h)} in ${r.themes} theme(s)`);
}

const logos = await page.evaluate((ids) => {
  const out = [];
  const el = document.querySelector('.wordmark__name')
    || document.querySelector('.wordmark__text')
    || document.querySelector('.wordmark');
  if (!el) return [{ theme: 'none', note: 'sem .wordmark' }];
  for (const id of ids) {
    document.documentElement.dataset.theme = id;
    void document.body.offsetWidth;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    out.push({
      theme: id,
      fontSize: cs.fontSize,
      x: Math.round(r.left),
      top: Math.round(r.top),
    });
  }
  return out;
}, themeIds);
const sizeSet = new Set(logos.map((l) => l.fontSize));
const xSet = new Set(logos.map((l) => l.x));
const topSet = new Set(logos.map((l) => l.top));
console.log(`WORDMARK font-size values across ${logos.length} theme(s): ${[...sizeSet].join(', ')}`);
console.log(`WORDMARK x values: ${[...xSet].join(', ')}`);
console.log(`WORDMARK top values: ${[...topSet].join(', ')}`);
await browser.close();


/* WCAG CONTRASTE, CALCULADO. O dono pediu *"contraste bom, TODOS os textos no
 * historico vs o horario do texto"*, e a relacao que ele quer e' uma DIRECAO: o
 * horario mais escuro, o texto mais aceso. Uma razao calculada e' a unica forma
 * de dizer isso que nao e' opiniao -- `opacity` no horario entra na conta, porque
 * `getComputedStyle().color` ainda devolve a cor CHEIA e a transparencia e' do
 * elemento.
 *
 * O PISO E' 3:1 e nao 4,5:1 de proposito: o horario e' texto SECUNDARIO e o dono
 * PEDIU que ele fosse mais fraco. Abaixo de 3:1 ele ja' nao se le, e e' isso que
 * este numero acusa. */
function parseColor(str) {
  const m = String(str || '').match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(',').map((x) => parseFloat(x));
  return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
}
function flatten(c, bg) {
  if (!c) return null;
  const a = c.a == null ? 1 : c.a;
  if (!bg) return c;
  return {
    r: c.r * a + bg.r * (1 - a),
    g: c.g * a + bg.g * (1 - a),
    b: c.b * a + bg.b * (1 - a),
    a: 1,
  };
}
function luminance(c) {
  const f = (v) => {
    const x = v / 255;
    return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
}
function contrastRatio(a, b) {
  if (!a || !b) return null;
  const l1 = luminance(a);
  const l2 = luminance(b);
  const hi = Math.max(l1, l2);
  const lo = Math.min(l1, l2);
  return (hi + 0.05) / (lo + 0.05);
}

const bad = report.filter((t) => t.rows.some((r) => r.clippedX || r.clippedY || r.rowClippedX || r.rowClippedY));
const clamped = report.filter((t) => t.rows.some((r) => r.lineClamp !== 'none' && r.lineClamp !== 'normal'));
const centered = report.filter((t) => t.rows.some((r) => r.textAlign !== 'start' && r.textAlign !== 'left'));

console.log(`probe: ${themeIds.length} theme(s), ${report[0] ? report[0].rows.length : 0} row(s)`);
console.log(`CLIPPED rows in ${bad.length} theme(s)`);
for (const t of bad) {
  const sample = t.rows.find((r) => r.clippedX || r.clippedY || r.rowClippedX || r.rowClippedY);
  console.log(`  ${t.theme}: overflowX=${sample.overflowX} overflowY=${sample.overflowY}`
    + ` ws=${sample.whiteSpace} overflow=${sample.overflow} clamp=${sample.lineClamp}`
    + ` rowX=${sample.rowClippedX} rowY=${sample.rowClippedY}`);
}
console.log(`LINE-CLAMPED rows in ${clamped.length} theme(s)`);
const unreadable = [];
const louder = [];
for (const t of report) {
  for (const r of t.rows) {
    if (r.stamp == null) continue;
    if (r.stamp < 3) unreadable.push({ theme: t.theme, ...r });
    if (r.stamp >= r.body) louder.push({ theme: t.theme, ...r });
    break;
  }
}
const stamped = report.reduce((n, t) => n + (t.rows.some((r) => r.stamp != null) ? 1 : 0), 0);
console.log(`STAMP UNREADABLE (<3:1 over its own background) in ${unreadable.length} of ${stamped} theme(s)`);
for (const r of unreadable) console.log(`  ${r.theme}: stamp=${r.stamp}:1 body=${r.body}:1 (${r.timeColor} / opacity ${r.timeOpacity})`);
console.log(`STAMP LOUDER THAN TEXT in ${louder.length} theme(s)`);
for (const r of louder) console.log(`  ${r.theme}: stamp=${r.stamp}:1 body=${r.body}:1`);
for (const t of clamped) console.log(`  ${t.theme}: clamp=${t.rows.find((r) => r.lineClamp !== 'none').lineClamp}`);
console.log(`NOT LEFT-ALIGNED rows in ${centered.length} theme(s)`);
for (const t of centered) console.log(`  ${t.theme}: textAlign=${t.rows.find((r) => r.textAlign !== 'start' && r.textAlign !== 'left').textAlign}`);
if (errors.length) {
  console.log(`PAGE ERRORS: ${errors.length}`);
  for (const e of errors.slice(0, 5)) console.log('  ' + e);
}
if (JSON_OUT) writeFileSync(JSON_OUT, JSON.stringify({ themes: report, errors }, null, 2));
process.exit(bad.length || errors.length ? 1 : 0);
